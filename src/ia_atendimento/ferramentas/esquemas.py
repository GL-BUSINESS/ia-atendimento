"""Esquemas de entrada e saída do catálogo MVP (estudo F T1–T14; D-29; contexto `PROJECAO_DAS_FERRAMENTAS`).

Todos `extra=forbid`. A ENTRADA é só referência (o código monta valores, CPF e dados a partir do estado, nunca do modelo). A SAÍDA é a
forma que o código guarda depois da reconstrução por allowlist: o que não está aqui é descartado na chegada (`saida.reconstruir`); valores
em reais ficam do lado do código (`Decimal`), e ao modelo só vai a projeção de `PROJECAO_DAS_FERRAMENTAS`. Comissão, `coef_valor`,
`tabela_identificador`, CPF e motivo cru do banco não existem em nenhum esquema (D-29): não há campo onde caibam.

HIPÓTESE (B5.2–B5.4 fixam contra o 360 de dev, as fixtures e o dublê): os campos do lado do código de T1/T3/T5/T7–T9/T13. Mudar qualquer
esquema muda o `catalogo_hash` e pede `numero` novo (`catalogo_versoes.json`).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints

from ia_atendimento.contexto import FASES_DO_T2, FRASES_DO_T10, MACROS_DA_PROPOSTA, PROXIMAS_ACOES_DO_T10, STATUS_DA_OFERTA
from ia_atendimento.turno import PLACEHOLDERS_DO_TEXTO, AlvoPedido


class Fechado(BaseModel):
    """Base de todo esquema do gateway: campo a mais é erro, nada se altera depois de validado e a entrada recusada não vai ao erro."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


RefOferta = Annotated[str, StringConstraints(pattern=r"^oferta-[0-9]{1,2}$")]
RefOpcao = Annotated[str, StringConstraints(pattern=r"^opcao-[0-9]{1,2}$")]
IdOpaco = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.:-]{1,64}$")]  # id real do lado do código (uuid, chave do ledger)
Banco = Literal["FACTA", "3RN", "C6"]
Placeholder = Literal[tuple(sorted(PLACEHOLDERS_DO_TEXTO))]  # type: ignore[valid-type]
FaseDoT2 = Literal[tuple(sorted(FASES_DO_T2))]  # type: ignore[valid-type]
StatusDaOferta = Literal[tuple(sorted(STATUS_DA_OFERTA))]  # type: ignore[valid-type]
MacroDaProposta = Literal[tuple(sorted(MACROS_DA_PROPOSTA))]  # type: ignore[valid-type]
ProximaAcao = Literal[tuple(sorted(PROXIMAS_ACOES_DO_T10))]  # type: ignore[valid-type]
FraseDoT10 = Literal[tuple(sorted(FRASES_DO_T10))]  # type: ignore[valid-type]
Reais = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Prazo = Annotated[int, Field(ge=1, le=240)]
# T6 (D-29): a lista fechada de campos da digitação; `complemento` e `email` não se coletam.
CampoDaDigitacao = Literal[
    "celular",
    "cep",
    "numero",
    "forma_pagamento",
    "tipo_chave_pix",
    "chave_pix",
    "tipo_conta",
    "banco",
    "agencia",
    "conta",
    "conta_digito",
    "agencia_digito",
]


# --- entradas -----------------------------------------------------------------------------------------------------------------------------


class SemArgumentos(Fechado):
    """T1, T2, T10, T13: o código sabe de quem é o atendimento; nada vem do modelo."""


class ArgsOferta(Fechado):
    """T3. Na E2 a oferta ainda não foi mostrada: sem `oferta_ref` (lê a oferta corrente do estado)."""

    oferta_ref: RefOferta | None = None


class ArgsSimulacao(Fechado):
    """T5: a oferta (apelido) e o QUE o cliente quer mudar; o número do pedido é extraído por código (H P3)."""

    oferta_ref: RefOferta
    alvo: AlvoPedido


class ArgsColeta(Fechado):
    """T6 (só código, modo guiado): o valor é a mensagem inteira do cliente, vai ao validador e ao cofre sem passar pelo modelo (B5.3)."""

    campo: CampoDaDigitacao
    valor: Annotated[SecretStr, Field(max_length=80)]


class ArgsDigitacao(Fechado):
    """T7 (só código): a confirmação aceita é a âncora; oferta, valores, dados e vendedor saem do estado e do cofre (B5.4)."""

    confirmacao_id: IdOpaco


class ArgsTentativa(Fechado):
    """T8/T9 (só código): a tentativa de digitação do ledger."""

    tentativa_ref: IdOpaco


class ArgsOptOut(Fechado):
    """T14 (só código): o tipo do registro; a mensagem que o motivou fica no passo, não aqui."""

    tipo: Literal["opt_out", "nao_perturbe"]


# --- saídas -------------------------------------------------------------------------------------------------------------------------------


class SaidaT1(Fechado):
    """T1 (`pessoas:resumos`, D-29): ao código só isto. O CPF fica na memória do gateway, nunca aqui."""

    encontrado: bool
    primeiro_nome: Annotated[str, StringConstraints(min_length=1, max_length=40)] | None = None
    nao_perturbe: bool = False
    limite_contratos: bool = False


class SaidaT2(Fechado):
    fase: FaseDoT2
    etapa: FaseDoT2 | None = None
    contrato_vivo: bool = False
    proposta_viva: bool = False
    degradado: bool = False


class SaidaT3(Fechado):
    """T3 (`pessoas:propostas`): a oferta corrente. Valores só do lado do código; `coef_valor` e comissão não existem aqui."""

    oferta_ref: IdOpaco | None = None
    status: StatusDaOferta
    versao: Annotated[int, Field(ge=1, le=99)] | None = None
    vencida: bool = False
    mudou: bool = False
    placeholders: tuple[Placeholder, ...] = ()
    banco: Banco | None = None
    valor_liberado: Reais | None = None
    valor_parcela: Reais | None = None
    prazo: Prazo | None = None
    valid_until: datetime | None = None


class OpcaoT5(Fechado):
    opcao_ref: IdOpaco
    dentro_da_alcada: bool
    placeholders: tuple[Placeholder, ...] = ()
    valor_liberado: Reais | None = None
    valor_parcela: Reais | None = None
    prazo: Prazo | None = None


class SaidaT5(Fechado):
    opcoes: Annotated[tuple[OpcaoT5, ...], Field(max_length=5)] = ()
    sem_opcao: bool = False
    acima_do_maximo: bool = False


class SaidaT6(Fechado):
    """`{valido, motivo_classe, faltam[]}`: nunca ecoa o valor (B5.3)."""

    valido: bool
    motivo_classe: Literal["formato", "tamanho", "digito", "banco_nao_aceita", "vazio"] | None = None
    faltam: tuple[CampoDaDigitacao, ...] = ()


class SaidaT7(Fechado):
    """Classe do resultado da digitação (B2.3/B5.4). `indeterminado` nunca reenvia: vai ao T8."""

    classe: Literal["criada", "corrigivel", "recusa", "indeterminado", "transitorio", "em_andamento"]
    ref_externa: IdOpaco | None = None


class SaidaT8(Fechado):
    estado: Literal["criada", "nao_criada", "aguardando", "indeterminado"]
    ref_externa: IdOpaco | None = None


class SaidaT9(Fechado):
    """O link fica do lado do código; ao cliente ele sai pelo placeholder `{{link}}` do texto fixo."""

    disponivel: bool
    link: Annotated[str, StringConstraints(pattern=r"^https://[A-Za-z0-9.-]{1,253}(/[A-Za-z0-9._~%/?#=&+-]{0,400})?$")] | None = None


class SaidaT10(Fechado):
    macro: MacroDaProposta
    proxima_acao: ProximaAcao | None = None
    frase_ref: FraseDoT10 | None = None


class EstadoDoBanco(Fechado):
    banco: Banco
    disponivel: bool
    degradado: bool = False


class SaidaT13(Fechado):
    bancos: Annotated[tuple[EstadoDoBanco, ...], Field(max_length=3)] = ()
    janela_dataprev: bool = False


class SaidaT14(Fechado):
    registrado: bool
