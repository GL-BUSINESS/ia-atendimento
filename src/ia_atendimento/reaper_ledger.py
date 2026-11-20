"""`reaper_ledger` (B1.6b; G-0116; contrato 08 §7.1): fecha linhas do ledger que ninguém vai repetir.

Rodada periódica (e no boot) sobre `idx_ferramenta_chamada_aberta`:
- **`reservada` há mais de 10 min** ⇒ `nao_criada`. Uma `reservada` prova que nada saiu (o CAS `reservada → enviada` vem antes da
  chamada); fechá-la libera a vaga única da T7 por (pessoa, banco). Se a execução dona ainda estiver viva, o CAS dela perde e ela não
  chama nada.
- **`enviada|em_andamento` além do timeout + folga** ⇒ o mesmo critério da órfã achada no retry (`ledger.desfecho_da_orfa`, G-0131):
  efeito irreversível em `real|teste` vira `indeterminado` (alerta crítico; a T8 decide a T7, B5.4); o resto volta a `transitorio`
  (repete com a mesma chave, sem trancar vaga nenhuma).
Cada fechamento é um CAS do estado: quem fechou primeiro vale.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

import psycopg

from ia_atendimento.alertas import Alertas
from ia_atendimento.ledger import EM_VOO, FOLGA_EM_VOO, TIMEOUT_PADRAO_S, desfecho_da_orfa

RESERVADA_MAX: Final = timedelta(minutes=10)
EM_VOO_MAX: Final = timedelta(seconds=TIMEOUT_PADRAO_S) + FOLGA_EM_VOO
LIMITE: Final = 200

_SQL_ABERTAS: Final = """
SELECT chamada_id, atendimento_id, classe_efeito, estado, modo FROM ia.ferramenta_chamada
WHERE concluida_em IS NULL AND ((estado = 'reservada' AND reservada_em < %(reservada)s)
  OR (estado = ANY(%(em_voo)s) AND enviada_em < %(enviada)s))
ORDER BY reservada_em LIMIT %(limite)s
"""
_SQL_FECHAR: Final = """
UPDATE ia.ferramenta_chamada SET estado = %s, concluida_em = %s WHERE chamada_id = %s AND estado = %s RETURNING chamada_id
"""


@dataclass(frozen=True)
class Varredura:
    nao_criadas: int = 0
    indeterminadas: int = 0
    transitorias: int = 0


def varrer_ledger(conn: psycopg.Connection, agora: datetime, alertas: Alertas, *, limite: int = LIMITE) -> Varredura:
    linhas = conn.execute(
        _SQL_ABERTAS, {"reservada": agora - RESERVADA_MAX, "em_voo": list(EM_VOO), "enviada": agora - EM_VOO_MAX, "limite": limite}
    ).fetchall()
    contagem = {"nao_criada": 0, "indeterminado": 0, "transitorio": 0}
    for chamada_id, atd, classe, estado_atual, modo in linhas:
        final = "nao_criada" if estado_atual == "reservada" else desfecho_da_orfa(classe, modo)
        if conn.execute(_SQL_FECHAR, (final, agora, chamada_id, estado_atual)).fetchone() is None:
            continue  # alguém fechou antes
        contagem[final] += 1
        if final == "indeterminado":
            alertas.alertar("critico", "efeito_indeterminado", atendimento_id=atd)
    resultado = Varredura(contagem["nao_criada"], contagem["indeterminado"], contagem["transitorio"])
    if resultado.nao_criadas or resultado.transitorias:
        alertas.alertar("amarelo", "ledger_orfas", detalhe=f"nao_criadas={resultado.nao_criadas} transitorias={resultado.transitorias}")
    return resultado
