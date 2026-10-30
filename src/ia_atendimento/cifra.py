"""AES-256-GCM na aplicação para `conversa_cifrada` e `cofre` (estudo I §1.6; roteiro §0.3 regra 3).

- Chave só na VPS: arquivo JSON 0600 `{"<chave_id>": "<base64 de 32 bytes>"}`; `chave_id` mensal; apagar a entrada
  no dia 31 deixa ilegível qualquer cópia antiga do texto (backup, dump, WAL).
- AAD amarra o texto à linha. Forma simples: `atendimento_id`. Forma completa do esquema (copiar a linha para outro
  atendimento, seq, remetente ou tipo não decifra): `atendimento_id|seq|remetente|tipo|chave_id`.
- Nada do texto, da chave ou do ciphertext entra em log, em `repr` ou em mensagem de erro.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import stat
import uuid
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

TAMANHO_CHAVE = 32
TAMANHO_NONCE = 12
TAMANHO_TAG = 16
LIMITE_CIFRA = 20_000  # CHECK das colunas `cifra`: 17..20000 bytes (texto + tag)
CHAVE_ID_MAX = 32767  # smallint


class ErroCifra(Exception):
    """Base dos erros de cifra. As mensagens nunca carregam texto, chave nem ciphertext."""


class ChaveInsegura(ErroCifra):
    """Arquivo de chaves ausente, com permissão aberta, malformado ou com chave que não tem 32 bytes."""


class ChaveDesconhecida(ErroCifra):
    """`chave_id` que o chaveiro não tem (por exemplo, chave mensal já descartada)."""


class FalhaAoDecifrar(ErroCifra):
    """Tag GCM inválida: AAD, nonce, ciphertext ou chave não conferem."""


class Cifrado(NamedTuple):
    chave_id: int
    nonce: bytes
    ct: bytes  # texto cifrado + tag GCM de 16 bytes (o que vai na coluna `cifra`)


def _normalizar_atendimento(atendimento_id: str | uuid.UUID) -> str:
    try:
        return str(uuid.UUID(str(atendimento_id)))
    except ValueError:
        raise ValueError("atendimento_id deve ser um UUID") from None


def montar_aad(
    atendimento_id: str | uuid.UUID, *, chave_id: int, seq: int | None = None, remetente: str | None = None, tipo: str | None = None
) -> bytes:
    """Forma simples (sem seq/remetente/tipo) = `atendimento_id`; completa = `atendimento_id|seq|remetente|tipo|chave_id`."""
    atd = _normalizar_atendimento(atendimento_id)
    extras = (seq, remetente, tipo)
    if all(e is None for e in extras):
        return atd.encode()
    if any(e is None for e in extras):
        raise ValueError("AAD completo exige seq, remetente e tipo juntos")
    return f"{atd}|{seq}|{remetente}|{tipo}|{chave_id}".encode()


def _ler_arquivo(caminho: Path) -> dict[int, bytes]:
    try:
        fd = os.open(caminho, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        raise ChaveInsegura("arquivo de chaves ausente, ilegível ou é um link simbólico") from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ChaveInsegura("arquivo de chaves não é um arquivo comum")
        if info.st_mode & 0o077:
            raise ChaveInsegura(f"arquivo de chaves com permissão aberta ({stat.S_IMODE(info.st_mode):04o}); exige 0600")
        with os.fdopen(fd, "rb", closefd=False) as f:
            bruto = f.read()
    finally:
        os.close(fd)
    try:
        dados = json.loads(bruto)
    except ValueError:
        raise ChaveInsegura("arquivo de chaves não é JSON válido") from None
    if not isinstance(dados, dict) or not dados:
        raise ChaveInsegura("arquivo de chaves deve ser um objeto JSON {chave_id: base64} não vazio")
    chaves: dict[int, bytes] = {}
    for rotulo, valor in dados.items():
        if not (isinstance(rotulo, str) and rotulo.isdigit() and 1 <= int(rotulo) <= CHAVE_ID_MAX):
            raise ChaveInsegura(f"chave_id inválido no arquivo (esperado inteiro 1..{CHAVE_ID_MAX})")
        chave_id = int(rotulo)
        try:
            chave = base64.b64decode(valor, validate=True) if isinstance(valor, str) else b""
        except (binascii.Error, ValueError):
            raise ChaveInsegura(f"chave {chave_id}: base64 inválido") from None
        if len(chave) != TAMANHO_CHAVE:
            raise ChaveInsegura(f"chave {chave_id} deve ter {TAMANHO_CHAVE} bytes")
        chaves[chave_id] = chave
    return chaves


class Chaveiro:
    """Conjunto de chaves por `chave_id` + a vigente. Imutável depois de criado."""

    def __init__(self, chaves: Mapping[int, bytes], vigente: int) -> None:
        if vigente not in chaves:
            raise ChaveInsegura(f"chave vigente {vigente} não está no chaveiro")
        if any(len(c) != TAMANHO_CHAVE for c in chaves.values()):
            raise ChaveInsegura(f"toda chave deve ter {TAMANHO_CHAVE} bytes")
        self._aes = {chave_id: AESGCM(chave) for chave_id, chave in chaves.items()}
        self._vigente = vigente

    @classmethod
    def de_arquivo(cls, caminho: str | Path, vigente: int) -> Chaveiro:
        return cls(_ler_arquivo(Path(caminho)), vigente)

    @property
    def vigente(self) -> int:
        return self._vigente

    @property
    def ids(self) -> tuple[int, ...]:
        return tuple(sorted(self._aes))

    def __repr__(self) -> str:
        return f"Chaveiro(vigente={self._vigente}, ids={list(self.ids)})"

    def cifrar(
        self, texto: str, atendimento_id: str | uuid.UUID, *, seq: int | None = None, remetente: str | None = None, tipo: str | None = None
    ) -> Cifrado:
        dados = texto.encode("utf-8")
        if not dados:
            raise ValueError("texto vazio")
        if len(dados) + TAMANHO_TAG > LIMITE_CIFRA:
            raise ValueError(f"texto maior que o limite da coluna ({LIMITE_CIFRA - TAMANHO_TAG} bytes)")
        aad = montar_aad(atendimento_id, chave_id=self._vigente, seq=seq, remetente=remetente, tipo=tipo)
        nonce = os.urandom(TAMANHO_NONCE)
        return Cifrado(self._vigente, nonce, self._aes[self._vigente].encrypt(nonce, dados, aad))

    def decifrar(
        self,
        chave_id: int,
        nonce: bytes,
        ct: bytes,
        atendimento_id: str | uuid.UUID,
        *,
        seq: int | None = None,
        remetente: str | None = None,
        tipo: str | None = None,
    ) -> str:
        aes = self._aes.get(chave_id)
        if aes is None:
            raise ChaveDesconhecida(f"chave_id {chave_id} desconhecida (descartada ou nunca existiu)")
        aad = montar_aad(atendimento_id, chave_id=chave_id, seq=seq, remetente=remetente, tipo=tipo)
        if len(nonce) != TAMANHO_NONCE or len(ct) <= TAMANHO_TAG:
            raise FalhaAoDecifrar("não foi possível decifrar (nonce ou texto cifrado malformados)")
        try:
            return aes.decrypt(bytes(nonce), bytes(ct), aad).decode("utf-8")
        except (InvalidTag, UnicodeDecodeError):
            raise FalhaAoDecifrar("não foi possível decifrar (AAD, nonce, texto cifrado ou chave não conferem)") from None


@lru_cache(maxsize=1)
def chaveiro_padrao() -> Chaveiro:
    """Chaveiro do ambiente (`CHAVE_AES_ARQUIVO` + `CHAVE_AES_ID`). Falha no boot se o arquivo estiver errado."""
    from ia_atendimento.config import get_settings

    s = get_settings()
    return Chaveiro.de_arquivo(s.chave_aes_arquivo, s.chave_aes_id)


def cifrar(texto: str, atendimento_id: str | uuid.UUID, **contexto: int | str | None) -> Cifrado:
    """`(chave_id, nonce, ct)` com o chaveiro do ambiente. `contexto` = seq, remetente, tipo (AAD completo)."""
    return chaveiro_padrao().cifrar(texto, atendimento_id, **contexto)  # type: ignore[arg-type]


def decifrar(chave_id: int, nonce: bytes, ct: bytes, atendimento_id: str | uuid.UUID, **contexto: int | str | None) -> str:
    return chaveiro_padrao().decifrar(chave_id, nonce, ct, atendimento_id, **contexto)  # type: ignore[arg-type]
