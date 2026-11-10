# Plano da revisão completa — IA de atendimento (09/11/2026) — v3 (10/11)

> Pedido do dono (09/11 noite): revisão por completo, do início ao fim, pegando todas as brechas, por workflows (ultracode), **sem Codex**. Este documento é o plano; nada foi revisado ainda.
> v1 (21h) passou por 4 críticos de contexto limpo em Sonnet 5.5 (`~/ia-revisao-0911/plano/critica-r1.md`, 46 lacunas). v2 incorpora as lacunas. v2 passou por 3 críticos Fable 5.1 (`critica-v2.md`): «pronto com emendas pequenas». **v3 aplica as emendas; onde o corpo e o §8 divergem, vale o §8.** Dono, 10/11: «faça enquanto respondo» + «depois faça as Fases 1 a 5; pode usar agente Fable e Opus».

## 0. Fatos medidos pelos críticos (09/11 ~21h BRT) que o dono precisa saber hoje

1. **Nenhum ato de 09/11 tem registro:** memória, roteiro, painel, RETOMAR, origin/main e worktrees não mudaram desde 04/11 19:27. Não li produção nem o Kan por dentro; «sem registro» não é prova de «não feito». **Pergunta fechada ao dono (§7).**
2. **Relógio de hoje:** o Redeploy do gateway de **10/11 05:30** só roda se `rotas-ia.sh` e `env-gateway.sh --gravar` tiverem sido feitos na noite de 09/11. Senão cai na reserva **11/11 05:30**, e A3.0–A3.7 (ensaios do canal) e o aceite da B1.6 escorregam um dia.
3. **Capacidade:** o resíduo de 63,6 dias-agente supunha 10 dias (09→18/11). Com 9 dias a partir de 10/11, o teto cai para r ≈ 0,71 (5 agentes) / 0,57 (4) / 0,42 (3), contra o ritmo medido de 0,49. Com 3 agentes não cabe; com 4 a folga é 0,08. **Esta revisão concorre com os agentes de construção.** (HIPÓTESE aritmética; a Parte C «Se atrasar» já diz: 1 dia ⇒ congelamento 19/11 e piloto de 4 dias; 2 dias ⇒ sem piloto real.)
4. **main com proteção parcial:** ruleset de org `main-protegida` (04/11) bloqueia exclusão e force-push nos 3 repos; falta do D-09 só «exigir PR valendo para admin» (10/11 12:00). `facta-on` e `gl-gateway` fazem deploy no merge.
5. **facta-on PR #49** (tap sem PII, rascunho) **conflita** com origin/main (`docker-compose.yml`, `tests/conftest.py`) depois dos merges #50–#56 de 05–09/11. O deploy #5 (12/11) depende dele. `conferir_janela_min` ainda é 10 (contrato 05 pede 20).
6. **Trabalho só local, sem cópia no GitHub:** `feat/esteira` (Dockerfile, compose, `deploy-vps.sh`, `release.sh`, `DEPLOY.md`, 1.225 linhas) e `kits/s4` (1.228 linhas) em `~/wt-ia/`, sem branch remota. Os kits de produção em `~/retomada-2809/fila-2910/ia/` não estão em git (modo 775, sem hash).
7. **B1.6b não começou** (sem branch nem worktree); PR #13 (B1.6a) espera por ela desde 04/11. Kits previstos para 05–08/11 não existem (`s4/migrar.sh`, `config/domingo.sh`, `gateway/ativar.sh`, chave AES de dezembro).
8. O **Painel de estado** do roteiro está atrás do git: B1.8, B2.1 e B5.1 constam «não iniciada» e estão na main.

## 1. Ponto de partida

- Código (origin/main local, último fetch a confirmar por `git ls-remote`): `ia-atendimento` `9a4baca` (src 874 KB / 98 arquivos / 16.855 linhas; tests 75 `test_*.py` + apoios; migrações 0001–0005), PR #13 `feat/b1-6a` (`9a714e3`, +2.503 linhas: ledger, gasto, espera, expiração, espelho); `bancos-duble` `ca3ed2c` (713 arquivos, 3,1 MB de mappings gerados); `gl-gateway` `92e9754` v0.4.0; `facta-on` `8c3e5ab`; `cliente360-api` `2b2d71d`; `cliente360-web` `ea6599fd` (só spec da tela; sem código da IA). B4 e B7 **não têm código**: os leitores não devem procurar.
- Papel: roteiro v3.3 (1.734 linhas, 510 KB), contratos 01 v2.5, 02, 03 v2.2, 04 v2.2, 05 (rótulo v2.1), 06 (sem rótulo), 07 v2.2, 08 v2.4; estudos a–n (695 KB), D18, D29, replanejamento, tela da IA (161 KB + 227 KB de L/R), levantamento 01–11 (425 KB), medições (59 KB), planos (141 KB), SÍNTESE, MONITORAMENTO, premissas, textos.
- Revisão de 03/11 (`REVISAO-GERAL-0411.md`, canônica em `estudos/`): **128 ids RG** (116 sobreviventes, RG-128 fora da conta, 11 refutados), 32 decisões D-nn, superadas em 4 camadas (resposta 03/11 noite → parecer Codex → respostas 04/11 11h → cenário C 04/11 tarde → contratos emendados). 111 sobreviventes constam na Parte F como «aplicado em texto (v3.3)», que prova só papel. Linhas «ROT:n» de §F e do parecer são da v3.2 (1.355 linhas): **número de linha não é prova; âncora de texto é.**

## 2. O que esta revisão responde

1. **O que do dia 09/11 aconteceu e o que bloqueia a B1.6b hoje** (pergunta de 5 linhas ao dono + Kan + git; sem agentes). E: **efeito no calendário** (§0.3) com a decisão do dono entre congelar construção durante a revisão, rodar em paralelo com paralelismo limitado, ou revisão enxuta.
2. **Fechamento rastreável dos 128 RG e das 32 D-nn**, medido contra a **última camada** de decisão, em 4 estados: fechado com prova (arquivo:linha de contrato/roteiro, commit/PR na origin, ou leitura de produção), fechado só no papel, aberto, superado. Mais os 20 «AJUSTAR» do Codex (adotado / superado / aberto, com dono e data).
3. **Coerência do papel** depois da v3.3: roteiro × contratos × estudos × decisões; etapas órfãs, datas vencidas, emendas aplicadas pela metade, Painel mentiroso.
4. **Código × contrato**, bloco a bloco, com os `docs/DECISOES-*`/`REVISAO-*` de cada bloco como entrada obrigatória, e **costuras** lidas com os dois lados em mãos.
5. **Segurança e PII** pela matriz de restrições (§3b), com três estados de prova.
6. **Kits de produção**: provado em ensaio local / nunca rodado em real / irreversível, por passo; idempotência e interrupção no meio; `desfazer.sh` como entrega própria; manifesto sha256.
7. **O que falta para a IA conversar de ponta a ponta** e o que o código assume de dependências externas não confirmadas (registro de premissas).

## 3. Regras

- **Só leitura.** Sem merge, push, fetch, deploy, `!` de produção, escrita em banco, correção de código. Ensaios rodam em worktrees descartáveis em `~/ia-revisao-0911/wt/` e Postgres descartável; nunca nos checkouts nem nos kits.
- **Sem Codex.** Independência: quem acha não verifica; verificadores tentam derrubar e variam prompt e ordem de leitura.
- **Proveniência:** todo achado cita `SHA:caminho:linha` (código) ou `arquivo:âncora de texto` (papel). Linha sem âncora é pista, não prova.
- **Denylist de leitura para todo agente:** `~/ia-corpus/` inteiro, qualquer `.zip`, `mappings/` do bancos-duble, `pessoas*.json|yaml`, `tests/corpus/dialogos`, arquivos 0600, `.env`, `~/.config/ia/`, `$SEGREDOS_DIR`, dumps, `gateway.payloads`. Esses só passam por varredura de script (`scripts/varredura.py`, `piiscan`, gitleaks) e o agente lê o relatório. Citação é por forma e contagem, nunca valor.
- **Portão de PII ao fim de cada fase:** `varredura.py` + gitleaks sobre `~/ia-revisao-0911/`; falha bloqueia a fase seguinte. `~/ia-revisao-0411/trabalho/` é varrido antes de ser reaproveitado.
- **Três estados de prova:** PROVADO EM CÓDIGO · PROVADO EM ENSAIO · NÃO VERIFICÁVEL AGORA (vira pós-condição escrita do kit/ato e lista de sondas só-leitura para o dono rodar com `!`).
- Tudo em `~/ia-revisao-0911/` (retomável); `estudos/REVISAO-GERAL-0411.md` é a versão canônica da revisão anterior (diff contra `.final.md` registrado na Fase 0).

### 3b. Matriz de restrições (uma linha por restrição; preenchida na Fase 0, provada na Fase 2)

Colunas: ID · fonte (arquivo+seção) · como se prova (grep de ausência / teste existente / teste novo / ensaio de kit / não verificável) · evidência esperada · estado · dono. Linhas mínimas:

- RS-01 só `us.api.fireworks.ai` + roteador `-us`: código (`config.py` HOSTS_DO_MODELO, validadores; todos os clientes HTTP/OTLP/DNS e endpoints por variável) **e** rede (VPS só tem chain `input`; ausência de política de saída é achado; propor `nft output` allowlist).
- RS-02 nada Anthropic / DeepSeek oficial no produto: grep em src, prompts, fixtures, `uv.lock`, `requirements.lock`.
- RS-03 CPF nunca a modelo/prompt/log/span/banco IA/ntfy/Kan/payload: leitor «CPF ponta a ponta» (todos os caminhos até cada sumidouro; `tests/test_vazamento_corpo.py` e o que ele NÃO cobre: CPF por extenso, misturado com letras, partido em mensagens, em URL/anexo, em resumo gerado). O limite declarado de `mascara.py` é **contradição da regra 2** e vai ao dono como decisão.
- RS-04 CPF só em memória do gateway de ferramentas: todos os call sites de `.revelar()`, nenhum `await` entre leitura e executor.
- RS-05 AES-256-GCM, AAD completa, chaves por mês, chave e texto cifrado em hosts distintos, descarte no dia 31.
- RS-06 **livro de retenção** por armazém (conversa_cifrada 14 d a partir do encerramento, cofre 1/7 d, args/eventos Procrastinate, `ia.passo`, Phoenix `ia_obs`, pgBackRest/WAL/dump, `gateway.payloads` 7 d, espelho S2 30 d, ntfy, logs de contêiner, n8n execution data, `~/ia-corpus`, a própria `~/ia-revisao-0911/`): origem do relógio, mecanismo, quem dispara, prova por consulta de forma, estado. Pior caso: atendimento que nunca encerra. Phoenix e pgBackRest são NÃO VERIFICÁVEIS sem estado vivo ⇒ D-32 fica como bloqueio de G2.
- RS-07 **inventário de segredos** (nome, onde mora, permissão, quem lê, rotação, o que um vazamento permite, prova de ausência em git/Kan/log): arquivos 0600 `:ro` × variáveis do Coolify; HMAC em 3 lugares (S2, S3, VPS); bearer do nginx; tópicos ntfy; token `ti` único e onipotente.
- RS-08 escrita em produção só por kit com ensaio, contagem e desfazer (PD-2); manifesto sha256 conferido antes de cada «sim».
- RS-09 janela 08–20 h e DATAPREV 20–23/11; RS-10 T7 em dúvida; RS-11 D-15 batimento fail-closed; RS-12 papéis/pg_hba (alínea v; `ia_qualidade` e `ia_app_b` sem linha no hba; `ia_app` com DELETE em procrastinate; `bkp_pg` ganha `ia_atendimento`); RS-13 segredos em repositório (gitleaks no CI só do bancos-duble; `.gitleaksignore` do ia-atendimento admite CPF de DV válido no histórico sem prova de ser sintético); RS-14 «teste × real» (`pessoas_teste`, `chats_teste`, `_regra_do_canal_de_teste`, `chatguru-ia-teste` alcança `ia-mensagem` sem trava técnica).

## 4. Fases (um workflow por fase; leio o resultado antes da seguinte)

### Fase 0 — Manifesto, inventário por script, linha de base (3–4 agentes + scripts)
- `git ls-remote` só-leitura nos 6 repositórios (ponta remota × origin/main local); **MANIFESTO** com SHA de cada repo/ramo/PR aberto, sha256 de cada kit e de cada contrato vigente, mergeabilidade dos PRs (`gh pr view --json mergeable`).
- Inventário **por script** (`git ls-tree -r` + `wc` por repo, ramos abertos nomeados, kits, worktrees com `não mesclado / não enviado / sem upstream`), não por LLM. Tabela de unidades de leitura com tamanho. Cobertura = diferença entre inventário e «o que cada leitor devolveu ter lido», por script.
- Linha de base de ferramentas em worktrees descartáveis no SHA do manifesto: `scripts/check.sh` ×3 (uma sob carga) com `BANCOS_DUBLE_PATH` certo; gitleaks (dir + histórico completo, `--redact`) nos 6 repos e nos worktrees de `~/wt-ia`; `scripts/varredura.py`; Semgrep CE (`p/python`, `p/secrets`, `p/owasp-top-ten`) em ia-atendimento e gl-gateway; `insecure-defaults:audit` nos dois; auditoria de dependências. Resultado = candidatos a achado, nunca veredito.
- Tabela `inventario-rg.csv` (128 ids): severidade, tipo, D-nn, linha de §F, linha da Parte F, âncora de texto no v3.3, tipo de fechamento esperado, estado. Pontos de partida: `v33/patch-*.pulados.md`, `v33/falhas.md`, `v33/VERIFICACAO.md`, `itens-fase3.json`. Cadeia de supersessão por D-nn.
- Reconciliação em 4 vias (Painel × git × memória × Kan) etapa por etapa, git como autoridade; cada divergência é achado «estado do roteiro mentiroso».
- **Registro de premissas externas:** ChatGuru webhook por mensagem, RPA leitor, FACTA perguntas 1–4, Fireworks (chave, preço, latência, cache, retenção zero/DPA), VPS OVH, Dataprev, cookie do RPA: confirmada/suposta, quem confirma, quando, que caminho do código quebra se «não».
- Estado de cada ato de 09/11 e 10/11: feito com prova / não feito / desconhecido.
- Crítico de completude roda **uma vez aqui** sobre o plano de leitura (antes dos leitores).
- 5 **canários de recall**: achados já corrigidos (`docs/REVISAO-B*-3010.md` / `-r2.md`; passe cego em `<fix>^`, ver §8) que os leitores da Fase 2 devem reencontrar no commit anterior à correção.

### Fase 1 — Papel (≈ 30 leitores, teto 60–70 KB quando cruza, 100 KB se só inventaria)
Roteiro por linhas reais: 1–278; 279–438 (painel + PD); 439–619 (A1–A2); 620–744 (A3–A4); 745–848 (A5–A8); 849–971 (B1–B4); 972–1094 (B5–B6); 1095–1202 (B7–B12); 1203–1324 (calendário); **1325–1506 (Partes D e E)**; 1507–1620 e 1621–1734 (Parte F + Anexo X).
Contratos: 01 em 2; 04 em 2; 08 em 2; 03+05+06; **02**+07; REVISAO-CONTRATOS-1/2 + PARA-O-DONO; leitura cruzada de fronteiras (quem emite × quem lê). Versão antiga só pelo resumo de mudanças do topo.
Estudos: a+b+c; d+e; f+g+h; i em 2 (DDL × `migrations/0001`); j+k+l; m+n+REVISAO-LACUNAS; D18+D29+replanejamento; TELA-IA-C360 em 2 + spec do web; tela-ia L/R em 2.
Intenção e evidência: SÍNTESE + plano mestre + MONITORAMENTO + premissas/custos (números citados no roteiro); levantamento 01–03; 04–06; 09–11 + medições + incidente; TEXTOS-PARA-APROVACAO + G0-PEDIDO. Fora: README.md, index.html, prototipo.html, maquete.html, versões antigas, `i-teste-0001.sh`.
Fechamento: 6 leitores por faixa de RG (~20 cada, com o trecho que os fecha) + 1 para 32 D-nn + 20 AJUSTAR.

### Fase 2 — Código, kits e ferramentas (≈ 30 leitores; teto ~250 KB src+testes por unidade)
`ia-atendimento` (main + `feat/b1-6a` como segunda base, com `git diff origin/main...feat/b1-6a`): estado+pausa+entrada; linha_tempo+conversa+cifra+cofre+proteção; fila+jobs+worker+enfileirador+observabilidade+scrubber; API de entrada (`app.py`, `auth.py`, `eventos.py`, `config_rotas.py`, `ambiente.py`; checklist: matriz rota×origem×credencial, 401/403 idênticos, 413, replay ±300 s no-op, ordem auth→corpo→parse, `x-gl-*` forjado, `ti`/`c360_api` sobre `ia_ativa`/`modo`/`chats_teste`, ausência de rate limit e lockout); turno+agente+passos (DECISOES/REVISAO B1.4); contexto+mensagens+calendário+modulos_fase+roteiro_f3 (**lente «o que o modelo vê»**: ProvedorFalso `vistos` nas 84 pessoas_teste, por fase, em arquivo local; CPF ausente, texto mascarado, TETO_TOKENS, ContextoNaoCabe); ferramentas (B5.1; gateway.py, projecao.py, segredo.py); agenda (extrator × estado/jobs; B5.7a/b); pessoas_teste+corpus (por script; B2.4, B8.1a); migrações 0001–0005 + testes (B1.8; asserções do 0001 em PG descartável; matriz papel×tabela×privilégio por `has_table_privilege`); ledger B1.6a; **esteira+CI** (`feat/esteira`, `ci.yml`, `.gitleaks*`, `kits/chats-teste.sh`, `scripts/*`).
`gl-gateway` em 2 (app; testes+docs B6.0; perguntas fixas: `corpo_campos` NULL × `{}`, quem escreve em `gateway.rotas`/`ips_confiaveis`, DESTINOS_PERMITIDOS, fallback de coluna ausente fail-closed, `ia-sumidouro` sem trava).
`bancos-duble` (código+docs ≈ 952 KB; mappings só por `piiscan`; anonimizador e faixa 000.000.xxx).
`facta-on` fronteira IA (`online.py` ≈ 4640–4990 (`/proposta/por-cpf` na linha 4672), flags `FACTAON_*`, `test_proposta_conferir.py`, contrato 05, PR #49 contra `8c3e5ab`, `app/log_acesso.py`).
`cliente360-api` (rotas `/v1/ia/*`, escopos, migração 000025, flags; o que o contrato 03 consome) e `cliente360-web` (spec + contrato 07; confirmar ausência de código).
n8n do braço (contrato 04 + `ia-sumidouro.workflow.json`): credenciais, retenção de execução, Code node, Header Auth.
Kits em 4: gateway produção (rotas-ia, env-gateway, montar_env, portão, vigia, desfazer, migrar, sql); gateway ensaio (ensaio-local.sh + stub + README: «o ensaio prova o que diz?»); s4; config + merge-0411 + merge-d06. **Rodar** os `ensaio-local.sh` em cópia descartável, inclusive `desfazer`, duas vezes seguidas e interrompido no meio; tabela por passo; o que cada kit deixa em disco; nenhum segredo em argv/`set -x`/stdout.
**Canário ponta a ponta** (uma execução no ensaio local): conversa sintética com CPF 000.000.xxx, telefone, e-mail, nome, endereço marcados; procurar cada canário e variantes em dump inteiro do banco (incl. `procrastinate_jobs`, `passo`, `ferramenta_chamada`), spans em memória, stdout/stderr, corpo ao provedor, payload ntfy, temporários. Ocorrência fora de `conversa_cifrada`/cofre = CRÍTICO.
Lentes transversais como **passes dirigidos** (grep estruturado → leitura de contexto), não «sobre tudo»: segurança/PII; falha silenciosa (`except`/`return None`/fallback, por quem leu o pacote); testes que congelam erro (só módulos com achado ≥ MÉDIO); **concorrência/idempotência** (entrega duplicada e retentativa em cada salto ChatGuru→gateway→n8n→API→job→ferramenta→FACTA; queda entre efeito e ack; worker morto no turno; kit rodado 2×; `test_rajada_um_turno`); **gasto** (teto por turno/dia/chat, laço de retentativa do pydantic-ai, chave zerada, parada dura na main, D3); **operação** (matriz alerta→quem→prazo→ação; substituto; 8 dias seguidos do mesmo operador).

### Fase 2b — Costuras (≈ 6 leitores, dois lados em mãos)
ChatGuru→gateway; gateway→orquestrador (vetor dourado cruzado `test_ia_assinatura.py` × `test_contrato_api.py`); orquestrador→n8n braço; orquestrador→cliente360-api; orquestrador→facta-on (+ fixtures do dublê); orquestrador→web/liga-desliga. Tabela campo a campo: quem emite, quem lê, tipo, nulabilidade, código de erro, retentativa.

### Fase 3 — Fusão e verificação (por lote, logo após cada fase 1, 2, 2b; checkpoint salvo)
- Fusão por agente dedicado com chave (repo+arquivo+faixa ±10 linhas, ou par de trechos + regra violada); fusão também contra RG-nnn (reabertura ≠ achado novo); todas as provas preservadas.
- Lentes por tipo: papel = fidelidade + superado + materialidade; código = reprodução (teste/mutação/traço) + superado + materialidade; kit = trecho do ensaio que prova. **Veredito por subafirmação.**
- CRÍTICO/ALTO: 3 verificadores; cai com 2 refutações **com contraprova arquivo:linha**; 1 refutação = «contestado», vai ao dono. MÉDIO: 1 verificador; refutação com contraprova rebaixa para «não confirmado», nunca apaga. BAIXO: checagem mecânica por script (arquivo:linha existe e a citação confere). Lente sem resposta = nova tentativa, não voto.
- Qualquer achado contra as restrições de §3b recebe 3 verificadores seja qual for a severidade. Categoria **«ausência de controle»** (prova = comando reprodutível com resultado vazio + SHA): só cai se um verificador mostrar o controle. Categoria **«risco aceito»** nunca cai: vai ao relatório com a decisão do dono que o aceitou.
- Rubrica de severidade de segurança escrita: CRÍTICO = PII/CPF/segredo alcançável fora do desenho ou escrita não autorizada; ALTO = defesa em profundidade ausente com caminho plausível; MÉDIO = controle frágil sem caminho demonstrado; BAIXO = higiene.

### Fase 4 — Completude (máximo 2 rodadas)
Crítico pergunta o que não foi lido (cobertura por script), que afirmação ficou sem prova, que costura ninguém cruzou, quantos dos 5 canários voltaram. A rodada 2 reexecuta **só as lacunas**. Para quando cobertura = 100 % do inventário **e** a rodada traz 0 CRÍTICO/ALTO verificado novo.

### Fase 5 — Síntese
`estudos/REVISAO-GERAL-0911.md`: veredito em 10 linhas; §1b efeito no calendário (tabela «Se atrasar» importada; conta r marcada como estimativa, pois nenhuma etapa registrou horas reais); achados por gravidade com prova e correção proposta; matriz de restrições com estado; livro de retenção; inventário de segredos (sem valores); registro de premissas com árvore de decisão; situação dos 128 RG e 32 D-nn; lista única do que depende do dono com data-limite; sondas só-leitura para o que é NÃO VERIFICÁVEL AGORA; ordem de ataque. Depois: painel, Kan, memória, roteiro (ponteiro na Parte F, Painel corrigido).

## 5. Modelos, paralelismo, custo

- Leitores e extração: **Sonnet 5.5** esforço alto. Inventário mecânico e fusão: **Haiku 5.5** max. Lentes transversais, verificadores, crítico de completude, síntese: **modelo da sessão (Fable 5.1)** — exceção à regra de 08/10, pedida ao dono em §7.
- Teto do Workflow na S3 = min(16, CPUs−2) por workflow; testes pesados em ondas de 3 (`pesado.sh`). Leitura ≈ 10 em paralelo.
- Total ≈ 86 leitores + verificadores ⇒ ≥ 200 agentes. Custo: sem medição anterior confiável; o custo real de cada fase sai do `journal.jsonl` para `custo.csv`. Não existe parada automática: o único freio é a diretiva «+N» do dono no lançamento. Checagem do limite de uso antes de cada lançamento; pausa do dono congela o estado com `resumeFromRunId`.

## 6. Correção vem depois

A revisão acha e prova. Correções saem numa etapa seguinte, com lista priorizada e «sim» do dono por item — porque correção depois do congelamento de 18/11 muda o calendário (§0.3).

## 7. Decisões do dono antes de lançar

1. **Pergunta fechada:** o que de 09/11 você fez? (A3.8 12:30 · A4.3a 13:15 · `rotas-ia.sh`/`env-gateway.sh --gravar` · cookie do RPA · chat de teste · perguntas ao ChatGuru/FACTA · titular/cartão · VPS · ata A1.10.) Sem resposta, trato como não feito e o Redeploy de 10/11 05:30 cai para 11/11.
2. **Construção × revisão:** (A) congelar a construção (NÃO recomendado: X7 em 10/11 18:00 exige ≥ 4 agentes de construção; 2 dias congelados = sem piloto real); (B) rodar em paralelo com a revisão limitada a 1–2 agentes pesados; (C) revisão enxuta (Fases 0, 2, 2b, 3, 5) até o congelamento.
3. **Calendário:** congelamento 18/11 e teto 04/12 continuam fixos, ou a revisão pode empurrar o piloto? (A correção dos achados ficaria depois do congelamento.)
4. **Modelos:** Fable 5.1 nas etapas de julgamento (lentes, verificadores, síntese), Sonnet nos leitores, Haiku no mecânico — ok?
5. **Leituras só-leitura de produção** para fechar o «NÃO VERIFICÁVEL AGORA»: autoriza uma leitura SELECT de `gateway.rotas` ia-*, versão viva do gateway, pg_hba/papéis da S4 e retenção do Phoenix — ou prefere rodar você com `!` a partir da lista que eu entregar?

### 7b. Pendências do dono no caminho crítico (da Parte C e do Painel; não inventadas)

| Item | Limite | O que para sem ele |
|---|---|---|
| A1.3 titular, e-mail de função, cartão em dólar | 10/11 | VPS (A1.5) e Fireworks (A1.4) |
| Ata dos padrões A1.10 | 10/11 | textos e respostas padrão |
| D-09 proteger main (3 repos) | 10/11 12:00 | merge = deploy sem revisão |
| A1.5 VPS OVH BHS | 12/11 14:00 | deploy do orquestrador (#8, 13/11), sombra (RG-041 CRÍTICO) |
| Substituto do Danilo e consultor sênior revisor | 11/11 | piloto não roda em dia de ausência |
| E-mails da semente | 12/11 | corpus por vendedor |
| Ciência do superior (A1.11), «sim» nomeado à 0005, aceite do provedor (E-3) | 13/11 | domingo, G2 |
| A1.4 chave Fireworks US$ 100 (arquivo 0600) | 17/11 | A2.9a; sem ela F3 só com ProvedorFalso e go/no-go «custo e latência não medidos» (D-01 pede não aceitar) |
| Chat de teste + 13 perguntas ChatGuru + 4 FACTA + cookie do RPA | 09/11 | A3.0–A3.7 |
| Aceite G2 | 18/11 | congelamento |
| 20 «AJUSTAR» do parecer (E-23) | a definir | — |

## 8. Emendas v3 (prevalecem sobre o corpo)

**Decidido pelo dono em 10/11:** Fase 0 e Fases 1–5 autorizadas; julgamento em Fable e Opus, leitores em Sonnet, mecânico em Haiku. Ainda abertos: atos de 09/11, degrau de 1 dia, prioridade da fila Cliente360, leituras de produção.

**Execução**
- Os agentes não leem os checkouts: leem uma **exportação** (`git archive` no SHA do manifesto) em `~/ia-revisao-0911/src/<repo>/`, já sem os caminhos da denylist (`mappings/`, `pessoas*`, `personas*`, `tests/corpus/dialogos`, `.zip`, `.env`). Papel é lido em `/opt/claude/docs/planejamento-ia/`. Kits são copiados para `~/ia-revisao-0911/kits/` sem arquivos 0600.
- Hook `rtk`: agentes usam Read/Grep/Glob; shell só por arquivo em `~/ia-revisao-0911/scripts/*.sh` chamado por `bash`, um por turno.
- Portão de PII: `piiscan` do bancos-duble + `gitleaks dir --no-git --redact` sobre `~/ia-revisao-0911/` ao fim de cada fase (o `varredura.py` só varre o próprio repo).
- Cobertura com coluna `modo` ∈ {leitor, script, fora}. Fusão contra RG-nnn em Sonnet com `inventario-rg.csv`.
- Fase 0 inclui linha do tempo 05–09/11 (MEMORY.md + commits) e reconciliação em **5 vias** (acrescenta kits × Parte C).
- Canários de recall: passe cego no commit pai da correção (`d0ddcb4^`, `34fafcf^`, `a30fd2c^`, `35d22cf^`), sem `docs/`.
- Canário ponta a ponta: versão reduzida por leitura de código e testes existentes (B1.7 não existe; harness completo fica como critério de aceite). Três famílias: CPF/telefone/e-mail; nome/endereço; frase-nonce.
- Ensaios dos kits: só se `GW_REPO`, `IA_REPO`, `IA_MIGRACOES`, `GW_PY` apontarem para a exportação; «PULADO» = não provado. `gateway/ensaio-local.sh:310` puxa imagem do Coolify: não rodar sem necessidade.
- Verificação: BAIXO por amostra de 10 %; verificador pode **subir** severidade com prova.

**Quarto estado de prova:** NÃO EXISTE ⇒ vira critério de aceite do bloco que vai construí-lo (não é achado de código).

**Matriz de restrições, correções**
- RS-01 rede descreve desenho (a VPS não existe) ⇒ NÃO EXISTE. RS-04: `.revelar()` não tem call sites; o CPF entra por `LeitorDeCpf` (`gateway.py:156,192,358`). RS-05: descarte no dia 31 é só papel. RS-10, RS-11, ntfy e 19:45 não existem na main (B1.6b, B6.6, B6.7) ⇒ NÃO EXISTE.
- RS-14: a trava `_regra_do_canal_de_teste` existe (`api/eventos.py:103,132`); sem trava é a rota `ia-sumidouro`.
- RS-06 acrescenta `espelho_evento`, `agendamento`, `candidato`, prazo de descarte desta pasta; simular `ia_app` chamando `fn_texto_podar(7,1,1)`. RS-07 acrescenta Postgres do Coolify S2 e backups, `CHAVE_H16`/`CHAVE_FINGERPRINT` no Coolify, ntfy.sh como terceiro.
- Novas: RS-15 flags e sementes `FACTAON_*`; RS-16 PD-6 `hide_input_in_errors` (`ferramentas/saida.py`, `especificacao.py`, `corpus/modelos.py`, `pessoas_teste/formas.py`); RS-17 log F07; RS-18 deploy só por tag; RS-19 modo teste nunca alcança FACTA de produção; RS-20 só a FACTA digita.
- Unidades novas na Fase 2: «núcleo de PII» (mascara, segredos, cifra, scrubber, observabilidade, protecao, saida, segredo, api/logs), «tempo» (relogio, calendario), e a API lista os 14 arquivos de `api/`.

**§7 corrigido**
- Opções de ritmo: (D) revisão completa sobre código congelado a partir de 18/11 18:00, CRÍTICO/ALTO até 25/11 12:00; (E) just-in-time por deploy. O dono mandou rodar a completa agora; os achados valem para os SHAs do manifesto e são reconferidos no congelamento.
- Teto 04/12 não se reabre; em aberto só o degrau de 1 dia ou piloto até 02/12.

**§7b corrigido:** D-09 = só «exigir PR». Ata A1.10 não destrava textos. Cookie do RPA é do Danilo. Lista única de 15 perguntas (13 ChatGuru, pergunta 4 FACTA). O padrão vigente aceita «custo e latência não medidos»; o contrário é AJUSTAR do Codex. Acrescentar: textos 1º lote 11/11 e 2º lote 13/11 (reemissão é tarefa minha, pendente); tag v0.3.0 12/11; A4.5 Phoenix 11/11 e `pgbackrest info`; limpeza da S2 antes de 16/11.
