"""Apoio dos testes da B1.2 (linha do tempo, conversa cifrada, cofre): chaveiro descartável, atendimento sintético e relógio fixo.

Tudo sintético: CPF `000.000.0nn`, chat de 24 hex fictício, nada de cliente real. Carregado por `pytest_plugins` nos três módulos
de teste (o `conftest.py` é da B1.1 e não é tocado aqui).
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest

from ia_atendimento.cifra import Chaveiro
from tests.banco import Banco

AGORA = datetime(2026, 11, 24, 13, 0, tzinfo=UTC)  # chave_id 2 = nov/2026
CHAT = "0123456789abcdef01234567"
OUTRO_CHAT = "fedcba9876543210fedcba98"
PHONE = "89abcdef0123456789abcdef"
PESSOA = "11111111-1111-7111-8111-111111111111"
CPF_SINTETICO = "000.000.012-34"  # formatado: a máscara o pega pela forma, com ou sem DV
MARCADOR = "zebra-quantica-parcela"  # texto marcador que NUNCA pode aparecer em claro no banco


def _b64() -> str:
    return base64.b64encode(os.urandom(32)).decode()


@pytest.fixture
def chaveiro(tmp_path: Path) -> Chaveiro:
    """Chaves 1 (out/2026) e 2 (nov/2026); a vigente é a 2."""
    arquivo = tmp_path / "chaves.json"
    arquivo.write_text(json.dumps({"1": _b64(), "2": _b64()}), encoding="utf-8")
    arquivo.chmod(0o600)
    return Chaveiro.de_arquivo(arquivo, vigente=2)


@pytest.fixture
def conn_app(banco: Banco) -> Iterator[psycopg.Connection]:
    """Conexão do runtime (`ia_app_a`: sem DDL nem DELETE), autocommit, num banco novo com 0001+0002."""
    with banco.sessao("ia_app_a") as conn:
        yield conn


def novo_atendimento(conn: psycopg.Connection, *, chat: str = CHAT, modo: str = "duble") -> uuid.UUID:
    """Insere um atendimento mínimo válido (como o `abrir` da B1.1 faria) e devolve o id. Sem PII."""
    chave = f"venda:{uuid.uuid4().hex}"
    linha = conn.execute(
        "INSERT INTO ia.atendimento (origem, chave_logica, idempotency_key, entrada_fingerprint, gatilho, disparado_por, pessoa_id, chat_id,"
        " phone_id, roteiro_versao, regras_versao, catalogo_versao, motor_versao, modo, criterio_versao, faixa_esforco)"
        " VALUES ('n8n_braco', %s, encode(sha256(convert_to(%s,'UTF8')),'hex'), %s, 'venda', 'operador@exemplo.invalid', %s, %s, %s,"
        " 1, 1, 1, 1, %s, 'crit_v1', 'media') RETURNING atendimento_id",
        (chave, chave, "a" * 64, PESSOA, chat, PHONE, modo),
    ).fetchone()
    assert linha is not None
    return linha[0]


def chaveiro_com(tmp_path: Path, chaves: dict[int, str], vigente: int, nome: str = "chaves_extra.json") -> Chaveiro:
    """Chaveiro com chaves dadas (base64), para provar descarte e rotação mensal."""
    arquivo = tmp_path / nome
    arquivo.write_text(json.dumps({str(k): v for k, v in chaves.items()}), encoding="utf-8")
    arquivo.chmod(0o600)
    return Chaveiro.de_arquivo(arquivo, vigente=vigente)


def chave_aleatoria() -> str:
    return _b64()
