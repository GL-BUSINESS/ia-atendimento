-- 0004_anexo_rpa_e_espelho.up.sql · API de entrada (B1.5): pendências D5 e D6 do contrato 08 §11. ADITIVA: não altera a 0001 nem a 0003. Ainda não aplicada em lugar nenhum.
-- Aplicar como s4_super (psql -1 -v ON_ERROR_STOP=1) junto com a linha do ledger, como a 0001/0002/0003 (migrations/README.md). NÃO reaplicar: o ledger impede
-- (a PK de `ia.migracao` recusa a segunda linha e a transação única desfaz o arquivo junto). Desfazer: o código antigo ignora a função e a tabela; nada é apagado.
-- À mão (só com o «sim» do dono): DROP TABLE ia.espelho_evento; DROP FUNCTION ia.fn_anexar_rpa(bigint, text).
SET ROLE ia_owner; SET lock_timeout = '3s';
-- D5: anexar o `_id` do RPA ao passo `mensagem_recebida` do webhook. `passo` é append-only para `ia_app` (0001: sem UPDATE), então a única escrita
-- permitida é esta função: SECURITY DEFINER, dono `ia_owner` (criada sob SET ROLE, dono da tabela e do UPDATE), search_path fixo, só EXECUTE para `ia_app`.
-- Escreve UMA coluna, só em passo de mensagem recebida que ainda não tem contraparte e que não nasceu do RPA, e nunca com id NULL; devolve se anexou.
CREATE OR REPLACE FUNCTION ia.fn_anexar_rpa(p_passo_id bigint, p_rpa text) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, ia AS $fn$
DECLARE v_n integer;
BEGIN
  UPDATE ia.passo SET msg_chave_rpa = p_rpa
   WHERE passo_id = p_passo_id AND tipo = 'mensagem_recebida' AND msg_chave_rpa IS NULL AND msg_chave NOT LIKE 'rpa:%' AND p_rpa IS NOT NULL;
  GET DIAGNOSTICS v_n = ROW_COUNT; RETURN v_n = 1;
END $fn$;
REVOKE ALL ON FUNCTION ia.fn_anexar_rpa(bigint, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ia.fn_anexar_rpa(bigint, text) TO ia_app;
-- D6: outbox do espelho (eventos `assumiu|pausou|retomou|encerrou` para a S2), escrita na mesma transação da mudança de estado. `seq` é por atendimento.
-- Só códigos, como a 0001 (revisão 1, R1-12): `chave` é a chave lógica; `detalhe` é um objeto de até 512 bytes com SÓ as quatro chaves do contrato
-- (chatbot_antes, retoma_em, encerrado_em, desfecho) e valores curtos sem espaço (nada de texto livre nem PII); `resultado` é o enum do 04 e só existe
-- depois do envio. A poda do atendimento leva as linhas junto (FK em cascata).
CREATE TABLE IF NOT EXISTS ia.espelho_evento (
  atendimento_id uuid NOT NULL REFERENCES ia.atendimento(atendimento_id) ON DELETE CASCADE,
  seq integer NOT NULL CHECK (seq >= 1),
  evento text NOT NULL CHECK (evento IN ('assumiu','pausou','retomou','encerrou')),
  chave text NOT NULL,
  detalhe jsonb NOT NULL DEFAULT '{}'::jsonb,                  -- chatbot_antes, retoma_em, encerrado_em, desfecho: sem PII
  criado_em timestamptz NOT NULL DEFAULT now(), proxima_em timestamptz NOT NULL DEFAULT now(),
  tentativas integer NOT NULL DEFAULT 0, enviado_em timestamptz, resultado text,
  PRIMARY KEY (atendimento_id, seq),
  CONSTRAINT espelho_evento_chave_check CHECK (chave ~ '^(venda|agendar):[A-Za-z0-9_.:-]{1,180}$'),
  CONSTRAINT espelho_evento_detalhe_check CHECK (jsonb_typeof(detalhe) = 'object' AND octet_length(detalhe::text) <= 512
    AND NOT jsonb_path_exists(detalhe, '$.keyvalue() ? (!(@.key like_regex "^(chatbot_antes|retoma_em|encerrado_em|desfecho)$" && @.value.type() == "string" && @.value like_regex "^[A-Za-z0-9_.:+-]{1,64}$"))')),
  CONSTRAINT espelho_evento_resultado_check CHECK (resultado IS NULL OR resultado IN ('aplicado','obsoleto','desconhecido','impedido')),
  CONSTRAINT espelho_evento_tentativas_check CHECK (tentativas >= 0),
  CONSTRAINT espelho_evento_enviado_check CHECK ((enviado_em IS NULL) = (resultado IS NULL)));
CREATE INDEX IF NOT EXISTS idx_espelho_evento_pendente ON ia.espelho_evento (proxima_em) WHERE enviado_em IS NULL;
GRANT SELECT, INSERT ON ia.espelho_evento TO ia_app;
GRANT UPDATE (proxima_em, tentativas, enviado_em, resultado) ON ia.espelho_evento TO ia_app;
RESET lock_timeout; RESET ROLE;
