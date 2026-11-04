# Revisão 2 · B2.4 «pessoas_teste e fixtures do modo duble» (03/11/2026)

Dois repositórios, dois pares de branches, **o mesmo documento nos dois**. Esta é a segunda passada, sobre as correções da revisão 1 (`docs/REVISAO-B2.4-0311.md`: 2 ALTO, 12 MÉDIO, 10 BAIXO).

| Repositório | Branch | Commits revisados (correções da r1) | Base |
|---|---|---|---|
| `ia-atendimento` (`~/wt-ia/ia-atendimento-b24`) | `feat/b2-4-pessoas-teste` | `b18d409..d39c4db` (8 commits) | `f59932c..d3e5f38` (r1) sobre `51da2fa` |
| `bancos-duble` (`~/wt-ia/bancos-duble-a63`) | `feat/b2-4-pessoas-teste` | `d12c4d0..2af7562` (5 commits) | `ed6d55e..3a372ae` (r1) sobre `1305152` |

Revisor adversarial independente (contexto limpo; não escreveu o código nem fez a revisão 1). **Só leitura**: este arquivo é a única mudança em cada repositório (a `REVISAO-B2.4-0311.md` da r1 também continua sem commit nos dois: `git status` mostra `??`). Mutações, reversões de commit, o WireMock da camada B e os cenários do kit rodaram em **cópias** ou em contêiner descartável no scratchpad; nada em produção, na VPS, na S4 ou no 360; sem push. Provas em `/tmp/claude-1001/-opt-claude/c3edfc59-52d9-4e44-8d0b-adab74392dfc/scratchpad/rev-b24-r2/` (`provas/` = scripts e os testes de cenário `test_scratch_*_r2.py`; `mut/` = cópias, `lib.sh`, logs; `*-check.log`, `*-sem-var.log`).
Fontes comparadas por mim, de novo: `cliente360-api@origin/main` (`a265fa5`, igual ao remoto hoje), `3rn-api@origin/main` (`3804b95`), `c6-api@origin/main` (`2e43221`) e os pins `cliente360-web/contrato/cliente360.json` e `cliente360-api/src/c360api/contrato/cliente360.json`.

## 0. Veredito

**Pronto para PR: SIM nos dois repositórios, sem CRÍTICO nem ALTO aberto.** Os dois ALTO da r1 estão fechados e a mutação que antes passava (CPF de uma persona trocado só num lado) agora reprova nos dois. Antes do **merge** valem os três MÉDIOS novos, todos baratos: **R2-01** (os `pares` do T3 saem fora da ordem do 360 real, e nenhum teste nota), **R2-02** (a emenda proposta do contrato 08 corrige uma tabela e deixa a outra, e a regra «fonte por `modo_efetivo`» contradiz a «parada dura» do próprio contrato) e **R2-03** (o `gerar` do kit só põe no arquivo os chats que a TI passou, e o `aplicar` em merge e o `limpar` caem em 422 com os antigos).

| Severidade | Qtde | IDs |
|---|---|---|
| CRÍTICO | 0 | |
| ALTO | 0 | |
| MÉDIO | 3 | R2-01, R2-02, R2-03 |
| BAIXO | 10 | R2-04 a R2-13 |

**Portões (rodados por mim, `bash scripts/check.sh` nos dois, cada um com a variável apontando para o outro):**

| Repo | Resultado | Tempo | Portão |
|---|---|---|---|
| `ia-atendimento` (`BANCOS_DUBLE_PATH=~/wt-ia/bancos-duble-a63`) | `2369 passed, 1 skipped, 3 xfailed` (esperado 2.369: confere) | 148 s | verde: lock, ruff, format, varredura limpa, 0001 OK, 0002 em dia, `pessoas_teste e fixtures/duble em dia`. O skip é o PyYAML ausente (`test_corpus_revisao2.py:248`, o teste do `atualizar_duble.py`; ver R2-08) |
| `bancos-duble` (`IA_ATENDIMENTO_PATH=~/wt-ia/ia-atendimento-b24`) | `693 passed, 6 skipped, 2 xfailed` (esperado 693: confere) | 61 s | verde: irmão achado, `pessoas_teste em dia`, ruff, stubs em dia (838 A + 884 B), fidelidade `--estrito`, piiscan 0 achado, **gitleaks ausente (avisa e segue)**. Os 6 skips são `FACTA_ON_REPO` |

**Sem as variáveis o `check.sh` FALHA, com mensagem clara (R1-02 confirmado):** `ia` sai 1 em `exigir_irmao.sh` («!! BANCOS_DUBLE_PATH não está definida … BANCOS_DUBLE_PATH=<checkout do bancos-duble com a B2.4> bash scripts/check.sh»); `duble` sai 1 antes de qualquer etapa («!! IA_ATENDIMENTO_PATH nao esta definida …»). Variável apontando para o lugar errado (`/tmp/naoexiste`) também sai 1 («aponta para um checkout sem a B2.4»). O `pytest` solto sem a variável continua pulando (1 skip no `ia`, 3 no `duble`), por desenho.

**Cobertura (linha, `sys.monitoring`, 99 testes do pacote):** `pessoas_teste` 635/699 = 90,8 %; sem `__main__.py` (51 linhas, só por subprocesso) 635/648 = **98,0 %**. Faltam `arquivo.py:49,54,55,57` (B1.5), `catalogo.py:82,115`, `fixtures_duble.py:44,88`, `fonte.py:117,123`, `formas.py:191,197,231`. Sem ramo.

## 1. Correções da r1: o que foi fechado

Convenção: **FECHADO** = corrigido e o teste reprova quando eu desfaço a correção (mutação em cópia); **PARCIAL** = corrigido em parte; **ABERTO** = deixado de propósito pelo autor.

| r1 | Sev. | Situação | Prova (minha) |
|---|---|---|---|
| R1-01 eco `nao_repagar` do 3RN | ALTO | **FECHADO** | Li `consulta.py` do `3rn-api@origin/main` (`calcular` → `_ecoar_nao_repagar`; `_calcular`: `SIM_AUSENTE` só com `nao_repagar`, `REPROVADO` por prazo com `prazosDisponiveis`, `success:true`/`etapa:"calculo"` no `PROCESSANDO`): os dois modelos, os três casos da fixture e o gerador batem, campo a campo. A `diff 9b20d44..origin/main` não toca `_calcular`/`nao_repagar` (só mensagem de CPF não encontrado). Mutações: eco tirado do `sem_simulacao` (gerador + arquivo regenerados) ⇒ `PessoasTesteInvalidas` ao carregar (validador `_todo_caso_ecoa_nao_repagar`); validador **e** eco tirados ⇒ 4 testes reprovam (`forma_quebrada_e_recusada[SIM_AUSENTE/calculado sem o eco]`, `p14_…`, `outra_persona_cai_no_padrao`) |
| R1-02 portão mente verde | ALTO | **FECHADO** | `check.sh` falha sem a variável nos dois (§0). **Mutação M2 de novo:** CPF de P01 trocado só no `ia` (corpus, snapshot do dublê e `pessoas.json` regenerados, coerente por dentro): `ia` com `BANCOS_DUBLE_PATH` ⇒ `test_pessoas_teste_o_hash_e_o_mesmo_do_instantaneo…` reprova (o hash gravado no `duble`, `d75e07d8…`, ≠ o do `ia` mutado); `duble` com `IA_ATENDIMENTO_PATH` apontando para o `ia` mutado ⇒ `check.sh` sai 1 em «pessoas_teste DIFERE do ia-atendimento». Resíduos: R2-11 (CI) e R2-08 (snapshot do dublê) |
| R1-03 `atribuicao.versao` | MÉDIO | **FECHADO** | `projetar_atribuicao` real: sem atribuição = `{versao: 0, site_profile_id: null}`. Mutação `versao=1` (regenerada) ⇒ 2 reprovam no `ia`; nos stubs do `duble` ⇒ 2 reprovam (`todas_as_pessoas_leem…`, corpo = exemplo do `ia`) |
| R1-04 par sem oferta | MÉDIO | **FECHADO** | P14/P-M18 viram par **ausente**; P59 `com_contrato` com `ContratoNaFoto`. Mutação: P14 volta a ter par 3RN vazio **e** as duas guardas (catálogo e `formas`) removidas ⇒ 4 reprovam. Sobrevivente declarado: tirar só a guarda de `formas.ParPropostasPessoa` (85 passed): é defesa redundante, o catálogo já barra |
| R1-05 «[TESTE]» | MÉDIO | **FECHADO** (documental) | `OPERACAO.md` §9 e `DECISOES` dizem «três travas por código + uma pendente»; conferi no código: trava 3 vale em `POST /atendimentos` **e** `POST /agendamentos` (`agendamentos.py:95` → `modo_do_atendimento`). O aceite do prefixo segue aberto até o `Canal` (B1.6/B6.8); `texto_de_saida` continua sem chamador em `src/` |
| R1-06 histórico `duble` | MÉDIO | **FECHADO** | Revertido o commit `1d1e64d` na cópia ⇒ `test_chats_teste_chat_com_historico_duble_de_cliente_nao_entra…` reprova (`200 == 422`). `modo` tem CHECK fechado em 4 valores (`0001_esquema.up.sql:120`), então a lista `real/sombra/duble` + «`duble` de pessoa de teste não barra» cobre tudo exceto `teste`, que a trava 3 já limita |
| R1-07 padrão do 3RN | MÉDIO | **FECHADO** | Padrão `SIM_AUSENTE`; `_servir` exige o CPF da própria persona. Mutações: padrão `calculado` ⇒ 2 reprovam; `_servir` sem a conferência de CPF ⇒ `cpf_eco_e_modo` reprova. `calculado` ficou sem persona (R1-23) |
| R1-08 kit | MÉDIO | **PARCIAL** | Merge, lista anterior guardada, `limpar` restaura, `--motivo` obrigatório e sem padrão, só WireGuard/loopback, `IA_REPO` com busca, kit versionado com 13 testes contra API falsa: tudo conferido por mim (§5). Continua sem rodar contra a API real. Novos achados R2-03 e R2-12 |
| R1-09 CPF por persona | MÉDIO | **FECHADO** | **Recalculei os 84 DV eu mesmo** (`provas/r1_09.py`): 84 CPFs distintos, todos `000.000.[01]nn` (45 de `0nn`, 39 de `1nn`, nn 1..138), 0 DV errado; 84 telefones `55009000nnnn` distintos; 84 `pessoa_id` distintos. Prazo da oferta FACTA = N do `aprovado-N` (resolvendo `clone_de`) em **41/41**; nenhuma persona do corpus mudou de perfil (só `persona_duble` e CPF: 39 linhas). 39 clones `n` 100..138 com `clone_de`. Mutação sem o sal do `uid` ⇒ `test_nenhum_id_de_stub_tem_cara_de_cpf` reprova. Resíduos: R2-08, R2-10, R2-13 |
| R1-10 oferta que vence | MÉDIO | **FECHADO** | No WireMock vivo (camada B do worktree): `cenario.py set oferta-vence-p51 Vencida` ⇒ `valid_until` 1 min atrás; `NovaVersao` ⇒ `versao 2`; P50/P52 intactas; `reset` volta ao normal. Mutação sem os stubs de cenário ⇒ 2 reprovam |
| R1-11 rotas do 360 | MÉDIO | **FECHADO** | `POST /c360-duble/v1/pessoas:resumos {pessoa_ids}` e `…/pessoas:propostas {cpf}` respondem (curl no contêiner); a rota antiga (`GET …/resumo`) dá 404. Mutação no caminho de T1 ⇒ reprova. Divergências que sobram: R2-09 |
| R1-12 contradição do §6 | MÉDIO | **FECHADO** como proposta; **a emenda tem furos** | Texto de `DECISOES` bate com o código (`FontePessoasTeste` serve só `teste|duble`; §5.6 já implementado). Furos: R2-02 |
| R1-13 golden servível | MÉDIO | **FECHADO** | `FixturesDuble.exemplo_cliente360`; `test_…_o_golden_do_360_nao_e_uma_fonte_servivel` |
| R1-14 deriva | MÉDIO | **PARCIAL** (aberto no que importa) | Ver §4. A deriva por nomes cobre `Contrato`/`ContratoNaFoto`, mas lê o pin velho do web (R2-06) |
| R1-15 chaves nulas | BAIXO | **PARCIAL** | T1 e `Oferta` corretos (mutação: `status_atendimento` de volta ⇒ reprova). Sobram `atributos_cadastrais.link_chat` e o `Contrato` (R2-04, R2-05) |
| R1-16 «não encontrado» | BAIXO | **FECHADO** | Teste compara o dict inteiro; confere com a rota real |
| R1-17 persona com `nao_perturbe`/`limite_contratos` | BAIXO | **ABERTO** (deixado) | Sem persona que exercite os ramos não nulos do T1. Não esconde defeito hoje (B5.2 define) |
| R1-18 telefone | BAIXO | **FECHADO** | O modelo exige `^55009000[0-9]{4}$`; mutação (padrão livre) ⇒ reprova |
| R1-19 CPF de exemplo | BAIXO | **FECHADO** | Montado por concatenação. Varri os dois repositórios por AST (concatenação e f-string constante): só aparecem CPFs de exemplo públicos (§3) |
| R1-20 `por` autodeclarado | BAIXO | **ABERTO** (deixado) | Limite do MVP. O kit só valida o formato de `--por` |
| R1-21 TOCTOU e pareamento | BAIXO | **ABERTO** (deixado) | Conferi o código: `PUT` confere fora da transação; a entrada compara `contem(pessoa_id)`, não `pessoa_do_chat`. Não esconde defeito da B2.4 |
| R1-22 DECISOES no `duble` | BAIXO | **FECHADO** | Cópia com cabeçalho próprio; o resto igual ao do `ia`. Sem teste que mantenha as cópias iguais |
| R1-23 T5 sem prazo/valor | BAIXO | **ABERTO** (deixado) | **Esconde defeito**: ver §6 |
| R1-24 `business_date` / versão | BAIXO | **PARCIAL** | `business_date` = dia de SP de `criada_em`: mutação reprova `test_valid_until_relativo`. O bump do `pyproject` fica para a v0.3.0 (declarado) |

## 2. Achados novos

Legenda das provas: «scratch» = o diretório acima.

### 2.1 MÉDIO

| ID | Sev. | Onde | O que acontece | Prova | Correção proposta |
|---|---|---|---|---|---|
| R2-01 | MÉDIO | `pessoas_teste/fonte.py` (`propostas`/`_par`, ordem do catálogo); `bancos-duble scripts/stubs_pessoas.py` (`corpo_propostas`) | O 360 real devolve os pares **ordenados** por `(banco, produto)` (`pessoas_propostas`: `for (banco, produto), grupo in sorted(pares.items())`). As fixtures devolvem na ordem do catálogo: P13, a única persona com dois pares, sai `[FACTA, C6]`; o real sairia `[C6, FACTA]`. O JSON Schema não vê ordem (0 falhas), o teste do `ia` **fixa a ordem errada** (`[p.banco for p in pares] == [par.banco for par in pessoa.pares]`) e o do `duble` compara com o mesmo corpo. Exatamente o par onde a escolha de banco do B5.2 importa | Mutação (pares de P13 em ordem inversa, regenerada): 85 passed no `ia`. `provas/cross84.py`: 168/168 corpos iguais entre `ia` e WireMock, com a mesma ordem. Fonte: `git -C ~/repos/cliente360-api show origin/main:src/c360api/rotas/pessoas.py \| grep -n "sorted(pares"` | Ordenar por `(banco, produto)` na fonte e no stub e trocar o assert por «igual a `sorted`»; regenerar os dois repositórios (o hash muda) |
| R2-02 | MÉDIO | `docs/DECISOES-B2.4-0211.md` «Proposta de emenda» vs `contratos/08-orquestrador.md` §6 | (a) **Há duas tabelas «Ler»** em §6 (a de `modo_efetivo × efeito` e a «Tabela final» v2.1); a emenda fala em «a linha «Ler» da tabela de §6» e não diz que as duas mudam. (b) **«A fonte de T1/T3 é decidida pelo `modo_efetivo`» contradiz a parada dura:** atendimento nascido `real` com posse real sob `config.modo = duble` tem `modo_efetivo = duble` (ordem real > teste > duble > sombra, menor vence), e a Tabela final manda ali «Ler: real, só leitura». Seguir a nota do B5.2 serve a fixture (e «não encontrado») a cliente real justamente na parada dura. A regra precisa da posse real, que `FontePessoasTeste` não conhece. (c) Em `teste` a tabela diz só «FACTA no dublê»; as fixtures de 3RN e C6 só servem em `duble|teste` (`ForaDoModoDeTeste`) e a emenda não as menciona: lida ao pé da letra, `teste` chamaria o C6 real (1 req/s, custo) com CPF sintético. (d) A mesma regra de `chats_teste` («`real\|sombra`») está também na tabela de erros (§2, linha `chat_de_cliente`) e no nome do teste em §14, fora de §5.6 | Leitura de `08-orquestrador.md` l. 186–207 e 65, 174, 349 | Reescrever a emenda em duas partes: tabela 1 e Tabela final; «fixtures (T1/T3, 3RN, C6) quando `modo_efetivo ∈ {teste, duble}` **e sem posse real**; com posse real sob parada dura, real só leitura»; `sombra`: real. Incluir §2 e §14 na lista de pontos a emendar |
| R2-03 | MÉDIO | `kits/chats-teste.sh` (`gerar`), `docs/OPERACAO.md` §9 | `gerar` monta o `PESSOAS_TESTE_ARQUIVO` só com os `--par` desta chamada. O `aplicar` em **merge** valida a lista **inteira** contra o arquivo lido no boot: quem gera o arquivo só com o chat novo, reinicia e aplica toma `422 pessoa_fora_de_pessoas_teste` pelos chats antigos, e o `limpar` (restaurar a lista anterior) também. O README e a mensagem do kit mandam «reiniciar» e não dizem «passe TODOS os pares vigentes»; só o `limpar --vazio` escapa | Teste em cópia contra a API real em processo (`provas/test_scratch_api_r2.py`): arquivo com A ⇒ `PUT [A]` 200; arquivo novo só com B ⇒ `PUT [A,B]` **422** e `PUT [A]` **422**. `gerar` real: `chats no arquivo gerado: ['bbbb…']` | `gerar` deve juntar os chats vigentes (GET) ou aceitar `--juntar`; no mínimo, escrever no README e no `--help` que `gerar` precisa de todos os pares |

### 2.2 BAIXO

| ID | Onde | O que acontece | Correção proposta |
|---|---|---|---|
| R2-04 | `fonte.py:138` (`ultima_consulta_em=criada`); `stubs_pessoas.py` (`ultima_consulta_em`); `AtributosCadastraisOferta` | **Campo inventado:** `pessoas:propostas` não emite `ultima_consulta_em` (`projetar_oferta` não o tem; só `propostas:periodo` o repassa). O schema o permite, por isso o 0/336 não o pega, mas um gateway que o leia acha em `duble` o que não existe em `sombra`. **Chave ausente:** a rota real emite `atributos_cadastrais` com as três chaves (`model_dump` de `AtributosCadastraisOferta`, `link_chat: null` incluído); a fixture só tem `nome` e `telefone`. `ciclo: 1` só sai no real com `C360_OFERTA_CICLO` ligada | Tirar `ultima_consulta_em`; emitir `link_chat: null`; documentar a flag do `ciclo` |
| R2-05 | `fonte.py:_contrato_na_foto`; `stubs_pessoas.py:_contrato_na_foto` | `projetar_contrato` real emite **sempre** 17 chaves que o `Contrato` da fixture (P59, a única persona «já tem proposta») omite: `refinamento, confianca, motivo, flags, adicional, valor_contratado, valor_financiado, valor_pago, pago_em, codigo_tabela, prazo_meses, valor_parcela, link_formalizacao, coeficiente, fundida_em_id, substitui_contrato_id, atualizada_em`. Mesma classe do R1-15, só corrigida na `Oferta`. Código que leia `contrato["flags"]` dá KeyError no `duble` e funciona no real | Emitir as 17 chaves com `null`/`[]`/`false` |
| R2-06 | `tests/test_fixtures_duble.py:325-341` | O teste de deriva lê `~/repos/cliente360-web/contrato/cliente360.json`, o **pin** do web (29/10), e não a fonte. Contra o `cliente360.json` do `cliente360-api@origin/main` o teste **reprova hoje**: `Contrato` ganhou `dados_banco`, `nota`, `seguro_recusado_em`, `vendedor_na_contratacao` (opt-in por flag, que `pessoas:propostas` não liga). Ou seja: passa porque o pin está velho, e quebra no próximo re-pin do web sem defeito real. Segue pulado se o arquivo faltar e **fora** do que `PESSOAS_TESTE_EXIGE_IRMAO` exige | Ler o contrato da API (ou fixar uma cópia no repositório, com hash), e trocar a igualdade de `Contrato` por «os 10 `required` + os que a rota liga» |
| R2-07 | `scripts/atualizar_pessoas_teste.py` (`CABECALHO`, grava o cabeçalho de `personas/pessoas_teste.yaml`); `scripts/pessoas_teste.py:4` | Texto **obsoleto depois do R1-09**: diz «mesmo CPF sintético `000.000.0nn-dd`» e «várias personas da F3 dividem o mesmo CPF porque dividem a persona do duble», o contrário do que a revisão decidiu. Quem abrir o YAML lê que CPF compartilhado é intencional. (O `ROTEIRO-DE-ACAO.md` l. 243 ainda diz «170 stubs na camada B»; são 175.) | Trocar o texto e regravar o YAML (o hash não muda: ele cobre o JSON) |
| R2-08 | `tests/corpus/duble_personas.json` (`ia`); `scripts/atualizar_duble.py` | O snapshot do `personas.yaml` do dublê dentro do corpus do `ia` (que valida `cpf_alinhado_duble`, `gabarito_cenario_duble`, `holdout_independente`, agora com os 39 clones) **não é conferido por nenhum portão**: `atualizar_duble.py --verificar` não está no `check.sh` de nenhum repositório e o único teste do script é o skip de PyYAML. A `fonte` do arquivo diz `@1305152+B2.4-R1-09`, que não é um commit. Conferi à mão (`atualizar_duble.py --verificar` com o python do `duble`): **em dia hoje** | `--verificar` no `check.sh` do `duble` (que tem PyYAML) apontando para o `ia`, ou PyYAML no venv de desenvolvimento do `ia`; gravar o hash real do commit na `fonte` |
| R2-09 | `stubs_pessoas.py` (`desconhecidas`) | T1 real aceita 1 a 200 ids e **omite** o desconhecido; o `duble` responde **422** a 2 ou mais ids (declarado, D14) com corpo próprio (`{"erro":{"codigo":"lote_nao_suportado_no_duble"}}`), que não é o `Problema` do 360. Também respondem 200 vazio o que o real recusa com 422: lista vazia, id mal formado, CPF com menos de 11 dígitos. Provado no WireMock vivo. O gateway da IA pergunta por uma pessoa, então não bloqueia; fica sem como exercitar o ramo 422 real | Documentar na `OPERACAO.md` e, se o B5.2 precisar do 422, um stub por padrão de corpo |
| R2-10 | `anonimizador/duble_anon/sinteticos.py` | O anonimizador sorteia em 1..99 (`PERSONA_MAX`) e os clones ocupam 100..138 de 100..199; **nenhum teste** impede subir `PERSONA_MAX` (a nota diz que mudar o máximo muda o mapeamento). Se subir a 100+, persona do anonimizador e clone repartem CPF `000.000.1nn` e os stubs se sobrepõem | Teste `PERSONA_MAX < min(n dos clones)` |
| R2-11 | `.github/workflows/ci.yml` nos dois | O CI (parado por cobrança) roda `pytest` puro: sem o irmão, os testes cruzados pulam e o CI fica verde. Só o `check.sh` local é estrito | Quando o CI voltar, fazer `actions/checkout` do irmão e exportar a variável, ou `PESSOAS_TESTE_EXIGE_IRMAO=1` com o irmão presente |
| R2-12 | `kits/chats-teste.sh` (`limpar`, `anterior_mais_recente`); cópia em `~/retomada-2809/fila-2910/ia/config/` | (a) `limpar` restaura o snapshot sem comparar com o que o `aplicar` deixou: se outra pessoa acrescentou um chat no meio, ele some (mostra antes e depois, mas segue com `--confirmo`). (b) pega o snapshot de **maior versão** do diretório de estado, e o snapshot não guarda a URL: versão de outro ambiente (ensaio local, por exemplo) vence. (c) A cópia da retomada difere da fonte por **uma linha** de cabeçalho (conferi com `diff`); nenhum teste a mantém igual | (a) recusar se a lista vigente ≠ a que o `aplicar` gravou, a menos de `--forcar`; (b) guardar a URL no snapshot; (c) teste que compare `kits/` com a cópia, ou gerar a cópia no release |
| R2-13 | `corpus/regras/duble.py:eventos_possiveis` | `eventos_possiveis(persona)` sem `corpus` devolve vazio para os 39 clones (o teste consagra: `== frozenset()`); hoje o único chamador passa o corpus | Levantar erro quando a persona for clone e `corpus` for `None` |

## 3. PII e segredos (pergunta 3)

- `scripts/varredura.py` (`ia`): `varredura: limpa`. `piiscan .` (`duble`): 0 achado. `piiscan` do `duble` sobre os arquivos que o `ia` tocou: 14 achados, todos exemplos dentro de testes e da própria `varredura.py` (telefones de exemplo no formato nacional e com `55`, um e-mail e o CPF de exemplo clássico, inclusive o telefone do teste negativo novo do R1-18); nenhum dado real.
- Greps próprios sobre os dois diffs completos (`diff-ia.patch` 7.022 linhas; `diff-duble-full.patch` 59.966 linhas, mapeamentos incluídos): CPF formatado fora de `000.000.[01]nn` ⇒ 0; 11 dígitos fora de `000000[01]` ⇒ 2 no `duble`, **os dois com DV inválido**; e-mails ⇒ `operador.teste@glcapital.invalid`, `x@y.test`, `personaNNN@example.invalid`; `55…` fora de `55009000` ⇒ 0. O kit: só o IP da WireGuard (`10.90.0.5`) e o caminho do arquivo de token, nenhum valor.
- **Concatenação e f-string (AST, `provas/pii_ast.py`)** nos dois repositórios: 9 achados no `ia` e 3 no `duble`, todos conferidos: o CPF de exemplo público que a `varredura.py` já lista, montado em `test_fixtures_duble.py:272` e `test_pessoas_teste.py:330`, e outro exemplo público (prefixo 390) em `test_varredura.py` (pré-existente, teste do próprio scanner), e-mails de teste negativo, e o fragmento de uuid `…-7291`+`3764320a` do `duble` (o falso positivo do piiscan, montado de propósito). **Nenhum CPF de exemplo escapa por concatenação.**
- **Sal do `uid`:** `uid` refaz o uuid5 até o id não conter 11 dígitos de CPF válido; só altera ids de stub (a ordem dos demais não muda) e nunca toca valor de pessoa. Não esconde nada: o piiscan e minha varredura passam por cima de todos os ids. A reversão (sem sal) é pega por `test_nenhum_id_de_stub_tem_cara_de_cpf`. Um falso positivo desses é, por acaso, um número DV-válido que poderia ser de alguém: por isso é melhor refazer o id do que isentá-lo.
- **Allowlist `000.000.[01]nn` sem gitleaks:** a regra `cpf-formatado` só olha CPF **formatado**; a allowlist `^000\.000\.[01]\d{2}-\d{2}$` é ancorada em `regexTarget = "match"` e limitada a `targetRules = ["cpf-formatado"]`; os testes de regex dão `liberado(0nn)`, `liberado(1nn)`, `not liberado(2nn)`. O gitleaks **não rodou em lugar nenhum desta árvore** (nem aqui, nem no CI parado). A faixa liberada (000..199, 200 números) é maior que a usada (1..45 e 100..138); sobram 61 livres em 139..199.
- Nomes: os 84 são nome comum + sobrenome inventado; nenhum de pessoa pública.

## 4. Forma fiel, por minha conta (pergunta 2) e o resíduo do R1-14

**Contra o contrato (JSON Schema 2020-12 completo, `unevaluatedProperties` incluso):** as 84 respostas T1 e as 84 T3 da `FontePessoasTeste` **e** as 168 respondidas pelo WireMock vivo (camada B), validadas contra o contrato do `cliente360-api@origin/main` **e** contra o pin do web: **0 falhas em 672 validações**. Mais: **168/168 corpos iguais** (a menos de instante/data) entre `FontePessoasTeste` e o WireMock, nas 84 pessoas (o teste do próprio `duble` só compara 5).

**Contra o código que monta a resposta (o que o schema não vê):**

| Campo / regra | T1 (`pessoas:resumos`) | T3 (`pessoas:propostas`) | Situação |
|---|---|---|---|
| Chaves de `PessoaResumo` | `pessoa_id, nome, cpf_mascarado, cpf, vendedor` sempre; `nao_perturbe`, `limite_contratos` só com as duas flags (as fixtures as emitem `null`, premissa declarada) | | confere; `status_atendimento` não existe e não sai |
| Topo de `ResultadoPropostasPessoa`, «não encontrado» | | `encontrado, pessoa_id, atribuicao, varias_ofertas, pares, lido_em`; sem pessoa: `pessoa_id`/`atribuicao` nulos | confere; `atribuicao {versao 0, site_profile_id null}` confere |
| Ordem dos `pares` | | real: `sorted((banco, produto))` | **diverge (R2-01)** |
| `Oferta`: chaves sempre emitidas, `economia`, `coeficiente` (sem `coef_base`/`coef_zona_negocio`, opcionais), `estado`, `business_date_origem` | | | confere |
| `Oferta.ultima_consulta_em`, `ciclo` | | real não emite o primeiro; o segundo só com `C360_OFERTA_CICLO` | **diverge (R2-04)** |
| `atributos_cadastrais.link_chat` | | real emite `null` | **diverge (R2-04)** |
| `Contrato` (P59) | | real: 31 chaves sempre; fixture: 14 | **diverge (R2-05)** |
| `ContratoNaFoto`, `caso`, `alvo_sugerido`, `terminal`, `consome_oferta_ativa` | | | confere |
| 3RN `calcular`: sucesso, `SIM_AUSENTE`, `REPROVADO` por prazo, `PROCESSANDO`/`ERRO`, eco `nao_repagar` | | | confere com `consulta.py` e `erros_3rn.py` (`origin/main`); o eco também vai nos 400 de validação, que a fixture não modela (fora do caminho) |
| C6 `simular`: `sem_oferta` (404, `success:true`), `simulado` (9 chaves de `extrair_opcoes` + `coeficiente_tabela`, `condicoes_persistidas`, `oferta:null`) | | | confere com `simular`, `_resposta`, `envelope.desfecho` e `sim_client.extrair_opcoes` (`origin/main`). O `result` do modelo cobre 4 dos 27 do `RESULTADOS`; os outros não têm fixture |

**R1-14: quanto drift isso deixa passar?** O teste de deriva compara só **nomes** de propriedade e `required` de 11 schemas, sem tipo, enum, `pattern`, `minimum`/`maxLength`, `oneOf`; não olha `SnapshotCoeficiente`, `AtribuicaoPropostas` nem `AlvoSugerido`; e lê o pin do web, que já está atrás da API (R2-06). 3RN e C6 **não têm** teste de deriva: a forma foi copiada do código em `9b20d44`/`cfb80d5` e eu a reconferi hoje contra `3804b95`/`2e43221` à mão. O que passaria calado: um valor novo em `Oferta.estado`/`Contrato.macro`, um `pattern` novo em `DecimalMoeda`, `convenio` com outro `maxLength`, qualquer campo novo do 3RN/C6. Hoje o drift real é **zero** (672 validações), mas a proteção contra o amanhã é fraca. Custo do conserto: `jsonschema` como dependência de desenvolvimento (existe no Python do sistema desta máquina; mexe no `uv.lock`).

## 5. Kit `kits/chats-teste.sh` (pergunta 4)

- **Cópia vs fonte:** a de `~/retomada-2809/fila-2910/ia/config/` difere por **uma linha** (o cabeçalho «CÓPIA de kits/…»); nenhum teste as mantém iguais (R2-12c). `bash -n` ok; sem `shellcheck` nesta máquina.
- **Conferido (por mim, na cópia da retomada e nos 13 testes do `ia`):** `--ensaio` imprime o plano e não abre conexão; `--ensaio --confirmo` e nenhum dos dois são recusados (exit 1 e 2); sem `--motivo` ⇒ recusa com a regra `[a-z0-9_]{1,40}`; URL fora de `10.90.0.5`/`127.0.0.1`/`localhost` ⇒ recusa («o token da TI viajaria em HTTP puro»), com `IA_API_FORA_DA_WG=1` como saída explícita (a regex é ancorada: `localhost.evil.com` não passa); `limpar` sem lista guardada ⇒ «use `--vazio`»; `gerar --confirmo` fora de qualquer checkout ⇒ «defina `IA_REPO`» (exit 1, nada gravado). O token vem de arquivo 0600 (não link) e vai a um arquivo temporário de cabeçalho, nunca ao argv.
- **Merge e restaurar:** `aplicar` acrescenta e guarda `anterior-<versão>.json` (0600, diretório 0700); `--substituir` troca tudo e também guarda; `limpar` desempilha na ordem inversa; `--vazio` zera.
- **O que a TI faria errado seguindo o README:** R2-03 (gerar só com os chats novos), R2-12a/b (restaurar por cima de mudança de terceiro ou de outro ambiente). Além disso, a cópia da retomada só acha o checkout com a B2.4 em `~/repos/ia-atendimento` (a `main`, **sem** o pacote, até o merge) ou em `~/wt-ia/ia-atendimento-b24` (só esta máquina): em outra máquina o `gerar` exige `IA_REPO`, e o README (`OPERACAO.md` §9) não lista isso entre os pré-requisitos.

## 6. Os deixados R1-14/17/20/21/23/24: qual esconde defeito agora?

| ID | Esconde defeito? |
|---|---|
| R1-14 | **Sim, em potencial** (§4): a deriva futura passa calada e o teste já está atrás da fonte |
| R1-23 | **Sim.** `calcular_3rn`/`simular_c6` não recebem prazo nem valor, então o caso `prazo_indisponivel` (o `REPROVADO` com `prazosDisponiveis`) é **inalcançável** pelo gateway, e o `calculado` do 3RN também (`por_persona` vazio: ninguém tem par 3RN). A F3 não exercita o sucesso do 3RN nem o recuo de prazo; existem só como dado e como teste da forma |
| R1-17 | Não hoje. O B5.2 define; o T1 do B5.2 (`ROTEIRO` l. 814) ainda lista `status_atendimento`, que `pessoas:resumos` **não emite**: a fixture fiel expõe a contradição, e o B5.2 vai precisar do `GET pessoa`, que não tem fixture em `duble|teste` |
| R1-20 | Não: o registro prova o quê e quando, não quem. Convém não prometer mais que isso na OPERACAO |
| R1-21 | Não esconde defeito da B2.4. A janela do TOCTOU é pequena e a trava 3 segura |
| R1-24 | Não (o `business_date` já foi corrigido; o bump é só versão) |

## 7. `bancos-duble` (pergunta 5)

- **39 clones `n` 100..138** com `clone_de`, mesmo cenário/params/camadas que a base, CPF `000.000.1nn` e `scenario` próprio: `test_clones_de_persona.py` (6 testes) e o `ia` (`test_corpus_clones.py`). 459 stubs novos na camada A, sem aviso de desempenho.
- **Anonimizador 1..99:** o mapeamento dele não mudou (`PERSONA_MAX = 99`, só a função `persona(n, ate=…)` aceita a faixa dos clones). Conflito futuro possível só se alguém subir o máximo (R2-10). As 45 originais já dividiam 1..99 com o anonimizador desde a A6.3 (pré-existente).
- **Rotas respondem como o 360?** Método, caminho e corpo sim (R1-11). Lote de 2+ ids ⇒ 422 **não** é o comportamento real (o real aceita 1..200 e omite o desconhecido); é a limitação declarada do WireMock (R2-09).
- **`cenario.py` P51/P52:** conferido no WireMock vivo (R1-10). O estado é por nome de scenario (`oferta-vence-p51`), então persona nenhuma interfere em outra; `reset` volta tudo a `Started`.
- **Camada B ao vivo:** subi o WireMock 3.13.2 com os mapeamentos do worktree numa porta aleatória (e o removi); T1 por `pessoa_id` e T3 por CPF para as 84, mais o desconhecido, responderam como esperado.

## 8. A emenda do contrato 08 (pergunta 6)

O texto de `DECISOES` bate com o código no que afirma sobre o código: `FontePessoasTeste` só serve em `teste|duble` e levanta `ForaDoModoDeTeste` em `real|sombra`; `chats_teste` recusa `duble` de pessoa fora do catálogo; a trava 3 vale em `/atendimentos` e `/agendamentos`. O risco está no texto que **muda o contrato** (R2-02): duas tabelas, a regra `modo_efetivo` × parada dura, o 3RN/C6 em `teste` e as menções de §2/§14. Consequência já aceita no documento (e correta): `teste` deixa de exercitar a leitura real do 360, então o smoke de leitura real em `sombra` é obrigatório.

## 9. Mutações da revisão 2 (cópias em `mut/`)

| # | Mutação | Resultado |
|---|---|---|
| M1-A | SIM_AUSENTE sem o eco, gerador e arquivo regenerados | morto (validador `_todo_caso_ecoa_nao_repagar`) |
| M1-B | idem + validador removido | morto (4 testes) |
| M1-C | padrão do 3RN = `calculado` | morto (2) |
| Mb | `_servir` sem conferir o CPF | morto (`cpf_eco_e_modo`) |
| Ma / Mc | `real` em `MODOS_COM_FIXTURES` / checagem de modo removida de `_pessoa` | mortos (`nao_serve_em_real_nem_em_sombra`) |
| R1-06 | reverter `1d1e64d` na produção | morto |
| M2 | CPF de P01 só no `ia` | `ia` e `duble` reprovam com a variável; `check.sh` sai 1 sem ela |
| T1 | `atribuicao.versao = 1` | morto (2) |
| T2 | tirar só a guarda de `formas` do par vazio | **sobrevive** (equivalente: o catálogo barra) |
| T2b | P14 volta a ter par 3RN vazio, sem as duas guardas | morto (4) |
| T4 | T1 emite `status_atendimento` | morto |
| T5 | `business_date` = dia de `agora` | morto |
| T6 | telefone livre no modelo | morto |
| **Md** | **pares de P13 em ordem inversa** | **sobrevive (R2-01)** |
| D1 / D2 / D3 / D5 | rota antiga de T1; sem cenário P51/P52; `versao 1`; `uid` sem sal | mortos |
| reversão de commit | `b18d409`, `a0b4594`, `3eda2f2`, `c08dd8a` | mortos |

## 10. O que conferi e está certo

- Os dois `check.sh` verdes com os números esperados (2.369 e 693) e falhando sem a variável.
- `pessoas.sha256` idêntico nos dois repositórios (`cmp`); 84 pessoas, 84 CPFs/telefones/`pessoa_id` distintos, DV recalculado por mim, faixa `000.000.[01]nn`, prazo da oferta = N do `aprovado-N` em 41/41.
- 672 validações JSON Schema sem falha (fonte e WireMock, contrato da API e pin do web); 168/168 corpos iguais entre `ia` e WireMock.
- `FontePessoasTeste` e `FixturesDuble` morrem em `real|sombra`; só respondem pelo CPF da própria persona (mutações).
- 3RN e C6: forma igual ao código de `origin/main`; sem drift desde os commits de origem.
- `chats_teste`: histórico `real|sombra|duble-de-cliente` barra; só a TI grava, com registro; a trava 3 em `/atendimentos` e `/agendamentos`.
- `P51/P52` ao vivo; `valid_until` relativo a cada resposta; `business_date` = dia de SP da criação.
- Nenhuma PII, nenhum segredo (varredura, piiscan, AST, greps); o sal do `uid` não esconde nada.
- Wheel leva `fixtures/` (teste existe e passa).
- Kit: merge, restauração, motivo obrigatório, só WG/loopback, token fora do argv e dos logs.

## 11. O que não revisei

Docker/WireMock além dos testes do `duble` e do contêiner descartável que subi; B1.5 fora das linhas que a B2.4 toca; o `Canal`, o gateway e o B5.2 (não existem); `gitleaks` (ausente); cobertura por ramo; nada contra a API real, a VPS, o 360 ou os bancos. O kit nunca rodou contra a API real (declarado pelo autor).
