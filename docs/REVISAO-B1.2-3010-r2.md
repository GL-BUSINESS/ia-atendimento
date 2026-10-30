# Re-revisão adversarial B1.2 (30/10) — branch `feat/b1-2-linha-tempo`, commit 7473563

Revisor de contexto limpo, só leitura. Tudo foi **rodado** (PG 18 descartável, papel `ia_app_a`) salvo onde marcado «lido».
Baseline: `bash scripts/check.sh` verde (851 passed, 2 xfailed). Experimentos fora do repo (`.../scratchpad/r2/test_r2a.py`, `test_r2b.py`);
mutação numa cópia (`.../scratchpad/r2/mut`), 11 mutantes, todos mortos (tabela no fim).

## Veredito: APROVAR COM CORREÇÕES (0 crítico, 0 alto, 4 médios, 3 baixos)

A1–A3 e M1–M7 estão fechados **nos caminhos que o autor testou**. Dois fechamentos têm furo residual real (A1: o «código» não é catálogo;
A2: só o construtor está coberto, não `model_validate`). Os achados S3/S4 da revisão de segurança procedem, ambos latentes (dependem de P2/P3).

## Fechados (provado)
- **Vetor do contrato:** `msg_chave` = `cg:0123456789abcdef01234567:be0f44572b7488ed` e `msg_fingerprint` = `d91e6bf4176d42e4a6af732ecda90217a3bbcdea5aadf9de756a8ac087a06dd4`
  recalculados à mão (HMAC com `chave-fingerprint-de-teste-descartavel-01`, prefixo `ia-evento/v1\n`): **batem**. O vetor não tinha nomes, então a reversão do
  M5 não o move. O texto do contrato §5.1 ainda diz «mascarado, inclusive os nomes da conversa»: está desatualizado (ver R2-7).
- **A1:** conversa completa (mensagem recebida, troca, cofre, decisão, erro, anotação, resumo recusado, `consumir` com versão errada e ordem inexistente) com
  marcador único: dump de `ia.*`/`procrastinate.*` só acha o marcador onde o regex de código o deixa passar (R2-2). Nenhuma exceção
  (`format_exception`+`repr`+`__dict__`) nem registro de log (`caplog` DEBUG) o contém; `PassoRecusadoPeloBanco` sem causa nem contexto; `ConflitoDeVersao` sem texto.
- **A2:** `repr`/`str` de `EventoMensagem`, `Troca`, `Conversa` limpos; `EventoMensagem(...)`, `DecisaoModelo(...)`, `AnotacaoOperador(...)` e `criar(...)` com erro
  levantam `EntradaInvalida` sem texto e sem `__context__`. (`model_dump()`, `__dict__`, `dataclasses.asdict` carregam o texto: inevitável num objeto de valor; ninguém os loga.)
- **A3:** dois «sim» no mesmo segundo com `mensagem_id` diferente → `Gravada, Gravada`; mesmo id → `Duplicada`; sem id e com hora → `Gravada, Duplicada`
  (colapso aceito pelo estudo B linha 92, «ok ok»); sem id e sem hora com `recebido_em` diferente (1 µs) → 2 `Gravada`; mesmo `recebido_em` → `Duplicada`;
  `identidade()` sem `recebido_em` e `recebido_em` naive → `ValueError`. O dedupe **permanente** do roteiro vale (índice único global; `ON CONFLICT` coberto).
  `cgid:` × `rpa:` e `cg:` × `rpa:` do mesmo conteúdo → 2 `Gravada` (M4, esperado: o `casar` é da B1.5).
- **Gancho `casar`:** roda dentro do `FOR UPDATE`, depois da busca exata e antes do INSERT; chamado em **todo** caminho que chega ao INSERT (webhook, replay, reconciliação).
  Não roda em `Duplicada`/`Conflito` (a busca exata vem antes: desenho certo). Mutante «casar fora do lock» morre.
- **M1:** `criado_em/expira_em/criada_em/apagar_em` do `now()` do banco (provado com `agora` = out/2026 e relógio real = 30/10: `expira_em − criado_em` = 7 d, `apagar_em − criada_em` = 30 d);
  guardar de novo não passa de `criado_em + 7 d`.
- **M3:** `nomes` sem default em `gravar_troca` e `gravar_resumo` (omitido → `TypeError`; `None` → `NomesIndisponiveis`); anotação sem nomes → `EntradaInvalida`;
  `gravar_passo` repete a checagem (2ª cerca, `PassoComPii`); `substituto` (`[dado:pix]`) não exige nomes (nem lê o valor: correto). `nomes=()` explícito grava nome (responsabilidade do chamador).
- **M5/regressão do fingerprint sem nomes:** a mesma frase com nome diferente **não** colapsa (os nomes não são mascarados, o texto difere → fingerprints diferentes;
  e o `h16` usa o texto cru). Só colapsam textos que diferem **só em PII** (CPF/telefone/e-mail), e apenas quando a `msg_chave` já é igual (`cgid:` igual): para isso é `Duplicada`, o que é
  aceitável (mesmo id = mesma mensagem). Aceitável, desde que o contrato seja corrigido.
- **xfail strict:** `ultimo_cliente_em` (`tests/test_conversa.py:237-248`) é honesto: a coluna existe em `feat/b1-1-estado` (`0003`, `ia.atendimento.ultimo_cliente_em`); ao integrar, o strict
  fica vermelho e força a remoção. O de `casar` (`tests/test_linha_tempo.py:490-496`) é honesto no motivo mas **inócuo** (R2-6).
- **Mutação:** os 11 mutantes das correções morrem (ver «Tautologia»).

## Achados

### R2-1 · MÉDIO · A2 incompleto: `model_validate`, `model_validate_json` e `TypeAdapter` vazam o texto (`scrubber.py:61-70`)
`ModeloSemEco.__init__` só intercepta o construtor. O Pydantic não chama `__init__` em `model_validate*`/`TypeAdapter(...).validate_python`: o `ValidationError`
sai cru e `errors()`/`.json()` trazem o `input` (provado: `EventoMensagem.model_validate({... "texto": M, "origem_evento": "reconciliacao"})` → `M in ex.errors()` = True,
`M in ex.json()` = True; idem `model_validate_json` e `DecisaoModelo.model_validate`; `str(ex)` limpo). É exatamente o caminho que a B1.5 (FastAPI) usa para tipar o corpo, e o 422 padrão ecoa `input`.
**Correção:** sobrescrever `model_validate` e `model_validate_json` em `ModeloSemEco` (mesma conversão via `erros_sem_input`) e, na B1.5, um `exception_handler` de `RequestValidationError` que
descarte `input`/`ctx`. **Caso que reprova hoje:** `with pytest.raises(EntradaInvalida): EventoMensagem.model_validate({...reconciliacao sem rpa_id, texto: M})`.

### R2-2 · MÉDIO · A1 incompleto: «código de catálogo» é só um regex; palavras e dígitos do cliente passam e ficam 365 d (`passos.py:30,84,107,127,…`)
`Codigo40 = ^[a-z0-9_]{1,40}$` não é lista fechada. Provado: `criar("decisao", motivo="cpf_52998224725")` e `motivo="joao_carlos_silva"` são aceitos; no dump, `ia.passo.motivo =
cliente_disse_zebraquantica` e `peca = zebraquantica`, `intencao = zebraquantica`, `objecao = joao_carlos_zebraquantica` (`ia_leitura` lê). O CPF em dígitos corridos escapa porque a
máscara nunca roda nas colunas-código. O teste do autor (`tests/test_linha_tempo.py:392`) usa marcador com hífens, que o regex recusa de qualquer jeito: nunca exercita o caso que importa.
**Correção:** enumerar `motivo`/`objecao`/`transversal`/`intencao`/`peca` quando o catálogo existir (B1.4/B5); até lá, no validador de `Codigo40`: recusar corrida de ≥ 4 dígitos e passar
`valor.replace("_", " ")` por `mascarar(..., nomes)` (os nomes já estão no `ContextVar`), e recusar token ≥ 4 letras que apareça na mensagem do turno. **Caso:** `criar("decisao", motivo="cpf_52998224725")` e
`criar("decisao", nomes=["João Carlos"], motivo="joao_carlos")` devem levantar `EntradaInvalida`.

### R2-3 · MÉDIO · M2: o mês da chave é UTC, sem normalizar, e a virada derruba escrita por até 3 h (`conversa.py:85-101`)
`chave_id_do_mes` usa `agora.year/month` sem `astimezone(UTC)`: `31/10 23:59:59-03:00` → chave 1, mas é `01/11 02:59 UTC` (→ 2); `31/10 21:00-03:00` → 1 (e é novembro em UTC).
Sem `agora` o código usa `datetime.now(UTC)`, então com `CHAVE_AES_ID` virada à meia-noite **BRT** todas as escritas de conversa/cofre falham com `ChaveForaDoMes` de 21:00 a 24:00 BRT do último dia
(provado: vigente 1 + `agora=01/11 00:00 UTC` → `ChaveForaDoMes`; vigente 1 + `31/10 23:59:59 BRT` → grava). `agora` naive é aceito sem erro. O `docs/OPERACAO.md` não foi tocado pelo commit
(diff sem ele) e não diz a hora da virada nem que agora a virada atrasada **para** o turno em vez de apenas cifrar com a chave velha. **Correção:** `agora.astimezone(UTC)` (recusar naive),
documentar «virar `CHAVE_AES_ID` e reiniciar às 00:00 UTC = 21:00 BRT», e decidir se uma janela curta (ex.: aceitar vigente = mês anterior até 5 min depois da virada) é preferível a parar o atendimento.
**Caso:** `chave_id_do_mes(datetime(2026,10,31,23,0,tzinfo=BRT))` deve valer 2.

### R2-4 · MÉDIO (latente até P2) · S3: `cgid:{mensagem_id}` não é amarrado ao chat (`evento_mensagem.py:156-157`, índice global `passo_msg_chave_uq`)
Provado: a mesma `mensagem_id` em dois chats → o 2º evento vira `Conflito` (fingerprint tem `chat_id`) e a mensagem **legítima do outro cliente não é gravada** (passos e pendentes do
atendimento B vazios); com o mesmo texto, `Conflito` também. Quem controlar um `mensagem_id` (Post forjado com assinatura válida, ou ids não globais do ChatGuru) silencia mensagens de outros chats.
Hoje inalcançável: o contrato 08 §5.1 devolve `422` a `message_id` até o P2. Severidade real: MÉDIO, correção barata e sem DDL.
**Correção:** `cgid:` + `HMAC(chave_h16, b"cgid/v1\n"+chat_id+b"\n"+mensagem_id)[:32]` (casa o CHECK da 0001; `cgid:{chat}:{id}` **não** casa por causa dos `:`; `cgid:{chat}-{id}` casa mas estoura
os 120 se o id passa de 95). **Caso:** dois atendimentos de chats diferentes com `mensagem_id="MSG-1"` → 2 `Gravada`.

### R2-5 · BAIXO (latente até P3) · S4: replay sem hora e sem id fura o dedupe; a guarda «exige recebido_em» é código morto (`linha_tempo.py:249`, `evento_mensagem.py:158-160`)
`recebido_em or datetime.now(UTC)` garante que `identidade` nunca levanta pela via de produção; o autor assumiu o custo («replay SEM hora não dedupa»). Provado: o mesmo evento sem `datetime_post`
duas vezes (webhook e replay) → `Gravada, Gravada`, mesmo fingerprint, chaves diferentes, 2 turnos e 2 respostas. O estudo B mostra `datetime_post` sempre presente (24 481 linhas), então hoje é teórico;
vira real se P3 disser que a hora falta. **Não** exigir hora/id (perderia mensagem). **Correção:** nesse ramo, busca secundária por `msg_fingerprint` no mesmo atendimento com `ocorrido_em` nos
últimos ~5 s (as 3 tentativas do ChatGuru chegam em 1,2–3,1 s), marcando `sem_hora`; fora da janela segue como mensagem nova (preserva o 2º «sim» legítimo). **Caso:** mesmo evento sem hora/id a 2 s de
distância → 1 `Gravada` + 1 `Duplicada`; a 60 s → 2 `Gravada`.

### R2-6 · BAIXO · o xfail strict de `casar` nunca vai virar (`tests/test_linha_tempo.py:490-496`)
O teste chama `gravar_mensagem_recebida` sem `casar`; o casamento da B1.5 é injetado, então o comportamento padrão não muda e o strict não lembra de nada. **Correção:** o teste passa a receber um
casador de verdade (fixture da B1.5) ou vira `pytest.skip` com a issue; o gancho já tem teste verde (`:473`).

### R2-7 · BAIXO · contrato 08 §5.1 desatualizado e restos
(a) §5.1 ainda manda mascarar «inclusive os nomes» no fingerprint; a implementação reverteu (M5): publicar v2.2. (b) o fallback `recebido_em` por relógio do processo ≠ relógio do banco (só afeta a
chave; sem efeito de segurança). (c) `datetime_post` do replay formatado com precisão diferente do webhook (`.000` × sem fração) dá a mesma chave (fração zero é omitida: ok), mas ms arredondados não: documentar que o replay
repete o `datetime_post` original. (d) M8/M9 seguem adiados e corretamente rastreados.

## Tautologia: os testes novos reprovam sem a correção? (mutantes aplicados numa cópia)
| Correção desfeita | Teste que reprova | Linha |
|---|---|---|
| M6: versão conferida depois da ordem | `test_consumir_perdedor_da_corrida_recebe_conflito_de_versao_m6` | `test_linha_tempo.py:499` |
| M4: `casar` fora do lock (removido) | `test_gancho_de_casamento_webhook_x_rpa_roda_sob_o_lock_m4` | `test_linha_tempo.py:473` |
| M2: sem `exigir_chave_do_mes` | `test_chave_do_mes_diferente_da_vigente_recusa_gravar_m2` | `test_conversa.py:277` |
| M1: `criado_em` do chamador (−1 h) | 8 testes de `test_cofre.py` (ex.: `test_canal_ida_e_volta_ttl_7d`) | `test_cofre.py:33` |
| A2: `__init__` devolve o `ValidationError` | 4 testes (ex.: `test_repr_e_errors_do_evento_nao_vazam_o_texto_a2`) | `test_linha_tempo.py:411` |
| A3: sem `cgid:` / sem fração de segundo | `test_mensagem_id_e_fracao_de_segundo_e_query_da_url_distinguem_mensagens_a3` | `test_linha_tempo.py:436` |
| A1: `motivo` volta a `str` (`DecisaoRegra` / `DecisaoModelo`) | `…_nunca_chega_ao_banco_a1` / `test_motivo_com_texto_livre_e_recusado_a1[…]` ×6 | `test_linha_tempo.py:392`, `test_passos.py` |
| M3: `nomes=()` como default | `test_sem_nomes_nao_grava_texto_de_cliente_nem_resumo_m3` | `test_conversa.py` |
| M7: `LIMITE_NOTA = 250` | `test_anotacao_com_categoria_de_40_e_nota_maxima_cabe_nos_300_do_check_m7` | `test_passos.py` |
Nenhum é tautológico. O gancho `:473` mede `RowShareLock` do próprio backend (prova que houve `FOR UPDATE` ou equivalente, não qual); suficiente. Lacunas de teste: R2-1 (só o construtor), R2-2 (só texto com espaço/hífen), R2-3
(só fixtures em UTC; nenhum teste da virada).

## O que pedir antes do merge
Obrigatório: R2-1, R2-2 e R2-3 (curtos, sem DDL). R2-4 antes de o P2 ligar (melhor agora: é um `if`). R2-5/R2-6/R2-7 podem ir para a B1.5 com issue.


---

## Resposta do autor (r2) (30/10)

Testes do revisor escritos antes e reprovando no código anterior; `bash scripts/check.sh` verde (861 passed, 1 xfailed).

| Item | Resposta |
|---|---|
| R2-1 | Corrigido. Um `model_validator(mode="wrap")` na base ficaria POR DENTRO dos validadores `after` das subclasses (o erro da anotação escapava); o fechamento é em `__get_pydantic_core_schema__`, que embrulha o esquema inteiro. Testados os 4 caminhos (`model_validate`, `model_validate_json`, `TypeAdapter` python e json) mais o construtor. `EntradaInvalida` deixou de herdar de `ValueError` (senão o Pydantic a embrulharia de novo com o input). **B1.5:** o corpo tipado do FastAPI passa a levantar `EntradaInvalida`; precisa de `exception_handler` que a devolva como 422 só com `detalhes`. |
| R2-2 | Corrigido. `motivo` é `Literal` (`MOTIVOS_DE_DECISAO`, 15 códigos em `passos.py`); `cliente_disse_zebraquantica` e `cpf_52998224725` são recusados e o teste do autor usa o caso que o regex deixava passar. `intencao`/`objecao`/`transversal`/`peca`/`verif_*` seguem regex até existir catálogo (B1.4/B5), agora com cerca: 4+ dígitos seguidos e `mascarar` (com os nomes do `ContextVar`) sobre o código com `_` virando espaço. Não recuso «token ≥ 4 letras presente na mensagem do turno»: precisa do texto do turno, que não chega a `passos`. |
| R2-3 | Corrigido. Regra única UTC, naive recusado, tolerância de 1 h para a chave do mês anterior (mês novo antes da hora continua recusado), documentado em `OPERACAO.md` §2. |
| R2-4 | Corrigido (HMAC amarrado ao chat; mesmo `mensagem_id` em dois chats dá 2 `Gravada`). |
| R2-5 | Corrigido sem rejeitar: busca secundária por fingerprint, 5 s, mesmo atendimento, só para evento sem hora e sem id; `Gravada.sem_hora` (e `msg_enviada_em` NULL, que é a marca do DDL). A guarda «exige `recebido_em`» de `identidade()` fica: é alcançável por quem chama `identidade` direto (testada); o que era morto é só o caminho de produção, onde `gravar_mensagem_recebida` sempre passa um instante. |
| R2-6 | O `xfail(strict)` do casamento saiu: não podia virar (o casador é injetado). O gancho `casar` continua provado por `test_gancho_de_casamento…` (sob o `FOR UPDATE`). |
| R2-7 | (a) contrato 08 §5.1 precisa da v2.2 (fingerprint sem nomes; `cgid:` por HMAC): vai na nota do PR. (b)–(d) registrados. |
