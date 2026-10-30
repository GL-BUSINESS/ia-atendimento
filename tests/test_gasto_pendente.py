"""Gasto do contrato 08 §9 (R1-14): Σ `passo.custo_brl` no dia/mês de São Paulo, todos os modos. PENDENTE da B1.6.

`chave._gasto` (B1.3) soma `custo_modelo_brl + custo_midia_brl` dos atendimentos por `iniciado_em`: a conversa que atravessa a meia-noite conta no dia
errado e o custo de um passo só aparece depois que o processador o copia para o atendimento. Hoje o custo é zero (não há processador), então as recusas
`teto_atingido`/`teto_diario` da entrada são inertes. **Não ligar `ia_ativa` antes da B1.6 trocar a fonte**; o `xfail` estrito abaixo vira vermelho (XPASS)
no dia em que a troca for feita, e quem a fizer remove a marca.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ia_atendimento.chave import gasto_dia
from tests import fixtures_fila as ff
from tests.fixtures_fila import inserir_atendimento

conn_app, conn_super = ff.conn_app, ff.conn_super

pytestmark = pytest.mark.banco


@pytest.mark.xfail(strict=True, reason="B1.6: o gasto do §9 é Σ passo.custo_brl (R1-14); a B1.3 ainda soma o custo do atendimento")
def test_gasto_do_dia_soma_passos_em_brt_e_todos_os_modos(conn_app, conn_super):
    agora = datetime.now(UTC)
    atd = inserir_atendimento(conn_super, estado="aberto", modo="duble", iniciado_em=agora)
    conn_super.execute(
        "INSERT INTO ia.passo (atendimento_id, ordem, tipo, texto, turno, fase, peca, custo_brl)"
        " VALUES (%s, 1, 'erro', 'Erro na peça modelo.', 1, 'E1', 'modelo', 5)",
        (atd,),
    )
    assert gasto_dia(conn_app, agora) == Decimal(5)
