# Operação do `ia-atendimento` (fundação e API de entrada)

> **Atenção.** As seções 3 e 4 descrevem escrita em **produção** (S4). São **texto para o dono**: **não executar sem o «sim» do
> dono**, só pelos kits (`bash ~/retomada-2809/fila-2910/ia/<passo>/…`), com ensaio, contagem na mão e caminho de volta.
> Este repositório e seus testes nunca conectam na S4, na VPS nem em qualquer banco que não seja local e descartável.

## 1. Desenvolvimento local

```bash
uv sync
bash scripts/check.sh                        # portão: ruff, varredura, checksum da 0001, 0002 em dia, pytest
bash scripts/aplicar_migracoes_local.sh      # Postgres 18 descartável + papéis + migrações + ledger
```

- Os testes sobem `postgres:18` com `docker run --rm -p 127.0.0.1::5432` e esperam o login TCP (a condição, não um sinal).
  `IA_TESTE_PG_HOST`/`IA_TESTE_PG_PORT` usam um serviço já de pé (CI); a fixture recusa host não local e cluster com papéis `ia_*`.
- `/tmp` da S3 tem cota por usuário; o contêiner usa `tmpfs`, e o pytest escreve só em `tmp_path`.

## 2. Chave AES da conversa e do cofre

Arquivo JSON `{"<chave_id>": "<base64 de 32 bytes>"}` com permissão **0600** (o `Chaveiro` recusa 0644, symlink ou chave que não tenha
32 bytes). Uma chave por mês (`chave_id` 1..32767); `CHAVE_AES_ID` aponta a vigente.

```bash
umask 077
uv run python - <<'PY' > "$CHAVE_AES_ARQUIVO"      # novo arquivo; para adicionar o mês seguinte, junte a nova entrada ao JSON existente
import base64, json, os
print(json.dumps({"1": base64.b64encode(os.urandom(32)).decode()}))
PY
chmod 600 "$CHAVE_AES_ARQUIVO"
```

- **Sem backup da chave** (P-R10): perder a chave = perder o texto cifrado (é a intenção: o texto vive 14 dias).
- **Descarte mensal:** no dia 31 após o fim do mês, apague a entrada daquele `chave_id` do arquivo. Qualquer cópia antiga do texto
  (dump, WAL, pgBackRest) passa a ser ilegível; `decifrar` levanta `ChaveDesconhecida`.
- **Rotação:** o chaveiro é lido uma vez no boot (`chaveiro_padrao` fica em cache). Trocar `CHAVE_AES_ID` ou o arquivo (mês novo, descarte do
  mês velho) exige **reiniciar o orquestrador**. Quem cifra usa só a chave vigente; `decifrar` acha a chave pelo `chave_id` gravado na linha.
- **Virada do mês (uma só regra, UTC):** o mês da chave é o de **UTC**; a virada é **00:00 UTC = 21:00 BRT**. Nessa hora, juntar a entrada do
  mês novo ao arquivo, trocar `CHAVE_AES_ID` e reiniciar. O orquestrador tolera a chave do mês ANTERIOR por **1 h** depois da meia-noite UTC; depois
  disso (ou com a chave nova antes da hora) conversa e cofre **recusam gravar** (`ChaveForaDoMes`) em vez de cifrar com a chave errada.
- O arquivo mora em `/etc/ia-s4` (diretório montado `:ro` no compose da VPS; memória `coolify-dockercompose-storages`). Nunca no git
  (`.gitignore` bloqueia `*.key`, `chaves*.json`, `*.aes`, `.env*`).

## 3. Aplicar as migrações na S4 — **NÃO EXECUTAR SEM O «SIM» DO DONO**

Pré-requisito: A4.3 pronto (papéis, database `ia_atendimento`, certificados, `pg_hba`). Comandos no formato do roteiro A4.6; `$S4` é o
`ssh` do dono (ver `~/s4-acesso/ACESSO-EQUIPE-S4.md`). Executar a partir da raiz do repo, na versão revisada (tag `v0.1.0` depois da revisão).

```bash
# 0. checksums batem com o que foi revisado
(cd migrations && sha256sum -c 0001.sha256) && uv run python scripts/gerar_0002.py --verificar
# 1. 0001 + linha do ledger NA MESMA TRANSAÇÃO (psql -1): ou entra tudo ou nada. O arquivo faz SET ROLE ia_owner e RESET ROLE.
SUM1=$(sha256sum migrations/0001_esquema.up.sql | cut -d' ' -f1)
{ cat migrations/0001_esquema.up.sql
  printf "SET ROLE ia_owner; INSERT INTO ia.migracao (migracao_id, checksum) VALUES ('0001_esquema', '%s');\nRESET ROLE;\n" "$SUM1"; } \
  | $S4 'sudo -n -u s4_super psql -X -q -1 -v ON_ERROR_STOP=1 -p 5434 -d ia_atendimento -f -'
# 2. 0002 (Procrastinate 3.10.0) + ledger, igual; o arquivo já traz SET ROLE ia_owner e search_path = procrastinate, public
SUM2=$(sha256sum migrations/0002_procrastinate.up.sql | cut -d' ' -f1)
{ cat migrations/0002_procrastinate.up.sql
  printf "SET ROLE ia_owner; INSERT INTO ia.migracao (migracao_id, checksum) VALUES ('0002_procrastinate', '%s');\nRESET ROLE;\n" "$SUM2"; } \
  | $S4 'sudo -n -u s4_super psql -X -q -1 -v ON_ERROR_STOP=1 -p 5434 -d ia_atendimento -f -'
# 3a. pré-checagem (ADD CONSTRAINT valida a tabela inteira; qualquer linha fora do formato derruba a transação, sem estrago): os três = 0
#     (3º: SELECT count(*) FROM ia.atendimento WHERE estado IN ('aberto','aguardando_cliente') AND (fase !~ '^E[1-9]$' OR estado_conversa ? 'pausa'))
$S4 'sudo -n -u s4_super psql -X -qAt -p 5434 -d ia_atendimento -c "SELECT count(*) FROM ia.atendimento WHERE chat_id !~ '"'"'^[0-9a-f]{24}$'"'"'" -c "SELECT count(*) FROM ia.config_versao WHERE nome = '"'"'chats_teste'"'"' AND jsonb_array_length(valor) > 20"'
# 3. 0003 (aditiva: ultimo_cliente_em, chats_teste e chat_id de 24 hex, encerrado terminal, fase×estado) + ledger, igual; o arquivo já traz SET ROLE ia_owner. ANTES da imagem nova
SUM3=$(sha256sum migrations/0003_estado_aditivo.up.sql | cut -d' ' -f1)
{ cat migrations/0003_estado_aditivo.up.sql
  printf "SET ROLE ia_owner; INSERT INTO ia.migracao (migracao_id, checksum) VALUES ('0003_estado_aditivo', '%s');\nRESET ROLE;\n" "$SUM3"; } \
  | $S4 'sudo -n -u s4_super psql -X -q -1 -v ON_ERROR_STOP=1 -p 5434 -d ia_atendimento -f -'
# 4. 0004 (aditiva: `ia.fn_anexar_rpa` SECURITY DEFINER e a outbox `ia.espelho_evento`) + ledger, igual; ANTES da imagem que sobe a API (B1.5)
SUM4=$(sha256sum migrations/0004_anexo_rpa_e_espelho.up.sql | cut -d' ' -f1)
{ cat migrations/0004_anexo_rpa_e_espelho.up.sql
  printf "SET ROLE ia_owner; INSERT INTO ia.migracao (migracao_id, checksum) VALUES ('0004_anexo_rpa_e_espelho', '%s');\nRESET ROLE;\n" "$SUM4"; } \
  | $S4 'sudo -n -u s4_super psql -X -q -1 -v ON_ERROR_STOP=1 -p 5434 -d ia_atendimento -f -'
```

**Conferir** (como `ia_app_a`, da VPS): `select migracao_id, left(checksum,8) from ia.migracao` (4 linhas); `select valor from
ia.config_versao where nome='ia_ativa'` = `false` e `nome='modo'` = `"duble"`; `DROP TABLE ia.passo` falha; `ia_app_a` sem `DELETE`; `ia.atendimento.ultimo_cliente_em` existe e um `INSERT` de `chats_teste` com 21 ids ou id fora de 24 hex minúsculo é recusado
(`config_versao_chats_teste_check`). Depois do fim, `ia_app` ainda grava `contrato_id`, `pii_auditoria`, `sinais_cliente`, `ultimo_cliente_em` e os contadores; `estado`, `desfecho`,
`encerrado_em`, `estado_conversa`, `motivo_desfecho`, `contexto_codigos` e `repasse_modo`/`repasse_consultor_ref` de um encerrado ficam congelados
(trigger `atendimento_terminal_absorvente`). A 0003 é aditiva: o código sem ela segue funcionando, e ela é inofensiva sem o código novo (desfazer = parar o app).
A 0004 também é aditiva: `UPDATE ia.passo` direto segue falhando (`permission denied`), `SELECT ia.fn_anexar_rpa(-1, 'rpa_inexistente')` devolve `f` como `ia_app_a`, e `ia_leitura_a` não lê `ia.espelho_evento`.

**Se der errado:** erro no meio de um arquivo (ou no INSERT do ledger) → a transação única (`-1`) desfaz tudo, inclusive o ledger; reaplicar
a 0001 é idempotente; a 0002, a 0003 e a 0004 já aplicadas **não** se reaplicam (o ledger é a verdade; `ADD CONSTRAINT` não é idempotente). **Desfazer:** `DROP DATABASE … WITH (FORCE)` só com autorização nova do dono (estudo E «Desfazer tudo» 1).

## 4. Conexão da fila (Procrastinate) — decisão de infra

As funções e gatilhos do Procrastinate usam nomes sem schema. Defina para `ia_app_a`/`_b` **uma** das opções (nenhuma é aplicada por este repo):
`options=-c search_path=procrastinate,public` na `DATABASE_URL`, ou, **por login** (`s4_super`; **não executar sem o «sim»**):

```sql
ALTER ROLE ia_app_a IN DATABASE ia_atendimento SET search_path = procrastinate, public;
ALTER ROLE ia_app_b IN DATABASE ia_atendimento SET search_path = procrastinate, public;
```

O código da fila (`fila.conninfo_da_fila`) acrescenta `-c search_path=procrastinate,public` às `options` da conexão do Procrastinate sozinho; a conexão
precisa ser **direta** ao Postgres (nunca por pooler em modo transação: o LISTEN/NOTIFY não atravessa; `prontidao.verificar_listen_notify` prova).

Não use o grupo `ia_app` no `ALTER ROLE`: configuração de papel não é herdada pelos logins membros (`tests/test_migracoes.py` prova).

## 5. Quando o checksum divergir

`aplicar()`/`conferir()` levantam `ChecksumDivergente` e **param**: alguém editou uma migração já aplicada. Não corrija o DDL: restaure o arquivo
(`git checkout`) ou, se o desenho mudou, crie a migração seguinte (`0005+`) e reabra o estudo I. Na dúvida, abra achado na Parte F do roteiro.

## 6. Trocar a versão do Procrastinate

Antes de aplicada: `uv add procrastinate==X`, `uv run python scripts/gerar_0002.py`, revisar o diff e commitar. Depois de aplicada: **não** regerar a 0002; o diff da pasta
de migrações do pacote vira a migração seguinte (`0005+`).

## 7. Release

Tag semver e `gh release create` só depois da revisão (rodízio: quem implementa não revisa). Esta fundação é a `v0.1.0`; **a tag ainda não foi criada**.

## 8. Subir a API de entrada (B1.5) — na VPS, só com as migrações 0003 e 0004 aplicadas

Pré-requisitos (ordem do contrato 08 §10): migrações 0003 e 0004 (seção 3) **antes** da imagem; os três arquivos de segredo abaixo montados `:ro`; o worker do
Procrastinate de pé (o `/readyz` dá 503 sem batimento de worker). Nada disto roda na S4 nem é feito por este repositório; a imagem e o Coolify são do dono.

```bash
# arquivos de segredo (modo 0600, dono do usuário do contêiner; nunca em variável de ambiente do Coolify, nunca no git)
umask 077
printf '%s\n' "<chave HMAC 1 do gateway, a mesma do GATEWAY_ASSINATURAS>" > /etc/ia-s4/gateway-hmac.keys    # 2ª linha só na virada de rotação
cat > /etc/ia-s4/saida.json <<'JSON'
{"ia_orquestrador_bearer": "<...>", "chatguru_token_ia": "<...>", "c360_client_id": "<...>", "c360_client_secret": "<...>"}
JSON
chmod 600 /etc/ia-s4/gateway-hmac.keys /etc/ia-s4/saida.json

# Onde cada segredo mora (decisão R1-24, DECISOES-B1.5):
#  - ARQUIVO 0600 montado :ro (nunca variável do Coolify): gateway-hmac.keys, saida.json e as chaves AES mensais (CHAVE_AES_ARQUIVO).
#  - VARIÁVEL SECRETA da plataforma (campo mascarado do Coolify, nunca em compose versionado nem em log): API_TOKENS, CHAVE_H16, CHAVE_FINGERPRINT,
#    CHAT_REF_CHAVE, MODELO_API_KEY_1 e DATABASE_URL. São permanentes (trocar quebra o dedupe ou o histórico), então não têm descarte mensal.
#  - VARIÁVEL comum (não secreta): GATEWAY_HMAC_ARQUIVO, SEGREDOS_SAIDA_ARQUIVO, CHAVE_AES_ID, RESPONSAVEL_IA, GIT_SHA, BUILT_AT, IA_MIGRACOES_DIR.
export GATEWAY_HMAC_ARQUIVO=/etc/ia-s4/gateway-hmac.keys SEGREDOS_SAIDA_ARQUIVO=/etc/ia-s4/saida.json
export RESPONSAVEL_IA=<e-mail do Amado> GIT_SHA=<sha da tag> BUILT_AT=<AAAA-MM-DDTHH:MM:SSZ>
uvicorn --factory ia_atendimento.api.ambiente:criar_app_de_ambiente --host 10.90.0.5 --port 8000 \
  --no-access-log --no-server-header --limit-concurrency 64 --timeout-keep-alive 5
```

- **Limites do processo:** `--limit-concurrency 64` e `--timeout-keep-alive 5` seguram uma inundação vinda da S2 (única origem permitida); o pool tem 8 conexões, cada uma com
  `lock_timeout=2s`, `statement_timeout=5s` e `idle_in_transaction_session_timeout=10s` (espera por lock vencida = 503 `nao_pronto`, o n8n repete) e `check` de conexão. `HEAD /healthz` responde 200 (sonda).
- **Falha de subida (de propósito):** segredo obrigatório ausente, arquivo de segredo aberto (diferente de 0600), link simbólico, chave HMAC curta ou repetida,
  token duplicado, `DATABASE_URL` com `+dialeto` (use `postgresql://` puro), `RESPONSAVEL_IA` que não é e-mail, preço ≤ 0, chave AES que não é a do mês. A mensagem diz o campo e a regra, **nunca o valor**.
- **Rotação da chave do gateway:** acrescente a chave nova como 2ª linha de `gateway-hmac.keys` e reinicie a API; só depois troque a do gateway; depois tire a velha
  (01 §3.2). Reiniciar também ao virar o mês da chave AES (seção 2).
- **Migrações no `/readyz`:** a pasta das migrações viaja no wheel (`ia_atendimento/migrations`) ou vem de `IA_MIGRACOES_DIR`; se não achar nenhuma a API **não sobe**, e o `/readyz` sem a pasta dá 503 `migracoes_nao_conferidas`
  (nunca 200 sem conferir checksum e pendência).
- **Conferir:** `GET /healthz` (sem token) devolve `version`/`git_sha`; `GET /readyz` e `GET /saude` com qualquer token válido (`ia_ativa=false` e `modo="duble"` no seed).
  Sem `/docs` nem `/openapi.json` (o esquema não é público). A fábrica configura o log da aplicação (INFO em stderr, formato fixo; o uvicorn só configura os `uvicorn.*`) e desliga o access log (grava caminho e query). Sai uma linha `req trace=… metodo=… rota=… status=… codigo=… ms=…` por requisição, e os 401 de assinatura/token e os 403 de origem geram `alerta ti: contador=…` em WARNING. O log traz só `trace_id`, rota (molde), status, código e duração: **nenhum corpo, texto, token nem assinatura**.
- **Conexão:** o pool usa a `DATABASE_URL` (login `ia_app_a/_b`) com `search_path=procrastinate,public` nas `options`, para o job entrar **na mesma transação** da gravação;
  conexão direta ao Postgres (nunca por pooler em modo transação).
- **Parada leve:** `PUT /config/ia_ativa` com `false` agenda um alarme (`alarme_encerrar_por_chave`, sem lock do chat) por atendimento aberto, aguardando ou pausado (até 19 min); ao disparar ele enfileira o `encerrar_por_chave` com o lock do chat, então o cliente que responde nesse intervalo não fica preso. O serviço que executa o job
  é da B1.6: até lá o job falha alto (`ServicoNaoConfigurado`) e a vigia alerta; a chave desligada já recusa entrada nova.

## 9. Chats de teste e `pessoas_teste` (B2.4) — só pelo kit, só a TI

`pessoas_teste` é a lista das 84 pessoas sintéticas (uma por `persona_id` da F3: P01–P60 e P-M01–P-M24; CPF `000.000.0nn`, `pessoa_id` `00000000-0000-7000-8000-…`).
Um chat de teste **nunca tem CPF**, mas `atendimento.pessoa_id` é obrigatório: no ensaio B, no smoke e na F3 a pessoa vem daqui, e em `duble|teste` T1 e T3 leem a oferta FACTA
(`valid_until` = agora + 2 h, a cada leitura) de `FontePessoasTeste`, não do 360. Em `real` e `sombra` a fonte se recusa (`ForaDoModoDeTeste`).

**Fantasma de venda em `teste` (risco 103).** Chat de cliente na lista `chats_teste` por engano faria a IA conversar de verdade. Quatro travas, todas por código: (1) `PUT /config/chats_teste`
só aceita chat cuja pessoa está em `pessoas_teste` (`422 pessoa_fora_de_pessoas_teste`) e que nunca teve atendimento `real`/`sombra` (`422 chat_de_cliente`); (2) só a origem `ti` grava a lista
(as outras tomam `403 origem_nao_autorizada`) e a versão guarda `publicado_por`, `motivo` e instante; (3) `POST /atendimentos` e `POST /agendamentos` em chat de teste só abrem com pessoa de
`pessoas_teste`; (4) o `Canal` entrega o texto com o prefixo «[TESTE]» (`texto_de_saida`, B1.6/B6.8 liga).

```bash
K=~/retomada-2809/fila-2910/ia/config/chats-teste.sh
bash $K gerar   --par <chat 24 hex>=P13 --par <outro chat>=P01 --ensaio      # só o plano; troque por --confirmo para escrever ./pessoas_teste.json (0600)
# entregue o arquivo à VPS no caminho de PESSOAS_TESTE_ARQUIVO e REINICIE o orquestrador (o arquivo é lido no boot)
bash $K aplicar --par <chat 24 hex>=P13 --par <outro chat>=P01 --por <login da TI> --confirmo     # PUT chats_teste (token da TI em arquivo 0600)
bash $K limpar  --por <login da TI> --confirmo                                                      # desfaz: chats_teste = []
```

O catálogo e as fixtures (`fixtures/duble/{cliente360_oferta,3rn_calcular,c6_simular}.json`) saem do corpus: `uv run python scripts/gerar_pessoas_teste.py` regrava e `--verificar` (no `check.sh`) reprova
quando divergem. Mudou uma persona do corpus ⇒ regrave, copie `pessoas.json` para o `bancos-duble` (`personas/pessoas_teste.yaml` + `pessoas_teste.sha256`) e rode os dois portões.
