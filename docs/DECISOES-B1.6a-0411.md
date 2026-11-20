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
| D3 | **Níveis** `nivel_do_gasto`: < 80 % normal; ≥ 80 % amarelo; ≥ 100 % crítico; > 125 % repassar. Limite zero: com gasto zero ⇒ **crítico** (revisão A7: o operador que zera o limite para barrar entrada nova não repassa todos os abertos; «100 % ⇒ crítico, os abertos concluem»); com qualquer gasto ⇒ repassar (já passou de 125 %). A entrada continua recusando com `gasto ≥ limite`. **Para o dono confirmar:** limite zero com gasto do dia > 0 repassa os abertos no turno seguinte; se a intenção de «zerar» for só barrar entrada, o certo é `bloqueio_entrada`, não o limite. `avaliar_gasto` devolve o pior entre dia (`subteto_dia`) e mês (`teto_mensal_brl`) | 08 §9 |
| D4 | **Soma que falha ⇒ `GastoIndisponivel`**, nunca zero: a entrada responde `503 nao_pronto` com log crítico (sem valor). `MedidorGasto` guarda a soma por 30 s pelo relógio injetado e reinicia quando o dia/mês muda; a entrada continua sem cache (`ttl` só onde se pede) | 08 §9 |
| D5 | **Ciclo do ledger em 4 passos commitados**: (1) cerca + `INSERT reservada ON CONFLICT (idem_key) DO NOTHING` numa transação; (2) CAS `reservada\|transitorio → enviada`; (3) chamada; (4) CAS `enviada → final`. `executar_efeito` **exige** conexão em autocommit e fora de transação (senão a «reserva» seria um savepoint não commitado) e recusa com `RuntimeError` | sp01 Task 8, D14b passo 1 |
| D6 | **A cerca é opcional e explícita** (`Cerca(versao, estados)`, padrão `aberto\|aguardando_cliente`): CAS `versao → versao+1` na transação da reserva. Perdeu ⇒ `ConflitoVersao` (versão mudou) ou `TransicaoInvalida` (estado fora); nada reservado. Repetição da chave **desfaz** a cerca (a versão não anda). O resultado traz a versão nova para a próxima escrita. Sem cerca, só recusa atendimento encerrado. O repasse (B1.6b) passa `estados={"repassando"}` | D14b passo 2 |
| D7 | **`reservada` achada no retry é reivindicada e executa** (diverge do texto da r2, «reservada ⇒ indeterminado»): a chamada só começa depois do CAS `reservada → enviada` commitado, então uma linha `reservada` prova que nada saiu, e só um dos concorrentes ganha o CAS. **`enviada` achada**: se mais velha que `timeout_s + 30 s` a execução dona morreu ⇒ `indeterminado` (nunca reenvia); se recente, está em andamento em outra execução ⇒ devolve `enviada` sem mexer (quem chama não reenvia) | D14b passo 3 |
| D8 | **Falha sem resposta** (timeout, exceção do cliente, `CancelledError`): efeito irreversível ⇒ `indeterminado`; leitura e ação interna ⇒ `transitorio` (repete com a mesma chave; o T12 é idempotente por `repasse_id`, 08 §7.1). O fechamento roda sob `asyncio.shield`; no corte, o ledger grava `indeterminado`, a chamada pendente é cancelada e o `CancelledError` sobe | D14b passo 3, 08 §7.1 |
| D9 | **`modo_efetivo`** = o mais restritivo entre `atendimento.modo` e `config.modo` (real > teste > duble > sombra), lido pelo `LeitorConfig` do chamador (cache ≤ 5 s) na reserva **e de novo** na reivindicação (um `transitorio` reexecutado depois da parada dura vira simulado). Em `sombra\|duble` o destino nunca é chamado: `simular(modo)` se houver, senão `ok` simulado. O ledger grava o `modo` com que o efeito correu; `simulado` é a coluna gerada (`modo <> 'real'`, então `teste` também é «simulado» no banco, embora chame o destino de teste: `ResultadoEfeito.executou` diz se chamou) | 08 §6 |
| D10 | **Posse real** = existe `assumir` do atendimento com `estado='ok'` e `modo ∈ {real, teste}` (ferramenta `assumir`, `acao_interna`, chave `assumir:{atd}`; predicado, sem coluna). **Devolução** (`Pedido.devolucao=True`: T12, `ia-repasse`, nota do repasse, `restaurar`) com posse real corre no modo do **atendimento** (`real\|teste`), mesmo sob parada dura, e o ledger grava esse modo (não o `sombra` global: o efeito aconteceu de verdade). **Sem posse real, simulada por inteiro em qualquer `config.modo`** (revisão A1: antes só sob parada dura; com o global `real` a devolução corria real): o ledger grava o `modo_efetivo` se já for `sombra\|duble`, senão `sombra` (nunca `real` nem `teste`), e não chama o destino | 08 §6 exceções 1 e 2 |
| D11 | **T7/T4 exigem confirmação ligada ao dado** antes de qualquer gravação ou chamada (`ConfirmacaoAusente`; revisão A2): `aceita`, do MESMO atendimento, do tipo da ferramenta (`digitacao` para T7, `consulta` para T4), do MESMO `banco` do pedido, `respondida_em ≤ expira_em`, **não vencida no relógio da execução** (`agora ≤ expira_em`: o prazo de uso é o da própria confirmação, ≤ 60 min pelo DDL) e **não gasta** por outra chave (outra linha do ledger com a mesma `confirmacao_id` fora de `corrigivel\|recusa\|nao_criada`, os desfechos em que a proposta não nasceu). Lida com `FOR SHARE`. Conferida na reserva **só da chave nova** e de novo na reivindicação (quem vai chamar); a repetição de uma T7 terminal devolve o gravado mesmo com o «sim» vencido (quem pergunta «já digitou?» não pode ouvir `ConfirmacaoAusente`). A vaga única de T7 por pessoa e banco (índice da 0001) vira `EfeitoOcupado` (outra unicidade que não a chave) | sp01 Task 8, DDL 0001 `ia.confirmacao` |
| D12 | **`chave_t11(atd, rodada, seq)`** = `t11:{atd}:{rodada}:{seq}`; `rodada` do CAS do `consumir` (`estado_conversa.contadores.rodada`) ou a do claim da volta; `seq` ≥ 1. Sem hora nem `job_id` | D14b passo 1 |
| D13 | **`ia_ativa` relida sem cache** (`chave.ia_ativa_agora`, direto do banco): `encerrar_por_chave` com a IA religada não chama o serviço (devolve `False`); `iniciar` com a IA desligada aborta o `reservado` (motivo `ia_desligada`) **antes** do `assumir` e grava o `encerrou` (`desfecho=ia_desligada`) na mesma transação; outro estado fica (a parada leve fecha). `executar_iniciar`/`executar_encerrar_por_chave` passam a devolver `bool` (a fila ignora) | DECISOES-B1.5:69, r2 B1.5 R1-31 |
| D14 | **`retomar` do reservado agendado** (`dialogo_agendar`) com a IA desligada: cancela o agendamento (`sistema`, passo `cancelado`), aborta o reservado (nunca tocou o chat) e emite `encerrou`; código `ia_desligada`. Roda depois das conferências de estado, `cedo` e teto de atraso, e antes do CAS `disparar`. O **pausado** (caso a) não muda aqui: já tocou o chat, quem o fecha é a parada leve. O apoio de testes `novo_agendado` passou a ligar `ia_ativa` (6 testes da B5.7b rodavam com a IA desligada, o padrão, e agora precisam dela ligada) | R1-31 |
| D15 | **`config_em(nome, instante)`** = a maior versão publicada até o instante; sem versão até lá, a mais antiga; nunca gravada, o padrão do registro. `limites_da_faixa` usa a versão vigente em `iniciado_em` e o teto global (2 lembretes, 7 dias, 3 contrapropostas, R$ 3, 10 agendamentos) | sp01 Task 5 |
| D16 | **Lease de espera com ponto de chamada**: `aguardar_cliente_com_espera` lê intervalos e calendário vigentes (não os de `iniciado_em`: o calendário é o de agora) e o `lembretes_max` da faixa em `iniciado_em`. Faixa sem lembrete: o vácuo encerra no primeiro intervalo, lease = agora + intervalo + 30 min | REVISAO-B1.1-r2 R2, DECISOES-B1.5 pend. 1 |
| D17 | **`expirar_parados`**: `aberto\|aguardando_cliente` (só `ESTADOS_EXPIRAVEIS`) com `agora − iniciado_em > dias_max` (faixa na versão de `iniciado_em`, ≤ 7) e sem job do chat em curso ⇒ `encerrar(expirado, expirar_parados)` sob `FOR UPDATE` + `encerrou` (`desfecho=expirar_parados`). Perdeu o CAS: pula. **Não devolve o chat** (sem `Canal` aqui): em 1–7 dias o `reaper_lease` já repassou; o `encerrou` fecha o espelho e a vigia devolve pelo prazo. Injetado no `worker.montar_servicos` | sp01 Task 5, 08 §7.3 |
| D19 | **A chave é presa ao pedido** (revisão A3): achada a linha, `atendimento_id`, `ferramenta`, `banco`, `args_hash` e `confirmacao_id` têm de ser os do pedido, senão `ChaveDivergente` (nada chamado). O `FOR UPDATE` e o CAS da reivindicação levam o `atendimento_id`. `ferramenta_versao`, `classe_efeito` e `tentativa_n` não entram (a versão muda entre deploys sem mudar o efeito) | revisão A3, autoachado 3 |
| D20 | **A reivindicação não rebaixa** (revisão A4): um `transitorio` que já correu em `real\|teste` não é reivindicado se o modo relido for `sombra\|duble` (parada dura): fica `transitorio` com o modo da tentativa real, sem chamar, e volta a executar quando o global voltar. Uma `reservada` pode ser reivindicada em qualquer modo (nada saiu). **Para o dono:** o `assumir` sem resposta continua **sem** posse real (08 §6 exceção 2, «o `assumir` nunca fechou `ok`»): sob parada dura a devolução dele é simulada e o lead fica com o Amado até a vigia R-b. Contar o `assumir` `transitorio` em `real` como posse «possível» é decisão do contrato, não desta etapa | revisão A4, autoachado 4 |
| D21 | **Cerca e reivindicação na mesma transação** (revisão A5): a reivindicação trava o atendimento (`FOR SHARE`) e reconfere estado e versão (com cerca: a mesma `versao`, que na chave nova é a que a cerca acabou de gravar; sem cerca: não encerrado) junto com o CAS `→ enviada`. A versão continua sem andar na repetição (D6) | revisão A5, autoachado 2 |
| D22 | **Simulação que falha ou é cortada ⇒ `transitorio`** (revisão A6): nada saiu, então a linha não fica `enviada` (que o retry daria como `indeterminado`); log de aviso só com a ferramenta e o tipo da exceção | revisão A6 |
| D23 | **`expirar_parados` em páginas** (revisão A8): keyset por `(iniciado_em, atendimento_id)`, página de 1.000, até achar o lote (200) ou acabar; as versões de `faixas_esforco` são lidas uma vez por rodada (`chave.config_no_tempo`, mesma regra do `config_em`, com teste de equivalência). O prazo continua contado de `iniciado_em` (vida máxima do atendimento, D17), não de `atualizado_em` | revisão A8 |
| D18 | **Outbox do espelho**: `espelho.emitir` exige transação aberta, trava a linha do atendimento, `seq = max+1`, só origem `n8n_braco` (as de `ti` não têm linha no espelho). `detalhe` = `{desfecho, encerrado_em}` sem PII | 08 §7.3 |

## Ficou de fora (e por quê)

1. **Tudo da B1.6b**: processador, repasse em etapas, `Canal` (falso e protocolo), desligamento (`encerrar_por_chave` de verdade), batimento
   90 s fail-closed (D-15), espera do repasse ≤ 30 min (D-14), `publicar_espelho`, `reaper_ledger`, `criar_confirmacao`/`aceitar_confirmacao`,
   handler de `retomada_perdida`/`agendamento_perdido`, as obrigações herdadas da B1.4 (`ErroDoModelo`, `como_decisao_de_falha`, `[dado:campo]`…).
2. **Testes de aceite D14b (ii) e (iii) ponta a ponta**: (iii) `CancelledError` está provado no ledger; (i) está provado no ledger com duas
   rodadas; (ii) «`retomar` reivindicado, `jobs_presos` no meio, `turno` do cliente: ≤ 1 mensagem» precisa do processador e da volta (B1.6b/B5.7c).
3. **`test_parada_dura_intercepta_atendimento_real_aberto` e `test_retomar_nao_acorda_pausado_em_parada_dura`** do roteiro: o ledger já
   intercepta em ≤ 5 s (`test_modo_efetivo_relido_a_cada_efeito_e_gravado_no_ledger`); a versão com o `turno` e a volta é da B1.6b.
4. **Itens novos do roteiro v3.3 B1.6 que ficam com a B1.6b** (revisão A11): **RG-006** `turnos_max = 24` (disjuntor do processador);
   **RG-104** `texto_mensagem` > 4000 ⇒ truncar, marcar e logar, não 422 (entrada e processador; emenda do 08:122 pendente); **RG-075**
   `texto_livre.casos.json` nasce na B1.6b com o sha anotado, e B6.2 e B7.1 copiam de lá. Os testes do roteiro
   `test_teste_nunca_alcanca_facta_real` e `test_sombra_nunca_alcanca_facta_real_nem_canal` existem aqui no nível do ledger
   (`test_teste_vai_ao_destino_de_teste`, `test_sombra_e_duble_nunca_chamam_o_destino`); as versões com o gateway e o `Canal` são da B5.1
   e da B1.6b.
5. **A volta do pausado com a IA desligada** (B5.7c): `retomar_atendimento` deve reler `ia_ativa_agora` antes de `sair_da_pausa`.
6. **Migração**: nenhuma. Se a B1.6b precisar (ex.: `tokens_cache`), é a 0006.
7. **Emendas de contrato** (fora deste repositório): 08 §6 deveria dizer que a devolução com posse real grava o modo do atendimento (D10),
   que a sem posse grava `sombra` (D10), que `reservada` achada é reivindicada (D7) e que o `transitorio` real não se rebaixa (D20); 08 §9
   pode citar `custo_ausente` como definido em D2 e o limite zero de D3.
8. **`valores_hash` × `args_hash` na T7** (revisão A2, autoachado 1): conferir que os argumentos da T7 são os valores confirmados exige que
   o `args_hash` traga o mesmo hash (ou que o ledger receba os valores); decide-se na B1.6b junto com `criar_confirmacao`/`aceitar_confirmacao`.

## Para o revisor tentar derrubar

- D7 (reivindicar `reservada`) contra a r2 da B5.7b. A prova é o par de testes `test_reservada_achada…` e `test_duas_execucoes_concorrentes…`.
- D6: sem cerca, o ledger aceita efeito em `pausado`/`reservado`/`repassando`. É de propósito (repasse e assumir), mas quem envia ao cliente
  tem de passar a cerca; a B1.6b deve provar que o `turno` e o `lembrete` sempre passam.
- Mutações feitas à mão (todas derrubaram ao menos um teste): tirar o `AND versao = %s` da cerca; tirar o `ON CONFLICT`; aceitar
  `indeterminado` como reexecutável; falha virar `transitorio` em efeito irreversível; o corte não gravar; ignorar o modo global; devolução
  sem conferir posse real; `expirar_parados` sem filtro de estado.

## Achados do revisor automático de segurança (04/11)

Os quatro foram fechados na correção da revisão (`docs/REVISAO-B1.6a-0411.md`): 1 ⇒ A2/D11 (menos `valores_hash`, pendência 8); 2 ⇒ A5/D21;
3 ⇒ A3/D19; 4 ⇒ A4/D20.

## Revisão de 04/11 (`docs/REVISAO-B1.6a-0411.md`): destino de cada achado

Cada correção veio com teste que reprova sem ela, conferido rodando os testes novos contra o código anterior: no ledger, 17 dos 18 casos
novos reprovaram (o 18º, `test_t7_corrigivel_nao_gasta_a_confirmacao`, é a guarda do desenho de D11 e passa nos dois de propósito); o caso
`(0, 0) ⇒ critico` reprova no `gasto.py` anterior; o teste de páginas reprova no `expiracao.py` anterior; o do job de produção reprova com a
lambda do worker trocada por outra que não expira nada. O A10 não muda código de produção (só tira a dependência do relógio de parede).

| Achado | Gravidade | Destino | Testes |
|---|---|---|---|
| A1 devolução sem posse corre real com o global `real` | ALTO | corrigido (D10) | `test_devolucao_sem_posse_real_e_simulada_mesmo_com_o_global_real[3]`, `test_devolucao_em_teste_sem_posse_real_tambem_e_simulada` |
| A2 confirmação da T7 só confere `aceita` | ALTO | corrigido (D11), menos `valores_hash` (pendência 8) | `test_t7_com_confirmacao_que_nao_e_deste_dado_levanta_antes_do_banco[4]`, `test_t7_nao_reusa_a_confirmacao_gasta_por_outra_chave`, `test_t7_repetida_confere_a_confirmacao_so_quando_vai_chamar`, `test_t7_corrigivel_nao_gasta_a_confirmacao` |
| A3 chave não presa ao atendimento | MÉDIO | corrigido (D19) | `test_chave_de_outro_atendimento_e_recusada_sem_chamar`, `test_chave_com_outros_argumentos_e_recusada_sem_chamar` |
| A4 reivindicação rebaixa o modo | MÉDIO | corrigido (D20); a posse «possível» do `assumir` sem resposta fica para o dono | `test_transitorio_real_nao_e_rebaixado_pela_parada_dura` |
| A5 reivindicação sem a cerca | BAIXO | corrigido (D21) | `test_reivindicacao_reconfere_a_cerca_na_mesma_transacao`, `test_reivindicacao_sem_cerca_recusa_atendimento_encerrado_no_meio` |
| A6 `simular` que levanta deixa `enviada` | BAIXO | corrigido (D22) | `test_simulacao_que_falha_fica_transitorio_e_repete`, `test_corte_na_simulacao_fica_transitorio` |
| A7 limite zero leva a `repassar` | BAIXO | corrigido para gasto zero (D3); limite zero com gasto > 0 segue repassando, para o dono confirmar | `test_80_100_125_por_cento[…]` (dois casos novos) |
| A8 N+1 e candidatos de fora | BAIXO | corrigido (D23); o prazo segue de `iniciado_em` (D17) | `test_candidatos_velhos_dentro_do_prazo_nao_escondem_os_vencidos`, `test_config_no_tempo_segue_a_regra_do_config_em` |
| A9 teste do job de produção só confere `configurado()` | BAIXO | corrigido: o teste executa a injeção de produção (reprova com a lambda trocada) | `test_o_job_usa_o_servico_de_producao` |
| A10 teste instável na virada do dia | BAIXO | corrigido: relógio fixo, com um passo do dia seguinte que não pode entrar | `test_gasto_do_dia_soma_passos_em_brt_e_todos_os_modos` |
| A11 itens da v3.3 sem dono declarado | BAIXO | registrado (Ficou de fora, item 4) | — |

## Retomada de 20/11 (rebase sobre a `main` com B1.8 e B5.1; achados da revisão geral de 10/11)

O ramo foi rebaseado sobre `origin/main` (`9a4baca`, com B1.8 e B5.1): o único conflito foi de texto no `CHANGELOG.md` (as duas entradas
ficam). Nenhum conflito de código; B1.6a, B1.8 e B5.1 passam juntas pelo portão (G-0076/RG-045), menos os 11 testes que já falham na
própria `main` em 20/11 (dependem do relógio de parede ou do irmão `cliente360-api`; tratados em PR à parte).

| # | Achado (REVISAO-GERAL-0911) | Decisão | Testes |
|---|---|---|---|
| D24 | **G-0131 (ALTO)** linha `enviada` órfã virava `indeterminado` terminal para qualquer classe: o T12 morto no meio nunca mais se repetia | `desfecho_da_orfa`: só efeito irreversível que correu em `real\|teste` vira `indeterminado`; ação interna (T12, `assumir`, `restaurar`), leitura e qualquer efeito simulado voltam a `transitorio` e são reivindicados NA MESMA chamada (executa uma vez). Corrige D7 e alinha com D8 e o 08 §7.1 | `test_orfa_de_acao_interna_volta_a_transitorio_e_executa_uma_vez[t12,assumir]`, `test_orfa_simulada_de_irreversivel_volta_a_transitorio` |
| D25 | **G-0087 (ALTO, parte do ledger)** efeito irreversível despachado podia voltar `transitorio` (erro tipado depois do disparo) e se repetir | `Desfecho.nada_saiu` (padrão `False`): `transitorio` de efeito irreversível em `real\|teste` só fica `transitorio` se o protocolo PROVA que nada chegou ao destino; senão vira `indeterminado`. A parte do gateway (reconstrução inválida, `BANCO_INDISPONIVEL` e `CancelledError` depois do disparo) é da B5.4 | `test_transitorio_de_irreversivel_sem_prova_vira_indeterminado`, `test_transitorio_de_irreversivel_com_prova_repete` |
| D26 | **G-0454 (MÉDIO)** T11 sem `args_hash`: mensagem diferente na mesma `(rodada, seq)` era engolida como repetição | `Pedido` de `efeito_irreversivel` exige `args_hash` (sha256 hex do conteúdo); a mesma chave com outro conteúdo dá `ChaveDivergente`. A regra de `seq` para lembrete, TX-42 e volta é da B1.6b | `test_irreversivel_sem_args_hash_e_recusado`, `test_t11_mesma_chave_outro_texto_e_chave_divergente` |
| — | **F4-027 (MÉDIO)** runbook | `docs/OPERACAO.md` §12: `indeterminado`, linhas presas, 503 por gasto, `expirar_parados` | — |

Mutação conferida: com o `ledger.py` anterior, 6 dos 7 testes novos reprovam (o 7º, `…_outro_texto_…`, já passava: guarda de regressão).

Ficam para a B1.6b (critério de aceite dela, não deste PR): G-0093 (`expirar_parados` com posse real passa pelo repasse), G-0116
(`reaper_ledger`), G-0216 (batimento, `publicar_espelho`, repasse em etapas), G-0020/G-0032 (R-c2), G-0565 (desligamento), RG-104
(texto > 4000 trunca) e RG-006 (`turnos_max = 24`). **G-0085** (máscara de logs nunca ligada) é da `main` desde a B1.5 e segue aberto
(critério da B1.7). **Decisões que seguem com o dono:** D3 (limite zero com gasto > 0 repassa os abertos) e D20 (o `assumir` sem
resposta não dá posse real); aplicado o padrão documentado.
