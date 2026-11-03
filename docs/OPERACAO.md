# Operação do `ia-atendimento` (fundação)

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
```

**Conferir** (como `ia_app_a`, da VPS): `select migracao_id, left(checksum,8) from ia.migracao` (3 linhas); `select valor from
ia.config_versao where nome='ia_ativa'` = `false` e `nome='modo'` = `"duble"`; `DROP TABLE ia.passo` falha; `ia_app_a` sem `DELETE`; `ia.atendimento.ultimo_cliente_em` existe e um `INSERT` de `chats_teste` com 21 ids ou id fora de 24 hex minúsculo é recusado
(`config_versao_chats_teste_check`). Depois do fim, `ia_app` ainda grava `contrato_id`, `pii_auditoria`, `sinais_cliente`, `ultimo_cliente_em` e os contadores; `estado`, `desfecho`,
`encerrado_em`, `estado_conversa`, `motivo_desfecho`, `contexto_codigos` e `repasse_modo`/`repasse_consultor_ref` de um encerrado ficam congelados
(trigger `atendimento_terminal_absorvente`). A 0003 é aditiva: o código sem ela segue funcionando, e ela é inofensiva sem o código novo (desfazer = parar o app).

**Se der errado:** erro no meio de um arquivo (ou no INSERT do ledger) → a transação única (`-1`) desfaz tudo, inclusive o ledger; reaplicar
a 0001 é idempotente; a 0002 e a 0003 já aplicadas **não** se reaplicam (o ledger é a verdade; `ADD CONSTRAINT` não é idempotente). **Desfazer:** `DROP DATABASE … WITH (FORCE)` só com autorização nova do dono (estudo E «Desfazer tudo» 1).

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

## 5. Agente do turno: modelo, preço e traces (B1.4)

Nada disto liga sozinho: a IA nasce desligada (`ia_ativa=false`, `modo="duble"`) e **não existe chave de provedor** neste repositório. O que o orquestrador lê
do ambiente (nomes em `.env.example`; segredos só no `.env` ou no arquivo 0600 do cofre da VPS, nunca no git, no log nem no span):

| Variável | Padrão | Observação |
|---|---|---|
| `MODELO_NOME` | `deepseek-v4p1-flash-1017` | nome lógico; é o que a config (`modelo_por_faixa`) e o passo `decisao` gravam |
| `MODELO_ROTEADOR` | `accounts/fireworks/routers/deepseek-v4p1-flash-1017-us` | o que vai na requisição; precisa terminar em `-us` e ser o do `MODELO_NOME` (o boot recusa o endpoint «global») |
| `MODELO_BASE_URL_1` | `https://us.api.fireworks.ai/inference/v1` | só este host (ou loopback, para o dublê do modelo) |
| `MODELO_API_KEY_1` | — | `SecretStr`, ≥ 16 caracteres; sai de `Settings` e vai só no cabeçalho `Authorization` da chamada; o scrubber a troca por `[SEGREDO]` em span e log |
| `MODELO_RACIOCINIO_OFF` | `reasoning_effort_none` | **HIPÓTESE.** `reasoning_effort_none` envia `{"reasoning_effort": "none"}`; `thinking_disabled` envia `{"thinking": {"type": "disabled"}}`. A **A2.9** diz qual o V4.1 Flash no Fireworks aceita: trocar aqui, sem mexer em código |
| `MODELO_TEMPERATURA`, `MODELO_MAX_TOKENS` | `0.3`, `400` | saída ≤ 220 tokens (H §3.1) com folga para o JSON do `Turno`; vai como `max_tokens` |
| `MODELO_TIMEOUT_S` | `8` (máx. 10) | tempo de UMA chamada, no cliente HTTP e no turno; o turno inteiro tem esse tempo × 2 (`output_retries=1`). O SDK **não** repete 429/5xx/conexão (`max_retries=0`); não existe segundo provedor. Calibrar na A2.9 |
| `PRECO_IN_USD`, `PRECO_CACHE_USD`, `PRECO_OUT_USD`, `CAMBIO` | `0.45`, `0.009`, `1.80`, `5.3346` | US$/1M tokens do Fireworks só-EUA (estudo G §4) e câmbio de `premissas.json`; grava `custo_brl` no passo `decisao` (contrato 08 §9). ≤ 0 derruba o boot. **Conciliar com a fatura** |
| `PHOENIX_ENDPOINT` | vazio | vazio = nada é exportado (nem provedor de traces é criado). Com valor: OTLP/HTTP em `<endpoint>/v1/traces`, sem credencial na URL |
| `PHOENIX_PROJETO`, `PHOENIX_API_KEY` | `ia-atendimento`, vazio | a chave, se existir, vai como `Authorization: Bearer` |

- **Um provedor só.** Falha de rede, HTTP, tempo ou saída inválida vira `ErroDoModelo` (mensagem fixa, nunca o corpo da resposta) e sobe: o processador (B1.6) conta a
  falha e, na segunda, repassa ao vendedor. **Não há `FallbackModel`.** Trocar de provedor (reserva Together só-EUA, Gemini) é mudança de código revisada.
- **Raciocínio.** Se a resposta trouxer tokens de raciocínio o turno vale, mas sai o alerta `alerta_raciocinio` (log e evento do span `ia.turno`): custo e latência
  subiriam calados. `raciocinio=true` em `modelo_por_faixa` é recusado (`RaciocinioNaoLiberado`) até a F3 aprovar.
- **PII em span e log.** Todo span passa por `mascarar()` (CPF, telefone, e-mail, CEP, UUID, 8+ dígitos) e pelo registro de segredos antes de sair do processo; o
  `LogRecord` de todo logger também. É a segunda cerca: a primeira é o contexto, que nunca monta o prompt com esses dados. Para ver o texto do cliente no Phoenix o TI
  usa o «ver bruto» (14 d); aqui nunca.
- **Ferramentas.** `criar_agente(..., ferramentas={"T3": função})` é o único caminho: o nome precisa ter projeção em `PROJECAO_DAS_FERRAMENTAS` (senão o agente nem sobe) e o retorno só volta ao
  modelo projetado, mascarado e auditado. Ferramenta nova entra com a projeção dela, no mesmo PR.
- **E5 (coleta de dados).** `montar_contexto` oculta a mensagem do cliente (`[dado:<campo>]`): ela é o valor do campo. Só chega ao modelo com `desvio_liberado=True`, e quem decide o desvio é o processador.
- **Teto de 4 mil tokens** é **estimativa** (`tokens.EstimadorPorCaracteres`: 3 caracteres/token + 10%). O tokenizer do DeepSeek ainda não foi medido (H §3.1, HIPÓTESE):
  a **B8.2** mede e troca o estimador (`EstimadorPorCodificador`) sem mexer no resto.
- **Sem custo de rede nos testes.** `bash scripts/check.sh` roda o agente contra `httpx.MockTransport` e o `ProvedorFalso`; nenhum teste abre conexão externa.
- Quando a chave existir (pendência do dono, estudo G §5): o kit grava `MODELO_API_KEY_1` fora do chat, o **teste de aceitação da §6 do estudo G** (20 chamadas sintéticas)
  decide a forma de `MODELO_RACIOCINIO_OFF`, `NativeOutput` × Tool Output e o preço real; só depois a IA sai do dublê.

## 6. Quando o checksum divergir

`aplicar()`/`conferir()` levantam `ChecksumDivergente` e **param**: alguém editou uma migração já aplicada. Não corrija o DDL: restaure o arquivo
(`git checkout`) ou, se o desenho mudou, crie a migração seguinte (`0004+`) e reabra o estudo I. Na dúvida, abra achado na Parte F do roteiro.

## 7. Trocar a versão do Procrastinate

Antes de aplicada: `uv add procrastinate==X`, `uv run python scripts/gerar_0002.py`, revisar o diff e commitar. Depois de aplicada: **não** regerar a 0002; o diff da pasta
de migrações do pacote vira a migração seguinte (`0004+`).

## 8. Release

Tag semver e `gh release create` só depois da revisão (rodízio: quem implementa não revisa). Esta fundação é a `v0.1.0`; **a tag ainda não foi criada**.
