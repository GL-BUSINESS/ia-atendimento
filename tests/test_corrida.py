"""Corridas reais (threads) contra o Postgres descartável: idempotência sob concorrência, tetos sob a trava e estado relido sob o lock.

Trazidas da revisão 1 da B1.5 (`docs/REVISAO-B1.5-3010.md`, R1-01, R1-02, R1-03, R1-04, R1-08, R1-13). Esperam a CONDIÇÃO (alguém enfileirado na
trava, lida em `pg_locks`), não um sinal nem um `sleep` cego.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from ia_atendimento.api import agendamentos, anotacoes, atendimentos, config_rotas, eventos
from ia_atendimento.api.auth import Identidade
from ia_atendimento.api.erros import ErroApi
from tests import apoio_api
from tests.apoio_api import (
    CHAT,
    EspiaDeFila,
    abrir_ativo,
    corpo_de_agendamento,
    corpo_de_entrada,
    entrada_para,
    mensagem_nativa,
)

ambiente = apoio_api.ambiente
pytestmark = pytest.mark.banco
PRAZO_S = 15.0


def _chamar(fn, *args) -> tuple[str, Any]:
    try:
        return "ok", fn(*args)
    except ErroApi as erro:
        return "erro", erro.codigo
    except Exception as erro:
        return "exc", type(erro).__name__


def _status(resultado: tuple[str, Any]) -> Any:
    return resultado[1][0] if resultado[0] == "ok" else resultado[1]


def _esperar_alguem_na_trava(ambiente) -> None:
    """Espera a condição: há uma sessão ENFILEIRADA num advisory lock (a gêmea chegou na trava que a primeira segura)."""
    fim = time.monotonic() + PRAZO_S
    while time.monotonic() < fim:
        if ambiente.escalar("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted"):
            return
        time.sleep(0.02)
    raise AssertionError("ninguém entrou na fila da trava a tempo")


class FilaQueSegura(EspiaDeFila):
    """Segura a transação da 1ª requisição (e a trava) até a gêmea estar enfileirada nela."""

    def __init__(self, ambiente) -> None:
        super().__init__()
        self._ambiente = ambiente
        self.dentro = threading.Event()

    def iniciar(self, conn, atendimento_id, chat_id) -> None:
        super().iniciar(conn, atendimento_id, chat_id)
        self.dentro.set()
        _esperar_alguem_na_trava(self._ambiente)


# --- R1-01: o replay concorrente de POST /atendimentos devolve 200 ---------------------------------------------------------------------


def test_replay_concorrente_de_atendimento_com_max_abertos_1_devolve_200(ambiente):
    ambiente.ligar()
    ambiente.configurar("max_abertos", 1)
    fila = FilaQueSegura(ambiente)
    ambiente.trocar(enfileirador=fila)
    corpo = corpo_de_entrada()
    with ThreadPoolExecutor(2) as pool:
        a = pool.submit(_chamar, atendimentos.criar_atendimento, ambiente.ctx, "n8n_braco", corpo)
        assert fila.dentro.wait(PRAZO_S)
        b = pool.submit(_chamar, atendimentos.criar_atendimento, ambiente.ctx, "n8n_braco", corpo)
        ra, rb = a.result(), b.result()
    assert _status(ra) == 201
    assert _status(rb) == 200 and rb[1][1]["repetido"] is True, f"o retry do n8n recebeu {rb}"
    assert rb[1][1]["atendimento_id"] == ra[1][1]["atendimento_id"]
    assert ambiente.escalar("SELECT count(*) FROM ia.atendimento") == 1 and len(fila.inicios) == 1


def test_gemeo_de_atendimento_que_perdeu_a_janela_entre_o_replay_e_as_recusas_recebe_200(ambiente, monkeypatch):
    """Determinístico: o gêmeo B já fez a busca de replay (vazia) quando A termina; depois B bate no `abertos_max` causado pela própria reserva."""
    ambiente.ligar()
    ambiente.configurar("max_abertos", 1)
    corpo = corpo_de_entrada()
    original = atendimentos.estado.procurar_replay
    visto: dict[str, Any] = {"chamadas": 0}

    def espiao(conn, origem, entrada):
        resultado = original(conn, origem, entrada)
        visto["chamadas"] += 1
        if visto["chamadas"] == 1:  # a busca de B, fora da trava
            monkeypatch.setattr(atendimentos.estado, "procurar_replay", original)
            visto["a"] = _chamar(atendimentos.criar_atendimento, ambiente.ctx, "n8n_braco", corpo)
        return resultado

    monkeypatch.setattr(atendimentos.estado, "procurar_replay", espiao)
    rb = _chamar(atendimentos.criar_atendimento, ambiente.ctx, "n8n_braco", corpo)
    assert _status(visto["a"]) == 201
    assert _status(rb) == 200 and rb[1][1]["repetido"] is True, rb


# --- R1-02: o gêmeo de POST /agendamentos devolve 200 ----------------------------------------------------------------------------------


def test_gemeo_concorrente_de_agendamento_recebe_200_e_nao_chat_ocupado(ambiente, monkeypatch):
    ambiente.ligar()
    segurou = threading.Event()
    guardar = agendamentos.cofre.guardar

    def guardar_e_segurar(*args, **kwargs):
        guardar(*args, **kwargs)
        segurou.set()
        _esperar_alguem_na_trava(ambiente)  # A só commita com a gêmea na fila da trava

    monkeypatch.setattr(agendamentos.cofre, "guardar", guardar_e_segurar)
    corpo = corpo_de_agendamento()
    with ThreadPoolExecutor(2) as pool:
        a = pool.submit(_chamar, agendamentos.criar_agendamento, ambiente.ctx, "n8n_braco", corpo)
        assert segurou.wait(PRAZO_S)
        b = pool.submit(_chamar, agendamentos.criar_agendamento, ambiente.ctx, "n8n_braco", corpo)
        ra, rb = a.result(), b.result()
    assert _status(ra) == 201
    assert _status(rb) == 200 and rb[1][1]["repetido"] is True, f"o gêmeo recebeu {rb}"
    assert ambiente.escalar("SELECT count(*) FROM ia.agendamento") == 1


def test_gemeo_de_agendamento_que_perdeu_a_janela_entre_o_replay_e_o_chat_ocupado_recebe_200(ambiente, monkeypatch):
    ambiente.ligar()
    corpo = corpo_de_agendamento()
    original = agendamentos.ag.procurar_replay
    visto: dict[str, Any] = {"chamadas": 0}

    def espiao(conn, chave, hash_do_texto):
        resultado = original(conn, chave, hash_do_texto)
        visto["chamadas"] += 1
        if visto["chamadas"] == 1:
            monkeypatch.setattr(agendamentos.ag, "procurar_replay", original)
            visto["a"] = _chamar(agendamentos.criar_agendamento, ambiente.ctx, "n8n_braco", corpo)
        return resultado

    monkeypatch.setattr(agendamentos.ag, "procurar_replay", espiao)
    rb = _chamar(agendamentos.criar_agendamento, ambiente.ctx, "n8n_braco", corpo)
    assert _status(visto["a"]) == 201
    assert _status(rb) == 200 and rb[1][1]["repetido"] is True, rb


# --- tetos sob a trava (R1-08 e mutantes M2/M17 da R1-13) -----------------------------------------------------------------------------


def _simultaneos(ambiente, quantos: int, fazer) -> list[Any]:
    chats = [f"{i:024x}" for i in range(1, quantos + 1)]
    barreira = threading.Barrier(quantos)

    def um(chat: str):
        barreira.wait()
        return fazer(chat)

    with ThreadPoolExecutor(quantos) as pool:
        return [_status(r) for r in pool.map(um, chats)]


def test_max_abertos_sob_corrida(ambiente):
    ambiente.ligar()
    ambiente.configurar("max_abertos", 2)
    codigos = _simultaneos(ambiente, 8, lambda c: _chamar(atendimentos.criar_atendimento, ambiente.ctx, "n8n_braco", entrada_para(c)))
    assert codigos.count(201) == 2 and ambiente.escalar("SELECT count(*) FROM ia.atendimento") == 2, codigos


def test_max_disparos_dia_sob_corrida(ambiente):
    ambiente.ligar()
    ambiente.configurar("max_abertos", 50)
    ambiente.configurar("agenda_max_dia", 1)  # o registro exige agenda_max_dia <= max_disparos_dia
    ambiente.configurar("max_disparos_dia", 2)
    codigos = _simultaneos(ambiente, 8, lambda c: _chamar(atendimentos.criar_atendimento, ambiente.ctx, "n8n_braco", entrada_para(c)))
    assert codigos.count(201) == 2 and ambiente.escalar("SELECT count(*) FROM ia.atendimento") == 2, codigos
    assert set(codigos) == {201, "disparos_dia"}


def test_agenda_max_dia_sob_corrida(ambiente):
    ambiente.ligar()
    ambiente.configurar("agenda_max_dia", 2)
    codigos = _simultaneos(
        ambiente,
        8,
        lambda c: _chamar(agendamentos.criar_agendamento, ambiente.ctx, "n8n_braco", corpo_de_agendamento(c, clt_job_id=str(uuid.uuid4()))),
    )
    assert codigos.count(201) == 2 and ambiente.escalar("SELECT count(*) FROM ia.agendamento") == 2, codigos


# --- R1-03: candidatos idênticos concorrentes ----------------------------------------------------------------------------------------


def test_candidatos_identicos_concorrentes_um_grava_e_o_outro_repete(ambiente):
    resultados: Counter[tuple[Any, ...]] = Counter()
    for _ in range(25):
        sessao = str(uuid.uuid4())
        corpo = {
            "criterio_versao": "c1.0",
            "candidatos": [{"chat_id": CHAT, "posicao": 1, "perfil": {"banco": "FACTA"}, "escolhido": False}],
        }
        barreira = threading.Barrier(2)

        def um(sessao=sessao, corpo=corpo, barreira=barreira):
            barreira.wait()
            return _chamar(anotacoes.gravar_candidatos, ambiente.ctx, sessao, corpo)

        with ThreadPoolExecutor(2) as pool:
            rs = [f.result() for f in [pool.submit(um), pool.submit(um)]]
        resultados[tuple(sorted(str(r[1][1]) if r[0] == "ok" else f"{r[0]}:{r[1]}" for r in rs))] += 1
        assert ambiente.escalar("SELECT count(*) FROM ia.candidato WHERE sessao_id = %s", (sessao,)) == 1
    assert set(resultados) == {("{'gravados': 0, 'repetidos': 1}", "{'gravados': 1, 'repetidos': 0}")}, resultados


# --- R1-13: PUT e eventos idênticos (regressão) ---------------------------------------------------------------------------------------


def test_put_config_com_a_mesma_versao_esperada_so_um_vence(ambiente):
    versao = ambiente.escalar("SELECT max(versao) FROM ia.config_versao WHERE nome = 'max_abertos'")
    barreira = threading.Barrier(6)

    def um(i: int):
        barreira.wait()
        return _chamar(
            config_rotas.gravar_config, ambiente.ctx, "ti", "max_abertos", {"valor": 3 + i, "por": "x", "versao_esperada": versao}
        )

    with ThreadPoolExecutor(6) as pool:
        codigos = [_status(r) for r in pool.map(um, range(6))]
    assert codigos.count(200) == 1 and set(codigos) <= {200, "config_corrida"}, codigos


def test_eventos_identicos_concorrentes_um_grava_e_os_outros_repetem(ambiente):
    abrir_ativo(ambiente)
    identidade = Identidade("gateway_chatguru", "chatguru-ia")
    barreira = threading.Barrier(6)

    def um(_):
        barreira.wait()
        return _chamar(eventos.evento_chatguru, ambiente.ctx, identidade, mensagem_nativa())

    with ThreadPoolExecutor(6) as pool:
        resultados = sorted(r[1][1]["resultado"] if r[0] == "ok" else r[1] for r in pool.map(um, range(6)))
    assert resultados == ["gravado", *["repetido"] * 5]
    assert ambiente.escalar("SELECT count(*) FROM ia.passo WHERE tipo = 'mensagem_recebida'") == 1


# --- R1-04: o estado do atendimento é relido sob o lock ------------------------------------------------------------------------------


def _mudar_depois_da_leitura(ambiente, monkeypatch, atd, sql: str) -> None:
    original = eventos.atendimento_ativo

    def espiao(conn, chat_id):
        lido = original(conn, chat_id)
        with ambiente.super() as conn_super:
            conn_super.execute(sql, (atd,))  # o atendimento muda DEPOIS da leitura sem trava e ANTES do lock
        return lido

    monkeypatch.setattr(eventos, "atendimento_ativo", espiao)


def test_atendimento_encerrado_entre_a_leitura_e_o_lock_descarta_e_nao_grava(ambiente, monkeypatch):
    atd = abrir_ativo(ambiente)
    _mudar_depois_da_leitura(
        ambiente, monkeypatch, atd,
        "UPDATE ia.atendimento SET estado = 'encerrado', desfecho = 'sem_venda', encerrado_em = now(), lease_ate = NULL,"
        " estado_conversa = '{\"fase\": \"E9\"}' WHERE atendimento_id = %s",
    )  # fmt: skip
    status, corpo = eventos.evento_chatguru(ambiente.ctx, Identidade("gateway_chatguru", "chatguru-ia"), mensagem_nativa())
    assert (status, corpo["resultado"], corpo["motivo"]) == (200, "descartado", "sem_atendimento")
    assert ambiente.escalar("SELECT count(*) FROM ia.passo") == 0 and ambiente.escalar("SELECT count(*) FROM ia.conversa_cifrada") == 0
    assert ambiente.fila.turnos == []


def test_atendimento_em_repassando_entre_a_leitura_e_o_lock_grava_sem_enfileirar_turno(ambiente, monkeypatch):
    atd = abrir_ativo(ambiente)
    _mudar_depois_da_leitura(
        ambiente,
        monkeypatch,
        atd,
        "UPDATE ia.atendimento SET estado = 'repassando', estado_conversa = '{\"fase\": \"E10\"}' WHERE atendimento_id = %s",
    )
    _, corpo = eventos.evento_chatguru(ambiente.ctx, Identidade("gateway_chatguru", "chatguru-ia"), mensagem_nativa())
    assert corpo["resultado"] == "gravado" and corpo["turno_enfileirado"] is False
    assert ambiente.fila.turnos == []


def test_atendimento_fica_travado_desde_a_releitura_ate_o_fim_do_registro(ambiente, monkeypatch):
    """R2-06: a janela entre a releitura e `travar_atendimento` só fecha com o `FOR UPDATE` da releitura. Outra conexão tenta encerrar o atendimento no meio
    do registro: com a releitura simples ela passaria e a mensagem entraria num atendimento `encerrado`."""
    import psycopg

    from ia_atendimento import mensagens

    atd = abrir_ativo(ambiente)
    original = mensagens.gravar_mensagem_recebida
    visto: dict[str, bool] = {}

    def gancho(conn, atendimento_id, **kwargs):
        with ambiente.super() as outro:
            outro.execute("SET lock_timeout = '300ms'")
            try:
                outro.execute(
                    "UPDATE ia.atendimento SET estado = 'encerrado', desfecho = 'sem_venda', encerrado_em = now(), lease_ate = NULL,"
                    ' estado_conversa = \'{"fase": "E9"}\' WHERE atendimento_id = %s',
                    (atd,),
                )
                visto["bloqueado"] = False
            except psycopg.errors.LockNotAvailable:
                visto["bloqueado"] = True
        return original(conn, atendimento_id, **kwargs)

    monkeypatch.setattr(mensagens, "gravar_mensagem_recebida", gancho)
    _, corpo = eventos.evento_chatguru(ambiente.ctx, Identidade("gateway_chatguru", "chatguru-ia"), mensagem_nativa())
    assert visto["bloqueado"] is True, "o atendimento ficou livre entre a releitura e o registro"
    assert (
        corpo["resultado"] == "gravado"
        and ambiente.escalar("SELECT estado FROM ia.atendimento WHERE atendimento_id = %s", (atd,)) == "aberto"
    )
