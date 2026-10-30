"""Revisão 1 da B1.5 (`docs/REVISAO-B1.5-3010.md`): forma da entrada (R1-05, R1-06, R1-15, R1-16), texto de operador no config (R1-07, R1-17),
`/readyz` fechado sem a pasta de migrações (R1-09), alertas visíveis (R1-11), cache de config (R1-20), 503 de conexão (R1-30)."""

from __future__ import annotations

import json
import uuid

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


def test_datetime_post_mais_de_5_min_no_futuro_422_e_ate_5_min_vale(ambiente):
    abrir_ativo(ambiente)
    r = ambiente.evento_chatguru(mensagem_nativa("futuro", datetime_post="2026-12-31T10:00:00-03:00"))
    assert r.status_code == 422 and r.json()["erro"]["campo"] == "datetime_post"
    assert ambiente.evento_chatguru(mensagem_nativa("quase", datetime_post="2026-11-17T09:04:00-03:00")).json()["resultado"] == "gravado"
    assert ambiente.escalar("SELECT count(*) FROM ia.passo") == 1, "o futuro distante não chegou a msg_enviada_em"


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
