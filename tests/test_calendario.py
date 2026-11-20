"""Calendário de mensagem: janela 08–20 em America/Sao_Paulo, feriados e DATAPREV. Hora local calculada no código.

Domingo (D-18, B1.8): fechado por padrão; só abre com as DUAS chaves juntas, `calendario_bloqueio.domingos=false` e `janela_mensagem.dias."7"`.
"""

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
    limites_do_dia,
    limites_do_mes,
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
JANELA_COM_DOMINGO = {"dias": {**JANELA["dias"], "7": {"inicio": "09:00", "fim": "18:00"}}}
BLOQUEIO_SEM_DOMINGO = {**BLOQUEIO, "domingos": False}
# casos de domingo aberto usam 08/11 e 29/11: 15/11 é feriado no corpus (não no piso do código) e 22/11 cai na DATAPREV
DOMINGO_08 = (2026, 11, 8)
DOMINGO_29 = (2026, 11, 29)


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


@pytest.mark.parametrize("domingo_aberto", [False, True], ids=["domingo_fechado", "domingo_aberto"])
def test_calendario_domingo_feriado_e_dataprev(domingo_aberto: bool):
    cal = carregar_calendario(JANELA_COM_DOMINGO, BLOQUEIO_SEM_DOMINGO) if domingo_aberto else carregar_calendario(JANELA, BLOQUEIO)
    meio_dia = (15, 0)  # 12:00 em SP = 15:00 UTC
    assert cal.dentro_da_janela(utc(2026, 11, 14, *meio_dia)) is True  # sábado
    for domingo in (DOMINGO_08, DOMINGO_29):
        assert cal.dentro_da_janela(utc(*domingo, *meio_dia)) is domingo_aberto, domingo
        assert cal.bloqueado(utc(*domingo, *meio_dia)) is not domingo_aberto, domingo
    assert cal.dentro_da_janela(utc(2026, 11, 22, *meio_dia)) is False  # domingo dentro da DATAPREV: fechado nos dois estados
    assert cal.bloqueado(utc(2026, 11, 22, *meio_dia)) is True
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
        "domingo_07h": {"dias": {**JANELA["dias"], "7": {"inicio": "07:00", "fim": "12:00"}}},
        "domingo_20h30": {"dias": {**JANELA["dias"], "7": {"inicio": "09:00", "fim": "20:30"}}},
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


def test_calendario_bloqueio_exige_domingos_booleano_feriados_e_dataprev_minimos():
    validar_calendario_bloqueio(BLOQUEIO)
    validar_calendario_bloqueio(BLOQUEIO_SEM_DOMINGO)  # D-18: `false` é válido (sozinho não abre: falta o dia 7 na janela)
    assert {date(2026, 11, 2), date(2026, 11, 20)} <= FERIADOS_MINIMOS
    sem_campo = {k: v for k, v in BLOQUEIO.items() if k != "domingos"}
    domingos_texto = {**BLOQUEIO, "domingos": "false"}
    domingos_nulo = {**BLOQUEIO, "domingos": None}
    domingos_numero = {**BLOQUEIO, "domingos": 0}
    sem_20_11 = {**BLOQUEIO, "feriados": ["2026-11-02"]}
    sem_fuso = {**BLOQUEIO, "janelas": [{"de": "2026-11-20T22:00:00", "ate": "2026-11-23T06:00:00", "motivo": "dataprev"}]}
    invertida = {
        **BLOQUEIO,
        "janelas": [*BLOQUEIO["janelas"], {"de": "2026-12-01T10:00:00-03:00", "ate": "2026-12-01T09:00:00-03:00", "motivo": "x"}],
    }
    data_ruim = {**BLOQUEIO, "feriados": [*BLOQUEIO["feriados"], "02/11/2026"]}
    for valor in (
        sem_campo, domingos_texto, domingos_nulo, domingos_numero,
        sem_20_11, sem_fuso, invertida, data_ruim, {"domingos": True},
    ):  # fmt: skip
        with pytest.raises(CalendarioInvalido):
            validar_calendario_bloqueio(valor)
    # a DATAPREV é do código e mensal (DEC-PIA-011): a config sem ela, ou com ela mais curta, é válida e a janela continua bloqueada
    validar_calendario_bloqueio({**BLOQUEIO, "janelas": []})


def test_janela_mensagem_aceita_o_domingo_dentro_de_08_20():
    assert validar_janela_mensagem(JANELA_COM_DOMINGO)[7] == (time(9, 0), time(18, 0))
    assert validar_janela_mensagem({"dias": {"7": dict(DIA)}}) == {7: (time(8, 0), time(20, 0))}


@pytest.mark.parametrize(
    ("janela", "bloqueio", "abre"),
    [
        pytest.param(JANELA, BLOQUEIO, False, id="as_duas_fechadas"),
        pytest.param(JANELA_COM_DOMINGO, BLOQUEIO, False, id="so_a_janela_aberta"),
        pytest.param(JANELA, BLOQUEIO_SEM_DOMINGO, False, id="so_o_bloqueio_aberto"),
        pytest.param(JANELA_COM_DOMINGO, BLOQUEIO_SEM_DOMINGO, True, id="as_duas_abertas"),
    ],
)
def test_domingo_so_abre_com_as_duas_chaves(janela, bloqueio, abre: bool):
    cal = carregar_calendario(janela, bloqueio)
    assert cal.domingo_aberto is abre
    for domingo in (DOMINGO_08, DOMINGO_29):
        assert cal.dentro_da_janela(utc(*domingo, 15, 0)) is abre  # 12:00 SP
        assert cal.dentro_da_janela(utc(*domingo, 11, 30)) is False  # 08:30 SP: antes das 09:00 do dia 7
        assert cal.dentro_da_janela(utc(*domingo, 21, 0)) is False  # 18:00 SP: o fim é exclusivo
    sabado_noite = utc(2026, 11, 7, 23, 30)  # sábado 20:30 SP
    esperado = utc(*DOMINGO_08, 12, 0) if abre else utc(2026, 11, 9, 11, 0)  # domingo 09:00 ou segunda 08:00
    assert cal.proxima_janela(sabado_noite) == esperado


def test_defaults_seguem_sem_domingo():
    """Os padrões do registro (o que vale sem config publicada) e o seed da 0001 deixam o domingo fechado: abrir é publicar as 2 chaves."""
    from ia_atendimento.chave_registro import PADROES

    assert PADROES["calendario_bloqueio"]["domingos"] is True
    assert "7" not in PADROES["janela_mensagem"]["dias"]
    cal = carregar_calendario(PADROES["janela_mensagem"], PADROES["calendario_bloqueio"])
    assert cal.domingo_aberto is False
    assert cal.bloqueado(utc(*DOMINGO_29, 15, 0)) is True


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


def test_limites_do_dia_e_do_mes_sao_de_sao_paulo():
    # 02:30 UTC de 17/11 ainda é 23:30 de 16/11 em SP: o dia local vai de 16/11 03:00 UTC a 17/11 03:00 UTC
    assert limites_do_dia(utc(2026, 11, 17, 2, 30)) == (utc(2026, 11, 16, 3), utc(2026, 11, 17, 3))
    assert limites_do_dia(utc(2026, 11, 17, 3, 0)) == (utc(2026, 11, 17, 3), utc(2026, 11, 18, 3))
    # 01/11 02:30 UTC é 31/10 23:30 em SP: ainda é outubro
    assert limites_do_mes(utc(2026, 11, 1, 2, 30)) == (utc(2026, 10, 1, 3), utc(2026, 11, 1, 3))
    assert limites_do_mes(utc(2026, 12, 15, 12)) == (utc(2026, 12, 1, 3), utc(2027, 1, 1, 3))


def test_base_de_fusos_nao_depende_do_sistema():
    """Revisão A10/N5: o `tzdata` é dependência declarada. Com o TZPATH do sistema vazio (`reset_tzpath`, que é o que o `ZoneInfo` consulta;
    mexer em `zoneinfo.TZPATH` não muda nada) o fuso de São Paulo carrega pelo pacote."""
    import zoneinfo

    zoneinfo.reset_tzpath(to=[])
    zoneinfo.ZoneInfo.clear_cache()
    try:
        assert zoneinfo._tzpath.find_tzfile("America/Sao_Paulo") is None  # o sistema NÃO ajuda mais
        fuso = zoneinfo.ZoneInfo("America/Sao_Paulo")
        assert fuso.utcoffset(datetime(2026, 11, 17, 12)).total_seconds() == -3 * 3600
    finally:
        zoneinfo.reset_tzpath()
        zoneinfo.ZoneInfo.clear_cache()
