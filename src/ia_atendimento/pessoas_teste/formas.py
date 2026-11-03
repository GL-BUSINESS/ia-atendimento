"""Formas medidas (Pydantic estrito) do que as fixtures de `duble|teste` devolvem: 360 (T1/T3), 3RN `/calcular` e C6 `/simular` (B2.4).

Só a FORMA: nomes de campo, tipo, padrão e obrigatoriedade, copiados dos esquemas `Oferta`, `PayloadEconomicoCltV1`, `ParPropostasPessoa`,
`ResultadoPropostasPessoa`, `PessoaResumo` e `ResumosPessoas` de `cliente360.json` (cliente360-api) e dos dicts que `3rn-api`
(`app/routers/consulta.py`, `_calcular`) e `c6-api` (`app/routers/oferta.py`, `simular`) montam. Nenhum valor de cliente: quem produz o
valor é o catálogo sintético (`catalogo.py`). `extra="forbid"` onde o contrato é fechado (`unevaluatedProperties: false`): um campo a mais
ou a menos na fixture reprova, que é o que protege o gateway de uma fixture que "funciona" e diverge da resposta real (PD-6).

O corpo cru da C6 (`simulacao`) é aberto no banco: as condições aceitam campo extra; o envelope do `c6-api` ao redor é fechado.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Uuid = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")]
IdRecurso = Annotated[str, StringConstraints(pattern=r"^[0-9]{1,19}$")]
Instante = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$")]
Data = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]
CodigoBanco = Annotated[str, StringConstraints(pattern=r"^[A-Z0-9_]{2,32}$")]
CodigoProduto = CodigoBanco
DecimalMoeda = Annotated[str, StringConstraints(pattern=r"^-?[0-9]+(\.[0-9]{1,2})?$")]
DecimalSnapshot = Annotated[str, StringConstraints(pattern=r"^[0-9]+(\.[0-9]{1,12})?$")]
Cpf11 = Annotated[str, StringConstraints(pattern=r"^[0-9]{11}$")]
CpfMascarado = Annotated[str, StringConstraints(pattern=r"^\*{3}\.\*{3}\.\*{3}-[0-9]{2}$")]


class _Fechada(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Aberta(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)


# ----------------------------------------------------------------------------------------------------------- 360: T3 (pessoas:propostas)


class PayloadEconomicoCltV1(_Fechada):
    forma: Literal["payload_clt_v1"]
    valor_liberado: DecimalMoeda
    valor_parcela: DecimalMoeda | None = None
    prazo_meses: Annotated[int, Field(ge=0, le=600)]
    tabela_identificador: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    convenio: Annotated[str, StringConstraints(max_length=64)] | None = None
    coeficiente_financeiro: DecimalSnapshot | None = None


class AtributosCadastraisOferta(_Fechada):
    nome: str | None = None
    telefone: str | None = None
    link_chat: str | None = None


class SnapshotCoeficiente(_Fechada):
    """`SnapshotCoeficiente` sem `pct_*` (CF-INV-12): `coef_valor` é a grandeza que ordena o fallback (T3); nunca vai ao modelo."""

    alvo_tipo: Literal["oferta", "contrato"]
    alvo_id: str
    coef_origem: Literal[
        "catalogo",
        "corrigido",
        "pendente",
        "migrado_resolvido_vivo",
        "migrado_fallback_produtor",
        "migrado_sem_coeficiente",
        "migrado_fora_da_pagina",
    ]
    coef_valor: DecimalSnapshot | None = None
    coef_versao_id: int | None = None
    coef_resolvido_em: Instante | None = None
    coef_financeiro: DecimalSnapshot | None = None


class Oferta(_Fechada):
    oferta_id: IdRecurso
    pessoa_id: Uuid
    banco: CodigoBanco
    produto: CodigoProduto
    business_date: Data
    estado: Literal["ativa", "consumida", "encerrada", "superseded"]
    versao: Annotated[int, Field(ge=1)]
    valid_until: Instante
    criada_em: Instante
    ciclo: Annotated[int, Field(ge=1)] | None = None
    ultima_consulta_em: Instante | None = None
    sucede_oferta_id: IdRecurso | None = None
    tipo_operacao: str | None = None
    competencia_inicio: Instante | None = None
    competencia_fim: Instante | None = None
    lead_id: Uuid | None = None
    economia: PayloadEconomicoCltV1 | None = None
    atributos_cadastrais: AtributosCadastraisOferta | None = None
    coeficiente: SnapshotCoeficiente | None = None

    @model_validator(mode="after")
    def _ativa_com_economia(self) -> Oferta:
        if self.estado == "ativa" and self.economia is None:
            raise ValueError("oferta ativa sem economia")
        return self


class AlvoSugerido(_Fechada):
    tipo: Literal["oferta", "contrato"]
    id: IdRecurso


class ParPropostasPessoa(_Fechada):
    banco: CodigoBanco
    produto: CodigoProduto
    caso: Literal["sem_oferta", "so_oferta", "com_contrato", "varios_contratos"]
    contratos: Annotated[list[dict[str, Any]], Field(max_length=0)]  # as fixtures nunca têm contrato vivo (a forma do item é do 360)
    oferta_ativa: Oferta | None = None
    ofertas_outras: list[Oferta] | None = None
    alvo_sugerido: AlvoSugerido | None = None

    @model_validator(mode="after")
    def _caso_coerente(self) -> ParPropostasPessoa:
        if (self.caso == "so_oferta") != (self.oferta_ativa is not None):
            raise ValueError("`so_oferta` ⇔ há oferta ativa (sem contrato vivo nas fixtures)")
        if self.caso not in ("so_oferta", "sem_oferta"):
            raise ValueError("as fixtures só têm os casos sem_oferta e so_oferta")
        return self


class AtribuicaoPropostas(_Fechada):
    versao: Annotated[int, Field(ge=0)] | None = None
    site_profile_id: Uuid | None = None


class ResultadoPropostasPessoa(_Fechada):
    encontrado: bool
    pares: list[ParPropostasPessoa]
    varias_ofertas: bool
    lido_em: Instante
    pessoa_id: Uuid | None = None
    atribuicao: AtribuicaoPropostas | None = None

    @model_validator(mode="after")
    def _forma(self) -> ResultadoPropostasPessoa:
        if not self.encontrado and self.pares:
            raise ValueError("`encontrado:false` devolve `pares` vazio")
        ativas = sum(1 for p in self.pares if p.oferta_ativa is not None)
        if self.varias_ofertas != (ativas > 1):
            raise ValueError("`varias_ofertas` ⇔ oferta ativa em mais de um par")
        return self


# ----------------------------------------------------------------------------------------------------------- 360: T1 (pessoas:resumos)


class NaoPerturbe(_Fechada):
    desde: Instante
    ate: Instante


class LimiteContratos(_Fechada):
    banco: CodigoBanco
    desde: Instante
    visto_em: Instante


class PessoaResumo(_Fechada):
    pessoa_id: Uuid
    nome: str | None
    cpf_mascarado: CpfMascarado
    cpf: Cpf11
    status_atendimento: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{2,64}$")] | None = None
    vendedor: Annotated[str, StringConstraints(max_length=128)] | None = None
    vendedor_ator_id: IdRecurso | None = None
    nao_perturbe: NaoPerturbe | None = None
    limite_contratos: LimiteContratos | None = None


class ResumosPessoas(_Fechada):
    itens: list[PessoaResumo]


# ----------------------------------------------------------------------------------------------------------- 3RN: POST /3rn/calcular


class Calcular3rnCalculado(_Fechada):
    """Sucesso (`consulta.py`, `_calcular`, o `return` final): o recálculo na tabela que a consulta escolheu."""

    success: Literal[True]
    cpf: Cpf11
    fonte_sim: Literal["cache", "online"]
    tabela: str | None
    valorFinanciado: float | None
    valorLiquido: float | None
    parcela: float | None
    prazo: int | None
    coeficiente_tabela: float | None


class Calcular3rnSemCalculo(_Fechada):
    """Não houve cálculo: o passo de vínculos (Step 1) ou o recálculo (Step 2) devolveu um desfecho em vez de valores.

    `SIM_AUSENTE` é o caminho do `nao_repagar` (sem simulação em `trn.sim` a consulta paga NÃO é refeita): `success:false`, `vinculos`.
    `REPROVADO`/`PROCESSANDO`/`ERRO...` vêm do `_step1_sim` (`success:true`, `etapa:vinculos`) ou de `tratar_erro_api` (`success:false`).
    """

    success: bool
    cpf: Cpf11
    status: Literal["SIM_AUSENTE", "REPROVADO", "PROCESSANDO", "ERRO", "ERRO_AUTH", "MARGEM_INSUFICIENTE"]
    motivo: str
    etapa: Literal["vinculos", "calculo"] | None = None
    tabela: str | None = None
    prazoMaximo: int | None = None
    prazosDisponiveis: list[int] | None = None


# ----------------------------------------------------------------------------------------------------------- C6: POST /c6/oferta/simular


class C6Convenio(_Aberta):
    codigo: str | int
    descricao: str | None = None
    observacao: str | None = None


class C6Condicao(_Aberta):
    id_simulacao: str
    valor_cliente: float
    valor_parcela: float
    quantidade_parcelas: Annotated[int, Field(ge=1)]
    convenio: C6Convenio
    coeficiente_tabela: float | None = None


class C6CondicaoCredito(_Aberta):
    condicao: C6Condicao


class C6Simulacao(_Aberta):
    condicoes_credito: list[C6CondicaoCredito]


class C6OpcaoSelecionada(_Fechada):
    """`extrair_opcoes` do `c6-api` (`sim_client.py`) + a anotação `coeficiente_tabela` da governança."""

    id_simulacao: str
    convenio: str | int | None
    convenio_nome: str | None
    prazo: int | None
    valor_parcela: float
    valor_liberado: float
    proibida: bool
    motivo: str | None
    coeficiente_tabela: float | None = None


class C6Simular(_Fechada):
    """Envelope do `/c6/oferta/simular` (`envelope.desfecho` + `_resposta`): `success`, `result`, `cpf`, `fonte`, `custo` e o desfecho."""

    success: bool
    result: Literal["simulado", "sem_oferta", "sem_autorizacao", "simulacao_erro"]
    cpf: Cpf11
    fonte: Literal["online", "circuito"]
    custo: bool
    status: Literal["OK", "REPROVADO", "ERRO"]
    motivo: str
    simulacao: C6Simulacao | None
    condicoes_persistidas: bool
    oferta: None = None
    opcao_selecionada: C6OpcaoSelecionada | None = None
    motivo_banco: str | None = None

    @model_validator(mode="after")
    def _forma(self) -> C6Simular:
        if (self.result == "simulado") != (self.simulacao is not None):
            raise ValueError("`simulado` ⇔ há `simulacao`")
        return self
