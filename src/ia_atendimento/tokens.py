"""Contagem de tokens do contexto (B1.4): um estimador PLUGÁVEL, porque o tokenizer do DeepSeek ainda não foi medido (H §3.1, HIPÓTESE).

Nenhuma biblioteca de tokenização é baixada nem chamada por padrão (`tiktoken` busca o vocabulário na rede na primeira vez). O padrão é
conservador: `caracteres / 3,0 · 1,10` para o texto latino (pt-BR e JSON gastam ~2,5–3,5 caracteres por token nos tokenizers BPE de
100–130 mil
entradas), ou seja, superestima para o teto de 4 mil tokens valer de verdade; e **2 tokens por caractere não latino** (emoji, CJK,
árabe: cada um custa
pelo menos 1 token e, em UTF-8 de 3–4 bytes, quase sempre 2; contar como latino subestimava em ≥ 2,7×, B-3 da revisão). Os fatores 3,0
× 1,10 ficam até a
B8.2: medir com o tokenizer real e trocar o estimador é essa tarefa; quem tiver o codificador (`tiktoken`, `tokenizers`) usa
`EstimadorPorCodificador`.
"""

from __future__ import annotations

import math
from collections.abc import Sized
from dataclasses import dataclass
from typing import Any, Final, Protocol

CARACTERES_POR_TOKEN: Final = 3.0  # HIPÓTESE: medir em B8.2
MARGEM_PADRAO: Final = 1.10
TOKENS_POR_CARACTERE_NAO_LATINO: Final = 2.0  # HIPÓTESE (conservadora): medir em B8.2
ULTIMO_LATINO: Final = 0x024F  # fim do Latin Extended-B: português, acentos e pontuação Latin-1 contam como latino
PONTUACAO_GERAL: Final = range(0x2000, 0x2070)  # «…», «—», aspas curvas: contam como latino
SETAS_E_SIMBOLOS: Final = range(0x2190, 0x2300)  # «→», «≤», «≥» do próprio prompt: contam como latino


def _nao_latino(caractere: str) -> bool:
    codigo = ord(caractere)
    return codigo > ULTIMO_LATINO and codigo not in PONTUACAO_GERAL and codigo not in SETAS_E_SIMBOLOS


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
        if not texto:
            return 0
        nao_latinos = sum(1 for c in texto if _nao_latino(c))
        latinos = (len(texto) - nao_latinos) / self.caracteres_por_token * self.margem
        return math.ceil(round(latinos + nao_latinos * TOKENS_POR_CARACTERE_NAO_LATINO, 6))  # round: 300/3·1,1 não vira 111


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
