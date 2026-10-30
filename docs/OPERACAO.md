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

Não use o grupo `ia_app` no `ALTER ROLE`: configuração de papel não é herdada pelos logins membros (`tests/test_migracoes.py` prova).

## 5. Quando o checksum divergir

`aplicar()`/`conferir()` levantam `ChecksumDivergente` e **param**: alguém editou uma migração já aplicada. Não corrija o DDL: restaure o arquivo
(`git checkout`) ou, se o desenho mudou, crie a migração seguinte (`0004+`) e reabra o estudo I. Na dúvida, abra achado na Parte F do roteiro.

## 6. Trocar a versão do Procrastinate

Antes de aplicada: `uv add procrastinate==X`, `uv run python scripts/gerar_0002.py`, revisar o diff e commitar. Depois de aplicada: **não** regerar a 0002; o diff da pasta
de migrações do pacote vira a migração seguinte (`0004+`).

## 7. Release

Tag semver e `gh release create` só depois da revisão (rodízio: quem implementa não revisa). Esta fundação é a `v0.1.0`; **a tag ainda não foi criada**.
