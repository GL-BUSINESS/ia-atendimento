"""Migração 0003 (aditiva): `ultimo_cliente_em`, `chats_teste` ≤ 20 ids de 24 hex e `chat_id` de 24 hex minúsculo.

A 0001 nunca é editada (checksum no `test_esquema`); aqui se prova que a 0003 entra por cima de 0001→0002 e que cada CHECK novo reprova.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from pathlib import Path

import psycopg
import pytest

from ia_atendimento.migracoes import aplicar, listar
from tests.banco import Banco, apagar_banco, criar_banco, novo_nome

RAIZ = Path(__file__).resolve().parent.parent
MIGRACOES = RAIZ / "migrations"
ARQUIVO_0003 = MIGRACOES / "0003_estado_aditivo.up.sql"
CHAT_OK = "0123456789abcdef01234567"


def _hex24(i: int) -> str:
    return f"{i:024x}"


@pytest.fixture
def vazio(servidor, papeis):
    nome = novo_nome("ia_m3")
    criar_banco(servidor, nome)
    yield Banco(servidor, nome)
    apagar_banco(servidor, nome)


@pytest.fixture
def ate_0002(tmp_path) -> Path:
    destino = tmp_path / "ate0002"
    destino.mkdir()
    for nome in ("0001_esquema.up.sql", "0002_procrastinate.up.sql"):
        shutil.copy(MIGRACOES / nome, destino / nome)
    return destino


# --- o arquivo ------------------------------------------------------------------------------------------------------------------


def test_0003_e_a_terceira_migracao_com_checksum_dos_bytes():
    achadas = listar(MIGRACOES)
    assert [m.id for m in achadas][:3] == ["0001_esquema", "0002_procrastinate", "0003_estado_aditivo"]
    assert achadas[2].checksum == hashlib.sha256(ARQUIVO_0003.read_bytes()).hexdigest()


def test_0003_faz_set_role_dono_e_so_acrescenta():
    texto = ARQUIVO_0003.read_text(encoding="utf-8")
    ativas = [linha for linha in texto.splitlines() if linha.strip() and not linha.lstrip().startswith("--")]
    assert ativas[0].startswith("SET ROLE ia_owner")
    assert ativas[-1].strip().endswith("RESET ROLE;")
    corpo = "\n".join(ativas).upper()
    assert "DROP " not in corpo and "DELETE " not in corpo and "TRUNCATE" not in corpo, "migração aditiva: nada se apaga"


# --- aplicar por cima de 0001+0002 ------------------------------------------------------------------------------------------------


@pytest.mark.banco
def test_aplica_0001_0002_0003_em_sequencia_e_grava_o_ledger(vazio, ate_0002):
    with vazio.conectar(autocommit=False) as conn:
        assert aplicar(conn, ate_0002) == ["0001_esquema", "0002_procrastinate"]
    with vazio.conectar(autocommit=False) as conn:
        assert aplicar(conn, MIGRACOES)[:1] == ["0003_estado_aditivo"]
    with vazio.sessao() as conn:
        ledger = dict(conn.execute("SELECT migracao_id, checksum FROM ia.migracao").fetchall())
    assert ledger["0003_estado_aditivo"] == hashlib.sha256(ARQUIVO_0003.read_bytes()).hexdigest()
    assert ledger["0001_esquema"] == (MIGRACOES / "0001.sha256").read_text(encoding="utf-8").split()[0]


@pytest.mark.banco
def test_ultimo_cliente_em_e_coluna_timestamptz_nula_por_padrao(banco):
    with banco.sessao() as conn:
        linha = conn.execute(
            "SELECT data_type, is_nullable, column_default FROM information_schema.columns "
            "WHERE table_schema='ia' AND table_name='atendimento' AND column_name='ultimo_cliente_em'"
        ).fetchone()
    assert linha == ("timestamp with time zone", "YES", None)


@pytest.mark.banco
def test_ia_app_atualiza_ultimo_cliente_em_mas_continua_sem_atualizar_faixa_e_comissao(banco):
    with banco.sessao() as conn:
        pode = lambda papel, coluna: conn.execute(  # noqa: E731
            "SELECT has_column_privilege(%s, 'ia.atendimento', %s, 'UPDATE')", (papel, coluna)
        ).fetchone()[0]
        assert pode("ia_app_a", "ultimo_cliente_em")
        assert not pode("ia_leitura_a", "ultimo_cliente_em") and not pode("ia_qualidade_a", "ultimo_cliente_em")
        assert not pode("ia_app_a", "faixa_esforco") and not pode("ia_app_a", "comissao_esperada_brl")
        assert pode("ia_app_a", "versao")  # o GRANT da 0001 segue de pé


# --- D2: chats_teste ------------------------------------------------------------------------------------------------------------


def _publicar(conn: psycopg.Connection, nome: str, valor: object, versao: int = 2) -> None:
    conn.execute(
        "INSERT INTO ia.config_versao (nome, versao, valor, publicado_por) VALUES (%s, %s, %s::jsonb, 'teste')",
        (nome, versao, json.dumps(valor)),
    )


@pytest.mark.banco
def test_chats_teste_aceita_ate_20_ids_de_24_hex_minusculo(banco):
    with banco.sessao("ia_app_a") as conn:
        _publicar(conn, "chats_teste", [_hex24(i) for i in range(20)])
        _publicar(conn, "chats_teste", [], versao=3)


@pytest.mark.banco
@pytest.mark.parametrize(
    "valor",
    [
        pytest.param([_hex24(i) for i in range(21)], id="21-ids"),
        pytest.param(["chat_com_sublinhado"], id="aceito-pela-0001-mas-nao-e-hex"),
        pytest.param(["0123456789ABCDEF01234567"], id="hex-maiusculo"),
        pytest.param(["0123456789abcdef0123456"], id="23-hex"),
        pytest.param(["0123456789abcdef012345678"], id="25-hex"),
        pytest.param([CHAT_OK, 7], id="elemento-nao-string"),
        pytest.param({"chat": CHAT_OK}, id="nao-e-array"),
    ],
)
def test_chats_teste_fora_da_regra_reprova_no_check_novo(banco, valor):
    with banco.sessao("ia_app_a") as conn, pytest.raises(psycopg.errors.CheckViolation) as erro:
        _publicar(conn, "chats_teste", valor)
    assert erro.value.diag.constraint_name == "config_versao_chats_teste_check"


@pytest.mark.banco
def test_check_de_chats_teste_nao_mexe_nas_outras_chaves(banco):
    with banco.sessao("ia_app_a") as conn:
        _publicar(conn, "max_abertos", 12)
        _publicar(conn, "chave_aberta_sem_registro", {"qualquer": "coisa"})


# --- D3: chat_id de 24 hex minúsculo ---------------------------------------------------------------------------------------------


def _inserir_atendimento(conn: psycopg.Connection, chat_id: str) -> None:
    chave = f"venda:{uuid.uuid4().hex}"
    conn.execute(
        """INSERT INTO ia.atendimento (origem, chave_logica, idempotency_key, entrada_fingerprint, gatilho, disparado_por,
             criterio_versao, faixa_esforco, pessoa_id, chat_id, phone_id, roteiro_versao, regras_versao, catalogo_versao, motor_versao, modo)
           VALUES ('n8n_braco', %s, encode(sha256(convert_to(%s, 'UTF8')), 'hex'), repeat('a', 64), 'venda', 'operador.teste@exemplo.invalid',
             'c1.0', 'baixa', '11111111-1111-7111-8111-111111111111', %s, '89abcdef0123456789abcdef', 1, 1, 1, 1, 'duble')""",
        (chave, chave, chat_id),
    )


@pytest.mark.banco
def test_atendimento_aceita_chat_id_de_24_hex_minusculo(banco):
    with banco.sessao("ia_app_a") as conn:
        _inserir_atendimento(conn, CHAT_OK)


@pytest.mark.banco
@pytest.mark.parametrize(
    "chat_id",
    [
        pytest.param("chat_com-sublinhado", id="sublinhado-e-hifen-passavam-na-0001"),
        pytest.param("0123456789ABCDEF01234567", id="maiusculo"),
        pytest.param("0123456789abcdef0123456", id="23"),
        pytest.param("0123456789abcdef012345678", id="25"),
        pytest.param("0123456789abcdeg01234567", id="g-nao-e-hex"),
    ],
)
def test_atendimento_com_chat_id_fora_de_24_hex_reprova_no_check_novo(banco, chat_id):
    with banco.sessao("ia_app_a") as conn, pytest.raises(psycopg.errors.CheckViolation) as erro:
        _inserir_atendimento(conn, chat_id)
    assert erro.value.diag.constraint_name == "atendimento_chat_id_hex_check"
