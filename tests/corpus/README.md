# Corpus da F3 (roteiro B8.1a)

Personas, diálogos-gabarito e semente da avaliação F3 (B8.1b monta o harness, B8.2 roda a F3 curta). **Tudo é inventado**: nenhuma
conversa real do ChatGuru (o corpus real está proibido até o parecer jurídico J5), CPF só `000.000.0nn-dd`, nomes e sobrenomes fictícios,
valores redondos, telefone/e-mail só dos sintéticos da varredura. A *forma* das falas segue o levantamento 09 (§3-§4): o cliente escreve
curto (p50 de 11 caracteres; aqui a mediana é 8), quase sempre texto (97%), uma mensagem por turno, abreviação e sem acento.

| Arquivo | O que é |
|---|---|
| `personas.jsonl` | 60 personas P01-P60 (H §7). As 40 da F3 curta (C5) levam `f3_curta: true`: P01-P08, P19-P31, P36-P41, P44-P50, P53-P54, P57-P60 |
| `personas_m.jsonl` | 24 personas P-M01-P-M24 (agendar assinatura, M EM2). As 20 `critica: true` (as que a rodada de 13/11 exige) têm diálogo; as outras 4 não |
| `dialogos/<id>.jsonl` | gabarito roteirizado das 40 da F3 curta + as 20 P-M críticas: uma linha JSON por turno |
| `semente.json` | ordem das personas, hold-out (20%) e sementes das 3 execuções por persona; reproduzível |
| `duble_personas.json` | instantâneo (ids, CPFs, cenários) de `bancos-duble/personas/personas.yaml` **como está na main do dublê** (hash em `fonte`). O corpus se amarra ao dublê, não o contrário: `uv run --with pyyaml python scripts/atualizar_duble.py <personas.yaml> <hash> [--verificar]` regrava ou confere |

## A persona

`id`, `familia` (`H`/`M`), `classe` (classe de H §7), `f3_curta`, `cpf` (o do dublê quando há persona lá), `nome`, `perfil` (idade, vínculo
CLT, margem, oferta FACTA ativa sim/não, valor pré-aprovado redondo, prazo), `contexto` (`inicio_utc`, `instante_chave_utc` e
`cenario_tempo`: horário normal, noite, sábado, domingo, feriado de 20/11, virada DATAPREV, 22:30 UTC), `comportamento` (intenção
dominante e todas as exibidas, objeções **em ordem**, estilo, ritmo, some após qual fase, adia com/sem hora, digita CPF/telefone no texto,
pede humano, muda de ideia, hostil, mídia), `desfecho_esperado` (`vendeu`, `repassado`, `agendado`, `encerrado_sem_interesse`,
`recusado_facta`), `fases` (E0-E10 que percorre), `invariantes_em_risco` (I1-I9 que ela existe para testar), `cenario_facta` (o que o
dublê devolve: persona do dublê, ou `sem_chamada_facta`, ou estado global `virada`/`reabertura`) e, nas P-M, `em` (EM1-EM9) e `critica`.

CPFs: persona com stub no dublê usa o CPF dele. P14, P34, P44, P48, P52, P56, P57 e P58 digitam na FACTA e aparecem em `f3_sem_facta` do
dublê; o corpus as liga a uma persona `aprovado-NN` que **existe** lá (o caminho feliz serve a qualquer persona; o `f3` do dublê é só metadado).
As que não chamam a FACTA (P13, P32, P33, P35-P43, P45-P47, P49-P51, P53-P55, P60) e os estados globais (P30, P31) usam CPFs da faixa
reservada `000.000.075`-`098`, que o dublê não ocupa (o dublê cresce de baixo para cima; o `099` é dele): o validador recusa CPF do dublê
nelas, CPF repetido e CPF fora da faixa. Persona «sem FACTA» nunca chega ao T7/E7/E8 (regra `t7_so_com_oferta_facta`) e o gabarito só
produz os resultados de T7/T8 que o cenário do dublê da persona produz (regra `gabarito_cenario_duble`).

## O diálogo (gabarito)

Cada linha é um turno `{quem, fase_esperada, ...}`. O texto da IA **não** é fixado.

- `quem: "ia"`: `fase_esperada` (a fase DEPOIS do turno), `acoes_permitidas`, `acoes_proibidas`, `tx_esperado` (lista; só os compostos da
  lista fechada, como TX-02 + TX-03), `texto_livre_ia` (ponte do modelo, ≤ 1 TX), `evento` (vocabulário FECHADO: resultado de T7/T8, janela
  que abriu, lembrete, volta combinada...), `nota_esperada` (`nenhuma`, `TX-34`, `TX-35`, `NT-04`, `NT-07`...) e `motivo_e10` (só no primeiro
  turno E10), `campo_alvo` (em TX-07), `em_utc` (instante do turno; sem ele vale o último conhecido), `dispara_em_utc` (no TX-M08: quando a
  IA volta) e `invariantes` (as que o turno exercita). Turno da IA **sem** `tx_esperado` nem `texto_livre_ia` é silêncio e precisa de motivo
  (`evento`, aborto em E0, depois do E10 ou fora do horário) e de `enviar` proibido.
- `quem: "cliente"`: `fase_esperada` (a fase em que a mensagem chega), `texto_cliente` **ou** `midia`, `intencao_esperada`,
  `objecao_esperada`, `variacoes` (até 2 redações alternativas, escolhidas pela semente), `pii_digitada` (tipos de dado pessoal
  sintético que o texto traz: `cpf`, `telefone`, `email`, `cep`, `uuid`, `numero`) e `campo_alvo` quando entrega um campo da E5.
- Ações: `responder usar_ferramenta pedir_dado pedir_confirmacao aguardar repassar encerrar`, ferramentas `T1`..`T15`, `T7_mesma_chave`
  (retry com a mesma chave depois de TX-19), `enviar`, `nota`, `agendar`, `lembrete`. `T4` nunca é permitido (fora do MVP) e cada ferramenta só
  cabe na fase dela (H §2.3b). Toda mensagem da IA proíbe `valor_fora_placeholder` (I2), `ecoar_dado` (I5) e `promessa` (I9): são os
  tokens que o harness verifica na saída.
- A primeira linha é sempre da IA (abertura TX-01, ou o aborto em E0 de P54); só o caso (b) de M começa pelo Post do cliente. Dois turnos
  seguidos com mensagem da IA só com `evento` (I6). A fase da IA anda pelo grafo de H §2.1 e o cliente chega na fase em que a IA parou.
- **E5 completa:** antes do primeiro TX-11 o diálogo colhe recebimento (PIX **ou** conta), CEP, número e celular (`campo_alvo`), salvo o que
  `perfil.campos_no_360` diz que o 360 já tem.
- **SIM pelo texto:** SIM é explícito e isolado: o texto inteiro (sem acento nem maiúsculas, `!`/`.` no fim) é um de `sim`, `ss`, `confirmo`,
  `pode enviar`, `pode`, `isso`, `aceito`, `quero sim`, `pode sim`, `sim pode`. «sim?», «sim 👍», «sim, mas...», «acho que sim», «claro», «ok»,
  «bora» e «pode ser» NÃO são SIM e recebem TX-36 (confirmação), sem T7. Há diálogos de E6 ambíguo (TX-36), de «não» (volta à E4 com nova
  opção e novo TX-11) e de valores que mudam entre o SIM e o T7 (TX-12 e outro SIM), um deles no hold-out.
- **Janela de 24 h (P-R21):** mensagem da IA a mais de 24 h do último cliente só como template (TX-24); por isso P45 e P46 terminam em
  silêncio com `janela_24h_vencida`.
- **Agenda (M §2.4):** `dispara_em_utc` em seg-sáb 08:30-19:00 (sábado até 12:00), fora de feriado e DATAPREV, ≥ 10 min à frente, em até 23 h
  do último cliente, no máximo 2 por atendimento; a volta cai entre o horário combinado e +30 min.

## A semente

`semente.json` guarda a ordem das 60 personas, a ordem das 40, o hold-out e as sementes das 3 execuções por persona (vale também para as
P-M). Tudo sai de `semente_global` + sha256 (`chave(...)` em `ia_atendimento.corpus`); o validador recalcula e compara. A redação do
cliente em cada turno é `escolher_variacao(semente_global, id, execucao, indice_do_turno, 1 + len(variacoes))` (0 = `texto_cliente`). As `sementes` por execução
são para o provedor do modelo (variação da amostragem); a escolha da redação usa só `semente_global` + índice do turno. `chave(...)` é
`ia_atendimento.corpus.semente.chave`.
O hold-out (12 personas: 8 das 40 e 4 das 20 restantes, uma por classe) é avaliado à parte e **uma vez por versão**.

## O que o validador exige (`uv run python -m ia_atendimento.corpus`)

Esquema Pydantic `extra='forbid'`; ids e nomes únicos; CPF `000.000.0nn-dd` com DV certo e alinhado ao dublê; nomes só com sobrenome da
lista de inventados; as 40 da F3 curta exatas, cada uma e cada P-M crítica com diálogo; hold-out sem esqueleto de diálogo nem roteiro do cliente (fase, intenção) repetidos e com menos de 25% das falas específicas iguais às do desenvolvimento; cada invariante I1-I9 em ≥ 3 personas (também fora do hold-out);
toda fase E0-E10, intenção, objeção, EM1-EM9 e cada cenário de tempo/comportamento exigido cobertos, e (nos diálogos) toda objeção e fase com turno, cada intenção com ≥ 2 turnos, ≥ 8 turnos de texto livre do modelo (inclusive no hold-out), TX-36 e TX-12 com turno; falas variadas (≥ 75% distintas); **nenhum** CPF de DV válido fora de
`000.000.0nn`, celular fora dos sintéticos, e-mail fora de `.test`, e todo dado pessoal digitado declarado em `pii_digitada`
(a varredura usa `mascara.py`); nenhum `{{placeholder}}` fora do conjunto fechado dos TX nem TX inexistente; o gabarito não permite
T7/T4 sem confirmação (I1), reenvio depois de indeterminado (I4), mensagem fora do horário (I3), duas mensagens por turno (I6), mais de
24 turnos (I7), nota errada (I8); desfecho da persona igual ao fim do diálogo; falas curtas e pouca mídia.

## Como acrescentar uma persona

1. Escolha o id (P-nn só se for trocar uma das 60; novas entram como P-M ou numa família nova com ajuste de `conjunto_f3_curta`). Persona que
   o harness roda (F3 curta ou `critica: true`) precisa de diálogo.
2. Se há persona no dublê (`bancos-duble/personas/personas.yaml`), use o CPF dela e atualize `duble_personas.json`; senão, o próximo
   `000.000.0nn-dd` livre (calcule o DV: o validador confere) e `cenario_facta.sem_chamada_facta: true`.
3. Preencha todos os campos (o esquema recusa campo a mais ou enum desconhecido) e escolha um sobrenome da lista `SOBRENOMES_FICTICIOS`.
4. Se for da F3 curta, escreva `dialogos/<id>.jsonl` seguindo o gabarito acima; copie um diálogo parecido e ajuste.
5. Recalcule a semente: `uv run python -m ia_atendimento.corpus --semente` imprime a ordem, o hold-out e as sementes derivados; cole em
   `semente.json` (o validador `semente_reprodutivel` diz o que diverge). Mudar a lista de personas pode mudar o hold-out.
6. `uv run python -m ia_atendimento.corpus` (a partir da raiz do repo; `--raiz DIR` troca) e `uv run pytest tests/test_corpus*.py` até passar.

Dado real nunca entra: nem CPF, nem telefone, nem nome, nem trecho de conversa (extraia só a forma, ver `levantamento/09`).

## Para o harness (B8.1b/B8.2)

- O estado do WireMock do dublê é **global por nome de persona**: P24 e P28 dividem `indet-criada-5min`, e cada persona roda 3 vezes. Rode
  `scripts/cenario.py reset` do bancos-duble entre execuções (o corpus não marca reset por persona).
- `pessoas_teste` (B2.4) por persona **não** está no corpus: fica para a B2.4, que liga o CPF de cada persona à pessoa de teste do 360.
- Os resultados de T7/T8 por cenário estão em `vocabulario.EVENTOS_POR_PERSONA_DO_DUBLE`/`EVENTOS_POR_CENARIO_DO_DUBLE`.
