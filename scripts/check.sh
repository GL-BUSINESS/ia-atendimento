#!/usr/bin/env bash
# Portão local (o CI do GitHub pode estar parado por cobrança): lock coerente, lint, varredura, checksum da 0001, 0002 em dia, pessoas_teste e
# fixtures/duble em dia com o corpus e testes com tempo medido.
# Uso: bash scripts/check.sh        (precisa de docker com a imagem postgres:18, ou IA_TESTE_PG_HOST/IA_TESTE_PG_PORT)
set -euo pipefail
cd "$(dirname "$0")/.."
run() { echo "== $*"; "$@"; }
run uv lock --check
run uv run ruff check .
run uv run ruff format --check .
run uv run python scripts/varredura.py
(cd migrations && run sha256sum -c 0001.sha256)
run uv run python scripts/gerar_0002.py --verificar
run uv run python scripts/gerar_pessoas_teste.py --verificar
inicio=$(date +%s)
run timeout 600 uv run pytest -q
echo "== testes em $(( $(date +%s) - inicio )) s; portão local OK"
