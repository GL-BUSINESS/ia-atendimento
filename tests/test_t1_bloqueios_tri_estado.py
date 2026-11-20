"""G-0125 (revisão 0911): chave ausente de `nao_perturbe`/`limite_contratos` não pode virar «sem bloqueio».

O `pessoas:resumos` do 360 tem TRÊS estados por chave: objeto (bloqueado), `null` (a pessoa não está na lista) e AUSENTE (a flag do 360 está
desligada, por exemplo no desfazer do B4.2). `SaidaT1` tinha `False` por padrão e colapsava «ausente» em «livre»: a pré-condição
`sem_nao_perturbe` da T7 passava para quem pediu para não ser procurado. Agora os dois campos são obrigatórios e a projeção do resumo do 360 é
fail-closed: chave ausente (ou resumo sem a pessoa) vira bloqueio.
"""

from __future__ import annotations

import pydantic
import pytest

from ia_atendimento.ferramentas.esquemas import SaidaT1, saida_t1_do_resumo

CPF_DIGITOS = "000000" + "20100"  # base 2nn, DV inválido
PESSOA = {"pessoa_id": "11111111-1111-7111-8111-111111111111", "nome": None, "cpf_mascarado": "***.***.***-00", "cpf": CPF_DIGITOS}
NAO_PERTURBE = {"desde": "2026-11-01T10:00:00Z", "ate": "2026-12-01T10:00:00Z"}
LIMITE = {"banco": "FACTA", "desde": "2026-11-01T10:00:00Z", "visto_em": "2026-11-10T10:00:00Z"}


def test_saida_t1_sem_as_chaves_de_bloqueio_e_recusada():
    with pytest.raises(pydantic.ValidationError):
        SaidaT1.model_validate({"encontrado": True})


def test_t1_chave_ausente_bloqueia():
    saida = saida_t1_do_resumo({"itens": [PESSOA]})
    assert (saida.nao_perturbe, saida.limite_contratos) == (True, True)


def test_t1_null_e_livre_e_objeto_bloqueia():
    livre = saida_t1_do_resumo({"itens": [{**PESSOA, "nao_perturbe": None, "limite_contratos": None}]})
    assert (livre.encontrado, livre.nao_perturbe, livre.limite_contratos) == (True, False, False)
    preso = saida_t1_do_resumo({"itens": [{**PESSOA, "nao_perturbe": NAO_PERTURBE, "limite_contratos": LIMITE}]})
    assert (preso.nao_perturbe, preso.limite_contratos) == (True, True)


def test_t1_so_uma_chave_ausente_bloqueia_so_ela():
    saida = saida_t1_do_resumo({"itens": [{**PESSOA, "nao_perturbe": None}]})
    assert (saida.nao_perturbe, saida.limite_contratos) == (False, True)


def test_t1_pessoa_nao_encontrada_e_bloqueada():
    saida = saida_t1_do_resumo({"itens": []})
    assert (saida.encontrado, saida.nao_perturbe, saida.limite_contratos) == (False, True, True)


@pytest.mark.parametrize("valor", [False, 0, "", [], "sim"])
def test_t1_valor_que_nao_e_objeto_nem_null_bloqueia(valor):
    """Forma inesperada também é «não sei»: bloqueia (o 360 só manda objeto ou null)."""
    saida = saida_t1_do_resumo({"itens": [{**PESSOA, "nao_perturbe": valor, "limite_contratos": valor}]})
    assert (saida.nao_perturbe, saida.limite_contratos) == (True, True)


def test_t1_nao_leva_cpf_nem_nome():
    saida = saida_t1_do_resumo({"itens": [{**PESSOA, "nome": "Pessoa Sintetica", "nao_perturbe": None, "limite_contratos": None}]})
    assert CPF_DIGITOS not in saida.model_dump_json() and saida.primeiro_nome is None
