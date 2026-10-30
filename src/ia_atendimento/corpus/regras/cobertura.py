"""Cobertura: o que as personas e os diálogos exercitam (declarado nas personas × realmente presente nos diálogos)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable

from ia_atendimento.corpus.modelos import Corpus, Persona
from ia_atendimento.corpus.regras._comum import contagem
from ia_atendimento.corpus.vocabulario import (
    CENARIOS_DE_TEMPO,
    EMS,
    FASES,
    INTENCOES,
    INVARIANTES,
    MIN_PERSONAS_POR_INVARIANTE,
    MIN_TURNOS_DE_TEXTO_LIVRE,
    MIN_TURNOS_POR_INTENCAO,
    OBJECOES,
)


def _falta(esperado: Iterable[str], c: Counter[str], codigo: str, rotulo: str) -> list[str]:
    return [f"{codigo}: {rotulo} {x} sem nenhuma persona" for x in esperado if c[x] < 1]


def cobertura_invariantes(corpus: Corpus) -> list[str]:
    holdout = set(corpus.semente.holdout)
    todas = contagem(corpus.todas(), lambda p: p.invariantes_em_risco)
    dev = contagem((p for p in corpus.todas() if p.id not in holdout), lambda p: p.invariantes_em_risco)
    erros = [
        f"cobertura_invariantes: {i} testado por {todas[i]} persona(s) (mínimo {MIN_PERSONAS_POR_INVARIANTE})"
        for i in INVARIANTES
        if todas[i] < MIN_PERSONAS_POR_INVARIANTE
    ]
    erros += [
        f"cobertura_invariantes: {i} testado por {dev[i]} persona(s) fora do hold-out (mínimo {MIN_PERSONAS_POR_INVARIANTE})"
        for i in INVARIANTES
        if dev[i] < MIN_PERSONAS_POR_INVARIANTE <= todas[i]
    ]
    return erros


def cobertura_fases(corpus: Corpus) -> list[str]:
    return _falta(FASES, contagem(corpus.todas(), lambda p: p.fases), "cobertura_fases", "fase")


def cobertura_intencoes(corpus: Corpus) -> list[str]:
    return _falta(INTENCOES, contagem(corpus.todas(), lambda p: p.comportamento.intencoes), "cobertura_intencoes", "intenção")


def cobertura_objecoes(corpus: Corpus) -> list[str]:
    return _falta(OBJECOES, contagem(corpus.todas(), lambda p: p.comportamento.objecoes), "cobertura_objecoes", "objeção")


def cobertura_em(corpus: Corpus) -> list[str]:
    return _falta(EMS, contagem(corpus.todas(), lambda p: p.em), "cobertura_em", "caso de M")


def _testes_de_cenario() -> dict[str, Callable[[Persona], bool]]:
    return {
        **{f"cenario_tempo {t}": (lambda p, t=t: p.contexto.cenario_tempo == t) for t in CENARIOS_DE_TEMPO},
        "cliente hostil": lambda p: p.comportamento.hostil,
        "cliente que pede humano": lambda p: p.comportamento.pede_humano != "nao",
        "cliente que muda de ideia": lambda p: p.comportamento.muda_de_ideia,
        "lead que some após E3": lambda p: p.comportamento.some_apos == "E3",
        "adia com hora": lambda p: p.comportamento.adia == "com_hora",
        "adia sem hora": lambda p: p.comportamento.adia == "sem_hora",
        "digita CPF no texto": lambda p: p.comportamento.digita_cpf_no_texto,
        "digita telefone no texto": lambda p: p.comportamento.digita_telefone_no_texto,
        "áudio": lambda p: "audio" in p.comportamento.midia,
        "imagem": lambda p: "imagem" in p.comportamento.midia,
        "recusa FACTA status 28 (AF cancelada)": lambda p: p.cenario_facta.cenario == "af_cancelada",
        "estilo áudio": lambda p: "audio" in p.comportamento.estilo,
        "estilo sem acento": lambda p: "sem_acento" in p.comportamento.estilo,
        "estilo emoji": lambda p: "emoji" in p.comportamento.estilo,
    }


def cobertura_cenarios(corpus: Corpus) -> list[str]:
    """Cenários que o roteiro e o pedido exigem: tempo (noite, sábado, domingo, feriado, DATAPREV, 22:30 UTC), humano, hostil, mídia..."""
    todas = corpus.todas()
    return [
        f"cobertura_cenarios: nenhuma persona para «{nome}»"
        for nome, teste in _testes_de_cenario().items()
        if not any(teste(p) for p in todas)
    ]


def cobertura_dialogos(corpus: Corpus) -> list[str]:
    """O que a B8.2 roda: toda intenção, objeção e fase aparece em ALGUM turno, e todo cenário de tempo tem persona com diálogo."""
    intencoes: Counter[str] = Counter()
    objecoes: set[str] = set()
    fases: set[str] = set()
    tx: set[str] = set()
    for d in corpus.dialogos.values():
        for t in d.turnos:
            fases.add(t.fase_esperada)
            tx.update(t.tx_esperado)
            if t.intencao_esperada:
                intencoes[t.intencao_esperada] += 1
            if t.objecao_esperada:
                objecoes.add(t.objecao_esperada)
    livres = sum(t.texto_livre_ia for d in corpus.dialogos.values() for t in d.turnos)
    com_dialogo = [p for p in corpus.todas() if p.id in corpus.dialogos]
    tempos = {p.contexto.cenario_tempo for p in com_dialogo}
    erros = [
        f"cobertura_dialogos: intenção {i} com {intencoes[i]} turno(s) de diálogo (mínimo {MIN_TURNOS_POR_INTENCAO})"
        for i in INTENCOES
        if intencoes[i] < MIN_TURNOS_POR_INTENCAO
    ]
    erros += [
        f"cobertura_dialogos: {x} sem nenhum turno de diálogo (negativo do SIM e nova confirmação)"
        for x in ("TX-36", "TX-12")
        if x not in tx
    ]
    erros += [f"cobertura_dialogos: objeção {o} sem nenhum turno de diálogo" for o in OBJECOES if o not in objecoes]
    erros += [f"cobertura_dialogos: fase {f} sem nenhum turno de diálogo" for f in FASES if f not in fases]
    erros += [f"cobertura_dialogos: cenário de tempo {t} sem persona com diálogo" for t in CENARIOS_DE_TEMPO if t not in tempos]
    if livres < MIN_TURNOS_DE_TEXTO_LIVRE:
        erros.append(
            f"cobertura_dialogos: {livres} turnos com `texto_livre_ia` (mínimo {MIN_TURNOS_DE_TEXTO_LIVRE}; é onde I2 e I9 quebram)"
        )
    return erros


def invariantes_do_dialogo(corpus: Corpus) -> list[str]:
    erros = []
    for p in corpus.todas():
        d = corpus.dialogos.get(p.id)
        if d is None:
            continue
        falta = set(p.invariantes_em_risco) - {i for t in d.turnos for i in t.invariantes}
        if falta:
            erros.append(f"invariantes_do_dialogo: {p.id}: invariantes em risco que nenhum turno do diálogo testa {sorted(falta)}")
    return erros
