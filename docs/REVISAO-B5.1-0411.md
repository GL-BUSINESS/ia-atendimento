# B5.1 · Revisão independente (04/11)

Revisor: Claude de contexto limpo (não escreveu o código). Segundo revisor: Codex `gpt-6.1-sol`, `xhigh`, só leitura (rodou; saída completa no
scratchpad da sessão, `codex-b5-1.txt`). Alvo: `origin/main...feat/b5-1` (`9bee6a4..493c068`, 5 commits, 22 arquivos, +2.797/−6), contra o
roteiro v3.3 B5.1, o contrato 08 §6 (Tabela final), D-15, D-29, D18, P-R7, R2-02 e `docs/DECISOES-B5.1-0411.md`.

Origem: **[C]** Claude, **[X]** Codex, **[C+X]** os dois acharam sem combinar. Todo achado marcado «provado» foi reproduzido com uma sonda
fora do repositório (scripts no scratchpad, usando `tests/apoio_gateway.py`), sem alterar código.

## Veredito

**Não aceitar como está.** O portão está verde e a estrutura segue a spec (registro, hash, referências opacas, allowlist, `modo_efetivo` na
hora do efeito, CPF em memória). Mas há **1 achado ALTO** (a parada dura não alcança o efeito que está esperando a vaga do limitador) e
**7 MÉDIOS** (orçamento, limitador, contagem de corrigíveis, PII na causa do erro e nos dados do lado do código, histórico do catálogo
reescrevível, T8 simulado para tentativa real). Todos são correções locais pequenas no `gateway.py`, `saida.py` e no portão. Nada aqui pede
migração.

## Portão

`BANCOS_DUBLE_PATH=/home/danilo/wt-ia/bancos-duble-main-b16a` (detached em `origin/main` `f6ec889`) `flock ~/.c360-pesado.lock bash scripts/check.sh`:
**verde**, `3359 passed, 1 skipped (yaml), 1 xfailed (B1.6)` em 373 s. Lock, ruff, format, varredura, gitleaks, checksum da 0001, 0002 e
`pessoas_teste` OK. A branch está em dia com a `origin/main` (merge-base = `9bee6a4`). Bate com o número das DECISOES.

## Mutação (teste que reprova sem a mudança)

Numa cópia (`git archive HEAD`) fora do worktree, um mutante por vez:

| Mutante | Resultado |
|---|---|
| M1 destino resolvido ANTES das pré-condições | morto (`test_parada_dura_muda_o_roteamento_do_efeito_ja_em_curso`) |
| M2 FACTA em `teste` recebe a URL de produção | morto (`test_teste_e_sombra_*`) |
| M3 `reconstruir` sem o filtro da allowlist | morto (`test_saida_fora_da_allowlist_e_descartada`) |
| M4 `conferir_versao` ignora o hash | morto (`test_catalogo_hash_muda_sem_versao_falha_ci`) |
| M5 CPF lido também para fixture/interceptado | morto (`test_fixture_e_interceptado_nao_leem_cpf`) |
| M7 modo desconhecido vale `real` | morto (`test_ferramentas_modo.py`) |
| M10 sem o limitador por serviço | morto (`test_limitador_da_facta_*`) |
| **M6** subida aceita campo proibido na entrada | **sobrevive** às 152 do pacote (ver B-1) |
| **M8** varredura de `para_projetar` sem a máscara de PII | **sobrevive** às 152 (ver B-2) |
| **M9** `_vale` sem `await` da pré-condição assíncrona | **sobrevive** às 152 (ver B-3) |

Os seis testes nomeados no roteiro existem e cinco deles morrem com o mutante do seu ponto. Os três sobreviventes são lacunas de teste, não
de código.

## Achados

### ALTO

**A-1 [C+X] A parada dura não alcança o efeito que espera a vaga do limitador (provado).** `gateway.py:223` resolve o destino e só depois
`_executar` lê o CPF (`:303`) e espera o semáforo (`:325`). A T7 que entra na fila da FACTA atrás de duas T8 (timeout de 1.500 s cada) guarda
o destino `producao/real` resolvido antes da espera. Sonda: duas T8 seguram as vagas; a T7 entra; `config.modo` vira `sombra` e o relógio
passa de 5 s; as T8 soltam ⇒ **a T7 roda com `destino=producao`, `modo_efetivo=real`**. O Codex reproduziu a mesma janela durante a leitura
do CPF. O teste nomeado só muda o modo durante as pré-condições, antes da janela. Fere R2-02/P-R7 («relido a cada efeito») e D-15.
Correção: pegar a vaga do limitador (o serviço não depende do modo) e ler o CPF **antes** de `_resolver`, e resolver o destino logo antes de
`await funcao(chamada)`; teste com parada dura durante a espera do semáforo e durante a leitura do CPF.

### MÉDIOS

**M-1 [C+X] Chamadas síncronas concorrentes furam o orçamento do turno (provado).** `gateway.py:270-278` confere `orcamento.cabe()` antes e
só debita em `_rodar` (`:336-337`), depois do executor. O Pydantic AI 2.63 roda as function tools **em paralelo** por padrão
(`_tool_execution.py`, modo `parallel`). Sonda: 6 T3 concorrentes no mesmo `OrcamentoDoTurno` ⇒ 6 executadas, 6 ok, `sincronas=6` (teto 4).
O teste do roteiro chama em sequência. Correção: reservar a vaga (`sincronas += 1`) no `_conferir_orcamento`, de forma atômica no laço, e
acertar só o tempo no fim; ou marcar as `Tool` do gateway como `sequential=True`. Teste com `asyncio.gather` de 5.

**M-2 [C+X] O timeout não cobre a espera do limitador (provado).** `gateway.py:325`: `async with limitador, asyncio.timeout(prazo)` pega a
vaga **antes** de começar o prazo, e o `prazo` é calculado antes da espera. Sonda: T5 síncrona com timeout de 0,05 s atrás de duas T8 de
0,5 s ⇒ `ok` em 0,49 s e `orcamento.segundos=0,49`. Com T8 de 1.500 s na mesma instância, uma T5 do modelo pode pendurar o turno muito além
dos 5 s. Correção: `asyncio.timeout` por fora do semáforo para as síncronas (espera na fila conta e estoura como `BANCO_INDISPONIVEL`); para
a T7, timeout na fila não pode virar `INDETERMINADO` (nada saiu): separar a espera da vaga do timeout do efeito.

**M-3 [C+X] `CORRIGIVEL` tipado não conta no teto de 3 por atendimento (provado).** `gateway.py:307-310`: o `ErroDeFerramenta` do executor é
relançado antes de `_contar`. D15 das DECISOES convida o executor a levantar `CORRIGIVEL`. Sonda: 5 T7 com `raise
ErroDeFerramenta("CORRIGIVEL")` ⇒ 5 executadas, contador 0. O teste só cobre a saída `{"classe": "corrigivel"}`. Correção: contar o código
`CORRIGIVEL` também; e, para `leitura_paga`, contar a tentativa (o banco cobra mesmo com resposta inválida ou timeout) — hoje só conta o
sucesso (sem T4 no MVP, impacto futuro).

**M-4 [C+X] O erro tipado do executor guarda a causa com PII (provado).** `gateway.py:327-328, 307-308`: o gateway reaproveita a exceção do
executor. Executor que faz `except HTTPError: raise ErroDeFerramenta("RECUSA")` deixa em `Resultado.erro.__context__` a exceção original
(sonda: `RuntimeError` com o CPF na mensagem) e o `__traceback__` com os frames que têm o `CpfEmMemoria` revelado. Qualquer
`registro.exception`/`exc_info` da B1.6 sobre `resultado.erro` vaza. O teste `test_excecao_do_executor_vira_desconhecido_sem_eco` só cobre a
exceção genérica. Correção: reconstruir `ErroDeFerramenta(erro.codigo, precondicao=…, retry_apos_s=…)` novo, fora do `except`, e testar
`__context__ is None and __cause__ is None` para o caso tipado.

**M-5 [X, confirmado por C] Dá para mudar o catálogo sem `numero` novo reescrevendo o histórico.** `catalogo.py:109-120` confere só que a
última linha de `catalogo_versoes.json` tem o hash atual. Trocar o `hash` da linha `numero: 1` passa no portão com o catálogo mudado. O
critério do roteiro é «o CI falha se o hash mudar sem novo `numero`»; como o `numero` é o de `artefato_versao` e o atendimento grava
`catalogo_versao`, reescrever a linha 1 quebra a reprodutibilidade de quem já gravou 1. Correção: no `check.sh`, conferir que as linhas do
JSON na `origin/main` continuam idênticas (só acréscimo no fim); teste com histórico «reescrito».

**M-6 [X, rebaixado por C] A varredura por conteúdo só existe no caminho do modelo; `Resultado.dados` aceita CPF (provado).** `saida.py:42-49`
reconstrói pelo esquema sem varrer conteúdo; a varredura (`_varrer`) só roda em `para_projetar`. Sonda: T1 com `primeiro_nome =
"000.000.012-34"` ⇒ `ok` e o CPF em `r1.dados`; T3 com `oferta_ref = "00000001234"` (cabe no `IdOpaco`) ⇒ o CPF em `r3.dados` e no mapa de
apelidos (`{"oferta-1": "00000001234"}`). Ao modelo **não chega** (a projeção troca pelo apelido; conferido), por isso MÉDIO e não ALTO.
Mas D18 diz «CPF só na memória do gateway» e a B1.6 vai persistir/registrar `dados`. Correção: rodar a máscara de PII em todo `str` na
chegada (falha ⇒ `DESCONHECIDO`), e apertar `IdOpaco` (por exemplo, recusar 11 dígitos puros) ou exigir forma de uuid onde o id é uuid.

**M-7 [C] T8 de uma tentativa real sai simulada sob parada dura (provado).** `modo.py:156-158`: FACTA fora de `real`/`teste` é sempre
`interceptado`, inclusive a T8 (classe `leitura`) com `posse_real=True`. Sonda: atendimento `real` com posse real, `config.modo=sombra`, T8 da
tentativa real ⇒ roda o **simulador** e devolve `estado=nao_criada` para uma digitação que pode ter sido criada de verdade. A Tabela final de
08 §6 manda «Ler … real, só leitura» com posse real. É a pendência 1 das DECISOES, mas o caso T8 é mais grave que o T5: resolver um
`INDETERMINADO` real com resposta simulada abre caminho a redigitar (proposta duplicada) quando a parada sair. Correção mínima antes da
B5.4: T8 (e T9) interceptada com `posse_real=True` ⇒ `MODO_SOMENTE_LEITURA`, nunca o simulador; ou seguir o contrato (FACTA só leitura).
**Decisão para o dono/PD** junto com a pendência 1.

### BAIXOS

**B-1 [C] A regra «campo proibido em qualquer ferramenta» não tem teste (M6 sobrevive).** `especificacao.py:190` só é exercitada por
ferramenta do modelo, onde a regra seguinte (`campos - REFERENCIAS_DO_MODELO`) já recusa. Falta um caso `do_modelo=False` com `cpf`/`valor`.

**B-2 [C+X] `test_url_e_texto_com_pii_nao_chegam_ao_modelo_nem_por_campo_permitido` não testa texto com PII (M8 sobrevive).**
`test_ferramentas_gateway.py:186` só usa URL. Tirar `mascarar` de `_varrer` não derruba nada (a terceira cerca, `auditar_textos`, ainda
existe, mas a segunda fica sem prova). Falta PII em campo permitido de texto.

**B-3 [C+X] `test_precondicao_assincrona_e_aceita` não prova a aceitação (M9 sobrevive).** `test_ferramentas_gateway.py:304`: o verificador
devolve `False`; sem o `await`, a corrotina também não é `True` e o teste passa. Falta o caso assíncrono que devolve `True` e deixa a T7 rodar.

**B-4 [C] Chamada recusada na entrada não vai ao registro nem ao span.** `gateway.py:212-215`: ferramenta fora do catálogo ou do modelo só
loga; sem `RegistroDaChamada` nem `ia.ferramenta`. O modelo tentando o que não pode é sinal útil para o ledger/alerta.

**B-5 [C] `LeitorDeModo.config` é síncrono.** `modo.py:63-73`: na B1.6 a leitura do `config.modo` vai ao banco dentro do laço async.
Anotar na interface (ou aceitar `Awaitable`) antes de ligar.

## Descartados

- **[X] «A fixture viola a regra global de CPF; usar só 000.000.000-00» (`apoio_gateway.py:21`).** A regra da tarefa é a faixa
  `000.000.0nn`; `000.000.012-34` está nela. Descartado.
- **[X] «Os testes com agente sofreram timeout».** Foi o sandbox só leitura do Codex. No portão, `tests/test_ferramentas_agente.py` passou.

## Aderência à spec (o que está certo)

- Registro versionado com todos os itens do roteiro; `extra=forbid` conferido recursivamente na subida; `catalogo_hash` canônico com a
  allowlist dentro (D3); o `numero` amarrado a `artefato_versao` sem seed (D4, ato do dono).
- Modelo só com referências opacas; apelido de fora do contexto ou id de outro atendimento ⇒ `PARAMETRO_INVALIDO` (o «Se der errado» do
  roteiro); sem resolvedor, nada de id cru (fail-closed).
- Saída reconstruída pelo esquema, descarte na chegada, URL ⇒ `{{link}}`, `formatar_brl` no código; envelope de erro de vocabulário fechado.
- `modo_efetivo` = o mais restritivo, desconhecido ⇒ `sombra`, cache ≤ 5 s, falha de leitura não cacheia; FACTA de produção só em `real`;
  `teste` sem dublê nunca cai na produção; `Destinos` recusa URL ruim e dublê = produção.
- `CpfEmMemoria` não se mostra nem serializa; o CPF não vai a registro, span, log nem retorno ao modelo; nenhuma migração com coluna de CPF.
- As `Tool` do agente saem do registro e continuam pela capability da B1.4 (fase + projeção).
- Nenhuma migração, nada de produção, só DeepSeek/Fireworks (nada da Anthropic na operação), fixtures na faixa `000.000.0nn` (PD-6).

## Pendências que ficam

1. Corrigir A-1 e M-1 a M-6 (código + teste que reprova sem a correção) antes de abrir o PR.
2. M-7 e as pendências 1 e 2 das DECISOES (FACTA em `sombra`, T5 de 3RN/C6 em `sombra`): decisão do dono/PD.
3. Aceite formal só depois da B1.6 (roteiro: «aceite após B1.6»).
4. Emendas já listadas nas DECISOES (3 e 4): «Conferir» passa a `pytest tests/test_ferramentas*.py`; chave `t7:` com a B5.4.
