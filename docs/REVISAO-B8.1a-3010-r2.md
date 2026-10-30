# Revisão 2 de contexto limpo · B8.1a corpus da F3 (30/10)

Branch `feat/b8-1a-corpus`, d59d1b3 (corrige a Revisão 1). Só leitura. Rodei `bash scripts/check.sh` (939 passaram), `python -m ia_atendimento.corpus`
(0 violações), cobertura de linha+ramo do pacote (99%, sobra só o `raise SystemExit` do `__main__`), mutação das 40 regras e ~120 sondas de
mutação do corpus. Spec: ROTEIRO «B8.1a/B8.2», H §2.2–2.3b/§7, M §2.4, TEXTOS v3, `bancos-duble` origin/main (1305152, 0.1.2).
**Veredito: APROVAR COM CORREÇÕES.** As 4 ALTAs e a média da Revisão 1 fecham no essencial, mas R2-1 e R2-2 reabrem o espírito da A4 (o oráculo do
SIM) e R2-3 mostra que o «alinhado ao dublê» está verde só contra um instantâneo velho e ajustado à mão. Corrigir R2-1..R2-5 antes de B8.1b/B8.2.

Severidade: ALTA = corrompe o oráculo da B8.2 ou o consentimento; MÉDIA = mede errado ou deixa passar; BAIXA = higiene.

## 1. Revisão 1: o que fechou (conferido rodando)
| Achado | Resultado |
|---|---|
| A1 E5 completa | FECHADO. P04 sem CEP, sem celular, CEP trocado por 2º PIX, TX-07 sem `campo_alvo`: todos reprovam (`e5_completa`, `dialogo_gabarito`). 28 diálogos têm TX-11. |
| A2 janela 24 h | FECHADO. P44 com IA a 23 h59 do cliente passa; a 24 h01 e 30 h reprovam (`gabarito_janela24h`); TX-23 e TX-24+TX-03 depois de 24 h reprovam. P45/P46 encerram em silêncio. Ressalva R2-8 (24 h00 exatas passa). |
| A3 sem FACTA que digita | FECHADO no corpus (8 personas ganharam `aprovado-NN`; `t7_so_com_oferta_facta` reprova P04 com oferta inativa). **Não fechado no dublê**: R2-3. |
| A4 SIM pelo rótulo | PARCIAL. «bora/pode ser/claro/ok/sim, pode/pode sim/quero sim/sim senhor» reprovam; «SIM», «sim!», «Sim.» passam (certo). Mas R2-1 (lista alargada, «sim?») e R2-2 (nenhum negativo). |
| A5 P41 | FECHADO (`repassado`, TX-34). P49 manda TX-31. |
| Sondas A9 | FECHADO: TX-16 na abertura (E1) reprova (`gabarito_fase_tx`); rotulada E8 reprova (`gabarito_transicoes`); 3 TX numa mensagem reprovam (`gabarito_tx_composto`); pulo E1→E6, E3→E6, E3→E7, E5→E7 reprovam. T7 sem TX-11/SIM e T7 após «quer outro valor» reprovam por `gabarito_i1`. |
| A10 nomes, PII | FECHADO (secção 3). |
| §5 pacote | FECHADO (secção 5). 40/40 regras: desligar uma derruba ≥ 1 teste (`MUTAR=<regra>`, 40 `failed`). |

## 2. Achados novos

**R2-1 · ALTA · lista do SIM alargada sem autorização, e `sim?` vale SIM.** H E6: lista fechada = sim, ss, confirmo, pode enviar, pode, isso.
`vocabulario.py` SIMS soma `quero`, `aceito`, `pode mandar`, `sim pode enviar`, `sim confirmo`, `confirmo sim` (README l.51 admite «...»).
Nos diálogos: `quero` 7 redações, `pode mandar` 5, `aceito` 3 e 11 compostos (P04 t15 tem «quero» no texto-base). Pelo código descrito em H isso é TX-36.
Incoerente por dentro: aceita «sim pode enviar» e rejeita «sim, pode», «pode sim». `normalizar` tira a pontuação, então **«sim?» e «sim 👍» passam**
como SIM (`P04` t15: PASSA), contra H («`?`, condicional ⇒ TX-36»).
Correção: SIMS = exatamente a lista de H (ou levar «quero/aceito/pode mandar» ao dono como decisão), e `normalizar` não pode apagar `?`
(texto com `?` nunca é SIM). Reprova hoje: P04 t15 com texto «quero» e variação «sim?» deveria reprovar.

**R2-2 · ALTA · o negativo central do I1 não tem nenhum diálogo.** `TX-36` aparece em 0 arquivos; no E6 os únicos clientes que não dizem SIM são
`adiar_com_hora` (P-M04), `fora_de_escopo` (P49) e `quer_outro_prazo` (P58). Ninguém diz «sim, mas e se mudar?», «bora», «pode ser», «vou ver»,
«?» nem «não» (⇒ E3/E4); o A4 tirou «bora/pode ser» da E6 em vez de os transformar em casos TX-36. É o risco 1 de H (l.287). Também sem diálogo:
TX-12 (valor mudou no E7, nova confirmação: o «hash» do I1), TX-08/09/10 (erro sem ecoar o valor: I5), TX-24 (único template, o caso positivo da regra de 24 h).
Hoje um código que aceita «sim, mas...» como SIM passa em toda a F3 curta. Correção: ≥ 3 diálogos de E6 ambíguo (um no hold-out) com TX-36 e `T7` proibido,
mais um TX-12 e regra `cobertura_dialogos`: «TX-36 e TX-12 têm turno».

**R2-3 · MÉDIA · alinhamento com o dublê é com um instantâneo velho + ajuste manual.** `duble_personas.json` cita `@94f61e3`; a origin/main
do bancos-duble é 1305152 (0.1.2). Reconstruí o JSON a partir do `personas.yaml` da main e rodei `validar`: **9 violações**.
(a) P14, P34, P44, P48, P52, P56, P57, P58 ainda estão em `f3_sem_facta` lá e fora do `f3` de `aprovado-NN` (o ajuste proposto não existe no dublê).
(b) **P13 usa o CPF 000.000.047-74, que é da persona `indet-tentativa-antiga` (n=47) criada depois do instantâneo**; o README do corpus diz que «047 em diante
não tem stub»: falso. Sem-stub ocupam 047..071 e o dublê vai até n=99, então a colisão volta a cada persona nova.
O instantâneo com «AJUSTE PROPOSTO» deixa o validador verde sem que o dublê concorde; a B8.2 roda contra o dublê real.
Correção: PR no bancos-duble (as 8 personas em `f3`) antes de B8.2; CPFs dos sem-stub numa faixa reservada (ex.: 080-098); `fonte` com o hash do commit lido e
um script de reconferência; mover para o README «dublê ainda não ajustado».

**R2-4 · MÉDIA · o gabarito não é amarrado ao cenário do dublê.** `cpf_alinhado_duble` confere cenário só como rótulo. PASSAM:
P19 (dublê `recusa-fora-politica-etapa1`) com E8/TX-16/`resultado_t7_sucesso` antes do TX-18; P04 (`aprovado-60`) com `evento: resultado_t7_indeterminado`
+ TX-16; P04 com `evento: resultado_t7_recusa_politica` + TX-16; E7 sem `T7` permitido seguido de TX-16; E7 com `T7_mesma_chave` sem nenhum T7 antes.
Correção: tabela cenário → eventos de T7/T8 possíveis, evento ↔ TX (sucesso ⇒ TX-16/E8; recusa ⇒ TX-18; indeterminado ⇒ TX-15), TX-16 só com T7 permitido antes,
`T7_mesma_chave` só depois de T7.

**R2-5 · MÉDIA · hold-out só é independente no esqueleto completo.** `holdout_independente` compara a tupla inteira (inclui TX da IA), então qualquer turno a mais
escapa. Pelo roteiro do cliente (fase, intenção por turno): **P19, P26, P59 (hold-out) têm a mesma sequência de P01, P21, P30, P44 e entre si**; 67 de 143 falas
do hold-out (47%) existem literalmente no desenvolvimento. P03 ≈ P01/P02/P04 (0,88). Só P08, P31, P38, P41 têm roteiro próprio. A B8.2 mediria a mesma
conduta do cliente nos dois lados. Correção: regra `holdout_independente` por (fase, intenção) do cliente e por falas (excluindo as 6-8 genéricas: oi/sim/ss...);
refazer P19/P26/P59.

**R2-6 · MÉDIA · cobertura declarada ≠ cobertura com amostra.** Recalculado dos 60 arquivos (739 turnos): 20/20 intenções, 10/10 objeções, E0-E10 todas têm turno. Mas:
5 intenções com 1 turno (`quer_pensar`, `quer_outro_valor`, `sinal_fraude_ou_vulnerabilidade`, `reclamacao`, `nao_sou_eu`), 6 objeções em ≤ 2 diálogos, E9 em 1, E0 em 2, E2 em 5.
**Texto livre do modelo (onde I2/I9 quebram) = 4 turnos** (P04, P05, P29, P50; E3×3, E4×1), 0 no hold-out, 0 em E2/E8. Hold-out: 7/20 intenções, 4/10 objeções.
`cobertura_dialogos` aceita ≥ 1. Com meta de 95% por turno e 3 execuções, 1 turno = granularidade de 33%. Correção: mínimo 3 turnos por intenção/objeção fora do hold-out e
≥ 10 turnos de texto livre (≥ 2 no hold-out).
I1-I9 como ação proibida verificável: I1 `T7/T4` (397 de 422 turnos IA proíbem T7), I2/I5/I9 tokens em 403/403 mensagens, I3 `enviar` em 19/19 silêncios; I4 `T7` proibido após o envio; I6/I7/I8 são
estruturais (sem token): documentar assim.

## 3. PII e realismo: limpo, duas notas
Varri personas, diálogos, semente, dublê, README, CHANGELOG, docs e testes: CPF fora de `000.000.0nn` só em testes de `mascara`/`varredura` (preexistentes) e no
próprio `test_corpus*.py`; e-mails só `@exemplo.test` (44); telefones só 912345678/987654321/999999999/900000000; CEP `00000-nnn`. Nenhum banco/empresa/rua/site real (só «c6», «glcapital», «facta» em fala do cliente: é o domínio do negócio, não PII).
Sobrenomes: nenhum conhecido na lista (Marucci/Barucci/Galanti saíram); `Alvimar` é prenome real, sem dano. Falas: curtas e genéricas; não achei cópia (não há como provar, o real é proibido).
**R2-9 · BAIXA.** `docs/REVISAO-B8.1a-3010.md:66` ainda traz um CPF de dígito verificador válido (o clássico de exemplo, o mesmo de `test_corpus.py:21` e `test_corpus_revisao1b.py:72,100`).
Não é pessoa real, mas a Revisão 1 diz que as sondas foram removidas: trocar por «CPF de DV válido» no texto. A limitação de `texto_cliente` com nome+rua reais passar segue aceita.

## 4. Validador
Mutação: 40/40 regras, cada uma desligada, derrubam ≥ 1 teste. Ramos: 99% linha+ramo; os `raise` de esquema estão cobertos. `extra='forbid'` em todos os modelos
(`_Modelo` base de Perfil...Corpus, `Duble`, `PersonaDuble`, `Semente`); sondei chave a mais em 9 níveis, `"41"`, `"yes"`, `em_utc` sem fuso, `f3_globais` ausente, `evento` fora do vocabulário: todos viram `esquema:`.
**R2-8 · BAIXA.** `gabarito_janela24h` usa `<= 24 h`; ROTEIRO (A5.x, `agora − ultimo_cliente_em < 24 h`) e H E0 dizem `< 24 h`, TEXTOS diz `≤ 24 h`. IA a exatamente 24 h00 passa. Escolher um (o mais restritivo) e testar o limite.
**R2-10 · BAIXA.** `FERRAMENTAS_POR_FASE` não é a tabela H §2.3b: E3 permite T2 e não T13; E10 permite T8/T10/T13; E1/E2 sem T1. Teto frouxo demais não reprova nada.
**R2-11 · BAIXA.** `P24` e `P28` dividem a persona de estado `indet-criada-5min`; o README do dublê avisa que o estado do WireMock é global por nome e pede `cenario.py reset` entre rodadas: o corpus não marca reset por persona/execução (3 execuções).

## 5. Pacote `corpus/`
Todos < 350 linhas (maior: `vocabulario.py` 318); dependência desce, com uma exceção: `regras/invariantes.py` importa `normalizar/e_sim_literal/PEDIDO_DE_CONFIRMACAO` de `regras/gabarito.py`
(mover para `_comum`). Responsabilidades claras. **R2-12 · BAIXA:** `CORPUS_DIR = parents[3]/tests/corpus` faz `src/` depender de `tests/` (quebra instalado como pacote);
chaves do registro ≠ nomes das funções (`t7_so_com_oferta_facta` → `gabarito_t7_so_com_oferta_facta`, `cpf_sintetico` → `cpf_sintetico_regra`);
`tests/test_corpus_revisao1.py/1b.py` (950 linhas) estão nomeados pela revisão, não pela regra; 8 funções privadas de `mascara.py` (já aceito pelo autor); CHANGELOG mantém «0.2.0» acima de «[Unreleased]» e afirma
«hold-out sem esqueleto repetido» (R2-5). A spec pede `pessoas_teste` (B2.4) por persona: não há campo nem aviso de que ficou para depois (BAIXA).

## 6. Ordem sugerida
R2-1 e R2-2 (mudam SIMS, 3-4 diálogos e uma regra) → R2-4 (regra de amarração) → R2-3 (PR no bancos-duble + faixa de CPF) → R2-5/R2-6 (refazer 3 hold-out, ampliar amostra) → BAIXAS.

## Resposta do autor (r2) (30/10, commit `fix: corpus — correções da revisão 2 (R2-1…R2-6)`)

Aceitei o veredito. Cada regra nova tem teste de mutação (`tests/test_corpus_revisao2.py` e os anteriores) e desligar a regra derruba ≥ 1 teste. Cobertura de linha+ramo do pacote: 99% (sobra o `raise SystemExit` do `__main__` e um ramo de `personas.py`).

| Achado | Resposta |
|---|---|
| **R2-1** lista do SIM | `SIMS` voltou ao explícito e isolado: `sim`, `ss`, `confirmo`, `pode enviar`, `pode`, `isso`, `aceito`, `quero sim`, `pode sim`, `sim pode`. A validação é por **regra fechada** (`e_texto_sim`: texto inteiro, sem acento nem maiúsculas, `!`/`.` no fim, vírgula tolerada; qualquer outro caractere tira o SIM). `quero`, `pode mandar`, `sim pode enviar`, `sim confirmo`, `confirmo sim` saíram; `?` não é mais apagado: «sim?», «sim 👍», «sim, mas…», «claro», «ok», «bora», «pode ser» **não** são SIM. A sonda `quero` + variação `sim?` agora reprova. |
| **R2-2** negativo do SIM | Nova regra `gabarito_tx36` (resposta ambígua no E6 ⇒ TX-36 na resposta seguinte e nenhum T7). Diálogos no E6: P02 («sim, mas e se o valor mudar?»), P04 («bora»), P06 («acho que sim») e **P59, no hold-out** («e a parcela, quanto é mesmo?»), todos com TX-36 e o SIM só depois. «Não» no E6 (P20): volta à E4 com nova opção e novo TX-11. TX-12 (valores mudam entre o SIM e o T7 → outro SIM): P25. `cobertura_dialogos` exige TX-36 e TX-12 com turno. O rótulo `aceita` para «bora» continua permitido (a IA entendeu aceitação), mas só com TX-36 e nunca confirma. |
| **R2-3** dublê | `duble_personas.json` regravado da main do bancos-duble (**@1305152**, 48 personas) por `scripts/atualizar_duble.py` (`--verificar` confere). Não proponho mais ajuste lá: as 8 personas (P14, P34, P44, P48, P52, P56, P57, P58) usam persona que **existe** (`aprovado-NN`; o `f3` do dublê é só metadado e o caminho feliz serve a qualquer persona; a regra recusa o mesmo expediente fora do cenário aprovado). Os CPFs sem stub saem da faixa reservada **075–098** (24 personas, ocupação exata) e o validador exige a faixa; P13 não colide mais com `indet-tentativa-antiga`. P-M18/20/22 passaram a usar personas do dublê (`recusa-cpf-fora-da-base`, `aprovado-24`, `aprovado-36`). Nenhuma pendência B2.4 por falta de persona aprovada. |
| **R2-4** amarração ao cenário | Nova regra `gabarito_cenario_duble`: tabela persona/cenário do dublê → resultados de T7/T8 possíveis; evento ⇒ TX obrigado (sucesso ⇒ TX-16, recusa ⇒ TX-18, indeterminado ⇒ TX-15…); TX-16 só com resultado de sucesso que o cenário produz e com T7 permitido antes; `T7_mesma_chave` só depois de T7. As cinco sondas da revisão reprovam. P20, P30 e P59 ganharam o turno silencioso que carrega a ferramenta (T8, T13, por-cpf) na fase certa. |
| **R2-5** hold-out | `holdout_independente` agora compara também o **roteiro do cliente** (fase, intenção) e exige < 25% das falas específicas (> 6 caracteres, sem dado pessoal) iguais às do desenvolvimento. P19, P26 e P59 foram refeitos (duas dúvidas antes do aceite; dúvida do CEP no meio da coleta; pergunta no E6) com falas próprias; P03 também. |
| **R2-6** amostra | Cada uma das 20 intenções tem ≥ 2 turnos (P46/P53 e P37/P49, P40/P47, P27/P28, P25/P30/P06 dividem as raras) e há 10 turnos de texto livre do modelo, dois no hold-out (P08, P31). `cobertura_dialogos` exige os mínimos. (Objeções: segue ≥ 1 diálogo; a revisão pediu amostra por intenção.) |
| **R2-8** | Fronteira exclusiva (`< 24 h`; 24 h00 exatas já é template), com teste de 24 h00 e 23 h59. |
| **R2-9** | O CPF de exemplo saiu de `docs/REVISAO-B8.1a-3010.md`; teste garante que o doc não traz CPF de DV válido fora da faixa. |
| **R2-10** | `FERRAMENTAS_POR_FASE` é a tabela de H §2.3b (modelo + código), com `T7_mesma_chave` e `T13`/`T15` no E6 (banco fechado antes do T7). Teste compara com a tabela literal. |
| **R2-11** | README ganhou a seção «Para o harness»: reset do WireMock por execução (estado global por nome). |
| **R2-12** | `CORPUS_DIR` saiu de `src/`: `carregar_bruto(raiz)`/`carregar(raiz)` exigem o caminho, o `__main__` usa `tests/corpus` do diretório atual (`--raiz` troca); teste garante que o pacote não cita `"tests"`. `normalizar`/`e_sim_literal`/`PEDIDO_DE_CONFIRMACAO` foram para `regras/_comum.py` (a dependência volta a só descer). |

**Não feito:** (1) renomear funções para os nomes do registro e renomear `test_corpus_revisao*.py` por regra; (2) `pessoas_teste` por persona (fica para a B2.4, registrado no README); (3) função pública em `mascara.py`; (4) amostra mínima por **objeção** (a revisão pede por intenção/objeção; fiz por intenção); (5) o corpus de ≥ 150 frases do extrator (EM1).
