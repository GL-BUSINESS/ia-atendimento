"""Execução superada (revisão automática da B5.7b): um job que a fila deu como falho (`jobs_presos`) pode ainda estar rodando num worker só lento.

O chat já foi liberado para outro job; a execução SUPERADA não pode enviar nem gravar estado. Aqui, em CÓDIGO que este repositório tem:

- toda escrita de estado do atendimento é CAS por `versao` (`aplicar`, `consumir`, `gravar_estado_conversa`, `pausar`, `sair_da_pausa`...): quem
  segura uma versão velha leva `ConflitoVersao`/`ConflitoDeVersao` e NADA muda;
- a volta combinada (`retomar`) é reivindicada por CAS `confirmado → disparado`: a execução superada que já reivindicou segue sendo a única dona
  da volta, e quem chega depois (alarme repetido, `reaper_agenda`) acha `disparado` e não entrega outra.

O que NÃO está aqui: a idempotência do ENVIO da mensagem do `turno` e do `lembrete` (o `Canal`/ledger `t11:{atd}:{turno}:{seq}` e o serviço
`enviar_lembrete` são da B1.6; hoje são espiões). É gate da B1.6: sem o ledger, um turno superado ainda pode mandar a mensagem.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from ia_atendimento import agenda_jobs, estado, estado_pausa, fila, linha_tempo
from ia_atendimento.estado import ConflitoVersao, Mudancas
from ia_atendimento.estado_conversa import EstadoConversa, gravar_estado_conversa
from ia_atendimento.worker_vivo import liberar_jobs_presos
from tests import fixtures_fila as ff
from tests.apoio_agenda import Voltas, inserir_job, novo_aberto, novo_worker, pausado_confirmado
from tests.fixtures_fila import Chamadas, montar_servicos

conn_app, conn_super, relogio, conninfo_app = ff.conn_app, ff.conn_super, ff.relogio, ff.conninfo_app
pytestmark = pytest.mark.banco

COLUNAS = "estado, versao, lease_ate, retoma_em, estado_conversa::text, turnos, ordem_consumida, desfecho, motivo_desfecho"


def _linha(conn, atendimento_id: uuid.UUID):
    return conn.execute(f"SELECT {COLUNAS} FROM ia.atendimento WHERE atendimento_id = %s", (atendimento_id,)).fetchone()


# cada escrita que um `turno`/`lembrete`/volta faz no atendimento, com a versão que a execução LEU ao começar
ESCRITAS = {
    "renovar_lease": lambda c, a, v, r: estado.renovar_lease(c, a, v, relogio=r),
    "aguardar_cliente": lambda c, a, v, r: estado.aguardar_cliente(c, a, v, relogio=r),
    "repassar": lambda c, a, v, r: estado.repassar(c, a, v, modo="fila", motivo="pediu_humano", relogio=r),
    "encerrar": lambda c, a, v, r: estado.encerrar(c, a, v, desfecho="sem_resposta", motivo="vacuo", relogio=r),
    "aplicar_contadores": lambda c, a, v, r: estado.aplicar(c, a, v, Mudancas(turnos=9, mensagens_enviadas=9), agora=r()),
    "gravar_estado_conversa": lambda c, a, v, r: gravar_estado_conversa(c, a, v, EstadoConversa(fase="E4"), relogio=r),
    "pausar": lambda c, a, v, r: estado_pausa.pausar(c, a, v, retoma_em=r() + timedelta(hours=2), retoma_fase="E3", relogio=r),
    "consumir_mensagens": lambda c, a, v, r: linha_tempo.consumir(c, a, versao=v, ate_ordem=1),
}


@pytest.mark.parametrize("escrita", sorted(ESCRITAS))
def test_execucao_superada_nao_grava_estado(conn_app, relogio, versoes, escrita):
    """O substituto avançou o atendimento; a execução superada, com a versão velha, é recusada e nada muda."""
    atendimento, versao_lida, _ = novo_aberto(conn_app, relogio.agora, versoes, fase="E3")
    versao_nova = estado.renovar_lease(conn_app, atendimento, versao_lida, relogio=relogio.agora)  # o job substituto andou
    antes = _linha(conn_app, atendimento)
    assert antes[1] == versao_nova > versao_lida
    with pytest.raises((ConflitoVersao, linha_tempo.ConflitoDeVersao)):
        ESCRITAS[escrita](conn_app, atendimento, versao_lida, relogio.agora)
    assert _linha(conn_app, atendimento) == antes, "a execução superada não mudou NADA"


def test_execucao_superada_nao_tira_o_lead_da_pausa(conn_app, relogio, versoes):
    """`sair_da_pausa` da volta velha, depois que o substituto já mexeu no atendimento."""
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=relogio.agora() + timedelta(hours=2))
    versao_lida = conn_app.execute("SELECT versao FROM ia.atendimento WHERE atendimento_id = %s", (caso.atendimento_id,)).fetchone()[0]
    estado.repassar(conn_app, caso.atendimento_id, versao_lida, modo="fila", motivo="pediu_humano", relogio=relogio.agora)  # o substituto
    antes = _linha(conn_app, caso.atendimento_id)
    with pytest.raises(ConflitoVersao):
        estado_pausa.sair_da_pausa(conn_app, caso.atendimento_id, versao_lida, relogio=relogio.agora)
    assert _linha(conn_app, caso.atendimento_id) == antes and antes[0] == "repassando"


async def test_retomar_superado_pela_fila_nao_duplica_a_volta(conn_app, conn_super, conninfo_app, banco, relogio, versoes):
    """O worker A reivindicou a volta e segue nela (lento); a fila o dá como preso; o alarme repetido e o `reaper_agenda` enfileiram outro
    `retomar`. O CAS manda: o substituto acha `disparado` e não entrega uma segunda volta."""
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    relogio.definir(dispara + timedelta(seconds=3))
    voltas = Voltas()
    servicos = montar_servicos(banco, relogio, Chamadas(), retomar_atendimento=voltas)

    async def sem_rearme(_: float) -> None:
        raise AssertionError("não era para rearmar")

    assert await agenda_jobs.executar_retomar(servicos, caso.agendamento_id, sem_rearme, job_id=1) == "disparado"  # a execução A
    # a fila a dá como presa (batimento velho) enquanto A ainda roda: o lock do chat é solto
    morto = novo_worker(conn_super, 600)
    preso = inserir_job(conn_super, "ia:retomar", f"retomar_exec:{caso.agendamento_id}", "doing", morto, lock=f"chat:{caso.chat_id}")
    app = fila.criar_app(conninfo_app, com_periodicas=False)
    async with app.open_async():
        assert await liberar_jobs_presos(app) == [preso]
    # o substituto (alarme repetido / reaper): nada a entregar
    for _ in range(2):
        assert await agenda_jobs.executar_retomar(servicos, caso.agendamento_id, sem_rearme, job_id=2) == "nao_confirmado"
    assert voltas.ids == [caso.agendamento_id], "uma volta só"
