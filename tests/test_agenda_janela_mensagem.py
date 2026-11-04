"""R-01 da revisão da B1.8: a agenda só aceita a volta que o envio pode cumprir (`janela_mensagem` do dia, a mesma do `Calendario`).

Antes, a agenda lia só `domingo_aberto` do `Calendario` e usava a `agenda_janela` (08:30–19:00) também no domingo: com o domingo publicado
09:00–18:00, «domingo às 8:30» era aceito e o envio não podia cumprir. Módulo puro: sem banco, relógio injetado.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from ia_atendimento.agenda_extrator import RAZOES, ConfigAgenda, extrair
from ia_atendimento.agendamento import config_da_agenda
from ia_atendimento.calendario import carregar_calendario
from ia_atendimento.chave_registro import PADROES

BRT = ZoneInfo("America/Sao_Paulo")
SABADO10 = datetime(2026, 11, 7, 10, 0, tzinfo=BRT)  # o domingo seguinte é 08/11 (sem feriado nem DATAPREV)
DOMINGO_09_18 = {"inicio": "09:00", "fim": "18:00"}
SEG_SAB = dict(PADROES["janela_mensagem"]["dias"])


def _config(dias: dict, *, domingos: bool = False) -> dict:
    nomes = ("agenda_janela", "agenda_periodos", "agenda_teto_horas", "calendario_bloqueio", "janela_mensagem")
    base = {nome: PADROES[nome] for nome in nomes}
    return {
        **base,
        "janela_mensagem": {"dias": dias},
        "calendario_bloqueio": {**PADROES["calendario_bloqueio"], "domingos": domingos},
        "agenda_teto_horas": 23,
    }


def _ex(texto: str, config: dict, agora: datetime = SABADO10, **troca):
    cfg = dataclasses.replace(config_da_agenda(config), **troca)
    return extrair(texto, agora, agora, cfg)


def test_config_da_agenda_leva_o_horario_de_envio_de_cada_dia():
    cfg = config_da_agenda(_config({**SEG_SAB, "7": DOMINGO_09_18}))
    assert cfg.domingo_aberto is True
    assert cfg.janela_mensagem[7] == (time(9, 0), time(18, 0))
    assert cfg.janela_mensagem[1] == (time(8, 0), time(20, 0))


@pytest.mark.parametrize(
    ("texto", "motivo"),
    [
        ("domingo às 8:30", "antes_da_janela"),  # o caso da revisão: cabia na agenda_janela, não no envio do domingo
        ("domingo às 8h59", "antes_da_janela"),
        ("domingo às 9h", None),
        ("domingo às 17:59", None),
        ("domingo às 18h", "depois_da_janela"),  # o fim do envio é exclusivo, como `Calendario.dentro_da_janela`
        ("domingo às 18:30", "depois_da_janela"),
    ],
)
def test_domingo_aberto_segue_o_horario_publicado_do_dia_7(texto: str, motivo: str | None):
    r = _ex(texto, _config({**SEG_SAB, "7": DOMINGO_09_18}), teto_horas=100)  # só o «próximo dia útil» (domingo 19:00) limita
    assert r.motivo_recusa == motivo, r


def test_domingo_aberto_com_teto_longo_ainda_recusa_fora_do_horario_do_dia_7():
    """O teto não mascara a regra: com «próximo dia útil 19:00» e teto de 23 h longe, as 18:30 do domingo seguem fora."""
    config = _config({**SEG_SAB, "7": DOMINGO_09_18})
    agora = datetime(2026, 11, 8, 9, 30, tzinfo=BRT)  # o próprio domingo; teto = segunda 08:30
    assert _ex("hoje às 18:30", config, agora).motivo_recusa == "depois_da_janela"
    assert _ex("hoje às 17h", config, agora).motivo_recusa is None


def test_dia_tirado_da_janela_mensagem_nao_recebe_volta_nem_e_dia_util_do_teto():
    """A mesma lacuna em seg–sáb: sábado fora da `janela_mensagem` não aceita volta e o teto pula o sábado."""
    sem_sabado = {d: h for d, h in SEG_SAB.items() if d != "6"}
    sexta16 = datetime(2026, 11, 6, 16, 0, tzinfo=BRT)
    r = _ex("sábado às 10", _config(sem_sabado, domingos=True), sexta16)
    assert r.candidatos[0].razoes == ("dia_sem_janela",) and r.motivo_recusa == "dia_sem_janela"
    # teto de 100 h: o único limite é o «próximo dia útil 19:00»; sem sábado e com domingo fechado, é segunda 09/11
    longo = _ex("segunda às 10", _config(sem_sabado, domingos=True), sexta16, teto_horas=100)
    assert longo.motivo_recusa is None
    assert _ex("segunda às 10", _config(SEG_SAB, domingos=True), sexta16, teto_horas=100).motivo_recusa == "acima_do_teto"


def test_dia_sem_janela_esta_nas_razoes_e_nao_aparece_com_o_domingo_fechado():
    assert "dia_sem_janela" in RAZOES
    fechado = _ex("domingo às 9h", _config(dict(SEG_SAB), domingos=True))
    assert fechado.candidatos[0].razoes == ("domingo",)


@pytest.mark.parametrize("domingo", [DOMINGO_09_18, {"inicio": "08:00", "fim": "20:00"}, {"inicio": "10:15", "fim": "12:45"}])
def test_volta_aceita_pela_agenda_sempre_cabe_no_envio(domingo: dict):
    """Propriedade: de sábado 10:00, toda hora de domingo que a agenda aceita é um instante em que o `Calendario` deixa mandar mensagem."""
    config = _config({**SEG_SAB, "7": domingo})
    calendario = carregar_calendario(config["janela_mensagem"], config["calendario_bloqueio"])
    instante = datetime(2026, 11, 8, 0, 0, tzinfo=BRT)
    aceitas = 0
    while instante.date().day == 8:
        texto = f"domingo às {instante:%H:%M}"
        r = _ex(texto, config, teto_horas=100)
        if r.motivo_recusa is None:
            aceitas += 1
            assert calendario.dentro_da_janela(r.candidatos[0].quando), texto
        instante += timedelta(minutes=15)
    assert aceitas > 0


def test_config_agenda_recusa_janela_mensagem_malformada():
    with pytest.raises(ValueError, match="janela_mensagem"):
        ConfigAgenda(janela_mensagem={8: (time(9), time(18))})
    with pytest.raises(ValueError, match="janela_mensagem"):
        ConfigAgenda(janela_mensagem={7: (time(18), time(9))})


def test_sem_janela_mensagem_o_extrator_puro_segue_igual():
    """`ConfigAgenda()` sem `janela_mensagem` (o extrator puro e o corpus de frases) não muda: só a agenda_janela vale."""
    r = extrair("domingo às 8:30", SABADO10, SABADO10, ConfigAgenda(domingo_aberto=True, teto_horas=23))
    assert ConfigAgenda().janela_mensagem is None and r.motivo_recusa is None
