"""Corpus da F3, revisão 1 (30/10): regras novas e ramos de erro. Mesmo método de `test_corpus.py`: muta o bruto em memória e espera o código da regra."""

from __future__ import annotations

import copy
import re

import pytest

from ia_atendimento import corpus as c
from ia_atendimento.corpus.regras import semente as regras_semente
from ia_atendimento.corpus.regras._comum import e_sim_literal, e_texto_sim
from tests.test_corpus import CORPUS_DIR, _codigos, _persona, _reprova

SEM_VIOLACAO = "não devia reprovar"


@pytest.fixture(scope="module")
def bruto_original() -> dict:
    return c.carregar_bruto(CORPUS_DIR)


@pytest.fixture
def bruto(bruto_original: dict) -> dict:
    return copy.deepcopy(bruto_original)


def _turnos(bruto: dict, pid: str, **campos) -> list[tuple[int, dict]]:
    return [(i, t) for i, t in enumerate(bruto["dialogos"][pid]) if all(t.get(k) == v for k, v in campos.items())]


def _primeiro(bruto: dict, pid: str, **campos) -> dict:
    return _turnos(bruto, pid, **campos)[0][1]


def _sem(bruto: dict, codigo: str) -> None:
    assert not [v for v in c.validar(bruto) if v.startswith(codigo + ":")], SEM_VIOLACAO


# --- A1 · a E5 colhe os 4 campos de H §2.3 -------------------------------------------------------------------------------------------------


def test_e5_completa_todos_os_dialogos_que_chegam_ao_tx11_colhem_recebimento_cep_numero_e_celular(bruto_original):
    corpus = c.montar(bruto_original)
    chegam = [pid for pid, d in corpus.dialogos.items() if any("TX-11" in t.tx_esperado for t in d.turnos)]
    assert len(chegam) >= 25
    for pid in chegam:
        campos = {t.campo_alvo for t in corpus.dialogos[pid].turnos if t.quem == "cliente" and t.campo_alvo}
        assert {"cep", "numero_endereco", "celular"} <= campos, pid
        assert campos & {"pix", "conta"}, pid


@pytest.mark.parametrize("campo", ["cep", "numero_endereco", "celular", "pix"])
def test_e5_completa_reprova_dialogo_que_pula_um_campo(bruto, campo):
    turnos = bruto["dialogos"]["P01"]
    bruto["dialogos"]["P01"] = [t for t in turnos if t.get("campo_alvo") != campo]
    achadas = _reprova(bruto, "e5_completa")
    assert any(campo in a or "recebimento" in a for a in achadas)


def test_e5_completa_aceita_campo_que_o_360_ja_tem(bruto):
    bruto["dialogos"]["P01"] = [t for t in bruto["dialogos"]["P01"] if t.get("campo_alvo") != "cep"]
    _persona(bruto, "P01")["perfil"]["campos_no_360"] = ["cep"]
    _sem(bruto, "e5_completa")


def test_e5_completa_conta_basta_como_recebimento(bruto):
    assert any(t.get("campo_alvo") == "conta" for t in bruto["dialogos"]["P03"])
    _sem(bruto, "e5_completa")


# --- A2 · janela de 24 h do WhatsApp --------------------------------------------------------------------------------------------------------


def test_janela24h_reprova_texto_livre_36_h_depois_do_cliente(bruto):
    final = _primeiro(bruto, "P45", fase_esperada="E10")
    final["tx_esperado"] = ["TX-26"]  # segunda 08:00 é 36 h depois do «pode ser» de sábado 20:01
    final["acoes_proibidas"] = [a for a in final["acoes_proibidas"] if a != "enviar"]
    achadas = _reprova(bruto, "gabarito_janela24h")
    assert any("36 h" in a for a in achadas)


def test_janela24h_reprova_texto_livre_do_modelo_depois_de_24_h(bruto):
    final = _primeiro(bruto, "P46", fase_esperada="E10")
    final["texto_livre_ia"] = True
    _reprova(bruto, "gabarito_janela24h")


def test_janela24h_aceita_o_template_tx24_e_o_que_cabe_nas_24_h(bruto):
    final = _primeiro(bruto, "P45", fase_esperada="E10")
    final["tx_esperado"] = ["TX-24"]
    _sem(bruto, "gabarito_janela24h")
    _sem(bruto | {"dialogos": {**bruto["dialogos"]}}, "gabarito_janela24h")


def test_p45_e_p46_encerram_sem_mensagem_porque_ja_passou_de_24_h(bruto_original):
    corpus = c.montar(bruto_original)
    for pid, motivo in (("P45", "janela_24h_vencida"), ("P46", "janela_24h_vencida")):
        finais = [t for t in corpus.dialogos[pid].turnos if t.quem == "ia" and t.fase_esperada == "E10"]
        assert len(finais) == 1
        assert not finais[0].tx_esperado
        assert not finais[0].texto_livre_ia
        assert finais[0].motivo_e10 == motivo
    assert {p.id: p.desfecho_esperado for p in corpus.personas if p.id in ("P45", "P46")} == {"P45": "repassado", "P46": "repassado"}


# --- A3 · «sem FACTA» não digita --------------------------------------------------------------------------------------------------------------


def test_t7_so_com_oferta_facta_reprova_persona_sem_stub_que_digita(bruto):
    p = _persona(bruto, "P44")
    p["cenario_facta"].update(persona_duble=None, sem_chamada_facta=True, cenario="sem_facta")
    achadas = _reprova(bruto, "t7_so_com_oferta_facta")
    assert any("P44" in a for a in achadas)


def test_t7_so_com_oferta_facta_reprova_persona_sem_dialogo_que_chega_ao_e7(bruto):
    p = _persona(bruto, "P34")
    assert "E7" in p["fases"]
    p["cenario_facta"].update(persona_duble=None, sem_chamada_facta=True, cenario="sem_facta")
    _reprova(bruto, "t7_so_com_oferta_facta")


def test_t7_so_com_oferta_facta_reprova_oferta_inativa(bruto):
    perfil = _persona(bruto, "P01")["perfil"]
    perfil.update(oferta_facta_ativa=False, valor_pre_aprovado_brl=None, prazo_oferta_x=None)
    _reprova(bruto, "t7_so_com_oferta_facta")


def test_nenhuma_persona_sem_facta_chega_ao_e7(bruto_original):
    corpus = c.montar(bruto_original)
    for p in corpus.todas():
        if p.cenario_facta.sem_chamada_facta:
            assert not {"E7", "E8"} & set(p.fases), p.id


def test_duble_snapshot_e_o_da_main_do_bancos_duble_e_as_oito_personas_usam_persona_que_existe(bruto_original):
    duble = bruto_original["duble"]
    assert re.search(r"sha256 [0-9a-f]{12}\b", duble["fonte"]), "a fonte leva o sha256 do personas.yaml do dublê, não um commit (R2-08)"
    assert "AJUSTE" not in duble["fonte"]  # o corpus se amarra ao dublê, não o contrário
    existentes = {d["id"] for d in duble["personas"]}
    corpus = c.montar(bruto_original)
    for pid in ("P14", "P34", "P44", "P48", "P52", "P56", "P57", "P58"):
        persona = next(p for p in corpus.personas if p.id == pid)
        assert persona.cenario_facta.persona_duble in existentes
        assert persona.cenario_facta.cenario == "aprovado"


def test_cpf_alinhado_reprova_persona_fora_do_f3_do_duble_que_nao_e_caminho_feliz(bruto):
    p = _persona(bruto, "P14")
    assert p["cenario_facta"]["persona_duble"].startswith("aprovado")
    for d in bruto["duble"]["personas"]:  # o dublê não lista a P14 em nenhum `f3` (hoje ela tem clone próprio; antes ia pelo `aprovado-NN`)
        d["f3"] = [x for x in d["f3"] if x != "P14"]
    p["cenario_facta"].update(persona_duble="recusa-sem-margem", cenario="recusa")
    p["cpf"] = "000.000.014-06"
    achadas = _reprova(bruto, "cpf_alinhado_duble")
    assert any("caminho feliz" in a for a in achadas)


def test_cpf_dos_sem_stub_fica_na_faixa_reservada_e_nao_colide_com_o_duble(bruto_original, bruto):
    corpus = c.montar(bruto_original)
    sem_stub = [p for p in corpus.todas() if p.cenario_facta.persona_duble is None]
    assert len(sem_stub) == 24
    assert all(75 <= int(p.cpf[9:11]) <= 98 for p in sem_stub)
    _persona(bruto, "P13")["cpf"] = "000.000.047-74"  # o CPF de indet-tentativa-antiga (n=47), criada no dublê depois do 1º instantâneo
    achadas = _reprova(bruto, "cpf_alinhado_duble")
    assert any("usa CPF de uma delas" in a for a in achadas)
    assert any("faixa reservada" in a for a in achadas)


# --- A4/R2-1 · o SIM vale pelo texto, isolado e explícito ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("sim", True),
        ("SIM", True),
        ("sim!", True),
        ("Sim.", True),
        ("ss", True),
        ("SS", True),
        ("pode", True),
        ("pode enviar", True),
        ("Pode enviar!", True),
        ("confirmo", True),
        ("isso", True),
        ("aceito", True),
        ("sim, pode", True),
        ("pode sim", True),
        ("quero sim", True),
        ("sím", True),
        ("sim  pode", True),
        ("sim?", False),
        ("sim 👍", False),
        ("sim, mas e se mudar?", False),
        ("sim mas e se o valor mudar?", False),
        ("claro", False),
        ("ok", False),
        ("bora", False),
        ("pode ser", False),
        ("acho que sim", False),
        ("quero", False),
        ("pode mandar", False),
        ("sim pode enviar", False),
        ("sim confirmo", False),
        ("nao", False),
        ("", False),
        ("sim sim", False),
        ("  ", False),
    ],
)
def test_e_texto_sim_e_regra_fechada(texto, esperado):
    assert e_texto_sim(texto) is esperado


def test_e_sim_literal_exige_o_texto_e_todas_as_variacoes():
    base = {
        "quem": "cliente",
        "fase_esperada": "E6",
        "intencao_esperada": "aceita",
        "acoes_permitidas": ("responder",),
        "acoes_proibidas": ("T4",),
    }
    assert e_sim_literal(c.Turno(texto_cliente="sim", variacoes=("ss", "pode"), **base))
    assert not e_sim_literal(c.Turno(texto_cliente="sim", variacoes=("ss", "sim?"), **base))
    assert not e_sim_literal(
        c.Turno(quem="cliente", fase_esperada="E6", midia="audio", acoes_permitidas=("responder",), acoes_proibidas=("T4",))
    )


def test_sim_do_corpus_so_usa_a_lista_estreita(bruto_original):
    corpus = c.montar(bruto_original)
    vistos = 0
    for pid, d in corpus.dialogos.items():
        for i, t in enumerate(d.turnos):
            if t.quem == "cliente" and t.fase_esperada == "E6" and t.intencao_esperada == "aceita":
                proxima = next(x for x in d.turnos[i + 1 :] if x.quem == "ia")
                assert e_sim_literal(t) or "TX-36" in proxima.tx_esperado, (pid, t.texto_cliente)
                vistos += 1
    assert vistos >= 25


def test_i1_nao_aceita_sim_com_interrogacao_nem_sim_mas(bruto):
    """Sonda da re-revisão: «quero» com variação «sim?» num SIM seguido de T7 reprova."""
    t = _primeiro(bruto, "P01", quem="cliente", fase_esperada="E6")
    t["texto_cliente"], t["variacoes"] = "quero", ["sim?"]
    achadas = _reprova(bruto, "gabarito_i1")
    assert any("T7 permitido sem pedido" in a for a in achadas)


def test_i1_valida_o_texto_e_nao_o_rotulo(bruto):
    """O texto «sim mas e se o valor mudar?» rotulado `aceita` não confirma nada: o T7 que vem depois reprova."""
    t = _primeiro(bruto, "P01", quem="cliente", fase_esperada="E6")
    t["texto_cliente"], t["variacoes"] = "sim mas e se o valor mudar?", []
    achadas = _reprova(bruto, "gabarito_i1")
    assert any("T7 permitido sem pedido de confirmação" in a for a in achadas)
    _reprova(bruto, "gabarito_tx36")


def test_sim_literal_reprova_texto_de_sim_com_outro_rotulo(bruto):
    t = _primeiro(bruto, "P01", quem="cliente", fase_esperada="E6")
    t["intencao_esperada"] = "duvida_oferta"
    _reprova(bruto, "gabarito_sim_literal")


# --- R2-2 · o negativo do SIM tem diálogo: TX-36, «não» e TX-12 -------------------------------------------------------------------------------------


def test_pelo_menos_quatro_personas_da_f3_curta_tem_resposta_ambigua_no_e6_com_tx36_e_uma_no_hold_out(bruto_original):
    corpus = c.montar(bruto_original)
    com_tx36 = {pid for pid, d in corpus.dialogos.items() if not pid.startswith("P-M") and any("TX-36" in t.tx_esperado for t in d.turnos)}
    assert len(com_tx36) >= 4
    assert com_tx36 & set(corpus.semente.holdout)
    textos = {t.texto_cliente for pid in com_tx36 for t in corpus.dialogos[pid].turnos if t.quem == "cliente" and t.fase_esperada == "E6"}
    assert {"sim, mas e se o valor mudar?", "bora", "acho que sim"} <= textos


def test_um_codigo_que_aceita_sim_mas_como_sim_reprova(bruto):
    """O gabarito que deixa o T7 vir logo depois de «sim, mas...» (sem TX-36 no meio) reprova."""
    turnos = bruto["dialogos"]["P02"]
    i = next(i for i, t in enumerate(turnos) if t["quem"] == "ia" and "TX-36" in t.get("tx_esperado", []))
    del turnos[i : i + 2]  # tira o TX-36 e o SIM que vinha depois: do «sim, mas...» direto para o T7
    achadas = c.validar(bruto)
    assert any(a.startswith("gabarito_tx36:") for a in achadas)
    assert any(a.startswith("gabarito_i1:") for a in achadas)


def test_tx36_reprova_resposta_ambigua_sem_tx36_e_com_t7(bruto):
    turnos = bruto["dialogos"]["P04"]
    i = next(i for i, t in enumerate(turnos) if t["quem"] == "ia" and "TX-36" in t.get("tx_esperado", []))
    turnos[i]["tx_esperado"] = ["TX-11"]
    _reprova(bruto, "gabarito_tx36")
    b2 = c.carregar_bruto(CORPUS_DIR)
    t2 = b2["dialogos"]["P04"][i]
    t2["acoes_permitidas"] = [*t2["acoes_permitidas"], "T7"]
    t2["acoes_proibidas"] = [a for a in t2["acoes_proibidas"] if a != "T7"]
    _reprova(b2, "gabarito_tx36")


def test_cobertura_dialogos_exige_tx36_e_tx12(bruto):
    for d in bruto["dialogos"].values():
        for t in d:
            t["tx_esperado"] = [x for x in t.get("tx_esperado", []) if x not in ("TX-36", "TX-12")]
    achadas = _reprova(bruto, "cobertura_dialogos")
    assert any("TX-36" in a for a in achadas) and any("TX-12" in a for a in achadas)


def test_nao_no_e6_volta_para_a_e4_e_a_nova_opcao_pede_nova_confirmacao(bruto_original):
    corpus = c.montar(bruto_original)
    turnos = corpus.dialogos["P20"].turnos
    i = next(i for i, t in enumerate(turnos) if t.quem == "cliente" and t.fase_esperada == "E6" and t.texto_cliente.startswith("nao"))
    assert turnos[i + 1].fase_esperada == "E4"
    assert "TX-11" in next(t for t in turnos[i + 2 :] if t.quem == "ia" and t.fase_esperada == "E6").tx_esperado


def test_tx12_depois_do_sim_invalida_a_confirmacao_e_exige_outro_sim(bruto):
    turnos = bruto["dialogos"]["P25"]
    i = next(i for i, t in enumerate(turnos) if t["quem"] == "ia" and "TX-12" in t.get("tx_esperado", []))
    assert turnos[i]["evento"] == "precondicao_falhou_valores_mudaram"
    del turnos[i + 1]  # tira o segundo SIM
    _reprova(bruto, "gabarito_i1")


def test_i1_nao_aceita_sim_depois_de_o_cliente_mudar_o_pedido(bruto):
    """P58: depois de «nao, espera, 36x» o SIM antigo não vale; sem novo TX-11 o T7 reprova."""
    turnos = bruto["dialogos"]["P58"]
    i = next(i for i, t in enumerate(turnos) if t["quem"] == "ia" and t["fase_esperada"] == "E6" and i > 12)
    del turnos[i]  # tira o segundo TX-11
    _reprova(bruto, "gabarito_i1")


# --- A5 · recusa firme repassa com nota (Q5) --------------------------------------------------------------------------------------------


def test_p41_e_repassado_e_o_desfecho_deriva_do_motivo(bruto):
    assert _persona(bruto, "P41")["desfecho_esperado"] == "repassado"
    _persona(bruto, "P41")["desfecho_esperado"] = "encerrado_sem_interesse"
    _reprova(bruto, "desfecho_coerente")


def test_p49_manda_tx31_e_nao_tx36_para_a_manipulacao(bruto_original):
    corpus = c.montar(bruto_original)
    tx = [x for t in corpus.dialogos["P49"].turnos for x in t.tx_esperado]
    assert "TX-31" in tx
    assert "TX-36" not in tx


def test_desfecho_ja_concluiu_e_vendeu_e_exige_a_nota_nt07(bruto):
    t = _primeiro(bruto, "P-M09", fase_esperada="E10")
    assert t["nota_esperada"] == "NT-07"
    t["nota_esperada"] = "nenhuma"
    _reprova(bruto, "gabarito_i8")


# --- A6 · hold-out independente ----------------------------------------------------------------------------------------------------------


def test_holdout_independente_reprova_hold_out_clonado(bruto):
    ho = next(pid for pid in bruto["semente"]["holdout"] if pid in bruto["dialogos"] and not pid.startswith("P-M"))
    outro = next(pid for pid in bruto["dialogos"] if pid not in bruto["semente"]["holdout"] and not pid.startswith("P-M"))
    bruto["dialogos"][outro] = copy.deepcopy(bruto["dialogos"][ho])
    achadas = _reprova(bruto, "holdout_independente")
    assert any(ho in a for a in achadas)


def test_holdout_independente_reprova_persona_do_duble_dividida_com_o_desenvolvimento(bruto):
    corpus = c.montar(bruto)
    alvo = next(
        p
        for p in corpus.personas
        if p.id in corpus.semente.holdout and p.cenario_facta.persona_duble and p.cenario_facta.cenario != "aprovado"
    )
    dev = next(p for p in corpus.personas if p.id not in corpus.semente.holdout and p.cenario_facta.persona_duble)
    _persona(bruto, dev.id)["cenario_facta"]["persona_duble"] = alvo.cenario_facta.persona_duble
    achadas = _reprova(bruto, "holdout_independente")
    assert any(alvo.id in a and "dublê" in a for a in achadas)


def test_holdout_do_corpus_nao_tem_esqueleto_repetido(bruto_original):
    corpus = c.montar(bruto_original)
    esqueletos = [regras_semente.esqueleto(d) for d in corpus.dialogos.values()]
    for pid in corpus.semente.holdout:
        if pid in corpus.dialogos:
            assert esqueletos.count(regras_semente.esqueleto(corpus.dialogos[pid])) == 1, pid


# --- A8 · as P-M críticas têm diálogo -------------------------------------------------------------------------------------------------


def test_f3_com_dialogo_exige_dialogo_da_p_m_critica(bruto):
    del bruto["dialogos"]["P-M01"]
    achadas = _reprova(bruto, "f3_com_dialogo")
    assert any("P-M01" in a for a in achadas)


def test_f3_com_dialogo_recusa_dialogo_de_p_m_nao_critica(bruto):
    bruto["dialogos"]["P-M07"] = copy.deepcopy(bruto["dialogos"]["P-M02"])
    _reprova(bruto, "f3_com_dialogo")


def test_dialogo_do_caso_b_pode_abrir_pelo_post_do_cliente_e_os_demais_nao(bruto):
    assert bruto["dialogos"]["P-M15"][0]["quem"] == "cliente"
    _sem(bruto, "f3_com_dialogo")
    bruto["dialogos"]["P-M02"] = bruto["dialogos"]["P-M02"][1:]
    _reprova(bruto, "f3_com_dialogo")


# --- A9 · o que passava e devia reprovar --------------------------------------------------------------------------------------------------


def test_acoes_por_fase_reprova_t6_na_e3_e_t5_na_e5(bruto):
    t = _primeiro(bruto, "P01", quem="ia", fase_esperada="E3")
    t["acoes_permitidas"].append("T6")
    t["acoes_proibidas"] = [a for a in t["acoes_proibidas"] if a != "T6"]
    _reprova(bruto, "gabarito_acoes_por_fase")
    bruto2 = copy.deepcopy(bruto)
    bruto2["dialogos"]["P01"] = copy.deepcopy(bruto["dialogos"]["P01"])
    t2 = _primeiro(bruto2, "P01", fase_esperada="E3")
    t2["acoes_permitidas"].remove("T6")
    _sem(bruto2, "gabarito_acoes_por_fase")
    e5 = next(t for t in bruto2["dialogos"]["P01"] if t["quem"] == "ia" and t["fase_esperada"] == "E5")
    e5["acoes_permitidas"].append("T5")
    _reprova(bruto2, "gabarito_acoes_por_fase")


def test_fase_tx_reprova_link_na_abertura_e_tx_na_fase_errada(bruto):
    bruto["dialogos"]["P01"][0]["tx_esperado"] = ["TX-16"]
    achadas = _reprova(bruto, "gabarito_fase_tx")
    assert any("TX-16" in a and "E1" in a for a in achadas)


def test_tx_composto_reprova_tres_tx_numa_mensagem(bruto):
    t = _primeiro(bruto, "P01", quem="ia", fase_esperada="E3")
    t["tx_esperado"] = ["TX-03", "TX-05", "TX-11"]
    _reprova(bruto, "gabarito_tx_composto")


def test_tx_composto_aceita_os_compostos_da_lista_e_reprova_texto_livre_com_dois_tx(bruto):
    t = _primeiro(bruto, "P44", fase_esperada="E3", evento="janela_abriu_08h")
    assert t["tx_esperado"] == ["TX-02", "TX-03"]
    _sem(bruto, "gabarito_tx_composto")
    t["texto_livre_ia"] = True
    _reprova(bruto, "gabarito_tx_composto")


def test_transicoes_reprova_pulo_de_fase(bruto):
    t = _primeiro(bruto, "P01", quem="ia", fase_esperada="E3")
    t["fase_esperada"] = "E8"
    achadas = _reprova(bruto, "gabarito_transicoes")
    assert any("E1 → E8" in a for a in achadas)


def test_transicoes_reprova_cliente_em_fase_diferente_da_que_a_ia_parou(bruto):
    t = _primeiro(bruto, "P01", quem="cliente", fase_esperada="E3")
    t["fase_esperada"] = "E4"
    achadas = _reprova(bruto, "gabarito_transicoes")
    assert any("o cliente chega em E4" in a for a in achadas)


def test_silencio_reprova_ia_muda_em_horario(bruto):
    """Tirar o TX-03 deixa um silêncio sem motivo no meio do horário comercial."""
    t = _primeiro(bruto, "P01", quem="ia", fase_esperada="E3")
    t["tx_esperado"] = []
    t["acoes_proibidas"] = [*t["acoes_proibidas"], "enviar"]
    achadas = _reprova(bruto, "gabarito_silencio")
    assert any("sem motivo" in a for a in achadas)


def test_silencio_reprova_silencio_sem_enviar_proibido_e_mensagem_com_enviar_proibido(bruto):
    ((_, mudo),) = [(i, t) for i, t in _turnos(bruto, "P44", fase_esperada="E1") if t["quem"] == "ia" and not t["tx_esperado"]]
    mudo["acoes_proibidas"] = [a for a in mudo["acoes_proibidas"] if a != "enviar"]
    _reprova(bruto, "gabarito_silencio")
    bruto["dialogos"]["P01"][0]["acoes_proibidas"].append("enviar")
    achadas = _reprova(bruto, "gabarito_silencio")
    assert any("`enviar` proibido" in a for a in achadas)


def test_silencio_aceita_silencio_com_evento_e0_pos_e10_e_fora_do_horario(bruto):
    _sem(bruto, "gabarito_silencio")
    for pid in ("P54", "P23", "P44", "P60"):  # E0, pós-E10, noite, evento
        assert any(t["quem"] == "ia" and not t["tx_esperado"] for t in bruto["dialogos"][pid])


def test_evento_e_vocabulario_fechado(bruto):
    t = _primeiro(bruto, "P24", fase_esperada="E8")
    t["evento"] = "qualquer_coisa"
    assert "esquema" in _codigos(c.validar(bruto))


def test_seguranca_reprova_mensagem_que_nao_proibe_eco_valor_e_promessa(bruto):
    for token in c.ACOES_DE_SEGURANCA:
        b = copy.deepcopy(bruto)
        b["dialogos"]["P01"][0]["acoes_proibidas"].remove(token)
        achadas = _reprova(b, "gabarito_seguranca")
        assert any(token in a for a in achadas)


def test_texto_livre_do_modelo_e_exercitado_e_proibe_valor_e_promessa(bruto_original):
    corpus = c.montar(bruto_original)
    livres = [t for d in corpus.dialogos.values() for t in d.turnos if t.texto_livre_ia]
    assert len(livres) >= 4
    assert all(set(c.ACOES_DE_SEGURANCA) <= set(t.acoes_proibidas) for t in livres)


def test_cobertura_dialogos_reprova_intencao_sem_turno(bruto):
    for d in bruto["dialogos"].values():
        for t in d:
            if t.get("intencao_esperada") == "quer_pensar":
                t["intencao_esperada"] = "aceita"
    for p in bruto["personas"] + bruto["personas_m"]:
        p["comportamento"]["intencoes"] = [*p["comportamento"]["intencoes"]]
    achadas = _reprova(bruto, "cobertura_dialogos")
    assert any("quer_pensar" in a for a in achadas)


def test_cobertura_dialogos_reprova_objecao_fase_cenario_e_texto_livre_sem_turno(bruto):
    for d in bruto["dialogos"].values():
        for t in d:
            if t.get("objecao_esperada") == "taxa_juros":
                t["objecao_esperada"] = None
            t["texto_livre_ia"] = False
    achadas = _reprova(bruto, "cobertura_dialogos")
    assert any("taxa_juros" in a for a in achadas)
    assert any("texto_livre_ia" in a for a in achadas)


def test_cobertura_dialogos_reprova_cenario_de_tempo_so_em_persona_sem_dialogo(bruto):
    _persona(bruto, "P-M19")["contexto"]["cenario_tempo"] = "horario_normal"
    _persona(bruto, "P-M19")["contexto"]["instante_chave_utc"] = _persona(bruto, "P-M19")["contexto"]["inicio_utc"]
    _persona(bruto, "P-M19")["contexto"]["inicio_utc"] = "2026-11-14T14:00:00Z"
    achadas = _reprova(bruto, "cobertura_dialogos")
    assert any("domingo" in a for a in achadas) or any("cenário de tempo" in a for a in achadas)


def test_cobertura_dialogos_reprova_fase_sem_turno(bruto):
    for d in bruto["dialogos"].values():
        d[:] = [t for t in d if t["fase_esperada"] != "E9"]
    achadas = _reprova(bruto, "cobertura_dialogos")
    assert any("fase E9" in a for a in achadas)


def test_variedade_das_falas_reprova_corpus_repetitivo(bruto):
    for _pid, t in ((p, t) for p, ts in bruto["dialogos"].items() for t in ts if t.get("texto_cliente")):
        t["texto_cliente"] = "oi"
        t["variacoes"] = []
    _reprova(bruto, "variedade_das_falas")


def test_variedade_das_falas_do_corpus_chega_a_120_textos_distintos_em_160(bruto_original):
    textos = [t["texto_cliente"] for ts in bruto_original["dialogos"].values() for t in ts if t.get("texto_cliente")]
    assert len(set(textos)) / len(textos) >= 0.75
    f3 = [
        t["texto_cliente"]
        for pid, ts in bruto_original["dialogos"].items()
        if not pid.startswith("P-M")
        for t in ts
        if t.get("texto_cliente")
    ]
    assert len(set(f3)) >= 120
