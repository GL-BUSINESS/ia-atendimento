#!/usr/bin/env python3
"""Varredura dos arquivos versionados: segredo, CPF com DV válido e e-mail que não seja de teste. Sai 1 se achar algo.

Dado sintético permitido fica na lista abaixo (CPFs de exemplo conhecidos; e-mails `@exemplo.test`).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SEGREDOS = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16}|\bfw_[A-Za-z0-9]{24,}|\bgh[pousr]_[A-Za-z0-9]{30,}|\bsk-[A-Za-z0-9]{24,}"
    r"|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}|(?i:password|senha|secret|token)\s*[:=]\s*['\"][^'\"\s]{12,}['\"]"
)
CPF = re.compile(r"(?<![0-9])([0-9]{3})\.?([0-9]{3})\.?([0-9]{3})-?([0-9]{2})(?![0-9])")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})")
DOMINIOS_DE_TESTE = {"exemplo.test", "x.com", "sub.exemplo.com.br", "exemplo.com", "users.noreply.github.com"}
CPFS_SINTETICOS = {"52998224725", "00000000000", "12345678909", "11144477735"}
IGNORAR = {"uv.lock"}


def _cpf_valido(onze: str) -> bool:
    if len(set(onze)) == 1:
        return False
    for n in (9, 10):
        soma = sum(int(d) * p for d, p in zip(onze[:n], range(n + 1, 1, -1), strict=True))
        if (soma * 10) % 11 % 10 != int(onze[n]):
            return False
    return True


def varrer(arquivo: Path) -> list[str]:
    try:
        texto = arquivo.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    achados = []
    for numero, linha in enumerate(texto.splitlines(), start=1):
        if SEGREDOS.search(linha) and "exemplo" not in linha and "descartavel" not in linha:
            achados.append(f"{arquivo.relative_to(RAIZ)}:{numero}: parece segredo")
        for m in CPF.finditer(linha):
            onze = "".join(m.groups())
            if onze not in CPFS_SINTETICOS and _cpf_valido(onze):
                achados.append(f"{arquivo.relative_to(RAIZ)}:{numero}: CPF com DV válido fora da lista sintética")
        for m in EMAIL.finditer(linha):
            if m.group(1).lower() not in DOMINIOS_DE_TESTE:
                achados.append(f"{arquivo.relative_to(RAIZ)}:{numero}: e-mail de domínio real ({m.group(1)})")
    return achados


def main() -> int:
    arquivos = subprocess.run(["git", "ls-files", "-z"], cwd=RAIZ, check=True, capture_output=True, text=True).stdout.split("\0")
    achados = [a for nome in arquivos if nome and nome not in IGNORAR and (RAIZ / nome).is_file() for a in varrer(RAIZ / nome)]
    for a in achados:
        print(a, file=sys.stderr)
    if achados:
        print(f"varredura: {len(achados)} achado(s)", file=sys.stderr)
        return 1
    print("varredura: limpa")
    return 0


if __name__ == "__main__":
    sys.exit(main())
