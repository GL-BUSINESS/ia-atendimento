"""Contagem de tokens do contexto (B1.4): um estimador PLUGÁVEL, porque o tokenizer do DeepSeek ainda não foi medido (H §3.1, HIPÓTESE).

Nenhuma biblioteca de tokenização é baixada nem chamada por padrão (`tiktoken` busca o vocabulário na rede na primeira vez). O padrão é
conservador: `caracteres / 3,0 · 1,10` (pt-BR e JSON gastam ~2,5–3,5 caracteres por token nos tokenizers BPE de 100–130 mil entradas), ou
seja, superestima para o teto de 4 mil tokens valer de verdade. Medir com o tokenizer real e trocar o estimador é a tarefa B8.2: quem
tiver o codificador (`tiktoken`, `tokenizers`) usa `EstimadorPorCodificador`.
"""

from __future__ import annotations

import math
from collections.abc import Sized
from dataclasses import dataclass
from typing import Any, Final, Protocol

CARACTERES_POR_TOKEN: Final = 3.0  # HIPÓTESE: medir em B8.2
MARGEM_PADRAO: Final = 1.10


class EstimadorDeTokens(Protocol):
    def contar(self, texto: str) -> int:
        """Tokens estimados do texto (>= 0; texto vazio = 0)."""
        ...


@dataclass(frozen=True)
class EstimadorPorCaracteres:
    caracteres_por_token: float = CARACTERES_POR_TOKEN
    margem: float = MARGEM_PADRAO

    def __post_init__(self) -> None:
        if self.caracteres_por_token <= 0 or self.margem < 1:
            raise ValueError("caracteres_por_token deve ser positivo e a margem, >= 1 (estimar para menos furaria o teto)")

    def contar(self, texto: str) -> int:
        return math.ceil(len(texto) / self.caracteres_por_token * self.margem) if texto else 0


@dataclass(frozen=True)
class EstimadorPorCodificador:
    """Adaptador para qualquer objeto no feitio do `tiktoken.Encoding`: `encode(str)` devolve a sequência de ids."""

    codificador: Any
    margem: float = 1.0

    def contar(self, texto: str) -> int:
        if not texto:
            return 0
        ids = self.codificador.encode(texto)
        if not isinstance(ids, Sized):
            ids = list(ids)
        return math.ceil(len(ids) * self.margem)


ESTIMADOR_PADRAO: Final[EstimadorDeTokens] = EstimadorPorCaracteres()
