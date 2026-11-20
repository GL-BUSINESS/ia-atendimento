# S5 — o que o dono informa e o que ele faz à mão

A S5 é o servidor que o dono dedica à IA de atendimento (substitui a «VPS» do planejamento, DEC-PIA-009). O kit (`README.md`) só começa
depois desta lista. Nada aqui é segredo, **exceto** o que está marcado «por arquivo»: isso nunca vai para chat, Kan ou e-mail.

## 1. O que o dono informa (para preencher o `s5.env`)

| # | Item | Por quê | Vai para |
|---|---|---|---|
| 1 | **CPU (núcleos), RAM (GB), disco (GB e tipo: SSD/NVMe/HDD)** | decide `BANCO_LOCAL` (abaixo) e os `mem_limit` do compose | decisão 2 e `IA_MEM_*`, `PG_SHARED_BUFFERS` |
| 2 | **Sistema operacional** | o kit foi escrito e ensaiado para **Ubuntu 24.04 LTS** (serve 26.04); outro SO = avisar antes | — |
| 3 | **IP público** (IPv4; dizer se há IPv6) | endpoint do WireGuard na S2/S4 e regras do firewall | blocos que o dono roda na S2/S4 |
| 4 | **Onde fica** (provedor/datacenter ou local físico; latência até a S2) | WireGuard e janela de manutenção; se for local físico: energia, nobreak e link | — |
| 5 | **Acesso inicial**: usuário e forma (chave SSH já instalada? console do provedor?) | o kit roda por SSH com `sudo`; o console é o caminho de volta se o firewall errar | `ADMIN_USUARIO` |
| 6 | **Chaves SSH públicas** de quem administra (Danilo e o dono) | SSH só por chave | `/etc/ia-s5-adm/admin.pub` |
| 7 | **IPs de emergência para SSH** (opcional; ex.: IP fixo do escritório) | sem eles, o SSH é só pelo tailnet e pelo wg0 da S2 | `SSH_ORIGENS` |

## 2. O que o dono decide

| # | Decisão | Padrão do kit | Observação |
|---|---|---|---|
| D1 | **Onde ficam `ia_atendimento` e `ia_obs`**: `s5` ou `s4` | `s4` (decisão de 29/10) | `s5` só se a S5 comportar PostgreSQL + orquestrador + Phoenix (referência: ≥ 4 vCPU, ≥ 8 GB, ≥ 80 GB SSD) e **contraria 29/10**. Com `s5`: some o kit s4 e o peer S4↔S5, entra o backup cifrado com fila (`80-backup.sh`) |
| D2 | **IP da S5 no WireGuard** | `10.90.0.5` (o da VPS) | com ele os contratos 01–08 não mudam de número (`EMENDAS.md`) |
| D3 | **Chave age do backup** (só D1 = s5) | o dono gera **fora** da S5 e da S3: `age-keygen -o ia-s5-backup.key` e entrega só a linha `age1…` | a privada é a única forma de ler o backup |
| D4 | **Destino do backup na S3** (só D1 = s5) | `ia-backup@<s3 no tailnet>:/mnt/hdd/backups/ia-s5` | o dono cria o usuário, cola a linha `restrict,command="s3-rrsync-backup …"` que o `80-backup.sh` imprime, instala o `s3-rrsync-backup.sh` em `/usr/local/bin` e instala o `s3-arquivar-backup.sh` como root num timer |

## 3. O que o dono faz à mão (checklist)

- [ ] Entregar a S5 com Ubuntu 24.04 (ou 26.04) e o acesso do item 5; dizer os itens 1–7.
- [ ] Responder D1 e D2 (D3 e D4 só se D1 = s5).
- [ ] **Tailscale**: aprovar o nó `s5` no tailnet (o `10-endurecer.sh` instala; o `tailscale up` pede o login do dono ou uma chave de autenticação em `/etc/ia-s5-adm/tailscale.authkey`, 0600). Sem tailnet não há registro de imagens (ele só escuta no tailnet) nem SSH de admin.
- [ ] **Registro da S3**: senha do usuário de **leitura** em `/etc/ia-s5-adm/registro.senha` (root 0600), colada pelo próprio dono: `sudo install -m 600 /dev/stdin /etc/ia-s5-adm/registro.senha` e Ctrl-D.
- [ ] **WireGuard**: rodar na S2 (e na S4, se D1 = s4) o bloco que o `30-wireguard.sh` imprime (peer **aditivo**, nunca `wg syncconf`) e devolver a chave pública e o endpoint da S2 (e da S4).
- [ ] **Fireworks** (DEC-PIA-008): abrir a conta, pôr **teto mensal com aviso em 80 %** no painel do provedor e colar a chave na S5 com `sudo bash 50-segredos.sh instalar MODELO_API_KEY_1 --aplicar` (sem eco; nunca no chat).
- [ ] **gl-gateway**: colar a chave HMAC (a mesma do `GATEWAY_ASSINATURAS`) com `50-segredos.sh instalar gateway-hmac.keys --aplicar`.
- [ ] **Segredos de saída** (`saida.json`: Bearer `ia-orquestrador`, token `ia` do chatguru-api, client do c360-auth) com `50-segredos.sh instalar saida.json --aplicar`.
- [ ] **ntfy**: assinar no celular o tópico que `sudo bash 50-segredos.sh mostrar-topico` mostra (só no terminal) e conferir o `70-alerta.sh --aplicar --testar`.
- [ ] **Coolify da S2**: registrar a S5 como servidor remoto (pelo wg0, proxy «None») e criar a aplicação `dockercompose` (`docs/DEPLOY.md` §5). Opcional se o dono preferir `docker compose` direto na S5.
- [ ] **«Sim»** (PD-2) para cada `--aplicar` que mexe fora da S5: blocos na S2/S4, migrações (a 0005 tem `DROP CONSTRAINT`: «sim» nomeado), primeiro deploy.

## 4. Riscos conhecidos antes de começar

- **S5 = um ponto único**: sem réplica. Se ela cair, a IA para e o atendimento volta ao humano (repasse); o alerta do ntfy não depende da S5.
- **Banco na S5 (D1 = s5)**: sem PITR (backup lógico diário); perda máxima de ~24 h de estado da IA. O texto de conversa (cifrado, chave mensal fora do backup) não volta de propósito (P-R10).
- **S3 fora** (~16 h em 15–16/11): o backup espera na fila local e alerta em 26 h; a S5 precisa de disco para alguns dias de fila.
- **Banco da S2 em 83 % das conexões** (DEC-PIA-009): a IA não abre conexão no banco da S2; os fluxos do contrato 04 gravam no `n8n-db` (fora deste kit).
