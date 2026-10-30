"""Fixtures e ajudantes da B1.3 (chave, fila, prontidão): conexão como `ia_app_a`, relógio falso e linhas de `ia.atendimento` por SQL.

Ficam fora do `conftest.py` de propósito (a B1.1 mexe nele em paralelo): cada módulo de teste importa o que usa.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest
from psycopg.types.json import Jsonb

from ia_atendimento.relogio import RelogioFalso
from tests.banco import SENHA_LOGIN, Banco

# terça-feira 17/11/2026 12:00 em São Paulo: dentro da janela, sem feriado, sem DATAPREV
INSTANTE_UTIL = datetime(2026, 11, 17, 15, 0, tzinfo=UTC)
LOGIN_APP = "ia_app_a"


@pytest.fixture
def relogio() -> RelogioFalso:
    return RelogioFalso(INSTANTE_UTIL)


def conninfo(banco: Banco, usuario: str = LOGIN_APP) -> str:
    s = banco.servidor
    return f"host={s.host} port={s.port} dbname={banco.nome} user={usuario} password={SENHA_LOGIN}"


@pytest.fixture
def conninfo_app(banco: Banco) -> str:
    return conninfo(banco)


@pytest.fixture
def conn_app(banco: Banco) -> Iterator[psycopg.Connection]:
    """Conexão como o runtime (`ia_app_a`): o que o código de produção pode, o teste pode; nada além."""
    with banco.conectar(LOGIN_APP) as conn:
        yield conn


@pytest.fixture
def conn_super(banco: Banco) -> Iterator[psycopg.Connection]:
    """Superusuário só para montar cenário (linhas que o runtime não insere) e para o teste olhar o estado."""
    with banco.conectar() as conn:
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


def inserir_opt_out(conn: psycopg.Connection, pessoa_id: uuid.UUID, tipo: str = "opt_out") -> None:
    chave = f"t14:{pessoa_id}:{tipo}:{uuid.uuid4().hex[:8]}"
    conn.execute(
        "INSERT INTO ia.opt_out (pessoa_id, tipo, origem, chave_logica, idem_key, registrado_por) VALUES (%s, %s, 'operador', %s, %s, 'teste')",
        (pessoa_id, tipo, chave, hashlib.sha256(chave.encode()).hexdigest()),
    )


def estados_dos_atendimentos(conn: psycopg.Connection) -> dict[uuid.UUID, tuple[str, int]]:
    return {r[0]: (r[1], r[2]) for r in conn.execute("SELECT atendimento_id, estado, versao FROM ia.atendimento")}
