# Revisão da B1.6a (04/11): ledger `t11`, cerca de `versao`, `executar_efeito`, gasto Σ, `ia_ativa` relida, lease de espera e `expirar_parados`

Revisor independente, com contexto limpo (Claude Opus 5.5). Não escrevi nada deste código e não editei nenhum arquivo dele: as mutações e as sondas
rodaram numa cópia descartável (`git archive HEAD`) fora do worktree.
Branch `feat/b1-6a` @ `4ddc03a` (7 commits sobre a `main` `9bee6a4`, que já tem o #11). Ainda não há PR aberto para a branch.
Referências: roteiro v3.3 B1.6 (divisão RG-045, D-14, D-15), contrato 08 v2.3 §6, §7.3, §7.4 e §9, `docs/DECISOES-B1.6a-0411.md`, DDL 0001.

## Segundo revisor (Codex)

**Falhou e não deu achado.** O `codex exec -s read-only -m gpt-6.1-sol` (xhigh) terminou com `ERROR: You've hit your usage limit … try again at
3:52 PM`, depois de várias leituras recusadas no sandbox (`python: command not found`). Saída em
`/tmp/claude-1001/-opt-claude/c3edfc59-52d9-4e44-8d0b-adab74392dfc/scratchpad/codex-b1-6a.txt`. Todos os achados abaixo são **[Claude]**. Os que
coincidem com os quatro do revisor automático de segurança (seção final do DECISOES) aparecem como **[Claude + autoachado]**.

## Portão

`BANCOS_DUBLE_PATH=/home/danilo/wt-ia/bancos-duble-main-b16a` (`f6ec889`, igual a `origin/main`), rodado com `flock ~/.c360-pesado.lock bash scripts/check.sh`.
**Verde:** lock, ruff, format, varredura, gitleaks, sha da 0001, 0002 e `pessoas_teste` em dia. **3.284 testes passaram e 1 foi pulado**
(`test_corpus_revisao2.py:248`, falta `yaml` no ambiente; o pulo já vinha de antes e não é desta etapa), em 328 s.

## Testes que reprovam sem a mudança: 18 mutações, 18 mortas

Cada mutação foi aplicada numa cópia, rodou o arquivo de teste da área e depois foi desfeita.

| # | Mutação | Teste que a matou |
|---|---|---|
| M1 | falha de efeito irreversível vira `transitorio` | `test_timeout_vira_indeterminado_e_nunca_reenvia` |
| M2 | devolução sem conferir posse real | `test_parada_dura_sem_posse_real_simula_a_devolucao` |
| M3 | T7 sem exigir confirmação | `test_t7_sem_confirmacao_aceita_levanta_antes_do_banco[nenhuma]` |
| M4 | cerca sem `AND versao = %s` | `test_execucao_superada_nao_envia_e_o_canal_e_chamado_uma_vez` |
| M5 | `enviada` velha nunca é dada como morta | `test_enviada_achada_no_retry_vira_indeterminado_sem_chamar` |
| M6 | modo global ignorado | `test_modo_efetivo_relido_a_cada_efeito_e_gravado_no_ledger` |
| M7 | soma do gasto sem o limite do fim do dia | `test_conversa_que_atravessa_a_meia_noite_conta_cada_passo_no_seu_dia` |
| M8 | `custo_ausente` contado só por tokens | `test_custo_ausente_conta_passo_com_tokens_ou_do_modelo_sem_custo` |
| M9 | nível 125 % vira ≥ 100 % | `test_80_100_125_por_cento[…critico]` |
| M10 | `encerrar_por_chave` não relê `ia_ativa` | `test_encerrar_por_chave_com_a_ia_religada_nao_fecha` |
| M11 | `iniciar` não relê `ia_ativa` | `test_iniciar_com_a_ia_desligada_aborta_antes_do_assumir_e_emite_encerrou` |
| M12 | `reservado` agendado não relê `ia_ativa` | `test_reservado_agendado_com_a_ia_desligada_nao_dispara_e_aborta` |
| M13 | `expirar_parados` sem a guarda de job do chat em curso | `test_chat_com_job_em_curso_fica_para_a_proxima` |
| M14 | `expirar_parados` com a config de agora | `test_dias_max_e_o_da_versao_vigente_em_iniciado_em` |
| M15 | lease com a faixa da config de agora | `test_faixa_e_a_da_versao_vigente_em_iniciado_em` |
| M16 | a entrada engole `GastoIndisponivel` | `test_entrada_com_gasto_nao_calculavel_responde_503_nao_pronto_e_nao_grava` |
| M17 | `expirar_parados` não emite o `encerrou` | `test_expira_aberto_e_aguardando_alem_do_dias_max_da_faixa` |
| M18 | o corte (`CancelledError`) não grava no ledger | `test_cancelled_no_meio_do_envio_deixa_indeterminado_e_nao_reenvia` |

O aceite «`indeterminado` nunca reenvia, provado por mutação» está cumprido (M1, M5, M18). Ainda assim, as sondas abaixo acharam
comportamento que **nenhum** teste cobre (A1 a A3).

## Achados

Gravidade: CRÍTICO bloqueia; ALTO deve ser corrigido antes do merge; MÉDIO convém corrigir; BAIXO é opcional ou fica como pendência.

### A1 · ALTO · [Claude] Devolução sem posse real corre REAL quando `config.modo = real`

`src/ia_atendimento/ledger.py:256-259` (`_modo_do_efeito`). Sem posse real, a devolução cai em `modo_efetivo(atendimento, global)`. Com o
atendimento e o global em `real`, isso dá `real` e chama o destino. O contrato 08 §6, exceção 2, diz: «Atendimento sem posse real (nasceu
`sombra|duble`, **ou o `assumir` nunca fechou `ok`**): T12, repasse, nota e `restaurar` são **simulados por inteiro**, sem chamar o `chatguru-api`
nem o `ia-repasse`». A D10 do próprio DECISOES também diz «Sem posse real, simulada». O código só faz isso sob parada dura.
**Cenário:** atendimento `real`, `assumir` termina `indeterminado` ou `transitorio`, e o processador (B1.6b) repassa depois de 2 falhas. O T12 real
roda o rodízio do `zVuE` e o `restaurar` real mexe no chatbot e na delegação de um chat que a IA nunca tomou.
**Sonda (reprova hoje):**
```python
_config(conn_app, relogio, "modo", "real")
atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
await _executar(conn_app, relogio, atd, _assumir(atd), Espia(Desfecho("indeterminado")))
espia = Espia(); await _executar(conn_app, relogio, atd, _t12(atd), espia)
assert espia.destinos == []   # hoje: ['real']
```
**O teste que existe não pega:** `test_parada_dura_sem_posse_real_simula_a_devolucao` só cobre o global `sombra`.
**Correção sugerida:** para `pedido.devolucao`, use o modo do atendimento se houver posse real. Sem posse, grave um modo simulado (`sombra` ou
`duble`, nunca `real` nem `teste`) e não chame `chamar`. Inclua a sonda acima como teste.

### A2 · ALTO · [Claude + autoachado 1] A confirmação da T7 só confere `estado = 'aceita'`

`src/ia_atendimento/ledger.py:244-253`. O código não confere `tipo` (`digitacao`), nem `banco` igual ao do pedido, nem vencimento, nem uso único.
**Sondas (reprovam hoje):**
- T7 `banco='C6'` com uma confirmação aceita da FACTA não levanta `ConfirmacaoAusente`;
- T7 com a confirmação aceita e o relógio 3 h à frente (`expira_em` = criada + 30 min) não levanta.

O índice `ferramenta_chamada_t7_atendimento_uq` já impede reusar a confirmação para uma 2ª T7 viva ou `ok` no mesmo (atendimento, banco). Ele não impede
digitar em outro banco com o «sim» dado para a FACTA, e é isso que fura o «confirmação ligada ao DADO» do DDL (`0001`, comentário da `ia.confirmacao`).
**Correção:** `SELECT … FOR SHARE` com `tipo = 'digitacao'`, `banco = pedido.banco` e `respondida_em <= expira_em`, mais um prazo de uso
(`agora <= expira_em` ou um prazo explícito). Conferir `valores_hash` exige que o `args_hash` traga o mesmo hash: decidir na B1.6b junto com o
`criar_confirmacao`. Um teste por regra.

### A3 · MÉDIO · [Claude + autoachado 3] A chave do ledger não está presa ao atendimento

`src/ia_atendimento/ledger.py:295-310` e `:375-389`. `_ler` busca só por `idem_key` e `_reivindicar` só por `chamada_id`. Um pedido do atendimento B
com a `chave_logica` do atendimento A reivindica a linha `transitorio` de A e chama o destino. O modo e a posse usados são os de B; a linha é de A.
**Sonda (reprova hoje):** `t12:{A}` termina `transitorio` em A; o mesmo `Pedido` executado para B gera `espia.destinos == ['real']`.
Hoje as chaves levam o atendimento (`t11:{atd}`, `t12:{atd}`, `assumir:{atd}`), então isso pede erro de quem chama. Mas a `idem_key` é única no
banco todo (o DDL lembra que a `t4` não leva o atendimento) e o gateway da B5.1 vai montar chaves.
**Correção:** ao achar a linha, conferir `atendimento_id`, `ferramenta`, `banco`, `args_hash` e `confirmacao_id` e recusar divergência
(`EstadoErro`). Pôr `atendimento_id` no `WHERE` do CAS de reivindicação.

### A4 · MÉDIO · [Claude + autoachado 4] A reivindicação pode rebaixar o modo e apagar a posse

`src/ia_atendimento/ledger.py:307-309`. O `modo` é relido e sobrescrito no CAS `→ enviada`. Concordo com o risco que o autoachado descreve, sem
sonda própria: o `assumir` em `real` dá timeout e termina `transitorio` (`_desfecho_da_falha`, `:336-338`, porque `acao_interna` nunca vira
`indeterminado`), mesmo que a delegação possa ter acontecido. Vem a parada dura, a repetição é simulada e fecha `ok`/`sombra`, e `posse_real()` fica
falso. A devolução então é simulada (exceção 2) e o lead fica com o Amado e o chatbot desligado, até a vigia R-b.
**Correção:** não reivindicar em modo mais fraco que o já tentado. Guardar o modo mais forte (não sobrescrever `real|teste` por `sombra|duble`) ou
deixar a linha em `transitorio` e devolver sem chamar. Também vale decidir com o dono se o `assumir` sem resposta deve contar como posse
«possível» para a devolução.

### A5 · BAIXO · [Claude + autoachado 2, reduzido] A reivindicação roda sem a cerca

`src/ia_atendimento/ledger.py:276-310`. A sonda mostrou que um `transitorio` repetido em atendimento **encerrado** é recusado: `_cercar` roda antes
do `ON CONFLICT` e levanta `TransicaoInvalida`. Uma repetição com versão velha também é barrada (`ConflitoVersao`, M4). O que resta é a janela entre o
`ROLLBACK` da transação da cerca (a chave já existia) e o CAS de `_reivindicar`, que não reconfere estado nem versão. A gravidade baixa de MÉDIO para
BAIXO, mas a correção é a mesma do A3: CAS de reivindicação e cerca na mesma transação.

### A6 · BAIXO · [Claude] `simular` que levanta exceção deixa a linha `enviada`

`src/ia_atendimento/ledger.py:342-343`. A exceção do `simular` não é tratada. A linha fica `enviada` até `timeout_s + 30 s` e depois a repetição a
grava como `indeterminado`, sem nada ter saído. Isso suja a métrica e, numa T11 simulada, impede a resposta. Tratar como `transitorio` (nada saiu) ou
deixar a exceção sem reivindicar.

### A7 · BAIXO · [Claude] Limite zero leva a `repassar`

`src/ia_atendimento/gasto.py:92-93` (D3). O DDL aceita `subteto_dia = 0`. Se o operador zerar o limite para barrar entrada nova, o `turno` da B1.6b
repassa **todos os abertos** no turno seguinte. Isso contraria «100 % ⇒ crítico, os abertos concluem» do 08 §9. Sugestão: limite zero com gasto zero
fica `critico`, não `repassar`. Ou pedir ao dono para confirmar a D3.

### A8 · BAIXO · [Claude] `expirar_parados` faz N+1 e pode deixar candidatos de fora

`src/ia_atendimento/expiracao.py:116-134`. Faz um `config_em` por candidato, até 1.000 por rodada, ordenados por `iniciado_em`. Com mais de 1.000
abertos de mais de 1 dia ainda dentro do `dias_max`, os mais novos com `dias_max` menor ficam de fora. No piloto (≤ 10 por dia) não acontece.
Também: o prazo é contado de `iniciado_em` (D17), não de «parado» (`atualizado_em`, que tem `idx_atendimento_parado`). Está coerente com o
`dias_max` como vida máxima do atendimento; fica anotado.

### A9 · BAIXO · [Claude] `test_o_job_usa_o_servico_de_producao` só confere `configurado()`

`tests/test_expirar_parados.py:82` e `src/ia_atendimento/worker.py:55`. O teste não executa a lambda de produção: qualquer chamável que não fosse o
`_NaoConfigurado` passaria. Sugestão: chamar `servicos.expirar_parados()` contra o banco do teste e conferir o encerramento.

### A10 · BAIXO · [Claude] Teste instável na virada do dia

`tests/test_gasto_pendente.py:57`. `test_gasto_do_dia_soma_passos_em_brt_e_todos_os_modos` (veio da `main` como `xfail` e agora está ativo) usa
`datetime.now(UTC)` e o `now()` do banco. Se a meia-noite de São Paulo cair entre os dois, ele falha. A janela é mínima; trocar por um relógio fixo.

### A11 · BAIXO · [Claude] Aderência: itens novos da v3.3 sem dono declarado

O DECISOES («Ficou de fora») não diz onde ficam três itens do roteiro B1.6: **RG-075** (`texto_livre.casos.json` «nasce aqui», com o sha anotado,
copiado por B6.2/B7.1), **RG-104** (`texto_mensagem` > 4000 ⇒ truncar, marcar e logar, não 422) e **RG-006** (`turnos_max = 24`). Os três cabem na
B1.6b (processador e entrada). Basta escrever isso na tabela, para a B6.2 e a B7.1 não ficarem esperando. Os testes do roteiro
`test_teste_nunca_alcanca_facta_real` e `test_sombra_nunca_alcanca_facta_real_nem_canal` existem no nível do ledger com outros nomes
(`test_teste_vai_ao_destino_de_teste`, `test_sombra_e_duble_nunca_chamam_o_destino`). As versões com o gateway e o `Canal` são da B5.1 e da B1.6b.

## Conferido e sem achado

- **D7 (reivindicar `reservada`)**: está certa. O CAS `reservada → enviada` é commitado antes da chamada, então uma linha `reservada` prova que nada
  saiu. `enviada` nunca é reexecutada. A corrida de duas execuções tem teste.
- **D5/D8**: a reserva e o `enviada` ficam commitados antes de `chamar` (autocommit exigido e testado). O timeout, a exceção e o corte vão para
  `indeterminado` no efeito irreversível. O fechamento roda sob `shield`.
- **Gasto (§9)**: Σ `passo.custo_brl` por `ocorrido_em` em São Paulo, todos os modos contam, sem dupla contagem do ledger nem do atendimento, e
  `GastoIndisponivel` dá `503 nao_pronto` com log crítico sem valor. A entrada não tem cache e o `MedidorGasto` guarda por 30 s.
- **`ia_ativa` relida** (DECISOES-B1.5:69): `encerrar_por_chave`, `iniciar` e o `reservado` agendado leem o banco sem cache. O abort vem antes do
  `assumir`, com o `encerrou` na mesma transação. A mudança de 6 testes da B5.7b (ligar `ia_ativa` no apoio) é legítima e não afrouxa nada.
- **Outbox do espelho**: exige transação aberta, trava a linha do atendimento e calcula `seq = max + 1`. `detalhe` leva só o desfecho e o instante.
- **Pools** do worker e da API em `autocommit=True`, então o `conn.transaction()` de `expirar_um` é uma transação de verdade, não um savepoint.
- **PII e restrições**: o diff não tem CPF, e-mail, credencial nem texto de conversa. Os logs não levam valor. Os fixtures citam só
  DeepSeek/Fireworks. Não há migração nova (a 0006 continua livre) e nenhuma migração da `main` foi editada. Nada tocou S2, S4, VPS, n8n, Coolify,
  tag nem merge.

## Veredito

**Não mesclar como está.** O portão está verde e os testes que existem reprovam sem a mudança (18 de 18 mutações mortas). Mas há **2 ALTOS**:
A1, que é novo (a devolução real sem posse fere o 08 §6, exceção 2, e a D10), e A2 (a confirmação da T7 não amarra o banco nem o prazo). O próprio
DECISOES pede que A3 e A4 sejam fechados antes de qualquer merge. Cada correção deve vir com a sonda correspondente virando teste, para provar que
ele reprova sem a correção.
