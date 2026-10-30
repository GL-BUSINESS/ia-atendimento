"""Gabarito do agendamento (M §2.4-§2.6): a volta cai na janela da agenda, em até 23 h do último cliente, no máximo 2 por atendimento."""

from __future__ import annotations

from datetime import timedelta

from ia_atendimento.corpus.calendario import ANTECEDENCIA_MINIMA, dentro_da_agenda
from ia_atendimento.corpus.modelos import Corpus
from ia_atendimento.corpus.regras._comum import dialogos_com_persona, instantes
from ia_atendimento.corpus.vocabulario import AGENDA_MAX_HORAS

MAX_AGENDAMENTOS = 2
FOLGA_DA_VOLTA = timedelta(minutes=30)  # agenda_folga_min: depois disso a vigia devolve


def gabarito_agenda(corpus: Corpus) -> list[str]:
    erros: list[str] = []
    for pid, persona, d in dialogos_com_persona(corpus):
        ultimo_cliente, dispara, confirmados = None, None, 0
        for i, (t, quando) in enumerate(zip(d.turnos, instantes(persona.contexto.inicio_utc, d.turnos), strict=True)):
            onde = f"gabarito_agenda: {pid} turno {i}"
            if t.quem == "cliente":
                ultimo_cliente = quando
                continue
            confirma = "TX-M08" in t.tx_esperado
            if t.dispara_em_utc is not None and not confirma:
                erros.append(f"{onde}: dispara_em_utc só no turno que confirma a volta (TX-M08)")
            if confirma:
                confirmados += 1
                alvo = t.dispara_em_utc
                if alvo is None:
                    erros.append(f"{onde}: TX-M08 sem dispara_em_utc")
                    continue
                dispara = alvo
                if "agendar" not in t.acoes_permitidas:
                    erros.append(f"{onde}: TX-M08 sem a ação `agendar`")
                if not dentro_da_agenda(alvo):
                    erros.append(
                        f"{onde}: volta fora da janela da agenda (seg-sáb 08:30-19:00, sábado até 12:00, fora de feriado/DATAPREV)"
                    )
                if quando is not None and alvo - quando < ANTECEDENCIA_MINIMA:
                    erros.append(f"{onde}: volta com menos de 10 min de antecedência")
                if ultimo_cliente is not None and alvo - ultimo_cliente > timedelta(hours=AGENDA_MAX_HORAS):
                    erros.append(f"{onde}: volta a mais de {AGENDA_MAX_HORAS} h do último cliente (janela de 24 h do WhatsApp)")
                if confirmados > MAX_AGENDAMENTOS:
                    erros.append(f"{onde}: mais de {MAX_AGENDAMENTOS} agendamentos no mesmo atendimento")
            elif t.evento == "volta_combinada":
                if dispara is None:
                    erros.append(f"{onde}: volta sem agendamento confirmado antes")
                elif quando is None or not dispara <= quando <= dispara + FOLGA_DA_VOLTA:
                    erros.append(f"{onde}: a volta não cai entre o horário combinado e +30 min")
    return erros
