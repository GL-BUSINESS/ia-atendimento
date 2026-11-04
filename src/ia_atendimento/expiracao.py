"""`expirar_parados` (B1.6a; sp01 Task 5; gate 3 de DECISOES-B5.7b): encerra `expirado` quem passou do `dias_max` da faixa.

- Só `jobs.ESTADOS_EXPIRAVEIS` (`aberto`, `aguardando_cliente`). `pausado`, o `reservado` de agendamento e `repassando` têm donos próprios
  (volta, lease, repasse, parada leve manual).
- O prazo é o `dias_max` da faixa na versão de `faixas_esforco` vigente em `iniciado_em` (`espera.limites_da_faixa`), nunca acima de 7 dias.
- Chat com job do chat em curso (`doing`/`todo`, `lock=chat:`) fica para a próxima rodada: não se disputa o atendimento com um turno.
- Cada encerramento é um CAS de `versao` sob `FOR UPDATE` com o `encerrou` (`desfecho=expirar_parados`) no outbox, na mesma transação.
  Perdeu o CAS ou o estado mudou no meio: pula (o próximo tick reavalia).
- **Não devolve o chat**: em 1 a 7 dias o lease já venceu e o `reaper_lease` repassou; o que sobra aqui é rede de segurança (o lead que
  ninguém tocou). O `encerrou` fecha a linha do espelho, e a vigia da S2 devolve o lead pela regra de prazo se ainda for preciso.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Final

import psycopg

from ia_atendimento import espelho, estado
from ia_atendimento.chave import config_em
from ia_atendimento.espera import TETO_DIAS, limites_de
from ia_atendimento.estado_erros import EstadoErro
from ia_atendimento.jobs import ESTADOS_EXPIRAVEIS, LIMITE_LOTE, Servicos

MOTIVO: Final = "expirar_parados"
PISO_DIAS: Final = 1  # menor `dias_max` que o registro aceita
LIMITE_CANDIDATOS: Final = 1000

_SQL_CANDIDATOS: Final = """
SELECT a.atendimento_id, a.faixa_esforco, a.iniciado_em FROM ia.atendimento a
WHERE a.estado = ANY(%(estados)s) AND a.iniciado_em < %(piso)s
  AND NOT EXISTS (SELECT 1 FROM procrastinate.procrastinate_jobs j WHERE j.lock = 'chat:' || a.chat_id AND j.status IN ('doing', 'todo'))
ORDER BY a.iniciado_em LIMIT %(limite)s
"""


def vencidos(conn: psycopg.Connection, agora: datetime, limite: int = LIMITE_LOTE) -> list[uuid.UUID]:
    """Atendimentos expiráveis cujo `iniciado_em + dias_max` (da faixa, na versão de `iniciado_em`) já passou."""
    params = {"estados": list(ESTADOS_EXPIRAVEIS), "piso": agora - timedelta(days=PISO_DIAS), "limite": LIMITE_CANDIDATOS}
    achados: list[uuid.UUID] = []
    for atd, faixa, iniciado_em in conn.execute(_SQL_CANDIDATOS, params).fetchall():
        dias = min(TETO_DIAS, limites_de(config_em(conn, "faixas_esforco", iniciado_em), faixa).dias_max)
        if agora - iniciado_em > timedelta(days=dias):
            achados.append(atd)
        if len(achados) >= limite:
            break
    return achados


def expirar_um(conn: psycopg.Connection, atendimento_id: uuid.UUID, agora: datetime) -> bool:
    """`encerrar(expirado)` + `encerrou` numa transação. False se o atendimento saiu dos expiráveis ou perdeu o CAS no meio."""
    try:
        with conn.transaction():
            linha = conn.execute(
                "SELECT estado, versao FROM ia.atendimento WHERE atendimento_id = %s FOR UPDATE", (atendimento_id,)
            ).fetchone()
            if linha is None or linha[0] not in ESTADOS_EXPIRAVEIS:
                return False
            estado.encerrar(conn, atendimento_id, linha[1], desfecho="expirado", motivo=MOTIVO, relogio=lambda: agora)
            espelho.emitir_encerrou(conn, atendimento_id, "expirar_parados", agora)
            return True
    except EstadoErro:
        return False


def expirar_parados(servicos: Servicos) -> int:
    agora = servicos.relogio.agora()
    with servicos.abrir_conexao() as conn:
        return sum(expirar_um(conn, atd, agora) for atd in vencidos(conn, agora))


async def executar_expirar_parados(servicos: Servicos) -> int:
    """O serviço que o job periódico `expirar_parados` (a cada 30 min) chama; o banco roda em thread."""
    return await asyncio.to_thread(expirar_parados, servicos)
