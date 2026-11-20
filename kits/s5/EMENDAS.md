# Emendas de papel: «VPS» → «S5» (não aplicadas)

Levantamento de 20/11/2026. A S5 substitui a VPS do planejamento (DEC-PIA-009). **Nenhum contrato nem o roteiro foi editado**: as
emendas dependem das respostas do dono (capacidade da S5, onde ficam os bancos, IP no WireGuard). Esta nota diz **onde** mexer.

## Regra que reduz o trabalho

Se a S5 herdar o IP da VPS no WireGuard (**`WG_IP_S5=10.90.0.5`**, recomendação do kit), **todas as citações de `10.90.0.5` continuam
certas** e a emenda vira só troca de nome («VPS» → «S5»). Com outro IP, cada linha com `10.90.0.5` abaixo muda de valor também, e as
variáveis dos kits (`DESTINO_IA_MENSAGEM`, `PREFIXO_ORQUESTRADOR`, `IP_APP`, `IA_API_URL`) passam a ser obrigatórias.

| Decisão do dono | Efeito nas emendas |
|---|---|
| `WG_IP_S5 = 10.90.0.5` | só nome; nenhum número muda |
| `WG_IP_S5` diferente | nome **e** IP em todas as linhas com `10.90.0.5` (contratos 01, 03, 04, 08; kits s4, gateway, config) |
| `BANCO_LOCAL = s4` (padrão de 29/10) | A4.2, A4.3b e o kit s4 continuam (com «VPS» → «S5»); peer S4↔S5; regra nft da S4 com o IP da S5 |
| `BANCO_LOCAL = s5` | A4.2 perde o lado S4; A4.3 inteira sai da S4 e vai para `kits/s5/60-banco.sh`; o `pg_hba` e o nft da S4 **não** mudam; o contrato 03 (leitura `ia_leitura_a`) passa a apontar `WG_IP_S5:5432` com a CA da S5; A4.8 (pgBackRest da S4) vira `kits/s5/80-backup.sh`; **contraria a decisão de 29/10** e pede «sim» explícito |

## Contratos (`/opt/claude/docs/planejamento-ia/contratos/`)

| Arquivo | Linhas | O que muda |
|---|---|---|
| `01-gl-gateway.md` | 12, 88, 113, 131, 133, 145, 231, 234, 235, 238, 278, 319, 365 | «VPS» → «S5»; `destino` e prefixo `http://10.90.0.5:8000/…` só se o IP mudar; l.231 já diz «arquivo 0600, nunca no Coolify» (bate com a esteira nova) |
| `02-chatguru-api.md` | 52, 97, 166, 167, 168, 198 | «VPS» → «S5»; `allow 10.90.0.5` do vhost WG só se o IP mudar |
| `03-cliente360-api.md` | 13, 20, 52, 85, 137, 142 | «VPS» → «S5»; com `BANCO_LOCAL=s5`, a prova F21 (l.85) e a leitura `ia_leitura_a` passam a ser na S5 (`hostssl` com a CA da S5, `kits/s5/60-banco.sh`) |
| `04-n8n-braco-espelho.md` | 206, 378, 385, 394, 401 | «VPS» → «S5»; `GET http://10.90.0.5:8000/readyz` e `allow 10.90.0.5` só se o IP mudar |
| `05-facta-on.md` | 28, 66 | «vhost WG da VPS» → «da S5» |
| `07-cliente360-web.md` | 99 | «`PUT /config` na VPS» → «na S5» |
| `08-orquestrador.md` | 26, 201, 263, 291, 358 | l.26: `uvicorn --host 10.90.0.5` agora é `--host ${IA_BIND_IP}` (compose da esteira); «VPS» → «S5» |

## Roteiro (`ROTEIRO-DE-ACAO.md` v3.3, 117 citações de «VPS», 23 de `10.90.0.5`)

Agrupado por seção (números de linha de hoje). Onde o passo **muda de conteúdo**, e não só de nome, está em negrito.

| Seção | Linhas | Emenda |
|---|---|---|
| Cabeçalho, §0.1, §0.3 | 5–7, 19, 42, 45 | nome |
| §0.5b, §0.5c, §0.6 (D24–D26, P-R8, P-R10) | 115–170, 228, 231, 257, 260, 267 | D24–D26: «OVH VPS-2 em BHS» → «S5 (servidor próprio do dono)»; **P-R8**: a imagem não é construída pelo Coolify, vem do registro da S3 por tag (esteira); **P-R10**: `/etc/ia-s4` → `${IA_SEGREDOS_DIR}` (padrão `/etc/ia-s5`), arquivos `10001 0600` (G-0097) |
| Painel | 290, 294, 322–331, 347, 385, 405 | **A1.5 vira «S5 entregue pelo dono» (`kits/s5/00-pre-requisitos.md`)**; A4.1 → `10-endurecer.sh` + `20-docker.sh`; A4.2 → `30-wireguard.sh`; A4.4 → `40-firewall.sh` (lado S5) + vhost da S2 (inalterado); A4.6 → `migrar.sh` (G-0012); A4.7 → `70-alerta.sh`; A4.8 → `80-backup.sh` se `BANCO_LOCAL=s5`; A4.9 → `deploy-s5.sh` |
| PD (l.429) | 429 | kit da S5 em `~/retomada-2809/fila-2910/ia/s5/` (e `kits/s5/` no repositório) |
| A1.3, A1.4, **A1.5**, A1.10 | 482, 487, **490–491**, 512–519 | **A1.5 reescrita**: o dono informa a S5 (lista do `00-pre-requisitos.md`), não contrata VPS |
| A2.2, A3.0, A3.8 | 555, 626, 684 | nome |
| **A4 (cabeçalho e A4.1–A4.10)** | **687–743** | **A4.1 e A4.4 (lado S5) passam a ser os scripts do kit**; o bloco de A4.6 (l.718–727, ledger fora da transação, G-0011) sai e aponta `migrar.sh`; A4.9: `uvicorn --factory …ambiente:criar_app_de_ambiente --host ${IA_BIND_IP}` e worker `python -m ia_atendimento.worker` (F4-016, G-0016); permissão única `10001 0600` (G-0097) |
| A5.0, A6.6, A8.1 | 753, 760, 804, 824 | A6.6: `deploy-vps.sh` → `deploy-s5.sh` (G-0095), environment `producao-vps` → `producao-s5`, variável `REGISTRO_IMAGEM` |
| Mapa de deploys | 855–867 | nome; o «portão da VPS» vira o da S5 |
| B1.7, B2.2, B4.1, B5.1 | 911, 931, 960, 976 | nome |
| B6.0–B6.7 | 1036–1082 | nome; IP só se mudar |
| B9.3, B11.3, Dia a dia | 1147–1149, 1184–1185, 1264–1297 | nome; o piloto de 26–30/11 foi cancelado (DEC-PIA-011): datas novas quando a S5 existir |
| Parte D, Parte E, Padrões, Parte F | 1348–1430, 1452–1460, 1482–1499, 1511–1572 | Parte D: o desvio «VPS não sai» vira «S5 não entregue»; Parte F é histórico (não emendar) |

## Kits fora deste diretório (`~/retomada-2809/fila-2910/ia/`)

| Kit | Onde | Emenda |
|---|---|---|
| `s4/` | `lib.sh` (`VPS_SSH_DEST`, `VPS_T`), `s4-hba.sh:38` (`IP_APP=10.90.0.5`), `distribuir-certs.sh`, `provar.sh`, `desfazer.sh`, README | `VPS_SSH_DEST` → o ssh da S5; `IP_APP` = `WG_IP_S5`; **a entrega `root:10001 0640` contraria G-0097**: o `60-banco.sh --aplicar` (opção s4) copia de `S4_ENTREGA_DIR` para `${IA_SEGREDOS_DIR}` como `10001 0600`, então a entrega pode ficar como está. Só vale com `BANCO_LOCAL=s4` |
| `s4/migrar.sh` | novo (G-0012) | atalho para `s5/migrar.sh --alvo s4` |
| `gateway/` | `lib.sh:37,41`, `env-gateway.sh:23`, `entregar-hmac-vps.sh`, `montar_env.py`, README | nome; `DESTINO_IA_MENSAGEM`/`PREFIXO_ORQUESTRADOR` só se o IP mudar; `entregar-hmac-vps.sh` grava a chave HMAC: na S5 o destino é `${IA_SEGREDOS_DIR}/gateway-hmac.keys`, `10001 0600` (ou usar `kits/s5/50-segredos.sh instalar gateway-hmac.keys`) |
| `config/chats-teste.sh` | 25, 27, 33, 93 | `IA_API_URL` padrão `http://10.90.0.5:8000` só muda com o IP |

## No repositório `ia-atendimento` (fora desta PR, para não colidir com o ramo de `src/`)

`docs/OPERACAO.md` cita «VPS» nas l.5, 41, 82, 115, 157 e 258 e `/etc/ia-s4` na §2 e §8. A §8 ganhou nesta PR só a nota de que, na S5,
os segredos são arquivos (DEPLOY.md §4); o resto fica para a emenda depois das respostas do dono.
