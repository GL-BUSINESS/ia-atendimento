#!/usr/bin/env bash
# migrar.sh — aplica as migrações do ia-atendimento POR LEDGER (G-0012, A4.6), na S5 ou na S4.
#
# Regras (OPERACAO §3, migrations/README.md:25-26, G-0011):
#   - cada migração e a linha do ledger `ia.migracao` vão NA MESMA TRANSAÇÃO (`psql -1`): ou entra tudo ou nada;
#   - o ledger é a verdade: migração já registrada não se reaplica; checksum registrado diferente do arquivo = PARA;
#   - em ordem: se uma posterior já está no ledger e uma anterior não, PARA (não «tapa buraco»);
#   - antes de tudo confere o 0001.sha256 do repositório; a 0003 roda as pré-checagens do OPERACAO §3a (os três = 0);
#   - a 0005 tem DROP CONSTRAINT: só com `--sim-0005` («sim» nomeado do dono, D-18).
#
# Uso:  bash migrar.sh --alvo s5|s4 --repo <checkout do ia-atendimento NA TAG revisada> [--aplicar] [--sim-0005] [--ate 0004]
#   --alvo s5   psql local como `postgres` (porta PG_PORTA do s5.env), rodando NA S5 como root
#   --alvo s4   psql na S4 por ssh, como `s4_super`, porta 5434 (formato do roteiro A4.6), rodando da S3; S4_SSH no ambiente
#               (ex.: S4_SSH="ssh -o BatchMode=yes -i ~/s4-acesso/id_s4 danilo@<s4>"); PSQL_ALVO substitui o comando inteiro (ensaio)
# Sem --aplicar: lê o ledger (só leitura) e mostra o plano. Nada é escrito.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
ler_args "$@"
ALVO=""; REPO=""; SIM_0005=0; ATE=""; SEM_TAG=0
set -- "${ARGS_RESTANTES[@]:-}"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --alvo) shift; ALVO="${1:-}" ;;
    --repo) shift; REPO="${1:-}" ;;
    --sim-0005) SIM_0005=1 ;;
    --ate) shift; ATE="${1:-}" ;;
    --permitir-sem-tag) SEM_TAG=1 ;;   # SÓ para o ensaio local, em banco descartável
    "") ;;
    *) falhar "argumento desconhecido: $1" ;;
  esac
  shift
done
case "$ALVO" in s5 | s4) ;; *) falhar "--alvo s5 ou --alvo s4" ;; esac
[ -n "$REPO" ] && [ -d "$REPO/migrations" ] || falhar "--repo aponta um checkout do ia-atendimento (com migrations/)"
[ -z "$ATE" ] || [[ "$ATE" =~ ^[0-9]{4}$ ]] || falhar "--ate NNNN"
MIG="$(cd "$REPO/migrations" && pwd)"

if [ -z "${PSQL_ALVO:-}" ]; then
  if [ "$ALVO" = s5 ]; then
    carregar_env; exigir PG_PORTA; validar_porta "$PG_PORTA" PG_PORTA
    [ "$(id -u)" = 0 ] || falhar "--alvo s5 roda na S5 como root (sudo)"
    PSQL_ALVO="sudo -n -u postgres psql -X -q -v ON_ERROR_STOP=1 -p ${PG_PORTA} -d ia_atendimento"
  else
    [ -n "${S4_SSH:-}" ] || falhar "--alvo s4 precisa de S4_SSH (o ssh da S4 do dono)"
    [[ "${S4_PG_PORTA:-5434}" =~ ^[0-9]+$ ]] || falhar "S4_PG_PORTA numérica"
    REMOTO="$S4_SSH"
    PSQL_ALVO="sudo -n -u s4_super psql -X -q -v ON_ERROR_STOP=1 -p ${S4_PG_PORTA:-5434} -d ia_atendimento"
  fi
fi
read -ra PSQL <<<"$PSQL_ALVO"
read -ra REM <<<"${REMOTO:-}"
executar_psql() {  # pelo ssh, os argumentos viram UMA string de shell remota: cada um vai citado com %q
  if [ "${#REM[@]}" -gt 0 ]; then "${REM[@]}" "$(printf '%q ' "${PSQL[@]}" "$@")"; else "${PSQL[@]}" "$@"; fi
}
psql_ler() { executar_psql -At -c "$1"; }
psql_tx() { executar_psql -1 -f -; }   # SQL pelo stdin, transação única

titulo "0. o checkout é exatamente uma tag revisada (o SQL roda como superusuário)"
if [ "$SEM_TAG" = 1 ]; then
  aviso "--permitir-sem-tag: checkout NÃO conferido contra tag. Só para ensaio local em banco descartável."
else
  command -v git >/dev/null || falhar "git ausente: preciso conferir a tag do checkout"
  [ -z "$(git -C "$REPO" status --porcelain 2>/dev/null)" ] || falhar "checkout com mudança local (git status): só uma tag limpa"
  tag="$(git -C "$REPO" describe --exact-match --tags HEAD 2>/dev/null)" || falhar "HEAD do checkout não é uma tag (git describe --exact-match)"
  [[ "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || falhar "tag '$tag' fora do padrão vX.Y.Z"
  [ "$(git -C "$REPO" cat-file -t "refs/tags/$tag")" = tag ] || falhar "a tag $tag não é anotada (release.sh cria anotada)"
  info "checkout limpo na tag $tag ($(git -C "$REPO" rev-parse --short HEAD))"
fi

titulo "1. checksums do repositório"
(cd "$MIG" && sha256sum -c --quiet 0001.sha256) || falhar "0001.sha256 não confere: o checkout não é o revisado"
info "0001.sha256 confere"
mapfile -t ARQUIVOS < <(cd "$MIG" && ls -1 [0-9][0-9][0-9][0-9]_*.up.sql | LC_ALL=C sort)
[ "${#ARQUIVOS[@]}" -ge 1 ] || falhar "nenhuma migração em $MIG"

titulo "2. ledger atual (só leitura)"
existe_ledger="$(psql_ler "select to_regclass('ia.migracao') is not null")" || falhar "não consegui ler o banco ia_atendimento no alvo ${ALVO}"
declare -A NO_LEDGER=()
if [ "$existe_ledger" = t ]; then
  while IFS='|' read -r id soma; do [ -n "$id" ] && NO_LEDGER["$id"]="$soma"; done < <(psql_ler "select migracao_id || '|' || checksum from ia.migracao order by 1")
fi
info "${#NO_LEDGER[@]} migração(ões) no ledger"

titulo "3. plano"
PENDENTES=(); viu_pendente=0
for arq in "${ARQUIVOS[@]}"; do
  id="${arq%.up.sql}"; num="${id%%_*}"
  soma="$(sha256sum "$MIG/$arq" | cut -d' ' -f1)"
  if [ -n "${NO_LEDGER[$id]+x}" ]; then
    [ "$viu_pendente" = 0 ] || falhar "$id está no ledger mas uma anterior não: ledger fora de ordem, pare e investigue (OPERACAO §6)"
    [ "${NO_LEDGER[$id]}" = "$soma" ] || falhar "$id: checksum do ledger ≠ arquivo (OPERACAO §6: não reaplique; investigue)"
    info "$id  já aplicada (${soma:0:8})"
    continue
  fi
  if [ -n "$ATE" ] && [ "$num" -gt "$ATE" ]; then info "$id  pendente, fora do --ate $ATE"; viu_pendente=1; continue; fi
  viu_pendente=1
  if [ "$num" = 0005 ] && [ "$SIM_0005" = 0 ]; then info "$id  PENDENTE, mas tem DROP CONSTRAINT: só com --sim-0005 («sim» nomeado do dono)"; break; fi
  info "$id  a aplicar (${soma:0:8})"
  PENDENTES+=("$arq")
done
[ "${#PENDENTES[@]}" -gt 0 ] || { info "nada a aplicar"; resumo_ok; exit 0; }

pre_0003() {  # OPERACAO §3a: ADD CONSTRAINT valida a tabela inteira; os três precisam ser 0
  local q n
  for q in "SELECT count(*) FROM ia.atendimento WHERE chat_id !~ '^[0-9a-f]{24}\$'" \
           "SELECT count(*) FROM ia.config_versao WHERE nome = 'chats_teste' AND jsonb_array_length(valor) > 20" \
           "SELECT count(*) FROM ia.atendimento WHERE estado IN ('aberto','aguardando_cliente') AND (fase !~ '^E[1-9]\$' OR estado_conversa ? 'pausa')"; do
    n="$(psql_ler "$q")"; [ "$n" = 0 ] || falhar "pré-checagem da 0003 deu $n (esperado 0): nada aplicado"
  done
  info "pré-checagens da 0003: 0, 0, 0"
}

titulo "4. aplicar (uma transação por migração, ledger dentro)"
for arq in "${PENDENTES[@]}"; do
  id="${arq%.up.sql}"; soma="$(sha256sum "$MIG/$arq" | cut -d' ' -f1)"
  if ! aplicando; then info "[simular] psql -1 < $arq + INSERT INTO ia.migracao ('$id', '${soma:0:8}…')"; continue; fi
  [ "${id%%_*}" != 0003 ] || pre_0003
  { cat "$MIG/$arq"
    printf "\nSET ROLE ia_owner;\nINSERT INTO ia.migracao (migracao_id, checksum) VALUES ('%s', '%s');\nRESET ROLE;\n" "$id" "$soma"
  } | psql_tx || falhar "$id falhou; a transação única desfez tudo (inclusive o ledger). Nada parcial ficou."
  info "$id aplicada"
done

titulo "5. ledger depois"
if aplicando; then psql_ler "select migracao_id || '  ' || left(checksum, 8) from ia.migracao order by 1" | sed 's/^/   /'; fi
resumo_ok
