#!/usr/bin/env python3
"""Portão do histórico do catálogo de ferramentas (revisão B5.1, M-5): as linhas de `catalogo_versoes.json` na base (padrão `origin/main`)
continuam idênticas no checkout; só se acrescenta `numero` novo no fim. Sem o arquivo na base (antes da B5.1 entrar), passa.

Uso: uv run python scripts/conferir_catalogo.py [--base origin/main] [--raiz <checkout>]   (ou CATALOGO_BASE_REF=<ref>)
A base precisa existir: ref ausente FALHA (portão estrito), não pula.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from ia_atendimento.ferramentas.catalogo import CatalogoSemVersao, conferir_historico, ler_versoes

CAMINHO: str = "src/ia_atendimento/ferramentas/catalogo_versoes.json"


def _git(raiz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(raiz), *args], capture_output=True, text=True, check=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default=os.environ.get("CATALOGO_BASE_REF", "origin/main"))
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parent.parent)
    opcoes = parser.parse_args(argv)
    if _git(opcoes.raiz, "rev-parse", "--verify", "--quiet", f"{opcoes.base}^{{commit}}").returncode != 0:
        print(f"catálogo: a base {opcoes.base} não existe neste checkout (git fetch origin, ou CATALOGO_BASE_REF)", file=sys.stderr)
        return 1
    na_base = _git(opcoes.raiz, "show", f"{opcoes.base}:{CAMINHO}")
    atual = ler_versoes((opcoes.raiz / CAMINHO).read_text(encoding="utf-8"))
    if na_base.returncode != 0:
        print(f"catálogo: {CAMINHO} ainda não existe em {opcoes.base}; {len(atual)} numero(s) no checkout")
        return 0
    try:
        conferir_historico(ler_versoes(na_base.stdout), atual)
    except CatalogoSemVersao as erro:
        print(f"catálogo: {erro}", file=sys.stderr)
        return 1
    print(f"catálogo: histórico em dia com {opcoes.base} ({len(atual)} numero(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
