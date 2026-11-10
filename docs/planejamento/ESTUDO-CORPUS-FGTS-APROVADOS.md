# ESTUDO-CORPUS-FGTS-APROVADOS

Estudo único sobre 1.234 conversas do ChatGuru de clientes FGTS **aprovados**. Junta quatro relatórios de analistas: jornada, Fabio × consultor, o que o cliente diz e operação. Escrito para o dono e para o dev sênior que vai construir a IA Fabio Junior.

Só há números agregados. Nenhum hash de chat e nenhum trecho de conversa individual. Toda frase citada aparece em 20 chats ou mais.

---

## §0 Resumo em 10 linhas

1. A sessão que converte é curta e quase toda do robô. Do 1º contato do cliente ao form, a mediana é **49 min**. Humano antes do form: **2,5% a 9,8%** dos chats.
2. O gargalo é a consulta de saldo. Do CPF à oferta NS: p50 **27 min**, p90 **86 min**.
3. **72,9%** dos aprovados já tinham conversado em sessão anterior, e **67% a 69%** já tinham consultado antes. A mediana entre a 1ª consulta e o form final é de 131 dias. A falha foi do banco (reprovado 34%, saldo insuficiente 24%), não da conversa.
4. Na 1ª oferta NS, **82%** apertam «Sim» e **9%** apertam «Não». A objeção de valor chega como botão, não como frase.
5. Hoje o chatbot já tem **3 degraus**: NS → CAMPANHA → áudio com «APROVEITE!» (Sim/Não). Ele recupera **53 de 105** recusas da NS (50%), quase sempre em menos de 1 h.
6. O grupo que a IA vai atacar é pequeno: **18 chats** negaram três vezes. Desses, 17 foram para um humano e só 7 formalizaram em 7 dias (mediana de 456 h).
7. O consultor aparece em **41%** dos ciclos aprovados, mas entra **depois** da aprovação em 96% dos casos. O que ele mais faz é cobrar assinatura do contrato (79% das conversas com consultor).
8. **54%** das mensagens humanas são macros repetidas. Já existe um «GOLD» feito pelo humano: «com meu gerente/supervisor conseguimos liberar o maior valor», em 22 a 38 chats, conforme a contagem.
9. À noite ninguém atende. Entre 18 h e 23 h, o humano demora p50 de **777 min**. Fora do expediente, o p90 da resposta humana é de cerca de **15 h**.
10. Mensagem livre enviada depois da janela de 24 h falha em **51%** dos casos (96% no botão). Isso causa **81%** dos erros de envio. A IA tem de respeitar a janela.

---

## §1 Base e método

**Corpus.** O arquivo `seguro/msgs.jsonl` tem 177.086 linhas e 1.234 chats:

| Origem | Linhas |
|---|---|
| cliente | 46.497 |
| empresa | 96.924 |
| notas | 33.665 |

- Período: 02/04/2022 a 10/11/2026.
- Em 1.194 dos 1.198 chats com «recebido form», o último form é de nov/2026.
- Os dias 09 e 10/11 concentram **30,2%** das mensagens de cliente e **86,8%** das primeiras notas de digitação. Isso indica um disparo em massa do `template_utilidade_16`.

**Anonimização.**
- O chat aparece só como hash de 12 caracteres hex.
- O texto vem em vocabulário fechado: só entram palavras vistas em 20 chats ou mais.
- Palavras raras, números, valores, nomes e dados pessoais viram placeholders (`<w>`, `<n>`, `<valor>`, `<nome>`, `<pii>`).
- Nenhum analista leu dado cru. O que exigiria dado cru está marcado como tal.

**Marcos usados.** Cada relatório usou o seu, e os números diferem um pouco por isso.

| Marco | Significado | Chats |
|---|---|---|
| nota «recebido form» | dados confirmados e link enviado (jornada) | 1.198 |
| nota «aprovado tabela ns» | oferta calculada (fabio, objeções) | 1.201 |
| nota «está em fase de digitação» | proxy de formalização (operação) | 1.201 |
| «Pagamento Confirmado» | melhor marcador de fim | 906 na sessão final; 923 no histórico |

**Corte do histórico.** Um chat é o histórico inteiro do telefone, às vezes de anos.
- Jornada: corta em sessões quando passam 24 h sem mensagem.
- Operação: corta em ciclos quando o cliente some por mais de 7 dias.
- Fabio × consultor: usa um ciclo que vai do último «PEDE CPF» até 7 dias depois da aprovação.

**Robô × humano.** Não existe campo de autor. A regra combina quatro sinais:
1. **Tipo.** Botão (`interactive_quick_reply`), lista e template são sempre robô.
2. **Assinatura.** O ChatGuru assina a mensagem do atendente com `* <nome> : *`. É o sinal mais forte de humano: 3.652 a 3.702 mensagens, em 633 a 642 chats, conforme o recorte. Das mensagens assinadas, só 0,6% a 2,2% caem dentro da janela de tempo do robô.
3. **Tempo.** Mensagem sem assinatura que sai até W s depois de um diálogo disparado, ou dentro de uma rajada, conta como robô.
4. **Texto repetido.** Texto idêntico em muitos chats é macro ou automação.

**Sensibilidade.** A janela W pesa pouco. O que pesa é o filtro de texto repetido.

| Medida | W = 20 s | W = 30 s | W = 60 s |
|---|---|---|---|
| Humano antes do form, regra solta (jornada) | 10,7% | 9,8% | 8,7% |
| Humano antes do form, regra estrita (jornada) | 2,5% | 2,5% | 2,5% |
| Ciclos com consultor (fabio) | 507 | 506 | 506 |
| p50 da resposta humana, H2 (operação) | 7,6 min | 9,4 min | 10,8 min |

- W = 20 s e W = 60 s dão a mesma classe em 1.228 de 1.234 conversas.
- Sem o filtro de texto repetido, o humano fica cerca de **5 vezes maior** do que é. Pela regra só de tempo, 74,4% do «humano» é texto idêntico em 50 chats ou mais.
- Este estudo usa **W = 30 s com filtro de texto repetido** e a assinatura como verdade.

---

## §2 A jornada que aprovou

**Ordem real das etapas (fluxo v3, set/2026 em diante).** Tempos em mediana, relativos ao form.

| Etapa | Chats (de 1.198) | p50 |
|---|---|---|
| Mês de aniversário (só quem entra pelo tráfego) | 477 | −40 min |
| 1.1.3 Solicita Autorização | 1.184 | −47 min |
| Cliente «Autorizei» | 1.193 | −40 min |
| 1.1.2 PEDE CPF → INFORMOU CPF (vai para consulta) | 1.179 | −38 min |
| Oferta NS «VALOR NA CONTA HOJE!» (Sim / Não / Estou com Dúvida) | 1.197 | −3 min |
| «Sim» → chave PIX → «Confirmar Dados» | 1.197 | −62 s a −4 s |
| Nota «recebido form» | 1.198 | 0 |
| «Pagamento Confirmado» | 906 | +12 min |

A autorização vem antes do CPF. A chave PIX vem antes de «Dados Corretos».

**Tempos entre etapas.**

| Trecho | p50 | p90 |
|---|---|---|
| Solicita Autorização → Autorizei | 3 min | 12 min |
| **CPF enviado → oferta NS** | **27 min** | **86 min** |
| Oferta NS → «Sim» | 72 s | 24 min |
| «Sim» → form | 62 s | 4 min |
| Form → Pagamento Confirmado | 12 min | 2,8 h |

- Durante a espera da consulta, o «timer de segurança» de 15 min dispara em 749 chats. Ele manda «o sistema do FGTS está apresentando uma leve demora…» (891 chats).
- A consulta é disparada 2 vezes ou mais em 16,8% dos chats. Há reprocessamento do CPF em 9,8%.

**Tempo total. Duas medidas, as duas valem.**
- Da 1ª mensagem do cliente na sessão final até o form: p50 de **49 min**. A sessão é cortada após 24 h de silêncio.
- Do início do último ciclo até a digitação: p50 de **78 min**, p90 de 5,2 dias. O ciclo é cortado após 7 dias de silêncio.
- Pelo corte de ciclo: 62,5% formalizam em até 2 h, e 30,1% levam de 1 a 7 dias. Quem passa de 2 h tende a levar dias.

**Quem volta.**
- Tinham sessões anteriores (corte de 24 h): 72,9%.
- Tinham ciclos anteriores (corte de 7 dias): 68,5%.
- Já tinham informado CPF ou consultado antes: 67%. A mediana até o form final é de 131 dias.
- Motivos das falhas anteriores:

| Motivo | % dos chats |
|---|---|
| reprovado | 34,1% |
| saldo insuficiente | 24,1% |
| não foi possível consultar | 16,2% |
| não autorizou a tempo | 11,4% |
| autorização expirada | 6,8% |

Na sessão final, o motivo «reprovado» cai para 1,7%.

**Porta de entrada.**
- 1º contato: FGTS TRÁFEGO 47,2%, «Mensagem inicial» 43,8%. O cliente abre o chat em 97,9% dos casos.
- 42,6% das sessões finais começam com um template da empresa, quase sempre o `template_utilidade_16`. Do template à resposta: p50 de 14 min.
- Pela contagem de ciclo, 54,2% dos últimos ciclos começam com o cliente respondendo a um template enviado até 7 dias antes.

**CLT ↔ FGTS.**
- No histórico: FGTS→CLT em 32,1% dos chats e CLT→FGTS em 3,9%.
- Antes do form da sessão final, **ninguém** cruza: 1.197 de 1.198 ficam só no FGTS.
- O CLT entra **depois** do pagamento, pelo botão «Ver simulação CLT». Na sessão final, 38,4% clicam.
- Só 23 sessões finais (1,9%) começam pela URA CLT. No ciclo do relatório fabio, porém, 438 chats tiveram entrada pela URA do CLT. Essa conta inclui o histórico de 2026, quando a URA CLT rodava em 30% a 45% das sessões. **Vale o 1,9% para o fluxo atual.**

**O fluxo mudou 3 vezes em 2026.**

| Período | Fluxo |
|---|---|
| até mar/2026 | antigo, incluindo a IA do webhook |
| mar–abr/2026 | URA v1 |
| abr–set/2026 | URA v2: CPF antes da autorização |
| set/2026 em diante | URA v3 (atual) |

- NEGOU NS e NEGOU CAMPANHA existem desde jul/2026.
- O aviso «Não executado» atingia 27% a 32% das sessões em mar–jun/2026. Zerou em out/2026.

---

## §3 Fabio × consultor

**Proporção, no ciclo aprovado (W = 30 s, 7 dias).**

| Classe | Conversas | % |
|---|---|---|
| Só robô | 711 | 57,6% |
| Com consultor | 506 | 41,0% |
| Indefinido | 17 | 1,4% |

Os 41% não contradizem os 2,5% a 9,8% de humano antes do form. O consultor quase sempre chega **depois**:

| Quando entra a 1ª mensagem humana | Conversas |
|---|---|
| Antes da aprovação | 20 (4,0%) |
| Depois da aprovação, antes do link | 254 (50,2%) |
| Depois do link de formalização | 176 (34,8%) |
| Depois do «Consegui Finalizar» | 56 (11,1%) |

**Quem formaliza.** A venda (oferta → «Sim» → PIX → form) é do robô em mais de 90% dos casos. O humano trabalha no trecho entre a aprovação e a assinatura.

**O que faz um chat ir para o humano.** % de conversas com consultor quando o sinal existe:

| Sinal | Com o sinal | Sem o sinal |
|---|---|---|
| Nota «sem dados na base, digitar manualmente, cadastro incompleto» | 93,9% (131) | 34,7% |
| Botão «Vou fazer depois» | 83,3% (84) | 37,9% |
| Cliente mandou áudio | 65,6% | 39,7% |
| «Estou com dificuldade» | 64,6% | 39,3% |
| NEGOU CAMPANHA | 64,2% (67) | 39,7% |
| NEGOU NS | 61,9% (105) | 39,1% |

O relatório de jornada conta «cadastro não localizado» em 129 sessões finais (10,8%). Os dois provavelmente medem o mesmo fenômeno.

**Como o humano trabalha.**
- Em 63,4% das conversas, ele chega sem o cliente ter chamado. É cobrança de assinatura.
- Da aprovação à 1ª mensagem humana: p50 de 81 min, p90 de 939 min.
- Ele entra e sai. 58% das conversas com consultor têm 2 episódios humanos ou mais.
- O que ele faz, em % das 506 conversas com consultor:

| Tarefa | % |
|---|---|
| Link, assinatura e formalização | 79% |
| Insistência e follow-up | 69% |
| Valor, simulação e proposta | 50% (255) |
| Chave PIX | 37% (189) |
| Documento e print | 31% (156) |
| Explicar saque-aniversário e parcelas | 18% (92) |
| Autorização no app | 6% (32) |

- São macros. 54% das mensagens humanas são assinadas e repetidas em 20 chats ou mais. 40% são texto livre.

**Duração do ciclo.**

| | Só robô | Com consultor |
|---|---|---|
| p50 | 1,3 h | 21 h |
| p90 | 16,4 h | 143 h |

---

## §4 O que o cliente diz

**Formato.** 46.497 mensagens de cliente:

| Tipo | Mensagens |
|---|---|
| botão | 19.536 |
| dado (CPF, mês, número) | 11.017 |
| texto livre | 13.558 |
| imagem | 429 (221 chats, 18%) |
| áudio | 210 (108 chats, 9%) |

Só 31% do texto livre cai em alguma categoria. O resto é «ok», «oi», «sim» e CPF digitado.

**Dúvidas e travas mais comuns** (chats):

| Categoria | Chats | Onde aparece | Humano em 24 h | Robô resolveu |
|---|---|---|---|---|
| Desistência / «depois» | 407 | pós-digitação | 35% | 8% |
| «Não consigo» / erro | 281 | 57% pós-digitação | 44% | — |
| Como autorizar | 241 | entrada e CPF | 29% | 28% |
| «Já autorizei» | 228 | CPF, entrada, consulta | 20% | 15% |
| Prazo / quando cai | 219 | pós-digitação | 43% | 6% |
| Já fiz em outro lugar / bloqueado | 157 | entrada | 29% | 8% |
| PIX | 147 | pós e PIX | 56% | 10% |
| Valor baixo / quero mais | 119 | oferta | 48% | 22% |
| Documento / selfie | 105 | biometria | 53% | 1% |
| Juros / taxa | 34 | entrada | 51% | 11% |
| Desconfiança | 13 | — | — | — |
| Pedido de humano / ligação | 6 | — | — | — |

- «Já autorizei» é o maior problema não resolvido. Só **19%** formalizam em 7 dias. É o cliente preso num ciclo de autorização que falhou.
- Desconfiança e pedido de humano quase não aparecem. «golpe» aparece em 0 chats. Pode ser efeito do vocabulário fechado (palavras raras viram `<w>`) e do áudio. Medir isso **precisa de dado cru**.

**Objeção de valor depois da oferta.** Na 1ª oferta (1.201 chats):

| Resposta | Chats |
|---|---|
| «Sim» | 990 (82%) |
| «Não» | 105 (9%) |
| texto | 65 (5%) |
| silêncio por 48 h | 40 (3%) |

Objeção de valor por texto depois da oferta: só 51 chats.

**O que aconteceu com os 105 que disseram «Não» na NS:**

| Caminho | Chats | Humano em 48 h | Formalizou em 24 h | Formalizou em 7 d |
|---|---|---|---|---|
| não → sim (CAMPANHA) | 27 | 13 | 25 | 25 |
| não → não → sim (3º degrau, áudio) | 26 | 13 | 25 | 25 |
| não → não → não | 18 | 17 | 2 | 7 |
| outros (parou, digitou, mandou áudio) | 34 | 21 | 8 | 14 |

**O que funcionou.** As respostas sobre valor que se repetem em 20 chats ou mais:

| Padrão | Exemplo anonimizado | Chats |
|---|---|---|
| Explicar o valor baixo | «<nome> já realizou antecipações do fgts comprometendo as parcelas mais próximas…» | 41 (fabio) / 61 (objeções) |
| Anunciar o maior valor pelo gerente | «… agora com meu gerente conseguimos liberar o maior valor disponível pra você no banco giro! <valor>» | 22 (fabio) / 31 (objeções) |
| Anunciar o maior valor pelo supervisor | «<w> notícia! consegui liberar com meu supervisor uma proposta no valor de * <valor> *» | 31 (objeções) / 40 (revisão, histórico, assinatura removida) |
| Maior valor por outro banco (robô) | «* giro <nome> * te liberou <w> * maior * valor!» / «* banco bms * te liberou…» | 58 / 45 |
| Fechar com urgência | «<nome> interesse em receber este valor em conta * hoje ? *» | 29 |
| Pedir o PIX na mesma mensagem | «<nome> você quer receber seu fgts em menos de <n> minutos, me envie: chave pix de sua titularidade» | 24 |

As contagens diferem entre os relatórios porque o de fabio conta só dentro do ciclo aprovado e o de objeções conta no histórico inteiro. **Para dimensionar a IA, vale o número do ciclo (fabio).** O de objeções mostra que o padrão é estável no tempo.

Nenhuma resposta a uma objeção de valor **por texto** se repete em 20 chats. Não existe um script de valor padrão. O valor está mascarado, então não dá para medir quanto o «maior valor» subiu.

---

## §5 Operação

**Horários.** Sem os dias de pico 09–10/11:

| Faixa | Mensagens do cliente |
|---|---|
| 8–17 h | 78,2% |
| 18–23 h | 13,7% |
| 0–7 h | 8,2% |

- Sábado recebe 9,5% das mensagens e domingo 2,0%.
- 97% das primeiras mensagens humanas saem entre 7 h e 19 h.

**Latência.**
- Robô: p50 de 7 s e p90 de 2,8 min.
- Humano (H2, W = 30 s): p50 de 9,4 min e p90 de 3,9 h. Fora do expediente, p90 de 15 h.
- Por faixa, contando da mensagem pendente do cliente (relatório fabio):

| Faixa | p50 |
|---|---|
| 18–23 h | 777 min |
| segunda-feira | 136 min |
| terça-feira | 15,9 min |

**As duas medidas de espera humana não brigam.** O p50 de 9,4 min (operação) mede qualquer resposta humana a qualquer mensagem do cliente. O p50 de 81 min (fabio) mede da aprovação até a 1ª entrada do consultor.

**Lembretes.** 1.045 chats (84,7%) receberam template. A resposta cai a cada lembrete da mesma sequência de silêncio:

| Lembrete | Resposta em 24 h |
|---|---|
| 1º | 57,2% |
| 2º | 38,2% |
| 3º | 27,4% |
| 4º em diante | 17,8% |

O 4º lembrete em diante soma 27% dos envios.

**Janela de 24 h e erros.** São 540 erros em 96.924 envios (0,56%). O campo `err` está sempre falso. O erro só aparece no status.

| Envio | Taxa de erro |
|---|---|
| Livre, dentro de 24 h | 0,05% |
| **Livre, depois de 24 h** | **50,9%** (botão 96%, chat humano 81%) |
| Template, depois de 24 h | 0,55% |

**Automações já ativas** (a IA não pode duplicá-las):
- timer de segurança de 15 min: 923 chats;
- retry FGTS: 264 chats;
- agenda de follow-ups: 178 chats;
- «timers · followup»: 240 chats.

A regra «respondeu ao comercial, follow desativado» já desliga o follow-up quando o comercial entra (49 chats).

**A IA já existiu.** O diálogo «IA - WEBHOOK - Conversa» disparou 507 vezes em 69 chats, entre 09/2025 e 03/2026.
- Atuava **antes** da oferta, na coleta de CPF, na autorização e na consulta.
- Respondia com p50 de 16 s.
- Em 21 chats terminou em «estamos te transferindo para um atendente».
- Saiu do ar em 03/2026.

**Status final do chat.**

| Status | % |
|---|---|
| FECHADO | 46,2% |
| RESOLVIDO | 31,8% |
| EM ATENDIMENTO | 15,7% |
| ABERTO | 6,2% |

**Pico.** Em 09/11 chegaram 8.446 mensagens de cliente num único dia, logo depois de um disparo de template.

---

## §6 O que isso muda no desenho da IA Fabio Junior

### 6.1 Ponto de entrada

**Números divergentes sobre as recusas.** Cada relatório mede numa janela diferente.

| Medida | jornada (sessão final) | fabio (ciclo de 7 dias) | objeções / operação (histórico) |
|---|---|---|---|
| NEGOU NS | 82 (6,8%) | 105 | 116 (9,4%) |
| NEGOU CAMPANHA | 43 (3,6%) | 67 | 74 (6,0%) |

- **Para dimensionar a IA, vale o histórico (116 e 74).** A sessão final só guarda quem formalizou naquela mesma sessão, ou seja, esconde quem negou e demorou.
- A jornada diz que os 43 que negaram a CAMPANHA na sessão final formalizaram todos. Isso vale por construção. No histórico, 66 de 74 formalizaram mais tarde.

**Recomendação de entrada:**
1. **Entrada principal: no lugar do 3º degrau atual** (áudio + «APROVEITE!»), logo depois de NEGOU CAMPANHA. Hoje o robô responde a esse ponto em p50 de 5 s.
   - Substituindo o áudio, a IA recebe 60 chats na 1ª oferta (64 de 100 contando pelo diálogo NEGOU CAMPANHA em 48 h; 74 contando todos os ciclos).
   - Entrando depois do áudio, recebe só 34.
   - Se a IA entrar e o áudio continuar, os dois competem.
2. **Entrada secundária: o cliente não responde ao lembrete** depois de uma oferta. Na recusa, 16% a 22% somem por 1 h ou mais e voltam. Use no máximo até o 3º lembrete.
3. **Não entrar** na coleta de CPF nem na autorização. A IA antiga fez isso e saiu do ar. Essa fase o robô resolve em cerca de 40 min.
4. **Não oferecer CLT** antes do «Pagamento Confirmado».

O tamanho real da fatia da IA está nos clientes que **não** aprovaram, e eles não estão neste corpus.

### 6.2 O que a IA precisa saber responder

Ordem de prioridade dentro do degrau GOLD:
1. **Por que o valor é baixo.** Antecipações anteriores comprometeram as parcelas mais próximas, então o valor não aumenta.
2. **Quando o dinheiro cai.** 219 chats perguntam. Hoje o robô resolve só 6%.
3. **Chave PIX.** Titularidade e como trocar (147 a 189 chats).
4. **«Já autorizei» / como autorizar** (228 e 241 chats). Responder com status da consulta e uma previsão, sem nova oferta. O cliente fica nesse limbo 27 a 86 min.
5. **Confiança.** É rara, mas a resposta pronta existe: «você pode ficar absolutamente tranquilo… empresa séria com mais de <n> anos» (43 chats) e «segue as informações da nossa empresa para você ficar mais tranquilo…» (44 chats).
6. **Mídia.** 24% dos chats mandam áudio ou imagem. O mínimo é transcrever o áudio. Para imagem, reconhecer um print de erro e dar o passo certo, ou repassar.

### 6.3 Roteiro do degrau GOLD

Baseado só em padrões vistos em 20 chats ou mais:
1. Usar o contexto. A IA sabe que NS e CAMPANHA foram negadas e lê o último motivo de falha do histórico. Ela não repete a URA.
2. Explicar em 1 frase o motivo do valor, quando houver antecipação anterior.
3. Apresentar o GOLD como liberação especial: «consegui liberar com meu supervisor uma proposta no valor de <valor>». Só se for verdade. Ver Q-CF-02.
4. Fechar com uma pergunta curta e urgente: «interesse em receber este valor em conta hoje?»
5. No «sim», pedir a chave PIX na mesma mensagem e devolver ao fluxo do robô (Confirmar Dados → form). Hoje, do «não» recuperado ao form, a mediana é de 4 a 5 min.
6. No «não», repassar. Não abrir um 4º degrau.

### 6.4 Quando repassar ao consultor

| Situação | Ação |
|---|---|
| GOLD negado | repasse imediato |
| Cliente pede uma pessoa | repasse imediato |
| Nota «cadastro incompleto, digitar manualmente» (94% vão ao humano hoje) | a IA coleta nome, data de nascimento e sexo e repassa |
| Documento, selfie ou biometria travados (o robô resolve 1%) | repasse cedo |
| «Já autorizei» sem avanço depois do status | repasse |
| 4º lembrete sem resposta | parar ou repassar |
| Fora do expediente (7–19 h) | a IA continua atendendo; o repasse fica agendado e o cliente é avisado do horário |

O repasse leva junto o resumo: degraus negados, valor oferecido e última pergunta. 58% das conversas com consultor têm vai-e-volta, e o consultor não deve repetir perguntas.

### 6.5 Tom e frases de abertura

Todos os padrões abaixo aparecem em 20 chats ou mais.
- Saudação pelo horário com o nome: «<nome> dia <nome>, tudo bem com você?» (115) e «<nome> tarde <nome>, tudo bem com você?» (117).
- Mensagens curtas, uma ideia por mensagem, com urgência: «hoje», «em menos de <n> minutos».
- Sem textão e sem abrir defendendo a segurança. A resposta de confiança fica pronta para quando o cliente pedir.
- Ritmo de robô: responder em segundos. O robô hoje tem p50 de 7 s.

### 6.6 Métricas de sucesso e linha de base do piloto

| Métrica | Linha de base hoje (corpus de aprovados) |
|---|---|
| Formalização em 7 dias depois do 3º «não» | 7 de 18 (39%), mediana de 456 h |
| Formalização em 24 h depois de NEGOU CAMPANHA | 25 de 26 no caminho «não → não → sim» |
| Humano em 48 h depois do 1º NEGOU NS | 69 de 116 (59%), mediana de 1,1 h. A qualquer tempo depois: 75 |
| Humano em 48 h depois do 1º NEGOU CAMPANHA | 46 de 74 (62%), mediana de 0,8 h. A qualquer tempo depois: 50 |
| Tempo do «não» recuperado ao form | p50 de 4–5 min, p90 de 43–45 min |
| Tempo de resposta | robô p50 7 s; humano p50 9,4 min, p90 3,9 h |
| Erro por janela de 24 h | 50,9% das mensagens livres fora da janela |

Metas sugeridas para o piloto:
1. Mais de 39% de formalização em 7 dias no grupo que negou três vezes.
2. Repasse ao humano em 48 h abaixo de 62% depois de NEGOU CAMPANHA.
3. Erro de envio fora da janela perto de 0%.
4. Resposta em menos de 30 s.

Essas metas precisam de um grupo de controle, porque a base mostra só aprovados.

### 6.7 Riscos

1. **Competir com o 3º degrau atual.** Se o áudio + «APROVEITE!» ficar no ar, o cliente recebe duas ofertas.
2. **Promessa falsa.** «Meu gerente liberou o maior valor» só pode ser dito se o GOLD for de fato uma tabela maior.
3. **Duplicar automações.** O timer de 15 min, o retry e os follow-ups precisam ser suspensos quando a IA assume.
4. **Janela de 24 h.** Mensagem livre fora dela falha. Fora da janela, só template aprovado.
5. **Treinar no fluxo velho.** Exemplos de antes de set/2026 ensinam etapas que já não existem. Use só o fluxo v3.
6. **Pico de volume.** Foram 8.446 mensagens num dia. A IA e a fila de repasse precisam aguentar isso.
7. **Viés de sobrevivência.** Toda taxa aqui é teto. A conversão real só aparece com o corpus de quem não aprovou.

---

## §7 Limitações e perguntas ao dono

**Limitações.**
- Só há aprovados. As taxas medem velocidade, não conversão.
- Robô × humano é inferido. A assinatura é forte, mas uma automação feita com a conta de um consultor também sairia assinada.
- `<valor>` está mascarado. Não dá para medir a diferença entre NS, CAMPANHA e GOLD, nem qual tabela foi formalizada.
- O conteúdo de áudio e imagem não está no corpus, nem o do áudio do 3º degrau.
- O vocabulário fechado subconta desconfiança e pedido de humano.
- As categorias de texto saem de regex e se sobrepõem.
- O pico de 09–10/11 distorce dia da semana e horário da formalização.
- Cada relatório usa um corte de histórico. Onde os números divergem, o estudo mostra os dois.

**Perguntas ao dono.**

- **Q-CF-01. A IA substitui o 3º degrau atual (áudio + «APROVEITE!») ou entra depois dele?**
  Padrão recomendado: **substituir**. A IA recebe 60 chats em vez de 34 e não compete com o áudio.
- **Q-CF-02. O GOLD é uma tabela maior do Novo Saque, ou é o «maior valor» por outro banco (giro, bms), como nas macros de hoje?**
  Padrão recomendado: a IA só usa a frase «consegui liberar com meu supervisor» se o GOLD for de fato maior que a CAMPANHA. Se for outro banco, a IA diz o nome do banco.
- **Q-CF-03. O que o áudio do 3º degrau diz, e qual valor ele oferece?**
  Padrão recomendado: o dono descreve o conteúdo. Assim não precisamos de dado cru.
- **Q-CF-04. A IA também cobra assinatura depois da aprovação, que é a maior tarefa do consultor?**
  Padrão recomendado: **fase 2**. No piloto, só o GOLD. Depois, os lembretes de assinatura com base nas macros de hoje (1 h e 24 h).
- **Q-CF-05. Quando há cadastro incompleto, a IA coleta os dados e repassa?**
  Padrão recomendado: **sim**. Coleta nome, data de nascimento e sexo e repassa. A IA não digita proposta.
- **Q-CF-06. A IA atende 24/7, com repasse agendado para as 8 h?**
  Padrão recomendado: **sim**. Ela avisa o cliente do horário do retorno.
- **Q-CF-07. Qual é o limite de lembretes?**
  Padrão recomendado: **até 3**. Do 4º em diante, a resposta é de 17,8%. Fora da janela de 24 h, só template.
- **Q-CF-08. A IA pode transcrever áudio do cliente?**
  Padrão recomendado: **sim**, só transcrição, sem guardar o áudio.
- **Q-CF-09. Libera um corpus agregado de não aprovados e desistentes?**
  Padrão recomendado: **sim**, com as mesmas regras de anonimização. Sem ele não dá para dimensionar a fatia da IA nem a conversão real.
- **Q-CF-10. A IA oferece CLT?**
  Padrão recomendado: **não** durante a negociação do FGTS. Só depois do «Pagamento Confirmado», como hoje.
- **Q-CF-11. A IA atende quem diz «já autorizei» e está preso na consulta?**
  Padrão recomendado: **sim, só com status e previsão**, sem nova oferta. Se não houver avanço, ela repassa.

---

## §8 Revisão

Revisão de completude e consistência em 10/11/2026. Recalculei os números direto do `seguro/msgs.jsonl`, com scripts próprios (`scripts/critica_01_numeros.py` a `critica_04_hora_negou.py`). Saída só agregada.

**O que conferi e bateu.**

| Número do estudo | Recalculado |
|---|---|
| 1.234 chats; 46.497 / 96.924 / 33.665 linhas | igual |
| Notas «recebido form» 1.198, «aprovado tabela ns» 1.201, «fase de digitação» 1.201 | igual |
| NEGOU NS 116, NEGOU CAMPANHA 74, NEGOU AUDIO 34, IA-WEBHOOK 507 disparos em 69 chats | igual |
| Assinatura: 3.652 mensagens em 633 chats | igual (com a regex do relatório cliente) |
| 1ª oferta: «Sim» 990, «Não» 105, silêncio 40 | 988, 105 (100 pelo diálogo + 5 sem diálogo), 40 |
| Template em 1.045 chats (84,7%) | igual |
| Imagem 429 em 221 chats; áudio 210 em 108 chats | igual |
| Horário sem 09–10/11: 78,2% / 13,7% / 8,2% | igual |
| Pico 09/11: 8.446 mensagens de cliente | igual |
| Status final: 46,2 / 31,8 / 15,7 / 6,2% | igual |
| Erros: 540; livre fora de 24 h 50,9%; dentro 0,05%; template fora 0,55%; 81% dos erros | igual (440 de 540) |
| Sessão anterior: 72,9% | igual (873 de 1.198) |
| Frases: saudação 115 e 117, «antecipações…» 61, «gerente… maior valor» 31, «hoje?» 29, PIX 24 | igual |

**O que corrigi.**
1. §0, item 3. Dizia «73% já tinham falhado antes». Os 72,9% medem sessão anterior, não falha. Agora: 72,9% conversaram antes e 67% a 69% consultaram antes (69% na minha conta, por nota de consulta ou diálogo de CPF).
2. §6.6. «Humano em 48 h depois de NEGOU NS: 75 de 116» e «NEGOU CAMPANHA: 50 de 74» não eram de 48 h. Eram a qualquer tempo depois. Em 48 h após o 1º «não»: **69 de 116** (p50 1,1 h) e **46 de 74** (p50 0,8 h). A meta 2 do piloto passou de «abaixo de 65%» para «abaixo de 62% em 48 h», a linha de base real.
3. §1. «Pagamento Confirmado» 906 é da sessão final. No histórico são 923 chats.
4. §4 e §6.2. Frases de confiança e de supervisor estavam subcontadas: sem a assinatura, «supervisor» aparece em 40 chats (não 31) e «absolutamente tranquilo» em 43 (não 39). Acrescentei «segue as informações da nossa empresa para você ficar mais tranquilo…» (44 chats).
5. §6.1. Contando pelo diálogo, 64 de 100 que negaram a NS negam também a CAMPANHA em 48 h. O 60 do relatório cliente fica como limite de baixo.

**Heurística robô × humano.**
- A assinatura é sólida e estável. Mas a regex aceita no máximo 2 tokens de nome no começo. Uma regex solta (qualquer `* <nome> : *`) pega só 3.030 mensagens em 602 chats. O número de humanos depende do formato exato.
- Ponto frágil: o filtro de texto repetido manda para «robô» toda macro **sem** assinatura. Como 54% das mensagens humanas são macros, os 57,6% «só robô» são teto. A frase do supervisor sai sem assinatura em pelo menos 31 chats. Ela pode ser macro humana ou automação. Não dá para separar sem dado cru.
- O «humano antes do form» varia de 2,5% a 10,7% conforme a regra. Para decisão, usar a regra estrita (só assinatura): 2,5%.

**Risco de PII.**
- Nenhum hash de chat nos `.md` de `saida/`. Nenhuma frase citada com k < 20. As contagens abaixo de 20 (desconfiança 13, pedido de humano 6) são categorias, não frases.
- Fora do padrão: há 3 arquivos `f0_forma.json`, `f1_detalhes.json` e `f1_detalhes_valores.json` na raiz de `agregados/fgts/`, fora de `saida/`. São de outro tema (scripts `f*.py`). Os códigos hexadecimais neles são UUIDs de configuração com k ≥ 20, não hashes de chat. Os scripts `f*.py` e `fabio_humano_*.py` estão com permissão 664, não 600. Não mexi, porque não são deste tema.

**Perguntas para a IA que ficaram sem resposta.**
1. Horário do «não». Medi: das 74 NEGOU CAMPANHA, 53 caem em dia útil 8–18 h, 16 à noite ou de madrugada e 5 no fim de semana. Ou seja, **28%** dos casos do GOLD chegam fora do expediente, quando o humano demora p50 de 777 min. Isso reforça Q-CF-06 (IA 24/7).
2. O que o humano fez com os 7 de 18 que formalizaram depois do 3º «não». O n é pequeno demais para k ≥ 20. Fica aberto.
3. Quanto o GOLD precisa subir para virar o «não». `<valor>` está mascarado. Precisa de dado cru ou da tabela do banco (Q-CF-02).
4. Quantos «não» viram «sim» só pelo tempo, sem nova oferta. Exige grupo de controle (Q-CF-09).
5. Conteúdo do áudio do 3º degrau: segue em Q-CF-03.
