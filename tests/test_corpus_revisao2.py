"""Corpus da F3, revisão 2 (30/10): cenário do dublê, hold-out de verdade, amostra mínima, fronteiras e higiene."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

from ia_atendimento import corpus as c
from ia_atendimento.corpus import regras as pacote_regras
from ia_atendimento.corpus.regras import duble as regras_duble
from ia_atendimento.corpus.regras import semente as regras_semente
from ia_atendimento.corpus.vocabulario import FERRAMENTAS_POR_FASE
from tests.test_corpus import CORPUS_DIR, RAIZ, _persona, _reprova


@pytest.fixture(scope="module")
def bruto_original() -> dict:
    return c.carregar_bruto(CORPUS_DIR)


@pytest.fixture
def bruto(bruto_original: dict) -> dict:
    return copy.deepcopy(bruto_original)


def _turno(bruto: dict, pid: str, **campos) -> dict:
    return next(t for t in bruto["dialogos"][pid] if all(t.get(k) == v for k, v in campos.items()))


# --- R2-4 · o gabarito é amarrado ao cenário do dublê --------------------------------------------------------------------------------------


def test_p19_recusa_do_duble_nao_pode_ter_sucesso_com_link_antes_da_recusa(bruto):
    turnos = bruto["dialogos"]["P19"]
    i = next(i for i, t in enumerate(turnos) if t.get("evento") == "resultado_t7_recusa_politica")
    turnos[i] = {**turnos[i], "evento": "resultado_t7_sucesso", "fase_esperada": "E8", "tx_esperado": ["TX-16"]}
    achadas = _reprova(bruto, "gabarito_cenario_duble")
    assert any("não produz o resultado resultado_t7_sucesso" in a for a in achadas)


def test_p04_aprovado_nao_produz_indeterminado_nem_recusa(bruto):
    turnos = bruto["dialogos"]["P04"]
    i = next(i for i, t in enumerate(turnos) if t.get("evento") == "resultado_t7_sucesso")
    for evento, tx in (("resultado_t7_indeterminado", "TX-16"), ("resultado_t7_recusa_politica", "TX-16")):
        b = copy.deepcopy(bruto)
        b["dialogos"]["P04"][i]["evento"] = evento
        achadas = _reprova(b, "gabarito_cenario_duble")
        assert any(evento in a for a in achadas)
        assert any(f"obriga o {'TX-15' if 'indet' in evento else 'TX-18'}" in a for a in achadas)
        assert any("TX-16 (link) só depois de um resultado de sucesso" in a for a in achadas), tx


def test_tx16_sem_t7_antes_e_t7_mesma_chave_sem_t7_reprovam(bruto):
    turnos = bruto["dialogos"]["P04"]
    for t in turnos:
        t["acoes_permitidas"] = [a for a in t["acoes_permitidas"] if a != "T7"]
    achadas = _reprova(bruto, "gabarito_cenario_duble")
    assert any("TX-16 sem nenhum T7 permitido antes" in a for a in achadas)
    b2 = c.carregar_bruto(CORPUS_DIR)
    for t in b2["dialogos"]["P29"]:
        t["acoes_permitidas"] = [a for a in t["acoes_permitidas"] if a != "T7"]
    assert any("T7_mesma_chave sem T7 antes" in a for a in _reprova(b2, "gabarito_cenario_duble"))


def test_evento_de_resultado_em_persona_sem_facta_reprova(bruto):
    p = _persona(bruto, "P36")
    assert p["cenario_facta"]["sem_chamada_facta"]
    t = _turno(bruto, "P36", fase_esperada="E10")
    t["evento"] = "resultado_t7_sucesso"
    _reprova(bruto, "gabarito_cenario_duble")


def test_eventos_possiveis_por_persona_cenario_e_global(bruto_original):
    corpus = c.montar(bruto_original)
    por_id = {p.id: p for p in corpus.todas()}
    assert regras_duble.eventos_possiveis(por_id["P04"]) == {"resultado_t7_sucesso"}
    assert "t8_proposta_criada_em_17_min" in regras_duble.eventos_possiveis(por_id["P25"])
    assert "t13_banco_fechado_antes_do_t7" in regras_duble.eventos_possiveis(por_id["P30"])
    assert "retry_apos_retry_after" in regras_duble.eventos_possiveis(por_id["P31"])
    assert regras_duble.eventos_possiveis(por_id["P36"]) == frozenset()


def test_tx_obrigado_por_evento_silencioso_vem_na_proxima_mensagem(bruto):
    t = _turno(bruto, "P30", evento="t13_banco_fechado_antes_do_t7", fase_esperada="E10")
    t["tx_esperado"] = ["TX-26"]
    achadas = _reprova(bruto, "gabarito_cenario_duble")
    assert any("obriga o TX-20" in a for a in achadas)


# --- R2-5 · hold-out com roteiro do cliente próprio e falas próprias ------------------------------------------------------------------------


def test_holdout_independente_reprova_hold_out_com_o_roteiro_do_cliente_de_outra_persona(bruto):
    """Esqueleto diferente (a IA responde outro TX), mas o cliente faz exatamente o mesmo: reprova pelo roteiro (fase, intenção)."""
    clone = copy.deepcopy(bruto["dialogos"]["P01"])
    for t in clone:
        if t["quem"] == "ia" and t.get("tx_esperado") == ["TX-01"]:
            t["tx_esperado"] = ["TX-02", "TX-03"]
            t["fase_esperada"] = "E3"
            t["acoes_proibidas"] = [a for a in t["acoes_proibidas"] if a != "enviar"]
    bruto["dialogos"]["P26"] = clone
    achadas = c.validar(bruto)
    assert any(a.startswith("holdout_independente:") and "roteiro do cliente" in a for a in achadas)


def test_holdout_independente_reprova_falas_repetidas_do_desenvolvimento(bruto):
    dev = next(
        t["texto_cliente"]
        for pid, ts in bruto["dialogos"].items()
        if pid not in bruto["semente"]["holdout"]
        for t in ts
        if t.get("texto_cliente") and len(t["texto_cliente"]) > 12 and not t.get("campo_alvo")
    )
    for t in bruto["dialogos"]["P08"]:
        if t.get("texto_cliente") and len(t["texto_cliente"]) > 6 and not t.get("pii_digitada"):
            t["texto_cliente"], t["variacoes"] = dev, []
    achadas = _reprova(bruto, "holdout_independente")
    assert any("repete" in a and "P08" in a for a in achadas)


def test_holdout_do_corpus_tem_roteiro_do_cliente_unico_e_poucas_falas_repetidas(bruto_original):
    corpus = c.montar(bruto_original)
    roteiros = [regras_semente.roteiro_do_cliente(d) for d in corpus.dialogos.values()]
    for pid in corpus.semente.holdout:
        if pid in corpus.dialogos:
            assert roteiros.count(regras_semente.roteiro_do_cliente(corpus.dialogos[pid])) == 1, pid
    assert {"P19", "P26", "P59"} <= set(corpus.semente.holdout)
    # P19, P26 e P59 já não repetem o roteiro de P01, P21, P30 e P44 (nem entre si)
    dev = {regras_semente.roteiro_do_cliente(corpus.dialogos[p]) for p in ("P01", "P21", "P30", "P44")}
    ho = [regras_semente.roteiro_do_cliente(corpus.dialogos[p]) for p in ("P19", "P26", "P59")]
    assert len(set(ho)) == 3
    assert not set(ho) & dev


# --- R2-6 · amostra mínima -----------------------------------------------------------------------------------------------------------------


def test_cada_intencao_tem_pelo_menos_dois_turnos_e_ha_oito_de_texto_livre(bruto_original):
    corpus = c.montar(bruto_original)
    por_intencao: dict[str, int] = {}
    for d in corpus.dialogos.values():
        for t in d.turnos:
            if t.intencao_esperada:
                por_intencao[t.intencao_esperada] = por_intencao.get(t.intencao_esperada, 0) + 1
    assert set(por_intencao) == set(c.INTENCOES)
    assert min(por_intencao.values()) >= 2
    assert sum(t.texto_livre_ia for d in corpus.dialogos.values() for t in d.turnos) >= 8
    com_livre = {pid for pid, d in corpus.dialogos.items() if any(t.texto_livre_ia for t in d.turnos)}
    assert com_livre & set(corpus.semente.holdout)


def test_cobertura_dialogos_reprova_intencao_com_um_turno_so(bruto):
    achados = [t for ts in bruto["dialogos"].values() for t in ts if t.get("intencao_esperada") == "reclamacao"]
    assert len(achados) >= 2
    for t in achados[1:]:
        t["intencao_esperada"] = "aceita"
    achadas = _reprova(bruto, "cobertura_dialogos")
    assert any("reclamacao com 1 turno" in a for a in achadas)


def test_cobertura_dialogos_reprova_menos_de_oito_turnos_de_texto_livre(bruto):
    livres = [t for ts in bruto["dialogos"].values() for t in ts if t.get("texto_livre_ia")]
    for t in livres[3:]:
        t["texto_livre_ia"] = False
        t["tx_esperado"] = t["tx_esperado"] or ["TX-26"]
    achadas = _reprova(bruto, "cobertura_dialogos")
    assert any("turnos com `texto_livre_ia`" in a for a in achadas)


# --- baixas ----------------------------------------------------------------------------------------------------------------------------------


def test_janela_de_24_h_e_exclusiva_na_fronteira(bruto):
    """A 24 h00 exatas já é template (ROTEIRO: `< 24 h`); a 23 h59 ainda é texto livre."""
    turnos = bruto["dialogos"]["P01"]
    cliente = next(i for i, t in enumerate(turnos) if t["quem"] == "cliente")
    turnos[cliente]["em_utc"] = "2026-11-17T14:00:00Z"
    proxima = next(i for i in range(cliente + 1, len(turnos)) if turnos[i]["quem"] == "ia" and turnos[i].get("tx_esperado"))
    for tudo in turnos[proxima:]:
        tudo.pop("em_utc", None)
    turnos[proxima]["em_utc"] = "2026-11-18T14:00:00Z"  # 24 h00
    achadas = [a for a in c.validar(bruto) if a.startswith("gabarito_janela24h:")]
    assert achadas
    turnos[proxima]["em_utc"] = "2026-11-18T13:59:00Z"  # 23 h59
    assert not [a for a in c.validar(bruto) if a.startswith("gabarito_janela24h:")]


def test_ferramentas_por_fase_e_a_tabela_de_h():
    esperado = {
        "E0": {"T1", "T3", "T13", "T14"},
        "E1": {"T1", "T3", "T13", "T14"},
        "E2": {"T1", "T2", "T3"},
        "E3": {"T3", "T13"},
        "E4": {"T3", "T5", "T13"},
        "E5": {"T6"},
        "E6": {"T13", "T15"},
        "E7": {"T7", "T7_mesma_chave", "T8", "T9"},
        "E8": {"T9", "T10"},
        "E9": {"T11", "T12", "T14"},
        "E10": {"T11", "T12", "T14"},
    }
    assert {k: set(v) for k, v in FERRAMENTAS_POR_FASE.items()} == esperado
    assert "T4" not in set().union(*FERRAMENTAS_POR_FASE.values())


def test_ferramenta_fora_da_tabela_de_h_reprova_t2_na_e3_e_t10_na_e10(bruto):
    t = _turno(bruto, "P01", quem="ia", fase_esperada="E3")
    t["acoes_permitidas"].append("T2")
    _reprova(bruto, "gabarito_acoes_por_fase")
    b2 = c.carregar_bruto(CORPUS_DIR)
    final = _turno(b2, "P36", quem="ia", fase_esperada="E10")
    final["acoes_permitidas"].append("T10")
    _reprova(b2, "gabarito_acoes_por_fase")


def test_o_pacote_nao_aponta_de_src_para_tests():
    pacote = Path(c.__file__).parent
    for arquivo in pacote.rglob("*.py"):
        assert '"tests"' not in arquivo.read_text(encoding="utf-8"), arquivo
    assert not hasattr(c, "CORPUS_DIR")
    with pytest.raises(TypeError):
        c.carregar_bruto()  # type: ignore[call-arg]


def test_main_aceita_raiz_explicita(capsys):
    from ia_atendimento.corpus.__main__ import main

    assert main(["--raiz", str(CORPUS_DIR)]) == 0
    assert "0 violação" in capsys.readouterr().out


def test_doc_da_revisao_1_nao_traz_cpf_de_dv_valido_fora_da_faixa():
    from ia_atendimento.corpus.pii import achados_pii

    texto = (RAIZ / "docs" / "REVISAO-B8.1a-3010.md").read_text(encoding="utf-8")
    assert [a for a in achados_pii(texto) if a[0] == "cpf" and not a[1].startswith("000")] == []


def test_regras_do_registro_sao_todas_funcoes():
    assert len(pacote_regras.REGRAS) == 42
    assert all(callable(f) for f in pacote_regras.REGRAS.values())


def test_atualizar_duble_regrava_e_verifica(tmp_path, monkeypatch):
    pytest.importorskip("yaml")
    spec = importlib.util.spec_from_file_location("atualizar_duble", RAIZ / "scripts" / "atualizar_duble.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    arquivo = tmp_path / "personas.yaml"
    arquivo.write_text(
        "versao: 1\nf3_globais: {}\nf3_sem_facta: [P13]\npersonas:\n- {id: a, n: 1, cpf: 000.000.001-91, cenario: aprovado, f3: [P01]}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(modulo, "ALVO", tmp_path / "saida.json")
    assert modulo.main([str(arquivo), "abc123"]) == 0
    assert modulo.main([str(arquivo), "abc123", "--verificar"]) == 0
    arquivo.write_text(arquivo.read_text(encoding="utf-8").replace("[P01]", "[P02]"), encoding="utf-8")
    assert modulo.main([str(arquivo), "abc123", "--verificar"]) == 1
    assert modulo.main([]) == 2
