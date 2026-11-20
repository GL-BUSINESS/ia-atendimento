"""R2-001 (revisão 0911): pendente que começa com «dd/mm hh:mm» não pode derrubar o turno no `auditar_prompt`.

A numeração `1. «06/11 15:30»` colava o dígito do índice à data e à hora: a corrente de dígitos da máscara somava 9 dígitos, a isenção de
data e hora caía e o portão levantava `ContextoComDadoPessoal` (duas falhas seguidas ⇒ repasse). O mesmo acontecia entre DUAS pendentes,
uma terminando em hora e a seguinte começando com data. O rótulo da pendente agora é uma letra entre parênteses, que quebra a corrente.
"""

from __future__ import annotations

import pytest

from ia_atendimento import contexto as ctx
from ia_atendimento.tokens import EstimadorPorCaracteres


def _contexto(*pendentes: str) -> ctx.Contexto:
    insumos = ctx.Insumos(
        fase="E8", estado='{"fase":"E8"}', modulo="modulo", ferramentas="", exemplos=(), resumo=None, trocas=(), resultados="",
        pendentes=tuple(ctx.proteger_texto(p, ()) for p in pendentes),
    )  # fmt: skip
    return ctx.construir(insumos, {}, EstimadorPorCaracteres())


@pytest.mark.parametrize(
    "pendentes",
    [
        ("06/11 15:30",),
        ("pode ser 06/11 15:30",),
        ("pode ser às 15:30", "06/11 15:30"),
        ("06/11", "15:30"),
        (*(f"0{d}/11 1{d}:30" for d in range(1, 10)), "10/11 10:00", "11/11 11:00"),  # 11 linhas, como 10 pendentes + omitidas
    ],
)
def test_pendente_com_data_e_hora_passa_no_portao(pendentes):
    contexto = _contexto(*pendentes)
    ctx.auditar_prompt(contexto)  # antes: ContextoComDadoPessoal
    _, lidas = ctx.ler_do_prompt(contexto.usuario)
    assert lidas[-1] == pendentes[-1]


def test_ler_do_prompt_devolve_as_pendentes_na_ordem():
    contexto = _contexto("oi", "06/11 15:30", "ok")
    assert ctx.ler_do_prompt(contexto.usuario) == ("E8", ("oi", "06/11 15:30", "ok"))


def test_portao_continua_barrando_documento_na_pendente():
    """O rótulo novo não abre brecha: um CPF que escapasse da proteção ainda derruba o turno."""
    insumos = ctx.Insumos(
        fase="E8", estado='{"fase":"E8"}', modulo="modulo", ferramentas="", exemplos=(), resumo=None, trocas=(), resultados="",
        pendentes=("000.000." + "201-00",),
    )  # fmt: skip
    with pytest.raises(ctx.ContextoComDadoPessoal):
        ctx.auditar_prompt(ctx.construir(insumos, {}, EstimadorPorCaracteres()))


def test_cabem_rotulos_para_todas_as_pendentes_e_a_linha_de_omitidas():
    assert len(ctx._ROTULOS_DE_PENDENTE) >= ctx.MAX_PENDENTES_NO_PROMPT + 1
