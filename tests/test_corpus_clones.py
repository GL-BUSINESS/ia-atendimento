"""Um CPF e uma persona do dublê por persona da F3 (B2.4, R1-09): o estado do dublê (scenario do WireMock) e os stubs são por CPF.

O corpus de verdade passa sem violação; cada defeito é provado por mutação em memória (como em `test_corpus.py`).
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from ia_atendimento import corpus as c
from ia_atendimento.corpus.regras import duble as regras_duble

CORPUS_DIR = Path(__file__).resolve().parent / "corpus"


@pytest.fixture(scope="module")
def bruto_original() -> dict:
    return c.carregar_bruto(CORPUS_DIR)


@pytest.fixture
def bruto(bruto_original: dict) -> dict:
    return copy.deepcopy(bruto_original)


def _persona(bruto: dict, pid: str) -> dict:
    return next(p for p in [*bruto["personas"], *bruto["personas_m"]] if p["id"] == pid)


def _achadas(bruto: dict, codigo: str) -> list[str]:
    return [v for v in c.validar(bruto) if v.startswith(codigo + ":")]


def test_o_corpus_tem_84_cpfs_distintos_e_uma_persona_do_duble_por_persona(bruto_original):
    corpus = c.montar(bruto_original)
    assert len({p.cpf for p in corpus.todas()}) == 84
    com_stub = [p for p in corpus.todas() if p.cenario_facta.persona_duble]
    assert len({p.cenario_facta.persona_duble for p in com_stub}) == len(com_stub) == 60
    assert c.validar(bruto_original) == []


def test_dois_cpfs_iguais_reprovam_mesmo_com_persona_do_duble(bruto):
    """P05 no CPF de P02: antes passava (as duas dividiam o `aprovado-36`); agora é violação, além do CPF não bater com a persona do dublê dela."""
    _persona(bruto, "P05")["cpf"] = _persona(bruto, "P02")["cpf"]
    achadas = _achadas(bruto, "cpf_alinhado_duble")
    assert any("repetido entre personas (um CPF por persona" in a and "P02" in a and "P05" in a for a in achadas), achadas


def test_prazo_da_oferta_diferente_do_do_cenario_aprovado_reprova(bruto):
    """O T3 mostra o prazo do perfil e o T5/T7 do dublê calcula no do `aprovado-N`: P34 com 24x numa persona `aprovado-36` é violação."""
    p = _persona(bruto, "P34")
    assert p["cenario_facta"]["persona_duble"].startswith("aprovado-36")
    p["perfil"]["prazo_oferta_x"] = 24
    achadas = _achadas(bruto, "cpf_alinhado_duble")
    assert any("P34" in a and "prazo da oferta (24x)" in a and "aprovado-36" in a for a in achadas), achadas


def test_clone_vale_pela_persona_base_nos_eventos_possiveis(bruto_original):
    corpus = c.montar(bruto_original)
    por_id = {p.id: p for p in corpus.todas()}
    assert por_id["P28"].cenario_facta.persona_duble != "indet-criada-5min"  # clone próprio
    esperado = regras_duble.eventos_possiveis(por_id["P24"], corpus)  # a base
    assert "t8_proposta_criada_em_5_min" in esperado and regras_duble.eventos_possiveis(por_id["P28"], corpus) == esperado
    with pytest.raises(TypeError):  # o corpus é obrigatório: sem ele o clone voltaria vazio em silêncio (R2-13)
        regras_duble.eventos_possiveis(por_id["P28"])  # type: ignore[call-arg]


def test_gabarito_do_clone_e_amarrado_ao_cenario_da_base(bruto):
    """P28 (clone de `indet-criada-5min`) com um resultado que o cenário não produz continua reprovando: o clone herda os eventos da base."""
    turnos = bruto["dialogos"]["P28"]
    turno = next(t for t in turnos if t.get("evento"))
    turno["evento"] = "resultado_t7_recusa_politica"
    assert any("P28" in a and "não produz o resultado" in a for a in _achadas(bruto, "gabarito_cenario_duble"))
