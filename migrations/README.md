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

1. **0001**, por stdin (o `s4_super` pode não ler o home), transação única `-1`:
   `psql -1 -v ON_ERROR_STOP=1 -d ia_atendimento -f - < migrations/0001_esquema.up.sql`
2. **Ledger da 0001** (depois do COMMIT), com o sha256 do arquivo:
   `SET ROLE ia_owner; INSERT INTO ia.migracao (migracao_id, checksum) VALUES ('0001_esquema', '<sha256 de 0001.sha256>');`
3. **0002**, mesmo modo (o arquivo já traz `SET ROLE ia_owner; SET search_path = procrastinate, public;` e o `RESET`, então **não é
   preciso** prefixá-lo como na versão anterior do roteiro; prefixar de novo é inofensivo):
   `psql -1 -v ON_ERROR_STOP=1 -d ia_atendimento -f - < migrations/0002_procrastinate.up.sql`
4. **Ledger da 0002:** `INSERT INTO ia.migracao … ('0002_procrastinate', '<sha256sum migrations/0002_procrastinate.up.sql>')`.
5. **Conferir** (como `ia_app_a`): `ia_ativa = false`, `modo = "duble"`, `ia.migracao` com 2 linhas e checksums iguais aos arquivos;
   `DROP TABLE ia.passo` e `DELETE FROM ia.passo` falham com `permission denied`/`must be owner`.

Reaplicar a **0001** é idempotente (`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`; provado em teste). A **0002 não** se reaplica: o ledger é
quem impede (`aplicar()` do repo faz isso sozinho, mas só para banco **local**).

### Pontos de atenção

- **`search_path` do Procrastinate.** As funções e gatilhos do Procrastinate usam nomes sem schema (`procrastinate_jobs`). Quem opera a
  fila (`ia_app_a/_b`) precisa de `search_path = procrastinate, public` na conexão (`options=-c search_path=...` na URL) ou
  `ALTER ROLE ia_app IN DATABASE ia_atendimento SET search_path = procrastinate, public` (exige `s4_super`, é passo de infra). Sem isso o
  `INSERT` em `procrastinate_jobs` falha no gatilho. As tabelas de `ia` são sempre qualificadas no DDL.
- **Default privileges** da 0001 já cobrem a 0002: tabela nova em `procrastinate` nasce com DML ao `ia_app`; em `ia` não nasce com grant.
- **Texto da conversa e cofre** são cifrados na aplicação (sem pgcrypto); a chave nunca passa pelo banco.
- Uma migração `0003+` nova segue o mesmo caminho: arquivo com `SET ROLE ia_owner`, transação única, ledger com o sha256.

## Verificação local (sem S4)

`bash scripts/aplicar_migracoes_local.sh` sobe um `postgres:18` descartável, aplica as duas migrações com `migracoes.aplicar` e mostra o ledger.
`uv run pytest tests/test_migracoes.py tests/test_esquema.py` prova a aplicação, o ledger, o checksum e os 350 casos.
