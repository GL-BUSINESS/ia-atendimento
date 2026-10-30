# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versionamento semântico. Tags só depois da revisão.

## 0.2.0 (não publicada)

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
