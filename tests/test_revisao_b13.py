"""Achados da revisão de contexto limpo da B1.3 (`docs/REVISAO-B1.3-3010.md`): um teste por achado, escritos para reprovar no código revisado."""

from __future__ import annotations

import threading
import time
import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from ia_atendimento import fila, jobs
from ia_atendimento.chave import LeitorConfig, ValorInvalido, config_vigente, registrar_config
from ia_atendimento.prontidao import ler_prontidao, readyz_por_dsn
from ia_atendimento.relogio import RelogioFalso
from tests import fixtures_fila as ff
from tests.fixtures_fila import Chamadas, abrir, hex24, inserir_atendimento, jobs_por_status, montar_servicos, tornar_vencidos
from tests.test_fila import criar, rodar

conn_app, conn_super, relogio, conninfo_app = ff.conn_app, ff.conn_super, ff.relogio, ff.conninfo_app

pytestmark = pytest.mark.banco


def U(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


# --- A1: lembrete futuro não pode travar os turnos do chat -------------------------------------------------------------------------------


async def test_a1_turno_nao_espera_lembrete_futuro(conninfo_app, conn_super, banco, relogio):
    chamadas = Chamadas()
    app, chat, a1, a2 = criar(conninfo_app), hex24(), uuid.uuid4(), uuid.uuid4()
    async with app.open_async():
        await fila.agendar_lembrete(app, a1, chat, 1, datetime.now(UTC) + timedelta(hours=4))
        await fila.enfileirar_turno(app, a2, chat)
        tornar_vencidos(conn_super)  # só a rajada de 3 s vence; o lembrete de 4 h continua no futuro
        await rodar(app, montar_servicos(banco, relogio, chamadas))
    assert chamadas.turnos == [a2], "turno do cliente travado atrás do lembrete futuro do mesmo chat"
    futuros = conn_super.execute("SELECT task_name, lock FROM procrastinate.procrastinate_jobs WHERE status = 'todo'").fetchall()
    assert futuros == [("ia:alarme_lembrete", None)]  # o alarme agendado não leva lock


async def test_a1_alarme_ao_disparar_enfileira_o_lembrete_com_lock(conninfo_app, conn_super, banco, relogio):
    chamadas = Chamadas()
    app, chat, aid = criar(conninfo_app), hex24(), uuid.uuid4()
    async with app.open_async():
        await fila.agendar_lembrete(app, aid, chat, 2, datetime.now(UTC) + timedelta(hours=4))
        conn_super.execute("UPDATE procrastinate.procrastinate_jobs SET scheduled_at = now() - interval '1 second'")
        await rodar(app, montar_servicos(banco, relogio, chamadas))
    por_tarefa = {t: (s, lk, ql) for t, s, lk, ql in jobs_por_status(conn_super)}
    assert por_tarefa["ia:alarme_lembrete"][0] == "succeeded"
    assert por_tarefa["ia:lembrete"][1:] == (f"chat:{chat}", f"lembrete_exec:{aid}:2")  # com lock, sem agendamento (roda já)


# --- A2: AlreadyEnqueued dentro da transação do chamador -----------------------------------------------------------------------------------


async def test_a2_already_enqueued_na_mesma_transacao_nao_perde_a_gravacao(conninfo_app, conn_super):
    app, chat, aid = criar(conninfo_app), hex24(), uuid.uuid4()
    conn_super.execute("CREATE TABLE public.msg_teste (id int)")
    conn_super.execute("GRANT ALL ON public.msg_teste TO ia_app_a")
    async with app.open_async():
        assert await fila.enfileirar_turno(app, aid, chat) is not None  # 1ª mensagem da rajada, já commitada
        async with await psycopg.AsyncConnection.connect(fila.conninfo_da_fila(conninfo_app)) as conexao, conexao.transaction():
            await conexao.execute("INSERT INTO public.msg_teste VALUES (2)")  # a 2ª mensagem, gravada na MESMA transação do enqueue
            assert await fila.enfileirar_turno(app, aid, chat, conexao=conexao) is None
            await conexao.execute("SELECT 1")  # a transação segue utilizável (antes: InFailedSqlTransaction)
    assert conn_super.execute("SELECT count(*) FROM public.msg_teste").fetchone()[0] == 1
    assert [j[1] for j in jobs_por_status(conn_super)] == ["todo"]


# --- A3: a tarefa das 20:15 decide pelo tick, tem retry e reconciliação ----------------------------------------------------------------------

TICK_2015 = int(U(2026, 11, 12, 23, 15).timestamp())  # 20:15 em São Paulo


def test_a3_bloqueio_atrasado_ainda_grava_porque_decide_pelo_tick(conn_app, banco):
    atrasado = montar_servicos(banco, RelogioFalso(U(2026, 11, 13, 0, 5)), Chamadas())  # 21:05 em SP, job do tick das 20:15
    assert jobs.executar_bloqueio_diario(atrasado, TICK_2015) is True
    assert config_vigente(conn_app, "bloqueio_entrada").valor is True


def test_a3_tick_fora_das_20h_ou_velho_demais_nao_grava(conn_app, banco):
    defasado = int(U(2026, 11, 13, 0, 15).timestamp())  # tick às 21:15 locais: cron errado
    with pytest.raises(jobs.HorarioInesperado):
        jobs.executar_bloqueio_diario(montar_servicos(banco, RelogioFalso(U(2026, 11, 13, 0, 16)), Chamadas()), defasado)
    de_ontem = montar_servicos(banco, RelogioFalso(U(2026, 11, 13, 12, 0)), Chamadas())  # 09:00 do dia seguinte: o Danilo já abriu
    assert jobs.executar_bloqueio_diario(de_ontem, TICK_2015) is False
    assert config_vigente(conn_app, "bloqueio_entrada").versao == 1


def test_a3_tarefa_das_2015_tem_retry():
    app = criar("host=h dbname=d user=u")
    estrategia = app.tasks["ia:bloqueio_2015"].retry_strategy
    assert estrategia is not None and estrategia.max_attempts == 5


def test_a3_reconciliacao_fecha_a_casa_que_a_tarefa_perdeu(conn_app, banco):
    def reconciliar(instante: datetime) -> bool:
        return jobs.reconciliar_bloqueio_diario(montar_servicos(banco, RelogioFalso(instante), Chamadas()))

    assert reconciliar(U(2026, 11, 12, 22, 0)) is False  # 19:00 locais: ainda não passou das 20:15
    assert reconciliar(U(2026, 11, 13, 11, 0)) is False  # 08:00 locais: depois das 07:45 quem abre é o Danilo
    assert reconciliar(U(2026, 11, 13, 0, 0)) is True  # 21:00 locais, false desde antes das 20:15: a tarefa perdeu o tick
    assert config_vigente(conn_app, "bloqueio_entrada").valor is True
    assert reconciliar(U(2026, 11, 13, 0, 5)) is False  # já está true

    # o Danilo abre à noite de propósito (depois do tick): a reconciliação respeita
    registrar_config(conn_app, "bloqueio_entrada", False, "danilo", relogio=RelogioFalso(U(2026, 11, 14, 1, 0)))  # 22:00 de 13/11
    assert reconciliar(U(2026, 11, 14, 2, 0)) is False  # 23:00 de 13/11
    assert config_vigente(conn_app, "bloqueio_entrada").valor is False


def test_a3_reconciliacao_esta_agendada_como_periodica():
    app = criar("host=h dbname=d user=u", com_periodicas=True)
    assert "ia:reconciliar_bloqueio" in {pt.task.name for pt in app.periodic_registry.periodic_tasks.values()}


# --- A4: job único de 20/11 não renasce a cada boot --------------------------------------------------------------------------------------------


async def test_a4_job_de_2011_nao_e_reenfileirado_depois_de_executar(conninfo_app, conn_super, banco):
    app = criar(conninfo_app)
    async with app.open_async():
        assert await fila.agendar_bloqueio_dataprev(app, RelogioFalso(U(2026, 11, 12, 12, 0))) is not None
        tornar_vencidos(conn_super)
        conn_super.execute("UPDATE procrastinate.procrastinate_jobs SET scheduled_at = now() - interval '1 second'")
        await rodar(app, montar_servicos(banco, RelogioFalso(U(2026, 11, 21, 0, 51)), Chamadas()))
        segundo = await fila.agendar_bloqueio_dataprev(app, RelogioFalso(U(2026, 11, 21, 1, 0)))  # novo boot, ainda antes de 23/11 06:00
    assert segundo is None
    assert [j[1] for j in jobs_por_status(conn_super)] == ["succeeded"]


# --- A5: cache de config ---------------------------------------------------------------------------------------------------------------------


def test_a5_gravar_bloqueio_atualiza_o_cache_do_mesmo_processo(conn_app, banco, relogio):
    servicos = montar_servicos(banco, relogio, Chamadas())
    leitor = servicos.leitor_config
    assert leitor.valor(conn_app, "bloqueio_entrada") is False
    relogio.avancar(seconds=1)
    assert jobs.gravar_bloqueio_entrada(servicos, "tarefa:x") is True
    assert leitor.valor(conn_app, "bloqueio_entrada") is True


def test_a5_rollback_do_chamador_nao_envenena_o_cache(conn_app, relogio):
    leitor = LeitorConfig(relogio)
    assert leitor.valor(conn_app, "max_abertos") == 10
    conn_app.execute("BEGIN")
    leitor.registrar(conn_app, "max_abertos", 99, "x")
    conn_app.execute("ROLLBACK")
    assert leitor.valor(conn_app, "max_abertos") == 10


def test_a5_chave_nova_nao_fica_escondida_por_cache_de_none(conn_app, relogio):
    leitor = LeitorConfig(relogio)
    assert leitor.vigente(conn_app, "verificador_modelo") is None
    registrar_config(conn_app, "verificador_modelo", "deepseek-v4p1-flash-1017", "x", relogio=relogio)
    assert leitor.vigente(conn_app, "verificador_modelo").valor == "deepseek-v4p1-flash-1017"


# --- A6: write skew nos limites cruzados -----------------------------------------------------------------------------------------------------


def test_a6_limites_cruzados_com_escritas_concorrentes(banco, relogio):
    a, b = abrir(banco), abrir(banco)
    resultado: dict[str, object] = {}
    a.execute("BEGIN")
    registrar_config(a, "agenda_max_dia", 9, "A", relogio=relogio)  # max_disparos_dia vigente é 10: vale

    def escrever_b() -> None:
        try:
            resultado["b"] = registrar_config(b, "max_disparos_dia", 6, "B", relogio=relogio)
        except ValorInvalido as erro:
            resultado["b"] = erro

    fio = threading.Thread(target=escrever_b)
    fio.start()
    time.sleep(0.5)  # B precisa esperar a trava do par, não ler o 5 antigo
    a.execute("COMMIT")
    fio.join(10)
    vigente = {n: config_vigente(a, n).valor for n in ("agenda_max_dia", "max_disparos_dia")}
    assert vigente["agenda_max_dia"] <= vigente["max_disparos_dia"]
    assert isinstance(resultado["b"], ValorInvalido)  # B viu o 9 de A depois do commit e foi recusada
    a.close()
    b.close()


# --- A7: reaper e turno já na fila -------------------------------------------------------------------------------------------------------------


async def test_a7_reaper_nao_repassa_chat_com_turno_todo_vencido(banco, relogio, conn_super):
    chamadas, agora, chat = Chamadas(), relogio.agora(), hex24()
    inserir_atendimento(
        conn_super, estado="aberto", chat_id=chat, iniciado_em=agora - timedelta(minutes=20), lease_ate=agora - timedelta(seconds=1)
    )
    conn_super.execute(
        "INSERT INTO procrastinate.procrastinate_jobs (queue_name, task_name, lock, status, scheduled_at) "
        "VALUES ('default', 'ia:turno', %s, 'todo', now() - interval '1 second')",
        (f"chat:{chat}",),
    )
    assert await jobs.executar_reaper_lease(montar_servicos(banco, relogio, chamadas)) == 0
    assert chamadas.leases == []


# --- A8: readyz ------------------------------------------------------------------------------------------------------------------------------------


def test_a8_esquema_ausente_vira_falha_dura_e_nao_excecao(conninfo_app, conn_super):
    conn_super.execute("DROP TABLE procrastinate.procrastinate_workers CASCADE")
    p = readyz_por_dsn(conninfo_app)
    assert not p.pronto and p.falhas_duras == ("erro_de_consulta",)


def test_a8_defasagem_de_relogio_entre_hosts_nao_derruba_a_prontidao(conn_app, conn_super):
    """Batimento e agendamento são do relógio do BANCO e comparados com o `now()` do banco, não com o da aplicação."""
    conn_super.execute("INSERT INTO procrastinate.procrastinate_workers (last_heartbeat) VALUES (now() - interval '5 seconds')")
    for tipo in ("roteiro", "regras", "catalogo", "motor"):
        conn_super.execute("INSERT INTO ia.artefato_versao (tipo, numero, descricao, aprovado_por) VALUES (%s, 1, 'v1', 'teste')", (tipo,))
    assert ler_prontidao(conn_app).pronto  # a aplicação não passa relógio algum: nada a defasar


def test_a8_job_falhando_em_massa_e_sinal(conn_app, conn_super):
    conn_super.execute("INSERT INTO procrastinate.procrastinate_workers (last_heartbeat) VALUES (now())")
    for tipo in ("roteiro", "regras", "catalogo", "motor"):
        conn_super.execute("INSERT INTO ia.artefato_versao (tipo, numero, descricao, aprovado_por) VALUES (%s, 1, 'v1', 'teste')", (tipo,))

    def falhar(n: int) -> None:
        for _ in range(n):
            job = conn_super.execute(
                "INSERT INTO procrastinate.procrastinate_jobs (queue_name, task_name, status) VALUES ('default', 'ia:turno', 'failed') RETURNING id"
            ).fetchone()[0]
            conn_super.execute(
                "INSERT INTO procrastinate.procrastinate_events (job_id, type, at) VALUES (%s, 'failed', now() - interval '2 minutes')",
                (job,),
            )

    falhar(3)
    p = ler_prontidao(conn_app)
    assert p.falhados_15min == 3 and p.pronto  # mole
    falhar(20)
    p = ler_prontidao(conn_app)
    assert p.falhados_15min == 23 and p.falhas_duras == ("jobs_falhando",)
