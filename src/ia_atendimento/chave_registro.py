"""Registro das chaves de configuração: nome -> validação (Pydantic) e padrão. Espelha os CHECKs da 0001 e cobre também as chaves sem seed.

O CHECK do banco é a rede de baixo (nome aberto, valor validado só para as chaves conhecidas); este registro é a de cima:
fecha o nome (chave fora do registro = `ConfigInexistente`), acrescenta o que o DDL não sabe (`modo=teste` global, `chats_teste` com
até 20 ids de 24 hex, `agenda_max_dia` <= `max_disparos_dia` em `chave.py`) e guarda o padrão de cada chave para o boot (R2-17).
Nenhuma mensagem de erro leva o valor recebido: só o nome da chave e a regra.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    StrictBool,
    StrictFloat,
    StrictInt,
    TypeAdapter,
    ValidationError,
    field_validator,
)

from ia_atendimento.calendario import CalendarioInvalido, validar_calendario_bloqueio, validar_janela_mensagem

MODOS_GLOBAIS = ("real", "sombra", "duble")  # `teste` é por atendimento (o CHECK o admite; a aplicação não)
BANCOS = ("FACTA", "3RN", "C6")
FAIXAS = ("baixa", "media", "alta", "muito_alta")
MAX_CHATS_TESTE = 20
PADRAO_CHAT_ID = re.compile(r"^[0-9a-f]{24}$")
PADRAO_MODELO = r"^(deepseek|gemini)-[a-z0-9][a-z0-9._-]{0,59}$"
HORA = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"


class ErroConfig(Exception):
    """Base dos erros de configuração; `codigo` é o do envelope de erro da API (contrato 08)."""

    codigo = "erro_config"


class ConfigInexistente(ErroConfig):
    codigo = "config_inexistente"


class ValorInvalido(ErroConfig):
    codigo = "valor_invalido"

    def __init__(self, nome: str, regra: str) -> None:
        super().__init__(f"{nome}: {regra}")
        self.nome, self.regra = nome, regra


class ModoTesteGlobal(ValorInvalido):
    codigo = "modo_teste_global"


class ConfigCorrida(ErroConfig):
    codigo = "config_corrida"


@dataclass(frozen=True)
class Especificacao:
    validar: Callable[[Any], Any]  # devolve o valor normalizado (JSON puro) ou levanta ValorInvalido


# --- modelos Pydantic ------------------------------------------------------------------------------------------------------------------


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)


Numero = Annotated[StrictInt | StrictFloat, Field(allow_inf_nan=False)]
Inteiro0a2 = Annotated[StrictInt, Field(ge=0, le=2)]


class _Faixa(_Base):
    lembretes_max: Inteiro0a2
    lembrete_pago_max: Annotated[StrictInt, Field(ge=0, le=2)]
    dias_max: Annotated[StrictInt, Field(ge=1, le=7)]
    contrapropostas_max: Annotated[StrictInt, Field(ge=0, le=3)]
    custo_max_brl: Annotated[Numero, Field(gt=0, le=3)]
    agendamentos_max: Annotated[StrictInt, Field(ge=0, le=10)]

    @field_validator("lembrete_pago_max")
    @classmethod
    def _pago_ate_o_total(cls, valor: int, info: Any) -> int:
        if valor > info.data.get("lembretes_max", 0):
            raise ValueError("lembrete_pago_max não pode passar de lembretes_max")
        return valor


class _FaixasEsforco(_Base):
    limites_brl: Annotated[list[Numero], Field(min_length=3, max_length=3)]
    faixas: dict[str, _Faixa]

    @field_validator("limites_brl")
    @classmethod
    def _crescentes(cls, valor: list[float]) -> list[float]:
        if not 0 < valor[0] < valor[1] < valor[2]:
            raise ValueError("limites_brl deve ser crescente e positivo")
        return valor

    @field_validator("faixas")
    @classmethod
    def _as_quatro(cls, valor: dict[str, _Faixa]) -> dict[str, _Faixa]:
        if set(valor) != set(FAIXAS):
            raise ValueError("faixas deve ter exatamente baixa, media, alta e muito_alta")
        return valor


class _Multiplicadores(_Base):
    espera: Annotated[Numero, Field(ge=0, le=2)]
    lembretes: Annotated[Numero, Field(ge=0, le=2)]
    contrapropostas: Annotated[Numero, Field(ge=0, le=2)]


class _Periodos(_Base):
    comercial: _Multiplicadores
    fora: _Multiplicadores


class _EsforcoPorPeriodo(RootModel[dict[str, _Periodos]]):
    model_config = ConfigDict(strict=True, frozen=True, hide_input_in_errors=True)

    @field_validator("root")
    @classmethod
    def _as_quatro(cls, valor: dict[str, _Periodos]) -> dict[str, _Periodos]:
        if set(valor) != set(FAIXAS):
            raise ValueError("deve ter exatamente baixa, media, alta e muito_alta")
        return valor


class _ModeloDaFaixa(_Base):
    modelo: Annotated[str, Field(pattern=PADRAO_MODELO)]
    provedor: Annotated[str, Field(pattern=r"^[a-z0-9_-]{1,30}$")]
    raciocinio: StrictBool
    custo_max_brl: Annotated[Numero, Field(gt=0, le=3)]


class _ModeloPorFaixa(RootModel[dict[str, _ModeloDaFaixa]]):
    model_config = ConfigDict(strict=True, frozen=True, hide_input_in_errors=True)

    @field_validator("root")
    @classmethod
    def _as_quatro(cls, valor: dict[str, _ModeloDaFaixa]) -> dict[str, _ModeloDaFaixa]:
        if set(valor) != set(FAIXAS):
            raise ValueError("deve ter exatamente baixa, media, alta e muito_alta")
        return valor


class _AgendaJanela(_Base):
    inicio: Annotated[str, Field(pattern=HORA)]
    fim: Annotated[str, Field(pattern=HORA)]
    sabado_fim: Annotated[str, Field(pattern=HORA)] | None = None

    @field_validator("fim")
    @classmethod
    def _ordem(cls, fim: str, info: Any) -> str:
        inicio = info.data.get("inicio", "")
        if not ("08:00" <= inicio < fim <= "20:00"):
            raise ValueError("a janela da agenda fica entre 08:00 e 20:00, com início antes do fim")
        return fim

    @field_validator("sabado_fim")
    @classmethod
    def _sabado(cls, valor: str | None, info: Any) -> str | None:
        if valor is not None and not (info.data.get("inicio", "") < valor <= info.data.get("fim", "")):
            raise ValueError("sabado_fim deve ficar entre o início e o fim da janela")
        return valor


class _AgendaPeriodos(RootModel[dict[Annotated[str, Field(pattern=r"^[a-z_]{1,30}$")], Annotated[str, Field(pattern=HORA)]]]):
    model_config = ConfigDict(strict=True, frozen=True, hide_input_in_errors=True)

    @field_validator("root")
    @classmethod
    def _dentro_da_janela(cls, valor: dict[str, str]) -> dict[str, str]:
        if any(not ("08:00" <= hora <= "20:00") for hora in valor.values()):
            raise ValueError("cada período fica entre 08:00 e 20:00")
        return valor


# --- validadores -----------------------------------------------------------------------------------------------------------------------


def _por_modelo(nome: str, modelo: Any) -> Callable[[Any], Any]:
    adaptador = TypeAdapter(modelo)

    def validar(valor: Any) -> Any:
        try:
            resultado = adaptador.validate_python(valor)
        except ValidationError as erro:
            primeiro = erro.errors(include_input=False, include_url=False, include_context=False)[0]
            raise ValorInvalido(nome, f"{'.'.join(str(p) for p in primeiro['loc']) or 'valor'}: {primeiro['msg']}") from None
        return resultado.model_dump(mode="json", exclude_none=True) if isinstance(resultado, BaseModel) else resultado

    return validar


def _booleano(nome: str) -> Callable[[Any], Any]:
    return _por_modelo(nome, StrictBool)


def _numero_nao_negativo(nome: str) -> Callable[[Any], Any]:
    return _por_modelo(nome, Annotated[Numero, Field(ge=0)])


def _inteiro(nome: str, minimo: int, maximo: int) -> Callable[[Any], Any]:
    return _por_modelo(nome, Annotated[StrictInt, Field(ge=minimo, le=maximo)])


def _modo_global(valor: Any) -> str:
    if valor == "teste":
        raise ModoTesteGlobal("modo", "o modo global não aceita 'teste' (é por atendimento, pela lista chats_teste)")
    if not (isinstance(valor, str) and valor in MODOS_GLOBAIS):
        raise ValorInvalido("modo", "deve ser real, sombra ou duble")
    return valor


def _chats_teste(valor: Any) -> list[str]:
    if not isinstance(valor, list) or len(valor) > MAX_CHATS_TESTE:
        raise ValorInvalido("chats_teste", f"deve ser uma lista de até {MAX_CHATS_TESTE} ids")
    if not all(isinstance(c, str) and PADRAO_CHAT_ID.fullmatch(c) for c in valor):
        raise ValorInvalido("chats_teste", "cada id deve ter 24 caracteres hexadecimais minúsculos")
    if len(set(valor)) != len(valor):
        raise ValorInvalido("chats_teste", "ids repetidos")
    return list(valor)


def _bancos(valor: Any) -> list[str]:
    if not isinstance(valor, list) or len(set(valor if all(isinstance(b, str) for b in valor) else [])) != len(valor):
        raise ValorInvalido("bancos_digitacao", "deve ser uma lista de bancos sem repetição")
    if not set(valor) <= set(BANCOS):
        raise ValorInvalido("bancos_digitacao", f"bancos aceitos: {', '.join(BANCOS)}")
    return list(valor)


def _janela_mensagem(valor: Any) -> Any:
    try:
        validar_janela_mensagem(valor)
    except CalendarioInvalido as erro:
        raise ValorInvalido("janela_mensagem", str(erro)) from None
    return valor


def _calendario_bloqueio(valor: Any) -> Any:
    if not isinstance(valor, Mapping) or set(valor) - {"domingos", "feriados", "janelas"}:
        raise ValorInvalido("calendario_bloqueio", "aceita só domingos, feriados e janelas")
    try:
        validar_calendario_bloqueio(valor)
    except CalendarioInvalido as erro:
        raise ValorInvalido("calendario_bloqueio", str(erro)) from None
    return valor


def _janela_vendedores(valor: Any) -> Any:
    dias = valor.get("dias") if isinstance(valor, Mapping) else None
    if not isinstance(dias, Mapping) or not dias or set(valor) != {"dias"}:
        raise ValorInvalido("janela_vendedores", "deve ser {dias: {...}} com ao menos um dia")
    for chave, horario in dias.items():
        ok = (
            isinstance(horario, Mapping)
            and set(horario) == {"inicio", "fim"}
            and all(isinstance(h, str) and re.fullmatch(HORA, h) for h in horario.values())
        )
        if not (chave in {"1", "2", "3", "4", "5", "6", "7"} and ok and horario["inicio"] < horario["fim"]):
            raise ValorInvalido("janela_vendedores", "cada dia (1 a 7) leva inicio < fim em HH:MM")
    return valor


def _intervalos_lembrete(valor: Any) -> list[int]:
    if not isinstance(valor, list) or not 1 <= len(valor) <= 2:
        raise ValorInvalido("lembretes_intervalos_min", "deve ter 1 ou 2 intervalos (o teto global é de 2 lembretes)")
    return _por_modelo("lembretes_intervalos_min", list[Annotated[StrictInt, Field(ge=1, le=1440)]])(valor)


def _modelo_do_verificador(valor: Any) -> str:
    if not (isinstance(valor, str) and re.fullmatch(PADRAO_MODELO, valor)):
        raise ValorInvalido("verificador_modelo", "deve ser deepseek-* ou gemini-*")
    return valor


# --- padrões (= as seeds da 0001; o teste compara) ---------------------------------------------------------------------------------------

_DIA_MENSAGEM = {"inicio": "08:00", "fim": "20:00"}
_DIA_VENDEDOR = {"inicio": "08:00", "fim": "18:00"}
_MODELO = {"modelo": "deepseek-v4p1-flash-1017", "provedor": "fireworks-us", "raciocinio": False}
_NORMAL = {"espera": 1.0, "lembretes": 1.0, "contrapropostas": 1.0}


def _periodo(comercial: tuple[float, float, float]) -> dict[str, dict[str, float]]:
    espera, lembretes, contrapropostas = comercial
    return {"comercial": {"espera": espera, "lembretes": lembretes, "contrapropostas": contrapropostas}, "fora": dict(_NORMAL)}


PADROES: dict[str, Any] = {
    "ia_ativa": False,
    "teto_mensal_brl": 2000,
    "modo": "duble",
    "subteto_dia": 100,
    "max_disparos_dia": 10,
    "max_abertos": 10,
    "verificador_ativo": False,
    "bancos_digitacao": ["FACTA"],
    "ia_repasse_dias": 14,
    "faixas_esforco": {
        "limites_brl": [150, 400, 800],
        "faixas": {
            "baixa": {
                "lembretes_max": 0,
                "lembrete_pago_max": 0,
                "dias_max": 1,
                "contrapropostas_max": 1,
                "custo_max_brl": 1.0,
                "agendamentos_max": 0,
            },
            "media": {
                "lembretes_max": 1,
                "lembrete_pago_max": 0,
                "dias_max": 2,
                "contrapropostas_max": 2,
                "custo_max_brl": 2.0,
                "agendamentos_max": 1,
            },
            "alta": {
                "lembretes_max": 2,
                "lembrete_pago_max": 0,
                "dias_max": 3,
                "contrapropostas_max": 3,
                "custo_max_brl": 3.0,
                "agendamentos_max": 3,
            },
            "muito_alta": {
                "lembretes_max": 2,
                "lembrete_pago_max": 1,
                "dias_max": 3,
                "contrapropostas_max": 3,
                "custo_max_brl": 3.0,
                "agendamentos_max": 3,
            },
        },
    },
    "esforco_por_periodo": {
        "baixa": _periodo((0.5, 0.5, 0.5)),
        "media": _periodo((0.5, 0.5, 0.75)),
        "alta": _periodo((0.75, 0.75, 1.0)),
        "muito_alta": _periodo((1.0, 1.0, 1.0)),
    },
    "janela_vendedores": {"dias": {**{str(d): dict(_DIA_VENDEDOR) for d in range(1, 6)}, "6": {"inicio": "08:00", "fim": "12:00"}}},
    "janela_mensagem": {"dias": {str(d): dict(_DIA_MENSAGEM) for d in range(1, 7)}},
    "modelo_por_faixa": {
        "baixa": {**_MODELO, "custo_max_brl": 1.0},
        "media": {**_MODELO, "custo_max_brl": 2.0},
        "alta": {**_MODELO, "custo_max_brl": 3.0},
        "muito_alta": {**_MODELO, "custo_max_brl": 3.0},
    },
    "bloqueio_entrada": False,
    "chats_teste": [],
    "agenda_max_dia": 5,
    "agenda_periodos": {
        "cedo": "08:30",
        "manha": "09:00",
        "almoco": "12:00",
        "depois_do_almoco": "13:30",
        "tarde": "14:00",
        "fim_da_tarde": "17:30",
        "noite": "19:00",
    },
    "agenda_ativa": False,
    "agenda_janela": {"inicio": "08:30", "fim": "19:00", "sabado_fim": "12:00"},
    "agenda_teto_horas": 23,
    "agenda_max_por_atendimento": 2,
    "agenda_max_pausados": 10,
    "agenda_folga_min": 30,
    "agenda_b_digita": False,
    "alcada_valor_max_brl": 6000,
    "calendario_bloqueio": {
        "domingos": True,
        "feriados": ["2026-11-02", "2026-11-20"],
        "janelas": [{"de": "2026-11-20T22:00:00-03:00", "ate": "2026-11-23T06:00:00-03:00", "motivo": "dataprev"}],
    },
    # sem seed na 0001 (nome aberto); gravada no boot (v3, 30/10): 1º lembrete 4 h depois da última mensagem da IA, 2º 4 h depois
    "lembretes_intervalos_min": [240, 240],
}

REGISTRO: dict[str, Especificacao] = {
    nome: Especificacao(validar)
    for nome, validar in {
        "ia_ativa": _booleano("ia_ativa"),
        "verificador_ativo": _booleano("verificador_ativo"),
        "agenda_ativa": _booleano("agenda_ativa"),
        "agenda_b_digita": _booleano("agenda_b_digita"),
        "bloqueio_entrada": _booleano("bloqueio_entrada"),
        "teto_mensal_brl": _numero_nao_negativo("teto_mensal_brl"),
        "subteto_dia": _numero_nao_negativo("subteto_dia"),
        "alcada_valor_max_brl": _numero_nao_negativo("alcada_valor_max_brl"),
        "max_disparos_dia": _inteiro("max_disparos_dia", 1, 200),
        "max_abertos": _inteiro("max_abertos", 1, 200),
        "ia_repasse_dias": _inteiro("ia_repasse_dias", 1, 200),
        "agenda_max_pausados": _inteiro("agenda_max_pausados", 1, 200),
        "agenda_folga_min": _inteiro("agenda_folga_min", 1, 200),
        "agenda_max_dia": _inteiro("agenda_max_dia", 1, 200),
        "agenda_teto_horas": _inteiro("agenda_teto_horas", 1, 23),
        "agenda_max_por_atendimento": _inteiro("agenda_max_por_atendimento", 1, 2),
        "modo": _modo_global,
        "bancos_digitacao": _bancos,
        "chats_teste": _chats_teste,
        "faixas_esforco": _por_modelo("faixas_esforco", _FaixasEsforco),
        "esforco_por_periodo": _por_modelo("esforco_por_periodo", _EsforcoPorPeriodo),
        "modelo_por_faixa": _por_modelo("modelo_por_faixa", _ModeloPorFaixa),
        "agenda_janela": _por_modelo("agenda_janela", _AgendaJanela),
        "agenda_periodos": _por_modelo("agenda_periodos", _AgendaPeriodos),
        "janela_mensagem": _janela_mensagem,
        "janela_vendedores": _janela_vendedores,
        "calendario_bloqueio": _calendario_bloqueio,
        "lembretes_intervalos_min": _intervalos_lembrete,
        "verificador_modelo": _modelo_do_verificador,
    }.items()
}
