# Linha de base de ferramentas (Fase 0, revisão 09/11)

Exportação em /home/danilo/ia-revisao-0911/src/ (não é repositório git). Somente leitura; testes e docker não foram executados. Relatórios brutos em /home/danilo/ia-revisao-0911/fase0/baseline/. Scripts em /home/danilo/ia-revisao-0911/scripts/baseline-*.sh. Tudo aqui são candidatos, não vereditos. Nenhum valor de segredo foi copiado.

## Ferramentas

| Ferramenta | Situação |
|---|---|
| gitleaks | presente, v8.30.1 (/home/danilo/bin/gitleaks) |
| semgrep | presente, v1.184.0 (~/.local/bin/semgrep) |
| uv | presente (~/.local/bin/uv) |
| python3 | presente (/usr/bin/python3) |

Adaptação: na v8.30.1 `gitleaks dir` não aceita `--no-git` (erro «unknown flag», rc=126 na primeira tentativa). `dir` já ignora o git, então rodou-se `gitleaks dir --redact --report-format json --report-path ...`.

## (a) gitleaks dir --redact

| Alvo | Achados | Relatório |
|---|---|---|
| src/ia-atendimento | 0 | gitleaks-ia-atendimento.json |
| src/ia-atendimento-b1-6a | 0 | gitleaks-ia-atendimento-b1-6a.json |
| src/ia-atendimento-esteira | 0 | gitleaks-ia-atendimento-esteira.json |
| src/ia-atendimento-kits-s4 | 0 | gitleaks-ia-atendimento-kits-s4.json |
| src/gl-gateway | 0 | gitleaks-gl-gateway.json |
| src/bancos-duble | 0 | gitleaks-bancos-duble.json |
| src/facta-on | 3 | gitleaks-facta-on.json |
| kits/ | 0 | gitleaks-kits.json |

### Candidatos em facta-on (3, todos regra generic-api-key, valores redigidos)

1. generic-api-key em src/facta-on/app/cliente360_ctx.py:54. O casamento é o texto de um comentário («a API, `...`; não é segredo») sobre o namespace do contrato v1. A linha 55 é um UUID v5 de namespace (identificador público de derivação, não credencial). Provável falso positivo: o próprio comentário o declara não-segredo. Vale confirmar no contrato que o namespace é de fato público.
2. generic-api-key em src/facta-on/tests/test_coeficientes_c360.py:40. Atribuição a uma constante chamada TOKEN_FALSO em arquivo de teste. Provável falso positivo: nome e local indicam valor de fixture.
3. generic-api-key em src/facta-on/tests/vetores/observacao_v1.json:209. Campo «token_do_fato» num vetor de teste do contrato (entropia 3,75, baixa para credencial real). Provável falso positivo: dado de vetor de teste, não token de autenticação; confirmar que o valor é sintético.

Nenhum dos três é confirmado como segredo. O gitleaks em modo dir não vê histórico, só o estado exportado.

## (b) semgrep (p/python, p/secrets, p/owasp-top-ten)

| Alvo | Resultado |
|---|---|
| src/ia-atendimento | Concluído: 0 achados, 220 regras sobre 156 arquivos, 0 erros (semgrep-ia-atendimento.json/.log). Ressalva: 91 arquivos foram pulados por padrões do .semgrepignore (o padrão do semgrep costuma excluir tests/ e similares), portanto testes e parte do restante ficaram sem varredura. |
| src/gl-gateway | FALHOU, sem varredura. «Failed to obtain target files from semgrep-core» (erro de semgrep-core, rc=2), repetido três vezes, inclusive com `--no-git-ignore`. Aparece também o aviso «semgrep-core rule validation failed (OtherParseError)», que ocorreu mesmo na varredura de ia-atendimento que terminou bem. Não parece ser rede: as regras do registro foram baixadas no outro alvo. Causa não investigada (leitura apenas). Registros: semgrep-gl-gateway.json/.log. |

Consequência: gl-gateway não tem linha de base de semgrep. Cobertura estática dele nesta fase fica só com gitleaks (0 achados). Sugestão para fase posterior: tentar `--verbose` ou apontar para subpastas de gl-gateway para achar o arquivo/estrutura que derruba o semgrep-core, ou usar outra ferramenta (ex.: bandit) se disponível.

## Resumo

- gitleaks: 3 candidatos, todos em facta-on, todos com cara de falso positivo (comentário, constante de teste, vetor de teste). Demais repos e kits: 0.
- semgrep: ia-atendimento 0 achados (com 91 arquivos ignorados); gl-gateway não rodou por falha do semgrep-core.
