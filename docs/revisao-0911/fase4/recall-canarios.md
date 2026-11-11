# Recall dos canários (fase 4)

Fontes: `fase0/canarios-gabarito.txt`, `fase0/canario-N.arquivos`, `fase3/canarios-achados.json` (F2-C1..F2-C4 = canario-1..4),
`src/ia-atendimento/docs/REVISAO-B5.1-0411.md`, `REVISAO-B1.8-0411.md`, `REVISAO-B1.4-0311-r2.md`, e o diff canario-N x main dos
arquivos lidos (`scripts/fase4-recall-1.sh`, `-2.sh`, `-3.sh`).

Critério: **sim** = o achado descreve o mesmo defeito (mesmo mecanismo e mesmo efeito); **em parte** = pega o mecanismo vizinho ou só
parte do efeito; **não** = nenhum achado. Recall ponderado conta «em parte» como 0,5. «Fora do alcance» = o defeito está em arquivo que a
unidade não recebeu (testes ou documento), marcado para o recall alcançável.

## canario-1 (pai de d0ddcb4; B5.1: A-1, M-1..M-4, M-6, M-7, B-1..B-4) — 5 arquivos de `ferramentas/`, sem testes

| Defeito (doc) | O que é | Reencontrado? | Achado do leitor |
|---|---|---|---|
| A-1 (ALTO) | destino resolvido antes da fila do limitador e da leitura do CPF; parada dura não alcança a T7 que espera vaga (`gateway.py:223`, `:303`, `:325`) | **sim** | «Destino e pré-condições valem na hora de entrar na fila, não na hora do efeito» (ALTO; mesma sonda: T7 atrás de duas T8, modo muda na espera) |
| M-1 | síncronas concorrentes furam o teto de 4 (`cabe()` antes, débito depois do executor) | **sim** | «Orçamento por turno/atendimento não é atômico: chamadas paralelas do modelo o furam» (ALTO; mesma correção: reservar antes do `await`) |
| M-2 | timeout não cobre a espera do semáforo; timeout na fila não pode virar `INDETERMINADO` | **sim** | «Fila do limitador por serviço não tem prazo» (inclui «nunca INDETERMINADO se o efeito não saiu») |
| M-3 | `CORRIGIVEL` levantado pelo executor não conta no teto de 3; paga conta só sucesso | **em parte** | o achado do orçamento cita «o contador só sobe em sucesso: erro/timeout de uma leitura paga não conta» (metade da paga); o caminho do `CORRIGIVEL` tipado não aparece |
| M-4 | erro tipado do executor reaproveitado: `__context__` com a exceção original (PII na mensagem) e traceback com o CPF | **em parte** | «Traceback de ErroDeFerramenta devolvido pelo executor mantém Chamada (e o CPF) vivos» (BAIXO; viu o traceback e a retenção, não o `__context__` com PII; classificou como «retenção, não vazamento») |
| M-6 | `reconstruir` não varre conteúdo; `Resultado.dados` e o mapa de apelidos aceitam CPF em campo permitido | **não** | (vizinho sem acerto: «_varrer descarta em silêncio campo...», que olha o caminho do modelo, o único que já varria) |
| M-7 | FACTA leitura (T8/T9) com posse real sob parada dura cai no simulador e responde `nao_criada` | **não** | — |
| B-1 | regra «campo proibido» sem teste para `do_modelo=False` | **não** (fora do alcance: teste) | — |
| B-2 | teste de PII em campo permitido só usa URL | **não** (fora do alcance: teste) | — |
| B-3 | teste da pré-condição assíncrona não prova aceitação | **não** (fora do alcance: teste) | — |
| B-4 | chamada recusada na entrada (fora do catálogo / não é do modelo) não vai ao registro nem ao span | **não** | (vizinho: «Exceção do resolvedor de referências ou do leitor de modo escapa de Gateway.chamar sem registro», outro caminho) |

Recall: estrito 3/11 = 27%; ponderado 4/11 = 36%. Alcançável (sem B-1..B-3): estrito 3/8 = 38%; ponderado 4/8 = 50%.

## canario-2 (pai de 34fafcf; B1.8 R-01) — `agenda_extrator.py`, `agendamento.py`

| Defeito | O que é | Reencontrado? | Achado do leitor |
|---|---|---|---|
| R-01 (MÉDIO) | `config_da_agenda` não passa `janela_mensagem.dias`; a agenda reserva volta fora do horário de envio do dia (fim exclusivo no calendário) | **sim** | «Janela do extrator não é cruzada com janela_mensagem.dias do calendário» (cita `agendamento.py:119-127`, a mesma linha do doc, e o fim inclusivo x exclusivo, que a correção adotou) |

Recall: 1/1 = 100%.

## canario-3 (pai de a30fd2c; B1.4-r2 R2-07, R2-08) — `mascara.py`, `modulos_fase.py`, `protecao.py`

| Defeito | O que é | Reencontrado? | Achado do leitor |
|---|---|---|---|
| R2-07a | `mascarar` troca `dd/mm hh:mm` (8 dígitos) por `[NUMERO]`: data e hora do agendamento somem | **não** | (o leitor olhou a isenção de data no sentido oposto: «mascarar isenta data dd/mm/aaaa: data de nascimento fica em claro») |
| R2-07b | o extrator de agenda instruído a ler o texto de `proteger_texto`, não o de `mascarar` | **não** (fora do alcance: texto de contrato/estudo; o diff dos 3 arquivos não o contém e `agenda_extrator.py` não cita nenhum dos dois) | — |
| R2-08a | `[NUMERO]` opaco perde a grandeza (valor x parcela x prazo); correção `[NUMERO:n]` e a frase no SISTEMA | **não** | — |
| R2-08b | lista branca de hora sem `15hrs`, `15hs`, `15h30min` | **não** | — |

Recall: 0/4 = 0% (alcançável 0/3).

## canario-4 (pai de 35d22cf; B1.4-r2 R2-02, A1f) — `agente.py`, `ferramentas.py`

| Defeito | O que é | Reencontrado? | Achado do leitor |
|---|---|---|---|
| R2-02 | exceção qualquer da ferramenta escapa crua de `executar_turno` (não é `ErroDoModelo`, não conta falha, perde o gasto, mensagem pode citar PII); `httpx.HTTPError` sai com rótulo de provedor | **sim** | «Exceção de ferramenta fora da lista escapa crua, sem contar falha do turno» (ALTO; mesma correção: capturar `Exception` em `wrap_tool_execute`) + «Falha de rede da ferramenta é rotulada como falha do provedor» (a nota do rótulo errado no doc) |
| A1f | texto fixo do `ToolFailed` sem teste (mutante sobrevive) | **não** (fora do alcance: teste) | — |

Recall: 1/2 = 50% (alcançável 1/1 = 100%).

## Total

| | defeitos | sim | em parte | não | estrito | ponderado |
|---|---|---|---|---|---|---|
| todos | 18 | 5 | 2 | 11 | 28% | 33% |
| alcançáveis (sem 4 lacunas de teste e o R2-07b de contrato) | 13 | 5 | 2 | 6 | 38% | 46% |

Por gravidade do doc: o único ALTO (A-1) foi achado; a exceção que escapa (R2-02) também, e foi o achado ALTO da unidade.

## O que os leitores deixam passar

1. **Lacunas de teste (4/18: B-1, B-2, B-3, A1f).** As unidades receberam só código de produção; mutante sobrevivente é invisível a
   quem não lê os testes. Não é falha do leitor, é do recorte: se a revisão quer pegar isso, a unidade precisa do arquivo de teste.
2. **Excesso de máscara que quebra função (4/18: R2-07a, R2-08a, R2-08b, e o R2-07b).** Os leitores da máscara caçam vazamento (falso
   negativo: NFD, CPF partido, data em claro, nome curto) e não perguntam o que a máscara destrói (hora, data com hora, grandeza do número).
   Zero de quatro no canário da máscara, com oito achados entregues, todos do lado do vazamento ou de prompt.
3. **Regra que vem de tabela de contrato, não do código (M-7).** A T8 com posse real sob parada dura no simulador só é defeito à luz da
   «Tabela final» de 08 §6; sem o contrato ao lado, o `interceptado` parece correto.
4. **Caminho do dado que não vai ao modelo (M-6).** O leitor viu a varredura de `para_projetar` e concluiu pelo caminho do modelo; não seguiu
   `Resultado.dados` até quem o grava depois (B1.6).
5. **Caminho alternativo de controle por exceção (M-3, M-4 em parte).** O mesmo resultado chegando por `raise` em vez de `return` (o
   `CORRIGIVEL` tipado) e o encadeamento implícito de exceções (`__context__`) ficam meio vistos: o leitor achou o traceback, não a causa.
6. **Observabilidade de recusa (B-4).** Chamada recusada sem registro não foi vista; um achado vizinho tratou outra exceção sem registro.

O que eles pegam bem: concorrência e ordem de `await` (A-1, M-1, M-2), costura entre módulos (R-01) e exceção que escapa (R2-02), em
geral com a mesma correção que entrou na main.

Limites desta medida: a precisão (achados extras fora do gabarito) não foi medida; o diff contra a main inclui mudanças posteriores ao
commit de correção, separadas aqui pelo texto dos docs de revisão.
