"""Agente do turno (B1.4, sp01 T6): um provedor, o `Turno` e a execução com custo, latência e `trace_id`.

- **UM provedor** (estudo G §4): `OpenAIChatModel` em `https://us.api.fireworks.ai/inference/v1`, roteador só-EUA da versão 1017, saída por
  ferramenta (`Turno`), `output_retries=1`, **sem `FallbackModel`**. Falha de rede, HTTP, tempo ou saída inválida vira `ErroDoModelo`, sem
  encadear a causa (a mensagem do SDK pode citar o corpo da resposta). A reserva é o repasse ao vendedor: duas falhas, B1.6.
- **Raciocínio desligado por `extra_body`**, na forma que `Settings.modelo_raciocinio_off` manda. O padrão é HIPÓTESE até a A2.9 provar
  qual das duas formas o V4.1 Flash no Fireworks aceita; `raciocinio=true` na faixa só depois da F3 (`RaciocinioNaoLiberado`).
- **O provedor real fica atrás de `Provedor`.** Nos testes roda só o `ProvedorFalso`, que responde pelo roteiro da F3 (`roteiro_f3`)
  sem rede.
  A chave da API entra só por `Settings` (`SecretStr`), é lida dentro de `resolver` e registrada como segredo do scrubber.
- `Deps` não tem CPF, telefone nem nome: só os dois ids do atendimento e da pessoa (o gateway lê o 360 em memória, D18).
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any, Final, Protocol

import httpx
from openai import AsyncOpenAI, OpenAIError
from pydantic_ai import Agent, RunContext, capture_run_messages
from pydantic_ai.exceptions import (
    AgentRunError,
    ModelHTTPError,
    ModelRequestTimeout,
    ModelTimeoutError,
    RunTimedOut,
    UnexpectedModelBehavior,
)
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, ThinkingPart, ToolCallPart, UserPromptPart
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.instrumented import InstrumentationSettings
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import RequestUsage

from ia_atendimento import observabilidade
from ia_atendimento.config import PRECOS_PADRAO, Precos, Settings
from ia_atendimento.contexto import Apelidos, Contexto, ler_do_prompt
from ia_atendimento.ferramentas import Deps, registrar
from ia_atendimento.turno import (
    ACOES_POR_FASE,
    FERRAMENTAS_DO_MODELO_POR_FASE,
    OUTPUT_RETRIES,
    TX_DO_MODELO_POR_FASE,
    AcaoForaDaFase,
    ErroDoModelo,
    FerramentaForaDaFase,
    FerramentaPedida,
    ProvedorIndisponivel,
    ResultadoTurno,
    SaidaInvalida,
    Turno,
    TurnoForaDaFase,
    TxForaDaFase,
    UsoDoTurno,
    custo_brl,
    formato_do_turno,
    validar_turno_na_fase,
)

PROVEDOR_FIREWORKS_US: Final = "fireworks-us"
RETENTATIVAS_DE_FERRAMENTA: Final = 1
TOKENS_DE_SAIDA_DO_FALSO: Final = 90
CARACTERES_POR_TOKEN_DO_FALSO: Final = 3
_ERROS_DO_PROVEDOR: Final = (AgentRunError, httpx.HTTPError, OpenAIError, TimeoutError)
_ERROS_DE_TEMPO: Final = (TimeoutError, httpx.TimeoutException, ModelRequestTimeout, ModelTimeoutError, RunTimedOut)


# --- dependências e faixa ---------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ModeloDaFaixa:
    """Uma entrada de `modelo_por_faixa` (config, vigente em `iniciado_em`). `modelo` e `provedor` são o que o passo `decisao` grava."""

    modelo: str
    provedor: str
    raciocinio: bool
    custo_max_brl: Decimal

    @classmethod
    def de_config(cls, valor: Mapping[str, Any], faixa: str) -> ModeloDaFaixa:
        """`valor` = `config_vigente('modelo_por_faixa')`; `faixa` = `atendimento.faixa_esforco`."""
        try:
            item = valor[faixa]
            return cls(item["modelo"], item["provedor"], bool(item["raciocinio"]), Decimal(str(item["custo_max_brl"])))
        except (KeyError, TypeError):
            raise ProvedorNaoConfigurado(f"modelo_por_faixa sem entrada válida para a faixa {faixa}") from None


# --- provedor ---------------------------------------------------------------------------------------------------------------------------


class ProvedorNaoConfigurado(Exception):
    """Par modelo/provedor fora do que o MVP tem (só `deepseek-v4p1-flash-1017` em `fireworks-us`). Outro par é mudança de código "
    "revisada."""


class RaciocinioNaoLiberado(ProvedorNaoConfigurado):
    """`raciocinio=true` numa faixa: só depois da F3 (plano T6). Ligar sem medir sobe custo e latência e quebra a chamada de ferramenta "
    "(G §3)."""


class Provedor(Protocol):
    def resolver(self, modelo: str, provedor: str, raciocinio: bool) -> Model:
        """O modelo do Pydantic AI para o par (`modelo_por_faixa`)."""
        ...


def extra_body_raciocinio(forma: str) -> dict[str, Any]:
    """O trecho do `extra_body` que desliga o raciocínio. As duas formas estão na API do Fireworks (G §3); NENHUMA provada no V4.1 "
    "Flash (A2.9)."""
    if forma == "reasoning_effort_none":
        return {"reasoning_effort": "none"}
    if forma == "thinking_disabled":
        return {"thinking": {"type": "disabled"}}
    raise ValueError("forma de desligar o raciocínio desconhecida")


class ResolvedorModelo:
    """O provedor de verdade: Fireworks só-EUA. Não faz rede ao ser criado nem em `resolver`; a rede é do primeiro `run`."""

    def __init__(self, settings: Settings, *, cliente_http: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._cliente_http = cliente_http  # injetável: os testes põem um transporte simulado aqui
        observabilidade.registrar_segredo(settings.modelo_api_key_1)

    def __repr__(self) -> str:
        return f"ResolvedorModelo(modelo={self._settings.modelo_nome!r}, roteador={self._settings.modelo_roteador!r})"

    def resolver(self, modelo: str, provedor: str, raciocinio: bool) -> OpenAIChatModel:
        s = self._settings
        if not modelo.startswith("deepseek-") or (modelo, provedor) != (s.modelo_nome, PROVEDOR_FIREWORKS_US):
            raise ProvedorNaoConfigurado(f"par {modelo}/{provedor} não configurado (MVP: {s.modelo_nome}/{PROVEDOR_FIREWORKS_US})")
        if raciocinio:
            raise RaciocinioNaoLiberado("raciocinio=true só depois da F3 (A2.9 mede o parâmetro e a F3 aprova)")
        cliente = AsyncOpenAI(
            base_url=s.modelo_base_url_1,
            api_key=s.modelo_api_key_1.get_secret_value(),
            max_retries=s.modelo_tentativas_http,
            timeout=s.modelo_timeout_s,
            http_client=self._cliente_http,
        )
        ajustes = ModelSettings(
            temperature=s.modelo_temperatura, max_tokens=s.modelo_max_tokens, extra_body=extra_body_raciocinio(s.modelo_raciocinio_off)
        )
        # `max_tokens` (o campo que a API do Fireworks documenta; o padrão do Pydantic AI seria `max_completion_tokens`, não provado
        # lá: A2.9)
        perfil = OpenAIModelProfile(openai_chat_supports_max_completion_tokens=False)
        return OpenAIChatModel(s.modelo_roteador, provider=OpenAIProvider(openai_client=cliente), profile=perfil, settings=ajustes)


# --- provedor falso (testes) ------------------------------------------------------------------------------------------------------------


class Roteiro(Protocol):
    def responder(self, fase: str, mensagens: tuple[str, ...]) -> Turno | Mapping[str, Any]:
        """O `Turno` (ou o dicionário cru, para provar saída inválida) que o modelo daria a estas mensagens pendentes na fase."""
        ...


def _texto_do_usuario(mensagens: Sequence[ModelMessage]) -> str:
    for mensagem in reversed(mensagens):
        if isinstance(mensagem, ModelRequest):
            partes = [p.content for p in mensagem.parts if isinstance(p, UserPromptPart) and isinstance(p.content, str)]
            if partes:
                return "\n".join(partes)
    return ""


@dataclass
class ProvedorFalso:
    """Modelo determinístico, sem rede: lê o prompt que recebeu, pergunta ao `roteiro` e devolve o `Turno` pela ferramenta de saída.

    `vistos` guarda o prompt completo de cada chamada (instruções + mensagem), para provar o que chegou ao modelo. `falha` faz a próxima
    chamada levantar (provar que um provedor só falha e propaga). `uso` fixa os tokens; sem ele, estima pelo tamanho do prompt."""

    roteiro: Roteiro
    uso: RequestUsage | None = None
    falha: Exception | None = None
    chamadas: int = 0
    vistos: list[str] = field(default_factory=list)

    def resolver(self, modelo: str, provedor: str, raciocinio: bool) -> Model:
        return FunctionModel(self._responder, model_name=f"falso:{modelo}")

    def _responder(self, mensagens: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.chamadas += 1
        usuario = _texto_do_usuario(mensagens)
        self.vistos.append(f"{info.instructions or ''}\n{usuario}")
        if self.falha is not None:
            raise self.falha
        fase, pendentes = ler_do_prompt(usuario)
        if fase is None:
            raise RuntimeError("o prompt não traz a fase: o ProvedorFalso só entende o contexto montado por `montar_contexto`")
        saida = self.roteiro.responder(fase, pendentes)
        argumentos = saida.model_dump(mode="json") if isinstance(saida, Turno) else dict(saida)
        uso = self.uso or RequestUsage(
            input_tokens=math.ceil(len(self.vistos[-1]) / CARACTERES_POR_TOKEN_DO_FALSO), output_tokens=TOKENS_DE_SAIDA_DO_FALSO
        )
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, argumentos)], usage=uso)


# --- agente -----------------------------------------------------------------------------------------------------------------------------


def ferramenta_falsa(ctx: RunContext[Deps]) -> dict[str, Any]:
    """Lê a oferta ativa (simulação para o dublê): devolve só referências e placeholders, nunca valores."""
    return {"oferta_ref": "oferta-1", "placeholders": ["valor_liberado", "valor_parcela", "prazo"]}


@dataclass(frozen=True)
class AgenteDoTurno:
    """O `Agent` do Pydantic AI + o que `executar_turno` precisa saber: a faixa (nomes que o passo grava), os preços e o tempo."""

    agente: Agent[Deps, Turno]
    modelo: ModeloDaFaixa
    precos: Precos
    timeout_s: float | None
    ferramentas: tuple[str, ...]


def criar_agente(
    provedor: Provedor,
    modelo_faixa: ModeloDaFaixa,
    ferramentas: Mapping[str, Callable[..., Any]] | None = None,
    *,
    settings: Settings | None = None,
    precos: Precos = PRECOS_PADRAO,
    instrumentacao: InstrumentationSettings | None = None,
) -> AgenteDoTurno:
    """`Agent[Deps, Turno]` com a saída por ferramenta e `output_retries=1`. Sem `FallbackModel`: `provedor.resolver` devolve UM modelo.

    Com `settings`, vale o preço e o tempo dele (o tempo total do turno é o de uma chamada vezes as tentativas de saída). A instrumentação
    padrão é a de `observabilidade.configurar` (nenhuma, se não foi configurada).

    `ferramentas` é um mapa `{"T3": função}` e TODA ferramenta passa por `ferramentas.registrar`: o nome precisa ter projeção em
    `PROJECAO_DAS_FERRAMENTAS` (senão `FerramentaSemProjecao`, antes de qualquer chamada) e o retorno só volta ao modelo projetado e
    auditado."""
    tools, capacidades = registrar(ferramentas or {})
    modelo = provedor.resolver(modelo_faixa.modelo, modelo_faixa.provedor, modelo_faixa.raciocinio)
    agente: Agent[Deps, Turno] = Agent(
        modelo,
        output_type=Turno,
        deps_type=Deps,
        tools=tools,
        capabilities=capacidades or None,
        retries={"output": OUTPUT_RETRIES, "tools": RETENTATIVAS_DE_FERRAMENTA},
        name="turno",
    )
    instrumento = instrumentacao or observabilidade.instrumentacao_atual()
    if instrumento is not None:
        agente.instrument = instrumento
    timeout = settings.modelo_timeout_s * (OUTPUT_RETRIES + 1) if settings else None
    return AgenteDoTurno(agente, modelo_faixa, settings.precos() if settings else precos, timeout, tuple(ferramentas or ()))


def _numeros(uso: Any) -> tuple[int, int, int, int]:
    """(entrada total, entrada cacheada, saída, raciocínio) de um `RunUsage`/`RequestUsage`. Raciocínio já está dentro da saída."""
    detalhes = getattr(uso, "details", None) or {}
    raciocinio = max(getattr(uso, "output_reasoning_tokens", 0) or 0, int(detalhes.get("reasoning_tokens", 0) or 0))
    return uso.input_tokens or 0, uso.cache_read_tokens or 0, uso.output_tokens or 0, raciocinio


def _uso_das_mensagens(mensagens: Sequence[ModelMessage]) -> tuple[int, int, int, int]:
    """Soma o uso de todas as respostas do modelo (inclusive a que não virou `Turno`): o que falhou também gastou."""
    totais = [0, 0, 0, 0]
    for mensagem in mensagens:
        if isinstance(mensagem, ModelResponse):
            totais = [a + b for a, b in zip(totais, _numeros(mensagem.usage), strict=True)]
    return totais[0], totais[1], totais[2], totais[3]


def _uso_do_turno(numeros: tuple[int, int, int, int], latencia_ms: int, trace_id: str, precos: Precos) -> UsoDoTurno:
    entrada, cache, saida, raciocinio = numeros
    nao_cacheada = max(entrada - cache, 0)
    return UsoDoTurno(
        tokens_in=nao_cacheada,
        tokens_cache=cache,
        tokens_out=saida,
        tokens_raciocinio=raciocinio,
        custo_brl=custo_brl(tokens_in=nao_cacheada, tokens_cache=cache, tokens_out=saida, precos=precos),
        latencia_ms=latencia_ms,
        trace_id=None if trace_id == observabilidade.TRACE_ID_NULO else trace_id,
    )


def _erro_do_modelo(erro: BaseException, uso: UsoDoTurno) -> ErroDoModelo:
    """Mensagem FIXA (tipo de falha e status): o texto do SDK ou da validação pode citar o corpo da resposta ou a saída do modelo."""
    if isinstance(erro, UnexpectedModelBehavior):
        return SaidaInvalida("saida_invalida", "o modelo não devolveu um Turno válido", uso=uso)
    if isinstance(erro, _ERROS_DE_TEMPO):
        return ProvedorIndisponivel("tempo_esgotado", "o provedor não respondeu a tempo", uso=uso)
    status = erro.status_code if isinstance(erro, ModelHTTPError) else None
    complemento = f" (HTTP {status})" if status else ""
    return ProvedorIndisponivel("provedor", f"o provedor falhou{complemento}", uso=uso, status=status)


def _ferramentas_chamadas(mensagens: Sequence[ModelMessage], nomes: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        parte.tool_name
        for mensagem in mensagens
        if isinstance(mensagem, ModelResponse)
        for parte in mensagem.parts
        if isinstance(parte, ToolCallPart) and parte.tool_name in nomes
    )


def _trazem_raciocinio(mensagens: Sequence[ModelMessage], tokens: int) -> bool:
    return tokens > 0 or any(isinstance(p, ThinkingPart) for m in mensagens if isinstance(m, ModelResponse) for p in m.parts)


async def executar_turno(
    agente: AgenteDoTurno, deps: Deps, contexto: Contexto, *, cronometro: Callable[[], float] = time.perf_counter
) -> ResultadoTurno:
    """Roda UM turno do modelo e devolve `ResultadoTurno` (Turno validado na fase + tokens, `custo_brl`, latência, `trace_id`).

    Levanta `ProvedorIndisponivel`/`SaidaInvalida` (falha do provedor) ou `TurnoForaDaFase` (o modelo pediu o que a fase não permite); as
    duas famílias são `ErroDoModelo` e carregam o gasto em `.uso`. Cada tentativa vale uma falha; o processador conta as 2 (B1.6)."""
    if not isinstance(contexto, Contexto):  # só o que `contexto.construir` monta (e `montar_contexto` audita) chega ao provedor
        raise TypeError("executar_turno recebe o Contexto de contexto.montar_contexto, não texto solto")
    modelo, provedor = agente.modelo.modelo, agente.modelo.provedor
    # o resultado de ferramenta reusa os apelidos do contexto
    deps = replace(deps, apelidos=Apelidos(contexto.referencias))
    with observabilidade.span_do_turno(fase=contexto.fase, modelo=modelo, provedor=provedor) as span:
        trace_id = observabilidade.trace_id_atual()
        inicio = cronometro()
        execucao = None
        capturado: BaseException | None = None
        with capture_run_messages() as mensagens:
            try:
                execucao = await agente.agente.run(contexto.usuario, deps=deps, instructions=contexto.sistema, timeout=agente.timeout_s)
            except _ERROS_DO_PROVEDOR as erro:
                capturado = erro
        latencia_ms = int((cronometro() - inicio) * 1000)
        if execucao is None or capturado is not None:
            uso = _uso_do_turno(_uso_das_mensagens(mensagens), latencia_ms, trace_id, agente.precos)
            span.set_attribute("turno.erro", type(capturado).__name__)
            raise _erro_do_modelo(capturado, uso)  # fora do `except`: sem `__context__`
        numeros = _numeros(execucao.usage)
        uso = _uso_do_turno(numeros, latencia_ms, trace_id, agente.precos)
        historico = execucao.all_messages()
        raciocinio = _trazem_raciocinio(historico, numeros[3])
        if raciocinio:
            observabilidade.alertar_raciocinio(numeros[3], modelo=modelo, provedor=provedor)
        resultado = ResultadoTurno(
            execucao.output, modelo, provedor, uso, _ferramentas_chamadas(historico, agente.ferramentas),
            raciocinio_detectado=raciocinio, referencias=dict(deps.apelidos.mapa),
        )  # fmt: skip
        span.set_attributes(
            {"turno.acao": resultado.turno.acao, "turno.intencao": resultado.turno.intencao, "turno.custo_brl": str(uso.custo_brl)}
        )
        validar_turno_na_fase(contexto.fase, resultado.turno, resultado=replace(resultado, acao_invalida=True))
        return resultado


__all__ = [
    "ACOES_POR_FASE",
    "FERRAMENTAS_DO_MODELO_POR_FASE",
    "PROVEDOR_FIREWORKS_US",
    "TX_DO_MODELO_POR_FASE",
    "AcaoForaDaFase",
    "AgenteDoTurno",
    "Deps",
    "ErroDoModelo",
    "FerramentaForaDaFase",
    "FerramentaPedida",
    "ModeloDaFaixa",
    "Provedor",
    "ProvedorFalso",
    "ProvedorIndisponivel",
    "ProvedorNaoConfigurado",
    "RaciocinioNaoLiberado",
    "ResolvedorModelo",
    "ResultadoTurno",
    "Roteiro",
    "SaidaInvalida",
    "Turno",
    "TurnoForaDaFase",
    "TxForaDaFase",
    "UsoDoTurno",
    "criar_agente",
    "custo_brl",
    "executar_turno",
    "extra_body_raciocinio",
    "ferramenta_falsa",
    "formato_do_turno",
    "validar_turno_na_fase",
]
