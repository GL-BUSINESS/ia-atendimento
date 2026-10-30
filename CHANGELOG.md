# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versionamento semântico. Tags só depois da revisão.

## [Unreleased]

## 0.2.0 (não publicada)

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
