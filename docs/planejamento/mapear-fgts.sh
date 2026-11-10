#!/usr/bin/env bash
# FF-0 do estudo FGTS: mapeamentos de custo zero. SÓ LEITURA (BEGIN READ ONLY + statement_timeout).
# Roda na S3 e lê a S2 por ssh (contêiner n8n-db, banco postgres). Saída em ~/fgts-estudo/mapeamento/.
# Exporta só estrutura e agregados: sem CPF, telefone, nome, texto de cliente, credencial ou caminho de webhook.
set -uo pipefail
OUT=~/fgts-estudo/mapeamento; mkdir -p "$OUT"; chmod 700 "$OUT"
DIA=$(date +%Y%m%d-%H%M)
PSQL='docker exec -i n8n-db psql -U postgres -d postgres -X -q -At -v ON_ERROR_STOP=1'

q() {  # nome, sql (deve devolver UMA linha json)
  local nome=$1 sql=$2
  printf 'BEGIN TRANSACTION READ ONLY;\nSET LOCAL statement_timeout = %s;\n%s\nCOMMIT;\n' "'${TETO:-30s}'" "$sql" \
    | ssh -o BatchMode=yes s2 "$PSQL" > "$OUT/$nome.json" 2> "$OUT/$nome.err"
  local rc=$?
  sed -i '/^\(BEGIN\|SET\|COMMIT\)$/d' "$OUT/$nome.json"
  if [ $rc -eq 0 ]; then echo "ok   $nome ($(wc -c < "$OUT/$nome.json") bytes)"; rm -f "$OUT/$nome.err"
  else echo "FALHA $nome: $(head -c 300 "$OUT/$nome.err" | tr '\n' ' ')"; fi
}
existe() { printf "SELECT count(*) FROM information_schema.schemata WHERE schema_name='%s';" "$1" | ssh -o BatchMode=yes s2 "$PSQL"; }

echo "== esquemas (LC-12)"
q 00-esquemas "SELECT json_agg(json_build_object('esquema',n.nspname,'tabelas',(SELECT count(*) FROM pg_class c WHERE c.relnamespace=n.oid AND c.relkind='r'))) FROM pg_namespace n WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema';"

echo "== n8n: lógica dos fluxos FGTS (LC-01, LC-14, LC-15), sem path de webhook"
IDS="'6JmTdZMEkwNFIE5x','sBcKoLRl9VeOX3fF','VZJlJYm80zP46Zls','EcxlFFWdhyN21qh6','8w92yUtBD0Bz4Xw6'"
TETO=60s q 10-n8n-logica "
WITH alvo AS (SELECT id, name, active, \"updatedAt\", nodes::jsonb AS nodes, connections::jsonb AS conn FROM n8n.workflow_entity WHERE id IN ($IDS)),
nos AS (SELECT a.id, n->>'name' AS nome, n->>'type' AS tipo, coalesce((n->>'disabled')::boolean,false) AS desativado,
  CASE
   WHEN n->>'type' ~* '\.(if|switch|filter)\$' THEN jsonb_build_object('conditions',n->'parameters'->'conditions','rules',n->'parameters'->'rules','mode',n->'parameters'->'mode')
   WHEN n->>'type' ~* '\.wait\$' THEN jsonb_build_object('resume',n->'parameters'->'resume','amount',n->'parameters'->'amount','unit',n->'parameters'->'unit')
   WHEN n->>'type' ~* '\.set\$' THEN jsonb_build_object('assignments',n->'parameters'->'assignments','values',n->'parameters'->'values')
   WHEN n->>'type' ~* 'httprequest' THEN jsonb_build_object('method',coalesce(n->'parameters'->'method',n->'parameters'->'requestMethod'),'url',n->'parameters'->'url','jsonBody',n->'parameters'->'jsonBody','bodyParameters',n->'parameters'->'bodyParameters','queryParameters',n->'parameters'->'queryParameters')
   WHEN n->>'type' ~* 'webhook' THEN jsonb_build_object('httpMethod',n->'parameters'->'httpMethod')
   WHEN n->>'type' ~* '\.(code|function|functionitem)\$' THEN jsonb_build_object('code',coalesce(n->'parameters'->'jsCode',n->'parameters'->'functionCode'))
   WHEN n->>'type' ~* 'executeworkflow' THEN jsonb_build_object('workflowId',n->'parameters'->'workflowId')
   ELSE '{}'::jsonb END AS p
  FROM alvo a, jsonb_array_elements(a.nodes) n)
SELECT json_build_object(
 'fluxos',(SELECT json_agg(json_build_object('id',id,'nome',name,'ativo',active,'atualizado',\"updatedAt\")) FROM alvo),
 'nos',(SELECT json_agg(json_build_object('fluxo',id,'nome',nome,'tipo',tipo,'desativado',desativado,'p',
     regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(p::text,
       '(bearer|basic)\s+[^\"\\\\ ]+','\1 <redigido>','gi'),
       '/webhook(-test)?/[A-Za-z0-9_-]+','/webhook/<redigido>','g'),
       '[A-Za-z0-9_.-]{32,}','<redigido>','g'),
       '\d{10,}','<n>','g'),
       '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}','<email>','g'))) FROM nos),
 'ligacoes',(SELECT json_agg(json_build_object('fluxo',a.id,'de',src.key,'saida',ord.o-1,'para',d->>'node'))
     FROM alvo a, jsonb_each(a.conn) src, jsonb_each(src.value) tipo,
          jsonb_array_elements(tipo.value) WITH ORDINALITY AS ord(lista,o), jsonb_array_elements(ord.lista) d));"

echo "== n8n: execuções por fluxo e estado (24 h e 7 d)"
TETO=45s q 11-n8n-execucoes "
SELECT json_agg(t) FROM (
 SELECT w.name AS fluxo, e.status, count(*) FILTER (WHERE e.\"startedAt\" > now()-interval '24 hours') AS em_24h,
        count(*) AS em_7d, min(e.\"startedAt\")::date AS desde
   FROM n8n.execution_entity e JOIN n8n.workflow_entity w ON w.id=e.\"workflowId\"
  WHERE e.\"workflowId\" IN ($IDS) AND e.\"startedAt\" > now()-interval '7 days'
  GROUP BY 1,2 ORDER BY 1,2) t;"

if [ "$(existe gateway)" = 1 ]; then
echo "== gateway: rotas do FGTS (destino sem caminho de webhook)"
q 20-gateway-rotas "
SELECT json_agg(json_build_object('path',path,'ativo',ativo,'critico',critico,'origens',origens,'descricao',descricao,
  'destino',regexp_replace(destino,'/webhook(-test)?/.*','/webhook/<redigido>'))) FROM gateway.rotas
 WHERE path ILIKE '%fgts%' OR path ILIKE '%saque%' OR destino ILIKE '%8104%' OR descricao ILIKE '%fgts%';"
fi

if [ "$(existe novosaque)" = 1 ]; then
echo "== novosaque: colunas das tabelas (forma)"
q 30-ns-colunas "SELECT json_agg(json_build_object('tabela',table_name,'coluna',column_name,'tipo',data_type) ORDER BY table_name, ordinal_position) FROM information_schema.columns WHERE table_schema='novosaque';"
echo "== novosaque: funil por dia (LC-08)"
q 31-ns-consultas-dia "SELECT json_agg(t ORDER BY dia, nivel) FROM (SELECT dia, nivel, desfecho, left(descricao,80) AS descricao, consultas, transacoes, pessoas, unicas FROM novosaque.consultas_dia WHERE dia >= current_date-21) t;"
q 32-ns-eventos-dia "SELECT json_agg(t ORDER BY dia) FROM (SELECT dia, stage, summary_status, motivo_chave, decisao, sum(eventos) AS eventos, sum(transacoes) AS transacoes FROM novosaque.proposta_evento_dia WHERE dia >= current_date-21 GROUP BY 1,2,3,4,5) t;"
TETO=45s q 33-ns-estagios "SELECT json_agg(t) FROM (SELECT stage, summary_status, count(DISTINCT transaction_id) AS transacoes, min(ocorrido_em)::date AS desde FROM novosaque.proposta_evento WHERE ocorrido_em >= now()-interval '21 days' GROUP BY 1,2 ORDER BY 3 DESC) t;"
TETO=45s q 34-ns-acompanhamentos "SELECT json_agg(t ORDER BY dia) FROM (SELECT criado_em::date AS dia, produto, estado, desfecho, via_webhook, count(*) AS n FROM novosaque.acompanhamentos WHERE criado_em >= now()-interval '21 days' GROUP BY 1,2,3,4,5) t;"
TETO=45s q 35-ns-propostas "SELECT json_agg(t ORDER BY dia) FROM (SELECT data_inclusao AS dia, tabela, count(*) AS n, count(data_formalizacao) AS formalizadas, count(data_averbado) AS averbadas, count(data_pago) AS pagas, count(data_cancelado) AS canceladas, round(avg(valor_liberado),0) AS liberado_medio FROM novosaque.propostas WHERE data_inclusao >= current_date-30 GROUP BY 1,2) t;"
echo "== novosaque: forma das ofertas e comissão (LC-03, LC-04)"
TETO=60s q 36-ns-ofertas-forma "
WITH RECURSIVE j(path, v) AS (
  SELECT ''::text, ofertas FROM novosaque.esteira_guru WHERE criado_em >= now()-interval '3 days' AND ofertas IS NOT NULL
  UNION ALL
  SELECT j.path || CASE WHEN x.k IS NULL THEN '[]' ELSE '.' || x.k END, x.val FROM j,
   LATERAL (SELECT key AS k, value AS val FROM jsonb_each(CASE WHEN jsonb_typeof(j.v)='object' THEN j.v END)
            UNION ALL SELECT NULL, value FROM jsonb_array_elements(CASE WHEN jsonb_typeof(j.v)='array' THEN j.v END)) x)
SELECT json_build_object(
 'linhas_3d',(SELECT count(*) FROM novosaque.esteira_guru WHERE criado_em >= now()-interval '3 days'),
 'chaves',(SELECT json_agg(t) FROM (SELECT path, jsonb_typeof(v) AS tipo, count(*) AS n, count(*) FILTER (WHERE v='null'::jsonb) AS nulos FROM j WHERE path<>'' GROUP BY 1,2 ORDER BY 1) t),
 'tabelas',(SELECT json_agg(t) FROM (SELECT v#>>'{}' AS tabela, count(*) AS n FROM j WHERE path ~* '(table_name|tabela|table)\$' AND jsonb_typeof(v)='string' GROUP BY 1 ORDER BY 2 DESC LIMIT 40) t),
 'comissao',(SELECT json_agg(t) FROM (SELECT path, count(*) AS n, count(*) FILTER (WHERE jsonb_typeof(v)='number') AS numericos, min((v#>>'{}')::numeric) FILTER (WHERE jsonb_typeof(v)='number') AS minimo, round(avg((v#>>'{}')::numeric) FILTER (WHERE jsonb_typeof(v)='number'),4) AS media, max((v#>>'{}')::numeric) FILTER (WHERE jsonb_typeof(v)='number') AS maximo FROM j WHERE path ~* 'commission|comiss' GROUP BY 1) t));"
echo "== novosaque: robô e diálogos (LC-09, LC-02)"
q 37-ns-robo-regra "SELECT json_agg(t ORDER BY prioridade) FROM (SELECT id, stage, summary_status, motivo_chave, ativa, left(dialogo_descricao,80) AS dialogo_descricao, janela_silencio_min, max_por_contrato, validade_horas, prioridade FROM novosaque.robo_regra) t;"
q 38-ns-robo-config "SELECT json_agg(regexp_replace(row_to_json(r)::text,'[A-Za-z0-9_.-]{32,}','<redigido>','g')::json) FROM novosaque.robo_config r;"
q 39-ns-dialogos "SELECT json_build_object('config',(SELECT json_agg(json_build_object('nome',dialog_nome,'id',dialogo_id)) FROM novosaque.dialogos_config),'mapeamento',(SELECT json_agg(json_build_object('resultado',left(result,80),'mapeado',mapeado,'dialogo',dialog_nome,'retry',retry)) FROM novosaque.mapeamento_dialogos));"
else echo "esquema novosaque NÃO está no n8n-db (LC-12): pular LC-08/03/04/09"; fi

if [ "$(existe chatguru)" = 1 ]; then
echo "== chatguru: árvore de diálogos (só nome, grupo, nó, tipo)"
q 40-chatguru-dialogos "SELECT json_agg(t ORDER BY chatbot, grupo, nome) FROM (SELECT d.chatbot_id AS chatbot, d.nome, d.grupo, d.node, d.tipo FROM chatguru.dialogos d WHERE d.nome ILIKE ANY (ARRAY['%fgts%','%saque%','%autoriza%','%cpf%','%pix%','%form%','%link%','%pre%aprov%','%negou%','%campanha%','%ns%']) OR d.grupo ILIKE '%fgts%') t;"
fi

echo "== portão: varredura de PII e segredo nas saídas"
python3 -I - "$OUT" <<'PY'
import os,re,sys,json
out=sys.argv[1]; ruim=[]
def dv(c):
    d=[int(x) for x in c]
    if len(set(d))==1: return False
    for n in (9,10):
        s=sum(d[i]*(n+1-i) for i in range(n)); r=(s*10)%11%10
        if r!=d[n]: return False
    return True
cams=[]
try:
    for w in json.load(open(os.path.expanduser('~/fgts-estudo/n8n/fluxos-fgts-estrutura.json'))):
        cams+=[n['webhook']['caminho'] for n in w['nos'] if 'webhook' in n and n['webhook'].get('caminho') and len(n['webhook']['caminho'])>12]
except Exception: pass
for f in sorted(os.listdir(out)):
    if not f.endswith('.json'): continue
    t=open(os.path.join(out,f)).read(); m=[]
    m+=['cpf' for x in re.finditer(r'(?<!\d)(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})(?!\d)',t) if dv(''.join(x.groups())) and not x.group(0).startswith('000')]
    m+=['telefone' for _ in re.finditer(r'(?<![\d.])(?:55)?\(?\d{2}\)?\s?9\d{4}-?\d{4}(?![\d.])',t)]
    m+=['email' for _ in re.finditer(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(com|br|net|org)\b',t)]
    m+=['webhook' for c in cams if c in t]
    m+=['segredo' for _ in re.finditer(r'(?i)(bearer|basic)\s+(?!<redigido>)\S{8,}|sk-[A-Za-z0-9]{10,}|eyJ[A-Za-z0-9_-]{20,}',t)]
    if m:
        os.rename(os.path.join(out,f),os.path.join(out,f+'.QUARENTENA')); ruim.append((f,sorted(set(m)),len(m)))
for f,k,n in ruim: print('QUARENTENA',f,k,n)
print('portão:', 'limpo' if not ruim else f'{len(ruim)} arquivo(s) em quarentena; não abrir, avisar a sessão')
PY
ls -la "$OUT"
