"""`expirar_parados` (B1.6a; sp01 Task 5; gate 3 de DECISOES-B5.7b): encerra `expirado` quem passou do `dias_max` da faixa.

- Só `jobs.ESTADOS_EXPIRAVEIS` (`aberto`, `aguardando_cliente`). `pausado`, o `reservado` de agendamento e `repassando` têm donos próprios
  (volta, lease, repasse, parada leve manual).
- O prazo é o `dias_max` da faixa na versão de `faixas_esforco` vigente em `iniciado_em` (`espera.limites_da_faixa`), nunca acima de 7 dias.
- Chat com job do chat em curso (`doing`/`todo`, `lock=chat:`) fica para a próxima rodada: não se disputa o atendimento com um turno.
- Cada encerramento é um CAS de `versao` sob `FOR UPDATE` com o `encerrou` (`desfecho=expirar_parados`) no outbox, na mesma transação.
  Perdeu o CAS ou o estado mudou no meio: pula (o próximo tick reavalia).
- **Com posse real (B1.6b, G-0093) passa pelo repasse**: fase 1 (`repassando`, motivo `expirar_parados`) e o job `repasse` devolve o
  chat ao vendedor (nota, chatbot, rota); o `encerrou` sai quando o repasse fechar. Sem quem enfileire o job (`Servicos` sem a B1.6b),
  não mexe: um `repassando` sem job ficaria órfão. **Sem posse real** (nasceu `sombra|duble`, ou o `assumir` nunca fechou `ok`) não há o
  que devolver: encerra `expirado` direto, com o `encerrou` (`desfecho=expirar_parados`) no outbox.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Final

import psycopg

from ia_atendimento import espelho, estado
from ia_atendimento.chave import config_no_tempo
from ia_atendimento.espera import TETO_DIAS, limites_de
from ia_atendimento.estado_erros import EstadoErro
from ia_atendimento.jobs import ESTADOS_EXPIRAVEIS, LIMITE_LOTE, Servicos, configurado
from ia_atendimento.ledger import posse_real

MOTIVO: Final = "expirar_parados"
PISO_DIAS: Final = 1  # menor `dias_max` que o registro aceita
LIMITE_CANDIDATOS: Final = 1000  # tamanho da página de candidatos

_SQL_CANDIDATOS: Final = """
SELECT a.atendimento_id, a.faixa_esforco, a.iniciado_em FROM ia.atendimento a
WHERE a.estado = ANY(%(estados)s) AND a.iniciado_em < %(piso)s
  AND (%(depois_em)s::timestamptz IS NULL OR (a.iniciado_em, a.atendimento_id) > (%(depois_em)s, %(depois_id)s::uuid))
  AND NOT EXISTS (SELECT 1 FROM procrastinate.procrastinate_jobs j WHERE j.lock = 'chat:' || a.chat_id AND j.status IN ('doing', 'todo'))
ORDER BY a.iniciado_em, a.atendimento_id LIMIT %(limite)s
"""


def vencidos(conn: psycopg.Connection, agora: datetime, limite: int = LIMITE_LOTE) -> list[uuid.UUID]:
    """Atendimentos expiráveis cujo `iniciado_em + dias_max` (da faixa, na versão de `iniciado_em`) já passou. Percorre os candidatos
    em páginas (keyset por `iniciado_em, atendimento_id`) até achar `limite` ou acabar: os mais velhos ainda dentro de um `dias_max`
    maior não escondem os mais novos de faixa menor. As versões de `faixas_esforco` são lidas uma vez (`config_no_tempo`)."""
    faixas_em = config_no_tempo(conn, "faixas_esforco")
    params = {
        "estados": list(ESTADOS_EXPIRAVEIS), "piso": agora - timedelta(days=PISO_DIAS), "limite": LIMITE_CANDIDATOS,
        "depois_em": None, "depois_id": None,
    }  # fmt: skip
    achados: list[uuid.UUID] = []
    while True:
        pagina = conn.execute(_SQL_CANDIDATOS, params).fetchall()
        for atd, faixa, iniciado_em in pagina:
            if agora - iniciado_em > timedelta(days=min(TETO_DIAS, limites_de(faixas_em(iniciado_em), faixa).dias_max)):
                achados.append(atd)
                if len(achados) >= limite:
                    return achados
        if len(pagina) < LIMITE_CANDIDATOS:
            return achados
        params = {**params, "depois_em": pagina[-1][2], "depois_id": pagina[-1][0]}


def expirar_um(conn: psycopg.Connection, atendimento_id: uuid.UUID, agora: datetime, *, pode_repassar: bool = False) -> str | None:
    """Numa transação: sem posse real, `encerrar(expirado)` + `encerrou` (devolve `expirado`); com posse real e `pode_repassar`, fase 1
    do repasse (devolve `repassar`: quem chama enfileira o job). None se saiu dos expiráveis, perdeu o CAS ou tem posse sem repasse."""
    try:
        with conn.transaction():
            linha = conn.execute(
                "SELECT estado, versao, modo FROM ia.atendimento WHERE atendimento_id = %s FOR UPDATE", (atendimento_id,)
            ).fetchone()
            if linha is None or linha[0] not in ESTADOS_EXPIRAVEIS:
                return None
            if linha[2] in ("real", "teste") and posse_real(conn, atendimento_id):
                if not pode_repassar:
                    return None
                estado.repassar(conn, atendimento_id, linha[1], modo="indicado", motivo=MOTIVO, relogio=lambda: agora)
                return "repassar"
            estado.encerrar(conn, atendimento_id, linha[1], desfecho="expirado", motivo=MOTIVO, relogio=lambda: agora)
            espelho.emitir_encerrou(conn, atendimento_id, "expirar_parados", agora)
            return "expirado"
    except EstadoErro:
        return None


def expirar_parados(servicos: Servicos) -> tuple[int, list[uuid.UUID]]:
    """Devolve (quantos saíram, os que foram a `repassando` e precisam do job `repasse`)."""
    agora = servicos.relogio.agora()
    pode = configurado(servicos.enfileirar_repasse)
    with servicos.abrir_conexao() as conn:
        feitos = [(atd, expirar_um(conn, atd, agora, pode_repassar=pode)) for atd in vencidos(conn, agora)]
    return sum(1 for _, r in feitos if r), [atd for atd, r in feitos if r == "repassar"]


async def executar_expirar_parados(servicos: Servicos) -> int:
    """O serviço que o job periódico `expirar_parados` (a cada 30 min) chama; o banco roda em thread."""
    n, repassar = await asyncio.to_thread(expirar_parados, servicos)
    for atd in repassar:
        await servicos.enfileirar_repasse(atd)
    return n
