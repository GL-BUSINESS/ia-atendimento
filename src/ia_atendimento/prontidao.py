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
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from ia_atendimento import migracoes

# o `/readyz` e o healthcheck do worker dão o worker por morto com batimento > 30 s. Ordem das margens (cada uma menor que a seguinte):
# 30 s (aqui) < 40 s (a vigia do próprio worker o para, `worker_vivo`) < 60 s (`jobs_presos` falha o job; poda de worker)
HEARTBEAT_MAX_S = 30.0
TODO_MAX_S = 600.0  # K §3.3.5: job `todo` vencido há mais de 10 min = fila parada
TIPOS_DE_ARTEFATO = ("roteiro", "regras", "catalogo", "motor")
CANAL_PROBE = "ia_readyz"
TIMEOUT_NOTIFY_S = 2.0
STATEMENT_TIMEOUT_MS = 2000
JANELA_FALHAS_MIN = 15
FALHADOS_DURO = (
    20  # jobs falhos em 15 min acima disto = nada está sendo processado (mole abaixo; ex.: serviço não injetado, cota do modelo)
)

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
    falhados_15min: int = 0
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
SELECT extract(epoch FROM now() - min(coalesce(j.scheduled_at, e.at))) FROM procrastinate.procrastinate_jobs j
LEFT JOIN procrastinate.procrastinate_events e ON e.job_id = j.id AND e.type = 'deferred'
WHERE j.status = 'todo' AND coalesce(j.scheduled_at, e.at) <= now()
"""
_SQL_VIVOS = "SELECT count(*) FROM procrastinate.procrastinate_workers WHERE last_heartbeat >= now() - make_interval(secs => %s)"
_SQL_FALHADOS = """
SELECT count(DISTINCT j.id) FROM procrastinate.procrastinate_jobs j
JOIN procrastinate.procrastinate_events e ON e.job_id = j.id AND e.type = 'failed'
WHERE j.status = 'failed' AND e.at >= now() - make_interval(mins => %s)
"""


def ler_prontidao(conn: psycopg.Connection, *, heartbeat_max_s: float = HEARTBEAT_MAX_S, todo_max_s: float = TODO_MAX_S) -> Prontidao:
    """A view mais os sinais duros da fila e dos artefatos. Batimento, agendamento e falhas são instantes gravados pelo relógio do BANCO:
    comparam-se com o `now()` do banco (a aplicação não entra na conta, então defasagem de relógio entre hosts não derruba a prontidão)."""
    linha = conn.execute(_SQL_VIEW).fetchone()
    vivos = conn.execute(_SQL_VIVOS, (heartbeat_max_s,)).fetchone()[0]
    idade = conn.execute(_SQL_TODO_MAIS_VELHO).fetchone()[0]
    idade_s = float(idade) if idade is not None else None
    falhados = conn.execute(_SQL_FALHADOS, (JANELA_FALHAS_MIN,)).fetchone()[0]
    presentes = {r[0] for r in conn.execute("SELECT DISTINCT tipo FROM ia.artefato_versao")}
    faltando = tuple(sorted(set(TIPOS_DE_ARTEFATO) - presentes))
    falhas = [
        *(["workers_sem_heartbeat"] if vivos == 0 else []),
        *(["fila_parada"] if idade_s is not None and idade_s > todo_max_s else []),
        *(["jobs_falhando"] if falhados > FALHADOS_DURO else []),
        *(["artefatos_ausentes"] if faltando else []),
    ]
    return Prontidao(
        *linha[:8], tuple(linha[8] or ()), *linha[9:], workers_vivos=vivos, todo_mais_velho_s=idade_s, falhados_15min=falhados,
        artefatos_faltando=faltando, falhas_duras=tuple(falhas),
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
    *,
    conninfo_direto: str | None = None,
    diretorio_migracoes: Path | str | None = None,
    timeout_notify_s: float = TIMEOUT_NOTIFY_S,
) -> Prontidao:
    """Prontidão completa. `conninfo_direto` liga o teste de LISTEN/NOTIFY; `diretorio_migracoes` liga a conferência de checksum."""
    p = ler_prontidao(conn)
    falhas = list(p.falhas_duras)
    if diretorio_migracoes is not None and (falha := _falha_de_migracao(conn, diretorio_migracoes)):
        falhas.append(falha)
    notify = verificar_listen_notify(conninfo_direto, timeout_s=timeout_notify_s) if conninfo_direto else None
    return replace(p, listen_notify=notify, falhas_duras=tuple(falhas))


def readyz_por_dsn(dsn: str, **opcoes: object) -> Prontidao:
    """Abre a conexão e chama `readyz`. Banco inacessível = `banco_inacessivel`; qualquer outro erro do banco (esquema ausente, permissão,
    consulta cancelada pelo `statement_timeout`) = `erro_de_consulta`. Sempre falha dura (503), nunca exceção, e nunca ecoa o DSN."""
    try:
        with psycopg.connect(_com_timeout(dsn), autocommit=True, connect_timeout=3) as conn:
            return readyz(conn, **opcoes)  # type: ignore[arg-type]
    except psycopg.OperationalError as erro:
        log.warning("readyz: banco inacessível (%s)", type(erro).__name__)
        return Prontidao(falhas_duras=("banco_inacessivel",))
    except psycopg.Error as erro:
        log.warning("readyz: consulta falhou (%s)", type(erro).__name__)
        return Prontidao(falhas_duras=("erro_de_consulta",))


def _com_timeout(dsn: str) -> str:
    """O `/readyz` não pode pendurar se o banco travar: `statement_timeout` de 2 s somado às `options` que já existirem."""
    existentes = conninfo_to_dict(dsn).get("options", "")
    return make_conninfo(dsn, options=f"{existentes} -c statement_timeout={STATEMENT_TIMEOUT_MS}".strip())


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
