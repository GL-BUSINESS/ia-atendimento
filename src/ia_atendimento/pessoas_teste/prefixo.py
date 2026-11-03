"""Marca «[TESTE]» (B2.4, contrato 08 §6): toda mensagem que SAI para um chat de teste leva o prefixo (ninguém toma a conversa por real).

Só o `modo_efetivo = teste` envia de verdade a um chat da TI; em `real` o texto sai como está, em `duble` e `sombra` nada sai (o canal é
simulado ou rascunho), então o prefixo não se aplica. O `Canal` (B1.6/B6.8) passa o texto por `texto_de_saida` antes de entregar. O prefixo
conta no limite de tamanho da mensagem: quem monta o texto desconta `len(PREFIXO_TESTE) + 1`.
"""

from __future__ import annotations

from typing import Final

PREFIXO_TESTE: Final = "[TESTE]"


def marcar_teste(texto: str) -> str:
    """`[TESTE] texto`. Idempotente: texto que já começa com o prefixo não ganha outro."""
    return texto if e_marcada_teste(texto) else f"{PREFIXO_TESTE} {texto}"


def e_marcada_teste(texto: str) -> bool:
    return texto.startswith(PREFIXO_TESTE)


def texto_de_saida(modo_efetivo: str, texto: str) -> str:
    """O texto como o `Canal` o entrega: prefixado em `teste`, intacto nos outros modos."""
    return marcar_teste(texto) if modo_efetivo == "teste" else texto
