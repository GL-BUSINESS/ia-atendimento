-- 0001_esquema.up.sql · banco ia_atendimento (cluster gl360, S4) · aplicar como s4_super: psql -1 -v ON_ERROR_STOP=1 -f (o arquivo faz SET ROLE ia_owner).
-- Pré-requisito (infra, «sim» do dono): roles ia_owner (NOLOGIN, dono do banco), ia_app, ia_leitura e ia_qualidade (grupos NOLOGIN; L §7) e os logins _a/_b.
-- Depois do COMMIT o script de aplicação grava ia.migracao com o sha256 do arquivo. Sem pgcrypto: a cifra é na aplicação (§2).
SET ROLE ia_owner; SET lock_timeout = '3s';
CREATE SCHEMA IF NOT EXISTS ia; CREATE SCHEMA IF NOT EXISTS procrastinate;  -- procrastinate: conteúdo na 0002 (SQL de `procrastinate schema --read`, versão pinada)
REVOKE ALL ON SCHEMA ia, procrastinate FROM PUBLIC;
-- Default privileges do ia_owner: a 0002+ nasce com o grant certo. Em `ia` NÃO há grant automático de tabela (append-only × mutável difere por tabela);
-- função nunca nasce executável por PUBLIC; procrastinate dá DML (com DELETE) ao ia_app, que não cria nada lá.
ALTER DEFAULT PRIVILEGES FOR ROLE ia_owner REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE ia_owner IN SCHEMA ia GRANT USAGE, SELECT ON SEQUENCES TO ia_app;
ALTER DEFAULT PRIVILEGES FOR ROLE ia_owner IN SCHEMA procrastinate GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ia_app;
ALTER DEFAULT PRIVILEGES FOR ROLE ia_owner IN SCHEMA procrastinate GRANT USAGE, SELECT ON SEQUENCES TO ia_app;
ALTER DEFAULT PRIVILEGES FOR ROLE ia_owner IN SCHEMA procrastinate GRANT EXECUTE ON FUNCTIONS TO ia_app;
-- Ledger de migrações (o orquestrador confere a versão no boot) e versões dos artefatos em git (append-only por privilégio; sem seed: o dono aprova a v1).
CREATE TABLE IF NOT EXISTS ia.migracao (migracao_id text PRIMARY KEY CHECK (migracao_id ~ '^[0-9]{4}_[a-z0-9_]{1,60}$'), checksum text NOT NULL CHECK (checksum ~ '^[0-9a-f]{64}$'),
  aplicada_em timestamptz NOT NULL DEFAULT now(), aplicada_por text NOT NULL DEFAULT session_user);
CREATE TABLE IF NOT EXISTS ia.artefato_versao (
  tipo text NOT NULL, numero integer NOT NULL, entrou_em timestamptz NOT NULL DEFAULT now(), descricao text NOT NULL, aprovado_por text NOT NULL, fracao_experimentacao numeric(5,4) NOT NULL DEFAULT 0,
  CONSTRAINT artefato_versao_pk PRIMARY KEY (tipo, numero),
  CONSTRAINT artefato_versao_check CHECK (tipo IN ('roteiro', 'regras', 'catalogo', 'motor') AND numero >= 1 AND fracao_experimentacao BETWEEN 0 AND 1
    AND char_length(btrim(descricao)) BETWEEN 1 AND 1000 AND char_length(aprovado_por) BETWEEN 1 AND 128));
-- Configuração APPEND-ONLY (INV-34 do GL). Vigente = max(versao) por nome; perder a corrida na PK = 409. Nome ABERTO por padrão (chave nova não pede
-- ALTER; o registro de chaves válidas é o do orquestrador); as chaves conhecidas têm o valor validado aqui. Chaves do estudo J: max_*, subteto_dia, calendario_bloqueio.
CREATE TABLE IF NOT EXISTS ia.config_versao (
  nome text NOT NULL, versao integer NOT NULL, valor jsonb NOT NULL,
  publicado_em timestamptz NOT NULL DEFAULT now(), publicado_por text NOT NULL, motivo text,
  CONSTRAINT config_versao_pk PRIMARY KEY (nome, versao),
  CONSTRAINT config_versao_nome_check CHECK (nome ~ '^[a-z][a-z0-9_]{1,59}$' AND versao >= 1),
  CONSTRAINT config_versao_valor_check CHECK (CASE
    WHEN nome IN ('teto_mensal_brl', 'subteto_dia', 'alcada_valor_max_brl') THEN CASE WHEN jsonb_typeof(valor) = 'number' THEN (valor)::numeric >= 0 ELSE false END
    WHEN nome = 'agenda_teto_horas' THEN CASE WHEN jsonb_typeof(valor) = 'number' THEN (valor)::numeric BETWEEN 1 AND 23 AND (valor)::numeric = trunc((valor)::numeric) ELSE false END   -- M: janela de 24 h do WhatsApp
    WHEN nome = 'agenda_max_por_atendimento' THEN CASE WHEN jsonb_typeof(valor) = 'number' THEN (valor)::numeric BETWEEN 1 AND 2 AND (valor)::numeric = trunc((valor)::numeric) ELSE false END   -- teto do DDL: seq 1..2
    WHEN nome = 'agenda_janela' THEN jsonb_path_exists(valor, '$ ? (@.inicio like_regex "^([01][0-9]|2[0-3]):[0-5][0-9]$" && @.fim like_regex "^([01][0-9]|2[0-3]):[0-5][0-9]$" && @.inicio < @.fim && @.inicio >= "08:00" && @.fim <= "20:00"
      && (!exists(@.sabado_fim) || (@.sabado_fim like_regex "^([01][0-9]|2[0-3]):[0-5][0-9]$" && @.sabado_fim > @.inicio && @.sabado_fim <= @.fim)))')
    WHEN nome = 'chats_teste' THEN jsonb_typeof(valor) = 'array' AND jsonb_array_length(valor) <= 50 AND NOT jsonb_path_exists(valor, '$[*] ? (!(@.type() == "string" && @ like_regex "^[A-Za-z0-9_-]{1,128}$"))')   -- allowlist de chat_id do modo teste
    WHEN nome = 'agenda_periodos' THEN jsonb_typeof(valor) = 'object' AND NOT jsonb_path_exists(valor, '$.keyvalue() ? (!(@.key like_regex "^[a-z_]{1,30}$" && @.value like_regex "^([01][0-9]|2[0-3]):[0-5][0-9]$" && @.value >= "08:00" && @.value <= "20:00"))')   -- «de manhã» → 09:00…
    WHEN nome IN ('max_disparos_dia', 'max_abertos', 'ia_repasse_dias', 'agenda_max_pausados', 'agenda_folga_min', 'agenda_max_dia') THEN CASE WHEN jsonb_typeof(valor) = 'number'
      THEN (valor)::numeric BETWEEN 1 AND 200 AND (valor)::numeric = trunc((valor)::numeric) ELSE false END
    WHEN nome = 'modo' THEN jsonb_typeof(valor) = 'string' AND (valor #>> '{}') IN ('real', 'sombra', 'duble', 'teste')
    WHEN nome = 'bancos_digitacao' THEN jsonb_typeof(valor) = 'array' AND valor <@ '["FACTA", "3RN", "C6"]'::jsonb
    WHEN nome = 'calendario_bloqueio' THEN jsonb_typeof(valor) = 'object' AND coalesce(jsonb_typeof(valor -> 'janelas'), '') = 'array'
    WHEN nome = 'verificador_modelo' THEN jsonb_typeof(valor) = 'string'
    WHEN nome = 'faixas_esforco' THEN jsonb_typeof(valor) = 'object' AND octet_length(valor::text) <= 2048 AND NOT jsonb_path_exists(valor, '$.** ? (@.type() == "string")')   -- af/ag/MON 11c: sem texto;
      AND jsonb_path_exists(valor, '$ ? (@.limites_brl.type() == "array" && @.limites_brl.size() == 3 && @.limites_brl[0] > 0 && @.limites_brl[0] < @.limites_brl[1] && @.limites_brl[1] < @.limites_brl[2])')   -- baixa < L0 ≤ média ≤ L1 < alta ≤ L2 < muito_alta
      AND coalesce((valor -> 'faixas') ?& ARRAY['baixa', 'media', 'alta', 'muito_alta'] AND ((valor -> 'faixas') - ARRAY['baixa', 'media', 'alta', 'muito_alta']) = '{}'::jsonb, false)   -- coalesce: sem 'faixas' o NULL passaria no CHECK
      AND NOT jsonb_path_exists(valor, '$.faixas.* ? (!(@.lembretes_max >= 0 && @.lembretes_max <= 2 && @.lembrete_pago_max >= 0 && @.lembrete_pago_max <= @.lembretes_max && @.dias_max >= 1 && @.dias_max <= 7 && @.contrapropostas_max >= 0 && @.contrapropostas_max <= 3
        && @.custo_max_brl > 0 && @.custo_max_brl <= 3 && @.agendamentos_max >= 0 && @.agendamentos_max <= 10))')   -- TETO GLOBAL (P7, J D7-5, expirar 7 d): a faixa nunca o excede
    WHEN nome IN ('janela_mensagem', 'janela_vendedores') THEN coalesce(jsonb_typeof(valor -> 'dias') = 'object' AND ((valor -> 'dias') - ARRAY['1', '2', '3', '4', '5', '6', '7']) = '{}'::jsonb, false)   -- ah: dia ISO 1..7 → {inicio, fim}
      AND jsonb_path_exists(valor, '$.dias.*') AND NOT jsonb_path_exists(valor, '$.dias.* ? (!(@.inicio like_regex "^([01][0-9]|2[0-3]):[0-5][0-9]$" && @.fim like_regex "^([01][0-9]|2[0-3]):[0-5][0-9]$" && @.inicio < @.fim))')
      AND (nome <> 'janela_mensagem' OR (NOT jsonb_path_exists(valor, '$.dias."7"') AND NOT jsonb_path_exists(valor, '$.dias.* ? (!(@.inicio >= "08:00" && @.fim <= "20:00"))')))   -- janela_mensagem: seg–sáb 08–20, NUNCA ultrapassada
    WHEN nome = 'esforco_por_periodo' THEN jsonb_typeof(valor) = 'object' AND octet_length(valor::text) <= 2048   -- ai: faixa × período → multiplicador (o efetivo nunca passa do teto global)
      AND coalesce(valor ?& ARRAY['baixa', 'media', 'alta', 'muito_alta'] AND (valor - ARRAY['baixa', 'media', 'alta', 'muito_alta']) = '{}'::jsonb, false)
      AND NOT jsonb_path_exists(valor, '$.* ? (!(exists(@.comercial) && exists(@.fora)))') AND NOT jsonb_path_exists(valor, '$.*.keyvalue() ? (@.key != "comercial" && @.key != "fora")')
      AND NOT jsonb_path_exists(valor, '$.*.* ? (!(@.espera >= 0 && @.espera <= 2 && @.lembretes >= 0 && @.lembretes <= 2 && @.contrapropostas >= 0 && @.contrapropostas <= 2))')
    WHEN nome = 'modelo_por_faixa' THEN jsonb_typeof(valor) = 'object' AND octet_length(valor::text) <= 2048   -- ag: faixa → modelo; só deepseek-* ou gemini-*, nunca outra família
      AND coalesce(valor ?& ARRAY['baixa', 'media', 'alta', 'muito_alta'] AND (valor - ARRAY['baixa', 'media', 'alta', 'muito_alta']) = '{}'::jsonb, false)
      AND NOT jsonb_path_exists(valor, '$.* ? (!(@.modelo like_regex "^(deepseek|gemini)-[a-z0-9][a-z0-9._-]{0,59}$" && @.provedor like_regex "^[a-z0-9_-]{1,30}$" && @.raciocinio.type() == "boolean"
        && @.custo_max_brl > 0 && @.custo_max_brl <= 3))')
    WHEN nome IN ('ia_ativa', 'verificador_ativo', 'agenda_ativa', 'agenda_b_digita', 'bloqueio_entrada') THEN jsonb_typeof(valor) = 'boolean'
    ELSE true END),
  CONSTRAINT config_versao_autor_check CHECK (char_length(publicado_por) BETWEEN 1 AND 128 AND (motivo IS NULL OR char_length(motivo) BETWEEN 1 AND 500)));
-- Tudo nasce DESLIGADO e no modo mais seguro (D27; D1). Rampa do piloto (J §2.4) = versões novas de max_disparos_dia (15, 20). alcada_valor_max_brl = 6000: p90 do valor_contratado do robô na FACTA, 30 d, n=1.495 (REVISAO-LACUNAS §Medição para D15; D15, só FACTA no MVP).
INSERT INTO ia.config_versao (nome, versao, valor, publicado_por, motivo) VALUES
  ('ia_ativa', 1, 'false', 'migracao:0001', 'nasce desligada'), ('teto_mensal_brl', 1, '2000', 'migracao:0001', 'teto do piloto (dono, 29/10/2026)'), ('modo', 1, '"duble"', 'migracao:0001', 'nunca toca banco nem canal reais'),
  ('subteto_dia', 1, '100', 'migracao:0001', 'J §4.1 D7-5'), ('max_disparos_dia', 1, '10', 'migracao:0001', 'J §2.4: 23/11 ≤ 10, 24/11 ≤ 15, depois 20'), ('max_abertos', 1, '10', 'migracao:0001', 'D5'),
  ('verificador_ativo', 1, 'false', 'migracao:0001', 'T15 com modelo nasce desligado'), ('bancos_digitacao', 1, '["FACTA"]', 'migracao:0001', 'D1: só a FACTA digita'), ('ia_repasse_dias', 1, '14', 'migracao:0001', 'D35'),
  ('faixas_esforco', 1, '{"limites_brl": [150, 400, 800], "faixas": {"baixa": {"lembretes_max": 0, "lembrete_pago_max": 0, "dias_max": 1, "contrapropostas_max": 1, "custo_max_brl": 1.0, "agendamentos_max": 0},
    "media": {"lembretes_max": 1, "lembrete_pago_max": 0, "dias_max": 2, "contrapropostas_max": 2, "custo_max_brl": 2.0, "agendamentos_max": 1}, "alta": {"lembretes_max": 2, "lembrete_pago_max": 0, "dias_max": 3, "contrapropostas_max": 3, "custo_max_brl": 3.0, "agendamentos_max": 3},
    "muito_alta": {"lembretes_max": 2, "lembrete_pago_max": 1, "dias_max": 3, "contrapropostas_max": 3, "custo_max_brl": 3.0, "agendamentos_max": 3}}}',
   'migracao:0001', 'af/ag/ah/MON 11c: HIPÓTESE a medir (comissão esperada: <R$ 150 baixa, 150–400 média, 400–800 alta, >800 muito_alta; limites por faixa são chute; lembretes 0/1/2/2); nunca acima do teto global; só muito_alta pode pagar template'),
  ('esforco_por_periodo', 1, '{"baixa": {"comercial": {"espera": 0.5, "lembretes": 0.5, "contrapropostas": 0.5}, "fora": {"espera": 1.0, "lembretes": 1.0, "contrapropostas": 1.0}},
    "media": {"comercial": {"espera": 0.5, "lembretes": 0.5, "contrapropostas": 0.75}, "fora": {"espera": 1.0, "lembretes": 1.0, "contrapropostas": 1.0}},
    "alta": {"comercial": {"espera": 0.75, "lembretes": 0.75, "contrapropostas": 1.0}, "fora": {"espera": 1.0, "lembretes": 1.0, "contrapropostas": 1.0}},
    "muito_alta": {"comercial": {"espera": 1.0, "lembretes": 1.0, "contrapropostas": 1.0}, "fora": {"espera": 1.0, "lembretes": 1.0, "contrapropostas": 1.0}}}',
   'migracao:0001', 'ai/MON 11c: HIPÓTESE; no horário comercial dos vendedores o repasse vem mais cedo (multiplicador < 1); fora dele a faixa vale inteira; o efetivo nunca passa do teto global'),
  ('janela_vendedores', 1, '{"dias": {"1": {"inicio": "08:00", "fim": "18:00"}, "2": {"inicio": "08:00", "fim": "18:00"}, "3": {"inicio": "08:00", "fim": "18:00"}, "4": {"inicio": "08:00", "fim": "18:00"}, "5": {"inicio": "08:00", "fim": "18:00"}, "6": {"inicio": "08:00", "fim": "12:00"}}}', 'migracao:0001', 'ai: HIPÓTESE (seg–sex 08–18, sáb 08–12); define o período comercial'),
  ('janela_mensagem', 1, '{"dias": {"1": {"inicio": "08:00", "fim": "20:00"}, "2": {"inicio": "08:00", "fim": "20:00"}, "3": {"inicio": "08:00", "fim": "20:00"}, "4": {"inicio": "08:00", "fim": "20:00"}, "5": {"inicio": "08:00", "fim": "20:00"}, "6": {"inicio": "08:00", "fim": "20:00"}}}', 'migracao:0001', 'ai/J8: janela de mensagem ao cliente, seg–sáb 08–20; separada da dos vendedores e nunca ultrapassada'),
  ('modelo_por_faixa', 1, '{"baixa": {"modelo": "deepseek-v4p1-flash-1017", "provedor": "fireworks-us", "raciocinio": false, "custo_max_brl": 1.0}, "media": {"modelo": "deepseek-v4p1-flash-1017", "provedor": "fireworks-us", "raciocinio": false, "custo_max_brl": 2.0},
    "alta": {"modelo": "deepseek-v4p1-flash-1017", "provedor": "fireworks-us", "raciocinio": false, "custo_max_brl": 3.0}, "muito_alta": {"modelo": "deepseek-v4p1-flash-1017", "provedor": "fireworks-us", "raciocinio": false, "custo_max_brl": 3.0}}',
   'migracao:0001', 'ag: MVP com um modelo só em todas as faixas; trocar por faixa (V4 Pro, V4.1 Flash com raciocínio, Gemini Flash) só depois da F3, com o dono'),
  ('bloqueio_entrada', 1, 'false', 'migracao:0001', 'sem disparo novo (timer 20:15); abertos e pausados seguem as réguas deles'), ('chats_teste', 1, '[]', 'migracao:0001', 'allowlist de chat_id do modo teste; vazia = nenhum chat pode ser teste'),
  ('agenda_max_dia', 1, '5', 'migracao:0001', 'M §5.3: caso (b) começa baixo (5, 10, 15)'), ('agenda_periodos', 1, '{"cedo": "08:30", "manha": "09:00", "almoco": "12:00", "depois_do_almoco": "13:30", "tarde": "14:00", "fim_da_tarde": "17:30", "noite": "19:00"}', 'migracao:0001', 'M §2.3: padrões de período do extrator (noite = teto da janela)'),
  ('agenda_ativa', 1, 'false', 'migracao:0001', 'M: nasce desligado'), ('agenda_janela', 1, '{"inicio": "08:30", "fim": "19:00", "sabado_fim": "12:00"}', 'migracao:0001', 'M §2.4: seg–sáb, sábado até 12:00 no piloto (J §1.4)'),
  ('agenda_teto_horas', 1, '23', 'migracao:0001', 'M: última msg do cliente + 23 h (janela de 24 h)'), ('agenda_max_por_atendimento', 1, '2', 'migracao:0001', 'M: 2 por atendimento'), ('agenda_max_pausados', 1, '10', 'migracao:0001', 'M/K: fora de max_abertos'),
  ('agenda_folga_min', 1, '30', 'migracao:0001', 'M/K: a vigia só devolve em retoma_em + 30 min'), ('agenda_b_digita', 1, 'false', 'migracao:0001', 'M: caso (b) não abre digitação no MVP'),
  ('alcada_valor_max_brl', 1, '6000', 'migracao:0001', 'D15: p90 FACTA R$ 5.579 arredondado (REVISAO-LACUNAS §Medição para D15); acima disso mostra a oferta e repassa'),
  ('calendario_bloqueio', 1, '{"domingos": true, "feriados": ["2026-11-02", "2026-11-20"], "janelas": [{"de": "2026-11-20T22:00:00-03:00", "ate": "2026-11-23T06:00:00-03:00", "motivo": "dataprev"}]}',
   'migracao:0001', 'J §7: vale mesmo com a chave ligada; feriados a completar com o jurídico (J8)')
ON CONFLICT DO NOTHING;
-- Um atendimento da IA. Sem CPF, telefone, nome nem texto de conversa (o texto vive em conversa_cifrada). Mutável com CAS por `versao`.
CREATE TABLE IF NOT EXISTS ia.atendimento (
  atendimento_id uuid NOT NULL DEFAULT uuidv7(), origem text NOT NULL,   -- origem = caller autenticado: n8n_braco | robo_esteira
  chave_logica text NOT NULL, idempotency_key text NOT NULL,             -- legível (venda:<32 hex>, só p/ o TI) e o sha256 hex dela (A11), conferido por CHECK
  entrada_fingerprint text NOT NULL,                                     -- sha256 do corpo canônico: mesma chave + outro corpo = 409
  gatilho text NOT NULL, disparado_por text NOT NULL, sessao_id uuid, motivo_escolha text, motivo_escolha_nota text, criterio_versao text,  -- c §2.3, J §2.3
  comissao_esperada_brl numeric(14,2), faixa_esforco text NOT NULL,      -- af/MON 11c, gravadas no disparo e IMUTÁVEIS (fora do UPDATE do ia_app); comissão NULL = não calculável; nunca chega ao modelo
  pessoa_id uuid NOT NULL, chat_id text NOT NULL, phone_id text NOT NULL,  -- nunca CPF nem telefone do cliente (o número do chat vai ao cofre)
  clt_job_id uuid, contrato_id bigint, banco text, produto text, status_esteira text, perfil_versao smallint NOT NULL DEFAULT 1, perfil jsonb NOT NULL DEFAULT '{}',
  roteiro_versao integer NOT NULL, regras_versao integer NOT NULL, catalogo_versao integer NOT NULL, motor_versao integer NOT NULL, em_experimentacao boolean NOT NULL DEFAULT false,
  modo text NOT NULL,                                                    -- real | sombra | duble | teste (L), copiado da config ao abrir; métrica de produção filtra modo='real'
  estado text NOT NULL DEFAULT 'reservado', versao integer NOT NULL DEFAULT 1,  -- reservado → aberto ⇄ aguardando_cliente ⇄ pausado (M) → repassando → encerrado; versao = cerca (CAS)
  lease_ate timestamptz DEFAULT now() + interval '2 minutes', assumido_em timestamptz, retoma_em timestamptz,   -- M: quando um `pausado` volta (ou quando um `agendamento` reservado dispara)
    -- posse do chat (renovada a cada turno; NULL só se encerrado); assumir_canal concluído
  responsavel_antes text, chatbot_antes text, chatbot_estado text NOT NULL DEFAULT 'intocado',  -- consultor da entrega; estado anterior do chatbot e o que a IA fez com ele (A16)
  ordem_consumida integer NOT NULL DEFAULT 0,                            -- mensagens_recebida com ordem > isto ainda não foram respondidas (A9)
  estado_conversa jsonb NOT NULL DEFAULT '{"fase": "E0"}',               -- H §2.2/§3.2: máquina E0–E10 + contadores do P7, só códigos/referências, ≤ 2 KB (não é `estado`: este é o ciclo de vida)
  fase text NOT NULL GENERATED ALWAYS AS (estado_conversa ->> 'fase') STORED,   -- no encerramento é a fase final (L: fase_final)
  persona_id text,                                                        -- L: só no dublê/teste (F3)
  sem_avanco smallint NOT NULL DEFAULT 0, corrigiveis smallint NOT NULL DEFAULT 0, contrapropostas smallint NOT NULL DEFAULT 0,  -- contadores do P7 que o SQL do motor lê (L A2/A4); o JSON guarda só os do prompt
  confirmacoes_emitidas smallint NOT NULL DEFAULT 0, confirmacoes_invalidas smallint NOT NULL DEFAULT 0, nota_repasse_tamanho smallint,  -- L A5, G8
  opt_out_em timestamptz, humano_assumiu_em timestamptz, pii_auditoria boolean, sinais_cliente text[] NOT NULL DEFAULT '{}',  -- L G5/G10/§5; pii_auditoria: NULL = não auditado, false = limpo, true = achou PII
  desfecho text, motivo_desfecho text, contexto_codigos text[] NOT NULL DEFAULT '{}',
  turnos integer NOT NULL DEFAULT 0, mensagens_enviadas integer NOT NULL DEFAULT 0, lembretes_enviados integer NOT NULL DEFAULT 0,
  custo_modelo_brl numeric(14,6) NOT NULL DEFAULT 0, custo_midia_brl numeric(14,6) NOT NULL DEFAULT 0,
  repasse_modo text, repasse_consultor_ref text, repasse_nota_enviada boolean,  -- c §3: fila | indicado; o n8n devolve o site_profile_id
  iniciado_em timestamptz NOT NULL DEFAULT now(), encerrado_em timestamptz, atualizado_em timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT atendimento_pk PRIMARY KEY (atendimento_id),
  CONSTRAINT atendimento_idempotente UNIQUE (origem, idempotency_key),
  CONSTRAINT atendimento_pessoa_uq UNIQUE (atendimento_id, pessoa_id),  -- alvo das FKs compostas dos filhos
  CONSTRAINT atendimento_gatilho_check CHECK (gatilho IN ('venda', 'esteira_parada', 'agendamento') AND modo IN ('real', 'sombra', 'duble', 'teste')),
  CONSTRAINT atendimento_estado_check CHECK (estado IN ('reservado', 'aberto', 'aguardando_cliente', 'pausado', 'repassando', 'encerrado')),
  CONSTRAINT atendimento_desfecho_check CHECK (desfecho IS NULL OR desfecho IN ('sem_venda', 'repassado', 'sem_resposta', 'expirado', 'opt_out', 'abortado')
    OR (gatilho IN ('venda', 'agendamento') AND desfecho = 'vendeu') OR (gatilho = 'esteira_parada' AND desfecho IN ('destravou', 'motivo_identificado'))),
  CONSTRAINT atendimento_fim_check CHECK ((estado = 'encerrado') = (desfecho IS NOT NULL) AND (estado = 'encerrado') = (encerrado_em IS NOT NULL)),
  CONSTRAINT atendimento_lease_check CHECK ((estado = 'encerrado') = (lease_ate IS NULL)),
  CONSTRAINT atendimento_assumido_check CHECK ((estado = 'reservado' AND assumido_em IS NULL) OR estado = 'encerrado' OR assumido_em IS NOT NULL),
  CONSTRAINT atendimento_abortado_check CHECK (desfecho IS DISTINCT FROM 'abortado' OR assumido_em IS NULL),
  CONSTRAINT atendimento_sombra_check CHECK (modo <> 'sombra' OR desfecho IS NULL OR desfecho IN ('sem_venda', 'sem_resposta', 'expirado', 'abortado')),  -- sombra: nada saiu
  CONSTRAINT atendimento_repasse_check CHECK ((coalesce(estado = 'repassando' OR desfecho = 'repassado', false)
    OR (repasse_modo IS NULL AND repasse_consultor_ref IS NULL AND repasse_nota_enviada IS NULL)) AND (repasse_modo IS NULL OR repasse_modo IN ('fila', 'indicado'))
    AND (repasse_consultor_ref IS NULL OR repasse_consultor_ref ~ '^[A-Za-z0-9_-]{1,64}$')),
  CONSTRAINT atendimento_chatbot_check CHECK ((chatbot_antes IS NULL OR chatbot_antes IN ('ligado', 'desligado', 'desconhecido'))
    AND chatbot_estado IN ('intocado', 'desligado_pela_ia', 'restaurado', 'nao_confirmou') AND (chatbot_estado = 'intocado' OR chatbot_antes IS NOT NULL)),
  CONSTRAINT atendimento_gatilho_dados_check CHECK ((gatilho = 'esteira_parada' OR status_esteira IS NULL) AND (gatilho <> 'venda' OR criterio_versao IS NOT NULL)
    AND (criterio_versao IS NULL OR criterio_versao ~ '^[A-Za-z0-9_.-]{1,64}$')),
  CONSTRAINT atendimento_numeros_check CHECK (versao >= 1 AND ordem_consumida >= 0 AND roteiro_versao >= 1 AND regras_versao >= 1 AND catalogo_versao >= 1 AND motor_versao >= 1
    AND turnos >= 0 AND mensagens_enviadas >= 0 AND lembretes_enviados >= 0 AND custo_modelo_brl >= 0 AND custo_midia_brl >= 0),
  CONSTRAINT atendimento_escolha_check CHECK ((motivo_escolha IS NULL OR motivo_escolha IN ('mais_antigo_elegivel', 'oferta_forte', 'consultor_sobrecarregado', 'teste', 'outro'))
    AND coalesce(motivo_escolha = 'outro', false) = (motivo_escolha_nota IS NOT NULL) AND (motivo_escolha_nota IS NULL OR char_length(motivo_escolha_nota) BETWEEN 1 AND 80)),
  CONSTRAINT atendimento_conversa_check CHECK (jsonb_typeof(estado_conversa) = 'object' AND octet_length(estado_conversa::text) <= 2048 AND fase ~ '^E([0-9]|10)$'
    AND coalesce(jsonb_typeof(estado_conversa -> 'contadores'), 'object') = 'object' AND NOT jsonb_path_exists(estado_conversa, '$.contadores.* ? (@.type() != "number" || @ < 0)')
    AND ((estado = 'reservado') = (fase = 'E0') OR estado = 'encerrado') AND (estado <> 'repassando' OR fase = 'E10')   -- as duas máquinas não se contradizem
    AND (estado <> 'pausado' OR (fase ~ '^E([2-6]|8)$' AND coalesce((estado_conversa #>> '{pausa,retoma_fase}') = fase, false))) -- pausa nunca em E7; a fase de volta fica gravada em pausa.retoma_fase
    AND CASE WHEN estado = 'encerrado' THEN true WHEN estado = 'pausado' OR (estado = 'reservado' AND gatilho = 'agendamento') THEN retoma_em IS NOT NULL AND lease_ate >= retoma_em ELSE retoma_em IS NULL END),
  CONSTRAINT atendimento_esforco_check CHECK (faixa_esforco IN ('baixa', 'media', 'alta', 'muito_alta') AND (comissao_esperada_brl IS NULL OR comissao_esperada_brl >= 0)
    AND (comissao_esperada_brl IS NOT NULL OR faixa_esforco IN ('baixa', 'media'))),   -- esforço alto (ou modelo melhor) nunca sobre comissão desconhecida
  CONSTRAINT atendimento_qualidade_check CHECK (sem_avanco >= 0 AND corrigiveis >= 0 AND contrapropostas >= 0 AND confirmacoes_emitidas >= 0 AND confirmacoes_invalidas BETWEEN 0 AND confirmacoes_emitidas
    AND (persona_id IS NULL OR (modo IN ('duble', 'teste') AND persona_id ~ '^[A-Za-z0-9_-]{1,40}$')) AND coalesce(repasse_nota_enviada, false) = (nota_repasse_tamanho IS NOT NULL)
    AND (nota_repasse_tamanho IS NULL OR nota_repasse_tamanho BETWEEN 1 AND 400) AND (desfecho IS DISTINCT FROM 'opt_out' OR opt_out_em IS NOT NULL)
    AND (motivo_desfecho IS DISTINCT FROM 'humano_assumiu' OR humano_assumiu_em IS NOT NULL) AND cardinality(sinais_cliente) <= 12
    AND array_to_string(sinais_cliente, ',') ~ '^([a-z0-9_]{1,40}(,[a-z0-9_]{1,40})*)?$'),
  CONSTRAINT atendimento_codigos_check CHECK ((motivo_desfecho IS NULL OR motivo_desfecho ~ '^[a-z0-9_]{1,60}$') AND cardinality(contexto_codigos) <= 10
    AND array_to_string(contexto_codigos, ',') ~ '^([a-z0-9_]{1,40}(,[a-z0-9_]{1,40})*)?$'),
  CONSTRAINT atendimento_entrada_check CHECK (origem ~ '^[a-z0-9_]{1,40}$' AND chave_logica ~ '^[a-z][a-z0-9_]{1,19}:[A-Za-z0-9_.:-]{1,180}$'
    AND idempotency_key = encode(sha256(convert_to(chave_logica, 'UTF8')), 'hex') AND entrada_fingerprint ~ '^[0-9a-f]{64}$'
    AND char_length(disparado_por) BETWEEN 1 AND 128 AND chat_id ~ '^[A-Za-z0-9_-]{1,128}$' AND phone_id ~ '^[A-Za-z0-9_-]{1,64}$'),
  CONSTRAINT atendimento_banco_check CHECK ((banco IS NULL OR banco ~ '^[A-Z0-9_]{1,32}$') AND (produto IS NULL OR produto ~ '^[A-Z0-9_]{1,32}$')
    AND (status_esteira IS NULL OR status_esteira ~ '^[a-z0-9_]{1,60}$') AND jsonb_typeof(perfil) = 'object' AND octet_length(perfil::text) <= 2048));
CREATE UNIQUE INDEX IF NOT EXISTS atendimento_ativo_chat_uq ON ia.atendimento (chat_id) WHERE estado <> 'encerrado';  -- trava por chat NO BANCO (reservado e repassando também trancam)
CREATE INDEX IF NOT EXISTS idx_atendimento_chat ON ia.atendimento (chat_id, iniciado_em DESC); CREATE INDEX IF NOT EXISTS idx_atendimento_pessoa ON ia.atendimento (pessoa_id, iniciado_em DESC);
CREATE INDEX IF NOT EXISTS idx_atendimento_contrato ON ia.atendimento (contrato_id) WHERE contrato_id IS NOT NULL; CREATE INDEX IF NOT EXISTS idx_atendimento_iniciado ON ia.atendimento (iniciado_em);
CREATE INDEX IF NOT EXISTS idx_atendimento_encerrado ON ia.atendimento (encerrado_em) WHERE encerrado_em IS NOT NULL; CREATE INDEX IF NOT EXISTS idx_atendimento_sessao ON ia.atendimento (sessao_id) WHERE sessao_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_atendimento_lease ON ia.atendimento (lease_ate) WHERE estado <> 'encerrado'; CREATE INDEX IF NOT EXISTS idx_atendimento_parado ON ia.atendimento (atualizado_em) WHERE estado <> 'encerrado';  -- reapers
-- Desfecho que mora no gl360 (contrato em 48 h, pago em 14 d), copiado pelo job noturno via cliente360-api.
CREATE TABLE IF NOT EXISTS ia.atendimento_resultado (
  atendimento_id uuid NOT NULL PRIMARY KEY REFERENCES ia.atendimento (atendimento_id), proxima_conferencia_em timestamptz, conferido_em timestamptz, contrato_id bigint, contrato_criado_em timestamptz,
  macro text CHECK (macro IN ('aguardando_pagamento', 'cancelado', 'em_analise', 'estornado', 'pago', 'pendente')), pago_em timestamptz, valor_contratado numeric(14,2) CHECK (valor_contratado >= 0),
  marca_ia boolean, digitador_ator_id bigint);
CREATE INDEX IF NOT EXISTS idx_resultado_fila ON ia.atendimento_resultado (proxima_conferencia_em) WHERE proxima_conferencia_em IS NOT NULL;
-- Confirmação do cliente ligada ao DADO (f §4): o hash cobre {banco, valor, parcela, prazo, tabela, oferta_versao}; os valores em si ficam no gl360.
CREATE TABLE IF NOT EXISTS ia.confirmacao (
  confirmacao_id uuid NOT NULL DEFAULT uuidv7(), atendimento_id uuid NOT NULL,
  tipo text NOT NULL, banco text NOT NULL, oferta_versao integer NOT NULL, valores_hash text NOT NULL, texto_id text NOT NULL,  -- texto gerado por código
  estado text NOT NULL DEFAULT 'pendente', classe_resposta text,
  pergunta_ordem integer NOT NULL, resposta_ordem integer,   -- `ordem` dos passos (a resposta tem de ser POSTERIOR à pergunta)
  criada_em timestamptz NOT NULL DEFAULT now(), expira_em timestamptz NOT NULL DEFAULT now() + interval '30 minutes', respondida_em timestamptz,
  CONSTRAINT confirmacao_pk PRIMARY KEY (confirmacao_id),
  CONSTRAINT confirmacao_atendimento_uq UNIQUE (atendimento_id, confirmacao_id),
  CONSTRAINT confirmacao_atendimento_fk FOREIGN KEY (atendimento_id) REFERENCES ia.atendimento (atendimento_id),
  CONSTRAINT confirmacao_estado_check CHECK (tipo IN ('consulta', 'digitacao', 'fallback') AND estado IN ('pendente', 'aceita', 'recusada', 'expirada', 'invalidada')
    AND (classe_resposta IS NULL OR classe_resposta IN ('sim', 'nao', 'duvida'))),
  CONSTRAINT confirmacao_forma_check CHECK (CASE estado
    WHEN 'pendente' THEN num_nonnulls(classe_resposta, respondida_em, resposta_ordem) = 0
    WHEN 'aceita' THEN classe_resposta = 'sim' AND respondida_em IS NOT NULL AND resposta_ordem > pergunta_ordem
    WHEN 'recusada' THEN classe_resposta = 'nao' AND respondida_em IS NOT NULL AND resposta_ordem > pergunta_ordem
    ELSE true END AND (estado NOT IN ('aceita', 'recusada') OR resposta_ordem IS NOT NULL)),
  CONSTRAINT confirmacao_dados_check CHECK (banco ~ '^[A-Z0-9_]{1,32}$' AND oferta_versao >= 1 AND pergunta_ordem >= 1 AND valores_hash ~ '^[0-9a-f]{64}$'
    AND texto_id ~ '^[a-z0-9_.:-]{1,60}$' AND expira_em > criada_em AND expira_em <= criada_em + interval '60 minutes'));
CREATE UNIQUE INDEX IF NOT EXISTS confirmacao_pendente_uq ON ia.confirmacao (atendimento_id, tipo) WHERE estado = 'pendente';
-- Ledger das ferramentas com efeito (f §Gateway 8): gravado `reservada` ANTES da chamada; idem_key é o trinco. Mutável só por CAS de `estado`.
CREATE TABLE IF NOT EXISTS ia.ferramenta_chamada (
  chamada_id bigint GENERATED ALWAYS AS IDENTITY, atendimento_id uuid NOT NULL, pessoa_id uuid NOT NULL,
  ferramenta text NOT NULL, ferramenta_versao text NOT NULL, classe_efeito text NOT NULL,  -- leitura | leitura_paga | efeito_irreversivel | acao_interna
  chave_logica text NOT NULL, idem_key text NOT NULL,        -- legível (t7:…) e sha256 hex dela; UNIQUE global (t4 não leva o atendimento)
  estado text NOT NULL DEFAULT 'reservada', tentativa_n smallint NOT NULL DEFAULT 1,
  banco text, fallback boolean NOT NULL DEFAULT false, confirmacao_id uuid, args_hash text,
  modo text NOT NULL, simulado boolean GENERATED ALWAYS AS (modo <> 'real') STORED,
  http_bucket text, ref_externa text, resolve_id bigint,     -- resolve_id: a T8 aponta a T7 que ela resolve
  reservada_em timestamptz NOT NULL DEFAULT now(), enviada_em timestamptz, concluida_em timestamptz, latencia_ms integer, custo_brl numeric(14,6),
  CONSTRAINT ferramenta_chamada_pk PRIMARY KEY (chamada_id),
  CONSTRAINT ferramenta_chamada_idem_uq UNIQUE (idem_key),
  CONSTRAINT ferramenta_chamada_atendimento_fk FOREIGN KEY (atendimento_id, pessoa_id) REFERENCES ia.atendimento (atendimento_id, pessoa_id),
  CONSTRAINT ferramenta_chamada_confirmacao_fk FOREIGN KEY (atendimento_id, confirmacao_id) REFERENCES ia.confirmacao (atendimento_id, confirmacao_id),
  CONSTRAINT ferramenta_chamada_resolve_fk FOREIGN KEY (resolve_id) REFERENCES ia.ferramenta_chamada (chamada_id),
  CONSTRAINT ferramenta_chamada_estado_check CHECK (estado IN ('reservada', 'enviada', 'em_andamento', 'ok', 'corrigivel', 'recusa', 'indeterminado', 'transitorio', 'nao_criada')
    AND classe_efeito IN ('leitura', 'leitura_paga', 'efeito_irreversivel', 'acao_interna') AND modo IN ('real', 'sombra', 'duble', 'teste')),
  CONSTRAINT ferramenta_chamada_chave_check CHECK (ferramenta ~ '^[a-z][a-z0-9_]{1,19}$' AND ferramenta_versao ~ '^[0-9]{1,3}[.][0-9]{1,3}[.][0-9]{1,3}$'
    AND chave_logica ~ '^[a-z][a-z0-9_]{1,19}:[A-Za-z0-9_.:-]{1,180}$' AND split_part(chave_logica, ':', 1) = ferramenta
    AND idem_key = encode(sha256(convert_to(chave_logica, 'UTF8')), 'hex')),
  CONSTRAINT ferramenta_chamada_ciclo_check CHECK ((estado IN ('reservada', 'enviada', 'em_andamento')) = (concluida_em IS NULL)
    AND (estado <> 'reservada' OR enviada_em IS NULL) AND (estado NOT IN ('enviada', 'em_andamento') OR enviada_em IS NOT NULL)),
  CONSTRAINT ferramenta_chamada_forma_check CHECK ((ferramenta <> 't7' OR (confirmacao_id IS NOT NULL AND banco IS NOT NULL AND args_hash IS NOT NULL))
    AND (ferramenta = 't8') = (resolve_id IS NOT NULL) AND (banco IS NULL OR banco ~ '^[A-Z0-9_]{1,32}$') AND tentativa_n >= 1
    AND (args_hash IS NULL OR args_hash ~ '^[0-9a-f]{64}$') AND (http_bucket IS NULL OR http_bucket IN ('2xx', '3xx', '4xx', '5xx', 'timeout', 'rede'))
    AND (ref_externa IS NULL OR ref_externa ~ '^[A-Za-z0-9_.-]{1,64}$') AND coalesce(latencia_ms, 0) >= 0 AND coalesce(custo_brl, 0) >= 0));
-- Zero duplicidade na digitação, por construção: 1 T7 viva por (pessoa, banco) em QUALQUER atendimento; 1 T7 viva-ou-ok por (atendimento, banco); tentativa única.
CREATE UNIQUE INDEX IF NOT EXISTS ferramenta_chamada_t7_viva_uq ON ia.ferramenta_chamada (pessoa_id, banco) WHERE ferramenta = 't7' AND estado IN ('reservada', 'enviada', 'em_andamento', 'indeterminado');
CREATE UNIQUE INDEX IF NOT EXISTS ferramenta_chamada_t7_atendimento_uq ON ia.ferramenta_chamada (atendimento_id, banco) WHERE ferramenta = 't7' AND estado IN ('reservada', 'enviada', 'em_andamento', 'indeterminado', 'ok');
CREATE UNIQUE INDEX IF NOT EXISTS ferramenta_chamada_t7_tentativa_uq ON ia.ferramenta_chamada (atendimento_id, banco, tentativa_n) WHERE ferramenta = 't7';
CREATE INDEX IF NOT EXISTS idx_ferramenta_chamada_aberta ON ia.ferramenta_chamada (reservada_em) WHERE concluida_em IS NULL OR estado = 'indeterminado';  -- reaper e T8
-- Agendamento / pausa combinada (M §3): o cliente combina a volta; o texto NÃO mora aqui (só HMAC do texto mascarado; o texto vive 14 d em conversa_cifrada). `entrada` pausa_ia = caso (a), atendimento
-- `pausado`; dialogo_agendar = caso (b), atendimento `reservado` de vida longa (gatilho `agendamento`) que não toca o chat. Máx. 2 por atendimento (seq) e 1 ativo por vez (índice parcial).
CREATE TABLE IF NOT EXISTS ia.agendamento (
  agendamento_id uuid NOT NULL DEFAULT uuidv7(), atendimento_id uuid NOT NULL, pessoa_id uuid NOT NULL, chat_id text NOT NULL, entrada text NOT NULL, seq smallint NOT NULL,
  pedido_em timestamptz NOT NULL DEFAULT now(), msg_chave text NOT NULL, texto_hash text NOT NULL, retoma_fase text,
  horario_extraido timestamptz, tipo_extracao text, extrator_versao text, confianca text, usou_modelo boolean NOT NULL DEFAULT false,   -- o extrator é determinístico; o modelo só escolhe entre candidatos
  proposto_em timestamptz, confirmado_em timestamptz, confirmacao_origem text, dispara_em timestamptz, estado text NOT NULL DEFAULT 'pendente',
  desfecho_disparo text, cancelado_por text, cancelado_em timestamptz, disparado_em timestamptz, job_id bigint,
  chave_logica text NOT NULL, idem_key text NOT NULL, versao integer NOT NULL DEFAULT 1, criado_em timestamptz NOT NULL DEFAULT now(), atualizado_em timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT agendamento_pk PRIMARY KEY (agendamento_id), CONSTRAINT agendamento_atendimento_uq UNIQUE (atendimento_id, agendamento_id),
  CONSTRAINT agendamento_atendimento_fk FOREIGN KEY (atendimento_id, pessoa_id) REFERENCES ia.atendimento (atendimento_id, pessoa_id),
  CONSTRAINT agendamento_seq_uq UNIQUE (atendimento_id, seq), CONSTRAINT agendamento_msg_uq UNIQUE (msg_chave), CONSTRAINT agendamento_idem_uq UNIQUE (idem_key),   -- Post repetido pelo ChatGuru = no-op
  CONSTRAINT agendamento_forma_check CHECK (entrada IN ('pausa_ia', 'dialogo_agendar') AND seq BETWEEN 1 AND 2 AND chat_id ~ '^[A-Za-z0-9_-]{1,128}$' AND texto_hash ~ '^[0-9a-f]{64}$'
    AND msg_chave ~ '^(cg:[A-Za-z0-9]{8,64}:[0-9a-f]{16}|cgid:[A-Za-z0-9_.=-]{1,120}|rpa:[A-Za-z0-9_-]{8,64})$' AND (retoma_fase IS NULL OR retoma_fase ~ '^E([2-6]|8)$') AND (entrada <> 'pausa_ia' OR retoma_fase IS NOT NULL)
    AND (confianca IS NULL OR confianca IN ('alta', 'media', 'baixa')) AND (tipo_extracao IS NULL OR tipo_extracao ~ '^[a-z0-9_]{1,40}$') AND (extrator_versao IS NULL OR extrator_versao ~ '^[A-Za-z0-9_.-]{1,40}$')
    AND (confirmacao_origem IS NULL OR confirmacao_origem IN ('cliente', 'tacita', 'operador')) AND (desfecho_disparo IS NULL OR desfecho_disparo IN ('retomou', 'resolvido', 'reagendado_sistema', 'repassou', 'humano_atuou'))
    AND (cancelado_por IS NULL OR cancelado_por IN ('cliente', 'humano_assumiu', 'operador', 'opt_out', 'reagendado', 'sistema')) AND versao >= 1
    AND chave_logica ~ '^agendar?:[A-Za-z0-9_.:-]{1,180}$' AND idem_key = encode(sha256(convert_to(chave_logica, 'UTF8')), 'hex') AND (dispara_em IS NULL OR dispara_em > pedido_em)),
  CONSTRAINT agendamento_estado_check CHECK (estado IN ('pendente', 'confirmado', 'disparado', 'cancelado', 'expirado') AND CASE estado
    WHEN 'pendente' THEN num_nonnulls(confirmado_em, disparado_em, cancelado_por, desfecho_disparo) = 0
    WHEN 'confirmado' THEN confirmado_em IS NOT NULL AND dispara_em IS NOT NULL AND horario_extraido IS NOT NULL AND confirmacao_origem IS NOT NULL AND num_nonnulls(disparado_em, cancelado_por, desfecho_disparo) = 0
    WHEN 'disparado' THEN confirmado_em IS NOT NULL AND dispara_em IS NOT NULL AND disparado_em IS NOT NULL AND desfecho_disparo IS NOT NULL AND cancelado_por IS NULL
    WHEN 'cancelado' THEN cancelado_por IS NOT NULL AND cancelado_em IS NOT NULL AND disparado_em IS NULL
    ELSE cancelado_por IS NULL AND disparado_em IS NULL END));   -- expirado: pendente que ninguém confirmou
CREATE UNIQUE INDEX IF NOT EXISTS agendamento_ativo_uq ON ia.agendamento (atendimento_id) WHERE estado IN ('pendente', 'confirmado');   -- 1 agendamento ativo por atendimento
CREATE INDEX IF NOT EXISTS idx_agendamento_dispara ON ia.agendamento (dispara_em) WHERE estado = 'confirmado'; CREATE INDEX IF NOT EXISTS idx_agendamento_chat ON ia.agendamento (chat_id, pedido_em DESC);  -- reaper do job `retomar`
-- A linha do tempo. Append-only por privilégio. Texto de passo é montado pelo código; o texto do cliente NÃO entra aqui.
CREATE TABLE IF NOT EXISTS ia.passo (
  passo_id bigint GENERATED ALWAYS AS IDENTITY, atendimento_id uuid NOT NULL, ordem integer NOT NULL,
  ocorrido_em timestamptz NOT NULL DEFAULT now(), tipo text NOT NULL, texto text NOT NULL,
  motor text, motivo text, ferramenta text, ferramenta_versao text, chamada_id bigint, confirmacao_id uuid,  -- chamada_ferramenta → ledger; confirmacao → ia.confirmacao
  agendamento_id uuid,                       -- só tipo `agendamento` (M); resultado = proposto|confirmado|reagendado|cancelado|expirado|disparado|resolvido
  operador text,                             -- só anotacao_operador (J §1): e-mail do operador; resultado = categoria (reclamacao, ajuste, observacao…)
  turno smallint, fase text, tx_id text, intencao text, objecao text, confianca text, acao_invalida boolean NOT NULL DEFAULT false, transversal text,  -- L §2.4: o motor de qualidade lê SÓ isto;
  janela_24h boolean,                        -- ah: só `lembrete`; true = dentro da janela de serviço do WhatsApp, false = template pago (custo_brl obrigatório); a faixa permitir é regra da aplicação (faixas_esforco.lembrete_pago_max)
  faixa_esforco text,                        -- 11c: só em `decisao`, quando a regra do motor usou a faixa (a do atendimento, que é imutável)
  verif_det text[], confirmacao_ref text, invalidacao text, repasse_etapa text, responde_ordem integer,                    -- o que não for gravado desde o MVP não se recupera (texto some em 14 d)
  resultado text, entrega text, peca text, latencia_ms integer, custo_brl numeric(14,6), modelo text, provedor text, tokens_entrada integer, tokens_saida integer, trace_id text,  -- modelo/provedor que respondeu: faixa × modelo (ag)
  msg_chave text, msg_chave_rpa text, msg_fingerprint text, msg_tipo text, msg_tamanho integer, msg_enviada_em timestamptz,  -- só mensagem_recebida (b)
  origem_evento text, fora_de_ordem boolean NOT NULL DEFAULT false,
  verif_momento text, verif_rotulo text, verif_confianca numeric(4,3),
  CONSTRAINT passo_pk PRIMARY KEY (passo_id),
  CONSTRAINT passo_ordem_uq UNIQUE (atendimento_id, ordem),
  CONSTRAINT passo_atendimento_fk FOREIGN KEY (atendimento_id) REFERENCES ia.atendimento (atendimento_id),
  CONSTRAINT passo_chamada_fk FOREIGN KEY (chamada_id) REFERENCES ia.ferramenta_chamada (chamada_id),
  CONSTRAINT passo_confirmacao_fk FOREIGN KEY (atendimento_id, confirmacao_id) REFERENCES ia.confirmacao (atendimento_id, confirmacao_id),
  CONSTRAINT passo_agendamento_fk FOREIGN KEY (atendimento_id, agendamento_id) REFERENCES ia.agendamento (atendimento_id, agendamento_id),
  CONSTRAINT passo_responde_fk FOREIGN KEY (atendimento_id, responde_ordem) REFERENCES ia.passo (atendimento_id, ordem),   -- a mensagem que originou a resposta
  CONSTRAINT passo_tipo_check CHECK (tipo IN ('mensagem_recebida', 'decisao', 'chamada_ferramenta', 'confirmacao', 'resposta_enviada', 'lembrete',
    'encerramento', 'repasse', 'erro', 'verificacao', 'opt_out', 'anotacao_operador', 'agendamento')),
  CONSTRAINT passo_valores_check CHECK (char_length(texto) BETWEEN 1 AND 1000 AND (motivo IS NULL OR char_length(motivo) <= 300) AND motor IN ('regra', 'modelo', 'motor_escolha')
    AND entrega IN ('aceito', 'falhou', 'rascunho') AND trace_id ~ '^[0-9a-f]{32}$' AND coalesce(latencia_ms, 0) >= 0 AND coalesce(custo_brl, 0) >= 0  -- rascunho = sombra
    AND coalesce(tokens_entrada, 0) >= 0 AND coalesce(tokens_saida, 0) >= 0 AND (modelo IS NULL) = (provedor IS NULL) AND (modelo IS NULL OR modelo ~ '^[a-z0-9][a-z0-9._/-]{0,79}$')
    AND (provedor IS NULL OR provedor ~ '^[a-z0-9_-]{1,30}$') AND NOT (tipo = 'decisao' AND motor = 'modelo' AND modelo IS NULL)),   -- decisão do modelo sempre diz qual modelo
  CONSTRAINT passo_msg_forma_check CHECK (
    (tipo = 'mensagem_recebida') = (num_nonnulls(msg_chave, msg_fingerprint, msg_tipo, msg_tamanho, origem_evento) = 5)
    AND (tipo = 'mensagem_recebida' OR (num_nonnulls(msg_chave, msg_chave_rpa, msg_fingerprint, msg_tipo, msg_tamanho, msg_enviada_em, origem_evento) = 0 AND NOT fora_de_ordem))
    AND (msg_tipo IS NULL OR msg_tipo IN ('texto', 'audio', 'imagem', 'documento', 'sticker', 'localizacao', 'outro'))
    AND (origem_evento IS NULL OR origem_evento IN ('webhook', 'reconciliacao', 'replay')) AND (msg_tamanho IS NULL OR msg_tamanho >= 0)
    AND (msg_fingerprint IS NULL OR msg_fingerprint ~ '^[0-9a-f]{64}$') AND (msg_chave_rpa IS NULL OR msg_chave_rpa ~ '^[A-Za-z0-9_-]{8,64}$')
    AND (msg_chave IS NULL OR msg_chave ~ '^(cg:[A-Za-z0-9]{8,64}:[0-9a-f]{16}|cgid:[A-Za-z0-9_.=-]{1,120}|rpa:[A-Za-z0-9_-]{8,64})$')),
  CONSTRAINT passo_turno_check CHECK ((tipo = 'anotacao_operador' OR (turno IS NOT NULL AND turno >= 0 AND fase IS NOT NULL AND fase ~ '^E([0-9]|10)$'))   -- turno e fase sempre (L G6, A1)
    AND (tx_id IS NULL OR (tipo IN ('resposta_enviada', 'lembrete', 'repasse', 'agendamento') AND tx_id ~ '^TX-(M)?[0-9]{2}$')) AND (transversal IS NULL OR transversal ~ '^[a-z0-9_]{1,40}$')   -- tx_id: TX-nn (H) ou TX-Mnn (M); NULL = texto livre do modelo
    AND (responde_ordem IS NULL OR (responde_ordem >= 1 AND responde_ordem < ordem AND tipo <> 'mensagem_recebida'))),
  CONSTRAINT passo_modelo_check CHECK (((tipo = 'decisao' AND motor = 'modelo') = (intencao IS NOT NULL AND confianca IS NOT NULL)) AND (tipo = 'decisao' OR num_nonnulls(intencao, objecao, confianca) = 0)
    AND (objecao IS NULL OR intencao IS NOT NULL) AND (intencao IS NULL OR (intencao ~ '^[a-z0-9_]{1,40}$' AND confianca IN ('alta', 'media', 'baixa')))  -- vocabulário da intenção/objeção: Pydantic (H a marca como hipótese)
    AND (objecao IS NULL OR objecao ~ '^[a-z0-9_]{1,40}$') AND (NOT acao_invalida OR tipo = 'decisao') AND (faixa_esforco IS NULL OR (tipo = 'decisao' AND faixa_esforco IN ('baixa', 'media', 'alta', 'muito_alta')))),
  CONSTRAINT passo_auditoria_check CHECK (((tipo IN ('resposta_enviada', 'lembrete')) = (verif_det IS NOT NULL)) AND cardinality(verif_det) <= 10   -- verif_det: códigos do T15 determinístico, {} = limpo
    AND array_to_string(verif_det, ',') ~ '^([a-z0-9_]{1,40}(,[a-z0-9_]{1,40})*)?$' AND (confirmacao_ref IS NULL OR confirmacao_ref ~ '^[0-9a-f]{16}$')   -- confirmacao_ref: 16 hex do valores_hash
    AND (tipo <> 'confirmacao' OR (confirmacao_ref IS NOT NULL AND resultado IN ('pergunta', 'sim_valido', 'ambiguo', 'recusada', 'expirada', 'invalidada')))
    AND (tipo <> 'chamada_ferramenta' OR ferramenta NOT IN ('t4', 't7') OR confirmacao_ref IS NOT NULL)                                              -- G1: efeito pago só com confirmação
    AND ((tipo = 'confirmacao' AND resultado = 'invalidada') = (invalidacao IS NOT NULL)) AND (invalidacao IS NULL OR invalidacao ~ '^[a-z0-9_]{1,40}$')
    AND ((tipo = 'agendamento') = (agendamento_id IS NOT NULL)) AND (tipo <> 'agendamento' OR resultado IN ('proposto', 'confirmado', 'reagendado', 'cancelado', 'expirado', 'disparado', 'resolvido'))
    AND ((tipo = 'repasse') = (repasse_etapa IS NOT NULL)) AND (repasse_etapa IS NULL OR repasse_etapa IN ('nota', 'chatbot', 'rota', 'marca', 'lease', 'cerco'))),  -- C4 + K (cerco)
  CONSTRAINT passo_janela_check CHECK ((tipo = 'lembrete') = (janela_24h IS NOT NULL) AND (janela_24h IS DISTINCT FROM false OR coalesce(custo_brl, 0) > 0) AND (janela_24h IS DISTINCT FROM true OR coalesce(custo_brl, 0) = 0)),
  CONSTRAINT passo_verificacao_forma_check CHECK ((tipo = 'verificacao') = (num_nonnulls(verif_momento, verif_rotulo, verif_confianca, modelo) = 4)
    AND (tipo = 'verificacao' OR num_nonnulls(verif_momento, verif_rotulo, verif_confianca) = 0)
    AND (verif_momento IS NULL OR verif_momento IN ('entrada', 'saida', 'pre_t7')) AND (verif_confianca IS NULL OR verif_confianca BETWEEN 0 AND 1)),
  CONSTRAINT passo_campos_por_tipo_check CHECK ((tipo = 'decisao') = (motor IS NOT NULL) AND (tipo = 'chamada_ferramenta') = (ferramenta IS NOT NULL)
    AND (ferramenta IS NULL) = (ferramenta_versao IS NULL) AND (ferramenta_versao IS NULL OR ferramenta_versao ~ '^[0-9]{1,3}[.][0-9]{1,3}[.][0-9]{1,3}$')
    AND (chamada_id IS NULL OR tipo = 'chamada_ferramenta') AND (tipo = 'confirmacao') = (confirmacao_id IS NOT NULL)
    AND (tipo = 'erro') = (peca IS NOT NULL) AND (tipo IN ('resposta_enviada', 'lembrete')) = (entrega IS NOT NULL) AND ordem >= 1
    AND (tipo = 'anotacao_operador') = (operador IS NOT NULL) AND (tipo <> 'anotacao_operador' OR (resultado ~ '^[a-z0-9_]{1,40}$' AND char_length(texto) <= 300))));
CREATE UNIQUE INDEX IF NOT EXISTS passo_msg_chave_uq ON ia.passo (msg_chave) WHERE tipo = 'mensagem_recebida';  -- dedupe PERMANENTE (A27)
CREATE UNIQUE INDEX IF NOT EXISTS passo_msg_chave_rpa_uq ON ia.passo (msg_chave_rpa) WHERE msg_chave_rpa IS NOT NULL;  -- o _id do RPA anexado ao evento do webhook
CREATE INDEX IF NOT EXISTS idx_passo_pendentes ON ia.passo (atendimento_id, ordem) WHERE tipo = 'mensagem_recebida'; CREATE INDEX IF NOT EXISTS idx_passo_ocorrido ON ia.passo (ocorrido_em);  -- turno consome ordem > ordem_consumida
-- D17/H §3.4: texto MASCARADO da conversa e o resumo compacto, CIFRADOS NA APLICAÇÃO (AES-256-GCM; AAD = atendimento_id|seq|remetente|tipo|chave_id; chave só na VPS).
-- Lido só pelo runtime. O resumo (H §3.5: após 10 mensagens, sem valores nem nomes) é uma linha tipo='resumo' que cobre as mensagens até cobre_ate_seq; vale o de maior seq.
CREATE TABLE IF NOT EXISTS ia.conversa_cifrada (
  conversa_id bigint GENERATED ALWAYS AS IDENTITY, atendimento_id uuid NOT NULL, seq integer NOT NULL, passo_ordem integer,
  remetente text NOT NULL, tipo text NOT NULL DEFAULT 'mensagem', mascarado boolean NOT NULL DEFAULT true, cobre_ate_seq integer, mensagem_em timestamptz,
  chave_id smallint NOT NULL, nonce bytea NOT NULL, cifra bytea NOT NULL,   -- cifra = texto cifrado + tag GCM de 16 bytes
  criada_em timestamptz NOT NULL DEFAULT now(), apagar_em timestamptz NOT NULL DEFAULT now() + interval '30 days',  -- teto absoluto de vida da linha
  CONSTRAINT conversa_cifrada_pk PRIMARY KEY (conversa_id),
  CONSTRAINT conversa_cifrada_seq_uq UNIQUE (atendimento_id, seq),
  CONSTRAINT conversa_cifrada_atendimento_fk FOREIGN KEY (atendimento_id) REFERENCES ia.atendimento (atendimento_id),
  CONSTRAINT conversa_cifrada_passo_fk FOREIGN KEY (atendimento_id, passo_ordem) REFERENCES ia.passo (atendimento_id, ordem),
  CONSTRAINT conversa_cifrada_forma_check CHECK (seq >= 1 AND remetente IN ('cliente', 'ia') AND tipo IN ('mensagem', 'resumo') AND mascarado AND chave_id > 0
    AND (tipo = 'resumo') = (cobre_ate_seq IS NOT NULL) AND (tipo = 'mensagem' OR (remetente = 'ia' AND passo_ordem IS NULL AND cobre_ate_seq < seq))
    AND octet_length(nonce) = 12 AND octet_length(cifra) BETWEEN 17 AND 20000 AND apagar_em > criada_em AND apagar_em <= criada_em + interval '30 days'));
-- Cofre com prazo (D18, f T6): dados da digitação e o número do chat (necessário para enviar; é PII, por isso aqui e não no atendimento). Mesma cifra.
CREATE TABLE IF NOT EXISTS ia.cofre (
  atendimento_id uuid NOT NULL, finalidade text NOT NULL, chave_id smallint NOT NULL, nonce bytea NOT NULL, cifra bytea NOT NULL,
  criado_em timestamptz NOT NULL DEFAULT now(), expira_em timestamptz NOT NULL DEFAULT now() + interval '7 days',
  CONSTRAINT cofre_pk PRIMARY KEY (atendimento_id, finalidade),
  CONSTRAINT cofre_atendimento_fk FOREIGN KEY (atendimento_id) REFERENCES ia.atendimento (atendimento_id),
  CONSTRAINT cofre_forma_check CHECK (finalidade IN ('canal', 'digitacao') AND chave_id > 0 AND octet_length(nonce) = 12 AND octet_length(cifra) BETWEEN 17 AND 20000
    AND expira_em > criado_em AND expira_em <= criado_em + interval '7 days'));
-- Opt-out LOCAL (D14, f T14): só a IA respeita. Append-only; vale a última linha da pessoa. Sem FK para sobreviver à poda do atendimento.
CREATE TABLE IF NOT EXISTS ia.opt_out (
  opt_out_id bigint GENERATED ALWAYS AS IDENTITY, pessoa_id uuid NOT NULL, atendimento_id uuid,
  tipo text NOT NULL, origem text NOT NULL, chave_logica text NOT NULL, idem_key text NOT NULL,  -- t14:{pessoa}:{tipo}:{msg_chave}
  registrado_em timestamptz NOT NULL DEFAULT now(), registrado_por text NOT NULL,
  CONSTRAINT opt_out_pk PRIMARY KEY (opt_out_id), CONSTRAINT opt_out_idem_uq UNIQUE (idem_key),
  CONSTRAINT opt_out_forma_check CHECK (tipo IN ('opt_out', 'consentimento') AND origem IN ('cliente_mensagem', 'operador', 'importacao')
    AND chave_logica ~ '^t14:[A-Za-z0-9_.:=-]{1,180}$' AND idem_key = encode(sha256(convert_to(chave_logica, 'UTF8')), 'hex')
    AND char_length(registrado_por) BETWEEN 1 AND 128));
CREATE INDEX IF NOT EXISTS idx_opt_out_pessoa ON ia.opt_out (pessoa_id, registrado_em DESC);
-- Seleção do disparo (c §2.3, J §2): TODO lead avaliado na sessão. chat_ref = HMAC do chat_id. `recusa` = 1º critério que reprovou (J §2.1: sem_oferta_facta, origem_fora,
-- idade_fora, humano_atuou, opt_out, contrato_aberto, ja_atendido, acima_alcada, sem_canal, ja_em_atendimento, fora_de_janela) ou recusa do orquestrador (teto_diario, abertos_max…).
CREATE TABLE IF NOT EXISTS ia.candidato (
  candidato_id bigint GENERATED ALWAYS AS IDENTITY, sessao_id uuid NOT NULL, apresentado_em timestamptz NOT NULL DEFAULT now(),
  chat_ref text NOT NULL, criterio_versao text NOT NULL, posicao integer,   -- posicao = ordem FIFO entre os elegíveis (NULL = reprovou); salto = escolhido com elegível mais antigo
  perfil_versao smallint NOT NULL DEFAULT 1, perfil jsonb NOT NULL DEFAULT '{}', escolhido boolean NOT NULL, atendimento_id uuid, recusa text,
  CONSTRAINT candidato_pk PRIMARY KEY (candidato_id), CONSTRAINT candidato_sessao_uq UNIQUE (sessao_id, chat_ref),
  CONSTRAINT candidato_atendimento_fk FOREIGN KEY (atendimento_id) REFERENCES ia.atendimento (atendimento_id),
  CONSTRAINT candidato_forma_check CHECK (chat_ref ~ '^[0-9a-f]{64}$' AND criterio_versao ~ '^[A-Za-z0-9_.-]{1,64}$' AND jsonb_typeof(perfil) = 'object' AND octet_length(perfil::text) <= 2048
    AND (recusa IS NULL OR recusa ~ '^[a-z0-9_]{1,60}$') AND (posicao IS NULL OR posicao >= 1) AND num_nonnulls(atendimento_id, recusa) <= 1
    AND (escolhido OR atendimento_id IS NULL) AND (NOT escolhido OR num_nonnulls(atendimento_id, recusa) = 1)  -- escolhido: virou atendimento OU foi recusado
    AND (escolhido OR recusa IS NOT NULL OR posicao IS NOT NULL) AND (escolhido OR recusa IS NULL OR posicao IS NULL)));  -- elegível tem posição; reprovado não
CREATE INDEX IF NOT EXISTS idx_candidato_apresentado ON ia.candidato (apresentado_em);
-- Motor de qualidade (L §7): só notas e códigos, nunca texto (strings do jsonb ≤ 40 caracteres, por CHECK). Nota nova = linha nova; a antiga permanece. COLUNA = o que o SQL filtra,
-- agrega ou correlaciona (blocos, r1–r5, faixa, custo); JSONB = estrutura que muda por versão e ninguém agrega direto (itens, evidências, pesos, kappa). `qualidade_versao` = o `motor_versao` de L
-- (renomeado: atendimento.motor_versao é o motor de ESCOLHA).
CREATE TABLE IF NOT EXISTS ia.qualidade_motor_versao (
  qualidade_versao integer PRIMARY KEY CHECK (qualidade_versao >= 1), criada_em timestamptz NOT NULL DEFAULT now(), descricao text NOT NULL CHECK (char_length(descricao) BETWEEN 1 AND 500),
  pesos jsonb NOT NULL, faixas jsonb NOT NULL, kappa jsonb, rubrica_hash text, prompt_hash text, juiz_modelo text, juiz_provedor text, aprovado_em timestamptz, aprovado_por text,
  CONSTRAINT qualidade_motor_versao_check CHECK (jsonb_typeof(pesos) = 'object' AND octet_length(pesos::text) <= 8192 AND jsonb_typeof(faixas) = 'object' AND octet_length(faixas::text) <= 2048
    AND (kappa IS NULL OR (jsonb_typeof(kappa) = 'object' AND octet_length(kappa::text) <= 4096)) AND coalesce(rubrica_hash, repeat('0', 64)) ~ '^[0-9a-f]{64}$'
    AND coalesce(prompt_hash, repeat('0', 64)) ~ '^[0-9a-f]{64}$' AND (aprovado_em IS NULL) = (aprovado_por IS NULL)));
CREATE TABLE IF NOT EXISTS ia.qualidade_nota (
  atendimento_id uuid NOT NULL REFERENCES ia.atendimento (atendimento_id), qualidade_versao integer NOT NULL REFERENCES ia.qualidade_motor_versao (qualidade_versao),
  definitiva boolean NOT NULL, calculada_em timestamptz NOT NULL DEFAULT now(), nota smallint NOT NULL, faixa text NOT NULL, portao_falhas text[] NOT NULL DEFAULT '{}',   -- provisória ao encerrar, definitiva em +48 h
  bloco_a numeric(5,2) NOT NULL, bloco_b numeric(5,2) NOT NULL, bloco_c numeric(5,2) NOT NULL, componentes jsonb NOT NULL,    -- {"v":1,"A":{"A1":{"s":1,"p":8}},…}; pesos e faixas NÃO ficam no CHECK (são chute, mudam por versão)
  CONSTRAINT qualidade_nota_pk PRIMARY KEY (atendimento_id, qualidade_versao, definitiva),
  CONSTRAINT qualidade_nota_check CHECK (nota BETWEEN 0 AND 100 AND faixa IN ('A', 'B', 'C', 'D', 'P') AND bloco_a >= 0 AND bloco_b >= 0 AND bloco_c >= 0 AND bloco_a + bloco_b + bloco_c <= 100
    AND (faixa = 'P') = (cardinality(portao_falhas) > 0) AND (faixa <> 'P' OR nota = 0) AND (faixa = 'P' OR abs(nota - (bloco_a + bloco_b + bloco_c)) <= 1)   -- portão reprovado ⇒ nota 0, faixa P
    AND array_to_string(portao_falhas, ',') ~ '^([A-Z][0-9]{1,2}(,[A-Z][0-9]{1,2})*)?$' AND jsonb_typeof(componentes) = 'object' AND octet_length(componentes::text) <= 4096
    AND NOT jsonb_path_exists(componentes, '$.** ? (@.type() == "string" && @ like_regex "^.{41,}$")')));
CREATE INDEX IF NOT EXISTS idx_qualidade_nota_versao ON ia.qualidade_nota (qualidade_versao, faixa);
CREATE TABLE IF NOT EXISTS ia.qualidade_juiz (
  atendimento_id uuid NOT NULL REFERENCES ia.atendimento (atendimento_id), qualidade_versao integer NOT NULL REFERENCES ia.qualidade_motor_versao (qualidade_versao), passe smallint NOT NULL,
  status text NOT NULL, julgado_em timestamptz NOT NULL DEFAULT now(), r1 smallint, r2 smallint, r3 smallint, r4 smallint, r5 smallint,   -- notas 1–5 (NULL = critério fora da nota, «não confiável»)
  nota_juiz numeric(5,2), alerta_conformidade boolean, discord_intencao numeric(4,3), confianca text, sinais text[] NOT NULL DEFAULT '{}',
  detalhe jsonb NOT NULL DEFAULT '{}',      -- evidências (índices de `ordem`), códigos por critério, intenção por mensagem; sem texto
  modelo text, tokens_entrada integer, tokens_saida integer, custo_brl numeric(14,6),   -- custo_qualidade fica FORA de atendimento.custo_modelo_brl
  CONSTRAINT qualidade_juiz_pk PRIMARY KEY (atendimento_id, qualidade_versao, passe),
  CONSTRAINT qualidade_juiz_check CHECK (passe >= 1 AND status IN ('ok', 'juiz_falhou', 'nao_julgado') AND (status = 'ok') = (nota_juiz IS NOT NULL AND alerta_conformidade IS NOT NULL AND modelo IS NOT NULL)
    AND coalesce(nota_juiz, 0) BETWEEN 0 AND 100 AND coalesce(discord_intencao, 0) BETWEEN 0 AND 1 AND (confianca IS NULL OR confianca IN ('alta', 'media', 'baixa'))
    AND coalesce(r1, 1) BETWEEN 1 AND 5 AND coalesce(r2, 1) BETWEEN 1 AND 5 AND coalesce(r3, 1) BETWEEN 1 AND 5 AND coalesce(r4, 1) BETWEEN 1 AND 5 AND coalesce(r5, 1) BETWEEN 1 AND 5
    AND coalesce(tokens_entrada, 0) >= 0 AND coalesce(tokens_saida, 0) >= 0 AND coalesce(custo_brl, 0) >= 0 AND cardinality(sinais) <= 12 AND array_to_string(sinais, ',') ~ '^([a-z0-9_]{1,40}(,[a-z0-9_]{1,40})*)?$'
    AND jsonb_typeof(detalhe) = 'object' AND octet_length(detalhe::text) <= 6144 AND NOT jsonb_path_exists(detalhe, '$.** ? (@.type() == "string" && @ like_regex "^.{41,}$")')));
CREATE TABLE IF NOT EXISTS ia.qualidade_humana (   -- rubrica idêntica à do juiz; comentário humano só em códigos (nunca texto livre: pode ter PII)
  atendimento_id uuid NOT NULL REFERENCES ia.atendimento (atendimento_id), avaliador text NOT NULL, avaliado_em timestamptz NOT NULL DEFAULT now(),
  r1 smallint NOT NULL, r2 smallint NOT NULL, r3 smallint NOT NULL, r4 smallint NOT NULL, r5 smallint NOT NULL, codigos text[] NOT NULL DEFAULT '{}', duplo boolean NOT NULL DEFAULT false, rubrica_hash text NOT NULL,
  CONSTRAINT qualidade_humana_pk PRIMARY KEY (atendimento_id, avaliador),
  CONSTRAINT qualidade_humana_check CHECK (char_length(avaliador) BETWEEN 1 AND 128 AND r1 BETWEEN 1 AND 5 AND r2 BETWEEN 1 AND 5 AND r3 BETWEEN 1 AND 5 AND r4 BETWEEN 1 AND 5 AND r5 BETWEEN 1 AND 5
    AND rubrica_hash ~ '^[0-9a-f]{64}$' AND cardinality(codigos) <= 12 AND array_to_string(codigos, ',') ~ '^([a-z0-9_]{1,40}(,[a-z0-9_]{1,40})*)?$'));
CREATE TABLE IF NOT EXISTS ia.qualidade_amostra (   -- sorteio estratificado e semeado (L §4.2)
  amostra_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, atendimento_id uuid NOT NULL REFERENCES ia.atendimento (atendimento_id), etapa text NOT NULL, estrato text NOT NULL, motivo_amostra text NOT NULL,
  seed bigint NOT NULL, sorteada_em timestamptz NOT NULL DEFAULT now(), CONSTRAINT qualidade_amostra_uq UNIQUE (atendimento_id, etapa),
  CONSTRAINT qualidade_amostra_check CHECK (etapa IN ('A', 'B', 'regime') AND estrato ~ '^[a-z0-9_]{1,60}$' AND motivo_amostra ~ '^[a-z0-9_]{1,60}$'));
-- Prontidão (K §3.3): o que o /readyz da VPS e a vigia da S2 leem; só agregados e ids opacos. Só os ativos entram (usa o índice parcial do chat).
CREATE OR REPLACE VIEW ia.v_prontidao AS   -- abertos = o que a IA atende AGORA: pausados e agendados ficam fora (M: agenda_max_pausados é à parte de max_abertos)
SELECT count(*) FILTER (WHERE a.estado <> 'pausado' AND NOT (a.gatilho = 'agendamento' AND a.estado = 'reservado')) AS abertos, count(*) FILTER (WHERE a.estado = 'reservado' AND a.gatilho <> 'agendamento') AS reservados,
  count(*) FILTER (WHERE a.estado = 'repassando') AS repassando, count(*) FILTER (WHERE a.estado = 'pausado') AS pausados, count(*) FILTER (WHERE a.estado = 'reservado' AND a.gatilho = 'agendamento') AS agendados,
  min(a.iniciado_em) FILTER (WHERE a.estado <> 'pausado' AND NOT (a.gatilho = 'agendamento' AND a.estado = 'reservado')) AS mais_velho_em, min(a.retoma_em) AS proxima_retomada_em,
  count(*) FILTER (WHERE a.lease_ate < now() AND a.estado <> 'pausado' AND NOT (a.gatilho = 'agendamento' AND a.estado = 'reservado')) AS lease_vencidos,
  coalesce(array_agg(a.chat_id ORDER BY a.chat_id) FILTER (WHERE a.estado = 'repassando' AND a.atualizado_em < now() - interval '10 minutes'), '{}') AS repassando_ha_10min,
  (SELECT c.valor #>> '{}' FROM ia.config_versao c WHERE c.nome = 'modo' ORDER BY c.versao DESC LIMIT 1) AS modo,
  (SELECT (c.valor)::boolean FROM ia.config_versao c WHERE c.nome = 'ia_ativa' ORDER BY c.versao DESC LIMIT 1) AS ia_ativa, now() AS lido_em
FROM ia.atendimento a WHERE a.estado <> 'encerrado';
-- Retenção, sem trigger e sem DELETE no runtime. (1) Tudo 365 d após encerrado_em, filhos primeiro (opt_out NUNCA: é a lista de supressão).
CREATE OR REPLACE FUNCTION ia.fn_atendimento_podar(p_dias integer DEFAULT 365, p_lote integer DEFAULT 500)
RETURNS TABLE (atendimentos bigint, passos bigint) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, ia AS $fn$
DECLARE v_ids uuid[]; v_passos bigint;
BEGIN
  IF p_dias IS NULL OR p_dias < 365 OR p_lote IS NULL OR p_lote NOT BETWEEN 1 AND 5000 THEN RAISE EXCEPTION 'ia.fn_atendimento_podar: p_dias = % (mínimo 365), p_lote = % (1 a 5000)', p_dias, p_lote; END IF;
  SELECT coalesce(array_agg(s.atendimento_id), '{}') INTO v_ids FROM (SELECT a.atendimento_id FROM ia.atendimento a
    WHERE a.estado = 'encerrado' AND a.encerrado_em < now() - make_interval(days => p_dias) ORDER BY a.encerrado_em LIMIT p_lote FOR UPDATE SKIP LOCKED) s;
  DELETE FROM ia.qualidade_nota WHERE atendimento_id = ANY (v_ids); DELETE FROM ia.qualidade_juiz WHERE atendimento_id = ANY (v_ids);
  DELETE FROM ia.qualidade_humana WHERE atendimento_id = ANY (v_ids); DELETE FROM ia.qualidade_amostra WHERE atendimento_id = ANY (v_ids);
  DELETE FROM ia.conversa_cifrada WHERE atendimento_id = ANY (v_ids); DELETE FROM ia.cofre WHERE atendimento_id = ANY (v_ids);
  DELETE FROM ia.candidato WHERE atendimento_id = ANY (v_ids) OR apresentado_em < now() - make_interval(days => p_dias);
  DELETE FROM ia.passo WHERE atendimento_id = ANY (v_ids); GET DIAGNOSTICS v_passos = ROW_COUNT; DELETE FROM ia.agendamento WHERE atendimento_id = ANY (v_ids);
  DELETE FROM ia.ferramenta_chamada WHERE atendimento_id = ANY (v_ids); DELETE FROM ia.confirmacao WHERE atendimento_id = ANY (v_ids);
  DELETE FROM ia.atendimento_resultado WHERE atendimento_id = ANY (v_ids); DELETE FROM ia.atendimento WHERE atendimento_id = ANY (v_ids);
  RETURN QUERY SELECT cardinality(v_ids)::bigint, v_passos;
END $fn$;
-- (2) Texto: conversa 14 d após o encerramento (D17: teto 14 = a promessa, piso 7 = não apagar cedo), cofre 1 d; teto absoluto por linha (apagar_em, expira_em).
CREATE OR REPLACE FUNCTION ia.fn_texto_podar(p_dias_conversa integer DEFAULT 14, p_dias_cofre integer DEFAULT 1, p_lote integer DEFAULT 5000)
RETURNS TABLE (linhas_conversa bigint, linhas_cofre bigint) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, ia AS $fn$
DECLARE v_conv bigint; v_cofre bigint;
BEGIN
  IF p_dias_conversa IS NULL OR p_dias_conversa NOT BETWEEN 7 AND 14 OR p_dias_cofre IS NULL OR p_dias_cofre NOT BETWEEN 1 AND 7 OR p_lote IS NULL OR p_lote NOT BETWEEN 1 AND 50000 THEN
    RAISE EXCEPTION 'ia.fn_texto_podar: p_dias_conversa = % (7 a 14), p_dias_cofre = % (1 a 7), p_lote = % (1 a 50000)', p_dias_conversa, p_dias_cofre, p_lote; END IF;
  WITH v AS (SELECT c.conversa_id FROM ia.conversa_cifrada c WHERE c.apagar_em < now() OR EXISTS (SELECT 1 FROM ia.atendimento a
      WHERE a.atendimento_id = c.atendimento_id AND a.estado = 'encerrado' AND a.encerrado_em < now() - make_interval(days => p_dias_conversa)) LIMIT p_lote)
  DELETE FROM ia.conversa_cifrada WHERE conversa_id IN (SELECT conversa_id FROM v); GET DIAGNOSTICS v_conv = ROW_COUNT;
  WITH v AS (SELECT k.atendimento_id, k.finalidade FROM ia.cofre k WHERE k.expira_em < now() OR EXISTS (SELECT 1 FROM ia.atendimento a
      WHERE a.atendimento_id = k.atendimento_id AND a.estado = 'encerrado' AND a.encerrado_em < now() - make_interval(days => p_dias_cofre)) LIMIT p_lote)
  DELETE FROM ia.cofre k USING v WHERE k.atendimento_id = v.atendimento_id AND k.finalidade = v.finalidade; GET DIAGNOSTICS v_cofre = ROW_COUNT;
  RETURN QUERY SELECT v_conv, v_cofre;
END $fn$;
-- Privilégios nominais. ia_app: sem DDL, sem DELETE (a poda é função), UPDATE de atendimento só nas colunas mutáveis. ia_leitura: sem texto cifrado nem cofre.
GRANT USAGE ON SCHEMA ia, procrastinate TO ia_app; GRANT USAGE ON SCHEMA ia TO ia_leitura, ia_qualidade; GRANT SELECT ON ia.migracao, ia.v_prontidao TO ia_app;
GRANT SELECT, INSERT ON ia.atendimento, ia.passo, ia.artefato_versao, ia.config_versao, ia.conversa_cifrada, ia.opt_out, ia.candidato TO ia_app;
GRANT SELECT, INSERT, UPDATE ON ia.atendimento_resultado, ia.confirmacao, ia.ferramenta_chamada, ia.cofre, ia.agendamento TO ia_app;
GRANT UPDATE (retoma_em, sem_avanco, corrigiveis, contrapropostas, confirmacoes_emitidas, confirmacoes_invalidas, nota_repasse_tamanho, opt_out_em, humano_assumiu_em, pii_auditoria, sinais_cliente,
  estado, estado_conversa, versao, lease_ate, assumido_em, responsavel_antes, chatbot_antes, chatbot_estado, ordem_consumida, desfecho, motivo_desfecho, contexto_codigos, turnos,
  mensagens_enviadas, lembretes_enviados, custo_modelo_brl, custo_midia_brl, repasse_modo, repasse_consultor_ref, repasse_nota_enviada, contrato_id, encerrado_em, atualizado_em) ON ia.atendimento TO ia_app;
GRANT EXECUTE ON FUNCTION ia.fn_atendimento_podar(integer, integer), ia.fn_texto_podar(integer, integer, integer) TO ia_app;
GRANT SELECT ON ia.atendimento, ia.atendimento_resultado, ia.passo, ia.artefato_versao, ia.config_versao, ia.ferramenta_chamada, ia.confirmacao, ia.opt_out, ia.candidato, ia.agendamento, ia.v_prontidao, ia.qualidade_motor_versao, ia.qualidade_nota, ia.qualidade_juiz TO ia_leitura;  -- notas sim; texto, cofre e avaliação humana nunca
-- ia_qualidade (L §7): lê a linha do tempo (sem texto cifrado; a camada 2 ganha esse SELECT numa migração própria) e só ESCREVE em qualidade_*, sem UPDATE/DELETE/DDL.
GRANT SELECT ON ia.atendimento, ia.atendimento_resultado, ia.passo, ia.confirmacao, ia.ferramenta_chamada, ia.config_versao, ia.artefato_versao TO ia_qualidade;
GRANT SELECT, INSERT ON ia.qualidade_motor_versao, ia.qualidade_nota, ia.qualidade_juiz, ia.qualidade_humana, ia.qualidade_amostra TO ia_qualidade;
-- Varredura de ACL: a migração FALHA se PUBLIC tem algo em ia, ou se o leitor alcança o texto cifrado ou o cofre.
DO $acl$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace, LATERAL aclexplode(c.relacl) x WHERE n.nspname = 'ia' AND c.relkind IN ('r', 'S', 'v') AND x.grantee = 0)
    THEN RAISE EXCEPTION 'ACL: PUBLIC tem privilégio em ia.*'; END IF;
  IF has_table_privilege('ia_leitura', 'ia.conversa_cifrada', 'SELECT') OR has_table_privilege('ia_leitura', 'ia.cofre', 'SELECT') OR has_table_privilege('ia_leitura', 'ia.qualidade_humana', 'SELECT')
    OR has_table_privilege('ia_qualidade', 'ia.conversa_cifrada', 'SELECT') OR has_table_privilege('ia_qualidade', 'ia.cofre', 'SELECT') THEN RAISE EXCEPTION 'ACL: leitor alcança texto cifrado, cofre ou avaliação humana'; END IF;
END $acl$;
RESET lock_timeout; RESET ROLE;
