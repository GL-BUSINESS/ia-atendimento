"""Esquema `ia_atendimento` (migração 0001, estudo I): os 350 casos do `i-teste-0001.sh` portados + provas próprias do repo.

A sequência de casos compartilha UM banco (como o script): rode o módulo inteiro, não um caso solto com `-k`.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from collections.abc import Iterator

import psycopg
import pytest

from tests.banco import Banco, apagar_banco, criar_banco, novo_nome
from tests.casos import CASOS
from tests.casos.dsl import APP, FP, LEITURA, P1, P3, SUPER, Ctx, atd, chamada
from tests.conftest import ESTUDO_I, MIGRACOES

CASOS_DO_ESTUDO_I = 350  # «350 casos, 0 falhas» (estudo I §11/§12)
SQL_0001 = MIGRACOES / "0001_esquema.up.sql"


@pytest.fixture(scope="module")
def ctx(servidor, papeis, tmp_path_factory) -> Iterator[Ctx]:
    """Banco só com a infra; o 1º caso aplica a 0001 (sozinha, como o script) pelo `aplicar()` real."""
    nome = novo_nome("ia_seq")
    criar_banco(servidor, nome)
    so_0001 = tmp_path_factory.mktemp("so0001")
    shutil.copy(SQL_0001, so_0001 / SQL_0001.name)
    yield Ctx(Banco(servidor, nome), so_0001, SQL_0001.read_text(encoding="utf-8"))
    apagar_banco(servidor, nome)


def test_total_de_casos_portados():
    assert len(CASOS) == CASOS_DO_ESTUDO_I
    nomes = [c.nome for c in CASOS]
    assert len(set(nomes)) == len(nomes), "nome de caso repetido"


@pytest.mark.parametrize("caso", [pytest.param(c, id=f"{i:03d}-{c.id}") for i, c in enumerate(CASOS, start=1)])
def test_caso_do_estudo_i(ctx: Ctx, caso):
    caso.rodar(ctx)


# --- 0001: checksum e identidade com o estudo I --------------------------------------------------------------------------------


def _bloco_sql(markdown: str) -> str:
    """O mesmo que `awk '/^```sql$/{f=1;next} /^```$/{f=0} f'`: linhas entre as cercas, cada uma com seu \\n."""
    saida, dentro = [], False
    for linha in markdown.splitlines(keepends=True):
        corte = linha.rstrip("\r\n")
        if corte == "```sql":
            dentro = True
        elif corte == "```":
            dentro = False
        elif dentro:
            saida.append(linha)
    return "".join(saida)


def test_checksum_0001():
    esperado, _, nome = (MIGRACOES / "0001.sha256").read_text(encoding="utf-8").strip().partition("  ")
    assert nome == SQL_0001.name
    assert re.fullmatch(r"[0-9a-f]{64}", esperado)
    assert hashlib.sha256(SQL_0001.read_bytes()).hexdigest() == esperado, (
        "0001 foi editada: aplicada não se edita, o desenho novo é uma migração nova"
    )


@pytest.mark.skipif(not ESTUDO_I.exists(), reason="estudo I não está nesta máquina (CI): vale o 0001.sha256")
def test_0001_igual_ao_bloco_do_estudo_i():
    markdown = ESTUDO_I.read_text(encoding="utf-8")
    assert markdown.count("```sql") == 1, "o estudo I deve ter um único bloco sql"
    bloco = _bloco_sql(markdown)
    assert bloco.encode("utf-8") == SQL_0001.read_bytes(), "migrations/0001 difere do bloco do estudo I (re-extraia; não edite o DDL aqui)"
    declarado = re.search(r"sha256 do bloco `sql` desta versão[^`]*`[^`]*`[^`]*`([0-9a-f]{64})`", markdown)
    if declarado:
        assert hashlib.sha256(bloco.encode("utf-8")).hexdigest() == declarado.group(1)


# --- seeds e contagens (estudo I §11) -------------------------------------------------------------------------------------------


def _config(banco: Banco, nome: str) -> str:
    return banco.escalar(APP, f"SELECT valor FROM ia.config_versao WHERE nome='{nome}' ORDER BY versao DESC LIMIT 1")


def test_seeds(banco: Banco):
    assert _config(banco, "ia_ativa") == "false"
    assert _config(banco, "modo") == '"duble"'
    assert _config(banco, "alcada_valor_max_brl") == "6000"
    assert _config(banco, "bancos_digitacao") == '["FACTA"]'
    assert _config(banco, "teto_mensal_brl") == "2000"
    assert _config(banco, "subteto_dia") == "100"
    assert _config(banco, "max_disparos_dia") == "10"
    assert _config(banco, "max_abertos") == "10"
    assert _config(banco, "verificador_ativo") == "false"
    assert _config(banco, "bloqueio_entrada") == "false"
    assert _config(banco, "agenda_ativa") == "false"
    assert _config(banco, "chats_teste") == "[]"
    assert banco.escalar(APP, "SELECT valor->'limites_brl' FROM ia.config_versao WHERE nome='faixas_esforco'") == "[150, 400, 800]"
    assert banco.escalar(
        APP, "SELECT string_agg(k, ',' ORDER BY k) FROM ia.config_versao, jsonb_object_keys(valor->'faixas') k WHERE nome='faixas_esforco'"
    ) == ("alta,baixa,media,muito_alta")
    feriados = banco.escalar(APP, "SELECT valor->'feriados' FROM ia.config_versao WHERE nome='calendario_bloqueio'")
    assert "2026-11-02" in feriados and "2026-11-20" in feriados
    assert (
        banco.escalar(APP, "SELECT valor->'janelas'->0->>'de' FROM ia.config_versao WHERE nome='calendario_bloqueio'")
        == "2026-11-20T22:00:00-03:00"
    )


def test_seeds_27_chaves_todas_na_versao_1_e_do_autor_da_migracao(banco: Banco):
    assert banco.escalar(APP, "SELECT count(DISTINCT nome) FROM ia.config_versao") == "27"
    assert banco.escalar(APP, "SELECT count(*) FROM ia.config_versao WHERE versao <> 1 OR publicado_por <> 'migracao:0001'") == "0"


def test_seeds_nao_citam_anthropic_nem_a_api_oficial_da_deepseek(banco: Banco):
    achou = banco.escalar(
        APP, "SELECT count(*) FROM ia.config_versao WHERE valor::text ~* '(anthropic|claude|sonnet|opus|haiku|deepseek\\.com)'"
    )
    assert achou == "0"
    modelos = banco.escalar(
        APP,
        "SELECT string_agg(DISTINCT v.value->>'modelo' || '@' || (v.value->>'provedor'), ',') FROM ia.config_versao c, jsonb_each(c.valor) v WHERE c.nome='modelo_por_faixa'",
    )
    assert modelos == "deepseek-v4p1-flash-1017@fireworks-us"


def test_contagem_de_objetos_do_estudo(banco: Banco):
    assert banco.escalar(APP, "SELECT count(*) FROM pg_tables WHERE schemaname='ia'") == "18"
    assert banco.escalar(APP, "SELECT count(*) FROM pg_views WHERE schemaname='ia'") == "1"
    assert banco.escalar(
        APP,
        "SELECT string_agg(proname, ',' ORDER BY proname) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname='ia'",
    ) == ("fn_atendimento_podar,fn_atendimento_terminal,fn_texto_podar")  # + o trigger de terminal absorvente (0003)
    assert (
        banco.escalar(APP, "SELECT rolname FROM pg_roles r JOIN pg_database d ON d.datdba = r.oid WHERE d.datname = current_database()")
        == "ia_owner"
    )


# --- papéis: ia_app sem DDL e sem DELETE ------------------------------------------------------------------------------------------

UPDATE_PERMITIDO = {"atendimento_resultado", "confirmacao", "ferramenta_chamada", "cofre", "agendamento"}  # + colunas de `atendimento`


def violacoes_de_privilegio(banco: Banco) -> list[str]:
    """Tudo que o `ia_app` NÃO deveria poder em `ia`, lido do catálogo (não de tentativas)."""
    achados: list[str] = []
    with banco.sessao() as conn:
        tabelas = [r[0] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='ia' ORDER BY 1").fetchall()]
        for t in tabelas:
            for priv in ("DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
                if conn.execute("SELECT has_table_privilege('ia_app', %s, %s)", (f"ia.{t}", priv)).fetchone() == (True,):
                    achados.append(f"{priv} em ia.{t}")
            pode_update_tabela = conn.execute("SELECT has_table_privilege('ia_app', %s, 'UPDATE')", (f"ia.{t}",)).fetchone() == (True,)
            if pode_update_tabela and t not in UPDATE_PERMITIDO:
                achados.append(f"UPDATE (tabela inteira) em ia.{t}")
        for schema in ("ia", "procrastinate"):
            if conn.execute("SELECT has_schema_privilege('ia_app', %s, 'CREATE')", (schema,)).fetchone() == (True,):
                achados.append(f"CREATE no schema {schema}")
        imutaveis = [
            "pessoa_id",
            "chat_id",
            "faixa_esforco",
            "comissao_esperada_brl",
            "chave_logica",
            "idempotency_key",
            "origem",
            "gatilho",
            "modo",
            "iniciado_em",
        ]
        for coluna in imutaveis:
            if conn.execute("SELECT has_column_privilege('ia_app', 'ia.atendimento', %s, 'UPDATE')", (coluna,)).fetchone() == (True,):
                achados.append(f"UPDATE em ia.atendimento.{coluna}")
        if conn.execute(
            "SELECT rolsuper OR rolcreaterole OR rolcreatedb OR rolbypassrls FROM pg_roles WHERE rolname='ia_app'"
        ).fetchone() != (False,):
            achados.append("ia_app com atributo de superusuário/criação/bypassrls")
    return achados


def test_ia_app_sem_ddl_delete(banco: Banco):
    assert violacoes_de_privilegio(banco) == []


def test_violacoes_de_privilegio_enxerga_um_grant_indevido(banco: Banco):
    """Reprova sem a mudança: se alguém der DELETE/CREATE ao ia_app, o teste acima acusa."""
    with banco.sessao() as conn:
        conn.execute("SET ROLE ia_owner")
        conn.execute("GRANT DELETE ON ia.passo TO ia_app")
        conn.execute("GRANT CREATE ON SCHEMA ia TO ia_app")
        conn.execute("GRANT UPDATE ON ia.opt_out TO ia_app")
    assert set(violacoes_de_privilegio(banco)) == {"DELETE em ia.passo", "CREATE no schema ia", "UPDATE (tabela inteira) em ia.opt_out"}


@pytest.mark.parametrize(
    "ddl",
    [
        "CREATE TABLE ia.intruso (x int)",
        "CREATE SCHEMA intruso",
        "CREATE FUNCTION ia.intruso() RETURNS int LANGUAGE sql AS 'SELECT 1'",
        "ALTER TABLE ia.passo ADD COLUMN x int",
        "ALTER TABLE ia.atendimento DROP COLUMN pessoa_id",
        "DROP TABLE ia.passo",
        "DROP SCHEMA ia CASCADE",
        "DROP FUNCTION ia.fn_texto_podar(integer, integer, integer)",
        "TRUNCATE ia.passo",
        "TRUNCATE ia.atendimento CASCADE",
        "DELETE FROM ia.passo",
        "DELETE FROM ia.atendimento",
        "DELETE FROM ia.config_versao",
        "DELETE FROM ia.opt_out",
        "DELETE FROM ia.ferramenta_chamada",
        "DELETE FROM ia.conversa_cifrada",
        "DELETE FROM ia.cofre",
        "UPDATE ia.passo SET texto = 'x'",
        "UPDATE ia.config_versao SET valor = 'true'",
        "UPDATE ia.opt_out SET registrado_por = 'x'",
        "CREATE ROLE intruso2",
        "ALTER ROLE ia_app SUPERUSER",
        "DROP TABLE procrastinate.procrastinate_jobs",
        "CREATE TABLE procrastinate.intruso (x int)",
    ],
)
def test_ia_app_recusa_ddl_e_delete(banco: Banco, ddl: str):
    with banco.sessao(APP) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(ddl)


# --- controle negativo: as travas do banco existem por causa destes índices ----------------------------------------------------


def _0001_sem_indices(*nomes: str) -> str:
    sql = SQL_0001.read_text(encoding="utf-8")
    for nome in nomes:
        sql, trocas = re.subn(rf"^CREATE UNIQUE INDEX IF NOT EXISTS {nome} ON [^\n]*\n", "", sql, flags=re.MULTILINE)
        assert trocas == 1, nome
    return sql


@pytest.fixture
def sem_travas(servidor, papeis) -> Iterator[Banco]:
    nome = novo_nome("ia_neg")
    criar_banco(servidor, nome)
    banco = Banco(servidor, nome)
    with banco.sessao() as conn:
        conn.execute(_0001_sem_indices("atendimento_ativo_chat_uq", "ferramenta_chamada_t7_viva_uq"))
    yield banco
    apagar_banco(servidor, nome)


def _abrir_com_t7(conn: psycopg.Connection, chat: str, hex2: str, pessoa: str) -> None:
    """Atendimento + confirmação aceita-pendente + T7 reservada, como o orquestrador faria."""
    conn.execute(atd(chat, "venda:" + hex2 * 16, FP, pessoa))
    atendimento = conn.execute("SELECT atendimento_id FROM ia.atendimento WHERE chave_logica = %s", ("venda:" + hex2 * 16,)).fetchone()[0]
    confirmacao = conn.execute(
        "INSERT INTO ia.confirmacao (atendimento_id, tipo, banco, oferta_versao, valores_hash, texto_id, pergunta_ordem)"
        " VALUES (%s,'digitacao','FACTA',3,%s,'conf_digitacao_v1',2) RETURNING confirmacao_id",
        (atendimento, FP),
    ).fetchone()[0]
    conn.execute(
        chamada(
            str(atendimento),
            pessoa,
            "t7",
            f"t7:{atendimento}:FACTA:1:1:1",
            ", banco, args_hash, confirmacao_id",
            f", 'FACTA', '{FP}', '{confirmacao}'",
        )
    )


def test_controle_negativo_sem_o_indice_dois_atendimentos_no_mesmo_chat_entram(sem_travas: Banco):
    with sem_travas.sessao(APP) as conn:
        conn.execute(atd("chatNEG00001", "venda:" + "aa" * 16, FP, P1))
        conn.execute(atd("chatNEG00001", "venda:" + "bb" * 16, FP, P3))
        assert conn.execute("SELECT count(*) FROM ia.atendimento WHERE chat_id = 'chatNEG00001' AND estado <> 'encerrado'").fetchone() == (
            2,
        )


def test_controle_negativo_sem_o_indice_duas_t7_vivas_da_mesma_pessoa_entram(sem_travas: Banco):
    with sem_travas.sessao(APP) as conn:
        _abrir_com_t7(conn, "chatNEG00002", "cc", P1)
        _abrir_com_t7(conn, "chatNEG00003", "dd", P1)  # outra conversa, mesma pessoa, mesmo banco: só a trava t7_viva_uq impedia
        assert conn.execute("SELECT count(*) FROM ia.ferramenta_chamada WHERE ferramenta='t7' AND pessoa_id=%s", (P1,)).fetchone() == (2,)


def test_banco_intacto_recusa_duas_t7_vivas_da_mesma_pessoa(banco: Banco):
    with banco.sessao(APP) as conn:  # com a 0003 o chat_id é de 24 hex minúsculo
        _abrir_com_t7(conn, "00000000000000000000aa02", "cc", P1)
        with pytest.raises(psycopg.errors.UniqueViolation) as erro:
            _abrir_com_t7(conn, "00000000000000000000aa03", "dd", P1)
    assert erro.value.diag.constraint_name == "ferramenta_chamada_t7_viva_uq"


def test_ia_app_nao_concede_privilegio_a_ninguem(banco: Banco):
    """GRANT sem grant option vira aviso (nada é concedido); a prova é o catálogo."""
    with banco.sessao(APP) as conn:
        conn.execute("GRANT ALL ON ia.passo TO PUBLIC")
    assert banco.escalar(SUPER, "SELECT has_table_privilege('intruso', 'ia.passo', 'SELECT')") == "f"
    assert violacoes_de_privilegio(banco) == []


def test_banco_intacto_recusa_o_que_o_controle_negativo_deixa_passar(banco: Banco):
    with banco.sessao(APP) as conn:
        conn.execute(atd("00000000000000000000aa01", "venda:" + "aa" * 16, FP, P1))
        with pytest.raises(psycopg.errors.UniqueViolation) as erro:
            conn.execute(atd("00000000000000000000aa01", "venda:" + "bb" * 16, FP, P3))
    assert erro.value.diag.constraint_name == "atendimento_ativo_chat_uq"


def test_leitura_nao_alcanca_texto_nem_cofre(banco: Banco):
    for tabela in ("conversa_cifrada", "cofre", "qualidade_humana", "qualidade_amostra"):
        with banco.sessao(LEITURA) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(f"SELECT 1 FROM ia.{tabela}")
