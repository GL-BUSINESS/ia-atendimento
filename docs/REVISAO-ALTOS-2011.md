# Revisão independente — correção dos ALTO da revisão 0911 (20/11/2026)

Ramo `fix/altos-revisao-2011`, por cima de `fix/testes-relogio-2011` (PR #17). Quem revisou: um agente revisor de contexto limpo (Claude),
que não escreveu o código. Só leitura, `git diff`, `ruff` e chamadas diretas ao extrator; sem pytest. Base da revisão:
`origin/fix/testes-relogio-2011..1333de2`.

**Resultado:** nenhum CRÍTICO nem ALTO. Cinco MÉDIO e sete BAIXO. Os testes novos reprovam no código da base.

## Por achado da revisão 0911

| Achado | Resolve o cenário? | Teste reprova antes? |
|---|---|---|
| G-0085 | Sim para PII; segredos só em parte (M3, corrigido) | Sim |
| R2-001 | Sim | Sim |
| G-0119 | Sim (sem 422, sem eco, sem epoch); dedupe do retry fraco (M1, corrigido) | Sim |
| G-0121 | Sim | Sim |
| G-0122 | Sim (hex minúsculo) | Sim |
| G-0125 | Sim no esquema; a projeção fail-closed ainda não tem chamador (B5.2) | Sim |
| G-0090 | Sim para espaço; vírgula (M5, corrigido) | Sim |
| F4-009 / F4-010 | Sim | Sim |
| G-0097 | Só a documentação deste repositório e a mensagem (B7) | Sim |
| DEC-PIA-011 item 4 | Sim: calendário, extrator, corpus e job mensal | Sim |
| DEC-PIA-005/014 | Função correta, não ligada (M2) | Testa a função |

## Achados e destino

| Id | Sev. | Achado | Destino |
|---|---|---|---|
| M1 | MÉDIO | Post com hora inválida: a chave caía no recebimento (microssegundos) e o retry virava mensagem duplicada | **Corrigido**: a hora crua, com tipo e texto, entra na chave (`mensagem_id` só no HMAC, nunca gravado); teste do retry `repetido` |
| M2 | MÉDIO | `competencia.py` e `saida_t1_do_resumo` sem chamador; `criada_em` pode não ser o campo certo da competência (há `business_date`, `competencia_inicio`) | **Aberto, escrito no PR**: biblioteca pronta, a T3/T1 da B5.2 tem de chamar. Campo da competência: confirmar com o dono |
| M3 | MÉDIO | Só a chave do modelo e a do Phoenix viravam `[SEGREDO]` | **Corrigido**: tokens, chaves HMAC, `chat_ref`, senha do banco e os arquivos 0600 (gateway, saída) |
| M3c | ALTO (achado ao corrigir M3) | `mascarar_texto` passava a máscara de PII ANTES dos segredos: um segredo com 8+ dígitos tinha os dígitos trocados (`[TELEFONE]`) e o resto saía em claro | **Corrigido**: segredos primeiro, do mais longo ao mais curto; o teste de boot pega o token |
| M3b | — | Com `PHOENIX_ENDPOINT` definido, os spans passam a sair (mascarados) | **Aviso de implantação**: conferir o ambiente da S5 antes de subir |
| M4 | MÉDIO | O Post real do teste perdeu `celular` e `nome` (comentário colado na linha) | **Corrigido**, com `len(post_real()) == 22` |
| M5 | MÉDIO | «às 16, 17 também serve» saía 16:00 alta (já existia) | **Corrigido**: vírgula e ponto e vírgula antes do número solto |
| B1 | BAIXO | Job da DATAPREV com o relógio do worker atrás do banco concluía sem fechar | **Corrigido**: folga de 2 min |
| B2 | BAIXO | «às 15 2 pessoas», «às 15 2ª feira» viram `hora_incompleta` | Aceito: é o lado seguro (repasse) |
| B3 | BAIXO | `datetime_post_invalido` contava Post descartado ou recusado | **Corrigido**: conta só o gravado |
| B4 | BAIXO | `IndexError` acima de 26 pendentes em `Insumos` montado à mão | **Corrigido**: rótulo só de letras (aa, ab…) |
| B5 | BAIXO | Matrícula: cofre de 7 dias; retry com outra matrícula é descartado | Registro: a T7 (B5.4) falha alto sem a matrícula; o descarte no replay é intencional |
| B6 | BAIXO | Sha256 em maiúsculas segue 422 | Aceito: o 04 manda `hexdigest()` |
| B7 | BAIXO | `DEPLOY.md` da esteira ainda diz 640 | Fora do escopo (frente da esteira); a regra está na OPERACAO §2/§8 |
