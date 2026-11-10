# Reconciliação do estado em 5 vias e linha do tempo — IA de atendimento (Fase 0, 10/11/2026)

Só leitura. Nenhum dado de cliente. Linhas `ROT:l.N` são da v3.3 medida hoje (sha256 `508cab01…`, `fase0/MANIFESTO.md:130`); a âncora de texto é o ID da linha na tabela «Painel de estado» ou o trecho citado.

## 0. Fontes e limites

| Via | Fonte | Última escrita | Observação |
|---|---|---|---|
| 1 Painel / Parte C | `/opt/claude/docs/planejamento-ia/ROTEIRO-DE-ACAO.md`, «## Painel de estado» (l.279–413) e «# PARTE C» (l.1203–1295) | 04/11 16:27 (mtime; última linha da Parte F = #208, l.1718) | anterior à integração de 04/11 ~19h |
| 2 git | `fase0/MANIFESTO.md` + exportação `src/<repo>/` (CHANGELOG, `docs/`) | manifesto 10/11 09:00 | o mtime dos arquivos exportados é a data do commit da ponta: ia-atendimento e bancos-duble 04/11 19:27; gl-gateway 30/10 16:29; `feat/b1-6a` 04/11 16:03; cliente360-api 10/11 00:34. `cliente360-web` **não foi exportado** (MANIFESTO:8, local ≠ remoto) |
| 3 memória | `memory/ia-roteiro-estado.md` (04/11 19:30), `decisoes-dono-03-11-recomendacoes.md` (04/11 15:02), `planejamento-ia-atendimento.md` (03/11), `MEMORY.md` (índice) | 04/11 19:30 | `handoff-29-10-ia-semana-1.md` e `handoff-30-10-ia-manha.md` não foram relidos: o índice `MEMORY.md` os marca como «histórico… superado» e são anteriores à janela |
| 4 Kan | quadro `fejw8oz1nuze` | — | **Kan não lido.** O único caminho de leitura (`~/bin/kan`, linhas 12 e 14) é `ssh s2 "curl … 127.0.0.1:8131"`; ssh está proibido nesta revisão. Coluna Kan = «NL» em todas as linhas |
| 5 kits × Parte C | `~/ia-revisao-0911/kits/` (28 arquivos, `fase0/inv-kits.tsv`) | kit mais novo: `merge-0411/merge-0411.sh` 04/11 19:08 | cópia sem arquivos 0600; MANIFESTO:128 «Kits omitidos» está vazio |

**Regra aplicada:** git é a autoridade para código. Para atos de produção (S2, S4, Coolify, n8n, ChatGuru) nenhuma das 5 vias lê o estado vivo: «sem registro» não prova «não feito» (`PLANO-REVISAO-0911.md` §0.1).

## 1. Tabela etapa por etapa

Legenda: NI = não iniciada · C = concluída · NL = não lido · «=» sem divergência · **DIV** = divergência (vira achado no §5).

### Parte A

| ID | 1 Painel (ROT) | 2 git | 3 memória | 4 Kan | 5 kits × Parte C | Divergência |
|---|---|---|---|---|---|---|
| E0 | C 29/10 (l.284) | n/a (papel) | — | NL | — | = |
| A1.1a | NI; pendente do dono 09/11 (l.285) | n/a | pendência do dono (`ia-roteiro-estado.md:20`) | NL | — | sem registro do ato de 09/11 (§4) |
| A1.1b | NI (l.286) | n/a | — | NL | — | = |
| A1.2 | dispensada 30/10 (l.287) | n/a | `ia-roteiro-estado.md:17` | NL | — | = |
| A1.3 | NI; entrega 09/11, limite 10/11 (l.288) | n/a | `decisoes-dono-03-11-recomendacoes.md:21` | NL | — | sem registro; limite vence hoje |
| A1.4 | NI; chave até 17/11 (l.289) | n/a | idem | NL | — | = |
| A1.5 | NI; VPS até 12/11 14:00; «sim» ao `s4-hba.sh` 09/11 13:15 (l.290) | n/a | `ia-roteiro-estado.md:12` «VPS ainda não existe» | NL | `s4/s4-hba.sh` existe | sem registro do «sim» de 09/11 |
| A1.6 | NI, fora por D-30 (l.291) | n/a | — | NL | — | = |
| A1.7 | NI; substituto e revisor até 11/11 (l.292) | n/a | — | NL | — | = |
| A1.8 | NI; depois de 02/12 (l.293) | n/a | — | NL | kit de rotação ainda não previsto | = |
| A1.9 | C «sim p/ g1» 03/11 (l.294) | n/a | `ia-roteiro-estado.md:22` | NL | — | = |
| A1.10 | NI; ata até 10/11; «ok» a K dado (l.295) | n/a | — | NL | — | sem registro da ata; vence hoje |
| A1.11 | NI; até 13/11 (l.296) | n/a | — | NL | — | = |
| A1.12 | NI; no pedido único de 09/11 (l.297) | n/a | — | NL | — | sem registro |
| A1.13 | NI; cookie 09/11 à noite (l.298) | n/a | — | NL | — | sem registro |
| A2.1–A2.3, A2.5, A2.7, A2.8, A2.10 | C 30/10 (l.299–308) | n/a (medições em `medicoes/`, 30/10) | — | NL | — | = |
| A2.4 | NI; 10/11 de manhã (l.302) | n/a | — | NL | — | sem registro (a vencer hoje) |
| A2.6 | C 02/11; 3ª leitura de `df` em 09/11 (l.304) | n/a | — | NL | — | **DIV leve:** nenhuma medição nova em `medicoes/` (última: `INCIDENTE-3010-gateway.md`, 30/10 16:18) |
| A2.9 | NI (l.307) | n/a | sem chave | NL | — | = |
| A2.11a | aplicada 03/11 19:18 (l.309) | `premissas.json` e `custos.csv` com mtime 03/11 19:18 | — | NL | — | = |
| A2.11b | NI (l.310) | n/a | — | NL | — | = |
| A2.12 | NI; (a)–(c) em 09–10/11 (l.311) | n/a | — | NL | — | sem registro; nenhuma medição nova |
| A2.13 | NI; só estudo (l.312) | sem arquivo de estudo em `estudos/` | — | NL | — | = |
| A3.0–A3.7 | NI; A3.0 em 10/11 08:30 (l.313–320) | n/a | — | NL | `gateway/e12-sumidouro.sh`, `ativar-sumidouro.sh`, `ia-sumidouro.workflow.json` existem | dependem do reinício de 10/11 05:30, sem registro (§4) |
| A3.8 | NI; 09/11 12:30, pendente (l.321) | n/a | — | NL | **kit ausente**: ROT:l.684 «importar o fluxo inativo `zz-ensaio-ui`… (**não existe hoje**)»; `kits/` não tem pasta `n8n/` | sem registro; kit não existe |
| A4.1, A4.2, A4.4, A4.5, A4.7–A4.10 | NI (l.322–331) | n/a | — | NL | `gateway/entregar-hmac-vps.sh` existe; `ntfy/` não | = (dependem da VPS) |
| A4.3 | kit pronto; A4.3a em 09/11 13:15 (l.324) | `kits/s4` 148cc72 só local (MANIFESTO:13, :36 «ahead 1, behind 178») | `ia-roteiro-estado.md:13` «Kit S4 sem push» | NL | `s4/` com 8 arquivos (30/10) | sem registro do ato de 09/11 |
| A4.6 | NI; 13/11 12:30 (l.327) | 0001–0005 na main (`src/ia-atendimento/migrations/`) | `ia-roteiro-estado.md:44` | NL | **`s4/migrar.sh` ausente** (ROT:l.717 «a escrever»; l.1262 previa em 05–08/11) | atraso de kit (§2) |
| A5.0–A5.8 | versões 01 v2.5, 03 v2.2, 04 v2.2, 07 v2.2, 08 v2.4 (l.332–340) | n/a (papel): `contratos/` com mtime 04/11 16:25–16:27 | `ia-roteiro-estado.md:40` | NL | — | = (emenda do 02 segue «pendente», l.332) |
| A5.9 | NI; ≤ 11/11 (l.341) | n/a | — | NL | — | = |
| A6.1, A6.2 | C 30/10 (l.342–343) | `CHANGELOG.md:169` «[0.2.0] - 2026-10-30»; `migrations/0001.sha256` | — | NL | — | = |
| A6.3 | C no repo; colheita real sem registro (l.344) | `src/bancos-duble/CHANGELOG.md:52` «[0.1.2]» | `ia-roteiro-estado.md:13` | NL | kit da colheita fica na S2 (fora da cópia) | = |
| A6.4 | C: PR #49 em rascunho (l.345) | MANIFESTO:96 «#49 … draft=true mergeable=**CONFLICTING**»; tap ausente da main (`facta-on/app/config.py` sem `TAP`) | `ia-roteiro-estado.md:24` | NL | — | **DIV:** o PR passou a conflitar depois dos merges #50–#56 de 05–09/11 (`PLANO-REVISAO-0911.md` §0.5) |
| A6.5 | C 30/10 (l.346) | n/a | `ia-roteiro-estado.md:8` | NL | — | não conferível sem o Kan |
| A6.6 | C em parte (l.347) | `feat/esteira` 9e1afe3 só local (MANIFESTO:12, :32 «ahead 2, behind 178») | `ia-roteiro-estado.md:11` «ainda sem push» | NL | `deploy-vps.sh` e `release.sh` só na branch | = |
| A6.6b | NI; **≤ 08/11** (l.348) | não feita: `src/ia-atendimento-esteira/docker-compose.yml:96` ainda `procrastinate … worker`; sem push | gate declarado (`ia-roteiro-estado.md:24`) | NL | — | **DIV de prazo:** vencida em 08/11 sem entrega |
| A7.1 | pronta; reemissão 05/11; lotes 11/11 e 13/11 (l.349) | n/a (papel): `textos/TEXTOS-PARA-APROVACAO.md` com mtime 30/10 09:13 | pendência (`ia-roteiro-estado.md:19`) | NL | — | **DIV de prazo:** reemissão prevista para 05–08/11 (ROT:l.1262) não aconteceu; 1º lote é amanhã |
| A7.2 | NI (l.350) | — | — | NL | — | = |
| A8.1–A8.5 | C (l.351–355) | n/a | — | NL | — | = |

### Parte B

| ID | 1 Painel (ROT) | 2 git (autoridade) | 3 memória | 4 Kan | 5 kits × Parte C | Divergência |
|---|---|---|---|---|---|---|
| B1.1, B1.2, B1.3 | C 30/10, v0.2.0 (l.356–358) | `CHANGELOG.md:169`; `docs/REVISAO-B1.{1,2,3}-3010*.md` | — | NL | — | = |
| B1.4 | PR #9 mergeado, não concluída até A2.9a (l.359) | na main: `CHANGELOG.md:25`; `src/ia_atendimento/{turno,agente,contexto}.py` | `ia-roteiro-estado.md:32` | NL | — | = |
| B1.5 | C, #6 (l.360) | `src/ia_atendimento/api/` (14 arquivos); `migrations/0004_anexo_rpa_e_espelho.up.sql` | idem | NL | — | = |
| B1.6 | **NI**; «construção local desde 05/11» (l.361) | **B1.6a existe em PR #13** (MANIFESTO:92, `feat/b1-6a` 9a714e3, CONFLICTING; `src/ia-atendimento-b1-6a/src/ia_atendimento/{ledger,gasto,espera,expiracao,espelho}.py`, `docs/DECISOES-B1.6a-0411.md:9`); **B1.6b sem branch nem worktree** (MANIFESTO:19–38) | `ia-roteiro-estado.md:41,43,44` | NL | — | **DIV:** Painel não tem a divisão a/b nem o PR #13; o #13 conflita com a main (a branch não tem a 0005 nem o pacote `ferramentas/`) |
| B1.7 | NI; limite 12/11 (l.362) | `pyproject.toml:3` = 0.2.0; sem v0.3.0 | `ia-roteiro-estado.md:32` «sem tag» | NL | — | = (em risco: depende da B1.6b) |
| B1.8 | **NI**; «local desde 05/11, até 09/11» (l.363) | **na main** (9a4baca): `migrations/0005_domingo_por_config.up.sql`; `CHANGELOG.md:12`; `docs/DECISOES-B1.8-0411.md`, `docs/REVISAO-B1.8-0411.md` | `ia-roteiro-estado.md:44` «#12 … → main 9a4bacab» | NL | — | **DIV** |
| B2.1 | **NI** (l.364) | **na main** (ca3ed2c): `src/bancos-duble/CHANGELOG.md:7` «Etapa B2.1»; `docs/DECISOES-B2.1-0411.md`, `docs/REVISAO-B2.1-0411.md` | `ia-roteiro-estado.md:44` «#5 → main ca3ed2cf» | NL | — | **DIV.** O próprio CHANGELOG (:7) ainda diz «Só local, PR sem merge» |
| B2.2, B2.3 | NI (l.365–366); até 11/11 (ROT:l.1240) | não feitas: `docs/DECISOES-B2.1-0411.md:79` «seguem nas etapas deles»; sem branch (MANIFESTO:58–63) | — | NL | — | = (prazo de amanhã sem trabalho rastreável) |
| B2.4 | C, #8 e duble #2 (l.367) | `CHANGELOG.md:53`; `kits/chats-teste.sh` no repo | `ia-roteiro-estado.md:32` | NL | `config/chats-teste.sh` existe | = |
| B3.1, B3.2 | NI; #5 em 12/11 (l.368–369); PR único até 11/11 (ROT:l.1240) | `facta-on/app/config.py:123` `conferir_janela_min: float = 10.0`; só o #49, em conflito | — | NL | — | = (em risco) |
| B4.1–B4.3 | NI; #3 em 11/11, #4 em 12/11 (l.370–372) | nenhuma rota `/v1/ia` em `src/cliente360-api/src` (busca vazia); último release `CHANGELOG.md:115` «[0.25.19] - 2026-11-05», sem item da IA | — | NL | — | = (em risco: deploy em 1–2 dias sem código) |
| B5.1 | **NI** (l.373) | **na main**: `src/ia_atendimento/ferramentas/` (12 arquivos); `CHANGELOG.md:7`; `docs/DECISOES-B5.1-0411.md` | `ia-roteiro-estado.md:44` «#14 → main» | NL | — | **DIV** (aceite só depois da B1.6, `DECISOES-B5.1-0411.md:65–67`) |
| B5.2–B5.6 | NI (l.374–378) | sem código nem branch (MANIFESTO:19–38) | — | NL | — | = ; B5.3 e B5.5 (stubs) estavam previstas para 05–08/11 (ROT:l.1262) |
| B5.7a | C 30/10 (l.379) | `docs/REVISAO-B5.7a-3010*.md` | — | NL | — | = |
| B5.7b | C, #7 (l.380) | `CHANGELOG.md:84`; `src/ia_atendimento/{estado_pausa,agenda_estado,worker}.py` | `ia-roteiro-estado.md:32` | NL | — | = |
| B5.7c | NI; 13→16/11 (l.381) | — | — | NL | — | = |
| B5.7d | **NI**; «até 09/11» (l.382) | **parte de código na main**, entregue com a B1.8: `src/ia_atendimento/agenda_extrator.py:101,590,595,620`; resíduo = corpus ≥ 12 frases (`docs/DECISOES-B1.8-0411.md:12,46`); sem branch | — | NL | — | **DIV:** estado real = parcial; resíduo vencido em 09/11 |
| B5.8 | cortada C3 (l.383) | — | — | NL | — | = |
| B5.9 | NI (l.384) | — | — | NL | — | = |
| B6.0 | mergeada e no ar v0.4.0 (30/10); reinício único 10/11 05:30 «ainda não executado» (l.385) | gl-gateway 92e9754 remoto = local (MANIFESTO:5); `docs/DECISOES-B6.0.md` 30/10 | `ia-roteiro-estado.md:12` | NL | `rotas-ia.sh`, `env-gateway.sh`, `portao.sh`, `vigia.sh`, `desfazer.sh` existem; **`gateway/README.md` ainda descreve 05/11 05:30 e reserva 06/11** (`README.md:62,96,142,144`; mtime 03/11 19:13) | **DIV kit × roteiro:** o roteiro (l.385) e o contrato 01 v2.5 dizem 10/11, reserva 11/11; reinício sem registro (§4) |
| B6.1 | NI (l.386); 10→16/11 | sem branch nova no gl-gateway (MANIFESTO:64–67) | — | NL | `gateway/ativar.sh` e `n8n/importar.sh` ausentes | = |
| B6.2 | NI; contagem agregada em 09/11 (l.387) | sem código | — | NL | — | sem registro da contagem; «contra o contrato» em 05–08/11 (ROT:l.1262) não aconteceu |
| B6.3 | NI (l.388) | — | — | NL | — | = |
| B6.4 | NI; «ok» a K dado (l.389) | sem código | R-c2 pendente (`ia-roteiro-estado.md:40`) | NL | `espelho/ddl-espelho.sh`, `vigia/instalar.sh`, `devolver-leads` ausentes | = ; construção local de 05–08/11 não aconteceu |
| B6.5 | cortada C6 (l.390) | — | — | NL | — | = |
| B6.6–B6.9 | NI (l.391–394) | — | — | NL | `config/domingo.sh` ausente (B6.7) | = |
| B7.1 | NI; «PR `cliente360-web` #635 **aberto**» (l.395) | não verificável na exportação (web não exportado) | `ia-roteiro-estado.md:38` «dono mesclou cliente360-web #635» (04/11 15:06 BRT, merge `47760f7b`); `:42` #638 mesclado | NL | — | **DIV:** Painel diz aberto, memória diz mesclado; só spec, sem código da IA |
| B7.2 | NI (l.396) | — | — | NL | — | = |
| B8.1a | C 30/10 (l.397) | `docs/REVISAO-B8.1a-3010*.md`; `src/ia_atendimento/corpus/` | — | NL | — | = |
| B8.1b | NI; 13→15/11 (l.398) | — | — | NL | — | = |
| B8.1c | NI (l.399) | parte entregue com a B1.8: `CHANGELOG.md:18` (`corpus/calendario.py` com `domingo_aberto`); `docs/REVISAO-B1.8-0411.md:27` | — | NL | — | **DIV leve:** parcial |
| B8.2, B8.3 | NI (l.400–401) | — | — | NL | — | = |
| B9.0–B9.5a, B10.1, B11.x, B12.x | NI (l.402–413) | — | — | NL | kits `ensaios/` (B9.0, 17/11) ainda não devidos | = |

## 2. Kits previstos × existentes

Existem em `kits/` (28 arquivos): `gateway/` (18: `rotas-ia.sh`, `env-gateway.sh`, `montar_env.py`, `portao.sh`, `vigia.sh`, `desfazer.sh`, `migrar.sh`, `sql/migra_rotas_ia.sql`, `aguardar-reinicio.sh`, `entregar-hmac-vps.sh`, `e12-sumidouro.sh`, `ativar-sumidouro.sh`, `ia-sumidouro.workflow.json`, `ensaio-local.sh`, `ensaio_stub.py`, `lib.sh`, `README.md`), `s4/` (8), `config/chats-teste.sh`, `merge-d06/`, `merge-0411/`. Nenhum arquivo de estado ou registro de execução na cópia.

**Previstos e inexistentes:**

| Kit | Onde o roteiro o pede | Devia existir em | Usado em | Estado |
|---|---|---|---|---|
| `s4/migrar.sh` | ROT:l.1262 «kits `s4/migrar.sh`, `config/domingo.sh`, `gateway/ativar.sh` e o da chave AES de dezembro»; l.717 «kit `s4/migrar.sh` a escrever» | 05–08/11 | A4.6, 13/11 12:30 | **inexistente, vencido** |
| `config/domingo.sh` | ROT:l.1262; l.392; l.1081 | 05–08/11 | B9.5a 15/11 (dev), publicação 18/11, fechar 30/11 07:30 | **inexistente, vencido** |
| `gateway/ativar.sh` | ROT:l.1262; l.861 «o kit `ativar.sh` ainda não existe, nasce em B6.1» | 05–08/11 (Parte C) ou B6.1 (l.861): o roteiro se contradiz | 19/11 12:30 | **inexistente** (existe `ativar-sumidouro.sh`, outro propósito) |
| kit da chave AES de dezembro | ROT:l.1262; l.1219; l.1272 | 05–08/11 | 18/11 12:30 | **inexistente, vencido** |
| kit do A3.8 (`zz-ensaio-ui`, com export e remoção) | ROT:l.684 «(**não existe hoje**)»; l.321 «Claude (kit)» | antes de 09/11 12:30 | 09/11 12:30 | **inexistente; o ato de 09/11 não tinha kit** |
| `n8n/importar.sh` | ROT:l.756, l.865, l.1055 | B6.1 / antes de 16/11 | deploy #6, 16/11 | inexistente (ainda não vencido) |
| `espelho/ddl-espelho.sh` | ROT:l.1064, l.1133 | com a B6.4 | deploy #6, 16/11 | inexistente (ainda não vencido) |
| `vigia/instalar.sh` | ROT:l.1732 «`vigia/instalar.sh` (B6.4)» | com a B6.4 | 16/11 | inexistente |
| `devolver-leads` | ROT:l.1063, l.389 | com a B6.4 | 16/11; ensaio a seco 18/11 | inexistente |
| `config/set.sh` | ROT:l.1732 «A escrever: `config/set.sh <nome> <valor>`» | sem data | — | inexistente |
| `ntfy/instalar.sh` | ROT:l.1732 | A4.7/B6.6 | 12→16/11 | inexistente |
| `ensaios/` (6–8 kits com auto-reversão) | ROT:l.402 (B9.0) | 17/11 | 24–25/11 | inexistente (ainda não vencido) |
| kit de rotação da chave (A1.8) | ROT:l.293, l.1732 | depois do piloto | ≥ 02/12 | inexistente (não devido) |

Fora de `kits/`: `deploy-vps.sh` e `release.sh` só na branch local `feat/esteira` (MANIFESTO:12); kit da colheita na S2 (ROT:l.344), não conferível daqui.

**Kit existente e desatualizado:** `gateway/README.md:62` «### Quinta 05/11, 05:30 BRT», `:96` «Reserva: sexta 06/11», `:142–144`. O cenário C (04/11 à tarde) moveu o reinício para 10/11, reserva 11/11 (ROT:l.385; ROT:l.1264). Nenhum arquivo de `gateway/` foi tocado depois de 03/11 19:51.

## 3. Linha do tempo 04/11 → 10/11 (o que aconteceu de fato na IA)

| Quando (BRT) | Fato | Fonte |
|---|---|---|
| 03/11 22:27 | D-06: dono mescla ia-atendimento #10, #6, #7, #8, #9 (main `6abaf02`) e bancos-duble #2 | `ia-roteiro-estado.md:32`; ROT capa (l.4) |
| 04/11 ~11:00 | Dono responde ao parecer do Codex («segue recomendações suas» + 5 respostas) | `decisoes-dono-03-11-recomendacoes.md:19`; `estudos/PARECER-CODEX-32-DECISOES-0411.md` (mtime 11:09) |
| 04/11 | Dono adia o início para seg 09/11 e fixa o teto 04/12 | `decisoes-dono-03-11-recomendacoes.md:31,33`; `ia-roteiro-estado.md:36–37` |
| 04/11 14:45 | Replanejamento escrito (3 cenários) | `estudos/REPLANEJAMENTO-INICIO-0911.md` (mtime) |
| 04/11 15:06 | Dono mescla cliente360-web #635 (spec da tela da IA) | `ia-roteiro-estado.md:38` |
| 04/11 tarde | Cenário C adotado; construção só local liberada | `decisoes-dono-03-11-recomendacoes.md:35,41`; ROT:l.1205 |
| 04/11 16:03–16:08 | Último commit de `feat/b1-6a`; PR #13 atualizado pela última vez | exportação `ia-atendimento-b1-6a/docs` (mtime 16:03); MANIFESTO:92 (`2026-11-04T19:08:16Z`) |
| 04/11 16:25–16:27 | Contratos emendados (01 v2.5, 03 v2.2, 04 v2.2, 07 v2.2, 08 v2.4) e **última escrita do roteiro** | mtime de `contratos/*.md` e de `ROTEIRO-DE-ACAO.md`; Parte F #206–#208 (l.1716–1718) |
| 04/11 | Dono mescla cliente360-web #638 (DECISOES + PEDIDOS-DE-CONTRATO da tela) | `ia-roteiro-estado.md:42` |
| 04/11 19:08 | Kit `merge-0411.sh` escrito | `kits/merge-0411/merge-0411.sh` (mtime; linhas 2, 19) |
| 04/11 ~19:00–19:27 | Dono mescla bancos-duble #5 (B2.1) → `ca3ed2c`; ia-atendimento #12 (B1.8) e #14 (B5.1) → `9a4baca` | `ia-roteiro-estado.md:44`; MANIFESTO:3–4; mtime da exportação (19:27) |
| 04/11 19:30 | Última escrita da memória e do `RETOMAR-0911.md` | mtimes |
| **05–08/11** | **Nada rastreável na IA.** Previsto: construção local de B1.6b, B5.7d, B5.3, B5.5, B6.2, B6.4, A6.6b, 4 kits e reemissão dos textos (ROT:l.1262). Fato: nenhum branch, worktree, PR ou kit novo; textos sem reemissão | MANIFESTO:19–38 e :90–98; `kits/` (mtimes ≤ 04/11 19:08); `textos/` (30/10); `plano/critica-r1.md:124` |
| 05–09/11 | Fora da IA, mas na fronteira: facta-on recebe os merges #50–#56 (merge = deploy), o que põe o PR #49 em conflito; cliente360-api 0.25.19 em 05/11 e trabalho de pré-aprovações/estoque | `PLANO-REVISAO-0911.md` §0.5; `plano/critica-r1.md:113`; `src/cliente360-api/CHANGELOG.md:57–115`; MANIFESTO:96 |
| 05–09/11 | O índice da memória só registra outros projetos nesses dias (complementos do Claude, senha pela TI, C6 financiado, ponto, coeficiente CLT, consulta LUX, FACTA off, disco da S3) | `MEMORY.md`, entradas datadas 05/11, 06/11 e 09/11 |
| 09/11 (dia) | **Nenhum ato da IA com registro** em memória, roteiro, RETOMAR, origin/main ou kits | §4; `PLANO-REVISAO-0911.md` §0.1 |
| 09/11 noite | Dono pede a revisão completa; plano v1 (~21h), crítica r1 (21:06), crítica v2 (21:19) | `PLANO-REVISAO-0911.md` cabeçalho; `plano/critica-r1.md`, `plano/critica-v2.md` (mtimes) |
| 10/11 03:40 | Deploy de outro projeto (admissão FACTA off no C6); nada da IA | `MEMORY.md`, última entrada |
| 10/11 05:30 | Reinício do gateway previsto: **sem registro** | §4 |
| 10/11 08:59–09:00 | Plano v3; dono: «faça enquanto respondo» e Fases 1–5 autorizadas; manifesto e exportação | `PLANO-REVISAO-0911.md` cabeçalho e §8; MANIFESTO:1 |

## 4. Atos previstos para 09/11 e 10/11

Fontes do previsto: ROT:l.1263–1264 (Parte C) e `RETOMAR-0911.md` («Atos do dia 09/11 e de 10/11»). Nenhum tem prova. Estado «sem registro» = nenhuma das vias lidas o registra; produção e Kan não foram lidos.

| Quando | Ato | Quem | Estado | Onde a prova deveria estar |
|---|---|---|---|---|
| 09/11 manhã | Pedido único: A1.3, A1.5, A1.4, A1.1a (13 perguntas), A1.12 (pergunta 4), ata A1.10 | dono | **sem registro** | memória `decisoes-dono-*`, Painel l.285–297 |
| 09/11 12:30 | `!` A3.8 (`zz-ensaio-ui`) | dono | **sem registro**; o kit não existe (§2) | Painel l.321 |
| 09/11 13:15 | `!` A4.3a (`s4-papeis.sh`, «sim», `s4-hba.sh`) | dono | **sem registro** | Painel l.324; leitura de papéis/`pg_hba` da S4 |
| 09/11 > 20:30 | `!` `rotas-ia.sh` e `env-gateway.sh --gravar` + ensaio da vigia | dono | **sem registro** | Painel l.385; `gateway.rotas` e env do Coolify |
| 09/11 noite | Cookie do RPA renovado, com `salvo_em` (A1.13) | Danilo | **sem registro** | Painel l.298 |
| 09/11 | `pgbackrest info` e `df` da S2 (X4, X5) | Claude | **sem registro** (nenhum arquivo novo em `medicoes/`) | `medicoes/`, Painel l.304, l.329 |
| 09/11 | Conferir que o env do gateway não foi gravado em 04/11 | Claude | **sem registro** | Painel l.385 |
| 09/11 | Contagem agregada antes de B6.2 (H1–H3) | Claude | **sem registro** | Painel l.387 |
| 09/11–10/11 | A2.12 (a)–(c) | Claude | **sem registro** | Painel l.311 |
| 09/11 noite | Volume do gateway (X3, < 150 por 10 min) | Claude | **sem registro** | — |
| 09/11 | Agentes de construção «seguem» (B1.6b primeiro) | Claude | **sem registro**: B1.6b sem branch (MANIFESTO:19–38) | git |
| 10/11 05:30 | `portao.sh`, Redeploy, vigia `--desde` (#2) | dono + Danilo | **sem registro**; a pré-condição (rotas e env na noite de 09/11) também não tem registro ⇒ pelo roteiro cai na reserva de 11/11 05:30 | Painel l.385, l.313 |
| 10/11 manhã | A2.4 | Claude/Danilo | **sem registro** | Painel l.302 |
| 10/11 08:30 | A3.0–A3.3 no chat de teste | Danilo | **sem registro**; dependem do reinício e de A1.1a | Painel l.313–316 |
| 10/11 12:00 | D-09: exigir PR na `main` (3 repos) | dono | **sem registro** do «exigir PR»; ruleset `main-protegida` de 04/11 cobre só exclusão e force-push (`PLANO-REVISAO-0911.md` §0.4; a crítica r1, `plano/critica-r1.md:130`, dizia «Branch not protected») | GitHub (não lido aqui) |
| 10/11 | Limite de A1.3 e ata A1.10 | dono | **sem registro** | Painel l.288, l.295 |
| 10/11 18:00 | Checkpoint 0 (agentes vivos, regra X7) | Claude | a vencer hoje; nenhum agente de construção rastreável | ROT:l.1231 |
| 10/11 > 20:30 | A4.2 e A4.3b, se a VPS veio | dono | a vencer; VPS sem registro | Painel l.323–324 |

**Feito com prova: nenhum.** Único ato de 09–10/11 com prova é a própria revisão (plano, críticas, manifesto), que não está na Parte C.

## 5. Achados (um por divergência)

- **REC-01 — achado: estado do roteiro desatualizado.** B1.8 consta «não iniciada» (ROT:l.363); está na main `9a4baca` (`migrations/0005_domingo_por_config.up.sql`, `CHANGELOG.md:12`).
- **REC-02 — achado: estado do roteiro desatualizado.** B2.1 consta «não iniciada» (ROT:l.364); está na main `ca3ed2c` do bancos-duble (`CHANGELOG.md:7`, `docs/DECISOES-B2.1-0411.md`).
- **REC-03 — achado: estado do roteiro desatualizado.** B5.1 consta «não iniciada» (ROT:l.373); o pacote `ferramentas/` está na main (`CHANGELOG.md:7`).
- **REC-04 — achado: estado do roteiro desatualizado.** B1.6 consta «não iniciada» (ROT:l.361) e o Painel não tem a divisão a/b; a B1.6a existe no PR #13 (MANIFESTO:92), hoje em conflito com a main; a B1.6b não começou.
- **REC-05 — achado: estado do roteiro desatualizado.** B5.7d consta «não iniciada» (ROT:l.382); o código da agenda com domingo já entrou com a B1.8 (`agenda_extrator.py:101,590`); falta só o corpus, vencido em 09/11.
- **REC-06 — achado: estado do roteiro desatualizado.** B8.1c consta «não iniciada» (ROT:l.399); `corpus/calendario.py` já aceita `domingo_aberto` (`CHANGELOG.md:18`).
- **REC-07 — achado: estado do roteiro desatualizado.** B7.1 diz «PR `cliente360-web` #635 aberto» (ROT:l.395); a memória registra #635 e #638 mesclados em 04/11 (`ia-roteiro-estado.md:38,42`). Não conferido em git (web fora da exportação).
- **REC-08 — achado: estado do roteiro desatualizado.** A6.4 diz «concluída: PR #49 em rascunho» (ROT:l.345) sem dizer que o PR conflita com a main do facta-on desde os merges de 05–09/11 (MANIFESTO:96); o deploy #5 de 12/11 depende do rebase.
- **REC-09 — achado: estado do roteiro desatualizado.** A6.6b tem prazo «≤ 08/11» (ROT:l.348), vencido sem entrega: `feat/esteira` segue em 9e1afe3, sem push (MANIFESTO:32).
- **REC-10 — achado: estado do roteiro desatualizado.** A7.1: reemissão dos textos prevista para 05–08/11 (ROT:l.349, l.1262); `textos/TEXTOS-PARA-APROVACAO.md` não muda desde 30/10. O 1º lote do dono é 11/11.
- **REC-11 — achado: estado do roteiro desatualizado.** A linha «05–08/11» da Parte C (ROT:l.1262) e os estados «local desde 05/11» (l.361, l.363, l.382; faixas L1–L7, l.1238–1244) descrevem construção que não deixou rastro: nenhum branch, worktree, PR ou kit novo depois de 04/11 19:27.
- **REC-12 — achado: estado do roteiro desatualizado.** A conta do resíduo (ROT:l.1226, 10 dias a partir de 09/11) supõe 09/11 como dia de construção; sem trabalho rastreável em 09/11, valem 9 dias (`PLANO-REVISAO-0911.md` §0.3). A parcela já entregue em 04/11 (B1.8, B2.1, B5.1, parte da B1.6 e da B5.7d) também não foi descontada.
- **REC-13 — achado: estado do roteiro desatualizado.** Kits que a Parte C dá como escritos em 05–08/11 não existem: `s4/migrar.sh`, `config/domingo.sh`, `gateway/ativar.sh`, chave AES de dezembro (§2). O roteiro se contradiz sobre o `ativar.sh` (l.1262 × l.861).
- **REC-14 — achado: estado do roteiro desatualizado.** A3.8 marcado para 09/11 12:30 (ROT:l.321) com kit que o próprio roteiro diz não existir (l.684); sem kit e sem registro.
- **REC-15 — achado: estado do roteiro desatualizado (kit × roteiro).** `kits/gateway/README.md:62,96,142,144` ainda manda o reinício para 05/11 05:30 com reserva 06/11; roteiro e contrato 01 v2.5 dizem 10/11 e 11/11. Quem seguir o README na janela lê datas mortas.
- **REC-16 — achado: estado do roteiro desatualizado.** Todos os atos de 09/11 e 10/11 (§4) seguem no Painel como futuros («pendente do dono: 09/11», l.285, l.290, l.297, l.298, l.321, l.324, l.385) sem marca de feito nem de vencido; o reinício de 10/11 05:30 não tem registro e A3.0–A3.7 e o aceite da B1.6 escorregam com ele.
- **REC-17 — achado: estado do roteiro desatualizado.** Leituras de 09/11 sem resultado gravado: 3ª leitura de `df` (ROT:l.304), `pgbackrest info` (l.329), contagem agregada antes de B6.2 (l.387), A2.12 (l.311). `medicoes/` não tem arquivo depois de 30/10.
- **REC-18 — achado: estado do roteiro desatualizado (memória).** `ia-roteiro-estado.md:3` (descrição) ainda diz «30/10 noite… B1.5 em PR #6» e a linha 8 cita o roteiro «v3.1»; o índice `MEMORY.md` repete «30/10 noite: G0». O corpo vai até 04/11 19:30 e nada depois.
- **REC-19 — achado: estado do roteiro desatualizado.** `src/bancos-duble/CHANGELOG.md:7` diz «Só local, PR sem merge» para a B2.1, já mesclada (git × texto do próprio repo).
- **REC-20 — limite da reconciliação.** Kan não lido (via 4 inteira) e produção não lida: o estado de cada cartão e de cada ato de 09–10/11 só fecha com a resposta do dono à pergunta do `PLANO-REVISAO-0911.md` §7.1 ou com leitura autorizada.
