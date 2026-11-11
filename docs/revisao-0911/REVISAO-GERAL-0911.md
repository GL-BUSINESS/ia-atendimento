# Revisão geral da IA de atendimento: síntese final (10/11/2026)

## 1. Abertura

**Data.** 10/11/2026, noite (BRT). Os achados valem para os SHAs abaixo. No congelamento eles são reconferidos (`fase0/decisoes-delegadas.md` §2, «O que reconferir no congelamento»).

**Escopo (SHAs do `fase0/MANIFESTO.md`, 2026-11-10T09:00:20-03:00).**

| Repositório | Ref exportada | SHA | Arquivos | Observação |
|---|---|---|---|---|
| ia-atendimento | origin/main | `9a4bacab` | 257 | remoto = local |
| ia-atendimento | origin/feat/b1-6a (PR #13) | `9a714e39` | 243 | PR `CONFLICTING` com a main (MANIFESTO:92) |
| ia-atendimento | feat/esteira (local, sem push) | `9e1afe39` | 49 | ahead 2, behind 178 |
| ia-atendimento | kits/s4 (local, sem push) | `148cc72d` | 48 | ahead 1, behind 178 |
| bancos-duble | origin/main | `ca3ed2cf` | 101 | remoto = local |
| gl-gateway | origin/main | `92e97548` | 38 | remoto = local |
| facta-on | origin/main | `8c3e5abc` | 209 | remoto = local; PR #49 `CONFLICTING` |
| cliente360-api | origin/main | `6e9c62de` | 811 | remoto = local |
| cliente360-web | não exportado | remoto `9f0fc5f5` × local `cd4d9fc3` | — | pontas diferentes; fora da revisão |

Papel lido em `/opt/claude/docs/planejamento-ia/` (ROTEIRO v3.3, contratos vigentes sem sufixo, estudos). Kits copiados de `~/retomada-2809/fila-2910/ia/`. Produção, Kan, GitHub ao vivo, chatguru-api, ISKRA, gl-painel e cliente360-web **não foram lidos** (§10.7).

**Quem fez.** Workflows de agentes Claude, sem Codex. Leitores em Sonnet 5.5; julgamento e verificação em Fable 5.1/5.2 e Opus 5.5 (PLANO §8, «Decidido pelo dono em 10/11»), com Sonnet 5.5 também em parte da verificação das Fases 3b e 3d (Anexo A.1). O limite do Fable acabou às ~13:00 de 10/11; daí em diante os votos sem modelo fixo rodaram em Opus 5.5 (§10.6). Nada foi corrigido, mergeado nem publicado. Nenhuma sonda de produção tem saída gravada (§9, «Como ler»).

**Como ler.**

| Sigla | O que é | Fonte |
|---|---|---|
| `G-nnnn` | grupo de achado da Fase 3 (762 grupos, 3 votos cada) | `fase3/consolidado.json`; detalhe em `fase3/grupos/G-nnnn.json` |
| `F4-nnn` | achado da Fase 4 (leitores de lacuna L1–L6 e crítico de completude) | `fase4/consolidado-f4.json` |
| `R2-nnn` | achado da rodada 2 (5 passes dirigidos a pontos cegos) | `fase4/consolidado-r2.json` |
| `RG-nnn` | os 128 riscos da revisão de 04/11 | `fase0/inventario-rg.csv`; fechamento em `fase1/leituras/F1-53..F1-58.md` |
| `D-nn` | as 32 decisões do dono | `fase0/inventario-dnn.md`; fechamento em `F1-59.md` |
| `RS-nn` | as 34 restrições da matriz | `fase0/matriz-restricoes.md`; estado final no §7 |
| `DN-nn`, `SO-nn`, `RV-nn` | item do dono, sonda só-leitura, premissa nova | §9 |
| `ROT` | `/opt/claude/docs/planejamento-ia/ROTEIRO-DE-ACAO.md` v3.3 | — |
| `DEL` | `/home/danilo/ia-revisao-0911/fase0/decisoes-delegadas.md` | — |
| `fase*/`, `src/` | relativos a `/home/danilo/ia-revisao-0911/` | `src/` = exportação no SHA do manifesto |

- **Gravidade:** CRÍTICO, ALTO, MÉDIO, BAIXO, a final depois da verificação. **Não há CRÍTICO vivo** de código; os dois CRÍTICO abertos são RG de calendário (RG-041, RG-043; §8.2).
- **Estados:** «confirmado», «confirmado em parte», «não existe: critério de aceite» (peça ausente que vira aceite do bloco), «não verificável» (depende de produção; ver sondas no §9b).
- **«Reproduzido»** aqui quer dizer lido no código ou sondado em texto sintético. Nenhum teste «que reprova antes» foi rodado (F4-035).
- **Estimativa** marca toda conta de capacidade. Nenhuma etapa registrou horas reais (PLANO, Fase 5).
- Cada seção de 4 a 10 traz o seu próprio «Como ler» com os atalhos de caminho que usa.
- **Gravidade entre camadas.** O mesmo risco pode ter gravidade diferente por camada. Ex.: a VPS é CRÍTICO em RG-041 (risco de prazo da revisão de 04/11, `fase0/inventario-rg.csv:42`) e ALTO em G-0001 (peça ausente, gravidade final da Fase 3). Para ordenar o trabalho, esta síntese usa a mais alta.
- **Piso, não teto.** Os achados vivos são o que a revisão achou. O recall estrito nos canários foi 28 % (5/18) e o critério de parada da Fase 4 não foi atingido (§10.2, §10.3).

**Mapa do documento.**

| § | Conteúdo | Para quem executa |
|---|---|---|
| 2 | Veredito em 10 linhas | dono |
| 3 | Efeito no calendário e capacidade | dono, sessão principal |
| 4 | Ordem de ataque, dia a dia até 19/11, e ALTO sem data | sessão principal, agentes de construção |
| 5 | Achados de código: ALTO e MÉDIO (com e sem RS) | agente que corrige código |
| 6 | Papel, processo, estado; peças que não existem | sessão principal (emendas), blocos (aceite) |
| 7 | Matriz RS-01..RS-34, livro de retenção, inventário de segredos | revisor de segurança |
| 8 | 128 RG, 32 D-nn, 20 AJUSTAR | dono, sessão principal |
| 9 | O que depende do dono; sondas; premissas | dono, sessão principal |
| 10 | Qualidade da própria revisão | quem planeja a próxima rodada |
| Anexo A | Números da revisão e gasto de tokens | — |
| Anexo B | Prova principal por id (antigo §7.4) | quem confere uma prova |
| Anexo C | Tabela dos 128 RG (antigo §8.3) | dono, sessão principal |
| Notas | Notas da revisão final: o que mudou e o que foi rejeitado | quem audita esta síntese |

---

## 2. Veredito em 10 linhas

1. **Pronto para:** seguir a construção local, a F3 prévia com `ProvedorFalso` e ensaios em dev. O portão local passou 2× com 3429 testes (`fase4/check-x2.out:1-14`).
2. **Não pronto para:** atender cliente real, nem em sombra com texto real. Das 34 RS, nenhuma está sem achado vivo; só RS-02 conta como atendida, porque só tem 6 BAIXO (§7.0, §7.1).
3. Não há CRÍTICO vivo de código. Há 73 ALTO vivos (tabela abaixo). É piso, não teto: recall estrito de 28 % e critério de parada da Fase 4 não atingido (§10.2, §10.3).
4. **Risco 1, calendário:** o degrau de 1 dia já foi gasto (DEL §1). B1.6b não começou e o PR #13 está `CONFLICTING` (G-0076, `MANIFESTO.md:92`; RG-045). Outro dia perdido acaba com o piloto real (`ROT:1294`). A pergunta 1 do PLANO (o que se fez em 09/11) segue sem resposta até as sondas SO-01..SO-04, SO-13 e SO-17 (§9b).
5. **Risco 2, infraestrutura:** a VPS não existe (G-0001, RG-041 CRÍTICO). A esteira não sobe a main (F4-016, `docker-compose.yml:51`; G-0094; G-0016). O deploy pode anunciar tag errada (G-0095).
6. **Risco 3, PII:** a máscara de logs nunca é ligada (G-0085, `observabilidade.py:258`). Nome e endereço do cliente chegam ao prompt (G-0114, `mensagens.py:284-287`). Há CPFs de DV válido na main do facta-on (G-0118). D-32 bloqueia G2 (G-0005).
7. **Risco 4, digitação em dobro:** T7 já despachada pode sair com erro repetível (G-0087, `gateway.py:303-309`). Repasse morto vira terminal (G-0131, `ledger.py:509-512`). T5 de 3RN/C6 vai ao banco real em sombra (G-0088, `catalogo.py:165`).
8. **Risco 5, entrada do canal:** a forma real do Post nunca foi medida e dá 422 (G-0119, `api/eventos.py:41`). `matricula` dá 422 (G-0121). Hash sha256 cai em ~18 % (G-0122). Os kits nunca foram ensaiados (F4-035).
9. **Antes do congelamento:** dos 29 ALTO do §5, 18 se fecham com código no PR do bloco e 11 com decisão do dono, kit ou processo (tabela abaixo). Rebasear e mesclar B1.6a com G-0131; entregar B1.6b com R-c2 (G-0032, G-0020); consertar a esteira; escrever `s4/migrar.sh` (G-0012); resolver G-0084. Com a Parte A, só cabe com 5 agentes (§3.3).
10. **Do dono, antes de 19/11:** VPS até 12/11 14:00 (DN-11); ciência do degrau até 11/11 18:00 (DN-18); decisões de PII DN-20 a DN-26; chave Fireworks ou aceite «não medido» (DN-15, DN-21).

**Os 73 ALTO vivos por origem.**

| Origem | ALTO vivos | Onde |
|---|---:|---|
| Fase 3, código, costura, kit e ausência de controle | 24 | §5 |
| Fase 3, papel e estado desatualizado | 23 | §6.2 |
| Fase 3, «não existe: critério de aceite» | 21 | §6.5 |
| Fase 4 (F4-009, F4-016, F4-035, F4-036) | 4 | §5 |
| Rodada 2 (R2-001) | 1 | §5 |

**Os 29 ALTO do §5 por tipo de correção.** Asterisco: o código pede antes uma decisão do dono.

| Tipo de correção | N | Ids |
|---|---:|---|
| Código em PR do bloco | 18 | G-0084*, G-0085, R2-001, G-0114*, G-0119, G-0121, G-0122, G-0087, G-0088*, G-0125, G-0126*, G-0090, F4-009, G-0131, F4-016, G-0095, G-0097, G-0106 |
| Decisão do dono, kit, papel ou processo | 11 | G-0070 e G-0124 (decisão do dono); G-0118 (DN-23); G-0008 e G-0015 (kits); G-0020, G-0032, G-0055, G-0056 (papel e aceite); F4-035 e F4-036 (processo da revisão) |

---

## 3. Efeito no calendário

### 3.1 Calendário do degrau (DEL §1, adotado por delegação em 10/11)

O dono derruba qualquer item com uma palavra. Os itens 1 a 3 do DEL só ganham efeito irreversível no checkpoint de 11/11 18:00 (DEL:5). O ROT ainda traz o cenário C sem o degrau (G-0079, `ROT:1164` × `DEL:27`).

| Marco | Cenário C (ROT, Parte C) | Degrau (DEL §1) |
|---|---|---|
| Congelamento | qua 18/11 18:00 | **qui 19/11 18:00** |
| `ativar.sh` | 19/11 12:30 | 19/11 depois das 20:30 |
| F3 oficial | 18/11 18:00 → 19/11 15:00, com correção | 19 → 20/11, **sem correção** (falha ⇒ no-go) |
| F3 prévia | 16–17/11 | **16 → 18/11**, obrigatória |
| Sombra | 23/11 08:00 → 25/11 12:00 | igual |
| Ensaio B | 19/11 14:00–18:00 | 25/11 12:00–17:00 |
| Go/no-go | 25/11 17:00 | **26/11 12:00** |
| Piloto | 26–30/11, 5 dias, rampa até 70 | **27–30/11**, 4 dias, rampa a fixar (DN-19) |
| Relatório | 01/12 21:00 | igual |
| Teto | 04/12 | igual |

**Custos aceitos pela delegação (precisam da ciência do dono, DN-18):** F3 oficial sem correção; dia 1 do piloto na Black Friday (27/11); piloto de 4 dias sem rampa escrita (G-0172). **Limite duro:** 2 dias de atraso no total ⇒ sem piloto real (`ROT:1294`).

### 3.2 Mapa de deploys do degrau (DEL §1b; proposta, cada `!` pede «sim»)

| Ato | Cenário C | Degrau | Achados que seguram o ato |
|---|---|---|---|
| Rotas + env do gateway (N1–N3) | 09/11 noite | 10/11 depois das 20:30 | G-0515 (kit com datas velhas), G-0519 (ensaio de outro SHA) |
| Redeploy do gateway (#2) | 10/11 05:30 | 11/11 05:30 (reserva) | G-0070 (D-09), DN-06 |
| A3.0–A3.3 · A3.4–A3.7 | 10/11 · 11/11 | 11/11 08:30 · 12/11 | G-0119, DN-25, G-0056 |
| A4.3a (S4 papéis e hba) | 09/11 13:15 | 11/11 13:15 | F4-021, F4-022, F4-023, F4-035 |
| A3.8 (`zz-ensaio-ui`) | 09/11 12:30 | 12/11 13:15 | DN-13 |
| web #3 (B4.2) | 11/11 12:30 | 12/11 12:30 | G-0125, G-0035; B4 sem código (DEL F4) |
| API #4 | 12/11 12:30 | 13/11 12:30 | G-0124 |
| A4.6 (0001–0005) | 13/11 12:30 | 13/11 13:15 | G-0012, G-0011, G-0008, DN-33 |
| `facta-on` #5 | 12/11 noite | 13/11 depois das 20:30 | G-0017, G-0152, G-0118/DN-23, G-0106 |
| Tag `v0.3.0` (B1.7) | 12/11 | 13/11 | G-0019, G-0076, G-0131, R2-001, G-0085 |
| Orquestrador e dublê #8 | 13/11 noite | 16/11 depois das 20:30 | F4-016, G-0016, G-0094, G-0095, G-0097, G-0126, DN-11 |
| n8n, espelho e vigia #6 | 16/11 12:30 | 17/11 12:30 | G-0121, G-0122, G-0032, G-0020, DN-26, DN-28 |
| web #7 | 17/11 12:30 | 18/11 12:30 | G-0004 |
| Última tag + chave AES de dezembro | 18/11 12:30 | 19/11 12:30, tags até 17:00 | G-0084, DN-29 |
| A4.2/A4.3b · A4.4 | 10/11 noite · 11/11 noite | 11/11 noite · 12/11 noite, só com VPS | G-0015, G-0126, G-0074, G-0127 |

As provas de cada id estão nos §5 e §6. As dependências finas (A4.4 antes de B6.8, #4 antes de #7) pedem conferência da sessão principal antes de irem ao ROT (DEL:247).

### 3.3 Capacidade (estimativa; nada aqui foi medido)

Fórmula do ROT: r máximo = agentes × dias ÷ resíduo. O plano cabe se r máximo > 0,49, o único proxy de ritmo (`ROT:1222-1231`). Resíduo do cenário C: 63,6 d-agente, HIPÓTESE (`ROT`, «Conta do resíduo»).

**Carga das correções (estimativa desta síntese, não medida).** Pesos: 0,25 d-agente por ALTO do §5; 0,1 por MÉDIO de código; 0,03 por emenda de papel. A Parte A (≈ 3,25–3,5 d: kits, A4.x, A2.12, A2.13) corre à parte e «baixa todos os limites em ≈ 0,03» (`ROT:1230`); a tabela já desconta esse 0,03. Se as 100 peças «não existe» já estão no resíduo de 63,6: **não verificado**. O resíduo é de 04/11, e há peças da Parte A entre elas (ex.: G-0012, G-0015).

| Pacote | Itens | d-agente (estimativa) | Resíduo somado | r máx. 4 agentes × 9 d, menos Parte A | r máx. 5 agentes × 9 d, menos Parte A |
|---|---:|---:|---:|---:|---:|
| Só o resíduo (DEL §1) | — | 0 | 63,6 | 0,54 | 0,68 |
| + ALTO do §5 e emendas ALTO de papel (§6.2) | 29 + 23 | ≈ 8 | ≈ 71,6 | ≈ 0,47 | ≈ 0,60 |
| + MÉDIO de código com RS e da Fase 4 (§5, 111 + 33) | 144 | ≈ 14 | ≈ 85,6 | ≈ 0,39 | ≈ 0,50 |
| + MÉDIO de código sem RS (§5, 65) | 65 | ≈ 6,5 | ≈ 92,1 | ≈ 0,36 | ≈ 0,46 |
| + MÉDIO de papel (§6.3, §6.4) | 63 | ≈ 2 | ≈ 94,1 | ≈ 0,35 | ≈ 0,45 |

Conta: r = agentes × 9 ÷ resíduo somado, menos 0,03. Ex.: 4 × 9 ÷ 71,6 = 0,503; menos 0,03 = 0,47.

A subida real de agentes é 1 → 2 → 4 → 5, com portão de memória (DEL §2). A revisão disputa a mesma máquina (DEL F6: carga 15,4 em 12 vCPU às 09:03 de 10/11).

**O que cabe antes do congelamento de 19/11 18:00 (estimativa):**
- Com 4 agentes, nem o pacote ALTO cabe: r ≈ 0,47 < 0,49. Precisa de 5 agentes (r ≈ 0,60) ou de corte de escopo com «sim» do dono.
- Com 5 agentes: os 18 ALTO de código no PR do bloco que já está na fila (DEL §2, «Correções»), e os 11 ALTO de decisão, kit ou processo na data do dono (§2, tabela). Com os 144 MÉDIO de código, a folga cai a ≈ 0,01: nenhum dia parado.
- As emendas ALTO do ROT que a sessão principal faz sem tocar contrato: degrau (G-0079), Painel (G-0006, G-0007, G-0076), regra 5 (G-0004), A4.6 (G-0011), B3.x (G-0017).
- Os MÉDIOS que caem dentro de um bloco ainda aberto (exemplos: R2-010, R2-012, R2-013 em B5.4; F4-010, F4-011, F4-014 em B5.7a; F4-018 no rebase da esteira).
- Os atos do dono do §9a com data até 19/11.

**O que não cabe e deve ir a outra data:**
- Os MÉDIOS de código fora dos blocos abertos, e todos os 65 MÉDIO sem RS: mesmo com 5 agentes, r máx. cai abaixo de 0,49. Prazo proposto: CRÍTICO/ALTO do delta até 25/11 12:00 (DEL §2.7); o resto depois do piloto, com «sim» por item.
- As emendas de contrato (§6.3b). As emendas de 04/11 (01 v2.5, 03 v2.2, 04 v2.2, 07 v2.2, 08 v2.4) já foram aplicadas, e a regra «não se editam nesta rodada» foi riscada (`ROT:106`). Emenda nova pede «sim» do dono por item (PLANO §6). O 05 e o regime de permissão seguem pendentes (`ROT:1582`, Parte F linha 72).
- As 100 peças «não existe» que não são de bloco com deploy até 19/11 (B9 a B12, Parte F): viram aceite das etapas.
- A próxima rodada da revisão (§10.8): ensaios F2-47, canário 5, baseline de semgrep e dependências.

---

## 4. Ordem de ataque (10/11 → 19/11)

Regras: cada `!` pede o «sim» do dono e respeita PD-3 (dia útil, 12:30–14:00 ou depois das 20:30; nada em 14–15/11). Correção que muda data ou escopo pede «sim» por item (DEL §2). As provas resumidas estão na coluna «Prova»; a completa, no §5 ou §6.

**Como ler.**

| Atalho | Raiz | Nota |
|---|---|---|
| `src/`, `b1-6a/`, caminhos de código sem raiz (`ledger.py`, `api/eventos.py`, `modo.py`) | `/home/danilo/ia-revisao-0911/src/`; `b1-6a/` = `src/ia-atendimento-b1-6a/`; sem raiz = `src/ia-atendimento/src/ia_atendimento/` | exportação nos SHAs do §1 |
| `c360` | `src/cliente360-api/src/c360api/` | — |
| `kits/<kit>/` | cópia lida: `/home/danilo/ia-revisao-0911/kits/<kit>/`; cópia que roda: `~/retomada-2809/fila-2910/ia/<kit>/` (F4-022) | antes de cada «sim», `sha256sum` contra `fase0/MANIFESTO.md:99-127` (SO-33). O ramo `kits/s4` (`src/ia-atendimento-kits-s4/`) é uma terceira cópia, sem push |
| `ROT:n` | `/opt/claude/docs/planejamento-ia/ROTEIRO-DE-ACAO.md` v3.3 | — |
| `01`..`08`, `04:n`, `08:n`, `contratos/NN` | `/opt/claude/docs/planejamento-ia/contratos/NN-*.md`, vigentes sem sufixo | — |
| `DEL:n` | `/home/danilo/ia-revisao-0911/fase0/decisoes-delegadas.md` | — |
| `fase*/`, `F1-nn` | `/home/danilo/ia-revisao-0911/fase*/`; `F1-nn` = `fase1/leituras/F1-nn.md` | — |

| Quem | Significado |
|---|---|
| construção | agentes Claude de construção; «construção 1/2» = 1º ou 2º agente |
| sessão | sessão principal (Claude); roda as sondas SO-nn (§9b, regra 3) |
| revisão | unidade da próxima rodada desta revisão (§10.8), lançada pela sessão principal em `~/ia-revisao-0911/`; só ensaio local, sem produção |
| dono | o dono; `!` = ato em produção com «sim» |
| Danilo | ato pessoal do Danilo (cookie, ChatGuru, cliques no Coolify) |

**Pronto quando.** O item fecha quando passa o «Teste que reprova antes» do id no §5, ou a «Prova de feito» do id no §6.2, §6.3 ou §6.4, ou o «Critério de aceite» do §6.5. Item `DN` fecha com a resposta escrita do dono. Item `!` fecha com a pós-condição do kit e a sonda SO-nn ligada (§9b). Item sem nenhum desses está marcado «não verificado».

### Ter 10/11 (noite)

| # | Hora | Quem | Ação | Ids | Prova | Depende de |
|---|---|---|---|---|---|---|
| 1 | já | sessão | Lote de sondas SO-01, SO-02, SO-03, SO-04, SO-13, SO-17: saber o que foi feito em 09–10/11. DN-04 venceu 10/11 12:00; o estado sai de SO-13 | DN-04, DN-05, G-0070, G-0004 | §9b; nenhuma saída gravada | — |
| 2 | vencido 10/11 18:00 (DN-01); estado por SO-13 e resposta do dono | dono · Danilo | Pedido único: chat de teste, 13 perguntas ao ChatGuru e a pergunta 4 à FACTA (DN-01), A1.3 (DN-02), ata A1.10 com P5 (DN-03), cookie do RPA (DN-07) | DN-01..DN-03, DN-07, RG-042, RG-048 | DEL:161-164 | — |
| 3 | já | construção 1 | B1.6a: corrigir G-0131 e a parte de ledger de G-0087 antes do merge do PR #13 | G-0131, G-0087 | `b1-6a/ledger.py:509-512`, `:474-479` | — |
| 4 | quando o portão abrir | construção 2 | Rebase local do PR #13 e do PR #49 (`conferir_janela_min` 10 → 20), sem merge | G-0076, G-0461, G-0152 | `MANIFESTO.md:92`, `:96` | portão de memória (DEL §2) |
| 5 | já | construção 1 | Abrir a branch da B1.6b (consumo do batimento, D-15) | G-0066, RG-045 | §6.5 B1 | 3 |
| 6 | antes das 20:30 | dono | Decidir o sumidouro com Post inteiro 7 d (aceitar no livro de retenção ou mudar) | DN-25, G-0482 | `gl-gateway/app/projecao.py:57` | — |
| 7 | depois das 20:30 | dono `!` | «sim» a N1–N3 (`rotas-ia.sh`, `env-gateway.sh --gravar`, vigia de ensaio) | DN-05, G-0515, G-0519 | `kits/gateway/README.md:3`, `:27`, `:287` | 1, 2 (ata P5) |

### Qua 11/11

| # | Hora | Quem | Ação | Ids | Prova | Depende de |
|---|---|---|---|---|---|---|
| 8 | 05:30 | Danilo · dono | Redeploy do gateway (reserva) ou queda E-12; nenhum merge no gl-gateway | DN-06, G-0070 | `testes.yml:18,58` | 7, D-09 |
| 9 | 08:00 | construção | Subir a 4 agentes, se o portão abrir. Portão: `free -m` e `uptime` na S3; disponível ≥ 6 GB, swap parado, ensaios pesados encerrados | DN-17 | DEL:77, :81 | portão de memória |
| 10 | 08:30 | Danilo | A3.0–A3.3; medir a forma de `datetime_post` de cada Post | G-0119, RV-05, CG-01..CG-03 | `api/eventos.py:41`; `tipos.py:27` | 8, DN-01, DN-25 |
| 11 | manhã | construção | Rumo à tag v0.3.0 (B1.7): R2-001 (B1.4), G-0119 (data inválida vale como ausente) e G-0122 (B1.5); G-0085 como aceite de B1.6a/B1.7 | R2-001, G-0119, G-0122, G-0085 | `contexto.py:266,316`; `tipos.py:20,54`; `observabilidade.py:258` | — |
| 12 | manhã | revisão | Rodar F2-47 no kit `s4` (1×, 2×, interrompido, desfazer) e `sha256sum` contra o manifesto | F4-035, F4-022, SO-33 | `fase0/unidades.json:3079` | — |
| 13a | cedo | dono | «sim» por item à edição do ROT do item 13 (PLANO §6) | G-0079, G-0006, G-0007, G-0004, F4-021 | PLANO-REVISAO-0911.md §6 | — |
| 13 | manhã | sessão | ROT: registrar o degrau, Painel com SHA, regra 5 do web, A4.3a desfeita pelo kit | G-0079, G-0006, G-0007, G-0004, F4-021 | `ROT:1164`; `ROT:45`; `ROT:706` | 13a |
| 14 | 13:15 | dono `!` | A4.3a (`s4-papeis.sh`, `s4-hba.sh`) | DN-08, F4-023, S4-01 | `kits/s4/provar.sh:65` | 12, 13 |
| 15 | dia | construção | B5.7a: guardas de regex | G-0090, F4-009, F4-010, F4-011, F4-014 | `agenda_extrator.py:231,238` | — |
| 16 | dia | dono | Substituto e revisor (DN-09); 1º lote de textos (DN-10), depois da reemissão v2 pelo Claude | DN-09, DN-10, G-0075, G-0387 | `TEXTOS-PARA-APROVACAO.md:3` | reemissão v2 |
| 17 | 18:00 | dono | Checkpoint 0b (≥ 4 agentes?) e X7; ciência do degrau | DN-17, DN-18, G-0079, G-0174 | DEL:88; `ROT:1231` | 9 |

### Qui 12/11

| # | Hora | Quem | Ação | Ids | Prova | Depende de |
|---|---|---|---|---|---|---|
| 18 | 05:30 | dono | 2ª janela do gateway, só se a de 11/11 caiu | DN-06 | DEL:183 | — |
| 19 | 12:30 | dono `!` | web #3 (B4.2), só se construído e revisado; emenda «desligar a flag exige a IA desligada» | G-0125, G-0035 | `esquemas.py:112-113`; c360 `config.py:838` (`nao_perturbe_30d`), `:861` (`vendedor_ator_id`, G-0035) | B4.2 pronto |
| 20 | 13:15 | dono `!` | A3.8 (`zz-ensaio-ui`) | DN-13, N8-01 | DEL:160 | — |
| 21 | 14:00 | dono | Contratar a VPS (limite) | DN-11, G-0001, RG-041 | `ROT:290` | DN-02 |
| 22 | dia | Danilo | A3.4–A3.7, com os 3 robôs emissores ativos | G-0056, RG-093 | `ROT:1340` | 10 |
| 23 | dia | construção | Escrever e ensaiar `kits/s4/migrar.sh` (0001–0005, ledger na mesma transação) | G-0012, G-0011, G-0008 | `ROT:717`, `:722` | 12 |
| 24 | dia | construção | Esteira: rebase, `--factory`, worker, Dockerfile, `curl --fail-with-body`, permissão 0600 dono 10001, dias-piloto 26/27–30/11 | F4-016, G-0016, G-0094, F4-018, G-0095, G-0097, G-0096 | `docker-compose.yml:51,96`; `deploy-vps.sh:90`; `DEPLOY.md:62` | — |
| 25 | dia | dono | Decidir os escopos da credencial da IA antes de B4.1 | G-0124 | `cliente360.json:3238` | — |
| 26 | dia | dono | CPFs de DV válido no facta-on: são reais? Decidir antes do #5 | DN-23, G-0118, F4-036 | `facta-on/app/routers/online.py:594`; `fase4/historico-pii.md:24-26` | — |
| 27 | dia | dono | E-mails da semente | DN-12 | DEL §6 | — |
| 27a | dia | dono | Via de G-0126: exceção fechada só para `http://10.90.0.2` em `Destinos` ou TLS no vhost WG; e via de G-0114 (nome por T1 em memória ou risco aceito). Sem resposta, a tag do item 32 sai com G-0114 aberto, escrito no aceite provisório | G-0126, G-0114, DN-22 | `modo.py:96-97`; `mensagens.py:284-287` | — |
| 27b | dia | construção | G-0126: `_conferir_url` aceita `http` só para a lista fechada (10.90.0.2), com teste que recusa qualquer outro http | G-0126 | `modo.py:96-97` | 27a |
| 27c | dia | construção | G-0106: README e compose do bancos-duble sobem o facta-on só por `isolado_app.py` em rede `internal: true` (B2.2) | G-0106 | `bancos-duble/README.md:38-50` | — |
| 28 | noite | dono `!` | A4.4, só com VPS; aceitar só `http://10.90.0.2` em `Destinos`; tabela de `location` com `formalizar` | G-0015, G-0126, G-0074, G-0127 | `modo.py:96-97`; `contratos/02` §2 | 21, 27b |

### Sex 13/11

| # | Hora | Quem | Ação | Ids | Prova | Depende de |
|---|---|---|---|---|---|---|
| 29 | 12:30 | dono `!` | API #4 (B4.1–B4.3) | G-0124, N8-04 | `escopos.py:89-98` | 25 |
| 30 | antes de 13:15 | dono | `ia_app` pode ligar a IA e subir o teto? | DN-33, G-0246 | `i-esquema-reconciliado.md:513` | — |
| 31 | 13:15 | dono `!` | A4.6 por `s4/migrar.sh`, «sim» nomeado à 0005 | DN-14, DN-16, G-0012 | `ROT:717` | 14, 23, 30 |
| 32 | dia | construção | Tag `v0.3.0` com B1.4 em aceite provisório; PR #13 mesclado com G-0131; B1.6b no aceite | G-0019, G-0076, G-0131, G-0114 | `ROT:901`, `:1238` | 3, 4, 5, 11, 27a |
| 33 | dia | dono | 2º lote de textos com TX-42; A1.11, D-16, E-3 | DN-10, DN-14, G-0072 | `TEXTOS-PARA-APROVACAO.md:3` | 16 |
| 34 | depois das 20:30 | dono `!` | facta-on #5: um merge só (PR #49 + janela), flags próprias, CPFs fora da main | G-0017, G-0152, G-0118, G-0108, G-0106 | `ROT:947,952` × `:858` | 4, 26, 27c, D-09 |

Se a tag não sair em 13/11, o #8 de 16/11 fica sem imagem. Mais um dia perdido no total ⇒ sem piloto real (`ROT:1294`; DEL:47).

### Sáb 14/11 e dom 15/11 (sem `!`)

| # | Quem | Ação | Ids | Prova | Depende de |
|---|---|---|---|---|---|
| 35 | construção | B5.4: T7 despachada sempre INDETERMINADO; timeout de T8; parada dura sem simulador | G-0087, R2-010, R2-012, R2-013, R2-017 | `gateway.py:303-309,341-346`; `modo.py:157-164` | 32 |
| 36 | construção | B5.2/B5.3: `SaidaT1` tri-estado; `matricula` aceita na API | G-0125, G-0121 | `esquemas.py:112-113`; `api/atendimentos.py:38-46` | — |
| 37 | construção | B1.6b/B6.4: R-c2 e saída para vigia morta, com o desenho do dono | G-0032, G-0020, RG-095 | `04-n8n-braco-espelho.md:382`; `08:238` | DN-28 |
| 38 | construção | B1.2: chave do mês pelo relógio, se o dono mandar mudar o código | G-0084 | `conversa.py:102-114` | DN-29 |
| 39 | construção | 15/11: B9.5a em dev; o tap lê a FACTA no domingo | FA-04, DP-02 | `ROT` dia 15/11 | 34 |

### Seg 16/11

| # | Hora | Quem | Ação | Ids | Prova | Depende de |
|---|---|---|---|---|---|---|
| 40 | dia | construção | Checkpoint 2: B5.4 verde; F3 prévia começa (16 → 18/11) | G-0087, G-0088 | DEL §1 | 35 |
| 41 | dia | dono | T5 de 3RN/C6 em sombra: interceptar, `leitura_paga` ou teto próprio (antes de G2) | G-0088 | `catalogo.py:165` | — |
| 42 | dia | sessão | `df` da S2 (X5) e leitura do tap de 15/11 | SO-04, SO-11 | `ROT` dia 16/11 | 39 |
| 43 | depois das 20:30 | dono `!` | #8 orquestrador e dublê na VPS (A4.9, A4.10) | F4-016, G-0094, G-0095, G-0097, G-0126 | §5, esteira | 21, 24, 28, 32 |

### Ter 17/11

| # | Hora | Quem | Ação | Ids | Prova | Depende de |
|---|---|---|---|---|---|---|
| 44 | antes de 12:30 | dono | Telefone em claro no espelho (D-27); regra da vigia R-c2 | DN-26, DN-28 | F1-59:105; `04:382` | — |
| 45 | 12:30 | dono `!` | #6 n8n, espelho e vigia; a API com `matricula` antes do fluxo que envia o campo | G-0121, G-0122, G-0195, G-0055 | `api/atendimentos.py:38-46`; `04:209` | 36, 37, 44 |
| 46 | dia | dono | Chave Fireworks (A1.4) ou aceite escrito de «custo e latência não medidos» | DN-15, DN-21, G-0009, RG-040 | `ROT:139` × `:599` | — |

### Qua 18/11

| # | Hora | Quem | Ação | Ids | Prova | Depende de |
|---|---|---|---|---|---|---|
| 47 | 12:30 | dono `!` | web #7, fora das janelas do Cliente360; conferir o timer de deploy no merge | G-0004, SO-17 | `ROT:45`; memória `web-merge-auto-deploy` | 29 |
| 48 | dia | dono | Aceite de G2 com a via de D-32; aceite do limite da máscara (a parte de nomes, G-0114, já foi decidida no 27a ou está aberta na tag) | DN-20, DN-22, G-0005, G-0047, G-0114 | `ROT:43`, `:231`; `mascara.py:140` | SO-08 |
| 49 | dia | construção | F3 prévia termina; kits B9.0 em ensaio local | G-0022, F4-035 | `ROT:1142` | 40 |

### Qui 19/11 (congelamento)

| # | Hora | Quem | Ação | Ids | Prova | Depende de |
|---|---|---|---|---|---|---|
| 50 | 12:30 | dono `!` | Última tag e chave AES de dezembro (kit); tags até 17:00 | G-0084, DN-29 | `conversa.py:102-114` | 38 |
| 51 | 18:00 | sessão | Congelamento: `git diff` manifesto → SHA congelado; reverificar cada ALTO; manifesto sha256 dos kits novos | DEL §2 itens 1–7 | DEL:92-99 | 50 |
| 52 | depois das 20:30 | dono `!` | `ativar.sh`; F3 oficial 19 → 20/11, sem correção | G-0025 | `ROT:1293` | 51 |
| 53 | dia | Danilo | 2ª renovação do cookie do RPA | RPA-01, RG-048 | `ROT` dia 19/11 | — |

Depois do congelamento: CRÍTICO/ALTO do delta fechados até 25/11 12:00 (DEL §2.7). Go/no-go em 26/11 12:00 com DN-19, DN-27, DN-30, DN-31, DN-32 (§9a.2).

### ALTO sem linha no calendário acima

Proposta desta revisão final. As fontes não dão data a estes itens. A coluna «Até» liga o item ao primeiro ato do §3.2 que depende do bloco. Cada emenda pede «sim» por item (PLANO §6).

**Papel ALTO (§6.2).**

| Id | Quem | Ação | Até | «sim» exigido | Pronto quando |
|---|---|---|---|---|---|
| G-0031 | sessão | Emenda ao 04: `retomou` recalcula `prazo_ate` | antes do #6 (17/11 12:30) | sim, contrato | Prova de feito do §6.2 |
| G-0037 | sessão | Emenda ao 02 §3 e ao 08: `Canal.restaurar` não escreve delegação | antes de B6.8 | sim, contrato | idem |
| G-0043 | dono, depois sessão | Tolerância de ajuste e caminho de cancelamento na T7 | antes de B5.4 (item 35, 14–15/11) | sim, decisão do dono | idem |
| G-0050, G-0054 | sessão | Tarja «superado» nos estudos J, M e L | sem ato que dependa; até 19/11 | sim, por item | idem |
| G-0062, G-0063 | sessão | Nota de precedência no plano mestre e no sp01 | sem ato que dependa; até 19/11 | sim, por item | idem |

**«Não existe» ALTO (§6.5) sem linha no calendário.**

| Id | Bloco (§6.5) | Até | Pronto quando |
|---|---|---|---|
| G-0013 | A4 (egress da VPS) | A4.4 (item 28) | Critério de aceite do §6.5 |
| G-0036 | A3/A5.9 (contrato 02) | B6.8 | idem |
| G-0068 | A3/A5.9 (respostas do ChatGuru; prova de Post) | DN-01 (item 2) e A3.0 (item 10) | idem |
| G-0073 | A7 (textos no código) | 2º lote de textos (item 33) | idem |
| G-0083, G-0089, G-0091, G-0115 | B1 | tag v0.3.0 (item 32) ou #8 (item 43) | idem |
| G-0058 | B5 (matrícula) | antes de B6.2 e do #6 (item 45) | idem |
| G-0078, G-0086, G-0099, G-0123, G-0129 | B6 | #6 (item 45, 17/11) | idem |
| G-0565 | B7 (depende de B1.6b) | web #7 (item 47) | idem |
| G-0023 | B9 a B12 (parada dura) | go/no-go 26/11 12:00 (DN-27) | idem |

Os MÉDIO do §5, inclusive os 65 sem RS, não têm linha aqui. Entram no PR do bloco quando o bloco está aberto; o resto segue o §3.3.

---

## 5. Achados de código: ALTO e MÉDIO

Esta seção traz 29 achados ALTO vivos de código, costura, kit e ausência de controle: 24 grupos da Fase 3, 4 da Fase 4 (F4-009, F4-016, F4-035, F4-036) e 1 da rodada 2 (R2-001). Depois vêm 111 MÉDIOS da Fase 3 com RS, 65 MÉDIOS da Fase 3 sem RS e 33 MÉDIOS da Fase 4 sem RS atribuída na fonte. Não há CRÍTICO vivo.

### Como ler

- **Recorte.** Na Fase 3 entram grupos com `tipo` em {codigo, costura, kit, ausencia-de-controle} e estado vivo (confirmado, confirmado em parte, não existe). Os MÉDIO entram todos: 111 com RS e 65 sem RS, em subseções próprias. A fonte é `fase3/consolidado.json`, com detalhe em `fase3/grupos/G-nnnn.json`. Na Fase 4 entram todos os ALTO e MÉDIO de `fase4/consolidado-f4.json` e `fase4/consolidado-r2.json`.
- **Fora daqui.** Os 21 ALTO do tipo «não existe» viram critério de aceite e ficam em outra seção: G-0001, G-0012, G-0013, G-0023, G-0036, G-0058, G-0066, G-0068, G-0072, G-0073, G-0078, G-0083, G-0086, G-0089, G-0091, G-0099, G-0108, G-0115, G-0123, G-0129, G-0565. Os ALTO de papel e estado desatualizado também ficam fora, salvo G-0016 e G-0094, citados junto de F4-016.
- **Nada foi executado.** Toda «reprodução» abaixo é leitura de código ou sonda em texto sintético. As unidades de execução F2-47 e F2-48 nunca rodaram (F4-035). Nenhum teste citado como «reprova antes» foi rodado nesta revisão.
- **Bloco do roteiro.** O bloco vem de `ROTEIRO-DE-ACAO.md` ou da correção proposta pelos verificadores. Quando a fonte não nomeia bloco, a célula diz «sem bloco na fonte» e traz uma sugestão marcada como tal.
- **Caminhos.** Os caminhos de código são relativos a `/home/danilo/ia-revisao-0911/src/`. `ROT` = `/opt/claude/docs/planejamento-ia/ROTEIRO-DE-ACAO.md`. `08`, `04`, `05` = contratos vigentes em `/opt/claude/docs/planejamento-ia/contratos/`.

### Índice dos ALTO

| Id | Título curto | Repositório · módulo | Prova principal | Bloco | Estado |
|---|---|---|---|---|---|
| G-0084 | Chave AES de dezembro não entra sozinha | ia-atendimento · cifra/conversa | `ia-atendimento/src/ia_atendimento/conversa.py:102-114` | B1.2 (código) ou B9.1 (kit; 18/11 no cenário C, 19/11 12:30 no degrau) | confirmado |
| G-0085 | Máscara de logs nunca ligada | ia-atendimento · observabilidade | `ia-atendimento/src/ia_atendimento/observabilidade.py:258,267` | B1.6a/B1.7 | confirmado |
| R2-001 | Pendente «dd/mm hh:mm» derruba o turno | ia-atendimento · contexto/máscara | `ia-atendimento/src/ia_atendimento/contexto.py:266,316` | B1.4 | confirmado |
| G-0114 | Receptor grava com `nomes=()` fixo | ia-atendimento · mensagens/contexto | `ia-atendimento/src/ia_atendimento/mensagens.py:284-287` | antes de B1.6 | confirmado |
| G-0119 | `datetime_post` real nunca medido; 422 em tudo | ia-atendimento · api/eventos | `ia-atendimento/src/ia_atendimento/api/eventos.py:41,47` | A3.0/A3.1 + B1.5 | confirmado |
| G-0121 | POST /atendimentos recusa `matricula` | ia-atendimento · api/atendimentos | `ia-atendimento/src/ia_atendimento/api/atendimentos.py:38-46` | B5.3, antes de B6.2 | confirmado |
| G-0122 | `criterio_versao` sha256 recusado (~18 %) | ia-atendimento · api/validacao | `ia-atendimento/src/ia_atendimento/tipos.py:20,54` | B1.5 / B6.2 | confirmado |
| G-0087 | T7 despachada sai com erro repetível | ia-atendimento · ferramentas/gateway | `ia-atendimento/src/ia_atendimento/ferramentas/gateway.py:303-309,341-346` | B5.4 (+ B1.6a no ledger) | confirmado |
| G-0088 | T5 de 3RN/C6 vai à produção em sombra | ia-atendimento · ferramentas/catalogo+modo | `ia-atendimento/src/ia_atendimento/ferramentas/catalogo.py:165` | B5.2/B5.5, antes de G2 | confirmado |
| G-0125 | Chave ausente vira «sem bloqueio» | ia-atendimento · ferramentas/esquemas | `ia-atendimento/src/ia_atendimento/ferramentas/esquemas.py:112-113` | B5.2 | confirmado |
| G-0126 | Destinos recusa o http do túnel WG | ia-atendimento · ferramentas/modo | `ia-atendimento/src/ia_atendimento/ferramentas/modo.py:96-97` | A4.4 + B5.2/B5.4 | confirmado |
| G-0090 | «às 15 30» sai 15:00 alta | ia-atendimento · agenda_extrator | `ia-atendimento/src/ia_atendimento/agenda_extrator.py:238` | B5.7a | confirmado |
| F4-009 | «perto das 3 da tarde» sai alta | ia-atendimento · agenda_extrator | `ia-atendimento/src/ia_atendimento/agenda_extrator.py:231` | B5.7a | confirmado |
| G-0131 | Linha `enviada` órfã vira `indeterminado` terminal | ia-atendimento-b1-6a · ledger | `ia-atendimento-b1-6a/src/ia_atendimento/ledger.py:509-512` | B1.6a (PR #13) / B1.6b | confirmado |
| F4-016 | Compose da esteira não sobe a main | ia-atendimento-esteira · compose | `ia-atendimento-esteira/docker-compose.yml:51` | A6.6b | confirmado |
| G-0095 | deploy-vps.sh anuncia tag que não trocou | ia-atendimento-esteira · scripts | `ia-atendimento-esteira/scripts/deploy-vps.sh:90,104-105,145` | A6.6 / A4.9 | confirmado |
| G-0097 | DEPLOY.md manda 640; código recusa | ia-atendimento-esteira · docs × cifra | `ia-atendimento-esteira/docs/DEPLOY.md:62` × `ia-atendimento/src/ia_atendimento/cifra.py:113` | A4.9 | confirmado |
| G-0070 | main do gl-gateway: merge = deploy sem trava | gl-gateway · CI | `gl-gateway/.github/workflows/testes.yml:18,58` | D-09 (dono) antes de B6.0 | confirmado |
| G-0124 | Credencial da IA alcança 19 operações | cliente360-api · borda/escopos | `cliente360-api/src/c360api/contrato/cliente360.json:3238` | B4.1 | confirmado |
| G-0118 | CPFs declarados «caso real» no facta-on | facta-on · app e tests | `facta-on/app/routers/online.py:594` | sem bloco na fonte | confirmado |
| G-0106 | Receita do README sobe facta-on fora da rede interna | bancos-duble · README/compose | `bancos-duble/README.md:38-50` | B2.2 | confirmado |
| G-0008 | Escrita em produção sem kit (PD-2) | kits · roteiro | `ROT:427,717` | A4.2, A4.4, A4.6, A3.8 | confirmado em parte |
| G-0015 | A4.2/A4.4/A4.5/A4.7/A4.8 sem kit nem ensaio | kits · roteiro | `ROT:696,700` | A4.2, A4.4 | confirmado |
| G-0020 | D-15: vigia morta, ninguém devolve | papel · 04/08 | `ROT:1063-1066`; `08:238` | B6.4 + B1.6b/B6.3 | confirmado |
| G-0032 | D-14 entrega à vigia sem regra (R-c2) | papel · 04/08 | `04:382`; `08:244` | B6.4 | confirmado |
| G-0055 | `cpf_alterado` e `etapa_inapp` sem fonte | papel · roteiro/04 | `ROT:997,1049` | B6.2 / B5.5 | confirmado |
| G-0056 | Três robôs falam no chat sob IA | papel · roteiro/02 | `ROT:1340` | A3.4 | confirmado |
| F4-035 | Kits e check.sh nunca rodaram na revisão | revisão · unidades F2-47/F2-48 | `fase0/unidades.json:3079,3104` | antes do «sim» de A4.3a/A4.6 | confirmado |
| F4-036 | Histórico git nunca varrido por gitleaks | revisão · baseline | `fase0/baseline.md` seção (a) | antes da Fase 5 fechar RS-13 | confirmado |

### ALTO por repositório e módulo

#### ia-atendimento (main)

**G-0084 · Virada de mês da chave AES não entra sozinha (RS-05)**
- Onde: `ia-atendimento/src/ia_atendimento/conversa.py:102-114` (`exigir_chave_do_mes`); `cifra.py:178,187,202,217-223` (vigente fixa no boot); `api/ambiente.py:71`; `cofre.py:54`.
- O que acontece: a chave vigente vem de `CHAVE_AES_ID`, lida uma vez no boot. A checagem aceita só a chave do mês UTC, mais a anterior por 1 h. O roteiro diz que a chave de dezembro «entra sozinha» às 21:00 de 30/11 (`ROT:1177`, `ROT:1283`) e proíbe `!` no piloto (`ROT:872`).
- Cenário mínimo: kit de 18/11 com arquivo {2,3} e vigente 2. Em 01/12 01:00:01 UTC, `gravar_troca` e `cofre.guardar` levantam `ChaveForaDoMes`. A API responde 503 `nao_pronto` a cada mensagem. Com vigente 3 desde 18/11, a escrita para no mesmo dia.
- Correção: cifrar com `chave_id_do_mes(agora)` quando a entrada existe no chaveiro; `ChaveForaDoMes` só quando falta a chave do mês. Alternativa de papel: ato nomeado em 30/11 21:00–22:00 BRT, com «sim» prévio.
- Bloco: B1.2 (conversa cifrada) para o código; B9.1 (congelamento e ensaio a seco de 18/11) para o kit.
- Teste que reprova antes: relógio injetado em 30/11 22:00 BRT, chaveiro {2,3}, vigente 2; `gravar_troca` deve gravar com a chave 3. Hoje levanta `ChaveForaDoMes`. O teste `tests/test_conversa.py:307-319` congela o comportamento atual e precisa mudar junto.

**G-0085 · `observabilidade.configurar` sem chamador: máscara de logs não ligada (RS-03, RS-13, RS-16, RS-17)**
- Onde: `ia-atendimento/src/ia_atendimento/observabilidade.py:258,265-267`; `api/ambiente.py:37`; `worker.py:97`; `api/logs.py:22-34`. Igual no ramo b1-6a (`observabilidade.py:264-266`, `worker.py:100`).
- O que acontece: `instalar_filtro_de_logs` e o registro de segredos só rodam dentro de `configurar`. API e worker chamam só `configurar_logging`. Logger de terceiro (Procrastinate, httpx, psycopg_pool) cai no `lastResort` sem máscara, com traceback. `PHOENIX_ENDPOINT` não exporta nada.
- Cenário mínimo: job do worker falha com exceção cuja mensagem traz valor da linha; o Procrastinate loga o traceback em stderr sem máscara.
- Correção: chamar `observabilidade.configurar(settings)` em `criar_app_de_ambiente` e em `worker.main`, logo após `get_settings()`. Ou mover filtro e segredos para `configurar_logging`. Acrescentar `loop.set_exception_handler` com `formatar_sem_pii`.
- Bloco: critério de aceite de B1.6a/B1.7 (o repositório já adiou isso para «o boot da B1.5»: REVISAO-B1.4-0311-r2.md:52).
- Teste que reprova antes: em `test_boot_real.py` (subprocesso), um logger de terceiro emite WARNING com CPF sintético e a saída deve trazer `[CPF]`; `logging.getLogRecordFactory()` não pode ser a da stdlib.

**R2-001 · Pendente que começa com «dd/mm hh:mm» derruba o turno no `auditar_prompt`**
- Onde: `ia-atendimento/src/ia_atendimento/contexto.py:266` (numeração `f"{i}. «{t}»"`), `:316` (portão); `mascara.py:50` (`_CORRENTE`), `:145` (isenção pelo primeiro dígito).
- O que acontece: `proteger_texto` mantém «06/11 15:30». A montagem gera `1. «06/11 15:30»`. A corrente de dígitos começa no «1», atravessa «. «» e soma 9 dígitos. A isenção de data e hora não vale. `mascarar` troca por `[NUMERO]` e o portão levanta `ContextoComDadoPessoal`.
- Cenário mínimo: cliente responde só «06/11 15:30» a uma pergunta de agendamento (fases E2–E8/E10). O turno falha duas vezes e o atendimento é repassado.
- Correção: numerar pendentes sem dígito colado ao texto (`- «…»` ou `[msg 1] «…»`), ou auditar cada pendente antes de juntar.
- Bloco: B1.4 (contexto do turno).
- Teste que reprova antes: montar o contexto com uma pendente «06/11 15:30» e chamar `auditar_textos`; hoje levanta `ContextoComDadoPessoal`. Variante: pendente terminando em hora seguida de pendente começando com data.

**G-0114 · Nome do cliente nunca é conhecido: receptor grava com `nomes=()` fixo (RS-21)**
- Onde: `ia-atendimento/src/ia_atendimento/mensagens.py:284-287`; `conversa.py:117-131`; `contexto.py:349-353,507-508,561-562`; `mascara.py:174-177`. Igual no b1-6a.
- O que acontece: toda mensagem do cliente vai à conversa cifrada sem máscara de nome e sem `substituto`. Na E5 só a pendente é ocultada. No turno seguinte a mesma linha entra em `trocas` e no resumo, só com `proteger_texto`, que deixa passar nome, rua, bairro e banco.
- Cenário mínimo: na E5 o cliente responde o endereço; na E6 responde «sim, mas…»; o modelo recebe as três últimas trocas com o endereço em claro.
- Correção: em `montar_contexto`, renderizar como `[dado]` toda mensagem recebida na E5 que não foi desvio (join por `passo_ordem`). Alternativa: receptor grava `substituto="[dado:<campo>]"` na E5 e o valor vai só ao cofre. Para nomes: definir a fonte ou registrar risco aceito pelo dono.
- Bloco: decidir antes de B1.6 (o repositório registrou como R2-06 em REVISAO-B1.4-0311-r2).
- Teste que reprova antes: dois turnos (resposta de campo na E5, depois turno na E6 e na E8); afirmar que logradouro e banco não aparecem em `insumos.trocas` nem no prompt.

**G-0119 · Forma real do Post não medida contra validação estrita (`datetime_post`)**
- Onde: `ia-atendimento/src/ia_atendimento/api/eventos.py:41` (`extra=forbid`), `:47`, `:116`; `tipos.py:27,35-41`.
- O que acontece: o gateway repassa os campos A10 sem normalizar. O orquestrador só aceita RFC 3339 com fuso. Texto vazio, data sem fuso ou com espaço no lugar do «T» dão 422, que o gateway converte em 424.
- Cenário mínimo: o ChatGuru manda `datetime_post` sem fuso; toda mensagem de cliente vira 422 e nada é gravado.
- Correção: `datetime_post` que não parseia vale como ausente (mesmo tratamento de `relogio_futuro`, com contador de alerta). Critério novo em A3.0/A3.1: validar por forma cada Post do sumidouro contra `NativoChatguru`.
- Bloco: A3.0/A3.1 (medição) e B1.5 (código da API).
- Teste que reprova antes: POST de evento com `datetime_post` sem fuso e com espaço; esperado 2xx com hora tratada como ausente. Hoje 422.

**G-0121 · POST /atendimentos não aceita `matricula` (D-29) (RS-29)**
- Onde: `ia-atendimento/src/ia_atendimento/api/atendimentos.py:38-46,144,204`; `estado_entrada.py:33`; `api/validacao.py:33-38,45-47`.
- O que acontece: o 04 §2.5 passo 7 manda o braço incluir `matricula`. A API é `extra=forbid` e devolve 422 `campo_desconhecido`. Pelo passo 8, todo 422 vira `cancelar`.
- Cenário mínimo: corpo do 04 §2.5 com `"matricula"`; todo disparo é cancelado.
- Correção: campo opcional `^[0-9A-Za-z./-]{1,40}$`, gravado no cofre `digitacao` na mesma transação do `_abrir`, fora do fingerprint, do log e da resposta. Amarrar a ordem: API antes do fluxo n8n que envia o campo.
- Bloco: B5.3 (o 08 §3 diz «PR próprio (B5.3)»); conferir a dependência de B6.2 (deploy #6 em 16/11).
- Teste que reprova antes: teste de contrato que posta o corpo exato do 04 §2.5 contra a API real (não contra o orquestrador falso do 04 §9.4). Hoje 422.

**G-0122 · `criterio_versao` sha256 recusado por `rejeitar_documento`**
- Onde: `ia-atendimento/src/ia_atendimento/api/atendimentos.py:57-65`; `api/anotacoes.py:138`; `api/validacao.py:61-64`; `tipos.py:20,52-54`.
- O que acontece: o 04 define `criterio_versao` como sha256 hex. O regex aceita 64 caracteres, mas `contem_documento` recusa 10 ou mais dígitos seguidos. Cerca de 18,1 % dos hashes caem nisso (conta dos verificadores).
- Cenário mínimo: uma edição do critério gera hash com 10 dígitos seguidos; todo disparo e todo registro de candidato dão 422 `pii_no_texto_livre` até nova edição.
- Correção: ou o 04 passa a usar rótulo curto (`c1.0`), ou a API isenta `criterio_versao` quando o valor é hex de 64.
- Bloco: B1.5 (API) ou emenda do 04 antes de B6.2.
- Teste que reprova antes: POST /atendimentos e POST /sessoes/{id}/candidatos com hash de 64 hex contendo 10 dígitos seguidos; esperado 2xx.

**G-0087 · Efeito irreversível já despachado (T7) pode sair com erro repetível (RS-10)**
- Onde: `ia-atendimento/src/ia_atendimento/ferramentas/gateway.py:221-233,303-309,341-346`; `ferramentas/saida.py:75-76`. No ramo: `ia-atendimento-b1-6a/src/ia_atendimento/ledger.py:460,474-479`.
- O que acontece: só timeout ou exceção genérica viram INDETERMINADO. Três furos: (a) `reconstruir` recusa a saída depois do disparo e levanta DESCONHECIDO; (b) erro tipado do executor (`BANCO_INDISPONIVEL` com `retry_apos_s`) passa como veio; (c) `CancelledError` escapa sem `_fechar`.
- Cenário mínimo: T7 «criada» com `ref_externa` de 11 dígitos sai DESCONHECIDO (o teste `test_ferramentas_gateway_revisao.py:292` já mostra isso). O modelo pode redigitar e duplicar a proposta.
- Correção: para `efeito_irreversivel` com `despachado=True`, toda falha posterior vira INDETERMINADO. Capturar `CancelledError` em `_rodar`, fechar e relançar. No ledger: `transitorio` de irreversível em `real|teste` vira `indeterminado`.
- Bloco: B5.4 (T7 contra o dublê); a parte do ledger em B1.6a.
- Teste que reprova antes: três testes de mutação: reconstrução inválida após disparo, `BANCO_INDISPONIVEL` após disparo e cancelamento após disparo; todos devem dar INDETERMINADO com registro. Ver também R2-013 e R2-017 (MÉDIO).

**G-0088 · T5 de 3RN/C6 é classe leitura: em sombra ou dublê vai à produção com CPF (RS-20)**
- Onde: `ia-atendimento/src/ia_atendimento/ferramentas/catalogo.py:165`; `ferramentas/modo.py:170-173`; `ferramentas/gateway.py:279`; `fixtures/duble/c6_simular.json:18`.
- O que acontece: T5 é `classe="leitura"` com `usa_cpf=True`. `Destinos.resolver` manda 3RN/C6 à produção em `sombra` e em `duble` com posse real. O teto de pagas só olha `leitura_paga`, classe que nenhuma ferramenta usa.
- Cenário mínimo: config global sombra, oferta C6, quatro T5 no turno: as quatro saem para o banco real com CPF real, sem teto por atendimento.
- Correção: decidir com o dono antes do G2: T5 de 3RN/C6 interceptada em sombra, ou `leitura_paga`, ou teto próprio por atendimento e por dia. Ligar o limitador do C6 antes de qualquer sombra.
- Bloco: B5.2/B5.5, decisão antes de G2 (sombra A, B9.2).
- Teste que reprova antes: parametrizado T5 × {3RN, C6} × {sombra, duble+posse}; nunca pode resolver `producao`.

**G-0125 · `nao_perturbe` e `limite_contratos` ausentes viram «sem bloqueio» na IA**
- Onde: `ia-atendimento/src/ia_atendimento/ferramentas/esquemas.py:112-113`; `pessoas_teste/formas.py:283`; `cliente360-api/src/c360api/rotas/pessoas.py:407-414`; `projecao.py:950`.
- O que acontece: a API tem três estados (objeto, `null`, ausente). `SaidaT1` colapsa ausente em `False`. O desfazer oficial de B4.2 é desligar a flag.
- Cenário mínimo: B4.2 desfeito com `C360_NAO_PERTURBE_30D` off; a chave some; a pré-condição `sem_nao_perturbe` da T7 passa para quem pediu para não ser procurado.
- Correção: campos obrigatórios ou tri-estado em `SaidaT1`; chave ausente vira erro tipado ou bloqueio. Emendar 03 §3 e §8: desligar a flag exige a IA desligada antes.
- Bloco: B5.2 (executor de T1).
- Teste que reprova antes: `test_t1_chave_ausente_bloqueia` com fixture sem as duas chaves.

**G-0126 · Destinos recusa http fora de loopback, mas os vhosts WG do papel são http://10.90.0.2 (RS-19)**
- Onde: `ia-atendimento/src/ia_atendimento/ferramentas/modo.py:43,96-98,130-133,142-147`; `tests/test_ferramentas_modo.py:199`; `docs/DECISOES-B5.1-0411.md:53`.
- O que acontece: `_conferir_url` só aceita https ou http em loopback. O 05 §2, o `ROT:710,1087` e o 08 decidem http puro no túnel. Com a base real, o gateway não sobe.
- Cenário mínimo: `Destinos.de_ambiente({"FACTA_BASE": "http://10.90.0.2:8093/facta-online"})` levanta `DestinosInvalidos`.
- Correção: exceção explícita para uma lista fechada de hosts WG (só 10.90.0.2), com teste que recusa qualquer outro http. Não afrouxar para «qualquer host privado». Acrescentar as bases ao `Settings` e ao pré-voo.
- Bloco: decidir em A4.4; código em B5.2/B5.4.
- Teste que reprova antes: `Destinos.de_ambiente` com as bases do papel deve subir; `http://10.90.0.3` deve seguir recusado.

**G-0090 · Minutos justapostos são descartados e a hora sai alta**
- Onde: `ia-atendimento/src/ia_atendimento/agenda_extrator.py:231,237,238,395-406,505-506`. Igual no ramo b1-6a.
- O que acontece: `_R_AS` não tem a guarda de dígito seguinte que `_R_H` tem. Em «às 15 30», o «30» fica sem dono e `_resolver` devolve 15:00 com confiança alta. Viola EM1 («ambíguo nunca vira alta»).
- Cenário mínimo: `extrair("pode ser às 15 30", agora=qui 10:00, ConfigAgenda())` dá 15:00 alta; «às 3 30 da tarde» também.
- Correção: guarda `(?!\s*\d+(?![\d/]))` em `_R_AS`, `_R_EMEIA` e `_R_QUAL`, ou `hora_incompleta` quando sobra número colado.
- Bloco: B5.7a (extrator e corpus).
- Teste que reprova antes: em `test_n8` e no corpus: «às 15 30», «as 9 30 da manhã», «às 3 30 da tarde» devem dar recusa ou 15:30 média.

**F4-009 · Hedge «perto das/lá pelas … da tarde» sai ALTA**
- Onde: `ia-atendimento/src/ia_atendimento/agenda_extrator.py:231` (`_R_QUAL` sem `\b`), `:211` (`_ANTES`), `:261` (`_R_HEDGE`), `:387-388` (`_tem_hedge`).
- O que acontece: o achado de `_R_QUAL` começa dentro da palavra («d|as», «pel|as»). A janela do hedge vê só «perto d» e não casa. A aproximação sai alta.
- Cenário mínimo: sonda `fase4-L2b.sh`: «perto das 3 da tarde» e «lá pelas 4 da tarde» saem alta; o controle «por volta das 3 da tarde» sai média.
- Correção: `\b` antes de `(?P<pre>…)` em `_R_QUAL`, ou janela medida do início da palavra. Junto: `cerca\s+d[aeo]s?` (F4-010).
- Bloco: B5.7a.
- Teste que reprova antes: um caso por hedge com a forma «N da tarde»; `test_n4` (`tests/test_agenda_extrator.py:620-632`) só cobre «15h».

#### ia-atendimento-b1-6a (PR #13)

**G-0131 · Execução morta no meio de T12/assumir/restaurar: `enviada` órfã vira `indeterminado` terminal (RS-10, RS-25)**
- Onde: `ia-atendimento-b1-6a/src/ia_atendimento/ledger.py:509-512` (`_repetida`), `:428` (`_dar_como_indeterminada`), `:447` (`_desfecho_da_falha`), `:76` (terminal), `:479`.
- O que acontece: quando a própria execução vê a falha, `acao_interna` fecha `transitorio`. Quando o processo morre, o retry fecha a linha `enviada` como `indeterminado` para qualquer classe. Contradiz D8 e o 08 §7.1 («não para o T12»).
- Cenário mínimo: worker morto (OOM, deploy) enquanto espera o `ia-repasse`. No retry, `t12:{atd}` vira `indeterminado` e nunca mais chama. O atendimento fica `repassando`, chat no Amado, bot desligado.
- Correção: em `_repetida`, `indeterminado` só para `efeito_irreversivel` em `real|teste`; demais classes voltam a `transitorio` e seguem para a reivindicação.
- Bloco: B1.6a (antes do merge do PR #13) e critério de B1.6b.
- Teste que reprova antes: linha `t12` e `assumir` em `enviada` de 10 min atrás; a chamada deve executar uma vez e fechar `ok`. Hoje fecha `indeterminado` sem chamar.

#### ia-atendimento-esteira (ramo `feat/esteira`, local, 178 commits atrás)

**F4-016 · Compose da esteira não sobe a main: `api:app` inexistente e env de 30/10 (RS-18, por G-0016)**
- Onde: `ia-atendimento-esteira/docker-compose.yml:42-51,86-94`; main `ia-atendimento/src/ia_atendimento/api/__init__.py:3-6`; `config.py:88,106-115`.
- O que acontece: o comando é `uvicorn ia_atendimento.api:app` sem `--factory`; a main só exporta `criar_app` e `ambiente:criar_app_de_ambiente`. O env passa `API_TOKEN` singular (descartado por `extra="ignore"`) e não traz sete campos obrigatórios. Boot falha fechado.
- Relacionados: G-0016 (worker aponta `ia_atendimento.fila.app`, `docker-compose.yml:96`) e G-0094 (Dockerfile sem `migrations/` e `fixtures/`).
- Correção: `uvicorn --factory ia_atendimento.api.ambiente:criar_app_de_ambiente` com as flags da OPERACAO §8; worker `python -m ia_atendimento.worker`; env com os nomes atuais do `Settings`.
- Bloco: A6.6b (venceu em 08/11); bloqueia A4.9.
- Teste que reprova antes: `tests/test_esteira.py:109,118` rodado contra a main.

**G-0095 · deploy-vps.sh pode anunciar a tag nova no ar sem tê-la trocado (RS-08)**
- Onde: `ia-atendimento-esteira/scripts/deploy-vps.sh:90` (`curl -sS` sem `-f`), `:98`, `:104-105` (resposta a `/dev/null`), `:109`, `:143-145`, `:152`.
- O que acontece: PATCH de `IMAGE_TAG` recusado (404, 422) não muda o código de saída. O `deploy?force=true` reimplanta a tag antiga e o script imprime «OK: vX no ar». O rollback tem o mesmo silêncio.
- Cenário mínimo: Coolify devolve 422 «This field is not allowed» (já visto em `cliente360-api/deploy/dev/liga-web.sh:69`); o Kan registra versão errada em produção.
- Correção: `curl --fail-with-body` em toda chamada; reler `IMAGE_TAG` após o PATCH; exigir `version == tag` e `git_sha` no corpo do `/healthz`.
- Bloco: A6.6 (esteira), antes de A4.9.
- Teste que reprova antes: no teste do script, o `curl` falso devolve erro no PATCH; o script deve sair diferente de 0. Hoje sai 0.

**G-0097 · DEPLOY.md manda arquivos 640 em /etc/ia-s4; o código recusa qualquer bit de grupo (RS-05, RS-07)**
- Onde: `ia-atendimento-esteira/docs/DEPLOY.md:62`; `ia-atendimento/src/ia_atendimento/cifra.py:113-114`; `segredos.py:47-48`; `ia-atendimento-esteira/Dockerfile:65`; `docker-compose.yml:26-27,34`.
- O que acontece: o código recusa `st_mode & 0o077 != 0`; o contêiner roda como uid 10001 com `cap_drop: ALL`. Só sobe arquivo 0600 com dono 10001. DEPLOY.md dá 640; ROTEIRO A4.9 dá 0600 sem dono e nome de arquivo errado.
- Cenário mínimo: 0640 root:10001 dá `ChaveInsegura`; 0600 root:root dá «ausente, ilegível». Falha certa no primeiro boot de A4.9.
- Correção: uma regra única em ROTEIRO A4.9, DEPLOY §4 e OPERACAO §2/§8: `chown 10001:10001`, `chmod 600`, montagem `/etc/ia-s4:/etc/ia-s4:ro`. Virar o kit de chave que RS-05 pede.
- Bloco: A4.9.
- Teste que reprova antes: sonda de aceite `stat -c '%a %u'` mais `docker run --user 10001 … python -c 'Chaveiro.de_arquivo(...)'` com o arranjo do DEPLOY.md; hoje falha.

#### gl-gateway

**G-0070 · main do gl-gateway sem proteção demonstrada; merge = deploy (RS-27)**
- Onde: `gl-gateway/.github/workflows/testes.yml:5,18,58`; `.github/CODEOWNERS:3`; `/opt/claude/docs/planejamento-ia/medicoes/INCIDENTE-3010-gateway.md:7`.
- O que acontece: push na main dispara o job `imagem` (build e deploy no Coolify da S2). Só existe o ruleset `main-protegida` (exclusão e force-push). D-09 («exigir PR também para admin») segue pendente. CODEOWNERS não cobre `app/` nem `*.sql`. O pytest ainda barra pelo estágio `testes` do Dockerfile.
- Cenário mínimo: `gh pr merge` fora da janela; o código vai ao ar em minutos (já houve incidente em 30/10).
- Correção: sonda `gh api` de rulesets; exigir PR com aprovação também para admin; `app/` e `*.sql` no CODEOWNERS; passo de janela e dia antes de qualquer merge.
- Bloco: D-09 (dono) antes de B6.0.
- Teste que reprova antes: sonda só-leitura `gh api repos/<org>/gl-gateway/rulesets` deve mostrar a regra de PR para admin. Hoje não mostra (não verificável daqui; ver nota G-0070).

#### cliente360-api

**G-0124 · Os 5 escopos da credencial da IA alcançam 19 operações (RS-29)**
- Onde: `cliente360-api/src/c360api/contrato/cliente360.json:280,1996,2225,3238,3350`; borda `escopos.py:89-98,162`.
- O que acontece: a borda autoriza por escopo, sem lista de operações por credencial. Os cinco escopos alcançam 19 operações, entre elas `/propostas:periodo` (CPF inteiro em `PessoaResumo`), `/mudancas` e a escrita `contratos:trocar-vendedor`.
- Cenário mínimo: só depois de B4.1, e exige vazamento do segredo da VPS ou executor que monte outra URL.
- Correção: decidir antes de B4.1: rotas `/v1/ia/*` próprias sob escopo `ia:ler`, ou lista positiva de `operationId` por credencial, ou risco aceito por escrito no 03 §1 com a tabela das 19.
- Bloco: B4.1.
- Teste que reprova antes: com a credencial da IA, `GET /propostas:periodo` e `POST /contratos:trocar-vendedor` devem dar 403. Hoje passam no `exigir`.

#### facta-on

**G-0118 · CPFs declarados «caso real» em comentários e testes, sem portão de PII (RS-13)**
- Onde: `facta-on/app/routers/online.py:594,2005,2089,5758`; `app/erros.py:389`; `app/seguro_teto.py:14`; `app/margem.py:32`; mais 7 linhas em `tests/`.
- O que acontece: o piiscan acha 65 ocorrências (30 valores) de CPF com DV válido fora de lista sintética. A varredura de histórico (`fase4/historico-pii.md:24`) conta 29 distintos ainda na main. Nove linhas dizem no texto que o número é de cliente. O repositório não tem gitleaks, piiscan nem varredura; o Dockerfile só roda pytest.
- Cenário mínimo: os números vão ao GitHub, à imagem de teste e a qualquer ferramenta que leia o repositório.
- Correção: trocar por referência sem dado (id do chamado, data, hash curto) e constantes de teste da faixa 000.000.0nn; adotar o piiscan do bancos-duble no estágio `testes` do Dockerfile. Histórico: decisão do dono (ver F4-036).
- Bloco: sem bloco na fonte. Sugestão: junto do primeiro PR do facta-on (B3.1).
- Teste que reprova antes: piiscan no estágio `testes` do Dockerfile; hoje acusa as 65 ocorrências.

#### bancos-duble

**G-0106 · Receita do README sobe facta-on sem guarda nem rede interna (RS-15)**
- Onde: `bancos-duble/README.md:38-50`; `docker-compose.yml:7-8,60-62`; `tests/guarda_origem.py:160`; `facta-on/app/config.py:321,325`; `cliente360_sink.py:112-113`.
- O que acontece: a receita põe o facta-on na rede `bancos-duble-net`, que não é `internal`, sem esvaziar as saídas da casa. O sink manda POST sempre que a URL não está vazia.
- Cenário mínimo: `/autorizar` sem localização cai em `_fallback_localizacao` (`online.py:1038`) e faz POST de {ddd, cpf} ao host da tailnet. Os CPFs são sintéticos. Um verificador rebaixou para MÉDIO (caminho de dev); a gravidade final ficou ALTO.
- Correção: caminho único que passe pela guarda (`isolado_app.py` numa rede `internal: true`); no mínimo, listar no README as 10 variáveis que precisam ficar vazias; emendar `ROT:924`.
- Bloco: B2.2.
- Teste que reprova antes: subir pelo README; nenhuma conexão pode sair da rede do compose. Hoje sai.

#### Kits e papel (ausência de controle sem código)

**G-0008 · Painel prevê escrita em produção sem kit nomeado ou com kit inexistente (RS-08)**
- Onde: `ROT:427` (PD-2), `ROT:684,717-727`; `fase0/inv-kits.tsv:21-28`.
- O que acontece: PD-2 exige kit com ensaio e contagem. A4.6 (13/11, com DROP CONSTRAINT na 0005) aponta `s4/migrar.sh`, que não existe. A3.8 venceu em 09/11 sem kit. O bloco de A4.6 cobre só 0001-0002 e grava o ledger fora da transação (G-0011).
- Correção: coluna «Kit» no Painel; PD-2 recusa linha sem kit; escrever `s4/migrar.sh` antes de 13/11 12:30.
- Bloco: A4.6, A3.8, A4.2, A4.4, A4.8, A5.9.
- Teste que reprova antes: `ensaio-local` de `s4/migrar.sh` em PG descartável, 2× seguidas e interrompido no meio. Hoje o kit não existe.

**G-0015 · Passos de infra A4.2, A4.4, A4.5, A4.7 e A4.8 sem kit nem ensaio local (RS-08)**
- Onde: `ROT:46,427,696,700`; `matriz-restricoes.md:510` («4 kits NÃO EXISTEM»).
- O que acontece: A4.2 (WireGuard e nft na S4, que roda o ISKRA) e A4.4 (nft da VPS e nginx de produção da S2) usam blocos do estudo E editados na janela. No passo 12, um `nginx -t` reprovado não aborta o script.
- Correção: kits ensaiados em contêiner para A4.2 e A4.4 com `--ensaio`, contagem e desfazer; registrar desfazer manual nos demais.
- Bloco: A4.2, A4.4.
- Teste que reprova antes: ensaio local com `nginx -t` falso reprovando; o kit deve abortar.

**G-0020 · D-15 sem saída quando a vigia morreu (RS-11)**
- Onde: `ROT:1063-1066`; `08:224,238,261`; `04:377,385`; `ia-atendimento/src/ia_atendimento/saude.py:53` (`batimento_idade_s: None`).
- O que acontece: batimento ausente bloqueia `Canal.nota` e `Canal.enviar`. A compensação «a vigia continua devolvendo» falha quando a causa é a própria vigia, que também grava o batimento.
- Cenário mínimo: timer da vigia para em t0; em t0+90 s a VPS entra em fail-closed; a nota do repasse não sai; aos 30 min o job para e o chat fica no Amado.
- Correção: adotar R-c2 em B6.4; em B1.6b/B6.3, com batimento ausente o job espera até 30 min, marca `repasse_travado` e entrega ao humano por ntfy prioridade 5. Alerta da VPS por canal que não passe pela S2.
- Bloco: B6.4 e B1.6b/B6.3.
- Teste que reprova antes: teste de morte da vigia (K-E16) com mutação fail-open; o lead deve ser entregue ao humano. Hoje não há código (critério de aceite).

**G-0032 · D-14 entrega o lead à vigia, mas a vigia não tem regra (R-c2 sem decisão) (RS-11, RS-25; RG-095)**
- Onde: `04:338,356,382,441`; `08:244`; `ROT:1066,1718`.
- O que acontece: aos 30 min o orquestrador grava `repasse_travado` e para. Nenhuma regra R-a..R-g trata `repassando` com orquestrador vivo e n8n fora. Só a R-b age, até 7 h ou 20:15.
- Cenário mínimo: n8n cai às 14:00 durante um repasse; o lead fica no Amado com bot desligado até alguém atender o crítico.
- Correção: R-c2 como critério de aceite de B6.4 (orquestrador publica a lista `repasse_travado` no batimento; vigia devolve por indicado ou `consultor_antes`).
- Bloco: B6.4, decidir antes do deploy #6 (16/11).
- Teste que reprova antes: K-E8 com n8n inativo; lead devolvido em até X min após os 30. Hoje o aceite passa com devolução manual.

**G-0055 · Fonte de `cpf_alterado` e `etapa_inapp` sem passo de construção nem linha na matriz**
- Onde: `ROT:997,1047,1049,1052`; `08:90,104`; `matriz-restricoes.md` (0 ocorrências).
- O que acontece: B6.2 manda gravar o perfil v2; E0 exige `cpf_alterado=false`. O 04 v2.2, que prevalece, não tem o campo. Não há DDL da view `v_etapa_inapp`. Um perfil sem o campo passa calado (`perfil_versao` padrão 1).
- Correção: RS nova (identidade do titular: ausente ou nulo vira recusa `identidade_inconsistente`); passo e kit com o DDL da view; default seguro no perfil v2.
- Bloco: B6.2 e B5.5.
- Teste que reprova antes: perfil sem `cpf_alterado`; E0 deve recusar. Hoje não há código.

**G-0056 · Robôs concorrentes no chat sob IA só parcialmente cobertos (RG-093)**
- Onde: `ROT:390,1340`; estudo N L10; contrato 02 l.19-21,132.
- O que acontece: lembrete do gl-inapp, outbox do c6-api e `robo-operacional-clt` enviam pela API do chatguru-api, não pelo chatbot. Desligar o chatbot não os afeta. O cerco foi cortado (C6).
- Correção: incluir os três no quadro de riscos com verificação (A3.4 estendido) e critério «nenhum outro emissor no chat sob IA»; sem resultado, piloto só em chats da TI.
- Bloco: A3.4.
- Teste que reprova antes: ensaio A3.4 com os três emissores ativos num chat de teste delegado ao Amado. Não rodado.

#### Lacunas de prova da própria revisão (Fase 4)

**F4-035 · F2-47 (kits) e F2-48 (check.sh ×3, PG descartável, vistos) nunca rodaram**
- Prova: `fase0/unidades.json:3079,3104`; `fase3/cobertura.json` pula de F2-41 para F2-49; `fase0/baseline.md:3` («testes e docker não foram executados»).
- Efeito: nenhuma RS tem parte «provado em ensaio». RS-08 e RS-12 ficam só por leitura. G-0076 (B1.6a+B1.8+B5.1 juntas) não foi testado.
- Correção: rodar F2-47 e F2-48; até lá, toda tabela de kit diz «PROVADO EM ENSAIO: nenhum» e RS-12 «não medida».
- Bloco: antes do «sim» do dono para A4.3a e A4.6.

**F4-036 · Histórico git dos 6 repositórios nunca foi varrido por gitleaks**
- Prova: PLANO-REVISAO-0911.md:62 pede «dir + histórico completo»; `fase0/baseline.md` seção (a) rodou só `gitleaks dir`.
- Efeito: RS-13 avaliada só no estado exportado. O CPF isento no `.gitleaksignore` (commit citado em G-0471) e os casos de G-0118 ficam sem varredura de histórico.
- Correção: dono roda `gitleaks git --redact` nos 6 checkouts e nos worktrees de `~/wt-ia` (sonda S24) e o piiscan sobre o commit isento (S23), devolvendo só contagem por regra.
- Bloco: antes de fechar RS-13.
- Estado em 10/11 ~14:40 (`fase4/historico-pii.md`): varredura feita na sessão principal, só leitura, nos clones de `~/repos` (falta o cliente360-api na tabela de CPF). gitleaks não achou segredo real. CPF de DV válido fora do prefixo 000: 36 distintos no histórico do facta-on, 29 ainda na main, sobretudo em `tests/amostras/consulta_fato_lote_20261104.jsonl` (9) e `app/routers/online.py` (7). Isso reforça G-0118. Pendente: decisão do dono e limpeza de histórico se forem reais. Worktrees de `~/wt-ia`: não verificado.

### MÉDIOS da Fase 3 que tocam restrição (111)

Grupos MÉDIO vivos da Fase 3, tipo código, costura, kit ou ausência de controle, com pelo menos uma RS. A prova é o primeiro membro do grupo em `fase3/grupos/G-nnnn.json`. A correção é a primeira frase da proposta do leitor; o texto inteiro está no JSON do grupo. Agrupados pelo repositório da prova principal. «papel» reúne roteiro, contratos e estudos.

#### ia-atendimento (42)

| Id | RS | Título | Onde (prova principal) | Correção em 1 linha |
|---|---|---|---|---|
| G-0049 | RS-12 | ia_app com UPDATE na tabela inteira do ledger, confirmações, cofre e agendamentos | `ia-atendimento/migrations/0001_esquema.up.sql:438` | GRANT UPDATE por coluna (estado, enviada_em, concluida_em, http_bucket, ref_externa, latencia_ms, custo_brl) e criterio de aceite com teste de transicao regressiva … |
| G-0064 | RS-26 | Gasto da main soma atendimento.custo_* por iniciado_em, não Σ passo.custo_brl; teto inerte (RG-004) | `ia-atendimento/src/ia_atendimento/chave.py:196` | Tornar a b1-6a pré-requisito de merge antes de ia_ativa; critério de aceite: o job turno chama avaliar_gasto antes do modelo, test_gasto_indisponivel_nao_chama_o_modelo, … |
| G-0082 | RS-25 | Lease de espera faz o lead dormir com a IA (até 96 h), contra a regra do roteiro | `ia-atendimento/src/ia_atendimento/estado.py:64` | Decidir e registrar no ROTEIRO/DECISOES qual regra vale para `aguardando_cliente` à noite. |
| G-0117 | RS-26 | Resposta sem `usage` grava tokens e custo ZERO; `custo_ausente` nunca dispara | `ia-atendimento/src/ia_atendimento/turno.py:413` | Em `como_decisao`, quando `uso_ausente` for verdadeiro, passar `tokens_entrada=None`, `tokens_saida=None`, `custo_brl=None`. |
| G-0128 | RS-22 | Origem c360_api/web grava modo (inclusive real) no orquestrador; só o BFF barra | `ia-atendimento/src/ia_atendimento/api/config_rotas.py:37` | No F0, o proxy 03 aceita so `ia_ativa` (modo volta no F1 com D-T30), ou o orquestrador exige `versao_esperada` para origem c360_api; teste de aceite que prove 404/403 em … |
| G-0271 | RS-06 | Atendimento que nunca encerra mantém dados para sempre (sem teto de poda) | `ia-atendimento/migrations/0001_esquema.up.sql:404-410` | Registrar como criterio: job expirar garante encerramento de todo nao encerrado em prazo finito, com consulta de forma (count de nao encerrados com atualizado_em > 30 d) … |
| G-0274 | RS-12 | Runtime publica a própria config e aprova artefatos (INSERT em config_versao/artefato_versao) | `ia-atendimento/migrations/0001_esquema.up.sql:437` | Criar um grupo NOLOGIN `ia_config` (operador/painel) dono do INSERT em config_versao e artefato_versao e tirar esse INSERT do ia_app. |
| G-0313 | RS-03 | Motivo de config em texto livre pode deixar nome em config_versao | `ia-atendimento/src/ia_atendimento/api/validacao.py:55-58` | Ou trazer D-T32 (código de lista fechada) para o F0 no web e no kit do TI, ou registrar no §11 que o F0 sai com texto livre e risco aceito pelo dono; no orquestrador, … |
| G-0393 | RS-25 | Sem tempo-limite por job: turno pendurado com worker vivo prende o chat | `ia-atendimento/src/ia_atendimento/worker_vivo.py:36` | Limite de tempo total por tarefa de chat (ex.: `asyncio.timeout` em `turno`, `iniciar`, `lembrete`, `retomar`, `encerrar_por_chave`), falhando alto para o `reaper_lease` … |
| G-0395 | RS-06 | Poda diária sem retry, sem recuperação de tick perdido e sem sinal | `ia-atendimento/src/ia_atendimento/fila.py:179` | Retry na `podar`, cada passo isolado (falha de um não pula os outros), poda também na subida do worker e um sinal consultável (ex.: `count(*)` de `conversa_cifrada` … |
| G-0397 | RS-01 | Bases de banco e Phoenix sem lista positiva de host | `ia-atendimento/src/ia_atendimento/ferramentas/modo.py:41-46` | Lista positiva por serviço (hosts de produção e do dublê fixados no código, como `HOSTS_DO_MODELO`) e `phoenix_endpoint` restrito a loopback ou à rede do túnel, com … |
| G-0402 | RS-16, RS-17 | `excepthook` mascara só por forma (sem segredos registrados nem nomes); só 2 segredos registrados | `ia-atendimento/src/ia_atendimento/scrubber.py:82` | `formatar_sem_pii` passa a usar `observabilidade.mascarar_texto` (ou a função de segredos desce para um módulo comum, evitando import circular). |
| G-0405 | RS-07 | Token ti único e onipotente, sem rotação | `ia-atendimento/src/ia_atendimento/api/app.py:78` | Aceitar lista de 1–2 tokens por origem (como as chaves do gateway) para rotação sem queda; separar o `ti` em escopos (config, replay de evento, anotação) ou ao menos … |
| G-0411 | RS-26 | Gasto do turno que falha não tem passo que o carregue (DecisaoModelo/Erro não aceitam `.uso`) | `ia-atendimento/src/ia_atendimento/turno.py:408` | Dar a Erro (ou a um novo tipo) os campos modelo, provedor, tokens_entrada, tokens_saida, custo_brl e latencia_ms e criar como_passo_de_falha(erro) em turno.py; em … |
| G-0412 | RS-26 | Sem teto de requisições ao modelo por turno (usage_limits) com ferramentas | `ia-atendimento/src/ia_atendimento/agente.py:297` | Passar um limite explícito de requisições por turno (ex.: 4) em agente.run e mapear o estouro para ErroDoModelo com código próprio; recalcular o tempo do turno … |
| G-0416 | RS-01 | Ramo loopback de MODELO_BASE_URL_1 (e transporte sem pino) contorna a lista positiva do host do modelo em produção | `ia-atendimento/src/ia_atendimento/config.py:235-238` | Criar o cliente com `httpx.AsyncClient(trust_env=False, follow_redirects=False)` em `ResolvedorModelo._criar`; aceitar loopback só com uma variável explícita de ambiente … |
| G-0417 | RS-23 | Aspas «» removidas depois dos filtros reconstituem link e `r$`: o cliente derruba o turno | `ia-atendimento/src/ia_atendimento/protecao.py:137` | Tirar «» (e colapsar espaços) ANTES de `mascarar` e dos regex, logo depois de `normalizar`; ou trocar «» por espaço em vez de apagar. |
| G-0419 | RS-23 | `SISTEMA` proíbe «liberado» e promessa de prazo, mas o validador do texto livre só barra «aprovado/garantido» | `ia-atendimento/src/ia_atendimento/modulos_fase.py:29` | Acrescentar `liberad[oa]s?` (fora de `{{valor_liberado}}`, que já é removido antes da checagem) e as formas de prazo de liberação mais comuns a `_PROMESSA`, com teste; … |
| G-0424 | RS-09 | Lembrete adiado rearma com instante absoluto: laço quente com relógio atrasado | `ia-atendimento/src/ia_atendimento/fila.py:113` | Rearmar o lembrete como o retomar: atraso relativo max(ate, agora + 5 s) - agora via schedule_in, no relógio da aplicação. |
| G-0427 | RS-09 | Dois calendários independentes (corpus F3 x orquestrador) divergem sem teste | `ia-atendimento/src/ia_atendimento/corpus/calendario.py:12` | Aceite da B8.1c: teste de propriedade que percorre novembro e dezembro de 2026 de 30 em 30 min e exige corpus.dentro_do_horario == Calendario.dentro_da_janela para a … |
| G-0428 | RS-19 | FACTA_BASE_TESTE só é comparada com o host de FACTA_BASE | `ia-atendimento/src/ia_atendimento/ferramentas/modo.py:131` | Lista positiva para a base de teste (loopback, sufixo/host do dublê na VPS) em vez de «diferente da produção»; recusar subir com `FACTA_BASE_TESTE` preenchida e … |
| G-0438 | RS-24 | Rearme (Adiar) sem teto: pausado pode dormir sem limite | `ia-atendimento/src/ia_atendimento/agenda_estado.py:193` | rearmar(…, teto_horas) com a mesma regra de _conferir_tetos (ultimo_cliente_em + agenda_teto_horas), levantando EntradaInvalida; ou item de aceite nomeado da B5.7c com … |
| G-0441 | RS-14 | «Pessoa de teste» em execução é o que o arquivo disser: carregar aceita qualquer UUID | `ia-atendimento/src/ia_atendimento/pessoas_teste/arquivo.py:52` | Em arquivo.carregar (ou no _montar), recusar no boot todo pessoa_id fora de catalogo_padrao().pessoa_ids() (ou, no mínimo, fora do prefixo FAIXA_DO_PESSOA_ID), com teste … |
| G-0443 | RS-31 | Fixtures de 3RN e C6: forma lida do código, sem payload medido e sem teste de deriva | `ia-atendimento/src/ia_atendimento/pessoas_teste/formas.py:3` | Versionar um recorte da forma de /3rn/calcular e /c6/oferta/simular (como o do 360) com script --verificar no check.sh, ou um teste de contrato contra o bancos-duble. |
| G-0447 | RS-10 | ia_app reescreve qualquer coluna do ledger ferramenta_chamada | `ia-atendimento/migrations/0001_esquema.up.sql:438` | Numa migração nova: REVOKE UPDATE ON ia.ferramenta_chamada FROM ia_app e GRANT UPDATE (estado, enviada_em, concluida_em, http_bucket, ref_externa, latencia_ms, … |
| G-0448 | RS-06 | Teto absoluto de vida do texto depende de criada_em gravado pelo ia_app | `ia-atendimento/migrations/0001_esquema.up.sql:313` | Numa migração nova: GRANT INSERT por coluna em conversa_cifrada sem criada_em/apagar_em (valem os DEFAULTs), ou CHECK criada_em <= now() + interval '5 minutes' e … |
| G-0449 | RS-06 | Poda de 365 d trava com FK simples entre atendimentos e pula podar_jobs | `ia-atendimento/migrations/0001_esquema.up.sql:204` | Trocar as duas FKs por compostas (atendimento_id, chamada_id) → UNIQUE (atendimento_id, chamada_id), ou fixar por CHECK/trigger que a T8 resolve uma T7 do mesmo … |
| G-0450 | RS-06 | FKs sem índice tornam a poda de 365 d quadrática | `ia-atendimento/migrations/0001_esquema.up.sql:202` | Numa migração nova: CREATE INDEX em passo (chamada_id) WHERE chamada_id IS NOT NULL, em ferramenta_chamada (atendimento_id, pessoa_id), em ferramenta_chamada … |
| G-0452 | RS-03 | Campos livres sem CHECK de forma aceitam 11 dígitos e ficam 365 d legíveis | `ia-atendimento/migrations/0001_esquema.up.sql:271` | Numa migração nova, CHECK NOT (campo ~ '[0-9][0-9.\- ]{9,}[0-9]') em passo.texto (ao menos para anotacao_operador), passo.motivo, motivo_escolha_nota e … |
| G-0470 | RS-13 | CI do ia-atendimento não roda gitleaks (nem conferir_catalogo); portão de segredos só local | `ia-atendimento/.github/workflows/ci.yml:33` | Acrescentar ao ci.yml da main um passo de gitleaks (binário com sha256 fixado, como no cabeçalho de gitleaks.sh) e um de conferir_catalogo.py com fetch de origin/main; … |
| G-0472 | RS-13 | varredura.py cobre menos do que o PD-6 promete | `ia-atendimento/scripts/varredura.py:8` | Acrescentar celular sem hífen (55?DDD9XXXXXXXX com lista sintética), CEP e UUID fora do prefixo sintético 00000000-0000-7000-8000. |
| G-0474 | RS-08 | chats-teste.sh: três caminhos em que o desfazer some ou engana | `ia-atendimento/kits/chats-teste.sh:169` | Guardar a lista também no `--vazio`. |
| G-0477 | RS-08 | Migrações de produção por bloco inline, sem kit nem ensaio, precheck incompleto | `ia-atendimento/docs/OPERACAO.md:4` | Passar a §3 para kit s4/migrar.sh com --ensaio, uma migração por invocação, palavra de confirmação por passo, contagens impressas e a terceira consulta do precheck … |
| G-0480 | RS-01 | Cliente HTTP do modelo sem trava de proxy nem redirecionamento | `ia-atendimento/src/ia_atendimento/agente.py:176` | Construir em _criar um httpx.AsyncClient próprio com trust_env=False e follow_redirects=False e passá-lo ao AsyncOpenAI; opcionalmente um event hook de request que … |
| G-0552 | RS-29 | T2, T3 e T10 sem usa_cpf, mas pessoas:propostas exige CPF no corpo | `ia-atendimento/src/ia_atendimento/ferramentas/catalogo.py:152` | Antes de B5.2: decidir e escrever no 03 §1c como T2/T3 obtêm o CPF. |
| G-0555 | RS-29 | Vigia de deriva do contrato pula no CI | `ia-atendimento/tests/test_fixtures_duble.py:397` | No check.sh, uma variável única (ex.: PORTAO_ESTRITO=1) que transforme esses skips em falha, e imprimir a data do origin/main da API usado no frescor. |
| G-0558 | RS-10 | SaidaT8 não expressa recusa_politica nem os vereditos do contrato | `ia-atendimento/src/ia_atendimento/ferramentas/esquemas.py:171` | Em B5.4, trocar `SaidaT8.estado` pelos vereditos do contrato (`criada`, `nada_criado`, `recusa_politica`, `indeterminado`, `aguardando`), com bump de versão da … |
| G-0559 | RS-10 | T8 de 1500 s segura vaga do limitador da FACTA (2 vagas) | `ia-atendimento/src/ia_atendimento/ferramentas/gateway.py:61` | Limitar só o trecho HTTP de cada tentativa (o executor da T8 pega e solta a vaga a cada consulta ao `conferir`, dormindo fora dela), ou vagas separadas para leitura … |
| G-0562 | RS-22 | Origem da escrita não gravada; publicado_por afirmado por quem chama | `ia-atendimento/src/ia_atendimento/api/config_rotas.py:191` | Sem DDL: uma linha de log na escrita aceita (`config gravada trace=… nome=… versao=… origem=…`, sem `por` nem `motivo`) e um contador por origem. |
| G-0569 | RS-01, RS-03, RS-34 | PHOENIX_ENDPOINT aceita qualquer host público e http, com conteúdo nos spans | `ia-atendimento/src/ia_atendimento/config.py:249` | Lista positiva no validador: loopback (`HOSTS_LOCAIS`) e, se o desenho pedir, o IP WG da VPS; `https` obrigatório fora de loopback. |
| G-0570 | RS-26, RS-33 | modelo_por_faixa passa na validação da config com par que o runtime recusa (e custo_max_brl duplicado) | `ia-atendimento/src/ia_atendimento/chave_registro.py:87` | Decidir no contrato 08 §9 qual chave manda (sugestão: mínimo das duas, limitado a R$ 3) e escrever isso no disjuntor. |
| G-0575 | RS-12 | App não exige sslmode=verify-full; DSN canônico não escrito | `ia-atendimento/src/ia_atendimento/config.py:182-201` | No validador `_banco_como_ia_app`: se o host não for loopback nem socket, exigir `sslmode=verify-full` e a presença de `sslrootcert`, `sslcert` e `sslkey` (erro sem … |

#### ia-atendimento-b1-6a (5)

| Id | RS | Título | Onde (prova principal) | Correção em 1 linha |
|---|---|---|---|---|
| G-0093 | RS-25 | expirar_parados encerra sem devolver o chat; justificativa não se sustenta e outbox sem publicador | `ia-atendimento-b1-6a/src/ia_atendimento/expiracao.py:9` | Critério de aceite da B1.6b: `expirar_parados` com posse real passa pelo repasse (fase 1 `repassando` + job `repasse`) em vez de encerrar direto; só encerra direto quem … |
| G-0116 | RS-10 | Sem reaper do ledger: linha T7 `reservada`/`enviada` órfã tranca pessoa+banco para sempre | `ia-atendimento-b1-6a/migrations/0001_esquema.up.sql:217` | Critério de aceite da B1.6b: `reaper_ledger` periódico que (a) fecha `reservada` mais velha que N minutos como `nao_criada` (nada saiu, libera a vaga), (b) fecha … |
| G-0399 | RS-26 | Preço ausente vira default embutido; contrato diz que o boot recusa | `ia-atendimento-b1-6a/src/ia_atendimento/config.py:49` | Remover os defaults (campo obrigatório) ou registrar o default como 'não configurado' e recusar o boot; versionar preço e câmbio com data e alertar após N dias; criar … |
| G-0455 | RS-10, RS-32 | Ledger não amarra ferramenta a classe de efeito/timeout/cerca; «T7 nunca repete» depende do chamador | `ia-atendimento-b1-6a/src/ia_atendimento/ledger.py:136` | No ledger: tabela fixa ferramenta → classe (`t7`, `t11`, nota = irreversível) e recusar `Pedido` divergente; recusar `Desfecho('transitorio')` de efeito irreversível em … |
| G-0458 | RS-26 | Custo ausente/nulo vira zero: teto não enxerga resposta sem usage e custo_ausente/125 % sem chamador | `ia-atendimento-b1-6a/src/ia_atendimento/gasto.py:50` | Em `como_decisao`, quando `uso_ausente` for verdadeiro, gravar `tokens_entrada`, `tokens_saida` e `custo_brl` como `None` (o contrato pede NULOS). |

#### ia-atendimento-esteira (4)

| Id | RS | Título | Onde (prova principal) | Correção em 1 linha |
|---|---|---|---|---|
| G-0465 | RS-08 | Rollback do deploy-vps.sh não sobrevive a interrupção nem a segunda execução | `ia-atendimento-esteira/scripts/deploy-vps.sh:138` | Gravar a tag anterior em arquivo de estado (0600, fora do repositório) antes do PATCH e lê-lo se existir; recusar quando `anterior == tag` sem `--forcar`; `trap` que … |
| G-0466 | RS-07 | Secrets do registry: DEPLOY.md quebra o job construir; credencial de escrita compartilhada | `ia-atendimento-esteira/docs/DEPLOY.md:76` | Escolher um desenho e escrever nos dois lugares: `construir` com um environment próprio (por exemplo `registry-s3`, regra de ref `refs/tags/v*`, sem revisor) que guarda … |
| G-0467 | RS-18 | Imagem implantada por tag mutável, não por digest | `ia-atendimento-esteira/docker-compose.yml:23` | `deploy-vps.sh` recebe ou lê do registry o digest da tag, mostra-o no plano, e depois do deploy confere na VPS o `RepoDigests` do contêiner. |
| G-0468 | RS-18 | /healthz da main não recebe git_sha/built_at: nomes de variável diferentes | `ia-atendimento-esteira/Dockerfile` | No rebase, gravar `GIT_SHA` e `BUILT_AT` no `ENV` da imagem (fonte única, sem variável no Coolify) e tirar esses dois do bloco de `export` do OPERACAO §8. |

#### facta-on (5)

| Id | RS | Título | Onde (prova principal) | Correção em 1 linha |
|---|---|---|---|---|
| G-0105 | RS-10 | Janela do conferir 20 min no duble x 10 min no facta-on | `facta-on/app/config.py:123` | Critério de aceite antes do piloto: provar o valor efetivo de `conferir_janela_min` no facta-on de produção (>= 20) por leitura da configuração viva, e acrescentar ao … |
| G-0107 | RS-19 | conferir sem piso no desde e sem autenticação: histórico por CPF com link | `facta-on/app/routers/online.py:4869` | No facta-on (no PR da B3.2): recusar com 400 «desde» mais antigo que um teto (por exemplo 24 h; o orquestrador usa no máximo 25 min) e teste que reprova sem isso. |
| G-0355 | RS-10 | Guarda por-cpf cega para proposta manual ou estourada até o ciclo do robô | `facta-on/app/routers/online.py:4704-4705` | Medir o intervalo real do robô (config no banco, só leitura) e registrá-lo; declarar a janela cega como risco residual no contrato 05 com mitigação explícita (repasse se … |
| G-0503 | RS-10 | nao_criada aceita ciclo do robô que listou antes da janela ou foi interrompido | `facta-on/app/routers/online.py:4839` | Gravar na config o instante de INÍCIO da listagem do último ciclo completo e comparar esse instante com decide_em; registrar o ciclo interrompido por parada como não … |
| G-0504 | RS-27 | Deploy automático do facta-on sem prova de saúde e CODEOWNERS sem app/ | `facta-on/.github/workflows/testes.yml:54` | Antes do #5: sonda só-leitura da proteção da main e do environment production (gh api, D-09). |

#### bancos-duble (8)

| Id | RS | Título | Onde (prova principal) | Correção em 1 linha |
|---|---|---|---|---|
| G-0102 | RS-31 | Anonimizador mantem texto livre de 21 campos | `bancos-duble/anonimizador/duble_anon/allowlist.yaml:109` | Aplicar ao anonimizador o remédio da colheita: `status_*` só com o código (`NN`); `averbador`, `convenio`, `produto`, `tabela` e as descrições (`cbo`, `cnae`, bloqueio, … |
| G-0103 | RS-31 | piiscan nao serve de portao para nome sem denylist | `bancos-duble/piiscan/detectores.py:212` | Definir o portão desta revisão como `piiscan --denylist <arquivo fora do repo> --exigir-denylist`, com a denylist gerada dos nomes reais de clientes e vendedores do … |
| G-0485 | RS-13 | piiscan: falsos negativos estruturais de CPF e celular | `bancos-duble/piiscan/detectores.py:55` | Detectar CPF com DV válido no sufixo de 11 de sequências de 12 a 14 dígitos cujo prefixo seja só zeros. |
| G-0486 | RS-13 | piiscan pula calado: pragma, diretorios e nomes de arquivo | `bancos-duble/piiscan/varredura.py:141` | Honrar o pragma só em extensões de código e documento (`.py`, `.md`, `.toml`, `.sh`, `.yml`), nunca em `.json/.ndjson/.csv/.txt`, e imprimir a contagem de linhas … |
| G-0492 | RS-31 | Forma medida vazia: fidelidade --estrito passa sem comparar | `bancos-duble/docs/forma-medida.json:4` | Rodar a colheita (ou declarar por escrito o risco aceito «dublê só sintético», como a D-26 previa). |
| G-0493 | RS-08 | Colheita sem registro, proveniencia nem pino de versao | `bancos-duble/docs/COLHEITA.md:39` | Empacotar de um ref explícito (`git archive <sha de origin/main>`), fazer o colheita_s2.sh imprimir o sha256 de tools/colheita.py, tools/forma.py e … |
| G-0501 | RS-13, RS-31 | CI do bancos-duble: gitleaks sem historico, piiscan sem exigir denylist, branch sem PR nao roda | `bancos-duble/.github/workflows/ci.yml:55` | No CI: `fetch-depth: 0` e um segundo passo `gitleaks git --log-opts="origin/main..HEAD"` (ou `HEAD` na main), mais o piiscan sobre os blobs adicionados no PR. |
| G-0557 | RS-10 | Camada B nao reproduz casos que decidem T7/T8 | `bancos-duble/scripts/stubs_b.py:335` | Dar à camada B: cenário de 503 (os dois `result`, com `Retry-After`) e 400 em `conferir`/`por-cpf`; persona com placeholder; `esteira_lida_em` preenchido em … |

#### gl-gateway (4)

| Id | RS | Título | Onde (prova principal) | Correção em 1 linha |
|---|---|---|---|---|
| G-0101 | RS-03 | Nada obriga allowlist nas rotas ia-*: corpo_campos NULL manda o Post inteiro, assinado | `gl-gateway/app/rotas.py:189` | Fechar no codigo e no banco, nao so no kit: (a) em rotas._carregar_db, rota com entrada em GATEWAY_ASSINATURAS (ou com prefixo ia- fora de uma lista explicita de … |
| G-0481 | RS-07 | Origem de ips_confiaveis entra no HMAC como se viesse do token | `gl-gateway/app/main.py:427` | Rota com segredo (HMAC ou x-gl-servico) exige autenticacao por token: se via_ip, responder 401/403 antes do forward. |
| G-0484 | RS-27 | Gateway: deploy automático sem verificação pós-deploy (health none, /health constante) | `gl-gateway/.github/deploy-targets/gl-gateway-production.json:7` | Criterio de aceite antes do merge de qualquer PR da IA: (a) sonda pos-deploy no pipeline ou no kit (portao.sh/aguardar-reinicio.sh) que faz um POST autenticado a uma … |
| G-0542 | RS-06 | Expurgo de 7 dias de gateway.payloads fora do repositório do gateway | `gl-gateway/init_payloads.sql:35` | Sonda só de leitura na S2 (com o «!» do dono): contagem e menor recebida_em de gateway.payloads, geral e por rota ia-%. |

#### cliente360-api (1)

| Id | RS | Título | Onde (prova principal) | Correção em 1 linha |
|---|---|---|---|---|
| G-0507 | RS-29 | SO_CREDENCIAL_PROPRIA só tira o escopo do preset TI | `cliente360-api/src/c360auth/admin/catalogo.py:217` | Ou o contrato 03 passa a dizer que a barreira é cargo ti + TTL/expiração + revogação (e a prova de B4.3 inclui criar chave personalizada com ia:chave junto de outro … |

#### kits/config (2)

| Id | RS | Título | Onde (prova principal) | Correção em 1 linha |
|---|---|---|---|---|
| G-0528 | RS-08 | gerar da cópia instalada cai em checkout velho | `kits/config/chats-teste.sh:98` | Na cópia instalada, exigir `IA_REPO` explícito (falhar sem ele) ou fazer o instalador gravar na cópia o caminho e o SHA do checkout de origem e o `gerar` recusar … |
| G-0529 | RS-08 | chats-teste.sh: ensaio cego e --vazio sem guarda | `kits/config/chats-teste.sh:124` | Dar ao ensaio um modo que faça só o GET (somente leitura) e imprima versão, lista vigente e lista resultante; guardar a lista também no `--vazio`; depois do PUT, refazer … |

#### kits/gateway (12)

| Id | RS | Título | Onde (prova principal) | Correção em 1 linha |
|---|---|---|---|---|
| G-0014 | RS-08, RS-14 | Sumidouro guarda o Post inteiro por 7 dias, sem purga e sem trava contra chat real | `kits/gateway/rotas-ia.sh:27` | Antes de ativar, conferir no ChatGuru que o diálogo está ligado só ao chat de teste. |
| G-0109 | RS-08 | Volta do ativar-sumidouro desliga todas as rotas ia-% | `kits/gateway/ativar-sumidouro.sh:10` | Acrescentar `desativar-sumidouro.sh` (ou `ativar-sumidouro.sh --desativar`) com --ensaio/--confirmo: UPDATE só de path='ia-sumidouro', conferência de que as demais ia-% … |
| G-0110 | RS-08 | Kit do gateway não confere o próprio sha256 e aceita transporte de ensaio com --confirmo | `kits/gateway/lib.sh:16` | Criar um «conferir-kit.sh» (ou função em lib.sh chamada por parse_basico quando CONFIRMO=1) que compara sha256 de todos os arquivos do kit com um MANIFESTO ao lado e … |
| G-0111 | RS-08 | Ensaio não cobre passo a passo D-04 nem E-12 | `kits/gateway/ensaio-local.sh:108` | Trazer a prova de 03/11 para dentro do ensaio-local.sh (ou um ensaio-d04.sh no kit, com sha no MANIFESTO): seção E-12 (--ensaio, --confirmo, 2ª execução, --apagar, … |
| G-0508 | RS-03, RS-06, RS-14, RS-30 | ia-sumidouro guarda o Post inteiro (7 d) sem trava de chat, sem auth e sem fim de vida/purga | `kits/gateway/rotas-ia.sh:27` | Adicionar passo final de A3: desativar ia-sumidouro (UPDATE ativo=false) e apagar payloads da rota; exigir Header Auth no webhook; opcionalmente allowlist de chat_id da … |
| G-0511 | RS-08 | Sentinela 401 da vigia sem controle negativo: IP confiável dá verde com credencial perdida | `kits/gateway/vigia.sh:108` | Abrir a sentinela com um controle negativo: POST com token aleatório tem de dar 401; se der 404, falhar com «este IP é confiável: a sentinela não mede nada daqui». |
| G-0512 | RS-08 | Volta do env usa snapshot congelado | `kits/gateway/env-gateway.sh:123` | Em env-gateway.sh, quando o ponteiro existe e o Coolify ainda não tem o env novo, comparar lido-antes com o snapshot e falhar se diferirem (mandar refazer o snapshot). |
| G-0513 | RS-07 | entregar-hmac-vps.sh perde variáveis no sudo | `kits/gateway/entregar-hmac-vps.sh:23` | Pôr as atribuições dentro do script remoto (interpoladas com printf %q) ou depois do sudo via «sudo -n env VAR=… bash -c», e acrescentar «set -u» no script remoto. |
| G-0514 | RS-08 | Vigia: destino_erro fora do critério e janela sem linhas passa | `kits/gateway/vigia.sh:69` | Incluir destino_erro no relatório por rota com comparação contra ontem (reprovar se hoje > ontem + margem). |
| G-0516 | RS-08 | Sem registro do ato; ultimo-gravar.txt não prova gravação | `kits/gateway/env-gateway.sh:144` | Gravar em $SEGREDOS_DIR/atos.log (0600) uma linha por execução com --confirmo: data UTC, script, flags, sha256 do kit, resultado, NDEP antes/depois. |
| G-0517 | RS-08 | Plano B não diz se colar é acréscimo ou substituição | `kits/gateway/env-gateway.sh:12` | Reescrever a instrução: «na Developer view, localizar e substituir APENAS as linhas destas variáveis; conferir que o número total de variáveis depois = antes + 2». |
| G-0546 | RS-07 | Rotação HMAC não tira a chave antiga | `kits/gateway/entregar-hmac-vps.sh:48` | Acrescentar `--encerrar-virada` (regrava só a 1ª linha, confere 1 linha, modo e dono) e imprimir ao fim de toda gravação «reinicie o orquestrador para valer». |

#### kits/s4 (5)

| Id | RS | Título | Onde (prova principal) | Correção em 1 linha |
|---|---|---|---|---|
| G-0112 | RS-08 | Kit S4 roda de diretório vivo fora do git sem conferir sha256 antes do sim | `kits/s4/README.md` | Pôr no README um passo 0 obrigatório: `sha256sum ~/retomada-2809/fila-2910/ia/s4/* / diff - <bloco do MANIFESTO>` antes de cada «sim». |
| G-0113 | RS-07 | Senha dos logins sai da S4 contra o que o kit declara; ponte até a DATABASE_URL sem kit | `kits/s4/s4-papeis.sh:13` | Corrigir o comentário do kit e o README. |
| G-0523 | RS-12 | Leitura do bkp_pg no esquema ia não é conferida; prova de A4.3a é vazia | `kits/s4/provar.sh:85` | Na pré-condição de s4-papeis.sh, exigir `rolsuper OR pg_has_role('bkp_pg','pg_read_all_data','MEMBER')`. |
| G-0574 | RS-07, RS-12 | /etc/ia-s4 junta credenciais de ia_app_a e ia_obs_a sob o mesmo grupo 10001; Phoenix lê a chave do runtime | `kits/s4/distribuir-certs.sh:11` | Separar em /etc/ia-s4/app (grupo do orquestrador) e /etc/ia-s4/obs (grupo próprio do Phoenix), cada contêiner montando só o seu subdiretório. |
| G-0576 | RS-12 | Orçamento de conexões do ia_app_a (até 26) passa do limite 20 | `kits/s4/s4-papeis.sh:83` | Decidir o orçamento e escrevê-lo no kit e no OPERACAO: ou subir o limite do `ia_app_a` para 32 (o cluster é compartilhado com o ISKRA: conferir `max_connections` antes), … |

#### papel (roteiro, contratos, estudos) (23)

| Id | RS | Título | Onde (prova principal) | Correção em 1 linha |
|---|---|---|---|---|
| G-0018 | RS-27 | Merge = deploy no facta-on sem trava técnica, com PRs não-rascunho abertos | `ROTEIRO-DE-ACAO.md:855` | Antes de 12/11, fechar ou converter #15 e #16 em rascunho. |
| G-0021 | RS-10 | B5.4 não define o fim do ledger indeterminado depois de T8 | `ROTEIRO-DE-ACAO.md:992` | Acrescentar a B5.4 a tabela de estados do ledger T7/T8 (criada → ok; nao_criada após janela de 20 min → nova chave só se corrigível, senão repasse; aguardando > 25 min → … |
| G-0025 | RS-08 | No degrau, o ativar.sh fica sem reserva em 19/11 | `ROTEIRO-DE-ACAO.md:1293` | Escrever no roteiro o ramo «ativar.sh falhou em 19/11»: ou antecipar a ativação para 19/11 12:30 com o ensaio a seco de manhã, ou o dono pré-autorizar por escrito uma … |
| G-0033 | RS-17, RS-29 | Regex da matrícula aceita forma de CPF; guardas só comparam com o CPF do job ou dependem de PR inexistente | `08-orquestrador.md:45` | Rejeitar na API a forma de CPF (11 dígitos com dígitos verificadores válidos, ou pontuada ###.###.###-##) com 422 sem eco; fechar o regex pela medição H3 antes do … |
| G-0034 | RS-25 | Seção Desfazer (§10) ignora 0004/0005; sem kit de migração nem de domingo | `contratos/08-orquestrador.md:291` | Reescrever §10 com tabela de desfazer por migração (0003: DROPs do cabeçalho; 0004: DROP TABLE/FUNCTION; 0005: 0006 com pré-condição); entregar kit de aplicação com .bak … |
| G-0041 | RS-05 | Phoenix monta o diretório inteiro /etc/ia-s4 (chaves do ia_app e AES) | `estudos/semana-1/e-infra-s4-vps.md` | Diretorios separados por servico (/etc/ia-s4/orq e /etc/ia-s4/phoenix, ou mounts de arquivo individual), conversa.keys fora do alcance do Phoenix, uma unica origem da … |
| G-0042 | RS-10 | VPS chega a todas as rotas de digitação e ao cliente360-api inteiro | `estudos/semana-1/e-infra-s4-vps.md` | Allowlist por metodo+caminho (so as rotas que a IA usa), token de aplicacao por chamador, e o orquestrador em rede propria; a pergunta 5 deve dizer que inclui rotas de … |
| G-0046 | RS-20 | Formalizar 3RN/C6 e chatguru-api sem token na rede da VPS | `estudos/semana-1/f-catalogo-ferramentas.md` | Critério de aceite: o vhost da VPS publica só as rotas FACTA do MVP (consultar/esteira, calculadora, conferir, por-cpf, formalizar) e as de leitura dos demais; token de … |
| G-0052 | RS-28 | Ack e escalonamento ao dono sem mecanismo; tópico ntfy forjável | `j-operacao-piloto.md:228` | Especificar no B6.6/B6.4: ack = mensagem com formato fixo lida pela vigia, e re-alerta só pára com ack de publicador com token (ntfy próprio) ou com confirmação na linha … |
| G-0081 | RS-03 | 20 AJUSTAR do Codex (E-23) sem dono nem data | `ROTEIRO-DE-ACAO.md:1474` | Triar os 20 itens em adotado, rejeitado ou adiado com data, antes do DDL do espelho (B6.4) e antes do pedido de allow; registrar dono por item. |
| G-0130 | RS-32 | Envio incerto sem regra no 08 nem valor no DDL; chave de saída diverge entre 02 e código | `contratos/02-chatguru-api.md` | Emendar o 08 com a regra do envio incerto: ledger indeterminado; passo resposta_enviada com entrega='falhou' e motivo/resultado 'incerta' (ou valor novo por migração); … |
| G-0164 | RS-11 | Batimento: folga de 15 s sobre timer de 60 s; relógio e AccuracySec não escritos | `ROTEIRO-DE-ACAO.md:1063` | Fixar AccuracySec=1s e escrita do batimento como primeira ação do ciclo; documentar que a VPS compara gerado_em com o próprio relógio e a tolerância (por exemplo chrony … |
| G-0188 | RS-14 | Painel-dev pode alterar invariantes das rotas ia-* | `contratos/01-gl-gateway.md:30` | Acrescentar ao contrato a lista de quem escreve (painel, TI) e uma verificação recorrente (vigia ou SQL do kit repetível) de origens, destino e ips_confiaveis das rotas … |
| G-0231 | RS-22 | Recusas e PUT de resultado desconhecido sem auditoria no F0 | `contratos/07-cliente360-web.md` | Subir a auditoria por tentativa (operador, nome, valor, resultado, trace_id, sem motivo) para o F0 e gravar antes do PUT e de novo com o resultado. |
| G-0245 | RS-06 | Retenção depende de worker vivo; sem sinal de falha da poda | `estudos/semana-1/a-esquema-ia-atendimento.md` | Critério de aceite: alerta/consulta diária que falha se existir linha vencida (conversa_cifrada.apagar_em < now(), atendimento encerrado há mais de 365 d), e … |
| G-0268 | RS-23 | Mecanismo da regra 12 não cobre numeral por extenso, nome de banco e histórico com valores | `h-roteiro-conversa-memoria.md P3, §3.1 bloco 6, §3.4` | Guardar a fala da IA no histórico com placeholders; ampliar T15 com numerais por extenso, datas relativas e nomes de banco fora de placeholder; declarar quais … |
| G-0287 | RS-21 | Mensagem pendente do cliente entra no modelo sem RS de PII | `ROTEIRO-DE-ACAO.md:1043` | Acrescentar RS (mensagem pendente: apenas fala do cliente após a última saída, máx. |
| G-0300 | RS-22 | PAINEL_IA_OPERADORES é lista nova sem passo, dono nem semente; conflita com D4 | `estudos/TELA-IA-C360.md:990` | Definir uma única fonte de operadores (ou declarar a ligação entre as listas), incluir a semente de uid e a hora do ajuste de env no mapa de deploys, e citar no B7.1. |
| G-0303 | RS-21 | Motivo da chave em texto livre; nome de cliente persiste em config_versao | `TELA-IA-C360.md:1338` | Tornar o motivo código de lista fechada já no F0 (custo pequeno) ou registrar aceite explícito do dono do risco de nome em config_versao no F0; corrigir o status … |
| G-0315 | RS-25 | Ensaio a seco de 18/11 com prontidão nula por artefatos_ausentes até 19/11 | `contratos/03-cliente360-api.md` | Fixar no roteiro quando as quatro linhas artefato_versao v0/v1 entram na S4 (antes do ensaio de 18/11, com 'sim' do dono) e acrescentar ao aceite de B9.1 'prontidão … |
| G-0349 | RS-09 | Reabertura de 23/11 sem verificação da dependência real nem monitor | `ROTEIRO-DE-ACAO.md` | Critério de aceite de B11.1: leitura manual, na tarde de 19/11 e às 06:30 de 23/11, de eSocial/MTE e do calendário Dataprev; um disparo real de consulta de baixo custo … |
| G-0364 | RS-08 | Somente leitura só de sessão, como superusuário | `consultas/roda-s2.sh:12` | Criar role só-leitura (pg_read_all_data) para medição, ou usar PGOPTIONS='-c default_transaction_read_only=on' na conexão; não aceitar SQL arbitrário em q.sh sem esse … |
| G-0567 | RS-32 | Nota do orquestrador + nota da vigia: espelho só sabe da nota após a etapa rota (segunda nota) | `04-n8n-braco-espelho.md:321` | Documentar a tolerância a duplicata no caminho da vigia, ou ler o RPA do chat antes de escrever (já existe a guarda), e citar 02 §3/§5 para ator e tamanho no §7. |

### MÉDIOS da Fase 3 sem RS (65)

Grupos MÉDIO vivos da Fase 3, tipo código, costura, kit ou ausência de controle, **sem** RS no campo `rs` de `fase3/consolidado.json`. Filtro: `sev=MEDIO`, `tipo` em {codigo, costura, kit, ausencia-de-controle}, `estado` em {confirmado, confirmado em parte}, `rs` vazio. Dá 65 grupos; 58 não apareciam em nenhuma outra parte deste documento. O sinal ¹ marca os 7 já citados em outra seção.

- **Prova:** primeiro membro de `fase3/grupos/G-nnnn.json`, campo `provas[0]`, sem o trecho. Caminhos de código relativos a `src/`; `contratos/NN` = contrato vigente; `ROTEIRO-DE-ACAO.md` = ROT.
- **Correção:** primeira frase da proposta do primeiro membro; o texto inteiro está no JSON.
- **Bloco na correção:** blocos do roteiro citados nas correções do grupo (busca por `A\d`/`B\d`). «sem bloco na fonte» quando nenhuma correção nomeia bloco. Não é atribuição de bloco: a sessão principal confirma.
- **Fila:** entram no PR do bloco quando o bloco está aberto; o resto vai para depois do piloto, com «sim» por item (§3.3).

#### Sem RS · ia-atendimento (24)

| Id | Estado | Tipo | Título | Onde (prova principal) | Correção em 1 linha | Bloco na correção |
|---|---|---|---|---|---|---|
| G-0077 ¹ | conf. | costura | cpf_alterado não está no contrato 04 nem no código; roteiro cita como se estivesse | `ia-atendimento/src/ia_atendimento/contexto.py:75` | Emendar o 04 §2.5 com as quatro chaves de `perfil_versao=2`, tipo e origem de cada uma (inclusive de onde o braço lê `cpf_alterado`), e pôr no 08 §3 a remissão. | B5.5 |
| G-0092 | conf. | costura | Lista do SIM do corpus com 4 entradas fora da lista fechada | `ia-atendimento/src/ia_atendimento/corpus/vocabulario.py:298` | Reduzir SIMS aos 6 de H (e ajustar README:60 e os testes) ou levar as 4 ao dono como decisao e mudar H e o plano antes. | sem bloco na fonte |
| G-0366 | conf. | codigo | Código da agenda ainda usa sábado até 12:00, contra D-18 | `calendario.py:41` | Alinhar calendario/regras ao D-18 (B8.1c) e ao texto reemitido de TX-M03. | B8.1c |
| G-0390 | conf. | codigo | aplicar é público e sem tabela de transições; de=None pula o filtro de estado | `ia_atendimento/estado.py:411` | Em `aplicar`: `if de is None: raise TypeError` e, quando `mudancas.estado` vier, conferir o par (origem permitida → destino) contra uma tabela única de transições no … | sem bloco na fonte |
| G-0392 | conf. | codigo | lembrete com lock do chat e retry de 30 s segura turnos e pode repetir envio | `ia-atendimento/src/ia_atendimento/fila.py:57` | Tirar o retry do `lembrete` com lock e deixar a repetição no alarme sem lock (o `alarme_lembrete` já tem retry), ou em caso de falha transitória reagendar um alarme novo … | B1.6b |
| G-0394 | conf. | codigo | /readyz descarta sinais moles da fila | `ia-atendimento/src/ia_atendimento/api/saude.py:48` | Devolver `falhados_15min`, `listen_notify`, `workers_vivos` e `todo_mais_velho_s` no corpo do `/readyz` (ou do `/saude`) e fazer a vigia alertar por eles. | sem bloco na fonte |
| G-0398 | conf. | ausencia-de-controle | Chaves HMAC fracas e as do vetor público do contrato sobem | `ia_atendimento/config.py:106-109` | Recusar no boot as chaves conhecidas dos vetores (lista de resumos SHA-256, sem o valor) e exigir formato de alta entropia (64 hex ou base64 de 32 bytes) para as chaves … | sem bloco na fonte |
| G-0403 | em parte | costura | /healthz devolve git_sha e built_at desconhecido por nomes de variável divergentes | `ia-atendimento/src/ia_atendimento/api/ambiente.py:79` | Unificar os nomes (ler `IA_GIT_SHA`/`IA_BUILT_AT`/`IA_VERSION`, ou a imagem exportar `GIT_SHA`/`BUILT_AT`); | sem bloco na fonte |
| G-0406 | conf. | ausencia-de-controle | Sem limite de taxa nem lockout; alarme 401/403 só em memória | `ia-atendimento/src/ia_atendimento/api/app.py:174` | Pôr as flags do uvicorn no compose; | sem bloco na fonte |
| G-0408 | conf. | costura | `delegacao_externa` é calculado e jogado fora: humano no chat não muda nada | `ia_atendimento/api/eventos.py:114-117` | Decidir no contrato o efeito: no mínimo gravar um código em `contexto_codigos` e contar; | sem bloco na fonte |
| G-0415 ¹ | conf. | ausencia-de-controle | contexto_codigos é canal de código livre do modelo para dado persistente, sem catálogo | `ia-atendimento/src/ia_atendimento/turno.py:197` | Catálogo fechado de contexto_codigos (Literal ou conjunto versionado) validado no Turno; | sem bloco na fonte |
| G-0430 | em parte | codigo | Falhas engolidas sem tipo: verificador quebrado parece recusa de negócio | `ia_atendimento/ferramentas/gateway.py:437` | Registrar o tipo da exceção (`type(e).__name__`, nunca a mensagem) em log e em atributo do span nos quatro pontos; | sem bloco na fonte |
| G-0431 | conf. | codigo | Ações internas do código dividem o teto de 4 síncronas do turno | `ia_atendimento/ferramentas/gateway.py:282` | Isentar `acao_interna` (e as chamadas com `pelo_modelo=False`) do teto do turno, ou dar ao código um orçamento próprio; | sem bloco na fonte |
| G-0434 | em parte | costura | horario_unico agenda único candidato válido ignorando outra leitura | `agendamento.py:157-163` | Em horario_unico, retornar SemHora (ou um marcador «ambíguo») quando len(resultado.candidatos) > 1, a menos que a razão do descartado seja antecedência/passado do «hoje» … | B5.7c |
| G-0437 | conf. | codigo | fechar_volta_perdida sobrescreve o desfecho de uma volta que deu certo | `ia-atendimento/src/ia_atendimento/agenda_estado.py:254` | Dentro de fechar_volta_perdida, só agir se esperando_a_volta(entrada, estado, gatilho) for verdade (devolver None caso contrário), ou receber a acao do lease e recusar o … | sem bloco na fonte |
| G-0475 | conf. | ausencia-de-controle | «Todo teste reprova sem a mudança» sem mecanismo, só prosa | `ia-atendimento/scripts/check.sh:21` | Para os aceites que citam «provado por mutação», versionar um script por bloco (ex.: scripts/mutacoes/<bloco>.sh) que aplica a mutação nomeada, roda os testes-alvo e … | sem bloco na fonte |
| G-0479 | em parte | ausencia-de-controle | Operador e substituto não nomeados; rotinas manuais sem dono | `ia-atendimento/docs/OPERACAO.md:34` | Seção 'Papéis' em OPERACAO com operador, substituto e contato; | sem bloco na fonte |
| G-0534 | em parte | costura | Replay sem hora: janela de 5 s contra timeout de 30 s do gateway; `message_id` recusado | `ia-atendimento/src/ia_atendimento/linha_tempo.py:30` | Decidir e escrever no contrato 08 §5.1: ou (a) incluir o id da mensagem do ChatGuru na allowlist A10 da rota `ia-mensagem` e mapear para `mensagem_id` (chave `cgid:`, … | A10 |
| G-0535 | conf. | codigo | reaper_lease para no primeiro lease que falha | `ia-atendimento/src/ia_atendimento/jobs.py:267` | Tratar cada lease isoladamente: capturar a exceção por item, registrar só o id truncado e o tipo, seguir para o próximo e falhar o job no fim se algum falhou (para a … | sem bloco na fonte |
| G-0536 | conf. | codigo | queueing_lock do turno é por chat, mas o argumento do job é o atendimento | `ia-atendimento/src/ia_atendimento/fila.py:240` | Usar `queueing_lock=turno:{atendimento_id}` (o `lock=chat:` continua serializando por chat), ou fazer o handler do turno resolver o atendimento ATIVO do chat em vez de … | sem bloco na fonte |
| G-0540 | conf. | costura | Dedupe das repetições do ChatGuru depende de datetime_post estável | `ia-atendimento/src/ia_atendimento/evento_mensagem.py:165` | A3.1 passa a medir e registrar: datetime_post de cada repetição do mesmo Post (igual ou diferente) e o timeout do ChatGuru. | A3.1 |
| G-0549 | conf. | costura | `perfil` do disparo não é definido no 04; rótulos da lista violam o tipo `Rotulo` | `ia-atendimento/src/ia_atendimento/tipos.py:89` | O 04 §2.5 passa a listar as chaves e formatos de `perfil` (o exemplo do 08: `banco`, `faixa_parcela`, `idade_min`) e o formato de `responsavel_antes`; | sem bloco na fonte |
| G-0551 | conf. | costura | ia-ui-fechar do 04 não cabe em POST candidatos | `ia-atendimento/src/ia_atendimento/api/anotacoes.py:45` | Conciliar 04 §2.6 com 08 §5.6: ou o pulo vai como `recusa` codificada (`pulado_<motivo>`, cabe em 40) sem `posicao`, ou a API ganha `motivo_pulo` e aceita `posicao` … | sem bloco na fonte |
| G-0553 | conf. | costura | SaidaT3/SaidaT1 sem campo para o que T7 e o resolver obsoleto precisam do 360 | `ia-atendimento/src/ia_atendimento/ferramentas/esquemas.py:5` | Em B5.2: acrescentar a `SaidaT3` os campos do lado do código (`tabela_identificador`, `coeficiente_financeiro`, `coef_valor`) e a `SaidaT1` o `vendedor_ator_id`, sem … | B5.2 |

#### Sem RS · ia-atendimento-b1-6a (2)

| Id | Estado | Tipo | Título | Onde (prova principal) | Correção em 1 linha | Bloco na correção |
|---|---|---|---|---|---|---|
| G-0454 | conf. | costura | T11 sem `args_hash`: colisão de `(rodada, seq)` é engolida como repetição | `ia-atendimento-b1-6a/src/ia_atendimento/ledger.py:112` | Exigir `args_hash` em todo `Pedido` de `efeito_irreversivel` (hash do `texto_id` mais o conteúdo renderizado), para que mensagem diferente na mesma chave levante … | B1.6b |
| G-0460 | conf. | codigo | Jobs iniciar e encerrar_por_chave viram no-op sem log | `ia-atendimento-b1-6a/src/ia_atendimento/jobs.py:173` | Uma linha de log (só ids e código) em cada retorno False; | sem bloco na fonte |

#### Sem RS · gl-gateway (2)

| Id | Estado | Tipo | Título | Onde (prova principal) | Correção em 1 linha | Bloco na correção |
|---|---|---|---|---|---|---|
| G-0361 | conf. | codigo | Boot com banco fora deixa cache vazio e responde 404 definitivo | `gl-gateway/app/rotas.py:208` | Distinguir cache nunca carregado de rota inexistente: responder 503 com Retry-After enquanto não houve carga bem-sucedida; | sem bloco na fonte |
| G-0544 | conf. | ausencia-de-controle | Balde por IP compartilhado entre ia-mensagem e rotas antigas; 429/424 sem reenvio | `gl-gateway/app/main.py:380` | Antes da sombra: medir rate_ip por minuto na metrica e alertar; | A3.1, B6.1b |

#### Sem RS · facta-on (4)

| Id | Estado | Tipo | Título | Onde (prova principal) | Correção em 1 linha | Bloco na correção |
|---|---|---|---|---|---|---|
| G-0341 | conf. | codigo | Retry de 401 da FACTA queima o token vivo (forcar=True) | `facta-on/app/facta_client.py:358` | Trocar o retry por token.invalidar(motivo, valor=<token que falhou>) seguido de obter() sem forçar; | sem bloco na fonte |
| G-0342 | conf. | ausencia-de-controle | Robô da esteira FACTA fora do throttle e do breaker; comentário diz o contrário | `facta-on/app/robo.py:197-199` | Passar as chamadas do robô pelo mesmo slot/breaker (ou com prioridade menor) e corrigir o comentário; | B5.4 |
| G-0494 | conf. | codigo | Primeira medida real deixa o portão vermelho por falso positivo | `facta-on/app/routers/online.py:3949` | Na colheita, omitir da medida (ou marcar `sem_pessoas: true`) a rota em que nenhum registro tem CPF; | sem bloco na fonte |
| G-0560 ¹ | conf. | costura | Identidade da IA no facta-on depende de o nginx não mandar X-Forwarded-For | `facta-on/app/security.py:131` | Escrever no contrato 05 §2 e na tabela do vhost: o `location /facta-online/…` do WG não envia `X-Forwarded-For` (ou a IA ganha service token), e 401/403 ⇒ «não sei». | B5.4 |

#### Sem RS · bancos-duble (1)

| Id | Estado | Tipo | Título | Onde (prova principal) | Correção em 1 linha | Bloco na correção |
|---|---|---|---|---|---|---|
| G-0495 | conf. | codigo | Classificador fail-open em erro:false e etapa_final desconhecida | `bancos-duble/catalogo/classificador.py:364` | Na etapa 3, exigir `codigo` para `sucesso`; | sem bloco na fonte |

#### Sem RS · kits, scripts e medições (7)

| Id | Estado | Tipo | Título | Onde (prova principal) | Correção em 1 linha | Bloco na correção |
|---|---|---|---|---|---|---|
| G-0104 | conf. | codigo | Camada B devolve 200 nao_autorizado para limite diario; facta-on devolve 503 | `scripts/stubs_b.py:96` | Em stubs_b.py acrescentar limite_consulta (503, Retry-After 3600) a HTTP_POR_RESULT e apontar dad-limite para ele (ERRO, via resposta_erro). | sem bloco na fonte |
| G-0357 | conf. | ausencia-de-controle | A2.6: leituras de 02/11 e 09/11 sem arquivo, critério P5 incoerente e condições humanas do portão passam com … | `kits/gateway/portao.sh:81-82` | Gravar as leituras de 02/11 e 09/11 (e a de hoje) em medicoes/ com df, pg_database_size e tamanho de execution_data; | sem bloco na fonte |
| G-0359 | conf. | kit | Kit S4 trata medição A2.7 de 30/10 como pré-condição corrente, sem portão de máquina | `kits/s4/README.md:13` | Pôr no início de s4-papeis.sh um bloco só leitura que aborte se last_failed_time > last_archived_time, se df < 40 GB ou conexões >= 60; | A2.7, A4.3 |
| G-0360 | conf. | ausencia-de-controle | A2.3: casamento de 100% circular e 1:N resolvido pelo job mais novo | `medicoes/A2-s2-medicoes-3010.md:37` | Antes de B6.2, medir (só contagem) quantos `link_chat` têm mais de um CPF e definir a regra de desempate ('mais recente', 'sem cpf_alterado' ou recusa); | B6.2 |
| G-0432 | conf. | ausencia-de-controle | Portão do catálogo: histórico só no check.sh local, sem conferência no CI | `scripts/check.sh:19` | Incluir `conferir_catalogo.py` no workflow (com `fetch-depth` suficiente para a base); | A4.6, B1.6 |
| G-0487 | conf. | ausencia-de-controle | Sem controle de deriva entre stubs da camada B e facta-on de main | `scripts/stubs_b.py:64-91` | Teste estático que leia online.py do FACTA_ON_REPO, extraia as chaves de _HTTP_POR_RESULT e falhe quando houver result sem stub ou sem dispensa explícita em lista. | sem bloco na fonte |
| G-0488 | conf. | ausencia-de-controle | conferir: duble nunca fica em aguardando depois da janela | `scripts/stubs_b.py:386-400` | Adicionar stub de prioridade maior que recuse desde fora de ISO-8601 com fuso com 400 e o mesmo corpo do real. | B5.4 |

#### Sem RS · contratos (9)

| Id | Estado | Tipo | Título | Onde (prova principal) | Correção em 1 linha | Bloco na correção |
|---|---|---|---|---|---|---|
| G-0069 | em parte | ausencia-de-controle | Levantamento não distingue Cliente360 antigo do novo | `contratos/03-cliente360-iskra.md:124` | Acrescentar ao levantamento e ao contrato 03 uma tabela 'qual base responde por quê' (gl360 novo, legado cliente_360, db360) com data de corte. | A3, B4 |
| G-0190 | em parte | ausencia-de-controle | Volta sem linha para contêiner novo que não sobe | `contratos/01-gl-gateway.md:321` | Acrescentar a linha (iv) à Volta: contêiner novo não sobe, com critério de decisão, comando exato (desfazer.sh --env + Redeploy) e tempo máximo de queda aceito antes de … | sem bloco na fonte |
| G-0199 | conf. | ausencia-de-controle | Perímetro do n8n: contêiner vizinho forja identidade | `contratos/04-n8n-braco-espelho.md:84` | Acrescentar ao S3 uma sonda a partir de outro contêiner da rede; | sem bloco na fonte |
| G-0218 | em parte | ausencia-de-controle | Tratamento de 403/404/409/422/5xx do 360 pelo orquestrador não definido no 03 | `contratos/03-cliente360-api.md` | Acrescentar tabela de erros do 360 (código -> ação do orquestrador: degradado, bloqueios, repasse, sem repetição em escrita) em §1 ou §10, ou apontar o contrato 08/B5.2 … | B5.2 |
| G-0227 | conf. | costura | Vigia e n8n do braço ausentes do 02 e do orçamento de vagas RPA | `contratos/02-chatguru-api.md` | Acrescentar ao 02 §1 as duas linhas (vigia, n8n braço) com rotas e frequência e reservar vagas RPA por consumidor, medido em A2.4/A3.3. | A2.4, A3.3 |
| G-0238 | conf. | costura | 422/400/403 do n8n chegam como 424 tratados como transitórios | `contratos/01-gl-gateway.md` | Na tabela de tradução do 01 §4.2 e no 08 §7.2/§7.3, separar o 424 por destino_status: 400/422 do destino ⇒ permanente (crítico imediato, sem repetição; | B1.6b |
| G-0240 | conf. | costura | Atendimento de teste exige linha no espelho, mas o 04 não descreve caminho de teste | `contratos/01-gl-gateway.md` | Acrescentar ao 04 uma seção «Ensaio em modo teste»: como o chat de `chats_teste` entra na lista (linha sintética de entrega/job ou fixture do kit que chama `reservar()` … | sem bloco na fonte |
| G-0550 | conf. | costura | 409 janela_24h e chave_reutilizada de POST /atendimentos sem tratamento no núcleo do n8n | `contratos/04-n8n-braco-espelho.md` | No 04 §2.5 passo 8: `janela_24h` ⇒ `cancelar`, pula (recusa `janela_24h`, levada em `recusa` ao `/candidatos`); | sem bloco na fonte |
| G-0563 | conf. | costura | Tabela de erros fechada do proxy não cobre códigos reais do PUT /config | `contratos/03-cliente360-api.md` | Completar a tabela do 03 §5.4 e o 07 §5.4: `pii_no_texto_livre` em `por` ⇒ erro nomeado «o seu login não é aceito pelo orquestrador; | B4.3 |

#### Sem RS · papel (ROT, estudos) (16)

| Id | Estado | Tipo | Título | Onde (prova principal) | Correção em 1 linha | Bloco na correção |
|---|---|---|---|---|---|---|
| G-0010 | em parte | costura | A4.2/A4.4 e consumidores da VPS caem antes de a VPS existir (limite 12/11 14:00) | `ROTEIRO-DE-ACAO.md` | Reagendar A4.1-A4.4 depois da entrega da VPS ou fixar data-limite de A1.5 em 09/11; | A1.5, A4.1, A4.2, A4.4 |
| G-0051 | em parte | ausencia-de-controle | Operador único por 8 dias sem substituto e também revisor | `ROTEIRO-DE-ACAO.md:25` | Nomear substituto com celular e treino de devolver-leads (ensaio com ele em 18/11) como critério de aceite do go/no-go; | sem bloco na fonte |
| G-0057 ¹ | em parte | ausencia-de-controle | Checkpoint 0 não mede r e 5 agentes sem evidência de RAM | `ROTEIRO-DE-ACAO.md:34` | Registrar horas reais desde ja (B1.1, B1.2, B1.3, B6.0), medir RAM do S3 com 5 agentes e antecipar o checkpoint para quando houver dado. | B1.1, B1.2, B1.3, B6.0 |
| G-0140 | conf. | costura | Chave Fireworks chega depois do deploy #8 | `ROTEIRO-DE-ACAO.md:487` | Acrescentar A1.4 (ou 'valor de enchimento ≥ 16 caracteres, trocado em 17/11') em A4.9; | A1.4, A4.9 |
| G-0144 | em parte | ausencia-de-controle | A2.12 fonte de domingo perecível sem registro | `ROTEIRO-DE-ACAO.md:612` | Ler (a) hoje e gravar em medicoes/ com rótulo; | B3.1 |
| G-0148 | conf. | ausencia-de-controle | A3.4 assume sem gate que chat sem CPF é recusado pelo zVuE | `ROTEIRO-DE-ACAO.md:625` | Subir a leitura do nó para o Aceite de A3.0 e para as dependências de A3.4. | A3.0, A3.4 |
| G-0149 | em parte | ausencia-de-controle | Alerta ntfy: sem prova de ausência de PII fora do Python e tópico ia-ack forjável | `ROTEIRO-DE-ACAO.md:731` | Pôr a lista de campos no Aceite de A4.7. | A4.7 |
| G-0153 | em parte | costura | A7.2 amarra aprovação das v1 ao fim de B8.2, mas B5.5 depende de A7.2 | `ROTEIRO-DE-ACAO.md:817` | Separar: hash dos TX travado após o lote 13/11 (APROVADOS-v1.md); | B5.5, B8.2 |
| G-0154 | conf. | ausencia-de-controle | A6.1 afirma kits versionados no repo; a main só tem chats-teste.sh | `ROTEIRO-DE-ACAO.md:779` | Dar push do kits/s4 e abrir PR; | A6.1 |
| G-0163 | conf. | kit | Volta do A4.6 diz ledger do kit, mas a 0005 não tem down | `ROTEIRO-DE-ACAO.md:868` | Trocar a célula por 'sem volta; | sem bloco na fonte |
| G-0168 | conf. | costura | Soma de dias e carga por agente: A4 com 17 d-agente | `ROTEIRO-DE-ACAO.md:1254` | Reescrever os cabeçalhos com duração líquida (já líquida do −1,0 e dos acréscimos) e marcar concluídas; | A4, B5.5, B5.6, B5.9 |
| G-0170 | em parte | ausencia-de-controle | Sem substituto nomeado para 8 dias seguidos de operação | `ROTEIRO-DE-ACAO.md:145` | Nomear o substituto na A1.7 antes do checkpoint de 11/11, incluí-lo no ensaio B de 19/11 e no ensaio a seco, e fixar no aceite como se conta um dia sem operador. | A1.7 |
| G-0309 | em parte | ausencia-de-controle | Situação sem cartão: cliente escreve com atendimento pausado à noite | `L-situacoes.md:416-418` | Criar o cartão (I-38) "mensagem do cliente em pausado fora do horário": registrar contagem por noite e id curto, linha na ficha das 20:15 e na de 08:15, e decisão do … | sem bloco na fonte |
| G-0371 ¹ | em parte | costura | Cenário C deslocou riscos de prazo sem resolvê-los | `ROTEIRO-DE-ACAO.md` | Refazer a Parte C a partir do que o dono confirmar que aconteceu em 09–10/11, com no máximo dois toques dele por dia e ordem explícita de prioridade (gateway e cookie … | A3 |
| G-0381 ¹ | conf. | costura | Substitutos da colheita real dependem de tap ausente da main | `ROTEIRO-DE-ACAO.md` | Escolher uma das duas e escrever no roteiro: (a) rodar a colheita por `!` antes do merge do #5, com registro; | B10.1, B2.2 |
| G-0388 ¹ | conf. | ausencia-de-controle | D-09: proteção da main só «pendente», prazo 10/11 12:00 | `ROTEIRO-DE-ACAO.md:45` | Conferir o ruleset dos três repositórios (PR obrigatório, vale para admin, sem force-push) antes de 12/11 e registrar o resultado em ROT:45 e E-16. | sem bloco na fonte |

### MÉDIOS da Fase 4 (F4-*, R2-*): RS não atribuída na fonte

Os consolidados da Fase 4 não trazem coluna RS. Estes 33 MÉDIOS ficam aqui com «RS: não atribuída» para quem executa. A correção é a do verificador, encurtada. Fontes: `fase4/consolidado-f4.md:30-47` e `fase4/consolidado-r2.md:14-28`. Caminhos de código relativos a `src/`.

#### ia-atendimento: máscara, contexto e prompt (R2)

| Id | Título | Onde | Correção em 1 linha |
|---|---|---|---|
| R2-002 | Formas comuns de data/hora ainda viram [NUMERO] na gravação | `ia-atendimento/src/ia_atendimento/mascara.py:47,135-149`; `conversa.py:128` | Isentar data+hora nas duas ordens, com hífen, com ano e listas hh:mm; casos no corpus |
| R2-004 | «[NUMERO:2] = prazo» e `_PRAZO` amplo empurram hora nua para prazo | `ia-atendimento/src/ia_atendimento/modulos_fase.py:35`; `protecao.py:63,71-78` | Marcar quantidade com contexto ([QTD]) ou restringir a prazo pedido; tirar a leitura «2 dígitos = prazo» do SISTEMA |
| R2-005 | Parte do nome que é palavra comum apaga a palavra | `ia-atendimento/src/ia_atendimento/mascara.py:163-189`; `protecao.py:137,141` | Não mascarar parte isolada de lista de palavras comuns, ou só quando capitalizada; testes |
| R2-015 | Anotação do operador grava nome e texto livre em claro por 365 d | `ia-atendimento/src/ia_atendimento/api/anotacoes.py:83-85` → `passos.py:273-279,410` | Recusar anotação sem nomes conhecidos (fail-closed), ou gravar cifrada com 14 d, ou lista fechada |
| R2-021 | POST /sessoes/{id}/candidatos recusa (422) o corpo dos pulados do 04 §2.6 | `ia-atendimento/src/ia_atendimento/api/anotacoes.py:44-62` | Fechar num contrato só e teste de contrato com o corpo do 04 |
| R2-022 | `texto_mensagem` acima de 4000 caracteres dá 422; contrato manda truncar | `ia-atendimento/src/ia_atendimento/api/eventos.py:46` | Truncar em 4000 antes da validação, contar só o tamanho; inverter `test_contrato_api.py:537` |

#### ia-atendimento: gateway de ferramentas e T7/T8 (R2)

| Id | Título | Onde | Correção em 1 linha |
|---|---|---|---|
| R2-008 | T8 (até 1500 s) segura as 2 vagas do limitador da FACTA | `ia-atendimento/src/ia_atendimento/ferramentas/catalogo.py:177-181`; `gateway.py:61,334-340` | Serviço próprio para a T8 ou polling por job em chamadas curtas (mesmo tema de G-0559) |
| R2-009 | `SaidaT8.estado` não comporta os vereditos do 05 §2.1 B | `ia-atendimento/src/ia_atendimento/ferramentas/esquemas.py:170-172` | Ampliar o Literal com os vereditos do contrato e novo número em `catalogo_versoes.json` (mesmo tema de G-0558) |
| R2-010 | Timeout da T8 vira BANCO_INDISPONIVEL (repetível) | `ia-atendimento/src/ia_atendimento/ferramentas/gateway.py:343-344` | Mapear o timeout da T8 para INDETERMINADO com repasse e nota |
| R2-011 | `posse_real` sem produtor na main; sob parada dura em dublê o atendimento real vai à fixture | `ia-atendimento/src/ia_atendimento/ferramentas/projecao.py:59`; `gateway.py:78`; `modo.py:170-174` | Ligar `posse_real` ao predicado do ledger antes de montar Deps; falhar fechado se não puder ler |
| R2-012 | T7 com posse real sob parada dura cai no simulador | `ia-atendimento/src/ia_atendimento/ferramentas/modo.py:157-164` | `efeito_irreversivel` com posse real em sombra/dublê ⇒ MODO_SOMENTE_LEITURA, sem simulador |
| R2-013 | CancelledError após o disparo da T7 não vira INDETERMINADO | `ia-atendimento/src/ia_atendimento/ferramentas/gateway.py:338-346,233` | Capturar BaseException quando despachado e irreversível; registrar INDETERMINADO e relançar (parte de G-0087) |
| R2-017 | Mover `despachado=True` antes da leitura do CPF não derruba teste | `ia-atendimento/src/ia_atendimento/ferramentas/gateway.py:338-346`; `tests/test_ferramentas_gateway_revisao.py:169-180` | Teste: T7 com leitor de CPF lento ou que falha ⇒ nunca INDETERMINADO e `t7.chamadas == []` |
| R2-018 | Pré-condição que devolve verdadeiro não-`True` não é testada | `ia-atendimento/src/ia_atendimento/ferramentas/gateway.py:431-439`; `tests/apoio_gateway.py:103-106` | Teste parametrizado com `(False,)`, `"false"`, `1`, `object()` e corrotina ⇒ PRECONDICAO_FALHOU |

#### ia-atendimento-b1-6a: ledger (R2, F4)

| Id | Título | Onde | Correção em 1 linha |
|---|---|---|---|
| R2-016 | Ledger grava `Desfecho.ref_externa` sem varredura de PII; CheckViolation ecoa a linha | `ia-atendimento-b1-6a/src/ia_atendimento/ledger.py:164-171,343-354,467-480`; `migrations/0001_esquema.up.sql:215` | Validar Desfecho na fronteira (forma do CHECK + `_tem_pii`); converter IntegrityError sem DETAIL |
| F4-026 | Merge junta duas `modo_efetivo` com regras divergentes | ramo `ledger.py:74,105-109` × main `ferramentas/modo.py:36,49-52` | Ledger usa `ferramentas.modo.modo_efetivo` (fail-closed) e teste cruzado ledger × gateway |
| F4-027 | OPERACAO do ramo sem runbook da B1.6a (não existe: critério de aceite) | ramo `docs/OPERACAO.md`; `docs/DECISOES-B1.6a-0411.md:14,31` | Seção: achar linhas `indeterminado`, quem decide, `expirar_parados`, 503 por gasto |

#### ia-atendimento: extrator de agenda (F4)

| Id | Título | Onde | Correção em 1 linha |
|---|---|---|---|
| F4-010 | `_R_HEDGE` fechado e com erro em «cerca das» | `ia-atendimento/src/ia_atendimento/agenda_extrator.py:260-263` | `cerca\s+d[aeo]s?`; incluir «e pouco», «em diante», «no máximo»; teste hedge × forma |
| F4-011 | «15h/16h» perde a segunda hora e sai ALTA | `ia-atendimento/src/ia_atendimento/agenda_extrator.py:273,395-406` | Tratar `/`, `-`, vírgula e `;` como conector em `_lista_incompleta`, ou recusar |
| F4-013 | «em 2h» lido como 14:00; «daqui 2h» como duração | `ia-atendimento/src/ia_atendimento/agenda_extrator.py:243-245,375-376` | «em N h» com N ≤ 7 e sem «às» ⇒ recusar `duracao_ambigua` |
| F4-014 | «quinze para as 4» gera 16:00 | `ia-atendimento/src/ia_atendimento/agenda_extrator.py:238` | Reconhecer «X para as N» ⇒ (N-1):(60-X), ou recusar `hora_incompleta` |

#### ia-atendimento: corpus e hold-out (F4)

| Id | Título | Onde | Correção em 1 linha |
|---|---|---|---|
| F4-001 | SIM do corpus aceita 4 formas que H manda para TX-36 | `ia-atendimento/src/ia_atendimento/corpus/vocabulario.py:298` | SIMS igual à lista de H, ou decisão do dono propagada a H e ao plano 01 |
| F4-002 | Variações de redação não são obrigadas a dizer o mesmo que o texto-base | `ia-atendimento/src/ia_atendimento/corpus/regras/pii.py:31`; `regras/gabarito.py:164-165` | Toda redação com a mesma classe de SIM e os mesmos tipos de `pii_digitada` |
| F4-004 | Hold-out sem P-M e com 4 de 12 vagas em personas sem diálogo | `ia-atendimento/src/ia_atendimento/corpus/semente.py:45-48` | Sortear o hold-out entre personas com diálogo, P-M incluídas |
| F4-005 | Hold-out v3 do extrator ensinou correções e segue no portão de 95 % | `ia-atendimento/tests/corpus/gerar_agenda_frases.py:436-438` | Mover v3 para regressão e cobrar 95 % só sobre v1+v2 |

#### Esteira, kits e consultas (F4)

| Id | Título | Onde | Correção em 1 linha |
|---|---|---|---|
| F4-018 | Conflito de pyproject/uv.lock no merge da esteira apaga dependências | `pyproject.toml`, `uv.lock` (main × esteira) | Manter a main e acrescentar só `pyyaml==6.0.3` ao grupo dev; regerar `uv.lock` |
| F4-023 | A4.3a sem comando para o `pg_dump -s` do aceite (não existe: critério de aceite) | `kits/s4/provar.sh:65`; `ROT:705-706` | `provar.sh --so-s4` ou o comando literal no roteiro |
| F4-030 | `q.sh`: read-only só por set de sessão como superusuário | `/opt/claude/docs/planejamento-ia/consultas/conversao-2910/q.sh:3` | Papel de leitura dedicado com `default_transaction_read_only` no papel |
| F4-031 | Medição de conversão expõe nome e desempenho de consultor | `consultas/conversao-2910/a2.sql:1,9-10`; `a5.sql:15` | Sair por `ator_id` e exigir `having count(*) >= 5` |
| F4-033 | `anon --k` sem piso desliga o k-anonimato | `bancos-duble/anonimizador/duble_anon/cli.py:129-143,162` | `max(args.k, K_PADRAO)` fora dos testes, ou recusar k < 5 sem flag de teste |

#### Processo da revisão (F4)

F4-021, F4-022 e F4-037 estão no §6.4, com a emenda proposta e a prova de feito.

---

## 6. Achados de papel, processo e estado, e peças que não existem

Esta seção cobre 86 achados vivos de papel, processo e estado: 83 da Fase 3 (23 ALTO, 60 MÉDIO) e 3 MÉDIO da Fase 4. Os 2 ALTO de processo da Fase 4 (F4-035, F4-036) estão no §5. Cobre também 100 peças que não existem: 98 da Fase 3 (21 ALTO, 50 MÉDIO, 27 BAIXO) e 2 da Fase 4 (MÉDIO).

### 6.0 Como ler esta seção

- **Fontes.** Fase 3: `fase3/consolidado.json` e `fase3/grupos/G-nnnn.json`. Fase 4: `fase4/consolidado-f4.json`. A rodada 2 (`consolidado-r2.json`) não tem achado de papel nem «não existe»: os 23 R2 são de código e ficam fora desta seção.
- **Filtro.** Papel = `tipo` igual a `papel` ou `estado-desatualizado`, `sev` ALTO ou MÉDIO, `estado` igual a «confirmado» ou «confirmado em parte». «Não existe» = `estado` igual a «não existe: critério de aceite». G-0616 («Spikes e validações do dublê FACTA só planejados») saiu: a peça existe (refutado).
- **Atalhos.** `ROT` = `/opt/claude/docs/planejamento-ia/ROTEIRO-DE-ACAO.md` (v3.3, mtime 04/11 16:27). `contratos/NN` = `/opt/claude/docs/planejamento-ia/contratos/NN-*.md` (vigentes, sem sufixo). `src/` = `/home/danilo/ia-revisao-0911/src/` (exportação da Fase 0). `estudos/` = `/opt/claude/docs/planejamento-ia/estudos/`.
- **Linhas.** Quando o verificador corrigiu a linha do leitor, vale a do verificador (ex.: G-0002 linha 166; G-0004 memória linha 11).
- **Emendas.** São propostas. Nenhuma foi aplicada. A regra «contratos não se editam nesta rodada» foi riscada em 04/11, e as emendas daquele dia foram aplicadas (01 v2.5, 03 v2.2, 04 v2.2, 07 v2.2, 08 v2.4; `ROT:106`). O 05 e o regime de permissão seguem pendentes (`ROT:1582`). Pelo PLANO §6, cada correção nova exige «sim» do dono por item.
- **Coluna «Parcial».** «sim» quando o verificador confirmou só em parte. A emenda já cobre só o núcleo que ficou de pé.
- **Para a IA executora.** Cada emenda diz arquivo, seção e texto novo. Rode o critério da coluna «Prova de feito» antes de marcar o item fechado.

### 6.1 Cinco padrões por trás dos 86 achados

| # | Padrão | Ids | Raiz |
|---|---|---|---|
| P1 | Roteiro parado em 04/11 16:27. Painel, Parte E e Parte F não registram 05/11 a 10/11. | G-0006, G-0007, G-0027, G-0029, G-0076, G-0079, G-0152, G-0016 | Nenhuma sessão atualizou o Painel. RETOMAR-0911 também é de 04/11 19:30 (nota de G-0007). |
| P2 | Documento superado sem tarja. Estudos e planos seguem com texto que o roteiro já trocou. | G-0040, G-0050, G-0054, G-0059, G-0060, G-0062, G-0063, G-0065, G-0156, G-0067, F4-021 | A regra «datas antigas valem pelo de-para» (ROT:165-166) não cobre conteúdo. Ninguém marcou os documentos. |
| P3 | Regra dupla dentro do próprio roteiro. As duas versões têm rótulo v3.3. | G-0003, G-0009, G-0017, G-0024, G-0080, G-0382, G-0387, G-0172, G-0174, G-0175, G-0176 | Emendas v3.3 entraram como adendo, sem riscar a frase antiga. |
| P4 | Contrato vigente diz uma coisa e o código faz outra. | G-0120, G-0400, G-0531, G-0035/G-0554, G-0418, G-0098, G-0100, G-0374 | O contrato mudou depois do código, ou o OPERACAO ficou na fundação. |
| P5 | Ramo, kit ou esteira declarado pronto e não está na main nem provado. | G-0016, G-0076, G-0094, G-0096, G-0152, G-0186, G-0461, G-0515, G-0519, F4-022, F4-035 | Ramos sem push (`kits/s4`, `feat/esteira`) e ensaios de outros SHAs. |

### 6.2 Papel e estado: ALTO (23)

| Id | Tipo | Parcial | Contradição | Trecho A | Trecho B | Emenda proposta (arquivo · seção · texto novo) | Prova de feito |
|---|---|---|---|---|---|---|---|
| G-0004 (RS-27) | estado | não | A regra 5 diz que o web não faz deploy no merge. A memória diz que faz desde 04/11. | ROT:45 «**Web não faz deploy no merge** (`subir-web-prod.sh`)» | memory/web-merge-auto-deploy.md:11 «o merge na main do web agora vai sozinho para produção, pelo timer `web-auto-deploy` na S3» | ROT · §0.3 regra 5 · «O web **faz** deploy no merge desde 04/11 (timer `web-auto-deploy` na S3). O PR #635 só se mescla na janela do #7 (17/11) e com a flag off.» Trocar também ROT:160, 429, 863, 964. | `grep -n "web-auto-deploy" ROT` acha a regra 5. Estado vivo do timer: **não verificado** nesta revisão (sonda só-leitura). |
| G-0005 (RS-06, RS-14) | papel | não | D-32 exige provar eliminação em 14 d do texto mascarado. A regra 3 diz que ele sobrevive nos fulls. | ROT:43 «provar que o texto mascarado no Phoenix e nos fulls/backups é eliminado em 14 d» | ROT:43 «o texto mascarado do Phoenix sobrevive nos fulls pelo aceite do dono de 30/10»; ROT:231 «não há como tirá-lo sem stanza própria» | ROT · A4.5 e A4.8, linha «Aceite» · «Via de D-32: [stanza própria do `ia_obs` \| retenção dos fulls ≤ 14 d \| aceite escrito do dono que revoga D-32 para os fulls]. Prova: [comando].» Apagar a frase concorrente de ROT:231. **Decisão do dono antes de 18/11 (G2).** | ROT:43 e ROT:231 dizem a mesma via; aceite de A4.5/A4.8 traz o comando de prova. |
| G-0009 | papel | não | D-01 diz «sem padrão» para o go sem medição. A2.9, B8.2 e B10.1 aceitam «custo/latência não medidos». | ROT:139 «sem padrão para A2.9, B8.2 e go; B1.6 segue com `FunctionModel`» | ROT:599 «o go/no-go registra «custo/latência não medidos» (v3.3)»; ROT:1123 «só I1–I9 com `ProvedorFalso`» | ROT · D-01 coluna «Se não vier», A1.4 (ROT:289), A2.9, B8.2, B10.1 · uma frase igual nos cinco: «Sem chave até 17/11 (A2.9a, ROT:1238): go só com aceite escrito do dono de custo e latência não medidos; sem o aceite, no-go.» Trocar «09/11» por «17/11». **Decisão do dono.** | `grep -n "custo/latência não medidos" ROT` devolve só linhas com a mesma regra. |
| G-0011 (RS-08) | papel | não | O bloco de A4.6 grava o ledger fora da transação da migração. O README exige a mesma transação. | ROT:722 «SET ROLE ia_owner; INSERT INTO ia.migracao (migracao_id,checksum) VALUES ('0001_esquema'» (segundo `psql -c`, sem `-1`) | src/ia-atendimento/migrations/README.md:25 «Cada arquivo e a linha do ledger vão na mesma transação» | ROT · A4.6 · apagar o bloco ROT:718-727 e escrever: «Aplicar 0001 a 0005 só por `kits/s4/migrar.sh` (ver G-0012). Cada migração e o INSERT do ledger vão no mesmo `psql -1`, com `RESET ROLE` dentro (migrations/README.md:25-26, OPERACAO §3).» | `grep -n "INSERT INTO ia.migracao" ROT` vazio; A4.6 aponta para o kit. |
| G-0016 (RG-067; RS-01, 07, 10, 18, 25) | estado | não | A6.6b venceu em 08/11 sem entrega. O worker do compose aponta `ia_atendimento.fila.app`, que não existe: o app da fila vem de função (`fila.py:79-83`, `criar_app`). | ROT:807 «Worker no compose e push da esteira (v3.3) · Claude · 0,5 d · **até 08/11**» | src/ia-atendimento-esteira/docker-compose.yml:96 `"procrastinate", "--app=ia_atendimento.fila.app", "worker"`; OPERACAO.md:203 descreve esse comando como o antigo | ROT · Painel (l.348) e A6.6b · «A6.6b vencida em 08/11. Nova data: [dono]. Aceite: compose rebaseado sobre a main sobe o worker com o módulo da main; teste do `command`; push e PR.» A6.6 item (1): «Coolify lê o compose e puxa a imagem.» Ver F4-016 (compose com `api:app` inexistente). | `docker compose config` no ramo rebaseado mostra o módulo da main; teste do command verde. |
| G-0017 (RS-15, RS-27) | papel | não | B3.1 e B3.2 dão dia e hora do merge do facta-on diferentes do mapa de deploys. | ROT:947 «hora **12:30–14:00**; merge do PR de A6.4»; ROT:952 «**depois das 20:30** do dia 10/11» | ROT:858 «**junto do #5: 12/11, depois das 20:30**, flag própria; nunca no dia do gateway (X2)» | ROT · corpos de B3.1 e B3.2 · «Um só merge (PR de A6.4 + janela de B3.2) em 12/11 depois das 20:30 (mapa #5), flag própria. DDL antes do merge, na mesma noite. O portão de disco PD-3 vale.» Mesma data em contratos/05 §2.6, §4, §5. | `grep -n "10/11" ROT` dentro de B3.x vazio; contratos/05 com 12/11. |
| G-0019 | estado | não | A cadeia B1.4 > B1.6 > B1.7 > v0.3.0 > deploy #8 não fecha: B1.4 só fecha com a chave (até 17/11). | ROT:901 «Depende de: B1.4, B1.5, A3.3»; ROT:910 «Depende de: B1.6» | ROT:1238 «B1.4 só fecha com a A2.9a, no dia da chave (até 17/11)» | ROT · B1.7 · «A tag v0.3.0 sai com B1.4 em aceite provisório (`ProvedorFalso`). A2.9a é portão separado e não segura a tag.» B1.6b: dono e branch nomeados. | B1.7 cita «aceite provisório»; `git ls-remote` mostra a branch da B1.6b. |
| G-0022 (RG-007; RS-11, RS-22) | papel | não | As falhas provocadas de 24/11 caem dentro da sombra (23/11 a 25/11), onde nada sai. | ROT:1142 «Falhas provocadas em 24/11 depois das 15:00 (com `bloqueio_entrada`)» e «sombra de **23/11 08:00 a 25/11 12:00**» | ROT:1149 «com `config.modo=sombra` nenhum chat de teste envia nem digita no dublê» | ROT · B9.3 · «K-E1, K-E2, K-E10 e K-E19 rodam no ensaio B de 19/11, em modo real com chat de teste. Em 24/11 só rodam falhas que funcionam sob `modo=sombra`. Cada linha de falha diz o `config.modo` que vale.» | Tabela de B9.3 com coluna «modo» preenchida em toda linha. |
| G-0031 | papel | não | `prazo_ate` não é recalculado em `retomou`. Lead retomado volta a `aberto` vencido e a R-b o devolve em 60 s. | contratos/04:215 «least(disparado_em+7h, 20:15 BRT do dia)»; 04:355 «`pausado → aberto`, `retoma_em = NULL`» | contratos/04:378 «**R-b** `aberto` com `agora > prazo_ate`» | contratos/04 · `aplicar_evento`, transição `retomou` · «Em `retomou`, `prazo_ate` = fórmula do §4.6 calculada a partir de `now()`.» §9.3: novo caso de teste SQL. RS-25: nota da exceção. | Teste SQL «retomado às 09:30 não é devolvido pela R-b» verde. |
| G-0037 (RS-32) | papel | não | O 02 manda `Canal.restaurar` escrever a delegação. O 08 delega a devolução pela rota. Ficam dois escritores. | contratos/02 §3 «POST …/chatbot?ligar=true + PUT …/delegacao com o consultor_antes» | contratos/08 «rota: POST ia-repasse (protocolo 01 §4.2) com idempotency_key=repasse:{atendimento_id}» | contratos/02 · §3 · «`Canal.restaurar` só religa o chatbot ao `chatbot_antes`. Não escreve delegação. A devolução ao consultor é só da rota `ia-repasse` (01 §4.2).» Alinhar 08 (linha Assumir/Canal.restaurar) e ROT B6.8. | `test_restaurar_nao_escreve_delegacao` verde. |
| G-0043 | papel | não | Ajuste de valor ou seguro só é reconfirmado depois da proposta criada. | estudos/semana-1/f-catalogo-ferramentas.md «se ajuste_centavos/seguro mudar valor ou parcela, nova confirmação antes de dizer «feito»» | ROT:992 repete a regra; nenhum documento traz tolerância nem cancelamento (nota do verificador) | ROT · B5.4 e contratos/05 · «Tolerância de ajuste: [valor do dono] em centavos e no seguro, dentro do texto confirmado e do hash. Acima dela, a T7 não fala ao cliente e abre repasse com nota. Proposta recusada: [caminho de cancelamento].» **Decisão do dono.** | Teste «ajuste acima da tolerância ⇒ repasse, nenhuma mensagem» verde. |
| G-0047 (RS-21) | papel | não | A máscara não cobre o que o estudo H proíbe no banco e no prompt. | estudos/semana-1/h-roteiro-conversa-memoria.md:157 «conta/agência/PIX, matrícula, empregador, margem, data de nascimento, nome da mãe» | src/ia-atendimento/src/ia_atendimento/mascara.py:13 e :44 isentam dd/mm/aaaa; :140 deixa passar menos de 8 dígitos | ROT · B5.1 e matriz RS-21 · uma de duas: «Limite aceito pelo dono em [data]: nascimento, agência, conta e nome passam pela máscara» ou «máscara por campo coletado (conta, agência, endereço, nascimento) aplicada ao histórico, também fora da E5». **Decisão do dono.** | Teste com agência de 4 e conta de 6 dígitos no histórico: nada chega ao prompt, ou linha de aceite na matriz. |
| G-0050 (RS-25) | estado | não | O checklist de J põe a chave em `off` às 20:15. RS-25 e o código só gravam `bloqueio_entrada`. | estudos/semana-1/j-operacao-piloto.md:65 «Chave: fica ligada até 20:15, depois o job a põe em `off`» | ROT:1178 «timer grava `bloqueio_entrada=true` (a chave `ia_ativa` segue ligada e `pausado` dorme)» | j-operacao-piloto.md · §1.3 itens 1 e 6 (e l.71, l.232) · «Às 20:15 o timer grava `bloqueio_entrada=true`. A chave `ia_ativa` segue ligada. `pausado` não conta como aberto. O 07:45 grava `bloqueio_entrada=false`.» Ou tarja «superado por ROT B11.2». | `grep -n "em .off." j-operacao-piloto.md` vazio ou com tarja. |
| G-0054 | estado | não | M e L seguem com janela seg–sáb e TX-M03 «segunda a sábado», superados pelo domingo (D-18). | estudos/semana-1/m-agendar-assinatura.md §2.4 «seg–sáb, **08:30–19:00**»; TX-M03 «Eu atendo de segunda a sábado, das 8h30 às 19h.» | ROT:813 manda tirar «segunda a sábado» (D-18 vence RG-023); ROT:1008 janela 08:30–19:00 todos os dias | m-agendar-assinatura.md §2.4, TX-M03 e l-motor-qualidade.md G3 · tarja: «Superado por D-18 (ROT:813, B5.7d). A janela vem de `janela_mensagem.dias`; TX-M03 é montado a partir de `janela_vendedores`.» | Tarja presente nos três pontos. |
| G-0062 (RS-03) | papel | não | O plano mestre contradiz cinco decisões de produto da v3.3 e não diz que cede. | planos/2026-10-29-00-plano-mestre.md «lido de `GET /pessoas/{id}`»; «só dentro de 08–20 seg–sáb» | ROT §0.5b «Sem `ficha:ler`, `pessoa:dossie` nem `GET /pessoas/{id}`» (D-29); «Nenhuma mensagem ao cliente fora de 08–20, todos os dias» | plano-mestre · topo · «Rev. v3.3: este plano cede ao ROTEIRO v3.3 e aos contratos sem sufixo. Pontos superados: l.58, l.84, l.86, bloco 02/Lista 3, foco 8, bloco 05 (D-29, D-30, D-15, D-18).» | Tarja na l.1-5 do mestre. |
| G-0063 (RG-003; RS-09, RS-11) | papel | não | O sp01 não tem nota de precedência. Pontos de RG-003/013 seguem vigentes nele. | planos/2026-10-29-01-orquestrador-nucleo.md:200 «turnos_max=30»; :285 «todos os campos menos chat_number» | contratos/08:109 «estreito: só a identidade do episódio, não «tudo menos 4» (sp01 T3)» | sp01 · cabeçalho · «O contrato 08 v2.4 e o ROT B1.6 prevalecem sobre este plano.» Tasks 3, 5, 7, 8: fingerprint estreito, `turnos_max=24`, gasto por `passo.custo_brl`, 200 descartado/conflito, T4 fora do MVP. Fecha também G-0065 e G-0156. | `grep -n prevalece planos/2026-10-29-01-*.md` acha a nota. |
| G-0074 (RG-011; RS-11) | papel | não | A tabela única de `location` do vhost WG no 02 §2 não foi escrita. | contratos/02 §2 `location / { return 403 ... }` e `location = /gateway/ia-repasse { ... }` (esboço) | ROT (B6.0) «Spec = tabela única do 02 §2 (+ `/facta-online/proposta/conferir`, `…/por-cpf`, `/ia/batimento.json`» | contratos/02 · §2 · tabela fechada com: `location = /ia/batimento.json` (GET, `allow 10.90.0.5`), `/facta-online/proposta/conferir`, `/facta-online/proposta/por-cpf`, porta 8118, bloco completo de `/gateway/ia-repasse`, `location / → 403`. Kit A4.4 «Conferir»: 200 com JSON v2. | `curl` da VPS a `/ia/batimento.json` = 200; a rota fora da tabela = 403. |
| G-0075 (RG-023) | estado | não | O arquivo de textos para aprovação ainda é a v1 de 30/10, com NT-01, TX-M03, TX-42 e lotes errados. | textos/TEXTOS-PARA-APROVACAO.md:3 «Versão 1, gerada em 30/10/2026»; :12 prazo único 11/11 «em lote» | ROT:813 «reemissão em 05/11, pendente; aprovação em dois lotes» | TEXTOS-PARA-APROVACAO.md · reemitir v2 · TX-42 incluído; NT-01 25 min; SIMS; TX-02/28/24 inativos; sem «seg–sáb»; lote 11/11 e lote 13/11. ROT Painel A7.1: responsável e data. | Linha 3 do arquivo diz «Versão 2»; `grep TX-42` acha. |
| G-0076 (RG-045) | estado | não | O PR #13 (B1.6a) está CONFLICTING com a main. B1.6a, B1.8 e B5.1 nunca passaram juntas pelo portão. | fase0/MANIFESTO.md:92 (PR #13 `mergeable=CONFLICTING`) | ROT:361-362 dá B1.6 «não iniciada; construção local desde 05/11» | ROT · Painel B1.6 · «B1.6a = PR #13, CONFLICTING com a main 9a4baca; rebase pendente. B1.6b sem branch.» Refazer a data da B1.7. Ver G-0461 (revisão r2). | `gh pr view 13 --json mergeable` = MERGEABLE e portão verde no commit rebaseado. |
| G-0079 (RS-08) | estado | não | A decisão delegada de 10/11 (degrau de 1 dia, piloto 27–30/11) não está no roteiro. | fase0/decisoes-delegadas.md:27 «go/no-go **26/11 12:00**; piloto **27–30/11**» | ROT:1164 «B10.1 ... **25/11 17:00**» | ROT · B8.2, B9.1, B9.3, B10.1, B11.1, B11.2, B12.1 · reescrever num só passe se o dono aceitar o degrau, com rampa de 4 dias (ver G-0172). Se derrubar, marcar a decisão delegada como sem efeito. **Decisão do dono antes do checkpoint de 11/11.** | ROT e decisoes-delegadas.md dão a mesma data de go/no-go. |
| G-0094 (RS-18) | estado | não | O Dockerfile da esteira não constrói a main: faltam `migrations/` e `fixtures/`. | src/ia-atendimento-esteira/Dockerfile:26 e :28 (copia só pyproject, uv.lock, README, src); .dockerignore:26 exclui migrations | src/ia-atendimento/pyproject.toml:46 `force-include` de migrations e fixtures | Dockerfile da esteira · no rebase · tirar `migrations` do `.dockerignore`; `COPY migrations/ ./migrations/` e `COPY fixtures/ ./fixtures/` antes do segundo `uv sync`. ROT A6.6b: passo de build. | `docker build` da main rebaseada e `docker run ... python -c` lista `ia_atendimento/migrations`. |
| G-0096 (RS-27) | estado | não | O portão de dia de piloto usa as datas antigas (23–28/11). 29/11 e 30/11 ficam fora da trava. | src/ia-atendimento-esteira/config/dias-piloto.txt:3 «Piloto real 23–28/11/2026» | ROT linhas 1, 3, 25, 204, 410: piloto 26–30/11 | dias-piloto.txt · lista 26–30/11 (e, se o dono decidir, 19/11, 20–23/11, 23–25/11). `deploy-vps.sh`: falha fechado com arquivo ausente ou vazio; `DEPLOY_AGORA` só com variável de teste. DEPLOY.md §6: congelamento 18/11. | Teste: `deploy-vps.sh --executar` em 29/11 com relógio falso é recusado. |
| G-0127 (RG-011; RS-10) | papel | não | A rota da T7 (`/proposta/formalizar`) não está no vhost WG nem no contrato 05. | ROT (B6.0) «Spec = tabela única do 02 §2 (+ `/facta-online/proposta/conferir`, `…/por-cpf`, ...)» | contratos/05 se intitula «(T7 e T8)», mas só especifica `conferir` e `por-cpf` (nota do verificador) | contratos/05 · nova seção T7 · rota, corpo (B5.4/D-29), tabela resposta → classe ancorada em `etapa3_iniciada`/`request_possivelmente_enviado` e 424, timeout. contratos/02 §2: `POST /facta-online/proposta/formalizar` e a rota de simulação do T5. | `grep -n formalizar contratos/05 contratos/02` acha as duas. |

### 6.3 Papel e estado: MÉDIO (60)

Agrupados por documento a emendar. Ids irmãos ficam na mesma linha quando a emenda é uma só.

#### 6.3a ROTEIRO-DE-ACAO.md

| Id | Tipo | Parcial | Contradição | Trecho A | Trecho B | Emenda proposta (seção · texto novo) |
|---|---|---|---|---|---|---|
| G-0002 | papel | sim | Três frases de precedência sem uma regra única. O verificador achou só falta de clareza. | ROT:10 «Em conflito entre documentos vale: este roteiro (depois de aprovado)» | ROT:4 «o arquivo de contrato sem sufixo volta a prevalecer sobre o roteiro, sem exceção»; ROT:166 de-para de datas | Capa, l.10 · «Conteúdo: contrato sem sufixo › roteiro › mestre › MON › estudos › REV › memória. Datas: o de-para do §0.5c vale sobre qualquer data de contrato ou estudo.» |
| G-0003 (RG-009) | papel | sim | Devolução sem venda: rodízio e «mesmo consultor» na mesma célula. | ROT:116 «sem venda, ele volta ao **mesmo consultor** (`indicado`, `consultor_antes`)» | ROT:239 «sem venda, o repasse vai ao **rodízio** (`zVuE` modo `fila`)» | ROT:116, 239, 388 · riscar a frase da manhã. Deixar só E-24: «Sem venda volta ao `consultor_antes`. Rodízio só com `consultor_antes` nulo.» Corrigir ROT:1063 («nulo» não é o fluxo principal no piloto). |
| G-0006 | estado | não | O Painel dá como não iniciadas etapas que estão na main. | ROT:363, 364, 373 (B1.8, B2.1, B5.1 «não iniciada») | src/ia-atendimento/migrations/0005_domingo_por_config.up.sql:1; main ia-atendimento 9a4baca, bancos-duble ca3ed2c | Painel · linhas B1.6 (a/b), B1.8, B2.1, B5.1, B5.7d, B8.1c, B7.1, A6.6b com data e SHA na coluna Prova. PD-1: passo «conferir o Painel contra `git ls-remote` no início da sessão». |
| G-0007 | estado | não | Atos de 09/11 e 10/11 seguem como futuros, sem marca de feito. | ROT:285 «pendente do dono: 09/11, no pedido único (D-03)»; ROT:321, 324 (A3.8 09/11 12:30, A4.3a 09/11 13:15) | PLANO-REVISAO-0911.md §0 item 1 «Nenhum ato de 09/11 tem registro» | Painel · cada linha recebe «feito (data, prova)», «vencido» ou «reagendado (nova data)». Coluna de data-limite própria. **Depende da resposta do dono à pergunta fechada do PLANO §7.1 (não verificado).** |
| G-0024 (RS-26) | papel | não | B10.1 exige F3 ≥ 95% que não existe sem a chave. B9.2 usa «2× o custo medido na F3». | ROT:1165 «F3: **I1–I9 sem nenhuma falha** e ≥ 95% de desfecho/intenção corretos» | ROT:1123 «só I1–I9 com `ProvedorFalso`»; ROT:1143 «custo ≤ 2× o custo medido na F3» | B10.1 · «Sem chave: go reduzido com revisão de 100% e teto fixo, ou no-go.» B9.2: teto absoluto em R$ por atendimento quando a F3 não mediu custo. Fecha com G-0009. |
| G-0026 (RS-06) | papel | sim | O padrão 9 diz que descartar a chave AES inutiliza o `ia_obs`. O texto do Phoenix é só mascarado, não cifrado. | ROT:1488 «`ia_obs` no pgBackRest (chave AES descartada = texto inútil)» | ROT:43 «o texto mascarado do Phoenix sobrevive nos fulls» | Parte D, padrão 9 (e ROT:231) · «`ia_obs` fica no pgBackRest. O texto mascarado do Phoenix **não** depende da chave AES. Ele depende da retenção e da prova de D-32.» |
| G-0027 | estado | sim | Perguntas da Parte E com data-limite vencida ou vencendo, sem status. | ROT:1461 E-10 «09/11»; ROT:1467 E-16 «10/11 12:00» | ROT:524, 523, 210 dizem K pendente; ROT:88, 113 dão o «ok» a K em 04/11 | Parte E · status e data por pergunta. Riscar ROT:524 (K já aprovado). E-10: resposta ou plano B (imagem construída na S3, PD-3). |
| G-0029 (RG-043) | estado | sim | Linhas da Parte F dizem «aplicado em texto» sem dizer que a execução segue aberta. | ROT:1606 «VPS (A1.5) não existe ... aplicado em texto (v3.3)» | ROT:1572 define «Aplicado = só o texto»; ROT:174 Redeploy de 10/11 | Parte F, l.61, 75, 96 · «texto aplicado; execução pendente: [ato, data, dono]», com ponteiro para ROT:174/180. |
| G-0080 (RG-103; RS-11, RS-25) | papel | não | A Spec da B6.4 manda a R-a devolver `aberto` e `pausado`, mas o CAS só troca `aberto`. | ROT:1063 «devolve todos os `aberto` **e `pausado`»» | ROT:1063 «`UPDATE … SET estado='devolvendo' WHERE chave=? AND estado='aberto'`» | B6.4 · trocar o CAS por remissão a `adquirir_devolucao` do 04. Aceite: teste «R-a devolve um `pausado`» e ensaio da corrida. |
| G-0145 | estado | não | 1,2 GB/dia de disco chamado de «medido» sem ser. | ROT:580 «~1,2 GB/dia medido (A2.6)» | ROT:304 (Painel) «as duas leituras não dão taxa» | A2.6 e mais três pontos · «estimado» no lugar de «medido». Gravar as leituras de 02/11 e de 09–10/11 em `medicoes/` antes de calcular a taxa. |
| G-0152 (RS-04) | estado | não | O PR #49 do tap é dado como concluído, mas está em conflito com a main. | fase0/MANIFESTO.md:96 «#49 feat/tap-retornos draft=true mergeable=CONFLICTING» | ROT:797 «PR em rascunho, não mesclar (merge = deploy; só em B3.1)» | A6.4 e Painel · «concluída, rebase pendente». B3.1: rebase e nova revisão independente antes do merge. |
| G-0156 | papel | não | A8.3 cita «08 v2.3 prevalece»; o 08 vigente é v2.4 e a nota no sp01 segue pendente. | ROT:832 «a nota de precedência «08 v2.3 prevalece» ainda vai para o sp01, pendente» | contratos/08:1 «... · v2.4» | A8.3 · «contratos sem sufixo prevalecem (08 v2.4)». Aplicar a nota do G-0063. |
| G-0172 | papel | não | A regra do degrau não define rampa de 4 dias nem aceite. O PUT de 27/11 ficaria errado. | ROT:1288 rampa 10·15·15·10·20 | ROT:1293 «`PUT /config/max_disparos_dia` 27/11 → 15, 29/11 → 10, 30/11 → 20» | ROT:1288, 1208 e linha do go/no-go · rampa de 4 dias com n máximo, teto do dia 1, aceite para 4 dias e horário de 25/11. **Levar ao dono junto com G-0079.** |
| G-0174 | papel | não | A regra X7 foi adiada por delegação. A condição de ≥ 4 agentes já falhou. | ROT:1231 e ROT:1297 (≤ 3 agentes em 10/11 18:00 ⇒ alternativa (c), sem padrão) | fase0/decisoes-delegadas.md:79 «só remedir em 11/11 18:00» | Parte F · registrar a resposta do dono à pergunta fechada: «aceita remedir em 11/11 18:00, sabendo que a alternativa (c) tem 8 dias?». Alinhar §2 e §6 de decisoes-delegadas.md. |
| G-0175 | estado | sim | A conta do resíduo usa janelas de 10 e 14 dias que não existem mais. | ROT:1214, 1226 (janela de 10 d a partir de 09/11 e de 14 d a partir de 05/11) | PLANO-REVISAO-0911.md:10 e decisoes-delegadas.md:31 recontam com 9 dias | Conta de r · base 10/11, 9 dias. Apagar a linha de 14 dias. Somar rebase, kits, textos, A6.6b e reserva para correções. Anotar horas por item fechado. |
| G-0176 | papel | sim | A distribuição por agente supõe 5 agentes desde 09/11. A subida real é 1 → 2 → 4 → 5. | ROT:1248, 1252 (tabela de 5 agentes) | decisoes-delegadas.md (subida delegada; fila A4 fica parada até 12/11) | Tabela ROT:1247-1255 · reemitir para a subida real. B1.6b em 1º. Dizer qual fila (A4 ou A5) espera e o efeito no checkpoint 2. Dono e data para B9.5a, os 4 kits, A6.6b, D-14, D-15. |
| G-0186 | estado | não | O Anexo X diz que os kits estão versionados em `ia-atendimento/kits/`. Só `chats-teste.sh` está lá. | ROT:1732 «Os kits ficam versionados em `ia-atendimento/kits/`» | src/ia-atendimento/kits/chats-teste.sh é o único arquivo em kits/ na main 9a4bacab | Anexo X · caminhos e lista reais. PR que versiona `gateway/` e `s4/` em `ia-atendimento/kits/`. Ver F4-022. |
| G-0279 (RS-28) | papel | não | O plano B de devolução posta `link_chat` num canal não definido. | estudos/semana-1/j-operacao-piloto.md:179 «o Danilo posta no canal a lista de `link_chat`» (copiado para o ROT) | j-operacao-piloto.md:183 «T+15 aviso no grupo dos consultores com a lista» | ROT B11.3 e J §… · «Lista com id curto no ntfy; os links só em canal fechado definido em A1.7, ou na tela do TI.» |
| G-0286 | papel | não | A reabertura depois de atendimento anterior (L9) não tem especificação. | ROT:127 «N-5 sim» | estudos/…/n-ponto-de-partida.md «`recusa_firme` bloqueia 30 d; `opt_out` sempre» | Spec de B5.5/B1.5 · «`recusa_firme` há menos de 30 d impede E0. Novo `clt_job_id` depois de 30 d reabre.» Teste de aceite. Abrir RG. |
| G-0382 (RG-121) | papel | sim | B6.9 «sai da construção», mas a Spec ainda pede script, testes e revisão. | ROT (B6.9) «sai da construção (−1 d na L6)» | ROT (B6.9) «script à mão em 30/11 e 13/12 ...» e «Aceite: testes verdes» | B6.9 · versão única: dono, data, onde roda (contêiner do orquestrador na VPS, como `ia_app_a`). Se não houver script: «B12.1 sai sem "digitados em 48 h" automático; número levantado à mão por [quem].» |
| G-0387 (RG-102) | papel | não | Go/no-go: revisor opcional em A1.7, amostra revisada obrigatória em B10.1. | ROT:498 «sem revisor → B9.2 sem nota de rascunhos (cai a métrica de qualidade, não o go/no-go)» | ROT:1165 «amostra ≥ 30 atendimentos (v3.3) (RG-102) com ≥ 90% OK/leve» | A1.7 e B10.1 · uma regra nos dois: «sem revisor nomeado até 11/11, a amostra é lida só pelo TI e o go/no-go registra nota de um leitor» ou «sem amostra revisada não há go». Linha de RG-102 na Parte F. Nota «superado» em J §3.2 e L. **Decisão do dono.** |
| G-0469 (RS-18) | papel | não | A4.9 e P-R8 descrevem um deploy diferente da esteira (montagem, nomes de variável, arquivo de chaves). | ROT (A4.9) «`/etc/ia-s4:/run/ia-s4:ro` (**diretório**, `:ro`)»; «`CONVERSA_CHAVES` em arquivo 0600 `/etc/ia-s4/conversa.keys`» | compose e DEPLOY.md usam `/etc/ia-s4:/etc/ia-s4` (nota do verificador) | A4.9 · apontar para DEPLOY.md e OPERACAO §8–§9 como fonte única de nomes e caminhos. P-R8 e A6.6 (1): «build na S3, Coolify só puxa por tag». |
| G-0496 | estado | não | D-20 está decidida no roteiro e não implementada no dublê. | ROT «D-20 opção A nos dois (M-05, M-06)» | ROT «M-05 tri-state → `indeterminado`/T8; M-06 lista estreita» (dublê com `xfail`, nota do verificador) | bancos-duble · implementar a opção A, remover `xfail`, atualizar o cabeçalho com decisão e data. Se ficou só no ia-atendimento: dizer isso e apontar o teste de paridade. |

#### 6.3b Contratos vigentes

| Id | Tipo | Parcial | Contradição | Trecho A | Trecho B | Emenda proposta (arquivo · seção · texto novo) |
|---|---|---|---|---|---|---|
| G-0030 (RG-043; RS-27) | papel | não | O cenário C não chegou ao corpo do contrato 01 (datas 13/11 e 06/11). | contratos/01:236 «até o ensaio a seco de 13/11»; :321 «reserva de 06/11» | contratos/01:296 «ativar.sh vai a **19/11, 12:30**, se o ensaio a seco de 18/11 (B9.1)» | 01 · §5 l.236, §9 passos 1–6, Volta (iii), E-12, P6 · datas do cenário C (09/11, 10/11, reserva 11/11, ensaio 18/11, ativar 19/11) ou marca «histórico». Atualizar `JANELA_*` em lib.sh e as mensagens do kit (ver G-0515). |
| G-0035, G-0554 | papel | não | O 06 e o 03 mandam reler `vendedor_ator_id`, que só sai com `C360_VENDEDOR_ATOR_ID=on`. B4.2 liga só duas flags. | contratos/06 «vendedor_ator_id da pessoa por pessoas:resumos»; contratos/03 «`vendedor_ator_id` (resolver `obsoleto`, 06)» | src/cliente360-api/src/c360api/config.py:861; rotas/pessoas.py:427 | 03 §3 e ROT B4.2 · «Três flags: `C360_NAO_PERTURBE_30D`, `C360_LIMITE_CONTRATOS`, `C360_VENDEDOR_ATOR_ID` (ordem ISKRA → web → API).» Sem o campo no T1, o resolver `obsoleto` falha fechado (repasse), com teste. Valor em produção: **não verificado** (leitura só-leitura). |
| G-0065 (RG-004) | papel | sim | sp01 Task 8 repassa sem modelo no teto mensal; o 08 §9 tem níveis 80/100/125%. | planos/…-01-orquestrador-nucleo.md:593 «`teto_mensal` atingido ou disjuntor ⇒ **repasse sem chamar o modelo**» | contratos/08 §9 l.284 e src/…/gasto.py:11 (80/100/125%) | sp01 · Task 8 passo 1 · níveis do 08 §9 e `GastoIndisponivel`. Nota de precedência do G-0063. |
| G-0067 (RG-123; RS-34) | papel | sim | MON manda Phoenix atrás do Cloudflare Access e ntfy com servidor próprio. O vigente é túnel SSH e ntfy.sh. | estudos/MONITORAMENTO-DESIGN.md:235 «atrás do Cloudflare Access restrito ao grupo TI» | ROT A1.6 «só por túnel SSH no tailnet (D-30)»; A4.7 «`ntfy.sh` no piloto» | MON §8a, §10, §6 · «"Ver bruto" mostra o `trace_id` (32 hex) e a instrução do túnel. Link só se o dono disser "não" a D-30.» |
| G-0195 (RS-30) | papel | não | O 04 promete PII só por função, mas dá SELECT direto em `sob_ia` com `chat_number`. | contratos/04:18 «PII só por funções `SECURITY DEFINER`» | contratos/04:209 «chat_number text, -- PII» | 04 · §4 · `GRANT SELECT` por coluna sem `chat_number` (ou view sem a coluna) para `ia_espelho` e `ia_vigia`. Matriz negativa do kit: `SELECT chat_number FROM ia_espelho.sob_ia` deve falhar. |
| G-0197 | papel | não | Respostas do orquestrador sem destino no braço n8n (`ja_atendido`, 403, 404, 429, 409 de chave divergente). | contratos/04:98 «**422** ⇒ `cancelar` ... **401** ⇒ `cancelar` + ntfy TI» | contratos/04:175 «por pessoa só o orquestrador (409)» e `ja_atendido` | 04 · §2.5 · tabela fechada status/código → ação (cancelar, pular, abortar, incerto). Código desconhecido ⇒ incerto + alerta. |
| G-0204, G-0214, G-0233 (RS-11) | papel | não | Batimento: relógio de comparação, tolerância e margem não definidos. Limiar 90 s com timer de 60 s deixa ~10 s. | contratos/04:385 «ausente ou **`gerado_em` > 90 s**»; 04:377 timer 60 s | contratos/08:261 «> 90 s»; 08:358 «relógios ... ± 300 s» | 04 §7 e 08 §7.4 · «Idade = relógio da VPS menos `gerado_em`, com tolerância explícita; chrony nas duas pontas; `seq` ≤ último com `gerado_em` diferente é recusado. Limiar ≥ 150 s com alerta amarelo a 60 s, ou gravação a cada 15 s.» HMAC no arquivo, ou risco aceito por escrito. Teste com relógio falso: 59 s e 75 s não alertam. |
| G-0212 | papel | sim | Passos do dedupe e o nome do identificador de mensagem divergem entre §5.1, nota v2.2 e §5.3. | contratos/08:129 «até lá message_id é 422 campo_fora_da_allowlist» | contratos/08:131 «msg_chave = cgid: + HMAC(chat_id, mensagem_id)» | 08 · §5.1/§5.3 · um nome de campo e um corpo aceito; dedupe de 5 s na ordem e na tabela de resultados. |
| G-0224, G-0225 (RS-32) | papel | sim / não | Envio ao cliente: quais status são ambíguos não está fechado. 502 e 504 não estão classificados para `nota_enviada`. | contratos/02 §5 «transporte, 429/502/503/504 e, por padrão, timeout» | contratos/02 «400/422/503/401/403 ... ⇒ nao»; «qualquer 424, timeout ... ⇒ incerta» | 02 · §5 · tabela status → ambíguo/definitivo para `message_send`; conferência por `is_out` depois da tentativa. Nota: «504 ⇒ incerta; 502 ⇒ incerta; 429 ⇒ nao.» Teste do wrapper por status. |
| G-0230 (RS-22) | papel | não | A tela não trata 401/403 da API, falha de transporte nem dado velho. | contratos/07 «O token `ia` vive ≤ 900 s» | contratos/07 §5.4 mapeia só 409, 422, 503 | 07 · §5.4 · «401/403 ⇒ "Credencial da IA expirada, chame o TI" + caminho de emergência. Falha de transporte no PUT ⇒ `resultado_desconhecido` (releitura). 429/5xx ⇒ "Não consegui gravar". `lido_em` > 60 s ⇒ "desatualizado".» |
| G-0239 (RS-17) | papel | não | O alarme `forward_falhou` não enxerga `destino_erro`. | contratos/04 «424 (`destino_erro`), repetível e visível no alarme `forward_falhou`» | contratos/04 «`forward_falhou > 0` por 1 min (B6.1)» | 04 §1 e regra da vigia · `resultado IN ('forward_falhou','destino_erro')` nas rotas `ia-%`, limiar próprio para `destino_erro`. 01 §6.1: qual peça alarma cada linha. |
| G-0368 (RG-010; RS-03) | papel | não | RG-010 foi refutado, mas o 05 ainda proíbe o que o PR #49 grava. | contratos/05:106 «(nem normalizada: nome ou texto livre não se prova ausente por regex)» | ROT:1582 «05 e o regime de permissão pendentes: contratos não se editam nesta rodada» | 05 · §4/§5.1, antes de 12/11 · desenho real: rótulo fechado, hash de 12, teto diário, nome único da flag. Revisor do #49 prova que `DESCONHECIDA` nunca guarda texto. |
| G-0499 (RS-15) | papel | não | O 05 cita um teste do dublê que não existe. A janela 20 × 10 não tem teste que compare. | contratos/05 §2.3 «é testado com **os mesmos** números (`test_dubl_t8_prazo_1500`)» | nome ausente em todos os repositórios (nota do verificador) | 05 · §2.3 · trocar «é testado» por critério de aceite de B5.4/B2.2 e citar `test_conferir_janela.py`. Asserção `xfail(strict)` que compara `decide_em - tentativa_em` com `JANELA_CONFERIR_MIN` até B3.2. |
| G-0566 (RS-09) | papel | não | TX-42 no repasse de noite e domingo sai sem conferir a janela 08–20. | contratos/08 «fora dela (noite, sábado depois das 12:00, domingo), **TX-42** com `{{retorno}}`» | contratos/08 «Todo envio posterior repete o teste e registra `janela_24h`» | 08 · §7.1 · «A mensagem do repasse (TX-25/26/27/42) só sai com `dentro_da_janela` e 24 h abertas no instante do envio. Fora disso o repasse segue sem mensagem (passo `fora_de_janela`).» §6: linha «janela 08–20 conferida antes de cada envio». |

#### 6.3c Estudos, textos e espec de tela

| Id | Tipo | Parcial | Contradição | Trecho A | Trecho B | Emenda proposta |
|---|---|---|---|---|---|---|
| G-0040 (RS-12) | papel | sim | O estudo E segue com `ia_app` dono do banco e com DDL. O ROT já usa `ia_owner`. | estudos/semana-1/e-infra-s4-vps.md «migrações e `procrastinate schema --apply` rodam como `ia_app`» | o mesmo arquivo, l.439 «**Dono do banco = `ia_owner` (NOLOGIN)**» | e-infra · tarja «histórico; superado por ROT A4 e kits/s4». Garantir que `s4-papeis.sh` é o único caminho executável. Fecha junto com F4-021. |
| G-0044 (RS-10) | papel | sim | A trava «não repetir T7» e a proposta viva do CPF são por atendimento e janela de 30 min. | f-catalogo-ferramentas.md «t7:{atendimento}:{banco}:{oferta_id}:{oferta_versao}:{tentativa}» | f-catalogo «o trinco é só local (não protege contra digitação humana/n8n concorrente)» | ROT B5.4 e 05 §2.2/§2.4 · trinco por (pessoa, banco) até a T8 resolver ou o humano fechar. Teste com dois atendimentos da mesma pessoa. |
| G-0048 (RS-24) | estado | sim | O estudo H não tem `ultimo_cliente_em`. O ROT já tem a regra (P-R21, regra 11, risco 95). | h-roteiro-conversa-memoria.md:153 «flags{janela_aberta, banco_ok, humano_ativo=false, ultimo_envio_em}» | ROT:271 (P-R21), ROT:51, ROT:1424 | H · tarja nos §2.4, §3.2, E9 e risco 5: «superado por ROT P-R21 e regra 11». |
| G-0053 | papel | sim | M: teto de 23 h contra exemplos «amanhã às 18h». O código já aplica o teto. | m-agendar-assinatura.md §2.4 «Teto: `min(ultima_msg_cliente + 23 h, próximo dia útil 19:00)`» | m §2.3 «amanhã de tarde ... média → confirma»; TX-M08 «amanhã (quinta, 30/10) às 18h» | M §2.3 · coluna «dentro do teto?». Decidir se «amanhã» exige modelo WABA no MVP. |
| G-0059, G-0060 | estado | não | A espec de tela usa datas anteriores a 04/11 (F0 em 12/11, matriz FP-01..FP-10 antiga). | estudos/TELA-IA-C360.md:957 «F0 · MVP de B7.1 (12/11 ...»; :807 «FP-05 \| Sombra A, 16–19/11» | ROT:1271 «12:30 web (#7 ...)» em 17/11; ROT:1272 congelamento 18/11 | TELA-IA-C360 §4.2 e §5.1 · datas do cenário C (#7 17/11, congelamento 18/11, sombra 23–25/11, go 25/11, piloto 26–30/11, relatório 01/12) ou ponteiro para a Parte C. Mesmo para L-situacoes §2/§4. |
| G-0262 | papel | sim | O hash da confirmação não cobre os dados de recebimento. | f-catalogo «hash de {banco, valor, parcela, prazo, tabela} e ≤ 30 min» | f-catalogo «nunca repetir conta/PIX/endereço de volta fora do template de confirmação» | ROT B5.4 · hash inclui dados de recebimento e `oferta_versao`; T6 depois do «sim» invalida a confirmação. Uma só definição. |
| G-0367 (RS-23) | papel | sim | Textos afirmam fatos do banco sem ferramenta nem validação. | TEXTOS-PARA-APROVACAO.md TX-32 «O banco mostra isso na tela de assinatura antes de você concluir» | TX-39 «selfie, documento e assinatura são feitos lá» | TEXTOS · segurar TX-32/39/41 até a FACTA confirmar; TX-06 «a condição disponível agora»; TX-14 sem «alguns minutos». |
| G-0418 (RS-23) | papel | não | FAQ com pergunta sim/não liberada na E6 confunde o SIM da confirmação. | src/ia-atendimento/src/ia_atendimento/turno.py:110 e :112 (TX-39/40 liberados em E3–E6) | TEXTOS rotula TX-39/40/41 como «E2/E8 (FAQ)» | Escolher: tirar TX-39/40 de E6 e E8 em `TX_DO_MODELO_POR_FASE`, ou exigir na B5.5 que o SIM só valha depois de TX-11/TX-36. Teste: «sim» depois de TX-40 na E6 não gera T7. |

#### 6.3d Documentos de operação e kits nos repositórios

| Id | Tipo | Parcial | Contradição | Trecho A | Trecho B | Emenda proposta |
|---|---|---|---|---|---|---|
| G-0098 (RG-034) | papel | não | O OPERACAO manda aplicar migrações a partir da tag v0.1.0, que não existe e só tem 0001–0002. | src/ia-atendimento/docs/OPERACAO.md:47 «tag v0.1.0 depois da revisão» | ROT B1.7 «v0.1.0 e v0.2.0 ... a B1.7 corta a v0.3.0» | OPERACAO §3 · «Na tag da imagem que sobe (v0.3.0 ou posterior), migrações 0001–0005, com `kits/s4/migrar.sh`.» §11: «v0.1.0 e v0.2.0 cortadas; a B1.7 corta a v0.3.0.» |
| G-0100, G-0400 (RS-05) | papel | sim / não | Virada mensal da chave AES: reinicia só o orquestrador, não o worker. O OPERACAO promete falha de subida que o boot não faz. | OPERACAO.md:36 «exige **reiniciar o orquestrador**»; OPERACAO.md:186 «chave AES que não é a do mês» como falha de subida | src/…/api/ambiente.py:71 (boot só monta o Chaveiro); conversa.py:156 (checa por requisição) | OPERACAO §2, §8, §9 · «Na virada reiniciar API **e** worker; conferir `GET /readyz` e `--saude`; alerta ntfy 30 min antes do fim da tolerância.» Código: `exigir_chave_do_mes` no boot de API e worker e no `/readyz`, ou o doc diz «falha por requisição». Ver G-0084 (código). |
| G-0120 (RG-104) | estado | não | Texto acima de 4000 caracteres dá 422. O 08 v2.4 §5.1 manda truncar. | src/ia_atendimento/api/eventos.py:46 `max_length=LIMITE_TEXTO` | contratos/08 §5.1 l.124 e ROT:904 «truncar e nunca responder 422» | Código (B1.6): aceitar até o limite do corpo (64 KB dá 413), truncar em 4000 antes de `EventoMensagem.criar`, logar só o tamanho. Igual a R2-022. Teste: 4001 caracteres ⇒ 200 e texto com 4000. |
| G-0374 (RG-083; RS-07) | papel | não | O OPERACAO não fixa dono e permissão dos arquivos 0600 em `/etc/ia-s4`. | src/…/cifra.py:113; segredos.py:47 (só 0600) | kits/s4/distribuir-certs.sh:85, :88 (root:grupo 0640) | OPERACAO §8 e ROT A4.9 · tabela única: certificados e `.senha` = root:<gid do app> 0640; chave AES, HMAC e saída = <uid>:<gid> 0600; comandos `install -m 600 -o <uid> -g <gid>`. Ensaio confere `%U`. Ver G-0097 (ALTO, código). |
| G-0461 | estado | não | A última revisão independente da B1.6a diz «não mesclar». As correções só foram conferidas pelo autor. | src/ia-atendimento-b1-6a/docs/REVISAO-B1.6a-0411.md «**Não mesclar como está.**» | o mesmo arquivo: branch `feat/b1-6a` @ `4ddc03a` | Processo · depois do rebase (G-0076), revisão r2 independente de `ledger.py`, `gasto.py`, `expiracao.py` e hunks de `jobs.py`/`chave.py`/`api/atendimentos.py`, repetindo as sondas A1–A6. |
| G-0497 (RS-15) | estado | não | O dublê foi provado contra facta-on e9ba005. Nada confere o SHA; a main é 8c3e5ab. | src/bancos-duble/tests/facta_on_checkout.py:24 (aceita qualquer diretório com `app/main.py`) | src/bancos-duble/tests/test_facta_on_app_isolado.py:16 (fixa e9ba005) | bancos-duble · gravar o SHA no checkout (`.sha` ou `FACTA_ON_SHA`), imprimir no cabeçalho do pytest; `check.sh` avisa SHA diferente. Refazer em 8c3e5ab e rodar I23/I25 antes do merge de B3.2. |
| G-0515 (RS-08, RS-27) | estado | não | O kit do gateway tem datas, versão de contrato e mensagens desatualizadas. | kits/gateway/README.md:3 «01-gl-gateway.md (**v2.4**, §9)»; :27 «noite de 04/11 \| rotas-ia.sh --confirmo» | contratos/01 v2.5 §9 l.296: janela ter 10/11 05:30, reserva qua 11/11 | kits/gateway · README e sentinelas de data para v2.5 e 10/11 (reserva 11/11), ou linha na Parte F «kit desatualizado». |
| G-0519 (RS-08) | estado | não | O «170 PASSOU» do kit do gateway é de outros SHAs e anterior às últimas edições. | kits/gateway/ensaio-local.sh:17, :19 (GW_REPO/IA_REPO livres) | kits/gateway/README.md:287 «`app/` do `gl-gateway` em `5b191b1`»; main 92e97548 | kits/gateway · rodar de novo com os SHAs da main e gravar no README: SHA do gateway, SHA do orquestrador, sha256 de cada script, data e hora. Rodar `portao-trafego` 20× e ler o caso que falhar. Depende de F4-035. |
| G-0531 (RS-17) | papel | não | F07 proíbe corpo de evento em span «nem mascarado». O código exporta o conteúdo por padrão. | src/…/observabilidade.py:258 `incluir_conteudo=True` | src/…/observabilidade.py:277 repassa a `include_content`; tests/test_observabilidade.py:146 exige o conteúdo | **Decisão do dono antes de ligar o Phoenix (A4.5/D-32):** ou F07 vale e o padrão vira `incluir_conteudo=False`, ou 01/08 ganham a exceção «texto mascarado no span do turno, 14 dias», com o residual de nome declarado. |

### 6.4 Processo e papel vindos da Fase 4 (3 MÉDIO; 2 ALTO no §5)

F4-035 e F4-036 (ALTO) estão detalhados no §5, «Lacunas de prova da própria revisão». Aqui ficam os três MÉDIO.

| Id | Sev | Achado | Prova principal | Emenda proposta | Prova de feito |
|---|---|---|---|---|---|
| F4-021 | MÉDIO | O roteiro manda desfazer A4.3 pelo texto v1 do estudo E (3 papéis), não pelo `desfazer.sh` (8 papéis). | ROT:706 «**Desfazer:** E §4 «Desfazer tudo» 1»; e-infra-s4-vps.md:393 (DROP de 3 papéis); kits/s4/desfazer.sh:28 (8 papéis) | ROT:706 · «Desfazer: `kits/s4/desfazer.sh` (D2–D5 na A4.3a; D1 só na A4.3b), com `--ensaio` antes.» Tarja em e-infra:392-393. | `grep -n "Desfazer tudo" ROT` vazio. |
| F4-022 | MÉDIO | O kit que roda é cópia solta em `~/retomada-2809/`, sem trava de hash. O ramo `kits/s4` não tem push. | kits/s4/README.md:26 «!bash ~/retomada-2809/fila-2910/ia/s4/s4-papeis.sh»; ROT:324 «(148cc72, sem push)»; MANIFESTO.md:36 «ahead 1, behind 178» | Push de `kits/s4` e PR em rascunho. Antes do `!` da A4.3a: `sha256sum -c` contra MANIFESTO.md:120-127, ou rodar do worktree em 148cc72. | `git ls-remote origin kits/s4` devolve 148cc72 ou sucessor; `sha256sum -c` OK. |
| F4-037 | MÉDIO | Costuras F2b-04, F2b-05, F2b-08, F2b-09 e F2-40 foram lidas com um lado só. A regra de isolamento proibiu a entrada obrigatória. | fase3/cobertura.json, `nao_lido` dessas unidades: «a regra geral proíbe ler relatório de outra unidade; não li» | Um verificador por costura lê F2b-0n e as F2 citadas e só aponta contradições. Regra do workflow: permitir ler relatório quando o roteiro da unidade o declara entrada. | Relatório de costura com as duas leituras citadas. |

### 6.5 Peças que não existem (100), por bloco do roteiro

Toda linha é uma peça ausente provada. A coluna «Critério de aceite» é o que fecha o item: um comando ou teste que reprova se a peça faltar. Nomes de teste entre crases vêm das fontes quando a fonte os nomeia. Os demais são propostos.

#### A1 e A2: pendências do dono e medições (6)

| Id | Sev | Peça ausente | Prova da ausência | Critério de aceite verificável |
|---|---|---|---|---|
| G-0001 (RG-041; RS-01) | ALTO | VPS OVH BHS | ROT Painel «VPS OVH BHS \| não iniciada; **prazo 03/11 vencido; pendente do dono»; fase0/reconciliacao.md:179 «Feito com prova: nenhum» | Da S2, `ping -c1 10.90.0.5` responde. Na VPS, `wg show wg0` lista 10.90.0.5. `nft list chain inet ia_vps output` mostra allowlist. `curl -m5` a host fora da lista falha. Limite do dono: 12/11 14:00 (PLANO §7b). |
| G-0260 | MÉDIO | DPA e retenção zero contratual do provedor | estudos/…/g-provedor-modelo.md «Retenção zero «por contrato» não existe em página pública de nenhum deles.» | Parte F tem linha datada: e-mail enviado e resposta arquivada, ou decisão do dono «aceita a política publicada no piloto». |
| G-0385 (RG-108) | MÉDIO | Kit de rotação das chaves expostas (A1.8) | ROT (A1.8) «**depois do piloto, a partir de 02/12** (corte de C)» | Linha de risco aceito no go/no-go com 02/12 e responsável. Kit com `--ensaio` rodado e saída gravada antes de 02/12. Três ajustes do parecer respondidos em D-24. |
| G-0147 | MÉDIO | Seção A1.13 (cookie do RPA) | ROT:298 «sem seção própria, passos em A2.1» | A1.13 escrita com passos. `sessao?conferir=true` devolve `idade_s` < 3600. Fallback e quem decide se o 2FA falhar estão escritos. A2.1 marca «vagas: não medido (padrão 5)». |
| G-0336 | MÉDIO | Medição de cache, tokenizer e latência (A2.11b) | premissas.json:569-577 «deepseek-v4.1-flash-eua classe estimado, cache de lista não aplicado» | Arquivo em `medicoes/` com `usage.prompt_tokens` reais e taxa de cache medida. R$/atendimento e o teto de R$ 2.000 recalculados. Classe da premissa passa a «medido». |
| G-0581 | BAIXO | Artefatos das medições prometidas | `medicoes/` só tem 5 arquivos, todos de 30/10 | Cada medição prometida tem arquivo datado em `medicoes/` (A2.4, A2.8, A2.12 e outras), com dono. `ls medicoes/` lista todas. |

#### A3 e A5.9: ensaios do canal e contrato 02 (6)

| Id | Sev | Peça ausente | Prova da ausência | Critério de aceite verificável |
|---|---|---|---|---|
| G-0068 | ALTO | Prova de Post por mensagem e do retry do webhook | contratos/01-chatguru-lead.md «Retry/idempotência do webhook do ChatGuru: pergunta em aberto, nunca respondida» | A3.1: 1 mensagem do chat de teste = 1 linha em `gateway.requisicoes` (SELECT count). Chaves registradas só por nome. Casos 424 e timeout com contagem de repetições. |
| G-0036 | ALTO | Cláusula que fixa o ator 85 no contrato 02 | contratos/02 «atribuição ator 85 \| não é daqui» | 02 emendado: id do robô fixo em configuração, não no corpo. `test_assumir_so_delega_ao_amado` e `test_enviar_recusa_phone_id_fora_da_lista` verdes. A3.3: leitura da conversa mostra autor e responsável esperados. |
| G-0039 | MÉDIO | Plano B para a falta do diálogo «pega-tudo» | estudos/…/b-receptor-mensagens.md «O diálogo «pega-tudo» pode não existir** (alto)» | Resposta do ChatGuru às perguntas 1 e 6 arquivada antes do piloto. Se negativa, decisão escrita do dono: RPA como leitor principal, com orçamento de vagas e SLA de latência. |
| G-0373 (RG-062) | MÉDIO | Kit do ensaio n8n S1–S6 (A3.8) | ROT (A3.8) «(1) Claude escreve o kit com export e remoção (**não existe hoje**)» | Kit importa o fluxo inativo, exporta resultado só com nomes de chave e códigos HTTP e remove o fluxo. `--ensaio` passa. S1–S6 registrados antes do aceite de B6.2 e do #6 (16/11). |
| G-0028 | MÉDIO | Desenho único do leitor RPA (desvio linha 1) | ROT:1330 «reconciliador RPA ≤ 10 chats como leitor principal ... é contra a decisão (k)» | Linhas 1, 8 e 40 da tabela de desvios reescritas num desenho. CG-12 e RPA-03 medidos em A2.4, com arquivo. O teto de 10 diz se é concorrente ou diário. |
| G-0179 | MÉDIO | Plano para K-E21 «re-dispara» (desvio linha 10) | ROT:1339 «o portão do `zVuE` (cortado em C6, v2) reabre se K-E21 mostrar o re-disparo» | Linha 10 diz o que acontece se K-E21 = re-dispara: reabrir B6.5 com escopo nomeado, ou aceitar o risco com o bot desligado. Data limite escrita. |

#### A4: infra S4, VPS, chaves e certificados (15)

| Id | Sev | Peça ausente | Prova da ausência | Critério de aceite verificável |
|---|---|---|---|---|
| G-0012, G-0464, G-0426 (parte A4.6) | ALTO, MÉDIO, MÉDIO | `kits/s4/migrar.sh` | ROT:717 «kit `s4/migrar.sh` a escrever (Claude, 0,5 d, ensaio local)»; migrations/README.md:57 | `migrar.sh --ensaio` em PG 18 descartável aplica 0001–0005. Depois, por conexão nova, `select count(*) from ia.migracao` = 5. O sha256 de cada arquivo confere com o manifesto e o ledger. A 0005 só passa com palavra própria (`--sim-0005`). Segunda execução não reaplica. Seeds do calendário intactos. Pronto até 12/11 (G-0377). |
| G-0013 | ALTO | Política de saída (egress) da VPS | ROT:708 «tabela própria `inet ia_vps` com janela de reversão» (sem chain output) | A4.4, passo 11: chain `output` com `policy drop` e allowlist; timer de reversão ensaiado. `curl -m5` da VPS a host fora da lista falha; a host da lista passa. |
| G-0135 | MÉDIO | Kits previstos para 05–08/11 (`s4/migrar.sh`, `config/domingo.sh`, `gateway/ativar.sh`, chave AES de dezembro) | ROT:1262 (Parte C) lista os quatro | Cada kit vira critério de aceite de A4.6, B6.7, B6.1 e A3.8. Uma só data para o `ativar.sh` no ROT. `ls kits/` mostra os quatro. |
| G-0377 (RG-079) | MÉDIO | Kits prometidos pelas emendas | inv-kits.tsv: só `./config/chats-teste.sh` | Por kit: `--ensaio`, backup, reversão automática, comando de volta, revisão por quem não escreveu. Datas: `migrar.sh` até 12/11; `ddl-espelho.sh` e `vigia/instalar.sh` com B6.4; `gateway/ativar.sh` até 18/11; `ensaios/` na B9.0. ROT:1138 corrigido para 19/11 12:30. |
| G-0750 | BAIXO | Kit da regra nft da VPS e da rotação de segredos do gateway | kits/s4/README.md:12 | Kit nft com `--ensaio` e desfazer (entrada e allowlist de saída). `rotacionar.sh` entrega com duas chaves e retira a antiga. `encerrar.sh` apaga segredos locais e imprime a contagem. |
| G-0762 | BAIXO | Rotação para `ia_app_b` | kits/s4/s4-papeis.sh:10 | `s4/rotacionar.sh --ensaio` liga o `_b` (senha, certificado, pg_hba, LOGIN), prova a conexão e só então desliga o `_a`. Ou registro escrito: rotação fora do piloto, com procedimento manual de emergência. |
| G-0736 | BAIXO | uid/gid real do orquestrador na VPS | kits/gateway/entregar-hmac-vps.sh:23 (valor de hipótese) | `docker run --rm <imagem> id` gravado. `UID_APP` e `GID_APP` passados ao kit. Boot do orquestrador sem `SegredoInvalido`. |
| G-0755 | BAIXO | Calendário de renovação dos certificados de 397 dias | kits/s4/distribuir-certs.sh:67 | `provar.sh` roda `openssl x509 -checkend 5184000` (60 dias) e falha perto do vencimento. Lembrete a T-60 dias registrado. |
| G-0401, G-0323 | MÉDIO, MÉDIO | Descarte mensal da chave AES (kit e regra do dia 31) | OPERACAO.md «no dia 31 após o fim do mês, apague a entrada»; sp01:53 «linha de `chave_id` descartada = texto ilegível (aceito: 14 d)» | Kit: data de descarte = fim do mês N + 31 d (≥ teto de 30 d), com dono. Edição atômica, shred da cópia, reinício. Prova: o chaveiro não tem id de N; uma linha sintética de N dá `ChaveDesconhecida`. Alerta se `omitidas` > 0 antes da data. |
| G-0273 | BAIXO | Custódia da chave AES, parecer J5 e aceite do `chat_number` | i-esquema-reconciliado.md §6 «Custódia e rotação da chave AES» | No G2: documento de custódia, parecer J5 e aceite escrito do dono, os três com data e caminho. |
| G-0221 | MÉDIO | Lista de IP na credencial da API (barreira só no vhost 8118, que não existe) | contratos/03 «sem lista de IP e a barreira é o allow do vhost + WG» | B4.1/A4.4: requisição de origem fora do WG recebe 403 (prova negativa gravada). Ou `PROXIES_CONFIAVEIS` e lista de IP configurados. |
| F4-023 | MÉDIO | Comando para o `pg_dump -s` exigido no aceite da A4.3a | kits/s4/provar.sh:65 aborta sem `VPS_SSH_DEST` antes do bloco do dump (l.80-96); ROT:705 «roda à mão» | `provar.sh --so-s4` (ou o comando literal no ROT) roda sem `VPS_SSH_DEST`, imprime o dump `-s` de `ia_atendimento` e mostra a recusa de `ia_obs`. Exit 0. |

#### A5: contratos entre peças (2)

| Id | Sev | Peça ausente | Prova da ausência | Critério de aceite verificável |
|---|---|---|---|---|
| G-0242 | MÉDIO | Contrato das saídas do orquestrador (provedor de modelo, ntfy, Phoenix) | contratos/08 «409 `provedor_fora` · `pre_voo_falhou` ... PreVoo: modelo; S4, canal ou cookie» (sem seção de saídas) | 08 ganha §«Saídas» com três tabelas: destino, credencial, campos permitidos (lista fechada, sem corpo de evento), timeout, erro e retentativa. Teste-canário por sumidouro. Item «Com o 02» em §16. |
| G-0236 | MÉDIO | Linhas na matriz de restrições para itens de segurança dos contratos | contratos/04:13 | `fase0/matriz-restricoes.md` (ou a matriz vigente) tem linhas para: identidade do operador de disparo (B6.2), allowlist e testes negativos do vhost WG (A4.4), R2-26 como risco aceito, credenciais do n8n no c360-auth. |

#### A7: textos (4)

| Id | Sev | Peça ausente | Prova da ausência | Critério de aceite verificável |
|---|---|---|---|---|
| G-0072 | ALTO | TX-42 (aviso de domingo) | src/…/vocabulario.py:228 `[f"TX-{n:02d}" for n in range(1, 42)]` (para em TX-41) | `grep -n TX-42 textos/TEXTOS-PARA-APROVACAO.md` acha. `TX_IDS` inclui TX-42. Teste de vocabulário com TX-42 verde. |
| G-0073 (RS-23) | ALTO | Textos fixos no código e trava contra divergência | src/…/modulos_fase.py:105 `"TX-32": "taxa e custo total (CET)"` (só rótulos) | Constantes TX no código. Teste que compara cada constante com o texto aprovado e reprova divergência. |
| G-0071 | MÉDIO | Aprovação e hash dos 67 textos (A7.2) | TEXTOS-PARA-APROVACAO.md «Aprovado, cada texto é travado por hash (A7.2)» | Arquivo de hashes com sha256 por TX e versão. Teste de A7.2/B5.5 recalcula e reprova divergência. Aprovação nos lotes 11/11 e 13/11 registrada. |
| G-0378 (RG-064) | MÉDIO | Dicionário de `contexto_codigos` e `texto_livre.casos.json` | TEXTOS-PARA-APROVACAO.md «Versão 1, gerada em 30/10/2026» (sem o dicionário) | Tabela código → frase (≤ 80 caracteres, sem PII) cobre `motivacao_*`, `objecao_*`, `pendencia_*`, `repasse_*`, a regra L6 e TX-01 sem nome, no lote de 13/11. `casos.json` nasce na B1.6b com sha anotado; B6.2, B7.1 e B4.3 conferem o sha no PR. ROT:997 corrigido para 13/11. |

#### B1: orquestrador (19)

| Id | Sev | Peça ausente | Prova da ausência | Critério de aceite verificável |
|---|---|---|---|---|
| G-0066 | ALTO | B1.6b inteira: processador, repasse, Canal, verificador, confirmação, `reaper_ledger` | src/ia-atendimento-b1-6a/docs/DECISOES-B1.6a-0411.md «**Tudo da B1.6b**: processador, repasse em etapas, `Canal` ...» | Branch da B1.6b com as seis peças e portão verde. Teste que liga `valores_hash` a `args_hash`. |
| G-0083 | ALTO | Parada dura por gasto e disjuntor por atendimento | src/ia_atendimento/agente.py:99-106 | `test_80_100_125_por_cento`, `test_gasto_indisponivel_nao_chama_o_modelo` e teste do disjuntor (24 turnos, R$ 3, `custo_max_brl` da faixa) verdes no ramo que for mergeado. |
| G-0089 | ALTO | Ledger de efeito ligado ao gateway de ferramentas | src/ia_atendimento/ferramentas/gateway.py:25 | Toda ferramenta com `idempotencia != nenhuma` só executa por `executar_efeito`, com `reservada` gravada antes. Teste: mesma chave duas vezes = uma execução. Contadores lidos do ledger. Boot recusa executor real de T7 sem ledger. |
| G-0115 | ALTO | Turno, Canal e T7 ligados ao ledger | src/ia-atendimento/src/ia_atendimento/worker.py:52 | Todo envio e toda ferramenta com efeito passam por `executar_efeito` com chave determinística. Teste com dois workers reais e SIGKILL entre `enviada` e o fechamento: zero reenvio e zero segunda digitação. `tratar_lease_vencido` e `enviar_lembrete` com CAS por `versao` e `lease_ate`. |
| G-0091 | ALTO | Rede de recuperação da volta (`tratar_lease_vencido` termina em serviço inexistente) | src/ia-atendimento/src/ia_atendimento/worker.py:49 | Handler real de `retomada_perdida` e `agendamento_perdido` chama `fechar_volta_perdida` na transação do repasse. Teste de SIGKILL pós-CAS até o lead chegar ao humano. Boot recusa `agenda_ativa=true` com serviço `_NaoConfigurado`. |
| G-0389 | MÉDIO | Chamador de produção da máquina de estados | src/ia_atendimento/api/atendimentos.py:193 | Teste ponta a ponta sem espião: atendimento vai de `reservado` a `encerrado` só por jobs reais. `repassando` com lease vencido é recolhido (alerta aos 10 min, limite 30 min). Turno acima de 5 min chama `renovar_lease`. |
| G-0391 | MÉDIO | Laço do turno (consumir, fala da IA, resumo, leitura do canal, `omitidas`) | src/ia-atendimento/src/ia_atendimento/linha_tempo.py:62-63 | `ConflitoDeVersao` unificado com teste do perdedor repetindo o turno. Fala da IA gravada na mesma transação do passo `resposta_enviada`. `omitidas > 0` vira `erro` ou repasse. `cofre.ler("canal")` = None vira repasse com código próprio. |
| G-0396 | MÉDIO | `Servicos` de produção no worker | src/ia-atendimento/src/ia_atendimento/worker.py:52 (vazios) | Todos os serviços injetados em `worker.py`. Teste de processo real: turno morto por SIGKILL termina repassado pelo `reaper_lease`. `processar_turno` relê `ia_ativa` e `modo` antes do modelo e antes do envio. |
| G-0407 | MÉDIO | Pré-voo real e batimento lido no `/readyz` | src/ia-atendimento/src/ia_atendimento/api/ambiente.py:77 | Pré-voo real em `_montar`, com teste de 409 `provedor_fora`. `batimento_idade_s` lido de verdade; `/readyz` falha com batimento velho. Deploy só declara «no ar» depois da vigia. |
| G-0422 | MÉDIO | Chamador de `montar_contexto` | src/ia-atendimento/src/ia_atendimento/contexto.py:523 | Teste de fiação: processador ponta a ponta com `ProvedorFalso` afirma o que chegou em `vistos`. Turno só de mídia não chama o modelo. Duas falhas de contexto viram repasse com passo `erro`. |
| G-0423 | MÉDIO | Teste das 84 `pessoas_teste` com `vistos` | src/ia-atendimento/tests/test_contexto.py:100 | 84 pessoas × 9 situações = 756 prompts gravados fora do git, pelo caminho real (`registrar_mensagem`). Zero ocorrência de CPF, telefone, e-mail, nome, logradouro, conta e ids reais. Falha com menos de 756 arquivos ou arquivo vazio. Execução cabe em F2-48 (F4-035). |
| G-0457 | MÉDIO | Consumo do batimento antes de todo efeito (D-15) | src/ia-atendimento-b1-6a/src/ia_atendimento/worker_vivo.py:86 | Leitor do batimento v2 (ausente, `v ≠ 2`, `seq` que retrocede, > 90 s ⇒ recusa) chamado antes de todo efeito `real\|teste`. Teste por mutação nas idades 59, 75, 89 e 91 s; fail-open reprova. `/readyz` devolve a idade real. |
| G-0532 | MÉDIO | Canário de PII ponta a ponta | src/ia-atendimento/tests/test_vazamento_corpo.py:95 (só corpo ao provedor) | Mesmo canário capturado em stderr, spans exportados, `passo`, `ferramenta_chamada` e `procrastinate_jobs` no PG descartável. Zero ocorrências. Critério de B1.6/B1.7. |
| G-0572 | MÉDIO | Fechamento da entrada quando o provedor recusa (401/402/403/429) | src/ia-atendimento/src/ia_atendimento/agente.py:358 | N falhas `ProvedorIndisponivel` 401/402/403 (ou K seguidas de qualquer status) gravam `bloqueio_entrada=true` e alerta crítico. Teste parametrizado com 401 e 402. |
| G-0380 (RG-098) | BAIXO | Recusa de abertura sem hora do cliente (D-13) | src/ia-atendimento/src/ia_atendimento/api/atendimentos.py:89 | Teste: `iniciar` com `ultimo_cliente_em` nulo ⇒ `abortar(janela_24h)`, nenhum envio. Teste: ≥ 24 h ⇒ idem, sem template de abertura. |
| G-0325 | MÉDIO | Ponta a ponta local da B1.7 | planos/…-01-orquestrador-nucleo.md «Create `tests/test_e2e_local.py`, `docker-compose.dev.yml`» | Os dois arquivos existem. O teste avança o relógio > 24 h antes da auditoria e passa. Sequência B1.6b → B1.7 com data no ROT. |
| G-0216 | MÉDIO | Consumo do batimento, publicador do espelho, repasse em etapas, tarefa das 19:45 | contratos/08:257 «Publicador: job `publicar_espelho`» | Cada peça com dono, data e teste por mutação em que o fail-open reprova. Fecha junto com G-0457, G-0123, G-0078. |
| G-0713 | BAIXO | Uso de `texto_de_saida`, `FontePessoasTeste` e `FixturesDuble` | src/ia-atendimento/src/ia_atendimento/pessoas_teste/prefixo.py:24 | Teste no Canal reprova envio em modo `teste` sem «[TESTE] » e com texto vazio. `test_t1_t3_t5_leem_fixture_so_com_modo_efetivo_teste_ou_duble_sem_posse_real` verde. |
| F4-027 | MÉDIO | Runbook da B1.6a no OPERACAO do ramo | ramo docs/OPERACAO.md: `grep -c` dá 0 para `indeterminado`, `expirar_parados`, `gasto`; DECISOES-B1.6a:14, :31 | Seção no OPERACAO: como achar linhas `indeterminado`, quem decide, como conferir `expirar_parados`, o que fazer com 503 `nao_pronto` por gasto. `grep -c indeterminad docs/OPERACAO.md` ≥ 1. |

#### B3: facta-on (2)

| Id | Sev | Peça ausente | Prova da ausência | Critério de aceite verificável |
|---|---|---|---|---|
| G-0108 (RG-015) | ALTO | Redação do CPF no log das rotas `conferir` e `por-cpf` | src/facta-on/app/routers/online.py:4727 | B3.2 inclui redação em `app/logs.py`. `test_log_app_nao_traz_cpf` verde: grep do CPF sintético no stdout = 0. Até lá, o 05 não afirma «CPF fora de persistência». |
| G-0608 | BAIXO | Peças do facta-on ainda inexistentes | src/facta-on/app/config.py:123 | Critérios de aceite de B3.1, B3.2, B5.4 e A4.8 citam cada peça. Fechadas com teste no PR. |

#### B4: cliente360-api (3)

| Id | Sev | Peça ausente | Prova da ausência | Critério de aceite verificável |
|---|---|---|---|---|
| G-0162, G-0506, G-0604 | MÉDIO, BAIXO, BAIXO | B4.3: rotas `/v1/ia/*`, escopos `ia:monitorar` e `ia:chave`, migração 000025, D-API-77, flags `C360_IA_*` | ROT:968 «só o proxy `GET/PUT /v1/ia/chave` ... flag **off**»; busca por `v1/ia` e `ia_leitura` em src/cliente360-api sem resultado | Migração, `catalogo.py`, `ESCOPOS_FORA_DA_SPEC`, `rotas-status.md` e `test_escopos_ia` no PR. Rotas respondem com a IA desligada; 403 sem papel Admin/TI; «indisponível» com o orquestrador fora. Ponto de corte 11/11: sem B4.3, o #4 sai sem ela. |

#### B5: gateway de ferramentas, roteiro e agenda (6)

| Id | Sev | Peça ausente | Prova da ausência | Critério de aceite verificável |
|---|---|---|---|---|
| G-0058 | ALTO | Caminho da matrícula e medições H1–H3 | ESTUDO-D29-ficha-essencial.md «Ela é obrigatória na digitação (`online.py:4882`)» | `test_matricula_so_no_cofre` verde. `sem_matricula` é a 12ª pré-condição. Contagem agregada H1–H3 anexada ao go/no-go. |
| G-0414 (RS-23) | MÉDIO | T15 e cerca de conteúdo (número por extenso passa) | src/ia-atendimento/src/ia_atendimento/turno.py:137 | T15 barra numerais e moeda por extenso e promessas. Remove caracteres de formato (Cf) antes de validar. Teste: todo valor enviado ao cliente nasce de placeholder resolvido por ferramenta do próprio atendimento. |
| G-0433 | MÉDIO | Leitor de CPF real só por `pessoas_teste` no modo teste | src/ia_atendimento/ferramentas/gateway.py:62 | Em `teste`, leitor responde só por `pessoas_teste`; outro CPF ⇒ DESCONHECIDO. CPF só em corpo, nunca em URL. Teste com CPF-canário cobre log do httpx, span e exceção de cada executor. |
| G-0556 | BAIXO | Cliente do 360, troca de token, executores T1/T2/T3/T10, testes D-29 | src/ia-atendimento/src/ia_atendimento/ferramentas/gateway.py:26 | Executores usam só `destino.url`. Query de `resumos` com `incluir_limite_contratos=true` e sem `incluir_contatos`, provada por teste. Os quatro testes de D-29 e os quatro do 03 §10 verdes. Corpo cru nunca em log. |
| G-0561 | MÉDIO | Contrato de teste das rotas da IA no facta-on | src/facta-on/tests/contrato_ai05.json:2 (outro recorte) | Recorte versionado das duas respostas, usado nos três repositórios. No facta-on, `test_conferir_expoe_status_proposta_af_cancelada` verde. No orquestrador, teste com o modelo do §7. Teste de fidelidade da camada B. |
| G-0702 | BAIXO | Contraproposta e pergunta de ambiguidade da agenda | agendamento.py:9-11 «ambíguo é da proposta/confirmação, B5.7c» | Função pura `proxima_valida(resultado, config)` com casos no corpus; testes verdes na B5.7c. |

#### B6: canal, braço n8n, repasse, espelho, vigia, ntfy (20)

| Id | Sev | Peça ausente | Prova da ausência | Critério de aceite verificável |
|---|---|---|---|---|
| G-0078 (RG-065), G-0440 (RG-065), G-0579 | ALTO, MÉDIO, BAIXO | Repasse forçado das 19:45 (B6.7) | ROT:51 «repasse forçado 19:45 = tarefa periódica do orquestrador, B6.7»; tests/test_agenda_jobs.py:222 (prova parcial) | Tarefa às 19:45 de São Paulo, todos os dias. Todo `aberto` e `aguardando_cliente` sai `repassado` com `motivo_desfecho=fim_do_dia` e nota. `test_repasse_forcado_1945_nao_toca_pausado` verde. Teste com relógio em domingo. Prova no ensaio antes do go/no-go. |
| G-0086, G-0328, G-0421 | ALTO, MÉDIO, MÉDIO | Janela 08–20 e 24 h conferidas no último salto do envio | src/ia-atendimento/src/ia_atendimento/chave.py:250 (só na entrada e no lembrete); contexto.py:426 | O último salto chama `dentro_da_janela` com calendário vigente e relógio injetado. Teste por mutação com 07:59:59, 20:00:00, domingo fechado, feriado e DATAPREV. Texto livre recusado com `janela_24h_aberta` falsa (teste com `ultimo_cliente_em` NULL, 24 h exatas e `datetime_post` atrasado). Uma só função de janela. |
| G-0099 | ALTO | Matriz de alertas no OPERACAO | src/ia-atendimento/docs/OPERACAO.md:192 «geram `alerta ti: contador=…` em WARNING» | Tabela alerta → severidade → destino ntfy → ack em 15 min → ação. Payload sem PII, tópico não adivinhável. Aceite de B6.6. |
| G-0573 | MÉDIO | Publicador ntfy.sh e lista do conteúdo permitido | ROT «o piloto roda no `ntfy.sh` com tópico secreto» | Função única, host constante, tópico em arquivo 0600. Corpo por lista positiva (código, severidade, hora, contagem, ação). `test_alerta_sem_pii` com CPF, telefone, e-mail, UUID e chat sintéticos. Falha de publicação não derruba o turno. |
| G-0311 | MÉDIO | Fonte do ack do alerta com ntfy.sh | j-operacao-piloto.md:228 «Ack = reação ou resposta «ack» no canal, lida pela vigia» | Ack dos 5 alertas críticos gravado em tabela (D-T31), ou repasse automático ao dono em 15 min. Até lá, aceite 7 = «verificado à mão com registro no Kan». |
| G-0123 | ALTO | Publicador orquestrador → n8n e repasse | src/ia-atendimento-b1-6a/src/ia_atendimento/espelho.py:5 | Teste enumera toda transição de estado e exige o evento na mesma transação. Publicador em ordem de `seq`, com os 4 resultados. Repasse com os 7 resultados e teto de 30 min (D-14). Poda não apaga atendimento com evento pendente. Ramo não vai a produção sem o publicador. |
| G-0129 | ALTO | Emissor ao ChatGuru (Canal, nota, assumir, restaurar) | src/ia-atendimento/src/ia_atendimento/jobs.py:125 | Teste de arquitetura: só um módulo importa o cliente do `chatguru-api`. Ordem fixa no último salto: batimento → `modo_efetivo` → janela 08–20 → 24 h → ledger. Os 9 testes do 02 §10 verdes contra o falso. |
| G-0568 | MÉDIO | Identidade fixa do remetente (robô e linha) | src/ia-atendimento/src/ia_atendimento/config.py:115 | Id do robô e `phone_id` permitidos como constante ou allowlist de código. Boot recusa valor fora. `POST /atendimentos` com `phone_id` fora ⇒ 422. Teste: nenhuma env troca o ator. |
| G-0589 | BAIXO | Teste do ator de envio fixo em 85 | ROT:1087 «`POST /pessoas/{id}/atribuicoes` com o ator 85» | `test_ator_de_envio_e_constante_85` verde em B6.8. |
| G-0203 | MÉDIO | View, kit DDL, fluxos, vigia e ensaio S1–S6 do braço n8n | contratos/04:3 «**Nada foi lido nem escrito na S2 nesta etapa**» | S1–S6, a contagem e o EXPLAIN registrados antes da importação dos fluxos. Importação reprovada sem o resultado. |
| G-0237 | MÉDIO | Medições A2.4 e A2.8 e tabela única de credenciais | contratos/04:429 | A2.4 e A2.8 medidas, com arquivo, antes de 11/11. Tabela de credenciais (nome, quem guarda, quem usa) no contrato 04. |
| G-0510 | MÉDIO | Fluxos e kits do braço n8n | kits/gateway/README.md:107 | Export JSON dos três fluxos aprovado pelo validador §9.1 a–h. `node --test` de `n8n/lib` com hash conferido. Credenciais só por nome. `ativar.sh --ensaio` com volta seletiva por rota. |
| G-0597 | BAIXO | Header Auth do n8n e itens do §13 do 01 | contratos/01:236 «credencial criada na tela pelo dono» | Teste prova 401 sem Header Auth no webhook. Fixture de lead de teste e batimento recente. |
| G-0213 | MÉDIO | Vigia da S2 (base do fail-closed de D-15) | contratos/08:224 «e a vigia da S2 continua devolvendo (§7.4)» | Teste ponta a ponta: a vigia derruba o batimento e o orquestrador para de enviar, antes de ligar `ia_ativa`. |
| G-0530, G-0426 (parte B6.7) | MÉDIO | `config/domingo.sh`, `gateway/ativar.sh` e `set.sh` | ROT «kits `s4/migrar.sh`, `config/domingo.sh`, `gateway/ativar.sh` ...»; migrations/README.md:57 | Formato do `chats-teste.sh`: `--ensaio`, `--confirmo`, `versao_esperada`, guarda do valor anterior, desfazer, teste contra API falsa. `domingo.sh` abrir publica `janela_mensagem` com o dia 7 antes de `domingos=false`. Prontos até 15/11 (`domingo.sh`) e 18/11 (`ativar.sh`). |
| G-0545 | MÉDIO | Reconciliador RPA e calibração do casamento webhook × RPA | src/ia-atendimento/src/ia_atendimento/api/eventos.py:167 | Teste ponta a ponta webhook + RPA da mesma mensagem com o atraso medido em A3.1: uma gravação, um turno. `casamento_janela_s` calibrado. Decisão D22 registrada no checkpoint 1. |

#### B7: web e tela da IA (7)

| Id | Sev | Peça ausente | Prova da ausência | Critério de aceite verificável |
|---|---|---|---|---|
| G-0565 | ALTO | Desligamento que fecha abertos em ≤ 20 min (depende da B1.6b) | src/ia-atendimento/src/ia_atendimento/worker.py:52 | Prova em dev contra o orquestrador real em `duble`: depois de desligar, todo `aberto`, `aguardando_cliente` e `pausado` chega a `encerrado` em ≤ 20 min; `reservado` da mesma janela é abortado. `encerrar_por_chave` injetado, com teste que falha se o serviço for `_NaoConfigurado`. Até lá, o #7 não liga `PAINEL_IA_C360` em produção. |
| G-0610 | BAIXO | Tela, BFF, flag, timer, emergência e ntfy do web | contratos/07 «B7.1 cria a instância do timer existente» | Critérios de aceite de B7.1 e do #7. Até o ntfy existir, o texto do diálogo traz um destino alternativo. |
| G-0297, G-0304 | BAIXO, MÉDIO | Rotas das seções F1/F2 da tela e peças do §6 nos contratos 03/08 | TELA-IA-C360.md «via rota PROPOSTA `GET /v1/ia/visao-geral`»; :1137 enum `efeito` «(v2) lido do orquestrador» | Pedidos IA-xx abertos nos contratos 03/08 antes de o módulo entrar no F1. `detalhe.origem` (enum fechado) no 03 §5.3, ou §6.5 reduzido ao que o contrato dá. |
| G-0305, G-0645 | MÉDIO, BAIXO | Papel `ia_leitura_painel` com ACL por coluna; ack obrigatório; pedidos IA-ORQ-* | src/ia-atendimento/migrations/0001_esquema.up.sql:443; kits/s4/s4-papeis.sh:41 | Migração cria `ia_leitura_painel` com GRANT por coluna. Varredura usa `has_column_privilege` e reprova coluna de PII legível. `s4-papeis.sh` cria o papel. |
| G-0299 | MÉDIO | Script de RT-16 e leituras da sombra (B7.2) | TELA-IA-C360.md:797 «ficha de domingo 20:15 (`D18:93`) + script B7.2» | Escopo de RT-16 no B7.2 com dono e aceite, ou a espec marca «à mão». |

#### B8: avaliação F3 (2)

| Id | Sev | Peça ausente | Prova da ausência | Critério de aceite verificável |
|---|---|---|---|---|
| G-0445 | MÉDIO | Corpus com domingo aberto (B8.1c) | src/ia-atendimento/src/ia_atendimento/corpus/calendario.py:5 | Parâmetro de calendário no `Corpus`/`validar`; regras o usam; diálogos de domingo aberto no corpus; validador verde. |
| G-0446 | BAIXO | Harness de medição B8.1b | src/ia-atendimento/src/ia_atendimento/roteiro_f3.py:110 | Harness com reset por execução e verificação dos tokens proibidos. Até lá, a F3 não conta como medição. |

#### B9 a B12: sombra, go/no-go, piloto e depois (6)

| Id | Sev | Peça ausente | Prova da ausência | Critério de aceite verificável |
|---|---|---|---|---|
| G-0023 | ALTO | Comando de parada dura, prazo de decisão e responsável noturno | ROT:1183 «parada dura (`modo=sombra`; (v3) vale para o atendimento já aberto» | `config/parar-duro.sh` (PUT `modo=sombra` + conferência de que nada sai em ≤ 5 s) e `config/religar.sh` ensaiados. B11.3 diz quem decide cada gatilho, em quantos minutos, e o substituto com token `ti`. Critério de B6.7/B9.0. |
| G-0627 | BAIXO | Peças exigidas por J e K | k-devolucao-lead-cenarios.md:166 «Vigia: timer systemd na S2 (60 s, Python stdlib» | Checklist de 25/11 com ensaio cronometrado: `devolver-leads` ≤ 30 min; chave off com 3 abertos ≤ 20 min. |
| G-0629 | BAIXO | TX-01T, view e descarte | ROT:813 «TX-01T inativo (N-4: só dentro de 24 h)» | Relatório da sombra com a fração de abortos `janela_24h` por ramo, antes de qualquer pedido de template à Meta. |
| G-0294 | BAIXO | Gatilho fora do horário como premissa confirmada | ROT:117 «Mecanismo **novo**: um timer do chatbot aciona o Amado» | B10.1 registra que o gatilho está fora do MVP; comunicação ao superior em A1.11. |
| G-0285 | BAIXO | Chave de desligamento do juiz (camada 2) | l-motor-qualidade.md «camada 2 ... entra depois do piloto» | `juiz_ativo=false` por padrão, allowlist de host igual à de RS-01, sem fallback. L §7 marcado superado pelo corte C3. |
| G-0660 | BAIXO | Janela DATAPREV recorrente | src/canario-4/src/ia_atendimento/calendario.py:26-27 | Pós-piloto (B12.2): janelas geradas por regra (dia 20 22:00 a 23 06:00) com exceções oficiais sobrepostas, como no JSON do 04 §8. |

#### Parte F do roteiro (2)

| Id | Sev | Peça ausente | Prova da ausência | Critério de aceite verificável |
|---|---|---|---|---|
| G-0292 | BAIXO | Estado honesto nas resoluções «aplicado» que cobrem peças inexistentes (B6.7, B6.8, B6.4) | ROT:1572 «Aplicado = só o texto do roteiro: nenhum merge, push» | Cada linha diz «texto aplicado; código pendente (B6.x)» e aponta o critério de aceite da etapa. Fecha junto com G-0029. |
| G-0594 | BAIXO | Ponteiro da Parte F e do Anexo X para a revisão 0911 | ROT:1718 (última linha da Parte F, 04/11) | Linha nova na Parte F aponta para `estudos/REVISAO-GERAL-0911.md` (PLANO Fase 5). `grep -n 0911 ROT` acha. |

### 6.6 O que destes itens depende do dono

Estes itens não fecham só com texto. Precisam de decisão escrita. A data-limite vem das fontes; onde a fonte não dá, a coluna diz «não verificado».

| Ids | Decisão | Limite | Fonte do limite |
|---|---|---|---|
| G-0079, G-0172, G-0174 | Aceitar ou derrubar o degrau de 1 dia (piloto 27–30/11), rampa de 4 dias e regra X7 | checkpoint de 11/11 | nota de G-0079; ROT:1297 |
| G-0009, G-0024 | Go sem medição de custo e latência | 17/11 (dia da chave) | ROT:1238 |
| G-0005, G-0026, G-0531 | Via de D-32 para o texto mascarado; conteúdo no span do Phoenix | 18/11 (G2) | nota de G-0005; ROT:1272 |
| G-0387 | Go/no-go com ou sem amostra revisada | 11/11 (revisor nomeado) | ROT:498 |
| G-0043 | Tolerância de ajuste de valor e seguro na T7 | não verificado | sem data nas fontes |
| G-0047 | Limite da máscara (nascimento, agência, conta, nome) | não verificado | sem data nas fontes |
| G-0007, G-0027 | Quais atos de 09/11 e 10/11 aconteceram | antes de qualquer `!` | PLANO §7.1 (pergunta fechada) |
| G-0001, G-0260, G-0385 | VPS, DPA/ZDR, rotação das chaves expostas | VPS 12/11 14:00; chaves 02/12 | PLANO §7b; ROT (A1.8) |
| F4-036 | Rodar gitleaks no histórico (sonda S24) e piiscan (S23) | antes da Fase 5 fechar | correção de F4-036 |

---

## 7. Matriz de restrições com estado final, livro de retenção e inventário de segredos

Das 34 restrições (RS-01..RS-34), nenhuma está sem achado vivo: 34 têm achado verificado vivo. Só RS-02 conta como ATENDIDA pelo critério do §7.0, porque só tem BAIXO. Além disso, 23 têm ALTO confirmado, 25 têm grupo «não existe» e 395 dos 762 grupos citam ao menos uma RS. O livro tem 21 armazéns (6 com poda em código, 7 inexistentes, 5 só verificáveis em produção). O inventário tem 15 segredos (nenhum valor achado em git; 7 sem rotação em vigor).

### 7.0 Como ler

- **Fontes do estado.** Grupos da Fase 3 (`fase3/consolidado.json`, campo `rs`), achados da Fase 4 (`fase4/consolidado-f4.json`, `consolidado-r2.json`), leituras F2 e a matriz inicial (`fase0/matriz-restricoes.md`). Contagens saem do campo `rs` normalizado.
- **Estados.** `ATENDIDA` = prova em código ou teste lido, sem achado vivo acima de BAIXO. `VIOLADA (gravidade)` = há grupo confirmado ou confirmado em parte; a gravidade é a do pior. `NÃO EXISTE` = peça ausente; vira critério de aceite do bloco. `NÃO VERIFICÁVEL` = depende de produção; segue a sonda só-leitura.
- **Ressalva de método.** Nenhuma prova aqui é «provado em ensaio»: as unidades de execução F2-47 (kits) e F2-48 nunca rodaram (F4-035). Depois disso a suíte do `ia-atendimento` rodou 2× (`fase4/check-x2.out`: «3429 passed, 1 skipped, 1 xfailed»). Ensaio dos kits: não verificado.
- **Sondas.** O id que vale é `SO-nn` (§9b). Os números «S1..S27» na matriz são os de `fase4/completude.md` §5; a coluna «Origem» do §9b dá o SO equivalente (ex.: S1 = SO-02, S4 = SO-13, S8 = SO-12, S11 e S12 = SO-19). Quem roda: a sessão principal, por script; o dono com `!` só quando o classificador barrar (§9b, regra 3). Todas devolvem só nome, contagem, modo ou data.
- **Prova principal de cada id** está no Anexo B (gerado dos arquivos de grupo). Na matriz, o id basta.
- **Coluna `g/v/A/M/B/NE`:** grupos que citam a RS / vivos / ALTO vivos / MÉDIO vivos / BAIXO vivos / «não existe».

### 7.1 Matriz RS-01..RS-34

| RS | Regra | Estado final | Atendida com prova (parte) | Violada: ids | Não existe: critério de aceite (ids) | Não verificável: sonda | g/v/A/M/B/NE |
|---|---|---|---|---|---|---|---|
| RS-01 | Modelo só em `us.api.fireworks.ai` + roteador `-us` | VIOLADA (ALTO) | Validador de host e roteador no boot: `IA/src/ia_atendimento/config.py:27` (`HOSTS_DO_MODELO`), `:239-240` (recusa), `:43` (sufixo `-us`) (completude §2; F2b-08) | ALTO G-0016; MÉDIO G-0416 (loopback contorna), G-0480 (sem trava de proxy/redirecionamento), G-0569, G-0397 | G-0001, G-0013 (ALTO): VPS e egress. Critério: chain `output` com allowlist (Fireworks US, S4 `:5434`, S2, DNS, ntfy, registry da S3 por F2-22:143) e `curl` recusado fora dela. G-0260: DPA/ZDR | Região da resposta: G-0761 (risco aceito). Sonda: depois da VPS, `nft list ruleset` + `curl` a host fora da lista | 13/8/1/4/3/4 |
| RS-02 | Nada da Anthropic; nunca a API oficial da DeepSeek | ATENDIDA com 6 BAIXO | `config.py:31` `DOMINIOS_PROIBIDOS`; grep sem SDK proibido em 5 locks, `src` e fixtures (F2-25:134); nenhum 2º campo de provedor (F2b-08) | só BAIXO: G-0334 (simulador com outros provedores), G-0386 (`gemini-*` aceito), G-0730 | — (T15/juiz: ver RS-33) | — | 6/6/0/0/6/0 |
| RS-03 | CPF nunca a modelo, prompt, log, span, banco da IA, ntfy, Kan, payload | VIOLADA (ALTO) | Sumidouros do orquestrador sem CPF por leitura: `passo`, `atendimento`, `procrastinate_jobs.args` (só ids), resposta HTTP, log da API (`tests/test_contrato_api.py:656-683`) (F2-39 tabela) | ALTO G-0085 (máscara de log sem chamador), G-0062; MÉDIO G-0101, G-0508, G-0569, G-0452, G-0313, R2-016; R2-001 (máscara derruba turno) | G-0108 (ALTO, CPF no log do facta-on; B3.1/B3.2), G-0532 (canário ponta a ponta), G-0573 (ntfy, B6.6), G-0242, G-0423 | Decisão do dono: G-0384, G-0482 (abertos); G-0420 (risco aceito em parte). Sondas S8, S11 | 24/15/2/7/6/5 |
| RS-04 | CPF só em memória do gateway de ferramentas, só durante a chamada | VIOLADA (MÉDIO) | CPF só nos frames `_preparar_disparo`/`_rodar`; fora de `Pedido`, `Resultado`, registro, span, log (F2-12:19, :118). Refutados G-0261, G-0265 | MÉDIO G-0152, R2-017 (mutação sobrevive) | G-0433 (leitor real; `duble` sem garantia de pessoa sintética), G-0028. Critério B5.2, B1.6, B5.4 | — (VPS não existe) | 6/2/0/1/1/2 |
| RS-05 | AES-256-GCM, AAD completa, chave por mês, hosts distintos, descarte | VIOLADA (ALTO) | Cifra, AAD e arquivo 0600 por leitura + testes (F2-05 itens 2, 6, 9) | ALTO G-0084 (virada de mês exige troca e reinício), G-0097 (DEPLOY 640 × código 0600); MÉDIO G-0041, G-0400 | G-0401 (descarte sem kit; «dia 31» ambíguo), G-0323. Critério: kit de descarte com prova (`ChaveDesconhecida`), data ≥ fim do mês + 30 d (F2-05:21) | Hosts distintos: `stat -c '%a %U' /etc/ia-s4/conversa.keys` na VPS + `docker inspect` (mount `ro`) (matriz l.135); S19 | 9/7/2/2/3/2 |
| RS-06 | Livro de retenção por armazém | VIOLADA (ALTO) | Poda em código: `fn_texto_podar`, `fn_atendimento_podar`, `podar_jobs` (F2-17 §4; F2-02 §4; F2-03:39). Detalhe em 7.2 | ALTO G-0005 (D-32); MÉDIO G-0271, G-0395, G-0245, G-0448, G-0449, G-0450, G-0542, G-0508, G-0026, R2-015 | G-0039; espelho S2 (G-0203, ver RS-30) | G-0246 (aberto). Sondas S11, S12, S15, S16 | 18/15/1/9/5/1 |
| RS-07 | Inventário de segredos | VIOLADA (ALTO) | `SecretStr`, `repr=False`, `compare_digest` (F2-04 §6; F2-05 item 9; F2-07:29-30). Detalhe em 7.3 | ALTO G-0016, G-0097; MÉDIO G-0405, G-0466, G-0481, G-0513, G-0546, G-0574, G-0113, G-0374; BAIXO R2-023 | G-0385 (RG-108, rotação após o piloto), G-0762, G-0750 | Onde os valores moram: S2, S19, S20, S21 | 18/15/2/8/5/2 |
| RS-08 | Escrita em produção só por kit com ensaio, contagem e desfazer (PD-2) | VIOLADA (ALTO) | Só leitura: `chats-teste.sh` com ensaio e contagem (F2 kits). Nenhum ensaio rodado (F4-035) | ALTO G-0008, G-0011, G-0015, G-0079, G-0095, F4-035; MÉDIO G-0110, G-0112, G-0465, G-0474, G-0477, F4-021, F4-022, F4-030 | G-0012 (ALTO, `s4/migrar.sh`), G-0464, G-0530 (`domingo.sh`, `ativar.sh`), F4-023. Critério A4.6, B6.1, B6.7 | Kit vivo = manifesto: `sha256sum` da cópia em uso × `fase0/MANIFESTO.md` (G-0112) | 40/37/5/20/12/3 |
| RS-09 | Janela 08–20 h, domingo por duas chaves, feriado, DATAPREV | VIOLADA (ALTO) | Fim exclusivo às 20:00 (F2-11:125); bloqueio DATAPREV de entrada (F2-11:68) | ALTO G-0063; MÉDIO G-0349, G-0424, G-0427, G-0566 | G-0086 (ALTO, janela só na entrada e no lembrete), G-0328, G-0426, G-0660. Critério: teste no último salto às 07:59/20:00/domingo/feriado/DATAPREV, por mutação (matriz l.218) | — | 14/9/1/4/4/4 |
| RS-10 | T7 em dúvida nunca se repete | VIOLADA (ALTO) | Nenhuma na main | ALTO G-0087, G-0127, G-0131, G-0016; MÉDIO G-0116, G-0447, G-0455, G-0503, G-0559, G-0105, G-0044, G-0355, G-0557, G-0558, R2-008, R2-009, R2-010, R2-013 | G-0066, G-0089, G-0115 (ALTO), G-0299, G-0561. Critério B1.6a + B1.6b + B5.4; janela de 20 min no facta-on (B3.2) | S7 (`FACTAON_CONFERIR_JANELA_MIN`) | 26/19/4/12/3/6 |
| RS-11 | D-15: sem batimento recente a IA não age | VIOLADA (ALTO, papel) e NÃO EXISTE em código | Nenhuma | ALTO G-0020, G-0022, G-0032, G-0063, G-0074; MÉDIO G-0080, G-0164, G-0204, G-0214, G-0233 | G-0216, G-0457, G-0579. Critério B1.6b (consumo), B6.4 (produtor), B6.8, B6.6 | — até existir | 13/10/5/5/0/3 |
| RS-12 | Papéis e `pg_hba` (alínea v) | VIOLADA (MÉDIO) | `ia_app` sem CREATE; privilégio por catálogo em `test_esquema.py:151-185` com controle negativo (F2-17:96) | MÉDIO G-0049, G-0274, G-0523, G-0574, G-0575, G-0576, G-0040, F4-030 | G-0645 | S17, S18 | 18/16/0/7/9/1 |
| RS-13 | Segredos e PII em repositório | VIOLADA (ALTO) | `gitleaks dir`: 0 em 7 alvos, 3 falsos positivos no facta-on (`fase0/baseline.md` tabela a); histórico de 5 repos: «Nenhum segredo real» (`fase4/historico-pii.md:15`) | ALTO G-0118 (29 CPF de DV válido não públicos ainda na main do facta-on, `historico-pii.md:24-26`), G-0085, F4-036; MÉDIO G-0470, G-0472, G-0485, G-0486, G-0501; BAIXO F4-020 | — | G-0471 (aberto). S22 (push protection), S23. 6º repositório sem linha no histórico: não verificado | 13/12/2/5/5/0 |
| RS-14 | Canal de teste não alcança o real | VIOLADA (ALTO) | `_regra_do_canal_de_teste` barra `chatguru-ia-teste` fora de `chats_teste` ou com modo ≠ teste (F2-08:29-40) | ALTO G-0005; MÉDIO G-0014, G-0508, G-0188, G-0441 | G-0713 | Diálogos do ChatGuru que apontam a `ia-sumidouro`/`ia-mensagem` com a credencial de teste (matriz l.295) | 12/11/1/4/6/1 |
| RS-15 | Flags e sementes `FACTAON_*` | VIOLADA (ALTO) | Nenhuma registrada | ALTO G-0017, G-0106; MÉDIO G-0497, G-0499 | G-0108 (tap, B3.1) | `printenv \| grep -c '^FACTAON_'` (só nomes) + S7 | 10/9/2/2/5/1 |
| RS-16 | PD-6: `hide_input_in_errors` e scrubber | VIOLADA (ALTO) | `config.py:78` `hide_input_in_errors=True`, `:276` `errors(include_input=False)` (completude §2); pacote do gateway todo `Fechado` (F2-12:120) | ALTO G-0085; MÉDIO G-0402; BAIXO G-0580, G-0689, G-0700, G-0710, G-0714 | — | — | 7/7/1/1/5/0 |
| RS-17 | F07: nenhum corpo de evento em log, span, traceback ou resposta | VIOLADA (ALTO) | Log da API sem corpo: `tests/test_contrato_api.py:656-683` (F2-39; F2-27:31) | ALTO G-0085; MÉDIO G-0531 (span exporta conteúdo), G-0402, G-0033, G-0239 | G-0108 (ALTO, facta-on); n8n do braço (B6.2) | nginx do vhost WG: `nginx -T \| grep -A3 ia_semquery` (matriz l.339) | 8/7/1/4/2/1 |
| RS-18 | Orquestrador só sobe por tag `v*` | VIOLADA (ALTO) | Nenhuma: a esteira não constrói a main | ALTO G-0016, G-0094, F4-016; MÉDIO G-0467 (tag mutável), G-0468, G-0469, F4-018; BAIXO F4-019 | Na main e em produção (A6.6b, A4.9, B1.7) | Coolify: tipo de build, auto-deploy, `image:tag` do contêiner (matriz l.354) | 5/5/2/3/0/0 |
| RS-19 | Modo teste, `duble`, `sombra` nunca alcançam a FACTA real | VIOLADA (ALTO) | FACTA em `duble`/`sombra` por leitura (F2b-05:161) | ALTO G-0126; MÉDIO G-0107, G-0428, R2-011, R2-012; BAIXO R2-014 | Executores T7/T8/T9 (B5.4). Critério: executor usa só `destino.url` | G-0442 (risco aceito em parte). Valores vivos das bases: VPS não existe; S25 | 9/7/1/2/4/0 |
| RS-20 | MVP: só a FACTA digita | VIOLADA (ALTO) | Constante ∩ flag (F2-12:122) | ALTO G-0088 (T5 de 3RN/C6 vai à produção em sombra); MÉDIO G-0046 | Executor de T7 e entrada E0 (B5.4, B5.5, B6.2; matriz l.383) | — | 5/5/1/1/3/0 |
| RS-21 | Texto, telefone, nome, e-mail do cliente só na trilha cifrada | VIOLADA (ALTO) | Texto em claro fora de `conversa_cifrada`/cofre: não achado (F2-02:18) | ALTO G-0047, G-0114 (`nomes=()` fixo); MÉDIO G-0287, G-0303, R2-015, R2-005; F4-031 (nome de consultor, não de cliente) | G-0305 (papel `ia_leitura_painel`) | — | 10/8/2/2/4/1 |
| RS-22 | IA nasce desligada e em `duble`; quem pode ligar | VIOLADA (ALTO) | `garantir_defaults` só grava chave ausente (`chave.py:143-150`; F2b-06:129); `c360_api` não alcança outra chave (`test_api_config_agenda.py:63-69`) | ALTO G-0022; MÉDIO G-0128, G-0230, G-0231, G-0300, G-0562, R2-011, R2-012 | G-0023 (ALTO, parada dura sem comando), G-0304 | Estado vivo: banco ainda sem migração (matriz l.408) | 18/16/1/5/10/2 |
| RS-23 | Valor sem ferramenta nunca vai ao cliente; texto sensível é fixo | VIOLADA (MÉDIO) e NÃO EXISTE (ALTO) | `Turno.texto` ≤ 320, sem dígito, `R$`, link, «aprovado» (`turno.py:130-150`; F2-09:61) | MÉDIO G-0268, G-0367, G-0417, G-0418, G-0419, R2-004; BAIXO R2-006 | G-0072, G-0073 (ALTO, textos fixos e TX-42), G-0414. Critério B5.5, A7.2 | — | 8/5/0/5/0/3 |
| RS-24 | Texto livre só até 24 h da última mensagem do cliente | VIOLADA (MÉDIO) | `ultimo_cliente_em` só avança e é limitado ao recebimento (F2-08:55) | MÉDIO G-0048, G-0438 | G-0421 (bloqueio no envio), G-0237, G-0380. Critério B6.8/B1.6b | — | 8/5/0/2/3/3 |
| RS-25 | Nenhum lead dorme com a IA; 20:15 grava `bloqueio_entrada` | VIOLADA (ALTO) | Tarefa `bloqueio_2015` pelo tick (F2-11:77); o código não grava `ia_ativa=false` (G-0050, nota) | ALTO G-0016, G-0032, G-0050, G-0131; MÉDIO G-0080, G-0082 (lease até 96 h), G-0093, G-0315, G-0393, G-0034 | G-0023, G-0091, G-0123, G-0565 (ALTO), G-0389, G-0396, G-0440, G-0627. Critério B6.7 + B1.6b | — | 20/12/4/6/2/8 |
| RS-26 | Teto financeiro e parada dura | VIOLADA (MÉDIO) e NÃO EXISTE (ALTO) | `ErroDoModelo.uso` soma as respostas (`agente.py:325-331`; `test_agente.py:444-465`) | MÉDIO G-0064, G-0117, G-0399, G-0411, G-0412, G-0458, G-0570, G-0024 | G-0083 (ALTO, parada por gasto), G-0572 | Cap na conta Fireworks: tela de billing (A1.4) | 16/14/0/8/6/2 |
| RS-27 | Merge = deploy; janela; `main` protegida; web antes da API | VIOLADA (ALTO) | Nenhuma | ALTO G-0004, G-0017, G-0070, G-0096; MÉDIO G-0018, G-0030, G-0484, G-0504, G-0515 | — | G-0667 (risco aceito). S4, S5, S6. `cliente360-web` fora da exportação | 16/14/4/5/5/0 |
| RS-28 | Alerta só por ntfy; fluxo antigo não se usa | VIOLADA (MÉDIO) e NÃO EXISTE (ALTO) | Ausência de Discord/fluxo antigo: não verificado nas fontes | MÉDIO G-0052 (tópico forjável), G-0279 | G-0099 (ALTO, matriz de alertas), G-0311, G-0573. Critério B6.6 | — | 5/3/0/2/1/2 |
| RS-29 | Só APIs da GL; do 360 só o essencial (D-29) | VIOLADA (ALTO) | 4 serviços de fora, saída por allowlist, contatos descartados (F2-12:123) | ALTO G-0121, G-0124; MÉDIO G-0033, G-0507, G-0552, G-0555 | G-0058 (ALTO, matrícula), G-0556. Critério B4.1 | G-0348 (aberto), G-0217 (risco aceito em parte). Credencial no `c360-auth` após B4.1 | 11/6/2/4/0/2 |
| RS-30 | n8n: nenhum PII em `execution_data` | VIOLADA (MÉDIO) | Sumidouro: `saveData*: none`, progresso e manual desligados (F2-34:14; `KITS/gateway/ia-sumidouro.workflow.json:39-42`) | MÉDIO G-0195, G-0508 | G-0203, G-0510 (braço) | G-0748 (risco aceito). S13 | 11/7/0/2/5/2 |
| RS-31 | Fixture da forma medida; dado real nunca no repo | VIOLADA (MÉDIO) | Gerador de pessoas determinístico (F2-29) | MÉDIO G-0102, G-0103, G-0443, G-0492, G-0501, F4-033; BAIXO F4-006, F4-020, F4-032, F4-034 | — | G-0471 (aberto); G-0491, G-0738 (risco aceito em parte). S25, S27 | 15/11/0/5/6/0 |
| RS-32 | Envio só como ator 85; nota de repasse única e curta | VIOLADA (ALTO) e NÃO EXISTE (ALTO) | Nenhuma | ALTO G-0037; MÉDIO G-0130, G-0224, G-0455, G-0567 | G-0036, G-0129 (ALTO), G-0568, G-0589. Critério B6.8, B6.3 | G-0226 (risco aceito em parte) | 10/5/1/4/0/4 |
| RS-33 | T15 e juiz nascem desligados; reserva = repasse | VIOLADA (MÉDIO) | Nenhum 2º campo de provedor em `config.py` (F2b-08) | MÉDIO G-0570 | G-0285. Critério: mesma allowlist de RS-01, flag off, sem fallback | — | 2/1/0/1/0/1 |
| RS-34 | Phoenix só por túnel SSH no tailnet (D-30) | VIOLADA (MÉDIO) | Nenhuma | MÉDIO G-0067, G-0569 | A4.5 | G-0329 (risco aceito em parte). `ss -ltnp` na VPS e ausência de hostname público (matriz l.490) | 3/2/0/2/0/0 |

**Leitura rápida.**
- RS sem nenhum ALTO (vivo ou «não existe»): RS-02, RS-04, RS-12, RS-24, RS-30, RS-31, RS-33, RS-34.
- ALTO que cruza mais RS: G-0016 (RS-01, 07, 10, 18, 25) e G-0085 (RS-03, 13, 16, 17).
- Peça que não existe e pesa mais: B1.6b inteira (G-0066), ligação do ledger ao gateway (G-0089, G-0115), emissor ao ChatGuru (G-0129), VPS (G-0001).

### 7.2 Livro de retenção

Pior caso = o que sobra se o processo para ou o dado foge do caminho feliz. «Em código» = existe e foi lido; nenhuma poda rodou em produção (o banco da IA ainda não tem migração, matriz l.408).

| # | Armazém | Dado sensível | Origem do relógio | Mecanismo de descarte | Estado | Pior caso | Ids e prova |
|---|---|---|---|---|---|---|---|
| R-01 | `ia.conversa_cifrada` (S4) | texto mascarado, cifrado | `encerrado_em` + 14 d, ou `apagar_em` ≤ `criada_em` + 30 d (CHECK) | `fn_texto_podar` no job `podar` 03:30 (`jobs.py:382-388`; `fila.py:179-181,214`) | Em código | Worker parado = nada apagado; `criada_em` gravado livre pelo `ia_app`; `fn_texto_podar(7,1,1)` apaga cedo | G-0245, G-0395, G-0448; F2-17:47, :56 |
| R-02 | `ia.cofre` (S4) | número do chat (`canal`), dados de digitação | `encerrado_em` + 1 d, ou `expira_em` ≤ `criado_em` + 7 d | `fn_texto_podar`; `cofre.expirar` sem chamador | Em código | `ia_app` tem UPDATE na linha inteira (`criado_em`, `expira_em`) | G-0049; F2-02:50; F2-17:57 |
| R-03 | `ia.atendimento`, `passo`, `agendamento`, `ferramenta_chamada`, `confirmacao`, `atendimento_resultado`, `qualidade_*` | códigos, HMAC, tamanho; anotação com nome em claro | `encerrado_em` + 365 d (só `encerrado`) | `fn_atendimento_podar` (`0001:404-419`) | Em código, com defeitos | Atendimento que nunca encerra fica para sempre; FK cruzada trava a poda e pula `podar_jobs`; poda quadrática | G-0271, G-0449, G-0450, G-0452, R2-015; F2-17:58 |
| R-04 | `ia.candidato` | `chat_ref` (HMAC), `perfil` jsonb livre | `apresentado_em` + 365 d | `fn_atendimento_podar` (`0001:414`) | Em código | `perfil` livre sem CHECK de forma | F2-17:59, :85 |
| R-05 | `ia.espelho_evento` | códigos; CHECK aceita 11 dígitos | nenhum próprio (cascata do atendimento) | só `ON DELETE CASCADE` | Sem poda própria; sem produtor | Vive com o atendimento (365 d ou para sempre) | F2-18:36, :39, :77 |
| R-06 | `ia.opt_out` | identificador de supressão | nenhum | nenhum (lista de supressão) | Por desenho | Para sempre | F2-17 §4 tabela |
| R-07 | `ia.config_versao`, `artefato_versao`, `migracao` | `motivo` em texto livre | nenhum | nenhum | Sem descarte | Nome de cliente digitado no `motivo` fica para sempre | G-0303, G-0313; F2-17 §4 tabela |
| R-08 | `procrastinate_jobs`/`events`/`periodic_defers` (S4) | só ids nos `args` | concluídos 7 d, falhos 30 d, órfãos 30 d | `podar_jobs` (`jobs.py:346-379`) | Em código | `todo`/`doing` nunca saem; falha da poda de 365 d pula esta | F2-03:39; F2-39 tabela; G-0449 |
| R-09 | Chaves AES mensais (`conversa.keys`, VPS) | chave que decifra R-01 | mês da chave | `shred` da linha (só papel) | NÃO EXISTE | Sem descarte, o texto cifrado de R-01 nos backups segue legível | G-0401, G-0323, G-0084; F2-05:12, :21 |
| R-10 | Phoenix `ia_obs` (VPS) | spans com conteúdo mascarado | 14 d (papel) | nenhum código na exportação | NÃO VERIFICÁVEL; bloqueia G2 (D-32) | Spans exportados por padrão, sem prova de eliminação | G-0005, G-0531, G-0569; sonda S16 |
| R-11 | pgBackRest, WAL, dump (S4) | cópia de R-01..R-08 e de `ia_obs` | política de fulls | `pgbackrest expire` (não lido) | NÃO VERIFICÁVEL | Texto mascarado do Phoenix sobrevive nos fulls | G-0005, G-0026, G-0329; sonda S15 |
| R-12 | `gateway.payloads` (S2) | Post do ChatGuru; no `ia-sumidouro`, o corpo inteiro com PII | `recebida_em` + 7 d (papel) | expurgo fora do repositório do gateway | NÃO VERIFICÁVEL; sem código | Ninguém apaga: Post com CPF guardado sem prazo | G-0542, G-0508, G-0014, G-0482, G-0734; sondas S11, S12 |
| R-13 | Espelho S2 `ia_espelho.sob_ia` | `chat_number` | ≤ 30 d / linha terminal (papel) | nenhum artefato | NÃO EXISTE | SELECT direto expõe `chat_number` aos dois papéis | G-0203, G-0195 |
| R-14 | n8n `execution_data` (sumidouro) | corpo do Post durante a execução | fim da execução | `saveData*: none` | Em JSON; vivo NÃO VERIFICÁVEL | Processo cai no meio: corpo fica até a poda do n8n (336 h, HIPÓTESE) | F2-34:14, :31; sonda S13 |
| R-15 | n8n do braço, repasse, agendar | — | — | — | NÃO EXISTE | — | G-0510 |
| R-16 | ntfy.sh (terceiro) | alerta | política do provedor | — | NÃO EXISTE | Link de chat postado em tópico público | G-0573, G-0279, G-0052 |
| R-17 | Logs de contêiner (VPS) | log do app; terceiros sem máscara | tamanho, não tempo | `json-file`, `max-size: 10m`, `max-file: 3` (`EST/docker-compose.yml:37-41`) | Em código (esteira) | Pouco tráfego = log antigo sem prazo; loggers de terceiros sem máscara | G-0085 |
| R-18 | Log do facta-on (S2) | CPF na query de `conferir`/`por-cpf` | rotação do Docker (não lida) | nenhum filtro na main | NÃO EXISTE (filtro) | CPF em log até a rotação | G-0108; sonda S8 |
| R-19 | `$SEGREDOS_DIR` do kit do gateway (S3) | cópias de credenciais e da chave HMAC | «depois do piloto» (comentário) | nenhum passo de apagar | NÃO EXISTE | Cópias ficam na S3 sem prazo | G-0750; `KITS/gateway/env-gateway.sh:27` |
| R-20 | `~/ia-corpus` | corpus bruto de conversas | gatilho por estado (D-31) | manual | NÃO VERIFICÁVEL por agente | Corpus bruto sem apagar | sonda S27 |
| R-21 | `~/ia-revisao-0911/` (esta pasta) | exportação inclui `src/facta-on` com CPF de DV válido não público | nenhum escrito | nenhum | NÃO EXISTE (prazo não escrito) | A cópia dos CPFs de G-0118 vive aqui sem prazo | PLANO-REVISAO-0911.md:158; `historico-pii.md:24-26`. Prazo: decisão do dono |

Contagem: 6 com poda em código (R-01, R-02, R-03, R-04, R-08, R-17); 7 inexistentes (R-09, R-13, R-15, R-16, R-18, R-19, R-21); 5 só verificáveis em produção (R-10, R-11, R-12, R-14, R-20); 3 sem descarte próprio por desenho (R-05, R-06, R-07).

### 7.3 Inventário de segredos (sem valores)

Prova de ausência em git, comum a todas as linhas: `gitleaks dir` na exportação deu 0 em 7 alvos e 3 falsos positivos no facta-on (`fase0/baseline.md` tabela a). `gitleaks` no histórico de todas as refs deu «Nenhum segredo real» em 5 repositórios (`fase4/historico-pii.md:5-15`). O 6º repositório citado em F4-036 não tem linha: não verificado. Ausência em Kan e em log de produção: não verificado.

| # | Segredo (nome) | Onde mora | Quem lê | Rotação | O que um vazamento permite | Ids e prova |
|---|---|---|---|---|---|---|
| K-01 | `DATABASE_URL` (senha do `ia_app_a`) | Variável secreta do Coolify S2 e backups dele; arquivo `.senha` em `/etc/ia-s4` (0640, root:10001); saída do kit fora da S4 | API e worker; `provar.sh` lê o `.senha`; Phoenix monta o diretório | Reserva `ia_app_b` sem senha nem kit | Conectar como `ia_app` (só de `10.90.0.5`, `hostssl`): UPDATE em tabelas inteiras, DELETE em `procrastinate` | G-0113, G-0762, G-0574, G-0041, G-0049; F2b-09:49-51; F2-22:42 |
| K-02 | `MODELO_API_KEY_1` | Variável do Coolify S2 → `environment:` do compose; `docker inspect`, `/proc/<pid>/environ` na VPS | `agente.py` (cabeçalho `Authorization`) | Não escrita | Gasto na conta do provedor; cap do provedor não verificado (RS-26) | F2-22:42; F2b-08:21 |
| K-03 | `API_TOKENS` (um por origem: `ti`, `c360_api`, `n8n_braco`, `vigia`) | Variável secreta do Coolify | API (`auth.py:46-50`, SHA-256 + `compare_digest`) | Um token por origem, sem sobreposição | `ti`: liga `modo=real` com dois PUT e injeta mensagem «do cliente» em qualquer chat. `c360_api`: grava `modo` | G-0405, G-0128; F2-07:29, :53, :55 |
| K-04 | `CHAVE_H16`, `CHAVE_FINGERPRINT`, `CHAT_REF_CHAVE` | Variáveis secretas do Coolify e backups dele | API e worker (HMAC) | Permanentes, sem descarte (RG-109) | Recalcular os HMAC e testar palpites, ligando `chat_ref` e fingerprint a um chat (inferência) | F2-05:25; `IA/docs/OPERACAO.md:172-176` |
| K-05 | `PHOENIX_API_KEY` | Opcional; D-30 prevê Phoenix sem auth em loopback | Exportador OTLP | Não escrita | Ler/gravar spans no Phoenix | F2b-08:21; G-0569 |
| K-06 | Chaves AES mensais (`CHAVE_AES_ARQUIVO`) | Arquivo 0600 `/etc/ia-s4`, montado `:ro` na VPS | Orquestrador; Phoenix monta o diretório inteiro | Manual, com reinício; descarte não existe | Com acesso ao banco ou backup, decifrar a conversa mascarada até o descarte | G-0084, G-0097, G-0041, G-0401, G-0374 |
| K-07 | `gateway-hmac.keys` (HMAC da rota `ia-mensagem`) | Arquivo 0600 na VPS (10001:10001); `GATEWAY_ASSINATURAS` no gl-gateway S2; cópia em `$SEGREDOS_DIR/assinaturas/` na S3 | API (`auth.py:85-87`) e gateway | 2ª linha na virada; o kit não tira a antiga | Forjar evento assinado como o gateway, com `canal_origem` | G-0546, G-0513, G-0481, R2-023; `KITS/gateway/entregar-hmac-vps.sh:8` |
| K-08 | `saida.json` (bearer do orquestrador, token ChatGuru da IA, cliente e segredo do 360) | Arquivo 0600 na VPS | Executores de ferramenta (ainda não existem) | Não escrita | Token ChatGuru: qualquer `action` em `/chatguru/acao`. Credencial do 360: 5 escopos, 19 operações, enumeração em lote | G-0226, G-0124; `IA/docs/OPERACAO.md:167-170`. Valores de produção: NÃO EXISTEM (A1.4, A1.5, B4.1) |
| K-09 | `GATEWAY_CREDENCIAIS` (inclui `chatguru-ia` e `chatguru-ia-teste`), `GATEWAY_CABECALHOS_SERVICO` | Coolify do gl-gateway S2 e backups; cópias em `$SEGREDOS_DIR` (S3) | gl-gateway | Sem kit de rotação | `chatguru-ia`: grava em qualquer atendimento ativo. `chatguru-ia-teste`: Post guardado no sumidouro | G-0750, G-0508, G-0748; F2-08:29-40; sonda S2 |
| K-10 | Senhas e certificados de `ia_obs_a`, `ia_leitura_a`, `bkp_pg` | `/etc/ia-s4` (VPS, mesmo grupo 10001 do `ia_app_a`); `/etc/ia-leitura-s4` (S2, root:70 0750) | Phoenix; leitura da S2; backup | Sem kit | `ia_obs_a` é dono do banco `ia_obs` (DDL) | G-0574, G-0523; F2-37:65; F2b-09:18 |
| K-11 | Credencial do registry (`S3_REGISTRY_USER`/`PASSWORD`) | Secrets do GitHub, mesmos valores em 3 repositórios | Workflow `imagem.yml` | Não escrita | Escrita no registry; tag mutável deixa trocar a imagem implantada (inferência, apoiada em G-0467) | G-0466, G-0467; F2-22:94; sonda S21 |
| K-12 | Token do Coolify | Secret do GitHub (`::add-mask::`); shell do operador (`curl -K -`) | Workflow e `deploy-vps.sh` | Não escrita | Disparar deploy; escopo exato não verificado | F2-22:45-46 |
| K-13 | Chave da rota `inapp-clt` e `n8n_segredo` | Fora da exportação | — | Adiada para depois do piloto (02/12); kit não existe | Tratadas como **expostas** (apareceram em transcritos) | G-0385; `ROTEIRO-DE-ACAO.md:502` |
| K-14 | Tópico do ntfy.sh | Não existe | — | — | Ler alertas; forjar alerta e ack | G-0573, G-0052 |
| K-15 | Cookie do RPA | Fora da exportação (premissa) | RPA | Expira | Não verificado | sonda S26 |

Sete sem rotação em vigor: K-02, K-05, K-08, K-11, K-12 (não escrita), K-04 (permanente por desenho) e K-13 (adiada, sem kit). K-03, K-06, K-07, K-09 e K-10 têm rotação só parcial, manual ou sem kit.

### 7.4 Prova principal por id

Movida para o Anexo B, no fim do documento.

---

## 8. Situação dos 128 RG, das 32 D-nn e dos 20 AJUSTAR

Dos 128 RG, 23 estão fechados com prova, 45 só no papel, 40 abertos, 9 superados e 11 refutados; das 32 D-nn, 4 têm prova, 1 prova parcial, 15 estão só no papel, 10 abertas e 2 superadas; dos 20 AJUSTAR, 16 seguem sem adoção e nenhum tem dono nem data no papel.

### 8.0 Como ler

- **Fontes.** Estado por id: leituras `fase1/leituras/F1-53.md` a `F1-58.md` (RG) e `F1-59.md` (D-nn e AJUSTAR). Severidade, título e D-nn: `fase0/inventario-rg.csv`. Grupos ligados: campo `rg` de `fase3/consolidado.json`.
- **Coluna «Fonte».** `F1-5x:n` é a linha da tabela do leitor onde o id é fechado. A prova completa está lá.
- **Siglas da prova.** ROT = `ROTEIRO-DE-ACAO.md` v3.3; 01–08 e PD = `contratos/` vigentes (sem sufixo); T = `textos/TEXTOS-PARA-APROVACAO.md`; MAN e REC = `fase0/MANIFESTO.md` e `fase0/reconciliacao.md`. Caminhos de código são da exportação em `/home/danilo/ia-revisao-0911/src/`.
- **Número de linha do roteiro.** Vale a v3.3. As colunas `ROT:n` da Parte F e do CSV usam a numeração da v3.2 e não servem de endereço (F1-53.md:65, F1-54.md:112). A âncora de texto é o que vale.
- **Limite.** Produção, Kan, GitHub ao vivo e `cliente360-web` não foram lidos. «Sem registro» não prova «não feito» (REC §0).

**Regra de normalização dos estados.** Os seis leitores usaram rótulos diferentes. F4-039 (`fase4/consolidado-f4.json`, «Os 128 RG não têm tabela única nem vocabulário comum») pede uma tabela única. Esta seção a entrega com estas regras:

| Rótulo do leitor | Estado final | Motivo |
|---|---|---|
| «fechado com prova», «com prova», «FECHADO», «FECHADO (papel)» | fechado com prova | a correção está no destino esperado pelo CSV (texto para `papel`, código na main para `código`) |
| «só no papel», «fechado só no papel» | fechado só no papel | texto emendado; código, kit ou ato ainda não existem |
| «PARCIAL», «só no papel, em parte» | aberto | correção pedida por F4-039: «PARCIAL ⇒ aberto com nota» |
| «aberto», «aberta», «ABERTO» | aberto | — |
| «superado», «superada» | superado | camada posterior trocou a decisão |
| `refutado` na coluna `estado` do CSV | refutado | mesmo quando o leitor usou outro rótulo (RG-047, RG-053, RG-056) |

Caso especial: RG-095 tem a letra superada (30 tentativas → 30 min), mas a regra R-c2 segue sem decisão (F1-57.md:21; G-0032 ALTO). Fica **aberto**.

A coluna «Rótulo do leitor» guarda o texto original. Quem discordar da regra pode recontar sem reler as fontes.

### 8.1 Contagem dos 128 RG por estado e severidade

| Estado | CRÍTICO | ALTO | MÉDIO | BAIXO | n/i | Total |
|---|---:|---:|---:|---:|---:|---:|
| fechado com prova | 0 | 3 | 13 | 7 | 0 | **23** |
| fechado só no papel | 0 | 10 | 21 | 14 | 0 | **45** |
| aberto | 2 | 16 | 10 | 12 | 0 | **40** |
| superado | 0 | 0 | 6 | 3 | 0 | **9** |
| refutado | 0 | 0 | 0 | 0 | 11 | **11** |
| **Total** | 2 | 29 | 50 | 36 | 11 | **128** |

n/i = severidade «não informada» no CSV (os 11 refutados). RG-128 entra na conta: nasceu fora da fusão de 03/11, mas teve decisão e correção (F1-58.md:77 «Quem contar pendências deve somá-lo»).

- **fechado com prova** (23): RG-001, RG-002, RG-014, RG-018, RG-019, RG-020, RG-021, RG-026, RG-028, RG-031, RG-032, RG-036, RG-037, RG-039, RG-046, RG-049, RG-055, RG-078, RG-103, RG-104, RG-116, RG-119, RG-128
- **fechado só no papel** (45): RG-005, RG-006, RG-008, RG-009, RG-012, RG-013, RG-015, RG-044, RG-051, RG-052, RG-054, RG-057, RG-058, RG-063, RG-065, RG-066, RG-068, RG-072, RG-074, RG-075, RG-076, RG-077, RG-079, RG-080, RG-084, RG-086, RG-087, RG-088, RG-090, RG-094, RG-096, RG-098, RG-099, RG-101, RG-102, RG-105, RG-106, RG-109, RG-114, RG-115, RG-117, RG-120, RG-121, RG-123, RG-126
- **aberto** (40): RG-003, RG-004, RG-007, RG-011, RG-016, RG-022, RG-023, RG-024, RG-025, RG-027, RG-029, RG-033, RG-034, RG-035, RG-038, RG-040, RG-041, RG-042, RG-043, RG-045, RG-048, RG-059, RG-060, RG-061, RG-062, RG-064, RG-067, RG-070, RG-073, RG-081, RG-082, RG-085, RG-091, RG-093, RG-095, RG-097, RG-100, RG-107, RG-110, RG-111
- **superado** (9): RG-017, RG-030, RG-050, RG-069, RG-071, RG-089, RG-108, RG-112, RG-113
- **refutado** (11): RG-010, RG-047, RG-053, RG-056, RG-083, RG-092, RG-118, RG-122, RG-124, RG-125, RG-127

**Leitura rápida.**
- «Fechado só no papel» é o maior grupo. Em muitos casos o código é de etapa ainda não construída (B1.6b, B5.4–B5.6, B6.2–B6.9, B9.0). Esses ids viram critério de aceite das etapas, não defeito.
- A Parte F do roteiro marca 111 ids como «aplicado em texto (v3.3)». Isso prova só papel (PLANO-REVISAO-0911.md:21). Pelo menos 5 linhas marcam «aplicado» com o alvo fora do roteiro intocado: ROT:1652, :1696, :1625, :1621, :1641 (F1-54.md:80).
- Só 54 dos 128 RG viraram grupo na Fase 3 (F4-039). A coluna «Grupos» mostra quais.

### 8.2 RG abertos de severidade CRÍTICO ou ALTO (18)

| RG | Sev. | Título | Prova |
|---|---|---|---|
| RG-004 | ALTO | Gasto por soma de passo.custo_brl bloqueia B1.6 e falta na Spec | main `chave.py:196` soma `custo_modelo_brl + custo_midia_brl`; correção só no ramo (`gasto.py:49`, PR #13 em conflito) |
| RG-007 | ALTO | Sombra A e ensaio B no mesmo dia violam o 08 §6 | ROT:1147 ensaio B riscado; ROT:1277 põe as falhas de 24/11 dentro da sombra |
| RG-011 | ALTO | Vhost WG 8093 autentica por prefixo mas o 02 exige allowlist fechada | 02:72-73 só `/gateway/ia-repasse`; ROT:712 «a emenda do 02 §2 fica pendente» |
| RG-016 | ALTO | Roteiro diz auto-deploy desligado mas gateway e facta-on deployam no merge | ROT:45 «a proteção da `main` é ação do dono, **pendente**» |
| RG-040 | ALTO | Chave Fireworks sem data trava A2.9 completa e B8.2 | ROT:289 «chave Fireworks até ~~09/11~~ 17/11»; ROT:1123 ainda 09/11; ato sem registro |
| RG-041 | CRÍTICO | VPS não existe e a cadeia A4, o deploy 8 e a sombra ficam sem data | ROT:290 «VPS contratada até 12/11 14:00»; REC §4 sem registro de A1.3/A1.5 |
| RG-042 | ALTO | Perguntas ao ChatGuru não enviadas e A3.0 depende da A1.1 inteira | ROT:285 «pendente do dono: 09/11, no pedido único»; sem registro |
| RG-043 | CRÍTICO | Janela do gateway de 05/11 desenhada para merge já feito em 30/10 | 01:298-305 passos de 04–06/11; `kits/gateway/lib.sh:52-53`; Redeploy de 10/11 sem registro |
| RG-045 | ALTO | B1.6 com 3 dias e doze obrigações herdadas sem folga | B1.6a só no PR #13 `CONFLICTING` (MAN:92); B1.6b sem branch (MAN:19-38) |
| RG-048 | ALTO | Cookie do RPA com 2FA humano e 18 dias sem renovação registrada | ROT:298 cookie 09/11; PD:45 «renovar antes de 18/11»; renovação sem registro |
| RG-062 | ALTO | Ensaios n8n S1 a S6 e alcance NAT sem kit nem data | ROT:683-685 «**não existe hoje**»; `kits/` sem `n8n/` |
| RG-064 | ALTO | B5.5 depende de dicionário de contexto_codigos que ninguém escreveu | `TEXTOS-PARA-APROVACAO.md:3` «Versão 1, gerada em 30/10/2026»; dicionário não existe |
| RG-067 | ALTO | Worker no compose da esteira sem etapa e A6.6 concluída com command inexistente | `ia-atendimento-esteira/docker-compose.yml:96` com `command` inexistente; prazo 08/11 vencido |
| RG-091 | ALTO | Corpo do ia-agendar no n8n sem saveData none e sem ensaio S4 | 04:373 «[ABERTO] Texto do cliente no corpo de `ia-agendar`» × PD:42 «Sem objeto» |
| RG-093 | ALTO | C6 tirou o cerco e a mitigação depende de A3.2 e A3.4 | A3.4 remarcada para 10–11/11 (ROT:643); B6.5 «cortada (C6)» (ROT:390) |
| RG-095 | ALTO | Até 30 do repasse: tentativas ou minutos e regra de repassando preso | 08:244 «30 min esgotados ⇒ `repasse_travado`»; R-c2 «Pendente, sem decisão» (ROT:1718) |
| RG-097 | ALTO | Pessoas e semente: substituto do Danilo, revisor e lista nominal | ROT:1457 «pendentes do dono: substituto e revisor» |
| RG-100 | ALTO | Textos: reemissão com emendas do N e aprovação em dois lotes | `TEXTOS-PARA-APROVACAO.md:3` «Versão 1, gerada em 30/10/2026»; TX-42: 0 ocorrências |

Três deles fecham só por ato do dono: RG-040 (chave Fireworks, 17/11), RG-041 (VPS, 12/11 14:00) e RG-042 (perguntas ao ChatGuru, 09/11). Nenhum dos três tem registro do ato (F1-54.md:45-51).

### 8.3 Tabela dos 128 RG

Movida para o Anexo C, no fim do documento. A contagem está no §8.1 e os abertos graves no §8.2.

### 8.4 As 32 D-nn

Camadas: C0 recomendação de 03/11; C1 «Segue recomendações» do dono (03/11 noite); C2 parecer do Codex (04/11, não é o dono); C3 respostas do dono 04/11 ~11h; C4 cenário C (04/11 tarde); C5 contratos emendados; C6 decisão delegada de 10/11 (degrau de 1 dia), que não está no roteiro nem no inventário (F1-59.md:28).

Fonte de cada linha: `fase1/leituras/F1-59.md:38-69` (uma linha por D-nn, na ordem). Placar idêntico ao de `fase0/inventario-dnn.md:43-53`.

| D | Decisão vigente (camada) | Estado | Prova principal | Grupo / RG |
|---|---|---|---|---|
| D-01 | Chave Fireworks até 17/11; sem chave, F3 só I1–I9 com `ProvedorFalso` (C4) | **aberta** (ato do dono) | ROT:289; ROT:1123 ainda 09/11 | RG-040, RG-054; G-0369 |
| D-02 | VPS até 12/11 14:00; C6 move o `s4-hba.sh` para 11/11 13:15 (C4/C6) | **aberta** | ROT:290; REC §4 sem registro | RG-041; G-0001 |
| D-03 | RPA leitor «sim, só sem webhook por mensagem» (C4) | **aberta** | ROT:147; chat de teste e 13 perguntas sem registro | RG-042, RG-051, RG-063, RG-084 |
| D-04 | Janela do gateway 10/11 05:30, reserva 11/11; C6 usa 11/11 05:30 (C4/C6) | **só no papel** | 01:294, :305; kit ainda em 04–06/11 (`kits/gateway/README.md:27,30,62,142`) | RG-029, RG-030, RG-043 |
| D-05 | C9 adotado; sombra de 2,5 d; caso (b) sai (C4) | **só no papel** | ROT:122, :1076; 07:167 | RG-007, RG-044, RG-115 |
| D-06 | Merges feitos pelo dono em 03/11 22:27 (ato) | **com prova** | pontas `9a4bacab`/`ca3ed2cf` (MAN); ROT:142 parado em `6abaf02` | RG-045, RG-046, RG-119, RG-128 |
| D-07 | Cookie do RPA em 09/11 à noite, 2ª em 19/11 (C4/C6) | **aberta** | ROT:143, :173; sem registro | RG-048 |
| D-08 | `!` sempre para mutação (C1) | **só no papel** | ROT:123; ROT:1732 | RG-050 |
| D-09 | Regra (a) + proteção da `main` até 10/11 12:00 (C4) | **aberta** (falta «exigir PR valendo para admin») | ROT:45 «pendente»; ROT:144 | RG-016; G-0388 |
| D-10 | «Ok» do dono ao desenho de K (C4) | **só no papel** (B6.4 sem código) | ROT:295 | RG-099 |
| D-11 | Reemissão dos textos; lotes 11/11 e 13/11 (C4) | **aberta** (reemissão não existe) | T:3 «Versão 1, gerada em 30/10/2026»; TX-42: 0 | RG-023, 024, 027, 064, 100; G-0075 |
| D-12 | N-1 «Sim» literal do dono (C3) | **só no papel** | ROT:114, :127 | RG-087, RG-094 |
| D-13 | Janela de 24 h = `espera` (C1) | **só no papel**, parte em código | ROT:128; PD:18-21 | RG-098 |
| D-14 | Espera total do repasse ≤ 30 min, depois `repasse_travado` (C5) | **só no papel** (0 ocorrências no código) | 08:244; `01:216`, `04:338` | RG-095; G-0032 |
| D-15 | Vigia fail-closed, batimento 90 s (C5) | **só no papel** | 08:224; `api/saude.py:53` devolve `batimento_idade_s: None` | RG-013, 090, 093, 114 |
| D-16 | Política publicada + aceite escrito do dono (C1) | **aberta** (assinatura até 13/11) | ROT:1453-1454 | RG-036 |
| D-17 | Papéis: substituto e revisor até 11/11; e-mails até 12/11 (C4) | **aberta** | ROT:145, :1457 | RG-097, RG-102; G-0387 |
| D-18 | Domingo incluso (C1); 29/11 dia 4 (C4); dia 3 de 4 no C6 | **com prova** no código | migração 0005 na main; `config/domingo.sh` «A escrever» (ROT:1732); TX-42 ausente | RG-056, RG-065, RG-066, RG-089 |
| D-19 | `saveData*: none`; importação 09/11 12:30; caso (b) fora; C6 12/11 13:15 (C4/C6) | **aberta** (kit «não existe hoje») | ROT:684; PD:42 | RG-062, RG-091; G-0373 |
| D-20 | M-05 tri-state e M-06 lista estreita (C1) | **só no papel** | ROT:130; PD:43 | RG-106 |
| D-21 | Comissão R$ 100 / 4 % como proxy (C1) | **só no papel** (painel não lido) | ROT:130 | RG-101 |
| D-22 | Parada leve devolve também `pausado` (C1) | **com prova** no orquestrador; vigia não existe | `jobs.py:42-43`; ROT:1063 CAS só `aberto` | RG-103; G-0080 |
| D-23 | Trigger fica no banco `ia_atendimento` (C1) | **com prova** no código | `0003_estado_aditivo.up.sql:4`, `:27`; 08:291 | RG-104 |
| D-24 | Rotação das chaves depois do piloto (C4) | **superada** (a de 06/11); kit «A escrever» | ROT:131, :501 | RG-050, RG-108; G-0385 |
| D-25 | Basta a ciência do superior; C6 muda o texto para 27–30/11 (C4/C6) | **só no papel** (apresentar até 13/11) | ROT:132, :159 | RG-110 |
| D-26 | Dublê sintético; colheita real (C1) | **só no papel** | ROT:132; ROT:344 sem registro | RG-111; G-0381 |
| D-27 | Telefone no espelho «como está», 30 d (C1) | **só no papel** | ROT:132; 04:21 | RG-096 |
| D-28 | Degrau; caso (b) fora (C4) | **superada** | ROT:132, :154; PD:37, :42 | RG-113 |
| D-29 | «Só o essencial…» (C1/C5) | **com prova parcial** | 03:39, 08:97; `matricula` em `src`: só `com_matricula` | RG-032 |
| D-30 | Phoenix só por túnel (C1) | **só no papel** (`feat/esteira` sem remoto; VPS não existe) | ROT:133; 03:206, 07:178 | RG-123 |
| D-31 | Apagar o corpus bruto no gatilho (C1) | **só no papel** | ROT:133 | RG-086 |
| D-32 | Gemini condicional + prova de 14 d da retenção (C3/C5) | **aberta** na prova de 14 d | ROT:43, :112, :134; nenhum contrato cita D-32 | RG-014, RG-069, RG-078 |

**Pontos que mudam o calendário** (F1-59.md:113-133):
- D-11: o roteiro diz «Textos reemitidos em 05/11» (ROT:126). O arquivo é a versão 1 de 30/10. O 1º lote vence em 11/11 (G-0075).
- D-14 e D-15: estão em três contratos e em nenhum código, nem na main nem em `feat/b1-6a` (F1-59.md:13). Seguram a B1.6b, a tag `v0.3.0` e o deploy #8.
- D-22 e E-24: a Spec da B6.4 (ROT:1063) traz o CAS só para `aberto` e «fluxo principal ⇒ rodízio». Os contratos dizem o contrário (01:478, 04:500).
- D-04 com C6: há três calendários escritos para a janela do gateway. Kit em 05/11, roteiro em 10/11, decisão delegada em 11/11 (F1-59.md:10).
- D-01: nenhuma decisão própria do dono aceita «custo/latência não medidos». O padrão vale por adoção em bloco (C1). O contrário é o AJUSTAR de D-01, pendente em E-23 (F1-59.md:147).
- D-32: o código aceita `gemini-*` sem condição. Não há frase literal do dono para «Gemini condicional» (F1-59.md:16).

### 8.5 Os 20 AJUSTAR do parecer do Codex

O roteiro só os registra em E-23: «dono + revisão · conforme cada item · a definir» (ROT:1474). Nenhum tem dono nem data no papel (G-0081 MÉDIO; F1-59.md:84).

Placar (F1-59.md:109; `fase0/inventario-dnn.md:113-141`): 3 adotados (D-06, D-12, D-25), 1 adotado e superado (D-18), 3 superados com resíduo (D-01, D-19, D-24), 2 parciais (D-03, D-17), 11 abertos.

**AJUSTAR não fechados (16).** A coluna «Dono e data propostos» é sugestão do leitor F1-59, não decisão. Marcados com ▲: os quatro que são controle e pedem resposta antes do deploy do bloco (F1-59.md:111).

| D | Pedido do parecer | Estado | Resíduo / prova | Dono e data propostos (F1-59) |
|---|---|---|---|---|
| D-01 | Chave em 09/11; nenhum piloto sem A2.9a e F3 com o modelo real | superado na data; **aberto** na trava | ROT:1165 aceita «custo/latência não medidos» | dono, até o go/no-go (aceite não delegável) |
| D-03 | «Ok» ao RPA leitor; retentativas como hipótese | **parcial** | ROT:454 ainda «3× em ~6 s; lock por chat» | Claude, emenda de texto antes de A3.0 |
| D-05 ▲ | Kit de parada dura; lista única de alertas | **aberto** | nenhum kit de parada em `kits/`; ROT:1165 «5 tipos» × ROT:1076 | Claude, B9.0 (17/11) |
| D-08 | `allow` só para leitura e ensaio | **aberto** | ROT:1732 ainda pede as duas regras de diretório | dono, na ata A1.10 |
| D-09 | Proteção antes do próximo merge que publica | **aberto** | ROT:45 «pendente» | dono, 10/11 12:00 |
| D-11 | `{{saudacao}}` na lista; TX-42 no 1º lote | **aberto** | T:3 versão 1; TX-42: 0 ocorrências | Claude reemite; dono aprova 11/11 |
| D-16 | Versão e data da política; assinar antes de G2 | **aberto** | ROT:1454 | dono, 13/11 |
| D-17 | Substituto treinado; revisor distinto; amostra antes do go | **parcial** | ROT:498 revisor opcional × ROT:1165 | dono, 11/11 (nomes) |
| D-19 | Provar ausência de corpo gravado; tirar «guardar 1 dia» | superado com **resíduo** | ROT:685 mantém «`retencao` 1 d (`!`)» | Claude, emenda de texto |
| D-21 | R$ 100 parâmetro único; tirar faixas de 1–3 % | **aberto** | ROT:242 «a 1–3% de comissão (… conta não refeita)» | Claude, A2.11a |
| D-22 ▲ | `pausado` na guarda da devolução; ensaio da corrida | **aberto** | ROT:1063 «WHERE chave=? AND estado='aberto'» (G-0080) | Claude, B6.4, antes do #6 |
| D-24 | Kits antes da janela; revogar a 2ª chave | superado na data; **resíduo** | kit «A escrever» (ROT:1732); G-0385 | Claude + dono, depois do piloto |
| D-26 | Comparação com o tap e contagem do M-06 antes do go | **aberto** | ROT:931 prevê; ROT:1165 não exige; tap fora da main (G-0381) | dono decide se entra no checklist |
| D-27 ▲ | Cifrar o telefone na S2 e apagá-lo ao fechar | **aberto** | ROT:132 «D-27 como está» | dono (aceite de risco), antes do #6 |
| D-29 ▲ | Recusar CPF por forma em identificadores; H1–H3 antes do real | **aberto** | 08:97 aceita `^[0-9A-Za-z./-]{1,40}$` (11 dígitos passam); 04:500 | Claude, B5.2/B5.4 e B6.2 |
| D-31 | Prazo, responsável e inventário das cópias do corpus | **aberto** | ROT:133 | dono + Claude |

Resíduos dos adotados: D-25 ainda tem «Aceite: «ok» ou «sem objeção»» em ROT:527. D-18 foi deslocado de novo pelo C6.

### 8.6 O que esta seção não verificou

- Atos do dono de 09 e 10/11 (A1.1a, A1.3, cookie, Redeploy do gateway, proteção da `main`): sem registro nas fontes. Ficam **não verificados**, não «não feitos».
- Painel `index.html` e `premissas.json` para D-21 e RG-101: não relidos pelos leitores.
- PR #13 e PR #49 no GitHub; tags `v0.1.0` e `v0.2.0` (a exportação não tem histórico).
- Âncoras herdadas do inventário sem reconferência própria do F1-59: D-13, D-18, D-20, D-22, D-23, D-28, D-30 (F1-59.md:157).
- A normalização desta seção (5.0) troca 9 rótulos «PARCIAL» ou «em parte» por **aberto**, mais o caso RG-095. Os demais estados são os dos leitores, sem nova leitura dos arquivos de destino.

---

## 9. O que depende do dono e de produção

Resumo: 38 itens dependem do dono (17 atos ou «sim» com data, 21 aceites e decisões); 34 sondas só-leitura cobrem o que não se prova sem produção; 55 premissas externas (51 supostas) mais 6 novas da revisão ficam com árvore de decisão.

**Como ler.**
- Datas no **calendário do degrau** (`fase0/decisoes-delegadas.md` §1, §1b, §5, §7; abaixo «DEL»). Onde o DEL não move a data, vale a do roteiro; onde eu inferi, está escrito «inferido».
- Estado no momento desta síntese (10/11 noite): **nenhuma sonda tem saída gravada**. Não existe `~/ia-revisao-0911/sondas/`; `medicoes/` não tem arquivo depois de 30/10 (`fase0/reconciliacao.md:165`, `:199`). Todo ato de 09–10/11 segue «desconhecido, tratado como não feito até a sonda provar» (DEL §5).
- Ids estáveis: `DN-nn` (dono), `SO-nn` (sonda), ids de premissa de `fase0/premissas.md` (CG, RPA, FA, FW, VPS, DP, CO, NT, PH, PB, N8, BAT, SUP, JUR, OPR, SEN, S4) e `RV-nn` (premissa nova da revisão).
- Para a IA que executa: um item `DN` só destrava a correção ligada quando o dono responde por escrito. Nenhuma sonda `SO` autoriza escrita.

---

### 9a. Lista única do que depende do dono

#### 9a.1 Atos pessoais e «sim» por kit, com data

| Id | O quê | Tipo | Data-limite (degrau) | Fonte da data | O que trava sem ela | Achado / prova |
|---|---|---|---|---|---|---|
| DN-01 | Marcar o chat de teste; enviar as 13 perguntas ao ChatGuru e a pergunta 4 à FACTA | ato | **10/11 18:00** | DEL:162 | A3.0 não roda em 11/11, nem pela queda E-12. Um segundo dia perdido acaba com o piloto real (DEL:47) | G-0068 (`01-chatguru-lead.md` «Retry/idempotência … nunca respondida»); G-0119 (`ia_atendimento/api/eventos.py:41`, `tipos.py:27`); premissas CG-01..CG-03, FA-04 |
| DN-02 | A1.3: titular, e-mail de função, cartão em dólar | ato | 10/11 | DEL:163; PLANO §7b | VPS (A1.5) e conta Fireworks (A1.4) | G-0001 (`ROTEIRO-DE-ACAO.md` A1.5 «não iniciada; prazo 03/11 vencido») |
| DN-03 | Ata A1.10, com o item P5 do portão, a linha factual do alcance da máscara e o D-08 | ato | 10/11 à noite | DEL:164; F1-59:92 | Sem P5 o portão do Redeploy de 11/11 não abre (`kits/gateway/README.md` tabela «Portão») | G-0384 (RG-107; `REVISAO-GERAL-0411.md` «o alcance da máscara nunca foi apresentado») |
| DN-04 | D-09: «exigir PR valendo para admin» nos 3 repositórios | ato | **10/11 12:00 (já passou; estado não verificado, SO-13)** | DEL:165; PLANO §0.4 | Até lá, nenhum merge em `gl-gateway` nem `facta-on` fora de janela. Merge = deploy | G-0070 (`gl-gateway/.github/workflows/testes.yml:18`, `:58`: o deploy sai do push sem esperar o pytest) |
| DN-05 | «sim» a N1–N3: `rotas-ia.sh`, `env-gateway.sh --gravar`, vigia de ensaio | «sim» | 10/11 depois das 20:30 | DEL §1b:53; DEL:157 | Sem rotas e env, não há Redeploy em 11/11 | F7 do DEL: README do kit com datas de 04–06/11 (DEL:18, :173) |
| DN-06 | Redeploy do gateway (reserva) e, se ela cair, uma 2ª janela; escolher a `ORIGEM_E12` | «sim» + clique do Danilo | **11/11 05:30**; 2ª janela proposta 12/11 05:30 | DEL §1b:54; DEL:183 | A3.0–A3.7 escorregam mais um dia; a queda E-12 vira o único caminho | `kits/gateway/e12-sumidouro.sh:10` «Sem padrão: quem escolhe é o dono» |
| DN-07 | Renovar o cookie do RPA e registrar `salvo_em` (ato do Danilo) | ato | 10/11 à noite | DEL:161 | A2.4, A3.3, A3.5 e a B1.6 ficam sem leitura de conversa | G-0665 (`medicoes/A2-s2-medicoes-3010.md` «Não há campo de expiração»); RPA-01 |
| DN-08 | «sim» a A4.3a: `s4-papeis.sh` e `s4-hba.sh` (S4 de produção) | «sim» | **11/11 13:15**; queda 12/11 13:15 | DEL:159; DEL §1b:56 | A4.6 de 13/11 perde a folga; `ia_obs` não nasce | F4-021 (`ROTEIRO-DE-ACAO.md:706` desfaz pelo texto v1, não por `kits/s4/desfazer.sh:28`); F4-023 (`kits/s4/provar.sh:65`); F4-024 |
| DN-09 | Nomes do substituto do Danilo e do consultor sênior revisor (D-17) | ato | 11/11 | DEL §6 «Qua» item 5; PLANO §7b | Piloto não roda em dia de ausência; 29/11 só com o Danilo (OPR-01) | F1-59:97 (D-17 «parcial») |
| DN-10 | Aprovar o 1º lote de textos (11/11) e o 2º com TX-42 (13/11); texto do aviso aos consultores («a partir de 27/11») | aprovação | 11/11 · 13/11 | DEL §7 «Textos»; DEL:39 | Textos do cliente sem aprovação. **A reemissão ainda não existe** (tarefa do Claude) | G-0075 (RG-023, arquivo ainda v1 de 30/10); G-0072 (TX-42 ausente); F1-59:94 (D-11) |
| DN-11 | A1.5: contratar a VPS OVH BHS | ato + pagamento | **12/11 14:00** | DEL:166 | Sem VPS, nada a substitui no #8 nem na sombra; orquestrador fica em dev (`ROTEIRO-DE-ACAO.md:1303`) | G-0001 (RG-041); G-0013 (VPS sem política de saída); VPS-01 |
| DN-12 | E-mails da semente de operadores | ato | 12/11 | DEL §6 «Qui» item 2; PLANO §7b | Disparo bloqueado sem identidade do operador (N8-03) | — |
| DN-13 | «sim» à importação do `zz-ensaio-ui` no n8n (A3.8) | «sim» | 12/11 13:15 | DEL:160; DEL §1b:57 | Segura a B6.2 e o deploy #6 | N8-01 |
| DN-14 | A1.11 ciência do superior (27–30/11); D-16 assinar a política; E-3 aceite do provedor; «sim» nomeado à migração 0005 | ato | 13/11 | PLANO §7b; F1-59:96 | Sem E-3/JUR-01: sombra com texto real só como ensaio B; G2 não abre. Objeção do superior para a B9 | SUP-01, JUR-01, FW-06 |
| DN-15 | A1.4: conta e chave Fireworks (US$ 100, arquivo 0600) | ato + pagamento | 17/11 (o DEL não move) | premissas FW-01; PLANO §7b | B1.4 não conclui; F3 só com `ProvedorFalso`; ver DN-21 | `ia_atendimento/config.py:85` (boot recusa sem `modelo_api_key_1`) |
| DN-16 | «sim» e merge por deploy do mapa: web #3 12/11 12:30 · API #4 13/11 12:30 · A4.6 13/11 13:15 · `facta-on` #5 13/11 >20:30 · #8 16/11 >20:30 · #6 17/11 12:30 · #7 18/11 12:30 · chave AES + última tag 19/11 12:30 | «sim» por kit | datas ao lado | DEL §1b:58-66 | Cada `!` sem «sim» não sai. As datas do §1b são proposta, não «sim» (DEL:231) | G-0017 (B3.1/B3.2 × mapa); G-0012 (`s4/migrar.sh` não existe); G-0011 (ledger fora da transação) |
| DN-17 | Regra X7, alternativa (c) | decisão | checkpoint 0b, **11/11 18:00** | DEL:88 | Com < 4 agentes vivos, X7 vai ao dono no mesmo dia; (c) revoga a alínea (ae) | DEL §2 |

#### 9a.2 Aceites de risco e decisões de produto (inclui os riscos que a revisão levantou)

| Id | Decisão pedida | Data-limite (degrau) | Fonte da data | O que trava sem ela | Achado / prova principal |
|---|---|---|---|---|---|
| DN-18 | Ciência do degrau de 1 dia e dos custos: F3 oficial sem correção, dia 1 na Black Friday, piloto de 4 dias. Mandar registrar no roteiro | **11/11 18:00** (efeito irreversível) | DEL:5, :35-39 | Roteiro segue com 18/11, 25/11 17:00 e reversão até 26/11 07:45, **antes** do go/no-go de 26/11 12:00 | G-0079 (`ROTEIRO-DE-ACAO.md:1164`, `:1167` × `decisoes-delegadas.md:27`) |
| DN-19 | Fixar a rampa do piloto de 4 dias (a de 5 dias tem 70 atendimentos) | go/no-go **26/11 12:00** | DEL:38 | `max_disparos_dia` sem número para 27–30/11 | G-0079 (B11.2 com rampa de 5 dias) |
| DN-20 | **Aceite de G2** com a prova de D-32: stanza própria, retenção ≤ 14 d ou dispensa escrita | 19/11 (inferido: 18/11 no cenário C, congelamento movido a 19/11) | premissas PH-02, PB-01; DEL §7 | G2 não abre; sombra A com texto real só como ensaio B (B9.2 bloqueada) | G-0005 (`ROTEIRO-DE-ACAO.md:43` «sobrevive nos fulls» × «provar … eliminado em 14 d»; `:231`); G-0329 (`MONITORAMENTO-DESIGN.md:52`) |
| DN-21 | **Aceite de «custo e latência não medidos»** no go/no-go, ou exigir A2.9a (AJUSTAR do D-01) | decidir até 17/11 (data da chave); registrar no go/no-go 26/11 12:00 | F1-59:88; PLANO §8 «§7b corrigido» | Sem decisão, D-01 «sem padrão para A2.9, B8.2 e go» contradiz A2.9/B8.2/B10.1 | G-0009 (`ROTEIRO-DE-ACAO.md:139` × `:599`); G-0619 (`g-provedor-modelo.md` «Cache 70% é HIPÓTESE»); FW-02..FW-05 |
| DN-22 | **Aceite do limite declarado da máscara** contra a regra 2 (RS-03) e RS-21: extenso, dígitos com letras, CPF partido, endereço, nome da mãe, empregador e nome do cliente passam | antes de G2: 19/11 (inferido); a linha factual vai na ata (DN-03) | DEL §7 «Aceites»; G-0384 | Sem aceite, sombra com texto real contraria a regra 2; correção por NER muda escopo | G-0420 (`ia_atendimento/mascara.py:12`, `:18` fora de escopo declarado; `:140` corrente < 8 dígitos fica); G-0047; G-0114 (`mensagens.py:284-287` `nomes=()` fixo); R2-015 (`api/anotacoes.py:83-85`) |
| DN-23 | **CPFs de DV válido na main do `facta-on`**: são de pessoa real? Se sim: tirar da main, reescrever o histórico e pôr portão de PII no workflow | sem data nas fontes; proposta: antes do merge #5 (13/11 >20:30), que publica de novo a main | historico-pii.md:26 | Reescrever histórico exige force-push, que o ruleset `main-protegida` bloqueia (PLANO §0.4): só o dono levanta | G-0118 ALTO (`facta-on/app/routers/online.py:594`, `:2005`, `:5758`; `.github/workflows/testes.yml:38` só pytest); F4-036; `historico-pii.md`: 29 não públicos ainda na main, 9 em `tests/amostras/consulta_fato_lote_20261104.jsonl` |
| DN-24 | CPF isento por impressão digital no `.gitleaksignore` do `ia-atendimento` e CPF em docstring de `decidir.py` (repos fora da revisão): mesma decisão de DN-23 | sem data nas fontes | — | Número de forma válida no histórico público, origem não provada | G-0471 (`ia-atendimento/.gitleaksignore:2`, `:4`); G-0340 «não verificável» (`01-chatguru-lead.md` cita `decidir.py:867`, `:870-878`); `historico-pii.md`: 1 «outro» só no histórico (`tests/test_mascara.py`) |
| DN-25 | `ia-sumidouro` guarda o Post inteiro, com PII, 7 d em `gateway.payloads`, sem autenticação no webhook: aceitar e pôr no livro de retenção, ou mudar | antes de A3.0: 11/11 08:30 | DEL:182; DEL §1b:55 | Ativar o sumidouro sem decisão grava PII de payload contra a regra 2 | G-0482 (`gl-gateway/app/projecao.py:57`, `main.py:465`, `metricas.py:108`); G-0734; G-0748 (`kits/gateway/ia-sumidouro.workflow.json:6`) |
| DN-26 | D-27: telefone em claro na S2 (cifrar e apagar ao fechar, ou aceitar) | antes do #6: 17/11 12:30 | F1-59:105; DEL §1b:64 | Espelho nasce com telefone em claro | F1-59:105 («ROT 132 "como está"») |
| DN-27 | Parada dura: comando, responsável noturno e prazo por gatilho (D-05 kit é do Claude, quem decide à noite é do dono) | antes do go/no-go 26/11 12:00 | F1-59:90; DEL §7 | Gatilhos D7-1..D7-3 sem quem decida; `kits/config/set.sh` não existe | G-0023 (`ROTEIRO-DE-ACAO.md:1183`, `:1101`, `:1178`); G-0083 (parada por gasto não existe) |
| DN-28 | R-c2 / PD-5: regra da vigia para o lead que o orquestrador desistiu de repassar | antes do #6: 17/11 12:30; senão vira risco aceito no go/no-go | `04-n8n-braco-espelho.md:382` | Lead preso no ator 85 com bot desligado até 7 h/20:15 | G-0032 (RG-095; `04-n8n-braco-espelho.md:338`, `:382`); G-0020 |
| DN-29 | Chave AES de dezembro: o código exige troca e reinício em 30/11, contra «nenhum `!` no piloto». Autorizar reinício no piloto ou mandar mudar o código | antes do kit de 19/11 12:30 | DEL §1b:66 | Desde 30/11 22:00 BRT todo `gravar_troca` e `cofre.guardar` levanta erro | G-0084 (`ia_atendimento/conversa.py:102-114`) |
| DN-30 | C8b: domingo real 29/11, com FACTA e Dataprev não medidas no domingo | go/no-go 26/11 12:00 | DEL §7 | Domingo vira conversa + repasse | premissas FA-04, DP-02; G-0054 |
| DN-31 | Esticar o piloto até 02/12 (padrão: não esticar) | go/no-go 26/11 12:00 | DEL:45 | — | DEL §1 |
| DN-32 | D-26: comparação com o tap e contagem do M-06 entram no checklist do go? | go/no-go 26/11 12:00 | F1-59:104 | ROT 931 prevê, ROT 1165 não exige | F1-59:104 |
| DN-33 | `ia_app` pode inserir `ia_ativa=true` e subir o teto: aceitar ou separar papel | antes de A4.6: 13/11 13:15 (inferido) | — | Liga/desliga e teto ficam sob a credencial do código | G-0246 (`i-esquema-reconciliado.md:513`) |
| DN-34 | Opt-out só vale para a IA (n8n e robôs seguem falando): aceitar ou estender | antes do piloto, 27/11 (inferido) | — | Impacto LGPD sem decisão (pergunta 3) | G-0263 (`f-catalogo-ferramentas.md`) |
| DN-35 | Os 20 «AJUSTAR» do parecer (E-23) que mudem data ou escopo: dono e data por item | sem data no papel | F1-59:11 | Nenhum dos 20 tem dono nem data | F1-59 §4 (`ROTEIRO-DE-ACAO.md:1474` «a definir») |
| DN-36 | D-31: prazo, responsável e inventário das cópias do corpus bruto | sem data nas fontes | F1-59:107 | Corpus bruto sem gatilho de descarte provado | matriz RS-06 (`matriz-restricoes.md:165`) |
| DN-37 | Prazo de descarte desta pasta `~/ia-revisao-0911/` | sem data nas fontes; a matriz manda decidir na Fase 5 | `matriz-restricoes.md:166` | Pasta com trechos de código e provas sem prazo | RS-06 |
| DN-38 | Abertos que o DEL não pediu: D20, D3, M-7, R-03 (DDD 00 das personas); troca do motor «treinado no corpus» pelo motor v0 sem decisão citada | sem data | DEL:238 | R-03: cenários de etapa 2 e 3 inalcançáveis no ensaio B3.2 | G-0489 (`anonimizador/duble_anon/sinteticos.py:63`); G-0623 |

**Prioridade para a sessão principal.** Os seis com risco de PII ou de prova legal (DN-20, DN-21, DN-22, DN-23, DN-25, DN-26) vão ao dono numa mensagem só, com o achado e a prova. Os de 10–11/11 (DN-01..DN-08, DN-17, DN-18) já estão no pedido único do DEL §6.

---

### 9b. Sondas só-leitura para o que é NÃO VERIFICÁVEL sem produção

**Regras (valem para todas).**
1. Nenhuma escreve. SQL sempre dentro de `BEGIN READ ONLY; … ROLLBACK;`. `printenv` só com nomes (`cut -d= -f1`), nunca valor de segredo.
2. Saída só por forma e contagem, e passa pelo portão de PII (`piiscan` + `gitleaks --redact`) antes de ir para o disco da revisão.
3. Quem roda (DEL §4): a **sessão principal**, num lote, por script em `~/ia-revisao-0911/sondas/`. Subagentes nunca. Se o classificador barrar, vira `!` do dono. Coolify por `tinker`, `portao.sh` e telas do Phoenix: dono. `salvo_em` do cookie e tela do ChatGuru: Danilo.
4. A S4 se lê por conexão direta. O MCP `supabase-gl360` mede outro banco (DEL:126).
5. Atalhos: `PSQL_GW` = `docker exec -i n8n-db psql -U postgres -d postgres -X -At` na S2 (`kits/gateway/lib.sh:21`). `<ct-gw>` = contêiner cujo nome começa por `gl-gateway-$GW_APP_UUID` (`lib.sh:28-29`). `$GW_URL` = `lib.sh:30`.

| Id | Afirmação que a sonda fecha | Máquina | Comando exato | Responde | Quem | Origem |
|---|---|---|---|---|---|---|
| SO-01 | `env-gateway.sh` rodou? (DN-05) | S3 local | `test -d ~/ia-gateway-segredos && stat -c '%y' ~/ia-gateway-segredos` (sem listar conteúdo) | existe + data | sessão | DEL S0 |
| SO-02 | `rotas-ia.sh` rodou? linha E-12 existe? (DN-05, G-0079) | S2 `n8n-db` | `$PSQL_GW -c "BEGIN READ ONLY; SELECT path, ativo, critico, corpo_campos IS NULL, guardar_corpo FROM gateway.rotas WHERE path LIKE 'ia-%' OR path LIKE 'zz-%' ORDER BY 1; SELECT count(*) FROM gateway.rotas; ROLLBACK;"` | linhas e contagem | sessão | DEL S1; F4 completude §5 S1 |
| SO-03 | O Redeploy saiu? (DN-06, CO-04) | S2 | `docker inspect --format '{{.State.StartedAt}} {{.Config.Image}}' <ct-gw>`; `curl -s --max-time 5 "$GW_URL/health"` (`gl-gateway/app/main.py:365`) | hora de início, imagem, versão | sessão | DEL S2; completude S3 |
| SO-04 | Portão de disco e carga (X5, CO-03) | S2 | `df -h / /var/lib/docker; uptime` | livre e carga | sessão | DEL S3 |
| SO-05 | Deploy do gateway fora de janela desde 04/11? | S2 Coolify | comando não está nas fontes (fila de deploys, contagem por estado) | contagem | dono (tinker) | DEL S4 |
| SO-06 | Volume X3: < 150 por 10 min (CO-04) | S2 `n8n-db` | `$PSQL_GW -c "BEGIN READ ONLY; SELECT count(*) FROM gateway.requisicoes WHERE recebida_em > now() - interval '10 min'; ROLLBACK;"` (coluna em `gl-gateway/init_metricas.sql:24`) | contagem | sessão, à noite | DEL S5 |
| SO-07 | A3.8 rodou? sumidouro importado? (DN-13, N8-01) | S2 n8n | SQL `SELECT name, active FROM workflow_entity WHERE name LIKE 'IA%' OR name LIKE 'zz-ensaio%'` em `BEGIN READ ONLY`; nome do banco do n8n **não verificado**; `docker exec <n8n> sh -c 'printenv \| cut -d= -f1 \| grep ^EXECUTIONS_DATA'` | nomes, estado, nomes de variável | sessão | DEL S6; completude S13 |
| SO-08 | D-32: retenção dos fulls (DN-20, PB-01) | S4 | `pgbackrest info` (só datas e tipos) | N dias | sessão | DEL S7; completude S15 |
| SO-09 | A4.3a rodou? papéis e hba (DN-08, RS-12, S4-01) | S4 | `BEGIN READ ONLY; SELECT rolname, rolcanlogin, rolconnlimit FROM pg_roles WHERE rolname LIKE 'ia\_%' OR rolname='bkp_pg'; SELECT type, database, user_name, address, auth_method, error FROM pg_hba_file_rules WHERE user_name && array['ia_app_a','ia_obs_a','ia_leitura_a','bkp_pg']; ROLLBACK;` | papéis e linhas | sessão | DEL S8; `matriz-restricoes.md:264`; completude S17 |
| SO-10 | `bkp_pg` lê o schema `ia`? `ia_app` pode apagar a conversa? | S4 | `BEGIN READ ONLY; SELECT has_schema_privilege('bkp_pg','ia','USAGE'); SELECT has_table_privilege('ia_app','ia.conversa_cifrada','DELETE'); ROLLBACK;` (só depois da A4.6) | booleanos | sessão | completude S18; `matriz-restricoes.md:264` |
| SO-11 | #5 ainda não saiu; janela de 20 min (RS-10, RS-15, FA-03, FA-05) | S2 | `curl -s` no `/health` do `facta-on` (`facta-on/app/main.py:100`; o DEL diz `/healthz`, o código diz `/health`); `docker exec <facta-on> sh -c 'printenv \| cut -d= -f1 \| grep ^FACTAON_'`; `docker exec <facta-on> printenv FACTAON_CONFERIR_JANELA_MIN` | versão, nomes das flags, janela | sessão | DEL S9; `matriz-restricoes.md:234`, `:310` |
| SO-12 | CPF no log do `facta-on` (G-0108) | S2 | `docker logs <facta-on> --since 24h 2>&1 \| grep -cE 'cpf=[0-9]'` | só contagem | sessão | completude S8 |
| SO-13 | D-09 vale para admin? PR #13 e #49 mergeáveis? (DN-04, G-0070) | GitHub | `gh api repos/GL-BUSINESS/<repo>/rulesets` e `gh api repos/GL-BUSINESS/<repo>/branches/main/protection` nos 3 repos; `gh pr view 13 -R GL-BUSINESS/ia-atendimento --json mergeable`; `gh pr view 49 -R GL-BUSINESS/facta-on --json mergeable` | regras e estado | sessão | DEL S11; completude S4 |
| SO-14 | Push protection e secret scanning (RS-13) | GitHub | `gh api repos/GL-BUSINESS/<repo> --jq .security_and_analysis` nos 6 repos | flags | sessão | completude S22; `matriz-restricoes.md:280` |
| SO-15 | Secrets do registry existem (CO-02, G-0466) | GitHub | `gh api repos/GL-BUSINESS/ia-atendimento/actions/secrets --jq '.secrets[].name'` | só nomes | sessão | completude S21 |
| SO-16 | `facta-on` faz deploy no merge (G-0017) | GitHub + Coolify | `gh api repos/GL-BUSINESS/facta-on/hooks --jq '.[].config.url' \| wc -l`; auto-deploy na tela do Coolify | contagem; liga/desliga | sessão + dono | completude S6 |
| SO-17 | O web faz deploy no merge (G-0004) | S3 | `systemctl list-timers --all \| grep -c web-auto-deploy` | contagem | sessão | completude S5 |
| SO-18 | Vhost WG: rota do T7, `ia_semquery`, cabeçalhos de IP (G-0127, G-0560, RS-17) | S2 | `nginx -T 2>/dev/null \| grep -nE 'listen .*(8093\|8114\|8118)\|location .*(facta-online\|formalizar\|ia-repasse\|batimento)\|proxy_set_header\|ia_semquery'` | linhas de config | sessão | completude S9, S10; `matriz-restricoes.md:339` |
| SO-19 | Sumidouro guarda Post 7 d e alguém apaga? (DN-25, G-0482, K3) | S2 `n8n-db` | `$PSQL_GW -c "BEGIN READ ONLY; SELECT count(*), min(recebida_em), max(recebida_em) FROM gateway.payloads WHERE rota='ia-sumidouro'; SELECT min(recebida_em) FROM gateway.payloads; ROLLBACK;"` | contagem e datas (mais velho que 7 d = sem expurgo) | sessão | completude S11, S12 |
| SO-20 | Execuções do sumidouro gravadas no n8n (G-0482, N8-01) | S2 n8n | `SELECT count(*) FROM execution_entity WHERE "workflowId" = '<id do ia-sumidouro>'` em `BEGIN READ ONLY` (banco do n8n não verificado) | contagem | sessão | completude S13; `matriz-restricoes.md:464` |
| SO-21 | Quem escreve em `gateway.rotas` (G-0188) | S2 `n8n-db` | `$PSQL_GW -c "BEGIN READ ONLY; SELECT grantee, privilege_type FROM information_schema.role_table_grants WHERE table_schema='gateway' AND table_name IN ('rotas','ips_confiaveis'); ROLLBACK;"` | papéis | sessão | completude S14 |
| SO-22 | Retenção do Phoenix (DN-20, PH-01, PH-02) | VPS | política do projeto na tela; `SELECT min(start_time) FROM spans` em `ia_obs` | data mais velha | dono (tela) | completude S16. **Hoje não existe** (DEL S13): pós-condição de A4.5 |
| SO-23 | Arquivos de chave na VPS (G-0097, RS-05) | VPS | `stat -c '%a %U:%G %n' /etc/ia-s4 /etc/ia-s4/*`; `docker inspect` do mount (`ro`) | modos | sessão | completude S19; `matriz-restricoes.md:135`. VPS não existe |
| SO-24 | Senhas de login fora da S4 (G-0113) | S3/S4 | `ls -la` do diretório de saída do kit `s4` (só nomes e modos; caminho não verificado) | nomes e modos | sessão | completude S20 |
| SO-25 | Histórico git dos 6 repos (F4-036) | S3 local | **já rodada** em 10/11 ~14:40: `gitleaks git --redact` + regra de DV | resultado em `fase4/historico-pii.md` | — | completude S24 |
| SO-26 | CPF isento no commit `88d081a` (G-0471) | S3 local | `git -C <checkout ia-atendimento> show 88d081a \| <piiscan com denylist>` (só contagem e faixa) | contagem | sessão | completude S23 |
| SO-27 | Faixa sintética 000 não colide com cliente (G-0442, G-0738, RV-03) | S4 gl360 | `SELECT count(*) FROM <tabela de pessoas> WHERE cpf LIKE '000000%'` em `BEGIN READ ONLY` (tabela **não verificada**) | só contagem | sessão | completude S25 |
| SO-28 | Cookie do RPA vivo (DN-07, RPA-01) | S2 | `/health` do RPA no `chatguru-api` (campo `valida`, sem cookie); `salvo_em` | booleano, data | Danilo | completude S26; DEL D2 |
| SO-29 | Corpus bruto apagado no gatilho (DN-36, D-31) | S3 | `ls ~/ia-corpus/entrada \| wc -l` | contagem | dono | completude S27; `matriz-restricoes.md:471` |
| SO-30 | O que foi marcado no Kan em 09/11 (PD-1) | Kan | leitura dos cartões da IA | estado | sessão | DEL S12 |
| SO-31 | env do Coolify = env do kit (DN-05) | S2 Coolify | `portao.sh --confirmo` (só leitura) | igual/difere | dono `!` | DEL D1 |
| SO-32 | Quem tem o token de teste e em que diálogo (RS-14, DN-25) | ChatGuru | listar na tela os diálogos que apontam para `…/ia-sumidouro` e `…/ia-mensagem` | lista de diálogos | Danilo | `matriz-restricoes.md:295` |
| SO-33 | Kit vivo = kit do manifesto (RS-08, F4-022) | S3 local | `sha256sum` dos arquivos de `~/retomada-2809/fila-2910/ia/<kit>/` contra `fase0/MANIFESTO.md`, antes de cada «sim» | igual/difere | sessão | `matriz-restricoes.md:202` |
| SO-34 | Teto de gasto no provedor; Coolify da VPS (CO-01); portas da VPS (RS-34) | Fireworks, Coolify, VPS | tela de billing; tipo de build e `is_auto_deploy_enabled`; `ss -ltnp` | limites, flags, portas | dono / sessão | `matriz-restricoes.md:436`, `:354`, `:490`. Só depois de A1.4, A4.5, A1.5 |

Não verificado e sem comando nas fontes: SO-05; contagem agregada H1–H3 da matrícula (FA-06, G-0058, Claude antes de B6.2); `/healthz` de `cliente360-api` e do web (DEL S10).

---

### 9c. Registro de premissas externas, com árvore de decisão

Base: `fase0/premissas.md` (55 linhas: 2 confirmadas, 2 parciais, 51 supostas). Datas movidas pelo degrau onde o DEL §1b move o ato. A coluna «Se não» diz o que muda no plano e no código.

#### 9c.1 Árvore das seis premissas que decidem o piloto

1. **CG-01 (Post por mensagem) → ensaio A3.1, 11/11 08:30 (degrau).**
   - Sim → webhook é o leitor; segue CG-02/CG-03.
   - Não → RPA vira leitor principal, ≤ 10 chats. O reconciliador RPA **não existe na main** (B6.1). Cai também em RPA-01 e RPA-02.
     - RPA-02 não (sem hora da última mensagem do cliente) → todas as aberturas abortam (`jobs.py:180-189`). Piloto sem disparo.
2. **FW-01 (chave Fireworks) → 17/11.**
   - Sim → A2.9a mede FW-02..FW-05; F3 com o modelo real.
   - Não → F3 só com `ProvedorFalso`; DN-21 decide se o go aceita «custo e latência não medidos».
     - DN-21 «não aceito» → no-go.
3. **VPS-01 (VPS) → 12/11 14:00.**
   - Sim → A4.2/A4.4 à noite; #8 em 16/11.
   - Não → nada substitui no #8 nem na sombra. Outro IP ou região mexe em `pg_hba`, nft, WireGuard e nginx (`kits/s4/s4-hba.sh:9-10`, `:38`).
4. **BAT-01 (batimento fail-closed) → B1.6b/B6.4.**
   - Código entregue → D-15 vale.
   - Não entregue → nada impede o orquestrador de agir com a S2 fora (`api/saude.py:53`). É controle, não premissa: sem ele, no-go.
5. **FA-04 / DP-02 (domingo) → tap lido em 16/11; go 26/11.**
   - Sim → 29/11 opera.
   - Não → domingo vira conversa + repasse (DN-30).
6. **PB-01 / PH-01 / PH-02 (D-32) → SO-08, A4.5; G2 19/11 (inferido).**
   - Fulls ≤ 14 d e Phoenix herda 14 d → G2 abre.
   - Não → G2 fechado até DN-20; sombra com texto real só como ensaio B.

#### 9c.2 Tabela completa

| Id | Premissa (curta) | Estado | Quem confirma · quando (degrau) | Prova / sonda | Se «não»: o que muda |
|---|---|---|---|---|---|
| CG-01 | 1 Post por mensagem, chatbot desligado, chat no ator 85 | suposta | Danilo, A3.1/A3.2 11/11 08:30; checkpoint 1 11/11 18:00 | G-0068 | RPA principal, ≤ 10 chats; reconciliador não existe (B6.1) |
| CG-02 | Em 424 repete 3× em ~6 s; ordem = chegada | suposta | A3.1 + verificação V2 | G-0191 (risco aceito em parte) | Post perdido = mensagem perdida; alarme `forward_falhou` descalibrado |
| CG-03 | Sem `message_id`; `datetime_post` = hora do Post | suposta | dono (pergunta 4, DN-01) | G-0119 (`tipos.py:27`) | Formato diferente dá 422 → 424 no gateway (`gl-gateway/app/main.py:524`) |
| CG-04 | `message_send` não troca o responsável; `message_status` por `/chatguru/acao` | suposta | Danilo, A3.3 (12/11) | G-0037; G-0226 | Relê/restaura delegação; canal real não existe (B1.6/B6.8) |
| CG-05 | Chat de teste e sumidouro; `zVuE` recusa chat sem CPF | suposta | dono (DN-01); Danilo cria o diálogo | SO-02, SO-32 | A3.0–A3.6, A2.4, A2.13, B6.1 sem ensaio |
| CG-06 | Token no corpo, sem IP fixo | suposta | dono (pergunta 10) | — | Muda a autenticação de `ia-mensagem` |
| CG-07 | Janela de 24 h vale; template a custo 0 | suposta | dono (pergunta 8) | — | Lembretes abortam (`jobs.py:171`) |
| CG-08 | Timer de 20 min não re-dispara o `zVuE` | suposta | Danilo, A3.4 (12/11) | — | Reabre B6.5 (+1 semana) |
| CG-09 | Delegação do consultor troca o responsável | suposta | Danilo, A3.5 (12/11) | — | Muda «humano assumiu» e o repasse (B6.3/B6.4) |
| CG-10 | Diálogo «Vou fazer Depois» | fora do MVP | A3.6 | — | Sem efeito no MVP |
| CG-11 | Gatilho fora do horário | fora do MVP | dono (pergunta 13) | — | Plano B: timer no orquestrador |
| CG-12 | 5 vagas de sessão RPA | suposta | dono (pergunta 11) | — | Teto de 10 chats do RPA não cabe |
| RPA-01 | Cookie dura entre renovações | parcial | Danilo, 10/11 noite e 19/11 | SO-28; G-0665 | Sem reconciliador, sem «humano assumiu», sem religar o bot |
| RPA-02 | RPA traz autor e hora da última mensagem do cliente | suposta | Claude, A2.4 (depois do cookie) | — | Aberturas abortam (`estado_pausa.py:95`) |
| RPA-03 | RPA aguenta leitura por turno | suposta | Claude, A2.4 | — | RPA sai do caminho crítico |
| FA-01 | Sem sandbox; só dublê | suposta | dono (comercial) | G-0489 | F3 e ensaio B testam contrato não verificado |
| FA-02 | Limite de consulta é transitório | suposta | dono | — | Repasse sobe; amostra do piloto pode não fechar |
| FA-03 | Proposta aparece em 1–17 min; T8 espera 25 | suposta | dono; tap lido em 16/11 | SO-11; G-0617; R2-008, R2-010 | T8 `indeterminado` mais vezes; `conferir_janela_min` ainda 10 (`facta-on/app/config.py:123`) |
| FA-04 | FACTA digita e averba no domingo | suposta, não medida | dono (pergunta 4); tap 16/11; go 26/11 | DN-30 | Domingo = conversa + repasse |
| FA-05 | Merge #5 põe tap e janela no ar e tira CPF do log | suposta; não está na main | dono, **13/11 >20:30** | SO-11, SO-12; G-0108; G-0017 | Sem tap, sem retornos reais; CPF segue no `uvicorn.access` |
| FA-06 | Matrícula vem do braço; filtro `tem_proposta` | suposta | Claude, H1–H3 antes de B6.2 | G-0058; G-0121 | T5/T7 recusam; piloto digita zero contratos |
| FW-01 | Conta, chave e Tier | suposta | dono, 17/11 | DN-15 | F3 cega; DN-21 |
| FW-02 | Preço por 1M tokens | suposta | Claude, A2.9a/A2.9b | G-0619 | Custo e teto errados |
| FW-03 | p50 ≤ 2 s, p95 ≤ 4 s | suposta | Claude, A2.9a | G-0619 | Timeout → repasse; meta da sombra cai |
| FW-04 | `reasoning_effort:"none"` e `tool_calls` estruturadas | suposta | Claude, A2.9a | — | Trocar de provedor (E-4) |
| FW-05 | Cache de prompt | suposta | Claude, A2.9 | G-0619 | Custo por atendimento sobe |
| FW-06 | ZDR público basta até o DPA | suposta | dono, E-3 em 13/11 | DN-14 | G2 não abre; sombra só ensaio B |
| FW-07 | Host e roteador só-EUA | suposta | Claude, A2.9a; comercial | G-0761 (`config.py:43`, `:175`); G-0013 | Boot recusa outra config; só-EUA segue nominal |
| FW-08 | Modelo 1017 não sai do ar no piloto | suposta | comercial | — | Contingência V4 Pro ou Gemini (mudança de código) |
| FW-09 | Flash passa a F3 | suposta | Claude, F3 prévia 16–18/11; oficial 19→20/11 | — | B8.3; sem correção, no-go |
| VPS-01 | VPS-2 em BHS até 12/11 14:00 | suposta | dono | G-0001 | Nada substitui no #8 e na sombra |
| VPS-02 | 8 GB cabem orquestrador + Phoenix + dublê | suposta | Claude, ensaio e sombra | — | OOM; tirar Phoenix da VPS (decisão do dono) |
| VPS-03 | Peer WG aditivo e nft sem recarregar | suposta | dono `!`, 11/11 noite, só com VPS | G-0015 (sem kit) | Perder SSH da S4 ou derrubar o ISKRA |
| DP-01 | Dataprev fora 20/11 22:00 → 23/11 06:00 | suposta | ninguém de fora; Danilo confere 20/11 21:50 | — | Mudar a janela é mudança de código (`calendario.py:32-33`, `:235`) |
| DP-02 | Dataprev no domingo | suposta | A2.12; tap 16/11 | — | Igual a FA-04 |
| CO-01 | Coolify da S2 gerencia a VPS | suposta | dono + Claude; #8 16/11 >20:30 | SO-34; G-0094, G-0095 | Fica o `deploy-vps.sh` manual |
| CO-02 | VPS puxa do registry da S3 | suposta | dono, antes do #8 | SO-15 | Imagem não chega |
| CO-03 | Disco e carga da S2 aguentam até 23/11 | parcial | Claude, `df` 16 e 23/11 | SO-04 | Disco < 15% bloqueia Redeploy e builds |
| CO-04 | Redeploy único do gateway | suposta | dono + Danilo, **11/11 05:30** | SO-03, SO-06 | Queda E-12 em 11/11 08:30 (DEL:175) |
| NT-01 | ntfy público chega em ≤ 2 min nos dois celulares | suposta | dono + Danilo, A1.7 | G-0099 | Alerta crítico não chega; cliente ntfy não existe (B6.6) |
| PH-01 | Phoenix herda 14 d e só em `127.0.0.1` | suposta | dono + Claude, A4.5 | SO-22 | D-32 falha; G2 fechado |
| PH-02 | Span de teste some em 14 d | suposta | Claude + dono, G2 | SO-22; G-0005 | DN-20 |
| PB-01 | Fulls do pgBackRest ≤ 14 d | suposta | sessão, SO-08 | G-0005; G-0329 | DN-20; encurtar afeta os outros bancos do cluster |
| PB-02 | WAL da S4 arquivando | confirmada em 30/10 | Claude, antes de A4.3a (11/11 13:15) | SO-08 | Não criar `ia_obs` |
| N8-01 | Corpo do webhook não fica nas execuções | suposta | Danilo, A3.8 12/11 13:15 | SO-07, SO-20 | Retenção de 1 d (`!`) ou opção (c) de D-05 |
| N8-02 | n8n alcança `:8114`, `:18110`, `:5678`; S3 dá 403 | suposta | A3.8 e após A4.2 | SO-18 | Corrigir nginx antes de tudo |
| N8-03 | Access injeta identidade no Webhook | suposta | dono (DN-12), 12/11 | — | Disparo bloqueado |
| N8-04 | Credencial `ia-n8n-braco` e rotas no 360 | suposta | Claude, API #4 13/11 12:30 | G-0124 | Braço não lê oferta nem contrato |
| N8-05 | Fluxos novos não agravam a S2 | suposta | Claude, vigia | SO-04 | Espelho, vigia e devolução caem |
| BAT-01 | Batimento lido antes de cada efeito | suposta; sem código | Claude, B1.6b/B6.4 | G-0066; G-0020 | No-go (controle) |
| SUP-01 | Basta a ciência do superior | suposta | dono, 13/11 | DN-14 | Parar B9 e reabrir |
| JUR-01 | Sem jurídico, sem aviso de IA | confirmada (30/10) | dono assina E-3, 13/11 | DN-14 | Sombra com texto real só ensaio B |
| OPR-01 | Substituto e revisor nomeados | suposta | dono, 11/11 | DN-09 | Operador único 8 dias; 29/11 fechado |
| SEN-01 | Token `ia` só no vhost WG | suposta | dono `!`, A4.4 12/11 noite | SO-18 | Quebraria 14 fluxos e o robô |
| S4-01 | `s4-hba.sh` restaura sozinho se errar | suposta; ensaiado só em PG local | dono `!`, 11/11 13:15 | SO-09; F4-024 | Linha errada pode barrar ISKRA/gl360 |

#### 9c.3 Premissas novas que a revisão levantou

| Id | Premissa | Estado | Quem confirma | Prova | Se «não» |
|---|---|---|---|---|---|
| RV-01 | Os CPFs «caso real» do `facta-on` não são de pessoa real | não verificado | dono (DN-23) | G-0118; `historico-pii.md:26` | Remoção da main, reescrita do histórico, portão de PII |
| RV-02 | O ISKRA é o único escritor do gl360 | suposta (fonte: exemplo, não config viva) | dono / leitura do ISKRA (não exportado) | G-0348 (`03-cliente360-iskra.md:25`, `:105`) | RS-29 sem prova; outro escritor fora do desenho |
| RV-03 | A faixa 000.000.0nn/1nn nunca é de cliente | suposta (spike I25) | SO-27 | G-0442 (`pessoas_teste/catalogo.py:37`); G-0738 | Scanners isentam CPF real; persona indistinguível de cliente |
| RV-04 | `delegacao_entregas.nome` é o do consultor | suposta | Claude, contagem | G-0202 (`04-n8n-braco-espelho.md:49`, `:147`) | Nome de cliente vai ao navegador; plano B: só `site_profile_id` |
| RV-05 | `datetime_post` real é RFC 3339 com fuso | não medida | A3.1 | G-0119 (`tipos.py:27`) | Todo Post dá 422 → 424 |
| RV-06 | Só-EUA garantido pelo nome do roteador | suposta | comercial; A2.9a | G-0761 | Precisa conferir `model`/região na resposta ou egress na VPS (G-0013) |

---

## 10. Qualidade da própria revisão

Resumo: 99 arquivos (1.150 KB) ficaram sem leitor. Seis leitores de lacuna (L1–L6) e o crítico de completude trouxeram 40 achados F4 (4 ALTO). Os canários tiveram recall estrito de 28% (5/18) e de 38% (5/13) nos defeitos alcançáveis. A rodada 2 trouxe 23 achados R2 (1 ALTO). O portão local passou duas vezes (3429 testes). Os ensaios dos kits (F2-47) e o canário 5 (F2-46) nunca rodaram.

Como ler: «prova» é `caminho:linha` ou arquivo com trecho. Todos os caminhos `fase*/` são relativos a `/home/danilo/ia-revisao-0911/`. O que não está nas fontes aparece como «não verificado».

### 10.1 Cobertura: arquivos sem leitor e o que foi feito

Fonte: `fase4/cobertura.md` (lista por repositório), `fase4/L1.md`..`L6.md` (escopo de cada leitor de lacuna).

| Grupo (cobertura.md) | Arquivos | KB | Leitor de lacuna | O que saiu | Ainda sem leitor nominal |
|---|---|---|---|---|---|
| bancos-duble | 17 | 116 | L6 | F4-032, F4-033 (MÉDIO), F4-034 | `DECISOES-B2.4-0211.md`, `REVISAO-B2.1-0411.md`, `test_gerar_mappings.py`, `test_camada_a_referencia.py`, `test_spike_i24.py`, `test_cenario.py`, `cloudflare-*.html`, `duble_anon/__main__.py`: não citados em L6; não verificado se lidos |
| ia-atendimento (corpus e agenda) | 29 | 399 | L1 (corpus), L2 (agenda) | F4-001..F4-008; F4-009 (ALTO), F4-010..F4-015 | nenhum: L1 declara escopo `src/ia_atendimento/corpus/` inteiro e `tests/test_corpus*.py` (`fase4/L1.md:3-5`) |
| ia-atendimento-b1-6a | 9 | 209 | L5 | F4-026..F4-029 | `README.md` do ramo: L5 só registra «falta a linha da B1.8» (`fase4/L5.md:20`) |
| ia-atendimento-esteira | 12 | 111 | L3 | F4-016 (ALTO), F4-017..F4-020 | nenhum |
| ia-atendimento-kits-s4 | 22 | 201 | L3, L4 | F4-021..F4-025 | nenhum |
| papel (`/opt/claude/docs/planejamento-ia/`) | 10 | 114 | L6 | F4-030, F4-031 (MÉDIO) | `__pycache__/modelo_custos.cpython-314.pyc` (binário), `estudos/semana-1/README.md`: não citados |
| **Total** | **99** | **1.150** | 6 leitores | 34 achados de leitor (F4-001..F4-034) + 6 do crítico de completude (F4-035..F4-040) | ~10 arquivos sem citação nominal |

Fora da lista de arquivos, o campo `nao_lido` de `fase3/cobertura.json` soma 640 itens em 118 unidades (`fase4/completude.md:16`). O crítico classificou 12 grupos como materiais (`fase4/completude.md` §4, M1–M12). Os principais:

| Id | Lacuna | Material? | Prova |
|---|---|---|---|
| M1 | Nenhuma unidade F2 executou teste: «provado por teste» no consolidado = teste lido | sim | `fase4/completude.md:88` |
| M2 | Bibliotecas não exportadas (pydantic-ai, procrastinate, openai SDK, OTLP) | sim | `fase4/completude.md:89`; afeta G-0085, G-0412, G-0480 |
| M3 | Repositórios não exportados: chatguru-api, ISKRA, gl-painel, cliente360-web, PR #49 do facta-on | sim | `fase4/completude.md:70-74` (costuras K1–K5) |
| M4 | Costuras com um lado só, porque a regra de isolamento proibiu a entrada obrigatória | sim | F4-037; `fase4/completude.md:78` (K9) |
| M12 | Semgrep do gl-gateway e de `tests/` não rodou; sem auditoria de dependências; `insecure-defaults:audit` não rodou | sim | G-0539 (BAIXO, confirmado); `fase4/completude.md:99` |

### 10.2 Recall dos canários e pontos cegos

Fonte: `fase4/recall-canarios.md`. Critério: «sim» = mesmo mecanismo e efeito; «em parte» vale 0,5.

| Canário | Base | Defeitos | Sim | Em parte | Não | Estrito | Alcançável estrito |
|---|---|---|---|---|---|---|---|
| canario-1 | B5.1 (pai de d0ddcb4) | 11 | 3 (A-1, M-1, M-2) | 2 (M-3, M-4) | 6 | 27% | 3/8 = 38% |
| canario-2 | B1.8 R-01 (pai de 34fafcf) | 1 | 1 | 0 | 0 | 100% | 100% |
| canario-3 | B1.4-r2 R2-07/R2-08 (pai de a30fd2c) | 4 | 0 | 0 | 4 | 0% | 0/3 |
| canario-4 | B1.4-r2 R2-02/A1f (pai de 35d22cf) | 2 | 1 (R2-02) | 0 | 1 | 50% | 1/1 |
| canario-5 | B5.7b (F2-46) | — | — | — | — | **não rodou** | — |
| **Total** | | 18 | 5 | 2 | 11 | **28%** (ponderado 33%) | **5/13 = 38%** (ponderado 46%) |

Prova do total: `fase4/recall-canarios.md:59-62`. O único defeito ALTO do gabarito (A-1) foi achado (`:64`). A precisão (achados fora do gabarito) não foi medida (`:84`).

Divergência: o crítico de completude leu o recall por canário e não por defeito («3 reencontrados, 1 parcial», `fase4/completude.md:13`). A conta por defeito acima é a que vale.

Pontos cegos medidos (`fase4/recall-canarios.md:66-79`):

| # | Ponto cego | Defeitos perdidos | Causa |
|---|---|---|---|
| PC-1 | Lacuna de teste: mutante que sobrevive | B-1, B-2, B-3, A1f (4/18) | a unidade recebeu só código de produção |
| PC-2 | Máscara que destrói função (hora, data com hora, grandeza do número) | R2-07a, R2-07b, R2-08a, R2-08b (4/18) | leitores caçam vazamento, não perda |
| PC-3 | Regra que só existe na tabela do contrato | M-7 | contrato 08 §6 não estava ao lado do código |
| PC-4 | Dado que não vai ao modelo, mas é gravado depois | M-6 | leitor não seguiu `Resultado.dados` até o gravador |
| PC-5 | Mesmo resultado por `raise` em vez de `return`; `__context__` | M-3, M-4 (em parte) | controle por exceção ficou meio visto |
| PC-6 | Recusa na entrada sem registro nem span | B-4 | sem leitor dedicado |

### 10.3 O que a rodada 2 cobriu e o que ainda pode estar escondido

Fonte: `fase4/consolidado-r2.md:3` («5 passes dirigidos»). Cada passe mira um ponto cego.

| Passe | Ponto cego | Achados | Mais grave | Prova |
|---|---|---|---|---|
| P1 | PC-2 máscara | R2-001..R2-007 | R2-001 ALTO: pendente «dd/mm hh:mm» derruba o turno no `auditar_prompt` | `contexto.py:266,316`; `mascara.py:50,145` |
| P2 | PC-3 contrato | R2-008..R2-014 | R2-008, R2-011 MÉDIO (`posse_real` sem produtor na main) | `ferramentas/modo.py:170-174` |
| P3 | PC-4 dado persistido | R2-015, R2-016 | R2-015 MÉDIO: anotação grava nome e texto livre em claro por 365 d | `api/anotacoes.py:83-85` |
| P4 | PC-1 teste que não reprova (mutação mental) | R2-017..R2-020 | R2-017, R2-018 MÉDIO | `gateway.py:338-346`, `:431-439` |
| P5 | costuras de entrada (recall inverso) | R2-021..R2-023 | R2-021, R2-022 MÉDIO | `api/anotacoes.py:44-62`; `api/eventos.py:46` |

Saldo: 23 achados, 11 confirmados e 12 confirmados em parte; 1 ALTO, 15 MÉDIO, 7 BAIXO (`fase4/consolidado-r2.md:5-8`).

O que ainda pode estar escondido:

- **Critério de parada não atingido.** O PLANO para a Fase 4 com cobertura 100% e 0 CRÍTICO/ALTO novo (`PLANO-REVISAO-0911.md`, Fase 4). A rodada 2 trouxe R2-001 ALTO e era a última permitida.
- **PC-2 rendeu achados novos depois das correções R2-07/R2-08.** A máscara ainda é a área mais fértil (R2-001..R2-007).
- **PC-5 e PC-6 sem passe próprio.** P4 só confirmou que `CORRIGIVEL` tipado e `__context__` limpo têm teste (`fase4/r2-P4.md:54,61`). Recusa sem registro (B-4) não teve passe.
- **P4 foi mutação mental, não mutação executada.** Nenhum mutante rodou.
- **Lacunas declaradas pelos próprios passes:** 23 no total (P1 7, P2 7, P3 2, P4 4, P5 3; `fase4/consolidado-r2.json`, chave `lacunas`).
- **Precisão nunca medida.** Não se sabe quantos achados vivos são falsos positivos que sobreviveram à verificação.

### 10.4 Portão local (check-x2)

Fonte: `fase4/check-x2.out`, `fase4/check-rodada-1.log`, `fase4/check-rodada-2.log`. Rodou `scripts/check.sh` na cópia `wt/ia-9a4baca` (main `9a4bacab`) com o irmão `wt/duble-ca3ed2c` (`check-rodada-1.log`, cabeçalho).

| Rodada | Início | Carga | Resultado | Duração | Prova |
|---|---|---|---|---|---|
| 1 | 14:25:55 | 3,21 | rc=0; 3429 passed, 1 skipped, 1 xfailed | 274,9 s | `fase4/check-x2.out:1-7` |
| 2 (sob carga) | 14:30:43 | 14,10 | rc=0; 3429 passed, 1 skipped, 1 xfailed | 356,6 s | `fase4/check-x2.out:8-14` |

- **Sem instabilidade entre rodadas.** O diff dos dois logs só difere na criação do `.venv` e no tempo.
- **Também passaram:** `uv lock --check`, ruff, `varredura.py` («limpa»), gitleaks (172 commits, «no leaks found»), sha256 da 0001, `gerar_0002 --verificar`, `gerar_pessoas_teste --verificar`, `conferir_catalogo` (`check-rodada-1.log`).
- **Teste pulado:** `tests/test_corpus_revisao2.py:248`, `test_atualizar_duble_regrava_e_verifica`, por `could not import 'yaml'`. Ele é o único teste do script `scripts/atualizar_duble.py` (regrava e `--verificar`). `yaml` não está no `pyproject.toml`. Logo, esse caminho nunca roda no portão.
- **XFAIL esperado:** `tests/test_gasto_pendente.py::test_gasto_do_dia_soma_passos_em_brt_e_todos_os_modos` (R1-14, depende da B1.6).
- **Aviso:** `PytestAssertRewriteWarning` em `tests.apoio_b12` (`check-rodada-1.log:84-87`).
- **Faltou:** o PLANO pede ×3 (F2-48 em `fase0/unidades.json`); rodaram 2. A suíte rodou só na main; B1.6a+main seguem sem portão conjunto (G-0076 ALTO).

### 10.5 O que nunca rodou

| Unidade / item | Pedido pelo PLANO | Estado | Prova | Efeito |
|---|---|---|---|---|
| F2-47 ensaios dos kits s4 e gateway (1×, 2× seguidas, interrompido, desfazer) | §4 Fase 2 | **nunca rodou**: não há `fase2/leituras/F2-47.md` | F4-035 ALTO; `fase4/completude.md:30` | «Provado em ensaio» vazio na revisão inteira; RS-08 sem prova; G-0110 só lido |
| F2-46 canário 5 (B5.7b) | §4 Fase 4 | **nunca rodou** | F4-038; `fase4/completude.md:162` | recall sem o 5º ponto |
| F2-48 check.sh ×3 | §4 Fase 0/2 | **parcial**: ×2 na Fase 4 (§10.4) | `fase4/check-x2.out` | sem 3ª rodada |
| F2-48 matriz papel × tabela × privilégio por `has_table_privilege` em Postgres descartável | §4 Fase 2 | **não gerada como matriz** | `fase4/completude.md:52` (RS-12) | ver nota abaixo |
| F2-48 simular `ia_app` chamando `fn_texto_podar(7,1,1)` | F2-48 em `fase0/unidades.json` | **nunca rodou** | idem | não verificado |
| F2-48 ProvedorFalso `vistos` nas pessoas_teste, por fase | lente «o que o modelo vê» | **nunca rodou** | idem | RS-03: o que o modelo vê por fase não foi medido |
| Varredura de histórico git | §4 Fase 0 | **feita depois**, em 5 dos 6 repositórios | `fase4/historico-pii.md` | F4-036 fechado em parte; cliente360-web não varrido |
| Semgrep gl-gateway e `tests/`, auditoria de dependências, `insecure-defaults` | §4 Fase 0 | **nunca rodou** | G-0539; `fase4/completude.md:99` | linha de base incompleta |

Nota sobre Postgres descartável: a suíte do portão sobe `postgres:18` quando não há `IA_TESTE_PG_HOST` (`src/ia-atendimento/tests/conftest.py:26-37`). `tests/test_esquema.py:156-165` afere privilégios de `ia_app` por `has_table_privilege` e `has_schema_privilege`. Isso passou nas duas rodadas. Mas cobre só `ia_app` e só privilégios proibidos. A matriz completa de papéis, comparada com F2-17, não existe. Se a rodada usou contêiner ou serviço externo: não verificado.

Histórico git: ver F4-036 no §5 e DN-23 no §9a.2.

### 10.6 Troca de modelo Fable → Opus às ~13:00 de 10/11

Prova: `custo/CUSTO-TOKENS.md`, nota «O limite do Fable acabou às ~13:00 de 10/11; daí em diante os votos sem modelo fixo rodaram em Opus 5.5».

- **Autorizada.** O dono aprovou «julgamento em Fable e Opus» (`PLANO-REVISAO-0911.md` §8, linha 140).
- **Como os votos eram montados.** A lente «b» (tentar derrubar) tinha `opus` fixo; as lentes «a» e «c» usavam o modelo da sessão (`wf/ia-revisao-0911-verif-graves.js:45,48`; idem `verif-medios.js` e `verif-restricoes.js`).
- **Efeito.** Antes das 13:00, os 3 votos misturavam Fable e Opus. Depois, os 3 votos ficaram em Opus. A independência entre verificadores caiu.
- **Fase 4 inteira rodou depois da troca.** Crítico de completude, L1–L6, rodada 2 e seus verificadores começaram após 14:00 (horários de `fase4/`).
- **Não verificado:** quais grupos G-nnnn foram votados antes e depois das 13:00. A tabela de custo (medida às 13:46) não traz linha Opus na Fase 3d, embora `verif-medios.js:45` peça `opus`. Causa não verificada.

### 10.7 Limites da revisão

| Limite | O que não foi lido | Prova | Consequência |
|---|---|---|---|
| Kan | quadro de gestão; atos de 09/11 | `fase4/completude.md:25` (F1-02, F1-03, F1-05, F1-54 em `nao_lido`) | pergunta 1 do PLANO só parcial |
| Produção | S2, S4, Coolify, n8n, nginx, Phoenix, GitHub vivo | `fase4/completude.md:93` (M6, ~60 itens) | todo «NÃO VERIFICÁVEL»; 27 sondas só-leitura em `fase4/completude.md:108-140`, reunidas com as do DEL em SO-01..SO-34 (§9b); a sessão principal roda, o dono só com `!` quando o classificador barrar |
| Repositórios fora da exportação | chatguru-api, ISKRA, gl-painel, cliente360-web, PR #49 | K1–K5 (`fase4/completude.md:70-74`) | G-0036, G-0129, G-0348, G-0188 só no papel |
| Bibliotecas | pydantic-ai, procrastinate, openai SDK, OTLP | M2 | alcance real de G-0085 e RS-03 em `procrastinate_jobs` |
| Denylist | diálogos, personas, mappings, corpus | M10 | só por `piiscan`, que não serve de portão (G-0103) |
| 128 RG | sem tabela única nem vocabulário comum | F4-039; consolidado cita 54 RG | estado por RG fica espalhado em F1-53..F1-58 |
| Rastreabilidade | leitores sem Grep/Glob, shell fora de script | F4-040 | buscas de ausência sem registro reprodutível |

### 10.8 O que uma próxima rodada deveria fazer

1. **Rodar F2-47 e o resto de F2-48.** Ensaios dos kits s4 e gateway (1×, 2×, interrompido, desfazer); matriz completa por `has_table_privilege` em Postgres descartável; ProvedorFalso `vistos` por fase. Sem isso, «provado em ensaio» segue vazio (F4-035).
2. **Dar teste junto com código a cada unidade.** PC-1 custou 4/18 do recall. A unidade precisa do arquivo de teste e de mutação executada (não mental) nos módulos dos ALTO vivos.
3. **Rodar o canário 5 (F2-46) e medir precisão.** Exportar o commit pai da B5.7b e amostrar achados vivos para contar falsos positivos.
4. **Passes dirigidos aos pontos cegos que sobraram.** PC-5 (controle por exceção) e PC-6 (recusa sem registro) não tiveram passe. Repetir P1 na máscara, que rendeu ALTO (R2-001).
5. **Fechar a 3ª rodada do portão e o teste pulado.** Instalar `yaml` no ambiente de teste (ou declará-lo) e rodar `check.sh` ×3. Rodar o portão também em B1.6a+main (G-0076).
6. **Completar a linha de base.** Semgrep no gl-gateway e em `tests/`, auditoria de dependências, `insecure-defaults`, e varredura de histórico do cliente360-web (G-0539, F4-036).
7. **Ler Kan e produção pelas sondas SO-01..SO-34 (§9b).** A sessão principal roda por script; o dono com `!` só quando o classificador barrar. A revisão incorpora só forma e contagem.
8. **Fixar o modelo de cada lente de verificação.** Registrar o modelo de cada voto por grupo, para que uma troca como a das 13:00 não reduza a independência sem rastro.

---

## Anexo A. Números da revisão

### A.1 Agentes por fase

Fonte: `custo/CUSTO-TOKENS.md` (medido em 10/11 13:46 BRT). A coluna conta arquivos de registro do workflow inteiro. Fase 3b ainda tinha ~10 agentes rodando na medição.

| Etapa | Agentes | Modelos | Saída escrita |
|---|---:|---|---|
| Crítica do plano v1 | 4 | Sonnet 5.5 | — |
| Crítica do plano v2 | 3 | Fable 5.1 | — |
| Fase 0: base e unidades | 9 | Fable 5.2, Opus 5.5, Sonnet 5.5 | `fase0/` (manifesto, inventários, matriz, premissas) |
| Fases 1, 2, 2b: leitores | 119 | Fable 5.2, Opus 5.5, Sonnet 5.5 | 63 arquivos `fase1/leituras/`, 56 `fase2/leituras/` (41 F2, 2 F2-21a/b, 9 F2b, 4 F2-C) |
| Fase 3a: fusão | 20 | Fable 5.2, Sonnet 5.5 | 762 grupos |
| Fase 3b: verificação graves | 954 | Fable 5.2, Opus 5.5, Sonnet 5.5 | votos dos grupos graves |
| Fase 3c: verificação restrições | 631 | Fable 5.2, Opus 5.5 | votos por RS |
| Fase 3d: verificação médios | 255 | Fable 5.2, Sonnet 5.5 | votos dos MÉDIO |
| Sessão principal | 2 | Fable 5.1, Fable 5.2, Opus 5.5 | orquestração |
| Fase 4: L1–L6, crítico de completude, rodada 2 (P1–P5) e verificadores | não medido | Opus 5.5 (depois das 13:00, §10.6) | 40 F4 + 23 R2 |
| Fase 5: seções s2–s7 e esta montagem | não medido | não verificado | este documento |

### A.2 Achados por fase e estado

**Fase 3** (`fase3/consolidado.md`): 762 grupos, 0 com voto faltando.

| Estado | CRÍTICO | ALTO | MÉDIO | BAIXO | Total |
|---|---:|---:|---:|---:|---:|
| confirmado | 0 | 46 | 185 | 97 | 328 |
| confirmado em parte | 0 | 1 | 51 | 142 | 194 |
| não existe: critério de aceite | 0 | 21 | 50 | 27 | 98 |
| aberto: decisão não achada | 0 | 0 | 7 | 1 | 8 |
| risco aceito em parte | 0 | 0 | 6 | 12 | 18 |
| risco aceito | 0 | 0 | 0 | 6 | 6 |
| não verificável | 0 | 0 | 1 | 0 | 1 |
| baixo não amostrado | 0 | 0 | 0 | 89 | 89 |
| contestado | 0 | 0 | 0 | 4 | 4 |
| não confirmado | 0 | 0 | 0 | 5 | 5 |
| refutado | 0 | 0 | 0 | 10 | 10 |
| peça existe (refutado) | 0 | 0 | 0 | 1 | 1 |
| **Total** | **0** | **68** | **300** | **394** | **762** |

Por tipo (campo `tipo`): papel 196, ausência de controle 141, código 101, não existe 99, estado desatualizado 93, costura 63, kit 37, risco aceito 32. O leitor marcou 1 CRÍTICO; a verificação o baixou a ALTO. Dos 130 ALTO do leitor, 61 caíram a MÉDIO e 3 a BAIXO (`fase3/consolidado.md`, tabela «Gravidade do leitor → final»).

**Fase 4** (`fase4/consolidado-f4.md`): 40 achados.

| Estado | CRÍTICO | ALTO | MÉDIO | BAIXO |
|---|---:|---:|---:|---:|
| confirmado | 0 | 4 | 14 | 7 |
| confirmado em parte | 0 | 0 | 2 | 11 |
| não existe: critério de aceite | 0 | 0 | 2 | 0 |

**Rodada 2** (`fase4/consolidado-r2.md`): 23 achados.

| Estado | CRÍTICO | ALTO | MÉDIO | BAIXO |
|---|---:|---:|---:|---:|
| confirmado | 0 | 1 | 8 | 2 |
| confirmado em parte | 0 | 0 | 7 | 5 |

**Fechamento das camadas anteriores** (§8): 128 RG (23 com prova, 45 só no papel, 40 abertos, 9 superados, 11 refutados); 32 D-nn (4 com prova, 1 parcial, 15 só no papel, 10 abertas, 2 superadas); 20 AJUSTAR (16 sem adoção, nenhum com dono e data).

**Qualidade** (§10): recall estrito dos canários 28 % (5/18), 38 % nos alcançáveis (5/13); precisão não medida; portão local 2× verde (3429 testes); F2-47 e F2-46 nunca rodaram.

### A.3 Gasto de tokens

Fonte: `custo/CUSTO-TOKENS.md`. Escopo: crítica do plano e Fases 0 a 3, medido às 13:46 de 10/11. Fases 4 e 5 não medidas.

| Grupo | Tokens |
|---|---:|
| Crítica do plano (v1 e v2) | 26,1 milhões |
| Fase 0 | 26,3 milhões |
| Leitores (Fases 1, 2, 2b) | 225,4 milhões |
| Fusão (3a) | 6,1 milhões |
| Verificação (3b, 3c, 3d) | 890,7 milhões |
| Sessão principal | 16,4 milhões |
| **Total medido** | **1.194,9 milhões** |

Saída escrita pelos modelos: 11,5 milhões de tokens. Cerca de 86 % do total é leitura de cache. A verificação custou ≈ 75 % do total.

---

## Anexo B. Prova principal por id (antigo §7.4)

Gerada de `fase3/grupos/G-nnnn.json` (primeiro membro, duas primeiras provas) e de `fase4/consolidado-f4.json`/`consolidado-r2.json` (campo `onde`). Caminhos relativos a `~/ia-revisao-0911/src/` quando de código. Nomes de pessoas nas citações foram trocados pelo papel.

| Id | Grav. | Estado | Título | Prova principal |
|---|---|---|---|---|
| F4-006 | BAIXO | confirmado em parte | Faixas sintéticas de telefone e número aceitam formato de dado real | src/ia_atendimento/corpus/pii.py:55-57,64 |
| F4-016 | ALTO | confirmado | Compose da esteira não sobe a main: api:app inexistente e env de 30/10 | src/ia-atendimento-esteira/docker-compose.yml l.42-51 e l.86-94 |
| F4-018 | MÉDIO | confirmado | Conflito de pyproject/uv.lock no merge da esteira apaga dependências | pyproject.toml e uv.lock (main x esteira) |
| F4-019 | BAIXO | confirmado em parte | Esteira e kit A4.3 só em ramos locais não empurrados | feat/esteira (9e1afe39, ahead 2) e kits/s4 (148cc72d, ahead 1) |
| F4-020 | BAIXO | confirmado | Amostra de CPF de DV válido fora da faixa sintética nos ramos | src/ia-atendimento-{esteira,kits-s4}/tests/test_varredura.py l.28 e l.91 |
| F4-021 | MÉDIO | confirmado em parte | Roteiro manda desfazer A4.3 pelo texto v1 do estudo E, não pelo desfazer.sh | ROTEIRO-DE-ACAO.md:706 × estudos/semana-1/e-infra-s4-vps.md:393 × kits/s4/desfazer.sh:28 |
| F4-022 | MÉDIO | confirmado | Kit que roda é cópia solta em retomada-2809, sem trava de hash; ramo kits/s4 sem push | kits/s4/README.md:26-29; ROTEIRO-DE-ACAO.md:324; fase0/MANIFESTO.md:36 |
| F4-023 | MÉDIO | não existe: critério de aceite | A4.3a sem comando para o pg_dump -s exigido no aceite; provar.sh aborta sem VPS | kits/s4/provar.sh:65; kits/s4/s4-hba.sh:153; ROTEIRO-DE-ACAO.md:705-706 |
| F4-030 | MÉDIO | confirmado | q.sh: read-only só por set de sessão como superusuário s4_super | consultas/conversao-2910/q.sh:3 |
| F4-031 | MÉDIO | confirmado | Medição de conversão expõe nome e desempenho de consultor | consultas/conversao-2910/a2.sql:1,9-10; a5.sql:15 |
| F4-032 | BAIXO | confirmado em parte | atualizar_pessoas_teste grava sem validar que o dado é sintético | bancos-duble/scripts/atualizar_pessoas_teste.py:32-42,62-63 |
| F4-033 | MÉDIO | confirmado | anon --k sem piso desliga o k-anonimato | bancos-duble/anonimizador/duble_anon/cli.py:162,129-143 |
| F4-034 | BAIXO | confirmado em parte | anon aceita --seed fixo em captura real | bancos-duble/anonimizador/duble_anon/cli.py:163,174; anonimizar.py:258-259 |
| F4-035 | ALTO | confirmado | Unidades de execução F2-47 (kits) e F2-48 (check.sh ×3, PG descartável, vistos) nunca rodaram: o estado «prova | fase0/unidades.json (F2-47, F2-48) × fase3/cobertura.json × fase2/leituras/ |
| F4-036 | ALTO | confirmado | Histórico git dos 6 repositórios nunca foi varrido por gitleaks, contra o PLANO; o CPF isento no .gitleaksigno | fase0/baseline.md (seção a) × PLANO §4 Fase 0 |
| G-0001 | ALTO | não existe: critério de aceite | VPS OVH BHS não existe e A1.3 vence hoje (RG-041 aberto) | ROTEIRO-DE-ACAO.md — "VPS OVH BHS \| não iniciada; **prazo 03/11 vencido; pendente do dono" ; estudos/PLANO-REVISAO-0911.md — "A1.5 VPS OVH BHS \| 12/11 14:00 \| deploy do orquestrador" |
| G-0004 | ALTO | confirmado | Regra 5 diz que o web não faz deploy no merge; a memória diz que faz | ROTEIRO-DE-ACAO.md:45 — "**Web não faz deploy no merge** (`subir-web-prod.sh`)" ; ROTEIRO-DE-ACAO.md:160 — "o deploy do web segue o #7, 17/11, por `!`" |
| G-0005 | ALTO | confirmado | D-32 exige prova de eliminação em 14 d que o papel diz não cumprir | ROTEIRO-DE-ACAO.md:43 — "o texto mascarado do Phoenix sobrevive nos fulls pelo aceite do dono de 30/10" ; ROTEIRO-DE-ACAO.md:43 — "provar que o texto mascarado no Phoenix e nos fulls/backups é eliminado em 14 d" |
| G-0008 | ALTO | confirmado em parte | Painel prevê escrita em produção sem kit nomeado ou com kit inexistente (PD-2) | ROTEIRO-DE-ACAO.md — "Kit em `~/retomada-2809/fila-2910/ia/<passo>/` com **ensaio**" (PD-2, l.427) ; ROTEIRO-DE-ACAO.md — "Claude (kit) + DONO (`!` da importação) + [operador TI]" (A3.8, l.321) |
| G-0011 | ALTO | confirmado | Bloco de A4.6 grava o ledger fora da transação da migração | ROTEIRO-DE-ACAO.md:722 — "SET ROLE ia_owner; INSERT INTO ia.migracao (migracao_id,checksum) VALUES ('0001_esquema'" ; ROTEIRO-DE-ACAO.md:726 — "INSERT INTO ia.migracao (migracao_id,checksum) VALUES ('0002_procrastinate'" |
| G-0012 | ALTO | não existe: critério de aceite | Kit s4/migrar.sh de A4.6 não existe | ROTEIRO-DE-ACAO.md:717 — "kit `s4/migrar.sh` a escrever (Claude, 0,5 d, ensaio local)" ; ROTEIRO-DE-ACAO.md:868 — "«sim» nomeado na 0005 (`DROP CONSTRAINT`); kit `s4/migrar.sh`" |
| G-0013 | ALTO | não existe: critério de aceite | VPS sem política de saída e sem critério de aceite de egress | ROTEIRO-DE-ACAO.md:708 — "tabela própria `inet ia_vps` com janela de reversão" ; estudos/semana-1/e-infra-s4-vps.md:316 — "type filter hook input priority filter; policy drop;" |
| G-0014 | MÉDIO | confirmado | Sumidouro guarda o Post inteiro por 7 dias, sem purga e sem trava contra chat real | kits/gateway/rotas-ia.sh:27 — "sumidouro do chat da TI (A3.0); guarda o Post inteiro por 7 dias" ; ROTEIRO-DE-ACAO.md:626 — "contar Posts com `chat_id` ≠ chat de teste (escopo do diálogo)" |
| G-0015 | ALTO | confirmado | Passos de infra A4.2, A4.4, A4.5, A4.7 e A4.8 sem kit nem ensaio local | ROTEIRO-DE-ACAO.md:696 — "Sem mudança nos comandos." ; ROTEIRO-DE-ACAO.md:700 — "ninguém adapta script ao vivo" |
| G-0016 | ALTO | confirmado | A6.6b vencida sem entrega: worker do compose aponta `fila.app`, que não existe no nível do módulo | ROTEIRO-DE-ACAO.md:807 — "Worker no compose e push da esteira (v3.3) · Claude · 0,5 d · **até 08/11**" ; src/ia-atendimento-esteira/docker-compose.yml:96 — "command": ["procrastinate", "--app=ia_atendimento.fila.app", "worker"] |
| G-0017 | ALTO | confirmado | B3.1 e B3.2 contradizem o mapa sobre dia e hora do merge do facta-on | ROTEIRO-DE-ACAO.md:947 — "portão de disco da S2 (PD-3) e hora **12:30–14:00**; merge do PR de A6.4" ; ROTEIRO-DE-ACAO.md:952 — "o merge é deploy: **depois das 20:30** do dia 10/11" |
| G-0018 | MÉDIO | confirmado | Merge = deploy no facta-on sem trava técnica, com PRs não-rascunho abertos | ROTEIRO-DE-ACAO.md:855 — "a proteção técnica da `main` é ação do dono, D-09, pendente" ; fase0/MANIFESTO.md:96 — "#16 feat/vendedor-por-intencao draft=false mergeable=UNKNOWN" |
| G-0020 | ALTO | confirmado | D-15 sem saída quando a vigia morreu: repasse trava e ninguém devolve | ROTEIRO-DE-ACAO.md:1063 — "ausente ou > 90 s ... a IA **não age** (fail-closed, D-15) e alerta; a vigia continua devolvendo" ; ROTEIRO-DE-ACAO.md:1066 — "a vigia não tem regra para `repassando` com o orquestrador vivo e o n8n fora" |
| G-0022 | ALTO | confirmado | Falhas provocadas de 24/11 caem dentro da sombra com modo global sombra | ROTEIRO-DE-ACAO.md:1142 — "Falhas provocadas em 24/11 depois das 15:00 (com `bloqueio_entrada`)" ; ROTEIRO-DE-ACAO.md:1142 — "sombra de **23/11 08:00 a 25/11 12:00** (2,5 dias)" |
| G-0023 | ALTO | não existe: critério de aceite | Parada dura sem comando, prazo de decisão nem responsável noturno | ROTEIRO-DE-ACAO.md:1183 — "parada dura (`modo=sombra`; (v3) vale para o atendimento já aberto" ; ROTEIRO-DE-ACAO.md:1101 — "o seletor de `modo` fica por `PUT` autenticado do TI" |
| G-0024 | MÉDIO | confirmado | B10.1 exige F3 >= 95% que não existe sem a chave do provedor | ROTEIRO-DE-ACAO.md:1123 — "só I1–I9 com `ProvedorFalso`, registrado no go/no-go" ; ROTEIRO-DE-ACAO.md:1165 — "F3: **I1–I9 sem nenhuma falha** e ≥ 95% de desfecho/intenção corretos" |
| G-0026 | MÉDIO | confirmado em parte | Padrão 9 diz chave AES inutiliza ia_obs, contradiz regra 3 e D-32 | ROTEIRO-DE-ACAO.md:1488 — «`ia_obs` no pgBackRest (chave AES descartada = texto inútil)» ; ROTEIRO-DE-ACAO.md:43 — «o texto mascarado do Phoenix sobrevive nos fulls pelo aceite do dono» |
| G-0028 | MÉDIO | não existe: critério de aceite | Desvio da linha 1 (RPA leitor principal) contradiz linhas 8 e 40 | ROTEIRO-DE-ACAO.md:1330 — «reconciliador RPA ≤ 10 chats como leitor principal; o dono é avisado no checkpoint 1: é contra a decisão (k)» ; ROTEIRO-DE-ACAO.md:1337 — «RPA só reconciliador; devolução mínima por diálogo; alerta a 11 d» |
| G-0030 | MÉDIO | confirmado | Cenário C não propagado: 13/11 e 06/11 no corpo do contrato 01 | 01-gl-gateway.md:236 — "não bloqueia o merge (até o ensaio a seco de 13/11)" ; 01-gl-gateway.md:303 — "só após o ensaio a seco de 13/11 (B6.1) **e** o portão" |
| G-0032 | ALTO | confirmado | D-14 entrega o lead à vigia, mas a vigia não tem regra (R-c2 sem decisão); lead preso após 30 min | 04-n8n-braco-espelho.md:338 — "o lead fica com a recuperação humana e a vigia (08 §7.2)" ; 04-n8n-braco-espelho.md:382 — "Hoje não há regra: R-c é o lease do espelho" |
| G-0033 | MÉDIO | confirmado | Regex da matrícula aceita forma de CPF; guardas só comparam com o CPF do job ou dependem de PR inexistente | 08-orquestrador.md:45 — "nenhum corpo aceita CPF, celular (exceto chat_number" ; 08-orquestrador.md:97 — "^[0-9A-Za-z./-]{1,40}$ [Claude], a confirmar por forma agregada" |
| G-0034 | MÉDIO | confirmado em parte | Seção Desfazer (§10) ignora 0004/0005; sem kit de migração nem de domingo | contratos/08-orquestrador.md:291 — "a 0003 é aditiva e inofensiva sem o código" ; src/ia-atendimento/migrations/0005_domingo_por_config.up.sql:8 — "Desfazer (só com «sim» do dono e sem nenhuma `janela_mensagem`" |
| G-0036 | ALTO | não existe: critério de aceite | Ator 85 não é fixado em nenhuma cláusula do contrato 02 | 02-chatguru-api.md — "atribuição ator 85 \| não é daqui": POST /pessoas/{id}/atribuicoes na cliente360-api ; 02-chatguru-api.md — "PUT /chatguru/rpa/chat/{chat}/delegacao {usuarios:[<id-ator-85>], departamentos:[]}" |
| G-0037 | ALTO | confirmado | Canal.restaurar do 02 devolve a delegação; o 08 delega pela rota | 02-chatguru-api.md — "POST …/chatbot?ligar=true + PUT …/delegacao com o consultor_antes" ; 08-orquestrador.md — "chatbot: Canal.restaurar, retry próprio." |
| G-0039 | MÉDIO | não existe: critério de aceite | Plano B de b não cobre ausência do diálogo pega-tudo | b-receptor-mensagens.md — "O diálogo «pega-tudo» pode não existir** (alto): sem ele, o Post só dispara" ; b-receptor-mensagens.md — "RPA de leitura **só como reconciliador** de chats abertos (exceção à decisão (k)" |
| G-0040 | MÉDIO | confirmado em parte | Corpo do roteiro e do estudo e não reconciliado com ia_owner | e-infra-s4-vps.md — "Faz migrações e Procrastinate no próprio banco. **Sem linha de `pg_hba`" ; e-infra-s4-vps.md — "CREATE DATABASE $1 OWNER $2 TEMPLATE template0 ENCODING 'UTF8'" |
| G-0041 | MÉDIO | confirmado em parte | Phoenix monta o diretório inteiro /etc/ia-s4 (chaves do ia_app e AES) | e-infra-s4-vps.md — "volumes: [\"/etc/ia-s4:/run/ia-s4:ro\"]" ; e-infra-s4-vps.md — "for f in ../ca.crt ia_app.crt ia_app.key ia_app.senha ia_obs.crt ia_obs.key ia_obs.senha" |
| G-0044 | MÉDIO | confirmado em parte | Trava «não repetir T7» e proposta viva do CPF cobertas só por atendimento e janela de 30 min | f-catalogo-ferramentas.md — "t7:{atendimento}:{banco}:{oferta_id}:{oferta_versao}:{tentativa}" ; f-catalogo-ferramentas.md — "sem proposta viva do CPF no banco (/proposta/por-cpf 30 min + pessoas:propostas)" |
| G-0046 | MÉDIO | confirmado em parte | Formalizar 3RN/C6 e chatguru-api sem token na rede da VPS | f-catalogo-ferramentas.md — "Quem entra no vhost WireGuard da VPS digita e envia." ; f-catalogo-ferramentas.md — "o api-s2 hoje publica só as 3 rotas de digitação para o web" |
| G-0047 | ALTO | confirmado | Máscara de PII não cobre o que o estudo proíbe no banco e no prompt | h-roteiro-conversa-memoria.md — "CPF com DV, telefone, e-mail, CEP, UUID/chave aleatória, sequências de 8+ dígitos" ; h-roteiro-conversa-memoria.md — "conta/agência/PIX, matrícula, empregador, margem, data de nascimento, nome da mãe" |
| G-0048 | MÉDIO | confirmado em parte | Janela de 24 h ausente do estudo H: TX-02 às 08:00, link retido, ultimo_cliente_em sem lugar no estado | h-roteiro-conversa-memoria.md — "nada sai; turno roda às 08:00 com prefixo TX-02; exceção só se Q3 liberar" ; h-roteiro-conversa-memoria.md — "flags{janela_aberta, banco_ok, humano_ativo=false, ultimo_envio_em}" |
| G-0049 | MÉDIO | confirmado | ia_app com UPDATE na tabela inteira do ledger, confirmações, cofre e agendamentos | src/ia-atendimento/migrations/0001_esquema.up.sql:438 — "GRANT SELECT, INSERT, UPDATE ON ia.atendimento_resultado, ia.confirmacao, ia.ferramenta_chama ; src/ia-atendimento/migrations/0001_esquema.up.sql:216 — "WHERE ferramenta = 't7' AND estado IN ('reservada', 'enviada', 'em_andamento', 'indeterminado |
| G-0050 | ALTO | confirmado | Checklist de J manda pôr a chave em off às 20:15, contradizendo RS-25 e o código | j-operacao-piloto.md:65 — "Chave: fica ligada até 20:15, depois o job a põe em `off`" ; j-operacao-piloto.md:60 — "0 atendimentos abertos, 0 em `reservado`/`repassando` > 10 min; senão rodar a devolução na hora" |
| G-0052 | MÉDIO | confirmado em parte | Ack e escalonamento ao dono sem mecanismo; tópico ntfy forjável | j-operacao-piloto.md:228 — "Ack = reação ou resposta «ack» no canal, lida pela vigia" ; k-devolucao-lead-cenarios.md:179 — "ack legível por máquina" (listado em «o que fica para depois») |
| G-0058 | ALTO | não existe: critério de aceite | Matrícula: nenhum elo do caminho existe em código e H1-H3 não foram medidas | ESTUDO-D29-ficha-essencial.md — "Ela é obrigatória na digitação (`online.py:4882`)" ; contratos/08-orquestrador.md:97 — "`^[0-9A-Za-z./-]{1,40}$` `[Claude]`, a confirmar por forma agregada" |
| G-0062 | ALTO | confirmado | Plano mestre contradiz decisões de produto da v3.3 | planos/2026-10-29-00-plano-mestre.md — "dentro do gateway de ferramentas, lido de `GET /pessoas/{id}`, e nunca chega" ; ROTEIRO-DE-ACAO.md — "Sem `ficha:ler`, `pessoa:dossie` nem `GET /pessoas/{id}`; nenhum escopo novo" (0.5b, D-29) |
| G-0063 | ALTO | confirmado | sp01 sem nota de precedência: pontos de RG-003/013 (30 turnos, fail-open 60 s, T12 incondicional) seguem vigen | 2026-10-29-01-orquestrador-nucleo.md:3 — "Este documento NÃO autoriza construção. Regra do dono: estudar antes de construir" (cabeçalho sem nota de pr ; 2026-10-29-01-orquestrador-nucleo.md:285 — "entrada_fingerprint = sha256(JSON canônico) de todos os campos menos chat_number" |
| G-0064 | MÉDIO | confirmado | Gasto da main soma atendimento.custo_* por iniciado_em, não Σ passo.custo_brl; teto inerte (RG-004) | src/ia-atendimento/src/ia_atendimento/chave.py:196 — SELECT coalesce(sum(custo_modelo_brl + custo_midia_brl), 0) FROM ia.atendimento WHERE iniciado_em ; src/ia-atendimento-b1-6a/src/ia_atendimento/gasto.py:49 — _SQL_SOMA sum(custo_brl) FROM ia.passo WHERE ocorrido_em |
| G-0066 | ALTO | não existe: critério de aceite | B1.6b inteira não tem código: processador, repasse, Canal, verificador, confirmação, reaper_ledger | src/ia-atendimento-b1-6a/docs/DECISOES-B1.6a-0411.md — "**Tudo da B1.6b**: processador, repasse em etapas, `Canal` (falso e protocolo)" ; planos/2026-10-29-01-orquestrador-nucleo.md — "**Files:** Create `src/ia_atendimento/ledger.py` (v3: era `gateway.py`), `src/ia_atendimento/canal.py`" |
| G-0067 | MÉDIO | confirmado em parte | MONITORAMENTO-DESIGN manda Phoenix atrás do Cloudflare Access e ntfy com servidor próprio + reserva; vigente é | MONITORAMENTO-DESIGN.md:235 — "atrás do Cloudflare Access restrito ao grupo TI; o link «ver bruto» é" ; MONITORAMENTO-DESIGN.md:268 — "Phoenix (`ia_obs`) como ferramenta separada, acesso só TI, link por `trace_id`" |
| G-0070 | ALTO | confirmado | main do gl-gateway sem proteção demonstrada; merge = deploy | gl-gateway/.github/workflows/testes.yml:18 — push em branches [main] dispara o job imagem ; gl-gateway/.github/workflows/testes.yml:58 — if github.event_name == 'push' && github.ref == 'refs/heads/main' |
| G-0072 | ALTO | não existe: critério de aceite | TX-42 (aviso de domingo) não existe no arquivo nem em TX_IDS | vocabulario.py:228 — [f"TX-{n:02d}" for n in range(1, 42)] (para em TX-41) ; ROTEIRO-DE-ACAO.md:813 — "TX-42 (novo, D-18, lote de 11/11; o dono aprova o texto)" |
| G-0073 | ALTO | não existe: critério de aceite | Nenhum texto fixo está no código, só IDs; nada trava o texto do cliente (RS-23) | modulos_fase.py:105 — "TX-32": "taxa e custo total (CET)" (so rotulos de FAQ) ; turno.py:110 — TX_FAQ: Final = frozenset({"TX-32", "TX-33", "TX-39", "TX-40", "TX-41"}) |
| G-0074 | ALTO | confirmado | Tabela única de location do vhost WG no 02 §2 não foi escrita (batimento.json, conferir/por-cpf, 8118 ausentes | 02-chatguru-api.md — "location / { return 403 '{\"ok\":false,\"error\":\"fora_da_allowlist\"}'; }" ; 02-chatguru-api.md — "location = /gateway/ia-repasse { ... }           # contrato 01 §4.2" |
| G-0079 | ALTO | confirmado | Decisão delegada de 10/11 (degrau de 1 dia, piloto 27-30/11) não está no roteiro | decisoes-delegadas.md:27 — "go/no-go **26/11 12:00**; piloto **27–30/11** (4 dias" ; ROTEIRO-DE-ACAO.md:1164 — "B10.1 Reunião e decisão do dono · dono + [operador TI] · ~~19/11~~ (v3.3, dono 04/11) **25/11 17:00**" |
| G-0080 | MÉDIO | confirmado | Spec da B6.4: CAS só troca «aberto», contradiz D-22 (pausado) | ROTEIRO-DE-ACAO.md:1063 — «R-a** orquestrador sem `/readyz` ≥ 10 min ⇒ devolve todos os `aberto` **e `pausado`» ; ROTEIRO-DE-ACAO.md:1063 — «CAS** `UPDATE … SET estado='devolvendo' WHERE chave=? AND estado='aberto'`» |
| G-0082 | MÉDIO | confirmado | Lease de espera faz o lead dormir com a IA (até 96 h), contra a regra do roteiro | src/ia_atendimento/estado.py:64 ; src/ia_atendimento/estado.py:531-536 |
| G-0083 | ALTO | não existe: critério de aceite | Parada dura por gasto e disjuntor por atendimento não existem | src/ia_atendimento/agente.py:99-106 ; src/ia_atendimento/worker.py:49-52 |
| G-0084 | ALTO | confirmado | Virada de mês da chave AES não entra sozinha: exige troca e reinício em 30/11, contra o roteiro | ROTEIRO-DE-ACAO.md — "21:00 a chave AES de dezembro entra sozinha (kit de 18/11)" ; ROTEIRO-DE-ACAO.md — "nenhum `!` em 14–15/11, 20–22/11, na sombra (23–25/11) nem no piloto (26–30/11)" |
| G-0085 | ALTO | confirmado | observabilidade.configurar sem chamador: máscara de logs não ligada | ia-atendimento/src/ia_atendimento/observabilidade.py:258 ; ia-atendimento/src/ia_atendimento/observabilidade.py:267 |
| G-0086 | ALTO | não existe: critério de aceite | Janela 08–20 só conferida na entrada e no lembrete | src/ia-atendimento/src/ia_atendimento/chave.py:250 ; src/ia-atendimento/src/ia_atendimento/api/agendamentos.py:40 |
| G-0087 | ALTO | confirmado | Efeito irreversível já despachado (T7) pode sair com erro repetível/não INDETERMINADO | src/ia_atendimento/ferramentas/gateway.py:309 ; src/ia_atendimento/ferramentas/gateway.py:303 |
| G-0088 | ALTO | confirmado | T5 de 3RN/C6 é classe leitura: em sombra/duble vai à produção com CPF, fora do teto de pagas | src/ia_atendimento/ferramentas/catalogo.py:165 ; src/ia_atendimento/ferramentas/modo.py:170 |
| G-0089 | ALTO | não existe: critério de aceite | Idempotência/ledger de efeito não ligado ao gateway: T7 executa sem reserva | src/ia_atendimento/ferramentas/gateway.py:25 ; src/ia_atendimento/ferramentas/catalogo.py:174 |
| G-0091 | ALTO | não existe: critério de aceite | Rede de recuperação da volta termina em serviços que não existem (tratar_lease_vencido) | ia-atendimento/src/ia_atendimento/worker.py:49 ; ia-atendimento/src/ia_atendimento/jobs.py:131 |
| G-0093 | MÉDIO | confirmado em parte | expirar_parados encerra sem devolver o chat; justificativa não se sustenta e outbox sem publicador | ia-atendimento-b1-6a/src/ia_atendimento/expiracao.py:9 ; ia-atendimento-b1-6a/src/ia_atendimento/expiracao.py:72 |
| G-0094 | ALTO | confirmado | Dockerfile da esteira não constrói a main: faltam migrations/ e fixtures/ | ia-atendimento-esteira/Dockerfile:26 ; ia-atendimento-esteira/Dockerfile:28 |
| G-0095 | ALTO | confirmado | deploy-vps.sh pode anunciar a tag nova no ar sem tê-la trocado | ia-atendimento-esteira/scripts/deploy-vps.sh:90 ; ia-atendimento-esteira/scripts/deploy-vps.sh:104 |
| G-0096 | ALTO | confirmado | Portão de dia de piloto e checklist nas datas antigas (dias-piloto.txt) | ia-atendimento-esteira/config/dias-piloto.txt:3 ; ia-atendimento-esteira/config/dias-piloto.txt:9 |
| G-0097 | ALTO | confirmado | DEPLOY.md manda arquivos 640 em /etc/ia-s4; o código recusa qualquer bit de grupo | ia-atendimento-esteira/docs/DEPLOY.md:62 ; ia-atendimento-esteira/Dockerfile:33 |
| G-0099 | ALTO | não existe: critério de aceite | OPERACAO sem matriz de alertas (destinatário, prazo, ação) | src/ia-atendimento/docs/OPERACAO.md:192 — "geram `alerta ti: contador=…` em WARNING. O log traz só" ; src/ia-atendimento/docs/OPERACAO.md:134 — "sai o alerta `alerta_raciocinio` (log e evento do span `ia.turno`)" |
| G-0101 | MÉDIO | confirmado | Nada obriga allowlist nas rotas ia-*: corpo_campos NULL manda o Post inteiro, assinado | gl-gateway/app/rotas.py:189 ; gl-gateway/app/projecao.py:46 |
| G-0102 | MÉDIO | confirmado | Anonimizador mantem texto livre de 21 campos | bancos-duble/anonimizador/duble_anon/allowlist.yaml:109 ; bancos-duble/anonimizador/duble_anon/allowlist.yaml:120 |
| G-0103 | MÉDIO | confirmado | piiscan nao serve de portao para nome sem denylist | bancos-duble/piiscan/detectores.py:212 ; bancos-duble/piiscan/nomes.py:10 |
| G-0105 | MÉDIO | confirmado em parte | Janela do conferir 20 min no duble x 10 min no facta-on | facta-on/app/config.py:123 ; bancos-duble/docs/DIVERGENCIAS.md:40 |
| G-0106 | ALTO | confirmado | Receita do README sobe facta-on sem guarda nem rede interna | bancos-duble/README.md:38 ; bancos-duble/README.md:50 |
| G-0107 | MÉDIO | confirmado em parte | conferir sem piso no desde e sem autenticação: histórico por CPF com link | facta-on/app/routers/online.py:4869 ; facta-on/app/routers/online.py:4794 |
| G-0108 | ALTO | não existe: critério de aceite | CPF das rotas conferir e por-cpf vai ao log (log() e uvicorn.access) sem filtro | facta-on/app/routers/online.py:4727 ; facta-on/app/routers/online.py:4738 |
| G-0110 | MÉDIO | confirmado | Kit do gateway não confere o próprio sha256 e aceita transporte de ensaio com --confirmo | kits/gateway/lib.sh:16 ; kits/gateway/lib.sh:20 |
| G-0112 | MÉDIO | confirmado | Kit S4 roda de diretório vivo fora do git sem conferir sha256 antes do sim | kits/s4/README.md — "!bash ~/retomada-2809/fila-2910/ia/s4/s4-hba.sh" ; fase0/MANIFESTO.md — "kits/s4 148cc72 (~/wt-ia/ia-atendimento-kits-s4) [origin/main: ahead 1, behind 178]" |
| G-0113 | MÉDIO | confirmado | Senha dos logins sai da S4 contra o que o kit declara; ponte até a DATABASE_URL sem kit | kits/s4/s4-papeis.sh:13 ; kits/s4/s4-papeis.sh:14 |
| G-0114 | ALTO | confirmado | Nome do cliente nunca é conhecido: receptor grava com `nomes=()` fixo e a máscara de nomes não atua em produçã | ia-atendimento/src/ia_atendimento/mensagens.py:284-287 ; ia-atendimento/src/ia_atendimento/conversa.py:123-131 |
| G-0115 | ALTO | não existe: critério de aceite | Turno, Canal e T7 pelo ledger não estão ligados em nenhuma das bases | src/ia-atendimento/src/ia_atendimento/worker.py:52 ; src/ia-atendimento-b1-6a/src/ia_atendimento/worker.py:54 |
| G-0116 | MÉDIO | confirmado | Sem reaper do ledger: linha T7 `reservada`/`enviada` órfã tranca pessoa+banco para sempre | ia-atendimento-b1-6a/migrations/0001_esquema.up.sql:217 ; ia-atendimento-b1-6a/migrations/0001_esquema.up.sql:220 |
| G-0117 | MÉDIO | confirmado | Resposta sem `usage` grava tokens e custo ZERO; `custo_ausente` nunca dispara | ia-atendimento/src/ia_atendimento/turno.py:413 ; ia-atendimento/src/ia_atendimento/agente.py:421 |
| G-0118 | ALTO | confirmado | facta-on: CPFs declarados caso real em comentários e testes, sem portão de PII | facta-on/app/routers/online.py:594 ; facta-on/app/routers/online.py:2005 |
| G-0121 | ALTO | confirmado | POST /atendimentos não aceita matricula (D-29): 422 | src/ia_atendimento/api/atendimentos.py:38-46 ; src/ia_atendimento/estado_entrada.py:33 |
| G-0123 | ALTO | não existe: critério de aceite | Sentido orquestrador para n8n não existe: sem publicador, sem repasse | ia-atendimento-b1-6a/src/ia_atendimento/espelho.py:5 ; ia-atendimento-b1-6a/src/ia_atendimento/espelho.py:23 |
| G-0124 | ALTO | confirmado | Os 5 escopos da credencial da IA alcançam 19 operações, com enumeração em lote e segunda escrita | cliente360-api/src/c360api/contrato/cliente360.json:3238 ; cliente360-api/src/c360api/contrato/cliente360.json:3350 |
| G-0126 | ALTO | confirmado | Destinos recusa http fora de loopback, mas os vhosts WG do papel são http://10.90.0.2 | ia-atendimento/src/ia_atendimento/ferramentas/modo.py:97 ; ia-atendimento/src/ia_atendimento/ferramentas/modo.py:43 |
| G-0127 | ALTO | confirmado | Rota do T7 (/proposta/formalizar) fora do vhost WG e do contrato 05 | ROTEIRO-DE-ACAO.md — "Spec = tabela única do 02 §2 (+ `/facta-online/proposta/conferir`, `…/por-cpf`, `/ia/batimento.json`" ; ROTEIRO-DE-ACAO.md — "sob a **allowlist fechada do 02 §2** (tabela única dos vhosts 8093/8114/8118; `location / → 403`)" |
| G-0128 | MÉDIO | confirmado | Origem c360_api/web grava modo (inclusive real) no orquestrador; só o BFF barra | ia-atendimento/src/ia_atendimento/api/config_rotas.py:37 ; ia-atendimento/src/ia_atendimento/api/config_rotas.py:47 |
| G-0129 | ALTO | não existe: critério de aceite | Emissor ao ChatGuru não existe (Canal, nota, assumir, restaurar) | ia-atendimento/src/ia_atendimento/jobs.py:125 ; ia-atendimento/src/ia_atendimento/jobs.py:128 |
| G-0130 | MÉDIO | confirmado em parte | Envio incerto sem regra no 08 nem valor no DDL; chave de saída diverge entre 02 e código | contratos/02-chatguru-api.md — "O orquestrador grava o passo `indeterminado` e **nunca reenvia**" ; contratos/02-chatguru-api.md — "Chave de saída `turno:{atendimento_id}:{n}` gravada **antes** do envio" |
| G-0131 | ALTO | confirmado | Execução morta no meio de T12/assumir/restaurar: `enviada` órfã vira `indeterminado` (terminal) para qualquer  | ia-atendimento-b1-6a/src/ia_atendimento/ledger.py:509 ; ia-atendimento-b1-6a/src/ia_atendimento/ledger.py:428 |
| G-0152 | MÉDIO | confirmado | PR #49 do tap dado como concluído mas em conflito com a main | fase0/MANIFESTO.md:96 — "#49 feat/tap-retornos draft=true mergeable=CONFLICTING" ; ROTEIRO-DE-ACAO.md:797 — "PR em rascunho, não mesclar (merge = deploy; só em B3.1)" |
| G-0164 | MÉDIO | confirmado | Batimento: folga de 15 s sobre timer de 60 s; relógio e AccuracySec não escritos | ROTEIRO-DE-ACAO.md:1063 — "timer systemd na S2, 60 s, Python stdlib, `MemoryMax`, `OOMScoreAdjust` baixo, `Persistent=true`" ; contratos/08-orquestrador.md:261 — "a VPS lê a cada 15 s" e "a idade oscila de 0 a 60 s" |
| G-0188 | MÉDIO | confirmado em parte | Painel-dev pode alterar invariantes das rotas ia-* | contratos/01-gl-gateway.md:30 — "gl_gateway tem SELECT na tabela; só o humano escreve em rotas" ; contratos/01-gl-gateway.md:31 — "insere só 6 colunas; atualizar_rota só toca 6 colunas" |
| G-0195 | MÉDIO | confirmado | SELECT direto em sob_ia expõe chat_number aos dois papéis | contratos/04-n8n-braco-espelho.md:18 — "PII só por funções `SECURITY DEFINER`; matriz mínima provada com os logins novos" ; contratos/04-n8n-braco-espelho.md:209 — "chat_number     text,  -- PII: some quando a linha é terminal" |
| G-0203 | MÉDIO | não existe: critério de aceite | Nenhum artefato existe: view, kit DDL, fluxos, vigia e ensaio S1-S6 | contratos/04-n8n-braco-espelho.md:3 — "**Nada foi lido nem escrito na S2 nesta etapa**; o que não foi medido é HIPÓTESE" ; contratos/04-n8n-braco-espelho.md:62 — "aparece em `execution_data`? Medir com `SELECT position('ZZ-MARCADOR-0000'" |
| G-0204 | MÉDIO | confirmado | Batimento: relógio de comparação e tolerância a desvio não definidos | 04-n8n-braco-espelho.md:385 — "ausente ou **`gerado_em` > 90 s**" ; 04-n8n-braco-espelho.md:385 — "`allow 10.90.0.5`" |
| G-0214 | MÉDIO | confirmado | Limite de 90 s do batimento sem relógio definido; única verificação de relógio tolera ±300 s | contratos/08-orquestrador.md:261 — "`gerado_em` **> 90 s** ⇒" ; contratos/08-orquestrador.md:358 — "relógios da S2 e da VPS dentro de ± 300 s (assinatura)" |
| G-0216 | MÉDIO | não existe: critério de aceite | Peças inexistentes: consumo do batimento, publicador do espelho, repasse por etapas, tarefa das 19:45 | contratos/08-orquestrador.md:257 — Publicador: job `publicar_espelho` (deferido na transação ; src/ia-atendimento-b1-6a/src/ia_atendimento/espelho.py:4 — O publicador (`publicar_espelho`, B1.6b) lê a tabela |
| G-0217 | MÉDIO | risco aceito em parte | Contrato 03 não declara que pessoa:ler alcança GET /pessoas/{id} | 03-cliente360-api.md — "Fora do escopo \| GET /pessoas/{id}/dossie etc. ⇒ 403 ESCOPO_INSUFICIENTE" ; ESTUDO-D29-ficha-essencial.md — "o token com pessoa:ler ainda alcança GET /pessoas/{id} se vazar" |
| G-0224 | MÉDIO | confirmado em parte | Envio ao cliente: status cobertos pelo sem_retry_ambiguo e conferência por conversa vagos | 02-chatguru-api.md — "transporte, 429/502/503/504 e, por padrão, timeout (que pode ter entregue)" ; 02-chatguru-api.md — "sem_retry_ambiguo:true → falha ambígua volta 424 mensagem_incerta/dialogo_incerto sem repetir" |
| G-0226 | MÉDIO | risco aceito em parte | Rota genérica /chatguru/acao com token permite qualquer action (risco aceito) | 02-chatguru-api.md — "Buraco residual, aceito: /chatguru/acao é genérica (qualquer action, inclusive chat_add e dialog_execute)" ; 02-chatguru-api.md — "o cliente de B6.8 só monta message_status; o token só existe no segredo do app na VPS" |
| G-0230 | MÉDIO | confirmado | Tela sem tratamento para 401/403 da API, falha de transporte e dado velho | contratos/07-cliente360-web.md — "O token `ia` vive ≤ 900 s (🔴): B7.1 cria a instância do timer existente" ; contratos/07-cliente360-web.md — "422 `modo_teste_global`/`valor_invalido` (em `detalhe.origem`) ⇒ mensagem curta" |
| G-0231 | MÉDIO | confirmado | Recusas e PUT de resultado desconhecido sem auditoria no F0 | contratos/07-cliente360-web.md — "registra auditoria sem `motivo` (nome da chave, valor, cargo, `trace_id`; molde `registrarAuditoriaLinhasPreAprovaco ; contratos/07-cliente360-web.md — "a auditoria com `operador` e `resultado` em toda tentativa" (linha da tabela §13, fase F1) |
| G-0233 | MÉDIO | confirmado | Batimento: limiar 90 s com timer 60 s sob fail-closed deixa margem de cerca de 10 s | contratos/04-n8n-braco-espelho.md:377 ; contratos/04-n8n-braco-espelho.md:385 |
| G-0237 | MÉDIO | não existe: critério de aceite | R2-19, R2-21 e R2-12 sem fechamento: medições A2.4/A2.8 e tabela de credenciais inexistentes | contratos/04-n8n-braco-espelho.md:429 ; contratos/08-orquestrador.md — "produtor = braço (RPA) ou `datetime_post`; ausente ⇒ ≥ 24 h; recusa segura" |
| G-0239 | MÉDIO | confirmado | Alarme forward_falhou não enxerga destino_erro | 04-n8n-braco-espelho.md — "que o gateway traduz em 424 (`destino_erro`), repetível e visível no alarme `forward_falhou`" ; 04-n8n-braco-espelho.md — "`forward_falhou > 0` por 1 min (B6.1) e `bloqueio_entrada` não mudou" |
| G-0242 | MÉDIO | não existe: critério de aceite | Fronteiras do orquestrador com provedor de modelo, ntfy e Phoenix sem contrato | 08-orquestrador.md — "409 `provedor_fora` · `pre_voo_falhou` \| atendimentos \| PreVoo: modelo; S4, canal ou cookie" ; 08-orquestrador.md — "1ª falha ⇒ amarelo; `repassando` ≥ 10 min (`v_prontidao.repassando_ha_10min`) ⇒ **crítico** (B6.6)" |
| G-0245 | MÉDIO | confirmado | Retenção depende de worker vivo; sem sinal de falha da poda | a-esquema-ia-atendimento.md — "chamada por tarefa periódica do Procrastinate (não por timer na S4 nem trigger)" ; a-esquema-ia-atendimento.md — "Timer systemd na S4 para a poda**: exigiria unidade nova em produção" |
| G-0246 | MÉDIO | aberto: decisão não achada | ia_app pode inserir ia_ativa e teto sem controle de quem | a-esquema-ia-atendimento.md — "GRANT SELECT, INSERT ON ia.passo, ia.artefato_versao, ia.config_versao TO ia_app;" ; a-esquema-ia-atendimento.md — "GRANT SELECT, INSERT, UPDATE ON ia.atendimento, ia.atendimento_resultado TO ia_app;" |
| G-0260 | MÉDIO | não existe: critério de aceite | DPA e ZDR contratual inexistentes | g-provedor-modelo.md — "**Retenção zero «por contrato» não existe em página pública de nenhum deles.**" ; g-provedor-modelo.md — "**DPA não achado** (PENDENTE)" |
| G-0261 | BAIXO | refutado | Dados do cliente (PIX, conta, endereço) passam pelo modelo | f-catalogo-ferramentas.md — "os dados coletados não vão ao modelo nem ao log" ; f-catalogo-ferramentas.md — "entrada {campo, valor} (um por vez) ou {revisar}" |
| G-0265 | BAIXO | refutado | CPF real enviado ao dublê em sombra/duble | f-catalogo-ferramentas.md — "Em sombra e duble o modelo recebe resultados do dublê por cenário" ; f-catalogo-ferramentas.md — "CPF só dentro do gateway (lido de GET /pessoas/{id} por chamada, sem persistir)" |
| G-0268 | MÉDIO | confirmado | Mecanismo da regra 12 não cobre numeral por extenso, nome de banco e histórico com valores | h-roteiro-conversa-memoria.md — "regex no T15 determinístico bloqueia dígito/«R$» fora de placeholder" ; h-roteiro-conversa-memoria.md — "Guarda **só o mascarado** e as respostas da própria IA (já sem PII)" |
| G-0271 | MÉDIO | confirmado | Atendimento que nunca encerra mantém dados para sempre (sem teto de poda) | src/ia-atendimento/migrations/0001_esquema.up.sql:404-410 — "WHERE a.estado = 'encerrado' AND a.encerrado_em < now() - make_interval" ; src/ia-atendimento/migrations/0001_esquema.up.sql:427 — "c.apagar_em < now() OR EXISTS" (so conversa_cifrada e cofre tem teto absoluto) |
| G-0274 | MÉDIO | confirmado em parte | Runtime publica a própria config e aprova artefatos (INSERT em config_versao/artefato_versao) | ia-atendimento/migrations/0001_esquema.up.sql:437 ; ia-atendimento/migrations/0001_esquema.up.sql:14 |
| G-0279 | MÉDIO | confirmado | Plano B de devolução posta links de chat em ntfy público/grupo indefinido | j-operacao-piloto.md:179 — "o [operador TI] posta no canal a lista de `link_chat`" ; j-operacao-piloto.md:183 — "T+15 aviso no grupo dos consultores com a lista" |
| G-0285 | BAIXO | não existe: critério de aceite | L: juiz sem chave de desligamento e papel ia_qualidade contradito | l-motor-qualidade.md — "camada 2 (juiz por modelo lendo a conversa cifrada) entra depois do piloto" (Resumo 1) ; l-motor-qualidade.md — "papel `ia_qualidade` com SELECT em `atendimento`, `passo`, `atendimento_resultado`, `mensagem_conversa` (decifra com chave pró |
| G-0287 | MÉDIO | confirmado em parte | Mensagem pendente do cliente entra no modelo sem RS de PII | ROTEIRO-DE-ACAO.md:1043 — "1 leitura, só a fala do cliente depois da última saída, mascarada" ; matriz-restricoes.md — "de onde vêm os `nomes` se o orquestrador não recebe nome" |
| G-0299 | MÉDIO | não existe: critério de aceite | RT-16 e linhas script apontam para script sem dono nem escopo | estudos/TELA-IA-C360.md:797 — "ficha de domingo 20:15 (`D18:93`) + script B7.2" ; estudos/TELA-IA-C360.md:807 — "ntfy + script + consulta \| zeros, leitura ≤ 5 % de falha, p95, custo × F3, amostra" |
| G-0300 | MÉDIO | confirmado | PAINEL_IA_OPERADORES é lista nova sem passo, dono nem semente; conflita com D4 | estudos/TELA-IA-C360.md:990 — "ligar exige o `uid` em `PAINEL_IA_OPERADORES`; desligar fica com o cargo" ; ROTEIRO-DE-ACAO.md:214 — "Operadores validados em `ia_espelho.operador` (04 §2.3; semente Admin+TI" |
| G-0303 | MÉDIO | confirmado | Motivo da chave em texto livre; nome de cliente persiste em config_versao | TELA-IA-C360.md:1338 — "O `motivo` da chave sai do texto livre (D-T32, `Rs` S-06)" ; TELA-IA-C360.md:1270 — "A máscara **não** pega nome de cliente (`orq:mascara.py:17`" |
| G-0304 | MÉDIO | não existe: critério de aceite | §6 exige do orquestrador e da API peças ausentes dos contratos 03 e 08 | TELA-IA-C360.md:1137 — "efeito: 'desligada' \| 'duble' \| 'sombra' \| 'real' \| 'desconhecido'; // (v2) lido do orquestrador" ; TELA-IA-C360.md:1189 — "O proxy da API devolve a **causa** em `detalhe.origem` (PROPOSTA" |
| G-0305 | MÉDIO | não existe: critério de aceite | Papel ia_leitura_painel e ACL por coluna não existem | ia-atendimento/migrations/0001_esquema.up.sql:443 ; ia-atendimento/migrations/0001_esquema.up.sql:451 |
| G-0311 | MÉDIO | não existe: critério de aceite | Ack do alerta sem fonte com ntfy.sh | j-operacao-piloto.md:228 — "Ack = reação ou resposta «ack» no canal, lida pela vigia" ; j-operacao-piloto.md:168 — "todo alerta de teste chegou ao canal com ack ≤ 15 min" |
| G-0313 | MÉDIO | confirmado | Motivo de config em texto livre pode deixar nome em config_versao | ia-atendimento/src/ia_atendimento/api/validacao.py:55-58 ; ia-atendimento/src/ia_atendimento/api/config_rotas.py:46 |
| G-0315 | MÉDIO | confirmado | Ensaio a seco de 18/11 com prontidão nula por artefatos_ausentes até 19/11 | contratos/03-cliente360-api.md — "`artefatos_ausentes` até a aprovação dos artefatos v1 no fim de B8.2" ; ROTEIRO-DE-ACAO.md — "F3 oficial 18/11 18:00 → 19/11 15:00" |
| G-0323 | MÉDIO | não existe: critério de aceite | Chave AES mensal x retenção de 14 d sem procedimento | 2026-10-29-01-orquestrador-nucleo.md:53 — "linha de `chave_id` descartada = texto ilegível (aceito: 14 d)" ; 2026-10-29-01-orquestrador-nucleo.md:383 — "test_chave_id_descartado_omite_a_linha_e_nao_derruba_o_turno" |
| G-0328 | MÉDIO | não existe: critério de aceite | Fronteira das 20:15 e DATAPREV: vigia e reabertura nao existem | planos/2026-10-29-01-orquestrador-nucleo.md — "a vigia da S2 alerta se `bloqueio_entrada` não mudou às 20:20 (B6.7)" ; planos/2026-10-29-01-orquestrador-nucleo.md — "nunca grava `false`: quem abre é o [operador TI] às 07:45" |
| G-0329 | MÉDIO | risco aceito em parte | Retenção de 14 d do ia_obs contradiz fulls do pgBackRest e spans sem regra de mascaramento | MONITORAMENTO-DESIGN.md:52 — "`ia_obs` (Phoenix, traces brutos, retenção 14 dias)" ; MONITORAMENTO-DESIGN.md:40 — "Dado bruto com conversa guardado por meses." |
| G-0334 | BAIXO | confirmado em parte | Arranjos com Anthropic, OpenAI, Google e DeepInfra seguem no simulador contra RS-01/RS-02 | premissas.json:579-673 — arranjos A1-A8, B1, B2 e C1 usam sonnet-5.5, haiku-5.5, gpt, gemini, qwen3-30b ; premissas.json:650-673 — B1, B2 e C1 com fallback sonnet-5.5 |
| G-0348 | MÉDIO | aberto: decisão não achada | ISKRA único escritor sem prova | 03-cliente360-iskra.md:25 — "«único escritor do GL360 … todos falam `POST /v1/op/{capability}`»" ; 03-cliente360-iskra.md:105 — "Nenhum robô/IA fala com o ISKRA diretamente" |
| G-0349 | MÉDIO | confirmado | Reabertura de 23/11 sem verificação da dependência real nem monitor | levantamento/04-dataprev-competencia.md — "em caráter excepcional, o ciclo de abertura referente à competência agosto de 2026" ; levantamento/04-dataprev-competencia.md — "Não existe status page pública nem RSS" |
| G-0355 | MÉDIO | confirmado | Guarda por-cpf cega para proposta manual ou estourada até o ciclo do robô | facta-on/app/routers/online.py:4704-4705 ; facta-on/app/routers/online.py:4839 |
| G-0367 | MÉDIO | confirmado em parte | Textos afirmam fatos do banco sem ferramenta nem validacao | TEXTOS-PARA-APROVACAO.md — TX-32 "O banco mostra isso na tela de assinatura antes de você concluir" (HIPÓTESE a validar com a FACTA) ; TEXTOS-PARA-APROVACAO.md — TX-39 "selfie, documento e assinatura são feitos lá" |
| G-0374 | MÉDIO | confirmado | OPERACAO não fixa dono/permissão dos arquivos 0600 em /etc/ia-s4 (sem chown) | ia-atendimento/src/ia_atendimento/cifra.py:113 ; ia-atendimento/src/ia_atendimento/segredos.py:47 |
| G-0380 | BAIXO | não existe: critério de aceite | D-13: recusa de abertura sem hora do cliente não existe no iniciar | ia-atendimento/src/ia_atendimento/api/atendimentos.py:89 ; ia-atendimento/src/ia_atendimento/api/atendimentos.py:91 |
| G-0384 | MÉDIO | aberto: decisão não achada | RG-107: alcance da máscara de PII não apresentado ao dono | ROTEIRO-DE-ACAO.md — "residual de PII sem NER (linha factual: rua, bairro, nome da mãe" ; ROTEIRO-DE-ACAO.md — "A1.10 \| Ata de padrões (0.6, 0.6-v2) e «ok» à análise de devolução (K) \| não iniciada" |
| G-0385 | MÉDIO | não existe: critério de aceite | RG-108: chaves expostas atravessam o piloto sem kit nem registro | ROTEIRO-DE-ACAO.md — "**depois do piloto, a partir de 02/12** (corte de C)" ; ROTEIRO-DE-ACAO.md — "apareceram em transcritos de subagentes: tratar como **expostos**" |
| G-0386 | BAIXO | confirmado em parte | D-32: Gemini como contingência sem frase do dono e código aceita gemini-* sem condição | ia-atendimento/src/ia_atendimento/config.py:33 ; ia-atendimento/src/ia_atendimento/config.py:207 |
| G-0389 | MÉDIO | não existe: critério de aceite | Máquina de estados sem chamador de produção na main; repassando vencido não é recolhido | src/ia_atendimento/api/atendimentos.py:193 ; src/ia_atendimento/api/atendimentos.py:205 |
| G-0393 | MÉDIO | confirmado | Sem tempo-limite por job: turno pendurado com worker vivo prende o chat | ia-atendimento/src/ia_atendimento/worker_vivo.py:36 ; ia-atendimento/src/ia_atendimento/jobs.py:239 |
| G-0395 | MÉDIO | confirmado | Poda diária sem retry, sem recuperação de tick perdido e sem sinal | ia-atendimento/src/ia_atendimento/fila.py:179 ; ia-atendimento/src/ia_atendimento/fila.py:214 |
| G-0396 | MÉDIO | não existe: critério de aceite | `Servicos` de produção vazios: nenhum job de chat processa na main | ia-atendimento/src/ia_atendimento/worker.py:52 ; ia-atendimento/src/ia_atendimento/jobs.py:125 |
| G-0397 | MÉDIO | confirmado | Bases de banco e Phoenix sem lista positiva de host | src/ia_atendimento/ferramentas/modo.py:41-46 ; src/ia_atendimento/ferramentas/modo.py:84-99 |
| G-0399 | MÉDIO | confirmado | Preço ausente vira default embutido; contrato diz que o boot recusa | src/ia-atendimento-b1-6a/src/ia_atendimento/config.py:49 — PRECO_IN_USD = Decimal("0.45") ; src/ia-atendimento-b1-6a/src/ia_atendimento/config.py:52 — CAMBIO = Decimal("5.3346") |
| G-0400 | MÉDIO | confirmado | OPERACAO promete falha de subida com chave AES fora do mês | src/ia-atendimento/src/ia_atendimento/api/ambiente.py:71 ; src/ia-atendimento/src/ia_atendimento/conversa.py:156 |
| G-0401 | MÉDIO | não existe: critério de aceite | Descarte mensal da chave AES sem código/kit e regra do dia 31 ambígua | src/ia-atendimento/docs/OPERACAO.md — "no dia 31 após o fim do mês, apague a entrada" ; ROTEIRO-DE-ACAO.md — "backups do pgBackRest** (chave mensal descartada no dia 31)" |
| G-0402 | MÉDIO | confirmado | `excepthook` mascara só por forma (sem segredos registrados nem nomes); só 2 segredos registrados | ia-atendimento/src/ia_atendimento/scrubber.py:82 ; ia-atendimento/src/ia_atendimento/observabilidade.py:73 |
| G-0405 | MÉDIO | confirmado | Token ti único e onipotente, sem rotação | ia-atendimento/src/ia_atendimento/api/app.py:78 ; ia-atendimento/src/ia_atendimento/api/app.py:126 |
| G-0411 | MÉDIO | confirmado | Gasto do turno que falha não tem passo que o carregue (DecisaoModelo/Erro não aceitam `.uso`) | ia-atendimento/src/ia_atendimento/turno.py:408 ; ia-atendimento/src/ia_atendimento/passos.py:232 |
| G-0412 | MÉDIO | confirmado | Sem teto de requisições ao modelo por turno (usage_limits) com ferramentas | ia-atendimento/src/ia_atendimento/agente.py:297 ; ia-atendimento/src/ia_atendimento/agente.py:303 |
| G-0414 | MÉDIO | não existe: critério de aceite | RS-23 neste pacote é só cerca estrutural: número por extenso passa e o T15 não existe | ia-atendimento/src/ia_atendimento/turno.py:137 ; ia-atendimento/src/ia_atendimento/turno.py:125 |
| G-0416 | MÉDIO | confirmado | Ramo loopback de MODELO_BASE_URL_1 (e transporte sem pino) contorna a lista positiva do host do modelo em prod | src/ia_atendimento/config.py:235-238 ; src/ia_atendimento/agente.py:143-145 |
| G-0417 | MÉDIO | confirmado | Aspas «» removidas depois dos filtros reconstituem link e `r$`: o cliente derruba o turno | ia-atendimento/src/ia_atendimento/protecao.py:137 ; ia-atendimento/src/ia_atendimento/protecao.py:142 |
| G-0418 | MÉDIO | confirmado | FAQ com pergunta de sim/não liberada na E6 confunde o SIM da confirmação | ia-atendimento/src/ia_atendimento/turno.py:110 ; ia-atendimento/src/ia_atendimento/turno.py:112 |
| G-0419 | MÉDIO | confirmado | `SISTEMA` proíbe «liberado» e promessa de prazo, mas o validador do texto livre só barra «aprovado/garantido» | ia-atendimento/src/ia_atendimento/modulos_fase.py:29 ; ia-atendimento/src/ia_atendimento/turno.py:125 |
| G-0420 | MÉDIO | risco aceito em parte | Limites da máscara (extenso, dígitos com letras, pedaços de CPF, data de nascimento) deixam CPF/valor chegarem | ia-atendimento/src/ia_atendimento/mascara.py:18 ; ia-atendimento/src/ia_atendimento/mascara.py:12 |
| G-0421 | MÉDIO | não existe: critério de aceite | Bloqueio de texto livre depois de 24 h não existe em nenhum arquivo da unidade | ia-atendimento/src/ia_atendimento/contexto.py:426 ; ia-atendimento/src/ia_atendimento/contexto.py:554 |
| G-0423 | MÉDIO | não existe: critério de aceite | Falta teste das 84 pessoas_teste com vistos | ia-atendimento/tests/test_contexto.py:100 ; ia-atendimento/tests/test_contexto.py:116 |
| G-0424 | MÉDIO | confirmado | Lembrete adiado rearma com instante absoluto: laço quente com relógio atrasado | src/ia-atendimento/src/ia_atendimento/fila.py:113 ; src/ia-atendimento/src/ia_atendimento/fila.py:312 |
| G-0426 | MÉDIO | não existe: critério de aceite | Kits s4/migrar.sh e domingo.sh não existem; sim da 0005 só texto | src/ia-atendimento/migrations/README.md:57 ; src/ia-atendimento/migrations/README.md:62 |
| G-0427 | MÉDIO | confirmado | Dois calendários independentes (corpus F3 x orquestrador) divergem sem teste | src/ia-atendimento/src/ia_atendimento/corpus/calendario.py:12 ; src/ia-atendimento/src/ia_atendimento/corpus/calendario.py:13 |
| G-0428 | MÉDIO | confirmado | FACTA_BASE_TESTE só é comparada com o host de FACTA_BASE | src/ia_atendimento/ferramentas/modo.py:131 ; src/ia_atendimento/ferramentas/modo.py:134 |
| G-0433 | MÉDIO | não existe: critério de aceite | Leitor de CPF real não existe; destino duble recebe CPF sem garantia de pessoa sintética | src/ia_atendimento/ferramentas/gateway.py:62 ; src/ia_atendimento/ferramentas/gateway.py:192 |
| G-0438 | MÉDIO | confirmado | Rearme (Adiar) sem teto: pausado pode dormir sem limite | ia-atendimento/src/ia_atendimento/agenda_estado.py:193 ; ia-atendimento/src/ia_atendimento/agenda_estado.py:214 |
| G-0440 | MÉDIO | não existe: critério de aceite | Prova da noite parcial; aguardando_cliente atravessa a noite | ia-atendimento/tests/test_agenda_jobs.py:222 ; ia-atendimento/tests/test_agenda_jobs.py:239 |
| G-0441 | MÉDIO | confirmado | «Pessoa de teste» em execução é o que o arquivo disser: carregar aceita qualquer UUID | ia-atendimento/src/ia_atendimento/pessoas_teste/arquivo.py:52 ; ia-atendimento/src/ia_atendimento/pessoas_teste/arquivo.py:58 |
| G-0442 | BAIXO | risco aceito em parte | CPFs de teste têm DV válido e a premissa «faixa nunca é de cliente» não está provada | ia-atendimento/src/ia_atendimento/pessoas_teste/catalogo.py:37 ; ia-atendimento/src/ia_atendimento/pessoas_teste/catalogo.py:103 |
| G-0443 | MÉDIO | confirmado | Fixtures de 3RN e C6: forma lida do código, sem payload medido e sem teste de deriva | ia-atendimento/src/ia_atendimento/pessoas_teste/formas.py:3 ; ia-atendimento/src/ia_atendimento/pessoas_teste/formas.py:389 |
| G-0447 | MÉDIO | confirmado | ia_app reescreve qualquer coluna do ledger ferramenta_chamada | ia-atendimento/migrations/0001_esquema.up.sql:438 ; ia-atendimento/migrations/0001_esquema.up.sql:439 |
| G-0448 | MÉDIO | confirmado | Teto absoluto de vida do texto depende de criada_em gravado pelo ia_app | ia-atendimento/migrations/0001_esquema.up.sql:313 ; ia-atendimento/migrations/0001_esquema.up.sql:320 |
| G-0449 | MÉDIO | confirmado | Poda de 365 d trava com FK simples entre atendimentos e pula podar_jobs | ia-atendimento/migrations/0001_esquema.up.sql:204 ; ia-atendimento/migrations/0001_esquema.up.sql:265 |
| G-0450 | MÉDIO | confirmado | FKs sem índice tornam a poda de 365 d quadrática | ia-atendimento/migrations/0001_esquema.up.sql:202 ; ia-atendimento/migrations/0001_esquema.up.sql:204 |
| G-0452 | MÉDIO | confirmado | Campos livres sem CHECK de forma aceitam 11 dígitos e ficam 365 d legíveis | ia-atendimento/migrations/0001_esquema.up.sql:271 ; ia-atendimento/migrations/0001_esquema.up.sql:303 |
| G-0455 | MÉDIO | confirmado | Ledger não amarra ferramenta a classe de efeito/timeout/cerca; «T7 nunca repete» depende do chamador | ia-atendimento-b1-6a/src/ia_atendimento/ledger.py:136 ; ia-atendimento-b1-6a/src/ia_atendimento/ledger.py:447 |
| G-0457 | MÉDIO | não existe: critério de aceite | D-15: nenhum consumo do batimento; devolução real sem gancho | ia-atendimento-b1-6a/src/ia_atendimento/worker_vivo.py:86 ; ia-atendimento-b1-6a/src/ia_atendimento/api/saude.py:53 |
| G-0458 | MÉDIO | confirmado | Custo ausente/nulo vira zero: teto não enxerga resposta sem usage e custo_ausente/125 % sem chamador | ia-atendimento-b1-6a/src/ia_atendimento/gasto.py:50 ; ia-atendimento-b1-6a/src/ia_atendimento/turno.py:255 |
| G-0464 | MÉDIO | não existe: critério de aceite | Kit s4/migrar.sh não existe; migrações por texto manual de psql sem controle do «sim» da 0005 | ROTEIRO-DE-ACAO.md — "kit `s4/migrar.sh` a escrever (Claude, 0,5 d, ensaio local)" ; ia-atendimento/migrations/README.md:57-66 |
| G-0465 | MÉDIO | confirmado | Rollback do deploy-vps.sh não sobrevive a interrupção nem a segunda execução | ia-atendimento-esteira/scripts/deploy-vps.sh:138 ; ia-atendimento-esteira/scripts/deploy-vps.sh:143 |
| G-0466 | MÉDIO | confirmado | Secrets do registry: DEPLOY.md quebra o job construir; credencial de escrita compartilhada | ia-atendimento-esteira/docs/DEPLOY.md:76 ; ia-atendimento-esteira/docs/DEPLOY.md:78 |
| G-0467 | MÉDIO | confirmado | Imagem implantada por tag mutável, não por digest | ia-atendimento-esteira/docker-compose.yml:23 ; ia-atendimento-esteira/.github/workflows/imagem.yml:159 |
| G-0468 | MÉDIO | confirmado | /healthz da main não recebe git_sha/built_at: nomes de variável diferentes | ia-atendimento-esteira/Dockerfile:46 ; ia-atendimento-esteira/Dockerfile:47 |
| G-0469 | MÉDIO | confirmado | A4.9 e P-R8 descrevem deploy diferente da esteira | ROTEIRO-DE-ACAO.md — "`/etc/ia-s4:/run/ia-s4:ro` (**diretório**, `:ro`), `OTLP http://127.0.0.1:6006/v1/traces`" ; ROTEIRO-DE-ACAO.md — "as chaves AES (`CONVERSA_CHAVES`) em arquivo 0600 `/etc/ia-s4/conversa.keys` na VPS" |
| G-0470 | MÉDIO | confirmado | CI do ia-atendimento não roda gitleaks (nem conferir_catalogo); portão de segredos só local | ia-atendimento/.github/workflows/ci.yml:33 ; ia-atendimento/.github/workflows/ci.yml:41 |
| G-0471 | MÉDIO | aberto: decisão não achada | .gitleaksignore isenta CPF de DV válido do commit 88d081a sem prova de ser sintético | ia-atendimento/.gitleaksignore:2 ; ia-atendimento/.gitleaksignore:4 |
| G-0472 | MÉDIO | confirmado | varredura.py cobre menos do que o PD-6 promete | ia-atendimento/scripts/varredura.py:8 ; ia-atendimento/scripts/varredura.py:28 |
| G-0474 | MÉDIO | confirmado | chats-teste.sh: três caminhos em que o desfazer some ou engana | ia-atendimento/kits/chats-teste.sh:169 ; ia-atendimento/kits/chats-teste.sh:116 |
| G-0477 | MÉDIO | confirmado | Migrações de produção por bloco inline, sem kit nem ensaio, precheck incompleto | src/ia-atendimento/docs/OPERACAO.md:4 — "só pelos kits (`bash ~/retomada-2809/fila-2910/ia/<passo>/…`), com ensaio" ; src/ia-atendimento/docs/OPERACAO.md:62 — "# 3a. pré-checagem (ADD CONSTRAINT valida a tabela inteira" |
| G-0480 | MÉDIO | confirmado | Cliente HTTP do modelo sem trava de proxy nem redirecionamento | ia-atendimento/src/ia_atendimento/agente.py:176 ; ia-atendimento/src/ia_atendimento/agente.py:181 |
| G-0481 | MÉDIO | confirmado | Origem de ips_confiaveis entra no HMAC como se viesse do token | gl-gateway/app/main.py:427 ; gl-gateway/app/main.py:508 |
| G-0482 | MÉDIO | aberto: decisão não achada | ia-sumidouro guarda o Post com PII por 7 dias sem decisão localizada nem expurgo | gl-gateway/app/projecao.py:57 ; gl-gateway/app/main.py:465 |
| G-0484 | MÉDIO | confirmado em parte | Gateway: deploy automático sem verificação pós-deploy (health none, /health constante) | gl-gateway/.github/deploy-targets/gl-gateway-production.json:7 ; gl-gateway/app/main.py:370 |
| G-0485 | MÉDIO | confirmado | piiscan: falsos negativos estruturais de CPF e celular | bancos-duble/piiscan/detectores.py:55 ; bancos-duble/piiscan/detectores.py:58 |
| G-0486 | MÉDIO | confirmado | piiscan pula calado: pragma, diretorios e nomes de arquivo | bancos-duble/piiscan/varredura.py:141 ; bancos-duble/piiscan/varredura.py:39 |
| G-0491 | MÉDIO | risco aceito em parte | Consistencia das pessoas de teste so no check.sh local, sem pin do irmao | scripts/atualizar_pessoas_teste.py:55-61 ; scripts/exigir_irmao.sh:15-18 |
| G-0492 | MÉDIO | confirmado | Forma medida vazia: fidelidade --estrito passa sem comparar | bancos-duble/docs/forma-medida.json:4 ; bancos-duble/tools/fidelidade.py:159 |
| G-0497 | MÉDIO | confirmado | Dublê provado contra facta-on e9ba005; nada confere o SHA | bancos-duble/tests/facta_on_checkout.py:24 ; bancos-duble/tests/test_facta_on_app_isolado.py:16 |
| G-0499 | MÉDIO | confirmado | Contrato 05 cita teste do dublê que não existe; janela 20 x 10 sem teste que as compare | contratos/05-facta-on.md — "é testado com **os mesmos** números (`test_dubl_t8_prazo_1500`)" ; contratos/05-facta-on.md — "`nao_criada` só depois do ciclo simulado, e é testado" |
| G-0501 | MÉDIO | confirmado | CI do bancos-duble: gitleaks sem historico, piiscan sem exigir denylist, branch sem PR nao roda | bancos-duble/.github/workflows/ci.yml:55 ; bancos-duble/.github/workflows/ci.yml:28 |
| G-0503 | MÉDIO | confirmado | nao_criada aceita ciclo do robô que listou antes da janela ou foi interrompido | facta-on/app/routers/online.py:4839 ; facta-on/app/robo.py:978 |
| G-0504 | MÉDIO | confirmado | Deploy automático do facta-on sem prova de saúde e CODEOWNERS sem app/ | facta-on/.github/workflows/testes.yml:54 ; facta-on/.github/workflows/testes.yml:5 |
| G-0507 | MÉDIO | confirmado | SO_CREDENCIAL_PROPRIA só tira o escopo do preset TI | src/cliente360-api/src/c360auth/admin/catalogo.py:217 — ESCOPOS_TI_TOTAL_ACCESS = frozenset(POR_NOME) - SO_CREDENCIAL_PROPRIA ; src/cliente360-api/src/c360auth/admin/catalogo.py:190 — definição de SO_CREDENCIAL_PROPRIA, sem outro uso em src/c360auth |
| G-0508 | MÉDIO | confirmado | ia-sumidouro guarda o Post inteiro (7 d) sem trava de chat, sem auth e sem fim de vida/purga | kits/gateway/rotas-ia.sh:27 — "'ia-sumidouro', '$DESTINO_IA_SUMIDOURO', 'chatguru-ia-teste', false, NULL::text[], true" ; kits/gateway/ia-sumidouro.workflow.json:7 — "httpMethod": "POST" (Webhook sem parâmetro de autenticação) |
| G-0510 | MÉDIO | não existe: critério de aceite | Fluxos e kits do braço n8n não existem; A3.8 passou da data sem kit | kits/gateway/README.md:107 ; kits/gateway/rotas-ia.sh:72 |
| G-0513 | MÉDIO | confirmado | entregar-hmac-vps.sh perde variáveis no sudo | kits/gateway/entregar-hmac-vps.sh:23 ; kits/gateway/entregar-hmac-vps.sh:41 |
| G-0515 | MÉDIO | confirmado | Kit do gateway com datas, versão e mensagens desatualizadas | kits/gateway/README.md:3 — "01-gl-gateway.md (**v2.4**, §9); decisão: **D-04**" ; kits/gateway/README.md:27 — "noite de 04/11 \| rotas-ia.sh --confirmo" |
| G-0523 | MÉDIO | confirmado | Leitura do bkp_pg no esquema ia não é conferida; prova de A4.3a é vazia | kits/s4/provar.sh:85 ; kits/s4/s4-papeis.sh:149 |
| G-0530 | MÉDIO | não existe: critério de aceite | domingo.sh, ativar.sh e set.sh não existem | ROTEIRO-DE-ACAO.md — "kits `s4/migrar.sh`, `config/domingo.sh`, `gateway/ativar.sh` e o da chave AES de dezembro" ; ROTEIRO-DE-ACAO.md — "o kit `ativar.sh` ainda não existe, nasce em B6.1" |
| G-0531 | MÉDIO | confirmado | F07 proíbe corpo de evento em span «nem mascarado»; o código exporta o conteúdo por padrão | src/ia-atendimento/src/ia_atendimento/observabilidade.py:258 ; src/ia-atendimento/src/ia_atendimento/observabilidade.py:277 |
| G-0532 | MÉDIO | não existe: critério de aceite | Canário ponta a ponta não existe; vazamento só no corpo ao provedor | ia-atendimento/tests/test_vazamento_corpo.py:95 ; ia-atendimento/tests/test_vazamento_corpo.py:102 |
| G-0542 | MÉDIO | confirmado | Expurgo de 7 dias de gateway.payloads fora do repositório do gateway | gl-gateway/init_payloads.sql:35 ; gl-gateway/init_payloads.sql:51 |
| G-0546 | MÉDIO | confirmado | Rotação HMAC não tira a chave antiga | kits/gateway/entregar-hmac-vps.sh:48 ; kits/gateway/entregar-hmac-vps.sh:50 |
| G-0552 | MÉDIO | confirmado | T2, T3 e T10 sem usa_cpf, mas pessoas:propostas exige CPF no corpo | ia-atendimento/src/ia_atendimento/ferramentas/catalogo.py:152 ; ia-atendimento/src/ia_atendimento/ferramentas/catalogo.py:157 |
| G-0555 | MÉDIO | confirmado | Vigia de deriva do contrato pula no CI | ia-atendimento/tests/test_fixtures_duble.py:397 ; ia-atendimento/tests/test_contrato_api.py:190 |
| G-0556 | BAIXO | não existe: critério de aceite | Cliente do 360, troca de token, executores T1/T2/T3/T10 e testes D-29 não existem | ia-atendimento/src/ia_atendimento/ferramentas/gateway.py:26 ; ia-atendimento/src/ia_atendimento/ferramentas/gateway.py:187 |
| G-0557 | MÉDIO | confirmado | Camada B nao reproduz casos que decidem T7/T8 | bancos-duble/scripts/stubs_b.py:335 ; bancos-duble/scripts/stubs_b.py:390 |
| G-0558 | MÉDIO | confirmado | SaidaT8 não expressa recusa_politica nem os vereditos do contrato | ia-atendimento/src/ia_atendimento/ferramentas/esquemas.py:171 ; contratos/05-facta-on.md — "`estado=criada` e **todos** os itens `cancelado` (AF cancelada da etapa 3, política) \| `recusa_politica`" |
| G-0559 | MÉDIO | confirmado | T8 de 1500 s segura vaga do limitador da FACTA (2 vagas) | src/ia_atendimento/ferramentas/gateway.py:61 ; src/ia_atendimento/ferramentas/gateway.py:335 |
| G-0561 | MÉDIO | não existe: critério de aceite | Sem contrato de teste para as rotas da IA no facta-on | facta-on/tests/contrato_ai05.json:2 ; facta-on/tests/contrato_ai12.json:2 |
| G-0562 | MÉDIO | confirmado | Origem da escrita não gravada; publicado_por afirmado por quem chama | ia-atendimento/src/ia_atendimento/api/config_rotas.py:191 ; ia-atendimento/src/ia_atendimento/chave.py:122 |
| G-0565 | ALTO | não existe: critério de aceite | «Abertos têm até 20 min e são repassados com a nota» depende de B1.6b; na main o job agendado pelo desligar fa | ia-atendimento/src/ia_atendimento/worker.py:52 ; ia-atendimento/src/ia_atendimento/jobs.py:133 |
| G-0566 | MÉDIO | confirmado | TX-42 no repasse noite/domingo sem condição de janela 08-20 | contratos/08-orquestrador.md — "fora dela (noite, sábado depois das 12:00, domingo), **TX-42** com `{{retorno}}`" ; contratos/08-orquestrador.md — "Todo envio posterior repete o teste e registra `janela_24h` no passo" |
| G-0567 | MÉDIO | confirmado | Nota do orquestrador + nota da vigia: espelho só sabe da nota após a etapa rota (segunda nota) | 04-n8n-braco-espelho.md:321 — "com `nao` não grava marco, e a vigia (se a devolução passar a ser dela" ; 04-n8n-braco-espelho.md:321 — "para que a vigia nunca escreva uma segunda" |
| G-0568 | MÉDIO | não existe: critério de aceite | Identidade do remetente (ator 85, linha) sem ponto fixo | ia-atendimento/src/ia_atendimento/config.py:115 ; ia-atendimento/src/ia_atendimento/config.py:164 |
| G-0569 | MÉDIO | confirmado | PHOENIX_ENDPOINT aceita qualquer host público e http, com conteúdo nos spans | ia-atendimento/src/ia_atendimento/config.py:249 ; ia-atendimento/src/ia_atendimento/config.py:258 |
| G-0570 | MÉDIO | confirmado | modelo_por_faixa passa na validação da config com par que o runtime recusa (e custo_max_brl duplicado) | ia-atendimento/src/ia_atendimento/chave_registro.py:87 ; ia-atendimento/src/ia_atendimento/chave_registro.py:140 |
| G-0572 | MÉDIO | não existe: critério de aceite | Provedor recusando (401/402/403/429) não fecha a entrada nem gera alerta crítico | ia-atendimento/src/ia_atendimento/agente.py:358 ; ia-atendimento/src/ia_atendimento/agente.py:75 |
| G-0573 | MÉDIO | não existe: critério de aceite | ntfy.sh sem código e sem critério do conteúdo permitido | ROTEIRO-DE-ACAO.md — "o piloto roda no `ntfy.sh` com tópico secreto" ; MONITORAMENTO-DESIGN.md — "id curto do atendimento, hora, regra, ação já tomada, próximo passo, link" |
| G-0574 | MÉDIO | confirmado | /etc/ia-s4 junta credenciais de ia_app_a e ia_obs_a sob o mesmo grupo 10001; Phoenix lê a chave do runtime | kits/s4/distribuir-certs.sh:11 ; kits/s4/distribuir-certs.sh:41 |
| G-0575 | MÉDIO | confirmado | App não exige sslmode=verify-full; DSN canônico não escrito | ia-atendimento/src/ia_atendimento/config.py:182-201 ; kits/s4/s4-hba.sh:42-46 |
| G-0576 | MÉDIO | confirmado | Orçamento de conexões do ia_app_a (até 26) passa do limite 20 | kits/s4/s4-papeis.sh:83 ; ia-atendimento/src/ia_atendimento/api/ambiente.py:31 |
| G-0579 | BAIXO | não existe: critério de aceite | RS-10, RS-11, ntfy, vigia 19:45, B6.6/B6.7 são pedido sem código | ROTEIRO-DE-ACAO.md:51 — "repasse forçado 19:45 = tarefa periódica do orquestrador, B6.7" ; matriz-restricoes.md:52 — "Não há `ntfy`, `fim_do_dia`/19:45 nem `executar_efeito` na main" |
| G-0580 | BAIXO | confirmado | PD-6 sem critério de toca texto de cliente; corpus e pessoas_teste sem a flag | ROTEIRO-DE-ACAO.md — "todo modelo Pydantic que toca texto de cliente usa `hide_input_in_errors=True`" (PD-6, l.435) ; ia-atendimento/src/ia_atendimento/corpus/modelos.py:33 |
| G-0589 | BAIXO | não existe: critério de aceite | Nenhum teste de ator de envio fixo em 85 | ROTEIRO-DE-ACAO.md:1087 — "`POST /pessoas/{id}/atribuicoes` com o ator 85" ; ROTEIRO-DE-ACAO.md:1088 — "`test_assumir_registra_ator_85_e_relê_delegacao`" |
| G-0627 | BAIXO | não existe: critério de aceite | Peças exigidas por J e K ainda inexistentes | k-devolucao-lead-cenarios.md:166 — "Vigia: timer systemd na S2 (60 s, Python stdlib" ; j-operacao-piloto.md:41 — "Repasse forçado de todo atendimento aberto" (19:45, B6.7) |
| G-0645 | BAIXO | não existe: critério de aceite | Papel ia_leitura_painel, ack obrigatório, ntfy de status e pedidos IA-ORQ-* ainda não existem | kits/s4/s4-papeis.sh:41 ; ia-atendimento/migrations/0001_esquema.up.sql:443 |
| G-0660 | BAIXO | não existe: critério de aceite | Janela DATAPREV recorrente não existe no código | src/canario-4/src/ia_atendimento/calendario.py:26-27 ; src/canario-4/src/ia_atendimento/calendario.py:140-141 |
| G-0667 | BAIXO | risco aceito | Lição 2 do incidente (fallback sem colunas) está no código | gl-gateway/app/rotas.py:123 — _UNDEFINED_COLUMN = "42703" ; gl-gateway/app/rotas.py:141-148 — tenta SELECT completo; só 42703 cai para o antigo |
| G-0689 | BAIXO | confirmado | PD-6 sem trava global nas bases Pydantic | ia-atendimento/src/ia_atendimento/corpus/modelos.py:33 ; ia-atendimento/src/ia_atendimento/pessoas_teste/formas.py:31 |
| G-0700 | BAIXO | confirmado | Regra de subida não exige hide_input_in_errors nos esquemas | src/ia_atendimento/ferramentas/especificacao.py:97 ; src/ia_atendimento/ferramentas/esquemas.py:27 |
| G-0710 | BAIXO | confirmado | Modelos de formas.py, catalogo.py e fixtures_duble.py sem hide_input_in_errors | ia-atendimento/src/ia_atendimento/pessoas_teste/formas.py:31 ; ia-atendimento/src/ia_atendimento/pessoas_teste/formas.py:35 |
| G-0713 | BAIXO | não existe: critério de aceite | texto_de_saida, FontePessoasTeste e FixturesDuble sem chamador no orquestrador | ia-atendimento/src/ia_atendimento/pessoas_teste/prefixo.py:24 ; ia-atendimento/src/ia_atendimento/pessoas_teste/prefixo.py:21 |
| G-0714 | BAIXO | confirmado | Modelos do corpus sem hide_input_in_errors | src/ia-atendimento/src/ia_atendimento/corpus/modelos.py:33 ; src/ia-atendimento/src/ia_atendimento/corpus/carga.py:29 |
| G-0730 | BAIXO | confirmado | Superfície transitiva sem uso (grpc, tiktoken); build-system sem pin | ia-atendimento/pyproject.toml:20 ; ia-atendimento/pyproject.toml:14 |
| G-0734 | BAIXO | risco aceito em parte | Teste congela ia-sumidouro guardando Post inteiro com CPF por 7 dias | gl-gateway/tests/test_ia_forward.py:168 ; gl-gateway/tests/conftest.py:64 |
| G-0738 | BAIXO | risco aceito em parte | Faixa sintetica de CPF e hipotese isenta nos scanners | bancos-duble/anonimizador/duble_anon/sinteticos.py:3 ; bancos-duble/piiscan/detectores.py:21 |
| G-0748 | BAIXO | risco aceito em parte | Webhook ia-sumidouro sem autenticação | kits/gateway/ia-sumidouro.workflow.json:6 ; kits/gateway/env-gateway.sh:19 |
| G-0750 | BAIXO | não existe: critério de aceite | Regra nft da VPS e rotação de segredos do gateway não têm kit | kits/s4/README.md:12 ; kits/gateway/env-gateway.sh:27 |
| G-0761 | BAIXO | risco aceito | Só-EUA garantido pelo nome do roteador; nada confere a resposta | ia-atendimento/src/ia_atendimento/config.py:43 ; ia-atendimento/src/ia_atendimento/config.py:175 |
| G-0762 | BAIXO | não existe: critério de aceite | Rotação para ia_app_b e troca de senha do ia_app_a sem kit | kits/s4/s4-papeis.sh:10 ; kits/s4/s4-papeis.sh:158 |
| R2-001 | ALTO | confirmado | Pendente que começa com 'dd/mm hh:mm' derruba o turno no auditar_prompt (prefixo '1. «' cola na cadeia de dígi | src/ia-atendimento/src/ia_atendimento/contexto.py:266,316; mascara.py:50,145 |
| R2-004 | MÉDIO | confirmado | Regra '[NUMERO:2] = prazo' e _PRAZO amplo empurram hora nua e quantidades para prazo | src/ia-atendimento/src/ia_atendimento/modulos_fase.py:35; protecao.py:63,71-78 |
| R2-005 | MÉDIO | confirmado | Parte do nome que é palavra comum (Dias, Graça, Socorro, Filho) apaga a palavra e quebra o 'fica' de duração | src/ia-atendimento/src/ia_atendimento/mascara.py:163-189; protecao.py:137,141 |
| R2-006 | BAIXO | confirmado em parte | Extração por código do número de alvo_pedido não existe; a única fonte guardada já vem mascarada | src/ia-atendimento/src/ia_atendimento/protecao.py:20; modulos_fase.py:60; ferramentas/esquemas.py (ArgsSimulacao) |
| R2-008 | MÉDIO | confirmado | T8 (leitura local do facta-on, até 1500 s) segura as 2 vagas do limitador da FACTA e bloqueia T5/T7/T9 de todo | src/ia-atendimento/src/ia_atendimento/ferramentas/catalogo.py:177-181; ferramentas/gateway.py:61,334-340 |
| R2-009 | MÉDIO | confirmado em parte | SaidaT8.estado não comporta os vereditos do 05 §2.1 B (falta recusa_politica e aguardando_status; usa nao_cria | src/ia-atendimento/src/ia_atendimento/ferramentas/esquemas.py:170-172 |
| R2-010 | MÉDIO | confirmado em parte | Timeout da T8 no prazo vira BANCO_INDISPONIVEL (código de repetir), quando o contrato manda indeterminado com  | src/ia-atendimento/src/ia_atendimento/ferramentas/gateway.py:343-344 |
| R2-011 | MÉDIO | confirmado | posse_real sem produtor na main: padrão False em Deps e ContextoDaChamada; sob parada dura em duble, o atendim | src/ia-atendimento/src/ia_atendimento/ferramentas/projecao.py:59; ferramentas/gateway.py:78; ferramentas/modo.py:170-174 |
| R2-012 | MÉDIO | confirmado em parte | T7 com posse real sob parada dura cai no simulador; o contrato manda barrar | src/ia-atendimento/src/ia_atendimento/ferramentas/modo.py:157-164 |
| R2-013 | MÉDIO | confirmado em parte | CancelledError depois do disparo da T7 não vira INDETERMINADO nem gera registro | src/ia-atendimento/src/ia_atendimento/ferramentas/gateway.py:338-346,233 |
| R2-014 | BAIXO | confirmado em parte | Leitura da FACTA em sombra/duble diverge da linha «Ler» de 08 §6, sem decisão registrada | src/ia-atendimento/src/ia_atendimento/ferramentas/modo.py:12-18,157-164 |
| R2-015 | MÉDIO | confirmado | Anotação do operador grava nome e texto livre sobre o cliente em claro por 365 d: a API desliga a cerca de nom | src/ia-atendimento/src/ia_atendimento/api/anotacoes.py:83-85 -> passos.py:273-279,410 -> linha_tempo.py:184-187 -> ia.passo.texto |
| R2-016 | MÉDIO | confirmado | Ledger b1-6a grava Desfecho.ref_externa sem a varredura de PII do gateway; valor fora do CHECK sobe CheckViola | src/ia-atendimento-b1-6a/src/ia_atendimento/ledger.py:164-171,241-246,343-354,419-425,467-480; migrations/0001_esquema.up.sql:215 |
| R2-017 | MÉDIO | confirmado em parte | Mover `despachado=True` para antes da leitura do CPF da T7 não derruba nenhum teste | src/ia-atendimento/src/ia_atendimento/ferramentas/gateway.py:338-346; tests/test_ferramentas_gateway_revisao.py:169-180; tests/test_ferramentas_gateway.py:486-489 |
| R2-023 | BAIXO | confirmado em parte | _NOME_ASSINAVEL.match com $ aceita \n no fim; o contrato e config.py usam fullmatch | gl-gateway/app/assinatura.py:47,79 |

---

## Anexo C. Tabela dos 128 RG (antigo §8.3)

| RG | Sev. | D-nn | Título (CSV) | Estado final | Rótulo do leitor | Prova / âncora | Grupos F3/F4 | Fonte |
|---|---|---|---|---|---|---|---|---|
| RG-001 | MÉDIO | — | Preço do modelo rotulado medido e cache 85% sem medição | **fechado com prova** | fechado com prova | ROT:309 «preço Fireworks 0,45/0,009/1,80 classe «estimado»»; `premissas.json:16` | G-0333 (BAIXO) | F1-53:21 |
| RG-002 | MÉDIO | — | Empate de 140 pagos por mês usa custo da era Sonnet | **fechado com prova** | fechado com prova | `index.html:1548` «O número antigo (≈ 140) usava o custo da era Sonnet» | — | F1-53:22 |
| RG-003 | MÉDIO | — | sp01 não acompanhou o contrato 08 v2.1 a v2.3 em cinco pontos | **aberto** | aberto | sp01:200 `turnos_max=30`; ROT:1581 «a nota no sp01 fica pendente» | G-0063 (ALTO), G-0327 (BAIXO) | F1-53:23 |
| RG-004 | ALTO | — | Gasto por soma de passo.custo_brl bloqueia B1.6 e falta na Spec | **aberto** | aberto | main `chave.py:196` soma `custo_modelo_brl + custo_midia_brl`; correção só no ramo (`gasto.py:49`, PR #13 em conflito) | G-0064 (MEDIO), G-0065 (MEDIO), G-0326 (BAIXO), G-0411 (MEDIO) | F1-53:24 |
| RG-005 | MÉDIO | — | T4 saiu do MVP mas estudos e sp01 ainda o desenham | **fechado só no papel** | fechado só no papel | ROT:997 `motivo_desfecho=oferta_vencida`; busca em `src/` e `migrations/` da main: vazia | — | F1-53:25 |
| RG-006 | MÉDIO | — | Teto de turnos 30 contra 24 entre mestre e estudos | **fechado só no papel** | fechado só no papel | ROT:904 «`turnos_max=24`»; sp01:200 e estudos ainda 30; `turnos_max` sem código | G-0324 (BAIXO) | F1-53:26 |
| RG-007 | ALTO | D-05 | Sombra A e ensaio B no mesmo dia violam o 08 §6 | **aberto** | aberto (reabertura) | ROT:1147 ensaio B riscado; ROT:1277 põe as falhas de 24/11 dentro da sombra | G-0022 (ALTO) | F1-53:27 |
| RG-008 | BAIXO | — | README e especificação sem banner histórico ainda ensinam Sonnet e Haiku | **fechado só no papel** | fechado só no papel | ROT:57 «históricos, não ler»; `README.md:1` sem banner, `:44` ainda Sonnet/Haiku | G-0038 (BAIXO), G-0661 (BAIXO), G-0670 (BAIXO) | F1-53:28 |
| RG-009 | ALTO | — | E10 repassa em modo fila mas indicado é o consultor original | **fechado só no papel** | fechado só no papel | 08:236 «O orquestrador não manda `fila`»; main `estado.py:359` `Literal["fila", "indicado"]`; ROT:1063 «devolve ao rodízio» | G-0003 (MEDIO) | F1-53:29 |
| RG-010 | n/i | — | Tap do facta-on grava mensagem normalizada contra o contrato 05 | **refutado** | refutado, resíduo pendente | 05:106 ainda «(nem normalizada…)»; PR #49 do facta-on em conflito | G-0368 (MEDIO) | F1-53:30 |
| RG-011 | ALTO | — | Vhost WG 8093 autentica por prefixo mas o 02 exige allowlist fechada | **aberto** | aberto | 02:72-73 só `/gateway/ia-repasse`; ROT:712 «a emenda do 02 §2 fica pendente» | G-0074 (ALTO), G-0127 (ALTO) | F1-53:31 |
| RG-012 | ALTO | — | Sempre reais para T12 e repasse contra só com posse real | **fechado só no papel** | fechado só no papel | ROT:257 «(superado, 08 §6…)»; main `ferramentas/gateway.py:78`; ROT:1149 sem marca | G-0181 (BAIXO) | F1-53:32 |
| RG-013 | MÉDIO | D-15 | Batimento de 60 s contra 90 s decidido e não aplicado | **fechado só no papel** | fechado só no papel | ROT:906 «ausente ou > 90 s»; `G0-PEDIDO-AO-DONO.md:33` e sp01:95 ainda 60 s | G-0182 (BAIXO) | F1-53:33 |
| RG-014 | ALTO | D-32 | B6.2 ainda manda Form de duas páginas e ia-disparo vencidos | **fechado com prova** | fechado com prova | ROT:1047 «Webhook + página estática, 22 s, `chat_ocupado`, sem `ia-disparo`» | G-0247 (BAIXO) | F1-53:34 |
| RG-015 | ALTO | — | B3.2 só isto ignora redação das 38 linhas de CPF em log | **fechado só no papel** | fechado só no papel | ROT:951 aceite da redação; facta-on `app/routers/online.py`: 38 × `cpf={cpf` | G-0108 (ALTO) | F1-53:35 |
| RG-016 | ALTO | D-09 | Roteiro diz auto-deploy desligado mas gateway e facta-on deployam no merge | **aberto** | aberto | ROT:45 «a proteção da `main` é ação do dono, **pendente**» | G-0388 (MEDIO) | F1-53:36 |
| RG-017 | MÉDIO | — | B9.1 depende de B8.2 que termina depois do congelamento | **superado** | superado | ROT:403 «(v3.3, RG-017: sai B8.2)»; ROT:1305-1306 | — | F1-53:37 |
| RG-018 | MÉDIO | — | Custo de 0,87 por atendimento não existe no estudo G | **fechado com prova** | fechado com prova | ROT:1122 «≈ R$ 0,44 por atendimento sem cache»; resíduo j:133 e l:76 | — | F1-53:38 |
| RG-019 | BAIXO | — | Custo de mensagem zero com classe medido por decisão do dono | **fechado com prova** | fechado com prova | `premissas.json:180-181` «"classe": "decisão do dono 29/10"» | — | F1-53:39 |
| RG-020 | MÉDIO | — | Premissas e painel desatualizados e A2.11 presa à chave | **fechado com prova** | fechado com prova | `index.html:670` «que **não é o piloto**» | — | F1-53:40 |
| RG-021 | BAIXO | — | Teto de 8 s é por chamada no código e não por turno | **fechado com prova** | fechado com prova | ROT:599 «`MODELO_TIMEOUT_S` (8 s por chamada; 16 s por turno)» | — | F1-53:41 |
| RG-022 | BAIXO | — | MON diz agenda fora do MVP e a memória do dono diz dentro | **aberto** | PARCIAL | `MONITORAMENTO-DESIGN.md:69` ainda «fora do MVP»; ROT:1696 diz «aplicado» | G-0671 (BAIXO) | F1-54:19 |
| RG-023 | MÉDIO | D-11 | TX-M03 promete sábado até 19h mas a agenda de sábado vai até 12h | **aberto** | PARCIAL | `TEXTOS-PARA-APROVACAO.md:100` ainda «segunda a sábado, das 8h30 às 19h» | G-0075 (ALTO) | F1-54:20 |
| RG-024 | BAIXO | D-11 | Regra de adiar para 08:00 mostrada como vigente fora de pausado | **aberto** | PARCIAL | T:35 «lembrete adia para 08:00»; T:58, :80, :84 sem «inativo» | — | F1-54:21 |
| RG-025 | BAIXO | — | Índice da semana 1 aponta o DDL de a como final | **aberto** | ABERTO (opcional) | `estudos/semana-1/README.md:9` «DDL final testado»; sem linha na Parte F | — | F1-54:22 |
| RG-026 | MÉDIO | — | metodo_identidade: 04 manda gravar no POST e o 08 rejeita extras | **fechado com prova** | FECHADO (papel) | 04:82 «(RG-026) Gravar … `metodo_identidade`» | — | F1-54:23 |
| RG-027 | MÉDIO | D-11 | T8 até 20 min sobrevive nos estudos e o contrato 05 fixa 25 min | **aberto** | PARCIAL | T:111 «até 20 minutos depois»; F:64, H:97, K:175 sem nota | — | F1-54:24 |
| RG-028 | BAIXO | — | CPF não chega ao n8n é imprecisão de redação | **fechado com prova** | FECHADO (papel) | 01:221 «(RG-028) O CPF não viaja no Post nem na rota» | — | F1-54:25 |
| RG-029 | BAIXO | D-04 | Contrato 01 se contradiz sobre o fallback de SELECT | **aberto** | ABERTO (declarado) | 01:480 «Não entrou nesta versão: RG-029»; 01:70, :362, :439 × :451 | G-0235 (BAIXO) | F1-54:26 |
| RG-030 | BAIXO | — | Reserva da janela do gateway: domingo no mapa e sexta nos contratos | **superado** | SUPERADO, resíduo no kit | ROT:385 reserva 11/11; `kits/gateway/lib.sh:52-53` ainda 05 e 06/11 | — | F1-54:27 |
| RG-031 | MÉDIO | — | TTL do token do c360-auth 3600 s contra 900 s e timer sem etapa | **fechado com prova** | FECHADO (papel); kit do timer não existe | ROT:960 «≤ 900 s (v3.3) (RG-031)»; 07:40; timer pendente (ROT:1099) | — | F1-54:28 |
| RG-032 | MÉDIO | D-29 | B4.2 liga três flags do 360 e o contrato 03 liga duas | **fechado com prova** | FECHADO (papel) | ROT:964 «ligar só `C360_NAO_PERTURBE_30D` e `C360_LIMITE_CONTRATOS`»; 03:62 | — | F1-54:29 |
| RG-033 | MÉDIO | — | Painel e etapas citam versões e pendências já superadas | **aberto** | PARCIAL | ROT:897 ainda «08 v2.1 prevalece sobre este texto» | — | F1-54:30 |
| RG-034 | MÉDIO | — | B1.7 manda taguear v0.1.0 que já existe | **aberto** | PARCIAL | `docs/OPERACAO.md:47` e `:272` (main e ramo) ainda «tag `v0.1.0`» | G-0098 (MEDIO) | F1-54:31 |
| RG-035 | BAIXO | — | Aceite de A4.3 pede dump das duas bases e o kit recusa ia_obs | **aberto** | PARCIAL | `kits/s4/README.md:88-90` mantém a pendência «decisão do dono» | — | F1-54:32 |
| RG-036 | MÉDIO | D-16 | Go/no-go exige retenção zero por escrito mas o jurídico foi dispensado | **fechado com prova** | FECHADO (papel); ato pendente | ROT:1165 «retenção zero por escrito ou aceite escrito do dono»; assinatura até 13/11 (ROT:1454) | — | F1-54:33 |
| RG-037 | BAIXO | — | 14,2 mil jobs por dia é comentário de código rotulado medido | **fechado com prova** | FECHADO | `premissas.json:679-680` «comentário de código (não medido)» | — | F1-54:34 |
| RG-038 | BAIXO | — | Painel e CHANGELOG dizem 739 turnos e após as correções são 766 | **aberto** | PARCIAL | `src/ia-atendimento/CHANGELOG.md:152` ainda «739 turnos» | — | F1-54:35 |
| RG-039 | BAIXO | — | ia-sumidouro guarda o corpo por 7 dias e o roteiro diz que não | **fechado com prova** | FECHADO (papel) | ROT:475 «`ia-sumidouro` guarda 7 d, só chats da TI» | — | F1-54:36 |
| RG-040 | ALTO | D-01 | Chave Fireworks sem data trava A2.9 completa e B8.2 | **aberto** | ABERTO (ato do dono) | ROT:289 «chave Fireworks até ~~09/11~~ 17/11»; ROT:1123 ainda 09/11; ato sem registro | G-0369 (BAIXO) | F1-54:37 |
| RG-041 | CRÍTICO | D-02 | VPS não existe e a cadeia A4, o deploy 8 e a sombra ficam sem data | **aberto** | ABERTO (ato do dono) | ROT:290 «VPS contratada até 12/11 14:00»; REC §4 sem registro de A1.3/A1.5 | G-0001 (ALTO), G-0370 (BAIXO) | F1-54:38 |
| RG-042 | ALTO | D-03 | Perguntas ao ChatGuru não enviadas e A3.0 depende da A1.1 inteira | **aberto** | ABERTO (ato do dono) | ROT:285 «pendente do dono: 09/11, no pedido único»; sem registro | — | F1-54:39 |
| RG-043 | CRÍTICO | D-04 D-32 | Janela do gateway de 05/11 desenhada para merge já feito em 30/10 | **aberto** | aberta | 01:298-305 passos de 04–06/11; `kits/gateway/lib.sh:52-53`; Redeploy de 10/11 sem registro | G-0029 (MEDIO), G-0030 (MEDIO), G-0111 (MEDIO), G-0291 (BAIXO), G-0747 (BAIXO) | F1-55:11 |
| RG-044 | ALTO | D-05 | Checkpoint 0 sem insumo: r sem horas reais e dois limiares | **fechado só no papel** | só no papel | ROT:1302 exige «agentes vivos (≥ 4)»; REC §3 sem agente rastreável desde 04/11 | G-0057 (MEDIO), G-0372 (BAIXO) | F1-55:12 |
| RG-045 | ALTO | D-06 | B1.6 com 3 dias e doze obrigações herdadas sem folga | **aberto** | aberta | B1.6a só no PR #13 `CONFLICTING` (MAN:92); B1.6b sem branch (MAN:19-38) | G-0076 (ALTO), F4-028 | F1-55:13 |
| RG-046 | ALTO | D-06 | PR 6 aberto há quatro dias e B1.6 nasce sem base integrada | **fechado com prova** | com prova; reincide no #13 | ROT:360 «PR #6 mergeado em 04/11 01:27 UTC»; main `9a4baca` (MAN:3) | — | F1-55:14 |
| RG-047 | n/i | — | Camada B do dublê gerada por record de facta-on isolado | **refutado** | só no papel (resíduo aplicado) | ROT:930; `src/bancos-duble/README.md:20` | — | F1-55:15 |
| RG-048 | ALTO | D-07 | Cookie do RPA com 2FA humano e 18 dias sem renovação registrada | **aberto** | aberta | ROT:298 cookie 09/11; PD:45 «renovar antes de 18/11»; renovação sem registro | G-0288 (BAIXO) | F1-55:16 |
| RG-049 | ALTO | — | B2.1 e B5.1 não começaram e B2.4 saiu antes de B2.1 | **fechado com prova** | com prova no git | `bancos-duble/CHANGELOG.md:7`; B2.1 e B5.1 na main; ROT:364/:373 desatualizados | — | F1-55:17 |
| RG-050 | MÉDIO | D-08 D-24 | 05/11 concentra cinco toques do dono e o checkpoint | **superado** | superada na data | ROT:1435; ROT:1263-1264 (09 e 10/11 concentram mais toques) | G-0371 (MEDIO) | F1-55:18 |
| RG-051 | MÉDIO | D-03 | Webhook por mensagem decidido sem o ensaio A3.1 | **fechado só no papel** | só no papel | ROT:314 «(k) é HIPÓTESE até A3.1»; A3.1 sem registro | — | F1-55:19 |
| RG-052 | MÉDIO | — | Prazo do T8 apoiado em ciclo do robô de 30 min nunca lido | **fechado só no papel** | só no papel | 05:73 «~30 min: **HIPÓTESE**»; facta-on `app/config.py:123` = 10.0 | — | F1-55:20 |
| RG-053 | n/i | — | Meta de 85 a 90% dos pagos é o teto físico sem medição | **refutado** | superada (refutado, sem emenda) | RG:815; nenhuma ocorrência de «RG-053» na v3.3 | — | F1-55:21 |
| RG-054 | BAIXO | D-01 | B1.4 construída sobre hipóteses do provedor e texto residual em ROT:737 | **fechado só no papel** | só no papel | ROT:892 ainda «é o que A2.9 provou» (emenda só em A2.9a) | — | F1-55:22 |
| RG-055 | BAIXO | — | CPF sintético fixado em código enquanto os estudos o marcam hipótese | **fechado com prova** | com prova | `bancos-duble/docs/DECISOES-B2.1-0411.md:20`; resíduo `OPERACAO.md:243` | G-0442 (BAIXO), G-0593 (BAIXO) | F1-55:23 |
| RG-056 | n/i | — | Tetos globais presos no CHECK da 0001 são hipótese a medir | **refutado** | com prova (nota ajustada) | `migrations/0005_domingo_por_config.up.sql`; `DECISOES-B1.6a-0411.md:7` | — | F1-55:24 |
| RG-057 | MÉDIO | — | Orçamento de vagas de RPA escrito sem medição | **fechado só no papel** | só no papel | ROT:562 p50/p95 e 429 em A2.4; A2.4 sem registro | — | F1-55:25 |
| RG-058 | MÉDIO | — | Retentativa do ChatGuru em três vezes circula como fato | **fechado só no papel** | só no papel | ROT:1044 e 01:327 ainda «3× em ~6 s» sem rótulo (emenda só em A3.1) | G-0672 (BAIXO) | F1-55:26 |
| RG-059 | BAIXO | — | Orçamento de tokens por estimador e tokenizer nunca rodou | **aberto** | aberta | `tokens.py:1` «o tokenizer do DeepSeek ainda não foi medido» | — | F1-55:27 |
| RG-060 | MÉDIO | — | Crescimento do disco da S2 mistura três grandezas | **aberto** | aberta | `medicoes/` sem arquivo depois de 30/10; ROT:1609 | — | F1-55:28 |
| RG-061 | BAIXO | — | 56% das vendas do robô depois de 5 min não está na evidência | **aberto** | aberta (sem efeito no MVP) | memória `decisoes-dono-29-10-ia-deepseek.md:15` sem a nota | — | F1-55:29 |
| RG-062 | ALTO | D-19 | Ensaios n8n S1 a S6 e alcance NAT sem kit nem data | **aberto** | aberta | ROT:683-685 «**não existe hoje**»; `kits/` sem `n8n/` | G-0373 (MEDIO) | F1-55:30 |
| RG-063 | MÉDIO | D-03 | Ramo ia_ativa nos diálogos nomeado mas não dimensionado | **fechado só no papel** | só no papel | ROT:636 «Ramo «não» (v3.3)»; ROT:1303 | — | F1-55:31 |
| RG-064 | ALTO | D-11 | B5.5 depende de dicionário de contexto_codigos que ninguém escreveu | **aberto** | aberta | `TEXTOS-PARA-APROVACAO.md:3` «Versão 1, gerada em 30/10/2026»; dicionário não existe | G-0378 (MEDIO), G-0415 (MEDIO) | F1-56:13 |
| RG-065 | ALTO | — | Repasse forçado das 19:45 não existe no sp01, no 08 nem no código | **fechado só no papel** | só no papel (peça não existe) | 08:489 «Não entrou nesta versão: RG-065»; `fim_do_dia`/`19:45` no código: vazio | G-0078 (ALTO), G-0082 (MEDIO), G-0440 (MEDIO) | F1-56:14 |
| RG-066 | ALTO | — | O 08 exige migrações 0003 e 0004 na S4 e A4.6 só aplica duas | **fechado só no papel** | só no papel | ROT:717 «0001–0005»; `s4/migrar.sh` não existe | — | F1-56:15 |
| RG-067 | ALTO | — | Worker no compose da esteira sem etapa e A6.6 concluída com command inexistente | **aberto** | aberta | `ia-atendimento-esteira/docker-compose.yml:96` com `command` inexistente; prazo 08/11 vencido | G-0016 (ALTO) | F1-56:16 |
| RG-068 | ALTO | — | B3.1: DDL tap_retorno_dia sem passo nos Passos e sem kit | **fechado só no papel** | só no papel | ROT:947 «12:30–14:00» × ROT:946 «20:30»; 05:112 `/healthz` (rota real `/health`) | G-0375 (BAIXO) | F1-56:17 |
| RG-069 | MÉDIO | — | Retenção do texto mascarado do Phoenix e dos fulls sem número | **superado** | superada (D-32) | ROT:43 «registrar N d não basta» | G-0258 (BAIXO) | F1-56:18 |
| RG-070 | MÉDIO | — | Referência de aceite 23,4% de pago com denominador diferente do funil | **aberto** | só no papel, em parte | ROT:1192 «compara com 23,4 %»; lev 08 e J:170 sem a definição | — | F1-56:19 |
| RG-071 | BAIXO | — | Rampa de disparos exige dois PUT de config em produção sem linha na rotina | **superado** | superada (cenário C) | ROT:1177 (cenário C prevalece); `config/set.sh` não existe | — | F1-56:20 |
| RG-072 | MÉDIO | — | Volta do pausado perto de 23 h: M promete lembretes que P-R20 aboliu | **fechado só no papel** | só no papel | ROT:1016 «(RG-072) 4ª divergência de M»; r2 da B5.7b não tocada | — | F1-56:21 |
| RG-073 | MÉDIO | — | Fatos do estudo N sem chave contratada no payload do braço | **aberto** | aberta | 04:95 sem as chaves v2; `contexto.py:75-84` sem `cpf_alterado` | G-0077 (MEDIO) | F1-56:22 |
| RG-074 | BAIXO | — | Credenciais ia-n8n-braco e ia-c360-n8n sem etapa | **fechado só no papel** | só no papel | ROT:960, :1055; 03:214 «Não entrou nesta versão: RG-074» | — | F1-56:23 |
| RG-075 | MÉDIO | — | texto_livre.casos.json exigido por quatro contratos não existe | **fechado só no papel** | só no papel (peça não existe) | ROT:904, :1049, :1099; nenhum `*casos.json` em `src/` | — | F1-56:24 |
| RG-076 | MÉDIO | — | Spec de B5.2 pede ao T1 um campo que o 360 não emite | **fechado só no papel** | só no papel | ROT:981 «fora `status_atendimento`»; resíduo `pessoas_teste/formas.py:280` | — | F1-56:25 |
| RG-077 | BAIXO | — | Smoke de leitura real do 360 em sombra falta no roteiro | **fechado só no papel** | só no papel | ROT:960 «T1/T3 contra o 360 de **produção**»; ato sem registro | — | F1-56:26 |
| RG-078 | BAIXO | D-32 | Spec e Aceite de B5.7b sem a emenda da revisão r2 | **fechado com prova** | com prova | `fila.py:138` `alarme_retomar`; `:157` `jobs_presos` | — | F1-56:27 |
| RG-079 | MÉDIO | — | Kits supostos prontos (K-E1 a K-E20, ddl-espelho) não existem | **fechado só no papel** | só no papel (peça não existe) | ROT:1132-1134; `kits/` sem `ensaios/`, `vigia/`, `n8n/`, `gateway/ativar.sh` | G-0377 (MEDIO) | F1-56:28 |
| RG-080 | BAIXO | — | Frequências dos ramos da abertura são hipótese e a sombra não as conta | **fechado só no papel** | só no papel | ROT:1154 «antes de 23/11» × ROT:1153 «antes de 26/11» | — | F1-56:29 |
| RG-081 | BAIXO | — | Vhost WG loga a URI com chat_id e o 08 proíbe chat_id em log | **aberto** | aberta no contrato | 02:55 sem a nota «risco aceito»; ROT:1612 admite a emenda pendente | G-0376 (BAIXO) | F1-56:30 |
| RG-082 | BAIXO | — | Credencial da IA com atribuicao:registrar atribui a qualquer perfil | **aberto** | aberta nos contratos | 03:214 «Não entrou… RG-082»; 06:22 sem nota de risco | — | F1-56:31 |
| RG-083 | n/i | — | Dois regimes de permissão em /etc/ia-s4 | **refutado** | refutado no núcleo, resíduo aberto | `distribuir-certs.sh:85,88`; resíduo `cifra.py:113-114` (0600) e `ensaio-local.sh:206` sem `%U` | G-0041 (MEDIO), G-0374 (MEDIO) | F1-56:32 |
| RG-084 | MÉDIO | D-03 | A5.9 pega-tudo real passou de 01/11 sem começar | **fechado só no papel** | só no papel | ROT:763-765 «só o pega-tudo»; prazo 11/11 | — | F1-56:33 |
| RG-085 | BAIXO | — | repasse_etapa tem seis valores no DDL e cinco no 08 | **aberto** | aberta (BAIXO, sem efeito) | 08:489 «Não entrou… RG-085»; `passos.py:225` `cerco` sem produtor | — | F1-57:11 |
| RG-086 | BAIXO | D-31 | Corpus bruto do ChatGuru na S3 sem ciclo de vida escrito | **fechado só no papel** | só no papel | ROT:133 é a única menção; A6.3 sem ciclo de vida | G-0674 (BAIXO) | F1-57:12 |
| RG-087 | MÉDIO | D-12 | Repasse em 2 h dispensa o lembrete de 4 h que recupera 48% | **fechado só no papel** | só no papel | ROT:1143 «(ah) fica, D-12 N-2»; B5.5/B5.6 sem código | — | F1-57:13 |
| RG-088 | BAIXO | — | B5.6 com seeds como constantes, faixa única e modelo único | **fechado só no papel** | só no papel | ROT:1002 «seeds como constantes; faixa única»; B5.6 sem código | — | F1-57:14 |
| RG-089 | MÉDIO | D-18 | Cenário C do domingo mistura definições e a faixa é desconhecida | **superado** | superada | RG:1021 «Superados por estas respostas: RG-089»; ROT:1599 | — | F1-57:15 |
| RG-090 | MÉDIO | D-15 | E-11: motor de camada 1 só grava, C4 e C6 valem | **fechado só no papel** | só no papel | ROT:1462 «Respondida (v3.3) (D-15…)»; SQL do relatório não existe | — | F1-57:16 |
| RG-091 | ALTO | D-19 | Corpo do ia-agendar no n8n sem saveData none e sem ensaio S4 | **aberto** | aberta | 04:373 «[ABERTO] Texto do cliente no corpo de `ia-agendar`» × PD:42 «Sem objeto» | G-0379 (BAIXO) | F1-57:17 |
| RG-092 | n/i | — | Marca ia em flags e selo IA revertidos sem pergunta ao dono | **refutado** | refutado, continua | ROT:1096 «Sem selo «IA»»; resíduo na ata A1.10 não enviada | — | F1-57:18 |
| RG-093 | ALTO | D-15 | C6 tirou o cerco e a mitigação depende de A3.2 e A3.4 | **aberto** | aberta | A3.4 remarcada para 10–11/11 (ROT:643); B6.5 «cortada (C6)» (ROT:390) | G-0056 (ALTO) | F1-57:19 |
| RG-094 | MÉDIO | D-12 | Cinco respostas do estudo N ao dono sobre ler mensagem e lembrete | **fechado só no papel** | só no papel | ROT:127 «N-1 «sim, mínima»»; leitura da fala pendente não existe | — | F1-57:20 |
| RG-095 | ALTO | D-14 | Até 30 do repasse: tentativas ou minutos e regra de repassando preso | **aberto** | superada na letra; regra R-c2 aberta | 08:244 «30 min esgotados ⇒ `repasse_travado`»; R-c2 «Pendente, sem decisão» (ROT:1718) | G-0032 (ALTO) | F1-57:21 |
| RG-096 | MÉDIO | D-27 | Telefone em claro em ia_espelho.sob_ia durante o atendimento | **fechado só no papel** | só no papel (risco aceito) | ROT:132 «D-27 como está»; 04:21 | — | F1-57:22 |
| RG-097 | ALTO | D-17 | Pessoas e semente: substituto do Danilo, revisor e lista nominal | **aberto** | aberta | ROT:1457 «pendentes do dono: substituto e revisor» | — | F1-57:23 |
| RG-098 | ALTO | D-13 | Janela de 24 h no PD D3: espera ou proxy | **fechado só no papel** | só no papel, parte em código | `api/atendimentos.py:89-93`; regra `espera` do `iniciar` não existe | G-0380 (BAIXO) | F1-57:24 |
| RG-099 | ALTO | D-10 | Ok ao desenho mínimo de K na ata A1.10 | **fechado só no papel** | só no papel | ROT:295 «ok» a K dado (D-10); B6.4 sem código | — | F1-57:25 |
| RG-100 | ALTO | D-11 | Textos: reemissão com emendas do N e aprovação em dois lotes | **aberto** | aberta | `TEXTOS-PARA-APROVACAO.md:3` «Versão 1, gerada em 30/10/2026»; TX-42: 0 ocorrências | F4-001 | F1-57:26 |
| RG-101 | MÉDIO | D-21 | Comissão por pago: R$ 100 e 4% no lugar de R$ 250 | **fechado só no papel** | só no papel | ROT:130 «R$ 100 / 4 % como proxy»; ROT:242 «conta não refeita» | — | F1-57:27 |
| RG-102 | MÉDIO | D-17 | Uma amostra só de 30 em dobro para L-Q1 e o portão da sombra | **fechado só no papel** | só no papel, com contradição | ROT:1165 amostra de 30 × ROT:498 revisor opcional | G-0387 (MEDIO) | F1-57:28 |
| RG-103 | MÉDIO | D-22 | Parada leve ia_ativa false devolve também os pausado | **fechado com prova** | com prova no orquestrador; vigia não existe | `jobs.py:42-43`; `chave.py:7` | G-0080 (MEDIO) | F1-57:29 |
| RG-104 | MÉDIO | D-23 | Regra de sem trigger em tabela nova vale para o banco ia_atendimento | **fechado com prova** | com prova no código | `migrations/0003_estado_aditivo.up.sql:4` e `:27` | G-0120 (MEDIO), G-0673 (BAIXO), R2-022 | F1-57:30 |
| RG-105 | BAIXO | — | Nota de repasse: uma chamada por marco com cópias idênticas possíveis | **fechado só no papel** | só no papel | ROT:1057 «uma chamada de `nota` por marco»; B6.3 sem código | — | F1-57:31 |
| RG-106 | BAIXO | D-20 | M-05 tri-state e M-06 lista estreita (E-14) | **fechado só no papel** | só no papel, parte em código | `ferramentas/esquemas.py:164-171` (`indeterminado`); B5.4 não existe | — | F1-57:32 |
| RG-107 | BAIXO | — | Residual de PII sem NER nunca apresentado ao dono | **aberto** | aberto | `mascara.py:1-19` só regex; ata A1.10 não saiu (ROT:295) | G-0384 (MEDIO), G-0420 (MEDIO) | F1-58:22 |
| RG-108 | MÉDIO | D-24 | Kit de rotação das duas chaves expostas (A1.8) não existe | **superado** | superado (D-24) e não existe | ROT:501 «depois do piloto, a partir de 02/12»; kit «A escrever» (ROT:1732) | G-0385 (MEDIO) | F1-58:23 |
| RG-109 | BAIXO | — | msg_fingerprint com chave permanente permite recuperar mensagens curtas | **fechado só no papel** | só no papel (residual aceito) | ROT:38 «Residual conhecido (v3.3, RG-109)» | — | F1-58:24 |
| RG-110 | MÉDIO | D-25 | Ciência do superior ao piloto (A1.11) e perguntas à FACTA (A1.12) | **aberto** | aberto | ROT:297 «não iniciada; **vencida desde 30/10**» | — | F1-58:25 |
| RG-111 | MÉDIO | D-26 | Colheita real na S2 e contagem do M-06 até 05/11 | **aberto** | aberto | ROT:344 «colheita real: **sem registro de execução**»; tap ausente da main | G-0381 (MEDIO), G-0492 (MEDIO), G-0493 (MEDIO) | F1-58:26 |
| RG-112 | BAIXO | — | Tela da IA: sim, sim, sim, 30 dias, nota só para a TI | **superado** | superado | ROT:523; Parte F linha 204 (estudo da tela, D-T01…D-T34) | — | F1-58:27 |
| RG-113 | MÉDIO | D-28 | Caso (b) da agenda: cortar fluxo n8n, A5.9 parte (b) e B5.7c | **superado** | superado (cenário C) | ROT:132 «**caso (b) fora do MVP**»; resíduos ROT:1016-1017 e kit do gateway | G-0383 (BAIXO) | F1-58:28 |
| RG-114 | ALTO | D-15 | ia_leitura_a, leitor.py e rotas 03 §5.1/§5.2 fora do MVP | **fechado só no papel** | só no papel | ROT:967-969; 03:69, :91, :202; B4.3 sem código | G-0564 (BAIXO) | F1-58:29 |
| RG-115 | MÉDIO | D-05 | C9 inteiro agora: promptfoo, ntfy.sh e B7.1 só a chave | **fechado só no papel** | só no papel | ROT:328, :391; sem `promptfoo` nem `ntfy` em `src/` | — | F1-58:30 |
| RG-116 | MÉDIO | — | Reserva Together fora de A1.3, A1.4 e do G0 | **fechado com prova** | fechado com prova | `agente.py:4` e `:280` «sem `FallbackModel`»; `config.py:26` | — | F1-58:31 |
| RG-117 | BAIXO | — | A3.4 (a) re-dispara: duas esperas de 2 h, não cortar | **fechado só no papel** | só no papel | ROT:135 «RG-117 não corta»; A3.4 não iniciada (ROT:317) | — | F1-58:32 |
| RG-118 | n/i | — | DDL e kit da S4 levam peças de fase 2 ao G1 | **refutado** | refutado, continua | `kits/s4/ensaio-local.sh:134-138`, `:180-181`, `:203-204` | — | F1-58:33 |
| RG-119 | MÉDIO | D-06 | IRMAO_TOKEN e CI cruzado vão para B12.2 e gitleaks entra nos check.sh | **fechado com prova** | fechado com prova | `ia-atendimento/scripts/check.sh:15`; `scripts/gitleaks.sh:9-13`; sem `IRMAO_TOKEN` | G-0470 (MEDIO) | F1-58:34 |
| RG-120 | BAIXO | — | B8.3 de contingência de modelo já está fora dos 83,5 dias | **fechado só no papel** | só no papel | ROT:1125 «condicional (< 95 %)» | — | F1-58:35 |
| RG-121 | MÉDIO | — | B6.9 vira script manual em 30/11 e 13/12 | **fechado só no papel** | só no papel | ROT:394, :1090-1093; o script não existe | G-0382 (MEDIO) | F1-58:36 |
| RG-122 | n/i | — | Coolify da S2 como servidor remoto da VPS | **refutado** | refutado, continua | esteira `scripts/deploy-vps.sh:10-12` e `:77` | — | F1-58:37 |
| RG-123 | BAIXO | D-30 | Phoenix só por túnel SSH no tailnet sem Cloudflare Access | **fechado só no papel** | só no papel | esteira `docker-compose.yml:48` (127.0.0.1:6006); `:52` ainda cita `cloudflared` | G-0067 (MEDIO), G-0676 (BAIXO) | F1-58:38 |
| RG-124 | n/i | — | Reconciliador RPA de 2 min sem condição e contra (k) | **refutado** | refutado, continua | 01:84 «O reconciliador RPA (B6.1b) é a recuperação» | — | F1-58:39 |
| RG-125 | n/i | — | Campo consultor sempre nulo no ia-repasse | **refutado** | refutado, continua | 08:235 «`consultor` (**sempre `null`** no MVP…» | — | F1-58:40 |
| RG-126 | BAIXO | — | B2.2: deriva semanal do catálogo e replay no CI | **fechado só no papel** | só no papel | ROT:931 comparação manual; `bancos-duble` `ci.yml` sem `schedule` | — | F1-58:41 |
| RG-127 | n/i | — | Braço n8n com dois caminhos de identidade e ia-ui-estado | **refutado** | refutado, continua | 04:79, :47, :118 | — | F1-58:42 |
| RG-128 | MÉDIO | D-06 D-09 | CI do ia-atendimento nunca chegou ao pytest: 24 de 24 falharam | **fechado com prova** | fechado com prova (código) | `ia-atendimento/.github/workflows/ci.yml:37-38` | G-0675 (BAIXO) | F1-58:43 |

**Resíduos que a tabela não mostra em uma linha.**
- RG-010 (refutado): o contrato 05 vigente ainda proíbe gravar a mensagem «nem normalizada» (05:106). O PR #49 do facta-on tem merge em 12/11. O revisor teria de recusá-lo pelo contrato (F1-53.md:61).
- RG-083 (refutado no núcleo): a aplicação exige 0600 na chave AES (`cifra.py:113-114`) e em `gateway-hmac.keys`/`saida.json` (`segredos.py:47-48`). A OPERACAO não fixa o dono desses arquivos. A API recusa subir no deploy #8 (F1-56.md:55-56; G-0374).
- RG-103 (com prova no orquestrador): a Spec da B6.4 ainda troca só `aberto` no CAS (ROT:1063), contra D-22 (G-0080).
- RG-113 (superado): o corte do caso (b) não chegou ao corpo de B5.7c (ROT:1016-1017) nem ao kit do gateway (F1-58.md:49).
- RG-128 (com prova): «CI da main verde em 04/11» (ROT:259) não é verificável daqui (F1-58.md:79).

Regras de leitura e normalização dos estados: §8.0.

---

## Notas da revisão final (10/11, noite)

Um crítico independente propôs 25 correções e apontou 10 erros (E1–E10) e 13 faltas (F1–F13). Cada uma foi conferida na fonte antes de entrar. Abaixo, o que mudou e o que foi rejeitado, com o motivo.

**Aplicadas.**

| Item do crítico | O que mudou | Prova conferida |
|---|---|---|
| E2, correção 2 (parte) | §4 item 19: a flag de não perturbe é c360 `config.py:838` (`nao_perturbe_30d`) | `src/cliente360-api/src/c360api/config.py:838`, validador `:840-846` |
| E3, correção 3 | §4 item 2: 13 perguntas ao ChatGuru e a pergunta 4 à FACTA | `fase0/decisoes-delegadas.md:162` |
| E5, correção 5 | §2 linha 2 e topo do §7 com a mesma regra: nenhuma RS sem achado vivo; só RS-02 conta como atendida (só BAIXO) | §7.0, definição de `ATENDIDA`; §7.1 linha RS-02 |
| E6, correção 6 | §6 conta 86 achados; F4-035 e F4-036 ficam no §5; título do §6.4 com «3 MÉDIO» | §6.4 tem 3 linhas |
| E7, correção 7 | G-0085 em B1.6a/B1.7 no §4 item 11, igual ao §3.2 e ao índice do §5 | correções de `fase3/grupos/G-0085.json`: «critério de aceite do B1.6/B1.7» |
| E8, correção 8 | índice do §5, G-0084: kit 18/11 no cenário C, 19/11 12:30 no degrau | §3.2; DN-29 |
| E9, correção 9 | §1 «Quem fez» inclui Sonnet 5.5 na verificação 3b e 3d | Anexo A.1 |
| E10, correção 10 (parte) | §7.0, §10.7 e §10.8 usam SO-nn e o executor do §9b | §9b, regra 3 e coluna «Origem» |
| F1, correção 11 | nova subseção do §5 com os 65 MÉDIO sem RS; título e «Como ler» do §5 corrigidos | filtro sobre `fase3/consolidado.json`: 65 grupos, 58 ausentes do documento |
| F2, correção 12 | §3.3 desconta a Parte A (−0,03), soma os 65 MÉDIO sem RS e marca «não verificado» o resíduo das 100 peças. Com 4 agentes o pacote ALTO dá ≈ 0,47 < 0,49 | `ROT:1230` «baixa todos os limites em ≈ 0,03» |
| F3, correção 14 | §2 linha 3 e §1: os achados são piso, não teto | §10.2 (28 %), §10.3 (critério de parada) |
| F4, correção 13 | §2: 18 ALTO de código em PR e 11 de decisão, kit ou processo, com ids | índice do §5 |
| F5, correção 20 | §4, nova seção «ALTO sem linha no calendário»: 7 de papel e 15 «não existe» | grep no §4 de cada id; bloco tirado do §6.5 |
| F6, correção 18 | §4 itens 27a e 27b (G-0126) e 27c (G-0106) | `modo.py:96-97`; `bancos-duble/README.md:38-50` |
| F7, correção 19 | §4 item 27a decide G-0114 antes da tag (item 32); sem resposta, a tag sai com G-0114 aberto e escrito | correção de `G-0114.json`: «Decidir a costura antes da B1.6» |
| F8, correção 16 | §4 «Como ler» com raízes de caminho e as três cópias de kit | `fase0/MANIFESTO.md:99-127`; F4-022 |
| F10, correção 21 | legenda «Quem» define «revisão»; item 13a (o «sim» à edição do ROT); comando do portão de memória no item 9 | `decisoes-delegadas.md:77,81`; PLANO §6 |
| F11, correção 22 | §4 itens 1 e 2: DN-04 e DN-01 vencidos, estado por SO-13 e resposta do dono | §9a.1 |
| F12, correção 15 | §2 linha 4: pergunta 1 do PLANO sem resposta até as sondas | PLANO §2 item 1; §9 «Como ler» |
| F13, correção 23 | §1 «Como ler»: RG-041 CRÍTICO × G-0001 ALTO; vale a mais alta | `fase0/inventario-rg.csv:42` |
| E4, correção 4 (parte) | §6.2 e Anexo B: `ia_atendimento.fila.app` não existe; o app vem de `criar_app` em `fila.py:79-83` | `src/ia-atendimento/src/ia_atendimento/fila.py:79-83` |

**Aplicadas em parte ou rejeitadas.**

| Item do crítico | Decisão | Motivo |
|---|---|---|
| E1, correção 1 | em parte | `ROT:1582` traz, sim, «contratos não se editam nesta rodada» (Parte F, linha 72, sobre o 05). Mas a regra foi riscada em `ROT:106`, e as emendas de 04/11 foram aplicadas. O texto agora cita as duas linhas |
| E2, correção 2 (parte do §6.3b) | rejeitada | A linha G-0035/G-0554 do §6.3b fala de `vendedor_ator_id`, e `config.py:861` é exatamente esse campo. A prova está certa |
| E4 (parte do §5) | rejeitada | O §5, F4-016, «Relacionados», não diz «módulo inexistente»; diz `ia_atendimento.fila.app` |
| F4, contagem | ajustada | O crítico listou 10 ids para «11». O 11º é G-0118, que pede decisão do dono (DN-23) antes de mexer na main |
| F9, correção 17 | em parte | Não foi criada uma coluna nas 9 tabelas diárias. A regra «Pronto quando» no «Como ler» do §4 aponta, por id, para o teste ou prova de feito. As tabelas novas de ALTO têm a coluna |
| Correção 10 (ids S na matriz) | em parte | As células «S8», «S26» etc. do §7.1 e §7.3 não foram renomeadas. O §7.0 dá a regra de equivalência e o §9b, a coluna «Origem» |
| Correção 14 | em parte | O veredito segue com 10 linhas: o «piso» entrou na linha 3, não numa linha 11 |
| Correção 23 | em parte | A frase foi para o «Como ler» do §1, que vale para o documento todo, e não para o §2.5 ou §8.2 |
| Correção 24 | em parte | §7.4 e §8.3 viraram Anexos B e C no mesmo arquivo. Arquivo separado não foi criado: esta etapa só pode gravar este arquivo |
| Correção 25 | rejeitada | O §3.2 compara cenário C × degrau por ato, o que o §4 não faz. Mantido, com G-0085 alinhado |
| «Cada ALTO em até 6 lugares» | rejeitada | Cada seção serve a um leitor do mapa do §1. O corte foi só o dos Anexos B e C |
| F2, cifra «≈ 6,5 d-agente» | aceita como estimativa | Peso 0,1 × 65, o mesmo peso dos outros MÉDIO; não medido |

**Não verificado nesta etapa.** O estado vivo de DN-01, DN-04 e dos atos de 09–10/11 (nenhuma sonda tem saída). Se o resíduo de 63,6 d-agente já conta as 100 peças «não existe».
