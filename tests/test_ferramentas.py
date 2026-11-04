"""Ferramentas registradas no `Agent` (B1.4, achado A-1 da revisão 1; sonda p9): o retorno REAL de uma ferramenta só volta ao modelo projetado e auditado.

O 'Fireworks' é o `httpx.MockTransport` de `apoio_b14`; os dados do retorno são sintéticos (`000.000.0nn`, `exemplo.test`, valores redondos).
"""

from __future__ import annotations

import contextlib
import json
import uuid
from dataclasses import replace
from typing import Any

import httpx
import pytest
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.exceptions import ToolFailed

from ia_atendimento.agente import ErroDoModelo, ResolvedorModelo, criar_agente, executar_turno
from ia_atendimento.contexto import Contexto, ContextoComDadoPessoal
from ia_atendimento.ferramentas import (
    MENSAGEM_DE_NOVA_TENTATIVA,
    Deps,
    FerramentaFalhou,
    FerramentaSemProjecao,
    RetornoDeFerramentaInvalido,
    proteger_retorno,
    registrar,
)
from ia_atendimento.turno import ACOES_POR_FASE, FerramentaForaDaFase
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

pytest_plugins = ["tests.apoio_b12"]

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


FASE_DA_FERRAMENTA = {"T2": "E2", "T3": "E3", "T5": "E4", "T10": "E8"}  # a fase em que o modelo pode pedir cada uma (H §2.3b)


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
    resultado = await executar_turno(_agente(rede, {nome: funcao}), deps, contexto or contexto_falso(FASE_DA_FERRAMENTA[nome]))
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
    """O cliente se chama «Ativa»: a máscara trocaria a palavra no prompt, então o valor do catálogo some do retorno (o resto fica)."""
    deps = Deps(atendimento_id=uuid.UUID(int=1), pessoa_id=uuid.UUID(int=2), nomes=("Ativa Silva",))
    rede, _ = await _turno_com_ferramenta(_ferramenta({"status": "ativa", "versao": 2}), nome="T3", deps=deps)
    (tool,) = [m for m in rede.corpos[1]["messages"] if m["role"] == "tool"]
    assert json.loads(tool["content"]) == {"versao": 2}


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


async def test_falha_da_protecao_de_ferramenta_chega_como_erro_do_modelo_com_o_gasto():
    """Retorno que não é objeto = ferramenta quebrada: conta como falha do turno (`except ErroDoModelo`) e leva o gasto do que já foi cobrado."""
    with pytest.raises(ErroDoModelo) as erro:
        await _turno_com_ferramenta(_ferramenta(f"oferta de {CPF}"))
    assert isinstance(erro.value, RetornoDeFerramentaInvalido) and erro.value.codigo == "retorno_de_ferramenta_invalido"
    assert erro.value.uso is not None and erro.value.uso.tokens_in == 1000 and erro.value.uso.custo_brl > 0
    assert CPF not in str(erro.value)


# --- qualquer exceção da ferramenta vira ErroDoModelo de texto fixo (R2-02) -------------------------------------------------------------------


def _ferramenta_que_levanta(erro: Exception):
    def funcao(ctx: RunContext[Deps]) -> Any:
        raise erro

    return funcao


@pytest.mark.parametrize(
    "erro",
    [
        ValueError(f"cpf={CPF} nome={NOME_DO_CLIENTE}"),
        RuntimeError(f"timeout no gateway para o CPF {CPF} ({NOME_DO_CLIENTE})"),
        KeyError(CPF),
        httpx.ConnectError(f"sem rota para o cliente {CPF}"),
        OSError(f"falha ao ler {EMAIL}"),
    ],
)
async def test_qualquer_excecao_da_ferramenta_vira_erro_do_modelo_com_texto_fixo_e_o_gasto(erro):
    """R2-02: só `ToolRetryError`/`ToolFailedError` viravam texto fixo; um `RuntimeError` escapava de `executar_turno` com o CPF na mensagem e sem contar."""
    with pytest.raises(ErroDoModelo) as capturado:
        await _turno_com_ferramenta(_ferramenta_que_levanta(erro))
    falha = capturado.value
    assert isinstance(falha, FerramentaFalhou) and falha.codigo == "ferramenta_falhou" and str(falha) == "a ferramenta T3 falhou"
    assert CPF not in repr(falha) and NOME_DO_CLIENTE not in repr(falha) and EMAIL not in repr(falha)
    assert falha.__cause__ is None and falha.__context__ is None
    assert falha.uso is not None and falha.uso.tokens_in == 1000 and falha.uso.custo_brl > 0  # o gasto da 1ª chamada vai junto


async def test_toolfailed_da_ferramenta_vai_ao_modelo_com_texto_fixo():
    """A1f da revisão 2: o texto fixo do `ToolFailed` não tinha teste (o mutante sobrevivia)."""
    rede = RedeSimulada([_chamada_de_ferramenta("T3"), resposta_openai(TURNO_E2)])
    await executar_turno(_agente(rede, {"T3": _ferramenta_que_levanta(ToolFailed(f"cpf {CPF} recusado"))}), DEPS, contexto_falso("E3"))
    corpo = json.dumps(rede.corpos[1]["messages"], ensure_ascii=False)
    assert CPF not in corpo and MENSAGEM_DE_NOVA_TENTATIVA in corpo


async def test_erro_do_modelo_levantado_dentro_da_ferramenta_passa_sem_ser_trocado():
    class Proprio(ErroDoModelo):
        pass

    with pytest.raises(Proprio):
        await _turno_com_ferramenta(_ferramenta_que_levanta(Proprio("meu_codigo", "fixa")))


# --- a ferramenta registrada obedece à fase: esquema no corpo, execução e conta de tokens (R2-03; sondas p4 e p9 da revisão 2) --------------


def _todas_as_ferramentas(chamadas: list[str]) -> dict[str, Any]:
    def uma(nome: str):
        def funcao(ctx: RunContext[Deps]) -> dict[str, Any]:
            chamadas.append(nome)
            return {"versao": 1}

        return funcao

    return {nome: uma(nome) for nome in ("T2", "T3", "T5", "T10")}


def _nomes_no_corpo(corpo: dict[str, Any]) -> list[str]:
    return [t["function"]["name"] for t in corpo["tools"]]


@pytest.mark.parametrize(
    ("fase", "esperadas"),
    [
        ("E2", ["T2", "T3"]),
        ("E3", ["T3"]),
        ("E4", ["T3", "T5"]),
        ("E5", []),
        ("E6", []),
        ("E7", []),
        ("E8", ["T10"]),
        ("E10", []),
    ],
)
async def test_so_o_esquema_das_ferramentas_da_fase_vai_ao_corpo_http(fase, esperadas):
    """R2-03: com T2/T3/T5/T10 registradas, o corpo da E2, E5 e E7 levava as quatro (≈ 300 tokens fora da conta do teto)."""
    acao = sorted(ACOES_POR_FASE[fase])[0]  # a ação que a fase aceita (E7 só `aguardar`, E10 `encerrar`/`repassar`)
    rede = RedeSimulada([resposta_openai({**TURNO_E2, "acao": acao})])
    agente = _agente(rede, _todas_as_ferramentas([]))
    await executar_turno(agente, DEPS, contexto_falso(fase))
    assert sorted(_nomes_no_corpo(rede.corpos[0])) == sorted([*esperadas, "final_result"])


async def test_ferramenta_que_a_fase_nao_libera_nao_executa_mesmo_que_o_modelo_a_chame():
    """O modelo pede T5 na E3: a função não roda (não estava nem no corpo), e o gasto não some."""
    chamadas: list[str] = []
    rede = RedeSimulada([_chamada_de_ferramenta("T5"), resposta_openai(TURNO_E2)])
    with contextlib.suppress(ErroDoModelo):  # pode virar saída inválida; o que importa é que a função NÃO rodou
        await executar_turno(_agente(rede, _todas_as_ferramentas(chamadas)), DEPS, contexto_falso("E3"))
    assert chamadas == []


async def test_ferramenta_fora_da_fase_na_execucao_e_acao_fora_da_fase_com_o_gasto():
    """Defesa em profundidade: mesmo se `prepare_tools` fosse contornado, a execução recusa (`AcaoForaDaFase`, `acao_invalida`)."""
    from ia_atendimento.ferramentas import ProjecaoDeFerramentas
    from ia_atendimento.turno import AcaoForaDaFase

    chamadas: list[str] = []

    async def deixa_tudo(self, ctx, tool_defs):  # `prepare_tools` contornado
        return tool_defs

    ProjecaoDeFerramentas.prepare_tools, original = deixa_tudo, ProjecaoDeFerramentas.prepare_tools
    try:
        rede = RedeSimulada([_chamada_de_ferramenta("T5"), resposta_openai(TURNO_E2)])
        with pytest.raises(AcaoForaDaFase) as erro:
            await executar_turno(_agente(rede, _todas_as_ferramentas(chamadas)), DEPS, contexto_falso("E3"))
    finally:
        ProjecaoDeFerramentas.prepare_tools = original
    assert chamadas == [] and isinstance(erro.value, FerramentaForaDaFase) and erro.value.acao_invalida
    assert erro.value.uso is not None and erro.value.uso.tokens_in == 1000


def test_ferramentas_chamadas_fora_da_fase_reprovam_na_validacao_do_turno():
    from ia_atendimento.turno import ResultadoTurno, Turno, UsoDoTurno, validar_turno_na_fase

    turno = Turno(intencao="saudacao", acao="responder", confianca="alta")
    resultado = ResultadoTurno(turno, "m", "p", UsoDoTurno(), ferramentas_chamadas=("T5",))
    with pytest.raises(FerramentaForaDaFase):
        validar_turno_na_fase("E3", turno, resultado=resultado)
    validar_turno_na_fase("E4", turno, resultado=resultado)  # T5 vale na E4
    validar_turno_na_fase("E3", turno, resultado=replace(resultado, ferramentas_chamadas=("T3",)))


def test_os_esquemas_das_ferramentas_registradas_entram_na_conta_de_tokens():
    agente = _agente(RedeSimulada([]), _todas_as_ferramentas([]))
    por_fase = {fase: agente.tokens_das_ferramentas(fase) for fase in ("E2", "E3", "E4", "E5", "E7", "E8")}
    assert por_fase["E5"] == por_fase["E7"] == 0
    assert por_fase["E2"] > por_fase["E3"] > 0 and por_fase["E4"] > por_fase["E3"] and por_fase["E8"] > 0
    assert agente.tokens_das_ferramentas("E99") == 0


async def test_montar_contexto_soma_os_tokens_das_ferramentas_e_corta_para_caber(db_conn, relogio, versoes, chaveiro):
    from ia_atendimento import contexto as ctx
    from ia_atendimento.linha_tempo import mensagens_pendentes
    from tests.apoio_b12 import AGORA
    from tests.apoio_b14 import abrir_em, receber

    agente = _agente(RedeSimulada([]), _todas_as_ferramentas([]))
    atd, _ = abrir_em(db_conn, relogio, versoes, fase="E4")
    receber(db_conn, atd, chaveiro, "oi", nomes=(NOME_DO_CLIENTE,))
    pendentes = mensagens_pendentes(db_conn, atd)
    sem = ctx.montar_contexto(db_conn, atd, pendentes=pendentes, chaveiro=chaveiro, nomes=(NOME_DO_CLIENTE,), agora=AGORA)
    com = ctx.montar_contexto(
        db_conn, atd, pendentes=pendentes, chaveiro=chaveiro, nomes=(NOME_DO_CLIENTE,), agora=AGORA,
        tokens_das_ferramentas=agente.tokens_das_ferramentas,
    )  # fmt: skip
    assert com.tokens_ferramentas == agente.tokens_das_ferramentas("E4") > 0
    assert com.tokens_total == sem.tokens_total + com.tokens_ferramentas
    # com o teto apertado, o que as ferramentas custam entra na decisão de cortar (e de recusar)
    apertado = sem.tokens_total + 5
    with pytest.raises(ctx.ContextoNaoCabe):
        ctx.montar_contexto(
            db_conn, atd, pendentes=pendentes, chaveiro=chaveiro, nomes=(NOME_DO_CLIENTE,), agora=AGORA, teto=apertado,
            tokens_das_ferramentas=agente.tokens_das_ferramentas,
        )  # fmt: skip


async def test_executar_turno_recusa_o_contexto_que_nao_contou_as_ferramentas_e_estouraria_o_teto():
    from ia_atendimento.contexto import TETO_TOKENS, ContextoNaoCabe

    agente = _agente(RedeSimulada([resposta_openai({**TURNO_E2, "acao": "responder"})]), _todas_as_ferramentas([]))
    ferramentas = agente.tokens_das_ferramentas("E4")
    base = contexto_falso("E4", pendentes=("x",)).tokens_total
    caracteres = int((TETO_TOKENS - ferramentas // 2 - base) * 3 / 1.1)  # tokens_total fica entre (teto − ferramentas) e o teto
    quase_cheio = contexto_falso("E4", pendentes=("x" * caracteres,))
    assert TETO_TOKENS - ferramentas < quase_cheio.tokens_total <= TETO_TOKENS  # o contexto sozinho cabe...
    with pytest.raises(ContextoNaoCabe):  # ...mas com os esquemas das ferramentas que o provedor recebe, não
        await executar_turno(agente, DEPS, quase_cheio)
