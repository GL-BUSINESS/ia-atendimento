#!/usr/bin/env bash
# lib.sh — base comum do kit da S5. Só é lido com `source`; não contém segredo.
#
# Contrato de todo script do kit:
#   - padrão = SIMULAR: imprime o que faria e não muda nada. `--aplicar` faz de verdade (como root, na S5, com o «sim» do dono).
#   - para no primeiro erro (set -euo pipefail + trap), dizendo a linha; rodar de novo é seguro (idempotente).
#   - nunca imprime segredo: segredo só entra por arquivo ou stdin e só sai para arquivo 0600. Nenhum segredo vira argumento de comando.
#   - configuração em s5.env (só NOMES e valores não secretos), lida por um parser que aceita apenas linhas NOME=valor literais.
set -euo pipefail
umask 077

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODO="simular"
S5_ENV="${S5_ENV:-}"
ARGS_RESTANTES=()
TEMPORARIOS=()
trap 'for _t in "${TEMPORARIOS[@]:-}"; do [ -z "$_t" ] || rm -f "$_t"; done' EXIT
trap 'exit 130' INT TERM

trap 's=$?; echo "!! $(basename "$0"): parou na linha $LINENO (código $s). Nada além do que já foi impresso mudou; corrija e rode de novo." >&2' ERR

ler_args() {  # ler_args "$@" — trata --aplicar/--simular/--env; o resto fica em ARGS_RESTANTES
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --aplicar) MODO="aplicar" ;;
      --simular) MODO="simular" ;;
      --env) shift; S5_ENV="${1:?--env pede um arquivo}" ;;
      -h | --help) sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; exit 0 ;;
      *) ARGS_RESTANTES+=("$1") ;;
    esac
    shift
  done
}

aplicando() { [ "$MODO" = "aplicar" ]; }
titulo() { printf '\n== %s  [%s]\n' "$*" "$MODO"; }
info() { printf '   %s\n' "$*"; }
aviso() { printf '   AVISO: %s\n' "$*" >&2; }
falhar() { echo "!! $(basename "$0"): $*" >&2; exit 1; }

# carrega s5.env sem `source`: só linhas NOME=valor, valor sem $, `, ;, | ou &. Arquivo tem de ser do root (ou do usuário) e não gravável por outros.
carregar_env() {
  local arq="${S5_ENV:-}" linha nome valor
  if [ -z "$arq" ]; then
    for c in /etc/ia-s5-adm/s5.env "$KIT_DIR/s5.env"; do [ -f "$c" ] && { arq="$c"; break; }; done
  fi
  [ -n "$arq" ] && [ -f "$arq" ] || falhar "s5.env não encontrado (copie s5.env.exemplo para /etc/ia-s5-adm/s5.env ou use --env ARQ)"
  [ ! -L "$arq" ] || falhar "s5.env não pode ser link simbólico"
  case "$(stat -c '%a' "$arq")" in *[2367]) falhar "s5.env gravável por outros: chmod 600" ;; esac
  case "$(stat -c '%a' "$arq")" in ?[2367]?) falhar "s5.env gravável pelo grupo: chmod 600" ;; esac
  while IFS= read -r linha || [ -n "$linha" ]; do
    linha="${linha%%$'\r'}"
    [[ "$linha" =~ ^[[:space:]]*(#|$) ]] && continue
    [[ "$linha" =~ ^([A-Z][A-Z0-9_]*)=(.*)$ ]] || falhar "s5.env: linha fora do formato NOME=valor: ${linha%%=*}"
    nome="${BASH_REMATCH[1]}"; valor="${BASH_REMATCH[2]}"
    valor="${valor#\"}"; valor="${valor%\"}"
    [[ "$valor" =~ [\$\`\;\|\&\<\>] ]] && falhar "s5.env: ${nome} com caractere proibido"
    if [ -z "${!nome+x}" ]; then printf -v "$nome" '%s' "$valor"; export "${nome?}"; fi
  done <"$arq"
  S5_ENV_CARREGADO="$arq"
}

exigir() {  # exigir NOME... — para se alguma variável estiver vazia
  local n faltam=()
  for n in "$@"; do [ -n "${!n:-}" ] || faltam+=("$n"); done
  [ "${#faltam[@]}" -eq 0 ] || falhar "faltam no s5.env: ${faltam[*]}"
}

exigir_root() { aplicando || return 0; [ "$(id -u)" = 0 ] || falhar "precisa de root na S5 (sudo bash $0 --aplicar)"; }

validar_ipv4() { [[ "$1" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || falhar "$2 não é IPv4: $1"; }
validar_porta() { [[ "$1" =~ ^[0-9]{1,5}$ ]] && [ "$1" -ge 1 ] && [ "$1" -le 65535 ] || falhar "$2 não é porta: $1"; }
validar_banco_local() { case "${BANCO_LOCAL:-}" in s5 | s4) ;; *) falhar "BANCO_LOCAL deve ser s5 ou s4 (decisão do dono, DEC-PIA-009)" ;; esac; }

# rodar CMD... — executa no modo aplicar; no simular só mostra. NUNCA passe segredo como argumento.
rodar() {
  if aplicando; then "$@"; else printf '   [simular] %s\n' "$(printf '%q ' "$@")"; fi
}

# escrever DEST MODO DONO:GRUPO < conteúdo — conteúdo NÃO secreto (é mostrado no simular); atômico; só troca se mudou
escrever() {
  local dest="$1" modo="$2" dono="$3" tmp
  tmp="$(mktemp)"; TEMPORARIOS+=("$tmp"); cat >"$tmp"
  if ! aplicando; then
    printf '   [simular] escreveria %s (%s %s, %s linhas):\n' "$dest" "$modo" "$dono" "$(wc -l <"$tmp")"
    sed 's/^/      | /' "$tmp"; rm -f "$tmp"; return 0
  fi
  [ -d "$(dirname "$dest")" ] || install -d -m 755 "$(dirname "$dest")"   # nunca muda o modo de diretório existente
  if [ -f "$dest" ] && cmp -s "$tmp" "$dest"; then
    chmod "$modo" "$dest"; chown "$dono" "$dest"; rm -f "$tmp"; info "$dest já estava igual"; return 0
  fi
  [ ! -f "$dest" ] || cp -p "$dest" "$dest.bak-ia-$(date -u +%Y%m%d%H%M%S)"
  install -m "$modo" -o "${dono%%:*}" -g "${dono##*:}" "$tmp" "$dest"; rm -f "$tmp"
  info "$dest gravado ($modo $dono)"
}

# escrever_segredo DEST DONO:GRUPO < segredo — 0600, nunca mostrado, nunca em argumento; recusa vazio
escrever_segredo() {
  local dest="$1" dono="$2" tmp
  if ! aplicando; then cat >/dev/null; printf '   [simular] gravaria o segredo em %s (0600 %s; conteúdo não exibido)\n' "$dest" "$dono"; return 0; fi
  [ -d "$(dirname "$dest")" ] || install -d -m 750 "$(dirname "$dest")"
  # temporário NO diretório de destino (nunca em /tmp) e apagado em qualquer saída (erro, Ctrl-C)
  tmp="$(mktemp "$(dirname "$dest")/.ia-novo.XXXXXX")"; TEMPORARIOS+=("$tmp"); cat >"$tmp"
  [ -s "$tmp" ] || { rm -f "$tmp"; falhar "segredo vazio para $(basename "$dest")"; }
  install -m 600 -o "${dono%%:*}" -g "${dono##*:}" "$tmp" "$dest"; rm -f "$tmp"
  info "$(basename "$dest"): gravado (0600 $dono)"
}

# SSH_CONNECTION da sessão de quem chamou. O `sudo` apaga essa variável (env_reset), então sobe pelos processos ancestrais até achá-la
# em /proc/<pid>/environ (root lê). Vazio = não há sessão SSH na cadeia (console do provedor).
# Imprime "<SSH_CONNECTION>|<início do processo da sessão, em segundos desde o boot>".
ssh_connection_da_sessao() {
  local pid="$$" i v tck
  tck="$(getconf CLK_TCK)"
  for i in $(seq 1 16); do
    v="$(tr '\0' '\n' <"/proc/$pid/environ" 2>/dev/null | sed -n 's/^SSH_CONNECTION=//p' | head -1)"
    if [ -n "$v" ]; then
      # o processo mais alto da cadeia que ainda tem SSH_CONNECTION é o shell da sessão: sobe enquanto o pai também tiver
      local pai
      while pai="$(awk '/^PPid:/{print $2}' "/proc/$pid/status" 2>/dev/null)" && [ -n "$pai" ] && [ "$pai" -gt 1 ] \
            && tr '\0' '\n' <"/proc/$pai/environ" 2>/dev/null | grep -qx "SSH_CONNECTION=$v"; do pid="$pai"; done
      printf '%s|%s' "$v" "$(( $(awk '{print $22}' "/proc/$pid/stat") / tck ))"; return 0
    fi
    pid="$(awk '/^PPid:/{print $2}' "/proc/$pid/status" 2>/dev/null)"
    [ -n "$pid" ] && [ "$pid" -gt 1 ] || return 0
  done
}

gerar_aleatorio() { openssl rand -base64 48 | tr -d '/+=\n' | cut -c1-"${1:-48}"; }

# drop-in systemd: o serviço só sobe depois do wg0 (memória s4-pg-antes-do-wg0: bind no IP do túnel falha se subir antes)
dropin_apos_wg0() {  # dropin_apos_wg0 <unidade>
  local wg="wg-quick@wg0"
  printf '[Unit]\nWants=%s.service\nAfter=%s.service\n' "$wg" "$wg" |
    escrever "/etc/systemd/system/$1.d/apos-wg0.conf" 644 root:root
}

# rodar com umask 022: pacote, repositório e chave de repositório precisam ser legíveis pelo usuário _apt e pelos serviços
# (com o umask 077 do kit a chave do apt sai 0600 e o apt diz «not signed»: achado do ensaio de 20/11)
rodar_022() { if aplicando; then (umask 022; "$@"); else rodar "$@"; fi; }

apt_instalar() {  # apt_instalar pacote... — só os que faltam
  local falta=() p
  for p in "$@"; do dpkg -s "$p" >/dev/null 2>&1 || falta+=("$p"); done
  [ "${#falta[@]}" -gt 0 ] || { info "pacotes já instalados: $*"; return 0; }
  rodar_022 env DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends "${falta[@]}"
}

resumo_ok() { printf '\n== %s: concluído no modo %s\n' "$(basename "$0")" "$MODO"; aplicando || echo "   (nada mudou; repita com --aplicar depois do «sim» do dono)"; }
