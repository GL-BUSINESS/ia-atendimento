"""Prontidão (`GET /readyz`): `ia.v_prontidao` mais as falhas DURAS e o teste de LISTEN/NOTIFY.

Falha dura (503): banco inacessível, nenhum worker com batimento recente, job `todo` vencido há mais de 10 min, `artefato_versao`
incompleto, migração pendente ou com checksum divergente. Campos moles (lease vencido, `repassando` parado, `modo`, `ia_ativa`,
`listen_notify`) aparecem na resposta, mas não derrubam: o worker tem polling de reserva, então um NOTIFY perdido só aumenta a latência.

LISTEN/NOTIFY exige conexão DIRETA ao Postgres: pooler em modo transação (pgbouncer) engole o NOTIFY. A prova é um round-trip real
(escuta num canal próprio, outro login notifica com um token e a escuta confere o token); canal próprio para não acordar worker à toa.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path

import psycopg
from psycopg import sql

from ia_atendimento import migracoes
from ia_atendimento.relogio import Relogio

HEARTBEAT_MAX_S = 30.0  # = stalled_worker_timeout do Procrastinate: depois disso o worker é considerado morto
TODO_MAX_S = 600.0  # K §3.3.5: job `todo` vencido há mais de 10 min = fila parada
TIPOS_DE_ARTEFATO = ("roteiro", "regras", "catalogo", "motor")
CANAL_PROBE = "ia_readyz"
TIMEOUT_NOTIFY_S = 2.0

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Prontidao:
    abertos: int = 0
    reservados: int = 0
    repassando: int = 0
    pausados: int = 0
    agendados: int = 0
    mais_velho_em: datetime | None = None
    proxima_retomada_em: datetime | None = None
    lease_vencidos: int = 0
    repassando_ha_10min: tuple[str, ...] = ()
    modo: str | None = None
    ia_ativa: bool | None = None
    lido_em: datetime | None = None
    workers_vivos: int = 0
    todo_mais_velho_s: float | None = None
    artefatos_faltando: tuple[str, ...] = ()
    listen_notify: bool | None = None  # None = não verificado nesta chamada
    falhas_duras: tuple[str, ...] = ()

    @property
    def pronto(self) -> bool:
        return not self.falhas_duras


_SQL_VIEW = """
SELECT abertos, reservados, repassando, pausados, agendados, mais_velho_em, proxima_retomada_em, lease_vencidos,
       repassando_ha_10min, modo, ia_ativa, lido_em FROM ia.v_prontidao
"""
_SQL_TODO_MAIS_VELHO = """
SELECT min(coalesce(j.scheduled_at, e.at)) FROM procrastinate.procrastinate_jobs j
LEFT JOIN procrastinate.procrastinate_events e ON e.job_id = j.id AND e.type = 'deferred'
WHERE j.status = 'todo' AND coalesce(j.scheduled_at, e.at) <= %s
"""


def ler_prontidao(
    conn: psycopg.Connection, relogio: Relogio, *, heartbeat_max_s: float = HEARTBEAT_MAX_S, todo_max_s: float = TODO_MAX_S
) -> Prontidao:
    """A view mais os sinais duros da fila e dos artefatos, pelo relógio injetado (o banco só guarda os instantes)."""
    agora = relogio.agora()
    linha = conn.execute(_SQL_VIEW).fetchone()
    vivos = conn.execute(
        "SELECT count(*) FROM procrastinate.procrastinate_workers WHERE last_heartbeat >= %s", (agora - timedelta(seconds=heartbeat_max_s),)
    ).fetchone()[0]
    mais_velho = conn.execute(_SQL_TODO_MAIS_VELHO, (agora,)).fetchone()[0]
    idade_s = (agora - mais_velho).total_seconds() if mais_velho is not None else None
    presentes = {r[0] for r in conn.execute("SELECT DISTINCT tipo FROM ia.artefato_versao")}
    faltando = tuple(sorted(set(TIPOS_DE_ARTEFATO) - presentes))
    falhas = [
        *(["workers_sem_heartbeat"] if vivos == 0 else []),
        *(["fila_parada"] if idade_s is not None and idade_s > todo_max_s else []),
        *(["artefatos_ausentes"] if faltando else []),
    ]
    return Prontidao(
        *linha[:8], tuple(linha[8] or ()), *linha[9:], workers_vivos=vivos, todo_mais_velho_s=idade_s, artefatos_faltando=faltando,
        falhas_duras=tuple(falhas),
    )  # fmt: skip


def _falha_de_migracao(conn: psycopg.Connection, diretorio: Path | str) -> str | None:
    try:
        migracoes.conferir(conn, diretorio)
    except migracoes.ChecksumDivergente:
        return "migracao_divergente"
    except migracoes.MigracoesPendentes:
        return "migracao_pendente"
    return None


def readyz(
    conn: psycopg.Connection,
    relogio: Relogio,
    *,
    conninfo_direto: str | None = None,
    diretorio_migracoes: Path | str | None = None,
    timeout_notify_s: float = TIMEOUT_NOTIFY_S,
) -> Prontidao:
    """Prontidão completa. `conninfo_direto` liga o teste de LISTEN/NOTIFY; `diretorio_migracoes` liga a conferência de checksum."""
    p = ler_prontidao(conn, relogio)
    falhas = list(p.falhas_duras)
    if diretorio_migracoes is not None and (falha := _falha_de_migracao(conn, diretorio_migracoes)):
        falhas.append(falha)
    notify = verificar_listen_notify(conninfo_direto, timeout_s=timeout_notify_s) if conninfo_direto else None
    return replace(p, listen_notify=notify, falhas_duras=tuple(falhas))


def readyz_por_dsn(dsn: str, relogio: Relogio, **opcoes: object) -> Prontidao:
    """Abre a conexão e chama `readyz`; banco inacessível vira a falha dura `banco_inacessivel` (nunca ecoa o DSN)."""
    try:
        with psycopg.connect(dsn, autocommit=True, connect_timeout=3) as conn:
            return readyz(conn, relogio, **opcoes)  # type: ignore[arg-type]
    except psycopg.OperationalError as erro:
        log.warning("readyz: banco inacessível (%s)", type(erro).__name__)
        return Prontidao(falhas_duras=("banco_inacessivel",))


def _notificar(conninfo: str, canal: str, token: str) -> None:
    with psycopg.connect(conninfo, autocommit=True, connect_timeout=3) as emissor:
        emissor.execute("SELECT pg_notify(%s, %s)", (canal, token))


def verificar_listen_notify(
    conninfo: str,
    *,
    timeout_s: float = TIMEOUT_NOTIFY_S,
    canal: str = CANAL_PROBE,
    notificar: Callable[[str, str, str], None] = _notificar,
) -> bool:
    """Round-trip de LISTEN/NOTIFY por conexão direta. True só se o NOSSO token chegar dentro de `timeout_s`."""
    token = uuid.uuid4().hex
    try:
        with psycopg.connect(conninfo, autocommit=True, connect_timeout=3) as escuta:
            escuta.execute(sql.SQL("LISTEN {}").format(sql.Identifier(canal)))
            notificar(conninfo, canal, token)
            return any(n.payload == token for n in escuta.notifies(timeout=timeout_s, stop_after=1))
    except psycopg.Error as erro:
        log.warning("listen/notify: falhou (%s)", type(erro).__name__)
        return False
