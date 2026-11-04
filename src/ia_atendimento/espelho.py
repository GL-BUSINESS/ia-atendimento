"""Outbox do espelho (`ia.espelho_evento`, contrato 08 §7.3): o evento nasce NA MESMA transação da mudança de estado do atendimento.

`seq` = `max(seq) + 1` por atendimento, serializado pela linha do atendimento (quem chama já fez o CAS de `versao` nela, ou a trava aqui).
Só atendimentos com linha no espelho (origem `n8n_braco`) emitem; os de origem `ti` não têm o que fechar na S2. O publicador
(`publicar_espelho`, B1.6b) lê a tabela em ordem de `seq`; aqui só se escreve. Sem PII: `detalhe` leva códigos e instantes.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Final, Literal

import psycopg
from psycopg.types.json import Jsonb

Evento = Literal["assumiu", "pausou", "retomou", "encerrou"]
# desfecho do `encerrou` (08 §7.3, 01 §4.2): o vocabulário do espelho, não o `atendimento.desfecho`
DesfechoEspelho = Literal["repassado", "sem_venda", "vendeu", "abortar", "opt_out", "ia_desligada", "devolvido_pela_s2", "expirar_parados"]
ORIGENS_COM_ESPELHO: Final = frozenset({"n8n_braco"})


def emitir(conn: psycopg.Connection, atendimento_id: uuid.UUID, evento: Evento, detalhe: dict[str, Any]) -> int | None:
    """Grava o evento na transação de quem chama (exige transação aberta). Devolve o `seq`, ou None se a origem não tem espelho."""
    if conn.info.transaction_status != psycopg.pq.TransactionStatus.INTRANS:
        raise RuntimeError("o evento do espelho nasce na transação da mudança de estado")
    linha = conn.execute(
        "SELECT origem, chave_logica FROM ia.atendimento WHERE atendimento_id = %s FOR UPDATE", (atendimento_id,)
    ).fetchone()
    if linha is None or linha[0] not in ORIGENS_COM_ESPELHO:
        return None
    seq = conn.execute(
        "INSERT INTO ia.espelho_evento (atendimento_id, seq, evento, chave, detalhe)"
        " SELECT %s, coalesce(max(seq), 0) + 1, %s, %s, %s FROM ia.espelho_evento WHERE atendimento_id = %s RETURNING seq",
        (atendimento_id, evento, linha[1], Jsonb(detalhe), atendimento_id),
    ).fetchone()[0]
    return int(seq)


def emitir_encerrou(conn: psycopg.Connection, atendimento_id: uuid.UUID, desfecho: DesfechoEspelho, encerrado_em: datetime) -> int | None:
    return emitir(conn, atendimento_id, "encerrou", {"desfecho": desfecho, "encerrado_em": encerrado_em.isoformat()})
