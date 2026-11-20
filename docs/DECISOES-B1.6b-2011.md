# B1.6b · Processador, repasse por etapas, `Canal`, batimento fail-closed, desligamento, `reaper_ledger` e publicador do espelho: decisões e pendências

Branch `feat/b1-6b`, empilhada sobre `feat/b1-6a` (PR #13). Especificação: roteiro v3.3 B1.6 (metade **b** da divisão RG-045), contrato 08
v2.4 §6, §7.1–§7.4, §9 e §14; achados da revisão geral de 10/11 (`estudos/REVISAO-GERAL-0911.md`) que caem neste bloco. Construção só
local, retomada pelo dono em 20/11: nada aplicado na S2, na S4, no n8n nem no Coolify; sem tag, sem merge, **sem migração nova** (a 0006
continua livre).

## Ajustes de escopo do dono (20/11)

1. **Sem adaptador real de delegação nem de `ia-repasse`.** O caminho `ia-repasse → webhook do zVuE` está morto em produção desde 30/10; a
   delegação real hoje é a edge function `delegar-pre-aprovado` (gl-painel + robô de tela) e o desenho volta ao dono (estudo do CLT de
   17/11, `levantamento/16-prontidao-ia.md` §3, **DEC-PIA-002/003/004**). Por isso repasse, `Canal`, espelho e desligamento ficam atrás de
   **portas** (`PortaCanal`, `PortaRepasse`, `PortaEspelho`, `FonteBatimento`, `Motor`, `Alertas`) com implementação falsa e testes contra a
   porta. **O adaptador real depende de DEC-PIA-002.**
2. **Hospedagem:** a IA vai para uma S5 que o dono ainda configura, não para a VPS. Nada aqui fixa host nem IP: o endereço do batimento é
   da porta `FonteBatimento`. As menções a VPS/10.90.0.5 em `docs/OPERACAO.md` §8–§10 e nos kits ficam como estão (só anotado em §12).

## Decisões

| # | Decisão | Fonte |
|---|---|---|
| E1 | **`batimento.py`**: `LeitorBatimento` guarda o último v2 aceito. Ausente, `v ≠ 2`, forma inválida, `seq` que regride, `gerado_em` sem fuso ou idade > 90 s ⇒ `indisponivel` (fail-closed, D-15) + alerta crítico. 59/75/89 s não bloqueiam; 91 s bloqueia. Forma inválida derruba o aceito; `seq` que regride é recusado e o anterior envelhece. A falha da porta conta como ausente | 08 §7.4, R2-04, D-15 |
| E2 | Regras: (i) `impedidos` barra sempre; (ii) `vivos` com o estado esperado só quando quem chama pede (`esperado_em_vivos`): retomada, e a 1ª ação depois de indisponibilidade (`recem_voltou`, que nasce `True` no processo novo = reaper do boot); (iii) o `iniciar` e o 1º turno dele, e o repasse (que não está em `vivos`), usam só a (i) | 08 §7.4 |
| E3 | **`canal.py`**: `Canal` = batimento + ledger + `PortaCanal`. Só consulta o batimento quem faria efeito REAL (`modo_efetivo ∈ {real, teste}`, ou devolução com posse real); `impedido` ⇒ `CercoFechado`, `indisponivel` ⇒ `BatimentoIndisponivel`, `fora_de_vivos` ⇒ `ForaDeVivos`, sempre ANTES de reservar no ledger. Chaves: `t11:{atd}:{rodada}:{seq}` com `args_hash` do texto, `nota:{atd}` (irreversível, devolução), `restaurar:{atd}` (ação interna, devolução), `assumir:{atd}`. Em `teste` o texto leva «[TESTE] ». O `assumir` devolve o chatbot anterior em `ref_externa` (`ligado\|desligado\|desconhecido`) | 08 §6, §7.4 |
| E4 | **Regra do `seq` (G-0454):** cada turno bom abre `rodada + 1` (CAS no `estado_conversa.contadores`) e numera os textos 1..n; a falha do modelo não abre rodada. Dois envios distintos nunca dividem chave (teste). O lembrete, a TX-42 e a volta ganham rodada própria quando forem ligados ao `Canal` (B5.5/B5.7c) | G-0454 |
| E5 | **`repasse.py`** (08 §7.1): fase 1 `iniciar_repasse` (CAS → `repassando`, `repasse_modo='indicado'`); fase 2 `executar_repasse` = nota → chatbot → rota → marca → lease, cada etapa um passo `repasse` com `resultado` (`ok\|transitorio\|incerto\|pulado`) e `motivo`; o job retoma pelo primeiro marco sem desfecho. `Passo.Repasse` ganhou `resultado` e `motivo` (colunas já existentes) | 08 §7.1 |
| E6 | **Nota**: UMA chamada. `ok` ⇒ `sim` (`repasse_nota_enviada=true`, tamanho); `indeterminado` (timeout, corte) ⇒ `incerta` (true, nunca repete); recusa ou `transitorio` com `nada_saiu` ⇒ `pulado/nota_nao_entregue`, `nao`, alerta amarelo, segue sem nota; sem mensagem da IA ao cliente ⇒ `pulado/nao_aplica`. O texto real (TX-34) vem do catálogo de textos; aqui `nota_padrao` é marcador | 08 §7.1, 02 §5 |
| E7 | **Chatbot**: `intocado` ⇒ pula; senão `Canal.restaurar` com retry próprio (transitório reagenda com backoff); recusa ⇒ `nao_confirmou`, crítico, segue | 08 §7.1, K §3.3.7 |
| E8 | **Rota**: `t12:{atd}` no ledger (ação interna, idempotente por `repasse_id`); o resultado do n8n vai em `ref_externa`. `delegou\|fechado_sem_delegar` ⇒ `encerrado(repassado)`; `ja_devolvido` ⇒ `devolvido_pela_s2`; `sem_consultor\|desconhecido` ⇒ `repassado` + `repasse_sem_consultor` + crítico; `em_andamento\|falha_transitoria`/sem resposta ⇒ `transitorio` e backoff; qualquer outra resposta ⇒ crítico e trava sem repetir. Depois da 1ª tentativa de rota o batimento não é consultado | 08 §7.1, §7.2 |
| E9 | **Batimento no repasse**: antes da nota e antes do chatbot, enquanto a rota não teve tentativa. `impedido` ⇒ `encerrado(repassado, devolvido_pela_s2)` sem nota, sem restaurar, sem rota. `indisponivel` ⇒ nada sai e o job espera (15 s) dentro do MESMO prazo de D-14 | 08 §7.1 (R2-03), D-15 |
| E10 | **D-14**: prazo de 30 min contado de `min(desde, 1ª tentativa de rota)`; `desde` = 1ª rodada do job, levada pelo reagendamento (o job novo herda; um reenfileiramento manual recomeça). Backoff 10 s, 30 s, 90 s, 4 min e depois 5 min; a próxima tentativa só é marcada se cabe nos 30 min (a 1ª + 8 repetições, a última aos ≈ 26 min); sem jitter (a fila já espalha). Esgotado ⇒ `repasse_travado` em `contexto_codigos`, passo, alerta **crítico** e alerta **`humano`** (G-0020: o lead vai a uma pessoa por canal que não passe pela S2, B6.6), e o job PARA com o atendimento em `repassando` | 08 §7.2, D-14 |
| E11 | **R-c2 do lado do orquestrador (G-0032)**: `repasse.repasses_travados(conn)` lista as chaves travadas para a vigia devolver por `indicado`. A regra da vigia, a rota que expõe a lista e o «crítico a cada 10 min» são da B6.4/B6.6 (**DN-28, decisão do dono**); padrão aplicado aqui: marcar, alertar `humano` e listar | G-0032, G-0020, RG-095 |
| E12 | **Sem posse real** (nasceu `sombra\|duble`, ou o `assumir` nunca fechou `ok`): as cinco etapas são simuladas, sem porta nenhuma, e fecha `sem_venda/repasse_simulado` com o `encerrou` | 08 §6 exc. 2 |
| E13 | **`processador.py`**: `iniciar` (regra i ⇒ `assumir` com cerca `reservado` ⇒ `estado.iniciar` + `assumiu` na mesma transação ⇒ 1º turno); `processar` na ordem: `aguardando → aberto`; batimento; transversais (gancho); gasto (falha ⇒ 60 s sem modelo; 80/100 % alertam 1×/dia por nível; > 125 % repassa); disjuntor (`turnos ≥ 24`, RG-006, ou custo do atendimento > `custo_max_brl` da faixa); `Motor.decidir`; envio com cerca; `aguardar_cliente_com_espera` ou repasse | roteiro B1.6, 08 §9 |
| E14 | **`ErroDoModelo`** conta em `estado_conversa.contadores.falhas` (CAS); a 2ª seguida ⇒ repasse `duas_falhas`; o turno bom zera. O `Motor` é porta: o agente da B1.4 entra na integração (B1.7) | DECISOES-B1.4:175 |
| E15 | **Execução superada**: perder a cerca (outra execução mexeu na versão) ⇒ `superado`, nada enviado (o motor pode ter rodado: o custo conta, a mensagem não sai) | D14b |
| E16 | **Desligamento** (`encerrar_por_chave`, depois de reler `ia_ativa`): `reservado` ⇒ `abortado` + `encerrou(ia_desligada)`; `aberto\|aguardando_cliente\|pausado` ⇒ repasse `ia_desligada` (nota e chatbot voltam ao vendedor); `repassando\|encerrado` não mudam (G-0565) | DECISOES-B1.5:69, G-0565 |
| E17 | **`reaper_ledger.py` (G-0116)**: `reservada` > 10 min ⇒ `nao_criada` (libera a vaga da T7 da pessoa); `enviada\|em_andamento` além de 10 s + 30 s ⇒ `desfecho_da_orfa` (irreversível real ⇒ `indeterminado` + crítico; o resto ⇒ `transitorio`). CAS por estado. A T8 que resolve o `indeterminado` da T7 é da B5.4 | G-0116, G-0131 |
| E18 | **`publicar_espelho.py` (G-0216)**: por atendimento só o 1º pendente sai (ordem de `seq`); sem resposta ⇒ `tentativas+1` e `proxima_em` pelo backoff; resposta fora do vocabulário ⇒ crítico e repete; `impedido` ⇒ `encerrado(repassado, devolvido_pela_s2)`; pendente > 10/30 min ⇒ amarelo/crítico. Periódica de 1 min (o 08 pede 10 s; o defer na transação fica para a integração) | 08 §7.3 |
| E19 | **`expirar_parados` com posse real passa pelo repasse (G-0093)**: fase 1 `repassando/expirar_parados` + job `repasse`; o `encerrou` sai quando o repasse fecha. Sem quem enfileire (`Servicos` sem a B1.6b, o caso de produção hoje) não mexe: `repassando` sem job ficaria órfão. Sem posse real continua encerrando `expirado` direto | G-0093 |
| E20 | **Texto > 4000 trunca (RG-104/G-0120)**: `/eventos/chatguru` e `/eventos/mensagem` aceitam o texto (o corpo segue limitado a 64 KB ⇒ 413), truncam em 4000 e logam só o tamanho; nunca 422 | 08 v2.4 §5.1 |
| E21 | **Pré-condições reconferidas no disparo (achado MÉDIO da revisão automática de segurança, 20/11, TOCTOU no gateway da B5.1)**: `_preparar_disparo` confere de novo as pré-condições depois da vaga do limitador e de novo depois da leitura do CPF, logo antes do disparo; a 1ª conferência vira a recusa cedo | revisão automática 20/11 |
| E22 | **Fila**: tarefas `repasse` (`lock=chat:`, `queueing_lock=repasse:{atd}`, reagenda com o mesmo `desde`), `reaper_ledger` e `publicar_espelho` (periódicas de 1 min). **`montagem_b16b.montar`** liga tudo sobre os `Servicos` a partir das portas; o `worker.montar_servicos` de produção NÃO a chama (sem adaptador real), e um teste prova que os serviços seguem falhando alto | — |

## Revisão independente de 20/11

`docs/REVISAO-B1.6b-2011.md`: 3 ALTO, 5 MÉDIO e 6 BAIXO; todos os ALTO e MÉDIO corrigidos com teste que reprova no código revisado, e os BAIXO
corrigidos ou registrados (9 e 13, parte). Mudanças de decisão: E10 (prazo exato), E2 (idade em [−30 s, 90 s] e episódio marcado sem consulta),
E13 (retry do turno não chama o modelo de novo; retry do `iniciar` completa pelo ledger), E17 (prazo por ferramenta do catálogo), rede do
`repassando` sem job.

## Ficou de fora (e por quê)

1. **Adaptadores reais** de `Canal`, `ia-repasse`, espelho e batimento: DEC-PIA-002 (delegação) e a S5 (hospedagem). O laço de 15 s que
   chama `LeitorBatimento.atualizar` também entra com o adaptador (B1.7/B6.3).
2. **`criar_confirmacao`/`aceitar_confirmacao` e `valores_hash × args_hash` da T7** (pendência 8 da B1.6a, G-0066): a T7 só roda pelo
   gateway da B5.4; o ledger já barra T7 sem confirmação ligada ao dado. Fica com a B5.4.
3. **RG-075** (`texto_livre.casos.json` com sha anotado): depende do dicionário de `contexto_codigos` (G-0378) e do texto aprovado;
   não nasce aqui. **Para o dono:** confirmar que vai para a B6.2.
4. **Obrigações herdadas da B1.4 que dependem do agente real** (`como_decisao_de_falha`, `[dado:<campo>]` na E5, `desvio_liberado`, `nomes`
   em `Deps`, texto de `mascarar` ao extrator, apelidos por `ResultadoTurno.referencias`, `montar_contexto(tokens_das_ferramentas=…)`,
   resumo barato): entram com o `Motor` real na B1.7. Handler de `retomada_perdida`/`agendamento_perdido`: B5.7c.
5. **Alerta crítico repetido a cada 10 min do `repasse_travado`** e do espelho: B6.6 (alertas). Aqui sai uma vez por evento.
6. **Testes ponta a ponta com o worker real** (D14b ii, SIGKILL no meio da T7): B1.7.

## Decisões que dependem do dono

- **DEC-PIA-002**: o adaptador real de delegação/repasse (sem ele, nada desta etapa liga em produção).
- **DN-28 / R-c2**: a regra da vigia para `repasse_travado`; padrão aplicado: marcar, alertar `humano` e listar (E11).
- **D3 e D20 da B1.6a** seguem com o padrão documentado (limite zero com gasto > 0 repassa; `assumir` sem resposta não dá posse real).
- O prazo de D-14 recomeçar num reenfileiramento manual (`scripts/reenfileirar_repasse.py`, ainda não existe) é de propósito: quem
  reenfileira é a TI, depois do alerta.
