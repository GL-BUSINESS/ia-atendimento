"""`uv run python -m ia_atendimento.corpus [--semente]`."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ia_atendimento.corpus import carregar_bruto, derivar_semente, montar, validar


def main(argv: Sequence[str] = ()) -> int:
    """Valida o corpus de `tests/corpus` (relativo ao diretório atual; `--raiz DIR` troca). Com `--semente` imprime a semente derivada."""
    raiz = Path(argv[argv.index("--raiz") + 1]) if "--raiz" in argv else Path("tests/corpus")
    bruto = carregar_bruto(raiz)
    if "--semente" in argv:
        corpus = montar(bruto)
        derivada = derivar_semente(corpus.personas, corpus.semente.semente_global, [p.id for p in corpus.personas_m])
        print(json.dumps(derivada, ensure_ascii=False, indent=1))
        return 0
    violacoes = validar(bruto)
    for v in violacoes:
        print(v)
    print(f"corpus: {len(violacoes)} violação(ões)")
    return 1 if violacoes else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
