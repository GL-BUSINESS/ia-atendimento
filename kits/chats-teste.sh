#!/usr/bin/env bash
# chats-teste.sh — chats de teste da TI <-> `pessoas_teste` e a lista `chats_teste` do orquestrador (B2.4; risco 103 «fantasma de venda em teste»).
#
#   bash chats-teste.sh gerar   --par CHAT=PERSONA [--par …] [--saida ARQ] [--recomecar]         monta o PESSOAS_TESTE_ARQUIVO (as 84 pessoas + os chats), 0600.
#                                                                                               PRESERVA os pares do arquivo de saída que já existe e acrescenta os --par
#                                                                                               (--recomecar ignora o arquivo anterior: então passe TODOS os pares)
#   bash chats-teste.sh aplicar --par CHAT=PERSONA [--par …] --motivo CODIGO --por LOGIN        ACRESCENTA estes chats à lista vigente (merge); guarda a lista anterior
#   bash chats-teste.sh aplicar … --substituir                                                  a lista passa a ser SÓ estes chats (a anterior também fica guardada)
#   bash chats-teste.sh limpar  --motivo CODIGO --por LOGIN [--forcar]                          desfaz o último `aplicar` DESTA API: restaura a lista que ele guardou, mas só se a
#                                                                                               lista vigente for a que o `aplicar` gravou (alguém mexeu no meio: recusa; --forcar restaura mesmo assim)
#   bash chats-teste.sh limpar  --vazio --motivo CODIGO --por LOGIN                             lista vazia (derruba todos os chats de teste)
#   (cada um exige --ensaio, que só imprime o plano e NÃO abre conexão, ou --confirmo, que executa)
#
# POR QUE DUAS FASES: a API recusa `chats_teste` com chat cuja pessoa não está no arquivo `PESSOAS_TESTE_ARQUIVO`, e esse arquivo é lido NO BOOT.
#   A API valida a lista INTEIRA (a vigente + os novos) contra o arquivo: por isso o `gerar` preserva os pares do arquivo anterior. Se o arquivo
#   anterior se perdeu, o `gerar --recomecar` exige TODOS os pares vigentes; sem eles o `aplicar` em merge e o `limpar` tomam 422 pelos chats antigos.
#   1) `gerar` escreve o arquivo localmente (nada remoto). 2) VOCÊ o entrega à VPS no caminho do `PESSOAS_TESTE_ARQUIVO` e reinicia o orquestrador
#   (este kit não mexe na VPS). 3) `aplicar` grava a lista. Chat que a TI não tem no arquivo = 422 `pessoa_fora_de_pessoas_teste`; chat de cliente
#   (atendimento `real`/`sombra`, ou `duble` de pessoa fora de `pessoas_teste`) = 422 `chat_de_cliente`; ambos antes de gravar nada.
#
# SEGURANÇA: o token `ti` vem de um arquivo 0600 ($IA_TOKEN_TI_ARQUIVO, padrão ~/ia-segredos/token_ti), nunca por argv nem impresso (vai a um arquivo
#   de cabeçalho 0600 temporário, `curl -H @arq`). Imprime só contagens, os ids dos chats de TESTE, o código HTTP e a versão. O CPF das pessoas de teste
#   nem passa por aqui. Quem grava fica no registro da versão (`publicado_por` = --por, `motivo` = --motivo, OBRIGATÓRIO e sem padrão: o registro não mente).
#   No máximo 20 chats (a 0003 recusa mais). A API só escuta na WireGuard (10.90.0.5:8000): outro host exige IA_API_FORA_DA_WG=1.
#
# Variáveis: IA_API_URL (padrão http://10.90.0.5:8000), IA_REPO (checkout do ia-atendimento COM a B2.4; padrão: o checkout deste kit, depois
#   ~/repos/ia-atendimento e ~/wt-ia/ia-atendimento-b24; o primeiro que tiver src/ia_atendimento/pessoas_teste/__main__.py), IA_PY (python do venv do repo; sem ele
#   usa `uv run`), SAIDA_ARQUIVO (padrão ./pessoas_teste.json), CHATS_TESTE_ESTADO (onde ficam as listas anteriores; padrão ~/ia-segredos/chats-teste, 0700).
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IA_API_URL="${IA_API_URL:-http://10.90.0.5:8000}"
IA_TOKEN_TI_ARQUIVO="${IA_TOKEN_TI_ARQUIVO:-$HOME/ia-segredos/token_ti}"
SAIDA_ARQUIVO="${SAIDA_ARQUIVO:-./pessoas_teste.json}"
CHATS_TESTE_ESTADO="${CHATS_TESTE_ESTADO:-$HOME/ia-segredos/chats-teste}"
MAX_CHATS=20

falha() { printf '!! %s\n' "$*" >&2; exit 1; }
titulo() { printf '\n== %s\n' "$*"; }
ok() { printf 'PASSOU  %s\n' "$*"; }
ajuda() { sed -n '2,/^set /p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; }

[ $# -ge 1 ] || { ajuda; exit 2; }
CMD="$1"; shift
ENSAIO=0; CONFIRMO=0; POR=""; MOTIVO="${IA_MOTIVO:-}"; SUBSTITUIR=0; VAZIO=0; RECOMECAR=0; FORCAR=0; PARES=()
while [ $# -gt 0 ]; do
  case "$1" in
    --ensaio) ENSAIO=1 ;;
    --confirmo) CONFIRMO=1 ;;
    --substituir) SUBSTITUIR=1 ;;
    --vazio) VAZIO=1 ;;
    --recomecar) RECOMECAR=1 ;;
    --forcar) FORCAR=1 ;;
    --par) [ $# -ge 2 ] || falha "--par exige CHAT=PERSONA"; PARES+=("$2"); shift ;;
    --por) [ $# -ge 2 ] || falha "--por exige o login do operador"; POR="$2"; shift ;;
    --motivo) [ $# -ge 2 ] || falha "--motivo exige um código"; MOTIVO="$2"; shift ;;
    --saida) [ $# -ge 2 ] || falha "--saida exige o caminho"; SAIDA_ARQUIVO="$2"; shift ;;
    -h|--help) ajuda; exit 0 ;;
    *) falha "argumento desconhecido: $1" ;;
  esac
  shift
done
case "$CMD" in gerar|aplicar|limpar) ;; *) falha "comando desconhecido: $CMD (gerar | aplicar | limpar)" ;; esac
if [ "$ENSAIO" = 0 ] && [ "$CONFIRMO" = 0 ]; then
  echo "Nada foi feito. Use --ensaio (só imprime o plano) ou --confirmo (executa)." >&2; exit 2
fi
[ "$ENSAIO" = 1 ] && [ "$CONFIRMO" = 1 ] && falha "--ensaio e --confirmo juntos não fazem sentido"
[ "$SUBSTITUIR" = 1 ] && [ "$CMD" != aplicar ] && falha "--substituir só vale em aplicar"
[ "$VAZIO" = 1 ] && [ "$CMD" != limpar ] && falha "--vazio só vale em limpar"
[ "$RECOMECAR" = 1 ] && [ "$CMD" != gerar ] && falha "--recomecar só vale em gerar"
[ "$FORCAR" = 1 ] && [ "$CMD" != limpar ] && falha "--forcar só vale em limpar"

# --- validações que valem nos dois modos (sem rede) -----------------------------------------------------------------------------------------
CHATS=()
if [ "$CMD" != limpar ]; then
  [ "${#PARES[@]}" -ge 1 ] || falha "$CMD exige ao menos um --par CHAT=PERSONA"
  [ "${#PARES[@]}" -le "$MAX_CHATS" ] || falha "mais de $MAX_CHATS chats (a 0003 recusa)"
  for p in "${PARES[@]}"; do
    [[ "$p" == *=* ]] || falha "par sem '=': use CHAT=PERSONA"
    chat="${p%%=*}"; persona="${p#*=}"
    [[ "$chat" =~ ^[0-9a-f]{24}$ ]] || falha "chat_id tem de ter 24 hex minúsculo"
    [[ "$persona" =~ ^(P(0[1-9]|[1-5][0-9]|60)|P-M(0[1-9]|1[0-9]|2[0-4]))$ ]] || falha "persona fora de P01–P60 / P-M01–P-M24"
    CHATS+=("$chat")
  done
  [ "$(printf '%s\n' "${CHATS[@]}" | sort -u | wc -l)" = "${#CHATS[@]}" ] || falha "chat repetido nos pares"
fi
if [ "$CMD" != gerar ]; then
  [[ "$POR" =~ ^[A-Za-z0-9._@+-]{3,128}$ ]] || falha "--por: login ou e-mail do operador (3 a 128 caracteres simples; nunca CPF)"
  [[ "$POR" =~ [0-9]{11} ]] && falha "--por parece conter documento"
  [[ "$MOTIVO" =~ ^[a-z0-9_]{1,40}$ ]] || falha "--motivo (ou IA_MOTIVO) é obrigatório: código [a-z0-9_]{1,40}, sem padrão (o registro da versão guarda o motivo REAL)"
  [[ "$IA_API_URL" =~ ^http://(10\.90\.0\.5|127\.0\.0\.1|localhost)(:[0-9]+)?$ ]] || [ "${IA_API_FORA_DA_WG:-0}" = 1 ] \
    || falha "IA_API_URL fora da WireGuard (10.90.0.5): o token da TI viajaria em HTTP puro; use IA_API_FORA_DA_WG=1 só se souber o que faz"
fi

repo_com_b24() { # primeiro candidato com o pacote pessoas_teste
  local c
  for c in "${IA_REPO:-}" "$AQUI/.." "$HOME/repos/ia-atendimento" "$HOME/wt-ia/ia-atendimento-b24"; do
    [ -n "$c" ] && [ -f "$c/src/ia_atendimento/pessoas_teste/__main__.py" ] && { (cd "$c" && pwd); return 0; }
  done
  return 1
}
URLH="$(printf '%s' "$IA_API_URL" | sha256sum | cut -c1-8)"   # a lista guardada é DESTA API: a de outro ambiente (ensaio local) nunca é restaurada aqui
anterior_mais_recente() { # `anterior-<urlhash>-<versao>.json` ainda não restaurados desta API, o de maior versão
  { ls -1 "$CHATS_TESTE_ESTADO"/anterior-"$URLH"-*.json 2>/dev/null || true; } | sed -E 's/.*anterior-[0-9a-f]{8}-([0-9]+)\.json/\1 &/' | sort -n | tail -1 | cut -d' ' -f2-
}

# --- plano ---------------------------------------------------------------------------------------------------------------------------------
titulo "plano ($CMD)"
case "$CMD" in
  gerar)
    if [ -f "$SAIDA_ARQUIVO" ] && [ "$RECOMECAR" = 0 ]; then JUNTA="PRESERVA os pares de $SAIDA_ARQUIVO e acrescenta ${#CHATS[@]} chat(s)"
    else JUNTA="grava SÓ os ${#CHATS[@]} chat(s) dos --par (arquivo novo ou --recomecar: passe TODOS os pares vigentes)"; fi
    echo "grava $SAIDA_ARQUIVO (0600) com as 84 pessoas; $JUNTA; roda 'python -m ia_atendimento.pessoas_teste arquivo' no checkout do ia-atendimento" ;;
  aplicar) echo "PUT $IA_API_URL/config/chats_teste: lista vigente $( [ "$SUBSTITUIR" = 1 ] && echo SUBSTITUÍDA por || echo ACRESCIDA de ) ${#CHATS[@]} chat(s); por=$POR, motivo=$MOTIVO, versao_esperada = a vigente (lida antes); a lista anterior fica em $CHATS_TESTE_ESTADO" ;;
  limpar)
    if [ "$VAZIO" = 1 ]; then echo "PUT $IA_API_URL/config/chats_teste = [] (todos os chats de teste caem), por=$POR, motivo=$MOTIVO"
    else
      ARQ_ANT="$(anterior_mais_recente)"
      if [ -n "$ARQ_ANT" ]; then echo "PUT $IA_API_URL/config/chats_teste = a lista guardada em $ARQ_ANT, por=$POR, motivo=$MOTIVO"
      else echo "NÃO há lista anterior guardada em $CHATS_TESTE_ESTADO: use --vazio para zerar a lista (nada para restaurar)"; fi
    fi ;;
esac
if [ "$ENSAIO" = 1 ]; then echo "--ensaio: nada executado, nenhuma conexão aberta."; exit 0; fi

# --- gerar ---------------------------------------------------------------------------------------------------------------------------------
if [ "$CMD" = gerar ]; then
  REPO="$(repo_com_b24)" || falha "nenhum checkout do ia-atendimento com a B2.4 (src/ia_atendimento/pessoas_teste/__main__.py): defina IA_REPO"
  args=(arquivo --saida "$SAIDA_ARQUIVO")
  if [ -f "$SAIDA_ARQUIVO" ] && [ "$RECOMECAR" = 0 ]; then
    cp -p "$SAIDA_ARQUIVO" "$SAIDA_ARQUIVO.anterior" && args+=(--juntar "$SAIDA_ARQUIVO.anterior")   # a saída é truncada: lê da cópia
    trap 'rm -f "$SAIDA_ARQUIVO.anterior"' EXIT
  fi
  for p in "${PARES[@]}"; do args+=(--par "$p"); done
  umask 077
  if [ -n "${IA_PY:-}" ]; then (cd "$REPO" && "$IA_PY" -m ia_atendimento.pessoas_teste "${args[@]}")
  else (cd "$REPO" && uv run --quiet python -m ia_atendimento.pessoas_teste "${args[@]}"); fi
  [ "$(stat -c %a "$SAIDA_ARQUIVO")" = 600 ] || falha "$SAIDA_ARQUIVO não ficou 0600"
  NCHATS=$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["chats"]))' "$SAIDA_ARQUIVO")
  ok "arquivo escrito (0600) com $NCHATS chat(s). Entregue-o à VPS no caminho do PESSOAS_TESTE_ARQUIVO e REINICIE o orquestrador; depois rode 'aplicar'."
  exit 0
fi

# --- aplicar / limpar -----------------------------------------------------------------------------------------------------------------------
[ -f "$IA_TOKEN_TI_ARQUIVO" ] && [ ! -L "$IA_TOKEN_TI_ARQUIVO" ] || falha "token da TI ausente ou é link simbólico: $IA_TOKEN_TI_ARQUIVO"
[ "$(stat -c %a "$IA_TOKEN_TI_ARQUIVO")" = 600 ] || falha "$IA_TOKEN_TI_ARQUIVO precisa ser 0600"
umask 077
mkdir -p "$CHATS_TESTE_ESTADO" && chmod 700 "$CHATS_TESTE_ESTADO"
CAB="$(mktemp)"; CORPO="$(mktemp)"; RESP="$(mktemp)"
trap 'rm -f "$CAB" "$CORPO" "$RESP"' EXIT
printf 'x-ia-token: %s\n' "$(tr -d '\n\r ' < "$IA_TOKEN_TI_ARQUIVO")" > "$CAB"
json() { python3 -c "$1" "${@:2}"; }
descartar_tmp() { if [ "$CMD" = aplicar ] && [ -n "${ANT_ARQ:-}" ]; then rm -f "$ANT_ARQ.tmp"; fi; return 0; }

titulo "1. lista vigente de chats_teste"
cod=$(curl -sS -m 15 -o "$RESP" -w '%{http_code}' -H @"$CAB" "$IA_API_URL/config/chats_teste") || falha "API fora do ar ou fora da WireGuard"
[ "$cod" = 200 ] || falha "GET /config/chats_teste devolveu HTTP $cod"
VERSAO=$(json 'import json,sys; print(int(json.load(open(sys.argv[1]))["versao"]))' "$RESP")
ATUAL=$(json 'import json,sys; print(" ".join(json.load(open(sys.argv[1]))["valor"] or []))' "$RESP")
ok "versão vigente = $VERSAO, $(printf '%s' "$ATUAL" | wc -w) chat(s): ${ATUAL:-(nenhum)}"

if [ "$CMD" = aplicar ]; then
  if [ "$SUBSTITUIR" = 1 ]; then NOVOS="${CHATS[*]}"; else NOVOS=$(json 'import sys; v=sys.argv[1].split(); n=sys.argv[2].split(); print(" ".join(v+[c for c in n if c not in v]))' "$ATUAL" "${CHATS[*]}"); fi
  ALVO_ROTULO="lista nova"
  ANT_ARQ="$CHATS_TESTE_ESTADO/anterior-$URLH-$VERSAO.json"
  [ -e "$ANT_ARQ" ] && falha "já existe $ANT_ARQ (um aplicar da versão $VERSAO que ninguém restaurou): rode 'limpar' antes, ou apague o arquivo se já não vale"
  json 'import json,sys; a = sys.argv; json.dump({"url": a[6], "versao_antes": int(a[2]), "valor": a[3].split(), "valor_depois": a[7].split(), "por": a[4], "motivo": a[5]}, open(a[1], "w"))' \
    "$ANT_ARQ.tmp" "$VERSAO" "$ATUAL" "$POR" "$MOTIVO" "$IA_API_URL" "$NOVOS"
else
  if [ "$VAZIO" = 1 ]; then NOVOS=""
  else
    ANT_ARQ="$(anterior_mais_recente)"
    [ -n "$ANT_ARQ" ] || falha "não há lista anterior guardada em $CHATS_TESTE_ESTADO: use --vazio para zerar a lista"
    NOVOS=$(json 'import json,sys; print(" ".join(json.load(open(sys.argv[1]))["valor"]))' "$ANT_ARQ")
    DEPOIS=$(json 'import json,sys; print(" ".join(json.load(open(sys.argv[1]))["valor_depois"]))' "$ANT_ARQ")
    if [ "$ATUAL" != "$DEPOIS" ] && [ "$FORCAR" = 0 ]; then
      falha "a lista vigente (${ATUAL:-(nenhum)}) NÃO é a que o aplicar gravou (${DEPOIS:-(nenhum)}): alguém mexeu em chats_teste no meio. Restaurar apagaria essa mudança; confira e use --forcar se for isso mesmo"
    fi
  fi
  ALVO_ROTULO="lista restaurada"
fi
[ "$(printf '%s' "$NOVOS" | wc -w)" -le "$MAX_CHATS" ] || { descartar_tmp; falha "a lista ficaria com mais de $MAX_CHATS chats (a 0003 recusa)"; }
titulo "2. PUT ($ALVO_ROTULO: $(printf '%s' "$NOVOS" | wc -w) chat(s): ${NOVOS:-(nenhum)})"
json 'import json,sys; arq, por, motivo, versao, novos = sys.argv[1:6]; json.dump({"valor": novos.split(), "por": por, "motivo": motivo, "versao_esperada": int(versao)}, open(arq, "w"))' \
  "$CORPO" "$POR" "$MOTIVO" "$VERSAO" "$NOVOS"
cod=$(curl -sS -m 20 -o "$RESP" -w '%{http_code}' -X PUT -H @"$CAB" -H 'content-type: application/json' --data-binary @"$CORPO" "$IA_API_URL/config/chats_teste") \
  || { descartar_tmp; falha "PUT falhou na rede"; }
if [ "$cod" = 200 ]; then
  nova=$(json 'import json,sys; d=json.load(open(sys.argv[1])); print(d["versao"], len(d["valor"]))' "$RESP")
  ok "gravado: versão e nº de chats = $nova (publicado_por=$POR, motivo=$MOTIVO)"
  if [ "$CMD" = aplicar ]; then
    mv "$ANT_ARQ.tmp" "$ANT_ARQ"
    echo "A lista anterior (versão $VERSAO) ficou em $ANT_ARQ. Desfazer: bash $(basename "$0") limpar --motivo $MOTIVO --por $POR --confirmo"
  elif [ "$VAZIO" = 0 ]; then
    mv "$ANT_ARQ" "$ANT_ARQ.restaurado"
  fi
else
  codigo=$(json 'import json,sys; print(json.load(open(sys.argv[1]))["erro"]["codigo"])' "$RESP" 2>/dev/null || echo "?")
  descartar_tmp
  falha "PUT recusado: HTTP $cod, código $codigo (nada foi gravado). 422 pessoa_fora_de_pessoas_teste = o orquestrador ainda não leu o arquivo com este chat; 422 chat_de_cliente = o chat tem histórico de cliente; 409 config_corrida = alguém gravou antes, rode de novo"
fi
