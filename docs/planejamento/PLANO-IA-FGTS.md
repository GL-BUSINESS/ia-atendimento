# Plano: IA de negociação do FGTS («Fabio Junior»)

11/11/2026, revisto à tarde. Plano de construção. Parte de três estudos — `ESTUDO-FGTS-PONTA-A-PONTA.md`, `ESTUDO-NEGOCIACAO-TABELAS.md` e `ESTUDO-CORPUS-FGTS-APROVADOS.md` — e das decisões do dono de 10 e 11/11, que prevalecem onde divergirem. Nada aqui autoriza escrita em produção: cada passo de produção pede o seu «sim».

## 1. Em uma frase

A IA entra quando o chatbot não consegue fechar e trabalha **na tabela que já está em negociação no chat**. Se o cliente só travou por não entender o processo, ela tira a dúvida e executa o diálogo de formalização que já finaliza tudo, sem mudar o valor. Só se o cliente recusar pelo valor ela oferece o próximo degrau da escada (NS → CAMPANHA → GOLD), sem pular e nunca acima da GOLD. Se ele recusar de novo, repassa ao consultor. Não digita contrato e não escolhe tabela fora da escada.

Mudança do dono em 11/11 à tarde: **a GOLD não é oferecida sempre.** Um lead pode chegar à IA com a NS em negociação porque o cliente é leigo e só não conseguiu formalizar. Oferecer a GOLD nesse caso dá valor a mais sem necessidade e perde a negociação.

## 2. O que as decisões novas simplificaram

| Estudo de 10/11 propunha | Agora (decisão do dono) | Efeito na construção |
|---|---|---|
| Motor de tabelas NF-02 a NF-07: candidatas, ganho mínimo, custo por real dado, piso de comissão | Escada fixa NS → CAMPANHA → GOLD; GOLD é o teto, fixo no código; a IA sobe no máximo um degrau, e só com objeção de valor | Sem motor. O código lê o degrau atual e, se for o caso, pede `/degrau/{atual+1}` |
| Sempre oferecer a GOLD (versão de 11/11 de manhã) | Depende do chat: problema simples → formaliza na tabela atual; objeção de valor → próximo degrau | Duas ações de saída (§3.5): formalizar no degrau atual ou no degrau novo |
| IA formaliza: coleta Pix, digita na API-17, confere (E5–E8, T6–T9) | A IA executa o diálogo de formalização que o chatbot já tem, como o F3 faz com a CAMPANHA | Sem digitação pela IA. Some o risco de contratação em dobro (G-0087) no FGTS |
| Gatilhos FG-01 (pré-aprovado sem contrato) e FG-03 (não assinou) | Entrada quando o chatbot falha, com o degrau atual no pedido; FG-03 (cobrar assinatura) é fase 2 (Q-CF-04) | Um gatilho com o degrau como dado; os pontos de falha do fluxo são mapeados na P1 |
| Destino de repasse FGTS inexistente (AN-16, bloqueava) | «FGTS - Consultores» (padrão da config) | Desbloqueado |
| Corpus de não aprovados para dimensionar | Dispensado; volume pelo F3: ~400 por dia | Tamanho conhecido |
| Disjuntor de `cef_indisponivel` (AN-29) | Queda da Caixa = desligar a IA à mão; vigia avisa | Sem disjuntor no código; a IA só checa `ligada` |

## 3. Desenho

### 3.1 Componentes

Reaproveita o orquestrador da IA CLT (`ia-atendimento`) com um gatilho novo, como os estudos já previam (AN-04). Não sobe serviço novo.

| Peça | Papel no FGTS | Existe? |
|---|---|---|
| Fluxos n8n do FGTS (pontos onde o chatbot desiste) | Chamam o braço n8n da IA em vez de seguir para o áudio ou para o abandono. NEGOU CAMPANHA é um deles; os outros saem do mapa da P1 | Existem; muda um nó por ponto |
| Braço n8n → orquestrador | `POST` com `gatilho=fgts_falha_chatbot`, `produto=FGTS`, `chat_id`, `transaction_id`, `degrau_atual` (1, 2 ou 3), `simulation_id` gravado no chat e `ponto` (de onde veio) | Contrato 04 precisa da emenda |
| `gl-gateway` | Tira PII da mensagem do cliente | Existe (rotas da IA ainda não) |
| Orquestrador (VPS) | Máquina de estados F0–F5 abaixo; o modelo só classifica e redige frases curtas | Existe em parte (CLT) |
| Ferramenta `oferta_degrau` (T17) | `GET :8104 /novosaque/fgts/contrato/{tx}/degrau/{n}`, para o degrau atual e para o próximo | Rota no PR novosaque-fgts#11 |
| Ferramenta `formalizar_degrau_atual` (T19) | Só executa o diálogo de formalização do ChatGuru, que já finaliza tudo; não mexe no valor | Nova, chama o diálogo que já existe |
| Ferramenta `formalizar_degrau_novo` (T20) | Grava `valor_liberado` e `ns_simulacao_negociada` do degrau oferecido no ChatGuru e executa o mesmo diálogo, os 3 passos do F3 | Nova, copia o F3 |
| Ferramenta `repassar` (T12) | Leva o chat a «FGTS - Consultores» com nota curta | Existe no CLT, muda o destino |
| Painel «Negociação FGTS» | Liga/desliga, sombra/real, holdout, teto por dia | PR painel-dev#53 |

### 3.2 Estados da conversa

| Estado | O que acontece | Quem decide |
|---|---|---|
| F0 pré-abertura | Checa: `ligada`, modo, sorteio do holdout (hash da chave do episódio), teto do dia, `/degrau/{degrau_atual}` com `motivo=ok` e o mesmo `simulation_id` do chat, nenhuma formalização aberta para o CPF. Falhou → o chatbot segue como hoje e nada é dito | Código |
| F1 abertura | Texto fixo conforme o `ponto` de entrada: retomar a conversa na proposta atual (valor da rota, nunca do modelo) e perguntar o que travou. Não oferece valor novo na abertura | Código |
| F2 conversa | O modelo classifica a resposta: aceita · dúvida (qual) · dificuldade no processo · objeção de valor · recusa sem motivo · quer humano · parar · sem sentido. Dúvida ou dificuldade conhecida → texto fixo do catálogo; o modelo só costura frases curtas | Modelo classifica, código responde |
| F2a subir degrau | Só com **objeção de valor explícita** e `degrau_atual < 3`: o código pede `/degrau/{atual+1}` e, com `motivo=ok`, manda o texto fixo «Conseguimos um valor maior!» com o valor novo. Uma subida por vez; a nova proposta passa a ser a atual. Na GOLD não sobe mais | Código |
| F3 aceite | Confirmação explícita do cliente → `formalizar_degrau_atual` se o valor não mudou, `formalizar_degrau_novo` se a IA subiu de degrau. A IA sai do chat | Código |
| F4 lembretes | Sem resposta: até 3 lembretes, só dentro da janela de 24 h do WhatsApp; fora dela, só template aprovado | Código |
| F5 encerramento | Recusa na GOLD, recusa sem motivo, «quer humano», 3 lembretes sem resposta ou erro → `repassar` com nota. Fora do expediente o repasse fica agendado para as 8h e o cliente é avisado (Q-CF-06). Pedido para parar → `registrar_opt_out` sem repasse | Código |

Quando tem dúvida entre «dificuldade no processo» e «objeção de valor», a regra é ficar na tabela atual: tirar a dúvida primeiro e só subir se o cliente disser de novo que o valor não serve.

### 3.3 Regras que não mudam do CLT

- O modelo nunca vê CPF, telefone, nome, tabela, comissão nem valor; o valor entra no texto pelo código.
- Só DeepSeek V4.1 Flash pela Fireworks nos EUA; nada da Anthropic no produto.
- Escada só para cima, um degrau por vez, só com objeção de valor, nunca acima da GOLD. Nunca oferece tabela fora da escada, nunca volta a um degrau já recusado, nunca diz «última chance».
- Sem frase falsa: «Conseguimos um valor maior!» e «com meu supervisor consegui» só quando a IA de fato subiu de degrau (o valor novo vem da rota e é maior que o atual).
- Proibido falar em parcela, desconto em folha, seguro, promessa sobre saldo ou prazo fixo (lista T15 do estudo).

### 3.4 Duas vozes

Quando a IA entra, o passo seguinte do chatbot (áudio do 3º degrau ou lembrete) sai para aquele cliente, e o robô operacional só age depois do contrato. Falta provar que nenhum outro fluxo (lembretes «Não Respondeu») fala no mesmo chat enquanto a IA está ativa; isso é critério de aceite da fase P3.

### 3.5 Ferramentas

Regra geral: **o modelo não chama nenhuma ferramenta.** No FGTS ele só devolve a classificação da mensagem (F2). Toda ferramenta é chamada pelo código, no estado certo, pelo gateway de ferramentas que o CLT já tem (`ferramentas/gateway.py`): timeout, idempotência, pré-condições rodadas por código antes do efeito, registro de cada chamada. As FGTS entram como especificações novas do catálogo versionado (`ferramentas/catalogo.py`), com número novo em `catalogo_versoes.json`. O catálogo ordena por `int(nome[1:])`, então os nomes seguem `T<n>` a partir de T17.

**Novas (FGTS)**

| Id | Função | Classe | Quando | Entrada → saída | Se falhar | Base |
|---|---|---|---|---|---|---|
| T17 | `oferta_degrau` | leitura | F0 (degrau atual), F2a (próximo degrau) e de novo logo antes da T19/T20 | `transaction_id` do episódio e `n` decidido pelo código (nunca pelo modelo) → `tem_oferta`, `motivo`, `liberado`, `liberado_brl`, `simulation_id`, `table_id`, `quem` | F0: `motivo ≠ ok`, timeout ou `simulation_id` diferente do chat → a IA não abre. F2a: sem oferta no próximo degrau → fica na proposta atual. Antes da T19/T20: valor ou `simulation_id` mudou → repasse com nota | Rota `GET :8104 …/degrau/{n}`, PR novosaque-fgts#11 |
| T18 | `formalizacao_aberta` | leitura (usa CPF só no código) | F0 e antes da T19/T20 | chave do episódio → `aberta: sim/não`, `desde` | Sem resposta: trata como «aberta» e não segue (falha fechada) | `novosaque.simulacoes` (`acao` contrato/formalizacao) por CPF, leitura |
| T19 | `formalizar_degrau_atual` | efeito (dispara a formalização; não muda valor) | F3, quando a IA não subiu de degrau | `chat_id`, `transaction_id`, `simulation_id` atual → `ok` / `indeterminado` | `indeterminado` nunca repete às cegas: lê o estado do chat e, sem certeza, repassa com nota | Só o passo «executar o diálogo de formalização» do F3; o valor e a simulação já estão gravados no chat |
| T20 | `formalizar_degrau_novo` | efeito (troca o valor e dispara a formalização) | F3, quando a IA subiu de degrau no F2a | `chat_id`, `transaction_id`, `simulation_id` e `liberado` do degrau novo lidos da T17 → `ok` / `indeterminado` | Igual à T19 | Os 3 passos do F3: grava `valor_liberado` e `ns_simulacao_negociada` no ChatGuru e executa o diálogo de formalização |
| T21 | `config_negociacao` | ação interna (só código) | F0 | nada → `ligada`, `modo`, `holdout_pct`, `teto_ia_dia`, contagem do dia, `destino_falha` | Sem leitura → trata como desligada | Tabela de config do PR painel-dev#53 |
| T22 | `marcar_ia_no_chat` (só se a prova da §3.4 pedir) | efeito reversível | Ao abrir (F1) e ao sair (F3/F5) | `chat_id`, `ligar/desligar` → `ok` | Falhou ao ligar → não abre. Falhou ao desligar → repasse com nota para o humano conferir | Campo no ChatGuru que os lembretes «Não Respondeu» leem para não falar junto |

Pré-condições comuns da T19 e da T20, todas por código e na ordem: `ligada` e `modo=real`; atendimento ainda com a IA (humano não assumiu); sem opt-out; confirmação de aceite registrada; T18 `aberta=não`; T17 de novo com `motivo=ok` e o mesmo `simulation_id` e `liberado` da proposta aceita; nenhuma T19/T20 anterior no episódio (idempotência por chave do episódio).

Só da T20: objeção de valor registrada no turno que levou ao F2a; degrau novo = degrau de entrada + subidas feitas, um por vez; degrau novo ≤ 3 (GOLD).

**Reaproveitadas do CLT**

| Id | Função | Uso no FGTS | O que muda |
|---|---|---|---|
| T11 | `Canal` (enviar mensagem) | Abertura F1, respostas do catálogo F2, oferta F2a, lembretes F4. Dentro da janela de 24 h, texto livre; fora, só template aprovado | Nada; textos TX-F novos |
| T12 | `repassar` | F5: leva o chat a «FGTS - Consultores» com nota curta (degrau atual, motivo, o que o cliente disse em resumo sem PII); fora do expediente agenda para as 8h | Destino vem da T21 (`destino_falha`) |
| T14 | `registrar_opt_out` | Cliente pede para parar: registra e encerra sem repasse | Nada |

**Fora do piloto**

| Id | Função | Quando entra |
|---|---|---|
| T16 | Serviço de mídia (transcrever áudio do cliente) | Fase 2 (Q-PF-03). No piloto, áudio do cliente vira repasse |
| — | Cobrar assinatura pendente (FG-03) | Fase 2 |
| T1–T10 do CLT (identificar, simular, digitar FACTA, conferir, link) | Não se aplicam: a IA do FGTS não simula fora da escada nem digita | Nunca, neste produto |

O que o modelo devolve no F2 (saída estruturada, não ferramenta): `intencao` ∈ {aceita, duvida, dificuldade_processo, objecao_valor, recusa_sem_motivo, quer_humano, opt_out, sem_sentido} e, se `duvida` ou `dificuldade_processo`, o `duvida_id` do catálogo. Duas saídas inválidas seguidas → repasse (regra P7 do CLT).

## 4. Fases

| Fase | Quando | O que entra | Produção? |
|---|---|---|---|
| P1 Preparar | Até 19/11, custo baixo, sem disputar a S3 com o CLT | Revisão Codex dos PRs #11 e #53 (a partir de 15/11); **mapa dos pontos onde o chatbot desiste**, com volume por ponto e degrau em que o cliente está (leitura dos fluxos, local); textos TX-F em rascunho para o dono (uma abertura por ponto de entrada); catálogo de dúvidas e de dificuldades do processo tirado do corpus; emenda do contrato 04 (gatilho, `degrau_atual`, `ponto`, chave do episódio) | Não |
| P2 Escada no ar | 01 a 05/12 | DDL na S2 + deploy do #11 + painel #53; F3 fase A (sombra, 3–5 dias) e fase B (troca) | Sim, 3 «sim» |
| P3 Construir a IA | Depois do relatório do piloto CLT (01/12) | Gatilho `fgts_falha_chatbot`, estados F0–F5 com F2a, ferramentas T17–T21 (e T22 se a prova das duas vozes pedir), T11/T12/T14 ajustadas (§3.5); testes, incluindo «leigo na NS não recebe a GOLD»; ensaio com o dublê | Não |
| P4 Sombra | ~1 semana | Com `modo=sombra`: a IA recebe o gatilho, decide e registra o que diria e se subiria de degrau, sem enviar; o chatbot segue como hoje | Leitura só |
| P5 Piloto | ~1 semana | `modo=real`, holdout 15%, teto inicial de 50 por dia, 24/7 com repasse agendado para as 8h (Q-CF-06) | Sim, «sim» do dono |
| P6 Rampa e fase 2 | Depois | Sobe o teto até cobrir os ~400 por dia; fase 2: cobrar assinatura (FG-03), transcrever áudio | Sim |

Estimativa da P3, sem medição ainda: 7 a 9 dias-agente (era 6 a 8; o F2a, o degrau como dado e a segunda ação de saída somam ~1 dia), porque o núcleo vem do CLT e a IA não digita.

## 5. Como saber se funciona

- **Métrica principal:** contrato pago em 7 dias, braço IA contra braço holdout (15%, sorteado e gravado no F0).
- **Margem:** parte dos fechamentos que saiu no mesmo degrau em que o cliente chegou (sem dar valor a mais) e quantos degraus a IA subiu por contrato. Subir quando não precisava é o erro caro desta IA.
- **De apoio:** aceite por degrau; repasses e motivo; tempo até a 1ª resposta; mensagens com erro de envio; custo do modelo por atendimento.
- **Linha de base:** hoje, dos 74 NEGOU CAMPANHA do corpus, 18 negaram três vezes e só 7 formalizaram em 7 dias. A linha de base dos outros pontos de entrada sai do mapa da P1.
- **Parada:** qualquer frase fora do catálogo de proibidas, valor diferente do da rota, subida de degrau sem objeção de valor registrada, ou duas vozes no mesmo chat → desligar a IA no painel.

## 6. Riscos

| Risco | Mitigação |
|---|---|
| A IA sobe de degrau sem precisar (classifica dificuldade como objeção de valor) | Subida só com objeção de valor explícita; na dúvida fica na tabela atual; teste dedicado na P3; na sombra (P4), conferir uma amostra das subidas antes do piloto |
| Degrau atual errado no pedido do n8n | F0 confere o `simulation_id` do chat contra a rota; diferente → a IA não abre |
| Caixa fora do ar | Vigia avisa no sino; desligar a IA à mão no painel |
| Comissão da GOLD desconhecida | Regra fixa da GOLD como teto; confirmar `insurance_amount` com a Novo Saque |
| Janela de 24 h do WhatsApp (51% de falha fora dela) | Texto livre só dentro da janela; fora, só template |
| Infra da IA CLT ainda não existe (VPS, rotas do gateway, chave Fireworks) | A P3 só começa depois da infra do CLT; o FGTS não pede infra nova |
| 28% dos NEGOU CAMPANHA chegam fora do expediente | IA responde 24/7 (Q-CF-06) e agenda o repasse para as 8h |

## 7. Perguntas ao dono (com padrão)

| Id | Pergunta | Padrão se não houver resposta |
|---|---|---|
| Q-PF-01 | O que o áudio do 3º degrau diz hoje (Q-CF-03)? | Escrever a abertura da IA do zero e mandar para aprovação |
| Q-PF-02 | Teto inicial do piloto por dia | 50 |
| Q-PF-03 | Transcrever áudio do cliente (Q-CF-08) já no piloto? | Fase 2; no piloto, áudio vira repasse |
| Q-PF-04 | Quem aprova os textos TX-F | O dono, em um lote, antes da P4 |
| Q-PF-05 | Com o cliente na NS reclamando do valor, a IA pode oferecer a CAMPANHA (um degrau) ou só o chatbot oferece a CAMPANHA? | A IA pode, um degrau por vez |
| Q-PF-06 | Em quais pontos o chatbot «desiste» e a IA deve entrar no piloto? | Os pontos do mapa da P1 com mais volume, levados ao dono antes da P3; NEGOU CAMPANHA entra |
