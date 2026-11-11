# Matriz de restrições RS-01..RS-20 (+ RS-21..RS-34) — Fase 0 da revisão 0911

Gerada em 10/11/2026 por leitura (só leitura) do plano, do roteiro v3.3, dos contratos vigentes e da exportação.
Nada aqui é veredito: é o mapa do que a Fase 2 tem de provar, onde olhar e o que perguntar.

## Como ler

**Prefixos de caminho** (todos confirmados por grep nos scripts `scripts/rs-0[1-5]-*.sh` desta pasta):

| Prefixo | Caminho real |
|---|---|
| `IA/` | `/home/danilo/ia-revisao-0911/src/ia-atendimento/` (origin/main `9a4baca`) |
| `B16/` | `/home/danilo/ia-revisao-0911/src/ia-atendimento-b1-6a/` (PR #13 `9a714e3`, CONFLICTING) |
| `EST/` | `/home/danilo/ia-revisao-0911/src/ia-atendimento-esteira/` (`feat/esteira` `9e1afe3`, só local) |
| `KS4/` | `/home/danilo/ia-revisao-0911/src/ia-atendimento-kits-s4/` (`kits/s4` `148cc72`, só local) |
| `GW/` | `/home/danilo/ia-revisao-0911/src/gl-gateway/` (`92e9754`) |
| `FO/` | `/home/danilo/ia-revisao-0911/src/facta-on/` (`8c3e5ab`) |
| `API/` | `/home/danilo/ia-revisao-0911/src/cliente360-api/` (`6e9c62d`) |
| `DUB/` | `/home/danilo/ia-revisao-0911/src/bancos-duble/` (`ca3ed2c`) |
| `KITS/` | `/home/danilo/ia-revisao-0911/kits/` |
| `ROT` | `/opt/claude/docs/planejamento-ia/ROTEIRO-DE-ACAO.md` (v3.3) |
| `C0n` | `/opt/claude/docs/planejamento-ia/contratos/0n-*.md` (sem sufixo = vigente) |
| `PLANO` | `/opt/claude/docs/planejamento-ia/estudos/PLANO-REVISAO-0911.md` |

`cliente360-web` **não foi exportado** (`fase0/MANIFESTO.md`, «cliente360-web … DIFERENTE»; sem linha na tabela de exportações): tudo que dependa dele é NÃO EXISTE / fora da exportação.

**Estados iniciais** (PLANO §3 «Três estados de prova» + §8 «Quarto estado de prova»):

- **A PROVAR** = existe código/kit na exportação; a Fase 2 fecha em PROVADO EM CÓDIGO ou PROVADO EM ENSAIO, ou abre achado.
- **NÃO EXISTE** = nenhum artefato na exportação; vira critério de aceite do bloco indicado (não é achado de código).
- **NÃO VERIFICÁVEL** = depende de estado vivo de produção; segue sonda só-leitura sugerida (o dono roda com `!`).
- Uma RS pode ter partes em estados diferentes; cada parte está marcada.

**Proveniência do papel:** a âncora de texto é a prova; o número de linha (lido hoje na v3.3) é só cortesia.

**Regra de verificação** (PLANO §4 Fase 3): qualquer achado contra uma linha desta matriz recebe 3 verificadores, seja qual for a severidade.

---

## Achados de Fase 0 que mudam o plano de leitura (ler antes da Fase 2)

| # | Fato medido | Prova | Efeito |
|---|---|---|---|
| F0-1 | `app/log_acesso.py` e a flag do tap **não existem** na main do `facta-on` | `scripts/rs-05-contagens.sh`: «facta-on main: log_acesso … 0 arquivo(s)», «FACTAON_TAP … 0 arquivo(s)»; `ls FO/app` sem `log_acesso.py` | PLANO §4 Fase 2 manda ler `app/log_acesso.py`: só existe no PR #49 (não exportado). RS-15/RS-17 lado facta-on = NÃO EXISTE na main |
| F0-2 | O nome da flag do tap diverge no papel | C05 título de §4 «flag `FACTAON_TAP_IA`, nasce **off**» × ROT Painel A6.4 «flag `FACTAON_TAP_RETORNOS` off» | Pergunta dirigida em RS-15 |
| F0-3 | `online.py` fica em `FO/app/routers/online.py`; as linhas do contrato 05 estão velhas | `FO/app/routers/online.py:4672` (`/proposta/por-cpf`), `:4857` (`/proposta/conferir`); C05 §2.6 cita «`online.py:4754,4569`» | Citar por âncora, não pela linha do contrato |
| F0-4 | Janela do `conferir` ainda é 10 | `FO/app/config.py:123` `conferir_janela_min: float = 10.0`; `FO/docker-compose.yml:151` `:-10` (C05 §3 cita `:146`) | RS-10 parte facta-on = NÃO EXISTE (B3.2) |
| F0-5 | `feat/b1-6a` tem `ferramentas.py` (arquivo), a main tem `ferramentas/` (pacote) | `diff -rq` em `rs-04-papel.sh`: «Only in …b1-6a…: ferramentas.py», «Only in …ia-atendimento…: ferramentas» | RS-04 e RS-10 precisam ser lidas nas **duas bases**; a integração `LeitorDeCpf` × `executar_efeito` não existe em SHA nenhum |
| F0-6 | Modelos Pydantic sem `hide_input_in_errors` | `IA/src/ia_atendimento/corpus/modelos.py:33` e `IA/src/ia_atendimento/pessoas_teste/formas.py:31`: `ConfigDict(extra="forbid", frozen=True)` | Candidato a achado de RS-16 (falta decidir se «tocam texto de cliente») |
| F0-7 | Default privileges dão `DELETE` a `ia_app` no schema `procrastinate` | `IA/migrations/0001_esquema.up.sql:11` | RS-12: alínea (v) «`ia_app` sem DDL/DELETE» × desenho da fila |
| F0-8 | `ia-sumidouro`: sem allowlist e `guardar_corpo=true` | `KITS/gateway/rotas-ia.sh:10` e `:27`; C01 §4.3 «sem allowlist e **com** corpo guardado (7 d)» | RS-03/RS-06/RS-14: corpo inteiro (com PII) em `gateway.payloads` por desenho; só a credencial `chatguru-ia-teste` separa |
| F0-9 | Não há `ntfy`, `fim_do_dia`/19:45 nem `executar_efeito` na main; `ntfy` e 19:45 também não na `b1-6a` | `rs-05-contagens.sh` (0 arquivos em `IA/src` e `B16/src`; `executar_efeito` só em `B16/src/ia_atendimento/ledger.py:520`) | Confirma PLANO §8 para RS-10, RS-11, RS-25 |
| F0-10 | `cliente360-api` não tem rota da IA em código | `rs-05-contagens.sh`: «c360-api src: /v1/ia rotas (py) … 0 arquivo(s)»; só o contrato JSON cita `/pessoas:resumos` (`API/src/c360api/contrato/cliente360.json:73`) e `/pessoas:propostas` (`:93`) | B4 sem código, como o PLANO §1 diz; leitores não procuram |

---

## RS-01 — Modelo só em `us.api.fireworks.ai` + roteador `-us`

- **Fonte:** ROT §0.3 regra 1, âncora «"global" ≠ EUA: só `us.api.fireworks.ai` + roteador `-us`» (l. 41); ROT §0.1 item 2 «Fireworks só-EUA» (l. 18); PLANO §3b RS-01 e §8 «RS-01 rede descreve desenho (a VPS não existe) ⇒ NÃO EXISTE».
- **Como se prova:** (código) leitura dos validadores + teste existente + grep de ausência de qualquer outro host de saída; (rede) ensaio/sonda — não há VPS.
- **Onde olhar:**
  - `IA/src/ia_atendimento/config.py:25-27` (`HOSTS_DO_MODELO = frozenset({"us.api.fireworks.ai"})`), `:42-44` (`PADRAO_ROTEADOR`, `ROTEADOR_PADRAO` com sufixo `-us`), `:84` (`modelo_base_url_1`), `:174-176` (roteador = `<modelo_nome>-us`), `:217-240` (validador de `modelo_base_url_1`: https, host, porta, sem credencial/query; ramo «local» em `:237`).
  - `IA/src/ia_atendimento/agente.py:3` (docstring «UM provedor»), `:73` (`PROVEDOR_FIREWORKS_US`), `:115` (par modelo/provedor fora do MVP), `:143` (cliente `httpx.AsyncClient` injetável), `:177` (`base_url=s.modelo_base_url_1`).
  - Outras saídas de rede do processo: `IA/src/ia_atendimento/observabilidade.py:246-254` (OTLP para `phoenix_endpoint`), `IA/src/ia_atendimento/config.py:98-100,249-262` (validador do `phoenix_endpoint`), `IA/src/ia_atendimento/ferramentas/modo.py:41,140-172` (`VARIAVEIS_DE_AMBIENTE`, bases de produção/teste por serviço), `IA/src/ia_atendimento/fila.py:63-80` (Postgres).
  - Testes: `IA/tests/test_config.py`, `IA/tests/test_agente.py`.
  - Rede: `EST/docker-compose.yml`, `EST/docs/DEPLOY.md`, `EST/scripts/deploy-vps.sh` (1 arquivo da esteira cita nft/iptables/egress — localizar); ROT A4.2 «**uma** linha nft: `iifname wg0 ip saddr 10.90.0.5 tcp dport 5434 accept`» (só entrada na S4); `/opt/claude/docs/planejamento-ia/estudos/semana-1/e-infra-s4-vps.md`.
- **Evidência esperada:** boot recusa qualquer `MODELO_BASE_URL_1` ≠ `https://us.api.fireworks.ai[:443]/…` e qualquer roteador sem `-us`; nenhum outro construtor de cliente de modelo em `IA/src`; teste que reprova com `api.fireworks.ai` (global). Rede: política de saída (allowlist `nft output`) descrita e testável.
- **Estado inicial:** código = **A PROVAR**. Rede/egress da VPS = **NÃO EXISTE** ⇒ critério de aceite de **A4.1/A4.4** (firewall da VPS) e **A4.9** (deploy do orquestrador): chain `output` com allowlist (Fireworks US, S4 `10.90.0.4:5434`, S2 `10.90.0.2`, DNS, ntfy.sh) e prova por `curl` recusado a host fora da lista.
- **Perguntas dirigidas:**
  1. O ramo «local» de `config.py:237` (http/https para host local) pode ser ativado em produção por variável? O que o restringe (lista de hosts locais, flag de ambiente)?
  2. `HOSTS_DO_MODELO` é conferido só no boot ou também quando o `httpx.AsyncClient` é **injetado** (`agente.py:143`)? Um cliente injetado com `base_url` próprio ou com `follow_redirects`/`trust_env` (proxy por `HTTPS_PROXY`) fura a regra?
  3. Existe algum segundo campo (`modelo_base_url_2`, reserva, T15, juiz) em `config.py` ou em `agente.py`? O sufixo `_1` sugere que sim: listar.
  4. O `phoenix_endpoint` aceita host público? O validador (`config.py:249-262`) restringe a túnel/host interno (D-30) ou só a forma?
  5. Resolução DNS: o host é fixado por nome; há pin de IP ou verificação de região na resposta (cabeçalho do roteador)? Se não, registrar como limite.
  6. `PADRAO_ROTEADOR` aceita `accounts/<qualquer-conta>/…-us`: uma conta de terceiro passaria? Isso importa?

## RS-02 — Nada da Anthropic; nunca a API oficial da DeepSeek

- **Fonte:** ROT §0.3 regra 1 «**Nada da Anthropic no produto** (atendimento, T15, juiz de qualidade)… **Nunca a API oficial da DeepSeek**» (l. 41); ROT §0.5 alínea (a); PLANO §3b RS-02.
- **Como se prova:** grep de ausência em src, prompts, fixtures, locks; leitura do validador de domínio proibido.
- **Onde olhar:** `IA/src/ia_atendimento/config.py:5` (docstring), `:232` («domínio proibido (API oficial…»); `IA/pyproject.toml:21` (dependências); `IA/uv.lock:466` (`openai`), `:483-516` (`openinference-*`), `:525-671` (`opentelemetry-*`), `:809` (`pydantic-ai-slim`); `IA/src/ia_atendimento/modulos_fase.py`, `contexto.py`, `mensagens.py`, `roteiro_f3.py` (texto de prompt); `IA/fixtures/duble/*.json`; `GW/requirements.lock`, `FO/requirements.lock`, `DUB/uv.lock`, `API/uv.lock`.
- **Evidência esperada:** 0 ocorrência de pacote `anthropic`, `google-genai`, `together`, `deepseek` (SDK) nos locks; as únicas menções a Anthropic/DeepSeek oficial em `IA/src` são o comentário e a denylist de `config.py`; teste que prova a recusa de `api.deepseek.com`.
- **Estado inicial:** **A PROVAR**. Medido na Fase 0 (`rs-05-contagens.sh`): 1 arquivo de `IA/src` casa `anthropic|claude` e 1 casa `deepseek.com|api.deepseek` (ambos compatíveis com `config.py`); 2 arquivos em `IA/tests`+`IA/fixtures` casam (provável teste da recusa); 0 em `GW/app`, `FO/app`, `DUB/camada-a|b`. Lock do `ia-atendimento` (`rs-02-grep-ia.sh`) sem `anthropic`.
- **Perguntas dirigidas:**
  1. Quais são exatamente os 2 arquivos de `IA/tests`+`IA/fixtures` que casam? É asserção de recusa ou fixture com nome de modelo proibido?
  2. A denylist de `config.py:232` é por sufixo de domínio? Cobre `api.deepseek.com`, `*.deepseek.com`, `api.anthropic.com`, `*.googleapis.com`, `api.together.xyz`, `api.openai.com`? Ou só os dois primeiros?
  3. `pydantic-ai-slim` foi instalado com quais extras (`IA/pyproject.toml`)? Algum extra traz SDK de outro provedor transitivamente?
  4. T15 (verificador por modelo, alínea l) e o juiz de qualidade têm configuração própria de provedor em algum lugar? Se não existem, registrar NÃO EXISTE (B5.9, B12.2) com o critério «mesma allowlist de host».
  5. Há texto «Claude»/«Anthropic» em prompt, texto fixo (TX) ou `CHANGELOG`/docs que vá para a imagem (`pyproject.toml:46` `force-include`)?

## RS-03 — CPF nunca a modelo/prompt/log/span/banco IA/ntfy/Kan/payload de entrada

- **Fonte:** ROT §0.3 regra 2 «**CPF nunca ao modelo, prompt, log, span do Phoenix, banco da IA, ntfy, Kan ou payload de entrada**» (l. 42); ROT §0.2 «Nunca escreva segredo, CPF, telefone, nome, texto de cliente em roteiro, Kan, ntfy, commit ou log (PD-6)» (l. 37); C01 §4 «**A10** = `{chat_id, phone_id, texto_mensagem, …}`» e §7 «Regra de log (F07…)»; C05 §2.6 «CPF na URL: logs, spans e `passo` (F29)»; C08 §5.5 «o CPF fica no n8n»; PLANO §3b RS-03 («O limite declarado de `mascara.py` é **contradição da regra 2** e vai ao dono como decisão»).
- **Como se prova:** leitor «CPF ponta a ponta» (cada caminho até cada sumidouro); teste existente + lista do que ele não cobre; grep de ausência; canário reduzido (PLANO §8).
- **Onde olhar:**
  - Entrada: `GW/app/projecao.py:4-57`, `GW/app/main.py:452-457` (projeção antes de encaminhar e de guardar), `GW/app/rotas.py:66-69,129,166,189-198` (`corpo_campos`, fallback de coluna ausente), `GW/migra_rotas_ia.sql:37-51`, `KITS/gateway/rotas-ia.sh:7-10,24-27`.
  - Orquestrador: `IA/src/ia_atendimento/mascara.py:63` (`_cpf_valido`), `:135` (`_trocas_de_digitos`), `:125` (`_trechos_isentos`), `:196` (`mascarar`) e a docstring do módulo (limite declarado); `IA/src/ia_atendimento/protecao.py:35,120-124`; `IA/src/ia_atendimento/contexto.py`, `mensagens.py` (o que o modelo vê); `IA/src/ia_atendimento/passos.py`, `linha_tempo.py:66-69` (`passo`); `IA/src/ia_atendimento/observabilidade.py:190` (`FiltroSemPii`), `:259-273` (`ExportadorMascarado`); `IA/src/ia_atendimento/scrubber.py:40-95`; `IA/src/ia_atendimento/api/logs.py:22-32`; `IA/src/ia_atendimento/ferramentas/saida.py:51-94` (`_tem_pii`, `_varrer`), `ferramentas/projecao.py:45,120`, `ferramentas/especificacao.py:43-44` (nomes proibidos `cpf`, `cpf_hash`); `IA/src/ia_atendimento/corpus/pii.py`.
  - Banco: `IA/migrations/0001_esquema.up.sql:191` (`ferramenta_chamada`), `:248` (`passo`), `:223` (`agendamento`), `:341` (`candidato`), `IA/migrations/0002_procrastinate.up.sql:72` (`procrastinate_jobs.args`), `IA/migrations/0004_anexo_rpa_e_espelho.up.sql:22` (`espelho_evento`).
  - Testes: `IA/tests/test_vazamento_corpo.py`, `test_mascara.py`, `test_protecao.py`, `test_observabilidade.py`, `test_contexto.py`, `test_ferramentas_gateway_revisao.py`; `GW/tests/test_ia_forward.py`, `test_ia_rotas.py`; `FO/tests/test_log_sem_pii.py`.
  - facta-on (CPF em query): `FO/app/routers/online.py:4672`, `:4857`; `FO/app/logs.py:7,21`.
- **Evidência esperada:** para cada sumidouro (prompt, `passo`, `ferramenta_chamada`, `procrastinate_jobs`, span, stdout/stderr, resposta HTTP, `espelho_evento`, ntfy, `gateway.payloads`) um teste ou leitura que mostre CPF ausente; lista explícita das formas não cobertas.
- **Estado inicial:** **A PROVAR** (código e testes existem). ntfy = **NÃO EXISTE** (B6.6). Limite do `mascara.py` = **decisão do dono** (não é achado a refutar). `ia-sumidouro` guarda corpo inteiro por desenho (F0-8) = **risco aceito a confirmar** (qual decisão do dono o aceitou?).
- **Perguntas dirigidas:**
  1. Copiar literalmente o limite declarado na docstring de `mascara.py`. Que formas de CPF passam: por extenso, com letras no meio, partido em duas mensagens, 11 dígitos com DV inválido, dentro de URL/nome de arquivo, em `url_arquivo`, em áudio transcrito, em resumo gerado pelo modelo?
  2. `_trechos_isentos` (`mascara.py:125`): o que fica isento e por quê? Um CPF pode cair num trecho isento (valor em R$, protocolo, código AF)?
  3. `protecao.py:35` corta em 1000 caracteres: o corte acontece antes ou depois de mascarar? Um CPF partido pelo corte sobra como 6+5 dígitos?
  4. `test_vazamento_corpo.py`: que sumidouros ele captura (log, span, `passo`, resposta, job args)? Quais não?
  5. `procrastinate_jobs.args`: algum job leva `texto`, `chat_number` ou corpo do evento como argumento? (`IA/src/ia_atendimento/enfileirador.py`, `fila.py`, `evento_mensagem.py`.)
  6. Fallback de `GW/app/rotas.py:166`: se as colunas `corpo_campos`/`guardar_corpo` não existem, as rotas `ia-*` **não são carregadas** — confirmar que é fail-closed e que não há caminho em que `ia-mensagem` rode com `corpo_campos` NULL (C01: NULL = repassa tudo). `corpo_campos = '{}'` é barrado pelo CHECK (`migra_rotas_ia.sql:48-51`) — e pelo código (`rotas.py:191`)?
  7. `responsavel_nome` e `responsavel_email` estão na A10 (C01 §4): são do consultor, não do cliente — confirmar; e `link_chat`/`url_arquivo` podem carregar telefone/CPF na URL?
  8. A saída de ferramenta que volta ao modelo (`ferramentas/saida.py:63` `_tem_pii`): o que acontece quando casa — corta o campo, falha a ferramenta, ou só marca?
  9. Erros do cliente HTTP do gateway de ferramentas levam a URL (com `?cpf=`) na mensagem de exceção? Quem a limpa antes de `passo`/log (C05 §2.6 itens 1–2; `test_url_com_cpf_sintetico_nao_chega_a_log_span_nem_passo` existe?).

## RS-04 — CPF só em memória do gateway de ferramentas, só durante a chamada

- **Fonte:** ROT §0.3 regra 2 «**Na VPS só em memória do gateway de ferramentas, só durante a chamada ao 360/FACTA, nunca em disco/log/trace** (D18…)» (l. 42); ROT §0.5b D-29 «`cpf` em memória do gateway»; PLANO §8 «RS-04: `.revelar()` não tem call sites; o CPF entra por `LeitorDeCpf` (`gateway.py:156,192,358`)».
- **Como se prova:** leitura de todos os pontos de leitura/uso; teste existente; grep de ausência de persistência.
- **Onde olhar:** `IA/src/ia_atendimento/ferramentas/segredo.py:17` (`CpfEmMemoria`); `IA/src/ia_atendimento/ferramentas/gateway.py:62` (`_DESTINOS_COM_CPF = {"producao","duble"}`), `:95-99` (`Chamada.cpf`, `repr=False`), `:156` (`LeitorDeCpf`), `:192,205` (injeção), `:358-371` (leitura e montagem da `Chamada`), `:373-380` (`_cpf`), `:391` (registro do destino); `IA/src/ia_atendimento/ferramentas/catalogo.py:149,165,175,180` (`usa_cpf=True`: T1, T5, T7, T8); `IA/src/ia_atendimento/ferramentas/especificacao.py:155,220`; `IA/src/ia_atendimento/ferramentas/projecao.py:45`. Testes: `IA/tests/test_ferramentas_gateway.py`, `test_ferramentas_gateway_revisao.py`, `apoio_gateway.py`. Segunda base: `B16/src/ia_atendimento/ferramentas.py` e `B16/src/ia_atendimento/ledger.py:520` (`executar_efeito`).
- **Evidência esperada:** `CpfEmMemoria` sem `__repr__`/`__str__`/pickle/JSON que revelem; lido uma vez por chamada, entregue só ao executor, nunca gravado em `ferramenta_chamada`, `passo`, span ou log; destino `interceptado`/`fixture` nunca recebe CPF.
- **Estado inicial:** **A PROVAR** na main (gateway B5.1). **NÃO EXISTE**: implementação real do `LeitorDeCpf` (quem busca o CPF: 360 `pessoas:resumos`) ⇒ aceite de **B5.2**; integração com `executar_efeito` ⇒ aceite de **B1.6 (integração a/b) e B5.4**.
- **Perguntas dirigidas:**
  1. `rs-05-contagens.sh` deu 0 `.revelar(` em `IA/src`. Como o executor extrai o valor de `CpfEmMemoria`? Qual é o método/atributo e quem o chama?
  2. `gateway.py:360-363`: o que são as linhas 361-363 (zera o CPF se o destino não é com CPF)? Há `await` entre a leitura (`:360`) e a entrega ao executor em que uma exceção/cancelamento deixe o objeto preso num traceback ou em `locals` capturados por span?
  3. `CpfEmMemoria` sobrevive em `Chamada` depois do retorno? Alguém guarda `Chamada` (lista de chamadas do turno, `Deps`, cache)?
  4. Para destino `duble`, o CPF real do lead vai ao dublê (WireMock grava requisições)? O dublê está na VPS (A4.10) — isso é «disco»?
  5. O leitor é `None` por padrão (`gateway.py:192`): ferramenta `usa_cpf` sem leitor falha fechado (`:378`)? Com que código?
  6. Na `b1-6a`, `ferramentas.py` conhece CPF? Na integração, quem garante que o `ledger` não serializa o pedido com CPF em `ferramenta_chamada`?

## RS-05 — AES-256-GCM, AAD completa, chaves por mês, chave e texto cifrado em hosts distintos, descarte no dia 31

- **Fonte:** ROT §0.3 regra 3 «só mascarado e cifrado (AES-256-GCM na aplicação) em `conversa_cifrada`» e «com a chave AES do mês descartada o texto cifrado é inútil» (l. 43); ROT §0.6 P-R10 «**Chaves AES em arquivo 0600 `/etc/ia-s4/conversa.keys` na VPS (montado `:ro`), fora do Coolify**… descarte = `shred` da linha do mês» (l. 260); ROT §0.5c «última tag e chave AES de dezembro 18/11 12:30–17:00» (l. 191); PLANO §8 «RS-05: descarte no dia 31 é só papel».
- **Como se prova:** leitura + testes existentes (cifra, cofre); descarte = não verificável/inexistente.
- **Onde olhar:** `IA/src/ia_atendimento/cifra.py:5-8` (AAD `atendimento_id|seq|remetente|tipo|chave_id`), `:27` (`AESGCM`), `:74-94` (`montar_aad`, AAD da mensagem e do cofre), `:104-113` (leitura do arquivo, `st_mode & 0o077`), `:141-144` (chaves distintas por mês), `:149-195` (`Chaveiro`); `IA/src/ia_atendimento/segredos.py:44-47`; `IA/src/ia_atendimento/cofre.py:39-83`; `IA/src/ia_atendimento/conversa.py`; `IA/migrations/0001_esquema.up.sql:309-328` (`conversa_cifrada`: nonce 12, `apagar_em ≤ +30 d`; `cofre`: `expira_em ≤ +7 d`). Testes: `IA/tests/test_cifra.py`, `test_cofre.py`, `test_segredos.py`, `IA/tests/casos/cifra_db.py`. Kits/esteira: `EST/docker-compose.yml` (montagem `:ro`), `EST/docs/DEPLOY.md`.
- **Evidência esperada:** chave de 32 bytes exigida; nonce aleatório de 12 bytes por mensagem; AAD sem campo opcional; troca de qualquer campo da AAD ⇒ `FalhaAoDecifrar`; arquivo com permissão > 0600 ⇒ boot recusa; `chave_id` por mês e regra de qual é o vigente; procedimento escrito de descarte com prova (linha removida, `ChaveDesconhecida` na leitura).
- **Estado inicial:** cifra/AAD/arquivo 0600 = **A PROVAR**. Descarte mensal (`shred`, quem, quando, prova) = **NÃO EXISTE** (`rs-05-contagens.sh`: 0 arquivo com `shred|descartar_chave` em `IA/src`, `IA/scripts`, `IA/kits`, `KITS/`) ⇒ critério de aceite de **A4.9** (montagem) e de kit novo de chave (PLANO §0.7 «chave AES de dezembro» inexistente), a fechar antes do **B9.1**. Hosts distintos (chave na VPS, texto na S4) = **NÃO VERIFICÁVEL** (VPS não existe) ⇒ sonda: `stat -c '%a %U' /etc/ia-s4/conversa.keys` na VPS + `docker inspect` do contêiner (mount `ro`) + grep do nome da variável no Coolify da S2 (sem valor).
- **Perguntas dirigidas:**
  1. Como `chave_id` mapeia para mês (AAAAMM? inteiro livre?) e quem escolhe o `vigente` (`Chaveiro.de_arquivo(caminho, vigente)`): configuração manual, relógio? O que acontece na virada do mês com processo no ar?
  2. «Descarte no dia 31» × retenção de 14 d após o encerramento: a mensagem de 30/11 cifrada com a chave de novembro precisa ser lida até 14/12. A regra do papel é coerente com a chave por mês? Qual é a data real de descarte que não quebra a retomada?
  3. O `repr` de `Chaveiro` e de `Cifrado` (`cifra.py:63,173`) revela algo? As chaves ficam em atributo acessível por traceback?
  4. O cofre usa `seq=0` e `remetente=REMETENTE_DO_COFRE` (`cifra.py:94`): duas gravações da mesma finalidade no mesmo atendimento têm AAD idêntica — o nonce aleatório basta; há risco de troca entre versões?
  5. `fstat` confere dono além do modo? Arquivo 0600 de outro usuário, link simbólico, diretório pai aberto?
  6. `CHAVE_H16`, `CHAVE_FINGERPRINT`, `CHAT_REF_CHAVE` (`config.py:106-109`) são HMAC permanentes (ROT §0.2 «Residual conhecido (RG-109): `msg_fingerprint` com chave permanente»): onde moram (Coolify?) e isso anula parte do descarte?

## RS-06 — Livro de retenção por armazém

- **Fonte:** ROT §0.3 regra 3 «**14 dias** após o encerramento (teto 30 d), e no Phoenix `ia_obs` por 14 dias» e «**(D-32) Antes de G2:** provar que o texto mascarado no Phoenix e nos fulls/backups é eliminado em 14 d» (l. 43); ROT PD-6 «os jobs do Procrastinate são podados (B1.3); o espelho da S2 apaga o `chat_number` > 30 d (B6.4)» (l. 435); C04 §4.6 «Retenção (F34)»; C01 §4.3 «`ia-sumidouro`: sem allowlist e **com** corpo guardado (7 d)»; C08 §3 «`chat_number`… `cofre` (finalidade `canal`, ≤ 7 d)» e §16 item 4 «retenção até `encerrou` ou 8 d»; PLANO §3b RS-06 e §8 (acrescenta `espelho_evento`, `agendamento`, `candidato`, prazo desta pasta, simular `fn_texto_podar(7,1,1)`).
- **Como se prova:** uma linha por armazém: origem do relógio · mecanismo · quem dispara · prova por consulta de forma · estado.
- **Onde olhar e estado por armazém:**

| Armazém | Onde | Estado inicial |
|---|---|---|
| `ia.conversa_cifrada` (14 d após `encerrado_em`; teto `apagar_em` 30 d) | `IA/migrations/0001_esquema.up.sql:309-320`, `:420-434` (`fn_texto_podar`, limites 7–14 / 1–7); `IA/src/ia_atendimento/jobs.py:37-38,382-391`; `IA/src/ia_atendimento/fila.py:60,179-181,214` (periódica `podar` 03:30 SP) | A PROVAR |
| `ia.cofre` (1 d após encerrar; teto `expira_em` 7 d) | `0001:322-328`; `IA/src/ia_atendimento/cofre.py:83` (`expirar`) | A PROVAR |
| `ia.passo`, `ia.atendimento` (365 d) | `0001:404-408` (`fn_atendimento_podar`, mínimo 365); `jobs.py:39,387` | A PROVAR |
| `procrastinate_jobs`/`events` (args) 7 d concluídos / 30 d falhos | `jobs.py:35-36,363-374` (`podar_jobs`); `IA/migrations/0002_procrastinate.up.sql:72,97` | A PROVAR |
| `ia.espelho_evento` | `IA/migrations/0004_anexo_rpa_e_espelho.up.sql:22-39` (só `ON DELETE CASCADE` do atendimento) | A PROVAR (parece sem poda própria: vive 365 d) |
| `ia.agendamento`, `ia.candidato`, `ia.ferramenta_chamada`, `ia.confirmacao`, `ia.opt_out` | `0001:223,341,191,171,330` | A PROVAR (qual tem poda? o que guardam?) |
| Phoenix `ia_obs` (14 d) | sem código na exportação; `observabilidade.py` só exporta | NÃO VERIFICÁVEL ⇒ D-32 bloqueia G2 |
| pgBackRest / WAL / dump lógico | `KITS/s4/provar.sh:7-11,80-95` (dump de `ia_atendimento` passa; `ia_obs` recusado «por desenho») | NÃO VERIFICÁVEL |
| `gateway.payloads` (7 d) | `GW/app/metricas.py:56-116`; `GW/init_payloads.sql`; `KITS/gateway/rotas-ia.sh:7-10` | A PROVAR (quem apaga aos 7 d?) + NÃO VERIFICÁVEL (estado vivo) |
| Espelho S2 `ia_espelho.sob_ia` (`chat_number` ≤ 30 d) | só papel: C04 §4.1–§4.6 | NÃO EXISTE ⇒ aceite de **B6.4** |
| n8n `execution_data` | `KITS/gateway/ia-sumidouro.workflow.json:39-40` (`saveData*: none`); C04 §2.3 | A PROVAR (sumidouro) / NÃO EXISTE (braço, B6.2) |
| ntfy.sh (terceiro) | nenhum código | NÃO EXISTE ⇒ aceite de **B6.6** |
| Logs de contêiner (VPS, S2) | `EST/docker-compose.yml` (driver/rotação) | A PROVAR (esteira) / NÃO VERIFICÁVEL |
| `~/ia-corpus` (D-31 «apagar o corpus bruto no gatilho por estado») | fora da leitura (denylist) | NÃO VERIFICÁVEL por agente ⇒ sonda |
| `~/ia-revisao-0911/` (esta pasta) | PLANO §8 «prazo de descarte desta pasta» | NÃO EXISTE (prazo não escrito) ⇒ decidir na Fase 5 |
| `$SEGREDOS_DIR` do kit do gateway | `KITS/gateway/env-gateway.sh:26-27` («Apagar tudo isto depois do piloto») | A PROVAR (existe passo de apagar?) |

- **Evidência esperada:** para cada linha, consulta de forma (`count(*)`, `min(criado_em)`), nunca valor; pior caso «atendimento que nunca encerra» coberto pelo teto absoluto.
- **Sondas só-leitura sugeridas (dono, `!`):** `pgbackrest info` (retenção de fulls); no Phoenix, a política de retenção do projeto e `select min(start_time) from spans` em `ia_obs`; na S2, `select count(*), min(recebida_em) from gateway.payloads where rota like 'ia-%'`; `select count(*) from ia.conversa_cifrada where apagar_em < now()` (deve ser 0 depois das 03:30).
- **Perguntas dirigidas:**
  1. Pior caso: atendimento que **nunca encerra** (`pausado` eterno, `repassando` preso). `apagar_em` (30 d) apaga a conversa mesmo sem encerramento (`0001:427` `c.apagar_em < now()`): confirmado? E o `passo`/`agendamento`/`espelho_evento` desse atendimento?
  2. `ia_app` tem `EXECUTE` em `fn_texto_podar` (`0001:442`): chamar `fn_texto_podar(7, 1, 1)` apaga texto com 7 d em vez de 14 (piso 7). É aceitável («não apagar cedo»)? E `p_lote=1` deixa resto — a periódica repete até zerar ou roda uma vez por dia com lote 5000?
  3. A periódica `podar` roda no worker: se o worker fica parado (piloto encerrado, VPS desligada em dezembro), quem apaga? A promessa de 14 d depende de processo vivo.
  4. `gateway.payloads`: existe job/SQL de expurgo aos 7 d no repositório do gateway ou é premissa de operação?
  5. `espelho_evento` guarda o quê (payload? `chat_number`?) — ler as colunas em `0004:22-37`.
  6. `podar_jobs` cobre `procrastinate_events` e `procrastinate_periodic_defers`? Job `failed` fica 30 d: seus `args` têm PII?
  7. D-32: que evidência concreta o aceite de A4.5/A4.8 vai exigir (configuração do Phoenix, `pgbackrest expire`, repo separado para `ia_obs`)? Hoje não há nada escrito ⇒ registrar como bloqueio de G2.

## RS-07 — Inventário de segredos

- **Fonte:** ROT §0.3 regra 6 (segredos entre as escritas de produção) e PD-2 «Segredos, rotação, firewall, DROP… sempre pedem «sim» novo» (l. 427); ROT §0.5b «Fireworks (chave em arquivo 0600, nunca no chat)» (l. 163); ROT P-R10 (l. 260); C01 §5 «Credenciais e env (um reinício)»; C02 §2 «Token só no vhost WG (nginx; A4.4)»; C03 §1 «Duas credenciais, nunca uma»; C08 §1 tabela de origens («`PUT /config/{nome}` | token `ti`…»); PLANO §3b RS-07 e §8 (Postgres do Coolify S2 e backups, `CHAVE_H16`/`CHAVE_FINGERPRINT` no Coolify, ntfy.sh como terceiro).
- **Como se prova:** tabela (nome · onde mora · permissão · quem lê · rotação · o que o vazamento permite · prova de ausência em git/Kan/log), sem valores; gitleaks (baseline) como entrada.
- **Onde olhar:** `IA/src/ia_atendimento/config.py:78-109` (campos `SecretStr`: `database_url`, `modelo_api_key_1`, `api_tokens`, `phoenix_api_key`, `chave_h16`, `chave_fingerprint`, `chat_ref_chave`), `:138` (tokens por origem), `:184` (banco como `ia_app`), `:252,268`; `IA/src/ia_atendimento/segredos.py:32,44-47`; `IA/src/ia_atendimento/api/auth.py:23-36`; `IA/src/ia_atendimento/observabilidade.py:266` (`registrar_segredo`); `GW/app/config.py:29,85,101,118,189`, `GW/app/assinatura.py:25,83`, `GW/app/main.py:216,295`; `KITS/gateway/lib.sh:4-5,31,86,129-139`, `KITS/gateway/env-gateway.sh:12-32,50-57`, `KITS/gateway/entregar-hmac-vps.sh`, `KITS/gateway/montar_env.py`; `KITS/s4/distribuir-certs.sh`, `KITS/s4/desfazer.sh:27,42`; `EST/docker-compose.yml`; baseline `fase0/baseline/gitleaks-*.log`.
- **Evidência esperada:** inventário fechado; cada segredo com dono, rotação e raio de dano; nenhum em argv, `set -x`, stdout de kit, Kan.
- **Estado inicial:** leitura dos kits e do `config.py` = **A PROVAR**; onde os valores moram de verdade (Coolify S2, backups do Postgres do Coolify, nginx `/etc/nginx/ia-token.conf`, VPS) = **NÃO VERIFICÁVEL** ⇒ sondas: nomes de variável (nunca valor) da aplicação no Coolify; `stat -c '%a %U:%G'` dos arquivos; `ls -la $SEGREDOS_DIR` (só nomes e modos). Token de produção do ChatGuru/Fireworks/VPS = **NÃO EXISTE** ainda (A1.4, A1.5).
- **Perguntas dirigidas:**
  1. A chave HMAC de `ia-mensagem` vive em 3 lugares (S2 env do gateway, S3 `$SEGREDOS_DIR`, VPS): quem apaga a cópia da S3 (`env-gateway.sh:27`) e quando? Há passo no kit ou só comentário?
  2. Token `ti`: o que ele pode (C08 §1: `PUT /config` de tudo, `chats_teste`)? É único e compartilhado? Um vazamento liga `ia_ativa` e muda `modo` para `real`?
  3. `api_tokens: dict[str, SecretStr]` (`config.py:88`): a comparação é em tempo constante (`auth.py`)? 401 e 403 são indistinguíveis para token errado × origem errada?
  4. `env-gateway.sh` grava pelo `artisan tinker` do Coolify: o valor passa por argv/histórico/log do tinker? `lib.sh` tem algum `set -x` condicional?
  5. `GATEWAY_*` no Coolify ficam no Postgres do Coolify da S2 e nos backups dele: qual a retenção desses backups? (Mesmo argumento que tirou a chave AES do Coolify, P-R10.)
  6. Senha do banco: `database_url` no ambiente do contêiner × arquivo 0600 (`KITS/s4` gera `.senha`): qual dos dois o compose da esteira usa?
  7. Tópico do ntfy.sh é segredo por obscuridade (terceiro, sem autenticação?): quem o conhece e o que um leitor do tópico vê (RS-03)?

## RS-08 — Escrita em produção só por kit com ensaio, contagem e desfazer (PD-2)

- **Fonte:** ROT §0.3 regra 6 «só com **«sim» do dono**, ensaio + contagem na mão, **pelos kits**…, com vigia e caminho de volta» (l. 46); ROT PD-2 itens (1)–(7) (l. 427); ROT §0.5b «**Nada aqui autoriza execução**» (l. 100); PLANO §3b RS-08 «manifesto sha256 conferido antes de cada «sim»».
- **Como se prova:** leitura passo a passo de cada kit + ensaio em cópia descartável (PLANO §8: só com `GW_REPO`, `IA_REPO`, `IA_MIGRACOES`, `GW_PY` apontando para a exportação; «PULADO» = não provado; não rodar `gateway/ensaio-local.sh:310` que puxa imagem do Coolify).
- **Onde olhar:** `KITS/gateway/` (`rotas-ia.sh`, `env-gateway.sh`, `migrar.sh`, `sql/migra_rotas_ia.sql`, `portao.sh`, `vigia.sh`, `aguardar-reinicio.sh`, `ativar-sumidouro.sh:5-20`, `e12-sumidouro.sh`, `entregar-hmac-vps.sh`, `desfazer.sh`, `ensaio-local.sh`, `ensaio_stub.py`, `README.md`); `KITS/s4/` (`s4-papeis.sh`, `s4-hba.sh:9-13,44-135`, `distribuir-certs.sh`, `provar.sh:4,26-36`, `desfazer.sh:2-8,27-103`, `ensaio-local.sh`, `README.md`); `KITS/config/chats-teste.sh` e `IA/kits/chats-teste.sh` (duas cópias: iguais?); `KITS/merge-0411/merge-0411.sh`, `KITS/merge-d06/merge-d06.sh`; `IA/scripts/aplicar_migracoes_local.sh`; `EST/scripts/deploy-vps.sh`, `EST/scripts/release.sh`; sha256 em `fase0/MANIFESTO.md` «## Kits (sha256)».
- **Evidência esperada:** tabela por passo: modo `--ensaio`/dry-run existe · contagem esperada impressa · exige confirmação · idempotente · interrompível · `desfazer` cobre · o que deixa em disco.
- **Estado inicial:** **A PROVAR** (leitura) + **PROVADO EM ENSAIO só onde o ensaio rodar na Fase 2**. Kits previstos e inexistentes = **NÃO EXISTE** (PLANO §0.7: `s4/migrar.sh`, `config/domingo.sh`, `gateway/ativar.sh`, chave AES de dezembro) ⇒ aceite de **A4.6, B1.8/B6.7, B6.0/B6.1, A4.9**. Conferência do sha256 antes do «sim» = **NÃO EXISTE** como passo (medido: 7 arquivos de `KITS/` citam `sha256sum|MANIFESTO`; falta ver se algum **confere** o próprio kit) ⇒ pergunta 1. Se o kit rodado em produção é o do manifesto = **NÃO VERIFICÁVEL** (os kits vivos não estão em git, PLANO §0.6) ⇒ sonda: `sha256sum` do diretório vivo contra o MANIFESTO antes de cada «sim».
- **Perguntas dirigidas:**
  1. Algum kit confere o próprio sha256 (ou o do SQL que aplica) antes de escrever? Em quais dos 7 arquivos e o que exatamente conferem?
  2. Para cada script que escreve: qual é a palavra de confirmação (`--confirmo`, `--gravar`, `read` «sim», `DROP`), e ela é pedida **por passo destrutivo** (PD-2 «sim novo» para segredos, firewall, DROP)?
  3. `desfazer.sh` do gateway e da S4: rodado 2× seguidas é no-op? Interrompido no meio (entre backup e reload do `pg_hba`) deixa o quê?
  4. PD-2 (5) «conferir com conexão nova»: os kits abrem conexão nova para a conferência ou reusam a sessão?
  5. PD-2 (6) vigia/caminho de volta: `vigia.sh` reverte sozinha? Sob que condição? PD-3 «se o serviço mudar por fora… parar o kit, não deixar reverter» está implementado?
  6. Migrações 0001–0005 na S4: o caminho hoje é `psql -1 -f` por stdin (ROT A4.6); existe kit com ensaio/contagem para a 0005 (`DROP CONSTRAINT`, «sim» nomeado)?
  7. `merge-0411.sh`/`merge-d06.sh` fazem merge/push: estão fora do escopo de «escrita em produção» mas `gl-gateway`/`facta-on` fazem deploy no merge — algum deles toca esses repos?

## RS-09 — Janela 08–20 h, domingo por duas chaves, feriado e DATAPREV 20–23/11

- **Fonte:** ROT §0.3 regra 11 «**Nenhuma mensagem ao cliente fora de 08–20, todos os dias; domingo só com as duas chaves abertas, `calendario_bloqueio.domingos=false` e `janela_mensagem.dias."7"`**… (hora de São Paulo calculada **no código**, o cluster é UTC), fora de feriado e da janela DATAPREV (20/11 22:00 → 23/11 06:00)» (l. 51); ROT §0.5b D-18; C08 §11 (migração 0005) e §22.
- **Como se prova:** teste existente com relógio injetado; leitura de quem consulta o calendário antes de enviar; CHECK do banco em PG descartável.
- **Onde olhar:** `IA/src/ia_atendimento/calendario.py:25-33` (`FUSO`, `INICIO_MINIMO=08:00`, `FIM_MAXIMO=20:00`, `DOMINGO`, `HORA_BLOQUEIO_ENTRADA=20:15`, `FERIADOS_MINIMOS={02/11, 20/11}`, `DATAPREV_DE/ATE`), `:44-54` (`JanelaBloqueio`, `Calendario`); `IA/src/ia_atendimento/relogio.py`; `IA/src/ia_atendimento/fila.py:35,187-189,215,366-379` (job único `bloqueio_dataprev` 20/11 21:50; periódica `bloqueio_2015`); `IA/src/ia_atendimento/jobs.py:22-25`; `IA/src/ia_atendimento/chave.py:226` (`bloqueio_entrada`); `IA/src/ia_atendimento/agendamento.py:115-128`; `IA/src/ia_atendimento/agenda_estado.py:186`; `IA/src/ia_atendimento/ferramentas/catalogo.py:40,192` (T13), `ferramentas/esquemas.py:196`, `ferramentas/erros.py:17,36`; `IA/migrations/0001_esquema.up.sql:24-60` (CHECK de `config_versao`), `IA/migrations/0005_domingo_por_config.up.sql:3,29-32`. Testes: `IA/tests/test_calendario.py`, `test_migracao_0005.py`, `test_agenda_janela_mensagem.py`, `test_relogio_injetado.py`, `test_api_config_agenda.py`.
- **Evidência esperada:** função única «pode enviar agora?» usada por **todo** caminho de envio; CHECK recusa janela fora de 08:00–20:00 nos 7 dias; domingo fechado por padrão; DATAPREV bloqueia entrada e envio.
- **Estado inicial:** calendário, CHECK, bloqueio de entrada = **A PROVAR**. **O envio em si não existe na main** (não há `Canal.enviar`; B6.8) ⇒ «nenhuma mensagem fora da janela» no ponto de envio = **NÃO EXISTE** ⇒ aceite de **B1.6b + B6.8** (teste: envio às 07:59/20:00/domingo fechado/feriado/DATAPREV recusado no último salto, provado por mutação). Kit de domingo (`config/domingo.sh`) = **NÃO EXISTE** (B6.7).
- **Perguntas dirigidas:**
  1. O bloqueio da DATAPREV é **só de entrada** (`bloqueio_entrada=true` às 21:50 de 20/11) ou há checagem no envio? De 20/11 20:00 a 22:00 e de 23/11 06:00 a 08:00 quem barra é a janela 08–20; de 22:00 a 06:00 quem barra um `retomar` agendado?
  2. Quem **reabre** depois da DATAPREV (23/11 06:00)? `fila.py:368` só deixa de agendar; quem grava `bloqueio_entrada=false`?
  3. `FERIADOS_MINIMOS` tem só 02/11 e 20/11: e 15/11 (domingo), 25/12? O que mais vem de `calendario_bloqueio` por config?
  4. `FIM_MAXIMO = 20:00` é inclusivo? Uma mensagem às 20:00:00 sai?
  5. As constantes da DATAPREV estão no código com ano fixo (2026): mudança de data pelo dono exige deploy por tag — registrar como restrição operacional.
  6. Fuso: algum `now()` do banco (UTC) decide janela (ex.: `fn_*`, views) em vez do código?
  7. `cron_utc(HORA_BLOQUEIO_ENTRADA, referencia)` (`fila.py:215`): o cron em UTC é calculado no boot — muda se o processo atravessar uma troca de offset? (Brasil sem horário de verão hoje: registrar a premissa.)

## RS-10 — T7 em dúvida nunca se repete

- **Fonte:** ROT §0.3 regra 12 «**T7 em dúvida nunca se repete:** timeout/indeterminado → T8 (janela do `conferir` 20 min; prazo 25 min, 05 §2.3)» (l. 52); ROT §0.5 alínea (m) «indeterminado nunca reenvia → T8» e (t) «Janela do `conferir` da FACTA = **20 min**»; C05 §2.1 (tabela de vereditos), §2.3 «Tempo de espera (T8): **25 minutos**», §2.4 «`por-cpf` antes do T7», §2.5; ROT B1.6 «Spec: `ledger.py`… mesma chave **nunca** executa 2×; timeout ⇒ `indeterminado` e **nunca reenvia**» (l. 906) e «Aceite: … `indeterminado` nunca reenvia (provado por mutação)» (l. 908); PLANO §8 «RS-10… não existem na main ⇒ NÃO EXISTE».
- **Como se prova:** hoje só na segunda base (PR #13) por leitura + teste; na main, critério de aceite.
- **Onde olhar:** `B16/src/ia_atendimento/ledger.py:10-25` (docstring das regras), `:71-76` (`EstadoFinal`, `TERMINAIS`), `:303` (`NAO_CONSOMEM`), `:402-447` (reivindicação, CAS de fechamento, `_dar_como_indeterminada`, sem resposta ⇒ `indeterminado` para `efeito_irreversivel`), `:475` (cancelamento), `:511`, `:520` (`executar_efeito`); `B16/tests/test_ledger.py`; na main: `IA/src/ia_atendimento/ferramentas/catalogo.py:174-184` (T7/T8/T9: `idempotencia="chave_por_tentativa"`, `timeout_s=125.0`), `ferramentas/erros.py:22` (`INDETERMINADO`), `ferramentas/modo.py:455-465` (FACTA em modo ≠ real); `IA/migrations/0001_esquema.up.sql:191` (`ferramenta_chamada`); facta-on: `FO/app/routers/online.py:4672` (`por-cpf`), `:4752-4761` (comentário do `nao_criada`), `:4857-4901` (`conferir`, fail-closed em `:4893`), `FO/app/config.py:123`, `FO/docker-compose.yml:151`; `FO/tests/test_proposta_conferir.py`, `test_proposta_por_cpf.py`; dublê: `DUB/camada-b`, `DUB/catalogo`.
- **Evidência esperada:** índice único de idempotência no banco; segunda execução da mesma chave não chama o banco; timeout/cancelamento/queda entre efeito e ack ⇒ `indeterminado`, nunca `transitorio`; redigitação só depois de `nao_criada` do `conferir` com janela de 20 min.
- **Estado inicial:** main = **NÃO EXISTE** ⇒ aceite de **B1.6a (merge do PR #13) + B1.6b + B5.4**; `b1-6a` = **A PROVAR** como segunda base (vale para `9a714e3`, reconferir após o merge). Janela 20 min no facta-on = **NÃO EXISTE** (F0-4) ⇒ aceite de **B3.2** (deploy #5). Valor vivo de `FACTAON_CONFERIR_JANELA_MIN` = **NÃO VERIFICÁVEL** ⇒ sonda (C05 §3): `docker exec <facta-on> printenv FACTAON_CONFERIR_JANELA_MIN`.
- **Perguntas dirigidas:**
  1. Na `b1-6a`, o que distingue `transitorio` (reexecuta) de `indeterminado`? `ledger.py:10` diz que o efeito «NÃO é reivindicado em modo simulado… fica `transitorio`»: há algum caminho real em que T7 feche `transitorio` depois de a requisição ter saído?
  2. Worker morto no meio da chamada (`ledger.py:20` «a execução que a reivindicou morreu depois de talvez ter chamado»): vira `indeterminado` sempre, para toda classe de efeito ou só `efeito_irreversivel` (`:447`)? T7 está classificado como irreversível?
  3. «Chave nova, ≤ 3» da alínea (m) (corrigível): quem gera a chave da nova tentativa e o que impede que um `indeterminado` receba chave nova e redigite (C05 §2.5)?
  4. Prazo de 25 min (T8) × janela de 20 min: o orquestrador mede a partir de quê (`desde`, C05 §2.2)? Com a janela ainda em 10 min em produção, o que o orquestrador conclui de um `nao_criada` aos 11 min?
  5. `timeout_s=125.0` do T7 (`catalogo.py:174`) × o timeout do `facta-on` para a FACTA: quem desiste primeiro?
  6. Mutação pedida no aceite: existe teste que reprova se `_dar_como_indeterminada` virar `transitorio`?
  7. Retentativa do pydantic-ai ou do Procrastinate (`retry=`) em torno de T7: algum laço externo reexecuta a ferramenta com **a mesma** chave (ok) ou com chave **nova** (viola)?

## RS-11 — D-15: sem batimento recente a IA não age (fail-closed)

- **Fonte:** ROT §0.5b D-15 «**Sem batimento recente a IA não age (fail-closed):** `batimento` ausente ou > 90 s ⇒ `Canal.enviar/nota` e o reaper do boot recusam o efeito e alertam; a vigia continua devolvendo» (l. 111); C08 §6 item 5 (texto riscado «fail-open com alerta» substituído), §7.1, §7.4 «Consumo do `batimento` v2 (F14)», §16 item 4 «Ausente ou velho ⇒ a IA não age (D-15)»; C04 §7 «Vigia da S2 e `batimento`»; ROT Parte D linha 88 «Zumbi sem cerco» (l. 1417); PLANO §8 «RS-11… não existem na main (B1.6b, B6.6, B6.7) ⇒ NÃO EXISTE».
- **Como se prova:** critério de aceite; leitura cruzada C04 §7 × C08 §7.4 (Fase 2b).
- **Onde olhar:** nada do batimento do espelho em código de produto confirmado. **Não confundir** com o batimento do worker do Procrastinate: `IA/src/ia_atendimento/worker_vivo.py`, `IA/src/ia_atendimento/fila.py:383-417`, `B16/src/ia_atendimento/worker_vivo.py:1-118` (isso é liveness de worker, não D-15). `rs-05-contagens.sh` achou 2 arquivos em `IA/src` e 2 em `B16/src` casando `impedidos|"vivos"|batimento_`: identificar quais e descartar/confirmar. Segunda base: `B16/src/ia_atendimento/espelho.py`, `B16/src/ia_atendimento/espera.py`.
- **Evidência esperada (quando existir):** `Canal.enviar`/`Canal.nota` e o reaper do boot leem o batimento **antes** do efeito; ausente, > 90 s, versão errada ou `seq` que retrocede ⇒ recusa + alerta crítico; teste por mutação (fail-open reprova).
- **Estado inicial:** **NÃO EXISTE** ⇒ critério de aceite de **B1.6b** (consumo), **B6.4** (produtor: vigia da S2), **B6.8** (`Canal`), **B6.6** (alerta).
- **Perguntas dirigidas:**
  1. Quais são os 2 arquivos que casaram em cada base e o que fazem?
  2. C08 §6 exceção 1 («T12, `ia-repasse`, a nota do repasse e `Canal.restaurar` executam REAIS… parada dura»): com D-15, o repasse/devolução também é barrado sem batimento? O texto vigente de §6 item 5 e §7.1 resolvem a contradição «a IA não age» × «é o que devolve o lead ao humano»? Copiar a frase exata.
  3. Relógio do «> 90 s»: comparado com o relógio da VPS ou da S2? Tolerância a desvio?
  4. Por onde o batimento chega à VPS (rota, credencial, HMAC)? Um batimento forjado/repetido passa (replay)?
  5. C04 §7 e C08 §7.4 descrevem o mesmo formato (`impedidos`, `vivos`, `seq`, retenção «até `encerrou` ou 8 d»)? Tabela campo a campo para a Fase 2b.

## RS-12 — Papéis e `pg_hba` (alínea v)

- **Fonte:** ROT §0.5 alínea (v) «`ia_owner` separado; `ia_app` sem DDL/DELETE; Phoenix é a exceção» (l. 83); ROT A4 «Ajustes sobre E… dono do banco = **`ia_owner`** (NOLOGIN)…; grupos `ia_app`, `ia_leitura`, **`ia_qualidade`** NOLOGIN e logins `_a` (`ia_app_b` NOLOGIN até a rotação)» (l. 690) e A4.3 «`s4-papeis.sh`… `ia_qualidade` (**só grupo NOLOGIN**: sem login, sem certificado e sem `pg_hba`…)» (l. 702); C03 §4 «Conexão ao `ia_atendimento` (S4)»; PLANO §3b RS-12.
- **Como se prova:** matriz papel × tabela × privilégio por `has_table_privilege` em PG descartável (migrações 0001–0005 aplicadas); ensaio do kit s4; estado vivo = sonda.
- **Onde olhar:** `IA/migrations/0001_esquema.up.sql:1-13` (`SET ROLE ia_owner`, `REVOKE … FROM PUBLIC`, default privileges — **`:11` dá `SELECT, INSERT, UPDATE, DELETE` em `procrastinate` a `ia_app`**), `:435-446` (grants nominais: `ia_app` sem DELETE em `ia`; `ia_leitura` sem texto cifrado nem cofre; `ia_qualidade`), `:451-452` (asserção de ACL no próprio DDL), `:404-442` (funções `SECURITY DEFINER` de poda); `IA/migrations/0002_procrastinate.up.sql:200,282,309,544,566` (DELETEs da fila); `0003:11`, `0004:16-17,38-39`; `IA/migrations/README.md`; `KITS/s4/s4-papeis.sh:8-12,69-115` (papéis, `ia_app_b NOLOGIN`, `GRANT CONNECT … TO ia_app, ia_leitura, ia_qualidade, bkp_pg` em `:99`), `KITS/s4/s4-hba.sh:9-13,44-46` (3 linhas `hostssl … scram-sha-256 clientcert=verify-full`; «`ia_qualidade` e `ia_app_b` NÃO ganham linha nenhuma»), `:50,111,132-135` (linha `local … bkp_pg peer` ganha `ia_atendimento`), `KITS/s4/provar.sh:7-11,28-36,67-95`, `KITS/s4/desfazer.sh:27-28,79-88`; `KS4/kits/` (mesmo kit versionado: comparar sha256 com `KITS/s4`); `IA/src/ia_atendimento/config.py:184` (`_banco_como_ia_app`). Testes: `IA/tests/test_esquema.py`, `test_migracoes.py`, `test_migracao_0003.py`, `test_migracao_0004.py`.
- **Evidência esperada:** `ia_app` sem `CREATE`/`DELETE`/`TRUNCATE` no schema `ia`; `DELETE` só em `procrastinate` (exceção escrita); `ia_leitura`/`ia_qualidade` sem `SELECT` em `conversa_cifrada` e `cofre`; funções de poda com `search_path` fixo e sem SQL dinâmico; `pg_hba` com 3 linhas `/32` antes do `reject`.
- **Estado inicial:** DDL e kit = **A PROVAR** (ensaio do `s4/ensaio-local.sh` na Fase 2). Estado vivo da S4 (A4.3a pendente do «sim», ROT l. 699) = **NÃO VERIFICÁVEL** ⇒ sondas: `select rolname, rolcanlogin, rolconnlimit from pg_roles where rolname like 'ia\_%'`; `select type, database, user_name, address, auth_method, options, error from pg_hba_file_rules where user_name && array['ia_app_a','ia_obs_a','ia_leitura_a','bkp_pg']`; `select has_table_privilege('ia_app','ia.conversa_cifrada','DELETE')`.
- **Perguntas dirigidas:**
  1. Alínea (v) diz «`ia_app` sem DDL/DELETE»; `0001:11` concede `DELETE` em todas as tabelas futuras de `procrastinate`. Há decisão escrita aceitando essa exceção (onde: `IA/migrations/README.md`? `docs/DECISOES-*`?) ou é contradição a levar ao dono? `procrastinate_jobs.args` com `DELETE` por `ia_app` permite apagar rastro.
  2. `ia_app` tem `UPDATE` em `ia.cofre`, `ferramenta_chamada`, `confirmacao`, `agendamento` (`0001:438`): pode reescrever o ledger (`ferramenta_chamada`) — isso enfraquece RS-10?
  3. As funções `SECURITY DEFINER` (`fn_texto_podar`, `fn_atendimento_podar`, `fn_anexar_rpa`) rodam como `ia_owner`: `REVOKE … FROM PUBLIC` cobre todas (`0001:9` é default; `0004:16` explícito)?
  4. `bkp_pg` ganha `CONNECT` e a linha local do `pg_hba`: com isso o dump lógico leva `conversa_cifrada` e `cofre` (cifrados) e `passo` — qual a retenção desse dump (RS-06)? E `ia_obs` fica fora «por desenho» (`provar.sh:9`): onde está o backup do `ia_obs` (A4.8)?
  5. `ia_qualidade` tem `CONNECT` no banco mas não tem login nem linha no hba: confirmado que nenhum login é membro dele?
  6. `ia_leitura_a` vem da S2 (`10.90.0.2`): quem na S2 usa (cliente360-api, C03 §4)? `default_transaction_read_only=on` é configuração do papel — um `SET` na sessão o desliga; os grants impedem a escrita de qualquer forma?
  7. `desfazer.sh:28` faz `DROP` de todos os papéis: exige confirmação própria (`confirmar_drop`)? Depois de haver dados?

## RS-13 — Segredos e PII em repositório

- **Fonte:** ROT PD-6 «varredura de CPF com DV, telefone, e-mail, CEP, UUID/JWT antes de commit» (l. 435); ROT §0.3 regra 13 «**Dado de teste nasce da forma medida**, nunca inventado; de produção sai só forma»; ROT P-R9 (l. 259, CI parado por cobrança, portão local); PLANO §3b RS-13 («gitleaks no CI só do bancos-duble; `.gitleaksignore` do ia-atendimento admite CPF de DV válido no histórico sem prova de ser sintético»).
- **Como se prova:** baseline gitleaks (dir + histórico) já rodado; leitura de configs e do CI; leitura do `.gitleaksignore` (4 linhas) contra o que ele isenta.
- **Onde olhar:** `IA/.gitleaks.toml` (regra de CPF formatado em `:12-13`; allowlists `:17-36`), `IA/.gitleaksignore` (4 linhas), `IA/scripts/gitleaks.sh`, `IA/scripts/varredura.py`, `IA/scripts/check.sh:14-15` (varredura + gitleaks estrito no portão local), `IA/.github/workflows/ci.yml:34-41` (ruff, varredura, pytest — **sem gitleaks**), `IA/tests/test_gitleaks.py`, `test_varredura.py`; `DUB/.github/workflows/ci.yml:44-51` (gitleaks com versão e sha256 fixos), `DUB/piiscan`, `DUB/piiscan.toml`; `GW/.github/workflows/testes.yml` (sem gitleaks nos hits); `FO/` (sem `.github` nos hits do grep — confirmar); baseline `fase0/baseline/gitleaks-*.log` (8 arquivos de 2.680 bytes cada — tamanho idêntico: conferir se rodou de fato ou se é a mesma mensagem de erro) e `fase0/baseline/semgrep-ia-atendimento.log` (108 bytes: quase vazio).
- **Evidência esperada:** gitleaks limpo em diretório e histórico nos 6 repos; cada entrada do `.gitleaksignore` justificada como sintética (faixa `000.000.[01]nn-dd` ou CPF de exemplo público); portão que **falha** sem o binário.
- **Estado inicial:** **A PROVAR**. Atenção: a linha de base parece não ter rodado (logs de tamanho idêntico; semgrep com 108 bytes) ⇒ primeira tarefa do leitor é abrir os logs e dizer «rodou / não rodou». Proteção no servidor (push protection, secret scanning do GitHub) = **NÃO VERIFICÁVEL** ⇒ sonda: `gh api repos/GL-BUSINESS/<repo> --jq .security_and_analysis`.
- **Perguntas dirigidas:**
  1. Os 8 logs de gitleaks têm exatamente 2.680 bytes: o conteúdo é resultado ou erro? Se erro, RS-13 não tem linha de base.
  2. As 4 entradas do `.gitleaksignore`: que regra, que arquivo, que commit? O valor isento é da faixa sintética? (Citar por forma, nunca o valor.)
  3. A allowlist `:23` (`regexes`) do `.gitleaks.toml` lista «CPFs de exemplo públicos da varredura»: quantos, e algum tem DV válido fora da faixa `000.000.xxx`? C05 §6 usa um CPF de exemplo com DV válido «da lista sintética da varredura»: é o mesmo conjunto?
  4. `varredura.py` declara que **não** pega prosa, nome, CEP, binário (`EST/scripts/varredura.py:8`): o que cobre o resto?
  5. CI do `ia-atendimento` e do `gl-gateway` sem gitleaks; `facta-on` sem workflow visível: registrar como «ausência de controle» com o comando reprodutível.
  6. `tests/contratos/cliente360-recorte.json` (53 KB) e `tests/corpus/agenda_frases.jsonl` (96 KB) estão no repo: o primeiro é recorte de contrato (forma) ou tem exemplo com dado? (Ler só por `piiscan`/varredura.)

## RS-14 — «Teste × real»: o canal de teste não alcança o real

- **Fonte:** C08 §5.2 «Autorização por origem e regra do canal de teste (F04)» — «origem `gateway_chatguru` com `canal_origem = chatguru-ia-teste`: o `chat_id` tem de estar em `chats_teste` **e** o atendimento ativo desse chat (se houver) ter `modo='teste'`; senão `403 origem_teste_fora_da_lista`, **nada g[ravado]**»; C08 §6 «Global (`config.modo`): `real|sombra|duble` (seed `duble`); `PUT modo=teste` ⇒ 422» e «`atendimento.modo` nasce na entrada: `chat_id ∈ chats_teste` ⇒ `teste`»; C08 §2 (422 `modo_teste_global`, `chat_de_cliente`); C01 §4.3 (`ia-sumidouro`); PLANO §3b RS-14 e §8 «a trava `_regra_do_canal_de_teste` existe (`api/eventos.py:103,132`); sem trava é a rota `ia-sumidouro`».
- **Como se prova:** leitura + testes existentes; matriz credencial × rota × chat × modo.
- **Onde olhar:** `IA/src/ia_atendimento/api/auth.py:27-36` (`CREDENCIAIS_DO_GATEWAY`, `CREDENCIAL_DE_TESTE`, `Identidade.canal_origem`); `IA/src/ia_atendimento/api/eventos.py:103-109` (`_regra_do_canal_de_teste`), `:132` (chamada antes de gravar); `IA/src/ia_atendimento/api/config_rotas.py` (`PUT /config`: `chats_teste` só `ti`; `modo=teste` 422); `IA/src/ia_atendimento/config.py:116-118` (`pessoas_teste_arquivo`: sem arquivo, nenhuma pessoa é de teste); `IA/src/ia_atendimento/pessoas_teste/{catalogo,fonte,prefixo,arquivo}.py`; `IA/src/ia_atendimento/estado_entrada.py`; `IA/kits/chats-teste.sh` e `KITS/config/chats-teste.sh`; gateway: `KITS/gateway/rotas-ia.sh:7,10,24,27` (`ia-mensagem` aceita `chatguru-ia,chatguru-ia-teste`; `ia-sumidouro` só `chatguru-ia-teste`), `GW/app/assinatura.py` (o que é assinado: a credencial vai no HMAC?), `GW/app/main.py:275-306`. Testes: `IA/tests/test_api_eventos.py`, `test_pessoas_teste_api.py`, `test_kit_chats_teste.py`, `test_contrato_api.py`; `GW/tests/test_ia_assinatura.py`, `test_ia_rotas.py`.
- **Evidência esperada:** `canal_origem` vem **assinado** pelo gateway (não de cabeçalho livre); credencial de teste + chat fora de `chats_teste` ⇒ 403 sem gravar; credencial real + chat de teste ⇒ comportamento definido; `chats_teste` só muda por `ti`.
- **Estado inicial:** **A PROVAR**. `ia-sumidouro` sem trava técnica de chat (só a credencial) = **«ausência de controle» a confirmar** (PLANO §8) — um chat de cliente configurado no ChatGuru com o token de teste cai no sumidouro com corpo guardado (F0-8). Quem tem o token de teste no ChatGuru e em que diálogo ele está = **NÃO VERIFICÁVEL** ⇒ sonda: listar no ChatGuru os diálogos que apontam para `…/ia-sumidouro` e `…/ia-mensagem` com a credencial de teste.
- **Perguntas dirigidas:**
  1. `eventos.py:109`: a condição é `chat_id not in chats_teste OR (modo_ativo is not None and modo_ativo != "teste")`. E o caminho inverso: credencial **real** (`chatguru-ia`) com `chat_id ∈ chats_teste` — passa? Com que modo nasce?
  2. `canal_origem` entra no cálculo do HMAC (`GW/app/assinatura.py:83`) e o orquestrador o lê do cabeçalho assinado? Um `x-gl-*` forjado por quem alcança a VPS pela WG troca `chatguru-ia-teste` por `chatguru-ia`?
  3. `/eventos/mensagem` (RPA) e `/agendamentos` têm a mesma regra de teste ou só `/eventos/chatguru`?
  4. Remover um chat de `chats_teste` com atendimento `teste` aberto: o que acontece (C08 §2 `chat_de_cliente`, v2.3)?
  5. Atendimento `teste` usa pessoa de `pessoas_teste`: o que impede `modo=teste` com `pessoa_id` real (`config.py:116-118`; C08 §2 «`duble` de `pessoa_id ∉ pessoas_teste`»)?
  6. As duas cópias de `chats-teste.sh` (`IA/kits/` e `KITS/config/`) são idênticas (sha256)? Qual é a que roda?

## RS-15 — Flags e sementes `FACTAON_*`

- **Fonte:** PLANO §8 «Novas: RS-15 flags e sementes `FACTAON_*`» (o plano não define o alcance; duas leituras plausíveis, as duas abaixo). (a) Flags: ROT PD-3 «flag nova **off**… cada «flag off» de env (facta-on, `C360_*`, gateway) é um **reinício** e conta como deploy» (l. 429); C05 §4 «Mudança B3.1: tap sem PII (PR de A6.4; flag `FACTAON_TAP_IA`, nasce **off**)»; C05 §3 (`FACTAON_CONFERIR_JANELA_MIN`). (b) Ambiente do dublê/dev: ROT Parte D linha 100 «**Token único da FACTA:** `gera-token` invalida o anterior… credencial fictícia; `FACTAON_BASE_URL` obrigatoriamente o WireMock (teste que falha); nunca copiar `.env` de produção» (l. 1429); ROT B2.1 I23 «`FACTAON_BASE_URL=http://bancos-duble:8080/facta`, `FACTAON_PROXY_URL=` vazio» (l. 924). (c) «Semente»: C05 §1 «Semente do `/proposta/formalizar` | nasce com `status_proposta = "AGUARDANDO ASSINATURA DIGITAL"` (**placeholder**…)» e §2.1 linha 2 (`placeholder`).
- **Como se prova:** leitura de `config.py`/compose do facta-on; teste do dublê; estado vivo = sonda.
- **Onde olhar:** `FO/app/config.py:123` (`conferir_janela_min`), demais campos com prefixo `FACTAON_` (ler o `env_prefix`); `FO/docker-compose.yml:104-151` (`FACTAON_BASE_URL` com default de produção em `:108`, `FACTAON_PROXY_URL` `:133`, `FACTAON_CONFERIR_JANELA_MIN` `:151`); `FO/app/token.py:37,168-172` (`FACTAON_TOKEN_GERAR`); `FO/app/routers/online.py:4672,4857` e a semente do `formalizar` (C05 cita `online.py:5167`: localizar por âncora `AGUARDANDO ASSINATURA DIGITAL`); `FO/init_factaon.sql`; `FO/tests/test_proposta_conferir.py`; dublê: `DUB/camada-b`, `DUB/docker-compose.yml`, `DUB/tests`; orquestrador: `IA/src/ia_atendimento/ferramentas/modo.py:41` (`VARIAVEIS_DE_AMBIENTE`: base de produção × teste da FACTA).
- **Evidência esperada:** toda flag nova da fronteira IA nasce off e é lida num ponto só; `facta-on` de dev/dublê **não sobe** com `FACTAON_BASE_URL` de produção nem com `FACTAON_TOKEN_GERAR=true` e credencial real; o `placeholder` da semente nunca é lido como estado final.
- **Estado inicial:** flags existentes e compose = **A PROVAR**; tap (`FACTAON_TAP_*`) = **NÃO EXISTE** na main (F0-1) ⇒ aceite de **B3.1** (PR #49, hoje CONFLICTING); «teste que falha» se `FACTAON_BASE_URL` não for o WireMock = **A PROVAR no `bancos-duble`** (existe?) senão **NÃO EXISTE** ⇒ aceite de **B2.1/B2.2**; valores vivos das flags em produção = **NÃO VERIFICÁVEL** ⇒ sonda: `docker exec <facta-on> printenv | grep -c '^FACTAON_'` e nomes (sem valores) + `printenv FACTAON_CONFERIR_JANELA_MIN`.
- **Perguntas dirigidas:**
  1. Qual é o nome certo da flag do tap: `FACTAON_TAP_IA` (C05 §4) ou `FACTAON_TAP_RETORNOS` (ROT Painel A6.4)? O PR #49 usa qual? (F0-2.)
  2. `FO/docker-compose.yml:108`: o default de `FACTAON_BASE_URL` é a FACTA de produção. Um `facta-on` de dev sem a variável fala com produção e, com `FACTAON_TOKEN_GERAR=true`, invalida o token da casa (Parte D 100). Que guarda existe (teste, validação de boot)?
  3. O que o dono quis dizer com «sementes» em RS-15? Fixar: (c) semente/placeholder do `formalizar`, sementes de fixture do dublê (`DUB/catalogo`), ou seeds de config? Se ficar ambíguo, vai à lista do dono.
  4. O orquestrador trata `placeholder` (C05 §2.1 linha 2) como «aguardando», nunca como «criada com assinatura pendente»? Onde (só papel; B5.4)?
  5. Inventário: quantas `FACTAON_*` existem, quais mudam comportamento que a IA consome (`conferir`, `por-cpf`, `status_proposta`), e qual é o default de cada uma?

## RS-16 — PD-6: `hide_input_in_errors` e scrubber de exceções

- **Fonte:** ROT PD-6 «(v3) **PII fora da trilha cifrada:** todo modelo Pydantic que toca texto de cliente usa `hide_input_in_errors=True` e o scrubber cobre exceções e tracebacks» (l. 435); PLANO §8 «RS-16 PD-6 `hide_input_in_errors` (`ferramentas/saida.py`, `especificacao.py`, `corpus/modelos.py`, `pessoas_teste/formas.py`)».
- **Como se prova:** grep estruturado (todo `BaseModel`/`ConfigDict`/`TypeAdapter`/`RootModel`/`dataclass` pydantic × presença da opção) + leitura de quem captura `ValidationError`.
- **Onde olhar:** com a opção (confirmado): `IA/src/ia_atendimento/scrubber.py:56-61` (`ModeloSemEco`), `linha_tempo.py:69`, `agendamento.py:59`, `turno.py:167,177,186`, `modelos_conversa.py:19`, `ferramentas/esquemas.py:24-27` (`Fechado`), `api/anotacoes.py:37,45,69`, `api/eventos.py:41,56`, `api/config_rotas.py:42`, `config.py:78`. **Sem a opção (confirmado):** `IA/src/ia_atendimento/corpus/modelos.py:32-33` (`_Modelo`), `IA/src/ia_atendimento/pessoas_teste/formas.py:30-31` (`_Fechada`). Sem modelo próprio, mas manipulam `BaseModel` e `ValidationError`: `ferramentas/saida.py:21,37,69-94`, `ferramentas/especificacao.py:24,78-182`. Scrubber: `scrubber.py:27-95` (`EntradaInvalida`, `erros_sem_input`, `validar`, `formatar_sem_pii`, `instalar_excepthook`, hook de thread), nota em `scrubber.py:57` e `config.py:268` (`.errors()`/`.json()` guardam o input mesmo com a opção). Testes: `IA/tests/test_observabilidade.py`, `test_vazamento_corpo.py`, `test_api_revisao1.py`, `test_ferramentas_gateway_revisao.py`.
- **Evidência esperada:** nenhum modelo que receba texto de cliente, saída de ferramenta (dados do 360/FACTA) ou corpo de evento sem a opção; nenhum `str(e)`/`repr(e)`/`.errors()`/`.json()` de `ValidationError` chegando a log, `passo`, span ou resposta HTTP; excepthook instalado na API **e** no worker.
- **Estado inicial:** **A PROVAR**, com candidato a achado já localizado (F0-6).
- **Perguntas dirigidas:**
  1. `corpus/modelos.py` e `pessoas_teste/formas.py` «tocam texto de cliente»? `pessoas_teste/formas.py` modela a **resposta do 360/FACTA** (formas de `Contrato`, `:137`): em produção, a mesma forma valida dado real (nome, endereço)? Se sim, a ausência da opção é achado; se só fixtures sintéticas, é BAIXO.
  2. `ferramentas/saida.py:69` (`reconstruir`): quando o `model_validate` do dado bruto de uma ferramenta falha, o que vira o erro? Leva `input` (dados reais do 360/FACTA) para `FerramentaFalhou`, `passo.erro`, log?
  3. Os modelos de saída das ferramentas (`e.SaidaT1`…`SaidaT9` em `ferramentas/esquemas.py`) herdam todos de `Fechado`? `especificacao.py:92` (`_conferir_fechado`) exige `hide_input_in_errors` ou só `extra="forbid"`?
  4. FastAPI: o handler de `RequestValidationError` devolve `input` no corpo 422 (padrão do FastAPI)? Onde é substituído (`IA/src/ia_atendimento/api/erros.py`, `api/validacao.py`)?
  5. `instalar_excepthook` é chamado em `api/app.py` e em `worker.py`? E tarefas asyncio (`loop.set_exception_handler`) e o log de erro do Procrastinate (que imprime `args` do job)?
  6. Exceções de terceiros que ecoam entrada: `psycopg` (parâmetros na mensagem de erro), `httpx` (URL), `json.JSONDecodeError` (trecho do documento), `openai` (corpo da requisição): o scrubber cobre por tipo ou por padrão de texto?

## RS-17 — Regra de log F07: nenhum corpo de evento em log, span, traceback ou resposta

- **Fonte:** C01 §7 «**Regra de log (F07, valendo para o gateway, o orquestrador e o n8n):** **nenhum corpo A10 é registrado em log, span ou traceback**, nem mascarado «por garantia»» (l. 280); C08 §0 «F07 | nenhum corpo de evento em log; só identificadores opacos, códigos e contagens | §1» e §1 «**Log (F07):** nenhum corpo de evento (`texto_mensagem`, `url_arquivo`, `link_chat`, `chat_number`; … e a `matricula`, D-29), nem mascarado, entra em log, span, traceback ou resposta. Só: `trace_id`, rota, código, `duracao_ms`…» (l. 47); C05 §2.6 (F29, quatro camadas); ROT B3.2 «(RG-015) … redação em `app/logs.py` (`log`/`log_err`, as 38 ocorrências de `cpf={cpf`) + `test_log_app_nao_traz_cpf`» (l. 951).
- **Como se prova:** grep estruturado de chamadas de log/`print`/atributos de span + captura de logs nos testes; para n8n e nginx, só papel/sonda.
- **Onde olhar:** gateway: `GW/app/logs.py:23-36` (`_UrlSemQuery` no logger `httpx`), `GW/app/main.py` (todo `log(`/`log_err(`; `:216` «só o TIPO vai ao log»; `:381,484`), `GW/app/metricas.py:56-116` (o que vai a `gateway.payloads` e a métricas), `GW/tests/test_ia_forward.py`; orquestrador: `IA/src/ia_atendimento/api/logs.py:22-32` (`uvicorn.access` desligado em `:32`), `IA/src/ia_atendimento/observabilidade.py:15,190` (`FiltroSemPii`), `:259-273`, `IA/src/ia_atendimento/api/app.py:223` (`x-trace-id`), `api/erros.py`, `api/validacao.py`, `evento_mensagem.py`; facta-on: `FO/app/logs.py:7,21`, `FO/Dockerfile` (`CMD` sem `--no-access-log`, C05 §2.6 item 4), `FO/tests/test_log_sem_pii.py`; n8n: `KITS/gateway/ia-sumidouro.workflow.json:39-40`; nginx: só C02 §2 e C05 §2.6 item 3.
- **Evidência esperada:** lista fechada do que cada serviço loga por requisição; teste com corpo-canário que falha se qualquer campo A10 aparecer em log/span/resposta; `uvicorn.access` desligado ou filtrado nos três serviços.
- **Estado inicial:** gateway e orquestrador = **A PROVAR**. facta-on: filtro do `uvicorn.access` e redação de `cpf={cpf` = **NÃO EXISTE** na main (F0-1; RG-015) ⇒ aceite de **B3.1/B3.2** (PR #49 + deploy #5). n8n do braço = **NÃO EXISTE** (B6.2). nginx do vhost WG (`log_format ia_semquery`, `error_log crit`) = **NÃO VERIFICÁVEL** ⇒ sonda: `nginx -T | grep -A3 ia_semquery` na S2 (A4.4 ainda não feita ⇒ hoje NÃO EXISTE).
- **Perguntas dirigidas:**
  1. `FO/tests/test_log_sem_pii.py` existe na main: o que ele cobre hoje (qual logger) e o que fica de fora (as «38 ocorrências de `cpf={cpf`» de RG-015 ainda estão em `FO/app/logs.py`/`online.py`? contar por forma).
  2. Gateway: no erro de forward (timeout, 5xx do destino) a resposta do destino ou o corpo entram no log? E em `gateway.payloads.resposta` com `guardar_corpo=false` (`migra_rotas_ia.sql:8` «nem o corpo nem a resposta»)?
  3. Orquestrador: `FiltroSemPii` é filtro por padrão de texto (mascara) ou por allowlist de campos? F07 diz «nem mascarado»: um log que contenha texto mascarado viola a regra — existe algum?
  4. O span do `httpx`/OpenInference leva `url.full`, `http.url`, `input.value`, `output.value`? O `ExportadorMascarado` mascara ou remove? (Texto mascarado no Phoenix é permitido pela regra 3; corpo de **evento** A10 não, por F07: a fronteira entre os dois está clara no código?)
  5. A resposta HTTP de erro ecoa algum campo do corpo (`chat_id` pode; `texto_mensagem` não)?
  6. `matricula` (D-29) entrou na lista de F07: em que modelo ela chega (`POST /atendimentos`) e ela vai para o cofre sem passar por log/`passo`?

## RS-18 — Orquestrador só sobe por tag `v*`

- **Fonte:** ROT §0.3 regra 5 «**Orquestrador na VPS: só por tag `v*`** (A6.6)» (l. 45); ROT PD-3 (l. 429); ROT §0.3 regra 14 «**Versionar sempre:** tag semver + release no GitHub; `/healthz` com `version`, `git_sha`, `built_at`»; ROT §0.6 P-R8 (l. 258); ROT Painel A6.6 «**concluída em parte (v3.3, RG-067)**… → **A6.6b**» (l. 347).
- **Como se prova:** leitura da esteira (só local, sem cópia no GitHub — PLANO §0.6); estado do Coolify = sonda.
- **Onde olhar:** `EST/.github/workflows/imagem.yml:1-3,22` (`tags: ["v*"]`), `:113-130`; `EST/.github/workflows/ci.yml:7`; `EST/scripts/release.sh:3-40` (semver, CHANGELOG, só da `main`, tag inexistente); `EST/scripts/deploy-vps.sh`; `EST/docker-compose.yml:21,65` (`IMAGE_TAG`); `EST/Dockerfile`; `EST/docs/DEPLOY.md`; `IA/src/ia_atendimento/api/saude.py` (`/healthz`); `IA/.github/workflows/ci.yml` (a main **não tem** `imagem.yml`).
- **Evidência esperada:** nenhum gatilho de build/deploy por push em branch; imagem identificada por tag imutável + digest; `deploy-vps.sh` recusa referência que não seja `vX.Y.Z` existente na `main`; `/healthz` devolve a mesma tag/sha.
- **Estado inicial:** esteira = **A PROVAR** (em `9e1afe3`, 178 commits atrás da main; não está na origin). Na main e em produção = **NÃO EXISTE** ⇒ aceite de **A6.6b + A4.9 + B1.7 (tag `v0.3.0`)**. Configuração do Coolify remoto (auto-deploy por webhook desligado? fonte = imagem do registry, não o repo? — P-R8 diz «construída pelo Coolify a partir do GitHub», a esteira diz «builder da S3 + registry»: **contradição a resolver**) = **NÃO VERIFICÁVEL** ⇒ sonda: na aplicação do Coolify, tipo de build, `is_auto_deploy_enabled`, e o `image:tag` do contêiner (`docker inspect --format '{{.Config.Image}}'`).
- **Perguntas dirigidas:**
  1. `imagem.yml` confere que a tag aponta para commit **contido na `main`** (`release.sh:24` exige cortar da main, mas a tag pode ser empurrada à mão de qualquer commit)?
  2. `deploy-vps.sh`: aceita `latest`, sha ou branch? Quem grava `IMAGE_TAG` e pede «sim» (PD-2)?
  3. P-R8 × esteira: qual é o desenho vigente? Se o Coolify construir do GitHub por webhook, «só por tag» depende de configuração de tela.
  4. Quem pode empurrar tag `v*`? A proteção de tags no GitHub existe (ruleset `main-protegida` cobre só branch, PLANO §0.4)?
  5. As migrações sobem antes da imagem (C08 §10 «Ordem»)? A imagem recusa subir com migração faltando (`IA/src/ia_atendimento/prontidao.py`, `migracoes.py`)?
  6. Rollback: voltar para a tag anterior com a 0005 aplicada funciona (DDL só relaxa o CHECK)?

## RS-19 — Modo teste (e `duble`/`sombra`) nunca alcança a FACTA de produção

- **Fonte:** PLANO §8 «RS-19 modo teste nunca alcança FACTA de produção»; C08 §6 «Regras de `modo` (F22)» (tabela por modo e exceções 1–5; «parada dura»); ROT §0.1 item 8 «A IA nasce desligada (`ia_ativa=false`) e em `modo=duble`»; ROT Parte D 100 (token único da FACTA).
- **Como se prova:** leitura de `modo.py` + teste existente (tabela modo × serviço × classe × posse).
- **Onde olhar:** `IA/src/ia_atendimento/ferramentas/modo.py:41` (`VARIAVEIS_DE_AMBIENTE`), `:140-172` (`Destinos.resolver`): `:151-154` (`real` ⇒ produção), `:155-165` (FACTA: modo ≠ `teste` ⇒ `interceptado`, ou `MODO_SOMENTE_LEITURA` para leitura com posse real; `teste` sem base de dublê ⇒ `MODO_SOMENTE_LEITURA` «nunca cai na produção»), `:166-172` (demais serviços: efeito ⇒ `interceptado`; `sombra` ou `duble` com posse real ⇒ produção **somente leitura**; senão `fixture`); `IA/src/ia_atendimento/ferramentas/gateway.py:62,359-365`; `IA/src/ia_atendimento/pessoas_teste/fixtures_duble.py`; `IA/fixtures/duble/*.json`. Testes: `IA/tests/test_ferramentas_modo.py`, `test_fixtures_duble.py`, `test_ferramentas_gateway.py`.
- **Evidência esperada:** para `modo ∈ {teste, duble, sombra}`, nenhum ramo de `resolver` devolve `Destino("producao", …)` para `servico == "facta"`; teste parametrizado cobrindo a tabela inteira; variável de teste apontando para host de produção recusada.
- **Estado inicial:** **A PROVAR** (o ramo existe e parece fechado). Executores reais de T7/T8/T9 = **NÃO EXISTE** (B5.4) ⇒ critério: o executor usa **só** `destino.url` (`gateway.py:95`). Valores vivos das variáveis de base (produção × teste) = **NÃO VERIFICÁVEL** (VPS não existe).
- **Perguntas dirigidas:**
  1. `Destinos.de_ambiente` (`modo.py:140-146`): a base `teste` da FACTA é validada (host do dublê/WG) ou qualquer URL serve? Se alguém puser a URL de produção na variável de teste, `modo=teste` fala com a FACTA real.
  2. O `modo` passado a `resolver` é o **do atendimento** (congelado na entrada) ou o global lido na hora? Mudar `config.modo` para `real` com atendimentos `duble` abertos faz o quê (C08 §6)?
  3. Exceção 1 de C08 §6 (posse real sob parada dura executa real): que serviços alcança? O comentário de `modo.py:458-460` diz que a leitura da FACTA com posse real fica fail-closed «até o dono decidir» — está na lista do dono?
  4. `sombra` lê o 360 de produção com CPF (`_DESTINOS_COM_CPF` inclui `producao`): é o desenho (sombra A com texto real, G2) — confirmar que não há efeito (escrita) possível no 360 nesse modo.
  5. Algum cliente HTTP de ferramenta constrói URL fora de `destino.url` (constante, variável de ambiente lida direto)?

## RS-20 — MVP: só a FACTA digita

- **Fonte:** ROT §0.1 item 6 «**MVP: só a FACTA digita**; 3RN e C6 só mostram oferta e simulam» (l. 22); ROT §0.5 alíneas (w) «**MVP começa só com FACTA**; 3RN/C6 só oferta e simulação», (x) «Piloto só com leads com oferta FACTA ativa», (n) «Fallback de banco só depois de esgotar o principal… pós-MVP»; ROT §0.3 regra 9; PLANO §8.
- **Como se prova:** leitura do catálogo + teste existente; CHECK do banco.
- **Onde olhar:** `IA/src/ia_atendimento/ferramentas/catalogo.py:165` (T5 `servico="banco"`: simula em FACTA/3RN/C6), `:174-175` (T7: `bancos=("FACTA",)`, `flag_dos_bancos="bancos_digitacao"`), `:180` (T8), `:184` (T9); `ferramentas/especificacao.py:34,67`; `ferramentas/gateway.py:214-282` (onde `bancos`/`flag_dos_bancos` são conferidos); `IA/migrations/0001_esquema.up.sql:24-60` (CHECK de `config_versao`: chave `bancos_digitacao`?), `:62` (seeds «Tudo nasce DESLIGADO»); `IA/src/ia_atendimento/chave_registro.py` (registro/validação de config); `IA/fixtures/duble/3rn_calcular.json`, `c6_simular.json`. Testes: `IA/tests/test_ferramentas.py`, `test_ferramentas_registro.py`, `test_ferramentas_gateway.py`.
- **Evidência esperada:** dupla trava: (1) constante de código `bancos=("FACTA",)` em T7/T8/T9; (2) flag `bancos_digitacao` que só pode **restringir** (interseção), nunca ampliar; teste que prova T7 com banco ≠ FACTA recusado mesmo com a flag listando 3RN/C6.
- **Estado inicial:** **A PROVAR** (catálogo). Executor de T7 e a entrada «só lead com oferta FACTA ativa» (E0, critério 1 do braço) = **NÃO EXISTE** ⇒ aceite de **B5.4, B5.5 e B6.2**.
- **Perguntas dirigidas:**
  1. A flag `bancos_digitacao` é interseção com `bancos=("FACTA",)` ou substitui? Um `PUT /config/bancos_digitacao` com `["FACTA","C6"]` é recusado pelo CHECK/registro?
  2. O banco da digitação vem de onde: argumento do modelo (`ArgsTentativa`), da oferta referenciada, ou fixo? O modelo pode pedir T7 com `banco="C6"`?
  3. T5 em 3RN/C6 é só leitura/simulação? Algum endpoint de «simular» desses bancos tem efeito colateral (consulta paga, reserva de margem, fila da AJIN)?
  4. `timeout` de 3600 s do 3RN (`especificacao.py:67`) existe no MVP — para qual ferramenta?

---

## Restrições que os documentos impõem e a matriz não tinha

Formato compacto; mesmas colunas. Todas entram na Fase 2 com a mesma regra dos 3 verificadores.

### RS-21 — Texto, telefone, nome e e-mail do cliente só na trilha cifrada (PII que não é CPF)

- **Fonte:** ROT §0.3 regra 2 «o `gl-gateway` da S2 remove CPF, celular, nome e e-mail do Post: allowlist de campos por rota, B6.0» e regra 3 «Nunca em `passo`, log, ntfy, Kan, git» (l. 42–43); C08 §3 (`chat_number` ⇒ cofre `canal`, ≤ 7 d) e §5.4 «Texto livre e PII (F09)»; C04 §2.3, §2.7; C07 §5.5 `validarTextoLivre(motivo)`.
- **Prova:** leitor «o que o modelo vê» + canário reduzido (PLANO §8: três famílias — CPF/telefone/e-mail; nome/endereço; frase-nonce).
- **Onde olhar:** `IA/src/ia_atendimento/mascara.py:98` (e-mail), `:163-192` (nomes: só os que recebe em `nomes`), `:196`; `IA/src/ia_atendimento/conversa.py`, `cofre.py:39`, `estado_entrada.py`, `api/atendimentos.py`, `api/anotacoes.py`, `api/validacao.py` (texto livre «sem PII» é validação); `IA/migrations/0001_esquema.up.sql:221` (agendamento: «o texto NÃO mora aqui (só HMAC do texto mascarado…)»), `:383` (`qualidade_humana`: «nunca texto livre»); `GW/app/projecao.py`.
- **Estado inicial:** **A PROVAR**. Tela (`validarTextoLivre`) e n8n = **NÃO EXISTE** (B7.1, B6.2).
- **Perguntas:** (1) `mascarar(texto, nomes)`: de onde vêm os `nomes` se o orquestrador não recebe nome (A10 sem nome do cliente)? Nome dito pelo cliente no texto passa ao modelo? (2) Endereço, data de nascimento, nome da mãe, conta bancária (coletados em T6): são mascarados ou vão em claro ao modelo antes de irem ao cofre `digitacao`? (3) `motivo`/anotações de operador: a validação recusa ou mascara? (4) HMAC do texto mascarado no `agendamento` com chave permanente (RG-109) permite correlação — aceito?

### RS-22 — A IA nasce desligada e em `duble`; quem pode ligar

- **Fonte:** ROT §0.1 item 8 e §0.3 regra 9 «`ia_ativa` nasce `false`, `modo` nasce `duble`»; C08 §1 («`PUT /config/{nome}` | token `ti`; `c360_api` só para `ia_ativa` e `modo`…; `chats_teste` só `ti`») e §6; C03 §5.4 (`PUT /v1/ia/chave/{nome}` · escopo `ia:chave` · flag `C360_IA_CHAVE`) e §6.
- **Onde olhar:** `IA/migrations/0001_esquema.up.sql:62` (seeds), `IA/src/ia_atendimento/chave.py:143` (`garantir_defaults`), `chave_registro.py`, `api/config_rotas.py:42`, `api/auth.py`; testes `test_chave.py`, `test_api_config_agenda.py`, `test_config.py`.
- **Estado inicial:** orquestrador = **A PROVAR**; proxy da API e tela = **NÃO EXISTE** (B4.3, B7.1); estado vivo = **NÃO VERIFICÁVEL** (banco ainda sem migração ⇒ hoje não existe).
- **Perguntas:** (1) `garantir_defaults` pode **reescrever** `ia_ativa`/`modo` num boot (religar ou desligar sozinho)? (2) `modo=real` exige o quê além do token (motivo, `versao_esperada`, dupla confirmação)? (3) `c360_api` consegue mudar outra chave por algum alias? (4) A recusa é auditada (`por`, login)?

### RS-23 — Valor que nenhuma ferramenta devolveu nunca vai ao cliente; texto sensível é fixo

- **Fonte:** ROT §0.3 regra 12 «Valor que nenhuma ferramenta devolveu nunca vai ao cliente» (l. 52); ROT §0.1 item 5 «o modelo só classifica intenção, extrai literais e redige frases curtas. Texto sensível é fixo (TX-01…42, TX-M01…13)»; ROT B5.6 «**o modelo não escolhe**».
- **Onde olhar:** `IA/src/ia_atendimento/protecao.py:96-124` (`ha_link`, `_trocar_numero`), `turno.py:162-186`, `agente.py`, `ferramentas/projecao.py`, `ferramentas/saida.py:100` (`formatar_brl`), `modulos_fase.py`, `roteiro_f3.py`; testes `test_protecao.py`, `test_agente.py`; corpus `IA/src/ia_atendimento/corpus/regras/invariantes.py`.
- **Estado inicial:** proteção de saída = **A PROVAR**; máquina E0–E10 e textos TX travados por hash = **NÃO EXISTE** (B5.5, A7.2).
- **Perguntas:** (1) A proteção compara os números da fala do modelo com os valores devolvidos por ferramentas **neste atendimento** ou só troca números por marcador? (2) Taxa, prazo, parcela, nome de banco, data: quais classes de literal são conferidas? (3) Link na fala do modelo é barrado sempre (`ha_link`)? (4) O que sai quando a proteção barra: texto fixo, repasse, silêncio?

### RS-24 — Mensagem livre só até 24 h depois da última mensagem do cliente

- **Fonte:** ROT §0.3 regra 11 «(v3) **Mensagem livre só até 24 h depois da última mensagem do cliente**… o orquestrador guarda `ultimo_cliente_em`, bloqueia o texto livre ≥ 24 h e registra `janela_24h` por lembrete» (l. 51); C08 §8 «`ultimo_cliente_em` e janela de 24 h (F23)».
- **Onde olhar:** `IA/migrations/0003_estado_aditivo.up.sql:8-11`; `IA/src/ia_atendimento/estado_conversa.py:77`; `agendamento.py:70,104-107,222`; `estado_pausa.py:42` (`AGENDA_TETO_HORAS = 23`); 9 arquivos de `IA/src` citam `janela_24h` (`rs-05-contagens.sh`); testes `test_agenda_janela_mensagem.py`, `test_estado_conversa.py`.
- **Estado inicial:** registro de `ultimo_cliente_em` e teto da agenda = **A PROVAR**; bloqueio no envio = **NÃO EXISTE** (B6.8/B1.6b).
- **Perguntas:** (1) `ultimo_cliente_em` vem do evento (`datetime_post`, forjável/atrasado) ou do relógio do servidor? (2) NULL = desconhecido: bloqueia ou libera? (3) O RPA como leitor (E-19) atualiza o mesmo campo?

### RS-25 — Nenhum lead dorme com a IA; 20:15 grava `bloqueio_entrada`, nunca `ia_ativa=false`

- **Fonte:** ROT §0.3 regra 11 «**Nenhum lead dorme com a IA** (repasse forçado 19:45 = tarefa periódica do orquestrador, B6.7, `motivo_desfecho=fim_do_dia`…) (RG-065). **O timer das 20:15 grava `bloqueio_entrada`, nunca `ia_ativa=false`**» (l. 51); ROT P-R13 (l. 263); D-14 «**Espera total do repasse ≤ 30 min**» (l. 110).
- **Onde olhar:** `IA/src/ia_atendimento/calendario.py:30`; `fila.py:215` (`bloqueio_2015`); `jobs.py` (`executar_bloqueio_*`, `expirar_parados` em `:42-44,130,161`); `estado_pausa.py:69`; `B16/src/ia_atendimento/expiracao.py`, `espera.py`, `B16/tests/test_expirar_parados.py`, `test_espera.py`.
- **Estado inicial:** 20:15 = **A PROVAR**; 19:45 / `fim_do_dia` = **NÃO EXISTE** em qualquer base (F0-9) ⇒ aceite de **B6.7 + B1.6b**; D-14 (≤ 30 min, alerta aos 10) = **NÃO EXISTE** na main ⇒ aceite de **B1.6b/B6.3**; rede da S2 às 20:15 = **NÃO EXISTE** (B6.4).
- **Perguntas:** (1) Algum caminho da tarefa das 20:15 grava `ia_ativa`? (2) `pausado` atravessa a noite por desenho: e `aguardando`/`aberto` sem a tarefa das 19:45 — hoje ficam até o `expirar_parados`? Com que prazo? (3) Quem **reabre** `bloqueio_entrada` de manhã (07:45 manual? tarefa?).

### RS-26 — Teto financeiro e parada dura

- **Fonte:** C08 §9 «Gasto e teto financeiro (F25)» (fonte canônica Σ `passo.custo_brl`; limites `subteto_dia`, `teto_mensal_brl`; 80/100/125 %; «Gasto não calculável… **não chama o modelo**»; «Preços ausentes ou ≤ 0… o boot **recusa subir**»); ROT §0.6 J-Q1 «parada dura»; `IA/migrations/0001_esquema.up.sql:47` («TETO GLOBAL»: `custo_max_brl ≤ 3`, `agendamentos_max ≤ 10`).
- **Onde olhar:** `IA/src/ia_atendimento/chave.py:193-210` (`_gasto`, `gasto_mes`, `gasto_dia`, `disparos_dia`); `config.py` (preços, câmbio); `ferramentas/orcamento.py`; `turno.py`, `passos.py`; `B16/src/ia_atendimento/gasto.py`, `B16/tests/test_gasto_pendente.py`; `IA/tests/test_gasto_pendente.py`, `test_chave.py`.
- **Estado inicial:** leitura de gasto na entrada = **A PROVAR**; verificação no job `turno` e os 125 % = **A PROVAR na `b1-6a`** / **NÃO EXISTE** na main; alertas = **NÃO EXISTE** (B6.6). Limite de gasto do lado do provedor (cap na conta Fireworks) = **NÃO VERIFICÁVEL** ⇒ sonda: tela de billing/limite da conta (A1.4).
- **Perguntas:** (1) Laço de retentativa do pydantic-ai (validação de saída) conta cada chamada em `passo`? (2) Turno que falha depois de gastar grava custo (B16 `turno.py:12`)? Na main? (3) `custo_brl` nulo soma zero em silêncio em algum `coalesce`? (4) Teto por **turno** e por **chat** existem ou só dia/mês?

### RS-27 — Deploy: merge = deploy em `gl-gateway`/`facta-on`; janela de deploy; `main` protegida; web antes da API

- **Fonte:** ROT §0.3 regra 4 «**Web antes da API**… Tudo atrás de flag» e regra 5 (merge = deploy; «hora de deploy… 12:30–14:00 ou depois das 20:30; nunca 09–12 h nem em dia de piloto») (l. 44–45); PD-3 (l. 429, inclui «portão de disco da S2» e «Congelamento… 18/11 18:00»); D-09 (l. 124, 144); C01 §9, C05 §5, C03 §8, C07 §7.
- **Onde olhar:** `GW/.github/workflows/testes.yml`, `GW/.github/deploy-targets/gl-gateway-production.json`, `GW/.github/CODEOWNERS`, `GW/.github/BUILD_PIPELINE_VERSION`; `FO/` (workflows — confirmar se existem); `KITS/gateway/portao.sh`, `aguardar-reinicio.sh`; `KITS/merge-0411/merge-0411.sh`, `KITS/merge-d06/merge-d06.sh`.
- **Estado inicial:** processo, não código: **A PROVAR** no que há (kits, CODEOWNERS); proteção da `main` e auto-deploy = **NÃO VERIFICÁVEL** ⇒ sonda: `gh api repos/GL-BUSINESS/<repo>/rulesets` e `…/branches/main/protection` (PLANO §0.4: falta «exigir PR valendo para admin»).
- **Perguntas:** (1) Algum kit de merge confere hora (janela) e dia (piloto/congelamento) antes de mesclar? (2) O PR #49 do facta-on (rascunho, CONFLICTING) inclui migração? «Migração antes do merge» está garantida por quê? (3) `CODEOWNERS` do gateway exige revisor independente?

### RS-28 — Alerta só por ntfy; fluxo n8n «Atendimento IA» e `relatorios.lote_ia_config` não se usam

- **Fonte:** ROT §0.3 regra 10 (l. 50); alíneas (z) e (u); ROT A4.7 «ntfy: `ntfy.sh` no piloto (C9, D-05)»; PLANO §8 (ntfy.sh como terceiro).
- **Onde olhar:** grep de ausência: `discord`, `lote_ia_config`, «Atendimento IA» em `IA/src`, `GW/app`, `KITS/`; (nenhum `ntfy` em `IA/src` nem `B16/src` — F0-9).
- **Estado inicial:** ausência de Discord/fluxo antigo = **A PROVAR** (grep); ntfy = **NÃO EXISTE** ⇒ aceite de **B6.6** (payload sem PII: só códigos, contagens, `atendimento_id` opaco; tópico não adivinhável; teste do corpo).
- **Perguntas:** (1) O gateway hoje alerta por Discord em rota crítica (`critico=true` nas rotas `ia-*`, `rotas-ia.sh:24-26`)? Se sim, o alerta de `ia-mensagem` leva o quê? (2) `ia-sumidouro` é `critico=false` (`:27`): confirmado.

### RS-29 — A IA só fala com o mundo pelas APIs da GL; do 360 só o essencial (D-29); ISKRA único escritor do gl360

- **Fonte:** ROT §0.1 item 4 (l. 20); D-29 «Sem `ficha:ler`, `pessoa:dossie` nem `GET /pessoas/{id}`; nenhum escopo novo… Do 360 só `pessoas:resumos`… e `pessoas:propostas`…, com allowlist» (l. 106); C03 §1 «Duas credenciais, nunca uma», §1c; C06 §1 «O que o MVP NÃO pede ao ISKRA».
- **Onde olhar:** `IA/src/ia_atendimento/ferramentas/modo.py:41` (serviços alcançáveis), `ferramentas/catalogo.py:149-192`, `ferramentas/esquemas.py` (allowlist de saída), `IA/tests/contratos/cliente360-recorte.json`, `IA/scripts/atualizar_contrato_360.py`, `IA/fixtures/duble/cliente360_oferta.json`; `API/src/c360api/contrato/cliente360.json:73,93`; `API/src/c360api/borda/credencial.py`.
- **Estado inicial:** catálogo e recorte = **A PROVAR**; credencial da IA no `c360-auth` e escopos = **NÃO EXISTE** (B4.1) / **NÃO VERIFICÁVEL** depois; nenhuma conexão direta ao gl360 a partir do orquestrador = **A PROVAR** por grep de DSN (só `ia_atendimento`, `config.py:184`).
- **Perguntas:** (1) O validador `_banco_como_ia_app` recusa DSN de outro banco/usuário? (2) O recorte do contrato do 360 tem campos além dos necessários (endereço, contatos)? `PessoaResumo` traz `contatos_vigentes` (`cliente360.json:19052`): a allowlist de saída os descarta?

### RS-30 — n8n: nenhum PII em `execution_data`

- **Fonte:** C04 §2.3 «Por que nenhum campo de PII entra em `execution_data` (F01)»; D-19 «`saveData*: none` + ensaio» (l. 129); PD-6.
- **Onde olhar:** `KITS/gateway/ia-sumidouro.workflow.json:39-40`; (braço, repasse, agendar: sem artefato).
- **Estado inicial:** sumidouro = **A PROVAR**; demais fluxos = **NÃO EXISTE** (B6.2, B6.3); configuração viva do n8n (`EXECUTIONS_DATA_SAVE_*`, pruning) = **NÃO VERIFICÁVEL** ⇒ sonda: `printenv | grep -c EXECUTIONS_DATA` no contêiner do n8n e `select count(*) from execution_entity where "workflowId" = <sumidouro>`.
- **Perguntas:** (1) `saveManualExecutions` e `saveExecutionProgress` também estão desligados no JSON? (2) O webhook do sumidouro tem Header Auth (`x-gl-servico`) ou aceita qualquer chamador local?

### RS-31 — Fixture nasce da forma medida; dado real nunca no repositório; denylist de leitura

- **Fonte:** ROT §0.3 regra 13; PD-6 «payload real só fora do repo e com skip limpo… Extrato de produção: só nome de campo, tipo, contagem»; D-31 «apagar o corpus bruto no gatilho por estado»; PLANO §3 «Denylist de leitura».
- **Onde olhar (só por script/relatório):** `DUB/anonimizador`, `DUB/piiscan`, `DUB/piiscan.toml`, `DUB/tools`; `IA/scripts/gerar_pessoas_teste.py`, `IA/src/ia_atendimento/pessoas_teste/prefixo.py`, `pessoas.sha256`; `IA/src/ia_atendimento/corpus/pii.py`, `corpus/regras/pii.py`; `IA/tests/test_corpus*.py`, `test_pessoas_teste.py`.
- **Estado inicial:** **A PROVAR** por `piiscan` (portão de PII ao fim de cada fase, PLANO §8); D-31 = **NÃO VERIFICÁVEL** por agente ⇒ sonda do dono: `ls ~/ia-corpus/entrada | wc -l`.
- **Perguntas:** (1) A faixa sintética `000.000.[01]nn` é imposta por código (`prefixo.py`) e por teste? (2) O anonimizador é determinístico e reversível por quem tem a semente?

### RS-32 — Envio só como Amado Batista (ator 85); nota de repasse única e curta

- **Fonte:** ROT §0.5 alíneas (b) e (o); C02 §3, §5; C06 §2.
- **Estado inicial:** **NÃO EXISTE** (B6.8, B6.3, B5.5 E10) ⇒ critérios: nenhum outro ator configurável; nota sem PII e com teto de tamanho (`nota_repasse_tamanho`, `0001:439`); 1–6 cópias idênticas toleradas (ROT B6.3).
- **Perguntas:** só papel nesta fase: C02 §5 «Sem idempotência no servidor (ledger do orquestrador)» × RS-10 — o envio de mensagem é `efeito_irreversivel` no ledger?

### RS-33 — T15 e juiz por modelo nascem desligados; reserva = repasse

- **Fonte:** ROT §0.5 alíneas (a) «reserva = repasse», (l) «T15 verificador por modelo: opcional, chave própria, **nasce desligado**»; D-32 «Gemini segue só como contingência condicional».
- **Estado inicial:** **NÃO EXISTE** (B5.9, B8.3) ⇒ critério: mesma allowlist de host de RS-01; flag off por padrão; nenhum fallback automático de provedor.
- **Perguntas:** existe hoje algum campo de configuração de segundo modelo/segunda chave (`config.py`)? (Liga com RS-01 pergunta 3.)

### RS-34 — Phoenix só por túnel SSH no tailnet (D-30)

- **Fonte:** ROT A1.6 «Acesso ao Phoenix: só por túnel SSH no tailnet (D-30)»; ROT §0.6 D24–D26 (l. 231).
- **Onde olhar:** `IA/src/ia_atendimento/config.py:249-262`; `EST/docker-compose.yml` (portas publicadas).
- **Estado inicial:** **NÃO EXISTE** (A4.5) / depois **NÃO VERIFICÁVEL** ⇒ sonda: `ss -ltnp` na VPS (Phoenix só em `127.0.0.1`/WG) e ausência de hostname público no Cloudflare.
- **Perguntas:** o compose da esteira publica a porta do Phoenix em `0.0.0.0`?

### Restrições de processo (sem linha própria; conferir na Fase 1)

Rodízio «quem implementa não revisa» e «todo teste reprova sem a mudança» (ROT §0.3 regra 7; PD-4, PD-5); Kan como fonte da verdade e sem PII nos cartões (regra 8; PD-1); «estudar antes de construir» (regra 9); «esperar a condição, não o sinal» (regra 13); `/healthz` com `version`, `git_sha`, `built_at` e «no ar» só depois da vigia (regra 14).

---

## Resumo de estados iniciais

| RS | Estado inicial |
|---|---|
| RS-01 | código A PROVAR · rede NÃO EXISTE (A4.1/A4.4/A4.9) |
| RS-02 | A PROVAR |
| RS-03 | A PROVAR · ntfy NÃO EXISTE (B6.6) · limite do `mascara.py` = decisão do dono · sumidouro = risco a confirmar |
| RS-04 | A PROVAR · leitor real e integração com o ledger NÃO EXISTEM (B5.2, B1.6, B5.4) |
| RS-05 | cifra A PROVAR · descarte NÃO EXISTE (A4.9 + kit de chave) · hosts distintos NÃO VERIFICÁVEL |
| RS-06 | por armazém (tabela): 8 A PROVAR · 4 NÃO EXISTE · Phoenix/pgBackRest/payloads vivos NÃO VERIFICÁVEL (D-32 bloqueia G2) |
| RS-07 | A PROVAR (kits, config) · onde os valores moram NÃO VERIFICÁVEL |
| RS-08 | A PROVAR + ensaio · 4 kits NÃO EXISTEM · sha256 do kit vivo NÃO VERIFICÁVEL |
| RS-09 | calendário A PROVAR · ponto de envio NÃO EXISTE (B1.6b, B6.8) |
| RS-10 | main NÃO EXISTE (B1.6, B5.4) · `b1-6a` A PROVAR · janela 20 min NÃO EXISTE (B3.2) |
| RS-11 | NÃO EXISTE (B1.6b, B6.4, B6.8, B6.6) |
| RS-12 | DDL e kit A PROVAR · S4 viva NÃO VERIFICÁVEL |
| RS-13 | A PROVAR (linha de base suspeita de não ter rodado) |
| RS-14 | A PROVAR · `ia-sumidouro` = ausência de controle a confirmar |
| RS-15 | A PROVAR · tap NÃO EXISTE (B3.1) · valores vivos NÃO VERIFICÁVEL · alcance de «sementes» a fixar com o dono |
| RS-16 | A PROVAR (2 modelos sem a opção já localizados) |
| RS-17 | gateway/orquestrador A PROVAR · facta-on e n8n NÃO EXISTEM (B3.1/B3.2, B6.2) · nginx NÃO VERIFICÁVEL |
| RS-18 | esteira A PROVAR (só local) · main/produção NÃO EXISTE (A6.6b, A4.9, B1.7) · Coolify NÃO VERIFICÁVEL |
| RS-19 | A PROVAR · executores NÃO EXISTEM (B5.4) |
| RS-20 | A PROVAR · executor e critério de entrada NÃO EXISTEM (B5.4, B5.5, B6.2) |
| RS-21..34 | ver cada linha (10 com parte A PROVAR; RS-32 e RS-33 inteiras NÃO EXISTE) |

## Pendências desta matriz (o que a Fase 0 não fechou)

1. Linha de base de ferramentas: os 8 `gitleaks-*.log` têm tamanho idêntico (2.680 bytes) e o `semgrep` tem 108 bytes; não foram abertos aqui. Sem eles, RS-13 começa sem linha de base.
2. «Sementes» em RS-15 e a exceção de `DELETE` em `procrastinate` (RS-12) precisam de palavra do dono ou de âncora que eu não encontrei.
3. `cliente360-web` fora da exportação: RS-22 (tela) e RS-27 (web antes da API) ficam só no papel.
4. Não li os contratos por inteiro: as âncoras de C02, C03, C06 e C07 vêm dos títulos de seção e de grep; os leitores da Fase 1 devem reconferi-las.
5. Arquivos casados por contagem e não identificados: os 2 de `IA/src` e de `B16/src` com `impedidos|"vivos"|batimento_` (RS-11), os 2 de `IA/tests`+`IA/fixtures` com `anthropic|api.deepseek` (RS-02), o de `KITS/` e o da esteira com `nft` (RS-01).
