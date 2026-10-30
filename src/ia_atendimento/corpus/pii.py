"""Dado pessoal no texto do corpus: só o sintético passa. Reusa a aritmética e as etapas de `mascara.py` (B1.2)."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from ia_atendimento import mascara

_MARCADOR_PARA_TIPO = {
    mascara.CPF: "cpf",
    mascara.TELEFONE: "telefone",
    mascara.EMAIL: "email",
    mascara.CEP: "cep",
    mascara.UUID: "uuid",
    mascara.NUMERO: "numero",
}
CELULARES_SINTETICOS = frozenset({"912345678", "987654321", "999999999", "900000000"})  # os mesmos de scripts/varredura.py
PLACEHOLDER = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)
MAX_DIGITOS_SIGNIFICATIVOS_DE_NUMERO = 6  # «0000123-4»: conta sintética = zeros à esquerda e poucos dígitos


def digitos(trecho: str) -> str:
    return "".join(str(int(c)) for c in trecho if c.isdigit())


def cpf_sintetico(onze: str) -> bool:
    """`000.000.0nn-dd` com os dois dígitos verificadores certos (a faixa que não existe em pessoa de verdade)."""
    return len(onze) == 11 and onze.startswith("0000000") and mascara._cpf_valido(onze)


def achados_pii(texto: str) -> list[tuple[str, str]]:
    """PII que a máscara de B1.2 enxerga no texto: lista de (tipo, valor). Mesma ordem de etapas de `mascara.mascarar`."""
    achados: list[tuple[str, str]] = []
    vista = mascara._vista_ascii(texto)
    trocas_email = mascara._trocas_de_email(vista)
    achados += [("email", vista[i:f]) for i, f, _ in trocas_email]
    texto = mascara._aplicar(texto, trocas_email)
    vista = mascara._vista_ascii(texto)
    achados += [("uuid", m.group().lower()) for m in mascara._UUID.finditer(vista)]
    texto = mascara._mascarar_padrao(texto, mascara._UUID, mascara.UUID)
    vista = mascara._vista_ascii(texto)
    achados += [(_MARCADOR_PARA_TIPO[marcador], vista[i:f]) for i, f, marcador in mascara._trocas_de_digitos(vista)]
    return achados


def pii_nao_sintetica(tipo: str, valor: str) -> bool:
    """True se o dado NÃO é do conjunto sintético permitido (então é, ou parece, dado de gente de verdade)."""
    d = digitos(valor)
    if tipo == "cpf":
        return not d.startswith("0000000")
    if tipo == "telefone":
        sem_pais = d[2:] if d.startswith("55") and len(d) > 11 else d
        return sem_pais[-9:] not in CELULARES_SINTETICOS
    if tipo == "email":
        return not valor.lower().endswith(".test")
    if tipo == "cep":
        return not d.startswith("00000")
    if tipo == "uuid":
        return not valor.startswith("00000000-")
    return not (d.startswith("0000") and len(d.lstrip("0")) <= MAX_DIGITOS_SIGNIFICATIVOS_DE_NUMERO)  # numero: chave/conta


def strings(objeto: Any, caminho: str = "") -> Iterator[tuple[str, str]]:
    """Todas as strings (caminho, valor) de um dump de modelo ou JSON, para as varreduras que valem em qualquer campo."""
    if isinstance(objeto, str):
        yield caminho, objeto
    elif isinstance(objeto, dict):
        for k, v in objeto.items():
            yield from strings(v, f"{caminho}.{k}" if caminho else str(k))
    elif isinstance(objeto, (list, tuple)):
        for i, v in enumerate(objeto):
            yield from strings(v, f"{caminho}[{i}]")
