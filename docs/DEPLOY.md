# Deploy do `ia-atendimento` na S5 (A6.6)

> **Atenção.** Esta página descreve a esteira; **nada aqui foi executado em produção**. A S5 (servidor da IA, que substitui a «VPS»
> do planejamento) ainda não existe: o kit que a prepara está em `kits/s5/` (README com a ordem). Subir exige o «sim» do dono (PD-2) e
> a janela do PD-3.

## 1. Visão em uma linha

`scripts/release.sh X.Y.Z` (tag anotada local) → o dono empurra a tag → `.github/workflows/imagem.yml` constrói na **S3** e publica
no registro da S3 → `scripts/deploy-s5.sh vX.Y.Z --executar` troca a tag na S5, **à mão, na janela**, e só diz «OK» se a S5 estiver
rodando aquela tag. Push na `main` **nunca** constrói nem implanta (PD-3).

| Peça | Arquivo | Papel |
|---|---|---|
| Imagem | `Dockerfile`, `.dockerignore`, `docker/ia-entrada.sh` | multi-stage com `uv` (instala do `uv.lock`), leva `migrations/` e `fixtures/` no pacote, usuário `10001`, ponto de entrada que carrega os segredos de arquivo 0600 |
| Compose | `docker-compose.yml` | `orquestrador` (`uvicorn --factory …ambiente:criar_app_de_ambiente`) + `worker` (`python -m ia_atendimento.worker`), mesma imagem, `network_mode: host`, raiz só leitura, `${IA_SEGREDOS_DIR}:ro` |
| Build | `.github/workflows/imagem.yml` | só tag `v*`; runner `s3-builders`; registro = variável `REGISTRO_IMAGEM` |
| CI | `.github/workflows/ci.yml` | continua: lint e testes por SHA em push/PR |
| Release | `scripts/release.sh` | portão + CHANGELOG + pyproject + tag anotada; **imprime** o `git push` |
| Deploy | `scripts/deploy-s5.sh` | hora, dia de piloto (falha fechado), portão da S5, `/healthz` antes; grava e **relê** `IMAGE_TAG`; deploy; `/healthz` com `version` e `git_sha` da tag; rollback |
| Servidor | `kits/s5/` | endurecimento, Docker e registro, WireGuard, firewall, banco (S5 ou S4), migrações, segredos, backup, alerta, `verificar.sh` |

**Nenhum host, IP ou registro fixo** no compose, no workflow ou no deploy: o IP da S5 no WireGuard, a porta, o registro e o diretório de
segredos vêm de variável (§4). Faltou variável obrigatória ⇒ o `docker compose` recusa subir.

## 2. Como sobe (passo a passo)

1. **Mudança na main** (PR revisado). Sem deploy: a main só acumula.
2. **Cortar a versão**, a partir da `main` atualizada: mover o `[Unreleased]` do `CHANGELOG.md` para `## [X.Y.Z] - data`, subir
   `version` no `pyproject.toml` (fonte única), commitar/mesclar e rodar `bash scripts/release.sh X.Y.Z`.
3. **Empurrar a tag** (decisão consciente; dispara a imagem): `git push origin vX.Y.Z`; depois `gh release create vX.Y.Z --verify-tag --notes-from-tag`.
4. **A imagem** (`imagem.yml`): confere que a tag é `vX.Y.Z`, igual ao `pyproject.toml` e **está na main**, constrói com `VERSION`,
   `GIT_SHA`, `BUILT_AT`, `APP_GID`, publica `ia-atendimento:vX.Y.Z` e `:<sha40>` (nunca `latest`) e confere o digest no registro.
5. **Deploy na janela** (12:30–14:00 ou depois das 20:30 BRT; nunca 09–12 h nem em dia de piloto), com o «sim» do dono e o
   `git fetch --tags` feito: `bash scripts/deploy-s5.sh vX.Y.Z` (simulação) e depois `... --executar`. Ele:
   - recusa se `config/dias-piloto.txt` faltar ou não tiver data (G-0096) ou se hoje for dia de piloto;
   - roda **na S5** o portão (`df` ≥ 15 % livre, carga < 6) e o `/healthz` antes;
   - lê a `IMAGE_TAG` atual (rollback), grava a nova com `curl --fail-with-body` e **relê** (G-0095: PATCH recusado ou ignorado sai 8 e
     nada é implantado);
   - dispara o deploy e só aceita `/healthz` 200 com `version` = `X.Y.Z` **e** `git_sha` = commit da tag (deploy «finished» com a tag
     velha rodando não é sucesso); se falhar, volta sozinho e confere a versão anterior.
   Primeiro deploy: `--primeiro` (não há `/healthz` nem tag anterior).
6. **Depois** (PD-3): contêiner novo (`docker ps` na S5), flags, Kan, memória.

**Deploy automático pelo workflow (opcional, desligado).** Com a variável `DEPLOY_AUTOMATICO=true`, o job `implantar` grava a tag e
dispara o deploy atrás do environment `producao-s5` (aprovação do dono). Ele **não** confere hora, dia de piloto, portão nem a versão
no `/healthz` (o runner não alcança o wg0): por isso o padrão é deixar a variável ausente e usar `deploy-s5.sh`.

## 3. Como desfaz

- **Tag errada antes do push:** `git tag -d vX.Y.Z`.
- **Tag já empurrada, deploy ainda não feito:** nada a desfazer em produção; corrija e corte a próxima versão (nunca reescreva tag).
- **Deploy ruim:** o `deploy-s5.sh` volta sozinho (código 6). Manual: `bash scripts/deploy-s5.sh <tag anterior> --executar`. Último
  recurso: no Coolify da S2, editar `IMAGE_TAG` e *Redeploy*.
- **Parar o serviço:** Coolify da S2, *Stop* da aplicação (o banco não muda). A imagem anterior continua na S5 porque leva
  `coolify.managed=true` (memória `coolify-cleanup-imagens`).

## 4. Onde ficam a configuração e os segredos (nunca no repositório)

**Regra única de permissão (G-0097).** O código recusa arquivo de segredo com qualquer bit de grupo ou de outros (`cifra.py`,
`segredos.py`) e o contêiner roda como uid **10001** com `cap_drop: ALL`. Então: diretório `${IA_SEGREDOS_DIR}` = `root:10001 0750`;
**cada arquivo** = `10001:10001 0600` (`install -m 600 -o 10001 -g 10001`). `0640` dá `ChaveInsegura`; `0600 root:root` dá «ilegível».
O kit `kits/s5/50-segredos.sh` cria tudo assim e o `verificar.sh` confere `stat -c '%a %u'`.

| O quê | Onde (S5) | Nome |
|---|---|---|
| **Segredos** (carregados pelo `ia-entrada`) | `${IA_SEGREDOS_DIR}/env/<NOME>`, um por arquivo, 0600 dono 10001 | `DATABASE_URL`, `MODELO_API_KEY_1` (Fireworks, DEC-PIA-008), `API_TOKENS`, `CHAVE_H16`, `CHAVE_FINGERPRINT`, `CHAT_REF_CHAVE`, `PHOENIX_API_KEY` (opcional) |
| Arquivos lidos pelo código | `${IA_SEGREDOS_DIR}/`, 0600 dono 10001 | chaves AES (`CHAVE_AES_ARQUIVO`), HMAC do gateway (`GATEWAY_HMAC_ARQUIVO`), segredos de saída (`SEGREDOS_SAIDA_ARQUIVO`), certificados do banco quando na S4 |
| Configuração (não secreta) | env da aplicação no Coolify (ou `.env` 0600 ao lado do compose) | `IMAGE_TAG`, `IA_REGISTRO_IMAGEM`, `IA_BIND_IP`, `IA_PORTA`, `IA_SEGREDOS_DIR`, `CHAVE_AES_ID`, `CHAVE_AES_ARQUIVO`, `GATEWAY_HMAC_ARQUIVO`, `SEGREDOS_SAIDA_ARQUIVO`, `RESPONSAVEL_IA`, `IA_MEM_ORQUESTRADOR`, `IA_MEM_WORKER` e os opcionais do `.env.example` |
| Registro e Coolify (CI) | **secrets do repositório** | `S3_REGISTRY_USER`, `S3_REGISTRY_PASSWORD`, `COOLIFY_S2_URL`, `COOLIFY_S2_TOKEN`, `ALERT_WEBHOOK_URL` (opcional) |
| Chaves de ligação (CI) | **variáveis do repositório** | `REGISTRO_IMAGEM` (obrigatória), `DEPLOY_AUTOMATICO` (ausente = só publica), `COOLIFY_UUID_IA_ORQUESTRADOR`, `APP_GID` (opcional) |
| Para o `deploy-s5.sh` (sessão do operador) | ambiente do shell, nunca arquivo do repo | `S5_SSH`, `COOLIFY_URL`, `COOLIFY_TOKEN`, `COOLIFY_APP_UUID`, `HEALTHZ_URL` |

Por que os segredos saem do Coolify (muda a OPERACAO §8, que os punha como variável secreta da plataforma): variável do Coolify fica no
banco e nos backups dele e no `docker inspect`; o P-R10 já tirava as chaves AES de lá pelo mesmo motivo, e a DEC-PIA-008 pede a chave
da Fireworks em arquivo 0600. Com isso o compose versionado não cita nenhum nome de segredo (um teste prova).

`DATABASE_URL`: com o banco na S5, `postgresql://ia_app_a:<senha>@127.0.0.1:5432/ia_atendimento` (host local; o contêiner usa a rede do
host); com o banco na S4, `postgresql://` com o login `ia_app_a`, a senha, `<IP da S4 no wg0>:5434/ia_atendimento` e `sslmode=verify-full&sslrootcert=…&sslcert=…&sslkey=…`
com os certificados em `${IA_SEGREDOS_DIR}` (kit s4). O kit grava a URL no arquivo sem nunca imprimi-la.

## 5. Configuração única (dono, antes do primeiro deploy)

1. **GitHub** (`GL-BUSINESS/ia-atendimento`): proteger as tags `v*` (ruleset: só Admin/TI criam ou movem tags); criar o environment
   `producao-s5` com revisor obrigatório e restringir a ele os secrets do registro/Coolify; criar os secrets e variáveis da tabela
   acima (os do registro e do Coolify S2 já existem no `gl-gateway` e no `facta-on`).
2. **S5:** rodar o kit `kits/s5/` na ordem do README (inclui o login no registro e os arquivos de segredo).
3. **Coolify da S2:** registrar a S5 como servidor remoto (proxy «None»), nova aplicação `dockercompose` (projeto `ia-atendimento`,
   ambiente *production*), deploy key só-leitura, arquivo `docker-compose.yml`, **auto-deploy e webhook DESLIGADOS** (PD-3), a
   configuração da tabela acima e `IMAGE_TAG` com a primeira tag; anotar o UUID. O Coolify **não constrói**: puxa a imagem do registro.
4. **Phoenix** é outra aplicação (A4.5); sem ele, deixe `PHOENIX_ENDPOINT` vazio (não exporta traces).

## 6. Checklist PD-3 (antes de `--executar`)

- [ ] «Sim» do dono para este deploy (PD-2) e para o horário.
- [ ] Hora: 12:30–14:00 ou depois das 20:30 BRT; **não** 09–12 h; **não** dia de piloto (`config/dias-piloto.txt` em dia e com datas).
- [ ] Nenhuma outra sessão mexendo na S5/Coolify; fila do Coolify vazia.
- [ ] Nenhum kit rodando dentro do contêiner alvo; flag nova **off**.
- [ ] `bash kits/s5/verificar.sh` na S5 sem FALHOU.
- [ ] Tag existe no registro (`imagem.yml` verde), release criado e `git fetch --tags` feito (o script confere o `git_sha`).
- [ ] Depois: `/healthz` (`version`/`git_sha`), contêiner novo, flags, Kan e memória atualizados.

## 7. Pendências conhecidas

- Primeiro `docker build` no builder da S3 e primeiro boot na S5: só depois que a S5 existir (o ensaio local está em `kits/s5/ENSAIO.md`).
- Phoenix (A4.5) e dublê da FACTA (A4.10): aplicações próprias, fora desta imagem.
- O `hadolint` não está instalado na S3; a imagem é validada por `docker build` local e por `tests/test_esteira.py`.
