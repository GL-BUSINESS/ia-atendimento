"""Os 13 tipos de passo da linha do tempo (B1.2, sp01 T4): uma classe Pydantic por tipo + `texto_passo`.

Cada classe carrega exatamente os campos que o CHECK do tipo exige ou permite (`extra="forbid"`: campo que o CHECK proíbe é recusado
antes de chegar ao banco, que é a segunda cerca). Todas usam `hide_input_in_errors=True`; `criar` troca o `ValidationError` por um
`EntradaInvalida` sem o valor (ver `scrubber`).

`texto_passo` é determinístico, em pt-BR, e **nunca cita o cliente**: só códigos, rótulos fixos e números (tamanho, versão). A exceção é
a `anotacao_operador`, cujo texto é do OPERADOR (não do cliente) e passa pela mesma rejeição de PII dos textos livres (contrato 08 §5.4).
`colunas()` devolve as colunas de `ia.passo` além de `texto`, `turno` e `fase`, que a `linha_tempo` acrescenta.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Collection
from contextvars import ContextVar
from decimal import Decimal
from typing import Annotated, Any, ClassVar, Final, Literal
from uuid import UUID

from pydantic import AfterValidator, AwareDatetime, Field, StringConstraints, model_validator

from ia_atendimento.mascara import mascarar
from ia_atendimento.scrubber import ModeloSemEco

MOTIVO_PADRAO: Final = "nao_informado"  # decisão sem motivo: o turno segue (H §2.2)
# `passo` vive 365 d e é lido por `ia_leitura`: o motivo do modelo é CÓDIGO de catálogo, nunca texto (achado A1).
LIMITE_NOTA: Final = 240  # «Anotação (» 10 + resultado 40 + «): » 3 + nota 240 = 293 ≤ 300 do CHECK (achado M7)
LIMITE_VERIF_DET: Final = 10

# Nomes da conversa durante a construção de um passo. Não é `context=` do Pydantic porque o construtor sobrescrito de `ModeloSemEco`
# (A2) faz o Pydantic chamar `__init__` sem contexto; a variável de contexto vale só dentro de `criar` e é por tarefa/thread.
_NOMES: ContextVar[Collection[str] | None] = ContextVar("nomes_da_conversa", default=None)


MAX_DIGITOS_EM_CODIGO: Final = 3  # «fila_v2», «t7»; uma corrida de 4+ dígitos pode ser CPF, conta ou telefone


def _codigo_sem_pii(valor: str) -> str:
    """Código de passo (`^[a-z0-9_]+$`) que o regex deixaria carregar PII: corrida de 4+ dígitos, CPF/telefone/e-mail ou nome da conversa.
    Enquanto o catálogo fechado não existe (B1.4/B5), é a cerca de `intencao`, `objecao`, `transversal`, `peca`… (R2-2)."""
    if re.search(rf"[0-9]{{{MAX_DIGITOS_EM_CODIGO + 1},}}", valor):
        raise ValueError("código com 4 ou mais dígitos seguidos")
    legivel = valor.replace("_", " ")
    if mascarar(legivel, _NOMES.get() or ()) != legivel:
        raise ValueError("código com dado pessoal")
    return valor


Codigo40 = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,40}$"), AfterValidator(_codigo_sem_pii)]
Codigo60 = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,60}$"), AfterValidator(_codigo_sem_pii)]
# Motivo da decisão: LISTA FECHADA (A1/R2-2). `passo` vive 365 d e é lido por `ia_leitura`: nenhuma palavra do cliente cabe aqui.
MOTIVOS_DE_DECISAO: Final = (
    "nao_informado", "oferta_aceita", "oferta_recusada", "cliente_concordou", "cliente_desistiu", "pede_humano", "pede_parar",
    "duvida_respondida", "objecao_tratada", "sem_avanco", "fora_de_escopo", "confirmacao_valida", "confirmacao_ambigua",
    "dado_faltante", "janela_encerrada",
)  # fmt: skip
MotivoDecisao = Literal[
    "nao_informado", "oferta_aceita", "oferta_recusada", "cliente_concordou", "cliente_desistiu", "pede_humano", "pede_parar",
    "duvida_respondida", "objecao_tratada", "sem_avanco", "fora_de_escopo", "confirmacao_valida", "confirmacao_ambigua",
    "dado_faltante", "janela_encerrada",
]  # fmt: skip
Hex16 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{16}$")]
Hex32 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]
Hex64 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Semver = Annotated[str, StringConstraints(pattern=r"^[0-9]{1,3}[.][0-9]{1,3}[.][0-9]{1,3}$")]
TxId = Annotated[str, StringConstraints(pattern=r"^TX-(M)?[0-9]{2}$")]
NomeModelo = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._/-]{0,79}$")]
NomeProvedor = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_-]{1,30}$")]
_PADRAO_MSG_CHAVE = r"^(cg:[A-Za-z0-9]{8,64}:[0-9a-f]{16}|cgid:[A-Za-z0-9_.=-]{1,120}|rpa:[A-Za-z0-9_-]{8,64})$"
MsgChave = Annotated[str, StringConstraints(pattern=_PADRAO_MSG_CHAVE)]
MsgChaveRpa = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{8,64}$")]
Confianca = Literal["alta", "media", "baixa"]
Faixa = Literal["baixa", "media", "alta", "muito_alta"]
Entrega = Literal["aceito", "falhou", "rascunho"]
Desfecho = Literal[
    "sem_venda", "repassado", "sem_resposta", "expirado", "opt_out", "abortado", "vendeu", "destravou", "motivo_identificado"
]
Dinheiro = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=6)]


class DadosPasso(ModeloSemEco):
    """Base dos 13 tipos. `tipo` é a constante de classe que vai para a coluna `tipo`."""

    tipo: ClassVar[str]

    def colunas(self) -> dict[str, Any]:
        """Colunas de `ia.passo` (além de `texto`, `turno` e `fase`)."""
        raise NotImplementedError


class MensagemRecebida(DadosPasso):
    tipo: ClassVar[str] = "mensagem_recebida"
    msg_chave: MsgChave
    msg_fingerprint: Hex64
    msg_tipo: Literal["texto", "audio", "imagem", "documento", "sticker", "localizacao", "outro"]
    msg_tamanho: Annotated[int, Field(ge=0)]
    origem_evento: Literal["webhook", "reconciliacao", "replay"]
    msg_enviada_em: AwareDatetime | None = None
    msg_chave_rpa: MsgChaveRpa | None = None
    fora_de_ordem: bool = False

    def colunas(self) -> dict[str, Any]:
        return self.model_dump()


class DecisaoModelo(DadosPasso):
    tipo: ClassVar[str] = "decisao"
    motor: Literal["modelo"] = "modelo"
    intencao: Codigo40
    confianca: Confianca
    objecao: Codigo40 | None = None
    acao_invalida: bool = False
    transversal: Codigo40 | None = None
    faixa_esforco: Faixa | None = None
    modelo: NomeModelo
    provedor: NomeProvedor
    tokens_entrada: Annotated[int, Field(ge=0)] | None = None
    tokens_saida: Annotated[int, Field(ge=0)] | None = None
    custo_brl: Dinheiro | None = None
    latencia_ms: Annotated[int, Field(ge=0)] | None = None
    trace_id: Hex32 | None = None
    motivo: MotivoDecisao | None = None

    def colunas(self) -> dict[str, Any]:
        return {**self.model_dump(), "motivo": self.motivo or MOTIVO_PADRAO}


class DecisaoRegra(DadosPasso):
    tipo: ClassVar[str] = "decisao"
    motor: Literal["regra", "motor_escolha"]
    transversal: Codigo40 | None = None
    faixa_esforco: Faixa | None = None
    trace_id: Hex32 | None = None
    motivo: MotivoDecisao | None = None

    def colunas(self) -> dict[str, Any]:
        return {**self.model_dump(), "motivo": self.motivo or MOTIVO_PADRAO}


class ChamadaFerramenta(DadosPasso):
    tipo: ClassVar[str] = "chamada_ferramenta"
    ferramenta: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,39}$")]
    ferramenta_versao: Semver
    chamada_id: Annotated[int, Field(ge=1)] | None = None
    confirmacao_ref: Hex16 | None = None
    resultado: Codigo40 | None = None
    latencia_ms: Annotated[int, Field(ge=0)] | None = None
    custo_brl: Dinheiro | None = None
    trace_id: Hex32 | None = None

    @model_validator(mode="after")
    def _efeito_pago_so_com_confirmacao(self) -> ChamadaFerramenta:
        if self.ferramenta in ("t4", "t7") and self.confirmacao_ref is None:
            raise ValueError("t4 e t7 só com confirmacao_ref (efeito pago exige confirmação)")
        return self

    def colunas(self) -> dict[str, Any]:
        return self.model_dump()


class Confirmacao(DadosPasso):
    tipo: ClassVar[str] = "confirmacao"
    confirmacao_id: UUID
    confirmacao_ref: Hex16
    resultado: Literal["pergunta", "sim_valido", "ambiguo", "recusada", "expirada", "invalidada"]
    invalidacao: Codigo40 | None = None

    @model_validator(mode="after")
    def _invalidacao_se_e_so_se_invalidada(self) -> Confirmacao:
        if (self.resultado == "invalidada") != (self.invalidacao is not None):
            raise ValueError("invalidacao existe se e somente se o resultado é «invalidada»")
        return self

    def colunas(self) -> dict[str, Any]:
        return self.model_dump()


class _Envio(DadosPasso):
    """`resposta_enviada` e `lembrete`: `verif_det` é OBRIGATÓRIO (`[]` = limpo); sem ele o envio é recusado (L G6)."""

    entrega: Entrega
    verif_det: Annotated[list[Codigo40], Field(max_length=LIMITE_VERIF_DET)]
    tx_id: TxId | None = None
    responde_ordem: Annotated[int, Field(ge=1)] | None = None
    latencia_ms: Annotated[int, Field(ge=0)] | None = None
    trace_id: Hex32 | None = None


class RespostaEnviada(_Envio):
    tipo: ClassVar[str] = "resposta_enviada"

    def colunas(self) -> dict[str, Any]:
        return self.model_dump()


class Lembrete(_Envio):
    tipo: ClassVar[str] = "lembrete"
    janela_24h: bool
    custo_brl: Dinheiro = Decimal(0)

    @model_validator(mode="after")
    def _template_pago_fora_da_janela(self) -> Lembrete:
        if self.janela_24h and self.custo_brl != 0:
            raise ValueError("dentro da janela de 24 h o custo é zero")
        if not self.janela_24h and self.custo_brl <= 0:
            raise ValueError("fora da janela de 24 h é template pago: custo_brl > 0")
        return self

    def colunas(self) -> dict[str, Any]:
        return self.model_dump()


class Encerramento(DadosPasso):
    tipo: ClassVar[str] = "encerramento"
    desfecho: Desfecho
    motivo_desfecho: Codigo60 | None = None

    def colunas(self) -> dict[str, Any]:
        return {"resultado": self.desfecho, "motivo": self.motivo_desfecho}


class Repasse(DadosPasso):
    tipo: ClassVar[str] = "repasse"
    repasse_etapa: Literal["nota", "chatbot", "rota", "marca", "lease", "cerco"]
    tx_id: TxId | None = None

    def colunas(self) -> dict[str, Any]:
        return self.model_dump()


class Erro(DadosPasso):
    tipo: ClassVar[str] = "erro"
    peca: Codigo40
    trace_id: Hex32 | None = None

    def colunas(self) -> dict[str, Any]:
        return self.model_dump()


class Verificacao(DadosPasso):
    tipo: ClassVar[str] = "verificacao"
    verif_momento: Literal["entrada", "saida", "pre_t7"]
    verif_rotulo: Codigo40
    verif_confianca: Annotated[Decimal, Field(ge=0, le=1, max_digits=4, decimal_places=3)]
    modelo: NomeModelo
    provedor: NomeProvedor
    tokens_entrada: Annotated[int, Field(ge=0)] | None = None
    tokens_saida: Annotated[int, Field(ge=0)] | None = None
    custo_brl: Dinheiro | None = None
    trace_id: Hex32 | None = None

    def colunas(self) -> dict[str, Any]:
        return self.model_dump()


class OptOut(DadosPasso):
    tipo: ClassVar[str] = "opt_out"
    trace_id: Hex32 | None = None

    def colunas(self) -> dict[str, Any]:
        return self.model_dump()


class AnotacaoOperador(DadosPasso):
    """Texto do OPERADOR (não do cliente), 1–250 caracteres, sem nada que a máscara trocaria (contrato 08 §5.4)."""

    tipo: ClassVar[str] = "anotacao_operador"
    operador: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    resultado: Codigo40
    nota: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=LIMITE_NOTA)]

    @model_validator(mode="after")
    def _sem_pii_no_texto_livre(self) -> AnotacaoOperador:
        nomes = _NOMES.get()
        if nomes is None:
            raise ValueError("pii_no_texto_livre: nomes da conversa não informados; o texto livre não é aceito sem eles")
        if mascarar(self.nota, nomes) != self.nota:
            raise ValueError("pii_no_texto_livre: a nota contém dado que a máscara trocaria")
        return self

    def colunas(self) -> dict[str, Any]:
        return {"operador": self.operador, "resultado": self.resultado}


class Agendamento(DadosPasso):
    tipo: ClassVar[str] = "agendamento"
    agendamento_id: UUID
    resultado: Literal["proposto", "confirmado", "reagendado", "cancelado", "expirado", "disparado", "resolvido"]
    tx_id: TxId | None = None

    def colunas(self) -> dict[str, Any]:
        return self.model_dump()


TIPOS_DE_PASSO: Final[tuple[str, ...]] = (
    "mensagem_recebida",
    "decisao",
    "chamada_ferramenta",
    "confirmacao",
    "resposta_enviada",
    "lembrete",
    "encerramento",
    "repasse",
    "erro",
    "verificacao",
    "opt_out",
    "anotacao_operador",
    "agendamento",
)
_CLASSES: Final[dict[str, type[DadosPasso]]] = {
    c.tipo: c
    for c in (
        MensagemRecebida, ChamadaFerramenta, Confirmacao, RespostaEnviada, Lembrete, Encerramento,
        Repasse, Erro, Verificacao, OptOut, AnotacaoOperador, Agendamento,
    )
}  # fmt: skip


def criar(tipo: str, *, nomes: Collection[str] | None = None, **campos: Any) -> DadosPasso:
    """Monta os dados de um passo pelo nome do tipo. `decisao` escolhe a classe pelo `motor` (modelo ou regra). Erro sem o valor.

    `nomes` = nome do cliente e variantes da conversa; é exigido pelo único tipo com texto livre de pessoa (`anotacao_operador`,
    texto do operador). `None` = indisponíveis: a nota é recusada. O `motivo` do modelo é código de catálogo, não texto (A1)."""
    if tipo == "decisao":
        classe: type[DadosPasso] = DecisaoModelo if campos.get("motor", "modelo") == "modelo" else DecisaoRegra
    elif tipo in _CLASSES:
        classe = _CLASSES[tipo]
    else:
        raise ValueError(f"tipo de passo desconhecido (esperado um de {len(TIPOS_DE_PASSO)})")
    marca = _NOMES.set(nomes)
    try:
        return classe(**campos)  # o construtor já devolve `EntradaInvalida` sem o valor (ModeloSemEco)
    finally:
        _NOMES.reset(marca)


# --- texto_passo -------------------------------------------------------------------------------------------------------------------


def _verificacao_det(verif_det: list[str]) -> str:
    return "verificação determinística limpa" if not verif_det else "verificação determinística apontou: " + ", ".join(verif_det)


def _texto_mensagem(d: MensagemRecebida) -> str:
    return f"Cliente enviou texto ({d.msg_tamanho} caracteres)." if d.msg_tipo == "texto" else f"Cliente enviou {d.msg_tipo}."


def _texto_decisao_modelo(d: DecisaoModelo) -> str:
    texto = f"Modelo classificou a intenção como {d.intencao} (confiança {d.confianca})"
    texto += f"; objeção: {d.objecao}" if d.objecao else ""
    texto += "; ação fora da fase" if d.acao_invalida else ""
    return texto + "."


def _texto_decisao_regra(d: DecisaoRegra) -> str:
    texto = "Decisão pelo motor de escolha" if d.motor == "motor_escolha" else "Decisão por regra"
    return texto + (f"; tratamento transversal: {d.transversal}." if d.transversal else ".")


def _texto_chamada(d: ChamadaFerramenta) -> str:
    return f"Ferramenta {d.ferramenta} (versão {d.ferramenta_versao}) chamada" + (" com confirmação." if d.confirmacao_ref else ".")


def _texto_confirmacao(d: Confirmacao) -> str:
    if d.resultado == "invalidada":
        return f"Confirmação invalidada (motivo: {d.invalidacao})."
    return f"Confirmação: {d.resultado}."


def _texto_envio(abertura: str, d: _Envio, janela: str = "") -> str:
    com_texto = f" com o texto {d.tx_id}" if d.tx_id else ""
    return f"{abertura} ({d.entrega}){com_texto}{janela}; {_verificacao_det(d.verif_det)}."


def _texto_resposta(d: RespostaEnviada) -> str:
    return _texto_envio("Resposta enviada" if d.tx_id else "Resposta livre enviada", d)


def _texto_lembrete(d: Lembrete) -> str:
    janela = ", dentro da janela de 24 h" if d.janela_24h else ", fora da janela de 24 h (template pago)"
    return _texto_envio("Lembrete enviado", d, janela)


def _texto_encerramento(d: Encerramento) -> str:
    return f"Atendimento encerrado: {d.desfecho}" + (f" (motivo: {d.motivo_desfecho})." if d.motivo_desfecho else ".")


def _texto_repasse(d: Repasse) -> str:
    return f"Repasse ao vendedor: etapa {d.repasse_etapa}" + (f" (texto {d.tx_id})." if d.tx_id else ".")


def _texto_verificacao(d: Verificacao) -> str:
    return f"Verificação na {d.verif_momento}: {d.verif_rotulo} (confiança {d.verif_confianca:.3f})."


_TEXTOS: Final[dict[type[DadosPasso], Callable[[Any], str]]] = {
    MensagemRecebida: _texto_mensagem,
    DecisaoModelo: _texto_decisao_modelo,
    DecisaoRegra: _texto_decisao_regra,
    ChamadaFerramenta: _texto_chamada,
    Confirmacao: _texto_confirmacao,
    RespostaEnviada: _texto_resposta,
    Lembrete: _texto_lembrete,
    Encerramento: _texto_encerramento,
    Repasse: _texto_repasse,
    Erro: lambda d: f"Erro na peça {d.peca}.",
    Verificacao: _texto_verificacao,
    OptOut: lambda d: "Pedido de não receber mais mensagens registrado.",
    AnotacaoOperador: lambda d: f"Anotação ({d.resultado}): {d.nota}",
    Agendamento: lambda d: f"Agendamento {d.resultado}.",
}


def texto_passo(dados: DadosPasso) -> str:
    """Texto determinístico (1–1000 caracteres, ≤ 300 na anotação) do passo; nunca cita o cliente."""
    escrever = _TEXTOS.get(type(dados))
    if escrever is None:
        raise TypeError("texto_passo espera uma das 14 classes de passo")
    return escrever(dados)
