"""Regras da semente e do hold-out."""

from __future__ import annotations

from collections import Counter

from ia_atendimento.corpus.modelos import Corpus, Dialogo
from ia_atendimento.corpus.semente import derivar_semente
from ia_atendimento.corpus.vocabulario import (
    EXECUCOES_POR_PERSONA,
    MAX_CARACTERES_DE_FALA_GENERICA,
    MAX_FRACAO_DE_FALAS_REPETIDAS_NO_HOLDOUT,
)


def semente_reprodutivel(corpus: Corpus) -> list[str]:
    s = corpus.semente
    esperado = derivar_semente(corpus.personas, s.semente_global, [p.id for p in corpus.personas_m])
    erros = []
    if s.versao != 1 or s.execucoes_por_persona != EXECUCOES_POR_PERSONA:
        erros.append("semente_reprodutivel: versão 1 e 3 execuções por persona")
    if s.ordem_personas != esperado["ordem_personas"]:
        erros.append("semente_reprodutivel: ordem_personas não é a derivada da semente global")
    if s.ordem_f3_curta != esperado["ordem_f3_curta"]:
        erros.append("semente_reprodutivel: ordem_f3_curta não é a derivada da semente global")
    if s.holdout != esperado["holdout"]:
        erros.append(f"semente_reprodutivel: hold-out diferente do derivado ({list(esperado['holdout'])})")
    faltam = sorted(set(esperado["sementes"]) - set(s.sementes))
    if faltam:
        erros.append(f"semente_reprodutivel: personas sem sementes de execução {faltam}")
    erros += [
        f"semente_reprodutivel: sementes de {pid} diferentes das derivadas"
        for pid, v in s.sementes.items()
        if pid in esperado["sementes"] and list(v) != esperado["sementes"][pid]
    ]
    erros += [f"semente_reprodutivel: sementes de persona inexistente {pid}" for pid in sorted(set(s.sementes) - set(esperado["sementes"]))]
    return erros


def esqueleto(d: Dialogo) -> tuple:
    """Quem fala, em que fase, com que TX e que intenção: o «desenho» do diálogo, sem o texto."""
    return tuple((t.quem, t.fase_esperada, t.tx_esperado, t.intencao_esperada) for t in d.turnos)


def roteiro_do_cliente(d: Dialogo) -> tuple:
    """O que o cliente faz (fase e intenção por turno), sem o que a IA responde."""
    return tuple((t.fase_esperada, t.intencao_esperada) for t in d.turnos if t.quem == "cliente")


def _fala_especifica(t) -> bool:
    return (
        t.texto_cliente is not None
        and not t.pii_digitada
        and not t.campo_alvo
        and len(normalizar_curto(t.texto_cliente)) > MAX_CARACTERES_DE_FALA_GENERICA
    )


def normalizar_curto(texto: str) -> str:
    return " ".join(texto.lower().split())


def holdout_independente(corpus: Corpus) -> list[str]:
    """O hold-out não é clone do desenvolvimento: esqueleto E roteiro do cliente (fase, intenção) únicos, falas específicas repetidas em
    menos de 25% e, fora do caminho feliz, persona do dublê própria."""
    erros: list[str] = []
    holdout = set(corpus.semente.holdout)
    esqueletos = Counter(esqueleto(d) for d in corpus.dialogos.values())
    roteiros = Counter(roteiro_do_cliente(d) for d in corpus.dialogos.values())
    por_id = {p.id: p for p in corpus.todas()}
    do_desenvolvimento = {
        normalizar_curto(t.texto_cliente)
        for pid, d in corpus.dialogos.items()
        if pid not in holdout
        for t in d.turnos
        if _fala_especifica(t)
    }
    for pid in sorted(holdout & set(corpus.dialogos)):
        d = corpus.dialogos[pid]
        if esqueletos[esqueleto(d)] > 1:
            erros.append(f"holdout_independente: {pid} (hold-out) tem o mesmo esqueleto de diálogo de outra persona")
        if roteiros[roteiro_do_cliente(d)] > 1:
            erros.append(
                f"holdout_independente: {pid} (hold-out) tem o mesmo roteiro do cliente (fase e intenção por turno) de outra persona"
            )
        falas = [normalizar_curto(t.texto_cliente) for t in d.turnos if _fala_especifica(t)]
        repetidas = sum(f in do_desenvolvimento for f in falas)
        if falas and repetidas / len(falas) >= MAX_FRACAO_DE_FALAS_REPETIDAS_NO_HOLDOUT:
            erros.append(f"holdout_independente: {pid} (hold-out) repete {repetidas}/{len(falas)} falas do desenvolvimento (máximo < 25%)")
    for pid in sorted(holdout):
        duble = por_id[pid].cenario_facta.persona_duble
        cenario = por_id[pid].cenario_facta.cenario
        if duble and cenario != "aprovado":
            outras = sorted(p.id for p in corpus.todas() if p.id != pid and p.id not in holdout and p.cenario_facta.persona_duble == duble)
            if outras:
                erros.append(f"holdout_independente: {pid} (hold-out) divide a persona {duble} do dublê com {outras}")
    return erros
