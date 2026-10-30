"""Fila Procrastinate (psycopg): app, tarefas, enfileiramento com trava por chat e as tarefas periódicas.

- **Conexão:** `options=-c search_path=procrastinate,public` no conector (as funções e gatilhos do Procrastinate usam nomes sem schema);
  conexão direta ao Postgres, nunca por pooler (LISTEN/NOTIFY não atravessa pooler em modo transação; ver `prontidao.py`).
- **Rajada:** o `queueing_lock` do Procrastinate 3.10.0 é índice único parcial só para `status='todo'`, sem janela. Por isso o turno é
  agendado `schedule_in=3 s` com `queueing_lock=turno:{chat}`: mensagens dentro desses 3 s caem no mesmo job (`AlreadyEnqueued` engolido).
  `lock=chat:{chat}` impede dois jobs do mesmo chat de rodarem juntos, inclusive um turno e o seguinte.
- **App por chamada:** o `Blueprint` nasce em `criar_app`, nunca no import: `add_tasks_from` o modifica, então não se reaproveita.
  Os `Servicos` (funções injetadas, `jobs.py`) chegam à tarefa por `additional_context`, sem estado global.
- Nenhuma tarefa decide negócio: chama o handler de `jobs.py`.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, time
from typing import Any

import procrastinate
import psycopg
from procrastinate import exceptions as pexc
from psycopg import ProgrammingError
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from ia_atendimento import jobs
from ia_atendimento.calendario import BLOQUEIO_DATAPREV_EM, DATAPREV_ATE, HORA_BLOQUEIO_ENTRADA, cron_utc
from ia_atendimento.chave import ConfigCorrida
from ia_atendimento.relogio import Relogio

SEARCH_PATH = "procrastinate,public"
JANELA_RAJADA_S = 3
NAMESPACE = "ia"
POOL_MIN = 1
POOL_MAX = 8
CONCORRENCIA_PADRAO = 4  # o lock por chat serializa o que precisa; a periódica não espera atrás de um turno de modelo (revisão A3)
# só falha transitória de banco/rede/corrida repete; erro de lógica (ex.: HorarioInesperado) falha de vez e a vigia alerta
RETRY_BLOQUEIO = procrastinate.RetryStrategy(max_attempts=5, wait=30, retry_exceptions={psycopg.Error, OSError, ConfigCorrida})
# 03:30 em São Paulo: fim da madrugada, longe do horário de atendimento
HORA_PODA_LOCAL = time(3, 30)


def conninfo_da_fila(database_url: str) -> str:
    """Conninfo do libpq a partir de URL (aceita o dialeto `+psycopg`) ou de pares `chave=valor`, com `search_path` somado às `options`."""
    texto = database_url
    if "://" in texto:
        esquema, resto = texto.split("://", 1)
        texto = f"{esquema.split('+', 1)[0]}://{resto}"
    try:
        partes = conninfo_to_dict(texto)
    except ProgrammingError:  # a mensagem do libpq cita a URL inteira, com a senha
        raise ValueError("database_url inválida: use postgresql://usuario:senha@host:porta/banco ou pares chave=valor") from None
    existentes = partes.get("options", "").strip()
    opcoes = f"{existentes} -c search_path={SEARCH_PATH}".strip()
    return make_conninfo(texto, options=opcoes)


def criar_app(database_url: str, *, com_periodicas: bool = True) -> procrastinate.App:
    """App do Procrastinate com todas as tarefas (`ia:<nome>`). O pool abre em `app.open_async()`."""
    conector = procrastinate.PsycopgConnector(conninfo=conninfo_da_fila(database_url), min_size=POOL_MIN, max_size=POOL_MAX)
    app = procrastinate.App(connector=conector)
    app.add_tasks_from(_montar_tarefas(com_periodicas), namespace=NAMESPACE)
    return app


def _servicos(contexto: procrastinate.JobContext) -> jobs.Servicos:
    servicos = contexto.additional_context.get("servicos")
    if not isinstance(servicos, jobs.Servicos):
        raise jobs.ServicoNaoConfigurado("o worker foi iniciado sem additional_context={'servicos': Servicos(...)}")
    return servicos


def _montar_tarefas(com_periodicas: bool) -> procrastinate.Blueprint:
    bp = procrastinate.Blueprint()

    @bp.task(name="turno", pass_context=True)
    async def turno(contexto: procrastinate.JobContext, atendimento_id: str) -> None:
        await jobs.executar_turno(_servicos(contexto), uuid.UUID(atendimento_id))

    @bp.task(name="iniciar", pass_context=True)
    async def iniciar(contexto: procrastinate.JobContext, atendimento_id: str) -> None:
        await jobs.executar_iniciar(_servicos(contexto), uuid.UUID(atendimento_id))

    @bp.task(name="lembrete", pass_context=True)
    async def lembrete(contexto: procrastinate.JobContext, atendimento_id: str, chat_id: str, n: int) -> None:
        async def reagendar(ate: datetime) -> None:
            await agendar_lembrete(contexto.app, uuid.UUID(atendimento_id), chat_id, n, ate)

        await jobs.executar_lembrete(_servicos(contexto), uuid.UUID(atendimento_id), n, reagendar)

    @bp.task(name="alarme_lembrete", pass_context=True)
    async def alarme_lembrete(contexto: procrastinate.JobContext, atendimento_id: str, chat_id: str, n: int) -> None:
        """O alarme agendado NÃO leva lock (um job futuro com lock trava os turnos do chat até a hora, revisão A1); ao disparar
        enfileira o `lembrete` de verdade, com lock do chat e sem agendamento."""
        await enfileirar_lembrete(contexto.app, uuid.UUID(atendimento_id), chat_id, n)

    @bp.task(name="expirar_parados", pass_context=True)
    async def expirar_parados(contexto: procrastinate.JobContext, timestamp: int) -> None:
        await jobs.executar_expirar(_servicos(contexto))

    @bp.task(name="reaper_lease", pass_context=True, queueing_lock="reaper_lease")
    async def reaper_lease(contexto: procrastinate.JobContext, timestamp: int) -> None:
        await jobs.executar_reaper_lease(_servicos(contexto))

    @bp.task(name="auditoria_pii", pass_context=True)
    async def auditoria_pii(contexto: procrastinate.JobContext, timestamp: int) -> None:
        await jobs.executar_auditoria_pii(_servicos(contexto))

    @bp.task(name="podar", pass_context=True)
    async def podar(contexto: procrastinate.JobContext, timestamp: int) -> None:
        await jobs.executar_podar(_servicos(contexto))

    @bp.task(name="bloqueio_2015", pass_context=True, retry=RETRY_BLOQUEIO)
    async def bloqueio_2015(contexto: procrastinate.JobContext, timestamp: int) -> None:
        await asyncio.to_thread(jobs.executar_bloqueio_diario, _servicos(contexto), timestamp)

    @bp.task(name="bloqueio_dataprev", pass_context=True, retry=RETRY_BLOQUEIO)
    async def bloqueio_dataprev(contexto: procrastinate.JobContext) -> None:
        await asyncio.to_thread(jobs.executar_bloqueio_dataprev, _servicos(contexto))

    @bp.task(name="reconciliar_bloqueio", pass_context=True, queueing_lock="reconciliar_bloqueio")
    async def reconciliar_bloqueio(contexto: procrastinate.JobContext, timestamp: int) -> None:
        await asyncio.to_thread(jobs.reconciliar_bloqueio_diario, _servicos(contexto))

    if com_periodicas:
        _registrar_periodicas(
            bp,
            {
                "reaper_lease": reaper_lease,
                "expirar_parados": expirar_parados,
                "auditoria_pii": auditoria_pii,
                "podar": podar,
                "bloqueio_2015": bloqueio_2015,
                "reconciliar_bloqueio": reconciliar_bloqueio,
            },
        )
    return bp


def _registrar_periodicas(bp: procrastinate.Blueprint, tarefas: dict[str, Any]) -> None:
    """Horários de negócio são de São Paulo; o cron do Procrastinate é UTC, então vêm de `cron_utc` a partir da hora local."""
    referencia = date(2026, 11, 12)
    agenda = {
        "reaper_lease": "* * * * *",
        "expirar_parados": "*/30 * * * *",
        "auditoria_pii": "7 * * * *",
        "podar": cron_utc(HORA_PODA_LOCAL, referencia),
        "bloqueio_2015": cron_utc(HORA_BLOQUEIO_ENTRADA, referencia),  # B6.7: 20:15 -> "15 23 * * *"
        "reconciliar_bloqueio": "*/5 * * * *",  # rede de segurança da tarefa das 20:15 (revisão A3)
    }
    for nome, cron in agenda.items():
        bp.periodic(cron=cron)(tarefas[nome])


# --- enfileiramento ----------------------------------------------------------------------------------------------------------------------


async def _enfileirar(app: procrastinate.App, tarefa: str, opcoes: dict[str, Any], **argumentos: Any) -> int | None:
    """Defere o job; `AlreadyEnqueued` (já há um igual esperando) devolve None em vez de erro: o job pendente cobre o pedido."""
    deferrer = app.tasks[f"{NAMESPACE}:{tarefa}"].configure(**opcoes)
    conexao = opcoes.get("connection")
    try:
        if conexao is None:
            return await deferrer.defer_async(**argumentos)
        # na transação do chamador a violação do índice único a abortaria inteira (e a gravação junto): o savepoint desfaz só o defer
        async with conexao.transaction():
            return await deferrer.defer_async(**argumentos)
    except pexc.AlreadyEnqueued:
        return None


async def enfileirar_turno(
    app: procrastinate.App, atendimento_id: uuid.UUID, chat_id: str, *, rajada_s: float = JANELA_RAJADA_S, conexao: Any = None
) -> int | None:
    """Um turno por rajada: espera 3 s, `queueing_lock` por chat (cola o que chega nesse prazo) e `lock` por chat (serializa)."""
    opcoes = {"lock": f"chat:{chat_id}", "queueing_lock": f"turno:{chat_id}", "schedule_in": {"seconds": rajada_s}, "connection": conexao}
    return await _enfileirar(app, "turno", opcoes, atendimento_id=str(atendimento_id))


async def enfileirar_iniciar(app: procrastinate.App, atendimento_id: uuid.UUID, chat_id: str, *, conexao: Any = None) -> int | None:
    opcoes = {"lock": f"chat:{chat_id}", "queueing_lock": f"iniciar:{atendimento_id}", "connection": conexao}
    return await _enfileirar(app, "iniciar", opcoes, atendimento_id=str(atendimento_id))


async def agendar_lembrete(
    app: procrastinate.App, atendimento_id: uuid.UUID, chat_id: str, n: int, em: datetime, *, conexao: Any = None
) -> int | None:
    """Lembrete `n` para `em` (UTC): agenda um ALARME sem lock (job futuro com lock travaria os turnos do chat). Um por (atendimento, n)."""
    opcoes = {"queueing_lock": f"lembrete:{atendimento_id}:{n}", "schedule_at": em, "connection": conexao}
    return await _enfileirar(app, "alarme_lembrete", opcoes, atendimento_id=str(atendimento_id), chat_id=chat_id, n=n)


async def enfileirar_lembrete(app: procrastinate.App, atendimento_id: uuid.UUID, chat_id: str, n: int) -> int | None:
    """O lembrete de verdade: roda já, com o lock do chat (serializa com os turnos). Chamado pelo alarme ao disparar."""
    opcoes = {"lock": f"chat:{chat_id}", "queueing_lock": f"lembrete_exec:{atendimento_id}:{n}"}
    return await _enfileirar(app, "lembrete", opcoes, atendimento_id=str(atendimento_id), chat_id=chat_id, n=n)


async def agendar_bloqueio_dataprev(app: procrastinate.App, relogio: Relogio) -> int | None:
    """Job único de 20/11 21:50 (SP) que grava `bloqueio_entrada=true`. Idempotente (chame em todo boot); depois da DATAPREV não agenda."""
    if relogio.agora() >= DATAPREV_ATE:
        return None
    trava = f"bloqueio_dataprev:{BLOQUEIO_DATAPREV_EM.date().isoformat()}"
    # o queueing_lock só vale para `todo`: depois de executado, o job de uma vez só não pode renascer a cada boot (revisão A4)
    existentes = await app.connector.execute_query_all_async(
        "SELECT 1 FROM procrastinate.procrastinate_jobs WHERE task_name = %(tarefa)s AND queueing_lock = %(trava)s LIMIT 1",
        tarefa=f"{NAMESPACE}:bloqueio_dataprev",
        trava=trava,
    )
    if existentes:
        return None
    return await _enfileirar(app, "bloqueio_dataprev", {"queueing_lock": trava, "schedule_at": BLOQUEIO_DATAPREV_EM})


async def rodar_worker(app: procrastinate.App, servicos: jobs.Servicos, **opcoes: Any) -> None:
    """Worker com os `Servicos` no contexto. Na subida reconcilia o bloqueio das 20:15 (se a tarefa perdeu o tick, fecha a casa agora).
    `opcoes` vão ao `run_worker_async` (`wait=False` nos testes)."""
    await asyncio.to_thread(jobs.reconciliar_bloqueio_diario, servicos)
    contexto = {**opcoes.pop("additional_context", {}), "servicos": servicos}
    opcoes.setdefault("concurrency", CONCORRENCIA_PADRAO)
    await app.run_worker_async(additional_context=contexto, **opcoes)
