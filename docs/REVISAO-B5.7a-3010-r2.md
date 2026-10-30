# Revisão adversarial 2 — B5.7a (30/10/2026)

Revisor de contexto limpo (não escreveu o código). Branch `feat/b5-7a-agenda-extrator`, HEAD `377720a` (correções da Revisão 1).
Escopo: `git diff 065c03f..377720a`, `docs/REVISAO-B5.7a-3010.md`, ROTEIRO §B5.7a e `m-agendar-assinatura.md` (EM1). Só leitura; nada no repositório foi alterado além deste arquivo.
Método: `uv run pytest tests/test_agenda_extrator.py -q` (318 passam); comparação **antigo (065c03f) × novo** em ~22.800 frases geradas (hora × dia × prefixo × sufixo) e
~700 pares «X sep Y»; 3.000 strings hostis; 10 mutações do código (cópia em diretório temporário).
Preparação dos exemplos: `E(t) = extrair(t, 05/11/2026 10:00 BRT, mesma ultima_msg, ConfigAgenda())` (quinta-feira).

**Veredito: APROVAR COM CORREÇÕES (bloqueantes: N1, N2, N3, N4).** Os 11 casos do revisor estão fechados e não há exceção nem origem inventada.
Mas duas correções criaram regressões que violam EM1 («ambíguo nunca alta») em frases simples (N1, N2), e duas classes vizinhas de R2/R4 continuam abertas (N3, N4).

## 1. R1–R11: fechados?

| # | Caso do revisor | Variações tentadas | Resultado |
|---|---|---|---|
| R1 | `31/11 às 15h`, `29/02/2027 às 15h` recusam `data_invalida` | `30/02`, `31/04`, `00/11`, `0/0`, `13/13`, `dia 0`, `dia 32`, `dia 29 de fevereiro`, `29/02/2028` (válida), `29/02/2024` (passada) | fechado |
| R2 | `hoje às 19:01:00`, `às 15:99`, `dozentas`, `15 e trinta e cinco` recusam | `15h 30`, `15:3`, `15.30`, `15 30`, `15,30`, `15:30:45` recusam; `15h30min`, `15:30h`, `15h e meia`, `daqui a uma hora e quinze minutos` leem inteiro | fechado nos casos do revisor; **regride em listas com «e»: N1** |
| R3 | `às 15h ou 16:30` → 15:00 e 16:30 | `15:30 ou 16h45`, `entre 14h30 e 15h`, `15h ou 16:99` (recusa) | fechado para dígitos; **abertos: N2, N5** |
| R4 | `umas 3 da tarde` não é alta | `umas 10 da manhã`, `depois das 3 da tarde`, `umas 7 da noite` | fechado só para «umas»/«depois das»; **N4** |
| R5 | `hoje ou amanhã daqui a 1 hora` não é alta | `amanhã daqui a 1 hora`, `segunda daqui a 2 horas` (`dia_contraditorio`), `quinta daqui a 2 horas` (hoje é quinta: média), `daqui a 1 hora ou amanhã` | fechado; resíduo **N7** |
| R6 | `agora` 10:00:59, `hoje às 10:10` → `antecedencia` | segundos 0/1/59, 10:00:59.999999, UTC 13:00:59; `daqui a 10 min` (10:10 com 00 s; 10:15 com 1 s); `daqui a 1 hora` (11:00 / 11:05) | fechado |
| R7 | `entre 15 e 16 parcelas` recusa | `10 contratos às 15` (15:00, certo), `15 reais`, `às 15 e 16 parcelas`, `R$ 15`, `15 mil às 16`, `2 filhos às 15`, 50 outras quantidades (`anos`, `meses`, `%`, `salários`, `euros`...) | fechado; classe vizinha **N6** |
| R8 | `29/02 às 15h` com agora em dez/2028 não lança | `agora` = 29/02/2024, 31/12 23:59:59.999999, 28/02/2027 | fechado |
| R9 | `meio-dia` é média | `meio dia e meia`, `meia-noite`, `meio-dia ou 1` | fechado |
| R10 | `meia-noite e meia` = 00:30 do dia seguinte | idem em `meia noite e meia` | fechado |
| R11 | hold-out sem casos que ensinaram correção | README e `test_r11` honestos; ver §5 | fechado, com ressalva |

Sem regressão nas frases simples: `às 15h`, `amanhã às 10:30`, `hoje 14h`, `sábado 9h`, `15h ou 16h`, `às 3 da tarde`, `daqui a meia hora`, `segunda às 14h`, `às 19h`,
`às 19h30` (fora), `às 12` etc. dão o mesmo resultado de antes (conferido em ~22.800 combinações; as diferenças são todas as listadas abaixo ou correções esperadas de R2/R3/R4/R9).

## 2. Achados novos

### N1 — ALTO — lista «X e Y» (e «três ou 16:30»): metade recusada, a outra sobrevive como ALTA (regressão causada por R2)
`agenda_extrator.py:184` (`_SEM_RESTO`, usado em 207–212) recusa o primeiro horário quando vem «e <dígito>» ou «ou <dígito>»; o segundo, lido sozinho, passa.
O guarda de 331–335 só cobre «ou» com lado esquerdo que começa por dígito, então não protege «e» nem numeral por extenso.
Hoje: `E("às 15h e 16h")` → **só 16:00 alta** (antes: 15:00 e 16:00, médias). Igualmente `15h e 16h30`, `15:30 e 16h`, `às 15 e 16:30`, `às 15 e 4 da tarde` (48 combinações),
`às três ou 16:30` → **16:30 alta**, `às 3 e meia ou 16:30` → 16:30 alta, `às 3 e meia ou 4 e meia` → 16:30 média sem o 15:30.
Correção: marcar `v.lista_incompleta = True` sempre que `_SEM_RESTO` bloqueia um achado e recusar a frase inteira (motivo `lista_incompleta`), ou aceitar «A e B» como alternativa média.
Teste que reprova hoje: `assert not [c for c in E("às 15h e 16h").candidatos if c.confianca == "alta"]` (e `E("às três ou 16:30")`).

### N2 — ALTO — `_depois_de_alternativa_recusada` depende da ordem de varredura e descarta alternativa válida (regressão causada por R3)
`agenda_extrator.py:331–335`, chamado em 348. O guarda olha `v.ocupado` do lado esquerdo, mas `meio-dia` (401), `depois das` (408), `umas` (413) e `N da tarde` sem «ou» são varridos
**antes** de `_R_H`/`_R_AS`; nesse momento o «15h» ainda não está ocupado e é tomado por «recusado», então a alternativa da direita é jogada fora e o «15h» sobra sozinho.
Hoje: `15h ou meio-dia`, `14h ou depois das 16`, `14h ou umas três`, `15h ou quatro da tarde`, `15h ou meio dia e meia` → **só o da esquerda, ALTA** (antes: duas médias). `10h ou meio-dia` perde o meio-dia.
Lacuna de teste: remover o guarda (linha 348) mantém **318/318 verdes**; nenhum teste o exercita.
Correção: decidir depois da varredura completa (segunda passada com `ocupado` final) ou registrar os trechos efetivamente rejeitados em `_Varredura`.
Teste que reprova hoje: `assert [c.quando.strftime("%H:%M") for c in E("15h ou meio-dia").candidatos] == ["12:00", "15:00"]`.

### N3 — ALTO — faixa «das 14 às 16h» vira 16:00 ALTA (pré-existente; mesmo mecanismo do R2: reconhecimento parcial)
Não há regex de faixa «de/das N às/a M»: só o último extremo é lido. `E("das 14 às 16h")` → **16:00 alta [16h]**; `de 14 às 16` → 16:00 alta; `das 10 às 12` / `10 às 12` → 12:00 alta;
`15 às 16h30` → 16:30 alta; `15h até 16h` e `às 15 a 16` → 15:00 alta (limite final ignorado). É uma das formas mais comuns de o cliente dizer disponibilidade; a confirmação tácita (B5.7c) agendaria no fim da faixa.
Correção: `_R_FAIXA = (?:de|das?)\s+N(…)\s+(?:a|as|ate)\s+M(…)` ⇒ média com os dois extremos (ou recusa); extremo de «até» nunca é alta.
Teste que reprova hoje: `assert all(c.confianca != "alta" for c in E("das 14 às 16h").candidatos)`.

### N4 — ALTO — aproximações além de «umas»/«depois das» continuam ALTA (R4 só fechou duas palavras)
`aprox` só é ligado em 409/412/414 (e alternativas). Hoje saem **alta**: `por volta das 15h`, `mais ou menos 15h`, `15h mais ou menos`, `aproximadamente 15h`, `perto das 15h`, `lá pelas 15h`,
`pelas 15h`, `uns 15h`, `tipo 15h`, `15h por aí`, `umas 15:30` (→ 15:30 alta; antes 15:00 média), `umas às 3 da tarde`, `umas as 15`, `15h ou mais`, `a partir das 15h`, `após as 15h`.
Hesitações também: `talvez 15h`, `acho que 15h`, `quem sabe 15h`, `15h se der` → alta (MÉDIO).
Correção: lista de hedges (janela de ~25 caracteres antes/depois do trecho) que força `aprox=True`; `a partir/após/ou mais` = limite inferior, recusar ou média.
Teste que reprova hoje: `for t in ("por volta das 15h", "mais ou menos 15h", "umas 15:30", "aproximadamente 15h"): assert all(c.confianca != "alta" for c in E(t).candidatos)`.

### N5 — MÉDIO — alternativa «ou 15 e meia» gera o minuto errado (R3 por outro caminho)
`_lado` (198) termina em `(?![\w:])` e aceita «e meia» logo depois; `_R_OU` registra 15:00 e deixa «e meia» para trás. `E("às 14h ou 15 e meia")` → 14:00 e **15:00** (média); `15h ou 16 e meia da tarde` → 15:00 e 16:00;
`15h ou 16h30min` agora recusa tudo (sobre-recusa leve). Hoje o cliente diz 15:30 e a IA oferece 15:00.
Correção: acrescentar `(?!\s+e\s+(?:{_MINW}\b|\d))` ao lado b (e ao a) de `_R_OU`/`_R_ENTRE`, ou suportar «e meia» em `_lado`.
Teste que reprova hoje: `assert "15:00" not in [c.quando.strftime("%H:%M") for c in E("às 14h ou 15 e meia").candidatos]`.

### N6 — MÉDIO — duração em horas lida como horário ALTO (classe do R7: número sem sentido de relógio)
`_R_H` (210) aceita qualquer «N horas». `trabalho 16 horas por dia` → 16:00 **alta**; `trabalho 12 horas por dia` → 12:00 alta; `demora 15 horas`, `espero há 15 horas`, `faz 15h que espero` → 15:00 alta.
Na mesma família: `daqui a 1 hora ou 2 horas` → 11:00 e **14:00** (média; «2 horas» lido como relógio); `daqui a 1 ou 2 horas` → 13:00 e 14:00; `dentro de 1 hora ou 2` → 11:00 alta (descarta «ou 2»; `_RESTO_REL` 215 não trata «ou»).
Correção: sem «às»/«h» colado, «N horas» precedido de `há|faz|por|demora|trabalho|durante|leva` ou seguido de `por dia|de trabalho|de curso` ⇒ não é hora; em contexto de «daqui a», o segundo «N horas» é duração; `_RESTO_REL` deve recusar «ou <dígito>».
Teste que reprova hoje: `assert not E("trabalho 16 horas por dia").candidatos`.

### N7 — MÉDIO — contradição parcial é ignorada em silêncio
`_combinar` 591–592: `return saida or recusa or ...`; a recusa `dia_contraditorio` só vale se **nada** mais saiu. `E("amanhã às 10 daqui a 1 hora")` → 06/11 10:00 **alta**, descartando o relativo (hoje 11:00).
Correção: se houve `recusa` e `saida` não vazia, devolver recusa (ou rebaixar tudo a média).
Teste que reprova hoje: `assert all(c.confianca != "alta" for c in E("amanhã às 10 daqui a 1 hora").candidatos)`.

### N8 — BAIXO — sobre-recusa nova (lado seguro, mas frases claras)
`E("às 15h 06/11")`, `15h 6/11/2026` (antes lia 15:00 em 06/11): `_R_H` tem `(?!\s*\d)` (210) e `_R_AS` agora exclui unidade, então ninguém lê. `E("às 3 e meia dia 6")`, `às quatro e meia dia 10 de novembro`:
«dia» está em `_QUANTIDADE` (189), logo «meia dia» parece quantidade; `às 15 dia 6` também recusa (já era assim). Correção: `dias?\b(?!\s+\d)` em `_QUANTIDADE` e `(?!\s*\d(?!\d*/))` em 210.

### N9 — BAIXO — notas
- `depois das 15h` → 15:15 (`extra=15`, 409): minuto que o cliente não disse; é média e foi decisão antiga, mas o consumidor (B5.7c) nunca pode mostrar «15:15» sem confirmação, e a `origem` termina em «depois das 3» para «depois das 3 da tarde».
- `dia 31` dito em novembro vira 31/12 (`_proxima_data`); sempre cai em `acima_do_teto`, sem dano.
- Dígitos Unicode (fullwidth, árabe-índico) são aceitos como número; a `origem` permanece literal. Aceitável.
- `50/50 às 15h` e `24/7 às 15h` entram como data (recusa ou data errada, fora do teto); raro.

## 3. Entradas hostis
3.000 strings (6 geradores: tokens de gramática com símbolos/NUL/RLO/emoji/fullwidth/árabe-índico, ASCII imprimível, code points aleatórios até U+2FFFF, `às 15h` repetido até 1.100 caracteres,
só dígitos/pontuação, 1.100 dígitos) × 9 valores de `agora` (2024-02-29, 2026-12-31 23:59:59.999999, 2028-12-05, UTC, sábado, 20/11 21:59...) × `usa_periodos` aleatório:
**0 exceções**, 810 candidatos, **todos com `origem` não vazia e substring literal do texto**, nenhum acima de 3, nenhum alta com mais de um candidato, pior tempo 22 ms.
Casos de ReDoS dirigidos (`as 15 e ` ×125, `15h ou ` ×140, `1h ` ×160, `́` ×990 + `15h`): ≤ 9 ms.

## 4. Os testes `test_r*` reprovam sem a correção?
Mutação aplicada em cópia (scratchpad), suíte inteira de 318 testes:

| Mutação (desfaz) | Linha | Resultado | Teste que pega |
|---|---|---|---|
| remover `data_invalida = True` (R1) | 477–480 | 4 falhas | `test_r1_data_explicita_invalida_nao_vira_hoje` + corpus |
| `(?:{_W})\b` sem `\b` (R2) | 179 | 2 falhas | `test_r2_...` (`dozentas`) |
| `_SEM_RESTO = ""` (R2) | 184 | 3 falhas | `test_r2_...` (`15 e trinta e cinco`) |
| `_lado` sem minutos (R3) | 395 | 2 falhas | `test_r3_alternativa_preserva_os_minutos...` |
| ignorar `aprox` (R4) | 358 | 2 falhas | `test_r4_aproximacao_nao_vira_alta_com_periodo` |
| `iguais` vazio não recusa (R5) | 569–570 | 2 falhas | `test_r5_hora_relativa_respeita_o_dia_explicito` |
| truncar `agora` (R6) | 611 | 1 falha | `test_r6_...` (linha 453) |
| `except ValueError` do bissexto (R8) | 449 | 1 falha (ValueError) | `test_r8_ano_bissexto_...` |
| minutos fixos em 0 na meia-noite (R10) | 404 | 2 falhas | `test_r10_...` |
| **remover `_depois_de_alternativa_recusada` (R3)** | **348** | **318 passam** | **nenhum (tautologia ao contrário: o guarda é código morto para a suíte e é a origem de N2)** |

`test_r1`, `test_r6`, `test_r8`, `test_r10` exercitam diretamente as linhas 477–480, 611 (+526), 449 e 404; não são tautológicos. Fraquezas: `test_r4` e `test_r7` só cobrem as palavras da lista
(N4/N6 passam); `test_r11` só confere a etiqueta `regressao`, não os ids `ho-251/253` que a Revisão 1 citou.

## 5. Hold-out
O README é honesto: v2 (43 casos) foi escrito depois da Revisão 1 pelo mesmo autor, 100% na 1ª rodada, e admite não exercitar os mecanismos da revisão. Nenhum dos 95 casos de hold-out
cobre N1–N7 (lista com «e», faixa «das 14 às 16», «por volta das», «ou meio-dia»). O 95% de acerto continua sendo gate de aceite, mas não é evidência de ausência de N1–N4; sugiro 30 casos novos
escritos por quem não viu este documento, congelados antes de qualquer ajuste.

## 6. Resumo para o autor
Bloquear merge até: N1 e N2 (regressões; corrigir e acrescentar testes que falham sem o guarda), N3 (faixa), N4 (hedges). N5–N7 no mesmo ciclo se couber; N8–N9 podem esperar.
Depois: nova rodada com os mesmos 10 mutantes de §4 mais um para o guarda (348), e as variações de cada item acima viram `test_r12_*`.

## Resposta do autor (r2) (30/10/2026)

Os 8 achados N1–N8 foram tratados no commit `fix: extrator v1 — correções da revisão 2 (N1–N8)` (`git log --grep "revisão 2"`). Ordem seguida: 35 casos de hold-out v3
escritos e congelados antes (1ª rodada contra `377720a`: 0/35), mais os `test_n*` e casos `regressao` no corpus (75 testes vermelhos), depois a correção (395 verdes).
Mudança de desenho principal: `_SEM_RESTO` e `_depois_de_alternativa_recusada` (que dependiam da ordem da varredura) foram removidos; `_lista_incompleta` roda DEPOIS de todas as
varreduras e recusa a frase inteira (`hora_incompleta`) se um conector «e»/«ou» liga uma hora lida a um número que não virou hora, em qualquer sentido.

| # | Correção | Teste / caso |
|---|---|---|
| N1 | «15h e 16h», «às 15 e 16:30», «às três ou 16:30»: as duas pontas ficam lidas (2 candidatos ⇒ `media`); ponta recusada ⇒ `hora_incompleta` | `test_n1_n2_n5_lista_ou_alternativa...`, `test_n1_n2_metade_recusada...`; hold-out v3 `lista` |
| N2 | Validação de lista pós-varredura (independe da ordem): «15h ou meio-dia», «14h ou depois das 16», «14h ou umas três» mantêm as duas alternativas | mesmos testes; mutação: desligar a validação reprova 12 testes, só o ramo «anterior» reprova 1 |
| N3 | `_R_FAIXA` («das/de N às/a M», «N até M»): recusa `intervalo`; «15 a 16 parcelas», «dia 5 a 7» não entram | `test_n3_*`; hold-out v3 `intervalo` |
| N4 | `_R_HEDGE` em janela de 26/16 caracteres (por volta, mais ou menos, aproximadamente, perto das, lá pelas, pelas, uns/umas, tipo, por aí, ou mais, a partir, após, cerca de, em torno, quase, talvez, acho que, quem sabe, se der/puder) força `aprox`; vale também para o relativo; «depois de amanhã» não conta | `test_n4_*` (24 frases); hold-out v3 `aproximado` |
| N5 | Lado da alternativa com «e meia/dígito» logo depois deixa de casar (vira EMEIA ⇒ 15:30); «16h30min» lido | `test_n1_n2_n5...` (`14h ou 15 e meia`, `15h ou 16h30min`) |
| N6 | `_eh_duracao` (há/faz/demora/trabalho/por... antes; «por dia», «de trabalho», «que espero» depois) e `_R_REL_LISTA` (`duracao_ambigua`) | `test_n6_*`; hold-out v3 `duracao` |
| N7 | Qualquer contradição do relativo com o dia dito recusa a frase (`dia_contraditorio`); `_par_fixo` respeita a confiança do relativo | `test_n7_*` |
| N8 | `(?!\s*\d+(?![\d/]))` no `_R_H` aceita data depois da hora; «dia N» deixa de ser quantidade | `test_n8_nao_recusa_demais` |
| N9 | Aceito sem mudança: «depois das 15h» → 15:15 (`media`); `dia 31` em novembro cai em 31/12 (sempre `acima_do_teto`) | — |

Mutantes (todos reprovam): validação de lista (12), faixa (11), hedge (25), duração (6), contradição parcial (7), ramo «anterior» (1). Mudança de comportamento deliberada: «às 11 ou 12 ou 13 ou 14 ou 15»
(cinco pontas, a última sem par) agora é `hora_incompleta`; `ambiguo_demais` continua para seis pontas lidas.
