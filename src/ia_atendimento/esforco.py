"""Faixa de esforço pela comissão esperada (sp01 T3/T7; `config.faixas_esforco.limites_brl`).

`< L0` baixa · `L0 ≤ c ≤ L1` média · `L1 < c ≤ L2` alta · `> L2` muito_alta. Sem comissão (a fonte é só o web, A2.10) vale a faixa
padrão `media` (P-R1). Puro: sem banco, sem relógio. A comissão e a faixa são gravadas no disparo e nunca mais mudam.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Final

FAIXA_PADRAO: Final = "media"


def faixa_por_comissao(comissao: Decimal | str | int | float | None, limites_brl: Sequence[Decimal | int | float]) -> str:
    """Faixa da comissão. `limites_brl` são os três cortes crescentes da config. `None` ⇒ `media`; negativa é erro de quem chama."""
    if comissao is None:
        return FAIXA_PADRAO
    valor = Decimal(str(comissao))
    if valor < 0:
        raise ValueError("comissão negativa")
    if len(limites_brl) != 3:
        raise ValueError("limites_brl deve ter três cortes")
    l0, l1, l2 = (Decimal(str(x)) for x in limites_brl)
    if valor < l0:
        return "baixa"
    if valor <= l1:
        return "media"
    return "alta" if valor <= l2 else "muito_alta"
