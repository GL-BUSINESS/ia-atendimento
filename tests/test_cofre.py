"""Cofre (B1.2, sp01 T4): `canal` e `digitacao` cifrados, TTL ≤ 7 d, expiração; o que está aqui nunca vai a `passo`."""

from __future__ import annotations

import time
from datetime import timedelta

import psycopg
import pytest

from ia_atendimento.cifra import FalhaAoDecifrar
from ia_atendimento.cofre import TTL_MAX, expirar, guardar, ler
from ia_atendimento.conversa import gravar_troca
from ia_atendimento.linha_tempo import CtxPasso, gravar_passo
from ia_atendimento.passos import criar
from tests.apoio_b12 import AGORA, MARCADOR, novo_atendimento

pytest_plugins = ["tests.apoio_b12"]

CANAL = {"chat_number": "5511912345678"}  # sintético
DIGITACAO = {"conta": f"{MARCADOR}-0001", "pix": "000.000.012-34"}


@pytest.fixture
def atd(conn_app):
    return novo_atendimento(conn_app)


def test_canal_ida_e_volta_ttl_7d(conn_app, atd, chaveiro):
    guardar(conn_app, atd, "canal", CANAL, agora=AGORA, chaveiro=chaveiro)
    assert ler(conn_app, atd, "canal", chaveiro=chaveiro) == CANAL
    linha = conn_app.execute(
        "SELECT chave_id, expira_em - criado_em, abs(extract(epoch FROM now() - criado_em)) < 10 FROM ia.cofre"
    ).fetchone()
    assert linha == (2, TTL_MAX, True)  # criado_em é do BANCO (M1)
    assert timedelta(days=7) == TTL_MAX
    assert ler(conn_app, atd, "digitacao", chaveiro=chaveiro) is None


def test_relogio_do_chamador_nao_decide_ttl_nem_chave_m1_m2(conn_app, atd, chaveiro):
    """`agora=2030` só serve para conferir a chave mensal (e aqui ela não confere); nunca vira `criado_em`/`expira_em`."""
    from datetime import UTC, datetime

    from ia_atendimento.conversa import ChaveForaDoMes

    with pytest.raises(ChaveForaDoMes):
        guardar(conn_app, atd, "canal", CANAL, agora=datetime(2030, 1, 1, tzinfo=UTC), chaveiro=chaveiro)
    assert conn_app.execute("SELECT count(*) FROM ia.cofre").fetchone() == (0,)


def test_guardar_de_novo_nao_renova_alem_de_7_dias_do_primeiro(conn_app, atd, chaveiro):
    guardar(conn_app, atd, "canal", CANAL, agora=AGORA, chaveiro=chaveiro)
    primeiro = conn_app.execute("SELECT criado_em, expira_em FROM ia.cofre").fetchone()
    guardar(conn_app, atd, "canal", {"chat_number": "5511900000000"}, agora=AGORA, chaveiro=chaveiro)
    assert conn_app.execute("SELECT criado_em, expira_em FROM ia.cofre").fetchone() == primeiro
    assert ler(conn_app, atd, "canal", chaveiro=chaveiro) == {"chat_number": "5511900000000"}


def test_ttl_acima_de_7_dias_ou_nao_positivo_e_recusado(conn_app, atd, chaveiro):
    for ttl in (timedelta(days=7, seconds=1), timedelta(0), timedelta(hours=-1)):
        with pytest.raises(ValueError, match="ttl"):
            guardar(conn_app, atd, "canal", CANAL, agora=AGORA, chaveiro=chaveiro, ttl=ttl)
    guardar(conn_app, atd, "canal", CANAL, agora=AGORA, chaveiro=chaveiro, ttl=timedelta(days=7))
    assert conn_app.execute("SELECT count(*) FROM ia.cofre").fetchone() == (1,)


def test_finalidade_e_dados_invalidos_sao_recusados_sem_eco(conn_app, atd, chaveiro):
    with pytest.raises(ValueError, match="finalidade"):
        guardar(conn_app, atd, "outra", CANAL, agora=AGORA, chaveiro=chaveiro)
    for dados in ({}, [1, 2], "texto", {"x": object()}):
        with pytest.raises(ValueError, match="dados") as erro:
            guardar(conn_app, atd, "digitacao", dados, agora=AGORA, chaveiro=chaveiro)  # type: ignore[arg-type]
        assert MARCADOR not in str(erro.value)


def test_guardar_de_novo_substitui_a_linha(conn_app, atd, chaveiro):
    guardar(conn_app, atd, "digitacao", {"v": 1}, agora=AGORA, chaveiro=chaveiro)
    guardar(conn_app, atd, "digitacao", {"v": 2}, agora=AGORA, chaveiro=chaveiro)
    assert ler(conn_app, atd, "digitacao", chaveiro=chaveiro) == {"v": 2}
    assert conn_app.execute("SELECT count(*) FROM ia.cofre").fetchone() == (1,)


def test_cofre_nao_contem_o_texto_em_claro_e_nonce_nunca_repete(banco, conn_app, atd, chaveiro):
    guardar(conn_app, atd, "digitacao", DIGITACAO, agora=AGORA, chaveiro=chaveiro)
    guardar(conn_app, atd, "canal", CANAL, agora=AGORA, chaveiro=chaveiro)
    with banco.sessao() as admin:
        dump = " ".join(r[0] for r in admin.execute("SELECT t::text FROM ia.cofre t").fetchall())
    for alvo in (MARCADOR, MARCADOR.encode().hex(), "5511912345678", "000.000.012-34"):
        assert alvo not in dump
    nonces = {bytes(r[0]) for r in conn_app.execute("SELECT nonce FROM ia.cofre").fetchall()}
    assert len(nonces) == 2


def test_o_que_vai_ao_cofre_nunca_vai_a_passo_nem_a_conversa(banco, conn_app, atd, chaveiro):
    guardar(conn_app, atd, "digitacao", DIGITACAO, agora=AGORA, chaveiro=chaveiro)
    gravar_passo(conn_app, atd, ctx=CtxPasso(turno=1, fase="E5"), dados=criar("erro", peca="digitacao"))
    gravar_troca(conn_app, atd, remetente="ia", texto="qual a sua conta?", agora=AGORA, chaveiro=chaveiro, nomes=())
    with banco.sessao() as admin:
        for tabela in ("passo", "conversa_cifrada", "atendimento"):
            dump = " ".join(r[0] for r in admin.execute(f"SELECT t::text FROM ia.{tabela} t").fetchall())
            assert MARCADOR not in dump
            assert "5511912345678" not in dump


def test_aad_do_cofre_inclui_a_finalidade(banco, conn_app, atd, chaveiro):
    guardar(conn_app, atd, "digitacao", DIGITACAO, agora=AGORA, chaveiro=chaveiro)
    with banco.sessao() as admin:
        admin.execute("UPDATE ia.cofre SET finalidade = 'canal'")
    with pytest.raises(FalhaAoDecifrar):
        ler(conn_app, atd, "canal", chaveiro=chaveiro)


def test_vencido_le_como_ausente_e_expirar_apaga_so_o_vencido(conn_app, atd, chaveiro_do_mes_atual):
    guardar(conn_app, atd, "canal", CANAL, chaveiro=chaveiro_do_mes_atual, ttl=timedelta(milliseconds=150))
    guardar(conn_app, atd, "digitacao", {"v": 1}, chaveiro=chaveiro_do_mes_atual, ttl=timedelta(days=1))
    assert ler(conn_app, atd, "canal", chaveiro=chaveiro_do_mes_atual) == CANAL
    time.sleep(0.5)
    assert ler(conn_app, atd, "canal", chaveiro=chaveiro_do_mes_atual) is None  # vencido lê como ausente, mesmo antes da poda
    assert conn_app.execute("SELECT count(*) FROM ia.cofre").fetchone() == (2,)
    assert expirar(conn_app) == 1
    assert [r[0] for r in conn_app.execute("SELECT finalidade FROM ia.cofre").fetchall()] == ["digitacao"]
    assert expirar(conn_app) == 0


def test_ia_leitura_nao_alcanca_texto_nem_cofre(banco, conn_app, atd, chaveiro):
    guardar(conn_app, atd, "canal", CANAL, agora=AGORA, chaveiro=chaveiro)
    gravar_troca(conn_app, atd, remetente="cliente", texto="oi", agora=AGORA, chaveiro=chaveiro, nomes=())
    gravar_passo(conn_app, atd, ctx=CtxPasso(turno=1, fase="E1"), dados=criar("opt_out"))
    for papel in ("ia_leitura_a", "ia_qualidade_a", "intruso"):
        with banco.sessao(papel) as leitor:
            for tabela in ("conversa_cifrada", "cofre"):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    leitor.execute(f"SELECT * FROM ia.{tabela}")
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    leitor.execute(f"SELECT cifra FROM ia.{tabela}")
    with banco.sessao("ia_leitura_a") as leitor:  # a linha do tempo (sem texto de cliente) ela lê
        assert leitor.execute("SELECT count(*) FROM ia.passo").fetchone() == (1,)
