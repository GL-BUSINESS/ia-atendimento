"""Enfileirador da API: o que ela precisa pôr na fila, SEMPRE na transação do chamador (job e gravação entram ou saem juntos).

`Enfileirador` é o protocolo que a API conhece; `EnfileiradorProcrastinate` é a implementação de produção (defer síncrono com a conexão da
própria API, `fila.enfileirar_*_sync`). Os testes da API injetam um espião que só registra.
"""

from __future__ import annotations

import uuid
from typing import Protocol

import procrastinate
import psycopg

from ia_atendimento import fila


class Enfileirador(Protocol):
    def turno(self, conn: psycopg.Connection, atendimento_id: uuid.UUID, chat_id: str) -> None:
        """Um turno por rajada (`schedule_in` 3 s, `queueing_lock` e `lock` por chat)."""
        ...

    def iniciar(self, conn: psycopg.Connection, atendimento_id: uuid.UUID, chat_id: str) -> None: ...

    def encerrar_por_chave(self, conn: psycopg.Connection, atendimento_id: uuid.UUID, chat_id: str, atraso_s: float) -> bool:
        """Agenda o encerramento da parada leve com atraso; `False` se já havia um agendado para o atendimento."""
        ...


class EnfileiradorProcrastinate:
    def __init__(self, app: procrastinate.App) -> None:
        self._app = app

    def turno(self, conn: psycopg.Connection, atendimento_id: uuid.UUID, chat_id: str) -> None:
        fila.enfileirar_turno_sync(self._app, conn, atendimento_id, chat_id)

    def iniciar(self, conn: psycopg.Connection, atendimento_id: uuid.UUID, chat_id: str) -> None:
        fila.enfileirar_iniciar_sync(self._app, conn, atendimento_id, chat_id)

    def encerrar_por_chave(self, conn: psycopg.Connection, atendimento_id: uuid.UUID, chat_id: str, atraso_s: float) -> bool:
        return fila.enfileirar_encerrar_por_chave_sync(self._app, conn, atendimento_id, chat_id, atraso_s=atraso_s) is not None
