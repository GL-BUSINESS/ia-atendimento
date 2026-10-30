"""Máscara determinística de PII para o texto que vai à `conversa_cifrada` (`mascarado = true`; roteiro B1.2).

Entra texto do cliente; sai texto com marcadores fixos (`[CPF]`, `[TELEFONE]`, `[EMAIL]`, `[CEP]`, `[UUID]`, `[NUMERO]`,
`[NOME]`). Só regex e aritmética, sem modelo: mesma entrada, mesma saída, e `mascarar(mascarar(x)) == mascarar(x)`.
Excesso de máscara é aceito (melhor mascarar demais que vazar); falta de máscara não.

Como casa (resistente a separadores): os padrões olham uma VISTA do texto em que todo dígito Unicode (largura total,
árabe-índico...) virou ASCII, com o mesmo comprimento; as trocas valem no texto original pelas posições. Uma "corrente de
dígitos" é uma sequência de dígitos com até 6 não-alfanuméricos entre dois dígitos (espaço, ponto, vírgula, barra, hífen,
sublinhado, parênteses, quebra de linha). Cada corrente é classificada pelos dígitos, sem olhar os separadores:
1º CPF (11 dígitos com DV válido, ou a forma `000.000.000-00`), CEP ou telefone BR: SEMPRE mascarado, nada o isenta;
2º `[NUMERO]` se sobrar com 8+ dígitos, salvo isenção. Corrente com menos de 8 dígitos fica (valor, prazo, proposta).
Isenções (só para o que sobraria como `[NUMERO]`): data `dd/mm/aaaa` e valor `R$ 1.234,56` (centavos obrigatórios, até 3 grupos
de milhar e 11 dígitos). A isenção só vale se a corrente inteira está dentro do trecho isento; se a corrente entra ou sai dele
(`R$ 11 91234-5678`, `29/10/2026 11912345678`), a isenção cai e a corrente inteira é mascarada.

Ordem: e-mail, UUID, correntes de dígitos e, por último, nomes marcados pelo chamador.
Limite conhecido (fora de escopo): dígitos por extenso ("cinco dois nove...") e dígitos misturados com letras não são mascarados.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable

CPF, TELEFONE, EMAIL, CEP, UUID, NUMERO, NOME = (f"[{r}]" for r in ("CPF", "TELEFONE", "EMAIL", "CEP", "UUID", "NUMERO", "NOME"))

MIN_DIGITOS = 8
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
_UUID = re.compile(r"(?<![0-9A-Za-z])[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?![0-9A-Za-z])")
# Isenções do [NUMERO] (data e dinheiro têm 8+ dígitos): data com ano 19xx/20xx e valor em reais com centavos, até 3 grupos de milhar.
_ISENTO = re.compile(
    r"(?<![0-9])(?:0?[1-9]|[12][0-9]|3[01])([/.\-])(?:0?[1-9]|1[0-2])\1(?:19|20)[0-9]{2}(?![0-9])"
    r"|R\$\s*[0-9]{1,3}(?:\.[0-9]{3}){0,3},[0-9]{2}(?![0-9])"
)
MAX_DIGITOS_DINHEIRO = 11
_CORRENTE = re.compile(r"[+(]?[0-9](?:[\W_]{0,6}[0-9])*")
_CPF_FORMATADO = re.compile(r"[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}")
_CEP_FORMATADO = re.compile(r"[0-9]{5}-[0-9]{3}")
_CEP_ROTULO = re.compile(r"\bcep\b[\s:.\-]*$", re.IGNORECASE)
_TELEFONE_CURTO = re.compile(r"9[0-9]{4}-[0-9]{4}|[2-5][0-9]{3}-[0-9]{4}")  # sem DDD só com o hífen no lugar
_TELEFONE_DIGITOS = re.compile(r"(?:55)?[0-9]{2}(?:9[0-9]{8}|[2-5][0-9]{7})")
_MARCADORES = re.compile(r"\[(?:CPF|TELEFONE|EMAIL|CEP|UUID|NUMERO|NOME)\]")
_PARTICULAS = frozenset({"da", "de", "do", "das", "dos", "di", "du", "del", "van", "von", "der", "las", "los"})
_TAMANHO_MIN_PARTE = 3

Troca = tuple[int, int, str]


def _cpf_valido(onze: str) -> bool:
    if len(onze) != 11 or len(set(onze)) == 1:
        return False
    for tamanho in (9, 10):
        soma = sum(int(d) * p for d, p in zip(onze[:tamanho], range(tamanho + 1, 1, -1), strict=True))
        if (soma * 10) % 11 % 10 != int(onze[tamanho]):
            return False
    return True


def _vista_ascii(texto: str) -> str:
    """Todo dígito Unicode vira ASCII; os demais caracteres ficam. SEMPRE o mesmo comprimento do original."""
    return "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in texto)


def _aplicar(texto: str, trocas: list[Troca]) -> str:
    saida: list[str] = []
    cursor = 0
    for inicio, fim, novo in sorted(trocas):
        saida.append(texto[cursor:inicio])
        saida.append(novo)
        cursor = fim
    saida.append(texto[cursor:])
    return "".join(saida)


def _mascarar_padrao(texto: str, padrao: re.Pattern[str], marcador: str) -> str:
    return _aplicar(texto, [(m.start(), m.end(), marcador) for m in padrao.finditer(_vista_ascii(texto))])


def _classe_forte(trecho: str, antes: str) -> str | None:
    """CPF, CEP ou telefone pelos dígitos (não pelos separadores); `None` se for só um número."""
    digitos = re.sub(r"[^0-9]", "", trecho)
    limpo = trecho.strip("+() ")
    if _CPF_FORMATADO.fullmatch(limpo) or _cpf_valido(digitos):
        return CPF
    if _CEP_FORMATADO.fullmatch(limpo) or (len(digitos) == 8 and _CEP_ROTULO.search(antes)):
        return CEP
    if _TELEFONE_DIGITOS.fullmatch(digitos) or _TELEFONE_CURTO.fullmatch(limpo):
        return TELEFONE
    return None


def _trechos_isentos(vista: str) -> list[tuple[int, int]]:
    isentos = []
    for achado in _ISENTO.finditer(vista):
        dinheiro = achado.group().startswith("R$")
        if dinheiro and sum(c.isdigit() for c in achado.group()) > MAX_DIGITOS_DINHEIRO:
            continue
        isentos.append(achado.span())
    return isentos


def _trocas_de_digitos(vista: str) -> list[Troca]:
    isentos = _trechos_isentos(vista)
    trocas: list[Troca] = []
    for achado in _CORRENTE.finditer(vista):
        trecho, inicio, fim = achado.group(), achado.start(), achado.end()
        if sum(c.isdigit() for c in trecho) < MIN_DIGITOS:
            continue
        rotulo = _classe_forte(trecho, vista[:inicio])
        if rotulo is None:
            primeiro_digito = inicio + next(i for i, c in enumerate(trecho) if c.isdigit())
            if any(a <= primeiro_digito and fim <= b for a, b in isentos):
                continue  # a corrente inteira é uma data ou um valor em reais
            rotulo = NUMERO
        trocas.append((inicio, fim, rotulo))
    return trocas


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
    trocas: list[Troca] = [
        (inicio, fim, NOME)
        for inicio, fim in (m.span() for m in padrao.finditer(dobrado))
        if not any(inicio < pf and fim > pi for pi, pf in protegidos)  # não mexe dentro de [CPF], [EMAIL]...
    ]
    return _aplicar(texto, trocas)


def _etapa_digitos(texto: str) -> str:
    return _aplicar(texto, _trocas_de_digitos(_vista_ascii(texto)))


def mascarar(texto: str, nomes: Iterable[str] = ()) -> str:
    """Troca PII por marcadores. `nomes` = nomes já conhecidos da conversa (marcados pelo chamador); acento e caixa não importam."""
    if not isinstance(texto, str):
        raise TypeError("mascarar espera str")
    etapas: list[Callable[[str], str]] = [
        lambda t: _mascarar_padrao(t, _EMAIL, EMAIL),
        lambda t: _mascarar_padrao(t, _UUID, UUID),
        _etapa_digitos,
    ]
    for etapa in etapas:
        texto = etapa(texto)
    return _mascarar_nomes(texto, nomes)
