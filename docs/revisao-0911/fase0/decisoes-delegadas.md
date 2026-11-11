# Decisões delegadas da revisão 0911 (Fable, 10/11/2026 ~09:10 BRT)

> **Base da delegação:** mensagem do dono de 10/11, «para as decisões use um Fable para escolher». Vale para as decisões abertas de `estudos/PLANO-REVISAO-0911.md` §8 («Ainda abertos: atos de 09/11, degrau de 1 dia, prioridade da fila Cliente360, leituras de produção»).
> **O que este arquivo é:** decisão de plano. Nada foi executado, mergeado, publicado nem lido em produção para escrevê-lo. O roteiro não foi editado; quem registra na Parte F e no Painel é a sessão principal, como «decisão delegada (Fable, 10/11)».
> **Reversão:** o dono derruba qualquer item com uma palavra. Os itens 1, 2 e 3 só ganham efeito irreversível no checkpoint de 11/11 18:00.
> **Sem PII e sem credencial.** Proveniência: `arquivo:linha` (roteiro v3.3, linhas reais lidas hoje) ou arquivo + âncora.

## 0. Fatos em que as decisões se apoiam

| # | Fato | Fonte |
|---|---|---|
| F1 | Nenhum ato de 09/11 tem registro; «sem registro» não prova «não feito» | `PLANO-REVISAO-0911.md` §0.1 |
| F2 | O Redeploy de 10/11 05:30 só rodava com rotas e env gravados na noite de 09/11; senão, reserva 11/11 05:30 e A3.0–A3.7 escorregam um dia | `PLANO-REVISAO-0911.md` §0.2; `ROTEIRO-DE-ACAO.md:174` |
| F3 | Resíduo 63,6 d-agente (HIPÓTESE); ritmo observado r ≈ 0,49; com 3 agentes nada fecha | `ROTEIRO-DE-ACAO.md:1222-1231` |
| F4 | B1.6b não começou; PR #13 e PR #49 estão `CONFLICTING`; B4 e B7 não têm código; kits de 05–08/11 não existem | `PLANO-REVISAO-0911.md` §0.5, §0.7, §1; `fase0/MANIFESTO.md` «## PRs abertos» |
| F5 | A regra «Se atrasar» já está escrita e aceita com o cenário C: 1 dia ⇒ congelamento 19/11, piloto 27–30/11, relatório 01/12; 2 dias ⇒ sem piloto real | `ROTEIRO-DE-ACAO.md:1292-1295` |
| F6 | **Medido agora na S3 (10/11 09:03, só leitura local):** carga 15,4 em 12 vCPU; 3,4 GB disponíveis de 15 GB; 29 GB de swap em uso; 51 contêineres; dezenas de processos de teste em curso | `scripts/dd-capacidade.sh` (saída desta sessão) |
| F7 | O kit do gateway nunca rodou no real e o README ainda traz as datas de 04–06/11 (`imagem-no-ar-0511.txt`, «Reserva: sexta 06/11») | `kits/gateway/README.md` tabela «Passo a passo», «### Quinta 05/11», «### Reserva» |
| F8 | `cliente360-web`: ponta remota diferente da local no manifesto | `fase0/MANIFESTO.md:8` |

F6 é o fato novo: a máquina já está saturada antes de religar a construção. Não atribuo a carga a ninguém (não medi de quem é).

---

## 1. Calendário: **degrau de 1 dia, adotado já**

**Decisão.** Congelamento **qui 19/11 18:00**; `ativar.sh` em 19/11 depois das 20:30; F3 oficial 19→20/11, sem janela de correção (falha ⇒ no-go); sombra 23/11 08:00 → 25/11 12:00 (não muda); ensaio B em 25/11 12:00–17:00; go/no-go **26/11 12:00**; piloto **27–30/11** (4 dias, domingo 29/11 como dia 3); relatório **01/12 21:00**; margem 02–04/12; teto 04/12 intacto. É a regra de `ROTEIRO-DE-ACAO.md:1293`, aplicada sem alteração.

**Por quê.**
1. O atraso já é fato, não risco: a construção não rodou em 09/11 nem roda cheia em 10/11 (F1, F4, F6), e a cadeia do canal perdeu pelo menos um dia (F2).
2. Conta (HIPÓTESE, mesma fórmula de `ROTEIRO-DE-ACAO.md:1229`), com a construção cheia a partir de 11/11: até 18/11 são 8 dias ⇒ r ≤ 0,63 · 0,50 · 0,38 (5 · 4 · 3 agentes); até 19/11 são 9 dias ⇒ r ≤ 0,71 · **0,57** · 0,42. Contra r ≈ 0,49, manter 18/11 só fecha com 5 agentes e zero parada; o degrau fecha com 4.
3. O relatório continua em 01/12 e os três dias de margem ficam inteiros.
4. Decidir hoje deixa remarcar com ordem o mapa de deploys, o ensaio B e o aviso aos consultores; decidir em 18/11 seria remarcar tudo na véspera.

**Custo assumido (precisa da ciência do dono):**
- a F3 oficial perde a correção de 19/11 à noite: falha de I1–I9 vira no-go;
- o dia 1 do piloto passa a ser a **Black Friday** (27/11; `ROTEIRO-DE-ACAO.md:1280`), o que a crítica do cenário B tinha evitado (`REPLANEJAMENTO-INICIO-0911.md` §3 item 3);
- o piloto cai de 5 para 4 dias. A rampa de 4 dias **não existe no roteiro**: fica para o dono fixar até o go/no-go (não decido número de atendimentos);
- o aviso aos consultores e a A1.11 ao superior passam a dizer «a partir de 27/11».

**Mitigação que decido:** a F3 prévia vira obrigatória e mais longa, 16→18/11, com o que estiver construído, porque é a única caça a defeito antes da oficial.

**Alternativas descartadas.**
- **Manter 18/11:** folga aritmética de 0,01 com 4 agentes, e a S3 não comporta 5 hoje (F6). Seria prometer uma data que os números não sustentam e cair no degrau sem aviso.
- **Esticar o piloto até 02/12:** não compra um dia de construção sequer; gasta 2 dos 3 dias de margem (relatório em 03/12), cruza 01/12 em operação (chave de dezembro, teto mensal, 3ª renovação do cookie) e pede 10 dias seguidos de operador. Continua sendo opção do dono no go/no-go, com as quatro condições de `ROTEIRO-DE-ACAO.md:1295`. Padrão: não esticar.

**Limite duro:** mais um dia perdido (2 no total) ⇒ não há piloto real e o relatório de 01/12 sai com a sombra (`ROTEIRO-DE-ACAO.md:1294`). Não há segundo degrau.

### 1b. Mapa de deploys do degrau (proposta; cada `!` continua pedindo o «sim» do dono)

| Ato | Cenário C (`ROTEIRO-DE-ACAO.md:1290`) | Degrau |
|---|---|---|
| Rotas + env do gateway (N1–N3) | 09/11 noite | **10/11 depois das 20:30** |
| Redeploy do gateway (#2) | 10/11 05:30 | **11/11 05:30** (a reserva) |
| A3.0–A3.3 · A3.4–A3.7 | 10/11 · 11/11 | 11/11 08:30 · 12/11 |
| A4.3a (S4 papéis e hba) | 09/11 13:15 | 11/11 13:15 |
| A3.8 (`zz-ensaio-ui`) | 09/11 12:30 | 12/11 13:15 |
| web #3 (B4.2) | 11/11 12:30 | 12/11 12:30 (B4 não tem código, F4) |
| API #4 | 12/11 12:30 | 13/11 12:30 |
| A4.6 (0001–0005) | 13/11 12:30 | 13/11 13:15 |
| `facta-on` #5 (tap + janela) | 12/11 noite | 13/11 depois das 20:30 (o tap ainda lê o domingo 15/11) |
| Tag `v0.3.0` (B1.7) | 12/11 | 13/11 |
| Orquestrador e dublê #8 | 13/11 noite | 16/11 depois das 20:30 |
| n8n, espelho e vigia #6 | 16/11 12:30 | 17/11 12:30 |
| web #7 | 17/11 12:30 | 18/11 12:30 |
| Última tag + chave AES de dezembro | 18/11 12:30 | 19/11 12:30, tags até 17:00 |
| A4.2/A4.3b · A4.4 | 10/11 noite · 11/11 noite | 11/11 noite · 12/11 noite, **só se a VPS existir** |

Não muda: B9.5a em dev em 15/11; nenhum `!` em fim de semana, feriado, DATAPREV, sombra ou piloto; X2 (o tap nunca no dia do gateway). A sessão principal confere as dependências antes de levar ao roteiro.

---

## 2. Revisão × construção

**Decisão.** A revisão segue completa (ordem do dono). A construção volta em degraus, com portão medido, não por relógio:

| Quando | Agentes de construção | Portão (`free -m` e `uptime`, na S3) | O que fazem |
|---|---|---|---|
| **10/11, já** | **1** | nenhum (cabe hoje) | B1.6b (caminho crítico: segura o PR #13 e a tag `v0.3.0`) |
| 10/11, quando abrir | **2** | disponível ≥ 5 GB e carga < 12 | conflitos do PR #13 e do PR #49 (inclui `conferir_janela_min` 10→20, contrato 05); só local, sem merge |
| **11/11 08:00** | **4** | disponível ≥ 6 GB, swap parado, ensaios pesados da Fase 2 encerrados | filas A1, A2, A3 e A5 de `ROTEIRO-DE-ACAO.md:1249-1255`; A4 entra como 4º se B6.x estiver travada pelos ensaios A3 |
| 12/11, fim da Fase 3 do lote de código | **5** | disponível ≥ 6 GB com os 4 rodando | fila que sobrou |

Regras: suíte pesada uma por vez, pela mesma trava `pesado.sh`, valendo para revisão e construção; com carga > 12, a revisão roda um ensaio pesado por vez (os leitores são leves e seguem). O portão pesa mais que a data: sem memória, não sobe agente.

**Por quê.** Congelar a construção dois dias mata o piloto real (F5); subir 4–5 agentes agora derruba a máquina (F6: carga 15 em 12 vCPU e 29 GB de swap; o `test_rajada_um_turno` já é instável sob carga, `RETOMAR-0911.md` «Pendências abertas»), e a linha de base da revisão sairia vermelha por carga, não por defeito. Um agente em B1.6b hoje protege o item de maior fila sem disputar os SHAs do manifesto.

**Regra X7 (checkpoint 0, hoje 18:00).** O checkpoint vai registrar ≤ 3 agentes vivos. Isso **não** dispara a alternativa (c) por decisão minha: ela fere a alínea (ae) e é «sem padrão: o dono decide» (`ROTEIRO-DE-ACAO.md:1231`). Decido só remedir em **11/11 18:00** (checkpoint 0b), exigindo ≥ 4 vivos. Abaixo disso, X7 vai ao dono no mesmo dia.

**Alternativas descartadas.** (A) congelar a construção até a revisão acabar; (B) 4–5 agentes hoje; (C) revisão enxuta, que contraria a ordem do dono de 10/11 (`PLANO-REVISAO-0911.md` §8 «Decidido pelo dono»).

**O que reconferir no congelamento (19/11 18:00).** Os achados valem para os SHAs de `fase0/MANIFESTO.md`.
1. `git diff <SHA do manifesto>..<SHA congelado>` por repositório, com a lista de arquivos tocados.
2. Cada CRÍTICO/ALTO reverificado no SHA congelado: existe, corrigido ou mudou de lugar.
3. Código que nasce depois do manifesto (B1.6b, B1.7, B4.x, B5.2–B5.9, B6.1–B6.8, B7.x, `feat/esteira` já com remoto) passa por leitura dirigida **antes do `!` do seu deploy** (opção E de §8, só para o delta), e não toda em 19/11.
4. Kits novos (`s4/migrar.sh`, `config/domingo.sh`, `gateway/ativar.sh`, chave AES de dezembro): ensaio local, `desfazer`, e manifesto sha256 reemitido e conferido antes de cada «sim» (RS-08).
5. Linhas da matriz §3b hoje em «NÃO EXISTE» (RS-01 rede, RS-10, RS-11, ntfy, 19:45): reexecutar a prova; viram critério de aceite do bloco.
6. Costuras da Fase 2b cujo lado mudou; portão de PII (`piiscan` + gitleaks) sobre a pasta da revisão.
7. Prazo: CRÍTICO/ALTO do delta fechados até **25/11 12:00**, antes do go/no-go de 26/11.

**Correções.** CRÍTICO num componente segura o `!` desse componente. Correção que cabe no PR do próprio bloco e não muda data entra na construção sem «sim» separado. A que muda data ou escopo continua pedindo o «sim» do dono por item (`PLANO-REVISAO-0911.md` §6).

---

## 3. Fila do Cliente360 × IA na S3 (10 → 19/11)

**Decisão.** A IA tem prioridade na S3 até o congelamento (19/11 18:00). Para o Cliente360, nesse período:
- **entra na hora:** incidente de produção (login, propostas, digitação, comissão errada) e o que o dono mandar furando a fila, com a palavra dele;
- **uma vaga:** no máximo 1 agente de Cliente360 na S3, sem suíte pesada ao mesmo tempo que a da IA;
- **espera 19/11 18:00:** funcionalidade nova, refatoração e estudo. De 19/11 em diante (F3, sombra, piloto) os agentes de construção ficam livres e a fila volta ao normal;
- **conta como IA:** B4.1–B4.3 (`cliente360-api`) e B4.2/B7.1 (`cliente360-web`);
- **sem merge de Cliente360 no web dentro das janelas da IA** (12/11 e 18/11, 12:30–14:00): o web faz deploy no merge e deploys concorrentes já derrubaram a produção. Antes de B4.2, a ponta local do web precisa ser atualizada (F8).

**Por quê.** A S3 já está no limite (F6) e a IA precisa de ≥ 4 agentes por 9 dias com folga de 0,08 sobre o ritmo observado (§1). É o único projeto com teto «nunca depois». O Cliente360 está em produção e funciona; o que não pode esperar é incidente, e isso continua entrando.

**Alternativa descartada.** Dividir a máquina meio a meio (a IA cairia para 2–3 agentes ⇒ X7) e congelar o Cliente360 por inteiro (incidente de produção não espera).

---

## 4. Leituras só-leitura de produção: quem roda e quais

**Decisão.** Roda a **sessão principal do Claude**, num lote só, por script gravado em `~/ia-revisao-0911/sondas/`, na faixa 12:30–14:00 de 10/11 (a S5 de volume, de novo, à noite). Saída só por forma e contagem, passando pelo portão de PII. **Os subagentes da revisão não rodam nenhuma** (sem ssh). Se o classificador barrar, a sonda vira `!` do dono; ninguém contorna. Precedente: `ROTEIRO-DE-ACAO.md:1263` («só leitura; se barrado, `!`»).

Ficam com o **dono**: o que toca o Coolify pelo `tinker` ou lê valor de variável (o próprio `portao.sh`) e a tela do Phoenix. Com o **Danilo**: o `salvo_em` do cookie e a tela do ChatGuru.

**Nunca se lê:** valor de segredo ou de variável de ambiente (só nome e presença), `gateway.payloads`, corpo de mensagem. A S4 se lê por conexão direta: o MCP `supabase-gl360` mede outro banco.

| # | Onde | Sonda (nenhuma escreve) | Responde |
|---|---|---|---|
| S0 | S3 local | existe `~/ia-gateway-segredos`? data do diretório (sem listar conteúdo) | indício de `env-gateway.sh` rodado |
| S1 | S2 `n8n-db` | `SELECT path, ativo, critico, corpo_campos IS NULL, guardar_corpo FROM gateway.rotas WHERE path LIKE 'ia-%' OR path LIKE 'zz-%'` + contagem total | `rotas-ia.sh` rodou? linha E-12 existe? |
| S2 | S2 | `GET /health` do gateway (versão e SHA) + `StartedAt` e imagem do contêiner | o Redeploy de 10/11 05:30 saiu? |
| S3 | S2 | `df -h / /var/lib/docker` e `uptime` | portão de disco (X5, P4, PD-3) |
| S4 | S2 | fila de deploys do Coolify: contagem por estado desde 04/11 | houve deploy do gateway fora de janela? |
| S5 | S2 | `count(*)` de `gateway.requisicoes` nos últimos 10 min (à noite) | X3: < 150 por 10 min |
| S6 | S2 n8n | `SELECT name, active` dos workflows «IA%» e «zz-ensaio%»; versão do n8n; nomes das variáveis de retenção de execução; forma do nó «Entrada ok?» do `zVuE` | A3.8 rodou? sumidouro importado? HIPÓTESE de A3.0 |
| S7 | S4 | `pgbackrest info` | X4: retenção dos fulls × prova de 14 d (D-32) |
| S8 | S4 | `pg_roles` e `pg_database` com `ia%`; `pg_hba_file_rules` das linhas `ia_*` | A4.3a rodou? RS-12 |
| S9 | S2 | `/healthz` do `facta-on` (versão, SHA), nomes e estado das flags `FACTAON_*`, janela de conferência efetiva | #5 ainda não saiu; RS-15 |
| S10 | S2 | `/healthz` de `cliente360-api` e do web | versão viva × manifesto |
| S11 | GitHub | rulesets dos 3 repositórios; mergeabilidade dos PRs #13 e #49 | D-09 «exigir PR» valendo para admin |
| S12 | Kan | cartões da IA (PD-1, leitura) | o que foi marcado em 09/11 |
| S13 | — | Phoenix (`ia_obs`) e VPS: **não existem ainda** | viram pós-condição de A4.5 e A4.1 |
| D1 | dono, `!` | `portao.sh --confirmo` (só leitura; compara o env do Coolify com o do kit) | env gravado? |
| D2 | Danilo | `salvo_em` do cookie do RPA; o diálogo de teste existe no ChatGuru? | cookie, A1.1a |

**Alternativa descartada.** O dono rodar tudo com `!`: mais uma pilha de atos pessoais num dia em que os atos dele já são o gargalo (§5), para leituras que o próprio roteiro já entrega ao Claude.

---

## 5. Atos de 09/11 sem registro

**Regra.** Cada ato fica como **desconhecido**, tratado como **não feito até a sonda provar**. Não afirmo que algum foi feito nem que deixou de ser. Rodar de novo o que já rodou é seguro nos kits do gateway: `rotas-ia.sh` usa `ON CONFLICT DO NOTHING` e `env-gateway.sh` reaproveita os segredos (`kits/gateway/README.md` «O que cada script faz»).

| Ato | Prova | Se não foi feito |
|---|---|---|
| `rotas-ia.sh` + `env-gateway.sh --gravar` + vigia de ensaio (N1–N3) | S0, S1, D1 | **hoje, 10/11, depois das 20:30**, com «sim» por kit; volume lido na mesma noite |
| Redeploy de 10/11 05:30 | S2 | **reserva 11/11 05:30** (abaixo) |
| A4.3a (`s4-papeis.sh`, «sim», `s4-hba.sh`) | S8 | 11/11 13:15, depois do lote da revisão sobre o kit `s4` (é a S4 de produção); queda 12/11 13:15. Folga até a A4.6 de 13/11 |
| A3.8 (`zz-ensaio-ui`) | S6 | 12/11 13:15; segura a B6.2 e o #6 |
| Cookie do RPA (Danilo) | D2 | hoje à noite; sem ele A2.4, A3.3 e a B1.6 ficam sem leitura |
| Chat de teste + 13 perguntas ao ChatGuru + pergunta 4 à FACTA | palavra do dono, D2 | **hoje até 18:00. É o item pessoal mais crítico:** sem chat de teste a A3.0 não roda em 11/11 nem pela queda E-12, e o segundo dia perdido acaba com o piloto real |
| A1.3 titular, e-mail de função, cartão (limite 10/11) | palavra do dono | hoje; segura VPS e Fireworks |
| Ata A1.10 (limite 10/11) | palavra do dono | hoje à noite. O item P5 do portão é «`ata`» (`kits/gateway/README.md` tabela «Portão»): sem ele o Redeploy de 11/11 não tem portão aberto |
| D-09 «exigir PR» (10/11 12:00) | S11 | hoje; até lá, nenhum merge em `gl-gateway` nem `facta-on` fora de janela |
| A1.5 VPS (limite 12/11 14:00) | palavra do dono | sem VPS em 12/11, o orquestrador roda em dev até o #8 (`ROTEIRO-DE-ACAO.md:1303`) |
| Leituras do Claude de 09/11 (`pgbackrest info`, `df`, volume, A2.8, A2.12 a–c) | — | entram no lote de sondas de hoje (S3, S5, S7) |

### Reserva de 11/11 05:30

1. **Até 18:00 de hoje:** o lote da revisão sobre o kit de produção do gateway sai primeiro (§6). CRÍTICO ou ALTO no caminho N1–J7 segura a janela.
2. **20:30:** N1, N2 e N3, na ordem do README. No N3, sair 1 é o esperado e só podem falhar os 4 tokens novos, as 2 linhas de boot e a de rotas carregadas (`kits/gateway/README.md` «Como ler o N3»). Qualquer outra falha ⇒ item 5.
3. **Nomes e datas do kit estão velhos (F7):** no J3 o arquivo é `imagem-no-ar-1111.txt`; onde o README diz 05/11 e 06/11, leia 11/11. É achado de papel para a revisão; não mexo no kit.
4. **05:30:** J1–J7. O Danilo clica Redeploy uma vez, nunca Restart. Nenhum merge no `gl-gateway` durante a janela. 08:30: A3.0 (workflow, `ativar-sumidouro.sh`, vigia `--com-sumidouro`) e A3.0–A3.3.
5. **Se o ensaio da noite falhar ou o portão de 11/11 fechar:** não há Redeploy, e a A3.0 roda em 11/11 08:30 pela **queda E-12**, para o canal não perder o segundo dia.

### Linha E-12 (`zz-sumidouro-e12`)

- **Só como queda** (D-04, `ROTEIRO-DE-ACAO.md:1463`). Não uso hoje para adiantar a A3: o ganho é de meio dia, o custo é um token existente num diálogo de teste e mais um ato do dono no dia mais cheio.
- Se usada: só `INSERT`, sem reinício, vale em 30 s. O workflow «IA · sumidouro» precisa estar importado e ativo antes; a vigia trata a linha como rota antiga (`kits/gateway/e12-sumidouro.sh:14`), então erro nela reprova a vigia do Redeploy.
- **Sai no mesmo dia do Redeploy**, com `--apagar`, depois de o diálogo passar para `/ia-sumidouro`. `desfazer.sh --rotas` não a alcança (`e12-sumidouro.sh:15`).
- O corpo dos Posts fica 7 dias em `gateway.payloads`, só de chats da TI: entra no livro de retenção (RS-06).
- **Não decido:** a `ORIGEM_E12` («Sem padrão: quem escolhe é o dono», `e12-sumidouro.sh:10`) e uma **segunda** janela de Redeploy. O roteiro só prevê a reserva de 11/11. Se ela cair, proponho qui 12/11 05:30 (o dia de menor volume medido foi uma quinta), mas é janela nova de reinício em produção e pede o «sim» do dono.

---

## 6. Ordem de ataque: 10, 11 e 12/11

**Ter 10/11**
1. Pedido único ao dono, com a lista fechada do §5 e do §7 (a sessão principal envia; uma mensagem só).
2. 12:30–14:00: lote de sondas S0–S12; a tabela «estado dos atos» da Fase 0 sai com prova.
3. Revisão: fechar a Fase 0 (portão de PII). Na Fase 2, **os kits primeiro**: gateway produção → `s4` → o resto, porque rodam hoje à noite e amanhã. Fase 1 (papel) em paralelo; leitores leves.
4. Construção: 1 agente em B1.6b; o 2º quando o portão de memória abrir.
5. 18:00: checkpoint 0, com a contagem real e X7 levado ao dono (§2).
6. 20:30: N1–N3, volume, cookie, ata P5, quem clica às 05:30.

**Qua 11/11**
1. 05:30 Redeploy (reserva) ou queda E-12. 08:30: A3.0–A3.3.
2. 08:00: construção sobe a 4 agentes, se o portão abrir.
3. Revisão: Fase 2 (código) e 2b (costuras); Fase 3 por lote, logo depois de cada um.
4. 13:15: A4.3a, se a revisão do kit `s4` não trouxe CRÍTICO/ALTO. À noite: A4.2/A4.3b, só com VPS.
5. Dono: 1º lote de textos; nomes do substituto e do revisor.
6. 18:00: checkpoint 0b (≥ 4 agentes?) e checkpoint 1 parcial (existe Post por mensagem?).

**Qui 12/11**
1. 12:30 web #3 (B4.2), se construído e revisado; 13:15 A3.8; 14:00 limite da VPS.
2. Danilo: A3.4–A3.7. Dono: e-mails da semente.
3. Revisão: Fase 3 do código, Fase 4 (rodada 1), início da Fase 5. Meta da síntese: 13/11 de manhã (HIPÓTESE; nenhuma fase tem custo medido).
4. Construção: 5º agente, se couber; B1.7 mirando a tag `v0.3.0` em 13/11.
5. À noite: A4.4, só com VPS.

Os CRÍTICO/ALTO já verificados vão ao dono no dia em que saem, sem esperar a síntese.

---

## 7. O que **não** é delegável (continua exigindo o próprio dono)

**Atos pessoais e pagamentos**
- A1.3 (titular, e-mail de função, cartão em dólar); A1.5 (contratar a VPS); A1.4 (conta e chave Fireworks, US$ 100, em arquivo 0600).
- Marcar o chat de teste; enviar as 13 perguntas ao ChatGuru e a pergunta 4 à FACTA.
- Ata dos padrões A1.10, incluindo o item P5 do portão.
- D-09 «exigir PR» nos 3 repositórios.
- Nomes do substituto do Danilo e do consultor sênior revisor; e-mails da semente.
- A1.11 (ciência do superior, agora com 27–30/11); assinatura do aceite do provedor (E-3).
- Cookie do RPA: é do Danilo.

**«Sim» por kit de produção (PD-2, `ROTEIRO-DE-ACAO.md:427`)**
- Todo `!`: `rotas-ia.sh`, `env-gateway.sh --gravar`, o clique do Redeploy, `s4-papeis.sh`, `s4-hba.sh`, A4.2, A4.4, A4.6 (com «sim» nomeado à 0005), retenção do pgBackRest, importações no n8n, `ativar.sh`, chave AES de dezembro, tags para a VPS.
- Todo merge em `gl-gateway` e `facta-on` (merge é deploy).
- A `ORIGEM_E12` e qualquer janela de Redeploy além da reserva de 11/11.
- As datas do §1b e do §5 são proposta de agenda; nenhuma vale como «sim».

**Aceites e decisões de produto**
- Aceite de G2 (com a prova de 14 d de D-32); go/no-go por escrito; esticar o piloto até 02/12; a rampa do piloto de 4 dias.
- Regra X7, alternativa (c): revoga a alínea (ae), só por resposta escrita.
- C8b (domingo real de 29/11).
- Aceites de risco que a revisão levantar: o limite declarado de `mascara.py` contra a regra 2 (RS-03), «custo e latência não medidos», e os 20 «AJUSTAR» (E-23) que mudem data ou escopo.
- D20, D3, M-7 e R-03 (`RETOMAR-0911.md` «Pendências abertas») não foram pedidas aqui e seguem abertas.

**Textos**
- Aprovação do 1º lote (11/11) e do 2º lote (13/11), com o TX-42; o texto do aviso aos consultores.

## 8. Limites desta decisão

- Não li produção, Kan, memória por dentro nem as pastas proibidas. As contas de r são HIPÓTESE, como no roteiro.
- F6 é uma leitura única, às 09:03. O portão do §2 manda medir de novo antes de cada subida.
- O mapa do §1b desloca um dia útil por inferência minha a partir de `ROTEIRO-DE-ACAO.md:1290` e `:1293`; as dependências finas (A4.4 antes de B6.8, #4 antes de #7) precisam da conferência da sessão principal antes de irem ao roteiro.
