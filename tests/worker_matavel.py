"""Worker REAL em processo à parte cuja volta trava DEPOIS do CAS `confirmado → disparado`; o teste dá `SIGKILL` nele (deploy no meio da volta).

Não é um teste (o pytest não o coleta): `tests/test_jobs_presos.py` o inicia com `subprocess`, espera o marcador e o mata. Configuração por ambiente:
`WORKER_MATAVEL_CONNINFO`, `WORKER_MATAVEL_AGORA` (ISO 8601 com fuso, o relógio do worker) e `WORKER_MATAVEL_MARCADOR` (arquivo que ele cria ao chegar
na volta, com o id do agendamento).
"""

import asyncio
import os
from contextlib import contextmanager
from datetime import datetime

import psycopg

from ia_atendimento import fila
from ia_atendimento.chave import LeitorConfig
from ia_atendimento.jobs import Servicos
from ia_atendimento.relogio import RelogioFalso

conninfo = os.environ["WORKER_MATAVEL_CONNINFO"]
relogio = RelogioFalso(datetime.fromisoformat(os.environ["WORKER_MATAVEL_AGORA"]))
marcador = os.environ["WORKER_MATAVEL_MARCADOR"]


@contextmanager
def abrir():
    with psycopg.connect(fila.conninfo_da_fila(conninfo), autocommit=True, connect_timeout=5) as conn:
        yield conn


async def volta(v):
    with open(marcador, "w") as f:
        f.write(str(v.agendamento_id))
    await asyncio.sleep(3600)  # a volta «demora»: o teste mata o processo aqui


servicos = Servicos(relogio=relogio, abrir_conexao=abrir, leitor_config=LeitorConfig(relogio), retomar_atendimento=volta)
app = fila.criar_app(conninfo, com_periodicas=False)


async def main():
    async with app.open_async():
        await app.run_worker_async(
            wait=True,
            install_signal_handlers=False,
            additional_context={"servicos": servicos},
            fetch_job_polling_interval=0.2,
            concurrency=3,
        )


asyncio.run(main())
