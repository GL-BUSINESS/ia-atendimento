"""DEC-PIA-005/014 (20/11): a T3 só apresenta oferta da competência vigente, gerada depois da última virada (dia 20, 00:00 de São Paulo)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ia_atendimento.calendario import FUSO
from ia_atendimento.competencia import da_competencia_vigente, oferta_apresentavel, status_para_t3, virada_vigente


def sp(ano: int, mes: int, dia: int, hora: int = 0, minuto: int = 0) -> datetime:
    return datetime(ano, mes, dia, hora, minuto, tzinfo=FUSO)


def oferta(criada: datetime, valida: datetime, estado: str = "ativa") -> dict:
    return {"estado": estado, "criada_em": criada.isoformat(), "valid_until": valida.isoformat()}


@pytest.mark.parametrize(
    ("agora", "virada"),
    [
        (sp(2026, 11, 20, 0, 0), sp(2026, 11, 20)),  # a virada é inclusiva
        (sp(2026, 11, 19, 23, 59), sp(2026, 10, 20)),
        (sp(2026, 11, 25, 10), sp(2026, 11, 20)),
        (sp(2026, 12, 5, 10), sp(2026, 11, 20)),
        (sp(2027, 1, 10, 10), sp(2026, 12, 20)),  # virada do ano
        (datetime(2026, 11, 20, 2, 59, tzinfo=UTC), sp(2026, 10, 20)),  # 19/11 23:59 em São Paulo: ainda a competência anterior
    ],
)
def test_virada_vigente(agora, virada):
    assert virada_vigente(agora) == virada.astimezone(UTC)


def test_oferta_de_antes_da_virada_nao_e_candidata():
    agora = sp(2026, 11, 20, 11)
    assert da_competencia_vigente(sp(2026, 11, 20, 0, 0), agora) is True
    assert da_competencia_vigente(sp(2026, 11, 19, 23, 59), agora) is False
    velha = oferta(sp(2026, 11, 18, 10), sp(2026, 12, 1))  # ainda dentro do valid_until: não importa
    assert oferta_apresentavel(velha, agora) is False and status_para_t3(velha, agora) == "vencida"


def test_oferta_nova_ativa_e_no_prazo_e_apresentada():
    agora = sp(2026, 11, 20, 11)
    nova = oferta(sp(2026, 11, 20, 9), sp(2026, 11, 27))
    assert oferta_apresentavel(nova, agora) is True and status_para_t3(nova, agora) == "ativa"


@pytest.mark.parametrize(
    "ruim",
    [
        oferta(sp(2026, 11, 20, 9), sp(2026, 11, 20, 10)),  # valid_until vencido
        oferta(sp(2026, 11, 20, 9), sp(2026, 11, 27), estado="consumida"),
        {"estado": "ativa", "criada_em": "2026-11-20T09:00:00", "valid_until": "2026-11-27T00:00:00-03:00"},  # sem fuso
        {"estado": "ativa", "valid_until": "2026-11-27T00:00:00-03:00"},  # sem criada_em
        {"estado": "ativa", "criada_em": 1763635200, "valid_until": "2026-11-27T00:00:00-03:00"},  # epoch
    ],
)
def test_forma_ruim_ou_fora_do_prazo_nao_apresenta(ruim):
    assert oferta_apresentavel(ruim, sp(2026, 11, 20, 11)) is False and status_para_t3(ruim, sp(2026, 11, 20, 11)) == "vencida"


def test_sem_oferta():
    assert status_para_t3(None, sp(2026, 11, 20, 11)) == "sem_oferta"


def test_instante_sem_fuso_e_recusado():
    with pytest.raises(ValueError):
        virada_vigente(datetime(2026, 11, 20, 11))
