"""Apoio dos testes do ciclo de vida: relógio falso, entrada sintética e semente de `artefato_versao`. Tudo sintético, sem PII."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg

from ia_atendimento.estado import EntradaAtendimento

CHAT = "0123456789abcdef01234567"
OUTRO_CHAT = "fedcba9876543210fedcba98"
PHONE = "89abcdef0123456789abcdef"
PESSOA = "11111111-1111-7111-8111-111111111111"
OUTRA_PESSOA = "22222222-2222-7222-8222-222222222222"
CLT_JOB = "5a1f0c3e-7b2d-4e9a-8c61-0d2f9b3a4e55"
CHAVE = "venda:57460eeceae26a872a0bef6a72cdf8df"
OPERADOR = "operador.teste@exemplo.invalid"
INICIO = datetime(2026, 11, 24, 13, 0, tzinfo=UTC)


class RelogioFalso:
    """`Relogio` injetável: o tempo de negócio nunca vem do `now()` do banco."""

    def __init__(self, agora: datetime = INICIO) -> None:
        self.agora = agora

    def __call__(self) -> datetime:
        return self.agora

    def avancar(self, **delta: float) -> None:
        self.agora += timedelta(**delta)


def corpo_da_entrada(**mudar: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "chave_logica": CHAVE,
        "gatilho": "venda",
        "pessoa_id": PESSOA,
        "chat_id": CHAT,
        "phone_id": PHONE,
        "disparado_por": OPERADOR,
        "clt_job_id": CLT_JOB,
        "sessao_id": "22222222-2222-7222-8222-222222222222",
        "motivo_escolha": "mais_antigo_elegivel",
        "criterio_versao": "c1.0",
        "perfil": {"banco": "FACTA", "faixa_parcela": "200_300", "idade_min": 42},
        "perfil_versao": 1,
    }
    return {**base, **mudar}


def entrada(**mudar: Any) -> EntradaAtendimento:
    return EntradaAtendimento(**corpo_da_entrada(**mudar))


def semear_versoes(conn: psycopg.Connection, **numeros: int) -> None:
    """Insere versões de artefato (por padrão a 1 de cada tipo); `roteiro=3` insere 1..3 (vigente = o maior)."""
    for tipo in ("roteiro", "regras", "catalogo", "motor"):
        for numero in range(1, numeros.get(tipo, 1) + 1):
            conn.execute(
                "INSERT INTO ia.artefato_versao (tipo, numero, descricao, aprovado_por) VALUES (%s, %s, 'teste', 'dono.teste@exemplo.invalid')",
                (tipo, numero),
            )
