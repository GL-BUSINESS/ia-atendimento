"""`reaper_ledger` (B1.6b; G-0116): `reservada` órfã libera a vaga da T7; `enviada` órfã segue o critério de classe (G-0131)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta

import pytest

from ia_atendimento.reaper_ledger import varrer_ledger
from tests import fixtures_fila as ff
from tests.apoio_b16b import AlertasFalsos
from tests.fixtures_fila import inserir_atendimento

conn_app, conn_super, relogio = ff.conn_app, ff.conn_super, ff.relogio

pytestmark = pytest.mark.banco


def _confirmacao(conn, atd, agora) -> uuid.UUID:
    return conn.execute(
        "INSERT INTO ia.confirmacao (atendimento_id, tipo, banco, oferta_versao, valores_hash, texto_id, estado, classe_resposta, respondida_em,"
        " resposta_ordem, pergunta_ordem, criada_em, expira_em) VALUES (%s, 'digitacao', 'FACTA', 1, %s, 'tx-28', 'aceita', 'sim', %s, 2, 1,"
        " %s, %s) RETURNING confirmacao_id",
        (atd, "d" * 64, agora - timedelta(minutes=1), agora - timedelta(minutes=2), agora + timedelta(minutes=28)),
    ).fetchone()[0]


def _linha(conn, atd, ferramenta, classe, estado, *, reservada_em, enviada_em=None, modo="real", banco=None, conf=None, tentativa=1):
    pessoa = conn.execute("SELECT pessoa_id FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()[0]
    chave = f"{ferramenta}:{atd}:{banco or 'x'}:{tentativa}"
    return conn.execute(
        "INSERT INTO ia.ferramenta_chamada (atendimento_id, pessoa_id, ferramenta, ferramenta_versao, classe_efeito, chave_logica, idem_key,"
        " estado, modo, reservada_em, enviada_em, banco, confirmacao_id, args_hash, tentativa_n) VALUES"
        " (%s, %s, %s, '1.0.0', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING chamada_id",
        (atd, pessoa, ferramenta, classe, chave, hashlib.sha256(chave.encode()).hexdigest(), estado, modo, reservada_em, enviada_em, banco,
         conf, "e" * 64 if classe == "efeito_irreversivel" else None, tentativa),
    ).fetchone()[0]  # fmt: skip


def _estado(conn, chamada_id):
    return conn.execute("SELECT estado FROM ia.ferramenta_chamada WHERE chamada_id = %s", (chamada_id,)).fetchone()[0]


def test_t7_reservada_orfa_em_atendimento_encerrado_nao_tranca_a_pessoa(conn_app, conn_super, relogio):
    agora = relogio.agora()
    pessoa = uuid.uuid4()
    velho = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=agora - timedelta(hours=1), pessoa_id=pessoa)
    orfa = _linha(conn_super, velho, "t7", "efeito_irreversivel", "reservada", reservada_em=agora - timedelta(minutes=11), banco="FACTA",
                  conf=_confirmacao(conn_super, velho, agora))  # fmt: skip
    conn_super.execute(
        "UPDATE ia.atendimento SET estado = 'encerrado', desfecho = 'sem_venda', encerrado_em = %s, lease_ate = NULL WHERE atendimento_id = %s",
        (agora, velho),
    )
    novo = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=agora, pessoa_id=pessoa)
    alertas = AlertasFalsos()
    assert varrer_ledger(conn_app, agora, alertas).nao_criadas == 1
    assert _estado(conn_super, orfa) == "nao_criada"
    _linha(
        conn_super,
        novo,
        "t7",
        "efeito_irreversivel",
        "reservada",
        reservada_em=agora,
        banco="FACTA",
        conf=_confirmacao(conn_super, novo, agora),
    )  # fmt: skip  (a vaga da pessoa está livre)


def test_reservada_recente_nao_e_mexida(conn_app, conn_super, relogio):
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
    linha = _linha(conn_super, atd, "t11", "efeito_irreversivel", "reservada", reservada_em=relogio.agora() - timedelta(minutes=9))
    varrer_ledger(conn_app, relogio.agora(), AlertasFalsos())
    assert _estado(conn_super, linha) == "reservada"


@pytest.mark.parametrize(
    ("ferramenta", "classe", "modo", "esperado"),
    [
        ("t11", "efeito_irreversivel", "real", "indeterminado"),
        ("t11", "efeito_irreversivel", "sombra", "transitorio"),
        ("t12", "acao_interna", "real", "transitorio"),
        ("assumir", "acao_interna", "real", "transitorio"),
    ],
)
def test_enviada_orfa_segue_o_criterio_de_classe(conn_app, conn_super, relogio, ferramenta, classe, modo, esperado):
    agora = relogio.agora()
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=agora)
    linha = _linha(conn_super, atd, ferramenta, classe, "enviada", reservada_em=agora - timedelta(minutes=5),
                   enviada_em=agora - timedelta(minutes=5), modo=modo)  # fmt: skip
    alertas = AlertasFalsos()
    varrer_ledger(conn_app, agora, alertas)
    assert _estado(conn_super, linha) == esperado
    assert ("efeito_indeterminado" in alertas.codigos("critico")) is (esperado == "indeterminado")


def test_enviada_dentro_do_timeout_nao_e_mexida(conn_app, conn_super, relogio):
    agora = relogio.agora()
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=agora)
    linha = _linha(conn_super, atd, "t11", "efeito_irreversivel", "enviada", reservada_em=agora - timedelta(seconds=20),
                   enviada_em=agora - timedelta(seconds=20))  # fmt: skip
    varrer_ledger(conn_app, agora, AlertasFalsos())
    assert _estado(conn_super, linha) == "enviada"
