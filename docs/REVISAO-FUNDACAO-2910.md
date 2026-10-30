# Revisão de contexto limpo da fundação · 29/10/2026

Revisor: Claude (contexto limpo, adversarial; não construiu). Alvo: `main` em `a7c6a50` (10 commits). Escopo: fundação (config, 0001/0002,
aplicador, cifra, máscara, varredura, testes, CI). Nada tocou S4, VPS ou produção; só `postgres:18` descartável local.
Fontes: roteiro §0 e A6.1–A6.6; estudo I §11–§12 (sha256 `5d1ceec1…3808`); memórias de decisão, rodízio, ecc/security.

## 1. Veredito

**PRONTO PARA TAG v0.1.0**, depois das correções abaixo (7 commits `fix:`), com uma condição de rodízio: os commits de correção foram
escritos por mim; como «quem implementa não revisa», vale um segundo olhar rápido (Codex ou outro Claude) nos 7 diffs antes da tag.
Nenhum CRÍTICO. 4 ALTOS, todos corrigidos. Restam só itens BAIXOS, documentados (seção 7).

| Severidade | Achados | Corrigidos | Abertos |
|---|---|---|---|
| CRÍTICO | 0 | – | – |
| ALTO | 4 | 4 | 0 |
| MÉDIO | 11 | 11 | 0 |
| BAIXO | 12 | 9 | 3 (documentados) |

Suíte: **569 → 687 testes**, 12 s, `bash scripts/check.sh` verde do zero (ruff, format, varredura, sha256 da 0001, 0002 em dia,
`uv lock --check`, pytest). 118 testes novos; os dos achados reprovam no código anterior (contagens por commit na seção 6).

## 2. Passo 1 · reprodução do zero

| Conferência | Resultado |
|---|---|
| `bash scripts/check.sh` e `pytest -q` | 569 passaram em 10,6 s (estado recebido) |
| `0001_esquema.up.sql` × bloco `sql` do estudo I (`awk` das cercas) | `cmp` idêntico; sha256 `5d1ceec13802…3808` = `0001.sha256` = §12.4 |
| `0002` × `SchemaManager.get_schema()` (procrastinate 3.10.0) | corpo entre marcadores idêntico; também idêntico ao `sql/schema.sql` do pacote |
| `i-teste-0001.sh` original contra a 0001 do repo | `350 passaram, 0 falharam` (rodei o script de verdade) |
| `uv lock --check`, pins `==` | coerente; 76 pacotes; nenhum `anthropic`/`claude` no lock |
| CI: SHAs das actions × tags upstream (`gh api`) | `checkout@3d3c42e…` = v7.0.1 e `setup-uv@68559e9…` = v10.3.3 |

## 3. Passo 2 · segurança (achados e destino)

### config.py (`4a79bc6`)
| Sev | Onde | Problema | Destino |
|---|---|---|---|
| ALTO | `config.py:81` `_url_do_modelo` | lista **negativa**: `api.deepseek.com.` (ponto final), `api.deepseek。com` (o httpx normaliza para `.`), `api.fireworks.ai` (global, «global» ≠ EUA), `openrouter.ai` e qualquer outro host passavam; `u:p@host` ia para o `repr` (campo não é SecretStr) | Lista **positiva**: só `https://us.api.fireworks.ai` ou loopback; sem credencial/query/porta. 16 casos recusados + 5 aceitos |
| ALTO | `config.py:55` `_banco_como_ia_app` | `postgresql://ia%5Fowner@…` (o libpq decodifica) e `?user=ia_owner` (vence a userinfo) burlavam a recusa do dono; aceitava `admin`, `ia_leitura_a`, `ia_app` (grupo NOLOGIN); a mensagem do libpq cita a URL com a senha | Login efetivo lido pelo `conninfo_to_dict` (mesmo parser da conexão) e exigido `ia_app_[a-z0-9]+`; erro capturado sem eco |
| MÉDIO | `config.py:74` | `anthropic/deepseek-x`, `claude/deepseek-v4`, `accounts/anthropic/…`, `deepseek-claude-3` passavam (regex aceitava qualquer prefixo) | Prefixo só `accounts/<conta>/(models\|routers)/`; `anthropic\|claude\|opus\|sonnet\|haiku` em qualquer ponto recusa |
| MÉDIO | `config.py:46-47` | `API_TOKEN=`/`MODELO_API_KEY_1=` vazios (o `.env.example` os traz vazios) subiam: API de entrada aberta | `min_length=16` |
| MÉDIO | `config.py:120` | `ValidationError.errors()`/`.json()` guardam o **valor de entrada** (a URL do banco com a senha) mesmo com `hide_input_in_errors`; só o `str()` esconde | `get_settings()` levanta `ConfiguracaoInvalida` só com campo + motivo, `from None` |
| BAIXO | `config.py:105` | `PHOENIX_ENDPOINT` com credencial sairia no `repr`; vazio do `.env.example` ficava `""` | recusa credencial/esquema estranho; vazio → `None` |

Tentativas que já eram barradas: `DEEPSEEK.COM`, `api.deepseek.com.evil` (barrado só por acaso, pela lista), userinfo apontando para DeepSeek,
IPv6 `[::1]`, `http://localhost.evil`, `deepseek-x/anthropic` (o regex exige `deepseek|gemini-` no fim).

### cifra.py (`7c78615`)
| Sev | Onde | Problema | Destino |
|---|---|---|---|
| ALTO | `cifra.py:74-91` | **Duas formas de AAD.** `cifrar(texto, atd)` sem contexto (o caminho mais curto) usava só `atendimento_id`: a linha podia ser movida entre seq/remetente/tipo. Divergia de I §1.6, do plano 01 e do `i-teste-0001.sh` (`{atd}\|1\|cliente\|mensagem\|1`) | **Decisão: vale a completa** `atendimento_id\|seq\|remetente\|tipo\|chave_id`; cofre `atendimento_id\|0\|cofre\|finalidade\|chave_id`. Forma simples removida; contexto é keyword obrigatório (`TypeError`) |
| MÉDIO | idem | `remetente="a\|b",tipo="c"` e `"a","b\|c"` davam a **mesma AAD** (separador sem escape) | domínio fechado = o CHECK do esquema (`cliente\|ia`, `mensagem\|resumo`; cofre `canal\|digitacao`) |
| BAIXO | `cifra.py:104-141` | rótulo `"١"` valia 1 (`isdigit`), `"²"` estourava `ValueError` cru, `"01"` colidia com `"1"`, JSON com `chave_id` repetido ficava com a última, mesma chave em dois meses (o descarte não descartaria nada), chave toda zero | `ChaveInsegura` em todos |
| BAIXO | `cifra.py:58` | `repr(Cifrado)` imprimia nonce e ciphertext (contradizia o docstring) | repr só com tamanhos |
| BAIXO | `cifra.py` `_cifrar` | surrogate solto: a exceção do codec citava o caractere | `ValueError("texto não é UTF-8 válido")` |

Confirmado correto: nonce de 96 bits aleatório **por mensagem** (`os.urandom`; volume mensal ≪ 2^32 por chave), arquivo 0600 verificado por `fstat`
no mesmo fd (sem TOCTOU), `O_NOFOLLOW`, rotação por `chave_id` (cifra com a vigente, decifra pela gravada), exceções sem texto/chave.

### mascara.py (`6ce0c4f`, `f0de31d`)
Sonda de ~85 entradas. **Mascarou:** CPF com pontos/espaços/hífens/barras/underscore/quebra de linha/zero-width/NBSP/soft-hyphen, dígitos
largura-total e árabe-índico, CPF em URL e JSON, `+55`, `(11)`, link `wa.me`, e-mail com caixa, CEP, UUID, nome informado.
**Não vazou nada que importe de falso-positivo:** `R$ 12.345,67`, `R$ 1.234.567,89`, data `12/05/1980`, `84x`, `96 meses`, proposta de 7 dígitos.
| Sev | Problema | Destino |
|---|---|---|
| MÉDIO | e-mail com letra Unicode: `joão@…` virava `joã[EMAIL]` (começo do nome vazava); domínio com acento passava inteiro; `＠` e `．` de largura total | `\w` + acentos combinantes; vista troca `＠ ． 。` |
| MÉDIO | **quadrática**: o regex de e-mail varria a corrida inteira a cada posição: 100 mil letras = 8,8 s, `1-1-1…` = 9,5 s (DoS por uma mensagem grande) | linear (0,03 s) |
| MÉDIO | **regressão minha, apontada pela revisão automática:** o primeiro conserto (lookbehind) deixava o 2º e-mail colado em claro (`a@b.test+joao@exemplo.test`). A classe `\w`+combinantes está correta no arquivo (o `\ẁ-ͯ` visto foi artefato de exibição) | sem lookbehind: corridas maximais + domínio no `@`; início nunca recua antes do fim do e-mail anterior |
| BAIXO | CPF em sobrescritos/circulados/subscritos (`⁵²⁹…`, `⑤②…`) | vista usa `isdigit`+`unicodedata.digit` (verificado nos 0x110000 pontos: nenhum `isdigit` sem `digit`; comprimento preservado) |

**Abertos (BAIXO, aceitos e já descritos no README):** CPF %-codificado em URL (`529%2E982…`); e-mail por extenso/«(at)»/«arroba»; `[NOME]` só
para nomes que o chamador informa («me chamo X» sem lista não é detectado: é desenho, o orquestrador não conhece o nome do cliente);
data ISO `2026-10-29` vira `[NUMERO]` (excesso aceito).

### migracoes.py (`2998d3d`, docs `16e293f`)
| Sev | Onde | Problema | Destino |
|---|---|---|---|
| MÉDIO | `migracoes.py:44-60` | checksum = sha256 dos bytes lidos em uma chamada; SQL executado = `read_text` em **outra** (CR LF virava LF; o arquivo podia mudar entre as duas): ledger podia registrar sha256 que não é do que rodou | bytes lidos uma vez; checksum e SQL saem deles |
| BAIXO | `migracoes.py:146` | `PGSERVICE` no ambiente com `host=` no DSN passava (o serviço pode trazer `hostaddr`, que vence o `host`) | recusa PGSERVICE sempre |
| MÉDIO | `docs/OPERACAO.md §3`, `migrations/README.md` | ledger gravado **depois do COMMIT**, em outro `psql`: janela «aplicada sem ledger» que `aplicar()` não tem | `{ cat arquivo; printf ledger; } \| psql -1`; teste executa o epílogo extraído do doc e prova que falha do ledger desfaz o arquivo |

**Ponto 4 (ledger na mesma transação + advisory lock): CORRETO em `aplicar()`.** Lock `xact` antes de ler o ledger; READ COMMITTED vê o commit do
vizinho; 4 aplicadores simultâneos aplicam cada migração 1 vez (teste novo; **reprova 3/3 sem o lock**). `conferir` funciona como `ia_app_a`
(ledger só leitura para o runtime). CLI local: `localhost`, `127.0.0.1`, `[::1]`, socket e `host=/tmp` passam; `hostaddr`, vírgula com host remoto,
`?host=` remoto, `service=`, PGHOST/PGHOSTADDR remotos são recusados; `dbname=postgresql://…` **não** é expandido pelo libpq do psycopg (testado).
**Aberto (BAIXO):** um túnel SSH para `127.0.0.1:5434` é indistinguível de banco local; o README já diz que a S4 é do dono, via psql.

### varredura.py e CI (`c34abec`)
| Sev | Problema | Destino |
|---|---|---|
| MÉDIO | `git ls-files` não via arquivo novo sem `git add`; o portão roda **antes** do commit | `--cached --others --exclude-standard` |
| MÉDIO | a palavra «exemplo» em qualquer ponto da linha isentava um segredo (`sk-… # exemplo`) | isenção só se o **trecho** casado é de exemplo |
| BAIXO | não pegava credencial em URL nem celular | regras novas (host real; celular com hífen fora da lista sintética). Docstring diz o que **não** pega: prosa, nome, CEP, binário, segredo sem forma conhecida |
| BAIXO | testes com IPs de aparência real (`100.117.x`, `10.9.x`) | faixa de documentação `203.0.113.0/24` |
| BAIXO | CI `uv sync --frozen` aceitava `uv.lock` fora do `pyproject` | `--locked`; `check.sh` ganhou `uv lock --check` |
CI conferido: `permissions: contents: read`, `pull_request` (não `_target`), actions por SHA verificado, `persist-credentials: false`, sem segredo,
serviço `postgres:18` com senha descartável, `timeout-minutes`. **Aberto (BAIXO):** `setup-uv` sem `version:` fixa a versão do `uv`.

## 4. Passo 3 · fidelidade ao estudo I
- **350 casos × `i-teste-0001.sh`:** os 350 nomes saem **na mesma ordem** (comparei com a saída do script rodado; só 4 diferem porque o script
  interpola o UUID no nome). Contagem por tipo: 200 `err`, 86 `ok`, 49 `eq`, 14 `func` (cifra e dedupe), 1 `nao_vazio`.
- **Amostra de 20** (índices 1, 4, 11, 42, 57, 68, 73, 108, 113, 137, 144, 156, 163, 172, 196, 205, 248, 324, 327, 342): papel, SQL e
  expectativa idênticos ao script (os laços do script, como as 6 etapas de repasse, foram expandidos). Os 13 de cifra usam o `Chaveiro` real com
  a AAD completa do script. Sem divergência.
- **Mutação:** removi `atendimento_ativo_chat_uq` → reprovam 12+ casos (as 4 «trava por chat», `pausado ainda tranca o chat`, e os dependentes);
  removi `ferramenta_chamada_t7_viva_uq` → reprova «2ª T7 viva da pessoa+banco». O controle negativo do repo (sem os 2 índices as inserções
  passam) está correto e tem o par «banco intacto recusa».

## 5. Passo 4 · qualidade
Funções < 50 linhas e arquivos < 800 (maior: `casos_c.py`, 624) em todo o repo; sem mutação escondida (Settings `frozen`, `Migracao` `frozen`,
`Chaveiro` imutável); erros explícitos e sem eco de valor. `uv.lock` coerente (`uv lock --check`). README/OPERACAO agora dizem a verdade:
ordem na S4 com `SET ROLE ia_owner` dentro dos arquivos, ledger atômico, `search_path` nos logins, «NÃO EXECUTAR SEM O SIM» nas seções 3 e 4,
rotação exige reiniciar (cache do chaveiro). `scripts/aplicar_migracoes_local.sh` roda limpo.

## 6. Passo 5 · os 5 pontos do construtor
1. **AAD:** a forma completa vale (I §1.6, plano 01, script do estudo). Simples removida; cofre com AAD própria. Commit `7c78615` (21 falhas antes).
2. **`search_path` do Procrastinate:** correto ficar **fora** da migração (é de papel/conexão). **Errado no doc:** `ALTER ROLE ia_app IN DATABASE`
   (grupo NOLOGIN) não chega ao login `ia_app_a`; reproduzi em PG 18 (`"$user", public`) e o `INSERT` em `procrastinate_jobs` falharia na S4.
   Docs corrigidos para `ia_app_a` e `ia_app_b`; teste executa o comando do README e prova o efeito. Commit `16e293f`.
3. **0002 com `SET ROLE ia_owner; SET search_path` embutido:** correto e consistente com a 0001. Fail-closed (`SET ROLE` falha se quem aplica não é
   superusuário/membro), desfeito pelo rollback, `RESET` no fim, coberto pelo checksum. Aceito como está (não regerei a 0002).
4. **Ledger na mesma transação:** correto no código; o passo a passo da S4 foi alinhado. Commits `2998d3d`, `16e293f`.
5. **Hardening do `Settings`:** insuficiente como entregue (lista negativa, parse de DSN próprio, `errors()` com valor). Agora lista positiva,
   login pelo libpq, segredos mínimos, `ConfiguracaoInvalida`. Commit `4a79bc6` (39 falhas antes).

Commits desta revisão: `4a79bc6` config · `7c78615` cifra · `6ce0c4f` máscara (13 falhas antes) · `2998d3d` migrações · `f0de31d` e-mail colado
(2 falhas antes) · `16e293f` docs S4 (+5 testes de doc→banco) · `c34abec` varredura/CI (4 falhas antes) · e o commit deste documento.

## 7. Itens abertos (todos BAIXO) e recados para as próximas etapas
- Túnel loopback para a S4 passa na guarda do CLI; diretório da chave AES não é verificado (a montagem `:ro` de `/etc/ia-s4` é a defesa);
  `setup-uv` sem versão fixa; a linha `ia_app_b` do doc só é verificada por regex (o cluster de teste não tem esse login).
- **B1/B5:** `modelo_nome` aceita o nome lógico (`deepseek-v4p1-flash-1017`) como na semente do banco; a garantia «só EUA» depende do roteador `-us`
  e do host. Quem montar a chamada ao provedor deve mapear o nome lógico para `accounts/fireworks/routers/…-us` e recusar o host sem o roteador.
- **B1.2:** `gravar_conversa` deve usar `cifrar(..., seq=, remetente=, tipo=)` e `cifrar_cofre`; a máscara recebe `nomes=` do chamador.
- Antes da tag: `git tag v0.1.0` + `gh release create` (rodízio: tag só por quem não escreveu as correções, depois do segundo olhar nos 7 diffs).
