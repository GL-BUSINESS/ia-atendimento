"""Relógio injetável: nenhum módulo de negócio chama `datetime.now()`; recebe um `Relogio` e pergunta `agora()` (sempre UTC, com fuso).

`RelogioFalso` é o relógio dos testes: parte de um instante fixo e só anda quando o teste manda (`avancar`).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Relogio(Protocol):
    def agora(self) -> datetime:
        """Instante atual, `datetime` ciente de fuso, em UTC."""
        ...


class RelogioReal:
    def agora(self) -> datetime:
        return datetime.now(UTC)


class RelogioFalso:
    """Instante controlado pelo teste. `avancar` e `definir` mudam o instante; `agora()` o devolve."""

    def __init__(self, inicio: datetime) -> None:
        self._agora = _exigir_fuso(inicio)

    def agora(self) -> datetime:
        return self._agora

    def avancar(self, **delta: float) -> datetime:
        """`avancar(seconds=3)`, `avancar(hours=4)`: mesmos nomes do `timedelta`."""
        self._agora = self._agora + timedelta(**delta)
        return self._agora

    def definir(self, instante: datetime) -> None:
        self._agora = _exigir_fuso(instante)


def _exigir_fuso(instante: datetime) -> datetime:
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("o relógio só aceita datetime com fuso (use UTC)")
    return instante.astimezone(UTC)
