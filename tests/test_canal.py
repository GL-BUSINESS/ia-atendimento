"""`Canal` (B1.6b; 08 §6 e §7.4): batimento antes do efeito real, ledger por baixo, porta falsa. Nada sai para fora."""

from __future__ import annotations

from datetime import timedelta

import pytest

from ia_atendimento.batimento import LeitorBatimento
from ia_atendimento.canal import BatimentoIndisponivel, Canal, CercoFechado, ForaDeVivos
from ia_atendimento.chave import LeitorConfig, registrar_config
from ia_atendimento.ledger import Cerca, Desfecho
from tests import fixtures_fila as ff
from tests.apoio_b16b import AlertasFalsos, CanalFalso, FonteFalsa, batimento_v2
from tests.fixtures_fila import inserir_atendimento

conn_app, conn_super, relogio = ff.conn_app, ff.conn_super, ff.relogio

pytestmark = pytest.mark.banco


def _config(conn, relogio, nome, valor):
    registrar_config(conn, nome, valor, "teste", relogio=relogio, motivo="preparo do teste")


def _chave(conn, atd) -> str:
    return conn.execute("SELECT chave_logica FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()[0]


def _versao(conn, atd) -> int:
    return conn.execute("SELECT versao FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()[0]


def _montar(relogio, corpo=None, *, ttl_s=0.0):
    porta, alertas = CanalFalso(), AlertasFalsos()
    batimento = LeitorBatimento(FonteFalsa(corpo), relogio, alertas)
    if corpo is not None:
        batimento.aceitar(corpo)
    canal = Canal(porta, batimento, leitor=LeitorConfig(relogio, ttl_s=ttl_s), relogio=relogio)
    return canal, porta, batimento, alertas


async def _enviar(canal, conn, atd, seq=1, texto="Oi, tudo bem?", **kw):
    return await canal.enviar(conn, atd, rodada=1, seq=seq, texto=texto, cerca=Cerca(_versao(conn, atd)), **kw)


async def test_real_com_batimento_livre_envia_uma_vez(conn_app, conn_super, relogio):
    _config(conn_app, relogio, "modo", "real")
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
    canal, porta, _, _ = _montar(relogio, batimento_v2(relogio.agora()))
    r = await _enviar(canal, conn_app, atd)
    assert (r.estado, r.modo, r.executou) == ("ok", "real", True)
    assert porta.chamadas == [("enviar", "real", "Oi, tudo bem?")]


async def test_sombra_nunca_alcanca_facta_real_nem_canal(conn_app, conn_super, relogio):
    """Nasceu `sombra`: não consulta o batimento (ausente aqui) e não chama a porta; o ledger grava `sombra`."""
    _config(conn_app, relogio, "modo", "real")
    atd = inserir_atendimento(conn_super, estado="aberto", modo="sombra", iniciado_em=relogio.agora())
    canal, porta, _, alertas = _montar(relogio, None)
    r = await _enviar(canal, conn_app, atd)
    assert (r.estado, r.modo, r.executou) == ("ok", "sombra", False)
    assert porta.chamadas == [] and alertas.vistos == []


async def test_parada_dura_intercepta_atendimento_real_aberto(conn_app, conn_super, relogio):
    """Nenhuma mensagem sai ≤ 5 s depois de `modo=sombra` (cache do LeitorConfig de 5 s)."""
    _config(conn_app, relogio, "modo", "real")
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
    canal, porta, _, _ = _montar(relogio, batimento_v2(relogio.agora()), ttl_s=5)
    await _enviar(canal, conn_app, atd, seq=1)
    _config(conn_app, relogio, "modo", "sombra")
    relogio.avancar(seconds=5)
    r = await _enviar(canal, conn_app, atd, seq=2)
    assert r.modo == "sombra" and not r.executou
    assert porta.ops() == ["enviar"]


async def test_teste_so_envia_em_chat_de_teste_com_prefixo(conn_app, conn_super, relogio):
    _config(conn_app, relogio, "modo", "real")
    atd = inserir_atendimento(conn_super, estado="aberto", modo="teste", iniciado_em=relogio.agora())
    canal, porta, _, _ = _montar(relogio, batimento_v2(relogio.agora()))
    await _enviar(canal, conn_app, atd)
    assert porta.chamadas == [("enviar", "teste", "[TESTE] Oi, tudo bem?")]


async def test_impedido_e_cerco_fechado_sem_reservar(conn_app, conn_super, relogio):
    _config(conn_app, relogio, "modo", "real")
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
    canal, porta, _, _ = _montar(relogio, batimento_v2(relogio.agora(), impedidos={_chave(conn_super, atd): "devolvido"}))
    with pytest.raises(CercoFechado):
        await _enviar(canal, conn_app, atd)
    n = conn_super.execute("SELECT count(*) FROM ia.ferramenta_chamada WHERE atendimento_id = %s", (atd,)).fetchone()[0]
    assert porta.chamadas == [] and n == 0


async def test_batimento_ausente_ou_velho_bloqueia_efeito_e_alerta(conn_app, conn_super, relogio):
    _config(conn_app, relogio, "modo", "real")
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
    canal, porta, _, alertas = _montar(relogio, batimento_v2(relogio.agora() - timedelta(seconds=91)))
    with pytest.raises(BatimentoIndisponivel):
        await _enviar(canal, conn_app, atd)
    assert porta.chamadas == [] and "batimento_indisponivel" in alertas.codigos("critico")


async def test_retomada_exige_vivos(conn_app, conn_super, relogio):
    _config(conn_app, relogio, "modo", "real")
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
    canal, porta, _, _ = _montar(relogio, batimento_v2(relogio.agora(), vivos={}))
    with pytest.raises(ForaDeVivos):
        await _enviar(canal, conn_app, atd, esperado_em_vivos="aberto")
    assert porta.chamadas == []


async def test_devolucao_sem_posse_real_nao_consulta_batimento_nem_chama(conn_app, conn_super, relogio):
    _config(conn_app, relogio, "modo", "real")
    atd = inserir_atendimento(conn_super, estado="repassando", modo="real", iniciado_em=relogio.agora())
    canal, porta, _, _ = _montar(relogio, None)
    r = await canal.nota(conn_app, atd, texto="Cliente pediu para falar com você.")
    assert (r.modo, r.executou) == ("sombra", False) and porta.chamadas == []


async def test_parada_dura_com_posse_real_consulta_impedidos(conn_app, conn_super, relogio):
    """R2-03: `impedidos` sob `sombra` global ⇒ nem nota, nem restaurar."""
    _config(conn_app, relogio, "modo", "real")
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
    canal, porta, batimento, _ = _montar(relogio, batimento_v2(relogio.agora()))
    await canal.assumir(conn_app, atd, cerca=Cerca(_versao(conn_super, atd)))
    _config(conn_app, relogio, "modo", "sombra")
    batimento.aceitar(batimento_v2(relogio.agora(), seq=2, impedidos={_chave(conn_super, atd): "devolvendo"}))
    with pytest.raises(CercoFechado):
        await canal.nota(conn_app, atd, texto="Nota.")
    with pytest.raises(CercoFechado):
        await canal.restaurar(conn_app, atd)
    assert porta.ops() == ["assumir"]


async def test_parada_dura_devolve_real_quem_tem_posse_real(conn_app, conn_super, relogio):
    _config(conn_app, relogio, "modo", "real")
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
    canal, porta, _, _ = _montar(relogio, batimento_v2(relogio.agora()))
    await canal.assumir(conn_app, atd, cerca=Cerca(_versao(conn_super, atd)))
    _config(conn_app, relogio, "modo", "sombra")
    r = await canal.restaurar(conn_app, atd)
    assert (r.modo, r.executou) == ("real", True) and porta.ops() == ["assumir", "restaurar"]


async def test_assumir_devolve_chatbot_antes(conn_app, conn_super, relogio):
    _config(conn_app, relogio, "modo", "real")
    atd = inserir_atendimento(conn_super, estado="reservado", modo="real", iniciado_em=relogio.agora())
    canal, porta, _, _ = _montar(relogio, batimento_v2(relogio.agora()))
    porta.respostas["assumir"] = [Desfecho("ok", ref_externa="desligado")]
    r = await canal.assumir(conn_app, atd, cerca=Cerca(_versao(conn_super, atd), {"reservado"}))
    assert (r.estado, r.ref_externa) == ("ok", "desligado")
