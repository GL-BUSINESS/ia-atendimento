#!/usr/bin/env python3
"""Regrava `tests/corpus/duble_personas.json` a partir do `personas/personas.yaml` do bancos-duble (só ids, n, CPF sintético, cenário, P-ids e `clone_de`).

Uso (o PyYAML não é dependência do projeto):
  uv run --with pyyaml python scripts/atualizar_duble.py ~/repos/bancos-duble/personas/personas.yaml <rotulo, ex.: B2.4> [--verificar]

`--verificar` não grava: sai 1 se o arquivo do corpus difere do que o dublê tem hoje. A `fonte` leva o sha256 do conteúdo do `personas.yaml`; o `check.sh` do
`bancos-duble` (que tem PyYAML) confere o instantâneo contra o `personas.yaml` dele num teste, então ele não pode ficar velho em silêncio (R2-08). Depois de regravar, rode `python -m ia_atendimento.corpus`:
persona do corpus que deixou de casar com o dublê aparece como violação `cpf_alinhado_duble`.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml

ALVO = Path(__file__).resolve().parent.parent / "tests" / "corpus" / "duble_personas.json"


def _persona(p: dict) -> dict:
    """Só o que liga a persona do corpus à do dublê; `clone_de` aparece só nos clones (B2.4, R1-09: uma persona do dublê por persona da F3)."""
    base = {"id": p["id"], "n": p["n"], "cpf": p["cpf"], "cenario": p["cenario"], "f3": p.get("f3") or []}
    return {**base, "clone_de": p["clone_de"]} if p.get("clone_de") else base


def gerar(yaml_path: Path, rotulo: str) -> dict:
    """O instantâneo. A `fonte` leva o sha256 do CONTEÚDO do `personas.yaml` (não um «commit»): é ele que o `bancos-duble` confere no portão dele (R2-08)."""
    bruto = yaml_path.read_bytes()
    d = yaml.safe_load(bruto)
    sha = hashlib.sha256(bruto).hexdigest()[:12]
    return {
        "fonte": f"bancos-duble {rotulo} personas/personas.yaml (sha256 {sha}, versao {d['versao']}): so id, n, CPF sintetico, cenario, as P-ids do f3 e o clone_de",
        "f3_globais": d["f3_globais"],
        "f3_sem_facta": d["f3_sem_facta"],
        "personas": [_persona(p) for p in d["personas"]],
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
