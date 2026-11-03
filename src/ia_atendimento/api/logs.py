"""Configuração de log da API (R2-03).

O uvicorn só configura os loggers `uvicorn.*`: sem isto a linha de requisição (`req trace=… rota=… status=… codigo=…`) e os alertas do TI
(`alerta ti: …`) nunca saem em produção, e o access log do uvicorn (que grava caminho e query) tem de ficar desligado.

Formato fixo e sem valores de cliente: as mensagens da API levam só `trace_id`, molde da rota, status, códigos e contagens (nunca corpo,
texto, URL, token nem assinatura). Idempotente: chamar duas vezes não duplica o handler."""

from __future__ import annotations

import logging
import sys
from typing import Final

from ia_atendimento.scrubber import instalar_excepthook

NOME_DO_LOGGER: Final = "ia_atendimento"
FORMATO: Final = "%(asctime)s %(levelname)s %(name)s %(message)s"
_MARCA: Final = "_ia_atendimento_api"


def configurar_logging(nivel: int = logging.INFO) -> logging.Logger:
    """INFO em `ia_atendimento` (stderr, formato fixo), access log do uvicorn desligado e traceback sem PII (`instalar_excepthook`)."""
    logger = logging.getLogger(NOME_DO_LOGGER)
    logger.setLevel(nivel)
    logger.propagate = False  # o handler abaixo é o único destino (nada de duplicar em um root configurado por outro)
    if not any(getattr(h, _MARCA, False) for h in logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(FORMATO))
        setattr(handler, _MARCA, True)
        logger.addHandler(handler)
    logging.getLogger("uvicorn.access").disabled = True
    instalar_excepthook()
    return logger
