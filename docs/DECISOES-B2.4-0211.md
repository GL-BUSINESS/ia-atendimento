# B2.4 · `pessoas_teste` (FACTA, T1/T3) e fixtures de 3RN e C6 para o modo `duble`: decisões e pendências para o revisor

Branch `feat/b2-4-pessoas-teste`, **empilhada sobre `origin/feat/b1-5-api-entrada`** (PR #6 ainda aberto; 2.252 testes na base). Par no `bancos-duble`: branch `feat/b2-4-pessoas-teste` a partir da main v0.1.2 (`1305152`).
Roteiro B2.4 (l. 773–776), riscos 92 e 103. **PII zero:** só CPF `000.000.0nn-dd`, nomes de fantasia do corpus, telefone `5500 9000-00nn`, `pessoa_id` `00000000-…`. Nada rodou em produção, na VPS, na S4 nem contra
banco; sem push.

## Decisões

| # | Decisão | Por quê |
|---|---|---|
| D1 | `pessoas_teste.py` (B1.5) virou **pacote**: `arquivo.py` é o mesmo código (`git mv`), e `from ia_atendimento.pessoas_teste import PessoasTesteFixas, carregar, …` continua valendo | a B1.5 deixou o nome reservado para a B2.4; nenhum import da API mudou |
| D2 | **Uma pessoa por `persona_id`** (60 H + 24 P-M = 84), gerada do corpus por `scripts/gerar_pessoas_teste.py` → `pessoas.json` + `pessoas.sha256`; `--verificar` entra no `check.sh` | o corpus é a fonte; catálogo escrito à mão deriva |
| D3 | `pessoa_id` fixo `00000000-0000-7000-8000-<n>` (n = 1..60; P-M = 101..124), UUID v7 | o `pii_nao_sintetica` do corpus já trata `00000000-` como sintético; o padrão `Uuid` do 360 é aceito |
| D4 | **CPF = o do corpus** (`000.000.0nn-dd`, DV válido). Várias personas dividem o CPF porque dividem a persona do dublê (P01, P34, P57 e P-M01 usam `aprovado-24`) | o CPF é a chave dos stubs da FACTA; T1/T3 são por `pessoa_id`, então não há ambiguidade. DV válido cobre o spike I25 (aberto) |
| D5 | Oferta FACTA ativa do **perfil** da persona (`valor_pre_aprovado_brl`, `prazo_oferta_x`), parcela = valor × coeficiente da tabela 115716 da camada A (`aprovado-24/36/48/60`); sem oferta (P-M18) o par vem `sem_oferta`. P13: oferta ativa também no C6; P14: par 3RN `sem_oferta` | H §7 («cita C6 e há oferta ativa»; «cita 3RN e não há») |
| D6 | `coef_valor` (ordena o fallback do T3, nunca vai ao modelo): FACTA 0,012, C6 0,010, 3RN 0,008. **Inventados**: só fixam a ordem; não são pct de comissão real | só a forma interessa (PD-6) |
| D7 | **`valid_until` relativo = agora + 2 h, calculado ao servir**, com `Relogio` injetado (`FontePessoasTeste`) e, na camada B, pelo WireMock (`{{now offset='2 hours'}}`); `criada_em` = agora − 15 min; `business_date` = o dia em São Paulo. O arquivo de exemplo guarda `agora_referencia` e a regra | oferta nunca "velha no arquivo"; o harness pode encurtar `validade` e subir `versao` (P51/P52, «a oferta vence») |
| D8 | A fonte serve só em **`duble` e `teste`**; `real` e `sombra` levantam `ForaDoModoDeTeste` | fixture nunca responde por cliente de verdade |
| D9 | Formas medidas em Pydantic estrito (`formas.py`): `Oferta`, `PayloadEconomicoCltV1`, `ParPropostasPessoa`, `ResultadoPropostasPessoa`, `PessoaResumo`, `ResumosPessoas` (do `cliente360.json`); `/3rn/calcular` e `/c6/oferta/simular` (dos dicts que `3rn-api@9b20d44` e `c6-api@cfb80d5` montam). `extra="forbid"` onde o contrato é fechado | fixture que "funciona" e diverge da resposta real é o risco; 30 mutações de forma reprovam |
| D10 | Fixtures de banco: P14 no 3RN = `SIM_AUSENTE` (`nao_repagar` sem simulação guardada: a consulta paga não é refeita), HTTP 200 `success:false`; `reprovado` fica como outro caso. Padrão do 3RN = `calculado`; padrão do C6 = `sem_oferta` (404, `success:true`, como o `c6-api`). `cpf` da resposta é o eco do pedido (arquivo traz `00000000000`) | segue o código lido; nada foi chamado |
| D11 | `chats_teste` ↔ `pessoas_teste`, restrição à TI e registro **já eram da B1.5** (D16 e `ORIGENS_QUE_MEXEM_EM_TUDO`). Esta etapa **não muda a API**: acrescenta os testes com o catálogo real (as 84 pessoas), inclusive 403 para `n8n_braco`, `c360_api` e `vigia`, e o registro (`publicado_por`, `motivo`) lido da tabela | evita mexer em código já revisado duas vezes |
| D12 | «[TESTE]»: `texto_de_saida(modo_efetivo, texto)` prefixa **só em `teste`**, idempotente, e o prefixo conta no limite de tamanho. **O `Canal` ainda não existe** (B1.6/B6.8): esta etapa entrega e prova a função | o aceite de «toda mensagem enviada a chat de teste leva o prefixo» fecha quando o `Canal` a chamar |
| D13 | Kit `~/retomada-2809/fila-2910/ia/config/chats-teste.sh` (`gerar`/`aplicar`/`limpar`, `--ensaio`/`--confirmo`). **Duas fases**: o `PESSOAS_TESTE_ARQUIVO` é lido no boot, então o kit gera o arquivo (0600), o dono o entrega à VPS e reinicia, e só então `aplicar` faz o `PUT`. Token da TI em arquivo 0600 (nunca argv), `versao_esperada` = a vigente, imprime só contagens e código | o contrário (PUT antes do reinício) dá 422 `pessoa_fora_de_pessoas_teste` |
| D14 | Camada B: `GET /c360-duble/v1/pessoas/{pessoa_id}/resumo|propostas` com o corpo do 360 (170 stubs, `metadata.evidencia = HIPOTESE`); qualquer outro `pessoa_id` = 200 «não encontrado», como o 360 | o 360 real é `POST …:resumos/:propostas` por CPF; chat de teste não tem CPF |
| D15 | **Consistência entre os repositórios:** o `bancos-duble` guarda `personas/pessoas_teste.yaml` (instantâneo) e o **mesmo** `pessoas_teste.sha256` (hash do JSON canônico da lista). `scripts/atualizar_pessoas_teste.py` regrava e recusa catálogo cujo hash não bate. Testes dos dois lados leem o outro por `IA_ATENDIMENTO_PATH` / `BANCOS_DUBLE_PATH` e são **pulados** sem a variável; no duble há ainda o teste que compara o corpo de T1/T3 do WireMock com o exemplo gravado no ia-atendimento (a menos dos instantes) | sem CI nos dois repos; o hash compartilhado é o que não depende de o outro estar presente |
| D16 | O wheel leva `fixtures/` (`force-include`, igual às migrações); `test_o_wheel_leva_as_migracoes…` passou a conferir as duas chaves | o gateway as lê fora do checkout |

## Pendências para o revisor

1. **Contrato 08 §6 precisa de emenda.** A linha «Ler» de `teste` diz «360 real; FACTA no dublê». O roteiro B2.4/B5.2 manda servir `pessoas_teste` em `duble|teste`, e o 360 real não conhece o `pessoa_id` sintético. Fiz como o roteiro; a tabela deve passar a dizer «fixtures `pessoas_teste` (T1/T3); FACTA no dublê».
2. **`Canal` e «[TESTE]» (B1.6/B6.8):** só a função está pronta. Teste de aceite de «nenhuma mensagem de teste sai sem prefixo» fica para quando o `Canal` existir.
3. **Gateway de ferramentas (B5.2):** ligar `FontePessoasTeste` ao `modo_efetivo` (chat → `pessoas_teste.pessoa_do_chat` → T1/T3) e `FixturesDuble.calcular_3rn/simular_c6` ao T5 de outro banco. Hoje nada do orquestrador as chama.
4. **Spike I25** (facta-on aceita CPF sintético) segue aberto; os CPFs têm DV válido por precaução.
5. **CPF compartilhado entre personas** herda o estado global de scenario do dublê (já avisado no README do corpus): `scenario.py reset` entre rodadas.
6. **Prazo da oferta × cenário do dublê:** a oferta de T3 vem do perfil (ex.: P34 prazo 36) e o T5/T7 da camada A segue o cenário do dublê (`aprovado-24`). O corpus já trata o `cenario_facta` como metadado; fica registrado.
7. **Valores inventados:** `coef_valor` (D6), IDs `SIM-TESTE-…`, convênio `800077` do C6 e tabela `FGL 102` do 3RN não são de produção. O contrato do 360 usado nos testes de deriva é o do checkout `cliente360-web` (`CLIENTE360_CONTRATO_PATH`; pulado se ausente). Campo opcional novo no contrato não reprova (só campo a mais no modelo ou obrigatório a menos).
8. **Kit só em ensaio:** rodei `--ensaio` e `--confirmo` contra uma API falsa local (200 e 422) e `gerar` de verdade no scratchpad; **nunca** contra a API real nem a VPS. Fica fora do repositório, como os demais kits.
9. **gitleaks** não está instalado nesta máquina (o `check.sh` do duble avisa e segue); `scripts/varredura.py` e o `piiscan` passaram.
10. A versão do `pyproject` do ia-atendimento não muda (entra na v0.3.0); sem tag em nenhum dos dois repos.

## Números

- ia-atendimento: 2.252 → **2.317 passed** (+65: 17 + 41 + 7), 2.316 e 2 skips sem `BANCOS_DUBLE_PATH`; `bash scripts/check.sh` verde. Nomes pedidos: `test_chats_teste_so_com_pessoa_de_teste`,
  `test_mensagem_de_teste_prefixada_TESTE`, `test_pessoas_teste_cobrem_todas_as_personas`, `test_valid_until_relativo`; `-k fixtures_duble` (41), `-k pessoas_teste` (26: 17 + 7 dos arquivos novos e 2 da B1.5).
- bancos-duble: 623 → **638 passed** (+15; 6 skipped e 2 xfailed como antes); `check.sh` verde com `DUBLE_REQUIRE_DOCKER=1` e `IA_ATENDIMENTO_PATH`; stubs da camada B 358 → 528.
- Mutações que reprovaram: validade de 3 h, prefixo em outro modo, checagem de pessoa removida, `c360_api` com `chats_teste`, `real` entre os modos servidos (ia-atendimento); `valid_until` fixo, sem stubs
  «desconhecida», YAML adulterado (bancos-duble).
