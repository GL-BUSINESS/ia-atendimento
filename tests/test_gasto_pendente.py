"""Gasto do contrato 08 §9 (R1-14, fechado na B1.6a): Σ `passo.custo_brl` no dia/mês de São Paulo, todos os modos.

A B1.3 somava `custo_modelo_brl + custo_midia_brl` dos atendimentos por `iniciado_em`: a conversa que atravessa a meia-noite contava no dia
errado e o custo de um passo só aparecia depois que o processador o copiasse para o atendimento. Agora a fonte é o passo (`ocorrido_em`,
`idx_passo_ocorrido`); `ferramenta_chamada.custo_brl` e o custo do atendimento NÃO entram (sem dupla contagem). O nome do arquivo ficou
o da pendência para o histórico apontar para cá.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest

from ia_atendimento import gasto
from ia_atendimento.gasto import (
    GastoIndisponivel,
    MedidorGasto,
    avaliar_gasto,
    custo_ausente_dia,
    gasto_dia,
    gasto_mes,
    nivel_do_gasto,
)
from ia_atendimento.relogio import RelogioFalso
from tests import apoio_api
from tests import fixtures_fila as ff
from tests.fixtures_fila import inserir_atendimento

conn_app, conn_super = ff.conn_app, ff.conn_super

pytestmark = pytest.mark.banco

# terça 17/11/2026: 00:00 em São Paulo = 03:00 UTC
MEIA_NOITE_17 = datetime(2026, 11, 17, 3, 0, tzinfo=UTC)


def _passo(conn, atd, ordem: int, custo, *, ocorrido_em: datetime, tipo: str = "erro", tokens: int | None = None) -> None:
    if tipo == "decisao":
        conn.execute(
            "INSERT INTO ia.passo (atendimento_id, ordem, ocorrido_em, tipo, texto, turno, fase, motor, intencao, confianca, modelo, provedor,"
            " tokens_entrada, tokens_saida, custo_brl) VALUES (%s, %s, %s, 'decisao', 'Decisão do modelo.', 1, 'E1', 'modelo', 'duvida', 'alta',"
            " 'deepseek-v4p1-flash-1017', 'fireworks-us', %s, %s, %s)",
            (atd, ordem, ocorrido_em, tokens, tokens, custo),
        )
        return
    conn.execute(
        "INSERT INTO ia.passo (atendimento_id, ordem, ocorrido_em, tipo, texto, turno, fase, peca, custo_brl)"
        " VALUES (%s, %s, %s, 'erro', 'Erro na peça modelo.', 1, 'E1', 'modelo', %s)",
        (atd, ordem, ocorrido_em, custo),
    )


def test_gasto_do_dia_soma_passos_em_brt_e_todos_os_modos(conn_app, conn_super):
    """Relógio fixo (revisão A10): com `datetime.now()` e o `now()` do banco, a meia-noite de São Paulo entre os dois o derrubava."""
    agora = MEIA_NOITE_17 + timedelta(hours=23, minutes=59)  # 17/11 23:59 BRT: o último minuto do dia
    atd = inserir_atendimento(conn_super, estado="aberto", modo="duble", iniciado_em=agora - timedelta(minutes=1))
    _passo(conn_super, atd, 1, Decimal(5), ocorrido_em=agora)
    _passo(conn_super, atd, 2, Decimal(7), ocorrido_em=agora + timedelta(minutes=1))  # 18/11 00:00 BRT: outro dia
    assert gasto_dia(conn_app, agora) == Decimal(5)


@pytest.mark.parametrize("modo", ["real", "sombra", "duble", "teste"])
def test_todos_os_modos_contam(conn_app, conn_super, modo):
    agora = MEIA_NOITE_17 + timedelta(hours=12)
    atd = inserir_atendimento(conn_super, estado="aberto", modo=modo, iniciado_em=agora - timedelta(hours=1))
    _passo(conn_super, atd, 1, Decimal("1.25"), ocorrido_em=agora)
    assert gasto_dia(conn_app, agora) == Decimal("1.25")


def test_conversa_que_atravessa_a_meia_noite_conta_cada_passo_no_seu_dia(conn_app, conn_super):
    """O dia é o do `ocorrido_em` do passo em São Paulo, não o `iniciado_em` do atendimento (nem o dia UTC)."""
    inicio = MEIA_NOITE_17 - timedelta(minutes=10)  # 16/11 23:50 BRT
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=inicio)
    _passo(conn_super, atd, 1, Decimal(3), ocorrido_em=MEIA_NOITE_17 - timedelta(minutes=5))  # 16/11 23:55 BRT
    _passo(conn_super, atd, 2, Decimal(2), ocorrido_em=MEIA_NOITE_17 + timedelta(minutes=10))  # 17/11 00:10 BRT
    _passo(conn_super, atd, 3, Decimal(7), ocorrido_em=MEIA_NOITE_17 + timedelta(hours=23, minutes=59))  # 17/11 23:59 BRT (18/11 UTC)
    assert gasto_dia(conn_app, MEIA_NOITE_17 + timedelta(hours=12)) == Decimal(9)
    assert gasto_dia(conn_app, MEIA_NOITE_17 - timedelta(hours=12)) == Decimal(3)


def test_mes_e_o_civil_de_sao_paulo(conn_app, conn_super):
    fim_de_outubro = datetime(2026, 11, 1, 2, 30, tzinfo=UTC)  # 31/10 23:30 BRT
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=fim_de_outubro)
    _passo(conn_super, atd, 1, Decimal(4), ocorrido_em=fim_de_outubro)
    _passo(conn_super, atd, 2, Decimal(1), ocorrido_em=fim_de_outubro + timedelta(hours=1))  # 01/11 00:30 BRT
    assert gasto_mes(conn_app, datetime(2026, 11, 17, 15, 0, tzinfo=UTC)) == Decimal(1)
    assert gasto_mes(conn_app, datetime(2026, 10, 31, 15, 0, tzinfo=UTC)) == Decimal(4)


def test_custo_copiado_no_atendimento_nao_e_somado(conn_app, conn_super):
    """`custo_modelo_brl`/`custo_midia_brl` são derivados (disjuntor por atendimento): somá-los dobraria o gasto."""
    agora = MEIA_NOITE_17 + timedelta(hours=12)
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=agora, custo_modelo=7, custo_midia=1)
    _passo(conn_super, atd, 1, Decimal(2), ocorrido_em=agora)
    assert gasto_dia(conn_app, agora) == Decimal(2)


def test_chamada_ferramenta_nao_duplica_custo(conn_app, conn_super):
    """O passo `chamada_ferramenta` carrega a cópia do custo do ledger; `ferramenta_chamada.custo_brl` não é somada."""
    agora = MEIA_NOITE_17 + timedelta(hours=12)
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=agora)
    pessoa = conn_super.execute("SELECT pessoa_id FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()[0]
    chave_logica = f"t11:{atd}:1:1"
    chamada = conn_super.execute(
        "INSERT INTO ia.ferramenta_chamada (atendimento_id, pessoa_id, ferramenta, ferramenta_versao, classe_efeito, chave_logica, idem_key,"
        " estado, modo, enviada_em, concluida_em, custo_brl) VALUES (%s, %s, 't11', '1.0.0', 'efeito_irreversivel', %s, %s, 'ok', 'real',"
        " %s, %s, 4) RETURNING chamada_id",
        (atd, pessoa, chave_logica, hashlib.sha256(chave_logica.encode()).hexdigest(), agora, agora),
    ).fetchone()[0]
    conn_super.execute(
        "INSERT INTO ia.passo (atendimento_id, ordem, ocorrido_em, tipo, texto, turno, fase, ferramenta, ferramenta_versao, chamada_id, custo_brl)"
        " VALUES (%s, 1, %s, 'chamada_ferramenta', 'Chamada de ferramenta.', 1, 'E1', 't11', '1.0.0', %s, 4)",
        (atd, agora, chamada),
    )
    assert gasto_dia(conn_app, agora) == Decimal(4)


def test_custo_ausente_conta_passo_com_tokens_ou_do_modelo_sem_custo(conn_app, conn_super):
    """Nunca se soma zero em silêncio: passo com tokens e `custo_brl` nulo, ou decisão do modelo sem `usage`, é `custo_ausente`."""
    agora = MEIA_NOITE_17 + timedelta(hours=12)
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=agora)
    _passo(conn_super, atd, 1, None, ocorrido_em=agora, tipo="decisao", tokens=100)  # tokens sem custo
    _passo(conn_super, atd, 2, None, ocorrido_em=agora, tipo="decisao", tokens=None)  # resposta sem usage
    _passo(conn_super, atd, 3, Decimal("0.5"), ocorrido_em=agora, tipo="decisao", tokens=100)  # completo
    _passo(conn_super, atd, 4, None, ocorrido_em=agora)  # erro sem custo nem tokens: não é chamada ao modelo
    assert custo_ausente_dia(conn_app, agora) == 2
    assert gasto_dia(conn_app, agora) == Decimal("0.5")


@pytest.mark.parametrize(
    ("gasto", "limite", "nivel"),
    [
        (Decimal("79.99"), Decimal(100), "normal"),
        (Decimal(80), Decimal(100), "amarelo"),
        (Decimal("99.99"), Decimal(100), "amarelo"),
        (Decimal(100), Decimal(100), "critico"),
        (Decimal(125), Decimal(100), "critico"),
        (Decimal("125.01"), Decimal(100), "repassar"),
        (Decimal(0), Decimal(0), "critico"),  # limite zero sem gasto: barra entrada nova, os abertos concluem (revisão A7)
        (Decimal("0.01"), Decimal(0), "repassar"),  # limite zero com gasto: já passou de 125 %
    ],
)
def test_80_100_125_por_cento(gasto, limite, nivel):
    assert nivel_do_gasto(gasto, limite) == nivel


def test_avaliar_gasto_devolve_o_pior_entre_dia_e_mes(conn_app, conn_super):
    agora = MEIA_NOITE_17 + timedelta(hours=12)
    relogio = RelogioFalso(agora)
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=agora)
    _passo(conn_super, atd, 1, Decimal(85), ocorrido_em=agora)  # 85% do subteto_dia padrão (100); 4,25% do mensal (2000)
    avaliacao = avaliar_gasto(conn_app, relogio)
    assert (avaliacao.nivel_dia, avaliacao.nivel_mes, avaliacao.nivel) == ("amarelo", "normal", "amarelo")
    assert avaliacao.custo_ausente == 0


def test_medidor_guarda_a_soma_por_30_s(conn_app, conn_super):
    agora = MEIA_NOITE_17 + timedelta(hours=12)
    relogio = RelogioFalso(agora)
    medidor = MedidorGasto(relogio)
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=agora)
    assert medidor.dia(conn_app) == 0
    _passo(conn_super, atd, 1, Decimal(3), ocorrido_em=agora)
    relogio.avancar(seconds=29)
    assert medidor.dia(conn_app) == 0, "dentro dos 30 s vale o cache"
    relogio.avancar(seconds=1)
    assert medidor.dia(conn_app) == Decimal(3)


def test_gasto_nao_calculavel_vira_gasto_indisponivel(conn_app, monkeypatch):
    def quebrada(*_args, **_kwargs):
        raise psycopg.errors.DataError("soma quebrada")

    monkeypatch.setattr(gasto, "_somar_custos", quebrada)
    with pytest.raises(GastoIndisponivel):
        gasto_dia(conn_app, MEIA_NOITE_17)


ambiente = apoio_api.ambiente


def test_entrada_com_gasto_nao_calculavel_responde_503_nao_pronto_e_nao_grava(ambiente, monkeypatch):
    ambiente.ligar()

    def quebrada(*_args, **_kwargs):
        raise psycopg.errors.DataError("soma quebrada")

    monkeypatch.setattr(gasto, "_somar_custos", quebrada)
    r = ambiente.post("/atendimentos", apoio_api.corpo_de_entrada())
    assert r.status_code == 503 and r.json()["erro"]["codigo"] == "nao_pronto", r.text
    assert ambiente.escalar("SELECT count(*) FROM ia.atendimento") == 0 and ambiente.fila.inicios == []
