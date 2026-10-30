"""Casos 2: rodada 2 (K prontidão/devolução, L motor de qualidade) e fim do bloco do `passo` (L §2.4).

Porte de `i-teste-0001.sh`, seção «rodada 2». Nomes iguais aos do script.
"""

from __future__ import annotations

from tests.casos.dsl import APP, FP, INTRUSO, LEITURA, P3, QUALIDADE, eq, err, mk, ok, owner, pas

FIM_ATIVO = "WHERE chat_id='chatAAAA0001' AND estado<>'encerrado';"
PK, CK = "passo_modelo_check", "passo_auditoria_check"
NOTA_COLS = "INSERT INTO ia.qualidade_nota (atendimento_id, qualidade_versao, definitiva, nota, faixa, portao_falhas, bloco_a, bloco_b, bloco_c, componentes)"


def _nota(valores: str) -> str:
    return f"{NOTA_COLS} VALUES ('@@ID1@@',1,{valores});"


def _nota_do_chat(valores: str) -> str:
    return f"{NOTA_COLS} SELECT atendimento_id, 1, {valores} FROM ia.atendimento WHERE chat_id='chatHHHH0008';"


CASOS_B = [
    err(
        "passo sem turno/fase recusado (L §2.4: retroativo é impossível)", APP, pas(", motor", "decisao", ", 'regra'"), "passo_turno_check"
    ),
    err("passo com fase E11 recusada", APP, pas(", motor, turno, fase", "decisao", ", 'regra', 1, 'E11'"), "passo_turno_check"),
    err(
        "decisão do MODELO sem intenção/confiança recusada",
        APP,
        pas(", motor, turno, fase, modelo, provedor", "decisao", ", 'modelo', 1, 'E3', 'deepseek-v4p1-flash-1017', 'fireworks-us'"),
        PK,
    ),
    err(
        "intenção em passo que não é decisão recusada",
        APP,
        pas(", motor, turno, fase, intencao, confianca", "decisao", ", 'regra', 1, 'E3', 'aceita', 'alta'"),
        PK,
    ),
    err(
        "confiança fora de alta|media|baixa recusada",
        APP,
        pas(
            ", motor, turno, fase, intencao, confianca, modelo, provedor",
            "decisao",
            ", 'modelo', 1, 'E3', 'aceita', 'certeza', 'deepseek-v4p1-flash-1017', 'fireworks-us'",
        ),
        PK,
    ),
    err(
        "acao_invalida fora de decisão recusada",
        APP,
        pas(", entrega, turno, fase, verif_det, acao_invalida", "resposta_enviada", ", 'aceito', 1, 'E3', '{}', true"),
        PK,
    ),
    err(
        "decisão do MODELO sem modelo/provedor recusada (ag: faixa × modelo)",
        APP,
        pas(", motor, turno, fase, intencao, confianca", "decisao", ", 'modelo', 1, 'E3', 'aceita', 'alta'"),
        "passo_valores_check",
    ),
    err(
        "modelo sem provedor recusado (os dois ou nenhum)",
        APP,
        pas(", motor, turno, fase, modelo", "decisao", ", 'regra', 1, 'E3', 'deepseek-v4p1-flash-1017'"),
        "passo_valores_check",
    ),
    ok(
        "decisão do modelo com intenção, objeção, confiança, transversal, ação inválida, modelo e provedor",
        APP,
        pas(
            ", motor, turno, fase, intencao, objecao, confianca, acao_invalida, transversal, modelo, provedor",
            "decisao",
            ", 'modelo', 1, 'E3', 'objecao', 'parcela_alta', 'media', true, 'fora_de_escopo', 'deepseek-v4p1-flash-1017', 'fireworks-us'",
        ),
    ),
    err(
        "resposta_enviada sem verif_det (T15 determinístico) recusada",
        APP,
        pas(", entrega, turno, fase", "resposta_enviada", ", 'aceito', 1, 'E3'"),
        CK,
    ),
    err(
        "tx_id mal formado recusado",
        APP,
        pas(", entrega, turno, fase, verif_det, tx_id", "resposta_enviada", ", 'aceito', 1, 'E3', '{}', 'TX3'"),
        "passo_turno_check",
    ),
    err(
        "responde_ordem inexistente recusada (FK)",
        APP,
        pas(", entrega, turno, fase, verif_det, responde_ordem", "resposta_enviada", ", 'aceito', 1, 'E3', '{}', 50"),
        "passo_responde_fk",
    ),
    ok(
        "resposta_enviada com tx_id, verif_det vazio (limpo) e responde_ordem",
        APP,
        pas(", entrega, turno, fase, verif_det, tx_id, responde_ordem", "resposta_enviada", ", 'aceito', 1, 'E3', '{}', 'TX-03', 2"),
    ),
    ok(
        "lembrete com verif_det de código e texto livre (tx_id NULL), dentro da janela de 24 h",
        APP,
        pas(", entrega, turno, fase, verif_det, janela_24h", "lembrete", ", 'aceito', 2, 'E9', '{horario_ok}', true"),
    ),
    err(
        "lembrete sem janela_24h recusado",
        APP,
        pas(", entrega, turno, fase, verif_det", "lembrete", ", 'aceito', 2, 'E9', '{}'"),
        "passo_janela_check",
    ),
    err(
        "lembrete fora da janela (template pago) sem custo recusado",
        APP,
        pas(", entrega, turno, fase, verif_det, janela_24h", "lembrete", ", 'aceito', 2, 'E9', '{}', false"),
        "passo_janela_check",
    ),
    err(
        "lembrete dentro da janela com custo recusado",
        APP,
        pas(", entrega, turno, fase, verif_det, janela_24h, custo_brl", "lembrete", ", 'aceito', 2, 'E9', '{}', true, 0.35"),
        "passo_janela_check",
    ),
    ok(
        "lembrete com template pago registra janela_24h=false e o custo",
        APP,
        pas(", entrega, turno, fase, verif_det, janela_24h, custo_brl", "lembrete", ", 'aceito', 2, 'E9', '{}', false, 0.35"),
    ),
    err(
        "janela_24h fora de lembrete recusada",
        APP,
        pas(", entrega, turno, fase, verif_det, janela_24h", "resposta_enviada", ", 'aceito', 2, 'E3', '{}', true"),
        "passo_janela_check",
    ),
    err(
        "chamada T7 sem confirmacao_ref recusada (G1)",
        APP,
        pas(", ferramenta, ferramenta_versao, turno, fase", "chamada_ferramenta", ", 't7', '1.0.0', 4, 'E7'"),
        CK,
    ),
    err(
        "passo de confirmação sem confirmacao_ref recusado",
        APP,
        pas(", confirmacao_id, resultado, turno, fase", "confirmacao", ", '@@CF@@', 'sim_valido', 4, 'E6'"),
        CK,
    ),
    err(
        "confirmação invalidada sem motivo (invalidacao) recusada",
        APP,
        pas(
            ", confirmacao_id, confirmacao_ref, resultado, turno, fase",
            "confirmacao",
            ", '@@CF@@', '0123456789abcdef', 'invalidada', 4, 'E6'",
        ),
        CK,
    ),
    ok(
        "passo de confirmação invalidada com motivo",
        APP,
        pas(
            ", confirmacao_id, confirmacao_ref, resultado, invalidacao, turno, fase",
            "confirmacao",
            ", '@@CF@@', '0123456789abcdef', 'invalidada', 'valor_mudou', 4, 'E6'",
        ),
    ),
    err("passo repasse sem etapa recusado (C4)", APP, pas(", turno, fase", "repasse", ", 5, 'E10'"), CK),
    *[
        ok(f"passo repasse etapa '{etapa}'", APP, pas(", repasse_etapa, turno, fase", "repasse", f", '{etapa}', 5, 'E10'"))
        for etapa in ("nota", "chatbot", "rota", "marca", "lease", "cerco")
    ],
    err("etapa de repasse fora da lista recusada", APP, pas(", repasse_etapa, turno, fase", "repasse", ", 'sorteio', 5, 'E10'"), CK),
    # atendimento: modo teste, persona, contadores, nota, opt-out, humano
    ok("modo 'teste' com persona (F3/ensaio) aceito", APP, mk("chatHHHH0008", "ab", P3, ", persona_id", ", 'P47'", modo="teste")),
    err(
        "persona em modo real recusada",
        APP,
        mk("chatIIII0009", "78", P3, ", persona_id", ", 'P47'", modo="real"),
        "atendimento_qualidade_check",
    ),
    err("modo fora de real|sombra|duble|teste recusado", APP, mk("chatIIII0009", "78", P3, modo="producao"), "atendimento_gatilho_check"),
    err(
        "nota do repasse sem repasse_nota_enviada recusada",
        APP,
        f"UPDATE ia.atendimento SET nota_repasse_tamanho=120 {FIM_ATIVO}",
        "atendimento_qualidade_check",
    ),
    err(
        "nota do repasse > 400 caracteres recusada",
        APP,
        "UPDATE ia.atendimento SET estado='repassando', estado_conversa='{\"fase\":\"E10\"}', repasse_modo='fila', repasse_nota_enviada=true, nota_repasse_tamanho=401 "
        + FIM_ATIVO,
        "atendimento_qualidade_check",
    ),
    ok(
        "repasse com nota de 120 caracteres, contadores e sinais do cliente",
        APP,
        "UPDATE ia.atendimento SET estado='repassando', estado_conversa='{\"fase\":\"E10\"}', repasse_modo='fila', repasse_nota_enviada=true, nota_repasse_tamanho=120,"
        " sem_avanco=1, corrigiveis=2, contrapropostas=1, confirmacoes_emitidas=2, confirmacoes_invalidas=1, sinais_cliente='{reclamacao,pede_humano}', pii_auditoria=false "
        + FIM_ATIVO,
    ),
    err(
        "confirmacoes_invalidas > emitidas recusada",
        APP,
        f"UPDATE ia.atendimento SET confirmacoes_invalidas=5 {FIM_ATIVO}",
        "atendimento_qualidade_check",
    ),
    err(
        "desfecho opt_out sem opt_out_em recusado (G10)",
        APP,
        "UPDATE ia.atendimento SET estado='encerrado', desfecho='opt_out', encerrado_em=now(), lease_ate=NULL WHERE chat_id='chatHHHH0008';",
        "atendimento_qualidade_check",
    ),
    eq(
        "desfecho opt_out com opt_out_em aceito",
        APP,
        "SELECT desfecho FROM ia.atendimento WHERE chat_id='chatHHHH0008' AND opt_out_em IS NOT NULL;",
        "opt_out",
        antes=(
            (
                APP,
                "UPDATE ia.atendimento SET estado='encerrado', desfecho='opt_out', opt_out_em=now(), encerrado_em=now(), lease_ate=NULL WHERE chat_id='chatHHHH0008';",
            ),
        ),
    ),
    eq(
        "motivo 'devolvido_pela_s2' (K): encerra como repassado, sem modo de repasse",
        APP,
        "SELECT desfecho || '/' || motivo_desfecho || '/' || coalesce(repasse_modo, '-') FROM ia.atendimento WHERE chat_id='chatJJJJ0010';",
        "repassado/devolvido_pela_s2/-",
        antes=(
            (
                APP,
                mk("chatJJJJ0010", "ef", P3)
                + "  UPDATE ia.atendimento SET estado='encerrado', desfecho='repassado', motivo_desfecho='devolvido_pela_s2', encerrado_em=now(), lease_ate=NULL WHERE chat_id='chatJJJJ0010';",
            ),
        ),
    ),
    err(
        "motivo 'humano_assumiu' sem humano_assumiu_em recusado",
        APP,
        mk("chatKKKK0011", "12", P3)
        + "  UPDATE ia.atendimento SET estado='encerrado', desfecho='repassado', motivo_desfecho='humano_assumiu', encerrado_em=now(), lease_ate=NULL WHERE chat_id='chatKKKK0011';",
        "atendimento_qualidade_check",
    ),
    # K: prontidão
    eq(
        "v_prontidao: abertos = ativos reais; modo e ia_ativa vigentes",
        APP,
        "SELECT abertos = (SELECT count(*) FROM ia.atendimento WHERE estado <> 'encerrado') AND modo = 'duble' AND NOT ia_ativa FROM ia.v_prontidao;",
        "t",
    ),
    eq(
        "v_prontidao: lease vencido e 'repassando' há mais de 10 min aparecem",
        LEITURA,
        "SELECT lease_vencidos >= 1 AND 'chatAAAA0001' = ANY (repassando_ha_10min) AND repassando >= 1 AND mais_velho_em IS NOT NULL FROM ia.v_prontidao;",
        "t",
        antes=(
            owner(
                "UPDATE ia.atendimento SET lease_ate = now() - interval '1 minute' WHERE chat_id='chatDDDD0004';"
                " UPDATE ia.atendimento SET atualizado_em = now() - interval '11 minutes' WHERE chat_id='chatAAAA0001' AND estado <> 'encerrado';"
            ),
        ),
    ),
    err("papel sem grant não lê v_prontidao", INTRUSO, "SELECT * FROM ia.v_prontidao;", "permission denied"),
    # L: qualidade
    ok(
        "ia_qualidade registra a versão do motor (pesos, faixas, hashes, kappa)",
        QUALIDADE,
        "INSERT INTO ia.qualidade_motor_versao (qualidade_versao, descricao, pesos, faixas, rubrica_hash, kappa, aprovado_em, aprovado_por)"
        f' VALUES (1,\'v1 chute\',\'{{"A":50,"B":20,"C":30}}\',\'{{"A":85,"B":70,"C":50}}\',\'{FP}\',\'{{"R1":{{"k":0.6}}}}\',now(),\'danilo@exemplo.test\');',
    ),
    err(
        "versão com aprovado_em sem aprovado_por recusada",
        QUALIDADE,
        "INSERT INTO ia.qualidade_motor_versao (qualidade_versao, descricao, pesos, faixas, aprovado_em) VALUES (2,'x','{}','{}',now());",
        "qualidade_motor_versao_check",
    ),
    ok(
        "nota provisória (blocos A/B/C + componentes por item)",
        QUALIDADE,
        _nota('false, 80, \'B\', \'{}\', 42, 14, 24, \'{"v":1,"A":{"A1":{"s":1,"p":8}}}\''),
    ),
    ok("nota definitiva do mesmo atendimento e versão (linha nova)", QUALIDADE, _nota("true, 79, 'B', '{}', 41, 14, 24, '{\"v\":1}'")),
    err("mesma nota duas vezes recusada (PK)", QUALIDADE, _nota("true, 79, 'B', '{}', 41, 14, 24, '{\"v\":1}'"), "qualidade_nota_pk"),
    ok("portão reprovado ⇒ faixa P, nota 0, falhas G1,G10", QUALIDADE, _nota_do_chat("false, 0, 'P', '{G1,G10}', 30, 10, 10, '{}'")),
    err("faixa P com nota > 0 recusada", QUALIDADE, _nota_do_chat("true, 50, 'P', '{G2}', 30, 10, 10, '{}'"), "qualidade_nota_check"),
    err(
        "faixa que não é P com falhas de portão recusada",
        QUALIDADE,
        _nota("false, 60, 'C', '{G3}', 30, 15, 15, '{}'"),
        "qualidade_nota_check",
    ),
    err(
        "nota que não bate com a soma dos blocos recusada",
        QUALIDADE,
        _nota("true, 90, 'A', '{}', 30, 10, 10, '{}'"),
        "qualidade_nota_check",
    ),
    err(
        "TEXTO em componentes (string > 40 caracteres) recusado: o motor nunca guarda trecho",
        QUALIDADE,
        _nota(
            "false, 80, 'B', '{}', 42, 14, 24, '{\"x\":{\"obs\":\"o cliente disse que não entendeu nada do que a IA explicou sobre o prazo\"}}'"
        ),
        "qualidade_nota_check",
    ),
    ok(
        "juiz ok: notas 1–5, alerta de conformidade, discordância de intenção, custo fora do atendimento",
        QUALIDADE,
        "INSERT INTO ia.qualidade_juiz (atendimento_id, qualidade_versao, passe, status, r1, r2, r3, r4, r5, nota_juiz, alerta_conformidade, discord_intencao,"
        " confianca, sinais, detalhe, modelo, tokens_entrada, tokens_saida, custo_brl)"
        " VALUES ('@@ID1@@',1,1,'ok',4,4,5,2,4,70.00,true,0.125,'media','{frustrado}','{\"R4\":{\"ev\":[3,5],\"cod\":[\"promessa\"]}}','modelo-juiz-x',4000,400,0.013);",
    ),
    ok(
        "juiz que falhou fica visível (status juiz_falhou, sem nota)",
        QUALIDADE,
        "INSERT INTO ia.qualidade_juiz (atendimento_id, qualidade_versao, passe, status) VALUES ('@@ID1@@',1,2,'juiz_falhou');",
    ),
    err(
        "juiz 'ok' sem nota recusado",
        QUALIDADE,
        "INSERT INTO ia.qualidade_juiz (atendimento_id, qualidade_versao, passe, status) VALUES ('@@ID1@@',1,3,'ok');",
        "qualidade_juiz_check",
    ),
    err(
        "critério do juiz fora de 1–5 recusado",
        QUALIDADE,
        "INSERT INTO ia.qualidade_juiz (atendimento_id, qualidade_versao, passe, status, r1) VALUES ('@@ID1@@',1,4,'juiz_falhou',6);",
        "qualidade_juiz_check",
    ),
    ok(
        "avaliação humana só com notas e códigos",
        QUALIDADE,
        "INSERT INTO ia.qualidade_humana (atendimento_id, avaliador, r1, r2, r3, r4, r5, codigos, duplo, rubrica_hash)"
        f" VALUES ('@@ID1@@','revisor1@exemplo.test',4,4,4,3,4,'{{nota_clara}}',true,'{FP}');",
    ),
    err(
        "avaliação humana com nota 0 recusada",
        QUALIDADE,
        "INSERT INTO ia.qualidade_humana (atendimento_id, avaliador, r1, r2, r3, r4, r5, rubrica_hash)"
        f" VALUES ('@@ID1@@','revisor2@exemplo.test',0,4,4,3,4,'{FP}');",
        "qualidade_humana_check",
    ),
    ok(
        "amostra estratificada semeada",
        QUALIDADE,
        "INSERT INTO ia.qualidade_amostra (atendimento_id, etapa, estrato, motivo_amostra, seed) VALUES ('@@ID1@@','B','repassado_p','nota_alta_sinal_negativo',20261123);",
    ),
    err(
        "amostra: etapa fora de A|B|regime recusada",
        QUALIDADE,
        "INSERT INTO ia.qualidade_amostra (atendimento_id, etapa, estrato, motivo_amostra, seed) VALUES ('@@ID1@@','C','x','y',1);",
        "qualidade_amostra_check",
    ),
    eq(
        "ia_leitura lê as notas (nota e juiz)",
        LEITURA,
        "SELECT (SELECT count(*) FROM ia.qualidade_nota) >= 3 AND (SELECT count(*) FROM ia.qualidade_juiz) >= 2;",
        "t",
    ),
    err("ia_leitura NÃO lê a avaliação humana", LEITURA, "SELECT * FROM ia.qualidade_humana;", "permission denied"),
    err("ia_leitura NÃO lê a amostra", LEITURA, "SELECT * FROM ia.qualidade_amostra;", "permission denied"),
    err(
        "ia_qualidade NÃO lê texto cifrado (camada 2 pede migração própria)",
        QUALIDADE,
        "SELECT count(*) FROM ia.conversa_cifrada;",
        "permission denied",
    ),
    err("ia_qualidade NÃO lê o cofre", QUALIDADE, "SELECT count(*) FROM ia.cofre;", "permission denied"),
    err("ia_qualidade NÃO escreve na linha do tempo", QUALIDADE, "UPDATE ia.atendimento SET turnos = 0;", "permission denied"),
    err("ia_qualidade NÃO apaga nota", QUALIDADE, "DELETE FROM ia.qualidade_nota;", "permission denied"),
    err("ia_qualidade NÃO altera nota (imutável)", QUALIDADE, "UPDATE ia.qualidade_nota SET nota = 100;", "permission denied"),
    err(
        "ia_app NÃO mexe no motor de qualidade",
        APP,
        "INSERT INTO ia.qualidade_amostra (atendimento_id, etapa, estrato, motivo_amostra, seed) VALUES ('@@ID1@@','A','x','y',1);",
        "permission denied",
    ),
]
