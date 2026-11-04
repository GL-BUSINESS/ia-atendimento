"""CPF só na memória do gateway (D18; regra 2): lido a cada chamada, entregue ao executor e esquecido no fim da chamada.

`CpfEmMemoria` não se mostra (`repr`/`str`/`format` mascarados), não vira JSON nem `pickle` e não tem `__dict__`: um log, um span, um
`asdict` ou um `json.dumps` descuidado levanta ou sai `[CPF]`, nunca os dígitos. Só `revelar()` devolve o número, e só o executor chama.
"""

from __future__ import annotations

import re
from typing import Final, NoReturn

_NAO_DIGITO: Final = re.compile(r"[.\-\s]")
_ONZE: Final = re.compile(r"^[0-9]{11}$")
_MASCARA: Final = "CpfEmMemoria([CPF])"


class CpfEmMemoria:
    __slots__ = ("_digitos",)

    def __init__(self, valor: str) -> None:
        digitos = _NAO_DIGITO.sub("", valor) if isinstance(valor, str) else ""
        if not _ONZE.fullmatch(digitos):
            raise ValueError("CPF deve ter 11 dígitos")
        object.__setattr__(self, "_digitos", digitos)

    def revelar(self) -> str:
        return self._digitos

    def __setattr__(self, nome: str, valor: object) -> NoReturn:
        raise AttributeError("CpfEmMemoria é imutável")

    def __repr__(self) -> str:
        return _MASCARA

    __str__ = __repr__

    def __format__(self, especificacao: str) -> str:
        return _MASCARA

    def __reduce__(self) -> NoReturn:
        raise TypeError("CpfEmMemoria não se serializa")

    def __copy__(self) -> NoReturn:
        raise TypeError("CpfEmMemoria não se copia")

    def __deepcopy__(self, memo: object) -> NoReturn:
        raise TypeError("CpfEmMemoria não se copia")
