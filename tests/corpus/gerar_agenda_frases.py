#!/usr/bin/env python3
"""Gera `agenda_frases.jsonl`, o corpus do extrator de horário (B5.7a). Veja `README.md` desta pasta.

TODAS as frases são INVENTADAS (português do Brasil, estilo WhatsApp curto). Nenhuma vem de conversa real (PD-6; o corpus real do
ChatGuru está proibido até o parecer jurídico). O `esperado` de cada caso é escrito À MÃO a partir da regra do estudo M, nunca
calculado chamando o extrator: o gerador não importa nada de `src/`, para o corpus não ficar circular.

Âncoras de calendário (2026, fuso BRT = UTC-3): 05/11 quinta, 06/11 sexta, 07/11 sábado, 08/11 domingo, 09/11 segunda;
feriados 02/11 e 20/11; bloqueio DATAPREV 20/11 22:00 → 23/11 06:00.
Teto (padrão): min(última msg do cliente + 23 h, próximo dia útil 19:00); a última msg é o próprio `agora`, salvo `ult=`.

Uso: python3 tests/corpus/gerar_agenda_frases.py        (reescreve o jsonl ao lado)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DESTINO = Path(__file__).with_name("agenda_frases.jsonl")
CONFIANCA = {"a": "alta", "m": "media", "b": "baixa"}

CASOS: list[dict] = []
MODO = {"holdout": False}  # liga no bloco do hold-out


def _iso(local: str) -> str:
    """'2026-11-05 15:00' (BRT) -> '2026-11-05T15:00:00-03:00'; com sufixo Z fica em UTC."""
    if local.endswith("Z"):
        return local[:-1].replace(" ", "T") + ":00+00:00"
    return local.replace(" ", "T") + ":00-03:00"


def caso(texto, agora, esperado=(), motivo=None, conf="", ult=None, periodos=False, tag="", holdout=False):
    """`esperado`: horários locais (BRT) de TODOS os candidatos, em ordem cronológica; `conf`: 'a'/'m'/'b' por candidato;
    `motivo`: motivo_recusa esperado (None quando há ao menos um candidato válido)."""
    assert len(conf) == len(esperado), (texto, conf, esperado)
    CASOS.append(
        {
            "id": "",
            "holdout": holdout or MODO["holdout"],
            "tag": tag,
            "texto": texto,
            "agora": _iso(agora),
            "ultima_msg": _iso(ult) if ult else None,
            "usa_periodos": periodos,
            "esperado": [_iso(e) for e in esperado],
            "confianca": [CONFIANCA[c] for c in conf],
            "motivo": motivo,
        }
    )


def valido(texto, agora, quando, conf="a", **kw):
    caso(texto, agora, [quando], None, conf, **kw)


def fora(texto, agora, quando, motivo, conf="a", **kw):
    caso(texto, agora, [quando], motivo, conf, **kw)


def vazio(texto, agora="2026-11-05 10:00", motivo="sem_hora_explicita", **kw):
    caso(texto, agora, [], motivo, "", **kw)


QUI10 = "2026-11-05 10:00"
QUI18 = "2026-11-05 18:00"
HOJE = "2026-11-05"
AMANHA = "2026-11-06"

# ---------------------------------------------------------------- desenvolvimento (a gramática foi escrita olhando estes)
# hora explícita, hoje (QUI 10:00; teto sexta 09:00)
for t, q, c in [
    ("pode ser às 15h", "15:00", "a"),
    ("15h", "15:00", "a"),
    ("às 15:30", "15:30", "a"),
    ("as 15", "15:00", "a"),
    ("15:30", "15:30", "a"),
    ("me liga 16h30", "16:30", "a"),
    ("às 3 da tarde", "15:00", "a"),
    ("3 da tarde", "15:00", "a"),
    ("às 4 da tarde", "16:00", "a"),
    ("meio-dia", "12:00", "m"),
    ("meio dia e meia", "12:30", "m"),
    ("as 14 horas", "14:00", "a"),
    ("umas 3", "15:00", "m"),
    ("3 e meia", "15:30", "m"),
    ("às 3 e meia da tarde", "15:30", "a"),
    ("às três da tarde", "15:00", "a"),
    ("quatro e meia", "16:30", "m"),
    ("depois das 4", "16:15", "m"),
    ("às 3", "15:00", "m"),
    ("às 11", "11:00", "a"),
    ("1 da tarde", "13:00", "a"),
    ("uma da tarde", "13:00", "a"),
    ("às 7 da noite", "19:00", "a"),
    ("12h30", "12:30", "a"),
    ("às 19h", "19:00", "a"),
    ("pode ser 15hrs", "15:00", "a"),
    ("15hs", "15:00", "a"),
    ("as 15 hrs", "15:00", "a"),
    ("15H", "15:00", "a"),
    ("ÀS 15H", "15:00", "a"),
    ("as 15 h", "15:00", "a"),
    ("blz as 15h kk", "15:00", "a"),
    ("15h 😀", "15:00", "a"),
    ("👍 15h!!!", "15:00", "a"),
    ("as 15h.", "15:00", "a"),
    ("pd ser 15hrs", "15:00", "a"),
    ("blz, as 15h30 ta bom", "15:30", "a"),
    ("15:00hs", "15:00", "a"),
    ("às 15 horas", "15:00", "a"),
    ("as 15h; pode ser?", "15:00", "a"),
    ("😊😊 15h 😊", "15:00", "a"),
    ("bom dia, posso falar às 14h?", "14:00", "a"),
]:
    valido(t, QUI10, f"{HOJE} {q}", c, tag="hora_hoje")

fora("às 19:01", QUI10, f"{HOJE} 19:01", "depois_da_janela", tag="janela")
fora("às 21h", QUI10, f"{HOJE} 21:00", "depois_da_janela", tag="janela")
fora("10 da noite", QUI10, f"{HOJE} 22:00", "depois_da_janela", tag="janela")
fora("meia-noite", QUI10, f"{AMANHA} 00:00", "antes_da_janela", "m", tag="janela")
fora("às 8", QUI10, f"{AMANHA} 08:00", "antes_da_janela", "m", tag="janela")
# 10:00 já é agora: o dia inferido rola para sexta, que passa do teto (sexta 09:00)
fora("umas 10 da manhã", QUI10, f"{AMANHA} 10:00", "acima_do_teto", "m", tag="hora_passada")
valido("às 8:30", QUI10, f"{AMANHA} 08:30", "m", tag="hora_passada")
caso("quinta às 15", QUI10, [f"{HOJE} 15:00", "2026-11-12 15:00"], None, "mm", tag="mesmo_dia_semana")

# semanas/dias com teto (QUI 10:00 -> teto sexta 09:00)
valido("sexta às 8:30", QUI10, f"{AMANHA} 08:30", tag="teto")
valido("sexta às 9", QUI10, f"{AMANHA} 09:00", tag="teto")
fora("sexta às 9:01", QUI10, f"{AMANHA} 09:01", "acima_do_teto", tag="teto")
fora("sexta às 10", QUI10, f"{AMANHA} 10:00", "acima_do_teto", tag="teto")
fora("sab as 10", QUI10, "2026-11-07 10:00", "acima_do_teto", tag="ruido")
fora("seg 14h", QUI10, "2026-11-09 14:00", "acima_do_teto", tag="ruido")
fora("sex 10h", QUI10, f"{AMANHA} 10:00", "acima_do_teto", tag="ruido")
fora("terça-feira 10h", QUI10, "2026-11-10 10:00", "acima_do_teto", tag="ruido")
fora("segunda feira às 10", QUI10, "2026-11-09 10:00", "acima_do_teto", tag="ruido")
fora("to livre amanha as 3 da tarde kkk", QUI10, f"{AMANHA} 15:00", "acima_do_teto", tag="ruido")

# distratores e sem hora explícita (nenhum candidato)
for t in [
    "tenho 3 parcelas",
    "quero 15 mil",
    "R$ 15 por mês",
    "em 3 vezes",
    "as 3 parcelas",
    "tenho 2 filhos",
    "dia 5",
    "ok",
    "",
    "boa tarde",
    "boa noite, tudo bem?",
    "bom dia",
    "depois",
    "mais tarde",
    "daqui a pouco",
    "semana que vem",
    "amanhã",
    "amanhã de tarde",
    "depois do almoço",
    "de manhã",
    "à noite",
    "segunda",
    "agora não",
    "pode ser agora",
    "qualquer hora",
    "outro dia",
    "cedo",
    "antes das 18h",
    "até as 17",
    "hoje à noite",
    "mais tarde eu te falo",
]:
    vazio(t, tag="sem_hora")
vazio("semana que vem às 15", QUI10, "dia_nao_resolvido", tag="dia_vago")
vazio("mês que vem às 10", QUI10, "dia_nao_resolvido", tag="dia_vago")
vazio("fim de semana às 10", QUI10, "dia_nao_resolvido", tag="dia_vago")

# relativo (agora 10:07; teto sexta 09:07); o resultado sobe para múltiplo de 5 min
R = "2026-11-05 10:07"
for t, q in [
    ("daqui a 1 hora", "11:10"),
    ("daqui a 30 min", "10:40"),
    ("em 2 horas", "12:10"),
    ("daqui meia hora", "10:40"),
    ("daqui a uma hora e meia", "11:40"),
    ("dentro de 15 minutos", "10:25"),
    ("daqui a 3 horas", "13:10"),
    ("daqui 2h", "12:10"),
    ("daqui a 1h", "11:10"),
]:
    valido(t, R, f"{HOJE} {q}", tag="relativo")
fora("daqui 5 min", R, f"{HOJE} 10:15", "antecedencia", tag="relativo")
fora("daqui a 12 horas", R, f"{HOJE} 22:10", "depois_da_janela", tag="relativo")
fora("daqui a 30 horas", R, "2026-11-06 16:10", "acima_do_teto", tag="relativo")

# dia relativo e dia da semana (QUI 18:00; teto sexta 17:00)
for t in ["amanhã às 10", "amanha 10h", "AMANHÃ ÀS 10H", "amnh as 10", "amanhaaa 10h", "boa tarde! amanhã às 10 pode ser?"]:
    valido(t, QUI18, f"{AMANHA} 10:00", tag="amanha")
valido("amanhã de manhã às 9", QUI18, f"{AMANHA} 09:00", tag="amanha")
valido("amanhã às 9:30", QUI18, f"{AMANHA} 09:30", tag="amanha")
valido("amanhã 15h", QUI18, f"{AMANHA} 15:00", tag="amanha")
valido("amanhã às 17h", QUI18, f"{AMANHA} 17:00", tag="teto")
fora("amanhã às 17:30", QUI18, f"{AMANHA} 17:30", "acima_do_teto", tag="teto")
valido("amanhã às 3 da tarde", QUI18, f"{AMANHA} 15:00", tag="amanha")
valido("hoje às 18:30", QUI18, f"{HOJE} 18:30", tag="hoje")
valido("hj 18:45", QUI18, f"{HOJE} 18:45", tag="hoje")
fora("hoje às 18:05", QUI18, f"{HOJE} 18:05", "antecedencia", tag="antecedencia")
fora("hoje às 17", QUI18, f"{HOJE} 17:00", "passado", tag="hora_passada")
valido("hoje 19h", QUI18, f"{HOJE} 19:00", tag="janela")
fora("hoje às 20h", QUI18, f"{HOJE} 20:00", "depois_da_janela", tag="janela")
valido("às 15", QUI18, f"{AMANHA} 15:00", "m", tag="hora_passada")
valido("sexta às 10", QUI18, f"{AMANHA} 10:00", tag="semana")
valido("sexta 14h", QUI18, f"{AMANHA} 14:00", tag="semana")
fora("sexta às 17:30", QUI18, f"{AMANHA} 17:30", "acima_do_teto", tag="teto")
fora("depois de amanhã às 10", QUI18, "2026-11-07 10:00", "acima_do_teto", tag="semana")
fora("sábado às 10", QUI18, "2026-11-07 10:00", "acima_do_teto", tag="semana")
fora("domingo às 10", QUI18, "2026-11-08 10:00", "domingo", tag="domingo")
fora("segunda às 14h", QUI18, "2026-11-09 14:00", "acima_do_teto", tag="semana")
fora("segunda feira às 9", QUI18, "2026-11-09 09:00", "acima_do_teto", tag="semana")
fora("terça 10h", QUI18, "2026-11-10 10:00", "acima_do_teto", tag="semana")
fora("terca as 10", QUI18, "2026-11-10 10:00", "acima_do_teto", tag="semana")
fora("quarta às 16", QUI18, "2026-11-11 16:00", "acima_do_teto", tag="semana")
fora("quinta que vem às 15", QUI18, "2026-11-12 15:00", "acima_do_teto", tag="semana")
fora("terça da semana que vem às 15h", QUI18, "2026-11-10 15:00", "acima_do_teto", tag="semana")
fora("dia 9 às 10", QUI18, "2026-11-09 10:00", "acima_do_teto", tag="data")
valido("dia 5 às 19", QUI18, f"{HOJE} 19:00", tag="data")
fora("dia 3 às 10", QUI18, "2026-12-03 10:00", "acima_do_teto", tag="data")
valido("06/11 às 10h", QUI18, f"{AMANHA} 10:00", tag="data")
valido("6/11 10h", QUI18, f"{AMANHA} 10:00", tag="data")
fora("dia 10 de novembro às 14:00", QUI18, "2026-11-10 14:00", "acima_do_teto", tag="data")
fora("10 de nov às 14h", QUI18, "2026-11-10 14:00", "acima_do_teto", tag="data")
fora("dia 31 às 10", QUI18, "2026-12-31 10:00", "acima_do_teto", tag="data")
fora("daqui a 3 dias às 10", QUI18, "2026-11-08 10:00", "domingo", tag="data")
caso("hoje ou amanhã às 15", QUI18, [f"{HOJE} 15:00", f"{AMANHA} 15:00"], None, "mm", tag="ambiguo")
caso("segunda ou terça às 14", QUI18, ["2026-11-09 14:00", "2026-11-10 14:00"], "acima_do_teto", "mm", tag="ambiguo")
fora("sexta 20/11 às 15", QUI18, "2026-11-20 15:00", "feriado", tag="feriado")
caso("15h ou 16h amanhã", QUI18, [f"{AMANHA} 15:00", f"{AMANHA} 16:00"], None, "mm", tag="ambiguo")
caso("amanhã às 10 ou 11", QUI18, [f"{AMANHA} 10:00", f"{AMANHA} 11:00"], None, "mm", tag="ambiguo")

# ambíguo (QUI 10:00)
caso("15 ou 16", QUI10, [f"{HOJE} 15:00", f"{HOJE} 16:00"], None, "mm", tag="ambiguo")
caso("às 15h ou 16h", QUI10, [f"{HOJE} 15:00", f"{HOJE} 16:00"], None, "mm", tag="ambiguo")
caso("pode ser 3 ou 4 da tarde", QUI10, [f"{HOJE} 15:00", f"{HOJE} 16:00"], None, "mm", tag="ambiguo")
caso("entre 15 e 16", QUI10, [f"{HOJE} 15:00", f"{HOJE} 16:00"], None, "mm", tag="ambiguo")
caso("às 11 ou às 14 ou 16h", QUI10, [f"{HOJE} 11:00", f"{HOJE} 14:00", f"{HOJE} 16:00"], None, "mmm", tag="ambiguo")
caso("às 15, não às 16", QUI10, [f"{HOJE} 15:00", f"{HOJE} 16:00"], None, "mm", tag="ambiguo")
vazio("às 11 ou 12 ou 13 ou 14 ou 15", QUI10, "ambiguo_demais", tag="ambiguo")

# feriados, DATAPREV, sábado, domingo
SEX30 = "2026-10-30 15:00"  # sexta; teto = sábado 14:00
fora("segunda às 10", SEX30, "2026-11-02 10:00", "feriado", tag="feriado")
fora("dia 2 às 10", SEX30, "2026-11-02 10:00", "feriado", tag="feriado")
fora("02/11 às 14h", SEX30, "2026-11-02 14:00", "feriado", tag="feriado")
valido("amanhã às 10", SEX30, "2026-10-31 10:00", tag="sabado")
fora("amanhã às 13h", SEX30, "2026-10-31 13:00", "depois_da_janela", tag="sabado")
fora("terça às 10", SEX30, "2026-11-03 10:00", "acima_do_teto", tag="teto")
fora("dia 20 às 10", QUI10, "2026-11-20 10:00", "feriado", tag="feriado")
fora("20/11 às 9h", QUI10, "2026-11-20 09:00", "feriado", tag="feriado")
fora("21/11 às 10", QUI10, "2026-11-21 10:00", "bloqueio_dataprev", tag="dataprev")
fora("sábado 21/11 às 10", QUI10, "2026-11-21 10:00", "bloqueio_dataprev", tag="dataprev")
fora("domingo 22/11 às 10", QUI10, "2026-11-22 10:00", "bloqueio_dataprev", tag="dataprev")
fora("segunda 23/11 05:30", QUI10, "2026-11-23 05:30", "bloqueio_dataprev", tag="dataprev")
fora("23/11 às 9", QUI10, "2026-11-23 09:00", "acima_do_teto", tag="dataprev")
fora("amanhã às 10", "2026-11-19 18:00", "2026-11-20 10:00", "feriado", tag="feriado")
fora("hoje às 22:30", "2026-11-20 08:00", "2026-11-20 22:30", "feriado", tag="dataprev")
fora("hoje 21h", "2026-11-20 20:00", "2026-11-20 21:00", "feriado", tag="dataprev")
fora("dia 20 às 9", "2026-11-18 10:00", "2026-11-20 09:00", "feriado", tag="feriado")

SAB = "2026-11-07 09:30"  # sábado; teto = domingo 08:30
valido("hoje às 11", SAB, "2026-11-07 11:00", tag="sabado")
valido("hoje às 12", SAB, "2026-11-07 12:00", tag="sabado")
fora("hoje às 12:30", SAB, "2026-11-07 12:30", "depois_da_janela", tag="sabado")
fora("hoje às 14", SAB, "2026-11-07 14:00", "depois_da_janela", tag="sabado")
fora("hoje às 9", SAB, "2026-11-07 09:00", "passado", tag="sabado")
fora("às 9", SAB, "2026-11-08 09:00", "domingo", "m", tag="domingo")
fora("segunda às 10", SAB, "2026-11-09 10:00", "acima_do_teto", tag="sabado")
fora("amanhã às 8:30", SAB, "2026-11-08 08:30", "domingo", tag="domingo")
valido("daqui a 1 hora", SAB, "2026-11-07 10:30", tag="relativo")

DOM = "2026-11-08 10:00"  # domingo; teto = segunda 09:00
fora("hoje às 15", DOM, "2026-11-08 15:00", "domingo", tag="domingo")
fora("às 15", DOM, "2026-11-08 15:00", "domingo", tag="domingo")
fora("amanhã às 10", DOM, "2026-11-09 10:00", "acima_do_teto", tag="domingo")
valido("amanhã às 8:30", DOM, "2026-11-09 08:30", tag="domingo")
valido("segunda às 8:30", DOM, "2026-11-09 08:30", tag="domingo")

# virada de dia em UTC (22:30Z = quinta 19:30 BRT; 02:30Z de sexta = quinta 23:30 BRT)
U1 = "2026-11-05T22:30Z"
valido("amanhã às 10", U1, f"{AMANHA} 10:00", tag="utc")
valido("amanhã às 18:30", U1, f"{AMANHA} 18:30", tag="utc")
fora("amanhã às 18:45", U1, f"{AMANHA} 18:45", "acima_do_teto", tag="utc")
fora("hoje às 19:45", U1, f"{HOJE} 19:45", "depois_da_janela", tag="utc")
fora("hoje 19:00", U1, f"{HOJE} 19:00", "passado", tag="utc")
fora("daqui a 1 hora", U1, f"{HOJE} 20:30", "depois_da_janela", tag="utc")
valido("às 9", U1, f"{AMANHA} 09:00", "m", tag="utc")
U2 = "2026-11-06T02:30Z"
valido("amanhã às 10", U2, f"{AMANHA} 10:00", tag="utc")
fora("hoje às 23:50", U2, f"{HOJE} 23:50", "depois_da_janela", tag="utc")
valido("amanhã às 19h", U2, f"{AMANHA} 19:00", tag="utc")
valido("sexta às 10", U2, f"{AMANHA} 10:00", tag="utc")

# teto com última mensagem do cliente
QUI14 = "2026-11-05 14:00"
valido("hoje às 16", QUI14, f"{HOJE} 16:00", ult="2026-11-05 09:00", tag="teto")
fora("amanhã às 8:30", QUI14, f"{AMANHA} 08:30", "acima_do_teto", ult="2026-11-05 09:00", tag="teto")
valido("amanhã às 13h", QUI14, f"{AMANHA} 13:00", tag="teto")
fora("amanhã às 13:30", QUI14, f"{AMANHA} 13:30", "acima_do_teto", tag="teto")
fora("hoje às 9", QUI14, f"{HOJE} 09:00", "passado", tag="hora_passada")
fora("hoje às 13", QUI14, f"{HOJE} 13:00", "passado", tag="hora_passada")
valido("às 13", QUI14, f"{AMANHA} 13:00", "m", tag="hora_passada")
fora("hoje às 16", QUI14, f"{HOJE} 16:00", "acima_do_teto", ult="2026-11-03 10:00", tag="teto")
valido("daqui a 1 hora", QUI14, f"{HOJE} 15:00", tag="relativo")

# períodos da config (usa_periodos): confiança nunca alta
caso("amanhã de tarde", QUI18, [f"{AMANHA} 14:00"], None, "m", periodos=True, tag="periodo")
caso("depois do almoço", QUI10, [f"{HOJE} 13:30"], None, "b", periodos=True, tag="periodo")
caso("de manhã", QUI10, [f"{AMANHA} 09:00"], None, "b", periodos=True, tag="periodo")
caso("à noite", QUI10, [f"{HOJE} 19:00"], None, "b", periodos=True, tag="periodo")
caso("fim da tarde", QUI10, [f"{HOJE} 17:30"], None, "b", periodos=True, tag="periodo")
caso("amanhã cedo", QUI18, [f"{AMANHA} 08:30"], None, "m", periodos=True, tag="periodo")
caso("amanhã de manhã", QUI18, [f"{AMANHA} 09:00"], None, "m", periodos=True, tag="periodo")
caso("segunda à tarde", QUI10, ["2026-11-09 14:00"], "acima_do_teto", "m", periodos=True, tag="periodo")
caso("hoje à noite", QUI10, [f"{HOJE} 19:00"], None, "m", periodos=True, tag="periodo")
caso("amanhã de tarde", QUI10, [f"{AMANHA} 14:00"], "acima_do_teto", "m", periodos=True, tag="periodo")
caso("amanhã de manhã às 10", QUI18, [f"{AMANHA} 10:00"], None, "a", periodos=True, tag="periodo")
vazio("boa tarde", periodos=True, tag="periodo")
vazio("mais tarde", periodos=True, tag="periodo")
vazio("mais tarde eu te falo", periodos=True, tag="periodo")

# ---------------------------------------------------------------- hold-out (escrito DEPOIS da gramática; ver README)
MODO["holdout"] = True
R = "2026-11-05 10:07"
valido("consigo as 16h sim", QUI10, f"{HOJE} 16:00", tag="hora_hoje")
valido("pode ser 14:30 hoje", QUI10, f"{HOJE} 14:30", tag="hora_hoje")
valido("hoje as 17h30", QUI10, f"{HOJE} 17:30", tag="hora_hoje")
valido("me chama as duas da tarde", QUI10, f"{HOJE} 14:00", tag="hora_hoje")
valido("só consigo depois das 5", QUI10, f"{HOJE} 17:15", "m", tag="giria")
valido("amanhã 9h", QUI18, f"{AMANHA} 09:00", tag="amanha")
valido("amanhã cedinho 8:30", QUI18, f"{AMANHA} 08:30", tag="amanha")
valido("pode ser amanhã às 11h30?", QUI18, f"{AMANHA} 11:30", tag="amanha")
valido("sexta de manhã 10h", QUI18, f"{AMANHA} 10:00", tag="semana")
valido("sexta feira 16h", QUI18, f"{AMANHA} 16:00", tag="semana")
valido("ola, amanha as 14 pode?", QUI18, f"{AMANHA} 14:00", tag="ruido")
valido("amanha às 5 da tarde", QUI18, f"{AMANHA} 17:00", tag="teto")
fora("amanha as 6 da tarde", QUI18, f"{AMANHA} 18:00", "acima_do_teto", tag="teto")
valido("daqui a 20 min", QUI10, f"{HOJE} 10:20", tag="relativo")
valido("em 45 minutos", R, f"{HOJE} 10:55", tag="relativo")
valido("daqui a 4 horas", R, f"{HOJE} 14:10", tag="relativo")
valido("daqui a duas horas", QUI10, f"{HOJE} 12:00", tag="relativo")
valido("meio dia", QUI10, f"{HOJE} 12:00", "m", tag="hora_hoje")
valido("meio-dia e meia", QUI10, f"{HOJE} 12:30", "m", tag="hora_hoje")
valido("tô livre à 1 da tarde", QUI10, f"{HOJE} 13:00", tag="ruido")
fora("pode ser as 9 da noite", QUI10, f"{HOJE} 21:00", "depois_da_janela", tag="janela")
valido("hoje as 18h", QUI10, f"{HOJE} 18:00", tag="hora_hoje")
valido("umas 2 e meia", QUI10, f"{HOJE} 14:30", "m", tag="giria")
valido("umas 5h", QUI10, f"{HOJE} 17:00", "m", tag="giria")
valido("mais tarde às 3", QUI10, f"{HOJE} 15:00", "m", tag="giria")
valido("15hrs pode ser", QUI10, f"{HOJE} 15:00", tag="ruido")
valido("11h da manhã", QUI10, f"{HOJE} 11:00", tag="hora_hoje")
valido("hoje as 19h", QUI18, f"{HOJE} 19:00", tag="janela")
valido("hoje mesmo as 18h30", QUI18, f"{HOJE} 18:30", tag="hoje")
valido("hoje às 10:30", SAB, "2026-11-07 10:30", tag="sabado")
fora("segunda às 9", SAB, "2026-11-09 09:00", "acima_do_teto", tag="sabado")
valido("amanhã às 08:30", DOM, "2026-11-09 08:30", tag="domingo")
valido("amanhã às 15:00", U1, f"{AMANHA} 15:00", tag="utc")
valido("amanhã às 08:30", U2, f"{AMANHA} 08:30", tag="utc")
fora("dia 3 às 10", SEX30, "2026-11-03 10:00", "acima_do_teto", tag="data")
fora("segunda dia 9 às 10", QUI10, "2026-11-09 10:00", "acima_do_teto", tag="data")
fora("dia 20 de novembro às 8", QUI10, "2026-11-20 08:00", "feriado", tag="feriado")
fora("21 de novembro 10h", QUI10, "2026-11-21 10:00", "bloqueio_dataprev", tag="dataprev")
fora("23/11 às 19h", QUI10, "2026-11-23 19:00", "acima_do_teto", tag="dataprev")
fora("pode ser as 15h do dia 6", QUI10, f"{AMANHA} 15:00", "acima_do_teto", tag="data")
fora("15h do domingo", QUI10, "2026-11-08 15:00", "domingo", tag="domingo")
fora("terça às 4 da tarde", QUI10, "2026-11-10 16:00", "acima_do_teto", tag="semana")
fora("5 de dezembro 10h", QUI10, "2026-12-05 10:00", "acima_do_teto", tag="data")
caso("sexta ou sábado às 10", QUI18, [f"{AMANHA} 10:00", "2026-11-07 10:00"], None, "mm", tag="ambiguo")
caso("às 10 ou 11 amanhã", QUI18, [f"{AMANHA} 10:00", f"{AMANHA} 11:00"], None, "mm", tag="ambiguo")
caso("pode ser as 3 ou as 4?", QUI18, [f"{AMANHA} 15:00", f"{AMANHA} 16:00"], None, "mm", tag="ambiguo")
caso("quinta-feira 15h", QUI10, [f"{HOJE} 15:00", "2026-11-12 15:00"], None, "mm", tag="mesmo_dia_semana")
for t in ["vou ver e te falo", "semana que vem eu consigo", "talvez amanhã", "acho que de tarde", "só tenho 3 parcelas pra pagar"]:
    vazio(t, tag="sem_hora")

# hold-out v2 (revisão 1, item 11): 40 casos novos, escritos e CONGELADOS antes de corrigir R1-R10; 1ª rodada registrada no README
MODO["holdout"] = True
valido("pode ligar 13h30", QUI10, f"{HOJE} 13:30", tag="hora_hoje")
valido("to disponivel as 12h", QUI10, f"{HOJE} 12:00", tag="ruido")
valido("me liga a tarde, as 4", QUI10, f"{HOJE} 16:00", tag="hora_hoje")
fora("as 9h da noite", QUI10, f"{HOJE} 21:00", "depois_da_janela", tag="janela")
valido("hoje as 11:15", QUI10, f"{HOJE} 11:15", tag="hora_hoje")
valido("daqui a 90 min", QUI10, f"{HOJE} 11:30", tag="relativo")
valido("daqui 3h", QUI10, f"{HOJE} 13:00", tag="relativo")
valido("dentro de 2 horas", QUI10, f"{HOJE} 12:00", tag="relativo")
caso("pode ser 14h ou 15h", QUI10, [f"{HOJE} 14:00", f"{HOJE} 15:00"], None, "mm", tag="ambiguo")
caso("as 13 ou 14", QUI10, [f"{HOJE} 13:00", f"{HOJE} 14:00"], None, "mm", tag="ambiguo")
valido("às 2 da tarde", QUI10, f"{HOJE} 14:00", tag="hora_hoje")
valido("umas 4h", QUI10, f"{HOJE} 16:00", "m", tag="giria")
valido("seis e meia", QUI10, f"{HOJE} 18:30", "m", tag="giria")
valido("depois das 3", QUI10, f"{HOJE} 15:15", "m", tag="giria")
valido("hoje as 16h", QUI10, f"{HOJE} 16:00", tag="hoje")
caso("quinta as 17", QUI10, [f"{HOJE} 17:00", "2026-11-12 17:00"], None, "mm", tag="mesmo_dia_semana")
fora("sabado as 11", QUI10, "2026-11-07 11:00", "acima_do_teto", tag="semana")
fora("domingo 14h", QUI10, "2026-11-08 14:00", "domingo", tag="domingo")
valido("dia 6 as 8:30", QUI10, f"{AMANHA} 08:30", tag="data")
valido("06/11 as 9h", QUI10, f"{AMANHA} 09:00", tag="data")
fora("6 de novembro 9h30", QUI10, f"{AMANHA} 09:30", "acima_do_teto", tag="data")
fora("02/11 as 10h", QUI10, "2026-11-02 10:00", "feriado", tag="feriado")
fora("dia 22 as 10h", QUI10, "2026-11-22 10:00", "bloqueio_dataprev", tag="dataprev")
fora("dia 21 as 8h", QUI10, "2026-11-21 08:00", "bloqueio_dataprev", tag="dataprev")
fora("dia 23 as 5 da manha", QUI10, "2026-11-23 05:00", "bloqueio_dataprev", tag="dataprev")
valido("amanhã às 9h", QUI18, f"{AMANHA} 09:00", tag="amanha")
valido("amanha 16:45", QUI18, f"{AMANHA} 16:45", tag="amanha")
valido("hoje 18h30", QUI18, f"{HOJE} 18:30", tag="hoje")
fora("pode ser amanha 8h", QUI18, f"{AMANHA} 08:00", "antes_da_janela", tag="janela")
valido("sexta 15h30", QUI18, f"{AMANHA} 15:30", tag="semana")
fora("hoje as 20h", U1, f"{HOJE} 20:00", "depois_da_janela", tag="utc")
valido("amanhã 9:45", U2, f"{AMANHA} 09:45", tag="utc")
valido("hoje as 11h30", SAB, "2026-11-07 11:30", tag="sabado")
fora("daqui a 3 horas", SAB, "2026-11-07 12:30", "depois_da_janela", tag="sabado")
valido("segunda 8h45", DOM, "2026-11-09 08:45", tag="domingo")
valido("às 15h, pode?", QUI10, f"{HOJE} 15:00", tag="ruido")
valido("15h30 pode ser?", QUI10, f"{HOJE} 15:30", tag="ruido")
for t in [
    "pode ser outro horario",
    "hoje nao da",
    "sexta",
    "amanha de manha",
    "queria uns dois contratos",
    "ok, as 3 parcelas de 15 reais",
]:
    vazio(t, tag="sem_hora")

# regressões achadas no 1º rodar do hold-out (52/54): «10h30 da manhã» perdia os minutos e «dps» não era reconhecido
MODO["holdout"] = False
valido("amanhã 9h30 da manhã", QUI18, f"{AMANHA} 09:30", tag="regressao")
valido("às 15h30 da tarde", QUI10, f"{HOJE} 15:30", tag="regressao")
valido("dps das 6", QUI10, f"{HOJE} 18:15", "m", tag="regressao")

# regressões da revisão adversarial 1 (docs/REVISAO-B5.7a-3010.md): cada item R1-R10 tem o caso que reprovava
valido("às 10h30 da manhã", QUI10, f"{HOJE} 10:30", tag="regressao")  # era hold-out e ensinou a correção: saiu do hold-out
valido("dps das 4 eu falo", QUI10, f"{HOJE} 16:15", "m", tag="regressao")  # idem
vazio("31/11 às 15h", QUI10, "data_invalida", tag="regressao")  # R1
vazio("29/02/2027 às 15h", QUI10, "data_invalida", tag="regressao")  # R1
vazio("hoje às 19:01:00", QUI10, "sem_hora_explicita", tag="regressao")  # R2
vazio("às 15:99", QUI10, "sem_hora_explicita", tag="regressao")  # R2
valido("às 15h e meia", QUI10, f"{HOJE} 15:30", tag="regressao")  # R2
vazio("às 15 e trinta e cinco", QUI10, "sem_hora_explicita", tag="regressao")  # R2
vazio("às dozentas parcelas", QUI10, "sem_hora_explicita", tag="regressao")  # R2
valido("daqui a uma hora e quinze minutos", "2026-11-05 10:00", f"{HOJE} 11:15", tag="regressao")  # R2
caso("às 15h ou 16:30", QUI10, [f"{HOJE} 15:00", f"{HOJE} 16:30"], None, "mm", tag="regressao")  # R3
caso("umas 3 da tarde", QUI10, [f"{HOJE} 15:00"], None, "m", tag="regressao")  # R4
caso("hoje ou amanhã daqui a 1 hora", QUI10, [f"{HOJE} 11:00"], None, "m", tag="regressao")  # R5
vazio("amanhã daqui a 1 hora", QUI10, "dia_contraditorio", tag="regressao")  # R5
vazio("tenho entre 15 e 16 parcelas", QUI10, "sem_hora_explicita", tag="regressao")  # R7
for t in [
    "tenho 12 parcelas",
    "R$ 15",
    "preciso de 2 contratos",
    "entre 12 e 24 meses",
    "as 2 contratos",
    "umas 12 parcelas",
    "me paga em 12 vezes",
]:
    vazio(t, tag="regressao")  # R7: quantidade nunca vira hora
fora("meia-noite e meia", QUI10, "2026-11-06 00:30", "antes_da_janela", "m", tag="regressao")  # R10

for i, c in enumerate(CASOS, 1):
    c["id"] = f"{'ho' if c['holdout'] else 'dev'}-{i:03d}"


def main() -> int:
    linhas = [json.dumps(c, ensure_ascii=False, sort_keys=True) for c in CASOS]
    DESTINO.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    ho = sum(1 for c in CASOS if c["holdout"])
    print(f"{len(CASOS)} frases ({ho} hold-out) -> {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
