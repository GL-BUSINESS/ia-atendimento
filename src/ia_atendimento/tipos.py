"""Tipos pequenos compartilhados: tamanho do jsonb, código/referência sem documento e rótulo de perfil.

«Só códigos» não é só um regex de alfabeto: `12345678909` e `5511912345678` casam `^[a-z0-9_]{1,40}$`. Aqui o código/referência/rótulo
também recusa dígito de documento ou telefone (6+ dígitos seguidos, CPF/CNPJ mascarado). O erro não repete o valor.
"""

from __future__ import annotations

import json
import re
from typing import Annotated, Final

from pydantic import AfterValidator, Field, StrictBool, StrictInt, StringConstraints

LIMITE_JSON_OCTETOS: Final = 2048  # CHECK do DDL: `octet_length(perfil::text)` e `octet_length(estado_conversa::text)`
_DIGITOS_LONGOS: Final = re.compile(r"\d{6,}")
_DOCUMENTO_MASCARADO: Final = re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}")


def octetos_como_jsonb(valor: object) -> int:
    """Tamanho em bytes do `valor::text` do jsonb (`", "` e `": "` como separadores): o que o CHECK `octet_length(...) <= 2048` mede."""
    return len(json.dumps(valor, ensure_ascii=False, separators=(", ", ": ")).encode("utf-8"))


def _sem_documento(valor: str) -> str:
    if _DIGITOS_LONGOS.search(valor) or _DOCUMENTO_MASCARADO.search(valor):
        raise ValueError("código/referência parece documento ou telefone")
    return valor


Codigo40 = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,40}$"), AfterValidator(_sem_documento)]
Codigo60 = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,60}$"), AfterValidator(_sem_documento)]
Referencia = Annotated[
    str, StringConstraints(pattern=r"^[A-Za-z0-9_.:-]{1,64}$"), AfterValidator(_sem_documento)
]  # id opaco (oferta, opção)
Rotulo = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.-]{1,40}$"), AfterValidator(_sem_documento)]  # valor de perfil
PerfilValor = StrictBool | Annotated[StrictInt, Field(gt=-(10**9), lt=10**9)] | Rotulo | None
Perfil = Annotated[dict[Codigo40, PerfilValor], Field(max_length=64)]  # plano: sem aninhamento, sem float, sem texto livre
