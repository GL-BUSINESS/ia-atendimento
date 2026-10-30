"""Montagem de produção da API (`ambiente._montar`): pool, fila de verdade, segredos em arquivo 0600 e a falha de subida sem valor no erro."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ia_atendimento.api.ambiente import _montar
from ia_atendimento.conversa import chave_id_do_mes
from ia_atendimento.pessoas_teste import PessoasTesteInvalidas
from ia_atendimento.pessoas_teste import carregar as carregar_pessoas
from ia_atendimento.segredos import SegredoInvalido
from tests import fixtures_fila as ff
from tests.apoio_api import CHAT, CHAVE_GATEWAY, TOKENS, corpo_de_entrada, settings_de_teste
from tests.estado_apoio import semear_versoes

pytestmark = pytest.mark.banco
SAIDA = {
    c: f"valor-descartavel-de-{c}-0123" for c in ("ia_orquestrador_bearer", "chatguru_token_ia", "c360_client_id", "c360_client_secret")
}


@pytest.fixture
def arquivos(tmp_path: Path) -> Path:
    import base64
    import os

    (tmp_path / "chaves-api.json").write_text(
        json.dumps({"1": base64.b64encode(os.urandom(32)).decode(), "2": base64.b64encode(os.urandom(32)).decode()})
    )
    (tmp_path / "gw.keys").write_text(CHAVE_GATEWAY + "\n")
    (tmp_path / "saida.json").write_text(json.dumps(SAIDA))
    for nome in ("chaves-api.json", "gw.keys", "saida.json"):
        (tmp_path / nome).chmod(0o600)
    return tmp_path


def test_sobe_com_pool_e_fila_reais_e_atende_a_entrada(banco, arquivos):
    with ff.abrir(banco, "postgres") as conn:
        semear_versoes(conn)
        conn.execute("INSERT INTO ia.config_versao (nome, versao, valor, publicado_por) VALUES ('ia_ativa', 2, 'true', 'teste')")
    app = _montar(settings_de_teste(banco, arquivos, chave_aes_id=chave_id_do_mes(datetime.now(UTC))))
    cab = {"x-ia-token": TOKENS["n8n_braco"]}
    with TestClient(app, raise_server_exceptions=False) as cliente:  # o ciclo de vida abre e fecha o pool
        assert cliente.get("/healthz").status_code == 200
        r = cliente.post("/atendimentos", json=corpo_de_entrada(ultimo_cliente_em=None) | {"ultimo_cliente_em": None}, headers=cab)
        # relógio real: fora da janela de mensagem em certos horários; o que se prova aqui é a montagem, então aceita 201 ou a recusa de janela
        assert r.status_code in (201, 409), r.text
        if r.status_code == 201:
            assert ff.abrir(banco, "postgres").execute(
                "SELECT count(*) FROM procrastinate.procrastinate_jobs WHERE task_name = 'ia:iniciar'"
            ).fetchone() == (1,)
        else:
            assert r.json()["erro"]["codigo"] == "fora_de_janela"
        assert cliente.get("/saude", headers=cab).json()["ia_ativa"] is True
        assert cliente.get("/saude").status_code == 401


def test_nao_sobe_com_arquivo_de_segredo_aberto_sem_citar_o_conteudo(banco, arquivos):
    (arquivos / "gw.keys").chmod(0o644)
    with pytest.raises(SegredoInvalido, match="0600") as erro:
        _montar(settings_de_teste(banco, arquivos, chave_aes_id=chave_id_do_mes(datetime.now(UTC))))
    assert CHAVE_GATEWAY not in str(erro.value)
    (arquivos / "gw.keys").chmod(0o600)
    (arquivos / "saida.json").write_text(json.dumps({**SAIDA, "c360_client_secret": "curto"}))
    with pytest.raises(SegredoInvalido) as erro:
        _montar(settings_de_teste(banco, arquivos, chave_aes_id=chave_id_do_mes(datetime.now(UTC))))
    assert "curto" not in str(erro.value)


def test_nao_sobe_sem_arquivo_de_segredo(banco, arquivos):
    (arquivos / "saida.json").unlink()
    with pytest.raises(SegredoInvalido):
        _montar(settings_de_teste(banco, arquivos, chave_aes_id=chave_id_do_mes(datetime.now(UTC))))


def test_pessoas_teste_de_arquivo_e_sem_arquivo_ninguem_e_de_teste(tmp_path):
    vazio = carregar_pessoas(None)
    assert not vazio.contem(__import__("uuid").UUID("33333333-3333-7333-8333-333333333333")) and vazio.pessoa_do_chat(CHAT) is None
    arquivo = tmp_path / "pessoas.json"
    arquivo.write_text(
        json.dumps(
            {
                "pessoas": ["33333333-3333-7333-8333-333333333333"],
                "chats": {"aaaaaaaaaaaaaaaaaaaaaaaa": "33333333-3333-7333-8333-333333333333"},
            }
        )
    )
    fixas = carregar_pessoas(arquivo)
    assert (
        str(fixas.pessoa_do_chat("aaaaaaaaaaaaaaaaaaaaaaaa")) == "33333333-3333-7333-8333-333333333333"
        and fixas.pessoa_do_chat(CHAT) is None
    )
    for ruim in (
        '{"pessoas": ["nao-e-uuid"], "chats": {}}',
        '{"pessoas": []}',
        "nao json",
        '{"pessoas": [], "chats": {"CHAT-MAIUSCULO": "x"}}',
    ):
        arquivo.write_text(ruim)
        with pytest.raises(PessoasTesteInvalidas):
            carregar_pessoas(arquivo)
    with pytest.raises(PessoasTesteInvalidas):
        carregar_pessoas(tmp_path / "nao-existe.json")


# --- revisão 2: dialeto na URL (R2-04) e pool com tempos-limite e check (R2-08) ------------------------------------------------------------------


def _settings_do_mes(banco, arquivos, **mudar):
    return settings_de_teste(banco, arquivos, chave_aes_id=chave_id_do_mes(datetime.now(UTC)), **mudar)


def test_subida_recusa_o_dialeto_psycopg_na_url_sem_citar_a_url(banco, arquivos):
    from ia_atendimento.config import ConfiguracaoInvalida

    s = banco.servidor
    url = f"postgresql+psycopg://ia_app_a:senha-descartavel-xyz@{s.host}:{s.port}/{banco.nome}"
    with pytest.raises(ConfiguracaoInvalida) as erro:
        _montar(_settings_do_mes(banco, arquivos, database_url=url))
    assert "database_url" in str(erro.value) and "senha-descartavel-xyz" not in str(erro.value) and s.host not in str(erro.value)


def test_conninfo_do_pool_leva_search_path_da_fila_e_os_tempos_limite():
    from psycopg.conninfo import conninfo_to_dict

    from ia_atendimento.api.ambiente import conninfo_do_pool

    opcoes = conninfo_to_dict(conninfo_do_pool("postgresql://ia_app_a:x@127.0.0.1:5432/ia?options=-c%20application_name%3Dapi"))["options"]
    for esperado in (
        "application_name=api", "search_path=procrastinate,public", "lock_timeout=2000", "statement_timeout=5000",
        "idle_in_transaction_session_timeout=10000",
    ):  # fmt: skip
        assert esperado in opcoes


def test_pool_e_criado_com_check_de_conexao(banco, arquivos, monkeypatch):
    from psycopg_pool import ConnectionPool

    from ia_atendimento.api import ambiente

    capturado: dict = {}
    original = ConnectionPool

    def espiao(*args, **kwargs):
        capturado.update(kwargs)
        return original(*args, **kwargs)

    espiao.check_connection = original.check_connection  # type: ignore[attr-defined]
    monkeypatch.setattr(ambiente, "ConnectionPool", espiao)
    _montar(_settings_do_mes(banco, arquivos))
    assert capturado["check"] is original.check_connection and capturado["kwargs"] == {"autocommit": True}


def test_conexao_do_pool_tem_lock_timeout_e_uma_espera_por_lock_vira_erro_de_503_em_vez_de_pendurar(banco, arquivos):
    import time

    import psycopg

    app = _montar(_settings_do_mes(banco, arquivos))
    with TestClient(app, raise_server_exceptions=False):  # abre o pool
        conexao = app.state.ctx.conexao
        with conexao() as conn:
            assert conn.execute("SHOW lock_timeout").fetchone() == ("2s",)
            assert conn.execute("SHOW statement_timeout").fetchone() == ("5s",)
            assert conn.execute("SHOW idle_in_transaction_session_timeout").fetchone() == ("10s",)
        with ff.abrir(banco, "postgres") as dono:  # alguém segura a trava advisory
            dono.execute("BEGIN")
            dono.execute("SELECT pg_advisory_xact_lock(hashtextextended('ia_atendimento.abrir', 0))")
            inicio = time.monotonic()
            with conexao() as conn, pytest.raises(psycopg.errors.LockNotAvailable), conn.transaction():
                conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('ia_atendimento.abrir', 0))")
            assert time.monotonic() - inicio < 4, "a espera acabou no lock_timeout, não ficou presa"
            dono.execute("ROLLBACK")
    assert issubclass(psycopg.errors.LockNotAvailable, psycopg.OperationalError), "OperationalError ⇒ 503 nao_pronto"
