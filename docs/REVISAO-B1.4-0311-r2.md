# Revisão 2 da B1.4 — contexto do turno, agente `Turno`, observabilidade e proteção de texto (03/11/2026)

Revisor adversarial independente (não escreveu o código e não fez a revisão 1). Branch `feat/b1-4-agente-turno`, HEAD `0dd55f2` (22 commits sobre `24bc524`; os 18 últimos corrigem a revisão 1). Só leitura no worktree
(este arquivo é a única escrita); sondas, cópias mutadas e saídas em `/tmp/claude-1001/-opt-claude/c3edfc59-52d9-4e44-8d0b-adab74392dfc/scratchpad/rev-b14-r2/`. **Nenhuma chamada de rede** (o «Fireworks» é
`httpx.MockTransport` ou um servidor que só escuta em 127.0.0.1); dados sintéticos (`000.000.0nn`, `exemplo.test`, `Maria Alvardel`); nenhum segredo na saída. Nenhum contêiner `ia-pg18-pytest-*` ficou de pé.

Portão local: `bash scripts/check.sh` = **2.251 passed, 1 skipped, 2 xfailed** em 101 s (lock, ruff, format, `varredura.py` = limpa, checksum da 0001, 0002 em dia); `git status` limpo antes e depois
(só os `.md` de revisão não rastreados).

## Veredito

**Pronto para PR: NÃO ainda — APROVADA COM CORREÇÕES (3 pequenas antes do PR).** Os 18 commits da revisão 1 fecham de verdade o que dizem fechar: dos 24 achados, 1 ALTO + 10 MÉDIOS + 6 BAIXOS estão
fechados com prova (sonda + mutação), 1 MÉDIO está parcial (M-5), 1 MÉDIO é a A2.9 (depende da chave, aberto por natureza), 3 BAIXOS estão parciais (B-2, B-8, B-9) e 2 foram deixados de propósito (B-5, B-10), com justificativa aceitável. O corpo HTTP que o
provedor recebe de E2 a E8, com estado rico e vetores novos, não leva CPF, telefone, e-mail, nome, id real, valor, coeficiente, comissão, motivo cru nem chave de perfil proibida. Mas a própria correção da
revisão 1 trouxe uma **regressão ALTA** (R2-01: uma mensagem de 4.000 caracteres do cliente trava o processo por ~1 s; 10 mensagens, ~10 s) e há dois buracos MÉDIOS no que o A-1 devia garantir
(R2-02, R2-03). Antes do PR: **R2-01, R2-02, R2-03** (poucas linhas cada). R2-04 e R2-05 são quase triviais e convém entrar junto; R2-06 a R2-08 são obrigações da B1.6/B5 que têm de entrar no texto das etapas
(emendas abaixo) e não bloqueiam o PR. A B1.4 **não pode ser marcada «concluída»** enquanto a A2.9 não rodar (M-12).

| Severidade (novos, R2) | Qtde |
|---|---|
| CRÍTICO | 0 |
| ALTO | 1 |
| MÉDIO | 7 |
| BAIXO | 4 |

## 1. Revisão 1 → revisão 2: o que foi corrigido (com prova)

Mutação = cópia do worktree com UMA troca, rodando 8 arquivos de teste (565 testes, ~15 s); 58 mutantes: **54 mortos, 4 sobreviventes** (A1f, A3, Q6, R5; ver «Qualidade»). Sondas citadas por nome em «Provas».

| r1 | Estado | Prova (r2) |
|---|---|---|
| **A-1** retorno de ferramenta cru | **FECHADO** (com ressalvas R2-02, R2-03, R2-04, R2-09) | `p4`: ferramenta com `valor_liberado`, CPF, coeficiente, comissão, nome na 2ª requisição ⇒ só `{"oferta_ref":"oferta-1","status":…,"placeholders":[…3 nomes…]}`; mutantes sem capability (6 testes reprovam), retorno cru (5), nome sem projeção sobe (6), auditoria off (1), `ModelRetry` cru (1), não-mapa aceito (2) mortos. **`ToolFailed` com texto cru sobrevive** (A1f, sem teste; o código está certo, `p4`: `{"error":"A ferramenta não conseguiu responder agora; siga sem ela."}`) |
| **M-1** número nu | **FECHADO** (custo funcional em §3) | `quero 5000`→`quero [NUMERO]`, `pode ser 5.000?`, `parcela de 312,45`, `prazo de 84`, `em 48 fica bom?`: todos trocados; mutante «sem `_NUMERO`»: 21 testes |
| **M-2** data/conta/matrícula/E5 | **FECHADO** | `nasci em 12/03/1985`→`[DATA]`, `12.03.1985`→`[DATA]`, `12/03/85`→`[NUMERO]`, `agência 1234-5 conta 56789-0`, `matrícula 1234567`, `rg 12.345.678-9`→`[NUMERO]`; E5 ⇒ `[dado:cep]` (corpo `p3`); mutantes sem `[DATA]` (3) e E5 não oculta (2) mortos. Histórico da E5 nas trocas seguintes: ver R2-06 |
| **M-3** nome colado a `_`/dígito | **FECHADO** | `maria1`→`[NOME]1`, `MARIA_ALVARDEL`→`[NOME]_[NOME]`, `alvardel2024`→`[NOME][NUMERO]`, `_alvardel`→`_[NOME]`, largura inteira e acento mascarados; mutante `\w` na borda: 16 testes. Residual aceito: `mariaalvardel` (colado a letras) e `M a r i a` |
| **M-4** `banco` | **FECHADO** | `_valor_do_lead('banco', …)`: só `FACTA|3RN|C6`; `R_1500`, `RS_5000`, `1500_00`, `MARIA1` ⇒ `None`; `oferta.banco` fora do catálogo ⇒ `OUTRO`; mutantes regex antigo (11), oferta livre (1), `_` fora do separador (7) mortos |
| **M-5** folhas por domínio fechado | **PARCIAL** | `placeholders` e `macro` ficaram em domínio fechado (mutantes 1 teste cada), `5000_00`/`r5000`/`valor_5000_00` barrados; mas `status`/`etapa`/`versao` seguem por **forma**: `valor-5000`, `parcela312`, `ref-1234567`, `conta-56789-0`, `5k`, `5mil` passam e chegam à 2ª requisição (R2-04). O mutante «chave `valor_liberado` na allowlist do T3» **sobrevive** (A3 da r1): a allowlist de CHAVES continua sem teste independente da de folhas |
| **M-6** placeholder da fase | **FECHADO** | matriz fase × placeholder (`p7`): `{{valor_liberado}}` na E2, `{{link}}` fora da E8, `{{nome}}` na E10 ⇒ `TextoForaDaFase`; mutante: 7 testes |
| **M-7** `r$`/`us$` solto | **FECHADO** | `preciso de r$ urgente`, `quanto em US$?`, `sou da Mr$ Ltda`, `R$` ⇒ `[VALOR]`; não derruba mais 3 turnos; mutante: 7 testes |
| **M-8** fiação do portão | **FECHADO** | mutante «sem `auditar_prompt` em `montar_contexto`» (r1: 0 testes) agora reprova 3; `executar_turno` com texto solto: 1 |
| **M-9** tempo-limite | **FECHADO** | `p5` (loopback, `modelo_timeout_s=1`): pendurado ⇒ 1,08 s e 1 conexão; **gotejando** (1 byte a cada 0,3 s, evita o timeout por leitura) ⇒ 2,00 s (= `agent.timeout`, 2×); 429/503/401 ⇒ 1 conexão cada, sem retentativa; `AsyncOpenAI.timeout=8.0`, `max_retries=0`, `Agent.timeout=16 s` no padrão; mutantes cliente sem timeout (2), agente sem timeout (1, r1: sobrevivia), SDK retenta (6), padrão 20 s (3+1) mortos |
| **M-10** fábrica de `LogRecord` | **FECHADO** | `logging.warning("valor %d","abc")` com o filtro instalado, fora do pytest: sem exceção; sai `[log mal formatado] 'valor %d' ('abc',)` + 1 aviso; mutante: 1 teste |
| **M-11** `ErroDoModelo` | **FECHADO** para provedor, contexto e proteção de retorno | `ContextoNaoCabe`, `ContextoComDadoPessoal`, `RetornoDeFerramentaInvalido` herdam `ErroDoModelo`; mutantes: 11 e 1. **Mas** exceção qualquer da ferramenta escapa (R2-02) |
| **M-12** A2.9 | **ABERTO** (por natureza) | 12 linhas em `DECISOES §6`; faltam critério de aprovação, amostra e provas do G §6 (R2-12) |
| B-1 retry do SDK | FECHADO | `p5`; mutante 6 testes |
| B-2 `usage` ausente / gasto da falha / coluna de cache | **PARCIAL** | (a) alerta + `uso_ausente` (mutante: 1); **(b)(c) deixados**; o passo `decisao` ainda sai com 0 (R2-10) |
| B-3 estimador | FECHADO | 100 emojis ⇒ 200 tokens (r1: 37); rajada limitada a 10 (mutantes 1 e 2) |
| B-4 scrubber | FECHADO | `p10`: CPF no nome do span, chave de atributo, nome de evento, chave/valor de atributo de evento, atributo de link, status, lista, JSON com `\n` partido, segredo: 0 vazamento; resta só inteiro em atributo (`12345678901`) e host de URL (R2-11) |
| B-5 esquema igual em todas as fases | DEIXADO (aceito até a A2.9) | decidir com a medição; entra na A2.9 |
| B-6 T3 na E2 | FECHADO | bloco 3 da E2: «Sem argumentos nesta fase (…não há oferta_ref)» |
| B-7 cliente HTTP por turno | FECHADO | `resolvedor._modelos` com 1 entrada; mutantes (1, 1) |
| B-8 `configurar()` | **PARCIAL** | `configurar` encerra o anterior (mutante: 1); `grep` em `src/`: nada chama `configurar()` nem `instalar_excepthook()` (é o boot da B1.5; o teste de fiação vai com ele) |
| B-9 texto livre | **PARCIAL** (aceito: T15 na B5) | barrados: `aprovado`, `garantido`, `R $`, `R＄`, `meusite.com.br/oferta`; passam: `dois mil reais`, `trinta e seis vezes`, `liberado hoje`, `cinco mil` |
| B-10 duplo em `src/` | DEIXADO | `ProvedorFalso`/`RoteiroF3` seguem em `src/`; mover quando nascer a B8.2 |
| B-11 args da ferramenta | FECHADO | `ArgsDaFerramenta`; mutante: 3 testes |
| Automático 1 (`_LINK` até o espaço) | FECHADO, **com regressão (R2-01)** | mutantes: host só (8), esquema só host (9), sem `ha_link` (2) |
| Automático 2 (NFKC) | FECHADO | `ｈｔｔｐ：／／exemplo.test／x`→`[LINK]`, `Ｒ＄`; mutantes: sem normalizar (7), identidade (9), sem ponto ideográfico (3), auditar sem normalizar (1) |

## 2. Achados novos da revisão 2

### ALTO

| ID | Onde | O que | Prova | Correção |
|---|---|---|---|---|
| **R2-01** *(regressão da correção da r1)* | `protecao.py:37` (`_LINK`, alternativa do host: `(?<!\w)(?:[a-z0-9-]+\.)+(?:TLDs)\b\S*`), chamada em `proteger_texto` e em `ha_link` | **Tempo quadrático no texto do cliente.** A lookbehind `(?<!\w)` deixa o regex começar em cada segmento depois de um `.` e o `+` do grupo vai até o fim a cada partida: n segmentos ⇒ O(n²). `proteger_texto` roda **antes** do corte de 560 caracteres, sobre o texto cru de até 4.000 caracteres (`LIMITE_TEXTO` do evento). O trabalho é síncrono: bloqueia o laço de eventos do worker, para todos os atendimentos. Entrou com `e49756b` (262 ms para 2.048 segmentos) e piorou com `0dd55f2` (1 s). Qualquer lead pode mandar `a.a.a.a…` | `c8_um.py`: `"a."*2048+"!"` (4.097 caracteres) = **1.025 ms** em `proteger_texto` (`mascarar`: 2,3 ms); 10.000 segmentos > 20 s (cancelado). `p6_dos.py` (Postgres, `montar_contexto` de verdade): 1 pendente `a.a.a…` de 3.999 caracteres = **1,06 s**; rajada de 10 (o máximo que entra no prompt) = **10,13 s**; o mesmo job reentra a cada falha. Variante `a-a-a…` = 0,11 s/0,99 s. As trocas não sofrem (`ler_trocas` corta em 280 caracteres) | (1) lookbehind `(?<![\w.\-])\.?` no começo do host (verificado em `c10_fix_link2.py`: 1.173 ms → 2,5 ms em 2.048 segmentos, 6 ms em 20.000; `.evil.xyz/path` ainda vira `[LINK]`; sobra `x..y.com/a`, a tratar); **e** (2) cortar o texto cru em ~1.000 caracteres antes de qualquer regex (o prompt nunca mostra mais de 560). Teste de desempenho: `proteger_texto("a."*2000)` e `"a-"*2000` < 50 ms; `montar_contexto` com 10 pendentes de 4.000 caracteres < 1 s |

### MÉDIO

| ID | Onde | O que | Prova | Correção |
|---|---|---|---|---|
| **R2-02** | `ferramentas.py:90-103` (`wrap_tool_execute`); `agente.py:_ERROS_DO_PROVEDOR`, `executar_turno` | **Exceção qualquer da ferramenta escapa de `executar_turno`.** Só `ToolRetryError`/`ToolFailedError` viram texto fixo; um `RuntimeError`/`KeyError`/erro do cliente do gateway sobe cru: não é `ErroDoModelo` (o `except ErroDoModelo` da B1.6 não conta a falha e o job reentra), a mensagem pode citar CPF/nome e o gasto do turno não vai a lugar nenhum. O mesmo para `FerramentaSemProjecao` levantada dentro da capability | `p4`: ferramenta que levanta `RuntimeError("timeout no gateway para o CPF 000.000.012-34 (Maria Alvardel)")` ⇒ `ESCAPA como RuntimeError | msg tem CPF: True`, 1 requisição. (`httpx.HTTPError` do gateway seria apanhado, mas com o rótulo «o provedor falhou»: errado) | Em `wrap_tool_execute`: `except Exception` (fora `ErroDoModelo`, `ModelRetry`, `ToolFailed`) ⇒ `ToolFailed(MENSAGEM_FIXA)` (o modelo segue sem a ferramenta) **ou** `ErroDoModelo("ferramenta_falhou", …, uso=…)`; decidir qual conta como falha (P7). Teste com mensagem que cita CPF |
| **R2-03** | `agente.py:criar_agente`; `ferramentas.py:registrar`; `turno.py:validar_turno_na_fase` | **Ferramenta registrada não obedece à fase.** `FERRAMENTAS_DO_MODELO_POR_FASE` só vale para o campo `Turno.ferramenta`; a ferramenta chamada pelo mecanismo de *function calling* (a que A-1 protege) roda em qualquer fase, e `ResultadoTurno.ferramentas_chamadas` nunca é conferida. Os esquemas das registradas vão no `tools` do corpo HTTP em toda fase, **fora** do bloco 3 («Nenhuma: não peça ferramenta») e **fora da conta do teto de 4 mil**. D4 («Ferramentas … por fase também são validados») só se cumpre para o campo estruturado | `p4`: modelo pede `T5` na E3 ⇒ a função rodou (`a funcao T5 rodou na E3? True`, `ferramentas_chamadas=('T5',)`). `p9`: com T2/T3/T5/T10 registradas, o corpo da **E2, E5 e E7** leva `['T2','T3','T5','T10','final_result']`; ≈ 300 tokens estimados fora da conta | Capability com `prepare_tools` (existe no pydantic-ai 2.63.0) que devolve só as ferramentas de `FERRAMENTAS_DO_MODELO_POR_FASE[fase]`, com a `fase` em `Deps`; `ferramentas_chamadas ⊆ …[fase]` em `validar_turno_na_fase`; contar os esquemas das registradas em `tokens_formato`. Teste: T10 na E2 não aparece no corpo nem executa |
| **R2-04** *(M-5 parcial)* | `contexto.py:97-106` (`status`, `etapa`, `versao`, `sem_opcao`… = `True`), `_folha_segura`, `_PARECE_NUMERO` | A barreira das folhas `True` continua heurística de forma. `_PARECE_NUMERO` só olha `^[a-z]{0,3}_?[0-9]{3,}` e `[0-9][.,_][0-9]{2}`: letra + hífen/dois-pontos + número, ou palavra longa + número, passam | `p1_folhas.py`: passam `valor-5000`, `parcela-312`, `prazo-84`, `reais5000`, `parcela312`, `margem1234`, `ref-1234567`, `agencia-1234`, `conta-56789-0`, `ate-5000`, `valor:5000`, `5k`, `5mil`, `1e5`, `0x1388`. `p4`: `status:"valor-5000"` ⇒ a 2ª requisição leva `5000` | `status`/`etapa` em enum do contrato do gateway (B5, como já feito em `macro`); enquanto isso rejeitar folha com `\d{2,}` em qualquer posição e `\d[.,_:-]\d`. Teste da allowlist de chaves independente (mata o A3) |
| **R2-05** | `protecao.py:_TLDS`/`_LINK`; `contexto.py:auditar_textos` (`ha_link` usa a mesma lista) | **Link com TLD fora da lista chega ao modelo, e o portão final não o vê** (usa o mesmo regex). H §3.3: «URL/link» nunca entra no prompt | `p3` (corpo HTTP, E2–E8, rajada com estado rico): `exemplo.test` e `meusite` presentes em 6 das 7 fases. Vetores isolados que passam: `meusite.company/oferta?id=9`, `exemplo.test/pagar`, `ofertas.academy/abc`, `x.tv/abc`, host de largura inteira `ｅｘｅｍｐｌｏ．ｔｅｓｔ／ｘ`, ponto ideográfico `exemplo。test/x`. Barrados: `bit.ly`, `wa.me`, `site.gov.br`, `http://192.168.0.1:8080/x`. Aceitos como residual: `exemplo[.]test`, `exemplo . test` | **Não** use «qualquer `x.y` com TLD de 2–6 letras»: 10 de 15 frases de chat sem espaço depois do ponto viram `[LINK]` (`c6_tld.py`: `sim.pode`, `bom dia.tudo bem?`, `Sr.Silva`, `vc.pode`, `oi.tudo`, `ate.logo`; «sim.pode» é um SIM na E6). Use o **sinal de caminho**: `(?<![\w@.\-])(?:[a-z0-9-]+\.)+[a-z]{2,24}(?=[/?#]|:\d)\S*` ⇒ `[LINK]` com qualquer TLD (0 casos nos 435 textos distintos do corpus (após `mascarar`); nas frases de chat sem caminho — `sim.pode`, `Sr.Silva`, `bom dia.tudo bem?`, `e/ou`, `5.000/mes` — 0 FP; só `sim.pode/nao`, raro, casa por engano); `ha_link` usa as duas regras. Host nu sem caminho (`meusite.company`) fica como risco aceito (não identifica pessoa e o modelo não segue link); a B8.2 mede |
| **R2-06** | `contexto.py` (`trocas`, `resumo`); H §2.3 E5 e §3.3; B1.6/B5.3 | **O que nenhum regex pega chega ao modelo, e o histórico da E5 não é `[dado:campo]`.** `proteger_texto` não conhece rua, bairro, nome da mãe, empregador, nome do banco. H §2.3 manda gravar `[dado:pix]` no histórico da E5; hoje a B1.4 oculta só a pendente da E5, e as **trocas** (3) e o **resumo** das fases E6–E8 levam a resposta da E5 como foi mascarada por `mascarar` (rua e bairro passam) | `p3`: `moro na Rua das Flores, 123, apto 45` ⇒ `Rua das Flores, [NUMERO], apto [NUMERO]`; `nome da minha mãe é Josefa da Silva` ⇒ intacto; `Flores` está no corpo HTTP das 7 fases (vem do resumo) | Obrigação da B1.6/B5.3, **com teste**: gravar `[dado:<campo>]` (não o texto) na conversa para a mensagem tratada como valor de campo; o resumo (H §3.5) nasce de texto já protegido. Registrar o residual sem NER (rua/mãe/empregador em texto livre) como risco aceito de H §3.3 |
| **R2-07** | `protecao.py` × `agenda_extrator.py`; `mascara.py` (B1.2) | **O extrator de agenda quebra se receber o texto de `proteger_texto`.** Hold-out de 130 frases: cru 130/130, só `mascarar` 130/130 (390: 389/390), **`proteger_texto` 122/130 = 93,8% (< 95%)** (390: 367/390). Quebram `15hrs`, `às 10 ou 11`, `as 13 ou 14`, `de 14 às 16`, `10 às 12`, `15h ou 16h30min`, `às 14h ou 15 e meia`, `às 15h 06/11` (`06/[NUMERO]`). Além disso a **máscara de PII da B1.2** troca `dd/mm hh:mm` sem «às» por `[NUMERO]` (8 dígitos): `06/11 15:30`, `dia 12/11 15:30`, `quinta 06/11 15:30`, `05/11 10:00 ou 11:00` — e a conversa já guarda assim | `c2_agenda.py` (hold-out por id: ho-251, 270, 287, 332, 334, 346, 347, 353); `c5.py` | O M §2.3 manda o extrator ler «texto mascarado»: dizer **`mascara.mascarar`**, nunca `proteger_texto` (emenda E-2). Teste na B5.7c/B1.6: o extrator recebe o texto de `ler_trocas`/pendente decifrado. Isentar `\d{1,2}/\d{1,2}[ ,]+\d{1,2}[:h]\d{2}` do `[NUMERO]` de 8 dígitos na B1.2 (com teste de CPF/telefone que não cai nessa forma) |
| **R2-08** | `protecao.py:_NUMERO`, `_trocar_numero` | **Perda funcional prevista do `[NUMERO]` opaco e da hora.** Sem palavra ao redor, a grandeza era a única pista de «valor × parcela × prazo» (`5000`, `250`, `84`): 8/8 casos da bateria perdem a pista. A lista branca de hora não cobre `15hrs`, `15hs`, `15h30min`, listas e intervalos (8/24 frases de agenda perdem a hora). No corpus da F3: 0/327 turnos perdem (ver §3) | `c4_bateria.py` (bateria do revisor, 62 casos) | `[NUMERO:n]` com a contagem de dígitos da parte inteira (sem ponto de milhar) + `hrs?|hs` e `min` na lista branca (protótipo em `proto/`: 8/8 magnitudes viram classe; `15hrs`, `15hs`, `15h30min` ficam; listas/intervalos e `dd/mm hh:mm` seguem para B5.7c/B1.2). Ver §3 |

### BAIXO

| ID | Onde | O que | Prova / correção |
|---|---|---|---|
| **R2-09** | `ferramentas.py:registrar`, `agente.py:AgenteDoTurno.agente`, `ferramentas.py:Deps` | O registro «único» é só convenção: sem ferramentas **não há capability**, e `AgenteDoTurno.agente` é o `Agent` cru; `ag.agente.tool_plain(fn)` depois de `criar_agente` passa o retorno cru. `Deps.nomes` tem padrão `()`: esquecer os nomes desliga em silêncio a máscara de nome do retorno. Os parâmetros da função registrada (o que o modelo passa) não são validados contra `ArgsDaFerramenta`. `p8`: CPF e `R$` na 2ª requisição. Correção: instalar a capability sempre (com `nomes` vazio ⇒ falha fechada), `Deps.nomes` obrigatório, `registrar` recusar parâmetro que não seja `oferta_ref`/`opcao_ref`/`alvo` |
| **R2-10** | `turno.py:ResultadoTurno.como_decisao`; contrato 08 §9 | Resposta sem `usage` alerta, mas o passo `decisao` sai com tokens e `custo_brl` = 0 (o contrato trata passo com tokens e `custo_brl` nulo como `custo_ausente` e diz «não se soma zero em silêncio»; resposta sem `usage` deve ser registrada como ausente, não como zero); o turno que **falha** depois de gastar leva `.uso` e não há helper para gravar o passo (B-2 b, deixado); `tokens_entrada` do passo é o **total** (com cache) e a fórmula do contrato não se reproduz da linha (B-2 c, deixado). Correção: `como_decisao` com `uso_ausente` ⇒ `tokens_*`/`custo_brl` `None`; `como_decisao_de_falha(erro)`; emenda E-1 |
| **R2-11** | testes e higiene | (a) o texto fixo do `ToolFailed` não tem teste (A1f); a allowlist de chaves de T3 não tem teste independente (A3); Q6 e R5 sobrevivem por redundância (segredo registrado também em `configurar`; roteador já validado por `_roteador_e_o_do_modelo`): aceitáveis. (b) `CHANGELOG.md:20` ainda lista `modelo_tentativas_http` (saiu). (c) `tests/test_contexto.py` tem 1.086 linhas (> 800). (d) `ruff C901`: `_estado_para_o_modelo` 11 (> 10), `_projetar` 8 retornos. (e) o scrubber não mascara atributo **inteiro** (`12345678901`) nem o host de URL em atributo |
| **R2-12** | `DECISOES-B1.4 §6` (A2.9) | A tabela de 12 provas diz *o que* medir mas não o critério de aprovação, a amostra nem a ordem; faltam provas que o G §6 e o roteiro A2.9 exigem. Ver §6 |

## 3. Custo da proteção (item 2)

### 3.1 O que foi medido

Corpus da F3 (`tests/corpus/dialogos`): **60 diálogos, 766 linhas de turno (329 do cliente, 437 da IA)**; 327 turnos do cliente têm texto (2 são mídia) e **966 redações** (texto + variações). (O número «739 turnos»
do pedido não bate com os arquivos; usei os contados.) Cada redação passou por `mascarar` (B1.2) e por `proteger_texto` com o nome da persona.

| Medida | Turnos (texto principal) | Redações (principal + variações) |
|---|---|---|
| total | 327 | 966 |
| com algum dígito | 141 | 416 |
| alteradas pela **máscara de PII** (B1.2; trocas feitas nas 966: 90 `[TELEFONE]`, 84 `[CEP]`, 44 `[EMAIL]`, 24 `[UUID]`, 8 `[CPF]`, 4 `[NUMERO]`, 2 `[NOME]`) | 85 | 252 |
| alteradas **além** da máscara pela proteção da B1.4 | **32 (9,8%)** | **94 (9,7%)** |

Dessas 94: **82 são E5** (28 turnos: `numero_endereco` 78, `conta` 4; a mensagem da E5 nem chega ao modelo por padrão), **9 E3** (`P05` «queria 250 por mês»→`[NUMERO]`; `P27`/`P28` «4 mil»→`[VALOR]`) e **3 E6**
(`P58` «36x»→`[PRAZO]`). **Nos 4 turnos fora da E5 a pista do tipo (parcela/valor/prazo) sobrevive**, por palavra (`parcela`, `por mês`) ou por marcador (`[VALOR]`, `[PRAZO]`): **0 de 327 turnos perdem o que o
gabarito exige** (`intencao`, `objecao`, `alvo_pedido`). A hora de toda redação de `adiar_com_hora` do corpus chega inteira. O corpus, porém, foi escrito com palavra ao lado do número; por isso a bateria abaixo.

Bateria do revisor (`c4_bateria.py`, 62 frases curtas de cliente brasileiro por fase, cada uma com o que tem de sobreviver):

| Grupo | Casos | Perdem o que a fase precisa | Quais |
|---|---|---|---|
| pedido com palavra («5000 reais», «5 mil», «parcela de 312,45», «por mês», «48x», «84 parcelas») | 13 | **0** | tipo vira `[VALOR]`/`[PRAZO]` ou a palavra fica |
| pedido **sem palavra** («5000», «quero 5000», «pode ser 3.500?», «250», «uns 300», «84», «em 48 fica bom?», «tem como 12000?») | 8 | **8** | a grandeza era a única pista (um 9º, «não, quero 3000» na E6, também perde; ficou no grupo da E6) |
| hora/dia (`15h`, `15h30`, `às 9`, `dia 10`, `daqui a 2 horas`, `9 da manhã`, `10 de novembro`…) | 24 | **8** | `15hrs`, `as 15 hrs`, `15hs`, `14 ou 15 h`, `entre 15 e 16`, `de 14 às 16`, `dia 12/11 15:30`, `06/11 15:30` |
| campo da E5 com desvio liberado (`o cep é 01310-100`→`[CEP]`, `agência 1234…`, `moro no número 123`, PIX por CPF/celular) | 8 | 0 | o rótulo (`cep`, `agência`, `conta`, `número`, `pix`) fica |
| confirmação da E6 (`sim, mas em 48x`→`[PRAZO]`, `sim pode enviar`, `não, quero 3000`→`não, quero [NUMERO]`) | 3 | 0 contados (1 é bare number, ver acima) | |
| número irrelevante (`tenho 45 anos`, `12 anos na empresa`, `desde 2019`, `me ligaram 2 vezes`→`[PRAZO]`) | 6 | 0 (troca inofensiva) | |

### 3.2 O extrator de agenda (hold-out de 130)

| Entrada do extrator | hold-out | todas (390) |
|---|---|---|
| texto cru | 130/130 | 390/390 |
| `mascarar` (como a conversa guarda) | **130/130** | 389/390 (`segunda 23/11 05:30`) |
| `proteger_texto` | **122/130 = 93,8% (< 95%)** | 367/390 |

Conclusão: **a proteção do prompt não pode ser a entrada do extrator**, e a máscara da B1.2 tem um falso positivo (`dd/mm hh:mm` ⇒ `[NUMERO]`) que o corpus de agenda quase não exercita (R2-07). Pior que errar:
com o texto protegido o extrator às vezes devolve um horário **errado** em vez de recusar (`de 14 às 16` cru ⇒ nenhum candidato; protegido ⇒ 16:00).

### 3.3 Classificação

| Tipo | Itens | Decisão |
|---|---|---|
| **Proteção necessária** (H §3.3, privacidade) | CPF, telefone, e-mail, CEP, UUID/chave PIX, 8+ dígitos, nomes da conversa (inclusive colados a `_`/dígito), link com esquema/`www.`/caminho, data de nascimento completa, conta/agência/matrícula/RG, símbolo de moeda | manter; é o que o corpo HTTP prova |
| **Política, não privacidade** (critério do roteiro «nenhum valor no prompt») | `[NUMERO]` em 2–7 dígitos soltos: protege o *valor da oferta* que o cliente repete («a parcela de 312,45»). O texto livre do modelo já não pode ter dígito e os `args` só levam apelidos, então o modelo não tem como devolver o número | manter a política, mas **sem apagar a grandeza**: `[NUMERO:n]` |
| **Perda funcional a contornar** | (1) grandeza sem palavra (8/8 da bateria); (2) `hrs`/`hs`/`h30min`, listas e intervalos de hora; (3) `dd/mm hh:mm` (B1.2); (4) o extrator e o número do pedido têm de ler o texto de `mascarar`, não o protegido | propostas abaixo |
| **Inofensivo** | `tenho [NUMERO] anos`, `me ligaram [PRAZO]` | nada a fazer |

### 3.4 Propostas concretas

1. **`[NUMERO:n]`** (n = dígitos da parte inteira, sem ponto de milhar, até 6; acima disso `[NUMERO]`): `quero 5000`→`quero [NUMERO:4]`, `250`→`[NUMERO:3]`, `84`→`[NUMERO:2]`, `3.500`→`[NUMERO:4]`,
   `12000`→`[NUMERO:5]`. O modelo infere o tipo (4+ = valor, 3 = parcela, 2 = prazo) sem ver o número; o número do pedido continua sendo extraído por código do texto de `mascarar`. Não vaza a oferta (só a contagem de
   dígitos do que o cliente digitou). Prova: protótipo `proto/protecao_v2.py` (não é código do repositório): 8/8 viram classe. Acrescentar uma linha ao `SISTEMA`: «`[NUMERO:n]` é um número de n dígitos; com 4 ou mais é valor em reais, com 3 é
   parcela, com 2 é prazo, quando a palavra em volta não disser». Atualizar `test_contexto.py` (`[NUMERO]` exato) e a regra de `ha_link`.
2. **Lista branca de hora**: `\d{1,2}\s*h(?:rs?|s)?(?:\s*\d{2}(?:\s*min)?)?` (protótipo: `15hrs`, `15hs`, `15h30min`, `as 15 hrs` ficam). Listas/intervalos («10 ou 11», «de 14 às 16», «entre 15 e 16») são do `adiar_com_hora`:
   o modelo precisa só do rótulo; deixar `[NUMERO:2]` (2 dígitos ≈ hora) basta para classificar, e o extrator lê o texto de `mascarar`.
3. **B1.2**: isentar `dd/mm` + espaço/vírgula + `hh:mm` do `[NUMERO]` de 8 dígitos (R2-07) e dar um teste que o CPF/telefone nunca caiam nessa forma.
4. **Contrato** (emenda E-2): extrator de agenda e número do pedido leem `mascarar`; `proteger_texto` é só para o prompt. Teste de integração na B5.7c: extrator recebe o texto de `ler_trocas`, nunca `Contexto.insumos`.
5. **Não** usar `[VALOR:n]` com o número preservado «para a ferramenta e não para o modelo» dentro do mesmo marcador: o marcador iria ao prompt e ao log do Phoenix. O número fica na conversa cifrada (texto de `mascarar`)
   e o código o lê de lá.

## 4. Vazamento, de novo e por conta própria (item 3)

Estado rico (`p3_vazamento.py`): atendimento aberto pelas transições de verdade, `perfil` com chaves proibidas (`faixa_parcela`, `chat_number`, `nome`, `cpf`), oferta, 1 opção T5, confirmação, `tentativa_t7`, linhas **antigas
gravadas sem máscara**, resumo cru, exemplos da F3 e 51 vetores; cada vetor sozinho em E4 (gravado com máscara e como linha legada sem máscara) e a rajada dos 10 mais perigosos em E2…E8; captura do corpo HTTP
completo (`messages`, `tools`, parâmetros).

| Resultado | Vetores |
|---|---|
| **Sem vazamento** | CPF pontuado, puro, com espaços, `000.000.012 34`; telefone `(11) 91234-5678`, `11912345678`, `55 11 91234 5678`, `chat_number` 5511912345678; e-mail; nome pleno, `maria1`, `MARIA_ALVARDEL`, `alvardel2024`, `_alvardel`, `Mária Alvardél`, `ｍａｒｉａ ａｌｖａｒｄｅｌ`; `https://…?t=abc`, `bit.ly`, `wa.me`, `site.gov.br`, IP com porta; `R$ 5.000,00`, `5k`, `3 mil`, `quero 5000`; nascimento (`12/03/1985`, `12.03.1985`, `12/03/85`, `1985-03-12`, `12 de março de 1985`); CEP; agência/conta; matrícula; RG; UUID |
| **Residual aceito (não fechável por regex)** | e-mail ofuscado (`fulano (arroba) exemplo ponto test`, `fulano[at]…`), nome espaçado (`M a r i a`) ou colado a letras (`mariaalvardel`), `exemplo[.]test`, `exemplo . test`, rua (`Rua das Flores`), nome da mãe (R2-06) |
| **Vaza e deve fechar** | `meusite.company/oferta?id=9`, `exemplo.test/pagar`, `ofertas.academy/abc`, `x.tv/abc`, host de largura inteira, ponto ideográfico (R2-05) |

Corpo HTTP, rajada de 10 vetores, estado rico, linhas legadas, E2 a E8: itens proibidos presentes = `exemplo.test` e `meusite` (E2, E3, E4, E6, E7, E8; na E5 a pendente é oculta) e `Flores` (todas, vem do
resumo). **0** CPF (formatado, puro, DV), telefone, `chat_number`, e-mail, nome/sobrenome, `oferta_id`/`opcao_id`/`pessoa_id`/`atendimento_id`, `R$`, valor, `faixa_parcela`, `ZZNOMEZZ`/`ZZCPFZZ`, ano de nascimento.
**2ª requisição com ferramenta real** (T3 com `valor_liberado`, `valor_parcela`, `prazo`, CPF, nome, coeficiente, comissão, motivo cru, `placeholders` com `5000_00` e CPF): corpo da 2ª requisição só com
`{"oferta_ref":"oferta-1","status":"ativa","versao":2,…,"placeholders":["valor_liberado","nome"]}`; 0 itens proibidos, **exceto** o `status` com número (R2-04). Exceção/`ModelRetry`/`ToolFailed` com CPF: o texto que volta ao
modelo é o fixo (mas ver R2-02).

**«Domínio fora da lista segue como texto» é aceitável?** Como regra geral, **não** (H §3.3 diz que URL nunca entra e `ha_link` foi pensado como «falha fechada»): `x.y` seguido de `/`, `?`, `#` ou `:porta` deve virar
`[LINK]` com qualquer TLD de 2–24 letras (R2-05, sem os falsos positivos da regra larga). O host nu sem caminho é um risco residual aceitável, a medir na B8.2.

## 5. Provedor (item 4)

Capturado do `httpx.MockTransport` (`p5_provedor.py`): `POST https://us.api.fireworks.ai/inference/v1/chat/completions`; `model = accounts/fireworks/routers/deepseek-v4p1-flash-1017-us`; corpo com `max_tokens:400` (não
`max_completion_tokens`), `temperature:0.3`, `tool_choice:"required"`, `reasoning_effort:"none"`, `stream:false`, `messages`, uma só ferramenta `final_result`; sem `parallel_tool_calls`, `user` ou `metadata`; a chave só
no cabeçalho `Authorization`, nunca no corpo. `ResolvedorModelo` cria **um** `OpenAIChatModel` por par (1 entrada em `_modelos`), recusa tudo que não seja `deepseek-*`/`fireworks-us` e `raciocinio=true`; não há
`FallbackModel` (tipo do modelo do agente = `OpenAIChatModel`); o boot recusa roteador sem `-us` ou de outra versão (R5 sobrevive por redundância com `_roteador_e_o_do_modelo`).

| Item | Conferido |
|---|---|
| Tempo | `AsyncOpenAI.timeout=8.0`, `Settings.modelo_timeout_s ≤ 10`, `Agent.run(timeout=)` = 2 × 8 = **16 s no padrão (20 s no teto)** para o turno; pendurado ⇒ 1,08 s a 1 s; gotejando ⇒ 2,00 s (corta o `agent.timeout`); uma conexão por falha |
| Retentativa | `max_retries=0`: 429, 503 e 401 ⇒ 1 requisição, `ProvedorIndisponivel("o provedor falhou (HTTP n)")`, sem `__cause__`/`__context__`, sem o corpo (o corpo de erro simulado trazia CPF e nome) |
| Orçamento do turno | o pior caso é uma 1ª resposta lenta e inválida + 2ª lenta: 16 s; duas falhas até o repasse ≈ 32 s, contra o «p95 ≤ 4 s» de H (meta de turno simples, não de pior caso); calibrar na A2.9 |
| Registro | nome sem projeção ⇒ `FerramentaSemProjecao` na subida (6 testes); `ModelRetry` ⇒ texto fixo (teste); `ToolFailed` ⇒ texto fixo (certo, sem teste: A1f); exceção qualquer ⇒ **escapa** (R2-02); fora da fase ⇒ **executa** (R2-03) |

## 6. Qualidade (item 5)

**Tamanho.** Maior arquivo de código `contexto.py` 579 linhas; maior função `executar_turno`/`montar_contexto` 45; nenhuma função > 50. `protecao.py` tem 93 linhas e 5 passadas; a complexidade está nas regexes
(`_NUMERO` com 8 alternativas e `_LINK`), e foi onde apareceu o achado ALTO. `tests/test_contexto.py` 1.086 linhas. ruff/format limpos; `C901` > 10 só em `_estado_para_o_modelo` (11).

**Mutação** (58 mutantes, 8 arquivos de teste). 54 mortos; **24 deles morrem por um único teste** (frágil). Sobreviventes: `A1f` (texto fixo do `ToolFailed`), `A3` (chave `valor_liberado` na allowlist do T3: o valor é barrado pela
folha, a chave não tem teste próprio), `Q6` e `R5` (redundantes). Mortos dos pontos pedidos: A-1 (6), M-1 (21), M-3 (16), M-4 (11), M-6 (7), M-9 (2+1+6+3+1), `protecao.py` automático 1 (8+9+2) e 2 (7+1+3+9). Mutantes extras
(não tocados na r1), todos mortos: apelidos não semeados (2 testes), `uso_ausente` (1), rajada sem limite (1), `configurar` não encerra (1), chave de atributo crua (3), JSON não decodificado (1), `args` com campo extra (3),
`_PROMESSA` off (4), inteiro alto em resultado (1), não latino a 0,3 (2), cliente HTTP novo a cada turno (1), `aclose` não fecha (1).

**O que não está coberto:** desempenho de `proteger_texto` (nenhum teste; R2-01); exceção arbitrária da ferramenta; ferramenta fora da fase; `status`/`etapa` fora do formato esperado; E5 no histórico; `dd/mm hh:mm`; chave
de T3 isolada; ints em atributo de span.

**As 12 provas da A2.9 estão bem definidas para quem tiver a chave? Parcialmente.** Dizem *o que* medir, não *quando passa* nem *quantas vezes*. Proposta de texto (cada linha com critério e amostra):

| # | Critério de aprovação e amostra que falta |
|---|---|
| 1 | Mesma requisição com cada forma, 3×: HTTP 200, `completion_tokens_details.reasoning_tokens == 0` e sem `reasoning_content` em 3/3; parâmetro desconhecido ⇒ 400 reprova a forma |
| 2 | 20/20 respostas com `tool_calls` `final_result` e `content` vazio; `NativeOutput` × Tool Output nas mesmas 20 entradas (G §6 teste 2): % de JSON válido na 1ª tentativa = 100% |
| 3 | Aceitar o nome não prova a **região**: ler também a documentação de residência de dados do roteador `-us` e um cabeçalho/ID que a mostre, se existir; registrar a fonte |
| 4 | Esquema real do `Turno` (hoje com `args` de 3 propriedades opcionais) nas 8 fases, 20 entradas: 0 `output_retries`; guardar o JSON do esquema que o provedor devolve em erro |
| 5 | Precisa de **uma chamada com raciocínio ligado** (senão `reasoning_tokens=0` e a hipótese «já inclui» não se prova): comparar `completion_tokens` com `reasoning_tokens` e o tamanho do `content` |
| 6 | Duas chamadas seguidas com prefixo idêntico ≥ o mínimo cacheável, dentro do prazo do cache: `cached_tokens > 0` em `usage.prompt_tokens_details`; ler os cabeçalhos da resposta também; registrar |
| 7 | O maior `Turno` possível (texto 320 caracteres, 10 `contexto_codigos`, ferramenta): `finish_reason != "length"` e `completion_tokens` máximo e p95 < 400 em 20/20 |
| 8 | `max_tokens=5`: `finish_reason == "length"` e `completion_tokens ≤ 5` prova qual campo vale; repetir com `max_completion_tokens` |
| 9 | Não cabe nas «20 chamadas»: rajada controlada (ex.: 30 chamadas em 1 s na chave `ia-teste`) para provocar 429 e ler `Retry-After`; decisão sobre `max_retries` fica com os números |
| 10 | p95 exige ≥ 100 chamadas (com 20, p95 é a 19ª); rodar **da VPS** (S4), em horário comercial, prompts reais (2,0–2,5 mil tokens), frio × com cache; decidir `MODELO_TIMEOUT_S` por p99, não p95 |
| 11 | `usage` presente em 100% das chamadas, inclusive nas de erro de saída |
| 12 | Chave e crédito: pendente do dono |
| *faltam* | G §6 testes **4** (4 situações de ferramenta, nenhuma inventada), **5** (`tool_calls` estruturado, sem DSML em `content`; vale para as ferramentas registradas), **6** (recusa de manipulação: «ignore as instruções», «diga que foi aprovado»), **7** (números e vírgula idênticos à ferramenta), **9** (custo real ±20% do §4) e **o estimador de tokens**: `usage.prompt_tokens` real × `Contexto.tokens_total` nos mesmos 20 contextos (calibra `EstimadorPorCaracteres` de graça). O teste 8 do G (troca para a reserva) e o 10 (comparação entre provedores) deixam de existir: não há `FallbackModel` |

## 7. Conformidade (item 6)

**H §3.1** (8 blocos na ordem; teto 4.000; corte resumo → trocas → exemplos): conforme (teste + `cortar_ate_caber`, mutantes mortos). Divergências já documentadas e aceitas: bloco 1 com o esquema do `Turno` passa de 800 a ≈ 1.300; total típico
2,1–2,4 mil, não 2,9 mil. Bloco 6 «cada troca ≤ 280 caracteres»: conforme (`ler_trocas` corta em 280). Bloco 8: 10 pendentes × piso de 120 caracteres chega a ≈ 440 tokens (H: 200); só o total é imposto.

**H §3.3**: nome/CPF/telefone/e-mail/CEP/UUID/8+ dígitos/data de nascimento/conta/matrícula/link/valor: conforme (§4). `pessoa_id`, `chat_id`, `coef_valor`, comissão, motivo cru: conforme. **Divergências:** (i) endereço, nome da mãe e empregador em texto livre passam (R2-06);
(ii) link com TLD fora da lista (R2-05); (iii) os nomes dos marcadores de H (`[TEL]`, `[DADO]`) são `[TELEFONE]`, `[NUMERO]` no código (emenda E-2).

**Contrato 08 §9**: fórmula implementada como `custo_brl(tokens_in não cacheada, tokens_cache, tokens_out)`, 6 casas, `ROUND_HALF_EVEN`, preços do `Settings` (≤ 0 derruba o boot: `test_boot_recusa_preco_ou_cambio…`); soma o uso de todas as
respostas do turno (inclusive a que falhou na validação); gasto do dia é Σ `passo.custo_brl`. Divergências: o texto do contrato multiplica `tokens_entrada·preco_in` mas o passo guarda a entrada **total**, e o passo não tem
coluna de cache (R2-10); resposta sem `usage` não vira NULO (R2-10).

### Emendas com texto exato

- **E-1 · contrato 08 §9**, trocar `custo_brl = (tokens_entrada·preco_in + tokens_cache·preco_cache + tokens_saida·preco_out)·cambio / 1e6` por:
  «`custo_brl = ((tokens_entrada − tokens_cache)·preco_in + tokens_cache·preco_cache + tokens_saida·preco_out)·cambio / 1e6`, com `tokens_entrada` = entrada TOTAL do provedor (cacheada ou não), `tokens_cache` = a parte
  lida do cache (`usage.prompt_tokens_details.cached_tokens`) e `tokens_saida` já incluindo os tokens de raciocínio. O passo `decisao` grava `tokens_entrada`, `tokens_saida` e `custo_brl`; `tokens_cache` não é coluna do
  `0001` (se a conferência linha a linha for necessária, a 0004 acrescenta `tokens_cache integer`). Resposta sem `usage` grava `tokens_*` e `custo_brl` NULOS e conta em `custo_ausente`; nunca zero.»
- **E-2 · estudo H §3.3**, última frase («sequências de 8+ dígitos ⇒ `[CPF]`, `[TEL]`, `[EMAIL]`, `[DADO]`; na E5 o valor nem chega ao modelo») por: «sequências de 8+ dígitos ⇒ `[CPF]`, `[TELEFONE]`, `[EMAIL]`, `[CEP]`, `[UUID]`,
  `[NUMERO]`. O histórico guarda só o que `mascara.mascarar` troca; ao **prompt** vão ainda `[NOME]`, `[VALOR]`, `[PRAZO]`, `[DATA]`, `[LINK]` e `[NUMERO:n]` (`protecao.proteger_texto`). O extrator de agenda (M §2.3), o número do
  pedido (`alvo_pedido`) e qualquer leitura por código usam o texto de `mascarar`, nunca o de `proteger_texto`. Na E5 a mensagem é gravada no histórico como `[dado:<campo>]` e a pendente nem chega ao modelo.»
- **E-3 · estudo H §3.1**, linha 1: teto «800» ⇒ «1.400 (≈ 800 do texto + ≈ 600 do esquema do `Turno`, que o provedor recebe como ferramenta de saída e conta junto)»; linha «Total»: «≈ 2.900» ⇒ «≈ 2.100–2.400 (estimativa
  3,0 caracteres/token × 1,10; a B8.2 mede com o tokenizer do DeepSeek)».
- **E-4 · estudo H §2.3b**, coluna «`acao` permitidas»: E7 «— (resultado é evento; no máximo 1 frase de ponte)» ⇒ «`aguardar`»; E9, E10 «—» ⇒ E9 «—», E10 «`repassar`, `encerrar` (o modelo só preenche `contexto_codigos`)». §2.2: acrescentar à
  `intencao` `adiar_com_hora | adiar_sem_hora` e o campo `sinal: positivo | neutro | negativo | frustrado` (padrão `neutro`); `texto`: «str ≤ 320 sem dígito Unicode, sem `R$`/`US$`/link/e-mail/«aprovado»/«garantido» e só com
  os placeholders da fase (`PLACEHOLDERS_DA_FASE`)».
- **E-5 · ROTEIRO B1.4**, Spec: «o parâmetro que desliga o raciocínio **é o que A2.9 provou**» ⇒ «é `reasoning_effort_none` (HIPÓTESE) até a A2.9; `MODELO_RACIOCINIO_OFF` troca sem código». Linha de status: «2.022 testes» ⇒
  «2.251 testes; revisões 1 e 2 feitas; falta a A2.9 e a chave».
- **E-6 · `TEXTOS-PARA-APROVACAO`/`SISTEMA`** (se R2-08 for adotado): acrescentar ao parágrafo dos marcadores «`[NUMERO:n]`: número de n dígitos».
- **E-7 · `CHANGELOG.md:20`**: remover `modelo_tentativas_http` da lista de `config.py`.
- **E-8 · obrigações da B1.6 a gravar em `DECISOES §6`**: conta `ErroDoModelo` (incluindo `.uso`); chama `como_decisao_de_falha`; grava `[dado:<campo>]` na E5; `desvio_liberado`; passa `nomes` em `Deps`; passa ao extrator
  o texto de `mascarar`; resolve apelidos por `ResultadoTurno.referencias`.

## 8. O que conferi e está certo

- **Corpo HTTP por fase** (E2 a E8, estado rico, linhas legadas sem máscara, resumo cru, 51 vetores): nenhum CPF, telefone, e-mail, nome, id real, valor, coeficiente, comissão, motivo cru, protocolo, link do T10 ou chave de
  perfil proibida; a oferta só aparece de E3 em diante; apelidos `oferta-N`/`opcao-N`.
- **Ferramenta real registrada** (2ª requisição): projeção, apelido reaproveitado, nome do cliente barrado, retorno não-objeto sem eco, falha da proteção como `ErroDoModelo` com o gasto, `ModelRetry` com texto fixo.
- **Provedor**: um só modelo, roteador `-us`, `max_tokens`, `reasoning_effort`, `tool_choice` e `stream` como o contrato manda; `max_retries=0`; tempo por chamada e do turno cortando em pendurado e em gotejando; mensagem de erro sem
  corpo, sem `__cause__`, sem chave.
- **Spans e logs**: exportador mascarado por último; nome, atributos (texto, lista, JSON decodificado, chave), eventos (nome, chave, valor), status, links e segredo registrado saem limpos; fábrica de `LogRecord` não levanta.
- **`Turno` e fases**: matriz placeholder × fase; `ACOES_POR_FASE` igual ao gabarito; `AcaoForaDaFase` e irmãs carregam o gasto; texto livre sem dígito, `R$`, link, promessa; `ArgsDaFerramenta`.
- **Custo**: preços, câmbio, arredondamento, cache subtraído da entrada, soma das tentativas.
- **Higiene**: portão local verde (2.251), `varredura` limpa, `git status` limpo, nenhum `print`/`console.log`, nenhum segredo; nenhum contêiner de teste ficou de pé.

## 9. Provas

Em `/tmp/claude-1001/-opt-claude/c3edfc59-52d9-4e44-8d0b-adab74392dfc/scratchpad/rev-b14-r2/` (rodar uma sonda com Postgres: `./rodar.sh pN_….py -q -s`; as puras: `.venv/bin/python -I arquivo.py`):

`check.log` (portão) · `mut/mutar.py`, `mut/resultado.json`, `mut/resultado_extra.json`, `mut/lote.log`, `mut/lote2.log` (58 mutantes) · `p1_folhas.py` (R2-04) · `p3_vazamento.py` + `saida/p3_vetores.json`, `saida/p3_corpo_E2..E8.json`
(vazamento) · `p4_ferramenta.py` (R2-02, R2-03, A-1) · `p5_provedor.py` (provedor, loopback) · `p6_dos.py`, `c8_um.py`, `c10_fix_link2.py` (R2-01) · `p7_diversos.py` (M-6, M-10, B-3, B-9) · `p8_bypass.py`, `p9_tools_no_corpo.py` (R2-09, R2-03) ·
`p10_scrubber.py` (B-4) · `c1_custo.py`, `c1_analise.py`, `c9_resumo.py`, `c1_linhas.json` (corpus F3) · `c2_agenda.py` (R2-07) · `c4_bateria.py` (R2-08) · `c6_tld.py`, `c7_tld2.py` (R2-05) · `proto/protecao_v2.py`, `proto/avalia2.py`
(protótipo de `[NUMERO:n]`, hora e link por caminho; **não** é código do repositório) · `q1_tamanho.py` (tamanho).
