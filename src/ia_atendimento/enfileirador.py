"""Enfileirador da API: o que ela precisa pôr na fila, SEMPRE na transação do chamador (job e gravação entram ou saem juntos).

`Enfileirador` é o protocolo que a API conhece; `EnfileiradorProcrastinate` é a implementação de produção (defer síncrono com a conexão da
própria API, `fila.enfileirar_*_sync`). Os testes da API injetam um espião que só registra.
"""

from __future__ import annotations

import uuid
from datetime import datetime
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

    def agendar_retomada(
        self, conn: psycopg.Connection, agendamento_id: uuid.UUID, atendimento_id: uuid.UUID, chat_id: str, dispara_em: datetime
    ) -> bool:
        """Alarme da volta combinada em `dispara_em` (`schedule_at`, sem lock do chat); `False` se o agendamento já tinha um esperando."""
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

    def agendar_retomada(
        self, conn: psycopg.Connection, agendamento_id: uuid.UUID, atendimento_id: uuid.UUID, chat_id: str, dispara_em: datetime
    ) -> bool:
        return fila.agendar_retomada_sync(self._app, conn, agendamento_id, atendimento_id, chat_id, dispara_em) is not None
