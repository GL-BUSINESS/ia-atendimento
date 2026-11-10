# Gasto de tokens — revisão completa da IA (planejamento)

Medido em 10/11/2026 15:06 BRT, com a revisão concluída (Fases 0 a 5). Soma do campo `usage` de cada mensagem nos registros dos agentes (`subagents/workflows/<run>/agent-*.jsonl`) e da sessão principal. Script: `~/ia-revisao-0911/scripts/custo.py` na S3.

**Escopo:** só planejamento e revisão. O desenvolvimento terá tabela própria, com o mesmo script.

## Resumo

| Etapa | Tokens |
|---|---|
| Verificação adversarial (Fase 3b, 3c, 3d) | 1.138,3 milhões |
| Leitores (Fases 1, 2, 2b) | 225,4 milhões |
| Fase 4, completude (2 rodadas) | 79,1 milhões |
| Sessão principal (orquestração) | 44,1 milhões |
| Fase 5, síntese | 41,4 milhões |
| Fase 0 | 26,3 milhões |
| Crítica do plano, v1 e v2 | 26,1 milhões |
| Fusão | 6,1 milhões |
| **Total** | **1.586,7 milhões** |

- 87 % do total é releitura de cache. O texto escrito pelos modelos somou 14,2 milhões de tokens.
- A verificação pesou mais por dois motivos: cerca de 1.800 votos que releem código e papel, e a troca de modelo às 13:00 de 10/11. Quando o limite do Fable acabou, a sessão passou a Opus 5.5 e a retomada refez em Opus parte dos votos já feitos em Fable.
- Lição para a próxima rodada: fixar o modelo de cada agente no script (`model`), para que uma troca de modelo da sessão não invalide o cache da retomada.

## Como ler a tabela detalhada

- **Entrada**: tokens novos enviados ao modelo, sem cache.
- **Cache escrita**: contexto gravado no cache do prompt.
- **Cache leitura**: contexto reaproveitado do cache, cobrado a uma fração da entrada.
- **Saída**: o que os modelos escreveram.
- «Agentes» conta arquivos de registro do workflow inteiro e se repete em cada linha de modelo da mesma etapa. Linhas `<synthetic>` são mensagens internas sem custo.

## Tabela detalhada

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
| Fase 3b: verificação graves | <synthetic> | 1398 | 0 | 0 | 0 | 0 | 0 |
| Fase 3b: verificação graves | claude-fable-5-2 | 1398 | 3.718 | 28.134.249 | 143.826.577 | 1.846.139 | 173.810.683 |
| Fase 3b: verificação graves | claude-opus-5-5 | 1398 | 9.140 | 44.608.298 | 329.024.539 | 2.664.931 | 376.306.908 |
| Fase 3b: verificação graves | claude-sonnet-5-5 | 1398 | 5.330 | 25.690.054 | 171.769.983 | 1.207.145 | 198.672.512 |
| Fase 3c: verificação restrições | <synthetic> | 631 | 0 | 0 | 0 | 0 | 0 |
| Fase 3c: verificação restrições | claude-fable-5-2 | 631 | 2.290 | 16.552.549 | 81.361.640 | 911.715 | 98.828.194 |
| Fase 3c: verificação restrições | claude-opus-5-5 | 631 | 4.534 | 23.151.992 | 157.086.812 | 1.141.945 | 181.385.283 |
| Fase 3d: verificação médios | <synthetic> | 255 | 0 | 0 | 0 | 0 | 0 |
| Fase 3d: verificação médios | claude-fable-5-2 | 255 | 2.292 | 15.688.803 | 85.229.136 | 900.410 | 101.820.641 |
| Fase 3d: verificação médios | claude-sonnet-5-5 | 255 | 214 | 1.042.444 | 6.370.601 | 35.180 | 7.448.439 |
| Fase 4: completude, rodada 1 | claude-opus-5-5 | 64 | 962 | 4.713.180 | 42.441.239 | 344.353 | 47.499.734 |
| Fase 4: pontos cegos, rodada 2 | claude-opus-5-5 | 38 | 580 | 3.191.330 | 28.105.659 | 254.242 | 31.551.811 |
| Fase 5: síntese | claude-opus-5-5 | 9 | 532 | 1.754.351 | 39.254.620 | 343.340 | 41.352.843 |
| Sessão principal (orquestração) | <synthetic> | 2 | 0 | 0 | 0 | 0 | 0 |
| Sessão principal (orquestração) | claude-fable-5-1 | 2 | 302 | 511.881 | 2.038.328 | 20.417 | 2.570.928 |
| Sessão principal (orquestração) | claude-fable-5-2 | 2 | 138 | 495.756 | 9.630.398 | 61.436 | 10.187.728 |
| Sessão principal (orquestração) | claude-opus-5-5 | 2 | 200 | 682.711 | 30.544.527 | 91.618 | 31.319.056 |
| **Total** | | | 35.020 | 192.104.663 | 1.380.363.112 | 14.213.458 | **1.586.716.253** |
