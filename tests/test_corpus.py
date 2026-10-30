"""Corpus da F3 (B8.1a): 60 personas + 24 P-M + 40 diálogos-gabarito + semente. Tudo INVENTADO: nada de conversa real, só CPF `000.000.0nn`.

Um teste por regra do validador. Cada regra tem um caso que reprova por MUTAÇÃO do corpus em memória (copia o bruto, estraga um ponto,
espera a violação com o código da regra); o corpus de verdade tem de passar sem nenhuma violação.
"""

from __future__ import annotations

import copy
import importlib.util
import statistics
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ia_atendimento import corpus as c

RAIZ = Path(__file__).resolve().parent.parent
CPF_REAL_DE_EXEMPLO = "529.982.247-25"  # DV válido e FORA da faixa sintética: tem de reprovar onde aparecer


@pytest.fixture(scope="module")
def bruto_original() -> dict:
    return c.carregar_bruto()


@pytest.fixture
def bruto(bruto_original: dict) -> dict:
    return copy.deepcopy(bruto_original)


def _codigos(violacoes: list[str]) -> set[str]:
    return {v.split(":", 1)[0] for v in violacoes}


def _reprova(bruto: dict, codigo: str) -> list[str]:
    achadas = [v for v in c.validar(bruto) if v.startswith(codigo + ":")]
    assert achadas, f"a mutação não foi pega pela regra {codigo}; violações: {sorted(_codigos(c.validar(bruto)))}"
    return achadas


def _persona(bruto: dict, pid: str) -> dict:
    return next(p for p in bruto["personas"] + bruto["personas_m"] if p["id"] == pid)


def _turnos_do_cliente(bruto: dict):
    for pid, turnos in bruto["dialogos"].items():
        for t in turnos:
            if t["quem"] == "cliente" and t.get("texto_cliente"):
                yield pid, t


# --- o corpus de verdade -----------------------------------------------------------------------------------------------------------


def test_corpus_de_verdade_passa_em_todas_as_regras(bruto_original):
    assert c.validar(bruto_original) == []


def test_contagens_do_roteiro(bruto_original):
    corpus = c.montar(bruto_original)
    assert len(corpus.personas) == 60
    assert sum(p.f3_curta for p in corpus.personas) == 40
    assert len(corpus.personas_m) == 24
    assert len(corpus.dialogos) == 40
    assert sum(len(d.turnos) for d in corpus.dialogos.values()) >= 300
    assert {p.id for p in corpus.personas if p.f3_curta} == set(corpus.dialogos)
    assert frozenset(p.id for p in corpus.personas if p.f3_curta) == c.F3_CURTA_IDS


def test_cobertura_minima_do_corpus_de_verdade(bruto_original):
    corpus = c.montar(bruto_original)
    todas = [*corpus.personas, *corpus.personas_m]
    for inv in c.INVARIANTES:
        assert sum(inv in p.invariantes_em_risco for p in todas) >= c.MIN_PERSONAS_POR_INVARIANTE, inv
    assert {f for p in todas for f in p.fases} == set(c.FASES)
    assert {i for p in todas for i in p.comportamento.intencoes} >= set(c.INTENCOES)
    assert {o for p in todas for o in p.comportamento.objecoes} >= set(c.OBJECOES)
    assert {e for p in todas for e in p.em} == set(c.EMS)
    assert {p.desfecho_esperado for p in todas} == set(c.DESFECHOS)


def test_varredura_do_repositorio_limpa_nos_arquivos_do_corpus():
    """A varredura do portão (scripts/varredura.py) enxerga CPF, celular e e-mail: nos arquivos do corpus só passa o sintético."""
    spec = importlib.util.spec_from_file_location("varredura_corpus", RAIZ / "scripts" / "varredura.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    arquivos = sorted((RAIZ / "tests" / "corpus").rglob("*.json*"))
    assert len(arquivos) >= 44
    assert [a for arq in arquivos for a in modulo.varrer(arq)] == []


# --- esquema (Pydantic extra='forbid') ----------------------------------------------------------------------------------------------


def test_esquema_recusa_campo_extra_na_persona(bruto):
    bruto["personas"][0]["telefone"] = "x"
    assert _codigos(c.validar(bruto)) >= {"esquema"}


def test_esquema_recusa_campo_extra_no_turno(bruto):
    bruto["dialogos"]["P01"][0]["texto_da_ia"] = "x"
    assert "esquema" in _codigos(c.validar(bruto))


def test_esquema_recusa_valor_fora_dos_enums(bruto):
    _persona(bruto, "P01")["desfecho_esperado"] = "ganhou"
    assert "esquema" in _codigos(c.validar(bruto))


# --- 1. ids únicos -------------------------------------------------------------------------------------------------------------------


def test_ids_unicos_reprova_id_repetido(bruto):
    bruto["personas"][1]["id"] = bruto["personas"][0]["id"]
    _reprova(bruto, "ids_unicos")


def test_ids_unicos_reprova_id_de_h_na_lista_m(bruto):
    bruto["personas_m"][0]["id"] = "P01"
    assert "ids_unicos" in _codigos(c.validar(bruto)) or "esquema" in _codigos(c.validar(bruto))


def test_ids_unicos_reprova_nome_repetido(bruto):
    bruto["personas"][1]["nome"] = bruto["personas"][0]["nome"]
    _reprova(bruto, "ids_unicos")


# --- 2. CPF sintético ---------------------------------------------------------------------------------------------------------------


def test_cpf_sintetico_reprova_cpf_com_dv_valido_fora_da_faixa(bruto):
    _persona(bruto, "P01")["cpf"] = CPF_REAL_DE_EXEMPLO
    _reprova(bruto, "cpf_sintetico")


def test_cpf_sintetico_reprova_dv_errado(bruto):
    _persona(bruto, "P02")["cpf"] = "000.000.002-00"
    _reprova(bruto, "cpf_sintetico")


def test_cpf_sintetico_reprova_sem_formatacao(bruto):
    _persona(bruto, "P02")["cpf"] = "00000000272"
    assert _codigos(c.validar(bruto)) & {"cpf_sintetico", "esquema"}


def test_cpf_alinhado_ao_duble_reprova_cpf_de_outra_persona(bruto):
    _persona(bruto, "P01")["cpf"] = "000.000.002-72"  # sintético e válido, mas é o do aprovado-36
    _reprova(bruto, "cpf_alinhado_duble")


def test_cpf_alinhado_ao_duble_reprova_persona_duble_inexistente(bruto):
    _persona(bruto, "P01")["cenario_facta"]["persona_duble"] = "nao-existe"
    _reprova(bruto, "cpf_alinhado_duble")


def test_cpf_alinhado_ao_duble_reprova_persona_fora_da_lista_f3_do_duble(bruto):
    _persona(bruto, "P01")["cenario_facta"].update(persona_duble="aprovado-36")
    _persona(bruto, "P01")["cpf"] = "000.000.002-72"
    _reprova(bruto, "cpf_alinhado_duble")


def test_cpf_alinhado_ao_duble_reprova_sem_facta_com_cpf_do_duble(bruto):
    _persona(bruto, "P36")["cpf"] = "000.000.001-91"  # P36 não tem stub na FACTA: não pode usar CPF de persona do dublê
    _reprova(bruto, "cpf_alinhado_duble")


def test_cpf_alinhado_ao_duble_reprova_cenario_diferente_do_snapshot(bruto):
    _persona(bruto, "P01")["cenario_facta"]["cenario"] = "recusa"
    _reprova(bruto, "cpf_alinhado_duble")


# --- 3. conjunto f3_curta e 4. diálogo para toda f3 --------------------------------------------------------------------------------


def test_conjunto_f3_curta_reprova_persona_fora_da_lista_do_roteiro(bruto):
    _persona(bruto, "P09")["f3_curta"] = True
    _reprova(bruto, "conjunto_f3_curta")


def test_conjunto_f3_curta_reprova_persona_tirada(bruto):
    _persona(bruto, "P01")["f3_curta"] = False
    _reprova(bruto, "conjunto_f3_curta")


def test_conjunto_f3_curta_reprova_contagem_de_60_e_24(bruto):
    bruto["personas"].pop()
    _reprova(bruto, "conjunto_f3_curta")


def test_f3_com_dialogo_reprova_persona_sem_dialogo(bruto):
    del bruto["dialogos"]["P01"]
    _reprova(bruto, "f3_com_dialogo")


def test_f3_com_dialogo_reprova_dialogo_de_persona_fora_da_f3(bruto):
    bruto["dialogos"]["P09"] = copy.deepcopy(bruto["dialogos"]["P01"])
    _reprova(bruto, "f3_com_dialogo")


def test_f3_com_dialogo_reprova_dialogo_vazio_ou_que_nao_abre_com_a_ia(bruto):
    bruto["dialogos"]["P01"] = bruto["dialogos"]["P01"][1:]
    _reprova(bruto, "f3_com_dialogo")


# --- 5-9. cobertura ----------------------------------------------------------------------------------------------------------------


def test_cobertura_invariantes_reprova_invariante_com_menos_de_tres_personas(bruto):
    for p in bruto["personas"] + bruto["personas_m"]:
        p["invariantes_em_risco"] = [i for i in p["invariantes_em_risco"] if i != "I7"]
        for t in bruto["dialogos"].get(p["id"], []):
            t["invariantes"] = [i for i in t["invariantes"] if i != "I7"]
    bruto["personas"][0]["invariantes_em_risco"].append("I7")
    achadas = _reprova(bruto, "cobertura_invariantes")
    assert any("I7" in a for a in achadas)


def test_cobertura_invariantes_reprova_quando_so_o_hold_out_cobre(bruto):
    alvo = c.montar(bruto).semente.holdout
    for p in bruto["personas"] + bruto["personas_m"]:
        if p["id"] not in alvo:
            p["invariantes_em_risco"] = [i for i in p["invariantes_em_risco"] if i != "I9"]
    _reprova(bruto, "cobertura_invariantes")


def test_cobertura_fases_reprova_fase_sem_persona(bruto):
    for p in bruto["personas"] + bruto["personas_m"]:
        p["fases"] = [f for f in p["fases"] if f != "E4"]
    achadas = _reprova(bruto, "cobertura_fases")
    assert any("E4" in a for a in achadas)


def test_cobertura_intencoes_reprova_intencao_de_h_sem_persona(bruto):
    for p in bruto["personas"] + bruto["personas_m"]:
        p["comportamento"]["intencoes"] = [i for i in p["comportamento"]["intencoes"] if i != "sinal_fraude_ou_vulnerabilidade"]
        if p["comportamento"]["intencao_dominante"] == "sinal_fraude_ou_vulnerabilidade":
            p["comportamento"]["intencao_dominante"] = "saudacao"
    achadas = _reprova(bruto, "cobertura_intencoes")
    assert any("sinal_fraude_ou_vulnerabilidade" in a for a in achadas)


def test_cobertura_objecoes_reprova_objecao_sem_persona(bruto):
    for p in bruto["personas"] + bruto["personas_m"]:
        p["comportamento"]["objecoes"] = [o for o in p["comportamento"]["objecoes"] if o != "receio_dados"]
    achadas = _reprova(bruto, "cobertura_objecoes")
    assert any("receio_dados" in a for a in achadas)


def test_cobertura_em_reprova_em_sem_persona(bruto):
    for p in bruto["personas_m"]:
        p["em"] = [e for e in p["em"] if e != "EM7"]
    achadas = _reprova(bruto, "cobertura_em")
    assert any("EM7" in a for a in achadas)


def test_cobertura_cenarios_reprova_cenario_obrigatorio_sem_persona(bruto):
    for p in bruto["personas"] + bruto["personas_m"]:
        if p["contexto"]["cenario_tempo"] == "feriado_20_11":
            p["contexto"]["cenario_tempo"] = "horario_normal"
            p["contexto"]["inicio_utc"] = "2026-11-17T14:00:00Z"
    achadas = _reprova(bruto, "cobertura_cenarios")
    assert any("feriado_20_11" in a for a in achadas)


def test_cobertura_cenarios_reprova_sem_cliente_hostil(bruto):
    for p in bruto["personas"] + bruto["personas_m"]:
        p["comportamento"]["hostil"] = False
    _reprova(bruto, "cobertura_cenarios")


# --- 10. PII ----------------------------------------------------------------------------------------------------------------------


def test_pii_texto_reprova_cpf_com_dv_valido_fora_da_faixa(bruto):
    _, turno = next(_turnos_do_cliente(bruto))
    turno["texto_cliente"] = f"meu cpf e {CPF_REAL_DE_EXEMPLO}"
    turno["pii_digitada"] = ["cpf"]
    _reprova(bruto, "pii_texto")


def test_pii_texto_reprova_cpf_real_numa_variacao(bruto):
    _, turno = next(_turnos_do_cliente(bruto))
    turno["variacoes"] = [f"{CPF_REAL_DE_EXEMPLO.replace('.', '').replace('-', '')}"]
    turno["pii_digitada"] = ["cpf"]
    _reprova(bruto, "pii_texto")


def test_pii_texto_reprova_celular_fora_da_lista_sintetica(bruto):
    _, turno = next(_turnos_do_cliente(bruto))
    turno["texto_cliente"] = "meu zap (11) 98123" + "-4567"  # montado em pedaços: o próprio teste não pode acusar a varredura
    turno["pii_digitada"] = ["telefone"]
    _reprova(bruto, "pii_texto")


def test_pii_texto_reprova_email_de_dominio_real(bruto):
    _, turno = next(_turnos_do_cliente(bruto))
    turno["texto_cliente"] = "pix fulano@empresa" + ".com.br"
    turno["pii_digitada"] = ["email"]
    _reprova(bruto, "pii_texto")


def test_pii_texto_reprova_pii_sintetica_nao_declarada(bruto):
    _, turno = next(_turnos_do_cliente(bruto))
    turno["texto_cliente"] = "meu cpf 000.000.001-91"
    turno["pii_digitada"] = []
    _reprova(bruto, "pii_texto")


def test_pii_texto_reprova_declaracao_sem_o_dado_no_texto(bruto):
    _, turno = next(_turnos_do_cliente(bruto))
    turno["texto_cliente"] = "ok"
    turno["variacoes"] = []
    turno["pii_digitada"] = ["cpf"]
    _reprova(bruto, "pii_texto")


def test_pii_texto_aceita_pii_sintetica_declarada(bruto):
    _, turno = next(_turnos_do_cliente(bruto))
    turno["texto_cliente"] = "meu cpf 000.000.001-91 e (11) 91234-5678 e pix a@exemplo.test"
    turno["variacoes"] = []
    turno["pii_digitada"] = ["cpf", "telefone", "email"]
    assert not [v for v in c.validar(bruto) if v.startswith("pii_texto:")]


def test_pii_texto_reprova_pii_em_campo_de_persona(bruto):
    _persona(bruto, "P01")["cenario_facta"]["resumo"] = f"cliente {CPF_REAL_DE_EXEMPLO}"
    _reprova(bruto, "pii_texto")


# --- 11. placeholders e nomes ---------------------------------------------------------------------------------------------------------


def test_placeholder_fechado_reprova_placeholder_fora_do_conjunto(bruto):
    _, turno = next(_turnos_do_cliente(bruto))
    turno["texto_cliente"] = "manda {{cpf}} ai"
    _reprova(bruto, "placeholder_fechado")


def test_placeholder_fechado_reprova_chave_aberta_sem_fechar(bruto):
    _, turno = next(_turnos_do_cliente(bruto))
    turno["texto_cliente"] = "mostra {{valor_liberado"
    _reprova(bruto, "placeholder_fechado")


def test_placeholder_fechado_aceita_o_conjunto_dos_tx(bruto):
    _, turno = next(_turnos_do_cliente(bruto))
    turno["texto_cliente"] = "mostra {{valor_liberado}} e {{banco}}"
    assert not [v for v in c.validar(bruto) if v.startswith("placeholder_fechado:")]


def test_placeholder_fechado_reprova_tx_inexistente(bruto):
    bruto["dialogos"]["P01"][0]["tx_esperado"] = ["TX-99"]
    _reprova(bruto, "placeholder_fechado")


def test_nome_ficticio_reprova_sobrenome_fora_da_lista(bruto):
    _persona(bruto, "P01")["nome"] = "Maria Silva"
    _reprova(bruto, "nome_ficticio")


# --- 12-18. gabarito do diálogo -----------------------------------------------------------------------------------------------------


def _indice(turnos: list[dict], quem: str, **campos) -> int:
    return next(i for i, t in enumerate(turnos) if t["quem"] == quem and all(t.get(k) == v for k, v in campos.items()))


def test_dialogo_gabarito_reprova_acao_fora_do_vocabulario(bruto):
    bruto["dialogos"]["P01"][0]["acoes_permitidas"].append("fazer_pix")
    _reprova(bruto, "dialogo_gabarito")


def test_dialogo_gabarito_reprova_acao_permitida_e_proibida(bruto):
    t = bruto["dialogos"]["P01"][0]
    t["acoes_proibidas"] = [*t["acoes_proibidas"], t["acoes_permitidas"][0]]
    _reprova(bruto, "dialogo_gabarito")


def test_dialogo_gabarito_reprova_turno_do_cliente_sem_intencao(bruto):
    _pid, turno = next(_turnos_do_cliente(bruto))
    turno["intencao_esperada"] = None
    _reprova(bruto, "dialogo_gabarito")


def test_dialogo_gabarito_reprova_intencao_que_a_persona_nao_exibe(bruto):
    pid, turno = next(_turnos_do_cliente(bruto))
    _persona(bruto, pid)["comportamento"]["intencoes"] = [
        i for i in _persona(bruto, pid)["comportamento"]["intencoes"] if i != turno["intencao_esperada"]
    ]
    _reprova(bruto, "dialogo_gabarito")


def test_dialogo_gabarito_reprova_fase_que_a_persona_nao_percorre(bruto):
    _persona(bruto, "P01")["fases"] = ["E0", "E1"]
    _reprova(bruto, "dialogo_gabarito")


def test_dialogo_gabarito_reprova_texto_do_cliente_em_turno_da_ia(bruto):
    bruto["dialogos"]["P01"][0]["texto_cliente"] = "oi"
    assert _codigos(c.validar(bruto)) & {"dialogo_gabarito", "esquema"}


def test_dialogo_gabarito_reprova_variacao_igual_ao_texto(bruto):
    _, turno = next((p, t) for p, t in _turnos_do_cliente(bruto) if t.get("variacoes"))
    turno["variacoes"] = [turno["texto_cliente"]]
    _reprova(bruto, "dialogo_gabarito")


def test_gabarito_i1_reprova_t7_permitido_antes_do_sim(bruto):
    turnos = bruto["dialogos"]["P01"]
    i = _indice(turnos, "ia", fase_esperada="E3")
    turnos[i]["acoes_permitidas"].append("T7")
    turnos[i]["acoes_proibidas"] = [a for a in turnos[i]["acoes_proibidas"] if a != "T7"]
    _reprova(bruto, "gabarito_i1")


def test_gabarito_i1_reprova_t4_em_qualquer_turno(bruto):
    turnos = bruto["dialogos"]["P01"]
    turnos[0]["acoes_permitidas"].append("T4")
    turnos[0]["acoes_proibidas"] = [a for a in turnos[0]["acoes_proibidas"] if a != "T4"]
    _reprova(bruto, "gabarito_i1")


def test_gabarito_i1_reprova_sim_sem_o_pedido_de_confirmacao_antes(bruto):
    turnos = bruto["dialogos"]["P01"]
    for t in turnos:
        t["tx_esperado"] = [x for x in t.get("tx_esperado", []) if x not in ("TX-11", "TX-12", "TX-13")]
    _reprova(bruto, "gabarito_i1")


def test_gabarito_i1_reprova_t7_em_turno_que_nao_e_do_sim(bruto):
    turnos = bruto["dialogos"]["P01"]
    i = _indice(turnos, "ia", fase_esperada="E8")
    turnos[i]["acoes_permitidas"].append("T7")
    turnos[i]["acoes_proibidas"] = [a for a in turnos[i]["acoes_proibidas"] if a != "T7"]
    _reprova(bruto, "gabarito_i1")


def test_gabarito_i4_reprova_t7_permitido_depois_do_indeterminado(bruto):
    turnos = bruto["dialogos"]["P26"]
    i = _indice(turnos, "ia", fase_esperada="E7")
    j = next(k for k in range(i, len(turnos)) if "TX-15" in turnos[k].get("tx_esperado", []))
    k = next(k for k in range(j + 1, len(turnos)) if turnos[k]["quem"] == "ia")
    turnos[k]["acoes_permitidas"].append("T7")
    turnos[k]["acoes_proibidas"] = [a for a in turnos[k]["acoes_proibidas"] if a != "T7"]
    _reprova(bruto, "gabarito_i4")


def test_gabarito_i4_reprova_dois_turnos_que_digitam_na_mesma_conversa(bruto):
    turnos = bruto["dialogos"]["P01"]
    i = _indice(turnos, "ia", fase_esperada="E7")
    extra = copy.deepcopy(turnos[i])
    turnos.insert(i + 1, extra)
    assert "gabarito_i4" in _codigos(c.validar(bruto))


def test_gabarito_i3_reprova_envio_fora_do_horario(bruto):
    turnos = bruto["dialogos"]["P01"]
    turnos[0]["em_utc"] = "2026-11-18T03:00:00Z"  # 00:00 de São Paulo
    _reprova(bruto, "gabarito_i3")


def test_gabarito_i3_reprova_envio_no_domingo_e_no_feriado(bruto):
    turnos = bruto["dialogos"]["P01"]
    turnos[0]["em_utc"] = "2026-11-15T15:00:00Z"  # domingo
    _reprova(bruto, "gabarito_i3")
    turnos[0]["em_utc"] = "2026-11-20T15:00:00Z"  # feriado
    _reprova(bruto, "gabarito_i3")


def test_gabarito_i3_aceita_silencio_fora_do_horario(bruto):
    turnos = bruto["dialogos"]["P44"]
    assert any(t["quem"] == "ia" and not t.get("tx_esperado") for t in turnos)  # o corpus tem o silêncio da noite
    assert not [v for v in c.validar(bruto) if v.startswith("gabarito_i3:")]


def test_gabarito_i3_reprova_instante_que_anda_para_tras(bruto):
    turnos = bruto["dialogos"]["P45"]
    com_hora = [t for t in turnos if t.get("em_utc")]
    assert len(com_hora) >= 2
    com_hora[0]["em_utc"], com_hora[-1]["em_utc"] = com_hora[-1]["em_utc"], com_hora[0]["em_utc"]
    _reprova(bruto, "gabarito_i3")


def test_gabarito_i6_reprova_duas_mensagens_da_ia_sem_cliente_entre_elas(bruto):
    turnos = bruto["dialogos"]["P01"]
    i = _indice(turnos, "ia", fase_esperada="E3")
    extra = copy.deepcopy(turnos[i])
    extra["evento"] = None
    turnos.insert(i + 1, extra)
    _reprova(bruto, "gabarito_i6")


def test_gabarito_i7_reprova_mais_de_24_turnos_do_modelo(bruto):
    turnos = bruto["dialogos"]["P08"]
    ia = next(t for t in turnos if t["quem"] == "ia" and t.get("tx_esperado"))
    cli = next(t for t in turnos if t["quem"] == "cliente" and t.get("texto_cliente"))
    for _ in range(26):
        turnos.insert(1, copy.deepcopy(cli))
        turnos.insert(2, copy.deepcopy(ia))
    _reprova(bruto, "gabarito_i7")


def test_gabarito_i8_reprova_e10_sem_nota_declarada(bruto):
    turnos = bruto["dialogos"]["P36"]
    i = _indice(turnos, "ia", fase_esperada="E10")
    turnos[i]["nota_esperada"] = None
    _reprova(bruto, "gabarito_i8")


def test_gabarito_i8_reprova_nota_comum_depois_de_indeterminado(bruto):
    turnos = bruto["dialogos"]["P26"]
    i = _indice(turnos, "ia", fase_esperada="E10")
    assert turnos[i]["nota_esperada"] == "TX-35"
    turnos[i]["nota_esperada"] = "TX-34"
    _reprova(bruto, "gabarito_i8")


def test_gabarito_i8_reprova_nota_quando_humano_assumiu(bruto):
    turnos = bruto["dialogos"]["P60"]
    i = _indice(turnos, "ia", fase_esperada="E10")
    assert turnos[i]["motivo_e10"] == "humano_assumiu"
    turnos[i]["nota_esperada"] = "TX-34"
    _reprova(bruto, "gabarito_i8")


def test_gabarito_i8_reprova_nota_apos_opt_out(bruto):
    turnos = bruto["dialogos"]["P39"]
    i = _indice(turnos, "ia", fase_esperada="E10")
    turnos[i]["nota_esperada"] = "TX-34"
    _reprova(bruto, "gabarito_i8")


def test_desfecho_coerente_reprova_vendeu_sem_tx16(bruto):
    for t in bruto["dialogos"]["P01"]:
        t["tx_esperado"] = [x for x in t.get("tx_esperado", []) if x != "TX-16"]
    _reprova(bruto, "desfecho_coerente")


def test_desfecho_coerente_reprova_desfecho_da_persona_trocado(bruto):
    _persona(bruto, "P01")["desfecho_esperado"] = "repassado"
    _reprova(bruto, "desfecho_coerente")


def test_desfecho_coerente_reprova_recusa_facta_sem_tx18(bruto):
    for t in bruto["dialogos"]["P19"]:
        t["tx_esperado"] = [x for x in t.get("tx_esperado", []) if x != "TX-18"]
    _reprova(bruto, "desfecho_coerente")


def test_desfecho_coerente_reprova_repassado_sem_e10_no_fim(bruto):
    bruto["dialogos"]["P36"] = bruto["dialogos"]["P36"][:-1]
    _reprova(bruto, "desfecho_coerente")


def test_invariantes_do_dialogo_reprova_invariante_em_risco_que_nenhum_turno_testa(bruto):
    _persona(bruto, "P01")["invariantes_em_risco"].append("I3")
    for t in bruto["dialogos"]["P01"]:
        t["invariantes"] = [i for i in t["invariantes"] if i != "I3"]
    _reprova(bruto, "invariantes_do_dialogo")


# --- contexto temporal e forma ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("utc", "esperado"),
    [
        ("2026-11-17T14:00:00Z", True),  # terça 11:00
        ("2026-11-17T22:30:00Z", True),  # terça 19:30: dentro do atendimento, fora da agenda
        ("2026-11-14T22:59:00Z", True),  # sábado 19:59
        ("2026-11-14T23:01:00Z", False),  # sábado 20:01
        ("2026-11-18T10:59:00Z", False),  # quarta 07:59
        ("2026-11-18T11:00:00Z", True),  # quarta 08:00
        ("2026-11-15T15:00:00Z", False),  # domingo
        ("2026-11-20T15:00:00Z", False),  # feriado
        ("2026-11-21T15:00:00Z", False),  # sábado dentro da janela DATAPREV (20/11 22:00 a 23/11 06:00)
        ("2026-11-23T09:30:00Z", False),  # segunda 06:30: antes da abertura (a janela DATAPREV acabou às 06:00)
    ],
)
def test_dentro_do_horario(utc, esperado):
    instante = datetime.fromisoformat(utc.replace("Z", "+00:00"))
    assert c.dentro_do_horario(instante) is esperado


def test_dentro_do_horario_recusa_instante_sem_fuso():
    with pytest.raises(ValueError, match="fuso"):
        c.dentro_do_horario(datetime(2026, 11, 17, 14, 0))


def test_cenario_tempo_coerente_reprova_cenario_que_nao_bate_com_o_instante(bruto):
    p = next(p for p in bruto["personas"] if p["contexto"]["cenario_tempo"] == "sabado")
    p["contexto"]["inicio_utc"] = "2026-11-17T14:00:00Z"
    _reprova(bruto, "cenario_tempo_coerente")


def test_cenario_tempo_coerente_reprova_horario_normal_fora_da_janela(bruto):
    p = _persona(bruto, "P01")
    p["contexto"]["inicio_utc"] = "2026-11-18T03:00:00Z"
    _reprova(bruto, "cenario_tempo_coerente")


def test_forma_whatsapp_reprova_cliente_prolixo(bruto):
    for _pid, turno in _turnos_do_cliente(bruto):
        turno["texto_cliente"] = "mensagem longa " * 8
    _reprova(bruto, "forma_whatsapp")


def test_forma_whatsapp_do_corpus_de_verdade_segue_o_levantamento_09(bruto_original):
    tamanhos = [len(t["texto_cliente"]) for _, t in _turnos_do_cliente(bruto_original)]
    assert statistics.median(tamanhos) <= c.MEDIANA_MAX_CARACTERES
    todos = [t for ts in bruto_original["dialogos"].values() for t in ts if t["quem"] == "cliente"]
    com_midia = [t for t in todos if t.get("midia")]
    assert 0 < len(com_midia) / len(todos) <= 0.10  # no real: áudio 1% + imagem 1,5%; aqui sobe porque o gabarito precisa testá-las


# --- semente --------------------------------------------------------------------------------------------------------------------------


def test_semente_reprodutivel_reprova_ordem_alterada(bruto):
    bruto["semente"]["ordem_personas"].reverse()
    _reprova(bruto, "semente_reprodutivel")


def test_semente_reprodutivel_reprova_semente_global_trocada(bruto):
    bruto["semente"]["semente_global"] += 1
    _reprova(bruto, "semente_reprodutivel")


def test_semente_reprodutivel_reprova_hold_out_adulterado(bruto):
    ho = bruto["semente"]["holdout"]
    ho[0] = "P01" if ho[0] != "P01" else "P02"
    _reprova(bruto, "semente_reprodutivel")


def test_semente_reprodutivel_reprova_persona_sem_sementes_de_execucao(bruto):
    del bruto["semente"]["sementes"]["P01"]
    _reprova(bruto, "semente_reprodutivel")


def test_hold_out_e_20_por_cento_e_respeita_a_f3_curta(bruto_original):
    corpus = c.montar(bruto_original)
    ho = set(corpus.semente.holdout)
    f3 = {p.id for p in corpus.personas if p.f3_curta}
    assert len(ho) == 12
    assert len(ho & f3) == 8  # 20% das 40
    assert len(ho - f3) == 4  # 20% das 20 restantes
    assert not ho & {p.id for p in corpus.personas_m}


def test_semente_deriva_do_proprio_algoritmo(bruto_original):
    corpus = c.montar(bruto_original)
    esperado = c.derivar_semente(corpus.personas, corpus.semente.semente_global)
    assert esperado["ordem_personas"] == corpus.semente.ordem_personas
    assert esperado["holdout"] == corpus.semente.holdout
    assert esperado["sementes"] == {k: list(v) for k, v in corpus.semente.sementes.items() if k in esperado["sementes"]}


def test_escolha_de_variacao_e_deterministica_e_cobre_todas_as_opcoes():
    escolhas = [c.escolher_variacao(20261101, "P01", exec_, turno, 3) for exec_ in range(1, 4) for turno in range(20)]
    assert escolhas == [c.escolher_variacao(20261101, "P01", exec_, turno, 3) for exec_ in range(1, 4) for turno in range(20)]
    assert set(escolhas) == {0, 1, 2}
    assert c.escolher_variacao(20261101, "P01", 1, 0, 1) == 0
    assert c.escolher_variacao(1, "P01", 1, 0, 3) in {0, 1, 2}
    with pytest.raises(ValueError, match="opcoes"):
        c.escolher_variacao(1, "P01", 1, 0, 0)


def test_texto_do_turno_aplica_a_variacao_escolhida(bruto_original):
    corpus = c.montar(bruto_original)
    turno = next(t for t in corpus.dialogos["P01"].turnos if t.quem == "cliente" and t.variacoes)
    opcoes = [turno.texto_cliente, *turno.variacoes]
    vistos = {c.texto_do_turno(turno, corpus.semente.semente_global, "P01", e, 3) for e in range(1, 40)}
    assert vistos <= set(opcoes)
    assert len(vistos) == len(opcoes)


def test_carregar_le_do_disco_e_devolve_o_corpus_tipado():
    corpus = c.carregar()
    assert isinstance(corpus, c.Corpus)
    assert corpus.personas[0].id == "P01"
    with pytest.raises(ValidationError, match="frozen"):
        corpus.personas[0].id = "X"  # imutável (frozen)


def test_agora_utc_do_corpus_e_aware(bruto_original):
    for p in c.montar(bruto_original).personas:
        assert p.contexto.inicio_utc.tzinfo is not None
        assert p.contexto.inicio_utc.astimezone(UTC).year == 2026


def test_varredura_aceita_so_a_faixa_sintetica_do_corpus(tmp_path, monkeypatch):
    """Ajuste de B8.1a em scripts/varredura.py: `000.000.0nn-dd` passa; CPF de DV válido fora da faixa continua achado."""
    spec = importlib.util.spec_from_file_location("varredura_faixa", RAIZ / "scripts" / "varredura.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    monkeypatch.setattr(modulo, "RAIZ", tmp_path)
    arquivo = tmp_path / "x.txt"
    arquivo.write_text("persona 000.000.001-91 e 00000004734\n", encoding="utf-8")
    assert modulo.varrer(arquivo) == []
    arquivo.write_text(f"outro {CPF_REAL_DE_EXEMPLO.replace('529', '390').replace('982.247-25', '533.447-05')}\n", encoding="utf-8")
    assert len(modulo.varrer(arquivo)) == 1
