"""Corpus da F3, revisão 1 (30/10), parte 2: PII em qualquer campo, esquema estrito, ramos de erro do gabarito, agenda, calendário e semente. Mesmo método de `test_corpus.py`: muta o bruto em memória e espera o código da regra."""

from __future__ import annotations

import copy
from datetime import UTC, datetime

import pytest

from ia_atendimento import corpus as c
from ia_atendimento.corpus import calendario, pii, semente
from tests.test_corpus import CORPUS_DIR, CPF_REAL_DE_EXEMPLO, _codigos, _persona, _reprova

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


# --- PII em qualquer campo, esquema estrito, KeyError ------------------------------------------------------------------------------------


def test_pii_texto_pega_cpf_real_no_snapshot_do_duble(bruto):
    bruto["duble"]["personas"][0]["cenario"] = f"cliente {CPF_REAL_DE_EXEMPLO}"
    achadas = _reprova(bruto, "pii_texto")
    assert any("duble" in a for a in achadas)


def test_pii_texto_pega_e_mail_real_nas_regras_da_semente(bruto):
    bruto["semente"]["regras"]["chave"] = "fale com fulano" + "@empresa" + ".com.br"
    achadas = _reprova(bruto, "pii_texto")
    assert any("semente.regras" in a for a in achadas)


def test_pii_texto_pega_cpf_em_tx_esperado_e_em_campos_da_ia(bruto):
    bruto["dialogos"]["P01"][0]["tx_esperado"] = [f"TX-01 {CPF_REAL_DE_EXEMPLO}"]
    achadas = _reprova(bruto, "pii_texto")
    assert any("P01 turno 0" in a for a in achadas)
    _reprova(bruto, "placeholder_fechado")


def test_pii_texto_recusa_conta_de_banco_com_digitos_de_verdade(bruto):
    t = _primeiro(bruto, "P03", intencao_esperada="fornece_dado", campo_alvo="conta")
    t["texto_cliente"], t["variacoes"] = "conta 000123456789", []
    achadas = _reprova(bruto, "pii_texto")
    assert any("numero fora do conjunto sintético" in a for a in achadas)


@pytest.mark.parametrize(
    ("tipo", "valor", "nao_sintetico"),
    [
        ("cpf", "000.000.012-44", False),
        ("cpf", "529.982.247-25", True),
        ("telefone", "(11) 91234-5678", False),
        ("telefone", "+55 11 98765-4321", False),
        ("telefone", "(11) 98123" + "-4567", True),
        ("email", "a@exemplo.test", False),
        ("email", "a@empresa" + ".com.br", True),
        ("cep", "00000-001", False),
        ("cep", "01001-000", True),
        ("uuid", "00000000-0000-4000-8000-000000000001", False),
        ("uuid", "11111111-2222-4333-8444-555555555555", True),
        ("numero", "0000123-4", False),
        ("numero", "123456789012", True),
        ("numero", "000123456789", True),
    ],
)
def test_pii_nao_sintetica(tipo, valor, nao_sintetico):
    assert pii.pii_nao_sintetica(tipo, valor) is nao_sintetico


def test_achados_pii_ve_cada_tipo():
    tipos = {
        t
        for t, _ in pii.achados_pii(
            "cpf 000.000.001-91 tel (11) 91234-5678 mail a@exemplo.test cep 00000-001 chave 00000000-0000-4000-8000-000000000001"
        )
    }
    assert tipos == {"cpf", "telefone", "email", "cep", "uuid"}
    assert pii.cpf_sintetico("00000000191")
    assert not pii.cpf_sintetico("52998224725")
    assert not pii.cpf_sintetico("00000000100")


def test_esquema_sem_f3_globais_no_duble_e_violacao_e_nao_excecao(bruto):
    del bruto["duble"]["f3_globais"]
    assert "esquema" in _codigos(c.validar(bruto))


def test_esquema_recusa_chave_a_mais_no_duble_e_na_semente(bruto):
    bruto["duble"]["extra"] = 1
    assert "esquema" in _codigos(c.validar(bruto))
    bruto2 = copy.deepcopy(bruto)
    del bruto2["duble"]["extra"]
    bruto2["semente"]["regras"]["outra"] = "x"
    assert "esquema" in _codigos(c.validar(bruto2))


def test_esquema_estrito_nao_coage_tipos(bruto):
    _persona(bruto, "P01")["perfil"]["idade"] = "41"
    assert "esquema" in _codigos(c.validar(bruto))
    bruto2 = copy.deepcopy(bruto)
    _persona(bruto2, "P01")["perfil"]["idade"] = 41
    _persona(bruto2, "P01")["perfil"]["vinculo_clt"] = "yes"
    assert "esquema" in _codigos(c.validar(bruto2))


@pytest.mark.parametrize(
    ("onde", "campo", "valor"),
    [
        ("persona", "classe", "classe_inventada"),
        ("cenario", "cenario", "cenario_inventado"),
        ("perfil", "valor_pre_aprovado_brl", 3001),
        ("perfil", "oferta_facta_ativa", False),
        ("perfil", "idade", 17),
        ("perfil", "prazo_oferta_x", 7),
        ("comportamento", "intencao_dominante", "parar"),
        ("comportamento", "estilo", []),
        ("persona", "critica", True),
        ("persona", "familia", "M"),
    ],
)
def test_esquema_recusa_valor_invalido_da_persona(bruto, onde, campo, valor):
    p = _persona(bruto, "P02")
    alvo = {"persona": p, "cenario": p["cenario_facta"], "perfil": p["perfil"], "comportamento": p["comportamento"]}[onde]
    alvo[campo] = valor
    assert "esquema" in _codigos(c.validar(bruto))


def test_esquema_recusa_p_m_na_f3_curta_e_h_com_em(bruto):
    _persona(bruto, "P-M01")["f3_curta"] = True
    assert "esquema" in _codigos(c.validar(bruto))
    bruto2 = copy.deepcopy(bruto)
    _persona(bruto2, "P-M01")["f3_curta"] = False
    _persona(bruto2, "P01")["em"] = ["EM1"]
    assert "esquema" in _codigos(c.validar(bruto2))


def test_esquema_recusa_forma_errada_do_turno(bruto):
    cliente = next(t for t in bruto["dialogos"]["P01"] if t["quem"] == "cliente")
    ia = bruto["dialogos"]["P01"][0]
    for mutacao in (
        (cliente, "tx_esperado", ["TX-01"]),
        (cliente, "texto_cliente", None),
        (ia, "objecao_esperada", "outra"),
        (ia, "intencao_esperada", "aceita"),
        (ia, "midia", "audio"),
    ):
        b = copy.deepcopy(bruto)
        alvo = b["dialogos"]["P01"][0 if mutacao[0] is ia else 1]
        alvo[mutacao[1]] = mutacao[2]
        assert "esquema" in _codigos(c.validar(b)), mutacao
    cliente_sem_nada = copy.deepcopy(bruto)
    cliente_sem_nada["dialogos"]["P01"][1]["midia"] = "audio"  # texto E mídia
    assert "esquema" in _codigos(c.validar(cliente_sem_nada))


def test_esquema_recusa_dominante_fora_da_lista(bruto):
    _persona(bruto, "P02")["comportamento"]["intencoes"] = ["saudacao"]
    assert "esquema" in _codigos(c.validar(bruto))


# --- ramos de erro do gabarito ---------------------------------------------------------------------------------------------------------


def test_dialogo_gabarito_reprova_turno_da_ia_sem_invariante_e_sem_proibida(bruto):
    t = bruto["dialogos"]["P01"][0]
    t["invariantes"], t["acoes_proibidas"] = [], []
    _reprova(bruto, "dialogo_gabarito")


def test_dialogo_gabarito_reprova_turno_sem_acoes_permitidas(bruto):
    bruto["dialogos"]["P01"][0]["acoes_permitidas"] = []
    _reprova(bruto, "dialogo_gabarito")


def test_dialogo_gabarito_reprova_campo_alvo_fora_de_lugar(bruto):
    t = _primeiro(bruto, "P01", quem="ia", fase_esperada="E3")
    t["campo_alvo"] = "pix"
    achadas = _reprova(bruto, "dialogo_gabarito")
    assert any("campo_alvo fora de TX-07" in a for a in achadas)
    b2 = copy.deepcopy(bruto)
    t2 = _primeiro(b2, "P01", fase_esperada="E3")
    del t2["campo_alvo"]
    entrega = _primeiro(b2, "P01", quem="cliente", campo_alvo="celular")
    del entrega["campo_alvo"]
    assert any("sem campo_alvo" in a for a in _reprova(b2, "dialogo_gabarito"))


def test_dialogo_gabarito_reprova_mensagem_depois_do_encerramento(bruto):
    turnos = bruto["dialogos"]["P23"]
    mudo = turnos[-1]
    mudo["tx_esperado"] = ["TX-26"]
    mudo["acoes_proibidas"] = [a for a in mudo["acoes_proibidas"] if a != "enviar"]
    achadas = _reprova(bruto, "dialogo_gabarito")
    assert any("depois do encerramento" in a for a in achadas)


def test_dialogo_gabarito_reprova_objecao_fora_de_ordem(bruto):
    _persona(bruto, "P08")["comportamento"]["objecoes"] = ["parcela_alta"]
    achadas = _reprova(bruto, "dialogo_gabarito")
    assert any("objeções" in a for a in achadas)


def test_dialogo_gabarito_reprova_fase_que_o_dialogo_nao_percorre(bruto):
    _persona(bruto, "P01")["fases"] = [*_persona(bruto, "P01")["fases"], "E9"]
    _reprova(bruto, "dialogo_gabarito")


def test_i1_reprova_sim_sem_pedido_de_confirmacao_e_t7_fora_do_e7(bruto):
    turnos = bruto["dialogos"]["P01"]
    for t in turnos:
        t["tx_esperado"] = [x for x in t.get("tx_esperado", []) if x != "TX-11"]
    achadas = _reprova(bruto, "gabarito_i1")
    assert any("SIM na E6 sem o pedido" in a for a in achadas)
    b2 = copy.deepcopy(bruto)
    e7 = _primeiro(b2, "P01", fase_esperada="E7")
    e7["fase_esperada"] = "E8"
    assert any("T7 só no turno E7" in a for a in _reprova(b2, "gabarito_i1"))


def test_i4_reprova_t7_mesma_chave_sem_transitorio_e_depois_de_indeterminado(bruto):
    t = _primeiro(bruto, "P24", fase_esperada="E8")
    t["acoes_permitidas"].append("T7_mesma_chave")
    t["fase_esperada"] = "E8"
    achadas = _reprova(bruto, "gabarito_i4")
    assert any("T7_mesma_chave" in a for a in achadas)


def test_i6_reprova_duas_mensagens_seguidas_e_i7_conta_so_turnos_sem_evento(bruto):
    a = _primeiro(bruto, "P01", fase_esperada="E7")
    assert a["quem"] == "ia"
    sem_evento = copy.deepcopy(bruto["dialogos"]["P01"])
    bruto["dialogos"]["P01"][bruto["dialogos"]["P01"].index(a) + 1]["evento"] = None
    _reprova(bruto, "gabarito_i6")
    assert len(sem_evento) < 24


def test_i8_reprova_tx35_sem_indeterminado_e_nota_em_turno_nao_e10_e_cliente_calado(bruto):
    t = _primeiro(bruto, "P36", fase_esperada="E10")
    t["nota_esperada"] = "TX-35"
    assert any("TX-35 sem indeterminado" in a for a in _reprova(bruto, "gabarito_i8"))
    b2 = copy.deepcopy(bruto)
    b2["dialogos"]["P01"][0]["nota_esperada"] = "TX-34"
    assert any("só no primeiro turno E10" in a for a in _reprova(b2, "gabarito_i8"))
    b3 = copy.deepcopy(bruto)
    b3["dialogos"]["P54"][0]["fase_esperada"] = "E10"
    b3["dialogos"]["P54"][0].update(nota_esperada="TX-34", motivo_e10="pede_humano")
    assert any("cliente nunca respondeu" in a for a in _reprova(b3, "gabarito_i8"))
    b4 = copy.deepcopy(bruto)
    e10 = _primeiro(b4, "P39", fase_esperada="E10")
    e10["nota_esperada"] = "TX-34"
    assert any("não gera nota" in a for a in _reprova(b4, "gabarito_i8"))


def test_i8_e10_precisa_declarar_nota_e_motivo(bruto):
    t = _primeiro(bruto, "P36", fase_esperada="E10")
    t["motivo_e10"] = None
    assert any("declara nota_esperada e motivo_e10" in a for a in _reprova(bruto, "gabarito_i8"))


def test_desfecho_derivado_cobre_todos_os_caminhos(bruto_original):
    corpus = c.montar(bruto_original)
    from ia_atendimento.corpus.regras.invariantes import desfecho_do_dialogo

    vistos = {next(iter(desfecho_do_dialogo(d))) for d in corpus.dialogos.values()}
    assert vistos == set(c.DESFECHOS)
    assert desfecho_do_dialogo(c.Dialogo(persona_id="X", turnos=())) == set()
    truncado = c.Dialogo(persona_id="X", turnos=corpus.dialogos["P01"].turnos[:2])
    assert desfecho_do_dialogo(truncado) == set()


def test_forma_whatsapp_reprova_midia_demais_e_texto_longo_fora_da_manipulacao(bruto):
    clientes = [t for ts in bruto["dialogos"].values() for t in ts if t["quem"] == "cliente"]
    for t in clientes[: len(clientes) // 2]:
        for chave in ("texto_cliente", "intencao_esperada", "variacoes", "pii_digitada", "campo_alvo", "objecao_esperada"):
            t.pop(chave, None)
        t["midia"] = "audio"
    achadas = _reprova(bruto, "forma_whatsapp")
    assert any("turnos de mídia" in a for a in achadas)
    b2 = c.carregar_bruto(CORPUS_DIR)
    t = _primeiro(b2, "P01", quem="cliente", fase_esperada="E3")
    t["texto_cliente"] = "x" * 400
    assert any("fora da persona de manipulação" in a for a in _reprova(b2, "forma_whatsapp"))


# --- agenda (M §2.4-§2.6) -------------------------------------------------------------------------------------------------------------------


def _m08(bruto: dict, pid: str, n: int = 0) -> dict:
    return _turnos(
        bruto,
        pid,
        fase_esperada="E3",
        dispara_em_utc=bruto["dialogos"][pid][[i for i, t in enumerate(bruto["dialogos"][pid]) if "TX-M08" in t.get("tx_esperado", [])][n]][
            "dispara_em_utc"
        ],
    )[0][1]


@pytest.mark.parametrize(
    ("dispara", "trecho"),
    [
        ("2026-11-18T22:01:00Z", "fora da janela da agenda"),  # 19:00 de São Paulo é o limite; 19:01 já não
        ("2026-11-18T10:00:00Z", "fora da janela da agenda"),  # 07:00
        ("2026-11-22T13:00:00Z", "fora da janela da agenda"),  # domingo
        ("2026-11-17T20:05:00Z", "menos de 10 min"),
        ("2026-11-19T20:00:00Z", "mais de 23 h"),
    ],
)
def test_agenda_reprova_volta_fora_da_regra(bruto, dispara, trecho):
    t = _m08(bruto, "P-M01")
    t["dispara_em_utc"] = dispara
    achadas = _reprova(bruto, "gabarito_agenda")
    assert any(trecho in a for a in achadas), achadas


def test_agenda_reprova_m08_sem_dispara_sem_agendar_e_dispara_fora_do_m08(bruto):
    t = _m08(bruto, "P-M01")
    t["acoes_permitidas"] = [a for a in t["acoes_permitidas"] if a != "agendar"]
    assert any("sem a ação `agendar`" in a for a in _reprova(bruto, "gabarito_agenda"))
    b2 = copy.deepcopy(bruto)
    del _m08(b2, "P-M01")["dispara_em_utc"]
    assert any("TX-M08 sem dispara_em_utc" in a for a in _reprova(b2, "gabarito_agenda"))
    b3 = copy.deepcopy(bruto)
    b3["dialogos"]["P-M01"][0]["dispara_em_utc"] = "2026-11-18T12:00:00Z"
    assert any("só no turno que confirma" in a for a in _reprova(b3, "gabarito_agenda"))


def test_agenda_reprova_volta_fora_do_prazo_e_volta_sem_agendamento_e_terceiro_agendamento(bruto):
    ((_i, volta),) = _turnos(bruto, "P-M01", evento="volta_combinada")
    volta["em_utc"] = "2026-11-18T13:00:00Z"  # 10:00, 1 h depois do combinado
    assert any("entre o horário combinado e +30 min" in a for a in _reprova(bruto, "gabarito_agenda"))
    b2 = copy.deepcopy(bruto)
    b2["dialogos"]["P-M01"] = [t for t in b2["dialogos"]["P-M01"] if "TX-M08" not in t.get("tx_esperado", [])]
    assert any("volta sem agendamento" in a for a in _reprova(b2, "gabarito_agenda"))
    b3 = copy.deepcopy(bruto)
    seis = b3["dialogos"]["P-M06"]
    extra = copy.deepcopy(next(t for t in seis if "TX-M08" in t.get("tx_esperado", [])))
    seis.append(extra)
    assert any("mais de 2 agendamentos" in a for a in _reprova(b3, "gabarito_agenda"))


def test_agenda_do_corpus_tem_volta_nas_seis_fases_de_pausa(bruto_original):
    corpus = c.montar(bruto_original)
    fases = {t.fase_esperada for d in corpus.dialogos.values() for t in d.turnos if "TX-M08" in t.tx_esperado}
    assert {"E2", "E3", "E5", "E6", "E8"} <= fases


# --- calendário e semente (ramos de erro) --------------------------------------------------------------------------------------------------


def test_dentro_da_agenda():
    def sp(h, m=0, dia=17):
        return datetime(2026, 11, dia, h + 3, m, tzinfo=UTC)

    assert calendario.dentro_da_agenda(sp(8, 30)) and calendario.dentro_da_agenda(sp(19, 0))
    assert not calendario.dentro_da_agenda(sp(8, 29)) and not calendario.dentro_da_agenda(sp(19, 1))
    assert calendario.dentro_da_agenda(sp(11, 59, 14)) and not calendario.dentro_da_agenda(sp(12, 30, 14))  # sábado só até 12:00
    assert not calendario.dentro_da_agenda(sp(10, 0, 15))  # domingo
    assert not calendario.dentro_da_agenda(sp(10, 0, 20))  # feriado
    with pytest.raises(ValueError, match="fuso"):
        calendario.dentro_da_agenda(datetime(2026, 11, 17, 10, 0))


def test_calendario_do_corpus_abre_o_domingo_so_por_parametro():
    """D-18 (B1.8): o padrão segue fechado (I3 e as regras não mudam até a B8.1c); aberto, o domingo vale 08–20 e a agenda 08:30–19:00.
    15/11 é feriado no corpus e segue bloqueado; 22/11 cai na DATAPREV. Casos de domingo aberto usam 08/11 e 29/11."""

    def sp(dia, h, m=0):
        return datetime(2026, 11, dia, h + 3, m, tzinfo=UTC)

    for dia in (8, 29):
        assert not calendario.dentro_do_horario(sp(dia, 12)) and not calendario.dentro_da_agenda(sp(dia, 12))
        assert calendario.dentro_do_horario(sp(dia, 8), domingo_aberto=True)
        assert calendario.dentro_do_horario(sp(dia, 19, 59), domingo_aberto=True)
        assert not calendario.dentro_do_horario(sp(dia, 20), domingo_aberto=True)
        assert calendario.dentro_da_agenda(sp(dia, 19), domingo_aberto=True)  # domingo não tem o corte de sábado
        assert not calendario.dentro_da_agenda(sp(dia, 8, 29), domingo_aberto=True)
    for dia in (15, 22):
        assert not calendario.dentro_do_horario(sp(dia, 12), domingo_aberto=True)
        assert not calendario.dentro_da_agenda(sp(dia, 12), domingo_aberto=True)


def test_cenarios_do_instante_cobre_cada_rotulo():
    def utc(d, h, m=0):
        return datetime(2026, 11, d, h, m, tzinfo=UTC)

    assert calendario.cenarios_do_instante(utc(17, 14)) == {"horario_normal"}
    assert "noite" in calendario.cenarios_do_instante(utc(18, 0))
    assert "sabado" in calendario.cenarios_do_instante(utc(14, 15))
    assert "domingo" in calendario.cenarios_do_instante(utc(15, 15))
    assert "feriado_20_11" in calendario.cenarios_do_instante(utc(20, 13))
    assert "virada_dataprev" in calendario.cenarios_do_instante(utc(21, 14))
    assert "virada_22h30_utc" in calendario.cenarios_do_instante(utc(17, 22, 30))
    assert "noite" not in calendario.cenarios_do_instante(utc(21, 14))  # a janela DATAPREV não é «noite»


def test_semente_reprodutivel_reprova_versao_ordem_f3_e_sementes_alteradas(bruto):
    bruto["semente"]["versao"] = 2
    bruto["semente"]["ordem_f3_curta"] = list(reversed(bruto["semente"]["ordem_f3_curta"]))
    bruto["semente"]["sementes"]["P02"] = [1, 2, 3]
    bruto["semente"]["sementes"]["P99"] = [1, 2, 3]
    achadas = c.validar(bruto)
    for trecho in ("versão 1", "ordem_f3_curta", "sementes de P02", "persona inexistente P99"):
        assert any(trecho in a for a in achadas), trecho


def test_ids_unicos_e_cpf_alinhado_ramos_de_erro(bruto):
    _persona(bruto, "P36")["cenario_facta"].update(sem_chamada_facta=False)
    _persona(bruto, "P01")["cenario_facta"].update(sem_chamada_facta=True)
    _persona(bruto, "P30")["cenario_facta"]["global_duble"] = "reabertura"
    _persona(bruto, "P02")["cpf"] = _persona(bruto, "P03")["cpf"]
    _persona(bruto, "P-M18")["cenario_facta"].update(persona_duble=None, sem_chamada_facta=False)
    _persona(bruto, "P37")["cpf"] = _persona(bruto, "P38")["cpf"]
    _persona(bruto, "P29")["cenario_facta"]["persona_duble"] = None
    achadas = c.validar(bruto)
    for trecho in (
        "não bate com `f3_sem_facta`",
        "não pode ser «sem FACTA» nem global",
        "global_duble deveria ser",
        "CPF diferente",
        "P-M sem persona do dublê tem de declarar",
        "repetido entre personas (um CPF por persona",
        "o dublê tem persona para ela",
    ):
        assert any(trecho in a for a in achadas), trecho


def test_cenario_tempo_coerente_reprova_chave_antes_do_inicio(bruto):
    ctx = _persona(bruto, "P01")["contexto"]
    ctx["instante_chave_utc"] = "2026-11-10T14:00:00Z"
    assert any("anterior ao início" in a for a in _reprova(bruto, "cenario_tempo_coerente"))


def test_gabarito_i3_reprova_relogio_que_anda_para_tras(bruto):
    t = _primeiro(bruto, "P-M01", evento="volta_combinada")
    t["em_utc"] = "2026-11-17T10:00:00Z"
    _reprova(bruto, "gabarito_i3")


def test_i7_reprova_mais_de_24_turnos_do_modelo(bruto):
    ia = bruto["dialogos"]["P01"][0]
    for _ in range(25):
        bruto["dialogos"]["P01"].append(copy.deepcopy(ia))
    _reprova(bruto, "gabarito_i7")


def test_normalizacao_e_helpers_da_semente():
    assert semente.chave(1, "a") == semente.chave(1, "a") != semente.chave(2, "a")
    with pytest.raises(ValueError, match="sem texto"):
        semente.texto_do_turno(
            c.Turno(quem="ia", fase_esperada="E1", acoes_permitidas=("responder",), acoes_proibidas=("T4",)), 1, "P01", 1, 0
        )


def test_main_valida_e_imprime_a_semente(capsys):
    from ia_atendimento.corpus.__main__ import main

    assert main([]) == 0
    assert "0 violação" in capsys.readouterr().out
    assert main(["--semente"]) == 0
    assert '"holdout"' in capsys.readouterr().out


def test_main_devolve_1_quando_o_corpus_tem_violacao(monkeypatch, capsys):
    from ia_atendimento.corpus import __main__ as m

    monkeypatch.setattr(m, "validar", lambda bruto: ["ids_unicos: x"])
    assert m.main([]) == 1
    assert "1 violação" in capsys.readouterr().out


def test_esquema_oferta_ativa_exige_valor_e_prazo_e_fases_nao_vazias(bruto):
    _persona(bruto, "P02")["perfil"]["valor_pre_aprovado_brl"] = None
    assert "esquema" in _codigos(c.validar(bruto))
    b2 = copy.deepcopy(bruto)
    _persona(b2, "P02")["perfil"]["valor_pre_aprovado_brl"] = 3000
    _persona(b2, "P02")["fases"] = []
    assert "esquema" in _codigos(c.validar(b2))


def test_conjunto_f3_curta_reprova_lista_de_p_m_fora_de_ordem(bruto):
    bruto["personas_m"].reverse()
    achadas = _reprova(bruto, "conjunto_f3_curta")
    assert any("P-M01..P-M24" in a for a in achadas)


def test_python_m_corpus_roda_como_programa():
    import subprocess
    import sys

    saida = subprocess.run([sys.executable, "-I", "-m", "ia_atendimento.corpus"], capture_output=True, text=True, check=False)
    assert saida.returncode == 0, saida.stdout + saida.stderr
    assert "0 violação" in saida.stdout
