"""Extrator determinístico de horário para o agendamento da assinatura (B5.7a; estudo M §2.3-2.4).

Módulo PURO: sem banco, sem rede, sem modelo, sem relógio próprio (`agora` e `ultima_msg_cliente_em` entram por parâmetro).
O modelo só classifica a intenção (`adiar_com_hora`/`adiar_sem_hora`) ou escolhe entre os candidatos devolvidos aqui; **nunca escreve
a data**. Todo candidato traz `origem`, o trecho literal do texto que o gerou (EM1: zero data inventada).

Contrato:
- `extrair(texto, agora, ultima_msg_cliente_em, config) -> Resultado`; `agora` e `ultima_msg_cliente_em` precisam de fuso (ValueError).
- v1 (C2 parcial): só vale hora explícita («às 15», «15h», «15:30», «3 da tarde», «meio-dia», «daqui a 1 hora»). Sem hora explícita
  ⇒ `candidatos=()` e `motivo_recusa='sem_hora_explicita'`. Palavras de período («de tarde», «depois do almoço») só viram candidato com
  `ConfigAgenda.usa_periodos=True`, usando `agenda_periodos`, e nunca com confiança `alta`.
- Mais de um candidato (duas horas, dois dias, «15 ou 16») ⇒ todos com confiança ≤ `media`; mais de 3 ⇒ `ambiguo_demais`.
- Candidato que não cabe (passado, antecedência < 10 min, domingo fechado, feriado, bloqueio DATAPREV, fora de 08:30-19:00, sábado depois
  de 12:00, acima do teto) NÃO é descartado: vem com `fora_da_janela=True` e `razoes` (para a contraproposta). `motivo_recusa` só é
  preenchido quando nenhum candidato serve (a razão de maior prioridade do primeiro candidato) ou quando não há candidato.
- Domingo (D-18, B1.8): `ConfigAgenda.domingo_aberto` (padrão `False`) vem das duas chaves do calendário (`agendamento.config_da_agenda`).
  Fechado, «domingo» é razão de recusa e o teto pula o domingo; aberto, o domingo vale como os outros dias (janela 08:30–19:00, feriado e
  DATAPREV seguem valendo).
- Horário de envio (R-01 da revisão da B1.8): com `ConfigAgenda.janela_mensagem` (o `Calendario.dias`, que a API sempre passa), a
  volta também tem de caber no horário de envio do dia: antes do início ⇒ `antes_da_janela`, no fim ou depois ⇒ `depois_da_janela`
  (fim exclusivo), dia sem horário ⇒ `dia_sem_janela`; e o teto só para em dia com horário de envio. A agenda nunca reserva uma volta
  que o envio não cumpre.
- Dia não dito: «hoje» se o horário ainda está à frente; senão «amanhã» (confiança cai para `media`). O dia assumido não é texto, mas a
  `origem` continua sendo só o trecho da hora.
- Idempotente: a mesma entrada dá sempre a mesma saída.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from types import MappingProxyType
from typing import Literal
from zoneinfo import ZoneInfo

VERSAO = "1"
FUSO = ZoneInfo("America/Sao_Paulo")
MAX_TEXTO = 1000  # uma resposta de agendamento é curta; texto maior nem é varrido
MAX_CANDIDATOS = 3
PASSO_RELATIVO_MIN = 5  # «daqui a 1 hora» sobe para múltiplo de 5 min

Confianca = Literal["alta", "media", "baixa"]
_ORDEM_CONFIANCA = {"baixa": 0, "media": 1, "alta": 2}
# prioridade das razões: a primeira da lista é o `motivo_recusa`
RAZOES = (
    "feriado", "bloqueio_dataprev", "domingo", "dia_sem_janela", "passado", "antecedencia", "antes_da_janela", "depois_da_janela",
    "acima_do_teto",
)  # fmt: skip

PERIODOS_PADRAO = MappingProxyType(
    {
        "cedo": "08:30",
        "manha": "09:00",
        "almoco": "12:00",
        "depois_do_almoco": "13:30",
        "tarde": "14:00",
        "fim_da_tarde": "17:30",
        "noite": "19:00",
    }
)
FERIADOS_PADRAO = frozenset({date(2026, 11, 2), date(2026, 11, 20)})
DATAPREV_PADRAO = (datetime(2026, 11, 20, 22, 0, tzinfo=FUSO), datetime(2026, 11, 23, 6, 0, tzinfo=FUSO))
_HHMM = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
_CHAVE_PERIODO = re.compile(r"^[a-z_]{1,30}$")


def _hhmm(valor: str, nome: str) -> time:
    if not isinstance(valor, str) or not _HHMM.match(valor):
        raise ValueError(f"{nome}: esperado HH:MM, veio {valor!r}")
    return time(int(valor[:2]), int(valor[3:]))


def _validar_envio(dias: Mapping[int, tuple[time, time]]) -> dict[int, tuple[time, time]]:
    """Cópia de `janela_mensagem` por dia ISO (1..7), cada uma `(início, fim)` com início < fim."""
    copia = dict(dias)
    for dia, horario in copia.items():
        if not (isinstance(dia, int) and 1 <= dia <= 7) or not (
            isinstance(horario, tuple) and len(horario) == 2 and all(isinstance(h, time) for h in horario) and horario[0] < horario[1]
        ):
            raise ValueError("janela_mensagem: dia ISO 1..7 -> (início, fim) com início antes do fim")
    return copia


@dataclass(frozen=True, slots=True)
class ConfigAgenda:
    """Chaves `agenda_*` da `config_versao` (estudo I §9) mais o calendário. Imutável; `das_chaves` valida como o DDL."""

    periodos: Mapping[str, str] = PERIODOS_PADRAO
    janela_inicio: str = "08:30"
    janela_fim: str = "19:00"
    sabado_fim: str | None = "12:00"  # None: sábado vale a janela inteira
    teto_horas: int = 23  # agenda_teto_horas (janela de 24 h do WhatsApp)
    teto_dia_util_fim: str = "19:00"  # «próximo dia útil 19:00» do teto
    antecedencia_min: int = 10
    feriados: frozenset[date] = FERIADOS_PADRAO
    bloqueios: tuple[tuple[datetime, datetime], ...] = (DATAPREV_PADRAO,)  # [início, fim)
    usa_periodos: bool = False  # v1 = False (C2 parcial): período sem hora explícita ⇒ repasse
    domingo_aberto: bool = False  # D-18: só com `calendario_bloqueio.domingos=false` E o dia 7 em `janela_mensagem` (fechado por padrão)
    # Horário de ENVIO por dia ISO (`Calendario.dias`, fim exclusivo). A volta também tem de caber nele (R-01 da B1.8): a agenda nunca
    # reserva uma hora que o envio não pode cumprir. `None` só no extrator puro (corpus de frases); a API sempre passa (`config_da_agenda`).
    janela_mensagem: Mapping[int, tuple[time, time]] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "periodos", MappingProxyType(dict(self.periodos)))
        for nome in ("janela_inicio", "janela_fim", "teto_dia_util_fim"):
            _hhmm(getattr(self, nome), nome)
        if self.sabado_fim is not None:
            _hhmm(self.sabado_fim, "sabado_fim")
        if not _hhmm(self.janela_inicio, "janela_inicio") < _hhmm(self.janela_fim, "janela_fim"):
            raise ValueError("janela_inicio precisa ser menor que janela_fim")
        if self.teto_horas < 1 or self.antecedencia_min < 0:
            raise ValueError("teto_horas >= 1 e antecedencia_min >= 0")
        for chave, valor in self.periodos.items():
            _hhmm(valor, f"periodos[{chave}]")
        if self.janela_mensagem is not None:
            object.__setattr__(self, "janela_mensagem", MappingProxyType(_validar_envio(self.janela_mensagem)))

    @classmethod
    def das_chaves(
        cls,
        agenda_janela: Mapping[str, str] | None = None,
        agenda_periodos: Mapping[str, str] | None = None,
        agenda_teto_horas: int | None = None,
        **resto,
    ) -> ConfigAgenda:
        """Monta a partir dos valores jsonb de `agenda_janela`, `agenda_periodos`, `agenda_teto_horas` com as mesmas regras do DDL."""
        campos: dict = dict(resto)
        if agenda_janela is not None:
            ini, fim = agenda_janela.get("inicio"), agenda_janela.get("fim")
            if not (_hhmm(ini, "agenda_janela.inicio") >= time(8) and time(8) < _hhmm(fim, "agenda_janela.fim") <= time(20) and ini < fim):
                raise ValueError("agenda_janela: inicio < fim, dentro de 08:00-20:00")
            campos.update(janela_inicio=ini, janela_fim=fim, sabado_fim=agenda_janela.get("sabado_fim"))
        if agenda_periodos is not None:
            for chave, valor in agenda_periodos.items():
                if not _CHAVE_PERIODO.match(chave) or not time(8) <= _hhmm(valor, "agenda_periodos") <= time(20):
                    raise ValueError(f"agenda_periodos: chave/hora invalida ({chave!r})")
            campos["periodos"] = dict(agenda_periodos)
        if agenda_teto_horas is not None:
            if isinstance(agenda_teto_horas, bool) or not isinstance(agenda_teto_horas, int) or not 1 <= agenda_teto_horas <= 23:
                raise ValueError("agenda_teto_horas: inteiro de 1 a 23")
            campos["teto_horas"] = agenda_teto_horas
        return cls(**campos)


@dataclass(frozen=True, slots=True)
class Candidato:
    quando: datetime  # tz-aware, America/Sao_Paulo
    confianca: Confianca
    origem: str  # trecho literal do texto que gerou o candidato
    fora_da_janela: bool = False
    razoes: tuple[str, ...] = ()  # por que não cabe, na ordem de RAZOES


@dataclass(frozen=True, slots=True)
class Resultado:
    candidatos: tuple[Candidato, ...]  # em ordem cronológica
    motivo_recusa: str | None
    versao: str = VERSAO

    @property
    def validos(self) -> tuple[Candidato, ...]:
        return tuple(c for c in self.candidatos if not c.fora_da_janela)


# ------------------------------------------------------------------------------------------------ texto
def _normalizar(texto: str) -> str:
    """Minúsculas sem acento, MESMO comprimento do original (um caractere por caractere): as posições valem no texto original."""
    saida = []
    for ch in texto:
        base = unicodedata.normalize("NFD", ch)[:1].lower()
        saida.append(base if len(base) == 1 else ch)
    return "".join(saida)


_NUMW = {
    "uma": 1,
    "um": 1,
    "dois": 2,
    "duas": 2,
    "tres": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
    "dez": 10,
    "onze": 11,
    "doze": 12,
}
_MIN = {"meia": 30, "quinze": 15, "quarenta e cinco": 45, "vinte e cinco": 25, "vinte": 20, "trinta": 30, "dez": 10, "cinco": 5}
_MESES = dict(
    zip(
        ("janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"),
        range(1, 13),
        strict=True,
    )
) | dict(zip(("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"), range(1, 13), strict=True))
_DIAS_SEMANA = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6, "seg": 0, "sex": 4, "sab": 5}

_W = "|".join(sorted((w for w in _NUMW if w not in ("um", "uma")), key=len, reverse=True))  # número por extenso sem «um/uma» (ambíguos)
_FIMNUM = r"(?!\d|[:.,/]\d)"  # «19:01:00», «15,30», «15:99» não são «19», «15»
_NUM = rf"(?:\d{{1,2}}{_FIMNUM}|(?:{_W})\b)"  # número por extenso precisa de fronteira: «dozentas» não é «doze»
_NUM_UMA = rf"(?:\d{{1,2}}(?!\d|[.,/]\d)|(?:uma|um|{_W})\b)"  # aceita «3:30 da tarde»
_MINW = "|".join(sorted(_MIN, key=len, reverse=True))
_MN = rf"(?P<mn>{_MINW})\b(?!\s+e\s+(?:{_MINW}\b|\d))"  # «e trinta e cinco» não vira «e trinta»
_UNID = r"(?:horas?|hrs?|hs|h)"
_ANTES = r"(?<![\d:/.,])"
# quantidade, não horário: «as 3 parcelas», «entre 15 e 16 parcelas», «2 contratos», «R$ 15», «12x»
_QUANTIDADE = (
    r"(?:parcelas?|prestacoes?|reais|real|vezes|vez|mil|dias|semanas?|anos?|mes|meses|filhos?|contos?|contratos?|propostas?|pessoas?"
    r"|clientes?|ofertas?|bancos?|x|k)\b|dia\b(?!\s+\d)|%|r\$"  # «dia 6» é data, não quantidade
)
_NAO_HORA = rf"(?!\s*(?:{_QUANTIDADE}))"
_QUAL = r"(?:da|de|a|na|pela)\s+(?P<q>manha|tarde|noite|madrugada)"
_R_MEIODIA = re.compile(rf"\b(?:meio[\s-]*dia|(?P<mnoite>meia[\s-]*noite))(?:\s+e\s+{_MN})?\b")


def _lado(n: str, *, fecha: bool = True) -> str:
    """Um lado de «15h ou 16:30»: a hora COMPLETA (com minutos), para não oferecer um horário que o cliente não disse."""
    resto = rf"(?!\s+e\s+(?:{_MINW}\b|\d))" if fecha else ""
    return rf"(?:as\s+)?(?P<{n}>\d{{1,2}})(?::(?P<{n}m>\d{{2}})|\s*{_UNID}(?P<{n}n>[0-5]\d)?(?:\s*min(?:utos?)?\b)?)?(?![\w:]){resto}"


_R_ENTRE = re.compile(rf"\bentre\s+{_lado('a', fecha=False)}\s+e\s+{_lado('b')}(?:\s+{_QUAL})?{_NAO_HORA}")
_R_OU = re.compile(rf"{_ANTES}{_lado('a')}\s+ou\s+{_lado('b')}(?:\s+{_QUAL})?{_NAO_HORA}")
_R_QUAL = re.compile(
    rf"{_ANTES}(?P<pre>(?:umas?|as?)\s+)?(?P<h>{_NUM_UMA})(?::(?P<m>\d{{2}}))?\s*(?:{_UNID}\b)?\s*(?:e\s+{_MN}\s+)?{_QUAL}\b"
)
_R_UMAS = re.compile(rf"\bumas?\s+(?P<h>{_NUM})(?:\s*{_UNID}\b)?(?:\s+e\s+{_MN})?{_NAO_HORA}")
_R_DEPOIS = re.compile(rf"\b(?:depois|dps)\s+d[aeo]s?\s+(?P<h>{_NUM})(?:\s*{_UNID}\b)?")
_R_HXM = re.compile(rf"{_ANTES}(?P<h>\d{{1,2}})\s*{_UNID}(?P<m>[0-5]\d)(?:\s*min(?:utos?)?\b)?(?!\d)")
_R_HM = re.compile(rf"{_ANTES}(?P<h>\d{{1,2}}):(?P<m>\d{{2}})(?![\d:])(?:\s*{_UNID}\b)?")
_R_H = re.compile(rf"{_ANTES}(?P<h>\d{{1,2}})\s*{_UNID}\b(?:\s+e\s+{_MN})?(?!\s*\d+(?![\d/]))")
_R_AS = re.compile(rf"\bas\s+(?P<h>{_NUM})(?!\s*{_UNID}\b)(?:\s+e\s+{_MN})?{_NAO_HORA}")
_R_EMEIA = re.compile(rf"{_ANTES}(?P<h>{_NUM})\s+e\s+{_MN}{_NAO_HORA}")
_QTD = r"(?:(?P<n>\d{1,3})|(?P<w>uma|um|duas|dois|tres|quatro|cinco|meia))"
# «uma hora e quinze minutos», «2 horas e meia»: a expressão inteira ou nada
_RESTO_REL = rf"(?:\s+e\s+(?:(?P<mm>{_MINW})\b(?:\s*min(?:utos?)?\b)?|(?P<md>\d{{1,2}})\s*min(?:utos?)?\b))?(?!\s+e\s+(?:{_MINW}\b|\d))"
# «em 15h» é horário (às 15h), não «daqui a 15 horas»: com «em» só vale a unidade por extenso
_R_REL_DAQUI = re.compile(rf"\b(?:daqui(?:\s+a)?|dentro\s+de)\s+{_QTD}\s*(?P<u>horas?|hrs?|hs|h|min(?:utos?)?)\b{_RESTO_REL}")
_R_REL_EM = re.compile(rf"\bem\s+{_QTD}\s*(?P<u>horas?|min(?:utos?)?)\b{_RESTO_REL}")
_R_LIMITE = re.compile(r"\b(?:antes\s+d[aeo]s?|ate\s+(?:a|as|o|os)?)\s*$")  # «antes das 18h», «até as 17»: limite, não horário

# faixa «das 14 às 16h», «de 14 a 16», «15h até 16h»: não é hora única (v1 só hora explícita única)
_FORMATO = rf"(?::\d{{2}}|\s*{_UNID}(?:[0-5]\d)?)"


def _lado_faixa(n: str) -> str:
    return rf"(?P<{n}>\d{{1,2}})(?P<{n}f>{_FORMATO})?(?![\w:])"


_R_FAIXA = re.compile(
    rf"{_ANTES}(?P<pre>(?:de|das?|do)\s+|as\s+)?{_lado_faixa('a')}\s+(?P<mid>as|ate|ao|a)\s+{_lado_faixa('b')}{_NAO_HORA}"
)
# aproximação ou hesitação perto da hora: a hora vale no máximo `media` («depois de amanhã» NÃO é aproximação)
_R_HEDGE = re.compile(
    r"\b(?:por\s+volta|mais\s+ou\s+menos|aproximadamente|aprox|perto\s+d[aeo]s?|la\s+pel[ao]s|pel[ao]s|umas?|uns|tipo|por\s+ai|ou\s+mais"
    r"|a\s+partir|apos|cerca\s+d[aeo]|em\s+torno|quase|talvez|acho\s+que|quem\s+sabe|se\s+der|se\s+puder)\b"
)
_JANELA_ANTES, _JANELA_DEPOIS = 26, 16
# duração, não horário: «trabalho 16 horas por dia», «demora 15 horas», «faz 15h que espero»
_R_DURACAO_ANTES = re.compile(r"\b(?:ha|faz|ja\s+faz|demora\w*|leva\w*|trabalh\w+|espero|esperei|esperando|durante|por)\s+$")
_R_DURACAO_DEPOIS = re.compile(r"^\s*(?:por\s+dia|de\s+(?:trabalho|curso|espera|viagem|fila)|que\s+espero|seguidas?|a\s+fio)\b")
_QN = r"(?:\d{1,3}|uma|um|duas|dois|tres|quatro|cinco|meia)"
_UREL = r"(?:horas?|hrs?|hs|h|min(?:utos?)?)\b"
_R_REL_LISTA = re.compile(
    rf"\b(?:daqui(?:\s+a)?|dentro\s+de|em)\s+(?:{_QN}\s*{_UREL}\s+ou\s+{_QN}(?:\s*{_UREL})?|{_QN}\s+ou\s+{_QN}\s*{_UREL})"
)
_R_CONECTOR_DEPOIS = re.compile(rf"\s+(?:e|ou)\s+(?:as\s+)?(?=\d|(?:{_W}|{_MINW}|uma|um|meio|meia)\b)")
_R_CONECTOR_ANTES = re.compile(r"(\d[\w:]*)\s+(?:e|ou)\s+(?:as\s+)?$")

_R_HOJE = re.compile(r"\b(?:hoje|hj)\b")
_R_DEPOIS_AMANHA = re.compile(r"\bdepois\s+de\s+amanha+\b")
_R_AMANHA = re.compile(r"\b(?:amanha+|amnh|amnha|aman)\b")
_R_SEMANA = re.compile(
    r"(?:\b(?:proxim[ao]|prox)\s+)?\b(?P<d>segunda(?!\s+(?:opcao|vez|via|parcela|proposta|parte))|terca|quarta|quinta|sexta|sabado|domingo|seg|sex|sab)(?:[\s-]*feira)?\b(?P<qv>\s+que\s+vem\b)?"
)
_R_DAQUI_DIAS = re.compile(r"\b(?:daqui(?:\s+a)?|em)\s+(?P<n>\d{1,3})\s+(?P<u>dias?|semanas?)\b")
_MES = "|".join(sorted(_MESES, key=len, reverse=True))
_R_DATA = re.compile(r"(?<![\d/.:,])(?P<d>\d{1,2})/(?P<m>\d{1,2})(?:/(?P<a>\d{4}|\d{2}))?(?![\d/:])")
_R_DIA_MES = re.compile(rf"(?:\bdia\s+)?(?<!\d)(?P<d>\d{{1,2}})\s+de\s+(?P<m>{_MES})\b(?:\s+de\s+(?P<a>\d{{4}}))?")
_R_DIA_N = re.compile(r"\bdia\s+(?P<d>\d{1,2})\b(?![\d:/])")
_R_VAGO = re.compile(
    r"\b(?:semana\s+que\s+vem|proxima\s+semana|semana\s+seguinte|mes\s+que\s+vem|proximo\s+mes|fim\s+de\s+semana|final\s+de\s+semana|fds|outro\s+dia)\b"
)
_R_SEMANA_QV = re.compile(r"\b(?:semana\s+que\s+vem|proxima\s+semana|semana\s+seguinte)\b")
_R_PERIODO_GLOBAL = {
    "manha": re.compile(r"\bmanha\b"),
    "tarde": re.compile(r"(?<!mais )(?<!boa )\btarde\b"),
    "noite": re.compile(r"(?<!boa )\bnoite\b"),
}
_R_PERIODOS = (  # ordem importa: o mais específico primeiro
    ("depois_do_almoco", re.compile(r"\b(?:(?:depois|apos|dps)\s+d[oa]\s+almoco|apos\s+o\s+almoco|depois\s+de\s+almocar)\b")),
    ("almoco", re.compile(r"\b(?:hora\s+do\s+almoco|almoco)\b")),
    ("fim_da_tarde", re.compile(r"\b(?:(?:fim|final)\s+(?:da|de)\s+tarde|tardinha)\b")),
    ("cedo", re.compile(r"\b(?:cedo|cedinho)\b")),
    ("manha", _R_PERIODO_GLOBAL["manha"]),
    ("tarde", _R_PERIODO_GLOBAL["tarde"]),
    ("noite", _R_PERIODO_GLOBAL["noite"]),
)


# ------------------------------------------------------------------------------------------------ menções
@dataclass(frozen=True, slots=True)
class _Hora:
    ini: int
    fim: int
    hora: int = 0  # 24 = meia-noite (00:00 do dia seguinte)
    minuto: int = 0
    alta: bool = False
    fixo: datetime | None = None  # «daqui a 1 hora»: já é um instante


@dataclass(frozen=True, slots=True)
class _Dia:
    ini: int
    fim: int
    data: date
    ambigua: bool = False  # mesmo dia da semana de hoje: hoje ou daqui a 7 dias
    tipo: str = "relativo"  # relativo (hoje/amanhã/daqui a N dias) | semana | data | dia_n («dia 5» sem mês)


@dataclass(slots=True)
class _Varredura:
    n: str
    ocupado: list[bool] = field(init=False)
    horas: list[_Hora] = field(default_factory=list)
    dias: list[_Dia] = field(default_factory=list)
    recusa: str | None = None  # motivo que derruba a frase inteira (intervalo, duração ambígua)
    data_invalida: bool = False  # o cliente DISSE um dia que não existe («31/11»): nunca cair em «hoje»

    def __post_init__(self) -> None:
        self.ocupado = [False] * len(self.n)

    def achados(self, rx: re.Pattern[str], *, consome: bool = True) -> Iterable[re.Match[str]]:
        """Ocorrências que não pisam em trecho já usado. Com `consome=False`, quem chama ocupa o trecho SÓ se o achado valer
        (um «30» de «10h30 da manhã» não é hora: não pode esconder o «10h30»)."""
        for m in rx.finditer(self.n):
            if not any(self.ocupado[m.start() : m.end()]):
                if consome:
                    self.ocupar(m.start(), m.end())
                yield m

    def ocupar(self, ini: int, fim: int) -> None:
        self.ocupado[ini:fim] = [True] * (fim - ini)


def _val(s: str) -> int:
    return int(s) if s.isdigit() else _NUMW[s]


def _periodo_unico(n: str) -> str | None:
    achados = {k for k, rx in _R_PERIODO_GLOBAL.items() if rx.search(n)}
    return achados.pop() if len(achados) == 1 else None


def _resolver(h: int, m: int, qual: str | None, literal24: bool, forte: bool, global_: str | None) -> tuple[int, int, bool] | None:
    """(hora 0-24, minuto, alta) ou None. 1-7 sem qualificador viram tarde («depois das 6» = 18h); 8-12 ficam como estão."""
    if m > 59 or h > 23:
        return None
    if qual is None and not literal24 and h <= 12:
        qual = global_
    assumido = False
    if qual in ("tarde", "noite"):
        hh = h + 12 if h < 12 else (24 if h == 12 and qual == "noite" else h)
        forte = True
    elif qual in ("manha", "madrugada"):
        hh, forte = h, True
    elif literal24 or h == 0 or h >= 8:
        hh = h
    else:
        hh, assumido = h + 12, True
    if hh == 24 and m:
        return None
    return hh, m, forte and not assumido


def _fora_de_contexto(v: _Varredura, m: re.Match[str]) -> bool:
    antes = v.n[max(0, m.start() - 14) : m.start()]
    return bool(re.search(r"r\$\s*$", antes))  # «R$ 15»: dinheiro, não hora


def _tem_hedge(v: _Varredura, ini: int, fim: int) -> bool:
    return bool(_R_HEDGE.search(v.n[max(0, ini - _JANELA_ANTES) : ini] + " " + v.n[fim : fim + _JANELA_DEPOIS]))


def _eh_duracao(v: _Varredura, m: re.Match[str]) -> bool:
    return bool(_R_DURACAO_ANTES.search(v.n[max(0, m.start() - 20) : m.start()]) or _R_DURACAO_DEPOIS.search(v.n[m.end() : m.end() + 24]))


def _lista_incompleta(v: _Varredura) -> bool:
    """Depois de varrer TUDO: «15h e 16h» tem as duas pontas lidas (ambíguo); «15h ou 16:99» e «15 e trinta e cinco» têm uma ponta
    que não virou hora, e então a outra não pode sobrar sozinha (a ordem da varredura não importa)."""
    for h in v.horas:
        seguinte = _R_CONECTOR_DEPOIS.match(v.n, h.fim)
        if seguinte and not v.ocupado[seguinte.end()]:
            return True
        base = max(0, h.ini - 14)
        anterior = _R_CONECTOR_ANTES.search(v.n[base : h.ini])
        if anterior and not v.ocupado[base + anterior.end(1) - 1]:
            return True
    return False


def _registrar_lote(
    v: _Varredura, m: re.Match[str], itens: list[tuple[int, int]], qual: str | None, *, aprox: bool = False, literal24: bool = False,
    forte: bool = True, extra: int = 0,
) -> None:  # fmt: skip
    """Registra todas as horas do achado ou nenhuma: um lado inválido de «15h ou 16:99» derruba a alternativa inteira."""
    if _fora_de_contexto(v, m):
        return
    if _R_LIMITE.search(v.n[max(0, m.start() - 14) : m.start()]):
        v.ocupar(m.start(), m.end())  # «antes das 18h»: limite, não horário marcado (e ninguém mais pega esse trecho)
        return
    if _eh_duracao(v, m):
        v.ocupar(m.start(), m.end())
        return
    aprox = aprox or _tem_hedge(v, m.start(), m.end())
    unico = _periodo_unico(v.n)
    resolvidas = [_resolver(h, mi, qual, literal24, forte, unico) for h, mi in itens]
    if any(r is None for r in resolvidas):
        return
    v.ocupar(m.start(), m.end())
    for r in resolvidas:
        hh, mm, alta = r  # type: ignore[misc]
        total = hh * 60 + mm + extra
        v.horas.append(_Hora(m.start(), m.end(), total // 60, total % 60, alta and extra == 0 and not aprox))


def _registrar(v: _Varredura, m: re.Match[str], h: int, mi: int, qual: str | None, **kw) -> None:
    _registrar_lote(v, m, [(h, mi)], qual, **kw)


def _minutos(grupo: str | None) -> int:
    return _MIN[grupo] if grupo else 0


def _arredondar(alvo: datetime) -> datetime:
    """Sobe para o próximo múltiplo de 5 min (segundos contam: 11:00:01 vai a 11:05)."""
    if alvo.second or alvo.microsecond:
        alvo = alvo.replace(second=0, microsecond=0) + timedelta(minutes=1)
    return alvo + timedelta(minutes=(-alvo.minute) % PASSO_RELATIVO_MIN)


def _escanear_relativo(v: _Varredura, agora: datetime) -> None:
    for _ in v.achados(_R_REL_LISTA):
        v.recusa = "duracao_ambigua"  # «daqui a 1 hora ou 2 horas»: qual duração?
    for rx in (_R_REL_DAQUI, _R_REL_EM):
        for m in v.achados(rx, consome=False):
            w, horas = m["w"], m["u"].startswith("h")
            resto = _MIN[m["mm"]] if m["mm"] else int(m["md"] or 0)
            if (w == "meia" and not horas) or (resto and (not horas or w == "meia")):
                continue  # «daqui meia min», «5 min e meia»: não existem; recusa em vez de aproximar
            minutos = 30 if w == "meia" else (int(m["n"]) if m["n"] else _NUMW[w]) * (60 if horas else 1)
            v.ocupar(m.start(), m.end())
            alvo = _arredondar(agora + timedelta(minutes=minutos + resto))
            v.horas.append(_Hora(m.start(), m.end(), alta=not _tem_hedge(v, m.start(), m.end()), fixo=alvo))


def _literal24(texto_h: str) -> bool:
    return len(texto_h) == 2 and texto_h[0] == "0"


def _escanear_faixa(v: _Varredura) -> None:
    for m in v.achados(_R_FAIXA, consome=False):
        formatada = bool(m["af"] or m["bf"])
        if m["pre"] or formatada or m["mid"] != "a":
            v.ocupar(m.start(), m.end())
            v.recusa = "intervalo"


def _escanear_alternativas(v: _Varredura) -> None:
    for rx in (_R_ENTRE, _R_OU):
        for m in v.achados(rx, consome=False):
            itens = [(int(m[x]), int(m[f"{x}m"] or m[f"{x}n"] or 0)) for x in ("a", "b")]
            _registrar_lote(v, m, itens, m["q"], aprox=True, forte=False)


def _escanear_horas(v: _Varredura, agora: datetime) -> None:
    _escanear_relativo(v, agora)
    _escanear_faixa(v)
    for m in v.achados(_R_MEIODIA, consome=False):
        if m["mnoite"]:
            v.ocupar(m.start(), m.end())
            v.horas.append(_Hora(m.start(), m.end(), 24, _minutos(m["mn"])))  # só a hora cheia do estudo M é «media»: nunca alta
        else:
            _registrar(v, m, 12, _minutos(m["mn"]), None, literal24=True, forte=False)
    _escanear_alternativas(v)
    for m in v.achados(_R_DEPOIS, consome=False):
        _registrar(v, m, _val(m["h"]), 0, None, forte=False, aprox=True, extra=15)
    for m in v.achados(_R_QUAL, consome=False):
        aprox = (m["pre"] or "").startswith("um")
        _registrar(v, m, _val(m["h"]), int(m["m"] or 0) + _minutos(m["mn"]), m["q"], aprox=aprox)
    for m in v.achados(_R_UMAS, consome=False):
        _registrar(v, m, _val(m["h"]), _minutos(m["mn"]), None, forte=False, aprox=True)
    for rx in (_R_HXM, _R_HM):
        for m in v.achados(rx, consome=False):
            _registrar(v, m, int(m["h"]), int(m["m"]), None, literal24=_literal24(m["h"]))
    for m in v.achados(_R_H, consome=False):
        _registrar(v, m, int(m["h"]), _minutos(m["mn"]), None, literal24=_literal24(m["h"]))
    for m in v.achados(_R_AS, consome=False):
        _registrar(v, m, _val(m["h"]), _minutos(m["mn"]), None)
    for m in v.achados(_R_EMEIA, consome=False):
        if not v.n[: m.start()].endswith(("dia ", "r$ ", "r$")):
            _registrar(v, m, _val(m["h"]), _minutos(m["mn"]), None, forte=False)


# ------------------------------------------------------------------------------------------------ dias
def _proxima_data(hoje: date, dia: int) -> date | None:
    ano, mes = hoje.year, hoje.month
    for _ in range(4):
        try:
            d = date(ano, mes, dia)
        except ValueError:
            d = None
        if d is not None and d >= hoje:
            return d
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    return None


def _data_com_mes(hoje: date, dia: int, mes: int, ano: int | None) -> date | None:
    try:
        d = date(ano if ano else hoje.year, mes, dia)
    except ValueError:
        return None
    if ano is None and (hoje - d).days > 90:  # «03/01» dito em dezembro é janeiro do ano que vem
        try:
            d = d.replace(year=d.year + 1)
        except ValueError:  # 29/02 e o ano seguinte não é bissexto
            return None
    return d


def _dias_da_semana(v: _Varredura, hoje: date) -> None:
    proxima_semana = bool(_R_SEMANA_QV.search(v.n))
    for m in v.achados(_R_SEMANA):
        alvo = _DIAS_SEMANA[m["d"]]
        forca_semana = bool(m["qv"]) or m.group(0).lstrip().startswith("prox")
        if proxima_semana:
            v.dias.append(_Dia(m.start(), m.end(), hoje - timedelta(days=hoje.weekday()) + timedelta(days=7 + alvo), tipo="semana"))
            continue
        delta = (alvo - hoje.weekday()) % 7
        if delta == 0 and not forca_semana:
            v.dias.append(_Dia(m.start(), m.end(), hoje, ambigua=True, tipo="semana"))
            v.dias.append(_Dia(m.start(), m.end(), hoje + timedelta(days=7), ambigua=True, tipo="semana"))
        else:
            v.dias.append(_Dia(m.start(), m.end(), hoje + timedelta(days=delta or 7), tipo="semana"))


def _escanear_dias(v: _Varredura, hoje: date) -> None:
    for m in v.achados(_R_DAQUI_DIAS):
        passo = int(m["n"]) * (7 if m["u"].startswith("sem") else 1)
        v.dias.append(_Dia(m.start(), m.end(), hoje + timedelta(days=passo)))
    for m in v.achados(_R_DATA):
        ano = (int(m["a"]) + (2000 if len(m["a"]) == 2 else 0)) if m["a"] else None
        d = _data_com_mes(hoje, int(m["d"]), int(m["m"]), ano)
        if d:
            v.dias.append(_Dia(m.start(), m.end(), d, tipo="data"))
        else:
            v.data_invalida = True
    for m in v.achados(_R_DIA_MES):
        d = _data_com_mes(hoje, int(m["d"]), _MESES[m["m"]], int(m["a"]) if m["a"] else None)
        if d:
            v.dias.append(_Dia(m.start(), m.end(), d, tipo="data"))
        else:
            v.data_invalida = True
    for m in v.achados(_R_DIA_N):
        d = _proxima_data(hoje, int(m["d"])) if 1 <= int(m["d"]) <= 31 else None
        if d:
            v.dias.append(_Dia(m.start(), m.end(), d, tipo="dia_n"))
        else:
            v.data_invalida = True
    for rx, passo in ((_R_DEPOIS_AMANHA, 2), (_R_AMANHA, 1), (_R_HOJE, 0)):
        for m in v.achados(rx):
            v.dias.append(_Dia(m.start(), m.end(), hoje + timedelta(days=passo)))
    _dias_da_semana(v, hoje)
    # «sexta 20/11»: o dia da semana só confirma a data; se não bate com nenhuma data dita, fica (e o resultado é ambíguo)
    semanas_das_datas = {d.data.weekday() for d in v.dias if d.tipo in ("data", "dia_n")}
    v.dias[:] = [d for d in v.dias if not (d.tipo == "semana" and d.data.weekday() in semanas_das_datas)]


# ------------------------------------------------------------------------------------------------ regras duras
def _dia_util(d: date, cfg: ConfigAgenda) -> bool:
    tem_envio = cfg.janela_mensagem is None or d.isoweekday() in cfg.janela_mensagem
    return (cfg.domingo_aberto or d.weekday() != 6) and d not in cfg.feriados and tem_envio


def _razoes_do_envio(q: datetime, cfg: ConfigAgenda) -> set[str]:
    """A volta fora do horário de ENVIO do dia (`janela_mensagem`, fim exclusivo como `Calendario.dentro_da_janela`)."""
    if cfg.janela_mensagem is None or (q.weekday() == 6 and not cfg.domingo_aberto):
        return set()  # domingo fechado já tem a razão «domingo»
    envio = cfg.janela_mensagem.get(q.isoweekday())
    if envio is None:
        return {"dia_sem_janela"}
    if q.time() < envio[0]:
        return {"antes_da_janela"}
    return {"depois_da_janela"} if q.time() >= envio[1] else set()


def _teto(agora: datetime, ultima: datetime, cfg: ConfigAgenda) -> datetime:
    d = agora.date() + timedelta(days=1)
    for _ in range(14):
        if _dia_util(d, cfg):
            break
        d += timedelta(days=1)
    return min(ultima + timedelta(hours=cfg.teto_horas), datetime.combine(d, _hhmm(cfg.teto_dia_util_fim, "teto"), tzinfo=FUSO))


def _razoes(q: datetime, agora: datetime, teto: datetime, cfg: ConfigAgenda) -> tuple[str, ...]:
    achadas = set()
    if q.date() in cfg.feriados:
        achadas.add("feriado")
    if any(ini <= q < fim for ini, fim in cfg.bloqueios):
        achadas.add("bloqueio_dataprev")
    if q.weekday() == 6 and not cfg.domingo_aberto:
        achadas.add("domingo")
    if q <= agora:
        achadas.add("passado")
    elif q < agora + timedelta(minutes=cfg.antecedencia_min):
        achadas.add("antecedencia")
    fim = cfg.sabado_fim if q.weekday() == 5 and cfg.sabado_fim else cfg.janela_fim
    if q.time() < _hhmm(cfg.janela_inicio, "janela_inicio"):
        achadas.add("antes_da_janela")
    elif q.time() > _hhmm(fim, "janela_fim"):
        achadas.add("depois_da_janela")
    if q > teto:
        achadas.add("acima_do_teto")
    achadas |= _razoes_do_envio(q, cfg)
    return tuple(r for r in RAZOES if r in achadas)


# ------------------------------------------------------------------------------------------------ montagem
def _instante(dia: date, hora: _Hora) -> datetime:
    base = datetime.combine(dia, time(hora.hora % 24, hora.minuto), tzinfo=FUSO)
    return base + timedelta(days=1) if hora.hora == 24 else base


def _par(agora: datetime, dia: _Dia | None, hora: _Hora) -> tuple[datetime, Confianca, int, int]:
    """(instante, confiança, início, fim do trecho de origem)."""
    conf: Confianca = "alta" if hora.alta else "media"
    if dia is not None:
        return _instante(dia.data, hora), ("media" if dia.ambigua else conf), min(dia.ini, hora.ini), max(dia.fim, hora.fim)
    hoje = _instante(agora.date(), hora)
    if hoje <= agora:
        return _instante(agora.date() + timedelta(days=1), hora), "media", hora.ini, hora.fim
    return hoje, conf, hora.ini, hora.fim


def _escanear_periodos(v: _Varredura, cfg: ConfigAgenda) -> list[tuple[int, int, time]]:
    achados = []
    for chave, rx in _R_PERIODOS:
        for m in v.achados(rx):
            if chave in cfg.periodos:
                achados.append((m.start(), m.end(), _hhmm(cfg.periodos[chave], f"periodos[{chave}]")))
    return achados


def _par_fixo(v: _Varredura, hora: _Hora) -> list[tuple[datetime, Confianca, int, int]] | str:
    """«daqui a 1 hora» já é um instante: se o cliente também disse um dia, o instante tem de cair nele."""
    if not v.dias:
        return [(hora.fixo, "alta" if hora.alta else "media", hora.ini, hora.fim)]  # type: ignore[list-item]
    iguais = [d for d in v.dias if d.data == hora.fixo.date()]  # type: ignore[union-attr]
    if not iguais:
        return "dia_contraditorio"
    conf: Confianca = "alta" if hora.alta and len(iguais) == len(v.dias) else "media"  # «hoje ou amanhã daqui a 1 hora» continua ambíguo
    return [(hora.fixo, conf, min([hora.ini, *(d.ini for d in iguais)]), max([hora.fim, *(d.fim for d in iguais)]))]  # type: ignore[list-item]


def _combinar(v: _Varredura, agora: datetime, cfg: ConfigAgenda) -> list[tuple[datetime, Confianca, int, int]] | str:
    periodos = _escanear_periodos(v, cfg) if cfg.usa_periodos and not v.horas else []
    if v.recusa:
        return v.recusa
    if v.horas and _lista_incompleta(v):
        return "hora_incompleta"
    if v.data_invalida and (v.horas or periodos):
        return "data_invalida"
    if _R_VAGO.search(v.n) and (not v.dias or any(d.tipo == "dia_n" for d in v.dias)):  # «semana que vem às 15»: não adivinha o dia
        return "dia_nao_resolvido" if (v.horas or periodos) else "sem_hora_explicita"
    if v.horas:
        saida = []
        for h in v.horas:
            achado = _par_fixo(v, h) if h.fixo is not None else [_par(agora, d, h) for d in (v.dias or [None])]
            if isinstance(achado, str):
                return achado  # uma contradição derruba a frase toda (nada sobra como alta)
            saida += achado
        return saida
    saida = []
    for ini, fim, hhmm in periodos:
        for d in v.dias or [None]:
            q, _, a, b = _par(agora, d, _Hora(ini, fim, hhmm.hour, hhmm.minute))
            saida.append((q, "media" if d is not None else "baixa", a, b))
    return saida or "sem_hora_explicita"


def _local(valor: datetime, nome: str) -> datetime:
    if not isinstance(valor, datetime) or valor.tzinfo is None or valor.utcoffset() is None:
        raise ValueError(f"{nome} precisa ser datetime com fuso (tz-aware)")
    return valor.astimezone(FUSO)


def extrair(texto: str, agora: datetime, ultima_msg_cliente_em: datetime, config: ConfigAgenda) -> Resultado:
    """Extrai candidatos de horário de `texto`. Veja o docstring do módulo para o contrato."""
    if not isinstance(texto, str):
        raise TypeError("texto precisa ser str")
    agora_l = _local(agora, "agora")  # com segundos: a antecedência de 10 min é medida no instante real
    ultima_l = _local(ultima_msg_cliente_em, "ultima_msg_cliente_em")
    if len(texto) > MAX_TEXTO:
        return Resultado((), "texto_longo")
    v = _Varredura(_normalizar(texto))
    _escanear_dias(v, agora_l.date())
    _escanear_horas(v, agora_l)
    pares = _combinar(v, agora_l, config)
    if isinstance(pares, str):
        return Resultado((), pares)
    unicos: dict[datetime, tuple[Confianca, int, int]] = {}
    for q, conf, ini, fim in pares:
        unicos.setdefault(q, (conf, ini, fim))
    if len(unicos) > MAX_CANDIDATOS:
        return Resultado((), "ambiguo_demais")
    teto = _teto(agora_l, ultima_l, config)
    candidatos = []
    for q in sorted(unicos):
        conf, ini, fim = unicos[q]
        if len(unicos) > 1 and _ORDEM_CONFIANCA[conf] > _ORDEM_CONFIANCA["media"]:
            conf = "media"
        razoes = _razoes(q, agora_l, teto, config)
        candidatos.append(Candidato(q, conf, texto[ini:fim], bool(razoes), razoes))
    motivo = None if any(not c.fora_da_janela for c in candidatos) else candidatos[0].razoes[0]
    return Resultado(tuple(candidatos), motivo)
