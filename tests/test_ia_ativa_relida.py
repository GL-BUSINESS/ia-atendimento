"""`ia_ativa` relida AO EXECUTAR (B1.6a; obrigações de DECISOES-B1.5:69 e da r2 da B1.5, R1-31).

- `encerrar_por_chave`: o `PUT ia_ativa=false` agenda um job por atendimento, escalonado em até 19 min. Se a IA foi religada nesse meio
  tempo (liga → desliga → liga), o job NÃO fecha o atendimento de uma IA ligada. A leitura não usa o cache do processo.
- `iniciar`: com a IA desligada, o `reservado` é abortado ANTES do `assumir` (nada muda no chat), com o `encerrou` no outbox do espelho.
- `retomar` do `reservado` de agendamento (caso b): com a IA desligada não dispara; o agendamento é cancelado (`sistema`) e o reservado
  abortado (nunca tocou o chat). O `pausado` (caso a) já tocou o chat: quem o fecha é a parada leve (`encerrar_por_chave`), e a volta
  da B5.7c relê `ia_ativa` antes de falar (pendência registrada em DECISOES-B1.6a).
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from ia_atendimento import agenda_jobs, jobs
from ia_atendimento.chave import LeitorConfig, registrar_config
from tests import fixtures_fila as ff
from tests.apoio_agenda import Voltas, agendado_confirmado
from tests.apoio_agenda import linha_do_agendamento as _ag
from tests.apoio_agenda import reagendar_ignorando as _reagendar_ignorando
from tests.apoio_agenda import servicos_com_volta as _servicos
from tests.fixtures_fila import Chamadas, inserir_atendimento, montar_servicos

conn_app, conn_super, relogio = ff.conn_app, ff.conn_super, ff.relogio
pytestmark = pytest.mark.banco


def _ia(conn, relogio, ligada: bool) -> None:
    registrar_config(conn, "ia_ativa", ligada, "teste", relogio=relogio, motivo="preparo do teste")


def _estado(conn, atd):
    return conn.execute("SELECT estado, desfecho, motivo_desfecho FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()


def _eventos(conn, atd):
    return [
        (r[0], r[1], r[2]["desfecho"])
        for r in conn.execute("SELECT seq, evento, detalhe FROM ia.espelho_evento WHERE atendimento_id = %s ORDER BY seq", (atd,))
    ]


# --- encerrar_por_chave ----------------------------------------------------------------------------------------------------------------


async def test_encerrar_por_chave_com_a_ia_religada_nao_fecha(banco, conn_app, relogio):
    leitor = LeitorConfig(relogio)  # ttl 5 s: o cache diz «desligada»
    _ia(conn_app, relogio, False)
    assert leitor.valor(conn_app, "ia_ativa") is False
    _ia(conn_app, relogio, True)  # religada por outro processo, dentro dos 5 s
    encerrados: list[uuid.UUID] = []

    async def encerrar(atd: uuid.UUID) -> None:
        encerrados.append(atd)

    servicos = montar_servicos(banco, relogio, Chamadas(), encerrar_por_chave=encerrar, leitor_config=leitor)
    assert await jobs.executar_encerrar_por_chave(servicos, uuid.uuid4()) is False
    assert encerrados == []


async def test_encerrar_por_chave_com_a_ia_desligada_executa(banco, conn_app, relogio):
    _ia(conn_app, relogio, False)
    encerrados: list[uuid.UUID] = []

    async def encerrar(atd: uuid.UUID) -> None:
        encerrados.append(atd)

    atd = uuid.uuid4()
    servicos = montar_servicos(banco, relogio, Chamadas(), encerrar_por_chave=encerrar)
    assert await jobs.executar_encerrar_por_chave(servicos, atd) is True
    assert encerrados == [atd]


# --- iniciar ---------------------------------------------------------------------------------------------------------------------------


async def test_iniciar_com_a_ia_desligada_aborta_antes_do_assumir_e_emite_encerrou(banco, conn_app, conn_super, relogio):
    _ia(conn_app, relogio, False)
    atd = inserir_atendimento(conn_super, estado="reservado", modo="real", iniciado_em=relogio.agora())
    chamadas = Chamadas()
    assert await jobs.executar_iniciar(montar_servicos(banco, relogio, chamadas), atd) is False
    assert chamadas.iniciados == [], "o assumir nunca foi chamado"
    assert _estado(conn_app, atd) == ("encerrado", "abortado", "ia_desligada")
    assert _eventos(conn_app, atd) == [(1, "encerrou", "ia_desligada")]


async def test_iniciar_com_a_ia_ligada_entrega_ao_servico(banco, conn_app, conn_super, relogio):
    _ia(conn_app, relogio, True)
    atd = inserir_atendimento(conn_super, estado="reservado", modo="real", iniciado_em=relogio.agora())
    chamadas = Chamadas()
    assert await jobs.executar_iniciar(montar_servicos(banco, relogio, chamadas), atd) is True
    assert chamadas.iniciados == [atd] and _estado(conn_app, atd)[0] == "reservado"


async def test_iniciar_de_quem_ja_nao_e_reservado_com_a_ia_desligada_nao_faz_nada(banco, conn_app, conn_super, relogio):
    _ia(conn_app, relogio, False)
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
    chamadas = Chamadas()
    assert await jobs.executar_iniciar(montar_servicos(banco, relogio, chamadas), atd) is False
    assert chamadas.iniciados == [] and _estado(conn_app, atd)[0] == "aberto", "quem fecha o aberto é a parada leve"


# --- retomar do reservado de agendamento -----------------------------------------------------------------------------------------------


async def test_reservado_agendado_com_a_ia_desligada_nao_dispara_e_aborta(banco, conn_app, relogio, versoes):
    dispara = relogio.agora() + timedelta(hours=2)
    caso = agendado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    _ia(conn_app, relogio, False)
    voltas = Voltas()
    relogio.definir(dispara)
    codigo = await agenda_jobs.executar_retomar(_servicos(banco, relogio, voltas), caso.agendamento_id, _reagendar_ignorando)
    assert codigo == "ia_desligada" and voltas.recebidas == []
    assert _ag(conn_app, caso.agendamento_id)[0] == "cancelado"
    assert _estado(conn_app, caso.atendimento_id) == ("encerrado", "abortado", "ia_desligada")
    assert _eventos(conn_app, caso.atendimento_id) == [(1, "encerrou", "ia_desligada")]


async def test_reservado_agendado_com_a_ia_ligada_dispara(banco, conn_app, relogio, versoes):
    dispara = relogio.agora() + timedelta(hours=2)
    caso = agendado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    _ia(conn_app, relogio, True)
    voltas = Voltas()
    relogio.definir(dispara)
    assert await agenda_jobs.executar_retomar(_servicos(banco, relogio, voltas), caso.agendamento_id, _reagendar_ignorando) == "disparado"
    assert len(voltas.recebidas) == 1
