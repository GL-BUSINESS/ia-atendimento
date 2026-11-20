# Revisão de segurança da esteira e do kit da S5 (20/11/2026)

Revisor independente (agente de segurança, só leitura, contexto limpo) sobre `git diff origin/main...feat/esteira-s5` no commit
`753ebdd`. Também entraram dois achados MÉDIOS da revisão automática do coordenador. Não houve CRÍTICO. Resultado: **1 ALTO, 6 MÉDIOS
e os BAIXOS**. O ALTO e os MÉDIOS foram corrigidos ou justificados no commit seguinte, `fix: revisão de segurança do kit da S5`.

## ALTO

| Id | Achado | Destino |
|---|---|---|
| A1 (= coordenador 1) | A chave `rrsync -wo` aceitava `--delete` e sobrescrita, então uma S5 comprometida apagava os backups da S3. | **Corrigido.** A primeira correção (`rrsync -wo -no-del -no-overwrite`) caiu no ensaio: o rsync 3.2.7 do Ubuntu 24.04 não tem `-no-overwrite`. A linha virou `from="<IP da S5>",restrict,command="/usr/local/bin/s3-rrsync-backup …"`; o invólucro (`kits/s5/s3-rrsync-backup.sh`) aceita **só** o comando de servidor exato do envio (`rsync --server -te.<capacidades> --partial-dir .parcial --ignore-existing . .`, lista fechada por expressão inteira e uma só linha), chama `rrsync -wo -no-del -munge` e acrescenta `-no-overwrite` quando a versão tiver. A versão anterior procurava `--ignore-existing` em qualquer ponto e foi burlável (MÉDIO do coordenador: depois do «.», com `--no-ignore-existing`/`--existing`, com `-l`). O ensaio roda 8 variantes de burla (opção depois do «.», `--no-ignore-existing`, `--existing`, `-l`, `-L`, `--delete`, `--sender`, `; id`) e todas são recusadas antes do rrsync. Entrou o `kits/s5/s3-arquivar-backup.sh`: na S3, como root, ele move o que chegou e conferiu o sha256 para um arquivo morto `root 0700`/`0400` com `chattr +i`, fora do alcance da chave. O ensaio prova que `rsync --delete` não apaga, que a sobrescrita não muda o arquivo, que o arquivo morto fica fora do alcance da chave e que a entrada fica vazia. Reenvio após falha: com `--ignore-existing` o rsync sai 0 e conta como sucesso. |

## MÉDIO

| Id | Achado | Destino |
|---|---|---|
| Coordenador 2 | Porta publicada pelo Docker passa por DNAT/FORWARD, fora da chain `input`. | **Corrigido.** A tabela `inet ia_s5` ganhou a chain `forward` (`ct state new ct status dnat iifname != "lo" drop`). O `verificar.sh` confere a regra e lista contêiner que publique porta em `0.0.0.0`/`[::]`. O compose da IA usa rede host e não publica porta, e um teste da esteira prova isso. O ensaio prova: com DNAT simulado (netns + `dnat`), a porta é alcançável antes do firewall e fechada depois; a saída do «contêiner» continua. |
| M1 | O arquivo do boot (`ia-s5.nft`) era regravado antes das guardas, e um reboot carregava regras não confirmadas. | **Corrigido.** As regras vão para `ia-s5.nft.novo`, passam por `nft -c` e pelas guardas e são aplicadas com a janela. Só o `--confirmar` move o arquivo para o definitivo. |
| M2 | O `migrar.sh` rodava SQL como superusuário de um checkout não conferido. O `0001.sha256` só cobre a 0001. | **Corrigido.** O checkout precisa estar limpo (`git status`), com HEAD exatamente numa tag anotada `vX.Y.Z`. `--permitir-sem-tag` existe só para o ensaio em banco descartável e avisa em voz alta. Manifesto sha256 de todas as migrações e aplicação como `ia_owner`: ficam abertos, porque mudam `migrations/` e o processo da 0001 (fora deste PR). |
| M3 | A chave AES mensal não entra em backup. | **Mantido de propósito.** P-R10 (decisão do dono): o texto vive 14 dias e perder a chave torna o texto ilegível, que é a intenção. Corrigido o lado técnico: a escrita do `chaves-aes.json` faz `fsync` do arquivo e do diretório. |
| M4 | O filtro de PII do `ia-alerta` deixava passar CPF formatado, telefone com hífen e nome. | **Corrigido.** A lista é fechada: `unidade`, `banco` e `origem` aceitam só rótulo técnico (`[a-z][a-z0-9_-]`); `horas`, `arquivos` e `livre_pct` aceitam só número de até 5 dígitos. O resto vira `par_recusado=1`. O ensaio manda CPF formatado, telefone, nome, e-mail e número longo, e nada disso chega ao ntfy. |

## BAIXO

| Achado | Destino |
|---|---|
| `--confirmar` aceitava sessão aberta ANTES da aplicação | **Corrigido**: compara o início do processo da sessão (desde o boot) com o instante da aplicação. |
| `PG_PORTA` sem validação no firewall | **Corrigido.** |
| DHCP sem regra (renovação cairia). A primeira correção (`udp sport 67 dport 68` aberto) ficou larga demais (MÉDIO, coordenador) | **Corrigido**: só com `FIREWALL_DHCP=sim`, só em `iifname FIREWALL_UPLINK`, só para `ip daddr` = IPv4 do uplink ou 255.255.255.255 e, com `FIREWALL_DHCP_SERVIDOR`, só desse `ip saddr`. `sim` sem uplink é recusado. Ensaio e `verificar.sh` conferem as duas posições. |
| Temporário de segredo em `/tmp` sem limpeza | **Corrigido**: o temporário fica no diretório de destino e há um `trap` que o apaga em qualquer saída. |
| `\r` de arquivo CRLF no `ia-entrada` | **Corrigido**, com teste. |
| `COOLIFY_URL` http, `COOLIFY_APP_UUID` e `S5_SSH` iniciando com `-` | **Corrigido** no `deploy-s5.sh`, com testes. |
| Parser do `s5.env` sem conferir o dono e aceitando `'"\(){}*` | Aberto. O arquivo é root 0600 e quem o controla já é root. A validação por tipo foi feita nos campos que viram regra ou comando (IP, porta, registro, destino, caminho). |
| `install -d` mudando o modo de `IA_SEGREDOS_DIR` existente | Aberto. O caminho vem do `s5.env` do root; o README manda `/etc/ia-s5`. |
| `wg0.conf` movido antes do `wg-quick strip`; `.bak-ia-*` com a privada antiga | Aberto (BAIXO). Os arquivos são 0600 root. |
| `registro.senha` fica depois do login | Aberto. O script avisa que pode ser apagada. Credential helper: depois. |
| Chave GPG dos repositórios sem conferir a impressão digital | Aberto (padrão dos guias oficiais). |
| Opção S4 copia `ia_obs_a.*` para o diretório do orquestrador | Aberto. O Phoenix (A4.5) precisa dela; separar na A4.5. |
| Certificados de 397 dias sem alerta de renovação | Aberto. Calendário de certificados é A4.8. |
| Rollback confere só a versão se a tag anterior não está no git local | Aberto. O script avisa. Falhar fechado tornaria o rollback impossível sem `git fetch`. |
| `DEPLOY_TESTE=1` contorna janela e sha | Mitigado. Sem `DEPLOY_TESTE=1`, `DEPLOY_AGORA`/`SHA_ESPERADO` são recusados. |
| `curl -K -` com `user=` do workflow quebra se o secret tiver `"` | Aberto (código herdado do pipeline central). |
| Digest conferido não é usado no deploy (puxa por tag) | Aberto. O ruleset de tags `v*` é a barreira (DEPLOY §5). |
| Contêiner de ensaio com `SYS_ADMIN`/`NET_ADMIN`/sem seccomp | Aceito. É local, descartável, só para o ensaio. |
