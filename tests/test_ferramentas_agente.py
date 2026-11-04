"""Aceite da B5.1: o registro gera as `Tool` do agente, e a chamada pelo function calling passa pelo gateway inteiro (validação,
referência, destino, projeção da B1.4 e fase da R2-03).

O 'Fireworks' é o `httpx.MockTransport` de `apoio_b14`; os dados são sintéticos.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from ia_atendimento.agente import ResolvedorModelo, criar_agente, executar_turno
from ia_atendimento.ferramentas import Deps
from tests.apoio_b14 import MODELO, NOME_DO_CLIENTE, TURNO_E2, RedeSimulada, contexto_falso, resposta_openai, settings_de_teste
from tests.apoio_gateway import ATENDIMENTO, CPF, OFERTA_REAL, PESSOA, PRODUCAO, RETORNO_T3_CRU, Espiao, gateway


def _chamada(nome: str, argumentos: dict[str, Any]) -> httpx.Response:
    chamada = {"id": "call_g", "type": "function", "function": {"name": nome, "arguments": json.dumps(argumentos)}}
    return httpx.Response(
        200,
        json={
            "id": "x", "object": "chat.completion", "created": 1, "model": "m",
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {"role": "assistant", "content": None, "tool_calls": [chamada]}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 10, "total_tokens": 1010},
        },
    )  # fmt: skip


async def _turno(gw, nome: str, argumentos: dict[str, Any], *, fase: str = "E3", modo: str = "real"):
    rede = RedeSimulada([_chamada(nome, argumentos), resposta_openai(TURNO_E2)])
    s = settings_de_teste()
    agente = criar_agente(ResolvedorModelo(s, cliente_http=rede.cliente()), MODELO, gw.ferramentas_do_agente(), settings=s)
    deps = Deps(atendimento_id=ATENDIMENTO, pessoa_id=PESSOA, nomes=(NOME_DO_CLIENTE,), modo=modo)
    resultado = await executar_turno(agente, deps, contexto_falso(fase, referencias={"oferta-1": OFERTA_REAL}))
    (tool,) = [m for m in rede.corpos[1]["messages"] if m["role"] == "tool"]
    return rede, resultado, json.loads(tool["content"])


def test_registro_gera_as_tool_do_agente():
    ferramentas = gateway().ferramentas_do_agente()
    assert set(ferramentas) == {"T2", "T3", "T5", "T10"}
    t5 = ferramentas["T5"]
    assert t5.name == "T5" and "simular" in (t5.description or "")
    esquema = t5.tool_def.parameters_json_schema
    assert set(esquema["properties"]) == {"oferta_ref", "alvo"} and esquema["additionalProperties"] is False


async def test_ferramenta_do_gateway_no_agente_projeta_e_resolve_a_referencia():
    t3 = Espiao(RETORNO_T3_CRU)
    rede, resultado, corpo = await _turno(gateway(executores={"T3": t3}), "T3", {"oferta_ref": "oferta-1"})
    assert [d["function"]["name"] for d in rede.corpos[0]["tools"] if d["function"]["name"] != "final_result"] == ["T3"]  # fase E3
    assert corpo == {"oferta_ref": "oferta-1", "status": "ativa", "versao": 2, "placeholders": ["valor_liberado", "valor_parcela", "prazo"]}
    (chamada,) = t3.chamadas
    assert chamada.referencias["oferta_ref"].id == OFERTA_REAL and chamada.destino.url == PRODUCAO[1]
    segunda = json.dumps(rede.corpos[1]["messages"], ensure_ascii=False)
    assert all(p not in segunda for p in (CPF, "5000", "0.0613", "410", "TAB-0001", "assina.exemplo", OFERTA_REAL))
    assert resultado.ferramentas_chamadas == ("T3",) and resultado.referencias == {"oferta-1": OFERTA_REAL}


async def test_argumento_proibido_pelo_function_calling_volta_como_erro_tipado_sem_eco():
    t3 = Espiao(RETORNO_T3_CRU)
    rede, _, corpo = await _turno(gateway(executores={"T3": t3}), "T3", {"oferta_ref": "oferta-1", "cpf": CPF})
    assert corpo == {"erro": "PARAMETRO_INVALIDO"} and t3.chamadas == []
    (tool,) = [m for m in rede.corpos[1]["messages"] if m["role"] == "tool"]
    assert CPF not in tool["content"]


async def test_no_modo_duble_o_agente_le_fixture_e_nunca_a_producao():
    t3 = Espiao(RETORNO_T3_CRU)
    _, _, corpo = await _turno(gateway(executores={"T3": t3}, config_modo=lambda: "duble"), "T3", {"oferta_ref": "oferta-1"}, modo="duble")
    assert corpo["status"] == "ativa"
    assert t3.chamadas[0].destino.tipo == "fixture" and t3.chamadas[0].destino.url is None
