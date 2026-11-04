"""Migração 0005 (D-18, B1.8): o CHECK de `config_versao` deixa de recusar o dia 7 em `janela_mensagem`.

A 0001 nunca é editada (sha travado). A 0005 só troca o `config_versao_valor_check` por uma cópia do CASE da 0001 com UM termo a menos:
o limite 08:00–20:00 segue valendo para os 7 dias, os seeds não mudam (domingo segue fechado por padrão) e as outras chaves seguem
validadas como antes. Prova-se: o texto (cópia fiel menos o termo), o banco antes (recusa) e depois (aceita), e o ledger.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import psycopg
import pytest

from ia_atendimento.migracoes import aplicar, listar
from tests.banco import Banco, apagar_banco, criar_banco, novo_nome

RAIZ = Path(__file__).resolve().parent.parent
MIGRACOES = RAIZ / "migrations"
ARQUIVO_0001 = MIGRACOES / "0001_esquema.up.sql"
ID_0005 = "0005_domingo_por_config"
ARQUIVO_0005 = MIGRACOES / f"{ID_0005}.up.sql"
RESTRICAO = "config_versao_valor_check"
# o único termo que sai (0001:50): `janela_mensagem` deixava de aceitar o dia 7; o limite de horário continua
TERMO_0001 = (
    "AND (nome <> 'janela_mensagem' OR (NOT jsonb_path_exists(valor, '$.dias.\"7\"') AND "
    'NOT jsonb_path_exists(valor, \'$.dias.* ? (!(@.inicio >= "08:00" && @.fim <= "20:00"))\')))'
)
TERMO_0005 = (
    "AND (nome <> 'janela_mensagem' OR NOT jsonb_path_exists(valor, '$.dias.* ? (!(@.inicio >= \"08:00\" && @.fim <= \"20:00\"))'))"
)
DIA = {"inicio": "08:00", "fim": "20:00"}
SEG_A_SAB = {str(d): dict(DIA) for d in range(1, 7)}


@pytest.fixture
def vazio(servidor, papeis):
    nome = novo_nome("ia_m5")
    criar_banco(servidor, nome)
    yield Banco(servidor, nome)
    apagar_banco(servidor, nome)


@pytest.fixture
def ate_0004(tmp_path) -> Path:
    destino = tmp_path / "ate0004"
    destino.mkdir()
    for m in listar(MIGRACOES):
        if m.numero <= 4:
            shutil.copy(m.caminho, destino / m.caminho.name)
    return destino


def _sem_comentarios(sql: str) -> str:
    """Tira `-- …` até o fim da linha (nenhum literal destes CHECKs tem `--`) e junta os espaços."""
    return " ".join(re.sub(r"--[^\n]*", "", sql).split())


def _case_do_check(sql: str) -> str:
    """O CASE do `config_versao_valor_check`, do `CHECK (CASE` até o `ELSE true END)` que o fecha."""
    limpo = _sem_comentarios(sql)
    inicio = limpo.index(f"CONSTRAINT {RESTRICAO} CHECK (CASE")
    fim = limpo.index("ELSE true END)", inicio) + len("ELSE true END)")
    return limpo[inicio:fim]


def _janela(conn: psycopg.Connection, versao: int, dias: dict) -> None:
    conn.execute(
        "INSERT INTO ia.config_versao (nome, versao, valor, publicado_por, motivo) VALUES ('janela_mensagem', %s, %s, 'teste', 'D-18')",
        (versao, json.dumps({"dias": dias})),
    )


# --- o arquivo -------------------------------------------------------------------------------------------------------------------


def test_0005_e_a_quinta_migracao_com_checksum_dos_bytes():
    achadas = listar(MIGRACOES)
    assert [m.id for m in achadas][4] == ID_0005
    assert achadas[4].checksum == hashlib.sha256(ARQUIVO_0005.read_bytes()).hexdigest()


def test_0005_so_troca_o_check_de_valor_com_set_role_do_dono():
    ativas = [
        linha for linha in ARQUIVO_0005.read_text(encoding="utf-8").splitlines() if linha.strip() and not linha.lstrip().startswith("--")
    ]
    assert ativas[0].startswith("SET ROLE ia_owner")
    assert ativas[-1].strip().endswith("RESET ROLE;")
    corpo = _sem_comentarios("\n".join(ativas)).upper()
    assert corpo.count("DROP ") == 1 and f"DROP CONSTRAINT {RESTRICAO.upper()}," in corpo, "o único DROP é o do CHECK que volta logo depois"
    assert corpo.count("ALTER TABLE") == 1 and "ALTER TABLE IA.CONFIG_VERSAO " in corpo
    for proibido in ("INSERT ", "UPDATE ", "DELETE ", "TRUNCATE", "CREATE ", "GRANT ", "REVOKE "):
        assert proibido not in corpo, proibido


def test_0005_copia_o_case_da_0001_com_um_unico_termo_a_menos():
    antes = _case_do_check(ARQUIVO_0001.read_text(encoding="utf-8"))
    depois = _case_do_check(ARQUIVO_0005.read_text(encoding="utf-8"))
    assert antes.count(TERMO_0001) == 1
    assert antes.replace(TERMO_0001, TERMO_0005) == depois
    assert '$.dias."7"' not in depois and '"08:00" && @.fim <= "20:00"' in depois


# --- o banco ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.banco
def test_sem_a_0005_o_banco_recusa_o_dia_7(vazio, ate_0004):
    with vazio.conectar(autocommit=False) as conn:
        aplicar(conn, ate_0004)
    with vazio.sessao("ia_app_a") as conn, pytest.raises(psycopg.errors.CheckViolation) as erro:
        _janela(conn, 2, {**SEG_A_SAB, "7": {"inicio": "09:00", "fim": "18:00"}})
    assert erro.value.diag.constraint_name == RESTRICAO


@pytest.mark.banco
def test_0005_aceita_dia_7_e_mantem_08_20(vazio, ate_0004):
    with vazio.conectar(autocommit=False) as conn:
        assert ID_0005 not in aplicar(conn, ate_0004)
    with vazio.conectar(autocommit=False) as conn:
        assert aplicar(conn, MIGRACOES) == [ID_0005]
    with vazio.sessao("ia_app_a") as conn:
        _janela(conn, 2, {**SEG_A_SAB, "7": {"inicio": "09:00", "fim": "18:00"}})
        _janela(conn, 3, {**SEG_A_SAB, "7": dict(DIA)})
        for dias in (
            {**SEG_A_SAB, "7": {"inicio": "07:59", "fim": "18:00"}},
            {**SEG_A_SAB, "7": {"inicio": "08:00", "fim": "20:01"}},
            {**SEG_A_SAB, "7": {"inicio": "12:00", "fim": "10:00"}},
            {"1": {"inicio": "08:00", "fim": "21:00"}},
            {"8": dict(DIA)},
            {},
        ):
            with pytest.raises(psycopg.errors.CheckViolation) as erro, conn.transaction():
                _janela(conn, 4, dias)
            assert erro.value.diag.constraint_name == RESTRICAO, dias


@pytest.mark.banco
def test_0005_segue_validando_as_outras_chaves(banco):
    with banco.sessao("ia_app_a") as conn:
        for nome, valor in (
            ("modo", '"producao"'),
            ("agenda_teto_horas", "24"),
            ("bloqueio_entrada", '"sim"'),
            ("calendario_bloqueio", "{}"),
        ):
            with pytest.raises(psycopg.errors.CheckViolation) as erro, conn.transaction():
                conn.execute("INSERT INTO ia.config_versao (nome, versao, valor, publicado_por) VALUES (%s, 2, %s, 'teste')", (nome, valor))
            assert erro.value.diag.constraint_name == RESTRICAO, nome
        restricoes = {r for (r,) in conn.execute("SELECT conname FROM pg_constraint WHERE conrelid = 'ia.config_versao'::regclass")}
    assert {RESTRICAO, "config_versao_chats_teste_check", "config_versao_nome_check", "config_versao_autor_check"} <= restricoes


@pytest.mark.banco
def test_0005_nao_mexe_nos_seeds_domingo_segue_fechado(banco):
    with banco.sessao() as conn:
        linhas = dict(
            conn.execute(
                "SELECT nome, valor FROM ia.config_versao WHERE nome IN ('janela_mensagem', 'calendario_bloqueio') AND versao = 1"
            ).fetchall()
        )
        versoes = conn.execute("SELECT count(*) FROM ia.config_versao WHERE nome IN ('janela_mensagem', 'calendario_bloqueio')").fetchone()
    assert linhas["calendario_bloqueio"]["domingos"] is True
    assert set(linhas["janela_mensagem"]["dias"]) == {"1", "2", "3", "4", "5", "6"}
    assert versoes == (2,)


@pytest.mark.banco
def test_0005_grava_o_ledger_e_reaplicar_e_recusado(vazio):
    with vazio.conectar(autocommit=False) as conn:
        aplicar(conn, MIGRACOES)
        assert aplicar(conn, MIGRACOES) == []
    soma = hashlib.sha256(ARQUIVO_0005.read_bytes()).hexdigest()
    with vazio.sessao() as conn:
        assert conn.execute("SELECT checksum FROM ia.migracao WHERE migracao_id = %s", (ID_0005,)).fetchone() == (soma,)
    epilogo = f"SET ROLE ia_owner; INSERT INTO ia.migracao (migracao_id, checksum) VALUES ('{ID_0005}', '{soma}'); RESET ROLE;"
    with vazio.conectar(autocommit=False) as conn, pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
        conn.execute(ARQUIVO_0005.read_text(encoding="utf-8") + epilogo)
