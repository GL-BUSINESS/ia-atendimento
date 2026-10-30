"""Identidade de uma mensagem recebida: `msg_chave` e `msg_fingerprint` (contrato 08 §5.1; uma função para os dois caminhos).

- `msg_chave`: webhook e replay ⇒ `cg:{chat_id}:{h16}`; reconciliação do RPA ⇒ `rpa:{rpa_id}`.
  `h16` = 16 hex iniciais de `HMAC-SHA256(chave_h16, b"h16/v1\\n" + "\\n".join([chat_id, hora_utc, tipo, texto, url_sem_query]))`.
  HMAC porque o sha256 puro de um texto curto é reversível por dicionário e a chave de dedupe é permanente; o texto bruto só entra
  no HMAC e nunca é gravado. (O `(chat_id, datetime_post)` sozinho colide em 0,55 % no corpus, 0,26 % com tipo e tamanho; o texto resolve.)
- `msg_fingerprint`: `sha256(b"ia-evento/v1\\n" + JSON canônico {chat_id, datetime_post, phone_id, texto MASCARADO, tipo, url_sem_query})`,
  nulos omitidos. Não inclui a origem: o mesmo conteúdo visto pelo webhook e pelo RPA tem o mesmo fingerprint (serve ao casamento, §5.3).
- Normalização antes de tudo: texto em NFC e sem espaços nas pontas; hora em UTC `AAAA-MM-DDTHH:MM:SSZ`; URL sem query nem fragmento.

Vetor dourado do contrato (chave `chave-h16-de-teste-descartavel-01`) conferido em `tests/test_linha_tempo.py`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import unicodedata
from dataclasses import dataclass
from datetime import UTC
from typing import Annotated, Any, Final, Literal, Self
from urllib.parse import urlsplit

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from ia_atendimento.mascara import mascarar
from ia_atendimento.scrubber import validar

PREFIXO_H16: Final = b"h16/v1\n"
PREFIXO_FINGERPRINT: Final = b"ia-evento/v1\n"
TAMANHO_MIN_CHAVE_H16: Final = 16
LIMITE_TEXTO: Final = 4000

Hex24 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{24}$")]
RpaId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{8,64}$")]
TipoMensagem = Literal["texto", "audio", "imagem", "documento", "sticker", "localizacao", "outro"]


class EventoMensagem(BaseModel):
    """Evento já projetado pela allowlist (CPF, celular e token nunca chegam aqui). Sem eco do valor nos erros."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    chat_id: Hex24
    phone_id: Hex24
    tipo: TipoMensagem
    texto: Annotated[str, Field(max_length=LIMITE_TEXTO)] | None = None
    url_arquivo: Annotated[str, Field(max_length=2000)] | None = None
    datetime_post: AwareDatetime | None = None
    origem_evento: Literal["webhook", "reconciliacao", "replay"]
    rpa_id: RpaId | None = None

    @model_validator(mode="after")
    def _coerente(self) -> Self:
        if self.origem_evento == "reconciliacao" and self.rpa_id is None:
            raise ValueError("reconciliacao exige rpa_id")
        if self.tipo == "texto" and not (self.texto or "").strip():
            raise ValueError("mensagem de texto exige texto")
        return self

    @classmethod
    def criar(cls, **campos: Any) -> Self:
        """Como o construtor, mas o erro sai como `EntradaInvalida` (sem `input`, sem causa encadeada)."""
        return validar(cls.__name__, lambda: cls(**campos))


@dataclass(frozen=True)
class Identidade:
    msg_chave: str
    msg_fingerprint: str
    msg_tamanho: int


def _texto_normalizado(evento: EventoMensagem) -> str | None:
    if evento.texto is None:
        return None
    return unicodedata.normalize("NFC", evento.texto).strip() or None


def _hora_utc(evento: EventoMensagem) -> str | None:
    if evento.datetime_post is None:
        return None
    return evento.datetime_post.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _url_sem_query(evento: EventoMensagem) -> str | None:
    if not evento.url_arquivo:
        return None
    partes = urlsplit(evento.url_arquivo)
    return f"{partes.scheme}://{partes.netloc}{partes.path}"


def _h16(evento: EventoMensagem, chave_h16: bytes) -> str:
    campos = [evento.chat_id, _hora_utc(evento) or "", evento.tipo, _texto_normalizado(evento) or "", _url_sem_query(evento) or ""]
    corpo = PREFIXO_H16 + "\n".join(campos).encode("utf-8")
    return hmac.new(chave_h16, corpo, hashlib.sha256).hexdigest()[:16]


def _fingerprint(evento: EventoMensagem) -> str:
    texto = _texto_normalizado(evento)
    canonico = {
        "chat_id": evento.chat_id,
        "datetime_post": _hora_utc(evento),
        "phone_id": evento.phone_id,
        "texto": mascarar(texto) if texto is not None else None,
        "tipo": evento.tipo,
        "url_sem_query": _url_sem_query(evento),
    }
    corpo = json.dumps({k: v for k, v in canonico.items() if v is not None}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(PREFIXO_FINGERPRINT + corpo.encode("utf-8")).hexdigest()


def identidade(evento: EventoMensagem, chave_h16: bytes) -> Identidade:
    """`msg_chave`, `msg_fingerprint` e `msg_tamanho` (caracteres do texto normalizado; 0 para mídia)."""
    if len(chave_h16) < TAMANHO_MIN_CHAVE_H16:
        raise ValueError(f"chave_h16 deve ter ao menos {TAMANHO_MIN_CHAVE_H16} bytes")
    chave = f"rpa:{evento.rpa_id}" if evento.origem_evento == "reconciliacao" else f"cg:{evento.chat_id}:{_h16(evento, chave_h16)}"
    return Identidade(chave, _fingerprint(evento), len(_texto_normalizado(evento) or ""))
