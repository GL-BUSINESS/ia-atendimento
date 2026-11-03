# B1.4 — decisões e pendências (02/11/2026)

Etapa «Contexto do turno, agente `Turno` e observabilidade» (sp01 T6; roteiro B1.4). Branch `feat/b1-4-agente-turno`, da main `24bc524`. Sem rede, sem chave de
provedor, sem S4/VPS/n8n/ChatGuru. Rótulos: **DECISÃO** (escolha minha, revisável) · **HIPÓTESE** (depende de medição) · **PENDENTE** (depende de outra etapa ou do dono).

## 1. O que existe

| Arquivo | Papel |
|---|---|
| `turno.py` | `Turno`, `ACOES_POR_FASE`, ferramentas e TX do modelo por fase, `validar_turno_na_fase` e os erros (`ErroDoModelo`, `AcaoForaDaFase`...), `custo_brl`, `ResultadoTurno` |
| `agente.py` | `ResolvedorModelo` (UM `OpenAIChatModel`, Fireworks só-EUA), `criar_agente`, `executar_turno`, `ProvedorFalso`, `ModeloDaFaixa`, `Deps` |
| `contexto.py`, `modulos_fase.py`, `tokens.py` | os 8 blocos de H §3.1, o texto fixo do prompt, o estimador de tokens e o corte |
| `roteiro_f3.py` | o roteiro da F3 como resposta do modelo (`ProvedorFalso`) e os exemplos do bloco 2 |
| `observabilidade.py` | OTel → Phoenix, scrubber de span/log, segredos, `trace_id`, alerta de raciocínio |
| `config.py` (acréscimos) | roteador só-EUA, forma de desligar o raciocínio, chamada ao modelo, preços e câmbio, Phoenix |

Testes novos: `test_agente.py` (66), `test_contexto.py` (47), `test_observabilidade.py` (18). Os 4 nomeados no roteiro: `test_cpf_e_valores_nao_vao_ao_modelo`, `test_span_nao_contem_cpf`,
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
  e outra versão do modelo). Retentativas do SDK (`MODELO_TENTATIVAS_HTTP`=1) são no MESMO provedor; tempo total do turno = `MODELO_TIMEOUT_S` × (1 + `output_retries`).
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
- **D15 O que o modelo recebe** (H §3.3/P3): texto de cliente passa pela máscara **outra vez** (a linha pode ter sido gravada antes de uma melhoria), dinheiro e prazo digitados viram `[VALOR]`/`[PRAZO]` (o número do pedido é extraído por
  código, `alvo_pedido` só aponta o que ele quer), `«»` e quebras saem (a mensagem não forja cabeçalho). Ids reais (oferta, opções) viram apelidos `oferta-1`/`opcao-2`; o mapa fica em `Contexto.referencias` para o processador (B1.6).
  A oferta só aparece a partir da E3 (Q1: abertura sem valores) e nunca com valor. Hora e dia ficam (o `adiar_com_hora` precisa deles).
- **D16 `auditar_prompt`** é o último portão: o prompt inteiro tem de passar na máscara sem mudar e não ter símbolo de moeda, senão `ContextoComDadoPessoal` e o turno não sai. Os nomes da conversa valem só para a parte variável (blocos 4–8).
- **D17 Exemplos do bloco 2** vêm da F3, **fora do hold-out** (20%, risco 7 de H), sem dígito nem PII, de intenções diferentes (as difíceis primeiro).
- **D18 `ProvedorFalso`** é o gabarito, não um modelo: responde a qualquer persona (inclusive as do hold-out) pelo `RoteiroF3`, que acha a fala do cliente já protegida e devolve o `Turno` esperado. Prova o encanamento; **não mede qualidade** (B8.2).

**Observabilidade**
- **D19 Não existe `PydanticAIInstrumentor`** na versão pinada de `openinference-instrumentation-pydantic-ai` (0.1.32): ela traz o `OpenInferenceSpanProcessor`. A instrumentação é por agente (`InstrumentationSettings`), sem estado global do pydantic-ai.
- **D20 O scrubber é um exportador** que embrulha o de verdade e roda por último na cadeia (depois do OpenInference, que copia o conteúdo das mensagens para atributos próprios): nome, atributos, listas, eventos (a exceção e o traceback entram aqui) e status. Mutação conferida: sem ele,
  três testes reprovam. Os logs passam pela fábrica de `LogRecord` (qualquer handler). Segredos registrados viram `[SEGREDO]`. Desligada por padrão: sem `PHOENIX_ENDPOINT` e sem exportador injetado não cria provedor nem faz rede.

## 3. Achados da revisão automática de segurança (2 × MEDIUM em `contexto.py`), corrigidos

1. **Limite inteiro único para todas as chaves do `perfil`** (`MAX_INTEIRO_DO_LEAD = 9999`): um valor da oferta ou um número sensível entraria no prompt por uma chave errada (`{"banco": 5000}`).
   Agora a allowlist é **por chave e com regra própria**: `LIMITES_INTEIROS_DO_LEAD = {"idade_do_lead_min": 9999, "etapas_do_robo_concluidas": 20}`; **inteiro em qualquer outra chave é rejeitado** (e `bool` nunca vale); `banco` segue `^[A-Z0-9_]{1,32}$`
   (igual a `EntradaAtendimento.banco`); `origem`, `ultimo_sentido`, `tipo_ultima_fala` e `etapa_inapp` são **enums fechados** (`LEAD_ENUMS`); valor fora da regra da própria chave some, sem eco. Testes: `test_inteiro_so_passa_na_chave_que_tem_limite_inteiro_e_dentro_do_limite`,
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

## 5. Pendências

- **A2.9 (parâmetro de raciocínio)**: provar qual forma o V4.1 Flash no Fireworks aceita (`MODELO_RACIOCINIO_OFF`), se há `reasoning_content`/tokens de raciocínio no `usage`, `Tool Output` × `NativeOutput`, `max_tokens` × `max_completion_tokens` e se o esquema do `Turno` (`patternProperties`/`maxProperties` em `args`)
  passa no modo de ferramenta do provedor; se não passar, simplificar `args`. Também confirmar onde o Fireworks devolve `cached_tokens` (o código lê `prompt_tokens_details`).
- **Chave Fireworks** (`MODELO_API_KEY_1`), conta com US$ 100 de crédito (Tier 2) e o teste de aceitação da §6 do estudo G: sem ela nada aqui fala com o modelo; o preço do `Settings` é o de planejamento e precisa ser conciliado com a fatura.
- **B8.2**: medir o tokenizer do DeepSeek e calibrar `EstimadorPorCaracteres`; avaliar a **qualidade** do prompt (`SISTEMA` e os módulos de fase são a versão 0, escrita sem modelo real) com as 60 personas × 3.
- **B1.6**: consumir `ErroDoModelo` (2 ⇒ repasse), gravar a `decisao` (`como_decisao`, `acao_invalida`), voltar apelidos a ids por `Contexto.referencias`, resolver placeholders e TX, `consumir` as pendentes, e fazer a chamada barata do **resumo** (H §3.5: o `gravar_resumo` existe; quem resume ainda não).
- **B5/gateway**: o formato do resultado de T2/T3/T5/T10 não existe ainda; `PROJECAO_DAS_FERRAMENTAS` é a allowlist esperada e muda junto com ele. **B6.2**: os códigos de `etapa_inapp`/`origem` e a escrita de `ultimo_sentido`/`tipo_ultima_fala` no `perfil` (L1/L3 do estudo N; dependem da A2.4); os enums de `LEAD_ENUMS` precisam acompanhar.
- **Phoenix real**: a exportação OTLP só foi verificada por construção (exportador trocado nos testes); falta o servidor (infra A4) e a retenção de 14 d do «ver bruto».
- A defesa contra manipulação do cliente (I2/I5/I9 em texto de saída) é o T15 determinístico (B5); aqui só se garante que o texto do cliente é tratado como dado e que o texto livre do modelo não leva número, link nem placeholder desconhecido.
