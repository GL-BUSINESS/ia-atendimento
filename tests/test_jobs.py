"""Handlers dos jobs (sem a fila): lembrete, reaper de lease, bloqueio programado, poda, auditoria de PII e expiração."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from ia_atendimento import jobs
from ia_atendimento.calendario import carregar_calendario
from ia_atendimento.chave import config_vigente
from ia_atendimento.jobs import Decisao, InstantaneoLembrete
from ia_atendimento.relogio import RelogioFalso
from tests import fixtures_fila as ff
from tests.fixtures_fila import Chamadas, hex24, inserir_atendimento, montar_servicos

conn_app, conn_super, relogio = ff.conn_app, ff.conn_super, ff.relogio

CAL = carregar_calendario(
    {"dias": {str(d): {"inicio": "08:00", "fim": "20:00"} for d in range(1, 7)}},
    {
        "domingos": True,
        "feriados": ["2026-11-02", "2026-11-20"],
        "janelas": [{"de": "2026-11-20T22:00:00-03:00", "ate": "2026-11-23T06:00:00-03:00", "motivo": "dataprev"}],
    },
)


def utc(d: int, h: int, m: int = 0, mes: int = 11) -> datetime:
    return datetime(2026, mes, d, h, m, tzinfo=UTC)


# --- lembrete (decisão pura) ---------------------------------------------------------------------------------------------------------------


def instantaneo(**mudancas) -> InstantaneoLembrete:
    """Por padrão a IA falou por último (1 min depois do cliente): é quando um lembrete faz sentido."""
    cliente = mudancas.get("ultimo_cliente_em", utc(17, 10))
    base = {
        "estado": "aguardando_cliente",
        "lembretes_enviados": 0,
        "lembretes_max": 1,
        "ultima_ia_em": cliente + timedelta(minutes=1) if cliente else utc(17, 11),
        "ultimo_cliente_em": cliente,
    }
    return InstantaneoLembrete(**{**base, **mudancas})


def test_lembrete_dentro_da_janela_envia_e_registra_a_janela_de_24h():
    agora = utc(17, 15)  # terça 12:00 SP
    assert jobs.decidir_lembrete(instantaneo(), agora, CAL) == Decisao("enviar", janela_24h=True)
    longe = instantaneo(ultimo_cliente_em=agora - timedelta(hours=25))
    assert jobs.decidir_lembrete(longe, agora, CAL) == Decisao("enviar", janela_24h=False)  # fora das 24 h: quem envia usa template
    desconhecida = instantaneo(ultimo_cliente_em=None)
    assert jobs.decidir_lembrete(desconhecida, agora, CAL) == Decisao("enviar", janela_24h=False)  # sem a data, só template


def test_lembrete_fora_da_janela_adia_para_08h_ou_encerra():
    noite = utc(17, 23, 30)  # terça 20:30 SP, fora da janela
    cliente_recente = instantaneo(ultimo_cliente_em=utc(17, 22))  # 19:00 SP: às 08:00 ainda dá 13 h
    assert jobs.decidir_lembrete(cliente_recente, noite, CAL) == Decisao("adiar", ate=utc(18, 11))  # quarta 08:00 SP
    cliente_antigo = instantaneo(ultimo_cliente_em=utc(17, 12))  # 09:00 SP: às 08:00 de quarta ainda dá 23 h
    assert jobs.decidir_lembrete(cliente_antigo, noite, CAL) == Decisao("adiar", ate=utc(18, 11))
    estourou = instantaneo(ultimo_cliente_em=utc(17, 10, 59))  # 07:59 SP de terça: quarta 08:00 = 24 h e 1 min
    assert jobs.decidir_lembrete(estourou, noite, CAL) == Decisao("encerrar", motivo="sem_lembrete_fora_da_janela")
    domingo = utc(15, 15)  # 12:00 SP: a próxima abertura é segunda 08:00
    assert jobs.decidir_lembrete(instantaneo(ultimo_cliente_em=utc(15, 23)), domingo, CAL) == Decisao(
        "adiar", ate=utc(16, 11)
    )  # falou domingo 20:00
    assert (
        jobs.decidir_lembrete(instantaneo(ultimo_cliente_em=utc(14, 20)), domingo, CAL).tipo == "encerrar"
    )  # falou sábado 17:00: 39 h até segunda
    assert jobs.decidir_lembrete(instantaneo(ultimo_cliente_em=None), noite, CAL) == Decisao(
        "encerrar", motivo="sem_lembrete_fora_da_janela"
    )


def test_lembrete_nao_sai_se_o_cliente_respondeu_depois_ou_o_estado_mudou():
    agora = utc(17, 15)
    respondeu = instantaneo(ultima_ia_em=utc(17, 11), ultimo_cliente_em=utc(17, 12))
    assert jobs.decidir_lembrete(respondeu, agora, CAL) == Decisao("ignorar", motivo="cliente_respondeu")
    for estado in ("aberto", "pausado", "repassando", "encerrado", "reservado"):
        assert jobs.decidir_lembrete(instantaneo(estado=estado), agora, CAL).tipo == "ignorar", estado
    assert jobs.decidir_lembrete(None, agora, CAL) == Decisao("ignorar", motivo="atendimento_inexistente")


def test_lembrete_respeita_maximo_efetivo_da_faixa():
    agora = utc(17, 15)
    for max_, enviados, esperado in ((0, 0, "ignorar"), (1, 0, "enviar"), (1, 1, "ignorar"), (2, 1, "enviar"), (2, 2, "ignorar")):
        decisao = jobs.decidir_lembrete(instantaneo(lembretes_max=max_, lembretes_enviados=enviados), agora, CAL)
        assert decisao.tipo == esperado, (max_, enviados)


async def test_executar_lembrete_age_conforme_a_decisao(banco, relogio):
    chamadas = Chamadas()
    atendimento = uuid.uuid4()
    servicos = montar_servicos(banco, relogio, chamadas)
    adiados: list[datetime] = []

    async def reagendar(ate: datetime) -> None:
        adiados.append(ate)

    chamadas.instantaneos[atendimento] = instantaneo(ultimo_cliente_em=relogio.agora() - timedelta(hours=5))
    await jobs.executar_lembrete(servicos, atendimento, 1, reagendar)
    assert chamadas.lembretes == [(atendimento, 1, True)]

    relogio.definir(utc(17, 23, 30))  # 20:30 SP
    chamadas.instantaneos[atendimento] = instantaneo(ultimo_cliente_em=utc(17, 22))
    await jobs.executar_lembrete(servicos, atendimento, 1, reagendar)
    assert adiados == [utc(18, 11)] and len(chamadas.lembretes) == 1

    chamadas.instantaneos[atendimento] = instantaneo(ultimo_cliente_em=utc(16, 12))
    await jobs.executar_lembrete(servicos, atendimento, 1, reagendar)
    assert chamadas.encerrados_sem_lembrete == [(atendimento, "sem_lembrete_fora_da_janela")]


# --- reaper de lease -----------------------------------------------------------------------------------------------------------------------


async def test_reaper_pula_pausado_e_reservado_de_agendamento_ate_o_lease(banco, relogio, conn_super):
    chamadas = Chamadas()
    agora = relogio.agora()
    vencido = agora - timedelta(minutes=10)
    reservado = inserir_atendimento(conn_super, estado="reservado", iniciado_em=agora - timedelta(minutes=20), lease_ate=vencido)
    aberto = inserir_atendimento(conn_super, estado="aberto", iniciado_em=agora - timedelta(minutes=20), lease_ate=vencido)
    aguardando = inserir_atendimento(conn_super, estado="aguardando_cliente", iniciado_em=agora - timedelta(minutes=20), lease_ate=vencido)
    inserir_atendimento(
        conn_super, estado="aberto", iniciado_em=agora - timedelta(minutes=20), lease_ate=agora + timedelta(minutes=1)
    )  # em dia
    pausado_em_dia = inserir_atendimento(
        conn_super,
        estado="pausado",
        iniciado_em=agora - timedelta(hours=1),
        retoma_em=agora + timedelta(hours=2),
        lease_ate=agora + timedelta(hours=3),
    )
    agendado_em_dia = inserir_atendimento(
        conn_super,
        estado="reservado",
        gatilho="agendamento",
        iniciado_em=agora - timedelta(hours=1),
        retoma_em=agora + timedelta(hours=2),
        lease_ate=agora + timedelta(hours=3),
    )
    pausado_perdido = inserir_atendimento(
        conn_super,
        estado="pausado",
        iniciado_em=agora - timedelta(hours=5),
        retoma_em=agora - timedelta(hours=2),
        lease_ate=agora - timedelta(hours=1),
    )
    servicos = montar_servicos(banco, relogio, chamadas)

    tratados = await jobs.executar_reaper_lease(servicos)

    por_id = {lease.atendimento_id: lease.acao for lease in chamadas.leases}
    assert por_id == {reservado: "abortar", aberto: "repassar", aguardando: "repassar", pausado_perdido: "retomada_perdida"}
    assert pausado_em_dia not in por_id and agendado_em_dia not in por_id  # pausa e agendamento em dia: o reaper não toca
    assert tratados == 4


async def test_reaper_nao_age_sobre_turno_em_curso(banco, relogio, conn_super):
    chamadas = Chamadas()
    agora = relogio.agora()
    chat = hex24()
    inserir_atendimento(
        conn_super, estado="aberto", chat_id=chat, iniciado_em=agora - timedelta(minutes=20), lease_ate=agora - timedelta(minutes=10)
    )
    conn_super.execute(
        "INSERT INTO procrastinate.procrastinate_jobs (queue_name, task_name, lock, status) VALUES ('default', 'ia:turno', %s, 'doing')",
        (f"chat:{chat}",),
    )
    assert await jobs.executar_reaper_lease(montar_servicos(banco, relogio, chamadas)) == 0
    assert chamadas.leases == []


# --- bloqueio programado -------------------------------------------------------------------------------------------------------------------


def test_job_unico_so_vale_antes_do_fim_da_janela_dataprev(banco, relogio, conn_app):
    atrasado = RelogioFalso(utc(23, 12))  # 23/11 09:00 SP: a janela acabou, o Danilo já gravou false depois do smoke
    assert jobs.executar_bloqueio_dataprev(montar_servicos(banco, atrasado, Chamadas())) is False
    assert config_vigente(conn_app, "bloqueio_entrada").valor is False
    na_hora = RelogioFalso(utc(21, 0, 51))
    assert jobs.executar_bloqueio_dataprev(montar_servicos(banco, na_hora, Chamadas())) is True
    assert config_vigente(conn_app, "bloqueio_entrada").valor is True
    assert jobs.executar_bloqueio_dataprev(montar_servicos(banco, na_hora, Chamadas())) is False  # já estava true: nada novo


def test_job_da_dataprev_com_relogio_do_worker_um_pouco_atras_do_banco_ainda_fecha(banco, conn_app):
    """Revisão (B1): o job sai pelo `now()` do banco; o worker com o relógio 1 min atrás não pode concluir sem fechar a entrada."""
    cedo_demais = RelogioFalso(utc(21, 0, 40))  # 20/11 21:40 SP, 10 min antes do tick: não é este job
    assert jobs.executar_bloqueio_dataprev(montar_servicos(banco, cedo_demais, Chamadas())) is False
    assert config_vigente(conn_app, "bloqueio_entrada").valor is False
    um_pouco_antes = RelogioFalso(utc(21, 0, 49))  # 21:49 SP, o tick é 21:50
    assert jobs.executar_bloqueio_dataprev(montar_servicos(banco, um_pouco_antes, Chamadas())) is True
    assert config_vigente(conn_app, "bloqueio_entrada").valor is True


# --- poda ------------------------------------------------------------------------------------------------------------------------------------


EVENTO_FINAL = {"todo": "deferred", "doing": "started", "succeeded": "succeeded", "failed": "failed", "cancelled": "cancelled"}


def inserir_job(conn, status: str, idade_dias: float, agora: datetime, nome: str = "ia:turno") -> int:
    """Job com um único evento (o último) há `idade_dias`, relativos ao relógio injetado, que não é o do banco."""
    job = conn.execute(
        "INSERT INTO procrastinate.procrastinate_jobs (queue_name, task_name, lock, args, status) "
        "VALUES ('default', %s, 'chat:x', '{\"atendimento_id\": \"x\"}', %s) RETURNING id",
        (nome, status),
    ).fetchone()[0]
    conn.execute("DELETE FROM procrastinate.procrastinate_events WHERE job_id = %s", (job,))  # o gatilho só cria evento para `todo`
    conn.execute(
        "INSERT INTO procrastinate.procrastinate_events (job_id, type, at) VALUES (%s, %s, %s)",
        (job, EVENTO_FINAL[status], agora - timedelta(days=idade_dias)),
    )
    return job


def ids_dos_jobs(conn) -> set[int]:
    return {r[0] for r in conn.execute("SELECT id FROM procrastinate.procrastinate_jobs")}


def test_podar_apaga_jobs_antigos_do_procrastinate(conn_super, relogio):
    agora = relogio.agora()
    velho_ok = inserir_job(conn_super, "succeeded", 8, agora)
    novo_ok = inserir_job(conn_super, "succeeded", 6, agora)
    velho_falho = inserir_job(conn_super, "failed", 31, agora)
    novo_falho = inserir_job(conn_super, "failed", 20, agora)
    velho_cancelado = inserir_job(conn_super, "cancelled", 9, agora)
    pendente_velho = inserir_job(conn_super, "todo", 90, agora)  # nunca se apaga o que ainda vai rodar
    rodando_velho = inserir_job(conn_super, "doing", 90, agora)
    assert conn_super.execute("SELECT count(*) FROM procrastinate.procrastinate_events").fetchone()[0] == 7

    apagados = jobs.podar_jobs(conn_super, agora, dias_concluidos=7, dias_falhos=30)

    assert ids_dos_jobs(conn_super) == {novo_ok, novo_falho, pendente_velho, rodando_velho}
    assert apagados == 3  # velho_ok, velho_falho, velho_cancelado
    assert {velho_ok, velho_falho, velho_cancelado}.isdisjoint(ids_dos_jobs(conn_super))
    # os eventos vão junto (ON DELETE CASCADE): nada de histórico órfão
    assert (
        conn_super.execute(
            "SELECT count(*) FROM procrastinate.procrastinate_events WHERE job_id NOT IN (SELECT id FROM procrastinate.procrastinate_jobs)"
        ).fetchone()[0]
        == 0
    )
    assert conn_super.execute("SELECT count(*) FROM procrastinate.procrastinate_events").fetchone()[0] == 4


def test_podar_jobs_periodicos_antigos_nao_quebram_a_chave_estrangeira(conn_super, relogio):
    agora = relogio.agora()
    job = inserir_job(conn_super, "succeeded", 10, agora, nome="ia:bloqueio_2015")
    conn_super.execute(
        "INSERT INTO procrastinate.procrastinate_periodic_defers (task_name, defer_timestamp, job_id, periodic_id) VALUES ('ia:bloqueio_2015', %s, %s, '')",
        (int((agora - timedelta(days=1)).timestamp()), job),
    )
    assert jobs.podar_jobs(conn_super, agora, dias_concluidos=7, dias_falhos=30) == 1
    assert conn_super.execute("SELECT job_id FROM procrastinate.procrastinate_periodic_defers").fetchone()[0] is None


async def test_podar_chama_as_duas_funcoes_do_banco(banco, relogio, conn_super):
    agora_real = datetime.now(UTC)
    velho = inserir_atendimento(conn_super, estado="encerrado", iniciado_em=agora_real - timedelta(days=16))
    conn_super.execute(
        "INSERT INTO ia.conversa_cifrada (atendimento_id, seq, remetente, chave_id, nonce, cifra, criada_em, apagar_em) "
        "VALUES (%s, 1, 'cliente', 1, decode('000000000000000000000000','hex'), decode(repeat('ab',20),'hex'), %s, %s)",
        (velho, agora_real - timedelta(days=16), agora_real + timedelta(days=10)),
    )
    resultado = await jobs.executar_podar(montar_servicos(banco, relogio, Chamadas()))
    assert resultado.conversa == 1  # fn_texto_podar(14, 1): encerrado há 15 dias perde o texto
    assert resultado.atendimentos == 0  # fn_atendimento_podar(365): nada com mais de um ano
    assert conn_super.execute("SELECT count(*) FROM ia.conversa_cifrada").fetchone()[0] == 0


# --- auditoria de PII e expiração (esqueletos que delegam) -------------------------------------------------------------------------------------


async def test_auditoria_pii_seleciona_encerrados_ha_mais_de_24h_sem_auditoria(banco, relogio, conn_super):
    chamadas = Chamadas()
    agora = relogio.agora()
    antigo = inserir_atendimento(conn_super, estado="encerrado", iniciado_em=agora - timedelta(hours=30))
    inserir_atendimento(conn_super, estado="encerrado", iniciado_em=agora - timedelta(hours=10))  # recente: ainda não
    auditado = inserir_atendimento(conn_super, estado="encerrado", iniciado_em=agora - timedelta(hours=40))
    conn_super.execute("UPDATE ia.atendimento SET pii_auditoria = false WHERE atendimento_id = %s", (auditado,))
    inserir_atendimento(conn_super, estado="aberto", iniciado_em=agora - timedelta(hours=40))  # aberto: não é auditável
    total = await jobs.executar_auditoria_pii(montar_servicos(banco, relogio, chamadas))
    assert chamadas.auditados == [(antigo,)] and total == 1


async def test_expirar_parados_delega_ao_servico(banco, relogio):
    chamadas = Chamadas()
    await jobs.executar_expirar(montar_servicos(banco, relogio, chamadas))
    assert chamadas.expirados == 1


def test_podar_apaga_o_rastro_antigo_das_periodicas(conn_super, relogio):
    """Revisão A13: `procrastinate_periodic_defers` cresce ~1440 linhas/dia com o reaper por minuto; sem job e velho, sai."""
    agora = relogio.agora()
    velho, novo = int((agora - timedelta(days=40)).timestamp()), int((agora - timedelta(days=2)).timestamp())
    for ts in (velho, novo):
        conn_super.execute(
            "INSERT INTO procrastinate.procrastinate_periodic_defers (task_name, defer_timestamp, job_id) VALUES ('ia:reaper_lease', %s, NULL)",
            (ts,),
        )
    jobs.podar_jobs(conn_super, agora)
    assert [r[0] for r in conn_super.execute("SELECT defer_timestamp FROM procrastinate.procrastinate_periodic_defers")] == [novo]
