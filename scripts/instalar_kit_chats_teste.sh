#!/usr/bin/env bash
# instalar_kit_chats_teste.sh — gera a CÓPIA de kits/chats-teste.sh que mora em ~/retomada-2809 (B2.4, R2-12c).
#
#   bash scripts/instalar_kit_chats_teste.sh [DESTINO]              escreve a cópia (0755)
#   bash scripts/instalar_kit_chats_teste.sh --verificar [DESTINO]  sai 1 se a cópia existente difere da fonte
#
# DESTINO padrão: $KIT_RETOMADA ou ~/retomada-2809/fila-2910/ia/config/chats-teste.sh. A cópia é a fonte + UMA linha de cabeçalho (a 2ª); a fonte e os testes
# moram no repositório. Quem edita o kit roda este script (o teste tests/test_kit_chats_teste.py reprova se a cópia desta máquina divergir).
set -euo pipefail
cd "$(dirname "$0")/.."
VERIFICAR=0
[ "${1:-}" = "--verificar" ] && { VERIFICAR=1; shift; }
DESTINO="${1:-${KIT_RETOMADA:-$HOME/retomada-2809/fila-2910/ia/config/chats-teste.sh}}"
gerar() {
  head -1 kits/chats-teste.sh
  echo "# CÓPIA de kits/chats-teste.sh do repositório ia-atendimento (branch feat/b2-4-pessoas-teste): a FONTE e os testes (tests/test_kit_chats_teste.py) moram lá."
  tail -n +2 kits/chats-teste.sh
}
if [ "$VERIFICAR" = 1 ]; then
  [ -f "$DESTINO" ] || { echo "!! $DESTINO não existe" >&2; exit 1; }
  gerar | cmp -s - "$DESTINO" || { echo "!! $DESTINO difere de kits/chats-teste.sh: rode bash scripts/instalar_kit_chats_teste.sh" >&2; exit 1; }
  echo "cópia em dia: $DESTINO"
else
  mkdir -p "$(dirname "$DESTINO")"
  gerar > "$DESTINO"
  chmod 755 "$DESTINO"
  echo "cópia escrita: $DESTINO"
fi
