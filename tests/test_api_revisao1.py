"""Revisão 1 da B1.5 (`docs/REVISAO-B1.5-3010.md`): forma da entrada (R1-05, R1-06, R1-15, R1-16), texto de operador no config (R1-07, R1-17),
`/readyz` fechado sem a pasta de migrações (R1-09), alertas visíveis (R1-11), cache de config (R1-20), 503 de conexão (R1-30)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests import apoio_api
from tests.apoio_api import (
    CHAT,
    OUTRO_CHAT,
    PHONE,
    TOKENS,
    abrir_ativo,
    corpo_de_agendamento,
    corpo_de_entrada,
    mensagem_nativa,
)

ambiente = apoio_api.ambiente
pytestmark = pytest.mark.banco
CPF = "00000001234"  # 11 dígitos sintéticos (faixa 000.000.0nn)
POR = "operador.teste@glcapital.invalid"


def _codigo(r) -> str:
    return r.json()["erro"]["codigo"]


# --- R1-05: responsavel_email vazio ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "email,esperado",
    [("", False), ("   ", False), (None, False), ("humano.teste@glcapital.invalid", True), (" Humano.Teste@glcapital.invalid ", True)],
)
def test_responsavel_vazio_nao_marca_delegacao_externa(ambiente, email, esperado):
    abrir_ativo(ambiente)
    corpo = mensagem_nativa()
    corpo["responsavel_email"] = email
    assert ambiente.evento_chatguru(corpo).json()["delegacao_externa"] is esperado


# --- R1-06: instantes só como texto RFC 3339 com fuso --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "valor",
    [int(CPF), float(CPF), CPF, "1700000000", 1700000000, "2026-11-17", "2026-11-17T08:59:30", "2026-11-17 08:59:30-03:00", True, "0"],
)
def test_datetime_post_que_nao_e_rfc3339_com_fuso_422_sem_eco(ambiente, valor):
    abrir_ativo(ambiente)
    r = ambiente.evento_chatguru(mensagem_nativa(datetime_post=valor))
    assert r.status_code == 422 and r.json()["erro"]["campo"] == "datetime_post" and CPF not in r.text
    r = ambiente.post(
        "/eventos/mensagem",
        {"chat_id": CHAT, "phone_id": PHONE, "tipo": "texto", "texto": "oi", "origem_evento": "webhook", "datetime_post": valor},
        token="ti",
    )
    assert r.status_code == 422 and CPF not in r.text
    assert ambiente.escalar("SELECT count(*) FROM ia.passo") == 0


@pytest.mark.parametrize("valor", [int(CPF), CPF, "1700000000", "2026-11-17T08:41:07"])
def test_ultimo_cliente_em_e_datetime_do_agendamento_so_rfc3339_com_fuso(ambiente, valor):
    ambiente.ligar()
    r = ambiente.post("/atendimentos", corpo_de_entrada(ultimo_cliente_em=valor))
    assert r.status_code == 422 and r.json()["erro"]["campo"] == "ultimo_cliente_em" and CPF not in r.text
    outra = f"agendar:{CHAT}:0000000000000000"
    assert _codigo(ambiente.post("/agendamentos", corpo_de_agendamento(datetime_post=valor, chave=outra))) == "validacao"
    r = ambiente.post("/agendamentos", corpo_de_agendamento(ultimo_cliente_em=valor))
    assert r.status_code == 422 and CPF not in r.text
    assert ambiente.escalar("SELECT count(*) FROM ia.atendimento") == 0


def test_rfc3339_com_z_e_com_fracao_continua_valendo(ambiente):
    abrir_ativo(ambiente)
    for valor in ("2026-11-17T11:59:30Z", "2026-11-17T08:59:31.250-03:00", "2026-11-17T11:59:32z"):
        assert ambiente.evento_chatguru(mensagem_nativa(f"oi {valor}", datetime_post=valor)).json()["resultado"] == "gravado", valor


@pytest.mark.parametrize(
    "hora",
    [
        "2026-11-17T15:06:00Z",
        "2026-11-17T18:00:00-03:00",
        "2026-12-31T10:00:00-03:00",
        "2099-01-01T00:00:00Z",
    ],  # +6 min, fuso trocado (+3 h), meses, anos
)
@pytest.mark.parametrize("rota", ["chatguru", "mensagem"])
def test_datetime_post_adiantado_nao_perde_a_mensagem_grava_pelo_recebimento_e_marca_o_atendimento(ambiente, rota, hora):
    """R2-02: relógio (ou fuso) do ChatGuru/RPA adiantado é sinal para o TI, não motivo para descartar a mensagem real do cliente."""
    atd = abrir_ativo(ambiente)
    if rota == "chatguru":
        r = ambiente.evento_chatguru(mensagem_nativa("quero a proposta", datetime_post=hora))
    else:
        corpo = {
            "chat_id": CHAT,
            "phone_id": PHONE,
            "tipo": "texto",
            "texto": "quero a proposta",
            "origem_evento": "webhook",
            "datetime_post": hora,
        }
        r = ambiente.post("/eventos/mensagem", corpo, token="ti")
    assert r.status_code == 200 and r.json()["resultado"] == "gravado", r.text
    agora = ambiente.relogio.agora()
    assert ambiente.escalar("SELECT msg_enviada_em FROM ia.passo WHERE atendimento_id = %s", (atd,)) == agora, (
        "vale o recebimento, nunca a hora do futuro"
    )
    assert ambiente.escalar("SELECT ultimo_cliente_em FROM ia.atendimento WHERE atendimento_id = %s", (atd,)) == agora
    assert ambiente.escalar("SELECT contexto_codigos FROM ia.atendimento WHERE atendimento_id = %s", (atd,)) == ["relogio_futuro"]
    assert ambiente.ctx.metricas.valor("datetime_post_adiantado") == 1 and ambiente.fila.turnos == [(atd, CHAT)]


def test_datetime_post_adiantado_o_retry_do_gateway_nao_duplica_e_o_codigo_entra_uma_vez(ambiente):
    atd = abrir_ativo(ambiente)
    corpo = mensagem_nativa("quero a proposta", datetime_post="2026-12-31T10:00:00-03:00")
    assert ambiente.evento_chatguru(corpo).json()["resultado"] == "gravado"
    assert ambiente.evento_chatguru(corpo).json()["resultado"] == "repetido", "as 3 tentativas do ChatGuru chegam em segundos"
    assert ambiente.escalar("SELECT count(*) FROM ia.passo WHERE atendimento_id = %s", (atd,)) == 1
    ambiente.evento_chatguru(mensagem_nativa("outra", datetime_post="2099-01-01T00:00:00Z"))
    assert ambiente.escalar("SELECT contexto_codigos FROM ia.atendimento WHERE atendimento_id = %s", (atd,)) == ["relogio_futuro"]


def test_ate_5_min_a_frente_vale_a_hora_do_evento_e_sem_codigo(ambiente):
    atd = abrir_ativo(ambiente)
    assert ambiente.evento_chatguru(mensagem_nativa("quase", datetime_post="2026-11-17T09:04:00-03:00")).json()["resultado"] == "gravado"
    assert ambiente.escalar("SELECT msg_enviada_em FROM ia.passo WHERE atendimento_id = %s", (atd,)) == datetime(
        2026, 11, 17, 12, 4, tzinfo=UTC
    )
    assert ambiente.escalar("SELECT contexto_codigos FROM ia.atendimento WHERE atendimento_id = %s", (atd,)) == []
    assert ambiente.ctx.metricas.valor("datetime_post_adiantado") == 0


# --- R1-15 e R1-16 --------------------------------------------------------------------------------------------------------------------------


def test_json_profundo_demais_422_e_nao_500(ambiente):
    r = ambiente.post("/atendimentos", b"[" * 30_000 + b"]" * 30_000)
    assert r.status_code == 422 and r.json()["erro"]["campo"] == "(corpo)"


@pytest.mark.parametrize(
    "campo,valor", [("criterio_versao", CPF), ("banco", CPF), ("produto", CPF), ("responsavel_antes", CPF), ("disparado_por", CPF)]
)
def test_codigos_e_identidades_da_entrada_recusam_documento(ambiente, campo, valor):
    ambiente.ligar()
    r = ambiente.post("/atendimentos", corpo_de_entrada(**{campo: valor}))
    assert r.status_code == 422 and _codigo(r) == "pii_no_texto_livre" and r.json()["erro"]["campo"] == campo and CPF not in r.text


def test_disparado_por_precisa_ser_login_ou_email(ambiente):
    ambiente.ligar()
    r = ambiente.post("/atendimentos", corpo_de_entrada(disparado_por="Fulano da Silva"))
    assert r.status_code == 422 and r.json()["erro"]["campo"] == "disparado_por"


def test_candidatos_recusa_vira_codigo_de_ate_40_sem_documento(ambiente):
    atd = abrir_ativo(ambiente)
    sessao = str(uuid.uuid4())
    for recusa in (CPF, "a" * 41, "Com Espaço", "ja_em_atendimento_" + "x" * 30):
        corpo = {"criterio_versao": "c1.0", "candidatos": [{"chat_id": OUTRO_CHAT, "escolhido": False, "recusa": recusa, "perfil": {}}]}
        r = ambiente.post(f"/sessoes/{sessao}/candidatos", corpo)
        assert r.status_code == 422 and CPF not in r.text, recusa
    corpo = {"criterio_versao": CPF, "candidatos": [{"chat_id": CHAT, "escolhido": True, "atendimento_id": str(atd), "perfil": {}}]}
    assert _codigo(ambiente.post(f"/sessoes/{sessao}/candidatos", corpo)) == "pii_no_texto_livre"


# --- R1-07 e R1-17: texto de operador no config --------------------------------------------------------------------------------------------


def _calendario(ambiente, motivo, **extra):
    base = ambiente.get("/config/calendario_bloqueio").json()["valor"]
    janelas = [*base["janelas"], {"de": "2026-12-10T12:00:00-03:00", "ate": "2026-12-10T14:00:00-03:00", "motivo": motivo, **extra}]
    return {**base, "janelas": janelas}


@pytest.mark.parametrize("motivo", [f"cliente {CPF}", "fulano@glcapital.invalid", "Manutenção programada", "x" * 41, "", 7, None])
def test_motivo_de_janela_do_calendario_so_codigo_sem_documento(ambiente, motivo):
    r = ambiente.put("/config/calendario_bloqueio", {"valor": _calendario(ambiente, motivo), "por": POR})
    assert r.status_code == 422 and _codigo(r) == "valor_invalido" and CPF not in r.text and "fulano@" not in r.text
    assert ambiente.escalar("SELECT max(versao) FROM ia.config_versao WHERE nome = 'calendario_bloqueio'") == 1


def test_janela_com_chave_extra_e_recusada_e_codigo_valido_e_aceito(ambiente):
    r = ambiente.put("/config/calendario_bloqueio", {"valor": _calendario(ambiente, "manutencao", cpf=CPF), "por": POR})
    assert r.status_code == 422 and CPF not in r.text
    r = ambiente.put("/config/calendario_bloqueio", {"valor": _calendario(ambiente, "manutencao"), "por": POR})
    assert r.status_code == 200 and r.json()["versao"] == 2


def test_legado_de_texto_livre_no_calendario_volta_mascarado_no_get_na_lista_e_no_historico(ambiente):
    base = ambiente.get("/config/calendario_bloqueio").json()["valor"]
    sujo = {**base, "janelas": [{**base["janelas"][0], "motivo": f"ligar {CPF} fulano@glcapital.invalid"}], "cpf_do_cliente": CPF}
    with ambiente.super() as conn:
        conn.execute(
            "INSERT INTO ia.config_versao (nome, versao, valor, publicado_por) VALUES ('calendario_bloqueio', 2, %s::jsonb, 'legado')",
            (json.dumps(sujo),),
        )
    for caminho in ("/config/calendario_bloqueio", "/config/calendario_bloqueio?historico=2", "/config"):
        texto = ambiente.get(caminho).text
        assert CPF not in texto and "fulano@" not in texto, caminho
    assert ambiente.get("/config/calendario_bloqueio").json()["valor"]["janelas"][0]["motivo"] == "[mascarado]"
    assert ambiente.ctx.metricas.valor("texto_livre_mascarado_na_leitura") >= 3


@pytest.mark.parametrize("por", [CPF, f"operador.{CPF}@glcapital.invalid", "Fulano da Silva", "a" * 129, "", "nome;drop"])
def test_por_do_put_e_login_ou_email_sem_documento(ambiente, por):
    r = ambiente.put("/config/max_abertos", {"valor": 12, "por": por})
    assert r.status_code == 422 and CPF not in r.text
    assert ambiente.escalar("SELECT max(versao) FROM ia.config_versao WHERE nome = 'max_abertos'") == 1


def test_publicado_por_legado_com_documento_volta_mascarado(ambiente):
    with ambiente.super() as conn:
        conn.execute("INSERT INTO ia.config_versao (nome, versao, valor, publicado_por) VALUES ('max_abertos', 2, '12', %s)", (f"op{CPF}",))
    assert ambiente.get("/config/max_abertos").json()["publicado_por"] == "[mascarado]"
    assert POR in json.dumps(ambiente.put("/config/max_abertos", {"valor": 13, "por": POR}).json() | {"por": POR}), (
        "o e-mail do operador não é mascarado"
    )
    assert ambiente.get("/config/max_abertos").json()["publicado_por"] == POR


def test_operador_da_anotacao_recusa_documento_e_texto_livre(ambiente):
    atd = abrir_ativo(ambiente)
    corpo = {"operador": POR, "categoria": "observacao", "texto": "ok"}
    assert ambiente.post(f"/atendimentos/{atd}/anotacoes", corpo, token="ti").status_code == 201
    for operador in (CPF, f"op{CPF}@glcapital.invalid", "Fulano da Silva"):
        r = ambiente.post(f"/atendimentos/{atd}/anotacoes", {**corpo, "operador": operador}, token="ti")
        assert r.status_code == 422 and CPF not in r.text, operador


def test_o_token_do_c360_tambem_passa_pela_regra_do_por(ambiente):
    r = ambiente.put("/config/modo", {"valor": "sombra", "por": f"op{CPF}"}, token="c360_api")
    assert r.status_code == 422 and _codigo(r) == "pii_no_texto_livre"
    assert ambiente.put("/config/modo", {"valor": "sombra", "por": POR}, token="c360_api").status_code == 200
    assert TOKENS["c360_api"] not in r.text


# --- R1-09: /readyz falha FECHADO sem a pasta de migrações; a pasta viaja no wheel -------------------------------------------------------------


def test_readyz_sem_pasta_de_migracoes_e_503_e_nunca_200_sem_conferir(ambiente):
    with ambiente.super() as conn:
        conn.execute("INSERT INTO procrastinate.procrastinate_workers (last_heartbeat) VALUES (now() - interval '5 seconds')")
    assert ambiente.get("/readyz").status_code == 200
    ambiente.trocar(diretorio_migracoes=None)
    r = ambiente.get("/readyz")
    assert r.status_code == 503 and r.json()["erro"]["detalhe"]["falhas"] == ["migracoes_nao_conferidas"]


def test_subida_recusa_pasta_de_migracoes_ausente_ou_vazia(monkeypatch, tmp_path):
    from ia_atendimento.api.ambiente import _diretorio_de_migracoes
    from ia_atendimento.config import ConfiguracaoInvalida

    monkeypatch.delenv("IA_MIGRACOES_DIR", raising=False)
    assert (_diretorio_de_migracoes() / "0001_esquema.up.sql").exists(), "no checkout vale a pasta migrations/ do repositório"
    monkeypatch.setenv("IA_MIGRACOES_DIR", str(tmp_path / "nao-existe"))
    with pytest.raises(ConfiguracaoInvalida):
        _diretorio_de_migracoes()
    monkeypatch.setenv("IA_MIGRACOES_DIR", str(tmp_path))
    with pytest.raises(ConfiguracaoInvalida):
        _diretorio_de_migracoes()
    monkeypatch.setenv("IA_MIGRACOES_DIR", str(Path(__file__).resolve().parent.parent / "migrations"))
    assert _diretorio_de_migracoes().name == "migrations"


def test_o_wheel_leva_as_migracoes_como_dados_do_pacote():
    import tomllib
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    wheel = tomllib.loads((raiz / "pyproject.toml").read_text())["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel["force-include"] == {"migrations": "ia_atendimento/migrations"}


# --- R1-30, R1-11, R1-25, R1-20 -------------------------------------------------------------------------------------------------------------


def test_conexao_fechada_pelo_pool_e_503_e_nao_500(ambiente):
    import psycopg

    def quebrada():
        raise psycopg.InterfaceError("connection is closed")

    ambiente.trocar(conexao=quebrada)
    r = ambiente.get("/saude")
    assert r.status_code == 503 and _codigo(r) == "nao_pronto"


def test_alertas_dos_contadores_aparecem_no_log(ambiente, caplog):
    with ambiente.super() as conn:
        conn.execute(
            "INSERT INTO ia.config_versao (nome, versao, valor, publicado_por, motivo) VALUES ('max_abertos', 2, '12', 'legado', %s)",
            (f"cpf {CPF}",),
        )
    with caplog.at_level("WARNING"):
        ambiente.get("/config/max_abertos")
    assert "alerta ti: contador=texto_livre_mascarado_na_leitura total=1" in caplog.text and CPF not in caplog.text


def test_casamento_com_chave_do_mes_descartada_deixa_alerta_no_log(ambiente, caplog):
    import os

    from ia_atendimento.cifra import Chaveiro
    from ia_atendimento.mensagens import _texto_do_passo

    atd = abrir_ativo(ambiente)
    assert ambiente.evento_chatguru(mensagem_nativa()).json()["resultado"] == "gravado"
    sem_a_chave = Chaveiro({1: os.urandom(32)}, vigente=1)  # a chave 2, que cifrou, foi descartada
    with ambiente.runtime() as conn, caplog.at_level("WARNING"):
        assert _texto_do_passo(conn, atd, 1, sem_a_chave) is None
    assert "alerta ti: casamento sem a chave do mês" in caplog.text


def test_put_invalida_o_cache_depois_do_commit(ambiente, monkeypatch):
    """Uma leitura concorrente entre o `registrar` e o commit repõe o valor velho no cache; o PUT o limpa de novo ao fim."""
    from ia_atendimento.chave import LeitorConfig

    leitor = LeitorConfig(ambiente.relogio, ttl_s=5)
    ambiente.trocar(leitor=leitor)
    registrar = LeitorConfig.registrar

    def registrar_e_deixar_leitura_velha_no_cache(self, conn, nome, valor, por, **opcoes):
        nova = registrar(self, conn, nome, valor, por, **opcoes)
        self._cache = {**self._cache, nome: (self._relogio.agora(), None)}  # a leitura concorrente repôs algo velho
        return nova

    monkeypatch.setattr(LeitorConfig, "registrar", registrar_e_deixar_leitura_velha_no_cache)
    assert ambiente.put("/config/max_abertos", {"valor": 12, "por": POR}).status_code == 200
    with ambiente.runtime() as conn:
        assert leitor.valor(conn, "max_abertos") == 12
