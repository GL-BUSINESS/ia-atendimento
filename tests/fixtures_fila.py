"""Fixtures e ajudantes da B1.3 (chave, fila, prontidão): conexão como `ia_app_a`, relógio falso e linhas de `ia.atendimento` por SQL.

Ficam fora do `conftest.py` de propósito (a B1.1 mexe nele em paralelo): cada módulo de teste importa o que usa.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest
from psycopg.types.json import Jsonb

from ia_atendimento.relogio import RelogioFalso
from tests.banco import SENHA_LOGIN, SENHA_SUPER, SUPER, Banco

# terça-feira 17/11/2026 12:00 em São Paulo: dentro da janela, sem feriado, sem DATAPREV
INSTANTE_UTIL = datetime(2026, 11, 17, 15, 0, tzinfo=UTC)
LOGIN_APP = "ia_app_a"


@pytest.fixture
def relogio() -> RelogioFalso:
    return RelogioFalso(INSTANTE_UTIL)


def conninfo(banco: Banco, usuario: str = LOGIN_APP) -> str:
    s = banco.servidor
    senha = SENHA_SUPER if usuario == SUPER else SENHA_LOGIN
    return f"host={s.host} port={s.port} dbname={banco.nome} user={usuario} password={senha}"


@pytest.fixture
def conninfo_app(banco: Banco) -> str:
    return conninfo(banco)


def abrir(banco: Banco, usuario: str = LOGIN_APP) -> psycopg.Connection:
    """Conexão com `search_path=procrastinate,public` (gatilhos do Procrastinate usam nomes sem schema), como a do runtime (OPERACAO §4)."""
    from ia_atendimento.fila import conninfo_da_fila

    return psycopg.connect(conninfo_da_fila(conninfo(banco, usuario)), autocommit=True, connect_timeout=5)


@pytest.fixture
def conn_app(banco: Banco) -> Iterator[psycopg.Connection]:
    """Conexão como o runtime (`ia_app_a`): o que o código de produção pode, o teste pode; nada além."""
    with abrir(banco) as conn:
        yield conn


@pytest.fixture
def conn_super(banco: Banco) -> Iterator[psycopg.Connection]:
    """Superusuário só para montar cenário (linhas que o runtime não insere) e para o teste olhar o estado."""
    with abrir(banco, "postgres") as conn:
        yield conn


def hex24() -> str:
    return uuid.uuid4().hex[:24]


def inserir_atendimento(
    conn: psycopg.Connection,
    *,
    estado: str = "aberto",
    chat_id: str | None = None,
    iniciado_em: datetime = INSTANTE_UTIL,
    custo_modelo: float = 0,
    custo_midia: float = 0,
    modo: str = "duble",
    gatilho: str = "venda",
    pessoa_id: uuid.UUID | None = None,
    lease_ate: datetime | None = None,
    retoma_em: datetime | None = None,
) -> uuid.UUID:
    """Insere um atendimento sintético válido para o estado pedido (os CHECKs do esquema continuam valendo)."""
    chave = f"venda:{uuid.uuid4().hex[:32]}"
    _fase, conversa, assumido = {
        "reservado": ("E0", {"fase": "E0"}, None),
        "aberto": ("E1", {"fase": "E1"}, iniciado_em),
        "aguardando_cliente": ("E3", {"fase": "E3"}, iniciado_em),
        "pausado": ("E3", {"fase": "E3", "pausa": {"retoma_fase": "E3"}}, iniciado_em),
        "repassando": ("E10", {"fase": "E10"}, iniciado_em),
        "encerrado": ("E9", {"fase": "E9"}, iniciado_em),
    }[estado]
    if estado == "pausado" and retoma_em is None:
        retoma_em = iniciado_em + timedelta(hours=1)
    if estado == "encerrado":
        lease_ate = None
    elif lease_ate is None:
        lease_ate = max(iniciado_em, retoma_em or iniciado_em) + timedelta(minutes=5)
    encerrado = {"desfecho": "sem_venda", "encerrado_em": iniciado_em + timedelta(minutes=1)} if estado == "encerrado" else {}
    colunas: dict[str, Any] = {
        "origem": "n8n_braco",
        "chave_logica": chave,
        "idempotency_key": hashlib.sha256(chave.encode()).hexdigest(),
        "entrada_fingerprint": hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        "gatilho": gatilho,
        "disparado_por": "teste",
        "criterio_versao": "c1" if gatilho == "venda" else None,
        "faixa_esforco": "media",
        "pessoa_id": pessoa_id or uuid.uuid4(),
        "chat_id": chat_id or hex24(),
        "phone_id": hex24(),
        "roteiro_versao": 1,
        "regras_versao": 1,
        "catalogo_versao": 1,
        "motor_versao": 1,
        "modo": modo,
        "estado": estado,
        "estado_conversa": Jsonb(conversa),
        "assumido_em": assumido,
        "lease_ate": lease_ate,
        "retoma_em": retoma_em,
        "custo_modelo_brl": custo_modelo,
        "custo_midia_brl": custo_midia,
        "iniciado_em": iniciado_em,
        "atualizado_em": iniciado_em,
        **encerrado,
    }
    nomes = ", ".join(colunas)
    marcas = ", ".join(f"%({c})s" for c in colunas)
    linha = conn.execute(f"INSERT INTO ia.atendimento ({nomes}) VALUES ({marcas}) RETURNING atendimento_id", colunas).fetchone()
    assert linha is not None
    return linha[0]


def inserir_custo(conn: psycopg.Connection, atendimento_id: uuid.UUID, custo: float, ocorrido_em: datetime) -> None:
    """Um passo `erro` com `custo_brl` (a fonte do gasto, contrato 08 §9) na próxima `ordem` do atendimento."""
    conn.execute(
        "INSERT INTO ia.passo (atendimento_id, ordem, ocorrido_em, tipo, texto, turno, fase, peca, custo_brl)"
        " SELECT %s, coalesce(max(ordem), 0) + 1, %s, 'erro', 'Erro na peça modelo.', 1, 'E1', 'modelo', %s FROM ia.passo WHERE atendimento_id = %s",
        (atendimento_id, ocorrido_em, custo, atendimento_id),
    )


def inserir_opt_out(conn: psycopg.Connection, pessoa_id: uuid.UUID, tipo: str = "opt_out") -> None:
    chave = f"t14:{pessoa_id}:{tipo}:{uuid.uuid4().hex[:8]}"
    conn.execute(
        "INSERT INTO ia.opt_out (pessoa_id, tipo, origem, chave_logica, idem_key, registrado_por) VALUES (%s, %s, 'operador', %s, %s, 'teste')",
        (pessoa_id, tipo, chave, hashlib.sha256(chave.encode()).hexdigest()),
    )


def estados_dos_atendimentos(conn: psycopg.Connection) -> dict[uuid.UUID, tuple[str, int]]:
    return {r[0]: (r[1], r[2]) for r in conn.execute("SELECT atendimento_id, estado, versao FROM ia.atendimento")}


# --- fila ------------------------------------------------------------------------------------------------------------------------------


@dataclass
class Chamadas:
    """Espião dos serviços injetados: cada lista guarda o que o handler chamou (mutável de propósito, é instrumento de teste)."""

    turnos: list[uuid.UUID] = field(default_factory=list)
    iniciados: list[uuid.UUID] = field(default_factory=list)
    lembretes: list[tuple[uuid.UUID, int, bool]] = field(default_factory=list)
    encerrados_sem_lembrete: list[tuple[uuid.UUID, str]] = field(default_factory=list)
    expirados: int = 0
    leases: list[Any] = field(default_factory=list)
    auditados: list[tuple[uuid.UUID, ...]] = field(default_factory=list)
    instantaneos: dict[uuid.UUID, Any] = field(default_factory=dict)


def montar_servicos(banco: Banco, relogio: RelogioFalso, chamadas: Chamadas, **troca: Any):
    """`Servicos` com fakes que só registram; `troca` substitui qualquer campo (ex.: `processar_turno=lento`)."""
    from ia_atendimento.chave import LeitorConfig
    from ia_atendimento.jobs import Servicos

    @contextmanager
    def abrir_conexao() -> Iterator[psycopg.Connection]:
        with abrir(banco) as conn:
            yield conn

    async def processar_turno(atendimento_id: uuid.UUID) -> None:
        chamadas.turnos.append(atendimento_id)

    async def iniciar_atendimento(atendimento_id: uuid.UUID) -> None:
        chamadas.iniciados.append(atendimento_id)

    async def ler_para_lembrete(atendimento_id: uuid.UUID):
        return chamadas.instantaneos.get(atendimento_id)

    async def enviar_lembrete(atendimento_id: uuid.UUID, n: int, janela_24h: bool) -> None:
        chamadas.lembretes.append((atendimento_id, n, janela_24h))

    async def encerrar_sem_lembrete(atendimento_id: uuid.UUID, motivo: str) -> None:
        chamadas.encerrados_sem_lembrete.append((atendimento_id, motivo))

    async def expirar_parados() -> int:
        chamadas.expirados += 1
        return 0

    async def tratar_lease(lease) -> None:
        chamadas.leases.append(lease)

    async def auditar_pii(ids) -> int:
        chamadas.auditados.append(tuple(ids))
        return len(ids)

    base = {
        "relogio": relogio,
        "abrir_conexao": abrir_conexao,
        "leitor_config": LeitorConfig(relogio),
        "processar_turno": processar_turno,
        "iniciar_atendimento": iniciar_atendimento,
        "ler_para_lembrete": ler_para_lembrete,
        "enviar_lembrete": enviar_lembrete,
        "encerrar_sem_lembrete": encerrar_sem_lembrete,
        "expirar_parados": expirar_parados,
        "tratar_lease_vencido": tratar_lease,
        "auditar_pii": auditar_pii,
    }
    return Servicos(**{**base, **troca})


async def esperar(condicao, limite_s: float = 10.0, passo_s: float = 0.02) -> None:
    """Espera a CONDIÇÃO (não um sinal nem um tempo fixo); estourar o limite é falha do teste."""
    import asyncio
    import time

    prazo = time.monotonic() + limite_s
    while not condicao():
        if time.monotonic() > prazo:
            raise AssertionError("condição não ocorreu no prazo")
        await asyncio.sleep(passo_s)


def tornar_vencidos(conn: psycopg.Connection) -> None:
    """Vence a espera curta da rajada (3 s), mas NÃO os jobs agendados para longe (lembrete de horas): o worker compara `scheduled_at` com o
    `now()` do banco, que o teste não controla, e vencer tudo escondia o bloqueio de turno atrás de lembrete futuro (revisão A1)."""
    conn.execute(
        "UPDATE procrastinate.procrastinate_jobs SET scheduled_at = now() - interval '1 second' "
        "WHERE status = 'todo' AND scheduled_at < now() + interval '1 minute'"
    )


def jobs_por_status(conn: psycopg.Connection, tarefa: str | None = None) -> list[tuple[str, str, str | None, str | None]]:
    filtro, params = ("WHERE task_name = %s", (tarefa,)) if tarefa else ("", ())
    consulta = f"SELECT task_name, status::text, lock, queueing_lock FROM procrastinate.procrastinate_jobs {filtro} ORDER BY id"
    return [tuple(r) for r in conn.execute(consulta, params)]
