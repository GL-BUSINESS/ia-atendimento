"""Tipos pequenos compartilhados: tamanho do jsonb, código/referência sem documento e rótulo de perfil.

«Só códigos» não é só um regex de alfabeto: `12345678909` e `5511912345678` casam `^[a-z0-9_]{1,40}$`. Aqui o código/referência/rótulo
também recusa CPF/celular (11 dígitos), CNPJ (14) e telefone com 55 (12–13), mascarados ou não. UUID e id numérico de 6 a 10 dígitos passam.
O erro não repete o valor.
"""

from __future__ import annotations

import json
import re
from typing import Annotated, Final

from pydantic import AfterValidator, Field, StrictBool, StrictInt, StringConstraints

LIMITE_JSON_OCTETOS: Final = 2048  # CHECK do DDL: `octet_length(perfil::text)` e `octet_length(estado_conversa::text)`
_UUID: Final = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_SEPARADOR_ENTRE_DIGITOS: Final = re.compile(r"(?<=\d)[.\-](?=\d)")
# CPF e celular nacional = 11 dígitos; CNPJ = 14; telefone com 55 na frente = 12 ou 13. Id de 6 a 10 dígitos (oferta_id bigint) passa.
_DOCUMENTO: Final = re.compile(r"(?<!\d)(\d{11}|\d{14}|55\d{10,11})(?!\d)")


def octetos_como_jsonb(valor: object) -> int:
    """Tamanho em bytes do `valor::text` do jsonb (`", "` e `": "` como separadores): o que o CHECK `octet_length(...) <= 2048` mede."""
    return len(json.dumps(valor, ensure_ascii=False, separators=(", ", ": ")).encode("utf-8"))


def _sem_documento(valor: str) -> str:
    """UUID inteiro passa (id gerado pelo sistema: 1 em 5 teria uma corrida de dígitos); o resto é conferido sem os `.`/`-` entre dígitos,
    para pegar `123.456.789-09` e `11-91234-5678`."""
    if _UUID.fullmatch(valor):
        return valor
    if _DOCUMENTO.search(_SEPARADOR_ENTRE_DIGITOS.sub("", valor)):
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
