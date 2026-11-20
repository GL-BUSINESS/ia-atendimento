# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versionamento semântico. Tags só depois da revisão.

## [Unreleased]

- **B1.6b, processador, repasse por etapas, `Canal`, batimento fail-closed, desligamento, `reaper_ledger` e publicador do espelho** (roteiro v3.3 B1.6,
  divisão RG-045; contrato 08 §6, §7.1–§7.4, §9; branch `feat/b1-6b`, empilhada na `feat/b1-6a`; `docs/DECISOES-B1.6b-2011.md`). Sem migração nova.
  Tudo atrás de portas com implementação falsa: o adaptador real de delegação depende de DEC-PIA-002 e a hospedagem vai para a S5.
  - `batimento.py` (v2, 90 s fail-closed, D-15), `canal.py` (batimento antes do efeito real + ledger), `repasse.py` (nota → chatbot → rota → marca → lease,
    D-14 com `repasse_travado` e alerta `humano`, R-c2 do lado do orquestrador), `processador.py` (iniciar, processar, gasto, disjuntor de 24 turnos,
    duas falhas, desligamento), `reaper_ledger.py` (G-0116), `publicar_espelho.py` (G-0216), `alertas.py`, `montagem_b16b.py`; fila: `repasse`,
    `reaper_ledger`, `publicar_espelho`.
  - `expirar_parados` com posse real passa pelo repasse (G-0093); texto > 4000 trunca em vez de 422 (RG-104); o gateway reconfere as pré-condições
    depois da vaga do limitador e da leitura do CPF (TOCTOU, revisão automática de 20/11).
- **B5.1, gateway de ferramentas** (branch `feat/b5-1`; `docs/DECISOES-B5.1-0411.md`). Pacote `ferramentas/` (o `ferramentas.py` da B1.4 vira `ferramentas/projecao.py`):
  registro versionado (`Especificacao`, esquemas `extra=forbid` em todos os níveis, classes de efeito, pré-condições nomeadas), `catalogo_hash` amarrado ao `numero` de
  `catalogo_versoes.json` (o portão falha se o hash mudar sem versão), o modelo só passa referências opacas, saída reconstruída pelo esquema e projetada pela allowlist (D-29),
  `modo_efetivo` relido na hora do efeito (cache ≤ 5 s; a FACTA de produção só em `real`), orçamento por turno e por atendimento, limitador por serviço, CPF só em memória
  (`CpfEmMemoria`) e as `Tool` do agente geradas do registro. Sem migração; ledger, batimento e executores ficam para B1.6 e B5.2–B5.4.
- **B1.8, domingo por config (D-18; branch `feat/b1-8`; `docs/DECISOES-B1.8-0411.md`).** Fechado por padrão: nada abre sem publicar as duas chaves.
  - Migração **`0005_domingo_por_config`** (só DDL; tem `DROP CONSTRAINT`, «sim» nomeado do dono na A4.6): o `config_versao_valor_check` volta como cópia do CASE da 0001 com um termo a menos
    (o `$.dias."7"` de `janela_mensagem`); 08:00–20:00 segue para os 7 dias; seeds intactos. A 0001 não muda.
  - `calendario.py`: `DIAS_ISO` 1..7; `bloqueado()` lê `calendario_bloqueio.domingos` (booleano obrigatório); o domingo só tem horário com `domingos=false` **e** o dia 7 em `janela_mensagem`
    (`Calendario.domingo_aberto`). Feriados mínimos e DATAPREV não mudam.
  - `agenda_extrator.py`: `ConfigAgenda.domingo_aberto` (padrão `False`) em `_dia_util` e `_razoes`; `agendamento.config_da_agenda` o tira do mesmo `Calendario`; `POST /agendamentos` lê `janela_mensagem`.
  - `corpus/calendario.py`: `dentro_do_horario`/`dentro_da_agenda` com `domingo_aberto` (padrão `False`); as regras da F3 seguem no padrão até a B8.1c.
  - Testes: `tests/test_migracao_0005.py`, `test_calendario.py` parametrizado, `test_domingo_so_abre_com_as_duas_chaves`, `test_defaults_seguem_sem_domingo`, integração em `test_chave.py` e `test_api_config_agenda.py`.
  - Revisão de 04/11 (`docs/REVISAO-B1.8-0411.md`), R-01 (MÉDIO): a agenda também confere o horário de ENVIO do dia (`ConfigAgenda.janela_mensagem`, do mesmo `Calendario`):
    fora dele ⇒ `antes_da_janela`/`depois_da_janela`, dia sem horário ⇒ razão nova `dia_sem_janela`; o teto pula dia sem envio. R-04 na `OPERACAO.md` §3; R-02 fica para a B5.7c/B6.7.
- **B1.6a, ledger `t11` com cerca de `versao`, `executar_efeito`, gasto Σ, `ia_ativa` relida, lease de espera e `expirar_parados`** (roteiro v3.3 B1.6,
  divisão RG-045; contrato 08 §6, §9, §14; branch `feat/b1-6a`; `docs/DECISOES-B1.6a-0411.md`). Sem migração nova.
  - `ledger.py`: reserva commitada antes da chamada (`ON CONFLICT DO NOTHING`) na transação da cerca de `versao`; só quem ganha `reservada|transitorio → enviada`
    chama; timeout/exceção/corte em efeito irreversível ⇒ `indeterminado` (nunca reenvia); `modo_efetivo` relido a cada efeito e gravado; posse real e
    devolução real sob parada dura; T7 sem confirmação aceita ⇒ `ConfirmacaoAusente`.
  - `gasto.py`: Σ `passo.custo_brl` em BRT (fecha R1-14; sai o `xfail` de `tests/test_gasto_pendente.py`), `custo_ausente`, 80/100/125 %, cache de 30 s;
    soma que falha ⇒ `503 nao_pronto` na entrada.
  - `ia_ativa` relida sem cache em `encerrar_por_chave`, `iniciar` (aborta o reservado antes do `assumir`) e `retomar` do reservado agendado.
  - `espera.py` (`aguardar_cliente_com_espera`, faixa na versão de `iniciado_em`), `chave.config_em`, `expiracao.py` (`expirar_parados` injetado no worker),
    `espelho.py` (`encerrou` no outbox na transação da mudança de estado).
  - Retomada de 20/11 (rebase sobre B1.8 + B5.1; `DECISOES-B1.6a-0411.md` D24–D26): órfã `enviada` de ação interna volta a `transitorio` e repete
    (G-0131); `transitorio` de irreversível real sem `Desfecho.nada_saiu` vira `indeterminado` (G-0087, ledger); irreversível exige `args_hash` (G-0454);
    runbook na `OPERACAO.md` §12 (F4-027).
  - Correção da revisão de 04/11 (`docs/REVISAO-B1.6a-0411.md`, A1 a A10): devolução sem posse real simulada também com o global `real`; T7 só com
    confirmação `digitacao` do mesmo banco, no prazo, não vencida e não gasta; chave presa ao pedido (`ChaveDivergente`); `transitorio` real não se
    rebaixa sob parada dura; cerca reconferida na reivindicação; simulação que falha fica `transitorio`; limite zero sem gasto é crítico;
    `expirar_parados` em páginas com `chave.config_no_tempo`.

- **Achados R-02 a R-07 da revisão da integração de D-06:** `gitleaks.sh` com `-v` (achado diz arquivo e regra; valor segue oculto); teste de achado em um só modo (`dir`/`git`);
  teste de 6 casas em `Preco`; nenhum `__pycache__` versionado; amostra de CPF de `tests/test_varredura.py` trocada para a faixa `000.000.2nn`, sem reescrever o histórico; `.gitleaksignore` deixa de chamá-la de sintética;
  exceção `111.444…` removida do `.gitleaks.toml`; `OPERACAO.md` sem duas seções 8 (Release vira §11; §8 a §10 mantêm o número); README e D15 corrigidos.
- **B1.4, contexto do turno, agente `Turno` e observabilidade** (sp01 T6; branch `feat/b1-4-agente-turno`; `docs/DECISOES-B1.4-0211.md`). Sem rede, sem
  chave de provedor: o provedor real fica atrás de `Provedor` e nos testes roda só o `ProvedorFalso` (responde pelo roteiro da F3).
  - `turno.py`: `Turno` (H §2.2 + `sinal`, `extra=forbid`, 20 intenções, texto ≤ 320 sem dígito, «R$», e-mail, link nem placeholder fora do conjunto
    fechado, `motivo` padrão «(não informado)»), `ACOES_POR_FASE` (batem com o gabarito da F3), `validar_turno_na_fase` (ação, ferramenta, TX e
    campo fora da fase ⇒ `AcaoForaDaFase` e irmãs, `acao_invalida=true`), `custo_brl` (contrato 08 §9, 6 casas) e `ResultadoTurno.como_decisao()`.
  - `agente.py`: `ResolvedorModelo` (UM `OpenAIChatModel` em `us.api.fireworks.ai/inference/v1`, roteador `…-1017-us`, **sem `FallbackModel`**),
    `criar_agente` (`output_retries=1`), `executar_turno` (custo, latência, `trace_id`; falha do provedor, tempo ou saída inválida ⇒ `ErroDoModelo` com
    mensagem fixa e o gasto em `.uso`), raciocínio desligado por `extra_body` (forma em `Settings`, HIPÓTESE até a A2.9), `ProvedorFalso`.
  - `contexto.py` + `modulos_fase.py` + `tokens.py`: os 8 blocos de H §3.1 montados do estado, `perfil` (allowlist com `ultimo_sentido`, `tipo_ultima_fala`,
    `etapa_inapp`), conversa cifrada, resumo e exemplos da F3 (fora do hold-out); estimador de tokens plugável (HIPÓTESE, medir em B8.2); corte
    resumo → trocas antigas → exemplos até ≤ 4.000; CPF, telefone, e-mail, nome, valores e ids reais nunca vão ao modelo (máscara de novo, `[VALOR]`/`[PRAZO]`,
    apelidos `oferta-1`, auditoria do prompt inteiro). Oferta só a partir da E3 (Q1).
  - `observabilidade.py`: OTel → Phoenix (desligado por padrão), exportador que mascara todo span, filtro de logs, segredos como `[SEGREDO]`, alerta de raciocínio.
  - `config.py`: `modelo_roteador` (só `-us`), `modelo_raciocinio_off`, `modelo_temperatura`, `modelo_max_tokens`, `modelo_timeout_s`,
    `preco_in_usd`/`preco_cache_usd`/`preco_out_usd`/`cambio` (≤ 0 derruba o boot), `phoenix_projeto`, `phoenix_api_key`.
  - Revisão automática de segurança (2 MEDIUM em `contexto.py`, corrigidos): o `perfil` ao modelo passou a allowlist **por chave** (inteiro só em `idade_do_lead_min`/`etapas_do_robo_concluidas`, cada
    um com seu limite; `banco` `^[A-Z0-9_]{1,32}$`; `origem`, `ultimo_sentido`, `tipo_ultima_fala` e `etapa_inapp` em enums fechados) e a folha de resultado de ferramenta voltou a só minúsculas; ambas rejeitam
    os nomes da conversa, e `auditar_prompt` também.
  - Testes: `tests/test_agente.py`, `tests/test_contexto.py`, `tests/test_observabilidade.py` (cobertura do código novo ≈ 98%).
  - Revisão 2 (`docs/REVISAO-B1.4-0311-r2.md`; 1 alto, 7 médios, 4 baixos; correções em `docs/DECISOES-B1.4-0211.md` §6): `proteger_texto` linear (lookbehind em caracteres de host) e com corte da entrada em 1.000 caracteres (R2-01);
    qualquer exceção de ferramenta é `FerramentaFalhou` (`ErroDoModelo`, texto fixo) (R2-02); a ferramenta registrada só aparece no corpo HTTP, só executa e só conta tokens na fase que a libera (R2-03); `status`/`etapa` e todas as
    folhas de texto do resultado por domínio fechado (R2-04); host com sinal de caminho é link com qualquer TLD (R2-05); `[NUMERO:n]`, hora com `hrs`/`hs`/`min`, `dd/mm hh:mm` isento da máscara de 8 dígitos e o extrator de agenda
    sobre o texto de `mascarar` (R2-07, R2-08). Testes novos: `test_protecao.py`; `test_ferramentas.py` e `test_contexto.py` ampliados.
  - Revisão 1 (`docs/REVISAO-B1.4-0311.md`; 0 crítico, 1 alto, 12 médios, 11 baixos; correções em `docs/DECISOES-B1.4-0211.md` §5): retorno de ferramenta só volta ao modelo projetado e
    auditado (`ferramentas.py`, A-1); `protecao.py` (número «nu» → `[NUMERO]`, data → `[DATA]`, link → `[LINK]`, `r$` solto → `[VALOR]`); mensagem da E5 oculta por padrão; nome colado a `_`/dígito mascarado
    (`mascara.py`); `banco` só do catálogo e folhas por domínio fechado; placeholder fora da fase ⇒ `TextoForaDaFase`; `executar_turno` só aceita o `Contexto` montado; tempo-limite de 8 s (teto 10) e
    `max_retries=0`; fábrica de `LogRecord` que nunca levanta; `ContextoNaoCabe`/`ContextoComDadoPessoal` são `ErroDoModelo`; estimador com não latino a 2 tokens/caractere; scrubber cobre chave,
    nome de evento, link e JSON; link digitado até o próximo espaço e em largura inteira (`normalizar`, `ha_link` na auditoria); texto livre sem promessa; `ArgsDaFerramenta`. `MODELO_TENTATIVAS_HTTP` saiu. Testes novos: `test_ferramentas.py`, `test_timeout.py`, `test_vazamento_corpo.py`.
- **B2.4, `pessoas_teste` (FACTA, T1/T3) e fixtures de 3RN/C6 para o modo `duble`** (`feat/b2-4-pessoas-teste`, empilhada sobre `feat/b1-5-api-entrada`; `docs/DECISOES-B2.4-0211.md`):
  - **`src/ia_atendimento/pessoas_teste/`** (o módulo `pessoas_teste.py` da B1.5 virou pacote; `arquivo.py` é o mesmo código e a API pública `PessoasTesteFixas`/`carregar` não mudou):
    `catalogo.py` + `pessoas.json` (84 pessoas sintéticas, uma por `persona_id` da F3, CPF `000.000.0nn-dd` do corpus, `pessoa_id` fixo `00000000-0000-7000-8000-…`, oferta FACTA ativa do perfil da persona,
    P13 com oferta ativa no C6, P14 com o par 3RN sem oferta, P-M18 com C6 e sem FACTA) e `pessoas.sha256` (hash canônico, o mesmo do instantâneo do `bancos-duble`);
    `fonte.py` (`FontePessoasTeste`: T1 `ResumosPessoas` e T3 `ResultadoPropostasPessoa` por `pessoa_id`, `valid_until` = agora + 2 h calculado a cada leitura, só em `duble|teste`, `ForaDoModoDeTeste` em `real|sombra`);
    `formas.py` (formas medidas do 360, de `/3rn/calcular` e de `/c6/oferta/simular`, Pydantic estrito); `prefixo.py` («[TESTE]», só no `modo_efetivo = teste`); `fixtures_duble.py` (carregador das fixtures de banco);
    `python -m ia_atendimento.pessoas_teste arquivo|listar` (monta o `PESSOAS_TESTE_ARQUIVO`).
  - **`fixtures/duble/{cliente360_oferta,3rn_calcular,c6_simular}.json`** (sem WireMock, sem chamada real; viajam no wheel por `force-include`): P13 (oferta ativa no C6, T5 simulado coerente com ela) e P14 (sem oferta no 3RN, `SIM_AUSENTE`).
    `scripts/gerar_pessoas_teste.py [--verificar]` gera tudo do corpus e entra no `check.sh`.
  - **Kit** `~/retomada-2809/fila-2910/ia/config/chats-teste.sh` (`gerar|aplicar|limpar`, `--ensaio`/`--confirmo`; `PUT /config/chats_teste` só com o token da TI e `versao_esperada`; nada rodou em produção). `docs/OPERACAO.md` §10.
  - **Testes** (`tests/test_pessoas_teste.py`, `tests/test_pessoas_teste_api.py`, `tests/test_fixtures_duble.py`): `test_chats_teste_so_com_pessoa_de_teste`, `test_mensagem_de_teste_prefixada_TESTE`,
    `test_pessoas_teste_cobrem_todas_as_personas`, `test_valid_until_relativo`; `pytest -k fixtures_duble` (41, com 30 mutações de forma) e `-k pessoas_teste`. 2.252 → 2.317 passed na primeira entrega (contagem final na revisão 1, abaixo).
  - **Não muda a API**: a ligação `chats_teste` ↔ `pessoas_teste` e a restrição à TI já eram da B1.5; esta etapa acrescenta o catálogo real, os testes que a fecham e o kit.
  - **Revisão 1 da B2.4 (`docs/REVISAO-B2.4-0311.md`: 0 crítico, 2 ALTO, 12 MÉDIO, 10 BAIXO)**, um commit `fix:` por item:
    - **R1-01/R1-07 (ALTO):** o `/3rn/calcular` no modo `nao_repagar` ecoa `"nao_repagar": true` (e `regra_id`/`taxa_pedida`/`taxa`) em toda resposta; a fixture e os modelos não tinham o eco e o `SIM_AUSENTE` do P14 era uma resposta que o servidor nunca produz.
      Agora o eco é exigido em todo caso do arquivo, o padrão é `SIM_AUSENTE`, o `REPROVADO` de vínculos (impossível no modo) deu lugar ao de prazo fora da tabela, e a fixture só responde pelo CPF da própria persona.
    - **R1-02 (ALTO):** o `check.sh` abre com `scripts/exigir_irmao.sh` e FALHA sem `BANCOS_DUBLE_PATH` (antes o teste cruzado era skip e o portão dizia OK); `PESSOAS_TESTE_EXIGE_IRMAO=1` transforma o skip em falha.
    - **R1-03/04/15/16:** T1/T3 na forma real do 360 (`atribuicao.versao` 0, par ausente em vez de `sem_oferta` vazio, `ContratoNaFoto` e `com_contrato` para o P59, chaves nulas da `Oferta`, «não encontrado» com `pessoa_id`/`atribuicao` nulos, T1 sem `status_atendimento`).
    - **R1-06:** `PUT /config/chats_teste` também barra chat com atendimento `duble` de pessoa fora de `pessoas_teste` (o seed de `modo` é `duble`).
    - **R1-09:** um CPF por persona (84 distintos; 39 clones de persona no dublê, `000.000.1nn`) e prazo da oferta = prazo do `aprovado-N`; o validador do corpus ganhou as regras (CPF repetido entre quaisquer personas; prazo ≠ cenário); o clone vale pela base nos eventos do gabarito e no hold-out.
    - **R1-08:** `kits/chats-teste.sh` (cópia em `~/retomada-2809`): `aplicar` faz merge e guarda a lista anterior, `limpar` restaura, `--motivo` obrigatório, só WireGuard/loopback; 13 testes contra uma API falsa em processo.
    - **R1-05/R1-12:** `OPERACAO.md` §10 diz «três travas por código + uma pendente» (o `Canal` ainda não chama «[TESTE]»); o texto proposto para a emenda do contrato 08 §6/§5.6 e a regra «a fonte de T1/T3 é decidida pelo `modo_efetivo`» estão em `DECISOES-B2.4-0211.md` (o contrato não foi editado).
    - **R1-13/18/19/24:** `exemplo_cliente360` (o golden não é fonte servível), telefone só em `5500 9000-00nn`, CPF de exemplo montado nos testes, `business_date` = dia da criação. **Deixados** (R1-14 parcial, R1-17, R1-20, R1-21, R1-23): ver as DECISOES.
    - Contagem final (`bash scripts/check.sh` com `BANCOS_DUBLE_PATH`): **2.252 → 2.369 passed** (1 skip de PyYAML e 3 xfail estritos como antes).
  - **Revisão 2 da B2.4 (`docs/REVISAO-B2.4-0311-r2.md`: pronto para PR, 3 MÉDIO e 10 BAIXO)**, um commit `fix:` por item:
    - **R2-01:** os `pares` do T3 saem ordenados por `(banco, produto)` como o 360 real (P13 = `[C6, FACTA]`); o modelo recusa fora de ordem. **R2-03:** o `gerar` do kit preserva os pares do arquivo anterior (`--juntar`; `--recomecar` ignora), com teste `gerar → aplicar → gerar → aplicar (merge) → limpar` sem 422.
      **R2-12:** o `limpar` só restaura se a lista vigente é a que o `aplicar` gravou e só a lista guardada desta URL (`--forcar`); a cópia de `~/retomada-2809` é gerada por `scripts/instalar_kit_chats_teste.sh` e conferida por teste.
    - **R2-04/R2-05:** sem `ultima_consulta_em` (só `propostas:periodo` o emite), com `link_chat: null`, `Contrato` do P59 com as 31 chaves. **R1-23:** a fixture do 3RN só tem `SIM_AUSENTE`. **R1-14/R2-06:** a deriva lê `tests/contratos/cliente360-recorte.json` (43 schemas da `cliente360-api@a265fa5`,
      `scripts/atualizar_contrato_360.py`), compara campos, `required`, enums e os opt-ins conhecidos, e um teste de frescor reprova se a API mudou. **R2-08:** a `fonte` do `duble_personas.json` leva o sha256 do `personas.yaml`. **R2-13:** `eventos_possiveis` exige o corpus.
    - **R2-11:** ~~o CI faz checkout do `bancos-duble` (secret `IRMAO_TOKEN`) e exige a consistência.~~ Superado (RG-128, RG-119): o passo do irmão saiu do CI, sem `IRMAO_TOKEN` o job caía antes do `pytest`; a consistência segue no `check.sh` local e o CI cruzado volta com o PAT (B12.2). **R2-02:** `FontePessoasTeste`/`FixturesDuble` aceitam `posse_real=` e se recusam; a emenda do contrato 08 (cinco pontos, as duas tabelas «Ler», a regra por `modo_efetivo` exceto posse real sob parada dura) está em `DECISOES-B2.4-0211.md`.
    - Contagem final (`bash scripts/check.sh` com `BANCOS_DUBLE_PATH`): **2.252 → 2.388 passed** (1 skip de PyYAML e 3 xfail estritos como antes).
- **B5.7b, agendamento: estado `pausado` e jobs `retomar`/`reaper_agenda`** (`feat/b5-7b-pausado`, empilhada sobre `feat/b1-5-api-entrada`; `docs/DECISOES-B5.7b-0211.md`; a versão do `pyproject` não muda):
  - **`estado_pausa.py` (saiu de `estado.py`, R1-07):** `pausar` (`aberto|aguardando_cliente → pausado`, **só de E2–E6 e E8, nunca E7**: `retoma_fase` é a fase atual e o UPDATE só casa com ela; `lease_ate = retoma_em + folga_min`,
    padrão 30; a chave `pausa` entra no `estado_conversa` no mesmo UPDATE) e `sair_da_pausa` (→ `aberto` com lease de turno, ou `aguardando_cliente`; tira `pausa` e `retoma_em`).
    `repassar` e `encerrar` também tiram a `pausa`: a chave existe se e somente se o estado é `pausado`. `abrir_agendado` (caso b: `reservado` de vida longa, `gatilho='agendamento'`, não toca o chat;
    o INSERT saiu de `agendamento.reservar`) e `iniciar_agendado` (na hora, já em `retoma_fase`, só para `gatilho='agendamento'`). `aplicar` ganha `pausa=` e `onde_igual=`. Os dois `xfail` estritos da B1.1
    (`pausar`, `abrir_agendado`) viraram testes verdes.
  - **`agenda_estado.py` (novo):** `pendente → confirmado → disparado | cancelado` por CAS em `versao` (`confirmar`, `disparar`, `cancelar`, `registrar_desfecho`, `ler_agendamento`) e o passo `agendamento` da linha do tempo.
  - **`agenda_jobs.py` + `fila.py` (novos jobs):** `alarme_retomar` (agendado em `dispara_em`, **sem lock**, `queueing_lock=retomar:{agendamento_id}`) enfileira o `retomar` de verdade (`lock=chat:`,
    `queueing_lock=retomar_exec:{agendamento_id}`), que reivindica o agendamento (CAS `confirmado → disparado`, uma transação) e entrega a volta a `Servicos.retomar_atendimento` (B5.7c; falha alto antes do
    CAS se não injetado). `reaper_agenda` por minuto reenfileira o `confirmado` vencido sem job vivo (`todo` ou `doing`; quem dá o `doing` por morto é só a `jobs_presos`). **Não usa `send_date` do ChatGuru.**
  - **`POST /agendamentos`:** grava o passo `agendamento` (`proposto`) e enfileira o alarme **na mesma transação** (`Enfileirador.agendar_retomada`); `retoma_fase` ≠ E8 com `agenda_b_digita=false` ⇒ 422 `validacao`.
  - **Provas:** `tests/test_agenda_jobs.py` (EM4: restart com 3 `confirmado`, um deles com o worker morto no meio do `retomar`, outro com o alarme sumido, na fila real, sem perda nem duplicidade;
    `test_um_agendamento_ativo_por_atendimento`, `test_post_triplicado_e_noop`, `test_reaper_pula_pausado`, `test_desligada_noturna_nao_encerra_pausado`, `test_pausar_nunca_em_E7`),
    `tests/test_estado_pausa.py`, `tests/test_agenda_estado.py`. Testes: 2.252 → 2.408 passed (+156, incluindo as revisões 1 e 2; dos 3 `xfail` estritos sobra o do gasto, B1.6).
  - **Revisão 1 (`docs/REVISAO-B5.7b-0311.md`; 0 crítico, 1 ALTO, 5 MÉDIO, 9 BAIXO) e revisão automática; um commit `fix:` por item, cada um com teste que reprova sem a correção (`docs/DECISOES-B5.7b-0211.md` D14–D20):**
    - **R1-01 (ALTO) e os 2 MÉDIO da revisão automática, jobs presos:** worker com `SIGKILL` deixava o job `doing` com o `lock=chat:` para sempre (o lead ficava `pausado` sem o `reaper_lease` enxergar o chat). `worker_vivo.py`: periódica `jobs_presos`
      (um só `UPDATE … WHERE status='doing' AND <worker morto>`, atômico; batimento velho **ou** `worker_id` NULL com o job rodando há mais de 60 s, nunca «NULL = morto na hora»), `stalled_worker_timeout = 60 s` em `rodar_worker`, e `vigiar_batimento`
      (o worker que perde a própria linha, o batimento ou o banco por 40 s para e aborta os jobs em voo; `WorkerPerdeuOBatimento`). Prova com `SIGKILL` real (`tests/worker_matavel.py`). Toda escrita de estado é CAS e o `retomar` é CAS: execução superada não grava
      nem duplica (`test_execucao_superada.py`). **Gate da B1.6: ledger de envio idempotente do `turno`/`lembrete` (hoje espiões).**
    - **R1-02:** `disparado → confirmado` por `agenda_estado.rearmar` (mesmo agendamento, `seq` intacto, atendimento movido junto, no máximo 2 rearmes); a volta devolve `jobs.Adiar`. **R1-03:** passou do lease (`dispara_em + folga`) o `retomar` não entrega: `expirado`, o lead é do `reaper_lease`.
      **R1-04:** o rearme do `cedo` é relativo (`max(dispara_em, agora + 5 s)`): 277 jobs em 3 s com relógio 2 s atrasado viram 1. **R1-05:** `pausar` impõe `agenda_max_pausados` (sob trava) e `agenda_teto_horas`. **R1-06:** a prova da noite usa o reaper de lease com handler que muda estado;
      `jobs.ESTADOS_EXPIRAVEIS` para o `expirar_parados` da B1.6. BAIXOS: R1-07 (`estado_pausa.py`), R1-08 (ordem de locks), R1-10 (`pausa` = 91 bytes), R1-11 (mutantes viraram testes), R1-12 (`Desfecho | Adiar | None`), R1-14.
  - **Revisão 2 (`docs/REVISAO-B5.7b-0311-r2.md`; pronto para PR, 0 crítico/alto, 3 MÉDIO e 9 BAIXO novos); um commit `fix:` por item (`docs/DECISOES-B5.7b-0211.md` D21–D26):**
    - **R2-01:** `Volta.atendimento_versao` (a versão lida sob o lock do claim) é a cerca da primeira escrita da volta. **R2-02:** ponto de entrada real do worker, `python -m ia_atendimento.worker` (script `ia-worker`; `--saude` = healthcheck de batimento;
      saída 3 se a vigia o parou); bloco exato do compose em `docs/OPERACAO.md` §9; teste de boot real com processo à parte. **R2-03:** `fechar_volta_perdida` fecha a linha (`repassou` / `cancelado` por sistema / `expirado`) e a NT-06 só diz «não retomou»
      quando a IA nunca falou (NT-05/NT-01 se a volta foi reivindicada). **R2-04:** `reagendado_sistema` puro não existe; só `Adiar` reagenda (`RetornoInvalidoDaVolta`). **R2-06/07:** `shutdown_graceful_timeout` de 30 s; `pytest-timeout` 2.4.0 pinado
      (120 s por teste); `test_agenda_jobs.py` dividido. R2-08 e R2-11 (mutantes vivos do rearme, comentário das margens). Abertos: R2-09, R2-10, R2-12 e as emendas do roteiro/contrato 08 §5.5 (dono).
  - **GATES antes de ligar `ia_ativa` ou `agenda_ativa` (nada disto está pronto neste PR):**
    1. **B1.6, ledger de envio com cerca de `versao`** (receita da r2, 6 passos): (1) reservar antes de enviar em `ia.ferramenta_chamada` (`idem_key` único, `ON CONFLICT DO NOTHING`; conflito ⇒ devolve o gravado e não envia; chave `t11:{atd}:{rodada}:{seq}`, `rodada` do CAS do `consumir`, nunca hora nem `job_id`);
       (2) a reserva e o CAS de `versao` (lida DEPOIS do modelo/da volta) na mesma transação, `ConflitoVersao` ⇒ passo `erro` e não envia (o ledger sozinho não basta: rodada N e N+1 têm chaves diferentes); (3) `enviada`/`falhou`/`indeterminado`, e timeout, 424, corte e `CancelledError`
       no meio do envio ⇒ `indeterminado` (envio e gravação em `asyncio.shield`), que nunca reenvia (`sem_retry_ambiguo`) e confere a conversa por RPA; (4) o `lembrete` (`RETRY_FILA` reexecuta depois de um envio que pode ter saído) usa a mesma chave no ledger; (5) a volta (B5.7c) escreve
       primeiro com `Volta.atendimento_versao` (`sair_da_pausa`/`iniciar_agendado`) e só depois envia; (6) testes de aceite com mutação: dois `turno` do mesmo atendimento ⇒ o `Canal` real é chamado 1 vez; `retomar` + `jobs_presos` + `turno` do cliente ⇒ no máximo uma mensagem; `CancelledError` no envio ⇒ `indeterminado`, sem reenvio.
    2. **Esteira:** trocar o `command` e o healthcheck do worker pelo bloco de `docs/OPERACAO.md` §9 (hoje o compose chama `procrastinate --app=ia_atendimento.fila.app worker`, que não existe).
    3. **B1.6, handler de lease:** `fechar_volta_perdida` na transação do repasse e a nota certa; `expirar_parados` por `jobs.ESTADOS_EXPIRAVEIS`. **B5.7c:** `Adiar` como único reagendamento do sistema, `pausar` com os valores vigentes da config, regra «nenhum I/O síncrono no laço do worker».
  - **Pendências declaradas:** B5.7c (confirmar/reagendar pelo cliente, pré-checagens e mensagem da volta; R1-13, R1-15, R2-09); o worker precisa de supervisor que o reinicie (`restart: unless-stopped`; sai com código 3 se a vigia o parar).

- **B1.5, API de entrada (T7) + migração 0004** (`feat/b1-5-api-entrada`; `docs/DECISOES-B1.5-3010.md`; a versão do `pyproject` não muda, entra na v0.3.0):
  - **Migração `0004_anexo_rpa_e_espelho`** (D5 e D6 do contrato 08 §11, aditiva): `ia.fn_anexar_rpa(bigint, text)` `SECURITY DEFINER` (dono `ia_owner`, `search_path = pg_catalog, ia`,
    `EXECUTE` só a `ia_app`; o único jeito de anexar o `_id` do RPA ao passo, que é append-only) e a outbox `ia.espelho_evento` (`SELECT, INSERT` e `UPDATE` de 4 colunas a `ia_app`, nada a `ia_leitura`).
    `tests/test_migracao_0004.py` prova `ia_app` executando a função e **sem** `UPDATE` direto em `passo`, `ia_leitura` sem a outbox, reaplicar recusado pelo ledger, checksum e o passo a passo da S4.
  - **`src/ia_atendimento/api/`** (FastAPI 0.162.0, já pinado): as 13 rotas do contrato 08, autenticação por `X-IA-Token` (origem = a do token) e, em `/eventos/chatguru`, por **assinatura HMAC do gateway**
    (`x-gl-*`, janela de ± 300 s, duas chaves na rotação); 403 por origem; envelope de erro sem eco do valor (também no 422 do Pydantic); log sem corpo; sem `/docs`.
    `POST /atendimentos` (sem CPF; `chat_number` cifrado no cofre; replay 200/409 pelo `entrada_fingerprint` do §4; recusas de config na ordem do catálogo, com `janela_24h`; `modo` por atendimento,
    `persona_id` só em chat de teste; faixa pela comissão), `POST /agendamentos` (chave recalculada, extrator B5.7a, `agenda_max_dia` sob a trava), eventos (uma função para webhook e RPA,
    `descartado`/`conflito` como 200, **casamento webhook × RPA** por `fn_anexar_rpa`), `GET|PUT /config` (corrida = 409, `ia_ativa=false` agenda `encerrar_por_chave`), anotações, candidatos, `por-chave`, `/healthz`, `/readyz`, `/saude`.
  - **Novos módulos:** `mensagens.py`, `agendamento.py`, `esforco.py`, `pessoas_teste.py`, `enfileirador.py` (defer síncrono do Procrastinate **na transação da API**), `segredos.py` (arquivos 0600), tarefa `encerrar_por_chave` (fila e `jobs`).
  - **`Settings`:** `api_tokens` por origem substitui `api_token`; `chat_ref_chave`, `responsavel_ia`, `casamento_janela_*`, `preco_*`/`cambio`, `pessoas_teste_arquivo`, e os arquivos de segredo (`GATEWAY_HMAC_ARQUIVO`, `SEGREDOS_SAIDA_ARQUIVO`); `.env.example` e README atualizados.
  - **Ajustes em módulos existentes:** `estado.procurar_replay` e `fingerprint_de_identidade`; `chave.bloqueio_entrada(abertura_possivel=)` e `optou_por_sair`/`abertos_agora` públicos; `linha_tempo.gravar_mensagem_recebida(fora_de_ordem=)`
    e o reenvio do `_id` do RPA já anexado vira `repetido` (não `conflito`).
  - **Dependências:** `psycopg-pool==3.3.3` declarado (já estava no `uv.lock` por causa do Procrastinate; a API o usa direto para o pool). `fastapi`, `uvicorn` e `httpx` (dev) já estavam pinados.
  - **Revisão de segurança automática (2 achados MEDIUM, corrigidos):** `agenda_max_dia` conferido de novo dentro do `pg_advisory_xact_lock`; URL malformada em `url_arquivo` virava `NameError` (500), agora 422 sem eco.

  - **Revisão 1 (`docs/REVISAO-B1.5-3010.md`, 31 achados; 0 crítico, 2 ALTO):**
    - **R1-01/R1-02 (ALTO):** o replay e o gêmeo concorrente de `POST /atendimentos` e `POST /agendamentos` devolvem `200 repetido` (replay conferido DENTRO da trava, antes de `abertos_max`/`chat_ocupado`, e relido quando uma recusa estoura); `tests/test_corrida.py` com threads reais.
    - **R1-03:** candidatos idênticos concorrentes ⇒ `ON CONFLICT DO NOTHING` + comparação (antes 500). **R1-04:** `/eventos` relê o atendimento com `FOR UPDATE` na transação do registro (encerrado ⇒ `descartado`; `repassando` ⇒ sem turno).
      **R1-08:** `max_disparos_dia` dentro da trava. **R1-05:** `responsavel_email` vazio não marca delegação. **R1-06:** instantes de corpo só como texto RFC 3339 com fuso (epoch e texto numérico ⇒ 422 sem eco) e `datetime_post` > +5 min grava pelo recebimento com o código `relogio_futuro` (R2-02: 422 perderia a mensagem real; o contrato 08 v2.2 §5.3 precisa dizer «grava limitado»).
    - **R1-07/R1-17:** `janelas[].motivo` do calendário é código `^[a-z0-9_]{1,40}$` sem documento (e a janela só tem `de`, `ate`, `motivo`); `por`, `operador` e `disparado_por` são login/e-mail sem sequência de documento; a leitura mascara o legado (`[mascarado]` + alerta).
    - **R1-09:** as migrações vão no wheel (`force-include`) e a subida falha sem a pasta; `/readyz` sem pasta é 503 `migracoes_nao_conferidas`. **R1-12/R1-18:** a 0004 (ainda não aplicada em lugar nenhum) ganhou CHECKs na outbox (`chave`, `detalhe` só com as 4 chaves e valores curtos, `resultado` no enum, `tentativas >= 0`, `resultado` só com `enviado_em`) e `fn_anexar_rpa` recusa id nulo; o checksum é o dos bytes novos.
    - **R1-11/R1-19/R1-20/R1-25/R1-30/R1-15/R1-16:** alertas dos contadores no log; access log do uvicorn desligado; cache de config limpo depois do commit; `ChaveDesconhecida` no casamento vira alerta; `InterfaceError` ⇒ 503; JSON profundo ⇒ 422; `recusa` de candidato é código de até 40 sem documento.
    - **R1-27:** `estado.py` dividido (`estado_erros.py`, `estado_entrada.py`; 825 → 620 linhas, API pública igual), `fila._montar_tarefas` e `linha_tempo.gravar_mensagem_recebida` < 50 linhas, docstrings repetidas removidas, `tests/test_api.py` dividido em 3 arquivos.
    - **Pendências declaradas (não corrigidas aqui):** **R1-14 gasto** (`chave._gasto` ainda soma o custo do atendimento, não Σ `passo.custo_brl` do §9: bloqueio da B1.6, **não ligar `ia_ativa` antes**; `tests/test_gasto_pendente.py` é um `xfail` estrito que vira vermelho quando a troca for feita);
      **R1-10 anotação:** o limite fica em **240**; o contrato 08 §3/§5.6 diz 1–300, mas o CHECK é sobre o texto do passo `Anotação (categoria): nota` ≤ 300, então o máximo real é **`287 − len(categoria)`** (277 com «observacao», 247 com categoria de 40): **o contrato 08 precisa de emenda** para «≤ 287 − len(categoria)» (ou o limite vira dinâmico).
  - **Revisão 2 (`docs/REVISAO-B1.5-3010-r2.md`; 0 crítico/alto, 3 MÉDIO, 8 BAIXO):** R2-01 parada leve como alarme sem lock (o turno do cliente não fica preso até 19 min); R2-02 `datetime_post` adiantado grava pelo recebimento com `relogio_futuro` (**o contrato 08 §5.3 precisa dizer «grava limitado»**);
    R2-03 log da aplicação configurado na fábrica (a linha `req trace=…` e os alarmes 401/403 saem em produção); R2-04 `+dialeto` na `DATABASE_URL` derruba a subida; R2-05 anos fora de 2020–2999 ⇒ 422; R2-06 testes do `FOR UPDATE` e do boot real; R2-07 flags do uvicorn e `HEAD /healthz`;
    R2-08 pool com `lock_timeout`/`statement_timeout`/`check`; R2-09 FIFO e JSON profundo nos segredos; R2-10 normalização antes do `descartado`; R2-11 as revisões versionadas; R1-24 parágrafo de segredos sem contradição.
  - **Testes:** 1.891 → 2.252 (+3 xfail estritos) (`test_api`, `test_contrato_api`, `test_migracao_0004`, `test_enfileirador`, `test_ambiente_api`, `test_segredos`, `test_esforco`, `test_mensagens`, mais os de `config`).

- **B8.1a, corpus da F3** (`tests/corpus/`, pacote `src/ia_atendimento/corpus/`, `tests/test_corpus*.py`): 60 personas P01-P60 (40 da F3 curta,
  C5) + 24 P-M, 60 diálogos-gabarito (40 da F3 curta + as 20 P-M críticas; 739 turnos; o texto da IA não é fixado), semente determinística
  (ordem, hold-out de 20%, 3 execuções por persona, escolha da variação do cliente) e carregador/validador Pydantic estrito (`extra='forbid'`,
  42 regras, cada uma com teste de mutação). Tudo inventado: nenhuma conversa real, CPF só `000.000.0nn` alinhado ao `bancos-duble`.
  `scripts/varredura.py` passa a aceitar a faixa `000.000.0nn` (CPF de DV válido que nenhuma pessoa tem).
- **B8.1a, correções da revisão 1** (`docs/REVISAO-B8.1a-3010.md`): E5 colhe os 4 campos; janela de 24 h do WhatsApp (P45/P46 encerram em
  silêncio); T7 só com persona do dublê (8 personas ganham `aprovado-NN`, ajuste proposto ao bancos-duble); SIM validado pelo texto; recusa firme
  repassa com nota (Q5); hold-out sem esqueleto repetido; intenções, objeções e fases com turno de diálogo; I2/I5/I9 viram ações proibidas
  verificáveis; evento em vocabulário fechado; PII varrida em todo campo; `corpus.py` virou pacote (< 350 linhas por arquivo).
- **B8.1a, correções da revisão 2** (`docs/REVISAO-B8.1a-3010-r2.md`): o SIM volta a ser explícito e isolado (regra fechada; «sim?», «sim, mas…»,
  «bora» pedem TX-36) e há diálogos de E6 ambíguo, «não» e TX-12 (um no hold-out); instantâneo do dublê da main (@1305152) e CPFs sem stub na faixa
  reservada 075-098, sem pedir ajuste ao bancos-duble; gabarito amarrado ao cenário do dublê (`gabarito_cenario_duble`); hold-out com roteiro do
  cliente e falas próprias; ≥ 2 turnos por intenção e 10 de texto livre do modelo; janela de 24 h exclusiva; `FERRAMENTAS_POR_FASE` igual a H §2.3b;
  `src/` não aponta mais para `tests/`.
- **RG-128 e RG-119, portão** (`ci.yml`, `scripts/check.sh`, `scripts/gitleaks.sh`, `.gitleaks.toml`, `.gitleaksignore`): o passo do sha256 do CI rodava com o
  caminho dobrado (`working-directory: migrations` + `migrations/0001.sha256`) e nunca chegou ao `pytest`; o `check.sh` ganha gitleaks **estrito** (8.30.1): sem o binário
  o portão falha, e a varredura cobre a árvore e o histórico da branch atual.

## [0.2.0] - 2026-10-30

B1.1 estado + migração 0003 (PR #3), B1.3 fila/calendário/chave (PR #2), B1.2 linha do tempo/conversa cifrada/cofre (PR #4), B5.7a extrator de horário (PR #1). Cada bloco com duas revisões adversariais e revisão automática de segurança; detalhes por bloco abaixo.

### B1.3 · fila, trava por chat, calendário, chave e jobs (sp01 T5) · branch `feat/b1-3-fila`
- `calendario`: janela de mensagem seg–sáb 08–20 em America/Sao_Paulo **calculada no código** (nunca pelo fuso do banco); a fonte é a
  config (`janela_mensagem`, `calendario_bloqueio`) e o código só **valida** (piso: sem domingo, nunca fora de 08–20, feriados 02/11 e
  20/11/2026 e janela DATAPREV 20/11 22:00 → 23/11 06:00 não podem ser tirados; a config pode acrescentar). `dentro_da_janela`,
  `proxima_janela`, `bloqueado`, `limites_do_dia/mes` (gasto do dia e do mês em hora local) e `cron_utc` (horário local → cron UTC).
- `relogio`: `Relogio`, `RelogioReal`, `RelogioFalso`; teste guarda que os módulos da B1.3 não leem o relógio do sistema nem o `now()` do banco.
- `chave` + `chave_registro`: configuração por `max(versao)` com cache de 5 s (relógio injetado); registro Pydantic das 27 chaves com seed
  (+ `lembretes_intervalos_min=[240, 240]` e `verificador_modelo`), padrão = seed da 0001 (teste compara), **recusa `modo=teste` global**,
  `chats_teste` fora do formato (≤ 20 ids de 24 hex), `agenda_max_dia` > `max_disparos_dia` e valores fora de tipo/limite; `409 config_corrida`
  por `versao_esperada` velha ou PK perdida; `garantir_defaults` no boot (R2-17).
- `bloqueio_entrada()`: oito recusas na ordem do contrato 08 (`ia_desligada`, `bloqueio_entrada`, `fora_de_janela`, `opt_out`,
  `teto_atingido`, `teto_diario`, `disparos_dia`, `abertos_max`). `bloqueio_entrada=true` recusa entrada nova e **não encerra, repassa
  nem toca em ninguém** (abertos e pausados seguem as réguas deles).
- `fila`: app Procrastinate 3.10.0 (psycopg, `search_path=procrastinate,public` por `options`), tarefas `turno`, `iniciar`, `lembrete`,
  `expirar_parados`, `reaper_lease`, `auditoria_pii`, `podar`; **rajada** = `schedule_in 3 s` + `queueing_lock=turno:{chat}` + `lock=chat:{chat}`;
  enfileirar na mesma transação (`conexao=`). Tarefa periódica **20:15 BRT** (`15 23 * * *`) que grava `bloqueio_entrada=true` (nunca `false`) e
  **job único de 20/11 21:50** (idempotente por `queueing_lock`; não agenda nem age depois da janela DATAPREV).
- `jobs`: handlers sobre `Servicos` (funções injetadas; sem serviço o job **falha alto**, a implementação real é da B1.6): decisão do lembrete
  (fora da janela adia para a abertura se o cliente ainda estará a ≤ 24 h, senão encerra sem lembrete), `reaper_lease` (pula `pausado` e o
  `reservado` de agendamento até o `lease_ate`; não age sobre chat com turno em curso), `podar` (`ia.fn_texto_podar(14, 1)`,
  `ia.fn_atendimento_podar(365)` e **apaga `procrastinate_jobs`/`procrastinate_events` concluídos > 7 d, falhos > 30 d**), `auditoria_pii` (esqueleto).
- `prontidao`: `readyz` lê `ia.v_prontidao` e as falhas duras (banco, worker sem batimento, fila parada > 10 min, artefatos, migração) e prova
  LISTEN/NOTIFY por round-trip em conexão direta.
- Revisão 1 (`docs/REVISAO-B1.3-3010.md`, A1–A8, A10, A13 parcial): lembrete agendado como alarme sem lock; defer na transação do chamador com savepoint;
  bloqueio das 20:15 por tick, com retry e reconciliação; job de 20/11 sem renascer; cache de config sem valor fantasma; limites cruzados serializados;
  reaper respeita turno na fila; `readyz` sem exceção e com `jobs_falhando`; `tzdata` declarado.
- Revisão 2 (`docs/REVISAO-B1.3-3010-r2.md`, N1–N5, N7): tarefa atrasada não refecha entrada aberta depois do tick; reaper respeita turno na rajada;
  lembrete sai 4 h depois da ÚLTIMA fala da IA (reprograma o alarme velho) e com `retry`; testes de cobertura e do `tzdata`.
- Testes: fila de verdade contra o Postgres 18 descartável do `check.sh` (worker `run_worker_async`), com relógio falso; fixtures em `tests/fixtures_fila.py`.

### B5.7a · extrator determinístico de horário · branch `feat/b5-7a-agenda-extrator`

### Adicionado
- **B5.7a `agenda_extrator` (v1):** extrator determinístico e puro de horário para o agendamento da assinatura (`src/ia_atendimento/agenda_extrator.py`,
  `VERSAO = "1"`). `extrair(texto, agora, ultima_msg_cliente_em, config) -> Resultado` com candidatos imutáveis (`quando` tz-aware BRT, `confianca`,
  `origem` = trecho literal do texto, `fora_da_janela` + `razoes`). Gramática pt-BR por regex e tabelas: hora explícita («às 15», «15h30», «15:30»,
  «3 da tarde», «meio-dia», «umas 3», «3 e meia», «depois das 4»), relativo («daqui a 1 hora», arredondado para cima a 5 min), dia («hoje», «amanhã»,
  dia da semana, «dia 5», «05/11», «10 de nov») e períodos de `agenda_periodos` (só com `usa_periodos=True`; nunca `alta`). **v1 só com hora
  explícita:** sem ela, `candidatos=()` e `motivo_recusa='sem_hora_explicita'`. Ambíguo («15 ou 16», dois dias) fica em `media`, no máximo 3 candidatos.
  Regras duras: janela 08:30-19:00 seg-sáb (sábado até 12:00 por flag), antecedência >= 10 min, teto `min(ultima_msg + agenda_teto_horas, próximo dia
  útil 19:00)`, feriados 02/11 e 20/11 e bloqueio DATAPREV (20/11 22:00 a 23/11 06:00). `ConfigAgenda.das_chaves` valida `agenda_janela`,
  `agenda_periodos` e `agenda_teto_horas` como o DDL. Sem banco, rede ou modelo; só biblioteca padrão.
- Corpus `tests/corpus/agenda_frases.jsonl` (281 frases inventadas, 54 de hold-out) com gerador e README; `tests/test_agenda_extrator.py`
  (EM1: zero data inventada, ambíguo nunca `alta`, hold-out >= 95%, teto, janela, feriados/DATAPREV, idempotência, ruído aleatório com semente).
- **Revisão adversarial 1 (R1-R10, `docs/REVISAO-B5.7a-3010.md`):** data explícita inválida recusa (`data_invalida`) em vez de virar «hoje»; hora lida inteira ou recusada (sem `19:01:00`→19:00, sem prefixo de numeral, «15h e meia», «uma hora e quinze minutos»); alternativas com minutos («15h ou 16:30»); aproximação («umas 3 da tarde») nunca `alta`; hora relativa respeita o dia dito (`dia_contraditorio`); segundos de `agora` contam na antecedência; quantidades («12 parcelas», «R$ 15», «2 contratos», «entre 15 e 16 parcelas») nunca viram hora; 29/02 sem exceção; «meio-dia» é `media`; «meia-noite e meia» usa os minutos; hold-out v2 com 43 casos novos.
- **Revisão adversarial 2 (N1-N8, `docs/REVISAO-B5.7a-3010-r2.md`):** listas e alternativas validadas depois de varrer a frase inteira (ponta recusada ⇒ `hora_incompleta`, nunca sobra uma `alta`; substitui o guarda dependente de ordem); faixa «das 14 às 16h» recusa com `intervalo`; aproximações e hesitações («por volta das», «mais ou menos», «uns», «talvez», «a partir das», «15h por aí»...) valem no máximo `media`; «ou 15 e meia» lê os minutos; duração («16 horas por dia», «daqui a 1 hora ou 2 horas») não é horário; contradição parcial do relativo recusa; «às 15h 06/11» e «às 3 e meia dia 6» deixam de ser recusados; hold-out v3 com 35 casos.

### B1.1 · ciclo de vida do atendimento (sp01 T3) · branch `feat/b1-1-estado`
### Adicionado
- **Migração `0003_estado_aditivo`** (aditiva; a 0001 não muda, `0001.sha256` igual): `ia.atendimento.ultimo_cliente_em timestamptz NULL` com
  `GRANT UPDATE` próprio a `ia_app` (não disputa o CAS de `versao`); CHECK `config_versao_chats_teste_check` (`chats_teste` ≤ 20 ids de 24 hex
  minúsculo, a 0001 aceitava 50 de `[A-Za-z0-9_-]{1,128}`); CHECK `atendimento_chat_id_hex_check` (`chat_id` de 24 hex minúsculo: um chat com
  `_`/`-` passava na 0001 e estourava o CHECK de `passo.msg_chave` na 1ª mensagem). Pendências D1–D3 do contrato 08 §8; D4 (fonte do gasto) não é DDL.
- **`estado.py`**: `abrir` (idempotente por `(origem, chave_logica)` + `entrada_fingerprint` do contrato 08 §4: mesmo corpo devolve o gravado,
  outro corpo `ConflitoIdempotencia`, mesmo com o chat ocupado; chat ocupado `ChatOcupado`), `iniciar`, `abortar`, `aguardar_cliente`/`retomar`,
  `repassar` em duas fases (`repassando`/E10, depois `encerrar(repassado)`), `encerrar`, `ler`; todas as transições passam por `aplicar`
  (`UPDATE … WHERE versao=$v`, `versao+1`, lease renovado, `ConflitoVersao`); `Mudancas` = exatamente as colunas do GRANT (testado contra o catálogo);
  `resolver_modo` (global `real|sombra|duble`, `teste` só em `chats_teste`, persona só em chat de teste); `EntradaAtendimento` sem PII.
  `pausado` já é aceito pelo enum e pelos CHECKs; `pausar`/`sair_da_pausa`/`abrir_agendado` ficam para B5.7b (2 testes `xfail` strict).
- **`estado_conversa.py`**: `EstadoConversa` (JSON ≤ 2 KB, `extra='forbid'`, `hide_input_in_errors`, só códigos/referências/contadores que não são
  coluna), `ler_`/`gravar_estado_conversa` (transição com CAS), `registrar_mensagem_do_cliente` (`ultimo_cliente_em` só avança, sem tocar `versao`),
  `janela_24h_aberta`.
- Testes: `test_migracao_0003.py`, `test_estado.py`, `test_estado_entrada.py`, `test_estado_conversa.py` (corridas entre conexões reais, vetor
  dourado do fingerprint, CHECK cruzado fase×estado). `docs/OPERACAO.md` e `migrations/README.md` ganham a 0003 (ledger na mesma transação, testado).
### Revisão 1 de contexto limpo (`docs/REVISAO-B1.1-3010.md`): A1–A4 e médios
- **A1** `encerrado` é absorvente: `aplicar` passa a ter `de` padrão = estados não terminais; a 0003 ganha o trigger `atendimento_terminal_absorvente`
  (estado/desfecho/`encerrado_em` de encerrado não mudam nem por SQL direto). **A2** `Mudancas.estado_conversa` é `EstadoConversa` (módulo novo
  `modelos_conversa.py`): o dict cru não burla mais `extra='forbid'`. **A3** `ultimo_cliente_em` mais de 5 min no futuro é recusado em `abrir` e
  `registrar_mensagem_do_cliente(..., relogio=)`; `janela_24h_aberta` fecha. **A4** `traduzir_erro_banco`/`executar_traduzindo`: erro de integridade/dado
  vira `DadoRecusado` (sqlstate e restrição, sem a linha) em `abrir` e `aplicar`; `perfil` sem float.
- **M1/M2** `tipos.py`: código, referência e rótulo de perfil recusam documento/telefone (6+ dígitos, CPF/CNPJ mascarado); `perfil` só rótulos.
  **M3** `repassado` só a partir de `repassando` (exceção: `devolvido_pela_s2`). **M4** `aguardar_cliente` grava lease longo (r2: `lease_de_espera`, calculado
  pelo calendário e `lembretes_intervalos_min`; teto de 96 h) e há `renovar_lease`. **M5** `chats_teste` string é `TypeError`; itens conferem 24 hex. **B1–B4, B6**: `aplicar` exige fuso; chaves do cliente não
  saem no erro de corpo; transições levantam `EntradaInvalida`; CHECK `atendimento_fase_estado_check` (E1..E9 em aberto/aguardando, `pausa` só em pausado); inteiros ≤ int4.
### Revisão 2 (`docs/REVISAO-B1.1-3010-r2.md`): R1–R8
- **R1** a regra anti-documento deixa de recusar UUID e id numérico de 6–10 dígitos (só 11 dígitos = CPF/celular, 14 = CNPJ, 55+10/11 = telefone,
  mascarados ou não). **R2** `lease_de_espera(agora, intervalos_min=, proxima_janela=)` calcula o lease até o encerramento por vácuo (+30 min), então
  o reaper da B1.3 (`_SQL_LEASES`, sem mudar o PR #2) não repassa quem espera o lembrete adiado; o alarme não leva lock, só o lease o protege.
  **R3** `renovar_lease` nunca encurta (`greatest`). **R4** o trigger terminal congela também `estado_conversa`, `motivo_desfecho`, `contexto_codigos` e
  `repasse_modo`/`consultor_ref`. **R5** `EstadoConversa` forjado é revalidado. **R6** A1 testado por camada (Python com o trigger desligado; trigger
  com `de` aberto). **R7** 0003 documenta o desfazer e a pré-checagem da fase×estado. **R8** `janela_24h_aberta` com datetime sem fuso é `ValueError`.
### Revisão automática de segurança (S5, S6) em `tipos.py`
- **S5** a checagem de documento remove espaço, ponto, hífen, barra, sublinhado e dois-pontos e recusa qualquer sequência de 10+ dígitos (12 dígitos,
  zero à esquerda, `12345 678901`, `123_456_789_01`...). **S6** UUID deixa de ser allowlist por regex: só `Referencia` (campo de ID) aceita UUID
  parseado, canônico, variante RFC 4122 e versão 4/7, ou id numérico de até 9 dígitos; `Rotulo` e `Codigo` não têm essa porta.
### Corrigido (achado dos próprios testes)
- Duas aberturas simultâneas da MESMA chave: o índice único do chat podia reclamar antes do da chave e a perdedora levantava `ChatOcupado`;
  agora relê e devolve o replay.
### Notas
- `ValidationError.errors()`/`.json()` carregam o valor recusado mesmo com `hide_input_in_errors`: `validar_corpo`/`entrada_de_corpo` devolvem
  só `(campo, regra)` e não encadeiam a causa (422 sem eco de CPF/telefone).

### B1.2 · linha do tempo, mensagens recebidas, conversa cifrada e cofre (sp01 T4) · branch `feat/b1-2-linha-tempo`
- `passos`: uma classe Pydantic por tipo dos **13** (`extra=forbid`, `hide_input_in_errors`), `criar(tipo, nomes=…, **campos)` e `texto_passo`
  determinístico que **nunca cita o cliente** (só códigos, rótulos e tamanho; arquivo dourado `tests/golden/texto_passo.json`; a anotação do
  operador é a exceção: texto do operador, recusado se a máscara o trocaria).
- `linha_tempo`: `gravar_passo` sob `SELECT … FOR UPDATE` do atendimento (recusa sem `turno`/`fase`, recusa envio sem `verif_det`, recusa texto
  que a máscara trocaria); `gravar_mensagem_recebida` com dedupe **permanente** (`Gravada | Duplicada | Conflito`, global, também entre
  atendimentos); `mensagens_pendentes` e `consumir` (CAS por `versao`, um turno por lote).
- `evento_mensagem`: `msg_chave` (`cg:{chat}:{h16}` ou `rpa:{id}`, `h16` por HMAC; vetor dourado do contrato 08 §5.1) e `msg_fingerprint`.
- `conversa`: máscara **antes** de cifrar (CPF com DV, telefone, e-mail, CEP, UUID, 8+ dígitos e nomes da conversa), AES-256-GCM com AAD
  completa e nonce aleatório por linha, `chave_id` mensal, `ler_trocas` (resumo + 3 trocas; chave descartada omite a linha), `gravar_resumo`
  sem dígito/nome/PII e `texto_livre_permitido` (janela de 24 h, fail-closed sem `ultimo_cliente_em`).
- `cofre`: `canal` e `digitacao` cifrados, TTL ≤ 7 d, vencido lê como ausente, `expirar` pela rotina de poda (o `ia_app` não tem DELETE).
- `scrubber`: `EntradaInvalida` (erro de validação sem o valor e sem causa encadeada), `formatar_sem_pii` e `instalar_excepthook`.
### Segurança (achados da revisão automática)
- **S1 (MÉDIO, PII):** `mascarar` não pega nome do cliente. O texto livre que vai a `passo` (nota do operador, motivo da decisão do modelo)
  recebe os `nomes` da conversa; sem eles a nota é recusada e o motivo é redigido por completo.
- **S2 (MÉDIO):** `msg_fingerprint` era `sha256` puro de texto curto (p50 de 11 caracteres): reversível por dicionário. Agora HMAC-SHA256 com
  `CHAVE_FINGERPRINT` (e `h16` com `CHAVE_H16`), as duas obrigatórias no boot, ≥ 32 caracteres e diferentes; os nomes da conversa são
  mascarados antes do hash. **O vetor do fingerprint do contrato 08 §5.1 (`924ee977…`) deixa de valer** (novo: `d91e6bf4…` com a chave de teste).
### Correções da revisão 1 (`docs/REVISAO-B1.2-3010.md`)
- **A1** `passo.motivo` da decisão é CÓDIGO (`^[a-z0-9_]{1,40}$`, padrão `nao_informado`), nunca texto; o `CheckViolation` do banco sai como
  `PassoRecusadoPeloBanco` só com o nome da restrição (o `DETAIL` imprimia a linha inteira). **A2** `EventoMensagem`/`Troca`/`Conversa` sem texto no
  `repr`; todos os modelos de passo e o evento herdam `ModeloSemEco` (o construtor direto levanta `EntradaInvalida`, não `ValidationError`).
  **A3** `msg_chave` por `cgid:{mensagem_id}` quando há id, fração de segundo e query da URL no `h16`, e sem `datetime_post` a chave exige
  `recebido_em` (a mensagem nunca colapsa). **A4** `ultimo_cliente_em` no futuro (> 5 min) fecha a janela; o `xfail` da coluna agora é `strict=True`.
- **M1** hora, TTL e retenção são do `now()` do banco (cofre e conversa; reguardar não renova além de 7 d); **M2** `chave_id` vigente conferido com o mês
  (`ChaveForaDoMes`); **M3** `nomes` obrigatório (`None` recusa); **M4** gancho `casar` sob o `FOR UPDATE` + `xfail(strict)` do casamento (B1.5);
  **M5** fingerprint sobre o texto mascarado SEM nomes (reverte a parte «nomes» do S2: dava `Conflito` falso; o HMAC já resolve o dicionário);
  **M6** `consumir` confere a `versao` antes de validar (`ConflitoDeVersao` ao perdedor); **M7** `LIMITE_NOTA = 240` (40 + 240 cabe nos 300 do CHECK).
- **B1/B2/B3/B7** testes dos 3 mutantes sobreviventes (`ON CONFLICT`, `.strip()`, vencimento do cofre); `Duplicada` não devolve `ordem` de outro
  atendimento; `expirar` e `ler` usam só o relógio do banco; `agora` dos passos saiu.
### Correções da revisão 2 (`docs/REVISAO-B1.2-3010-r2.md`)
- **R2-1** `ModeloSemEco` embrulha o esquema num validador `wrap` externo: `model_validate`, `model_validate_json`, `TypeAdapter` e o construtor levantam
  `EntradaInvalida` (agora `Exception`, não `ValueError`, para o Pydantic não embrulhá-la de novo) sem o valor. **R2-2** `motivo` é `Literal` de
  catálogo fechado (`MOTIVOS_DE_DECISAO`); os demais códigos recusam corrida de 4+ dígitos, CPF/telefone e nome da conversa. **R2-3** `chave_id_do_mes`
  normaliza para UTC (naive é recusado), tolera a chave do mês anterior por 1 h após a virada; regra em `docs/OPERACAO.md` §2.
- **R2-4 (S3)** `cgid:` = HMAC(`CHAVE_H16`, chat_id + mensagem_id)[:32] (cabe no CHECK da 0001). **R2-5 (S4)** sem hora nem id: dedupe secundário por
  fingerprint no mesmo atendimento em 5 s, `Gravada.sem_hora`; nada é rejeitado. **R2-6** removido o `xfail(strict)` inócuo do casamento (o gancho `casar` tem teste verde).
### Notas
- `ultimo_cliente_em` chega na migração 0003 da B1.1; até lá `texto_livre_permitido` recebe o valor por parâmetro e um teste `xfail` nomeado
  (`test_coluna_ultimo_cliente_em_existe_no_atendimento`) guarda a coluna. `registrar()` (passo + contadores no mesmo CAS) depende do `aplicar` da B1.1.

### Revisão de contexto limpo (29/10) · `docs/REVISAO-FUNDACAO-2910.md`
Corrigido (cada item com teste que reprova no código anterior): `config` com lista **positiva** de hosts do modelo (ponto final, ponto
ideográfico e `api.fireworks.ai` global furavam a lista de proibidos), login `ia_app_*` conferido pelo parser do libpq (`%5F`, `?user=`),
segredos vazios recusados e `ConfiguracaoInvalida` sem valor; `cifra` só com a AAD completa (a forma «simples» foi removida), cofre com AAD
própria, rótulos/chaves duvidosos recusados; `mascara` com e-mail Unicode, e-mails colados, dígitos sobrescritos/circulados e tempo linear
(antes: 9 s em 100 mil caracteres); `migracoes` executa os mesmos bytes do checksum e recusa PGSERVICE; passo a passo da S4 com ledger na mesma
transação e `search_path` nos **logins** (o `ALTER ROLE` no grupo `ia_app` não chegava ao `ia_app_a`); `varredura` vê arquivo novo, credencial
em URL e celular; CI com `uv sync --locked`.

### Corrigido
- **Achado MÉDIO da revisão de segurança automática (`pii_masking_bypass`), `mascara.py`:** CPF e telefone com separadores
  fora do conjunto antigo (`[ .-]`) ou repetidos passavam sem máscara (`123 . 456 / 789 -- 00`, `(11) 9 1234_5678`,
  `1 2 3 4 5 6 7 8 9 0 9`, quebra de linha, vírgula, barra). Correção: os padrões agora olham uma vista do texto com os
  dígitos Unicode normalizados para ASCII (largura total, árabe-índico) e classificam a *corrente de dígitos* (até 6
  não-alfanuméricos entre dois dígitos) pelos dígitos, sem olhar os separadores; as trocas valem no texto original pelas
  posições. Data `dd/mm/aaaa` (com `/`, `-` ou `.`, ano 19xx/20xx) e valor `R$ 1.234,56` bem formado não são mascarados.
  Testes novos reprovam sem a correção (14 falhas no código antigo).
- **Segundo achado MÉDIO (`mascara.py`): a isenção monetária protegia CPF e telefone depois de «R$»** (`R$ 123.456.789-09`,
  `R$ 11 91234-5678`) e cortar a corrente no início do trecho isento deixava o resto escapar. Correção: toda corrente de
  dígitos é classificada primeiro (CPF por DV, CEP, telefone BR) e isso nunca é isento; a isenção só vale para o que
  sobraria como `[NUMERO]`, exige centavos, até 3 grupos de milhar e 11 dígitos, e só se a corrente INTEIRA está dentro do
  trecho isento (se entra ou sai dele, a isenção cai e a corrente toda é mascarada). Efeito aceito: `R$ 12.345.678,90`
  (10 dígitos com forma de telefone) é mascarado; dinheiro comum (até R$ 999.999,99) continua intacto.
- Limitação registrada, fora de escopo: dígitos por extenso e dígitos misturados com letras (`5x2x9...`) não são mascarados.

### Adicionado
- Esqueleto do repositório: Python 3.13, dependências pinadas (`uv.lock`), ruff, pytest, `.env.example` só com nomes, `LICENSE` privada.
- `config.Settings` (pydantic-settings, `SecretStr`, `hide_input_in_errors`): recusa API oficial da DeepSeek, qualquer coisa da
  Anthropic, modelo fora de `deepseek-*`/`gemini-*` e `DATABASE_URL` com login `postgres`/`s4_super`/`ia_owner` (o runtime é `ia_app_*`).
- `cifra`: AES-256-GCM com AAD completa do esquema (`atendimento_id|seq|remetente|tipo|chave_id`; cofre `atendimento_id|0|cofre|finalidade|chave_id`),
  chaveiro em arquivo 0600 por `chave_id`; erros e logs sem texto, chave ou ciphertext.
- `mascara`: máscara determinística de PII (CPF por DV, telefone, e-mail, CEP, UUID, número longo, nome marcado).
- `migrations/0001` = bloco `sql` do estudo I **rodada 3c**, byte a byte (`5d1ceec1…3808`, `0001.sha256`); `0002` = Procrastinate 3.10.0
  (`scripts/gerar_0002.py`, com `--verificar`); `migracoes.aplicar`/`conferir` idempotentes com ledger `ia.migracao`, uma transação por arquivo,
  advisory lock e CLI que só aceita banco local (`host`, `hostaddr`, `PGHOST`, `service` verificados).
- Testes: os **350 casos** do `i-teste-0001.sh` portados como dados (nome, papel, SQL, expectativa) para pytest, mais checksum da 0001,
  igualdade com o bloco do estudo I, seeds (27 chaves), `ia_app` sem DDL/DELETE (lido do catálogo), controle negativo (sem os índices de
  trava por chat e de T7 viva as inserções passam) e a 0002.
- `scripts/check.sh` (portão local), `scripts/aplicar_migracoes_local.sh`, `scripts/varredura.py` (segredo, CPF com DV válido, e-mail real),
  `.github/workflows/ci.yml` (ruff + pytest com serviço `postgres:18`, sem segredos, `permissions: contents: read`, actions fixadas por SHA),
  `docs/OPERACAO.md` e `migrations/README.md` (aplicação na S4 = texto para o dono, **não executar sem o «sim»**).
