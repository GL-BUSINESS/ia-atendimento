#!/usr/bin/env bash
# 50-segredos.sh — arquivos de segredo da IA na S5, todos 0600 do uid do contêiner (G-0097), nunca em variável do compose nem na tela.
#
# Subcomandos (padrão: preparar):
#   preparar                 cria os diretórios; gera o que é INTERNO e permanente se faltar (CHAVE_H16, CHAVE_FINGERPRINT,
#                            CHAT_REF_CHAVE, API_TOKENS com as 4 origens), a chave AES do mês corrente e o tópico do ntfy.
#   instalar NOME            lê o segredo do STDIN (sem eco) e grava. NOME ∈ MODELO_API_KEY_1 (Fireworks, DEC-PIA-008),
#                            PHOENIX_API_KEY, gateway-hmac.keys, saida.json, pessoas_teste.json
#   entregar-tokens ORIGEM   escreve o token de uma origem (n8n_braco|ti|c360_api|vigia) no STDOUT só se ele NÃO for terminal
#                            (para um pipe até a S2: `... entregar-tokens n8n_braco | ssh s2 'sudo install -m 600 /dev/stdin <dest>'`)
#   mostrar-topico           mostra o tópico do ntfy SÓ num terminal (o dono assina no celular); recusa pipe e arquivo
#   conferir                 só leitura: existência, tipo, dono e modo de cada arquivo (nomes, nunca conteúdo)
#
# Uso:  sudo bash 50-segredos.sh [subcomando] [--aplicar]
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
ler_args "$@"
carregar_env
exigir IA_SEGREDOS_DIR IA_UID
exigir_root
SUB="${ARGS_RESTANTES[0]:-preparar}"; ARG1="${ARGS_RESTANTES[1]:-}"
ENV_DIR="$IA_SEGREDOS_DIR/env"; ADM=/etc/ia-s5-adm
DONO="$IA_UID:$IA_UID"
ORIGENS=(n8n_braco ti c360_api vigia)
INTERNOS=(CHAVE_H16 CHAVE_FINGERPRINT CHAT_REF_CHAVE)

# id da chave do mês em UTC: 1 = out/2026 (conversa.chave_id_do_mes)
chave_id_do_mes() { local a m; a="$(date -u +%Y)"; m="$(date -u +%-m)"; echo $(( (a - 2026) * 12 + m - 10 + 1 )); }

preparar() {
  titulo "1. diretórios: ${IA_SEGREDOS_DIR} e env/ (root:${IA_UID} 0750); ${ADM} (root 0700)"
  rodar install -d -m 750 -o root -g "$IA_UID" "$IA_SEGREDOS_DIR"
  rodar install -d -m 750 -o root -g "$IA_UID" "$ENV_DIR"
  rodar install -d -m 700 -o root -g root "$ADM"

  titulo "2. segredos internos permanentes (gerados aqui; trocar quebra dedupe/histórico: só se faltarem)"
  local n vistos=""
  for n in "${INTERNOS[@]}"; do
    if aplicando && [ -s "$ENV_DIR/$n" ]; then info "$n já existe"; continue; fi
    gerar_aleatorio 48 | escrever_segredo "$ENV_DIR/$n" "$DONO"
  done
  if aplicando; then
    vistos="$(for n in "${INTERNOS[@]}"; do sha256sum <"$ENV_DIR/$n"; done | sort | uniq -d)"
    [ -z "$vistos" ] || falhar "CHAVE_H16, CHAVE_FINGERPRINT e CHAT_REF_CHAVE precisam ser diferentes entre si"
  fi
  if aplicando && [ -s "$ENV_DIR/API_TOKENS" ]; then info "API_TOKENS já existe"
  else
    # JSON {"origem": "token"} com 4 tokens de 48 caracteres, distintos (config._tokens_por_origem)
    python3 -c 'import json, secrets, sys; print(json.dumps({o: secrets.token_urlsafe(36) for o in sys.argv[1:]}))' "${ORIGENS[@]}" |
      escrever_segredo "$ENV_DIR/API_TOKENS" "$DONO"
  fi

  titulo "3. chave AES do mês (CHAVE_AES_ID; arquivo ${IA_SEGREDOS_DIR}/chaves-aes.json, sem backup de propósito: P-R10)"
  local id="${CHAVE_AES_ID:-$(chave_id_do_mes)}" arq="$IA_SEGREDOS_DIR/chaves-aes.json"
  [[ "$id" =~ ^[0-9]+$ ]] && [ "$id" -ge 1 ] || falhar "CHAVE_AES_ID inválido"
  if aplicando; then
    python3 - "$arq" "$id" "$IA_UID" <<'PY'
import base64, json, os, sys
caminho, chave_id, uid = sys.argv[1], sys.argv[2], int(sys.argv[3])
dados = {}
if os.path.exists(caminho):
    if os.path.islink(caminho):
        sys.exit("chaves-aes.json é link simbólico: recusado")
    with open(caminho) as f:
        dados = json.load(f)
if chave_id in dados:
    print(f"   chave {chave_id} já existe (não troco)")
    sys.exit(0)
dados[chave_id] = base64.b64encode(os.urandom(32)).decode()
tmp = caminho + ".novo"
fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    json.dump(dados, f)
    f.flush()
    os.fsync(f.fileno())
os.chown(tmp, uid, uid)
os.replace(tmp, caminho)
dfd = os.open(os.path.dirname(caminho), os.O_RDONLY)
os.fsync(dfd)
os.close(dfd)
print(f"   chave {chave_id} acrescentada ({len(dados)} no arquivo)")
PY
  else info "[simular] acrescentaria a chave ${id} (32 bytes aleatórios) a $arq, 0600 ${DONO}; a virada mensal é a OPERACAO §2"; fi
  info "CHAVE_AES_ID=${id} e CHAVE_AES_ARQUIVO=${arq} vão na configuração do Coolify (não são segredo)"

  titulo "4. tópico do ntfy (DEC-PIA-010): ${ADM}/ntfy.topico (root 0600)"
  if aplicando && [ -s "$ADM/ntfy.topico" ]; then info "tópico já existe"
  else printf 'gl-ia-s5-%s\n' "$(openssl rand -hex 16)" | escrever_segredo "$ADM/ntfy.topico" root:root; fi

  titulo "5. o que o DONO entrega (por stdin, nunca no chat)"
  cat <<TXT
   sudo bash $0 instalar MODELO_API_KEY_1 --aplicar      # chave da Fireworks (conta do dono, teto mensal e aviso em 80 %)
   sudo bash $0 instalar gateway-hmac.keys --aplicar     # a mesma chave HMAC do GATEWAY_ASSINATURAS do gl-gateway
   sudo bash $0 instalar saida.json --aplicar            # {"ia_orquestrador_bearer", "chatguru_token_ia", "c360_client_id", "c360_client_secret"}
   sudo bash $0 mostrar-topico                           # assinar o tópico no app ntfy (só no terminal)
TXT
}

instalar() {
  local nome="$1" dest
  case "$nome" in
    MODELO_API_KEY_1 | PHOENIX_API_KEY) dest="$ENV_DIR/$nome" ;;
    gateway-hmac.keys | saida.json | pessoas_teste.json) dest="$IA_SEGREDOS_DIR/$nome" ;;
    *) falhar "nome fora da lista: $nome" ;;
  esac
  titulo "instalar ${nome} → ${dest}"
  if [ -t 0 ]; then echo "   cole o conteúdo e tecle Ctrl-D (não aparece na tela):" >&2; stty -echo; trap 'stty echo' EXIT; fi
  local tmp; tmp="$(mktemp)"; cat >"$tmp"
  [ ! -t 0 ] || { stty echo; echo >&2; }
  [ -s "$tmp" ] || { rm -f "$tmp"; falhar "conteúdo vazio"; }
  case "$nome" in
    MODELO_API_KEY_1) [ "$(head -1 "$tmp" | tr -d '\r\n' | wc -c)" -ge 16 ] || { rm -f "$tmp"; falhar "chave curta demais (mín. 16; o Settings recusaria)"; } ;;
    saida.json) python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert isinstance(d, dict) and d' "$tmp" 2>/dev/null \
      || { rm -f "$tmp"; falhar "saida.json não é um objeto JSON"; } ;;
    gateway-hmac.keys) [ "$(grep -c . "$tmp")" -le 2 ] || { rm -f "$tmp"; falhar "no máximo 2 chaves (uma por linha; 2 só na virada)"; } ;;
  esac
  escrever_segredo "$dest" "$DONO" <"$tmp"; rm -f "$tmp"
}

entregar_tokens() {
  local origem="$1"
  [[ " ${ORIGENS[*]} " == *" $origem "* ]] || falhar "origem fora de: ${ORIGENS[*]}"
  [ ! -t 1 ] || falhar "recuso escrever token num terminal: use um pipe até o destino"
  python3 -c 'import json,sys; sys.stdout.write(json.load(open(sys.argv[1]))[sys.argv[2]])' "$ENV_DIR/API_TOKENS" "$origem"
}

mostrar_topico() {
  [ -t 1 ] || falhar "o tópico só aparece num terminal (nada de pipe/arquivo/log)"
  printf 'tópico: %s/%s\n' "${NTFY_URL_BASE:-https://ntfy.sh}" "$(cat "$ADM/ntfy.topico")"
}

conferir() {
  titulo "conferir (só leitura; nomes e modos, nunca conteúdo)"
  local falhou=0 f esperado
  conf() {  # conf <arquivo> <modo dono esperado> <obrigatório 1|0>
    if [ ! -e "$1" ]; then [ "$3" = 1 ] && { echo "FALHOU  ausente: $1"; falhou=1; } || echo "PULOU   opcional ausente: $1"; return; fi
    [ ! -L "$1" ] || { echo "FALHOU  link simbólico: $1"; falhou=1; return; }
    [ "$(stat -c '%a %u' "$1")" = "$2" ] && echo "PASSOU  $1 ($2)" || { echo "FALHOU  $1: $(stat -c '%a %u' "$1"), esperado $2"; falhou=1; }
  }
  conf "$IA_SEGREDOS_DIR" "750 0" 1
  conf "$ENV_DIR" "750 0" 1
  for f in DATABASE_URL MODELO_API_KEY_1 API_TOKENS CHAVE_H16 CHAVE_FINGERPRINT CHAT_REF_CHAVE; do conf "$ENV_DIR/$f" "600 $IA_UID" 1; done
  conf "$ENV_DIR/PHOENIX_API_KEY" "600 $IA_UID" 0
  for f in chaves-aes.json gateway-hmac.keys saida.json; do conf "$IA_SEGREDOS_DIR/$f" "600 $IA_UID" 1; done
  conf "$IA_SEGREDOS_DIR/pessoas_teste.json" "600 $IA_UID" 0
  conf "$ADM" "700 0" 1
  conf "$ADM/ntfy.topico" "600 0" 1
  [ "$falhou" = 0 ] || falhar "há FALHOU acima"
}

case "$SUB" in
  preparar) preparar; resumo_ok ;;
  instalar) [ -n "$ARG1" ] || falhar "instalar NOME"; aplicando || falhar "instalar precisa de --aplicar (lê do stdin)"; instalar "$ARG1" ;;
  entregar-tokens) entregar_tokens "$ARG1" ;;
  mostrar-topico) mostrar_topico ;;
  conferir) conferir ;;
  *) falhar "subcomando desconhecido: $SUB" ;;
esac
