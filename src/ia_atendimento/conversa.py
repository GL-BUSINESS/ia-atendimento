"""Conversa cifrada (B1.2, sp01 T4): o texto do cliente e da IA, MASCARADO e cifrado na aplicação (AES-256-GCM), e a janela de 24 h.

- `gravar_troca` mascara ANTES de cifrar (`mascara.mascarar`: CPF com DV, telefone, e-mail, CEP, UUID, 8+ dígitos e os nomes da
  conversa), trunca em 4000 caracteres e cifra com `cifra.Chaveiro` (AAD `atendimento_id|seq|remetente|tipo|chave_id`, nonce
  aleatório de 12 bytes por linha). O banco só vê `nonce` e `cifra`; `mascarado` é sempre `true` (CHECK).
- `chave_id` é mensal: 1 = out/2026, 2 = nov/2026… (`chave_id_do_mes`); quem escolhe a vigente é `CHAVE_AES_ID` (docs/OPERACAO.md §2).
  Descartar a entrada de um mês deixa as linhas dele ilegíveis: `ler_trocas` as omite e conta (`omitidas`), o turno segue.
- `ler_trocas`: resumo vigente (o de maior `seq`) + as últimas N trocas (2N mensagens, cada uma cortada em 280 caracteres).
  AAD, nonce ou texto adulterados (linha copiada para outro atendimento/seq/remetente) levantam `FalhaAoDecifrar`: não são omitidos.
- `gravar_resumo` rejeita resumo com dígito, nome ou PII e com mais de 60 palavras (H §3.5); quem chama repete 1× e, falhando, o
  anterior continua valendo (nada é gravado na rejeição).
- `texto_livre_permitido`: texto livre só com `agora − ultimo_cliente_em < 24 h` (janela de serviço do WhatsApp; 95 % dos envios
  livres fora dela falham, levantamento 09 §4.5). Sem `ultimo_cliente_em` não há texto livre (só template).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final

import psycopg

from ia_atendimento.cifra import REMETENTES, ChaveDesconhecida, Chaveiro
from ia_atendimento.linha_tempo import travar_atendimento
from ia_atendimento.mascara import mascarar

LIMITE_TROCA: Final = 4000
LIMITE_LEITURA: Final = 280
TROCAS_PADRAO: Final = 3
RETENCAO_LINHA: Final = timedelta(days=30)  # teto absoluto da linha (CHECK `apagar_em <= criada_em + 30 d`)
JANELA_SERVICO: Final = timedelta(hours=24)
MAX_PALAVRAS_RESUMO: Final = 60
PRIMEIRO_MES: Final = (2026, 10)  # chave_id 1
SUBSTITUTO: Final = re.compile(r"^\[dado:[a-z0-9_]{1,20}\]$")


class ConversaErro(Exception):
    """Base. As mensagens nunca citam o texto."""


class TextoVazio(ConversaErro):
    pass


class ResumoInvalido(ConversaErro):
    """Resumo com dígito, nome, PII, longo demais ou cobrindo o que não existe. O anterior continua valendo."""


@dataclass(frozen=True)
class Troca:
    seq: int
    remetente: str
    texto: str
    mensagem_em: datetime | None


@dataclass(frozen=True)
class Conversa:
    resumo: str | None
    mensagens: tuple[Troca, ...]
    omitidas: int  # linhas cuja chave mensal foi descartada


def chave_id_do_mes(agora: datetime) -> int:
    """`chave_id` sequencial do mês de `agora` (1 = out/2026). Não estoura o smallint: 12 por ano."""
    meses = (agora.year - PRIMEIRO_MES[0]) * 12 + agora.month - PRIMEIRO_MES[1] + 1
    if meses < 1:
        raise ValueError("data anterior a out/2026: não há chave mensal")
    return meses


def texto_livre_permitido(agora: datetime, ultimo_cliente_em: datetime | None) -> bool:
    """`True` só se o cliente falou há menos de 24 h (exatamente 24 h já é fora). `None` ⇒ `False` (fail-closed)."""
    if agora.tzinfo is None:
        raise ValueError("agora precisa de fuso")
    if ultimo_cliente_em is None:
        return False
    if ultimo_cliente_em.tzinfo is None:
        raise ValueError("ultimo_cliente_em precisa de fuso")
    return agora - ultimo_cliente_em < JANELA_SERVICO


def _texto_a_gravar(texto: str, nomes: Collection[str], substituto: str | None) -> str:
    if substituto is not None:
        if not SUBSTITUTO.fullmatch(substituto):
            raise ValueError("substituto deve ser da forma [dado:rotulo]")
        return substituto
    final = mascarar(texto, nomes).strip()[:LIMITE_TROCA]
    if not final:
        raise TextoVazio("texto vazio depois da máscara")
    return final


def _inserir(conn: psycopg.Connection, atendimento_id: uuid.UUID, **c: Any) -> None:
    conn.execute(
        "INSERT INTO ia.conversa_cifrada (atendimento_id, seq, passo_ordem, remetente, tipo, cobre_ate_seq, mensagem_em,"
        " chave_id, nonce, cifra, criada_em, apagar_em) VALUES (%(a)s, %(seq)s, %(passo)s, %(rem)s, %(tipo)s, %(cobre)s, %(em)s,"
        " %(chave)s, %(nonce)s, %(cifra)s, %(criada)s, %(apagar)s)",
        {"a": atendimento_id, **c},
    )


def _gravar(
    conn: psycopg.Connection,
    atendimento_id: uuid.UUID,
    *,
    remetente: str,
    tipo: str,
    texto: str,
    agora: datetime,
    chaveiro: Chaveiro,
    passo_ordem: int | None = None,
    cobre_ate_seq: int | None = None,
    mensagem_em: datetime | None = None,
) -> int:
    with conn.transaction():
        travar_atendimento(conn, atendimento_id)
        linha = conn.execute(
            "SELECT coalesce(max(seq), 0) + 1 FROM ia.conversa_cifrada WHERE atendimento_id = %s", (atendimento_id,)
        ).fetchone()
        seq = linha[0] if linha else 1
        if cobre_ate_seq is not None and not 1 <= cobre_ate_seq < seq:
            raise ResumoInvalido("cobre_ate_seq deve apontar para mensagem existente")
        cifrado = chaveiro.cifrar(texto, atendimento_id, seq=seq, remetente=remetente, tipo=tipo)
        _inserir(
            conn, atendimento_id, seq=seq, passo=passo_ordem, rem=remetente, tipo=tipo, cobre=cobre_ate_seq, em=mensagem_em,
            chave=cifrado.chave_id, nonce=cifrado.nonce, cifra=cifrado.ct, criada=agora, apagar=agora + RETENCAO_LINHA,
        )  # fmt: skip
    return seq


def gravar_troca(
    conn: psycopg.Connection,
    atendimento_id: uuid.UUID,
    *,
    remetente: str,
    texto: str,
    agora: datetime,
    chaveiro: Chaveiro,
    passo_ordem: int | None = None,
    mensagem_em: datetime | None = None,
    nomes: Collection[str] = (),
    substituto: str | None = None,
) -> int:
    """Mascara, cifra e grava uma mensagem; devolve o `seq`. `substituto` (`[dado:pix]`) grava só o rótulo: o valor nem é lido."""
    if remetente not in REMETENTES:
        raise ValueError(f"remetente deve ser um de {sorted(REMETENTES)}")
    final = _texto_a_gravar(texto, nomes, substituto)
    return _gravar(
        conn, atendimento_id, remetente=remetente, tipo="mensagem", texto=final, agora=agora, chaveiro=chaveiro,
        passo_ordem=passo_ordem, mensagem_em=mensagem_em,
    )  # fmt: skip


def _validar_resumo(texto: str, nomes: Collection[str]) -> str:
    limpo = texto.strip()
    if not limpo or len(limpo.split()) > MAX_PALAVRAS_RESUMO:
        raise ResumoInvalido(f"resumo vazio ou com mais de {MAX_PALAVRAS_RESUMO} palavras")
    if any(c.isdigit() or c.isnumeric() for c in limpo):
        raise ResumoInvalido("resumo com dígito")
    if mascarar(limpo, nomes) != limpo:
        raise ResumoInvalido("resumo com nome ou dado pessoal")
    return limpo


def gravar_resumo(
    conn: psycopg.Connection,
    atendimento_id: uuid.UUID,
    *,
    texto: str,
    cobre_ate_seq: int,
    agora: datetime,
    chaveiro: Chaveiro,
    nomes: Collection[str] = (),
) -> int:
    """Resumo compacto (`tipo='resumo'`, remetente `ia`, sem passo). Sem dígito, sem nome, ≤ 60 palavras; senão `ResumoInvalido`."""
    limpo = _validar_resumo(texto, nomes)
    return _gravar(
        conn, atendimento_id, remetente="ia", tipo="resumo", texto=limpo, agora=agora, chaveiro=chaveiro, cobre_ate_seq=cobre_ate_seq
    )


def _decifrar(chaveiro: Chaveiro, atendimento_id: uuid.UUID, linha: tuple[Any, ...]) -> str | None:
    seq, remetente, tipo, chave_id, nonce, cifra = linha
    try:
        return chaveiro.decifrar(chave_id, bytes(nonce), bytes(cifra), atendimento_id, seq=seq, remetente=remetente, tipo=tipo)
    except ChaveDesconhecida:
        return None  # chave do mês descartada: texto ilegível por desenho (aceito, 14 d)


def ler_trocas(conn: psycopg.Connection, atendimento_id: uuid.UUID, *, chaveiro: Chaveiro, trocas: int = TROCAS_PADRAO) -> Conversa:
    """Resumo vigente + as últimas `trocas` trocas (2 mensagens cada), em ordem. Decifra só no runtime, com a chave da própria linha."""
    colunas = "seq, remetente, tipo, chave_id, nonce, cifra"
    resumo = conn.execute(
        f"SELECT {colunas} FROM ia.conversa_cifrada WHERE atendimento_id = %s AND tipo = 'resumo' ORDER BY seq DESC LIMIT 1",  # noqa: S608
        (atendimento_id,),
    ).fetchone()
    recentes = conn.execute(
        f"SELECT {colunas}, mensagem_em FROM ia.conversa_cifrada WHERE atendimento_id = %s AND tipo = 'mensagem'"  # noqa: S608
        " ORDER BY seq DESC LIMIT %s",
        (atendimento_id, trocas * 2),
    ).fetchall()
    omitidas = 0
    texto_resumo = None
    if resumo is not None:
        texto_resumo = _decifrar(chaveiro, atendimento_id, tuple(resumo))
        omitidas += texto_resumo is None
    mensagens: list[Troca] = []
    for linha in reversed(recentes):
        texto = _decifrar(chaveiro, atendimento_id, tuple(linha[:6]))
        if texto is None:
            omitidas += 1
            continue
        mensagens.append(Troca(linha[0], linha[1], texto[:LIMITE_LEITURA], linha[6]))
    return Conversa(texto_resumo, tuple(mensagens), omitidas)
