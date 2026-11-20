#!/usr/bin/env bash
# Deploy MANUAL do orquestrador na S5 por TAG (PD-3). Sem `--executar` só IMPRIME o que faria (kit: nada é chamado).
#
# Uso:  bash scripts/deploy-s5.sh vX.Y.Z [--executar] [--primeiro]
#   --executar  faz de verdade (pede o «sim» do dono antes; ver docs/DEPLOY.md)
#   --primeiro  primeiro deploy: aceita /healthz fora do ar ANTES (ainda não há nada rodando) e não faz rollback sem tag anterior
#
# Variáveis (só NOMES; os valores vêm do ambiente da sessão, nunca de arquivo do repo):
#   S5_SSH             usuario@host da S5 (ssh de admin, chave; pelo tailnet)
#   COOLIFY_URL        URL do Coolify da S2 (ele gerencia a S5 como servidor remoto)
#   COOLIFY_TOKEN      token da API do Coolify (vai por stdin ao curl, nunca em argumento)
#   COOLIFY_APP_UUID   uuid da aplicação dockercompose do ia-atendimento no Coolify
#   HEALTHZ_URL        OBRIGATÓRIA, ex.: http://<IA_BIND_IP>:<IA_PORTA>/healthz (conferida DENTRO da S5, por ssh: só o wg0 alcança)
#   DIAS_PILOTO_ARQUIVO  padrão config/dias-piloto.txt. Ausente ou sem nenhuma data = RECUSA (falha fechado, G-0096)
#   ESPERA_S, HEALTH_TENTATIVAS  pausa e tentativas do /healthz
#   Só com DEPLOY_TESTE=1 (testes): DEPLOY_AGORA ("AAAA-MM-DD HH:MM" BRT) e SHA_ESPERADO (sha40 da tag)
#
# O que conta como «no ar» (G-0095): o Coolify ACEITOU gravar a tag (curl --fail-with-body), a IMAGE_TAG relida é a nova, o deployment
# terminou «finished» e o /healthz responde 200 com `version` = X.Y.Z da tag e `git_sha` = o commit da tag. Qualquer um falhou ⇒ não é OK.
#
# Códigos de saída: 0 ok · 2 uso/variável faltando · 3 hora ou dia de piloto · 4 portão da S5 (disco/carga) ·
#                   5 /healthz fora do ar antes · 6 deploy falhou e voltou à tag anterior · 7 deploy falhou e o rollback também ·
#                   8 o Coolify recusou gravar a tag (nada foi implantado)
set -euo pipefail
cd "$(dirname "$0")/.."

DISCO_MIN_LIVRE_PCT=15      # PD-3: ≥ 15% livre
CARGA_MAX=6                 # PD-3: uptime < 6 (média de 1 min)
JANELA_1_INI=$((12 * 60 + 30)); JANELA_1_FIM=$((14 * 60)); JANELA_2_INI=$((20 * 60 + 30))   # 12:30–14:00 ou depois das 20:30 (BRT)
ESPERA_S="${ESPERA_S:-5}"
HEALTH_TENTATIVAS="${HEALTH_TENTATIVAS:-24}"
DIAS_PILOTO_ARQUIVO="${DIAS_PILOTO_ARQUIVO:-config/dias-piloto.txt}"
HEALTHZ_URL="${HEALTHZ_URL:-}"
PADRAO_HEALTHZ='^http://[A-Za-z0-9.-]+(:[0-9]{1,5})?/healthz$'

executar=0; primeiro=0; tag=""
for arg in "$@"; do
  case "$arg" in
    --executar) executar=1 ;;
    --primeiro) primeiro=1 ;;
    -*) echo "opção desconhecida: $arg" >&2; exit 2 ;;
    *) [ -z "$tag" ] || { echo "só uma tag" >&2; exit 2; }; tag="$arg" ;;
  esac
done
[[ "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "uso: bash scripts/deploy-s5.sh vX.Y.Z [--executar] [--primeiro]   (tag semver; nunca branch, sha ou latest)" >&2; exit 2; }
versao="${tag#v}"

falha() { local codigo="$1"; shift; echo "deploy-s5: $*" >&2; exit "$codigo"; }

if [ "${DEPLOY_TESTE:-0}" != 1 ]; then
  [ -z "${DEPLOY_AGORA:-}" ] && [ -z "${SHA_ESPERADO:-}" ] || falha 2 "DEPLOY_AGORA e SHA_ESPERADO só valem com DEPLOY_TESTE=1 (testes)"
fi

agora_brt() { if [ -n "${DEPLOY_AGORA:-}" ]; then echo "$DEPLOY_AGORA"; else TZ=America/Sao_Paulo date +'%Y-%m-%d %H:%M'; fi; }

dias_de_piloto() { grep -v '^[[:space:]]*#' "$DIAS_PILOTO_ARQUIVO" | tr -d ' \r' | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' || true; }

# devolve 0 se pode; senão imprime o motivo em stdout e devolve 1
hora_e_dia_ok() {
  local agora dia hhmm minutos
  agora="$(agora_brt)"; dia="${agora% *}"; hhmm="${agora#* }"
  minutos=$((10#${hhmm%:*} * 60 + 10#${hhmm#*:}))
  if ! { [ "$minutos" -ge "$JANELA_1_INI" ] && [ "$minutos" -le "$JANELA_1_FIM" ]; } && ! [ "$minutos" -gt "$JANELA_2_INI" ]; then
    echo "fora da janela de deploy (agora ${hhmm} BRT; vale 12:30–14:00 ou depois das 20:30, nunca 09–12 h de pico)"; return 1
  fi
  if [ ! -f "$DIAS_PILOTO_ARQUIVO" ] || [ -z "$(dias_de_piloto)" ]; then
    echo "${DIAS_PILOTO_ARQUIVO} ausente ou sem nenhuma data: sem a lista de dias de piloto nenhum deploy (falha fechado)"; return 1
  fi
  if dias_de_piloto | grep -qx "$dia"; then
    echo "${dia} é dia de piloto (${DIAS_PILOTO_ARQUIVO}): nenhum deploy"; return 1
  fi
  return 0
}

if [ "$executar" -eq 0 ]; then
  motivo="$(hora_e_dia_ok)" && estado="OK agora" || estado="BLOQUEADA agora: ${motivo}"
  cat <<TXT
== deploy-s5.sh ${tag}  (SIMULAÇÃO: nada foi chamado; use --executar com o «sim» do dono)
 0. janela/dia de piloto (local, BRT) ........ ${estado}
 1. portão NA S5 (ssh \$S5_SSH): disco livre ≥ ${DISCO_MIN_LIVRE_PCT}% em / e carga (loadavg 1 min) < ${CARGA_MAX}; reprovou = para (código 4)
 2. \$HEALTHZ_URL na S5 (antes) ... precisa dar 200 (código 5; --primeiro dispensa)
 3. ler IMAGE_TAG atual no Coolify (GET /api/v1/applications/\$COOLIFY_APP_UUID/envs) = tag do rollback
 4. gravar IMAGE_TAG=${tag} (PATCH .../envs, curl --fail-with-body) e RELER: tem que voltar ${tag} (senão código 8, nada implantado)
 5. disparar o deploy (POST /api/v1/deploy?uuid=\$COOLIFY_APP_UUID&force=true) e esperar "finished"
 6. \$HEALTHZ_URL na S5 (depois), até ${HEALTH_TENTATIVAS} tentativas: 200 E version=${versao} E git_sha = commit da tag ${tag}
 7. falhou em 5 ou 6: gravar IMAGE_TAG=<tag anterior>, novo deploy, mesmo /healthz com a versão anterior (código 6; se falhar, 7)
Rollback manual: bash scripts/deploy-s5.sh <tag anterior> --executar   (a hora/portão valem também para ele)
Variáveis: S5_SSH COOLIFY_URL COOLIFY_TOKEN COOLIFY_APP_UUID HEALTHZ_URL (valores nunca impressos)
TXT
  exit 0
fi

for var in S5_SSH COOLIFY_URL COOLIFY_TOKEN COOLIFY_APP_UUID HEALTHZ_URL; do
  [ -n "${!var:-}" ] || falha 2 "variável ${var} não definida"
done
[[ "$HEALTHZ_URL" =~ $PADRAO_HEALTHZ ]] || falha 2 "HEALTHZ_URL fora do formato http://host[:porta]/healthz"
[[ "$COOLIFY_URL" =~ ^https:// ]] || falha 2 "COOLIFY_URL precisa ser https:// (o token vai no cabeçalho)"
[[ "$COOLIFY_APP_UUID" =~ ^[A-Za-z0-9-]{8,64}$ ]] || falha 2 "COOLIFY_APP_UUID fora do formato"
[[ "$S5_SSH" != -* ]] || falha 2 "S5_SSH não pode começar com '-'"

sha_da_tag() {  # sha40 do commit da tag, do git local (git fetch --tags antes); vazio se não existir
  if [ "${DEPLOY_TESTE:-0}" = 1 ] && [ -n "${SHA_ESPERADO:-}" ]; then echo "$SHA_ESPERADO"; return 0; fi
  git rev-parse -q --verify "refs/tags/$1^{commit}" 2>/dev/null || true
}
sha_novo="$(sha_da_tag "$tag")"
[[ "$sha_novo" =~ ^[0-9a-f]{40}$ ]] || falha 2 "a tag ${tag} não existe no git local (git fetch --tags): sem ela não há git_sha a conferir"

motivo="$(hora_e_dia_ok)" || falha 3 "$motivo"

s5() { ssh -o BatchMode=yes -o ConnectTimeout=10 "$S5_SSH" "$1"; }

# o token vai por stdin (curl -K -), não aparece em `ps` nem em log. --fail-with-body: 4xx/5xx viram código de saída != 0
coolify() {  # coolify METODO CAMINHO [json]
  local metodo="$1" caminho="$2" corpo="${3:-}" args=()
  [ -z "$corpo" ] || args=(-d "$corpo")
  printf 'header = "Authorization: Bearer %s"\nheader = "Content-Type: application/json"\n' "$COOLIFY_TOKEN" \
    | curl -sS --fail-with-body --max-time 60 -K - -X "$metodo" "${args[@]}" "${COOLIFY_URL%/}${caminho}"
}

# imprime "<código> <version> <git_sha>" do /healthz da S5 (código 000 se não respondeu)
healthz() {
  local saida corpo codigo
  saida="$(s5 "curl -s --max-time 5 -w '\n%{http_code}' $(printf '%q' "$HEALTHZ_URL")" 2>/dev/null || true)"
  codigo="$(printf '%s\n' "$saida" | tail -n1 | tr -dc '0-9')"
  corpo="$(printf '%s\n' "$saida" | sed '$d')"
  printf '%s %s %s\n' "${codigo:-000}" \
    "$(printf '%s' "$corpo" | jq -r '.version // "-"' 2>/dev/null || echo -)" \
    "$(printf '%s' "$corpo" | jq -r '.git_sha // "-"' 2>/dev/null || echo -)"
}

espera_healthz() {  # espera_healthz TENTATIVAS VERSAO SHA — 0 só com 200 E a versão E o sha esperados (SHA '*' = não confere o sha)
  local i cod ver sha
  for i in $(seq 1 "$1"); do
    read -r cod ver sha <<<"$(healthz)"
    if [ "$cod" = "200" ] && [ "$ver" = "$2" ] && { [ "$3" = "*" ] || [ "$sha" = "$3" ]; }; then return 0; fi
    [ "$cod" != "200" ] || echo "   /healthz 200 mas version=${ver} git_sha=${sha:0:12} (esperado ${2} ${3:0:12})" >&2
    sleep "$ESPERA_S"
  done
  return 1
}

tag_no_coolify() {
  coolify GET "/api/v1/applications/${COOLIFY_APP_UUID}/envs" | jq -r '[.[]? | select(.key=="IMAGE_TAG") | .value][0] // ""'
}

grava_tag() {  # grava e RELÊ; 1 se o Coolify recusou ou a releitura não bate
  local relida
  coolify PATCH "/api/v1/applications/${COOLIFY_APP_UUID}/envs" \
    "$(jq -nc --arg v "$1" '{key:"IMAGE_TAG",value:$v,is_preview:false,is_buildtime:false,is_runtime:true}')" >/dev/null \
    || { echo "deploy-s5: o Coolify recusou gravar IMAGE_TAG=$1" >&2; return 1; }
  relida="$(tag_no_coolify)" || { echo "deploy-s5: não consegui reler IMAGE_TAG" >&2; return 1; }
  [ "$relida" = "$1" ] || { echo "deploy-s5: IMAGE_TAG relida é '${relida}', não '$1'" >&2; return 1; }
}

dispara_e_espera() {
  local resposta dep status i
  resposta="$(coolify POST "/api/v1/deploy?uuid=${COOLIFY_APP_UUID}&force=true")" || { echo "deploy-s5: o Coolify recusou o deploy" >&2; return 1; }
  dep="$(printf '%s' "$resposta" | jq -r '.deployments[0].deployment_uuid // ""' 2>/dev/null || true)"
  [ -n "$dep" ] || { echo "deploy-s5: o Coolify não enfileirou o deploy" >&2; return 1; }
  for i in $(seq 1 90); do
    status="$(coolify GET "/api/v1/deployments/${dep}" | jq -r '.status // ""' 2>/dev/null || true)"
    case "$status" in
      finished) return 0 ;;
      failed | cancelled*) echo "deploy-s5: deployment ${status}" >&2; return 1 ;;
    esac
    sleep "$ESPERA_S"
  done
  echo "deploy-s5: tempo esgotado esperando o deployment" >&2; return 1
}

echo "== 1/6 portão da S5"
uso_pct="$(s5 "LC_ALL=C df --output=pcent / | tail -1" | tr -dc '0-9')"
livre=$((100 - ${uso_pct:-100}))
[ "$livre" -ge "$DISCO_MIN_LIVRE_PCT" ] || falha 4 "disco da S5 com ${livre}% livre (mínimo ${DISCO_MIN_LIVRE_PCT}%)"
carga="$(s5 "cut -d' ' -f1 /proc/loadavg" | tr -d '[:space:]')"
awk -v c="${carga:-99}" -v m="$CARGA_MAX" 'BEGIN{exit !(c+0 < m+0)}' || falha 4 "carga da S5 em ${carga} (máximo < ${CARGA_MAX})"
echo "   disco livre ${livre}%, carga ${carga}"

echo "== 2/6 /healthz antes"
read -r cod_antes _ _ <<<"$(healthz)"
if [ "$cod_antes" != "200" ]; then
  [ "$primeiro" -eq 1 ] || falha 5 "/healthz não respondeu 200 antes do deploy (primeiro deploy? use --primeiro)"
  echo "   fora do ar (aceito: --primeiro)"
fi

echo "== 3/6 tag atual (rollback)"
anterior="$(tag_no_coolify)" || falha 8 "não consegui ler as variáveis da aplicação no Coolify"
echo "   anterior: ${anterior:-nenhuma}   nova: ${tag}"
[ -n "$anterior" ] || [ "$primeiro" -eq 1 ] || falha 2 "não achei IMAGE_TAG anterior no Coolify; sem ponto de rollback só com --primeiro"
sha_anterior=""
if [ -n "$anterior" ]; then
  [[ "$anterior" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || falha 2 "IMAGE_TAG atual '${anterior}' não é semver: corrija à mão antes"
  sha_anterior="$(sha_da_tag "$anterior")"
fi

echo "== 4/6 gravar IMAGE_TAG"
grava_tag "$tag" || falha 8 "nada foi implantado (a tag no Coolify continua a anterior ou foi recusada)"

echo "== 5/6 deploy e /healthz depois"
if dispara_e_espera && espera_healthz "$HEALTH_TENTATIVAS" "$versao" "$sha_novo"; then
  echo "== 6/6 OK: ${tag} no ar; /healthz 200, version ${versao}, git_sha ${sha_novo:0:12}"
  exit 0
fi

echo "deploy-s5: FALHOU em ${tag}" >&2
[ -n "$anterior" ] || falha 7 "sem tag anterior para voltar; intervenção manual (--primeiro)"
echo "== rollback para ${anterior}" >&2
grava_tag "$anterior" || falha 7 "o rollback não conseguiu gravar ${anterior}; intervenção manual (Coolify da S2)"
[ -n "$sha_anterior" ] || echo "deploy-s5: a tag ${anterior} não está no git local; no rollback confiro só a versão" >&2
if dispara_e_espera && espera_healthz "$HEALTH_TENTATIVAS" "${anterior#v}" "${sha_anterior:-*}"; then
  falha 6 "rollback feito: ${anterior} no ar"
fi
falha 7 "o rollback para ${anterior} TAMBÉM falhou; intervenção manual (Coolify da S2 e docker logs na S5)"
