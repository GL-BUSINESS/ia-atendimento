"""Casos 1: aplicação, config, replay e trava por chat, estados, chaves, dedupe, confirmação/ledger, opt-out, candidato, cifra.

Porte de `estudos/semana-1/i-teste-0001.sh` (linhas 22 a 186). Nomes iguais aos do script.
"""

from __future__ import annotations

from tests.casos.cifra_db import casos_cifra
from tests.casos.dsl import (
    APP,
    FP,
    FP2,
    H32,
    LEITURA,
    P1,
    P2,
    P3,
    SUPER,
    atd,
    cand,
    chamada,
    eq,
    err,
    fn,
    mk,
    nao_vazio,
    ok,
    pas,
    t7,
)

CFG = "INSERT INTO ia.config_versao VALUES"


def _aplica_0001(ctx):
    from ia_atendimento.migracoes import aplicar

    with ctx.banco.conectar(autocommit=False) as conn:
        assert aplicar(conn, ctx.dir_so_0001) == ["0001_esquema"]
        assert conn.execute("SELECT checksum FROM ia.migracao WHERE migracao_id = '0001_esquema'").fetchone() is not None


def _replay(fp: str) -> str:
    chave = f"venda:{H32}"
    return (
        "WITH ins AS (INSERT INTO ia.atendimento (origem, chave_logica, idempotency_key, entrada_fingerprint, gatilho, disparado_por, pessoa_id, chat_id,"
        " phone_id, roteiro_versao, regras_versao, catalogo_versao, motor_versao, modo, criterio_versao, faixa_esforco)"
        f" VALUES ('n8n_braco','{chave}', encode(sha256(convert_to('{chave}','UTF8')),'hex'), '{fp}', 'venda','op@exemplo.test','{P1}','chatAAAA0001',"
        "'a1b2c3d4e5f6a1b2c3d4e5f6',1,1,1,1,'duble','crit_v1','media') ON CONFLICT (origem, idempotency_key) DO NOTHING RETURNING 1)"
        " SELECT CASE WHEN EXISTS (SELECT 1 FROM ins) THEN '201' WHEN (SELECT entrada_fingerprint FROM ia.atendimento WHERE origem='n8n_braco'"
        f" AND idempotency_key=encode(sha256(convert_to('{chave}','UTF8')),'hex'))='{fp}' THEN '200' ELSE '409' END;"
    )


MSG_CG = "cg:0123456789abcdef01234567:0f1e2d3c4b5a6978"


def _msg(chave: str, ordem: str, fp: str = FP, tamanho: int = 12) -> str:
    return (
        "INSERT INTO ia.passo (atendimento_id, ordem, tipo, texto, msg_chave, msg_fingerprint, msg_tipo, msg_tamanho, origem_evento, turno, fase)"
        f" VALUES ('@@ID1@@',{ordem},'mensagem_recebida','Cliente enviou texto.','{chave}','{fp}','texto',{tamanho},'webhook',1,'E2');"
    )


def _dedupe(fp: str) -> str:
    ordem = "(SELECT max(ordem)+1 FROM ia.passo WHERE atendimento_id='@@ID1@@')"
    return (
        f"WITH ins AS ({_msg(MSG_CG, ordem, fp).rstrip(';')} ON CONFLICT (msg_chave) WHERE tipo='mensagem_recebida' DO NOTHING RETURNING 1)"
        f" SELECT CASE WHEN EXISTS (SELECT 1 FROM ins) THEN '201' WHEN (SELECT msg_fingerprint FROM ia.passo WHERE msg_chave='{MSG_CG}')='{fp}'"
        " THEN '200' ELSE '409' END;"
    )


def _t7_faltando_confirmacao() -> str:
    return chamada("@@ID1@@", P1, "t7", "t7:@@ID1@@:FACTA:48213:3:1", ", banco, args_hash", f", 'FACTA', '{FP}'")


def _confirmacao(atendimento: str) -> str:
    return (
        "INSERT INTO ia.confirmacao (atendimento_id, tipo, banco, oferta_versao, valores_hash, texto_id, pergunta_ordem)"
        f" VALUES ('{atendimento}','digitacao','FACTA',3,'{FP}','conf_digitacao_v1',2)"
    )


CHAVES_DO_LEDGER = [
    ("t11", "t11:@@ID1@@:3:1"),
    ("t4", f"t4:{P1}:FACTA:2026-11-24"),
    ("assumir", "assumir:@@ID1@@"),
    ("t12", "t12:@@ID1@@"),
    ("t9", "t9:@@ID1@@:FACTA:48213"),
]
MSG_CHAVES = [MSG_CG, "cgid:wamid.HBgN-sintetico=", "rpa:65f1c2a9b8d7e6f5a4b3c2d1"]
V = "config_versao_valor_check"
UPD_ABERTO = (
    "UPDATE ia.atendimento SET estado='aberto', assumido_em=now(), estado_conversa='{\"fase\":\"E1\"}' WHERE chat_id='chatAAAA0001';"
)
UPD_ATIVO = "WHERE chat_id='chatAAAA0001' AND estado<>'encerrado';"

CASOS_A = [
    # == aplicação (como superusuário da S4: SET ROLE ia_owner dentro do arquivo)
    fn("0001 aplica em transação única", _aplica_0001),
    ok("0001 reaplicada = idempotente", SUPER, "@@SQL_0001@@"),
    eq(
        "seed: ia_ativa nasce false", APP, "SELECT valor FROM ia.config_versao WHERE nome='ia_ativa' ORDER BY versao DESC LIMIT 1;", "false"
    ),
    eq("seed: modo nasce duble", APP, "SELECT valor FROM ia.config_versao WHERE nome='modo';", '"duble"'),
    eq("seed: alçada D15 = 6000 (p90 FACTA medido)", APP, "SELECT valor FROM ia.config_versao WHERE nome='alcada_valor_max_brl';", "6000"),
    eq("seed: só a FACTA digita", APP, "SELECT valor FROM ia.config_versao WHERE nome='bancos_digitacao';", '["FACTA"]'),
    err("config: modo inválido recusado", APP, f"{CFG} ('modo',2,'\"producao\"',now(),'x',null);", V),
    err("config: banco fora da lista recusado", APP, f"{CFG} ('bancos_digitacao',2,'[\"XPTO\"]',now(),'x',null);", V),
    ok(
        "config (J): max_disparos_dia, max_abertos, subteto_dia, calendario_bloqueio com valores válidos (rampa = versão nova)",
        APP,
        f"{CFG} ('max_disparos_dia',2,'15',now(),'danilo@exemplo.test','rampa 24/11'), ('subteto_dia',2,'80',now(),'x',null), ('max_abertos',2,'8',now(),'x',null);",
    ),
    eq(
        "config: calendário nasce com a janela DATAPREV 20/11 22h → 23/11 06h",
        APP,
        "SELECT valor->'janelas'->0->>'ate' FROM ia.config_versao WHERE nome='calendario_bloqueio';",
        "2026-11-23T06:00:00-03:00",
    ),
    err("config: max_disparos_dia = 0 recusado", APP, f"{CFG} ('max_disparos_dia',3,'0',now(),'x',null);", V),
    err("config: max_abertos fracionário recusado", APP, f"{CFG} ('max_abertos',3,'2.5',now(),'x',null);", V),
    err("config: calendário sem 'janelas' recusado", APP, f"{CFG} ('calendario_bloqueio',2,'{{\"domingos\":true}}',now(),'x',null);", V),
    ok(
        "config ABERTA: chave nova bem formada entra sem ALTER (0002 não precisa mexer no CHECK)",
        APP,
        f"{CFG} ('flag_futura_xyz',1,'{{\"a\":1}}',now(),'x',null);",
    ),
    err("config: nome mal formado recusado", APP, f"{CFG} ('Nome Ruim',1,'true',now(),'x',null);", "config_versao_nome_check"),
    err("config: ia_ativa não booleano recusado", APP, f"{CFG} ('ia_ativa',2,'\"sim\"',now(),'x',null);", V),
    err("config: UPDATE negado (append-only)", APP, "UPDATE ia.config_versao SET valor='true' WHERE nome='ia_ativa';", "permission denied"),
    # == replay 200/409 e trava por chat
    ok("abre atendimento (estado reservado, lease 2 min)", APP, atd("chatAAAA0001", f"venda:{H32}", FP, P1)),
    eq("replay: mesma chave + mesmo corpo = 200 (sem 2º registro, mesmo com o chat ocupado)", APP, _replay(FP), "200"),
    eq("replay: mesma chave + outro corpo = 409", APP, _replay(FP2), "409"),
    eq("replay não criou linha nova", APP, "SELECT count(*) FROM ia.atendimento WHERE chat_id='chatAAAA0001';", "1"),
    err("trava por chat: 2º ativo no mesmo chat (reservado) = recusado", APP, mk("chatAAAA0001", "ab", P2), "atendimento_ativo_chat_uq"),
    ok("chat diferente passa", APP, mk("chatBBBB0002", "cd", P1)),
    err(
        "trava por chat: ainda recusa com o estado 'aberto'",
        APP,
        mk("chatAAAA0001", "ef", P2),
        "atendimento_ativo_chat_uq",
        antes=((APP, UPD_ABERTO),),
    ),
    ok(
        "estado 'repassando' mantém a posse (mudança aceita)",
        APP,
        "UPDATE ia.atendimento SET estado='repassando', repasse_modo='fila', estado_conversa='{\"fase\":\"E10\"}' WHERE chat_id='chatAAAA0001';",
    ),
    err("trava por chat: ainda recusa com 'repassando'", APP, mk("chatAAAA0001", "12", P2), "atendimento_ativo_chat_uq"),
    ok(
        "encerra (desfecho repassado, lease NULL) libera o chat",
        APP,
        "UPDATE ia.atendimento SET estado='encerrado', desfecho='repassado', encerrado_em=now(), lease_ate=NULL WHERE chat_id='chatAAAA0001';",
    ),
    ok("novo atendimento no chat liberado", APP, mk("chatAAAA0001", "34", P1)),
    # == CHECK dos estados
    err(
        "estado inexistente recusado",
        APP,
        "UPDATE ia.atendimento SET estado='bogus', assumido_em=now(), estado_conversa='{\"fase\":\"E1\"}' WHERE chat_id='chatBBBB0002';",
        "atendimento_estado_check",
    ),
    err(
        "'aberto' sem assumir_canal concluído recusado",
        APP,
        "UPDATE ia.atendimento SET estado='aberto', estado_conversa='{\"fase\":\"E1\"}' WHERE chat_id='chatBBBB0002';",
        "atendimento_assumido_check",
    ),
    err(
        "encerrado sem desfecho recusado",
        APP,
        "UPDATE ia.atendimento SET estado='encerrado', encerrado_em=now(), lease_ate=NULL WHERE chat_id='chatBBBB0002';",
        "atendimento_fim_check",
    ),
    err(
        "encerrado com lease recusado",
        APP,
        "UPDATE ia.atendimento SET estado='encerrado', desfecho='sem_venda', encerrado_em=now() WHERE chat_id='chatBBBB0002';",
        "atendimento_lease_check",
    ),
    err(
        "'abortado' depois de assumir o canal recusado",
        APP,
        "UPDATE ia.atendimento SET assumido_em=now(), estado='encerrado', desfecho='abortado', encerrado_em=now(), lease_ate=NULL WHERE chat_id='chatBBBB0002';",
        "atendimento_abortado_check",
    ),
    err(
        "modo sombra não pode 'vendeu' (nada saiu)",
        SUPER,
        "SET ROLE ia_owner; UPDATE ia.atendimento SET modo='sombra', assumido_em=now(), estado='encerrado', desfecho='vendeu', encerrado_em=now(), lease_ate=NULL WHERE chat_id='chatBBBB0002';",
        "atendimento_sombra_check",
    ),
    err(
        "fase fora de E0–E10 recusada (H)",
        APP,
        f'UPDATE ia.atendimento SET estado_conversa=\'{{"fase":"E11"}}\' {UPD_ATIVO}',
        "atendimento_conversa_check",
    ),
    err(
        "contador negativo em estado_conversa recusado",
        APP,
        f'UPDATE ia.atendimento SET estado_conversa=\'{{"fase":"E0","contadores":{{"t5":-1}}}}\' {UPD_ATIVO}',
        "atendimento_conversa_check",
    ),
    err(
        "contador não numérico recusado",
        APP,
        f'UPDATE ia.atendimento SET estado_conversa=\'{{"fase":"E0","contadores":{{"t5":"x"}}}}\' {UPD_ATIVO}',
        "atendimento_conversa_check",
    ),
    err(
        "estado_conversa > 2 KB recusado",
        APP,
        f"UPDATE ia.atendimento SET estado_conversa=jsonb_build_object('fase','E0','obj', repeat('x',2100)) {UPD_ATIVO}",
        "atendimento_conversa_check",
    ),
    err(
        "'reservado' fora de E0 recusado (duas máquinas coerentes)",
        APP,
        "UPDATE ia.atendimento SET estado_conversa='{\"fase\":\"E3\"}' WHERE chat_id='chatBBBB0002';",
        "atendimento_conversa_check",
    ),
    err(
        "'repassando' fora de E10 recusado",
        APP,
        "UPDATE ia.atendimento SET estado='repassando', repasse_modo='fila', assumido_em=now(), estado_conversa='{\"fase\":\"E3\"}' WHERE chat_id='chatBBBB0002';",
        "atendimento_conversa_check",
    ),
    ok(
        "estado_conversa com fase e contadores aceito; fase gerada",
        APP,
        'UPDATE ia.atendimento SET estado=\'aberto\', assumido_em=now(), estado_conversa=\'{"fase":"E1","contadores":{"t5":0,"lembretes":0,"trocas_desde_resumo":2}}\' '
        + UPD_ATIVO,
    ),
    eq("fase (coluna gerada) = E1", APP, f"SELECT fase FROM ia.atendimento {UPD_ATIVO}", "E1"),
    err(
        "motivo_escolha fora da lista fechada recusado (J §2.3)",
        APP,
        atd("chatDDDD0004", "venda:" + "56" * 16, FP, P3, ", motivo_escolha", ", 'promissor'"),
        "atendimento_escolha_check",
    ),
    err(
        "motivo 'outro' sem nota recusado",
        APP,
        atd("chatDDDD0004", "venda:" + "56" * 16, FP, P3, ", motivo_escolha", ", 'outro'"),
        "atendimento_escolha_check",
    ),
    ok(
        "motivo 'outro' com nota ≤ 80 aceito",
        APP,
        atd(
            "chatDDDD0004",
            "venda:" + "56" * 16,
            FP,
            P3,
            ", motivo_escolha, motivo_escolha_nota",
            ", 'outro', 'lead pedido pelo coordenador'",
        ),
    ),
    err(
        "venda sem criterio_versao recusada (J §2.2)",
        APP,
        "INSERT INTO ia.atendimento (origem, chave_logica, idempotency_key, entrada_fingerprint, gatilho, disparado_por, pessoa_id, chat_id, phone_id,"
        " roteiro_versao, regras_versao, catalogo_versao, motor_versao, modo, faixa_esforco)"
        f" VALUES ('n8n_braco','venda:{H32}',encode(sha256(convert_to('venda:{H32}','UTF8')),'hex'),'{FP}','venda','x','{P3}','chatEEEE0005',"
        "'a1b2c3d4e5f6a1b2c3d4e5f6',1,1,1,1,'duble','baixa');",
        "atendimento_gatilho_dados_check",
    ),
    ok(
        "'abortado' em reservado (humano_ativo) aceito",
        APP,
        "UPDATE ia.atendimento SET estado='encerrado', desfecho='abortado', motivo_desfecho='humano_ativo', encerrado_em=now(), lease_ate=NULL WHERE chat_id='chatBBBB0002';",
    ),
    err(
        "chatbot desligado sem guardar o estado anterior recusado",
        APP,
        f"UPDATE ia.atendimento SET chatbot_estado='desligado_pela_ia' {UPD_ATIVO}",
        "atendimento_chatbot_check",
    ),
    err(
        "repasse_modo fora do repasse recusado",
        APP,
        f"UPDATE ia.atendimento SET repasse_modo='fila' {UPD_ATIVO}",
        "atendimento_repasse_check",
    ),
    err("ia_app não altera pessoa_id (UPDATE por coluna)", APP, f"UPDATE ia.atendimento SET pessoa_id='{P3}';", "permission denied"),
    # == formatos reais das chaves (c, f, b)
    eq(
        "venda:<32 hex> aceita e idempotency_key = sha256(chave_logica)",
        APP,
        f"SELECT bool_and(idempotency_key = encode(sha256(convert_to(chave_logica,'UTF8')),'hex')) FROM ia.atendimento WHERE chave_logica = 'venda:{H32}';",
        "t",
    ),
    err(
        "idempotency_key que não é o sha256 da chave lógica recusada",
        APP,
        "INSERT INTO ia.atendimento (origem, chave_logica, idempotency_key, entrada_fingerprint, gatilho, disparado_por, pessoa_id, chat_id, phone_id,"
        " roteiro_versao, regras_versao, catalogo_versao, motor_versao, modo, criterio_versao, faixa_esforco)"
        f" VALUES ('n8n_braco','venda:{H32}','{FP}','{FP}','venda','x','{P3}','chatCCCC0003','a1b2c3d4e5f6a1b2c3d4e5f6',1,1,1,1,'duble','crit_v1','media');",
        "atendimento_entrada_check",
    ),
]
CASOS_A += [
    ok(f"ledger aceita a chave {chave.replace('@@ID1@@', '<ID1>')}", APP, chamada("@@ID1@@", P1, ferr, chave))
    for ferr, chave in CHAVES_DO_LEDGER
]
CASOS_A += [
    err(
        "forma antiga 'ia-assumir-<id>' recusada (A11)",
        APP,
        chamada("@@ID1@@", P1, "assumir", "ia-assumir-@@ID1@@"),
        "ferramenta_chamada_chave_check",
    ),
    err("prefixo da chave ≠ ferramenta recusado", APP, chamada("@@ID1@@", P1, "t12", "repasse:@@ID1@@"), "ferramenta_chamada_chave_check"),
    err("mesma chave duas vezes = recusada (trinco)", APP, chamada("@@ID1@@", P1, "t11", "t11:@@ID1@@:3:1"), "ferramenta_chamada_idem_uq"),
    err(
        "T4 do mesmo dia da pessoa em OUTRO atendimento = recusada (sem 2ª consulta paga)",
        APP,
        chamada("@@ID2@@", P1, "t4", f"t4:{P1}:FACTA:2026-11-24"),
        "ferramenta_chamada_idem_uq",
    ),
    err("chave sem ':' recusada", APP, chamada("@@ID1@@", P1, "t7", "t7-abc"), "ferramenta_chamada_chave_check"),
]
_ordem_proxima = "(SELECT coalesce(max(ordem),0)+1 FROM ia.passo WHERE atendimento_id='@@ID1@@')"
CASOS_A += [ok(f"msg_chave aceita {chave}", APP, _msg(chave, _ordem_proxima)) for chave in MSG_CHAVES]
CASOS_A += [
    err(
        "msg_chave fora dos 3 formatos recusada",
        APP,
        _msg("lixo com espaço", "90", tamanho=1).replace(f"'{FP}'", f"'{FP}'", 1),
        "passo_msg_forma_check",
    ),
    # == dedupe de mensagem (b) e pendentes (A9)
    eq("evento repetido (mesma chave e fingerprint) = no-op 200, sem novo turno", APP, _dedupe(FP), "200"),
    eq("mesma chave com fingerprint diferente = conflito detectável (409/erro)", APP, _dedupe(FP2), "409"),
    eq(
        "3 mensagens pendentes (ordem > ordem_consumida)",
        APP,
        "SELECT count(*) FROM ia.passo p JOIN ia.atendimento a USING (atendimento_id) WHERE a.atendimento_id='@@ID1@@' AND p.tipo='mensagem_recebida' AND p.ordem > a.ordem_consumida;",
        "3",
    ),
    err(
        "passo: (atendimento, ordem) único",
        APP,
        "INSERT INTO ia.passo (atendimento_id, ordem, tipo, texto, motor, intencao, confianca, turno, fase, modelo, provedor)"
        " VALUES ('@@ID1@@',1,'decisao','x','modelo','aceita','alta',1,'E3','deepseek-v4p1-flash-1017','fireworks-us');",
        "passo_ordem_uq",
    ),
    err(
        "texto de cliente não cabe em passo de decisão com msg_* (forma por tipo)",
        APP,
        "INSERT INTO ia.passo (atendimento_id, ordem, tipo, texto, motor, intencao, confianca, turno, fase, msg_tipo, modelo, provedor)"
        " VALUES ('@@ID1@@',91,'decisao','x','modelo','aceita','alta',1,'E3','texto','deepseek-v4p1-flash-1017','fireworks-us');",
        "passo_msg_forma_check",
    ),
    # == confirmação e ledger da digitação (f)
    nao_vazio(
        "confirmação criada (expira em 30 min por padrão)", APP, _confirmacao("@@ID1@@") + " RETURNING confirmacao_id;", guardar="CF"
    ),
    err("2ª confirmação pendente do mesmo tipo recusada", APP, _confirmacao("@@ID1@@") + ";", "confirmacao_pendente_uq"),
    err(
        "'aceita' com resposta ANTERIOR à pergunta recusada",
        APP,
        "UPDATE ia.confirmacao SET estado='aceita', classe_resposta='sim', respondida_em=now(), resposta_ordem=1 WHERE confirmacao_id='@@CF@@';",
        "confirmacao_forma_check",
    ),
    ok(
        "'aceita' com resposta posterior aceita",
        APP,
        "UPDATE ia.confirmacao SET estado='aceita', classe_resposta='sim', respondida_em=now(), resposta_ordem=5 WHERE confirmacao_id='@@CF@@';",
    ),
    err("T7 sem confirmação recusada", APP, _t7_faltando_confirmacao(), "ferramenta_chamada_forma_check"),
    ok("T7 com confirmação aceita (reservada ANTES de chamar)", APP, t7("@@ID1@@", P1, "t7:@@ID1@@:FACTA:48213:3:1")),
    err(
        "2ª T7 viva da MESMA pessoa+banco, em outro atendimento = recusada",
        APP,
        chamada("@@ID2@@", P1, "t7", "t7:@@ID2@@:FACTA:48213:3:1", ", banco, args_hash, confirmacao_id", f", 'FACTA', '{FP}', '@@CF2@@'"),
        "ferramenta_chamada_t7_viva_uq",
        antes=((APP, _confirmacao("@@ID2@@") + " RETURNING confirmacao_id;", "CF2"),),
    ),
    err(
        "confirmação de OUTRO atendimento não serve (FK composta)",
        APP,
        chamada("@@ID2@@", P1, "t7", "t7:@@ID2@@:C6:1:1:1", ", banco, args_hash, confirmacao_id", f", 'C6', '{FP}', '@@CF@@'"),
        "ferramenta_chamada_confirmacao_fk",
    ),
    err(
        "ledger: pessoa que não é a do atendimento recusada (FK composta)",
        APP,
        chamada("@@ID1@@", P3, "t11", "t11:@@ID1@@:9:9"),
        "ferramenta_chamada_atendimento_fk",
    ),
    err(
        "ciclo: 'ok' sem concluida_em recusado",
        APP,
        "UPDATE ia.ferramenta_chamada SET estado='ok' WHERE ferramenta='t7';",
        "ferramenta_chamada_ciclo_check",
    ),
    ok(
        "reservada → enviada → indeterminado (CAS por estado)",
        APP,
        "UPDATE ia.ferramenta_chamada SET estado='enviada', enviada_em=now() WHERE ferramenta='t7' AND estado='reservada';"
        " UPDATE ia.ferramenta_chamada SET estado='indeterminado', concluida_em=now(), http_bucket='timeout' WHERE ferramenta='t7' AND estado='enviada';",
    ),
    err(
        "T7 indeterminada BLOQUEIA nova T7 da pessoa+banco (nunca reenvia)",
        APP,
        t7("@@ID1@@", P1, "t7:@@ID1@@:FACTA:48213:3:2", 2),
        "ferramenta_chamada_t7_",
    ),
    err("T8 sem a T7 que resolve recusada", APP, chamada("@@ID1@@", P1, "t8", "t8:@@ID1@@:FACTA:1"), "ferramenta_chamada_forma_check"),
    ok(
        "T8 aponta a T7 e a resolve (criada → T7 vira ok)",
        APP,
        chamada("@@ID1@@", P1, "t8", "t8:@@ID1@@:FACTA:1", ", resolve_id", ", @@T7ID@@")
        + " UPDATE ia.ferramenta_chamada SET estado='ok', ref_externa='PROP48213' WHERE chamada_id=@@T7ID@@ AND estado='indeterminado';",
    ),
    err(
        "depois de 'ok', nova T7 no mesmo atendimento+banco = recusada",
        APP,
        t7("@@ID1@@", P1, "t7:@@ID1@@:FACTA:48213:3:3", 3),
        "ferramenta_chamada_t7_atendimento_uq",
    ),
    eq("simulado é derivado do modo (duble ⇒ true)", APP, "SELECT simulado FROM ia.ferramenta_chamada WHERE chamada_id=@@T7ID@@;", "t"),
    ok(
        "passo chamada_ferramenta liga ao ledger",
        APP,
        "INSERT INTO ia.passo (atendimento_id, ordem, tipo, texto, ferramenta, ferramenta_versao, chamada_id, confirmacao_ref, turno, fase)"
        " VALUES ('@@ID1@@',100,'chamada_ferramenta','t7: proposta enviada','t7','1.0.0',@@T7ID@@,'0123456789abcdef',4,'E7');",
    ),
    ok(
        "anotacao_operador: quem + categoria + texto curto, mesmo em atendimento encerrado (J §1)",
        APP,
        "INSERT INTO ia.passo (atendimento_id, ordem, tipo, texto, operador, resultado) VALUES ('@@ID2@@',50,'anotacao_operador',"
        "'Reclamação registrada pelo coordenador; lead devolvido ao consultor.','danilo@exemplo.test','reclamacao');",
    ),
    err(
        "anotacao_operador sem operador recusada",
        APP,
        "INSERT INTO ia.passo (atendimento_id, ordem, tipo, texto, resultado) VALUES ('@@ID2@@',51,'anotacao_operador','x','reclamacao');",
        "passo_campos_por_tipo_check",
    ),
    err(
        "anotacao_operador com texto > 300 recusada",
        APP,
        "INSERT INTO ia.passo (atendimento_id, ordem, tipo, texto, operador, resultado) VALUES ('@@ID2@@',52,'anotacao_operador',repeat('x',301),'a@exemplo.test','reclamacao');",
        "passo_campos_por_tipo_check",
    ),
    eq(
        "reclamações do piloto (D7-4) saem de uma consulta simples",
        LEITURA,
        "SELECT count(*) FROM ia.passo WHERE tipo='anotacao_operador' AND resultado='reclamacao';",
        "1",
    ),
]
_OPT = f"t14:{P1}:opt_out:{MSG_CG}"
CASOS_A += [
    ok(
        "opt-out local (chave t14:...)",
        APP,
        "INSERT INTO ia.opt_out (pessoa_id, atendimento_id, tipo, origem, chave_logica, idem_key, registrado_por)"
        f" VALUES ('{P1}','@@ID1@@','opt_out','cliente_mensagem','{_OPT}', encode(sha256(convert_to('{_OPT}','UTF8')),'hex'),'orquestrador');",
    ),
    err(
        "opt-out repetido (mesma mensagem) = no-op por UNIQUE",
        APP,
        "INSERT INTO ia.opt_out (pessoa_id, tipo, origem, chave_logica, idem_key, registrado_por)"
        f" VALUES ('{P1}','opt_out','cliente_mensagem','{_OPT}', encode(sha256(convert_to('{_OPT}','UTF8')),'hex'),'x');",
        "opt_out_idem_uq",
    ),
    ok("candidato escolhido que virou atendimento", APP, cand("a", "posicao, escolhido, atendimento_id", "1, true, '@@ID1@@'")),
    ok("candidato elegível NÃO escolhido (tem posição FIFO: base do % de saltos)", APP, cand("b", "posicao, escolhido", "2, false")),
    ok("candidato reprovado em critério (J §2.1): código, sem posição", APP, cand("c", "escolhido, recusa", "false, 'sem_oferta_facta'")),
    ok(
        "candidato escolhido mas recusado pelo orquestrador (409 teto_diario)",
        APP,
        cand("d", "posicao, escolhido, recusa", "3, true, 'teto_diario'"),
    ),
    err("elegível não escolhido SEM posição recusado", APP, cand("e", "escolhido", "false"), "candidato_forma_check"),
    err(
        "reprovado em critério COM posição recusado",
        APP,
        cand("f", "posicao, escolhido, recusa", "4, false, 'idade_fora'"),
        "candidato_forma_check",
    ),
    err("escolhido sem atendimento nem recusa recusado", APP, cand("1", "posicao, escolhido", "5, true"), "candidato_forma_check"),
    err(
        "não escolhido com atendimento recusado",
        APP,
        cand("2", "posicao, escolhido, atendimento_id", "6, false, '@@ID1@@'"),
        "candidato_forma_check",
    ),
    err("o mesmo lead 2× na mesma sessão recusado", APP, cand("a", "posicao, escolhido", "7, false"), "candidato_sessao_uq"),
    # == cifra do texto da conversa (aplicação) e leitura só pelo runtime
    *casos_cifra(),
]
# `pas` fica exportado para os grupos seguintes
__all__ = ["CASOS_A", "pas"]
