"""Publicador do espelho (B1.6b; 08 §7.3): ordem de `seq`, repetição com backoff, `impedido` para o atendimento. Porta falsa."""

from __future__ import annotations

from datetime import timedelta

import pytest

from ia_atendimento import espelho
from ia_atendimento.publicar_espelho import DepsEspelho, publicar_espelho
from tests import fixtures_fila as ff
from tests.apoio_b16b import AlertasFalsos, EspelhoFalso
from tests.fixtures_fila import inserir_atendimento

conn_app, conn_super, relogio = ff.conn_app, ff.conn_super, ff.relogio

pytestmark = pytest.mark.banco


def _emitir(conn, atd, *eventos, quando=None):
    """O outbox nasce com `now()` do banco; o publicador decide pelo relógio injetado, então o teste alinha os dois."""
    with conn.transaction():
        for e in eventos:
            espelho.emitir(conn, atd, e, {})
    if quando is not None:
        conn.execute("UPDATE ia.espelho_evento SET proxima_em = %s WHERE atendimento_id = %s", (quando, atd))


def _pendentes(conn, atd):
    return [
        r[0]
        for r in conn.execute("SELECT seq FROM ia.espelho_evento WHERE atendimento_id = %s AND enviado_em IS NULL ORDER BY seq", (atd,))
    ]


def _deps(relogio, porta):
    return DepsEspelho(porta, AlertasFalsos(), relogio)


async def test_outbox_publicado_em_ordem_de_seq(conn_app, conn_super, relogio):
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
    _emitir(conn_app, atd, "assumiu", "pausou", "retomou", quando=relogio.agora())
    porta = EspelhoFalso()
    deps = _deps(relogio, porta)
    for _ in range(3):
        await publicar_espelho(conn_app, deps)
    assert [s for _, s, _ in porta.enviados] == [1, 2, 3] and _pendentes(conn_super, atd) == []


async def test_falha_repete_com_backoff_sem_pular_a_ordem(conn_app, conn_super, relogio):
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
    _emitir(conn_app, atd, "assumiu", "pausou", quando=relogio.agora())
    porta = EspelhoFalso([OSError("424"), "aplicado"])
    deps = _deps(relogio, porta)
    assert await publicar_espelho(conn_app, deps) == 0
    assert await publicar_espelho(conn_app, deps) == 0  # ainda no backoff (10 s): nem o seq 2 sai na frente
    relogio.avancar(seconds=11)
    assert await publicar_espelho(conn_app, deps) == 1
    assert [s for _, s, _ in porta.enviados] == [1, 1] and _pendentes(conn_super, atd) == [2]


async def test_resposta_impedido_para_o_atendimento(conn_app, conn_super, relogio):
    atd = inserir_atendimento(conn_super, estado="aguardando_cliente", modo="real", iniciado_em=relogio.agora())
    _emitir(conn_app, atd, "assumiu", quando=relogio.agora())
    await publicar_espelho(conn_app, _deps(relogio, EspelhoFalso(["impedido"])))
    linha = conn_super.execute("SELECT estado, motivo_desfecho FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()
    assert linha == ("encerrado", "devolvido_pela_s2") and _pendentes(conn_super, atd) == [2]  # o `encerrou` na fila


async def test_resposta_desconhecida_alerta_e_repete(conn_app, conn_super, relogio):
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
    _emitir(conn_app, atd, "assumiu", quando=relogio.agora())
    deps = _deps(relogio, EspelhoFalso(["talvez"]))
    await publicar_espelho(conn_app, deps)
    assert "espelho_resposta_invalida" in deps.alertas.codigos("critico") and _pendentes(conn_super, atd) == [1]


async def test_pendente_velho_alerta(conn_app, conn_super, relogio):
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
    _emitir(conn_app, atd, "assumiu", quando=relogio.agora())
    conn_super.execute(
        "UPDATE ia.espelho_evento SET criado_em = %s WHERE atendimento_id = %s", (relogio.agora() - timedelta(minutes=31), atd)
    )
    deps = _deps(relogio, EspelhoFalso([OSError("fora")]))
    await publicar_espelho(conn_app, deps)
    assert "espelho_pendente" in deps.alertas.codigos("critico")
