"""Casos 4: poda (14 d texto, 1 d cofre, 365 d resto; piso e teto), papéis, grants e default privileges.

Porte de `i-teste-0001.sh`, seções «poda» e «papéis, grants e default privileges». Nomes iguais aos do script.
Fora da contagem do estudo (informativo no script, sem veredito): `CREATE EXTENSION pgcrypto` como `ia_owner`.
"""

from __future__ import annotations

from pathlib import Path

from tests.casos.dsl import APP, FP, INTRUSO, LEITURA, P2, SUPER, eq, err, ok, owner

SEMENTE = (Path(__file__).parent / "semente_poda.sql").read_text(encoding="utf-8")
OLD = "chat_id LIKE 'chatOLD%'"
PODADOS = f"(SELECT atendimento_id FROM ia.atendimento WHERE {OLD})"

CASOS_D = [
    ok("semeia 3 encerrados antigos (15 d, 10 d, 400 d) com texto, cofre e passos", SUPER, "SET ROLE ia_owner; " + SEMENTE),
    err("poda de texto recusa p_dias_conversa = 30 (teto de 14)", APP, "SELECT * FROM ia.fn_texto_podar(30);", "ia.fn_texto_podar"),
    err("poda de texto recusa p_dias_conversa = 3 (piso de 7)", APP, "SELECT * FROM ia.fn_texto_podar(3);", "ia.fn_texto_podar"),
    eq(
        "fn_texto_podar(): apaga a conversa de 15 d e preserva a de 10 d, as ativas e a de hoje",
        APP,
        "SELECT linhas_conversa||'/'||linhas_cofre FROM ia.fn_texto_podar();",
        "2/3",
    ),
    eq(
        "sobram só as conversas dos atendimentos < 14 d após o fim (10 d) e dos ativos",
        APP,
        f"SELECT count(*) FROM ia.conversa_cifrada WHERE atendimento_id IN {PODADOS};",
        "1",
    ),
    eq(
        "cofre: apagado 1 d após o encerramento (todos os antigos)",
        APP,
        f"SELECT count(*) FROM ia.cofre WHERE atendimento_id IN {PODADOS};",
        "0",
    ),
    eq(
        "conversa de atendimento ATIVO (mensagem + resumo) não é tocada",
        APP,
        "SELECT count(*) FROM ia.conversa_cifrada WHERE atendimento_id='@@ID1@@';",
        "2",
    ),
    err("poda geral recusa p_dias = 30 (piso de 365)", APP, "SELECT * FROM ia.fn_atendimento_podar(30);", "mínimo 365"),
    eq(
        "fn_atendimento_podar(): poda só o de 400 d (filhos primeiro, sem ciclo de FK; 2 passos)",
        APP,
        "SELECT atendimentos||'/'||passos FROM ia.fn_atendimento_podar();",
        "1/2",
    ),
    eq(
        "os de 15 d e 10 d continuam (365 d)", APP, "SELECT count(*) FROM ia.atendimento WHERE chat_id IN ('chatOLD010','chatOLD011');", "2"
    ),
    eq(
        "poda geral leva a nota de qualidade do atendimento podado e preserva a versão do motor",
        SUPER,
        "SELECT (SELECT count(*) FROM ia.qualidade_nota WHERE qualidade_versao=90) || '/' || (SELECT count(*) FROM ia.qualidade_motor_versao WHERE qualidade_versao=90);",
        "0/1",
    ),
    eq(
        "poda geral leva o agendamento e o passo 'agendamento' do atendimento podado",
        SUPER,
        "SELECT (SELECT count(*) FROM ia.agendamento WHERE chat_id='chatOLD012') || '/' || (SELECT count(*) FROM ia.passo WHERE tipo='agendamento' AND ocorrido_em < now() - interval '300 days');",
        "0/0",
    ),
    eq("opt_out nunca é podado", APP, "SELECT count(*) FROM ia.opt_out;", "1"),
    # == papéis, grants e default privileges
    err("ia_app sem DDL (CREATE TABLE em ia)", APP, "CREATE TABLE ia.intruso (x int);", "permission denied"),
    err("ia_app sem DDL (ALTER TABLE)", APP, "ALTER TABLE ia.passo ADD COLUMN x int;", "must be owner"),
    err("ia_app sem DDL (DROP)", APP, "DROP TABLE ia.passo;", "must be owner"),
    err("ia_app sem DELETE (passo)", APP, "DELETE FROM ia.passo;", "permission denied"),
    err("ia_app sem DELETE (atendimento)", APP, "DELETE FROM ia.atendimento;", "permission denied"),
    err("ia_app sem DELETE (conversa_cifrada)", APP, "DELETE FROM ia.conversa_cifrada;", "permission denied"),
    err("ia_app sem TRUNCATE", APP, "TRUNCATE ia.passo;", "permission denied"),
    err("passo é append-only (UPDATE negado)", APP, "UPDATE ia.passo SET texto='x';", "permission denied"),
    err("ia_app não grava em ia.migracao", APP, f"INSERT INTO ia.migracao VALUES ('0002_x', '{FP}');", "permission denied"),
    ok(
        "ia_leitura lê atendimento e passo",
        LEITURA,
        "SELECT count(*) FROM ia.atendimento; SELECT count(*) FROM ia.passo; SELECT count(*) FROM ia.ferramenta_chamada;",
    ),
    err("ia_leitura não lê o cofre", LEITURA, "SELECT count(*) FROM ia.cofre;", "permission denied"),
    err(
        "ia_leitura não escreve",
        LEITURA,
        f"INSERT INTO ia.opt_out (pessoa_id, tipo, origem, chave_logica, idem_key, registrado_por) VALUES ('{P2}','opt_out','operador','t14:x','x','x');",
        "permission denied",
    ),
    err("papel sem grant (intruso) nem enxerga o schema", INTRUSO, "SELECT 1 FROM ia.atendimento;", "permission denied for schema ia"),
    err(
        "default privileges: tabela nova em ia NÃO nasce legível por ia_app",
        APP,
        "SELECT * FROM ia.zz_nova;",
        "permission denied",
        antes=(
            owner(
                "CREATE TABLE ia.zz_nova (x int); CREATE TABLE procrastinate.zz_job (x int); CREATE FUNCTION ia.zz_fn() RETURNS int LANGUAGE sql AS 'SELECT 1';"
            ),
        ),
    ),
    err(
        "default privileges: tabela nova em ia NÃO nasce legível por ia_leitura", LEITURA, "SELECT * FROM ia.zz_nova;", "permission denied"
    ),
    ok(
        "default privileges: tabela nova em procrastinate nasce com DML para ia_app (inclui DELETE)",
        APP,
        "INSERT INTO procrastinate.zz_job VALUES (1); DELETE FROM procrastinate.zz_job;",
    ),
    eq(
        "default privileges: função nova NÃO é executável por PUBLIC",
        SUPER,
        "SELECT has_function_privilege('intruso', 'ia.zz_fn()', 'EXECUTE');",
        "f",
    ),
    ok(
        "ia_app não cria objeto em procrastinate",
        SUPER,
        "SELECT NOT has_schema_privilege('ia_app','procrastinate','CREATE');",
        depois=(owner("DROP TABLE ia.zz_nova; DROP TABLE procrastinate.zz_job; DROP FUNCTION ia.zz_fn();"),),
    ),
]
