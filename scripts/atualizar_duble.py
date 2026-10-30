#!/usr/bin/env python3
"""Regrava `tests/corpus/duble_personas.json` a partir do `personas/personas.yaml` do bancos-duble (só ids, n, CPF sintético, cenário, P-ids).

Uso (o PyYAML não é dependência do projeto):
  uv run --with pyyaml python scripts/atualizar_duble.py ~/repos/bancos-duble/personas/personas.yaml <hash-do-commit-lido> [--verificar]

`--verificar` não grava: sai 1 se o arquivo do corpus difere do que o dublê tem hoje. Depois de regravar, rode `python -m ia_atendimento.corpus`:
persona do corpus que deixou de casar com o dublê aparece como violação `cpf_alinhado_duble`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ALVO = Path(__file__).resolve().parent.parent / "tests" / "corpus" / "duble_personas.json"


def gerar(yaml_path: Path, commit: str) -> dict:
    d = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    return {
        "fonte": f"bancos-duble origin/main @{commit} personas/personas.yaml (versao {d['versao']}): so id, n, CPF sintetico, cenario e as P-ids do f3",
        "f3_globais": d["f3_globais"],
        "f3_sem_facta": d["f3_sem_facta"],
        "personas": [
            {"id": p["id"], "n": p["n"], "cpf": p["cpf"], "cenario": p["cenario"], "f3": p.get("f3") or []} for p in d["personas"]
        ],
    }


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 2
    novo = json.dumps(gerar(Path(args[0]).expanduser(), args[1]), ensure_ascii=False, indent=1) + "\n"
    if "--verificar" in argv:
        igual = ALVO.read_text(encoding="utf-8") == novo
        print("duble_personas.json em dia" if igual else "duble_personas.json DIFERE do bancos-duble")
        return 0 if igual else 1
    ALVO.write_text(novo, encoding="utf-8")
    print(f"gravado {ALVO}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
