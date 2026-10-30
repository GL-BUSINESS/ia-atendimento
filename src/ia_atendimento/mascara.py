"""Máscara determinística de PII para o texto que vai à `conversa_cifrada` (`mascarado = true`; roteiro B1.2).

Entra texto do cliente; sai texto com marcadores fixos (`[CPF]`, `[TELEFONE]`, `[EMAIL]`, `[CEP]`, `[UUID]`, `[NUMERO]`,
`[NOME]`). Só regex e aritmética, sem modelo: mesma entrada, mesma saída, e `mascarar(mascarar(x)) == mascarar(x)`.
Excesso de máscara é aceito (melhor mascarar demais que vazar); falta de máscara não.

Ordem: e-mail, UUID, CPF, CEP, telefone, número longo (8+ dígitos) e, por último, nomes marcados pelo chamador.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

CPF, TELEFONE, EMAIL, CEP, UUID, NUMERO, NOME = (f"[{r}]" for r in ("CPF", "TELEFONE", "EMAIL", "CEP", "UUID", "NUMERO", "NOME"))

_SEP = r"[  .\-]"
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
_UUID = re.compile(r"(?<![0-9A-Za-z])[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?![0-9A-Za-z])")
_CPF_FORMATADO = re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)")
_ONZE_DIGITOS = re.compile(r"(?<!\d)\d{11}(?!\d)")
_CEP_COM_ROTULO = re.compile(r"(\bcep\b[\s:.\-]*)(\d{5}[ .\-]?\d{3})(?!\d)", re.IGNORECASE)
_CEP_FORMATADO = re.compile(r"(?<!\d)\d{5}-\d{3}(?!\d)")
# Telefone: celular com DDD (9 dígitos), fixo com DDD, ou 8/9 dígitos COM hífen. Não pode continuar em mais dígitos
# (senão "1234 5678 9012 3456" viraria telefone + sobra); 8 dígitos soltos caem em [NUMERO].
_TELEFONE = re.compile(
    rf"(?<!\d)(?:"
    rf"(?:\+?55{_SEP}?)?\(?\d{{2}}\)?{_SEP}?9\d{{4}}{_SEP}?\d{{4}}"
    rf"|(?:\+?55{_SEP}?)?\(?\d{{2}}\)?{_SEP}?[2-5]\d{{3}}{_SEP}?\d{{4}}"
    rf"|9\d{{4}}-\d{{4}}|[2-5]\d{{3}}-\d{{4}}"
    rf")(?!{_SEP}?\d)"
)
_NUMERO_LONGO = re.compile(rf"(?<!\d)\d(?:{_SEP}?\d){{7,}}(?!\d)")
_MARCADORES = re.compile(r"\[(?:CPF|TELEFONE|EMAIL|CEP|UUID|NUMERO|NOME)\]")
_PARTICULAS = frozenset({"da", "de", "do", "das", "dos", "di", "du", "del", "van", "von", "der", "las", "los"})
_TAMANHO_MIN_PARTE = 3


def _cpf_valido(onze: str) -> bool:
    if len(set(onze)) == 1:
        return False
    for tamanho in (9, 10):
        soma = sum(int(d) * p for d, p in zip(onze[:tamanho], range(tamanho + 1, 1, -1), strict=True))
        if (soma * 10) % 11 % 10 != int(onze[tamanho]):
            return False
    return True


def _trocar_cpf(achado: re.Match[str]) -> str:
    return CPF if _cpf_valido(achado.group()) else achado.group()


def _base(caractere: str) -> str:
    sem_acento = unicodedata.normalize("NFD", caractere)[0]
    minusculo = sem_acento.lower()
    return minusculo if len(minusculo) == 1 else sem_acento


def _dobrar(texto: str) -> str:
    """Sem acento e sem caixa, SEMPRE com o mesmo comprimento do original (os índices valem nos dois)."""
    return "".join(_base(c) for c in texto)


def _partes_de_nome(nomes: Iterable[str]) -> list[str]:
    partes: set[str] = set()
    for nome in nomes:
        dobrado = _dobrar(nome).strip()
        if not dobrado:
            continue
        partes.add(" ".join(dobrado.split()))
        partes.update(p for p in dobrado.split() if len(p) >= _TAMANHO_MIN_PARTE and p not in _PARTICULAS)
    return sorted(partes, key=lambda p: (-len(p), p))


def _mascarar_nomes(texto: str, nomes: Iterable[str]) -> str:
    partes = _partes_de_nome(nomes)
    if not partes:
        return texto
    dobrado = _dobrar(texto)
    padrao = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(p).replace(r"\ ", r"\s+") for p in partes) + r")(?!\w)")
    protegidos = [m.span() for m in _MARCADORES.finditer(texto)]
    saida: list[str] = []
    cursor = 0
    for achado in padrao.finditer(dobrado):
        inicio, fim = achado.span()
        if any(inicio < pf and fim > pi for pi, pf in protegidos):
            continue  # não mexe dentro de [CPF], [EMAIL]...
        saida.append(texto[cursor:inicio])
        saida.append(NOME)
        cursor = fim
    saida.append(texto[cursor:])
    return "".join(saida)


def mascarar(texto: str, nomes: Iterable[str] = ()) -> str:
    """Troca PII por marcadores. `nomes` = nomes já conhecidos da conversa (marcados pelo chamador); acento e caixa não importam."""
    if not isinstance(texto, str):
        raise TypeError("mascarar espera str")
    texto = _EMAIL.sub(EMAIL, texto)
    texto = _UUID.sub(UUID, texto)
    texto = _CPF_FORMATADO.sub(CPF, texto)
    texto = _ONZE_DIGITOS.sub(_trocar_cpf, texto)
    texto = _CEP_COM_ROTULO.sub(lambda m: m.group(1) + CEP, texto)
    texto = _CEP_FORMATADO.sub(CEP, texto)
    texto = _TELEFONE.sub(TELEFONE, texto)
    texto = _NUMERO_LONGO.sub(NUMERO, texto)
    return _mascarar_nomes(texto, nomes)
