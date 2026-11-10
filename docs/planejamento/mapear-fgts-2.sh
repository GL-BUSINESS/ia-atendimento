#!/usr/bin/env bash
# FF-0, rodada 2: as 9 ofertas por simulação (LC-03, LC-04). SÓ LEITURA.
# Só agregados por table_name: contagem, chaves presentes, valores médios e comissão.
# Nada de CPF, telefone, nome, simulation_id ou transaction_id na saída.
set -uo pipefail
OUT=~/fgts-estudo/mapeamento; mkdir -p "$OUT"; chmod 700 "$OUT"
PSQL='docker exec -i n8n-db psql -U postgres -d postgres -X -q -At -v ON_ERROR_STOP=1'
q() {
  local nome=$1 sql=$2
  printf 'BEGIN TRANSACTION READ ONLY;\nSET LOCAL statement_timeout = %s;\n%s\nCOMMIT;\n' "'${TETO:-60s}'" "$sql" \
    | ssh -o BatchMode=yes s2 "$PSQL" > "$OUT/$nome.json" 2> "$OUT/$nome.err"
  local rc=$?
  sed -i '/^\(BEGIN\|SET\|COMMIT\)$/d' "$OUT/$nome.json"
  if [ $rc -eq 0 ]; then echo "ok   $nome ($(wc -c < "$OUT/$nome.json") bytes)"; rm -f "$OUT/$nome.err"
  else echo "FALHA $nome: $(head -c 300 "$OUT/$nome.err" | tr '\n' ' ')"; fi
}
# Ofertas com success=true, de qualquer profundidade da resposta, nas últimas 24 h.
OF="
WITH o AS (SELECT s.id AS sim, e.key AS slug, e.value AS of
           FROM novosaque.simulacoes s, jsonb_each(s.resposta_enviada->'ofertas') e
           WHERE s.enviada_em >= now()-interval '24 hours' AND s.acao='esteira'
             AND jsonb_typeof(s.resposta_enviada->'ofertas')='object' AND jsonb_typeof(e.value)='object')
, n AS (SELECT sim, of, coalesce(of->>'table_name', slug) AS tabela,
          CASE WHEN jsonb_typeof(of->'disbursed_amount')='number' THEN (of->>'disbursed_amount')::numeric
               WHEN of->>'disbursed_amount' ~ '^[0-9.]+,[0-9]+\$' THEN replace(replace(of->>'disbursed_amount','.',''),',','.')::numeric
               WHEN of->>'disbursed_amount' ~ '^[0-9]+(\\.[0-9]+)?\$' THEN (of->>'disbursed_amount')::numeric END AS liberado
        FROM o)"
echo "== novosaque: as 9 ofertas por tabela (24 h)"
TETO=90s q 41-ns-ofertas-tabela "$OF
, ns AS (SELECT sim, max(liberado) AS lib_ns FROM n WHERE tabela='TABELA NS' GROUP BY 1)
SELECT json_build_object(
 'simulacoes_com_oferta',(SELECT count(DISTINCT sim) FROM n),
 'ofertas_por_simulacao',(SELECT json_agg(t) FROM (SELECT k AS ofertas, count(*) AS simulacoes FROM (SELECT sim, count(*) AS k FROM n GROUP BY 1) z GROUP BY 1 ORDER BY 1) t),
 'por_tabela',(SELECT json_agg(t ORDER BY n DESC) FROM (
    SELECT n.tabela, count(*) AS n, round(avg(n.liberado),2) AS liberado_medio,
           round(avg(n.liberado/nullif(ns.lib_ns,0)),4) AS razao_vs_ns,
           round(percentile_cont(0.5) WITHIN GROUP (ORDER BY n.liberado/nullif(ns.lib_ns,0))::numeric,4) AS razao_vs_ns_p50
    FROM n LEFT JOIN ns USING (sim) GROUP BY 1) t),
 'chaves_da_oferta',(SELECT json_agg(t ORDER BY chave) FROM (
    SELECT k AS chave, jsonb_typeof(of->k) AS tipo, count(*) AS n FROM n, jsonb_object_keys(of) k GROUP BY 1,2) t),
 'comissao',(SELECT json_agg(t) FROM (
    SELECT n.tabela, k AS chave, count(*) AS n,
           count(*) FILTER (WHERE jsonb_typeof(of->k)='number') AS numericos,
           count(*) FILTER (WHERE of->k IS NULL OR of->k='null'::jsonb) AS nulos,
           round(min((of->>k)::numeric) FILTER (WHERE jsonb_typeof(of->k)='number'),6) AS minimo,
           round(avg((of->>k)::numeric) FILTER (WHERE jsonb_typeof(of->k)='number'),6) AS media,
           round(max((of->>k)::numeric) FILTER (WHERE jsonb_typeof(of->k)='number'),6) AS maximo
    FROM n, jsonb_object_keys(of) k WHERE k ~* 'commission|comiss|fee|tac|spread' GROUP BY 1,2) t),
 'iguais_entre_tabelas',(SELECT json_agg(t) FROM (
    SELECT k AS chave, count(DISTINCT sim) AS simulacoes,
           count(DISTINCT sim) FILTER (WHERE d > 1) AS com_diferenca
    FROM (SELECT sim, k, count(DISTINCT of->k) AS d FROM n, jsonb_object_keys(of) k
          WHERE k NOT IN ('simulation_id','table_id','table_name','installments') GROUP BY 1,2) z GROUP BY 1) t));"
echo "== novosaque: o que cada proposta contratou (30 d)"
q 42-ns-contratada "SELECT json_agg(t) FROM (SELECT tabela, count(*) AS n, count(valor_financiado) AS com_financiado,
  count(*) FILTER (WHERE valor_financiado > valor_liberado) AS ganhou_valor,
  count(*) FILTER (WHERE valor_financiado < valor_liberado) AS perdeu_valor,
  round(avg(valor_financiado - valor_liberado) FILTER (WHERE valor_financiado IS NOT NULL),2) AS dif_media
  FROM novosaque.propostas WHERE data_inclusao >= current_date-30 GROUP BY 1) t;"

echo "== portão"
python3 -I - "$OUT" <<'PY'
import os,re,sys
out=sys.argv[1]; ruim=[]
for f in ('41-ns-ofertas-tabela.json','42-ns-contratada.json'):
    p=os.path.join(out,f)
    if not os.path.exists(p): continue
    t=open(p).read()
    m=re.findall(r'(?<![\d.])\d{11}(?![\d.])|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}|@[A-Za-z0-9.-]+\.(?:com|br)',t)
    if m: os.rename(p,p+'.QUARENTENA'); ruim.append((f,len(m)))
for f,n in ruim: print('QUARENTENA',f,n)
print('portão:', 'limpo' if not ruim else 'quarentena; não abrir, avisar a sessão')
PY
