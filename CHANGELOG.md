# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versionamento semântico. Tags só depois da revisão.

## 0.2.0 (não publicada)

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

## [Unreleased]

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
