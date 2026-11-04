# Revisão B1.8 · Domingo por config (D-18): migração 0005 e calendário · 04/11

Revisor independente de contexto limpo (Claude Opus 5.5; não escreveu o código) + Codex `gpt-6.1-sol` xhigh, só leitura, como segundo revisor.
Escopo: `origin/main...feat/b1-8` (5 commits, `20f8860`..`8eec159`; 19 arquivos, +558/−58). Spec: roteiro v3.3 §B1.8 (linha 913), D-18,
`estudos/ESTUDO-D18-domingo.md` §1 e §8, `docs/DECISOES-B1.8-0411.md`. Nada foi editado no código; nenhuma ação fora da máquina local.

## Veredito

**Aprovável, com 1 achado MÉDIO** (agenda × horário do dia 7) que ou se corrige antes do merge ou passa, registrado, para a B5.7d. Nenhum
CRÍTICO ou ALTO. Portão verde, spec atendida, fechado por padrão confirmado, testes reprovam sem a mudança (14 mutações, 13 mortas; a que
sobrevive é equivalente).

## Portão

`BANCOS_DUBLE_PATH=/home/danilo/wt-ia/bancos-duble-main-b16a` (detached em `f6ec889` = `origin/main`), com `flock ~/.c360-pesado.lock`:
`bash scripts/check.sh` **OK**: lock, ruff check/format, varredura, gitleaks, sha da 0001, 0002 e pessoas_teste em dia;
**3229 passed, 1 skipped (yaml), 1 xfailed (B1.6, já conhecido)** em 395 s.

## Achados

| # | Gravidade | Origem | Arquivo:linha | Achado | Sugestão |
|---|---|---|---|---|---|
| R-01 | **MÉDIO** | Claude **e** Codex (independentes, mesmo achado) | `src/ia_atendimento/agendamento.py:119-127`; `src/ia_atendimento/agenda_extrator.py:578-596` | A agenda recebe só `domingo_aberto` do `Calendario` e descarta o **horário** de `janela_mensagem.dias."7"`. Aberto, o domingo usa a `agenda_janela` (08:30–19:00). Com domingo publicado 09:00–18:00 (o exemplo dos próprios testes), reproduzido: sábado 10:00, «domingo às 8:30» ⇒ aceito sem razão, e `Calendario.dentro_da_janela(08/11 08:30)` = `False`; Codex reproduziu também «domingo às 19h» pedido no domingo. A API reserva uma volta que o envio não pode cumprir. O limite legal 08–20 nunca é furado (CHECK da `agenda_janela`); fura-se só o horário escolhido pelo operador. A mesma lacuna existe antes para seg–sáb (a agenda nunca leu `janela_mensagem` por dia; se o sábado sair da janela, a agenda ainda o aceita), mas com os defaults nunca aparecia: o domingo é o 1º caso real. O teste `test_api_config_agenda.py:275` usa 08–20 e não pega | Em `_razoes`, acrescentar razão (`antes_da_janela`/`depois_da_janela`, ou nova `fora_da_janela_mensagem`) quando `q` não está em `calendario.dentro_da_janela`, passando os `dias` à `ConfigAgenda`; ou interseção `agenda_janela ∩ janela_mensagem[dia]` em `config_da_agenda`. Teste com domingo 09–18. Alternativa mínima: o kit `config/domingo.sh` (B6.7) só publica o dia 7 como 08:00–20:00 e a B5.7d registra a lacuna |
| R-02 | BAIXO | Claude | `src/ia_atendimento/agenda_jobs.py:10-21` (fora do diff) | Fechar o domingo depois de agendar não cancela a volta já marcada para domingo: o `retomar` não reconsulta o calendário (a pré-checagem é da B5.7c, `Servicos.retomar_atendimento`). O estudo D-18 §1.3 já chama isso de armadilha, e `DECISOES` deixa para B5.7c/B5.7d e para a operação. Não é defeito desta branch | B5.7c: a pré-checagem da volta inclui `dentro_da_janela` do calendário vigente; `domingo.sh fechar` avisa quantos `confirmado` caem no domingo |
| R-03 | BAIXO | Claude | `src/ia_atendimento/calendario.py:79-83` | A «defesa em profundidade» D5 em `_horario` é **mutante equivalente**: com ela removida (M3), todos os testes passam e o comportamento observável é o mesmo, porque `bloqueado()` já fecha o domingo e `proxima_janela` só dá um passo a mais. A frase de D5 («pula para segunda sem parar no domingo») descreve só um passo interno | Manter (custa nada) ou tirar; ajustar o texto de D5 para não sugerir diferença de comportamento |
| R-04 | BAIXO | Claude | `src/ia_atendimento/calendario.py:126,154`; `docs/OPERACAO.md` §3 | Volta de imagem: com a 0005 aplicada e as chaves abertas (`domingos=false` ou dia 7), uma imagem anterior à B1.8 recusa a config (`CalendarioInvalido`) em entrada, lembrete e agendamento. Isso é fail-closed (D-15), mas aparece como erro interno e não como recusa | No kit `domingo.sh`/A4.6, uma linha: «antes de voltar a imagem para < B1.8, `domingo.sh fechar`» |
| R-05 | BAIXO | Claude | `docs/DECISOES-B1.8-0411.md:3`; roteiro B5.7d/B8.1c | (a) Diz «roteiro v3.3 B1.8 (linha 850)»; a seção está na linha 913. (b) A branch já entrega parte da B5.7d (`ConfigAgenda.domingo_aberto`, `_dia_util`, `_razoes`) e da B8.1c (`corpus/calendario.py` com parâmetro). Isso está certo e documentado, mas o Painel/Kan precisa dizer o que sobra (B5.7d: ≥ 12 frases, hold-out, `pausado` sáb→dom; B8.1c: I3/gabarito/agenda e personas) para não refazer | Corrigir a linha; anotar o resíduo nas etapas |
| R-06 | INFO | Claude | `tests/casos/casos_c.py:284` | A spec pede para parametrizar o caso; D2 o mantém porque a suíte de 350 casos roda só a 0001 (`test_esquema.py:30-32`), em linha com o estudo §8 («`i-teste-0001.sh:318` fica como está»). Conferido: a «inversão» está em `test_migracao_0005.py` (recusa até a 0004, aceita com a 0005). Aceito | — |
| R-07 | INFO | Codex | — (ambiente, não o diff) | O Codex relatou que algumas leituras do ambiente mostraram `project_ref` completos e senhas fictícias do harness de teste. Os valores não foram repetidos aqui. Não há segredo nas linhas adicionadas: gitleaks verde e varredura de CPF/e-mail nas adições sem nada | Nada a fazer no PR |

## Spec e decisões: conferência

- **0005 só DDL**, `DROP` e `ADD CONSTRAINT` do `config_versao_valor_check` no **mesmo** `ALTER TABLE`, `SET ROLE ia_owner`, `lock_timeout 3s`.
  O CASE é cópia da 0001 com um único termo a menos. Conferido à mão e por `test_0005_copia_o_case_da_0001_com_um_unico_termo_a_menos`.
  A 0003 e a 0004 **não** tocam o `valor_check` (só a 0003 cria o `chats_teste_check`, que continua): a cópia da 0001 não desfaz nada posterior.
  O 08–20 vale para os 7 dias. Seeds e `PADROES` não mudam. A 0001 não muda (sha verde no portão). A migração é aditiva no efeito (só afrouxa),
  então o `ADD CONSTRAINT` revalida sem falhar. Ledger: `migrations/README.md` passo 5 e `OPERACAO.md` §3, com «sim» nomeado (PD-2, A4.6).
- **Duas chaves, fechado por padrão (D-18/D-15):** `domingo_aberto = not domingos and 7 in dias`. `domingos` precisa ser bool estrito:
  `"false"`, `0`, `null` e ausente são recusados (testado). O piso de feriados 02/11 e 20/11 e da DATAPREV não mudou. 22/11 (domingo na
  DATAPREV) segue fechado aberto ou não (testado).
- **Consumidores:** `chave.py:250`, `api/agendamentos.py:40`, `jobs.py:213` e `estado.py:542` usam `carregar_calendario` e herdam a regra.
  Fora do calendário e da agenda, nenhum `isoweekday()==7`/`weekday()==6` sobrou em `src/`.
- **D-14, D-29, Fireworks/DeepSeek, CPF ao modelo:** não tocados por esta etapa. **PII:** nenhuma nas adições; fixtures sem CPF novo.
- **Commits:** os 5 têm `Co-Authored-By` e `Claude-Session`. Nada em S2/S4/VPS/n8n/Coolify; sem tag, merge nem push forçado.

## Mutação (teste reprova sem a mudança)

Cópia descartável (`git archive HEAD`) no scratchpad; o worktree revisado não foi tocado (`git status` limpo).

| Mutação | Resultado | Teste que matou |
|---|---|---|
| M1 `bloqueado()` volta a fechar todo domingo | morto | `test_calendario_domingo_feriado_e_dataprev[domingo_aberto]`, `test_domingo_so_abre_com_as_duas_chaves[as_duas_abertas]` |
| M2 `domingo_aberto` só por `domingos=false` (sem o dia 7) | morto | `…[so_o_bloqueio_aberto]`, `test_config_da_agenda_so_abre_o_domingo_com_as_duas_chaves` |
| M3 `_horario` sem a defesa D5 | **sobrevive (equivalente, R-03)** | — |
| M4 `carregar_calendario` sempre `domingos=True` | morto | 2 de `test_calendario.py` |
| M5 validador aceita `0`/`1` como booleano | morto | `test_calendario_bloqueio_exige_domingos_booleano_…` |
| M6 `_razoes` sempre põe «domingo» | morto | 2 de `test_agenda_extrator.py` |
| M7 `_dia_util` sempre pula domingo | morto | `test_proximo_dia_util_do_teto_inclui_o_domingo_aberto` |
| M9 corpus ignora `domingo_aberto` | morto | `test_calendario_do_corpus_abre_o_domingo_so_por_parametro` |
| M10 corpus aberto por padrão | morto | idem |
| D1 0005 volta a recusar o dia 7 (banco) | morto | `test_0005_copia…`, `test_0005_aceita_dia_7_e_mantem_08_20`, `test_chave.py::test_domingo_so_abre_a_entrada…`, `test_api_config_agenda.py::…[domingo_aberto]` |
| D2 0005 perde o limite 08–20 (banco) | morto | `test_0005_copia…`, `test_0005_aceita_dia_7_e_mantem_08_20` |
| D3 `CHAVES_DA_AGENDA` sem `janela_mensagem` | morto | 12 de `test_api_config_agenda.py` (KeyError) |
| D4 `bloqueado()` ignora `domingos`, no banco | morto | `test_chave.py::test_domingo_so_abre_a_entrada_com_as_duas_chaves_publicadas` |

Codex, por conta própria: restaurou as regras da `origin/main` em memória e os testes novos falharam (calendário 2, extrator 2, corpus 1). Não achou
teste tautológico. Não rodou PostgreSQL (sandbox só leitura).

## Antes do merge (dono)

1. Decidir R-01: corrigir agora (preferível, ~1 h e um teste) ou registrar na B5.7d e limitar o kit a publicar o domingo 08–20.
2. R-05 (a): linha do roteiro no `DECISOES`.
3. A 0005 na S4 continua **só por A4.6, com «sim» nomeado** (tem `DROP CONSTRAINT`).
