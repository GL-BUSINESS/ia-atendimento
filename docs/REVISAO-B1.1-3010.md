# Revisão adversarial de contexto limpo · B1.1 (`feat/b1-1-estado`, 7858eb7) · 30/10

Revisor: Claude (Sonnet 5.5), sem ter escrito o código; substitui o Codex sem cota. Só leitura: nada foi editado no repo (único arquivo criado: este).
Base: `git diff origin/main...HEAD` (5 commits) contra ROTEIRO «B1.1», sp01 T2/T3, estudo I §3 e contrato 08 (§3, §4, §6, §8, §11).
Provas rodadas em PG 18 descartável (docker) com as fixtures do repo; os casos abaixo estão em `/tmp/claude-1001/probe_ia/test_achados.py` (fora do repo; 13 reprovam hoje, 1 passa).

**Veredito: APROVAR COM CORREÇÕES.** Zero CRÍTICO. 4 ALTO (A1–A4) devem entrar antes do merge: são pequenos e ficam todos em `estado.py`/`estado_conversa.py`.
Contagem: CRÍTICO 0 · ALTO 4 · MÉDIO 5 · BAIXO 8.

## O que resistiu (provado, não só lido)

- `bash scripts/check.sh` verde: 854 passed, 2 xfailed, 19 s. Ruff, varredura, `0001.sha256` e `gerar_0002 --verificar` ok.
- **CAS:** `aplicar` é o único UPDATE de transição e sempre leva `WHERE atendimento_id AND versao`. Mutação «tirar `AND versao`» reprova. `registrar_mensagem_do_cliente` não usa `versao` por desenho (coluna com GRANT próprio, só `greatest`).
- **Replay/fingerprint:** o vetor `b8da81fb…` é literal do contrato (não calculado pelo teste). Mutações «replay ignora fp», «fp sem `chat_id`», «fp com `perfil`», «repetido=False» reprovam. Mesma chave com outro `chat_id`, `pessoa_id`, `phone_id`, `gatilho`, `clt_job_id` ou `persona_id` dá `ConflitoIdempotencia`; replay nunca devolve atendimento de outro chat.
- **`abrir` × chat ocupado:** `ChatOcupado` deixa `transaction_status=IDLE`, 0 locks em espera, 1 linha só (savepoint limpo). Sem o savepoint o teste reprova (mutação M32).
- **Índice parcial** `atendimento_ativo_chat_uq` (0001) tranca `reservado`/`repassando`; vários atendimentos sequenciais no mesmo chat passam.
- **Imutáveis:** como `ia_app_a`, `UPDATE` de `comissao_esperada_brl`, `faixa_esforco`, `modo`, `persona_id`, `chat_id`, `pessoa_id`, `gatilho`, `entrada_fingerprint` dá `InsufficientPrivilege`. `ultimo_cliente_em` só `ia_app` escreve; `ia_leitura`/`ia_qualidade` leem e não escrevem; `intruso` nem lê.
- **0003:** aditiva (só `ADD COLUMN IF NOT EXISTS`, `GRANT`, 2 `ADD CONSTRAINT`), passa por `migracoes.aplicar` (ledger + checksum dos bytes na mesma transação), docs coerentes com o script de `psql -1`. Não toca `0001.sha256`.
- **SQL:** nenhum valor interpolado; só `sql.Identifier` e nomes de campo vindos de `Mudancas.model_fields_set` (`extra=forbid`). Sem `logging`/`print` nos dois módulos.
- **`xfail(strict)`:** os 2 (`pausar`/`abrir_agendado`, `raises=AttributeError`) são marcadores honestos de B5.7b; não mascaram bug.
- **Mutação (26 rodadas, `/tmp/claude-1001/mut_run.py`):** 22 reprovam. 3 sobrevivem por equivalência (o CHECK do banco já barra: M5 `abortar` sem `assumido_em IS NULL`, M6 `encerrar(abortado)` sem trava, M29 `_REPASSAVEIS` ampliado). 1 sobrevive de verdade (T1 abaixo).

## ALTO

### A1 · `encerrado` não é absorvente: `aplicar` é público e `de` é opcional
`estado.py:547` (`de: ... = None`), `:556-566`; banco sem trigger. Só os invólucros passam `de`. Qualquer chamador de `aplicar(..., Mudancas(estado="aberto", desfecho=None, encerrado_em=None, lease_ate=...))` ressuscita um atendimento encerrado (os CHECKs aceitam; só o índice do chat barra, e só se houver outro vivo). Provado: `RESSUSCITOU aberto`; com chat reocupado a barra é `UniqueViolation` crua.
Correção: `de` obrigatório (sem default; `aplicar_qualquer` explícito, se preciso) ou default `ESTADOS_NAO_TERMINAIS`; e, na 0003 (ainda não aplicada), `BEFORE UPDATE ... WHEN (OLD.estado='encerrado') EXECUTE ... RAISE` (terminal também no banco, para `ia_app` por SQL direto).
```python
def test_encerrado_e_absorvente_tambem_via_aplicar(db_conn, relogio, versoes):
    atd, v = aberto(db_conn, relogio, versoes)
    v = encerrar(db_conn, atd, v, desfecho="sem_venda", motivo="fim", relogio=relogio)
    with pytest.raises((TransicaoInvalida, TypeError)):
        aplicar(
            db_conn,
            atd,
            v,
            Mudancas(estado="aberto", desfecho=None, encerrado_em=None, lease_ate=relogio() + timedelta(minutes=5)),
            agora=relogio(),
        )
    assert ler(db_conn, atd).estado == "encerrado"  # hoje: DID NOT RAISE
```

### A2 · `Mudancas.estado_conversa` é `dict[str, Any]` e contorna o schema de `EstadoConversa`
`estado.py:442`, `:474-481`, `:491-496`. O único limite é 2 KB. `aplicar(..., Mudancas(estado_conversa={"fase":"E1","cpf":"12345678909","texto":"meu nome é X"}))` grava no banco (provado: `EXTRA {'cpf': ..., 'texto': ...}`). O que `estado_conversa.py` promete («só códigos, `extra=forbid`») vale só por `gravar_estado_conversa`; o caminho alternativo está aberto, e os próprios testes (`test_estado.py:651-654`) usam o dict cru. O 2 KB também é medido por `json.dumps` do Python, que subestima floats (`1e22` = 5 B no Python, 23 B no `jsonb`): o banco acaba barrando (ver A4).
Correção: `Mudancas.estado_conversa: EstadoConversa | None` (mover `EstadoConversa` para um módulo sem ciclo, p. ex. `modelos_conversa.py`) e gravar `para_json()`; ou validar no `model_validator` com import tardio. Medir o tamanho no banco (`octet_length(%s::jsonb::text)`) ou recusar `float`.
```python
def test_mudancas_nao_aceita_estado_conversa_fora_do_schema():
    with pytest.raises(Exception):
        Mudancas(estado_conversa={"fase": "E1", "cpf": "12345678909"})  # hoje: DID NOT RAISE
```

### A3 · `ultimo_cliente_em` no futuro é aceito em `abrir` e em `registrar_mensagem_do_cliente`, e nunca recua
`estado.py:173`, `estado_conversa.py:126-145`. Contrato 08 §8: «no futuro (> 5 min) ⇒ 422 `validacao`». Hoje `abrir` grava 30 dias à frente e `registrar_mensagem_do_cliente(..., +3650 d)` devolve `2036-11-21`; como o UPDATE é `greatest`, o valor errado fica para sempre e `janela_24h_aberta` devolve `True` (diferença negativa < 24 h): texto livre fora da janela do WhatsApp (falha 95%, levantamento 09 §4.5). Provado: `FUTURO aceito`, `FUTURO msg ... True`.
Correção: validar contra o `relogio` em `abrir` (`> agora + 5 min` ⇒ `EntradaInvalida`) e em `registrar_mensagem_do_cliente` (recebe `agora`); `janela_24h_aberta` devolve `False` se `ultimo > agora + tolerância`.
```python
def test_ultimo_cliente_em_no_futuro_e_recusado(db_conn, relogio, versoes):
    with pytest.raises(EstadoErro):
        abrir_(db_conn, relogio, versoes, entrada(ultimo_cliente_em=relogio() + timedelta(days=30)))
    r = abrir_(db_conn, relogio, versoes)
    with pytest.raises(ValueError):
        registrar_mensagem_do_cliente(db_conn, r.atendimento_id, relogio() + timedelta(days=3650))
    assert not janela_24h_aberta(relogio() + timedelta(days=30), relogio())
```

### A4 · Exceções cruas do psycopg vazam a linha inteira (e o `perfil`) por `str(exc)`
`estado.py:394-407` (`abrir` só traduz `UniqueViolation`), `:558-563` (`aplicar` só traduz `CheckViolation`). Qualquer outro `IntegrityError`/`DataError` sobe com `DETAIL: Failing row contains (...)` (todas as colunas, `perfil` incluso) ou `CONTEXT: JSON data ... {"renda_cliente_12345": NaN...`. Provado: (a) `origem="N8N"` ou `perfil={"a":[1e22]*280}` ⇒ `CheckViolation` em `abrir` com a linha; (b) `perfil` com `float("nan")` ⇒ `InvalidTextRepresentation` com as chaves/valores do perfil; (c) `aplicar(Mudancas(estado_conversa={}))` ⇒ `NotNullViolation` com a linha. A promessa «sem valor da linha na mensagem» (docstring de `aplicar`) só vale para um caso.
Correção: um `traduzir_erro_banco(exc)` único (`psycopg.errors.IntegrityError|DataError` ⇒ `EstadoErro` com `restricao`/`sqlstate`, `from None`), usado em `abrir` e `aplicar`; recusar `float` não finito em `perfil` (`allow_inf_nan=False`).
```python
def test_abrir_nao_deixa_psycopg_cru_nem_a_linha_na_mensagem(db_conn, relogio, versoes):
    with pytest.raises(EstadoErro) as e:
        abrir_(db_conn, relogio, versoes, entrada(perfil={"a": [1e22] * 280}))
    assert "Failing row" not in str(e.value)
    with pytest.raises(EstadoErro) as e:
        abrir_(db_conn, relogio, versoes, entrada(perfil={"renda_cliente_12345": float("nan")}))
    assert "renda_cliente_12345" not in str(e.value)
```

## MÉDIO

### M1 · «Só códigos» aceita dígitos de CPF/telefone
`estado_conversa.py:36-37`, `estado.py:45-47`: `Codigo = ^[a-z0-9_]{1,40}$` e `Referencia = ^[A-Za-z0-9_.:-]{1,64}$` casam `12345678909`, `5511912345678` e `123.456.789-09`. Provado gravando em `campos_coletados`, `objecoes`, chaves de `flags` e `oferta_corrente.oferta_id`. Vale também para `contexto_codigos`, `motivo_desfecho`, `sinais_cliente`.
Correção: recusar `\d{6,}` e `\d{3}\.\d{3}\.\d{3}-\d{2}` nos tipos de código/referência (e, quando o roteiro fixar o vocabulário, enum). Teste: `estado_conversa_de_json({"fase":"E1","campos_coletados":["12345678909"]})` deve levantar `EntradaInvalida` (hoje não levanta).

### M2 · `perfil` aceita qualquer coisa (PII incluída)
`estado.py:166`, `:181-182`. O contrato 08 §3 pede «só rótulos sem PII»; o modelo diz «Sem PII», mas `perfil: dict[str, Any]` recebe `{"cpf": "123.456.789-09", "nome": "Fulano da Silva", "telefone": "5511912345678"}` (provado). A varredura §5.4 é da API (B6.1), mas é a última camada antes de `ia.atendimento`, e A4 mostra o perfil escapando em exceções.
Correção: chave `Codigo`, valor `str` curto de código / `int` / `bool` / `None`, sem aninhamento e sem float; mesma recusa de M1. Teste: `entrada(perfil={"cpf":"123.456.789-09"})` deve falhar.

### M3 · `encerrar(desfecho="repassado")` vale de qualquer estado, sem passar por `repassando`
`estado.py:644-677`, `_REPASSAVEIS`/`de=ESTADOS_NAO_TERMINAIS`. Provado: de `aberto` e de `reservado` fecha `repassado` com `repasse_modo=None` (o CHECK aceita). Sp01 T3 e ROTEIRO pedem repasse em duas fases; a única exceção legítima é a devolução da S2 (`motivo='devolvido_pela_s2'`, sp01 l.93). Um chamador apressado marca lead como repassado sem repassar.
Correção: `desfecho=="repassado"` ⇒ `de={"repassando"}`, salvo `motivo=="devolvido_pela_s2"`.
```python
def test_repassado_so_a_partir_de_repassando(db_conn, relogio, versoes):
    atd, v = aberto(db_conn, relogio, versoes)
    with pytest.raises(TransicaoInvalida):
        encerrar(db_conn, atd, v, desfecho="repassado", motivo="x", relogio=relogio)  # hoje: DID NOT RAISE
```

### M4 · Lease: sem renovação fora de transição e `aguardando_cliente` expira em 5 min
`estado.py:572-605`, `estado_conversa.py:117-123`. Não existe `renovar_lease`; `gravar_estado_conversa` e `aplicar` genérico não renovam (documentado), então um turno de LLM acima de 5 min vence sem ter como renovar. Pior: `aguardar_cliente` põe `+300 s` mas o cliente leva horas, e o plano (l.419) manda o `reaper_lease` repassar `aberto|aguardando_cliente` com lease vencido. Isso contradiz os lembretes de 240 min. O código segue a letra do plano; o risco é de desenho e vai estourar em B1.3.
Correção: decidir antes de B1.3: ou `aguardar_cliente` grava lease até o último lembrete + folga, ou o reaper pula `aguardando_cliente`; e expor `renovar_lease(conn, id, versao, relogio)` (CAS). Teste: `aguardar_cliente` seguido de `relogio.avancar(minutes=10)` não deixa o atendimento «vencido» para o `v_prontidao`.

### M5 · `resolver_modo`/`abrir` confiam em `chats_teste` do chamador, que pode ser `str`
`estado.py:233-246`. `chat_id in chats_teste` com `chats_teste` string vira substring: `chats_teste="xx"+chat+"yy"` devolve `modo='teste'` (provado). Nada confere os itens (24 hex) nem lê `config_versao`; `modo_global="real"` num chat da lista também depende só de o chamador passar a lista certa. §6 também pede `pessoa_id ∈ pessoas_teste` (API/B2.4, fora daqui).
Correção: `if isinstance(chats_teste, (str, bytes)): raise TypeError`; normalizar para `frozenset` validado por `Hex24`. Teste: `abrir(..., chats_teste="xx"+chat+"yy")` deve levantar `TypeError`.

## BAIXO

- **B1 · `aplicar(agora=naive)` é aceito** (`estado.py:540-563`; `agora_de` só roda nos invólucros): grava `timestamptz` pelo fuso da sessão. Provado. Correção: `if agora.tzinfo is None: raise ValueError`. Teste: `aplicar(..., agora=datetime(2026,11,24,13,0))` ⇒ `ValueError`.
- **B2 · Nome de chave do corpo é ecoado** (`estado.py:186-205`): `loc` leva a chave do cliente; `entrada_de_corpo({**corpo, "123.456.789-09": "x"})` devolve `corpo inválido: 123.456.789-09 (extra_forbidden)`; em `flags` idem (`flags.12345678909 Fulano.[key]`). Contrato 08 §5.1 aceita «só o nome», mas o nome pode ser dado. Correção: trocar `loc` de `extra_forbidden`/`[key]` por `"(campo desconhecido)"`. Teste: `assert "123.456.789-09" not in str(e.value)`.
- **B3 · `ValidationError` crua nas transições** (`iniciar`, `repassar`, `encerrar`, `aguardar_*`): taxonomia inconsistente com `EntradaInvalida`, e `exc.errors()[0]["input"]` traz o valor (`repassar(motivo="CPF 123.456.789-09")` ⇒ `input: 'CPF 123.456.789-09'`; o `str` é limpo por `hide_input_in_errors`, o `.errors()`/`.json()` não). Correção: construir `Mudancas` via `validar_corpo(Mudancas, campos)` nos invólucros.
- **B4 · `gravar_estado_conversa` não valida coerência fase×estado em Python** (`estado_conversa.py:117-123`): em `aberto` aceita `fase=E10` (sem estar `repassando`) e `pausa` fora de `pausado` (provado: `E10 em aberto`, `pausa em aberto`); o CHECK só cobre `reservado⇔E0`, `repassando⇒E10`, `pausado`. Correção: tabela de fases por estado (e `pausa` só em `pausado`).
- **B5 · 0003 sem pré-checagem de dados** (`0003...sql`): `ADD CONSTRAINT` valida a tabela inteira; `chat_id` com `_`/`-` ou `chats_teste` fora da regra existentes derrubam a transação inteira (o `psql -1` desfaz, sem estrago). Correção: no passo a passo, `SELECT count(*) FROM ia.atendimento WHERE chat_id !~ '^[0-9a-f]{24}$'` antes de aplicar.
- **B6 · Overflow de inteiro sobe como `NumericValueOutOfRange`** (`Mudancas.turnos=2**40`, provado; sem valor na mensagem). Correção: `le=2**31-1` em `turnos`/`mensagens_enviadas`/`lembretes_enviados`/`ordem_consumida`.
- **B7 · `registrar_mensagem_do_cliente` não toca `atualizado_em`** (`estado_conversa.py:133-137`): mensagem do cliente não conta como atividade para `idx_atendimento_parado` (reaper `expirar_parados`). Decidir em B1.3; se contar, incluir `atualizado_em` no mesmo UPDATE (sem `versao`).
- **B8 · Plano T3 pede `abrir` «sob `pg_advisory_xact_lock`»**; a implementação usa savepoint + índice único e prova a corrida real (2 threads), o que é melhor. Só registrar o desvio; `max_abertos` fica em B1.5.

## Testes tautológicos, fixtures e lacunas

- **T1 · lacuna real:** mutação `gravar_estado_conversa(de=None)` sobrevive (129 passed). O docstring diz «atendimento encerrado não muda», o comportamento está certo hoje (provado), mas nenhum teste o guarda.
  ```python
  def test_gravar_estado_conversa_em_encerrado_e_recusado(db_conn, relogio, versoes):
      atd, v = aberto(db_conn, relogio, versoes)
      v = encerrar(db_conn, atd, v, desfecho="sem_venda", motivo="fim", relogio=relogio)
      with pytest.raises(TransicaoInvalida):
          gravar_estado_conversa(db_conn, atd, v, EstadoConversa(fase="E2"), relogio=relogio)
  ```
- **T2 · vetor dourado cego a maiúscula de UUID:** `pessoa_id` do vetor só tem dígitos; trocar por `str(pessoa_id).upper()` no fingerprint passa tudo. `test_fingerprint_normaliza_uuid_maiusculo` compara dois hashes que passam pelo mesmo `upper()`. Correção: UUID com letras (`aaaaaaaa-…`) no teste de normalização, comparando com literal.
- **T3 · os testes de `Mudancas` dependem do bypass de A2:** `test_estado.py:651-654` e `:696+` passam `estado_conversa` como dict cru. Quando A2 for corrigido, trocar por `EstadoConversa(...).para_json()`.
- Fixtures: `db_conn` é autocommit (cenário de produção deve ser igual: `psycopg_pool`/`autocommit=True`); nada esconde erro. `versoes` semeia só 1..N sem lacunas. As corridas usam conexões reais (`ThreadPoolExecutor`), sem mock.

## As 5 correções mais importantes, em ordem

1. **A1** · `aplicar` sem `de` padrão + trigger de terminal absorvente na 0003 (ainda não aplicada na S4: é de graça agora).
2. **A2** · `Mudancas.estado_conversa` tipado por `EstadoConversa` (fecha o único caminho que burla `extra=forbid`/«só códigos»).
3. **A4** · tradutor único de `IntegrityError`/`DataError` em `abrir` e `aplicar` + recusa de float não finito no `perfil`.
4. **A3** · `ultimo_cliente_em` contra o relógio (> 5 min no futuro ⇒ recusa) em `abrir`, `registrar_mensagem_do_cliente` e `janela_24h_aberta`.
5. **M1 + M2** · códigos/referências e `perfil` sem dígitos de documento (dobra com M3 e T1 no mesmo PR de correções).

---

## Resposta do autor (30/10, commit `fix: estado — correções da revisão 1 (A1–A4 e médios)`)

Os 13 casos de `/tmp/claude-1001/probe_ia/test_achados.py` foram portados para `tests/test_estado_revisao1.py` (e os da 0003 para `tests/test_migracao_0003.py`), vistos vermelhos (ImportError no módulo novo; 7 falhas reais nos casos de banco) e depois corrigidos. Suíte: 854 → 905 passed, 2 xfailed (`check.sh` verde). Quatro mutações das correções reprovam (A1, M1, A3, M3).

| Achado | Resposta |
|---|---|
| **A1** | Corrigido nas duas camadas: `aplicar(de=)` agora tem padrão `ESTADOS_NAO_TERMINAIS` (não aceita `None` por omissão) **e** a 0003 ganha o trigger `atendimento_terminal_absorvente` (`BEFORE UPDATE ... WHEN OLD.estado='encerrado'` e mudou `estado`, `desfecho` ou `encerrado_em`; levanta `check_violation`). Decisão minha: o trigger **não** barra `contrato_id`, `pii_auditoria` nem `ultimo_cliente_em` depois do fim (o job noturno os grava). A 0003 mudou in-place (ainda não aplicada em lugar nenhum). |
| **A2** | `Mudancas.estado_conversa: EstadoConversa \| None`; modelos movidos para `modelos_conversa.py` (sem ciclo); `estado_conversa.py` os reexporta. Os testes de `test_estado.py` usam `EstadoConversa(...)`. Efeito colateral: `pausa.retoma_fase="E7"` nem se constrói mais; o caso «pausado em E7» agora passa `fase="E7"` a `aplicar`. |
| **A3** | `abrir` recusa `ultimo_cliente_em` > relógio + 5 min (`EntradaInvalida`, depois do replay); `registrar_mensagem_do_cliente` ganhou `relogio` **obrigatório** (mudança de assinatura: o probe chamava sem ele; o caso foi adaptado) e levanta `EntradaInvalida` (um `ValueError`); `janela_24h_aberta` devolve `False` no futuro além de 5 min. |
| **A4** | `traduzir_erro_banco` + `executar_traduzindo` (savepoint, tradução fora do `except`, sem `__context__`): `IntegrityError`/`DataError` viram `DadoRecusado(sqlstate, restricao)`, ou `TransicaoInvalida` (CHECK em `aplicar`) / `ChatOcupado`. `origem` é validada antes do banco. `perfil` não aceita mais float (nem NaN/inf). O caso do revisor chamava `entrada(perfil=...)` dentro de `raises(EstadoErro)`: a recusa agora vem do Pydantic (`ValidationError`), então o teste usa `model_construct` para provar a tradução do banco e outro teste prova a recusa na entrada. |
| **M1/M2** | `tipos.py`: `Codigo40/60`, `Referencia` e `Rotulo` recusam 6+ dígitos seguidos e CPF/CNPJ mascarado. `perfil` = `dict[Codigo40, bool \| int(<1e9) \| Rotulo \| None]`, ≤ 64 chaves, sem aninhamento. Custo aceito: id de oferta puramente numérico com 6+ dígitos seria recusado (hoje o vocabulário é `of-001`); `repasse_consultor_ref` ficou fora da regra (o `site_profile_id` pode ser numérico longo). |
| **M3** | `encerrar(repassado)` só de `repassando`, salvo `motivo="devolvido_pela_s2"`. O teste de sombra passou a fazer `repassar` antes. |
| **M4** | **Decisão de desenho [Claude], a confirmar com o dono do B1.3:** `aguardar_cliente` grava lease de **12 h** (`LEASE_AGUARDANDO_S`: lembretes 4 h + 4 h + 2 h até encerrar, com folga), em vez de mudar o reaper; `retomar` volta a +5 min. Novo `renovar_lease(..., segundos=)` (CAS) para turno longo. |
| **M5** | `chats_teste` `str`/`bytes` ⇒ `TypeError`; itens fora de 24 hex ⇒ `EntradaInvalida`; normalizado para `frozenset`. |
| **B1** | `aplicar` exige `agora` com fuso. **B2** o nome de chave do cliente não sai mais: chave extra vira `(campo desconhecido)`, chave de dicionário `(chave)` (só nomes de campo do modelo aparecem). **B3** as transições constroem `Mudancas` por `validar_corpo`: `EntradaInvalida`, sem `ValidationError` cru. **B4** feito no banco, não em Python: CHECK `atendimento_fase_estado_check` na 0003 (`aberto`/`aguardando_cliente` ⇒ fase E1..E9 e sem `pausa`). Quem implementar `sair_da_pausa` (B5.7b) tem de remover a chave `pausa`. **B5** pré-checagem de contagem no passo a passo da S4 (`OPERACAO.md`, `migrations/README.md`). **B6** `le=2**31-1` nos inteiros de contagem. |
| **B7** | Não alterado: `registrar_mensagem_do_cliente` continua sem tocar `atualizado_em` (a coluna não está no GRANT próprio). Decidir em B1.3 se a mensagem do cliente conta como atividade para o reaper; se contar, é GRANT novo numa 0004. |
| **B8** | Registrado: savepoint + índice único no lugar do `pg_advisory_xact_lock`; `max_abertos` fica em B1.5. |
| **T1/T2/T3** | T1: `test_t1_gravar_estado_conversa_em_encerrado_e_recusado`. T2: UUID com letras, comparado com literal calculado fora do código (`d6883c70…`). T3: resolvido junto com A2. |
