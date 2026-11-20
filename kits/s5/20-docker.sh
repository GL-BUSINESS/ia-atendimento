#!/usr/bin/env bash
# 20-docker.sh — Docker CE do repositório oficial, daemon com teto de log e live-restore, Docker só depois do wg0, e login no registro
# de imagens da S3 (as imagens de produção vêm de lá; o Coolify da S2 só puxa).
#
# Uso:  sudo bash 20-docker.sh [--aplicar]
# Segredo: a senha de LEITURA do registro fica em /etc/ia-s5-adm/registro.senha (root, 0600) e vai ao `docker login` por stdin.
#          O Docker a guarda em /root/.docker/config.json (0600, base64: não é cifra). Depois do login o arquivo .senha pode ser apagado.
# Desfazer: `apt-get purge docker-ce docker-ce-cli containerd.io` e apagar /etc/docker/daemon.json e o drop-in.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
ler_args "$@"
carregar_env
exigir IA_REGISTRO_IMAGEM REGISTRO_USUARIO
exigir_root
[[ "$IA_REGISTRO_IMAGEM" =~ ^[A-Za-z0-9.-]+(:[0-9]{1,5})?$ ]] || falhar "IA_REGISTRO_IMAGEM deve ser host[:porta]"
SENHA_REGISTRO=/etc/ia-s5-adm/registro.senha

titulo "1. Docker CE (repositório oficial)"
if command -v dockerd >/dev/null 2>&1; then info "docker já instalado: $(docker --version 2>/dev/null || true)"; else
  codinome="$(. /etc/os-release && echo "${VERSION_CODENAME:-noble}")"
  rodar install -d -m 755 /etc/apt/keyrings
  rodar_022 sh -c "curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc && chmod a+r /etc/apt/keyrings/docker.asc"
  printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu %s stable\n' \
    "$(dpkg --print-architecture)" "$codinome" | escrever /etc/apt/sources.list.d/docker.list 644 root:root
  rodar_022 env DEBIAN_FRONTEND=noninteractive apt-get update -q
  apt_instalar docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

titulo "2. daemon: teto de log, live-restore (reiniciar o dockerd não derruba os contêineres)"
escrever /etc/docker/daemon.json 644 root:root <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" },
  "live-restore": true
}
JSON

titulo "3. Docker só depois do wg0 (o orquestrador escuta no IP do túnel)"
dropin_apos_wg0 docker.service
rodar systemctl daemon-reload
rodar systemctl enable docker
rodar systemctl restart docker

titulo "4. login no registro ${IA_REGISTRO_IMAGEM} (usuário de leitura)"
if aplicando; then
  [ -f "$SENHA_REGISTRO" ] || falhar "falta $SENHA_REGISTRO (o dono grava: sudo install -m 600 /dev/stdin $SENHA_REGISTRO, cola a senha, Ctrl-D)"
  [ "$(stat -c '%a %u' "$SENHA_REGISTRO")" = "600 0" ] || falhar "$SENHA_REGISTRO tem de ser 0600 do root"
  docker login "$IA_REGISTRO_IMAGEM" -u "$REGISTRO_USUARIO" --password-stdin <"$SENHA_REGISTRO" >/dev/null
  info "login ok (credencial em /root/.docker/config.json, 0600)"
  chmod 600 /root/.docker/config.json
else
  info "[simular] docker login ${IA_REGISTRO_IMAGEM} -u ${REGISTRO_USUARIO} --password-stdin < ${SENHA_REGISTRO}"
fi

titulo "5. prova"
rodar docker info --format '{{.ServerVersion}} live-restore={{.LiveRestoreEnabled}}'
resumo_ok
