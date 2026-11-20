"""Repasse por etapas (B1.6b; 08 §7.1/§7.2; D-14, D-15; R-c2 do lado do orquestrador). Portas falsas; nada sai para fora."""

from __future__ import annotations

from datetime import timedelta

import pytest

from ia_atendimento import repasse
from ia_atendimento.batimento import LeitorBatimento
from ia_atendimento.canal import Canal
from ia_atendimento.chave import LeitorConfig, registrar_config
from ia_atendimento.ledger import Cerca, Desfecho
from ia_atendimento.repasse import DepsRepasse, Reagendar, executar_repasse, iniciar_repasse, repasses_travados
from tests import fixtures_fila as ff
from tests.apoio_b16b import AlertasFalsos, CanalFalso, FonteFalsa, RotaFalsa, batimento_v2
from tests.fixtures_fila import inserir_atendimento

conn_app, conn_super, relogio = ff.conn_app, ff.conn_super, ff.relogio

pytestmark = pytest.mark.banco


class Montagem:
    def __init__(self, conn_app, conn_super, relogio, *, modo="real", corpo="vivo", rota=None, chatbot="desligado_pela_ia", posse=True):
        registrar_config(conn_app, "modo", "real", "teste", relogio=relogio, motivo="preparo do teste")
        self.conn, self.sup, self.relogio = conn_app, conn_super, relogio
        self.porta, self.alertas, self.rota = CanalFalso(), AlertasFalsos(), rota or RotaFalsa()
        self.batimento = LeitorBatimento(FonteFalsa(), relogio, self.alertas)
        if corpo == "vivo":
            self.batimento.aceitar(batimento_v2(relogio.agora()))
        leitor = LeitorConfig(relogio, ttl_s=0)
        self.canal = Canal(self.porta, self.batimento, leitor=leitor, relogio=relogio)
        self.deps = DepsRepasse(self.canal, self.rota, self.batimento, self.alertas, leitor, relogio)
        self.atd = inserir_atendimento(conn_super, estado="aberto", modo=modo, iniciado_em=relogio.agora())
        self.chave = conn_super.execute("SELECT chave_logica FROM ia.atendimento WHERE atendimento_id = %s", (self.atd,)).fetchone()[0]
        self.posse = posse
        self.chatbot = chatbot

    async def preparar(self):
        if self.posse:
            await self.canal.assumir(self.conn, self.atd, cerca=Cerca(self._versao()))
        self.sup.execute(
            "UPDATE ia.atendimento SET chatbot_estado = %s, chatbot_antes = 'ligado', mensagens_enviadas = 2 WHERE atendimento_id = %s",
            (self.chatbot, self.atd),
        )
        iniciar_repasse(self.conn, self.atd, motivo="duas_falhas", relogio=self.relogio)
        self.porta.chamadas.clear()

    def _versao(self):
        return self.sup.execute("SELECT versao FROM ia.atendimento WHERE atendimento_id = %s", (self.atd,)).fetchone()[0]

    def fim(self):
        return self.sup.execute(
            "SELECT estado, desfecho, motivo_desfecho, contexto_codigos, repasse_nota_enviada, nota_repasse_tamanho, chatbot_estado"
            " FROM ia.atendimento WHERE atendimento_id = %s",
            (self.atd,),
        ).fetchone()

    def eventos(self):
        return [r[0] for r in self.sup.execute("SELECT detalhe->>'desfecho' FROM ia.espelho_evento WHERE atendimento_id = %s", (self.atd,))]

    async def rodar(self, desde=None):
        return await executar_repasse(self.conn, self.atd, self.deps, desde)

    async def ate_parar(self, limite=40):
        """Roda o job como a fila faria: avança o relógio pelo atraso pedido e repete com o mesmo `desde`."""
        r, voltas = await self.rodar(), 1
        while isinstance(r, Reagendar) and voltas < limite:
            self.relogio.avancar(seconds=r.atraso_s)
            if self.batimento_vivo:
                self.batimento.aceitar(batimento_v2(self.relogio.agora(), seq=voltas + 1))
            r, voltas = await self.rodar(r.desde), voltas + 1
        return r, voltas

    batimento_vivo = True


@pytest.fixture
async def m(conn_app, conn_super, relogio):
    montagem = Montagem(conn_app, conn_super, relogio)
    await montagem.preparar()
    return montagem


async def test_ordem_do_repasse_restaura_chatbot_antes_da_rota(m):
    assert await m.rodar() is None
    assert m.porta.ops() == ["nota", "restaurar"] and len(m.rota.corpos) == 1
    corpo = m.rota.corpos[0]
    assert corpo["idempotency_key"] == f"repasse:{m.atd}" and corpo["nota_enviada"] == "sim" and corpo["consultor"] is None
    assert not {"chat_number", "pessoa_id", "cpf"} & set(corpo)
    estado, desfecho, *_, chatbot = m.fim()
    assert (estado, desfecho, chatbot) == ("encerrado", "repassado", "restaurado")
    assert m.eventos() == ["repassado"]


async def test_repasse_retoma_pelo_primeiro_marco_sem_ok(conn_app, conn_super, relogio):
    m = Montagem(conn_app, conn_super, relogio, rota=RotaFalsa(["falha_transitoria", "delegou"]))
    await m.preparar()
    r = await m.rodar()
    assert isinstance(r, Reagendar) and r.atraso_s == 10 and m.fim()[0] == "repassando"
    relogio.avancar(seconds=10)
    m.batimento.aceitar(batimento_v2(relogio.agora(), seq=2))
    assert await m.rodar(r.desde) is None
    assert m.porta.ops() == ["nota", "restaurar"]  # nota e chatbot não se repetem
    assert [c["idempotency_key"] for c in m.rota.corpos] == [f"repasse:{m.atd}"] * 2
    assert m.fim()[:2] == ("encerrado", "repassado")


async def test_nota_incerta_nunca_repete(m):
    m.porta.respostas["nota"] = [TimeoutError("sem resposta")]
    m.rota.resultados = ["falha_transitoria", "delegou"]
    r = await m.rodar()
    m.relogio.avancar(seconds=r.atraso_s)
    m.batimento.aceitar(batimento_v2(m.relogio.agora(), seq=2))
    await m.rodar(r.desde)
    assert m.porta.ops().count("nota") == 1
    assert [c["nota_enviada"] for c in m.rota.corpos] == ["incerta", "incerta"]
    fim = m.fim()
    assert (fim[4], fim[5]) == (True, len(repasse.nota_padrao(repasse.ler_linha(m.sup, m.atd)) or ""))


async def test_nota_503_segue_sem_nota_e_marca_nao(m):
    m.porta.respostas["nota"] = [Desfecho("transitorio", http_bucket="5xx", nada_saiu=True)]
    assert await m.rodar() is None
    assert m.rota.corpos[0]["nota_enviada"] == "nao"
    assert (m.fim()[4], m.fim()[5]) == (False, None) and "nota_nao_entregue" in m.alertas.codigos("amarelo")


async def test_nota_enviada_mapeia_para_boolean_do_ddl(m):
    await m.rodar()
    fim = m.fim()
    assert fim[4] is True and fim[5] > 0


async def test_sem_mensagem_da_ia_a_nota_nao_se_aplica(conn_app, conn_super, relogio):
    m = Montagem(conn_app, conn_super, relogio)
    await m.preparar()
    conn_super.execute("UPDATE ia.atendimento SET mensagens_enviadas = 0 WHERE atendimento_id = %s", (m.atd,))
    await m.rodar()
    assert "nota" not in m.porta.ops() and m.rota.corpos[0]["nota_enviada"] == "nao_aplica"


async def test_n8n_5xx_mantem_repassando_e_reagenda_com_mesma_chave(conn_app, conn_super, relogio):
    m = Montagem(conn_app, conn_super, relogio, rota=RotaFalsa([OSError("502")]))
    await m.preparar()
    r = await m.rodar()
    assert isinstance(r, Reagendar) and m.fim()[0] == "repassando"
    assert "repasse_falhou" in m.alertas.codigos("amarelo")


async def test_repasse_para_de_tentar_aos_30_min_e_marca_travado(conn_app, conn_super, relogio):
    m = Montagem(conn_app, conn_super, relogio, rota=RotaFalsa(["falha_transitoria"]))
    await m.preparar()
    inicio = relogio.agora()
    r, _ = await m.ate_parar()
    assert r is None and relogio.agora() - inicio <= timedelta(minutes=30, seconds=1)
    assert 8 <= len(m.rota.corpos) <= 10  # a 1ª + 8 repetições, a última aos ≈ 26 min (08 §7.2)
    estado, *_ = m.fim()
    assert estado == "repassando" and "repasse_travado" in m.fim()[3]
    assert "repasse_travado" in m.alertas.codigos("humano") and "repasse_travado" in m.alertas.codigos("critico")
    assert repasses_travados(conn_super) == [m.chave]


async def test_ja_devolvido_encerra_devolvido_pela_s2_sem_restaurar(conn_app, conn_super, relogio):
    m = Montagem(conn_app, conn_super, relogio, rota=RotaFalsa(["ja_devolvido"]))
    await m.preparar()
    assert await m.rodar() is None
    assert m.fim()[:3] == ("encerrado", "repassado", "devolvido_pela_s2") and m.eventos() == ["devolvido_pela_s2"]
    assert m.porta.ops().count("restaurar") == 1


@pytest.mark.parametrize("resultado", ["sem_consultor", "desconhecido"])
async def test_sem_consultor_e_desconhecido_encerram_com_pendencia(conn_app, conn_super, relogio, resultado):
    m = Montagem(conn_app, conn_super, relogio, rota=RotaFalsa([resultado]))
    await m.preparar()
    assert await m.rodar() is None
    assert m.fim()[:2] == ("encerrado", "repassado") and "repasse_sem_consultor" in m.fim()[3]
    assert "repasse_sem_consultor" in m.alertas.codigos("critico")


async def test_resposta_invalida_trava_sem_repetir(conn_app, conn_super, relogio):
    m = Montagem(conn_app, conn_super, relogio, rota=RotaFalsa(["quem_sabe"]))
    await m.preparar()
    assert await m.rodar() is None
    assert "repasse_travado" in m.fim()[3] and "repasse_resposta_invalida" in m.alertas.codigos("critico")


async def test_batimento_impedido_antes_da_rota_nao_briga_com_a_vigia(m):
    m.batimento.aceitar(batimento_v2(m.relogio.agora(), seq=5, impedidos={m.chave: "devolvendo"}))
    assert await m.rodar() is None
    assert m.porta.ops() == [] and m.rota.corpos == []
    assert m.fim()[:3] == ("encerrado", "repassado", "devolvido_pela_s2")


async def test_retry_da_rota_nao_consulta_o_batimento(conn_app, conn_super, relogio):
    m = Montagem(conn_app, conn_super, relogio, rota=RotaFalsa(["falha_transitoria", "delegou"]))
    await m.preparar()
    r = await m.rodar()
    relogio.avancar(seconds=200)  # o batimento envelhece (vigia fora): depois da 1ª tentativa de rota não importa
    assert await m.rodar(r.desde) is None
    assert m.fim()[:2] == ("encerrado", "repassado")


async def test_batimento_indisponivel_espera_e_entrega_ao_humano_aos_30_min(conn_app, conn_super, relogio):
    """G-0020: a vigia morreu (sem batimento). Nada sai (D-15); o job espera até 30 min e entrega ao humano."""
    m = Montagem(conn_app, conn_super, relogio)
    await m.preparar()
    m.batimento_vivo = False
    relogio.avancar(seconds=91)  # o último batimento envelhece e nenhum novo chega
    r, _ = await m.ate_parar(limite=200)
    assert r is None and m.porta.ops() == [] and m.rota.corpos == []
    assert "repasse_travado" in m.fim()[3] and "repasse_travado" in m.alertas.codigos("humano")


async def test_sem_posse_real_simula_as_cinco_etapas(conn_app, conn_super, relogio):
    m = Montagem(conn_app, conn_super, relogio, modo="sombra", corpo=None, posse=False)
    await m.preparar()
    assert await m.rodar() is None
    assert m.porta.ops() == [] and m.rota.corpos == []
    assert m.fim()[:3] == ("encerrado", "sem_venda", "repasse_simulado") and m.eventos() == ["sem_venda"]
    n = conn_super.execute("SELECT count(*) FROM ia.passo WHERE atendimento_id = %s AND tipo = 'repasse'", (m.atd,)).fetchone()[0]
    assert n == 5


async def test_real_sem_assumir_ok_tambem_e_simulado(conn_app, conn_super, relogio):
    m = Montagem(conn_app, conn_super, relogio, posse=False)
    await m.preparar()
    assert await m.rodar() is None
    assert m.porta.ops() == [] and m.rota.corpos == [] and m.fim()[1] == "sem_venda"


async def test_chatbot_intocado_pula_o_restaurar(conn_app, conn_super, relogio):
    m = Montagem(conn_app, conn_super, relogio, chatbot="intocado")
    await m.preparar()
    await m.rodar()
    assert m.porta.ops() == ["nota"]


async def test_restaurar_transitorio_reagenda_e_repete(m):
    m.porta.respostas["restaurar"] = [OSError("caiu")]
    r = await m.rodar()
    assert isinstance(r, Reagendar) and m.rota.corpos == []
    m.relogio.avancar(seconds=r.atraso_s)
    m.batimento.aceitar(batimento_v2(m.relogio.agora(), seq=3))
    assert await m.rodar(r.desde) is None
    assert m.porta.ops() == ["nota", "restaurar", "restaurar"]
