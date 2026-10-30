# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versionamento semântico. Tags só depois da revisão.

## [0.2.0] (não publicada)

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
