#!/usr/bin/env bash
# 30-wireguard.sh — par de chaves da S5, wg0 com a S2 (contratos 01 e 02: gateway e chatguru-api) e, com BANCO_LOCAL=s4, com a S4.
# Imprime (não executa) o bloco que o DONO roda na S2 e na S4: peer ADITIVO com `wg set`, nunca `wg syncconf` (memória s4-provisionada).
#
# Uso:  sudo bash 30-wireguard.sh [--aplicar]
# Duas passadas: a 1ª gera a chave e mostra a PÚBLICA (o dono a cadastra na S2/S4 e preenche WG_PUB_S2/WG_ENDPOINT_S2 no s5.env);
# a 2ª escreve /etc/wireguard/wg0.conf e sobe o wg0. Sem os peers a 1ª passada PARA com código 3 (de propósito).
# A chave privada nunca sai da S5 nem aparece na tela: entra no wg0.conf (0600) por arquivo, como no estudo E §3.2.
# Desfazer: systemctl disable --now wg-quick@wg0; na S2/S4, `wg set wg0 peer <S5_PUB> remove` e restaurar o .bak-ia-*.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
ler_args "$@"
carregar_env
exigir BANCO_LOCAL WG_PORTA WG_IP_S5 WG_IP_S2 IA_PORTA
validar_banco_local
exigir_root
validar_ipv4 "$WG_IP_S5" WG_IP_S5; validar_ipv4 "$WG_IP_S2" WG_IP_S2; validar_porta "$WG_PORTA" WG_PORTA
WG_DIR=/etc/wireguard
CHAVE="$WG_DIR/s5.key"; PUB="$WG_DIR/s5.pub"

titulo "1. par de chaves da S5"
if [ -s "$CHAVE" ]; then info "chave já existe (não troco: trocar exige recadastrar nos peers)"
else rodar sh -c "umask 077; install -d -m 700 $WG_DIR; wg genkey > $CHAVE; wg pubkey < $CHAVE > $PUB"; fi
if aplicando; then
  [ "$(stat -c '%a' "$CHAVE")" = 600 ] || chmod 600 "$CHAVE"
  S5_PUB="$(cat "$PUB")"; info "chave PÚBLICA da S5 (entregar ao dono): $S5_PUB"
else S5_PUB="<pública da S5, do passo 1>"; fi

peers_ok=1
for v in WG_PUB_S2 WG_ENDPOINT_S2; do [ -n "${!v:-}" ] || peers_ok=0; done
if [ "$BANCO_LOCAL" = s4 ]; then for v in WG_IP_S4 WG_PUB_S4 WG_ENDPOINT_S4; do [ -n "${!v:-}" ] || peers_ok=0; done; fi

titulo "2. bloco para o DONO rodar na S2 (e na S4) — NÃO executado por este script"
lado() {  # lado <nome> <ip_s5> ; imprime o bloco aditivo
  cat <<TXT
   # --- na $1, como root (aditivo; NUNCA wg syncconf nem wg-quick strip) ---
   cp -p /etc/wireguard/wg0.conf /etc/wireguard/wg0.conf.bak-ia-\$(date +%Y%m%d%H%M%S)
   wg set wg0 peer '${S5_PUB}' allowed-ips ${2}/32 endpoint <IP_PUBLICO_DA_S5>:${WG_PORTA} persistent-keepalive 25
   printf '\\n# --- S5 IA ---\\n[Peer]\\nPublicKey = %s\\nAllowedIPs = %s/32\\nEndpoint = <IP_PUBLICO_DA_S5>:%s\\nPersistentKeepalive = 25\\n' '${S5_PUB}' ${2} ${WG_PORTA} >> /etc/wireguard/wg0.conf
TXT
}
lado S2 "$WG_IP_S5"
cat <<TXT
   ip route replace ${WG_IP_S5}/32 dev wg0
   ufw allow from <IP_PUBLICO_DA_S5> to any port ${WG_PORTA} proto udp comment 'WireGuard S5 IA'
   # conferir: wg show wg0 latest-handshakes (os peers antigos continuam frescos)
TXT
if [ "$BANCO_LOCAL" = s4 ]; then
  lado S4 "$WG_IP_S5"
  echo "   # na S4 também: a linha nft do estudo E passo 4 trocando 10.90.0.5 por ${WG_IP_S5} (só porta ${S4_PG_PORTA:-5434}, só wg0)"
fi

if [ "$peers_ok" = 0 ]; then
  echo
  echo "== PAUSA: faltam WG_PUB_S2/WG_ENDPOINT_S2$([ "$BANCO_LOCAL" = s4 ] && echo ' e WG_PUB_S4/WG_ENDPOINT_S4') no s5.env."
  echo "   Entregue a pública acima ao dono, ele roda o bloco na S2/S4 e devolve as públicas e endpoints; rode este script de novo."
  aplicando && exit 3
  echo "   (simular: sigo mostrando o resto com valores de exemplo)"
  WG_PUB_S2="${WG_PUB_S2:-<pública da S2>}"; WG_ENDPOINT_S2="${WG_ENDPOINT_S2:-<ip:porta da S2>}"
  WG_PUB_S4="${WG_PUB_S4:-<pública da S4>}"; WG_ENDPOINT_S4="${WG_ENDPOINT_S4:-<ip:porta da S4>}"
fi

titulo "3. /etc/wireguard/wg0.conf (0600; a privada entra por arquivo, não pela tela)"
montar_conf() {  # stdout: o wg0.conf; a linha PrivateKey é lida do arquivo só no modo aplicar
  printf '# kit s5 (30-wireguard.sh). Sem rota default: só /32 dos peers.\n[Interface]\nAddress = %s/32\nListenPort = %s\n' "$WG_IP_S5" "$WG_PORTA"
  if aplicando; then printf 'PrivateKey = %s\n' "$(cat "$CHAVE")"; else printf 'PrivateKey = <conteúdo de %s, não exibido>\n' "$CHAVE"; fi
  printf '\n[Peer]\n# S2 (gateway, chatguru-api, n8n)\nPublicKey = %s\nAllowedIPs = %s/32\nEndpoint = %s\nPersistentKeepalive = 25\n' \
    "$WG_PUB_S2" "$WG_IP_S2" "$WG_ENDPOINT_S2"
  if [ "$BANCO_LOCAL" = s4 ]; then
    printf '\n[Peer]\n# S4 (PostgreSQL gl360, bancos da IA)\nPublicKey = %s\nAllowedIPs = %s/32\nEndpoint = %s\nPersistentKeepalive = 25\n' \
      "$WG_PUB_S4" "$WG_IP_S4" "$WG_ENDPOINT_S4"
  fi
}
if aplicando; then
  [ "${WG_PUB_S2}" != "$S5_PUB" ] || falhar "WG_PUB_S2 igual à pública da S5"
  montar_conf | escrever_segredo "$WG_DIR/wg0.conf.novo" root:root
  if [ -f "$WG_DIR/wg0.conf" ] && cmp -s "$WG_DIR/wg0.conf.novo" "$WG_DIR/wg0.conf"; then rm -f "$WG_DIR/wg0.conf.novo"; info "wg0.conf já estava igual"
  else
    [ ! -f "$WG_DIR/wg0.conf" ] || cp -p "$WG_DIR/wg0.conf" "$WG_DIR/wg0.conf.bak-ia-$(date -u +%Y%m%d%H%M%S)"
    mv "$WG_DIR/wg0.conf.novo" "$WG_DIR/wg0.conf"; info "wg0.conf gravado"
  fi
  wg-quick strip wg0 >/dev/null || falhar "wg0.conf não passa no wg-quick strip"
else montar_conf | sed 's/^/      | /'; fi

titulo "4. subir e manter no boot"
rodar systemctl enable wg-quick@wg0
if aplicando && ip link show wg0 >/dev/null 2>&1; then rodar systemctl restart wg-quick@wg0; else rodar systemctl start wg-quick@wg0; fi
if aplicando; then
  sleep 5
  wg show wg0 latest-handshakes | awk '{print "   handshake", substr($1,1,8)"…", ($2==0?"NENHUM":"ok")}'
  ping -c2 -W2 "$WG_IP_S2" >/dev/null && info "ping ${WG_IP_S2} ok" || aviso "sem ping na S2 ainda: o bloco do passo 2 já foi rodado lá?"
fi
resumo_ok
