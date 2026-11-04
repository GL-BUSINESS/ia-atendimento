# ia-atendimento

Orquestrador da **IA de atendimento da GL Capital** (MVP em 29/11/2026). Este repositório tem a **fundação (A6)**, o
**ciclo de vida do atendimento (B1.1)**, a **API de entrada (B1.5)**, a **pausa combinada e os jobs da agenda (B5.7b)**, as **pessoas de teste (B2.4)** e, desde a B1.4, o **agente do turno**
(contexto, `Turno`, observabilidade): sem ferramentas de negócio, sem n8n, sem chave de provedor (o modelo real só roda atrás de `Provedor`; nos testes, o `ProvedorFalso`) e sem nada em produção. O que existe e está provado:

| Peça | Onde | Prova |
|---|---|---|
| Esquema `ia_atendimento` (migração 0001 = bloco `sql` do estudo I, byte a byte) | `migrations/0001_esquema.up.sql`, `0001.sha256` | 350 casos portados do `i-teste-0001.sh` + checksum |
| Fila Procrastinate 3.10.0 (migração 0002) | `migrations/0002_procrastinate.up.sql` | aplica limpa; `gerar_0002.py --verificar` |
| Aplicador idempotente com ledger `ia.migracao` | `src/ia_atendimento/migracoes.py` | `tests/test_migracoes.py` |
| `Settings` por env (`SecretStr`, sem segredo no `repr`) | `src/ia_atendimento/config.py` | `tests/test_config.py` |
| AES-256-GCM com AAD, chaves em arquivo 0600 | `src/ia_atendimento/cifra.py` | `tests/test_cifra.py` |
| Máscara determinística de PII | `src/ia_atendimento/mascara.py` | `tests/test_mascara.py` |
| Migração 0003 aditiva (`ultimo_cliente_em`, `chats_teste` ≤ 20 ids de 24 hex, `chat_id` de 24 hex) | `migrations/0003_estado_aditivo.up.sql` | `tests/test_migracao_0003.py` |
| Ciclo de vida do atendimento (CAS por `versao`, lease, idempotência, trava por chat) — B1.1 | `src/ia_atendimento/estado.py` | `tests/test_estado.py`, `tests/test_estado_entrada.py` |
| Estado da conversa (JSON ≤ 2 KB, só códigos) e `ultimo_cliente_em` — B1.1 | `src/ia_atendimento/estado_conversa.py` | `tests/test_estado_conversa.py` |
| Calendário de mensagem (08–20 seg–sáb SP, feriados, DATAPREV) | `src/ia_atendimento/calendario.py` | `tests/test_calendario.py` |
| Config versionada, registro validado e recusas de entrada | `src/ia_atendimento/chave.py`, `chave_registro.py` | `tests/test_chave.py` |
| Fila Procrastinate (rajada de 3 s, trava por chat), jobs e bloqueio das 20:15 | `src/ia_atendimento/fila.py`, `jobs.py` | `tests/test_fila.py`, `tests/test_jobs.py` |
| Prontidão (`readyz`, LISTEN/NOTIFY) | `src/ia_atendimento/prontidao.py` | `tests/test_prontidao.py` |

| Contexto do turno: 8 blocos de H §3.1, ≤ 4 mil tokens (estimativa), corte resumo → trocas → exemplos, sem PII nem valor — B1.4 | `src/ia_atendimento/contexto.py`, `protecao.py`, `modulos_fase.py`, `tokens.py`, `ferramentas.py` | `tests/test_contexto.py`, `test_ferramentas.py`, `test_vazamento_corpo.py` |
| Agente do turno: `Turno`, ações por fase, UM provedor (Fireworks só-EUA), custo por turno — B1.4 | `src/ia_atendimento/turno.py`, `agente.py`, `roteiro_f3.py` | `tests/test_agente.py`, `test_timeout.py` |
| Observabilidade OTel → Phoenix com scrubber de spans e logs — B1.4 | `src/ia_atendimento/observabilidade.py` | `tests/test_observabilidade.py` |

| Extrator determinístico de horário do agendamento (B5.7a, puro) | `src/ia_atendimento/agenda_extrator.py`, `tests/corpus/` | `tests/test_agenda_extrator.py` (EM1) |
| Migração 0004: `ia.fn_anexar_rpa` (SECURITY DEFINER) e a outbox `ia.espelho_evento` — B1.5 | `migrations/0004_anexo_rpa_e_espelho.up.sql` | `tests/test_migracao_0004.py` |
| API de entrada: 13 rotas do contrato 08, auth por token e HMAC do gateway, erros sem eco — B1.5 | `src/ia_atendimento/api/` | `tests/test_api*.py`, `tests/test_contrato_api.py`, `tests/test_corrida.py` |
| Mensagem recebida (uma função para webhook e RPA) e casamento webhook × RPA — B1.5 | `src/ia_atendimento/mensagens.py` | `tests/test_contrato_api.py`, `tests/test_mensagens.py` |
| Agendamento («Vou fazer depois»), faixa de esforço, `pessoas_teste` (arquivo `{pessoas, chats}`), enfileirador e segredos em arquivo 0600 — B1.5 | `agendamento.py`, `esforco.py`, `pessoas_teste/arquivo.py`, `enfileirador.py`, `segredos.py` | `tests/test_api*.py`, `tests/test_enfileirador.py`, `tests/test_segredos.py`, `tests/test_ambiente_api.py` |
| `pessoas_teste`: 84 pessoas sintéticas (uma por `persona_id` da F3, um CPF cada), oferta FACTA ativa com `valid_until` relativo servida em `duble\|teste` (T1/T3), «[TESTE]», formas medidas, `fixtures/duble/` de 360, 3RN e C6 e o kit `chats-teste.sh` — B2.4 | `src/ia_atendimento/pessoas_teste/`, `fixtures/duble/`, `kits/chats-teste.sh`, `scripts/gerar_pessoas_teste.py` | `tests/test_pessoas_teste*.py`, `tests/test_fixtures_duble.py`, `tests/test_corpus_clones.py`, `tests/test_kit_chats_teste.py`, `tests/test_exige_irmao.py` |
| Estado `pausado` (`pausar`/`sair_da_pausa`: só de E2–E6 e E8, nunca E7, com teto de pausados e de horas) e `reservado` de vida longa (`abrir_agendado`/`iniciar_agendado`) — B5.7b | `src/ia_atendimento/estado_pausa.py` | `tests/test_estado_pausa.py`, `tests/test_agenda_jobs.py` |
| Estados da linha `agendamento` (`confirmar`/`disparar`/`cancelar`, CAS por `versao`) e o passo `agendamento` — B5.7b | `src/ia_atendimento/agenda_estado.py` | `tests/test_agenda_estado.py` |
| Jobs `retomar` (alarme sem lock + CAS `confirmado → disparado`) e `reaper_agenda` por minuto; `POST /agendamentos` enfileira o alarme — B5.7b | `agenda_jobs.py`, `fila.py`, `api/agendamentos.py` | `tests/test_agenda_jobs.py` (EM4: restart com 3 `confirmado`) |
| Jobs presos: periódica `jobs_presos` (UPDATE atômico) e vigia do batimento do worker; rearme de agendamento e teto de atraso — B5.7b | `worker_vivo.py`, `agenda_estado.py`, `agenda_jobs.py` | `tests/test_jobs_presos.py` (SIGKILL real), `tests/test_execucao_superada.py`, `tests/test_agenda_rearme.py` |
| Ponto de entrada do worker (`python -m ia_atendimento.worker`, script `ia-worker`, `--saude`); volta perdida fecha a linha (`fechar_volta_perdida`) — B5.7b | `worker.py`, `agenda_estado.py`, `docs/OPERACAO.md` §9 | `tests/test_worker_real.py` (processo real), `tests/test_agenda_volta_perdida.py` |

## Como rodar

Requisitos: `uv`, Python 3.13 (o `uv` instala), `docker` com a imagem `postgres:18` (os testes sobem um Postgres descartável em
`127.0.0.1`, porta livre, e o derrubam ao fim).

```bash
uv sync                      # dependências pinadas (uv.lock)
BANCOS_DUBLE_PATH=<checkout do bancos-duble> bash scripts/check.sh   # portão local: ruff, varredura, checksum da 0001, 0002 em dia, pessoas_teste/fixtures em dia, pytest com tempo medido (a variável é obrigatória: a consistência com o bancos-duble é parte do portão)
uv run pytest -q             # só os testes
bash scripts/aplicar_migracoes_local.sh [--manter]   # aplica 0001+0002 num Postgres descartável e mostra o ledger
```

Sem docker (CI): `IA_TESTE_PG_HOST=localhost IA_TESTE_PG_PORT=5432 uv run pytest` usa um serviço Postgres local já de pé.
A fixture **recusa** host que não seja local e cluster que já tenha papéis `ia_*`: os testes nunca tocam a S4.

Os 350 casos de `tests/test_esquema.py` formam uma **sequência com estado compartilhado** (como o script do estudo I): rode o
módulo inteiro, não um caso solto com `-k`.

## Variáveis de ambiente

Só nomes em `.env.example` (copie para `.env`, que o git ignora). `Settings` valida no boot: modelo `deepseek-*`/`gemini-*`,
URL do modelo em https (http só em localhost) e **nunca** `deepseek.com` nem `anthropic.com`.

| Variável | Para quê |
|---|---|
| `DATABASE_URL` | banco `ia_atendimento`, login `ia_app_a`/`_b` (sem DDL, sem DELETE) |
| `MODELO_NOME`, `MODELO_BASE_URL_1`, `MODELO_API_KEY_1` | DeepSeek V4.1 Flash 1017 no Fireworks só-EUA (estudo G §3) |
| `API_TOKENS` | tokens da API por origem, JSON `{"n8n_braco": "…", "ti": "…", "c360_api": "…", "vigia": "…"}` (`X-IA-Token`; cada um >= 32 caracteres e diferente dos outros; `robo_esteira` é reservada e não tem token) |
| `MODELO_ROTEADOR` | roteador só-EUA (`…/routers/deepseek-<versão>-us`, o do `MODELO_NOME`); outro valor derruba o boot |
| `MODELO_RACIOCINIO_OFF` | como desligar o raciocínio no `extra_body`: `reasoning_effort_none` (padrão) ou `thinking_disabled`. **HIPÓTESE até a A2.9** |
| `MODELO_TEMPERATURA`, `MODELO_MAX_TOKENS`, `MODELO_TIMEOUT_S` | chamada ao modelo (0,3 · 400 · 8 s, teto de 10 s; sem retentativa do SDK, só o `output_retries=1`) |
| `CHAT_REF_CHAVE` | HMAC do `candidato.chat_ref` (>= 32 caracteres, diferente de `CHAVE_H16` e `CHAVE_FINGERPRINT`, permanente) |
| `GATEWAY_HMAC_ARQUIVO` | arquivo **0600** montado `:ro` com 1 ou 2 chaves HMAC do gateway (uma por linha; duas só na virada de rotação) — contrato 01 §3.2 |
| `SEGREDOS_SAIDA_ARQUIVO` | arquivo **0600** montado `:ro`, JSON com `ia_orquestrador_bearer`, `chatguru_token_ia`, `c360_client_id`, `c360_client_secret` (só validados no boot; usados a partir da B1.6/B6.8) |
| `RESPONSAVEL_IA` | e-mail do Amado no ChatGuru: `responsavel_email` diferente dele no evento marca `delegacao_externa` |
| `IA_MIGRACOES_DIR` | (opcional) pasta das migrações que o `/readyz` confere; padrão: `migrations/` do checkout ou a que o wheel leva dentro do pacote; não achar derruba a subida |
| `PESSOAS_TESTE_ARQUIVO` | `pessoas_teste`, JSON `{"pessoas": [uuid], "chats": {chat_id: uuid}}`; vazio = ninguém é de teste. Monte-o com `python -m ia_atendimento.pessoas_teste arquivo --par CHAT=PERSONA` (kit `config/chats-teste.sh`, `docs/OPERACAO.md` §10): as 84 pessoas do catálogo mais os chats da TI |
| `CASAMENTO_JANELA_S`, `CASAMENTO_JANELA_SEM_HORA_S` | janelas do casamento webhook × RPA (padrão 10 s e 30 s) |
| `PRECO_IN_USD`, `PRECO_CACHE_USD`, `PRECO_OUT_USD`, `CAMBIO`, `PRECO_TEMPLATE_BRL` | preços do custo (padrão do plano: 0,45 / 0,009 / 1,80 por 1M de tokens e câmbio 5,3346; ≤ 0 recusa o boot) |
| `PHOENIX_ENDPOINT` | traces (banco `ia_obs`); vazio = não exporta |
| `PHOENIX_PROJETO`, `PHOENIX_API_KEY` | projeto (padrão `ia-atendimento`) e chave do Phoenix, se ele exigir (`SecretStr`) |
| `CHAVE_AES_ID`, `CHAVE_AES_ARQUIVO` | chave vigente (mensal) e arquivo 0600 `{"<id>": "<base64 de 32 bytes>"}` |
| `CHAVE_H16`, `CHAVE_FINGERPRINT` | chaves HMAC (>= 32 caracteres, diferentes entre si, permanentes) do `msg_chave` e do `msg_fingerprint` da mensagem recebida |

## API de entrada (B1.5)

Contrato: `contratos/08-orquestrador.md` v2.1/v2.2 (fora deste repo). `uvicorn --factory ia_atendimento.api.ambiente:criar_app_de_ambiente --host 10.90.0.5 --port 8000 --no-access-log`
(OPERACAO.md §8). Autenticação: `X-IA-Token` (origem = a do token que casou) em todas as rotas, menos `/eventos/chatguru`, que pede a **assinatura HMAC do
gateway** (`x-gl-origem|rota|timestamp|assinatura`; o token `ti` vale ali só como replay manual, sem `x-gl-*`), e `/healthz`, aberta.

| Rota | Origens |
|---|---|
| `POST /atendimentos` | `n8n_braco` (e `robo_esteira`, reservada, sem token) |
| `GET /atendimentos/por-chave/{chave}` | `n8n_braco`, `vigia`, `ti` |
| `POST /eventos/chatguru` | assinatura do gateway; ou `ti` (replay manual) |
| `POST /eventos/mensagem` | `ti` |
| `POST /agendamentos` (grava o passo `agendamento` e enfileira o alarme do `retomar` em `dispara_em`; `retoma_fase` só `E8` com `agenda_b_digita=false`), `POST /sessoes/{id}/candidatos` | `n8n_braco` |
| `GET /config`, `GET /config/{nome}` | `n8n_braco`, `ti`, `c360_api`, `vigia` |
| `PUT /config/{nome}` | `ti`; `c360_api` só `ia_ativa` e `modo` |
| `POST /atendimentos/{id}/anotacoes` | `ti` |
| `GET /readyz`, `GET /saude` | qualquer token válido; `GET /healthz` sem token |

Erros: `{"erro":{"codigo","mensagem","campo","detalhe"},"trace_id"}`; nunca ecoam o valor recebido. Sem CPF em corpo, log ou banco. Decisões e pendências:
`docs/DECISOES-B1.5-3010.md`.

## Contrato de dados

O esquema é do **estudo I** e não se edita aqui: `estudos/semana-1/i-esquema-reconciliado.md` (bloco `sql` do §4; rodadas até
a 3c, §12) e a visão geral em `MONITORAMENTO-DESIGN.md` §5 («Base comum de dados»), ambos em `docs/planejamento-ia/` do
repositório de documentação da empresa (fora deste repo). Mudou o desenho = **nova migração** (a 0003 já existe: B1.1), nunca edição da 0001
depois de aplicada. O teste `test_0001_igual_ao_bloco_do_estudo_i` compara o arquivo com o bloco do estudo (quando o estudo
está na máquina) e `test_checksum_0001` com `migrations/0001.sha256`.

Para aplicar na S4 (feito pelo dono, nunca por este código): `migrations/README.md` e `docs/OPERACAO.md`.

## Regras invioláveis (resumo do roteiro §0.3)

1. **Nada da Anthropic no produto.** Claude/Codex são só ferramentas de desenvolvimento. **Nunca a API oficial da DeepSeek**;
   só `us.api.fireworks.ai` (roteador `-us`).
2. **CPF nunca** ao modelo, prompt, log, span, banco da IA, ntfy, Kan ou payload de entrada. Não há coluna de CPF nem de telefone.
3. **Texto do cliente só mascarado e cifrado** (AES-256-GCM, `conversa_cifrada`), 14 dias após o encerramento (teto 30 d).
   Nunca em `passo`, log, ntfy, Kan ou git.
4. **Tudo nasce desligado e em dublê:** `ia_ativa=false`, `modo="duble"`, MVP só FACTA.
5. **Escrita em produção só com o «sim» do dono**, pelos kits; este repo não aplica nada na S4/VPS.
6. **T7 em dúvida nunca se repete** (a trava é do banco: índices únicos parciais do ledger).
7. **Esperar a condição, não o sinal** em testes; **dado de teste sintético**, nunca de produção.
8. **Versionar sempre:** tag semver + release no GitHub (a tag `v0.1.0` só depois da revisão).

## Limitações conhecidas

- **Máscara de PII** (`mascara.py`): não mascara dígitos por extenso («cinco dois nove...») nem dígitos misturados com letras;
  excesso de máscara é aceito (corrente de 8+ dígitos vira `[NUMERO]`, data e valor `R$ 1.234,56` bem formados são isentos).
- **Procrastinate** usa nomes sem schema em funções e gatilhos: a conexão da fila precisa de `search_path = procrastinate, public`
  (ver `migrations/README.md`). Isso é decisão da infra/B1.3, não da migração.
- **AAD da cifra:** uma só forma, `atendimento_id|seq|remetente|tipo|chave_id` (cofre: `atendimento_id|0|cofre|finalidade|chave_id`),
  com contexto obrigatório e domínio fechado. Quem decifra passa o mesmo contexto de quem cifrou.
- **Máscara de PII:** `[NOME]` só para nomes que o chamador informa (a máscara não adivinha «me chamo X»); e-mail escrito por extenso
  («fulano arroba gmail ponto com», «fulano (at) gmail.com») e CPF com `%`-codificação em URL não são mascarados.
- **Destino do modelo:** `Settings` aceita só `https://us.api.fireworks.ai` ou loopback. Trocar de provedor (reserva Together só-EUA,
  Gemini) é mudança de código revisada, não de variável de ambiente.

## Estrutura

```
migrations/      0001 (estudo I), 0002 (Procrastinate), 0003 (estado), 0004 (anexo do RPA e outbox), 0001.sha256, README.md (ordem de aplicação na S4)
scripts/         check.sh, aplicar_migracoes_local.sh, gerar_0002.py, varredura.py
src/ia_atendimento/  config.py, cifra.py, mascara.py, migracoes.py, turno.py, agente.py, contexto.py, observabilidade.py (B1.4), estado*.py, fila.py, jobs.py, mensagens.py, agendamento.py, agenda_estado.py, agenda_jobs.py, estado_pausa.py, worker_vivo.py, worker.py, api/ …
tests/           test_*.py; casos/ = os 350 casos do estudo I como dados (nome, papel, SQL, expectativa)
docs/OPERACAO.md operação (aplicação na S4 = texto para o dono, não executar sem o «sim»)
.github/workflows/ci.yml  ruff + pytest com serviço postgres:18, sem segredos
```
