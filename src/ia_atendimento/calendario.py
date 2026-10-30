"""Calendário de mensagem ao cliente: janela seg–sáb 08–20 em America/Sao_Paulo, feriados e janelas de bloqueio (DATAPREV).

- A **fonte** é a config (`janela_mensagem`, `calendario_bloqueio`); o código só **valida** (`validar_*`) e aplica. A validação é um piso:
  a janela nunca passa de 08:00–20:00 nem inclui domingo; o calendário sempre bloqueia domingo, os feriados de 02/11 e 20/11/2026 e a
  janela da DATAPREV (20/11 22:00 → 23/11 06:00). A config pode ACRESCENTAR feriados e janelas, nunca tirar esses.
- A hora local é calculada AQUI (zoneinfo), nunca pelo fuso do banco (o cluster é UTC) e nunca pelo `datetime.now()`: toda função recebe o
  instante (ciente de fuso) de um `Relogio` injetado.
- Imutável: `Calendario` é um dataclass congelado; carregar de novo = chamar `carregar_calendario` com a config vigente.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
INICIO_MINIMO = time(8, 0)
FIM_MAXIMO = time(20, 0)
DIAS_ISO = frozenset(range(1, 7))  # seg..sáb; domingo (7) nunca
HORA_BLOQUEIO_ENTRADA = time(20, 15)  # B6.7: a tarefa diária grava bloqueio_entrada=true neste horário local
FERIADOS_MINIMOS = frozenset({date(2026, 11, 2), date(2026, 11, 20)})
DATAPREV_DE = datetime(2026, 11, 20, 22, 0, tzinfo=FUSO)
DATAPREV_ATE = datetime(2026, 11, 23, 6, 0, tzinfo=FUSO)
_HORA = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
_LIMITE_PASSOS = 64  # cada passo avança para o próximo início/fim de janela: 64 cobre meses de feriados e janelas emendadas


class CalendarioInvalido(ValueError):
    """Config de calendário fora do piso do código. A mensagem diz só campo e regra, nunca o valor inteiro."""


@dataclass(frozen=True)
class JanelaBloqueio:
    de: datetime
    ate: datetime
    motivo: str

    def contem(self, instante: datetime) -> bool:
        return self.de <= instante < self.ate


@dataclass(frozen=True)
class Calendario:
    dias: Mapping[int, tuple[time, time]]  # dia ISO 1..6 -> (início, fim) local; fim exclusivo
    feriados: frozenset[date]
    janelas: tuple[JanelaBloqueio, ...]

    def bloqueado(self, agora: datetime) -> bool:
        """Domingo, feriado ou dentro de uma janela de bloqueio (vale mesmo com a chave ligada)."""
        local = _local(agora)
        return local.isoweekday() == 7 or local.date() in self.feriados or self._janela_bloqueio_em(agora) is not None

    def dentro_da_janela(self, agora: datetime) -> bool:
        """Pode mandar mensagem ao cliente neste instante?"""
        if self.bloqueado(agora):
            return False
        local = _local(agora)
        horario = self.dias.get(local.isoweekday())
        return horario is not None and horario[0] <= local.time() < horario[1]

    def proxima_janela(self, agora: datetime) -> datetime:
        """Primeiro instante (UTC) em que se pode mandar mensagem, a partir de `agora` (o próprio `agora` se já está dentro)."""
        instante = _utc(agora)
        for _ in range(_LIMITE_PASSOS):
            if self.dentro_da_janela(instante):
                return instante
            janela = self._janela_bloqueio_em(instante)
            instante = janela.ate if janela else self._proximo_inicio(instante)
        raise CalendarioInvalido("calendário sem janela livre nos próximos passos: confira feriados e janelas")

    def _janela_bloqueio_em(self, instante: datetime) -> JanelaBloqueio | None:
        return next((j for j in self.janelas if j.contem(instante)), None)

    def _proximo_inicio(self, instante: datetime) -> datetime:
        """Menor início de janela de mensagem estritamente depois de `instante` (ignora feriados: quem chama repete o teste)."""
        local = _local(instante)
        for avanco in range(0, 15):
            dia = local.date() + timedelta(days=avanco)
            horario = self.dias.get(dia.isoweekday())
            if horario is None:
                continue
            inicio = datetime.combine(dia, horario[0], tzinfo=FUSO)
            if inicio > local:
                return inicio.astimezone(UTC)
        raise CalendarioInvalido("janela_mensagem sem nenhum dia útil")


def _utc(instante: datetime) -> datetime:
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("o calendário só aceita instante com fuso (venha de um Relogio)")
    return instante.astimezone(UTC)


def _local(instante: datetime) -> datetime:
    return _utc(instante).astimezone(FUSO)


def carregar_calendario(janela_mensagem: Mapping[str, Any], calendario_bloqueio: Mapping[str, Any]) -> Calendario:
    """Valida as duas chaves da config e monta o `Calendario`. Levanta `CalendarioInvalido` se alguma fugir do piso."""
    dias = validar_janela_mensagem(janela_mensagem)
    feriados, janelas = validar_calendario_bloqueio(calendario_bloqueio)
    return Calendario(dias=dias, feriados=feriados, janelas=janelas)


def validar_janela_mensagem(valor: Mapping[str, Any]) -> dict[int, tuple[time, time]]:
    """`{"dias": {"1": {"inicio": "08:00", "fim": "20:00"}, ...}}`: só seg–sáb, dentro de 08:00–20:00, início < fim."""
    dias = valor.get("dias") if isinstance(valor, Mapping) else None
    if not isinstance(dias, Mapping) or not dias:
        raise CalendarioInvalido("janela_mensagem.dias deve ser um objeto com ao menos um dia")
    resultado: dict[int, tuple[time, time]] = {}
    for chave, horario in dias.items():
        if not (isinstance(chave, str) and chave.isdigit() and int(chave) in DIAS_ISO):
            raise CalendarioInvalido("janela_mensagem.dias aceita só os dias 1 a 6 (segunda a sábado; domingo nunca)")
        inicio, fim = _hora(horario, "inicio"), _hora(horario, "fim")
        if not (INICIO_MINIMO <= inicio < fim <= FIM_MAXIMO):
            raise CalendarioInvalido("janela_mensagem: cada dia deve ficar entre 08:00 e 20:00, com início antes do fim")
        resultado[int(chave)] = (inicio, fim)
    return resultado


def _hora(horario: Any, campo: str) -> time:
    texto = horario.get(campo) if isinstance(horario, Mapping) else None
    if not (isinstance(texto, str) and _HORA.fullmatch(texto)):
        raise CalendarioInvalido(f"janela_mensagem: {campo} deve ser HH:MM")
    return time(int(texto[:2]), int(texto[3:]))


def validar_calendario_bloqueio(valor: Mapping[str, Any]) -> tuple[frozenset[date], tuple[JanelaBloqueio, ...]]:
    """`{"domingos": true, "feriados": ["AAAA-MM-DD"...], "janelas": [{"de", "ate", "motivo"}...]}` com o piso do código."""
    if not isinstance(valor, Mapping) or valor.get("domingos") is not True:
        raise CalendarioInvalido("calendario_bloqueio.domingos deve ser true (domingo nunca recebe mensagem)")
    feriados = frozenset(_data(item) for item in _lista(valor, "feriados"))
    janelas = tuple(_janela(item) for item in _lista(valor, "janelas"))
    if not feriados >= FERIADOS_MINIMOS:
        raise CalendarioInvalido("calendario_bloqueio.feriados não pode tirar 02/11/2026 nem 20/11/2026")
    if not any(j.de <= DATAPREV_DE and j.ate >= DATAPREV_ATE for j in janelas):
        raise CalendarioInvalido("calendario_bloqueio.janelas deve cobrir a DATAPREV (20/11/2026 22:00 a 23/11/2026 06:00, São Paulo)")
    return feriados, janelas


def _lista(valor: Mapping[str, Any], campo: str) -> list[Any]:
    itens = valor.get(campo)
    if not isinstance(itens, list):
        raise CalendarioInvalido(f"calendario_bloqueio.{campo} deve ser uma lista")
    return itens


def _data(texto: Any) -> date:
    try:
        if not isinstance(texto, str) or len(texto) != 10:
            raise ValueError
        return date.fromisoformat(texto)
    except ValueError:
        raise CalendarioInvalido("calendario_bloqueio.feriados deve ter datas AAAA-MM-DD") from None


def _janela(item: Any) -> JanelaBloqueio:
    if not isinstance(item, Mapping) or not isinstance(item.get("motivo"), str) or not item["motivo"]:
        raise CalendarioInvalido("calendario_bloqueio.janelas: cada item precisa de de, ate e motivo")
    de, ate = _instante(item.get("de")), _instante(item.get("ate"))
    if de >= ate:
        raise CalendarioInvalido("calendario_bloqueio.janelas: 'de' deve ser antes de 'ate'")
    return JanelaBloqueio(de=de, ate=ate, motivo=item["motivo"])


def _instante(texto: Any) -> datetime:
    try:
        if not isinstance(texto, str):
            raise ValueError
        instante = datetime.fromisoformat(texto)
    except ValueError:
        raise CalendarioInvalido("calendario_bloqueio.janelas: de/ate devem ser ISO 8601 com fuso") from None
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise CalendarioInvalido("calendario_bloqueio.janelas: de/ate devem ter fuso (ex.: -03:00)")
    return instante.astimezone(UTC)


def cron_utc(hora_local: time, em: date) -> str:
    """Expressão cron (UTC) do horário local diário `hora_local`, pelo deslocamento de São Paulo em `em`.

    O Procrastinate agenda tarefas periódicas em UTC; o horário de negócio é local. Sem horário de verão desde 2019 o resultado é fixo
    (20:15 -> `15 23 * * *`); se o horário de verão voltar, `em` (a data de referência) muda o resultado e o cron é regerado no boot.
    """
    local = datetime.combine(em, hora_local, tzinfo=FUSO).astimezone(UTC)
    return f"{local.minute} {local.hour} * * *"


def limites_do_dia(agora: datetime) -> tuple[datetime, datetime]:
    """[início, fim) do dia local de São Paulo que contém `agora`, em UTC. Gasto e disparos do dia contam por este intervalo."""
    local = _local(agora)
    inicio = datetime.combine(local.date(), time(0, 0), tzinfo=FUSO)
    return inicio.astimezone(UTC), datetime.combine(local.date() + timedelta(days=1), time(0, 0), tzinfo=FUSO).astimezone(UTC)


def limites_do_mes(agora: datetime) -> tuple[datetime, datetime]:
    """[início, fim) do mês local de São Paulo que contém `agora`, em UTC."""
    local = _local(agora)
    primeiro = local.date().replace(day=1)
    seguinte = (primeiro + timedelta(days=32)).replace(day=1)
    return (
        datetime.combine(primeiro, time(0, 0), tzinfo=FUSO).astimezone(UTC),
        datetime.combine(seguinte, time(0, 0), tzinfo=FUSO).astimezone(UTC),
    )
