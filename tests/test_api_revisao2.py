"""Revisão 2 da B1.5 (`docs/REVISAO-B1.5-3010-r2.md`): datas extremas (R2-05), `HEAD /healthz` (R2-07), ordem 422 × descartado (R2-10)."""

from __future__ import annotations

import pytest

from tests import apoio_api
from tests.apoio_api import CHAT, PHONE, abrir_ativo, corpo_de_agendamento, corpo_de_entrada, mensagem_nativa

ambiente = apoio_api.ambiente
pytestmark = pytest.mark.banco
EXTREMAS = [
    "0001-01-01T00:00:00+05:00",
    "0001-01-01T00:00:00Z",
    "1900-01-01T00:00:00Z",
    "2019-12-31T23:59:59Z",
    "9999-12-31T23:59:59-05:00",
    "3000-01-01T00:00:00Z",
]


@pytest.mark.parametrize("hora", EXTREMAS)
def test_data_extrema_e_422_sem_eco_e_nunca_500_nem_gravada(ambiente, hora):
    abrir_ativo(ambiente)
    r = ambiente.evento_chatguru(mensagem_nativa(datetime_post=hora))
    assert r.status_code == 422 and r.json()["erro"]["campo"] == "datetime_post" and hora not in r.text
    corpo = {"chat_id": CHAT, "phone_id": PHONE, "tipo": "texto", "texto": "oi", "origem_evento": "webhook", "datetime_post": hora}
    assert ambiente.post("/eventos/mensagem", corpo, token="ti").status_code == 422
    ambiente.ligar()
    r = ambiente.post("/atendimentos", corpo_de_entrada(ultimo_cliente_em=hora))
    assert r.status_code == 422 and r.json()["erro"]["campo"] == "ultimo_cliente_em"
    assert ambiente.post("/agendamentos", corpo_de_agendamento(ultimo_cliente_em=hora)).status_code == 422
    assert (
        ambiente.post("/agendamentos", corpo_de_agendamento(datetime_post=hora, chave=f"agendar:{CHAT}:0000000000000000")).status_code
        == 422
    )
    assert ambiente.escalar("SELECT count(*) FROM ia.passo") == 0 and ambiente.escalar("SELECT count(*) FROM ia.agendamento") == 0


def test_a_faixa_de_anos_aceita_o_que_e_real(ambiente):
    abrir_ativo(ambiente)
    for hora in ("2020-01-01T00:00:00Z", "2026-11-17T08:59:30-03:00", "2026-11-17T11:59:30.123456Z"):
        assert ambiente.evento_chatguru(mensagem_nativa(f"oi {hora}", datetime_post=hora)).json()["resultado"] == "gravado", hora


def test_head_healthz_200_sem_corpo_e_sem_entrar_no_contrato_de_rotas(ambiente):
    r = ambiente.cliente.head("/healthz")
    assert r.status_code == 200 and r.content == b""
    assert ambiente.cliente.get("/healthz").status_code == 200
    assert ambiente.cliente.head("/saude").status_code == 405, "HEAD só na sonda de saúde"
    assert "head" not in ambiente.cliente.app.openapi()["paths"]["/healthz"]


@pytest.mark.parametrize("com_atendimento", [False, True])
def test_url_malformada_da_422_com_ou_sem_atendimento_ativo(ambiente, com_atendimento):
    if com_atendimento:
        abrir_ativo(ambiente)
    r = ambiente.evento_chatguru(
        mensagem_nativa(tipo_mensagem="image", texto_mensagem=None, url_arquivo="ftp://exemplo.test/segredo-da-url")
    )
    assert r.status_code == 422 and r.json()["erro"]["campo"] == "url_arquivo" and "segredo-da-url" not in r.text, (
        "a forma não depende do estado do chat"
    )
