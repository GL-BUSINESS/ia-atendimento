#!/usr/bin/env bash
# verificar.sh — SÓ LEITURA. Confere cada etapa do kit da S5 e imprime PASSOU / FALHOU / PULOU, com o passo a refazer.
# Não muda nada, não conecta em outro servidor, não imprime segredo (só nomes, modos, contagens e estados).
#
# Uso:  sudo bash verificar.sh [--env ARQ] [--etapa 10|20|30|40|50|60|70|80|app]
# Saída: 0 sem FALHOU; 1 com algum FALHOU.
set -uo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
set +e; trap - ERR
ler_args "$@"
carregar_env
ETAPA=""; [ "${ARGS_RESTANTES[0]:-}" = --etapa ] && ETAPA="${ARGS_RESTANTES[1]:-}"
[ "$(id -u)" = 0 ] || { echo "rode como root (sudo): vários arquivos conferidos são 0600"; exit 2; }
passou=0; falhou=0; pulou=0
ok() { printf 'PASSOU  [%s] %s\n' "$1" "$2"; passou=$((passou + 1)); }
nok() { printf 'FALHOU  [%s] %s  → refazer: %s\n' "$1" "$2" "$3"; falhou=$((falhou + 1)); }
pula() { printf 'PULOU   [%s] %s\n' "$1" "$2"; pulou=$((pulou + 1)); }
checa() { local e="$1" desc="$2" refazer="$3"; shift 3; if "$@" >/dev/null 2>&1; then ok "$e" "$desc"; else nok "$e" "$desc" "$refazer"; fi; }
quer() { [ -z "$ETAPA" ] || [ "$ETAPA" = "$1" ]; }
modo_dono() { [ "$(stat -c '%a %u' "$1" 2>/dev/null)" = "$2" ]; }

if quer 10; then
  e=10; r="10-endurecer.sh --aplicar"
  checa $e "usuário ${ADMIN_USUARIO:-?} existe" "$r" id "${ADMIN_USUARIO:-x}"
  casa="$(getent passwd "${ADMIN_USUARIO:-x}" | cut -d: -f6)"
  checa $e "authorized_keys do admin não vazio" "$r" test -s "${casa:-/nonexistent}/.ssh/authorized_keys"
  checa $e "sshd: senha desligada" "$r" sh -c "sshd -T 2>/dev/null | grep -qx 'passwordauthentication no'"
  checa $e "sshd: root só por chave" "$r" sh -c "sshd -T 2>/dev/null | grep -Eqx 'permitrootlogin (without-password|prohibit-password|no)'"
  checa $e "unattended-upgrades habilitado" "$r" systemctl is-enabled unattended-upgrades
  checa $e "fuso UTC" "$r" sh -c "[ \"\$(timedatectl show -p Timezone --value)\" = UTC ]"
  checa $e "relógio sincronizado (NTP)" "$r" sh -c "[ \"\$(timedatectl show -p NTPSynchronized --value)\" = yes ]"
  if command -v tailscale >/dev/null; then checa $e "tailscale conectado" "tailscale up (dono)" tailscale status
  else nok $e "tailscale instalado" "$r"; fi
fi

if quer 20; then
  e=20; r="20-docker.sh --aplicar"
  checa $e "docker ativo" "$r" systemctl is-active docker
  checa $e "docker habilitado no boot" "$r" systemctl is-enabled docker
  checa $e "daemon.json com teto de log e live-restore" "$r" sh -c "jq -e '.\"live-restore\" == true and .\"log-opts\".\"max-size\"' /etc/docker/daemon.json"
  checa $e "docker só depois do wg0 (drop-in)" "$r" grep -q 'After=wg-quick@wg0' /etc/systemd/system/docker.service.d/apos-wg0.conf
  checa $e "login no registro ${IA_REGISTRO_IMAGEM:-?} presente" "$r" sh -c "jq -e --arg r '${IA_REGISTRO_IMAGEM:-x}' '.auths[\$r]' /root/.docker/config.json"
  checa $e "/root/.docker/config.json 0600" "$r" modo_dono /root/.docker/config.json "600 0"
fi

if quer 30; then
  e=30; r="30-wireguard.sh --aplicar"
  checa $e "chave privada 0600" "$r" modo_dono /etc/wireguard/s5.key "600 0"
  checa $e "wg0.conf 0600" "$r" modo_dono /etc/wireguard/wg0.conf "600 0"
  checa $e "wg-quick@wg0 habilitado" "$r" systemctl is-enabled wg-quick@wg0
  checa $e "wg0 com ${WG_IP_S5:-?}/32" "$r" sh -c "ip -4 -o addr show wg0 | grep -q ' ${WG_IP_S5:-x}/32 '"
  checa $e "sem rota default pelo wg0" "$r" sh -c "! ip route show default | grep -q 'dev wg0'"
  esperado=1; [ "${BANCO_LOCAL:-}" = s4 ] && esperado=2
  n="$(wg show wg0 peers 2>/dev/null | wc -l)"
  [ "$n" = "$esperado" ] && ok $e "wg0 com $n peer(s)" || nok $e "wg0 com $n peer(s), esperado $esperado" "$r"
  agora=$(date +%s)
  while read -r _ hs; do
    [ -n "${hs:-}" ] || continue
    if [ "$hs" -gt 0 ] && [ $((agora - hs)) -lt 180 ]; then ok $e "handshake fresco ($((agora - hs)) s)"; else nok $e "peer sem handshake recente" "bloco do dono na S2/S4 (30-wireguard.sh passo 2)"; fi
  done < <(wg show wg0 latest-handshakes 2>/dev/null)
  checa $e "ping na S2 pelo wg0 (${WG_IP_S2:-?})" "$r" ping -c1 -W2 "${WG_IP_S2:-127.0.0.2}"
fi

if quer 40; then
  e=40; r="40-firewall.sh --aplicar (e --confirmar de outra conexão)"
  checa $e "tabela inet ia_s5 viva" "$r" nft list table inet ia_s5
  checa $e "policy drop no input" "$r" sh -c "nft list chain inet ia_s5 input | grep -q 'policy drop'"
  checa $e "porta ${IA_PORTA:-8000} só de ${WG_IP_S2:-?} pelo wg0" "$r" sh -c "nft list chain inet ia_s5 input | grep -q 'iifname \"wg0\" ip saddr ${WG_IP_S2:-x} tcp dport ${IA_PORTA:-8000}'"
  n="$(nft list chain inet ia_s5 input 2>/dev/null | grep -c "dport ${IA_PORTA:-8000}")"
  [ "$n" = 1 ] && ok $e "uma só regra abre a porta ${IA_PORTA:-8000}" || nok $e "$n regras abrem a porta ${IA_PORTA:-8000}" "$r"
  checa $e "ia-s5-nft.service habilitado (persiste no boot)" "--confirmar de uma conexão NOVA" systemctl is-enabled ia-s5-nft.service
  if systemctl is-active ia-s5-nft-reverte.timer >/dev/null 2>&1; then nok $e "reversão AINDA armada (não confirmado)" "--confirmar de uma conexão NOVA"; else ok $e "sem reversão pendente"; fi
  if [ "${FIREWALL_DHCP:-nao}" = sim ]; then
    checa $e "DHCP só no uplink ${FIREWALL_UPLINK:-?}, para o IP da S5 ou broadcast" "$r" sh -c "nft list chain inet ia_s5 input | grep 'sport 67' | grep -q 'iifname \"${FIREWALL_UPLINK:-x}\" .*ip daddr { [0-9.]*, 255.255.255.255 }'"
    n="$(nft list chain inet ia_s5 input 2>/dev/null | grep -c 'sport 67')"; [ "$n" = 1 ] && ok $e "uma só regra de DHCP" || nok $e "$n regras de DHCP" "$r"
  else
    checa $e "sem regra de DHCP (FIREWALL_DHCP=nao)" "$r" sh -c "! nft list chain inet ia_s5 input | grep -q 'sport 67'"
  fi
  checa $e "forward: porta publicada pelo Docker (DNAT) fechada para fora" "$r" sh -c "nft list chain inet ia_s5 forward | grep -q 'ct status dnat .* drop'"
  if command -v docker >/dev/null 2>&1; then
    pub="$(docker ps --format '{{.Names}} {{.Ports}}' 2>/dev/null | grep -E '(0\.0\.0\.0|\[::\]|:::)[0-9]+->' || true)"
    [ -z "$pub" ] && ok $e "nenhum contêiner publica porta em 0.0.0.0/[::]" || nok $e "contêiner publicando porta em todas as interfaces: $(echo "$pub" | cut -d' ' -f1 | tr '\n' ' ')" "tirar o ports: ou publicar só em 127.0.0.1/${WG_IP_S5:-IP do wg0}"
  fi
  checa $e "SSH admitido por tailscale0 ou SSH_ORIGENS" "$r" sh -c "nft list chain inet ia_s5 input | grep -Eq '(tailscale0|ip saddr .*) tcp dport 22'"
fi

if quer 60; then
  e=60; r="60-banco.sh --aplicar"
  case "${BANCO_LOCAL:-}" in
    s5)
      u="postgresql@${PG_VERSAO:-18}-main"
      checa $e "$u ativo" "$r" systemctl is-active "$u"
      checa $e "$u depois do wg0 (drop-in)" "$r" grep -q 'After=wg-quick@wg0' "/etc/systemd/system/$u.service.d/apos-wg0.conf"
      checa $e "escuta em 127.0.0.1:${PG_PORTA:-5432}" "$r" sh -c "ss -ltn | grep -q '127.0.0.1:${PG_PORTA:-5432} '"
      checa $e "não escuta em 0.0.0.0/[::]" "$r" sh -c "! ss -ltn | grep -Eq '(0\.0\.0\.0|\[::\]|\*):${PG_PORTA:-5432} '"
      q() { sudo -n -u postgres psql -X -qAt -p "${PG_PORTA:-5432}" -d postgres -c "$1" 2>/dev/null; }
      [ "$(q "select count(*) from pg_roles where rolname like 'ia\_%'")" = 8 ] && ok $e "8 papéis ia_*" || nok $e "papéis ia_* ≠ 8" "$r"
      [ "$(q "select count(*) from pg_roles where rolname like 'ia\_%' and (rolsuper or rolcreatedb or rolcreaterole or rolbypassrls)")" = 0 ] \
        && ok $e "nenhum papel ia_* privilegiado" || nok $e "papel ia_* com privilégio" "$r"
      [ "$(q "select string_agg(datname || ':' || pg_get_userbyid(datdba), ',' order by datname) from pg_database where datname like 'ia\_%'")" = "ia_atendimento:ia_owner,ia_obs:ia_obs_a" ] \
        && ok $e "bancos e donos" || nok $e "bancos/donos diferentes" "$r"
      [ "$(q "select count(*) from pg_hba_file_rules where error is not null")" = 0 ] && ok $e "pg_hba sem erro" || nok $e "pg_hba com erro" "$r"
      checa $e "senhas 0600 em /etc/ia-s5-adm/pg-senhas" "$r" sh -c 'for f in /etc/ia-s5-adm/pg-senhas/*.senha; do [ "$(stat -c %a "$f")" = 600 ] || exit 1; done'
      n="$(sudo -n -u postgres psql -X -qAt -p "${PG_PORTA:-5432}" -d ia_atendimento -c "select count(*) from ia.migracao" 2>/dev/null)"
      [ "${n:-0}" -ge 5 ] && ok $e "ledger com $n migrações" || nok $e "ledger com ${n:-0} migrações (esperado ≥ 5)" "migrar.sh --alvo s5 --aplicar"
      ;;
    s4)
      for f in ca.crt ia_app_a.crt ia_app_a.key ia_obs_a.crt ia_obs_a.key; do
        checa $e "$f 0600 do ${IA_UID:-10001}" "$r" modo_dono "${IA_SEGREDOS_DIR:-/x}/$f" "600 ${IA_UID:-10001}"
      done
      pula $e "conexão à S4 e ledger: provar.sh do kit s4 e migrar.sh --alvo s4 (leitura) da S3"
      ;;
    *) nok $e "BANCO_LOCAL vazio" "decisão do dono (DEC-PIA-009)" ;;
  esac
  checa $e "DATABASE_URL 0600 do ${IA_UID:-10001}" "$r" modo_dono "${IA_SEGREDOS_DIR:-/x}/env/DATABASE_URL" "600 ${IA_UID:-10001}"
fi

if quer 50; then
  e=50
  saida="$(bash "$KIT_DIR/50-segredos.sh" conferir ${S5_ENV_CARREGADO:+--env "$S5_ENV_CARREGADO"} 2>&1)"
  while read -r st resto; do
    case "$st" in PASSOU) ok $e "$resto" ;; FALHOU) nok $e "$resto" "50-segredos.sh (preparar/instalar)" ;; PULOU) pula $e "$resto" ;; esac
  done <<<"$saida"
fi

if quer 80; then
  e=80; r="80-backup.sh --aplicar"
  if [ "${BANCO_LOCAL:-}" = s5 ]; then
    for t in ia-s5-backup.timer ia-s5-backup-enviar.timer; do checa $e "$t ativo" "$r" systemctl is-active "$t"; done
    fila="${BACKUP_FILA_DIR:-/var/backups/ia-s5}"
    checa $e "fila 0700" "$r" modo_dono "$fila" "700 0"
    ultimo="$(find "$fila/fila" "$fila/enviados" -maxdepth 1 -name '*.dump.age' -printf '%T@\n' 2>/dev/null | sort -n | tail -1 | cut -d. -f1)"
    if [ -n "$ultimo" ] && [ $(( ($(date +%s) - ultimo) / 3600 )) -lt 26 ]; then ok $e "dump com menos de 26 h"; else nok $e "nenhum dump nas últimas 26 h" "systemctl start ia-s5-backup"; fi
    pend="$(find "$fila/fila" -maxdepth 1 -name '*.age' 2>/dev/null | wc -l)"
    [ "$pend" -le 2 ] && ok $e "fila com $pend arquivo(s)" || nok $e "fila com $pend arquivos (destino fora?)" "ver S3; ia-s5-backup-enviar"
    checa $e "nenhum dump em claro na fila" "$r" sh -c "! find '$fila' -type f \\( -name '*.dump' -o -name '*.sql' \\) | grep -q ."
  else pula $e "BANCO_LOCAL=${BANCO_LOCAL:-?}: backup é o da S4"; fi
fi

if quer 70; then
  e=70; r="70-alerta.sh --aplicar"
  checa $e "ia-alerta instalado" "$r" test -x /usr/local/sbin/ia-alerta
  checa $e "ia-s5-alerta@.service instalado" "$r" test -f /etc/systemd/system/ia-s5-alerta@.service
  checa $e "tópico 0600 do root" "50-segredos.sh --aplicar" modo_dono /etc/ia-s5-adm/ntfy.topico "600 0"
fi

if quer app; then
  e=app
  if command -v docker >/dev/null && [ -n "$(docker ps -q --filter label=coolify.managed=true 2>/dev/null)" ]; then
    for c in $(docker ps --format '{{.Names}}' | grep -E 'orquestrador|worker'); do
      st="$(docker inspect -f '{{.State.Health.Status}}' "$c" 2>/dev/null)"
      [ "$st" = healthy ] && ok $e "$c healthy" || nok $e "$c: $st" "docker logs $c (sem segredo: o boot cita só o campo)"
    done
    if [ -n "${WG_IP_S5:-}" ]; then
      checa $e "/healthz em ${WG_IP_S5}:${IA_PORTA:-8000}" "deploy-s5.sh" curl -fsS --max-time 3 "http://${WG_IP_S5}:${IA_PORTA:-8000}/healthz"
    fi
  else pula $e "orquestrador ainda não implantado (deploy-s5.sh --primeiro)"; fi
fi

printf '\n== verificar.sh: %d PASSOU, %d FALHOU, %d PULOU\n' "$passou" "$falhou" "$pulou"
[ "$falhou" = 0 ]
