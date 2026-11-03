"""Ciclo de vida do atendimento (B1.1, sp01 T3): seis estados, CAS por `versao`, lease e a trava por chat, contra o PG 18 real.

Sem PII: ids, chat e operador sintéticos (`tests/estado_apoio.py`).
"""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import psycopg
import pytest

from ia_atendimento import estado, estado_pausa
from ia_atendimento.estado import (
    LEASE_AGUARDANDO_S,
    LEASE_RESERVADO_S,
    LEASE_TURNO_S,
    ArtefatoAusente,
    AtendimentoInexistente,
    ChatOcupado,
    ConflitoIdempotencia,
    ConflitoVersao,
    EntradaInvalida,
    Mudancas,
    TransicaoInvalida,
    abortar,
    abrir,
    aguardar_cliente,
    aplicar,
    encerrar,
    entrada_fingerprint,
    iniciar,
    ler,
    repassar,
    retomar,
    versoes_vigentes,
)
from ia_atendimento.estado_conversa import EstadoConversa, Pausa, gravar_estado_conversa
from tests.banco import Banco
from tests.estado_apoio import CHAT, CHAVE, INICIO, OUTRA_PESSOA, OUTRO_CHAT, PESSOA, entrada

# --- helpers --------------------------------------------------------------------------------------------------------------------


def _chat(n: int) -> str:
    return f"{n:024x}"


def _entrada_n(n: int, **mudar):
    return entrada(chave_logica=f"venda:{n:032x}", chat_id=_chat(n), **mudar)


def _abrir(conn, relogio, versoes, ent=None, *, modo_global="duble", chats_teste=(), faixa="media", comissao=None, origem="n8n_braco"):
    return abrir(
        conn,
        origem=origem,
        entrada=ent or entrada(),
        versoes=versoes,
        modo_global=modo_global,
        chats_teste=frozenset(chats_teste),
        faixa_esforco=faixa,
        comissao_esperada_brl=comissao,
        relogio=relogio,
    )


def _iniciar(conn, relogio, atd, versao):
    return iniciar(conn, atd, versao, chatbot_antes="desligado", chatbot_estado="desligado_pela_ia", relogio=relogio)


def _aberto(conn, relogio, versoes, n=1, **kw):
    """Atendimento `aberto` (E1) do chat n; devolve (atendimento_id, versao)."""
    res = _abrir(conn, relogio, versoes, _entrada_n(n), **kw)
    return res.atendimento_id, _iniciar(conn, relogio, res.atendimento_id, res.versao)


def _estado_e_versao(conn, atd):
    return conn.execute("SELECT estado, versao FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()


# --- artefatos e abrir -----------------------------------------------------------------------------------------------------------


@pytest.mark.banco
def test_abrir_sem_artefato_versao_levanta_artefato_ausente(db_conn):
    with pytest.raises(ArtefatoAusente) as erro:
        versoes_vigentes(db_conn)
    assert erro.value.tipos == ("catalogo", "motor", "regras", "roteiro")


@pytest.mark.banco
def test_versoes_vigentes_e_o_maior_numero_por_tipo(db_conn, versoes):
    assert versoes_vigentes(db_conn) == versoes


@pytest.mark.banco
def test_versoes_vigentes_com_tipo_faltando_nomeia_so_o_que_falta(db_conn):
    db_conn.execute(
        "INSERT INTO ia.artefato_versao (tipo, numero, descricao, aprovado_por) VALUES ('roteiro', 1, 'x', 'dono.teste@exemplo.invalid')"
    )
    with pytest.raises(ArtefatoAusente) as erro:
        versoes_vigentes(db_conn)
    assert erro.value.tipos == ("catalogo", "motor", "regras")


@pytest.mark.banco
def test_abrir_cria_reservado_com_lease_de_2_min_e_fase_e0(db_conn, relogio, versoes):
    res = _abrir(db_conn, relogio, versoes)
    a = ler(db_conn, res.atendimento_id)
    assert (res.estado, res.versao, res.repetido) == ("reservado", 1, False)
    assert (a.estado, a.fase, a.assumido_em, a.versao, a.modo) == ("reservado", "E0", None, 1, "duble")
    assert LEASE_RESERVADO_S == 120 and a.lease_ate == relogio() + timedelta(seconds=120)
    assert (a.iniciado_em, a.atualizado_em) == (relogio(), relogio())  # tempo de negócio vem do Relogio, não do now() do banco
    assert (a.roteiro_versao, a.regras_versao, a.catalogo_versao, a.motor_versao) == (3, 2, 1, 4)
    assert (a.origem, a.chave_logica, a.gatilho, a.chat_id) == ("n8n_braco", CHAVE, "venda", CHAT)
    assert a.entrada_fingerprint == entrada_fingerprint(entrada())


@pytest.mark.banco
def test_abrir_guarda_ultimo_cliente_em_da_entrada(db_conn, relogio, versoes):
    res = _abrir(db_conn, relogio, versoes, entrada(ultimo_cliente_em="2026-11-24T09:00:00-03:00"))
    assert ler(db_conn, res.atendimento_id).ultimo_cliente_em.isoformat() == "2026-11-24T12:00:00+00:00"


@pytest.mark.banco
def test_abrir_grava_faixa_e_comissao_e_elas_sao_imutaveis(db_conn, relogio, versoes):
    res = _abrir(db_conn, relogio, versoes, faixa="alta", comissao="1234.56")
    a = ler(db_conn, res.atendimento_id)
    assert (a.faixa_esforco, str(a.comissao_esperada_brl)) == ("alta", "1234.56")
    for coluna, valor in (("faixa_esforco", "baixa"), ("comissao_esperada_brl", 1)):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db_conn.execute(f"UPDATE ia.atendimento SET {coluna} = %s WHERE atendimento_id = %s", (valor, res.atendimento_id))
    a2 = ler(db_conn, res.atendimento_id)
    assert (a2.faixa_esforco, a2.comissao_esperada_brl) == (a.faixa_esforco, a.comissao_esperada_brl)


@pytest.mark.banco
@pytest.mark.parametrize("faixa", ["alta", "muito_alta"])
def test_faixa_alta_sem_comissao_calculada_e_recusada_antes_do_banco(db_conn, relogio, versoes, faixa):
    with pytest.raises(EntradaInvalida):
        _abrir(db_conn, relogio, versoes, faixa=faixa, comissao=None)
    assert db_conn.execute("SELECT count(*) FROM ia.atendimento").fetchone() == (0,)


@pytest.mark.banco
def test_faixa_desconhecida_e_comissao_negativa_sao_recusadas(db_conn, relogio, versoes):
    with pytest.raises(EntradaInvalida):
        _abrir(db_conn, relogio, versoes, faixa="enorme")
    with pytest.raises(EntradaInvalida):
        _abrir(db_conn, relogio, versoes, faixa="media", comissao="-1")


@pytest.mark.banco
def test_relogio_sem_fuso_e_recusado(db_conn, versoes):
    from datetime import datetime

    with pytest.raises(ValueError, match="fuso"):
        _abrir(db_conn, lambda: datetime(2026, 11, 24, 13, 0), versoes)


# --- modo (contrato 08 §6) -------------------------------------------------------------------------------------------------------


@pytest.mark.banco
@pytest.mark.parametrize("global_", ["real", "sombra", "duble"])
def test_modo_nasce_do_global_fora_da_lista_de_teste(db_conn, relogio, versoes, global_):
    res = _abrir(db_conn, relogio, versoes, modo_global=global_)
    assert res.modo == global_ == ler(db_conn, res.atendimento_id).modo


@pytest.mark.banco
def test_chat_em_chats_teste_nasce_teste_e_aceita_persona(db_conn, relogio, versoes):
    res = _abrir(db_conn, relogio, versoes, entrada(persona_id="persona_teste_1"), modo_global="real", chats_teste=[CHAT])
    a = ler(db_conn, res.atendimento_id)
    assert (a.modo, a.persona_id) == ("teste", "persona_teste_1")


@pytest.mark.banco
def test_modo_teste_pedido_com_chat_fora_da_lista_e_recusado(db_conn, relogio, versoes):
    with pytest.raises(estado.ModoInvalido) as erro:
        _abrir(db_conn, relogio, versoes, entrada(modo="teste"), chats_teste=[OUTRO_CHAT])
    assert erro.value.codigo == "teste_fora_da_lista"


@pytest.mark.banco
def test_persona_so_em_chat_de_teste(db_conn, relogio, versoes):
    with pytest.raises(estado.ModoInvalido) as erro:
        _abrir(db_conn, relogio, versoes, entrada(persona_id="persona_teste_1"), modo_global="duble")
    assert erro.value.codigo == "persona_fora_de_teste"


@pytest.mark.banco
def test_modo_global_teste_e_recusado(db_conn, relogio, versoes):
    with pytest.raises(estado.ModoInvalido) as erro:
        _abrir(db_conn, relogio, versoes, modo_global="teste")
    assert erro.value.codigo == "modo_teste_global"


# --- idempotência e trava por chat -----------------------------------------------------------------------------------------------


@pytest.mark.banco
def test_replay_da_mesma_entrada_e_200_e_outro_corpo_e_409(db_conn, relogio, versoes):
    primeira = _abrir(db_conn, relogio, versoes)
    replay = _abrir(db_conn, relogio, versoes, entrada(disparado_por="outro.operador@exemplo.invalid", perfil={"x": 1}))
    assert (replay.atendimento_id, replay.repetido, replay.estado) == (primeira.atendimento_id, True, "reservado")
    with pytest.raises(ConflitoIdempotencia):
        _abrir(db_conn, relogio, versoes, entrada(pessoa_id=OUTRA_PESSOA))
    assert db_conn.execute("SELECT count(*) FROM ia.atendimento").fetchone() == (1,)


@pytest.mark.banco
def test_replay_devolve_o_gravado_mesmo_com_modo_e_versoes_novos(db_conn, relogio, versoes):
    primeira = _abrir(db_conn, relogio, versoes, modo_global="duble")
    db_conn.execute(
        "INSERT INTO ia.artefato_versao (tipo, numero, descricao, aprovado_por) VALUES ('motor', 5, 'x', 'dono.teste@exemplo.invalid')"
    )
    replay = _abrir(db_conn, relogio, versoes_vigentes(db_conn), modo_global="sombra", faixa="alta", comissao="10")
    assert (replay.atendimento_id, replay.modo, replay.repetido) == (primeira.atendimento_id, "duble", True)
    a = ler(db_conn, primeira.atendimento_id)
    assert (a.motor_versao, a.faixa_esforco) == (4, "media")  # nada é atualizado no replay


@pytest.mark.banco
def test_replay_vale_mesmo_com_o_chat_ocupado_e_corpo_diferente_e_409_nao_chat_ocupado(db_conn, relogio, versoes):
    primeira = _abrir(db_conn, relogio, versoes)  # o chat está ocupado por ela mesma (reservado tranca)
    assert _abrir(db_conn, relogio, versoes).atendimento_id == primeira.atendimento_id
    with pytest.raises(ConflitoIdempotencia):
        _abrir(db_conn, relogio, versoes, entrada(phone_id="0123456789abcdef01234567"))  # mesma chave, outro corpo, chat ocupado


@pytest.mark.banco
def test_replay_depois_de_encerrado_devolve_o_existente(db_conn, relogio, versoes):
    res = _abrir(db_conn, relogio, versoes)
    abortar(db_conn, res.atendimento_id, res.versao, motivo="teste", relogio=relogio)
    replay = _abrir(db_conn, relogio, versoes)
    assert (replay.atendimento_id, replay.repetido, replay.estado) == (res.atendimento_id, True, "encerrado")
    assert db_conn.execute("SELECT count(*) FROM ia.atendimento").fetchone() == (1,)


@pytest.mark.banco
def test_outra_origem_com_a_mesma_chave_e_outro_atendimento_mas_o_chat_continua_trancado(db_conn, relogio, versoes):
    _abrir(db_conn, relogio, versoes, origem="n8n_braco")
    with pytest.raises(ChatOcupado):
        _abrir(db_conn, relogio, versoes, origem="robo_esteira")


@pytest.mark.banco
def test_chat_ocupado_por_atendimento_nao_encerrado_levanta_chat_ocupado(db_conn, relogio, versoes):
    _abrir(db_conn, relogio, versoes, _entrada_n(1))
    with pytest.raises(ChatOcupado):
        _abrir(db_conn, relogio, versoes, entrada(chave_logica="venda:00000000000000000000000000000002", chat_id=_chat(1)))
    assert db_conn.execute("SELECT count(*) FROM ia.atendimento").fetchone() == (1,)


@pytest.mark.banco
def test_cada_estado_nao_terminal_tranca_o_chat(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes, 1)
    nova = lambda: _abrir(db_conn, relogio, versoes, entrada(chave_logica="venda:" + "9" * 32, chat_id=_chat(1)))  # noqa: E731
    with pytest.raises(ChatOcupado):  # aberto
        nova()
    v = aguardar_cliente(db_conn, atd, v, relogio=relogio)
    with pytest.raises(ChatOcupado):  # aguardando_cliente
        nova()
    v = repassar(db_conn, atd, v, modo="fila", motivo="pediu_humano", relogio=relogio)
    with pytest.raises(ChatOcupado):  # repassando
        nova()
    encerrar(db_conn, atd, v, desfecho="repassado", motivo="pediu_humano", relogio=relogio)
    assert nova().estado == "reservado"  # encerrado destranca


@pytest.mark.banco
def test_repassando_tranca_chat(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes, 1)
    v = repassar(db_conn, atd, v, modo="fila", motivo="pediu_humano", relogio=relogio)
    outra = entrada(chave_logica="venda:" + "8" * 32, chat_id=_chat(1))
    with pytest.raises(ChatOcupado):
        _abrir(db_conn, relogio, versoes, outra)
    encerrar(db_conn, atd, v, desfecho="repassado", motivo="pediu_humano", relogio=relogio)
    assert _abrir(db_conn, relogio, versoes, outra).estado == "reservado"


@pytest.mark.banco
def test_varios_atendimentos_sequenciais_no_mesmo_chat(db_conn, relogio, versoes):
    """O índice único é PARCIAL (estado <> 'encerrado'): o mesmo chat tem vários atendimentos em sequência e só 1 vivo."""
    desfechos = ["sem_resposta", "sem_venda", "expirado"]
    for i, desfecho in enumerate(desfechos):
        res = _abrir(db_conn, relogio, versoes, entrada(chave_logica=f"venda:{i + 1:032x}", chat_id=CHAT))
        v = _iniciar(db_conn, relogio, res.atendimento_id, res.versao)
        encerrar(db_conn, res.atendimento_id, v, desfecho=desfecho, motivo="fim_de_teste", relogio=relogio)
    vivo = _abrir(db_conn, relogio, versoes, entrada(chave_logica="venda:" + "f" * 32, chat_id=CHAT))
    with pytest.raises(ChatOcupado):
        _abrir(db_conn, relogio, versoes, entrada(chave_logica="venda:" + "e" * 32, chat_id=CHAT))
    contagem = db_conn.execute(
        "SELECT count(*), count(*) FILTER (WHERE estado <> 'encerrado') FROM ia.atendimento WHERE chat_id = %s", (CHAT,)
    ).fetchone()
    assert contagem == (4, 1) and vivo.estado == "reservado"


# --- iniciar / abortar / aguardar / retomar ---------------------------------------------------------------------------------------


@pytest.mark.banco
def test_iniciar_leva_a_aberto_e_muda_fase_para_e1_e_renova_lease_5min(db_conn, relogio, versoes):
    res = _abrir(db_conn, relogio, versoes)
    relogio.avancar(seconds=30)
    v = iniciar(
        db_conn,
        res.atendimento_id,
        res.versao,
        chatbot_antes="ligado",
        chatbot_estado="desligado_pela_ia",
        responsavel_antes="consultor.x",
        relogio=relogio,
    )
    a = ler(db_conn, res.atendimento_id)
    assert v == 2 == a.versao
    assert (a.estado, a.fase, a.assumido_em, a.responsavel_antes) == ("aberto", "E1", relogio(), "consultor.x")
    assert (a.chatbot_antes, a.chatbot_estado) == ("ligado", "desligado_pela_ia")
    assert LEASE_TURNO_S == 300 and a.lease_ate == relogio() + timedelta(seconds=300) and a.atualizado_em == relogio()


@pytest.mark.banco
def test_iniciar_so_vale_a_partir_de_reservado(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    with pytest.raises(TransicaoInvalida):
        _iniciar(db_conn, relogio, atd, v)
    assert _estado_e_versao(db_conn, atd) == ("aberto", v)


@pytest.mark.banco
def test_iniciar_recusa_chatbot_inconsistente(db_conn, relogio, versoes):
    res = _abrir(db_conn, relogio, versoes)
    with pytest.raises(EntradaInvalida):
        iniciar(db_conn, res.atendimento_id, res.versao, chatbot_antes="ligado", chatbot_estado="nada", relogio=relogio)
    with pytest.raises(EntradaInvalida):  # chatbot mexido sem saber o estado anterior (CHECK atendimento_chatbot_check, antes do banco)
        iniciar(db_conn, res.atendimento_id, res.versao, chatbot_antes=None, chatbot_estado="desligado_pela_ia", relogio=relogio)


@pytest.mark.banco
def test_reservado_abortado(db_conn, relogio, versoes):
    res = _abrir(db_conn, relogio, versoes)
    relogio.avancar(seconds=5)
    v = abortar(db_conn, res.atendimento_id, res.versao, motivo="canal_indisponivel", relogio=relogio)
    a = ler(db_conn, res.atendimento_id)
    assert (a.estado, a.desfecho, a.motivo_desfecho, a.assumido_em, a.lease_ate, a.encerrado_em, a.versao) == (
        "encerrado", "abortado", "canal_indisponivel", None, None, relogio(), v
    )  # fmt: skip


@pytest.mark.banco
def test_abortar_depois_de_iniciar_e_invalido(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    with pytest.raises(TransicaoInvalida):
        abortar(db_conn, atd, v, motivo="tarde_demais", relogio=relogio)
    assert _estado_e_versao(db_conn, atd) == ("aberto", v)


@pytest.mark.banco
def test_encerrar_com_abortado_depois_de_assumir_tambem_e_invalido(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    with pytest.raises(TransicaoInvalida):
        encerrar(db_conn, atd, v, desfecho="abortado", motivo="x", relogio=relogio)


@pytest.mark.banco
def test_aguardar_cliente_e_retomar_alternam_e_renovam_lease(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    relogio.avancar(minutes=4)
    v = aguardar_cliente(db_conn, atd, v, relogio=relogio)
    a = ler(db_conn, atd)
    assert (a.estado, a.fase, a.versao, a.lease_ate) == ("aguardando_cliente", "E1", v, relogio() + timedelta(seconds=LEASE_AGUARDANDO_S))
    relogio.avancar(hours=1)
    v = retomar(db_conn, atd, v, relogio=relogio)
    a = ler(db_conn, atd)
    assert (a.estado, a.versao, a.lease_ate) == ("aberto", v, relogio() + timedelta(seconds=300))


@pytest.mark.banco
def test_aguardar_so_de_aberto_e_retomar_so_de_aguardando(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    with pytest.raises(TransicaoInvalida):
        retomar(db_conn, atd, v, relogio=relogio)
    v = aguardar_cliente(db_conn, atd, v, relogio=relogio)
    with pytest.raises(TransicaoInvalida):
        aguardar_cliente(db_conn, atd, v, relogio=relogio)


# --- repasse em duas fases ------------------------------------------------------------------------------------------------------


@pytest.mark.banco
def test_repassar_em_duas_fases(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    v = repassar(db_conn, atd, v, modo="indicado", motivo="pediu_humano", relogio=relogio)
    a = ler(db_conn, atd)
    assert (a.estado, a.fase, a.repasse_modo, a.desfecho, a.lease_ate) == (
        "repassando",
        "E10",
        "indicado",
        None,
        relogio() + timedelta(seconds=300),
    )
    relogio.avancar(seconds=20)
    encerrar(db_conn, atd, v, desfecho="repassado", motivo="pediu_humano", consultor_ref="perfil-teste-01", relogio=relogio)
    a = ler(db_conn, atd)
    assert (a.estado, a.desfecho, a.repasse_modo, a.repasse_consultor_ref, a.fase, a.lease_ate) == (
        "encerrado", "repassado", "indicado", "perfil-teste-01", "E10", None
    )  # fmt: skip


@pytest.mark.banco
def test_repassar_de_aguardando_cliente_e_de_reservado_nao(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes, 1)
    v = aguardar_cliente(db_conn, atd, v, relogio=relogio)
    assert repassar(db_conn, atd, v, modo="fila", motivo="m", relogio=relogio) == v + 1
    res = _abrir(db_conn, relogio, versoes, _entrada_n(2))
    with pytest.raises(TransicaoInvalida):
        repassar(db_conn, res.atendimento_id, res.versao, modo="fila", motivo="m", relogio=relogio)


@pytest.mark.banco
def test_repassando_so_sai_para_encerrado(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    v = repassar(db_conn, atd, v, modo="fila", motivo="pediu_humano", relogio=relogio)
    for transicao in (aguardar_cliente, retomar):
        with pytest.raises(TransicaoInvalida):
            transicao(db_conn, atd, v, relogio=relogio)
    with pytest.raises(TransicaoInvalida):
        repassar(db_conn, atd, v, modo="fila", motivo="de_novo", relogio=relogio)


@pytest.mark.banco
def test_modo_de_repasse_desconhecido_e_recusado(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    with pytest.raises(EntradaInvalida):
        repassar(db_conn, atd, v, modo="qualquer", motivo="m", relogio=relogio)


# --- sombra ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.banco
@pytest.mark.parametrize("desfecho", ["vendeu", "repassado"])
def test_sombra_nao_fecha_vendeu_nem_repassado(db_conn, relogio, versoes, desfecho):
    atd, v = _aberto(db_conn, relogio, versoes, modo_global="sombra")
    if desfecho == "repassado":
        v = repassar(db_conn, atd, v, modo="fila", motivo="pediu_humano", relogio=relogio)  # `repassado` só sai de `repassando`
    estado_antes = _estado_e_versao(db_conn, atd)
    with pytest.raises(TransicaoInvalida) as erro:
        encerrar(db_conn, atd, v, desfecho=desfecho, motivo="x", relogio=relogio)
    assert erro.value.restricao == "atendimento_sombra_check"
    assert _estado_e_versao(db_conn, atd) == estado_antes


@pytest.mark.banco
def test_repasse_simulado_em_sombra_fecha_sem_venda(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes, modo_global="sombra")
    v = repassar(db_conn, atd, v, modo="fila", motivo="pediu_humano", relogio=relogio)
    encerrar(db_conn, atd, v, desfecho="sem_venda", motivo="repasse_simulado", relogio=relogio)
    a = ler(db_conn, atd)
    assert (a.estado, a.desfecho, a.motivo_desfecho, a.repasse_modo) == (
        "encerrado",
        "sem_venda",
        "repasse_simulado",
        None,
    )  # repasse_* só vale com repassado


# --- encerrar -------------------------------------------------------------------------------------------------------------------


@pytest.mark.banco
def test_encerrar_vendeu_a_partir_de_aberto_zera_lease_e_grava_contexto(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    relogio.avancar(minutes=3)
    encerrar(db_conn, atd, v, desfecho="vendeu", motivo="contrato_ok", contexto_codigos=("t7_ok", "pix"), relogio=relogio)
    a = ler(db_conn, atd)
    assert (a.estado, a.desfecho, a.lease_ate, a.encerrado_em, a.contexto_codigos, a.retoma_em) == (
        "encerrado", "vendeu", None, relogio(), ("t7_ok", "pix"), None
    )  # fmt: skip


@pytest.mark.banco
@pytest.mark.parametrize("passos", [0, 1, 2], ids=["de-aberto", "de-aguardando", "de-repassando"])
def test_encerrar_vale_de_qualquer_estado_nao_terminal(db_conn, relogio, versoes, passos):
    atd, v = _aberto(db_conn, relogio, versoes)
    if passos == 1:
        v = aguardar_cliente(db_conn, atd, v, relogio=relogio)
    if passos == 2:
        v = repassar(db_conn, atd, v, modo="fila", motivo="m", relogio=relogio)
    encerrar(db_conn, atd, v, desfecho="sem_resposta", motivo="sem_resposta_do_cliente", relogio=relogio)
    assert ler(db_conn, atd).estado == "encerrado"


@pytest.mark.banco
def test_encerrado_e_terminal(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    v = encerrar(db_conn, atd, v, desfecho="sem_venda", motivo="fim", relogio=relogio)
    for chamar in (
        lambda: encerrar(db_conn, atd, v, desfecho="sem_venda", motivo="fim", relogio=relogio),
        lambda: aguardar_cliente(db_conn, atd, v, relogio=relogio),
        lambda: retomar(db_conn, atd, v, relogio=relogio),
        lambda: repassar(db_conn, atd, v, modo="fila", motivo="m", relogio=relogio),
        lambda: abortar(db_conn, atd, v, motivo="m", relogio=relogio),
        lambda: _iniciar(db_conn, relogio, atd, v),
    ):
        with pytest.raises(TransicaoInvalida):
            chamar()
    assert _estado_e_versao(db_conn, atd) == ("encerrado", v)


@pytest.mark.banco
def test_desfecho_incompativel_com_o_gatilho_e_recusado_pelo_check(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)  # gatilho venda
    with pytest.raises(TransicaoInvalida) as erro:
        encerrar(db_conn, atd, v, desfecho="destravou", motivo="x", relogio=relogio)
    assert erro.value.restricao == "atendimento_desfecho_check"


@pytest.mark.banco
def test_opt_out_e_humano_assumiu_exigem_o_timestamp_no_mesmo_update(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    with pytest.raises(EntradaInvalida):
        encerrar(db_conn, atd, v, desfecho="opt_out", motivo="pediu_para_parar", relogio=relogio)
    with pytest.raises(EntradaInvalida):
        encerrar(db_conn, atd, v, desfecho="sem_venda", motivo="humano_assumiu", relogio=relogio)
    assert _estado_e_versao(db_conn, atd) == ("aberto", v)
    # o mesmo vale se alguém contornar `encerrar` e chamar `aplicar` direto: o CHECK do banco barra no mesmo UPDATE
    cru = Mudancas(estado="encerrado", desfecho="opt_out", lease_ate=None, encerrado_em=relogio())
    with pytest.raises(TransicaoInvalida) as erro:
        aplicar(db_conn, atd, v, cru, agora=relogio())
    assert erro.value.restricao == "atendimento_qualidade_check"
    quando = relogio() - timedelta(minutes=1)
    encerrar(db_conn, atd, v, desfecho="opt_out", motivo="pediu_para_parar", opt_out_em=quando, relogio=relogio)
    assert (ler(db_conn, atd).desfecho, ler(db_conn, atd).opt_out_em) == ("opt_out", quando)


@pytest.mark.banco
def test_humano_assumiu_grava_o_timestamp_junto_do_motivo(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    quando = relogio() - timedelta(seconds=90)
    encerrar(db_conn, atd, v, desfecho="sem_venda", motivo="humano_assumiu", humano_assumiu_em=quando, relogio=relogio)
    a = ler(db_conn, atd)
    assert (a.motivo_desfecho, a.humano_assumiu_em) == ("humano_assumiu", quando)


# --- CAS por versao -------------------------------------------------------------------------------------------------------------


@pytest.mark.banco
def test_transicao_com_versao_velha_falha(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    antes = ler(db_conn, atd)
    with pytest.raises(ConflitoVersao):
        aguardar_cliente(db_conn, atd, v - 1, relogio=relogio)
    with pytest.raises(ConflitoVersao):
        aguardar_cliente(db_conn, atd, v + 1, relogio=relogio)
    assert ler(db_conn, atd) == antes  # nada muda


@pytest.mark.banco
def test_toda_transicao_incrementa_versao_em_um_e_atualiza_atualizado_em(db_conn, relogio, versoes):
    res = _abrir(db_conn, relogio, versoes)
    visto = [res.versao]
    relogio.avancar(seconds=1)
    visto.append(_iniciar(db_conn, relogio, res.atendimento_id, visto[-1]))
    for transicao in (aguardar_cliente, retomar):
        relogio.avancar(seconds=1)
        visto.append(transicao(db_conn, res.atendimento_id, visto[-1], relogio=relogio))
        assert ler(db_conn, res.atendimento_id).atualizado_em == relogio()
    assert visto == [1, 2, 3, 4]


@pytest.mark.banco
def test_transicao_em_atendimento_inexistente(db_conn, relogio, versoes):
    import uuid

    with pytest.raises(AtendimentoInexistente):
        aguardar_cliente(db_conn, uuid.uuid4(), 1, relogio=relogio)
    with pytest.raises(AtendimentoInexistente):
        ler(db_conn, uuid.uuid4())


@pytest.mark.banco
def test_conflito_versao_em_corrida(banco: Banco, relogio, versoes_semeadas_no_banco):
    """Duas transições com a MESMA `versao`, ao mesmo tempo, em conexões distintas: uma vence, a outra é ConflitoVersao."""
    with banco.sessao("ia_app_a") as conn:
        res = _abrir(conn, relogio, versoes_semeadas_no_banco)
        v = _iniciar(conn, relogio, res.atendimento_id, res.versao)
    largada = threading.Barrier(2)

    def correr(transicao):
        with banco.sessao("ia_app_a") as outra:
            largada.wait(timeout=10)
            try:
                return transicao(outra)
            except ConflitoVersao as erro:
                return erro

    aguardar = lambda c: aguardar_cliente(c, res.atendimento_id, v, relogio=relogio)  # noqa: E731
    fechar = lambda c: encerrar(c, res.atendimento_id, v, desfecho="sem_venda", motivo="fim", relogio=relogio)  # noqa: E731
    with ThreadPoolExecutor(2) as pool:
        resultados = [f.result(timeout=30) for f in [pool.submit(correr, aguardar), pool.submit(correr, fechar)]]
    vencedores = [r for r in resultados if isinstance(r, int)]
    perdedores = [r for r in resultados if isinstance(r, ConflitoVersao)]
    assert len(vencedores) == 1 and len(perdedores) == 1, resultados
    with banco.sessao("ia_app_a") as conn:
        assert ler(conn, res.atendimento_id).versao == v + 1


@pytest.mark.banco
def test_duas_aberturas_concorrentes_do_mesmo_chat_so_uma_vence(banco: Banco, relogio, versoes_semeadas_no_banco):
    largada = threading.Barrier(2)

    def abrir_chave(n: int):
        with banco.sessao("ia_app_a") as conn:
            largada.wait(timeout=10)
            try:
                return _abrir(conn, relogio, versoes_semeadas_no_banco, entrada(chave_logica=f"venda:{n:032x}", chat_id=CHAT))
            except ChatOcupado as erro:
                return erro

    with ThreadPoolExecutor(2) as pool:
        resultados = [f.result(timeout=30) for f in [pool.submit(abrir_chave, 1), pool.submit(abrir_chave, 2)]]
    assert sorted(type(r).__name__ for r in resultados) == ["ChatOcupado", "Resultado"]


@pytest.mark.banco
def test_duas_aberturas_concorrentes_da_mesma_chave_geram_um_atendimento_e_um_replay(banco: Banco, relogio, versoes_semeadas_no_banco):
    """Em vários rounds (a janela é estreita): o índice do chat pode reclamar antes do da chave, e isso é replay, não `ChatOcupado`."""
    rounds = 25
    largada = threading.Barrier(2)

    def abrir_igual(_):
        achados = []
        with banco.sessao("ia_app_a") as conn:
            for n in range(1, rounds + 1):
                largada.wait(timeout=10)
                achados.append(_abrir(conn, relogio, versoes_semeadas_no_banco, _entrada_n(n)))
        return achados

    with ThreadPoolExecutor(2) as pool:
        a, b = [f.result(timeout=60) for f in [pool.submit(abrir_igual, 1), pool.submit(abrir_igual, 2)]]
    for um, outro in zip(a, b, strict=True):
        assert um.atendimento_id == outro.atendimento_id
        assert sorted((um.repetido, outro.repetido)) == [False, True]


# --- CHECK cruzado fase x estado e a estrutura do pausado ------------------------------------------------------------------------


@pytest.mark.banco
@pytest.mark.parametrize(
    "mudanca,fase",
    [
        pytest.param(Mudancas(estado="aguardando_cliente"), "E0", id="nao-reservado-com-fase-E0"),
        pytest.param(Mudancas(estado="repassando"), "E4", id="repassando-fora-de-E10"),
        pytest.param(Mudancas(estado="pausado", retoma_em=INICIO + timedelta(hours=3), lease_ate=INICIO + timedelta(hours=4),
                              estado_conversa=EstadoConversa(fase="E3", pausa=Pausa(retoma_fase="E3"))), "E7", id="pausado-em-E7"),
        pytest.param(Mudancas(estado="pausado", retoma_em=INICIO + timedelta(hours=3), lease_ate=INICIO + timedelta(hours=4),
                              estado_conversa=EstadoConversa(fase="E3", pausa=Pausa(retoma_fase="E4"))), "E3", id="pausado-com-retoma-fase-diferente"),
    ],
)  # fmt: skip
def test_check_fase_estado_cruzado(db_conn, relogio, versoes, mudanca, fase):
    atd, v = _aberto(db_conn, relogio, versoes)  # aberto, E1, assumido_em gravado: só o CHECK cruzado pode reprovar
    with pytest.raises(TransicaoInvalida) as erro:
        aplicar(db_conn, atd, v, mudanca, agora=relogio(), fase=fase)
    assert erro.value.restricao == "atendimento_conversa_check"
    assert _estado_e_versao(db_conn, atd) == ("aberto", v)


@pytest.mark.banco
def test_check_fase_estado_cruzado_reservado_exige_e0(db_conn, relogio, versoes):
    res = _abrir(db_conn, relogio, versoes)
    with pytest.raises(TransicaoInvalida) as erro:
        aplicar(db_conn, res.atendimento_id, res.versao, Mudancas(), agora=relogio(), fase="E3")
    assert erro.value.restricao == "atendimento_conversa_check"


@pytest.mark.banco
def test_transicao_que_muda_estado_atualiza_a_fase_junto(db_conn, relogio, versoes):
    """Sem o `fase` no mesmo UPDATE o CHECK reprova: provado acima. Aqui, o caminho feliz de cada transição respeita a tabela."""
    atd, v = _aberto(db_conn, relogio, versoes)
    pares = []
    for transicao in (
        lambda v: aguardar_cliente(db_conn, atd, v, relogio=relogio),
        lambda v: retomar(db_conn, atd, v, relogio=relogio),
        lambda v: repassar(db_conn, atd, v, modo="fila", motivo="m", relogio=relogio),
    ):
        v = transicao(v)
        a = ler(db_conn, atd)
        pares.append((a.estado, a.fase))
    assert pares == [("aguardando_cliente", "E1"), ("aberto", "E1"), ("repassando", "E10")]


@pytest.mark.banco
def test_estrutura_aceita_pausado_e_dele_se_repassa_e_se_encerra(db_conn, relogio, versoes):
    """O enum e os CHECKs aceitam `pausado` por `aplicar` direto (as transições `pausar`/`sair_da_pausa` são da B5.7b); o ciclo parte dele."""
    atd, v = _aberto(db_conn, relogio, versoes, 1)
    retoma = relogio() + timedelta(hours=3)
    pausa = EstadoConversa(fase="E3", pausa=Pausa(retoma_fase="E3"))
    v = aplicar(
        db_conn,
        atd,
        v,
        Mudancas(estado="pausado", retoma_em=retoma, lease_ate=retoma + timedelta(minutes=30), estado_conversa=pausa),
        agora=relogio(),
    )
    a = ler(db_conn, atd)
    assert (a.estado, a.fase, a.retoma_em) == ("pausado", "E3", retoma)
    with pytest.raises(ChatOcupado):  # pausado tranca o chat
        _abrir(db_conn, relogio, versoes, entrada(chave_logica="venda:" + "7" * 32, chat_id=_chat(1)))
    v = repassar(db_conn, atd, v, modo="fila", motivo="pediu_humano", relogio=relogio)
    a = ler(db_conn, atd)
    assert (a.estado, a.fase, a.retoma_em) == ("repassando", "E10", None)  # saiu da pausa: retoma_em volta a NULL
    # e um segundo, pausado, encerra direto
    atd2, v2 = _aberto(db_conn, relogio, versoes, 2)
    v2 = aplicar(db_conn, atd2, v2, Mudancas(estado="pausado", retoma_em=retoma, lease_ate=retoma, estado_conversa=pausa), agora=relogio())
    encerrar(db_conn, atd2, v2, desfecho="expirado", motivo="pausa_vencida", relogio=relogio)
    assert ler(db_conn, atd2).estado == "encerrado"


@pytest.mark.banco
def test_pausado_com_lease_menor_que_retoma_em_e_recusado(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    retoma = relogio() + timedelta(hours=3)
    with pytest.raises(TransicaoInvalida) as erro:
        aplicar(
            db_conn, atd, v,
            Mudancas(estado="pausado", retoma_em=retoma, lease_ate=retoma - timedelta(minutes=1), estado_conversa=EstadoConversa(fase="E3", pausa=Pausa(retoma_fase="E3"))),
            agora=relogio(),
        )  # fmt: skip
    assert erro.value.restricao == "atendimento_conversa_check"


@pytest.mark.banco
def test_pausar_e_sair_da_pausa(db_conn, relogio, versoes):
    """B5.7b: as transições de pausa (a cobertura completa está em `test_estado_pausa.py` e `test_agenda_jobs.py`)."""
    atd, v = _aberto(db_conn, relogio, versoes)
    v = gravar_estado_conversa(db_conn, atd, v, EstadoConversa(fase="E3"), relogio=relogio)
    retoma = relogio() + timedelta(hours=3)
    v = estado_pausa.pausar(db_conn, atd, v, retoma_em=retoma, retoma_fase="E3", relogio=relogio)
    a = ler(db_conn, atd)
    assert (a.estado, a.fase, a.retoma_em, a.lease_ate) == ("pausado", "E3", retoma, retoma + timedelta(minutes=30))
    assert a.estado_conversa["pausa"] == {"retoma_fase": "E3"}
    estado_pausa.sair_da_pausa(db_conn, atd, v, relogio=relogio)
    a = ler(db_conn, atd)
    assert (a.estado, a.fase, a.retoma_em) == ("aberto", "E3", None) and "pausa" not in a.estado_conversa


@pytest.mark.banco
def test_abrir_agendado_reserva_de_vida_longa(db_conn, relogio, versoes):
    """B5.7b: `reservado` de agendamento, sem tocar o chat, com `lease_ate >= retoma_em` (a cobertura completa está em `test_estado_pausa.py`)."""
    retoma = relogio() + timedelta(hours=5)
    r = estado_pausa.abrir_agendado(
        db_conn, origem="n8n_braco", chave_logica=f"agendar:{CHAT}:0123456789abcdef", disparado_por="dialogo_agendar",
        pessoa_id=uuid.UUID(PESSOA), chat_id=CHAT, phone_id="89abcdef0123456789abcdef", clt_job_id=uuid.uuid4(), versoes=versoes,
        modo="duble", retoma_em=retoma, ultimo_cliente_em=relogio(), agora=relogio(),
    )  # fmt: skip
    a = ler(db_conn, r.atendimento_id)
    assert (a.estado, a.gatilho, a.fase, a.retoma_em, a.assumido_em) == ("reservado", "agendamento", "E0", retoma, None)
    assert a.lease_ate == retoma + timedelta(minutes=30)
