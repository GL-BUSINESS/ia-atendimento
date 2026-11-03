"""Ferramentas registradas no `Agent` (B1.4, achado A-1 da revisão 1; sonda p9): o retorno REAL de uma ferramenta só volta ao modelo projetado e auditado.

O 'Fireworks' é o `httpx.MockTransport` de `apoio_b14`; os dados do retorno são sintéticos (`000.000.0nn`, `exemplo.test`, valores redondos).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
import pytest
from pydantic_ai import ModelRetry, RunContext

from ia_atendimento.agente import ResolvedorModelo, criar_agente, executar_turno
from ia_atendimento.contexto import Contexto, ContextoComDadoPessoal
from ia_atendimento.ferramentas import (
    Deps,
    FerramentaSemProjecao,
    RetornoDeFerramentaInvalido,
    proteger_retorno,
    registrar,
)
from tests.apoio_b14 import (
    CPF,
    EMAIL,
    MODELO,
    NOME_DO_CLIENTE,
    TURNO_E2,
    RedeSimulada,
    contexto_falso,
    resposta_openai,
    settings_de_teste,
)

DEPS = Deps(atendimento_id=uuid.UUID(int=1), pessoa_id=uuid.UUID(int=2), nomes=(NOME_DO_CLIENTE,))
OFERTA_REAL = "0194a8b0-2f7e-4c3a-9d41-6b1f0c2e7a55"
OPCAO_REAL = "0194a8b0-2f7e-4c3a-9d41-6b1f0c2e7a66"
RETORNO_CRU = {
    "oferta_ref": OFERTA_REAL,
    "status": "ativa",
    "versao": 2,
    "valor_liberado": "R$ 5.000,00",
    "valor_parcela": "R$ 312,45",
    "prazo": 36,
    "cpf": CPF,
    "nome": NOME_DO_CLIENTE,
    "email": EMAIL,
    "coef_valor": "0.0613",
    "comissao": "R$ 410,00",
    "motivo_do_banco": "reprovado por margem de 1.234,56",
    "placeholders": ["valor_liberado", "valor_parcela", "prazo", CPF],
}
PROIBIDOS = [
    "5.000,00", "312,45", "R$", CPF, "00000001234", NOME_DO_CLIENTE, "Alvardel", EMAIL, "0.0613", "coef_valor", "410,00", "1.234,56",
    "motivo_do_banco", OFERTA_REAL, "valor_liberado\":", "cpf", "comissao",
]  # fmt: skip


def _chamada_de_ferramenta(nome: str) -> httpx.Response:
    chamada = {"id": "call_t", "type": "function", "function": {"name": nome, "arguments": "{}"}}
    return httpx.Response(
        200,
        json={
            "id": "x", "object": "chat.completion", "created": 1, "model": "m",
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {"role": "assistant", "content": None, "tool_calls": [chamada]}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 10, "total_tokens": 1010},
        },
    )  # fmt: skip


def _agente(rede: RedeSimulada, ferramentas: dict[str, Any]):
    s = settings_de_teste()
    return criar_agente(ResolvedorModelo(s, cliente_http=rede.cliente()), MODELO, ferramentas, settings=s)


async def _turno_com_ferramenta(funcao, nome: str = "T3", deps: Deps = DEPS, contexto: Contexto | None = None):
    rede = RedeSimulada([_chamada_de_ferramenta(nome), resposta_openai(TURNO_E2)])
    resultado = await executar_turno(_agente(rede, {nome: funcao}), deps, contexto or contexto_falso("E3"))
    return rede, resultado


def _ferramenta(retorno: Any):
    """Função de ferramenta que devolve `retorno` (precisa do `RunContext` anotado: o Pydantic AI não passa `ctx` por nome)."""

    def funcao(ctx: RunContext[Deps]) -> Any:
        return retorno

    return funcao


def oferta_ativa(ctx: RunContext[Deps]) -> dict[str, Any]:
    """O que o gateway devolveria de verdade: valores, CPF, coeficiente, comissão e o motivo cru do banco."""
    return dict(RETORNO_CRU)


async def test_retorno_de_ferramenta_real_nao_vai_cru_ao_modelo():
    """A-1: antes, a 2ª requisição ao provedor levava a mensagem `tool` com os valores, o CPF e o coeficiente em claro."""
    rede, r = await _turno_com_ferramenta(oferta_ativa)
    assert len(rede.corpos) == 2 and r.ferramentas_chamadas == ("T3",)
    segunda = json.dumps(rede.corpos[1]["messages"], ensure_ascii=False)
    assert [p for p in PROIBIDOS if p in segunda] == []
    (mensagem,) = [m for m in rede.corpos[1]["messages"] if m["role"] == "tool"]
    assert json.loads(mensagem["content"]) == {
        "oferta_ref": "oferta-1",
        "status": "ativa",
        "versao": 2,
        "placeholders": ["valor_liberado", "valor_parcela", "prazo"],
    }
    assert r.referencias == {"oferta-1": OFERTA_REAL}  # o processador (B1.6) volta ao id real por aqui


async def test_funcao_assincrona_e_ferramenta_com_argumentos_tambem_passam_pela_projecao():
    async def simular(ctx: RunContext[Deps]) -> dict[str, Any]:
        return {
            "opcoes": [{"opcao_ref": OPCAO_REAL, "dentro_da_alcada": True, "valor_liberado": "R$ 4.000,00", "placeholders": ["prazo"]}],
            "cpf": CPF,
        }

    rede, r = await _turno_com_ferramenta(simular, nome="T5")
    segunda = json.dumps(rede.corpos[1]["messages"], ensure_ascii=False)
    assert "4.000,00" not in segunda and CPF not in segunda and "R$" not in segunda and OPCAO_REAL not in segunda
    (tool,) = [m for m in rede.corpos[1]["messages"] if m["role"] == "tool"]
    assert r.referencias == {"opcao-1": OPCAO_REAL}
    assert json.loads(tool["content"])["opcoes"][0]["opcao_ref"] == "opcao-1"


async def test_apelido_do_contexto_e_reusado_no_retorno_da_ferramenta():
    contexto = contexto_falso("E3", referencias={"oferta-1": OFERTA_REAL})
    _, r = await _turno_com_ferramenta(_ferramenta({"oferta_ref": OFERTA_REAL, "status": "ativa"}), contexto=contexto)
    assert r.referencias == {"oferta-1": OFERTA_REAL}  # o MESMO id real, o MESMO apelido (nada de oferta-2 para a mesma oferta)


async def test_nome_do_cliente_no_retorno_da_ferramenta_e_barrado():
    segunda_rede, _ = await _turno_com_ferramenta(_ferramenta({"status": "alvardel", "etapa": "proposta"}), nome="T2")
    (tool,) = [m for m in segunda_rede.corpos[1]["messages"] if m["role"] == "tool"]
    assert json.loads(tool["content"]) == {"etapa": "proposta"}  # o sobrenome do cliente sai; o resto fica


async def test_model_retry_da_ferramenta_vai_ao_modelo_com_texto_fixo():
    """A mensagem de um `ModelRetry` é lida pelo modelo: não pode citar o dado que falhou."""

    def falha(ctx: RunContext[Deps]) -> dict[str, Any]:
        raise ModelRetry(f"cpf {CPF} recusado, valor R$ 5.000,00")

    rede = RedeSimulada([_chamada_de_ferramenta("T3"), resposta_openai(TURNO_E2)])
    await executar_turno(_agente(rede, {"T3": falha}), DEPS, contexto_falso("E3"))
    corpo = json.dumps(rede.corpos[1]["messages"], ensure_ascii=False)
    assert CPF not in corpo and "5.000,00" not in corpo and "siga sem ela" in corpo


async def test_retorno_que_nao_e_objeto_levanta_sem_eco_do_valor():
    with pytest.raises(RetornoDeFerramentaInvalido) as erro:
        await _turno_com_ferramenta(_ferramenta(f"oferta de {CPF}"))
    assert CPF not in str(erro.value)


def test_proteger_retorno_audita_o_que_a_projecao_deixou_passar(monkeypatch):
    """Terceira cerca: se a projeção falhar e algo ainda casar com a máscara, o turno não sai (`ErroDoModelo`)."""
    from ia_atendimento import ferramentas as modulo

    monkeypatch.setattr(modulo, "projetar_resultado", lambda *a, **k: json.dumps({"T3": {"status": CPF}}))
    with pytest.raises(ContextoComDadoPessoal) as erro:
        proteger_retorno("T3", {"status": "ativa"}, DEPS)
    assert CPF not in str(erro.value)


def test_proteger_retorno_sem_nada_a_passar_devolve_objeto_vazio():
    assert proteger_retorno("T3", {"cpf": CPF, "valor_liberado": "R$ 1,00"}, DEPS) == {}


# --- o registro: sem projeção declarada o agente nem sobe -------------------------------------------------------------------------------


@pytest.mark.parametrize("nome", ["oferta_ativa", "T7", "T4", "T13", "t3", ""])
def test_ferramenta_sem_projecao_declarada_nao_sobe(nome):
    with pytest.raises(FerramentaSemProjecao):
        criar_agente(ResolvedorModelo(settings_de_teste()), MODELO, {nome: oferta_ativa}, settings=settings_de_teste())


def test_ferramentas_so_como_mapa_nunca_como_lista_de_funcoes():
    with pytest.raises(FerramentaSemProjecao, match="mapa"):
        registrar([oferta_ativa])  # type: ignore[arg-type]


def test_as_quatro_ferramentas_do_modelo_sobem_com_o_nome_do_catalogo():
    tools, capacidades = registrar({"T2": oferta_ativa, "T3": oferta_ativa, "T5": oferta_ativa, "T10": oferta_ativa})
    assert [t.name for t in tools] == ["T2", "T3", "T5", "T10"] and len(capacidades) == 1
    assert registrar({}) == ([], [])
