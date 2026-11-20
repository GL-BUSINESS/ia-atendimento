"""Fila Procrastinate (psycopg): app, tarefas, enfileiramento com trava por chat e as tarefas periódicas.

- **Conexão:** `options=-c search_path=procrastinate,public` no conector (as funções e gatilhos do Procrastinate usam nomes sem schema);
  conexão direta ao Postgres, nunca por pooler (LISTEN/NOTIFY não atravessa pooler em modo transação; ver `prontidao.py`).
- **Rajada:** o `queueing_lock` do Procrastinate 3.10.0 é índice único parcial só para `status='todo'`, sem janela. Por isso o turno é
  agendado `schedule_in=3 s` com `queueing_lock=turno:{chat}`: mensagens dentro desses 3 s caem no mesmo job (`AlreadyEnqueued` engolido).
  `lock=chat:{chat}` impede dois jobs do mesmo chat de rodarem juntos, inclusive um turno e o seguinte. Resíduo aceito: o turno em rajada
  (id menor, 3 s) segura `iniciar`/`lembrete` do mesmo chat por até 3 s.
  `POOL_MAX=8` com `concurrency=4` deixa 2 conexões livres por processo (4 jobs + listener + batimento).
- **App por chamada:** o `Blueprint` nasce em `criar_app`, nunca no import: `add_tasks_from` o modifica, então não se reaproveita.
  Os `Servicos` (funções injetadas, `jobs.py`) chegam à tarefa por `additional_context`, sem estado global.
- **Volta combinada (B5.7b):** `alarme_retomar` (agendado em `dispara_em`, SEM lock, `queueing_lock=retomar:{agendamento_id}`) enfileira o
  `retomar` de verdade (`lock=chat:`, `queueing_lock=retomar_exec:{agendamento_id}`); `reaper_agenda` por minuto reenfileira o que ficou
  sem job vivo.
- Nenhuma tarefa decide negócio: chama o handler de `jobs.py` ou `agenda_jobs.py`.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date, datetime, time
from typing import Any

import procrastinate
import psycopg
from procrastinate import exceptions as pexc
from procrastinate.exceptions import ConnectorException
from procrastinate.worker import Worker
from psycopg import ProgrammingError
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from ia_atendimento import agenda_jobs, jobs
from ia_atendimento.calendario import BLOQUEIO_DATAPREV_EM, DATAPREV_ATE, HORA_BLOQUEIO_ENTRADA, cron_utc
from ia_atendimento.chave import ConfigCorrida
from ia_atendimento.relogio import Relogio
from ia_atendimento.worker_vivo import (
    GRACA_DE_ENCERRAMENTO_S,
    HEARTBEAT_PRESO_S,
    INTERVALO_VIGIA_S,
    TOLERANCIA_VIGIA_S,
    WorkerPerdeuOBatimento,
    derrubado_pela_linha_sumida,
    liberar_jobs_presos,
    vigiar_batimento,
)

log = logging.getLogger(__name__)
SEARCH_PATH = "procrastinate,public"
JANELA_RAJADA_S = 3
NAMESPACE = "ia"
POOL_MIN = 1
POOL_MAX = 8
CONCORRENCIA_PADRAO = 4  # o lock por chat serializa o que precisa; a periódica não espera atrás de um turno de modelo (revisão A3)
# só falha transitória de banco/rede/corrida repete; erro de lógica (ex.: HorarioInesperado) falha de vez e a vigia alerta
RETRY_FILA = procrastinate.RetryStrategy(max_attempts=5, wait=30, retry_exceptions={psycopg.Error, OSError})
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
    _tarefas_do_chat(bp)
    periodicas = {**_tarefas_de_manutencao(bp), **_tarefas_da_agenda(bp)}
    if com_periodicas:
        _registrar_periodicas(bp, periodicas)
    return bp


def _tarefas_do_chat(bp: procrastinate.Blueprint) -> None:
    @bp.task(name="turno", pass_context=True)
    async def turno(contexto: procrastinate.JobContext, atendimento_id: str) -> None:
        await jobs.executar_turno(_servicos(contexto), uuid.UUID(atendimento_id))

    @bp.task(name="iniciar", pass_context=True)
    async def iniciar(contexto: procrastinate.JobContext, atendimento_id: str) -> None:
        await jobs.executar_iniciar(_servicos(contexto), uuid.UUID(atendimento_id))

    @bp.task(name="lembrete", pass_context=True, retry=RETRY_FILA)
    async def lembrete(contexto: procrastinate.JobContext, atendimento_id: str, chat_id: str, n: int) -> None:
        async def reagendar(ate: datetime) -> None:
            await agendar_lembrete(contexto.app, uuid.UUID(atendimento_id), chat_id, n, ate)

        await jobs.executar_lembrete(_servicos(contexto), uuid.UUID(atendimento_id), n, reagendar)

    @bp.task(name="alarme_lembrete", pass_context=True, retry=RETRY_FILA)
    async def alarme_lembrete(contexto: procrastinate.JobContext, atendimento_id: str, chat_id: str, n: int) -> None:
        """O alarme agendado NÃO leva lock (um job futuro com lock trava os turnos do chat até a hora, revisão A1); ao disparar
        enfileira o `lembrete` de verdade, com lock do chat e sem agendamento."""
        await enfileirar_lembrete(contexto.app, uuid.UUID(atendimento_id), chat_id, n)

    @bp.task(name="alarme_encerrar_por_chave", pass_context=True, retry=RETRY_FILA)
    async def alarme_encerrar_por_chave(contexto: procrastinate.JobContext, atendimento_id: str, chat_id: str) -> None:
        """Alarme SEM lock (como o do lembrete): um job futuro com `lock=chat:` seguraria turnos, repasse e lembrete do chat até a hora
        (R2-01). Ao disparar enfileira o `encerrar_por_chave` de verdade, com o lock do chat e sem atraso."""
        await enfileirar_encerrar_por_chave(contexto.app, uuid.UUID(atendimento_id), chat_id)

    @bp.task(name="encerrar_por_chave", pass_context=True)
    async def encerrar_por_chave(contexto: procrastinate.JobContext, atendimento_id: str) -> None:
        await jobs.executar_encerrar_por_chave(_servicos(contexto), uuid.UUID(atendimento_id))

    @bp.task(name="repasse", pass_context=True, retry=RETRY_FILA)
    async def repasse(contexto: procrastinate.JobContext, atendimento_id: str, chat_id: str, desde: str | None = None) -> None:
        """B1.6b (08 §7.1/§7.2): uma rodada; o `Reagendar` vira job novo com o mesmo `desde` (o prazo de D-14 não reinicia)."""
        atd = uuid.UUID(atendimento_id)
        proximo = await jobs.executar_repasse(_servicos(contexto), atd, datetime.fromisoformat(desde) if desde else None)
        if proximo is not None:
            await enfileirar_repasse(contexto.app, atd, chat_id, desde=proximo.desde, atraso_s=proximo.atraso_s)


def _tarefas_da_agenda(bp: procrastinate.Blueprint) -> dict[str, Any]:
    """A volta combinada (alarme, job de verdade e a rede por minuto); devolve a periódica."""

    @bp.task(name="alarme_retomar", pass_context=True, retry=RETRY_FILA)
    async def alarme_retomar(contexto: procrastinate.JobContext, agendamento_id: str, atendimento_id: str, chat_id: str) -> None:
        """Alarme SEM lock (um `todo` futuro com `lock=chat:` seguraria os turnos do chat na pausa): ao disparar, enfileira o `retomar`."""
        await enfileirar_retomar(contexto.app, uuid.UUID(agendamento_id), uuid.UUID(atendimento_id), chat_id)

    @bp.task(name="retomar", pass_context=True)  # sem retry: a reivindicação (CAS `confirmado → disparado`) não é reentrante
    async def retomar(contexto: procrastinate.JobContext, agendamento_id: str, atendimento_id: str, chat_id: str) -> None:
        async def reagendar(atraso_s: float) -> None:
            await agendar_retomada(contexto.app, uuid.UUID(agendamento_id), uuid.UUID(atendimento_id), chat_id, atraso_s)

        await agenda_jobs.executar_retomar(_servicos(contexto), uuid.UUID(agendamento_id), reagendar, job_id=contexto.job.id)

    @bp.task(name="reaper_agenda", pass_context=True, queueing_lock="reaper_agenda")
    async def reaper_agenda(contexto: procrastinate.JobContext, timestamp: int) -> None:
        async def enfileirar(v: agenda_jobs.Vencido) -> None:
            await enfileirar_retomar(contexto.app, v.agendamento_id, v.atendimento_id, v.chat_id)

        await agenda_jobs.executar_reaper_agenda(_servicos(contexto), enfileirar)

    @bp.task(name="jobs_presos", pass_context=True, queueing_lock="jobs_presos")
    async def jobs_presos(contexto: procrastinate.JobContext, timestamp: int) -> None:
        await liberar_jobs_presos(contexto.app)

    return {"reaper_agenda": reaper_agenda, "jobs_presos": jobs_presos}


def _tarefas_de_manutencao(bp: procrastinate.Blueprint) -> dict[str, Any]:
    """Tarefas sem chat (reaper, expiração, auditoria, poda, bloqueios); devolve as periódicas, que `_registrar_periodicas` agenda."""

    @bp.task(name="expirar_parados", pass_context=True)
    async def expirar_parados(contexto: procrastinate.JobContext, timestamp: int) -> None:
        await jobs.executar_expirar(_servicos(contexto))

    @bp.task(name="reaper_lease", pass_context=True, queueing_lock="reaper_lease")
    async def reaper_lease(contexto: procrastinate.JobContext, timestamp: int) -> None:
        await jobs.executar_reaper_lease(_servicos(contexto))

    @bp.task(name="reaper_ledger", pass_context=True, queueing_lock="reaper_ledger")
    async def reaper_ledger(contexto: procrastinate.JobContext, timestamp: int) -> None:
        await jobs.executar_reaper_ledger(_servicos(contexto))

    @bp.task(name="publicar_espelho", pass_context=True, queueing_lock="publicar_espelho")
    async def publicar_espelho(contexto: procrastinate.JobContext, timestamp: int) -> None:
        await jobs.executar_publicar_espelho(_servicos(contexto))

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

    return {
        "reaper_lease": reaper_lease,
        "reaper_ledger": reaper_ledger,
        "publicar_espelho": publicar_espelho,
        "expirar_parados": expirar_parados,
        "auditoria_pii": auditoria_pii,
        "podar": podar,
        "bloqueio_2015": bloqueio_2015,
        "reconciliar_bloqueio": reconciliar_bloqueio,
    }


def _registrar_periodicas(bp: procrastinate.Blueprint, tarefas: dict[str, Any]) -> None:
    """Horários de negócio são de São Paulo; o cron do Procrastinate é UTC, então vêm de `cron_utc` a partir da hora local."""
    referencia = date(2026, 11, 12)
    agenda = {
        "reaper_lease": "* * * * *",
        "reaper_agenda": "* * * * *",  # B5.7b: reenfileira a volta combinada que ficou sem job vivo
        "jobs_presos": "* * * * *",  # R1-01: `doing` de worker morto segura o lock do chat para sempre
        "expirar_parados": "*/30 * * * *",
        "reaper_ledger": "* * * * *",  # B1.6b (G-0116): reservada > 10 min ⇒ nao_criada; enviada órfã pelo critério de classe
        # B1.6b (08 §7.3): o contrato pede 10 s; o cron do Procrastinate é de minuto. O publicador do evento novo, deferido na transação,
        # fica para a integração (B1.7); até lá o atraso máximo é ~1 min (o alerta amarelo é de 10 min).
        "publicar_espelho": "* * * * *",
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


def _pedido_turno(atendimento_id: uuid.UUID, chat_id: str, rajada_s: float, conexao: Any) -> tuple[str, dict[str, Any], dict[str, Any]]:
    opcoes = {"lock": f"chat:{chat_id}", "queueing_lock": f"turno:{chat_id}", "schedule_in": {"seconds": rajada_s}, "connection": conexao}
    return "turno", opcoes, {"atendimento_id": str(atendimento_id)}


def _pedido_iniciar(atendimento_id: uuid.UUID, chat_id: str, conexao: Any) -> tuple[str, dict[str, Any], dict[str, Any]]:
    opcoes = {"lock": f"chat:{chat_id}", "queueing_lock": f"iniciar:{atendimento_id}", "connection": conexao}
    return "iniciar", opcoes, {"atendimento_id": str(atendimento_id)}


def _pedido_alarme_encerrar_por_chave(
    atendimento_id: uuid.UUID, chat_id: str, atraso_s: float, conexao: Any
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """O agendado para daqui a `atraso_s` NÃO leva `lock` (R2-01); o `queueing_lock` garante um alarme por atendimento."""
    opcoes = {"queueing_lock": f"encerrar_por_chave:{atendimento_id}", "schedule_in": {"seconds": atraso_s}, "connection": conexao}
    return "alarme_encerrar_por_chave", opcoes, {"atendimento_id": str(atendimento_id), "chat_id": chat_id}


def _pedido_alarme_retomar(
    agendamento_id: uuid.UUID, atendimento_id: uuid.UUID, chat_id: str, quando: datetime | float, conexao: Any
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """O alarme NÃO leva `lock` (ver a docstring do módulo); o `queueing_lock` garante um alarme `todo` por agendamento.
    `quando` é um instante (`schedule_at`, na criação) ou um atraso em segundos (`schedule_in`, no rearme: relativo ao `now()` do banco)."""
    hora = {"schedule_at": quando} if isinstance(quando, datetime) else {"schedule_in": {"seconds": quando}}
    opcoes = {"queueing_lock": f"{agenda_jobs.PREFIXO_ALARME}{agendamento_id}", **hora, "connection": conexao}
    argumentos = {"agendamento_id": str(agendamento_id), "atendimento_id": str(atendimento_id), "chat_id": chat_id}
    return "alarme_retomar", opcoes, argumentos


async def enfileirar_turno(
    app: procrastinate.App, atendimento_id: uuid.UUID, chat_id: str, *, rajada_s: float = JANELA_RAJADA_S, conexao: Any = None
) -> int | None:
    """Um turno por rajada: espera 3 s, `queueing_lock` por chat (cola o que chega nesse prazo) e `lock` por chat (serializa)."""
    tarefa, opcoes, argumentos = _pedido_turno(atendimento_id, chat_id, rajada_s, conexao)
    return await _enfileirar(app, tarefa, opcoes, **argumentos)


async def enfileirar_iniciar(app: procrastinate.App, atendimento_id: uuid.UUID, chat_id: str, *, conexao: Any = None) -> int | None:
    tarefa, opcoes, argumentos = _pedido_iniciar(atendimento_id, chat_id, conexao)
    return await _enfileirar(app, tarefa, opcoes, **argumentos)


async def enfileirar_encerrar_por_chave(app: procrastinate.App, atendimento_id: uuid.UUID, chat_id: str) -> int | None:
    """O encerramento de verdade: roda já, com o lock do chat (serializa com os turnos). Chamado pelo alarme ao disparar."""
    opcoes = {"lock": f"chat:{chat_id}", "queueing_lock": f"encerrar_exec:{atendimento_id}"}
    return await _enfileirar(app, "encerrar_por_chave", opcoes, atendimento_id=str(atendimento_id))


async def agendar_retomada(
    app: procrastinate.App,
    agendamento_id: uuid.UUID,
    atendimento_id: uuid.UUID,
    chat_id: str,
    quando: datetime | float,
    *,
    conexao: Any = None,
) -> int | None:
    """Alarme da volta combinada para `quando` (instante UTC = `dispara_em`, ou atraso em segundos). `None` = já havia um alarme `todo`."""
    tarefa, opcoes, argumentos = _pedido_alarme_retomar(agendamento_id, atendimento_id, chat_id, quando, conexao)
    return await _enfileirar(app, tarefa, opcoes, **argumentos)


async def enfileirar_retomar(app: procrastinate.App, agendamento_id: uuid.UUID, atendimento_id: uuid.UUID, chat_id: str) -> int | None:
    """O `retomar` de verdade: roda já, com o lock do chat (serializa com os turnos). Vem do alarme ao disparar e do `reaper_agenda`."""
    opcoes = {"lock": f"chat:{chat_id}", "queueing_lock": f"{agenda_jobs.PREFIXO_EXEC}{agendamento_id}"}
    argumentos = {"agendamento_id": str(agendamento_id), "atendimento_id": str(atendimento_id), "chat_id": chat_id}
    return await _enfileirar(app, "retomar", opcoes, **argumentos)


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


async def enfileirar_repasse(
    app: procrastinate.App, atendimento_id: uuid.UUID, chat_id: str, *, desde: datetime | None = None, atraso_s: float = 0
) -> int | None:
    """O job `repasse` (B1.6b): lock do chat (serializa com turno e lembrete), um `todo` por atendimento."""
    opcoes: dict[str, Any] = {"lock": f"chat:{chat_id}", "queueing_lock": f"repasse:{atendimento_id}"}
    if atraso_s > 0:
        opcoes["schedule_in"] = {"seconds": atraso_s}
    argumentos = {"atendimento_id": str(atendimento_id), "chat_id": chat_id, "desde": desde.isoformat() if desde else None}
    return await _enfileirar(app, "repasse", opcoes, **argumentos)


# --- enfileiramento SÍNCRONO na transação do chamador (API de entrada, B1.5) --------------------------------------------------------


def _enfileirar_sync(app: procrastinate.App, tarefa: str, opcoes: dict[str, Any], **argumentos: Any) -> int | None:
    """Como `_enfileirar`, com a conexão psycopg SÍNCRONA da API: o job entra na MESMA transação da gravação (some junto no rollback).

    Savepoint em volta: o `AlreadyEnqueued` (índice único do `queueing_lock`) não derruba a transação do chamador. `None` = já havia um."""
    deferrer = app.tasks[f"{NAMESPACE}:{tarefa}"].configure(**opcoes)
    conexao = opcoes["connection"]
    try:
        with conexao.transaction():
            return deferrer.defer(**argumentos)
    except pexc.AlreadyEnqueued:
        return None


def enfileirar_turno_sync(
    app: procrastinate.App, conexao: psycopg.Connection, atendimento_id: uuid.UUID, chat_id: str, *, rajada_s: float = JANELA_RAJADA_S
) -> int | None:
    tarefa, opcoes, argumentos = _pedido_turno(atendimento_id, chat_id, rajada_s, conexao)
    return _enfileirar_sync(app, tarefa, opcoes, **argumentos)


def enfileirar_iniciar_sync(app: procrastinate.App, conexao: psycopg.Connection, atendimento_id: uuid.UUID, chat_id: str) -> int | None:
    tarefa, opcoes, argumentos = _pedido_iniciar(atendimento_id, chat_id, conexao)
    return _enfileirar_sync(app, tarefa, opcoes, **argumentos)


def enfileirar_encerrar_por_chave_sync(
    app: procrastinate.App, conexao: psycopg.Connection, atendimento_id: uuid.UUID, chat_id: str, *, atraso_s: float
) -> int | None:
    """Um ALARME por atendimento, com atraso (escalonado pelo chamador), sem lock; idempotente por `queueing_lock`."""
    tarefa, opcoes, argumentos = _pedido_alarme_encerrar_por_chave(atendimento_id, chat_id, atraso_s, conexao)
    return _enfileirar_sync(app, tarefa, opcoes, **argumentos)


def agendar_retomada_sync(
    app: procrastinate.App, conexao: psycopg.Connection, agendamento_id: uuid.UUID, atendimento_id: uuid.UUID, chat_id: str, em: datetime
) -> int | None:
    """Um alarme por agendamento, para `dispara_em`, na transação do chamador (a API ou a confirmação); idempotente por `queueing_lock`."""
    tarefa, opcoes, argumentos = _pedido_alarme_retomar(agendamento_id, atendimento_id, chat_id, em, conexao)
    return _enfileirar_sync(app, tarefa, opcoes, **argumentos)


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


def _novo_worker(app: procrastinate.App, **opcoes: Any) -> Worker:
    """O que `app.run_worker_async` faz por dentro, mas devolvendo o `Worker` (a vigia do batimento precisa do `worker_id` e do `stop`)."""
    app.perform_import_paths()
    return Worker(app=app, **opcoes)


async def rodar_worker(app: procrastinate.App, servicos: jobs.Servicos, **opcoes: Any) -> None:
    """Worker com os `Servicos` no contexto. Na subida reconcilia o bloqueio das 20:15 (se a tarefa perdeu o tick, fecha a casa agora).
    `opcoes` vão ao `Worker` (`wait=False` nos testes); `vigia_intervalo_s` e `vigia_tolerancia_s` são da vigia do batimento.

    O worker poda os mortos com `stalled_worker_timeout = HEARTBEAT_PRESO_S` (o padrão, 30 s, deixaria `worker_id` NULL no job de um
    worker só lento antes da margem da fila) e uma vigia o PARA, abortando os jobs em voo, se ele perder a própria linha ou o batimento
    (`WorkerPerdeuOBatimento`: o processo sai com erro e o supervisor o reinicia)."""
    try:
        await asyncio.to_thread(jobs.reconciliar_bloqueio_diario, servicos)
    except psycopg.Error as erro:  # a periódica de 5 min repete; um soluço de banco não pode impedir o worker de subir
        log.warning("reconciliação do bloqueio na subida falhou (%s)", type(erro).__name__)
    intervalo, tolerancia = opcoes.pop("vigia_intervalo_s", INTERVALO_VIGIA_S), opcoes.pop("vigia_tolerancia_s", TOLERANCIA_VIGIA_S)
    contexto = {**opcoes.pop("additional_context", {}), "servicos": servicos}
    opcoes.setdefault("concurrency", CONCORRENCIA_PADRAO)
    opcoes.setdefault("stalled_worker_timeout", HEARTBEAT_PRESO_S)
    opcoes.setdefault("shutdown_graceful_timeout", GRACA_DE_ENCERRAMENTO_S)
    worker = _novo_worker(app, additional_context=contexto, **opcoes)
    vigia = asyncio.create_task(vigiar_batimento(app, worker, intervalo_s=intervalo, tolerancia_s=tolerancia), name="vigia_do_batimento")
    try:
        await worker.run()
    except ConnectorException as erro:  # a linha sumiu no meio de um `fetch_job` (FK): o mesmo veredito da vigia, não um erro genérico
        if derrubado_pela_linha_sumida(erro):
            log.error("o fetch do worker caiu na FK do worker_id: a linha dele foi podada por outro worker (linha_sumiu)")
            raise WorkerPerdeuOBatimento("linha_sumiu") from None
        raise
    finally:
        vigia.cancel()
        await asyncio.gather(vigia, return_exceptions=True)
    if vigia.done() and not vigia.cancelled() and vigia.exception() is None:
        raise WorkerPerdeuOBatimento(vigia.result())
