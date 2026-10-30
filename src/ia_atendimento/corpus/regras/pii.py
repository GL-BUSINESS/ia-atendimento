"""Regras de dado pessoal e de texto: PII em qualquer campo, placeholders e TX do conjunto fechado, nomes."""

from __future__ import annotations

from collections.abc import Iterator

from ia_atendimento.corpus.modelos import Corpus, como_dict
from ia_atendimento.corpus.pii import PLACEHOLDER, achados_pii, pii_nao_sintetica, strings
from ia_atendimento.corpus.vocabulario import PLACEHOLDERS, TX_IDS


def _pii_sintetica_declarada(corpus: Corpus) -> list[str]:
    """Texto do cliente (e variações): só PII sintética e sempre declarada em `pii_digitada`."""
    erros: list[str] = []
    for pid, d in corpus.dialogos.items():
        for i, t in enumerate(d.turnos):
            if t.texto_cliente is None:
                continue
            declarados = set(t.pii_digitada)
            for k, texto in enumerate((t.texto_cliente, *t.variacoes)):
                achados = achados_pii(texto)
                erros += [
                    f"pii_texto: {pid} turno {i}: {tipo} fora do conjunto sintético ({valor!r})"
                    for tipo, valor in achados
                    if pii_nao_sintetica(tipo, valor)
                ]
                erros += [
                    f"pii_texto: {pid} turno {i}: {tipo} no texto sem constar de pii_digitada"
                    for tipo in sorted({t_ for t_, _ in achados} - declarados)
                ]
                if k == 0:
                    erros += [
                        f"pii_texto: {pid} turno {i}: pii_digitada diz {tipo} mas o texto não tem"
                        for tipo in sorted(declarados - {t_ for t_, _ in achados})
                    ]
    return erros


def _sem_pii_nenhuma(corpus: Corpus) -> list[str]:
    """Todo o resto (persona, evento, nota, snapshot do dublê, regras da semente...) NÃO pode ter PII, nem a sintética."""
    erros: list[str] = []
    fontes: list[tuple[str, object]] = []
    for p in corpus.todas():
        fontes.append((p.id, como_dict(p, exclude={"cpf", "contexto"})))
    for pid, d in corpus.dialogos.items():
        for i, t in enumerate(d.turnos):
            fontes.append(
                (f"{pid} turno {i}", como_dict(t, exclude={"texto_cliente", "variacoes", "em_utc", "dispara_em_utc", "pii_digitada"}))
            )
    fontes.append(("duble", como_dict(corpus.duble, exclude={"personas": {"__all__": {"cpf"}}})))
    fontes.append(("semente.regras", corpus.semente.regras))
    for onde, dump in fontes:
        for caminho, valor in strings(dump):
            erros += [f"pii_texto: {onde}.{caminho}: {tipo} em campo que não é fala do cliente" for tipo, _ in achados_pii(valor)]
    return erros


def pii_texto(corpus: Corpus) -> list[str]:
    return _pii_sintetica_declarada(corpus) + _sem_pii_nenhuma(corpus)


def _todos_os_textos(corpus: Corpus) -> Iterator[tuple[str, str]]:
    for p in corpus.todas():
        yield from ((f"{p.id}.{c}", v) for c, v in strings(como_dict(p)))
    for pid, d in corpus.dialogos.items():
        yield from ((f"{pid}.{c}", v) for c, v in strings(como_dict(d)))


def placeholder_fechado(corpus: Corpus) -> list[str]:
    erros = []
    for onde, texto in _todos_os_textos(corpus):
        for m in PLACEHOLDER.finditer(texto):
            if m.group(1) not in PLACEHOLDERS:
                erros.append(f"placeholder_fechado: {onde}: {{{{{m.group(1)}}}}} fora do conjunto fechado dos TX")
        resto = PLACEHOLDER.sub("", texto)
        if "{{" in resto or "}}" in resto:
            erros.append(f"placeholder_fechado: {onde}: chaves duplas sem par")
    for pid, d in corpus.dialogos.items():
        erros += [
            f"placeholder_fechado: {pid}: {tx} não é um TX da lista aprovável" for t in d.turnos for tx in t.tx_esperado if tx not in TX_IDS
        ]
    return erros
