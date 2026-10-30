"""Auxiliares das regras."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime

from ia_atendimento.corpus.modelos import Corpus, Persona, Turno

Regra = Callable[[Corpus], list[str]]


def mensagem_da_ia(t: Turno) -> bool:
    """Turno da IA que ENVIA algo ao cliente (TX ou texto livre do modelo). Sem isso é silêncio."""
    return t.quem == "ia" and bool(t.tx_esperado or t.texto_livre_ia)


def contagem(personas: Iterable[Persona], extrair: Callable[[Persona], Iterable[str]]) -> Counter[str]:
    c: Counter[str] = Counter()
    for p in personas:
        c.update(set(extrair(p)))
    return c


def instantes(inicio: datetime | None, turnos: Sequence[Turno]) -> list[datetime | None]:
    """Instante efetivo de cada turno: o `em_utc` dele, ou o último conhecido (começa no início da persona)."""
    atual = inicio
    saida: list[datetime | None] = []
    for t in turnos:
        atual = t.em_utc or atual
        saida.append(atual)
    return saida


def dialogos_com_persona(corpus: Corpus):
    """(id, persona, diálogo) de cada diálogo cuja persona existe (H ou M)."""
    por_id = {p.id: p for p in corpus.todas()}
    for pid, d in corpus.dialogos.items():
        if pid in por_id:
            yield pid, por_id[pid], d


def precisa_de_dialogo(p: Persona) -> bool:
    """F3 curta (H) ou P-M crítica: as que o harness roda."""
    return p.f3_curta or p.critica
