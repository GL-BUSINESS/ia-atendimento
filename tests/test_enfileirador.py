"""Enfileirador da API: o job entra na MESMA transação da gravação (defer síncrono do Procrastinate com a conexão da API)."""

from __future__ import annotations

import uuid

import psycopg
import pytest

from ia_atendimento import fila
from ia_atendimento.enfileirador import EnfileiradorProcrastinate
from tests import apoio_api
from tests.apoio_api import CHAT, OUTRO_CHAT, abrir_ativo, corpo_de_entrada, mensagem_nativa
from tests.fixtures_fila import abrir, conninfo_app, hex24  # noqa: F401

ambiente = apoio_api.ambiente
pytestmark = pytest.mark.banco


@pytest.fixture
def enfileirador(conninfo_app):  # noqa: F811
    return EnfileiradorProcrastinate(fila.criar_app(conninfo_app, com_periodicas=False))


def _jobs(banco_conn: psycopg.Connection, tarefa: str):
    return banco_conn.execute(
        "SELECT task_name, lock, queueing_lock, args, scheduled_at FROM procrastinate.procrastinate_jobs WHERE task_name = %s ORDER BY id",
        (tarefa,),
    ).fetchall()


def test_job_entra_na_transacao_do_chamador_e_some_no_rollback(banco, enfileirador):
    atd, chat = uuid.uuid4(), hex24()
    with abrir(banco) as conn:
        with pytest.raises(RuntimeError, match="desfaz"), conn.transaction():
            enfileirador.turno(conn, atd, chat)
            assert conn.execute("SELECT count(*) FROM procrastinate.procrastinate_jobs").fetchone() == (1,), (
                "dentro da transação o job existe"
            )
            raise RuntimeError("desfaz tudo")
        assert conn.execute("SELECT count(*) FROM procrastinate.procrastinate_jobs").fetchone() == (0,)
        with conn.transaction():
            enfileirador.turno(conn, atd, chat)
        job = _jobs(conn, "ia:turno")[0]
    assert job[1:4] == (f"chat:{chat}", f"turno:{chat}", {"atendimento_id": str(atd)}) and job[4] is not None, "schedule_in de 3 s"


def test_rajada_de_mensagens_cola_no_mesmo_turno_sem_derrubar_a_transacao(banco, enfileirador):
    atd, chat = uuid.uuid4(), hex24()
    with abrir(banco) as conn:
        with conn.transaction():
            conn.execute("CREATE TEMP TABLE marca (x int)")
            enfileirador.turno(conn, atd, chat)
            enfileirador.turno(conn, atd, chat)  # `AlreadyEnqueued` engolido pelo savepoint
            conn.execute("INSERT INTO marca VALUES (1)")
        assert conn.execute("SELECT count(*) FROM marca").fetchone() == (1,), "a transação seguiu viva e foi commitada"
        assert len(_jobs(conn, "ia:turno")) == 1


def test_iniciar_e_encerrar_por_chave_levam_lock_do_chat_e_trava_propria(banco, enfileirador):
    atd, chat = uuid.uuid4(), hex24()
    with abrir(banco) as conn:
        with conn.transaction():
            enfileirador.iniciar(conn, atd, chat)
            assert enfileirador.encerrar_por_chave(conn, atd, chat, 120.0) is True
            assert enfileirador.encerrar_por_chave(conn, atd, chat, 240.0) is False, "um por atendimento"
        iniciar, encerrar = _jobs(conn, "ia:iniciar")[0], _jobs(conn, "ia:encerrar_por_chave")[0]
        agora = conn.execute("SELECT now()").fetchone()[0]
    assert iniciar[1:3] == (f"chat:{chat}", f"iniciar:{atd}") and encerrar[1:3] == (f"chat:{chat}", f"encerrar_por_chave:{atd}")
    assert 100 < (encerrar[4] - agora).total_seconds() <= 121


def test_api_de_verdade_enfileira_iniciar_e_turno_na_transacao_da_gravacao(ambiente, enfileirador):
    ambiente.trocar(enfileirador=enfileirador)
    ambiente.ligar()
    r = ambiente.post("/atendimentos", corpo_de_entrada())
    assert r.status_code == 201
    atd = r.json()["atendimento_id"]
    assert ambiente.consultar("SELECT task_name, args->>'atendimento_id', lock FROM procrastinate.procrastinate_jobs") == [
        ("ia:iniciar", atd, f"chat:{CHAT}")
    ]
    abrir_ativo(ambiente, OUTRO_CHAT)
    assert ambiente.evento_chatguru(mensagem_nativa(chat_id=OUTRO_CHAT)).json()["turno_enfileirado"] is True
    assert ambiente.escalar("SELECT count(*) FROM procrastinate.procrastinate_jobs WHERE task_name = 'ia:turno'") == 1
    # a parada leve: um job por atendimento, na transação do PUT
    r = ambiente.put("/config/ia_ativa", {"valor": False, "por": "operador.teste@glcapital.invalid"})
    assert r.json()["efeitos"] == {"encerrar_por_chave_agendados": 1}
    assert ambiente.escalar("SELECT count(*) FROM procrastinate.procrastinate_jobs WHERE task_name = 'ia:encerrar_por_chave'") == 1
    ambiente.put("/config/ia_ativa", {"valor": False, "por": "operador.teste@glcapital.invalid"})
    assert ambiente.escalar("SELECT count(*) FROM procrastinate.procrastinate_jobs WHERE task_name = 'ia:encerrar_por_chave'") == 1, (
        "idempotente"
    )
