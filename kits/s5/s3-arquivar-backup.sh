#!/usr/bin/env bash
# s3-arquivar-backup.sh — roda NA S3, como ROOT (não na S5). Tira os backups da S5 do diretório que a chave do rrsync alcança e os
# guarda num arquivo morto que a S5 não alcança, imutável. Assim uma S5 comprometida não apaga nem troca o que já chegou
# (a chave já é `rrsync -wo -no-del -no-overwrite`; isto é a segunda barreira).
#
# Para cada X.age que tem X.age.sha256 ao lado e cujo sha256 confere: move os dois para ${ARQUIVO}/AAAA-MM/ (root 0700), arquivos 0400
# root e `chattr +i` (se o sistema de arquivos não suportar, fica só root 0400 e o log diz). Arquivo que não confere fica onde está
# (pode estar chegando) e, se tiver mais de 2 h, vai para ${ARQUIVO}/suspeitos/ e sai com código 1 (o timer alerta).
#
# Uso:  sudo bash s3-arquivar-backup.sh [--aplicar] [--entrada DIR] [--arquivo DIR]
#   padrão: --entrada /mnt/hdd/backups/ia-s5  --arquivo /mnt/hdd/backups/ia-s5-arquivo ; sem --aplicar só lista o que faria.
# Timer sugerido (o dono instala na S3):
#   /etc/systemd/system/ia-s5-arquivar.service: [Service] Type=oneshot / ExecStart=/usr/local/sbin/s3-arquivar-backup.sh --aplicar
#   /etc/systemd/system/ia-s5-arquivar.timer:   [Timer] OnCalendar=*:0/15 / Persistent=true / [Install] WantedBy=timers.target
# Retenção do arquivo morto: decisão do dono (apagar exige `chattr -i`, de propósito).
set -euo pipefail
umask 077
APLICAR=0; ENTRADA=/mnt/hdd/backups/ia-s5; ARQUIVO=/mnt/hdd/backups/ia-s5-arquivo
while [ "$#" -gt 0 ]; do
  case "$1" in
    --aplicar) APLICAR=1 ;;
    --entrada) shift; ENTRADA="${1:?}" ;;
    --arquivo) shift; ARQUIVO="${1:?}" ;;
    *) echo "argumento desconhecido: $1" >&2; exit 2 ;;
  esac
  shift
done
[ "$(id -u)" = 0 ] || { echo "rode como root na S3" >&2; exit 2; }
[ -d "$ENTRADA" ] || { echo "entrada ausente: $ENTRADA" >&2; exit 2; }
case "$ARQUIVO/" in "$ENTRADA"/*) echo "o arquivo morto não pode ficar dentro da entrada do rrsync" >&2; exit 2 ;; esac
log() { logger -t ia-s5-arquivar "$*" 2>/dev/null || true; echo "$*"; }
suspeito=0
[ "$APLICAR" = 1 ] && install -d -m 700 -o root -g root "$ARQUIVO" "$ARQUIVO/suspeitos"

while IFS= read -r -d '' arq; do
  base="$(basename "$arq")"
  [[ "$base" =~ ^(ia_[a-z_]+|globais)-[0-9]{8}T[0-9]{6}Z\.(dump|sql)\.age$ ]] || { log "nome fora do padrão, ignorado: $base"; continue; }
  soma="$arq.sha256"
  if [ -f "$soma" ] && [ "$(cut -d' ' -f1 <"$soma")" = "$(sha256sum "$arq" | cut -d' ' -f1)" ]; then
    mes="$(sed -E 's/.*-([0-9]{4})([0-9]{2})[0-9]{2}T.*/\1-\2/' <<<"$base")"; destino="$ARQUIVO/$mes"
    if [ "$APLICAR" = 0 ]; then log "[simular] arquivaria $base em $destino"; continue; fi
    install -d -m 700 -o root -g root "$destino"
    [ ! -e "$destino/$base" ] || { log "já arquivado (não sobrescrevo): $base"; mv -n "$arq" "$soma" "$ARQUIVO/suspeitos/" 2>/dev/null || true; suspeito=1; continue; }
    mv -n "$soma" "$destino/$base.sha256"; mv -n "$arq" "$destino/$base"
    chown root:root "$destino/$base" "$destino/$base.sha256"; chmod 0400 "$destino/$base" "$destino/$base.sha256"
    if chattr +i "$destino/$base" "$destino/$base.sha256" 2>/dev/null; then log "arquivado e imutável: $base"
    else log "arquivado (root 0400; chattr não suportado aqui): $base"; fi
  elif [ -n "$(find "$arq" -mmin +120)" ]; then
    log "sha256 ausente ou divergente há mais de 2 h: $base"
    [ "$APLICAR" = 1 ] && mv -n "$arq" "$ARQUIVO/suspeitos/" && { [ ! -f "$soma" ] || mv -n "$soma" "$ARQUIVO/suspeitos/"; }
    suspeito=1
  fi
done < <(find "$ENTRADA" -maxdepth 1 -type f -name '*.age' -print0)
exit "$suspeito"
