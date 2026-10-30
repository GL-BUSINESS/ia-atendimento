# ia-atendimento

Orquestrador da **IA de atendimento da GL Capital** (MVP em 29/11/2026). Este repositório está na fase **A6 do roteiro: só a
fundação**, sem agente, sem ferramentas, sem API de negócio, sem n8n e sem nada em produção. O que existe e está provado:

| Peça | Onde | Prova |
|---|---|---|
| Esquema `ia_atendimento` (migração 0001 = bloco `sql` do estudo I, byte a byte) | `migrations/0001_esquema.up.sql`, `0001.sha256` | 350 casos portados do `i-teste-0001.sh` + checksum |
| Fila Procrastinate 3.10.0 (migração 0002) | `migrations/0002_procrastinate.up.sql` | aplica limpa; `gerar_0002.py --verificar` |
| Aplicador idempotente com ledger `ia.migracao` | `src/ia_atendimento/migracoes.py` | `tests/test_migracoes.py` |
| `Settings` por env (`SecretStr`, sem segredo no `repr`) | `src/ia_atendimento/config.py` | `tests/test_config.py` |
| AES-256-GCM com AAD, chaves em arquivo 0600 | `src/ia_atendimento/cifra.py` | `tests/test_cifra.py` |
| Máscara determinística de PII | `src/ia_atendimento/mascara.py` | `tests/test_mascara.py` |

## Como rodar

Requisitos: `uv`, Python 3.13 (o `uv` instala), `docker` com a imagem `postgres:18` (os testes sobem um Postgres descartável em
`127.0.0.1`, porta livre, e o derrubam ao fim).

```bash
uv sync                      # dependências pinadas (uv.lock)
bash scripts/check.sh        # portão local: ruff, varredura, checksum da 0001, 0002 em dia, pytest com tempo medido
uv run pytest -q             # só os testes
bash scripts/aplicar_migracoes_local.sh [--manter]   # aplica 0001+0002 num Postgres descartável e mostra o ledger
```

Sem docker (CI): `IA_TESTE_PG_HOST=localhost IA_TESTE_PG_PORT=5432 uv run pytest` usa um serviço Postgres local já de pé.
A fixture **recusa** host que não seja local e cluster que já tenha papéis `ia_*`: os testes nunca tocam a S4.

Os 350 casos de `tests/test_esquema.py` formam uma **sequência com estado compartilhado** (como o script do estudo I): rode o
módulo inteiro, não um caso solto com `-k`.

## Variáveis de ambiente

Só nomes em `.env.example` (copie para `.env`, que o git ignora). `Settings` valida no boot: modelo `deepseek-*`/`gemini-*`,
URL do modelo em https (http só em localhost) e **nunca** `deepseek.com` nem `anthropic.com`.

| Variável | Para quê |
|---|---|
| `DATABASE_URL` | banco `ia_atendimento`, login `ia_app_a`/`_b` (sem DDL, sem DELETE) |
| `MODELO_NOME`, `MODELO_BASE_URL_1`, `MODELO_API_KEY_1` | DeepSeek V4.1 Flash 1017 no Fireworks só-EUA (estudo G §3) |
| `API_TOKEN` | token da API de entrada |
| `PHOENIX_ENDPOINT` | traces (banco `ia_obs`); vazio = não exporta |
| `CHAVE_AES_ID`, `CHAVE_AES_ARQUIVO` | chave vigente (mensal) e arquivo 0600 `{"<id>": "<base64 de 32 bytes>"}` |

## Contrato de dados

O esquema é do **estudo I** e não se edita aqui: `estudos/semana-1/i-esquema-reconciliado.md` (bloco `sql` do §4; rodadas até
a 3c, §12) e a visão geral em `MONITORAMENTO-DESIGN.md` §5 («Base comum de dados»), ambos em `docs/planejamento-ia/` do
repositório de documentação da empresa (fora deste repo). Mudou o desenho = **nova migração 0003+**, nunca edição da 0001
depois de aplicada. O teste `test_0001_igual_ao_bloco_do_estudo_i` compara o arquivo com o bloco do estudo (quando o estudo
está na máquina) e `test_checksum_0001` com `migrations/0001.sha256`.

Para aplicar na S4 (feito pelo dono, nunca por este código): `migrations/README.md` e `docs/OPERACAO.md`.

## Regras invioláveis (resumo do roteiro §0.3)

1. **Nada da Anthropic no produto.** Claude/Codex são só ferramentas de desenvolvimento. **Nunca a API oficial da DeepSeek**;
   só `us.api.fireworks.ai` (roteador `-us`).
2. **CPF nunca** ao modelo, prompt, log, span, banco da IA, ntfy, Kan ou payload de entrada. Não há coluna de CPF nem de telefone.
3. **Texto do cliente só mascarado e cifrado** (AES-256-GCM, `conversa_cifrada`), 14 dias após o encerramento (teto 30 d).
   Nunca em `passo`, log, ntfy, Kan ou git.
4. **Tudo nasce desligado e em dublê:** `ia_ativa=false`, `modo="duble"`, MVP só FACTA.
5. **Escrita em produção só com o «sim» do dono**, pelos kits; este repo não aplica nada na S4/VPS.
6. **T7 em dúvida nunca se repete** (a trava é do banco: índices únicos parciais do ledger).
7. **Esperar a condição, não o sinal** em testes; **dado de teste sintético**, nunca de produção.
8. **Versionar sempre:** tag semver + release no GitHub (a tag `v0.1.0` só depois da revisão).

## Limitações conhecidas

- **Máscara de PII** (`mascara.py`): não mascara dígitos por extenso («cinco dois nove...») nem dígitos misturados com letras;
  excesso de máscara é aceito (corrente de 8+ dígitos vira `[NUMERO]`, data e valor `R$ 1.234,56` bem formados são isentos).
- **Procrastinate** usa nomes sem schema em funções e gatilhos: a conexão da fila precisa de `search_path = procrastinate, public`
  (ver `migrations/README.md`). Isso é decisão da infra/B1.3, não da migração.
- **AAD da cifra:** uma só forma, `atendimento_id|seq|remetente|tipo|chave_id` (cofre: `atendimento_id|0|cofre|finalidade|chave_id`),
  com contexto obrigatório e domínio fechado. Quem decifra passa o mesmo contexto de quem cifrou.
- **Máscara de PII:** `[NOME]` só para nomes que o chamador informa (a máscara não adivinha «me chamo X»); e-mail escrito por extenso
  («fulano arroba gmail ponto com», «fulano (at) gmail.com») e CPF com `%`-codificação em URL não são mascarados.
- **Destino do modelo:** `Settings` aceita só `https://us.api.fireworks.ai` ou loopback. Trocar de provedor (reserva Together só-EUA,
  Gemini) é mudança de código revisada, não de variável de ambiente.

## Estrutura

```
migrations/      0001 (estudo I), 0002 (Procrastinate), 0001.sha256, README.md (ordem de aplicação na S4)
scripts/         check.sh, aplicar_migracoes_local.sh, gerar_0002.py, varredura.py
src/ia_atendimento/  config.py, cifra.py, mascara.py, migracoes.py
tests/           test_*.py; casos/ = os 350 casos do estudo I como dados (nome, papel, SQL, expectativa)
docs/OPERACAO.md operação (aplicação na S4 = texto para o dono, não executar sem o «sim»)
.github/workflows/ci.yml  ruff + pytest com serviço postgres:18, sem segredos
```
