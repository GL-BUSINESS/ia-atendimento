#!/usr/bin/env bash
# exigir_irmao.sh — o portão (check.sh) FALHA, em vez de pular, se o checkout do bancos-duble não estiver à vista (B2.4, R1-02).
#
# A consistência das 84 pessoas de teste entre o ia-atendimento e o bancos-duble só existe se os dois repositórios são comparados; sem a variável o
# teste cruzado é skip e o portão imprimia «OK» mesmo com o CPF de uma persona mudado num lado só (revisão 1, mutação M2).
# Uso: BANCOS_DUBLE_PATH=~/repos/bancos-duble bash scripts/exigir_irmao.sh      (sai 0 se achar; 1 com a mensagem do que fazer)
set -euo pipefail
ARQUIVO="personas/pessoas_teste.sha256"
if [ -z "${BANCOS_DUBLE_PATH:-}" ]; then
  echo "!! BANCOS_DUBLE_PATH não está definida. O portão compara este repositório com o bancos-duble (B2.4):" >&2
  echo "   BANCOS_DUBLE_PATH=<checkout do bancos-duble com a B2.4> bash scripts/check.sh" >&2
  exit 1
fi
RAIZ="${BANCOS_DUBLE_PATH/#\~/$HOME}"
if [ ! -f "$RAIZ/$ARQUIVO" ]; then
  echo "!! $RAIZ/$ARQUIVO não existe: BANCOS_DUBLE_PATH aponta para um checkout sem a B2.4 (ou para o lugar errado)." >&2
  exit 1
fi
echo "irmão achado: $RAIZ"
