"""Calendário do atendimento (J8; M §2.4; ROTEIRO «20/11 IA desligada, janela DATAPREV 20/11 22:00 a 23/11 06:00»).

Domingo (D-18, B1.8): `domingo_aberto` (padrão `False`) é o estado das duas chaves do `calendario.py` do orquestrador. Fechado, o domingo é
bloqueado como antes; aberto, vale 08–20 e a agenda 08:30–19:00. Feriados (15/11 inclusive) e a DATAPREV seguem bloqueados nos dois
estados. As regras da F3 (I3, gabarito, agenda) ainda chamam com o padrão: passar o estado a elas é da B8.1c.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, timezone

from ia_atendimento.calendario import janela_dataprev_em

FUSO_SP = timezone(timedelta(hours=-3), "America/Sao_Paulo")  # sem horário de verão desde 2019
FERIADOS_2026: frozenset[date] = frozenset(
    date(2026, m, d) for m, d in ((1, 1), (4, 3), (4, 21), (5, 1), (6, 4), (9, 7), (10, 12), (11, 2), (11, 15), (11, 20), (12, 25))
)
ABRE, FECHA = time(8, 0), time(20, 0)  # atendimento geral (TX-28)
AGENDA_ABRE, AGENDA_FECHA, AGENDA_SABADO_FIM = time(8, 30), time(19, 0), time(12, 0)  # janela da volta combinada (M §2.4)
ANTECEDENCIA_MINIMA = timedelta(minutes=10)


def _local(instante: datetime) -> datetime:
    if instante.tzinfo is None:
        raise ValueError("instante sem fuso")
    return instante.astimezone(FUSO_SP)


def _dia_bloqueado(local: datetime, domingo_aberto: bool) -> bool:
    domingo_fechado = local.weekday() == 6 and not domingo_aberto
    return domingo_fechado or local.date() in FERIADOS_2026 or janela_dataprev_em(local) is not None  # mensal (DEC-PIA-011)


def dentro_do_horario(instante: datetime, *, domingo_aberto: bool = False) -> bool:
    """08:00 ≤ hora < 20:00 em São Paulo (seg–sáb; domingo só aberto), fora de feriado e da janela DATAPREV (nada sai fora disso: I3)."""
    local = _local(instante)
    return not _dia_bloqueado(local, domingo_aberto) and ABRE <= local.time() < FECHA


def dentro_da_agenda(instante: datetime, *, domingo_aberto: bool = False) -> bool:
    """Janela da VOLTA combinada: 08:30–19:00 (sábado até 12:00; domingo só aberto), fora de feriado e DATAPREV."""
    local = _local(instante)
    if _dia_bloqueado(local, domingo_aberto):
        return False
    fim = AGENDA_SABADO_FIM if local.weekday() == 5 else AGENDA_FECHA
    return AGENDA_ABRE <= local.time() <= fim


def cenarios_do_instante(instante: datetime) -> set[str]:
    """Rótulos de `CenarioTempo` que descrevem o instante (um instante pode ter mais de um, ex.: sábado e virada DATAPREV)."""
    local = _local(instante)
    rotulos: set[str] = set()
    na_janela = janela_dataprev_em(local) is not None
    if dentro_do_horario(instante) and local.weekday() < 5:
        rotulos.add("horario_normal")
    if local.weekday() < 6 and local.date() not in FERIADOS_2026 and not na_janela and not ABRE <= local.time() < FECHA:
        rotulos.add("noite")
    if local.weekday() == 5:
        rotulos.add("sabado")
    if local.weekday() == 6:
        rotulos.add("domingo")
    if local.date() == date(2026, 11, 20):
        rotulos.add("feriado_20_11")
    if na_janela:
        rotulos.add("virada_dataprev")
    if instante.astimezone(UTC).time() == time(22, 30) and dentro_do_horario(instante):
        rotulos.add("virada_22h30_utc")
    return rotulos
