"""`expirar_parados` de verdade (B1.6a; sp01 Task 5 «parado > `dias_max` da faixa ⇒ `encerrar(expirado)`»; gate 3 de DECISOES-B5.7b).

- Só `jobs.ESTADOS_EXPIRAVEIS` (`aberto`, `aguardando_cliente`): `pausado` dorme até a volta e o `reservado` de agendamento até `retoma_em`;
  `repassando` é do repasse. Quem fecha esses é a parada leve, o lease ou a vigia.
- O prazo é o `dias_max` da faixa na versão de `faixas_esforco` vigente em `iniciado_em` (trocar a config não muda atendimento em curso).
- Chat com job `turno`/`iniciar`/`lembrete` em curso (`doing`/`todo` com `lock=chat:`) fica para a próxima rodada (como o `reaper_lease`).
- Todo encerramento emite `encerrou` no outbox do espelho (`desfecho = expirar_parados`), na mesma transação.
"""

from __future__ import annotations

import copy
from datetime import timedelta

import pytest

from ia_atendimento import expiracao, jobs, worker
from ia_atendimento.chave import registrar_config
from ia_atendimento.chave_registro import PADROES
from tests import fixtures_fila as ff
from tests.apoio_agenda import inserir_job
from tests.fixtures_fila import Chamadas, inserir_atendimento, montar_servicos

conn_app, conn_super, relogio = ff.conn_app, ff.conn_super, ff.relogio
pytestmark = pytest.mark.banco


def _estado(conn, atd):
    return conn.execute("SELECT estado, desfecho, motivo_desfecho FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()


def _encerrou(conn, atd):
    return [r[0] for r in conn.execute("SELECT detalhe ->> 'desfecho' FROM ia.espelho_evento WHERE atendimento_id = %s", (atd,))]


async def _expirar(banco, relogio) -> int:
    return await expiracao.executar_expirar_parados(montar_servicos(banco, relogio, Chamadas()))


async def test_expira_aberto_e_aguardando_alem_do_dias_max_da_faixa(banco, conn_super, relogio):
    agora = relogio.agora()
    velho_aberto = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=agora - timedelta(days=2, minutes=1))
    velho_aguardando = inserir_atendimento(conn_super, estado="aguardando_cliente", modo="sombra", iniciado_em=agora - timedelta(days=3))
    novo = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=agora - timedelta(days=1, hours=23))
    assert await _expirar(banco, relogio) == 2  # faixa `media` (fixture): dias_max = 2
    assert _estado(conn_super, velho_aberto) == ("encerrado", "expirado", "expirar_parados")
    assert _estado(conn_super, velho_aguardando) == ("encerrado", "expirado", "expirar_parados")
    assert _estado(conn_super, novo)[0] == "aberto"
    assert _encerrou(conn_super, velho_aberto) == ["expirar_parados"] and _encerrou(conn_super, novo) == []


@pytest.mark.parametrize("estado", ["pausado", "reservado", "repassando"])
async def test_nao_expira_fora_dos_estados_expiraveis(banco, conn_super, relogio, estado):
    atd = inserir_atendimento(conn_super, estado=estado, modo="real", iniciado_em=relogio.agora() - timedelta(days=8))
    assert await _expirar(banco, relogio) == 0
    assert _estado(conn_super, atd)[0] == estado


async def test_chat_com_job_em_curso_fica_para_a_proxima(banco, conn_super, relogio):
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora() - timedelta(days=5))
    chat = conn_super.execute("SELECT chat_id FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()[0]
    job = inserir_job(conn_super, "ia:turno", f"turno:{chat}", "doing", lock=f"chat:{chat}")
    assert await _expirar(banco, relogio) == 0
    conn_super.execute("UPDATE procrastinate.procrastinate_jobs SET status = 'succeeded' WHERE id = %s", (job,))
    assert await _expirar(banco, relogio) == 1


async def test_dias_max_e_o_da_versao_vigente_em_iniciado_em(banco, conn_app, conn_super, relogio):
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora() - timedelta(days=2, hours=1))
    nova = copy.deepcopy(PADROES["faixas_esforco"])
    nova["faixas"]["media"]["dias_max"] = 7
    registrar_config(conn_app, "faixas_esforco", nova, "teste", relogio=relogio, motivo="nova versão depois do início")
    assert await _expirar(banco, relogio) == 1, "vale o dias_max de quando o atendimento começou (2), não o novo (7)"
    assert _estado(conn_super, atd)[1] == "expirado"
    relogio.avancar(minutes=1)
    novo = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
    relogio.avancar(days=3)
    assert await _expirar(banco, relogio) == 0, "o atendimento novo nasceu sob dias_max = 7"
    assert _estado(conn_super, novo)[0] == "aberto"


async def test_o_job_usa_o_servico_de_producao(banco, conn_super, relogio):
    """O worker de produção injeta o `expirar_parados` real (não falha mais com `ServicoNaoConfigurado`)."""

    class _Pool:
        def connection(self):
            return ff.abrir(banco)

    servicos = worker.montar_servicos(_Pool())
    assert jobs.configurado(servicos.expirar_parados)
