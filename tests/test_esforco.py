"""Faixa de esforço pela comissão (sp01 T3): fronteiras de `limites_brl = [150, 400, 800]`."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ia_atendimento.esforco import FAIXA_PADRAO, faixa_por_comissao

LIMITES = [150, 400, 800]


@pytest.mark.parametrize(
    "comissao,faixa",
    [
        ("0", "baixa"),
        ("149.99", "baixa"),
        ("150", "media"),
        ("400", "media"),
        ("400.01", "alta"),
        ("800", "alta"),
        ("800.01", "muito_alta"),
        (5000, "muito_alta"),
    ],
)
def test_faixa_por_comissao_nas_fronteiras(comissao, faixa):
    assert faixa_por_comissao(comissao, LIMITES) == faixa
    assert faixa_por_comissao(Decimal(str(comissao)), [Decimal(x) for x in LIMITES]) == faixa


def test_sem_comissao_vale_a_faixa_padrao_media():
    assert faixa_por_comissao(None, LIMITES) == FAIXA_PADRAO == "media"


def test_comissao_negativa_e_limites_errados_sao_erro_de_quem_chama():
    with pytest.raises(ValueError):
        faixa_por_comissao(-1, LIMITES)
    with pytest.raises(ValueError):
        faixa_por_comissao(10, [1, 2])
