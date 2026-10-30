# Revisão de contexto limpo · B8.1a corpus da F3 (30/10)

Branch `feat/b8-1a-corpus` (c409ada sobre origin/main). Só leitura. Spec: ROTEIRO «B8.1a», «B8.2», §0.6 padrão 6; estudos H, M, L, D; TEXTOS v3.
Rodei `bash scripts/check.sh` (802 passaram), `python -m ia_atendimento.corpus` (0 violações) e ~60 sondas de mutação (scripts no scratchpad da sessão).
**Veredito: APROVAR COM CORREÇÕES.** Mecânica boa (regras reais, nenhuma PII encontrada). O gabarito, porém, tem erros de conteúdo que fariam
a B8.2 punir o comportamento certo, e o validador não os vê. Corrigir A1–A5 antes de B8.1b; o resto pode entrar junto.

Severidade: ALTA = corrompe o oráculo da B8.2 ou o consentimento; MÉDIA = mede errado ou deixa passar; BAIXA = higiene.

## 1. PII e realismo: nada a bloquear
- Varri personas, diálogos, semente e dublê: só `000.000.0nn`, `a@exemplo.test`, `(11) 91234-5678`, UUID `00000000-…`, CEP `00000-001`, conta `0000123-4`.
  Nenhuma sequência de ≥ 8 dígitos fora disso; sem banco, empresa, rua ou site reais (só «facta»).
- Frases: curtas e genéricas («oi», «pode ser», «ta caro»). O levantamento 09 só tem tamanhos, e o corpus real não foi aberto (proibido); logo não há como ter cópia, só a forma.
- **A10 BAIXA (nomes).** `nome_ficticio` confere só o último token. Sobrenomes que existem de verdade: **Marucci** (P-M20), **Barucci** (P-M13), **Galanti** (P34). Com primeiro nome comum (Cecilia Galanti) soa pessoa real. Trocar os três.
- **A10b BAIXA (diversidade).** 160 falas do cliente, 59 textos distintos: «oi» 35×, «pode ser» 25×, «sim» 25×, `a@exemplo.test` em 16 dos 27 PIX. Em 33 de 160 turnos as 3 execuções caem na mesma redação (hash, sem garantia de cobrir as variações). A meta de 95% de intenção fica quase de graça.
- **varredura.py (A11 BAIXA). Sem brecha de CPF real.** 5 CPFs de DV válido gerados ao acaso (omitidos aqui: a própria varredura os acusaria), formatados e crus: **10/10 ACHADO**. Também acha um CPF de base 123 (fora da faixa 0000000nn) e passa o de base 099 (esperado). Real nunca começa com 7 zeros (base < 100). Ressalvas: a isenção vale para o repositório inteiro (limitar a `tests/corpus`) e sequência > 11 dígitos nem casa o regex (já era assim).

## 2. Gabarito errado (os achados que importam)

**A1 · ALTA · E5 colhe 1 campo em vez de 4.** H §2.3 E5: recebimento + CEP + número + celular, «Sai: `faltam=[]` ⇒ E6». Só `P01.jsonl` faz os 4 (pix, cep, numero_endereco, celular).
Os outros **26 de 27** diálogos que chegam a E6 vão de uma só fala (PIX ou conta) direto ao TX-11: P02–P07, P19–P31, P44, P45, P48, P49, P57–P59. A B8.2 vai reprovar o código certo (que pergunta CEP) ou ensinar o fluxo errado.
Hoje nenhuma regra exige completude da E5. Correção: gabarito completo (TX-07 ×4) ou campo `perfil.campos_no_360` e regra «E6 só com faltam=[]».

**A2 · ALTA · P45 e P46 respondem fora da janela de 24 h.** TEXTOS L27/L79 e ROTEIRO E0 v3: texto livre só com < 24 h do último cliente, depois só template (e só o TX-24 é template).
`P45.jsonl` t5 (TX-02+TX-07, seg 08:00) vem 36 h depois da fala de sáb 20:01; `P46.jsonl` t3 (TX-02+TX-03, 23/11 08:00) vem ~70 h depois da fala de 20/11. `gabarito_i3` só olha o relógio de parede.
Correção: regra `gabarito_janela24h` (mensagem de texto livre/TX ≤ 24 h do último `cliente`) e refazer os dois (silêncio + E9/E10, ou template). Reprova hoje: nada.

**A3 · ALTA · «sem FACTA» que digita.** P44, P45, P48, P57, P58 (todas da F3 curta) têm `sem_chamada_facta: true`, sem persona do dublê, e mesmo assim `T7` + TX-16 + `vendeu`.
O `resumo` do P54 diz que sem FACTA a conversa «termina antes de T4/T7»; na camada B o T7 desses CPFs cai em stub inexistente. Sem diálogo, mas com E7 e `sem_facta`: P14, P34, P52, P56.
A origem é a lista `f3_sem_facta` do dublê (o snapshot bate 100% com `origin/main@94f61e3`, conferi): o erro é de cruzamento, e `cpf_alinhado_duble` só compara com o snapshot.
Correção: dar a essas personas um `aprovado-NN` (e ajustar o `f3` do dublê) ou cortar o diálogo antes do T7; regra nova «T7 permitido ⇒ `persona_duble` não nulo».

**A4 · ALTA · SIM fora da lista fechada.** H E6: lista fechada (sim, ss, confirmo, pode enviar, pode, isso) + posterioridade ao TX-11.
`P04.jsonl` t7 (E6, `aceita`) tem as redações **«bora»** e **«pode ser»**; `P02.jsonl` t7 tem «confirmo, pode mandar». Pelo código real isso é TX-36, não T7.
`gabarito_i1` confia no rótulo `intencao_esperada=aceita`: sonda com texto `sim mas e se o valor mudar?` rotulado `aceita` e T7 permitido **passa**. Correção: em todo turno E6 que antecede um `T7`, toda redação ∈ lista fechada; mover «bora/pode ser» para a E3.

**A5 · MÉDIA · P41 desfecho errado.** `personas.jsonl` L41: `encerrado_sem_interesse`, mas o diálogo faz T12 + nota TX-34 + TX-25 («deixo com um consultor»), e a Q5 padrão (TEXTOS L37) é «encerra e repassa com nota». P08 (mesma `recusa_firme`) está como `repassado`.
A causa é `corpus.py:966`, que mapeia `recusa_firme → encerrado_sem_interesse` e torna `desfecho_coerente` circular. Correção: P41 → `repassado`; deixar só `opt_out` e `identidade` na linha 966.

**A5b · BAIXA.** P49 t8: «digite sem eu confirmar» recebe TX-36; H §2.4 manda TX-31 (T15 bloqueia). P46 está certo (lembrete 4 h = TX-23, v3); conferi contra TEXTOS e não é erro.

## 3. Cobertura real × declarada
Recalculada dos arquivos. As regras `cobertura_*` contam personas (84), inclusive as 44 sem diálogo, e o relatório não distingue.
- **Invariantes** (personas que declaram / turnos de diálogo que marcam): I1 27/27, I2 21/39, I3 28/39, I4 20/25, I5 11/32, I6 20/40, I7 15/40, I8 36/22, I9 13/37. Todos ≥ 3 também fora do hold-out; ok. Mas só I1, I3, I4, I6, I7, I8 têm regra sobre o gabarito. **I2, I5, I9 são rótulos** (nada os verifica), e `texto_livre_ia` é `true` em 0 turnos (o caminho do texto livre do modelo, onde I2/I9 quebram, não é exercitado).
- **Nos 40 diálogos que a B8.2 roda:** 7 de 20 intenções sem nenhum turno (duvida_oferta, quer_outro_valor, quer_outro_banco, sinal_fraude_ou_vulnerabilidade, ininteligivel, adiar_com_hora, adiar_sem_hora); 7 de 10 objeções sem turno (só parcela_alta, prazo_longo, outra); fases: E0 1, E2 3, E4 5, E9 1 diálogo.
  Noite/sábado/feriado só em P44–P46; `virada_dataprev`, `virada_22h30_utc` e domingo só em P-M **sem diálogo**.
- **TX nunca esperados:** TX-06, 08, 09, 10, 12, 13, 17, 21, 22, 24, 28, 32, 33, 39, 41 (P15–P18, P55/P56 ficam fora por C5; ainda assim TX-12/13 e TX-24 são o núcleo de I1/E9).
- **Hold-out contaminado (A6 MÉDIA).** Esqueleto idêntico (fase, TX, intenção por turno): **P19** (hold-out) = P20 = P22 (dev); **P31** (hold-out) = P24 = P27 (dev). P03 (hold-out) divide o dublê `aprovado-48` com P06 (dev); P08 com P04/P07 (`aprovado-60`).
  Ajustar P20/P22/P24/P27 mexe no hold-out sem querer. Sem persona f3 «clone» de não-f3 com outro nome, mas P09≡P12, P24≡P28 e P47≡P50 são clones dentro do dev. Correção: regra `holdout_independente` (esqueleto e persona do dublê únicos) e redesenhar os diálogos.
- **Escopo (A8 MÉDIA).** B8.1a «Conferir: cada persona tem gabarito por turno»; há 40/84. As 20 P-M críticas, que a rodada de 13/11 exige (B8.2), não têm diálogo (README: «ganham diálogo em B8.2», empurra a escrita para o dia da rodada).
  EM1 pede corpus de ≥ 150 frases com hold-out (M L249): há 0. EM1/EM3/EM4/EM9 são testes de infraestrutura e entram como etiqueta em persona, então `cobertura_em` mede rótulo. A spec manda `evals/`; o dado está em `tests/corpus` e `corpus.py` (em `src/`) lê `tests/` (`corpus.py:31`).

## 4. Validador
**Mutação real.** Desliguei cada uma das 26 regras (`REGRAS[x] = lambda c: []`): **26/26 derrubam ≥ 1 teste**. Não há regra morta. Corpus vazio: `conjunto_f3_curta` e `f3_com_dialogo` seguram (17 regras ficam vazias, ok).
**Ramos sem teste (18).** Linhas 578–593 (5 ramos de `cpf_alinhado_duble`), 604, 791, 802, 806, 808, **812 (IA fala depois do E10)**, 817, **874 (`T7_mesma_chave` sem TX-19)**, 939, 948, 952, **1022 (mídia > 10%)**, 1036, mais 12 `raise` de esquema (228–337). Todos funcionam em sonda manual, mas o README promete «um caso que reprova por regra» e ramo sem teste vira regressão silenciosa.

**Sondas que PASSAM e deviam reprovar (A9 MÉDIA):**
| Mutação | Resultado |
|---|---|
| `T6` em turno E3; `T5` em E5 (`P01` t2/t4) | passa: não há `ACOES_POR_FASE` nem tabela H §2.3b |
| TX-16 (link) na abertura E1; IA pulando E1→E8; fase do cliente incoerente com a IA anterior | passa: não há grafo de transição nem fase×TX |
| `tx_esperado=['TX-03','TX-05','TX-11']` (3 perguntas numa mensagem) | passa: I6 só vê 1 mensagem; «uma pergunta» não é checada |
| IA muda em horário (TX-03 removido) | passa: vira «silêncio» sem `evento` |
| P58 t10: SIM sem novo TX-11 depois da recusa | passa: `pedido` nunca zera em «não» (`_regra_gabarito_i1`, l.824) |
| IA→IA com `evento: "qualquer_coisa"` | passa: `evento` é `str` livre e isenta I6/I7 (l.326, 909, 918) |
| `evento` com CPF 529.982.247-25 e e-mail real; o mesmo em `duble_personas.json` e `semente.regras` | **passa** (só `texto_cliente`, variações e campos de persona são varridos para PII) |
| `texto_cliente` com «Joao da Silva do Banco Itau, Rua Augusta 100» | passa (nome/empresa/endereço fora do alcance, como a varredura admite) |
| conta real `000123456789` | passa: `_pii_nao_sintetica` aceita qualquer `numero` que comece por 000 (l.494) |

**`extra='forbid'` contornável (A9b).** `Corpus.duble: dict[str, Any]` e `Semente.regras: dict[str, str]` aceitam chave a mais; sem a chave `f3_globais` o validador **estoura `KeyError`** em vez de dar violação. Sem `strict`: `idade="41"` e `vinculo_clt="yes"` são coagidos. `classe`, `cenario`, `resumo` e `evento` são texto livre.

## 5. `corpus.py` (1.112 linhas): divisão proposta, sem executar
Pacote `ia_atendimento/corpus/` (todos < 200 linhas; `__init__.py` reexporta a API que `tests/test_corpus.py` já usa, então o teste não muda):
- `vocabulario.py` (Literals, `ACOES`, `TX_IDS`, `PLACEHOLDERS`, `F3_CURTA_IDS`, limites, ~120) e `calendario.py` (`dentro_do_horario`, `_cenario_do_instante`, ~60): sem dependência.
- `modelos.py` (Perfil … Corpus, ~200) e `carga.py` (`carregar_bruto/montar/carregar`, ~40).
- `semente.py` (`_chave`, `escolher_variacao`, `texto_do_turno`, `derivar_semente`, ~60) e `pii.py` (`achados_pii`, `_pii_nao_sintetica`, `cpf_sintetico`, ~90). Pedir a `mascara.py` uma função pública: hoje usa 8 privadas (`_vista_ascii`, `_trocas_de_digitos`, …).
- `regras/personas.py` (ids, nome, cpf×2, conjunto_f3_curta, f3_com_dialogo, cenario_tempo), `regras/cobertura.py` (6 `cobertura_*`, invariantes_do_dialogo), `regras/pii.py` (pii_texto, placeholder_fechado), `regras/dialogo.py` (dialogo_gabarito, forma_whatsapp), `regras/invariantes.py` (i1, i3, i4, i6, i7, i8, desfecho_coerente), `regras/semente.py`, e `regras/__init__.py` com `REGRAS` e `validar`.
- `__main__.py` (`main`). Dependência só desce (regras → modelos → vocabulário); mover os dados para `evals/corpus/` no mesmo corte. Ordem: calendário/vocabulário, modelos/carga, semente/pii, regras, `__main__`; `check.sh` entre cada passo.

## 6. Menores
`README` cita `chave(...)` público, o código tem `_chave`. As `sementes` por execução em `semente.json` não são usadas por `escolher_variacao` (só `semente_global` + índice); ok se são do provedor, dizer no README. CHANGELOG pôs «0.2.0» acima de «[Unreleased]». `Turno.objecao_esperada` aceito em turno da IA.

## Ordem de correção sugerida
A1, A3 (mudam diálogos e dublê) → A2 e A4 (regras novas + dois diálogos) → A5 (um campo e uma linha) → A6/A8/A9 → o resto.

## Resposta do autor (30/10, commit `fix: corpus — correções da revisão 1`)

Aceitei o veredito. O que mudou, na ordem do doc; cada regra nova tem teste de mutação (`tests/test_corpus_revisao1.py` e `…1b.py`) e **desligar a regra derruba pelo menos 1 teste**.

| Achado | Resposta |
|---|---|
| **A1** E5 com 1 campo | Todo diálogo que chega ao TX-11 colhe recebimento (PIX **ou** conta), CEP, número e celular. Regra `e5_completa` (aceita `perfil.campos_no_360`). 28 diálogos refeitos. |
| **A2** P45/P46 fora das 24 h | Regra `gabarito_janela24h` (mensagem da IA > 24 h do último cliente só como TX-24). P45 e P46 agora **encerram em silêncio** (`janela_24h_vencida`; P45 com nota TX-34 porque houve oferta, P46 sem nota); os dois viram `repassado`. O TX-02 continua exercitado em P44 (11 h depois do cliente). |
| **A3** «sem FACTA» que digita | P14, P34, P44, P48, P52, P56, P57 e P58 ganharam persona `aprovado-NN`; P45 continua sem FACTA e nunca passa do E3. Regra `t7_so_com_oferta_facta` (T7 ou fases E7/E8 exigem persona do dublê ou estado global **e** oferta ativa). **Pendência para o dono do bancos-duble:** o snapshot do corpus já reflete o ajuste (`fonte` diz «AJUSTE PROPOSTO»); o `personas/personas.yaml` do bancos-duble precisa do mesmo `f3` e sair de `f3_sem_facta` para essas 8. Não toquei no repositório dele. |
| **A4** SIM pelo rótulo | `e_sim_literal` valida o TEXTO e as variações contra a lista fechada; `gabarito_i1` confirma só com SIM literal e `gabarito_sim_literal` reprova os dois sentidos. «bora/pode ser» saíram da E6 (foram para a E3). O pedido também cai quando o cliente muda o pedido (`quer_outro_*`, recusa, objeção). |
| **A5** P41 | `repassado`; `recusa_firme` deixou de ser `encerrado_sem_interesse` na derivação (só `opt_out` e `identidade`; `ja_concluiu` vira `vendeu`). P43 e P-M08 acompanharam. **A5b:** P49 manda TX-31. |
| **A6** hold-out | Regra `holdout_independente` (esqueleto único; persona do dublê não dividida com o desenvolvimento fora do caminho feliz `aprovado`). P20, P22, P24, P27, P31 e P25 ganharam desenhos próprios (objeção antes, dúvida do prazo, «não lembro», mais valor, taxa com 503 que dá certo, «vou pensar»). |
| **A8** escopo | As 20 P-M críticas têm diálogo (agenda, pausa em E3/E5/E6/E8, reagendar, opt-out, já assinei, caso (b), 22:30 UTC, DATAPREV...). Regra `gabarito_agenda` (janela 08:30-19:00, sábado até 12:00, ≥ 10 min, ≤ 23 h do cliente, ≤ 2 agendamentos, volta entre o combinado e +30 min). **Não feito:** o corpus de ≥ 150 frases do extrator (EM1) é do teste do extrator, não do corpus de personas; EM1/EM3/EM4/EM9 seguem como etiqueta de persona. **Não movi** os dados para `evals/corpus/` (o coordenador mandou manter `tests/corpus`). |
| **A9** sondas | Fechadas: `gabarito_acoes_por_fase` (T6 só na E5...), `gabarito_fase_tx` (TX-16 na abertura), `gabarito_transicoes` (pulo de fase e cliente fora da fase da IA), `gabarito_tx_composto` (lista de compostos), `gabarito_silencio` (silêncio com motivo), `evento` em vocabulário fechado (Literal), PII varrida em **todo** campo (turnos da IA, `duble`, `semente.regras`, notas), conta com dígitos de verdade recusada, `duble` e `regras` como modelos estritos (chave a mais ou faltando vira `esquema`, nunca `KeyError`), tipos estritos (`"41"` e `"yes"` recusados), `classe`/`cenario` em vocabulário. Cobertura de linhas do pacote: 99% → 100% (as linhas que sobraram eram `raise` de esquema e o `__main__`, agora testados). |
| **Cobertura real** | Nos diálogos: toda intenção (20/20), toda objeção (10/10), toda fase E0-E10 e todo cenário de tempo têm turno (`cobertura_dialogos`). **I2, I5, I9** viraram ações proibidas que o harness verifica em toda mensagem da IA (`valor_fora_placeholder`, `ecoar_dado`, `promessa`) e há 4 turnos de **texto livre do modelo** (ponte), onde I2/I9 quebram. |
| **A10 / A10b** | Sobrenomes `-ucci` e `-anti` (Marucci, Barucci, Galanti e parentes) saíram da lista de inventados; 16 novos `-ovim`. Falas: `variedade_das_falas` (≥ 75% distintas); 209 textos distintos em 244 falas da F3 curta (era 59 em 160). |
| **§5** `corpus.py` | Virou o pacote `ia_atendimento/corpus/` exatamente como o §5 (vocabulário, calendário, modelos, carga, semente, pii, `regras/{personas,cobertura,pii,gabarito,invariantes,agenda,forma,semente}`, `__main__`); maior arquivo 318 linhas; a API que o teste usava continua em `ia_atendimento.corpus`. |

**Não feito / decisões:** (1) pedir a `mascara.py` uma função pública (hoje `corpus/pii.py` usa 8 privadas; tocar em `mascara.py` colide com as branches B1.x). (2) Limitar a isenção da faixa `000.000.0nn` da varredura a `tests/corpus` (A11 baixa): os próprios testes usam a faixa. (3) TX-08/09/10/12/17/21/22/24/28/39 ainda sem diálogo (P15-P18, P51-P52, P55-P56 ficam fora da F3 curta por C5).
