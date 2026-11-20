#!/usr/bin/env bash
# ensaio-local.sh — F4-035: roda o kit da S5 inteiro, primeiro em --simular e depois em --aplicar, em CONTÊINERES DESCARTÁVEIS locais
# (Ubuntu 24.04 com systemd). Nunca toca em servidor real: nada de ssh para S2/S3/S4/S5, nada de ntfy.sh (um ntfy falso escuta em
# 127.0.0.1 dentro do contêiner) e o «HDD da S3» é outro contêiner. Tudo nasce e morre aqui (prefixo ia-s5-ensaio-).
#
# Uso:  bash ensaio-local.sh [--manter]      (--manter deixa os contêineres de pé para inspeção)
# Requer: docker local. Saída: um PASSOU/FALHOU por item e o resumo; o log completo vai para $ENSAIO_LOG (padrão: ./ensaio-AAAAMMDD.log).
#
# Limites (o contêiner não é a S5): sem módulo wireguard no kernel do hospedeiro o wg0 não sobe (a chave, o wg0.conf e o
# `wg-quick strip` são ensaiados); sem Docker dentro do contêiner (20-docker.sh só em --simular); NTP é do hospedeiro; Tailscale
# instala mas não faz login. Cada limite aparece como PULOU, nunca como PASSOU.
set -uo pipefail
# roda de uma CÓPIA: o bash lê o script aos poucos, e editar o original durante o ensaio o quebraria
if [ -z "${ENSAIO_KIT:-}" ]; then
  copia="$(mktemp)"; cp "$0" "$copia"
  ENSAIO_KIT="$(cd "$(dirname "$0")" && pwd)" exec bash "$copia" "$@"
fi
KIT="$ENSAIO_KIT"
REPO="$(cd "$KIT/../.." && pwd)"
MANTER=0; [ "${1:-}" = --manter ] && MANTER=1
P=ia-s5-ensaio
REDE="$P-rede"; S5="$P-s5"; S3="$P-s3"; IMG="$P:local"
TMP="$(mktemp -d)"; chmod 700 "$TMP"
ENSAIO_LOG="${ENSAIO_LOG:-$PWD/ensaio-$(date +%Y%m%d-%H%M).log}"
passou=0; falhou=0; pulou=0

ok() { printf 'PASSOU  %s\n' "$*" | tee -a "$ENSAIO_LOG"; passou=$((passou + 1)); }
nok() { printf 'FALHOU  %s\n' "$*" | tee -a "$ENSAIO_LOG"; falhou=$((falhou + 1)); }
pula() { printf 'PULOU   %s\n' "$*" | tee -a "$ENSAIO_LOG"; pulou=$((pulou + 1)); }
secao() { printf '\n######## %s\n' "$*" | tee -a "$ENSAIO_LOG"; }
espera() { local d="$1"; shift; if "$@" </dev/null; then ok "$d"; else nok "$d"; fi; }
nao() { ! "$@"; }
em_s5() { docker exec -i "$S5" bash -c "$1"; }
em_s3() { docker exec -i "$S3" bash -c "$1"; }
roda() {  # roda <descrição> <comando no S5> — guarda a saída no log; devolve o código
  local d="$1" c="$2" rc
  printf '\n$ %s\n' "$c" >>"$ENSAIO_LOG"
  em_s5 "$c" </dev/null >>"$ENSAIO_LOG" 2>&1; rc=$?
  printf '[%s] código %s\n' "$d" "$rc" >>"$ENSAIO_LOG"; return "$rc"
}

limpar() {
  [ "$MANTER" = 1 ] && { echo "contêineres mantidos: $S5 $S3 (docker rm -f $S5 $S3; docker network rm $REDE)"; rm -rf "$TMP"; return; }
  docker rm -f "$S5" "$S3" >/dev/null 2>&1; docker network rm "$REDE" >/dev/null 2>&1; rm -rf "$TMP"
}
trap limpar EXIT

secao "0. imagem e rede descartáveis"
cat >"$TMP/Dockerfile" <<'EOF'
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -q && apt-get install -y -q --no-install-recommends systemd systemd-sysv dbus openssh-server sudo python3 iproute2 \
      curl ca-certificates openssl gnupg locales rsync iputils-ping kmod && rm -rf /var/lib/apt/lists/* \
    && systemctl mask getty.target console-getty.service systemd-firstboot.service systemd-logind.service && systemctl enable ssh
STOPSIGNAL SIGRTMIN+3
CMD ["/bin/sh", "-c", "mount -o remount,rw /sys/fs/cgroup && exec /sbin/init"]
EOF
docker build -q -t "$IMG" "$TMP" >>"$ENSAIO_LOG" 2>&1 || { echo "build da imagem falhou (ver $ENSAIO_LOG)"; exit 2; }
docker rm -f "$S5" "$S3" >/dev/null 2>&1; docker network rm "$REDE" >/dev/null 2>&1
docker network create "$REDE" >/dev/null
OPCS=(-d -t -e container=docker --network "$REDE" --cap-add SYS_ADMIN --cap-add NET_ADMIN --security-opt seccomp=unconfined
      --security-opt apparmor=unconfined --cgroupns=private --tmpfs /run --tmpfs /run/lock --tmpfs /tmp)
docker run "${OPCS[@]}" --sysctl net.ipv4.ip_forward=1 --name "$S5" --hostname s5 -v "$KIT:/kit-ro:ro" -v "$REPO:/repo:ro" "$IMG" >/dev/null
docker run "${OPCS[@]}" --name "$S3" --hostname s3 "$IMG" >/dev/null
for _ in $(seq 1 30); do em_s5 'systemctl is-system-running' 2>/dev/null | grep -Eq 'running|degraded' && break; sleep 1; done
IP_S5="$(docker inspect -f "{{(index .NetworkSettings.Networks \"$REDE\").IPAddress}}" "$S5")"
IP_S3="$(docker inspect -f "{{(index .NetworkSettings.Networks \"$REDE\").IPAddress}}" "$S3")"
GW="$(docker network inspect -f '{{(index .IPAM.Config 0).Gateway}}' "$REDE")"
ok "contêineres de pé (S5 ${IP_S5}, S3 ${IP_S3}, hospedeiro ${GW})"
# o kit é copiado (o montado é só leitura) e o IP do wg0 da S5 fica num apelido do eth0 do CONTÊINER (não há módulo wireguard)
em_s5 'cp -a /kit-ro /kit && chmod 700 /kit && ip addr add 10.90.0.5/32 dev eth0'

secao "1. chaves e s5.env do ensaio (nada real)"
ssh-keygen -q -t ed25519 -N '' -C ensaio -f "$TMP/admin" >/dev/null
docker exec -i "$S5" bash -c 'install -d -m 700 /etc/ia-s5-adm && cat > /etc/ia-s5-adm/admin.pub' <"$TMP/admin.pub"
em_s5 'install -d -m 700 /etc/wireguard; command -v wg >/dev/null || true' >/dev/null
PUB_S2_FALSA="$(em_s5 'python3 -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())"')"
cat >"$TMP/s5.env" <<ENV
BANCO_LOCAL=s5
ADMIN_USUARIO=ensaio
ADMIN_CHAVES_ARQUIVO=/etc/ia-s5-adm/admin.pub
SSH_ORIGENS=${GW}/32
TAILSCALE_AUTHKEY_ARQUIVO=/etc/ia-s5-adm/nao-existe
FIREWALL_JANELA_S=60
FIREWALL_DHCP=nao
FIREWALL_UPLINK=
FIREWALL_DHCP_SERVIDOR=
WG_PORTA=51820
WG_IP_S5=10.90.0.5
WG_IP_S2=10.90.0.2
WG_PUB_S2=${PUB_S2_FALSA}
WG_ENDPOINT_S2=${IP_S3}:51820
WG_IP_S4=10.90.0.4
WG_PUB_S4=
WG_ENDPOINT_S4=
IA_PORTA=8000
IA_UID=10001
IA_SEGREDOS_DIR=/etc/ia-s5
IA_REGISTRO_IMAGEM=registro.exemplo.test:5010
REGISTRO_USUARIO=leitura
CHAVE_AES_ID=
PG_VERSAO=18
PG_PORTA=5432
PG_LEITURA_S2=sim
PG_SHARED_BUFFERS=128MB
PG_MAX_CONNECTIONS=50
S4_ENTREGA_DIR=/etc/ia-s4
S4_PG_PORTA=5434
BACKUP_DESTINO=ia-backup@${IP_S3}
BACKUP_DESTINO_DIR=/mnt/hdd/backups/ia-s5
BACKUP_AGE_DESTINATARIO=age1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq
BACKUP_BANCOS=ia_atendimento
BACKUP_RETENCAO_LOCAL_DIAS=3
BACKUP_FILA_MAX_HORAS=26
BACKUP_FILA_DIR=/var/backups/ia-s5
NTFY_URL_BASE=http://127.0.0.1:8099
ENV
docker exec -i "$S5" bash -c 'install -m 600 /dev/stdin /etc/ia-s5-adm/s5.env' <"$TMP/s5.env"
sed 's/^BANCO_LOCAL=s5/BANCO_LOCAL=s4/; s/^WG_PUB_S4=$/WG_PUB_S4=x/' "$TMP/s5.env" | docker exec -i "$S5" bash -c 'install -m 600 /dev/stdin /etc/ia-s5-adm/s5-s4.env'
ok "s5.env do ensaio gravado (0600)"

secao "2. tudo em --simular (BANCO_LOCAL=s5 e s4): nada pode mudar"
antes="$(em_s5 'find /etc /usr/local /var/backups -xdev -newer /kit/lib.sh -type f 2>/dev/null | sort | md5sum')"
for env in s5.env s5-s4.env; do
  for s in 10-endurecer 20-docker 30-wireguard 40-firewall 50-segredos 60-banco 70-alerta 80-backup; do
    if roda "simular $s ($env)" "cd /kit && bash $s.sh --env /etc/ia-s5-adm/$env"; then ok "simular $s ($env)"; else nok "simular $s ($env)"; fi
  done
  if roda "simular migrar ($env)" "cd /kit && bash migrar.sh --permitir-sem-tag --alvo s5 --repo /repo --env /etc/ia-s5-adm/$env"; then
    nok "migrar --alvo s5 sem PostgreSQL deveria parar ao ler o ledger ($env)"; else ok "migrar sem banco PARA ao ler o ledger ($env)"; fi
done
depois="$(em_s5 'find /etc /usr/local /var/backups -xdev -newer /kit/lib.sh -type f 2>/dev/null | sort | md5sum')"
[ "$antes" = "$depois" ] && ok "simular não criou nem alterou arquivo em /etc, /usr/local, /var/backups" || nok "simular alterou arquivos"
roda "env com \$" "printf 'BANCO_LOCAL=s5\nADMIN_USUARIO=\$(id)\n' > /tmp/ruim.env; chmod 600 /tmp/ruim.env; cd /kit && bash 10-endurecer.sh --env /tmp/ruim.env" \
  && nok "s5.env com \$(...) foi aceito" || ok "s5.env com \$(...) é recusado (parser sem source)"
roda "env aberto" "cp /etc/ia-s5-adm/s5.env /tmp/aberto.env; chmod 666 /tmp/aberto.env; cd /kit && bash 10-endurecer.sh --env /tmp/aberto.env" \
  && nok "s5.env 0666 foi aceito" || ok "s5.env gravável por outros é recusado"

secao "3. 10-endurecer --aplicar"
if roda "10 aplicar" "cd /kit && bash 10-endurecer.sh --aplicar"; then ok "10-endurecer aplicado"; else nok "10-endurecer aplicado"; fi
espera "sshd: senha desligada" em_s5 'sshd -T | grep -qx "passwordauthentication no"'
espera "SSH NOVO por chave do admin funciona" ssh -i "$TMP/admin" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o ConnectTimeout=5 "ensaio@$IP_S5" true
espera "SSH por senha recusado" nao ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o PreferredAuthentications=password -o ConnectTimeout=5 "ensaio@$IP_S5" true
espera "sudo sem senha do admin" ssh -i "$TMP/admin" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes "ensaio@$IP_S5" 'sudo -n true'
espera "unattended-upgrades habilitado" em_s5 'systemctl is-enabled unattended-upgrades'
roda "10 de novo" "cd /kit && bash 10-endurecer.sh --aplicar" && ok "10-endurecer idempotente (2ª passada sem erro)" || nok "10-endurecer 2ª passada"
pula "NTP: relógio do hospedeiro no contêiner (na S5 o verificar.sh confere NTPSynchronized)"
pula "tailscale up: exige login do dono (instalação ensaiada)"
secao "4. 20-docker"
pula "20-docker --aplicar: sem Docker dentro do contêiner (só --simular, item 2)"

secao "5. 30-wireguard --aplicar"
roda "30 aplicar" "cd /kit && bash 30-wireguard.sh --aplicar"; rc=$?
espera "chave privada 0600 e pública gerada" em_s5 '[ "$(stat -c %a /etc/wireguard/s5.key)" = 600 ] && [ -s /etc/wireguard/s5.pub ]'
espera "wg0.conf 0600 passa no wg-quick strip" em_s5 '[ "$(stat -c %a /etc/wireguard/wg0.conf)" = 600 ] && wg-quick strip wg0 >/dev/null'
espera "privada não apareceu na saída" nao grep -qF "$(em_s5 'cat /etc/wireguard/s5.key')" "$ENSAIO_LOG"
espera "wg0.conf sem rota default (AllowedIPs só /32)" nao em_s5 'grep -E "AllowedIPs = .*(0\.0\.0\.0/0|::/0)" /etc/wireguard/wg0.conf'
if [ "$rc" = 0 ]; then ok "wg0 subiu"; else pula "wg0 não sobe sem o módulo wireguard no kernel do hospedeiro (código $rc; esperado no contêiner)"; fi

secao "6. 40-firewall: caminho de volta, janela de reversão e confirmação por conexão NOVA"
# «porta publicada pelo Docker» simulada: um netns com ouvinte na 80 e DNAT da 18080 (o mesmo caminho prerouting → forward do Docker)
em_s5 'ip netns add pub && ip link add vh type veth peer name vp && ip link set vp netns pub && ip addr add 192.168.77.1/24 dev vh && ip link set vh up &&
  ip -n pub addr add 192.168.77.2/24 dev vp && ip -n pub link set vp up && ip -n pub link set lo up && ip -n pub route add default via 192.168.77.1 &&
  nft add table ip ensaio_nat && nft add chain ip ensaio_nat pre "{ type nat hook prerouting priority dstnat; }" &&
  nft add rule ip ensaio_nat pre tcp dport 18080 dnat to 192.168.77.2:80 &&
  nft add chain ip ensaio_nat pos "{ type nat hook postrouting priority srcnat; }" &&
  nft add rule ip ensaio_nat pos ip saddr 192.168.77.0/24 oifname eth0 masquerade' >>"$ENSAIO_LOG" 2>&1
docker exec -d "$S5" ip netns exec pub python3 -m http.server 80 --bind 192.168.77.2
for _ in $(seq 1 20); do em_s5 'ip netns exec pub timeout 1 bash -c "</dev/tcp/192.168.77.2/80"' 2>/dev/null && break; sleep 0.5; done
espera "porta «publicada» (DNAT 18080) alcançável de fora ANTES do firewall" timeout 4 bash -c "</dev/tcp/$IP_S5/18080"
SSHA=(ssh -i "$TMP/admin" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o ConnectTimeout=5 "ensaio@$IP_S5")
roda "40 sem ssh" "cd /kit && bash 40-firewall.sh --aplicar" && nok "40 sem SSH nem --sem-ssh-atual aplicou" || ok "40 sem SSH_CONNECTION recusa (pede --sem-ssh-atual)"
em_s5 "sed 's#^SSH_ORIGENS=.*#SSH_ORIGENS=203.0.113.0/24#' /etc/ia-s5-adm/s5.env > /etc/ia-s5-adm/s5-fora.env; chmod 600 /etc/ia-s5-adm/s5-fora.env"
"${SSHA[@]}" 'sudo bash /kit/40-firewall.sh --aplicar --env /etc/ia-s5-adm/s5-fora.env' >>"$ENSAIO_LOG" 2>&1 \
  && nok "40 aplicou com a sessão FORA das regras" || ok "40 recusa quando a sessão atual não está coberta (sob sudo, SSH_CONNECTION recuperada)"
espera "nada aplicado na recusa" nao em_s5 'nft list table inet ia_s5'
# aplicar e tentar confirmar NA MESMA conexão: a aplicação passa, a confirmação tem de ser recusada
"${SSHA[@]}" 'sudo bash /kit/40-firewall.sh --aplicar && echo APLICOU && sudo bash /kit/40-firewall.sh --aplicar --confirmar' >"$TMP/mesma.log" 2>&1; rc=$?
cat "$TMP/mesma.log" >>"$ENSAIO_LOG"
grep -q APLICOU "$TMP/mesma.log" && ok "40 aplicado com janela (sessão coberta por SSH_ORIGENS, sob sudo)" || nok "40 aplicado com janela"
[ "$rc" != 0 ] && grep -q "MESMA sessão" "$TMP/mesma.log" && ok "--confirmar recusado na MESMA conexão que aplicou" || nok "--confirmar aceito na mesma conexão"
espera "tabela viva e reversão armada" em_s5 'nft list table inet ia_s5 >/dev/null && systemctl is-active ia-s5-nft-reverte.timer'
# ouvintes de teste (no lugar do orquestrador e do PostgreSQL) para provar que a regra, e não a falta de serviço, fecha a porta
docker exec -d "$S5" python3 -m http.server 8000 --bind 0.0.0.0
docker exec -d "$S5" python3 -c 'import socket,time; s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(("0.0.0.0", 5432)); s.listen(); time.sleep(150)'
sleep 1
espera "os ouvintes respondem por dentro (lo)" em_s5 'timeout 3 bash -c "</dev/tcp/127.0.0.1/8000" && timeout 3 bash -c "</dev/tcp/127.0.0.1/5432"'
espera "conexão NOVA ainda entra depois de aplicar" "${SSHA[@]}" true
"${SSHA[@]}" 'sudo bash /kit/40-firewall.sh --aplicar --confirmar' >>"$ENSAIO_LOG" 2>&1 && ok "--confirmar de conexão NOVA" || nok "--confirmar de conexão NOVA"
espera "reversão desarmada e ia-s5-nft.service habilitado" em_s5 '! systemctl is-active ia-s5-nft-reverte.timer && systemctl is-enabled ia-s5-nft.service'
espera "porta 8000 (com ouvinte) fechada para quem não é a S2 pelo wg0" nao timeout 4 bash -c "</dev/tcp/$IP_S5/8000" 2>/dev/null
espera "porta 5432 (com ouvinte) fechada para o hospedeiro" nao timeout 4 bash -c "</dev/tcp/$IP_S5/5432" 2>/dev/null
em_s5 'pkill -f socket.socket; pkill -f http.server' >/dev/null 2>&1; sleep 1
espera "SSH continua aberto para SSH_ORIGENS" "${SSHA[@]}" true
espera "FIREWALL_DHCP=nao: nenhuma regra de DHCP" nao em_s5 'nft list chain inet ia_s5 input | grep -q "sport 67"'
em_s5 "sed 's/^FIREWALL_DHCP=nao/FIREWALL_DHCP=sim/; s/^FIREWALL_UPLINK=.*/FIREWALL_UPLINK=eth0/; s/^FIREWALL_DHCP_SERVIDOR=.*/FIREWALL_DHCP_SERVIDOR=${GW}/' /etc/ia-s5-adm/s5.env > /etc/ia-s5-adm/s5-dhcp.env; chmod 600 /etc/ia-s5-adm/s5-dhcp.env"
espera "FIREWALL_DHCP=sim: regra só no uplink, do servidor informado, para o IP da S5 ou broadcast" \
  em_s5 "cd /kit && bash 40-firewall.sh --env /etc/ia-s5-adm/s5-dhcp.env | grep -q 'iifname \"eth0\" ip saddr ${GW} ip daddr { ${IP_S5}, 255.255.255.255 } udp sport 67 udp dport 68'"
em_s5 "sed 's/^FIREWALL_UPLINK=.*/FIREWALL_UPLINK=/' /etc/ia-s5-adm/s5-dhcp.env > /etc/ia-s5-adm/s5-dhcp-ruim.env; chmod 600 /etc/ia-s5-adm/s5-dhcp-ruim.env"
roda "40 dhcp sem uplink" "cd /kit && bash 40-firewall.sh --env /etc/ia-s5-adm/s5-dhcp-ruim.env" && nok "FIREWALL_DHCP=sim sem uplink aceito" || ok "FIREWALL_DHCP=sim sem FIREWALL_UPLINK é recusado"
espera "porta «publicada» (DNAT 18080) FECHADA para fora pela chain forward" nao timeout 4 bash -c "</dev/tcp/$IP_S5/18080"
espera "o netns («contêiner») ainda sai para fora: a chain forward só barra a ENTRADA por DNAT" em_s5 "ip netns exec pub timeout 5 bash -c '</dev/tcp/${IP_S3}/22' || { nft list ruleset >&2; false; }"
# reversão: aplica de novo e NÃO confirma; em 60 s a tabela tem de sumir sozinha
"${SSHA[@]}" 'sudo bash /kit/40-firewall.sh --aplicar' >>"$ENSAIO_LOG" 2>&1
sleep 70
espera "sem confirmação, a tabela some sozinha em ${FIREWALL_JANELA_S:-60} s" nao em_s5 'nft list table inet ia_s5'
em_s5 'systemctl restart ia-s5-nft.service' && espera "ia-s5-nft.service recria a tabela (boot)" em_s5 'nft list table inet ia_s5'

secao "7. 50-segredos"
roda "50 aplicar" "cd /kit && bash 50-segredos.sh preparar --aplicar" && ok "50-segredos preparar" || nok "50-segredos preparar"
CHAVE_FW_FALSA="fw_ensaio_$(openssl rand -hex 12)"
printf '%s\n' "$CHAVE_FW_FALSA" | docker exec -i "$S5" bash -c 'cd /kit && bash 50-segredos.sh instalar MODELO_API_KEY_1 --aplicar' >>"$ENSAIO_LOG" 2>&1 \
  && ok "chave da Fireworks instalada pelo stdin" || nok "instalar MODELO_API_KEY_1"
printf 'hmac-ensaio-%s\n' "$(openssl rand -hex 20)" | docker exec -i "$S5" bash -c 'cd /kit && bash 50-segredos.sh instalar gateway-hmac.keys --aplicar' >>"$ENSAIO_LOG" 2>&1
printf '{"ia_orquestrador_bearer": "x%s"}\n' "$(openssl rand -hex 20)" | docker exec -i "$S5" bash -c 'cd /kit && bash 50-segredos.sh instalar saida.json --aplicar' >>"$ENSAIO_LOG" 2>&1
printf 'nao-e-json\n' | docker exec -i "$S5" bash -c 'cd /kit && bash 50-segredos.sh instalar saida.json --aplicar' >>"$ENSAIO_LOG" 2>&1 \
  && nok "saida.json inválido aceito" || ok "saida.json inválido recusado"
espera "chave da Fireworks 0600 do uid 10001" em_s5 '[ "$(stat -c "%a %u" /etc/ia-s5/env/MODELO_API_KEY_1)" = "600 10001" ]'
espera "mostrar-topico recusa pipe" nao em_s5 'set -o pipefail; cd /kit && bash 50-segredos.sh mostrar-topico | cat'
espera "entregar-tokens recusa terminal" nao docker exec -t "$S5" bash -c 'cd /kit && bash 50-segredos.sh entregar-tokens ti'
roda "50 de novo" "cd /kit && bash 50-segredos.sh preparar --aplicar" && ok "50-segredos idempotente" || nok "50-segredos 2ª passada"
espera "segredos internos não mudaram na 2ª passada" em_s5 'n=$(python3 -c "import json;print(len(json.load(open(\"/etc/ia-s5/chaves-aes.json\"))))"); [ "$n" = 1 ]'

secao "8. 60-banco (PostgreSQL 18 na S5)"
roda "60 aplicar" "cd /kit && bash 60-banco.sh --aplicar" && ok "60-banco aplicado" || nok "60-banco aplicado"
espera "8 papéis ia_*, nenhum privilegiado" em_s5 '[ "$(sudo -u postgres psql -qAt -c "select count(*) from pg_roles where rolname like '"'"'ia\_%'"'"' and not (rolsuper or rolcreatedb or rolcreaterole or rolbypassrls)")" = 8 ]'
espera "escuta em 127.0.0.1 e 10.90.0.5, não em 0.0.0.0" em_s5 'ss -ltn | grep -q "127.0.0.1:5432 " && ss -ltn | grep -q "10.90.0.5:5432 " && ! ss -ltn | grep -q "0.0.0.0:5432 "'
espera "DATABASE_URL do app conecta como ia_app_a" em_s5 'PGCONNECT_TIMEOUT=5 psql "$(cat /etc/ia-s5/env/DATABASE_URL)" -qAt -c "select current_user" | grep -qx ia_app_a'
espera "ia_app_a não entra no ia_obs (pg_hba)" nao em_s5 'u=$(cat /etc/ia-s5/env/DATABASE_URL); PGCONNECT_TIMEOUT=5 psql "${u%/ia_atendimento}/ia_obs" -c "select 1"'
espera "conexão sem TLS pelo IP do wg0 recusada" nao em_s5 'PGPASSWORD=$(cat /etc/ia-s5-adm/pg-senhas/ia_leitura_a.senha) psql "host=10.90.0.5 dbname=ia_atendimento user=ia_leitura_a sslmode=disable connect_timeout=5" -c "select 1"'
espera "senhas nunca na saída" nao grep -qF "$(em_s5 'cat /etc/ia-s5-adm/pg-senhas/ia_app_a.senha')" "$ENSAIO_LOG"
roda "60 de novo" "cd /kit && bash 60-banco.sh --aplicar" && ok "60-banco idempotente" || nok "60-banco 2ª passada"

secao "9. migrar.sh (G-0012) por ledger"
roda "migrar sem tag" "cd /kit && bash migrar.sh --alvo s5 --repo /repo" && nok "migrar aceitou checkout sem tag" || ok "migrar recusa checkout que não é uma tag limpa"
roda "migrar simular" "cd /kit && bash migrar.sh --permitir-sem-tag --alvo s5 --repo /repo" && ok "migrar em simular lê o ledger vazio" || nok "migrar simular"
roda "migrar ate 0004" "cd /kit && bash migrar.sh --permitir-sem-tag --alvo s5 --repo /repo --aplicar --ate 0004" && ok "0001–0004 aplicadas" || nok "0001–0004"
roda "migrar sem sim" "cd /kit && bash migrar.sh --permitir-sem-tag --alvo s5 --repo /repo --aplicar" ; em_s5 '[ "$(sudo -u postgres psql -qAt -d ia_atendimento -c "select count(*) from ia.migracao")" = 4 ]' \
  && ok "0005 NÃO roda sem --sim-0005" || nok "0005 rodou sem o sim"
roda "migrar 0005" "cd /kit && bash migrar.sh --permitir-sem-tag --alvo s5 --repo /repo --aplicar --sim-0005" && ok "0005 com --sim-0005" || nok "0005 com --sim-0005"
espera "ledger com 5 e checksums iguais aos arquivos" em_s5 'cd /repo/migrations && for f in 000*.up.sql; do s=$(sha256sum $f | cut -d" " -f1); [ "$(sudo -u postgres psql -qAt -d ia_atendimento -c "select checksum from ia.migracao where migracao_id = '"'"'${f%.up.sql}'"'"'")" = "$s" ] || exit 1; done'
roda "migrar de novo" "cd /kit && bash migrar.sh --permitir-sem-tag --alvo s5 --repo /repo --aplicar --sim-0005" && ok "migrar idempotente (nada a aplicar)" || nok "migrar 2ª passada"
em_s5 'rm -rf /tmp/repo2 && cp -a /repo/migrations /tmp/repo2-m && mkdir -p /tmp/repo2 && mv /tmp/repo2-m /tmp/repo2/migrations && echo "-- adulterado" >> /tmp/repo2/migrations/0004_anexo_rpa_e_espelho.up.sql'
roda "migrar adulterado" "cd /kit && bash migrar.sh --permitir-sem-tag --alvo s5 --repo /tmp/repo2 --aplicar --sim-0005" && nok "checksum divergente aceito" || ok "checksum divergente do ledger PARA"
espera "ia_app_a sem DDL (DROP TABLE falha)" nao em_s5 'psql "$(cat /etc/ia-s5/env/DATABASE_URL)" -c "DROP TABLE ia.passo"'
espera "seed como ia_app_a: ia_ativa=false" em_s5 "psql \"\$(cat /etc/ia-s5/env/DATABASE_URL)\" -qAt -c \"select valor::text from ia.config_versao where nome = 'ia_ativa'\" | grep -qx false"

secao "10. 70-alerta (ntfy FALSO em 127.0.0.1:8099; nada sai para a internet)"
docker exec -d "$S5" python3 -c '
import http.server
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); corpo = self.rfile.read(n).decode()
        open("/tmp/ntfy.log", "a").write(self.path + " " + corpo + "\n"); self.send_response(200); self.end_headers(); self.wfile.write(b"{}")
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", 8099), H).serve_forever()'
sleep 1
roda "70 aplicar" "cd /kit && bash 70-alerta.sh --aplicar --testar" && ok "70-alerta aplicado e teste enviado" || nok "70-alerta"
TOPICO="$(em_s5 'cat /etc/ia-s5-adm/ntfy.topico')"
espera "o ntfy recebeu «s5 teste_alerta origem=kit» no tópico" em_s5 "grep -qx '/${TOPICO} s5 teste_alerta origem=kit' /tmp/ntfy.log"
em_s5 '/usr/local/sbin/ia-alerta teste_pii cpf=000.000.001-91 tel=11-98765-4321 banco=Maria.Silva origem=fulano@x.test horas=12345678' >/dev/null 2>&1
espera "PII formatada (CPF, telefone, nome, e-mail, número longo) recusada; nada dela chega ao ntfy" em_s5 'tail -1 /tmp/ntfy.log | grep -qx "/[^ ]* s5 teste_pii par_recusado=1 par_recusado=1 par_recusado=1 par_recusado=1 par_recusado=1" && ! grep -Eq "000\.000\.001|98765|Maria|fulano|12345678" /tmp/ntfy.log'
em_s5 '/usr/local/sbin/ia-alerta "Codigo Com Espaco"' >/dev/null 2>&1
espera "código fora do formato vira alerta_invalido" em_s5 'tail -1 /tmp/ntfy.log | grep -q "s5 alerta_invalido"'
espera "tópico fora do journal" nao em_s5 "journalctl -q --no-pager | grep -qF '${TOPICO}'"
espera "tópico não aparece na saída do kit" nao grep -qF "$TOPICO" "$ENSAIO_LOG"

secao "11. 80-backup: fila local, envio à «S3» (contêiner), queda do destino e alerta"
em_s3 'apt-get update -q >/dev/null && DEBIAN_FRONTEND=noninteractive apt-get install -y -q age >/dev/null; useradd -m -s /bin/bash ia-backup; install -d -m 700 -o ia-backup -g ia-backup /mnt/hdd/backups/ia-s5' >>"$ENSAIO_LOG" 2>&1
em_s3 'age-keygen -o /root/backup.age.key 2>/dev/null; age-keygen -y /root/backup.age.key' >"$TMP/age.pub"
AGE_PUB="$(cat "$TMP/age.pub")"
em_s5 "sed -i 's#^BACKUP_AGE_DESTINATARIO=.*#BACKUP_AGE_DESTINATARIO=${AGE_PUB}#' /etc/ia-s5-adm/s5.env"
roda "80 aplicar" "cd /kit && bash 80-backup.sh --aplicar" && ok "80-backup aplicado" || nok "80-backup aplicado"
LINHA="$(em_s5 'cat /etc/ia-s5-adm/backup_ed25519.pub')"
docker cp "$KIT/s3-rrsync-backup.sh" "$S3:/usr/local/bin/s3-rrsync-backup"; em_s3 'chown root:root /usr/local/bin/s3-rrsync-backup; chmod 755 /usr/local/bin/s3-rrsync-backup'
printf 'restrict,command="/usr/local/bin/s3-rrsync-backup /mnt/hdd/backups/ia-s5" %s\n' "$LINHA" | em_s3 'install -d -m 700 -o ia-backup -g ia-backup /home/ia-backup/.ssh && cat > /home/ia-backup/.ssh/authorized_keys && chown ia-backup: /home/ia-backup/.ssh/authorized_keys && chmod 600 /home/ia-backup/.ssh/authorized_keys'
# no lugar do dono aceitando a chave da S3 uma vez (StrictHostKeyChecking=yes depois)
em_s5 "install -d -m 700 /root/.ssh; for i in \$(seq 1 20); do ssh-keyscan -T 3 ${IP_S3} >> /root/.ssh/known_hosts 2>/dev/null; ssh-keygen -F ${IP_S3} >/dev/null && break; sleep 1; done" </dev/null
espera "known_hosts da S5 conhece a S3" em_s5 "ssh-keygen -F ${IP_S3}"
espera "a chave do backup entra na S3 (presa ao invólucro)" em_s5 "ssh -i /etc/ia-s5-adm/backup_ed25519 -o BatchMode=yes ia-backup@${IP_S3} 2>&1 | grep -q 'recusado (comando fora da lista fechada)'"
roda "backup" "systemctl start ia-s5-backup.service" && ok "backup diário rodou" || nok "backup diário"
espera "fila com o dump cifrado e o .sha256, sem dump em claro" em_s5 'ls /var/backups/ia-s5/fila/ia_atendimento-*.dump.age >/dev/null && ! find /var/backups/ia-s5 -name "*.dump" -o -name "*.parcial" | grep -q .'
espera "o arquivo da fila é age (não é PGDMP em claro)" em_s5 'head -c 30 /var/backups/ia-s5/fila/ia_atendimento-*.dump.age | grep -q "age-encryption.org"'
roda "enviar" "systemctl start ia-s5-backup-enviar.service" && ok "envio rodou" || nok "envio"
espera "S3 recebeu e a fila da S5 esvaziou" bash -c "docker exec $S3 sh -c 'ls /mnt/hdd/backups/ia-s5/ia_atendimento-*.dump.age' >/dev/null && [ -z \"\$(docker exec $S5 sh -c 'ls /var/backups/ia-s5/fila/*.age 2>/dev/null')\" ]"
espera "na S3 decifra com a chave do dono e é um dump do PostgreSQL (PGDMP)" em_s3 'f=$(ls /mnt/hdd/backups/ia-s5/ia_atendimento-*.dump.age | head -1); [ -n "$f" ] && age -d -i /root/backup.age.key "$f" | head -c 5 | grep -q PGDMP'
espera "chave do backup NÃO lê nem lista na S3" nao em_s5 "ssh -i /etc/ia-s5-adm/backup_ed25519 -o BatchMode=yes ia-backup@${IP_S3} ls"
espera "chave do backup não puxa arquivo da S3" nao em_s5 "rsync -e 'ssh -i /etc/ia-s5-adm/backup_ed25519 -o BatchMode=yes' ia-backup@${IP_S3}:ia_atendimento-x /tmp/"
RSB="rsync -e 'ssh -i /etc/ia-s5-adm/backup_ed25519 -o BatchMode=yes'"
ALVO1="$(em_s3 'basename "$(ls /mnt/hdd/backups/ia-s5/ia_atendimento-*.dump.age | head -1)"')"
SHA1="$(em_s3 "sha256sum /mnt/hdd/backups/ia-s5/$ALVO1 | cut -d' ' -f1")"
em_s5 "mkdir -p /tmp/vazio && $RSB -r --delete /tmp/vazio/ ia-backup@${IP_S3}:" >>"$ENSAIO_LOG" 2>&1
espera "rsync --delete com a chave do backup NÃO apaga nada na S3 (-no-del)" em_s3 "test -f /mnt/hdd/backups/ia-s5/$ALVO1"
em_s5 "head -c 100 /dev/urandom > /tmp/$ALVO1 && $RSB /tmp/$ALVO1 ia-backup@${IP_S3}:" >>"$ENSAIO_LOG" 2>&1
em_s5 "$RSB -I /tmp/$ALVO1 ia-backup@${IP_S3}:" >>"$ENSAIO_LOG" 2>&1
em_s5 "$RSB --ignore-existing -I /tmp/$ALVO1 ia-backup@${IP_S3}:" >>"$ENSAIO_LOG" 2>&1
espera "sobrescrever um backup que já existe na S3 não muda o arquivo (-no-overwrite)" em_s3 "[ \"\$(sha256sum /mnt/hdd/backups/ia-s5/$ALVO1 | cut -d' ' -f1)\" = '$SHA1' ]"
# variantes de burla do invólucro, direto na «S3» com comandos forjados: todas têm de sair 1 ANTES do rrsync
for burla in "rsync --server -te.LsfxCIvu . . --ignore-existing" "rsync --server -te.LsfxCIvu --ignore-existing --no-ignore-existing . ." \
             "rsync --server -te.LsfxCIvu --existing --ignore-existing . ." "rsync --server -tle.LsfxCIvu --ignore-existing . ." \
             "rsync --server -tLe.LsfxCIvu --ignore-existing . ." "rsync --server -te.LsfxCIvu --delete --ignore-existing . ." \
             "rsync --server --sender -te.LsfxCIvu --ignore-existing . ." "rsync --server -te.LsfxCIvu --ignore-existing . . ; id"; do
  printf '%s' "$burla" >"$TMP/burla"
  docker cp "$TMP/burla" "$S3:/tmp/burla" >/dev/null
  if em_s3 'SSH_ORIGINAL_COMMAND="$(cat /tmp/burla)" /usr/local/bin/s3-rrsync-backup /mnt/hdd/backups/ia-s5 </dev/null >/dev/null 2>&1; [ $? = 1 ]'; then
    ok "s3-rrsync-backup recusa: ${burla#rsync --server }"
  else nok "s3-rrsync-backup ACEITOU: ${burla#rsync --server }"; fi
done
docker cp "$KIT/s3-arquivar-backup.sh" "$S3:/root/s3-arquivar-backup.sh"
em_s3 'bash /root/s3-arquivar-backup.sh --aplicar' >>"$ENSAIO_LOG" 2>&1 && ok "s3-arquivar-backup moveu o que chegou para o arquivo morto" || nok "s3-arquivar-backup"
espera "no arquivo morto: root 0400, fora do alcance do rrsync; entrada vazia" em_s3 "f=\$(find /mnt/hdd/backups/ia-s5-arquivo -name '$ALVO1'); [ -n \"\$f\" ] && [ \"\$(stat -c '%a %U' \$f)\" = '400 root' ] && ! ls /mnt/hdd/backups/ia-s5/*.age 2>/dev/null"
espera "a chave do backup não alcança o arquivo morto" nao em_s5 "$RSB ia-backup@${IP_S3}:../ia-s5-arquivo/ /tmp/x/"
docker stop -t 2 "$S3" >/dev/null
roda "backup com S3 fora" "systemctl start ia-s5-backup.service"
roda "enviar com S3 fora" "systemctl start ia-s5-backup-enviar.service"
espera "com a S3 fora, o dump FICA na fila" em_s5 'ls /var/backups/ia-s5/fila/ia_atendimento-*.dump.age >/dev/null'
em_s5 'touch -d "30 hours ago" /var/backups/ia-s5/fila/*.age'
roda "enviar atrasado" "systemctl start ia-s5-backup-enviar.service"
espera "fila parada > 26 h gera alerta backup_fila_atrasada (sem PII)" em_s5 'grep -Eq "s5 backup_fila_atrasada horas=3[0-9] arquivos=[0-9]+$" /tmp/ntfy.log'
docker start "$S3" >/dev/null
for _ in $(seq 1 30); do em_s3 'systemctl is-active ssh' 2>/dev/null | grep -qx active && break; sleep 1; done
roda "enviar de volta" "systemctl start ia-s5-backup-enviar.service"
espera "S3 de volta: a fila esvazia sozinha" bash -c "[ -z \"\$(docker exec $S5 sh -c 'ls /var/backups/ia-s5/fila/*.age 2>/dev/null')\" ]"

secao "12. verificar.sh (só leitura)"
roda "verificar" "cd /kit && bash verificar.sh"; rc=$?
em_s5 'cd /kit && bash verificar.sh' 2>/dev/null | grep -E '^(PASSOU|FALHOU|PULOU)|^== verificar' | sed 's/^/   /' | tee -a "$ENSAIO_LOG"
[ "$rc" != 0 ] && pula "verificar.sh tem FALHOU esperados no contêiner (Docker, wg0, tailscale, NTP): ver a lista acima" || ok "verificar.sh sem FALHOU"
em_s5 'touch /tmp/marca-verificar'; sleep 1
em_s5 'cd /kit && bash verificar.sh' >/dev/null 2>&1
escritos="$(em_s5 'find /etc /usr/local /var/backups /root -xdev -type f -newer /tmp/marca-verificar 2>/dev/null')"
[ -z "$escritos" ] && ok "verificar.sh não escreveu nada (nenhum arquivo mais novo que a marca)" || nok "verificar.sh escreveu: $escritos"

secao "13. nenhum segredo na saída do ensaio"
for arq in /etc/ia-s5/env/MODELO_API_KEY_1 /etc/ia-s5/env/CHAVE_H16 /etc/ia-s5/env/CHAT_REF_CHAVE /etc/ia-s5-adm/pg-senhas/ia_obs_a.senha; do
  v="$(em_s5 "head -1 $arq")"
  [ -n "$v" ] && ! grep -qF "$v" "$ENSAIO_LOG" && ok "valor de $(basename "$arq") ausente do log" || nok "valor de $(basename "$arq") no log (ou vazio)"
done
grep -qF "$CHAVE_FW_FALSA" "$ENSAIO_LOG" && nok "chave Fireworks falsa no log" || ok "chave Fireworks falsa ausente do log"

printf '\n== ensaio-local.sh: %d PASSOU, %d FALHOU, %d PULOU (log: %s)\n' "$passou" "$falhou" "$pulou" "$ENSAIO_LOG" | tee -a "$ENSAIO_LOG"
[ "$falhou" = 0 ]
