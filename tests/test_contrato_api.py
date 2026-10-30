"""Testes de contrato da API (contrato 08 §14): vetores dourados, rotas, catálogo de erros, assinatura do gateway e casamento webhook × RPA.

O contrato mora fora do repositório (`/opt/claude/docs/planejamento-ia/contratos/08-orquestrador.md`, ou `CONTRATO_08_PATH`): os testes que o leem são
pulados onde ele não está, e cada um tem um instantâneo embutido que vale em qualquer máquina.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ia_atendimento import agendamento as ag
from ia_atendimento import estado
from ia_atendimento.api.auth import assinatura_esperada
from ia_atendimento.api.erros import CODIGOS_AUXILIARES, CODIGOS_DO_CONTRATO
from ia_atendimento.estado_conversa import registrar_mensagem_do_cliente
from ia_atendimento.evento_mensagem import ChavesDeMensagem, EventoMensagem, identidade
from tests import apoio_api
from tests.apoio_api import (
    CHAT,
    CHAT_TESTE,
    CHAVE_GATEWAY,
    CHAVE_GATEWAY_NOVA,
    FINGERPRINT,
    H16,
    OUTRO_CHAT,
    PESSOA,
    PHONE,
    TOKENS,
    abrir_ativo,
    corpo_de_entrada,
    mensagem_nativa,
)
from tests.estado_apoio import entrada as entrada_de_estado

ambiente = apoio_api.ambiente
CONTRATO = Path(os.environ.get("CONTRATO_08_PATH", "/opt/claude/docs/planejamento-ia/contratos/08-orquestrador.md"))
ROTAS_DO_CONTRATO = {
    ("POST", "/atendimentos"), ("GET", "/atendimentos/por-chave/{chave}"), ("POST", "/eventos/chatguru"), ("POST", "/eventos/mensagem"),
    ("POST", "/agendamentos"), ("GET", "/config"), ("GET", "/config/{nome}"), ("PUT", "/config/{nome}"),
    ("POST", "/atendimentos/{atendimento_id}/anotacoes"), ("POST", "/sessoes/{sessao_id}/candidatos"), ("GET", "/healthz"), ("GET", "/readyz"), ("GET", "/saude"),
}  # fmt: skip
# instantâneo da tabela de §2 (contrato 08 v2.1): o teste que lê o arquivo confere que ainda é este
CODIGOS_DO_CONTRATO_V21 = {
    "token_invalido", "assinatura_invalida", "origem_nao_autorizada", "origem_teste_fora_da_lista", "atendimento_inexistente", "config_inexistente",
    "ia_desligada", "bloqueio_entrada", "fora_de_janela", "opt_out", "janela_24h", "teto_atingido", "teto_diario", "disparos_dia", "abertos_max",
    "chat_ocupado", "chave_reutilizada", "provedor_fora", "pre_voo_falhou", "agenda_desligada", "agenda_max_dia", "config_corrida", "payload_grande",
    "validacao", "campo_desconhecido", "campo_fora_da_allowlist", "gatilho_desabilitado", "chave_incoerente", "faixa_incoerente", "teste_fora_da_lista",
    "persona_fora_de_teste", "pessoa_fora_de_pessoas_teste", "valor_invalido", "modo_teste_global", "chat_de_cliente", "pii_no_texto_livre",
    "artefatos_ausentes", "nao_pronto",
}  # fmt: skip
CPF_SINTETICO = "000.000.012-34"
CELULAR = "5511912345678"


# --- vetores dourados (sem banco) ---------------------------------------------------------------------------------------------------------


def test_fingerprint_vetor_dourado():
    entrada = entrada_de_estado()  # o exemplo de §3
    assert estado.entrada_fingerprint(entrada) == "b8da81fb3df655ca7f76f648613991e4a8291667ea7941b3a1c8d699d4636650"
    assert estado.idempotency_key(entrada.chave_logica) == "87efe21cc58f3483825867fe9cfe0a4a2ebd36ecbc8be6dd454a5e47ed20726d"


def test_fingerprint_ignora_perfil_sessao_disparado_por_ultimo_cliente_e_chat_number():
    base = estado.entrada_fingerprint(entrada_de_estado())
    mudou = entrada_de_estado(
        perfil={"banco": "C6"}, sessao_id=str(uuid.uuid4()), disparado_por="outro@glcapital.invalid", ultimo_cliente_em="2026-11-24T10:00:00-03:00",
        motivo_escolha="oferta_forte", criterio_versao="c2.0", banco="C6", produto="CLT", responsavel_antes="x", perfil_versao=3,
    )  # fmt: skip
    assert estado.entrada_fingerprint(mudou) == base


def test_fingerprint_inclui_pessoa_chat_e_clt_job():
    base = estado.entrada_fingerprint(entrada_de_estado())
    for mudar in (
        {"pessoa_id": "44444444-4444-7444-8444-444444444444"},
        {"chat_id": OUTRO_CHAT},
        {"clt_job_id": str(uuid.uuid4())},
        {"phone_id": OUTRO_CHAT},
    ):
        assert estado.entrada_fingerprint(entrada_de_estado(**mudar)) != base, mudar


def test_fingerprint_null_igual_a_ausente_e_ordem_das_chaves_nao_importa():
    identidade_a = {"chat_id": CHAT, "clt_job_id": None, "gatilho": "venda", "persona_id": None}
    identidade_b = {"persona_id": None, "gatilho": "venda", "chat_id": CHAT}
    assert estado.fingerprint_de_identidade(identidade_a) == estado.fingerprint_de_identidade(identidade_b)
    assert estado.fingerprint_de_identidade(identidade_a) != estado.fingerprint_de_identidade({**identidade_a, "persona_id": "P01"})


def _evento_do_vetor(**mudar) -> EventoMensagem:
    campos = {"chat_id": CHAT, "phone_id": PHONE, "tipo": "texto", "texto": "oi, quero saber da proposta", "origem_evento": "webhook",
              "datetime_post": datetime.fromisoformat("2026-11-24T10:15:30-03:00")}  # fmt: skip
    return EventoMensagem.criar(**{**campos, **mudar})


def test_msg_chave_h16_vetor_e_estavel_e_sem_texto_em_claro():
    chaves = ChavesDeMensagem(H16.encode(), FINGERPRINT.encode())
    ident = identidade(_evento_do_vetor(), chaves)
    assert ident.msg_chave == f"cg:{CHAT}:be0f44572b7488ed"
    assert identidade(_evento_do_vetor(), chaves).msg_chave == ident.msg_chave
    assert "proposta" not in ident.msg_chave + ident.msg_fingerprint


def test_fingerprint_vetor_hmac_d91e6bf4():
    """R2/S2: HMAC com a `chave_fingerprint`, não sha256 puro (o vetor `924ee977…` da v2 não vale mais)."""
    ident = identidade(_evento_do_vetor(), ChavesDeMensagem(H16.encode(), FINGERPRINT.encode()))
    assert ident.msg_fingerprint == "d91e6bf4176d42e4a6af732ecda90217a3bbcdea5aadf9de756a8ac087a06dd4"
    outra = identidade(_evento_do_vetor(), ChavesDeMensagem(H16.encode(), b"outra-chave-fingerprint-descartavel-02"))
    assert outra.msg_fingerprint != ident.msg_fingerprint


def test_boot_recusa_chave_fingerprint_ausente_curta_ou_igual_a_h16():
    from pydantic import ValidationError

    from tests.apoio_api import TOKENS as _  # noqa: F401
    from tests.test_config import BASE

    with pytest.raises(ValueError, match="32"):
        ChavesDeMensagem(H16.encode(), b"curta")
    with pytest.raises(ValueError, match="diferentes"):
        ChavesDeMensagem(H16.encode(), H16.encode())
    from ia_atendimento.config import Settings

    campos = {k.lower(): v for k, v in BASE.items() if k != "API_TOKENS"}
    campos["api_tokens"] = {"ti": TOKENS["ti"]}
    for ruim in ({"chave_fingerprint": ""}, {"chave_fingerprint": "curta"}, {"chave_fingerprint": campos["chave_h16"]}):
        with pytest.raises(ValidationError):
            Settings(**{**campos, **ruim})


def test_assinatura_vetor_dourado_do_gateway():
    corpo = (
        b'{"chat_id":"0123456789abcdef01234567","phone_id":"89abcdef0123456789abcdef","tipo_mensagem":"chat",'
        b'"texto_mensagem":"oi, quero saber da proposta","datetime_post":"2026-11-24T10:15:30-03:00"}'
    )
    chave = b"chave-de-teste-descartavel-do-contrato-01"
    assert assinatura_esperada(chave, "chatguru-ia", "ia-mensagem", "1795526131", corpo) == (
        "v1=2a0ce825983fe6f37799435e3323da60083e6c3195b669491a91a92450e94b02"
    )
    assert assinatura_esperada(chave, "chatguru-ia-teste", "ia-mensagem", "1795526131", corpo) == (
        "v1=d15ca8795ff1ecc9cf57188c7518545a6f582e3f1decaa464496083b916d5204"
    )


def test_agendamento_chave_vetor_dourado():
    """Os cinco valores de 04 §6: três jeitos de escrever o mesmo instante e um instante diferente."""
    esperado = {
        "2026-11-24T10:15:30-03:00": "025f6a9ea3e702e7", "2026-11-24T13:15:30Z": "025f6a9ea3e702e7", "2026-11-24T10:15:30.987-03:00": "025f6a9ea3e702e7",
        "2026-11-24T18:45:30+05:30": "025f6a9ea3e702e7", "2026-11-25T00:00:00-03:00": "08ca03480ca1d427",
    }  # fmt: skip
    for texto, sufixo in esperado.items():
        instante = datetime.fromisoformat(texto)
        assert ag.sufixo16(instante) == sufixo, texto
        assert ag.chave_logica_do_agendamento(CHAT, instante) == f"agendar:{CHAT}:{sufixo}"
    assert ag.datetime_utc_texto(datetime.fromisoformat("2026-11-24T10:15:30.987-03:00")) == "2026-11-24T13:15:30Z"


def test_agendamento_msg_chave_cg_cabe_no_check_da_0001():
    msg = ag.msg_chave_do_agendamento(CHAT, datetime.fromisoformat("2026-11-24T10:15:30-03:00"))
    assert msg == f"cg:{CHAT}:025f6a9ea3e702e7"
    sql = (Path(__file__).resolve().parent.parent / "migrations" / "0001_esquema.up.sql").read_text(encoding="utf-8")
    padrao = re.search(r"msg_chave ~ '(\^\(cg:\[A-Za-z0-9\]\{8,64\}:\[0-9a-f\]\{16\}\|[^']+)'", sql)
    assert padrao is not None and re.fullmatch(padrao.group(1), msg)
    assert re.fullmatch(
        r"^agendar?:[A-Za-z0-9_.:-]{1,180}$", ag.chave_logica_do_agendamento(CHAT, datetime.fromisoformat("2026-11-24T10:15:30-03:00"))
    )


# --- rotas e catálogo -------------------------------------------------------------------------------------------------------------------


def test_rotas_do_openapi_iguais_as_do_contrato(ambiente):
    do_openapi = {(metodo.upper(), caminho) for caminho, item in ambiente.cliente.app.openapi()["paths"].items() for metodo in item}
    assert do_openapi == ROTAS_DO_CONTRATO and len(do_openapi) == 13


def test_codigos_de_erro_do_enum_iguais_a_tabela_do_contrato():
    assert set(CODIGOS_DO_CONTRATO) == CODIGOS_DO_CONTRATO_V21 and not set(CODIGOS_AUXILIARES) & set(CODIGOS_DO_CONTRATO)
    assert {c: s for c, s in CODIGOS_DO_CONTRATO.items() if s == 401} == {"token_invalido": 401, "assinatura_invalida": 401}


@pytest.mark.skipif(not CONTRATO.exists(), reason="contrato 08 fora desta máquina (CONTRATO_08_PATH)")
def test_codigos_de_erro_batem_com_o_arquivo_do_contrato():
    tabela = CONTRATO.read_text(encoding="utf-8").split("## 2. Catálogo de erros", 1)[1].split("**Eventos não usam 404", 1)[0]
    achados: dict[str, int] = {}
    for linha in tabela.splitlines():
        celulas = [c.strip() for c in linha.strip().strip("|").split("|")]
        if len(celulas) < 3 or not re.match(r"^\d{3}", celulas[0]):
            continue
        status = int(celulas[0][:3])
        for codigo in re.findall(r"`([a-z0-9_]+)`", celulas[0]) + re.findall(r"`(campo_[a-z_]+)`", linha):
            achados[codigo] = status
    assert achados == CODIGOS_DO_CONTRATO, set(achados) ^ set(CODIGOS_DO_CONTRATO)


@pytest.mark.skipif(not CONTRATO.exists(), reason="contrato 08 fora desta máquina (CONTRATO_08_PATH)")
def test_as_13_rotas_do_contrato_estao_no_arquivo():
    texto = CONTRATO.read_text(encoding="utf-8")
    for metodo, caminho in ROTAS_DO_CONTRATO:
        molde = re.sub(r"\\\{[a-z_]+\\\}", r"\\{[a-z]+\\}", re.escape(caminho))
        assert re.search(molde, texto), (metodo, caminho)


def _chamar(ambiente, metodo: str, caminho: str, token: str | None):
    caminho = caminho.format(chave="venda:" + "a" * 32, nome="modo", atendimento_id=uuid.uuid4(), sessao_id=uuid.uuid4())
    headers = {"x-ia-token": TOKENS[token]} if token else {}
    return ambiente.cliente.request(metodo, caminho, headers={**headers, "content-type": "application/json"}, content=b"{}")


def test_healthz_sem_token_e_o_resto_401(ambiente):
    assert _chamar(ambiente, "GET", "/healthz", None).status_code == 200
    for metodo, caminho in sorted(ROTAS_DO_CONTRATO - {("GET", "/healthz")}):
        r = _chamar(ambiente, metodo, caminho, None)
        assert r.status_code == 401 and r.json()["erro"]["codigo"] == "token_invalido", (metodo, caminho)
        assert r.json() == {
            **r.json(),
            "erro": {"codigo": "token_invalido", "mensagem": "Token ausente ou inválido.", "campo": None, "detalhe": {}},
        }


def test_origem_errada_403_por_rota(ambiente):
    permitidas = {
        ("POST", "/atendimentos"): {"n8n_braco"}, ("GET", "/atendimentos/por-chave/{chave}"): {"n8n_braco", "vigia", "ti"},
        ("POST", "/eventos/mensagem"): {"ti"}, ("POST", "/eventos/chatguru"): {"ti"}, ("POST", "/agendamentos"): {"n8n_braco"},
        ("POST", "/sessoes/{sessao_id}/candidatos"): {"n8n_braco"}, ("GET", "/config"): {"n8n_braco", "ti", "c360_api", "vigia"},
        ("GET", "/config/{nome}"): {"n8n_braco", "ti", "c360_api", "vigia"}, ("PUT", "/config/{nome}"): {"ti", "c360_api"},
        ("POST", "/atendimentos/{atendimento_id}/anotacoes"): {"ti"},
    }  # fmt: skip
    for (metodo, caminho), origens in permitidas.items():
        for origem in TOKENS:
            r = _chamar(ambiente, metodo, caminho, origem)
            if origem in origens:
                assert r.status_code != 403, (metodo, caminho, origem)
            else:
                assert r.status_code == 403 and r.json()["erro"]["codigo"] == "origem_nao_autorizada", (metodo, caminho, origem)
    for origem in TOKENS:  # readyz e saude: qualquer token válido
        assert _chamar(ambiente, "GET", "/saude", origem).status_code == 200


def test_corpo_com_cpf_ou_celular_422_sem_ecoar_valor(ambiente):
    ambiente.ligar()
    for extra in ({"cpf": CPF_SINTETICO}, {"celular": CELULAR}, {"telefone": CELULAR, "documento": CPF_SINTETICO}):
        r = ambiente.post("/atendimentos", corpo_de_entrada(**extra))
        assert r.status_code == 422 and CPF_SINTETICO not in r.text and CELULAR not in r.text
    r = ambiente.post("/atendimentos", corpo_de_entrada(chat_number="valor-que-nao-e-telefone"))
    assert r.status_code == 422 and "valor-que-nao" not in r.text
    assert ambiente.escalar("SELECT count(*) FROM ia.atendimento") == 0


def test_pii_no_texto_livre_422_e_mascara_na_leitura(ambiente):
    ambiente.ligar()
    for alvo in (
        corpo_de_entrada(motivo_escolha="outro", motivo_escolha_nota="cliente 000.000.012-34"),
        corpo_de_entrada(perfil={"contato": CELULAR}),
        corpo_de_entrada(perfil={"id": str(uuid.uuid4())}),
    ):
        r = ambiente.post("/atendimentos", alvo)
        assert r.status_code == 422, alvo
        assert CPF_SINTETICO not in r.text and CELULAR not in r.text
    ok = ambiente.post("/atendimentos", corpo_de_entrada(motivo_escolha="outro", motivo_escolha_nota="oferta forte do dia"))
    assert ok.status_code == 201


def test_ordem_das_recusas_da_entrada(ambiente):
    """Cada correção revela a PRÓXIMA recusa, na ordem do catálogo (08 §2): ia_desligada → bloqueio → janela → opt_out → 24h → tetos → disparos → abertos."""
    ambiente.relogio.definir(datetime(2026, 11, 23, 15, 0, tzinfo=UTC))  # segunda 23/11, 12:00
    abrir_ativo(ambiente, OUTRO_CHAT, estado="aberto")  # 1 aberto e 1 disparo de hoje (segunda)
    ambiente.configurar("ia_ativa", False)
    ambiente.configurar("bloqueio_entrada", True)
    ambiente.relogio.definir(datetime(2026, 11, 22, 15, 0, tzinfo=UTC))  # domingo
    with ambiente.super() as conn:
        conn.execute(
            "INSERT INTO ia.opt_out (pessoa_id, tipo, origem, chave_logica, idem_key, registrado_por) VALUES (%s, 'opt_out', 'operador', 't14:x',"
            " encode(sha256(convert_to('t14:x','UTF8')),'hex'), 'teste')",
            (PESSOA,),
        )
    ambiente.configurar("teto_mensal_brl", 0)
    ambiente.configurar("subteto_dia", 0)
    ambiente.configurar("agenda_max_dia", 1)
    ambiente.configurar("max_disparos_dia", 1)
    ambiente.configurar("max_abertos", 1)
    velho = corpo_de_entrada(ultimo_cliente_em="2026-11-18T10:00:00-03:00")  # 4 dias antes do domingo

    def codigo() -> str:
        return ambiente.post("/atendimentos", velho).json()["erro"]["codigo"]

    assert codigo() == "ia_desligada"
    ambiente.configurar("ia_ativa", True)
    assert codigo() == "bloqueio_entrada"
    ambiente.configurar("bloqueio_entrada", False)
    assert codigo() == "fora_de_janela"
    ambiente.relogio.definir(datetime(2026, 11, 23, 15, 0, tzinfo=UTC))  # segunda 23/11, 12:00
    assert codigo() == "opt_out"
    with ambiente.super() as conn:
        conn.execute(
            "INSERT INTO ia.opt_out (pessoa_id, tipo, origem, chave_logica, idem_key, registrado_por) VALUES (%s, 'consentimento', 'operador', 't14:y',"
            " encode(sha256(convert_to('t14:y','UTF8')),'hex'), 'teste')",
            (PESSOA,),
        )
    assert codigo() == "janela_24h"
    velho = corpo_de_entrada(ultimo_cliente_em="2026-11-23T10:00:00-03:00")
    assert codigo() == "teto_atingido"
    ambiente.configurar("teto_mensal_brl", 2000)
    assert codigo() == "teto_diario"
    ambiente.configurar("subteto_dia", 100)
    assert codigo() == "disparos_dia"
    ambiente.configurar("max_disparos_dia", 10)
    assert codigo() == "abertos_max"
    ambiente.configurar("max_abertos", 10)
    assert ambiente.post("/atendimentos", velho).status_code == 201


def test_chats_teste_21_ids_ou_nao_hex_422(ambiente):
    por = "operador.teste@glcapital.invalid"
    ids = [f"{i:024x}" for i in range(21)]
    for valor in (ids, ["chat_com_sublinhado"], ["0123456789ABCDEF01234567"], [CHAT, CHAT], "texto", [7]):
        r = ambiente.put("/config/chats_teste", {"valor": valor, "por": por})
        assert r.status_code == 422 and r.json()["erro"]["codigo"] == "valor_invalido", valor


def test_chat_com_atendimento_real_ou_sombra_nao_entra_em_chats_teste(ambiente):
    por = "operador.teste@glcapital.invalid"
    for modo in ("real", "sombra"):
        abrir_ativo(ambiente, CHAT_TESTE, estado="encerrado", modo=modo)
        r = ambiente.put("/config/chats_teste", {"valor": [CHAT_TESTE], "por": por})
        assert r.status_code == 422 and r.json()["erro"]["codigo"] == "chat_de_cliente", modo
        with ambiente.super() as conn:
            conn.execute("DELETE FROM ia.atendimento WHERE chat_id = %s", (CHAT_TESTE,))


def test_ultimo_cliente_em_so_avanca_e_nao_incrementa_versao(ambiente):
    atd = abrir_ativo(ambiente)
    versao = ambiente.escalar("SELECT versao FROM ia.atendimento WHERE atendimento_id = %s", (atd,))
    with ambiente.runtime() as conn:
        t1 = datetime(2026, 11, 17, 14, 0, tzinfo=UTC)
        relogio = lambda: datetime(2026, 11, 17, 15, 0, tzinfo=UTC)  # noqa: E731
        assert registrar_mensagem_do_cliente(conn, atd, t1, relogio=relogio) == t1
        assert registrar_mensagem_do_cliente(conn, atd, t1 - timedelta(hours=2), relogio=relogio) == t1, (
            "mensagem antiga não recua a janela"
        )
        assert registrar_mensagem_do_cliente(conn, atd, t1 + timedelta(minutes=5), relogio=relogio) == t1 + timedelta(minutes=5)
    assert ambiente.escalar("SELECT versao FROM ia.atendimento WHERE atendimento_id = %s", (atd,)) == versao


def test_put_config_efeitos_so_encerrar_por_chave_agendados(ambiente):
    por = "operador.teste@glcapital.invalid"
    for nome, valor in (("max_abertos", 12), ("ia_ativa", True), ("ia_ativa", False), ("bloqueio_entrada", True), ("modo", "sombra")):
        r = ambiente.put(f"/config/{nome}", {"valor": valor, "por": por})
        assert r.status_code == 200 and set(r.json()) == {"nome", "versao", "valor", "publicado_em", "efeitos"}, nome
        assert set(r.json()["efeitos"]) == {"encerrar_por_chave_agendados"}, nome


def test_reexecucao_do_post_devolve_sempre_atendimento_id(ambiente):
    """F10: o n8n repete depois de uma queda e reconcilia a reserva; em qualquer estado a resposta traz id, estado e repetido."""
    ambiente.ligar()
    primeira = ambiente.post("/atendimentos", corpo_de_entrada())
    assert primeira.status_code == 201
    atd = primeira.json()["atendimento_id"]
    with ambiente.super() as conn:
        conn.execute(
            "UPDATE ia.atendimento SET estado = 'encerrado', desfecho = 'sem_venda', encerrado_em = now(), lease_ate = NULL WHERE atendimento_id = %s",
            (atd,),
        )
    r = ambiente.post("/atendimentos", corpo_de_entrada())
    assert r.status_code == 200 and (r.json()["atendimento_id"], r.json()["estado"], r.json()["repetido"]) == (atd, "encerrado", True)


# --- eventos: assinatura do gateway ------------------------------------------------------------------------------------------------------


def _bruto(corpo: dict) -> bytes:
    return json.dumps(corpo, separators=(",", ":"), ensure_ascii=False).encode()


def test_evento_sem_assinatura_401(ambiente):
    abrir_ativo(ambiente)
    r = ambiente.cliente.post("/eventos/chatguru", content=_bruto(mensagem_nativa()), headers={"content-type": "application/json"})
    assert r.status_code == 401 and r.json()["erro"]["codigo"] == "token_invalido"
    assert ambiente.escalar("SELECT count(*) FROM ia.passo") == 0


def test_assinatura_valida_grava_e_chave_nova_na_virada_tambem_vale(ambiente):
    abrir_ativo(ambiente)
    bruto = _bruto(mensagem_nativa())
    assert ambiente.cliente.post("/eventos/chatguru", content=bruto, headers=ambiente.assinar(bruto)).json()["resultado"] == "gravado"
    ambiente.trocar(gateway_hmac=(CHAVE_GATEWAY.encode(), CHAVE_GATEWAY_NOVA.encode()))  # a rotação: duas chaves valem
    outro = _bruto(mensagem_nativa("segunda", datetime_post="2026-11-17T09:01:00-03:00"))
    assert (
        ambiente.cliente.post("/eventos/chatguru", content=outro, headers=ambiente.assinar(outro, chave=CHAVE_GATEWAY_NOVA)).json()[
            "resultado"
        ]
        == "gravado"
    )
    terceiro = _bruto(mensagem_nativa("terceira", datetime_post="2026-11-17T09:02:00-03:00"))
    r = ambiente.cliente.post(
        "/eventos/chatguru", content=terceiro, headers=ambiente.assinar(terceiro, chave="chave-que-nunca-foi-do-gateway-0123456789")
    )
    assert r.status_code == 401 and r.json()["erro"]["codigo"] == "assinatura_invalida"


@pytest.mark.parametrize("segundos", [301, -301, 3600, -86400])
def test_assinatura_com_timestamp_velho_ou_do_futuro_401(ambiente, segundos):
    abrir_ativo(ambiente)
    bruto = _bruto(mensagem_nativa())
    agora = int(ambiente.relogio.agora().timestamp())
    r = ambiente.cliente.post("/eventos/chatguru", content=bruto, headers=ambiente.assinar(bruto, agora=agora - segundos))
    assert r.status_code == 401 and r.json()["erro"]["codigo"] == "assinatura_invalida"
    assert ambiente.escalar("SELECT count(*) FROM ia.passo") == 0


@pytest.mark.parametrize("segundos", [0, 299, 300, -300])
def test_assinatura_dentro_da_tolerancia_de_300s_vale(ambiente, segundos):
    abrir_ativo(ambiente)
    bruto = _bruto(mensagem_nativa())
    agora = int(ambiente.relogio.agora().timestamp())
    assert (
        ambiente.cliente.post("/eventos/chatguru", content=bruto, headers=ambiente.assinar(bruto, agora=agora - segundos)).status_code
        == 200
    )


def test_assinatura_de_outra_rota_ou_origem_trocada_401(ambiente):
    abrir_ativo(ambiente)
    bruto = _bruto(mensagem_nativa())
    for opcoes in ({"rota": "ia-repasse"}, {"origem": "chatguru-ia-outra"}, {"rota": ""}, {"origem": ""}):
        r = ambiente.cliente.post("/eventos/chatguru", content=bruto, headers=ambiente.assinar(bruto, **opcoes))
        assert r.status_code == 401 and r.json()["erro"]["codigo"] == "assinatura_invalida", opcoes
    # assinada como produção, apresentada como teste: a origem faz parte do HMAC
    cabecalhos = {**ambiente.assinar(bruto, origem="chatguru-ia"), "x-gl-origem": "chatguru-ia-teste"}
    assert ambiente.cliente.post("/eventos/chatguru", content=bruto, headers=cabecalhos).status_code == 401
    # um byte a mais no corpo
    assert ambiente.cliente.post("/eventos/chatguru", content=bruto + b" ", headers=ambiente.assinar(bruto)).status_code == 401
    # cabeçalho faltando e assinatura mal formada
    for tirar in ("x-gl-origem", "x-gl-rota", "x-gl-timestamp", "x-gl-assinatura"):
        cab = ambiente.assinar(bruto)
        del cab[tirar]
        assert ambiente.cliente.post("/eventos/chatguru", content=bruto, headers=cab).status_code == 401, tirar
    cab = {**ambiente.assinar(bruto), "x-gl-timestamp": "99999999999999999999999"}
    assert ambiente.cliente.post("/eventos/chatguru", content=bruto, headers=cab).status_code == 401
    assert ambiente.escalar("SELECT count(*) FROM ia.passo") == 0


def test_401_de_assinatura_tem_corpo_identico_qualquer_que_seja_a_falha(ambiente):
    bruto = _bruto(mensagem_nativa())
    corpos = set()
    for cab in (
        {**ambiente.assinar(bruto), "x-gl-assinatura": "v1=" + "0" * 64},
        ambiente.assinar(bruto, agora=1),
        {**ambiente.assinar(bruto), "x-gl-rota": "outra"},
    ):
        r = ambiente.cliente.post("/eventos/chatguru", content=bruto, headers=cab)
        corpos.add(json.dumps({**r.json(), "trace_id": ""}, sort_keys=True))
    assert len(corpos) == 1


def test_x_ia_token_nao_substitui_assinatura_quando_ela_vem(ambiente):
    abrir_ativo(ambiente)
    bruto = _bruto(mensagem_nativa())
    cab = {**ambiente.assinar(bruto), "x-gl-assinatura": "v1=" + "0" * 64, "x-ia-token": TOKENS["ti"]}
    r = ambiente.cliente.post("/eventos/chatguru", content=bruto, headers=cab)
    assert r.status_code == 401 and r.json()["erro"]["codigo"] == "assinatura_invalida"
    # nem o token de outra origem vale na rota do gateway; o `ti` (replay manual, sem x-gl-*) vale e entra como replay
    assert ambiente.post("/eventos/chatguru", mensagem_nativa(), token="n8n_braco").status_code == 403
    r = ambiente.post("/eventos/chatguru", mensagem_nativa(), token="ti")
    assert r.status_code == 200 and r.json()["resultado"] == "gravado"
    assert ambiente.escalar("SELECT origem_evento FROM ia.passo") == "replay"


@pytest.mark.parametrize("cabecalho", ["x-gl-origem", "x-gl-rota", "x-gl-timestamp", "x-gl-assinatura", "x-gl-foo"])
def test_x_gl_parcial_mais_token_ti_continua_401(ambiente, cabecalho):
    """Qualquer `x-gl-*`, mesmo sozinho, obriga a assinatura valer: o token `ti` não é a queda."""
    abrir_ativo(ambiente)
    r = ambiente.cliente.post(
        "/eventos/chatguru",
        content=_bruto(mensagem_nativa()),
        headers={cabecalho: "valor", "x-ia-token": TOKENS["ti"], "content-type": "application/json"},
    )
    assert r.status_code == 401 and r.json()["erro"]["codigo"] == "assinatura_invalida"
    assert ambiente.escalar("SELECT count(*) FROM ia.passo") == 0


def test_origem_teste_fora_de_chats_teste_403_sem_gravar(ambiente):
    abrir_ativo(ambiente)
    r = ambiente.evento_chatguru(mensagem_nativa(), origem="chatguru-ia-teste")
    assert r.status_code == 403 and r.json()["erro"]["codigo"] == "origem_teste_fora_da_lista"
    assert ambiente.escalar("SELECT count(*) FROM ia.passo") == 0 and ambiente.ctx.metricas.valor("evento_teste_fora_da_lista") == 1
    # sem atendimento nenhum, chat fora da lista: o 403 vem ANTES do descarte
    r = ambiente.evento_chatguru(mensagem_nativa(chat_id=OUTRO_CHAT), origem="chatguru-ia-teste")
    assert r.status_code == 403


def test_origem_teste_com_atendimento_real_403(ambiente):
    ambiente.configurar("chats_teste", [CHAT_TESTE])
    abrir_ativo(ambiente, CHAT_TESTE, modo="real")
    r = ambiente.evento_chatguru(mensagem_nativa(chat_id=CHAT_TESTE), origem="chatguru-ia-teste")
    assert r.status_code == 403 and r.json()["erro"]["codigo"] == "origem_teste_fora_da_lista"
    assert ambiente.escalar("SELECT count(*) FROM ia.passo") == 0


def test_origem_teste_em_chat_de_teste_com_atendimento_teste_grava_e_producao_nao_tem_a_regra(ambiente):
    ambiente.configurar("chats_teste", [CHAT_TESTE])
    abrir_ativo(ambiente, CHAT_TESTE, modo="teste")
    assert ambiente.evento_chatguru(mensagem_nativa(chat_id=CHAT_TESTE), origem="chatguru-ia-teste").json()["resultado"] == "gravado"
    abrir_ativo(ambiente, CHAT, modo="real")  # a credencial de produção vale em qualquer chat
    assert ambiente.evento_chatguru(mensagem_nativa(chat_id=CHAT)).json()["resultado"] == "gravado"


def test_mesmo_conteudo_por_chatguru_e_por_mensagem_mesma_chave_e_fingerprint(ambiente):
    abrir_ativo(ambiente)
    assert ambiente.evento_chatguru(mensagem_nativa()).json()["resultado"] == "gravado"
    normalizado = {"chat_id": CHAT, "phone_id": PHONE, "tipo": "texto", "texto": "oi, quero saber da proposta", "origem_evento": "replay",
                   "datetime_post": "2026-11-17T08:59:30-03:00"}  # fmt: skip
    r = ambiente.post("/eventos/mensagem", normalizado, token="ti")
    assert r.json()["resultado"] == "repetido", "a mesma mensagem pelo outro caminho é a mesma mensagem"
    assert ambiente.escalar("SELECT count(*) FROM ia.passo WHERE tipo = 'mensagem_recebida'") == 1
    ident = identidade(
        _evento_do_vetor(datetime_post=datetime.fromisoformat("2026-11-17T08:59:30-03:00")),
        ChavesDeMensagem(H16.encode(), FINGERPRINT.encode()),
    )
    assert ambiente.consultar("SELECT msg_chave, msg_fingerprint FROM ia.passo") == [(ident.msg_chave, ident.msg_fingerprint)]


def test_422_corpo_invalido_sem_gravar(ambiente):
    abrir_ativo(ambiente)
    for corpo in (
        mensagem_nativa(chat_id="nao-e-hex"),
        mensagem_nativa(datetime_post="2026-11-17T08:59:30"),
        {"chat_id": CHAT},
        mensagem_nativa(texto_mensagem="x" * 4001),
    ):
        r = ambiente.evento_chatguru(corpo)
        assert r.status_code == 422, corpo
    assert ambiente.escalar("SELECT count(*) FROM ia.passo") == 0 and ambiente.fila.turnos == []


# --- casamento webhook × RPA ----------------------------------------------------------------------------------------------------------------


def _rpa(txt: str, rpa_id: str, hora: str | None = "2026-11-17T08:59:31-03:00", **mudar) -> dict:
    corpo = {"chat_id": CHAT, "phone_id": PHONE, "tipo": "texto", "texto": txt, "origem_evento": "reconciliacao", "rpa_id": rpa_id}
    if hora is not None:
        corpo["datetime_post"] = hora
    return {**corpo, **mudar}


def test_webhook_e_rpa_com_1s_de_diferenca_um_turno_e_anexa_o_id(ambiente):
    atd = abrir_ativo(ambiente)
    assert ambiente.evento_chatguru(mensagem_nativa("quero a proposta")).json()["resultado"] == "gravado"
    r = ambiente.post("/eventos/mensagem", _rpa("Quero  a   PROPOSTA", "rpa_abcdefgh01"), token="ti")
    assert r.status_code == 200 and r.json() == {
        "recebido": True,
        "resultado": "anexado",
        "atendimento_id": str(atd),
        "ordem": 1,
        "turno_enfileirado": False,
    }
    assert ambiente.consultar("SELECT count(*), max(msg_chave_rpa) FROM ia.passo WHERE tipo = 'mensagem_recebida'") == [
        (1, "rpa_abcdefgh01")
    ]
    assert len(ambiente.fila.turnos) == 1, "um só turno para a mesma mensagem vista pelas duas fontes"
    assert ambiente.escalar("SELECT count(*) FROM ia.conversa_cifrada") == 1
    r = ambiente.post(
        "/eventos/mensagem", _rpa("Quero  a   PROPOSTA", "rpa_abcdefgh01"), token="ti"
    )  # o reconciliador repete: busca exata pelo _id
    assert r.json()["resultado"] == "repetido" and ambiente.escalar("SELECT count(*) FROM ia.passo") == 1


def test_rpa_antes_do_webhook_anexa_sem_reinserir(ambiente):
    abrir_ativo(ambiente)
    r = ambiente.post("/eventos/mensagem", _rpa("quero a proposta", "rpa_abcdefgh02"), token="ti")
    assert r.json()["resultado"] == "gravado" and ambiente.escalar("SELECT msg_chave FROM ia.passo") == "rpa:rpa_abcdefgh02"
    r = ambiente.evento_chatguru(mensagem_nativa("quero a proposta", datetime_post="2026-11-17T08:59:30-03:00"))
    assert r.json()["resultado"] == "anexado" and r.json()["turno_enfileirado"] is False
    assert ambiente.escalar("SELECT count(*) FROM ia.passo") == 1 and len(ambiente.fila.turnos) == 1


def test_pareamento_um_para_um_com_mensagens_identicas(ambiente):
    abrir_ativo(ambiente)
    for hora in ("2026-11-17T08:59:30-03:00", "2026-11-17T08:59:36-03:00"):  # duas vezes «sim» em 6 s (passos distintos do webhook)
        assert ambiente.evento_chatguru(mensagem_nativa("sim", datetime_post=hora)).json()["resultado"] == "gravado"
    a = ambiente.post("/eventos/mensagem", _rpa("sim", "rpa_pareado01", hora="2026-11-17T08:59:31-03:00"), token="ti").json()
    b = ambiente.post("/eventos/mensagem", _rpa("sim", "rpa_pareado02", hora="2026-11-17T08:59:37-03:00"), token="ti").json()
    assert (a["resultado"], a["ordem"], b["resultado"], b["ordem"]) == ("anexado", 1, "anexado", 2), (
        "cada RPA casa com UM webhook, o mais próximo"
    )
    c = ambiente.post("/eventos/mensagem", _rpa("sim", "rpa_pareado03", hora="2026-11-17T08:59:32-03:00"), token="ti").json()
    assert c["resultado"] == "gravado", "os dois webhooks já têm contraparte: a terceira é mensagem nova"
    assert ambiente.consultar("SELECT ordem, msg_chave_rpa FROM ia.passo ORDER BY ordem") == [
        (1, "rpa_pareado01"),
        (2, "rpa_pareado02"),
        (3, None),
    ]


def test_mensagens_diferentes_ou_fora_da_janela_de_10s_nao_casam(ambiente):
    abrir_ativo(ambiente)
    ambiente.evento_chatguru(mensagem_nativa("quero a proposta"))
    assert ambiente.post("/eventos/mensagem", _rpa("outro texto", "rpa_texto0001"), token="ti").json()["resultado"] == "gravado"
    assert (
        ambiente.post("/eventos/mensagem", _rpa("quero a proposta", "rpa_tempo0001", hora="2026-11-17T08:59:41-03:00"), token="ti").json()[
            "resultado"
        ]
        == "gravado"
    )
    assert (
        ambiente.post("/eventos/mensagem", _rpa("quero a proposta", "rpa_tempo0002", hora="2026-11-17T08:59:40-03:00"), token="ti").json()[
            "resultado"
        ]
        == "anexado"
    )


def test_midia_casa_por_tipo_e_tempo_sem_texto(ambiente):
    abrir_ativo(ambiente)
    ambiente.evento_chatguru(mensagem_nativa(tipo_mensagem="image", texto_mensagem=None, url_arquivo="https://m.exemplo.test/a.jpg?t=1"))
    r = ambiente.post("/eventos/mensagem", _rpa("", "rpa_imagem001", tipo="imagem", texto=None), token="ti")
    assert r.json()["resultado"] == "anexado"
    r = ambiente.post("/eventos/mensagem", _rpa("", "rpa_audio0001", tipo="audio", texto=None), token="ti")
    assert r.json()["resultado"] == "gravado", "tipo diferente não casa"


def test_hora_ausente_usa_janela_de_30s(ambiente):
    atd = abrir_ativo(ambiente)
    ambiente.evento_chatguru(mensagem_nativa("quero a proposta"))
    com_hora = _rpa("quero a proposta", "rpa_semhora001", hora=None)
    assert ambiente.post("/eventos/mensagem", com_hora, token="ti").json()["resultado"] == "anexado"
    ambiente.evento_chatguru(mensagem_nativa("segunda mensagem", datetime_post="2026-11-17T09:10:00-03:00"))
    with ambiente.super() as conn:  # o webhook foi visto há 31 s (relógio do banco)
        conn.execute("UPDATE ia.passo SET ocorrido_em = now() - interval '31 seconds' WHERE ordem = 2 AND atendimento_id = %s", (atd,))
    assert (
        ambiente.post("/eventos/mensagem", _rpa("segunda mensagem", "rpa_semhora002", hora=None), token="ti").json()["resultado"]
        == "gravado"
    )
    ambiente.evento_chatguru(mensagem_nativa("terceira", datetime_post="2026-11-17T09:20:00-03:00"))
    with ambiente.super() as conn:
        conn.execute("UPDATE ia.passo SET ocorrido_em = now() - interval '29 seconds' WHERE ordem = 4 AND atendimento_id = %s", (atd,))
    assert ambiente.post("/eventos/mensagem", _rpa("terceira", "rpa_semhora003", hora=None), token="ti").json()["resultado"] == "anexado"


def test_casamento_nao_atravessa_atendimentos(ambiente):
    abrir_ativo(ambiente, CHAT)
    abrir_ativo(ambiente, OUTRO_CHAT)
    ambiente.evento_chatguru(mensagem_nativa("quero a proposta"))
    r = ambiente.post("/eventos/mensagem", _rpa("quero a proposta", "rpa_outrochat1", chat_id=OUTRO_CHAT), token="ti")
    assert r.json()["resultado"] == "gravado" and ambiente.escalar("SELECT count(*) FROM ia.passo") == 2


def test_nenhum_log_contem_o_corpo_do_evento(ambiente, caplog):
    abrir_ativo(ambiente)
    marcador = "zebra-quantica-parcela"
    corpo = mensagem_nativa(
        f"{marcador} meu contato 11 91234-5678", link_chat="https://chat.exemplo.test/c/segredo-do-link", url_arquivo=None
    )
    with caplog.at_level("DEBUG"):
        assert ambiente.evento_chatguru(corpo).json()["resultado"] == "gravado"
        ambiente.evento_chatguru({**corpo, "cpf": CPF_SINTETICO})  # 422
        ambiente.evento_chatguru(
            mensagem_nativa(
                f"{marcador}-2", tipo_mensagem="image", texto_mensagem=None, url_arquivo="https://m.exemplo.test/x.jpg?token=segredo-url"
            )
        )
        ambiente.post("/eventos/mensagem", _rpa(f"{marcador} 3", "rpa_logsemcorpo"), token="ti")
    tudo = caplog.text
    for proibido in (
        marcador,
        "segredo-do-link",
        "segredo-url",
        "91234-5678",
        CPF_SINTETICO,
        TOKENS["ti"],
        CHAVE_GATEWAY,
        "x-gl-assinatura",
    ):
        assert proibido not in tudo, proibido
    assert "rota=/eventos/chatguru" in tudo and "status=200" in tudo and "status=422" in tudo, "o log tem rota, status e duração"
