"""`disparado` não é beco sem saída (R1-02 da revisão 1 da B5.7b): a volta reivindica ANTES das pré-checagens e pode decidir adiar.

Estudo M §2.5 (`reagendado_sistema`: «próximo horário válido, MESMO agendamento») e §2.6 («tentar» a +10 min): `rearmar` faz `disparado → confirmado`
com novo `dispara_em`, sem consumir `seq`, movendo o atendimento junto, no máximo `MAX_REARMES` vezes.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from ia_atendimento import agenda_estado as ae
from ia_atendimento import agenda_jobs, estado, fila, jobs
from ia_atendimento.estado import EntradaInvalida, TransicaoInvalida
from ia_atendimento.jobs import Adiar
from tests import fixtures_fila as ff
from tests.apoio_agenda import Voltas, agendado_confirmado, pausado_confirmado
from tests.fixtures_fila import Chamadas, montar_servicos

conn_app, conn_super, relogio, conninfo_app = ff.conn_app, ff.conn_super, ff.relogio, ff.conninfo_app
pytestmark = pytest.mark.banco


def _servicos(banco, relogio, voltas):
    return montar_servicos(banco, relogio, Chamadas(), retomar_atendimento=voltas)


def _ag(conn, agendamento_id):
    return conn.execute(
        "SELECT estado, seq, versao, dispara_em, disparado_em, desfecho_disparo, job_id FROM ia.agendamento WHERE agendamento_id = %s",
        (agendamento_id,),
    ).fetchone()


def _atd(conn, atendimento_id):
    return conn.execute("SELECT estado, retoma_em, lease_ate FROM ia.atendimento WHERE atendimento_id = %s", (atendimento_id,)).fetchone()


def _passos(conn, atendimento_id):
    return [
        r[0]
        for r in conn.execute(
            "SELECT resultado FROM ia.passo WHERE atendimento_id = %s AND tipo = 'agendamento' ORDER BY ordem", (atendimento_id,)
        )
    ]


async def _sem_alarme(_: float) -> None:
    raise AssertionError("não era para rearmar o alarme")


@pytest.mark.parametrize("motivo", ["reagendado_sistema", "tentar_de_novo"])
async def test_a_volta_que_adia_rearma_o_mesmo_agendamento_sem_consumir_seq(banco, conn_app, relogio, versoes, motivo):
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara, fase="E5")
    relogio.definir(dispara + timedelta(seconds=2))
    nova_hora = relogio.agora() + (timedelta(minutes=10) if motivo == "tentar_de_novo" else timedelta(hours=18))
    voltas = Voltas(sequencia=[Adiar(nova_hora, motivo)])  # a 1ª volta adia; a 2ª entrega (None = retomou)
    servicos = _servicos(banco, relogio, voltas)
    rearmes: list[float] = []

    async def reagendar(atraso: float) -> None:
        rearmes.append(atraso)

    assert await agenda_jobs.executar_retomar(servicos, caso.agendamento_id, reagendar, job_id=11) == "disparado"
    # o MESMO agendamento voltou a `confirmado`, no mesmo seq, com a hora nova e sem rastro do disparo
    estado, seq, versao, hora, disparado_em, desfecho, job = _ag(conn_app, caso.agendamento_id)
    assert (estado, seq, hora, disparado_em, desfecho, job) == ("confirmado", 1, nova_hora, None, None, None)
    assert conn_app.execute("SELECT count(*) FROM ia.agendamento WHERE atendimento_id = %s", (caso.atendimento_id,)).fetchone()[0] == 1
    # o atendimento acompanha: o lease nunca fica antes da hora nova, nem encurta
    estado_atd, retoma_em, lease = _atd(conn_app, caso.atendimento_id)
    assert (estado_atd, retoma_em) == ("pausado", nova_hora) and lease >= nova_hora + timedelta(minutes=30)
    assert lease >= dispara + timedelta(minutes=30), "nunca encurta o lease"
    assert _passos(conn_app, caso.atendimento_id) == ["disparado", "reagendado"]
    assert len(rearmes) == 1 and rearmes[0] == pytest.approx((nova_hora - relogio.agora()).total_seconds())  # o alarme novo, na hora nova
    # o reaper_lease NÃO devolve o lead no lease velho
    assert jobs.selecionar_leases_vencidos(conn_app, dispara + timedelta(minutes=31)) == [], (
        "o lease velho (dispara + 30 min) não vale mais"
    )
    assert jobs.selecionar_leases_vencidos(conn_app, nova_hora + timedelta(minutes=29)) == []
    assert [lease.acao for lease in jobs.selecionar_leases_vencidos(conn_app, nova_hora + timedelta(minutes=31))] == ["retomada_perdida"]
    # na hora nova a volta sai de novo (o 2º `retomar` entrega e não adia)
    relogio.definir(nova_hora + timedelta(seconds=1))
    assert await agenda_jobs.executar_retomar(servicos, caso.agendamento_id, _sem_alarme, job_id=12) == "disparado"
    assert _ag(conn_app, caso.agendamento_id)[:3] == ("disparado", 1, versao + 1) and len(voltas.recebidas) == 2


async def test_o_rearme_vale_para_o_reservado_de_agendamento(banco, conn_app, relogio, versoes):
    dispara = relogio.agora() + timedelta(hours=2)
    caso = agendado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    relogio.definir(dispara)
    nova_hora = dispara + timedelta(hours=20)
    servicos = _servicos(banco, relogio, Voltas(sequencia=[Adiar(nova_hora, "reagendado_sistema")]))

    async def reagendar(_: float) -> None: ...

    assert await agenda_jobs.executar_retomar(servicos, caso.agendamento_id, reagendar) == "disparado"
    assert _atd(conn_app, caso.atendimento_id)[:2] == ("reservado", nova_hora) and _ag(conn_app, caso.agendamento_id)[0] == "confirmado"
    assert _atd(conn_app, caso.atendimento_id)[2] == nova_hora + timedelta(minutes=30)


async def test_rearme_limitado_a_max_rearmes_depois_o_lead_e_do_reaper_lease(banco, conn_app, relogio, versoes):
    """Uma volta que SEMPRE adia não pode prender o lead fora do `reaper_lease` (o rearme estende o lease): o 3º rearme falha alto."""
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    voltas = Voltas(desfecho=None)
    servicos = _servicos(banco, relogio, voltas)

    async def reagendar(_: float) -> None: ...

    hora = dispara
    for n in range(ae.MAX_REARMES):
        relogio.definir(hora + timedelta(seconds=1))
        hora = relogio.agora() + timedelta(minutes=10)
        voltas.sequencia = [Adiar(hora, "tentar_de_novo")]
        assert await agenda_jobs.executar_retomar(servicos, caso.agendamento_id, reagendar) == "disparado", n
    relogio.definir(hora + timedelta(seconds=1))
    voltas.sequencia = [Adiar(relogio.agora() + timedelta(minutes=10), "tentar_de_novo")]
    with pytest.raises(ae.LimiteDeRearmes):
        await agenda_jobs.executar_retomar(servicos, caso.agendamento_id, reagendar)
    assert _ag(conn_app, caso.agendamento_id)[0] == "disparado", "fica `disparado`: o lease devolve o lead ao humano"
    assert _passos(conn_app, caso.atendimento_id).count("reagendado") == ae.MAX_REARMES


async def test_rearme_recusa_hora_passada_e_atendimento_que_saiu_da_espera(banco, conn_app, relogio, versoes):
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    relogio.definir(dispara + timedelta(seconds=1))
    servicos = _servicos(banco, relogio, Voltas())
    await agenda_jobs.executar_retomar(servicos, caso.agendamento_id, _sem_alarme)  # reivindica: `disparado`
    antes = (_ag(conn_app, caso.agendamento_id), _atd(conn_app, caso.atendimento_id))
    with pytest.raises(EntradaInvalida):  # hora que já passou
        ae.rearmar(conn_app, caso.agendamento_id, dispara_em=relogio.agora(), agora=relogio.agora())
    with pytest.raises(ValueError, match="fuso"):
        ae.rearmar(conn_app, caso.agendamento_id, dispara_em=datetime(2026, 11, 20, 12, 0), agora=relogio.agora())
    versao = conn_app.execute("SELECT versao FROM ia.atendimento WHERE atendimento_id = %s", (caso.atendimento_id,)).fetchone()[0]
    estado.repassar(conn_app, caso.atendimento_id, versao, modo="fila", motivo="pediu_humano", relogio=relogio.agora)  # saiu da espera
    with pytest.raises(TransicaoInvalida, match="não espera mais a volta"):
        ae.rearmar(conn_app, caso.agendamento_id, dispara_em=relogio.agora() + timedelta(minutes=10), agora=relogio.agora())
    assert _ag(conn_app, caso.agendamento_id) == antes[0], "recusado: o agendamento não mudou"


async def test_o_alarme_do_rearme_entra_na_fila_na_hora_nova(conninfo_app, conn_app, conn_super, banco, relogio, versoes):
    """Com a fila real: o `retomar` que adia deixa um alarme `todo` novo, ~10 min à frente, e nenhum job vencido."""
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    relogio.definir(dispara + timedelta(seconds=1))
    servicos = _servicos(banco, relogio, Voltas(sequencia=[Adiar(relogio.agora() + timedelta(minutes=10), "tentar_de_novo")]))
    app = fila.criar_app(conninfo_app, com_periodicas=False)
    async with app.open_async():
        await fila.agendar_retomada(app, caso.agendamento_id, caso.atendimento_id, caso.chat_id, dispara)
        conn_super.execute("UPDATE procrastinate.procrastinate_jobs SET scheduled_at = now() - interval '1 second'")
        await app.run_worker_async(
            wait=False, install_signal_handlers=False, additional_context={"servicos": servicos}, fetch_job_polling_interval=0.05
        )
    (novo,) = conn_super.execute(
        "SELECT scheduled_at - now(), queueing_lock, lock FROM procrastinate.procrastinate_jobs"
        " WHERE task_name = 'ia:alarme_retomar' AND status = 'todo'"
    ).fetchall()
    assert timedelta(minutes=9) < novo[0] <= timedelta(minutes=10, seconds=5)
    assert novo[1:] == (f"retomar:{caso.agendamento_id}", None), "alarme sem lock do chat, um por agendamento"
    assert _ag(conn_app, caso.agendamento_id)[0] == "confirmado"


@pytest.mark.parametrize("devolvido", ["reagendado_sistema", "inventado", ""])
async def test_reagendado_sistema_puro_nao_reabre_o_beco_falha_alto_e_manda_usar_adiar(banco, conn_app, relogio, versoes, devolvido):
    """R2-04: `"reagendado_sistema"` devolvido como texto deixava o agendamento `disparado/reagendado_sistema`, sem rearme nem alarme (o beco do R1-02).
    Só `Adiar` reagenda; qualquer outro texto fora de `DesfechoDaVolta` falha explícita (e o lease devolve o lead)."""
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    relogio.definir(dispara + timedelta(seconds=1))
    with pytest.raises(agenda_jobs.RetornoInvalidoDaVolta, match="Adiar"):
        await agenda_jobs.executar_retomar(_servicos(banco, relogio, Voltas(desfecho=devolvido)), caso.agendamento_id, _sem_alarme)
    desfecho = _ag(conn_app, caso.agendamento_id)[5]
    assert desfecho != "reagendado_sistema", "nunca grava o desfecho que não tem alarme"


@pytest.mark.parametrize("devolvido", [None, "retomou", "resolvido", "repassou", "humano_atuou"])
async def test_os_desfechos_validos_da_volta_continuam_aceitos(banco, conn_app, relogio, versoes, devolvido):
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    relogio.definir(dispara + timedelta(seconds=1))
    resultado = await agenda_jobs.executar_retomar(_servicos(banco, relogio, Voltas(desfecho=devolvido)), caso.agendamento_id, _sem_alarme)
    assert resultado == "disparado" and _ag(conn_app, caso.agendamento_id)[5] == (devolvido or "retomou")
