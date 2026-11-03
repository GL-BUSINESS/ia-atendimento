"""O `Turno` (saída do modelo), as tabelas da fase e o que sai de um turno: erros, uso, custo e resultado (B1.4, sp01 T6).

Módulo puro: sem rede, sem banco, sem OpenTelemetry. `agente.py` o reexporta e o usa para conversar com o provedor.

- **`Turno`** é o que o modelo devolve (H §2.2 + `sinal`, L §2.4): `extra="forbid"`, 20 intenções, texto livre ≤ 320 caracteres **sem
  dígito,
  sem «R$», sem link, sem e-mail** e só com os placeholders do conjunto fechado (H P3). O modelo escolhe um `tx_id` do catálogo; NUNCA
  escreve o texto fixo. Não herda de `ModeloSemEco`: o `ValidationError` tem de chegar ao pydantic-ai para valer o `output_retries`.
- **A fase manda.** `validar_turno_na_fase` confere ação, ferramenta, TX e campo contra as tabelas da fase (H §2.3b). Fora delas é
  `TurnoForaDaFase` (a `decisao` grava `acao_invalida=true`): conta como falha do modelo, e duas falhas viram repasse (B1.6).
- **Custo** (contrato 08 §9): `custo_brl = (tokens_in·in + tokens_cache·cache + tokens_out·out)/1e6 · câmbio`, 6 casas (`numeric(14,6)`).
  O turno que falha depois de gastar tokens leva o uso no erro: o gasto do dia é Σ `passo.custo_brl`, e custo ausente não vira zero calado.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from functools import cache
from types import MappingProxyType
from typing import Annotated, Any, Final, Literal, cast, get_args

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from ia_atendimento.config import PRECOS_PADRAO, Precos
from ia_atendimento.mascara import mascarar
from ia_atendimento.modelos_conversa import Fase
from ia_atendimento.passos import MOTIVOS_DE_DECISAO, DecisaoModelo, Faixa, criar
from ia_atendimento.passos import Codigo40 as CodigoSemPii
from ia_atendimento.tipos import Referencia

# --- vocabulário do Turno (H §2.2; `tests/test_agente.py` o compara com o da F3) ---------------------------------------------------------

Intencao = Literal[
    "aceita", "recusa_firme", "quer_pensar", "duvida_processo", "duvida_oferta", "objecao", "quer_outro_valor", "quer_outro_prazo",
    "quer_outro_banco", "fornece_dado", "pede_humano", "reclamacao", "parar", "saudacao", "fora_de_escopo", "nao_sou_eu",
    "sinal_fraude_ou_vulnerabilidade", "ininteligivel", "adiar_com_hora", "adiar_sem_hora",
]  # fmt: skip  # as 18 de H §2.2 + as 2 de M (agendamento)
Objecao = Literal[
    "parcela_alta", "valor_baixo", "prazo_longo", "desconfianca", "ja_contratou", "nao_lembra", "receio_dados", "sem_tempo", "taxa_juros",
    "outra",
]  # fmt: skip
AlvoPedido = Literal["valor", "parcela", "prazo"]  # o NÚMERO é extraído por código da mensagem
CampoAlvo = Literal["pix", "conta", "cep", "numero_endereco", "celular"]
Acao = Literal["responder", "usar_ferramenta", "pedir_dado", "pedir_confirmacao", "aguardar", "repassar", "encerrar"]
Confianca = Literal["alta", "media", "baixa"]
Sinal = Literal["positivo", "neutro", "negativo", "frustrado"]  # L §2.4: um token que serve ao `sinais_cliente`

LIMITE_TEXTO: Final = 320  # H P2
LIMITE_MOTIVO: Final = 120
MOTIVO_AUSENTE: Final = "(não informado)"
OUTPUT_RETRIES: Final = 1  # a saída inválida ganha UMA nova tentativa; depois é falha do modelo (`SaidaInvalida`)
# Placeholders que o texto livre do modelo pode usar: o conjunto fechado de TEXTOS-PARA-APROVACAO (o código os resolve).
PLACEHOLDERS_DO_TEXTO: Final = frozenset(
    {"nome", "banco", "valor_liberado", "valor_parcela", "prazo", "destino", "link", "campo", "retorno", "pedido", "quando"}
)
_PLACEHOLDER: Final = re.compile(r"\{\{([a-z_]{1,30})\}\}")
_TEXTO_PROIBIDO: Final = ("r$", "us$", "@", "://", "www.", "http")  # valor, e-mail e link só por placeholder (H P3)

# Ações do modelo por fase (H §2.3b, coluna «acao permitidas»). E0/E1/E9: sem turno do modelo (H §2.3). E2–E6 e E8 são a tabela de H e
# batem com
# o gabarito das falas do cliente na F3 (teste). E7 também bate com a F3: só `aguardar` (a «frase de ponte» de H é o TX-38, que o
# código escolhe).
# E10 («Modelo: só contexto_codigos», H §2.3) leva `repassar` ou `encerrar`: a F3 só tem `encerrar` para fala do cliente, mas o turno que
# preenche `contexto_codigos` repassa. Decisão revisável.
ACOES_POR_FASE: Final[Mapping[Fase, frozenset[Acao]]] = MappingProxyType(
    {
        "E0": frozenset(),
        "E1": frozenset(),
        "E2": frozenset({"responder", "aguardar", "repassar", "encerrar"}),
        "E3": frozenset({"responder", "usar_ferramenta", "aguardar"}),
        "E4": frozenset({"usar_ferramenta", "responder", "repassar"}),
        "E5": frozenset({"pedir_dado", "responder", "repassar"}),
        "E6": frozenset({"aguardar", "responder"}),
        "E7": frozenset({"aguardar"}),
        "E8": frozenset({"responder", "aguardar", "encerrar"}),
        "E9": frozenset(),
        "E10": frozenset({"repassar", "encerrar"}),
    }
)
# Ferramentas que o MODELO pode pedir (H §2.3b, coluna «Modelo pode pedir»). T4, T6–T9 e T11–T15 são só do código no MVP.
FERRAMENTAS_DO_MODELO_POR_FASE: Final[Mapping[Fase, frozenset[str]]] = MappingProxyType(
    {
        "E0": frozenset(), "E1": frozenset(), "E2": frozenset({"T2", "T3"}), "E3": frozenset({"T3"}), "E4": frozenset({"T3", "T5"}),
        "E5": frozenset(), "E6": frozenset(), "E7": frozenset(), "E8": frozenset({"T10"}), "E9": frozenset(), "E10": frozenset(),
    }
)  # fmt: skip
# Textos fixos que o modelo pode ESCOLHER (H §2.3, E2: FAQ fechada). O resto do catálogo quem escolhe é o código.
TX_FAQ: Final = frozenset({"TX-32", "TX-33", "TX-39", "TX-40", "TX-41"})
TX_DO_MODELO_POR_FASE: Final[Mapping[Fase, frozenset[str]]] = MappingProxyType(
    {fase: (TX_FAQ if fase in ("E2", "E3", "E4", "E5", "E6", "E8") else frozenset()) for fase in get_args(Fase)}
)
FASE_DO_CAMPO_ALVO: Final = "E5"  # H §2.2: `campo_alvo` só na fase E5

MILHAO: Final = Decimal(1_000_000)
SEIS_CASAS: Final = Decimal("0.000001")  # `passo.custo_brl` é numeric(14,6)


# --- Turno -------------------------------------------------------------------------------------------------------------------------------


def _texto_livre_valido(texto: str) -> str:
    desconhecidos = {n for n in _PLACEHOLDER.findall(texto) if n not in PLACEHOLDERS_DO_TEXTO}
    if desconhecidos:
        raise ValueError("placeholder fora do conjunto fechado")
    resto = _PLACEHOLDER.sub("", texto)
    if "{" in resto or "}" in resto:
        raise ValueError("chave solta: placeholder malformado")
    if any(unicodedata.category(c).startswith("N") for c in resto):
        raise ValueError("texto livre sem dígito: número, valor e prazo só por placeholder (H P3)")
    if any(proibido in resto.lower() for proibido in _TEXTO_PROIBIDO):
        raise ValueError("texto livre sem «R$», e-mail nem link: só por placeholder")
    if mascarar(resto) != resto:
        raise ValueError("texto livre com dado pessoal")
    return texto


def _enxugar_schema(schema: dict[str, Any]) -> None:
    """O esquema vai ao modelo a cada chamada (é custo de entrada): sem `title` nem `description`, que o pydantic acrescenta sozinho."""
    schema.pop("title", None)
    schema.pop("description", None)
    for propriedade in schema.get("properties", {}).values():
        propriedade.pop("title", None)
        propriedade.pop("default", None)  # o modelo não precisa saber o padrão; `required` já diz o que é obrigatório


class FerramentaPedida(BaseModel):
    """A ferramenta que o modelo quer usar: o nome é validado contra a fase; os argumentos são só referências opacas."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, json_schema_extra=_enxugar_schema)

    nome: Annotated[str, StringConstraints(pattern=r"^T([1-9]|1[0-5])$")]
    args: Annotated[dict[Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,29}$")], Referencia], Field(max_length=4)] = Field(
        default_factory=dict
    )


class Turno(BaseModel):
    """Saída estruturada do modelo (H §2.2). `acao` é conferida contra a fase fora daqui (`validar_turno_na_fase`)."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, json_schema_extra=_enxugar_schema)

    intencao: Intencao
    acao: Acao
    confianca: Confianca  # baixa ⇒ o código repergunta
    objecao: Objecao | None = None
    alvo_pedido: AlvoPedido | None = None
    campo_alvo: CampoAlvo | None = None
    ferramenta: FerramentaPedida | None = None
    tx_id: Annotated[str, StringConstraints(pattern=r"^TX-(M)?[0-9]{2}$")] | None = None  # igual ao CHECK de `passo.tx_id`
    texto: Annotated[str, StringConstraints(min_length=1, max_length=LIMITE_TEXTO), AfterValidator(_texto_livre_valido)] | None = None
    contexto_codigos: Annotated[tuple[CodigoSemPii, ...], Field(max_length=10)] = ()
    motivo: Annotated[str, StringConstraints(max_length=LIMITE_MOTIVO)] = MOTIVO_AUSENTE
    sinal: Sinal = "neutro"  # sem o campo o padrão é neutro: faltar `sinal` não pode virar repasse

    @field_validator("motivo", mode="before")
    @classmethod
    def _motivo_vazio_vira_padrao(cls, valor: object) -> object:
        return MOTIVO_AUSENTE if valor is None or (isinstance(valor, str) and not valor.strip()) else valor

    @field_validator("texto", "tx_id", mode="before")
    @classmethod
    def _vazio_vira_nulo(cls, valor: object) -> object:
        return None if isinstance(valor, str) and not valor.strip() else valor

    @model_validator(mode="after")
    def _ferramenta_se_e_so_se_usar_ferramenta(self) -> Turno:
        if (self.acao == "usar_ferramenta") != (self.ferramenta is not None):
            raise ValueError("ferramenta existe se e somente se a ação é usar_ferramenta")
        return self


FERRAMENTA_DE_SAIDA: Final = "final_result"  # nome que o Pydantic AI dá à ferramenta de saída (Tool Output)


@cache
def formato_do_turno() -> str:
    """A ferramenta de saída como o provedor a recebe (nome, descrição e esquema do `Turno`). Conta nos tokens de entrada, junto do "
    "bloco 1."""
    ferramenta = {
        "type": "function",
        "function": {
            "name": FERRAMENTA_DE_SAIDA,
            "description": "The final response which ends this conversation",
            "parameters": Turno.model_json_schema(),
        },
    }
    return json.dumps([ferramenta], ensure_ascii=False, separators=(",", ":"))


# --- custo e uso -------------------------------------------------------------------------------------------------------------------------


def custo_brl(*, tokens_in: int, tokens_cache: int, tokens_out: int, precos: Precos = PRECOS_PADRAO) -> Decimal:
    """Custo estimado do turno em R$, 6 casas. `tokens_in` = entrada NÃO cacheada; `tokens_cache` = entrada lida do cache de prefixo."""
    if min(tokens_in, tokens_cache, tokens_out) < 0:
        raise ValueError("tokens não podem ser negativos")
    dolares = (tokens_in * precos.entrada_usd + tokens_cache * precos.cache_usd + tokens_out * precos.saida_usd) / MILHAO
    return (dolares * precos.cambio).quantize(SEIS_CASAS, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True)
class UsoDoTurno:
    """O que o turno gastou. `tokens_raciocinio` já está dentro de `tokens_out` (o provedor cobra como saída)."""

    tokens_in: int = 0
    tokens_cache: int = 0
    tokens_out: int = 0
    tokens_raciocinio: int = 0
    custo_brl: Decimal = Decimal(0)
    latencia_ms: int = 0
    trace_id: str | None = None

    @property
    def tokens_entrada(self) -> int:
        """Entrada total (cacheada ou não): o que o passo grava em `tokens_entrada`."""
        return self.tokens_in + self.tokens_cache


# --- erros do modelo ---------------------------------------------------------------------------------------------------------------------


class ErroDoModelo(Exception):
    """Falha do turno do modelo: o processador a conta (duas ⇒ repasse, P7). A mensagem é fixa: nunca cita prompt, saída nem corpo HTTP.

    `uso` é o que o turno gastou antes de falhar (para o gasto do dia); `status` é o HTTP do provedor, quando houve."""

    def __init__(self, codigo: str, mensagem: str, *, uso: UsoDoTurno | None = None, status: int | None = None) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.uso = uso
        self.status = status


class ProvedorIndisponivel(ErroDoModelo):
    """Rede, HTTP (`status`), limite, cota ou tempo esgotado no provedor. Não há segundo provedor (G §4): a reserva é o repasse."""


class SaidaInvalida(ErroDoModelo):
    """O modelo respondeu, mas a saída não virou um `Turno` válido nem depois do `output_retries`."""


class TurnoForaDaFase(ErroDoModelo):
    """O modelo respondeu, mas pediu o que a fase não permite. A `decisao` grava `acao_invalida=true`; `resultado` leva o gasto."""

    acao_invalida = True

    def __init__(self, codigo: str, mensagem: str, *, turno: Turno, fase: str, resultado: ResultadoTurno | None = None) -> None:
        super().__init__(codigo, mensagem, uso=resultado.uso if resultado else None)
        self.turno = turno
        self.fase = fase
        self.resultado = resultado


class AcaoForaDaFase(TurnoForaDaFase):
    pass


class FerramentaForaDaFase(TurnoForaDaFase):
    pass


class TxForaDaFase(TurnoForaDaFase):
    pass


class CampoForaDaFase(TurnoForaDaFase):
    pass


def validar_turno_na_fase(fase: str, turno: Turno, *, resultado: ResultadoTurno | None = None) -> None:
    """Confere o `Turno` contra a fase. Levanta o erro específico (todos `TurnoForaDaFase`); fase sem turno do modelo recusa toda ação."""
    if fase not in ACOES_POR_FASE:
        raise ValueError("fase desconhecida")
    if turno.acao not in ACOES_POR_FASE[fase]:  # type: ignore[index]
        raise AcaoForaDaFase("acao_fora_da_fase", f"ação {turno.acao} não vale na fase {fase}", turno=turno, fase=fase, resultado=resultado)
    if turno.ferramenta is not None and turno.ferramenta.nome not in FERRAMENTAS_DO_MODELO_POR_FASE[fase]:  # type: ignore[index]
        raise FerramentaForaDaFase(
            "ferramenta_fora_da_fase",
            f"ferramenta {turno.ferramenta.nome} não vale na fase {fase}",
            turno=turno,
            fase=fase,
            resultado=resultado,
        )
    if turno.tx_id is not None and turno.tx_id not in TX_DO_MODELO_POR_FASE[fase]:  # type: ignore[index]
        raise TxForaDaFase(
            "tx_fora_da_fase", f"texto {turno.tx_id} não é do modelo na fase {fase}", turno=turno, fase=fase, resultado=resultado
        )
    if turno.campo_alvo is not None and fase != FASE_DO_CAMPO_ALVO:
        raise CampoForaDaFase(
            "campo_fora_da_fase", f"campo_alvo só vale na fase {FASE_DO_CAMPO_ALVO}", turno=turno, fase=fase, resultado=resultado
        )


# --- resultado ---------------------------------------------------------------------------------------------------------------------------


def motivo_de_decisao(motivo: str) -> str | None:
    """`passo.motivo` é de lista fechada (A1): o texto livre do modelo NUNCA vai para o passo; só vale se for um dos códigos."""
    return motivo if motivo in MOTIVOS_DE_DECISAO else None


@dataclass(frozen=True)
class ResultadoTurno:
    """Um turno do modelo: o `Turno` validado + o que ele custou. `modelo` e `provedor` são os de `modelo_por_faixa` (o que o passo "
    "grava)."""

    turno: Turno
    modelo: str
    provedor: str
    uso: UsoDoTurno
    ferramentas_chamadas: tuple[str, ...] = ()
    raciocinio_detectado: bool = False
    acao_invalida: bool = False

    @property
    def tokens_in(self) -> int:
        return self.uso.tokens_in

    @property
    def tokens_cache(self) -> int:
        return self.uso.tokens_cache

    @property
    def tokens_out(self) -> int:
        return self.uso.tokens_out

    @property
    def custo_brl(self) -> Decimal:
        return self.uso.custo_brl

    @property
    def latencia_ms(self) -> int:
        return self.uso.latencia_ms

    @property
    def trace_id(self) -> str | None:
        return self.uso.trace_id

    def como_decisao(self, *, faixa_esforco: Faixa | None = None, transversal: str | None = None) -> DecisaoModelo:
        """O passo `decisao` do modelo, com tokens, `custo_brl` e latência do turno (contrato 08 §9). Sem texto do modelo nem do cliente."""
        decisao = criar(
            "decisao", motor="modelo", intencao=self.turno.intencao, confianca=self.turno.confianca, objecao=self.turno.objecao,
            acao_invalida=self.acao_invalida, transversal=transversal, faixa_esforco=faixa_esforco, modelo=self.modelo,
            provedor=self.provedor, tokens_entrada=self.uso.tokens_entrada, tokens_saida=self.uso.tokens_out, custo_brl=self.uso.custo_brl,
            latencia_ms=self.uso.latencia_ms, trace_id=self.uso.trace_id, motivo=motivo_de_decisao(self.turno.motivo),
        )  # fmt: skip
        return cast(DecisaoModelo, decisao)
