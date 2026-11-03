"""Jobs presos (R1-01 da revisão 1 da B5.7b): `doing` de worker morto segura o `lock=chat:` de QUALQUER tarefa até alguém dá-lo como falho.

Sem a periódica `jobs_presos`, um `SIGKILL` no meio da volta (deploy do Coolify) deixa o lead `pausado` para sempre: o job `retomar` fica `doing` (com
`worker_id` NULL, o worker novo poda o morto), o `reaper_lease` não enxerga o chat (`NOT EXISTS job doing no chat`) e o turno do cliente fica `todo`.
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from croniter import croniter

from ia_atendimento import fila
from ia_atendimento.relogio import RelogioFalso
from ia_atendimento.worker_vivo import (
    HEARTBEAT_PRESO_S,
    TOLERANCIA_VIGIA_S,
    WorkerPerdeuOBatimento,
    motivo_de_abortar,
    vigiar_batimento,
)
from tests import fixtures_fila as ff
from tests.apoio_agenda import Voltas, inserir_job, novo_worker, pausado_confirmado
from tests.fixtures_fila import Chamadas, hex24, jobs_por_status, montar_servicos

conn_app, conn_super, relogio, conninfo_app = ff.conn_app, ff.conn_super, ff.relogio, ff.conninfo_app
pytestmark = pytest.mark.banco
WORKER_MATAVEL = Path(__file__).resolve().parent / "worker_matavel.py"


def criar(conninfo: str, **opcoes):
    return fila.criar_app(conninfo, com_periodicas=opcoes.pop("com_periodicas", False))


async def rodar(app, servicos) -> None:
    await app.run_worker_async(
        wait=False, install_signal_handlers=False, additional_context={"servicos": servicos}, fetch_job_polling_interval=0.05
    )


def _status(conn, job_id: int) -> str:
    return conn.execute("SELECT status::text FROM procrastinate.procrastinate_jobs WHERE id = %s", (job_id,)).fetchone()[0]


# --- a prova de ponta a ponta: SIGKILL real depois do CAS -------------------------------------------------------------------------------------


async def test_sigkill_no_meio_da_volta_o_lead_volta_a_ser_visto_pelo_reaper_lease(
    banco, conn_app, conn_super, conninfo_app, relogio, versoes, tmp_path
):
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara, fase="E5")
    app = criar(conninfo_app)
    async with app.open_async():
        await fila.agendar_retomada(app, caso.agendamento_id, caso.atendimento_id, caso.chat_id, dispara)
    conn_super.execute("UPDATE procrastinate.procrastinate_jobs SET scheduled_at = now() - interval '1 second'")
    marcador = tmp_path / "volta.txt"
    env = {
        **os.environ,
        "WORKER_MATAVEL_CONNINFO": conninfo_app,
        "WORKER_MATAVEL_AGORA": (dispara + timedelta(seconds=5)).isoformat(),
        "WORKER_MATAVEL_MARCADOR": str(marcador),
    }
    processo = subprocess.Popen([sys.executable, str(WORKER_MATAVEL)], env=env)
    try:
        await ff.esperar(marcador.exists, limite_s=30)  # o CAS já passou: o worker está dentro da volta
        assert conn_app.execute("SELECT estado FROM ia.agendamento WHERE agendamento_id = %s", (caso.agendamento_id,)).fetchone() == (
            "disparado",
        )
        os.kill(processo.pid, signal.SIGKILL)
    finally:
        processo.wait(timeout=10)
    assert [j[:2] for j in jobs_por_status(conn_super, "ia:retomar")] == [("ia:retomar", "doing")], "o job do worker morto ficou `doing`"

    # passa o tempo: o batimento do morto envelhece e chega a hora em que o lease do pausado vence (retoma_em + 30 min)
    conn_super.execute("UPDATE procrastinate.procrastinate_workers SET last_heartbeat = now() - interval '10 minutes'")
    conn_super.execute("UPDATE procrastinate.procrastinate_events SET at = at - interval '10 minutes'")  # e o job já roda há tempo
    depois = RelogioFalso(dispara + timedelta(minutes=31))
    chamadas = Chamadas()
    servicos = montar_servicos(banco, depois, chamadas, retomar_atendimento=Voltas())
    app2 = criar(conninfo_app)
    async with app2.open_async():
        await app2.tasks["ia:jobs_presos"].defer_async(timestamp=int(time.time()))  # a periódica geral, um tick
        await rodar(app2, servicos)
        await app2.tasks["ia:reaper_lease"].defer_async(timestamp=int(time.time()))
        await rodar(app2, servicos)
        await fila.enfileirar_turno(app2, caso.atendimento_id, caso.chat_id)  # o cliente escreve: o turno do chat tem de sair
        conn_super.execute(
            "UPDATE procrastinate.procrastinate_jobs SET scheduled_at = now() - interval '1 second' WHERE task_name = 'ia:turno'"
        )
        await rodar(app2, servicos)

    assert [j[1] for j in jobs_por_status(conn_super, "ia:retomar")] == ["failed"], "o job preso foi dado como falho"
    assert [(lease.atendimento_id, lease.acao) for lease in chamadas.leases] == [(caso.atendimento_id, "retomada_perdida")], (
        "o reaper_lease volta a enxergar o chat e devolve o lead"
    )
    assert chamadas.turnos == [caso.atendimento_id], "e o turno do cliente sai"


# --- o contrato geral da periódica ----------------------------------------------------------------------------------------------------------


async def test_jobs_presos_libera_o_lock_do_chat_de_qualquer_tarefa_e_so_dos_mortos(conninfo_app, conn_super, banco, relogio):
    morto, vivo = novo_worker(conn_super, 600), novo_worker(conn_super, 5)
    chat_a, chat_b, chat_c = hex24(), hex24(), hex24()
    preso_turno = inserir_job(conn_super, "ia:turno", f"turno:{chat_a}", "doing", morto, lock=f"chat:{chat_a}")
    preso_lembrete = inserir_job(conn_super, "ia:lembrete", f"lembrete_exec:{uuid.uuid4()}:1", "doing", morto, lock=f"chat:{chat_b}")
    sem_worker = inserir_job(
        conn_super, "ia:iniciar", f"iniciar:{uuid.uuid4()}", "doing", None, lock=f"chat:{chat_c}"
    )  # worker podado (SET NULL)
    rodando = inserir_job(conn_super, "ia:turno", f"turno:{hex24()}", "doing", vivo, lock=f"chat:{hex24()}")
    esperando = inserir_job(conn_super, "ia:turno", f"turno:{hex24()}", "todo", None, lock=f"chat:{hex24()}")
    app = criar(conninfo_app)
    async with app.open_async():
        liberados = await fila.liberar_jobs_presos(app)
    assert sorted(liberados) == sorted([preso_turno, preso_lembrete, sem_worker])
    assert [_status(conn_super, j) for j in (preso_turno, preso_lembrete, sem_worker)] == ["failed"] * 3
    assert (_status(conn_super, rodando), _status(conn_super, esperando)) == ("doing", "todo"), "worker vivo e job na fila não são tocados"
    # o chat voltou a andar: o próximo job do chat A sai no fetch (antes, o `doing` do morto o segurava)
    inserir_job(conn_super, "ia:turno", f"turno2:{chat_a}", "todo", None, lock=f"chat:{chat_a}")
    buscados = []
    while (linha := conn_super.execute("SELECT id, lock FROM procrastinate.procrastinate_fetch_job_v2(NULL, NULL)").fetchone())[
        0
    ] is not None:
        buscados.append(linha[1])
    assert f"chat:{chat_a}" in buscados


async def test_sem_job_preso_a_periodica_nao_faz_nada(conninfo_app, conn_super):
    app = criar(conninfo_app)
    async with app.open_async():
        assert await fila.liberar_jobs_presos(app) == []


def test_jobs_presos_e_periodica_por_minuto_e_nao_empilha():
    app = criar("host=h dbname=d user=u", com_periodicas=True)
    registradas = {pt.task.name: pt.cron for pt in app.periodic_registry.periodic_tasks.values()}
    assert registradas["ia:jobs_presos"] == "* * * * *"
    assert croniter(registradas["ia:jobs_presos"], datetime(2026, 11, 12, 22, 0, tzinfo=UTC)).get_next(datetime) == datetime(
        2026, 11, 12, 22, 1, tzinfo=UTC
    )
    assert app.tasks["ia:jobs_presos"].queueing_lock == "jobs_presos", "periódicas atrasadas não empilham"


# --- revisão automática: margem para job de worker podado e UPDATE atômico ---------------------------------------------------------------------


def _evento_started(conn, job_id: int, segundos_atras: int) -> None:
    conn.execute(
        "INSERT INTO procrastinate.procrastinate_events (job_id, type, at) VALUES (%s, 'started', now() - make_interval(secs => %s))",
        (job_id, segundos_atras),
    )


async def test_job_de_worker_podado_so_e_preso_depois_da_margem_desde_o_started(conninfo_app, conn_super):
    """O Procrastinate poda o worker com `stalled_worker_timeout` (30 s) e o job fica com `worker_id` NULL: um worker só LENTO não pode ter o job
    dado como preso antes da margem. Com `get_stalled_jobs` (NULL = morto na hora) o job recém-podado era falhado no primeiro tick."""
    recente = inserir_job(conn_super, "ia:turno", f"turno:{hex24()}", "doing", None, lock=f"chat:{hex24()}")
    velho = inserir_job(conn_super, "ia:turno", f"turno:{hex24()}", "doing", None, lock=f"chat:{hex24()}")
    _evento_started(conn_super, recente, int(HEARTBEAT_PRESO_S) - 20)  # começou há 40 s: ainda dentro da margem
    _evento_started(conn_super, velho, int(HEARTBEAT_PRESO_S) + 20)
    app = criar(conninfo_app)
    async with app.open_async():
        assert await fila.liberar_jobs_presos(app) == [velho]
    assert (_status(conn_super, recente), _status(conn_super, velho)) == ("doing", "failed")


async def test_o_update_reconfere_o_predicado_na_escrita_job_que_acabou_no_meio_nao_vira_erro(conninfo_app, conn_super, conn_app):
    """Corrida real: um worker «morto» (batimento velho) termina o job e o confirma ENQUANTO a periódica escreve. Ler e depois `finish_job`
    levantava «Job was not found or not in doing»; um só UPDATE com o predicado reavaliado na linha nova não toca em job `succeeded`."""
    morto = novo_worker(conn_super, 600)
    job = inserir_job(conn_super, "ia:turno", f"turno:{hex24()}", "doing", morto, lock=f"chat:{hex24()}")
    conn_olhar = (
        conn_app  # outra conexão, fora da transação: `pg_stat_activity` é um instantâneo por transação (a do `conn_super` ficaria velha)
    )
    app = criar(conninfo_app)
    async with app.open_async():
        with conn_super.transaction():  # o worker confirma o job (sem commit ainda): a linha fica travada para a periódica
            conn_super.execute("UPDATE procrastinate.procrastinate_jobs SET status = 'succeeded' WHERE id = %s", (job,))
            tarefa = asyncio.create_task(fila.liberar_jobs_presos(app))
            await ff.esperar(
                lambda: (
                    conn_olhar.execute(
                        "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock' AND query LIKE '%procrastinate_jobs j%SET status = ''failed''%'"
                    ).fetchone()[0]
                    == 1
                ),
                limite_s=15,
            )  # a periódica já está na fila da linha
        liberados = await asyncio.wait_for(tarefa, 15)  # o commit liberou: o predicado é reavaliado na linha nova
    assert liberados == [] and _status(conn_super, job) == "succeeded"


async def test_worker_com_batimento_fresco_nunca_e_tocado_mesmo_sem_started(conninfo_app, conn_super):
    vivo = novo_worker(conn_super, 5)
    job = inserir_job(conn_super, "ia:turno", f"turno:{hex24()}", "doing", vivo, lock=f"chat:{hex24()}")
    _evento_started(conn_super, job, 3600)  # roda há uma hora, mas o worker bate o coração: é um turno lento, não um preso
    app = criar(conninfo_app)
    async with app.open_async():
        assert await fila.liberar_jobs_presos(app) == []
    assert _status(conn_super, job) == "doing"


# --- a vigia do worker: perdeu a linha ou o batimento ⇒ aborta os jobs em voo ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("existe", "idade", "sem_resposta", "motivo"),
    [
        (False, None, 0.0, "linha_sumiu"),
        (True, 10.0, 0.0, None),
        (True, 39.9, 0.0, None),
        (True, 40.0, 0.0, "batimento_velho"),
        (True, 400.0, 0.0, "batimento_velho"),
        (True, None, 39.9, None),  # leitura falhando, ainda dentro da tolerância
        (True, None, 40.0, "banco_inalcancavel"),
        (False, 100.0, 100.0, "linha_sumiu"),  # a linha sumida vale primeiro
    ],
)
def test_motivo_de_abortar(existe, idade, sem_resposta, motivo):
    assert motivo_de_abortar(existe=existe, idade_s=idade, sem_resposta_ha_s=sem_resposta, tolerancia_s=40.0) == motivo


def test_o_worker_se_aborta_antes_de_a_fila_dar_o_job_por_morto():
    assert 0 < TOLERANCIA_VIGIA_S < HEARTBEAT_PRESO_S, "senão a fila liberaria o chat com o job superado ainda enviando"
    assert HEARTBEAT_PRESO_S == 60 and TOLERANCIA_VIGIA_S == 40


class _TurnoQueNaoAcaba:
    """`processar_turno` que fica rodando até ser cancelado, e registra o cancelamento."""

    def __init__(self) -> None:
        self.rodando = asyncio.Event()
        self.cancelado = False

    async def __call__(self, atendimento_id: uuid.UUID) -> None:
        self.rodando.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            self.cancelado = True
            raise


async def _subir_worker_com_turno_em_voo(banco, conninfo_app, conn_super, relogio, **opcoes):
    turno = _TurnoQueNaoAcaba()
    servicos = montar_servicos(banco, relogio, Chamadas(), processar_turno=turno)
    app = criar(conninfo_app)
    await app.open_async()
    await fila.enfileirar_turno(app, uuid.uuid4(), hex24(), rajada_s=0)
    worker = asyncio.create_task(
        fila.rodar_worker(app, servicos, wait=True, install_signal_handlers=False, fetch_job_polling_interval=0.05, **opcoes)
    )
    await asyncio.wait_for(turno.rodando.wait(), 15)
    return app, turno, worker


@pytest.mark.parametrize("como", ["linha_sumiu", "batimento_velho"])
async def test_worker_que_perde_a_linha_ou_o_batimento_aborta_o_job_em_voo_e_sai_com_erro(banco, conninfo_app, conn_super, relogio, como):
    app, turno, worker = await _subir_worker_com_turno_em_voo(
        banco, conninfo_app, conn_super, relogio, vigia_intervalo_s=0.1, vigia_tolerancia_s=5.0, update_heartbeat_interval=3600
    )
    try:
        assert not worker.done() and not turno.cancelado, "com o batimento fresco a vigia não faz nada"
        if como == "linha_sumiu":
            conn_super.execute("DELETE FROM procrastinate.procrastinate_workers")  # outro worker o podou
        else:
            conn_super.execute("UPDATE procrastinate.procrastinate_workers SET last_heartbeat = now() - interval '100 seconds'")
        with pytest.raises(WorkerPerdeuOBatimento, match=como):
            await asyncio.wait_for(worker, 15)
        assert turno.cancelado, "o job em voo foi abortado: não segue enviando com o chat já liberado para outro"
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
        await app.close_async()


async def test_worker_com_o_banco_inalcancavel_se_aborta_depois_da_tolerancia():
    class AppSemBanco:
        class connector:
            @staticmethod
            async def execute_query_all_async(*_: object, **__: object) -> list[dict[str, float]]:
                raise OSError("sem rede")

    class WorkerFalso:
        worker_id = 7
        shutdown_graceful_timeout: float | None = None
        parado = False

        def stop(self) -> None:
            self.parado = True

    worker = WorkerFalso()
    motivo = await asyncio.wait_for(vigiar_batimento(AppSemBanco(), worker, intervalo_s=0.01, tolerancia_s=0.1), 5)  # type: ignore[arg-type]
    assert motivo == "banco_inalcancavel" and worker.parado and worker.shutdown_graceful_timeout == 0
