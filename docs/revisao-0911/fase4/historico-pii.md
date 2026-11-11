# Varredura de histórico git (F4-036), 10/11/2026 ~14:40

Feita na sessão principal, só leitura, nos clones locais em ~/repos (todas as refs, `git log --all -p`). Nenhum valor exibido: só forma e contagem.

## gitleaks (regras padrão + config do próprio repositório), `--redact`

| Repositório | Achados | Leitura |
|---|---|---|
| gl-gateway | 0 | limpo |
| ia-atendimento | 1 | `generic-api-key` em `tests/test_boot_real.py:109` (texto de log de teste) — falso positivo |
| bancos-duble | 78 | regra `cpf-formatado` do repo em `personas/`; todos os 171 números têm prefixo 000 (sintéticos pela regra do projeto) |
| facta-on | 4 | tokens de teste e um `.env.example` com valor vazio (gitleaks pegou a linha seguinte) — falsos positivos |
| cliente360-api | 15 | tokens sintéticos de teste, ids no CHANGELOG, nome de papel num rig de teste — falsos positivos |

Nenhum segredo real encontrado no histórico.

## CPF de dígito verificador válido, fora do prefixo 000 (regra própria; DV calculado)

| Repositório | Distintos no histórico | Exemplos públicos conhecidos | Outros | Ainda na main (não públicos) |
|---|---|---|---|---|
| ia-atendimento | 6 | 5 | 1 (`tests/test_mascara.py`, só no histórico) | 0 |
| bancos-duble | 1 | 1 | 0 | 0 |
| gl-gateway | 0 | 0 | 0 | 0 |
| facta-on | 36 | 5 | 31 | **29** |

No `facta-on`, os não públicos estão sobretudo em `tests/amostras/consulta_fato_lote_20261104.jsonl` (9), `app/routers/online.py` (7), `tests/test_margem_facta.py` (6), `tests/test_motivo_cancelamento.py`, `app/margem.py`, `tests/test_selecao_taxa_minima.py`. A forma não diz se são CPFs de pessoas reais ou gerados com DV válido; o nome «amostras/…lote_20261104» e os comentários «caso real» (G-0118) indicam origem em produção. **Reforça G-0118 (ALTO, RS-13): precisa de decisão do dono e de limpeza de histórico se forem reais.**
