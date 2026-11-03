"""Auxiliares das regras."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime

from ia_atendimento.corpus.modelos import Corpus, Persona, Turno
from ia_atendimento.corpus.vocabulario import SIMS

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


def base_do_duble(corpus: Corpus, persona_duble: str | None) -> str | None:
    """A persona-base do dublê: um clone (B2.4, R1-09: uma persona do dublê por persona da F3) aponta para a base pelo `clone_de`."""
    if persona_duble is None:
        return None
    por_id = {d.id: d for d in corpus.duble.personas}
    return por_id[persona_duble].clone_de or persona_duble if persona_duble in por_id else persona_duble


def dialogos_com_persona(corpus: Corpus):
    """(id, persona, diálogo) de cada diálogo cuja persona existe (H ou M)."""
    por_id = {p.id: p for p in corpus.todas()}
    for pid, d in corpus.dialogos.items():
        if pid in por_id:
            yield pid, por_id[pid], d


def precisa_de_dialogo(p: Persona) -> bool:
    """F3 curta (H) ou P-M crítica: as que o harness roda."""
    return p.f3_curta or p.critica


PEDIDO_DE_CONFIRMACAO = frozenset({"TX-11", "TX-12", "TX-13"})


def e_texto_sim(texto: str) -> bool:
    """SIM explícito e ISOLADO (H §2.3 + TX-36): o texto inteiro, sem acento nem maiúsculas, com «!»/«.» no fim e vírgula tolerados,
    é UM dos SIMS. Outro caractere (`?`, emoji, palavra a mais) tira o SIM: «sim?», «sim 👍», «sim, mas...», «claro», «ok», «bora»."""
    t = "".join(ch for ch in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(ch) != "Mn").strip()
    t = re.sub(r"[!.]+$", "", t).replace(",", " ")
    return re.sub(r"\s+", " ", t).strip() in SIMS


def redacoes(t: Turno) -> list[str]:
    return [t.texto_cliente or "", *t.variacoes]


def e_sim_literal(t: Turno) -> bool:
    """O TEXTO (e toda variação) do cliente é um SIM isolado."""
    return t.texto_cliente is not None and all(e_texto_sim(x) for x in redacoes(t))
