# B1.8 · Domingo por config (D-18): migração 0005 e calendário. Decisões e pendências para o revisor

Branch `feat/b1-8`, a partir de `origin/main` `9bee6a4` (PR #11 mergeado). Especificação: roteiro v3.3 B1.8 (linha 913) e D-18; `estudos/ESTUDO-D18-domingo.md`
§1 (mapa das três camadas) e §1.3 (duas chaves, fechado por padrão). Nada foi aplicado na S4, na VPS, no n8n nem no Coolify. Nenhuma chave foi publicada.

## O que a B1.8 entrega e o que fica para as etapas seguintes

| B1.8 (aqui) | Depois |
|---|---|
| Migração `0005_domingo_por_config` (só DDL) | Aplicar na S4: **A4.6**, com «sim» nomeado do dono (tem `DROP CONSTRAINT`, PD-2) |
| `calendario.py` lê o domingo da config; validadores aceitam o dia 7 | Kit `ia/config/domingo.sh` (`abrir`/`fechar`/`--ensaio`) e a publicação em 13/11: **B6.7 / B9.1** |
| `ConfigAgenda.domingo_aberto` em `_dia_util` e `_razoes`; `config_da_agenda` o tira do `Calendario`; `POST /agendamentos` lê `janela_mensagem` | Resíduo da **B5.7d** (o código da agenda já está aqui): ≥ 12 frases novas com domingo aberto no `agenda_frases.jsonl`, hold-out intacto, e o `pausado` de sábado voltando no domingo |
| `corpus/calendario.py`: `dentro_do_horario`/`dentro_da_agenda` com `domingo_aberto` (padrão `False`) | Resíduo da **B8.1c** (o parâmetro do corpus já está aqui): passar o estado a I3 (`regras/invariantes.py:77`), `regras/gabarito.py:141`, `regras/agenda.py:37`; 3 personas de domingo na F3 curta |
| Linha da 0005 no ledger (`migrations/README.md` passo 5, `docs/OPERACAO.md` §3) | TX-42 e `{{retorno}}`: **B5.5**; critério 10 do n8n: **B6.2**; rótulo do web: **B7.1** |

## Decisões

| # | Decisão | Fonte |
|---|---|---|
| D1 | **0005 só troca o `config_versao_valor_check`.** `DROP CONSTRAINT` e `ADD CONSTRAINT` no **mesmo** `ALTER TABLE`, na transação única do aplicador: não existe instante sem CHECK. O CASE é cópia literal de `0001:29-60` com **um** termo a menos (`NOT jsonb_path_exists(valor, '$.dias."7"')`); o limite 08:00–20:00 segue para os 7 dias e todas as outras chaves seguem validadas igual. O **nome** da restrição é o mesmo: o mapeamento de erro (`check_violation` com `config_versao_valor_check`) e os casos do estudo I continuam valendo. O arquivo foi gerado a partir das linhas da 0001 (troca de uma linha), e `test_0005_copia_o_case_da_0001_com_um_unico_termo_a_menos` prova a cópia: CASE da 0001, sem comentários, com o termo trocado = CASE da 0005 | ESTUDO-D18 §1.2; roteiro B1.8 |
| D2 | **A 0001 não muda** (sha `5d1ceec1…`). `tests/casos/casos_c.py:284` («janela_mensagem no domingo recusada») **fica**: a sequência dos 350 casos do estudo I roda só a 0001 (`test_esquema.py`, fixture `so_0001`), como o `i-teste-0001.sh:318`, que o estudo §8 manda manter. A «parametrização» pedida no roteiro está em `test_migracao_0005.py`: o mesmo `INSERT` é recusado até a 0004 e aceito com a 0005 | ESTUDO-D18 §8 («`i-teste-0001.sh:318` fica como está») |
| D3 | **Duas chaves, fechado por padrão.** O domingo só tem horário com `calendario_bloqueio.domingos=false` **e** `janela_mensagem.dias."7"` (`Calendario.domingo_aberto`). Uma só não abre: `domingos=true` bloqueia o dia 7 mesmo com horário na janela; `domingos=false` sem o dia 7 não tem horário. `PADROES` (`chave_registro.py`) e os seeds da 0001 **não mudam**: `test_defaults_seguem_sem_domingo` e `test_0005_nao_mexe_nos_seeds_domingo_segue_fechado` | ESTUDO-D18 §1.3; D-15 |
| D4 | **`domingos` precisa ser booleano** (fail-closed). Antes só `true` passava; agora `true` ou `false`. Ausente, `null`, `"false"` ou `0` ⇒ `CalendarioInvalido` (registro: `422 valor_invalido`). Uma config que não diga o que fazer com o domingo não abre nada nem derruba o piso dos feriados/DATAPREV, que **não mudam** | D-15 |
| D5 | **Defesa em profundidade no `Calendario`:** além de `bloqueado()` ler `domingos`, o horário do dia 7 só existe com as duas chaves (`_horario`), também em `_proximo_inicio`. Com `domingos=true` e o dia 7 na janela, `proxima_janela` de sábado 20:30 dá segunda 08:00. **Não muda comportamento observável** (revisão R-03: a mutação que a tira é equivalente, porque `bloqueado()` já fecha o domingo e `proxima_janela` só daria um passo a mais); fica porque custa nada e protege quem ler `_horario`/`_proximo_inicio` sem passar por `bloqueado()` | revisão R-03 |
| D6 | **Agenda pelo mesmo `Calendario` do envio.** `config_da_agenda` passou a chamar `carregar_calendario(janela_mensagem, calendario_bloqueio)` (antes só `validar_calendario_bloqueio`) e tira dele feriados, janelas e `domingo_aberto`. Por isso `CHAVES_DA_AGENDA` ganhou `janela_mensagem`. Não há segunda regra de domingo na agenda que possa divergir do envio. Aberto, o domingo segue a janela 08:30–19:00 dos dias úteis (não herda o `sabado_fim`) e o teto «próximo dia útil 19:00» passa a poder ser o domingo | ESTUDO-D18 §1.1 (linha «Agenda»); roteiro B5.7d |
| D7 | **Corpus por parâmetro, padrão fechado.** `corpus/calendario.py` recebe `domingo_aberto` só como argumento nomeado; nenhuma regra da F3 o passa ainda, então I3, gabarito e agenda do corpus continuam iguais (os testes de `test_corpus*.py` não mudaram). 15/11 segue feriado **no corpus** e bloqueado nos dois estados; no `calendario.py` do orquestrador 15/11 **não** é feriado mínimo (o estudo §1.3 diz que isso é útil ao ensaio de 15/11). A divergência é a já registrada no estudo; casos de domingo aberto usam 08/11 e 29/11 | ESTUDO-D18 §1.3; roteiro B8.1c |
| D8 | **Testes de `test_migracoes.py` sem número fixo.** Dois testes criavam `0005_*.up.sql` numa cópia da pasta para provar rollback e CR LF; com a 0005 real o número repetia. Agora usam `PROXIMA = len(TODAS) + 1`. `test_migracao_0004` aceita migrações posteriores (`aplicar(...)[0] == ID_0004`) | — |
| D10 | **A agenda só aceita a volta que o envio cumpre (revisão R-01, MÉDIO, corrigido).** `config_da_agenda` passa `Calendario.dias` como `ConfigAgenda.janela_mensagem`; `_razoes` soma a `agenda_janela` (08:30–19:00, sábado até 12:00) ao horário de envio do dia: antes do início ⇒ `antes_da_janela`, no fim ou depois ⇒ `depois_da_janela` (fim **exclusivo**, como `Calendario.dentro_da_janela`), dia sem horário de envio ⇒ razão nova **`dia_sem_janela`** (depois de `domingo` na prioridade; o domingo fechado continua só com `domingo`). `_dia_util` (o teto «próximo dia útil 19:00») também pula dia sem horário de envio. Com os defaults (seg–sáb 08:00–20:00) nada muda: o corpus de 350 frases e o hold-out seguem 100 %. `ConfigAgenda()` sem `janela_mensagem` (extrator puro, corpus) não confere o envio. Fecha também a lacuna de seg–sáb que existia antes (sábado tirado da `janela_mensagem` ainda era aceito). Prova: `tests/test_agenda_janela_mensagem.py` (propriedade: de sábado 10:00, toda volta de domingo aceita é `dentro_da_janela`, com 3 horários publicados) e `test_api_config_agenda.py::test_agendamento_de_domingo_respeita_o_horario_publicado_do_dia_7` (domingo 09–18: «amanhã às 8:30» ⇒ `sem_hora`, «amanhã às 9h» ⇒ 201); os dois reprovam sem a correção | revisão R-01 |
| D9 | **Numeração.** A 0005 é desta etapa (D-18). Migração de outra etapa usa 0006 ou mais (a de tetos, RG-056, fica na 0006) | roteiro §«Fica para depois» |

## Testes que reprovam sem a mudança

- `tests/test_migracao_0005.py` (8): sem o arquivo, 5 falham; `test_sem_a_0005_o_banco_recusa_o_dia_7` prova a recusa até a 0004.
- `tests/test_calendario.py`: parametrizado (`domingo_fechado`/`domingo_aberto`), `test_domingo_so_abre_com_as_duas_chaves` (4 combinações), `test_defaults_seguem_sem_domingo`,
  `test_janela_mensagem_aceita_o_domingo_dentro_de_08_20`: 8 falham com o `calendario.py` da `main`.
- `tests/test_chave.py::test_domingo_so_abre_a_entrada_com_as_duas_chaves_publicadas` (banco com a 0005, registro de verdade): falha com o `calendario.py` da `main`.
- `tests/test_agenda_extrator.py` (2) e `tests/test_api_config_agenda.py` (`domingo_aberto` e `config_da_agenda`): 4 falham sem a mudança da agenda.
- `tests/test_corpus_revisao1b.py::test_calendario_do_corpus_abre_o_domingo_so_por_parametro`: falha sem o parâmetro.
- (revisão R-01) `tests/test_agenda_janela_mensagem.py`: 12 de 15 falham sem a correção (as 3 que passam são as horas que já cabiam nas duas
  janelas); `test_api_config_agenda.py::test_agendamento_de_domingo_respeita_o_horario_publicado_do_dia_7` (banco): falha sem a correção.

## O que ficou de fora (de propósito)

- **Publicar as chaves** e o kit `ia/config/domingo.sh`: B6.7/B9.1 (13/11). Esta etapa não abre domingo em lugar nenhum.
- **Aplicar a 0005 na S4**: A4.6, com «sim» nomeado (PD-2). O `/readyz` fica `migracao_pendente` numa imagem com este código e sem a 0005 aplicada.
- **Corpus de frases** com domingo aberto (≥ 12) e hold-out: B5.7d. **Regras da F3** e personas de domingo: B8.1c.
- **`cenarios_do_instante`** do corpus: o rótulo «noite» segue só seg–sáb; é rótulo de cobertura, não regra de envio (B8.1c decide).
- **`pausado` de sábado voltando no domingo**: com as chaves abertas, a agenda já aceita o domingo; o comportamento da volta (e a armadilha do `bloqueio_entrada`, estudo §1.3) é da B5.7c/B5.7d e da operação (§4).
- **Feriado de 15/11 no `calendario.py`**: não acrescentado (o piso mínimo segue 02/11 e 20/11; a config pode acrescentar). Decisão do dono, se quiser fechar 15/11.

## Para o revisor

- Conferir que o CASE da 0005 é cópia fiel: `test_0005_copia_o_case_da_0001_com_um_unico_termo_a_menos` compara o texto sem comentários; o comentário da linha trocada mudou de «seg–sáb» para «7 dias».
- `ADD CONSTRAINT` revalida a tabela inteira: tudo o que o CHECK antigo aceitava o novo aceita (ele só tira uma condição), então a aplicação não falha por linha existente.
- O registro de config (`chave_registro.py`) não mudou: delega a `validar_janela_mensagem`/`validar_calendario_bloqueio`.

## Revisão de 04/11 (`docs/REVISAO-B1.8-0411.md`): o que foi corrigido e o que não

| Achado | Gravidade | O que foi feito |
|---|---|---|
| R-01 agenda × horário do dia 7 | MÉDIO | **Corrigido** (D10), com testes que reprovam sem a correção. |
| R-02 fechar o domingo não cancela a volta já marcada | BAIXO | **Não corrigido aqui:** o `retomar` (`agenda_jobs.py`, fora do diff) não reconsulta o calendário; a pré-checagem da volta é da **B5.7c** (`Servicos.retomar_atendimento`), que deve incluir `dentro_da_janela` do calendário vigente, e o kit `domingo.sh fechar` (**B6.7**) deve avisar quantos `confirmado` caem no domingo. Não é defeito desta branch (o estudo D-18 §1.3 já registra a armadilha). |
| R-03 defesa D5 é mutante equivalente | BAIXO | **Mantida** (custa nada); o texto de D5 agora diz que não muda comportamento observável. |
| R-04 volta de imagem < B1.8 com as chaves abertas | BAIXO | **Documentado** em `docs/OPERACAO.md` §3: antes de voltar a imagem para < B1.8, fechar o domingo (`domingos = true`, sem o dia 7). O kit `domingo.sh` (B6.7) deve repetir o aviso. Código não muda: a recusa é fail-closed (D-15). |
| R-05 linha do roteiro e resíduo das etapas | BAIXO | **Corrigido:** linha 913; a tabela do início diz o que sobra da B5.7d e da B8.1c. O Painel/Kan é atualizado pelo orquestrador, não por esta branch. |
| R-06 caso 284 da suíte de 350 | INFO | Aceito pela revisão (D2). |
| R-07 ambiente do revisor | INFO | Nada a fazer no PR. |
