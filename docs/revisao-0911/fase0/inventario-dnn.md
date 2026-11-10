# Inventário das 32 decisões D-nn e dos 20 «AJUSTAR» — revisão 0911, fase 0

> Só leitura, feita em 10/11/2026. Nada foi executado, editado ou lido em produção. Sem PII e sem credencial.
> A classificação de estado é juízo deste agente (Fable 5.2) sobre o que está escrito; nenhuma decisão do dono foi escolhida ou alterada aqui.

## 0. Como ler

**Fontes e siglas** (números de linha são dos arquivos como estavam em 10/11; a âncora de texto entre «» é o que vale):

| Sigla | Arquivo |
|---|---|
| RG | `/opt/claude/docs/planejamento-ia/estudos/REVISAO-GERAL-0411.md` (§C em 727–787; §H em 1002–1021) |
| PAR | `/opt/claude/docs/planejamento-ia/estudos/PARECER-CODEX-32-DECISOES-0411.md` |
| REP | `/opt/claude/docs/planejamento-ia/estudos/REPLANEJAMENTO-INICIO-0911.md` |
| RET | `/opt/claude/docs/planejamento-ia/RETOMAR-0911.md` |
| PLN | `/opt/claude/docs/planejamento-ia/estudos/PLANO-REVISAO-0911.md` |
| ROT | `/opt/claude/docs/planejamento-ia/ROTEIRO-DE-ACAO.md` v3.3 |
| 01, 03, 04, 07, 08, PD | `/opt/claude/docs/planejamento-ia/contratos/` (01 v2.5, 03 v2.2, 04 v2.2, 07 v2.2, 08 v2.4, `PARA-O-DONO.md`) |
| MEM | `/home/danilo/.claude/projects/-opt-claude/memory/decisoes-dono-03-11-recomendacoes.md` |
| EST | `/home/danilo/.claude/projects/-opt-claude/memory/ia-roteiro-estado.md` |
| MAN | `/home/danilo/ia-revisao-0911/fase0/MANIFESTO.md` |
| código | `/home/danilo/ia-revisao-0911/src/<repo>/…` (SHAs do MAN); kits em `/home/danilo/ia-revisao-0911/kits/` |

**Camadas de decisão, da mais antiga à última:**

| Camada | O que é | Fonte |
|---|---|---|
| C0 | Recomendação original («padrão se calar») de 03/11 | RG §C, 733–764 |
| C1 | Dono, 03/11 noite: «Segue recomendações e atualiza o artefato…», mais D-18 e D-29 diretas | RG 1004–1010; MEM 8 |
| C2 | Parecer do Codex, 04/11 (não é o dono: 8 CONCORDO, 20 AJUSTAR, 4 DISCORDO) | PAR 9–42 |
| C3 | Dono, 04/11 ~11h: «segue recomendações suas» + 5 respostas | MEM 19–24; ROT 7, 108–117 |
| C4 | Dono, 04/11 tarde: «segue suas recomendações» (cenário C e respostas) | MEM 35–42; ROT 3, 151–163 |
| C5 | Contratos emendados em 04/11 e revisão PD-5 | ROT 4, 1717, 1718 |

**Estados:**
- **com prova**: a decisão vigente está em código na `origin/main` do SHA do MAN, ou é ato registrado com SHA.
- **só no papel**: decidida e refletida em roteiro ou contrato, sem código nem ato.
- **aberta**: falta ato ou resposta do dono, ou o texto ainda não cumpre a decisão.
- **superada**: uma camada posterior trocou a decisão.

**Limite desta leitura:** PLN 8 diz que nenhum ato de 09/11 tem registro e que «sem registro» não é prova de «não feito». Não li produção, Kan nem painel. Onde digo «sem registro», é isso.

## 1. Placar

| Estado | Qtde | D-nn |
|---|---:|---|
| com prova | 4 | D-06, D-18, D-22, D-23 |
| com prova parcial | 1 | D-29 |
| só no papel | 15 | D-04, D-05, D-08, D-10, D-12, D-13, D-14, D-15, D-20, D-21, D-25, D-26, D-27, D-30, D-31 |
| aberta | 10 | D-01, D-02, D-03, D-07, D-09, D-11, D-16, D-17, D-19, D-32 |
| superada | 2 | D-24, D-28 |

Dos 20 AJUSTAR: 3 adotados, 1 adotado e superado, 3 superados com resíduo, 2 parciais, 11 abertos (§3).

Vencem hoje ou amanhã, segundo o próprio roteiro: A1.3 e a ata A1.10 (10/11), a proteção da `main` (10/11 12:00), o primeiro lote de textos e os nomes de substituto e revisor (11/11) — ROT 139, 144, 145, 126.

## 2. As 32 D-nn

Cada linha traz: pergunta · recomendação original (C0) · respostas por camada · decisão vigente · onde está · estado.

### D-01 a D-08

| D | Pergunta | C0 (RG) | Camadas seguintes | Vigente na última camada | Onde está refletida | Estado |
|---|---|---|---|---|---|---|
| D-01 | Titular, e-mail de função e cartão; chave Fireworks: que dia? | Sem padrão; A1.3 até 06/11, chave até 12/11 (RG 733) | C1: pendente do dono (RG 1010). C2: AJUSTAR. C3: «Sim, amanhã te passo tudo», cartão 06/11 e chave 09/11 (MEM 21). C4: pedido único em 09/11 (MEM 36, 42) | A1.3 até 10/11; chave até 17/11; sem chave, a F3 roda só I1–I9 com `ProvedorFalso` e o go/no-go registra a falta | ROT 139 «A1.3 até 10/11; chave até 17/11»; ROT 289 «sem chave até 17/11: B8.2 só I1–I9»; ROT 1165 «custo/latência não medidos» | **aberta** (ato do dono, sem registro) |
| D-02 | VPS OVH: que dia? | Sem padrão; 06/11 (RG 734) | C1: pendente. C2: CONCORDO. C3: até 06/11 (MEM 21). C4: cenário C | VPS contratada até 12/11 14:00; «sim» ao `s4-hba.sh` em 09/11 13:15 | ROT 140; ROT 290 «VPS contratada até 12/11 14:00» | **aberta** (ato do dono, sem registro) |
| D-03 | Chat de teste e perguntas ao ChatGuru | Padrões da tabela de A1.1 (RG 735) | C1: pendente. C2: AJUSTAR. C3: dono pediu explicação sobre o RPA (MEM 23). C4: RPA «sim, só se não houver webhook por mensagem» (MEM 38) | Chat de teste e 13 perguntas em 09/11; RPA como leitor só se A3.1 = «não» | ROT 141; ROT 285 «pendente do dono: 09/11»; ROT 147, 157; ROT 1470 (E-19) | **aberta** (ato do dono, sem registro) |
| D-04 | Reinício único do gateway sem esperar a VPS | Sem padrão: são `!` do dono (RG 736) | C1: adotado, 05/11 05:30. C2: CONCORDO. C4: cenário C | Ter 10/11 05:30, reserva qua 11/11; rotas e env na noite de 09/11; E-12 só como queda | ROT 121; ROT 385; ROT 174; 01:294 «Ordem real (v2.4, D-04, RG-043)»; `kits/gateway/README.md:171` «Passo a passo (D-04; contrato 01 §9)» | **só no papel** (kit existe; execução sem registro) |
| D-05 | Adotar C9 já? | (a) C9; sombra de 4 dias; agenda no MVP (RG 737) | C1: adotado. C2: AJUSTAR. C4: sombra vira 2,5 dias e sai o caso (b) da agenda | C9 adotado: 5 críticos + ficha, pytest, web só com a chave, ntfy próprio depois do piloto | ROT 122; ROT 1076 «só os 5 críticos»; ROT 1319; ROT 1459 (E-8); 07:167 «sem seletor de `modo`» | **só no papel** (B6.6 e B7.1 sem código; PLN 19) |
| D-06 | Autoriza os merges #10, #6, #7, #8, #9 e bancos-duble #2? | Sem padrão: palavra do dono (RG 738) | C1: esperam «merge #6» (RG 1010). C2: AJUSTAR. Dono fez em 03/11 22:27 BRT (EST 32); depois #11, #12, #14 e bancos-duble #3, #5 (EST 34, 44) | Feito. `ia-atendimento` main `9a4bacab`, `bancos-duble` main `ca3ed2cf` | ROT 142 «Feito pelo dono (v3.3)»; ROT 1713; MAN 3–4 (pontas remotas iguais às locais); `kits/merge-d06/merge-d06.sh:2`; `ia-atendimento/migrations/0004_anexo_rpa_e_espelho.up.sql` e `0005_domingo_por_config.up.sql` presentes na exportação | **com prova** (resta o PR #13, B1.6a, sem merge: RET 12) |
| D-07 | Cookie do RPA: quem renova e quando | Sem padrão (RG 739) | C1: pendente. C2: CONCORDO. C4: cenário C | Danilo renova em 09/11 à noite com `salvo_em`; 2ª renovação em 19/11 | ROT 143; ROT 298 | **aberta** (ato, sem registro) |
| D-08 | Regra `allow` de diretório para os kits | `!` sempre (RG 740) | C1: adotado. C2: AJUSTAR | `!` sempre; as duas regras de diretório seguem pedidas ao dono | ROT 123; ROT 1732 «cobrar antes de … 09/11, D-08» | **só no papel** |

### D-09 a D-16

| D | Pergunta | C0 (RG) | Camadas seguintes | Vigente na última camada | Onde está refletida | Estado |
|---|---|---|---|---|---|---|
| D-09 | Proteger a `main` de 3 repositórios e aceitar «merge = deploy» com regras | Regra (a) vale por silêncio; a proteção é ação do dono (RG 741) | C1: regra adotada. C2: AJUSTAR. C4: data nova | Regra (a) vale; proteção até 10/11 12:00, antes do primeiro merge do `facta-on` (12/11) | ROT 45 «a proteção da `main` é ação do dono, **pendente**»; ROT 124, 144; ROT 1264; ROT 1467 (E-16) | **aberta**. PLN 11 relata um ruleset de organização de 04/11 que barra exclusão e force-push; falta «exigir PR valendo para admin». Não reconferi |
| D-10 | «Ok» ao desenho mínimo K (devolução de leads) | Ok por silêncio em 06/11 12:00 (RG 742) | C1: adotado. C2: DISCORDO. C3: não vale por silêncio (MEM 20). C4: «ok» dado (MEM 38) | «Ok» dado; B6.4 segue para o deploy #6 de 16/11; DDL na S2 só por `!` | ROT 88; ROT 113 «(v3.3, dono 04/11), tarde: **«ok» dado**»; ROT 146, 156; ROT 1062 | **só no papel** (B6.4 sem código; regra R-c2 aberta: ROT 1066) |
| D-11 | Textos: reemissão e aprovação em dois lotes | Marcadores do estudo; sem aprovação o piloto não liga (RG 743) | C1: adotado. C2: AJUSTAR. C4: lotes novos | Reemissão com as emendas do N e TX-42; lotes em 11/11 e 13/11 | ROT 126; ROT 236; ROT 349; ROT 812 | **aberta**. `textos/TEXTOS-PARA-APROVACAO.md:3` ainda é a «Versão 1, gerada em 30/10/2026»; busca por «TX-42», «saudacao» e «TX-01T» no arquivo: vazia. PLN 166 confirma: reemissão pendente |
| D-12 | As 5 respostas do estudo N | H-Q4 «não»; a IA abre «surda» (RG 744) | C1: N-1 «sim, mínima» foi assumido (ROT 1575). C2: AJUSTAR. C3: N-1 «Sim» do dono (MEM 22) | N-1 sim (1 fala pendente mascarada); N-2 sem lembrete no comercial; N-3 TX-25; N-4 só dentro de 24 h; N-5 sim | ROT 114; ROT 127; ROT 237 «H-Q4 «não» (G0) **superado por N-1**»; ROT 997 (N-4) | **só no papel**. `ia-atendimento/src/ia_atendimento/contexto.py:79-80` tem `ultimo_sentido` e `tipo_ultima_fala`; a leitura da fala pendente não foi localizada |
| D-13 | Janela de 24 h sem a hora do cliente: `espera` ou `proxy`? | `espera` (RG 745) | C1: adotado. C2: CONCORDO | `espera`; A2.4 mede parse e fuso em 10/11 | ROT 128; ROT 1466 (E-15); PD 18–21 | **só no papel**, com parte em código: `ia-atendimento/src/ia_atendimento/api/atendimentos.py:89-93` e `api/contexto.py:104`. A regra no `iniciar` é da B1.6; A2.4 sem registro |
| D-14 | Repasse: «até 30» são tentativas ou minutos? | 30 tentativas, ≈ 2 h 11 (RG 746) | C1: adotado. C2: DISCORDO. C3: 30 minutos (MEM 20). C4: «sim» às emendas (MEM 40). C5: aplicado | Espera total ≤ 30 min; crítico e recuperação humana aos 10 min; aos 30 min o orquestrador para | ROT 110; ROT 235; PD 10 «Resposta: `30min` (D-14)»; 01:216; 04:338; 08:244; 08:364 (teste novo); 08:478 | **só no papel**. Busca por `repasse_travado`, `espera_total` e afins em `ia-atendimento/src` e em `ia-atendimento-b1-6a/src`: vazia. B1.6b não começou (PLN 14) |
| D-15 | E-9 (batimento ausente ⇒ agir com alerta) e E-11 (três cortes) | Aceitos por padrão (RG 747) | C1: adotado. C2: DISCORDO. C3: fail-closed (MEM 20). C5: aplicado | Sem batimento recente (> 90 s) a IA não age; a vigia continua devolvendo; E-11 (1)(2)(3) aceitos | ROT 111; ROT 517; ROT 1417; ROT 1460 (E-9); ROT 1462 (E-11); 04:385; 04:446; 08:224; 08:261; 01:377 | **só no papel**. Busca por `batimento.json` e `impedidos` no código: vazia. `ferramentas/modo.py:4` cita D-15 para outra regra (modo desconhecido vale `sombra`) |
| D-16 | Sem jurídico: política publicada do provedor + aceite escrito bastam? | Sim (RG 748) | C1: adotado. C2: AJUSTAR | Política publicada + aceite escrito do dono; assinatura até 13/11 | ROT 128; ROT 487; ROT 1453–1454 «**Pendente, ato do dono:** assinar o aceite»; ROT 1165 | **aberta** (assinatura) |

### D-17 a D-24

| D | Pergunta | C0 (RG) | Camadas seguintes | Vigente na última camada | Onde está refletida | Estado |
|---|---|---|---|---|---|---|
| D-17 | Pessoas, celulares e semente de operadores | Celulares dono + Danilo; revisor Danilo; coordenação dono; sem substituto o piloto para no dia (RG 749) | C1: pendente. C2: AJUSTAR. C3: dono pediu explicação (MEM 23). C4: Danilo opera, dono no 2º celular (MEM 39) | Papéis respondidos; faltam os nomes do substituto e do revisor (até 11/11) e os e-mails da semente (até 12/11) | ROT 145; ROT 158; ROT 292; ROT 498; ROT 1457 (E-6) | **aberta** |
| D-18 | Domingo fica para a fase 2? | Sim, fase 2 (RG 750) | C1: dono, literal: «não, IA no domingo deve estar incluso também» (RG 1007). C2: AJUSTAR. C4: P1 e P2 refeitos pelo cenário C. C5: aplicado | Domingo no MVP, fechado por padrão, aberto só com duas chaves; migração 0005 com «sim» nomeado; 15/11 em dev; domingo real em 29/11 (dia 4, ≤ 10) | ROT 104–105; ROT 1468 (E-17); 08:56; 08:349; 04:178; 07:106; 03:211. Código: `ia-atendimento/migrations/0005_domingo_por_config.up.sql:1-10`; `src/ia_atendimento/calendario.py:58-63`; `agenda_extrator.py:101` | **com prova** no código. Pendente: a 0005 «Ainda não aplicada em lugar nenhum» (`0005…sql:5`); `config/domingo.sh` é «A escrever» (ROT 1732); TX-42 fora do arquivo de textos; pergunta 4 à FACTA sem registro |
| D-19 | Corpo do `ia-agendar` sem gravação + ensaio; importação de `zz-ensaio-ui` | `saveData*: none` + ensaio (RG 751) | C1: adotado, 06/11. C2: AJUSTAR. C4: 09/11 12:30; o caso (b) sai do MVP | Importação por `!` em 09/11 12:30; ensaios S1–S6 como primeiro ato de B6.2 | ROT 129; ROT 321; ROT 683–685; ROT 1048; PD 42 «Sem objeto no piloto»; 04:429 | **aberta** (ato sem registro; o kit «não existe hoje», ROT 684) |
| D-20 | M-05 em três estados e M-06 com lista estreita | Opção A nos dois (RG 752) | C1: adotado. C2: CONCORDO | A nos dois; `indeterminado` vai ao T8 e nunca reenvia | ROT 130; ROT 1465 (E-14); PD 43. Código: `ia-atendimento/src/ia_atendimento/ferramentas/esquemas.py:164-171` | **só no papel**; o esquema já traz `indeterminado`, a digitação (B5.4) não existe; M-06 sem contagem |
| D-21 | Comissão: R$ 100 por pago / 4 % | Sim, como proxy (RG 753) | C1: adotado. C2: AJUSTAR | R$ 100 / 4 % como proxy de outubro | ROT 130; ROT 309 «comissão R$ 100 / 4 % (D-21)» e «**aplicada em 03/11 19:18**» | **só no papel** (não reli `premissas.json` nem o painel) |
| D-22 | `ia_ativa=false` devolve também os pausados? | Sim, (a); à noite a vigia grava `bloqueio_entrada` (RG 754) | C1: adotado. C2: AJUSTAR | (a); 19:45 e 20:15 não devolvem `pausado` | ROT 130; ROT 523; ROT 1063 «**R-a** … devolve todos os `aberto` **e `pausado`**»; ROT 1081. Código: `ia-atendimento/src/ia_atendimento/jobs.py:42-43`; `chave.py:7`; `fila.py:130-132` | **com prova** no orquestrador; a vigia (B6.4) não existe |
| D-23 | A regra «sem trigger em tabela nova» vale para o banco da IA? | Não: o trigger da 0003 fica (RG 755) | C1: adotado. C2: CONCORDO | O trigger fica; DROP só com «sim» | ROT 130. Código: `ia-atendimento/migrations/0003_estado_aditivo.up.sql:4` e `:27` | **com prova** no código; aplicação na S4 espera a A4.6 (13/11) |
| D-24 | Rotação das 2 chaves expostas: agora ou depois do piloto? | Rotacionar em 06/11; uma lente preferia adiar (RG 756) | C1: rotacionar. C2: AJUSTAR. C4: depois do piloto (REP 287) | Depois do piloto, a partir de 02/12, numa noite sem deploy | ROT 131 «**rotacionar depois do piloto, a partir de 02/12**»; ROT 293; ROT 1732 (`rotacao/inapp-chave.sh` «A escrever») | **superada** (a rotação de 06/11); a vigente está só no papel e o kit não existe |

### D-25 a D-32

| D | Pergunta | C0 (RG) | Camadas seguintes | Vigente na última camada | Onde está refletida | Estado |
|---|---|---|---|---|---|---|
| D-25 | «Ok» do superior ao piloto | Silêncio = segue (RG 757) | C1: adotado. C2: AJUSTAR. C3: «ok» ambíguo (MEM 23). C4: basta a ciência (MEM 39) | Basta a ciência; o dono apresenta até 13/11 com as datas de 26–30/11 | ROT 66; ROT 132; ROT 148, 159; ROT 527; ROT 1472 (E-21) | **só no papel** (falta o ato de apresentar) |
| D-26 | Colheita na S2 e contagem do M-06 | Dublê sintético; lacuna como risco aceito (RG 758) | C1: adotado. C2: AJUSTAR | Padrão mantido; colheita possível a partir de 09/11, antes do deploy #5 | ROT 132; ROT 344 «colheita real: **sem registro de execução**» | **só no papel**. Busca por `tap_retorno_dia` em `facta-on/app`: vazia (o tap não está na main; PLN 12) |
| D-27 | Telefone em claro no espelho da S2 | Como está (RG 759) | C1: adotado. C2: AJUSTAR | Como está: `chat_number` em claro, 30 dias, sem sair da S2 | ROT 132; ROT 1063 «`chat_number` (30 d, nunca sai da S2)» | **só no papel** |
| D-28 | Caso (b) do «Vou fazer Depois»: degrau ou corte? | Degrau: `agenda_b_digita=false`, aviso + repasse (RG 760) | C1: adotado. C2: CONCORDO. C4: caso (b) fora do MVP (MEM 36) | Fora do MVP; sai o fluxo n8n «IA · agendar» e a parte (b) de B5.7c | ROT 132 «**caso (b) fora do MVP**»; ROT 154; PD 37; 04:429. Código: `ia-atendimento/src/ia_atendimento/chave_registro.py:381`; `api/agendamentos.py:28` e `:90-92` | **superada** pelo corte do cenário C; a rota `/agendamentos` existe e fica sem uso |
| D-29 | A IA lê a ficha completa (T2) do 360? | Não (RG 761) | C1: dono, literal: «Só o essencial para dar continuidade à contratação.» (RG 1008). C2: AJUSTAR. C5: aplicado | Só `pessoas:resumos` e `pessoas:propostas` com allowlist; sem escopo novo; a `matricula` vem do braço n8n para o cofre | ROT 106; ROT 227; ROT 755; ROT 1469 (E-18); 03:5; 03:201; 04:91; 04:493; 08:45; 08:97. Código: `ia-atendimento/src/ia_atendimento/ferramentas/esquemas.py:108` e `:125` | **com prova parcial**: a allowlist de T1 e T3 está no código; `matricula` em `api/` e `cofre.py`: busca vazia; `000025` e `ia:chave` em `cliente360-api`: busca vazia |
| D-30 | Phoenix só por túnel SSH | Padrão anterior era Access; a revisão propôs o túnel (RG 762) | C1: adotado. C2: CONCORDO | Só por túnel no tailnet, sem Access nem hostname | ROT 133; ROT 231; ROT 291; ROT 493; ROT 1363; 03:206; 07:178. Código: `ia-atendimento-esteira/docker-compose.yml:48`; `docs/DEPLOY.md:86` | **só no papel** (`feat/esteira` sem cópia remota: MAN 32; a VPS não existe) |
| D-31 | Corpus bruto: guardar ou apagar? | Apagar quando existir o derivado e os estudos fecharem (RG 763) | C1: adotado. C2: AJUSTAR | Apagar no gatilho por estado; sem data | ROT 133 «apagar o corpus bruto no gatilho por estado» | **só no papel** (não li a pasta do corpus) |
| D-32 | «Sim» às emendas da v3.3 | Sem padrão (RG 764) | C1: v3.3 aplicada em arquivo. C2: DISCORDO. C3: Gemini só como contingência; prova de eliminação em 14 dias antes de G2 (MEM 20). C4: «sim» às emendas dos contratos (MEM 40). C5: aplicadas, PD-5 feita | v3.3 e contratos vigentes; Gemini condicional; G2 (18/11) exige a prova de 14 dias | ROT 5–6; ROT 112; ROT 43; ROT 134; ROT 736; ROT 1455 (E-4); ROT 1572; ROT 1717–1718 | **aberta** na prova de 14 dias (`pgbackrest info` de 09/11 sem registro); o texto está aplicado. Código aceita `gemini-*`: `ia-atendimento/src/ia_atendimento/config.py:205-207` |

## 3. Os 20 «AJUSTAR» do parecer

ROT 100 e ROT 1474 (E-23) dizem que os 20 «não foram adotados em bloco» e seguem pendentes; RET 43 repete. O estado abaixo é item a item.

| D | O que o parecer pede (PAR) | Estado | Onde |
|---|---|---|---|
| D-01 | Chave em 09/11; nenhum piloto sem A2.9a e F3 com o modelo real (PAR 11) | **superado com resíduo**: 09/11 foi adotado em C3 e trocado por 17/11 em C4; a trava do modelo real **não** foi adotada | ROT 115; ROT 289; ROT 1165; PLN 166 «O padrão vigente aceita «custo e latência não medidos»» |
| D-03 | «Ok» específico ao RPA leitor; retentativas tratadas como hipótese (PAR 13) | **parcial**: o «ok» foi dado; a tabela de padrões ainda traz «3× em ~6 s» | ROT 147, 157; ROT 454 «3× em ~6 s; lock por chat»; ROT 1638 |
| D-05 | Kit pronto de parada dura; lista única de alertas a provar (PAR 15) | **aberto** | Nenhum kit de parada em `kits/`; ROT 1165 «nos 5 tipos» × ROT 1076 (5 críticos mais o alerta do cookie) |
| D-06 | Sincronizar os resumos com os merges feitos (PAR 16) | **adotado** no roteiro; RG §H não foi reescrita (declarado em RG 1021) | ROT 142; ROT 1713; RG 1010 |
| D-08 | Limitar `allow` a leitura e ensaio (PAR 18) | **aberto** | ROT 1732 segue pedindo as duas regras de diretório |
| D-09 | Proteção antes do próximo merge que publica; revisão e portão anexos ao kit (PAR 19) | **aberto** | ROT 144 «só a regra (a) vale» se a proteção não vier |
| D-11 | `{{saudacao}}` na lista de placeholders; TX-42 no primeiro lote (PAR 21) | **aberto**: TX-42 está marcado para 11/11, mas a reemissão não existe | ROT 105 (P5); `textos/TEXTOS-PARA-APROVACAO.md:3` |
| D-12 | Pergunta explícita sobre N-1 (PAR 22) | **adotado** | MEM 22; ROT 114 |
| D-16 | Arquivar versão e data da política; assinar antes de G2; barrar texto real sem comprovação (PAR 26) | **aberto** | ROT 1454 |
| D-17 | Titular e substituto treinados; revisor distinto; amostra revisada antes do go (PAR 27) | **parcial**: papéis respondidos; os dois turnos de 15/11 saíram (ensaio em dev); revisor distinto e amostra obrigatória abertos | ROT 158; ROT 198; ROT 498 |
| D-18 | 0005 antes da imagem; ensaio de feriado só em teste; sequência única no calendário (PAR 28) | **adotado e superado**: 0005 antes da imagem; 15/11 virou ensaio em dev; a sequência é o cenário C | 08:291; ROT 198; ROT 165–207 |
| D-19 | Provar ausência de corpo gravado; tirar a saída «guardar por um dia» (PAR 29) | **superado com resíduo**: o caso (b) saiu; a saída de um dia continua no roteiro | PD 42; ROT 685 «`retencao` 1 d (`!`)» |
| D-21 | R$ 100 como parâmetro único; refazer ou tirar as faixas de 1–3 % (PAR 31) | **aberto** (não reli o painel) | ROT 309 |
| D-22 | Incluir `pausado` na guarda da devolução; ensaio da corrida (PAR 32) | **aberto** | ROT 1063: R-a devolve `pausado`, e o CAS do mesmo parágrafo é «`WHERE chave=? AND estado='aberto'`» |
| D-24 | Kits antes da janela; revogar a 2ª chave; não chamar desativação de rotação (PAR 34) | **superado com resíduo**: a rotação foi para depois do piloto; o conteúdo segue sem resposta | ROT 131; ROT 1732 |
| D-25 | Regra única sobre a alçada do superior (PAR 35) | **adotado** | ROT 159; ROT 1472 |
| D-26 | Comparação com o tap e contagem do M-06 antes do go (PAR 36) | **aberto** | ROT 931 prevê a comparação; ROT 1165 não a exige |
| D-27 | Cifrar o telefone na S2 e apagá-lo ao fechar (PAR 37) | **aberto** | ROT 132 «D-27 como está» |
| D-29 | Recusar CPF por forma em identificadores; provar H1–H3 antes do real (PAR 39) | **aberto** | 08:97 (o padrão da `matricula` aceita 11 dígitos); 04:500 (a guarda V-28 só compara com o CPF do job); ROT 1469 «Falta medição agregada (H1–H3)» |
| D-31 | Prazo, responsável e inventário de cópias do corpus (PAR 41) | **aberto** | ROT 133 |

Os 4 DISCORDO (D-10, D-14, D-15, D-32) foram adotados em C3; os 8 CONCORDO (D-02, D-04, D-07, D-13, D-20, D-23, D-28, D-30) não pediam mudança.

## 4. Contradições entre camadas

Ordenadas pelo que pode causar dano primeiro.

1. **Devolução sem venda: três versões no mesmo roteiro.** De manhã (C3) o roteiro registrou «rodízio» como destino; à tarde (C4, E-24) o dono manteve D3 e o lead volta ao mesmo consultor. ROT 1475 diz que «`consultor_antes` não é nulo no fluxo principal». ROT 1063 ainda descreve «`consultor_antes` nulo, o fluxo principal com o lead no Amado ⇒ devolve ao **rodízio**», e ROT 388 e ROT 116 trazem as duas frases em sequência. Vale E-24 (ROT 155) e os contratos (01:7, 04:5); a Spec da B6.4 pode ser lida pelo texto velho.
2. **D-11: o roteiro dá os textos como reemitidos.** ROT 126 diz «Textos reemitidos em 05/11 (só arquivo)»; o arquivo é a versão de 30/10, sem TX-42. O primeiro lote vence em 11/11, e G3 depende dele.
3. **D-01: a data da chave andou para trás.** 12/11 (C0) → 09/11 (C3, respondendo ao parecer) → 17/11 (C4). O parecer pedia o contrário do que ficou: a última camada aceita o go/no-go sem prova do modelo real (ROT 1165).
4. **D-22: a guarda da devolução contradiz a própria regra.** No mesmo parágrafo (ROT 1063), R-a devolve abertos e pausados e o CAS só troca quem está `aberto`. O parecer apontou; ninguém resolveu.
5. **D-14 e D-15 não existem em código.** Viraram duas vezes (fail-open e 30 tentativas → fail-closed e 30 minutos) e estão em três contratos, mas `ia-atendimento` e a `feat/b1-6a` não têm repasse com teto nem leitura do batimento. Fica aberta a regra da vigia para `repassando` com o n8n fora (ROT 1066; 04:382).
6. **D-04: o kit do gateway ficou na camada de 03/11.** `kits/gateway/README.md:3` cita o contrato 01 «**v2.4**» e as linhas 27, 30, 62 e 142 trazem «noite de 04/11» e «05/11 05:30»; o roteiro e o contrato estão em 09–10/11 e v2.5 (ROT 174; `01-gl-gateway.md:1`).
7. **D-32 apoia-se numa leitura.** MEM 20 marca D-14, D-15, D-32 e D-10 como «Adotado (leitura do Claude)» de «segue recomendações suas». D-14 e D-15 ganharam o «sim» às emendas à tarde (MEM 40) e D-10 o «ok» (MEM 38). Para D-32 (Gemini condicional, prova de 14 dias) não há frase literal do dono. E ROT 43 afirma, na mesma regra, que o texto do Phoenix «sobrevive nos fulls pelo aceite do dono de 30/10» e que é preciso provar a eliminação em 14 dias.
8. **D-19: roteiro e PD divergem.** ROT 685 mantém o gatilho «`retencao` 1 d» se o ensaio mostrar corpo gravado; PD 42 diz «Sem objeto no piloto». Além disso, o roteiro cita «`PD:41`» para a agenda, e hoje a linha 41 do PD é a do gateway (a da agenda é a 42).
9. **D-17: o revisor é opcional num lugar e obrigatório em outro.** ROT 498 diz que sem revisor «cai a métrica de qualidade, não o go/no-go»; ROT 1165 exige no go «amostra ≥ 30 atendimentos … com ≥ 90% OK/leve».
10. **D-09: o roteiro não registra a proteção parcial.** ROT 45 e ROT 144 dizem só «pendente»; PLN 11 relata o ruleset de 04/11.
11. **D-18: o Painel está atrás do código.** ROT 363 traz B1.8 como «não iniciada»; a 0005 e o `calendario.py` estão na main `9a4bacab` (PLN 15 aponta o mesmo para B2.1 e B5.1). ROT 142 e a capa (ROT 5) param na main `6abaf02`.
12. **D-25: aceite com duas redações.** ROT 527 mantém «**Aceite:** «ok» ou «sem objeção» registrado até 13/11» e, logo depois, «o aceite é a ciência registrada».
13. **D-05: cinco ou seis alertas.** ROT 1165 pede prova «nos 5 tipos»; ROT 1076 lista 5 críticos e acrescenta o alerta crítico do cookie do RPA.
14. **Documentos que ficaram numa camada antiga.** RG §H (RG 1010, 1017) ainda diz que os merges esperam e que as emendas dos contratos não foram feitas; o próprio RG 1021 avisa que não foi reescrito. `G0-PEDIDO-AO-DONO.md:33` ainda oferece E-9 como «`batimento` ausente > 60 s ⇒ fala uma vez».
15. **«D-12» tem dois sentidos.** Em 04:55, «tabela D-12 do roteiro» é o risco 12 da Parte D, não a decisão D-12 (ROT 685 explica).

## 5. O que não conferi

- Produção, Kan e painel (`index.html`): nada foi lido.
- `premissas.json` e `custos.csv` (D-21): vale só o que o Painel do roteiro afirma.
- O arquivo `DECISOES-APLICADAS.md`, citado pelo parecer: não existe em `/opt/claude/docs/planejamento-ia/` nem em `/home/danilo/ia-revisao-0911/` (busca por nome, 4 níveis).
- O commit `6abaf02` do D-06: a exportação não tem histórico; a prova é a ponta `9a4bacab` do MAN e os artefatos presentes.
- Buscas «vazias» valem para os caminhos indicados na linha; os scripts estão em `/home/danilo/ia-revisao-0911/scripts/` (`dnn-localizar.sh`, `dnn-linhas.sh`, `dnn-codigo.sh`, `dnn-conferir.sh`, `dnn-conferir2.sh`).
