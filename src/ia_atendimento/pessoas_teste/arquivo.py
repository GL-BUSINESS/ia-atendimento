"""`pessoas_teste` (fixtures da B2.4): quem pode ser cliente de um chat de teste (contrato 08 §6).

Arquivo JSON `{"pessoas": ["<uuid>", ...], "chats": {"<chat_id de 24 hex>": "<uuid>"}}`: a pessoa do chat de teste e a lista de pessoas
de teste.
Sem arquivo vale `SEM_PESSOAS_DE_TESTE` (a mais restritiva): nenhuma pessoa é de teste, então nenhum chat entra em `chats_teste`.
Sem PII: só UUIDs e ids de chat sintéticos.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Protocol
from uuid import UUID

_CHAT_HEX24: Final = re.compile(r"^[0-9a-f]{24}$")


class PessoasTesteInvalidas(RuntimeError):
    """Arquivo de fixtures ilegível ou fora do formato. Falha de subida; a mensagem não cita o conteúdo."""


class PessoasTeste(Protocol):
    def contem(self, pessoa_id: UUID) -> bool: ...

    def pessoa_do_chat(self, chat_id: str) -> UUID | None: ...


@dataclass(frozen=True)
class PessoasTesteFixas:
    pessoas: frozenset[UUID] = field(default_factory=frozenset)
    chats: dict[str, UUID] = field(default_factory=dict)

    def contem(self, pessoa_id: UUID) -> bool:
        return pessoa_id in self.pessoas

    def pessoa_do_chat(self, chat_id: str) -> UUID | None:
        pessoa = self.chats.get(chat_id)
        return pessoa if pessoa in self.pessoas else None


SEM_PESSOAS_DE_TESTE: Final = PessoasTesteFixas()


def carregar(caminho: Path | str | None) -> PessoasTesteFixas:
    if caminho is None:
        return SEM_PESSOAS_DE_TESTE
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
        pessoas = frozenset(UUID(p) for p in dados["pessoas"])
        chats = {c: UUID(p) for c, p in dados["chats"].items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise PessoasTesteInvalidas("pessoas_teste: arquivo ausente ou fora do formato {pessoas: [uuid], chats: {chat_id: uuid}}") from None
    if not all(_CHAT_HEX24.fullmatch(c) for c in chats):
        raise PessoasTesteInvalidas("pessoas_teste: chat_id deve ter 24 hex minúsculo")
    return PessoasTesteFixas(pessoas, chats)
