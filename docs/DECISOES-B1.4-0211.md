# B1.4 — decisões e pendências (02/11/2026)

Etapa «Contexto do turno, agente `Turno` e observabilidade» (sp01 T6; roteiro B1.4). Branch `feat/b1-4-agente-turno`, da main `24bc524`. Sem rede, sem chave de
provedor, sem S4/VPS/n8n/ChatGuru. Rótulos: **DECISÃO** (escolha minha, revisável) · **HIPÓTESE** (depende de medição) · **PENDENTE** (depende de outra etapa ou do dono).

## 1. O que existe

| Arquivo | Papel |
|---|---|
| `turno.py` | `Turno`, `ACOES_POR_FASE`, ferramentas e TX do modelo por fase, `validar_turno_na_fase` e os erros (`ErroDoModelo`, `AcaoForaDaFase`...), `custo_brl`, `ResultadoTurno` |
| `ferramentas.py` | registro de ferramentas (`{"T3": f}`), `Deps`, capability que projeta e audita o retorno (A-1) |
| `agente.py` | `ResolvedorModelo` (UM `OpenAIChatModel`, Fireworks só-EUA), `criar_agente`, `executar_turno`, `ProvedorFalso`, `ModeloDaFaixa`, `Deps` |
| `contexto.py`, `protecao.py`, `modulos_fase.py`, `tokens.py` | os 8 blocos de H §3.1, o texto fixo do prompt, o estimador de tokens e o corte |
| `roteiro_f3.py` | o roteiro da F3 como resposta do modelo (`ProvedorFalso`) e os exemplos do bloco 2 |
| `observabilidade.py` | OTel → Phoenix, scrubber de span/log, segredos, `trace_id`, alerta de raciocínio |
| `config.py` (acréscimos) | roteador só-EUA, forma de desligar o raciocínio, chamada ao modelo, preços e câmbio, Phoenix |

Testes novos: `test_agente.py`, `test_contexto.py`, `test_observabilidade.py`, `test_ferramentas.py`, `test_timeout.py`, `test_vazamento_corpo.py` (números exatos no relatório da etapa). Os 4 nomeados no roteiro: `test_cpf_e_valores_nao_vao_ao_modelo`, `test_span_nao_contem_cpf`,
`test_raciocinio_desligado_vai_no_extra_body`, `test_um_so_provedor_falha_e_propaga`. Cobertura do código novo ≈ 98% (o projeto não tem `pytest-cov`; medido com `uv run --with coverage`).

## 2. Decisões

**Turno e fase**
- **D1 `Turno` fora de `agente.py`** (`turno.py`, puro): o contexto, o roteiro e o agente o usam sem importar OTel nem rede. Não herda de `ModeloSemEco`: o `ValidationError` tem de chegar ao
  pydantic-ai para valer o `output_retries`. O `hide_input_in_errors` e a mensagem fixa de `ErroDoModelo` fazem a mesma proteção (nenhum erro cita a saída do modelo).
- **D2 Texto livre** (≤ 320, H P2/P3): sem dígito Unicode, sem «R$»/«US$», e-mail ou link, sem placeholder fora do conjunto fechado dos TX e sem nada que a máscara trocaria.
  `ferramenta` existe se e somente se `acao = usar_ferramenta`; `args` são só referências opacas (nada com 10+ dígitos); `contexto_codigos` ≤ 10 códigos sem PII.
- **D3 `ACOES_POR_FASE`**: E2–E6 e E8 são a tabela de H §2.3b e **batem com o gabarito das falas do cliente na F3** (um teste compara). E7 = só `aguardar` (a prosa de H diz
  «no máximo uma frase de empatia», mas o gabarito da F3 só admite `aguardar` e o texto de espera é o TX-38, do código). E10 = `repassar`/`encerrar` («Modelo: só `contexto_codigos`»).
  E0, E1 e E9 = vazio (sem turno do modelo): toda ação ali é `AcaoForaDaFase`.
- **D4 Ferramentas e TX do modelo por fase** também são validados (`FerramentaForaDaFase`, `TxForaDaFase`, `CampoForaDaFase`): o modelo só pede T2/T3/T5/T10 onde H §2.3b manda e só escolhe TX da
  FAQ (32/33/39/40/41). Tudo isso é `TurnoForaDaFase` → `acao_invalida=true` na `decisao`, conta como falha (2 ⇒ repasse, B1.6). O erro leva o resultado (gasto) em `.resultado`.
- **D5 `sinal` e `motivo`**: `sinal` tem padrão `neutro` (faltar o campo não pode virar repasse); `motivo` ausente/vazio vira «(não informado)». O `passo.motivo` é de lista fechada (B1.2, achado A1):
  **o texto livre do modelo não vai ao passo**, só o código quando coincide com um da lista (`motivo_de_decisao`).

**Provedor**
- **D6 Um provedor, sem `FallbackModel`**: `ResolvedorModelo.resolver(modelo, provedor, raciocinio)` só aceita o par `deepseek-*` / `fireworks-us` do `Settings` (outro ⇒ `ProvedorNaoConfigurado`;
  `raciocinio=true` ⇒ `RaciocinioNaoLiberado`, até a F3). Falha de rede/HTTP/tempo ⇒ `ProvedorIndisponivel`; saída inválida depois do `output_retries=1` ⇒ `SaidaInvalida`. Mensagem fixa, sem
  `__cause__`/`__context__`: o SDK cita o corpo da resposta. O uso das tentativas que falharam também é cobrado (`erro.uso`).
- **D7 Roteador no `Settings`**: `MODELO_ROTEADOR` precisa casar `accounts/<conta>/routers/deepseek-<versão>-us` e ser o do `MODELO_NOME` (o boot recusa o endpoint «global», que G §2 diz não garantir os EUA,
  e outra versão do modelo). O SDK **não** repete a chamada (`max_retries=0`, revisão M-9): a segunda chance é só o `output_retries=1`. `MODELO_TIMEOUT_S` (padrão 8 s, teto 10 s) vale no cliente HTTP e, vezes (1 + `output_retries`), no turno inteiro.
- **D8 `criar_agente` devolve `AgenteDoTurno`** (o `Agent[Deps, Turno]` em `.agente`, mais faixa, preços e tempo) em vez do `Agent` cru do plano: `executar_turno` precisa dos nomes que o passo grava. `Deps` = só `atendimento_id` e `pessoa_id` (sem CPF).
- **D9 `max_tokens`** vai como `max_tokens` (perfil `openai_chat_supports_max_completion_tokens=False`): é o campo que a API do Fireworks documenta; o Pydantic AI usaria `max_completion_tokens`. **HIPÓTESE** (A2.9 confirma).
- **D10 Custo** (contrato 08 §9): `tokens_in` = entrada **não cacheada** (entrada total − `cached_tokens`); `custo_brl` em 6 casas, `ROUND_HALF_EVEN`, preços do `Settings` (≤ 0 derruba o boot, `test_boot_recusa_preco…`).
  Os tokens de raciocínio já estão dentro da saída (o provedor os cobra assim). `como_decisao()` monta o passo `decisao` com tokens, custo, latência e `trace_id`.

**Raciocínio**
- **D11 Parâmetro configurável** (`MODELO_RACIOCINIO_OFF`): `reasoning_effort_none` (padrão, `{"reasoning_effort": "none"}`) ou `thinking_disabled` (`{"thinking": {"type": "disabled"}}`). As duas estão na API do
  Fireworks (G §3); **nenhuma provada no V4.1 Flash**. O teste prova que a forma escolhida vai no `extra_body` e a outra não. Se vier tokens de raciocínio, o turno vale mas há `alerta_raciocinio` (log + span).

**Contexto**
- **D12 Dois pedaços**: blocos 1–3 (estáveis na fase) vão como instruções e 4–8 como a mensagem do usuário (elegível a cache de prefixo; não contamos com isso). O esquema do `Turno`, que o provedor recebe como ferramenta
  de saída, **conta junto do bloco 1** (`tokens_formato`).
- **D13 Estimador plugável** (`tokens.py`): `caracteres/3 × 1,10` — conservador, sem rede. O `tiktoken` está instalado como dependência transitiva, mas baixa o vocabulário da rede e não é o do DeepSeek; **HIPÓTESE, medir em B8.2**
  (`EstimadorPorCodificador` já aceita qualquer codificador). Medido com ele: um turno típico fica em ≈ 2,1–2,3 mil tokens estimados (H supunha 2,9 mil), com o bloco 1 em ≈ 1,3 mil (600 de sistema + 720 do esquema), acima dos 800 de H.
- **D14 Corte** (H §3.1): resumo → trocas antigas (uma troca por vez; **a última troca nunca sai**) → exemplos (um a um). Se nem assim couber, `ContextoNaoCabe` (falha do modelo). Nada além dessas três coisas é opcional.
- **D15 O que o modelo recebe** (H §3.3/P3): `protecao.proteger_texto` passa o texto de cliente pela máscara **outra vez** (a linha pode ter sido gravada antes de uma melhoria) e troca, em ordem: link digitado por `[LINK]`, data
  `dd/mm/aaaa` por `[DATA]`, dinheiro e prazo por `[VALOR]`/`[PRAZO]`, `r$`/`us$` solto por `[VALOR]` e **todo número de 2+ dígitos que não seja hora, dia ou duração por `[NUMERO]`**
  (o número do pedido é extraído por código; `alvo_pedido` só aponta o que ele quer); `«»` e quebras saem (a mensagem não forja cabeçalho). Ids reais viram apelidos `oferta-1`/`opcao-2` (mapa em
  `Contexto.referencias`). A oferta só aparece a partir da E3 (Q1) e nunca com valor. Hora, dia e duração ficam (o `adiar_com_hora` precisa; a prova é o corpus da F3). **Na E5 a mensagem do cliente É o valor do campo**:
  `montar_contexto` a troca por `[dado:<campo>]` salvo `desvio_liberado=True` (quem decide o desvio é o B5.3).
- **D16 `auditar_prompt`** (chamado em `montar_contexto`, com teste de fiação; `executar_turno` só aceita o `Contexto` montado) é o último portão: o prompt inteiro tem de passar na máscara sem mudar e não ter símbolo de moeda, senão `ContextoComDadoPessoal` e o turno não sai. Os nomes da conversa valem só para a parte variável (blocos 4–8).
- **D17 Exemplos do bloco 2** vêm da F3, **fora do hold-out** (20%, risco 7 de H), sem dígito nem PII, de intenções diferentes (as difíceis primeiro).
- **D18 `ProvedorFalso`** é o gabarito, não um modelo: responde a qualquer persona (inclusive as do hold-out) pelo `RoteiroF3`, que acha a fala do cliente já protegida e devolve o `Turno` esperado. Prova o encanamento; **não mede qualidade** (B8.2).

**Observabilidade**
- **D19 Não existe `PydanticAIInstrumentor`** na versão pinada de `openinference-instrumentation-pydantic-ai` (0.1.32): ela traz o `OpenInferenceSpanProcessor`. A instrumentação é por agente (`InstrumentationSettings`), sem estado global do pydantic-ai.
- **D20 O scrubber é um exportador** que embrulha o de verdade e roda por último na cadeia (depois do OpenInference, que copia o conteúdo das mensagens para atributos próprios): nome, atributos, listas, eventos (a exceção e o traceback entram aqui) e status. Mutação conferida: sem ele,
  três testes reprovam. Os logs passam pela fábrica de `LogRecord` (qualquer handler). Segredos registrados viram `[SEGREDO]`. Desligada por padrão: sem `PHOENIX_ENDPOINT` e sem exportador injetado não cria provedor nem faz rede.

## 3. Achados da revisão automática de segurança (2 × MEDIUM em `contexto.py`), corrigidos

1. **Limite inteiro único para todas as chaves do `perfil`** (`MAX_INTEIRO_DO_LEAD = 9999`): um valor da oferta ou um número sensível entraria no prompt por uma chave errada (`{"banco": 5000}`).
   Agora a allowlist é **por chave e com regra própria**: `LIMITES_INTEIROS_DO_LEAD = {"idade_do_lead_min": 9999, "etapas_do_robo_concluidas": 20}`; **inteiro em qualquer outra chave é rejeitado** (e `bool` nunca vale); `banco` só do catálogo `chave_registro.BANCOS` (revisão M-4; antes `^[A-Z0-9_]{1,32}$`); `origem`, `ultimo_sentido`, `tipo_ultima_fala` e `etapa_inapp` são **enums fechados** (`LEAD_ENUMS`); valor fora da regra da própria chave some, sem eco. Testes: `test_inteiro_so_passa_na_chave_que_tem_limite_inteiro_e_dentro_do_limite`,
   `test_valor_do_perfil_fora_da_regra_da_propria_chave_e_descartado` (12 casos), `test_perfil_valido_chega_inteiro…`. Reprovam com o limite único (mutação conferida).
2. **`_FOLHA_TEXTO` alargado para maiúsculas** relaxava a allowlist de PII de todos os resultados de ferramenta. Voltou a `^[a-z0-9][a-z0-9_.:-]{0,39}$` como regra geral; a maiúscula existe só onde a chave pede (`banco`). `_folha_segura`, `projetar_resultado` e o `lead` agora recebem os **`nomes` da conversa** e
   descartam a folha que a máscara trocaria por nome; `auditar_prompt(contexto, nomes)` faz o mesmo no prompt montado (só na parte variável, para um cliente chamado «Amado» não derrubar o turno por causa do texto fixo). Testes: `test_a_allowlist_de_resultado_de_ferramenta_continua_so_em_minusculas`,
   `test_nome_conhecido_nao_passa_como_folha_de_resultado_de_ferramenta`, `test_nome_do_cliente_nao_entra_no_lead_nem_por_enum`, `test_auditar_prompt_com_nomes_…`. Cada um reprova sem a sua correção (mutação conferida).
   Efeito colateral aceito: um cliente cujo nome é igual a um código do lead («Facta», «Inapp») perde esse campo no prompt (fail-closed).

## 4. Divergências do plano (sp01 T6) e de H

- `PydanticAIInstrumentor().instrument()` → `OpenInferenceSpanProcessor` + `InstrumentationSettings` (D19).
- `criar_agente` devolve `AgenteDoTurno` (D8); `ferramenta_falsa(ctx)` não recebe `pessoa_id` (está em `Deps`); `montar_contexto(conn, atendimento_id, pendentes=…, chaveiro=…, nomes=…, agora=…)` lê o atendimento sozinho.
- `ResultadoTurno` ganha `uso` (`tokens_in` = não cacheada), `raciocinio_detectado` e `acao_invalida`; `custo_brl` é função de `Precos` do `Settings`.
- H §3.1 dá 600–800 tokens ao bloco 1; com o esquema do `Turno` como ferramenta de saída ele passa de 1,2 mil (estimado). O total continua folgado (D13).
- H §2.2 manda o `motivo` à linha do tempo; B1.2 (A1) o fechou numa lista de códigos (D5).

## 5. Revisão 1 (03/11/2026, `docs/REVISAO-B1.4-0311.md`): o que foi corrigido

Um commit `fix:` por item, cada um com teste que reprova sem a correção (mutação conferida). 0 crítico, 1 alto, 12 médios, 11 baixos.

| ID | Correção | Teste |
|---|---|---|
| **A-1** | Ferramenta registrada só por `ferramentas.registrar({"T3": f})`: nome sem projeção em `PROJECAO_DAS_FERRAMENTAS` ⇒ `FerramentaSemProjecao` na subida; `after_tool_execute` projeta, audita e devolve só o permitido; `ModelRetry`/`ToolFailed` vão com texto fixo; apelidos novos entram em `ResultadoTurno.referencias` | `test_ferramentas.py` (sonda p9) |
| **M-1/M-2** | `protecao.py`: `[NUMERO]` para 2+ dígitos fora de hora/dia/duração, `[DATA]` para data completa; E5 oculta a mensagem (`[dado:campo]`) salvo `desvio_liberado` | `test_contexto.py`; corpus de `adiar_com_hora` inteiro |
| **M-3** | Raiz em `mascara.py`: o nome só deixa de ser nome se colado a LETRA (`maria1`, `maria_alvardel`, `_alvardel` mascaram). Em vez de normalizar `[_\d]+` antes de mascarar, a borda certa na máscara resolve todos os chamadores (texto, perfil, folha, auditoria) e a checagem de dígitos/e-mail continua no texto original | `test_mascara.py`, `test_contexto.py` (sonda p1) |
| **M-4/M-5** | `banco` só de `chave_registro.BANCOS` (fora do catálogo na oferta vira `OUTRO`); `_` conta como separador em `_PARECE_NUMERO`; `placeholders` de T3/T5 e `macro` do T10 por domínio fechado (`PLACEHOLDERS_DO_TEXTO`, 6 macros do ST-00…05) | `test_contexto.py` (sonda p1) |
| **M-6** | `PLACEHOLDERS_DA_FASE` em `turno.py` aplicado ao `Turno.texto`: placeholder fora da fase ⇒ `TextoForaDaFase` (`acao_invalida`) | `test_agente.py` |
| **M-7** | `r$`/`us$` solto vira `[VALOR]` (não derruba mais 3 turnos seguidos) | `test_contexto.py` |
| **M-8** | Teste de fiação do `auditar_prompt` em `montar_contexto` (proteção neutralizada); `executar_turno` só aceita `Contexto` | `test_contexto.py` |
| **M-9** | `MODELO_TIMEOUT_S` 8 s (teto 10), `max_retries=0`; `criar_agente` sem `settings` usa o do resolvedor ou o padrão | `test_timeout.py` (sonda p6, servidor que pendura em 127.0.0.1) |
| **M-10** | A fábrica de `LogRecord` nunca levanta: formato inválido sai com marca, mascarado, mais um aviso sem o conteúdo | `test_observabilidade.py` |
| **M-11** | `ContextoNaoCabe`, `ContextoComDadoPessoal` e `RetornoDeFerramentaInvalido` são `ErroDoModelo` (`FalhaDoContexto`), com `codigo` e o gasto do turno | `test_contexto.py`, `test_ferramentas.py` |
| **M-12** | Tabela da A2.9 abaixo; a B1.4 **não** está «concluída» até ela fechar | — |
| **B-1** | Padrão sem retentativa do SDK (um 429/500/503 é uma requisição) | `test_agente.py` (sonda p4) |
| **B-2 (a)** | Resposta sem `usage`: `ResultadoTurno.uso_ausente` e `alerta_uso_ausente` | `test_agente.py` |
| **B-3** | Estimador: não latino a 2 tokens/caractere (3,0 × 1,10 do latim ficam até a B8.2); rajada limitada às 10 últimas + linha de omitidas | `test_contexto.py` (sonda p7) |
| **B-4** | Scrubber mascara chave de atributo, nome de evento, link e JSON decodificado (CPF partido por `\n`) | `test_observabilidade.py` (sondas p3, p3b, p8) |
| **B-6** | Bloco 3 da E2 sem `oferta_ref` (o estado ainda não tem oferta) | `test_contexto.py` |
| **B-7, B-8** | `ResolvedorModelo` cacheia o cliente por par e tem `aclose()`; `configurar()` encerra o provedor anterior | `test_agente.py`, `test_observabilidade.py` |
| **B-9** | Texto livre recusa «aprovado/garantido/garantia», link sem esquema e `R $`/`R＄` (o resto, número por extenso, é do T15 na B5) | `test_agente.py` |
| **B-11** | `ArgsDaFerramenta`: só `oferta_ref` (`oferta-N`), `opcao_ref` (`opcao-N`) e `alvo` (`valor|parcela|prazo`) | `test_agente.py` |

**Achados da revisão automática em `protecao.py` (2 × MEDIUM), corrigidos:**
1. `_LINK` só consumia o host quando não havia `http`: `.evil.xyz/…`, `:porta`, `?query` e `#fragmento` ficavam no texto e iam ao provedor. Agora, depois de casar o esquema (`xxx://`), `www.` ou o host com TLD conhecido (lista ampliada: `xyz`, `info`,
   `site`, `online`, `top`, `club`...), o link vai **até o próximo espaço**; e `auditar_textos` ganhou a checagem de link (`ha_link`) que falha fechada (texto com link residual ⇒ `ContextoComDadoPessoal`, também no retorno de ferramenta).
2. `_LINK` rodava no texto cru e os demais validadores numa vista normalizada: URL e `Ｒ＄` de largura inteira (`ｈｔｔｐ：／／`), pontos ideográficos (`。`, `｡`) escapavam. Agora `normalizar()` (NFKC caractere a caractere, **mesmo comprimento**,
   mais o ponto ideográfico) roda **antes de todo o pipeline** de `proteger_texto` e também dentro de `auditar_textos`. Em vez de casar na vista e substituir no original pelos índices, o pipeline inteiro trabalha sobre a vista (o mesmo efeito para
   todos os validadores, sem divergência possível; o modelo lê «fora do link» no lugar de «ｆｏｒａ ｄｏ ｌｉｎｋ»). Testes: `test_link_vai_ate_o_proximo_espaco_…`, `test_link_e_moeda_de_largura_inteira_nao_escapam`, `test_auditar_textos_barra_link_residual_…`,
   `test_montar_contexto_barra_o_link_que_a_protecao_nao_pegou` (cada um reprova sem a sua correção, mutação conferida). Custo aceito: «ok.obrigado» e «Sr.Silva» continuam iguais (TLD fora da lista), mas um domínio real fora da lista segue como texto
   (a auditoria só barra o que a lista conhece; a B8.2 mede os falsos negativos).

Também: a URL que o cliente digitou chegava ao corpo da requisição (sonda p2): agora `[LINK]`. A prova p2 (corpo HTTP completo por fase, 49 itens proibidos) virou `tests/test_vazamento_corpo.py`.

**Deixados (BAIXOS, de propósito):** **B-2 (b)(c)** helper para gravar o gasto do turno que FALHA e a coluna `tokens_cache` (depende do contrato 08 §9 e da B1.6; hoje a fórmula não se reproduz a partir da linha do passo); **B-5** esquema do `Turno` igual em todas as
fases, `sinal` opcional (enum de `acao` por fase e `required` mudam o prefixo e o comportamento do modelo: decidir com a A2.9; os `args` já saem com `properties` explícitas); **B-8 (parte)** nada no `src/` chama `configurar()` nem
`instalar_excepthook()` (é o boot da B1.5; o teste de fiação vai com ele); **B-9 (parte)** número e moeda por extenso e telefone por extenso (T15, B5); **B-10** `ProvedorFalso`/`RoteiroF3` em `src/` (o harness da B8.2 os usa; mover para um pacote `duble` quando a B8.2 nascer).
A divergência do `RoteiroF3` com as falas P36/P53 (E2) é do duplo, não do código de produção.

## 6. Pendências

**A2.9 (M-12): a B1.4 só fecha quando estas 12 linhas tiverem resposta medida.** Roteiro: as 20 chamadas sintéticas do estudo G §6, com a chave Fireworks, no principal.

| # | O que provar | Hoje (HIPÓTESE) | Se falhar, muda |
|---|---|---|---|
| 1 | Qual forma desliga o raciocínio no V4.1 Flash: `reasoning_effort="none"` ou `thinking:{type:disabled}` | `reasoning_effort_none` (padrão) | `MODELO_RACIOCINIO_OFF` (sem código) |
| 2 | `tool_choice:"required"` é aceito junto com o parâmetro acima | aceito | `NativeOutput` no lugar do Tool Output |
| 3 | O nome do roteador no campo `model` (`accounts/fireworks/routers/…-1017-us`) | aceito | `MODELO_ROTEADOR` |
| 4 | O esquema do `Turno` como ferramenta (`anyOf` com `null`, `maxLength`, `pattern`, `args` com propriedades opcionais) passa e a saída chega válida; `NativeOutput` × Tool Output | passa | simplificar o esquema (B-5: `acao` por fase) |
| 5 | `usage.completion_tokens` já inclui os tokens de raciocínio | inclui | custo (`tokens_raciocinio`) |
| 6 | Onde vem `cached_tokens` (`usage.prompt_tokens_details` × cabeçalho) | `prompt_tokens_details` | custo superestimado se vier de outro lugar |
| 7 | `max_tokens=400` com tokens de raciocínio trunca a saída (⇒ `SaidaInvalida`)? | não, com raciocínio desligado | subir `MODELO_MAX_TOKENS` |
| 8 | `max_tokens` × `max_completion_tokens` | `max_tokens` | perfil do modelo |
| 9 | `Retry-After` e 429 no serverless: vale reabrir `max_retries` (hoje 0)? | não | `RETENTATIVAS_DO_SDK` |
| 10 | Latência real (p50/p95) para calibrar `MODELO_TIMEOUT_S` (8 s) | p95 ≤ 4 s | `MODELO_TIMEOUT_S` |
| 11 | `usage` sempre presente na resposta | sempre | já há alerta (`alerta_uso_ausente`) |
| 12 | Chave Fireworks, US$ 100 de crédito (Tier 2) e o teste de aceitação do estudo G §6 | pendente do dono | nada roda sem ela |

**Demais pendências**
- **B8.2**: medir o tokenizer do DeepSeek e calibrar `EstimadorPorCaracteres` (hoje 3,0 × 1,10 no latim e 2 tokens por caractere não latino); avaliar a **qualidade** do prompt (`SISTEMA` e os módulos de fase são a v0, escrita sem modelo real) com as 60 personas × 3.
- **B1.6**: consumir `ErroDoModelo` (inclui as falhas do contexto e da proteção de ferramenta; 2 ⇒ repasse), gravar a `decisao` (`como_decisao`, `acao_invalida`), voltar apelidos a ids por `ResultadoTurno.referencias`, resolver placeholders e TX, `consumir` as pendentes, decidir o `desvio_liberado` da E5 e fazer a chamada barata do **resumo** (H §3.5).
- **B5/gateway**: o formato do resultado de T2/T3/T5/T10 não existe ainda; `PROJECAO_DAS_FERRAMENTAS` é a allowlist esperada e muda junto com ele (ferramenta nova só entra com projeção). **B6.2**: os códigos de `etapa_inapp`/`origem` e a escrita de `ultimo_sentido`/`tipo_ultima_fala` no `perfil` (L1/L3 do estudo N; dependem da A2.4); os enums de `LEAD_ENUMS` precisam acompanhar.
- **Phoenix real**: a exportação OTLP só foi verificada por construção (exportador trocado nos testes); falta o servidor (infra A4) e a retenção de 14 d do «ver bruto».
- A defesa contra manipulação do cliente (I2/I5/I9 em texto de saída) é o T15 determinístico (B5); aqui só se garante que o texto do cliente é tratado como dado e que o texto livre do modelo não leva número, link, promessa nem placeholder fora da fase.
