"""Cofre (B1.2, sp01 T4): dado de curta vida do atendimento, cifrado na aplicação (mesma cifra da conversa).

- Duas finalidades: `canal` (o número do chat, necessário para enviar; é PII) e `digitacao` (dados da proposta). AAD
  `atendimento_id|0|cofre|finalidade|chave_id`: trocar a finalidade da linha quebra a tag.
- TTL de 1 segundo a 7 dias (`expira_em <= criado_em + 7 d`, CHECK). O vencido LÊ como ausente mesmo antes de ser apagado.
- O `ia_app` não tem DELETE: o apagamento físico é `ia.fn_texto_podar` (SECURITY DEFINER; relógio do banco). `expirar` a chama.
- O que entra aqui nunca entra em `passo`, em log, em span nem no prompt; `ia_leitura` e `ia_qualidade` nem enxergam a tabela.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any, Final

import psycopg

from ia_atendimento.cifra import FINALIDADES_DO_COFRE, Chaveiro

TTL_MAX: Final = timedelta(days=7)
DIAS_COFRE_ENCERRADO: Final = 1  # fn_texto_podar: cofre de atendimento encerrado há mais de 1 d também sai
DIAS_CONVERSA_PODA: Final = 14


def _serializar(dados: Mapping[str, Any]) -> str:
    if not isinstance(dados, Mapping) or not dados:
        raise ValueError("dados do cofre deve ser um objeto JSON não vazio")
    try:
        return json.dumps(dict(dados), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        raise ValueError("dados do cofre não é serializável em JSON") from None  # sem eco do conteúdo


def guardar(
    conn: psycopg.Connection,
    atendimento_id: uuid.UUID,
    finalidade: str,
    dados: Mapping[str, Any],
    *,
    agora: datetime,
    chaveiro: Chaveiro,
    ttl: timedelta = TTL_MAX,
) -> None:
    """Cifra e grava (ou substitui) o cofre da finalidade. `ttl` entre 1 µs e 7 dias."""
    if finalidade not in FINALIDADES_DO_COFRE:
        raise ValueError(f"finalidade deve ser uma de {sorted(FINALIDADES_DO_COFRE)}")
    if not timedelta(0) < ttl <= TTL_MAX:
        raise ValueError("ttl deve ser positivo e de no máximo 7 dias")
    cifrado = chaveiro.cifrar_cofre(_serializar(dados), atendimento_id, finalidade)
    conn.execute(
        "INSERT INTO ia.cofre (atendimento_id, finalidade, chave_id, nonce, cifra, criado_em, expira_em)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s)"
        " ON CONFLICT (atendimento_id, finalidade) DO UPDATE SET chave_id = EXCLUDED.chave_id, nonce = EXCLUDED.nonce,"
        " cifra = EXCLUDED.cifra, criado_em = EXCLUDED.criado_em, expira_em = EXCLUDED.expira_em",
        (atendimento_id, finalidade, cifrado.chave_id, cifrado.nonce, cifrado.ct, agora, agora + ttl),
    )


def ler(
    conn: psycopg.Connection, atendimento_id: uuid.UUID, finalidade: str, *, agora: datetime, chaveiro: Chaveiro
) -> dict[str, Any] | None:
    """Dados decifrados, ou `None` se não existe ou já venceu em `agora`. Tag inválida levanta `FalhaAoDecifrar`."""
    if finalidade not in FINALIDADES_DO_COFRE:
        raise ValueError(f"finalidade deve ser uma de {sorted(FINALIDADES_DO_COFRE)}")
    linha = conn.execute(
        "SELECT chave_id, nonce, cifra, expira_em FROM ia.cofre WHERE atendimento_id = %s AND finalidade = %s", (atendimento_id, finalidade)
    ).fetchone()
    if linha is None or linha[3] <= agora:
        return None
    chave_id, nonce, cifra, _ = linha
    texto = chaveiro.decifrar_cofre(chave_id, bytes(nonce), bytes(cifra), atendimento_id, finalidade)
    return json.loads(texto)


def expirar(conn: psycopg.Connection, agora: datetime) -> int:
    """Apaga fisicamente o cofre vencido (linhas com `expira_em <= agora`); devolve quantas linhas do cofre saíram.

    Sem DELETE para o `ia_app`, passa por `ia.fn_texto_podar`, que usa o relógio do banco e também poda a conversa vencida e o
    cofre/conversa de atendimento encerrado há mais de 1/14 dias (a mesma rotina do job `podar`). Se nada venceu em `agora`, não chama."""
    vencidas = conn.execute("SELECT count(*) FROM ia.cofre WHERE expira_em <= %s", (agora,)).fetchone()
    if vencidas is None or vencidas[0] == 0:
        return 0
    linha = conn.execute("SELECT linhas_cofre FROM ia.fn_texto_podar(%s, %s)", (DIAS_CONVERSA_PODA, DIAS_COFRE_ENCERRADO)).fetchone()
    return int(linha[0]) if linha else 0
