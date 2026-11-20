# Revisão independente da B1.6b (20/11/2026)

Revisor: agente revisor de Python com contexto limpo, diferente de quem implementou (regra do dono: quem implementa não revisa). Escopo:
`git diff feat/b1-6a..feat/b1-6b` (commits `642a67b`, `d47606e`, `cb77d4b`) e o último commit da B1.6a (`97950ab`, ledger). Leitura do
código, do contrato 08 §6, §7.1–§7.4 e §9 e do esquema; sem rodar testes. Veredito do revisor: **bloquear** (3 ALTO, 5 MÉDIO, 6 BAIXO,
nenhum CRÍTICO). O `97950ab` (G-0131, G-0087, G-0454 no ledger) saiu sem achado.

Depois da correção, cada achado corrigido tem teste que **reprova no código revisado** (conferido: 15 dos 18 testes novos reprovam com os
arquivos da revisão; os 3 que passam nos dois são guardas de caminho feliz). Destino de cada achado:

| # | Gravidade | Achado | Destino | Testes |
|---|---|---|---|---|
| 1 | ALTO | `repassando` sem job: worker morto entre a fase 1 (commit) e o defer, ou job que esgota o retry; o `reaper_lease` não olha `repassando` | corrigido: `repasse.repasses_sem_job` (sem job `todo\|doing` com `queueing_lock repasse:{atd}`, sem `repasse_travado`, parado há > 2 min) e a rodada periódica do `reaper_ledger` (montagem) reenfileira com alerta amarelo `repasse_sem_job`. Defer na mesma transação do CAS fica para a integração com a fila (B1.7) | `test_repassando_sem_job_e_achado_pela_rede` |
| 2 | ALTO | T11 em dobro no retry do turno: a nova execução abria `rodada + 1` e chamava o modelo de novo | corrigido: turno bom sempre termina em `aguardando_cliente`/`repassando`; quem chega em `aberto` (retry) com T11 da rodada corrente no ledger não chama o modelo, fecha o turno e alerta `turno_retomado_sem_reenvio`. O texto que faltou se perde (nunca duplica; RS-10 vale mais) | `test_retry_do_turno_que_morreu_depois_de_enviar_nao_responde_de_novo` |
| 3 | ALTO | `iniciar` que morre depois do `assumir ok` nunca completa e o chatbot fica desligado | corrigido: no retry vale a versão atual e o que o LEDGER gravou (`modo` e `ref_externa`); `desligado_pela_ia` pelo modo gravado, não por `executou` | `test_retry_do_iniciar_depois_do_assumir_completa` |
| 4 | MÉDIO | estado do T11 ignorado (recusa/transitório contados como enviados) | corrigido: `enviada` ⇒ `em_andamento` e reagenda; fora de `ok\|indeterminado` ⇒ repasse `envio_falhou`; simulado não conta em `mensagens_enviadas` | `test_envio_que_nao_saiu_repassa_e_nao_conta[2]` |
| 5 | MÉDIO | `impedido` do espelho em `sombra` viola `atendimento_sombra_check`; `_marcar` em transação separada | corrigido: sombra fecha `sem_venda/devolvido_pela_s2`; marcar e encerrar na mesma transação | `test_impedido_em_sombra_fecha_sem_venda` |
| 6 | MÉDIO | batimento fail-open com `gerado_em` no futuro; `recem_voltou` só marcava com consulta | corrigido: idade fora de [−30 s, 90 s] ⇒ indisponível; `atualizar()`/`disponivel()` marcam o episódio; um alerta crítico por episódio (BAIXO 12) | `test_gerado_em_no_futuro_alem_de_30s_e_indisponivel`, `test_indisponibilidade_sem_consulta_ainda_exige_vivos_na_volta`, `test_um_alerta_por_episodio_de_indisponibilidade` |
| 7 | MÉDIO | reaper fechava T7 viva (125 s no catálogo) aos 40 s | corrigido: prazo por ferramenta do catálogo (`nome_no_ledger → timeout_s`), mínimo de 10 s + 30 s | `test_t7_lenta_segue_o_prazo_do_catalogo[2]` |
| 8 | MÉDIO | motivo `humano_assumiu` sem `humano_assumiu_em` prende o repasse (CHECK `atendimento_qualidade_check`) | corrigido: `estado.repassar` aceita e exige o instante; `iniciar_repasse` o grava e o `encerrar` relê o da fase 1; motivo fora de `^[a-z0-9_]{1,60}$` vira `repasse` | `test_motivo_humano_assumiu_fecha_o_repasse`, `test_motivo_fora_da_forma_vira_repasse`, `test_motivo_do_modelo_fora_da_forma_nao_derruba_o_repasse` |
| 9 | BAIXO | resposta inválida fecha o T12 como `recusa` (terminal): reenfileirar não destrava | registrado: destravar exige ato da TI (nova chave `t12` com tentativa, B6.4/kit); o alerta crítico sai na hora | — |
| 10 | BAIXO | `porta.publicar` sem timeout | corrigido: `asyncio.timeout(10 s)` | coberto por `test_falha_repete_com_backoff_sem_pular_a_ordem` |
| 11 | BAIXO | 1ª rota sem consultar o batimento quando nota e chatbot já tinham marco | corrigido: consulta uma vez antes da 1ª rota | coberto pelos testes do repasse |
| 12 | BAIXO | tempestade de alertas; `conferir` levanta em caminho de erro | corrigido: um alerta por episódio; `AlertasEmLog` troca alerta fora da forma por `alerta_invalido` em vez de levantar | `test_um_alerta_por_episodio_de_indisponibilidade` |
| 13 | BAIXO | nota `""` quebra `Mudancas`; texto que muda entre retries | corrigido o vazio (vira `nao_aplica`); texto que muda: o `texto_da_nota` real tem de ser determinístico (registrado para a B5.5) | `test_nota_vazia_nao_se_aplica` |
| 14 | BAIXO | `_anotar_rodada(falhou=True)` sem capturar `ConflitoVersao` | corrigido: `superado` | — |

Também corrigido junto (o revisor apontou o teste frouxo): o prazo de D-14 agora só marca a próxima tentativa se ela cabe nos 30 min;
o teste afirma exatamente 9 tentativas, a última aos 1.570 s (≈ 26 min), como no 08 §7.2.

## O que o revisor conferiu e deu como certo

Autocommit e transações do ledger dentro do repasse; CHECKs de `repasse_nota_enviada`/`nota_repasse_tamanho`, `repasse_modo`,
`contexto_codigos` e `ref_externa`; nota com chave única, `indeterminado` que nunca repete e `args_hash`; outbox (`detalhe`, `chave`);
o TOCTOU do gateway fechado (nenhum `await` entre a última conferência e o executor); gasto e disjuntor sem desvio do §9.
