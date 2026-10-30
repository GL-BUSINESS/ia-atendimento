"""AES-256-GCM na aplicação para `conversa_cifrada` e `cofre` (estudo I §1.6; roteiro §0.3 regra 3).

- Chave só na VPS: arquivo JSON 0600 `{"<chave_id>": "<base64 de 32 bytes>"}`; `chave_id` mensal; apagar a entrada
  no dia 31 deixa ilegível qualquer cópia antiga do texto (backup, dump, WAL).
- AAD = `atendimento_id|seq|remetente|tipo|chave_id` (I §1.6; plano 01): copiar a linha para outro atendimento, seq,
  remetente, tipo ou chave não decifra. No cofre: `atendimento_id|0|cofre|finalidade|chave_id`. É a ÚNICA forma: não existe
  AAD «só com o atendimento_id» (revisão 29/10: o contexto é obrigatório, esquecê-lo é `TypeError`, não cifra fraca).
  Os valores têm domínio fechado (os do CHECK do esquema), o que também impede `|` de gerar AAD ambígua.
- Nada do texto, da chave ou do ciphertext entra em log, em `repr` ou em mensagem de erro.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import stat
import uuid
from collections.abc import Callable, Mapping
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

REMETENTES = frozenset({"cliente", "ia"})  # CHECK conversa_cifrada_forma_check
TIPOS_DE_MENSAGEM = frozenset({"mensagem", "resumo"})
FINALIDADES_DO_COFRE = frozenset({"canal", "digitacao"})  # CHECK cofre_forma_check
REMETENTE_DO_COFRE = "cofre"
_TOKEN_AAD = re.compile(r"[a-z_]{1,20}")
_ROTULO_CHAVE = re.compile(r"[1-9][0-9]{0,4}")  # inteiro ASCII canônico: sem «01», «+1», dígitos Unicode nem espaço
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

    def __repr__(self) -> str:  # nonce e ciphertext não vão para log nem traceback (o contrato do módulo)
        return f"Cifrado(chave_id={self.chave_id}, nonce=<{len(self.nonce)} bytes>, ct=<{len(self.ct)} bytes>)"


def _normalizar_atendimento(atendimento_id: str | uuid.UUID) -> str:
    try:
        return str(uuid.UUID(str(atendimento_id)))
    except ValueError:
        raise ValueError("atendimento_id deve ser um UUID") from None


def montar_aad(atendimento_id: str | uuid.UUID, *, chave_id: int, seq: int, remetente: str, tipo: str) -> bytes:
    """`atendimento_id|seq|remetente|tipo|chave_id`. Sem valor opcional: AAD incompleta não existe."""
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
        raise ValueError("seq deve ser inteiro >= 0")
    if not (isinstance(remetente, str) and isinstance(tipo, str) and _TOKEN_AAD.fullmatch(remetente) and _TOKEN_AAD.fullmatch(tipo)):
        raise ValueError("remetente e tipo devem ser palavras minúsculas (sem separador)")
    return f"{_normalizar_atendimento(atendimento_id)}|{seq}|{remetente}|{tipo}|{chave_id}".encode()


def _aad_da_mensagem(atendimento_id: str | uuid.UUID, chave_id: int, seq: int, remetente: str, tipo: str) -> bytes:
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 1:
        raise ValueError("seq deve ser inteiro >= 1 (o esquema exige seq >= 1)")
    if remetente not in REMETENTES or tipo not in TIPOS_DE_MENSAGEM:
        raise ValueError(f"remetente deve ser um de {sorted(REMETENTES)} e tipo um de {sorted(TIPOS_DE_MENSAGEM)}")
    return montar_aad(atendimento_id, chave_id=chave_id, seq=seq, remetente=remetente, tipo=tipo)


def _aad_do_cofre(atendimento_id: str | uuid.UUID, chave_id: int, finalidade: str) -> bytes:
    if finalidade not in FINALIDADES_DO_COFRE:
        raise ValueError(f"finalidade deve ser uma de {sorted(FINALIDADES_DO_COFRE)}")
    return montar_aad(atendimento_id, chave_id=chave_id, seq=0, remetente=REMETENTE_DO_COFRE, tipo=finalidade)


def _sem_repeticao(pares: list[tuple[str, object]]) -> dict[str, object]:
    chaves = [k for k, _ in pares]
    if len(set(chaves)) != len(chaves):
        raise ValueError("chave_id repetida")
    return dict(pares)


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
        dados = json.loads(bruto, object_pairs_hook=_sem_repeticao)
    except ValueError:
        raise ChaveInsegura("arquivo de chaves não é JSON válido (ou repete um chave_id)") from None
    if not isinstance(dados, dict) or not dados:
        raise ChaveInsegura("arquivo de chaves deve ser um objeto JSON {chave_id: base64} não vazio")
    chaves: dict[int, bytes] = {}
    for rotulo, valor in dados.items():
        if not (_ROTULO_CHAVE.fullmatch(rotulo) and int(rotulo) <= CHAVE_ID_MAX):
            raise ChaveInsegura(f"chave_id inválido no arquivo (esperado inteiro ASCII 1..{CHAVE_ID_MAX}, sem zero à esquerda)")
        chave_id = int(rotulo)
        try:
            chave = base64.b64decode(valor, validate=True) if isinstance(valor, str) else b""
        except (binascii.Error, ValueError):
            raise ChaveInsegura(f"chave {chave_id}: base64 inválido") from None
        if len(chave) != TAMANHO_CHAVE:
            raise ChaveInsegura(f"chave {chave_id} deve ter {TAMANHO_CHAVE} bytes")
        chaves[chave_id] = chave
    _exigir_chaves_distintas(chaves)
    return chaves


def _exigir_chaves_distintas(chaves: Mapping[int, bytes]) -> None:
    """Mesma chave em dois meses faria o descarte mensal não descartar nada; chave toda zero é marcador de lugar, não chave."""
    if len(set(chaves.values())) != len(chaves):
        raise ChaveInsegura("a mesma chave aparece em dois chave_id (o descarte mensal não surtiria efeito)")
    if any(not any(chave) for chave in chaves.values()):
        raise ChaveInsegura("chave toda zero não é uma chave")


class Chaveiro:
    """Conjunto de chaves por `chave_id` + a vigente. Imutável depois de criado."""

    def __init__(self, chaves: Mapping[int, bytes], vigente: int) -> None:
        if vigente not in chaves:
            raise ChaveInsegura(f"chave vigente {vigente} não está no chaveiro")
        if any(len(c) != TAMANHO_CHAVE for c in chaves.values()):
            raise ChaveInsegura(f"toda chave deve ter {TAMANHO_CHAVE} bytes")
        _exigir_chaves_distintas(chaves)
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

    def cifrar(self, texto: str, atendimento_id: str | uuid.UUID, *, seq: int, remetente: str, tipo: str) -> Cifrado:
        """Mensagem ou resumo da conversa (`conversa_cifrada`)."""
        return self._cifrar(texto, _aad_da_mensagem(atendimento_id, self._vigente, seq, remetente, tipo))

    def decifrar(
        self, chave_id: int, nonce: bytes, ct: bytes, atendimento_id: str | uuid.UUID, *, seq: int, remetente: str, tipo: str
    ) -> str:
        return self._decifrar(chave_id, nonce, ct, lambda: _aad_da_mensagem(atendimento_id, chave_id, seq, remetente, tipo))

    def cifrar_cofre(self, texto: str, atendimento_id: str | uuid.UUID, finalidade: str) -> Cifrado:
        """Dado de curta vida do `cofre` (finalidade `canal` ou `digitacao`)."""
        return self._cifrar(texto, _aad_do_cofre(atendimento_id, self._vigente, finalidade))

    def decifrar_cofre(self, chave_id: int, nonce: bytes, ct: bytes, atendimento_id: str | uuid.UUID, finalidade: str) -> str:
        return self._decifrar(chave_id, nonce, ct, lambda: _aad_do_cofre(atendimento_id, chave_id, finalidade))

    def _cifrar(self, texto: str, aad: bytes) -> Cifrado:
        try:
            dados = texto.encode("utf-8")
        except UnicodeEncodeError:  # a mensagem do codec cita o caractere
            raise ValueError("texto não é UTF-8 válido") from None
        if not dados:
            raise ValueError("texto vazio")
        if len(dados) + TAMANHO_TAG > LIMITE_CIFRA:
            raise ValueError(f"texto maior que o limite da coluna ({LIMITE_CIFRA - TAMANHO_TAG} bytes)")
        nonce = os.urandom(TAMANHO_NONCE)  # 96 bits aleatórios por mensagem; a chave é mensal (volume << 2^32 por chave)
        return Cifrado(self._vigente, nonce, self._aes[self._vigente].encrypt(nonce, dados, aad))

    def _decifrar(self, chave_id: int, nonce: bytes, ct: bytes, aad_de: Callable[[], bytes]) -> str:
        aes = self._aes.get(chave_id)
        if aes is None:
            raise ChaveDesconhecida(f"chave_id {chave_id} desconhecida (descartada ou nunca existiu)")
        aad = aad_de()
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


def cifrar(texto: str, atendimento_id: str | uuid.UUID, *, seq: int, remetente: str, tipo: str) -> Cifrado:
    """`(chave_id, nonce, ct)` da mensagem/resumo com o chaveiro do ambiente."""
    return chaveiro_padrao().cifrar(texto, atendimento_id, seq=seq, remetente=remetente, tipo=tipo)


def decifrar(chave_id: int, nonce: bytes, ct: bytes, atendimento_id: str | uuid.UUID, *, seq: int, remetente: str, tipo: str) -> str:
    return chaveiro_padrao().decifrar(chave_id, nonce, ct, atendimento_id, seq=seq, remetente=remetente, tipo=tipo)


def cifrar_cofre(texto: str, atendimento_id: str | uuid.UUID, finalidade: str) -> Cifrado:
    return chaveiro_padrao().cifrar_cofre(texto, atendimento_id, finalidade)


def decifrar_cofre(chave_id: int, nonce: bytes, ct: bytes, atendimento_id: str | uuid.UUID, finalidade: str) -> str:
    return chaveiro_padrao().decifrar_cofre(chave_id, nonce, ct, atendimento_id, finalidade)
