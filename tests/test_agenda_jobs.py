"""Pausa combinada e jobs da agenda (B5.7b): `pausado`, `retomar`, `reaper_agenda` e `POST /agendamentos` com a fila de verdade.

Entregáveis do roteiro: EM4 (restart com 3 `confirmado`, sem perda nem duplicidade), `test_um_agendamento_ativo_por_atendimento`,
`test_post_triplicado_e_noop`, `test_reaper_pula_pausado`, `test_desligada_noturna_nao_encerra_pausado` e `test_pausar_nunca_em_E7`.
A volta em si (pré-checagens, mensagem) é da B5.7c: aqui o serviço `retomar_atendimento` é um espião (`Voltas`) e o que se prova é o CAS, a fila,
o lock do chat, o reaper e a ausência de efeito no chat. A reivindicação do `retomar`, o `reaper_agenda` e a fila ficam em `test_agenda_retomar.py`
(o arquivo passava de 800 linhas, R2-07).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from ia_atendimento import agenda_estado as ae
from ia_atendimento import estado, estado_pausa, fila, jobs
from ia_atendimento.chave import config_vigente
from ia_atendimento.enfileirador import EnfileiradorProcrastinate
from ia_atendimento.estado import EntradaInvalida, TransicaoInvalida
from ia_atendimento.relogio import RelogioFalso
from tests import apoio_api
from tests import fixtures_fila as ff
from tests.apoio_agenda import (
    Voltas,
    agendado_confirmado,
    criar,
    inserir_agendamento,
    inserir_job,
    novo_aberto,
    novo_agendado,
    novo_worker,
    pausado_confirmado,
    rodar,
    tratar_lease_de_referencia,
)
from tests.apoio_agenda import estado_e_versao as _estado
from tests.apoio_agenda import linha_do_agendamento as _ag
from tests.apoio_agenda import passos_do_agendamento as _passos
from tests.apoio_agenda import servicos_com_volta as _servicos
from tests.apoio_api import CHAT, EspiaDeFila, corpo_de_agendamento
from tests.fixtures_fila import Chamadas, jobs_por_status, montar_servicos

ambiente = apoio_api.ambiente
conn_app, conn_super, relogio, conninfo_app = ff.conn_app, ff.conn_super, ff.relogio, ff.conninfo_app
pytestmark = pytest.mark.banco
POR = "operador.teste@glcapital.invalid"


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


def test_segundo_pedido_no_mesmo_chat_nao_cria_segundo_agendamento_ativo(ambiente):
    """R1-14: o invariante «um ativo por atendimento» pelo caminho do POST (o teste do banco só provava o índice): o atendimento `reservado` tranca o chat."""
    ambiente.ligar()
    assert ambiente.post("/agendamentos", corpo_de_agendamento()).status_code == 201
    outro = ambiente.post("/agendamentos", corpo_de_agendamento(datetime_post="2026-11-17T11:56:00-03:00"))  # outra chave, mesmo chat
    assert outro.status_code == 409 and outro.json()["erro"]["codigo"] == "chat_ocupado"
    assert [ambiente.escalar(f"SELECT count(*) FROM {t}") for t in ("ia.atendimento", "ia.agendamento")] == [1, 1]
