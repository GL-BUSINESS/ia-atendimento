#!/bin/sh
# s3-rrsync-backup — fica NA S3 em /usr/local/bin (root 0755). É o `command=` da chave de backup da S5 no authorized_keys:
#   from="<IP da S5 no tailnet>",restrict,command="/usr/local/bin/s3-rrsync-backup /mnt/hdd/backups/ia-s5" ssh-ed25519 …
# Garante, do lado da S3, que a chave só GRAVA ARQUIVO NOVO: sem ler, sem apagar, sem sobrescrever, sem link.
#
# LISTA FECHADA: só aceita exatamente o comando de servidor que o `ia-s5-backup-enviar` gera
#   (`rsync -t --ignore-existing --partial-dir=.parcial …`):
#     rsync --server -te.<capacidades> [--partial-dir .parcial] --ignore-existing [--partial-dir .parcial] . .
#   Qualquer outra opção (--delete*, --remove*, --sender, --no-ignore-existing, --existing, -l/-L/-k/-K, opção depois do «.») é recusada.
#   O receptor é a S3: é ela que aplica o --ignore-existing, então a S5 não o contorna.
# Depois chama `rrsync -wo -no-del -munge` (e `-no-overwrite` quando a versão tem: rsync ≥ 3.3; o Ubuntu 24.04 traz 3.2.7 sem ela).
set -eu
dir="${1:?uso: s3-rrsync-backup DIR}"
cmd="${SSH_ORIGINAL_COMMAND:-}"
recusa() { echo "s3-rrsync-backup: recusado ($1)" >&2; logger -t s3-rrsync-backup "recusado: $1" 2>/dev/null || true; exit 1; }
# -te. seguido só das letras de capacidade do protocolo (maiúsculas/minúsculas, sem opção de transferência antes do «e.»)
padrao='^rsync --server -te\.[A-Za-z]+( --partial-dir[ =]\.parcial)? --ignore-existing( --partial-dir[ =]\.parcial)? \. \.$'
printf '%s\n' "$cmd" | grep -Eqx -- "$padrao" || recusa "comando fora da lista fechada"
[ "$(printf '%s' "$cmd" | wc -l)" = 0 ] || recusa "mais de uma linha"
extra=""
/usr/bin/rrsync -h 2>/dev/null | grep -q -- '-no-overwrite' && extra="-no-overwrite"
# shellcheck disable=SC2086
exec /usr/bin/rrsync -wo -no-del -munge $extra "$dir"
