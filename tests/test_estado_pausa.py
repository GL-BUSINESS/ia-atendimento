"""Pausa combinada (B5.7b, estudo M): `pausar`, `sair_da_pausa`, `abrir_agendado` e `iniciar_agendado` contra o PG 18 real.

Cada regra tem o teste da recusa que a barra: fase de E7 não pausa, lease nunca abaixo de `retoma_em`, CAS, estado de origem errado e a chave
`pausa` do `estado_conversa` que só existe em `pausado`. Sem PII (`tests/estado_apoio.py`).
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from ia_atendimento import estado, estado_pausa
from ia_atendimento.estado import (
    LEASE_AGUARDANDO_S,
    LEASE_TURNO_S,
    ChatOcupado,
    ConflitoVersao,
    DadoRecusado,
    EntradaInvalida,
    TransicaoInvalida,
    ler,
)
from ia_atendimento.estado_conversa import EstadoConversa, gravar_estado_conversa, registrar_mensagem_do_cliente
from tests.apoio_agenda import novo_aberto, novo_agendado
from tests.estado_apoio import CHAT, entrada

pytestmark = pytest.mark.banco


def _retoma(relogio, horas: float = 3):
    return relogio() + timedelta(hours=horas)


# --- pausar -----------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fase", "pausa"),
    [("E1", False), ("E2", True), ("E3", True), ("E4", True), ("E5", True), ("E6", True), ("E7", False), ("E8", True), ("E9", False)],
)
def test_pausa_so_de_e2_a_e6_e_e8(db_conn, relogio, versoes, fase, pausa):
    atd, v, _ = novo_aberto(db_conn, relogio, versoes, fase=fase)
    if not pausa:
        with pytest.raises((EntradaInvalida, TransicaoInvalida)):
            estado_pausa.pausar(db_conn, atd, v, retoma_em=_retoma(relogio), retoma_fase=fase, relogio=relogio)
        assert ler(db_conn, atd).estado == "aberto" and ler(db_conn, atd).versao == v
        return
    estado_pausa.pausar(db_conn, atd, v, retoma_em=_retoma(relogio), retoma_fase=fase, relogio=relogio)
    a = ler(db_conn, atd)
    assert (a.estado, a.fase, a.estado_conversa["pausa"]["retoma_fase"]) == ("pausado", fase, fase)


def test_pausar_nunca_de_e7_nem_com_retoma_fase_e7(db_conn, relogio, versoes):
    """E7 é T7/T8 em voo. Barrado por `retoma_fase` (E7 ou fora da lista) e pela FASE ATUAL (E7 com `retoma_fase` de outra fase)."""
    em_e7, v7, _ = novo_aberto(db_conn, relogio, versoes, fase="E7")
    with pytest.raises(TransicaoInvalida):
        estado_pausa.pausar(
            db_conn, em_e7, v7, retoma_em=_retoma(relogio), retoma_fase="E3", relogio=relogio
        )  # a fase atual não é a de volta
    em_e3, v3, _ = novo_aberto(db_conn, relogio, versoes, fase="E3")
    for fase in ("E7", "E0", "E1", "E9", "E10", "E", "E33", "e3", "", "E3 "):
        with pytest.raises(EntradaInvalida):
            estado_pausa.pausar(db_conn, em_e3, v3, retoma_em=_retoma(relogio), retoma_fase=fase, relogio=relogio)
    assert ler(db_conn, em_e3).versao == v3 and ler(db_conn, em_e7).estado == "aberto"
    with pytest.raises(TransicaoInvalida):  # a fase atual (E3) não é a de volta pedida (E5): não se pula de fase pausando
        estado_pausa.pausar(db_conn, em_e3, v3, retoma_em=_retoma(relogio), retoma_fase="E5", relogio=relogio)


def test_pausar_grava_lease_ate_retoma_em_mais_folga(db_conn, relogio, versoes):
    atd, v, _ = novo_aberto(db_conn, relogio, versoes)
    retoma = _retoma(relogio, 20)
    estado_pausa.pausar(db_conn, atd, v, retoma_em=retoma, retoma_fase="E3", relogio=relogio)
    a = ler(db_conn, atd)
    assert (a.retoma_em, a.lease_ate) == (retoma, retoma + timedelta(minutes=30))  # padrão = agenda_folga_min
    assert a.lease_ate >= a.retoma_em
    outro, vo, _ = novo_aberto(db_conn, relogio, versoes)
    estado_pausa.pausar(db_conn, outro, vo, retoma_em=retoma, retoma_fase="E3", folga_min=0, relogio=relogio)
    assert ler(db_conn, outro).lease_ate == retoma  # folga zero: o CHECK `lease_ate >= retoma_em` aceita a igualdade


def test_pausar_recusa_folga_negativa_e_retoma_em_que_nao_esta_no_futuro(db_conn, relogio, versoes):
    atd, v, _ = novo_aberto(db_conn, relogio, versoes)
    with pytest.raises(EntradaInvalida, match="folga"):
        estado_pausa.pausar(db_conn, atd, v, retoma_em=_retoma(relogio), retoma_fase="E3", folga_min=-1, relogio=relogio)
    for retoma in (relogio(), relogio() - timedelta(minutes=1)):
        with pytest.raises(EntradaInvalida, match="retoma_em"):
            estado_pausa.pausar(db_conn, atd, v, retoma_em=retoma, retoma_fase="E3", relogio=relogio)
    assert ler(db_conn, atd).estado == "aberto"


def test_pausar_grava_a_pausa_no_json_com_a_referencia_do_agendamento(db_conn, relogio, versoes):
    atd, v, _ = novo_aberto(db_conn, relogio, versoes, fase="E5")
    ref = str(uuid.UUID("01912345-6789-7abc-8def-0123456789ab"))
    estado_pausa.pausar(db_conn, atd, v, retoma_em=_retoma(relogio), retoma_fase="E5", agendamento_ref=ref, relogio=relogio)
    a = ler(db_conn, atd)
    assert a.estado_conversa == {"fase": "E5", "pausa": {"agendamento_ref": ref, "retoma_fase": "E5"}}


def test_pausar_preserva_o_resto_do_estado_da_conversa(db_conn, relogio, versoes):
    atd, v, _ = novo_aberto(db_conn, relogio, versoes)
    conversa = EstadoConversa(fase="E4", campos_coletados=("renda",), objecoes=("parcela_alta",), flags={"quer_pensar": True})
    v = gravar_estado_conversa(db_conn, atd, v, conversa, relogio=relogio)
    estado_pausa.pausar(db_conn, atd, v, retoma_em=_retoma(relogio), retoma_fase="E4", relogio=relogio)
    guardado = ler(db_conn, atd).estado_conversa
    assert {k: guardado[k] for k in ("campos_coletados", "objecoes", "flags")} == {
        "campos_coletados": ["renda"], "objecoes": ["parcela_alta"], "flags": {"quer_pensar": True},
    }  # fmt: skip
    assert guardado["pausa"] == {"retoma_fase": "E4"}


def test_pausar_referencia_invalida_nao_ecoa_o_valor(db_conn, relogio, versoes):
    atd, v, _ = novo_aberto(db_conn, relogio, versoes)
    with pytest.raises(EntradaInvalida) as erro:
        estado_pausa.pausar(db_conn, atd, v, retoma_em=_retoma(relogio), retoma_fase="E3", agendamento_ref="12345678909", relogio=relogio)
    assert "12345678909" not in str(erro.value) and "12345678909" not in repr(erro.value.__cause__)
    assert ler(db_conn, atd).estado == "aberto"


def test_pausar_de_aguardando_cliente_e_so_dele_ou_de_aberto(db_conn, relogio, versoes):
    atd, v, _ = novo_aberto(db_conn, relogio, versoes)
    v = estado.aguardar_cliente(db_conn, atd, v, relogio=relogio)
    v = estado_pausa.pausar(db_conn, atd, v, retoma_em=_retoma(relogio), retoma_fase="E3", relogio=relogio)
    assert ler(db_conn, atd).estado == "pausado"
    with pytest.raises(TransicaoInvalida):  # já pausado: não se pausa de novo (nem se estica a pausa por aqui)
        estado_pausa.pausar(db_conn, atd, v, retoma_em=_retoma(relogio, 4), retoma_fase="E3", relogio=relogio)
    for destino, preparo in (
        ("repassando", lambda a, ver: estado.repassar(db_conn, a, ver, modo="fila", motivo="m", relogio=relogio)),
        ("encerrado", lambda a, ver: estado.encerrar(db_conn, a, ver, desfecho="sem_venda", motivo="m", relogio=relogio)),
    ):
        outro, vo, _ = novo_aberto(db_conn, relogio, versoes)
        vo = preparo(outro, vo)
        with pytest.raises(TransicaoInvalida):
            estado_pausa.pausar(db_conn, outro, vo, retoma_em=_retoma(relogio), retoma_fase="E3", relogio=relogio)
        assert ler(db_conn, outro).estado == destino


def test_pausar_de_reservado_e_recusado(db_conn, relogio, versoes):
    r = estado.abrir(
        db_conn,
        origem="n8n_braco",
        entrada=entrada(),
        versoes=versoes,
        modo_global="duble",
        chats_teste=frozenset(),
        faixa_esforco="media",
        comissao_esperada_brl=None,
        relogio=relogio,
    )
    with pytest.raises(TransicaoInvalida):
        estado_pausa.pausar(db_conn, r.atendimento_id, r.versao, retoma_em=_retoma(relogio), retoma_fase="E3", relogio=relogio)


def test_pausar_com_versao_velha_e_conflito_e_nao_muda_nada(db_conn, relogio, versoes):
    atd, v, _ = novo_aberto(db_conn, relogio, versoes)
    estado.renovar_lease(db_conn, atd, v, relogio=relogio)  # alguém mexeu: a versão andou
    with pytest.raises(ConflitoVersao):
        estado_pausa.pausar(db_conn, atd, v, retoma_em=_retoma(relogio), retoma_fase="E3", relogio=relogio)
    assert ler(db_conn, atd).estado == "aberto"


# --- sair_da_pausa ------------------------------------------------------------------------------------------------------------------------


def test_sair_da_pausa_volta_a_aberto_na_fase_gravada_sem_pausa_nem_retoma_em(db_conn, relogio, versoes):
    atd, v, _ = novo_aberto(db_conn, relogio, versoes, fase="E6")
    v = estado_pausa.pausar(db_conn, atd, v, retoma_em=_retoma(relogio), retoma_fase="E6", relogio=relogio)
    relogio.avancar(hours=3)  # chegou a hora
    estado_pausa.sair_da_pausa(db_conn, atd, v, relogio=relogio)
    a = ler(db_conn, atd)
    assert (a.estado, a.fase, a.retoma_em) == ("aberto", "E6", None)
    assert a.lease_ate == relogio() + timedelta(seconds=LEASE_TURNO_S)  # a volta é um turno: se falhar, o reaper devolve em 5 min
    assert a.estado_conversa == {"fase": "E6"}  # a chave `pausa` só existe em `pausado`


def test_sair_da_pausa_para_aguardando_cliente(db_conn, relogio, versoes):
    atd, v, _ = novo_aberto(db_conn, relogio, versoes)
    v = estado_pausa.pausar(db_conn, atd, v, retoma_em=_retoma(relogio), retoma_fase="E3", relogio=relogio)
    v = estado_pausa.sair_da_pausa(db_conn, atd, v, relogio=relogio, para="aguardando_cliente")
    a = ler(db_conn, atd)
    assert (a.estado, a.retoma_em, a.lease_ate) == ("aguardando_cliente", None, relogio() + timedelta(seconds=LEASE_AGUARDANDO_S))
    outro, vo, _ = novo_aberto(db_conn, relogio, versoes)
    vo = estado_pausa.pausar(db_conn, outro, vo, retoma_em=_retoma(relogio), retoma_fase="E3", relogio=relogio)
    espera = relogio() + timedelta(hours=6)
    estado_pausa.sair_da_pausa(db_conn, outro, vo, relogio=relogio, para="aguardando_cliente", lease_ate=espera)
    assert ler(db_conn, outro).lease_ate == espera


def test_sair_da_pausa_recusa_lease_incoerente_e_estado_errado(db_conn, relogio, versoes):
    atd, v, _ = novo_aberto(db_conn, relogio, versoes)
    with pytest.raises(TransicaoInvalida):  # aberto não está pausado
        estado_pausa.sair_da_pausa(db_conn, atd, v, relogio=relogio)
    v = estado_pausa.pausar(db_conn, atd, v, retoma_em=_retoma(relogio), retoma_fase="E3", relogio=relogio)
    with pytest.raises(EntradaInvalida):  # lease de espera só para aguardando_cliente
        estado_pausa.sair_da_pausa(db_conn, atd, v, relogio=relogio, lease_ate=relogio() + timedelta(hours=1))
    with pytest.raises(EntradaInvalida):  # e no futuro
        estado_pausa.sair_da_pausa(db_conn, atd, v, relogio=relogio, para="aguardando_cliente", lease_ate=relogio() - timedelta(seconds=1))
    assert ler(db_conn, atd).estado == "pausado" and ler(db_conn, atd).versao == v
    with pytest.raises(ConflitoVersao):
        estado_pausa.sair_da_pausa(db_conn, atd, v - 1, relogio=relogio)


def test_a_chave_pausa_so_existe_em_pausado_repassar_e_encerrar_a_tiram(db_conn, relogio, versoes):
    """Invariante: `pausa` no JSON se e só se `estado = 'pausado'`. Quem sai da pausa por outro caminho a leva junto no MESMO UPDATE."""
    for sair, estado_final in (
        (lambda a, v: estado.repassar(db_conn, a, v, modo="fila", motivo="pediu_humano", relogio=relogio), "repassando"),
        (lambda a, v: estado.encerrar(db_conn, a, v, desfecho="sem_resposta", motivo="pausa_vencida", relogio=relogio), "encerrado"),
        (lambda a, v: estado_pausa.sair_da_pausa(db_conn, a, v, relogio=relogio), "aberto"),
    ):
        atd, v, _ = novo_aberto(db_conn, relogio, versoes)
        v = estado_pausa.pausar(db_conn, atd, v, retoma_em=_retoma(relogio), retoma_fase="E3", relogio=relogio)
        assert "pausa" in ler(db_conn, atd).estado_conversa
        sair(atd, v)
        a = ler(db_conn, atd)
        assert a.estado == estado_final and "pausa" not in a.estado_conversa, estado_final
        assert a.retoma_em is None


# --- abrir_agendado e iniciar_agendado ------------------------------------------------------------------------------------------------------


def test_abrir_agendado_tranca_o_chat_sem_tocar_nele_e_o_abortar_funciona(db_conn, relogio, versoes):
    agora = relogio()
    retoma = agora + timedelta(hours=20)
    atd, v, chat = novo_agendado(db_conn, agora, versoes, retoma_em=retoma)
    a = ler(db_conn, atd)
    assert (a.estado, a.gatilho, a.fase, a.assumido_em, a.chatbot_estado) == ("reservado", "agendamento", "E0", None, "intocado")
    assert (a.retoma_em, a.lease_ate) == (retoma, retoma + timedelta(minutes=30))
    with pytest.raises(ChatOcupado):  # o chat fica trancado para qualquer outro atendimento
        estado.abrir(
            db_conn, origem="n8n_braco", entrada=entrada(chave_logica="venda:" + "9" * 32, chat_id=chat), versoes=versoes, modo_global="duble",
            chats_teste=frozenset(), faixa_esforco="media", comissao_esperada_brl=None, relogio=relogio,
        )  # fmt: skip
    estado.abortar(db_conn, atd, v, motivo="agenda_nao_disparou", relogio=relogio)  # o reservado que nunca disparou vira `abortado`
    b = ler(db_conn, atd)
    assert (b.estado, b.desfecho, b.retoma_em, b.lease_ate) == ("encerrado", "abortado", None, None)


def test_abrir_agendado_recusa_retoma_em_no_passado_chave_repetida_e_chat_ocupado(db_conn, relogio, versoes):
    agora = relogio()
    with pytest.raises(EntradaInvalida):
        novo_agendado(db_conn, agora, versoes, retoma_em=agora)
    with pytest.raises(EntradaInvalida):
        novo_agendado(db_conn, agora, versoes, retoma_em=agora + timedelta(hours=1), folga_min=-5)
    atd, _v, chat = novo_agendado(db_conn, agora, versoes, retoma_em=agora + timedelta(hours=1), folga_min=0)
    assert ler(db_conn, atd).lease_ate == ler(db_conn, atd).retoma_em  # folga zero cabe no CHECK
    base = {
        "origem": "n8n_braco", "disparado_por": "dialogo_agendar", "pessoa_id": uuid.uuid4(), "chat_id": chat,
        "phone_id": "89abcdef0123456789abcdef", "clt_job_id": uuid.uuid4(), "versoes": versoes, "modo": "duble",
        "retoma_em": agora + timedelta(hours=2), "ultimo_cliente_em": agora, "agora": agora,
    }  # fmt: skip
    with pytest.raises(ChatOcupado):
        estado_pausa.abrir_agendado(db_conn, chave_logica=f"agendar:{chat}:{'1' * 16}", **base)
    mesma_chave = f"agendar:{'f' * 24}:{'1' * 16}"
    estado_pausa.abrir_agendado(db_conn, chave_logica=mesma_chave, **{**base, "chat_id": "f" * 24})
    with pytest.raises(DadoRecusado):  # a mesma chave lógica em outro chat (a idempotência é do chamador)
        estado_pausa.abrir_agendado(db_conn, chave_logica=mesma_chave, **{**base, "chat_id": "e" * 24})
    with pytest.raises(ValueError):  # `agora` sem fuso
        estado_pausa.abrir_agendado(db_conn, chave_logica="agendar:x", **{**base, "agora": agora.replace(tzinfo=None)})


def test_iniciar_agendado_entra_na_fase_de_volta_e_zera_retoma_em(db_conn, relogio, versoes):
    agora = relogio()
    atd, v, _ = novo_agendado(db_conn, agora, versoes, retoma_em=agora + timedelta(hours=1))
    with pytest.raises(TransicaoInvalida):  # o `iniciar` comum deixaria `retoma_em` no `aberto` (CHECK) e cairia em E1
        estado.iniciar(db_conn, atd, v, chatbot_antes="desligado", chatbot_estado="desligado_pela_ia", relogio=relogio)
    for fase in ("E7", "E1", "E9", "E10"):
        with pytest.raises(EntradaInvalida):
            estado_pausa.iniciar_agendado(
                db_conn, atd, v, retoma_fase=fase, chatbot_antes="ligado", chatbot_estado="desligado_pela_ia", relogio=relogio
            )
    with pytest.raises(EntradaInvalida):
        estado_pausa.iniciar_agendado(
            db_conn, atd, v, retoma_fase="E8", chatbot_antes=None, chatbot_estado="desligado_pela_ia", relogio=relogio
        )
    estado_pausa.iniciar_agendado(
        db_conn, atd, v, retoma_fase="E8", chatbot_antes="ligado", chatbot_estado="desligado_pela_ia", relogio=relogio
    )
    a = ler(db_conn, atd)
    assert (a.estado, a.fase, a.retoma_em, a.assumido_em) == ("aberto", "E8", None, agora)
    assert a.lease_ate == agora + timedelta(seconds=LEASE_TURNO_S) and a.chatbot_antes == "ligado"


def test_iniciar_agendado_so_vale_para_o_gatilho_agendamento(db_conn, relogio, versoes):
    r = estado.abrir(
        db_conn,
        origem="n8n_braco",
        entrada=entrada(chat_id=CHAT),
        versoes=versoes,
        modo_global="duble",
        chats_teste=frozenset(),
        faixa_esforco="media",
        comissao_esperada_brl=None,
        relogio=relogio,
    )
    with pytest.raises(TransicaoInvalida):  # reservado de VENDA não vai para E8 por aqui
        estado_pausa.iniciar_agendado(
            db_conn,
            r.atendimento_id,
            r.versao,
            retoma_fase="E8",
            chatbot_antes="ligado",
            chatbot_estado="desligado_pela_ia",
            relogio=relogio,
        )
    assert ler(db_conn, r.atendimento_id).estado == "reservado"


# --- tetos de quem cria `pausado` (R1-05) ------------------------------------------------------------------------------------------------------


def test_os_padroes_dos_tetos_sao_os_do_registro_de_config():
    from ia_atendimento.chave_registro import PADROES
    from ia_atendimento.estado_pausa import AGENDA_FOLGA_MIN, AGENDA_MAX_PAUSADOS, AGENDA_TETO_HORAS

    assert (
        PADROES["agenda_folga_min"],
        PADROES["agenda_max_pausados"],
        PADROES["agenda_teto_horas"],
    ) == (AGENDA_FOLGA_MIN, AGENDA_MAX_PAUSADOS, AGENDA_TETO_HORAS)


def test_pausar_recusa_o_pausado_alem_de_agenda_max_pausados_e_libera_quando_um_sai(db_conn, relogio, versoes):
    pausados = []
    for _ in range(2):
        atd, v, _ = novo_aberto(db_conn, relogio, versoes)
        estado_pausa.pausar(db_conn, atd, v, retoma_em=_retoma(relogio), retoma_fase="E3", max_pausados=2, relogio=relogio)
        pausados.append(atd)
    terceiro, v3, _ = novo_aberto(db_conn, relogio, versoes)
    with pytest.raises(estado_pausa.LimiteDePausados, match="agenda_max_pausados = 2"):
        estado_pausa.pausar(db_conn, terceiro, v3, retoma_em=_retoma(relogio), retoma_fase="E3", max_pausados=2, relogio=relogio)
    assert ler(db_conn, terceiro).estado == "aberto" and ler(db_conn, terceiro).versao == v3, "recusado: nada mudou"
    um = ler(db_conn, pausados[0])
    estado_pausa.sair_da_pausa(db_conn, um.atendimento_id, um.versao, relogio=relogio)  # um acorda: abre vaga
    estado_pausa.pausar(db_conn, terceiro, v3, retoma_em=_retoma(relogio), retoma_fase="E3", max_pausados=2, relogio=relogio)
    assert ler(db_conn, terceiro).estado == "pausado"


def test_o_teto_de_pausados_vale_para_o_padrao_de_10(db_conn, relogio, versoes):
    for _ in range(10):
        atd, v, _ = novo_aberto(db_conn, relogio, versoes)
        estado_pausa.pausar(db_conn, atd, v, retoma_em=_retoma(relogio), retoma_fase="E3", relogio=relogio)
    onze, v11, _ = novo_aberto(db_conn, relogio, versoes)
    with pytest.raises(estado_pausa.LimiteDePausados):
        estado_pausa.pausar(db_conn, onze, v11, retoma_em=_retoma(relogio), retoma_fase="E3", relogio=relogio)


def test_pausas_concorrentes_nao_passam_juntas_do_teto(banco, relogio, versoes_semeadas_no_banco):
    """A contagem é feita SOB a trava: sem ela, cinco pausas simultâneas viam 0 pausados e as cinco passavam de `max_pausados = 2`."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    versoes = versoes_semeadas_no_banco
    with banco.sessao("ia_app_a") as conn:
        casos = [novo_aberto(conn, relogio, versoes)[:2] for _ in range(5)]
    largada = Barrier(5)

    def pausar(caso):
        atd, v = caso
        with banco.sessao("ia_app_a") as conn:
            largada.wait(timeout=10)
            try:
                estado_pausa.pausar(conn, atd, v, retoma_em=_retoma(relogio), retoma_fase="E3", max_pausados=2, relogio=relogio)
            except estado_pausa.LimiteDePausados:
                return "recusado"
            return "pausado"

    with ThreadPoolExecutor(5) as pool:
        resultados = [f.result(timeout=30) for f in [pool.submit(pausar, c) for c in casos]]
    assert sorted(resultados) == ["pausado", "pausado", "recusado", "recusado", "recusado"]


def test_pausar_recusa_retoma_em_alem_do_teto_de_23h_da_ultima_mensagem_do_cliente(db_conn, relogio, versoes):
    atd, v, _ = novo_aberto(db_conn, relogio, versoes)
    # sem `ultimo_cliente_em` conhecido o teto conta de agora
    with pytest.raises(EntradaInvalida, match="teto"):
        estado_pausa.pausar(db_conn, atd, v, retoma_em=_retoma(relogio, 23.01), retoma_fase="E3", relogio=relogio)
    # o cliente falou há 5 h: a janela de 24 h fecha em 18 h
    registrar_mensagem_do_cliente(db_conn, atd, relogio() - timedelta(hours=5), relogio=relogio)
    with pytest.raises(EntradaInvalida, match="teto"):
        estado_pausa.pausar(db_conn, atd, v, retoma_em=_retoma(relogio, 18.01), retoma_fase="E3", relogio=relogio)
    assert ler(db_conn, atd).estado == "aberto"
    estado_pausa.pausar(db_conn, atd, v, retoma_em=_retoma(relogio, 18), retoma_fase="E3", relogio=relogio)  # no teto exato, passa
    assert ler(db_conn, atd).estado == "pausado"
    # um 30 dias à frente nunca entra, nem com teto folgado de config
    outro, vo, _ = novo_aberto(db_conn, relogio, versoes)
    with pytest.raises(EntradaInvalida, match="teto"):
        estado_pausa.pausar(db_conn, outro, vo, retoma_em=_retoma(relogio, 24 * 30), retoma_fase="E3", teto_horas=23, relogio=relogio)


def test_a_chave_pausa_acrescenta_32_bytes_sem_referencia_e_91_com_o_uuid_do_agendamento(db_conn, relogio, versoes):
    """R1-10: o número da DECISOES (era «~60») medido. O validador Python de 2 KB (`modelos_conversa`) NÃO enxerga a `pausa`, que entra por
    `jsonb_set`: um estado com mais de 2.048 - 91 bytes não pausa (`TransicaoInvalida atendimento_conversa_check`). O processador deve manter folga."""

    def tamanho(atendimento_id) -> int:
        return db_conn.execute(
            "SELECT octet_length(estado_conversa::text) FROM ia.atendimento WHERE atendimento_id = %s", (atendimento_id,)
        ).fetchone()[0]

    medidas = []
    for ref in (None, str(uuid.uuid4())):
        atd, v, _ = novo_aberto(db_conn, relogio, versoes, fase="E3")
        antes = tamanho(atd)
        estado_pausa.pausar(db_conn, atd, v, retoma_em=_retoma(relogio), retoma_fase="E3", agendamento_ref=ref, relogio=relogio)
        medidas.append(tamanho(atd) - antes)
    assert medidas == [32, 91]
