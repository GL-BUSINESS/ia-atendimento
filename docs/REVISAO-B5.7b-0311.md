# Revisão adversarial 1 da B5.7b: estado `pausado` e jobs `retomar`/`reaper_agenda` (03/11/2026)

**Veredito: APROVAR COM RESSALVAS. 0 CRÍTICO, 1 ALTO, 5 MÉDIO, 9 BAIXO.** O núcleo está sólido: CAS sem duplicidade, serialização com o turno, atomicidade da API e os invariantes do banco se sustentam
sob prova real (dois workers, SIGKILL, fila de verdade). O ALTO (R1-01) é uma lacuna de recuperação que contradiz a promessa de D6/D8 e o aceite «restart sem perda»: o lead fica preso para sempre se o worker
morre **depois** do CAS. Ele tem correção pequena e já validada abaixo; corrija antes do merge ou escreva-o como gate duro (nada de `agenda_ativa=true` e nada de `ia_ativa` antes dele). Os MÉDIO R1-02 e R1-03 são
decisões de desenho que a B5.7c herda e que ficam caras depois de construídas em cima.

Branch `feat/b5-7b-pausado` (`5a88a33`, `c14c2ff`, `60a3464`) sobre `origin/feat/b1-5-api-entrada`. Revisor independente; nada foi alterado fora deste arquivo, sem push, nada em produção. Sem PII nem segredo.

Fontes lidas: `docs/DECISOES-B5.7b-0211.md`; `estudos/semana-1/m-agendar-assinatura.md` (§2.4–2.8, §3, §5.4); `ROTEIRO-DE-ACAO.md` B5.7b e P-R13; `contratos/08-orquestrador.md` §5.5, §5.6, §6;
`estudos/semana-1/i-esquema-reconciliado.md` (DDL `agendamento`, `atendimento_conversa_check`); o código do Procrastinate 3.10.0 (`procrastinate_fetch_job_v2`, `finish_job_v1`, `prune_stalled_workers`, `get_stalled_jobs`).

**Portão local:** `bash scripts/check.sh` = `uv lock --check`, ruff, `ruff format --check`, `varredura.py` (**limpa**), `sha256sum -c 0001.sha256`, `gerar_0002.py --verificar` e
**2.319 passed, 1 skipped (falta `yaml`), 1 xfailed (gasto, B1.6)** em 157 s. O esperado foi reproduzido.

**Provas** (fora do repositório, em `/tmp/claude-1001/-opt-claude/c3edfc59-52d9-4e44-8d0b-adab74392dfc/scratchpad/rev-b57b/`): `probe/test_rev_probe_a.py` (17 sondas, todas verdes; as que provam defeito afirmam o defeito),
`probe/worker_matavel.py` (worker real em processo à parte, recebe SIGKILL), `sondas.log`, `mut.py` + `mutantes.log` (7 mutantes), `em4x5.log` (EM4 cinco vezes), `check1.log`. Rodam sobre uma cópia de `HEAD` em `copy/`.

## Achados

| # | Sev | Onde | Achado e prova | Correção |
|---|---|---|---|---|
| R1-01 | **ALTO** | `agenda_jobs.py:129-150` (`_SQL_VENCIDOS` só olha `confirmado`), `fila.py:139-147`, `jobs.py:212-215`; texto de D6, D8 e CHANGELOG | **Worker morto depois do CAS prende o lead e o chat para sempre.** D6 diz «se a volta falhar depois dela… o lead é devolvido pelo `reaper_lease`»; isso só vale para exceção (o job termina `failed` e solta o lock). Com **SIGKILL real** no meio da volta (sonda P1: subprocesso trava dentro de `retomar_atendimento`, `kill -9`, segundo worker sobe e roda 3 minutos de `reaper_agenda` + `reaper_lease`): agendamento `disparado`, atendimento `pausado`, job `retomar` `doing` com `worker_id` NULL (o worker novo poda o morto), `reaper_lease` vê **0** leases (`NOT EXISTS job doing no chat`), o `turno` do cliente fica `todo` para sempre. O `reaper_agenda` não toca porque a linha já não é `confirmado`. Mesmo efeito com um `turno`/`lembrete` morto no chat do pausado (P16): `retomar` fica `todo` eternamente, `reaper_agenda` o toma por «job vivo». O aceite EM4 («nenhum perdido») só se sustenta para o kill **antes** do CAS (P14, 3 rodadas, 3 voltas únicas). Deploy com SIGKILL no meio da volta é rotina (Coolify). | Periódica geral de travados **nesta** etapa: o Procrastinate 3.10 tem `job_manager.get_stalled_jobs()` (heartbeat, já cobre `worker_id IS NULL`); `finish_job_by_id_async(id, FAILED, delete_job=False)` em cada um libera o lock. **Validado** (P1b): depois disso o `reaper_lease` enxerga `retomada_perdida` e o turno do cliente sai. Teste novo = a sonda P1 com SIGKILL real. Corrigir D6/D8/CHANGELOG. |
| R1-02 | MÉDIO | `agenda_estado.py:112-124` (`disparar`), `agenda_jobs.py:81`, `jobs.py:114` | **`disparado` é beco sem saída.** D6 reivindica **antes** das pré-checagens, mas o estudo M §2.5 faz `reagendado_sistema` «próximo horário válido, **mesmo agendamento**» e §2.6 faz «tentar» a T+10 min. Depois de `disparado` não há `confirmado` de volta (`disparar` e `confirmar` de novo = `ConflitoVersao`, P13; o CHECK `agendamento_estado_check` também proíbe `disparado_em` em `confirmado`). O desfecho `reagendado_sistema` fica gravado, nada rearma o alarme e o lead dorme até o lease (retoma_em + 30 min) cair no `reaper_lease`. A saída por novo `seq` consome o teto de 2 (`agenda_max_por_atendimento`) e tira do cliente a chance de reagendar. Uma falha transitória no instante da volta (ChatGuru 1 min fora) vira repasse em 30 min, sem a segunda tentativa que o dono aprovou (resposta 1/pergunta 3). | Decidir **antes** da B5.7c: estado de reivindicação com validade (`disparando` + lease, ou `disparado → confirmado` com novo `dispara_em` por função própria) e atualizar o DDL/estudo. |
| R1-03 | MÉDIO | `agenda_jobs.py:78` (só barra o `cedo`), `agenda_jobs.py:129-150` | **Sem teto de atraso.** Após queda longa do worker, alarme tardio ou `reaper_agenda` ainda reivindica e entrega a volta. Sonda P12: 5 h depois da hora combinada (14:00 → 19:00 em SP; um atraso maior já cai fora da janela 08:30–19:00 e pode estourar as 24 h do WhatsApp), `reaper_agenda` e `reaper_lease` enxergam o mesmo caso e `executar_retomar` devolve `disparado` com a volta entregue. O estudo M §2.8 manda a vigia **devolver** em retoma_em + folga, não falar tarde. Quem chega primeiro (reaper_agenda ou reaper_lease) decide, e o outro desiste por causa do job no chat. Combina com R1-02: o `reagendado_sistema` da pré-checagem não tem para onde ir. | `agora > dispara_em + folga_min` ⇒ não reivindicar (`cancelar(por="sistema")` ou deixar o lease agir); teste com relógio +31 min. |
| R1-04 | MÉDIO | `agenda_jobs.py:107-108`, `fila.py:134-136` | **`cedo` rearma o alarme na mesma hora, já vencida no banco: laço quente.** Se o relógio da aplicação atrasa em relação ao `now()` do Postgres (o alarme dispara pelo banco, o `_reivindicar` compara com a aplicação), o `retomar` devolve `cedo`, `agendar_retomada(dispara_em)` cria alarme com `scheduled_at` no passado, que dispara de imediato. Sonda P3: relógio da aplicação 2 s atrás ⇒ **277 jobs em 3 s** (~90/s) por agendamento, e cresce com o desvio. O teste da casa só vê `rearmados == [dispara]`. | Rearmar com atraso real: `schedule_in = (dispara_em − agora_da_app) + 1 s` (mínimo 1 s) e teste com relógio atrasado contando jobs. |
| R1-05 | MÉDIO | `estado.py:658-687` (`pausar`); pendência 1 | **`agenda_max_pausados` não tem dono e `pausar` aceita `retoma_em` em qualquer futuro.** O único código que cria `pausado` não impõe o teto de 10 (pergunta 2 do dono: «até 10 por vez») nem o de 23 h (`agenda_teto_horas`); depende de a B5.7c lembrar. Um `pausado` de 30 dias passa no CHECK (`lease_ate ≥ retoma_em`) e dorme com a IA. Defeito latente que o «B5.7c confere» esconde. | `pausar(…, max_pausados, teto_retoma_em)` conferindo sob `TRAVA_ABRIR` (ou a pendência vira item do aceite da B5.7c com teste nomeado). |
| R1-06 | MÉDIO | `test_agenda_jobs.py:243-299` (`test_desligada_noturna_nao_encerra_pausado`); pendência 3 | **A prova de «a noite não encerra `pausado`» é por espiões e não guarda a B1.6.** Reais no teste: `gravar_bloqueio_entrada`, `selecionar_leases_vencidos` e `PUT /config`, todos anteriores à B5.7b; `expirar_parados`, `tratar_lease_vencido` e `encerrar_por_chave` são `Chamadas` (espiões que nunca mudam estado). Em `src/` não existe nenhum chamador de `estado.encerrar`/`repassar` fora de `estado.py`. O teste passaria com qualquer `pausar` que ponha `lease_ate ≥ retoma_em`. As 19:45/20:15 são da vigia na S2 (fora do repositório). Nota: pelo contrato 08 §5.6 a parada **manual** `ia_ativa=false` **encerra** pausados (`config_rotas.py:38`, certo e testado); a lista do pedido de revisão («`encerrar_por_chave` não encerram») só vale para bloqueio, timer e vigia. | Exportar o predicado (`ESTADOS_EXPIRAVEIS` sem `pausado`) e um teste de contrato que o `expirar_parados` real da B1.6 tem de importar; ou escrever o teste real como aceite da B1.6. |
| R1-07 | BAIXO | `estado.py` (796 linhas) | A 4 linhas do teto de 800; o bloco «pausa combinada» (654–796) é coeso e extraível. A B5.7c precisa mexer aqui (R1-02, reagendar `pausado`) e será forçada a dividir sob pressão. Nenhuma função passa de 40 linhas (maior: `abrir_agendado`, 40). | Dividir já: `estado_pausa.py` depois de tirar `aplicar` do ciclo de importação. |
| R1-08 | BAIXO | `agenda_jobs.py:60` (comentário), `:89-94` (`_registrar_desfecho`) | **Ordem de locks inversa.** `_reivindicar` trava atendimento e depois agendamento; `_registrar_desfecho("resolvido")` faz `UPDATE agendamento` e só então `passo_de_agendamento` (trava o atendimento). O comentário diz «a mesma da API e da B5.7c»; não é. P10 provoca `DeadlockDetected` com duas transações. No job o lock do chat impede retomar×retomar; a janela abre com a B5.7c (cancelamento por webhook trava o atendimento primeiro). | Fazer `_registrar_desfecho` travar o atendimento antes; teste de ordem. |
| R1-09 | BAIXO | `fila.py:143-144` | **Falso positivo do `reaper_agenda` (worker vivo, batimento > 30 s).** Sonda P8: o reaper dá `failed` no `doing` vivo, solta o `lock=chat:` (um turno poderia correr junto com o job velho) e o job velho termina com «Task exception was never retrieved» ao falhar o `finish_job`. **Sem duplicidade**: 1 volta só, o CAS decide. Só ocorre antes do CAS. | Registrar em D8; filtrar o `finish_job` do worker (não é daqui). |
| R1-10 | BAIXO | pendência 5 | O número está errado: a chave `pausa` com `agendamento_ref` (uuid) acrescenta **91 bytes** ao `estado_conversa` (32 sem ref), não ~60 (P4). Estado com 1.957 bytes ou mais não pausa (`TransicaoInvalida atendimento_conversa_check`); o validador Python (`modelos_conversa.py:74`) não enxerga a `pausa`. | Corrigir o texto; reservar 100 bytes no validador. |
| R1-11 | BAIXO | `agendamento.py` (`folga_min`), `api/agendamentos.py:90-94`, `fila.py:139` | **Mutantes que sobrevivem à suíte (7 rodados, 3 relevantes vivos).** M1: a API ignora `agenda_folga_min` da config e usa 30 (ninguém testa folga ≠ 30 pelo `POST`); `AGENDA_FOLGA_MIN=30` está duplicado como padrão em `pausar`/`abrir_agendado` (`estado.py:73`). M2: o 422 de `retoma_fase` movido para depois das recusas de config (contraria D11) segue verde. M3: `reaper_agenda` sem `queueing_lock` segue verde (periódicas empilhariam). M4 (sem `FOR UPDATE` do atendimento) é inócuo: o CAS cobre. Mortos: M5 (worker podado), M6 (`cedo` sem rearmar), M7 (lock por atendimento). | Um teste de `POST` com `agenda_folga_min=45`; um com `agenda_ativa=false` + `retoma_fase=E3`; um do `queueing_lock` da periódica. |
| R1-12 | BAIXO | `jobs.py:114`, `agenda_jobs.py:110-112` | `retomar_atendimento` devolve `str | None` livre; um valor fora do CHECK (`desfecho_disparo`) estoura **depois** da volta entregue: job `failed`, linha segue `retomou`. | Tipar como `Desfecho | None`. |
| R1-13 | BAIXO | `agenda_jobs.py:85` | `Volta.retoma_fase` vem da linha `agendamento`, não de `estado_conversa.pausa.retoma_fase`; o banco não liga os dois (só `pausa.retoma_fase = fase`). Divergência fica silenciosa. | Conferir na reivindicação ou ler do atendimento. |
| R1-14 | BAIXO | `test_agenda_jobs.py:110` | `test_um_agendamento_ativo_por_atendimento` só exercita `agendamento_ativo_uq` e `agendamento_forma_check` da 0001: passaria sem uma linha da B5.7b. É prova do invariante do banco, não do código. | Somar o caminho do `POST` (segundo pedido no mesmo atendimento). |
| R1-15 | BAIXO | `fila.py` (alarme), B5.7c | Reagendar (`seq` 2) **não cancela** o alarme do `seq` 1: ele fica `todo` até a hora velha e vira no-op (`nao_confirmado`), então são dois alarmes na fila (inofensivo). Também não existe função para mover `retoma_em`/`lease_ate` de um `pausado` ou `reservado` agendado (`renovar_lease` os exclui). | Item explícito da B5.7c. |

## Invariantes pedidos: como cada um foi provado

| Invariante | Resultado | Prova |
|---|---|---|
| `pausado` só de E2–E6/E8, nunca E7, em código **e** banco | Certo | `pausar` (lista, `onde_igual` da fase, CHECK `atendimento_conversa_check`); `test_pausar_nunca_em_E7` e `test_pausa_so_de_e2_a_e6_e_e8` rodados; o `UPDATE` direto com `E7` leva `check_violation`. M `onde_igual` removido segue verde porque o CHECK cobre (defesa em profundidade, não lacuna). |
| chave `pausa` ⇔ estado `pausado` | Certo | Banco: `pausado` exige `pausa.retoma_fase = fase` (0001) e `aberto/aguardando` proíbem `pausa` (0003). Para `repassando`/`encerrado` é Python: `repassar`, `encerrar` e `sair_da_pausa` removem no mesmo UPDATE; nenhum outro `aplicar` aceita `pausado` em `de`. |
| `lease_ate ≥ retoma_em` | Certo | CHECK `atendimento_conversa_check` (`0001_esquema.up.sql:143-144`) para `pausado` e `reservado` de agendamento; `renovar_lease` exclui os dois. |
| `reaper_lease` pula `pausado` | Certo | `lease_ate = retoma_em + 30 min`; `test_reaper_pula_pausado` e P1/P16 (só aparece depois do lease, como `retomada_perdida`). |
| `bloqueio_entrada`, timer noturno e 19:45/20:15 não encerram `pausado` | Parcial | Real: `bloqueio_2015` só grava `bloqueio_entrada=true`, `PUT bloqueio_entrada` não agenda encerramento. 19:45/20:15: vigia da S2, fora do repo. `expirar_parados`/`encerrar_por_chave`: espiões (R1-06). |
| Um agendamento ativo por atendimento | Certo | Índice `agendamento_ativo_uq`; reproduzido com `pendente`+`pendente`, `confirmado` e teto `seq` ≤ 2. |
| POST triplicado é noop | Certo | `test_post_triplicado_e_noop` (fila real) e P9: **8 POSTs paralelos** = 1×201 + 7×200 `repetido`, 1 atendimento, 1 agendamento, 1 passo, 1 job. |

## Concorrência com a fila real do Procrastinate 3.10

| Pergunta | Resultado | Prova |
|---|---|---|
| `retomar` corre junto com turno do mesmo chat? | **Não** | P11: dois workers, `turno` de 1,5 s e `retomar` do mesmo chat: `turno` 0,0–1,5, `retomar` 1,53–2,03. O alarme (sem lock) não prende o turno do cliente: SQL de `procrastinate_fetch_job_v2` lido (job `todo` de mesmo lock bloqueia os de id maior **sem olhar `scheduled_at`**), e `test_o_alarme_futuro_nao_prende_o_turno…`. |
| CAS `confirmado → disparado` com 2 workers | Certo | P5, 3 rodadas: dois workers concorrentes, 18 agendamentos, alarme + 3 `retomar` duplicados + `reaper_agenda` cada: **18 voltas, 18 únicas**, linha `disparado` versão 3. Mais `test_quatro_retomar_ao_mesmo_tempo_so_um_reivindica`. |
| `doing` de worker morto, antes do CAS | Certo | P14: SIGKILL real com `concurrency=3`, 3 `confirmado`, um preso antes do CAS: 3 voltas únicas em 3 rodadas. EM4 da casa: **5/5 verdes** (`em4x5.log`). |
| `doing` de worker morto, **depois** do CAS | **Falha** | R1-01 (P1, P16). |
| Worker vivo, lento (falso positivo) ⇒ duplicidade? | **Não** duplica | P8: 1 volta; só o ruído e o lock solto (R1-09). |
| Restart EM4 com 3 `confirmado`, ×5 | Certo | `em4x5.log`: 7/7 em cada uma das 5 rodadas (EM4 + reaper + quatro retomar). |

## `queueing_lock`: D5 está certa

`retomar:{agendamento_id}` (alarme) e `retomar_exec:{agendamento_id}` (job de verdade). O índice é `UNIQUE (queueing_lock) WHERE status = 'todo'` (`schema.sql` do Procrastinate): com `{atendimento_id}` o alarme do
`seq` 2 seria engolido pelo do `seq` 1 ainda `todo`. O mutante M7 (lock por atendimento) morre em `test_post_triplicado_e_noop` e `test_alarme_e_um_por_agendamento…`. **O alarme do `seq` 1 não é cancelado**
(R1-15), vira no-op quando dispara. O pedido que dizia `retomar:{atendimento_id}` estava errado; o estudo M §3 e o DDL (`i` linha 681) dizem `{agendamento_id}`. O roteiro diz `schedule_at` + `lock` por chat e a D4 diverge
com razão (o `lock` no agendado bloqueia o turno do cliente por horas); atualize o roteiro B5.7b («Se der errado») para registrar a divergência.

## API

- **Mesma transação:** P2 faz o enfileirador **real** inserir o job e só depois levantar: atendimento, agendamento, passo e `procrastinate_jobs` ficam todos em **0**. (O teste da casa usa espião que nem chega a inserir; vale a P2.)
- **422:** `retoma_fase=E3` com `agenda_b_digita=false` ⇒ `422 validacao`, `campo: retoma_fase`, `detalhe: {regra: so_e8_sem_agenda_b_digita}`; sem eco do valor. E7/E1/E9 já caem no padrão do modelo (`^E([2-6]|8)$`). A posição (depois do replay, antes das recusas) não tem teste vermelho (M2, R1-11).
- Replay e gêmeo concorrente não enfileiram de novo (P9).

## As pendências declaradas: qual esconde defeito agora

| Pendência | Esconde defeito? |
|---|---|
| 2. `doing` de worker morto segura `lock=chat:` de **qualquer** tarefa | **Sim, é o R1-01.** Deixa de ser «geral, da B1.6» porque a própria B5.7b promete cura. |
| 1. `agenda_max_pausados` não imposto | Sim, R1-05. |
| 3. `expirar_parados`/`encerrar_por_chave` e `pausado` | Sim, R1-06: sem guarda para a B1.6. |
| 5. `pausa` perto do teto de 2 KB | Número errado (91 B), R1-10. |
| 7. `estado.py` 796 | R1-07. |
| 4. Espelho/vigia (K) | Não esconde: fora do repo. |
| 6. Linha no contrato 08 §5.5 | Documental. |

## O que conferi e está certo

- `D4` (alarme sem lock) e `D5` (lock por agendamento): lidos no SQL do Procrastinate e reproduzidos; o roteiro «`schedule_at` + `lock`» está errado, a casa acertou ao divergir.
- CAS por `versao` + `estado = ANY(de)`: dois workers reais, 18 agendamentos, zero duplicidade (P5); `_reivindicar` lê `FOR UPDATE`, confere o estado de espera e só então `disparar`.
- `fora_do_estado` cancela por `sistema` e não fala: com atendimento `encerrado`, `repassando` e `abortado` (P15, os três), o passo `cancelado` entra sem violar o terminal absorvente da 0003.
- `retomar` sem o serviço injetado falha **antes** do CAS (não reivindica sem ter o que entregar).
- Atomicidade do `POST` com a fila real (P2) e idempotência concorrente (P9).
- `abrir_agendado`/`iniciar_agendado`: o `reservado` de vida longa tranca o chat sem tocá-lo; `iniciar_agendado` só vale com `gatilho='agendamento'`; `abortar` do reservado que nunca disparou funciona.
- `repassar`/`encerrar` tiram a `pausa` no mesmo UPDATE; o `encerrado` continua absorvente.
- Qualidade: varredura limpa, ruff limpo, lock coerente, 0001 intacta (`sha256`); nenhuma função acima de 40 linhas nas peças novas; `lease_so_cresce` e o resto do `aplicar` intactos.
- Os dois `xfail` estritos antigos viraram verdes e sobra um (gasto, B1.6), como o CHANGELOG diz.

## Condições para fechar

1. **R1-01** corrigido (periódica geral de travados + teste com SIGKILL real depois do CAS) **ou** registrado como gate duro de produção; D6/D8/CHANGELOG corrigidos de qualquer forma.
2. **R1-02 e R1-03** decididos por escrito antes de abrir a B5.7c (estado de reivindicação com validade; teto de atraso).
3. **R1-04** (rearmar com atraso) e **R1-05** (dono do `agenda_max_pausados`) na B5.7b ou como item de aceite nomeado da B5.7c.
4. **R1-06**: o predicado/teste de contrato entra no aceite da B1.6.
5. Os BAIXO viram issues; R1-08 e R1-12 são de dois minutos.
