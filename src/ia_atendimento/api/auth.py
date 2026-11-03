"""Autenticação e roteamento por origem (contrato 08 §1): duas vias, e nunca uma no lugar da outra.

1. `X-IA-Token`, comparação em tempo constante contra TODOS os tokens (sem sair no primeiro). A origem é a do token que casou, nunca um
   campo do corpo.
2. Assinatura HMAC do gateway, só em `POST /eventos/chatguru`: `x-gl-origem`, `x-gl-rota`, `x-gl-timestamp`, `x-gl-assinatura`
   (`v1=<hex>`), HMAC-SHA256 de
   `gl-gw/v1\\n origem \\n rota \\n timestamp \\n corpo` contra cada chave da lista. Verificada com o corpo CRU, antes de parsear. Se
   algum `x-gl-*` vem, a
   assinatura tem de valer: não há queda para o token. Falha ⇒ 401 de corpo idêntico, sem dizer qual item falhou.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from ia_atendimento.api.erros import ErroApi

CABECALHO_TOKEN: Final = "x-ia-token"  # noqa: S105  (nome do cabeçalho, não um segredo)
PREFIXO_ASSINATURA: Final = b"gl-gw/v1"
VERSAO_ASSINATURA: Final = "v1="
ROTA_DO_GATEWAY: Final = "ia-mensagem"
CREDENCIAIS_DO_GATEWAY: Final = frozenset({"chatguru-ia", "chatguru-ia-teste"})
CREDENCIAL_DE_TESTE: Final = "chatguru-ia-teste"
ORIGEM_DO_GATEWAY: Final = "gateway_chatguru"
TOLERANCIA_RELOGIO_S: Final = 300


@dataclass(frozen=True)
class Identidade:
    origem: str
    canal_origem: str | None = None  # credencial assinada pelo gateway (`chatguru-ia` ou `chatguru-ia-teste`); só na origem do gateway


def _resumo(valor: bytes) -> bytes:
    return hashlib.sha256(valor).digest()


def autenticar_token(headers: Mapping[str, str], tokens: Mapping[str, bytes]) -> Identidade:
    """401 `token_invalido` (corpo idêntico) se ausente ou desconhecido. Compara os resumos de todos os tokens, sem sair no primeiro
    acerto."""
    apresentado = _resumo(headers.get(CABECALHO_TOKEN, "").encode("utf-8", "replace"))
    origem: str | None = None
    for nome, token in tokens.items():
        if hmac.compare_digest(apresentado, _resumo(token)) and origem is None:
            origem = nome
    if origem is None or CABECALHO_TOKEN not in headers:
        raise ErroApi("token_invalido")
    return Identidade(origem)


def tem_cabecalho_do_gateway(headers: Mapping[str, str]) -> bool:
    return any(nome.startswith("x-gl-") for nome in headers)


def assinatura_esperada(chave: bytes, origem: str, rota: str, timestamp: str, corpo: bytes) -> str:
    mensagem = b"\n".join([PREFIXO_ASSINATURA, origem.encode(), rota.encode(), timestamp.encode()]) + b"\n" + corpo
    return VERSAO_ASSINATURA + hmac.new(chave, mensagem, hashlib.sha256).hexdigest()


def _cabecalhos_aceitaveis(origem: str, rota: str, timestamp: str, assinatura: str, agora: datetime) -> bool:
    """Forma, rota, origem e janela de tempo (a verificação do HMAC é à parte)."""
    if not (origem and rota and timestamp and assinatura):
        return False
    if rota != ROTA_DO_GATEWAY or origem not in CREDENCIAIS_DO_GATEWAY:
        return False
    if not (timestamp.isascii() and timestamp.isdigit() and len(timestamp) <= 12):
        return False
    return abs(agora.timestamp() - int(timestamp)) <= TOLERANCIA_RELOGIO_S


def verificar_assinatura(headers: Mapping[str, str], corpo: bytes, chaves: Collection[bytes], agora: datetime) -> Identidade:
    """Valida os quatro cabeçalhos, a rota, a origem, a janela de ± 300 s e o HMAC (contra cada chave). Qualquer falha ⇒
    `assinatura_invalida`."""
    origem = headers.get("x-gl-origem", "")
    rota = headers.get("x-gl-rota", "")
    timestamp = headers.get("x-gl-timestamp", "")
    assinatura = headers.get("x-gl-assinatura", "")
    aceitavel = _cabecalhos_aceitaveis(origem, rota, timestamp, assinatura, agora)
    confere = False
    for chave in chaves:  # todas, sempre: o tempo não diz qual chave (nem se alguma) casou
        esperada = assinatura_esperada(chave, origem, rota, timestamp, corpo).encode()
        confere |= hmac.compare_digest(esperada, assinatura.encode("utf-8", "replace"))
    if not (aceitavel and confere):
        raise ErroApi("assinatura_invalida")
    return Identidade(ORIGEM_DO_GATEWAY, origem)


def autorizar(identidade: Identidade, permitidas: Collection[str]) -> Identidade:
    """Autenticado, mas a rota não é desta origem ⇒ 403 `origem_nao_autorizada`."""
    if identidade.origem not in permitidas:
        raise ErroApi("origem_nao_autorizada")
    return identidade
