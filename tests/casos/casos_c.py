"""Casos 3: rodada 3a (comissão, faixas, modelo por faixa, janelas), 3b (agendamento e pausa) e 3c (tx_id, intenção, chaves novas).

Porte de `i-teste-0001.sh`, seções «rodada 3a», «rodada 3b» e «rodada 3c». Nomes iguais aos do script.
"""

from __future__ import annotations

import copy
import json

from tests.casos.dsl import APP, FP, LEITURA, P1, P2, P3, QUALIDADE, atd, eq, err, mk, ok, pas, psl

V = "config_versao_valor_check"


def _json(obj) -> str:
    return json.dumps(obj, separators=(",", ":"))


def _faixas(versao: int, valor: dict | str) -> str:
    texto = valor if isinstance(valor, str) else _json(valor)
    return f"INSERT INTO ia.config_versao VALUES ('faixas_esforco',{versao},'{texto}',now(),'danilo@exemplo.test','teste');"


def _fx(lembretes_baixa: int, custo_alta: float) -> dict:
    return {
        "limites_brl": [150, 400, 800],
        "faixas": {
            "baixa": {
                "lembretes_max": lembretes_baixa,
                "lembrete_pago_max": 0,
                "dias_max": 1,
                "contrapropostas_max": 1,
                "custo_max_brl": 1.0,
                "agendamentos_max": 0,
            },
            "media": {
                "lembretes_max": 2,
                "lembrete_pago_max": 0,
                "dias_max": 2,
                "contrapropostas_max": 2,
                "custo_max_brl": 2.0,
                "agendamentos_max": 1,
            },
            "alta": {
                "lembretes_max": 2,
                "lembrete_pago_max": 0,
                "dias_max": 3,
                "contrapropostas_max": 3,
                "custo_max_brl": custo_alta,
                "agendamentos_max": 3,
            },
            "muito_alta": {
                "lembretes_max": 2,
                "lembrete_pago_max": 1,
                "dias_max": 3,
                "contrapropostas_max": 3,
                "custo_max_brl": 3.0,
                "agendamentos_max": 3,
            },
        },
    }


def _fx_sem(caminho: list[str], base=None) -> dict:
    d = copy.deepcopy(base or _fx(1, 3.0))
    alvo = d
    for chave in caminho[:-1]:
        alvo = alvo[chave]
    del alvo[caminho[-1]]
    return d


def _fx_com(**mudancas) -> dict:
    d = _fx(1, 3.0)
    d.update(mudancas)
    return d


def _fx_faixa_extra() -> dict:
    d = _fx(1, 3.0)
    novo = {}
    for chave, valor in d["faixas"].items():
        if chave == "alta":
            novo["altissima"] = {"lembretes_max": 1, "dias_max": 1, "contrapropostas_max": 1, "custo_max_brl": 1, "agendamentos_max": 0}
        novo[chave] = valor
    d["faixas"] = novo
    return d


def _fx_pago_maior() -> dict:
    d = _fx(1, 3.0)
    d["faixas"]["muito_alta"].update(lembretes_max=1, lembrete_pago_max=2)
    return d


def _mpf(versao: int, valor: dict) -> str:
    return f"INSERT INTO ia.config_versao VALUES ('modelo_por_faixa',{versao},'{_json(valor)}',now(),'danilo@exemplo.test','teste');"


def _mp(modelo: str, provedor: str, raciocinio, custo) -> dict:
    flash = {"modelo": "deepseek-v4p1-flash-1017", "provedor": "fireworks-us", "raciocinio": False}
    return {
        "baixa": {**flash, "custo_max_brl": 1.0},
        "media": {**flash, "custo_max_brl": 2.0},
        "alta": {**flash, "custo_max_brl": 3.0},
        "muito_alta": {"modelo": modelo, "provedor": provedor, "raciocinio": raciocinio, "custo_max_brl": custo},
    }


def _ja(nome: str, versao: int, valor) -> str:
    texto = valor if isinstance(valor, str) else _json(valor)
    return f"INSERT INTO ia.config_versao VALUES ('{nome}',{versao},'{texto}',now(),'x',null);"


def _ep(espera) -> dict:
    um = {"espera": 1, "lembretes": 1, "contrapropostas": 1}
    return {
        "baixa": {
            "comercial": {"espera": espera, "lembretes": 0.5, "contrapropostas": 0.5},
            "fora": {"espera": 1.0, "lembretes": 1.0, "contrapropostas": 1.0},
        },
        "media": {"comercial": {"espera": 0.5, "lembretes": 0.5, "contrapropostas": 0.5}, "fora": dict(um)},
        "alta": {"comercial": dict(um), "fora": dict(um)},
        "muito_alta": {"comercial": dict(um), "fora": dict(um)},
    }


def _mk2(chat: str, hex2: str, cols: str, vals: str, faixa: str) -> str:
    return atd(chat, "venda:" + hex2 * 16, FP, P3, cols, vals, faixa=faixa)


def _dia(inicio: str, fim: str) -> dict:
    return {"inicio": inicio, "fim": fim}


JANELA_09_19 = {"dias": {str(d): _dia("09:00", "19:00") for d in range(1, 6)}}
FA = "INSERT INTO ia.config_versao VALUES"
CASOS_C_3A = [
    eq(
        "seed faixas_esforco: 4 faixas, limites 150/400/800 (hipótese a medir)",
        APP,
        "SELECT (valor->'limites_brl'->>0) || '/' || (valor->'limites_brl'->>1) || '/' || (valor->'limites_brl'->>2) || '/' || (SELECT count(*) FROM jsonb_object_keys(valor->'faixas')) FROM ia.config_versao WHERE nome='faixas_esforco' AND versao=1;",
        "150/400/800/4",
    ),
    ok("nova versão das faixas aceita (limites dentro do teto global)", APP, _faixas(2, _fx(0, 2.5))),
    err("faixa acima do teto global de lembretes (3 > 2) recusada", APP, _faixas(3, _fx(3, 3.0)), V),
    err("faixa acima do teto global de custo (R$ 3,50 > 3) recusada", APP, _faixas(3, _fx(1, 3.5)), V),
    err("faixa sem campo obrigatório (agendamentos_max) recusada", APP, _faixas(3, _fx_sem(["faixas", "baixa", "agendamentos_max"])), V),
    err("faixa extra (4ª faixa) recusada", APP, _faixas(3, _fx_faixa_extra()), V),
    err("config de faixas sem o objeto 'faixas' recusada", APP, _faixas(3, '{"limites_brl":[150,400,800]}'), V),
    err("config de faixas sem 'limites_brl' recusada", APP, _faixas(3, _fx_sem(["limites_brl"])), V),
    err("limites de comissão fora de ordem recusados", APP, _faixas(3, _fx_com(limites_brl=[400, 150, 800])), V),
    err("texto dentro da config de faixas recusado", APP, _faixas(3, {"obs": "x", **_fx(1, 3.0)}), V),
    ok("disparo com comissão esperada e faixa alta", APP, _mk2("chatLLLL0012", "a1", ", persona_id", ", 'P01'", "520.00, 'alta'")),
    ok("faixa muito_alta (comissão > R$ 800) aceita", APP, _mk2("chatOOOO0015", "d4", "", "", "930.00, 'muito_alta'")),
    err(
        "faixa muito_alta sobre comissão NULL recusada",
        APP,
        _mk2("chatNNNN0014", "c3", "", "", "NULL, 'muito_alta'"),
        "atendimento_esforco_check",
    ),
    ok("comissão não calculável (NULL) com faixa baixa", APP, _mk2("chatMMMM0013", "b2", "", "", "NULL, 'baixa'")),
    err("faixa 'alta' sobre comissão NULL recusada", APP, _mk2("chatNNNN0014", "c3", "", "", "NULL, 'alta'"), "atendimento_esforco_check"),
    err(
        "faixa fora de baixa|media|alta recusada",
        APP,
        _mk2("chatNNNN0014", "c3", "", "", "100.00, 'altissima'"),
        "atendimento_esforco_check",
    ),
    err("comissão negativa recusada", APP, _mk2("chatNNNN0014", "c3", "", "", "-1.00, 'baixa'"), "atendimento_esforco_check"),
    err("disparo sem faixa_esforco recusado (NOT NULL)", APP, _mk2("chatNNNN0014", "c3", "", "", "100.00, NULL"), "faixa_esforco"),
    err(
        "faixa_esforco é imutável (UPDATE negado ao ia_app)",
        APP,
        "UPDATE ia.atendimento SET faixa_esforco = 'alta' WHERE chat_id='chatLLLL0012';",
        "permission denied",
    ),
    err(
        "comissao_esperada_brl é imutável (UPDATE negado ao ia_app)",
        APP,
        "UPDATE ia.atendimento SET comissao_esperada_brl = 1 WHERE chat_id='chatLLLL0012';",
        "permission denied",
    ),
    eq(
        "seed modelo_por_faixa: mesmo modelo nas 4 faixas, raciocínio off",
        APP,
        "SELECT count(DISTINCT v.value->>'modelo') || '/' || bool_and((v.value->>'raciocinio')::boolean = false)::text || '/' || count(*) FROM ia.config_versao c, jsonb_each(c.valor) v WHERE c.nome='modelo_por_faixa' AND c.versao=1;",
        "1/true/4",
    ),
    ok("modelo_por_faixa: V4 Pro só na muito_alta (degrau)", APP, _mpf(2, _mp("deepseek-v4-pro", "fireworks-us", False, 3.0))),
    ok(
        "modelo_por_faixa: V4.1 Flash com raciocínio ligado (degrau barato)",
        APP,
        _mpf(3, _mp("deepseek-v4p1-flash-1017", "fireworks-us", True, 3.0)),
    ),
    ok("modelo_por_faixa: Gemini Flash", APP, _mpf(4, _mp("gemini-flash", "together-us", False, 2.5))),
    err("modelo_por_faixa: família fora de deepseek-*/gemini-* recusada", APP, _mpf(5, _mp("gpt-oss-120b", "fireworks-us", False, 3.0)), V),
    err(
        "modelo_por_faixa: modelo de outra empresa (prefixo qualquer) recusado",
        APP,
        _mpf(5, _mp("outro-modelo-x", "fireworks-us", False, 3.0)),
        V,
    ),
    err("modelo_por_faixa: raciocinio não booleano recusado", APP, _mpf(5, _mp("deepseek-v4-pro", "fireworks-us", "sim", 3.0)), V),
    err(
        "modelo_por_faixa: custo_max_brl acima do teto global (5 > 3) recusado",
        APP,
        _mpf(5, _mp("deepseek-v4-pro", "fireworks-us", False, 5.0)),
        V,
    ),
    err("modelo_por_faixa: provedor com caractere inválido recusado", APP, _mpf(5, _mp("deepseek-v4-pro", "Fireworks US", False, 3.0)), V),
    err(
        "modelo_por_faixa: faixa faltando recusada",
        APP,
        _mpf(5, {k: v for k, v in _mp("deepseek-v4-pro", "fireworks-us", False, 3.0).items() if k != "baixa"}),
        V,
    ),
    ok(
        "decisão do motor registra a faixa aplicada",
        APP,
        psl(", motor, turno, fase, faixa_esforco", 1, "decisao", ", 'regra', 1, 'E3', 'alta'"),
    ),
    err(
        "faixa_esforco em passo que não é decisão recusada",
        APP,
        psl(", entrega, turno, fase, verif_det, faixa_esforco", 2, "resposta_enviada", ", 'aceito', 1, 'E3', '{}', 'alta'"),
        "passo_modelo_check",
    ),
    err(
        "faixa_esforco inválida no passo recusada",
        APP,
        psl(", motor, turno, fase, faixa_esforco", 2, "decisao", ", 'regra', 1, 'E3', 'enorme'"),
        "passo_modelo_check",
    ),
    ok(
        "decisão do modelo gravada com modelo e provedor (para faixa × modelo)",
        APP,
        psl(
            ", motor, turno, fase, faixa_esforco, intencao, confianca, modelo, provedor, custo_brl",
            3,
            "decisao",
            ", 'modelo', 1, 'E3', 'alta', 'aceita', 'alta', 'deepseek-v4p1-flash-1017', 'fireworks-us', 0.0021",
        ),
    ),
    eq(
        "evolução: desfecho/custo por faixa × modelo sai de um JOIN simples",
        LEITURA,
        "SELECT a.faixa_esforco || '/' || p.modelo || '/' || p.provedor || '/' || count(*) FROM ia.atendimento a JOIN ia.passo p USING (atendimento_id) WHERE p.tipo='decisao' AND p.motor='modelo' AND a.chat_id='chatLLLL0012' GROUP BY a.faixa_esforco, p.modelo, p.provedor;",
        "alta/deepseek-v4p1-flash-1017/fireworks-us/1",
    ),
    eq(
        "limites da faixa vêm da versão vigente em iniciado_em (derivável, sem coluna)",
        APP,
        "SELECT (c.valor #>> '{faixas,alta,lembretes_max}') FROM ia.atendimento a JOIN LATERAL (SELECT valor FROM ia.config_versao WHERE nome='faixas_esforco' AND publicado_em <= a.iniciado_em ORDER BY versao DESC LIMIT 1) c ON true WHERE a.chat_id='chatLLLL0012';",
        "2",
    ),
    eq(
        "seed lembretes_max por faixa = 0/1/2/2 (ah), só muito_alta paga template",
        APP,
        "SELECT string_agg((v.value->>'lembretes_max') || ':' || (v.value->>'lembrete_pago_max'), ',' ORDER BY CASE v.key WHEN 'baixa' THEN 1 WHEN 'media' THEN 2 WHEN 'alta' THEN 3 ELSE 4 END) FROM ia.config_versao c, jsonb_each(c.valor->'faixas') v WHERE c.nome='faixas_esforco' AND c.versao=1;",
        "0:0,1:0,2:0,2:1",
    ),
    err("lembrete_pago_max maior que lembretes_max recusado", APP, _faixas(9, _fx_pago_maior()), V),
    eq(
        "seed janela_vendedores (hipótese): seg–sex 08–18, sáb 08–12, sem domingo",
        APP,
        "SELECT (valor #>> '{dias,1,fim}') || '/' || (valor #>> '{dias,6,fim}') || '/' || coalesce(valor #>> '{dias,7,inicio}', '-') FROM ia.config_versao WHERE nome='janela_vendedores' AND versao=1;",
        "18:00/12:00/-",
    ),
    eq(
        "seed janela_mensagem: seg–sáb 08–20",
        APP,
        "SELECT (valor #>> '{dias,1,inicio}') || '-' || (valor #>> '{dias,6,fim}') || '/' || coalesce(valor #>> '{dias,7,inicio}', '-') FROM ia.config_versao WHERE nome='janela_mensagem' AND versao=1;",
        "08:00-20:00/-",
    ),
    err(
        "janela_mensagem passando das 20:00 recusada (nunca ultrapassada)",
        APP,
        _ja("janela_mensagem", 2, {"dias": {"1": _dia("08:00", "21:00")}}),
        V,
    ),
    err("janela_mensagem antes das 08:00 recusada", APP, _ja("janela_mensagem", 2, {"dias": {"1": _dia("07:00", "20:00")}}), V),
    err("janela_mensagem no domingo recusada", APP, _ja("janela_mensagem", 2, {"dias": {"7": _dia("09:00", "12:00")}}), V),
    err("janela_mensagem com fim antes do início recusada", APP, _ja("janela_mensagem", 2, {"dias": {"1": _dia("20:00", "08:00")}}), V),
    err("janela_mensagem sem 'dias' recusada", APP, _ja("janela_mensagem", 2, {"x": 1}), V),
    ok("janela_mensagem mais curta (seg–sex 09–19) aceita", APP, _ja("janela_mensagem", 2, JANELA_09_19)),
    ok(
        "janela_vendedores pode incluir o domingo e passar das 18h (é só o período comercial)",
        APP,
        _ja("janela_vendedores", 2, {"dias": {"1": _dia("08:00", "22:00"), "7": _dia("09:00", "12:00")}}),
    ),
    err("dia fora de 1..7 recusado", APP, _ja("janela_vendedores", 3, {"dias": {"8": ["08:00", "12:00"]}}), V),
    err(
        "agenda_janela fora da janela de mensagem (fim 21:00) recusada",
        APP,
        _ja("agenda_janela", 3, {"inicio": "08:30", "fim": "21:00"}),
        V,
    ),
    eq(
        "seed esforco_por_periodo: 4 faixas × comercial|fora; comercial = repasse mais cedo (multiplicador < 1)",
        APP,
        "SELECT count(*) || '/' || bool_and((p.value->'comercial'->>'espera')::numeric <= (p.value->'fora'->>'espera')::numeric)::text FROM ia.config_versao c, jsonb_each(c.valor) p WHERE c.nome='esforco_por_periodo' AND c.versao=1;",
        "4/true",
    ),
    ok("esforco_por_periodo válido aceito", APP, _ja("esforco_por_periodo", 2, _ep(0.5))),
    err("multiplicador acima de 2 recusado", APP, _ja("esforco_por_periodo", 3, _ep(3)), V),
    err("multiplicador negativo recusado", APP, _ja("esforco_por_periodo", 3, _ep(-1)), V),
    err("esforco_por_periodo sem o período 'fora' recusado", APP, _ja("esforco_por_periodo", 3, _fx_sem(["baixa", "fora"], _ep(0.5))), V),
    err(
        "esforco_por_periodo com período extra ('noite') recusado",
        APP,
        _ja(
            "esforco_por_periodo",
            3,
            {**_ep(0.5), "baixa": {"noite": {"espera": 1, "lembretes": 1, "contrapropostas": 1}, **_ep(0.5)["baixa"]}},
        ),
        V,
    ),
    err("esforco_por_periodo sem uma faixa recusado", APP, _ja("esforco_por_periodo", 3, _fx_sem(["muito_alta"], _ep(0.5))), V),
]

PAUSA_OK = ", retoma_em = now() + interval '3 hours', lease_ate = now() + interval '3 hours 30 minutes'"
PAUSA_FORA = ", retoma_em = now() + interval '3 hours', lease_ate = now() + interval '4 hours'"
M1, M2, M3 = (f"cg:0123456789abcdef01234567:{n * 16}" for n in "123")


def _pausa(estado_conversa: str, extra: str) -> str:
    return f"UPDATE ia.atendimento SET estado='pausado', estado_conversa='{estado_conversa}'{extra} WHERE chat_id='chatRRRR0016';"


def _agd(pessoa: str, seq: int, msg: str, texto_hash: str = FP, retoma: str = "'E4'") -> str:
    chave = f"agenda:@@PAT@@:{seq}"
    return (
        "INSERT INTO ia.agendamento (atendimento_id, pessoa_id, chat_id, entrada, seq, msg_chave, texto_hash, retoma_fase, chave_logica, idem_key)"
        f" VALUES ('@@PAT@@','{pessoa}','chatRRRR0016','pausa_ia',{seq},'{msg}','{texto_hash}',{retoma},'{chave}',encode(sha256(convert_to('{chave}','UTF8')),'hex'));"
    )


def _pas_a(atendimento: str, cols: str, ordem: int, vals: str) -> str:
    return f"INSERT INTO ia.passo (atendimento_id, ordem, tipo, texto, turno, fase{cols}) VALUES ('{atendimento}',{ordem},'agendamento','x',2,'E4'{vals});"


def _mkb(chat: str, cols: str, vals: str) -> str:
    return atd(chat, f"agendar:{chat}:0f1e2d3c4b5a6978", FP, P2, cols, vals, gatilho="agendamento")


RET, RETV = ", retoma_em, lease_ate", ", now() + interval '3 hours', now() + interval '3 hours 30 minutes'"
P_CONF = '{"fase":"E4","pausa":{"retoma_fase":"E4"}}'
CASOS_C_3B = [
    eq(
        "seed agenda_janela 08:30–19:00 (sábado até 12:00 no piloto)",
        APP,
        "SELECT (valor->>'inicio') || '-' || (valor->>'fim') || '-' || (valor->>'sabado_fim') FROM ia.config_versao WHERE nome='agenda_janela';",
        "08:30-19:00-12:00",
    ),
    eq(
        "seeds agenda_*: desligado, teto 23 h, máx 2 por atendimento, (b) não digita, 10 pausados, folga 30",
        APP,
        "SELECT string_agg(nome || '=' || (valor #>> '{}'), ',' ORDER BY nome) FROM ia.config_versao WHERE nome IN ('agenda_ativa','agenda_teto_horas','agenda_max_por_atendimento','agenda_b_digita','agenda_max_pausados','agenda_folga_min');",
        "agenda_ativa=false,agenda_b_digita=false,agenda_folga_min=30,agenda_max_pausados=10,agenda_max_por_atendimento=2,agenda_teto_horas=23",
    ),
    err("agenda_janela com fim antes do início recusada", APP, _ja("agenda_janela", 2, {"inicio": "19:00", "fim": "08:30"}), V),
    err("agenda_janela com hora mal formada recusada", APP, _ja("agenda_janela", 2, {"inicio": "8:30", "fim": "19:00"}), V),
    err(
        "agenda_janela com sabado_fim depois do fim recusada",
        APP,
        _ja("agenda_janela", 2, {"inicio": "08:30", "fim": "19:00", "sabado_fim": "20:00"}),
        V,
    ),
    ok("agenda_janela nova (sem sabado_fim) aceita", APP, _ja("agenda_janela", 2, {"inicio": "09:00", "fim": "18:30"})),
    err("agenda_teto_horas = 24 recusado (janela de 24 h do WhatsApp)", APP, _ja("agenda_teto_horas", 2, "24"), V),
    err("agenda_max_por_atendimento = 3 recusado (teto do DDL: seq 1..2)", APP, _ja("agenda_max_por_atendimento", 2, "3"), V),
    err("agenda_ativa não booleano recusado", APP, _ja("agenda_ativa", 2, '"sim"'), V),
    # caso (a): pausa combinada
    err(
        "pausado sem retoma_em recusado",
        APP,
        _pausa(P_CONF, ""),
        "atendimento_conversa_check",
        antes=(
            (
                APP,
                mk("chatRRRR0016", "e5", P1)
                + " UPDATE ia.atendimento SET estado='aguardando_cliente', assumido_em=now(), estado_conversa='{\"fase\":\"E4\"}' WHERE chat_id='chatRRRR0016';",
            ),
        ),
    ),
    err(
        "pausa em E7 (T7/T8 em voo) recusada",
        APP,
        _pausa('{"fase":"E7","pausa":{"retoma_fase":"E7"}}', PAUSA_FORA),
        "atendimento_conversa_check",
    ),
    err(
        "pausa com fase diferente de pausa.retoma_fase recusada",
        APP,
        _pausa('{"fase":"E4","pausa":{"retoma_fase":"E5"}}', PAUSA_FORA),
        "atendimento_conversa_check",
    ),
    err(
        "lease_ate antes de retoma_em recusado",
        APP,
        _pausa(P_CONF, ", retoma_em = now() + interval '3 hours', lease_ate = now() + interval '1 hour'"),
        "atendimento_conversa_check",
    ),
    ok("pausado em E4 com retoma_em e lease até retoma_em + folga", APP, _pausa(P_CONF, PAUSA_OK)),
    eq(
        "pausado guarda a fase de volta (fase gerada = E4)",
        APP,
        "SELECT estado || '/' || fase FROM ia.atendimento WHERE chat_id='chatRRRR0016';",
        "pausado/E4",
    ),
    err("pausado ainda tranca o chat (trava por chat)", APP, mk("chatRRRR0016", "f6", P1), "atendimento_ativo_chat_uq"),
    eq(
        "v_prontidao: pausado fora de 'abertos', com próxima retomada",
        APP,
        "SELECT pausados >= 1 AND proxima_retomada_em IS NOT NULL AND abertos = (SELECT count(*) FROM ia.atendimento WHERE estado NOT IN ('encerrado','pausado') AND NOT (gatilho='agendamento' AND estado='reservado')) FROM ia.v_prontidao;",
        "t",
    ),
    ok("agendamento 1 (pausa_ia, pendente), sem texto: só o HMAC", APP, _agd(P1, 1, M1)),
    err("pausa_ia sem retoma_fase recusada", APP, _agd(P1, 2, M2, retoma="NULL"), "agendamento_forma_check"),
    err("retoma_fase E7 recusada", APP, _agd(P1, 2, M2, retoma="'E7'"), "agendamento_forma_check"),
    err("texto_hash que não é hex de 64 recusado", APP, _agd(P1, 2, M2, "texto em claro"), "agendamento_forma_check"),
    err("2º agendamento ATIVO no mesmo atendimento recusado (índice parcial)", APP, _agd(P1, 2, M2), "agendamento_ativo_uq"),
    err(
        "confirmado sem confirmado_em/horário recusado",
        APP,
        "UPDATE ia.agendamento SET estado='confirmado' WHERE atendimento_id='@@PAT@@' AND seq=1;",
        "agendamento_estado_check",
    ),
    err(
        "dispara_em antes do pedido recusado",
        APP,
        "UPDATE ia.agendamento SET estado='confirmado', confirmado_em=now(), horario_extraido=now(), dispara_em=pedido_em - interval '1 hour', confirmacao_origem='cliente' WHERE atendimento_id='@@PAT@@' AND seq=1;",
        "agendamento_forma_check",
    ),
    ok(
        "confirmado (extração alta, confirmação do cliente, dispara_em, versao+1)",
        APP,
        "UPDATE ia.agendamento SET estado='confirmado', confirmado_em=now(), proposto_em=now(), horario_extraido=now() + interval '3 hours', dispara_em=now() + interval '3 hours', confirmacao_origem='cliente', confianca='alta', tipo_extracao='hora_relativa', extrator_versao='1.0.0', versao=2 WHERE atendimento_id='@@PAT@@' AND seq=1;",
    ),
    err(
        "cancelado sem cancelado_por recusado",
        APP,
        "UPDATE ia.agendamento SET estado='cancelado', cancelado_em=now() WHERE atendimento_id='@@PAT@@' AND seq=1;",
        "agendamento_estado_check",
    ),
    err(
        "disparado sem desfecho_disparo recusado",
        APP,
        "UPDATE ia.agendamento SET estado='disparado', disparado_em=now() WHERE atendimento_id='@@PAT@@' AND seq=1;",
        "agendamento_estado_check",
    ),
    ok(
        "reagendar: o cliente muda o horário, o anterior cancela com 'reagendado'",
        APP,
        "UPDATE ia.agendamento SET estado='cancelado', cancelado_por='reagendado', cancelado_em=now(), versao=3 WHERE atendimento_id='@@PAT@@' AND seq=1;",
    ),
    err("pessoa que não é a do atendimento recusada (FK composta)", APP, _agd(P3, 2, M2), "agendamento_atendimento_fk"),
    err("mesma mensagem não gera 2º agendamento (Post repetido pelo ChatGuru)", APP, _agd(P1, 2, M1), "agendamento_msg_uq"),
    ok("agendamento 2 (o 2º e último permitido)", APP, _agd(P1, 2, M2)),
    err("3º agendamento no atendimento recusado (máx. 2)", APP, _agd(P1, 3, M3), "agendamento_forma_check"),
    ok(
        "agendamento 2 confirmado e disparado (retomou)",
        APP,
        "UPDATE ia.agendamento SET estado='confirmado', confirmado_em=now(), horario_extraido=now() + interval '1 hour', dispara_em=now() + interval '1 hour', confirmacao_origem='tacita', versao=2 WHERE atendimento_id='@@PAT@@' AND seq=2;"
        " UPDATE ia.agendamento SET estado='disparado', disparado_em=now(), desfecho_disparo='retomou', versao=3 WHERE atendimento_id='@@PAT@@' AND seq=2;",
    ),
    ok(
        "passo 'agendamento' liga ao agendamento (resultado disparado)",
        APP,
        _pas_a("@@PAT@@", ", agendamento_id, resultado", 1, ", '@@AID@@', 'disparado'"),
    ),
    err(
        "passo 'agendamento' sem agendamento_id recusado",
        APP,
        _pas_a("@@PAT@@", ", resultado", 2, ", 'disparado'"),
        "passo_auditoria_check",
    ),
    err(
        "passo 'agendamento' com resultado fora do vocabulário recusado",
        APP,
        _pas_a("@@PAT@@", ", agendamento_id, resultado", 2, ", '@@AID@@', 'xyz'"),
        "passo_auditoria_check",
    ),
    err(
        "passo apontando agendamento de OUTRO atendimento recusado (FK composta)",
        APP,
        _pas_a("@@ID1@@", ", agendamento_id, resultado", 3000, ", '@@AID@@', 'proposto'"),
        "passo_agendamento_fk",
    ),
    ok(
        "volta da pausa: aguardando_cliente sem retoma_em",
        APP,
        "UPDATE ia.atendimento SET estado='aguardando_cliente', retoma_em=NULL WHERE chat_id='chatRRRR0016';",
    ),
    err(
        "retoma_em fora de pausado/agendado recusado",
        APP,
        "UPDATE ia.atendimento SET retoma_em=now() WHERE chat_id='chatRRRR0016';",
        "atendimento_conversa_check",
    ),
    eq("ia_leitura lê agendamentos (sem texto: só hash)", LEITURA, "SELECT count(*) >= 2 FROM ia.agendamento;", "t"),
    err("ia_qualidade não lê agendamentos", QUALIDADE, "SELECT * FROM ia.agendamento;", "permission denied"),
    # caso (b): atendimento 'agendamento' reservado de vida longa
    err("gatilho 'agendamento' reservado sem retoma_em recusado", APP, _mkb("chatSSSS0017", "", ""), "atendimento_conversa_check"),
    ok("gatilho 'agendamento' (caso b): reservado de vida longa, sem tocar o chat", APP, _mkb("chatSSSS0017", RET, RETV)),
    err(
        "retoma_em em 'reservado' de gatilho venda recusado",
        APP,
        mk("chatTTTT0018", "9a", P2, ", retoma_em", ", now() + interval '3 hours'"),
        "atendimento_conversa_check",
    ),
    eq(
        "v_prontidao: o agendado não conta como aberto",
        APP,
        "SELECT agendados >= 1 AND abertos = (SELECT count(*) FROM ia.atendimento WHERE estado NOT IN ('encerrado','pausado') AND NOT (gatilho='agendamento' AND estado='reservado')) FROM ia.v_prontidao;",
        "t",
    ),
    eq(
        "reservado que nunca disparou vira abortado/agenda_nao_disparou",
        APP,
        "SELECT desfecho || '/' || motivo_desfecho FROM ia.atendimento WHERE chat_id='chatSSSS0017';",
        "abortado/agenda_nao_disparou",
        antes=(
            (
                APP,
                "UPDATE ia.atendimento SET estado='encerrado', desfecho='abortado', motivo_desfecho='agenda_nao_disparou', encerrado_em=now(), lease_ate=NULL WHERE chat_id='chatSSSS0017';",
            ),
        ),
    ),
    eq(
        "caso (b): iniciar → E3 e a venda é possível (gatilho agendamento pode 'vendeu')",
        APP,
        "SELECT gatilho || '/' || desfecho FROM ia.atendimento WHERE chat_id='chatUUUU0019';",
        "agendamento/vendeu",
        antes=(
            (
                APP,
                _mkb("chatUUUU0019", RET, RETV)
                + " UPDATE ia.atendimento SET estado='aberto', assumido_em=now(), retoma_em=NULL, estado_conversa='{\"fase\":\"E3\"}' WHERE chat_id='chatUUUU0019';"
                " UPDATE ia.atendimento SET estado='encerrado', desfecho='vendeu', encerrado_em=now(), lease_ate=NULL WHERE chat_id='chatUUUU0019';",
            ),
        ),
    ),
]

SEM_VERIF = ", entrega, turno, fase, verif_det, tx_id"
CASOS_C_3C = [
    *[
        ok(f"resposta_enviada aceita tx_id {tx}", APP, pas(SEM_VERIF, "resposta_enviada", f", 'aceito', 3, 'E3', '{{}}', '{tx}'"))
        for tx in ("TX-03", "TX-M01", "TX-M13", "TX-42")
    ],
    *[
        err(f"tx_id {tx} recusado", APP, pas(SEM_VERIF, "resposta_enviada", f", 'aceito', 3, 'E3', '{{}}', '{tx}'"), "passo_turno_check")
        for tx in ("TX-X01", "TX-M1", "TX-123", "tx-03", "TX-MM01")
    ],
    ok(
        "nota de devolução de K: passo repasse (etapa nota) com tx_id",
        APP,
        pas(", repasse_etapa, turno, fase, tx_id", "repasse", ", 'nota', 5, 'E10', 'TX-42'"),
    ),
    ok(
        "texto M do agendamento: passo agendamento com tx_id TX-M09",
        APP,
        _pas_a("@@PAT@@", ", agendamento_id, resultado, tx_id", 50, ", '@@AID@@', 'proposto', 'TX-M09'"),
    ),
    err(
        "tx_id em decisão recusado (só passos que falam ou notam)",
        APP,
        pas(", motor, turno, fase, tx_id", "decisao", ", 'regra', 3, 'E3', 'TX-03'"),
        "passo_turno_check",
    ),
    err(
        "intencao em mensagem_recebida recusada (só decisão do modelo)",
        APP,
        "INSERT INTO ia.passo (atendimento_id, ordem, tipo, texto, msg_chave, msg_fingerprint, msg_tipo, msg_tamanho, origem_evento, turno, fase, intencao)"
        f" VALUES ('@@ID1@@',(SELECT coalesce(max(ordem),0)+1 FROM ia.passo WHERE atendimento_id='@@ID1@@'),'mensagem_recebida','x','cg:0123456789abcdef01234567:9999999999999999','{FP}','texto',3,'webhook',3,'E2','aceita');",
        "passo_modelo_check",
    ),
    err(
        "objecao em mensagem_recebida recusada",
        APP,
        "INSERT INTO ia.passo (atendimento_id, ordem, tipo, texto, msg_chave, msg_fingerprint, msg_tipo, msg_tamanho, origem_evento, turno, fase, objecao)"
        f" VALUES ('@@ID1@@',(SELECT coalesce(max(ordem),0)+1 FROM ia.passo WHERE atendimento_id='@@ID1@@'),'mensagem_recebida','x','cg:0123456789abcdef01234567:8888888888888888','{FP}','texto',3,'webhook',3,'E2','parcela_alta');",
        "passo_modelo_check",
    ),
    err(
        "confianca em resposta_enviada recusada",
        APP,
        pas(", entrega, turno, fase, verif_det, confianca", "resposta_enviada", ", 'aceito', 3, 'E3', '{}', 'alta'"),
        "passo_modelo_check",
    ),
    eq(
        "seed bloqueio_entrada=false e chats_teste=[] (allowlist vazia: nenhum chat é teste)",
        APP,
        "SELECT string_agg(nome || '=' || (valor #>> '{}'), ',' ORDER BY nome) FROM ia.config_versao WHERE nome IN ('bloqueio_entrada','chats_teste') AND versao=1;",
        "bloqueio_entrada=false,chats_teste=[]",
    ),
    eq(
        "seed agenda_max_dia=5 e agenda_periodos (noite = 19:00, o teto da janela)",
        APP,
        "SELECT (SELECT valor #>> '{}' FROM ia.config_versao WHERE nome='agenda_max_dia' AND versao=1) || '/' || (SELECT valor->>'noite' FROM ia.config_versao WHERE nome='agenda_periodos' AND versao=1);",
        "5/19:00",
    ),
    eq(
        "verificador_modelo não tem seed (padrão na aplicação: sem modelo no verificador)",
        APP,
        "SELECT count(*) FROM ia.config_versao WHERE nome='verificador_modelo';",
        "0",
    ),
    err("bloqueio_entrada não booleano recusado", APP, _ja("bloqueio_entrada", 2, '"sim"'), V),
    ok("bloqueio_entrada=true (timer das 20:15) aceito", APP, _ja("bloqueio_entrada", 2, "true")),
    ok("chats_teste com ids válidos aceito", APP, _ja("chats_teste", 2, ["65f1c2a9b8d7e6f5a4b3c2d1", "teste_chat_01"])),
    err("chats_teste com id inválido (espaço) recusado", APP, _ja("chats_teste", 3, ["chat com espaço"]), V),
    err("chats_teste que não é lista de textos recusado", APP, _ja("chats_teste", 3, [123]), V),
    err("chats_teste com mais de 50 ids recusado", APP, _ja("chats_teste", 3, [f"c{i:02d}" for i in range(51)]), V),
    err("agenda_periodos com hora fora da janela de mensagem (21:00) recusado", APP, _ja("agenda_periodos", 2, {"noite": "21:00"}), V),
    err("agenda_periodos com hora mal formada recusado", APP, _ja("agenda_periodos", 2, {"manha": "9h"}), V),
    ok("agenda_periodos novo aceito", APP, _ja("agenda_periodos", 2, {"manha": "09:30", "tarde": "15:00"})),
    err("agenda_max_dia = 0 recusado", APP, _ja("agenda_max_dia", 2, "0"), V),
]
CASOS_C = [*CASOS_C_3A, *CASOS_C_3B, *CASOS_C_3C]
