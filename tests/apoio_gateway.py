"""Apoio dos testes do gateway de ferramentas (B5.1): catálogo, destinos e um gateway montado com executores espiões.

Dados sintéticos: CPF da faixa `000.000.0nn`, hosts `.test` (RFC 2606), ids de oferta inventados com forma de uuid.
"""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from ia_atendimento.contexto import Apelidos
from ia_atendimento.ferramentas.catalogo import CATALOGO_MVP, Catalogo
from ia_atendimento.ferramentas.gateway import Chamada, ContextoDaChamada, Gateway, Referencia
from ia_atendimento.ferramentas.modo import BasesDoServico, Destinos, LeitorDeModo
from ia_atendimento.ferramentas.segredo import CpfEmMemoria
from ia_atendimento.relogio import RelogioFalso

CPF = "000.000.012-34"
CPF_DIGITOS = "00000001234"
FACTA_PROD = "https://facta-on.producao.test"
FACTA_DUBLE = "https://duble-facta.vps.test"
C360_PROD = "https://api-360.producao.test"
PRODUCAO = (FACTA_PROD, C360_PROD, "https://trn.producao.test", "https://c6.producao.test")
ATENDIMENTO = uuid.UUID(int=101)
OUTRO_ATENDIMENTO = uuid.UUID(int=202)
PESSOA = uuid.UUID(int=303)
OFERTA_REAL = "0194a8b0-2f7e-4c3a-9d41-6b1f0c2e7a55"
OFERTA_DE_OUTRO = "0194a8b0-2f7e-4c3a-9d41-6b1f0c2e7a99"
CONFIRMACAO = "0194a8b0-2f7e-4c3a-9d41-6b1f0c2e7c01"
INICIO = datetime(2026, 11, 10, 12, tzinfo=UTC)
RETORNO_T3_CRU: dict[str, Any] = {
    "oferta_ref": OFERTA_REAL,
    "status": "ativa",
    "versao": 2,
    "placeholders": ["valor_liberado", "valor_parcela", "prazo"],
    "banco": "FACTA",
    "valor_liberado": "5000.00",
    "valor_parcela": "312.45",
    "prazo": 36,
    "cpf": CPF,
    "coef_valor": "0.0613",
    "comissao": "410.00",
    "tabela_identificador": "TAB-0001",
    "link_formalizacao": "https://assina.exemplo.test/abc",
    "motivo_texto": "reprovado por margem de 1.234,56",
}


def destinos() -> Destinos:
    return Destinos(
        {
            "facta": BasesDoServico(producao=FACTA_PROD, teste=FACTA_DUBLE),
            "c360": BasesDoServico(producao=C360_PROD),
            "trn": BasesDoServico(producao=PRODUCAO[2]),
            "c6": BasesDoServico(producao=PRODUCAO[3]),
        }
    )


def contexto(modo: str = "real", *, posse_real: bool = False, apelidos: Mapping[str, str] | None = None) -> ContextoDaChamada:
    return ContextoDaChamada(
        atendimento_id=ATENDIMENTO,
        pessoa_id=PESSOA,
        atendimento_modo=modo,
        posse_real=posse_real,
        apelidos=Apelidos(apelidos if apelidos is not None else {"oferta-1": OFERTA_REAL}),
    )


def referencias_do_atendimento(atendimento_id: uuid.UUID, campo: str, real: str) -> Referencia | None:
    """O estado do atendimento 101: uma oferta FACTA e uma confirmação. Qualquer outro id (ou outro atendimento) não é dele."""
    if atendimento_id != ATENDIMENTO:
        return None
    if campo == "oferta_ref" and real == OFERTA_REAL:
        return Referencia(real, banco="FACTA")
    if campo == "confirmacao_id" and real == CONFIRMACAO:
        return Referencia(real, banco="FACTA")
    return None


async def ler_cpf(pessoa_id: uuid.UUID) -> CpfEmMemoria | None:
    return CpfEmMemoria(CPF) if pessoa_id == PESSOA else None


@dataclasses.dataclass
class Espiao:
    """Executor que registra o que recebeu e devolve `retorno` (ou o que `comportamento` devolver)."""

    retorno: Mapping[str, Any] | None = None
    comportamento: Callable[[Chamada], Awaitable[Any]] | None = None
    chamadas: list[Chamada] = dataclasses.field(default_factory=list)

    async def __call__(self, chamada: Chamada) -> Any:
        self.chamadas.append(chamada)
        if self.comportamento is not None:
            return await self.comportamento(chamada)
        return dict(self.retorno or {})


def todas_as_precondicoes_valem() -> dict[str, Callable[..., bool]]:
    from ia_atendimento.ferramentas.erros import PRECONDICOES

    return {nome: (lambda pedido: True) for nome in PRECONDICOES}


def gateway(
    *,
    executores: Mapping[str, Any] | None = None,
    simuladores: Mapping[str, Any] | None = None,
    config_modo: Callable[[], str] = lambda: "real",
    relogio: RelogioFalso | None = None,
    catalogo: Catalogo = CATALOGO_MVP,
    **opcoes: Any,
) -> Gateway:
    relogio = relogio or RelogioFalso(INICIO)
    opcoes.setdefault("referencias", referencias_do_atendimento)
    opcoes.setdefault("leitor_de_cpf", ler_cpf)
    opcoes.setdefault("precondicoes", todas_as_precondicoes_valem())
    opcoes.setdefault("bancos_ligados", lambda flag: ("FACTA",))
    return Gateway(
        catalogo,
        destinos(),
        LeitorDeModo(config_modo, relogio),
        executores or {},
        simuladores=simuladores or {},
        **opcoes,
    )
