"""Worker vivo ou morto (R1-01, revisão 1 da B5.7b): libera o `lock=chat:` de job preso e faz o worker sem batimento abortar os seus.

Um worker que leva `SIGKILL` (deploy) deixa o job `doing` para sempre, e o `lock=chat:` dele segura TODO job posterior do chat: o
turno do cliente nunca sai e o `reaper_lease` não enxerga o chat (`NOT EXISTS job doing no chat`). Dois lados, numa só margem:

- **Fila** (`liberar_jobs_presos`, periódica): UM `UPDATE … WHERE status = 'doing' AND <worker morto>` que reconfere o predicado na
  escrita (ler e depois `finish_job` deixava um job que acabou no meio virar exceção). «Morto» = batimento mais velho que
  `HEARTBEAT_PRESO_S` **ou** `worker_id` NULL (o Procrastinate podou o worker) com o job rodando há mais de `HEARTBEAT_PRESO_S` (último
  `started`). Sem essa idade, o job de um worker só lento, podado com os 30 s padrão, seria dado como preso na hora.
- **Worker** (`vigiar_batimento`): quem vê a própria linha sumir, o próprio batimento envelhecer ou o banco inalcançável por
  `TOLERANCIA_VIGIA_S` (menor que a margem da fila) para o worker e ABORTA os jobs em voo, antes de a fila dá-los como falhos.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Final, Protocol

import procrastinate
import psycopg

from ia_atendimento.prontidao import HEARTBEAT_MAX_S

log = logging.getLogger(__name__)
HEARTBEAT_PRESO_S: Final = HEARTBEAT_MAX_S * 2  # margem comum: batimento velho OU job de worker podado rodando há mais que isto = preso
TOLERANCIA_VIGIA_S: Final = HEARTBEAT_PRESO_S * 2 / 3  # o worker se aborta ANTES (40 s) de a fila o dar por morto (60 s)
INTERVALO_VIGIA_S: Final = 10.0
# Prazo para os jobs em voo terminarem depois do SIGTERM do deploy; passado, o worker os aborta. Menor que o `stop_grace_period` do
# contêiner (40 s): sem prazo finito o worker esperava sem limite até o SIGKILL, e o `doing` que sobrava só saía pela `jobs_presos`.
GRACA_DE_ENCERRAMENTO_S: Final = 30.0

_SQL_PRESOS: Final = """
UPDATE procrastinate.procrastinate_jobs j
   SET status = 'failed', abort_requested = false, attempts = j.attempts + 1
 WHERE j.status = 'doing'
   AND (EXISTS (SELECT 1 FROM procrastinate.procrastinate_workers w
                 WHERE w.id = j.worker_id AND w.last_heartbeat < now() - make_interval(secs => %(limite)s))
        OR (j.worker_id IS NULL
            AND coalesce((SELECT max(e.at) FROM procrastinate.procrastinate_events e WHERE e.job_id = j.id AND e.type = 'started'),
                         '-infinity'::timestamptz) < now() - make_interval(secs => %(limite)s)))
RETURNING j.id
"""
_SQL_MEU_BATIMENTO: Final = (
    "SELECT extract(epoch FROM now() - last_heartbeat)::float8 AS idade FROM procrastinate.procrastinate_workers WHERE id = %(id)s"
)


class WorkerPerdeuOBatimento(RuntimeError):
    """O worker se parou porque perdeu a posse dos próprios jobs (o supervisor deve reiniciá-lo e alertar)."""


class _Worker(Protocol):
    worker_id: int | None
    shutdown_graceful_timeout: float | None

    def stop(self) -> None: ...


async def liberar_jobs_presos(app: procrastinate.App, *, limite_s: float = HEARTBEAT_PRESO_S) -> list[int]:
    """Dá como `failed` todo job `doing` de worker morto, numa só instrução. Devolve os ids; só ids no log, nunca argumentos de job.

    `failed`, não `todo`: a tarefa pode já ter feito o efeito (a volta já reivindicou o agendamento), e quem repete é o negócio
    (`reaper_agenda`, `reaper_lease`), nunca a fila."""
    linhas = await app.connector.execute_query_all_async(_SQL_PRESOS, limite=limite_s)
    liberados = [int(linha["id"]) for linha in linhas]
    if liberados:
        log.warning("jobs presos de worker morto dados como falhos: %s", liberados)
    return liberados


def derrubado_pela_linha_sumida(erro: BaseException) -> bool:
    """A queda é o `fetch_job` batendo na FK `procrastinate_jobs.worker_id → procrastinate_workers` porque OUTRO worker podou a linha deste?
    O Procrastinate embrulha o erro do banco em `ConnectorException`; a causa é a `ForeignKeyViolation` do `worker_id`. `rodar_worker` dá a
    essa queda o mesmo veredito da vigia (`linha_sumiu`, saída 3): o resultado não depende de quem chegou primeiro, a vigia ou o `fetch`.
    (O `worker_id` do `Worker` já foi zerado quando `run()` levanta, então não dá para reconsultar a linha: a causa é o sinal.)"""
    causa = erro.__cause__
    return isinstance(causa, psycopg.errors.ForeignKeyViolation) and "worker" in (causa.diag.constraint_name or "")


def motivo_de_abortar(*, existe: bool, idade_s: float | None, sem_resposta_ha_s: float, tolerancia_s: float) -> str | None:
    """Por que o worker deve abortar os jobs em voo, ou `None`. Puro: a regra inteira da vigia num lugar só."""
    if not existe:
        return "linha_sumiu"  # outro worker o podou (`stalled_worker_timeout`) ou alguém apagou: já não há posse a renovar
    if idade_s is not None and idade_s >= tolerancia_s:
        return "batimento_velho"  # o batimento não é renovado (laço bloqueado ou escrita falhando)
    if sem_resposta_ha_s >= tolerancia_s:
        return "banco_inalcancavel"  # nem a leitura do batimento passa: a fila também vai dá-lo por morto
    return None


async def vigiar_batimento(
    app: procrastinate.App,
    worker: _Worker,
    *,
    intervalo_s: float = INTERVALO_VIGIA_S,
    tolerancia_s: float = TOLERANCIA_VIGIA_S,
) -> str:
    """Confere a linha do próprio worker a cada `intervalo_s`; ao perder a posse, aborta os jobs em voo (`shutdown_graceful_timeout = 0`) e
    para o worker. Devolve o motivo. O Procrastinate já para o worker se a ESCRITA do batimento levanta, mas não vê a linha sumir (o
    `UPDATE … WHERE id` de 0 linhas passa em silêncio): é isso que esta vigia cobre."""
    laco = asyncio.get_running_loop()
    ultimo_ok = laco.time()
    while True:
        await asyncio.sleep(intervalo_s)
        if worker.worker_id is None:
            continue
        existe, idade = True, None
        try:
            linhas: list[Any] = await app.connector.execute_query_all_async(_SQL_MEU_BATIMENTO, id=worker.worker_id)
        except Exception as erro:  # banco fora, pool esgotado, timeout: conta o tempo sem resposta
            log.warning("vigia do batimento: leitura falhou (%s)", type(erro).__name__)
        else:
            ultimo_ok = laco.time()
            existe, idade = bool(linhas), (float(linhas[0]["idade"]) if linhas else None)
        motivo = motivo_de_abortar(existe=existe, idade_s=idade, sem_resposta_ha_s=laco.time() - ultimo_ok, tolerancia_s=tolerancia_s)
        if motivo is not None:
            log.error("worker %s perdeu o batimento (%s): abortando os jobs em voo", worker.worker_id, motivo)
            worker.shutdown_graceful_timeout = 0  # sem espera: o job superado não pode seguir enviando enquanto a fila o libera
            worker.stop()
            return motivo
