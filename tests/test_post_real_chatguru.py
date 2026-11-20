"""G-0119 (revisão 0911) e DEC-PIA-007 (20/11): o Post por mensagem do ChatGuru, na FORMA medida em produção, entra sem 422.

Forma medida (estudo do CLT, `levantamento/03-entrada-chatguru-canal.md` §2.4, e `VERIFICACAO-DECISOES-PIA-2011.md` N4): o corpo tem
23 chaves, nenhuma é id de mensagem (`bsuid` é id de usuário do WhatsApp), e `datetime_post` vem como `AAAA-MM-DDTHH:MM:SS-03:00` em 100 %
dos Posts. `chat_id` e `phone_id` são 24 hex em 100 %. O estudo nomeia 22 das 23 chaves; a 23ª não foi registrada por nome e a projeção do
gateway a descarta de qualquer jeito. Os VALORES daqui são sintéticos: só nomes de chave e tipos vêm da medida.

O gateway projeta pela allowlist A10 (contrato 01 §4) e só passa valor escalar; o que sobra chega a `/eventos/chatguru`. Sem id de mensagem,
a deduplicação é por HMAC de chat + horário + tipo + texto (`cg:{chat}:{h16}`, `evento_mensagem.py`).
"""

from __future__ import annotations

import math
from typing import Any, Final

import pytest

from tests import apoio_api
from tests.apoio_api import CHAT, PHONE, RESPONSAVEL_IA, abrir_ativo, mensagem_nativa

ambiente = apoio_api.ambiente
pytestmark = pytest.mark.banco

# contrato 01 §4: as chaves do topo que a rota `ia-mensagem` deixa passar
CPF_SINTETICO: Final = "000.000." + "201-00"  # base 2nn, DV inválido; sem o literal na árvore (gitleaks)
A10: Final = frozenset(
    {"chat_id", "phone_id", "texto_mensagem", "tipo_mensagem", "url_arquivo", "datetime_post", "responsavel_nome", "responsavel_email",
     "executado_por", "link_chat"}
)  # fmt: skip


def post_real(texto: str = "quero saber da proposta", hora: str = "2026-11-17T08:59:30-03:00", **mudar: Any) -> dict[str, Any]:
    """As 22 chaves nomeadas no estudo, com os TIPOS medidos e valores sintéticos (nenhum dado de cliente)."""
    base: dict[str, Any] = {
        # `email` na forma real é «55…@c.us»; aqui o domínio é reservado para não cair na varredura
        "chat_id": CHAT, "phone_id": PHONE, "email": "5500000000000@exemplo.invalid", "celular": "5500000000000", "nome": "Pessoa Sintetica",
        "link_chat": f"https://chatguru.invalid/chats#{CHAT}", "chat_created": "2026-11-17T08:00:00-03:00", "datetime_post": hora,
        "tipo_mensagem": "chat", "texto_mensagem": texto, "executado_por": "", "tags": ["Pre-aprovado"],
        "campos_personalizados": {"CPF": CPF_SINTETICO}, "bot_context": {"MBURA": "INAAP-1"}, "responsavel_email": RESPONSAVEL_IA,
        "responsavel_nome": "Amado Batista", "campanha_id": "", "campanha_nome": "", "origem": "", "ctwa_ad": None, "bsuid": "bsuid-sintetico",
        "username": "",
    }  # fmt: skip
    return {**base, **mudar}


def test_a_forma_tem_as_22_chaves_nomeadas_no_estudo():
    assert len(post_real()) == 22


def projetar_como_o_gateway(corpo: dict[str, Any]) -> dict[str, Any]:
    """`app/projecao.py` do gl-gateway: só chaves A10 do topo com valor escalar finito (objeto, lista, NaN e infinito caem)."""

    def escalar(valor: Any) -> bool:
        if isinstance(valor, float):
            return math.isfinite(valor)
        return valor is None or isinstance(valor, str | int | bool)

    return {k: v for k, v in corpo.items() if k in A10 and escalar(v)}


def test_post_real_projetado_grava_sem_422(ambiente):
    atd = abrir_ativo(ambiente)
    r = ambiente.evento_chatguru(projetar_como_o_gateway(post_real()))
    assert r.status_code == 200, r.text
    assert r.json()["resultado"] == "gravado" and r.json()["atendimento_id"] == str(atd)


def test_post_real_repetido_deduplica_por_chat_hora_e_texto(ambiente):
    """DEC-PIA-007: sem id de mensagem, o mesmo Post (retry do ChatGuru) é `repetido`; outro texto ou outro segundo é mensagem nova."""
    atd = abrir_ativo(ambiente)
    corpo = projetar_como_o_gateway(post_real())
    assert ambiente.evento_chatguru(corpo).json()["resultado"] == "gravado"
    assert ambiente.evento_chatguru(corpo).json()["resultado"] == "repetido"
    assert ambiente.evento_chatguru(projetar_como_o_gateway(post_real("outro texto"))).json()["resultado"] == "gravado"
    outra_hora = projetar_como_o_gateway(post_real(hora="2026-11-17T08:59:31-03:00"))
    assert ambiente.evento_chatguru(outra_hora).json()["resultado"] == "gravado"
    assert ambiente.escalar("SELECT count(*) FROM ia.passo WHERE atendimento_id = %s", (atd,)) == 3


def test_post_real_sem_projecao_segue_recusado_pela_allowlist(ambiente):
    """Se a rota subir sem `corpo_campos` (o gateway repassaria o corpo inteiro), o orquestrador recusa e não grava nada: CPF, celular e nome
    nunca entram. É a defesa do contrato 08 §5.3; o kit da rota é que não pode subir sem a allowlist."""
    abrir_ativo(ambiente)
    r = ambiente.evento_chatguru(post_real())
    assert r.status_code == 422 and r.json()["erro"]["codigo"] == "campo_fora_da_allowlist"
    recusadas = {c["campo"] for c in r.json()["erro"]["detalhe"]["campos"]}
    assert {"celular", "nome", "email", "campos_personalizados", "bot_context"} <= recusadas
    assert CPF_SINTETICO not in r.text and ambiente.escalar("SELECT count(*) FROM ia.passo") == 0


@pytest.mark.parametrize(
    "hora",
    [
        "2026-11-17T08:59:30",
        "2026-11-17 08:59:30-03:00",
        "",
        "   ",
        "17/11/2026 08:59",
        "1900-01-01T00:00:00Z",
        "000000" + "20100",
        20100,
        1.5,
        True,
    ],
)
def test_datetime_post_invalido_vale_como_ausente_e_conta_o_alerta(ambiente, hora):
    """G-0119: hora fora da forma não derruba a mensagem (antes: 422 → 424 no gateway → o ChatGuru repetia e a mensagem se perdia)."""
    atd = abrir_ativo(ambiente)
    r = ambiente.evento_chatguru(projetar_como_o_gateway(post_real(hora=hora)))
    assert r.status_code == 200 and r.json()["resultado"] == "gravado", r.text
    assert ambiente.escalar("SELECT msg_enviada_em FROM ia.passo WHERE atendimento_id = %s", (atd,)) is None, "igual ao Post sem hora"
    assert ambiente.escalar("SELECT ultimo_cliente_em FROM ia.atendimento WHERE atendimento_id = %s", (atd,)) == ambiente.relogio.agora()
    assert ambiente.ctx.metricas.valor("datetime_post_invalido") == 1
    assert ambiente.fila.turnos == [(atd, CHAT)]


@pytest.mark.parametrize("hora", ["2026-11-17 08:59:30-03:00", "2026-11-17T08:59:30"])
def test_retry_do_post_com_hora_invalida_e_repetido_e_conta_uma_vez(ambiente, hora):
    """Revisão (M1): sem hora a chave era o recebimento (com microssegundos) e o retry do ChatGuru virava mensagem nova. A hora crua entra na
    chave: o mesmo Post é `repetido`; outro texto na mesma hora crua é mensagem nova."""
    atd = abrir_ativo(ambiente)
    corpo = projetar_como_o_gateway(post_real(hora=hora))
    assert ambiente.evento_chatguru(corpo).json()["resultado"] == "gravado"
    ambiente.relogio.avancar(seconds=7)  # o retry chega depois: o recebimento muda, a chave não
    assert ambiente.evento_chatguru(corpo).json()["resultado"] == "repetido"
    assert ambiente.evento_chatguru(projetar_como_o_gateway(post_real("outro", hora=hora))).json()["resultado"] == "gravado"
    assert ambiente.escalar("SELECT count(*) FROM ia.passo WHERE atendimento_id = %s", (atd,)) == 2
    assert ambiente.ctx.metricas.valor("datetime_post_invalido") == 2


def test_hora_invalida_sem_atendimento_nao_conta(ambiente):
    r = ambiente.evento_chatguru(projetar_como_o_gateway(post_real(hora="2026-11-17T08:59:30")))
    assert r.json()["resultado"] == "descartado" and ambiente.ctx.metricas.valor("datetime_post_invalido") == 0


def test_datetime_post_invalido_com_chave_fora_da_allowlist_segue_422_sem_contar(ambiente):
    abrir_ativo(ambiente)
    r = ambiente.evento_chatguru(mensagem_nativa(datetime_post="2026-11-17T08:59:30", cpf=CPF_SINTETICO))
    assert r.status_code == 422 and r.json()["erro"]["codigo"] == "campo_fora_da_allowlist"
    assert ambiente.ctx.metricas.valor("datetime_post_invalido") == 0


def test_hora_valida_nao_conta_alerta(ambiente):
    abrir_ativo(ambiente)
    assert ambiente.evento_chatguru(projetar_como_o_gateway(post_real())).json()["resultado"] == "gravado"
    assert ambiente.ctx.metricas.valor("datetime_post_invalido") == 0


def test_rota_normalizada_segue_estrita(ambiente):
    """`/eventos/mensagem` é do RPA e do replay (código nosso): forma errada continua 422, para o bug aparecer em vez de sumir."""
    abrir_ativo(ambiente)
    corpo = {
        "chat_id": CHAT,
        "phone_id": PHONE,
        "tipo": "texto",
        "texto": "oi",
        "origem_evento": "webhook",
        "datetime_post": "2026-11-17T08:59",
    }
    assert ambiente.post("/eventos/mensagem", corpo, token="ti").status_code == 422
