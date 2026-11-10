# Revisão 0911 — Fase 4, rodada 2 (pontos cegos) consolidada

23 achados novos verificados (5 passes dirigidos: máscara que destrói função, regra só no contrato, dado persistido, teste que não reprova, costuras de entrada).

| Estado | CRÍTICO | ALTO | MÉDIO | BAIXO |
|---|---|---|---|---|
| confirmado | 0 | 1 | 8 | 2 |
| confirmado em parte | 0 | 0 | 7 | 5 |
## Achados novos (vivos), por gravidade

| Id | Gravidade | Estado | Unidade | Título | Onde |
|---|---|---|---|---|---|
| R2-001 | ALTO | confirmado | P1 | Pendente que começa com 'dd/mm hh:mm' derruba o turno no auditar_prompt (prefixo '1. «' cola na cadeia de dígitos) | src/ia-atendimento/src/ia_atendimento/contexto.py:266,316; mascara.py:50,145 |
| R2-002 | MEDIO | confirmado em parte | P1 | Formas comuns de data/hora ainda viram [NUMERO] na gravação (isenção só cobre 'dd/mm[ ,]+hh:mm') | src/ia-atendimento/src/ia_atendimento/mascara.py:47,135-149; conversa.py:128 |
| R2-004 | MEDIO | confirmado | P1 | Regra '[NUMERO:2] = prazo' e _PRAZO amplo empurram hora nua e quantidades para prazo | src/ia-atendimento/src/ia_atendimento/modulos_fase.py:35; protecao.py:63,71-78 |
| R2-005 | MEDIO | confirmado | P1 | Parte do nome que é palavra comum (Dias, Graça, Socorro, Filho) apaga a palavra e quebra o 'fica' de duração | src/ia-atendimento/src/ia_atendimento/mascara.py:163-189; protecao.py:137,141 |
| R2-008 | MEDIO | confirmado | P2 | T8 (leitura local do facta-on, até 1500 s) segura as 2 vagas do limitador da FACTA e bloqueia T5/T7/T9 de todos os atendimentos | src/ia-atendimento/src/ia_atendimento/ferramentas/catalogo.py:177-181; ferramentas/gateway.py:61,334-340 |
| R2-009 | MEDIO | confirmado em parte | P2 | SaidaT8.estado não comporta os vereditos do 05 §2.1 B (falta recusa_politica e aguardando_status; usa nao_criada em vez de nada_criado) | src/ia-atendimento/src/ia_atendimento/ferramentas/esquemas.py:170-172 |
| R2-010 | MEDIO | confirmado em parte | P2 | Timeout da T8 no prazo vira BANCO_INDISPONIVEL (código de repetir), quando o contrato manda indeterminado com repasse e nota | src/ia-atendimento/src/ia_atendimento/ferramentas/gateway.py:343-344 |
| R2-011 | MEDIO | confirmado | P2 | posse_real sem produtor na main: padrão False em Deps e ContextoDaChamada; sob parada dura em duble, o atendimento real vai à fixture | src/ia-atendimento/src/ia_atendimento/ferramentas/projecao.py:59; ferramentas/gateway.py:78; ferramentas/modo.py:170-174 |
| R2-012 | MEDIO | confirmado em parte | P2 | T7 com posse real sob parada dura cai no simulador; o contrato manda barrar | src/ia-atendimento/src/ia_atendimento/ferramentas/modo.py:157-164 |
| R2-013 | MEDIO | confirmado em parte | P2 | CancelledError depois do disparo da T7 não vira INDETERMINADO nem gera registro | src/ia-atendimento/src/ia_atendimento/ferramentas/gateway.py:338-346,233 |
| R2-015 | MEDIO | confirmado | P3 | Anotação do operador grava nome e texto livre sobre o cliente em claro por 365 d: a API desliga a cerca de nomes passando nomes=() | src/ia-atendimento/src/ia_atendimento/api/anotacoes.py:83-85 -> passos.py:273-279,410 -> linha_tempo.py:184-187 -> ia.passo.texto |
| R2-016 | MEDIO | confirmado | P3 | Ledger b1-6a grava Desfecho.ref_externa sem a varredura de PII do gateway; valor fora do CHECK sobe CheckViolation com a linha inteira e deixa a chamada enviada | src/ia-atendimento-b1-6a/src/ia_atendimento/ledger.py:164-171,241-246,343-354,419-425,467-480; migrations/0001_esquema.up.sql:215 |
| R2-017 | MEDIO | confirmado em parte | P4 | Mover `despachado=True` para antes da leitura do CPF da T7 não derruba nenhum teste | src/ia-atendimento/src/ia_atendimento/ferramentas/gateway.py:338-346; tests/test_ferramentas_gateway_revisao.py:169-180; tests/test_ferramentas_gateway.py:486-489 |
| R2-018 | MEDIO | confirmado | P4 | Pré-condição que devolve valor verdadeiro que não é `True` não é testada: `is True` → `bool()` sobrevive | src/ia-atendimento/src/ia_atendimento/ferramentas/gateway.py:431-439; tests/apoio_gateway.py:103-106; tests/test_ferramentas_gateway.py:247,283,291,305; tests/test_ferramentas_gateway_revisao.py:349-359 |
| R2-021 | MEDIO | confirmado | P5 | POST /sessoes/{id}/candidatos recusa (422) o corpo dos pulados que o 04 §2.6 manda | src/ia-atendimento/src/ia_atendimento/api/anotacoes.py:44-62 |
| R2-022 | MEDIO | confirmado em parte | P5 | texto_mensagem acima de 4000 caracteres ainda dá 422, e o contrato vigente manda truncar | src/ia-atendimento/src/ia_atendimento/api/eventos.py:46 |
| R2-003 | BAIXO | confirmado em parte | P1 | Faixa de valor '3000-4000' vira [TELEFONE]; lista de números sem palavra vira [NUMERO] | src/ia-atendimento/src/ia_atendimento/mascara.py:54,120 |
| R2-006 | BAIXO | confirmado em parte | P1 | Extração por código do número de alvo_pedido não existe; a única fonte guardada já vem mascarada | src/ia-atendimento/src/ia_atendimento/protecao.py:20; modulos_fase.py:60; ferramentas/esquemas.py (ArgsSimulacao) |
| R2-007 | BAIXO | confirmado em parte | P1 | Hash de idempotência do agendamento sobre texto mascarado colide textos diferentes | src/ia-atendimento/src/ia_atendimento/agendamento.py:92 |
| R2-014 | BAIXO | confirmado em parte | P2 | Leitura da FACTA em sombra/duble diverge da linha «Ler» de 08 §6, sem decisão registrada | src/ia-atendimento/src/ia_atendimento/ferramentas/modo.py:12-18,157-164 |
| R2-019 | BAIXO | confirmado | P4 | Guarda de banco fora de SERVICO_DO_BANCO na T5 sem teste | src/ia-atendimento/src/ia_atendimento/ferramentas/gateway.py:269-270; tests/apoio_gateway.py:73-81; tests/test_ferramentas_gateway_revisao.py:47-48 |
| R2-020 | BAIXO | confirmado | P4 | Filtro que impede nome de mascarar dentro de marcador ([CPF], [EMAIL]) sem teste | src/ia-atendimento/src/ia_atendimento/mascara.py:183-188; tests/test_mascara.py |
| R2-023 | BAIXO | confirmado em parte | P5 | _NOME_ASSINAVEL.match com $ aceita \n no fim; o contrato e config.py usam fullmatch | src/gl-gateway/app/assinatura.py:47,79 |
