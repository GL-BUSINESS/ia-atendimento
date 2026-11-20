"""Fila Procrastinate de verdade contra o Postgres descartável: rajada, trava por chat, mesma transação, bloqueio das 20:15 e job único de 20/11."""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from datetime import UTC, date, datetime, timedelta

import psycopg
import pytest
from croniter import croniter

from ia_atendimento import fila
from ia_atendimento.calendario import HORA_BLOQUEIO_ENTRADA, cron_utc
from ia_atendimento.chave import config_vigente, registrar_config
from ia_atendimento.relogio import RelogioFalso
from tests import fixtures_fila as ff
from tests.fixtures_fila import Chamadas, esperar, hex24, jobs_por_status, montar_servicos, tornar_vencidos

conn_app, conn_super, relogio, conninfo_app = ff.conn_app, ff.conn_super, ff.relogio, ff.conninfo_app

pytestmark = pytest.mark.banco


def criar(conninfo: str, **opcoes):
    return fila.criar_app(conninfo, com_periodicas=opcoes.pop("com_periodicas", False), **opcoes)


async def rodar(app, servicos, **opcoes) -> None:
    """Worker que processa o que está vencido e sai (`wait=False`)."""
    await app.run_worker_async(
        wait=False, install_signal_handlers=False, additional_context={"servicos": servicos}, fetch_job_polling_interval=0.05, **opcoes
    )


# --- conexão da fila ----------------------------------------------------------------------------------------------------------------------


def test_conninfo_da_fila_poe_search_path_por_options_sem_perder_o_resto():
    com_dialeto = fila.conninfo_da_fila("postgresql+psycopg://ia_app_a:segredo@127.0.0.1:5432/ia?options=-c%20statement_timeout%3D5000")
    partes = psycopg.conninfo.conninfo_to_dict(com_dialeto)
    assert partes["options"] == "-c statement_timeout=5000 -c search_path=procrastinate,public"
    assert (partes["host"], partes["user"], partes["dbname"]) == ("127.0.0.1", "ia_app_a", "ia")
    simples = psycopg.conninfo.conninfo_to_dict(fila.conninfo_da_fila("host=h dbname=d user=u"))
    assert simples["options"] == "-c search_path=procrastinate,public"
    with pytest.raises(ValueError) as erro:
        fila.conninfo_da_fila("isto não é uma url com segredo123")
    assert "segredo123" not in str(erro.value)


async def test_fila_funciona_com_o_login_do_runtime_e_search_path_por_options(conninfo_app, conn_super):
    """Funções e gatilhos do Procrastinate usam nomes sem schema: sem `options` o defer abaixo falharia."""
    app = criar(conninfo_app)
    async with app.open_async():
        job = await app.tasks["ia:turno"].configure(lock="chat:x").defer_async(atendimento_id=str(uuid.uuid4()))
    assert job > 0
    assert [j[:2] for j in jobs_por_status(conn_super)] == [("ia:turno", "todo")]


# --- rajada e trava por chat ---------------------------------------------------------------------------------------------------------------


async def test_rajada_um_turno(conninfo_app, conn_super, banco, relogio):
    chamadas = Chamadas()
    servicos = montar_servicos(banco, relogio, chamadas)
    app = criar(conninfo_app)
    atendimento, chat = uuid.uuid4(), hex24()
    async with app.open_async():
        primeiro = await fila.enfileirar_turno(app, atendimento, chat)
        assert primeiro is not None
        for _ in range(2):  # 2ª e 3ª mensagens da rajada, no meio do intervalo de 3 s
            await asyncio.sleep(0.2)
            assert await fila.enfileirar_turno(app, atendimento, chat) is None  # AlreadyEnqueued engolido
        todo = conn_super.execute(
            "SELECT count(*), min(scheduled_at - now()), max(scheduled_at - now()) FROM procrastinate.procrastinate_jobs WHERE status = 'todo'"
        ).fetchone()
        assert todo[0] == 1  # três mensagens, um job
        assert timedelta(seconds=2) < todo[1] <= todo[2] <= timedelta(seconds=3)  # agendado para ~3 s à frente, não já
        assert jobs_por_status(conn_super)[0][2:] == (f"chat:{chat}", f"turno:{chat}")

        await rodar(app, servicos)  # ainda dentro dos 3 s: nada a fazer
        assert chamadas.turnos == []
        tornar_vencidos(conn_super)
        await rodar(app, servicos)
    assert chamadas.turnos == [atendimento]  # UM turno consome as três
    assert [j[1] for j in jobs_por_status(conn_super, "ia:turno")] == ["succeeded"]


async def test_mensagem_depois_do_turno_em_curso_enfileira_outro(conninfo_app, conn_super, banco, relogio):
    """O `queueing_lock` só vale para `todo`: com o turno já em execução, a mensagem nova ganha o seu job (o lock do chat o segura)."""
    app = criar(conninfo_app)
    chat = hex24()
    async with app.open_async():
        assert await fila.enfileirar_turno(app, uuid.uuid4(), chat) is not None
        conn_super.execute("UPDATE procrastinate.procrastinate_jobs SET status = 'doing'")
        assert await fila.enfileirar_turno(app, uuid.uuid4(), chat) is not None
    assert [j[1] for j in jobs_por_status(conn_super)] == ["doing", "todo"]


async def test_lock_por_chat_serializa(conninfo_app, conn_super, banco, relogio):
    chamadas = Chamadas()
    eventos: list[str] = []
    liberar_primeiro = asyncio.Event()

    async def turno_lento(atendimento_id: uuid.UUID) -> None:
        eventos.append(f"inicio:{atendimento_id}")
        if len(eventos) == 1:
            await liberar_primeiro.wait()
        eventos.append(f"fim:{atendimento_id}")

    servicos = montar_servicos(banco, relogio, chamadas, processar_turno=turno_lento)
    app = criar(conninfo_app)
    chat, a1, a2 = hex24(), uuid.uuid4(), uuid.uuid4()
    async with app.open_async():
        await fila.enfileirar_turno(app, a1, chat)
        tornar_vencidos(conn_super)
        worker = asyncio.create_task(
            app.run_worker_async(
                wait=True,
                install_signal_handlers=False,
                concurrency=4,
                fetch_job_polling_interval=0.05,
                additional_context={"servicos": servicos},
            )
        )
        await esperar(lambda: eventos == [f"inicio:{a1}"])  # o 1º começou e está preso
        await fila.enfileirar_turno(app, a2, chat)  # outro turno do MESMO chat, com o 1º em execução
        tornar_vencidos(conn_super)
        await asyncio.sleep(0.5)  # tempo de sobra para o worker (concurrency 4) pegar o 2º, se o lock deixasse
        assert eventos == [f"inicio:{a1}"], "o 2º turno do mesmo chat começou antes do 1º terminar"
        liberar_primeiro.set()
        await esperar(lambda: len(eventos) == 4)
        worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker
    assert eventos == [f"inicio:{a1}", f"fim:{a1}", f"inicio:{a2}", f"fim:{a2}"]


async def test_chats_diferentes_em_paralelo(conninfo_app, conn_super, banco, relogio):
    chamadas = Chamadas()
    iniciados: set[uuid.UUID] = set()

    async def turno_que_espera_o_outro(atendimento_id: uuid.UUID) -> None:
        iniciados.add(atendimento_id)
        await esperar(lambda: len(iniciados) == 2, limite_s=5)  # só termina se o outro chat também estiver rodando

    servicos = montar_servicos(banco, relogio, chamadas, processar_turno=turno_que_espera_o_outro)
    app = criar(conninfo_app)
    async with app.open_async():
        for _ in range(2):
            await fila.enfileirar_turno(app, uuid.uuid4(), hex24())
        tornar_vencidos(conn_super)
        await rodar(app, servicos, concurrency=2)
    assert [j[1] for j in jobs_por_status(conn_super)] == ["succeeded", "succeeded"]


async def test_enfileirar_na_mesma_transacao_some_se_a_transacao_desfaz(conninfo_app, conn_super):
    app = criar(conninfo_app)
    async with app.open_async(), await psycopg.AsyncConnection.connect(fila.conninfo_da_fila(conninfo_app)) as conexao:
        async with conexao.transaction(force_rollback=True):  # a gravação do passo falhou: o job vai junto
            await fila.enfileirar_turno(app, uuid.uuid4(), hex24(), conexao=conexao)
        assert jobs_por_status(conn_super) == []
        async with conexao.transaction():
            await fila.enfileirar_turno(app, uuid.uuid4(), hex24(), conexao=conexao)
    assert [j[1] for j in jobs_por_status(conn_super)] == ["todo"]


# --- tarefas de agenda e de lembrete --------------------------------------------------------------------------------------------------------


async def test_iniciar_e_lembrete_rodam_com_lock_do_chat(conninfo_app, conn_super, banco, relogio):
    chamadas = Chamadas()
    servicos = montar_servicos(banco, relogio, chamadas)
    app = criar(conninfo_app)
    atendimento, chat = uuid.uuid4(), hex24()
    from ia_atendimento.jobs import InstantaneoLembrete

    chamadas.instantaneos[atendimento] = InstantaneoLembrete(
        estado="aguardando_cliente",
        lembretes_enviados=0,
        lembretes_max=1,
        ultima_ia_em=relogio.agora() - timedelta(hours=4),
        ultimo_cliente_em=relogio.agora() - timedelta(hours=5),
    )
    async with app.open_async():
        await fila.enfileirar_iniciar(app, atendimento, chat)
        await fila.agendar_lembrete(app, atendimento, chat, 1, relogio.agora() + timedelta(hours=4))
        assert await fila.agendar_lembrete(app, atendimento, chat, 1, relogio.agora() + timedelta(hours=4)) is None  # mesmo lembrete: um só
        assert [(t, lk, ql) for t, _, lk, ql in jobs_por_status(conn_super)] == [
            ("ia:iniciar", f"chat:{chat}", f"iniciar:{atendimento}"),
            ("ia:alarme_lembrete", None, f"lembrete:{atendimento}:1"),  # o alarme agendado não leva lock (revisão A1)
        ]
        conn_super.execute("UPDATE procrastinate.procrastinate_jobs SET scheduled_at = now() - interval '1 second' WHERE status = 'todo'")
        await rodar(app, servicos)
    assert chamadas.iniciados == [atendimento]
    assert chamadas.lembretes == [(atendimento, 1, True)]


async def test_servico_nao_configurado_falha_de_forma_explicita(conninfo_app, conn_super):
    """Sem o serviço real (B1.6), o job falha alto: nunca finge que processou."""
    app = criar(conninfo_app)
    from ia_atendimento.jobs import Servicos

    async with app.open_async():
        await fila.enfileirar_turno(app, uuid.uuid4(), hex24())
        tornar_vencidos(conn_super)
        await rodar(app, Servicos(relogio=RelogioFalso(datetime(2026, 11, 17, 15, tzinfo=UTC)), abrir_conexao=lambda: None))
    assert [j[1] for j in jobs_por_status(conn_super)] == ["failed"]


# --- bloqueio programado -------------------------------------------------------------------------------------------------------------------


def test_tarefas_periodicas_registradas_com_o_cron_certo():
    app = criar("host=h dbname=d user=u", com_periodicas=True)
    registradas = {pt.task.name: pt.cron for pt in app.periodic_registry.periodic_tasks.values()}
    assert registradas["ia:bloqueio_2015"] == "15 23 * * *" == cron_utc(HORA_BLOQUEIO_ENTRADA, date(2026, 11, 12))
    assert {"ia:reaper_lease", "ia:expirar_parados", "ia:auditoria_pii", "ia:podar"} <= set(registradas)
    # 20:15 em SP é 23:15 UTC: a próxima execução depois de 12/11 22:00 UTC é 12/11 23:15 UTC
    proxima = croniter(registradas["ia:bloqueio_2015"], datetime(2026, 11, 12, 22, 0, tzinfo=UTC)).get_next(datetime)
    assert proxima == datetime(2026, 11, 12, 23, 15, tzinfo=UTC)


async def test_tarefa_das_2015_grava_bloqueio_entrada(conninfo_app, conn_app, conn_super, banco):
    relogio = RelogioFalso(datetime(2026, 11, 12, 23, 15, 1, tzinfo=UTC))  # 20:15 em São Paulo
    servicos = montar_servicos(banco, relogio, Chamadas())
    app = criar(conninfo_app)
    assert config_vigente(conn_app, "bloqueio_entrada").valor is False
    async with app.open_async():
        await app.tasks["ia:bloqueio_2015"].defer_async(timestamp=int(relogio.agora().timestamp()))
        await rodar(app, servicos)
    vigente = config_vigente(conn_app, "bloqueio_entrada")
    assert (vigente.valor, vigente.versao, vigente.publicado_por) == (True, 2, "tarefa:bloqueio_2015")

    # no dia seguinte, já com true: nada novo é gravado
    relogio.avancar(days=1)
    async with app.open_async():
        await app.tasks["ia:bloqueio_2015"].defer_async(timestamp=int(relogio.agora().timestamp()))
        await rodar(app, servicos)
    assert config_vigente(conn_app, "bloqueio_entrada").versao == 2

    # o Danilo abre às 07:45 (false); a tarefa do dia seguinte fecha de novo, e nenhuma versão false vem dela
    registrar_config(conn_app, "bloqueio_entrada", False, "danilo", relogio=relogio)
    relogio.avancar(days=1)
    async with app.open_async():
        await app.tasks["ia:bloqueio_2015"].defer_async(timestamp=int(relogio.agora().timestamp()))
        await rodar(app, servicos)
    historico = conn_super.execute(
        "SELECT versao, valor, publicado_por FROM ia.config_versao WHERE nome = 'bloqueio_entrada' ORDER BY versao"
    ).fetchall()
    assert [(v, val) for v, val, _ in historico] == [(1, False), (2, True), (3, False), (4, True)]
    assert {por for v, _, por in historico if por.startswith("tarefa:")} == {"tarefa:bloqueio_2015"}
    assert all(val is True for _, val, por in historico if por.startswith("tarefa:"))  # a tarefa nunca grava false


async def test_tarefa_das_2015_fora_do_horario_falha_e_nao_grava(conninfo_app, conn_app, conn_super, banco):
    """Se o horário de verão voltar e o cron ficar defasado, a tarefa não grava às 21:15: falha alto (a vigia da S2 alerta às 20:20)."""
    relogio = RelogioFalso(datetime(2026, 11, 13, 0, 15, tzinfo=UTC))  # 21:15 em SP
    app = criar(conninfo_app)
    async with app.open_async():
        await app.tasks["ia:bloqueio_2015"].defer_async(timestamp=1)
        await rodar(app, montar_servicos(banco, relogio, Chamadas()))
    assert [j[1] for j in jobs_por_status(conn_super, "ia:bloqueio_2015")] == ["failed"]
    assert config_vigente(conn_app, "bloqueio_entrada").versao == 1


def _agendados(conn_super) -> list[tuple[datetime, str, str]]:
    return conn_super.execute(
        "SELECT scheduled_at, queueing_lock, status::text FROM procrastinate.procrastinate_jobs"
        " WHERE task_name = 'ia:bloqueio_dataprev' ORDER BY scheduled_at"
    ).fetchall()


async def test_job_mensal_da_dataprev_grava_bloqueio_e_deixa_o_do_mes_seguinte(conninfo_app, conn_app, conn_super, banco):
    """DEC-PIA-011: o job sai todo dia 20 às 21:50 (SP). O boot agenda o do mês e o do mês seguinte; ao rodar, o job agenda o próximo."""
    antes = RelogioFalso(datetime(2026, 11, 12, 12, 0, tzinfo=UTC))
    app = criar(conninfo_app)
    async with app.open_async():
        job = await fila.agendar_bloqueio_dataprev(app, antes)
        assert job is not None
        assert await fila.agendar_bloqueio_dataprev(app, antes) is None  # idempotente, mesmo chamando em todo boot
        assert [a[:2] for a in _agendados(conn_super)] == [
            (datetime(2026, 11, 21, 0, 50, tzinfo=UTC), "bloqueio_dataprev:2026-11-20"),  # 20/11 21:50 em São Paulo
            (datetime(2026, 12, 21, 0, 50, tzinfo=UTC), "bloqueio_dataprev:2026-12-20"),  # 20/12 21:50 em São Paulo
        ]

        # na hora: grava true e não encerra ninguém; a volta não é automática
        ativo = ff.inserir_atendimento(conn_super, estado="aberto")
        conn_super.execute(
            "UPDATE procrastinate.procrastinate_jobs SET scheduled_at = now() - interval '1 second' WHERE queueing_lock = %s",
            ("bloqueio_dataprev:2026-11-20",),
        )  # chegou 20/11 21:50
        na_hora = RelogioFalso(datetime(2026, 11, 21, 0, 51, tzinfo=UTC))
        await rodar(app, montar_servicos(banco, na_hora, Chamadas()))
    assert config_vigente(conn_app, "bloqueio_entrada").valor is True
    assert conn_super.execute("SELECT estado FROM ia.atendimento WHERE atendimento_id = %s", (ativo,)).fetchone()[0] == "aberto"
    assert [(a[1], a[2]) for a in _agendados(conn_super)] == [
        ("bloqueio_dataprev:2026-11-20", "succeeded"),
        ("bloqueio_dataprev:2026-12-20", "todo"),  # sempre há o do mês seguinte na fila
    ]

    # o de dezembro, ao rodar (21/12 00:51 UTC = 20/12 21:50 SP), fecha a entrada e deixa o de janeiro: a corrente não depende de boot
    registrar_config(conn_app, "bloqueio_entrada", False, "ti", relogio=RelogioFalso(datetime(2026, 11, 23, 10, 0, tzinfo=UTC)))
    async with app.open_async():
        conn_super.execute(
            "UPDATE procrastinate.procrastinate_jobs SET scheduled_at = now() - interval '1 second' WHERE queueing_lock = %s",
            ("bloqueio_dataprev:2026-12-20",),
        )
        await rodar(app, montar_servicos(banco, RelogioFalso(datetime(2026, 12, 21, 0, 51, tzinfo=UTC)), Chamadas()))
    assert config_vigente(conn_app, "bloqueio_entrada").valor is True
    assert [(a[1], a[2]) for a in _agendados(conn_super)] == [
        ("bloqueio_dataprev:2026-11-20", "succeeded"),
        ("bloqueio_dataprev:2026-12-20", "succeeded"),
        ("bloqueio_dataprev:2027-01-20", "todo"),
    ]
