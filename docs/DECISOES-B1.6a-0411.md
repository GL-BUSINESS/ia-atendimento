# B1.6a · Ledger `t11` com cerca de `versao`, `executar_efeito`, gasto Σ, `ia_ativa` relida, lease de espera e `expirar_parados`: decisões e pendências

Branch `feat/b1-6a`, a partir da `main` (`9bee6a4`). Especificação: roteiro v3.3 B1.6 (divisão RG-045: esta é a metade **a**), contrato 08 v2.3
§6 (modos, posse real), §9 (gasto) e §14 (testes); receita D14b da revisão 2 da B5.7b (`docs/REVISAO-B5.7b-0311-r2.md` §2 e §6;
`docs/DECISOES-B5.7b-0211.md`, gates 1 e 3); obrigações herdadas de `docs/DECISOES-B1.5-3010.md:69` e de `docs/REVISAO-B1.5-3010-r2.md` §6.
Feito só local: nada aplicado na S2, na S4, na VPS, no n8n nem no Coolify; sem tag, sem merge. **Sem migração nova**: o esquema da 0001/0004
já tem tudo o que esta metade usa (a 0006 continua livre; a 0005 é do domingo).

## O que entra aqui e o que fica para a B1.6b

| B1.6a (aqui) | B1.6b (depois) |
|---|---|
| `ledger.py`: `executar_efeito`, cerca de `versao`, `modo_efetivo`, `posse_real`, `chave_t11`, `ConfirmacaoAusente`, `EfeitoOcupado` | `processador.py` (`iniciar`, `processar`, 2 falhas ⇒ repasse, disjuntor), `repasse.py` (nota → chatbot → rota → marca → lease) |
| `gasto.py`: Σ `passo.custo_brl` em BRT, `custo_ausente`, 80/100/125 %, cache de 30 s, `GastoIndisponivel` ⇒ `503 nao_pronto` | o `turno` consultar `avaliar_gasto` antes do modelo (alerta 1×/dia e 1×/mês; > 125 % repassa) |
| `ia_ativa` relida: `encerrar_por_chave`, `iniciar`, `retomar` do reservado agendado | o serviço `encerrar_por_chave` em si (repassar aberto/aguardando/pausado), o desligamento |
| `espera.py`: `limites_da_faixa`, `lease_de_espera_do_atendimento`, `aguardar_cliente_com_espera`; `chave.config_em` | quem chama `aguardar_cliente_com_espera` (o processador, depois de responder) |
| `expiracao.py`: `expirar_parados` real, injetado no worker | `Canal` falso/real, batimento 90 s fail-closed (D-15), repasse ≤ 30 min (D-14), `publicar_espelho` |
| `espelho.py`: `emitir`/`emitir_encerrou` na transação da mudança de estado | os outros eventos (`assumiu`, `pausou`, `retomou`) e o `encerrou` dos demais encerramentos |

## Decisões

| # | Decisão | Fonte |
|---|---|---|
| D1 | **Gasto = Σ `passo.custo_brl` por `ocorrido_em`**, dia e mês de America/Sao_Paulo convertidos a UTC no código (`calendario.limites_*`), todos os modos. `ferramenta_chamada.custo_brl` e `atendimento.custo_modelo_brl`/`custo_midia_brl` **não** entram. Saiu de `chave.py` para `gasto.py` (`chave` reexporta `gasto_dia`/`gasto_mes`/`GastoIndisponivel`). O `xfail` estrito de `tests/test_gasto_pendente.py` caiu; o nome do arquivo ficou para o histórico | 08 §9, R1-14 |
| D2 | **`custo_ausente`** = passo do dia com `custo_brl` nulo **e** (tokens não nulos **ou** `decisao` do modelo). Passo `erro` sem tokens nem custo não conta (não houve chamada ao modelo). Só a contagem; o alerta crítico é de quem lê (B1.6b) | 08 §9 |
| D3 | **Níveis** `nivel_do_gasto`: < 80 % normal; ≥ 80 % amarelo; ≥ 100 % crítico; > 125 % repassar. Limite zero ⇒ repassar (qualquer gasto já passou dele; a entrada já recusa com `gasto ≥ limite`). `avaliar_gasto` devolve o pior entre dia (`subteto_dia`) e mês (`teto_mensal_brl`) | 08 §9 |
| D4 | **Soma que falha ⇒ `GastoIndisponivel`**, nunca zero: a entrada responde `503 nao_pronto` com log crítico (sem valor). `MedidorGasto` guarda a soma por 30 s pelo relógio injetado e reinicia quando o dia/mês muda; a entrada continua sem cache (`ttl` só onde se pede) | 08 §9 |
| D5 | **Ciclo do ledger em 4 passos commitados**: (1) cerca + `INSERT reservada ON CONFLICT (idem_key) DO NOTHING` numa transação; (2) CAS `reservada\|transitorio → enviada`; (3) chamada; (4) CAS `enviada → final`. `executar_efeito` **exige** conexão em autocommit e fora de transação (senão a «reserva» seria um savepoint não commitado) e recusa com `RuntimeError` | sp01 Task 8, D14b passo 1 |
| D6 | **A cerca é opcional e explícita** (`Cerca(versao, estados)`, padrão `aberto\|aguardando_cliente`): CAS `versao → versao+1` na transação da reserva. Perdeu ⇒ `ConflitoVersao` (versão mudou) ou `TransicaoInvalida` (estado fora); nada reservado. Repetição da chave **desfaz** a cerca (a versão não anda). O resultado traz a versão nova para a próxima escrita. Sem cerca, só recusa atendimento encerrado. O repasse (B1.6b) passa `estados={"repassando"}` | D14b passo 2 |
| D7 | **`reservada` achada no retry é reivindicada e executa** (diverge do texto da r2, «reservada ⇒ indeterminado»): a chamada só começa depois do CAS `reservada → enviada` commitado, então uma linha `reservada` prova que nada saiu, e só um dos concorrentes ganha o CAS. **`enviada` achada**: se mais velha que `timeout_s + 30 s` a execução dona morreu ⇒ `indeterminado` (nunca reenvia); se recente, está em andamento em outra execução ⇒ devolve `enviada` sem mexer (quem chama não reenvia) | D14b passo 3 |
| D8 | **Falha sem resposta** (timeout, exceção do cliente, `CancelledError`): efeito irreversível ⇒ `indeterminado`; leitura e ação interna ⇒ `transitorio` (repete com a mesma chave; o T12 é idempotente por `repasse_id`, 08 §7.1). O fechamento roda sob `asyncio.shield`; no corte, o ledger grava `indeterminado`, a chamada pendente é cancelada e o `CancelledError` sobe | D14b passo 3, 08 §7.1 |
| D9 | **`modo_efetivo`** = o mais restritivo entre `atendimento.modo` e `config.modo` (real > teste > duble > sombra), lido pelo `LeitorConfig` do chamador (cache ≤ 5 s) na reserva **e de novo** na reivindicação (um `transitorio` reexecutado depois da parada dura vira simulado). Em `sombra\|duble` o destino nunca é chamado: `simular(modo)` se houver, senão `ok` simulado. O ledger grava o `modo` com que o efeito correu; `simulado` é a coluna gerada (`modo <> 'real'`, então `teste` também é «simulado» no banco, embora chame o destino de teste: `ResultadoEfeito.executou` diz se chamou) | 08 §6 |
| D10 | **Posse real** = existe `assumir` do atendimento com `estado='ok'` e `modo ∈ {real, teste}` (ferramenta `assumir`, `acao_interna`, chave `assumir:{atd}`; predicado, sem coluna). **Devolução** (`Pedido.devolucao=True`: T12, `ia-repasse`, nota do repasse, `restaurar`) com posse real corre no modo do **atendimento** (`real\|teste`), mesmo sob parada dura, e o ledger grava esse modo (não o `sombra` global: o efeito aconteceu de verdade). Sem posse real, simulada | 08 §6 exceções 1 e 2 |
| D11 | **T7/T4 exigem confirmação `aceita` do MESMO atendimento** antes de qualquer gravação ou chamada (`ConfirmacaoAusente`). Não confere `expira_em` (a aceitação já exige `agora ≤ expira_em`; quem aceita é a B1.6b). A vaga única de T7 por pessoa e banco (índice da 0001) vira `EfeitoOcupado` (outra unicidade que não a chave) | sp01 Task 8 |
| D12 | **`chave_t11(atd, rodada, seq)`** = `t11:{atd}:{rodada}:{seq}`; `rodada` do CAS do `consumir` (`estado_conversa.contadores.rodada`) ou a do claim da volta; `seq` ≥ 1. Sem hora nem `job_id` | D14b passo 1 |
| D13 | **`ia_ativa` relida sem cache** (`chave.ia_ativa_agora`, direto do banco): `encerrar_por_chave` com a IA religada não chama o serviço (devolve `False`); `iniciar` com a IA desligada aborta o `reservado` (motivo `ia_desligada`) **antes** do `assumir` e grava o `encerrou` (`desfecho=ia_desligada`) na mesma transação; outro estado fica (a parada leve fecha). `executar_iniciar`/`executar_encerrar_por_chave` passam a devolver `bool` (a fila ignora) | DECISOES-B1.5:69, r2 B1.5 R1-31 |
| D14 | **`retomar` do reservado agendado** (`dialogo_agendar`) com a IA desligada: cancela o agendamento (`sistema`, passo `cancelado`), aborta o reservado (nunca tocou o chat) e emite `encerrou`; código `ia_desligada`. Roda depois das conferências de estado, `cedo` e teto de atraso, e antes do CAS `disparar`. O **pausado** (caso a) não muda aqui: já tocou o chat, quem o fecha é a parada leve. O apoio de testes `novo_agendado` passou a ligar `ia_ativa` (6 testes da B5.7b rodavam com a IA desligada, o padrão, e agora precisam dela ligada) | R1-31 |
| D15 | **`config_em(nome, instante)`** = a maior versão publicada até o instante; sem versão até lá, a mais antiga; nunca gravada, o padrão do registro. `limites_da_faixa` usa a versão vigente em `iniciado_em` e o teto global (2 lembretes, 7 dias, 3 contrapropostas, R$ 3, 10 agendamentos) | sp01 Task 5 |
| D16 | **Lease de espera com ponto de chamada**: `aguardar_cliente_com_espera` lê intervalos e calendário vigentes (não os de `iniciado_em`: o calendário é o de agora) e o `lembretes_max` da faixa em `iniciado_em`. Faixa sem lembrete: o vácuo encerra no primeiro intervalo, lease = agora + intervalo + 30 min | REVISAO-B1.1-r2 R2, DECISOES-B1.5 pend. 1 |
| D17 | **`expirar_parados`**: `aberto\|aguardando_cliente` (só `ESTADOS_EXPIRAVEIS`) com `agora − iniciado_em > dias_max` (faixa na versão de `iniciado_em`, ≤ 7) e sem job do chat em curso ⇒ `encerrar(expirado, expirar_parados)` sob `FOR UPDATE` + `encerrou` (`desfecho=expirar_parados`). Perdeu o CAS: pula. **Não devolve o chat** (sem `Canal` aqui): em 1–7 dias o `reaper_lease` já repassou; o `encerrou` fecha o espelho e a vigia devolve pelo prazo. Injetado no `worker.montar_servicos` | sp01 Task 5, 08 §7.3 |
| D18 | **Outbox do espelho**: `espelho.emitir` exige transação aberta, trava a linha do atendimento, `seq = max+1`, só origem `n8n_braco` (as de `ti` não têm linha no espelho). `detalhe` = `{desfecho, encerrado_em}` sem PII | 08 §7.3 |

## Ficou de fora (e por quê)

1. **Tudo da B1.6b**: processador, repasse em etapas, `Canal` (falso e protocolo), desligamento (`encerrar_por_chave` de verdade), batimento
   90 s fail-closed (D-15), espera do repasse ≤ 30 min (D-14), `publicar_espelho`, `reaper_ledger`, `criar_confirmacao`/`aceitar_confirmacao`,
   handler de `retomada_perdida`/`agendamento_perdido`, as obrigações herdadas da B1.4 (`ErroDoModelo`, `como_decisao_de_falha`, `[dado:campo]`…).
2. **Testes de aceite D14b (ii) e (iii) ponta a ponta**: (iii) `CancelledError` está provado no ledger; (i) está provado no ledger com duas
   rodadas; (ii) «`retomar` reivindicado, `jobs_presos` no meio, `turno` do cliente: ≤ 1 mensagem» precisa do processador e da volta (B1.6b/B5.7c).
3. **`test_parada_dura_intercepta_atendimento_real_aberto` e `test_retomar_nao_acorda_pausado_em_parada_dura`** do roteiro: o ledger já
   intercepta em ≤ 5 s (`test_modo_efetivo_relido_a_cada_efeito_e_gravado_no_ledger`); a versão com o `turno` e a volta é da B1.6b.
4. **A volta do pausado com a IA desligada** (B5.7c): `retomar_atendimento` deve reler `ia_ativa_agora` antes de `sair_da_pausa`.
5. **Migração**: nenhuma. Se a B1.6b precisar (ex.: `tokens_cache`), é a 0006.
6. **Emendas de contrato** (fora deste repositório): 08 §6 deveria dizer que a devolução com posse real grava o modo do atendimento (D10) e que
   `reservada` achada é reivindicada (D7); 08 §9 pode citar `custo_ausente` como definido em D2.

## Para o revisor tentar derrubar

- D7 (reivindicar `reservada`) contra a r2 da B5.7b. A prova é o par de testes `test_reservada_achada…` e `test_duas_execucoes_concorrentes…`.
- D6: sem cerca, o ledger aceita efeito em `pausado`/`reservado`/`repassando`. É de propósito (repasse e assumir), mas quem envia ao cliente
  tem de passar a cerca; a B1.6b deve provar que o `turno` e o `lembrete` sempre passam.
- Mutações feitas à mão (todas derrubaram ao menos um teste): tirar o `AND versao = %s` da cerca; tirar o `ON CONFLICT`; aceitar
  `indeterminado` como reexecutável; falha virar `transitorio` em efeito irreversível; o corte não gravar; ignorar o modo global; devolução
  sem conferir posse real; `expirar_parados` sem filtro de estado.

## Achados do revisor automático de segurança (04/11), em aberto para a etapa de revisão e correção

Registrados por ele para tratar **depois** da revisão deste PR e **antes de qualquer merge**; não mexi para não atravessar essa etapa:

1. **ALTO** · `_exigir_confirmacao` só confere `estado='aceita'`: exigir `tipo` (`digitacao` para T7), `banco` igual ao do pedido, `valores_hash`
   dos valores confirmados, não vencida pelo relógio da decisão, `FOR SHARE` e uso único.
2. **MÉDIO** · Linha existente reexecutável com cerca: o CAS de `versao` e a reivindicação devem ir na mesma transação (hoje a cerca é desfeita
   na repetição e `_reivindicar` roda sem ela); reconferir estado e versão em `_reivindicar`.
3. **MÉDIO** · A chave não está presa ao pedido: ao achar a linha, conferir `atendimento_id`, `ferramenta`, `banco`, `args_hash` e
   `confirmacao_id` e recusar divergência; `_reivindicar` com `atendimento_id` no CAS.
4. **MÉDIO** · A reivindicação pode rebaixar o modo: um `transitorio` que rodou em `real|teste` e é reexecutado sob parada dura vira
   simulado e apaga que a tentativa anterior foi real (risco concreto: `assumir` sem resposta ⇒ `transitorio` ⇒ simulado ⇒ sem posse real ⇒
   devolução simulada). Guardar o modo mais forte já tentado, ou não reivindicar nesse caso.
