"""Estados da linha `ia.agendamento` (B5.7b): `pendente → confirmado → disparado | cancelado`, tudo por CAS em `versao`, contra o PG 18 real."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from ia_atendimento import agenda_estado as ae
from ia_atendimento.estado import ConflitoVersao, TransicaoInvalida
from tests.apoio_agenda import inserir_agendamento, novo_agendado
from tests.banco import Banco

pytestmark = pytest.mark.banco


def _pendente(db_conn, relogio, versoes):
    """Caso (b) com a linha `pendente` (a hora cabe: dispara_em depois de pedido_em)."""
    agora = relogio()
    atd, _v, _chat = novo_agendado(db_conn, agora, versoes, retoma_em=agora + timedelta(hours=3))
    return atd, inserir_agendamento(
        db_conn, atd, entrada_do_pedido="dialogo_agendar", dispara_em=agora + timedelta(hours=3), pedido_em=agora
    )


def test_confirmar_pendente_grava_quem_e_quando_e_sobe_a_versao(db_conn, relogio, versoes):
    _atd, ag = _pendente(db_conn, relogio, versoes)
    assert ae.confirmar(db_conn, ag, 1, origem="cliente", agora=relogio()) == 2
    linha = ae.ler_agendamento(db_conn, ag)
    assert (linha.estado, linha.versao, linha.confirmacao_origem, linha.confirmado_em) == ("confirmado", 2, "cliente", relogio())
    with pytest.raises(TransicaoInvalida):  # já confirmado: confirmar de novo não é transição
        ae.confirmar(db_conn, ag, 2, origem="tacita", agora=relogio())
    with pytest.raises(ConflitoVersao):
        ae.confirmar(db_conn, ag, 1, origem="cliente", agora=relogio())


def test_confirmar_origem_invalida_e_barrada_pelo_banco_com_o_nome_da_restricao(db_conn, relogio, versoes):
    _atd, ag = _pendente(db_conn, relogio, versoes)
    with pytest.raises(TransicaoInvalida) as erro:
        ae.confirmar(db_conn, ag, 1, origem="alguem", agora=relogio())  # type: ignore[arg-type]
    assert erro.value.restricao == "agendamento_forma_check" and "alguem" not in str(erro.value)
    assert ae.ler_agendamento(db_conn, ag).estado == "pendente"


def test_disparar_so_de_confirmado_e_grava_o_desfecho_o_instante_e_o_job(db_conn, relogio, versoes):
    _atd, ag = _pendente(db_conn, relogio, versoes)
    with pytest.raises(TransicaoInvalida):  # pendente não dispara: a confirmação ainda não veio
        ae.disparar(db_conn, ag, 1, agora=relogio())
    ae.confirmar(db_conn, ag, 1, origem="cliente", agora=relogio())
    relogio.avancar(hours=3)
    assert ae.disparar(db_conn, ag, 2, agora=relogio(), job_id=77) == 3
    linha = ae.ler_agendamento(db_conn, ag)
    assert (linha.estado, linha.desfecho_disparo, linha.disparado_em, linha.job_id) == ("disparado", "retomou", relogio(), 77)
    with pytest.raises(TransicaoInvalida):  # o segundo que chega não dispara de novo
        ae.disparar(db_conn, ag, 3, agora=relogio())
    with pytest.raises(ConflitoVersao):
        ae.disparar(db_conn, ag, 2, agora=relogio())


def test_registrar_desfecho_so_de_disparado_e_so_os_cinco_valores(db_conn, relogio, versoes):
    _atd, ag = _pendente(db_conn, relogio, versoes)
    with pytest.raises(TransicaoInvalida):
        ae.registrar_desfecho(db_conn, ag, "resolvido", agora=relogio())
    ae.confirmar(db_conn, ag, 1, origem="cliente", agora=relogio())
    ae.disparar(db_conn, ag, 2, agora=relogio())
    with pytest.raises(TransicaoInvalida) as erro:
        ae.registrar_desfecho(db_conn, ag, "inventado", agora=relogio())  # type: ignore[arg-type]
    assert erro.value.restricao == "agendamento_forma_check"
    ae.registrar_desfecho(db_conn, ag, "resolvido", agora=relogio())
    assert ae.ler_agendamento(db_conn, ag).desfecho_disparo == "resolvido"


def test_cancelar_de_pendente_ou_confirmado_e_nunca_de_disparado(db_conn, relogio, versoes):
    _atd, ag = _pendente(db_conn, relogio, versoes)
    ae.cancelar(db_conn, ag, 1, por="cliente", agora=relogio())
    linha = ae.ler_agendamento(db_conn, ag)
    assert (linha.estado, linha.cancelado_por, linha.cancelado_em) == ("cancelado", "cliente", relogio())
    with pytest.raises(TransicaoInvalida):
        ae.cancelar(db_conn, ag, 2, por="sistema", agora=relogio())  # cancelado é terminal
    _atd2, confirmado = _pendente(db_conn, relogio, versoes)
    ae.confirmar(db_conn, confirmado, 1, origem="cliente", agora=relogio())
    ae.cancelar(db_conn, confirmado, 2, por="humano_assumiu", agora=relogio())
    assert ae.ler_agendamento(db_conn, confirmado).cancelado_por == "humano_assumiu"
    _atd3, disparado = _pendente(db_conn, relogio, versoes)
    ae.confirmar(db_conn, disparado, 1, origem="cliente", agora=relogio())
    ae.disparar(db_conn, disparado, 2, agora=relogio())
    with pytest.raises(TransicaoInvalida):
        ae.cancelar(db_conn, disparado, 3, por="sistema", agora=relogio())
    _atd4, qualquer = _pendente(db_conn, relogio, versoes)
    with pytest.raises(TransicaoInvalida) as erro:
        ae.cancelar(db_conn, qualquer, 1, por="ninguem", agora=relogio())  # type: ignore[arg-type]
    assert erro.value.restricao == "agendamento_forma_check"


def test_agendamento_inexistente_e_agora_sem_fuso(db_conn, relogio):
    with pytest.raises(ae.AgendamentoInexistente):
        ae.ler_agendamento(db_conn, uuid.uuid4())
    with pytest.raises(ae.AgendamentoInexistente):
        ae.confirmar(db_conn, uuid.uuid4(), 1, origem="cliente", agora=relogio())
    with pytest.raises(ValueError, match="fuso"):
        ae.confirmar(db_conn, uuid.uuid4(), 1, origem="cliente", agora=relogio().replace(tzinfo=None))


def test_passo_de_agendamento_entra_na_linha_do_tempo_com_texto_do_codigo(db_conn, relogio, versoes):
    atd, ag = _pendente(db_conn, relogio, versoes)
    assert ae.passo_de_agendamento(db_conn, atd, uuid.UUID(str(ag)), "proposto") == 1
    assert ae.passo_de_agendamento(db_conn, atd, uuid.UUID(str(ag)), "disparado") == 2
    linhas = db_conn.execute(
        "SELECT ordem, tipo, resultado, texto, fase, turno, agendamento_id FROM ia.passo WHERE atendimento_id = %s ORDER BY ordem", (atd,)
    ).fetchall()
    assert linhas == [
        (1, "agendamento", "proposto", "Agendamento proposto.", "E0", 0, ag),
        (2, "agendamento", "disparado", "Agendamento disparado.", "E0", 0, ag),
    ]


def test_dois_disparos_concorrentes_da_mesma_versao_so_um_ganha(banco: Banco, relogio, versoes_semeadas_no_banco):
    """O CAS `confirmado → disparado` é a garantia de «nenhum duplicado»: quem perde nunca fala com o cliente."""
    with banco.sessao("ia_app_a") as conn:
        agora = relogio()
        atd, _v, _c = novo_agendado(conn, agora, versoes_semeadas_no_banco, retoma_em=agora + timedelta(hours=1))
        ag = inserir_agendamento(conn, atd, entrada_do_pedido="dialogo_agendar", dispara_em=agora + timedelta(hours=1), pedido_em=agora)
        ae.confirmar(conn, ag, 1, origem="cliente", agora=agora)
    largada = threading.Barrier(4)

    def tentar(_: int):
        with banco.sessao("ia_app_a") as conn:
            largada.wait(timeout=10)
            try:
                return ae.disparar(conn, ag, 2, agora=relogio())
            except (ConflitoVersao, TransicaoInvalida) as erro:
                return erro

    with ThreadPoolExecutor(4) as pool:
        resultados = [f.result(timeout=30) for f in [pool.submit(tentar, n) for n in range(4)]]
    assert [r for r in resultados if isinstance(r, int)] == [3] and len(resultados) == 4
