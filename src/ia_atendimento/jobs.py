"""Handlers dos jobs da fila, sem Procrastinate: recebem os `Servicos` (funções injetadas) e devolvem o que fizeram.

O que é do banco (selecionar leases vencidos, gravar o bloqueio, podar, escolher o que auditar) está aqui e é testado contra o Postgres;
o que é de outras etapas (processar o turno, enviar o lembrete, repassar, expirar, varrer PII) entra por `Servicos` e, enquanto não
existe (B1.6), falha ALTO com `ServicoNaoConfigurado`: um job nunca finge que processou.
Handlers síncronos de banco rodam em thread (`asyncio.to_thread`) quando chamados de código assíncrono: o psycopg síncrono não trava o loop.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import psycopg

from ia_atendimento.calendario import (
    BLOQUEIO_DATAPREV_EM,
    DATAPREV_ATE,
    FUSO,
    HORA_BLOQUEIO_ENTRADA,
    Calendario,
    carregar_calendario,
)
from ia_atendimento.chave import ConfigCorrida, LeitorConfig, config_vigente
from ia_atendimento.relogio import Relogio

JANELA_24H = timedelta(hours=24)
LIMITE_LOTE = 200
HORAS_AUDITORIA_PII = 24
DIAS_JOBS_CONCLUIDOS = 7  # succeeded, cancelled, aborted: o worker nunca os apaga e o args/evento não tem utilidade depois
DIAS_JOBS_FALHOS = 30  # failed fica mais tempo para diagnóstico
DIAS_TEXTO = 14  # fn_texto_podar(14, 1): conversa 14 d, cofre 1 d após o encerramento
DIAS_COFRE = 1
DIAS_ATENDIMENTO = 365
JANELA_DO_BLOQUEIO = timedelta(hours=11, minutes=30)  # 20:15 -> 07:45, quando o Danilo abre a entrada
STATUS_CONCLUIDOS = ("succeeded", "cancelled", "aborted")


class ServicoNaoConfigurado(RuntimeError):
    """O job chamou um serviço que ainda não foi injetado (as implementações reais chegam na B1.6)."""


class HorarioInesperado(RuntimeError):
    """A tarefa das 20:15 rodou fora das 20h de São Paulo: o cron ficou defasado. Não grava; a vigia alerta."""


class _NaoConfigurado:
    def __init__(self, nome: str) -> None:
        self._nome = nome

    async def __call__(self, *_: Any, **__: Any) -> Any:
        raise ServicoNaoConfigurado(f"serviço '{self._nome}' não foi injetado (Servicos)")


@dataclass(frozen=True)
class InstantaneoLembrete:
    """O que o lembrete precisa saber do atendimento (a leitura real é do estado, B1.1)."""

    estado: str
    lembretes_enviados: int
    lembretes_max: int  # efetivo: min(2, faixa.lembretes_max)
    ultima_ia_em: datetime | None
    ultimo_cliente_em: datetime | None


@dataclass(frozen=True)
class LeaseVencido:
    atendimento_id: uuid.UUID
    chat_id: str
    estado: str
    gatilho: str
    lease_ate: datetime
    acao: Literal["abortar", "repassar", "retomada_perdida", "agendamento_perdido"]


@dataclass(frozen=True)
class Servicos:
    relogio: Relogio
    abrir_conexao: Callable[[], AbstractContextManager[psycopg.Connection]]
    leitor_config: LeitorConfig | None = None
    processar_turno: Callable[[uuid.UUID], Awaitable[None]] = field(default=_NaoConfigurado("processar_turno"))
    iniciar_atendimento: Callable[[uuid.UUID], Awaitable[None]] = field(default=_NaoConfigurado("iniciar_atendimento"))
    ler_para_lembrete: Callable[[uuid.UUID], Awaitable[InstantaneoLembrete | None]] = field(default=_NaoConfigurado("ler_para_lembrete"))
    enviar_lembrete: Callable[[uuid.UUID, int, bool], Awaitable[None]] = field(default=_NaoConfigurado("enviar_lembrete"))
    encerrar_sem_lembrete: Callable[[uuid.UUID, str], Awaitable[None]] = field(default=_NaoConfigurado("encerrar_sem_lembrete"))
    expirar_parados: Callable[[], Awaitable[int]] = field(default=_NaoConfigurado("expirar_parados"))
    tratar_lease_vencido: Callable[[LeaseVencido], Awaitable[None]] = field(default=_NaoConfigurado("tratar_lease_vencido"))
    auditar_pii: Callable[[Sequence[uuid.UUID]], Awaitable[int]] = field(default=_NaoConfigurado("auditar_pii"))

    def leitor(self) -> LeitorConfig:
        return self.leitor_config or LeitorConfig(self.relogio, ttl_s=0)


# --- turno, iniciar, expirar -------------------------------------------------------------------------------------------------------------


async def executar_turno(servicos: Servicos, atendimento_id: uuid.UUID) -> None:
    await servicos.processar_turno(atendimento_id)


async def executar_iniciar(servicos: Servicos, atendimento_id: uuid.UUID) -> None:
    await servicos.iniciar_atendimento(atendimento_id)


async def executar_expirar(servicos: Servicos) -> int:
    return await servicos.expirar_parados()


# --- lembrete --------------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Decisao:
    tipo: Literal["enviar", "adiar", "encerrar", "ignorar"]
    ate: datetime | None = None  # adiar: instante UTC da próxima janela
    janela_24h: bool | None = None  # enviar: o cliente falou há menos de 24 h? (senão, só template)
    motivo: str | None = None


def decidir_lembrete(
    snapshot: InstantaneoLembrete | None, agora: datetime, calendario: Calendario, *, intervalo: timedelta = timedelta(0)
) -> Decisao:
    """Regras do lembrete (B1.3): só em `aguardando_cliente`, sem resposta do cliente depois da IA e abaixo do máximo efetivo.

    Fora da janela de mensagem: adia para a abertura da próxima janela se, NESSE instante, o cliente ainda estará a <= 24 h da última
    mensagem dele; senão encerra sem lembrete (H E9).
    """
    if snapshot is None:
        return Decisao("ignorar", motivo="atendimento_inexistente")
    if snapshot.estado != "aguardando_cliente":
        return Decisao("ignorar", motivo="estado")
    if snapshot.lembretes_enviados >= snapshot.lembretes_max:
        return Decisao("ignorar", motivo="maximo_da_faixa")
    cliente, ia = snapshot.ultimo_cliente_em, snapshot.ultima_ia_em
    if cliente is not None and ia is not None and cliente > ia:
        return Decisao("ignorar", motivo="cliente_respondeu")
    devido = ia + intervalo if ia is not None else None
    if devido is not None and devido > agora:
        # o alarme é de uma fala anterior da IA (o `queueing_lock` descarta o alarme novo): o lembrete sai `intervalo` depois da ÚLTIMA fala
        futura = decidir_lembrete(snapshot, devido, calendario)
        return Decisao("adiar", ate=futura.ate if futura.tipo == "adiar" else devido)
    if calendario.dentro_da_janela(agora):
        return Decisao("enviar", janela_24h=_dentro_de_24h(cliente, agora))
    abertura = calendario.proxima_janela(agora)
    if cliente is not None and _dentro_de_24h(cliente, abertura):
        return Decisao("adiar", ate=abertura)
    return Decisao("encerrar", motivo="sem_lembrete_fora_da_janela")


def _dentro_de_24h(ultimo_cliente_em: datetime | None, instante: datetime) -> bool:
    return ultimo_cliente_em is not None and instante - ultimo_cliente_em <= JANELA_24H


def _config_do_lembrete(servicos: Servicos, n: int) -> tuple[Calendario, timedelta]:
    """Calendário vigente e o intervalo (min) do lembrete `n` em `lembretes_intervalos_min` (o último vale para os seguintes)."""
    leitor = servicos.leitor()
    with servicos.abrir_conexao() as conn:
        calendario = carregar_calendario(leitor.valor(conn, "janela_mensagem"), leitor.valor(conn, "calendario_bloqueio"))
        intervalos = leitor.valor(conn, "lembretes_intervalos_min")
    return calendario, timedelta(minutes=intervalos[min(max(n, 1), len(intervalos)) - 1])


async def executar_lembrete(
    servicos: Servicos, atendimento_id: uuid.UUID, n: int, reagendar: Callable[[datetime], Awaitable[None]]
) -> Decisao:
    snapshot = await servicos.ler_para_lembrete(atendimento_id)
    calendario, intervalo = await asyncio.to_thread(_config_do_lembrete, servicos, n)
    decisao = decidir_lembrete(snapshot, servicos.relogio.agora(), calendario, intervalo=intervalo)
    if decisao.tipo == "enviar":
        await servicos.enviar_lembrete(atendimento_id, n, bool(decisao.janela_24h))
    elif decisao.tipo == "adiar" and decisao.ate is not None:
        await reagendar(decisao.ate)
    elif decisao.tipo == "encerrar":
        await servicos.encerrar_sem_lembrete(atendimento_id, decisao.motivo or "sem_lembrete")
    return decisao


# --- reaper de lease ---------------------------------------------------------------------------------------------------------------------

# job com lock do chat (turno, iniciar, lembrete) `doing` ou `todo` = o chat está em curso; o alarme do lembrete não tem lock
_SQL_LEASES = """
SELECT a.atendimento_id, a.chat_id, a.estado, a.gatilho, a.lease_ate FROM ia.atendimento a
WHERE a.estado IN ('reservado', 'aberto', 'aguardando_cliente', 'pausado') AND a.lease_ate < %s
  AND NOT EXISTS (SELECT 1 FROM procrastinate.procrastinate_jobs j WHERE j.lock = 'chat:' || a.chat_id AND j.status IN ('doing', 'todo'))
ORDER BY a.lease_ate LIMIT %s
"""


def _acao_do_lease(estado: str, gatilho: str) -> Literal["abortar", "repassar", "retomada_perdida", "agendamento_perdido"]:
    if estado == "pausado":
        return "retomada_perdida"
    if estado == "reservado":
        return "agendamento_perdido" if gatilho == "agendamento" else "abortar"
    return "repassar"


def selecionar_leases_vencidos(conn: psycopg.Connection, agora: datetime, limite: int = LIMITE_LOTE) -> list[LeaseVencido]:
    """Leases vencidos pelo relógio injetado, sem job do chat em curso ou na fila (`doing` ou `todo`, inclusive dentro da rajada de 3 s).

    Pausado e `reservado` de agendamento têm o lease estendido até a volta (`lease_ate >= retoma_em`): só aparecem quando a volta falhou."""
    return [
        LeaseVencido(atendimento_id=r[0], chat_id=r[1], estado=r[2], gatilho=r[3], lease_ate=r[4], acao=_acao_do_lease(r[2], r[3]))
        for r in conn.execute(_SQL_LEASES, (agora, limite))
    ]


def _leases(servicos: Servicos) -> list[LeaseVencido]:
    with servicos.abrir_conexao() as conn:
        return selecionar_leases_vencidos(conn, servicos.relogio.agora())


async def executar_reaper_lease(servicos: Servicos) -> int:
    vencidos = await asyncio.to_thread(_leases, servicos)
    for lease in vencidos:
        await servicos.tratar_lease_vencido(lease)
    return len(vencidos)


# --- bloqueio programado (B6.7) ---------------------------------------------------------------------------------------------------------


def _deve_fechar(atual: object, tick: datetime | None) -> bool:
    """Critério único (tarefa das 20:15, job de 20/11 e reconciliação): fecha se ainda não está `true` e ninguém gravou DEPOIS do tick
    (quem abriu de propósito depois do tick não é desfeito, nem por job atrasado nem por retry)."""
    if atual is None:
        return True
    if atual.valor is True:
        return False
    return tick is None or atual.publicado_em < tick


def gravar_bloqueio_entrada(servicos: Servicos, por: str, tick: datetime | None = None) -> bool:
    """Grava `bloqueio_entrada=true` se ainda não está. NUNCA grava false (quem abre é o Danilo às 07:45). Devolve se gravou.

    Escreve pelo `LeitorConfig` do processo: o cache enxerga o `true` na hora (revisão A5).
    """
    leitor = servicos.leitor()
    with servicos.abrir_conexao() as conn:
        atual = config_vigente(conn, "bloqueio_entrada")
        if not _deve_fechar(atual, tick):
            return False
        try:
            leitor.registrar(
                conn, "bloqueio_entrada", True, por, versao_esperada=atual.versao if atual else 0,
                motivo="fechamento programado da entrada nova (abertos e pausados seguem)",
            )  # fmt: skip
        except ConfigCorrida:
            depois = config_vigente(conn, "bloqueio_entrada")
            if not _deve_fechar(depois, tick):  # outro worker fechou, ou o Danilo abriu, entre a leitura e a escrita
                return False
            raise
        return True


def executar_bloqueio_diario(servicos: Servicos, timestamp: int | None = None) -> bool:
    """Tarefa periódica das 20:15 (São Paulo). Decide pelo TICK (`timestamp`, o instante agendado), não pela hora em que o handler roda:
    um job atrasado por fila cheia ainda fecha a casa; um tick que não é das 20h locais (cron defasado) falha alto; um tick com mais
    de 11h30 (depois das 07:45, quando o Danilo abre) não faz nada."""
    agora = servicos.relogio.agora()
    tick = datetime.fromtimestamp(timestamp, UTC) if timestamp is not None else agora
    hora_local = tick.astimezone(FUSO)
    if hora_local.hour != HORA_BLOQUEIO_ENTRADA.hour:
        raise HorarioInesperado(f"o tick do bloqueio é das {hora_local:%H:%M} (esperado {HORA_BLOQUEIO_ENTRADA:%H}h): cron defasado")
    if agora - tick > JANELA_DO_BLOQUEIO:
        return False
    return gravar_bloqueio_entrada(servicos, "tarefa:bloqueio_2015", tick)


def reconciliar_bloqueio_diario(servicos: Servicos) -> bool:
    """Rede de segurança (subida do worker e a cada 5 min): entre 20:15 e 07:45 locais, se a chave não foi gravada depois do tick das 20:15
    e está `false`, a tarefa perdeu o tick (deploy, queda): grava `true`. Quem abriu de propósito depois do tick não é desfeito."""
    agora = servicos.relogio.agora()
    local = agora.astimezone(FUSO)
    tick = datetime.combine(local.date(), HORA_BLOQUEIO_ENTRADA, tzinfo=FUSO)
    if tick > local:
        tick -= timedelta(days=1)
    if agora - tick >= JANELA_DO_BLOQUEIO:
        return False
    return gravar_bloqueio_entrada(servicos, "tarefa:reconciliacao_bloqueio", tick)


def executar_bloqueio_dataprev(servicos: Servicos) -> bool:
    """Job único de 20/11: fecha a entrada antes da janela DATAPREV. Atrasado para depois da janela, não faz nada (a volta é do Danilo)."""
    if servicos.relogio.agora() >= DATAPREV_ATE:
        return False
    return gravar_bloqueio_entrada(servicos, "tarefa:bloqueio_dataprev", BLOQUEIO_DATAPREV_EM)


# --- poda ------------------------------------------------------------------------------------------------------------------------------

_SQL_PODAR_JOBS = """
DELETE FROM procrastinate.procrastinate_jobs j USING
  (SELECT job_id, max(at) AS ultimo FROM procrastinate.procrastinate_events GROUP BY job_id) e
WHERE e.job_id = j.id
  AND ((j.status = ANY(%s::procrastinate.procrastinate_job_status[]) AND e.ultimo < %s) OR (j.status = 'failed' AND e.ultimo < %s))
"""


@dataclass(frozen=True)
class ResultadoPoda:
    conversa: int
    cofre: int
    atendimentos: int
    passos: int
    jobs: int


def podar_jobs(
    conn: psycopg.Connection, agora: datetime, *, dias_concluidos: int = DIAS_JOBS_CONCLUIDOS, dias_falhos: int = DIAS_JOBS_FALHOS
) -> int:
    """Apaga job concluído há mais de `dias_concluidos` (falho: `dias_falhos`); evento e `args` saem junto (CASCADE). `todo`/`doing`: nunca.

    O worker do Procrastinate não apaga nada (`delete_jobs=never`) e a poda do esquema `ia` não alcança estas tabelas.
    """
    cursor = conn.execute(
        _SQL_PODAR_JOBS, (list(STATUS_CONCLUIDOS), agora - timedelta(days=dias_concluidos), agora - timedelta(days=dias_falhos))
    )
    apagados = cursor.rowcount
    # o rastro da periódica (um por tick; o `job_id` vira NULL com a poda do job) também não se acumula (revisão A13)
    conn.execute(
        "DELETE FROM procrastinate.procrastinate_periodic_defers WHERE job_id IS NULL AND defer_timestamp < %s",
        (int((agora - timedelta(days=dias_falhos)).timestamp()),),
    )
    return apagados


def _podar(servicos: Servicos) -> ResultadoPoda:
    with servicos.abrir_conexao() as conn:
        conversa, cofre = conn.execute(
            "SELECT linhas_conversa, linhas_cofre FROM ia.fn_texto_podar(%s, %s)", (DIAS_TEXTO, DIAS_COFRE)
        ).fetchone()
        atendimentos, passos = conn.execute("SELECT atendimentos, passos FROM ia.fn_atendimento_podar(%s)", (DIAS_ATENDIMENTO,)).fetchone()
        return ResultadoPoda(conversa, cofre, atendimentos, passos, podar_jobs(conn, servicos.relogio.agora()))


async def executar_podar(servicos: Servicos) -> ResultadoPoda:
    return await asyncio.to_thread(_podar, servicos)


# --- auditoria de PII (esqueleto) -------------------------------------------------------------------------------------

_SQL_PARA_AUDITAR = """
SELECT atendimento_id FROM ia.atendimento
WHERE estado = 'encerrado' AND pii_auditoria IS NULL AND encerrado_em < %s ORDER BY encerrado_em LIMIT %s
"""


def _para_auditar(servicos: Servicos) -> list[uuid.UUID]:
    corte = servicos.relogio.agora() - timedelta(hours=HORAS_AUDITORIA_PII)
    with servicos.abrir_conexao() as conn:
        return [r[0] for r in conn.execute(_SQL_PARA_AUDITAR, (corte, LIMITE_LOTE))]


async def executar_auditoria_pii(servicos: Servicos) -> int:
    """Seleciona os encerrados há mais de 24 h ainda sem auditoria e entrega ao serviço (que varre, grava false/true e alerta)."""
    ids = await asyncio.to_thread(_para_auditar, servicos)
    return await servicos.auditar_pii(ids) if ids else 0
