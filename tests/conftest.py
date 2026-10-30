"""Fixtures: Postgres 18 descartável, papéis como a infra do estudo E e banco-modelo com 0001+0002 aplicadas."""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from tests.banco import (
    Banco,
    Servidor,
    apagar_banco,
    criar_banco,
    criar_papeis,
    novo_nome,
    servidor_do_ambiente,
    subir_docker,
)

RAIZ = Path(__file__).resolve().parent.parent
MIGRACOES = RAIZ / "migrations"
IMAGEM = os.environ.get("IA_TESTE_PG_IMAGEM", "postgres:18")
ESTUDO_I = Path(os.environ.get("ESTUDO_I_PATH", "/opt/claude/docs/planejamento-ia/estudos/semana-1/i-esquema-reconciliado.md"))


@pytest.fixture(scope="session")
def servidor() -> Iterator[Servidor]:
    """`IA_TESTE_PG_HOST`/`IA_TESTE_PG_PORT` apontam para um serviço local descartável (CI); sem eles sobe `postgres:18` no docker."""
    host = os.environ.get("IA_TESTE_PG_HOST")
    if host:
        yield servidor_do_ambiente(host, int(os.environ.get("IA_TESTE_PG_PORT", "5432")))
        return
    srv, derrubar = subir_docker(IMAGEM)
    try:
        yield srv
    finally:
        derrubar()


@pytest.fixture(scope="session")
def papeis(servidor: Servidor) -> None:
    criar_papeis(servidor)


@pytest.fixture(scope="session")
def modelo(servidor: Servidor, papeis: None) -> Iterator[str]:
    """Banco-modelo (template) com todas as migrações aplicadas pelo mesmo `aplicar()` do uso real."""
    from ia_atendimento.migracoes import aplicar

    nome = novo_nome("ia_modelo")
    criar_banco(servidor, nome)
    with servidor.conectar(nome, autocommit=False) as conn:
        aplicar(conn, MIGRACOES)
    yield nome
    apagar_banco(servidor, nome)


@pytest.fixture
def banco(servidor: Servidor, modelo: str) -> Iterator[Banco]:
    """Cópia nova do modelo (CREATE DATABASE ... TEMPLATE), para testes que mudam estado."""
    nome = novo_nome("ia_teste")
    criar_banco(servidor, nome, modelo=modelo)
    try:
        yield Banco(servidor, nome)
    finally:
        apagar_banco(servidor, nome)


@pytest.fixture
def so_0001(tmp_path: Path) -> Path:
    """Diretório com apenas a 0001 (a sequência de 322 casos do estudo I prova a 0001 sozinha)."""
    destino = tmp_path / "so0001"
    destino.mkdir()
    shutil.copy(MIGRACOES / "0001_esquema.up.sql", destino / "0001_esquema.up.sql")
    return destino


@pytest.fixture
def db_conn(banco: Banco) -> Iterator[psycopg.Connection]:
    """Conexão do runtime (`ia_app_a`, sem DDL nem DELETE) num banco novo com 0001+0002+0003; autocommit, como as transições esperam."""
    with banco.sessao("ia_app_a") as conn:
        yield conn


@pytest.fixture
def relogio():
    from tests.estado_apoio import RelogioFalso

    return RelogioFalso()


@pytest.fixture
def versoes(db_conn: psycopg.Connection):
    """Artefatos semeados (roteiro 3, regras 2, catálogo 1, motor 4); devolve o que `versoes_vigentes` deve ler."""
    from ia_atendimento.estado import Versoes
    from tests.estado_apoio import semear_versoes

    semear_versoes(db_conn, roteiro=3, regras=2, catalogo=1, motor=4)
    return Versoes(roteiro=3, regras=2, catalogo=1, motor=4)


@pytest.fixture
def versoes_semeadas_no_banco(banco: Banco):
    """Como `versoes`, para testes que abrem as próprias conexões (corridas entre threads)."""
    from ia_atendimento.estado import Versoes
    from tests.estado_apoio import semear_versoes

    with banco.sessao("ia_app_a") as conn:
        semear_versoes(conn, roteiro=3, regras=2, catalogo=1, motor=4)
    return Versoes(roteiro=3, regras=2, catalogo=1, motor=4)
