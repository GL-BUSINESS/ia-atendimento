"""Pausa combinada e jobs da agenda (B5.7b): `pausado`, `retomar`, `reaper_agenda` e `POST /agendamentos` com a fila de verdade.

Entregáveis do roteiro: EM4 (restart com 3 `confirmado`, sem perda nem duplicidade), `test_um_agendamento_ativo_por_atendimento`,
`test_post_triplicado_e_noop`, `test_reaper_pula_pausado`, `test_desligada_noturna_nao_encerra_pausado` e `test_pausar_nunca_em_E7`.
A volta em si (pré-checagens, mensagem) é da B5.7c: aqui o serviço `retomar_atendimento` é um espião (`Voltas`) e o que se prova é o CAS, a fila,
o lock do chat, o reaper e a ausência de efeito no chat.
"""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta

import psycopg
import pytest
from croniter import croniter

from ia_atendimento import agenda_estado as ae
from ia_atendimento import agenda_jobs, estado, estado_pausa, fila, jobs
from ia_atendimento.calendario import HORA_BLOQUEIO_ENTRADA, cron_utc
from ia_atendimento.chave import config_vigente
from ia_atendimento.enfileirador import EnfileiradorProcrastinate
from ia_atendimento.estado import EntradaInvalida, TransicaoInvalida
from ia_atendimento.jobs import Servicos
from ia_atendimento.relogio import RelogioFalso
from tests import apoio_api
from tests import fixtures_fila as ff
from tests.apoio_agenda import (
    Voltas,
    agendado_confirmado,
    inserir_agendamento,
    inserir_job,
    novo_aberto,
    novo_agendado,
    novo_worker,
    pausado_confirmado,
    tratar_lease_de_referencia,
)
from tests.apoio_api import CHAT, EspiaDeFila, corpo_de_agendamento
from tests.fixtures_fila import Chamadas, jobs_por_status, montar_servicos

ambiente = apoio_api.ambiente
conn_app, conn_super, relogio, conninfo_app = ff.conn_app, ff.conn_super, ff.relogio, ff.conninfo_app
pytestmark = pytest.mark.banco
POR = "operador.teste@glcapital.invalid"


def criar(conninfo: str, **opcoes):
    return fila.criar_app(conninfo, com_periodicas=opcoes.pop("com_periodicas", False))


async def rodar(app, servicos, **opcoes) -> None:
    """Worker que processa o que está vencido e sai (`wait=False`): um «processo» do worker."""
    await app.run_worker_async(
        wait=False, install_signal_handlers=False, additional_context={"servicos": servicos}, fetch_job_polling_interval=0.05, **opcoes
    )


def _jobs(conn: psycopg.Connection, tarefa: str):
    return conn.execute(
        "SELECT status::text, lock, queueing_lock, args, scheduled_at FROM procrastinate.procrastinate_jobs WHERE task_name = %s ORDER BY id",
        (tarefa,),
    ).fetchall()


def _estado(conn: psycopg.Connection, atendimento_id: uuid.UUID) -> tuple[str, int]:
    return conn.execute("SELECT estado, versao FROM ia.atendimento WHERE atendimento_id = %s", (atendimento_id,)).fetchone()


def _ag(conn: psycopg.Connection, agendamento_id: uuid.UUID) -> tuple[str, int, str | None, int | None]:
    return conn.execute(
        "SELECT estado, versao, desfecho_disparo, job_id FROM ia.agendamento WHERE agendamento_id = %s", (agendamento_id,)
    ).fetchone()


def _passos(conn: psycopg.Connection, atendimento_id: uuid.UUID) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT resultado FROM ia.passo WHERE atendimento_id = %s AND tipo = 'agendamento' ORDER BY ordem", (atendimento_id,)
        )
    ]


async def _reagendar_ignorando(_: datetime) -> None:
    raise AssertionError("não era para reagendar")


# --- pausa: E7 nunca; um agendamento ativo por atendimento ------------------------------------------------------------------------------------


def test_pausar_nunca_em_E7(conn_app, relogio, versoes):
    """Três camadas: a assinatura (`retoma_fase` fora de E2–E6/E8), o UPDATE (a fase ATUAL tem de ser a de volta) e o CHECK do banco."""
    atd, v, _ = novo_aberto(conn_app, relogio.agora, versoes, fase="E7")
    retoma = relogio.agora() + timedelta(hours=2)
    with pytest.raises(EntradaInvalida):
        estado_pausa.pausar(conn_app, atd, v, retoma_em=retoma, retoma_fase="E7", relogio=relogio.agora)
    for outra in ("E2", "E3", "E4", "E5", "E6", "E8"):
        with pytest.raises(TransicaoInvalida):  # em E7 não se pausa «voltando» para outra fase
            estado_pausa.pausar(conn_app, atd, v, retoma_em=retoma, retoma_fase=outra, relogio=relogio.agora)
    assert _estado(conn_app, atd) == ("aberto", v)
    with pytest.raises(psycopg.errors.CheckViolation) as erro:  # nem por SQL direto, com o JSON forjado
        conn_app.execute(
            "UPDATE ia.atendimento SET estado = 'pausado', retoma_em = %s, lease_ate = %s, estado_conversa = %s::jsonb WHERE atendimento_id = %s",
            (retoma, retoma, '{"fase": "E7", "pausa": {"retoma_fase": "E7"}}', atd),
        )
    assert erro.value.diag.constraint_name == "atendimento_conversa_check"
    assert _estado(conn_app, atd) == ("aberto", v)


def test_um_agendamento_ativo_por_atendimento(conn_app, relogio, versoes):
    """`agendamento_ativo_uq`: no máximo um `pendente|confirmado` por atendimento; reagendar é cancelar e abrir o `seq` 2; nunca um 3º."""
    agora = relogio.agora()
    atd, _v, _chat = novo_agendado(conn_app, agora, versoes, retoma_em=agora + timedelta(hours=3))
    um = inserir_agendamento(conn_app, atd, entrada_do_pedido="dialogo_agendar", dispara_em=agora + timedelta(hours=3), pedido_em=agora)

    def outro(seq: int) -> uuid.UUID:
        return inserir_agendamento(
            conn_app, atd, entrada_do_pedido="dialogo_agendar", dispara_em=agora + timedelta(hours=4), pedido_em=agora, seq=seq
        )

    with pytest.raises(psycopg.errors.UniqueViolation) as erro:  # pendente + pendente
        outro(2)
    assert erro.value.diag.constraint_name == "agendamento_ativo_uq"
    ae.confirmar(conn_app, um, 1, origem="cliente", agora=agora)
    with pytest.raises(psycopg.errors.UniqueViolation) as erro:  # confirmado também é ativo
        outro(2)
    assert erro.value.diag.constraint_name == "agendamento_ativo_uq"
    ae.cancelar(conn_app, um, 2, por="reagendado", agora=agora)
    dois = outro(2)  # cancelado liberou a vaga
    with pytest.raises(psycopg.errors.UniqueViolation):  # e o `seq` 2 já foi usado
        outro(2)
    ae.cancelar(conn_app, dois, 1, por="reagendado", agora=agora)
    with pytest.raises(psycopg.errors.CheckViolation) as erro:  # teto de 2 por atendimento (`agenda_max_por_atendimento`)
        outro(3)
    assert erro.value.diag.constraint_name == "agendamento_forma_check"
    assert conn_app.execute("SELECT count(*) FROM ia.agendamento WHERE atendimento_id = %s", (atd,)).fetchone() == (2,)


# --- POST /agendamentos: passo, alarme e idempotência -----------------------------------------------------------------------------------------


def test_post_triplicado_e_noop(ambiente):
    """O ChatGuru repete o Post 3× depois de um 424: o 1º cria, os outros devolvem o gravado e NADA muda (nem atendimento, nem passo, nem job)."""
    ambiente.trocar(enfileirador=EnfileiradorProcrastinate(criar(ff.conninfo(ambiente.banco))))
    ambiente.ligar()
    corpo = corpo_de_agendamento()
    primeiro = ambiente.post("/agendamentos", corpo)
    assert primeiro.status_code == 201 and primeiro.json()["estado"] == "pendente"
    antes = ambiente.consultar(
        "SELECT task_name, status::text, queueing_lock, scheduled_at FROM procrastinate.procrastinate_jobs ORDER BY id"
    )
    for _ in range(2):
        repetido = ambiente.post("/agendamentos", corpo)
        assert repetido.status_code == 200 and repetido.json() == {**primeiro.json(), "repetido": True}
    assert ambiente.post("/agendamentos", {**corpo, "texto_mensagem": "pode ser hoje às 18h"}).status_code == 409  # `chave_reutilizada`
    agendamento = primeiro.json()["agendamento_id"]
    assert [ambiente.escalar(f"SELECT count(*) FROM {t}") for t in ("ia.atendimento", "ia.agendamento")] == [1, 1]
    assert ambiente.consultar("SELECT tipo, resultado FROM ia.passo") == [("agendamento", "proposto")]
    depois = ambiente.consultar(
        "SELECT task_name, status::text, queueing_lock, scheduled_at FROM procrastinate.procrastinate_jobs ORDER BY id"
    )
    assert depois == antes and len(depois) == 1
    assert depois[0][:3] == ("ia:alarme_retomar", "todo", f"retomar:{agendamento}")
    assert depois[0][3] == datetime(
        2026, 11, 17, 20, 0, tzinfo=UTC
    )  # «hoje às 17h» em São Paulo; `schedule_at` = `dispara_em`, não `send_date`


def test_post_grava_o_passo_e_o_alarme_do_retomar_sem_lock_do_chat(ambiente):
    espiao = EspiaDeFila()
    ambiente.trocar(enfileirador=espiao)
    ambiente.ligar()
    r = ambiente.post("/agendamentos", corpo_de_agendamento())
    assert r.status_code == 201
    corpo = r.json()
    assert espiao.retomadas == [
        (uuid.UUID(corpo["agendamento_id"]), uuid.UUID(corpo["atendimento_id"]), CHAT, datetime(2026, 11, 17, 20, 0, tzinfo=UTC))
    ]
    assert ambiente.consultar("SELECT tipo, resultado, fase, turno, agendamento_id::text FROM ia.passo") == [
        ("agendamento", "proposto", "E0", 0, corpo["agendamento_id"])
    ]
    ambiente.post("/agendamentos", corpo_de_agendamento())  # repetido: não enfileira de novo
    assert len(espiao.retomadas) == 1


def test_o_alarme_entra_na_transacao_da_reserva_e_some_junto_se_ela_falha(ambiente):
    """Reserva e alarme são UMA transação: se enfileirar falha, não sobra atendimento `reservado` sem job nem agendamento sem passo."""

    class FilaQueFalha(EspiaDeFila):
        def agendar_retomada(self, *args, **kwargs) -> bool:
            raise RuntimeError("fila fora")

    ambiente.trocar(enfileirador=FilaQueFalha())
    ambiente.ligar()
    assert ambiente.post("/agendamentos", corpo_de_agendamento()).status_code == 500
    assert [ambiente.escalar(f"SELECT count(*) FROM {t}") for t in ("ia.atendimento", "ia.agendamento", "ia.passo", "ia.cofre")] == [
        0,
        0,
        0,
        0,
    ]


def test_agenda_b_digita_false_so_aceita_retoma_fase_e8(ambiente):
    espiao = EspiaDeFila()
    ambiente.trocar(enfileirador=espiao)
    ambiente.ligar()
    r = ambiente.post("/agendamentos", corpo_de_agendamento(retoma_fase="E3"))
    erro = r.json()["erro"]
    assert r.status_code == 422 and (erro["codigo"], erro["campo"], erro["detalhe"]) == (
        "validacao", "retoma_fase", {"regra": "so_e8_sem_agenda_b_digita"}
    )  # fmt: skip
    assert ambiente.escalar("SELECT count(*) FROM ia.atendimento") == 0 and espiao.retomadas == []
    ambiente.configurar("agenda_b_digita", True)
    assert ambiente.post("/agendamentos", corpo_de_agendamento(retoma_fase="E3")).status_code == 201


# --- reaper_lease pula pausado; a noite não o encerra -----------------------------------------------------------------------------------------


async def test_reaper_pula_pausado(conn_app, banco, relogio, versoes):
    """`pausar` põe `lease_ate = retoma_em + 30 min`: o `reaper_lease` só o enxerga depois disso (e então é `retomada_perdida`, não repasse)."""
    retoma = relogio.agora() + timedelta(hours=20)
    pausado = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=retoma)
    agendado = agendado_confirmado(conn_app, relogio.agora, versoes, dispara_em=retoma)
    aberto, _v, _c = novo_aberto(conn_app, relogio.agora, versoes)
    for quando in (retoma - timedelta(hours=19), retoma - timedelta(minutes=1), retoma, retoma + timedelta(minutes=29, seconds=59)):
        vistos = {lease.atendimento_id for lease in jobs.selecionar_leases_vencidos(conn_app, quando)}
        assert pausado.atendimento_id not in vistos and agendado.atendimento_id not in vistos, quando
    depois = retoma + timedelta(minutes=30, seconds=1)
    por_id = {lease.atendimento_id: lease for lease in jobs.selecionar_leases_vencidos(conn_app, depois)}
    assert por_id[pausado.atendimento_id].acao == "retomada_perdida"
    assert por_id[agendado.atendimento_id].acao == "agendamento_perdido"
    assert por_id[aberto].acao == "repassar"  # o aberto, sim, foi visto (a pausa é que é poupada)
    chamadas = Chamadas()
    servicos = montar_servicos(banco, RelogioFalso(depois), chamadas)
    assert await jobs.executar_reaper_lease(servicos) == 3
    assert {(lease.atendimento_id, lease.acao) for lease in chamadas.leases} == {
        (pausado.atendimento_id, "retomada_perdida"), (agendado.atendimento_id, "agendamento_perdido"), (aberto, "repassar"),
    }  # fmt: skip


async def test_desligada_noturna_nao_encerra_pausado(ambiente, banco, conn_super):
    """P-R13 / M-Q2: o timer das 20:15 grava `bloqueio_entrada=true` (entrada nova fechada) e NÃO toca em ninguém; o pausado dorme até a hora
    dele. Só a parada leve MANUAL (`ia_ativa=false`) encerra pausados (D15)."""
    versoes = estado.versoes_vigentes(conn_super)
    relogio = ambiente.relogio
    amanha_0900 = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)  # 09:00 em São Paulo
    with ff.abrir(banco) as conn:
        pausado = pausado_confirmado(conn, relogio.agora, versoes, dispara_em=amanha_0900, fase="E8")
        aberto, _v, _c = novo_aberto(conn, relogio.agora, versoes)
        aguardando, va, _c = novo_aberto(conn, relogio.agora, versoes)
        estado.aguardar_cliente(conn, aguardando, va, relogio=relogio.agora)
        antes = {a: _estado(conn, a) for a in (pausado.atendimento_id, aberto, aguardando)}

    relogio.definir(datetime(2026, 11, 17, 23, 15, 1, tzinfo=UTC))  # 20:15:01 em São Paulo
    chamadas = Chamadas()
    servicos = montar_servicos(banco, relogio, chamadas, tratar_lease_vencido=tratar_lease_de_referencia(banco, relogio, chamadas.leases))
    app = criar(ff.conninfo(banco))
    async with app.open_async():
        await app.tasks["ia:bloqueio_2015"].defer_async(timestamp=int(relogio.agora().timestamp()))
        await rodar(app, servicos)
        for noite in (
            datetime(2026, 11, 17, 23, 20, tzinfo=UTC),
            datetime(2026, 11, 18, 10, 45, tzinfo=UTC),
        ):  # 20:20 e 07:45 do dia seguinte
            relogio.definir(noite)
            await app.tasks["ia:reaper_lease"].defer_async(timestamp=int(noite.timestamp()))
            await app.tasks["ia:expirar_parados"].defer_async(timestamp=int(noite.timestamp()))
            await rodar(app, servicos)
    with ff.abrir(banco) as conn:
        assert config_vigente(conn, "bloqueio_entrada").valor is True
        # o bloqueio e o reaper REAIS (o handler de lease também muda estado): quem tem lease vencido (o `aberto`, de 5 min) foi devolvido ...
        assert (
            _estado(conn, aberto)[0] == "repassando" and _estado(conn, aguardando) == antes[aguardando]
        )  # (o aguardando tem lease de 96 h)
        # ... e quem dorme, não: o `pausado` segue intacto, com a mesma versão, a noite inteira
        assert _estado(conn, pausado.atendimento_id) == antes[pausado.atendimento_id] == ("pausado", antes[pausado.atendimento_id][1])
    assert [j[0] for j in jobs_por_status(conn_super) if "encerrar" in j[0]] == [], (
        "nenhum encerrar_por_chave (alarme ou real) foi agendado"
    )
    assert pausado.atendimento_id not in {lease.atendimento_id for lease in chamadas.leases}, "o reaper de lease poupa quem dorme"
    assert {lease.atendimento_id for lease in chamadas.leases} == {aberto}, "e viu o aberto de lease vencido: o reaper estava vivo"

    # o mesmo `PUT bloqueio_entrada` pela API também não encerra ninguém; a parada leve manual encerra, pausado incluso (decisão D15)
    ambiente.ligar()
    r = ambiente.put("/config/bloqueio_entrada", {"valor": True, "por": POR})
    assert r.json()["efeitos"] == {"encerrar_por_chave_agendados": 0} and ambiente.fila.encerramentos == []
    r = ambiente.put("/config/ia_ativa", {"valor": False, "por": POR, "motivo": "parada leve de ensaio"})
    assert r.json()["efeitos"] == {"encerrar_por_chave_agendados": 2}  # o aguardando e o pausado (o aberto já foi repassado pelo reaper)
    assert {a for a, _, _ in ambiente.fila.encerramentos} == {pausado.atendimento_id, aguardando}

    # e só quando o lease da pausa vence (retoma_em + 30 min), com a volta perdida, o reaper de lease a vê e a devolve
    relogio.definir(amanha_0900 + timedelta(minutes=31))
    async with app.open_async():
        await app.tasks["ia:reaper_lease"].defer_async(timestamp=int(relogio.agora().timestamp()) + 1)
        await rodar(app, servicos)
    assert [lease.acao for lease in chamadas.leases if lease.atendimento_id == pausado.atendimento_id] == ["retomada_perdida"]
    with ff.abrir(banco) as conn:
        assert _estado(conn, pausado.atendimento_id)[0] == "repassando"


def test_so_o_aberto_e_o_aguardando_expiram_por_tempo_o_pausado_dorme():
    """Contrato para a B1.6: o `expirar_parados` real filtra por `jobs.ESTADOS_EXPIRAVEIS`. Fora da parada leve MANUAL (`ESTADOS_DA_PARADA_LEVE`,
    que inclui `pausado`), nada encerra quem dorme."""
    from ia_atendimento.api.config_rotas import ESTADOS_DA_PARADA_LEVE

    assert {"aberto", "aguardando_cliente"} == jobs.ESTADOS_EXPIRAVEIS
    assert {"pausado", "reservado", "repassando", "encerrado"}.isdisjoint(jobs.ESTADOS_EXPIRAVEIS)
    assert "pausado" in ESTADOS_DA_PARADA_LEVE and set(jobs.ESTADOS_EXPIRAVEIS) < set(ESTADOS_DA_PARADA_LEVE)


# --- retomar: a reivindicação (CAS) ---------------------------------------------------------------------------------------------------------


def _servicos(banco, relogio, voltas, **troca):
    return montar_servicos(banco, relogio, Chamadas(), retomar_atendimento=voltas, **troca)


async def test_retomar_do_pausado_reivindica_uma_vez_e_nao_mexe_no_atendimento(banco, conn_app, relogio, versoes):
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara, fase="E5")
    antes = _estado(conn_app, caso.atendimento_id)
    voltas = Voltas()
    servicos = _servicos(banco, relogio, voltas)
    relogio.definir(dispara + timedelta(seconds=3))
    assert await agenda_jobs.executar_retomar(servicos, caso.agendamento_id, _reagendar_ignorando, job_id=41) == "disparado"
    (volta,) = voltas.recebidas
    assert (volta.agendamento_id, volta.atendimento_id, volta.chat_id, volta.entrada, volta.retoma_fase, volta.dispara_em) == (
        caso.agendamento_id, caso.atendimento_id, caso.chat_id, "pausa_ia", "E5", dispara
    )  # fmt: skip
    assert _ag(conn_app, caso.agendamento_id) == ("disparado", 3, "retomou", 41)
    assert _passos(conn_app, caso.atendimento_id) == ["disparado"]
    assert _estado(conn_app, caso.atendimento_id) == antes, "o job só reivindica: sair da pausa e falar é da volta (B5.7c)"
    for _ in range(3):  # alarme + reaper + reexecução: quem chega depois acha `disparado`
        assert await agenda_jobs.executar_retomar(servicos, caso.agendamento_id, _reagendar_ignorando) == "nao_confirmado"
    assert len(voltas.recebidas) == 1 and _passos(conn_app, caso.atendimento_id) == ["disparado"]


async def test_retomar_do_caso_b_entrega_a_volta_sem_tocar_no_reservado(banco, conn_app, relogio, versoes):
    dispara = relogio.agora() + timedelta(hours=2)
    caso = agendado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    voltas = Voltas()
    relogio.definir(dispara)
    assert await agenda_jobs.executar_retomar(_servicos(banco, relogio, voltas), caso.agendamento_id, _reagendar_ignorando) == "disparado"
    assert [(v.entrada, v.retoma_fase) for v in voltas.recebidas] == [("dialogo_agendar", "E8")]
    estado_, _versao = _estado(conn_app, caso.atendimento_id)
    assert estado_ == "reservado" and conn_app.execute(
        "SELECT assumido_em, chatbot_estado FROM ia.atendimento WHERE atendimento_id = %s", (caso.atendimento_id,)
    ).fetchone() == (None, "intocado"), "o chat não foi tocado: quem assume é o `iniciar_agendado` da volta"


@pytest.mark.parametrize(("antes_s", "atraso_s"), [(1, 5.0), (4, 5.0), (60, 60.0), (3600, 3600.0)])
async def test_retomar_cedo_rearma_o_alarme_com_atraso_relativo_e_nao_reivindica(banco, conn_app, relogio, versoes, antes_s, atraso_s):
    """`max(dispara_em, agora + 5 s) - agora`: nunca para uma hora que o banco já considera vencida (R1-04)."""
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    rearmados: list[float] = []

    async def reagendar(atraso: float) -> None:
        rearmados.append(atraso)

    voltas = Voltas()
    relogio.definir(dispara - timedelta(seconds=antes_s))  # o alarme saiu antes do relógio da aplicação
    assert await agenda_jobs.executar_retomar(_servicos(banco, relogio, voltas), caso.agendamento_id, reagendar) == "cedo"
    assert rearmados == [atraso_s] and voltas.recebidas == [] and _ag(conn_app, caso.agendamento_id)[0] == "confirmado"


async def test_relogio_da_app_atrasado_nao_vira_laco_quente(conninfo_app, conn_app, conn_super, banco, versoes):
    """Sonda P3 da revisão: com o relógio da aplicação 2 s atrás do banco, o `cedo` rearmava o alarme PARA `dispara_em` (já vencido no banco) e o
    job voltava na hora: 277 jobs em 3 s. Agora: um alarme, um `retomar` e UM alarme novo, 5 s à frente; e depois que a hora chega, uma volta só."""
    real = datetime.now(UTC)
    dispara = real - timedelta(seconds=1)  # já vencido para o relógio do BANCO
    caso = pausado_confirmado(conn_app, RelogioFalso(real - timedelta(hours=3)).agora, versoes, dispara_em=dispara)
    atrasado = RelogioFalso(dispara - timedelta(seconds=2))  # relógio da app 2 s atrás do dispara_em
    voltas = Voltas()
    servicos = _servicos(banco, atrasado, voltas)
    app = criar(conninfo_app)
    async with app.open_async():
        await fila.agendar_retomada(app, caso.agendamento_id, caso.atendimento_id, caso.chat_id, dispara)
        await asyncio.wait_for(rodar(app, servicos), 5)
    assert conn_super.execute("SELECT count(*) FROM procrastinate.procrastinate_jobs").fetchone()[0] <= 3
    (novo,) = conn_super.execute(
        "SELECT scheduled_at - now() FROM procrastinate.procrastinate_jobs WHERE task_name = 'ia:alarme_retomar' AND status = 'todo'"
    ).fetchall()
    assert timedelta(seconds=3) < novo[0] <= timedelta(seconds=5), "o alarme novo volta no futuro, não na hora"
    assert voltas.recebidas == [] and _ag(conn_app, caso.agendamento_id)[0] == "confirmado"
    # a hora chega (para o relógio da app também) e o alarme novo vence: uma volta, só uma
    atrasado.definir(dispara + timedelta(seconds=3))
    conn_super.execute("UPDATE procrastinate.procrastinate_jobs SET scheduled_at = now() - interval '1 second' WHERE status = 'todo'")
    async with app.open_async():
        await asyncio.wait_for(rodar(app, servicos), 5)
    assert voltas.ids == [caso.agendamento_id] and _ag(conn_app, caso.agendamento_id)[:3] == ("disparado", 3, "retomou")


async def test_retomar_muito_depois_da_hora_nao_entrega_a_volta_marca_expirado_e_o_lead_e_da_vigia(banco, conn_app, relogio, versoes):
    """R1-03: queda longa do worker. 5 h depois (14:00 → 19:00 em SP, fora da janela de 08:30–19:00 do dia seguinte e perto das 24 h do WhatsApp)
    a volta NÃO sai: `expirado`, passo `expirado`, atendimento intocado; o `reaper_lease` vê `retomada_perdida` e o `reaper_agenda` para."""
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara, fase="E5")
    antes = _estado(conn_app, caso.atendimento_id)
    voltas = Voltas()
    servicos = _servicos(banco, relogio, voltas)
    relogio.definir(dispara + timedelta(hours=5))
    assert [v.agendamento_id for v in agenda_jobs.selecionar_vencidos(conn_app, relogio.agora())] == [caso.agendamento_id]
    assert await agenda_jobs.executar_retomar(servicos, caso.agendamento_id, _reagendar_ignorando) == "expirado"
    assert voltas.recebidas == [], "a volta não é entregue tarde"
    assert _ag(conn_app, caso.agendamento_id)[:3] == ("expirado", 3, None)
    assert conn_app.execute(
        "SELECT disparado_em, cancelado_por FROM ia.agendamento WHERE agendamento_id = %s", (caso.agendamento_id,)
    ).fetchone() == (None, None)
    assert _passos(conn_app, caso.atendimento_id) == ["expirado"] and _estado(conn_app, caso.atendimento_id) == antes
    assert [(lease.atendimento_id, lease.acao) for lease in jobs.selecionar_leases_vencidos(conn_app, relogio.agora())] == [
        (caso.atendimento_id, "retomada_perdida")
    ]  # o lead segue `pausado` com o lease vencido: devolvê-lo ao humano é do reaper de lease
    assert agenda_jobs.selecionar_vencidos(conn_app, relogio.agora()) == [], "o reaper_agenda não insiste"
    assert await agenda_jobs.executar_retomar(servicos, caso.agendamento_id, _reagendar_ignorando) == "nao_confirmado"


@pytest.mark.parametrize(
    ("depois", "esperado"),
    [
        (timedelta(minutes=29, seconds=59), "disparado"),
        (timedelta(minutes=30), "disparado"),
        (timedelta(minutes=30, seconds=1), "expirado"),
    ],
)
async def test_o_teto_de_atraso_e_o_lease_retoma_em_mais_folga(banco, conn_app, relogio, versoes, depois, esperado):
    dispara = relogio.agora() + timedelta(hours=2)
    caso = agendado_confirmado(
        conn_app, relogio.agora, versoes, dispara_em=dispara
    )  # caso (b): o `reservado` de vida longa tem o mesmo teto
    relogio.definir(dispara + depois)
    assert await agenda_jobs.executar_retomar(_servicos(banco, relogio, Voltas()), caso.agendamento_id, _reagendar_ignorando) == esperado


async def test_retomar_de_pendente_ou_inexistente_nao_faz_nada(banco, conn_app, relogio, versoes):
    agora = relogio.agora()
    atd, _v, _c = novo_agendado(conn_app, agora, versoes, retoma_em=agora + timedelta(hours=1))
    pendente = inserir_agendamento(
        conn_app, atd, entrada_do_pedido="dialogo_agendar", dispara_em=agora + timedelta(hours=1), pedido_em=agora
    )
    voltas = Voltas()
    servicos = _servicos(banco, relogio, voltas)
    relogio.avancar(hours=2)
    assert await agenda_jobs.executar_retomar(servicos, pendente, _reagendar_ignorando) == "nao_confirmado"  # a confirmação nunca veio
    assert await agenda_jobs.executar_retomar(servicos, uuid.uuid4(), _reagendar_ignorando) == "inexistente"
    assert voltas.recebidas == [] and _ag(conn_app, pendente)[0] == "pendente" and _passos(conn_app, atd) == []


async def test_retomar_com_o_atendimento_fora_da_espera_cancela_por_sistema_e_nao_fala(banco, conn_app, relogio, versoes):
    """Alguém tirou o atendimento da pausa (o cliente voltou antes da hora) e deixou o agendamento `confirmado`: a volta não sai."""
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    _, versao = _estado(conn_app, caso.atendimento_id)
    estado_pausa.sair_da_pausa(conn_app, caso.atendimento_id, versao, relogio=relogio.agora)
    voltas = Voltas()
    relogio.definir(dispara + timedelta(minutes=1))
    assert (
        await agenda_jobs.executar_retomar(_servicos(banco, relogio, voltas), caso.agendamento_id, _reagendar_ignorando) == "fora_do_estado"
    )
    assert voltas.recebidas == []
    assert conn_app.execute("SELECT estado, cancelado_por FROM ia.agendamento WHERE agendamento_id = %s", (caso.agendamento_id,)).fetchone() == (
        "cancelado", "sistema"
    )  # fmt: skip
    assert _passos(conn_app, caso.atendimento_id) == ["cancelado"] and _estado(conn_app, caso.atendimento_id)[0] == "aberto"


@pytest.mark.parametrize("desfecho", ["resolvido", "repassou", "humano_atuou", "reagendado_sistema", "retomou", None])
async def test_o_desfecho_que_a_volta_devolve_vira_o_desfecho_do_disparo(banco, conn_app, relogio, versoes, desfecho):
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    relogio.definir(dispara)
    assert (
        await agenda_jobs.executar_retomar(_servicos(banco, relogio, Voltas(desfecho=desfecho)), caso.agendamento_id, _reagendar_ignorando)
        == "disparado"
    )
    assert _ag(conn_app, caso.agendamento_id)[2] == (desfecho or "retomou")
    assert _passos(conn_app, caso.atendimento_id) == (["disparado", "resolvido"] if desfecho == "resolvido" else ["disparado"])


async def test_a_volta_que_falha_depois_da_reivindicacao_nao_e_repetida_o_lease_devolve_o_lead(banco, conn_app, relogio, versoes):
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    relogio.definir(dispara)
    voltas = Voltas(erro=OSError("chatguru fora"))
    servicos = _servicos(banco, relogio, voltas)
    with pytest.raises(OSError, match="chatguru"):
        await agenda_jobs.executar_retomar(servicos, caso.agendamento_id, _reagendar_ignorando)
    assert _ag(conn_app, caso.agendamento_id)[0] == "disparado"
    assert await agenda_jobs.executar_retomar(servicos, caso.agendamento_id, _reagendar_ignorando) == "nao_confirmado"  # não repete
    assert len(voltas.recebidas) == 1 and _estado(conn_app, caso.atendimento_id)[0] == "pausado"
    perdidos = jobs.selecionar_leases_vencidos(conn_app, dispara + timedelta(minutes=31))  # e o reaper de lease o devolve
    assert [(lease.atendimento_id, lease.acao) for lease in perdidos] == [(caso.atendimento_id, "retomada_perdida")]


async def test_retomar_sem_o_servico_da_volta_falha_antes_de_reivindicar(banco, conn_app, relogio, versoes):
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    relogio.definir(dispara)
    sem_servico = Servicos(relogio=relogio, abrir_conexao=lambda: ff.abrir(banco))  # type: ignore[arg-type]
    with pytest.raises(jobs.ServicoNaoConfigurado):
        await agenda_jobs.executar_retomar(sem_servico, caso.agendamento_id, _reagendar_ignorando)
    assert _ag(conn_app, caso.agendamento_id)[:2] == ("confirmado", 2), "sem a volta para entregar, o agendamento NÃO é reivindicado"


async def test_quatro_retomar_ao_mesmo_tempo_so_um_reivindica(banco, conn_app, relogio, versoes):
    """O CAS é a prova de «nenhum duplicado»: mesmo com o `queueing_lock` furado (alarme + reaper + reexecução), só uma volta sai."""
    dispara = relogio.agora() + timedelta(hours=2)
    caso = agendado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    servicos = _servicos(banco, relogio, Voltas())
    largada = threading.Barrier(4)
    agora = dispara + timedelta(seconds=1)

    def tentar(_: int):
        largada.wait(timeout=10)
        return agenda_jobs._reivindicar(servicos, caso.agendamento_id, agora, None)

    with ThreadPoolExecutor(4) as pool:
        resultados = [f.result(timeout=30) for f in [pool.submit(tentar, n) for n in range(4)]]
    assert sorted(r.codigo for r in resultados) == ["disparado", "nao_confirmado", "nao_confirmado", "nao_confirmado"]
    assert _ag(conn_app, caso.agendamento_id)[:2] == ("disparado", 3) and _passos(conn_app, caso.atendimento_id) == ["disparado"]


# --- reaper_agenda: quem está sem job vivo -----------------------------------------------------------------------------------------------------


def test_reaper_agenda_seleciona_so_o_confirmado_vencido_sem_job_vivo(conn_app, conn_super, relogio, versoes):
    dispara = relogio.agora() + timedelta(hours=1)
    caso = lambda: pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)  # noqa: E731
    sem_job, com_alarme, com_exec, rodando_vivo, rodando_morto, ja_acabou = (caso() for _ in range(6))
    viva, morta = novo_worker(conn_super, 5), novo_worker(conn_super, 600)
    inserir_job(conn_super, "ia:alarme_retomar", f"retomar:{com_alarme.agendamento_id}", "todo")
    inserir_job(conn_super, "ia:retomar", f"retomar_exec:{com_exec.agendamento_id}", "todo", lock=f"chat:{com_exec.chat_id}")
    inserir_job(conn_super, "ia:retomar", f"retomar_exec:{rodando_vivo.agendamento_id}", "doing", viva, lock=f"chat:{rodando_vivo.chat_id}")
    travado = inserir_job(
        conn_super, "ia:retomar", f"retomar_exec:{rodando_morto.agendamento_id}", "doing", morta, lock=f"chat:{rodando_morto.chat_id}"
    )
    inserir_job(
        conn_super, "ia:alarme_retomar", f"retomar:{ja_acabou.agendamento_id}", "succeeded"
    )  # o alarme rodou e o job de verdade se perdeu
    sem_confirmar, _v, _c = novo_agendado(conn_app, relogio.agora(), versoes, retoma_em=dispara)
    inserir_agendamento(conn_app, sem_confirmar, entrada_do_pedido="dialogo_agendar", dispara_em=dispara, pedido_em=relogio.agora())
    ainda_cedo = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara + timedelta(hours=1))
    aberto = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    estado_pausa.sair_da_pausa(conn_app, aberto.atendimento_id, _estado(conn_app, aberto.atendimento_id)[1], relogio=relogio.agora)

    vencidos = {v.agendamento_id: v for v in agenda_jobs.selecionar_vencidos(conn_app, dispara + timedelta(minutes=1))}
    assert set(vencidos) == {sem_job.agendamento_id, ja_acabou.agendamento_id}
    assert rodando_morto.agendamento_id not in vencidos, "`doing` conta como vivo até a `jobs_presos` dá-lo como falho (uma só autoridade)"
    assert travado
    assert vencidos[sem_job.agendamento_id].chat_id == sem_job.chat_id
    assert ainda_cedo.agendamento_id not in vencidos and aberto.agendamento_id not in vencidos  # fora da hora / fora da espera
    assert agenda_jobs.selecionar_vencidos(conn_app, dispara - timedelta(seconds=1)) == []


async def test_executar_reaper_agenda_entrega_cada_vencido_ao_enfileirador(banco, conn_app, relogio, versoes):
    dispara = relogio.agora() + timedelta(hours=1)
    um, dois = (pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara) for _ in range(2))
    pedidos: list[agenda_jobs.Vencido] = []

    async def enfileirar(v: agenda_jobs.Vencido) -> None:
        pedidos.append(v)

    relogio.definir(dispara + timedelta(minutes=2))
    assert await agenda_jobs.executar_reaper_agenda(_servicos(banco, relogio, Voltas()), enfileirar) == 2
    assert {p.agendamento_id for p in pedidos} == {um.agendamento_id, dois.agendamento_id}


# --- a fila: alarme sem lock, job de verdade com lock, periódica --------------------------------------------------------------------------------


async def test_alarme_e_um_por_agendamento_sem_lock_e_o_reagendamento_nao_e_engolido(conninfo_app, conn_super):
    app = criar(conninfo_app)
    ag1, ag2, atd, chat = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), ff.hex24()
    em = datetime(2026, 11, 17, 20, 0, tzinfo=UTC)
    async with app.open_async():
        assert await fila.agendar_retomada(app, ag1, atd, chat, em) is not None
        assert await fila.agendar_retomada(app, ag1, atd, chat, em + timedelta(hours=1)) is None  # o mesmo agendamento: um só alarme
        assert await fila.agendar_retomada(app, ag2, atd, chat, em - timedelta(hours=1)) is not None  # o `seq` 2, mais cedo, não é engolido
    alarmes = _jobs(conn_super, "ia:alarme_retomar")
    assert [(a[1], a[2], a[4]) for a in alarmes] == [(None, f"retomar:{ag1}", em), (None, f"retomar:{ag2}", em - timedelta(hours=1))]
    assert alarmes[0][3] == {"agendamento_id": str(ag1), "atendimento_id": str(atd), "chat_id": chat}


async def test_o_alarme_futuro_nao_prende_o_turno_do_cliente_durante_a_pausa(conninfo_app, conn_super):
    """Com `lock=chat:` no job agendado, o `fetch` do Procrastinate recusaria o turno do mesmo chat até a hora combinada (horas)."""
    app = criar(conninfo_app)
    ag, atd, chat = uuid.uuid4(), uuid.uuid4(), ff.hex24()
    async with app.open_async():
        await fila.agendar_retomada(app, ag, atd, chat, datetime.now(UTC) + timedelta(hours=20))
        await fila.enfileirar_turno(app, atd, chat)
    conn_super.execute(
        "UPDATE procrastinate.procrastinate_jobs SET scheduled_at = now() - interval '1 second' WHERE task_name = 'ia:turno'"
    )
    liberado = conn_super.execute("SELECT task_name FROM procrastinate.procrastinate_fetch_job_v2(NULL, NULL)").fetchone()
    assert liberado == ("ia:turno",)


async def test_o_alarme_vencido_enfileira_o_retomar_com_o_lock_do_chat_e_o_worker_o_executa(
    conninfo_app, conn_super, banco, conn_app, relogio, versoes
):
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    voltas = Voltas()
    servicos = _servicos(banco, relogio, voltas)
    app = criar(conninfo_app)
    async with app.open_async():
        await fila.agendar_retomada(app, caso.agendamento_id, caso.atendimento_id, caso.chat_id, dispara)
        conn_super.execute("UPDATE procrastinate.procrastinate_jobs SET scheduled_at = now() - interval '1 second'")
        relogio.definir(dispara + timedelta(seconds=5))
        await rodar(app, servicos)
    assert [(j[0], j[1], j[2]) for j in _jobs(conn_super, "ia:alarme_retomar")] == [("succeeded", None, f"retomar:{caso.agendamento_id}")]
    (real,) = _jobs(conn_super, "ia:retomar")
    assert real[:3] == ("succeeded", f"chat:{caso.chat_id}", f"retomar_exec:{caso.agendamento_id}")
    assert voltas.ids == [caso.agendamento_id] and _ag(conn_app, caso.agendamento_id)[:3] == ("disparado", 3, "retomou")
    assert _ag(conn_app, caso.agendamento_id)[3] is not None, "o `job_id` do Procrastinate fica na linha"


def test_reaper_agenda_e_periodica_por_minuto():
    app = criar("host=h dbname=d user=u", com_periodicas=True)
    registradas = {pt.task.name: pt.cron for pt in app.periodic_registry.periodic_tasks.values()}
    assert registradas["ia:reaper_agenda"] == "* * * * *" == registradas["ia:reaper_lease"]
    assert {"ia:alarme_retomar", "ia:retomar"} <= set(app.tasks) and "ia:retomar" not in registradas
    assert registradas["ia:bloqueio_2015"] == cron_utc(HORA_BLOQUEIO_ENTRADA, date(2026, 11, 12))
    assert croniter(registradas["ia:reaper_agenda"], datetime(2026, 11, 12, 22, 0, tzinfo=UTC)).get_next(datetime) == datetime(
        2026, 11, 12, 22, 1, tzinfo=UTC
    )


# --- EM4: restart ---------------------------------------------------------------------------------------------------------------------------


async def test_em4_restart_com_tres_confirmados_sem_perda_nem_duplicidade(conninfo_app, conn_app, conn_super, banco, relogio, versoes):
    """Fila de verdade. Três `confirmado` com o alarme na fila; o worker cai e volta em três situações: (0) morto no meio do `retomar`
    (job `doing`, worker sem batimento, lock do chat preso), (1) o alarme sumiu da fila, (2) alarme intacto. O `reaper_agenda` do worker novo
    recoloca o que ficou sem job vivo; o CAS e o `queueing_lock` impedem a segunda volta."""
    dispara = relogio.agora() + timedelta(hours=2)
    casos = [
        pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara, fase="E3"),
        pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara, fase="E5"),
        agendado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara),
    ]
    ids = {c.agendamento_id for c in casos}
    voltas = Voltas()
    servicos = _servicos(banco, relogio, voltas)

    # worker 1: sobe com os alarmes na fila, nada venceu, e cai
    worker1 = criar(conninfo_app)
    async with worker1.open_async():
        for c in casos:
            assert await fila.agendar_retomada(worker1, c.agendamento_id, c.atendimento_id, c.chat_id, c.dispara_em) is not None
        await rodar(worker1, servicos)
    assert voltas.recebidas == [] and [j[1] for j in jobs_por_status(conn_super, "ia:alarme_retomar")] == ["todo"] * 3

    # a hora chega com o worker fora do ar
    relogio.definir(dispara + timedelta(minutes=1))
    morto = novo_worker(conn_super, 600)
    conn_super.execute(
        "UPDATE procrastinate.procrastinate_jobs SET status = 'succeeded' WHERE queueing_lock = %s", (f"retomar:{casos[0].agendamento_id}",)
    )
    travado = inserir_job(
        conn_super, "ia:retomar", f"retomar_exec:{casos[0].agendamento_id}", "doing", morto, lock=f"chat:{casos[0].chat_id}"
    )
    conn_super.execute("DELETE FROM procrastinate.procrastinate_jobs WHERE queueing_lock = %s", (f"retomar:{casos[1].agendamento_id}",))
    conn_super.execute(
        "UPDATE procrastinate.procrastinate_jobs SET scheduled_at = now() - interval '1 second' WHERE queueing_lock = %s",
        (f"retomar:{casos[2].agendamento_id}",),
    )

    # worker 2 (outro processo, outro app): o `reaper_agenda` da periódica e as filas que sobraram
    worker2 = criar(conninfo_app)
    async with worker2.open_async():
        await worker2.tasks["ia:jobs_presos"].defer_async(timestamp=int(relogio.agora().timestamp()))  # a periódica geral ...
        await worker2.tasks["ia:reaper_agenda"].defer_async(
            timestamp=int(relogio.agora().timestamp())
        )  # ... e a da agenda, no mesmo minuto
        for _ in range(6):
            await rodar(worker2, servicos)
            if set(voltas.ids) == ids:
                break
    assert sorted(voltas.ids) == sorted(ids) and len(voltas.ids) == 3, "nenhum perdido, nenhum duplicado"
    for c in casos:
        assert _ag(conn_app, c.agendamento_id)[:3] == ("disparado", 3, "retomou")
        assert _passos(conn_app, c.atendimento_id) == ["disparado"]
    assert (
        dict(conn_super.execute("SELECT id, status::text FROM procrastinate.procrastinate_jobs WHERE id = %s", (travado,)).fetchall())[
            travado
        ]
        == "failed"
    )
    assert not [j for j in jobs_por_status(conn_super) if j[1] in ("todo", "doing")], "nada pendente na fila"
    assert [_estado(conn_app, c.atendimento_id)[0] for c in casos] == ["pausado", "pausado", "reservado"], (
        "o job não encosta no atendimento"
    )

    # worker 3: reinício + reaper de novo + retomar duplicados de propósito (alarme e reaper juntos): continua 3 e só 3
    worker3 = criar(conninfo_app)
    async with worker3.open_async():
        for _ in range(2):
            await worker3.tasks["ia:reaper_agenda"].defer_async(timestamp=int(relogio.agora().timestamp()) + 60)
            for c in casos:
                await fila.enfileirar_retomar(worker3, c.agendamento_id, c.atendimento_id, c.chat_id)
                await fila.enfileirar_retomar(worker3, c.agendamento_id, c.atendimento_id, c.chat_id)  # `queueing_lock`: o 2º é engolido
            await rodar(worker3, servicos)
    assert sorted(voltas.ids) == sorted(ids) and len(voltas.ids) == 3
    assert all(_ag(conn_app, c.agendamento_id)[1] == 3 for c in casos), "a linha não foi mexida de novo"


async def test_reaper_agenda_nao_reenfileira_o_que_tem_job_vivo(conninfo_app, conn_app, conn_super, banco, relogio, versoes):
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    relogio.definir(dispara + timedelta(minutes=1))
    app = criar(conninfo_app)
    async with app.open_async():
        await fila.agendar_retomada(
            app, caso.agendamento_id, caso.atendimento_id, caso.chat_id, dispara
        )  # alarme `todo`, ainda não vencido no banco
        await app.tasks["ia:reaper_agenda"].defer_async(timestamp=1)
        await rodar(app, _servicos(banco, relogio, Voltas()))
    assert _jobs(conn_super, "ia:retomar") == [], "alarme `todo` é job vivo: o reaper espera"
    assert [j[0] for j in _jobs(conn_super, "ia:reaper_agenda")] == ["succeeded"]


async def test_reaper_agenda_nao_insiste_quando_o_atendimento_ja_saiu_da_espera(
    conninfo_app, conn_app, conn_super, banco, relogio, versoes
):
    """Depois de `retoma_em + folga` o `reaper_lease` devolve o lead (`retomada_perdida` ⇒ repasse): o atendimento sai de `pausado` e a agenda
    para de insistir (sem isto o reaper reenfileiraria a volta de um lead já repassado, para sempre)."""
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    _, versao = _estado(conn_app, caso.atendimento_id)
    estado.repassar(
        conn_app, caso.atendimento_id, versao, modo="fila", motivo="retomada_perdida", relogio=relogio.agora
    )  # o reaper_lease devolveu
    relogio.definir(dispara + timedelta(minutes=45))
    assert agenda_jobs.selecionar_vencidos(conn_app, relogio.agora()) == []


def test_registrar_desfecho_trava_o_atendimento_antes_do_agendamento(banco, conn_app, conn_super, relogio, versoes):
    """R1-08: a ordem de locks é sempre atendimento → agendamento (a de `_reivindicar` e da B5.7c). Com o atendimento preso por outra transação,
    `_registrar_desfecho` espera NELE sem ter tocado na linha do agendamento; na ordem inversa a linha ficava travada e dois `retomar`/cancelamentos
    se enroscavam em deadlock."""
    dispara = relogio.agora() + timedelta(hours=2)
    caso = pausado_confirmado(conn_app, relogio.agora, versoes, dispara_em=dispara)
    relogio.definir(dispara + timedelta(seconds=1))
    servicos = _servicos(banco, relogio, Voltas())
    reivindicacao = agenda_jobs._reivindicar(servicos, caso.agendamento_id, relogio.agora(), None)
    assert reivindicacao.codigo == "disparado" and reivindicacao.volta is not None
    erros: list[BaseException] = []

    def registrar() -> None:
        try:
            agenda_jobs._registrar_desfecho(servicos, reivindicacao.volta, "resolvido")
        except BaseException as erro:
            erros.append(erro)

    with conn_super.transaction():
        conn_super.execute("SELECT 1 FROM ia.atendimento WHERE atendimento_id = %s FOR UPDATE", (caso.atendimento_id,))
        fio = threading.Thread(target=registrar)
        fio.start()
        prazo = time.monotonic() + 15
        while not conn_app.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock' AND query LIKE '%FOR UPDATE%'"
        ).fetchone()[0]:
            assert time.monotonic() < prazo, "o registro do desfecho não chegou a esperar o lock do atendimento"
            time.sleep(0.02)
        with conn_app.transaction():  # a linha do agendamento tem de estar LIVRE enquanto o atendimento é esperado
            conn_app.execute("SELECT 1 FROM ia.agendamento WHERE agendamento_id = %s FOR UPDATE NOWAIT", (caso.agendamento_id,))
    fio.join(15)
    assert erros == [] and _ag(conn_app, caso.agendamento_id)[2] == "resolvido"


# --- BAIXOS da revisão 1 (R1-10, R1-11, R1-14) -------------------------------------------------------------------------------------------------


def test_post_usa_agenda_folga_min_da_config_e_nao_o_padrao_de_30(ambiente):
    """R1-11 (M1): a API ignorava `agenda_folga_min` sem que nenhum teste visse (só se testava a folga de 30)."""
    ambiente.ligar()
    ambiente.configurar("agenda_folga_min", 45)
    r = ambiente.post("/agendamentos", corpo_de_agendamento())
    assert r.status_code == 201
    retoma, lease = ambiente.consultar(
        "SELECT retoma_em, lease_ate FROM ia.atendimento WHERE atendimento_id = %s", (r.json()["atendimento_id"],)
    )[0]
    assert lease - retoma == timedelta(minutes=45)


def test_o_422_de_retoma_fase_vem_antes_das_recusas_de_config(ambiente):
    """R1-11 (M2), D11: com a agenda e a IA desligadas (o seed), `retoma_fase=E3` é 422 `validacao`, não 409 `agenda_desligada`."""
    r = ambiente.post("/agendamentos", corpo_de_agendamento(retoma_fase="E3"))
    assert r.status_code == 422 and r.json()["erro"]["campo"] == "retoma_fase"
    assert (
        ambiente.post("/agendamentos", corpo_de_agendamento()).json()["erro"]["codigo"] == "agenda_desligada"
    )  # com E8, a recusa de config vale


def test_reaper_agenda_tem_queueing_lock_e_periodicas_atrasadas_nao_empilham(conninfo_app, conn_super):
    """R1-11 (M3): sem o `queueing_lock` o teste não via nada; um tick atrasado empilharia outro `reaper_agenda` atrás do primeiro."""
    from procrastinate import exceptions as pexc

    app = criar(conninfo_app)
    assert app.tasks["ia:reaper_agenda"].queueing_lock == "reaper_agenda"

    async def duas_vezes() -> None:
        async with app.open_async():
            await app.tasks["ia:reaper_agenda"].defer_async(timestamp=1)
            with pytest.raises(pexc.AlreadyEnqueued):
                await app.tasks["ia:reaper_agenda"].defer_async(timestamp=2)

    asyncio.run(duas_vezes())
    assert (
        conn_super.execute("SELECT count(*) FROM procrastinate.procrastinate_jobs WHERE task_name = 'ia:reaper_agenda'").fetchone()[0] == 1
    )


def test_segundo_pedido_no_mesmo_chat_nao_cria_segundo_agendamento_ativo(ambiente):
    """R1-14: o invariante «um ativo por atendimento» pelo caminho do POST (o teste do banco só provava o índice): o atendimento `reservado` tranca o chat."""
    ambiente.ligar()
    assert ambiente.post("/agendamentos", corpo_de_agendamento()).status_code == 201
    outro = ambiente.post("/agendamentos", corpo_de_agendamento(datetime_post="2026-11-17T11:56:00-03:00"))  # outra chave, mesmo chat
    assert outro.status_code == 409 and outro.json()["erro"]["codigo"] == "chat_ocupado"
    assert [ambiente.escalar(f"SELECT count(*) FROM {t}") for t in ("ia.atendimento", "ia.agendamento")] == [1, 1]
