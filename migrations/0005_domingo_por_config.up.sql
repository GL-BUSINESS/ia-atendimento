-- 0005_domingo_por_config.up.sql · domingo por config (D-18, B1.8; estudos/ESTUDO-D18-domingo.md §1.2). Só DDL. Não altera a 0001 (sha travado):
-- troca o `config_versao_valor_check` por uma cópia do CASE da 0001 com UM termo a menos (o `NOT jsonb_path_exists(valor, '$.dias."7"')` de
-- `janela_mensagem`). O limite 08:00–20:00 segue no CHECK para os 7 dias; as outras chaves seguem validadas igual; os seeds não mudam
-- (`calendario_bloqueio.domingos=true` e `janela_mensagem` seg–sáb): domingo continua FECHADO por padrão. O código (`calendario.py`) só abre o
-- domingo com as duas chaves juntas: `calendario_bloqueio.domingos=false` E `janela_mensagem.dias."7"`. Ainda não aplicada em lugar nenhum.
-- Tem `DROP CONSTRAINT`: na S4 só por A4.6, com «sim» nomeado do dono (PD-2). Aplicar como s4_super (psql -1 -v ON_ERROR_STOP=1) junto com a
-- linha do ledger (migrations/README.md). DROP e ADD vão no MESMO `ALTER TABLE`, na mesma transação: não existe instante sem o CHECK.
-- NÃO reaplicar: o ledger impede. Desfazer (só com «sim» do dono e sem nenhuma `janela_mensagem` vigente com o dia 7): uma 0006 que volte o termo.
SET ROLE ia_owner; SET lock_timeout = '3s';
ALTER TABLE ia.config_versao DROP CONSTRAINT config_versao_valor_check,
  ADD CONSTRAINT config_versao_valor_check CHECK (CASE
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
      AND (nome <> 'janela_mensagem' OR NOT jsonb_path_exists(valor, '$.dias.* ? (!(@.inicio >= "08:00" && @.fim <= "20:00"))'))   -- janela_mensagem: 08–20 nos 7 dias, NUNCA ultrapassada (0005: o dia 7 deixa de ser recusado; D-18)
    WHEN nome = 'esforco_por_periodo' THEN jsonb_typeof(valor) = 'object' AND octet_length(valor::text) <= 2048   -- ai: faixa × período → multiplicador (o efetivo nunca passa do teto global)
      AND coalesce(valor ?& ARRAY['baixa', 'media', 'alta', 'muito_alta'] AND (valor - ARRAY['baixa', 'media', 'alta', 'muito_alta']) = '{}'::jsonb, false)
      AND NOT jsonb_path_exists(valor, '$.* ? (!(exists(@.comercial) && exists(@.fora)))') AND NOT jsonb_path_exists(valor, '$.*.keyvalue() ? (@.key != "comercial" && @.key != "fora")')
      AND NOT jsonb_path_exists(valor, '$.*.* ? (!(@.espera >= 0 && @.espera <= 2 && @.lembretes >= 0 && @.lembretes <= 2 && @.contrapropostas >= 0 && @.contrapropostas <= 2))')
    WHEN nome = 'modelo_por_faixa' THEN jsonb_typeof(valor) = 'object' AND octet_length(valor::text) <= 2048   -- ag: faixa → modelo; só deepseek-* ou gemini-*, nunca outra família
      AND coalesce(valor ?& ARRAY['baixa', 'media', 'alta', 'muito_alta'] AND (valor - ARRAY['baixa', 'media', 'alta', 'muito_alta']) = '{}'::jsonb, false)
      AND NOT jsonb_path_exists(valor, '$.* ? (!(@.modelo like_regex "^(deepseek|gemini)-[a-z0-9][a-z0-9._-]{0,59}$" && @.provedor like_regex "^[a-z0-9_-]{1,30}$" && @.raciocinio.type() == "boolean"
        && @.custo_max_brl > 0 && @.custo_max_brl <= 3))')
    WHEN nome IN ('ia_ativa', 'verificador_ativo', 'agenda_ativa', 'agenda_b_digita', 'bloqueio_entrada') THEN jsonb_typeof(valor) = 'boolean'
    ELSE true END);
RESET lock_timeout; RESET ROLE;
