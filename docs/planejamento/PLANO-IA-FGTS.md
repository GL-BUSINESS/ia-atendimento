# Plano: IA de negociação do FGTS («Fabio Junior»)

11/11/2026. Plano de construção. Parte de três estudos — `ESTUDO-FGTS-PONTA-A-PONTA.md`, `ESTUDO-NEGOCIACAO-TABELAS.md` e `ESTUDO-CORPUS-FGTS-APROVADOS.md` — e das decisões do dono de 10 e 11/11, que prevalecem onde divergirem. Nada aqui autoriza escrita em produção: cada passo de produção pede o seu «sim».

## 1. Em uma frase

A IA ocupa só o 3º degrau do chatbot. Quando o cliente recusa a NS e a CAMPANHA, ela oferece a GOLD («Conseguimos um valor maior!»), responde dúvidas e devolve o cliente ao fluxo de formalização do próprio chatbot. Se ele recusar de novo, repassa ao consultor. Não digita contrato, não escolhe tabela, não negocia além da GOLD.

## 2. O que as decisões novas simplificaram

| Estudo de 10/11 propunha | Agora (decisão do dono) | Efeito na construção |
|---|---|---|
| Motor de tabelas NF-02 a NF-07: candidatas, ganho mínimo, custo por real dado, piso de comissão | Escada fixa NS → CAMPANHA → GOLD; GOLD é o teto, fixo no código | Sem motor. O código só pede `/degrau/3` |
| IA formaliza: coleta Pix, digita na API-17, confere (E5–E8, T6–T9) | A IA devolve ao fluxo de formalização que o chatbot já tem, como o F3 faz com a CAMPANHA | Sem digitação pela IA. Some o risco de contratação em dobro (G-0087) no FGTS |
| Gatilhos FG-01 (pré-aprovado sem contrato) e FG-03 (não assinou) | Entrada logo depois de NEGOU CAMPANHA; FG-03 (cobrar assinatura) é fase 2 (Q-CF-04) | Um gatilho só no piloto |
| Destino de repasse FGTS inexistente (AN-16, bloqueava) | «FGTS - Consultores» (padrão da config) | Desbloqueado |
| Corpus de não aprovados para dimensionar | Dispensado; volume pelo F3: ~400 por dia | Tamanho conhecido |
| Disjuntor de `cef_indisponivel` (AN-29) | Queda da Caixa = desligar a IA à mão; vigia avisa | Sem disjuntor no código; a IA só checa `ligada` |

## 3. Desenho

### 3.1 Componentes

Reaproveita o orquestrador da IA CLT (`ia-atendimento`) com um gatilho novo, como os estudos já previam (AN-04). Não sobe serviço novo.

| Peça | Papel no FGTS | Existe? |
|---|---|---|
| Fluxo n8n do diálogo NEGOU CAMPANHA | Chama o braço n8n da IA em vez de mandar o áudio | Existe; muda um nó |
| Braço n8n → orquestrador | `POST` com `gatilho=fgts_pos_campanha`, `produto=FGTS`, `chat_id`, `transaction_id` | Contrato 04 precisa da emenda |
| `gl-gateway` | Tira PII da mensagem do cliente | Existe (rotas da IA ainda não) |
| Orquestrador (VPS) | Máquina de estados F0–F5 abaixo; o modelo só classifica e redige frases curtas | Existe em parte (CLT) |
| Ferramenta `oferta_gold` | `GET :8104 /novosaque/fgts/contrato/{tx}/degrau/3` | Rota no PR novosaque-fgts#11 |
| Ferramenta `voltar_ao_chatbot` | Grava `valor_liberado` e `ns_simulacao_negociada` (GOLD) no ChatGuru e dispara o diálogo de formalização, os mesmos 3 passos do F3 | Nova, copia o F3 |
| Ferramenta `repassar` | Leva o chat a «FGTS - Consultores» com nota curta | Existe no CLT (T12), muda o destino |
| Painel «Negociação FGTS» | Liga/desliga, sombra/real, holdout, teto por dia | PR painel-dev#53 |

### 3.2 Estados da conversa

| Estado | O que acontece | Quem decide |
|---|---|---|
| F0 pré-abertura | Checa: `ligada`, modo, sorteio do holdout (hash da chave do episódio), teto do dia, `/degrau/3` com `motivo=ok`, nenhuma formalização aberta para o CPF. Falhou → o chatbot segue como hoje (áudio) e nada é dito | Código |
| F1 abertura | Texto fixo com o valor da GOLD (`liberado_brl` da rota, nunca do modelo): «Conseguimos um valor maior!» | Código |
| F2 conversa | O modelo classifica a resposta: aceita · recusa · dúvida (qual) · quer humano · sem sentido. Dúvida conhecida → texto fixo do catálogo; o modelo só costura frases curtas | Modelo classifica, código responde |
| F3 aceite | Confirmação explícita do cliente → `voltar_ao_chatbot`. A IA sai do chat | Código |
| F4 lembretes | Sem resposta: até 3 lembretes, só dentro da janela de 24 h do WhatsApp; fora dela, só template aprovado | Código |
| F5 encerramento | Recusa, «quer humano», 3 lembretes sem resposta ou erro → `repassar` com nota. Fora do expediente o repasse fica agendado para as 8h e o cliente é avisado (Q-CF-06) | Código |

### 3.3 Regras que não mudam do CLT

- O modelo nunca vê CPF, telefone, nome, tabela, comissão nem valor; o valor entra no texto pelo código.
- Só DeepSeek V4.1 Flash pela Fireworks nos EUA; nada da Anthropic no produto.
- Uma oferta só: a IA nunca oferece outra tabela, nunca reapresenta a CAMPANHA, nunca diz «última chance».
- Sem frase falsa: «com meu supervisor consegui» só se a GOLD for de fato maior que a CAMPANHA (sempre é: 1,29 contra 1,10, em múltiplos da NS).
- Proibido falar em parcela, desconto em folha, seguro, promessa sobre saldo ou prazo fixo (lista T15 do estudo).

### 3.4 Duas vozes

Quando a IA entra, o 3º degrau do chatbot (áudio) sai para aquele cliente, e o robô operacional só age depois do contrato. Falta provar que nenhum outro fluxo (lembretes «Não Respondeu») fala no mesmo chat enquanto a IA está ativa; isso é critério de aceite da fase P3.

### 3.5 Ferramentas

Regra geral: **o modelo não chama nenhuma ferramenta.** No FGTS ele só devolve a classificação da mensagem (§3.2, F2). Toda ferramenta é chamada pelo código, no estado certo, pelo gateway de ferramentas que o CLT já tem (`ferramentas/gateway.py`): timeout, idempotência, pré-condições rodadas por código antes do efeito, registro de cada chamada. As FGTS entram como especificações novas do catálogo versionado (`ferramentas/catalogo.py`), com número novo em `catalogo_versoes.json`. O catálogo ordena por `int(nome[1:])`, então os nomes seguem `T<n>` a partir de T17.

**Novas (FGTS)**

| Id | Função | Classe | Quando | Entrada → saída | Se falhar | Base |
|---|---|---|---|---|---|---|
| T17 | `oferta_gold` | leitura | F0 (decidir se abre) e de novo logo antes da T19 | `transaction_id` do episódio (nunca do modelo) → `tem_oferta`, `motivo`, `liberado`, `liberado_brl`, `simulation_id`, `table_id` | `motivo ≠ ok` ou timeout no F0: a IA não abre e o chatbot segue com o áudio. Antes da T19: valor ou `simulation_id` diferente do da abertura → repasse com nota | Rota `GET :8104 …/degrau/3`, PR novosaque-fgts#11 |
| T18 | `formalizacao_aberta` | leitura (usa CPF só no código) | F0 e antes da T19 | chave do episódio → `aberta: sim/não`, `desde` | Sem resposta: trata como «aberta» e não segue (falha fechada) | `novosaque.simulacoes` (`acao` contrato/formalizacao) por CPF, leitura |
| T19 | `voltar_ao_chatbot` | efeito (não digita contrato, mas dispara a formalização) | F3, só depois da confirmação explícita | `transaction_id`, `simulation_id` e `liberado` lidos da T17 → `ok` / `indeterminado` | `indeterminado` nunca repete às cegas: lê o estado do chat e, sem certeza, repassa com nota | Os mesmos 3 passos do F3 com a CAMPANHA: grava `valor_liberado` e `ns_simulacao_negociada` (GOLD) no ChatGuru e dispara o diálogo de formalização |
| T20 | `config_negociacao` | ação interna (só código) | F0 | nada → `ligada`, `modo`, `holdout_pct`, `teto_ia_dia`, contagem do dia, `destino_falha` | Sem leitura → trata como desligada | Tabela de config do PR painel-dev#53 |
| T21 | `marcar_ia_no_chat` (só se a prova da §3.4 pedir) | efeito reversível | Ao abrir (F1) e ao sair (F3/F5) | `chat_id`, `ligar/desligar` → `ok` | Falhou ao ligar → não abre. Falhou ao desligar → repasse com nota para o humano conferir | Campo no ChatGuru que os lembretes «Não Respondeu» leem para não falar junto |

Pré-condições da T19, todas por código e na ordem: `ligada` e `modo=real`; atendimento ainda com a IA (humano não assumiu); sem opt-out; confirmação de aceite registrada; T18 `aberta=não`; T17 de novo com `motivo=ok` e o mesmo `simulation_id` e `liberado` da abertura; nenhuma T19 anterior no episódio (idempotência por chave do episódio).

**Reaproveitadas do CLT**

| Id | Função | Uso no FGTS | O que muda |
|---|---|---|---|
| T11 | `Canal` (enviar mensagem) | Abertura F1, respostas do catálogo F2, lembretes F4. Dentro da janela de 24 h, texto livre; fora, só template aprovado | Nada; textos TX-F novos |
| T12 | `repassar` | F5: leva o chat a «FGTS - Consultores» com nota curta (motivo, valor oferecido, o que o cliente disse em resumo sem PII); fora do expediente agenda para as 8h | Destino vem da T20 (`destino_falha`) |
| T14 | `registrar_opt_out` | Cliente pede para parar: registra e encerra sem repasse | Nada |

**Fora do piloto**

| Id | Função | Quando entra |
|---|---|---|
| T16 | Serviço de mídia (transcrever áudio do cliente) | Fase 2 (Q-PF-03). No piloto, áudio do cliente vira repasse |
| — | Cobrar assinatura pendente (FG-03) | Fase 2 |
| T1–T10 do CLT (identificar, simular, digitar FACTA, conferir, link) | Não se aplicam: a IA do FGTS não simula outra tabela nem digita | Nunca, neste produto |

O que o modelo devolve no F2 (saída estruturada, não ferramenta): `intencao` ∈ {aceita, recusa, duvida, quer_humano, opt_out, sem_sentido} e, se `duvida`, o `duvida_id` do catálogo. Duas saídas inválidas seguidas → repasse (regra P7 do CLT).

## 4. Fases

| Fase | Quando | O que entra | Produção? |
|---|---|---|---|
| P1 Preparar | Até 19/11, custo baixo, sem disputar a S3 com o CLT | Revisão Codex dos PRs #11 e #53 (a partir de 15/11); textos TX-F em rascunho para o dono; catálogo de dúvidas tirado do corpus; emenda do contrato 04 (gatilho, chave do episódio) | Não |
| P2 Escada no ar | 01 a 05/12 | DDL na S2 + deploy do #11 + painel #53; F3 fase A (sombra, 3–5 dias) e fase B (troca) | Sim, 3 «sim» |
| P3 Construir a IA | Depois do relatório do piloto CLT (01/12) | Gatilho `fgts_pos_campanha`, estados F0–F5, ferramentas T17–T20 (e T21 se a prova das duas vozes pedir), T11/T12/T14 ajustadas (§3.5); testes; ensaio com o dublê | Não |
| P4 Sombra | ~1 semana | Com `modo=sombra`: a IA recebe o gatilho, decide e registra o que diria, sem enviar; o chatbot segue com o áudio | Leitura só |
| P5 Piloto | ~1 semana | `modo=real`, holdout 15%, teto inicial de 50 por dia, 24/7 com repasse agendado para as 8h (Q-CF-06) | Sim, «sim» do dono |
| P6 Rampa e fase 2 | Depois | Sobe o teto até cobrir os ~400 por dia; fase 2: cobrar assinatura (FG-03), transcrever áudio | Sim |

Estimativa da P3, sem medição ainda: 6 a 8 dias-agente, porque o núcleo vem do CLT e a IA não formaliza.

## 5. Como saber se funciona

- **Métrica principal:** contrato pago em 7 dias, braço IA contra braço holdout (15%, sorteado e gravado no F0).
- **De apoio:** aceite da GOLD; repasses e motivo; tempo até a 1ª resposta; mensagens com erro de envio; custo do modelo por atendimento.
- **Linha de base:** hoje, dos 74 NEGOU CAMPANHA do corpus, 18 negaram três vezes e só 7 formalizaram em 7 dias.
- **Parada:** qualquer frase fora do catálogo de proibidas, valor diferente do da rota, ou duas vozes no mesmo chat → desligar a IA no painel.

## 6. Riscos

| Risco | Mitigação |
|---|---|
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
