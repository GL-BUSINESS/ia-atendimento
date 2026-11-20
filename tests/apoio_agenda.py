"""Apoio dos testes da pausa combinada e dos jobs da agenda (B5.7b): atendimentos pausados/agendados pelas transições de verdade e linhas de
`ia.agendamento` por SQL (a criação do caso (a) é da B5.7c). Tudo sintético, sem PII.
"""

from __future__ import annotations

import itertools
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import psycopg

from ia_atendimento import agenda_estado as ae
from ia_atendimento import estado, estado_pausa, fila
from ia_atendimento.chave import ia_ativa_agora, registrar_config
from ia_atendimento.estado import Versoes
from ia_atendimento.estado_conversa import EstadoConversa, gravar_estado_conversa
from ia_atendimento.jobs import Volta
from ia_atendimento.relogio import RelogioFalso
from tests.estado_apoio import entrada
from tests.fixtures_fila import Chamadas, montar_servicos

_SEQ = itertools.count(1)
FOLGA_MIN = 30


@dataclass
class Caso:
    """Um atendimento à espera da volta e o agendamento `confirmado` dele."""

    atendimento_id: uuid.UUID
    agendamento_id: uuid.UUID
    chat_id: str
    dispara_em: datetime


@dataclass
class Voltas:
    """Espião do serviço `retomar_atendimento` (a volta é da B5.7c): guarda cada `Volta` recebida e devolve o desfecho pedido."""

    recebidas: list[Volta] = field(default_factory=list)
    desfecho: Any = None  # o que cada volta devolve (um desfecho, um `Adiar` ou `None`)
    sequencia: list[Any] = field(default_factory=list)  # se houver, uma resposta por volta, na ordem (depois, `desfecho`)
    erro: Exception | None = None

    async def __call__(self, volta: Volta) -> Any:
        self.recebidas.append(volta)
        if self.erro is not None:
            raise self.erro
        return self.sequencia.pop(0) if self.sequencia else self.desfecho

    @property
    def ids(self) -> list[uuid.UUID]:
        return [v.agendamento_id for v in self.recebidas]


def novo_aberto(conn: psycopg.Connection, relogio: Any, versoes: Versoes, *, fase: str = "E3") -> tuple[uuid.UUID, int, str]:
    """Atendimento `aberto` (de verdade: `abrir` + `iniciar` + fase) num chat novo. `relogio` é o callable que as transições esperam."""
    n = next(_SEQ)
    chat = f"{n:024x}"
    pessoa = str(uuid.uuid4())
    resultado = estado.abrir(
        conn,
        origem="n8n_braco",
        entrada=entrada(chave_logica=f"venda:{n:032x}", chat_id=chat, pessoa_id=pessoa),
        versoes=versoes,
        modo_global="duble",
        chats_teste=frozenset(),
        faixa_esforco="media",
        comissao_esperada_brl=None,
        relogio=relogio,
    )
    v = estado.iniciar(
        conn, resultado.atendimento_id, resultado.versao, chatbot_antes="desligado", chatbot_estado="desligado_pela_ia", relogio=relogio
    )
    v = gravar_estado_conversa(conn, resultado.atendimento_id, v, EstadoConversa(fase=fase), relogio=relogio)
    return resultado.atendimento_id, v, chat


def novo_agendado(
    conn: psycopg.Connection, agora: datetime, versoes: Versoes, *, retoma_em: datetime, folga_min: int = FOLGA_MIN
) -> tuple[uuid.UUID, int, str]:
    """Caso (b): `reservado` de vida longa por `abrir_agendado`. Devolve (atendimento, versao, chat).

    Liga `ia_ativa` (instância no ar): desde a B1.6a o `retomar` do reservado agendado recusa com a IA desligada (R1-31)."""
    if not ia_ativa_agora(conn):
        registrar_config(conn, "ia_ativa", True, "teste", relogio=RelogioFalso(agora), motivo="instância no ar (apoio_agenda)")
    n = next(_SEQ)
    chat = f"{n:024x}"
    resultado = estado_pausa.abrir_agendado(
        conn,
        origem="n8n_braco",
        chave_logica=f"agendar:{chat}:{n:016x}",
        disparado_por="dialogo_agendar",
        pessoa_id=uuid.uuid4(),
        chat_id=chat,
        phone_id="89abcdef0123456789abcdef",
        clt_job_id=uuid.uuid4(),
        versoes=versoes,
        modo="duble",
        retoma_em=retoma_em,
        ultimo_cliente_em=agora,
        agora=agora,
        folga_min=folga_min,
    )
    return resultado.atendimento_id, resultado.versao, chat


def inserir_agendamento(
    conn: psycopg.Connection,
    atendimento_id: uuid.UUID,
    *,
    entrada_do_pedido: str,
    dispara_em: datetime,
    pedido_em: datetime,
    retoma_fase: str | None = "E8",
    seq: int = 1,
) -> uuid.UUID:
    """Linha `pendente` do agendamento por SQL, coerente com o CHECK (`msg_chave` e `chave_logica` na forma do contrato 08 §5.5)."""
    pessoa, chat = conn.execute("SELECT pessoa_id, chat_id FROM ia.atendimento WHERE atendimento_id = %s", (atendimento_id,)).fetchone()
    sufixo = uuid.uuid4().hex[:16]
    chave = f"agendar:{chat}:{sufixo}"
    linha = conn.execute(
        "INSERT INTO ia.agendamento (atendimento_id, pessoa_id, chat_id, entrada, seq, pedido_em, msg_chave, texto_hash, retoma_fase,"
        " horario_extraido, tipo_extracao, extrator_versao, confianca, dispara_em, chave_logica, idem_key)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'explicita', '1', 'alta', %s, %s, encode(sha256(convert_to(%s, 'UTF8')), 'hex'))"
        " RETURNING agendamento_id",
        (atendimento_id, pessoa, chat, entrada_do_pedido, seq, pedido_em, f"cg:{chat}:{sufixo}", "a" * 64, retoma_fase, dispara_em,
         dispara_em, chave, chave),
    ).fetchone()  # fmt: skip
    return linha[0]


def pausado_confirmado(conn: psycopg.Connection, relogio: Any, versoes: Versoes, *, dispara_em: datetime, fase: str = "E3") -> Caso:
    """Caso (a) completo: `aberto` → `pausar` → agendamento `pausa_ia` → `confirmar` (cliente)."""
    atendimento_id, versao, chat = novo_aberto(conn, relogio, versoes, fase=fase)
    estado_pausa.pausar(conn, atendimento_id, versao, retoma_em=dispara_em, retoma_fase=fase, relogio=relogio)
    agendamento_id = inserir_agendamento(
        conn, atendimento_id, entrada_do_pedido="pausa_ia", dispara_em=dispara_em, pedido_em=relogio(), retoma_fase=fase
    )
    ae.confirmar(conn, agendamento_id, 1, origem="cliente", agora=relogio())
    return Caso(atendimento_id, agendamento_id, chat, dispara_em)


def agendado_confirmado(conn: psycopg.Connection, relogio: Any, versoes: Versoes, *, dispara_em: datetime) -> Caso:
    """Caso (b) completo: `abrir_agendado` → agendamento `dialogo_agendar` → `confirmar`."""
    agora = relogio()
    atendimento_id, _versao, chat = novo_agendado(conn, agora, versoes, retoma_em=dispara_em)
    agendamento_id = inserir_agendamento(conn, atendimento_id, entrada_do_pedido="dialogo_agendar", dispara_em=dispara_em, pedido_em=agora)
    ae.confirmar(conn, agendamento_id, 1, origem="cliente", agora=agora)
    return Caso(atendimento_id, agendamento_id, chat, dispara_em)


def estado_do_atendimento(conn: psycopg.Connection, atendimento_id: uuid.UUID) -> tuple[str, int, timedelta | None]:
    estado_, versao, lease = conn.execute(
        "SELECT estado, versao, lease_ate - retoma_em FROM ia.atendimento WHERE atendimento_id = %s", (atendimento_id,)
    ).fetchone()
    return estado_, versao, lease


def tratar_lease_de_referencia(
    banco: Any, relogio: Any, vistos: list[Any] | None = None, notas: list[tuple[uuid.UUID, str | None]] | None = None
):
    """`tratar_lease_vencido` que MUDA o estado de verdade (o da B1.6 fará): `abortar` e `agendamento_perdido` abortam o `reservado`; o resto
    repassa. Substitui o espião que só anotava: com ele, um `pausar` que deixasse o lease curto demais passaria despercebido (R1-06).

    Na MESMA transação fecha a linha do agendamento (`fechar_volta_perdida`, R2-03) e anota a nota ao consultor que é verdade (`notas`)."""
    from tests import fixtures_fila as ff

    async def tratar(lease: Any) -> None:
        if vistos is not None:
            vistos.append(lease)
        with ff.abrir(banco) as conn, conn.transaction():
            fechada = ae.fechar_volta_perdida(conn, lease.atendimento_id, agora=relogio.agora())
            if notas is not None:
                notas.append((lease.atendimento_id, fechada.nota if fechada else None))
            versao = conn.execute("SELECT versao FROM ia.atendimento WHERE atendimento_id = %s", (lease.atendimento_id,)).fetchone()[0]
            if lease.acao in ("abortar", "agendamento_perdido"):
                estado.abortar(conn, lease.atendimento_id, versao, motivo=lease.acao, relogio=relogio.agora)
            else:
                estado.repassar(conn, lease.atendimento_id, versao, modo="fila", motivo=lease.acao, relogio=relogio.agora)

    return tratar


def inserir_job(
    conn: psycopg.Connection, tarefa: str, queueing_lock: str, status: str, worker_id: int | None = None, lock: str | None = None
) -> int:
    return conn.execute(
        "INSERT INTO procrastinate.procrastinate_jobs (queue_name, task_name, lock, queueing_lock, status, worker_id)"
        " VALUES ('default', %s, %s, %s, %s::procrastinate.procrastinate_job_status, %s) RETURNING id",
        (tarefa, lock, queueing_lock, status, worker_id),
    ).fetchone()[0]


def novo_worker(conn: psycopg.Connection, segundos_atras: int) -> int:
    return conn.execute(
        "INSERT INTO procrastinate.procrastinate_workers (last_heartbeat) VALUES (now() - make_interval(secs => %s)) RETURNING id",
        (segundos_atras,),
    ).fetchone()[0]


# --- ajudantes dos testes de agenda (compartilhados por test_agenda_jobs e test_agenda_retomar) ---


def criar(conninfo: str, **opcoes):
    return fila.criar_app(conninfo, com_periodicas=opcoes.pop("com_periodicas", False))


async def rodar(app, servicos, **opcoes) -> None:
    """Worker que processa o que está vencido e sai (`wait=False`): um «processo» do worker."""
    await app.run_worker_async(
        wait=False, install_signal_handlers=False, additional_context={"servicos": servicos}, fetch_job_polling_interval=0.05, **opcoes
    )


def jobs_da_tarefa(conn: psycopg.Connection, tarefa: str):
    return conn.execute(
        "SELECT status::text, lock, queueing_lock, args, scheduled_at FROM procrastinate.procrastinate_jobs WHERE task_name = %s ORDER BY id",
        (tarefa,),
    ).fetchall()


def estado_e_versao(conn: psycopg.Connection, atendimento_id: uuid.UUID) -> tuple[str, int]:
    return conn.execute("SELECT estado, versao FROM ia.atendimento WHERE atendimento_id = %s", (atendimento_id,)).fetchone()


def linha_do_agendamento(conn: psycopg.Connection, agendamento_id: uuid.UUID) -> tuple[str, int, str | None, int | None]:
    return conn.execute(
        "SELECT estado, versao, desfecho_disparo, job_id FROM ia.agendamento WHERE agendamento_id = %s", (agendamento_id,)
    ).fetchone()


def passos_do_agendamento(conn: psycopg.Connection, atendimento_id: uuid.UUID) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT resultado FROM ia.passo WHERE atendimento_id = %s AND tipo = 'agendamento' ORDER BY ordem", (atendimento_id,)
        )
    ]


async def reagendar_ignorando(_: datetime) -> None:
    raise AssertionError("não era para reagendar")


def servicos_com_volta(banco, relogio, voltas, **troca):
    return montar_servicos(banco, relogio, Chamadas(), retomar_atendimento=voltas, **troca)
