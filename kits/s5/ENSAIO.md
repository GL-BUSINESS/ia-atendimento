# Ensaio do kit da S5 (F4-035) — 20/11/2026

`bash kits/s5/ensaio-local.sh`, rodado na S3 por `~/retomada-2809/pesado.sh`, um de cada vez. Dois contêineres descartáveis
Ubuntu 24.04 com systemd: «S5» e «S3» (destino do backup). Rede própria (`ia-s5-ensaio-rede`), apagada no fim. Nenhum servidor real foi
tocado: sem ssh para S2/S3/S4, sem ntfy.sh (um ntfy falso em `127.0.0.1:8099`), sem registro. O PostgreSQL 18 vem do PGDG e o Tailscale
do repositório oficial, baixados dentro do contêiner.

## Resultado final

**Rodada 7 (final): 121 PASSOU, 0 FALHOU, 4 PULOU** (`rc=0`), depois das correções da revisão de segurança. Foram 7 rodadas:
as 6 primeiras acharam os defeitos da tabela «Achados do ensaio». Depois da rodada 7 só mudaram dois valores de teste (o CPF sintético
passou para a faixa sintética `000.000.0nn` e a chave falsa ficou de baixa entropia, por causa do gitleaks); a lógica é a mesma.

PULOU: NTP, `tailscale up`, `20-docker --aplicar` e o `verificar.sh` com FALHOU esperados no contêiner (abaixo).

## Imagem da esteira (G-0094)

`docker build` local da árvore deste PR (descartável, apagada em seguida): o pacote leva as 5 migrações (0001–0005) e as 3 fixtures do
dublê; `ia_atendimento.api.ambiente:criar_app_de_ambiente` e `ia_atendimento.worker.main` existem; o processo roda como `uid=10001`;
o `ia-entrada` sai 78 sem o diretório de segredos.

## O que o ensaio cobre

| Etapa | Prova |
|---|---|
| Todas, `--simular` | os 8 scripts em `s5` e `s4`; nenhum arquivo criado ou alterado em `/etc`, `/usr/local` e `/var/backups`. O parser recusa `$(…)` e `s5.env` gravável por outros |
| 10 | Senha desligada. Uma conexão SSH nova por chave entra e por senha é recusada. `sudo -n` funciona. Unattended-upgrades fica habilitado. A 2ª passada é idempotente |
| 30 | Chave 0600; o `wg0.conf` 0600 passa no `wg-quick strip` e tem só /32; a privada não aparece na saída. O `wg0` subiu |
| 40 | Recusa sem SSH (console sem `--sem-ssh-atual`) e com a sessão fora das regras, mesmo sob `sudo`. Aplica com janela. O `--confirmar` é recusado na mesma conexão e aceito de uma conexão nova. A porta 8000 e a 5432, com ouvinte, ficam fechadas para fora. Uma porta publicada por DNAT (o caminho do Docker) é alcançável antes e fechada depois, e a saída do «contêiner» continua. Sem confirmação a tabela some sozinha em 60 s; o `ia-s5-nft.service` a recria. DHCP: sem regra com `nao`; com `sim`, a regra vale só no uplink, do servidor informado, para o IP da S5 ou broadcast; `sim` sem uplink é recusado |
| 50 | A chave da Fireworks entra por stdin e fica 0600 do uid 10001. `saida.json` inválido é recusado. `mostrar-topico` recusa pipe e `entregar-tokens` recusa terminal. Idempotente: a chave AES não é trocada |
| 60 | PostgreSQL 18 com 8 papéis `ia_*` sem privilégio. Escuta em 127.0.0.1 e no IP do wg0, nunca em 0.0.0.0. A `DATABASE_URL` conecta como `ia_app_a`. `ia_app_a` não entra no `ia_obs`; sem TLS pelo wg0 é recusado. Nenhuma senha na saída. Idempotente |
| migrar | Recusa checkout sem tag. 0001–0004 por ledger; a 0005 só com `--sim-0005`. O checksum do ledger bate com os arquivos. A 2ª passada não faz nada. Uma migração adulterada PARA. `ia_app_a` sem DDL; o seed tem `ia_ativa=false` |
| 70 | O alerta chega ao tópico. CPF formatado, telefone, nome, e-mail e número longo viram `par_recusado`. Código fora do formato vira `alerta_invalido`. O tópico não aparece no journal nem na saída |
| 80 | Dump cifrado com age na fila, sem nada em claro. Envio à «S3», que decifra com a chave do dono (PGDMP). A chave do backup não lê nem lista. As 8 variantes de burla do `s3-rrsync-backup` são recusadas. `--delete` não apaga e a sobrescrita não muda o arquivo. O `s3-arquivar-backup` move para o arquivo morto (root 0400), fora do alcance da chave. Com a S3 parada o dump fica na fila e, com 30 h, alerta `backup_fila_atrasada`; com a S3 de volta a fila esvazia |
| verificar | Roda e não escreve nada |
| segredos | O valor da chave da Fireworks, de `CHAVE_H16`, de `CHAT_REF_CHAVE` e da senha do `ia_obs_a` não aparece no log |

## Limites do contêiner (PULOU, nunca PASSOU)

- `20-docker --aplicar`: sem Docker dentro do contêiner (só `--simular`). O `docker login` e o `daemon.json` ficam para a S5 real.
- NTP: o relógio é do hospedeiro. O `10-endurecer` pula o `set-ntp` em contêiner e avisa.
- `tailscale up`: exige o login do dono. A instalação foi ensaiada.
- WireGuard: o `wg0` sobe, mas não há peer real. O `verificar.sh` acusa «sem handshake», como deve.
- O `verificar.sh` termina com FALHOU nesses itens (Docker, tailscale, handshake, ping na S2): é o comportamento certo.

## Achados do ensaio (corrigidos antes desta versão)

| Rodada | Achado | Correção |
|---|---|---|
| 1 | Com o `umask 077` do kit, a chave do repositório do Tailscale saía 0600 e o apt dizia «not signed». O passo 10 parava e o resto caía em cascata | `rodar_022` para apt, chaves e PGDG |
| 1 (preparo) | O `sudo` apaga `SSH_CONNECTION`: o firewall acharia que roda pelo console e a prova do caminho de volta viraria `--sem-ssh-atual` | `ssh_connection_da_sessao` sobe pelos processos ancestrais |
| 3 | O `--confirmar` parava ao ler o arquivo da sessão (sem `\n` final, `read` sai 1) | `|| true` |
| 3 | A conferência de papéis comparava em collation pt_BR (`_` ignorado) | `collate "C"` |
| 4 | O rsync 3.2.7 do Ubuntu 24.04 não tem `rrsync -no-overwrite`: o envio à S3 falhava | invólucro `s3-rrsync-backup` com lista fechada (e `-no-overwrite` quando houver) |
| 2, 4, 5 | Do próprio ensaio: editar o script durante a rodada, `&&` no começo de linha, `age -d` esperando stdin, known_hosts antes do sshd | o ensaio roda de uma cópia, com stdin fechado e espera pela chave |

## Efeito no hospedeiro (S3)

Criar o `wg0` dentro do contêiner fez o kernel da S3 carregar o módulo `wireguard` (antes não estava carregado). É inofensivo: não há
interface WireGuard no namespace do hospedeiro. Fica registrado porque o pedido era não tocar em servidor real. Nada mais mudou fora dos
contêineres. A imagem `ia-s5-ensaio:local` fica para repetir o ensaio; para apagar, `docker rmi ia-s5-ensaio:local`.
