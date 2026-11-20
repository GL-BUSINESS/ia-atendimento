# Kit da S5 — servidor da IA de atendimento

Prepara a S5 (substitui a «VPS» do planejamento; DEC-PIA-009) para receber o orquestrador da esteira (`docker-compose.yml`,
`docs/DEPLOY.md`). Cópia de trabalho em `~/retomada-2809/fila-2910/ia/s5/`; versão revisada em `kits/s5/` do `ia-atendimento`.

**Antes de tudo:** `00-pre-requisitos.md` (o que o dono informa e faz). **Depois:** `EMENDAS.md` (onde o papel cita a VPS).
**Ensaio:** `ensaio-local.sh` e o resultado em `ENSAIO.md`.

## Contrato de todos os scripts

- **Padrão = simular**: mostra o que faria e não muda nada. `--aplicar` faz de verdade, como root na S5, com o «sim» do dono (PD-2).
- **Para no primeiro erro** e diz a linha. **Idempotente**: rodar de novo depois de corrigir é seguro.
- **Nunca imprime segredo**: segredo entra por arquivo ou stdin e sai só para arquivo `0600`. Configuração no `s5.env` (copiar de
  `s5.env.exemplo` para `/etc/ia-s5-adm/s5.env`, root 0600), lido por um parser que recusa `$`, crase, `;`, `|`, `&`, `<`, `>`.
- `--env ARQ` troca o arquivo de configuração. `verificar.sh` é só leitura e confere tudo.

## Ordem

Tempo = estimativa de relógio na S5 (download incluído, link comum); «mão do dono» = o que ele faz fora do script.

| # | Comando (na S5, de `sudo -i` ou `sudo bash`) | Muda | Tempo | Retorno esperado |
|---|---|---|---|---|
| 0 | copiar o kit e o `s5.env` preenchido para a S5 (`scp -r s5/ <s5>:`) | nada | 5 min | `/etc/ia-s5-adm/s5.env` 0600 |
| 1 | `bash 10-endurecer.sh` → `--aplicar` | pacotes, usuário de admin, SSH só chave, atualizações de segurança, UTC/NTP, journald, sysctl, Tailscale | 5–8 min | «concluído no modo aplicar»; abrir **outra** janela: `ssh <admin>@<s5> true` entra. Tailscale: o dono aprova o nó |
| 2 | `bash 20-docker.sh` → `--aplicar` | Docker CE, `daemon.json`, Docker após o wg0, login no registro da S3 | 3–5 min | `docker info` com `live-restore=true`; «login ok» |
| 3 | `bash 30-wireguard.sh --aplicar` (1ª vez) | gera o par de chaves | 1 min | mostra a **pública** e o bloco para a S2 (e S4); **sai com código 3** de propósito (faltam os peers) |
| 3b | dono: roda o bloco na S2/S4 e devolve `WG_PUB_S2`, `WG_ENDPOINT_S2` (e S4) → preencher o `s5.env` | S2/S4: peer aditivo | 10 min | — |
| 3c | `bash 30-wireguard.sh --aplicar` (2ª vez) | `wg0.conf` e `wg-quick@wg0` | 1 min | handshake «ok»; `ping` na S2 |
| 4 | `bash 40-firewall.sh --aplicar` **por SSH** | tabela `inet ia_s5` com reversão em 180 s | 1 min | «aplicado. A tabela SOME sozinha…» |
| 4b | de uma **conexão nova**: `ssh <admin>@<s5> 'sudo bash …/40-firewall.sh --aplicar --confirmar'` | persiste (`ia-s5-nft.service`) | 1 min | «CONFIRMADO». Se a conexão nova não abrir: não fazer nada; a tabela some sozinha |
| 5 | `bash 50-segredos.sh preparar --aplicar` | diretórios, segredos internos, chave AES do mês, tópico do ntfy | 1 min | nomes dos arquivos, nunca valores |
| 5b | dono: `50-segredos.sh instalar MODELO_API_KEY_1 / gateway-hmac.keys / saida.json --aplicar` (stdin, sem eco); `mostrar-topico` | arquivos 0600 do uid 10001 | 10 min | «gravado (0600 10001:10001)» |
| 6 | `bash 60-banco.sh --aplicar` | **s5**: PostgreSQL 18, papéis, bancos, `pg_hba`, TLS, `DATABASE_URL` · **s4**: copia certificados do kit s4 e grava `DATABASE_URL` | s5: 5–8 min · s4: 1 min | «8 papéis como na S4», «2 bancos» · (s4) a prova é o `provar.sh` do kit s4 |
| 7 | `bash migrar.sh --alvo s5 --repo <checkout na tag> --aplicar --ate 0004`, depois `--sim-0005` com o «sim» nomeado. Na S4: da S3, `S4_SSH=… bash migrar.sh --alvo s4 …` | migrações 0001–0005 por ledger | 2 min | «0001… aplicada» até a 0005; rodar de novo: «nada a aplicar» |
| 8 | `bash 70-alerta.sh --aplicar --testar` | `ia-alerta` e `ia-s5-alerta@.service` | 1 min | «s5 teste_alerta origem=kit» chega no celular |
| 9 | `bash 80-backup.sh --aplicar` (só `BANCO_LOCAL=s5`) | timers de backup e envio, chave ssh do backup | 2 min | imprime a linha `restrict,command="s3-rrsync-backup …"` (o invólucro deste kit, instalado na S3) que o dono cola na S3; na S3 o dono instala `s3-arquivar-backup.sh` (root, timer de 15 min) |
| 10 | `bash verificar.sh` | nada | 1 min | `0 FALHOU`. Cada FALHOU diz o passo a refazer |
| 11 | Coolify da S2 + `scripts/deploy-s5.sh vX.Y.Z --executar --primeiro` (`docs/DEPLOY.md`) | aplicação no ar | 15 min + janela | `/healthz` com a versão e o `git_sha` da tag; `verificar.sh --etapa app` |

**Total**: ~45–60 min de relógio na S5 e ~40 min de mão do dono (sem contar a espera pelas respostas dele).

## Desfazer

Cada script diz o seu «Desfazer» no cabeçalho. Ordem inversa: parar a aplicação no Coolify → `systemctl disable --now` dos timers de
backup → (S5) `dropdb` só com autorização nova → `nft delete table inet ia_s5` e `systemctl disable ia-s5-nft.service` →
`systemctl disable --now wg-quick@wg0` e, na S2/S4, `wg set wg0 peer <pública da S5> remove` + o `.bak-ia-*`.

## Arquivos

| Arquivo | Papel |
|---|---|
| `00-pre-requisitos.md` | o que o dono informa e faz |
| `s5.env.exemplo` | configuração (sem segredo) |
| `lib.sh` | modo simular/aplicar, parser do `s5.env`, escrita atômica, segredo sem eco |
| `10-endurecer.sh` … `80-backup.sh` | os passos, na ordem |
| `migrar.sh` | migrações por ledger, S5 ou S4 (G-0012) |
| `verificar.sh` | conferência só leitura |
| `s3-rrsync-backup.sh` | roda NA S3: `command=` da chave de backup; só grava arquivo novo (sem ler, apagar nem sobrescrever) |
| `s3-arquivar-backup.sh` | roda NA S3 (root): tira os backups recebidos do alcance da chave do rrsync e os torna imutáveis |
| `ensaio-local.sh`, `ENSAIO.md` | ensaio em contêineres descartáveis (F4-035) e o resultado |
| `EMENDAS.md` | onde o roteiro e os contratos citam a VPS |
