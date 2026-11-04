# B5.1 · Gateway de ferramentas: decisões e o que ficou de fora

Branch `feat/b5-1`, a partir da `main` `9bee6a4` (04/11). Especificação: roteiro v3.3 B5.1 (registro, validação, mascaramento, modos), estudo F
§Gateway 1–12, contrato 08 §6 (`modo_efetivo`, posse real, Tabela final), D-15 (fail-closed), D-29 (saída só pela allowlist), D18 (CPF em
memória), P-R7, P-R23, R2-02. Construção só local (dono, 04/11): nada em S2, S4, VPS, n8n ou Coolify; sem migração; sem merge.

Portão: `BANCOS_DUBLE_PATH=<bancos-duble na main> bash scripts/check.sh` verde, **3.391 testes** (1 skip de `yaml`, 1 xfail da B1.6), 184 deles novos (152 da construção, 32 da revisão) em
`tests/test_ferramentas_registro.py`, `tests/test_ferramentas_modo.py`, `tests/test_ferramentas_gateway.py`, `tests/test_ferramentas_gateway_revisao.py` e
`tests/test_ferramentas_agente.py` (apoio em `tests/apoio_gateway.py`). Conferir só a etapa: `uv run pytest tests/test_ferramentas*.py`.

## O que entrou

| Arquivo | O quê |
|---|---|
| `ferramentas/projecao.py` | o antigo `ferramentas.py` da B1.4, sem mudança de comportamento; `Deps` ganha `modo`, `posse_real`, `orcamento`; `proteger_retorno` deixa passar o envelope de erro; `registrar` aceita `Tool` |
| `ferramentas/especificacao.py` | `Especificacao` declarativa e as regras que a recusam na subida |
| `ferramentas/esquemas.py` | esquemas de entrada (só referências) e de saída do catálogo MVP, todos `extra=forbid` |
| `ferramentas/catalogo.py`, `catalogo_versoes.json` | `CATALOGO_MVP`, `catalogo_hash`, histórico de `numero` e `conferir_versao` |
| `ferramentas/modo.py` | `modo_efetivo`, `LeitorDeModo` (cache ≤ 5 s), `Destinos` (URL base por serviço) e a tabela de destino |
| `ferramentas/gateway.py` | `Gateway.chamar` e `ferramentas_do_agente` |
| `ferramentas/saida.py`, `segredo.py`, `orcamento.py`, `erros.py` | reconstrução e varredura da saída, `formatar_brl`; `CpfEmMemoria`; tetos; vocabulário fechado de erros e pré-condições |
| `observabilidade.py`, `agente.py` | span `ia.ferramenta`; `executar_turno` põe um orçamento novo por turno |

## Testes nomeados no roteiro

| Teste | Onde | Prova |
|---|---|---|
| `test_catalogo_hash_muda_sem_versao_falha_ci` | registro | catálogo mudado sem `numero` novo ⇒ `CatalogoSemVersao`; com o `numero` novo passa. O portão roda `test_catalogo_vigente_tem_versao_registrada` |
| `test_modelo_nao_fornece_cpf_nem_valor` | gateway | nenhum esquema do modelo tem os 20 campos proibidos; argumento a mais ⇒ `PARAMETRO_INVALIDO`, sem eco, executor parado |
| `test_saida_fora_da_allowlist_e_descartada` | gateway | CPF, `coef_valor`, comissão, tabela, link e motivo cru somem na chegada; ao modelo só a projeção |
| `test_teste_e_sombra_nunca_resolvem_host_de_producao` | modo | ver D8 (a exceção da leitura do 360/3RN/C6 em `sombra`) |
| `test_cpf_so_em_memoria_do_gateway` | gateway | o executor recebe o CPF; log cru, span cru, registro, resultado e exceção do executor não o têm; nenhuma migração tem coluna de CPF |
| `test_parada_dura_muda_o_roteamento_do_efeito_ja_em_curso` | gateway | o atendimento leu em `real`; a parada dura liga durante as pré-condições da T7; a T7 sai interceptada |

Mutantes conferidos à mão (cada um derruba ao menos um teste): destino resolvido antes das pré-condições; teste resolvendo produção; teste sem dublê
caindo na produção; FACTA tratada como leitura comum; cache do modo eterno; parada dura ignorada; dublê = produção aceito; apelido inventado
aceito; id cru sem resolvedor; CPF lido para fixture; CPF ou mensagem da exceção no log; pré-condição sem verificador aceita; sem limitador; sem
envelope de erro; sem orçamento do turno.

## Decisões

| # | Decisão | Fonte |
|---|---|---|
| D1 | **Pacote `src/ia_atendimento/ferramentas/`** neste repositório (dono, 04/11). O `ferramentas.py` da B1.4 virou `ferramentas/projecao.py` e o pacote reexporta os mesmos nomes; o único ajuste em teste antigo é o alvo do `monkeypatch` (`ferramentas.projecao`) | dono 04/11; R2-28 |
| D2 | **Catálogo MVP = T1, T2, T3, T5, T6, T7, T8, T9, T10, T13, T14.** Fora: T4 (P-R23), T11 e T12 (ações do orquestrador: `Canal` e repasse, B1.6), T15 (B5.9, nasce desligado), T16 (serviço de mídia). Do modelo só T2, T3, T5 e T10 (= `FERRAMENTAS_DO_MODELO_POR_FASE`; teste) | F §Resumo 2; H §2.3b |
| D3 | **`catalogo_hash`** = sha256 do JSON canônico (`sort_keys`, sem espaço, UTF-8) de `descrever()` de cada especificação em ordem de número: nome, função, semver, descrição, classe, serviço, pré-condições, timeout, execução, idempotência, bancos, flag, `usa_cpf`, os JSON Schemas de entrada e saída **e a allowlist do modelo** (`PROJECAO_DAS_FERRAMENTAS`): abrir uma chave da allowlist pede `numero` novo. O histórico mora em `ferramentas/catalogo_versoes.json` (1, 2, 3… sem buraco, hash novo a cada número). Para versionar: `uv run python -m ia_atendimento.ferramentas.catalogo` imprime o hash | F §Gateway 1; D-29 |
| D4 | O `numero` do JSON é o de `ia.artefato_versao(tipo='catalogo')`. A 0001 não traz seed (o dono aprova a v1): **inserir a linha é ato do dono** (kit da S4), e a B1.6 grava `versao_vigente().numero` em `atendimento.catalogo_versao`. Nenhuma migração nesta etapa | 0001; I |
| D5 | **Esquemas `extra=forbid` em todos os níveis**, conferidos recursivamente na subida (`EsquemaInvalido`). A entrada de ferramenta do modelo só tem nomes de `REFERENCIAS_DO_MODELO` (`oferta_ref`, `opcao_ref`, `confirmacao_id`, `tentativa_ref`, `alvo`); os 20 nomes de `CAMPOS_PROIBIDOS_NA_ENTRADA` (CPF, banco, valor, parcela, prazo, tabela, coeficiente, vendedor, destino, URL, telefone, e-mail, nome…) são recusados em QUALQUER ferramenta, salvo a T6 (o valor do cliente vai ao validador e ao cofre sem passar pelo modelo, B5.3) | F §Gateway 2 |
| D6 | **Referências.** O modelo cita só o apelido que o contexto lhe deu (`oferta-1`); o gateway troca pelo id real e pergunta ao `ResolvedorDeReferencias` (injetado; a B1.6 lê o estado) se é deste atendimento e de qual banco. Apelido que o contexto não deu, ou id de outro atendimento ⇒ `PARAMETRO_INVALIDO` («Se der errado» do roteiro). **Sem resolvedor, só o apelido do próprio contexto vale**: o código não passa id cru sem conferência (fail-closed) | F §Gateway 2; roteiro |
| D7 | **Saída em três cercas.** (1) `reconstruir`: só as chaves do esquema de saída entram, o resto é descartado NA CHEGADA (D-29) e o que sobra tem de cumprir o esquema (senão `DESCONHECIDO`, sem eco); e todo `str` que sobra é varrido por conteúdo: CPF, telefone, e-mail, CEP (a máscara) ou 11 dígitos com forma de CPF ⇒ `DESCONHECIDO`, porque `dados` é do lado do código e a B1.6 o grava (D18; revisão, M-6). Uuid e número longo sem forma de documento (proposta do banco, `[NUMERO]`) passam; (2) `para_projetar`: URL vira `{{link}}`, texto que a máscara de PII troca some, padrões (`false`, `[]`) não vão; (3) a projeção da B1.4 (`proteger_retorno`), uma vez só. Valores em reais ficam do lado do código; `formatar_brl` formata o que for ao cliente | F §Gateway 7; D-29 |
| D8 | **Destino** (`modo.py`): a FACTA de produção **só em `real`** (roteiro B5.1); em `teste` vai a `FACTA_BASE_TESTE` (sem ela, `MODO_SOMENTE_LEITURA`, nunca a produção); em `duble`/`sombra` fica interceptada. Leitura do 360/3RN/C6: `teste` ⇒ fixture (mesmo com posse real: a pessoa é sintética); `duble` ⇒ fixture, salvo posse real sob parada dura ⇒ produção só leitura; `sombra` ⇒ produção só leitura (08 §6, Tabela final). Leitura paga e efeito fora de `real` ⇒ interceptado. **Leitura da FACTA (T5, T8, T9) com posse real em `duble`/`sombra` ⇒ `MODO_SOMENTE_LEITURA`**: nem a produção (roteiro) nem o simulador, que diria `nao_criada` a uma digitação que pode existir (revisão, M-7; decisão do dono pendente, ver abaixo). **Divergência registrada:** a linha «Ler» de 08 §6 manda a FACTA (T5) ler o real em `sombra`; aqui vale o roteiro, mais restritivo. O teste `test_teste_e_sombra_nunca_resolvem_host_de_producao` prova «nunca» para `teste` em todo serviço e para `sombra` na FACTA e em todo efeito; a leitura do 360/3RN/C6 em `sombra` é a exceção do contrato, com `somente_leitura=True` | roteiro B5.1; 08 §6; DECISOES-B2.4 |
| D9 | **`modo_efetivo`** = o mais restritivo (real > teste > duble > sombra). Valor desconhecido, `teste` global ou `None` ⇒ `sombra`. `LeitorDeModo` relê o `config.modo` com cache ≤ 5 s (relógio injetado); leitura que falha vale `sombra` e não entra no cache. **O destino é resolvido na hora do efeito: depois das pré-condições, depois da vaga do limitador e, se o CPF é lido, de novo depois da leitura**; entre o último `_resolver` e o `await` do executor não há ponto de espera. A parada dura alcança o efeito em curso, inclusive a T7 na fila atrás de duas T8 (revisão, A-1) | P-R7; R2-02; D-15 |
| D10 | **`Destinos` recusa subir** com URL fora de `https` (http só em loopback), com credencial, query ou fragmento, ou com o host de teste igual ao da produção (F §Gateway 11). As URLs saem de `Destinos.de_ambiente` (`FACTA_BASE`, `FACTA_BASE_TESTE`, `C360_BASE`, `TRN_BASE`, `C6_BASE`); o `Settings` **não** ganhou campos nesta etapa. O repr não mostra URL | F §Gateway 11 |
| D11 | **CPF em memória** (D18). `CpfEmMemoria`: `repr`/`str`/`format` mascarados, sem `__dict__`, `json.dumps`, `pickle` e `copy` levantam. O gateway o lê a cada chamada, **só** para ferramenta com `usa_cpf` (T1, T5, T7, T8) e destino de produção ou dublê (fixture e interceptado não leem), entrega ao executor e não o põe em `RegistroDaChamada`, span, log nem `Resultado`. Sem leitor, leitor que falha ou pessoa sem CPF ⇒ `DESCONHECIDO`. A mensagem de exceção do executor nunca é registrada | D18; E-1; regra 2 |
| D12 | **Erros tipados** de vocabulário fechado (14 códigos de F §Gateway 5) e **13 pré-condições** nomeadas (as 12 da T7 com opt-out e não perturbe separados). O modelo recebe só `{"erro": código}` (e `precondicao` em `PRECONDICAO_FALHOU`); `proteger_retorno` só deixa passar o envelope com valores do vocabulário | F §Gateway 3, 5 |
| D13 | **Pré-condições fail-closed:** cada nome declarado precisa de verificador que devolva exatamente `True` (síncrono ou não); sem verificador, com exceção ou outra resposta ⇒ `PRECONDICAO_FALHOU{nome}`. Banco fora de `spec.bancos` ou da flag `bancos_digitacao` (`bancos_ligados`, injetado; padrão: nenhum) ⇒ `banco_habilitado` | F §Gateway 3; mem(w) |
| D14 | **Orçamento.** Por turno (`OrcamentoDoTurno`, novo a cada `executar_turno` em `Deps.orcamento`; sem ele, esgotado): ≤ 4 síncronas e ≤ 5 s. A vaga da síncrona é **reservada** na conferência, sem `await` entre conferir e contar (o Pydantic AI roda as tools em paralelo; revisão, M-1), e conta mesmo se a chamada parar numa pré-condição (teto de tentativas). O timeout da síncrona é o menor entre o da ferramenta e o que resta do turno e **cobre a fila do limitador** (revisão, M-2); assíncronas não contam. Por atendimento (`ContadorDoAtendimento`): ≤ 2 pagas, **contadas no disparo** (a tentativa, que o banco cobra mesmo com falha; atômica), e ≤ 3 corrigíveis (a `classe` `corrigivel` da saída e o `CORRIGIVEL` tipado do executor; revisão, M-3). O contador é **em memória**: a B1.6 o troca pela contagem do ledger | roteiro B5.1; F §Gateway 6 |
| D15 | **Classificação da falha.** Timeout de leitura, ou na fila do limitador, ⇒ `BANCO_INDISPONIVEL`; falha (timeout ou exceção) de efeito irreversível **já disparado** ⇒ `INDETERMINADO` (regra 12: vai ao T8, nunca reenvia); antes do disparo nada saiu e não é dúvida; outra exceção ⇒ `DESCONHECIDO`. A assíncrona tem um prazo para a fila e o do efeito recomeça ao pegar a vaga. O executor pode levantar um `ErroDeFerramenta` (`CORRIGIVEL`, `RECUSA`…): o `Resultado` guarda uma **cópia nova** (`copia_limpa`), sem `__cause__`, `__context__` nem `__traceback__` (revisão, M-4) | regra 12; F §Gateway 5 |
| D16 | **Limitador por serviço** (concorrência): FACTA 2, 3RN 2, C6 1. A T5 vai ao serviço do banco da oferta referenciada. A vaga vem **antes** do destino (o serviço não depende do modo): o simulador também ocupa vaga, como antes | F §Gateway 10 |
| D17 | **As `Tool` do agente vêm do registro** (`Gateway.ferramentas_do_agente`, aceite): `Tool.from_schema` com o esquema de entrada da especificação (`additionalProperties: false`) e a descrição do catálogo; continuam passando pela capability da B1.4 (fase e projeção). `registrar` aceita `Tool` (nome igual à chave) | roteiro B5.1 «Aceite» |
| D18 | **Registro da chamada** (`RegistroDaChamada`, callback injetado): `ferramenta` (`t3`, CHECK da 0001), semver, classe, resultado (`ok` ou o código), `modo_efetivo`, destino, `simulado` (= modo ≠ real), latência, `args_hash` (sha256 dos argumentos com os ids reais) e banco. Sem CPF, sem valor, sem id em claro. Span `ia.ferramenta` e uma linha de log, só com códigos | F §Gateway 8 |

## O que ficou de fora (e de quem é)

- **Ledger de verdade** (`ferramenta_chamada` `reservada` antes da chamada, `idem_key`, CAS de estado, chaves `t7:{atd}:FACTA:{oferta}:{versao}:{n}`) e a contagem de pagas/corrigíveis que sobrevive a reinício: B1.6/B5.4. O `RegistroDaChamada` já tem a forma.
- **Batimento antes de cada efeito real** (08 §7.4, D-15): o gateway não o consulta; é da B1.6 (`executar_efeito`/`Canal`). Até lá, nenhum executor real deve ser ligado.
- **`posse_real`** é passado pelo chamador (predicado do ledger, B1.6); `Deps.posse_real` nasce `false`.
- **Executores** (360 de dev, fixtures `pessoas_teste`, `FixturesDuble`, dublê da FACTA) e o limitador de **taxa** do C6 (0,5 req/s): B5.2–B5.4. Aqui só a concorrência.
- **Fluxo assíncrono** (job Procrastinate, `EM_ANDAMENTO`, mensagem-ponte TX-14): B5.4. A T7/T8 estão no catálogo como `assincrona` (fora do orçamento do turno).
- **Regra do semver no meio do atendimento** (patch sim, minor/major só em atendimento novo): não é imposta aqui; o atendimento fixa `catalogo_versao` (B1.6).
- **Prontidão**: o `/readyz` não confere `versao_vigente()` contra `artefato_versao` no banco. Sugestão para a B1.6/A4.6.
- **T2 na forma de D-29** (`pares`, `tentativa_ia`, `bloqueios`) e os campos do lado do código de T1/T3/T5/T7–T9/T13 são **HIPÓTESE** até a B5.2–B5.4; mudar qualquer um muda o hash e pede o `numero` 2.
- **O caminho `montar_contexto(resultados=…)`** (o `Turno.ferramenta`, sem function calling) projeta pela allowlist do contexto, que não tem `erro`: o envelope de erro não chega por ali. A B5.5 decide se o código usa esse caminho.
- **R2-09 da B1.4** (função comum registrada sem validar parâmetros): as `Tool` do gateway cumprem; `registrar` ainda aceita função comum (os testes da B1.4 a usam).
- **Lista de hosts de produção**: `Destinos` só recusa o teste igual à produção; não sabe quais hosts são de produção. HIPÓTESE a fechar no kit da VPS (A4.9/A4.10).
- Cobertura não medida por ferramenta (o `pytest-cov` não está nas dependências); os mutantes acima cobrem os caminhos de segurança.

## Revisão independente (04/11, `docs/REVISAO-B5.1-0411.md`): o que foi corrigido

Cada correção tem teste que reprova no código revisado (`493c068`), conferido rodando os testes novos contra o `src` antigo (21 reprovam) e,
para as lacunas de teste, com o mutante da revisão (M6, M8 e M9 agora morrem), além de mutantes das correções (sem reler o destino depois do
CPF, sem o `reschedule` da assíncrona, `INDETERMINADO` sem `despachado`, sem a forma de CPF na chegada): todos morrem. Testes em
`tests/test_ferramentas_gateway_revisao.py`, `tests/test_ferramentas_modo.py` e `tests/test_ferramentas_registro.py`.

| Achado | Correção |
|---|---|
| A-1 (ALTO) parada dura não alcança a T7 na fila nem durante a leitura do CPF | vaga → destino → CPF → destino de novo → executor (D9) |
| M-1 síncronas em paralelo furam o teto | `OrcamentoDoTurno.reservar()` atômico na conferência; `gastar` só acerta o tempo (D14) |
| M-2 timeout não cobre a fila | `asyncio.timeout` por fora do semáforo; assíncrona com `reschedule` ao pegar a vaga; `despachado` separa fila de efeito (D15) |
| M-3 `CORRIGIVEL` tipado não conta; paga só no sucesso | conta o tipado disparado; `reservar_paga` no disparo, atômico (D14) |
| M-4 erro tipado guarda a causa com PII | `ErroDeFerramenta.copia_limpa()` em `chamar`; o tipado do executor é refeito fora do `except` (D15) |
| M-5 histórico do catálogo reescrevível | `conferir_historico` + `scripts/conferir_catalogo.py` no `check.sh` contra a `origin/main` (estrito: base ausente falha; `CATALOGO_BASE_REF` troca a base) |
| M-6 `Resultado.dados` aceita CPF | varredura por conteúdo de todo `str` na chegada (D7) |
| M-7 T8 real sob parada dura sai simulada | correção mínima fail-closed: leitura da FACTA com posse real fora de `real`/`teste` ⇒ `MODO_SOMENTE_LEITURA` (D8) |
| B-1, B-2, B-3 lacunas de teste | testes novos que matam M6, M8 e M9 |
| B-4 recusa na entrada sem registro | ferramenta do catálogo pedida pelo modelo sem ser dele vai ao `RegistroDaChamada` e ao span (`parametro_invalido`) |

### O que não foi corrigido, e por quê

- **B-5 (`LeitorDeModo.config` síncrono).** Hoje o leitor é injetado e lê memória; a leitura do `config.modo` no banco é da B1.6, que decide
  a forma (pré-carga por outro laço, ou `config` assíncrono). Mudar a interface agora, sem o chamador real, seria desenho especulativo.
  Fica para a B1.6: quem ligar o banco ali não pode bloquear o laço.
- **B-4, parte do nome desconhecido.** Ferramenta fora do catálogo (`T4`, nome inventado) segue só na linha de log: não tem nome válido para o
  CHECK `ferramenta` da 0001 nem versão. A B1.6 pode contar essas linhas de log no alerta.
- **M-7, a decisão de fundo.** A correção é a mínima (nem produção nem simulador). Seguir o contrato (FACTA «Ler real, só leitura» com posse
  real) ou manter o roteiro é **decisão do dono/PD**, junto com a pendência 1 abaixo. Até lá, a T5/T8/T9 de atendimento com posse real sob
  parada dura devolve `MODO_SOMENTE_LEITURA`.
- **A-1, mudança para menos restritivo durante a espera** (`sombra` → `real` enquanto a T7 espera): o destino relido é o da hora, `real`.
  É o comportamento pedido («relido a cada efeito»); o batimento antes do efeito real continua sendo da B1.6.
- **A reserva da vaga síncrona conta a tentativa** que para numa pré-condição: mais restritivo que antes, de propósito (sem devolução de vaga,
  que reabriria a corrida do M-1).

## Pendências para o revisor (PD-5) e emendas fora do repositório

1. Conferir D8: FACTA em `sombra` interceptada (roteiro) × «Ler real» (08 §6). Se o contrato prevalecer, muda uma linha de `Destinos.resolver` e o teste.
2. Conferir D8: T5 de 3RN/C6 em `sombra` lê o real (08 §6); custo e limites do C6 com CPF real na sombra.
3. Emenda do roteiro B5.1: o aceite «o registro gera as `Tool` do agente» está em `test_ferramentas_agente.py`; «Conferir» passa a `pytest tests/test_ferramentas*.py`.
4. Emenda do estudo F §Gateway 9 e roteiro B5.4: a chave `t7:` segue com a B5.4 (não entrou aqui).
