# Revisão 1 · B2.4 «pessoas_teste e fixtures do modo duble» (03/11/2026)

Dois repositórios, dois pares de branches, **o mesmo documento nos dois**:

| Repositório | Branch | Commits revisados | Base |
|---|---|---|---|
| `ia-atendimento` (`~/wt-ia/ia-atendimento-b24`) | `feat/b2-4-pessoas-teste` | `f59932c`, `a50c96f`, `d3e5f38` | `origin/feat/b1-5-api-entrada` (`51da2fa`) |
| `bancos-duble` (`~/wt-ia/bancos-duble-a63`) | `feat/b2-4-pessoas-teste` | `ed6d55e`, `7d63f1b`, `3a372ae` | `main` v0.1.2 (`1305152`) |

Revisor adversarial independente (contexto limpo, não escreveu o código). **Só leitura**: este arquivo é a única mudança em cada repositório; mutações, o ensaio do kit contra API falsa, a
cobertura e o wheel rodaram em **cópias** no scratchpad; nada em produção, na VPS ou na S4; sem push. Referências: `docs/DECISOES-B2.4-0211.md` (só existe no `ia-atendimento`),
`ROTEIRO-DE-ACAO.md` l. 773–776 (B2.4) e riscos 92/103, `contratos/08-orquestrador.md` §6, `levantamento/02` e `03`, e a **forma medida** nos fontes (`cliente360-api@origin/main`,
`3rn-api@9b20d44` e `@origin/main`, `c6-api@cfb80d5` e `@origin/main`, `facta-on@origin/main`) e no contrato pinado (`cliente360-web/contrato/cliente360.json`).

## 0. Veredito

**Aprovar com ressalvas: pode seguir para a revisão 2, mas não mergear antes de corrigir R1-01 e R1-02 (ALTO) e de decidir R1-03 a R1-14 (MÉDIO). Nada CRÍTICO.** O que foi pedido ao código
está sólido: nenhuma PII (varredura própria, `varredura.py` e `piiscan`), `FontePessoasTeste` morre em `real|sombra` (3 mutações), `valid_until` é relativo nos dois repositórios, o hash é o
mesmo e as 170 respostas da camada B **e** as 170 do `ia-atendimento` (84 × 2 + 2 «desconhecida») validam 100 % contra o `cliente360.json` real (JSON Schema, 2020-12). O que falha é a **fidelidade onde ninguém
compara com o fonte** (o eco `nao_repagar` do 3RN, `atribuicao.versao`, o par `sem_oferta` sem contrato), a **consistência entre repositórios, que só existe se alguém lembrar de exportar
uma variável**, e a **narrativa do risco 103**: das «quatro travas por código» da `OPERACAO.md`, três existem e a quarta («[TESTE]») é uma função que ninguém chama.

| Severidade | Qtde | IDs |
|---|---|---|
| CRÍTICO | 0 | |
| ALTO | 2 | R1-01, R1-02 |
| MÉDIO | 12 | R1-03 a R1-14 |
| BAIXO | 10 | R1-15 a R1-24 |

**Suítes (rodadas por mim, `bash scripts/check.sh` nos dois, cada um com a variável apontando para o outro):**

| Repo | Resultado | Tempo | Portão |
|---|---|---|---|
| `ia-atendimento` (`BANCOS_DUBLE_PATH`) | `2317 passed, 1 skipped, 3 xfailed` (esperado 2.317: confere) | 146 s | verde: lock, ruff, format, varredura limpa, 0001 OK, 0002 em dia, `pessoas_teste e fixtures/duble em dia` |
| `bancos-duble` (`IA_ATENDIMENTO_PATH`, `DUBLE_REQUIRE_DOCKER=1`) | `638 passed, 6 skipped, 2 xfailed` (esperado 638: confere) | 57 s | verde: ruff, stubs em dia (379 A + 528 B), fidelidade `--estrito`, piiscan 0 achado; **gitleaks ausente (avisa e segue)** |

**Sem as variáveis** o mesmo `check.sh` também sai verde: `ia` pula 1 teste (`test_pessoas_teste.py:318`) e `duble` pula 3 (`:286`, `:297`, `:327`), todos de consistência entre os repositórios
(R1-02).

**Cobertura real** do pacote `pessoas_teste` (`sys.monitoring`, linha; 65 testes do `ia`): **89,5 %** (512/572); sem `__main__.py` (51 linhas, coberto só por subprocesso, que a medição
em processo não vê) **98,3 %** (512/521). Faltam: `arquivo.py:49,54,55,57` (B1.5), `catalogo.py:95`, `fixtures_duble.py:41,85`, `formas.py:124,144`. Ramo não medido. No `duble`, a camada B é
coberta por testes de docker (170 stubs lidos de verdade no WireMock).

**Mutação (18 mutantes em cópias fora dos repositórios):** 15 mortos, 1 equivalente (M4b), 1 recusa parcial (M3b) e **1 sobrevivente que é o achado R1-02** (M2): o drift de CPF num só
repositório passa nos dois portões sem as variáveis. Tabela em §4.

## 1. As seis perguntas do pedido

1. **PII e fantasma de venda.** Nenhuma PII. 84 CPFs, todos `000.000.0nn` com DV válido (6 CPFs compartilhados por 45 personas, R1-09), nomes do corpus (sobrenomes fictícios), telefones
   `5500 9000-00nn`, UUID `00000000-0000-7000-8000-…`. Greps próprios nos dois diffs (CPF formatado e de 11 dígitos fora de `0000000…`, e-mail, `55…` fora de `55009000`) só acham: um CPF de
   exemplo clássico num teste negativo (`test_pessoas_teste.py:260`, na lista de CPFs sintéticos permitidos de `varredura.py:~40`), um (um `.invalid` usado como operador nos testes de API e um `@y.test` num teste negativo).
   `piiscan` nos arquivos tocados do `ia`: 3 achados, nenhum dado real (o CPF do teste acima e dois do CHANGELOG da B1.x); no `duble`: 0. `FontePessoasTeste` **nunca** serve em
   `real|sombra`: mutações M1a/M1b/M1c morrem (§4). `chats_teste` só aceita chat com pessoa em `pessoas_teste` e `PUT` só da TI com registro: **provado** (M4a/M4c morrem; os 403 de
   `n8n_braco`, `c360_api` e `vigia` valem). Furos reais: R1-06 (histórico `duble` não barra), R1-05 («[TESTE]» não está ligado), R1-21/R1-22.
2. **Forma fiel.** Pydantic estrito + o teste de deriva não bastam; fiz a prova independente (JSON Schema do `cliente360.json` real): **0 falhas em 170 respostas do `ia` e 0 em 170 stubs do
   `duble` renderizados**. Mas o contrato não é o comportamento. Comparando com o **código** que monta as respostas: campos **inventados** = `atribuicao.versao: 1` (real: `0`, R1-03),
   `status_atendimento: null` no T1 (a allowlist real tem 5 chaves e não a inclui, R1-15); **ausentes** = o eco `nao_repagar` do 3RN (R1-01), as chaves `null` que a projeção real sempre
   emite na `Oferta` (R1-15) e `pessoa_id:null`/`atribuicao:null` no «não encontrado» (R1-16); **impossível no real** = o par `sem_oferta` sem contrato (R1-04). `valid_until` relativo é
   recalculado a cada leitura nos dois lados e **nunca** persistido fixo no que é servido; o exemplo `cliente360_oferta.json` guarda instantes fixos de propósito (R1-13).
3. **Consistência entre repos.** O hash é o mesmo e o teste cruzado **falha** se uma pessoa mudar de CPF só num lado (M2, M3a), mas **só com a variável**: sem ela os dois repositórios
   passam sozinhos com o drift (R1-02). O `atualizar_pessoas_teste.py` recusa hash divergente (M3b), mas aceita JSON+hash adulterados juntos (só confere consistência interna).
4. **Kit.** `--ensaio`/`--confirmo` exclusivos e obrigatórios, token 0600 e fora do argv, duas fases, registro (`publicado_por`, `motivo`): tudo confere (ensaio contra API falsa, §3.8).
   O que trava a TI e o que o ensaio não prova: R1-08.
5. **bancos-duble.** 170 stubs, todos `metadata.evidencia = HIPOTESE` (168 `pessoa-de-teste` + 2 `desconhecida`). Camada B responde «não encontrado» como o 360 (`itens: []` correto para
   `pessoas:resumos`, que **omite** id desconhecido; `encontrado:false` com chaves a menos, R1-16). `atualizar_pessoas_teste.py` recusa hash divergente. Rotas fora do contrato do 360: R1-11.
6. **Qualidade.** Módulos ≤ 275 linhas, nenhuma função > 40 linhas; mutações em §4; pendências em §5; emenda do §6 em §6.

## 2. Achados

Legenda das provas: «scratch» = `/tmp/claude-1001/-opt-claude/c3edfc59-52d9-4e44-8d0b-adab74392dfc/scratchpad/rev-b24/`. Scripts em `scratch/provas/`; cópias para mutação em `scratch/mut/`.

### 2.1 ALTO

| ID | Sev. | Arquivo:linha | O que acontece | Como provar | Correção proposta |
|---|---|---|---|---|---|
| R1-01 | ALTO | `pessoas_teste/formas.py:184-211` (`Calcular3rnCalculado`, `Calcular3rnSemCalculo`), `fixtures/duble/3rn_calcular.json` caso `sem_simulacao`, `scripts/gerar_pessoas_teste.py` (`fixture_3rn`) | O `3rn-api` **ecoa `"nao_repagar": true` em toda resposta do `/calcular` quando o pedido o traz** (`consulta.py`: `calcular` → `_ecoar_nao_repagar`, docstring: «o eco é a prova para o chamador de que ESTE 3rn-api entendeu o campo»). `SIM_AUSENTE` **só existe** nesse modo, e é o caso do P14 (D10). A fixture não tem o eco e os modelos são `extra="forbid"`: **recusam a resposta real**, e a fixture do P14 é uma resposta que o servidor nunca produz. O mesmo vale para `regra_id`/`taxa_pedida`/`taxa` (tabela/taxa escolhidas). O `origin/main` do `3rn-api` não mudou o `_calcular` (só `restringir`/`origem`). | `scratch/provas/prova_3rn_eco.py` (`uv run python`): `SIM_AUSENTE+eco RECUSA [('nao_repagar',)]`, `calculado+eco RECUSA`, com tabela `RECUSA [nao_repagar, regra_id, taxa_pedida, taxa]`. Fonte: `git -C ~/repos/3rn-api show 9b20d44:app/routers/consulta.py` (`def calcular`/`_ecoar_nao_repagar`) | Acrescentar `nao_repagar: Literal[True] \| None = None` (e `regra_id`, `taxa_pedida`, `taxa`) aos dois modelos, pôr o eco nos casos da fixture (todos usam `nao_repagar`, é o modo da IA: L10 do levantamento), e um teste que ligue o contrato do 3rn-api (como o do 360) em vez de só o modelo próprio |
| R1-02 | ALTO | `scripts/check.sh` (nos dois); `ia: tests/test_pessoas_teste.py:318-330`; `duble: tests/test_pessoas_teste.py:47-50,286,297,327` | D15 diz que a consistência entre os repositórios é o que protege 84 pessoas × 6 CPFs compartilhados, mas **só roda com `BANCOS_DUBLE_PATH`/`IA_ATENDIMENTO_PATH`**; sem a variável é `skip` e **o portão imprime «OK»** (`-q`, sem `-rs`; `DUBLE_REQUIRE_DOCKER` existe para o docker, nada igual para o outro repositório). O CI do GitHub está parado por cobrança (memória `ci-parado-cobranca`) e, ligado, o do `duble` não enxerga o `ia-atendimento`. Mutação M2 (CPF do P01 muda no corpus e é regenerado só no `ia`): `ia` passa (57 passed, 1 skipped), `duble` passa (12 passed, 3 skipped); com as variáveis os dois reprovam. É o «harness que mente verde» da memória `esperar-condicao-nao-sinal`. | `scratch/mut/rodar.sh` (M2, §4); `uv run pytest -q -rs tests/test_pessoas_teste.py` sem a variável mostra o skip | `check.sh` exigir a variável (`IA_REQUIRE_CROSS=1` como `DUBLE_REQUIRE_DOCKER`) ou achar o irmão por caminho padrão (`../bancos-duble*`); falhar (não pular) se o irmão existe e o teste foi pulado; no `duble`, rodar `atualizar_pessoas_teste.py --verificar <pessoas.json>` quando o caminho existir |

### 2.2 MÉDIO

| ID | Sev. | Arquivo:linha | O que acontece | Como provar | Correção proposta |
|---|---|---|---|---|---|
| R1-03 | MÉDIO | `pessoas_teste/fonte.py:79`; `bancos-duble scripts/stubs_pessoas.py:93`; golden `fixtures/duble/cliente360_oferta.json` | **Campo inventado:** `atribuicao: {versao: 1, site_profile_id: null}`. O 360 real (`rotas/esperado.py:projetar_atribuicao`, origin/main): «pessoa sem atribuição sai `{versao: 0, site_profile_id: null}`»; `versao` é o `esperado` do CAS do handoff. As 84 pessoas sintéticas não têm atribuição, logo o real é `0`. `1` com `site_profile_id` nulo não existe. Quem testar o handoff (B6) contra o dublê usa `esperado=1` e leva `conflito_head` no real | `git -C ~/repos/cliente360-api show origin/main:src/c360api/rotas/esperado.py \| sed -n 107,121p` | `versao=0` nos dois lados (regenerar golden, hash não muda) |
| R1-04 | MÉDIO | `fonte.py:102-107` (`_par` sem oferta); `stubs_pessoas.py:74-87`; `formas.py:110-124` (`contratos` com `max_length=0` na l. 114, só `so_oferta`/`sem_oferta`); `tests/test_pessoas_teste.py:116-122` e `duble tests:258-275` | No 360 real o par só nasce de oferta **ativa** ou de **contrato** (`pessoas_propostas`: `pares` vem de `ofertas_visiveis + contratos`; sem `incluir_historico` a oferta não ativa nem entra). «Sem oferta no 3RN» (P14) e «sem FACTA» (P-M18) são, no real, **o par ausente**; um par `sem_oferta` só aparece com contrato (cancelado, que vira item de `contratos`) ou, com `incluir_historico`, com oferta não ativa: **nunca com `contratos: []` e sem histórico**. As fixtures e os testes consagram o par `sem_oferta` vazio; o caminho real (par ausente) não é exercitado. Os casos `com_contrato`/`varios_contratos` são **impossíveis pelo modelo**, embora o corpus tenha `proposta-viva` (P59), `recusa-contrato-andamento` (P22) e 4 `indet-*` | `git -C ~/repos/cliente360-api show origin/main:src/c360api/rotas/pessoas.py \| grep -n "ofertas_visiveis"` e `_classificar_par` | Gerar P14/P-M18 **sem** o par (ou com um contrato cancelado), manter o `sem_oferta` como variante, e liberar `com_contrato` para as personas de «já tem proposta» quando o B5.2 precisar |
| R1-05 | MÉDIO | `pessoas_teste/prefixo.py:15-26`; `docs/OPERACAO.md:162-166`; nenhum import de `texto_de_saida`/`marcar_teste` fora de `tests/` (grep) | O roteiro e o risco 103 pedem «mensagem de teste prefixada». O que existe é uma **função pura sem chamador** (o `Canal` é B1.6/B6.8). A `OPERACAO.md` §9 afirma «**Quatro travas, todas por código**» e a quarta é «o `Canal` entrega o texto com o prefixo» — não é código, é intenção. O teste `test_mensagem_de_teste_prefixada_TESTE` prova a função, não o aceite. Detalhes da função: `texto_de_saida("teste", "")` devolve `"[TESTE] "`; a idempotência é `startswith("[TESTE]")` (um texto que começa com `[TESTES]` ou `[TESTE]x` fica sem prefixo); o «prefixo conta no limite» está só na docstring | `grep -rn "texto_de_saida\|marcar_teste" src` (só definição e `__init__`) | Trocar «todas por código» por «três por código; a quarta liga com o `Canal`», abrir o aceite como pendente no Kan, e travar no `Canal` com um teste que reprove envio em `teste` sem o prefixo |
| R1-06 | MÉDIO | `api/config_rotas.py:133-142` (`_conferir_chats_teste`, `modo IN ('real','sombra')`) | O seed de `modo` é **`duble`**: chat de cliente real que passou pelo orquestrador em `duble` tem atendimento `modo='duble'`, que **não** barra a entrada em `chats_teste` (o contrato §6 também só cita `real\|sombra`). Chat com histórico `real`/`sombra` ⇒ 422 `chat_de_cliente`; com histórico `duble` ⇒ **200**. A trava (3) (`pessoa_id ∈ pessoas_teste` na entrada) segura a conversa, mas a trava (1) deixa de ser o que a `OPERACAO.md` descreve | `scratch/provas/test_rev_duble_cliente.py` (cópia): `MODO real -> 422 chat_de_cliente`, `sombra -> 422`, `duble -> 200` | Barrar também atendimento `duble` cujo `pessoa_id ∉ pessoas_teste` (o `duble` do harness usa pessoas do catálogo); emendar o contrato §5.6 |
| R1-07 | MÉDIO | `fixtures_duble.py:125-133` (`_servir`); `fixtures/duble/3rn_calcular.json` `padrao: calculado`; `tests/test_fixtures_duble.py:200-206` | O padrão do 3RN é um **cálculo bem-sucedido (R$ 3.500 em 48x) para qualquer persona e qualquer CPF** (D10). O 3RN real, no modo `nao_repagar`, sem `trn.sim` devolve `SIM_AUSENTE`; a persona sem par 3RN (todas menos P14) deveria cair em `SIM_AUSENTE`, não num número inventado. Nem a persona nem o CPF são conferidos (`_servir` aceita qualquer 11 dígitos, inclusive CPF real: só o modo barra). O C6 não tem o problema (padrão `sem_oferta`) | `fixtures.calcular_3rn("P01", "<11 dígitos>", "duble")` ⇒ `(200, {success: True, valorFinanciado: 3500.0, …})` | Inverter: padrão `sem_simulacao`; `calculado` só para persona com par 3RN ativo; exigir CPF `000.000.0nn` |
| R1-08 | MÉDIO | `~/retomada-2809/fila-2910/ia/config/chats-teste.sh:117` (corpo do `PUT`), `:23-25`, `:24` | (a) `aplicar` envia **só os chats dos `--par`** (`"valor": chats`): **substitui** a lista, sem ler o `valor` vigente (lê só `versao`) nem mostrar diferença; `limpar` (o «desfazer» impresso) vai a `[]`, não restaura a lista anterior. (b) `IA_REPO` padrão `~/repos/ia-atendimento` é a `main` de 24bc524, **sem** o pacote `pessoas_teste` (`gerar` falha até o merge; ver `ls src/ia_atendimento/pessoas_teste*` ⇒ inexistente) e `~/ia-segredos/token_ti` não existe nesta máquina. (c) `motivo` padrão `chats_teste_ensaio` serve a uso real (o registro mente). (d) `PUT` por HTTP puro (dentro da WireGuard). (e) o kit mora fora do repositório, sem teste e sem `shellcheck` (`bash -n` ok). **O ensaio contra API falsa prova** o fluxo de controle (flags, token 0600/sem argv, GET→PUT, corpo, ramos 200/422/409, nada do token nos logs); **não prova** autorização real, `LoginOuEmail`, nem a semântica de substituição | `scratch/kit/` (`fake_api.py` + `api-*.log`): corpo observado `{"valor": [2 chats], "por": …, "versao_esperada": 3}` com a lista vigente de 1 chat; `limpar` ⇒ `valor: []` | Mesclar (`valor` vigente ∪ pares) com `--substituir` explícito e imprimir antes/depois; `desfazer` guardar a lista anterior; `IA_MOTIVO` obrigatório; versionar o kit com um teste `bats`/contra o app em processo (o `test_pessoas_teste_arquivo_gerado_pelo_kit_vale_no_boot_real` cobre só o CLI) |
| R1-09 | MÉDIO | `catalogo.py` (docstring l. 11-13); `DECISOES D4`; pendências 5 e 6 | **45 das 84 personas dividem 6 CPFs** (`…002` ×14, `…001` ×10, `…004` ×9, `…003` ×8, mais dois pares). O estado do dublê da FACTA é por CPF (`scenario`): F3 em paralelo, ou duas personas do mesmo CPF seguidas sem `reset`, vê a proposta de uma na outra (a `proposta-viva`, `conferir`, `por-cpf`). A pendência 6 cita «ex.: P34»; medido: **das 41 personas com oferta FACTA e persona `aprovado-N`, 23 têm prazo da oferta (T3) ≠ prazo do dublê (T5/T7)** (P34, P48, P52, P56–P58, P-M05–P-M17, P-M19–P-M21, P-M24) — a F3 verá oferta de 36x e cálculo de 24x como regra, não exceção | `scratch/provas/contagem_cpf_prazo.py <pessoas.json>` | Exigir `scenario.py reset` por persona no harness (B8.1b), um CPF por persona onde o estado importa (a faixa `…0nn` comporta 99), e decidir (dono) se prazo T3 ≠ T5 é desejado |
| R1-10 | MÉDIO | `bancos-duble scripts/stubs_pessoas.py:28-29` (`VALIDADE`/`CRIADA` fixos em 2 h/15 min); `fonte.py:51,67-74` | P51/P52 (`oferta_vence`) e «a versão mudou» precisam de oferta que **vence** durante a conversa. No `ia`, `validade=` e `versao=` existem (só no harness em processo); na **camada B (WireMock) são fixos**: todo `GET` devolve `agora + 2 h`, `versao: 1`, e o roteiro B2.2 diz «F3 roda só na camada B». Com `valid_until` recalculado a cada leitura, avançar o relógio nunca vence a oferta | `grep -n "2 hours" scripts/stubs_pessoas.py`; `test_valid_until_e_agora_mais_2h_a_cada_resposta` consagra o +2 h | Cenário por persona no WireMock (`Scenarios`/`cenario.py`) para P51/P52 (validade curta, `versao: 2`), ou documentar que `oferta_vence` só roda no harness em processo |
| R1-11 | MÉDIO | `bancos-duble scripts/stubs_pessoas.py:22,98-116`; `DECISOES D14` | A camada B serve `GET /c360-duble/v1/pessoas/{id}/resumo\|propostas`, rotas que **não existem** no 360 (real: `POST /pessoas:resumos` por `pessoa_ids`, `POST /pessoas:propostas` por `cpf`). O gateway terá um adaptador só do dublê; o caminho real (método, corpo, cabeçalhos, erros 502/422) **nunca é exercitado antes de `sombra`**. A justificativa de D14 («o 360 real é POST …:resumos/:propostas **por CPF**») é falsa para T1: `pessoasResumos` recebe `pessoa_ids`, então a rota real poderia ser espelhada com `matchesJsonPath`. Só T3 (por CPF, compartilhado entre personas) justifica a divergência | `git -C ~/repos/cliente360-api show origin/main:src/c360api/rotas/pessoas.py \| sed -n '/operation_id="pessoasResumos"/,/pedido.pessoa_ids/p'` | Espelhar T1 (`POST /v1/pessoas:resumos` + corpo); para T3, casar por um cabeçalho de teste ou `pessoa_id` no corpo; corrigir D14 |
| R1-12 | MÉDIO | `contratos/08-orquestrador.md` §6 (linha «Ler» de `teste`: «360 real; FACTA no dublê»); `fonte.py:1-12`; pendência 1 | **Contradição interna do contrato**: §6 exige `pessoa_id ∈ pessoas_teste` (sintéticas, que o 360 real não conhece) **e** manda `teste` ler o 360 real. Análise em §6 deste documento: o roteiro está certo (fixtures em `duble\|teste`); a tabela é que está velha. Risco da implementação: o B5.2 que ler a tabela literalmente liga `teste` ao 360 real e T1/T3 voltam vazios para as 84; o que a pendência não diz é que a «correção óbvia» (cadastrar as 84 no 360) escreveria CPF e ofertas inventados em produção | §6 | Emendar a tabela e o §5.6 antes do B5.2; teste de aceite no gateway: `modo_efetivo=teste` ⇒ fonte de fixture, `sombra` ⇒ 360 real mesmo em atendimento nascido `teste` |
| R1-13 | MÉDIO | `fixtures_duble.py:112-116` (`FixturesDuble.cliente360`), `fixtures/duble/cliente360_oferta.json` (`agora_referencia: 2026-11-17T15:00:00Z`), `catalogo.py:177` (`catalogo_padrao`) | O docstring diz que o arquivo é «o que o gateway devolve em `duble\|teste`»; o objeto expõe `casos[...].propostas` com `valid_until` **congelado** (2026-11-17T17:00Z) e **sem guarda de modo**. Servido como está, a oferta vence em 17/11 às 17:00Z, seis dias antes do smoke de 23/11 (exatamente o «oferta velha no arquivo» que D7 diz evitar). O mesmo para `catalogo_padrao()`/`por_pessoa()` (público, sem `ForaDoModoDeTeste`): o «nunca em `real`» vale pela convenção de usar `FontePessoasTeste`, não pela construção | `fixtures.cliente360.casos["P01"].propostas.pares[0].oferta_ativa.valid_until` | Tornar o campo privado ou renomear (`exemplo_golden`), e dizer no docstring que T1/T3 vêm sempre de `FontePessoasTeste` |
| R1-14 | MÉDIO | `tests/test_fixtures_duble.py:37,253-266`; `DECISOES D9` e pendência 7 | O teste de deriva compara **nomes de campos** (modelo ⊆ esquema, `required` ⊆ modelo): não olha tipo, enum, padrão, nem `SnapshotCoeficiente`, `AtribuicaoPropostas`, `AlvoSugerido`. 3RN e C6 **não têm teste de deriva** (a forma foi lida do fonte em commits de 25–27/10; hoje o `_calcular` não mudou, mas nada avisa se mudar). O caminho padrão do contrato é o checkout compartilhado `~/repos/cliente360-web` (pode estar velho; hoje está igual ao `origin/main`) e, ausente, o teste é **pulado**. Minha validação (JSON Schema completo) não depende desse teste: a repliquei em `scratch/provas/validar_360.py` | `python3 scratch/provas/validar_360.py scratch/t1t3.json` ⇒ `falhas: 0 de 170` | Trocar o teste por validação JSON Schema completa do `cliente360.json` (já pinado no web) e ler 3RN/C6 por um «contrato» pinado no repositório |

### 2.3 BAIXO

| ID | Sev. | Arquivo:linha | O que acontece | Correção proposta |
|---|---|---|---|---|
| R1-15 | BAIXO | `fonte.py:62,96-99`; `stubs_pessoas.py:44-52` | O docstring do T1 diz «Sem `nao_perturbe` nem `limite_contratos`» e a saída **traz os dois como `null`** (e `status_atendimento: null`). No real (`pessoa/projecao.py`, allowlist de 5 chaves) as duas primeiras só saem com a flag ligada («null afirmaria "não está no limite"») e `status_atendimento` **não sai**. Na `Oferta`, a projeção real sempre emite `business_date_origem`, `superseded_causa`, `motivo_encerramento*`, `competencia_*`, `origem`, `lead_id` (como `null`); as fixtures omitem | Alinhar o docstring à saída ou ao real; emitir as chaves `null` da `Oferta` |
| R1-16 | BAIXO | `fonte.py:72`; `stubs_pessoas.py:128`; `tests/test_pessoas_teste.py:129`; `duble tests:253` | «Não encontrado» do T3 sai sem `pessoa_id` e `atribuicao` (o real sempre as emite, `null`), e **os testes asseguram a ausência** (`"pessoa_id" not in vazio`) | Emitir `pessoa_id: null`, `atribuicao: null` e trocar o assert |
| R1-17 | BAIXO | `fonte.py:98`, `stubs_pessoas.py:50` | As 84 pessoas leem T1 com `nao_perturbe`, `limite_contratos` e `status_atendimento` nulos: a lógica de bloqueio/limite do B5.2 não tem pessoa que a exercite (o P21 «não perturbe» e o P22 «contrato em andamento» só aprendem isso na etapa 1, o que é defensável, mas sobra nenhuma persona com T1 não nulo) | Duas pessoas extras (ou variantes) com `nao_perturbe` e `limite_contratos` preenchidos |
| R1-18 | BAIXO | `catalogo.py:73`; `tests/test_pessoas_teste.py:206-224` | O modelo valida a faixa do **CPF** (`000.000.0nn`) mas aceita **qualquer telefone** de 12-13 dígitos e qualquer nome; a restrição ao «5500 9000-00nn» e a sobrenomes fictícios vive só no teste. O DV válido (D4, «cobre o spike I25 aberto») aumenta a chance de colidir com CPF real: a premissa «prefixo que nunca é de cliente» (roteiro) não está provada | Validar `5500 9000` no modelo; decidir I25 e, se o dublê não validar DV, usar CPFs de DV inválido |
| R1-19 | BAIXO | `tests/test_pessoas_teste.py:260` | O teste negativo usa um CPF de exemplo clássico (DV válido) que aciona o `piiscan` (está na lista de sintéticos de `varredura.py`, não na do `piiscan`) | Construir o CPF no teste (concatenar) |
| R1-20 | BAIXO | `api/config_rotas.py:41-47` (`PutConfig.por`) | `por` é **autodeclarado**: os 4 tokens de origem não têm identidade de operador, então «registro» prova *o que* e *quando*, não *quem* | Aceitável no MVP; registrar o fingerprint do token ou exigir `por ∈ lista` |
| R1-21 | BAIXO | `api/config_rotas.py:179-181`, `api/atendimentos.py:105-115` | A checagem do `PUT` roda **fora** da transação (TOCTOU com um atendimento `real` criado no mesmo instante); a entrada confere `contem(pessoa_id)`, não `pessoa_do_chat(chat) == pessoa_id` (um chat de teste ligado ao P01 abre com o P-M01) | Mover a conferência para dentro da transação; decidir se o pareamento é estrito |
| R1-22 | BAIXO | `bancos-duble` (sem `docs/DECISOES-B2.4-*`) | O pedido manda ler o documento «nos dois repos»; ele só existe no `ia-atendimento`. No `duble` a decisão está no README/CHANGELOG, mas as pendências 4–7 e 9 não têm casa lá. gitleaks não instalado: nenhuma varredura de segredo rodou (pendência 9) | Copiar as decisões e as pendências do `duble` |
| R1-23 | BAIXO | `fixtures_duble.py:116-123` | `calcular_3rn`/`simular_c6` não recebem prazo nem valor: devolvem sempre o mesmo número (3.500 em 48x; C6 em 24/36/48/60 fixos). A F3 não consegue «ajustar o prazo» nem exercitar `validar_prazo_tabela` (`REPROVADO` com `prazosDisponiveis`) | Parametrizar por prazo/valor quando o B5.2 definir o T5 |
| R1-24 | BAIXO | `fonte.py:74,107,110`; `pyproject.toml` | `business_date` é o dia em SP e `criada_em` = agora − 15 min: entre 00:00 e 00:15 SP a oferta «nasce» no dia anterior ao seu `business_date`. A versão do `pyproject` segue 0.2.0 com o wheel mudando de conteúdo (declarado, pendência 10) | Usar o dia de SP de `criada_em`; bump na v0.3.0 |

## 3. Provas por pergunta

### 3.1 PII (pergunta 1)
`scripts/varredura.py` ⇒ `varredura: limpa`; `piiscan` (do `duble`) nos arquivos tocados do `ia`: 3 achados (CPF de exemplo em teste negativo, dois em CHANGELOG antigo); `piiscan .` no `duble`: 0.
Greps próprios nos dois diffs (`scratch/diff-ia.patch`, `scratch/diff-duble.patch`): CPF formatado fora de `000.000.0` ⇒ 1 (o do R1-19); 11 dígitos fora de `00000000` ⇒ só `000000nn…` (a faixa); e-mail ⇒ 2 em testes negativos; telefone `55…` fora de `55009000` ⇒ 0.
Lista dos 84 nomes: pseudo-nomes do corpus (primeiro nome comum + sobrenome inventado); nenhum de pessoa pública.

### 3.2 `FontePessoasTeste` em `real|sombra`
M1a (`MODOS_COM_FIXTURES` com `real`), M1b (checagem de modo removida de `_pessoa`), M1c (idem em `_servir`): **mortos** por `test_pessoas_teste_nao_serve_em_real_nem_em_sombra` e `test_fixtures_duble_cpf_eco_e_modo`. A guarda é uma *allowlist* de `str` (modo desconhecido, vazio ou com caixa diferente também levanta): falha fechada. Furo: só a função guarda (R1-13).

### 3.3 `chats_teste` e `PUT`
M4a (sem `_conferir_chats_teste`) ⇒ `test_chats_teste_so_com_pessoa_de_teste` morre; M4c (`c360_api` ganha `chats_teste`) ⇒ morre; M4b (`n8n_braco` em `ORIGENS_QUE_MEXEM_EM_TUDO`) é **equivalente**: a rota já restringe a `{ti, c360_api}` (`api/app.py:145`), são duas camadas.
O registro (`publicado_por`, `motivo`, `publicado_em`, valor) é lido da linha da tabela `ia.config_versao` pelo teste (`test_pessoas_teste_api.py:110-118`).

### 3.4 Forma fiel
`scratch/provas/validar_360.py` valida os 168 + 2 corpos do `ia` e, em `validar_duble.py`, os 170 stubs do `duble` (templates `{{now…}}` renderizados) contra `components.schemas.ResumosPessoas`/`ResultadoPropostasPessoa` do `cliente360.json` (draft 2020-12, `unevaluatedProperties` incluso). O validador morde: campo inventado e `valid_until` removido são recusados. Resultado: **0 falhas / 170 e 0 / 170**.
Comparação com o código (não com o contrato): R1-01, R1-03, R1-04, R1-15, R1-16. C6: `sem_oferta` (404, `success:true`, `status REPROVADO`, `motivo`, `motivo_banco`) e `simulado` (`opcao_selecionada` com as 9 chaves de `extrair_opcoes` + `coeficiente_tabela`, `condicoes_persistidas`, `oferta: null`) **batem** com `simular`/`_resposta`/`classificar` do `c6-api@cfb80d5` (e com o `origin/main`). 3RN `calculado` e `SIM_AUSENTE`/`REPROVADO` batem fora o eco (R1-01).
`convenio: "CLT"` na economia FACTA é medido (`facta-on` grava `PRODUTO = "CLT"` em `cliente360_novo.py:744`).

### 3.5 Hash e consistência
`ia`: `sha256(canônico(pessoas.json))` == `pessoas.sha256` (`test_pessoas_teste_hash_gravado_confere`). `duble`: `sha256(canônico(yaml))` == o `.sha256` (`test_o_yaml_das_pessoas_confere_com_o_hash_gravado`). Cruzado (só com variável): os dois `.sha256` iguais e os JSON canônicos iguais. M2/M3a/M3b em §4.

### 3.6 `valid_until`
Nunca persistido fixo no que se **serve**: `fonte.propostas` soma `agora + validade` a cada chamada (`fonte.py:74`, relógio injetado); a camada B usa `{{now offset='2 hours'}}` (`stubs_pessoas.py:28`); teste de docker lê duas vezes com 2,2 s de intervalo e exige a diferença (`test_valid_until_e_agora_mais_2h_a_cada_resposta`); `test_nenhum_template_…` proíbe instante fixo nos stubs de T3 (D1 morre). O arquivo `cliente360_oferta.json` guarda instantes fixos como *exemplo* e o declara (`relativo`, `agora_referencia`): ver R1-13.

### 3.7 Wheel
`uv build --wheel` numa cópia: o wheel leva `pessoas.json`, `pessoas.sha256`, os 3 `fixtures/duble/*.json`; importado de um diretório de site-packages isolado, `carregar_fixtures_duble()` e `catalogo_padrao()` funcionam (caminho 2 de `diretorio_padrao`).

### 3.8 Kit (ensaio em API falsa local, `scratch/kit/fake_api.py`)
Sem flag ⇒ exit 2; `--ensaio` ⇒ imprime o plano e não conecta; `--ensaio --confirmo` ⇒ recusa; chat/persona malformados ⇒ recusa; token ausente, link simbólico ou 0644 ⇒ recusa; `gerar --confirmo` ⇒ arquivo 0600 com 84 pessoas e 1 chat; `aplicar` ⇒ `GET` (cabeçalho presente, valor do token **nunca** impresso nem logado) e `PUT` com `versao_esperada` = vigente; 422 e 409 ⇒ saída 1 com o código; `limpar` ⇒ `PUT []`. O ensaio **prova** o controle de fluxo e o corpo; não prova a autorização real (R1-08).

## 4. Mutações (cópias em `scratch/mut/`, `scratch/mut/rodar.sh`)

| # | Mutação | Repo | Resultado | Teste que reprova |
|---|---|---|---|---|
| M1a | `real` em `MODOS_COM_FIXTURES` | ia | morto | `test_pessoas_teste_nao_serve_em_real_nem_em_sombra` |
| M1b | checagem de modo removida de `_pessoa` | ia | morto | idem |
| M1c | idem em `_servir` | ia | morto | `test_fixtures_duble_cpf_eco_e_modo` |
| E0 | validade padrão 3 h | ia | morto | `test_valid_until_relativo` |
| E1 | `cpf_mascarado` com dígitos errados | ia | morto | `test_pessoas_teste_gerador_esta_em_dia` (golden); o teste direto não compara a máscara |
| E4 | `alvo_sugerido.tipo = contrato` | ia | morto | idem (só o golden) |
| E5 | nome e telefone trocados em `atributos_cadastrais` | ia | morto | idem (só o golden) |
| E7 | `criada_em` no futuro | ia | morto | `test_valid_until_relativo` |
| E8 | `coef_valor` = `coeficiente_financeiro` | ia | morto | golden |
| M4a | sem `_conferir_chats_teste` | ia | morto | `test_chats_teste_so_com_pessoa_de_teste` |
| M4b | `n8n_braco` em `ORIGENS_QUE_MEXEM_EM_TUDO` | ia | equivalente (rota restringe a `{ti, c360_api}`) | |
| M4c | `chats_teste` para `c360_api` | ia | morto | `test_chats_teste_so_a_ti_mexe_na_lista_e_fica_registro` |
| **M2** | **P01 muda de CPF só no corpus do `ia` (regenerado)** | ia + duble | **passa nos dois sem variável (R1-02)**; com variável reprova nos dois | `test_pessoas_teste_o_hash_e_o_mesmo…`, `test_as_pessoas_sao_as_mesmas…` |
| M3a | CPF editado no YAML do `duble`, `.sha256` intacto | duble | morto | `test_o_yaml_das_pessoas_confere_com_o_hash_gravado` e `gerar_mappings --check` |
| M3b | `atualizar_pessoas_teste.py` com JSON do ia adulterado (hash velho) | duble | recusa (exit 2); com JSON **e** hash adulterados juntos aceita (só confere coerência interna) | |
| D1 | `valid_until` fixo nos stubs (regenerado) | duble | morto | `test_nenhum_template_de_data_…` |
| D2 | sem stubs «desconhecida» (regenerado) | duble | morto | `test_os_stubs_de_t1_e_t3_…` (84×2+2) |
| D3 | `evidencia` ≠ `HIPOTESE` | duble | morto | idem |

## 5. Decisões D1–D16 e pendências 1–10

D1–D3, D5–D9, D11–D13, D15–D16: conferem. D4 (CPF compartilhado, DV válido) ⇒ R1-09/R1-18. D10 ⇒ R1-01/R1-07. D14 ⇒ R1-11. D12 ⇒ R1-05 (a função está correta; o aceite não fecha). A afirmação «não muda a API» (D11) é verdadeira (`git diff` só toca `tests/test_api_revisao1.py` em `tests/`).

| Pend. | Veredito | Esconde defeito agora? |
|---|---|---|
| 1 (emenda §6) | Real, e pior do que descrito: contradição interna do contrato (R1-12) | Sim, para o B5.2 |
| 2 (`Canal`/«[TESTE]») | Verdadeira, mas a `OPERACAO.md` contradiz («todas por código») (R1-05) | Sim, a narrativa do risco 103 |
| 3 (gateway) | Verdadeira: nada chama `FontePessoasTeste` nem `FixturesDuble`; «P13 e P14 rodam» é aceite de unidade | Não |
| 4 (I25) | Aberta; o DV válido é aposta (R1-18) | Não |
| 5 (CPF compartilhado) | **Subestimada**: 45 personas / 6 CPFs (R1-09) | **Sim** |
| 6 (prazo × cenário) | **Subestimada**: 23 das 41 (R1-09) | **Sim, a que mais** |
| 7 (valores inventados; deriva) | Os valores são declarados; a deriva é fraca (R1-14) e o 3RN/C6 não têm | Sim, em parte |
| 8 (kit só em ensaio) | Verdadeira; falta o que o ensaio não vê (R1-08) | Não |
| 9 (gitleaks) | Verdadeira (R1-22) | Não |
| 10 (versão) | Inofensiva (R1-24) | Não |

## 6. A emenda do contrato 08 §6: quem está certo

**A tabela diz** (`teste` × «Ler»): «360 real; FACTA no dublê». **O roteiro (B2.4, spec 1) e a regra do próprio §6** («Chat de `chats_teste` exige `pessoa_id ∈ pessoas_teste`») dizem que a pessoa de um chat de teste é **sintética**, e o 360 não conhece `pessoa_id` nem CPF `000.000.0nn`. As duas frases do mesmo parágrafo não se cumprem juntas.

**Quem está certo: o roteiro (e a implementação).** Ler o 360 real em `teste` devolve `itens: []` / `encontrado: false` para as 84 pessoas: a IA nunca vê oferta, e o ensaio B e o smoke de 23/11 não existem. A única forma de manter «360 real» seria cadastrar as 84 pessoas e ofertas inventadas **no 360 de produção** (CPF e valores falsos em `core.pessoa`/`core.oferta`, nos relatórios, nas comissões e no outbox), o que é pior que o problema.

| Leitura | Risco |
|---|---|
| Tabela (360 real em `teste`) | T1/T3 vazios para as 84 (nada roda); ou, se alguém «resolver» cadastrando as 84 no 360, poluição de produção; ou, se `pessoa_id` real for aceito em `teste`, o fantasma de venda volta (a trava 3 deixa de valer) |
| Roteiro/B2.4 (fixtures em `duble\|teste`) | (a) `teste` deixa de exercitar a **leitura real do 360** (auth, latência, deriva do contrato) antes de `sombra`: a primeira leitura real passa a ser em `sombra`, com cliente real (só leitura) — compensar com um smoke de leitura real do 360 em `sombra` e com a validação do contrato pinado (R1-14); (b) o gateway precisa decidir pela fonte com o `modo_efetivo` (o mais restritivo): um atendimento `teste` com `config.modo = sombra` tem `modo_efetivo = sombra` e deve ler o **360 real** (e achar «não encontrado»), não a fixture — usar `atendimento.modo` serve fixture onde o contrato manda ler real; (c) atendimento de cliente real nascido `duble` (o seed) lê fixture e vê «não encontrado» (inofensivo, mas decisões do `duble` real-tráfego não dizem nada sobre dados) |

**Texto proposto para a tabela** (linha «Ler»): `teste`: «fixtures `pessoas_teste` (T1/T3) para pessoas de `pessoas_teste`; FACTA no dublê; 360 real só para pessoa fora de `pessoas_teste` (que `teste` recusa na entrada)»; `duble`: «fixtures `pessoas_teste` e dublê»; `sombra`: «real, só leitura **sempre**, mesmo em atendimento nascido `teste`». Acrescentar ao §6 uma frase: «a fonte de T1/T3 é decidida pelo `modo_efetivo`, nunca pelo `atendimento.modo`» e, ao §5.6, «`chats_teste` recusa também chat com atendimento `duble` de `pessoa_id ∉ pessoas_teste`» (R1-06).

## 7. O que não revisei
Docker/WireMock além dos testes do próprio `duble` (rodaram com `DUBLE_REQUIRE_DOCKER=1`); B1.5 (já revisada duas vezes) fora das linhas que a B2.4 toca; comportamento do `Canal`, do gateway e do B5.2 (não existem); `gitleaks` (ausente). Cobertura por ramo não medida. Não rodei nada contra a API real, a VPS, o 360 ou os bancos.
