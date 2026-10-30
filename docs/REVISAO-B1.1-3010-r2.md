# Revisão adversarial 2 · B1.1 (`feat/b1-1-estado`, 305c697) · 30/10

Revisor: Claude (Sonnet 5.5), contexto limpo, sem ter escrito o código. Só leitura: nada do repo foi editado (único arquivo criado: este).
Base: `git diff 7858eb7..305c697` + `docs/REVISAO-B1.1-3010.md` + ROTEIRO «B1.1», sp01 T3, estudo I §3, contrato 08.
Provas em PG 18 descartável (fixtures do repo; sondas em `/tmp/claude-1001/probe_ia2/`, mutações numa CÓPIA em `.../probe_ia2/mut`).

**Veredito: APROVAR COM CORREÇÕES.** Zero CRÍTICO. A1–A4, M3, M5, B1–B4, B6, T1–T3 estão fechados de verdade. Os dois ALTO abaixo nascem
justamente das correções M1 e M4 (uma regressão e um desenho que não fecha com o reaper da B1.3). Antes do merge: R1 e R2.
`bash scripts/check.sh`: 905 passed, 2 xfailed, 22 s. Os 4 arquivos pedidos: verdes.

## O que fecha (provado, com variações)

- **A1 por SQL como `ia_app_a`** em encerrado: `estado`, `desfecho`, `encerrado_em`, os três juntos (ressuscitar) ⇒ `CheckViolation atendimento_terminal_absorvente`.
  `fase` ⇒ `GeneratedAlways` (coluna gerada). `ia_app` não desliga o trigger (`DISABLE TRIGGER`, `DROP TRIGGER`, `session_replication_role` ⇒ `InsufficientPrivilege`).
  Via `aplicar`, o trigger vira `TransicaoInvalida(restricao='atendimento_terminal_absorvente')`. `contrato_id`, `pii_auditoria`, `ultimo_cliente_em` passam:
  correto (o job `auditoria_pii` roda em encerrados há > 24 h; mensagem do cliente depois do fim é legítima). Mas o trigger deixa passar MAIS do que isso (R4).
- **CHECK fase×estado:** `aberto`/`aguardando` com E0 ⇒ `atendimento_conversa_check`; com E10 ou com `pausa` (inclusive `"pausa": null`) ⇒ `atendimento_fase_estado_check`;
  E1..E9 passam. `pausado→aberto` (futuro `sair_da_pausa`): sem tirar `pausa` ⇒ `TransicaoInvalida`; com `EstadoConversa(fase=retoma_fase)` (sem `pausa`) passa.
  O CHECK é compatível com B5.7b, desde que a transição reescreva `estado_conversa` (a resposta do autor já avisa).
- **A2:** `Mudancas(estado_conversa={...})` ⇒ `ValidationError`. `model_construct`/`model_copy(update=)` com dict ⇒ `AttributeError` em `_valor_sql` (nada é gravado).
  Sobra o bypass de R5. JSON direto no banco como `ia_app` grava qualquer chave (`{"fase":"E1","cpf":...}` OK); a leitura por `estado_conversa_de_json` falha fechada (`EntradaInvalida`).
- **A3:** relógio +5 min exatos aceito, +5 min +1 s ⇒ `EntradaInvalida` (`abrir` e `registrar_...`); +4:59 e −1 s passam; `ultimo_cliente_em` não recua (`greatest`);
  `janela_24h_aberta`: +5 min ⇒ True, +5 min +1 s ⇒ False, exatamente 24 h ⇒ False. Chamadores de `registrar_mensagem_do_cliente(relogio=)`: só os testes (grep em todas as branches).
- **A4** (via `model_construct`, que contorna o Pydantic): `NotNullViolation` (23502, `abrir` e `aplicar`), NaN em `perfil` (22P02), `\u0000` (22P05), int4/smallint/bigint
  estourado (22003), `atendimento_banco_check`, `atendimento_codigos_check`, `_qualidade_check`, `_chatbot_check`, trigger: tudo vira `DadoRecusado(sqlstate, restricao)` ou
  `TransicaoInvalida`; a mensagem só traz sqlstate e nome da restrição, `__context__` e `__cause__` são `None`. Nenhuma traz linha, `perfil` ou `renda_cliente_12345`.
  `ForeignKeyViolation` e `StringDataRightTruncation` são inalcançáveis hoje (`ia.atendimento` não tem FK para `artefato_versao` e as colunas são `text` sem limite); o tradutor
  é por classe (`IntegrityError|DataError`), então cobre quando existirem. Resta `TypeError` cru para valor não serializável em `model_construct` (sem o valor na mensagem).
- **Papéis:** `ia_leitura_a` e `ia_qualidade_a` leem (`ultimo_cliente_em` inclusive) e não escrevem, não chamam a função do trigger e não mexem nele.
- **0003:** aditiva (teste de varredura de `DROP/DELETE/TRUNCATE`), entra por `migracoes.aplicar` (ledger com sha256 dos bytes), não toca `0001.sha256`. Editar in loco é seguro: nenhum
  `0003` em `main`, `origin/main`, `kits/s4`, `b1-2`, `b1-3`, `b5-7a`.

## ALTO

### R1 · M1 recusa UUID e `oferta_id` numérico real (regressão da correção)
`tipos.py:20-21,30-33` (`_DIGITOS_LONGOS = \d{6,}` aplicado a `Referencia`), usado em `modelos_conversa.py:36` (`OfertaCorrente.oferta_id`), `:52` (`Pausa.agendamento_ref`), `:60` (`opcoes_t5`).
Provado: 28 % dos uuid4 e 20 % dos uuid7 são recusados por `Referencia`. `ia.agendamento.agendamento_id` é `uuid DEFAULT uuidv7()` (0001:224): cerca de 1 em 5 pausas por
agendamento (B5.7b) falharia ao gravar o estado, de forma intermitente. Caso fixo: `Pausa(agendamento_ref="01912345-6789-7abc-8def-0123456789ab", retoma_fase="E3")` recusado hoje
(o UUID `0192f3a1-7c4e-...` passa). `core.oferta.oferta_id` é `bigint GENERATED AS IDENTITY` (schema 11-s10, estudo I:64 usa `48213`): `OfertaCorrente(oferta_id="115716")` recusado hoje;
o id passa de 6 dígitos com o uso, e a recusa aparece só em produção (as fixtures usam `of-001`). A resposta do autor tratou como «custo aceito»; não é: trava E3–E7.
Correção: `Referencia` aceita UUID inteiro (`^[0-9a-f]{8}-[0-9a-f]{4}-...$`) antes da regra de dígitos; `oferta_id` tipado como `int` (`ge=1, lt=10**9`, como o `perfil`) ou texto
com prefixo de letras. Em qualquer caso, não aplicar `\d{6,}` a identificador gerado pelo sistema.
```python
def test_referencia_aceita_uuid_e_oferta_numerica():
    assert Pausa(agendamento_ref="01912345-6789-7abc-8def-0123456789ab", retoma_fase="E3")  # hoje: ValidationError
    assert OfertaCorrente(banco="FACTA", oferta_id="115716", oferta_versao=1)  # hoje: ValidationError
```

### R2 · M4 não fecha: lease de 12 h × reaper da B1.3 repassa quem espera o cliente
`estado.py` (`LEASE_AGUARDANDO_S = 12 h`) × `feat/b1-3-fila:src/ia_atendimento/jobs.py` `_SQL_LEASES`: seleciona `aguardando_cliente` com `lease_ate < agora` e exclui só job
`doing` ou `todo` JÁ VENCIDO do mesmo chat (`scheduled_at <= agora`). Os dois desenhos batem só em horário comercial. O lembrete fora da janela (08–20 seg–sáb) é ADIADO para a
próxima abertura (`decidir_lembrete` ⇒ `adiar`): IA fala às 16:00 ⇒ lembrete às 20:00+ ⇒ 08:00 do dia seguinte = 16 h; sábado à noite ⇒ segunda 08:00 = 36–60 h. Esse `todo` está no
futuro, logo não protege. Provado com o SQL literal do reaper: `aguardar_cliente` em t0, job `todo` agendado em t0+14 h ⇒ reaper devolve `[]` em t0+11 h e `['aguardando_cliente']`
em t0+12,5 h, 13 h, 13,9 h ⇒ ação `repassar` de um lead que está esperando como planejado, e o lembrete agendado fica órfão. O teste `test_m4_...` (linha 245) só olha 10 h e
afirma uma constante (`LEASE_AGUARDANDO_S >= 10*3600`); não cobre o caso.
Correção (uma das duas, decidir com a B1.3): (a) o reaper ignora `aguardando_cliente` que tenha QUALQUER `todo` de `lembrete`/`encerrar_vacuo` no chat (a exclusão passa a valer
independentemente de `scheduled_at`); ou (b) quem agenda/adia o lembrete chama `renovar_lease(segundos=até_o_job + folga)`. Em ambos, teste de integração estado+SQL do reaper.
```python
def test_lembrete_adiado_para_o_dia_seguinte_nao_deixa_o_reaper_pegar_o_aguardando(db_conn, relogio, versoes):
    # aguardar_cliente às 16:00; job lembrete 'todo' agendado para 08:00 do dia seguinte; em t0+13 h selecionar_leases_vencidos(...) == []  # hoje: [aguardando_cliente]
```

## MÉDIO

### R3 · `renovar_lease` com o padrão ENCURTA o lease de quem espera o cliente
`estado.py` (`renovar_lease`, `segundos=LEASE_TURNO_S`; `_lease(agora, segundos)`): `aguardar_cliente` ⇒ 12 h; `renovar_lease(...)` sem argumento ⇒ 5 min (provado: 12:00:00 → 0:05:00).
Quem chamar «renovar» num aguardando por reflexo cria exatamente o R2. Correção: nunca reduzir (`lease_ate = greatest(...)` no UPDATE ou lendo o valor atual) ou recusar `segundos`
omitido fora de `aberto`/`repassando`. Teste: `aguardar_cliente` + `renovar_lease` ⇒ `lease_ate` não diminui.

### R4 · O trigger terminal só congela 3 colunas; o GRANT deixa mexer no resto do encerrado
`0003_estado_aditivo.up.sql` (cláusula `WHEN`): estado, desfecho e `encerrado_em`. Provado como `ia_app_a` num encerrado: `estado_conversa` vira `{'cpf':'1','fase':'E2'}` (a `fase` gerada
é a «fase_final» que a qualidade L lê), e `motivo_desfecho`, `turnos`, `versao` mudam. `aplicar` bloqueia (`de`), SQL direto não. Correção: acrescentar `estado_conversa` e
`motivo_desfecho` (e `contexto_codigos`, `repasse_*`) ao `WHEN`, mantendo livres `contrato_id`, `pii_auditoria`, `ultimo_cliente_em`, `sinais_cliente`. Se for decisão, registrar a lista das
colunas pós-fim em `OPERACAO.md`. Teste: `UPDATE ... SET estado_conversa = '{"fase":"E2"}'` em encerrado ⇒ `CheckViolation`.

## BAIXO

- **R5 · `Mudancas` ainda aceita `EstadoConversa` forjado:** `EstadoConversa.model_construct(fase="E1", flags={"5511912345678": True})` é gravado (provado), pois `para_json()` não revalida.
  Correção: `ConfigDict(revalidate_instances="always")` em `Mudancas` ou `EstadoConversa.model_validate(valor.model_dump())` em `_valor_sql` (`estado.py`).
- **R6 · A1 sem teste da camada Python:** com `de` padrão trocado por «todos os estados» a suíte dá 202 passed (o trigger cobre). Cada camada sozinha: o trigger é guardado por
  `test_migracao_0003.py:234`; o padrão de `aplicar(de=)` não. Teste: `inspect.signature(aplicar).parameters["de"].default == ESTADOS_NAO_TERMINAIS`.
- **R7 · 0003 desatualizada em dois pontos:** (i) a linha 3 do SQL («Desfazer: ... os CHECKs só recusam o que o contrato já recusa; nada é apagado») não menciona o trigger nem o CHECK
  fase×estado; documentar `DROP TRIGGER atendimento_terminal_absorvente`, `DROP FUNCTION ia.fn_atendimento_terminal()`, `DROP CONSTRAINT atendimento_fase_estado_check`.
  (ii) A pré-checagem de `OPERACAO.md` (passo 3a) só conta `chat_id` e `chats_teste`; o `ADD CONSTRAINT atendimento_fase_estado_check` também valida a tabela inteira. Acrescentar
  `SELECT count(*) FROM ia.atendimento WHERE estado IN ('aberto','aguardando_cliente') AND (fase !~ '^E[1-9]$' OR estado_conversa ? 'pausa')` = 0.
- **R8 · `janela_24h_aberta(naive, agora)` levanta `TypeError` cru** (`estado_conversa.py`, subtração de naive com aware). Uma linha: `ValueError("fuso")`.

## Tautologia: 3 testes de `test_estado_revisao1.py` que reprovam se a correção for desfeita (cópia mutada, nenhum arquivo do repo tocado)

| Correção desfeita | Teste que reprova | Linha |
|---|---|---|
| A3: `registrar_...` sem a checagem do futuro | `test_a3_registrar_mensagem_no_futuro_e_recusado_e_nao_grava` | 106 |
| A4: tradução feita DENTRO do `except` (volta o `__context__`) | `test_a4_abrir_nao_deixa_psycopg_cru_nem_a_linha_na_mensagem` (+ `...not_null...`) | 122 (150) |
| M3: `encerrar(repassado)` volta a valer de qualquer estado | `test_m3_repassado_so_a_partir_de_repassando` | 226 |

Também reprovam: A2 (tipo volta a `Any`, 7 falhas, linha 85), M1 (sem `_sem_documento`, 8 falhas, linha 177), M5 (linha 273), B3 (linha 317), B4 sem o CHECK (linha 327 e
`test_migracao_0003.py:280`), origem (linha 141), perfil com float (3 falhas). Não detectam: `test_a1` (linha 73) cai nas duas camadas, só o trigger tem teste próprio (R6);
`test_m4_...` (linha 245) é praticamente a constante (R2). Mutação com a mensagem «sem linha» trocada por texto vazio sobrevive, mas não é falha: o teste confere ausência de «Failing row» e do `perfil`.

## Ordem das correções

1. **R1** (UUID/`oferta_id`): barato e é a única regressão funcional. 2. **R2** (+R3) com a dona da B1.3: o reaper ou o lease, e o teste de integração. 3. **R4** no `WHEN` da 0003 (ainda não aplicada, é de graça agora). 4. R5–R8 no mesmo PR.

---

## Resposta do autor (r2) · 30/10 · commit `fix: estado — correções da revisão 2 (R1–R8)`

Casos da revisão primeiro em `tests/test_estado_revisao2.py` (vermelhos: ImportError dos símbolos novos, 5 falhas do trigger, 1 do `model_construct`), depois a correção. Suíte: 905 → 930 passed, 2 xfailed (`check.sh` verde). Mutações que reprovam: R1 (volta o `\d{6,}`, 2 falhas), R2 (lease antigo, 2), R3 (sem `greatest`, 1), R4 (trigger sem `estado_conversa`, 1), R5 (sem revalidação, 1).

| Achado | Resposta |
|---|---|
| **R1** | Corrigido. `_sem_documento`: UUID inteiro passa; o resto é conferido sem os `.`/`-` entre dígitos e recusa só **11 dígitos** (CPF/celular, mascarados ou não), **14** (CNPJ) e **55+10/11** (telefone com país). `oferta_id` de 6–9 dígitos passa (testado com 115716, 48213, 4821300000). Testes: 2000 uuid4 + 2000 uuidv7 em `Pausa` e `OfertaCorrente`. Continuam recusados `123.456.789-09`, `12345678909`, `5511912345678`, `11-91234-5678`, `cpf12345678909`. Custo restante: id numérico de exatamente 11 ou 14 dígitos seria recusado (não existe hoje; `oferta_id` é bigint curto). |
| **R2** | Escolhi a opção que **não muda o PR #2**: o lease cobre a espera. Novo `lease_de_espera(agora, *, intervalos_min, proxima_janela, ...)` (puro; o chamador passa `lembretes_intervalos_min` e o `Calendario.proxima_janela` da B1.3): cada lembrete sai `intervalo` depois do anterior, adiado para a próxima abertura se cair fora da janela; soma 120 min até o encerramento (H E9) + 30 min de folga. `aguardar_cliente(..., lease_ate=)` grava esse valor (recusa lease no passado); sem ele vale o teto `LEASE_AGUARDANDO_S = 96 h` (fim de semana + feriado + DATAPREV). Como o alarme do lembrete não leva lock do chat (comentário do próprio `jobs.py`), só o lease o protege. O teste de integração roda o **`_SQL_LEASES` literal de `feat/b1-3-fila` (dd806ab)** contra o estado: terça 16:00, em 1/4/13/14/20 h o reaper devolve `[]`, e só passa do `lease_ate` devolve o lead. Obs.: o `leases.sql` da sonda tinha a versão antiga do reaper (exclusão por `scheduled_at <= agora`); a atual exclui qualquer `todo` com lock, mas o alarme não tem lock, então o problema era real do mesmo jeito. **Quem chama (B1.4):** `aguardar_cliente(..., lease_ate=lease_de_espera(agora, intervalos_min=cfg, proxima_janela=cal.proxima_janela))`. |
| **R3** | `renovar_lease` usa `greatest(lease_ate, novo)` no UPDATE (`aplicar(lease_so_cresce=True)`): nunca encurta; o teste confere aguardando + renovar. |
| **R4** | O `WHEN` do trigger inclui `estado_conversa`, `motivo_desfecho`, `contexto_codigos`, `repasse_modo` e `repasse_consultor_ref`. Livres depois do fim: `contrato_id`, `pii_auditoria`, `sinais_cliente`, `ultimo_cliente_em` e os contadores. Lista registrada em `OPERACAO.md`. |
| **R5** | `revalidate_instances="always"` em `_Base` de `modelos_conversa.py` (tem de estar no modelo aninhado, não em `Mudancas`). |
| **R6** | `test_r6_aplicar_tem_por_padrao_so_os_estados_nao_terminais`; `test_r6_a1_camada_python_sozinha_com_o_trigger_desligado` (superusuário desliga o trigger e `aplicar` ainda recusa, `restricao is None`); `test_r6_a1_camada_do_trigger_sozinha_com_de_aberto_a_todos`. |
| **R7** | Cabeçalho da 0003 ganhou o desfazer à mão (trigger, função, 3 constraints); pré-checagem da fase×estado em `OPERACAO.md` e `migrations/README.md`. |
| **R8** | `janela_24h_aberta` levanta `ValueError` («fuso») com datetime sem fuso. |
| **test_m4** | O teste de constante saiu; o comportamental (reaper da B1.3 em 5 instantes) o substitui. |
