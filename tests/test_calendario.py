"""Calendário de mensagem: janela 08–20 seg–sáb em America/Sao_Paulo, feriados e DATAPREV. Hora local calculada no código."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

import pytest

from ia_atendimento.calendario import (
    FERIADOS_MINIMOS,
    HORA_BLOQUEIO_ENTRADA,
    Calendario,
    CalendarioInvalido,
    carregar_calendario,
    cron_utc,
    validar_calendario_bloqueio,
    validar_janela_mensagem,
)

DIA = {"inicio": "08:00", "fim": "20:00"}
JANELA = {"dias": {str(d): dict(DIA) for d in range(1, 7)}}
BLOQUEIO = {
    "domingos": True,
    "feriados": ["2026-11-02", "2026-11-20"],
    "janelas": [{"de": "2026-11-20T22:00:00-03:00", "ate": "2026-11-23T06:00:00-03:00", "motivo": "dataprev"}],
}


def utc(ano: int, mes: int, dia: int, h: int = 0, m: int = 0, s: int = 0) -> datetime:
    return datetime(ano, mes, dia, h, m, s, tzinfo=UTC)


@pytest.fixture
def cal() -> Calendario:
    return carregar_calendario(JANELA, BLOQUEIO)


def test_hora_local_vem_do_codigo_nao_do_banco(cal: Calendario):
    # terça 17/11/2026: 22:30 UTC = 19:30 em São Paulo (dentro); 23:30 UTC = 20:30 (fora)
    assert cal.dentro_da_janela(utc(2026, 11, 17, 22, 30)) is True
    assert cal.dentro_da_janela(utc(2026, 11, 17, 23, 30)) is False
    # bordas: 08:00 local (11:00 UTC) entra; 20:00 local (23:00 UTC) já saiu; 07:59:59 local não
    assert cal.dentro_da_janela(utc(2026, 11, 17, 11, 0)) is True
    assert cal.dentro_da_janela(utc(2026, 11, 17, 10, 59, 59)) is False
    assert cal.dentro_da_janela(utc(2026, 11, 17, 22, 59, 59)) is True
    assert cal.dentro_da_janela(utc(2026, 11, 17, 23, 0)) is False


def test_calendario_domingo_feriado_e_dataprev(cal: Calendario):
    meio_dia = (15, 0)  # 12:00 em SP = 15:00 UTC
    assert cal.dentro_da_janela(utc(2026, 11, 14, *meio_dia)) is True  # sábado
    assert cal.dentro_da_janela(utc(2026, 11, 15, *meio_dia)) is False  # domingo
    assert cal.bloqueado(utc(2026, 11, 15, *meio_dia)) is True
    assert cal.dentro_da_janela(utc(2026, 11, 2, *meio_dia)) is False  # segunda, feriado
    assert cal.bloqueado(utc(2026, 11, 2, *meio_dia)) is True
    assert cal.dentro_da_janela(utc(2026, 11, 20, *meio_dia)) is False  # sexta, feriado
    # DATAPREV: 20/11 22:00 SP (21/11 01:00 UTC) até 23/11 06:00 SP (09:00 UTC)
    assert cal.bloqueado(utc(2026, 11, 21, 0, 59)) is True  # ainda feriado de 20/11
    assert cal.bloqueado(utc(2026, 11, 21, 15, 0)) is True  # sábado 12:00 SP, dentro da janela
    assert cal.dentro_da_janela(utc(2026, 11, 21, 15, 0)) is False
    assert cal.bloqueado(utc(2026, 11, 23, 8, 59)) is True  # 05:59 SP
    assert cal.bloqueado(utc(2026, 11, 23, 9, 0)) is False  # 06:00 SP: a janela fecha
    assert cal.dentro_da_janela(utc(2026, 11, 23, 9, 0)) is False  # mas só abre às 08:00
    assert cal.dentro_da_janela(utc(2026, 11, 23, 11, 0)) is True
    # dia útil comum não é bloqueado
    assert cal.bloqueado(utc(2026, 11, 17, *meio_dia)) is False


def test_proxima_janela_pula_domingo_feriado_e_dataprev(cal: Calendario):
    dentro = utc(2026, 11, 17, 15, 0)
    assert cal.proxima_janela(dentro) == dentro  # já dentro: o próprio instante
    assert cal.proxima_janela(utc(2026, 11, 17, 23, 30)) == utc(2026, 11, 18, 11, 0)  # terça 20:30 -> quarta 08:00
    assert cal.proxima_janela(utc(2026, 11, 14, 23, 30)) == utc(2026, 11, 16, 11, 0)  # sábado 20:30 -> segunda 08:00
    assert cal.proxima_janela(utc(2026, 10, 31, 23, 30)) == utc(
        2026, 11, 3, 11, 0
    )  # sáb 31/10 20:30 -> dom, seg 02/11 feriado -> terça 03/11
    assert cal.proxima_janela(utc(2026, 11, 20, 15, 0)) == utc(2026, 11, 23, 11, 0)  # feriado + DATAPREV -> segunda 23/11 08:00
    assert cal.proxima_janela(utc(2026, 11, 23, 6, 0)) == utc(2026, 11, 23, 11, 0)  # 03:00 SP, ainda bloqueado


def test_instante_sem_fuso_e_recusado(cal: Calendario):
    ingenuo = datetime(2026, 11, 17, 12, 0)
    for chamada in (cal.dentro_da_janela, cal.bloqueado, cal.proxima_janela):
        with pytest.raises(ValueError, match="fuso"):
            chamada(ingenuo)


def test_janela_mensagem_da_config_nunca_passa_de_20h():
    validar_janela_mensagem(JANELA)
    invalidas = {
        "domingo": {"dias": {**JANELA["dias"], "7": dict(DIA)}},
        "fim_20h30": {"dias": {"1": {"inicio": "08:00", "fim": "20:30"}}},
        "inicio_07h": {"dias": {"1": {"inicio": "07:00", "fim": "18:00"}}},
        "invertida": {"dias": {"1": {"inicio": "12:00", "fim": "12:00"}}},
        "dia_fora": {"dias": {"0": dict(DIA)}},
        "hora_ruim": {"dias": {"1": {"inicio": "8h", "fim": "20:00"}}},
        "sem_dias": {"dias": {}},
        "forma": {"outra": 1},
    }
    for nome, valor in invalidas.items():
        with pytest.raises(CalendarioInvalido):
            validar_janela_mensagem(valor)
        assert nome  # a mensagem do teste mostra qual caso falhou


def test_calendario_bloqueio_exige_domingo_feriados_e_dataprev_minimos():
    validar_calendario_bloqueio(BLOQUEIO)
    assert {date(2026, 11, 2), date(2026, 11, 20)} <= FERIADOS_MINIMOS
    sem_domingo = {**BLOQUEIO, "domingos": False}
    sem_20_11 = {**BLOQUEIO, "feriados": ["2026-11-02"]}
    sem_dataprev = {**BLOQUEIO, "janelas": []}
    dataprev_curta = {
        **BLOQUEIO,
        "janelas": [{"de": "2026-11-20T22:00:00-03:00", "ate": "2026-11-22T06:00:00-03:00", "motivo": "dataprev"}],
    }
    sem_fuso = {**BLOQUEIO, "janelas": [{"de": "2026-11-20T22:00:00", "ate": "2026-11-23T06:00:00", "motivo": "dataprev"}]}
    invertida = {
        **BLOQUEIO,
        "janelas": [*BLOQUEIO["janelas"], {"de": "2026-12-01T10:00:00-03:00", "ate": "2026-12-01T09:00:00-03:00", "motivo": "x"}],
    }
    data_ruim = {**BLOQUEIO, "feriados": [*BLOQUEIO["feriados"], "02/11/2026"]}
    for valor in (sem_domingo, sem_20_11, sem_dataprev, dataprev_curta, sem_fuso, invertida, data_ruim, {"domingos": True}):
        with pytest.raises(CalendarioInvalido):
            validar_calendario_bloqueio(valor)


def test_feriado_ou_janela_a_mais_da_config_vale():
    com_extra = {
        **BLOQUEIO,
        "feriados": [*BLOQUEIO["feriados"], "2026-12-25"],
        "janelas": [*BLOQUEIO["janelas"], {"de": "2026-12-10T12:00:00-03:00", "ate": "2026-12-10T14:00:00-03:00", "motivo": "manutencao"}],
    }
    cal = carregar_calendario(JANELA, com_extra)
    assert cal.dentro_da_janela(utc(2026, 12, 25, 15, 0)) is False  # sexta 25/12
    assert cal.dentro_da_janela(utc(2026, 12, 10, 16, 0)) is False  # 13:00 SP, dentro da janela extra
    assert cal.dentro_da_janela(utc(2026, 12, 10, 18, 0)) is True  # 15:00 SP, depois dela


def test_hora_do_bloqueio_diario_em_utc_vem_da_hora_local():
    assert time(20, 15) == HORA_BLOQUEIO_ENTRADA
    assert cron_utc(HORA_BLOQUEIO_ENTRADA, date(2026, 11, 12)) == "15 23 * * *"
    assert cron_utc(time(3, 30), date(2026, 11, 12)) == "30 6 * * *"
