#!/usr/bin/env bash
# Aplica as migrações em um Postgres 18 DESCARTÁVEL no docker local (127.0.0.1) e mostra o ledger. Nada toca a S4.
# Uso: bash scripts/aplicar_migracoes_local.sh [--manter]
#   sem flag: sobe, cria os papéis como a infra do estudo E, aplica, confere e remove o contêiner;
#   --manter: deixa o contêiner de pé e imprime o DSN do ia_app_a (senha descartável de teste).
set -euo pipefail
cd "$(dirname "$0")/.."
MANTER=0; [ "${1:-}" = "--manter" ] && MANTER=1
IMAGEM="${IA_TESTE_PG_IMAGEM:-postgres:18}"; C="ia-pg18-local-$$"; SENHA=descartavel
derrubar() { [ "$MANTER" = 1 ] || docker rm -f "$C" >/dev/null 2>&1 || true; }
trap derrubar EXIT
docker run -d --rm --name "$C" -p 127.0.0.1::5432 -e POSTGRES_PASSWORD="$SENHA" "$IMAGEM" >/dev/null
PORTA=$(docker port "$C" 5432/tcp | sed -n 's/^127\.0\.0\.1:\([0-9]*\)$/\1/p' | head -1)
[ -n "$PORTA" ] || { echo "porta do contêiner não encontrada" >&2; exit 1; }
# esperar a CONDIÇÃO (login por TCP aceito), não um sinal: o servidor temporário do init só escuta no socket unix
for _ in $(seq 1 90); do docker exec "$C" psql -h 127.0.0.1 -U postgres -tAc 'select 1' >/dev/null 2>&1 && break; sleep 1; done
docker exec "$C" psql -h 127.0.0.1 -U postgres -tAc 'select 1' >/dev/null
psql_c() { docker exec -i "$C" psql -h 127.0.0.1 -U postgres -X -q -v ON_ERROR_STOP=1 "$@"; }
psql_c -d postgres <<'SQL'
CREATE ROLE ia_owner NOLOGIN; CREATE ROLE ia_app NOLOGIN; CREATE ROLE ia_leitura NOLOGIN; CREATE ROLE ia_qualidade NOLOGIN;
CREATE ROLE ia_app_a LOGIN IN ROLE ia_app PASSWORD 'x'; CREATE ROLE ia_leitura_a LOGIN IN ROLE ia_leitura PASSWORD 'x';
CREATE ROLE ia_qualidade_a LOGIN IN ROLE ia_qualidade PASSWORD 'x';
CREATE DATABASE ia_atendimento OWNER ia_owner;
REVOKE CONNECT ON DATABASE ia_atendimento FROM PUBLIC;
GRANT CONNECT ON DATABASE ia_atendimento TO ia_app, ia_leitura, ia_qualidade;
SQL
DSN="postgresql://postgres:${SENHA}@127.0.0.1:${PORTA}/ia_atendimento"
uv run python -m ia_atendimento.migracoes --dsn "$DSN"
uv run python -m ia_atendimento.migracoes --dsn "$DSN" --conferir
psql_c -d ia_atendimento -tAc "select migracao_id || '  ' || left(checksum, 12) || '  ' || aplicada_por from ia.migracao order by 1"
if [ "$MANTER" = 1 ]; then
  echo "contêiner $C de pé. ia_app_a: postgresql://ia_app_a:x@127.0.0.1:${PORTA}/ia_atendimento  (docker rm -f $C para remover)"
fi
