# Gasto de tokens — revisão completa da IA (planejamento)

Medido em 10/11/2026 13:46 BRT, somando o campo `usage` de cada mensagem dos registros de agente em disco (`subagents/workflows/<run>/agent-*.jsonl`) e da sessão principal. Script: `~/ia-revisao-0911/scripts/custo.py` na S3.

**Escopo:** só o planejamento e a revisão (críticas do plano, Fases 0 a 3). Desenvolvimento ainda não começou e terá tabela própria.

**Como ler:**
- **Entrada**: tokens novos enviados ao modelo, sem cache.
- **Cache escrita**: contexto gravado no cache do prompt (cobrado um pouco acima da entrada).
- **Cache leitura**: contexto reaproveitado do cache (cobrado a uma fração da entrada). É a maior parte porque cada agente relê o próprio histórico a cada passo.
- **Saída**: o que os modelos escreveram.
- A coluna «Agentes» conta arquivos de registro do workflow inteiro; ela se repete em cada linha de modelo da mesma etapa.
- Linhas `<synthetic>` são mensagens internas sem custo.
- A Fase 3b ainda tinha cerca de 10 agentes rodando no momento da medição. Faltam as Fases 4 e 5.
- O limite do Fable acabou às ~13:00 de 10/11; daí em diante os votos sem modelo fixo rodaram em Opus 5.5.

| Etapa | Modelo | Agentes | Entrada | Cache escrita | Cache leitura | Saída | Total |
|---|---|---|---|---|---|---|---|
| Plano: crítica v1 (4 críticos) | claude-sonnet-5-5 | 4 | 268 | 681.265 | 19.272.324 | 146.050 | 20.099.907 |
| Plano: crítica v2 (3 críticos) | claude-fable-5-1 | 3 | 1.032 | 628.931 | 5.286.504 | 114.754 | 6.031.221 |
| Fase 0: base e unidades | claude-fable-5-2 | 9 | 120 | 1.096.574 | 8.505.368 | 313.133 | 9.915.195 |
| Fase 0: base e unidades | claude-opus-5-5 | 9 | 30 | 203.547 | 2.495.360 | 115.239 | 2.814.176 |
| Fase 0: base e unidades | claude-sonnet-5-5 | 9 | 166 | 604.760 | 12.879.438 | 102.927 | 13.587.291 |
| Fases 1, 2, 2b: leitores | claude-fable-5-2 | 119 | 1.264 | 11.907.496 | 93.613.905 | 1.906.088 | 107.428.753 |
| Fases 1, 2, 2b: leitores | claude-opus-5-5 | 119 | 158 | 911.424 | 10.477.660 | 134.307 | 11.523.549 |
| Fases 1, 2, 2b: leitores | claude-sonnet-5-5 | 119 | 1.624 | 8.147.771 | 96.864.309 | 1.441.662 | 106.455.366 |
| Fase 3a: fusão | claude-fable-5-2 | 20 | 18 | 278.385 | 1.277.060 | 28.826 | 1.584.289 |
| Fase 3a: fusão | claude-sonnet-5-5 | 20 | 108 | 1.426.912 | 3.007.125 | 87.601 | 4.521.746 |
| Fase 3b: verificação graves | <synthetic> | 954 | 0 | 0 | 0 | 0 | 0 |
| Fase 3b: verificação graves | claude-fable-5-2 | 954 | 3.718 | 28.134.249 | 143.826.577 | 1.846.139 | 173.810.683 |
| Fase 3b: verificação graves | claude-opus-5-5 | 954 | 4.918 | 23.821.239 | 178.118.267 | 1.397.952 | 203.342.376 |
| Fase 3b: verificação graves | claude-sonnet-5-5 | 954 | 3.416 | 16.367.281 | 110.399.964 | 782.274 | 127.552.935 |
| Fase 3c: verificação restrições | <synthetic> | 631 | 0 | 0 | 0 | 0 | 0 |
| Fase 3c: verificação restrições | claude-fable-5-2 | 631 | 2.290 | 16.552.549 | 81.361.640 | 911.715 | 98.828.194 |
| Fase 3c: verificação restrições | claude-opus-5-5 | 631 | 4.534 | 23.151.992 | 157.086.812 | 1.141.945 | 181.385.283 |
| Fase 3d: verificação médios | <synthetic> | 255 | 0 | 0 | 0 | 0 | 0 |
| Fase 3d: verificação médios | claude-fable-5-2 | 255 | 2.292 | 15.688.803 | 85.229.136 | 900.410 | 101.820.641 |
| Fase 3d: verificação médios | claude-sonnet-5-5 | 255 | 214 | 1.042.444 | 6.370.601 | 35.180 | 7.448.439 |
| Sessão principal (orquestração) | <synthetic> | 2 | 0 | 0 | 0 | 0 | 0 |
| Sessão principal (orquestração) | claude-fable-5-1 | 2 | 302 | 511.881 | 2.038.328 | 20.417 | 2.570.928 |
| Sessão principal (orquestração) | claude-fable-5-2 | 2 | 138 | 495.756 | 9.630.398 | 61.436 | 10.187.728 |
| Sessão principal (orquestração) | claude-opus-5-5 | 2 | 36 | 245.361 | 3.708.138 | 12.143 | 3.965.678 |
| **Total** | | | 26.646 | 151.898.620 | 1.031.448.914 | 11.500.198 | **1.194.874.378** |

## Resumo

| Grupo | Total de tokens |
|---|---|
| Crítica do plano (v1 e v2) | 26,1 milhões |
| Fase 0 | 26,3 milhões |
| Leitores (Fases 1, 2, 2b) | 225,4 milhões |
| Fusão | 6,1 milhões |
| Verificação (Fase 3b, 3c, 3d) | 890,7 milhões |
| Sessão principal | 16,4 milhões |

Saída escrita pelos modelos no total: 11,5 milhões de tokens. Cerca de 86 % do total é leitura de cache.
