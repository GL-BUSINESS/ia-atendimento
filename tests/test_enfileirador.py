"""Enfileirador da API: o job entra na MESMA transação da gravação (defer síncrono do Procrastinate com a conexão da API)."""

from __future__ import annotations

import uuid

import psycopg
import pytest

from ia_atendimento import fila
from ia_atendimento.enfileirador import EnfileiradorProcrastinate
from tests import apoio_api
from tests import fixtures_fila as ff
from tests.apoio_api import CHAT, OUTRO_CHAT, abrir_ativo, corpo_de_entrada, mensagem_nativa
from tests.fixtures_fila import abrir, hex24

ambiente = apoio_api.ambiente
conninfo_app, conn_super, relogio = ff.conninfo_app, ff.conn_super, ff.relogio
pytestmark = pytest.mark.banco


@pytest.fixture
def enfileirador(conninfo_app):
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


def test_iniciar_leva_lock_do_chat_e_o_alarme_de_encerrar_por_chave_nao_leva_lock(banco, enfileirador):
    atd, chat = uuid.uuid4(), hex24()
    with abrir(banco) as conn:
        with conn.transaction():
            enfileirador.iniciar(conn, atd, chat)
            assert enfileirador.encerrar_por_chave(conn, atd, chat, 120.0) is True
            assert enfileirador.encerrar_por_chave(conn, atd, chat, 240.0) is False, "um por atendimento"
        iniciar, alarme = _jobs(conn, "ia:iniciar")[0], _jobs(conn, "ia:alarme_encerrar_por_chave")[0]
        agora = conn.execute("SELECT now()").fetchone()[0]
        sem_encerramento_de_verdade = _jobs(conn, "ia:encerrar_por_chave") == []
    assert iniciar[1:3] == (f"chat:{chat}", f"iniciar:{atd}")
    assert alarme[1:3] == (None, f"encerrar_por_chave:{atd}"), "o job futuro NÃO leva lock do chat (R2-01)"
    assert sem_encerramento_de_verdade, "o encerramento de verdade só nasce quando o alarme dispara"
    assert 100 < (alarme[4] - agora).total_seconds() <= 121


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
    assert ambiente.escalar("SELECT count(*) FROM procrastinate.procrastinate_jobs WHERE task_name = 'ia:alarme_encerrar_por_chave'") == 1
    ambiente.put("/config/ia_ativa", {"valor": False, "por": "operador.teste@glcapital.invalid"})
    assert (
        ambiente.escalar("SELECT count(*) FROM procrastinate.procrastinate_jobs WHERE task_name = 'ia:alarme_encerrar_por_chave'") == 1
    ), "idempotente"


# --- R2-01: a parada leve não prende o chat do cliente por até 19 min -------------------------------------------------------------------------


def _buscar(conn: psycopg.Connection):
    """O que o worker pegaria agora (`procrastinate_fetch_job_v2`), marcando como feito; `None` se nada está liberado."""
    linha = conn.execute("SELECT id, task_name, lock FROM procrastinate.procrastinate_fetch_job_v2(NULL, NULL)").fetchone()
    if linha is None or linha[0] is None:
        return None
    conn.execute("UPDATE procrastinate.procrastinate_jobs SET status = 'succeeded' WHERE id = %s", (linha[0],))
    return tuple(linha)


def test_parada_leve_nao_deixa_o_turno_do_cliente_preso_atras_do_encerramento(ambiente, enfileirador):
    """De ponta a ponta com a fila real: o `PUT ia_ativa=false` agenda o encerramento do 2º chat para ~9,5 min; o cliente desse chat responde agora e o
    turno (vencido em 3 s) tem de ser liberado. Com `lock=chat:` no job futuro, o `fetch` do Procrastinate o recusava (não olha `scheduled_at`)."""
    ambiente.trocar(enfileirador=enfileirador)
    ambiente.ligar()
    c1, c2 = hex24(), hex24()
    abrir_ativo(ambiente, c1)
    abrir_ativo(ambiente, c2)
    assert ambiente.put("/config/ia_ativa", {"valor": False, "por": "operador.teste@glcapital.invalid"}).json()["efeitos"] == {
        "encerrar_por_chave_agendados": 2
    }
    assert (
        ambiente.evento_chatguru(mensagem_nativa(chat_id=c2, datetime_post=None, texto="quero falar com um atendente")).json()[
            "turno_enfileirado"
        ]
        is True
    )
    with ambiente.super() as conn:
        conn.execute(
            "UPDATE procrastinate.procrastinate_jobs SET scheduled_at = now() - interval '1 second' WHERE task_name = 'ia:turno'"
        )  # passaram os 3 s da rajada
        liberados = []
        while (job := _buscar(conn)) is not None:
            liberados.append(job[1])
    assert "ia:turno" in liberados, f"o turno do cliente ficou preso: {liberados}"
    assert "ia:encerrar_por_chave" not in liberados, "o encerramento futuro não existe como job com lock antes da hora"


async def test_alarme_dispara_e_enfileira_o_encerramento_de_verdade_com_lock_do_chat(conninfo_app, conn_super, banco, relogio):
    """O alarme vencido executa e enfileira o `encerrar_por_chave` com `lock=chat:` e sem atraso; o worker o executa (serviço injetado)."""
    from ia_atendimento.fila import criar_app
    from tests.fixtures_fila import Chamadas, montar_servicos

    encerrados: list[uuid.UUID] = []

    async def encerrar(atendimento_id: uuid.UUID) -> None:
        encerrados.append(atendimento_id)

    servicos = montar_servicos(banco, relogio, Chamadas(), encerrar_por_chave=encerrar)
    atd, chat = uuid.uuid4(), hex24()
    with abrir(banco) as conn:  # a API: defer SÍNCRONO, com o app sem pool assíncrono aberto
        assert EnfileiradorProcrastinate(criar_app(conninfo_app, com_periodicas=False)).encerrar_por_chave(conn, atd, chat, 600.0) is True
    conn_super.execute("UPDATE procrastinate.procrastinate_jobs SET scheduled_at = now() - interval '1 second' WHERE status = 'todo'")
    worker = criar_app(conninfo_app, com_periodicas=False)  # o worker: outro processo, outro app
    async with worker.open_async():
        await worker.run_worker_async(
            wait=False, install_signal_handlers=False, additional_context={"servicos": servicos}, fetch_job_polling_interval=0.05
        )
    assert encerrados == [atd]
    nomes = conn_super.execute("SELECT task_name, lock FROM procrastinate.procrastinate_jobs ORDER BY id").fetchall()
    assert nomes == [("ia:alarme_encerrar_por_chave", None), ("ia:encerrar_por_chave", f"chat:{chat}")]
