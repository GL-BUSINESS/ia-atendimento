"""API de entrada (B1.5, sp01 T7): eventos (`/eventos/chatguru` e `/eventos/mensagem`), contra o Postgres 18 descartável.

Corpo nativo e normalizado, descarte, conflito, mídia, tipos e janelas. A assinatura do gateway e o casamento webhook × RPA ficam em `test_contrato_api.py`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from tests import apoio_api
from tests.apoio_api import (
    CHAT,
    PHONE,
    TELEFONE,
    abrir_ativo,
    mensagem_nativa,
)

ambiente = apoio_api.ambiente  # a fixture mora em `apoio_api`; este nome a registra neste módulo
pytestmark = pytest.mark.banco
CPF_SINTETICO = "000.000.012-34"


def _codigo(resposta) -> str:
    return resposta.json()["erro"]["codigo"]


# --- eventos -----------------------------------------------------------------------------------------------------------------------------


def test_evento_chatguru_sem_cpf_nem_celular_chave_fora_da_allowlist_422(ambiente):
    abrir_ativo(ambiente)
    corpo = mensagem_nativa(cpf=CPF_SINTETICO, celular=TELEFONE, message_id="abc")
    r = ambiente.evento_chatguru(corpo)
    assert r.status_code == 422 and _codigo(r) == "campo_fora_da_allowlist"
    assert CPF_SINTETICO not in r.text and TELEFONE not in r.text
    assert {c["campo"] for c in r.json()["erro"]["detalhe"]["campos"]} == {"cpf", "celular", "message_id"}
    assert ambiente.escalar("SELECT count(*) FROM ia.passo") == 0 and ambiente.escalar("SELECT count(*) FROM ia.conversa_cifrada") == 0


def test_chave_estranha_que_e_o_proprio_dado_nao_volta_na_resposta(ambiente):
    abrir_ativo(ambiente)
    r = ambiente.evento_chatguru(mensagem_nativa(**{"000.000.012-34": "x", "cpf00000001234": "y"}))
    assert r.status_code == 422 and CPF_SINTETICO not in r.text and "00000001234" not in r.text


def test_mensagem_sem_atendimento_ativo_200_descartado_e_nada_gravado(ambiente):
    r = ambiente.evento_chatguru(mensagem_nativa())
    assert r.status_code == 200 and r.json() == {"recebido": True, "resultado": "descartado", "motivo": "sem_atendimento"}
    assert ambiente.escalar("SELECT count(*) FROM ia.passo") == 0 and ambiente.fila.turnos == []
    abrir_ativo(ambiente, estado="encerrado")  # encerrado não é ativo
    assert ambiente.evento_chatguru(mensagem_nativa()).json()["motivo"] == "sem_atendimento"


def test_mensagem_grava_passo_conversa_cifrada_ultimo_cliente_em_e_enfileira_turno(ambiente):
    atd = abrir_ativo(ambiente)
    antes = ambiente.consultar("SELECT versao, ultimo_cliente_em FROM ia.atendimento WHERE atendimento_id = %s", (atd,))[0]
    texto = "zebra-quantica-parcela quero saber da proposta"
    r = ambiente.evento_chatguru(mensagem_nativa(texto))
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["resultado"] == "gravado" and corpo["atendimento_id"] == str(atd) and corpo["ordem"] == 1
    assert (corpo["fora_de_ordem"], corpo["turno_enfileirado"], corpo["delegacao_externa"]) == (False, True, False)
    passo = ambiente.consultar(
        "SELECT msg_chave, msg_tipo, msg_tamanho, origem_evento, texto FROM ia.passo WHERE atendimento_id = %s", (atd,)
    )[0]
    assert passo[0].startswith(f"cg:{CHAT}:") and passo[1:4] == ("texto", len(texto), "webhook") and texto not in passo[4]
    conversa = ambiente.consultar("SELECT remetente, cifra FROM ia.conversa_cifrada WHERE atendimento_id = %s", (atd,))
    assert [c[0] for c in conversa] == ["cliente"] and b"zebra" not in bytes(conversa[0][1])
    depois = ambiente.consultar("SELECT versao, ultimo_cliente_em FROM ia.atendimento WHERE atendimento_id = %s", (atd,))[0]
    assert depois[0] == antes[0], "o ultimo_cliente_em não toca a versao (nem disputa o CAS)"
    assert depois[1] == datetime(2026, 11, 17, 11, 59, 30, tzinfo=UTC)
    assert ambiente.fila.turnos == [(atd, CHAT)]


def test_mensagem_e_conversa_e_turno_na_mesma_transacao(ambiente):
    """Se enfileirar o turno falha, nada fica: nem o passo, nem a conversa cifrada, nem o `ultimo_cliente_em`."""
    atd = abrir_ativo(ambiente)

    class Quebra:
        def turno(self, *_):
            raise RuntimeError("fila fora")

        iniciar = encerrar_por_chave = turno

    ambiente.trocar(enfileirador=Quebra())
    assert ambiente.evento_chatguru(mensagem_nativa()).status_code == 500
    assert ambiente.escalar("SELECT count(*) FROM ia.passo") == 0 and ambiente.escalar("SELECT count(*) FROM ia.conversa_cifrada") == 0
    assert ambiente.escalar("SELECT ultimo_cliente_em FROM ia.atendimento WHERE atendimento_id = %s", (atd,)) is None


def test_mensagem_repetida_200_repetido_e_outro_fingerprint_200_conflito(ambiente):
    atd = abrir_ativo(ambiente)
    assert ambiente.evento_chatguru(mensagem_nativa()).json()["resultado"] == "gravado"
    r = ambiente.evento_chatguru(mensagem_nativa())
    assert r.status_code == 200 and r.json() == {"recebido": True, "resultado": "repetido", "atendimento_id": str(atd)}
    assert ambiente.escalar("SELECT count(*) FROM ia.passo WHERE tipo = 'mensagem_recebida'") == 1
    # mesma msg_chave (chat, hora, tipo, texto), outro phone_id ⇒ outro fingerprint
    r = ambiente.evento_chatguru(mensagem_nativa(phone_id="bbbbbbbbbbbbbbbbbbbbbbbb"))
    assert r.status_code == 200 and r.json()["resultado"] == "conflito" and r.json()["recebido"] is False
    pecas = ambiente.consultar("SELECT tipo, peca, texto FROM ia.passo WHERE tipo = 'erro'")
    assert pecas == [("erro", "receptor", "Erro na peça receptor.")]
    assert ambiente.escalar("SELECT count(*) FROM ia.passo WHERE tipo = 'mensagem_recebida'") == 1


def test_responsavel_diferente_do_amado_marca_delegacao_externa(ambiente):
    abrir_ativo(ambiente)
    r = ambiente.evento_chatguru(mensagem_nativa(responsavel_email="consultor.teste@glcapital.invalid"))
    assert r.json()["delegacao_externa"] is True and r.json()["turno_enfileirado"] is True
    r = ambiente.evento_chatguru(
        mensagem_nativa("outra", datetime_post="2026-11-17T09:01:00-03:00", responsavel_email="AMADO.teste@glcapital.invalid")
    )
    assert r.json()["delegacao_externa"] is False, "e-mail comparado sem diferenciar maiúsculas"


def test_responsavel_nome_executado_por_e_link_do_chat_sao_descartados_sem_registro(ambiente):
    abrir_ativo(ambiente)
    r = ambiente.evento_chatguru(
        mensagem_nativa(
            responsavel_nome="Fulana Teste", executado_por="alguem@glcapital.invalid", link_chat="https://chat.exemplo.test/c/abc?t=segredo"
        )
    )
    assert r.status_code == 200 and r.json()["resultado"] == "gravado"
    tudo = json.dumps(ambiente.consultar("SELECT p::text FROM ia.passo p") + ambiente.consultar("SELECT a::text FROM ia.atendimento a"))
    assert "Fulana" not in tudo and "alguem@" not in tudo and "segredo" not in tudo


def test_audio_grava_marcador_e_enfileira_sem_chamar_modelo(ambiente):
    atd = abrir_ativo(ambiente)
    corpo = mensagem_nativa(
        tipo_mensagem="ptt", texto_mensagem=None, url_arquivo="https://midia.exemplo.test/a/b.ogg?Signature=segredo-da-url"
    )
    r = ambiente.evento_chatguru(corpo)
    assert r.json()["resultado"] == "gravado" and r.json()["turno_enfileirado"] is True
    assert ambiente.escalar("SELECT msg_tipo FROM ia.passo WHERE atendimento_id = %s", (atd,)) == "audio"
    cifra = ambiente.consultar("SELECT remetente, tipo, seq, chave_id, nonce, cifra FROM ia.conversa_cifrada")[0]
    texto = ambiente.ctx.chaveiro.decifrar(cifra[3], bytes(cifra[4]), bytes(cifra[5]), atd, seq=cifra[2], remetente=cifra[0], tipo=cifra[1])
    assert texto == "[audio]"
    assert "segredo-da-url" not in json.dumps(ambiente.consultar("SELECT p::text FROM ia.passo p"))
    # a mesma mídia com OUTRA query (token novo) é a mesma mensagem: repetida
    corpo["url_arquivo"] = "https://midia.exemplo.test/a/b.ogg?Signature=outro-token"
    assert ambiente.evento_chatguru(corpo).json()["resultado"] == "repetido"


@pytest.mark.parametrize(
    "tipo,esperado",
    [
        ("chat", "texto"),
        ("audio", "audio"),
        ("ptt", "audio"),
        ("image", "imagem"),
        ("document", "documento"),
        ("sticker", "sticker"),
        ("location", "localizacao"),
        ("video", "outro"),
    ],
)
def test_tipo_nativo_mapeado(ambiente, tipo, esperado):
    atd = abrir_ativo(ambiente)
    corpo = mensagem_nativa(tipo_mensagem=tipo, texto_mensagem="oi" if tipo == "chat" else None)
    assert ambiente.evento_chatguru(corpo).json()["resultado"] == "gravado"
    assert ambiente.escalar("SELECT msg_tipo FROM ia.passo WHERE atendimento_id = %s", (atd,)) == esperado


def test_chat_sem_texto_200_descartado_texto_vazio(ambiente):
    abrir_ativo(ambiente)
    for texto in (None, "", "   "):
        r = ambiente.evento_chatguru(mensagem_nativa(texto))
        assert r.status_code == 200 and r.json()["motivo"] == "texto_vazio" and r.json()["resultado"] == "descartado"
    assert ambiente.escalar("SELECT count(*) FROM ia.passo") == 0


def test_repassando_grava_mas_nao_enfileira_turno(ambiente):
    abrir_ativo(ambiente, estado="repassando")
    r = ambiente.evento_chatguru(mensagem_nativa())
    assert r.json()["resultado"] == "gravado" and r.json()["turno_enfileirado"] is False and ambiente.fila.turnos == []


def test_fora_de_ordem_quando_a_hora_e_anterior_a_da_ultima_mensagem(ambiente):
    abrir_ativo(ambiente)
    assert ambiente.evento_chatguru(mensagem_nativa("segunda", datetime_post="2026-11-17T09:00:00-03:00")).json()["fora_de_ordem"] is False
    r = ambiente.evento_chatguru(mensagem_nativa("primeira", datetime_post="2026-11-17T08:55:00-03:00"))
    assert r.json()["fora_de_ordem"] is True
    assert ambiente.escalar("SELECT ultimo_cliente_em FROM ia.atendimento") == datetime(2026, 11, 17, 12, 0, tzinfo=UTC), "só avança"


def test_mensagem_sem_hora_usa_o_recebimento_e_hora_no_futuro_nao_adianta_a_janela(ambiente):
    abrir_ativo(ambiente)
    ambiente.evento_chatguru(mensagem_nativa("sem hora", datetime_post=None))
    ambiente.evento_chatguru(mensagem_nativa("futuro", datetime_post="2026-12-31T10:00:00-03:00"))
    assert ambiente.escalar("SELECT ultimo_cliente_em FROM ia.atendimento") == ambiente.relogio.agora()


def test_url_malformada_422_sem_ecoar_a_url(ambiente):
    abrir_ativo(ambiente)
    for ruim in ("http://[::1", "http://exemplo.test:porta/x", "ftp://exemplo.test/x?segredo-da-url=1", "sem-esquema/segredo-da-url"):
        r = ambiente.evento_chatguru(mensagem_nativa(tipo_mensagem="image", texto_mensagem=None, url_arquivo=ruim))
        assert r.status_code == 422, ruim
        assert (
            r.json()["erro"]["campo"] == "url_arquivo" and "segredo-da-url" not in r.text and "porta" not in r.text and "::1" not in r.text
        )
    assert ambiente.escalar("SELECT count(*) FROM ia.passo") == 0


def test_evento_mensagem_normalizado_so_com_token_ti(ambiente):
    abrir_ativo(ambiente)
    corpo = {
        "chat_id": CHAT,
        "phone_id": PHONE,
        "tipo": "texto",
        "texto": "oi",
        "datetime_post": "2026-11-17T09:00:00-03:00",
        "origem_evento": "webhook",
    }
    assert ambiente.post("/eventos/mensagem", corpo, token="n8n_braco").status_code == 403
    assert ambiente.post("/eventos/mensagem", corpo, token=None).status_code == 401
    r = ambiente.post("/eventos/mensagem", corpo, token="ti")
    assert r.status_code == 200 and r.json()["resultado"] == "gravado"
    assert ambiente.post("/eventos/mensagem", {**corpo, "origem_evento": "reconciliacao"}, token="ti").status_code == 422, (
        "reconciliação exige rpa_id"
    )


def test_evento_corpo_chunked_acima_de_64kb_413_sem_content_length(ambiente):
    pedacos = iter([b"x" * 40_000, b"x" * 40_000])  # sem Content-Length: o limite vale pelo que de fato chega
    r = ambiente.cliente.post("/eventos/chatguru", content=pedacos, headers={"content-type": "application/json"})
    assert r.status_code == 413 and _codigo(r) == "payload_grande"


def test_evento_corpo_acima_de_64kb_413(ambiente):
    grande = json.dumps(mensagem_nativa("x" * 70_000)).encode()
    r = ambiente.cliente.post("/eventos/chatguru", content=grande, headers=ambiente.assinar(grande))
    assert r.status_code == 413 and _codigo(r) == "payload_grande"
