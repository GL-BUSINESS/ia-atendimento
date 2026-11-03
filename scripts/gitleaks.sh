#!/usr/bin/env bash
# gitleaks ESTRITO (RG-119, PD-6): árvore de trabalho e histórico da branch atual. Sem o binário FALHA, não pula: o portão não pode dizer OK sem ter varrido.
# Config: .gitleaks.toml e .gitleaksignore. Variável: GITLEAKS_BIN (padrão: gitleaks).
# Binário: release oficial 8.30.1, gitleaks_8.30.1_linux_x64.tar.gz, sha256 551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb, em ~/bin.
set -uo pipefail
cd "$(dirname "$0")/.."

BIN="${GITLEAKS_BIN:-gitleaks}"
if ! command -v "$BIN" >/dev/null 2>&1; then
  echo "!! gitleaks não instalado ('$BIN'): o portão falha em vez de pular." >&2
  echo "   instalar a 8.30.1 de https://github.com/gitleaks/gitleaks/releases, conferir o sha256 (cabeçalho de scripts/gitleaks.sh) e pôr no PATH, ou definir GITLEAKS_BIN." >&2
  exit 1
fi

OPCOES=(--config .gitleaks.toml --redact --no-banner --exit-code 1)
status=0
"$BIN" dir "${OPCOES[@]}" . || status=1
if [ -d .git ] || [ -f .git ]; then
  # Só o histórico de HEAD: sem isto o gitleaks usa `--all` e o resultado dependeria das outras branches deste checkout.
  "$BIN" git "${OPCOES[@]}" --log-opts=HEAD . || status=1
fi
exit "$status"
