# Revisão 0911 — Fase 3 consolidada

762 grupos de achado. Votos faltando em 0 grupos: 

## Estado × gravidade final

| Estado | CRÍTICO | ALTO | MÉDIO | BAIXO | Total |
|---|---|---|---|---|---|
| aberto: decisão não achada | 0 | 0 | 7 | 1 | 8 |
| baixo não amostrado | 0 | 0 | 0 | 89 | 89 |
| confirmado | 0 | 46 | 185 | 97 | 328 |
| confirmado em parte | 0 | 1 | 51 | 142 | 194 |
| contestado | 0 | 0 | 0 | 4 | 4 |
| não confirmado | 0 | 0 | 0 | 5 | 5 |
| não existe: critério de aceite | 0 | 21 | 50 | 27 | 98 |
| não verificável | 0 | 0 | 1 | 0 | 1 |
| peça existe (refutado) | 0 | 0 | 0 | 1 | 1 |
| refutado | 0 | 0 | 0 | 10 | 10 |
| risco aceito | 0 | 0 | 0 | 6 | 6 |
| risco aceito em parte | 0 | 0 | 6 | 12 | 18 |

## Gravidade do leitor → final (só grupos verificados)

| Leitor \ Final | CRITICO | ALTO | MEDIO | BAIXO |
|---|---|---|---|---|
| CRITICO | 0 | 1 | 0 | 0 |
| ALTO | 0 | 66 | 61 | 3 |
| MEDIO | 0 | 1 | 239 | 205 |
| BAIXO | 0 | 0 | 0 | 97 |

## CRITICO vivos (0)

| Grupo | Estado | Título | RG | RS | Unidades |
|---|---|---|---|---|---|

## ALTO vivos (47)

| Grupo | Estado | Título | RG | RS | Unidades |
|---|---|---|---|---|---|
| G-0004 | confirmado | Regra 5 diz que o web não faz deploy no merge; a memória diz que faz |  | RS-27 | F1-01 |
| G-0005 | confirmado | D-32 exige prova de eliminação em 14 d que o papel diz não cumprir |  | RS-06,RS-14 | F1-01,F1-04,F1-10 |
| G-0008 | confirmado em parte | Painel prevê escrita em produção sem kit nomeado ou com kit inexistente (PD-2) |  | RS-08 | F1-02 |
| G-0009 | confirmado | Go/no-go sem custo e latência: D-01 contradiz A2.9/B8.2/B10.1 |  |  | F1-03,F1-59 |
| G-0011 | confirmado | Bloco de A4.6 grava o ledger fora da transação da migração |  | RS-08 | F1-04,F2-18,F2b-09 |
| G-0015 | confirmado | Passos de infra A4.2, A4.4, A4.5, A4.7 e A4.8 sem kit nem ensaio local |  | RS-08 | F1-04 |
| G-0016 | confirmado | A6.6b vencida sem entrega: worker do compose aponta módulo inexistente | RG-067 | RS-01,RS-07,RS-10,RS-18,RS-25 | F1-05,F1-56,F2-03,F2-07,F2-22,F2-24,F2-25,F2b-02,F2b-09 |
| G-0017 | confirmado | B3.1 e B3.2 contradizem o mapa sobre dia e hora do merge do facta-on |  | RS-15,RS-27 | F1-06,F1-20,F2-32 |
| G-0019 | confirmado | Cadeia B1.4 > B1.6 > B1.7 > v0.3.0 > deploy #8 não fecha |  |  | F1-06 |
| G-0020 | confirmado | D-15 sem saída quando a vigia morreu: repasse trava e ninguém devolve |  | RS-11 | F1-07,F1-16,F1-18,F2b-03 |
| G-0022 | confirmado | Falhas provocadas de 24/11 caem dentro da sombra com modo global sombra | RG-007 | RS-11,RS-22 | F1-08,F1-53 |
| G-0031 | confirmado | prazo_ate nunca recalculado em retomou: lead retomado devolvido pela R-b em 60 s |  |  | F1-16 |
| G-0032 | confirmado | D-14 entrega o lead à vigia, mas a vigia não tem regra (R-c2 sem decisão); lead preso após 30 min | RG-095 | RS-11,RS-25 | F1-16,F1-23,F1-31,F1-57,F1-59 |
| G-0037 | confirmado | Canal.restaurar do 02 devolve a delegação; o 08 delega pela rota |  | RS-32 | F1-21 |
| G-0043 | confirmado | Ajuste de valor/seguro só é reconfirmado depois da proposta já criada |  |  | F1-28a |
| G-0047 | confirmado | Máscara de PII não cobre o que o estudo proíbe no banco e no prompt |  | RS-21 | F1-28b |
| G-0050 | confirmado | Checklist de J manda pôr a chave em off às 20:15, contradizendo RS-25 e o código |  | RS-25 | F1-31,F1-39a |
| G-0054 | confirmado | M: janela seg–sáb e TX-M03 superados pelo domingo |  |  | F1-32 |
| G-0055 | confirmado | Fonte de cpf_alterado e etapa_inapp sem passo de construção nem linha na matriz |  |  | F1-33 |
| G-0056 | confirmado | Robôs concorrentes no chat sob IA só parcialmente cobertos | RG-093 |  | F1-33 |
| G-0062 | confirmado | Plano mestre contradiz decisões de produto da v3.3 |  | RS-03 | F1-41 |
| G-0063 | confirmado | sp01 sem nota de precedência: pontos de RG-003/013 (30 turnos, fail-open 60 s, T12 incondicional) seguem vigentes | RG-003 | RS-09,RS-11 | F1-42,F1-43,F1-53 |
| G-0070 | confirmado | main do gl-gateway sem proteção demonstrada; merge = deploy |  | RS-27 | F1-51b |
| G-0074 | confirmado | Tabela única de location do vhost WG no 02 §2 não foi escrita (batimento.json, conferir/por-cpf, 8118 ausentes) | RG-011 | RS-11 | F1-21,F1-23,F1-53 |
| G-0075 | confirmado | Textos para aprovacao nao reemitidos: arquivo ainda v1 de 30/10 com NT-01, TX-M03, TX-42 e lotes errados | RG-023 |  | F1-05,F1-52,F1-54,F1-57,F1-59 |
| G-0076 | confirmado | PR #13 (B1.6a) CONFLICTING com a main; B1.6a+B1.8+B5.1 nunca passaram juntas por portão | RG-045 |  | F1-55,F2-21a,F2-21b |
| G-0079 | confirmado | Decisão delegada de 10/11 (degrau de 1 dia, piloto 27-30/11) não está no roteiro |  | RS-08 | F1-08,F1-09,F1-59 |
| G-0084 | confirmado | Virada de mês da chave AES não entra sozinha: exige troca e reinício em 30/11, contra o roteiro |  | RS-05 | F2-02,F2-05 |
| G-0085 | confirmado | observabilidade.configurar sem chamador: máscara de logs não ligada |  | RS-03,RS-03, RS-16, RS-17,RS-13,RS-17 | F2-06,F2-39,F2-49,F2b-08 |
| G-0087 | confirmado | Efeito irreversível já despachado (T7) pode sair com erro repetível/não INDETERMINADO |  | RS-10 | F2-12,F2-40,F2b-05 |
| G-0088 | confirmado | T5 de 3RN/C6 é classe leitura: em sombra/duble vai à produção com CPF, fora do teto de pagas |  | RS-20 | F2-12,F2b-05 |
| G-0090 | confirmado | Minutos justapostos são descartados e a hora sai alta |  |  | F2-13 |
| G-0094 | confirmado | Dockerfile da esteira não constrói a main: faltam migrations/ e fixtures/ |  | RS-18 | F2-22 |
| G-0095 | confirmado | deploy-vps.sh pode anunciar a tag nova no ar sem tê-la trocado |  | RS-08 | F2-22 |
| G-0096 | confirmado | Portão de dia de piloto e checklist nas datas antigas (dias-piloto.txt) |  | RS-27 | F2-22 |
| G-0097 | confirmado | DEPLOY.md manda arquivos 640 em /etc/ia-s4; o código recusa qualquer bit de grupo |  | RS-05,RS-07 | F2-22,F2b-09 |
| G-0106 | confirmado | Receita do README sobe facta-on sem guarda nem rede interna |  | RS-15 | F2-31 |
| G-0114 | confirmado | Nome do cliente nunca é conhecido: receptor grava com `nomes=()` fixo e a máscara de nomes não atua em produção | R2-06 (REVISAO-B1.4-0311-r2, id do repositório; RG-nnn não identificado) | RS-21 | F2-02,F2-10,F2-39 |
| G-0118 | confirmado | facta-on: CPFs declarados caso real em comentários e testes, sem portão de PII |  | RS-13 | F2-49 |
| G-0119 | confirmado | Forma real do Post não medida contra validação estrita (datetime_post) |  |  | F2b-01 |
| G-0121 | confirmado | POST /atendimentos não aceita matricula (D-29): 422 |  | RS-29 | F2-08,F2b-03 |
| G-0122 | confirmado | criterio_versao sha256 recusado por rejeitar_documento |  |  | F2b-03 |
| G-0124 | confirmado | Os 5 escopos da credencial da IA alcançam 19 operações, com enumeração em lote e segunda escrita |  | RS-29 | F2b-04 |
| G-0125 | confirmado | nao_perturbe e limite_contratos ausentes viram sem bloqueio na IA |  |  | F2b-04 |
| G-0126 | confirmado | Destinos recusa http fora de loopback, mas os vhosts WG do papel são http://10.90.0.2 |  | RS-19 | F2b-04,F2b-05 |
| G-0127 | confirmado | Rota do T7 (/proposta/formalizar) fora do vhost WG e do contrato 05 | RG-011 | RS-10 | F2b-05 |
| G-0131 | confirmado | Execução morta no meio de T12/assumir/restaurar: `enviada` órfã vira `indeterminado` (terminal) para qualquer classe e o repasse não se repete |  | RS-10,RS-25 | F2-19,F2b-07 |

## Peças que não existem (99): viram critério de aceite

| Grupo | Gravidade | Título | Unidades |
|---|---|---|---|
| G-0001 | ALTO | VPS OVH BHS não existe e A1.3 vence hoje (RG-041 aberto) | F1-49,F1-54 |
| G-0012 | ALTO | Kit s4/migrar.sh de A4.6 não existe | F1-04 |
| G-0013 | ALTO | VPS sem política de saída e sem critério de aceite de egress | F1-04,F1-27,F2-22,F2-25 |
| G-0023 | ALTO | Parada dura sem comando, prazo de decisão nem responsável noturno | F1-08,F2-24 |
| G-0036 | ALTO | Ator 85 não é fixado em nenhuma cláusula do contrato 02 | F1-21 |
| G-0058 | ALTO | Matrícula: nenhum elo do caminho existe em código e H1-H3 não foram medidas | F1-35 |
| G-0066 | ALTO | B1.6b inteira não tem código: processador, repasse, Canal, verificador, confirmação, reaper_ledger | F1-43 |
| G-0068 | ALTO | Post por mensagem e retry do webhook sem evidência | F1-46 |
| G-0072 | ALTO | TX-42 (aviso de domingo) não existe no arquivo nem em TX_IDS | F1-52 |
| G-0073 | ALTO | Nenhum texto fixo está no código, só IDs; nada trava o texto do cliente (RS-23) | F1-52 |
| G-0078 | ALTO | Repasse forçado das 19:45 (B6.7) não existe | F1-56 |
| G-0083 | ALTO | Parada dura por gasto e disjuntor por atendimento não existem | F2-04,F2-41 |
| G-0086 | ALTO | Janela 08–20 só conferida na entrada e no lembrete | F2-11,F2b-07 |
| G-0089 | ALTO | Idempotência/ledger de efeito não ligado ao gateway: T7 executa sem reserva | F2-12,F2-20,F2-21a |
| G-0091 | ALTO | Rede de recuperação da volta termina em serviços que não existem (tratar_lease_vencido) | F2-14 |
| G-0099 | ALTO | OPERACAO sem matriz de alertas (destinatário, prazo, ação) | F2-24 |
| G-0108 | ALTO | CPF das rotas conferir e por-cpf vai ao log (log() e uvicorn.access) sem filtro | F1-20,F1-47,F1-53,F2-32,F2b-05 |
| G-0115 | ALTO | Turno, Canal e T7 pelo ledger não estão ligados em nenhuma das bases | F2-40 |
| G-0123 | ALTO | Sentido orquestrador para n8n não existe: sem publicador, sem repasse | F2b-03 |
| G-0129 | ALTO | Emissor ao ChatGuru não existe (Canal, nota, assumir, restaurar) | F2b-07 |
| G-0565 | ALTO | «Abertos têm até 20 min e são repassados com a nota» depende de B1.6b; na main o job agendado pelo desligar falha | F2b-06 |
| G-0028 | MEDIO | Desvio da linha 1 (RPA leitor principal) contradiz linhas 8 e 40 | F1-10 |
| G-0039 | MEDIO | Plano B de b não cobre ausência do diálogo pega-tudo | F1-25 |
| G-0071 | MEDIO | Nenhum dos 67 textos aprovado nem travado por hash | F1-52 |
| G-0135 | MEDIO | Kits previstos para 05-08/11 não existem | F1-02 |
| G-0147 | MEDIO | A1.13 cookie do RPA sem seção nem procedimento | F1-03 |
| G-0162 | MEDIO | B4.3 e escopos ia:* não existem; migração 000025 e D-API-77 só promessa | F1-06 |
| G-0179 | MEDIO | Desvio da linha 10 (reabrir portão zVuE) não cabe no calendário | F1-10 |
| G-0203 | MEDIO | Nenhum artefato existe: view, kit DDL, fluxos, vigia e ensaio S1-S6 | F1-15 |
| G-0213 | MEDIO | Fail-closed do batimento (D-15) depende da vigia da S2, que não existe | F1-17 |
| G-0216 | MEDIO | Peças inexistentes: consumo do batimento, publicador do espelho, repasse por etapas, tarefa das 19:45 | F1-18 |
| G-0221 | MEDIO | Sem lista de IP na chave: única barreira é o vhost WG 8118 inexistente | F1-19 |
| G-0236 | MEDIO | Itens de segurança dos contratos sem linha na matriz de restrições | F1-23 |
| G-0237 | MEDIO | R2-19, R2-21 e R2-12 sem fechamento: medições A2.4/A2.8 e tabela de credenciais inexistentes | F1-23 |
| G-0242 | MEDIO | Fronteiras do orquestrador com provedor de modelo, ntfy e Phoenix sem contrato | F1-24 |
| G-0260 | MEDIO | DPA e ZDR contratual inexistentes | F1-27 |
| G-0299 | MEDIO | RT-16 e linhas script apontam para script sem dono nem escopo | F1-37a |
| G-0304 | MEDIO | §6 exige do orquestrador e da API peças ausentes dos contratos 03 e 08 | F1-37b |
| G-0305 | MEDIO | Papel ia_leitura_painel e ACL por coluna não existem | F1-37b |
| G-0311 | MEDIO | Ack do alerta sem fonte com ntfy.sh | F1-39a |
| G-0323 | MEDIO | Chave AES mensal x retenção de 14 d sem procedimento | F1-42 |
| G-0325 | MEDIO | B1.7 e2e nao existe | F1-43 |
| G-0328 | MEDIO | Fronteira das 20:15 e DATAPREV: vigia e reabertura nao existem | F1-43 |
| G-0336 | MEDIO | Medicoes de cache, tokenizer e latencia ainda nao existem | F1-45 |
| G-0373 | MEDIO | Kit do ensaio n8n S1–S6 (A3.8) não existe | F1-55 |
| G-0377 | MEDIO | Kits prometidos pelas emendas não existem | F1-56 |
| G-0378 | MEDIO | Dicionario de contexto_codigos e texto_livre.casos.json nao existem | F1-56 |
| G-0385 | MEDIO | RG-108: chaves expostas atravessam o piloto sem kit nem registro | F1-58 |
| G-0389 | MEDIO | Máquina de estados sem chamador de produção na main; repassando vencido não é recolhido | F2-01 |
| G-0391 | MEDIO | Laço do turno ausente: consumir, fala da IA, resumo, leitura do canal e `omitidas` sem chamador | F2-02 |
| G-0396 | MEDIO | `Servicos` de produção vazios: nenhum job de chat processa na main | F2-03 |
| G-0401 | MEDIO | Descarte mensal da chave AES sem código/kit e regra do dia 31 ambígua | F2-05 |
| G-0407 | MEDIO | Pré-voo real, batimento da vigia e no ar só depois da vigia não existem | F2-07 |
| G-0414 | MEDIO | RS-23 neste pacote é só cerca estrutural: número por extenso passa e o T15 não existe | F2-09 |
| G-0421 | MEDIO | Bloqueio de texto livre depois de 24 h não existe em nenhum arquivo da unidade | F2-10 |
| G-0422 | MEDIO | Nada em src chama montar_contexto: exemplos, resumo e desvio da E5 são só capacidade | F2-10 |
| G-0423 | MEDIO | Falta teste das 84 pessoas_teste com vistos | F2-10 |
| G-0426 | MEDIO | Kits s4/migrar.sh e domingo.sh não existem; sim da 0005 só texto | F2-11 |
| G-0433 | MEDIO | Leitor de CPF real não existe; destino duble recebe CPF sem garantia de pessoa sintética | F2-12 |
| G-0440 | MEDIO | Prova da noite parcial; aguardando_cliente atravessa a noite | F2-14 |
| G-0445 | MEDIO | Corpus com domingo aberto (B8.1c) não existe | F2-16 |
| G-0457 | MEDIO | D-15: nenhum consumo do batimento; devolução real sem gancho | F2-19 |
| G-0464 | MEDIO | Kit s4/migrar.sh não existe; migrações por texto manual de psql sem controle do «sim» da 0005 | F2-18,F2-21b |
| G-0510 | MEDIO | Fluxos e kits do braço n8n não existem; A3.8 passou da data sem kit | F2-34 |
| G-0530 | MEDIO | domingo.sh, ativar.sh e set.sh não existem | F2-38 |
| G-0532 | MEDIO | Canário ponta a ponta não existe; vazamento só no corpo ao provedor | F2-06,F2-39 |
| G-0545 | MEDIO | Reconciliador RPA (plano B do leitor) não existe; janela de casamento webhook x RPA não calibrada | F2b-01 |
| G-0561 | MEDIO | Sem contrato de teste para as rotas da IA no facta-on | F2b-05 |
| G-0568 | MEDIO | Identidade do remetente (Amado, linha) sem ponto fixo | F2b-07 |
| G-0572 | MEDIO | Provedor recusando (401/402/403/429) não fecha a entrada nem gera alerta crítico | F2-41,F2b-08 |
| G-0573 | MEDIO | ntfy.sh sem código e sem critério do conteúdo permitido | F2b-08 |
| G-0273 | BAIXO | Chave AES, parecer J5 e aceite do chat_number pendentes | F1-29 |
| G-0285 | BAIXO | L: juiz sem chave de desligamento e papel ia_qualidade contradito | F1-32 |
| G-0292 | BAIXO | Resoluções 'aplicado' cobrem peças inexistentes (B6.7, B6.8, B6.4) | F1-34 |
| G-0294 | BAIXO | Gatilho fora do horário não é premissa confirmada; estudo D-18 o ignora | F1-35 |
| G-0297 | BAIXO | Rotas das seções F1/F2 inexistentes no contrato 03/08 | F1-36 |
| G-0380 | BAIXO | D-13: recusa de abertura sem hora do cliente não existe no iniciar | F1-57 |
| G-0446 | BAIXO | Harness de medição B8.1b não existe | F2-16 |
| G-0506 | BAIXO | Todo o caminho da IA (/v1/ia/*, escopos, migração) não existe na cliente360-api | F1-38,F2-33 |
| G-0556 | BAIXO | Cliente do 360, troca de token, executores T1/T2/T3/T10 e testes D-29 não existem | F2b-04 |
| G-0579 | BAIXO | RS-10, RS-11, ntfy, vigia 19:45, B6.6/B6.7 são pedido sem código | F1-01 |
| G-0581 | BAIXO | Medições prometidas sem artefato, algumas vencidas | F1-03 |
| G-0589 | BAIXO | Nenhum teste de ator de envio fixo em 85 | F1-07 |
| G-0594 | BAIXO | Parte F e Anexo X sem ponteiro para a revisão 0911 | F1-12 |
| G-0597 | BAIXO | Header Auth do n8n e itens do §13 sem aceite ou dono | F1-14 |
| G-0604 | BAIXO | Migração 000025, D-API-77, flags C360_IA_* e rotas /v1/ia/* não existem | F1-19 |
| G-0608 | BAIXO | Peças do facta-on que não existem ainda (critérios de aceite) | F1-20 |
| G-0610 | BAIXO | Peças do web sem código (tela, BFF, flag, timer, emergência, ntfy) | F1-22 |
| G-0616 | BAIXO | Spikes e validações do dublê FACTA só planejados | F1-26 |
| G-0627 | BAIXO | Peças exigidas por J e K ainda inexistentes | F1-31 |
| G-0629 | BAIXO | Peças sem existência: TX-01T, view, descarte (critério de aceite) | F1-33 |
| G-0645 | BAIXO | Papel ia_leitura_painel, ack obrigatório, ntfy de status e pedidos IA-ORQ-* ainda não existem | F1-40 |
| G-0660 | BAIXO | Janela DATAPREV recorrente não existe no código | F1-49 |
| G-0702 | BAIXO | Contraproposta e pergunta de ambiguidade não existem | F2-13 |
| G-0713 | BAIXO | texto_de_saida, FontePessoasTeste e FixturesDuble sem chamador no orquestrador | F2-15 |
| G-0736 | BAIXO | uid/gid do orquestrador na VPS seguem hipótese | F2-27 |
| G-0750 | BAIXO | Regra nft da VPS e rotação de segredos do gateway não têm kit | F2-35 |
| G-0755 | BAIXO | Calendário de renovação dos certificados de 397 dias e kit s4/migrar.sh ainda não existem | F2-37 |
| G-0762 | BAIXO | Rotação para ia_app_b e troca de senha do ia_app_a sem kit | F2b-09 |

## Riscos aceitos (32)

| Grupo | Estado | Gravidade | Título |
|---|---|---|---|
| G-0142 | risco aceito | BAIXO | Janela de desfazer C2-C6 vence antes do limite da ata |
| G-0191 | risco aceito em parte | BAIXO | Queda de 4-8 s vs repetições de ~6 s tratadas como cobertura |
| G-0202 | aberto: decisão não achada | MEDIO | Rótulo consultor_nome depende de confirmação pendente e está na view |
| G-0217 | risco aceito em parte | MEDIO | Contrato 03 não declara que pessoa:ler alcança GET /pessoas/{id} |
| G-0226 | risco aceito em parte | MEDIO | Rota genérica /chatguru/acao com token permite qualquer action (risco aceito) |
| G-0246 | aberto: decisão não achada | MEDIO | ia_app pode inserir ia_ativa e teto sem controle de quem |
| G-0252 | risco aceito em parte | BAIXO | Portão do chatguru-api fail-open por 60 s sem dono nem teste |
| G-0259 | risco aceito em parte | BAIXO | Renovação de certificados sem dono; servidor vence antes dos clientes |
| G-0263 | risco aceito em parte | MEDIO | Opt-out só vale para a IA |
| G-0329 | risco aceito em parte | MEDIO | Retenção de 14 d do ia_obs contradiz fulls do pgBackRest e spans sem regra de mascaramento |
| G-0348 | aberto: decisão não achada | MEDIO | ISKRA único escritor sem prova |
| G-0384 | aberto: decisão não achada | MEDIO | RG-107: alcance da máscara de PII não apresentado ao dono |
| G-0420 | risco aceito em parte | MEDIO | Limites da máscara (extenso, dígitos com letras, pedaços de CPF, data de nascimento) deixam CPF/valor chegarem ao modelo, contra a regra 2 |
| G-0442 | risco aceito em parte | BAIXO | CPFs de teste têm DV válido e a premissa «faixa nunca é de cliente» não está provada |
| G-0471 | aberto: decisão não achada | MEDIO | .gitleaksignore isenta CPF de DV válido do commit 88d081a sem prova de ser sintético |
| G-0482 | aberto: decisão não achada | MEDIO | ia-sumidouro guarda o Post com PII por 7 dias sem decisão localizada nem expurgo |
| G-0489 | aberto: decisão não achada | MEDIO | DDD 00 das personas (R-03) segue aberto |
| G-0491 | risco aceito em parte | MEDIO | Consistencia das pessoas de teste so no check.sh local, sem pin do irmao |
| G-0584 | risco aceito | BAIXO | A1.8 adiamento por silêncio da chave exposta inapp-clt |
| G-0617 | risco aceito em parte | BAIXO | Janela do conferir de 20 min com margem estreita sobre 16,9 min |
| G-0619 | risco aceito em parte | BAIXO | Preço, latência e cache do estudo g não medidos |
| G-0623 | risco aceito em parte | BAIXO | Motor v0 fixo substitui «treinado no corpus» sem decisão do dono citada |
| G-0635 | risco aceito | BAIXO | Estimativas do F0 somam tetos como valor e divergem do roteiro |
| G-0636 | risco aceito | BAIXO | Matriz promete cobertura de tela que não existe antes de 29/11 |
| G-0665 | risco aceito em parte | BAIXO | Cookie do RPA: aceite de 30/10 não vale hoje |
| G-0667 | risco aceito | BAIXO | Lição 2 do incidente (fallback sem colunas) está no código |
| G-0690 | risco aceito em parte | BAIXO | Replay assinado dentro de 300 s reexecuta sem datetime_post |
| G-0716 | aberto: decisão não achada | BAIXO | Cobertura por rótulo e mutação das regras não reproduzível |
| G-0734 | risco aceito em parte | BAIXO | Teste congela ia-sumidouro guardando Post inteiro com CPF por 7 dias |
| G-0738 | risco aceito em parte | BAIXO | Faixa sintetica de CPF e hipotese isenta nos scanners |
| G-0748 | risco aceito em parte | BAIXO | Webhook ia-sumidouro sem autenticação |
| G-0761 | risco aceito | BAIXO | Só-EUA garantido pelo nome do roteador; nada confere a resposta |
