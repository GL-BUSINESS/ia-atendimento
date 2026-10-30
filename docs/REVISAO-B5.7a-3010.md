# Revisão adversarial B5.7a — 30/10/2026

**Veredito: REPROVAR.** Há violações reproduzíveis de EM1 e da antecedência mínima: datas e minutos são descartados, aproximações recebem confiança alta e números sem significado temporal geram horários.

Branch `feat/b5-7a-agenda-extrator`, HEAD `065c03f`, comparada com `origin/main` pelo diff de três pontos. Revisão coletiva do diff completo: 7 arquivos, 1.705 inserções. Nenhuma alteração na implementação, no corpus ou no Git.

Referências: `ROTEIRO-DE-ACAO.md`, §B5.7a, e `estudos/semana-1/m-agendar-assinatura.md`, especialmente §§2.3–2.4 e EM1, em `/opt/claude/docs/planejamento-ia/`.

Validação: `uv run pytest tests/test_agenda_extrator.py -q -p no:cacheprovider`, com bytecode desabilitado e cache do uv em `/tmp`: **265 passaram; 54/54 no conjunto chamado hold-out**. Os onze testes propostos abaixo foram exercitados com `uv run python -c`: todos reprovam atualmente, incluindo a exceção do item 8.

Preparação comum aos exemplos, com textos inteiramente sintéticos:

```python
from datetime import datetime
from ia_atendimento.agenda_extrator import ConfigAgenda, Resultado, extrair, FUSO

a = datetime(2026, 11, 5, 10, 0, tzinfo=FUSO)


def E(texto, agora=a):
    return extrair(texto, agora, agora, ConfigAgenda())
```

**1. ALTO — data explícita inválida é substituída por hoje**

Local: `src/ia_atendimento/agenda_extrator.py:421`, com fallback em `:492`.
Problema: `31/11 às 15h` e `29/02/2027 às 15h` retornam **05/11/2026 15:00, alta, válido**, origem `15h`. A data inválida é consumida e descartada; a ausência posterior de dia autoriza inferir hoje. O cliente forneceu um dia, portanto essa inferência inventa uma data diferente.
Correção: registrar data explícita inválida e devolver recusa; impedir o fallback de dia nesse estado.
Teste que reprova hoje:
```python
assert not E("31/11 às 15h").candidatos
```

**2. ALTO — reconhecimento parcial apaga minutos e atravessa fronteiras**

Local: `src/ia_atendimento/agenda_extrator.py:202`, acionado pelo fallback em `:370` após rejeição de outros formatos.
Problema: `hoje às 19:01:00` vira **19:00, alta, válido**; no sábado, `hoje às 12:30:00` vira **12:00, válido**. `às 15:99` vira 15:00; `às 15h e meia` vira 15:00; `às 15 e trinta e cinco` vira 15:30. Falta também limite de palavra: `às dozentas parcelas` vira **12:00 alta**, origem `às doze`. Expressões relativas compostas sofrem o mesmo corte: `daqui a uma hora e quinze minutos` vira 11:00, não 11:15.
Correção: reconhecer a expressão temporal inteira, delimitar numerais e impedir reaproveitamento de prefixos de formatos inválidos ou incompletos. Se a construção não for suportada, recusar integralmente.
Teste que reprova hoje:
```python
assert not E("hoje às 19:01:00").validos
```

**3. ALTO — alternativa com minutos gera horário diferente do pedido**

Local: `src/ia_atendimento/agenda_extrator.py:191`, com consumo prioritário em `:354`.
Problema: `às 15h ou 16:30` produz **15:00 e 16:00**. `_R_OU` aceita a segunda hora sem consumir `:30`, ocupa o trecho e impede o reconhecedor completo. Ambos ficam em média, mas 16:00 não é uma alternativa oferecida pelo cliente.
Correção: cada lado da alternativa deve usar a gramática completa de hora, preservando minutos; rejeitar uma alternativa incompleta antes de ocupar o texto.
Teste que reprova hoje:
```python
assert [c.quando.strftime("%H:%M") for c in E("às 15h ou 16:30").candidatos] == ["15:00", "16:30"]
```

**4. ALTO — qualificador de período transforma aproximação em alta**

Local: `src/ia_atendimento/agenda_extrator.py:302` e `:304`, chamados por `:359`.
Problema: `umas 3 da tarde` retorna **15:00 alta**. O reconhecedor passa `forte=False` por causa de `umas`, mas `_resolver` sobrescreve essa incerteza ao resolver tarde/manhã. Viola “ambíguo nunca alta”; saber o período não elimina a aproximação.
Correção: preservar a confiança reduzida independentemente do qualificador de período.
Teste que reprova hoje:
```python
assert all(c.confianca != "alta" for c in E("umas 3 da tarde").candidatos)
```

**5. ALTO — hora relativa ignora dia explícito e elimina ambiguidade**

Local: `src/ia_atendimento/agenda_extrator.py:487`.
Problema: `amanhã daqui a 1 hora` retorna **hoje 11:00 alta**. `hoje ou amanhã daqui a 1 hora` também devolve apenas hoje 11:00 alta: `_par` ignora todos os dias quando encontra `hora.fixo`; a deduplicação posterior apaga o conflito.
Correção: confrontar a data calculada com os dias explícitos e recusar contradições ou preservar a ambiguidade antes de deduplicar.
Teste que reprova hoje:
```python
assert all(c.confianca != "alta" for c in E("hoje ou amanhã daqui a 1 hora").candidatos)
```

**6. ALTO — truncamento de segundos permite menos de dez minutos**

Local: `src/ia_atendimento/agenda_extrator.py:531`; comparação em `:467`.
Problema: com agora **10:00:59**, `hoje às 10:10` é válido e alta, embora a antecedência real seja **541 segundos**, inferior aos 600 exigidos. O código trunca `agora` antes da validação. Também antecipa relativos: `daqui a 1 hora` nesse instante vira 11:00 em vez da próxima grade, 11:05.
Correção: preservar segundos e microssegundos de agora; arredondar somente o alvo relativo para cima, depois de somar a duração completa.
Teste que reprova hoje:
```python
assert "antecedencia" in E("hoje às 10:10", a.replace(second=59)).candidatos[0].razoes
```

**7. ALTO — quantidade de parcelas vira hora explícita**

Local: `src/ia_atendimento/agenda_extrator.py:189`.
Problema: `tenho entre 15 e 16 parcelas` produz candidatos válidos às **15:00 e 16:00**, com origem `entre 15 e 16`. `_R_ENTRE` não aplica a exclusão de unidades não temporais existente em `_NAO_HORA`. A v1 cria horários mesmo sem uma hora no texto.
Correção: aplicar a exclusão de contexto quantitativo ao intervalo inteiro, antes de registrar qualquer extremo.
Teste que reprova hoje:
```python
assert not E("tenho entre 15 e 16 parcelas").candidatos
```

**8. MÉDIO — avanço de ano bissexto lança exceção não tratada**

Local: `src/ia_atendimento/agenda_extrator.py:397`.
Problema: com agora em **05/12/2028**, `29/02 às 15h` lança `ValueError: day is out of range for month`. O avanço para 2029 usa `replace` fora do `try`. A ocorrência depende do ano injetado; não foi reproduzida com datas de 2026.
Correção: validar novamente o dia ao avançar o ano e devolver recusa sem exceção.
Teste que reprova hoje:
```python
assert isinstance(E("29/02 às 15h", datetime(2028, 12, 5, 10, tzinfo=FUSO)), Resultado)
```

**9. MÉDIO — confiança de meio-dia contraria o gabarito do estudo**

Local: `src/ia_atendimento/agenda_extrator.py:353`; expectativa incorreta em `tests/corpus/gerar_agenda_frases.py:84` e `:353`.
Problema: M §2.3 determina confiança **média** para `meio-dia`, mas implementação e corpus exigem alta. A coincidência entre ambos esconde o desvio. A distinção afeta consumidores que usam alta para dispensar confirmação; B5.7c mantém a confirmação tácita desligada na v1.
Correção: rebaixar a confiança dessa construção e corrigir o gabarito do corpus.
Teste que reprova hoje:
```python
assert E("meio-dia").candidatos[0].confianca == "media"
```

**10. MÉDIO — meia-noite ignora minutos capturados**

Local: `src/ia_atendimento/agenda_extrator.py:351`.
Problema: `meia-noite e meia` retorna **06/11 00:00 alta**, em vez de 00:30. A regex captura `mn`, mas esse ramo fixa minuto zero. Ambos ficam fora da janela; ainda assim o candidato e a futura contraproposta partem de horário errado.
Correção: usar os minutos capturados também no ramo de meia-noite.
Teste que reprova hoje:
```python
assert E("meia-noite e meia").candidatos[0].quando.minute == 30
```

**11. MÉDIO — teste de aceite reutiliza hold-out usado no ajuste**

Local: `tests/test_agenda_extrator.py:80`; evidência em `tests/corpus/README.md:43` e `tests/corpus/gerar_agenda_frases.py:388`.
Problema: os casos `ho-251` e `ho-253` ensinaram correções e continuam marcados como hold-out. O README reconhece que **54/54 já não é cego**, mas o teste segue apresentando esse número como hold-out. A primeira rodada declarada, **52/54 = 96,3%**, já supera 95%; esta revisão não contesta esse resultado histórico, apenas a validade da medição atual como avaliação independente.
Correção: manter os casos expostos como regressão e criar pelo menos 30 novos casos independentes; congelar corpus, versão avaliada e resultado da primeira execução antes de qualquer ajuste.
Teste de independência que reprova hoje, após carregar `HOLDOUT` como no módulo de testes:
```python
assert not {"ho-251", "ho-253"} & {f["id"] for f in HOLDOUT}
```

Nos casos exercitados, toda `origem` é substring literal: ela é construída por fatiamento do próprio texto. O teste de origem em `tests/test_agenda_extrator.py:103` verifica essa propriedade estrutural, mas não prova que o candidato respeite a expressão inteira. O teste de ambiguidade em `:118` também deixa escapar ambiguidade perdida: só entra na verificação principal se a implementação já devolveu dois candidatos. Os itens 1–5 e 7 demonstram essas lacunas; a suíte completa depende da implementação e não é tautológica como um todo.

Conversão de parâmetros UTC/São Paulo, virada de dia, ausência de horário de verão em 2026, limites inclusivos de 19:00 e sábado 12:00, teto da última mensagem +23 h e feriados 02/11 e 20/11 se comportaram corretamente para entradas válidas. DATAPREV respeitou início inclusivo e fim exclusivo. O problema de fronteira do item 2 ocorre antes dessas validações, ao alterar a hora pedida.

Não foi comprovada ReDoS catastrófica: as entradas hostis próximas do limite de 1.000 caracteres terminaram em aproximadamente 1–57 ms; textos maiores são recusados. Isso não constitui prova de limite de CPU para toda entrada. A exceção confirmada está no item 8.

Nas 281 frases, a varredura por forma não encontrou CPF, telefone ou e-mail; a leitura não identificou nomes de clientes nem frase reconhecível de conversa real. O gerador e o README declaram material inventado; não há fonte independente para atestar a procedência de cada frase. Não há chamada de modelo neste módulo puro, portanto não foi identificado caminho em que o modelo escreva datas.

## Resposta do autor (30/10/2026)

Todos os 11 achados foram tratados (os 7 ALTOS pedidos mais os 4 MÉDIOS). Em cada um o caso que reprovava foi escrito primeiro (vermelho: 40 testes falhando),
depois a correção (verde: 318 passed). Commit das correções: `fix: extrator v1 — correções da revisão 1 (R1–R7)` (localizável por `git log --grep "revisão 1"`; o
corpus e os testes foram incluídos no mesmo commit). Regra aplicada: na dúvida o extrator recusa ou rebaixa a confiança, nunca aproxima.

| # | Correção | Teste / caso do corpus |
|---|---|---|
| 1 | Data explícita que não existe marca `data_invalida` e o dia não cai em «hoje»; recusa `candidatos=()`, `motivo_recusa='data_invalida'` | `test_r1_data_explicita_invalida_nao_vira_hoje`; corpus `31/11 às 15h`, `29/02/2027 às 15h` |
| 2 | Numerais com fronteira (`doze\b`), `FIMNUM` recusa `:`, `.`, `,` seguidos de dígito, resto «e trinta e cinco»/«ou 16:99» recusa; «15h e meia» e «uma hora e quinze minutos» passam a ser lidas inteiras; trecho só é consumido se o achado vale | `test_r2_*`; corpus `hoje às 19:01:00`, `às 15:99`, `às dozentas parcelas`, `daqui a uma hora e quinze minutos` |
| 3 | Cada lado de «X ou Y»/«entre X e Y» usa a hora completa (minutos); lado inválido derruba a alternativa toda (registro em lote) | `test_r3_*`; corpus `às 15h ou 16:30` |
| 4 | Parâmetro `aprox` separado: «umas», «depois das», alternativas nunca viram `alta`, com ou sem período | `test_r4_*`; corpus `umas 3 da tarde` |
| 5 | Hora relativa confrontada com os dias ditos: contradição ⇒ `dia_contraditorio`; ambiguidade preservada (`media`) | `test_r5_*`; corpus `hoje ou amanhã daqui a 1 hora`, `amanhã daqui a 1 hora` |
| 6 | `agora` não é mais truncado; relativo soma a duração inteira e só então sobe para a grade de 5 min | `test_r6_*` (10:00:59 → antecedência e 11:05) |
| 7 | Lista de quantidade (`parcelas`, `contratos`, `meses`, `pessoas`, `x`, `k`, `R$`...) aplicada também ao `entre X e Y`; `R$ N` nunca é hora | `test_r7_*` (13 frases); corpus `tenho entre 15 e 16 parcelas`, `12 parcelas`, `R$ 15`, `2 contratos` |
| 8 | 29/02 ao avançar o ano: `_data_com_mes` trata o `ValueError` e devolve `data_invalida` | `test_r8_ano_bissexto_...` |
| 9 | «meio-dia», «meio dia e meia» e «meia-noite» passam a `media` (gabarito do corpus corrigido) | `test_r9_meio_dia_e_media` |
| 10 | «meia-noite e meia» usa os minutos capturados (00:30 do dia seguinte) | `test_r10_...`; corpus idem |
| 11 | Os dois casos que ensinaram correção saíram do hold-out (`regressao`); 43 casos novos de hold-out v2 congelados antes das correções (1ª rodada 43/43); README do corpus registra v1 e v2 | `test_r11_holdout_nao_reutiliza_caso_que_ensinou_correcao` |

Provas de mutação das correções (todas reprovam): remover a recusa de data inválida (4 falhas), remover `aprox` (2), voltar a truncar segundos (1),
tirar a exclusão do dia explícito do relativo (2), tirar `contratos/propostas/pessoas` da lista de quantidade (4).
Limitação nova e deliberada: «às 10 e 15 parcelas» e «às 15 e 16» (lista sem «ou») agora recusam em vez de ler só o primeiro número.
