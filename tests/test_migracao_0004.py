"""Migração 0004 (aditiva): `ia.fn_anexar_rpa` (D5) e `ia.espelho_evento` (D6) do contrato 08 §11.

A 0001 e a 0003 nunca são editadas; aqui se prova o checksum, a função (único caminho de escrita em `passo`), as permissões negativas
(`ia_app` sem UPDATE direto em `passo`; `ia_leitura` sem a outbox) e que reaplicar é recusado pelo ledger.
"""

from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path

import psycopg
import pytest

from ia_atendimento.migracoes import aplicar, listar
from tests.apoio_b12 import CHAT, novo_atendimento
from tests.banco import Banco, apagar_banco, criar_banco, novo_nome

RAIZ = Path(__file__).resolve().parent.parent
MIGRACOES = RAIZ / "migrations"
ARQUIVO_0004 = MIGRACOES / "0004_anexo_rpa_e_espelho.up.sql"
ID_0004 = "0004_anexo_rpa_e_espelho"
RPA_A = "rpa_abcdefgh01"
RPA_B = "rpa_abcdefgh02"
HASH16 = "0123456789abcdef"


@pytest.fixture
def vazio(servidor, papeis):
    nome = novo_nome("ia_m4")
    criar_banco(servidor, nome)
    yield Banco(servidor, nome)
    apagar_banco(servidor, nome)


@pytest.fixture
def ate_0003(tmp_path) -> Path:
    destino = tmp_path / "ate0003"
    destino.mkdir()
    for nome in ("0001_esquema.up.sql", "0002_procrastinate.up.sql", "0003_estado_aditivo.up.sql"):
        shutil.copy(MIGRACOES / nome, destino / nome)
    return destino


def _passo_mensagem(conn: psycopg.Connection, atd: uuid.UUID, ordem: int, chave: str, **extra: object) -> int:
    """`mensagem_recebida` mínima válida (as cinco colunas da forma + turno/fase); devolve o `passo_id`."""
    colunas = {
        "atendimento_id": atd, "ordem": ordem, "tipo": "mensagem_recebida", "texto": "Cliente enviou texto (3 caracteres).",
        "turno": 1, "fase": "E1", "msg_chave": chave, "msg_fingerprint": "b" * 64, "msg_tipo": "texto", "msg_tamanho": 3,
        "origem_evento": "webhook", **extra,
    }  # fmt: skip
    linha = conn.execute(
        f"INSERT INTO ia.passo ({', '.join(colunas)}) VALUES ({', '.join(['%s'] * len(colunas))}) RETURNING passo_id",
        list(colunas.values()),
    ).fetchone()
    assert linha is not None
    return linha[0]


# --- o arquivo -------------------------------------------------------------------------------------------------------------------


def test_0004_e_a_quarta_migracao_com_checksum_dos_bytes():
    achadas = listar(MIGRACOES)
    assert [m.id for m in achadas][:4] == ["0001_esquema", "0002_procrastinate", "0003_estado_aditivo", ID_0004]
    assert achadas[3].checksum == hashlib.sha256(ARQUIVO_0004.read_bytes()).hexdigest()


def test_0004_faz_set_role_dono_e_so_acrescenta():
    texto = ARQUIVO_0004.read_text(encoding="utf-8")
    ativas = [linha for linha in texto.splitlines() if linha.strip() and not linha.lstrip().startswith("--")]
    assert ativas[0].startswith("SET ROLE ia_owner")
    assert ativas[-1].strip().endswith("RESET ROLE;")
    corpo = "\n".join(ativas).upper().replace("ON DELETE CASCADE", "")  # a FK em cascata é o desenho (a poda leva a outbox junto)
    assert "DROP " not in corpo and "DELETE " not in corpo and "TRUNCATE" not in corpo and "ALTER TABLE" not in corpo


@pytest.mark.banco
def test_aplica_por_cima_da_0003_e_grava_o_ledger(vazio, ate_0003):
    with vazio.conectar(autocommit=False) as conn:
        assert aplicar(conn, ate_0003) == ["0001_esquema", "0002_procrastinate", "0003_estado_aditivo"]
    with vazio.conectar(autocommit=False) as conn:
        assert aplicar(conn, MIGRACOES) == [ID_0004]
    with vazio.sessao() as conn:
        ledger = dict(conn.execute("SELECT migracao_id, checksum FROM ia.migracao").fetchall())
    assert ledger[ID_0004] == hashlib.sha256(ARQUIVO_0004.read_bytes()).hexdigest()


@pytest.mark.banco
def test_reaplicar_e_recusado_pelo_ledger(vazio):
    """`aplicar` pula o que está no ledger; o `psql -1` do dono (arquivo + INSERT do ledger) falha na PK e desfaz tudo."""
    with vazio.conectar(autocommit=False) as conn:
        aplicar(conn, MIGRACOES)
        assert aplicar(conn, MIGRACOES) == []
    soma = hashlib.sha256(ARQUIVO_0004.read_bytes()).hexdigest()
    epilogo = f"SET ROLE ia_owner; INSERT INTO ia.migracao (migracao_id, checksum) VALUES ('{ID_0004}', '{soma}'); RESET ROLE;"
    with vazio.conectar(autocommit=False) as conn, pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
        conn.execute(ARQUIVO_0004.read_text(encoding="utf-8") + epilogo)


# --- D5: fn_anexar_rpa ------------------------------------------------------------------------------------------------------------


@pytest.mark.banco
def test_funcao_e_security_definer_do_dono_com_search_path_fixo(banco):
    with banco.sessao() as conn:
        linha = conn.execute(
            "SELECT p.prosecdef, pg_get_userbyid(p.proowner), p.proconfig FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'ia' AND p.proname = 'fn_anexar_rpa'"
        ).fetchone()
    assert linha == (True, "ia_owner", ["search_path=pg_catalog, ia"])


@pytest.mark.banco
def test_so_ia_app_executa_a_funcao(banco):
    with banco.sessao() as conn:
        pode = lambda papel: conn.execute(  # noqa: E731
            "SELECT has_function_privilege(%s, 'ia.fn_anexar_rpa(bigint, text)', 'EXECUTE')", (papel,)
        ).fetchone()[0]
        assert pode("ia_app_a")
        assert not pode("ia_leitura_a") and not pode("ia_qualidade_a") and not pode("intruso")
        assert not conn.execute(
            "SELECT bool_or(x.grantee = 0) FROM pg_proc p, LATERAL aclexplode(p.proacl) x WHERE p.proname = 'fn_anexar_rpa'"
        ).fetchone()[0], "PUBLIC não executa"


@pytest.mark.banco
def test_ia_app_executa_a_funcao_e_nao_faz_update_direto_em_passo(banco):
    with banco.sessao("ia_app_a") as conn:
        atd = novo_atendimento(conn)
        passo = _passo_mensagem(conn, atd, 1, f"cg:{CHAT}:{HASH16}")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE ia.passo SET msg_chave_rpa = %s WHERE passo_id = %s", (RPA_A, passo))
        assert conn.execute("SELECT ia.fn_anexar_rpa(%s, %s)", (passo, RPA_A)).fetchone() == (True,)
        assert conn.execute("SELECT msg_chave_rpa FROM ia.passo WHERE passo_id = %s", (passo,)).fetchone() == (RPA_A,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE ia.passo SET texto = 'x' WHERE passo_id = %s", (passo,))


@pytest.mark.banco
def test_funcao_so_anexa_uma_vez_e_so_em_mensagem_do_webhook(banco):
    with banco.sessao("ia_app_a") as conn:
        atd = novo_atendimento(conn)
        webhook = _passo_mensagem(conn, atd, 1, f"cg:{CHAT}:{HASH16}")
        do_rpa = _passo_mensagem(conn, atd, 2, f"rpa:{RPA_B}", origem_evento="reconciliacao")
        outro_tipo = conn.execute(
            "INSERT INTO ia.passo (atendimento_id, ordem, tipo, texto, turno, fase, peca) VALUES (%s, 3, 'erro', 'Erro na peça receptor.', 1, 'E1', 'receptor') "
            "RETURNING passo_id",
            (atd,),
        ).fetchone()[0]
        assert conn.execute("SELECT ia.fn_anexar_rpa(%s, %s)", (webhook, RPA_A)).fetchone() == (True,)
        assert conn.execute("SELECT ia.fn_anexar_rpa(%s, %s)", (webhook, "rpa_outro_id01")).fetchone() == (False,), "já tem contraparte"
        assert conn.execute("SELECT ia.fn_anexar_rpa(%s, %s)", (do_rpa, RPA_A)).fetchone() == (False,), "a linha nasceu do RPA"
        assert conn.execute("SELECT ia.fn_anexar_rpa(%s, %s)", (outro_tipo, RPA_A)).fetchone() == (False,), "só mensagem_recebida"
        assert conn.execute("SELECT ia.fn_anexar_rpa(-1, %s)", (RPA_A,)).fetchone() == (False,), "passo inexistente"


@pytest.mark.banco
def test_o_mesmo_id_do_rpa_nao_anexa_a_dois_passos(banco):
    with banco.sessao("ia_app_a") as conn:
        atd = novo_atendimento(conn)
        a = _passo_mensagem(conn, atd, 1, f"cg:{CHAT}:{HASH16}")
        b = _passo_mensagem(conn, atd, 2, f"cg:{CHAT}:fedcba9876543210")
        assert conn.execute("SELECT ia.fn_anexar_rpa(%s, %s)", (a, RPA_A)).fetchone() == (True,)
        with pytest.raises(psycopg.errors.UniqueViolation):
            conn.execute("SELECT ia.fn_anexar_rpa(%s, %s)", (b, RPA_A))


@pytest.mark.banco
def test_funcao_recusa_id_do_rpa_fora_do_formato_pelo_check_da_0001(banco):
    with banco.sessao("ia_app_a") as conn:
        atd = novo_atendimento(conn)
        passo = _passo_mensagem(conn, atd, 1, f"cg:{CHAT}:{HASH16}")
        with pytest.raises(psycopg.errors.CheckViolation) as erro:
            conn.execute("SELECT ia.fn_anexar_rpa(%s, 'curto')", (passo,))
        assert erro.value.diag.constraint_name == "passo_msg_forma_check"


# --- D6: espelho_evento ------------------------------------------------------------------------------------------------------------


@pytest.mark.banco
def test_espelho_evento_ia_app_insere_atualiza_so_as_quatro_colunas_e_nao_apaga(banco):
    with banco.sessao("ia_app_a") as conn:
        atd = novo_atendimento(conn)
        conn.execute("INSERT INTO ia.espelho_evento (atendimento_id, seq, evento, chave) VALUES (%s, 1, 'assumiu', 'venda:abc')", (atd,))
        conn.execute(
            "UPDATE ia.espelho_evento SET tentativas = 1, enviado_em = now(), resultado = 'aplicado' WHERE atendimento_id = %s", (atd,)
        )
        for coluna in ("evento", "chave", "seq", "detalhe", "criado_em"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(f"UPDATE ia.espelho_evento SET {coluna} = {coluna} WHERE atendimento_id = %s", (atd,))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM ia.espelho_evento WHERE atendimento_id = %s", (atd,))


@pytest.mark.banco
def test_ia_leitura_e_ia_qualidade_nao_leem_o_espelho_evento(banco):
    for papel in ("ia_leitura_a", "ia_qualidade_a", "intruso"):
        with banco.sessao(papel) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT count(*) FROM ia.espelho_evento")
    with banco.sessao() as conn:
        assert not conn.execute("SELECT has_table_privilege('ia_leitura', 'ia.espelho_evento', 'SELECT')").fetchone()[0]
        assert not conn.execute(
            "SELECT bool_or(x.grantee = 0) FROM pg_class c, LATERAL aclexplode(c.relacl) x WHERE c.relname = 'espelho_evento'"
        ).fetchone()[0]


@pytest.mark.banco
@pytest.mark.parametrize(
    "linha,restricao",
    [
        pytest.param("(%s, 0, 'assumiu', 'venda:abc')", "espelho_evento_seq_check", id="seq-zero"),
        pytest.param("(%s, 1, 'abriu', 'venda:abc')", "espelho_evento_evento_check", id="evento-fora-do-vocabulario"),
    ],
)
def test_espelho_evento_checks(banco, linha, restricao):
    with banco.sessao("ia_app_a") as conn:
        atd = novo_atendimento(conn)
        with pytest.raises(psycopg.errors.CheckViolation) as erro:
            conn.execute(f"INSERT INTO ia.espelho_evento (atendimento_id, seq, evento, chave) VALUES {linha}", (atd,))
        assert erro.value.diag.constraint_name == restricao


@pytest.mark.banco
def test_espelho_evento_seq_e_unico_por_atendimento_e_a_poda_leva_a_outbox_junto(banco):
    with banco.sessao("ia_app_a") as conn:
        atd = novo_atendimento(conn)
        conn.execute("INSERT INTO ia.espelho_evento (atendimento_id, seq, evento, chave) VALUES (%s, 1, 'assumiu', 'venda:abc')", (atd,))
        with pytest.raises(psycopg.errors.UniqueViolation):
            conn.execute("INSERT INTO ia.espelho_evento (atendimento_id, seq, evento, chave) VALUES (%s, 1, 'pausou', 'venda:abc')", (atd,))
    with banco.sessao() as conn:  # encerrado há mais de 365 d: a poda (SECURITY DEFINER) apaga o atendimento e a FK em cascata, a outbox
        conn.execute(
            "UPDATE ia.atendimento SET estado = 'encerrado', desfecho = 'sem_venda', encerrado_em = now() - interval '400 days', lease_ate = NULL,"
            " assumido_em = now() WHERE atendimento_id = %s",
            (atd,),
        )
        conn.execute("SELECT * FROM ia.fn_atendimento_podar(365)")
        assert conn.execute("SELECT count(*) FROM ia.espelho_evento WHERE atendimento_id = %s", (atd,)).fetchone() == (0,)


# --- o passo a passo do dono (docs) é testado contra o banco -----------------------------------------------------------------------


@pytest.mark.banco
@pytest.mark.parametrize("doc", [RAIZ / "docs" / "OPERACAO.md", MIGRACOES / "README.md"], ids=lambda d: d.name)
def test_docs_documentam_a_0004_com_o_ledger_na_mesma_transacao(vazio, ate_0003, doc):
    from tests.test_migracoes import _epilogo_documentado

    with vazio.conectar(autocommit=False) as conn:
        aplicar(conn, ate_0003)
    corpo = ARQUIVO_0004.read_text(encoding="utf-8")
    soma = hashlib.sha256(ARQUIVO_0004.read_bytes()).hexdigest()
    ruim = _epilogo_documentado(doc, ID_0004, "xyz")  # checksum inválido: o CHECK do ledger recusa
    with vazio.conectar(autocommit=False) as conn, pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
        conn.execute(corpo + ruim)
    with vazio.sessao() as conn:  # nada ficou: nem a função nem a tabela
        assert conn.execute("SELECT to_regclass('ia.espelho_evento'), to_regprocedure('ia.fn_anexar_rpa(bigint, text)')").fetchone() == (
            None,
            None,
        )
    with vazio.conectar(autocommit=False) as conn, conn.transaction():
        conn.execute(corpo + _epilogo_documentado(doc, ID_0004, soma))
    with vazio.sessao() as conn:
        assert conn.execute("SELECT checksum FROM ia.migracao WHERE migracao_id = %s", (ID_0004,)).fetchone() == (soma,)
