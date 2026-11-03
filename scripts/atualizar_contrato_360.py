#!/usr/bin/env python3
"""Regrava `tests/contratos/cliente360-recorte.json`: os schemas do `cliente360.json` da `cliente360-api` de que as fixtures dependem (B2.4, R1-14/R2-06).

O teste de deriva (`tests/test_fixtures_duble.py`) compara os modelos de `pessoas_teste/formas.py` com ESTE recorte, que é versionado: roda sempre, em qualquer máquina,
e lê o contrato da API (a fonte), não o pin do `cliente360-web`. O recorte é o fecho (`$ref`) dos schemas abaixo. Se a API mudar um deles, o teste de frescor reprova
e este script regrava (e os modelos acompanham).

Uso: uv run python scripts/atualizar_contrato_360.py [--verificar] [REPO_DA_API] [REF]     (padrão: ~/repos/cliente360-api e origin/main)
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ALVO = Path(__file__).resolve().parent.parent / "tests" / "contratos" / "cliente360-recorte.json"
CAMINHO_NA_API = "src/c360api/contrato/cliente360.json"
RAIZES = (
    "Oferta", "PayloadEconomicoCltV1", "ParPropostasPessoa", "ResultadoPropostasPessoa", "PessoaResumo", "ResumosPessoas", "AtributosCadastraisOferta",
    "NaoPerturbe", "LimiteContratos", "ContratoNaFoto", "Contrato",
)  # fmt: skip


def _refs(objeto, achados: set[str]) -> None:
    if isinstance(objeto, dict):
        for chave, valor in objeto.items():
            if chave == "$ref" and isinstance(valor, str) and valor.startswith("#/components/schemas/"):
                achados.add(valor.rsplit("/", 1)[-1])
            else:
                _refs(valor, achados)
    elif isinstance(objeto, list):
        for valor in objeto:
            _refs(valor, achados)


def recorte(contrato_completo: dict, ref: str, bruto: bytes) -> dict:
    esquemas = contrato_completo["components"]["schemas"]
    vistos: set[str] = set()
    pendentes = list(RAIZES)
    while pendentes:
        nome = pendentes.pop()
        if nome in vistos:
            continue
        vistos.add(nome)
        achados: set[str] = set()
        _refs(esquemas[nome], achados)
        pendentes += sorted(achados - vistos)
    return {
        "fonte": f"cliente360-api@{ref} {CAMINHO_NA_API}",
        "sha256_do_contrato_completo": hashlib.sha256(bruto).hexdigest(),
        "raizes": list(RAIZES),
        "schemas": {nome: esquemas[nome] for nome in sorted(vistos)},
    }


def ler_da_api(repo: Path, ref: str) -> tuple[dict, bytes, str]:
    bruto = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{CAMINHO_NA_API}"], capture_output=True, check=True).stdout
    curto = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", ref], capture_output=True, text=True, check=True).stdout.strip()
    return json.loads(bruto), bruto, curto


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    repo = Path(args[0]).expanduser() if args else Path.home() / "repos" / "cliente360-api"
    ref = args[1] if len(args) > 1 else "origin/main"
    contrato, bruto, curto = ler_da_api(repo, ref)
    novo = json.dumps(recorte(contrato, curto, bruto), indent=1, ensure_ascii=False) + "\n"
    if "--verificar" in argv:
        atual = json.loads(ALVO.read_text(encoding="utf-8"))["schemas"]
        mesmo = atual == json.loads(novo)["schemas"]
        print(
            "recorte do contrato do 360 em dia"
            if mesmo
            else f"recorte DIFERE do cliente360-api@{curto} (rode scripts/atualizar_contrato_360.py)"
        )
        return 0 if mesmo else 1
    ALVO.write_text(novo, encoding="utf-8")
    print(f"gravado {ALVO.name} ({len(json.loads(novo)['schemas'])} schemas, cliente360-api@{curto})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
