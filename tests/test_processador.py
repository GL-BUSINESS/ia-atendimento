"""Processador (B1.6b; roteiro B1.6 T8; 08 §6, §7.4, §9): iniciar, processar e o desligamento. Portas falsas; nada sai para fora."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from ia_atendimento.batimento import LeitorBatimento
from ia_atendimento.canal import Canal
from ia_atendimento.chave import LeitorConfig, registrar_config
from ia_atendimento.gasto import GastoIndisponivel, MedidorGasto
from ia_atendimento.ledger import Cerca, Desfecho
from ia_atendimento.processador import Decisao, DepsProcessador, encerrar_por_chave, iniciar, processar
from ia_atendimento.turno import ErroDoModelo
from tests import fixtures_fila as ff
from tests.apoio_b16b import AlertasFalsos, CanalFalso, FonteFalsa, batimento_v2
from tests.fixtures_fila import inserir_atendimento, inserir_custo

conn_app, conn_super, relogio = ff.conn_app, ff.conn_super, ff.relogio

pytestmark = pytest.mark.banco


class MotorFalso:
    def __init__(self, *saidas):
        self.saidas = list(saidas) or [Decisao(("Oi! Posso te ajudar com a proposta?",))]
        self.chamadas = 0
        self.antes = None

    async def decidir(self, atendimento_id):
        self.chamadas += 1
        if self.antes is not None:
            self.antes()
        saida = self.saidas.pop(0) if len(self.saidas) > 1 else self.saidas[0]
        if isinstance(saida, BaseException):
            raise saida
        return saida


class MedidorQuebrado(MedidorGasto):
    def dia(self, conn):
        raise GastoIndisponivel("soma falhou")


class M:
    def __init__(self, conn_app, conn_super, relogio, *, estado="aberto", modo="real", motor=None, corpo="vivo", **kw):
        registrar_config(conn_app, "modo", "real", "teste", relogio=relogio, motivo="preparo do teste")
        self.conn, self.sup, self.relogio = conn_app, conn_super, relogio
        self.porta, self.alertas, self.motor = CanalFalso(), AlertasFalsos(), motor or MotorFalso()
        self.batimento = LeitorBatimento(FonteFalsa(), relogio, self.alertas)
        self.atd = inserir_atendimento(conn_super, estado=estado, modo=modo, iniciado_em=relogio.agora())
        self.chave = self.linha("chave_logica")
        if corpo == "vivo":
            self.batimento.aceitar(batimento_v2(relogio.agora(), vivos={self.chave: "aberto"}))
        leitor = LeitorConfig(relogio, ttl_s=0)
        self.repasses = []

        async def enfileirar(atd):
            self.repasses.append(atd)

        canal = Canal(self.porta, self.batimento, leitor=leitor, relogio=relogio)
        self.deps = DepsProcessador(canal, self.motor, self.batimento, self.alertas, leitor, relogio, enfileirar, **kw)

    def linha(self, coluna):
        return self.sup.execute(f"SELECT {coluna} FROM ia.atendimento WHERE atendimento_id = %s", (self.atd,)).fetchone()[0]

    def eventos(self):
        return [r[0] for r in self.sup.execute("SELECT evento FROM ia.espelho_evento WHERE atendimento_id = %s ORDER BY seq", (self.atd,))]

    def chaves(self):
        return [r[0] for r in self.sup.execute("SELECT chave_logica FROM ia.ferramenta_chamada WHERE atendimento_id = %s", (self.atd,))]


async def test_iniciar_assume_e_abre_com_o_primeiro_turno(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio, estado="reservado")
    r = await iniciar(conn_app, m.atd, m.deps)
    assert r.acao == "aguardar" and m.porta.ops() == ["assumir", "enviar"]
    assert (m.linha("estado"), m.linha("chatbot_estado"), m.linha("chatbot_antes")) == ("aguardando_cliente", "desligado_pela_ia", "ligado")
    assert m.eventos() == ["assumiu"] and m.linha("mensagens_enviadas") == 1 and m.linha("turnos") == 1


async def test_iniciar_com_impedido_encerra_devolvido_sem_assumir(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio, estado="reservado")
    m.batimento.aceitar(batimento_v2(relogio.agora(), seq=2, impedidos={m.chave: "devolvido"}))
    assert (await iniciar(conn_app, m.atd, m.deps)).acao == "devolvido_pela_s2"
    assert m.porta.chamadas == [] and m.linha("motivo_desfecho") == "devolvido_pela_s2"


async def test_iniciar_com_batimento_indisponivel_nao_assume(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio, estado="reservado", corpo=None)
    assert (await iniciar(conn_app, m.atd, m.deps)).acao == "batimento_indisponivel"
    assert m.porta.chamadas == [] and m.linha("estado") == "reservado"


async def test_iniciar_em_sombra_nao_toca_o_chat(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio, estado="reservado", modo="sombra", corpo=None)
    r = await iniciar(conn_app, m.atd, m.deps)
    assert r.acao == "aguardar" and m.porta.chamadas == []
    assert (m.linha("chatbot_estado"), m.linha("chatbot_antes")) == ("intocado", "desconhecido")


async def test_processar_aguardando_volta_e_responde(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio, estado="aguardando_cliente")
    assert (await processar(conn_app, m.atd, m.deps)).acao == "aguardar"
    assert m.porta.ops() == ["enviar"] and m.linha("estado") == "aguardando_cliente"


async def test_zumbi_le_devolvido_e_se_fecha_sem_enviar(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio)
    m.batimento.aceitar(batimento_v2(relogio.agora(), seq=2, impedidos={m.chave: "devolvido"}))
    assert (await processar(conn_app, m.atd, m.deps)).acao == "devolvido_pela_s2"
    assert m.porta.chamadas == [] and m.motor.chamadas == 0
    assert (m.linha("estado"), m.linha("motivo_desfecho")) == ("encerrado", "devolvido_pela_s2") and m.eventos() == ["encerrou"]


async def test_batimento_indisponivel_nao_chama_o_modelo_e_reagenda(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio, corpo=None)
    r = await processar(conn_app, m.atd, m.deps)
    assert (r.acao, r.reagendar_s) == ("batimento_indisponivel", 15.0) and m.motor.chamadas == 0


async def test_primeira_acao_depois_de_indisponibilidade_exige_vivos(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio, corpo=None)
    m.batimento.aceitar(batimento_v2(relogio.agora(), vivos={}))
    assert (await processar(conn_app, m.atd, m.deps)).acao == "fora_de_vivos"
    assert m.motor.chamadas == 0


async def test_retomar_nao_acorda_pausado_em_parada_dura(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio, estado="pausado")
    registrar_config(conn_app, "modo", "sombra", "teste", relogio=relogio, motivo="parada dura")
    assert (await processar(conn_app, m.atd, m.deps)).acao == "fora_de_estado"
    assert m.motor.chamadas == 0 and m.linha("estado") == "pausado"


async def test_duas_falhas_do_modelo_repassam(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio, motor=MotorFalso(ErroDoModelo("provedor", "falhou")))
    r1 = await processar(conn_app, m.atd, m.deps)
    assert (r1.acao, r1.reagendar_s) == ("falha_do_modelo", 10.0) and m.linha("estado") == "aberto"
    r2 = await processar(conn_app, m.atd, m.deps)
    assert r2.acao == "repassar" and m.linha("estado") == "repassando" and m.repasses == [m.atd]
    assert m.linha("motivo_desfecho") == "duas_falhas"


async def test_turno_bom_zera_as_falhas(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio, motor=MotorFalso(ErroDoModelo("provedor", "falhou"), Decisao(("Oi",)), ErroDoModelo("x", "y")))
    await processar(conn_app, m.atd, m.deps)
    await processar(conn_app, m.atd, m.deps)
    r = await processar(conn_app, m.atd, m.deps)
    assert r.acao == "falha_do_modelo"


async def test_disjuntor_acima_de_24_turnos(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio)
    conn_super.execute("UPDATE ia.atendimento SET turnos = 24 WHERE atendimento_id = %s", (m.atd,))
    assert (await processar(conn_app, m.atd, m.deps)).acao == "repassar"
    assert m.motor.chamadas == 0 and m.linha("motivo_desfecho") == "disjuntor_turnos"


async def test_23_turnos_ainda_chama_o_modelo(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio)
    conn_super.execute("UPDATE ia.atendimento SET turnos = 23 WHERE atendimento_id = %s", (m.atd,))
    assert (await processar(conn_app, m.atd, m.deps)).acao == "aguardar" and m.motor.chamadas == 1


async def test_disjuntor_de_custo_do_atendimento(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio)
    conn_super.execute("UPDATE ia.atendimento SET custo_modelo_brl = 3.01 WHERE atendimento_id = %s", (m.atd,))
    assert (await processar(conn_app, m.atd, m.deps)).acao == "repassar"
    assert m.linha("motivo_desfecho") == "disjuntor_custo"


async def test_gasto_indisponivel_nao_chama_o_modelo(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio, medidor=MedidorQuebrado(relogio))
    r = await processar(conn_app, m.atd, m.deps)
    assert (r.acao, r.reagendar_s) == ("gasto_indisponivel", 60.0) and m.motor.chamadas == 0
    assert "gasto_indisponivel" in m.alertas.codigos("critico")


async def test_gasto_acima_de_125_por_cento_repassa_sem_chamar_o_modelo(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio)
    registrar_config(conn_app, "subteto_dia", 10, "teste", relogio=relogio, motivo="preparo do teste")
    inserir_custo(conn_super, m.atd, 12.6, relogio.agora())
    assert (await processar(conn_app, m.atd, m.deps)).acao == "repassar"
    assert m.motor.chamadas == 0 and m.linha("motivo_desfecho") == "teto_gasto"


async def test_gasto_de_80_por_cento_alerta_uma_vez_por_dia(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio)
    registrar_config(conn_app, "subteto_dia", 10, "teste", relogio=relogio, motivo="preparo do teste")
    inserir_custo(conn_super, m.atd, 8.5, relogio.agora())
    await processar(conn_app, m.atd, m.deps)
    await processar(conn_app, m.atd, m.deps)
    assert m.alertas.codigos("amarelo").count("gasto_amarelo") == 1 and m.motor.chamadas == 2


async def test_transversal_repassa_antes_do_modelo(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio, transversal=lambda conn, atd: "pediu_humano")
    assert (await processar(conn_app, m.atd, m.deps)).acao == "repassar"
    assert m.motor.chamadas == 0 and m.linha("motivo_desfecho") == "pediu_humano"


async def test_rodada_superada_nao_envia(conn_app, conn_super, relogio):
    """Outra execução mexeu na versão enquanto o modelo pensava: a velha não envia por cima."""
    m = M(conn_app, conn_super, relogio)
    m.motor.antes = lambda: conn_super.execute("UPDATE ia.atendimento SET versao = versao + 1 WHERE atendimento_id = %s", (m.atd,))
    assert (await processar(conn_app, m.atd, m.deps)).acao == "superado"
    assert m.porta.chamadas == []


async def test_dois_turnos_nunca_compartilham_chave_t11(conn_app, conn_super, relogio):
    """G-0454: cada turno abre `rodada` nova; cada texto do turno tem `seq` próprio."""
    m = M(conn_app, conn_super, relogio, motor=MotorFalso(Decisao(("a", "b"))))
    await processar(conn_app, m.atd, m.deps)
    await processar(conn_app, m.atd, m.deps)
    chaves = m.chaves()
    assert len(chaves) == len(set(chaves)) == 4 and m.porta.ops() == ["enviar"] * 4


async def test_decisao_de_repassar_envia_e_repassa(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio, motor=MotorFalso(Decisao(("Vou te passar para o seu consultor.",), "repassar", "cliente_pediu")))
    assert (await processar(conn_app, m.atd, m.deps)).acao == "repassar"
    assert m.porta.ops() == ["enviar"] and m.linha("estado") == "repassando" and m.repasses == [m.atd]


@pytest.mark.parametrize("estado", ["aberto", "aguardando_cliente", "pausado"])
async def test_desligamento_repassa_os_abertos(conn_app, conn_super, relogio, estado):
    m = M(conn_app, conn_super, relogio, estado=estado)
    assert (await encerrar_por_chave(conn_app, m.atd, m.deps)).acao == "repassar"
    assert (m.linha("estado"), m.linha("motivo_desfecho")) == ("repassando", "ia_desligada") and m.repasses == [m.atd]


async def test_desligamento_aborta_o_reservado(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio, estado="reservado")
    assert (await encerrar_por_chave(conn_app, m.atd, m.deps)).acao == "abortado"
    assert (m.linha("estado"), m.linha("desfecho")) == ("encerrado", "abortado") and m.eventos() == ["encerrou"]
    assert m.porta.chamadas == []


@pytest.mark.parametrize("estado", ["repassando", "encerrado"])
async def test_desligamento_nao_mexe_em_repassando_nem_encerrado(conn_app, conn_super, relogio, estado):
    m = M(conn_app, conn_super, relogio, estado=estado)
    assert (await encerrar_por_chave(conn_app, m.atd, m.deps)).acao == "fora_de_estado"
    assert m.repasses == []


def test_decimal_do_teto_por_atendimento():
    assert Decimal("3.01") > Decimal(3)


async def test_retry_do_turno_que_morreu_depois_de_enviar_nao_responde_de_novo(conn_app, conn_super, relogio):
    """Revisão B1.6b, achado 2: o worker morreu entre o 1º e o 2º envio. O retry não chama o modelo nem envia outra resposta."""
    m = M(conn_app, conn_super, relogio, motor=MotorFalso(Decisao(("primeira", "segunda"))))
    m.porta.respostas["enviar"] = [Desfecho("ok"), asyncio.CancelledError()]
    with pytest.raises(asyncio.CancelledError):
        await processar(conn_app, m.atd, m.deps)
    r = await processar(conn_app, m.atd, m.deps)
    assert r.acao == "retomado_sem_reenvio" and m.motor.chamadas == 1
    assert m.porta.ops() == ["enviar", "enviar"] and m.linha("estado") == "aguardando_cliente"
    assert "turno_retomado_sem_reenvio" in m.alertas.codigos("amarelo")


async def test_retry_do_iniciar_depois_do_assumir_completa(conn_app, conn_super, relogio):
    """Revisão B1.6b, achado 3: o `assumir` fechou `ok` (chatbot desligado de verdade) e a execução morreu antes do `estado.iniciar`.
    O retry abre o atendimento com o chatbot anterior que o ledger gravou e não assume de novo."""
    m = M(conn_app, conn_super, relogio, estado="reservado")
    versao = m.linha("versao")
    await m.deps.canal.assumir(conn_app, m.atd, cerca=Cerca(versao, {"reservado"}))
    r = await iniciar(conn_app, m.atd, m.deps)
    assert r.acao == "aguardar" and m.porta.ops() == ["assumir", "enviar"]
    assert (m.linha("chatbot_estado"), m.linha("chatbot_antes")) == ("desligado_pela_ia", "ligado")


@pytest.mark.parametrize("desfecho", [Desfecho("recusa", http_bucket="4xx"), Desfecho("transitorio", http_bucket="5xx", nada_saiu=True)])
async def test_envio_que_nao_saiu_repassa_e_nao_conta(conn_app, conn_super, relogio, desfecho):
    """Revisão B1.6b, achado 4: a resposta não saiu ⇒ o cliente vai a uma pessoa; `mensagens_enviadas` não conta o que não saiu."""
    m = M(conn_app, conn_super, relogio)
    m.porta.respostas["enviar"] = [desfecho]
    assert (await processar(conn_app, m.atd, m.deps)).acao == "repassar"
    assert m.linha("mensagens_enviadas") == 0 and m.linha("motivo_desfecho") == "envio_falhou"


async def test_motivo_do_modelo_fora_da_forma_nao_derruba_o_repasse(conn_app, conn_super, relogio):
    m = M(conn_app, conn_super, relogio, motor=MotorFalso(Decisao((), "repassar", "Motivo Livre!")))
    assert (await processar(conn_app, m.atd, m.deps)).acao == "repassar"
    assert m.linha("motivo_desfecho") == "repasse"
