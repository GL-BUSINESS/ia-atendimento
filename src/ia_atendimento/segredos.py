"""Segredos que só vivem em ARQUIVO 0600 montado `:ro` (P-R10, contrato 08 §11): chaves HMAC do gateway e segredos de saída.

- O arquivo precisa ser comum, não ser link simbólico e ter modo sem acesso para grupo/outros (0600), como o `Chaveiro` da cifra.
- Nenhuma mensagem de erro cita valor, e `repr` não mostra nada (`field(repr=False)`): o segredo não vai a log, traceback nem resposta.
- Faltou, ficou aberto, veio vazio ou curto ⇒ `SegredoInvalido` (falha de subida), dizendo só o arquivo e a regra.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

TAMANHO_MIN: Final = 16
TAMANHO_MIN_CHAVE_GATEWAY: Final = 32
MAX_CHAVES_GATEWAY: Final = 2  # uma; duas só na virada de rotação (01 §3.2)
CAMPOS_DE_SAIDA: Final = ("ia_orquestrador_bearer", "chatguru_token_ia", "c360_client_id", "c360_client_secret")


class SegredoInvalido(RuntimeError):
    """Arquivo de segredo ausente, aberto demais, ilegível ou com conteúdo fora da regra. A mensagem nunca traz o conteúdo."""


@dataclass(frozen=True)
class SegredosDeSaida:
    """Credenciais que o orquestrador APRESENTA a outros serviços (usadas a partir da B1.6/B6.8; aqui só validadas no boot)."""

    ia_orquestrador_bearer: str = field(repr=False)  # Bearer da credencial `ia-orquestrador` (para `ia-repasse`, 01 §4.2)
    chatguru_token_ia: str = field(repr=False)  # token da origem `ia` do chatguru-api (`token-ia-chatguru`)
    c360_client_id: str = field(repr=False)  # client do c360-auth (03 §1)
    c360_client_secret: str = field(repr=False)


def ler_arquivo_privado(caminho: Path | str) -> bytes:
    """Conteúdo do arquivo, só se for comum, não-link e 0600. `O_NOFOLLOW` recusa o link simbólico no próprio `open`."""
    try:
        fd = os.open(caminho, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)  # NONBLOCK: um FIFO no caminho não pode travar a subida (R2-09)
    except OSError:
        raise SegredoInvalido("arquivo de segredo ausente, ilegível ou é um link simbólico") from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise SegredoInvalido("arquivo de segredo não é um arquivo comum")
        if info.st_mode & 0o077:
            raise SegredoInvalido(f"arquivo de segredo com permissão aberta ({stat.S_IMODE(info.st_mode):04o}); exige 0600")
        with os.fdopen(fd, "rb", closefd=False) as f:
            return f.read()
    finally:
        os.close(fd)


def carregar_gateway_hmac(caminho: Path | str) -> tuple[bytes, ...]:
    """Uma chave por linha (linha em branco e `#` ignoradas), 1 ou 2, cada uma com >= 32 caracteres sem espaço, todas diferentes.

    A chave vale como **bytes ASCII** do HMAC (01 §3.2: o gateway usa `chave.encode()` da string de 64 hex)."""
    try:
        texto = ler_arquivo_privado(caminho).decode("ascii")
    except UnicodeDecodeError:
        raise SegredoInvalido("gateway-hmac: o arquivo deve ser ASCII") from None
    chaves = [linha.strip() for linha in texto.splitlines() if linha.strip() and not linha.lstrip().startswith("#")]
    if not 1 <= len(chaves) <= MAX_CHAVES_GATEWAY:
        raise SegredoInvalido(f"gateway-hmac: o arquivo deve ter 1 ou {MAX_CHAVES_GATEWAY} chaves (uma por linha)")
    if any(len(c) < TAMANHO_MIN_CHAVE_GATEWAY or not c.isprintable() or " " in c for c in chaves):
        raise SegredoInvalido(
            f"gateway-hmac: cada chave precisa de ao menos {TAMANHO_MIN_CHAVE_GATEWAY} caracteres imprimíveis, sem espaço"
        )
    if len(set(chaves)) != len(chaves):
        raise SegredoInvalido("gateway-hmac: as duas chaves são iguais")
    return tuple(c.encode("ascii") for c in chaves)


def carregar_segredos_de_saida(caminho: Path | str) -> SegredosDeSaida:
    """JSON `{ia_orquestrador_bearer, chatguru_token_ia, c360_client_id, c360_client_secret}`: todos presentes e com >= 16 caracteres."""
    try:
        dados = json.loads(ler_arquivo_privado(caminho))
    except (ValueError, RecursionError):  # JSON de 100 mil `[` estoura a pilha do parser
        raise SegredoInvalido("segredos de saída: o arquivo não é JSON válido") from None
    if not isinstance(dados, dict) or set(dados) != set(CAMPOS_DE_SAIDA):
        raise SegredoInvalido(f"segredos de saída: o JSON deve ter exatamente os campos {', '.join(CAMPOS_DE_SAIDA)}")
    if not all(isinstance(v, str) and len(v) >= TAMANHO_MIN and v == v.strip() for v in dados.values()):
        raise SegredoInvalido(f"segredos de saída: cada valor é texto com ao menos {TAMANHO_MIN} caracteres, sem espaço nas pontas")
    return SegredosDeSaida(**dados)
