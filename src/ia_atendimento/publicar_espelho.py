"""Publicador do espelho (B1.6b; contrato 08 §7.3; G-0216): lê o outbox `ia.espelho_evento` e envia em ordem de `seq` por atendimento.

- Por atendimento, só o PRIMEIRO evento pendente sai em cada rodada (ordem garantida: o seguinte espera o anterior virar enviado).
- Porta `PortaEspelho` (o `tipo:"espelho"` do `ia-repasse`, `idempotency_key=espelho:{atd}:{seq}`). **Sem adaptador real aqui**: o
  caminho `ia-repasse` está em revisão (DEC-PIA-002).
- Sem resposta ⇒ `tentativas + 1` e `proxima_em` pelo backoff de §7.2 (10 s, 30 s, 90 s, 4 min, depois 5 min). Resposta fora de
  `aplicado|obsoleto|desconhecido|impedido` ⇒ crítico e mesma repetição.
- `aplicado|obsoleto` ⇒ enviado. `desconhecido` ⇒ enviado + alerta. **`impedido` ⇒ enviado e o atendimento PARA**:
  `encerrado(repassado, devolvido_pela_s2)` com o `encerrou` na fila, sem nota, sem restaurar, sem `ia-repasse`.
- Evento pendente há mais de 10 min ⇒ amarelo; 30 min ⇒ crítico.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final, Protocol

import psycopg

from ia_atendimento.alertas import Alertas
from ia_atendimento.relogio import Relogio
from ia_atendimento.repasse import backoff_s, encerrar_devolvido_pela_s2, ler_linha

RESULTADOS: Final = frozenset({"aplicado", "obsoleto", "desconhecido", "impedido"})
AMARELO_APOS: Final = timedelta(minutes=10)
CRITICO_APOS: Final = timedelta(minutes=30)
LIMITE: Final = 100

_SQL_PENDENTES: Final = """
SELECT p.atendimento_id, p.seq, p.evento, p.chave, p.detalhe, p.tentativas FROM (
  SELECT DISTINCT ON (atendimento_id) atendimento_id, seq, evento, chave, detalhe, tentativas, proxima_em, criado_em
  FROM ia.espelho_evento WHERE enviado_em IS NULL ORDER BY atendimento_id, seq) p
WHERE p.proxima_em <= %s ORDER BY p.criado_em LIMIT %s
"""


class PortaEspelho(Protocol):
    async def publicar(self, chave: str, seq: int, evento: str, detalhe: dict[str, Any]) -> str: ...


@dataclass(frozen=True)
class DepsEspelho:
    porta: PortaEspelho
    alertas: Alertas
    relogio: Relogio


def _adiar(conn: psycopg.Connection, atd: Any, seq: int, tentativas: int, agora: datetime) -> None:
    conn.execute(
        "UPDATE ia.espelho_evento SET tentativas = %s, proxima_em = %s WHERE atendimento_id = %s AND seq = %s AND enviado_em IS NULL",
        (tentativas + 1, agora + timedelta(seconds=backoff_s(tentativas + 1)), atd, seq),
    )


def _marcar(conn: psycopg.Connection, atd: Any, seq: int, tentativas: int, resultado: str, agora: datetime) -> None:
    conn.execute(
        "UPDATE ia.espelho_evento SET tentativas = %s, enviado_em = %s, resultado = %s"
        " WHERE atendimento_id = %s AND seq = %s AND enviado_em IS NULL",
        (tentativas + 1, agora, resultado, atd, seq),
    )


def _alertar_atraso(conn: psycopg.Connection, deps: DepsEspelho, agora: datetime) -> None:
    mais_velho = conn.execute("SELECT min(criado_em) FROM ia.espelho_evento WHERE enviado_em IS NULL").fetchone()[0]
    if mais_velho is None:
        return
    if agora - mais_velho > CRITICO_APOS:
        deps.alertas.alertar("critico", "espelho_pendente")
    elif agora - mais_velho > AMARELO_APOS:
        deps.alertas.alertar("amarelo", "espelho_pendente")


async def publicar_espelho(conn: psycopg.Connection, deps: DepsEspelho, *, limite: int = LIMITE) -> int:
    """Uma rodada. Devolve quantos eventos ficaram enviados."""
    agora = deps.relogio.agora()
    enviados = 0
    for atd, seq, evento, chave, detalhe, tentativas in conn.execute(_SQL_PENDENTES, (agora, limite)).fetchall():
        try:
            resultado = await deps.porta.publicar(chave, seq, evento, dict(detalhe))
        except Exception:  # sem resposta (424, timeout, 5xx): repete com a mesma chave
            _adiar(conn, atd, seq, tentativas, agora)
            continue
        if resultado not in RESULTADOS:
            deps.alertas.alertar("critico", "espelho_resposta_invalida", atendimento_id=atd)
            _adiar(conn, atd, seq, tentativas, agora)
            continue
        _marcar(conn, atd, seq, tentativas, resultado, agora)
        enviados += 1
        if resultado == "desconhecido":
            deps.alertas.alertar("amarelo", "espelho_desconhecido", atendimento_id=atd)
        if resultado == "impedido":
            linha = ler_linha(conn, atd)
            if linha is not None and linha.estado != "encerrado":
                encerrar_devolvido_pela_s2(conn, linha, agora)
    _alertar_atraso(conn, deps, deps.relogio.agora())
    return enviados
