# Revisão 2 da B1.3 (30/10) — `feat/b1-3-fila` @ 8b9dbc6

Revisor adversarial de contexto limpo. Escopo: `git diff e7be601..8b9dbc6` (correções da Revisão 1), spec B1.3/B6.7 e T5.
Método: `bash scripts/check.sh` (verde, 790 testes em 20 s), Postgres 18 descartável + Procrastinate 3.10.0 real, 29 experimentos novos
(`~/.cache/rev-b13/test_rev2.py` e `test_rev2b.py`) e 20 mutações da correção em cópia do repo (script em `/tmp/.../scratchpad/mut/mut.py`). Nada do repo foi editado.
Rodar: `uv run python -m pytest -p tests.conftest --import-mode=importlib ~/.cache/rev-b13/test_rev2.py -s -c pyproject.toml -p no:cacheprovider`.

## Veredito: APROVAR COM CORREÇÕES (nenhum bloqueante; N1, N2 e N3 antes do ensaio de 13/11)

A1–A8 estão fechados de verdade (mutação: desfazer cada correção reprova ao menos um teste, com 5 exceções de cobertura listadas em N4).
Achados novos: 0 altos, 3 médios (N1–N3), 4 baixos (N4–N7), 1 informativo (N8).

## 1. A1–A8 confirmados e variações tentadas

| Achado | Variação tentada | Resultado |
|---|---|---|
| A1 | 2 alarmes (+4 h, +8 h) + turno + `expirar_parados` no mesmo chat | turno e `expirar` rodam; os 2 alarmes ficam `todo` sem lock |
| A1 | alarme sem lock dispara com turno `doing` do mesmo chat (turno de 2,5 s) | alarme `succeeded`; o `lembrete` só roda DEPOIS do fim do turno (ordem `turno_fim` < `lembrete`) |
| A1 | cadeia inteira pela fila real: alarme → `lembrete` → `adiar` (20:30) → novo alarme 08:00 → `lembrete` envia 1×, `janela_24h=True` | ok (ver §2: nenhum teste do repo cobre isso) |
| A1 | `turno` agendado +3 s (id menor) × `lembrete_exec` imediato (id maior) | o lembrete espera os 3 s da rajada (HOL residual de 3 s: aceitável, ver N8) |
| A2 | conexão em autocommit | 2º `enfileirar_turno` devolve `None`, conexão segue utilizável; chat novo enfileira |
| A2 | transação externa + `rollback()` | o job some junto com o `INSERT` (0 jobs do chat); a gravação da mensagem continua atômica |
| A3 | `PeriodicDeferrer` com boot 9 s / 11 s / 120 s / 599 s / 601 s / 3600 s depois do tick | deferido até 599 s; perdido a partir de 601 s (`max_delay` = **600 s**, ver N8) |
| A3 | reconciliação às 20:16, 23:59, 07:44, 07:45, 08:00 e 19:59 locais | `True, True, True, False, False, False` (fronteira de 11h30 exata) |
| A3 | dois workers subindo juntos (threads) | `[True, False]`: uma versão só, sem reconciliação duplicada (CAS + releitura) |
| A3 | `retry` de verdade (2 `OperationalError` e depois ok; `HorarioInesperado`) | 1ª falha vira `todo` com `attempts=1` e `scheduled_at` futuro; `HorarioInesperado` vira `failed` sem repetir |
| A3 | `rodar_worker` reconcilia na subida | ok (21:16 locais → `bloqueio_entrada=true`) |
| A4 | boot 3× depois de executar; 3 boots em paralelo antes de executar | `[1, None, None]`; depois `None, None, None` (e `None` também com o job `failed`, ver N5) |
| A5 | PUT e leitura no mesmo processo / em outro `LeitorConfig` / conexão não-autocommit com leitura prévia e rollback | `True` / `False` por ≤ 5 s e `True` aos 6 s (TTL esperado) / `10` (sem veneno) |
| A6 | pares em ordem inversa, pares válidos, mesma chave, concorrentes | `(5,6)` com a 2ª recusada; `(7,8)` ambas gravadas; mesma chave serializa; sem deadlock |
| A7 | turno `todo` vencido × agendado +2 s × +3 s (relógio da fixture) | 0 repasses × **1** × **1** (ver N2) |
| A8 | esquema ausente; DSN com `options` prévias; `statement_timeout`; job `failed` de verdade | `erro_de_consulta`; `SHOW statement_timeout`=2 s e `options` prévias preservadas; `falhados_15min=1` com evento real |
| Lock | `concurrency=4`, 2 workers, 3 chats × (turno, iniciar, lembrete) com 0,15 s cada | pico simultâneo por chat = 1 (o `fetch_job_v2` rejeita por `doing` e por `todo` de id menor) |

## 2. `tornar_vencidos` só vence espera < 1 min: esconde algum caso real?

Sim, um: a cadeia do lembrete de 4 h nunca roda inteira no repo. `test_iniciar_e_lembrete_rodam_com_lock_do_chat` e `test_a1_alarme_ao_disparar...`
forçam o alarme com `UPDATE` explícito e só provam alarme → `lembrete_exec`. Ninguém roda `lembrete` → `adiar` → `reagendar` → novo alarme → 2º `lembrete`
na fila real (a única prova é o meu `test_e2e_adiar_pela_fila_real`, que passa). Também não há teste de que o `retry` (espera 30 s) funciona em tempo:
a espera de 30 s cai na janela de 1 min e seria vencida à força. Correção: copiar o `test_e2e_adiar_pela_fila_real` de `~/.cache/rev-b13/test_rev2b.py`
para `tests/test_revisao_b13.py` (ele já usa `UPDATE` explícito, não `tornar_vencidos`).

## 3. Regressões

- **`concurrency=4` com `lock=chat:`**: sem regressão (pico 1 em 18 jobs, 2 workers). Cuidado só com o pool: `POOL_MAX=8`, 4 jobs + listener + heartbeat; com 2 workers no mesmo banco, cada um tem o seu pool (ok). Documentar.
- **`readyz` sem `relogio`**: determinístico. Os testes usam margens grandes (5 s/31 s, 9/11 min) e idade pelo `now()` do banco; a idade só cresce com a lentidão do teste, então não há flake. Perdeu-se a prova EXATA da fronteira (30,0 s / 600,0 s, `>` × `>=`): ver N6.
- **`tzdata==2026.6`**: existe no PyPI (publicado 28/10/2026, `uv.lock` com hash, `uv lock --check` ok, venv com 2026.6). Pino de pacote de 2 dias: aceitável, mas veja N5 sobre o teste.

## 4. Testes que NÃO reprovam quando a correção é desfeita (mutação)

| # | Teste (arquivo:linha) | Mutação que sobrevive | O que falta |
|---|---|---|---|
| 1 | `test_a3_reconciliacao_esta_agendada_como_periodica` (`test_revisao_b13.py:117`) | cron da reconciliação trocado para `0 3 * * *` | comparar também `periodic_task.cron == "*/5 * * * *"` |
| 2 | `test_a3_tarefa_das_2015_tem_retry` (`:95`) + ausência de teste de `rodar_worker` | tirar de `rodar_worker` a linha `await asyncio.to_thread(jobs.reconciliar_bloqueio_diario, servicos)` (`fila.py:~219`); ou o `setdefault("concurrency", ...)` (`fila.py:~221`) | testes: `rodar_worker(wait=False)` às 21:16 locais grava `true` (meu `test_a3_rodar_worker_reconcilia_na_subida`); e `concurrency` efetivo = 4 |
| 3 | `test_a8_esquema_ausente_vira_falha_dura_e_nao_excecao` (`:212`) | remover `_com_timeout(dsn)` de `readyz_por_dsn` (`prontidao.py:131-146`) | teste com `SHOW statement_timeout` = `2s` e `options` preservadas (meu `test_a8_variacoes`) |
| 4 | `test_base_de_fusos_nao_depende_do_sistema` (`tests/test_calendario.py:156`) | qualquer: **tautológico** | ver N5 |

Sobrevivente adicional sem teste algum: `tzdata` fora do `pyproject.toml` (é só dependência; ok, mas ver N5).
Os outros 17 testes da correção morrem sob mutação, inclusive por testes antigos (ex.: tirar `retry_exceptions` reprova `test_tarefa_das_2015_fora_do_horario_falha_e_nao_grava`).

## Achados

### N1 · MÉDIA · A tarefa atrasada das 20:15 desfaz a abertura deliberada que a reconciliação respeita
- `src/ia_atendimento/jobs.py:239-250` (`executar_bloqueio_diario`) × `:253-268` (`reconciliar_bloqueio_diario`).
- **Problema.** A reconciliação não grava se `publicado_em >= tick` (o Danilo abriu depois do tick). A tarefa não tem essa regra: um job do tick das 20:15 que roda atrasado (retry de 30 s × 5, fila parada, worker fora)
  fecha de novo uma entrada que o Danilo abriu depois do tick. O mesmo vale para o `retry` após `ConfigCorrida` (`gravar_bloqueio_entrada`, `:224-234`): abriu entre as duas tentativas → a nova tentativa fecha.
- **Caso que reprova hoje (rodado, `test_a3_tick_atrasado_vs_danilo_abriu`):** tick 23:15Z; Danilo grava `false` às 21:00 locais; job atrasado roda 22:00 locais → `gravou=True`, `valor=True`.
- **Correção.** Extrair o critério para `_deve_fechar(conn, tick)` e usá-lo nas duas funções; em `gravar_bloqueio_entrada` receber `tick` e recusar se `atual.publicado_em >= tick`.

### N2 · MÉDIA · Reaper ainda repassa quem tem turno `todo` dentro da rajada de 3 s, e mistura relógios
- `src/ia_atendimento/jobs.py:174-179,197` (`_SQL_LEASES`: `j.scheduled_at <= %s` com `agora` da aplicação).
- **Problema.** O turno nasce com `schedule_in=3 s`; com o lease já vencido, o reaper (1/min) vê o `todo` ainda no futuro, não o conta como em curso e repassa; o turno chega depois ao atendimento repassado.
  Além disso `scheduled_at` é do relógio do BANCO e o corte é do relógio da aplicação (a mesma mistura que o A8b removeu da prontidão); nos testes o relógio falso é 17/11, então TODO job `todo` do banco parece vencido.
- **Caso que reprova hoje (rodado, `test_a7_turno_todo_futuro_vs_vencido`):** `todo` em `relogio+2 s` e `+3 s` → `executar_reaper_lease` devolve 1 (vencido: 0).
- **Correção.** Como o alarme não tem mais lock, todo `todo` com `lock = 'chat:' || chat_id` é turno/iniciar/lembrete_exec iminente: usar `j.status IN ('doing','todo')` sem comparar `scheduled_at` (e sem o 2º parâmetro `agora`).
  Teste: o do experimento, esperando 0.

### N3 · MÉDIA (pré-existente, aparece agora) · Alarme velho não é reprogramado: o lembrete sai 4 h depois da PRIMEIRA fala da IA
- `src/ia_atendimento/fila.py:185-190` (`queueing_lock=lembrete:{atendimento}:{n}`), `jobs.py` `decidir_lembrete` (não confere o tempo decorrido). Spec B1.3: «1º lembrete 4 h depois da última mensagem da IA».
- **Problema.** IA fala em T0 (alarme T0+4 h); o cliente responde, a IA fala de novo em T0+1 h: o 2º `agendar_lembrete` devolve `None` (já há alarme `todo`). Às T0+4 h o estado é `aguardando_cliente`, `cliente < ia`
  → `enviar`, 3 h depois da última fala da IA. Fora isso o alarme e o `lembrete` não têm `retry`: um soluço de banco em `enfileirar_lembrete` deixa o alarme `failed` e o lembrete se perde calado (o `readyz` só acusa > 20 falhas).
- **Caso que reprova hoje (rodado, `test_alarme_velho_nao_reprograma`):** 2 chamadas (+4 h, +7 h) → `1, None`; fica só o de +4 h.
- **Correção.** Decidir no `lembrete`: `ultima_ia_em + intervalo > agora` → `adiar` até esse instante (o `Decisao("adiar")` já existe); `retry` (5×, 30 s, `psycopg.Error`/`OSError`) no `alarme_lembrete` e no `lembrete`. Isso é de B1.5/B1.6 se o dono preferir cancelar o alarme antigo; registrar a decisão.

### N4 · BAIXA · Três testes novos não pegam a regressão que dizem pegar
Ver §4 (linhas e mutações). Correção: os 4 testes sugeridos (cron, `rodar_worker` com reconciliação, `concurrency`, timeout).

### N5 · BAIXA · `test_base_de_fusos_nao_depende_do_sistema` é tautológico
- `tests/test_calendario.py:156-166`. `monkeypatch.setattr(zoneinfo, "TZPATH", ())` NÃO altera o que `ZoneInfo` usa (`zoneinfo._tzpath.TZPATH`). Rodado: depois do patch, `find_tzfile("America/Sao_Paulo")` ainda acha `/usr/share/zoneinfo/...`; o teste passa mesmo sem `tzdata` instalado.
- **Correção.** `zoneinfo.reset_tzpath(to=[])` + `ZoneInfo.clear_cache()` e, no `finally`, `reset_tzpath()`. Rodado: com `reset_tzpath(to=[])`, `find_tzfile` devolve `None` e `ZoneInfo` carrega pelo pacote `tzdata` (prova que o pino serve).
- Obs.: `agendar_bloqueio_dataprev` também devolve `None` com o job `failed` (consulta por qualquer status): falha definitiva não é reagendada no boot. Intencional? Registrar (a reconciliação diária cobre 20/11 à noite).

### N6 · BAIXA · `readyz_por_dsn` e fronteiras
- `prontidao.py:131-146`: DSN no dialeto `postgresql+psycopg://` (que `conninfo_da_fila` aceita) vira `erro_de_consulta` (o `conninfo_to_dict` levanta `ProgrammingError`); o rótulo engana. Reusar o tratamento de `conninfo_da_fila` ou devolver `dsn_invalido`.
- Fronteira exata de 30 s/600 s sem teste: com os kwargs `heartbeat_max_s`/`todo_max_s` dá para testar `>` × `>=` com folga (ex.: batimento de 5 s com `heartbeat_max_s=4` e `=6`).

### N7 · BAIXA · `rodar_worker` e a reconciliação na subida
- `fila.py:~215-222`: se a reconciliação levantar (soluço de banco), o worker nem sobe e o supervisor reinicia em laço. Capturar `psycopg.Error`, logar `type(erro).__name__` e seguir (a periódica de 5 min repete).
- Documentar: `POOL_MAX=8` com `concurrency=4` (4 jobs + listener + heartbeat) deixa 2 folgas por processo.

### N8 · INFO
- **Erro de premissa da Revisão 1 (A3, problema 1).** O `max_delay` do `PeriodicDeferrer` no 3.10.0 é **600 s** (`procrastinate/periodic.py:22`), não 10 s. Deploy a 11 s do tick NÃO perde a tarefa (rodado: deferido até 599 s). Perde-se a partir de 601 s, e aí a reconciliação cobre.
  Corrigir a linha em `docs/REVISAO-B1.3-3010.md` para não induzir o próximo leitor.
- HOL residual: `turno` (rajada de 3 s, id menor) segura `iniciar`/`lembrete_exec` do mesmo chat por até 3 s. Aceitável; documentar no docstring de `fila.py`.
- `procrastinate_periodic_defers`: a poda usa `defer_timestamp < agora - dias_falhos` (30 d) e `job_id IS NULL`; coerente com a retenção dos falhos.
- Débitos já declarados pelo autor (A9, A11, A12 resto, A13 log de args) seguem fora do escopo; concordo que vão a B1.5/B1.6.

## Ordem sugerida
1. N2 (uma linha de SQL) e N1 (critério único), com os testes dos experimentos.
2. N3 (decisão do dono se o alarme antigo é cancelado ou se o `lembrete` reprograma) e os 4 testes de N4 + cadeia `adiar` real (§2).
3. N5, N6, N7, N8 (nota na Revisão 1).


---

## Resposta do autor (r2) (30/10)

Testes em `tests/test_revisao_b13.py` (seção «Revisão 2»), escritos antes da correção e vermelhos (N1, N2, N3, N5, N7); os de N4 cobrem comportamento já correto e passavam, ficando como rede.

| Achado | Correção | Teste |
|---|---|---|
| N1 | `_deve_fechar(atual, tick)` é o critério único (tarefa das 20:15, job de 20/11 `BLOQUEIO_DATAPREV_EM` e reconciliação): não fecha se já é `true` nem se alguém gravou **depois do tick**; vale também na releitura após `ConfigCorrida` (retry) | `test_n1_tick_atrasado_respeita_abertura_posterior_ao_tick`, `test_n1_job_de_2011_tambem_respeita_...`, `test_n1_abertura_anterior_ao_tick_continua_sendo_fechada` |
| N2 | `_SQL_LEASES`: qualquer job `doing`/`todo` com `lock = chat:{id}` segura o reaper (sem comparar relógios; o alarme não tem lock) | `test_n2_reaper_nao_repassa_chat_com_turno_todo_na_rajada_ou_vencido[-1,2,3,600]`, `test_n2_job_de_outro_chat_ou_alarme_sem_lock_...` |
| N3 | Decisão do autor (sem cancelar o alarme antigo, que fica para B1.5/B1.6 se o dono preferir): `decidir_lembrete(..., intervalo=)` adia para `ultima_ia_em + lembretes_intervalos_min[n-1]` (e para a abertura seguinte se cair fora da janela); `retry` (5×, 30 s, só `psycopg.Error`/`OSError`) em `alarme_lembrete` e `lembrete` | `test_n3_lembrete_antes_do_intervalo_...`, `test_n3_alarme_velho_e_reprogramado_pela_fila_real`, `test_n3_cadeia_adiar_pela_fila_real` (a cadeia alarme → lembrete → adiar → novo alarme → envio, da §2), `test_n3_alarme_e_lembrete_tem_retry_...` |
| N4 | cron da reconciliação (`*/5`), `rodar_worker` reconcilia na subida e usa `concurrency=4`, `statement_timeout` e `options` preservadas no readyz | `test_n4_*` (3 testes) |
| N5 | `zoneinfo.reset_tzpath(to=[])` + prova de que o sistema não acha mais o arquivo; o pacote `tzdata` carrega | `test_base_de_fusos_nao_depende_do_sistema` |
| N7 | `rodar_worker` captura `psycopg.Error` da reconciliação (loga o tipo) e sobe; limite do pool e HOL de 3 s documentados no docstring de `fila.py` | `test_n7_falha_na_reconciliacao_da_subida_nao_derruba_o_worker` |
| N8 | nota de correção (`max_delay` = 600 s) acrescentada à Revisão 1 | n/a |
| N6 | não feito: DSN `postgresql+psycopg://` em `readyz_por_dsn` ainda vira `erro_de_consulta`; fronteira exata de 30 s/600 s sem teste (backlog) | n/a |
