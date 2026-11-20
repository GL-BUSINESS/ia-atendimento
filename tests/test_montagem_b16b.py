"""Montagem da B1.6b: os jobs chegam ao processador, ao repasse e ao desligamento de verdade (portas falsas); a produção não os liga."""

from __future__ import annotations

import pytest

from ia_atendimento import jobs, montagem_b16b, worker
from ia_atendimento.batimento import LeitorBatimento
from ia_atendimento.chave import registrar_config
from tests import fixtures_fila as ff
from tests.apoio_b16b import AlertasFalsos, CanalFalso, EspelhoFalso, FonteFalsa, RotaFalsa, batimento_v2
from tests.fixtures_fila import Chamadas, inserir_atendimento, montar_servicos
from tests.test_processador import MotorFalso

conn_app, conn_super, relogio = ff.conn_app, ff.conn_super, ff.relogio

pytestmark = pytest.mark.banco


def _montado(banco, relogio):
    alertas = AlertasFalsos()
    batimento = LeitorBatimento(FonteFalsa(), relogio, alertas)
    batimento.aceitar(batimento_v2(relogio.agora()))
    portas = montagem_b16b.Portas(CanalFalso(), RotaFalsa(), EspelhoFalso(), batimento, MotorFalso(), alertas)
    return montagem_b16b.montar(montar_servicos(banco, relogio, Chamadas()), portas), portas


async def test_job_iniciar_assume_e_responde(banco, conn_app, conn_super, relogio):
    registrar_config(conn_app, "modo", "real", "teste", relogio=relogio, motivo="preparo do teste")
    registrar_config(conn_app, "ia_ativa", True, "teste", relogio=relogio, motivo="preparo do teste")
    servicos, portas = _montado(banco, relogio)
    atd = inserir_atendimento(conn_super, estado="reservado", modo="real", iniciado_em=relogio.agora())
    assert await jobs.executar_iniciar(servicos, atd)
    assert portas.canal.ops() == ["assumir", "enviar"]


async def test_desligamento_injetado_fecha_os_abertos(banco, conn_app, conn_super, relogio):
    """G-0565: com `ia_ativa=false`, o job `encerrar_por_chave` leva o aberto a `repassando` e a rodada do repasse o encerra."""
    registrar_config(conn_app, "modo", "real", "teste", relogio=relogio, motivo="preparo do teste")
    servicos, _ = _montado(banco, relogio)
    assert jobs.configurado(servicos.encerrar_por_chave)
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
    assert await jobs.executar_encerrar_por_chave(servicos, atd)
    assert await jobs.executar_repasse(servicos, atd, None) is None
    estado = conn_super.execute("SELECT estado, motivo_desfecho FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()
    assert estado == ("encerrado", "repasse_simulado")  # sem `assumir` ok não há posse real: devolução simulada (08 §6 exc. 2)


def test_producao_ainda_nao_liga_a_b16b():
    """Sem adaptador real (DEC-PIA-002), o worker de produção mantém os serviços da B1.6b falhando alto."""

    class PoolFalso:
        def connection(self):
            raise AssertionError("não deveria abrir conexão")

    servicos = worker.montar_servicos(PoolFalso())
    for nome in ("processar_turno", "iniciar_atendimento", "encerrar_por_chave", "repassar", "enfileirar_repasse", "reaper_ledger",
                 "publicar_espelho"):  # fmt: skip
        assert not jobs.configurado(getattr(servicos, nome)), nome
