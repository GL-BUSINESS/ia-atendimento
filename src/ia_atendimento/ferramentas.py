"""Ferramentas registradas no `Agent` (B1.4, achado A-1 da revisão): NENHUM retorno de ferramenta volta ao modelo sem a projeção.

O retorno de uma ferramenta REAL (T2, T3, T5, T10 pelo gateway, B5) é do mundo de fora: traz valores, CPF, coeficiente, comissão e
motivo cru do banco.
`criar_agente` só aceita ferramentas por este registro, que:

1. exige que o nome da ferramenta esteja em `PROJECAO_DAS_FERRAMENTAS` (a allowlist de chaves e folhas); sem projeção declarada o
agente nem sobe
   (`FerramentaSemProjecao`);
2. passa TODO retorno por `projetar_resultado` (só as chaves da allowlist, ids viram apelidos, folhas por regra) num
`AbstractCapability` do Pydantic AI
   (`after_tool_execute`), que roda depois de qualquer função e antes de a mensagem de ferramenta ser montada;
3. audita o que sobrou com a mesma máscara do prompt (com os nomes da conversa) e, se algo ainda casar, levanta
`ContextoComDadoPessoal` (é `ErroDoModelo`);
4. troca a mensagem de um `ModelRetry` da ferramenta por texto fixo: a mensagem iria ao modelo e pode citar o dado que falhou.

Os apelidos novos (`opcao-2`...) entram no mesmo mapa do contexto (`Deps.apelidos`), que o processador (B1.6) lê para voltar aos ids reais.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final
from uuid import UUID

from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.exceptions import ToolFailed, ToolFailedError, ToolRetryError
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.tools import Tool, ToolDefinition

from ia_atendimento.contexto import PROJECAO_DAS_FERRAMENTAS, Apelidos, auditar_textos, projetar_resultado
from ia_atendimento.turno import ErroDoModelo

MENSAGEM_DE_NOVA_TENTATIVA: Final = "A ferramenta não conseguiu responder agora; siga sem ela."


@dataclass(frozen=True)
class Deps:
    """O que as ferramentas recebem do turno. Sem CPF e sem `cpf_hash`: o CPF só existe em memória no gateway (D18).

    `nomes` (nome do cliente e variantes) e `apelidos` servem só para proteger o retorno das ferramentas; nenhum dos dois vai ao modelo
    nem ao `repr`.
    `executar_turno` troca `apelidos` por um mapa semeado com o do contexto."""

    atendimento_id: UUID
    pessoa_id: UUID
    nomes: tuple[str, ...] = field(default=(), repr=False)
    apelidos: Apelidos = field(default_factory=Apelidos, repr=False, compare=False)


class FerramentaSemProjecao(ValueError):
    """Ferramenta registrada sem projeção em `PROJECAO_DAS_FERRAMENTAS` (ou fora do formato do registro): o agente não sobe."""


class RetornoDeFerramentaInvalido(ErroDoModelo, TypeError):
    """O retorno da ferramenta não é um objeto (mapa): não há como projetar. A mensagem nunca cita o retorno. Conta como falha do turno."""

    def __init__(self, nome: str) -> None:
        ErroDoModelo.__init__(self, "retorno_de_ferramenta_invalido", f"a ferramenta {nome} deve devolver um objeto")


def proteger_retorno(nome: str, retorno: Any, deps: Deps) -> dict[str, Any]:
    """Projeta o retorno da ferramenta `nome` pela allowlist, audita o que sobrou e devolve só o que pode ir ao modelo."""
    if not isinstance(retorno, Mapping):
        raise RetornoDeFerramentaInvalido(nome)
    projetado = projetar_resultado({nome: retorno}, deps.apelidos, deps.nomes)
    corpo: dict[str, Any] = json.loads(projetado)[nome] if projetado else {}
    auditar_textos("", json.dumps(corpo, ensure_ascii=False), deps.nomes)
    return corpo


@dataclass
class ProjecaoDeFerramentas(AbstractCapability[Deps]):
    """Capability: o retorno de toda função registrada passa por `proteger_retorno` antes de voltar ao modelo."""

    nomes: frozenset[str]

    @classmethod
    def get_serialization_name(cls) -> str | None:
        return None

    async def after_tool_execute(
        self, ctx: RunContext[Deps], *, call: ToolCallPart, tool_def: ToolDefinition, args: Any, result: Any
    ) -> Any:
        if tool_def.name not in self.nomes:
            raise FerramentaSemProjecao(f"ferramenta {tool_def.name} sem projeção declarada")
        return proteger_retorno(tool_def.name, result, ctx.deps)

    async def wrap_tool_execute(
        self, ctx: RunContext[Deps], *, call: ToolCallPart, tool_def: ToolDefinition, args: Any, handler: Any
    ) -> Any:
        """O texto de um `ModelRetry`/`ToolFailed` da ferramenta é lido pelo modelo e pode citar o dado que falhou: vai um texto fixo "
        "no lugar."""
        try:
            return await handler(args)
        except ToolRetryError:
            raise ModelRetry(MENSAGEM_DE_NOVA_TENTATIVA) from None
        except ToolFailedError:
            raise ToolFailed(MENSAGEM_DE_NOVA_TENTATIVA) from None


def registrar(ferramentas: Mapping[str, Callable[..., Any]]) -> tuple[list[Tool[Deps]], list[AbstractCapability[Deps]]]:
    """`{"T3": funcao}` → as `Tool` (com o nome do catálogo) e a capability que protege o retorno. Nome sem projeção ⇒ "
    "`FerramentaSemProjecao`."""
    if not isinstance(ferramentas, Mapping):
        raise FerramentaSemProjecao("ferramentas deve ser um mapa {nome do catálogo: função}, como {'T3': oferta_ativa}")
    sem = sorted(n for n in ferramentas if n not in PROJECAO_DAS_FERRAMENTAS)
    if sem:
        raise FerramentaSemProjecao(f"ferramenta sem projeção em PROJECAO_DAS_FERRAMENTAS: {', '.join(sem)}")
    if not ferramentas:
        return [], []
    tools = [Tool(funcao, name=nome) for nome, funcao in ferramentas.items()]
    return tools, [ProjecaoDeFerramentas(frozenset(ferramentas))]
