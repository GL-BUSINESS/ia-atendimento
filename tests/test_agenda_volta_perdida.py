"""Volta perdida (R2-03 da revisão 2 da B5.7b): o lead devolvido pelo `reaper_lease` não deixa o agendamento `disparado/retomou` PARA SEMPRE,
e a nota ao consultor só diz «a IA não retomou» (NT-06) quando a IA realmente não falou.

O handler de lease é o da B1.6; aqui vale o de referência de `tests/apoio_agenda.py`, que fecha a linha na mesma transação do repasse.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from ia_atendimento import agenda_estado as ae
from ia_atendimento import agenda_jobs, jobs
from tests import fixtures_fila as ff
from tests.apoio_agenda import (
    Voltas,
    agendado_confirmado,
    inserir_agendamento,
    novo_agendado,
    pausado_confirmado,
    tratar_lease_de_referencia,
)
from tests.fixtures_fila import Chamadas, montar_servicos

conn_app, conn_super, relogio, conninfo_app = ff.conn_app, ff.conn_super, ff.relogio, ff.conninfo_app
pytestmark = pytest.mark.banco


def _linha(conn, agendamento_id):
    return conn.execute(
        "SELECT estado, desfecho_disparo, cancelado_por FROM ia.agendamento WHERE agendamento_id = %s", (agendamento_id,)
    ).fetchone()


def _passos(conn, atendimento_id):
    return [
        r[0]
        for r in conn.execute(
            "SELECT resultado FROM ia.passo WHERE atendimento_id = %s AND tipo = 'agendamento' ORDER BY ordem", (atendimento_id,)
        )
    ]


async def _reaper(banco, relogio, quando):
    """Um tick do `reaper_lease` real com o handler de referência; devolve as notas ao consultor."""
    relogio.definir(quando)
    notas: list = []
    servicos = montar_servicos(
        banco,
        relogio,
        Chamadas(),
        tratar_lease_vencido=tratar_lease_de_referencia(banco, relogio, notas=notas),
        retomar_atendimento=Voltas(),
    )
    assert await jobs.executar_reaper_lease(servicos) == len(notas)
    return notas


@pytest.mark.parametrize(("fase", "nota"), [("E5", "NT-01"), ("E8", "NT-05")])
async def test_volta_reivindicada_e_perdida_fecha_como_repassou_e_nao_diz_que_a_ia_nao_retomou(
    banco, conn_app, relogio, versoes, fase, nota
):
    """O worker morreu depois do CAS: `disparado/retomou` ficaria para sempre e a mensagem PODE ter saído. Fecha como `repassou`; NT-05 em E8
    («não conseguiu concluir»), NT-01 nas outras fases («interrompido; o cliente pode ter escrito»). NT-06 seria falsa."""
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara, fase=fase)
    relogio.definir(dispara + timedelta(seconds=1))
    await agenda_jobs.executar_retomar(
        montar_servicos(banco, relogio, Chamadas(), retomar_atendimento=Voltas()), caso.agendamento_id, lambda _: None
    )  # a volta reivindica e «morre» (o espião não faz nada)
    assert _linha(conn_app, caso.agendamento_id)[:2] == ("disparado", "retomou")
    notas = await _reaper(banco, relogio, dispara + timedelta(minutes=31))
    assert notas == [(caso.atendimento_id, nota)]
    assert _linha(conn_app, caso.agendamento_id)[:2] == ("disparado", "repassou"), "a linha para de dizer «retomou»"
    assert conn_app.execute("SELECT estado FROM ia.atendimento WHERE atendimento_id = %s", (caso.atendimento_id,)).fetchone() == (
        "repassando",
    )


async def test_confirmado_orfao_alarme_perdido_cancela_por_sistema_e_diz_que_a_ia_nao_retomou(banco, conn_app, relogio, versoes):
    """O alarme sumiu e o `reaper_lease` chegou antes do `reaper_agenda` (que só olha `pausado`/`reservado`): a IA nunca falou ⇒ NT-06 é verdade."""
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    notas = await _reaper(banco, relogio, dispara + timedelta(minutes=31))
    assert notas == [(caso.atendimento_id, "NT-06")]
    assert _linha(conn_app, caso.agendamento_id) == ("cancelado", None, "sistema") and _passos(conn_app, caso.atendimento_id) == [
        "cancelado"
    ]


async def test_expirado_pelo_teto_de_atraso_continua_expirado_e_diz_nt_06(banco, conn_app, relogio, versoes):
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    relogio.definir(dispara + timedelta(hours=5))
    servicos = montar_servicos(banco, relogio, Chamadas(), retomar_atendimento=Voltas())
    assert await agenda_jobs.executar_retomar(servicos, caso.agendamento_id, lambda _: None) == "expirado"
    notas = await _reaper(banco, relogio, relogio.agora())
    assert notas == [(caso.atendimento_id, "NT-06")] and _linha(conn_app, caso.agendamento_id)[0] == "expirado"


async def test_pendente_que_ninguem_confirmou_do_caso_b_vira_expirado_no_aborto(banco, conn_app, relogio, versoes):
    agora = relogio.agora()
    atd, _v, _c = novo_agendado(conn_app, agora, versoes, retoma_em=agora + timedelta(hours=1))
    ag = inserir_agendamento(conn_app, atd, entrada_do_pedido="dialogo_agendar", dispara_em=agora + timedelta(hours=1), pedido_em=agora)
    notas = await _reaper(banco, relogio, agora + timedelta(hours=1, minutes=31))
    assert notas == [(atd, "NT-06")] and _linha(conn_app, ag)[0] == "expirado" and _passos(conn_app, atd) == ["expirado"]
    assert conn_app.execute("SELECT estado, desfecho FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone() == (
        "encerrado",
        "abortado",
    )


async def test_caso_b_reservado_confirmado_nunca_disparou_e_cancelado_e_abortado(banco, conn_app, relogio, versoes):
    dispara = relogio.agora() + timedelta(hours=2)
    caso = agendado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    notas = await _reaper(banco, relogio, dispara + timedelta(minutes=31))
    assert notas == [(caso.atendimento_id, "NT-06")] and _linha(conn_app, caso.agendamento_id) == ("cancelado", None, "sistema")


def test_sem_agendamento_nao_ha_o_que_fechar(conn_app, relogio, versoes):
    from tests.apoio_agenda import novo_aberto

    atd, _v, _c = novo_aberto(conn_app, relogio.agora, versoes)
    assert ae.fechar_volta_perdida(conn_app, atd, agora=relogio.agora()) is None


@pytest.mark.parametrize(
    ("situacao", "fase", "nota"),
    [
        ("nao_falou", "E3", "NT-06"),
        ("nao_falou", "E8", "NT-06"),
        ("pode_ter_falado", "E8", "NT-05"),
        ("pode_ter_falado", "E4", "NT-01"),
        ("pode_ter_falado", None, "NT-01"),
    ],
)
def test_a_nota_so_diz_a_ia_nao_retomou_quando_a_ia_nunca_falou(situacao, fase, nota):
    assert ae.nota_da_volta_perdida(situacao, fase) == nota
