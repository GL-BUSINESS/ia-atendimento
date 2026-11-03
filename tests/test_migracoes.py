from __future__ import annotations

import hashlib
import re
import shutil
from importlib.metadata import version
from pathlib import Path

import psycopg
import pytest
from procrastinate.schema import SchemaManager

from ia_atendimento.migracoes import (
    ChecksumDivergente,
    MigracaoErro,
    MigracoesPendentes,
    aplicar,
    conferir,
    listar,
    main,
)
from tests.banco import Banco, apagar_banco, criar_banco, novo_nome

RAIZ = Path(__file__).resolve().parent.parent
MIGRACOES = RAIZ / "migrations"


TODAS = ["0001_esquema", "0002_procrastinate", "0003_estado_aditivo", "0004_anexo_rpa_e_espelho"]  # a pasta migrations/ inteira, em ordem


def _sha(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


@pytest.fixture
def vazio(servidor, papeis):
    """Banco só com a infra (papéis e database), como a infra do estudo E entrega antes das migrações."""
    nome = novo_nome("ia_vazio")
    criar_banco(servidor, nome)
    yield Banco(servidor, nome)
    apagar_banco(servidor, nome)


def _ledger(banco: Banco) -> dict[str, str]:
    with banco.sessao() as conn:
        return dict(conn.execute("SELECT migracao_id, checksum FROM ia.migracao ORDER BY 1").fetchall())


# --- listar / arquivos (sem banco) ---------------------------------------------------------------------------------


def test_listar_devolve_em_ordem_com_checksum_dos_bytes():
    achadas = listar(MIGRACOES)
    assert [m.id for m in achadas] == TODAS
    assert [m.checksum for m in achadas] == [_sha(MIGRACOES / f"{i}.up.sql") for i in TODAS]


def test_listar_ignora_o_que_nao_e_migracao(tmp_path):
    (tmp_path / "README.md").write_text("x")
    (tmp_path / "0001.sha256").write_text("x")
    (tmp_path / "0001_a.up.sql").write_text("SELECT 1;")
    assert [m.id for m in listar(tmp_path)] == ["0001_a"]


def test_listar_recusa_buraco_na_numeracao(tmp_path):
    (tmp_path / "0001_a.up.sql").write_text("SELECT 1;")
    (tmp_path / "0003_c.up.sql").write_text("SELECT 1;")
    with pytest.raises(MigracaoErro, match="0002"):
        listar(tmp_path)


def test_listar_recusa_numero_repetido(tmp_path):
    (tmp_path / "0001_a.up.sql").write_text("SELECT 1;")
    (tmp_path / "0001_b.up.sql").write_text("SELECT 1;")
    with pytest.raises(MigracaoErro, match="repetid"):
        listar(tmp_path)


def test_listar_recusa_nome_fora_do_padrao_do_ledger(tmp_path):
    (tmp_path / "0001_Esquema Novo.up.sql").write_text("SELECT 1;")
    with pytest.raises(MigracaoErro):
        listar(tmp_path)


def test_listar_diretorio_vazio_ou_inexistente_recusado(tmp_path):
    with pytest.raises(MigracaoErro):
        listar(tmp_path)
    with pytest.raises(MigracaoErro):
        listar(tmp_path / "nao-existe")


# --- 0002 (Procrastinate) ---------------------------------------------------------------------------------------------


def test_0002_corpo_e_o_do_pacote_pinado():
    """Se alguém subir a versão do procrastinate sem regerar a 0002 (scripts/gerar_0002.py), este teste reprova."""
    texto = (MIGRACOES / "0002_procrastinate.up.sql").read_text(encoding="utf-8")
    versao = version("procrastinate")
    inicio = f"-- >>> procrastinate {versao} schema.sql\n"
    fim = f"-- <<< procrastinate {versao} schema.sql\n"
    assert inicio in texto and fim in texto, f"0002 não foi gerada com procrastinate {versao}"
    corpo = texto.split(inicio, 1)[1].split(fim, 1)[0]
    assert corpo == SchemaManager.get_schema()
    assert re.search(r"^SET ROLE ia_owner; SET search_path = procrastinate, public;$", texto, re.MULTILINE)
    assert texto.rstrip().endswith("RESET search_path; RESET ROLE;")


# --- aplicar (banco) --------------------------------------------------------------------------------------------------


@pytest.mark.banco
def test_aplicar_em_banco_vazio_aplica_tudo_e_grava_o_ledger(vazio):
    with vazio.conectar(autocommit=False) as conn:
        feitas = aplicar(conn, MIGRACOES)
    assert feitas == TODAS
    assert _ledger(vazio) == {i: _sha(MIGRACOES / f"{i}.up.sql") for i in TODAS}
    with vazio.sessao() as conn:
        assert conn.execute("SELECT aplicada_por FROM ia.migracao WHERE migracao_id = '0001_esquema'").fetchone() == ("postgres",)


@pytest.mark.banco
def test_aplicar_de_novo_e_no_op(vazio):
    with vazio.conectar(autocommit=False) as conn:
        aplicar(conn, MIGRACOES)
        antes = _ledger(vazio)
        assert aplicar(conn, MIGRACOES) == []
    assert _ledger(vazio) == antes


@pytest.mark.banco
def test_aplicar_registra_0001_ja_aplicada_a_mao_sem_reaplicar_a_0002(vazio, so_0001):
    """Fluxo do dono (psql): 0001 aplicada sem ledger. `aplicar` é idempotente na 0001 e só registra."""
    sql_0001 = (MIGRACOES / "0001_esquema.up.sql").read_text(encoding="utf-8")
    with vazio.sessao() as conn:
        conn.execute(sql_0001)
    with vazio.conectar(autocommit=False) as conn:
        assert aplicar(conn, MIGRACOES) == TODAS


@pytest.mark.banco
def test_checksum_divergente_para_antes_de_aplicar_qualquer_coisa(vazio, tmp_path):
    copia = tmp_path / "copia"
    shutil.copytree(MIGRACOES, copia)
    with vazio.conectar(autocommit=False) as conn:
        aplicar(conn, copia)
    (copia / "0002_procrastinate.up.sql").write_text(
        (copia / "0002_procrastinate.up.sql").read_text(encoding="utf-8") + "\n-- editada depois de aplicada\n", encoding="utf-8"
    )
    with vazio.conectar(autocommit=False) as conn, pytest.raises(ChecksumDivergente, match="0002_procrastinate"):
        aplicar(conn, copia)


@pytest.mark.banco
def test_migracao_com_erro_desfaz_tudo_e_nao_grava_ledger(vazio, tmp_path):
    copia = tmp_path / "copia"
    shutil.copytree(MIGRACOES, copia)
    (copia / "0005_quebrada.up.sql").write_text("CREATE TABLE ia.zz_meio (x int); SELECT 1/0;", encoding="utf-8")
    with vazio.conectar(autocommit=False) as conn, pytest.raises(psycopg.errors.DivisionByZero):
        aplicar(conn, copia)
    ledger = _ledger(vazio)
    assert set(ledger) == set(TODAS)  # as boas ficaram; a 0005 não
    with vazio.sessao() as conn:
        assert conn.execute("SELECT to_regclass('ia.zz_meio')").fetchone() == (None,)


@pytest.mark.banco
def test_aplicar_exige_conexao_sem_transacao_aberta(vazio):
    with vazio.conectar(autocommit=False) as conn:
        conn.execute("SELECT 1")
        with pytest.raises(MigracaoErro, match="transação"):
            aplicar(conn, MIGRACOES)


@pytest.mark.banco
def test_ledger_nasce_com_o_papel_dono_e_ia_app_so_le(vazio):
    with vazio.conectar(autocommit=False) as conn:
        aplicar(conn, MIGRACOES)
    with vazio.sessao("ia_app_a") as conn:
        assert conn.execute("SELECT count(*) FROM ia.migracao").fetchone() == (len(TODAS),)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("INSERT INTO ia.migracao VALUES ('0004_x', %s)", ("a" * 64,))


@pytest.mark.banco
def test_conferir_ok_pendente_e_divergente(vazio, tmp_path, so_0001):
    with vazio.conectar(autocommit=False) as conn:
        with pytest.raises(MigracoesPendentes, match="0001_esquema"):  # banco vazio: nem o ledger existe
            conferir(conn, MIGRACOES)
        aplicar(conn, so_0001)
        with pytest.raises(MigracoesPendentes, match="0002_procrastinate"):
            conferir(conn, MIGRACOES)
        aplicar(conn, MIGRACOES)
        conferir(conn, MIGRACOES)  # ok: não levanta
    copia = tmp_path / "copia"
    shutil.copytree(MIGRACOES, copia)
    (copia / "0001_esquema.up.sql").write_bytes((copia / "0001_esquema.up.sql").read_bytes() + b"-- x\n")
    with vazio.conectar(autocommit=False) as conn, pytest.raises(ChecksumDivergente, match="0001_esquema"):
        conferir(conn, copia)


@pytest.mark.banco
def test_0002_cria_a_fila_e_ia_app_opera_com_search_path(banco):
    """Procrastinate roda com search_path = procrastinate, public (função/trigger usam nomes sem schema)."""
    with banco.sessao("ia_app_a") as conn:
        tabelas = {r[0] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'procrastinate'").fetchall()}
        assert {"procrastinate_jobs", "procrastinate_events", "procrastinate_workers", "procrastinate_periodic_defers"} <= tabelas
        conn.execute("SET search_path = procrastinate, public")
        conn.execute("INSERT INTO procrastinate_jobs (queue_name, task_name, args) VALUES ('q', 't', '{}')")
        assert conn.execute("SELECT count(*) FROM procrastinate_events").fetchone() == (1,)  # o trigger rodou
        conn.execute("DELETE FROM procrastinate_jobs")  # DML completo (inclui DELETE) só aqui, nunca em `ia`
    with banco.sessao("ia_leitura_a") as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("SELECT count(*) FROM procrastinate.procrastinate_jobs")


@pytest.mark.banco
def test_ia_app_nao_cria_nada_em_procrastinate_e_o_dono_e_ia_owner(banco):
    with banco.sessao() as conn:
        assert conn.execute("SELECT NOT has_schema_privilege('ia_app', 'procrastinate', 'CREATE')").fetchone() == (True,)
        donos = conn.execute("SELECT DISTINCT tableowner FROM pg_tables WHERE schemaname IN ('ia', 'procrastinate')").fetchall()
    assert donos == [("ia_owner",)]


# --- CLI: só local ------------------------------------------------------------------------------------------------------


def test_cli_recusa_host_que_nao_e_local(capsys):
    with pytest.raises(SystemExit) as saida:
        main(["--dsn", "postgresql://s4_super:segredo-nao-mostrar@203.0.113.4:5434/ia_atendimento"])
    assert saida.value.code == 2
    err = capsys.readouterr().err
    assert "local" in err and "segredo-nao-mostrar" not in err


@pytest.mark.banco
def test_cli_aplica_em_banco_local_e_nao_imprime_senha(vazio, servidor, capsys):
    dsn = f"postgresql://postgres:descartavel@{servidor.host}:{servidor.port}/{vazio.nome}"
    assert main(["--dsn", dsn]) == 0
    saida = capsys.readouterr().out
    assert "0001_esquema" in saida and "0002_procrastinate" in saida and "descartavel" not in saida
    assert main(["--dsn", dsn, "--conferir"]) == 0


@pytest.mark.parametrize(
    "dsn",
    [
        "host=localhost hostaddr=203.0.113.4 dbname=x user=s4_super",  # hostaddr vence o host: conectaria na S4
        "host=localhost,203.0.113.4 dbname=x user=s4_super",
        "postgresql://u:p@db.exemplo.test/x",
        "service=s4 user=s4_super",  # pg_service.conf pode apontar para qualquer host
        "dbname=x user=s4_super hostaddr=203.0.113.9",
    ],
)
def test_cli_recusa_dsn_que_pode_chegar_a_um_host_remoto(dsn, capsys):
    with pytest.raises(SystemExit) as saida:
        main(["--dsn", dsn])
    assert saida.value.code == 2


def test_cli_sem_host_no_dsn_respeita_pghost_do_ambiente(monkeypatch):
    monkeypatch.setenv("PGHOST", "203.0.113.4")
    with pytest.raises(SystemExit) as saida:
        main(["--dsn", "dbname=x user=s4_super"])
    assert saida.value.code == 2


@pytest.mark.parametrize(
    "dsn", ["host=/var/run/postgresql dbname=x", "host=127.0.0.1 hostaddr=127.0.0.1 dbname=x", "host=localhost dbname=x"]
)
def test_host_local_aceita_socket_e_loopback(dsn):
    from ia_atendimento.migracoes import _host_local

    assert _host_local(dsn)


# --- revisão 29/10 -------------------------------------------------------------------------------------------------------------


@pytest.mark.banco
def test_o_sql_executado_e_exatamente_os_bytes_do_checksum(vazio, tmp_path):
    """`read_text` traduzia CR LF em LF: o ledger registrava o sha256 dos bytes, mas o banco recebia outro texto."""
    copia = tmp_path / "copia"
    shutil.copytree(MIGRACOES, copia)
    bytes_0004 = b"CREATE TABLE ia.zz_crlf AS SELECT length('a\r\nb') AS n;\n"
    (copia / "0005_crlf.up.sql").write_bytes(bytes_0004)
    with vazio.conectar(autocommit=False) as conn:
        aplicar(conn, copia)
    with vazio.sessao() as conn:
        assert conn.execute("SELECT n FROM ia.zz_crlf").fetchone() == (4,)  # a\r\nb: 4 caracteres, não 3
        assert conn.execute("SELECT checksum FROM ia.migracao WHERE migracao_id = '0005_crlf'").fetchone() == (
            hashlib.sha256(bytes_0004).hexdigest(),
        )


def test_migracao_com_bytes_que_nao_sao_utf8_e_recusada_com_nome_do_arquivo(tmp_path):
    (tmp_path / "0001_ruim.up.sql").write_bytes(b"SELECT '\xff';")
    achada = listar(tmp_path)[0]
    with pytest.raises(MigracaoErro, match="0001_ruim"):
        achada.ler()


@pytest.mark.banco
def test_quatro_aplicadores_ao_mesmo_tempo_aplicam_cada_migracao_uma_vez(vazio):
    """Advisory lock + ledger na mesma transação: os outros três esperam e encontram tudo registrado."""
    import threading

    resultados: dict[int, object] = {}

    def rodar(i: int) -> None:
        try:
            with vazio.conectar(autocommit=False) as conn:
                resultados[i] = aplicar(conn, MIGRACOES)
        except Exception as erro:  # o teste afirma sobre o resultado; a exceção entra como valor
            resultados[i] = repr(erro)

    fios = [threading.Thread(target=rodar, args=(i,)) for i in range(4)]
    for fio in fios:
        fio.start()
    for fio in fios:
        fio.join(timeout=120)
    aplicadas = [r for r in resultados.values() if r == TODAS]
    vazias = [r for r in resultados.values() if r == []]
    assert len(aplicadas) == 1 and len(vazias) == 3, resultados
    assert set(_ledger(vazio)) == set(TODAS)


def test_cli_recusa_pgservice_mesmo_com_host_no_dsn(monkeypatch):
    """O serviço pode definir `hostaddr` (que vence o `host`): o DSN diz loopback e a conexão vai para outro lugar."""
    from ia_atendimento.migracoes import _host_local

    monkeypatch.setenv("PGSERVICE", "s4")
    assert not _host_local("host=127.0.0.1 dbname=x")
    assert not _host_local("host=/var/run/postgresql dbname=x")


# --- revisão 29/10: o passo a passo da S4 (docs) é testado contra o banco -----------------------------------------------------------

DOCS_S4 = (RAIZ / "docs" / "OPERACAO.md", MIGRACOES / "README.md")
ALTER_DOCUMENTADO = re.compile(r"ALTER ROLE (\w+) IN DATABASE ia_atendimento SET search_path = procrastinate, public")


def _texto(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8")


@pytest.mark.parametrize("doc", DOCS_S4, ids=lambda d: d.name)
def test_docs_mandam_o_search_path_para_os_logins_e_nunca_para_o_grupo(doc):
    papeis = ALTER_DOCUMENTADO.findall(_texto(doc))
    assert set(papeis) == {"ia_app_a", "ia_app_b"}, f"{doc.name}: ALTER ROLE de search_path tem de ser nos logins, achei {papeis}"


@pytest.mark.banco
def test_search_path_do_grupo_nao_chega_ao_login_e_o_alter_documentado_chega(banco):
    """Configuração de papel não é herdada por quem é membro: `ALTER ROLE ia_app ...` (o que os docs diziam) não valia para ia_app_a."""

    def search_path_do_login() -> str:
        with banco.sessao("ia_app_a") as conn:
            return conn.execute("SHOW search_path").fetchone()[0]

    with banco.sessao() as conn:
        conn.execute(f"ALTER ROLE ia_app IN DATABASE {banco.nome} SET search_path = procrastinate, public")
    assert search_path_do_login() == '"$user", public'  # o grupo não vale
    documentado = ALTER_DOCUMENTADO.search(_texto(DOCS_S4[1]).replace("ia_app_b", "ia_app_a"))
    assert documentado is not None
    with banco.sessao() as conn:
        conn.execute(documentado.group().replace("ia_atendimento", banco.nome))  # o comando EXATO do README, no banco de teste
    assert search_path_do_login() == "procrastinate, public"
    with banco.sessao("ia_app_a") as conn:  # e a fila funciona sem nenhum SET na sessão
        conn.execute("INSERT INTO procrastinate_jobs (queue_name, task_name, args) VALUES ('q', 't', '{}')")
        assert conn.execute("SELECT count(*) FROM procrastinate_events").fetchone() == (1,)


def _epilogo_documentado(doc: Path, migracao_id: str, checksum: str) -> str:
    padrao = re.compile(
        rf'printf "(SET ROLE ia_owner; INSERT INTO ia\.migracao \(migracao_id, checksum\) VALUES \(\'{migracao_id}\', \'%s\'\);\\nRESET ROLE;\\n)"'
    )
    achado = padrao.search(_texto(doc))
    assert achado is not None, (
        f"{doc.name}: a linha do ledger de {migracao_id} tem de ir no mesmo psql -1 que o arquivo (printf ... | psql)"
    )
    return achado.group(1).replace("\\n", "\n") % checksum


@pytest.mark.banco
@pytest.mark.parametrize("doc", DOCS_S4, ids=lambda d: d.name)
def test_ledger_documentado_vai_na_mesma_transacao_do_arquivo(vazio, doc):
    """O fluxo do dono (`{ cat arquivo; printf ledger; } | psql -1`) entra ou sai inteiro, igual ao `aplicar()`."""
    arquivo = MIGRACOES / "0001_esquema.up.sql"
    soma = _sha(arquivo)
    corpo = arquivo.read_text(encoding="utf-8")
    ruim = _epilogo_documentado(doc, "0001_esquema", "xyz")  # checksum inválido: o CHECK do ledger recusa
    with vazio.conectar(autocommit=False) as conn, pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
        conn.execute(corpo + ruim)
    with vazio.sessao() as conn:
        assert conn.execute("SELECT to_regclass('ia.migracao')").fetchone() == (None,)  # nada ficou: o arquivo foi desfeito junto
    with vazio.conectar(autocommit=False) as conn, conn.transaction():
        conn.execute(corpo + _epilogo_documentado(doc, "0001_esquema", soma))
    assert _ledger(vazio) == {"0001_esquema": soma}
