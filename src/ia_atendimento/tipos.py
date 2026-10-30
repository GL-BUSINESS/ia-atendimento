"""Tipos pequenos compartilhados: tamanho do jsonb, código/referência sem documento e rótulo de perfil.

«Só códigos» não é só um regex de alfabeto: `12345678909` e `5511912345678` casam `^[a-z0-9_]{1,40}$`. Aqui o código/referência/rótulo
também recusa qualquer sequência de 10+ dígitos depois de tirar os separadores (CPF, CNPJ, telefone, mascarados ou não). Só o campo de ID
(`Referencia`) aceita UUID parseado (v4/v7) e id numérico de até 9 dígitos. O erro não repete o valor.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Annotated, Final

from pydantic import AfterValidator, AwareDatetime, BeforeValidator, Field, StrictBool, StrictInt, StringConstraints

LIMITE_JSON_OCTETOS: Final = 2048  # CHECK do DDL: `octet_length(perfil::text)` e `octet_length(estado_conversa::text)`
_SEPARADORES: Final = re.compile(r"[\s.\-/_:]")
_DIGITOS_DE_DOCUMENTO: Final = re.compile(r"\d{10,}")  # CPF/celular 11, CNPJ 14, telefone com DDD 10–13: nenhum cabe em código ou rótulo
_ID_NUMERICO: Final = re.compile(r"\d{1,9}")  # `oferta_id` bigint do 360: até 9 dígitos (o 10º já é telefone fixo com DDD)
_VERSOES_DE_UUID: Final = (4, 7)  # os que o sistema gera: uuid4 (Python) e uuidv7 (`DEFAULT uuidv7()` do banco)


_RFC3339: Final = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d{1,9})?(Z|z|[+-]\d{2}:\d{2})$")


def _so_rfc3339(valor: object) -> object:
    """O Pydantic em modo *lax* lê inteiro, decimal e texto numérico como epoch: um número de 11 dígitos (CPF) viraria data gravada.
    Instante vindo de corpo é TEXTO RFC 3339 com fuso (`2026-11-24T10:15:30-03:00`, `...Z`); um `datetime` pronto (código) também passa."""
    if isinstance(valor, datetime) or (isinstance(valor, str) and _RFC3339.fullmatch(valor)):
        return valor
    raise ValueError("instante deve ser texto RFC 3339 com fuso, ex.: 2026-11-24T10:15:30-03:00")


DataHora = Annotated[AwareDatetime, BeforeValidator(_so_rfc3339)]  # instante com fuso, só como texto RFC 3339 (nunca epoch)


def octetos_como_jsonb(valor: object) -> int:
    """Tamanho em bytes do `valor::text` do jsonb (`", "` e `": "` como separadores): o que o CHECK `octet_length(...) <= 2048` mede."""
    return len(json.dumps(valor, ensure_ascii=False, separators=(", ", ": ")).encode("utf-8"))


def contem_documento(valor: str) -> bool:
    """`True` se, tirados os separadores, há uma sequência de 10+ dígitos (CPF, CNPJ, telefone), mascarada ou não."""
    return _DIGITOS_DE_DOCUMENTO.search(_SEPARADORES.sub("", valor)) is not None


def _sem_documento(valor: str) -> str:
    """Tira espaço, ponto, hífen, barra, sublinhado e dois-pontos e recusa qualquer sequência de 10 ou mais dígitos: `123.456.789-09`,
    `12345 678901`, `123_456_789_01` e `1234.5678.90.12` viram a mesma sequência de dígitos. Sem exceção para UUID."""
    if contem_documento(valor):
        raise ValueError("código/referência parece documento ou telefone")
    return valor


def _uuid_de_sistema(valor: str) -> bool:
    """UUID PARSEADO, na forma canônica (minúsculo, hifenizado), variante RFC 4122 e versão 4 ou 7. Um «uuid» forjado
    (`12345678-9012-3456-7890-123456789012`: variante inválida) não passa; um uuid4/uuid7 com 10+ dígitos decimais no último grupo, sim."""
    try:
        u = uuid.UUID(valor)
    except ValueError:
        return False
    return str(u) == valor and u.variant == uuid.RFC_4122 and u.version in _VERSOES_DE_UUID


def _id_de_sistema(valor: str) -> str:
    """Só para campo de ID (`oferta_id`, `agendamento_ref`, `opcoes_t5`): UUID parseado ou id numérico de até 9 dígitos passam; o resto
    segue `_sem_documento`. Rótulo de perfil e código NÃO têm essa porta. Residual: um UUID v4/v7 bem formado que carregue um documento
    no último grupo é indistinguível de um id aleatório; a defesa é o campo ser um id, preenchido por código, nunca por texto do cliente."""
    if _ID_NUMERICO.fullmatch(valor) or _uuid_de_sistema(valor):
        return valor
    return _sem_documento(valor)


Codigo40 = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,40}$"), AfterValidator(_sem_documento)]
Codigo60 = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,60}$"), AfterValidator(_sem_documento)]
Referencia = Annotated[
    str, StringConstraints(pattern=r"^[A-Za-z0-9_.:-]{1,64}$"), AfterValidator(_id_de_sistema)
]  # id opaco de sistema (oferta, agendamento, opção): UUID parseado ou numérico até 9 dígitos
Rotulo = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.-]{1,40}$"), AfterValidator(_sem_documento)]  # valor de perfil
PerfilValor = StrictBool | Annotated[StrictInt, Field(gt=-(10**9), lt=10**9)] | Rotulo | None
Perfil = Annotated[dict[Codigo40, PerfilValor], Field(max_length=64)]  # plano: sem aninhamento, sem float, sem texto livre
