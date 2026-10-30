# Revisão adversarial da B1.3 (30/10) — `feat/b1-3-fila`

Revisor de contexto limpo (substitui o Codex, sem cota). Escopo: 4 commits sobre `origin/main` (calendário, chave, fila, jobs, prontidão; 3098 linhas).
Método: leitura do diff inteiro + `bash scripts/check.sh` (verde: 771 testes em 18 s) + experimentos contra Postgres 18 descartável e Procrastinate 3.10.0
real. Os experimentos estão em `~/.cache/rev-b13/test_rev.py` (fora do repositório; rodam com
`uv run python -m pytest -p tests.conftest --import-mode=importlib ~/.cache/rev-b13/test_rev.py -s -c pyproject.toml`). Nenhum arquivo do repo foi editado.

## Veredito: APROVAR COM CORREÇÕES (bloqueiam o merge: A1, A2 e A3)

Contagem: **3 altos** (A1, A2, A3), **5 médios** (A4–A8), **4 baixos** (A9–A12), **1 informativo** (A13).
(Sem item «crítico» de segurança: sem SQL por interpolação, sem segredo ou PII em log, `search_path` correto.)

As 5 correções mais importantes, em ordem:
1. **A1** — `lembrete` agendado com `lock=chat:` trava TODOS os turnos posteriores do chat até a hora do lembrete (head-of-line no Procrastinate).
2. **A2** — `AlreadyEnqueued` engolido dentro de transação do chamador aborta a transação e perde a mensagem gravada junto, sem erro.
3. **A3** — a tarefa das 20:15 não tem recuperação: reinício/deploy a 10 s do horário, ou atraso > 45 min, e `bloqueio_entrada` nunca vira `true`.
4. **A5/A6** — cache de config: gravação do bloqueio ignora o cache do próprio processo; cache envenenado por rollback; limites cruzados com write skew.
5. **A4/A7** — job único de 20/11 duplicado a cada boot; reaper repassa atendimento cujo turno já está na fila.

---

## Achados

### A1 · ALTA · `lembrete` com `lock` + `schedule_at` futuro bloqueia os turnos do chat (head-of-line)
- `src/ia_atendimento/fila.py:150-154` (`agendar_lembrete`), `:70-74` (`reagendar`), `:139-145` (`enfileirar_turno`).
- **Problema.** O `procrastinate_fetch_job_v2` (3.10, `03.03.00_01_pre_priority_lock_fetch_job.sql`) rejeita um job se existir OUTRO job `todo` do mesmo `lock`
  com mesma prioridade e `id` menor, **mesmo agendado para o futuro**. O lembrete (+4 h) é criado depois que a IA responde; qualquer `turno` do cliente
  enfileirado depois tem `id` maior e fica parado até o lembrete rodar. Resultado: o cliente responde às 12:05, a IA só processa às 16:00 (quando o lembrete
  roda, vê `cliente_respondeu`, ignora, e só então libera o turno). Também afeta o lembrete reagendado (`adiar`) e qualquer `iniciar`.
  `readyz` só acusa `fila_parada` depois de 10 min. O reaper (A7) ainda pode repassar o atendimento no meio do atraso.
- **Prova** (`test_hol_lembrete_bloqueia_turno`): defer lembrete +4 h, defer turno, torna o turno vencido, roda worker → `chamadas.turnos == []`,
  jobs: `lembrete todo`, `turno todo`. Os testes da branch não pegam porque `tornar_vencidos` (fixtures_fila.py) vence TODOS os `todo`, inclusive o lembrete de +4 h.
- **Correção.** Não usar `lock` em job agendado para o futuro. Opções: (a) o alarme é um job SEM lock que, ao disparar, enfileira o `lembrete` com
  `lock=chat:` e sem `schedule_*`; (b) guardar `proximo_lembrete_em` no atendimento e um varredor periódico que enfileira o que venceu.
- **Teste que reprova hoje:**
  ```python
  async def test_turno_nao_espera_lembrete_futuro(conninfo_app, conn_super, banco, relogio):
      ch = Chamadas()
      app = criar(conninfo_app)
      chat, a2 = hex24(), uuid.uuid4()
      async with app.open_async():
          await fila.agendar_lembrete(app, uuid.uuid4(), chat, 1, datetime.now(UTC) + timedelta(hours=4))
          await fila.enfileirar_turno(app, a2, chat)
          conn_super.execute(
              "UPDATE procrastinate.procrastinate_jobs SET scheduled_at = now() - interval '1 second' WHERE task_name = 'ia:turno'"
          )
          await rodar(app, montar_servicos(banco, relogio, ch))
      assert ch.turnos == [a2]
  ```

### A2 · ALTA · `AlreadyEnqueued` na transação do chamador: aborta a transação e perde a gravação, calado
- `src/ia_atendimento/fila.py:123-128` (`_enfileirar`), usado com `conexao=` em `:139`, `:148`, `:157`; o docstring do módulo vende «mesma transação».
- **Problema.** O índice único parcial dispara `UniqueViolation` DENTRO da transação do chamador. O Procrastinate converte em `AlreadyEnqueued`, `_enfileirar`
  devolve `None` como se fosse sucesso, mas a transação ficou `InFailedSqlTransaction`; o `COMMIT` vira `ROLLBACK` sem exceção. A 2ª mensagem da rajada
  (exatamente o caso que o `queueing_lock` existe para tratar) some junto com o `INSERT` da mensagem. O teste da branch cobre só um enfileiramento por transação.
- **Prova** (`test_already_enqueued_na_mesma_transacao`): 1º turno commitado; em nova transação `INSERT INTO msg_teste` + `enfileirar_turno(conexao=...)` →
  retorno `None`, saída do bloco sem erro, `SELECT count(*) FROM msg_teste` = **0**. Com um `SELECT 1` após o enfileirar: `InFailedSqlTransaction`.
- **Correção.** Quando `conexao` vier, envolver o `defer_async` em `async with conexao.transaction():` (savepoint) dentro do `try`; o savepoint desfaz só o defer.
  Documentar que o `conexao` precisa estar em transação.
- **Teste que reprova hoje:** o de cima, com `assert count == 1` e `assert retorno is None`.

### A3 · ALTA (operacional) · A tarefa das 20:15 não tem recuperação e é frágil a atraso
- `src/ia_atendimento/jobs.py:230-238` (`executar_bloqueio_diario`), `src/ia_atendimento/fila.py:112-122` (`_registrar_periodicas`), `rodar_worker` (`:165`).
- **Problema 1 (sem catch-up).** `PeriodicDeferrer.get_timestamps` descarta tick mais velho que `max_delay` (10 s, `periodic.py`). Worker reiniciado/deployado entre
  23:15:00 e depois de 23:15:10 UTC (ou fora do ar às 20:15) nunca defere o job do dia; a casa fica aberta até o alerta das 20:20 e a ação manual.
  Hoje é a única trava do B6.7 dentro do orquestrador.
- **Problema 2 (guarda por relógio de execução).** `hora_local.hour != 20` olha a hora em que o handler roda, não a do tick (`timestamp` é recebido e descartado).
  Job atrasado (concurrency padrão do worker = 1, um turno de LLM de 60 s na frente; ou fila parada) que comece às 21:00 BRT levanta `HorarioInesperado` e
  **nunca** grava; sem `retry`, falha única (soluço de conexão) idem.
- **Prova** (`test_bloqueio_atrasado_21h`): `executar_bloqueio_diario(sv, ts_das_23h15_utc)` com relógio 21:05 BRT → `HorarioInesperado`; bloqueio não gravado.
- **Correção.** Decidir pelo `timestamp` do tick (aceitar se o tick é 20:15 local e `agora` ≤ ~07:00 do dia seguinte; gravar `true` é idempotente e seguro),
  `retry` (ex.: 5×, 30 s) na tarefa, e uma reconciliação na subida do worker e a cada hora: «se local ∈ [20:15, 07:45) e `bloqueio_entrada=false` e hoje já passou
  das 20:15 sem `true` → gravar `true`». Rodar o worker com `concurrency` ≥ 2 ou fila separada para periódicas.
- **Teste que reprova hoje:** o acima com `assert gravou is True` (relógio 21:05, `timestamp` das 20:15).

### A4 · MÉDIA · Job único de 20/11 é reenfileirado a cada boot depois de executar
- `src/ia_atendimento/fila.py:157-162` (`agendar_bloqueio_dataprev`).
- **Problema.** `queueing_lock` só vale para `status='todo'`. Depois que o job rodou (`succeeded`), o próximo boot (ainda antes de 23/11 06:00) cria outro, com
  `scheduled_at` no passado, que roda na hora. Se o Danilo/TI abriu a entrada nesse intervalo (ex.: teste do smoke), o boot a fecha de novo.
- **Prova** (`test_dataprev_duplica_apos_executar`): jobs = `[succeeded, todo]`, segundo `agendar_bloqueio_dataprev` devolve id 2 (esperado `None`).
  O teste da branch só prova a idempotência ANTES de executar.
- **Correção.** Checar existência por `(task_name, queueing_lock)` em qualquer status antes de deferir (ou `defer_periodic_job`/chave de idempotência própria).
- **Teste:** o acima com `assert segundo is None`.

### A5 · MÉDIA · Cache de config: três furos
- `src/ia_atendimento/jobs.py:200-215` (`gravar_bloqueio_entrada`), `src/ia_atendimento/chave.py:170-176` (`LeitorConfig.registrar`).
- (a) `gravar_bloqueio_entrada` chama `registrar_config` direto, sem invalidar o `LeitorConfig` compartilhado em `Servicos.leitor_config`: no mesmo processo, até 5 s depois do
  `true` o leitor ainda devolve `False` (`test_cache_stale_apos_gravar_bloqueio`: `leitor.valor(...)` → `False`). Mesmo vale para qualquer PUT feito por `registrar_config` em vez de
  `leitor.registrar`; a API deveria expor uma só porta de escrita.
- (b) `registrar` atualiza o cache DEPOIS do `INSERT`, mas se o chamador estiver numa transação maior que dá rollback, o cache guarda por 5 s uma versão que não existe
  (`test_cache_envenenado_por_rollback`: cache = 99, banco = 10). Para as chaves de segurança (`ia_ativa`, `modo`, `bloqueio_entrada`) 5 s com valor fantasma é pior que 5 s velho.
- (c) cache de `None` também por 5 s (`vigente` guarda `lida=None`): chave nova criada some por 5 s.
- **Correção.** `gravar_bloqueio_entrada` usar `leitor.registrar`; em `registrar`, só tocar o cache se `conn.info.transaction_status == IDLE` após o `INSERT` (ou invalidar com `pop` em vez de gravar);
  não cachear `None`.
- **Testes:** os dois acima com a asserção invertida.

### A6 · MÉDIA · Limites cruzados com write skew
- `src/ia_atendimento/chave.py:124-133` (`_conferir_limites_cruzados`) — `agenda_max_dia ≤ max_disparos_dia`.
- **Problema.** Cada escrita lê a outra chave em `READ COMMITTED` sem trava; duas escritas concorrentes passam as duas. `(agenda_max_dia, max_disparos_dia) = (9, 6)` ficou gravado.
  O CAS por `versao` não protege porque as chaves são linhas diferentes.
- **Prova** (`test_write_skew_limites_cruzados`): A abre transação e grava `agenda_max_dia=9` (vigente `max_disparos_dia=10`); B grava `max_disparos_dia=6` (vê `agenda_max_dia=5`); A comita → 9 > 6.
- **Correção.** `pg_advisory_xact_lock(hashtext('ia.config.limites'))` no início do `registrar_config` das duas chaves (ou `SELECT ... FOR UPDATE` na linha vigente do par).
- **Teste:** o acima.

### A7 · MÉDIA · Reaper repassa atendimento com turno já enfileirado
- `src/ia_atendimento/jobs.py:158-163` (`_SQL_LEASES`).
- **Problema.** O `NOT EXISTS` só olha jobs `doing`. Lease vencido + `turno` `todo` já vencido (fila congestionada, A1, concurrency 1) → o reaper devolve `repassar` e o turno
  chega depois a um atendimento já repassado. Combinado com A1 isso vira repasse falso de quem acabou de responder.
- **Prova** (`test_reaper_com_turno_todo_pendente`): `executar_reaper_lease` devolve 1 / `['repassar']`.
- **Correção.** Tratar `todo` com `scheduled_at <= now()` (e `iniciar`) do mesmo `lock` como «em curso» (`status IN ('doing','todo')` com `scheduled_at <= now()`), ou fazer o próprio turno renovar o lease ao enfileirar.
- **Verificado OK:** `lease_ate == agora` não é tratado (estrito `<`); `pausado`/`reservado` de agendamento só quando o lease EXPIROU de fato (teste da branch cobre).

### A8 · MÉDIA · `readyz`: exceção, relógios misturados e fila falhando
- `src/ia_atendimento/prontidao.py:121-129` (`readyz_por_dsn`), `:78-98` (`ler_prontidao`).
- (a) só captura `psycopg.OperationalError`. Esquema do Procrastinate ausente/parcial (`UndefinedTable`), permissão (`InsufficientPrivilege`) ou `QueryCanceled` propagam e a rota devolve 500, não 503 com
  `falhas_duras`. Prova: `DROP TABLE procrastinate_workers` → `readyz_por_dsn` levanta `UndefinedTable`. Sem `statement_timeout`/`options` o `/readyz` também pendura se o banco travar.
  Correção: capturar `psycopg.Error` → `banco_inacessivel`/`erro_de_consulta`, `options=-c statement_timeout=2000`.
- (b) heartbeat e `scheduled_at` são gravados pelo relógio do BANCO e comparados com `relogio.agora()` da aplicação. Defasagem de 30 s entre hosts derruba a prontidão (limite = `stalled_worker_timeout`)
  sem que nada esteja errado. Usar `now()` no SQL para esses dois sinais (a view já usa).
- (c) job `failed` em massa (ex.: `ServicoNaoConfigurado`, cota do modelo) não é sinal: o worker vivo e a fila sem `todo` velho dão `pronto=True` com nada sendo processado. Acrescentar `falhados_15min` (mole acima de N, duro acima de M).
- Verificado OK: o worker real do 3.10 grava `procrastinate_workers.last_heartbeat` (checado com `run_worker_async` de verdade, 1 s); o round-trip LISTEN/NOTIFY confere o token.

### A9 · BAIXA · `cron_utc` com data de referência fixa
- `src/ia_atendimento/fila.py:112` (`referencia = date(2026, 11, 12)`) e docstring de `calendario.cron_utc` («o cron é regerado no boot»).
- Hoje correto (`15 23 * * *`; sem horário de verão desde 2019). Se voltar, `cron_utc(20:15, 2018-12-01)` dá `15 22`; mas a data é constante, então o «regerado no boot» do docstring não acontece:
  o cron fica errado metade do ano e só a guarda de A3 (que falha alto) segura. Correção: passar `date.today()` do relógio injetado e, ou documentar que DST exige mudança de código (a guarda é o aviso),
  ou registrar 2 crons (22:15 e 23:15) com a guarda decidindo. Teste: `_registrar_periodicas` com relógio em 2018-12-01 deve produzir `15 22 * * *`.

### A10 · BAIXA · `tzdata` não declarado
- `pyproject.toml`; `src/ia_atendimento/calendario.py:27` (`FUSO = ZoneInfo(...)` no import: sem base de fusos o pacote inteiro não importa).
- Hoje funciona: `tzdata` entra no lock por `python-dateutil` (transitivo) e está no venv copiado para a imagem; além disso `python:3.12-slim-bookworm` tem `/usr/share/zoneinfo` (testado). Falta explícito e teste.
  Correção: `"tzdata>=2026.1"` em `dependencies` (não cai se um dia sair o `dateutil`) + teste `ZoneInfo("America/Sao_Paulo")` com `ZONEINFO`/`TZPATH` vazios. O `Dockerfile` da `feat/esteira` usa `python:3.13-slim` (não testei esta tag).

### A11 · BAIXA · Escopo e boot
- Spec da B1.3 lista `encerrar_vacuo`, `encerrar_por_chave` e `conferir_esquema_no_boot`; nenhum existe na branch (readyz confere checksum, mas não há tarefa de boot). Se ficam para B1.6, dizer no CHANGELOG.
- `garantir_defaults` e `agendar_bloqueio_dataprev` não têm chamador: «job de 20/11 agendado» (aceite da B6.7) não está atendido por nada que rode. Definir o ponto de boot (B1.5).
- `rodar_worker` sem `concurrency`, sem `retry` padrão nas tarefas (um `turno` que falha uma vez fica `failed` até o reaper repassar) e sem `queueing_lock` no `bloqueio_2015`. Decidir e registrar.
- `LIMITE_LOTE` do reaper = 200: acima disso o resto espera o próximo minuto (ok), mas o laço `tratar_lease_vencido` é sequencial.

### A12 · BAIXA · Testes que não pegam (fixtures e tautologias)
- `tornar_vencidos` vence todo `todo` do banco: esconde A1 em `test_lock_por_chat_serializa` e `test_iniciar_e_lembrete_rodam_com_lock_do_chat` (o lembrete de +4 h é «vencido» à força).
- `test_bloqueio_entrada_nao_encerra_abertos_nem_pausados` chama só `bloqueio_entrada()`, uma função de leitura: não tem como encerrar nada. O risco real está nos consumidores (reaper, expirar, lembrete); falta teste que rode o reaper/lembrete com a chave ligada.
- `test_tarefas_periodicas_registradas_com_o_cron_certo` compara `cron_utc` com ele mesmo (a literal `"15 23 * * *"` salva); nenhum teste roda o `PeriodicDeferrer` (eu rodei: o reaper sai `succeeded` no 1º tick, então a fiação com `timestamp` e `pass_context` está certa).
- `test_job_unico_de_2011` só prova a idempotência antes de executar (A4); `inserir_job` da poda cria 1 evento por job, o real tem 3 (passa igual, mas não é o dado real; ver `teste-com-dado-real`).
- `test_pk_perdida...` usa `monkeypatch` da leitura para forçar a PK: bom, mas o CAS real concorrente (duas conexões) só existe nos meus experimentos (passou, ver abaixo).

### A13 · INFO · Higiene
- `procrastinate_periodic_defers` não é podada: ~1440 linhas/dia (reaper a cada minuto), com `job_id` virando `NULL`. Inofensivo por anos; incluir no `podar_jobs` com `defer_timestamp` < corte.
- O worker do Procrastinate loga `call_string` com argumentos: `chat_id` e `atendimento_id` aparecem em log (ids internos, não CPF/telefone). Aceitável; se o `chat_id` vier a ser derivado do telefone, mascarar.
- `validar_calendario_bloqueio` exige para sempre os feriados de 2026 e a janela DATAPREV; depois de 23/11 toda versão nova de config terá de carregar uma janela passada. Intencional («piso»), mas anotar.

---

## O que foi provado SEM achado (rodado)

| Tema | Resultado |
|---|---|
| Fronteiras do calendário | 20:00:00 BRT = fora (próx. 08:00 do dia seguinte); 19:59:59.999999 = dentro; 08:00:00 = dentro; 07:59:59 = fora; 00:00 UTC (21:00 BRT do dia anterior) = fora; sáb 23:59:59 BRT → seg 08:00; domingo e 02/11, 20/11 bloqueados; 23/11 06:00 BRT fora, 08:00 dentro. |
| Dia de negócio | `limites_do_dia`: 23:59:59 BRT (02:59:59Z) cai no dia 17, 00:00 BRT (03:00Z) no dia 18; intervalo [03:00Z, 03:00Z). Não usa fuso do banco nem `now()`. |
| CAS de config | Duas escritas concorrentes (A segura a transação, B espera na PK): B recebe `ConfigCorrida`, versão vigente 2 = valor de A. Sem perda e sem 3ª versão. |
| `lock` por chat | Dois apps/workers (`concurrency=4` cada), 8 turnos do mesmo chat: pico de execução simultânea = 1. (O furo é a ordem, A1, não a exclusão.) |
| Rajada | `queueing_lock=turno:{chat}` + `schedule_in=3 s` junta mensagens em 1 job fora de transação; mensagem durante o turno em curso gera outro job (correto). |
| Poda | Nunca apaga `todo`/`doing`; `failed` de 20 d fica, de 31 d sai; concluído de 6 d fica, de 8 d sai; eventos saem por CASCADE; `periodic_defers.job_id` vira `NULL`. O `ia_app_a` tem permissão. |
| Reaper | Não age sobre pausado/agendado em dia; não age sobre turno `doing`; `lease_ate == agora` fica de fora. |
| `bloqueio_entrada=true` | Nenhum código da branch encerra, repassa ou altera atendimento; estados e versões idênticos antes e depois (e nenhum job novo). |
| `search_path` | `conninfo_da_fila` soma `-c search_path=procrastinate,public` a `options` existentes (o último vence), aceita `postgresql+psycopg://` e pares `chave=valor`, esconde a senha na mensagem de erro. |
| SQL | Sem f-string/`%` em SQL no `src/`; só parâmetros `%s` e `sql.Identifier` (LISTEN). F-strings de SQL só nas fixtures de teste (colunas constantes). |
| Segredo/PII em log | Nenhum `log.*` carrega DSN, valor de config ou texto; exceções usam `type(erro).__name__`. |
| Heartbeat | Worker real do 3.10 insere/atualiza `procrastinate_workers`; `HEARTBEAT_MAX_S=30` = `stalled_worker_timeout` (folga de 20 s sobre o intervalo de 10 s). |
| Periódicas | Com `com_periodicas=True` o 1º tick enfileira e executa `reaper_lease` (AlreadyEnqueued do `queueing_lock` é tratado pelo deferrer). |

## Plano de correção sugerido (ordem)
1. A2 (savepoint) e A1 (alarme sem lock) — bloqueiam B1.5/B1.6, porque o chamador (API) grava a mensagem e enfileira na mesma transação, e o lembrete é a primeira tarefa agendada.
2. A3 (tick/retry/reconciliação) + A4 antes do ensaio a seco de 13/11 e do job de 20/11.
3. A5, A6, A7, A8: pequenos, cada um com o teste acima.
4. A9–A13: backlog da B1.3 ou do B1.5.

## Reprodução rápida
```
cd ~/wt-ia/ia-atendimento-b13
uv run python -m pytest -p tests.conftest --import-mode=importlib ~/.cache/rev-b13/test_rev.py -s -c pyproject.toml -p no:cacheprovider
# falham hoje (= achados): hol_lembrete, dataprev_duplica, cache_stale, cache_envenenado, write_skew, bloqueio_atrasado_21h, already_enqueued, reaper_com_turno_todo, readyz_schema_ausente
# passam (= provas sem achado): fronteiras, cas_duas_escritas, dois_workers_mesmo_chat, worker_heartbeat_real, periodica_roda, conninfo, reaper_lease_igual_agora
```

---

## Resposta do autor (30/10)

Todos os testes novos estão em `tests/test_revisao_b13.py` (portados dos experimentos do revisor, vermelhos antes da correção) e `tests/test_jobs.py`/`test_calendario.py` onde indicado.
`tornar_vencidos` (A12) agora só vence a espera curta (`scheduled_at < now() + 1 min`), então jobs agendados para longe não são vencidos à força.

| Achado | Correção | Teste |
|---|---|---|
| A1 | `agendar_lembrete` agenda o **alarme** (`ia:alarme_lembrete`, sem lock); ao disparar, enfileira `ia:lembrete` com `lock=chat:` e sem `schedule_*` (`enfileirar_lembrete`) | `test_a1_turno_nao_espera_lembrete_futuro`, `test_a1_alarme_ao_disparar_enfileira_o_lembrete_com_lock` |
| A2 | `_enfileirar` com `conexao=` roda o defer em `conexao.transaction()` (savepoint): `AlreadyEnqueued` desfaz só o defer | `test_a2_already_enqueued_na_mesma_transacao_nao_perde_a_gravacao` |
| A3 | `executar_bloqueio_diario` decide pelo **tick** (`timestamp`): atrasado até 11h30 ainda grava, tick fora das 20h falha alto; `retry` (5×, 30 s, só falha transitória de banco/rede/corrida) em `bloqueio_2015` e `bloqueio_dataprev`; `reconciliar_bloqueio_diario` na subida do worker (`rodar_worker`) e a cada 5 min (periódica), respeitando quem abriu depois do tick; `rodar_worker` com `concurrency=4` | `test_a3_*` (5 testes) |
| A4 | `agendar_bloqueio_dataprev` consulta o job por `(task_name, queueing_lock)` em qualquer status antes de deferir | `test_a4_job_de_2011_nao_e_reenfileirado_depois_de_executar` |
| A5 | (a) `gravar_bloqueio_entrada` escreve por `LeitorConfig.registrar`; (b) `registrar` só cacheia se a conexão voltou a IDLE (senão invalida a chave); (c) `None` não é cacheado | `test_a5_*` (3 testes) |
| A6 | `pg_advisory_xact_lock` do par `agenda_max_dia`/`max_disparos_dia` no início de `registrar_config` | `test_a6_limites_cruzados_com_escritas_concorrentes` |
| A7 | `_SQL_LEASES` trata `todo` vencido do mesmo `lock` de chat (e `doing`) como turno na fila | `test_a7_reaper_nao_repassa_chat_com_turno_todo_vencido` |
| A8 | `readyz_por_dsn` captura `psycopg.Error` (`erro_de_consulta`) e usa `statement_timeout` de 2 s; batimento/fila comparados com o `now()` do banco (sem relógio da aplicação); `falhados_15min` (mole; duro `jobs_falhando` acima de 20) | `test_a8_*` (3 testes) |
| A10 | `tzdata==2026.6` declarado (já estava no lock, via `dateutil`) | `test_base_de_fusos_nao_depende_do_sistema` |
| A13 (parcial) | `podar_jobs` apaga `procrastinate_periodic_defers` sem job e mais velhos que a retenção dos falhos | `test_podar_apaga_o_rastro_antigo_das_periodicas` |
| A9, A11, A12 (resto), A13 (log de args) | Não feitos agora: `cron_utc` segue com data de referência fixa (a guarda do tick falha alto se o horário de verão voltar); `encerrar_vacuo`, `encerrar_por_chave`, `conferir_esquema_no_boot` e os chamadores de `garantir_defaults`/`agendar_bloqueio_dataprev` ficam para B1.5/B1.6; guarda do teste de bloqueio com consumidores (reaper/lembrete com a chave ligada) fica no backlog | n/a |

Nota: o guarda `test_relogio_injetado` agora permite `now()` do banco só em `prontidao.py`, que compara instantes gravados pelo próprio banco (A8b).
