"""DEC-PIA-011 item 4 (20/11): a janela da DATAPREV é MENSAL no código: todo dia 20 às 22:00 até o dia 23 às 06:00 (São Paulo).

Antes só existia a de novembro de 2026 (`calendario.py`, `agenda_extrator.py`, job único de 20/11). Aqui: o calendário bloqueia a janela de
qualquer mês mesmo com a config sem ela, o extrator de agenda recusa a volta dentro dela, e o job que fecha a entrada sai todo mês.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ia_atendimento.agenda_extrator import ConfigAgenda, extrair, na_dataprev
from ia_atendimento.calendario import (
    FUSO,
    bloqueio_dataprev_em,
    carregar_calendario,
    janela_dataprev_do_mes,
    janela_dataprev_em,
    janela_dataprev_seguinte,
    proxima_janela_dataprev,
)
from ia_atendimento.corpus import calendario as calendario_do_corpus

JANELA = {"dias": {str(d): {"inicio": "08:00", "fim": "20:00"} for d in range(1, 7)}}
SEM_JANELAS = {"domingos": True, "feriados": ["2026-11-02", "2026-11-20"], "janelas": []}


def sp(ano: int, mes: int, dia: int, hora: int, minuto: int = 0) -> datetime:
    return datetime(ano, mes, dia, hora, minuto, tzinfo=FUSO)


@pytest.mark.parametrize(("ano", "mes"), [(2026, 11), (2026, 12), (2027, 1), (2027, 2), (2027, 6)])
def test_janela_de_todo_mes_vai_do_dia_20_22h_ao_dia_23_06h(ano, mes):
    janela = janela_dataprev_do_mes(ano, mes)
    assert janela.de == sp(ano, mes, 20, 22).astimezone(UTC) and janela.ate == sp(ano, mes, 23, 6).astimezone(UTC)
    assert janela_dataprev_em(sp(ano, mes, 20, 21, 59)) is None
    assert janela_dataprev_em(sp(ano, mes, 20, 22)) == janela
    assert janela_dataprev_em(sp(ano, mes, 23, 5, 59)) == janela
    assert janela_dataprev_em(sp(ano, mes, 23, 6)) is None


def test_calendario_sem_a_janela_na_config_bloqueia_a_dataprev_de_dezembro():
    cal = carregar_calendario(JANELA, SEM_JANELAS)
    assert cal.dentro_da_janela(sp(2026, 12, 21, 10)) is False  # segunda 21/12, dentro da janela
    assert cal.dentro_da_janela(sp(2026, 12, 18, 10)) is True  # sexta 18/12, fora
    assert cal.proxima_janela(sp(2026, 12, 21, 10)) == sp(2026, 12, 23, 8).astimezone(UTC)  # quarta 23/12 08:00


def test_a_janela_de_novembro_continua_bloqueada():
    cal = carregar_calendario(JANELA, SEM_JANELAS)
    assert cal.dentro_da_janela(sp(2026, 11, 21, 10)) is False


def test_proxima_janela_e_a_que_ainda_nao_acabou():
    assert proxima_janela_dataprev(sp(2026, 11, 20, 12)) == janela_dataprev_do_mes(2026, 11)
    assert proxima_janela_dataprev(sp(2026, 11, 22, 12)) == janela_dataprev_do_mes(2026, 11)  # dentro dela
    assert proxima_janela_dataprev(sp(2026, 11, 23, 6)) == janela_dataprev_do_mes(2026, 12)
    assert proxima_janela_dataprev(sp(2026, 12, 25, 6)) == janela_dataprev_do_mes(2027, 1)  # virada do ano
    assert janela_dataprev_seguinte(janela_dataprev_do_mes(2026, 12)) == janela_dataprev_do_mes(2027, 1)


def test_bloqueio_da_entrada_e_10_min_antes():
    assert bloqueio_dataprev_em(janela_dataprev_do_mes(2026, 12)) == sp(2026, 12, 20, 21, 50).astimezone(UTC)


def test_extrator_de_agenda_recusa_volta_dentro_da_dataprev_de_dezembro():
    agora = sp(2026, 12, 18, 10)  # sexta
    r = extrair("segunda 21/12 às 10", agora, agora, ConfigAgenda(teto_horas=100))
    assert "bloqueio_dataprev" in r.candidatos[0].razoes
    fora = extrair("sexta 18/12 às 15", agora, agora, ConfigAgenda())
    assert "bloqueio_dataprev" not in fora.candidatos[0].razoes


def test_corpus_usa_a_mesma_janela_mensal():
    assert calendario_do_corpus.dentro_do_horario(sp(2026, 12, 21, 10)) is False
    assert calendario_do_corpus.dentro_do_horario(sp(2026, 12, 18, 10)) is True
    assert date(2026, 12, 21).weekday() == 0  # a âncora é uma segunda (não é domingo nem feriado)


def test_a_gemea_do_extrator_diz_o_mesmo_que_o_calendario_minuto_a_minuto_na_borda():
    from datetime import timedelta

    for ano, mes in ((2026, 11), (2026, 12), (2027, 2)):
        for base in (sp(ano, mes, 20, 21, 55), sp(ano, mes, 23, 5, 55)):
            for minuto in range(11):
                instante = base + timedelta(minutes=minuto)
                assert na_dataprev(instante) is (janela_dataprev_em(instante) is not None), instante
