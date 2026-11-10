# Fase 4 — Crítico de completude (10/11/2026)

Só leitura. Fontes: `PLANO-REVISAO-0911.md` §2, §3b, §4, §8; `fase0/matriz-restricoes.md`; `fase3/consolidado.md` e `consolidado.json` (762 grupos);
`fase4/cobertura.md` e `fase4/L1..L6.md`; `fase3/cobertura.json` (campo `nao_lido`, 640 itens em 118 unidades); `fase0/unidades.json`;
`fase0/baseline.md`; `fase3/canarios-achados.json`; `fase0/canarios-gabarito.txt`. Scripts desta leitura:
`scripts/fase4-completude-1.sh` (RS × grupos, `nao_lido` por unidade), `-2.sh` (localização de trechos), `-3.sh` (RG por estado, gabarito do canário 1).
Nenhum dado de pessoa aparece aqui; tudo é forma, contagem ou caminho.

Resumo em 8 linhas:
1. Das 7 perguntas do §2, **2 respondidas** (3 coerência do papel; 5 segurança/PII, com ressalva), **5 parciais** (1, 2, 4, 6, 7).
2. **RS-01..RS-20: todas têm achado verificado vivo** (confirmado ou confirmado em parte). Nenhuma está «atendida» por inteiro; 6 têm parte atendida com prova em código.
3. **O estado «PROVADO EM ENSAIO» está vazio na revisão inteira:** as unidades de execução F2-47 (kits) e F2-48 (check.sh ×3, PG descartável, `vistos`) nunca rodaram; o canário 5 (F2-46) também não.
4. Canários 1–4 rodaram (F2-C1..C4); a contagem de recall não foi registrada em lugar nenhum. Minha leitura: 3 reencontrados, 1 parcial, 1 não rodado.
5. Os 128 RG têm estado nas leituras F1-53..F1-58, mas em vocabulário heterogêneo e sem tabela única; o consolidado cita só 54 RG.
6. Costuras não cruzadas campo a campo: 9 (lista em §3), quase todas por repositório não exportado ou peça inexistente.
7. Dos 640 `nao_lido`, 12 grupos são materiais (§4); os demais são escopo de unidade, denylist ou produção.
8. 27 sondas só-leitura (§5) fecham as afirmações do consolidado que dependem de produção.

---

## 1. As 7 perguntas do §2 do PLANO

| # | Pergunta (PLANO §2) | Estado | Prova | O que falta |
|---|---|---|---|---|
| 1 | Atos de 09/11, bloqueio da B1.6b, efeito no calendário | **parcial** | `fase0/reconciliacao.md` §4 «Atos previstos para 09/11 e 10/11»; G-0079 (degrau de 1 dia fora do roteiro); G-0019 (cadeia B1.4>B1.6>B1.7>v0.3.0>#8 não fecha); G-0066 (B1.6b sem código) | Resposta do dono (§7.1 do PLANO) e leitura do Kan; nenhuma unidade leu Kan nem produção (F1-02, F1-03, F1-05, F1-54 em `nao_lido`). A decisão A/B/C/D/E de ritmo não está registrada como tomada (PLANO §8 «Ainda abertos: atos de 09/11, degrau de 1 dia, prioridade da fila Cliente360, leituras de produção») |
| 2 | Fechamento dos 128 RG e 32 D-nn em 4 estados + 20 AJUSTAR | **parcial** | F1-53..F1-58 dão estado por id (ex.: `fase1/leituras/F1-55.md:11-13` «**aberta**», «**só no papel**», «**com prova**»; `F1-54.md:20` «**PARCIAL**»); F1-59 cobre D-nn; G-0081 (20 AJUSTAR sem dono nem data) | Tabela única 128 × {com prova, só papel, aberto, superado}: não existe. Vocabulário diverge entre leitores («PARCIAL» não é um dos 4 estados). O consolidado só cita 54 RG em grupos (`fase4-completude-3.sh`). Triagem item a item dos 20 AJUSTAR: não feita |
| 3 | Coerência do papel | **respondida** | 48 ALTO vivos, a maioria de papel (G-0004, G-0009, G-0017, G-0050, G-0054, G-0062, G-0063, G-0075, G-0079, G-0096) | — |
| 4 | Código × contrato bloco a bloco + costuras com os dois lados | **parcial** | F2-01..F2-41 e F2b-01..F2b-09 | Nenhum teste executado (todas as F2 declaram «nenhum teste foi executado»); 4 costuras leram só um lado porque a regra «não ler relatório de outra unidade» bloqueou a entrada obrigatória (achado C-03); 9 costuras sem cruzamento (§3) |
| 5 | Segurança e PII pela matriz, três estados | **respondida com ressalva** | RS-01..RS-34 com grupos verificados (tabela §2) | O estado «PROVADO EM ENSAIO» não ocorre em nenhuma RS (F2-47/F2-48 não rodaram, C-01); histórico git nunca varrido (C-02) |
| 6 | Kits: ensaio/nunca rodado/irreversível por passo; idempotência; interrupção; desfazer; sha256 | **parcial** | Leituras F2-34..F2-38; G-0110 (kit não confere sha256), G-0753 (desfazer interativo), G-0525, G-0754 | Nenhum ensaio rodado (F2-47 ausente): «2× seguidas», «interrompido no meio» e «desfazer» são só leitura. A coluna «provado em ensaio local» da tabela por passo está vazia |
| 7 | O que falta para conversar ponta a ponta + premissas externas | **parcial** | 99 grupos «não existe» (consolidado §«Peças que não existem»); `fase0/premissas.md`; G-0019, G-0068, G-0129, G-0123 | Não há uma cadeia única ordenada «evento → turno → ferramenta → envio» com a peça faltante em cada elo; premissas (ChatGuru por mensagem, Fireworks ZDR/preço, cookie RPA, Dataprev) aparecem espalhadas (G-0068, G-0260, G-0619, G-0665), sem a árvore de decisão pedida no §4 Fase 5 |

---

## 2. RS-01..RS-20: achado verificado, prova de atendimento, lacuna

Contagens: grupos do consolidado cujo campo `rs` cita a RS (`fase4-completude-1.sh`). «Vivos» = confirmado ou confirmado em parte.

| RS | Grupos (vivos) | Achado verificado mais grave | Parte atendida com prova | Lacuna (nem achado nem prova) |
|---|---|---|---|---|
| RS-01 host só-EUA | 13 (8) | G-0016 ALTO; G-0416, G-0480, G-0569 MEDIO | `IA/src/ia_atendimento/config.py:27` `HOSTS_DO_MODELO = frozenset({"us.api.fireworks.ai"})`, `:239-240` recusa fora da lista; `:43` roteador `-us` | Rede/egress da VPS: NÃO EXISTE (G-0013) |
| RS-02 nada Anthropic/DeepSeek oficial | 6 (6) | só BAIXO (G-0334, G-0386, G-0730) | `config.py:31` `DOMINIOS_PROIBIDOS`, `:33-34` padrão do modelo e termos proibidos | — |
| RS-03 CPF fora de modelo/log/span/banco | 24 (15) | G-0085 ALTO (máscara de log sem chamador); G-0101 MEDIO | — | Canário ponta a ponta (G-0532, NÃO EXISTE); `procrastinate_jobs.args` por execução: nunca medido (F2-48 ausente) |
| RS-04 CPF só em memória | 6 (2) | G-0152 MEDIO | leitura F2-12 (gateway B5.1) | Leitor real e integração ao ledger: NÃO EXISTE |
| RS-05 AES-GCM, chave mensal, descarte | 9 (7) | G-0084, G-0097 ALTO | cifra/AAD lidas em F2-05 | Descarte: NÃO EXISTE (G-0401) |
| RS-06 livro de retenção | 18 (15) | G-0005 ALTO; G-0271, G-0395 MEDIO | — | Phoenix, pgBackRest, `gateway.payloads` vivos: sondas §5 |
| RS-07 inventário de segredos | 18 (15) | G-0016, G-0097 ALTO; G-0405 MEDIO | — | Onde os valores moram (Coolify, backups): sondas |
| RS-08 escrita só por kit com ensaio | 40 (37) | G-0008, G-0011, G-0015 ALTO | — | **Nenhum ensaio rodado na revisão** (C-01) |
| RS-09 janela 08–20, DATAPREV | 14 (9) | G-0063 ALTO; G-0086 ALTO NE | calendário lido (F2-11) | Ponto de envio: NÃO EXISTE |
| RS-10 T7 em dúvida não repete | 26 (19) | G-0087, G-0127, G-0131 ALTO | — | — |
| RS-11 batimento fail-closed | 13 (10) | G-0020, G-0022, G-0032, G-0074 ALTO | — | Inteira NÃO EXISTE no código |
| RS-12 papéis e pg_hba | 18 (16) | G-0049, G-0274, G-0523, G-0575 MEDIO | — | **Matriz papel×tabela×privilégio por `has_table_privilege` em PG descartável: nunca medida** (F2-48 ausente; F2b-09 declara «matriz desta leitura» sem a medição) |
| RS-13 segredos/PII em repositório | 13 (12) | G-0085, G-0118 ALTO | gitleaks dir: 0 em 7 alvos (`fase0/baseline.md` tabela a) | **Histórico git nunca varrido** (C-02) |
| RS-14 teste × real | 12 (11) | G-0005 ALTO; G-0014, G-0508 MEDIO | trava `_regra_do_canal_de_teste` (PLANO §8) | Quem tem o token de teste no ChatGuru: sonda |
| RS-15 flags FACTAON_* | 10 (9) | G-0017 ALTO | — | Valores vivos: sonda |
| RS-16 hide_input_in_errors | 7 (7) | G-0085 ALTO; G-0402 MEDIO | `config.py:78` `hide_input_in_errors=True`; `:276` `errors(include_input=False…)` | — |
| RS-17 log F07 | 8 (7) | G-0085 ALTO; G-0108 ALTO NE; G-0531 MEDIO | — | nginx do vhost WG: sonda |
| RS-18 deploy só por tag | 5 (5) | G-0016, G-0094 ALTO; G-0467 MEDIO | — | Config do Coolify: sonda |
| RS-19 teste nunca alcança FACTA real | 9 (7) | G-0107, G-0126, G-0428 MEDIO | — | Executores: NÃO EXISTE |
| RS-20 só a FACTA digita | 5 (5) | G-0088 ALTO | — | Executor de T7 e critério E0: NÃO EXISTE |

Nenhuma RS-01..RS-20 ficou sem achado nem prova. As lacunas reais são de **método** (ensaio e varredura de histórico não rodaram), não de leitura.

---

## 3. Costuras que ninguém cruzou campo a campo

| # | Costura | Por que não foi cruzada | Prova (`nao_lido`) | Efeito |
|---|---|---|---|---|
| K1 | orquestrador → **chatguru-api** (`/chatguru/mensagem`, `/nota`, assumir/restaurar) | repositório `chatguru-api` não exportado; só o contrato 02 | F1-21 «Código do chatguru-api: não exportado»; F2b-07 «repo chatguru-api … não está no export» | Toda a saída ao cliente (G-0129 NE) e o ator 85 (G-0036) ficam só no papel dos dois lados |
| K2 | **ISKRA** ↔ ator 85 / `pg_hba.matriz.tsv` | ISKRA não exportado | F1-20, F1-48, F2-37 | G-0348 «ISKRA único escritor sem prova» segue aberto |
| K3 | **gl-painel/painel-dev** ↔ `gateway.rotas` (quem edita `corpo_campos`) e ↔ `gateway.payloads` (quem apaga aos 7 d) | painel não exportado | F1-13, F2-26, F2-27, F2-34, F2b-01 | O «7 d» do sumidouro (G-0014/G-0508) e a invariante das rotas ia-* (G-0188) dependem de código que ninguém leu |
| K4 | orquestrador ↔ **cliente360-web** (BFF, zod, `PAINEL_IA_OPERADORES`) | web não exportado (MANIFESTO «DIFERENTE») | F1-02, F1-19, F1-22, F1-38, F1-40, F2b-06 | RS-22 e RS-27 só no papel |
| K5 | facta-on **PR #49** (tap, `log_acesso.py`) ↔ contrato 05 | ramo não exportado | F0-1; F2-32; F1-20; F1-53 | RS-15/RS-17 lado facta-on NÃO VERIFICÁVEL na revisão |
| K6 | **mappings do dublê** ↔ fixtures do orquestrador e `stubs_b.py` | denylist | F2-29, F2b-05 «persona transitória … não confirmei» | Só por `piiscan`; o piiscan não serve de portão (G-0103) |
| K7 | **vigia S2/batimento** ↔ orquestrador; **n8n do braço** ↔ `ia-repasse` | peças inexistentes | F2b-03 §4–§6; F1-15 | Critério de aceite (G-0123, G-0213) |
| K8 | `ia-repasse` **01 §4.2** ↔ `espelho_evento` da b1-6a | F2b-03 e F2b-07 declaram 01 §4.2 «não lido» | F2b-03, F2b-07 | **Fechado nesta leitura, sem achado:** `B16/src/ia_atendimento/espelho.py:17` `Evento = Literal["assumiu","pausou","retomou","encerrou"]` e `:19` `DesfechoEspelho` com os 8 valores de `contratos/01-gl-gateway.md:182`; `seq` monótono `:34`. O publicador (B1.6b) não existe |
| K9 | costuras F2b-04, F2b-05, F2b-08, F2b-09 e F2-40 **com o outro lado vindo das leituras F2** | regra «proibido ler relatório de outra unidade» contradiz a entrada obrigatória do roteiro da unidade | F2b-04 «F2-33.md … entrada obrigatória, mas a regra geral proíbe»; F2b-05 «Resultado de F2-32 … proibido»; F2b-08 «Resultados de F2-25, F2-06, F2-10 e F2-39: não lidos»; F2b-09 «Resultados de F2-17, F2-18, F2-37 e F2-48 … não lidos»; F2-40 «Relatórios de F2-35, F2-37 e F2-38» | Achado C-03 |

---

## 4. Os 640 `nao_lido`: o que é material

Agrupei por causa. «Material» = o leitor deixou de ler algo que pode mudar uma conclusão do consolidado.

| Grupo | Itens (aprox.) | Material? | O que faltou ler / fazer | Conclusões afetadas |
|---|---|---|---|---|
| M1 Execução proibida: «nenhum teste foi executado» | ~45 unidades F2 | **sim** | rodar `check.sh` ×3, suíte em PG descartável, ensaios dos kits (F2-47, F2-48 nunca rodaram) | «provado por teste» em todo o consolidado = teste **lido**; RS-08, RS-12; G-0076 (B1.6a+main nunca passaram juntas) |
| M2 Bibliotecas não exportadas (pydantic-ai 2.63, procrastinate 3.10, openai SDK, OTLP) | F2-04, F2-06, F2-09, F2-25, F2-39, F2-41, F2b-08, F2-C4 | **sim** | limite padrão de requisições por `run`, `trust_env`/proxy, o que o Procrastinate loga com os `args` do job | G-0412, G-0480, G-0085 (alcance real), RS-03 em `procrastinate_jobs` |
| M3 Repositórios não exportados (chatguru-api, ISKRA, gl-painel, cliente360-web, PR #49) | ~30 | **sim** | ver K1–K5 | G-0036, G-0129, G-0348, G-0188, G-0014/G-0508, RS-22, RS-27, RS-15, RS-17 |
| M4 Leitura cruzada proibida nas costuras | 5 unidades | **sim** | ver K9 | Tabelas campo a campo de F2b-04/05/08/09 |
| M5 Histórico git (commit 88d081a, tags v0.1.0/v0.2.0, base 9bee6a4 do #13) | F2-15, F2-20, F2-21b, F2-23, F2-24, F1-54 | **sim** | `git show`/gitleaks em modo git | G-0471 (CPF isento sem prova de ser sintético); RS-13 (C-02); lista real de conflitos do #13 |
| M6 Produção/Kan/Coolify/GitHub vivo | ~60 | sim, mas por desenho | sondas §5 | todo «NÃO VERIFICÁVEL» |
| M7 Cópia viva dos kits em `~/retomada-2809` × exportada | F2-35, F2-37, F2-38 | parcial | L4 cobriu o kit s4; gateway e config só por sha256 do MANIFESTO (F2-38 conferiu o de config) | RS-08 (G-0110) |
| M8 `REVISAO-GERAL-0411.md` lido só por blocos | F1-53..F1-58 | não | — | — |
| M9 Faixas de roteiro/contrato fora da unidade | ~200 | não, salvo 01 §4.2 (fechado em K8) e 04 §4 (espelho da S2, NE) | — | — |
| M10 Denylist (dialogos, personas, pessoas*.json, mappings, ia-corpus) | ~40 | não por agente | só `piiscan`/gitleaks; `piiscan` sem `PIISCAN_DENYLIST_KEY` (F2-49) | G-0103, G-0442, G-0738 |
| M11 Ferramentas Grep/Glob indisponíveis ou shell direto fora de script | F1-15, F1-53, F1-56, F2-07, F2-11, F2-14, F2-18, F2-19, F2-22, F2-33, F2-39, F2-40, F2-41 | baixo | F1-15 respondeu a pergunta 6 sem busca | rastreabilidade (C-05) |
| M12 Semgrep do gl-gateway e de `tests/` não rodou; sem auditoria de dependências; `insecure-defaults:audit` não rodou | F2-49, baseline | **sim** | linha de base do PLANO §4 Fase 0 | já em G-0539 (exceto `insecure-defaults`, que entra em C-01) |

Lacunas que **fechei lendo** (sem achado novo):
- F2-07 «não verifiquei se a mensagem de erro do `/readyz` pode citar o DSN»: `IA/src/ia_atendimento/prontidao.py:139-144` loga só `type(erro).__name__` e devolve código fixo (`banco_inacessivel`/`erro_de_consulta`). Fechado.
- F2-39 «a afirmação sobre o que chega à mensagem de ErroDoModelo fica sem prova»: `IA/src/ia_atendimento/agente.py:348-360` monta mensagens fixas («o provedor falhou (HTTP n)») e `:414` levanta fora do `except` («sem `__context__`»). Fechado.
- F2b-03/F2b-07 «01 §4.2 não lido»: K8. Fechado para o espelho; o lado repasse não existe.

---

## 5. Afirmações do consolidado que dependem de produção: sondas só-leitura

Todas para o dono rodar com `!`. Nenhuma devolve valor de cliente nem segredo: só nome, contagem, modo ou data.

| # | Afirmação (grupo) | Sonda |
|---|---|---|
| S1 | Atos de 09/11: rotas ia-* criadas? (§2.1; G-0079) | S2 `n8n-db`: `select path, ativo, corpo_campos is null as sem_allowlist, guardar_corpo from gateway.rotas where path like 'ia-%' order by 1;` |
| S2 | `env-gateway.sh --gravar` feito? | Coolify: listar **nomes** das variáveis `GATEWAY_*` da aplicação gl-gateway (sem valor) |
| S3 | Redeploy de 10/11 05:30 aconteceu? (PLANO §0.2) | S2: `docker inspect <gl-gateway> --format '{{.State.StartedAt}} {{.Config.Image}}'` |
| S4 | main do gl-gateway sem proteção (G-0070); D-09 | `gh api repos/GL-BUSINESS/gl-gateway/rulesets` e `…/branches/main/protection` (idem facta-on, ia-atendimento) |
| S5 | web faz deploy no merge (G-0004) | S3: `systemctl list-timers --all \| grep -c web-auto-deploy` |
| S6 | facta-on merge = deploy (G-0017, G-0018) | Coolify: auto-deploy da aplicação facta-on (liga/desliga); `gh api repos/GL-BUSINESS/facta-on/hooks --jq '.[].config.url' \| wc -l` |
| S7 | Janela do `conferir` em produção (F0-4; RS-10) | `docker exec <facta-on> printenv FACTAON_CONFERIR_JANELA_MIN` |
| S8 | CPF em log do facta-on (G-0108) | `docker logs <facta-on> --since 24h 2>&1 \| grep -cE 'cpf=[0-9]'` (só contagem) |
| S9 | Rota do T7 alcançável pelo vhost WG (G-0127) | S2: `nginx -T 2>/dev/null \| grep -nE 'listen .*(8093\|8114\|8118)\|location .*(facta-online\|formalizar\|ia-repasse\|batimento)'` |
| S10 | `X-Forwarded-For`/`CF-Connecting-IP` no vhost (G-0560; 01 §4.2) | mesma saída do S9, `grep -n proxy_set_header` |
| S11 | Sumidouro guarda Post com PII 7 d e ninguém apaga (G-0014, G-0482, G-0508) | `select count(*), min(recebida_em), max(recebida_em) from gateway.payloads where rota = 'ia-sumidouro';` |
| S12 | Quem apaga `gateway.payloads` aos 7 d (K3) | `select min(recebida_em) from gateway.payloads;` (mais velho que 7 d = não há expurgo) |
| S13 | Execuções do sumidouro no n8n (G-0482) | n8n: `select count(*) from execution_entity where "workflowId" = '<id do ia-sumidouro>';` e `printenv \| grep -c EXECUTIONS_DATA` |
| S14 | Quem escreve em `gateway.rotas` (G-0188) | `select grantee, privilege_type from information_schema.role_table_grants where table_schema='gateway' and table_name in ('rotas','ips_confiaveis');` |
| S15 | D-32: retenção do pgBackRest (G-0005, G-0329) | S4: `pgbackrest info` (só datas e tipos de backup) |
| S16 | D-32: retenção do Phoenix (G-0005) | Phoenix: política de retenção do projeto e `select min(start_time) from spans` em `ia_obs` (se existir) |
| S17 | Papéis e hba da S4 (RS-12; G-0523) | S4: `select rolname, rolcanlogin, rolconnlimit from pg_roles where rolname like 'ia\_%' or rolname='bkp_pg';` e `select type, database, user_name, address, auth_method from pg_hba_file_rules where 'ia_atendimento' = any(database);` |
| S18 | `bkp_pg` lê o schema `ia` (G-0523) | S4: `select has_schema_privilege('bkp_pg','ia','USAGE'), has_table_privilege('bkp_pg','ia.atendimento','SELECT');` |
| S19 | `/etc/ia-s4` (G-0097, G-0374, G-0574) | onde existir: `stat -c '%a %U:%G %n' /etc/ia-s4 /etc/ia-s4/*` |
| S20 | Senhas de login fora da S4 (G-0113) | S3/S4: `ls -la` do diretório de saída do kit s4 (só modos e nomes) |
| S21 | Secrets do registry (G-0466) | `gh api repos/GL-BUSINESS/ia-atendimento/actions/secrets --jq '.secrets[].name'` |
| S22 | Push protection / secret scanning (RS-13) | `gh api repos/GL-BUSINESS/<repo> --jq .security_and_analysis` nos 6 repos |
| S23 | CPF isento no histórico (G-0471) | local: `git -C <checkout ia-atendimento> show 88d081a \| <piiscan com denylist>` (só contagem e faixa) |
| S24 | Histórico dos 6 repos (C-02) | local: `gitleaks git --redact --report-format json` em cada checkout (só contagem por regra) |
| S25 | Faixa sintética de CPF não colide com cliente (G-0442, G-0738) | gl360: `select count(*) from <tabela de pessoas> where cpf like '000000%';` (só contagem) |
| S26 | Cookie do RPA vivo (G-0665; A1.13) | chatguru-api: `/health` do RPA (campo `valida`, sem cookie) |
| S27 | Corpus bruto apagado no gatilho (D-31) | `ls ~/ia-corpus/entrada \| wc -l` |

---

## 6. Achados desta leitura

| Id | Grav. | Título |
|---|---|---|
| C-01 | ALTO | Unidades de execução F2-47 (kits) e F2-48 (check.sh, PG descartável, `vistos`) nunca rodaram: «provado em ensaio» vazio |
| C-02 | ALTO | Histórico git dos 6 repositórios nunca varrido por gitleaks, contra o PLANO |
| C-03 | MEDIO | Costuras F2b-04/05/08/09 e F2-40 sem o outro lado: regra de isolamento bloqueou a entrada obrigatória |
| C-04 | MEDIO | Canário 5 não rodou e o recall dos canários 1–4 não foi contado; critério de parada da Fase 4 sem medida |
| C-05 | MEDIO | 128 RG sem tabela única nem vocabulário comum; consolidado cita 54 |
| C-06 | BAIXO | Leitores rodaram shell fora de script e sem Grep; rastreabilidade incompleta |

Detalhe e provas na saída estruturada.

Recall dos canários (minha leitura do gabarito × `fase3/canarios-achados.json`):
- C1 (pai de d0ddcb4, B5.1 A-1 «parada dura não alcança o efeito que espera a vaga do limitador», `docs/REVISAO-B5.1-0411.md:48`): **reencontrado** («Destino e pré-condições valem na hora de entrar na fila, não na hora do efeito»; «Fila do limitador por serviço não tem prazo»).
- C2 (pai de 34fafcf, agenda só aceita volta dentro do horário do dia): **reencontrado** («Janela do extrator não é cruzada com janela_mensagem.dias do calendário»; «horario_unico descarta calado o candidato fora da janela»).
- C3 (pai de a30fd2c, `[NUMERO:n]` com contagem de dígitos, hora com hrs/hs/min): **parcial** (achados vizinhos na máscara — data isenta, CPF partido —, nada sobre contagem de dígitos nem «hrs/hs/min»).
- C4 (pai de 35d22cf, exceção de ferramenta vira ErroDoModelo fixo): **reencontrado** («Exceção de ferramenta fora da lista escapa crua», ALTO).
- C5: **não rodado** (F2-46 sem leitura).
