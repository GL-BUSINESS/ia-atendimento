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
- **Revisão adversarial 2 (N1-N8, `docs/REVISAO-B5.7a-3010-r2.md`):** listas e alternativas validadas depois de varrer a frase inteira (ponta recusada ⇒ `hora_incompleta`, nunca sobra uma `alta`; substitui o guarda dependente de ordem); faixa «das 14 às 16h» recusa com `intervalo`; aproximações e hesitações («por volta das», «mais ou menos», «uns», «talvez», «a partir das», «15h por aí»...) valem no máximo `media`; «ou 15 e meia» lê os minutos; duração («16 horas por dia», «daqui a 1 hora ou 2 horas») não é horário; contradição parcial do relativo recusa; «às 15h 06/11» e «às 3 e meia dia 6» deixam de ser recusados; hold-out v3 com 35 casos.

## [Unreleased]

## 0.2.0 (não publicada) · B1.1 ciclo de vida do atendimento (sp01 T3)
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
