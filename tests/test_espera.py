"""Lease de quem espera o cliente com o ponto de chamada (B1.6a; pendência 1 de DECISOES-B1.5 e R2 de REVISAO-B1.1-r2).

`aguardar_cliente_com_espera` lê da config os intervalos dos lembretes e o calendário vigentes e, do atendimento, o `lembretes_max` da
faixa NA VERSÃO de `faixas_esforco` vigente em `iniciado_em` (trocar a config não muda atendimento em curso), e passa o resultado de
`estado.lease_de_espera` ao `aguardar_cliente`. Faixa sem lembrete (`lembretes_max=0`) encerra por vácuo no primeiro intervalo.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta

import pytest

from ia_atendimento.calendario import FUSO
from ia_atendimento.chave import LeitorConfig, config_em, registrar_config
from ia_atendimento.chave_registro import PADROES
from ia_atendimento.espera import aguardar_cliente_com_espera, lease_de_espera_do_atendimento, limites_da_faixa
from tests import fixtures_fila as ff
from tests.fixtures_fila import inserir_atendimento

conn_app, conn_super = ff.conn_app, ff.conn_super
pytestmark = pytest.mark.banco

TERCA_12H = datetime(2026, 11, 17, 15, 0, tzinfo=UTC)


def _faixa(conn, atd, faixa: str) -> None:
    conn.execute("UPDATE ia.atendimento SET faixa_esforco = %s, comissao_esperada_brl = 1000 WHERE atendimento_id = %s", (faixa, atd))


def _lease(conn, atd):
    return conn.execute("SELECT estado, lease_ate FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()


@pytest.mark.parametrize(
    ("faixa", "esperado_local"),
    [
        ("baixa", datetime(2026, 11, 17, 16, 30, tzinfo=FUSO)),  # sem lembrete: vácuo às 16:00 (+4 h) + 30 min
        ("media", datetime(2026, 11, 17, 18, 30, tzinfo=FUSO)),  # 1 lembrete às 16:00, encerra 18:00, + 30 min
        ("alta", datetime(2026, 11, 18, 10, 30, tzinfo=FUSO)),  # 16:00 e 20:00 (fora) → qua 08:00, encerra 10:00, + 30 min
    ],
)
def test_lease_de_espera_segue_a_faixa_os_intervalos_e_o_calendario(conn_app, conn_super, faixa, esperado_local):
    from ia_atendimento.relogio import RelogioFalso

    relogio = RelogioFalso(TERCA_12H)
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=TERCA_12H - timedelta(minutes=10))
    _faixa(conn_super, atd, faixa)
    versao = conn_app.execute("SELECT versao FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()[0]
    nova = aguardar_cliente_com_espera(conn_app, atd, versao, relogio=relogio, leitor=LeitorConfig(relogio, ttl_s=0))
    assert nova == versao + 1
    assert _lease(conn_app, atd) == ("aguardando_cliente", esperado_local.astimezone(UTC))


def test_faixa_e_a_da_versao_vigente_em_iniciado_em(conn_app, conn_super):
    from ia_atendimento.relogio import RelogioFalso

    relogio = RelogioFalso(TERCA_12H)
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=TERCA_12H - timedelta(hours=1))
    _faixa(conn_super, atd, "media")
    nova = copy.deepcopy(PADROES["faixas_esforco"])
    nova["faixas"]["media"]["lembretes_max"] = 0
    nova["faixas"]["media"]["dias_max"] = 7
    registrar_config(conn_app, "faixas_esforco", nova, "teste", relogio=relogio, motivo="nova versão depois do início")
    assert limites_da_faixa(conn_app, atd).lembretes_max == 1, "atendimento em curso não muda com a config nova"
    assert config_em(conn_app, "faixas_esforco", TERCA_12H)["faixas"]["media"]["lembretes_max"] == 0
    assert lease_de_espera_do_atendimento(conn_app, atd, relogio.agora(), LeitorConfig(relogio, ttl_s=0)) == datetime(
        2026, 11, 17, 18, 30, tzinfo=FUSO
    ).astimezone(UTC)


def test_config_em_sem_versao_anterior_ao_instante_usa_a_primeira(conn_app):
    """O atendimento iniciado antes de qualquer gravação da chave (seed no boot depois dele) usa a versão mais antiga, não o padrão em código."""
    antiga = datetime(2020, 1, 1, tzinfo=UTC)
    assert config_em(conn_app, "faixas_esforco", antiga) == PADROES["faixas_esforco"]
