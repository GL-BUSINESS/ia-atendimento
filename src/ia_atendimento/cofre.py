"""Cofre (B1.2, sp01 T4): dado de curta vida do atendimento, cifrado na aplicação (mesma cifra da conversa).

- Duas finalidades: `canal` (o número do chat, necessário para enviar; é PII) e `digitacao` (dados da proposta). AAD
  `atendimento_id|0|cofre|finalidade|chave_id`: trocar a finalidade da linha quebra a tag.
- TTL de 1 µs a 7 dias, contado pelo `now()` do BANCO (um relógio do chamador errado não alonga a vida real do dado, achado M1);
  guardar de novo NÃO renova além de `criado_em + 7 d` do primeiro. O vencido LÊ como ausente mesmo antes de ser apagado.
- `agora` (opcional) só confere a chave mensal (M2): o `chave_id` vigente tem de ser o do mês.
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
from ia_atendimento.conversa import exigir_chave_do_mes

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
    chaveiro: Chaveiro,
    ttl: timedelta = TTL_MAX,
    agora: datetime | None = None,
) -> None:
    """Cifra e grava (ou substitui) o cofre da finalidade. `ttl` entre 1 µs e 7 dias."""
    if finalidade not in FINALIDADES_DO_COFRE:
        raise ValueError(f"finalidade deve ser uma de {sorted(FINALIDADES_DO_COFRE)}")
    if not timedelta(0) < ttl <= TTL_MAX:
        raise ValueError("ttl deve ser positivo e de no máximo 7 dias")
    exigir_chave_do_mes(chaveiro, agora)
    cifrado = chaveiro.cifrar_cofre(_serializar(dados), atendimento_id, finalidade)
    conn.execute(
        "INSERT INTO ia.cofre (atendimento_id, finalidade, chave_id, nonce, cifra, criado_em, expira_em)"
        " VALUES (%(a)s, %(f)s, %(k)s, %(n)s, %(c)s, now(), now() + %(ttl)s)"
        " ON CONFLICT (atendimento_id, finalidade) DO UPDATE SET chave_id = EXCLUDED.chave_id, nonce = EXCLUDED.nonce,"
        " cifra = EXCLUDED.cifra,"
        # linha ainda viva: mantém o `criado_em` e nunca passa de criado_em + 7 d; linha vencida: recomeça
        " criado_em = CASE WHEN ia.cofre.expira_em > now() THEN ia.cofre.criado_em ELSE now() END,"
        " expira_em = CASE WHEN ia.cofre.expira_em > now() THEN least(EXCLUDED.expira_em, ia.cofre.criado_em + %(max)s)"
        " ELSE EXCLUDED.expira_em END",
        {"a": atendimento_id, "f": finalidade, "k": cifrado.chave_id, "n": cifrado.nonce, "c": cifrado.ct, "ttl": ttl, "max": TTL_MAX},
    )


def ler(conn: psycopg.Connection, atendimento_id: uuid.UUID, finalidade: str, *, chaveiro: Chaveiro) -> dict[str, Any] | None:
    """Dados decifrados, ou `None` se não existe ou já venceu (pelo relógio do banco). Tag inválida levanta `FalhaAoDecifrar`."""
    if finalidade not in FINALIDADES_DO_COFRE:
        raise ValueError(f"finalidade deve ser uma de {sorted(FINALIDADES_DO_COFRE)}")
    linha = conn.execute(
        "SELECT chave_id, nonce, cifra FROM ia.cofre WHERE atendimento_id = %s AND finalidade = %s AND expira_em > now()",
        (atendimento_id, finalidade),
    ).fetchone()
    if linha is None:
        return None
    chave_id, nonce, cifra = linha
    return json.loads(chaveiro.decifrar_cofre(chave_id, bytes(nonce), bytes(cifra), atendimento_id, finalidade))


def expirar(conn: psycopg.Connection) -> int:
    """Apaga fisicamente o cofre vencido (`expira_em <= now()` do banco); devolve quantas linhas do cofre saíram.

    Sem DELETE para o `ia_app`, passa por `ia.fn_texto_podar` (SECURITY DEFINER), a mesma rotina do job `podar`: também poda a conversa
    vencida e o cofre/conversa de atendimento encerrado há mais de 1/14 dias. Um só relógio (o do banco) decide o vencimento."""
    vencidas = conn.execute("SELECT count(*) FROM ia.cofre WHERE expira_em <= now()").fetchone()
    if vencidas is None or vencidas[0] == 0:
        return 0
    linha = conn.execute("SELECT linhas_cofre FROM ia.fn_texto_podar(%s, %s)", (DIAS_CONVERSA_PODA, DIAS_COFRE_ENCERRADO)).fetchone()
    return int(linha[0]) if linha else 0
