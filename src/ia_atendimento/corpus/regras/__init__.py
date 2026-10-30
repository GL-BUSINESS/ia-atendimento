"""As regras do validador do corpus: cada uma é uma função `Corpus -> list[str]` com mensagens `codigo: texto`; `REGRAS` as junta."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from ia_atendimento.corpus.carga import montar
from ia_atendimento.corpus.regras import agenda, cobertura, forma, gabarito, invariantes, personas, pii
from ia_atendimento.corpus.regras import semente as regras_semente
from ia_atendimento.corpus.regras._comum import Regra

REGRAS: dict[str, Regra] = {
    "ids_unicos": personas.ids_unicos,
    "nome_ficticio": personas.nome_ficticio,
    "cpf_sintetico": personas.cpf_sintetico_regra,
    "cpf_alinhado_duble": personas.cpf_alinhado_duble,
    "conjunto_f3_curta": personas.conjunto_f3_curta,
    "f3_com_dialogo": personas.f3_com_dialogo,
    "cenario_tempo_coerente": personas.cenario_tempo_coerente,
    "cobertura_invariantes": cobertura.cobertura_invariantes,
    "cobertura_fases": cobertura.cobertura_fases,
    "cobertura_intencoes": cobertura.cobertura_intencoes,
    "cobertura_objecoes": cobertura.cobertura_objecoes,
    "cobertura_em": cobertura.cobertura_em,
    "cobertura_cenarios": cobertura.cobertura_cenarios,
    "cobertura_dialogos": cobertura.cobertura_dialogos,
    "invariantes_do_dialogo": cobertura.invariantes_do_dialogo,
    "pii_texto": pii.pii_texto,
    "placeholder_fechado": pii.placeholder_fechado,
    "dialogo_gabarito": gabarito.dialogo_gabarito,
    "gabarito_acoes_por_fase": gabarito.gabarito_acoes_por_fase,
    "gabarito_fase_tx": gabarito.gabarito_fase_tx,
    "gabarito_tx_composto": gabarito.gabarito_tx_composto,
    "gabarito_transicoes": gabarito.gabarito_transicoes,
    "gabarito_silencio": gabarito.gabarito_silencio,
    "gabarito_seguranca": gabarito.gabarito_seguranca,
    "e5_completa": gabarito.e5_completa,
    "gabarito_sim_literal": gabarito.gabarito_sim_literal,
    "gabarito_janela24h": gabarito.gabarito_janela24h,
    "t7_so_com_oferta_facta": gabarito.gabarito_t7_so_com_oferta_facta,
    "gabarito_i1": invariantes.gabarito_i1,
    "gabarito_i3": invariantes.gabarito_i3,
    "gabarito_i4": invariantes.gabarito_i4,
    "gabarito_i6": invariantes.gabarito_i6,
    "gabarito_i7": invariantes.gabarito_i7,
    "gabarito_i8": invariantes.gabarito_i8,
    "gabarito_agenda": agenda.gabarito_agenda,
    "desfecho_coerente": invariantes.desfecho_coerente,
    "forma_whatsapp": forma.forma_whatsapp,
    "variedade_das_falas": forma.variedade_das_falas,
    "semente_reprodutivel": regras_semente.semente_reprodutivel,
    "holdout_independente": regras_semente.holdout_independente,
}


def validar(bruto: dict[str, Any]) -> list[str]:
    """Todas as violações do corpus, `codigo: mensagem`. Lista vazia = corpus bom. Esquema inválido vira `esquema: …` e para por aí."""
    try:
        corpus = montar(bruto)
    except ValidationError as erro:
        return [f"esquema: {'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in erro.errors()]
    return [violacao for regra in REGRAS.values() for violacao in regra(corpus)]
