"""Porta de alertas do orquestrador (B1.6b). O canal real (ntfy, painel) é da B6.6; aqui só a forma e a implementação em log.

Níveis: `amarelo`, `critico` e `humano` (o lead precisa de uma pessoa agora: `repasse_travado`, vigia morta; no canal real vira
prioridade máxima por um caminho que não passe pela S2, G-0020). O alerta leva CÓDIGO, id do atendimento e um detalhe curto sem PII,
nunca texto do cliente, chave de config com valor, CPF ou telefone.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Final, Literal, Protocol

log = logging.getLogger(__name__)

Nivel = Literal["amarelo", "critico", "humano"]
_CODIGO: Final = re.compile(r"^[a-z0-9_]{1,40}$")
_DETALHE: Final = re.compile(r"^[A-Za-z0-9_ .:,=-]{0,120}$")


class Alertas(Protocol):
    def alertar(self, nivel: Nivel, codigo: str, *, atendimento_id: object = None, detalhe: str = "") -> None: ...


def conferir(codigo: str, detalhe: str) -> None:
    if not _CODIGO.fullmatch(codigo) or not _DETALHE.fullmatch(detalhe):
        raise ValueError("alerta fora da forma (código [a-z0-9_] e detalhe curto sem PII)")


class AlertasEmLog:
    """Implementação padrão: uma linha de log por alerta (o filtro de logs mascara o resto)."""

    def alertar(self, nivel: Nivel, codigo: str, *, atendimento_id: object = None, detalhe: str = "") -> None:
        conferir(codigo, detalhe)
        atd = str(atendimento_id) if isinstance(atendimento_id, uuid.UUID) else "-"
        nivel_log = logging.WARNING if nivel == "amarelo" else logging.ERROR
        log.log(nivel_log, "alerta %s %s atendimento=%s %s", nivel, codigo, atd, detalhe)
