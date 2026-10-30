"""PII fora da trilha de erro (B1.2, regra de v3): exceção, traceback e `ValidationError` nunca carregam texto de cliente.

Duas camadas, porque nenhuma basta sozinha:
1. Os modelos Pydantic que tocam texto usam `hide_input_in_errors=True` (`str(erro)` não cita o valor de entrada).
2. `ValidationError.errors()` e `.json()` guardam o `input` mesmo assim; por isso os módulos convertem o erro com `erros_sem_input`
   (só `loc`, `type` e `msg`) e relançam um erro nosso, fora do bloco `except`, para o valor não ficar preso em `__context__`.

`formatar_sem_pii` aplica a máscara de PII (`mascara.mascarar`) ao traceback inteiro; `instalar_excepthook` o liga em
`sys.excepthook` e `threading.excepthook`, para que um erro não tratado nunca imprima CPF, telefone ou e-mail.
"""

from __future__ import annotations

import sys
import threading
import traceback
from collections.abc import Callable
from types import TracebackType
from typing import Any

from pydantic import ValidationError

from ia_atendimento.mascara import mascarar


class EntradaInvalida(ValueError):
    """Entrada recusada pela validação. Só diz QUAIS campos e POR QUÊ (`detalhes`), nunca o valor recebido."""

    def __init__(self, modelo: str, detalhes: tuple[str, ...]) -> None:
        self.modelo = modelo
        self.detalhes = detalhes
        super().__init__(f"{modelo} inválido: " + "; ".join(detalhes))


def erros_sem_input(erro: ValidationError) -> tuple[str, ...]:
    """`campo: mensagem` de cada falha, sem `input`, `ctx` nem URL (o `ctx` pode repetir o valor)."""
    itens = erro.errors(include_input=False, include_context=False, include_url=False)
    return tuple(f"{'.'.join(str(parte) for parte in item['loc']) or '(corpo)'}: {item['msg']}" for item in itens)


def validar[T](nome_do_modelo: str, construir: Callable[[], T]) -> T:
    """Executa `construir()`; se o Pydantic recusar, levanta `EntradaInvalida` sem o valor e sem encadear a exceção original."""
    detalhes: tuple[str, ...] | None = None
    try:
        return construir()
    except ValidationError as erro:
        detalhes = erros_sem_input(erro)
    raise EntradaInvalida(nome_do_modelo, detalhes)  # fora do `except`: `__context__` fica vazio


def formatar_sem_pii(erro: BaseException) -> str:
    """Traceback formatado com toda PII mascarada (inclui as causas encadeadas)."""
    return mascarar("".join(traceback.format_exception(erro)))


def _hook(tipo: type[BaseException], erro: BaseException, rastro: TracebackType | None) -> None:
    erro.__traceback__ = rastro
    sys.stderr.write(formatar_sem_pii(erro))


def _hook_de_thread(args: Any) -> None:
    if args.exc_value is not None:
        _hook(args.exc_type, args.exc_value, args.exc_traceback)


def instalar_excepthook() -> None:
    """Idempotente. O Python imprime erro não tratado por estes dois ganchos; ambos passam pela máscara."""
    sys.excepthook = _hook
    threading.excepthook = _hook_de_thread
