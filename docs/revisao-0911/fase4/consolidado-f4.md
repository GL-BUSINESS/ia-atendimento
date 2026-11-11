# Revisão 0911 — Fase 4 (completude) consolidada

40 achados novos verificados (6 leitores de lacuna + crítico de completude).

| Estado | CRÍTICO | ALTO | MÉDIO | BAIXO |
|---|---|---|---|---|
| confirmado | 0 | 4 | 14 | 7 |
| confirmado em parte | 0 | 0 | 2 | 11 |
| não existe: critério de aceite | 0 | 0 | 2 | 0 |

## Recall dos canários

De 18 defeitos do gabarito, os leitores acharam 5 por inteiro e 2 em parte. Recall estrito: 28%. Recall com cada achado parcial valendo 0,5: 33%. Cinco defeitos estavam fora do alcance: quatro são lacunas de teste e os leitores não receberam arquivos de teste; um está em texto de contrato. Sem esses cinco, sobram 13 alcançáveis: estrito 5/13 (38%), com parciais 6/13 (46%). O único defeito ALTO do gabarito (A-1) foi achado. Relatório completo: fase4/recall-canarios.md. Os diffs e os trechos dos docs saíram de scripts/fase4-recall-1.sh, -2.sh e -3.sh. A precisão (achados que não estão no gabarito) não foi medida.

- canario-1 (B5.1, 11 defeitos): estrito 3/11 = 27%, com parciais 4/11 = 36%. Sem os 3 de teste (B-1, B-2, B-3), alcançáveis: estrito 3/8 = 38%, com parciais 4/8 = 50%. SIM: A-1, «Destino e pré-condições valem na hora de entrar na fila, não na hora do efeito»; M-1, «Orçamento por turno/atendimento não é atômico»; M-2, «Fila do limitador por serviço não tem prazo». EM PARTE: M-3, porque o achado do orçamento só diz que a leitura paga não conta tentativa e não vê o CORRIGIVEL levantado pelo executor; M-4, «Traceback de ErroDeFerramenta... mantém Chamada (e o CPF) vivos», que viu o traceback mas não o __context__ com PII e classificou como BAIXO. NÃO: M-6 (Resultado.dados aceita CPF), M-7 (T8 com posse real cai no simulador na parada dura), B-1 a B-3 (testes, fora do alcance) e B-4 (recusa na entrada não vai ao registro).
- canario-2 (B1.8 R-01): 1/1 = 100%. SIM: «Janela do extrator não é cruzada com janela_mensagem.dias do calendário», com a mesma linha (agendamento.py:119-127) e o mesmo ponto de fim inclusivo x exclusivo que a correção adotou.
- canario-3 (R2-07, R2-08; 4 defeitos): 0/4 = 0%; alcançáveis 0/3. NÃO: (1) mascarar troca 'dd/mm hh:mm' por [NUMERO]; (2) o extrator lê o texto de proteger_texto, que é texto de contrato e está fora do alcance; (3) [NUMERO] opaco perde a grandeza do número, a correção é [NUMERO:n]; (4) a lista de horas aceitas não tem 15hrs/15hs/15h30min. Os 8 achados da unidade são todos de vazamento ou de prompt. A data aparece num deles, mas no sentido oposto: «mascarar isenta data dd/mm/aaaa».
- canario-4 (R2-02, A1f): 1/2 = 50%; alcançável 1/1 = 100%. SIM: R2-02, «Exceção de ferramenta fora da lista escapa crua, sem contar falha do turno» (ALTO, mesma correção que entrou na main), reforçado por «Falha de rede da ferramenta é rotulada como falha do provedor». NÃO: A1f (texto fixo do ToolFailed sem teste; fora do alcance).

**Padrão de perda:** (1) Lacunas de teste (B-1, B-2, B-3, A1f): 4 dos 18. As unidades receberam só código de produção, então um mutante que sobrevive fica invisível. É limite do recorte, não do leitor. (2) Máscara que apaga demais e quebra função (R2-07/R2-08): os leitores procuram vazamento de PII e não perguntam o que a máscara destrói (hora, data com hora, tamanho do número). Deu 0 de 4 no canário da máscara. (3) Regra que só existe na tabela do contrato 08 §6 (M-7): sem o contrato ao lado, o 'interceptado' parece certo. (4) Caminho do dado que não vai ao modelo (M-6): o leitor viu a varredura do caminho do modelo e não seguiu Resultado.dados até quem o grava depois. (5) O mesmo resultado chegando por exceção e não por retorno, e o encadeamento implícito de exceções (M-3, M-4): ficaram meio vistos. (6) Registro de chamada recusada (B-4). Onde os leitores acertam bem: concorrência e ordem de await (A-1, M-1, M-2), costura entre módulos (R-01) e exceção que escapa (R2-02), em geral propondo a mesma correção que entrou na main.

## Achados novos (vivos), por gravidade

| Id | Gravidade | Estado | Unidade | Título | Onde |
|---|---|---|---|---|---|
| F4-009 | ALTO | confirmado | L2 | Hedge «perto das/lá pelas … da tarde» sai ALTA: _R_QUAL sem fronteira desloca a janela | src/ia-atendimento/src/ia_atendimento/agenda_extrator.py:231 |
| F4-016 | ALTO | confirmado | L3 | Compose da esteira não sobe a main: api:app inexistente e env de 30/10 | src/ia-atendimento-esteira/docker-compose.yml l.42-51 e l.86-94 |
| F4-035 | ALTO | confirmado | CRIT | Unidades de execução F2-47 (kits) e F2-48 (check.sh ×3, PG descartável, vistos) nunca rodaram: o estado «provado em ensaio» está vazio em toda a revisão | fase0/unidades.json (F2-47, F2-48) × fase3/cobertura.json × fase2/leituras/ |
| F4-036 | ALTO | confirmado | CRIT | Histórico git dos 6 repositórios nunca foi varrido por gitleaks, contra o PLANO; o CPF isento no .gitleaksignore e os CPFs «caso real» do facta-on ficam sem varredura de histórico | fase0/baseline.md (seção a) × PLANO §4 Fase 0 |
| F4-001 | MEDIO | confirmado | L1 | SIM do corpus aceita 4 formas que H e o plano 01 mandam para TX-36 | src/ia_atendimento/corpus/vocabulario.py:298; tests/test_corpus_revisao1.py:188-191 |
| F4-002 | MEDIO | confirmado | L1 | Variações de redação não são obrigadas a dizer o mesmo que o texto-base | src/ia_atendimento/corpus/regras/pii.py:31; corpus/semente.py:25-29; regras/gabarito.py:164-165,197-201 |
| F4-004 | MEDIO | confirmado | L1 | Hold-out sem P-M e com 4 das 12 vagas em personas sem diálogo | src/ia_atendimento/corpus/semente.py:45-48; regras/semente.py:19; tests/corpus/semente.json |
| F4-005 | MEDIO | confirmado | L1 | Hold-out v3 do extrator ensinou correções e segue no portão de 95% | tests/corpus/gerar_agenda_frases.py:436-438; tests/corpus/README.md:152,159-160; tests/test_agenda_extrator.py:83-88,545-549 |
| F4-010 | MEDIO | confirmado | L2 | _R_HEDGE fechado e com erro em «cerca das»: aproximações e limites ainda ALTA | src/ia-atendimento/src/ia_atendimento/agenda_extrator.py:260-263 |
| F4-011 | MEDIO | confirmado | L2 | «15h/16h» perde a segunda hora e devolve a primeira ALTA | src/ia-atendimento/src/ia_atendimento/agenda_extrator.py:273,395-406 |
| F4-013 | MEDIO | confirmado | L2 | «em 2h» lido como relógio 14:00; «daqui 2h» como duração 12:00 | src/ia-atendimento/src/ia_atendimento/agenda_extrator.py:243-245,375-376 |
| F4-014 | MEDIO | confirmado | L2 | «quinze para as 4» gera 16:00 em vez de 15:45 | src/ia-atendimento/src/ia_atendimento/agenda_extrator.py:238 |
| F4-018 | MEDIO | confirmado | L3 | Conflito de pyproject/uv.lock no merge da esteira apaga dependências | pyproject.toml e uv.lock (main x esteira) |
| F4-021 | MEDIO | confirmado em parte | L4 | Roteiro manda desfazer A4.3 pelo texto v1 do estudo E, não pelo desfazer.sh | /opt/claude/docs/planejamento-ia/ROTEIRO-DE-ACAO.md:706 × estudos/semana-1/e-infra-s4-vps.md:393 × kits/s4/desfazer.sh:28 |
| F4-022 | MEDIO | confirmado | L4 | Kit que roda é cópia solta em retomada-2809, sem trava de hash; ramo kits/s4 sem push | kits/s4/README.md:26-29; ROTEIRO-DE-ACAO.md:324; fase0/MANIFESTO.md:36 |
| F4-023 | MEDIO | não existe: critério de aceite | L4 | A4.3a sem comando para o pg_dump -s exigido no aceite; provar.sh aborta sem VPS | kits/s4/provar.sh:65; kits/s4/s4-hba.sh:153; ROTEIRO-DE-ACAO.md:705-706 |
| F4-026 | MEDIO | confirmado | L5 | Merge junta duas modo_efetivo com regras divergentes | ramo src/ia_atendimento/ledger.py:74,105-109 x main src/ia_atendimento/ferramentas/modo.py:36,49-52 |
| F4-027 | MEDIO | não existe: critério de aceite | L5 | OPERACAO do ramo sem runbook da B1.6a | ramo docs/OPERACAO.md (todo); ramo docs/DECISOES-B1.6a-0411.md:14,31 |
| F4-030 | MEDIO | confirmado | L6 | q.sh: read-only só por set de sessão como superusuário s4_super | /opt/claude/docs/planejamento-ia/consultas/conversao-2910/q.sh:3 |
| F4-031 | MEDIO | confirmado | L6 | Medição de conversão expõe nome e desempenho de consultor | /opt/claude/docs/planejamento-ia/consultas/conversao-2910/a2.sql:1,9-10; a5.sql:15 |
| F4-033 | MEDIO | confirmado | L6 | anon --k sem piso desliga o k-anonimato | src/bancos-duble/anonimizador/duble_anon/cli.py:162,129-143 |
| F4-037 | MEDIO | confirmado em parte | CRIT | Costuras F2b-04, F2b-05, F2b-08, F2b-09 e F2-40 feitas com um lado só: a regra de isolamento proibiu a entrada obrigatória vinda das leituras F2 | fase3/cobertura.json (nao_lido de F2b-04, F2b-05, F2b-08, F2b-09, F2-40) |
| F4-003 | BAIXO | confirmado em parte | L1 | I1 e I4 não olham T7 permitido em turno do cliente | src/ia_atendimento/corpus/regras/invariantes.py:22-25,48-49; regras/duble.py:43; modelos.py:160,170-184 |
| F4-006 | BAIXO | confirmado em parte | L1 | Faixas sintéticas de telefone e número aceitam formato de dado real | src/ia_atendimento/corpus/pii.py:55-57,64 |
| F4-007 | BAIXO | confirmado | L1 | corpus/pii.py copia a máscara por privadas, sem teste de equivalência | src/ia_atendimento/corpus/pii.py:38-46 |
| F4-008 | BAIXO | confirmado | L1 | README promete texto livre no hold-out que nenhuma regra exige | tests/corpus/README.md:82; src/ia_atendimento/corpus/regras/cobertura.py:104,120 |
| F4-012 | BAIXO | confirmado em parte | L2 | Faixa com hífen e «entre X e Y» viram alternativas, não intervalo | src/ia-atendimento/src/ia_atendimento/agenda_extrator.py:228,256-258,476-480 |
| F4-015 | BAIXO | confirmado em parte | L2 | Ids do corpus são posicionais: ho-251/253 da revisão 1 hoje são outras frases | src/ia-atendimento/tests/corpus/agenda_frases.jsonl |
| F4-017 | BAIXO | confirmado | L3 | Ramos locais com máscara sem M-3/R2-07 e Settings sem HMAC | src/ia-atendimento-{esteira,kits-s4}/src/ia_atendimento/mascara.py e config.py |
| F4-019 | BAIXO | confirmado em parte | L3 | Esteira e kit A4.3 só em ramos locais não empurrados | feat/esteira (9e1afe39, ahead 2) e kits/s4 (148cc72d, ahead 1) |
| F4-020 | BAIXO | confirmado | L3 | Amostra de CPF de DV válido fora da faixa sintética nos ramos | src/ia-atendimento-{esteira,kits-s4}/tests/test_varredura.py l.28 e l.91 |
| F4-024 | BAIXO | confirmado | L4 | Roteiro espera «no pg_hba.conf entry»; kit com reject final produz «rejects connection» | ROTEIRO-DE-ACAO.md:705 × kits/s4/provar.sh:24, README.md:69-70 |
| F4-025 | BAIXO | confirmado em parte | L4 | Ensaio do kit cobriu só migrações 0001-0002; A4.6 aplicará 0001-0005 | kits/s4/README.md:109; src/ia-atendimento-kits-s4/migrations/ × src/ia-atendimento/migrations/ |
| F4-028 | BAIXO | confirmado | L5 | CHANGELOG conflita no mesmo ponto; resolver por um lado apaga B1.8+B5.1 ou B1.6a | CHANGELOG.md:7 (main e ramo) |
| F4-029 | BAIXO | confirmado | L5 | OPERACAO do ramo manda conferir 4 linhas no ledger (main: 5) | ramo docs/OPERACAO.md:~84 x main docs/OPERACAO.md:~92 |
| F4-032 | BAIXO | confirmado em parte | L6 | atualizar_pessoas_teste grava sem validar que o dado é sintético | src/bancos-duble/scripts/atualizar_pessoas_teste.py:32-42,62-63 |
| F4-034 | BAIXO | confirmado em parte | L6 | anon aceita --seed fixo em captura real | src/bancos-duble/anonimizador/duble_anon/cli.py:163,174; anonimizar.py:258-259 |
| F4-038 | BAIXO | confirmado em parte | CRIT | Canário 5 não rodou e o recall dos canários 1–4 não foi contado em lugar nenhum; o critério de parada da Fase 4 fica sem medida | fase0/canarios-gabarito.txt × fase3/consolidado.md × fase3/canarios-achados.json |
| F4-039 | BAIXO | confirmado em parte | CRIT | Os 128 RG não têm tabela única nem vocabulário comum dos 4 estados; o consolidado só cita 54 | fase1/leituras/F1-53..F1-58 × fase3/consolidado.json |
| F4-040 | BAIXO | confirmado em parte | CRIT | Leitores rodaram shell fora de script e sem Grep/Glob; a rastreabilidade de buscas de ausência ficou incompleta | fase3/cobertura.json (nao_lido de F1-15, F1-53, F1-56, F2-07, F2-11, F2-14, F2-18, F2-19, F2-22, F2-33, F2-39, F2-40, F2-41) |
