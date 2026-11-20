#!/usr/bin/env bash
# 40-firewall.sh — tabela nftables própria `inet ia_s5` (INPUT DROP) com JANELA DE REVERSÃO e confirmação por CONEXÃO NOVA.
# Memória firewall-remoto-caminho-de-volta (S4, 02/09): a sessão aberta sobrevive (`established`), o ping continua, e só a conexão
# SEGUINTE descobre que ficou de fora. Por isso este script:
#   (a) RECUSA aplicar se a sessão de onde roda não estiver coberta por uma regra (tailscale0 ou SSH_ORIGENS);
#   (b) aplica com `systemd-run --on-active=${FIREWALL_JANELA_S}` que APAGA a tabela sozinho se ninguém confirmar;
#   (c) só confirma (`--confirmar`) a partir de uma sessão SSH DIFERENTE da que aplicou (outra porta de origem).
# Não usa `flush ruleset` (apagaria as regras do Docker e do Tailscale) e não toca em /etc/nftables.conf: a tabela persiste por um
# serviço próprio, ia-s5-nft.service, antes da rede.
#
# Uso:  sudo bash 40-firewall.sh [--aplicar]                 # aplica com janela (padrão simular: mostra as regras)
#       sudo bash 40-firewall.sh --aplicar --confirmar       # DE OUTRA CONEXÃO SSH: cancela a reversão e persiste
#       sudo bash 40-firewall.sh --aplicar --sem-ssh-atual   # rodando pelo console do provedor (sem SSH_CONNECTION)
# Desfazer: sudo nft delete table inet ia_s5 && sudo systemctl disable ia-s5-nft.service
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
ler_args "$@"
carregar_env
exigir BANCO_LOCAL WG_PORTA WG_IP_S2 IA_PORTA FIREWALL_JANELA_S
validar_banco_local
exigir_root
validar_ipv4 "$WG_IP_S2" WG_IP_S2; validar_porta "$IA_PORTA" IA_PORTA; validar_porta "$WG_PORTA" WG_PORTA
[ "$BANCO_LOCAL" != s5 ] || validar_porta "${PG_PORTA:-5432}" PG_PORTA
# DHCP só se a S5 recebe IP por DHCP (FIREWALL_DHCP=sim), só no uplink, só para o IP dela ou broadcast, e só do servidor informado
case "${FIREWALL_DHCP:-nao}" in nao) ;; sim)
  [[ "${FIREWALL_UPLINK:-}" =~ ^[A-Za-z0-9_.-]{1,15}$ ]] || falhar "FIREWALL_DHCP=sim exige FIREWALL_UPLINK (interface de saída, ex.: eth0)"
  [ -z "${FIREWALL_DHCP_SERVIDOR:-}" ] || validar_ipv4 "$FIREWALL_DHCP_SERVIDOR" FIREWALL_DHCP_SERVIDOR
  IP_UPLINK="$(ip -4 -o addr show dev "$FIREWALL_UPLINK" 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1)"
  if [ -z "$IP_UPLINK" ]; then aplicando && falhar "sem IPv4 em $FIREWALL_UPLINK"; IP_UPLINK="<IPv4 de $FIREWALL_UPLINK>"; fi
  [[ "$IP_UPLINK" == "<"* ]] || validar_ipv4 "$IP_UPLINK" IP_UPLINK ;;
  *) falhar "FIREWALL_DHCP deve ser sim ou nao" ;;
esac
[[ "$FIREWALL_JANELA_S" =~ ^[0-9]+$ ]] && [ "$FIREWALL_JANELA_S" -ge 60 ] || falhar "FIREWALL_JANELA_S ≥ 60"
CONFIRMAR=0; SEM_SSH=0
for a in "${ARGS_RESTANTES[@]:-}"; do
  case "$a" in --confirmar) CONFIRMAR=1 ;; --sem-ssh-atual) SEM_SSH=1 ;; "") ;; *) falhar "argumento desconhecido: $a" ;; esac
done
NFT_ARQ=/etc/ia-s5-adm/nft/ia-s5.nft
SESSAO_ARQ=/run/ia-s5-nft.sessao
UNIDADE_REVERTE=ia-s5-nft-reverte
_sessao="$(ssh_connection_da_sessao)"   # o sudo apaga SSH_CONNECTION; a função a recupera dos processos ancestrais
SESSAO_SSH="${_sessao%|*}"; SESSAO_INICIO="${_sessao##*|}"; [ -n "$_sessao" ] || { SESSAO_SSH=""; SESSAO_INICIO=0; }
NFT_NOVO="$NFT_ARQ.novo"   # o definitivo (lido no boot) só muda no --confirmar

# origens: endpoints WireGuard (só o IP) e SSH de emergência
endpoints=()
for v in WG_ENDPOINT_S2 WG_ENDPOINT_S4; do
  [ "$v" = WG_ENDPOINT_S4 ] && [ "$BANCO_LOCAL" != s4 ] && continue
  [ -n "${!v:-}" ] || continue
  ip="${!v%:*}"; validar_ipv4 "$ip" "$v"; endpoints+=("$ip")
done
[ "${#endpoints[@]}" -gt 0 ] || { aplicando && falhar "sem WG_ENDPOINT_S2: rode o 30-wireguard.sh até o fim antes"; endpoints=("<IP público da S2>"); }
ssh_origens=()
IFS=',' read -ra _o <<<"${SSH_ORIGENS:-}"
for o in "${_o[@]:-}"; do
  o="${o// /}"; [ -n "$o" ] || continue
  [[ "$o" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}(/[0-9]{1,2})?$ ]] || falhar "SSH_ORIGENS: '$o' não é IPv4/CIDR"
  ssh_origens+=("$o")
done

regras() {
  local lista_ep lista_ssh=""
  lista_ep="$(IFS=,; echo "${endpoints[*]}")"
  [ "${#ssh_origens[@]}" -eq 0 ] || lista_ssh="$(IFS=,; echo "${ssh_origens[*]}")"
  cat <<NFT
# kit s5 (40-firewall.sh) — gerado; editar o s5.env e rodar o script de novo. Idempotente: cria, apaga e recria a tabela numa transação.
table inet ia_s5
delete table inet ia_s5
table inet ia_s5 {
  chain input {
    type filter hook input priority filter; policy drop;
    ct state established,related accept
    ct state invalid drop
    iifname "lo" accept
    icmp type echo-request limit rate 5/second accept
    icmpv6 type { nd-neighbor-solicit, nd-neighbor-advert, nd-router-advert, nd-router-solicit } accept
    icmpv6 type echo-request limit rate 5/second accept
    ip saddr { ${lista_ep} } udp dport ${WG_PORTA} counter accept comment "wireguard dos peers"
NFT
  if [ "${FIREWALL_DHCP:-nao}" = sim ]; then
    local saddr=""; [ -z "${FIREWALL_DHCP_SERVIDOR:-}" ] || saddr="ip saddr ${FIREWALL_DHCP_SERVIDOR} "
    echo "    iifname \"${FIREWALL_UPLINK}\" ${saddr}ip daddr { ${IP_UPLINK}, 255.255.255.255 } udp sport 67 udp dport 68 counter accept comment \"renovacao DHCP so no uplink\""
  fi
  cat <<NFT
    udp dport 41641 counter accept comment "tailscale direto (sem ele cai no DERP)"
    iifname "tailscale0" tcp dport 22 counter accept comment "admin pelo tailnet"
NFT
  [ -z "$lista_ssh" ] || echo "    ip saddr { ${lista_ssh} } tcp dport 22 counter accept comment \"SSH de emergencia (SSH_ORIGENS)\""
  cat <<NFT
    iifname "wg0" ip saddr ${WG_IP_S2} tcp dport 22 counter accept comment "Coolify da S2 pelo wg0"
    iifname "wg0" ip saddr ${WG_IP_S2} tcp dport ${IA_PORTA} counter accept comment "gateway/n8n da S2 -> orquestrador"
NFT
  if [ "$BANCO_LOCAL" = s5 ] && [ "${PG_LEITURA_S2:-nao}" = sim ]; then
    echo "    iifname \"wg0\" ip saddr ${WG_IP_S2} tcp dport ${PG_PORTA:-5432} counter accept comment \"ia_leitura_a da S2 (contrato 03)\""
  fi
  cat <<NFT
    counter comment "negado pela policy drop"
  }
  # Porta PUBLICADA pelo Docker (ports: no compose de qualquer app, inclusive helper do Coolify) entra por DNAT no prerouting e segue
  # pelo FORWARD: a chain input acima não a vê. Aqui toda conexão NOVA que chegou por DNAT vinda de fora da máquina é derrubada.
  # Contêiner saindo para a internet não é DNAT e passa; o compose da IA usa rede host e não publica porta (teste da esteira).
  chain forward {
    type filter hook forward priority filter - 5; policy accept;
    ct state established,related accept
    ct state new ct status dnat iifname != "lo" counter drop comment "porta publicada pelo Docker: fechada para fora"
  }
}
NFT
}

# a sessão atual está coberta? 0 = sim. SSH_CONNECTION = "ip_cliente porta_cliente ip_local porta_local"
sessao_coberta() {
  local cli ifc o
  read -r cli _ <<<"${SESSAO_SSH:-}"
  [ -n "$cli" ] || return 1
  ifc="$(ip -o route get "$cli" 2>/dev/null | sed -n 's/.* dev \([^ ]*\).*/\1/p')"
  if [ "$ifc" = tailscale0 ]; then
    tailscale status >/dev/null 2>&1 && { info "sessão atual pelo tailscale0 (coberta)"; return 0; }
    return 1
  fi
  if [ "$ifc" = wg0 ] && [ "$cli" = "$WG_IP_S2" ]; then info "sessão atual pelo wg0 a partir da S2 (coberta)"; return 0; fi
  for o in "${ssh_origens[@]:-}"; do
    [ -n "$o" ] || continue
    python3 -c 'import ipaddress,sys; sys.exit(0 if ipaddress.ip_address(sys.argv[1]) in ipaddress.ip_network(sys.argv[2], strict=False) else 1)' "$cli" "$o" \
      && { info "sessão atual de ${cli} coberta por SSH_ORIGENS"; return 0; }
  done
  return 1
}

if [ "$CONFIRMAR" = 1 ]; then
  titulo "confirmar: só de uma CONEXÃO NOVA"
  aplicando || falhar "--confirmar precisa de --aplicar"
  [ -f "$SESSAO_ARQ" ] && [ -f "$NFT_NOVO" ] || falhar "não há aplicação pendente: a janela já venceu ou nada foi aplicado"
  [ -n "$SESSAO_SSH" ] || falhar "--confirmar tem de vir de uma sessão SSH (é isso que prova o caminho de volta)"
  IFS='|' read -r sessao_aplicou aplicado_em <"$SESSAO_ARQ" || true   # o arquivo não termina em \n
  [ "$sessao_aplicou" != "$SESSAO_SSH" ] || falhar "esta é a MESMA sessão que aplicou: abra outra conexão ssh e confirme de lá"
  [ "${SESSAO_INICIO:-0}" -ge "${aplicado_em:-0}" ] || falhar "esta sessão foi aberta ANTES da aplicação: só uma conexão aberta DEPOIS prova o caminho de volta"
  nft list table inet ia_s5 >/dev/null 2>&1 || falhar "a tabela ia_s5 não está viva (a reversão já rodou?): aplique de novo"
  systemctl stop "${UNIDADE_REVERTE}.timer" 2>/dev/null || true
  systemctl reset-failed "${UNIDADE_REVERTE}.service" 2>/dev/null || true
  rm -f "$SESSAO_ARQ"
  [ ! -f "$NFT_ARQ" ] || cp -p "$NFT_ARQ" "$NFT_ARQ.bak-ia-$(date -u +%Y%m%d%H%M%S)"
  mv "$NFT_NOVO" "$NFT_ARQ"; info "regras confirmadas viram as do boot: $NFT_ARQ"
  escrever /etc/systemd/system/ia-s5-nft.service 644 root:root <<UNIT
[Unit]
Description=kit s5: tabela nftables inet ia_s5 (INPUT DROP com as exceções do kit)
DefaultDependencies=no
Before=network-pre.target
Wants=network-pre.target
After=local-fs.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/nft -f ${NFT_ARQ}
ExecStop=/usr/sbin/nft delete table inet ia_s5

[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable ia-s5-nft.service
  info "CONFIRMADO: reversão cancelada; ia-s5-nft.service habilitado (a tabela volta no boot, antes da rede)"
  resumo_ok; exit 0
fi

titulo "1. regras (tabela inet ia_s5)"
regras | escrever "$NFT_NOVO" 600 root:root
aplicando && { nft -c -f "$NFT_NOVO" || falhar "nft -c reprovou o arquivo"; info "sintaxe ok (nft -c); o arquivo do boot só muda no --confirmar"; }

titulo "2. caminho de volta ANTES de fechar"
if aplicando; then
  if [ -z "$SESSAO_SSH" ]; then
    [ "$SEM_SSH" = 1 ] || falhar "sem SSH_CONNECTION: se está no console do provedor, rode com --sem-ssh-atual (e confirme depois por SSH NOVO)"
    info "console do provedor (--sem-ssh-atual)"
  else
    sessao_coberta || falhar "a sessão de onde você roda NÃO está coberta pelas regras (nem tailscale0 nem SSH_ORIGENS): eu te trancaria fora. Nada aplicado."
  fi
  tailscale status >/dev/null 2>&1 || [ "${#ssh_origens[@]}" -gt 0 ] || falhar "sem tailscale conectado e sem SSH_ORIGENS: nenhuma porta de admin sobraria"
fi

titulo "3. aplicar com janela de reversão de ${FIREWALL_JANELA_S} s"
if aplicando; then
  systemctl stop "${UNIDADE_REVERTE}.timer" 2>/dev/null || true
  systemctl reset-failed "${UNIDADE_REVERTE}.service" 2>/dev/null || true
  systemd-run --quiet --on-active="${FIREWALL_JANELA_S}" --unit="$UNIDADE_REVERTE" /usr/sbin/nft delete table inet ia_s5
  printf '%s|%s' "${SESSAO_SSH:-console}" "$(cut -d. -f1 /proc/uptime)" >"$SESSAO_ARQ"; chmod 600 "$SESSAO_ARQ"
  nft -f "$NFT_NOVO"
  info "aplicado. A tabela SOME sozinha em ${FIREWALL_JANELA_S} s se ninguém confirmar."
  cat <<TXT

   AGORA, numa janela NOVA (não nesta sessão):
     ssh ${ADMIN_USUARIO:-<admin>}@<s5 pelo tailnet> 'sudo bash $(cd "$(dirname "$0")" && pwd)/40-firewall.sh --aplicar --confirmar'
   Se a conexão nova não abrir: NÃO faça nada; em ${FIREWALL_JANELA_S} s a tabela é apagada e o acesso volta.
TXT
else
  info "[simular] systemd-run --on-active=${FIREWALL_JANELA_S} --unit=${UNIDADE_REVERTE} nft delete table inet ia_s5"
  info "[simular] nft -f ${NFT_ARQ}; depois, de OUTRA conexão: 40-firewall.sh --aplicar --confirmar"
fi
resumo_ok
