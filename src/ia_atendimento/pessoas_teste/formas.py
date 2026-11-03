"""Formas medidas (Pydantic estrito) do que as fixtures de `duble|teste` devolvem: 360 (T1/T3), 3RN `/calcular` e C6 `/simular` (B2.4).

Só a FORMA: nomes de campo, tipo, padrão e obrigatoriedade, copiados dos esquemas `Oferta`, `PayloadEconomicoCltV1`, `ParPropostasPessoa`,
`ResultadoPropostasPessoa`, `PessoaResumo` e `ResumosPessoas` de `cliente360.json` (cliente360-api) e dos dicts que `3rn-api`
(`app/routers/consulta.py`, `_calcular`) e `c6-api` (`app/routers/oferta.py`, `simular`) montam. Nenhum valor de cliente: quem produz o
valor é o catálogo sintético (`catalogo.py`). `extra="forbid"` onde o contrato é fechado (`unevaluatedProperties: false`): um campo a mais
ou a menos na fixture reprova, que é o que protege o gateway de uma fixture que "funciona" e diverge da resposta real (PD-6).

O corpo cru da C6 (`simulacao`) é aberto no banco: as condições aceitam campo extra; o envelope do `c6-api` ao redor é fechado.
"""

from __future__ import annotations

from typing import Annotated, Literal

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
    business_date_origem: Literal["medida", "imputada"] | None = None
    superseded_causa: str | None = None
    motivo_encerramento: str | None = None
    motivo_encerramento_texto: str | None = None
    competencia_inicio: Instante | None = None
    competencia_fim: Instante | None = None
    origem: str | None = None
    lead_id: Uuid | None = None
    economia: PayloadEconomicoCltV1 | None = None
    atributos_cadastrais: AtributosCadastraisOferta | None = None
    coeficiente: SnapshotCoeficiente | None = None

    @model_validator(mode="after")
    def _forma_da_projecao(self) -> Oferta:
        """A projeção real (`projetar_oferta`) SEMPRE emite as chaves abaixo (`null` sem valor): a fixture não as omite."""
        if self.estado == "ativa" and self.economia is None:
            raise ValueError("oferta ativa sem economia")
        sempre = {
            "business_date_origem", "superseded_causa", "motivo_encerramento", "motivo_encerramento_texto",
            "competencia_inicio", "competencia_fim", "origem", "lead_id", "atributos_cadastrais", "coeficiente",
        }  # fmt: skip
        if sempre - self.model_fields_set:
            raise ValueError(f"a projeção real sempre emite estas chaves: {sorted(sempre - self.model_fields_set)}")
        return self


class AlvoSugerido(_Fechada):
    tipo: Literal["oferta", "contrato"]
    id: IdRecurso


OPCIONAIS_DO_CONTRATO = frozenset({
    "tipo_operacao", "oferta_id", "adocao", "refinamento", "status_nativo_codigo", "status_nativo_texto", "confianca",
    "motivo", "motivo_texto", "flags", "adicional", "valor_pago", "valor_contratado", "valor_financiado", "codigo_tabela",
    "prazo_meses", "valor_parcela", "valor_pre_aprovado", "pago_em", "coeficiente", "fundida_em_id", "substitui_contrato_id",
    "atualizada_em", "vendedor_efetivo", "link_formalizacao", "data_contratacao_negocio",
})  # fmt: skip
MACROS_TERMINAIS = frozenset({"pago", "cancelado", "estornado"})


class Contrato(BaseModel):
    """`Contrato` do 360: os obrigatórios do esquema, mais os opcionais que o contrato declara (qualquer outro nome é recusado)."""

    model_config = ConfigDict(extra="allow", frozen=True)

    contrato_id: IdRecurso
    pessoa_id: Uuid
    banco: CodigoBanco
    produto: CodigoProduto
    referencia_banco: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    origem_contratacao: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{2,64}$")]
    macro: Literal["pendente", "em_analise", "aguardando_pagamento", "pago", "cancelado", "estornado"]
    pacote_versao: Annotated[int, Field(ge=1)]
    versao: Annotated[int, Field(ge=1)]
    criada_em: Instante

    @model_validator(mode="after")
    def _so_campo_do_contrato(self) -> Contrato:
        fora = set(self.model_extra or {}) - OPCIONAIS_DO_CONTRATO
        if fora:
            raise ValueError(f"campo fora do contrato do 360 (Contrato): {sorted(fora)}")
        return self

    @property
    def vivo(self) -> bool:
        """`contrato_banco_ref_vivo`: nem fundido nem cancelado."""
        return self.macro != "cancelado" and (self.model_extra or {}).get("fundida_em_id") is None


class ContratoNaFoto(_Fechada):
    contrato: Contrato
    terminal: bool
    consome_oferta_ativa: bool

    @model_validator(mode="after")
    def _terminal_e_pelo_macro(self) -> ContratoNaFoto:
        if self.terminal != (self.contrato.macro in MACROS_TERMINAIS):
            raise ValueError("`terminal` ⇔ macro pago, cancelado ou estornado")
        return self


class ParPropostasPessoa(_Fechada):
    """Um par (banco × produto). No 360 real o par só NASCE de uma oferta ativa ou de um contrato (`pessoas_propostas`:
    `ofertas_visiveis + contratos`): «sem oferta» é o par AUSENTE; `sem_oferta` só aparece com contratos todos mortos (cancelados)
    e sem oferta ativa. O `caso` é função pura do estado (`_classificar_par`), conferido aqui."""

    banco: CodigoBanco
    produto: CodigoProduto
    caso: Literal["sem_oferta", "so_oferta", "com_contrato", "varios_contratos"]
    contratos: list[ContratoNaFoto]
    oferta_ativa: Oferta | None = None
    ofertas_outras: list[Oferta] | None = None
    alvo_sugerido: AlvoSugerido | None = None

    @model_validator(mode="after")
    def _caso_coerente(self) -> ParPropostasPessoa:
        if self.oferta_ativa is None and not self.contratos:
            raise ValueError("par sem oferta ativa e sem contrato não existe no 360: o par é AUSENTE")
        vivos = [c.contrato for c in self.contratos if c.contrato.vivo]
        if len(vivos) >= 2:
            esperado, alvo = "varios_contratos", None
        elif len(vivos) == 1:
            esperado, alvo = "com_contrato", AlvoSugerido(tipo="contrato", id=vivos[0].contrato_id)
        elif self.oferta_ativa is not None:
            esperado, alvo = "so_oferta", AlvoSugerido(tipo="oferta", id=self.oferta_ativa.oferta_id)
        else:
            esperado, alvo = "sem_oferta", None
        if self.caso != esperado:
            raise ValueError(f"`caso` incoerente com o estado do par: esperado {esperado!r}")
        if self.alvo_sugerido != alvo:
            raise ValueError("`alvo_sugerido` incoerente com o caso")
        id_ativa = self.oferta_ativa.oferta_id if self.oferta_ativa else None
        for c in self.contratos:
            if c.consome_oferta_ativa != (id_ativa is not None and (c.contrato.model_extra or {}).get("oferta_id") == id_ativa):
                raise ValueError("`consome_oferta_ativa` ⇔ o contrato nasceu da oferta ativa do par")
        return self


class AtribuicaoPropostas(_Fechada):
    """`projetar_atribuicao`: pessoa SEM atribuição sai `{versao: 0, site_profile_id: null}` (o `esperado` do primeiro handoff)."""

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
        if {"pessoa_id", "atribuicao"} - self.model_fields_set:
            raise ValueError("a rota real SEMPRE emite `pessoa_id` e `atribuicao` (`null` quando a pessoa não foi encontrada)")
        if not self.encontrado and (self.pares or self.pessoa_id is not None or self.atribuicao is not None):
            raise ValueError("`encontrado:false` devolve `pares` vazio e `pessoa_id`/`atribuicao` nulos")
        if self.encontrado and (self.pessoa_id is None or self.atribuicao is None or self.atribuicao.versao is None):
            raise ValueError("`encontrado:true` traz `pessoa_id` e `atribuicao {versao, site_profile_id}`")
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
    """Sucesso (`consulta.py`, `_calcular`, o `return` final): o recálculo na tabela que a consulta escolheu.

    No modo da IA (`nao_repagar: true`) a resposta ECOA `"nao_repagar": true` (`_ecoar_nao_repagar`: «a prova, para o chamador, de que ESTE
    3rn-api entendeu o campo»); com outra tabela ou taxa ecoa também `regra_id`, `taxa_pedida` e `taxa` (a que a AJIN devolveu).
    """

    success: Literal[True]
    cpf: Cpf11
    fonte_sim: Literal["cache", "online"]
    tabela: str | None
    valorFinanciado: float | None
    valorLiquido: float | None
    parcela: float | None
    prazo: int | None
    coeficiente_tabela: float | None
    nao_repagar: Literal[True] | None = None
    regra_id: str | None = None
    taxa_pedida: float | None = None
    taxa: float | None = None


class Calcular3rnSemCalculo(_Fechada):
    """Não houve cálculo: o recálculo (Step 2) ou a validação do prazo devolveu um desfecho em vez de valores.

    No modo da IA (`nao_repagar: true`, o único em que as fixtures existem) o passo de vínculos (Step 1) NUNCA roda online, então:
    `SIM_AUSENTE` (sem simulação em `trn.sim` a consulta paga NÃO é refeita): `success:false`, `etapa:"vinculos"`; prazo fora da tabela ou
    acima do teto do vínculo: `success:false`, `status:"REPROVADO"` com `tabela`, `prazoMaximo` e `prazosDisponiveis`, SEM `etapa`; erro do
    Step 2 (`tratar_erro_api`): `etapa:"calculo"` e `success:false` (`PROCESSANDO` na falha de rede é `success:true`). Todas ecoam
    `"nao_repagar": true`.
    """

    success: bool
    cpf: Cpf11
    status: Literal["SIM_AUSENTE", "REPROVADO", "PROCESSANDO", "ERRO", "ERRO_AUTH"]
    motivo: str
    etapa: Literal["vinculos", "calculo"] | None = None
    tabela: str | None = None
    prazoMaximo: int | None = None
    prazosDisponiveis: list[int] | None = None
    nao_repagar: Literal[True] | None = None

    @model_validator(mode="after")
    def _forma_real(self) -> Calcular3rnSemCalculo:
        if self.status == "SIM_AUSENTE" and (self.success or self.etapa != "vinculos"):
            raise ValueError("SIM_AUSENTE é `success:false` na etapa `vinculos`")
        if self.prazosDisponiveis is not None and self.status != "REPROVADO":
            raise ValueError("`prazosDisponiveis` só acompanha o REPROVADO de prazo fora da tabela")
        return self


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
