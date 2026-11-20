#!/usr/bin/env bash
# 80-backup.sh — backup lógico CIFRADO dos bancos da IA na S5 para o HDD da S3, com FILA LOCAL e alerta (só BANCO_LOCAL=s5;
# com o banco na S4, o backup é o da S4 e este passo só avisa).
#
# Desenho (DEC-PIA-009; a S3 ficou ~16 h fora em 15–16/11):
#   ia-s5-backup (diário, 06:30 UTC = 03:30 BRT): pg_dump -Fc de cada banco de BACKUP_BANCOS → age (chave PÚBLICA; a privada fica com o
#     dono, fora da S5 e da S3) → ${BACKUP_FILA_DIR}/fila/. O arquivo só aparece na fila completo (.parcial → mv atômico).
#   ia-s5-backup-enviar (de hora em hora): rsync de cada arquivo da fila para BACKUP_DESTINO:BACKUP_DESTINO_DIR com chave ssh própria
#     (no destino, restrita pelo `s3-rrsync-backup` (rrsync -wo -no-del, --ignore-existing obrigatório): só grava arquivo NOVO; não lê, não apaga, não sobrescreve). Na S3 um job
#     de root (s3-arquivar-backup.sh) tira cada arquivo recebido e conferido para um arquivo morto fora do alcance da chave e o torna
#     imutável: uma S5 comprometida não apaga o que já chegou. Sucesso ⇒ vai para enviados/ (guardado
#     BACKUP_RETENCAO_LOCAL_DIAS). Falha ⇒ fica na fila; se o mais velho passar de BACKUP_FILA_MAX_HORAS, alerta (ntfy, sem PII).
#   O `ia_obs` (Phoenix, texto de conversa) fica FORA por padrão, como na S4 (A §4); a chave AES mensal NUNCA vai no backup (P-R10).
#
# Uso:  sudo bash 80-backup.sh [--aplicar]
# Desfazer: systemctl disable --now ia-s5-backup.timer ia-s5-backup-enviar.timer; apagar as unidades e /usr/local/sbin/ia-s5-backup*.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
ler_args "$@"
carregar_env
exigir BANCO_LOCAL
validar_banco_local
exigir_root
if [ "$BANCO_LOCAL" = s4 ]; then
  titulo "backup"; info "BANCO_LOCAL=s4: os bancos da IA estão na S4 (pgBackRest/dump da S4, A4.8). Nada a fazer na S5."; resumo_ok; exit 0
fi
exigir BACKUP_DESTINO BACKUP_DESTINO_DIR BACKUP_AGE_DESTINATARIO BACKUP_BANCOS BACKUP_RETENCAO_LOCAL_DIAS BACKUP_FILA_MAX_HORAS BACKUP_FILA_DIR PG_PORTA
[[ "$BACKUP_AGE_DESTINATARIO" =~ ^age1[0-9a-z]{58}$ ]] || falhar "BACKUP_AGE_DESTINATARIO deve ser uma chave PÚBLICA age (age1…)"
[[ "$BACKUP_DESTINO" =~ ^[a-z_][a-z0-9_-]*@[A-Za-z0-9.-]+$ ]] || falhar "BACKUP_DESTINO deve ser usuario@host"
[[ "$BACKUP_DESTINO_DIR" =~ ^/[A-Za-z0-9_./-]+$ ]] || falhar "BACKUP_DESTINO_DIR: caminho absoluto simples"
[[ "$BACKUP_FILA_DIR" =~ ^/[A-Za-z0-9_./-]+$ ]] || falhar "BACKUP_FILA_DIR: caminho absoluto simples"
for n in BACKUP_RETENCAO_LOCAL_DIAS BACKUP_FILA_MAX_HORAS PG_PORTA; do [[ "${!n}" =~ ^[0-9]+$ ]] || falhar "$n numérico"; done
for b in $BACKUP_BANCOS; do [[ "$b" =~ ^ia_[a-z_]+$ ]] || falhar "BACKUP_BANCOS: '$b' fora de ia_*"; done
ADM=/etc/ia-s5-adm
CHAVE_SSH="$ADM/backup_ed25519"

titulo "1. pacotes e diretórios da fila (root 0700)"
apt_instalar age rsync openssh-client
rodar install -d -m 700 "$BACKUP_FILA_DIR" "$BACKUP_FILA_DIR/fila" "$BACKUP_FILA_DIR/enviados"

titulo "2. chave ssh só do backup (a PÚBLICA vai para a S3 presa ao s3-rrsync-backup)"
if aplicando; then
  [ -s "$CHAVE_SSH" ] || ssh-keygen -q -t ed25519 -N '' -C "ia-s5-backup" -f "$CHAVE_SSH"
  chmod 600 "$CHAVE_SSH"
  info "linha para o authorized_keys do usuário de destino na S3 (o DONO cola lá; só grava em ${BACKUP_DESTINO_DIR}):"
  printf '   from="<IP da S5 no tailnet>",restrict,command="/usr/local/bin/s3-rrsync-backup %s" %s\n' "$BACKUP_DESTINO_DIR" "$(cat "$CHAVE_SSH.pub")"
  info "(troque <IP da S5 no tailnet> pelo IP 100.x da S5: a chave só vale vindo dela)"
else info "[simular] ssh-keygen -t ed25519 -f $CHAVE_SSH (sem senha, 0600) e mostraria a linha restrict,command=\"s3-rrsync-backup …\""; fi

titulo "3. /etc/ia-s5-adm/backup.conf (lido pelos scripts; não secreto)"
escrever "$ADM/backup.conf" 600 root:root <<CONF
BANCOS="${BACKUP_BANCOS}"
PG_PORTA=${PG_PORTA}
FILA=${BACKUP_FILA_DIR}
DESTINO=${BACKUP_DESTINO}
DESTINO_DIR=${BACKUP_DESTINO_DIR}
AGE_DESTINATARIO=${BACKUP_AGE_DESTINATARIO}
RETENCAO_DIAS=${BACKUP_RETENCAO_LOCAL_DIAS}
FILA_MAX_HORAS=${BACKUP_FILA_MAX_HORAS}
CHAVE_SSH=${CHAVE_SSH}
CONF

titulo "4. /usr/local/sbin/ia-s5-backup (dump → age → fila)"
escrever /usr/local/sbin/ia-s5-backup 755 root:root <<'SCRIPT'
#!/usr/bin/env bash
# ia-s5-backup — pg_dump -Fc cifrado com age para a fila local (kit s5, 80-backup.sh). Nunca grava dump em claro no disco.
set -euo pipefail
umask 077
. /etc/ia-s5-adm/backup.conf
exec 9>"$FILA/.lock"; flock -n 9 || { logger -t ia-s5-backup "outro backup rodando"; exit 0; }
livre=$(df --output=pcent "$FILA" | tail -1 | tr -dc '0-9'); livre=$((100 - ${livre:-100}))
[ "$livre" -ge 10 ] || { /usr/local/sbin/ia-alerta backup_sem_disco livre_pct="$livre" || true; exit 1; }
quando=$(date -u +%Y%m%dT%H%M%SZ)
for banco in $BANCOS; do
  final="$FILA/fila/${banco}-${quando}.dump.age"
  if ! sudo -n -u postgres pg_dump -p "$PG_PORTA" -Fc -d "$banco" | age -r "$AGE_DESTINATARIO" -o "$final.parcial"; then
    rm -f "$final.parcial"; /usr/local/sbin/ia-alerta backup_dump_falhou banco="$banco" || true; exit 1
  fi
  [ -s "$final.parcial" ] || { rm -f "$final.parcial"; /usr/local/sbin/ia-alerta backup_dump_vazio banco="$banco" || true; exit 1; }
  sha256sum "$final.parcial" | sed "s#\.parcial\$##; s#$FILA/fila/##" >"$final.sha256"
  mv "$final.parcial" "$final"
  logger -t ia-s5-backup "na fila: $(basename "$final") $(stat -c %s "$final") bytes"
done
# papéis sem senha (para restaurar num cluster novo); cifrado igual
sudo -n -u postgres pg_dumpall -p "$PG_PORTA" --globals-only --no-role-passwords | age -r "$AGE_DESTINATARIO" -o "$FILA/fila/globais-${quando}.sql.age.parcial"
sha256sum "$FILA/fila/globais-${quando}.sql.age.parcial" | sed "s#\.parcial\$##; s#$FILA/fila/##" >"$FILA/fila/globais-${quando}.sql.age.sha256"
mv "$FILA/fila/globais-${quando}.sql.age.parcial" "$FILA/fila/globais-${quando}.sql.age"
SCRIPT

titulo "5. /usr/local/sbin/ia-s5-backup-enviar (fila → S3; alerta se atrasar)"
escrever /usr/local/sbin/ia-s5-backup-enviar 755 root:root <<'SCRIPT'
#!/usr/bin/env bash
# ia-s5-backup-enviar — esvazia a fila para a S3 (kit s5, 80-backup.sh). Destino fora = a fila espera; atraso = alerta.
set -euo pipefail
umask 077
. /etc/ia-s5-adm/backup.conf
exec 9>"$FILA/.lock-envio"; flock -n 9 || exit 0
SSH="ssh -i $CHAVE_SSH -o BatchMode=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=yes"
enviados=0; falhou=0
while IFS= read -r arq; do
  base=$(basename "$arq")
  # o .sha256 vai junto; o arquivo principal por último (quem lê do outro lado vê o .sha256 primeiro)
  # --ignore-existing: a S3 (s3-rrsync-backup) recusa o envio sem ele; arquivo que já está lá não é reenviado nem trocado
  if rsync -t --ignore-existing --partial-dir=.parcial -e "$SSH" "$arq.sha256" "$arq" "$DESTINO:" 2>/dev/null; then
    mv "$arq" "$arq.sha256" "$FILA/enviados/"; enviados=$((enviados + 1)); logger -t ia-s5-backup "enviado $base"
  else falhou=1; logger -t ia-s5-backup "destino fora; $base fica na fila"; break; fi
done < <(find "$FILA/fila" -maxdepth 1 -type f -name '*.age' -printf '%T@ %p\n' | sort -n | cut -d' ' -f2-)
# retenção local só do que JÁ foi enviado; a fila nunca é apagada
find "$FILA/enviados" -maxdepth 1 -type f -mtime +"$RETENCAO_DIAS" -delete
pendentes=$(find "$FILA/fila" -maxdepth 1 -type f -name '*.age' | wc -l)
if [ "$pendentes" -gt 0 ]; then
  mais_velho=$(find "$FILA/fila" -maxdepth 1 -type f -name '*.age' -printf '%T@\n' | sort -n | head -1 | cut -d. -f1)
  horas=$(( ($(date +%s) - mais_velho) / 3600 ))
  if [ "$horas" -ge "$FILA_MAX_HORAS" ]; then /usr/local/sbin/ia-alerta backup_fila_atrasada horas="$horas" arquivos="$pendentes" || true; fi
fi
# backup diário que não aconteceu também é alerta (o mais novo, na fila ou enviado, com mais de 26 h)
ultimo=$(find "$FILA/fila" "$FILA/enviados" -maxdepth 1 -type f -name '*.dump.age' -printf '%T@\n' | sort -n | tail -1 | cut -d. -f1)
if [ -z "$ultimo" ] || [ $(( ($(date +%s) - ${ultimo:-0}) / 3600 )) -ge 26 ]; then /usr/local/sbin/ia-alerta backup_sem_dump_recente || true; fi
logger -t ia-s5-backup "envio: $enviados enviado(s), $pendentes na fila"
[ "$falhou" = 0 ] || exit 0   # destino fora não é falha da unidade: a fila e o alerta de atraso cuidam disso
SCRIPT

titulo "6. unidades systemd (OnFailure → ia-alerta)"
escrever /etc/systemd/system/ia-s5-backup.service 644 root:root <<'UNIT'
[Unit]
Description=kit s5: backup cifrado dos bancos da IA para a fila local
After=postgresql.service
OnFailure=ia-s5-alerta@%N.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/ia-s5-backup
Nice=10
IOSchedulingClass=idle
UNIT
escrever /etc/systemd/system/ia-s5-backup.timer 644 root:root <<'UNIT'
[Unit]
Description=kit s5: backup diário 06:30 UTC (03:30 BRT)

[Timer]
OnCalendar=*-*-* 06:30:00 UTC
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
UNIT
escrever /etc/systemd/system/ia-s5-backup-enviar.service 644 root:root <<'UNIT'
[Unit]
Description=kit s5: envia a fila de backup para a S3
Wants=network-online.target
After=network-online.target
OnFailure=ia-s5-alerta@%N.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/ia-s5-backup-enviar
UNIT
escrever /etc/systemd/system/ia-s5-backup-enviar.timer 644 root:root <<'UNIT'
[Unit]
Description=kit s5: envio da fila de backup de hora em hora

[Timer]
OnCalendar=hourly
Persistent=true
RandomizedDelaySec=120

[Install]
WantedBy=timers.target
UNIT
rodar systemctl daemon-reload
rodar systemctl enable --now ia-s5-backup.timer ia-s5-backup-enviar.timer

titulo "7. o que o DONO faz na S3 (não executado aqui)"
cat <<TXT
   - usuário de destino (ex.: ia-backup) sem shell útil, dono de ${BACKUP_DESTINO_DIR} (0700), com a linha restrict/rrsync do passo 2
     e o s3-rrsync-backup.sh deste kit em /usr/local/bin/s3-rrsync-backup (root 0755);
   - instalar na S3, como ROOT, o s3-arquivar-backup.sh deste kit num timer de 15 min (texto da unidade no cabeçalho dele): ele move
     o que chegou e confere o sha256 para ${BACKUP_DESTINO_DIR}-arquivo (root 0700) e aplica chattr +i;
   - na S5, uma vez, aceitar a chave do host da S3: sudo ssh -i ${CHAVE_SSH} ${BACKUP_DESTINO} (StrictHostKeyChecking=yes depois);
   - guardar a chave PRIVADA age fora da S5 e da S3; ensaiar a volta: age -d -i <privada> X.dump.age | pg_restore -d <banco descartável>.
TXT
resumo_ok
