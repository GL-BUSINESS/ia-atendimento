# Estudo: FGTS ponta a ponta e a negociação via IA

> **Atualizado em 10/11 com a estrutura dos fluxos n8n exportada pelo dono** (`/home/danilo/fgts-estudo/n8n/fluxos-fgts-estrutura.json`; análise em `LEV/lev-n8n.md`). Mudaram §2, §4 e §7; o resto foi mantido (só o caminho literal do webhook do fluxo 2 saiu de §3.3). Os caminhos de webhook dos fluxos são segredo funcional: aqui cada um é citado só como «webhook do fluxo <nome>». Rótulo novo: **FATO-E** = está na estrutura exportada, prova `n8n:<fluxo>/<nó>`. A estrutura não traz condição de IF/Switch, corpo de HTTP nem código: o ramo «sim/não» é **HIPÓTESE pela ordem** das ligações (`LEV/lev-n8n.md` «Limite da estrutura»).
> 10/11/2026, revisado no mesmo dia (ver «Notas da revisão», §10). Só leitura. Pedido do dono (10/11): «assim como tem o serviço do CLT, pesquisa e analogia em cima do produto FGTS, porque vamos começar por ele a negociação via IA; todas as APIs e tudo que é usado no FGTS, do início ao fim; ele tem venda automatizada com chatbot, e a IA só entra **após a falha da negociação via chatbot**».
> Base: levantamentos `LEV/lev-novosaque.md`, `lev-chatbot.md`, `lev-analogia.md`, `lev-regras.md`, `lev-c360.md`, `lev-legado.md`, `lev-outros-bancos.md`. Os pontos decisivos foram conferidos de novo no código (marcados ✔).
> Nada de banco, ssh, docker, n8n de produção, `.env` ou dado de cliente. Nenhum CPF, telefone, e-mail, nome de cliente ou credencial aqui. Aviso: o README do `novosaque-fgts` traz um documento de exemplo num bloco de JSON (perto de `NSR:397`); não foi copiado.
> **Rótulos.** FATO = código ou doc com caminho:linha. MEDIDO = número registrado no código ou README, com a data dele (não remedido). **NÃO VERIFICADO** = depende do n8n de produção (leitura barrada), do ChatGuru ou da Novo Saque. **HIPÓTESE** = inferência sem prova.

**Atalhos.**

| Atalho | Caminho |
|---|---|
| `src/` | `/home/danilo/fgts-estudo/src/` (SHAs em `/home/danilo/fgts-estudo/estudo/MANIFESTO.md`) |
| `NS` | `src/novosaque-fgts/` (`cf6efdd`) |
| `NSR` | `src/novosaque-fgts/README.md` |
| `LEV` | `/home/danilo/fgts-estudo/estudo/` |
| `ENT` | `estudos/ESTUDO-NEGOCIACAO-TABELAS.md` (estudo paralelo, já escrito) |
| `H`, `F`, `C`, `K` | `estudos/semana-1/h-roteiro-conversa-memoria.md`, `f-catalogo-ferramentas.md`, `c-braco-n8n.md`, `k-devolucao-lead-cenarios.md` |
| `RG0911` | `estudos/REVISAO-GERAL-0911.md` |
| `MEM:` | `~/.claude/projects/-opt-claude/memory/` |
| Doc Novo Saque | <https://developers.novosaque.com.br/llms.txt> (índice lido em 10/11/2026) |

---

## 1. Resumo em 10 linhas

1. **O produto:** antecipação do saque-aniversário do FGTS. O cliente cede até 5 aniversários (a queda para 3 foi adiada até 31/03/2027), de R$ 100 a R$ 500 cada, uma antecipação por ano, 90 dias de carência depois da adesão. Teto de juros de 1,80% a.m. só em fonte secundária. Não há parcela mensal: a Caixa paga o banco a cada aniversário (`LEV/lev-regras.md` §2).
2. **Um banco só:** Novo Saque, pelo serviço `novosaque-fgts` (:8104, loopback na S2). Nenhum outro serviço da casa faz FGTS (`LEV/lev-outros-bancos.md` §1). Mas **cada simulação devolve 9 tabelas** (NS, CAMPANHA, ZERO, GOLD…), todas na mesma transação.
3. **Onde se vende:** só no WhatsApp. Chatbot «MBURA - FGTS» no ChatGuru + n8n + «FGTS FORM». Não há in-app, site nem digitação FGTS no Cliente360 novo. Nada do FGTS grava no gl360 (decisão do dono de 28/09).
4. **Volume (MEDIDO):** ~370 mil consultas/semana; ~1,1 mil formalizações/dia. É 50× o teto diário da IA do piloto CLT.
5. **Onde falha antes da oferta:** 45% sem saldo, 31% `timeout` (a Caixa demora até horas), 18% sem oferta; **24% de todas as consultas** são «falta autorização no app», recuperáveis, e ninguém re-simula depois (`NSR:715-727` ✔).
6. **Onde falha depois da oferta:** **a perda pré-aprovado → formalizado é desconhecida**. As fontes da casa dão de ~0% a ~65% conforme o número que se usa (§2, tabela E1). Medido só o fim do funil: ~23% dos `Awaiting formalization` acabam em `sign-contract/Canceled` (eventos, `NS app/robo_evento.py:48-58` ✔).
7. **A negociação no FGTS é escolher a tabela, não recalcular.** Prazo, taxa e total devido são iguais nas 9; só o valor liberado muda. A NS é contratada em 96,5% e nunca é a de maior liberado (`NS app/propostas.py:279-283` ✔). O que a troca de tabela tira da GL (seguro? comissão? juros?) é **HIPÓTESE** até ver a forma crua de uma oferta de cada tabela.
8. **Onde a IA entraria:** depois da falha do chatbot, em dois gatilhos: **FG-01** pré-aprovado sem contrato (com `tardia: bool`) e **FG-03** formalizou e não assinou. Nenhum dos dois é «falha do chatbot» observável hoje: é «não converteu em N minutos». O FG-01 só fica confiável com o GET do contrato + `formalizacoes_desde`, nunca pela auditoria sozinha.
9. **O que falta para negociar:** a lógica dos fluxos do n8n (inclusive o código de 26 linhas de «FGTS - negou ns (passa campanha)», que **já faz**, linear, o degrau NS → CAMPANHA; o que ele escolhe e quem o dispara seguem abertos, LC-14); a comissão por tabela (o fator do Go é **peso de meta**, não comissão); as 8 tabelas não escolhidas vivem 3 a 30 dias; holdout para medir.
9b. **Atualização de 10/11, 17:37 (FF-0, §7.2):**
    - **Volume:** FG-01 tem ~1.500 casos por dia útil e FG-03 ~150 a 200. O portão G-F1 passa.
    - **Escada do chatbot:** NEGOU NS → CAMPANHA → NEGOU CAMPANHA, mais três lembretes depois de passar o valor. A IA entra **depois** do diálogo `NEGOU CAMPANHA` ou do lembrete «Não Respondeu», e assim a falha do chatbot fica observável.
    - **Robô:** não cobre FG-01 nem FG-03.
    - **Risco no F3:** ele lê o primeiro item do contrato cru, sem filtrar a tabela.
    - **Ainda falta:** a comissão por tabela (rodada 2 do mapeamento e pergunta 1 à Novo Saque).
10. **Recomendação:** não mexer no piloto CLT de 27–30/11. Agora, só custo zero: export completo do n8n, perguntas à Novo Saque e uma medição de funil sem PII (LC-08) que vira portão de go/no-go. Datas de FF-3/FF-4 só depois dos portões do §8.3.

---

## 2. O processo do início ao fim

Quem age: **C** = cliente · **CB** = chatbot (ChatGuru + n8n) · **CS** = consultor · **BN** = banco (Novo Saque e Caixa) · **SI** = sistema da casa.

| # | Passo | Quem | API / serviço | O que pode falhar | Prova |
|---|---|---|---|---|---|
| **P01** | Lead chega no WhatsApp: anúncio *click-to-WhatsApp* «Saque FGTS», tráfego («qual o mês do seu aniversário?»), campanha em massa (template `fgts_balance_notice2`) ou consultor que dispara o «fluxo fgts» por atalho | C · CB · CS | ChatGuru (diálogo) | lead some sem responder | `src/painel-dev/tests/test_reprocessador.py:428-436`; `levantamento/10-conducao-por-vendedor.md:108`; `src/painel-dev/app/binds_atalhos.py:5,49` |
| **P02** | Chatbot pede o CPF (`MBURA - FGTS - 1.1.2 PEDE CPF`) | CB | ChatGuru | lead não manda o CPF | nome do diálogo: `levantamento/10-conducao-por-vendedor.md:108` (amostra de episódios **repassados a vendedor**, não o funil do chatbot: os volumes de lá não medem este passo) |
| **P03** | Chatbot pede: aderir ao saque-aniversário, esperar 90 dias depois da adesão, e **autorizar a instituição no app do FGTS** (`1.1.3 Solicita Autorização`, 2º diálogo mais executado na amostra de repassados, atrás de `MBURA - CLT - FLUXO INAPP`) | C (no app da Caixa) | **nenhuma API**: a autorização é feita no app | não autoriza; autoriza e ninguém re-simula | autorização no app: doc Novo Saque <https://developers.novosaque.com.br/-1946002m0.md> (só `term` / `Awaiting authorization`); adesão e 90 dias: [Agência Brasil](https://agenciabrasil.ebc.com.br/economia/noticia/2025-10/novas-regras-do-saque-aniversario-do-fgts-entram-em-vigor-neste-sabado); `LEV/lev-regras.md` §3 |
| **P04** | Chatbot entrega o CPF (`1.1.4 INFORMOU CPF`) → webhook do ChatGuru → `gl-gateway POST /fgts` → **webhook do fluxo «FGTS - gerar consulta inicial»** (F1) | CB · SI | gl-gateway (54 mil POSTs/24 h) → n8n F1 | 424 do gateway; `PoolTimeout` do n8n | `src/gl-gateway/README.md:337-338`; `src/gl-gateway/tests/conftest.py:77`; `estudos/semana-1/b-receptor-mensagens.md:34`; `n8n:FGTS - gerar consulta inicial/Recebe lead`. Que a rota `fgts` caia no F1 é **HIPÓTESE forte** (54 mil/24 h na rota × 52,8 mil desfechos/dia, `NS app/acompanhamento.py:4-5`); o destino em `gateway.rotas` não foi lido |
| **P05** | F1 anota «Lead Recebido» (:8102 nota), valida o CPF (nó de código) e testa se há CPF no campo; sem CPF → mensagem «CPF não válido» + contexto. **Não há `reprova-24h` nem 360 na entrada** (o estudo anterior dizia que havia) | SI · CB | chatguru-api (:8102) | CPF inválido (fora do gatilho) | `n8n:FGTS - gerar consulta inicial/Adicionar nota: Lead Recebido`, `tem cpf valido?`, `tem cpf no campo?`, `envia mensagem cpf não valido`; nenhum nó para :8126 nem :8114 no F1 (FATO-E). :8102 = chatguru-api: `src/painel-dev/app/servicos.py:1388` |
| **P06** | Abre a transação **só pelo modo assíncrono**: `n8n:FGTS - gerar consulta inicial/Acompanhamento NS` (POST :8104; HIPÓTESE forte = `POST /novosaque/fgts/acompanhamento`) → Novo Saque `GET .../FGTS/simulation?document=`. Nenhum fluxo FGTS ativo chama a esteira síncrona (`POST /esteira`) | SI · BN | novosaque-fgts (:8104) → partners-api | **erro 424/503** → nota de erro + `Stop and Error1`, **sem a retentativa com `transaction_id`** que o serviço pede (FG-09); **recusa na abertura** (`fora_da_politica`, `bloqueio_temporario`, `ja_formalizado`) → `Stop and Error1`, **nada ao lead** (FG-10); **simulação em andamento** → `ultima-transacao` + leitura + nota, sem reinscrever (FG-11) | `n8n:FGTS - gerar consulta inicial/Acompanhamento NS`, `Inscrito na fila?`, `Simulação em andamento?`, `busca o simulation_id`, `Stop and Error1`; `NS app/main.py:1320-1322,1419-1431` ✔; `NSR:551-552,696-697`; :8104 = `src/novosaque-fgts/Dockerfile:127` |
| **P07** | Caixa consulta o saldo: `term` → `check-balance` → `simulation`. De segundos a horas (mediana 93 min às 11 h em 22/09). No modo assíncrono o **laço do próprio serviço** acompanha até 6 h e manda **um** aviso por inscrição (inclusive `timeout`) | BN · SI | partners-api (webhook só acorda; o GET decide); laço do `novosaque-fgts` | Caixa fora: o laço **nunca re-simula**, `cef_indisponivel` é entregue como desfecho e desce ao dicionário (o «re-simula até 10×» valia só para a esteira síncrona); `timeout` agora às 6 h (o 30,8% foi medido com o corte de 300 s do síncrono) | `NSR:430-453`; `NS app/acompanhamento.py:24-31`; `NS app/config.py:230` |
| **P08** | Desfecho chega pelo **webhook do fluxo «FGTS - resultado assíncrono (fluxo 2)»** (F2) → `NS - Decide` (4 saídas: terminal; polling 60 s; espera 10 min; fallback). Terminal sem margem → `Já formalizou hoje?` (sim: só nota) → `Em Processamento?` (sim: volta ao laço) → `POST /novosaque/dicionario` → `result mapeado?` → sim: **diálogo** de recusa do ChatGuru pelo motivo (sem saldo, autorize no app, aderir, «Niver», mudança cadastral, devolve consultor); não: só nota | SI · CB | novosaque-fgts → n8n F2 → novosaque-fgts (dicionário) → chatguru-api | `saldo_negado` 45,3%; `simulacao_sem_oferta` 18,5%; **não mapeado** e **fallback** = só nota, nada ao lead (FG-12) | `n8n:FGTS - resultado assíncrono (fluxo 2)/NS - Decide`, `Já formalizou hoje?`, `Em Processamento?`, `Adicionar nota: Resultado reprovado` (é o POST ao dicionário), `result mapeado?`, `disparar mensagem reprovado chatguru`, `Adicionar nota: Resultado não mapeado`; `NS app/aviso.py:51`; `NS init_acompanhamento.sql:234-235`; `NS/tests/test_acompanhamento.py:836-842`; `NSR:435-444` ✔, `729-768` |
| **P09** | **Oferta** (`simulada`, 3,4%): até 9 tabelas na transação. Grava `novosaque.propostas` (só a TABELA NS; PK `transaction_id`, que rotaciona por CPF em 24 h) e `esteira_guru` (as 9, por 3 dias). No F2, `Tem margem?` = sim → nota «Lead com saldo» → **valor num campo do ChatGuru** → **diálogo de pré-aprovado** → contexto. Depois, **enriquecimento**: 360 (`pessoas:obter-ou-cadastrar`, com espera se indisponível/enriquecendo) → se não achou, facta-off `/factaoff/base-offline` (base **CLT**) → se não achou, Nova Vida; termina em nome e nascimento nos campos do ChatGuru e, pela FACTA, gravado no 360 (`pessoas:ingestoes`) | SI · CB | novosaque-fgts → n8n F2 → chatguru-api; cliente360-api (:8114); facta-off (:8107); novavida (:8133) | o texto da oferta (vive no diálogo do ChatGuru) e **qual tabela vai no campo**: NÃO VERIFICADO (corpo do HTTP) | `NS app/propostas.py:300-341` ✔; `NS init_propostas.sql:73` ✔; `NSR:966-985`; `n8n:FGTS - resultado assíncrono (fluxo 2)/Tem margem?`, `Adicionar valor ao campo`, `disparar mensagem pre aprovado guru`, `consulta cliente 360 (api)`, `consulta off facta`, `consulta nova vida`, `registra dados no 360 (facta)`; portas: `src/gl-inapp/inappclt/app/config.py:838`, `src/painel-dev/app/servicos.py:625,1005`, `src/painel-dev/app/factaoff_teste.py:53,61` |
| **P10** | **Oferta tardia**: a Caixa respondeu depois de muito tempo. Chega pelo mesmo aviso do F2 e passa **pelo mesmo nó** de oferta: nenhum nó distingue a tardia (não há IF sobre `aviso.espera_s`). Em 21/10, 1.237 tardias contra 1.025 na hora; numa medição anterior de 7 dias (data não registrada), 291 tardias (4,1%) contra 6.750 | SI · CB | novosaque-fgts → n8n F2 | lead já esfriou; recebe o mesmo diálogo de pré-aprovado | `NSR:~985`; `NSR:1197-1206` ✔; `n8n:FGTS - resultado assíncrono (fluxo 2)/Tem margem?` (único caminho de oferta, FATO-E) |
| **P10b** | **Passagem NS → CAMPANHA: existe e está ativa na S2.** Fluxo «FGTS - negou ns (passa campanha)» (F3, 7 nós, atualizado 29/09), **linear, sem nó de decisão**: lê a transação no :8104 → código de 26 linhas (HIPÓTESE: escolhe a CAMPANHA) → campo do ChatGuru → espera → diálogo → contexto. Chamado por webhook do fluxo, HIPÓTESE pela rota `fgts-campanha` do gateway (< 100/24 h). «Negou» = HIPÓTESE preferida: **o lead** recusou a NS num diálogo | CB | n8n F3 → novosaque-fgts; chatguru-api | sem ramo de erro; o que o código escolhe e quem dispara: NÃO VERIFICADO | `n8n:FGTS - negou ns (passa campanha)/recebe lead`, `get propostas ns`, `Code in JavaScript`, `disparar mensagem guru2`; `NS app/propostas.py:265-282` (CAMPANHA é a 2ª tabela contratada) |
| **P10c** | **Chave Pix**: o lead manda a chave; «motor de pix fgts» (F4) valida (código de 721 linhas) e um switch de 6 saídas grava o campo «Chave pix» e dispara o próximo diálogo, ou responde «CPF de outra pessoa», «chave aleatória não aceita», «chave inválida» | C · CB | n8n F4 → chatguru-api | chave recusada (condução, o lead pode mandar outra); a chave aleatória é recusada pela casa, não pela Novo Saque | `n8n:motor de pix fgts/regex`, `Switch`, `Adiciona ao campo Chave pix`, `chave pix aleatoria não aceita`; rota `motor-chavepix` (1,2 mil/24 h, HIPÓTESE de destino) `estudos/semana-1/b-receptor-mensagens.md:34` |
| **P11** | Lead aceita. «FGTS FORM» (F5): `registra telefone no 360` → 360 → se falta dado, Nova Vida (`completa com nova vida`, e grava no 360 se completou) → `normaliza dados` (código, 208 linhas). **O F5 não pergunta nome nem nascimento ao lead e não coleta Pix**: busca no 360/Nova Vida e lê os campos (Pix gravado pelo F4, HIPÓTESE pelo encadeamento) | C · CB | gl-gateway `/fgts-form` → n8n F5; cliente360-api; novavida | dados parciais ficam nos **campos do ChatGuru** e no **360** (o quê exatamente: corpo NÃO VERIFICADO, LC-15) | `src/painel-dev/app/n8n_regras.py:1106` ✔; `n8n:FGTS FORM/registra telefone no 360`, `consulta nova vida`, `completa com nova vida`, `registra dados no 360 (nova vida)`, `normaliza dados` |
| **P12** | **Formalização** `POST /novosaque/fgts/contrato/{tx}/formalizacao` (HIPÓTESE forte: `n8n:FGTS FORM/HTTP Request`, POST :8104) → Novo Saque `POST .../formalization` (202, assíncrona). 7 campos obrigatórios; o resto é default da casa. Sem idempotência, 1 tentativa, 30 s. Parte das formalizações ainda corre **fora** deste serviço. Erro → `idade acima do limite?` → sim: diálogo de idade; não: `Stop and Error`, **nada ao lead** | SI · BN | n8n F5 → novosaque-fgts → partners-api | 400 campo; 422 recusa; **424 indeterminado (nunca repetir)**; segunda formalização = «Simulation status invalid»; todo erro ≠ idade fica mudo (FG-06) | `NSR:145-236`; `NS app/formalizacao.py:45-66` ✔; `NS app/main.py:646-739`; `NSR:1539-1543` ✔; `n8n:FGTS FORM/idade acima do limite?`, `dispara dialogo idade acima do limite`, `Stop and Error`. Qual `simulation_id` (qual tabela) vai no corpo: NÃO VERIFICADO |
| **P13** | Link de assinatura: `contract_link` aparece no GET do contrato em `sign-contract / Awaiting formalization`; o webhook nunca traz. **Quem envia: o F5**: `Wait` → GET do contrato (`HTTP Request1`, HIPÓTESE) → `tem link de formalizacao?` → sim: `passa link form` (**mensagem** :8102) + diálogo + `cadastra newcorban` (:8106, proposta no CRM NewCorban); não: `pode reconsultar?` → laço ou `sem link de formalizacao` (Stop and Error, nada ao lead) | SI · CB | n8n F5 → novosaque-fgts → partners-api; chatguru-api; newcorban-api | link que não sai no tempo do laço: lead fica sem link e sem mensagem (FG-03b) | `NS app/propostas.py:510-576` ✔; `n8n:FGTS FORM/tem link de formalizacao?`, `passa link form`, `cadastra newcorban`, `pode reconsultar?`, `sem link de formalizacao`; :8106 = `src/painel-dev/app/servicos.py:904` |
| **P14** | Cliente assina no link (mediana 407 s entre o POST e a assinatura; máximo 37,6 h). Sem selfie nem documento no FGTS. Em quanto tempo a Novo Saque cancela o link não assinado: **não documentado** (LC-16) | C | página da Novo Saque | **não assina**: `sign-contract/Canceled` 3.879 eventos em 22 dias | `NS app/propostas.py:475-479` ✔; `NS app/robo_evento.py:48-58` ✔; doc <https://developers.novosaque.com.br/documents-upload-34573929e0.md> |
| **P15** | Averbação na Caixa (`registry`) | BN | — | `Canceled` por código da Caixa: 5 (operação em andamento), 14, 17 (valor maior que o disponível), 35 (mudança cadastral), 37 (saldo insuficiente), 52 (limite de operações); `Registry retry` | `NS/migrar_regras_do_servidor_antigo.sql:33-84` |
| **P16** | Desembolso: `Registered - Pending payment` → `Awaiting disbursement` → **`Contract paid`** (dinheiro na conta) | BN | — | `Payment returned` (367 em 22 d): corrigir Pix por `PUT .../reprocess/payment`, que a casa **não usa** | `NS app/robo_evento.py:48-58` ✔; doc <https://developers.novosaque.com.br/reprocessar-pagamento-27300860e0.md> |
| **P17** | Comissão: `pay-commission / Commission credited` | BN → GL | — | — | idem |
| **P18** | Robô operacional manda diálogo por status (pago, cancelado, TED devolvida). O do servidor antigo estava em `real`; o novo, dentro do `novosaque-fgts`, nasceu com as regras desligadas | SI | novosaque-fgts → `chatguru-api POST /chatguru/dialogo` | duas vozes no chat; 12% dos pagos sem destino (formalizados fora do serviço); estado de hoje NÃO VERIFICADO. **Nenhum fluxo do n8n age depois do link** (FATO-E, por ausência) | `NSR:1432-1503`, `1539-1543` ✔; `NS/migrar_regras_do_servidor_antigo.sql:5-13` |
| **P19** | Depois de falha do chatbot: diálogo «DEVOLVE CONSULTOR» (Caixa fora, «não possui contas de FGTS», ambos com `retry`; e black list sem retry) e departamento «FGTS - Consultores», sem divisão de leads. **No n8n não há follow-up, delegação nem departamento em fluxo FGTS**, e o «Followup 2 FGTS» não existe mais na S2 | CB · CS | ChatGuru | repasse de pré-aprovado parado: **não existe no n8n**; se existe, é interno do ChatGuru (LC-02) | `NS/completa_catalogo_do_antigo.sql:33-40` ✔; `src/painel-dev/app/chatguru_departamentos.py:1-12`; ausência no export, cujo filtro pega todo fluxo com «fgts» no nome (`/home/danilo/fgts-estudo/scripts/exportar-n8n-fgts.sh:11`) |

**Os fluxos FGTS do n8n na S2 (export de 10/11).** Nenhum chama outro e nenhum tem gatilho por agenda: todos começam por webhook, e o acoplamento passa pelo **ChatGuru** (um diálogo dispara a rota do gateway do próximo fluxo) e pelo **`novosaque-fgts`** (que avisa o F2). Nenhum nó Postgres: na S2 tudo é HTTP (o `mbfgts.jobs_fgts` e a leitura de `api_novosaque.simulacao` eram do S3 antigo).

| # | Fluxo (id) | Ativo · atualizado · nós | Papel | Termina em |
|---|---|---|---|---|
| F1 | «FGTS - gerar consulta inicial» (`VZJlJYm80zP46Zls`) | sim · 26/10 · 15 | valida CPF e inscreve no acompanhamento | fila do serviço; ou mensagem de CPF inválido; ou só nota/erro |
| F2 | «FGTS - resultado assíncrono (fluxo 2)» (`6JmTdZMEkwNFIE5x`) | sim · 26/10 · 48 | desfecho → oferta, recusa ou espera; enriquecimento | diálogo de pré-aprovado; diálogo de recusa; ou só nota |
| F3 | «FGTS - negou ns (passa campanha)» (`EcxlFFWdhyN21qh6`) | sim · 29/09 · 7 | oferta da CAMPANHA | diálogo da CAMPANHA |
| F4 | «motor de pix fgts» (`8w92yUtBD0Bz4Xw6`) | sim · 05/10 · 8 | valida e grava a chave Pix | campo + diálogo; ou mensagem de recusa da chave |
| F5 | «FGTS FORM» (`sBcKoLRl9VeOX3fF`) | sim · 23/10 · 32 | cadastro, formalização, link | link por mensagem + NewCorban; diálogo de idade; ou erro mudo |
| F6 | «CLT Resultado C6 (inapp)» (`kNwFrjy1KtvQAkCq`) | sim · 10/11 · 37 | **CLT**, não FGTS; os 3 nós `reprova-24h` dele estão **sem ligação** (nunca executam) | — |
| F7 | «TESTE - eco do aviso assincrono» (`fazxTNW9YxpZVznK`) | **não** · 28/10 · 2 | teste | — |

Sumiram da S2 (o filtro do export os pegaria): «Followup 2 FGTS», os 4 fluxos de Pix do S3 antigo e «FGTS - FORMALIZAÇÃO (idade >74)»; viraram F4 e F5. Prova: `LEV/lev-n8n.md` §0; portas → serviço com prova de código em `LEV/lev-n8n.md` §0.1 (a memória `gl-infra-topology.md` não lista as 81xx).

**Funil medido.** Os números da casa **não fecham entre si** (datas e recortes diferentes, nenhuma junção por transação).

| Fonte | Número | Por dia | Pré-aprovado → formalizado implícito (com ~1.144/dia) |
|---|---|---|---|
| `NSR:435-444` ✔ (7 dias até 26/10) | 12.457 `simulada` | ≈ 1.780 | ≈ 64% (perda ≈ 36%) |
| `NSR:~985` (7 dias, data não registrada) | 6.750 + 291 tardias | ≈ 1.006 | > 100% (incoerente: há formalização fora deste serviço) |
| `NSR:966-970` ✔ (24 h) | 3.317 pré-aprovações de 3.263 CPFs | 3.317 | ≈ 34% (perda ≈ 65%) |
| `NSR:711` ✔ | formalizações | ≈ 1.144 | — |
| `NS app/robo_evento.py:48-58` ✔ (22 dias, robô antigo) | 16.727 `Offer available` × 16.721 `Awaiting formalization` | — | ≈ 100%, **mas** o robô antigo acompanha propostas já no Corban; HIPÓTESE: é viés de seleção, não conversão |
| Mesma fonte | 16.721 `Awaiting formalization` → 12.830 assinados → 11.381 pagos | — | eventos, não contratos únicos: ≈ 77% assinam, ≈ 68% são pagos |
| Mesma fonte | 3.879 `sign-contract/Canceled` | ≈ 176 | ≈ 23% dos `Awaiting formalization` |

**Conclusão:** a perda pré-aprovado → formalizado está **entre ~0% e ~65%**; ninguém sabe. Ela é o tamanho do FG-01 e só se fecha com a medição LC-08, que é portão de FF-1 e FF-3 (§8.3).

---

## 3. Inventário de APIs

Uma linha por endpoint. «Custo/limite» só com o que está provado; o resto, «não documentado».

### 3.1 Novo Saque (partners-api, externo)

| Id | Método e caminho | Para quê | Entrada essencial | Saída essencial | Custo / limite | Usado? | Prova |
|---|---|---|---|---|---|---|---|
| API-01 | `GET /partners-api/contracts/FGTS/simulation?document=` | abre transação: saldo + simulação | CPF | 201 `transaction_id` (às vezes na chave `contract`) | custo não documentado; cria transação com TTL ~3 d; 1 em andamento por CPF; bloqueio temporário após recusas | sim | doc <https://developers.novosaque.com.br/iniciar-simula%C3%A7%C3%A3o-de-contrato-27300855e0.md>; `NS app/novosaque.py:135-136,488-495` |
| API-02 | `GET /partners-api/contracts/FGTS/contract/{tx}` | estado, saldo, **9 ofertas**, link, status | `transaction_id` | `stage`, `summary_status`, `balance_check_result`, `simulation_results[]`, `contract_simulation_results`, `contract_link` | ~8 KB; 404 depois do TTL; a casa faz 3 tentativas, 15 s | sim | doc <https://developers.novosaque.com.br/buscar-contrato-e-status-do-fluxo-27300857e0.md>; `NS app/novosaque.py:398-425,529-532` |
| API-03 | `PUT /partners-api/contracts/FGTS/simulation/{tx}` | re-simular parâmetros (`installments`, `installment_value`); `product` aceita FGTS | tx + query | 201 | em que `stage` vale: não documentado | **não** | doc <https://developers.novosaque.com.br/re-simula%C3%A7%C3%A3o-de-parametros-de-simula%C3%A7%C3%A3o-existente-27300856e0.md> |
| API-04 | `POST /partners-api/contracts/FGTS/contract/{tx}/formalization` | contratar uma oferta | `simulation_id` + `customer_data` (Pix ou conta) | 202 «queued» | **sem idempotência**; 1 por transação | sim | doc <https://developers.novosaque.com.br/iniciar-formalizacao-do-contrato-27300858e0.md>; `NS app/novosaque.py:498-526` |
| API-05 | `PUT /partners-api/contracts/FGTS/contract/{tx}/reprocess/payment` | corrigir Pix depois de `Payment returned` (CLT ou FGTS) | `bank_data` | 200 | elegibilidade não documentada | **não** | doc <https://developers.novosaque.com.br/reprocessar-pagamento-27300860e0.md> |
| API-06 | `GET .../contract/{tx}/files/{file_type}` | arquivo assinado | tx, tipo | URL | enum só CLT e CARD | não se aplica | doc <https://developers.novosaque.com.br/obter-url-de-arquivo-assinado-27300859e0.md> |
| API-07 | Webhook da Novo Saque → `POST /novosaque/webhook/{token}` | avisa **quando** olhar; nunca decide | evento | — | ~100 mil/dia, quase todos de outros parceiros; chega por espelho do servidor antigo | sim | `NS app/esteira.py:27-29`; `NSR:877-898` |
| — | Autorizar no app, cancelar, reenviar link, trocar Pix antes do pagamento, listar por CPF | — | — | — | **não existem** | — | `LEV/lev-novosaque.md` §2, §9 |

Autenticação: `X-Api-Key` em toda chamada; 401/403 viram 424 `novosaque_credencial` (`NS app/novosaque.py:152-153,437-443`). Nenhum rate limit documentado.

**Comissão na doc.** O schema `SimulationResult` tem `commission` → `SimulationCommission` (`commission_corban_value`, `commission_corban`, `commission_total`, `commission_seller_value`…). Nos **exemplos** da doc, porém, `commission` só aparece em `contract_simulation_results` (a oferta contratada), não em cada item de `simulation_results`; `commission_corban_value` é `string` no schema e número no exemplo (doc API-02, lida em 10/11). Se vem preenchido **por oferta antes da escolha** é LC-03.

### 3.2 `novosaque-fgts` (:8104, loopback na S2)

| Id | Método e caminho | Para quê | Entrada essencial | Saída essencial | Custo / limite | Quem chama | Prova |
|---|---|---|---|---|---|---|---|
| API-10 | `POST /novosaque/fgts/simulacao` | abre transação (só API-01) | `cpf` | `transaction_id` | 422 `fora_da_politica`, `bloqueio_temporario` + `repetir_em_s` | console do painel | `NS app/main.py:1514` ✔ |
| API-11 | `POST /novosaque/fgts/esteira` (+ alias `/novosaque/simulacao/consultar-sincrona`) | abre e espera o desfecho | `cpf`, campos do ChatGuru (`telefone_guru`, `guru_link`, `guru_phone_id`, `guru_responsavel`) | envelope legado: `desfecho`, `aprovado`, `ofertas{slug:…}` em texto pt-BR | até 60 min; 504 `esteira_timeout` | n8n (NÃO VERIFICADO) | `NS app/main.py:1582-1606` ✔; `NS app/legado.py:74-124` |
| API-12 | `GET /novosaque/fgts/esteira/{tx}` | leitura pura do desfecho; nunca re-simula; grava oferta tardia | tx | mesmo envelope | — | n8n (laço «NS - Aguardar 60s») | `NS app/main.py:1609-1630` ✔ |
| API-13 | `POST /novosaque/fgts/acompanhamento` | abre e avisa depois (fluxo 2) | `cpf`, `destino`, `contexto` | 202 `acompanhando`; depois POST no n8n | aviso só para hosts de loopback (`aviso_hosts`) | n8n | `NS app/main.py:1633-1656` ✔; `NS app/config.py:264` ✔ |
| API-14 | `GET /novosaque/fgts/acompanhamento/{tx}`, `GET /novosaque/fgts/acompanhamentos` | ler a fila | tx | estado | — | operação | `NS app/main.py:1659,1716` |
| API-15 | `POST /novosaque/fgts/ultima-transacao` | última transação do CPF (7 d) aberta **por este serviço** | `cpf` | tx | — | n8n | `NS app/main.py:1691` ✔; `NSR:~705-712` |
| API-16 | `GET /novosaque/fgts/contrato/{tx}` | passthrough cru de API-02 | tx | contrato | — | n8n, painel | `NS app/main.py:1524` ✔ |
| API-17 | `POST /novosaque/fgts/contrato/{tx}/formalizacao` (+ alias sem `fgts`) | formaliza | `simulation_id`, 7 campos, `digitador_proposta?`, `vendedor?`, `origem?` (opcionais, ainda não enviados por todos os nós) | 201 + `X-Formalizacao-Id` | 1 tentativa; 424 com `conferir_antes_de_repetir` | n8n (NÃO VERIFICADO) | `NS app/main.py:1542-1579,186-246` ✔; `LEV/lev-chatbot.md` C9 |
| API-18 | `POST /novosaque/dicionario` | motivo → diálogo do ChatGuru | texto da recusa | `dialog_id`, `mapeado`, `retry` | — | n8n | `NS app/main.py:1732` ✔; `NSR:729-768` |
| API-19 | `GET /novosaque/fgts/estatisticas` | agregados por desfecho | período | contagens | — | cliente360-web `/fgts/statistics` | `NS app/main.py:1762` ✔; `LEV/lev-c360.md` §4 |
| API-20 | `GET /novosaque/fgts/consultas` | lista **com PII** (≤ 200) | filtros | linhas | não serve à IA | operação | `NS app/main.py:1802` ✔ |
| API-21 | `POST /novosaque/webhook/{token}` | recebe API-07 | evento | — | token no path | Novo Saque | `NS app/main.py:1845` ✔ |
| API-22 | `GET /health` | estado sem banco | — | `configurado`, `esteiras_ativas` | — | monitoramento | `NS app/main.py:1852` |
| — | função `novosaque.formalizacoes_desde(cpf)` (SECURITY DEFINER) | transações formalizadas do CPF, com status | CPF | tx, instante, `stage`, `summary_status` | só o que este serviço formalizou | trava `ja_formalizado` | `NS app/ja_formalizado.py:27-30,96` ✔ |

Saídas do serviço: n8n fluxo 2 (`NS app/aviso.py:276-325`), `chatguru-api` (`NS app/robo_entrega.py:619`), `reprova-24h` (`NS app/reprova24h.py:97-98`).

### 3.3 Serviços em volta

| Id | Serviço | Método e caminho | Para quê | Entrada / saída essencial | Custo / limite | Prova |
|---|---|---|---|---|---|---|
| API-30 | gl-gateway | `POST /fgts` | entrada do chatbot → n8n | token por origem; 424 em falha do destino | 54 mil/24 h, p95 175 ms; rotas em `gateway.rotas` | `src/gl-gateway/README.md:337-338`; `src/gl-gateway/tests/conftest.py:77` |
| API-31 | gl-gateway | `POST /fgts-form` | coleta de dados → n8n «FGTS FORM» | — | ~49/h no painel (≈ 1,2 mil/24 h) × ~0,9 mil/24 h no estudo do gateway: fontes divergem | `src/painel-dev/app/n8n_regras.py:1106` ✔; `estudos/semana-1/b-receptor-mensagens.md:34` |
| API-32 | gl-gateway | `POST /fgts-campanha` | campanha | — | < 100/24 h; o que faz: NÃO VERIFICADO | `estudos/semana-1/b-receptor-mensagens.md:34` |
| API-33 | gl-gateway → edge | `POST /fn-validador-cpf-timer-fgts` → `:8126/validador-cpf-timer-fgts` | validar CPF com timer | código não exportado | 3,3 mil/24 h | `src/painel-dev/tests/test_apoio.py:731-740` |
| API-34 | edge `reprova-24h` (:8126) | marca/consulta reprovado 24 h | CPF; Redis `EX 86400` | só recusas definitivas | `NS app/reprova24h.py:1-35` ✔ |
| API-35 | n8n | webhook do fluxo «FGTS - resultado assíncrono (fluxo 2)» | recebe o desfecho assíncrono | envelope da esteira + `aviso.espera_s` | — | `NSR:540-568`; `n8n:FGTS - resultado assíncrono (fluxo 2)/Recebe resultado` |
| API-36 | chatguru-api (:8102) | `POST /chatguru/mensagem`, `/dialogo`, `/nota`, `/campos`, `/contexto` | falar com o lead e anotar | `phone_id`, `chat_number` | `sem_retry_ambiguo` | `src/chatguru-api/README.md:82-97` |
| API-37 | chatguru-api | `GET/POST /chatguru/rpa/chat/{chat}/chatbot`; `GET/PUT .../delegacao`; `POST /chatguru/rpa/template` | ler/desligar o chatbot, ler/mudar delegação, template fora de 24 h | RPA com cookie; template pago, 424 `incerto` nunca repetir | `src/chatguru-api/README.md:165-182` |
| API-38 | cliente360-api | `POST /pessoas:obter-ou-cadastrar` | nome do lead | CPF → pessoa | 202 + releitura em 40 s | `src/cliente360-api/docs/rotas-status.md:42,480` |
| API-39 | novavida-api | `POST /novavida/nvcheck` | completar cadastro no «FGTS FORM» | CPF → recorte | teto diário (`/health`); 429/424 → segue sem | `src/novavida-api/README.md:14-17,38,80` |
| API-40 | api-interna | `POST /facta/base-offline-fgts` | **base CLT** da FACTA para lead do FGTS (cruzamento) | CPF → vínculos CLT | runtime NÃO VERIFICADO | `src/api-interna/FACTA/Facta_offline/app/routers/facta.py:318-348` |
| API-41 | robo-atualizador-fgts (Node, :8787) | varre propostas no Corban | — | — | `src/painel-dev/README.md:1752-1778` |
| API-42 | cliente360-api | `GET /coeficientes/fgts/tabelas`; `POST /coeficientes/fgts/*` | catálogo de tabelas FGTS | leitura atrás de `C360_TABELAS_FGTS`; escrita 503/501 (D19-11) | sem coeficiente gravado; faixa decidida 0–3 (`MEM:decisoes-fgts-coeficientes.md` item 2) | `src/cliente360-api/src/c360api/rotas/tabelas_fgts.py:62-94`; `controlplane/bloqueios.py:127-152` |
| API-43 | cliente360 legado | `GET /clientes/{cpf}/ficha` (seção `fgts`) | ofertas por tabela, propostas, contratos por CPF | segredo S2S | se ainda roda: NÃO VERIFICADO | `src/cliente360/app/ficha.py:845-944` |

---

## 4. O chatbot de venda automatizada

### 4.1 Fluxo (o que se prova, com a estrutura de 10/11)

```
anúncio / tráfego / campanha / consultor
        │
ChatGuru «MBURA - FGTS»: 1.1.2 PEDE CPF → 1.1.3 Solicita Autorização → 1.1.4 INFORMOU CPF
        │ rota gateway `fgts` (HIPÓTESE forte; 54 mil/24 h) → webhook do fluxo F1
[F1 «FGTS - gerar consulta inicial»]  CPF ok? ── não ──► mensagem «CPF não válido»
        │ POST acompanhamento :8104 ── erro 424/503 ──► nota + Stop and Error (nada ao lead)      [FG-09]
        │                           ── recusa na abertura ──► Stop and Error (nada ao lead)       [FG-10]
        │                           ── em andamento ──► ultima-transacao + leitura + nota          [FG-11]
        ▼ 202 acompanhando
novosaque-fgts: laço próprio até 6 h (nunca re-simula) ──► Novo Saque / Caixa
        │ 1 aviso por inscrição → webhook do fluxo F2
[F2 «FGTS - resultado assíncrono (fluxo 2)»] «NS - Decide»
        ├─ polling ──► Aguardar 60 s / 10 min ──► NS - Buscar resultado ──► NS - Decide
        ├─ fallback ──► nota de erro (nada ao lead)                                              [FG-12]
        └─ terminal ──► Tem margem?
              ├─ sim ──► campo + diálogo PRÉ-APROVADO (tardia igual) ──► 360 → FACTA off (CLT) → Nova Vida (nome/nasc.)
              └─ não ──► Já formalizou hoje? (nota) ─► Em Processamento? (volta ao laço) ─► /novosaque/dicionario
                           └─ mapeado: diálogo de RECUSA (inclui «DEVOLVE CONSULTOR») · não mapeado: só nota  [FG-12]
ChatGuru (diálogo da oferta)
        ├─ lead recusa a NS? ── rota `fgts-campanha` (HIPÓTESE) ──► [F3 «negou ns»] linear ──► campo + diálogo CAMPANHA
        └─ lead manda Pix ── rota `motor-chavepix` (HIPÓTESE) ──► [F4 «motor de pix fgts»] ──► campo Pix + diálogo | recusa da chave
ChatGuru (diálogo de dados) ── rota `fgts-form` (FATO) ──► [F5 «FGTS FORM»]
        360 / Nova Vida ─► POST formalização :8104 ── erro ─► idade? diálogo : Stop and Error (mudo)    [FG-06]
                         └─► GET contrato em laço ─► link? ─► MENSAGEM com link + NewCorban :8106          [FG-03]
                                                     └─ não sai ─► Stop and Error (mudo)                 [FG-03b]
Depois do link: nenhum fluxo do n8n. Pós-contrato = robô operacional dentro do novosaque-fgts.
```

| Peça | Estado da prova | Prova |
|---|---|---|
| Nomes dos diálogos MBURA | FATO (amostra exportada de episódios **repassados a vendedor**; volumes não medem o funil do chatbot) | `levantamento/10-conducao-por-vendedor.md:108` ✔ |
| Rota `fgts` do gateway e destino n8n | FATO que vai ao n8n; que caia no F1: HIPÓTESE forte pelo volume | `src/gl-gateway/README.md:337-338`; `src/gl-gateway/tests/conftest.py:77`; `LEV/lev-n8n.md` §1 F1 |
| **Mesmo id `VZJlJYm80zP46Zls`, outro papel**: o antigo «FGTS - consulta inicial (com retry CEF)» virou «FGTS - gerar consulta inicial» em 26/10; só inscreve e sai. `NS - Decide`, dicionário e oferta foram para o F2 | FATO-E | `n8n:FGTS - gerar consulta inicial/*` (15 nós, nenhum switch); nome antigo só em fixture: `src/painel-dev/tests/test_n8n.py:817` |
| Nós `NS - Decide` (4 saídas), `NS - Aguardar 60s`, `NS - Aguardar 10min`, `Tem margem?`, `Já formalizou hoje?`, `Em Processamento?`, `result mapeado?` | FATO-E, no F2 | `n8n:FGTS - resultado assíncrono (fluxo 2)/*`; ordem das saídas bate com `NS/tests/test_acompanhamento.py:836-842` |
| O nó de recusa chama-se `disparar mensagem reprovado chatguru` e é **diálogo**, não mensagem (o estudo citava `MENSAGEM DE REPROVADO`) | FATO-E | `n8n:FGTS - resultado assíncrono (fluxo 2)/disparar mensagem reprovado chatguru` |
| «FGTS FORM», Pix (agora 1 fluxo com switch de 6 saídas), «negou ns (passa campanha)» ativos na S2; «FORMALIZAÇÃO (idade >74)» absorvido pelo F5 | FATO-E | `n8n:FGTS FORM/idade acima do limite?`; `n8n:motor de pix fgts/Switch`; `n8n:FGTS - negou ns (passa campanha)/*` |
| O chatbot **já faz o degrau NS → CAMPANHA** (F3), de forma determinística e linear | FATO-E a existência e a forma; a condição de disparo e a escolha (código de 26 linhas): NÃO VERIFICADO | `n8n:FGTS - negou ns (passa campanha)/Code in JavaScript` |
| Quem envia o link: F5 por **mensagem**, e cadastra a proposta no NewCorban | FATO-E | `n8n:FGTS FORM/passa link form`, `cadastra newcorban` |
| O n8n grava **dado cadastral** do lead FGTS no 360 novo (telefone, nome, nascimento; não proposta) | FATO-E | `n8n:FGTS FORM/registra telefone no 360`, `registra dados no 360 (nova vida)`; `n8n:FGTS - resultado assíncrono (fluxo 2)/registra dados no 360 (facta)` |
| Qual tabela o chatbot mostra no campo e formaliza; o texto da oferta; o que testa cada IF | **NÃO VERIFICADO** (corpo, condição e código não vieram no export) | — |
| Repasse de pré-aprovado parado a consultor | **não existe no n8n**; dentro do ChatGuru, NÃO VERIFICADO (LC-02) | ausência no export |
| «Followup 2 FGTS» (`qtNPYrkVuQ5jmF2i`) | **não existe mais** na S2 (HIPÓTESE forte: apagado; medido até 28/09) | ausência; `/home/danilo/fgts-estudo/scripts/exportar-n8n-fgts.sh:11`; `src/painel-dev/app/n8n_regras.py:68-71` ✔ |
| `reprova-24h` no FGTS | **nenhum fluxo FGTS chama :8126**; os 3 nós que chamam o edge `reprova-24h` (:8126) estão só no F6 (CLT) e soltos | `n8n:CLT Resultado C6 (inapp)/salva reprovação fgts - reaproveitamento facio` (sem ligação) |
| No legado, a conta-robô vendia ~10× o melhor humano (4.114 × ~400 contratos em 7 dias) | MEDIDO (~08/2026) | `src/gl-site-go/internal/domain/site/propostasfgts/types.go:76-77` (arquivado) |

### 4.2 Pontos de falha, com evidência, e o que acontece hoje

| Id | Falha | Evidência / volume | O que acontece depois (hoje) | Recuperável? |
|---|---|---|---|---|
| PF-01 | Lead some antes do CPF ou da autorização | **não medido**: a amostra de diálogos é de episódios repassados, não do funil | follow-up do ChatGuru; NÃO VERIFICADO | não ir atrás (decisão (ai) de 29/10) |
| PF-02 | **Falta autorização no app** | 89.193 em 7 dias (24%); 170 aprovados no mesmo dia em 24 h | diálogo «Solicita Autorização - REPROCESSAMENTO»; transação terminal, **ninguém re-simula** | sim, com freio (~60 mil pessoas/semana) |
| PF-03 | Sem adesão / carência de 90 dias / «operação não permitida antes de dd/mm» | dentro dos 8.382/24 h; «Niver» 1.473 num mês de agosto | diálogos «Optar pelo saque aniversário» e «Niver» | sim, como **agendamento** |
| PF-04 | Caixa lenta: `timeout` aos 300 s | 30,8% das consultas; tardias = 1.237 × 1.025 na hora em 21/10, mas 4,1% numa medição anterior de 7 dias (desde 23/10 a tardia conta como `simulada`) | a oferta chega pelo F2 e recebe **o mesmo diálogo** de pré-aprovado da oferta na hora (nenhum nó distingue tardia, FATO-E) | sim |
| PF-05 | Caixa fora (`cef_indisponivel`) ou «sem contas de FGTS» com retry | 0,35–3,45%/dia (agosto) | no assíncrono **ninguém re-simula**: `cef_indisponivel` é entregue como desfecho e vai ao dicionário (`NS app/acompanhamento.py:29-31`; F2 sem POST de reinscrição); o «até 10×» era da esteira síncrona, hoje sem chamador no n8n | volta sozinha, se alguém consultar de novo |
| PF-06 | **Pré-aprovado que não formaliza** | **tamanho desconhecido**: de ~0% a ~65% conforme a fonte (§2) | o F2 termina no diálogo de pré-aprovado; o único passo seguinte do n8n é o F3 (CAMPANHA, se o lead «negou» a NS), o F4 (Pix) ou o F5 (formulário). **Não há follow-up no n8n** | sim, **se existir em volume** (LC-08) |
| PF-07 | Formalização com erro (400 campo/Pix; 422; 424) | 1 erro em 1.533 (agosto) | idade acima do limite → diálogo; **qualquer outro erro → `Stop and Error`, nada ao lead** (`n8n:FGTS FORM/idade acima do limite?`, `Stop and Error`) | 400/Pix sim; 424 nunca repetir |
| PF-08 | **Formalizou e não assinou** | 3.879 `sign-contract/Canceled` em 22 dias (~23% dos `Awaiting formalization`) | regra de robô para esse status: NÃO VERIFICADA | sim |
| PF-09 | Cancelado na averbação (códigos da Caixa) | 1.022 `registry/Canceled` em 22 dias | robô antigo manda diálogo por código | quase nunca (regra da Caixa) |
| PF-10 | `Payment returned` | 367 em 22 dias | robô antigo: diálogo «TED devolvida»; API-05 não usada | sim (coletar Pix novo) |
| PF-11 | Chatbot não entendeu a mensagem | robô reprocessador do `automacao-chatguru` | reprocessa | depende do webhook por mensagem |
| PF-12 | **Formalização dupla** | 174 CPFs formalizaram 2× no mesmo dia (27–30/09); 144 das segundas canceladas. A Novo Saque «não enxerga a reserva» e devolve oferta mesmo assim | trava `ja_formalizado` na consulta, só para formalização **de hoje e já assinada**; deixa passar quando a 1ª está em `Awaiting formalization` | evitar, não recuperar |

Provas: PF-02 `NSR:715-727` ✔, `NS app/reprova24h.py:10-17` ✔; PF-03 `NS/completa_catalogo_do_antigo.sql:44-60`; PF-04 `NSR:437-453,~985,1197-1206` ✔; PF-05 `NSR:323-325`, `NS/completa_catalogo_do_antigo.sql:33-38` ✔; PF-06 §2; PF-07 `NSR:154-194,208-210`; PF-08, PF-09, PF-10 `NS app/robo_evento.py:48-58` ✔; PF-11 `src/chatguru-api/README.md:150-155`; PF-12 `NS app/ja_formalizado.py:1-20` ✔.

### 4.3 Definição proposta de «falha da negociação via chatbot»

**Definição.** O chatbot falhou quando **havia uma oferta FGTS válida para o lead e ela não virou contrato assinado** dentro de uma janela, **sem o chatbot nem um humano ainda agindo no chat**. Antes da oferta não há negociação: é condução (FG-04, FG-05), e vem depois.

**Limite honesto.** Hoje «o chatbot falhou» não é observável diretamente: o que se observa é «o lead não converteu em N minutos». A estrutura de 10/11 simplifica uma parte: **o chatbot do FGTS não tem nenhum laço de espera depois de mostrar a oferta ou o link** (todo fluxo termina num diálogo, numa mensagem ou numa nota; não há follow-up no n8n). Logo, «o chatbot falhou» = «o próximo webhook do mesmo lead (F3, F4 ou F5) não chegou», e isso só se lê cruzando execuções do n8n por chat, ou pelo lado do `novosaque-fgts`. O que ainda pode agir depois do diálogo final é o **ChatGuru** (diálogos e follow-ups internos, LC-02) e o robô operacional: a exclusão por API-37 continua necessária.

| Id | Gatilho | Onde acontece no n8n (nó / ramo) | Sinal detectável | Onde se lê (sistema) | Janela proposta | Entra na IA? |
|---|---|---|---|---|---|---|
| **FG-01** | Pré-aprovado sem contrato (atributo `tardia: bool`) | `n8n:FGTS - resultado assíncrono (fluxo 2)/Tem margem?` = sim → `disparar mensagem pre aprovado guru` é o **último passo de venda** do F2; a falha é o F4/F5 do mesmo lead não chegar. A tardia passa **pelo mesmo nó** | (a) linha em `novosaque.propostas` com desfecho `simulada`; **e** (b) GET do contrato (API-02) com `stage` **fora** de `create-contract`/`sign-contract`/`registry`/`disbursement`/`pay-commission`; **e** (c) `novosaque.formalizacoes_desde(cpf)` vazio para o `transaction_id` e **todas** as `transaction_ids_anteriores`. `tardia = true` pelo `aviso.espera_s` do envelope do aviso (> 300 s). «Sem formalização 2xx na auditoria» **não basta**: parte da formalização corre fora do serviço (`NSR:1539-1543` ✔). Alternativa no n8n: execução do F2 que passou pelo nó de pré-aprovado sem execução do F5 para o mesmo chat em N min (pede `execution_entity`) | novosaque-fgts (Postgres `novosaque.*`) + API-02; execuções do n8n | ≥ 30 min depois da oferta (≥ 15 min se `tardia`) e TTL folgado (≥ 6 h) | **sim, fase 1** (negociação de tabela), **só se LC-08 mostrar volume**; **excluir (ou começar no degrau seguinte) todo lead com execução do F3** na transação |
| **FG-01c** (novo) | CAMPANHA oferecida pelo chatbot e também não fechou | `n8n:FGTS - negou ns (passa campanha)/disparar mensagem guru2` (fim do F3) sem F5 depois | execução do F3 para o chat; proposta sem formalização (mesmas travas do FG-01) | execuções do n8n + `novosaque-fgts` + API-02 | idem FG-01 | só depois de ver o código do F3 (o degrau CAMPANHA já foi gasto); volume: rota `fgts-campanha` < 100/24 h (HIPÓTESE de que é o F3) |
| ~~FG-02~~ | (fundido em FG-01 como `tardia: true`) | — | — | — | — | — (somar os dois contava o mesmo lead duas vezes) |
| **FG-03** | Formalizou e não assinou | `n8n:FGTS FORM/tem link de formalizacao?` = sim → `passa link form` é o último passo; depois o n8n não acompanha | API-02 em `sign-contract / Awaiting formalization`, sem `Signed contract` | API-02 (fonte primária); `novosaque.proposta_evento` depende do espelho do servidor antigo (`NSR:1054`) | ≥ 2 h e antes do cancelamento (prazo de cancelamento: LC-16) | **sim, fase 1**, só **reenviar o link** (sem renegociar tabela, sem formalização nova enquanto houver `Awaiting formalization` vivo) |
| **FG-03b** (novo, silêncio) | Formalizou e o link nunca saiu | `n8n:FGTS FORM/pode reconsultar?` = não → `sem link de formalizacao` (Stop and Error): **nada ao lead** | formalização 2xx com `link_formalizacao` nulo em `novosaque.propostas` (`NS app/propostas.py:549-576`); execução do F5 com erro nesse nó | novosaque-fgts; execuções do n8n | depois do laço do F5 | corrigir no n8n (mensagem/retentativa) antes de IA; não medido |
| FG-04 | Falta autorização / adesão | `n8n:FGTS - resultado assíncrono (fluxo 2)/Em Processamento?` = não → dicionário → `result mapeado?` = sim → `disparar mensagem reprovado chatguru`. Nenhum nó re-simula depois | desfecho `saldo_negado` com motivo de autorização ou adesão | auditoria + dicionário | depois do diálogo do chatbot | **fase 2**, e primeiro por um **robô de re-simulação sem IA** |
| FG-05 | Data (carência, «Niver») | mesmo caminho do FG-04, diálogo «Niver» | motivo com data | dicionário | na data | fase 2, como agendamento (gatilho M) |
| FG-06 | Erro de dado na formalização | `n8n:FGTS FORM/HTTP Request` (saída de erro) → `idade acima do limite?` = não → `Stop and Error`: **nada ao lead** | 400/422/424 de API-17 na auditoria; execução do F5 com erro | resposta de API-17 | na hora | fase 2; o silêncio se corrige no n8n antes |
| FG-07 | Objeção explícita no chat («valor baixo») | **fora do n8n**: nenhum fluxo recebe mensagem livre do lead | texto do lead | só com webhook por mensagem do ChatGuru | — | depois (precisa da entrada do canal) |
| FG-08 | `Payment returned` | **fora do n8n** (robô operacional do serviço) | evento | `novosaque.proposta_evento` / API-02 | na hora | fase 3 (pós-venda, não negociação) |
| **FG-09** (novo, silêncio) | Inscrição falhou com a transação talvez aberta | `n8n:FGTS - gerar consulta inicial/Acompanhamento NS` (saída de erro) → `Adicionar nota erro` → `Stop and Error1`, **sem a retentativa com `transaction_id`** que o serviço pede (`NS app/main.py:1419-1431`) | 503 `nao_inscrito` com `transaction_id` na auditoria de abertura; nota de erro no chat | novosaque-fgts | na hora | corrigir no n8n; não medido |
| **FG-10** (novo, silêncio) | Recusa na abertura sem mensagem | `n8n:FGTS - gerar consulta inicial/Inscrito na fila?` = não → `Simulação em andamento?` = não → `Stop and Error1` (`bloqueio_temporario`, que traz `repetir_em_s`; `fora_da_politica`; `ja_formalizado`: HIPÓTESE pela condição) | desfecho da abertura com `via: "abertura"` (`NS app/main.py:1371-1378`) | novosaque-fgts | na hora (`bloqueio_temporario`: em `repetir_em_s`) | antes da oferta: condução, não negociação; não medido |
| **FG-11** (novo) | Simulação em andamento que pode não estar na fila | `n8n:FGTS - gerar consulta inicial/Simulação em andamento?` = sim → `busca o simulation_id` → `NS - Buscar resultado1` → nota; o lead **não é reinscrito** (HIPÓTESE pelo método não declarado) | `ultima-transacao` com `na_fila: false` (`NSR:691-694`) | novosaque-fgts | — | corrigir no n8n; não medido |
| **FG-12** (novo, silêncio) | Resultado não mapeado ou sem desfecho | `n8n:FGTS - resultado assíncrono (fluxo 2)/result mapeado?` = não → `Adicionar nota: Resultado não mapeado`; `NS - Decide` saída [3] → `Adicionar nota erro`: só nota | dicionário com `mapeado: false`; envelope sem `desfecho` nem `transaction_id` | novosaque-fgts | na hora | corrigir no n8n/dicionário; não medido |

**Os silêncios (FG-03b, FG-06, FG-09, FG-10, FG-12) são falhas do chatbot em sentido estrito** (o lead fica sem resposta), mas não são negociação: parte se corrige no próprio n8n (retentativa com `transaction_id`, mensagem no lugar do `Stop and Error`) antes de pensar em IA. Para medi-los sem PII: contagem de execuções por fluxo e por nó de saída em 7 dias (§7.1, ampliado para os ids F1–F5).

**Consequência para o motor (§5.2).** O degrau NS → CAMPANHA **já existe no chatbot** (F3). O motor v0 não pode tratar a CAMPANHA como 1º degrau para quem passou pelo F3; a IA precisa ler as execuções do F3 por chat ou por `transaction_id`, ou o F3 passa a gravar uma marca (no `novosaque-fgts`, nunca no n8n). Q-FG-02 continua suspensa até ver o código de 26 linhas do F3 e o diálogo que o dispara.

**Fora do gatilho (FG-X):** CPF inválido (`n8n:FGTS - gerar consulta inicial/envia mensagem cpf não valido`); já formalizou hoje (`n8n:FGTS - resultado assíncrono (fluxo 2)/Adicionar nota: Já formalizou hoje`); idade acima do limite (`n8n:FGTS FORM/dispara dialogo idade acima do limite`); chave Pix recusada (`n8n:motor de pix fgts/chave pix inválida` e irmãos: é condução, o lead pode mandar outra); lead sem cadastro no 360/FACTA/Nova Vida (`n8n:FGTS - resultado assíncrono (fluxo 2)/Adicionar nota: 360 sem cadastro`: falta de dado, não falha de venda); sem saldo, sem conta, parcela < R$ 100, sem oferta, fora da política, `ja_formalizado`, `cef_indisponivel`, `bloqueio_temporario`, `simulacao_em_andamento`, cancelado pela Caixa, lead que nunca respondeu, chat sem `telefone_guru`/`guru_phone_id` (12% dos pagos ficam `sem_destino`, `NSR:1539-1543`), e **chat com humano ou chatbot ainda atuando**, lido assim:
- delegação a vendedor ou departamento ≠ do robô: `GET .../delegacao` (API-37);
- chatbot ativo no chat: `GET .../chatbot` (API-37);
- RPA com cookie: frágil; se a leitura falhar, o lead **fica fora** (fail-closed). Não há prova de que essas leituras estejam ligadas em algum fluxo hoje.
- «Humano nos últimos 60 min» **depende do webhook por mensagem**, que não existe (FG-07): fica fora do v0.

**Volume.** HIPÓTESE: FG-03 ≈ 170/dia (3.879 ÷ 22, eventos). FG-01: **desconhecido** (§2); não usar número até LC-08.

**Por que FG-01 e FG-03 primeiro.** Os dois se leem no `novosaque-fgts` + API-02, têm a oferta e o canal na mesma linha (`guru_link`, `telefone_guru`) e não precisam do n8n para o sinal. A exclusão de «chatbot ainda agindo» precisa do API-37 (ChatGuru) e, para o FG-01, das execuções do F3; o n8n em si não age depois do diálogo final de F2/F3/F5.

---

## 5. Alavancas de negociação e roteiro da IA

### 5.1 Alavancas

| Id | Alavanca | Existe? | Efeito cliente × GL | Prova |
|---|---|---|---|---|
| **AL-01** | **Tabela** (9 por transação) | **sim, a principal** | só o liberado muda; prazo, taxa e total devido iguais. Mais liberado = menos de algo para a GL (o quê: AL-02) | `NS app/propostas.py:300-310` ✔; `NSR:994-1000` ✔ |
| AL-02 | «Seguro» embutido | **HIPÓTESE** | o código afirma: total devido = liberado + IOF + `insurance_amount`, «45% da operação, R$ 65,80 em média, fecha em 7.033 de 7.033» (`NS app/propostas.py:322-329` ✔). Mas não sobra lugar para os juros (~1,8% a.m. por até 5 anos), e o exemplo do README (CAMPANHA) tem `insurance_amount: null`, `interest_value: null` e total ≠ liberado + IOF (`NSR:~397-404` ✔). HIPÓTESE alternativa: o campo carrega os juros. **Proibido falar em «seguro» ao cliente** até LC-04 | idem |
| AL-03 | Anos antecipados (1 a 5) | regulatório sim; **pela API, não provado** | menos anos resolve «valor maior que o disponível» (código 17) | API-03 não testada; `LEV/lev-regras.md` §5 |
| AL-04 | Valor por ano (R$ 100–500) | idem AL-03 | — | idem |
| AL-05 | Taxa | **não**: a Novo Saque pratica 1,7999% a.m., colada no teto de 1,80% (fonte secundária) | — | `NSR:404`; `LEV/lev-regras.md:52` |
| AL-06 | Banco | **não** hoje (um só). Um 2º banco exige o cliente autorizar outra instituição no app, e o app mostra o nome dela | — | `LEV/lev-outros-bancos.md` §5.2 |
| AL-07 | Momento | sim: depois da carência, do débito anual ou do bloqueio. Uma antecipação por ano | agendar, não negociar | `LEV/lev-regras.md` §4, `:51` |
| — | Parcela, prazo mensal, margem | não existem no FGTS | — | Res. CCFGTS 958, art. 2º, §4º (`LEV/lev-regras.md` §2) |

**Comissão por tabela (o lado GL).** Hoje **não há fonte de comissão FGTS**:
- O fator do Go arquivado (TABELA NS 1,95 · CAMPANHA 1,50 · GOLD 1,15 · demais 1,00) é **peso de meta de vendedor**, não comissão (`FatoresMeta`, `src/gl-site-go/internal/domain/site/propostasfgts/types.go:356-385` ✔). Não serve de piso sem «sim» explícito do dono.
- O dono disse em 28/09: «% empresa e coeficientes: ainda não sabe»; faixa do coeficiente FGTS de 0 a 3 (`MEM:decisoes-fgts-coeficientes.md` itens 2 e 5). O editor está bloqueado (D19-11).
- A doc da Novo Saque traz `commission.commission_corban_value` (§3.1), que a casa **não lê** (`NS app/novosaque.py:307-309` ✔). Se vem por oferta antes da escolha: LC-03.
- Sem fonte, o motor não roda (NF-02).

### 5.2 Roteiro de negociação da IA para o FGTS (motor v0, por regra)

Mesmo princípio do CLT e do `ENT` §4: **o código decide o degrau; o modelo nunca vê tabela, coeficiente nem comissão.** **Emendado em 10/11 pelo `ENT` §0.3 (FG-NT-10…17), que prevalece onde divergir:** o export mostrou que o chatbot **já faz** o degrau NS → CAMPANHA (F3); a IA começa no degrau seguinte ao último que o chatbot mostrou (NS, ou CAMPANHA para quem passou pelo F3) e nunca reapresenta a CAMPANHA. Segue em aberto só o que o código de 26 linhas do F3 escolhe (LC-14).

| Id | Regra |
|---|---|
| **NF-01** | **Degrau 0 = a última tabela que o chatbot mostrou** na transação viva: TABELA NS (a que a operação contrata, 96,5%) ou CAMPANHA, se o lead passou pelo F3 (`ENT` FG-NT-10). |
| **NF-02** | **Candidatas** = outras tabelas da **mesma transação** (`success: true`), com TTL folgado e **comissão em R$ conhecida**: `commission_corban_value` da oferta (se vier, LC-03) ou coeficiente cadastrado pelo dono no editor FGTS (faixa 0–3). Sem comissão conhecida = fora; sem nenhuma fonte, o motor fica desligado. Sem re-simular: as 9 já vieram. |
| **NF-03** | Só sobe um degrau depois de objeção codificada `valor_baixo` (ou recusa da oferta com esse motivo). Nunca na 1ª apresentação, nunca por «vou pensar», nunca por iniciativa da IA. |
| **NF-04** | **Ganho mínimo ao cliente:** Δ liberado ≥ 5% e ≥ R$ 20 contra o degrau atual (padrão; Q-FG-04). |
| **NF-05** | **Ordem (= `ENT` NT-23):** entre as que passam no ganho e no piso, a de **menor custo por real dado** = Δcomissão ÷ Δliberado (Δ contra o degrau atual); empate, maior ganho ao cliente. |
| **NF-06** | **Piso de rentabilidade:** comissão da candidata em R$ ≥ X (Q-FG-03) **e** ≥ p% da comissão da NS (padrão p a decidir; o 85% do CLT, `ENT` Q-02, é referência). A ZERO nunca entra no v0. |
| **NF-07** | **Um degrau por atendimento no v0.** Pela tabela de faixas do `ENT` §4.3, um ticket FGTS cai em «baixa» (< R$ 150) e teria **0** degraus. O FGTS precisa de faixas próprias (Q-FG-05). |
| **NF-08** | **Nova confirmação a cada degrau.** O hash leva `transaction_id`, `simulation_id`, `table_name`, liberado, nº de anos e o hash da chave Pix (nunca a chave). Outra tabela ou outra transação invalida. |
| **NF-09** | **Antes de formalizar:** GET do contrato (API-02) com `simulation/Offer available`; `formalizacoes_desde(cpf)` sem contrato em `sign-contract`/`registry`/`disbursement` (inclusive `Awaiting formalization`: aí só reenviar o link); ledger da IA sem formalização aberta. 424 = nunca repetir, conferir pelo GET. |
| **NF-09b** | **Antes de re-simular** (IA ou robô do PF-02): a mesma trava de NF-09. A Novo Saque devolve oferta a quem já tem reserva (`NS app/ja_formalizado.py:4-9` ✔). |
| **NF-10** | Recusa depois do último degrau → encerra (E10) com nota curta; nunca «última chance». |
| **NF-11** | Anos antecipados (AL-03) **fora do v0** até o teste do PUT em sandbox. |
| **NF-12** | **Registrar a exposição desde o 1º dia:** tabelas elegíveis, mostrada, aceita, objeção, desfecho (pago/cancelado), braço do holdout. |

**Equilíbrio cliente × GL.** O total devido é o mesmo nas 9; o que o cliente ganha em liberado sai de algum componente da GL ou do banco (AL-02: HIPÓTESE). A conta do degrau é custo por real dado = Δcomissão ÷ Δliberado, e NF-05 escolhe o menor. Exemplo: A dá Δliberado R$ 20 por Δcomissão R$ 10 (0,50); B dá R$ 100 por R$ 20 (0,20): escolhe B. No v1, valor esperado = comissão(t) × P(aceite | t, contexto), com Thompson sampling dentro do piso (`ENT` §5.4).

**Vantagem do FGTS para aprender.** O `ENT` estima mais de um ano para a v1 no CLT só com a IA (~1–3 objeções/dia, `ENT` §5.4). No FGTS, **se** LC-08 mostrar centenas de FG-01 por dia, ~500 exposições pós-objeção caberiam em semanas (HIPÓTESE).

**Medição (holdout).** A conta-robô já fecha muito e o lead assina até 37,6 h depois (`NS app/propostas.py:475-479` ✔): sem grupo de controle, o ganho da IA não se separa da conversão natural.
- 10–20% dos FG-01/FG-03 elegíveis sorteados para **não** receber a IA (sorteio por hash da chave do episódio, gravado).
- `origem='ia'` obrigatório na API-17 desde o primeiro dia (hoje é opcional e nem todos os nós mandam).
- Métrica: pago em 7 dias, braço IA × braço controle.

### 5.3 Dados que precisam existir

| Id | Dado | Hoje | Proposta | Ligação com o `ENT` |
|---|---|---|---|---|
| DD-01 | **As 9 ofertas por transação, duráveis** | só a NS em `novosaque.propostas`; as 9 na ponte `esteira_guru` (3 d) e no resumo da auditoria (7–30 d), que **não guarda `insurance_amount` nem `commission`** (`NS app/novosaque.py:307-309` ✔) | tabela nova `novosaque.proposta_oferta` (uma linha por tabela por transação): `transaction_id`, `simulation_id`, `table_id`, `table_name`, liberado, total devido, `insurance_amount`, IOF, TAC, taxa, CET, `interest_value` (se vier), nº de anos, `commission` (se vier), instante, `escolhida`/`contratada`. Sem PII. Retenção 13 meses | é o `core.oferta_opcao` (NT-02) do FGTS, mas **fora do gl360** (decisão do dono de 28/09). Mesmas colunas de propósito, para migrar quando o RD-202 abrir |
| DD-02 | Comissão por tabela | sem fonte (§5.1) | (a) ler `commission_corban_value` se vier por oferta; (b) senão, o dono cadastra o coeficiente no editor `/coefficients/fgts` (faixa 0–3; bloqueado: rev. 37, roteiro `fgts-novosaque`, D19-11). O fator de meta do Go **não** entra sem «sim» explícito | `ENT` NT-24 (piso) |
| DD-03 | Exposição e resposta | não existe | passo `decisao` da IA (já existe no `ia-atendimento`) + campo `canal` + braço do holdout | `ENT` §5.3 |
| DD-04 | Tabela contratada | `valor_financiado` vem da ponte na formalização | gravar `simulation_id` contratado em DD-01 | `ENT` NT-13 |
| DD-05 | Candidatos sem PII | `/consultas` devolve PII | view `ia_candidatos_fgts` (FG-01/FG-03, com `tardia`) só com ids e o mínimo do canal; já aplica a trava `formalizacoes_desde` | `C` / contrato 04 |
| DD-06 | Chave estável do episódio | `transaction_id` rotaciona (PK; o antigo vai para `transaction_ids_anteriores`, `NSR:972-980` ✔, `NS init_propostas.sql:73` ✔) | chave = **primeiro** `transaction_id` da linha (o mais antigo de `transaction_ids_anteriores`, ou o atual se vazio); alternativa: `sha256(cpf_hash\|dia_SP\|chat_id)`. Documentar a rotação no contrato 05-NS | AN-03 |

---

## 6. Analogia CLT → FGTS para a IA

Veredito: **igual** · **muda** · **novo** · **n/a** (não se aplica). Detalhe item a item em `LEV/lev-analogia.md` §3–§8.

| Id | Item (CLT) | FGTS | Veredito |
|---|---|---|---|
| AN-01 | Gatilho «Amado não vendeu» → `zVuE` (delegação após 20 min) | FG-01/FG-03 lidos no `novosaque-fgts` + API-02; não existe `zVuE` FGTS | muda |
| AN-02 | Disparo a dedo, lead a lead, pelo braço n8n | igual, com view nova | muda (fonte) |
| AN-03 | Chave do episódio `venda:sha256(clt_job_id\|chat_id)` | `venda:sha256(tx_origem\|chat_id)`, com `tx_origem` = primeiro `transaction_id` da linha (DD-06); **não existe `proposta_id`** | muda |
| AN-04 | `gatilho: "venda"` no orquestrador | `gatilho: "fgts_pos_chatbot"`, `produto: "FGTS"`, `banco: "NOVO_SAQUE"` | muda (enum novo) |
| AN-05 | E0 pré-abertura (oferta FACTA válida, DATAPREV, `cpf_alterado`) | transação viva com `Offer available`; Caixa ok; sem DATAPREV; trava `formalizacoes_desde`; chatbot e humano fora do chat (API-37) | muda |
| AN-06 | E1 abertura TX-01 | duas aberturas por sinal (TX-F01a FG-01, TX-F01c FG-03), com variante `tardia` | muda |
| AN-07 | E2 entender (objeções parcela, prazo, valor) | sem parcela nem prazo; entram «e se eu for demitido?», «não sei usar o app», «já antecipei» | muda |
| AN-08 | — | **E2b destravar no app** (autorização, adesão, carência) | novo |
| AN-09 | E3 apresentar (valor, parcela, prazo, banco) | valor liberado e anos antecipados | muda |
| AN-10 | E4 ajustar com T5 (recalcular) | troca de tabela na mesma transação; sem T5 | muda (forte) |
| AN-11 | E5 coletar (Pix ou conta, CEP) | 7 campos, só Pix; endereço é default; o que o «FGTS FORM» já coletou é NÃO VERIFICADO (LC-15) | muda (menor) |
| AN-12 | E6 confirmação com hash | igual na mecânica; hash com tx e `simulation_id` | igual / muda |
| AN-13 | E7 digitar FACTA (assíncrono, conferir 20 min) | API-17; 424 nunca repete; conferência pelo mesmo tx | muda |
| AN-14 | E8 link e status | `contract_link` no GET; status `stage/summary_status` | muda |
| AN-15 | E9 vácuo (lembretes) | igual; ticket menor ⇒ 0 lembrete pago (HIPÓTESE) | igual |
| AN-16 | E10 encerramento → repasse ao `zVuE` | destino FGTS **não existe** | muda (bloqueia) |
| AN-17 | T1 identificar (360) | igual | igual |
| AN-18 | T2 estado (360 + ledger) | `novosaque-fgts` + ledger + API-37 | muda |
| AN-19 | T3 ofertas (`pessoas:propostas`) | API-12 / DD-01, projeção sem tabela ao modelo | muda |
| AN-20 | T4 consulta paga (FACTA) | re-simular = API-13 (abre transação; aviso precisa de destino novo); trava NF-09b antes | muda |
| AN-21 | T4a autorização (C6 liveness) | vira E2b, sem endpoint | muda |
| AN-22 | T5 simular | não existe | n/a |
| AN-23 | T6 coletar | menor | muda |
| AN-24 | T7 digitar | API-17 com `origem='ia'` obrigatório (FGTS fora do 360) | muda |
| AN-25 | T8 conferir | API-02 pelo mesmo tx (melhor que a FACTA; TTL ~3 d) | muda |
| AN-26 | T9 link · T10 status | `contract_link` · catálogo do robô operacional | muda |
| AN-27 | T11 enviar · T14 opt-out · T15 verificar · T16 mídia | iguais (T15 ganha regras: proibir «parcela», «desconto em folha», «seguro», promessa sobre saldo, «5 anos» fixo) | igual |
| AN-28 | T12 repassar | nota igual; destino indefinido | muda |
| AN-29 | T13 contexto (DATAPREV + health) | `/health` do `novosaque-fgts` + breaker de `cef_indisponivel` | muda |
| AN-30 | Contrato 03 (cliente360-api) | só T1 e credencial; nada de oferta | igual (parcial) |
| AN-31 | Contrato 04 (braço n8n, espelho) | view de candidatos nova | muda |
| AN-32 | Contrato 05 (facta-on) | **contrato 05-NS** novo para o `novosaque-fgts`, com transporte (§8.4) | novo |
| AN-33 | Contrato 08 (orquestrador) | enum, chave DD-06, sem `matricula` | muda |
| AN-34 | K devolução (vigia, livro, nunca chat mudo) | vale; sem destino, devolução mínima = religar o chatbot | muda |
| AN-35 | Textos: 41 TX | 17 iguais, 15 mudam, 9 n/a; +14 novos (TX-F01…F14), **aprovados pelo dono** (decisão de 30/10, sem jurídico); a adesão é pergunta de exceção (Q-FG-11) | muda / novo |
| AN-36 | Motor R1 (FACTA, maior `coef_valor`) e R9 de tabelas do `ENT` | NF-01…NF-12 com as emendas FG-NT-10…17 do `ENT` §0.3 (escolha do F3 aberta, LC-14) | muda |
| AN-37 | Faixas de esforço por comissão | faixas próprias do FGTS | muda |
| AN-38 | Fallback de banco (n) | um banco só | n/a |
| AN-39 | Janela DATAPREV | Caixa lenta ou fora | n/a / novo |
| AN-40 | Gatilho M «agendar assinatura» | serve para FG-03 e FG-05 | igual |
| AN-41 | Atribuição: digitador Amado + marca `ia` em `core.contrato` | campos `digitador_proposta`/`vendedor`/`origem` da API-17; `origem` vira obrigatório para a IA; nada no 360 | muda |
| AN-42 | Canal: usuário Amado Batista no ChatGuru | igual (Q-FG-07) | igual |
| AN-43 | Duas vozes: chatbot e robô CLT | chatbot MBURA + «negou ns» (F3, ativo) + robô operacional FGTS + fluxo 2 do n8n | muda (mais vozes) |

---

## 7. Lacunas e o que não foi verificado

| Id | Lacuna | Por que importa | Como fechar |
|---|---|---|---|
| LC-01 | **Fluxos FGTS do n8n de produção, com a lógica.** **Em parte fechada em 10/11**: a estrutura (nós, tipos, ligações, hosts) está em §2 e §4.1. **Continua aberto:** condição de cada IF/Switch, corpo de cada HTTP (qual tabela vai no campo e qual `simulation_id` na formalização), código dos nós Code (F3: 26 linhas; F4: 721; F5 `normaliza dados`: 208), tempos dos Wait, destino real das rotas do gateway | qual tabela mostra e formaliza, quando desiste do laço do link | comando do §7.1 (o dono roda), agora só para os ids F1–F5 |
| LC-02 | Árvore de diálogos «MBURA - FGTS» no ChatGuru | texto e ação de cada diálogo (delegação, departamento) | `POST /chatguru/rpa/dialogos/sincronizar` e leitura de `chatguru.dialogos` (só nome, ordem e ação; sem texto de cliente) |
| LC-03 | `commission` vem **por oferta** (em `simulation_results`) e antes da escolha? `commission_corban_value` vem preenchido? | sem isso, NF-02 não tem fonte e o motor fica desligado | resumo **sem PII** de um contrato real (só as chaves e se `commission` é nulo por item), ou pergunta à Novo Saque |
| LC-04 | Forma crua de uma oferta de cada tabela (só chaves e sinais: nulo, positivo) | nomes das 9 tabelas hoje; o que é `insurance_amount` (seguro ou juros, AL-02) | contagem por `table_name` + forma de chaves no resumo da auditoria ou em `esteira_guru`, sem CPF |
| LC-05 | API-03 (re-simular anos): em que `stage` vale para FGTS? | alavanca AL-03 | teste em **sandbox** (`api.novosaque.dev.br`) com chave de sandbox e CPF de teste |
| LC-06 | Custo por simulação | E2b, robô de re-simulação e IA abrem transação | contrato comercial / Novo Saque |
| LC-07 | Nome da instituição no app do FGTS | texto TX-F03 | Novo Saque |
| LC-08 | **Funil pré-aprovado → formalizado → assinado por transação** | tamanho real de FG-01/FG-03; portão de FF-1 e FF-3 | agregado sem linhas: `novosaque.propostas` (`simulada`, por dia) × `formalizacoes_desde`/auditoria × API-02 por amostra × `proposta_evento`; separar `tardia` |
| LC-09 | Robô operacional do servidor antigo ainda em `real`? Regras do novo ligadas? | duas vozes no chat | `SELECT` em `novosaque.robo_regra` (ativas) e estado do robô antigo |
| LC-10 | Código das edge functions `validador-cpf-timer-fgts` e `reprova-24h` | entrada e marca. Desde 10/11 se sabe que **nenhum fluxo FGTS do n8n chama :8126** (os nós `reprova-24h` só existem no F6, CLT, e soltos); a marca só é gravada pelo `novosaque-fgts` (`NS app/reprova24h.py:97-98`) | exportar do edge-runtime (:8126) |
| LC-11 | Textos regulatórios oficiais (Res. CCFGTS 1.130/2025, prorrogação de 29/10/2026, teto de 1,80%) | textos ao cliente | DOU / Conselho Curador (as páginas da Caixa não abriram; o teto só tem fonte secundária, `LEV/lev-regras.md:52`) |
| LC-12 | Onde mora o schema `novosaque` (n8n-db da S2 × Postgres da VPS) | onde fica DD-01 | `\dn` no n8n-db |
| LC-13 | Destino do lead quando a IA FGTS falha | E10 | Q-FG-06 |
| LC-14 | **«FGTS - negou ns (passa campanha)».** **Existência e forma fechadas em 10/11**: ativo na S2, 7 nós, linear, sem decisão; lê a transação no :8104, código de 26 linhas, grava campo, espera, dispara diálogo (P10b). **Continua aberto:** o que o código escolhe (sempre a CAMPANHA? checa se ela existe?) e o diálogo que dispara o fluxo («negou» = lead recusou: HIPÓTESE preferida) | o degrau NS → CAMPANHA **é** do chatbot; o motor v0 precisa excluir ou avançar quem passou pelo F3; Q-FG-02 segue suspensa até o código | código do F3 pelo §7.1 + diálogo de origem (LC-02) + execuções do F3 por dia |
| LC-15 | Onde ficam os dados parciais do «FGTS FORM» quando o lead para no meio. **Em parte fechada em 10/11**: nos **campos do ChatGuru** (Pix pelo F4; nome e nascimento pelo F2/F5) e no **360 novo** (`pessoas:ingestoes`: telefone, nome, nascimento). O F5 não pergunta nome nem nascimento ao lead (FATO-E). **Aberto:** quais campos exatamente (corpo dos HTTP) | a IA não pode pedir de novo o que já foi dado, nem confiar no que não leu | §7.1 (corpo dos HTTP do F2/F4/F5) + `GET /chatguru/campos` |
| LC-16 | Em quanto tempo a Novo Saque cancela o link não assinado? O `contract_link` continua válido para reenvio? | janela do FG-03 | pergunta à Novo Saque |
| LC-17 | Reconciliar tardias: >50% em 21/10 × 4,1% numa medição anterior de 7 dias, com a mudança de contagem de 23/10 | tamanho de `tardia` no FG-01 | LC-08 separando `tardia`; registrar a data da medição de 4,1% |

### 7.0 O que fechou com a exportação de 10/11

Fonte: estrutura dos 7 fluxos exportada pelo dono (`/home/danilo/fgts-estudo/n8n/fluxos-fgts-estrutura.json`), analisada em `LEV/lev-n8n.md` §3.

| Lacuna / afirmação | Fechou? | O que a estrutura diz | Prova |
|---|---|---|---|
| LC-14 / P10b «negou ns» existe e está ativo? | **sim** (existência e forma) | ativo, linear, degrau NS → CAMPANHA determinístico | `n8n:FGTS - negou ns (passa campanha)/*` |
| P13 quem envia o link | **sim** | F5, por mensagem, e cadastra no NewCorban | `n8n:FGTS FORM/passa link form`, `cadastra newcorban` |
| P10 / PF-04 o que vai na oferta tardia | **sim** (forma) | o mesmo diálogo de pré-aprovado; nenhum nó distingue | `n8n:FGTS - resultado assíncrono (fluxo 2)/Tem margem?` |
| P09 como o n8n mostra a oferta | **sim** (forma) | valor num campo do ChatGuru + diálogo; qual tabela: aberto | `n8n:FGTS - resultado assíncrono (fluxo 2)/Adicionar valor ao campo` |
| PF-07 mensagem quando a formalização falha | **sim** | idade → diálogo; qualquer outro erro → `Stop and Error`, nada ao lead | `n8n:FGTS FORM/idade acima do limite?` |
| P19 / H2 repasse de pré-aprovado parado | **sim, no n8n** | não existe no n8n; se existir, é do ChatGuru (LC-02) | ausência |
| «Followup 2 FGTS» | **sim** | não existe mais na S2 | ausência; `scripts/exportar-n8n-fgts.sh:11` |
| P05 `reprova-24h` e 360 antes da consulta | **sim, era erro** | nenhum dos dois na entrada; 360 só depois da oferta (F2) e no F5 | `n8n:FGTS - gerar consulta inicial/*` |
| P06 / API-11 esteira síncrona pelo n8n | **sim, era erro** | nenhum fluxo FGTS ativo chama `POST /esteira`; só `/acompanhamento` | ausência; `n8n:FGTS - gerar consulta inicial/Acompanhamento NS` |
| PF-05 «re-simula até 10×» | **sim, era erro no assíncrono** | ninguém re-simula; `cef_indisponivel` é desfecho | `NS app/acompanhamento.py:29-31`; F2 sem reinscrição |
| Resumo 3 «nada do FGTS grava no gl360» | **corrigido em parte** | proposta não; **dado cadastral sim**, no cliente360-api | `n8n:FGTS FORM/registra telefone no 360` |
| API-40 FACTA no FGTS | **corrigido** | o n8n usa facta-off :8107 `/factaoff/base-offline` (base CLT), só para nome e nascimento | `n8n:FGTS - resultado assíncrono (fluxo 2)/consulta off facta`; `src/painel-dev/app/factaoff_teste.py:53,61` |
| API-17 quem chama a formalização | **HIPÓTESE forte** | `n8n:FGTS FORM/HTTP Request` (POST :8104) | §2 P12 |
| H1 rota `fgts` → consulta inicial | **quase** | volume bate; falta `gateway.rotas` | §2 P04 |
| LC-01, LC-15 | **em parte** | ver linhas acima | — |
| LC-09 duas vozes | **em parte** | o n8n não é voz do pós-contrato; vozes no chat FGTS: diálogos do ChatGuru, F2, F3, F4, F5 e o robô operacional | §4.1 |

**Continua aberto:** condição de cada IF/Switch, corpo de cada HTTP, código dos nós Code, destino real das rotas do gateway, contagem de execuções por fluxo e por saída. Tudo sai do §7.1.

### 7.2 O que fechou com o mapeamento FF-0 de 10/11 (17:37)

Fonte: `scripts/mapear-fgts.sh`, rodado pelo dono (só leitura, com teto de tempo; saída local em `~/fgts-estudo/mapeamento/`, fora do git). Dois arquivos caíram no portão: os números com cara de CPF e de telefone eram trechos de UUID. Foram redigidos por script, sem abrir o conteúdo, e o portão voltou limpo. O efeito colateral é que a proteção também apagou as expressões longas do n8n (`$('nó').item.json…`). Por isso o campo exato que alguns nós leem continua aberto.

**LC-12, fechada.** O esquema `novosaque` (15 tabelas) está no mesmo banco do n8n (`n8n-db` da S2, banco `postgres`), ao lado de `n8n`, `gateway`, `chatguru` e `inappclt`. DD-01 (`novosaque.proposta_oferta`) ficaria ali.

**LC-03/LC-04: as 9 tabelas já são guardadas, e só uma coisa muda entre elas.**
- A resposta crua de cada simulação, com as 9 ofertas, fica em `novosaque.simulacoes.resposta`. O mapa `simulation_id → disbursed_amount` das 9 ofertas fica em `novosaque.esteira_guru.ofertas`, guardado por 3 dias.
- Medido pelo próprio serviço em 13.871 contratos: prazo, taxa e `total_loan_amount` são **iguais** nas 9 tabelas. Só o **valor liberado** muda (`init_propostas.sql:186-196`, `README.md:994-1001`).
- Logo, no FGTS a negociação entre tabelas é uma única troca: mais dinheiro para o cliente contra menos comissão para a GL. O cliente paga a mesma dívida em qualquer tabela.
- A `TABELA NS` é a referência da casa. Aparece em 100% dos contratos com oferta, é a contratada em 96,5% deles e **nunca** é a de maior valor. A de maior valor é a `ZERO`, que quase ninguém fecha.
- `propostas.valor_liberado` é o valor da NS. `propostas.valor_financiado` é o valor da tabela contratada. A diferença entre os dois já mede o que a negociação ganhou ou perdeu.
- **Continua aberto:** quanto a GL recebe em cada tabela. A rodada 1 leu a coluna errada (`esteira_guru.ofertas`, que é só o mapa de valores). A rodada 2 (`scripts/mapear-fgts-2.sh`) mede, nas últimas 24 h, as chaves de cada oferta, a comissão por tabela e a razão do valor de cada tabela sobre o da NS. Se `commission` vier vazia, a resposta depende da pergunta 1 à Novo Saque.

**As tabelas por simulação** (rodada 2 corrigida, 24 h, 1.689 simulações com oferta; LC-04 fechada):
- **São 10 tabelas, não 9.** As 10 vêm em **100%** das simulações com oferta.
- Ordem pelo valor liberado ao cliente (razão sobre a NS, mediana):

  | Tabela | Razão sobre a NS | Liberado médio |
  |---|---|---|
  | IMBATIVEL | 0,90 | R$ 72 |
  | **TABELA NS** | 1,00 | R$ 80 |
  | **CAMPANHA** | 1,10 | R$ 88 |
  | DIAMANTE | 1,19 | R$ 95 |
  | **GOLD** | **1,29** | **R$ 103** |
  | MONEY | 1,39 | R$ 111 |
  | LIGHT | 1,48 | R$ 118 |
  | SOFT | 1,58 | R$ 126 |
  | SMART | 1,68 | R$ 134 |
  | ZERO | 1,87 | R$ 149 |

- Os degraus são regulares, de cerca de 9,7% do valor da NS cada. A escada decidida pelo dono (NS → CAMPANHA → GOLD) **pula a DIAMANTE**. Ela entrega ao cliente +29% sobre a NS e +18% sobre a CAMPANHA.
- **O que é igual entre as tabelas:** taxa de juros mensal, parcelas, total devido, IOF e TAC (sempre nula).
- **O que muda:** valor liberado, `insurance_amount` e o CET.
- **HIPÓTESE:** a parte da GL está em `insurance_amount`. É uma conta: com o total devido igual, o que o cliente deixa de receber tem de ir para algum lugar. Confirmar na pergunta 1 à Novo Saque ou com uma conta de fechamento (total = liberado + `insurance_amount` + IOF).
- **A comissão não vem na oferta guardada.** Nenhum campo `commission` aparece nas 16.890 ofertas. Ou o envelope da casa corta esse campo, ou a Novo Saque não o manda no webhook. A comissão por tabela continua dependendo da Novo Saque (pergunta 1).

**O que se contrata hoje** (rodada 2, `propostas` de 30 dias):
- Das 49.161 pré-aprovações, 17.868 formalizaram.
- **991 (5,5%) fecharam uma tabela com valor maior que a NS** (é o degrau da CAMPANHA do F3).
- 8 fecharam com valor menor; o resto ficou na NS.
- A diferença média é de R$ 0,29 por proposta formalizada, porque quase todas ficam na NS.

A primeira versão da consulta das ofertas voltou vazia: no caminho assíncrono, as ofertas ficam em `simulacoes.resposta_enviada->'ofertas'`, separadas por slug e sem o cronograma (`NS app/acompanhamento.py:539-549`). A consulta foi corrigida, testada num Postgres descartável e precisa rodar de novo.

**LC-08: o funil, fechado** (agregado por dia, transações, `proposta_evento_dia`).

| Etapa (dia útil típico, 20–31/10) | Transações/dia | Taxa |
|---|---|---|
| Oferta disponível (`simulation / Offer available`) | ~2.800 | — |
| Contrato gerado (`create-contract`) | ~1.250 | ~45% das ofertas |
| Assinado (`Signed contract`) | ~1.100 | ~88% dos contratos |
| Pago (`Contract paid`) | ~950 | ~86% dos assinados |

- **FG-01 (pré-aprovado sem contrato): ~1.500 por dia útil.** Em `propostas`, que já tira repetição de CPF em 24 h: 22/10 teve 2.862 pré-aprovações e 1.267 formalizadas. O portão G-F1 (≥ 50 por dia) passa com folga de 30×.
- **FG-03 (formalizou e não assinou): ~150 a 200 por dia.** Confirma a hipótese de ~170.
- Entre 03 e 05/11 o funil ficou quase zerado: 0 a 12 ofertas por dia, enquanto os cancelamentos continuaram. O motivo não está nos dados (provável troca de credencial ou migração). Não usar esses dias como base.
- Recusas antes da oferta, de 03 a 09/11: saldo negado 67 mil, sem oferta 38 mil, timeout 11 mil, simuladas 10 mil. O principal motivo de «sem oferta» é `parcela_abaixo_minimo` (34 mil eventos), que é saldo pequeno e não dá para negociar. `falta_autorizacao_trabalhador` soma 32 mil eventos, o que confirma a perda na autorização do app.

**LC-14 (degrau NS → CAMPANHA): fechada na forma; resta um risco.**
- A escada do chatbot já existe na árvore do ChatGuru (`chatguru.dialogos`, grupo «MB URA - FGTS»):
  1. `1.1.6 - Não - NEGOU NS (depois de passar valor)` dispara o F3.
  2. O F3 lê o contrato cru no :8104, pega `[0].disbursed_amount`, grava o valor num campo, espera 45 s e dispara o diálogo.
  3. Se o lead recusa de novo, `1.1.6.1 - Não - NEGOU CAMPANHA`.
- **Risco (HIPÓTESE forte):** o F3 lê o **primeiro item** de um array do contrato cru, sem filtrar por `table_name` nem por `success`. O serviço avisa que esse array mistura ofertas e itens de falha (`NS app/novosaque.py:228-233`). Assim, o valor «da campanha» pode ser o de outra tabela, ou vir vazio. O caminho exato foi redigido pela proteção. Para confirmar, ver o nó `Code in JavaScript` do F3 no editor do n8n (leitura).

**Ponto de entrada da IA: agora é observável.** A falha da negociação pelo chatbot passa a ser um destes dois sinais:
- o lead chegou ao diálogo `1.1.6.1 - Não - NEGOU CAMPANHA`;
- o lead passou por `Follow Up - Depois de Passar Valor FGTS - Não Respondeu` (a sequência de lembretes 1, 2 e 3 já existe no grupo «Acompanhamento»).

Isso substitui a definição indireta do §4.3 para FG-01. A IA entra depois que **as duas tabelas do chatbot e os três lembretes** já foram tentados, nunca antes. O sinal vem do ChatGuru; contar quantos leads chegam a ele por dia é o próximo agregado (execuções do diálogo, sem conteúdo).

**LC-09 (robô e duas vozes): fechada.**
- `novosaque.robo_config` está em modo `real`, dispara nas etapas `sign-contract`, `registry` e `disbursement`, com teto de 200 envios por hora e janela de 24 h, 7 dias por semana.
- Das 88 regras, 13 estão ativas, todas de pós-contrato: averbação negada, limite excedido, TED devolvida, «não autorizou Novo Saque», reprovado na formalização.
- **Nenhuma regra ativa** cobre `simulation / Offer available` (FG-01) nem `sign-contract / Awaiting formalization` (FG-03). O robô não fala com quem a IA atenderia, então não há duas vozes nesses pontos.
- Em `mapeamento_dialogos`, 5 textos do banco ficam sem diálogo, entre eles `Aguardando autorização no app do FGTS` e `Temporary block…`. Hoje esses leads não recebem nada.

**LC-02 (árvore do ChatGuru): fechada na forma.** São 127 diálogos em 2 chatbots. Os do FGTS estão nos grupos «MB URA - FGTS» (pedir CPF, autorizar, dados corretos, Pix, NEGOU NS, NEGOU CAMPANHA), «MBURA - FGTS - NIVER» (mês de aniversário), «TIMERS URA FGTS» (lembretes de autorização e da URA inicial), «Acompanhamento» (lembretes depois de passar o valor), «ROBO OPERACIONAL» e «UTILIDADES» (delegar a consultores). Só nome, grupo e tipo; nenhum texto foi lido.

**LC-01/LC-15: avançaram, mas não fecharam.**
- O FORM formaliza com o `simulation_id` que vem do lead (`recebe lead`). Ou seja, a tabela formalizada é a que o chatbot gravou no campo, não uma escolha do n8n.
- Vendedor e digitador vão fixos como robô (`origem: 'ROBO'`). Os dados enviados à formalização são nome, nascimento, sexo, DDD, telefone e Pix.
- Os tempos de espera também foram mapeados: o FORM espera 3 min pelo link e depois 2 min por tentativa; o F2 espera 60 s e 10 min; o F3 espera 45 s.
- O campo exato que cada nó lê foi apagado pela proteção. Para fechar, basta abrir os nós no editor do n8n.

**Execuções em 7 dias.**

| Fluxo | Execuções | Erros |
|---|---|---|
| Consulta inicial | 139 mil | 920 |
| Resultado assíncrono | 132 mil | 2.082 |
| FORM | 3.887 | 7 |
| «Negou ns» | 2.881 (~410 por dia; recusas da NS que viram CAMPANHA) | — |
| Pix | 4.807 | — |

**Gateway.** As rotas `fgts`, `fgts-campanha` e `fgts-form` levam ao n8n local. Os caminhos foram redigidos. `fn-validador-cpf-timer-fgts` leva à edge function :8126.

### 7.1 Comando só-leitura para exportar os fluxos FGTS do n8n (versão única)

> 10/11: a estrutura já veio (pelo script antigo, sem parâmetros). O que falta é a **lógica**: rodar o comando abaixo, de preferência filtrando pelos ids F1–F5 (§2). **Cuidado:** o comando exporta o `path` dos nós Webhook, que é segredo funcional; retirar `'path',n->'parameters'->'path'` do SQL ou nunca copiar esse campo para estudo.

Esta é a **única versão** do export. O script `~/fgts-estudo/scripts/exportar-n8n-fgts.sh` fica **obsoleto**: descarta condições de IF/Switch, tempos de Wait, corpo do HTTP e código, e grava `.bruto.json` com os nós inteiros antes de filtrar (só apaga se o Python terminar).

Roda **na S2**, pelo dono, **fora do pico**. Grava JSON por linha em `~/export-n8n-fgts-AAAAMMDD.jsonl`. O que sai:
- fluxo: nome, id, ativo, data;
- nó: nome, tipo, desativado e **só** estes parâmetros, com redação no próprio SQL (nada bruto vai ao disco):
  - IF/Switch/Filter: `conditions`, `rules`, `mode`;
  - Wait: `resume`, `amount`, `unit`;
  - Set: `assignments`, `values`;
  - HTTP Request: método, URL, `jsonBody`, `bodyParameters`, `queryParameters`;
  - Webhook: método e path;
  - Code/Function: o código;
  - Execute Workflow: o id do fluxo chamado;
- ligações (só nomes de nós).

**Não sai:** `headerParameters`, `authentication`, `credentials`, `execution_data`, payloads. A redação troca `Bearer …`/`Basic …`, sequências de 24+ caracteres alfanuméricos, números de 10+ dígitos e e-mails. Não foi testado aqui (leitura barrada).

```bash
# 1) descobrir o schema (n8n ou public)
sudo docker exec -i n8n-db psql -U postgres -d postgres -X -At \
  -c "SELECT table_schema FROM information_schema.tables WHERE table_name='workflow_entity'"
# 2) export (trocar n8n. pelo schema achado)
F=~/export-n8n-fgts-$(date +%Y%m%d).jsonl
sudo docker exec -i n8n-db psql -U postgres -d postgres -X -q -At -v ON_ERROR_STOP=1 -f - > "$F" <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '60s';
WITH alvo AS (
  SELECT id, name, active, "updatedAt", nodes::jsonb AS nodes, connections::jsonb AS conn
    FROM n8n.workflow_entity
   WHERE name ILIKE ANY (ARRAY['%fgts%','%saque%','%anivers%','%novosaque%','%novo saque%','%negou ns%','%campanha%'])
      OR nodes::text ILIKE ANY (ARRAY['%8104%','%novosaque%','%fgts%'])),
nos AS (
  SELECT a.id, n->>'name' AS nome, n->>'type' AS tipo, coalesce((n->>'disabled')::boolean,false) AS desativado,
         CASE
           WHEN n->>'type' ~* '\.(if|switch|filter)$' THEN jsonb_build_object('conditions',n->'parameters'->'conditions','rules',n->'parameters'->'rules','mode',n->'parameters'->'mode')
           WHEN n->>'type' ~* '\.wait$' THEN jsonb_build_object('resume',n->'parameters'->'resume','amount',n->'parameters'->'amount','unit',n->'parameters'->'unit')
           WHEN n->>'type' ~* '\.set$' THEN jsonb_build_object('assignments',n->'parameters'->'assignments','values',n->'parameters'->'values')
           WHEN n->>'type' ~* 'httprequest' THEN jsonb_build_object('method',coalesce(n->'parameters'->'method',n->'parameters'->'requestMethod'),'url',n->'parameters'->'url','jsonBody',n->'parameters'->'jsonBody','bodyParameters',n->'parameters'->'bodyParameters','queryParameters',n->'parameters'->'queryParameters')
           WHEN n->>'type' ~* 'webhook' THEN jsonb_build_object('httpMethod',n->'parameters'->'httpMethod','path',n->'parameters'->'path')
           WHEN n->>'type' ~* '\.(code|function|functionitem)$' THEN jsonb_build_object('code',coalesce(n->'parameters'->'jsCode',n->'parameters'->'functionCode'))
           WHEN n->>'type' ~* 'executeworkflow' THEN jsonb_build_object('workflowId',n->'parameters'->'workflowId')
           ELSE '{}'::jsonb END AS p
    FROM alvo a, jsonb_array_elements(a.nodes) n)
SELECT json_build_object('k','FLUXO','id',id,'nome',name,'ativo',active,'atualizado',"updatedAt")::text FROM alvo
UNION ALL
SELECT json_build_object('k','NO','fluxo',id,'nome',nome,'tipo',tipo,'desativado',desativado,
  'p', regexp_replace(regexp_replace(regexp_replace(regexp_replace(p::text,
        '(bearer|basic)\s+\S+', '\1 <redigido>', 'gi'),
        '[A-Za-z0-9_.-]{24,}', '<redigido>', 'g'),
        '\d{10,}', '<n>', 'g'),
        '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '<email>', 'g'))::text FROM nos
UNION ALL
SELECT json_build_object('k','LIGA','fluxo',a.id,'de',src.key,'para',d->>'node','tipo',tipo.key)::text
  FROM alvo a, jsonb_each(a.conn) src, jsonb_each(src.value) tipo,
       jsonb_array_elements(tipo.value) lista, jsonb_array_elements(lista) d;
COMMIT;
SQL
wc -l "$F"; grep -ciE 'bearer [^<]|token|apikey|api_key|senha|password|secret' "$F"
```

A última linha conta palavras suspeitas: se der > 0, abrir e conferir antes de mandar. O `grep` acerta também nomes de campo inofensivos (`token` num path); a conferência é a olho.

**Execuções por fluxo (opcional, separado, fora do pico).** A S2 já teve incidente de carga (`MEM:decisoes-dono-26-10-pre-aprovacoes.md:39-40`), e `execution_entity` é grande. Só com teto de tempo:

```bash
sudo docker exec -i n8n-db psql -U postgres -d postgres -X -q -At -F $'\t' -v ON_ERROR_STOP=1 <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '30s';
SELECT e."workflowId", e.status, count(*) FROM n8n.execution_entity e
 WHERE e."startedAt" > now() - interval '24 hours'
   AND e."workflowId" IN (SELECT id FROM n8n.workflow_entity WHERE name ILIKE '%fgts%' OR name ILIKE '%negou ns%')
 GROUP BY 1, 2 ORDER BY 1, 2;
COMMIT;
SQL
```

Depois do export, a sessão procura no arquivo por `tabela_ns|campanha|zero|simulation_id|table_name|ofertas` para fechar LC-01, LC-14 e LC-15. Complementos sem PII: linhas `fgts*` de `gateway.rotas` (`path`, `destino`, `ativo`, `critico`) e `novosaque.dialogos_config` (nome → id).

---

## 8. Fases para começar a negociação via IA pelo FGTS

### 8.1 Convivência com o piloto CLT de 27–30/11

| Fato | Prova |
|---|---|
| Piloto CLT 27–30/11; congelamento 19/11 18:00; go/no-go 26/11 12:00 | `RG0911:108-117` |
| «Não pronto para atender cliente real»; 73 ALTO vivos; VPS não existe; «outro dia perdido acaba com o piloto real» | `RG0911:70-74` ✔ |
| Com 4 agentes nem o pacote ALTO cabe (r ≈ 0,47 < 0,49) | `RG0911:161-163` ✔ |
| A IA do piloto ainda não tem VPS, orquestrador no ar, nem entrada do canal medida | `RG0911:74-77` ✔ |
| O `ENT` já recomendou negociação **fora** do piloto e F0 em produção só depois de 01/12 | `ENT` §6.5 |

**Recomendação honesta.**
1. **Não trocar o piloto para FGTS.** O piloto CLT é a primeira vez que a IA fala com cliente; a base (orquestrador, ledger, vigia, portão do ChatGuru, devolução) é a mesma para o FGTS.
2. **A negociação começa pelo FGTS**, como o dono pediu, mas **depois do piloto e dos portões** do §8.3. Ainda não há prova de que o FG-01 exista em volume (§2) nem do que o degrau NS → CAMPANHA do chatbot (F3) escolhe (LC-14).
3. **Os maiores ganhos rápidos do FGTS talvez nem precisem de IA:** um robô de re-simulação para PF-02 (24% das consultas) e um lembrete de assinatura para PF-08. São regras, com freio, no próprio `novosaque-fgts`.
4. **Nada da trilha FGTS em produção antes de 01/12.** Até 19/11, só custo zero. Código local da trilha FGTS **não** disputa agentes com o pacote ALTO do CLT: só com agente realmente ocioso.

### 8.2 Fases

Estimativas em d-agente são chute, no padrão do ROT («1 d» = um dia de relógio de um agente com revisão). **Não são trabalho livre:** disputam os mesmos agentes do CLT.

| Fase | O que construir | Repositório | Quando | d-agente |
|---|---|---|---|---|
| **FF-0** Custo zero | dono roda o §7.1 (export **com lógica**); sessão lê e fecha LC-01, LC-02, LC-14, LC-15; perguntas à Novo Saque (LC-03, LC-05, LC-06, LC-07, LC-16); **medição LC-08 sem PII** (agregado por dia) | — (sessão + dono) | já (11–19/11), sem `!` em produção | 0,5–1 |
| **Portão G-F1** | LC-08 com perda pré-aprovado → formalizado medida; FG-01 elegível ≥ N/dia (padrão N = 50, depois das exclusões) | — | fim do FF-0 | — |
| **FF-1** Dados | DD-01 `novosaque.proposta_oferta` + gravação na esteira e no GET; DD-04; DD-06 (chave estável); rota sem PII `GET /novosaque/fgts/ia/oportunidade/{tx_origem}` (ofertas + estado + canal mínimo); view de candidatos FG-01/FG-03 (DD-05) com a trava `formalizacoes_desde` | `novosaque-fgts` (DDL no schema `novosaque`, com «sim») | depois de G-F1; código local antes, produção depois de 01/12 | 4–5 |
| **FF-2** Robôs sem IA | robô de re-simulação PF-02 (cadência +2 h/+1 d/+3 d/+7 d) com trava NF-09b, **teto diário ≤ 10% das consultas do dia** (~5 mil/dia sobre ~53 mil), máximo 4 tentativas por CPF, respeito à escada de bloqueio, **parada automática por carga da S2** (mesmos limiares do modo leve de 27/10: MemAvailable < 1,5 GB, load ≥ 18); lembrete de assinatura para `Awaiting formalization` parado (PF-08) pela regra do robô operacional; tudo em `sombra` primeiro | `novosaque-fgts` | dezembro, depois de 01/12 | 3–4 |
| **FF-3** IA FGTS em sombra | contrato 05-NS (com transporte, §8.4); emendas 04 e 08 (gatilho, chave DD-06, produto); adaptadores T2/T3/T7/T8/T9 para API-12/API-17/API-02; E2b; exclusões por API-37; motor NF-01…NF-12 em config (`negociacao_fgts`, desligado); textos TX-F **aprovados pelo dono**; F3 com personas FGTS; holdout desenhado | `ia-atendimento`, `novosaque-fgts`, braço n8n, contratos | **sem data**: só depois dos portões G-F3 (§8.3) | 8–10 |
| **FF-4** Piloto FGTS | FG-03 e FG-01 a dedo, teto 10–20/dia, 2 semanas, **holdout 10–20%**, `origem='ia'` obrigatório; registro de exposição desde o dia 1; v1 (Thompson) quando houver ≥ ~500 exposições pós-objeção | idem | **sem data** até os portões | 2 + acompanhamento |
| | **Total até o piloto FGTS** | | | **≈ 18–22** (disputando agentes com o CLT) |

Volume do FF-2 no pior caso (sem teto): ~60 mil pessoas/semana × 4 tentativas = ~240 mil consultas a mais por semana, +65% sobre as ~370 mil atuais. O teto de 10% é o freio padrão (Q-FG-10).

O gl360 não entra em nenhuma fase (decisão de 28/09); quando o RD-202 abrir, DD-01 migra para `core.oferta_opcao` (`ENT` NT-02).

### 8.3 Portões e caminho crítico

| Portão | Condição | Depende de | Libera |
|---|---|---|---|
| **G-F1** | LC-08 medido; FG-01 elegível ≥ N/dia (padrão 50) | FF-0 | FF-1 |
| **G-F3a** | Piloto CLT com go no relatório de 01/12 (VPS, orquestrador, ledger, vigia, portão do ChatGuru no ar) | piloto CLT | FF-3 |
| **G-F3b** | LC-01 fechado **com lógica** e LC-14 resolvida (o que o código do F3 escolhe e qual diálogo o dispara; a existência do degrau já está provada) | export §7.1 | FF-3 (motor) |
| **G-F3c** | LC-03 respondido (fonte de comissão) **ou** coeficientes cadastrados pelo dono | Novo Saque / dono | NF-02 |
| **G-F3d** | LC-16 respondido (janela do FG-03) | Novo Saque | FG-03 |
| **G-F3e** | Transporte VPS → `novosaque-fgts` decidido (§8.4) | dono | FF-3 |
| **G-F4** | FF-3 em sombra sem achado ALTO; holdout e `origem='ia'` funcionando | FF-3 | FF-4 |

**Caminho crítico externo:** as perguntas à Novo Saque (LC-03, LC-05, LC-06, LC-07, LC-16) não têm data de resposta. Enviar nesta semana (Q-FG-13); sem resposta, G-F3c/G-F3d travam o FF-3. Datas de FF-3 e FF-4 só depois de G-F1 e das respostas.

### 8.4 Transporte da IA até o `novosaque-fgts`

O serviço escuta só em loopback na S2, e o aviso do fluxo 2 só vai para hosts de loopback (`NS app/config.py:264` ✔). A IA vai rodar numa VPS que ainda não existe (`RG0911:74-75`). Duas saídas (Q-FG-16):
- **(a) A IA FGTS roda na S2**, ao lado do serviço: nada a abrir, mas disputa a carga da S2.
- **(b) VPS → S2** por rota nova no gl-gateway (token por origem, lista de permissão só das rotas da IA: API-12, API-16, API-17, rota de oportunidade) ou por túnel WireGuard; e o desfecho assíncrono por polling da IA (sem aviso fora do loopback) ou por `aviso_hosts` ampliado com «sim».

Riscos próprios do FGTS: formalização dupla sem chave (NF-09, NF-09b, PF-12); re-simulação em rajada estoura o bloqueio por CPF e a carga da S2 (FF-2); duas ou três vozes no chat (chatbot, «negou ns», robô operacional, fluxo 2); adesão ao saque-aniversário tem efeito jurídico para o trabalhador (a IA não induz, Q-FG-11); regra de anos muda em 31/03/2027 (texto nunca fixa «5 anos»).

---

## 9. Perguntas fechadas ao dono

| Id | Pergunta | Padrão recomendado |
|---|---|---|
| **Q-FG-01** | «Falha da negociação via chatbot» = só depois de haver oferta (FG-01 com `tardia`, FG-03)? | **Sim.** FG-04/05/06 numa 2ª fase; FG-07 quando o webhook por mensagem existir |
| **Q-FG-02** | A IA pode oferecer outra tabela que não a NS, com objeção de valor? | **Sim, 1 degrau depois do que o chatbot mostrou** (NS, ou CAMPANHA se passou pelo F3; `ENT` Q-FG-19), pela regra NF-05, nova confirmação. Ainda depende do código de 26 linhas do F3 (LC-14) |
| **Q-FG-03** | Piso de comissão por tabela? | **Comissão em R$ ≥ X** (X do dono), lida de `commission_corban_value` ou do coeficiente cadastrado no editor (0–3); sem fonte, motor desligado; ZERO nunca no v0 |
| **Q-FG-04** | Ganho mínimo ao cliente para subir de degrau? | **≥ 5% e ≥ R$ 20** no liberado |
| **Q-FG-05** | Faixas de esforço próprias do FGTS (ticket pequeno)? | **Sim**: 1 degrau e 0 lembrete pago em todas as faixas no v0 |
| **Q-FG-06** | Para onde vai o lead quando a IA FGTS também falha? | **Departamento «FGTS - Consultores»** com nota curta; sem consultor livre, religar o chatbot e encerrar |
| **Q-FG-07** | A IA FGTS fala como Amado Batista no ChatGuru, como a do CLT? | **Sim** |
| **Q-FG-08** | Guardar as 9 ofertas por transação no `novosaque-fgts` (DD-01), fora do gl360? | **Sim**, 13 meses, sem PII |
| **Q-FG-09** | Usar o fator de meta do Go (1,95/1,50/1,15/1,00) como comissão provisória? | **Não.** É peso de meta de vendedor, não comissão. Só com «sim» explícito do dono, rotulado como provisório e com data de validade |
| **Q-FG-10** | Construir antes o robô de re-simulação (PF-02) e o lembrete de assinatura (PF-08), sem IA? | **Sim**, em `sombra`, em dezembro, com teto ≤ 10% das consultas do dia, 4 tentativas por CPF e parada por carga da S2 |
| **Q-FG-11** | A IA pode orientar a adesão ao saque-aniversário (efeito jurídico para o trabalhador)? | **Não no v0**: só explica com texto **aprovado pelo dono** e repassa. Exceção à decisão de 30/10 («sem jurídico»)? padrão: **não pedir jurídico**, salvo o dono querer |
| **Q-FG-12** | O piloto CLT de 27–30/11 fica como está, e a trilha FGTS vai à produção só depois de 01/12 e dos portões do §8.3? | **Sim** |
| **Q-FG-13** | Pedir à Novo Saque: custo por simulação, `commission` por oferta, nome da instituição no app, PUT de anos no FGTS, prazo de cancelamento do link e reenvio? | **Sim**, nesta semana |
| **Q-FG-14** | Rodar o export do §7.1 (versão única, com lógica e redação) na S2, fora do pico? | **Sim**, antes de 19/11 |
| **Q-FG-15** | Nome, nascimento e sexo da formalização vêm do 360 (amplia D-29) ou a IA pergunta? | **A IA pergunta** no v0, salvo o que LC-15 mostrar já coletado e legível (não amplia D-29 antes do piloto) |
| **Q-FG-16** | A IA FGTS roda na S2 ou na VPS com rota pelo gateway? | **VPS + rota no gl-gateway** com lista de permissão e polling (sem abrir `aviso_hosts`); S2 só se a VPS atrasar |
| **Q-FG-17** | Holdout de 10–20% dos elegíveis sem IA e `origem='ia'` obrigatório na API-17? | **Sim**, 15%, desde o 1º dia do FF-4 |
| **Q-FG-18** | Portão G-F1: volume mínimo de FG-01 elegível por dia para seguir? | **N = 50/dia** depois das exclusões; abaixo disso, só FG-03 e os robôs do FF-2 |

### 9.1 Decisões do dono (10/11, noite)

- **Q-FG-12, Q-FG-08, Q-FG-14, Q-FG-13: o dono respondeu «recomendações», ou seja, aceitou o padrão das quatro.**
  - **Q-FG-12:** o piloto CLT fica como está. O FGTS só vai à produção depois de 01/12.
  - **Q-FG-08:** as 9 ofertas por transação serão guardadas no `novosaque-fgts` (DD-01), por 13 meses e sem PII. A IA só entra depois da escada do chatbot.
  - **Q-FG-14:** a parte deste item que já rodou é o FF-0 de 10/11 (§7.2). Falta a rodada 2 (`mapear-fgts-2.sh`), que o dono roda fora do pico, antes de 19/11.
  - **Q-FG-13:** as perguntas à Novo Saque vão nesta semana. Quem envia é o dono (texto em `~/fgts-estudo/estudo/perguntas-novo-saque.md`).
- **Q-FG-02, decidida pelo dono e diferente do padrão:**
  - A IA oferece **uma única tabela, a GOLD**, e só quando o lead recusou as duas primeiras tabelas do chatbot (NS e CAMPANHA).
  - **As outras seis tabelas não são oferecidas**, nem pela IA nem por outra via.
  - Na prática, a escada fica assim: NS (chatbot) → CAMPANHA (chatbot, fluxo F3) → GOLD (IA) → repasse (Q-FG-06).
  - O que muda no desenho:
    - O motor v0 deixa de escolher entre as 9 tabelas e passa a fazer uma única troca, sempre para a GOLD.
    - O piso de comissão (Q-FG-03) e o ganho mínimo (Q-FG-04) só valem para conferir se a GOLD existe e é válida naquela simulação.
    - A ZERO e as demais ficam fora de vez.
  - **Fechado pela rodada 2:**
    - O nome da tabela é `GOLD` e ela vem em 100% das simulações com oferta.
    - Ela libera 1,29× o valor da NS e fica entre DIAMANTE e MONEY.
    - Se algum dia a GOLD faltar, a IA não oferece outra tabela e repassa o lead.
  - **Ainda aberto:** quanto a GL deixa de ganhar na GOLD em relação à NS, para a conta do piso (Q-FG-03).
- **O dono confirmou «é a gold mesmo»**: a escada pula a DIAMANTE de propósito.

- **Q-FG-07, decidida pelo dono:**
  - Na trilha FGTS, a IA fala como **Fabio Junior**, o mesmo nome do chatbot do FGTS (a formalização já vai como `FABIO JUNIOR - MB`).
  - O CLT continua com Amado Batista.
  - Corpus anunciado pelo dono: conversas dos APROVADOS do FGTS com o chatbot, cobrindo quem formalizou com o Fabio e quem foi repassado ao consultor. Pode incluir leads que passaram pela URA do CLT.
  - Tratamento do corpus:
    - fica em pasta local, fora do git;
    - a PII é redigida por script antes de qualquer leitura;
    - a análise sai só em agregados;
    - nenhuma fala de cliente é publicada.

### 9.2 Escada e parâmetros configuráveis (pedido do dono, 10/11)

Literal: «isso deve ser configurável de fácil acesso e manutenção também. mesmo que não vá ajustar toda hora.» Nada da negociação fica fixo no código nem no n8n.

**Molde: o que já existe para o robô operacional do FGTS.**
- A aba `/roboopfgts` do `painel-dev` (`src/painel-dev/app/roboopfgts_edicao.py`) edita `novosaque.robo_config` (linha única) e `novosaque.robo_regra`.
- Só ADMIN da Authelia acessa.
- Antes de gravar, a tela mostra a revisão «antes → depois», com o que passa a falar com o cliente em vermelho.
- A gravação usa `SELECT … FOR UPDATE` com assinatura da linha.
- O serviço relê a configuração a cada 15 s, sem deploy.

A negociação usa o mesmo molde, numa aba nova («Negociação FGTS») ao lado dessa.

**Desenho (DD-04, papel; nada em produção antes de 01/12):**

| Peça | Onde | O que guarda |
|---|---|---|
| `novosaque.negociacao_degrau` | n8n-db da S2, junto do resto do `novosaque` | Uma linha por degrau: `ordem`, `table_name`, `quem` (`chatbot` ou `ia`), `ativo`, `texto_id`. Valor inicial: 1 = TABELA NS (chatbot), 2 = CAMPANHA (chatbot), 3 = GOLD (ia) |
| `novosaque.negociacao_config` (linha única) | idem | `ligada`, `modo` (`sombra` ou `real`), `holdout_pct` (15), `piso_comissao` (nulo enquanto não houver fonte), `teto_ia_dia`, `janela` (horários e dias), `destino_falha` (departamento), `historico`, `atualizado_por`, `atualizado_em` |
| Aba «Negociação FGTS» no `painel-dev` | mesmo processo do `/roboopfgts` | Editar a ordem, trocar a tabela de um degrau, desligar degrau ou IA, mudar holdout e janela. A tabela se escolhe de uma lista com as que **apareceram nas ofertas das últimas 24 h** (hoje, as 10), e não por texto livre. Revisão antes de gravar; só ADMIN |
| Rota de leitura no `novosaque-fgts` (:8104) | ex.: `GET /novosaque/fgts/contrato/{id}/degrau/{n}` | Devolve a oferta do degrau `n` **pelo `table_name` configurado**, filtrando `success`. Se a tabela não veio, responde «sem oferta» em vez de outro valor |

**Por que isso também corrige o risco do F3:**
- Hoje o fluxo «negou ns» lê `[0].disbursed_amount`, que é o primeiro item do contrato cru.
- Passando a chamar a rota do degrau 2, ele mostra sempre a tabela configurada, e nunca o primeiro item da lista.
- A troca da CAMPANHA, se um dia acontecer, vira um ajuste na tela e não uma edição no n8n.
- A IA chama a mesma rota para o degrau 3.
- Chatbot e IA passam a ler a escada **de um só lugar**.

**Travas:**
- **Tabela válida:** gravar um degrau com uma tabela que não apareceu em 24 h é recusado.
- **Ordem crescente:** um degrau com valor ao cliente menor que o anterior é recusado. A razão sobre a NS sai das ofertas medidas e evita, por exemplo, colocar a IMBATIVEL depois da NS.
- **Sem degrau vazio:** se a GOLD (ou o degrau da IA) faltar numa simulação, o lead vai para `destino_falha`, sem trocar de tabela por conta própria.
- **Histórico:** toda mudança fica em `historico`, com quem e quando. O rastro também vai para o log do painel (`[negociacaofgts]`).

**Custo (estimativa):** cerca de 1,5 a 2 dias-agente, dentro da FF-1. São 2 tabelas, a aba (cópia do molde do `/roboopfgts`), a rota do degrau e a troca do nó do F3. A troca do F3 é a única mudança no fluxo em produção e precisa do «sim» do dono por kit.

---

## 10. Notas da revisão

Revisão crítica de 10/11/2026 conferida item a item na fonte. Cópia da versão anterior: `/tmp/claude-1001/-opt-claude/4c346449-3b97-4843-b75a-28e60cb6e04a/scratchpad/ESTUDO-FGTS-antes-revisao.md` (temporária).

**Aplicadas (sustentam-se na fonte):**

| # | Correção | Conferido em |
|---|---|---|
| E1 | Tamanho do FG-01/PF-06 desconhecido; tabela com as fontes lado a lado; «~2/3» e «até ~2 mil/dia» retirados; LC-08 virou portão G-F1 | `NSR:435-444`, `~985`, `966-970`, `711`; `NS app/robo_evento.py:48-58` |
| E2 | FG-01 exige GET do contrato + `formalizacoes_desde` em todas as `transaction_ids_anteriores`; auditoria sozinha não basta | `NSR:1539-1543` («formalizados fora deste serviço»); `NS app/propostas.py:525` (4.292 consultas com `contract_number` em 7 dias) |
| E3 | Fator do Go = peso de meta; retirado como piso (NF-06, Q-FG-03, Q-FG-09) | `types.go:356-385` (`FatoresMeta`, «multiplicador» da meta); `MEM:decisoes-fgts-coeficientes.md` itens 2 e 5 |
| E4 | «Seguro ≈ 45%» rebaixado a HIPÓTESE; proibido «seguro» em texto ao cliente até LC-04 | `NS app/propostas.py:322-329`; exemplo `NSR:~397-404` (CAMPANHA com `insurance_amount: null`, total ≠ liberado + IOF) |
| E5 | NF-05 corrigida para o NT-23 (menor Δcomissão ÷ Δliberado); frase «NF-05 minimiza» apagada | contraexemplo aritmético da revisão |
| E6 | Volumes de diálogo tirados de P02/P03/PF-01; P03 corrigido (CLT INAPP 13.653 é o mais executado; amostra de repassados) | `levantamento/10-conducao-por-vendedor.md:108` |
| E7 | Chave AN-03 sem `proposta_id`; DD-06 com `tx_origem` | `NS init_propostas.sql:73`; `NSR:972-980` |
| E8 | «Com jurídico» trocado por «aprovado pelo dono»; adesão como pergunta de exceção (Q-FG-11) | `MEM:decisoes-dono-30-10-sem-juridico.md` |
| E9 | §7.1 refeito como versão única com lógica e redação no SQL; sem `isArchived`; sem bruto em disco; execuções separadas com teto de tempo e janela de 24 h; script obsoleto declarado | `scripts/exportar-n8n-fgts.sh` (grava `.bruto.json`, descarta parâmetros); `MEM:decisoes-dono-26-10-pre-aprovacoes.md:39-40` |
| B1 | P10b e LC-14 («negou ns (passa campanha)»); motor e Q-FG-02 suspensos | `src/_plan-material/paralelo/s3-runtime.md:659` |
| B2 | Holdout e `origem='ia'` obrigatório (§5.2, Q-FG-17) | `NS app/propostas.py:475-479`; `LEV/lev-chatbot.md` C9 |
| B3 | §8.4 transporte e Q-FG-16 | `NS app/config.py:264`; `RG0911:74-75` |
| B4 | LC-16; FG-03 só reenvia link; formalização nova proibida com `Awaiting formalization` vivo | `NS app/ja_formalizado.py:15-18` (a trava deixa passar esse caso) |
| B5 | NF-09b: trava antes de re-simular | `NS app/ja_formalizado.py:4-9` |
| B6 | LC-15 (dados parciais do FGTS FORM) | — (NÃO VERIFICADO, como a revisão disse) |
| B7 | FF-2 com teto, tentativas e parada por carga; pior caso registrado | `NSR:715-727`; `MEM:decisoes-dono-26-10-pre-aprovacoes.md:39-40` |
| §4 | Exclusão de humano por API-37 (delegação, chatbot ativo, fail-closed); «60 min» depende do webhook por mensagem; FG-02 fundido no FG-01 | `src/chatguru-api/README.md:165-182` |
| §5 | Calendário com portões (§8.3), sem data para FF-3/FF-4, caminho crítico externo, aviso de disputa de agentes | `RG0911:70-77,161-163` |
| 10 | Prova pública de P03 separada: doc Novo Saque só autorização; adesão e 90 dias na Agência Brasil | página da Agência Brasil lida em 10/11 («Prazo mínimo de 90 dias», «Apenas uma antecipação por ano», sem teto de juros) |
| 19 | Tardias: não reconciliáveis com o que há; LC-17 | `NSR:~985`, `1197-1206` |
| 21 | `fgts-form` com as duas fontes; DEVOLVE CONSULTOR com «sem contas de FGTS» e retry; resumo da auditoria sem `insurance_amount`/`commission`; «uma antecipação por ano» no resumo e em AL-07 | `n8n_regras.py:1106`; `completa_catalogo_do_antigo.sql:33-38`; `NS app/novosaque.py:307-309`; `LEV/lev-regras.md:51` |
| — | Prova de gateway trocada de `README:150-162` (genérica) para `README:337-338` + `conftest.py:77` | revisão, item 20 |
| — | Prova de «NS nunca a de maior liberado» ajustada para `propostas.py:279-283` | revisão, item 6 |

**Aplicadas com ressalva:**
- **E1, leitura «≈ 100%».** A igualdade 16.727 `Offer available` ≈ 16.721 `Awaiting formalization` vem do robô do servidor antigo, que acompanha propostas já registradas no Corban. HIPÓTESE: é viés de seleção (só vê transação que seguiu), não conversão de ~100%. Por isso a faixa ficou «~0% a ~65%» como a revisão propôs, mas o «≈ 100%» não é usado como evidência de que o FG-01 seja pequeno.
- **Comissão na doc (item 24).** Confirmado o `SimulationCommission` no schema, mas a doc só mostra `commission` em `contract_simulation_results` nos exemplos. Se vem por oferta antes da escolha não está provado: entrou como ressalva em §3.1 e em LC-03, e `commission_corban_value` é fonte **condicional**, não certa.
- **Teto de 1,80%.** A Agência Brasil não fala de teto; a fonte é secundária (meutudo, via `LEV/lev-regras.md:52`). Mantido com o rótulo «fonte secundária».
- **Agência Brasil, número de parcelas.** A página de 10/2025 diz «máximo de cinco parcelas no primeiro ano e três a partir de 2026»; a regra dos 3 foi adiada para 31/03/2027 (`LEV/lev-regras.md:47`, tnh1). Mantido «até 5» com o adiamento.
- **Padrões novos** (N = 50/dia no G-F1, holdout 15%, teto 10% no FF-2) são propostas desta revisão para o dono decidir, não fatos.

**Rejeitadas:** nenhuma no todo. Fica de fora só a leitura literal de que a conversão «pode chegar perto de 100%» (ver ressalva acima).

**Crítica final (10/11, olhos limpos).** Nenhum caminho de webhook nos dois estudos (`/home/danilo/fgts-estudo/scripts/checa-segredo-dois-estudos.sh`: os únicos trechos que batem são palavras do próprio nome do fluxo; nenhum segmento com dígito). Corrigido: nós do F2 = 48 e do F5 = 32 (o `LEV/lev-n8n.md` §0 diz 50 e 31; contagem refeita no export por `/home/danilo/fgts-estudo/scripts/checa-metadados-fluxos.sh`); nome do nó de `reprova-24h` do F6; §5.2, NF-01, AN-36, AN-43, Q-FG-02, §8.1 e G-F3b alinhados ao `ENT` §0.3 (o F3 existe; o aberto é só o que ele escolhe). No `ENT`, as citações `EFG:<linha>` viraram citações por seção (os números tinham ficado velhos depois da atualização do n8n).

**Não foi possível conferir:** a existência de `isArchived` por versão do n8n (a coluna foi retirada do comando por precaução); o conteúdo de `lev-chatbot.md` C9 além da linha citada; a data da medição de 4,1% de tardias.
