-- 0003_estado_aditivo.up.sql · ciclo de vida do atendimento (B1.1): pendências D1, D2 e D3 do contrato 08 §8. ADITIVA: não altera a 0001. Ainda não aplicada em lugar nenhum (pôde mudar na revisão 1).
-- Aplicar como s4_super (psql -1 -v ON_ERROR_STOP=1) junto com a linha do ledger, como a 0001/0002 (migrations/README.md). NÃO reaplicar: o ledger impede
-- (ADD CONSTRAINT não é idempotente). Desfazer: o código antigo ignora a coluna e os CHECKs só recusam o que o contrato já recusa; nada é apagado.
-- À mão (só com o «sim» do dono): DROP TRIGGER atendimento_terminal_absorvente ON ia.atendimento; DROP FUNCTION ia.fn_atendimento_terminal();
-- ALTER TABLE ia.atendimento DROP CONSTRAINT atendimento_fase_estado_check, DROP CONSTRAINT atendimento_chat_id_hex_check;
-- ALTER TABLE ia.config_versao DROP CONSTRAINT config_versao_chats_teste_check.
SET ROLE ia_owner; SET lock_timeout = '3s';
-- D1: última mensagem do cliente (janela de 24 h do WhatsApp, `agenda_teto_horas`). NULL = desconhecido. Coluna com GRANT próprio: o evento da
-- mensagem escreve nela sem disputar o CAS de `versao` com o processador do turno (ela nunca entra no UPDATE com `versao`).
ALTER TABLE ia.atendimento ADD COLUMN IF NOT EXISTS ultimo_cliente_em timestamptz;
GRANT UPDATE (ultimo_cliente_em) ON ia.atendimento TO ia_app;
-- D2: `chats_teste` ≤ 20 ids de 24 hex minúsculo (a 0001 aceita até 50 de `[A-Za-z0-9_-]{1,128}`; os dois CHECKs valem juntos, vence o mais estreito).
ALTER TABLE ia.config_versao ADD CONSTRAINT config_versao_chats_teste_check CHECK (CASE WHEN nome = 'chats_teste'
  THEN jsonb_typeof(valor) = 'array' AND jsonb_array_length(valor) <= 20
    AND NOT jsonb_path_exists(valor, '$[*] ? (!(@.type() == "string" && @ like_regex "^[0-9a-f]{24}$"))')
  ELSE true END);
-- D3: `chat_id` de 24 hex minúsculo. A 0001 aceita `_` e `-`, mas `passo.msg_chave` (`cg:[A-Za-z0-9]{8,64}:…`) não: um chat assim entraria
-- e estouraria o CHECK da 1ª mensagem. Fecha na porta.
ALTER TABLE ia.atendimento ADD CONSTRAINT atendimento_chat_id_hex_check CHECK (chat_id ~ '^[0-9a-f]{24}$');
-- Revisão 1 (A1) e 2 (R4): `encerrado` é terminal TAMBÉM no banco. Quem muda estado, desfecho, encerrado_em, estado_conversa (a `fase` gerada é a
-- fase final), motivo_desfecho, contexto_codigos ou repasse_modo/consultor_ref de um encerrado (ia_app por SQL direto incluso) leva check_violation
-- com o nome da restrição. Seguem graváveis depois do fim: contrato_id, pii_auditoria, sinais_cliente, ultimo_cliente_em e os contadores.
CREATE OR REPLACE FUNCTION ia.fn_atendimento_terminal() RETURNS trigger LANGUAGE plpgsql AS $f$
BEGIN
  RAISE EXCEPTION 'atendimento encerrado é terminal' USING ERRCODE = 'check_violation', CONSTRAINT = 'atendimento_terminal_absorvente';
END $f$;
CREATE TRIGGER atendimento_terminal_absorvente BEFORE UPDATE ON ia.atendimento FOR EACH ROW
  WHEN (OLD.estado = 'encerrado' AND (NEW.estado IS DISTINCT FROM OLD.estado OR NEW.desfecho IS DISTINCT FROM OLD.desfecho
    OR NEW.encerrado_em IS DISTINCT FROM OLD.encerrado_em OR NEW.estado_conversa IS DISTINCT FROM OLD.estado_conversa
    OR NEW.motivo_desfecho IS DISTINCT FROM OLD.motivo_desfecho OR NEW.contexto_codigos IS DISTINCT FROM OLD.contexto_codigos
    OR NEW.repasse_modo IS DISTINCT FROM OLD.repasse_modo OR NEW.repasse_consultor_ref IS DISTINCT FROM OLD.repasse_consultor_ref))
  EXECUTE FUNCTION ia.fn_atendimento_terminal();
-- Revisão 1 (B4): enquanto o atendimento conversa (`aberto`/`aguardando_cliente`) a fase é E1..E9 (E0 é do reservado, E10 do repassando) e a chave
-- `pausa` só existe em `pausado`. Os outros estados ficam como a 0001 já os cruza.
ALTER TABLE ia.atendimento ADD CONSTRAINT atendimento_fase_estado_check
  CHECK (estado NOT IN ('aberto', 'aguardando_cliente') OR (fase ~ '^E[1-9]$' AND NOT (estado_conversa ? 'pausa')));
RESET lock_timeout; RESET ROLE;
