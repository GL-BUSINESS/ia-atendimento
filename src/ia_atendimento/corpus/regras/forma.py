"""Forma das falas do cliente (levantamento 09 §3): curtas, quase só texto, e variadas."""

from __future__ import annotations

import statistics

from ia_atendimento.corpus.modelos import Corpus
from ia_atendimento.corpus.vocabulario import (
    MAX_CARACTERES_FORA_DA_MANIPULACAO,
    MAX_FRACAO_MIDIA,
    MEDIANA_MAX_CARACTERES,
    MIN_FRACAO_FALAS_DISTINTAS,
)


def forma_whatsapp(corpus: Corpus) -> list[str]:
    """Falas curtas (p50 de 11 caracteres), quase tudo texto; texto longo só na persona de manipulação."""
    textos: list[tuple[str, str]] = []
    cliente = midia = 0
    for pid, d in corpus.dialogos.items():
        for t in d.turnos:
            if t.quem == "cliente":
                cliente += 1
                midia += t.midia is not None
                if t.texto_cliente is not None:
                    textos.append((pid, t.texto_cliente))
    por_id = {p.id: p for p in corpus.todas()}
    erros = []
    if textos and (mediana := statistics.median(len(x) for _, x in textos)) > MEDIANA_MAX_CARACTERES:
        erros.append(f"forma_whatsapp: mediana de {mediana} caracteres (máximo {MEDIANA_MAX_CARACTERES}; no real p50 = 11)")
    if cliente and midia / cliente > MAX_FRACAO_MIDIA:
        erros.append(f"forma_whatsapp: {midia}/{cliente} turnos de mídia (máximo {MAX_FRACAO_MIDIA:.0%})")
    erros += [
        f"forma_whatsapp: {pid}: texto de {len(x)} caracteres fora da persona de manipulação"
        for pid, x in textos
        if len(x) > MAX_CARACTERES_FORA_DA_MANIPULACAO and por_id[pid].classe != "manipulacao"
    ]
    return erros


def variedade_das_falas(corpus: Corpus) -> list[str]:
    """Falas repetidas demais («oi» 35x, «pode ser» 25x) deixam a meta de 95% de intenção «de graça»."""
    textos = [t.texto_cliente for d in corpus.dialogos.values() for t in d.turnos if t.texto_cliente is not None]
    if textos and len(set(textos)) / len(textos) < MIN_FRACAO_FALAS_DISTINTAS:
        return [
            f"variedade_das_falas: {len(set(textos))} textos distintos em {len(textos)} falas (mínimo {MIN_FRACAO_FALAS_DISTINTAS:.0%})"
        ]
    return []
