"""Jobs presos (R1-01 da revisão 1 da B5.7b): `doing` de worker morto segura o `lock=chat:` de QUALQUER tarefa até alguém dá-lo como falho.

Sem a periódica `jobs_presos`, um `SIGKILL` no meio da volta (deploy do Coolify) deixa o lead `pausado` para sempre: o job `retomar` fica `doing` (com
`worker_id` NULL, o worker novo poda o morto), o `reaper_lease` não enxerga o chat (`NOT EXISTS job doing no chat`) e o turno do cliente fica `todo`.
"""

from __future__ import annotations

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
