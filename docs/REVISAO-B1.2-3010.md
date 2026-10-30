# Revisão adversarial B1.2 (30/10) — branch `feat/b1-2-linha-tempo` (6 commits, +2519 linhas)

Revisor de contexto limpo, só leitura. Tudo abaixo foi **rodado** (PG 18 descartável, papel `ia_app_a`), salvo onde marcado «lido».
Baseline: `bash scripts/check.sh` verde (827 passed, 1 xfailed). Mutação: 30 mutantes aplicados numa cópia em /tmp, 27 mortos.
Scripts dos experimentos: `/tmp/rev_exp_b12/test_rev*.py` (rodam com `PYTHONPATH=. pytest -p tests.conftest -p tests.apoio_b12`).

## Veredito: APROVAR COM CORREÇÕES (0 crítico, 4 altos, 9 médios)

O núcleo criptográfico está sólido: nonces únicos (50/50), AAD com os 5 campos (copiar linha para outro atendimento, outro `seq` ou
outro remetente dá `FalhaAoDecifrar`), `ia_leitura`/`ia_qualidade`/`intruso` sem acesso a `cofre`/`conversa_cifrada`, `ia_app` sem
UPDATE/DELETE em `passo`/`conversa_cifrada` e sem DELETE no cofre, escrita concorrente (4 threads × 10) sem colisão de `seq`/`ordem`,
HMAC do fingerprint ≠ `h16`, SQL só com colunas internas. Os furos estão na borda: texto livre do modelo, `repr`, dedupe e relógio.

## As 5 correções mais importantes
1. **A1** `passo.motivo` guarda palavras do cliente em claro por 365 d (e vaza também pelo `DETAIL` do CheckViolation).
2. **A2** `repr(EventoMensagem)`/`Troca`/`Conversa` e `ValidationError.errors()` do construtor direto trazem o texto cru.
3. **A3** dedupe permanente descarta para sempre mensagem legítima idêntica (`datetime_post` ausente; dois «sim» no mesmo segundo).
4. **M1/M2** TTL, retenção e `chave_id` seguem o relógio/chaveiro do chamador: nada no banco limita a vida real a 7/30 d.
5. **M3** `nomes=()` como default em `gravar_troca`/`gravar_resumo`/`gravar_mensagem_recebida` é fail-open (o resumo grava o nome).

---

## ALTO

### A1 · `passo.motivo` carrega texto do cliente em claro, legível por `ia_leitura`, 365 d (`passos.py:67-76`, `passos.py:107,119`)
O modelo escreve o `motivo`; `_mascarado` só troca PII e o nome do cliente. Prova (marcador único `zebra-quantica-parcela-XYZ`, dump
de todas as tabelas `ia.*` e `procrastinate.*`): único achado em claro = `ia.passo.motivo = "cliente disse zebra-…-XYZ sobre juros"`.
`conversa_cifrada` e `cofre` ficaram limpos. `conversa_cifrada` vive 14 d; o `passo` vive 365 d e `ia_leitura`/`ia_qualidade` o leem:
a promessa «texto some em 14 d» é furada pelo `motivo`. Além disso o apelido passa: `«Joãozinho quer parcela menor»` com
`nomes=["João Carlos"]` grava intacto. E a violação de CHECK imprime a linha inteira: `Failing row contains (…, cliente disse
SEGREDO-ZZZ, …)` (provado: `"SEGREDO-ZZZ" in str(CheckViolation)` = True), então o motivo vai a log/Sentry sem passar por `mascarar`.
**Correção:** `motivo` do modelo vira código (`^[a-z0-9_]{1,40}$`, como `intencao`) ou lista fechada; se texto livre for inegociável,
recusar `motivo` que contenha qualquer palavra ≥ 4 letras presente na mensagem do turno e capturar `psycopg.errors.CheckViolation`
relançando sem `DETAIL`. **Teste que reprova hoje:** `gravar_passo(decisao, motivo=f"cliente disse {MARCADOR}")` e depois
`assert MARCADOR not in dump(ia.passo)`.

### A2 · `repr` e `ValidationError.errors()` expõem texto (`evento_mensagem.py:58-66`, `conversa.py:57-71`)
`repr(EventoMensagem(texto="zebra… joão carlos"))` → `texto='zebra… joão carlos'` (provado). `Troca` e `Conversa` (texto decifrado)
idem. `hide_input_in_errors` só protege `str(erro)`: o construtor direto com `model_validator` falhando
(`origem_evento="reconciliacao"` sem `rpa_id`, texto `"   SEGREDO-123 "`) devolve `e.errors()` com o dict de entrada inteiro
(provado: `"SEGREDO" in errors()` = True; `str(e)` = False). A B1.5 (FastAPI) devolverá `input` no 422 se tipar o corpo como `EventoMensagem`.
**Correção:** `Field(repr=False)` em `texto` e `url_arquivo` (a URL pode levar token); `field(repr=False)` em `Troca.texto` e
`Conversa.resumo/mensagens`; sobrescrever `__init__`/usar `model_validator(mode="wrap")` para que o construtor também passe por `validar`, ou
tornar `criar` o único caminho e testar que `EventoMensagem(...)` direto não é usado fora de testes. **Teste:** `assert MARCADOR not in repr(evento)`
e `assert MARCADOR not in json.dumps(erro.errors(), default=str)` no caminho de `reconciliacao` sem `rpa_id`.

### A3 · Dedupe permanente que descarta mensagem legítima (`evento_mensagem.py:110-117`, `linha_tempo.py:222-226`)
`h16` usa a hora truncada ao segundo e `datetime_post` é opcional (`None` → `""`, contrato 08 §5.1). Provado: `«sim»` duas vezes no mesmo
segundo → `Gravada, Duplicada`; com `datetime_post=None` o 2º `«sim»` é `Duplicada` (e seria para sempre, em qualquer atendimento futuro do
chat, porque o índice é global e permanente). Duas imagens cujo link só difere na query: `Gravada, Duplicada`. O `«sim»` é justamente a
confirmação de T4/T7. `Duplicada` é no-op silencioso: quem chama não distingue replay de mensagem nova.
**Correção:** sem `datetime_post`, não usar `cg:` (usar `cgid:`/rejeitar com 422 ou injetar o instante de recebimento arredondado ao
minuto no h16 e registrar `fora_de_ordem`); incluir frações de segundo no h16; devolver em `Duplicada` o `atendimento_id` apenas se igual ao
atual (ver B2). **Teste:** `identidade(ev("sim", datetime_post=None))` gravado em dois atendimentos diferentes deve gerar 2 `Gravada`.

### A4 · Texto livre do passo sem hora de recebimento: `texto_livre_permitido` sem fonte persistida (`conversa.py:76-84`, `tests/test_conversa.py:223`)
A spec B1.2 (v3) diz «o estado guarda `ultimo_cliente_em`». Nada o grava (`grep` só acha docstring); `gravar_mensagem_recebida` não o atualiza.
O teste da coluna é `xfail(strict=False)`: nunca fica vermelho nem avisa quando a coluna aparecer. Futuro no relógio do cliente também passa:
`texto_livre_permitido(AGORA, AGORA+30d)` = True (provado). A fronteira de 24 h exata está certa (`==24h` → False, `24h−1µs` → True; mutante `<=` morto).
**Correção:** `strict=True` no xfail e dono/prazo explícito (B1.1/0003); recusar `ultimo_cliente_em > agora + tolerância`.

---

## MÉDIO

### M1 · TTL e retenção seguem o relógio do chamador (`cofre.py:49-57`, `conversa.py:111-116`)
`guardar` grava `criado_em=agora` e `expira_em=agora+ttl`; o CHECK só compara as duas colunas entre si. Provado: `agora=2030-01-01` →
`expira_em=2030-01-08`; `expirar(now)` devolve 0 e a linha fica 4 anos (a poda usa `now()` do banco). Idem `criada_em/apagar_em` de
`conversa_cifrada` e o piso/teto de `ocorrido_em`. Reguardar renova o TTL sem limite (`criado_em` é reescrito).
**Correção:** `criado_em`/`expira_em` por `now()`/`now()+make_interval` no SQL (parâmetro `ttl` só para o intervalo), `ocorrido_em` idem.
**Teste:** `guardar(agora=2030)` seguido de `SELECT expira_em <= now()+interval '7 days'`.

### M2 · `chave_id` mensal nunca é conferido com `agora` (`conversa.py:68`, `cifra.py` vigente)
`chave_id_do_mes` não é chamado em código de produção. Provado: `gravar_troca(agora=2026-12-15)` com chaveiro vigente 2 grava `chave_id=2`
(esperado 3). Esquecer de virar `CHAVE_AES_ID` no dia 1 faz as linhas de dezembro morrerem com a chave de novembro (perda) ou, no sentido
inverso, mantém o texto legível além do descarte planejado. **Correção:** `if chaveiro.vigente != chave_id_do_mes(agora): raise ChaveForaDoMes`
em `_gravar`/`guardar`. O teste hoje só afirma a igualdade da fixture (`test_conversa.py:114`).

### M3 · `nomes=()` como default é fail-open (`conversa.py:111,153`, `linha_tempo.py:195`)
`passos` usa `None`=fail-closed; conversa/resumo/identidade usam `()`. Provado: `gravar_resumo(texto="O João Carlos quer parcela menor e mora na
Rua das Flores")` sem `nomes` **grava** e `ler_trocas` devolve o nome ao prompt (H §3.5: «sem nomes»). **Correção:** `nomes` obrigatório,
sem default (ou `None` recusa). **Teste:** chamar `gravar_resumo` sem `nomes` deve falhar.

### M4 · Casamento webhook × RPA ausente: o mesmo evento vira dois passos (`linha_tempo.py:188-203`)
Provado: webhook `cg:…` (ordem 1) e reconciliação `rpa:abc12345XYZ` do mesmo conteúdo → `Gravada` ×2, `mensagens_pendentes`=2, dois turnos.
O autor deixa para B1.5; **não quebra o aceite literal de B1.2** («dedupe por `msg_chave` + `msg_fingerprint`») e o ramo `msg_chave_rpa = rpa_id` está
correto para depois do `fn_anexar_rpa` (contrato D5). Mas o reconciliador (a cada 2 min) vê toda mensagem que o webhook já entregou, então
no dia em que ligar sem o passo 7 do contrato §5.3 cada mensagem vira 2 turnos. O fingerprint inclui `datetime_post`, que o RPA desvia: não serve
de atalho. **Correção:** o passo 7 (candidatos do mesmo atendimento, texto decifrado, |Δt| ≤ 10 s) precisa viver **dentro** desta função, sob o
`FOR UPDATE`, senão há corrida entre os dois caminhos; documentar a precondição no docstring e deixar um teste `xfail(strict=True)`
`test_webhook_e_rpa_colapsam`.

### M5 · `Conflito` falso quando os `nomes` mudam entre replays (`evento_mensagem.py:126-139`)
O fingerprint mascara com `nomes`. Provado: mesma mensagem «sou o joão» com `nomes=()` e depois `nomes=["João"]` → `Conflito` (passo `erro` +
alerta TI por mensagem repetida inocente). Se o nome do cliente for corrigido/aprendido depois, todo replay antigo vira alarme.
**Correção:** fingerprint só sobre o texto mascarado **sem nomes** (nomes só no que vai à conversa), como diz o contrato §5.1.

### M6 · `consumir` perdedor da corrida recebe `ValueError`, não `ConflitoDeVersao` (`linha_tempo.py:268-272`)
Provado com 2 threads: `[('ok', 2), ('ValueError', 'ate_ordem deve ser…')]`. Quem trata só `ConflitoDeVersao` para repetir o turno estoura.
A validação roda antes do CAS e vê `ordem_consumida` já avançada. **Correção:** ler `versao` sob o lock e levantar `ConflitoDeVersao` antes de validar `ate_ordem`.

### M7 · `anotacao_operador` com `resultado` longo viola o CHECK (`passos.py:46,LIMITE_NOTA=250`)
`«Anotação (` + 40 + `): ` + 250 = 303 > 300. Provado: `CheckViolation passo_campos_por_tipo_check` (e a mensagem traz a linha inteira,
ver A1). **Correção:** `LIMITE_NOTA = 240`, ou validar `len(texto_passo) <= 300` no modelo. **Teste:** `resultado="r"*40, nota="n"*250`.

### M8 · Máscara de nomes (`mascara.py:_mascarar_nomes`, pré-existente na main, mas é a fronteira do achado S1)
Provado com `nomes=["João Carlos da Silva"]`: `Joãozinho`, `joaoCarlos`, `joaodasilva@x` (já mascarado só pelo e-mail), `JC`, `Carlão` passam;
nome de ≤ 2 letras (`Jo`) nunca é mascarado (`_TAMANHO_MIN_PARTE=3`). CPF/telefone resistem bem (espaços, pontos parciais, `+55`, 11 dígitos
colados a letras, largura total, e-mail com unicode/IDN: todos mascarados). Fora: `529a982a247a25` e `529.......982.....247-25` (deixa `529.......`), e-mail
«joão arroba gmail ponto com» (limites já documentados). **Correção:** casar a parte do nome como prefixo de palavra (`joao\w*`) para as
partes ≥ 4 letras e pedir ao chamador apelidos/diminutivos; aceitar o resíduo documentado.

### M9 · Chaves HMAC fracas e as do vetor público aceitas (`config.py:55-64`, `evento_mensagem.py:84-89`)
`ChavesDeMensagem(h16=b"a"*32, fingerprint=b"b"*32)` e as chaves de teste do contrato (`chave-h16-de-teste-descartavel-01`) constroem e
`Settings` só exige 32 caracteres. Chave permanente e impossível de girar: uma fraca derruba o argumento do HMAC (S2). **Correção:** exigir ≥ 32
bytes decodificados de base64/hex (ou entropia mínima) e recusar as chaves de teste conhecidas fora de `ambiente=teste`.

---

## BAIXO
- **B1** Mutantes sobreviventes (testes que não pesam): `M10` sem `ON CONFLICT` (corrida entre atendimentos nunca exercitada), `M12` `linha[3] < agora`
  (fronteira do vencimento do cofre), `M30` sem `.strip()` na normalização (o dedupe de «texto␠» não tem teste). 27 dos 30 mutantes morrem.
- **B2** `Duplicada`/`Conflito` devolvem `atendimento_id`+`ordem` de **outro** atendimento (vazamento interno entre conversas do mesmo chat).
- **B3** `expirar` (`cofre.py:67-78`): conta por `agora` do chamador mas a poda usa `now()`; com relógio atrasado deixa vencido; também poda
  conversa/cofre de encerrados (efeito colateral documentado). Provado: `expirar(agora=ontem)` devolve 0 com linha vencida no banco.
- **B4** `ler_trocas` levanta `FalhaAoDecifrar` em uma linha adulterada e derruba o turno inteiro (DoS por quem tem escrita no banco); desenho aceitável, registrar.
- **B5** Nome do cliente igual a palavra do texto fixo (`nomes=["Erro"]`) faz `gravar_passo(erro)` levantar `PassoComPii` (provado; improvável).
- **B6** `RETENCAO_LINHA = 30 d` é o teto absoluto; atendimento aberto > 14 d mantém texto além da promessa de 14 d (a poda só conta após o encerramento).
- **B7** `gravar_passo(ocorrido_em=agora)`/`naive` datetime: sem validação de fuso em `agora` (só `texto_livre_permitido` valida).

## Itens perguntados e sem achado (provado)
- Texto em log/span: nenhum `logging`/`print`/OTel nos 6 módulos novos; `caplog` DEBUG sem o marcador.
- `passo.texto` nunca cita o cliente (13 tipos; só tamanho/códigos). Cofre nunca vai a passo/conversa.
- AAD/nonce/`seq` trocado, `chave_id` adulterado, chave descartada (linha omitida e contada) e chave antiga ainda decifrando: ok.
- `FOR UPDATE` presente em `gravar_passo`, `gravar_mensagem_recebida`, `consumir`, `_gravar` (conversa/resumo); `guardar` usa upsert sem lock (ok).
- `consumir`: CAS por `versao` impede dois consumos (mutante sem CAS morto); corrida só falha no tipo da exceção (M6).
- GRANTs da 0001 bastam para tudo que o código faz como `ia_app` (rodado como `ia_app_a`, sem superusuário); `FOR UPDATE` exige só UPDATE em coluna: ok.
  Atenção B1.5: `ia_app` não tem UPDATE em `passo`, então anexar `msg_chave_rpa` depende da `ia.fn_anexar_rpa` da 0003 (contrato D5).
- `hide_input_in_errors` via `criar`/`validar`: sem `input` nem `__cause__`/`__context__`; surrogate solto vira `ValidationError` sem eco.
- SQL por interpolação: só nomes de coluna de `DadosPasso.colunas()` e constantes (`# noqa: S608` justificados); valores sempre parametrizados.
- Testes não tautológicos nos pontos críticos (AAD ×3, nonce, janela 24 h, CAS, `verif_det`, `turno/fase`, motivo mascarado, TTL 7 d, cofre vencido).


---

## Resposta do autor (30/10)

Todos os testes do revisor foram escritos antes e reprovaram no código anterior; `bash scripts/check.sh` verde (851 passed, 2 xfailed). Mutação: os 9
mutantes das correções (inclui os 3 sobreviventes B1) morrem.

| Item | Resposta |
|---|---|
| A1 | Corrigido. `motivo` é código de catálogo (`Codigo40`), texto livre/apelido/PII é recusado; `nomes` saiu de `colunas()`. `CheckViolation` vira `PassoRecusadoPeloBanco(restricao)` sem causa encadeada. |
| A2 | Corrigido. `Field(repr=False)` em `texto`/`url_arquivo`; `Troca.texto` e `Conversa.*` fora do `repr`; `ModeloSemEco.__init__` troca o `ValidationError` por `EntradaInvalida` (vale para `EventoMensagem` e para as 14 classes de passo). Os nomes vão a `criar` por `ContextVar` porque o Pydantic chama `__init__` sem `context=`. |
| A3 | Corrigido no que o dado permite: `cgid:` com `mensagem_id`; fração de segundo e query da URL no `h16` (o vetor do contrato, sem fração, segue igual); sem hora nem id exige `recebido_em` (custo: replay SEM hora não dedupa). Dois «sim» no mesmo segundo SEM id continuam colapsando: só o `mensagem_id` do ChatGuru (P2) resolve. |
| A4 | Parcial. `xfail` strict e futuro > 5 min fecha a janela. A gravação de `ultimo_cliente_em` é da B1.1 (0003, `registrar_mensagem_do_cliente`). |
| M1 | Corrigido. `criado_em/expira_em/criada_em/apagar_em/ocorrido_em` por `now()` do SQL; `agora` ficou só para a chave mensal. `guardar` de novo não passa de `criado_em + 7 d`. |
| M2 | Corrigido (`ChaveForaDoMes`); o chamador sem `agora` usa o relógio real. |
| M3 | Corrigido. `nomes` sem default nas três APIs de conversa; `None` levanta `NomesIndisponiveis`. A identidade não recebe mais `nomes` (M5). |
| M4 | Gancho `casar` dentro do `FOR UPDATE` (teste com casador falso) e `xfail(strict)` `test_webhook_e_rpa_colapsam`. O casamento em si (decifrar candidatos, |Δt| ≤ 10 s) fica na B1.5. |
| M5 | Corrigido. Fingerprint sobre o texto mascarado sem nomes. Isso reverte a parte «nomes antes do hash» do S2; o HMAC com chave própria continua e é o que impede a reversão por dicionário. |
| M6 | Corrigido (versão conferida primeiro sob o lock). |
| M7 | Corrigido (`LIMITE_NOTA = 240`, teste 40 + 240 e 40 + 250). |
| M8 | Adiado: está em `mascara.py` (fundação, fora do escopo B1.2); prefixo de palavra e apelidos pedem decisão sobre excesso de máscara. |
| M9 | Adiado: entropia mínima das chaves HMAC e recusa das chaves de teste dependem do formato (base64/hex) que o dono definir para o segredo; hoje 32+ caracteres e diferentes. |
| B1 | Três mutantes agora têm teste (`ON CONFLICT` por corrida simulada, `.strip()`, vencimento do cofre pelo relógio do banco). |
| B2, B3, B7 | Corrigidos (`Duplicada` sem `ordem` alheia; `expirar` só com o relógio do banco; `agora` dos passos removido). |
| B4, B5, B6 | Registrados, sem mudança: `FalhaAoDecifrar` derruba o turno de propósito (integridade); nome igual a palavra do texto fixo é improvável; retenção de atendimento aberto > 14 d fica para a poda da B1.3. |
