"""Tarefas da B1.6b na fila de verdade (Postgres descartável): `repasse` se reagenda com o mesmo `desde`; periódicas registradas."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ia_atendimento import fila
from ia_atendimento.repasse import Reagendar
from tests import fixtures_fila as ff
from tests.fixtures_fila import Chamadas, hex24, jobs_por_status, montar_servicos

conn_app, conn_super, relogio, conninfo_app = ff.conn_app, ff.conn_super, ff.relogio, ff.conninfo_app

pytestmark = pytest.mark.banco


def test_periodicas_da_b16b_registradas():
    app = fila.criar_app("host=h dbname=d user=u", com_periodicas=True)
    crons = {pt.task.name: pt.cron for pt in app.periodic_registry.periodic_tasks.values()}
    assert crons["ia:reaper_ledger"] == "* * * * *" and crons["ia:publicar_espelho"] == "* * * * *"


async def test_repasse_se_reagenda_com_o_mesmo_desde(banco, conninfo_app, conn_super, relogio):
    desde = datetime(2026, 11, 20, 14, 0, tzinfo=UTC)
    vistos = []

    async def repassar(atd, d):
        vistos.append((atd, d))
        return Reagendar(30, d or desde) if len(vistos) == 1 else None

    servicos = montar_servicos(banco, relogio, Chamadas(), repassar=repassar)
    app = fila.criar_app(conninfo_app, com_periodicas=False)
    atd, chat = uuid.uuid4(), hex24()
    async with app.open_async():
        await fila.enfileirar_repasse(app, atd, chat)
        await app.run_worker_async(wait=False, install_signal_handlers=False, additional_context={"servicos": servicos},
                                   fetch_job_polling_interval=0.05)  # fmt: skip
    assert vistos == [(atd, None)]
    jobs = jobs_por_status(conn_super, "ia:repasse")
    assert [j[1] for j in jobs] == ["succeeded", "todo"] and jobs[1][2:] == (f"chat:{chat}", f"repasse:{atd}")
    args = conn_super.execute("SELECT args FROM procrastinate.procrastinate_jobs WHERE status = 'todo'").fetchone()[0]
    assert args["desde"] == desde.isoformat()
