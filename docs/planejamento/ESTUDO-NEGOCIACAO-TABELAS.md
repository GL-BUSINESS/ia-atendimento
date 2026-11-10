# Estudo: negociação entre tabelas e «N tabelas por lead» no 360

> 10/11/2026, revisado no mesmo dia (crítica independente + revisão final; ver «Notas da revisão» no fim). Só leitura: código da main exportado em `ia-negociacao/src/` (SHAs em `ia-negociacao/estudo/MANIFESTO.md`), planejamento da IA e memórias. Nenhum banco, ssh ou docker. Sem CPF, nome, telefone ou credencial.
> Base: os levantamentos `estudo/lev-c360.md`, `lev-facta.md`, `lev-c6-3rn.md`, `lev-ia.md`, `lev-ml.md`, `lev-web.md`, `lev-pedido-2.md`. Os pontos decisivos foram conferidos de novo nas fontes (scripts `ia-negociacao/scripts/conferir-negociacao-{1,2,3}.sh` e `revisao-final-{1,2}.sh`). Versão anterior guardada em `ia-negociacao/estudo/ESTUDO-NEGOCIACAO-TABELAS.antes-revisao-final.md`.
> **HIPÓTESE** marca o que não se prova com papel ou código. Esforço em **d-agente** é chute, como no ROT («1 d» = um dia de relógio de um agente com revisão, `ROTEIRO-DE-ACAO.md:34`). **Prazo de relógio** é outra conta (§6.6).

**Atalhos.** `src/` = `ia-negociacao/src/`. `H` = `estudos/semana-1/h-roteiro-conversa-memoria.md`. `F` = `estudos/semana-1/f-catalogo-ferramentas.md`. `ROT` = `ROTEIRO-DE-ACAO.md`. `RG0911` = `estudos/REVISAO-GERAL-0911.md`. `MEM:` = `~/.claude/projects/-opt-claude/memory/`.

**Pedido do dono (10/11).** Tabelas que não são cadastradas no 360; volta só uma. Quer negociar: quando o cliente recusa por valor baixo ou juros altos, oferecer outra tabela de coeficiente um pouco menor, que pode converter mais. Caso a caso, com aprendizado de máquina. Com roteiro, sem fechar com tabela ruim demais e sem gastar à toa. Primeiro passo: **salvar as outras tabelas no 360, por lead (N tabelas), para reciclar na IA.** Pedido complementar no mesmo dia: rotacionar entre bancos quando outro banco paga parecido e dá mais ao cliente (`estudo/lev-pedido-2.md:3`).

---

## 0. Resumo em 10 linhas

1. **Negociação entre tabelas não está no planejamento da IA.** Só existe a contraproposta dentro da mesma oferta (E4 + T5, R3/R4, até 3). Prova no §1.
2. **O «comece a salvar» já está atendido em forma crua desde 09/11:** o 360 grava N opções por consulta positiva em `core.observacao.ofertas` (jsonb, 1 a 20), e o que está lá se recupera depois por backfill. Faltam comissão, código de catálogo, leitura por lead e desfecho. **O que ainda se perde hoje:** a grade de prazos do C6, os outros prazos da FACTA quando a consulta pede 1 prazo (HIPÓTESE de que o n8n pede assim), os recálculos e as alternativas 3RN (§2.1).
3. **«Tabela não cadastrada» tem causa no código:** a fila de Pendências só lê a opção escolhida. Quando a tabela sem comissão **convive** com uma catalogada, ela perde a escolha e nunca vira pendência: o ciclo se fecha. Sozinha, sem nenhuma candidata com comissão, ela **é** escolhida e entra em Pendências. A negociação vive exatamente no primeiro caso (§2.2).
4. FACTA e C6 devolvem N tabelas numa consulta. O 3RN devolve 1 por vínculo; as outras regras são catálogo da conta, não do lead, e o recálculo nelas tem 2 defeitos (§2.1).
5. **Desenho:** tabela-filha nova `core.oferta_opcao` na S4, escrita só pelo ISKRA na mesma transação da observação, só no INSERT novo com desfecho `aplicada`, com comissão congelada pela mesma função da OP-CF-03; leitura nova por lead na API; web atrás de flag, web antes da API (§3).
6. **Roteiro:** escada por regra fixa. Só depois de objeção e de o T5 **falhar de fato** na tabela atual. Piso em **comissão em R$**, teto de comissão cedida por atendimento já na v0, nova confirmação ligada à opção a cada degrau. O modelo nunca vê tabela nem comissão (§4).
7. **Três buracos que travam a F2:** a confirmação da IA exige `oferta_versao` (precisa emenda); a fórmula de comissão em R$ só existe no web (precisa ir ao servidor com teste de paridade); o gatilho é um rótulo do modelo (precisa de defesa por código) (§4.5, §3.5, §4.2).
8. **Aprendizado de máquina só depois:** hoje não há dado de exposição nem variação. O Credit Intelligence prevê aprovação do banco, não aceite do cliente, e está parado. Registrar a exposição desde já (§5).
9. **Fases:** F0 salvar N tabelas (~11 d-agente, **≥ 2 semanas de relógio**) · F1 web + fórmula no servidor (~5–6 d) · F2 IA por regra (~7–9 d) · F3 aprendizado (meses de dado) (§6). **Nada disso entra na IA do piloto;** F0 vai à produção só depois do relatório do piloto (01/12 21:00, `ROT:25`) (§6.5).
10. Rotação entre bancos com banco oculto: **não recomendada**. O banco aparece no texto de oferta, no link e na assinatura; só a FACTA digita no MVP (§4.8).

---

## 1. A negociação entre tabelas está no planejamento? **Não.** Há negociação só dentro da mesma oferta

| O que existe | Prova |
|---|---|
| E4 «Ajustar»: o código chama T5 com o número do cliente e escolhe a opção (R3/R4). Volta à E3 ou segue | `H` linha 86; `H` §5 R3–R4 (linha 198) |
| Política de oferta: mostra «a oferta ativa de melhor `coef_valor` da FACTA … nada de taxa, CET, coeficiente, comissão ou tabela»; «Máx. 3 contrapropostas»; «Nunca oferece C6/3RN por iniciativa própria no MVP» | `H` §4 (linhas 187-190) |
| Motor v0: `fracao_experimentacao = 0`; R1 banco FACTA, maior `coef_valor`; R8 «Fallback de banco inexistente no MVP» | `H` §5 R1, R8 (linha 203) |
| «Sem fallback de banco no MVP: a regra do dono só vale entre bancos com T8 e hoje só a FACTA tem» | `F:14` |
| Código da IA: T3 devolve **uma** oferta; T5 devolve até 5 opções **sem tabela**; «Comissão, `coef_valor`, `tabela_identificador` … não existem em nenhum esquema» | `src/ia-atendimento/src/ia_atendimento/ferramentas/esquemas.py:5-6`, `:124-152` |
| Motor v0 (B5.6) «não iniciada» | `ROT:378`, `ROT:1000-1005` |
| Busca negativa por «outra tabela», «outras tabelas», «negocia», «degrau», «escada» no ROT, na RG0911 e nos estudos | `lev-ia.md:57` (saída de `scripts/lev-ia-06.sh`) |

**Parcial, no máximo, por três peças que já ajudam:** a confirmação prevê a tabela no hash (`F:118`; `src/ia-atendimento/migrations/0001_esquema.up.sql:174`), mas a coluna-chave é `oferta_versao integer NOT NULL` (`:177`, ver §4.5); as faixas de esforço já têm `contrapropostas_max` (`0001_esquema.up.sql:67-70`); e o passo `decisao` grava o motor (`src/ia-atendimento/src/ia_atendimento/passos.py:131-133`). Nenhuma regra fala em trocar de tabela.

---

## 2. Diagnóstico

### 2.1 Por banco: quantas o banco devolve, quantas o 360 guarda, onde as outras se perdem

| | FACTA (facta-on) | C6 (c6-api) | 3RN (3rn-api, AJIN) |
|---|---|---|---|
| **O banco devolve** | **N tabelas** por prazo em `operacoes-disponiveis` (famílias SMART, GOLD PRIME, POWER, PLUS, PREMIUM e versões «sem seguro»). Todos os prazos só no modo grade. Chamada **não cobrada** (`src/facta-on/app/facta_client.py:490-539`; «NÃO cobra» em `:490-497`; `lev-facta.md:11,23`) | **N condições**, uma por convênio (= tabela), numa simulação `POR_VALOR_MAXIMO`. **Cobrada.** A grade por prazo custa até 12 simulações a mais (`src/c6-api/app/oferta/sim_client.py:211-242`; `src/c6-api/app/routers/oferta.py:1238-1277`) | **1 por vínculo.** A AJIN escolhe a tabela pelo tempo de casa (`src/3rn-api/app/routers/consulta.py:1610-1615`). Outra tabela só por `/3rn/calcular` com `regra_id`, **não cobrado** (`:1715-1722`, `:1837`). As outras regras vêm de `/3rn/regras` (`:1642-1659`): **catálogo da conta, não do lead** |
| **Economia gravada (oferta)** | 1 (`src/facta-on/app/cliente360_novo.py:726-749`) | 1 (`src/c6-api/app/cliente360_novo.py:548-560`) | 1 (`src/3rn-api/app/cliente360_novo.py:597-626`) |
| **`core.observacao.ofertas` (rev. 101)** | Até 20, desde 09/11 ~12:31. Campos: prazo, liberado, parcela, `tabela` = **código operacional** 11xxxx, `coeficiente` **financeiro**, matrícula→`vinculo_ref`, margem (`src/facta-on/app/cliente360_ctx.py:336-355`; `:343-349`) | Até 20, desde 09/11 ~11:55. Campos: prazo, liberado, parcela, convênio = tabela e **`coeficiente` = comissão** (`coeficiente_tabela`) (`src/c6-api/app/cliente360_contexto.py:23-28` docstring, `:237-253`, `:272-300`). **Sem matrícula e sem margem:** a API as descarta para o C6 (`src/cliente360-api/src/c360api/comercial/contexto.py:554`, `:561`, `self.banco != "C6"`), logo nunca há `vinculo_ref` por opção do C6 | **1 por vínculo elegível**, desde 09/11 09:19 (`src/3rn-api/app/cliente360_consulta_ctx.py:20` docstring; `_ofertas` em `:230-242`). Para a maioria dos CPFs, **1** (HIPÓTESE, sem medição) |
| **Onde as outras se perdem** | (a) modo de 1 prazo corta os outros prazos (`src/facta-on/app/routers/online.py:2316-2328`); HIPÓTESE: o n8n chama assim. (b) O item não leva nome, código canônico, taxa, seguro, bruto nem comissão (`cliente360_ctx.py:343-354`). (c) Corte em 20, a escolhida nunca sai (`:391-394`) | (a) A grade por prazo e os recálculos não vão ao 360 (`cliente360_contexto.py` lê só `outcome["simulacao"]`, `:272-300`; `oferta.py:1405-1414`, `:1491-1499`). (b) Taxa, CET e IOF não vão por opção. (c) `c6.cache` é sobrescrito por CPF (`src/c6-api/init_c6.sql:308-311`) | (a) O item do contexto leva só o identificador da tabela (`cliente360_consulta_ctx.py:222-227`, `:248-250`), **mas o dict inteiro da regra já está à mão:** `opcao["regra"]` = `rule` da AJIN (`src/3rn-api/app/cliente360_novo.py:2015-2017`), com `id` e `code`. (b) O recálculo em outra tabela não grava nada (`consulta.py:1666-1667`). (c) **Dois defeitos com `regra_id`:** o prazo é validado contra a tabela **original** (`consulta.py:1799`, `validar_prazo_tabela(body.prazo, sim.get("ruleName"), …)`) e a resposta devolve o nome e o `coeficiente_tabela` da tabela **original** (`:1844`, `:1851-1852`) |
| **Cortes comuns** | Lista só em positiva (`rev101_observacao_contexto.up.sql:113`). Sem correspondência com a economia, **a lista inteira cai** (`src/cliente360-api/src/c360api/comercial/contexto.py:589-598`). Corte em 20 na API (`:148`). Chave desconhecida no item é descartada e contada, sem derrubar o item (`:536-537`). Cache e recálculo não viram observação (decisão do dono, `MEM:decisoes-dono-08-10-oferta.md:15`) |||

**Medição que falta (o dono roda na S4, só leitura, sem PII na saída):** itens por positiva por banco, positivas por dia hoje, e que fração dos textos `tabela` resolve no catálogo. Consulta pronta em `lev-c360.md:130-139`.

### 2.2 Quais tabelas «não estão cadastradas», e por quê

Há duas leituras. As duas são reais.

| Leitura | O que é | Causa (prova) |
|---|---|---|
| **(a) Opção não persistida** | O banco devolveu e o 360 não guardava. Até 09/11, só a escolhida entrava. Hoje entra no jsonb, mas ninguém lê por lead | Uma economia por versão e uma oferta ativa por par, por desenho (`src/iskra/tools/ci/g1/gl360-schema.sql:1117-1119`, `:1297-1305`); `rev101…up.sql:154` («A escolhida continua sendo a de `payload_economico`»); `pessoa.listar_consultas` lê só a economia (`src/iskra/src/glw/ops/gl360/pessoa_listar_consultas.py:36-37`) |
| **(b) Tabela fora do catálogo de comissão** | Código que o banco oferta e que não tem `coef_valor` | Pendências (OP-CF-16) lê contratos, `payload_extra.tabela_banco` e `oferta_versao.payload_economico.tabela_identificador`, isto é, **só a escolhida** (`src/iskra/src/glw/ops/gl360/coeficiente_listar_tabelas_pendentes.py:7-12`, `:50-62`). **Nenhuma leitura de `observacao.ofertas` fora do painel** (busca: só `_painel_sql.py:330,406`) |

**Quando o ciclo se fecha, e quando não (FACTA e C6, web).** A chave de escolha trata comissão ausente como 0 (`src/facta-on/app/routers/online.py:2070-2090`; web `src/cliente360-web/src/features/digitacao/opcoes-real.ts:56-78`: «Sem coeficiente perde»).
- **Convive com uma tabela catalogada:** a sem catálogo perde a escolha → não vai à economia → Pendências não a vê → segue sem comissão. **Fecha-se.** É exatamente o caso da negociação: a alternativa útil é a que não ganhou.
- **Nenhuma candidata tem comissão:** a escolha cai no maior valor (facta-on, `online.py:2079-2083`) ou na primeira não proibida (web, `opcoes-real.ts:66-68`). A tabela sem catálogo **é** escolhida e entra em Pendências por `incluir_ofertas`. **Não se fecha.**

**3RN e C6, causa extra:** a tabela nova vira esqueleto no catálogo **antigo** `mbclt.tabelas`, sem coeficiente (`src/3rn-api/app/tabelas_prioridade.py:264-332`; `src/c6-api/app/oferta/tabelas.py:423-426`). O catálogo do 360 não sincroniza (`MEM:coeficientes-migracao-c360.md`). Com a fonte `cliente360`, responde `sem_catalogo` → `None` (`src/3rn-api/app/coeficientes_c360.py:47-49`).

**FACTA, causa extra:** o item grava o código **operacional** (11xxxx), e o catálogo usa o **canônico** (6xxxx/7xxxx) mais apelido (`online.py:1922-1929`). Resolve só se o apelido operacional→canônico estiver populado. Estava vazio em 22/09 (`MEM:coeficientes-migracao-c360.md`); HIPÓTESE de que hoje está.

**Casos registrados:** FACTA 116085 60x, 69981 60x e 116480 60x seguiam pendentes em 04/11 (`MEM:coef-vigencia-2910-03-11.md`); 3RN FGL87 24x só apareceu por `incluir_ofertas` (`coeficiente_listar_tabelas_pendentes.py:59-60`).

### 2.3 O que já está pronto para aproveitar

| Peça | Prova |
|---|---|
| Lista de opções gravada nos 3 bancos desde 09/11 | `MEM:pre-aprovacoes-so-s4-04-11.md:49` |
| Congelamento do snapshot de comissão no write path: OP-CF-03 (`_snapshot.congelar`), embutida na OP-OF-13, resolve o catálogo pelo arg `coeficiente {identificadores, prazo_meses}` | `src/iskra/src/glw/ops/gl360/_snapshot.py:111`; o arg é montado em `src/cliente360-api/src/c360api/comercial/escrita.py:212-245` (`_incluir_coeficiente`, docstring `:216-220`). **Não** confundir com `coeficiente.resolver_lote`, op de **leitura** no pool `ro` (`src/iskra/src/glw/ops/gl360/catalogo.py:646`) |
| `vinculo_ref` HMAC: a matrícula nunca é gravada (FACTA e 3RN; C6 não tem, §2.1) | `rev101…up.sql:137-140`; `_observacao_contexto.py:11-13` |
| O vendedor humano **já negocia entre tabelas** no web (select de tabela, troca de prazo, recálculo) | `src/cliente360-web/src/features/digitacao/cartao-aprovado.tsx:184-213`; `opcoes-real.ts:6-9` |
| A lista do vendedor some em 30 min (`sessionStorage`) | `src/cliente360-web/src/features/digitacao/sessao-digitacao.ts:46` |
| Função pura do produtor reaproveitável no backfill | `src/facta-on/app/cliente360_ctx.py:401-407` |
| As rotas de digitação da FACTA já recebem a tabela no corpo: `SimularOperacaoReq.codigo_tabela` (`/proposta/simulacao`) e `FormalizarReq.codigo_tabela` (`/proposta/formalizar`) | `src/facta-on/app/routers/online.py:3794`, `:3801`, `:3813`; `:4963`, `:4975`, `:5362` |

---

## 3. Desenho de dados «N tabelas por lead»

### 3.1 Onde mora

| Id | Decisão de desenho | Por quê |
|---|---|---|
| **NT-01** | Mora no **gl360 da S4**, esquema `core`. Escritor único: **ISKRA** | «É o único escritor de `core.*` e `ref.*` em runtime» (`lev-c360.md:22`, com o INSERT da observação em `oferta_aplicar_observacao.py:848` e a busca de zero `INSERT/UPDATE` em `core.`/`ref.` na API, `lev-c360.md:24`). A API só escreve em `acesso.*`. O gl360 de produção é a S4, não o MCP (`MEM:gl360-producao-e-a-s4.md:11-16`) |
| **NT-02** | **Tabela-filha nova `core.oferta_opcao`** (nome provisório), uma linha por opção, filha de `core.observacao`. O jsonb `ofertas` continua como evidência imutável | Opção A (só ler o jsonb) não congela comissão, não aceita desfecho e é cara para treino em lote (`lev-c360.md:148`). Opção C (opção como oferta ou versão) quebra INV-10, o fingerprint e o fill-once (`gl360-schema.sql:1117-1119`, `:1338`, `:1383-1385`) |
| **NT-03** | **Não** tocar em `core.oferta`, `oferta_versao`, `payload_economico` nem pré-aprovado | Pré-aprovado = última consulta, regra P1–P14 (`MEM:decisoes-dono-08-10-oferta.md:14-15,47`). Uma opção alternativa nunca vira pré-aprovado nem conversão. **Consequência:** a confirmação da IA, que hoje se ancora em `oferta_versao`, precisa de emenda (§4.5, NT-29b) |

### 3.2 Esquema proposto (`core.oferta_opcao`)

| Coluna | Tipo | Regra | Fonte |
|---|---|---|---|
| `opcao_id` | bigint identity PK | | |
| `observation_id` | **uuid** FK → `core.observacao(observation_id)` | NOT NULL; ON DELETE RESTRICT; criar `NOT VALID` e validar depois | PK real: `gl360-schema.sql:1248` |
| `pessoa_id` | **uuid** | copiado da observação (índice por lead sem junção) | `gl360-schema.sql:1250` |
| `banco_id`, `produto_id` | smallint | copiados | `gl360-schema.sql:1251-1252` |
| `observed_at`, `competencia` | timestamptz, date | copiados | |
| `ordem` | smallint 1..20 | posição na lista do produtor | |
| `escolhida` | bool | exatamente 1 true por observação (mesma regra do jsonb) | `_observacao_contexto.py:184` |
| `origem` | text CHECK `IN ('consulta')` | só consulta na F0. Recálculo fica de fora; se um dia entrar, com valor próprio e nunca no pré-aprovado | `MEM:decisoes-dono-08-10-oferta.md:15` |
| `vinculo_ref` | text `^[0-9a-f]{32}$` NULL | HMAC; matrícula nunca. **Sempre NULL no C6** (a API descarta a matrícula do C6) | `rev101…up.sql:92,137-138`; `contexto.py:554` |
| `prazo_meses` | smallint 1..240 | | |
| `valor_liberado`, `valor_parcela` | numeric(12,2) > 0 | | |
| `valor_bruto` | numeric(12,2) NULL | FACTA `contrato`, C6 bruto | `lev-facta.md:42`; `src/c6-api/app/oferta/oferta_extra.py:4-7` |
| `taxa_mes` | numeric(7,4) NULL | FACTA `taxa`, C6 taxa, 3RN `rate` | `lev-facta.md:40`; `parsers_3rn.py:332-343` |
| `cet_mes` | numeric(7,4) NULL | só quando o banco manda (C6, 3RN) | |
| `valor_seguro`, `com_seguro` | numeric NULL, bool NULL | FACTA GOLD | `src/facta-on/app/cliente360_novo.py:1033-1035`; `src/facta-on/app/seguro_teto.py:5-12` |
| `tabela_texto` | text ≤ 64 | o identificador cru do banco (FACTA operacional, C6 convênio, 3RN o da economia) | mesmo padrão de `OfertaObservacao.tabela` |
| `tabela_codigo_canonico` | text NULL | FACTA: prefixo do nome; 3RN: `rule.code` | `online.py:1922-1929`; `cliente360_novo.py:2015-2017` |
| `tabela_nome` | text ≤ 200 NULL | nome de produto, sem dado de cliente | |
| `regra_ref` | text NULL | 3RN `rule.id` (id da regra, não é PII): permite recalcular nessa tabela | `consulta.py:1764` (`ruleId`) |
| `coef_financeiro` | numeric NULL | o fator da parcela | |
| `tabela_id` | FK `ref.catalogo_tabela` NULL | NULL = sem catálogo | |
| `coef_versao_id`, `coef_valor`, `pct_empresa`, `coef_origem` | mesmas regras do snapshot de `oferta_versao` | **congelados no INSERT** (fill-once) pela mesma função da OP-CF-03 (NT-06), mesma FK tripla de `ofv_coef_par_identico` | `gl360-schema.sql:1321-1388` |
| `contexto_v`, `produtor_sha` | | rastreio de carga ruim | `rev101…up.sql:155-156` |

**Comissão estimada em R$: não gravar.** Calcular na leitura pela fórmula única do servidor (NT-15, §3.5). Duplicar a fórmula é risco (`MEM:decisoes-dono-21-10-pct-encerradas.md:13`; `lev-ml.md:99`).

**Semântica de `ofertas.coeficiente` no jsonb muda por banco:** FACTA = financeiro (`cliente360_ctx.py:347`); C6 = comissão (`cliente360_contexto.py:23-28`). Nunca copiar esse campo como `coef_valor` (NT-08).

**Validade.** A opção guardada é **referência, não oferta firme.** Não tem `valid_until` próprio: vale a da oferta da observação (`gl360-schema.sql:1049-1053`), e a leitura marca `vencida` quando a observação é de outro dia ou de outra competência. Antes de mostrar ao cliente, sempre se recalcula (FACTA e 3RN sem custo; C6 é paga, §8).

**Chaves e índices.**
- UNIQUE (`observation_id`, `ordem`).
- Índice (`pessoa_id`, `banco_id`, `observed_at` DESC): leitura por lead.
- Índice parcial (`banco_id`, `tabela_texto`, `prazo_meses`) WHERE `tabela_id IS NULL`: alimenta Pendências.
- Índice (`tabela_id`, `prazo_meses`, `observed_at`): estudos e treino.

**Volume: CONTRADIÇÃO, medir antes da DDL.** Duas fontes do próprio levantamento não batem (`lev-c360.md:122-126`):
- «≈ 400 positivas/dia» vem de set–out (`MEM:credit-intelligence-engine`), antes da volta do CLT em 23/10. Daria 1,2 a 4 mil linhas/dia.
- «~600 obs/10 min» em 05/11 12:14 (`MEM:pre-aprovacoes-so-s4-04-11.md:26`), com reprovações: se fosse o ritmo do dia todo, ~86 mil observações/dia. Só uma fração é positiva, e o horário de pico não é a média; ainda assim a estimativa de linhas pode estar **até 10 vezes baixa**.
O disco, os índices e o p95 da OP-OF-13 se recalculam com o número medido (positivas/dia × itens por positiva, consulta de `lev-c360.md:130-139`). Antes disso, nenhum número de GB vale.

**Retenção.** Padrão recomendado: igual a `core.observacao` (sem expurgo), porque é o rótulo do aprendizado. Alternativa: 13 meses. Pergunta Q-07.

**PII.** Nenhum CPF, nome, telefone ou matrícula. Só `pessoa_id`, `vinculo_ref` HMAC e nomes de produto. Os grants seguem os da observação (pool `rt` escreve, `ro` lê). O DBeaver recebe só leitura (mesma regra dada a `core.observacao` em 04/11, `MEM:pre-aprovacoes-so-s4-04-11.md:22`).

### 3.3 Caminho de escrita

| Id | Passo | Quem | Quando |
|---|---|---|---|
| **NT-04** | **Contexto v2 nos produtores:** o item ganha `tabela_nome`, `tabela_codigo_canonico`, `taxa_mes`, `cet_mes`, `valor_bruto`, `valor_seguro`, `coeficiente_tabela` (comissão), `regra_ref` (3RN) | facta-on (`cliente360_ctx.py:336-355`); c6-api (`cliente360_contexto.py:272-300`); 3rn-api em `cliente360_consulta_ctx._ofertas` (`:230-242`), lendo `opcao["regra"]["id"]` e `["code"]`, que já estão no dict (`cliente360_novo.py:2017`); **sem mexer em `parsers_3rn.py`** | na consulta positiva, como hoje (nunca no cache, nunca no recálculo) |
| **NT-05** | **API AI-01** aceita os campos novos na lista de permissão e higieniza | cliente360-api, `src/c360api/comercial/contexto.py:88-102,523-631` | |
| **NT-06** | **ISKRA:** `OfertaObservacao` (hoje `extra="forbid"`, `_observacao_contexto.py:117-133`) aceita os campos; **OP-OF-13** grava a observação, o jsonb **e** as linhas de `core.oferta_opcao` na **mesma transação** do pool `rt`. A comissão de cada linha se resolve pela **mesma função interna da OP-CF-03** (`_snapshot.congelar`, `_snapshot.py:111`, com `_coeficiente.py`), nunca chamando a op de leitura `coeficiente.resolver_lote` (pool `ro`, `catalogo.py:646`) | iskra, `src/iskra/src/glw/ops/gl360/oferta_aplicar_observacao.py:848` | |
| **NT-06b** | **Idempotência:** grava filhas **só no INSERT novo com desfecho `aplicada`**. Nada em replay (`observation_id` repetido), `registrada_sem_mutacao`, `stale_competencia` ou `quarentena`. Motivo: `core.observacao` é imutável (`fn_imutavel`, `gl360-schema.sql:1291`) e as colunas da rev. 101 ficam **fora do envelope do replay** («corrigir contexto não se faz por reenvio», `_observacao_contexto.py:18-19`); os desfechos estão em `oferta_aplicar_observacao.py:100-105`, `:547-548`. A filha herda a imutabilidade (trigger `fn_imutavel` também) | iskra | |
| **NT-07** | **Ordem de subida:** ISKRA (aceita v2, flag off) → API (lista de permissão, flag off) → produtor (manda v2). Desligar na ordem inversa | | **O perigo é a API repassar campo novo antes de o ISKRA aceitar:** o `extra="forbid"` devolve 422 e a observação vai para a **fila morta** do produtor (`_observacao_contexto.py:4-8`). O produtor subir antes da API é inofensivo: a API descarta a chave desconhecida contando, sem derrubar o item (`contexto.py:536-537`) |
| **NT-08** | **Backfill** de `core.oferta_opcao` a partir de `observacao.ofertas` desde 09/11, **só de observações `aplicada`**. Comissão resolvida pela versão vigente em `observed_at` (ISKRA, op nomeada, kit). `coeficiente` do jsonb tratado **por banco**: FACTA → `coef_financeiro`; C6 → só referência de conferência contra o catálogo; nunca copiado como `coef_valor`. Linhas antigas ficam sem nome, taxa e seguro | ISKRA + kit S4 + «sim» | uma vez |
| **NT-09** | **Pendências lê as opções:** OP-CF-16 ganha `incluir_opcoes=true` (padrão `false`), com fonte `core.oferta_opcao WHERE tabela_id IS NULL` (antes da tabela nova: o jsonb dos últimos 30 dias). Fecha a leitura (b) do §2.2 | iskra (`coeficiente_listar_tabelas_pendentes.py`), API passa o arg | Já há precedente: o dono mandou «TUDO que vier sem tabela, inclusive de OFERTA» (16/10, `:50-51`) |

### 3.4 Leitura pela API e pelo web

| Id | Peça | Regra |
|---|---|---|
| **NT-10** | ISKRA op de leitura `pessoa.listar_opcoes(pessoa_id, banco?, desde?, so_ultima=true)`, pool `ro` | devolve as opções da última consulta positiva por banco (ou todas desde `desde`), com `vencida` calculado e a comissão estimada em R$ pela fórmula do NT-15 |
| **NT-11** | API `GET /v1/pessoas/{id}/opcoes`, **escopo novo `opcao:ler`**, flag `C360_OPCOES_LEITURA` (off) | recurso novo, não chave nova em `Oferta` (`lev-web.md:93`). `pct_empresa` e comissão só para quem já lê comissão (HIPÓTESE: o nome do escopo de comissão na API não foi conferido). Para a IA, `coef_valor` e `tabela_*` só no lado do código (contrato 03, `lev-ia.md:89`) |
| **NT-12** | Web: schema zod do recurso novo **antes** de a API ligar a flag; tela «Opções por lead» na ficha, atrás de flag `PAINEL_OPCOES_POR_LEAD`, primeiro só Admin e TI | o web usa `z.strictObject` (149 ocorrências; `src/cliente360-web/src/contrato/zod.ts`); precedente de quebra em 19/10 (`MEM:campo-novo-api-quebra-web.md`) |
| **NT-13** | Web: a Digitação registra a opção que o vendedor usou e a que estava selecionada ao abrir. Grava pela API no gl360 (rota nova, ISKRA escreve, esquema `core`, sem texto livre) | sinal de treino com volume real (§5.3). **Condição:** é dado pessoal da operação; o rastro análogo do web só liga depois de **revisão jurídica** e de política de expiração (`src/cliente360-web/src/server/rastro/registrar.ts:19-22`). NT-13 fica sob a mesma condição (Q-20) |

### 3.5 Fórmula de comissão em R$ no servidor (pré-requisito da F2)

| Id | Peça | Por quê |
|---|---|---|
| **NT-15** | Uma função única de «comissão estimada em R$» (base liberado ou financiado conforme `meta_base` × coeficiente, `pct_empresa`, regra do 712xx) no **ISKRA** (op de leitura) ou na **API**, com **teste de paridade** contra a tela de Comissões do web, sobre o mesmo conjunto de contratos | Hoje a conta em R$ é do web (`MEM:relatorio-comissoes-plano.md`: «META = base × coeficiente»); a API e o ISKRA expõem só os snapshots (`coef_valor`, `pct_empresa`; `cliente360-api/src/c360api/coeficiente/projecao.py:548`), e a IA recebe `comissao_esperada_brl` pronta do chamador (`src/ia-atendimento/src/ia_atendimento/api/atendimentos.py:43`, `:113-118`). NT-23, NT-24, a faixa por degrau e o orçamento de comissão cedida dependem dela. HIPÓTESE: a busca por uma função de comissão em R$ no ISKRA/API não achou nenhuma (`scripts/revisao-final-2.sh`) |

---

## 4. Roteiro de negociação (regra fixa, v0)

### 4.1 A escada

| Id | Regra |
|---|---|
| **NT-20** | **Degrau 0** = a oferta de sempre: maior prazo → maior `coef_valor` → maior valor (P13, `MEM:decisoes-dono-08-10-oferta.md:47`; R1 `H` §5) |
| **NT-21** | **Candidatas** = opções da **última consulta positiva** do mesmo banco, não vencidas, com `tabela_id` resolvido, e do **mesmo vínculo**: FACTA e 3RN por `vinculo_ref`; **C6 pela mesma observação** (mesma consulta, mesmo `job_ref`), porque o C6 não tem `vinculo_ref` (§2.1). Sem catálogo = fora: sem comissão, não se negocia (cai em Pendências, NT-09). **3RN fora da escada na v0:** a consulta traz 1 opção por vínculo, e as alternativas viriam de `/3rn/regras` (catálogo da conta) filtrado por elegibilidade, regra que não existe e cujo recálculo tem 2 defeitos (§2.1). Entra só depois do conserto da F0.2 e de uma regra de elegibilidade desenhada (Q-18) |
| **NT-22** | **Ganho mínimo ao cliente:** a candidata precisa melhorar a dimensão da objeção em ≥ Y % contra o degrau atual (valor liberado para `valor_baixo`; parcela para `parcela_alta`/`taxa_juros`). Y é do dono (Q-03) |
| **NT-23** | **Ordem:** entre as candidatas com ganho e acima do piso, a de **menor custo por real dado ao cliente** = Δcomissão em R$ ÷ Δ(dimensão da objeção) contra o degrau 0. Empate: maior ganho ao cliente. Assim a regra faz o que promete: perder o mínimo de comissão por real dado |
| **NT-24** | **Piso** (decisão do dono, Q-02), **na grandeza certa, comissão em R$** (como `lev-ml.md` §6): a candidata só entra se comissão estimada (NT-15) ≥ max(**P % da comissão do degrau 0**, **R$ X**). Trava secundária: `coef_valor` ≥ coef mínimo absoluto (o CLT vai de 0 a 10, `MEM:coef-clt-faixa-0-10-09-11.md:8`). Valor para discutir: P = 85 % (`lev-ml.md` §6); X e o coef mínimo, sem padrão. Sem NT-15 no ar, R9 não liga |
| **NT-25** | **Sempre recalcular antes de mostrar.** O degrau escolhido passa pelo T5 nessa tabela; a opção guardada só diz o que existe e quanto paga. FACTA: `operacoes-disponiveis` e `etapa1` não cobram (`lev-facta.md:23,26`). 3RN: só depois do conserto de `consulta.py:1799,1844,1851` |

**Atenção, não provado:** «coeficiente menor dá mais dinheiro ao cliente» é **HIPÓTESE**. O facta-on mediu correlação ≈ 0 entre o coeficiente financeiro e a comissão (`src/facta-on/app/routers/online.py:2074-2077`). Por isso NT-22 filtra o ganho do cliente de forma explícita, em vez de supor que ele vem junto.

**Alavanca natural da FACTA:** o par GOLD (com seguro) × a mesma família sem seguro. A mesma parcela dá 7,5 % a 13 % mais ao cliente, com a mesma taxa (`seguro_teto.py:5-12`). Mas o dono decidiu em 24/10 manter a GOLD porque «o seguro é o produto e a comissão» (`src/facta-on/app/seguro_teto.py:18-21`). Usar a «sem seguro» como degrau pede o «sim» dele (Q-05).

### 4.2 Quando oferecer a próxima (o gatilho não pode ser só do modelo)

O rótulo de objeção é **classificado pelo modelo** nas fases E2/E3 (`src/ia-atendimento/src/ia_atendimento/modulos_fase.py:44-53`, `:58-60`). Se o gatilho fosse só esse rótulo, o modelo decidiria, na prática, descer de degrau. Por isso:

| Id | Gatilho e defesa |
|---|---|
| **NT-26** | Descer exige **os dois**: (1) objeção codificada `valor_baixo`, `taxa_juros` ou `parcela_alta`; **e** (2) um **fato de código**: o T5 na tabela atual, com o número que o cliente deu (extraído pelo código, `alvo_pedido`), voltou `sem_opcao`/`acima_do_maximo`, ou a opção do T5 foi mostrada e recusada. Sem número do cliente, primeiro roda o R3 normal na tabela atual. Atenção: o vocabulário de `objecao` em `H:64` **não tem** `taxa_juros`, mas o R3 (`H:198`) o usa; alinhar antes da F2 |
| **NT-26b** | **Teto de comissão cedida por atendimento já na v0**, independente do rótulo: Σ (comissão do degrau 0 − comissão do degrau mostrado) ≤ R$ Z por atendimento, além do piso. E um **orçamento mensal** de comissão cedida com corte automático (`lev-ml.md` §6, «Orçamento de perda»), também na v0 |
| **NT-26c** | **Personas de manipulação na F3:** cliente que alega juros alto sem número, que recusa em série para baixar, que repete a objeção depois de aceitar. Critério: nenhuma desce além do teto, nenhuma desce sem o fato de código |
| **NT-27** | Nunca na primeira apresentação. Nunca por «quero pensar» (vai a R5). Nunca depois de recusa firme repetida (E10) |
| **NT-28** | Um degrau por turno. Um degrau conta como contraproposta (mantém o teto global de 3, `H` §1 P7) |

### 4.3 Limite de degraus por faixa de esforço

| Faixa (comissão esperada, `0001_esquema.up.sql:67-70`) | `contrapropostas_max` hoje | **`degraus_tabela_max` (proposta, Q-04)** |
|---|---|---|
| baixa (< R$ 150) | 1 | **0**: comissão pequena não paga a perda |
| media (150–400) | 2 | **1** |
| alta (400–800) | 3 | **2** |
| muito_alta (> 800) | 3 | **2** |

- A faixa é a do degrau 0 e **fica fixa** no atendimento (`src/ia-atendimento/src/ia_atendimento/estado.py:9`; CHECK `0001:145-146`). Descer de degrau não reduz o esforço no meio.
- Hoje a faixa vem do chamador (`atendimentos.py:113-118`); com NT-15, passa a poder ser conferida no servidor.
- No piloto vale a faixa única `media`, e o efetivo de contrapropostas é ambíguo (1 ou 2, `ROT:1002-1003` × `0001:72`; `lev-ia.md:122`). Resolver isso antes de somar degraus.

### 4.4 Textos fixos novos (aprovação D36)

| Id | Uso | Rascunho |
|---|---|---|
| **TX-05b** | contraproposta em degrau novo | «Consegui uma condição diferente para você: *{{valor_liberado}}* liberados, parcela de *{{valor_parcela}}* em *{{prazo}}x*. Prefere esta?» |
| **TX-06b** | chegou ao piso ou ao limite de degraus | «Esta é a melhor condição que consigo hoje: *{{valor_liberado}}* liberados, parcela de *{{valor_parcela}}* em *{{prazo}}x*. Quer seguir com ela?» |

Seguem as regras de `H` §6: ≤ 400 caracteres, uma pergunta, negrito só nos valores, sem promessa, sem citar tabela, taxa ou juros. Pergunta de taxa ou CET continua no TX-32.

### 4.5 Confirmação ligada ao dado

| Id | Regra |
|---|---|
| **NT-29** | Trocar de degrau troca a tabela ⇒ hash novo ⇒ confirmação anterior invalidada. Exige que o B5.4 ponha `tabela_identificador` no hash canônico, como o papel já manda (`F:118`; hoje sem código: `lev-ia.md:73`) |
| **NT-29b** | **Conflito a resolver antes da F2.** `ia.confirmacao` tem `oferta_versao integer NOT NULL` com CHECK `oferta_versao >= 1`, e o hash cobre `{banco, valor, parcela, prazo, tabela, oferta_versao}` (`0001_esquema.up.sql:174-177`, `:191`). Um degrau de outra tabela **não é** uma `oferta_versao` (NT-03). Proposta: `oferta_versao` continua (a do degrau 0, âncora da oferta) **e** entra `opcao_id bigint NULL` (NULL = degrau 0) na coluna e no hash. Pede: migração da IA com «sim» nomeado (coluna + CHECK), e **emenda do contrato 05** (T7 digita a tabela da opção confirmada) e do F §4 (hash). Q-16 |
| **NT-30** | T7 ganha a pré-condição `degrau_dentro_do_piso` e digita **a tabela do degrau confirmado**, não a da oferta ativa. **Fato parcial:** as rotas `/proposta/simulacao` e `/proposta/formalizar` do facta-on recebem `codigo_tabela` no corpo (`online.py:3801`, `:4975`), e a tela do vendedor já digita outra tabela da lista (`cartao-aprovado.tsx:184-199`). **Falta provar** que o T7 da IA leva a tabela do degrau até lá (HIPÓTESE; o T7 ainda não tem código) |

### 4.6 O que o modelo vê e não vê

| O quê | Vai ao modelo? |
|---|---|
| `oferta_ref`/`opcao_ref` do degrau corrente, placeholders | sim, opaco |
| que existe outra tabela, quantas, em que ordem | **não** |
| `coef_valor`, comissão, `tabela_*`, piso, faixa | **não** (`F:116,121`; `esquemas.py:5-6`; `src/ia-atendimento/src/ia_atendimento/contexto.py:104-120`) |
| a decisão de descer de degrau | **não**: é do código (regra **R9** nova). O modelo só dá o rótulo da objeção, e o rótulo sozinho não basta (NT-26) |

### 4.7 Mudanças na IA (para a F2)

| Peça | Mudança | Prova do «hoje» |
|---|---|---|
| Motor | **R9**: próximo degrau por NT-21…NT-28; `fracao_experimentacao` segue 0 | `H` §5 |
| T3 | lado do código recebe `degraus[]` de NT-11; modelo vê só o degrau corrente. Minor ⇒ `numero` novo do catálogo | `esquemas.py:8-9,124-137` |
| T5 | lado do código guarda a tabela de cada opção | `esquemas.py:140-152` |
| Estado | + `degrau`, `degraus_vistos` (refs ≤ 5), `comissao_cedida`; valores nunca no estado; HIPÓTESE: cabe em 2 KB | `src/ia-atendimento/src/ia_atendimento/modelos_conversa.py:22-76` |
| Confirmação | NT-29b (`opcao_id` na coluna e no hash) | `0001:174-191` |
| Config | chave `negociacao_tabelas` {ativa=false, piso, ganho_min, degraus por faixa, teto cedido por atendimento, orçamento mensal}; o CHECK de `config_versao` pede migração com «sim» nomeado | `0001:43-47`; contrato 08 |
| Passo `decisao` | grava `regra=R9`, degrau, `opcao_id`, conjunto elegível, propensão (§5.2). `opcao_id` aponta para o gl360 **sem FK** (outro banco): referência lógica declarada | `passos.py:131-133` |
| Nota de repasse | + `pendencia_piso_tabela` | `H` §7 |
| Contratos | emendas 03 (leitura de opções), 05 (T7 com tabela do degrau, confirmação por `opcao_id`), 08 (config, R9, passo); cada uma com «sim» | `RG0911:170` |

### 4.8 Pedido complementar: rotação entre bancos com banco oculto

| Ponto | Situação | Prova |
|---|---|---|
| Esconder o banco | **Não dá na contratação.** O texto de oferta já mostra `{{banco}}` (TX-03); o link de formalização e a assinatura são do banco | `H` §6 TX-03; `F` T9 |
| Obrigação de informar banco e CET antes do aceite | **HIPÓTESE com forte indício:** a regra do CET (CMN) e o Código de Defesa do Consumidor pedem informação prévia de custo e de quem concede o crédito. Sem fonte jurídica lida aqui; pedir ao jurídico (já pendente para outros pontos, J8) | — |
| Rotação na IA | Só entre bancos com T8 (conferência), e hoje só a FACTA tem. MVP sem fallback (decisão (w)) | `F:14`; `MEM:decisoes-dono-29-10-ia-deepseek.md:25` |
| O que 3RN e C6 precisariam | T7 com idempotência, T8 (3RN sem rota de conferência; C6 sem busca por CPF), T9, e o G-0088 fechado (T5 de 3RN/C6 vai ao banco real em sombra) | `F:13`; `RG0911:76` |
| Custo | C6: cada simulação é paga; o preço no código é provisório, nunca confirmado (`src/c6-api/app/routers/oferta.py:156-161`). 3RN: só a consulta de vínculos é cobrada; o recálculo não (`consulta.py:1837`) | |
| **Caminho mais rápido e mais seguro** | **O vendedor humano primeiro.** A tela «Opções por lead» (NT-12) mostra lado a lado as opções dos bancos com consulta recente, ordenadas por NT-23. O vendedor já digita nos 3 bancos, explica o banco e o CET, e a escolha dele vira dado (NT-13, sob a condição jurídica) | `lev-web.md:44-54` |

A função de escolha entre bancos é a mesma da escada: valor esperado = comissão estimada × P(aceite | opção, contexto), com o piso. Na v0, P(aceite) é constante, e a regra vira NT-23 com o piso NT-24.

---

## 5. Política de escolha

### 5.1 O que o Credit Intelligence já cobre, sendo honesto

| Pergunta | Resposta | Prova |
|---|---|---|
| Prevê aceite do cliente por tabela? | **Não.** Prevê se o banco devolve ≥ 1 oferta válida, por banco | `src/gl-credit-intelligence-api/docs/adr/0004-facta-on-only-target.md:11-12`; `MEM:decisoes-dono-22-10-credit-intel.md:15` (D-05) |
| Está rodando? | **Não.** Ponte parada em 26/10; banco `glci` arquivado em 04/11; a coleta não volta | `MEM:pre-aprovacoes-so-s4-04-11.md:18-20` |
| Pode reordenar decisões? | **Não.** D-02: shadow, «nunca … reordenar … nem alterar decisões» | `MEM:decisoes-dono-22-10-credit-intel.md:14` |
| Desempenho | AUC 0,60–0,70, Brier skill 0,01–0,04: as features dizem pouco | `src/gl-credit-intelligence-api/docs/model-v1.md:294-297` |
| O que se reaproveita | O **método**: corte temporal com embargo, GroupKFold por pessoa, calibração, shadow antes de efeito, artefato auditado, promoção só pelo dono | `model-v1.md:57-81,97-106` |

### 5.2 v0 agora: regra determinística

- R9 (§4), `fracao_experimentacao = 0`, propensão gravada = 1,0.
- Liga primeiro em **sombra**: o motor calcula o degrau que ofereceria e grava, mas a conversa segue sem R9. Depois liga só na FACTA.
- **Métrica de canibalização com corte (R-02):** taxa de aceite na **1ª apresentação** (E3 → aceita ÷ E3 apresentadas), semanal, na FACTA. Linha de base: as 4 semanas antes de ligar R9. Corte automático de R9 se cair mais de **N p.p.** (Q-21; padrão para discutir, 5 p.p.) por 2 semanas seguidas. Volume baixo da IA torna essa métrica ruidosa (§5.4): ler junto com o vendedor.

### 5.3 Dados a registrar desde já (para treinar depois)

| Evento | Campos | Onde |
|---|---|---|
| **Exposição** (cada vez que uma opção é mostrada) | atendimento ou sessão do vendedor, canal (`ia` / `vendedor`), `opcao_id`, degrau, conjunto elegível (ids + `coef_valor` + Δ valor + Δ comissão), **propensão**, versão do motor, faixa, objeção que disparou, instante | IA: `ia_atendimento.passo` (`decisao`). Vendedor: NT-13 no gl360 (sob condição jurídica) |
| **Resposta** | aceitou, pediu outro valor, objeção (código), sumiu, repassou | IA: passo do turno (`objecao`, `intencao` já existem, `lev-ia.md:152`) |
| **Desfecho** | contrato digitado (`core.contrato.oferta_id`, `codigo_tabela`), depois pago/cancelado, datas | já existe (`gl360-schema.sql:1456-1484`); falta a chave exposição→contrato |
| **Exclusões** | troca forçada pela FACTA («sem seguro»), cache, recálculo, regime antes de 23/10 | `MEM:decisoes-dono-27-10-seguro-facta.md:15`; `model-v1.md:302` |

### 5.4 v1: aprendizado caso a caso, só depois

| Etapa | Quando | Como |
|---|---|---|
| Descritivo (E1–E5 de `lev-ml.md:161-170`) | logo depois da F0 | Δ valor × Δ comissão por banco; conversão por faixa de `coef_valor`; trocas naturais oferta→contrato. **Dado do vendedor serve aqui**, não para avaliar política (ver abaixo) |
| **v1: Thompson sampling Beta-Binomial, células reduzidas e hierárquico** | quando cada célula tiver dezenas de exposições pós-objeção **na própria política** | célula = (objeção × faixa de queda de comissão), ~6 células, com prior forte compartilhado (hierárquico). Banco e ganho ao cliente entram depois. Exploração ≤ 10–20 % **dentro** do piso, com propensão gravada |
| Comparação formal (teste de braços) | só com ~**520 exposições por braço** (`lev-ml.md` §4: 22 % → 30 %, α 5 %, poder 80 %); com 2 braços por célula e 6 células, **~6 mil** exposições pós-objeção | inviável só com a IA; possível só somando o vendedor com propensão registrada |
| v2: bandit contextual ou uplift | só se a avaliação off-policy da v1 mostrar ganho com intervalo fora do zero; uplift só com grupo de controle | `lev-ml.md:136-137` |
| Travas | orçamento mensal de «comissão cedida» com corte automático (**já na v0**, NT-26b); chave de desligar sem deploy; probabilidade só de modelo validado, nunca do LLM | `lev-ml.md` §6; `MEM:credit-intelligence-engine.md:17-18` |

**Recompensa com atraso.** «Comissão realizada (pago)» chega semanas depois (censura, `lev-ml.md` §3). Alvo intermediário: **contrato digitado × comissão estimada (NT-15)**, corrigido quando sai pago ou cancelado (`label_coverage`, como no motor do glci). Sem isso, o aprendizado demora o dobro.

**Linha de base.** O 22,4 % de venda depois de objeção vem de **conversas de vendedor** (`lev-ml.md` §4), não da IA. Não serve como base da IA; a base da IA se mede na sombra.

**Viés de seleção do vendedor.** O vendedor escolhe quando simular, digitar e o tom (`lev-ml.md` §3, «Efeito do vendedor»). Sem propensão do lado do vendedor, o dado dele serve para o **descritivo**, não para avaliar uma política fora dela (off-policy).

**Volume, sendo realista.** A IA do piloto tem teto de 10 a 20 disparos por dia (`0001:65`); com 10–15 % de objeção de preço (HIPÓTESE), isso é ~1–3 casos por dia: **mais de um ano por comparação só com a IA** (`lev-ml.md` §4). O volume está no vendedor humano e no in-app.

---

## 6. Fases e esforço

### 6.1 F0: capturar e salvar N tabelas por lead (independe da IA; serve o vendedor)

| Sub | O quê | Repositórios / PRs | Migração / kit | d-agente (estimativa) |
|---|---|---|---|---|
| F0.0 | **Medir** positivas/dia e itens por positiva por banco (§3.2, contradição de volume) | — (o dono roda a consulta de `lev-c360.md:130-139` na S4) | só leitura | 0,25 |
| F0.1 | Pendências lê as opções (NT-09), fonte jsonb dos últimos 30 dias | iskra (1), cliente360-api (1, passar o arg) | só deploy + flag; sem DDL | 1,5 |
| F0.2 | Contexto v2 (NT-04…NT-07), mais o conserto do 3RN `regra_id` (`consulta.py:1799`, `:1844`, `:1851`) | iskra, cliente360-api, facta-on, c6-api, 3rn-api (5 PRs) | deploys em ordem ISKRA → API → produtores; flags | 3,5 |
| F0.3 | `core.oferta_opcao` + escrita em OP-OF-13 com `_snapshot.congelar` e idempotência (NT-06, NT-06b) + backfill desde 09/11 (NT-02, NT-08) | iskra (2: rev nova + op de backfill) | **rev. nova na S4** (kit, `lock_timeout`, «sim»); backfill por kit com «sim» | 4 |
| F0.4 | Leitura (NT-10, NT-11) | iskra, cliente360-api | escopo novo no `c360-auth` | 2 |
| | **Total F0** | ~10 PRs | 1 DDL, ~6 deploys, 1 backfill | **≈ 11 (10–12)** |

**Riscos da F0:** a API repassar campo novo antes de o ISKRA aceitar manda a observação à fila morta (NT-07); o passo extra deixa a OP-OF-13 mais lenta (medir p95 no ensaio, com o volume medido); a rev. nova trava `core.observacao` se a FK nascer validada (criar `NOT VALID` e validar depois, como a rev. 101 fez, `rev101…up.sql:81-125`); o deploy do facta-on é automático no merge (`MEM:facta-on-merge-auto-deploy.md`).

### 6.2 F1: mostrar no web e pôr a fórmula no servidor

| O quê | Repositórios | d-agente |
|---|---|---|
| Zod do recurso novo (antes da API); tela «Opções por lead» na ficha, Admin/TI, flag (NT-12) | cliente360-web (2 PRs: schema, tela) | 2 |
| **Fórmula de comissão em R$ no servidor** com teste de paridade contra a tela de Comissões (NT-15) | iskra ou cliente360-api, + teste | 1,5–2 |
| Registro da opção usada pelo vendedor na Digitação (NT-13): rota nova na API, op no ISKRA, tabela de evento (DDL). **Só depois da revisão jurídica** (Q-20) | web, API, iskra | 2 |
| **Total F1** | | **≈ 5–6** |

Riscos: um campo novo na API antes do web derruba a ficha (`MEM:campo-novo-api-quebra-web.md`); o web faz deploy no merge (`MEM:web-merge-auto-deploy.md`).

### 6.3 F2: negociação na IA por regra

| O quê | d-agente |
|---|---|
| Emendas de contrato 03, 05, 08 e do F §4 (cada uma com «sim») | 1 |
| Migração da IA: `ia.confirmacao.opcao_id` + CHECK + hash (NT-29b), com «sim» nomeado | 0,5 |
| T3 minor (`degraus[]`), T5 com tabela, estado, contador, teto cedido, R9, pré-condição do T7 | 3 |
| Config `negociacao_tabelas` + migração do CHECK (com «sim» nomeado); alinhar o vocabulário `taxa_juros` (`H:64` × `H:198`) | 0,5 |
| TX-05b/06b (aprovação D36) | 0,25 |
| F3 com personas de objeção de valor, **personas de manipulação** (NT-26c) e casos de degrau; sombra | 2 |
| **Total F2** | **≈ 7–9** (inclui revisão) |

Dependências: B5.6 (motor v0) feito; B5.4 com a tabela no hash; F0.4 e NT-15 no ar. Riscos: mais T5 por atendimento sobe o custo; G-0088 aberto para qualquer degrau fora da FACTA.

### 6.4 F3: aprendizado

| O quê | d-agente | Quando |
|---|---|---|
| Descritivos E1–E5 (leitura na S4 pelo dono) | 2 | logo depois da F0 |
| Thompson v1 em sombra, avaliação off-policy, painel de comissão cedida | 4–6 | com dezenas de exposições por célula na própria política (§5.4); meses |

### 6.5 Cabe antes do congelamento sem ameaçar o piloto?

| Fato | Prova |
|---|---|
| Congelamento: 18/11 18:00 no cenário C; **19/11 18:00 no degrau** já adotado por delegação | `ROT:870,1272`; `RG0911:108` |
| Piloto real 26–30/11; **relatório 01/12 21:00**; teto 04/12 | `ROT:3`, `ROT:25` |
| Com 4 agentes **nem o pacote ALTO cabe** (r ≈ 0,47 < 0,49); com 5, folga ≈ 0,01 com os MÉDIO | `RG0911:161-163` |
| «Outro dia perdido acaba com o piloto real» | `RG0911:73` |
| Depois do congelamento: só correção avisada em IA, API, web e n8n | `ROT:870` |
| facta-on `#5` e API `#4` estão no mapa de deploys do piloto | `RG0911:131-133` |

**Recomendação explícita:**
1. **Não pôr a negociação na IA do piloto** (F2 fora). Não cabe e mexe no caminho crítico (motor, T3, T7, hash, confirmação, contratos).
2. **F0 vai à produção só depois do relatório do piloto** (01/12 21:00, `ROT:25`; marco, não data solta): ela toca API, ISKRA e facta-on, que estão no caminho do piloto. Só codar localmente se houver agente ocioso, sem tirar ninguém do pacote ALTO.
3. **Custo zero, já:** (a) no B5.4 em curso, pôr `tabela_identificador` no hash (o papel já manda) e **deixar espaço para `opcao_id`** na mesma conta (NT-29b), para não pagar a migração duas vezes; (b) gravar `objecao` e desfecho por passo (já existe); (c) **manter `observacao.ofertas` ligado** (já está desde 09/11: os dados se acumulam sem código novo, e o backfill NT-08 os recupera); (d) o dono rodar a medição de volume (F0.0), só leitura.
4. **Ordem depois do piloto:** F0.0 → F0.1 → F0.2 → F0.3/F0.4 → F1 (com NT-15) → (descritivos) → F2 → F3.

### 6.6 Esforço × prazo de relógio

O d-agente mede esforço, não calendário. A F0 tem **~6 deploys em ordem** (ISKRA → API → 3 produtores, mais a leitura), **1 DDL com kit e «sim»** e **1 backfill com «sim»**; cada escrita em produção vai com kit + «sim» próprio (`MEM:pre-aprovacoes-so-s4-04-11.md:22`), e deploys concorrentes já derrubaram produção (`MEM:deploys-concorrentes-27-10.md`). Com deploys em fila e vigia entre eles (HIPÓTESE: ~1 por dia útil), a F0 leva **≥ 2 semanas de relógio**, não 11 dias de calendário corridos. Contando do relatório do piloto, a F0 fecha em meados de dezembro (HIPÓTESE), e a F2 não começa antes de janeiro.

---

## 7. Perguntas fechadas ao dono

| Id | Pergunta | Padrão recomendado |
|---|---|---|
| **Q-01** | «Tabelas não cadastradas» é (a) opção que o banco devolveu e o 360 não guarda, (b) tabela sem comissão no catálogo, ou as duas? | **As duas** (§2.2) |
| **Q-02** | Piso da escada: % da **comissão em R$** do degrau 0, comissão mínima em R$ e coef mínimo absoluto? | **≥ 85 % da comissão** do degrau 0 **e** ≥ R$ X (X a definir); coef mínimo como trava secundária; sem piso, R9 não liga |
| **Q-03** | Ganho mínimo ao cliente para descer um degrau? | **≥ 5 %** no valor liberado (ou na parcela, conforme a objeção) |
| **Q-04** | Degraus por faixa; e degrau conta como contraproposta? | **0 / 1 / 2 / 2**; **conta** (teto global de 3 mantido) |
| **Q-05** | A «sem seguro» da FACTA pode ser degrau de negociação? | **Não no começo** (mantém a decisão de 24/10); reavaliar com os descritivos |
| **Q-06** | Gravar as opções numa tabela nova (`core.oferta_opcao`, DDL na S4) ou só ler o jsonb? | **Tabela nova** (NT-02), depois de medir o volume (F0.0); o jsonb fica como evidência |
| **Q-07** | Retenção das opções? | **Igual a `core.observacao`** (sem expurgo) |
| **Q-08** | Pendências passa a listar as alternativas sem catálogo (NT-09)? | **Sim**, atrás de `incluir_opcoes`, padrão `false` até a conferência |
| **Q-09** | A FACTA passa a pedir todos os prazos (modo grade) na consulta do n8n? Não cobra, mas pesa em latência | **Medir antes**; não mudar no piloto |
| **Q-10** | A negociação começa no **vendedor** (tela, F1) antes da IA? | **Sim** |
| **Q-11** | Pode haver sorteio entre alternativas permitidas depois de uma objeção (exploração ≤ 10 %, dentro do piso)? É diferente do «a dedo, sem sorteio» do disparo | **Sim, só na v1**, depois da sombra; v0 sem sorteio |
| **Q-12** | Recompensa do aprendizado: comissão realizada (pago) ou conversão pura? | **Comissão realizada** ÷ comissão do degrau 0, com **contrato digitado** como alvo intermediário corrigido depois |
| **Q-13** | Rotação entre bancos com banco oculto ao cliente? | **Não**: banco e CET são mostrados; rotação só pelo vendedor agora e na IA depois de T8 em 3RN/C6 |
| **Q-14** | Reter os dumps de `jobs_clt` com os `json_*` por ≥ 12 meses (histórico de N tabelas antes de 09/11)? | **Sim**, cifrado, só forma; extração com «sim» (`MEM:pii-extrato-producao`) |
| **Q-15** | F0 e F2 fora do piloto, F0 em produção só depois do relatório do piloto (01/12)? | **Sim** (§6.5) |
| **Q-16** | A confirmação da IA passa a se ancorar em `oferta_versao` **+** `opcao_id` (coluna e hash), com migração e emenda do contrato 05? | **Sim**, `opcao_id` NULL = degrau 0; espaço já reservado no B5.4 |
| **Q-17** | No C6, «mesmo vínculo» = mesma consulta (mesma observação, mesmo `job_ref`)? | **Sim** (o C6 não tem `vinculo_ref`) |
| **Q-18** | O 3RN entra na escada? | **Não na v0**; entra depois do conserto do `regra_id` e de uma regra de elegibilidade sobre `/3rn/regras` |
| **Q-19** | Onde mora a fórmula única de comissão em R$: ISKRA ou API? | **ISKRA** (op de leitura, perto do catálogo), com teste de paridade contra a tela de Comissões |
| **Q-20** | O registro da escolha do vendedor (NT-13) espera a mesma revisão jurídica do rastro da Digitação? | **Sim**; até lá, a tela mostra mas não registra |
| **Q-21** | Teto de comissão cedida por atendimento (R$ Z), orçamento mensal e limiar de corte por canibalização (queda do aceite no degrau 0)? | Z e orçamento a definir pelo dono; corte com **queda > 5 p.p.** por 2 semanas |

---

## 8. Riscos e o que pode dar errado

| Id | Risco | Efeito | Freio |
|---|---|---|---|
| R-01 | **Comissão menor** em contratos que fechariam de qualquer jeito | perda líquida | gatilho com fato de código (NT-26); piso em R$ (NT-24); teto cedido e orçamento já na v0 (NT-26b) |
| R-02 | **Canibalização:** o cliente aprende a recusar para ganhar mais | o degrau 0 converte menos | degrau nunca na 1ª apresentação; teto por faixa; textos sem citar «tabela» ou «outra condição melhor»; métrica com corte (§5.2, Q-21); personas de manipulação (NT-26c) |
| R-03 | **Custo de consulta paga** | C6: cada recálculo é uma simulação paga, preço desconhecido (`oferta.py:156-161`), numa pista de 1 concorrente com 429 que fecha para todos (`lev-c6-3rn.md:142-145`) | F2 só na FACTA (recálculo grátis); C6 só com G-0088 fechado e teto de pagas |
| R-04 | **Regra de banco e compliance** | 3RN: a AJIN aplica a taxa mínima do perfil só no `create_loans`; tabela mais barata pode ser recusada lá na frente (`consulta.py:1610-1615`). FACTA: troca a tabela GOLD na assinatura se o cliente recusa o seguro (`seguro_teto.py:5-12`). Banco e CET precisam ser informados (§4.8, HIPÓTESE jurídica) | recalcular sempre (NT-25); manter os cortes de taxa mínima e margem (`lev-facta.md:59-61`); jurídico |
| R-05 | **Tabela vencida ou encerrada** | oferta de tabela que o banco não aceita mais; coeficiente errado | validade da observação (§3.2); `encerrado_em` do catálogo (`gl360-schema.sql:641-656`); recalcular antes de mostrar |
| R-06 | **Comissão errada** | ranking errado: 3RN `/calcular` devolve o coef da tabela original e valida o prazo contra ela (`consulta.py:1799`, `:1851`); FACTA grava o coef financeiro no lugar da comissão (`cliente360_ctx.py:347`); fórmula em R$ duplicada | conserto na F0.2; comissão sempre congelada pelo ISKRA (NT-06); fórmula única com paridade (NT-15); backfill por banco (NT-08) |
| R-07 | **Pré-aprovado e conversão contaminados** | se uma opção ou um recálculo virar oferta, mudam os cards e as Comissões | NT-03: opção nunca vira oferta; `origem='consulta'` só |
| R-08 | **Web quebra** por campo novo | ficha 502 em todo CPF | recurso novo; web antes da API (NT-12) |
| R-09 | **Viés no aprendizado** | política determinística, efeito do vendedor, troca forçada, censura do pagamento | exclusões do §5.3; propensão gravada; dado do vendedor só no descritivo; alvo intermediário (§5.4) |
| R-10 | **Calendário do piloto** | qualquer item desta lista no caminho crítico ameaça o piloto | §6.5: nada em produção antes do relatório do piloto |
| R-11 | **Lista incompleta** | o n8n consulta 1 prazo (HIPÓTESE), o corte de 20, a lista cai inteira quando a escolhida não casa, a grade do C6 não vai | medir (`lev-c360.md:130-139`); Q-09 |
| R-12 | **Fila morta na subida** | a API repassa o v2 antes de o ISKRA aceitar: 422 e observações perdidas para a fila morta | ordem NT-07; flag off na API até o ISKRA no ar |
| R-13 | **Volume subestimado** | DDL, índices e p95 da OP-OF-13 dimensionados com número 10 vezes baixo | F0.0 antes da DDL (§3.2) |

---

## Notas da revisão (10/11, revisão final)

Crítica independente conferida na fonte (scripts `revisao-final-1.sh` e `revisao-final-2.sh`). Correções numeradas do crítico (H1–H20):

**Aplicadas (conferidas no código ou no papel):**
- **H1** citações: C6 `cliente360_contexto.py:65-100` era `instante_ms`; trocado por `:23-28`, `:237-253`, `:272-300`. 3RN `cliente360_consulta_ctx.py:110-122` era a leitura do `origem_fluxo`; trocado por `:20`, `:222-242`.
- **H2** NT-04 3RN: `opcao["regra"]` é o dict inteiro (`cliente360_novo.py:2015-2017`); ponto de mudança é `_ofertas`, não `parsers_3rn.py:341`.
- **H3** segundo defeito do 3RN confirmado: `consulta.py:1799` valida o prazo com `sim.get("ruleName")`.
- **H4/A17/B8** `escrita.py:212-245` é `_incluir_coeficiente`, que monta o arg da OP-CF-03 (`_snapshot.congelar`, `_snapshot.py:111`); `coeficiente.resolver_lote` é leitura `ro` (`catalogo.py:646`). Corrigidos NT-06 e §2.3.
- **H5** NT-07: a API descarta chave desconhecida contando (`contexto.py:536-537`); o 422/fila morta é do ISKRA (`_observacao_contexto.py:4-8`). Porquê reescrito; ordem mantida.
- **H6** §2.2: sem candidata com comissão, a tabela sem catálogo é escolhida (`online.py:2079-2083`, desempate por valor; web `opcoes-real.ts:66-68`, primeira não proibida, não «maior valor» como dizia a crítica para o web). Texto ajustado.
- **H7** NT-24 passou a comissão em R$ (`lev-ml.md` §6, «Piso de comissão»); NT-23 passou a Δcomissão ÷ Δcliente.
- **H8** NT-15 novo: fórmula em R$ no servidor com paridade. A IA recebe `comissao_esperada_brl` do chamador (`atendimentos.py:43`; a crítica citou `:45`, a linha real é `:43`).
- **H9** NT-29b novo: `ia.confirmacao.oferta_versao integer NOT NULL`, CHECK `>= 1` (`0001:177`, `:191`).
- **H10** NT-26 com fato de código, NT-26b teto cedido na v0, NT-26c personas. Rótulo do modelo em `modulos_fase.py:44-53`, `:58-60`.
- **H11** C6 sem `vinculo_ref` (`contexto.py:554`, `:561`); regra «mesma observação» (Q-17). 3RN fora da escada na v0 (Q-18).
- **H12** NT-06b (idempotência) e NT-08 por banco. Desfechos em `oferta_aplicar_observacao.py:100-105`; replay fora do envelope (`_observacao_contexto.py:18-19`).
- **H13** volume marcado como contradição; F0.0 de medição antes da DDL; números de GB retirados.
- **H14** DDL: `observation_id uuid` (`gl360-schema.sql:1248`), `pessoa_id uuid` (`:1250`).
- **H15** NT-13 condicionado à revisão jurídica (`registrar.ts:19-22`, que também pede política de expiração); dado mora no `core` do gl360 via ISKRA (Q-20).
- **H16** §5.4: ~520 por braço, células reduzidas + hierárquico, alvo intermediário, 22,4 % é de vendedor, viés do vendedor.
- **H17** §6.6 novo (esforço × relógio). Ver rejeição parcial abaixo sobre «01/12».
- **H18** NT-30 virou fato parcial: `SimularOperacaoReq` (`online.py:3794`, rota `:3813`) e `FormalizarReq` (`:4963`, rota `:5362`) têm `codigo_tabela` (`:3801`, `:4975`).
- **H19** resumo linha 2 reescrita.
- **H20** NT-01 cita `lev-c360.md:22` em vez de `config.py:34,50`.
- **D(ii)/(iii)** `opcao_id` declarado como referência lógica sem FK (§4.7); semântica de `ofertas.coeficiente` por banco (§3.2, NT-08).
- **E** métrica de canibalização com limiar de corte (§5.2, Q-21).

**Rejeitadas ou ajustadas, com motivo:**
- **H17 parcial («01/12 não tem fonte»): rejeitado.** 01/12 21:00 é a data do relatório do piloto no cenário C (`ROT:3`, `ROT:25`). O texto passou a dizer o marco («depois do relatório do piloto»), com a fonte. A sugestão de «checkpoint depois da rampa de 23-24/11» também não se sustenta: 23-25/11 é a sombra; o piloto real é 26–30/11 (`ROT:25`).
- **A22 («F:118 está na linha 119»): rejeitado.** Conferido com `sed -n 112,122p`: a linha 118 do F é o item 4 «Confirmação ligada ao dado»; a 119 é «Erros tipados». `F:118` fica.
- **G «1 deploy por dia na janela das 12:30»: não confirmado.** Não achei fonte para a janela das 12:30; o ritmo de ~1 deploy por dia útil ficou como HIPÓTESE em §6.6. A conclusão (≥ 2 semanas de relógio) se mantém pelo número de deploys e de «sim».
- **B6 «~86 mil observações/dia»: ajustado.** O «~600 obs/10 min» é uma leitura de 05/11 12:14 (horário comercial) e inclui reprovações; extrapolar a 24 h é teto, não estimativa. Registrado como contradição e teto, com medição obrigatória.
- **C8 escopo `comissao:ler`:** não conferido nesta revisão; NT-11 passou a dizer «quem já lê comissão» com HIPÓTESE sobre o nome do escopo.

**Achado próprio desta revisão:** o vocabulário de `objecao` em `H:64` não tem `taxa_juros`, mas o R3 (`H:198`) e NT-26 o usam. Alinhar antes da F2 (§6.3).
