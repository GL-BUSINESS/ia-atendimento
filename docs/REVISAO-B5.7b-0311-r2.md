# Revisão adversarial 2 da B5.7b: `pausado`, `retomar`/`reaper_agenda`, `jobs_presos` (03/11/2026)

**Veredito: PRONTO PARA PR: SIM** (PR empilhado sobre a B1.5, sem merge em `main` e sem ligar `ia_ativa`/`agenda_ativa`). **0 CRÍTICO, 0 ALTO, 3 MÉDIO, 9 BAIXO novos.** Os 12 commits de correção
(`cf9d68b`…`8fe554f`) fecham de verdade o ALTO e os 5 MÉDIO da revisão 1 e os 2 achados automáticos: cada reversão testada em cópia derruba pelo menos um teste (37 mutantes, 35 mortos, 2 vivos e sem
efeito de produto). Os 3 MÉDIO novos não são defeitos do que está no repositório: são (R2-01) uma cerca que sai de graça se entrar **agora** no contrato `Volta`, e (R2-02, R2-03) dois
**gates duros** que precisam estar escritos no PR porque a proteção da revisão 1 só vale quando o worker real existir. Recomendo corrigir R2-01 e R2-04 antes de abrir o PR (5 linhas cada); o resto é gate declarado da B1.6/B5.7c/esteira.

Branch `feat/b5-7b-pausado` (15 commits sobre `origin/feat/b1-5-api-entrada`), `HEAD` `8fe554f`. Revisor independente da r2; não fiz a r1. Nada foi alterado fora deste arquivo, sem push, nada em produção, só Postgres 18
local descartável (contêineres `ia-pg18-pytest-r2-*`, todos removidos). Sem PII nem segredo.

**Portão local reproduzido:** `bash scripts/check.sh` = `uv lock --check`, ruff, `ruff format --check`, `varredura.py` (**limpa**, também rodada à parte), `sha256sum -c 0001.sha256`, `gerar_0002.py --verificar` e
**2.374 passed, 1 skipped (falta `yaml`), 1 xfailed (gasto, B1.6)** em 149 s (`check.log`).

**Provas** (fora do repositório, em `/tmp/claude-1001/-opt-claude/c3edfc59-52d9-4e44-8d0b-adab74392dfc/scratchpad/rev-b57b-r2/`): `probe/test_r2_probe.py` e `probe/test_r2_probe_c.py` (47 sondas, todas verdes; as que provam
defeito afirmam o defeito), `probe/worker_longo.py` (worker real em processo à parte), `sondas.log`, `probe_a.log`, `mut.py`/`mut2.py`/`mut3.py` + `mutantes.log`/`mutantes2.log`, `check.log`, `rodar.sh` (sobe e derruba o Postgres de cada rodada).
Tudo roda sobre cópias de `HEAD` (`copy/`, `mutcopy*/`).

## 1. Cada correção da r1: fechada de verdade?

«Reprova se reverter» = mutante em cópia derrubado por teste nomeado.

| r1 | Estado | Prova |
|---|---|---|
| R1-01 ALTO, worker morto depois do CAS | **Fechado** (ressalvas R2-02, R2-05, R2-06) | `test_sigkill_no_meio_da_volta…` é SIGKILL real depois do CAS, e o turno do cliente sai. Mutantes: periódica fora do cron (R1-01a) morto por `test_jobs_presos_e_periodica_por_minuto…`; `liberar_jobs_presos` vazio (R1-01b) e sem o ramo `worker_id NULL` (R1-01c) mortos pelo EM4; `jobs_presos` sem `queueing_lock` (Y5) morto. Cura (por leitura do código e do tick de 1 min, não cronometrada): ≤ ~2 min depois do kill (batimento velho 60 s + tick). |
| R1-02 MÉDIO, `disparado` sem saída | **Fechado** (ressalva R2-04) | `rearmar` + `Adiar`. Mutantes: alarme novo ausente (X7), rearme sem conferir a espera (Y2), sem limite (Y3), sem o piso de 5 s (Z2) mortos. Corrida de **dois rearmes**: ver (d). |
| R1-03 MÉDIO, sem teto de atraso | **Fechado** | R1-03a (sem teto) e R1-03b (`>=`) mortos; o teste de fronteira parametrizado (29:59, 30:00, 30:01) pega o `>=`. Comportamento depois do `expirado`: ver (e). |
| R1-04 MÉDIO, `cedo` em laço quente | **Fechado** | R1-04a (sem piso) e R1-04b (piso 0) mortos por `…rearma_o_alarme_com_atraso_relativo…[1-5.0]`; `test_relogio_da_app_atrasado_nao_vira_laco_quente` conta jobs na fila real (≤ 3). |
| R1-05 MÉDIO, `agenda_max_pausados` sem dono | **Fechado** | R1-05a (sem conferir), b (sem trava consultiva), c (`>`), d (`>=` no teto de horas) mortos. Corrida: ver (f). |
| R1-06 MÉDIO, prova da noite por espiões | **Parcial, aceito como gate da B1.6** | O reaper de lease é real e o handler muda estado (a prova melhorou muito), mas `expirar_parados` segue espião e `jobs.ESTADOS_EXPIRAVEIS` só é comparado consigo mesmo (X9 morto por teste estático). Ver R2-12. |
| R1-07 BAIXO, `estado.py` 796 linhas | **Fechado** | AST das 4 funções e das 4 constantes movidas **idêntico** (`cf9d68b^:estado.py` × `estado_pausa.py`); o resto de `estado.py` não mudou nenhum nó. Ver R2-12 sobre a ausência de reexportação. |
| R1-08 BAIXO, ordem de locks | **Fechado** | X3 (sem `travar_dono` em `_registrar_desfecho`) morto por `test_registrar_desfecho_trava_o_atendimento_antes_do_agendamento`. |
| R1-09 BAIXO, falso positivo do worker vivo | **Parcial, aceito** | Mitigado pela vigia; a sonda (b) confirma o ruído (`ConnectorException` no `finish_job` do perdedor); a sonda (a) mostra o caso que a vigia **não** cobre (laço bloqueado, R2-06). |
| R1-10 BAIXO, 91 bytes | **Fechado no texto**; validador de 2 KB segue sem reservar 100 B | O teste de 32/91 bytes existe; a decisão do validador ficou como pendência declarada (D, item 5). |
| R1-11 BAIXO, 3 mutantes vivos | **Fechado** | R1-11a (folga da config ignorada), b (422 depois das recusas), c (`reaper_agenda` sem `queueing_lock`): mortos 3/3. |
| R1-12 BAIXO, tipo de retorno | **Parcial** | `Desfecho \| Adiar \| None`, mas `Desfecho` contém `reagendado_sistema`: R2-04. |
| R1-13 BAIXO, `Volta.retoma_fase` da linha | **Aberto, aceito** (B5.7c) | Sem mudança; documentado. |
| R1-14 BAIXO | **Fechado** | `test_segundo_pedido_no_mesmo_chat_nao_cria_segundo_agendamento_ativo` (409 `chat_ocupado`) além do invariante do banco. |
| R1-15 BAIXO | **Aberto, aceito** (B5.7c) | Documentado. |
| Auto-1 (`worker_id NULL` = morto na hora) | **Fechado** | `W-MEDIO1` (`< now()` sem margem) morto por `test_job_de_worker_podado_so_e_preso_depois_da_margem_desde_o_started`; F1 (sem `stalled_worker_timeout=60`) morto por `test_n4_rodar_worker…`. |
| Auto-2 (`doing → failed` não atômico) | **Fechado** | `W-MEDIO2` (status não reconferido) morto pela corrida real com a linha travada; ver (b). |
| `fila.py`: `raise WorkerPerdeuOBatimento`, vigia, `shutdown_graceful_timeout = 0` | **Fechado, com ressalva** | F2 (sem o `raise`) e W4 (tolerância > margem) e Y4 (`>` no lugar de `>=`) mortos por teste; **F3 (vigia sem task) e W3 (sem `graceful = 0`) só morrem por TRAVAMENTO**: o teste `worker_que_perde…` não tem timeout no `finally` e a suíte não tem timeout por teste (R2-07). Matei os dois à mão após 150 s. |

**Regressão nova:** nenhuma funcional. `rodar_worker` deixou de passar por `app.run_worker_async` (perde `app.worker_defaults`, que o app não usa hoje); o `reaper_agenda` virou dependente da `jobs_presos` para
`doing` morto (de propósito, uma só autoridade).

**Mutantes extras** (os 3 pedidos e mais): X1 `lease_so_cresce=False` no rearme, X2 `MAX_REARMES=3`, X4 `fora_do_estado` sem cancelar, X5 `queueing_lock` do exec igual ao do alarme, X6 `_SQL_VENCIDOS` sem o lock do exec,
X8 reivindicar sem checar o serviço, Z1 `reaper_agenda` sem contar `doing` como vivo, Y1 `versao` fora do `WHERE` do `aplicar`. **Sobrevivem X1 e X2** (R2-08); o resto morre. Total 37 mutantes: 35 mortos (2 por travamento), 2 vivos.

### As perguntas da tarefa

**(a) `jobs_presos` com 60 s e idade mínima de 60 s: worker vivo e lento é dado como morto?** Depende de **o laço de eventos estar vivo**, não da duração do job. Sonda `test_a_job_longo…` (87 s, dois workers reais com `rodar_worker`):
(i) job de **75 s** sem bloquear o laço: batimento ≤ 5 s o tempo todo, 17 ticks de `liberar_jobs_presos` de fora, o job ficou `doing` e terminou `succeeded`: **nunca tocado**; (ii) job de **70 s que bloqueia o laço** (`time.sleep`
no handler): batimento chega a 61 s no tick de 60 s e a periódica o dá como `failed` com o processo vivo e o job ainda rodando (terminou aos 70 s); o lock do chat ficou livre ~8 s antes de o job acabar; ao acordar, a vigia saiu com
`WorkerPerdeuOBatimento batimento_velho`. Logo: o job legítimo mais longo **não tem teto** no código (o plano não define timeout de turno; o pior caso é modelo 20 s + ferramentas), e isso é seguro desde que o handler
nunca bloqueie o laço por mais de ~40 s (vigia) / 60 s (fila). Um SDK síncrono do modelo ou do ChatGuru dentro do laço, com retry, passa disso. É o R2-06.

**(b) O `UPDATE` único reconfere o predicado: corrida real com o término normal, 20×.** `finish_job_by_id_async(SUCCEEDED)` × `liberar_jobs_presos` em paralelo, com um worker de batimento velho: 20 rodadas, **12 vezes o término ganhou
(`succeeded`) e 8 vezes a periódica (`failed`)**; a periódica **nunca levantou** e nunca deixou estado misto; nas 8 em que perdeu, o `finish_job` do worker levanta `ConnectorException` («not in doing status»), ruído sem efeito
(o job fica `failed` apesar de ter acabado: já era o R1-09). O mutante W-MEDIO2 (sem reconferir) é morto pelo teste da linha travada.

**(c) `vigiar_batimento` abortando em voo.** Sonda `test_c_vigia…` com `rodar_worker` real, `retomar` real e a thread do `_reivindicar` esperando o `FOR UPDATE` do atendimento: apaguei a linha do worker.
Resultado: `WorkerPerdeuOBatimento linha_sumiu`; o **job virou `aborted`** (não ficou `doing`, `attempts = 1`), o **lock do chat ficou livre na hora** (0 jobs `todo/doing` com `lock=chat:`), **mas a thread não morreu**:
a transação continuou esperando o lock e, quando o liberei, **fez o CAS e commitou** `disparado/retomou` com **0 voltas entregues** (a corrotina já tinha sido cancelada). Ou seja: o abort **não faz rollback** do que
está numa thread (`asyncio.to_thread` não é cancelável) e o processo só sai quando a thread acaba (`asyncio.run` espera o executor); a volta se perde e o lead cai no `reaper_lease` em `retoma_em + 30 min` (R2-05, R2-03).
Vira «preso em 60 s»? Não: o `aborted` já fechou o job; a `jobs_presos` só vê o que ficou `doing`.
**O supervisor:** existe só como política de contêiner em `feat/esteira` (`docker-compose.yml:69` `restart: unless-stopped`, `:80` `stop_grace_period: 40s`) e como texto na OPERACAO §8. **Ninguém chama `rodar_worker`**: o `command`
do worker (`docker-compose.yml:96`) é `procrastinate --app=ia_atendimento.fila.app worker`, módulo/atributo que não existe (`fila.py` expõe `criar_app`), sem `Servicos`, sem vigia e com `stalled_worker_timeout` de 30 s; o healthcheck
(`:100`) é `import ia_atendimento`. O próprio compose avisa (`:16`) que os `command:` nascem na B1. Não há `__main__`/script de console no `pyproject` que use `rodar_worker`. Vira o R2-02.

**(d) `rearmar disparado → confirmado`, sem `seq`, máximo 2.** 10 rodadas de **dois rearmes concorrentes** (horas diferentes): sempre exatamente 1 vence, o outro leva `TransicaoInvalida`/`ConflitoVersao`; `seq` = 1, 1 passo
`reagendado`, `retoma_em` = a hora do vencedor, `lease_ate ≥ retoma_em`. O 3º rearme sequencial leva `LimiteDeRearmes` e o agendamento fica `disparado` com o lease do 2º rearme (`dispara + 30 min`). A contagem é feita sob o lock do
atendimento (serializa). Ressalva de modelagem: R2-09.

**(e) `expirado` depois do lease.** Para `pausado` (caso a): o `reaper_lease` o vê com `acao = "retomada_perdida"` (para o `reservado` de agendamento, `agendamento_perdido`, que o handler de referência aborta). O repasse leva
`motivo = "retomada_perdida"`; **não existe NT no repositório** (grep): o texto de `textos/TEXTOS-PARA-APROVACAO.md` é **NT-06** («cliente combinou retorno às HH:MM; a IA não retomou»), ou a **NT-05** (pendência de assinatura) quando
`retoma_fase = E8`. O `HH:MM` sai de `agendamento.dispara_em`, que o `expirado` preserva (sonda: linha `expirado`, `seq` 1, `retoma_fase` E8, `desfecho_disparo` NULL). Mas **só no `expirado` a frase «não retomou» é certa**; ver R2-03
para o `disparado` perdido.

**(f) `LimiteDePausados` sob trava consultiva, 5 concorrentes, teto 2, 10×:** 10 de 10 rodadas com exatamente 2 `pausado` e 3 `LimiteDePausados`; nenhum erro de outro tipo (`barrier` de 5 threads, conexões próprias). A trava
global `ia_atendimento.pausar` não forma ciclo com os locks de linha (a contagem não trava linhas; só pode haver espera cruzada se a mesma transação segurar a linha de A e pausar A, que não é o caso).

## 2. D14b: execução superada de `retomar`

**Provado:** a execução que **perde o CAS** nunca entrega. 20 rodadas × 6 `executar_retomar` concorrentes sobre o mesmo agendamento: 20 vezes exatamente 1 `disparado` e 1 volta; Y1 (tirar `versao` do `WHERE` do `aplicar`) é morto
(`test_pausar_com_versao_velha…`); os 8 casos de `test_execucao_superada.py` seguem verdes.

**Refutado na forma ampla («nunca entrega a volta»):** a execução que **ganhou** o CAS e depois foi dada como morta pela fila (`jobs_presos`, worker lento ou laço bloqueado) **continua e entrega** (sonda `test_d14b_vencedor_do_cas_declarado_morto_ainda_entrega`:
A reivindica e trava, a fila a falha, o substituto acha `disparado`, A termina e entrega; `entregues == [id]`). Uma volta só, mas por uma execução **sem o lock do chat** que pode correr junto com um `turno` do cliente liberado pela
própria `jobs_presos`. E `gravar_passo` não tem CAS (a execução superada ainda pode **anexar passos**; só o estado é cercado). A única coisa que impede dano hoje é o CAS do estado; a cerca do envio **não existe** (turno/lembrete são
espiões). `Volta` não carrega a versão do atendimento (R2-01), embora `Dono.versao` seja lida sob lock no claim e o claim **não** a incremente (sonda `test_y_fencing…`: 4 → 4; `sair_da_pausa` com essa versão levaria `ConflitoVersao` se
um repasse/turno tivesse mexido).

**O que a B1.6 precisa fazer para fechar o gate** (plano do núcleo, itens 4 e 5, chave `t11:{atd}:{rodada}:{seq}`):
1. **Reservar antes de enviar**, no ledger `ia.ferramenta_chamada` (`idem_key = sha256(chave_logica)`, `UNIQUE`): `INSERT … ON CONFLICT DO NOTHING` em `reservada`; conflito ⇒ devolve o resultado gravado e **não envia**. `rodada` = a que o `consumir` (CAS) deu ao turno;
   para a volta, a `rodada` lida no claim (determinística; nunca hora nem `job_id`) e `seq` = ordinal da mensagem.
2. **Cerca no envio:** a reserva e um CAS de `versao` do atendimento (a versão lida **depois** do modelo/da volta) na **mesma transação**; `ConflitoVersao` ⇒ passo `erro`, **não envia**. O ledger sozinho **não basta**: a execução superada
   (rodada N) e o substituto (rodada N+1) têm chaves diferentes e os dois enviariam. É o item 5 do plano («o envio só vale se o CAS de `versao` ainda passa»).
3. **Estados:** `enviada`/`falhou`/`indeterminado`; `reservada` encontrada no retry = `indeterminado`; **timeout, 424, corte e `CancelledError` no meio do envio ⇒ `indeterminado`** (o envio e a gravação do resultado em `asyncio.shield`, porque a vigia e o
   `shutdown_graceful_timeout` cancelam qualquer `await`); `indeterminado` **nunca reenvia** (`sem_retry_ambiguo`) e confere a conversa por RPA antes de qualquer decisão.
4. **`lembrete`:** `RETRY_FILA` reexecuta em `psycopg.Error`/`OSError` depois de um envio que pode ter saído: precisa da mesma chave (`t11` ou a do lembrete) no ledger, senão repete a mensagem.
5. **Volta (B5.7c):** primeira escrita = `sair_da_pausa`/`iniciar_agendado` com a **versão do claim** (R2-01); só depois o envio pela regra 1–3.
6. **Testes de aceite (com mutação):** (i) dois `turno` do mesmo atendimento, o primeiro parado depois do modelo, o segundo completo: o `Canal` real é chamado 1 vez; tirar o CAS antes da reserva derruba; tirar o `ON CONFLICT` derruba;
   (ii) `retomar` reivindicado, `jobs_presos` entre o claim e o envio, `turno` do cliente no meio: no máximo uma mensagem; (iii) `CancelledError` no meio do envio deixa `indeterminado` e não reenvia.

## 3. Conformidade

**Estudo M.** Conforme: estados da linha (`pendente → confirmado → disparado | cancelado | expirado`), CAS `UPDATE … WHERE estado AND versao`, `reaper_agenda` por minuto «sem job vivo, idempotente por `queueing_lock`», `reaper_lease` pulando `pausado` até
`lease_ate`, `agenda_folga_min`/`agenda_teto_horas`/`agenda_max_pausados`/`agenda_max_por_atendimento`, pausa nunca em E7, EM4, `send_date` fora, `pausa{agendamento_ref, retoma_fase}`, `pausado` fora da 19:45/20:15. **Divergências deliberadas e
documentadas:** (1) M §2.5 (a) volta em `aguardando_cliente`; D2 faz `aberto` com lease de turno (e oferece `aguardando_cliente`): decisão da B5.7c, mas registre em M. (2) M §2.8 manda o `reservado` que nunca disparou virar `abortado (agenda_nao_disparou)`;
o código nomeia a ação `agendamento_perdido` e o handler de referência usa esse texto como `motivo`: alinhar o nome na B1.6. (3) M §3 diz `retomar` = um job com `queueing_lock = retomar:{agendamento_id}` **e** `lock = chat`; o código tem dois (D4/D5).

**Roteiro B5.7b (linhas 842–845): a divergência «`schedule_at` + `lock` por chat» × D4. Quem está certo? A D4.** Reli o SQL, não só a nota: `procrastinate_fetch_job_v2` (`schema.sql:210-253`) rejeita o candidato se existe outro job do mesmo `lock` em
`doing` **ou** `todo` com `priority` maior ou `id` menor, **sem olhar `scheduled_at`**. Um `retomar` agendado para daqui a 20 h com `lock=chat:X` trava todo `turno` de X criado depois dele (id maior): a mensagem do cliente durante a pausa ficaria sem
resposta até a hora combinada (a sonda da r1 e `test_o_alarme_futuro_nao_prende_o_turno…` mostram). O roteiro está **errado** e **precisa de emenda**. Texto exato:
- Spec, onde está «jobs `retomar` (`queueing_lock = retomar:{id}`, CAS `confirmado → disparado`)», trocar por: «jobs `alarme_retomar` (agendado em `dispara_em`, **sem `lock`**, `queueing_lock = retomar:{agendamento_id}`) e `retomar` (enfileirado pelo alarme e pelo `reaper_agenda`, `lock = chat:{chat_id}`, `queueing_lock = retomar_exec:{agendamento_id}`, CAS `confirmado → disparado`); periódicas `reaper_agenda` e `jobs_presos` por minuto».
- «Se der errado», trocar «⇒ `schedule_at` + `lock` por chat» por: «⇒ alarme com `schedule_at` **sem** `lock` + job de execução com `lock` por chat; o `lock` num job futuro trava os turnos do chat até a hora (o `procrastinate_fetch_job_v2` ignora `scheduled_at`)».
- Aceite: acrescentar «restart **com SIGKILL depois do CAS** sem lead preso (`jobs_presos`)» e «a volta que passa do lease não é entregue (`expirado`)»; Desfazer: «D0, `agenda_ativa=false` e parar a periódica `jobs_presos` só junto com o worker».
- Estudo M §3 «Idempotência»: mesma troca (alarme sem lock + exec com lock).

**Contrato 08 §5.5 (o 422 novo).** Hoje: «`retoma_fase` (`"E8"` enquanto `agenda_b_digita=false`)» e a linha «Ordem: `agenda_desligada` → …». Emendas:
1. Corpo: «`retoma_fase` (`^E([2-6]|8)$`, obrigatório; **`"E8"` enquanto `agenda_b_digita=false`**: qualquer outra fase com a chave desligada ⇒ `422 validacao`, `campo:"retoma_fase"`, `detalhe:{"regra":"so_e8_sem_agenda_b_digita"}`, sem eco do valor; E7, E1, E9, E10 e lixo ⇒ `422 validacao` pelo padrão)».
2. Ordem: «forma (422) → `chave_incoerente` → **replay** (`200 repetido` / `409 chave_reutilizada`) → **`422 retoma_fase`** → `agenda_desligada` → `ia_desligada` → `bloqueio_entrada` → `fora_de_janela` → `opt_out` → `agenda_max_dia` → `chat_ocupado` → extrator → modo (422) → `503 artefatos_ausentes` → reserva».
3. Resposta `201`: «grava também o passo `agendamento` (`resultado:"proposto"`) e enfileira o alarme do `retomar` em `dispara_em` **na mesma transação** da reserva e do cofre; falha ao enfileirar ⇒ nada fica gravado».
4. Tabela de erros (linha 62), célula de `422 validacao`: acrescentar «ou regra de aplicação (`campo`, `regra`), ex.: `so_e8_sem_agenda_b_digita`».
5. «`dispara_em` ≤ `datetime_post` + `agenda_teto_horas`»: o código usa `ultimo_cliente_em` (padrão `datetime_post`); escrever «≤ `ultimo_cliente_em` (padrão `datetime_post`) + `agenda_teto_horas`».

**`DECISOES-B5.7b-0211.md`:** D14b diz «a execução superada que já reivindicou segue dona da volta»: acrescentar «**e entrega sem o lock do chat** (a fila já a deu como falha); a cerca é o CAS de `versao` no envio (gate da B1.6)»; D14 «Para o deploy: supervisor» virar **gate duro** com a pendência do ponto de entrada (R2-02); a pendência 3 ganha o item R2-03.

## 4. Achados novos

| # | Sev | Onde | Achado e prova | Correção |
|---|---|---|---|---|
| R2-01 | **MÉDIO** | `jobs.py` (`Volta`), `agenda_jobs.py:62,82` | **`Volta` não carrega a cerca.** `Dono.versao` é lida sob `FOR UPDATE` no claim e o claim não a incrementa (sonda: versão 4 antes e depois), mas `Volta(agendamento_id, atendimento_id, chat_id, entrada, retoma_fase, dispara_em)` a descarta. A volta da B5.7c vai reler a versão e o `sair_da_pausa` passa mesmo que um `turno` ou repasse tenha mexido depois do claim: a execução declarada morta pela fila escreve e envia por cima. | Acrescentar `atendimento_versao: int` a `Volta` (preenchida de `dono.versao`) e um teste «`sair_da_pausa(versao=volta.atendimento_versao)` depois de um repasse ⇒ `ConflitoVersao`». Barato agora, contrato quebrado depois. |
| R2-02 | **MÉDIO** | `feat/esteira:docker-compose.yml:96,100`; `OPERACAO.md §8` | **A proteção da r1 não está ligada a nada.** Não há ponto de entrada que chame `rodar_worker` (nem `__main__`, nem script no `pyproject`); o compose da esteira sobe `procrastinate --app=ia_atendimento.fila.app worker` (módulo/atributo inexistentes; sem `Servicos`, sem vigia, prune de 30 s) e o healthcheck é `import ia_atendimento` (não vê worker vivo-mas-preso). A OPERACAO afirma «o worker sobe por `fila.rodar_worker`». O `restart: unless-stopped` e o `stop_grace_period: 40s` existem. | **Gate duro de deploy:** entrypoint que monta `Servicos`, chama `rodar_worker`, sai com código ≠ 0 em `WorkerPerdeuOBatimento` e define `shutdown_graceful_timeout` (R2-06); healthcheck que lê a idade do próprio batimento (`prontidao`); teste que o `command` do compose aponta para esse entrypoint. Reescrever a frase da OPERACAO como pendência. |
| R2-03 | **MÉDIO** | `agenda_jobs.py:78-83,128`; `jobs.py:234` (`_acao_do_lease`) | **Volta perdida deixa o registro mentindo e o repasse não o fecha.** Depois do CAS o `desfecho_disparo` já é `retomou`. Se a volta levanta, é abortada (R2-05) ou o worker morre, a linha fica `disparado/retomou` **para sempre**, mesmo depois do `retomada_perdida` repassar o lead (sonda `E2`: `[('disparado','retomou')]` depois do repasse). O mesmo vale para `confirmado` órfão se o alarme foi perdido e o `reaper_lease` chegou primeiro (o `reaper_agenda` só enxerga `pausado`/`reservado`). E a NT-06 «a IA **não retomou**» é falsa quando a mensagem pode ter saído (morte depois do envio). Métricas «repasses por falha da volta» e «taxa de resposta após a volta» (M §5.3) saem erradas. | Gate da B1.6: o handler de `retomada_perdida`/`agendamento_perdido` fecha a linha na mesma transação do repasse (`registrar_desfecho(…, "repassou")` se `disparado`; `cancelar(por="sistema")` se `confirmado`); para `disparado` usa nota neutra («a volta combinada pode ter sido enviada, confira») ou confere por RPA; só `expirado` e `confirmado` usam NT-06. Um teste do handler de referência de `apoio_agenda` cobrindo as 3 linhas. |
| R2-04 | BAIXO | `jobs.py:134`, `agenda_jobs.py:128` | `Desfecho` inclui `"reagendado_sistema"` e `executar_retomar` o aceita como retorno puro: o agendamento fica `disparado/reagendado_sistema`, sem rearme e sem alarme (sonda `X_REAGENDADO_PURO`), exatamente o beco do R1-02. `Adiar` é o único caminho certo. | Tipar o retorno como `Literal["resolvido","repassou","humano_atuou"] \| Adiar \| None` ou recusar `reagendado_sistema` em `_registrar_desfecho`; teste. |
| R2-05 | BAIXO | `worker_vivo.py:104-108`, `agenda_jobs.py:120` | Abortar cancela a corrotina, não a thread: o claim pode **commitar depois** do abort e a volta se perde (sonda C: `aborted`, lock livre, `disparado/retomou`, 0 voltas). O processo só sai quando as threads acabam. Efeito aceitável (a rede é o lease), mas D14 diz «para e aborta» sem isto. | Registrar em D14; B1.6: envio e resultado em `asyncio.shield` (item 3 do gate). |
| R2-06 | BAIXO | `fila.py:385-408`, `worker_vivo.py` | (i) Laço bloqueado > 60 s: job vivo vira `failed` e o lock é solto com o job ainda rodando (sonda A); a vigia roda no mesmo laço e não pode ajudar. Entre 40 e 60 s a vigia pode abortar um job que a fila manteria. (ii) `shutdown_graceful_timeout` fica `None`: no SIGTERM do deploy o worker espera sem limite (e cancela o batimento ao drenar) até o SIGKILL dos 40 s, deixando `doing` para a `jobs_presos` (cura de até ~2 min); atribuir `0` na vigia depois de iniciada a drenagem não surte efeito (o `asyncio.wait` já leu o prazo; lido em `worker.py`, não executado). | `opcoes.setdefault("shutdown_graceful_timeout", 30.0)` (< `stop_grace_period`); regra de código para a B1.6: **nenhum I/O síncrono no laço** (SDK síncrono ⇒ `to_thread`), com teste de «atraso do laço» (`loop.slow_callback_duration`). |
| R2-07 | BAIXO | `pyproject.toml`, `tests/test_jobs_presos.py:268`, `tests/test_agenda_jobs.py` | Sem timeout por teste: F3 e W3 travam a suíte (até o `timeout 600` do `check.sh`) em vez de falhar. `tests/test_agenda_jobs.py` tem **828 linhas** (> 800) e `test_em4_…` 74. | `shutdown_graceful_timeout=1` nas opções do worker do teste (ou `pytest-timeout`); dividir o arquivo. |
| R2-08 | BAIXO | `agenda_estado.py:43,215`; `tests/test_agenda_rearme.py` | Mutantes vivos: **X1** (`lease_so_cresce=False` no rearme; só importa se `agenda_folga_min` diminuir entre a pausa e o rearme) e **X2** (`MAX_REARMES=3`: o teste é paramétrico no próprio símbolo, o «2» da decisão do dono não está fixado). | `assert ae.MAX_REARMES == 2` e um teste com folga reduzida. |
| R2-09 | BAIXO | `agenda_estado.py:201-205` | O limite de rearmes conta passos `reagendado`; o CHECK do `passo` tem uma só palavra `reagendado` e M §3 a usa também para o reagendar do cliente (B5.7c): um passo `reagendado` gravado no `agendamento_id` errado come o orçamento. | B5.7c: nunca gravar `reagendado` no id de outro uso, ou coluna `rearmes` (0005). |
| R2-10 | BAIXO | `worker_vivo.py:79-108`, `fila.py:379` | Se a task da vigia morre por exceção inesperada (não de leitura), ninguém vê até o fim do worker e a proteção some em silêncio; `_novo_worker` ignora `app.worker_defaults`. | `add_done_callback` que loga e para o worker; passar os defaults. |
| R2-11 | BAIXO | `prontidao.py:26`, `OPERACAO.md §8` | Comentário velho: «`HEARTBEAT_MAX_S` = `stalled_worker_timeout` do Procrastinate» (agora é 60). A ordem 30 s (`/readyz`) < 40 s (vigia) < 60 s (fila) é boa e merece estar escrita. SQL cru nas tabelas internas do Procrastinate (`procrastinate_workers`, `procrastinate_events`) acopla ao 3.10 pinado. | Comentário + um teste de versão do Procrastinate. |
| R2-12 | BAIXO | `estado_pausa.py:19-35`; `jobs.py:45` | `estado_pausa` importa os privados `_lease` e `_mudancas` de `estado`; `estado.py` não reexporta as funções movidas (nada no repositório as usa, mas qualquer ramo paralelo, como a B5.7c, tem de importar do módulo novo); `ESTADOS_EXPIRAVEIS` não tem consumidor real. | Tornar públicos os dois auxiliares; oferecer em `jobs.py` o SQL do `expirar_parados` já filtrado pelo predicado. |

## 5. O que conferi e está certo

- **`estado_pausa.py`:** 4 funções e 4 constantes movidas com AST idêntico a `5a88a33/c14c2ff`; só `pausar` mudou depois, de propósito (R1-05). Importa sem ciclo; nenhuma função de `src/` passa de 46 linhas (`gravar_mensagem_recebida`, anterior à etapa); o maior arquivo novo ou alterado é `estado.py` com 648 (o de `src/` mais longo é `agenda_extrator.py`, 693, da B5.7a).
- **CAS `confirmado → disparado`:** 20×6 concorrentes, 1 volta; `fora_do_estado` cancela por `sistema` sem falar; `retomar` sem serviço falha antes do CAS (X8 morto).
- **`jobs_presos`:** UPDATE único `status='doing' AND (batimento velho OR (NULL e started > 60 s))`, `failed` (não `todo`: a tarefa pode já ter agido), `attempts + 1` e `abort_requested=false` como o `finish_job`; só ids no log. Job de 75 s em worker vivo nunca é tocado.
- **Vigia:** `linha_sumiu`, `batimento_velho` e `banco_inalcancavel` com `Worker` real; o job vira `aborted`, o lock é solto, `rodar_worker` sai com `WorkerPerdeuOBatimento`; o `retomar` não tem retry e, nas tarefas com `RETRY_FILA`, `CancelledError` não está em `retry_exceptions`: o abort não reenfileira.
- **`pausar`:** teto de pausados sob `pg_advisory_xact_lock` (10 rodadas de 5 threads nesta revisão: sempre 2), teto de 23 h na fronteira exata, `lease_ate = retoma_em + folga`, a chave `pausa` só em `pausado`.
- **API:** `retoma_fase` depois do replay e antes das recusas (R1-11b morto), enfileiramento na mesma transação, folga da config (R1-11a morto).
- **Lock do `retomar` com o turno do cliente:** continua certo (D4/D5 conferidas no SQL do Procrastinate), `queueing_lock` por agendamento.
- **Docs:** CHANGELOG/README com 2.374 e as colunas da tabela coerentes; D14–D20 batem com o código nos pontos que testei.

## 6. Gates antes de ligar qualquer coisa (consolidado)

1. **B1.6:** ledger `t11`/lembrete **com a cerca de `versao`** (seção 2) + handler de `retomada_perdida`/`agendamento_perdido` que fecha a linha do agendamento e escolhe a NT certa (R2-03) + `expirar_parados` filtrado por `ESTADOS_EXPIRAVEIS`.
2. **Deploy:** entrypoint de worker + healthcheck + `shutdown_graceful_timeout` + `command` do compose (R2-02, R2-06). Sem isso, a vigia e o prune de 60 s da r1 não existem em produção.
3. **B5.7c:** `atendimento_versao` na volta (R2-01), `Adiar` como único caminho de reagendamento do sistema (R2-04), tentativa a +10 min é uma `Adiar` (uma exceção transitória hoje **não** repete: o job falha e o lead espera o lease).
4. **Condições para o PR:** R2-01 e R2-04 corrigidos (ou aceitos por escrito); R2-02 e R2-03 escritos como gate no corpo do PR e em `DECISOES`; emendas do roteiro e do contrato 08 §5.5 aplicadas pelo dono (estão fora deste repositório).
