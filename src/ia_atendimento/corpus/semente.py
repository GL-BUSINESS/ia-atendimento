"""Semente determinística: ordem das personas, hold-out (20%), sementes das 3 execuções e escolha da redação do cliente."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from typing import Any

from ia_atendimento.corpus.modelos import Persona, Turno
from ia_atendimento.corpus.vocabulario import EXECUCOES_POR_PERSONA, FRACAO_HOLDOUT


def chave(semente_global: int, *partes: object) -> int:
    resumo = hashlib.sha256("|".join(str(p) for p in (semente_global, *partes)).encode()).hexdigest()
    return int(resumo[:16], 16)


def escolher_variacao(semente_global: int, persona_id: str, execucao: int, indice_turno: int, n_opcoes: int) -> int:
    """Índice (0 = texto original) da redação usada no turno `indice_turno` da `execucao` da persona; mesma entrada, mesma saída."""
    if n_opcoes < 1:
        raise ValueError("n_opcoes deve ser >= 1")
    return chave(semente_global, "variacao", persona_id, execucao, indice_turno) % n_opcoes


def texto_do_turno(turno: Turno, semente_global: int, persona_id: str, execucao: int, indice_turno: int) -> str:
    if turno.texto_cliente is None:
        raise ValueError("turno sem texto (mídia ou turno da IA)")
    opcoes = (turno.texto_cliente, *turno.variacoes)
    return opcoes[escolher_variacao(semente_global, persona_id, execucao, indice_turno, len(opcoes))]


def _escolhe_por_classe(candidatos: Sequence[Persona], quantos: int, semente_global: int) -> list[str]:
    """Um por classe (o de menor chave), depois os `quantos` de menor chave entre esses: o hold-out espalha-se pelas classes."""
    melhor: dict[str, Persona] = {}
    for p in sorted(candidatos, key=lambda x: (chave(semente_global, "holdout", x.id), x.id)):
        melhor.setdefault(p.classe, p)
    escolhidos = sorted(melhor.values(), key=lambda x: (chave(semente_global, "holdout-classe", x.classe), x.classe))[:quantos]
    return [p.id for p in escolhidos]


def derivar_semente(personas: Sequence[Persona], semente_global: int, ids_m: Iterable[str] = ()) -> dict[str, Any]:
    """Reconstrói do zero o que `semente.json` guarda: ordem das personas, hold-out (20%) e as sementes das 3 execuções por persona."""
    ids = [p.id for p in personas]
    ordem = sorted(ids, key=lambda i: (chave(semente_global, "ordem", i), i))
    f3 = [p for p in personas if p.f3_curta]
    resto = [p for p in personas if not p.f3_curta]
    holdout = _escolhe_por_classe(f3, round(len(f3) * FRACAO_HOLDOUT), semente_global)
    holdout += _escolhe_por_classe(resto, round(len(resto) * FRACAO_HOLDOUT), semente_global)
    sementes = {
        pid: [chave(semente_global, "execucao", pid, k) % 2**31 for k in range(1, EXECUCOES_POR_PERSONA + 1)] for pid in (*ids, *ids_m)
    }
    return {
        "ordem_personas": tuple(ordem),
        "ordem_f3_curta": tuple(i for i in ordem if i in {p.id for p in f3}),
        "holdout": tuple(sorted(holdout, key=lambda i: (chave(semente_global, "ordem", i), i))),
        "sementes": sementes,
    }
