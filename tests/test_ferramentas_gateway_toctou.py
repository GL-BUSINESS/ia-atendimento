"""Pré-condições voláteis reconferidas depois da vaga do limitador e da leitura do CPF (achado MÉDIO da revisão automática de 20/11,
TOCTOU/fail-open no gateway da B5.1). Dados sintéticos; nada sai para fora."""

from __future__ import annotations

import asyncio

from ia_atendimento.ferramentas.erros import PRECONDICOES
from ia_atendimento.ferramentas.gateway import Referencia
from ia_atendimento.ferramentas.orcamento import OrcamentoDoTurno
from ia_atendimento.ferramentas.segredo import CpfEmMemoria
from tests.apoio_gateway import CONFIRMACAO, CPF, Espiao, contexto, gateway

T7_OK = {"classe": "criada", "ref_externa": "AF-0001"}
GUARDA_S = 2.0


def _tudo_facta(atendimento_id, campo, real):
    return Referencia(real, banco="FACTA")


def _precondicoes(vale: list[bool]):
    return {nome: (lambda pedido: vale[0]) for nome in PRECONDICOES}


async def _chamar(gw, nome, args):
    return await gw.chamar(nome, args, contexto(), orcamento=OrcamentoDoTurno())


async def test_precondicao_que_cai_durante_a_espera_da_vaga_barra_o_disparo():
    """A T7 passa as pré-condições, espera a vaga atrás de duas T8 e, na espera, o cliente pede opt-out (ou o humano assume): ao pegar
    a vaga, o gateway confere de novo e NÃO dispara."""
    vale, liberar, em_voo = [True], asyncio.Event(), [0]

    async def segura(chamada):
        em_voo[0] += 1
        await liberar.wait()
        return {"estado": "aguardando"}

    t7 = Espiao(T7_OK)
    gw = gateway(executores={"T8": Espiao(comportamento=segura), "T7": t7}, referencias=_tudo_facta, precondicoes=_precondicoes(vale))
    ocupadas = [asyncio.create_task(_chamar(gw, "T8", {"tentativa_ref": f"t7-{n}"})) for n in range(2)]
    for _ in range(100):
        if em_voo[0] == 2:
            break
        await asyncio.sleep(0.005)
    tarefa = asyncio.create_task(_chamar(gw, "T7", {"confirmacao_id": CONFIRMACAO}))
    await asyncio.sleep(0.02)
    vale[0] = False
    liberar.set()
    r = await asyncio.wait_for(tarefa, GUARDA_S)
    await asyncio.gather(*ocupadas)
    assert t7.chamadas == [] and r.erro is not None and r.erro.codigo == "PRECONDICAO_FALHOU"


async def test_precondicao_que_cai_durante_a_leitura_do_cpf_barra_o_disparo():
    vale = [True]

    async def ler_cpf(pessoa_id):
        vale[0] = False
        await asyncio.sleep(0)
        return CpfEmMemoria(CPF)

    t7 = Espiao(T7_OK)
    gw = gateway(executores={"T7": t7}, leitor_de_cpf=ler_cpf, precondicoes=_precondicoes(vale))
    r = await _chamar(gw, "T7", {"confirmacao_id": CONFIRMACAO})
    assert t7.chamadas == [] and r.erro is not None and r.erro.codigo == "PRECONDICAO_FALHOU"


async def test_precondicoes_que_seguem_valendo_disparam_uma_vez():
    t7 = Espiao(T7_OK)
    gw = gateway(executores={"T7": t7}, precondicoes=_precondicoes([True]))
    r = await _chamar(gw, "T7", {"confirmacao_id": CONFIRMACAO})
    assert r.erro is None and len(t7.chamadas) == 1
