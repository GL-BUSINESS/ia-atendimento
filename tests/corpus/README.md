# Corpus do extrator de horário (B5.7a)

`agenda_frases.jsonl` = uma frase por linha. É o gabarito de `tests/test_agenda_extrator.py` (EM1 do estudo M).

## Regras do corpus

- **Todas as frases são inventadas** (português do Brasil, estilo WhatsApp curto: sem acento, abreviações, emojis). Nenhuma foi copiada
  de conversa real. O corpus real do ChatGuru está proibido até o parecer jurídico (PD-6). Não acrescente frase real nem dado pessoal.
- O `esperado` é escrito **à mão** a partir da regra do estudo M, nunca calculado chamando o extrator. O gerador não importa nada de `src/`.

## Campos

| Campo | Significado |
|---|---|
| `id` | `dev-NNN` ou `ho-NNN` (hold-out) |
| `holdout` | `true`: escrito depois da gramática e **não** usado para ajustá-la (ver abaixo) |
| `tag` | categoria (`utc`, `sabado`, `domingo`, `feriado`, `dataprev`, `relativo`, `ambiguo`, `sem_hora`, `ruido`, `giria`, `teto`, `hora_passada`, `periodo`, `regressao`...) |
| `texto` | a frase do cliente |
| `agora` | ISO com fuso (`-03:00` ou `+00:00` para os casos de 22:30 UTC) |
| `ultima_msg` | ISO com fuso da última mensagem do cliente; `null` = igual a `agora` (o teto fica em `agora + 23 h`) |
| `usa_periodos` | `true` liga `ConfigAgenda.usa_periodos` (palavras de período viram candidato, nunca `alta`) |
| `esperado` | `quando` de TODOS os candidatos (ISO, BRT), em ordem cronológica, inclusive os marcados `fora_da_janela`; `[]` se nenhum |
| `confianca` | confiança de cada candidato, na mesma ordem |
| `motivo` | `motivo_recusa` esperado: `null` quando há ao menos um candidato que cabe; senão a razão de maior prioridade do 1º candidato (`feriado` > `bloqueio_dataprev` > `domingo` > `passado` > `antecedencia` > `antes_da_janela` > `depois_da_janela` > `acima_do_teto`) ou `sem_hora_explicita`, `dia_nao_resolvido`, `ambiguo_demais` |

Âncoras (2026, BRT): 05/11 quinta, 06/11 sexta, 07/11 sábado, 08/11 domingo, 09/11 segunda; feriados 02/11 e 20/11; bloqueio DATAPREV
20/11 22:00 até 23/11 06:00. O teto padrão é `min(ultima_msg + 23 h, próximo dia útil 19:00)`, por isso quase todo «amanhã» cedo demais já cai
em `acima_do_teto`: é a regra, e o corpus a exercita.

## Como gerar

```bash
python3 tests/corpus/gerar_agenda_frases.py     # reescreve agenda_frases.jsonl (determinístico)
uv run pytest tests/test_agenda_extrator.py -q
```

Para acrescentar um caso, edite `gerar_agenda_frases.py` (helpers `valido`, `fora`, `vazio`, `caso`) e gere de novo. Nunca edite o jsonl à mão.

## Hold-out

Os casos `holdout: true` (blocos «hold-out» do gerador) foram escritos **depois** de a gramática estar pronta e passando no conjunto de
desenvolvimento. O critério de aceite é acerto >= 95% neles (`test_holdout_acerto_minimo_de_95_por_cento`, que imprime o número).
Primeira rodada (antes de qualquer ajuste): 52/54 = 96,3%. As duas falhas eram bugs reais (minutos perdidos em «10h30 da manhã»; «dps das 4»
não reconhecido); foram corrigidas e viraram casos `regressao` no conjunto de desenvolvimento. A rodada seguinte (54/54) **já não é cega**:
para medir de novo com honestidade, acrescente casos novos de hold-out em vez de reaproveitar os antigos.
