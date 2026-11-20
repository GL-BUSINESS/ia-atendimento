#!/usr/bin/env bash
# 10-endurecer.sh — usuário de admin, SSH só por chave, atualizações automáticas de segurança, relógio (UTC + NTP), journald com teto,
# sysctl de rede básico, pacotes do kit e Tailscale (admin plane). Não mexe em firewall (40) nem em Docker (20).
#
# Uso:  sudo bash 10-endurecer.sh [--aplicar] [--env /etc/ia-s5-adm/s5.env]
# Caminho de volta: SSH por senha só é desligado DEPOIS de conferir que o usuário de admin tem chave autorizada (senão para).
# Desfazer: apagar /etc/ssh/sshd_config.d/10-ia-s5.conf e `systemctl reload ssh`; o resto é aditivo.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
ler_args "$@"
carregar_env
exigir ADMIN_USUARIO ADMIN_CHAVES_ARQUIVO
exigir_root
[[ "$ADMIN_USUARIO" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] || falhar "ADMIN_USUARIO inválido"

titulo "1. pacotes base do kit"
rodar_022 env DEBIAN_FRONTEND=noninteractive apt-get update -q
apt_instalar ca-certificates curl gnupg jq openssl nftables wireguard-tools unattended-upgrades apt-listchanges rsync age python3 sudo

titulo "2. usuário de admin ${ADMIN_USUARIO} com chave"
[ -f "$ADMIN_CHAVES_ARQUIVO" ] || { aplicando && falhar "arquivo de chaves públicas ausente: $ADMIN_CHAVES_ARQUIVO"; }
if [ -f "$ADMIN_CHAVES_ARQUIVO" ]; then
  n=0
  while IFS= read -r chave || [ -n "$chave" ]; do
    [[ "$chave" =~ ^[[:space:]]*(#|$) ]] && continue
    printf '%s\n' "$chave" | ssh-keygen -l -f /dev/stdin >/dev/null 2>&1 || falhar "linha de $ADMIN_CHAVES_ARQUIVO não é chave pública ssh"
    n=$((n + 1))
  done <"$ADMIN_CHAVES_ARQUIVO"
  [ "$n" -ge 1 ] || falhar "nenhuma chave pública em $ADMIN_CHAVES_ARQUIVO: desligar a senha te deixaria fora"
  info "$n chave(s) pública(s) válidas"
fi
if id "$ADMIN_USUARIO" >/dev/null 2>&1; then info "usuário já existe"; else rodar useradd -m -s /bin/bash -G sudo "$ADMIN_USUARIO"; fi
rodar usermod -aG sudo "$ADMIN_USUARIO"
casa="$(getent passwd "$ADMIN_USUARIO" | cut -d: -f6 || true)"; casa="${casa:-/home/$ADMIN_USUARIO}"
rodar install -d -m 700 -o "$ADMIN_USUARIO" -g "$ADMIN_USUARIO" "$casa/.ssh"
if [ -f "$ADMIN_CHAVES_ARQUIVO" ]; then
  grep -Ev '^[[:space:]]*(#|$)' "$ADMIN_CHAVES_ARQUIVO" | escrever "$casa/.ssh/authorized_keys" 600 "$ADMIN_USUARIO:$ADMIN_USUARIO"
fi
# sudo sem senha para o admin (as contas não têm senha; o kit roda por sudo -n)
printf '%s ALL=(ALL) NOPASSWD:ALL\n' "$ADMIN_USUARIO" | escrever "/etc/sudoers.d/90-ia-s5-admin" 440 root:root
aplicando && { visudo -cf /etc/sudoers.d/90-ia-s5-admin >/dev/null || { rm -f /etc/sudoers.d/90-ia-s5-admin; falhar "sudoers inválido; removido"; }; }

titulo "3. SSH só por chave"
escrever /etc/ssh/sshd_config.d/10-ia-s5.conf 644 root:root <<'CONF'
# kit s5 (10-endurecer.sh): só chave; root só por chave (o Coolify da S2 pode precisar); sem encaminhamento gráfico
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitRootLogin prohibit-password
PermitEmptyPasswords no
MaxAuthTries 3
LoginGraceTime 30
X11Forwarding no
AllowAgentForwarding no
CONF
if aplicando; then
  [ -s "$casa/.ssh/authorized_keys" ] || falhar "authorized_keys do ${ADMIN_USUARIO} vazio: não recarrego o sshd"
  sshd -t || { rm -f /etc/ssh/sshd_config.d/10-ia-s5.conf; falhar "sshd -t reprovou; drop-in removido"; }
  systemctl reload ssh 2>/dev/null || systemctl reload sshd
  [ "$(sshd -T 2>/dev/null | awk '/^passwordauthentication /{print $2}')" = "no" ] || falhar "sshd ainda aceita senha (outro arquivo vence?)"
  info "sshd recarregado; senha desligada. PROVE AGORA de outra janela: ssh ${ADMIN_USUARIO}@<s5> true"
fi

titulo "4. atualizações automáticas (só segurança, sem reinício automático)"
escrever /etc/apt/apt.conf.d/52ia-s5-unattended 644 root:root <<'CONF'
// kit s5: só a origem de segurança da distribuição; reinício é do dono, na janela (o kernel novo fica pendente)
Unattended-Upgrade::Allowed-Origins { "${distro_id}:${distro_codename}-security"; "${distro_id}ESMApps:${distro_codename}-apps-security"; "${distro_id}ESM:${distro_codename}-infra-security"; };
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Package-Blacklist { "docker-ce"; "docker-ce-cli"; "containerd.io"; "postgresql-"; "wireguard"; };
CONF
escrever /etc/apt/apt.conf.d/20auto-upgrades 644 root:root <<'CONF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
CONF
rodar systemctl enable --now unattended-upgrades

titulo "5. relógio: UTC e NTP"
rodar timedatectl set-timezone UTC
if systemd-detect-virt --container >/dev/null 2>&1; then
  aviso "rodando em contêiner ($(systemd-detect-virt --container)): o relógio é do hospedeiro; NTP não se liga aqui"
else
  rodar timedatectl set-ntp true
fi

titulo "6. journald com teto e sysctl de rede"
escrever /etc/systemd/journald.conf.d/ia-s5.conf 644 root:root <<'CONF'
[Journal]
SystemMaxUse=1G
CONF
escrever /etc/sysctl.d/60-ia-s5.conf 644 root:root <<'CONF'
# kit s5: sem redirecionamento ICMP nem rota de origem; filtro de caminho reverso frouxo (o wg0 e o tailscale0 têm rotas próprias)
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.all.rp_filter = 2
net.ipv4.tcp_syncookies = 1
CONF
rodar systemctl restart systemd-journald
rodar sysctl --system -q

titulo "7. Tailscale (SSH de admin e acesso ao registro da S3)"
if command -v tailscale >/dev/null 2>&1; then info "tailscale já instalado"; else
  codinome="$(. /etc/os-release && echo "${VERSION_CODENAME:-noble}")"
  rodar install -d -m 755 /usr/share/keyrings
  rodar_022 sh -c "curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/${codinome}.noarmor.gpg -o /usr/share/keyrings/tailscale-archive-keyring.gpg && chmod 644 /usr/share/keyrings/tailscale-archive-keyring.gpg"
  printf 'deb [signed-by=/usr/share/keyrings/tailscale-archive-keyring.gpg] https://pkgs.tailscale.com/stable/ubuntu %s main\n' "$codinome" |
    escrever /etc/apt/sources.list.d/tailscale.list 644 root:root
  rodar_022 env DEBIAN_FRONTEND=noninteractive apt-get update -q
  apt_instalar tailscale
fi
if aplicando && tailscale status >/dev/null 2>&1; then info "tailscale conectado"
elif [ -f "${TAILSCALE_AUTHKEY_ARQUIVO:-/nonexistent}" ]; then
  # a chave vai por arquivo (o tailscale lê `file:`), nunca na linha de comando
  rodar tailscale up --ssh=false --auth-key="file:${TAILSCALE_AUTHKEY_ARQUIVO}" --hostname=s5
else
  aviso "tailscale sem login: o DONO roda 'sudo tailscale up --ssh=false --hostname=s5' e aprova o nó (o firewall do passo 40 exige tailscale0 ou SSH_ORIGENS)"
fi

resumo_ok
