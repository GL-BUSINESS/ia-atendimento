# Migrações

> **Só documentação.** Nada deste arquivo foi aplicado na S4. Aplicar é do **dono**, com o «sim» dele, pelos kits (roteiro
> §0.3 regra 6, A4.6). Este repositório nunca conecta na S4.

| Arquivo | O que é | Edita? |
|---|---|---|
| `0001_esquema.up.sql` | bloco `sql` do §4 do estudo I (rodada 3c), byte a byte; schemas `ia` e `procrastinate`, 18 tabelas, 1 view, 2 funções de poda, grants, seeds | **Nunca.** O estudo I é a fonte; mudou o desenho = 0003+ |
| `0001.sha256` | `sha256sum` do arquivo acima (`5d1ceec1…3808`) | só junto com uma nova extração do estudo |
| `0002_procrastinate.up.sql` | fila de jobs (Procrastinate 3.10.0), gerada por `scripts/gerar_0002.py` | só regerar ao trocar a versão **antes** de aplicada |

Convenções: nome `NNNN_nome.up.sql` (casa com o CHECK de `ia.migracao.migracao_id`), numeração contínua, sem `down`
(desfazer é decisão do dono: `DROP DATABASE … WITH (FORCE)` só com autorização nova). Cada arquivo faz o próprio `SET ROLE ia_owner`
e roda em **uma transação**. O checksum no ledger é o sha256 dos **bytes** do arquivo.

## Ordem de aplicação na S4 (texto para o dono; `psql` local como `s4_super` + `SET ROLE ia_owner`)

Pré-requisitos (A4.3, já feitos antes): papéis `ia_owner` (NOLOGIN, dono do banco), `ia_app`, `ia_leitura`, `ia_qualidade` (grupos
NOLOGIN) e os logins `_a`/`_b`; database `ia_atendimento` com dono `ia_owner`; `CONNECT` só para os grupos. Quem aplica é `s4_super`
(`sudo -n -u s4_super psql -X -q -p 5434`); o arquivo troca para `ia_owner` sozinho.

Cada arquivo e a linha do ledger vão **na mesma transação** (`psql -1`): ou entra tudo ou nada, como no `aplicar()` do repo (que o
CLI só roda em banco local). Não existe janela «aplicada mas sem ledger». `$S4` é o `ssh` do dono; o arquivo segue por stdin (o `s4_super`
pode não ler o home).

1. **0001 + ledger**, transação única `-1`:
   ```bash
   SUM1=$(sha256sum migrations/0001_esquema.up.sql | cut -d' ' -f1)
   { cat migrations/0001_esquema.up.sql
     printf "SET ROLE ia_owner; INSERT INTO ia.migracao (migracao_id, checksum) VALUES ('0001_esquema', '%s');\nRESET ROLE;\n" "$SUM1"; } \
     | $S4 'sudo -n -u s4_super psql -X -q -1 -v ON_ERROR_STOP=1 -p 5434 -d ia_atendimento -f -'
   ```
2. **0002 + ledger**, igual (o arquivo já traz `SET ROLE ia_owner; SET search_path = procrastinate, public;` e o `RESET`):
   ```bash
   SUM2=$(sha256sum migrations/0002_procrastinate.up.sql | cut -d' ' -f1)
   { cat migrations/0002_procrastinate.up.sql
     printf "SET ROLE ia_owner; INSERT INTO ia.migracao (migracao_id, checksum) VALUES ('0002_procrastinate', '%s');\nRESET ROLE;\n" "$SUM2"; } \
     | $S4 'sudo -n -u s4_super psql -X -q -1 -v ON_ERROR_STOP=1 -p 5434 -d ia_atendimento -f -'
   ```
3. **`search_path` da fila**, por **login** (passo de infra, `s4_super`, depois do «sim»; ver «Pontos de atenção»):
   ```sql
   ALTER ROLE ia_app_a IN DATABASE ia_atendimento SET search_path = procrastinate, public;
   ALTER ROLE ia_app_b IN DATABASE ia_atendimento SET search_path = procrastinate, public;
   ```
4. **Conferir** (como `ia_app_a`): `ia_ativa = false`, `modo = "duble"`, `ia.migracao` com 2 linhas e checksums iguais aos arquivos;
   `DROP TABLE ia.passo` e `DELETE FROM ia.passo` falham com `permission denied`/`must be owner`.

Reaplicar a **0001** é idempotente (`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`; provado em teste). A **0002 não** se reaplica: o ledger é
quem impede (`aplicar()` do repo faz isso sozinho, mas só para banco **local**).

### Pontos de atenção

- **`search_path` do Procrastinate.** As funções e gatilhos do Procrastinate usam nomes sem schema (`procrastinate_jobs`). Quem opera a
  fila (`ia_app_a/_b`) precisa de `search_path = procrastinate, public` na conexão (`options=-c search_path=procrastinate,public` na URL)
  ou `ALTER ROLE ia_app_a IN DATABASE ia_atendimento SET search_path = procrastinate, public` (e `ia_app_b`; exige `s4_super`, é passo de
  infra). **O `ALTER ROLE` tem de ser no LOGIN, não no grupo `ia_app`:** configuração de papel não é herdada por quem é membro dele
  (verificado em PG 18: o login `ia_app_a` continua com `"$user", public`; `tests/test_migracoes.py` prova). Sem o `search_path` o
  `INSERT` em `procrastinate_jobs` falha no gatilho. As tabelas de `ia` são sempre qualificadas no DDL.
- **Default privileges** da 0001 já cobrem a 0002: tabela nova em `procrastinate` nasce com DML ao `ia_app`; em `ia` não nasce com grant.
- **Texto da conversa e cofre** são cifrados na aplicação (sem pgcrypto); a chave nunca passa pelo banco.
- Uma migração `0003+` nova segue o mesmo caminho: arquivo com `SET ROLE ia_owner`, transação única, ledger com o sha256.

## Verificação local (sem S4)

`bash scripts/aplicar_migracoes_local.sh` sobe um `postgres:18` descartável, aplica as duas migrações com `migracoes.aplicar` e mostra o ledger.
`uv run pytest tests/test_migracoes.py tests/test_esquema.py` prova a aplicação, o ledger, o checksum e os 350 casos.
