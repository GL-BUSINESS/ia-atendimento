"""G-0090 e F4-009 (revisão 0911): o extrator nunca devolve hora ERRADA ou aproximada com confiança alta (EM1).

- G-0090: «às 15 30» descartava o «30» e saía 15:00 alta. Minuto solto colado à hora agora derruba a frase (`hora_incompleta`).
- F4-009: «perto das 3 da tarde» e «lá pelas 4 da tarde» saíam alta: o achado começava DENTRO da palavra («d|as», «pel|as») e a janela do
  hedge via só «perto d». Agora o achado começa na fronteira da palavra. Junto, F4-010: «cerca das» também é aproximação.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from ia_atendimento.agenda_extrator import ConfigAgenda, extrair

QUI10 = datetime(2026, 11, 5, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))  # quinta-feira, como o corpus


def _ex(texto: str):
    return extrair(texto, QUI10, QUI10, ConfigAgenda())


def _sem_alta_errada(texto: str, certo: str) -> None:
    """Recusa, ou o horário certo sem `alta`: nunca o horário errado, nunca `alta` com minuto descartado."""
    r = _ex(texto)
    for c in r.candidatos:
        assert c.quando.strftime("%H:%M") == certo and c.confianca != "alta", (texto, c)


@pytest.mark.parametrize(
    ("texto", "certo"),
    [
        ("pode ser às 15 30", "15:30"),
        ("às 15 30", "15:30"),
        ("as 9 30 da manhã", "09:30"),
        ("às 3 30 da tarde", "15:30"),
        ("às 15 20 30", "15:20"),
    ],
)
def test_minuto_justaposto_nunca_sai_alta_nem_descartado(texto, certo):
    _sem_alta_errada(texto, certo)


@pytest.mark.parametrize("texto", ["às 15 30", "às 3 30 da tarde"])
def test_minuto_justaposto_recusa_como_hora_incompleta(texto):
    assert _ex(texto).motivo_recusa == "hora_incompleta"


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("às 15h 06/11", "06/11 15:00"),  # a data colada não é minuto
        ("às 15 dia 6", "06/11 15:00"),
        ("às 3 e meia dia 6", "06/11 15:30"),
        ("às 15:30", "05/11 15:30"),
        ("às 15h30", "05/11 15:30"),
    ],
)
def test_data_e_minuto_formatado_continuam_valendo(texto, esperado):
    r = _ex(texto)
    assert [c.quando.strftime("%d/%m %H:%M") for c in r.candidatos] == [esperado], texto


@pytest.mark.parametrize(
    ("texto", "certo"),
    [
        ("perto das 3 da tarde", "15:00"),
        ("lá pelas 4 da tarde", "16:00"),
        ("la pelas 4 da tarde", "16:00"),
        ("pelas 4 da tarde", "16:00"),
        ("cerca das 3 da tarde", "15:00"),
        ("perto das 15h", "15:00"),
    ],
)
def test_aproximacao_com_da_tarde_sai_media(texto, certo):
    r = _ex(texto)
    assert r.candidatos, texto
    assert [(c.quando.strftime("%H:%M"), c.confianca) for c in r.candidatos] == [(certo, "media")], texto


@pytest.mark.parametrize(("texto", "certo"), [("às 3 da tarde", "15:00"), ("3 da tarde", "15:00"), ("amanhã às 9 da manhã", "09:00")])
def test_sem_aproximacao_segue_alta(texto, certo):
    assert [(c.quando.strftime("%H:%M"), c.confianca) for c in _ex(texto).candidatos] == [(certo, "alta")], texto
