"""Ledger dos efeitos (`ia.ferramenta_chamada`) e `executar_efeito` (B1.6a; contrato 08 §6; receita D14b da revisão 2 da B5.7b).

Ciclo de uma chamada, cada passo commitado antes do seguinte (a conexão TEM de estar em autocommit, fora de transação):
1. **Reserva:** na mesma transação, a cerca de `versao` do atendimento (CAS `versao → versao + 1`, opcional) e o `INSERT … 'reservada'
   ON CONFLICT (idem_key) DO NOTHING`. Perder a cerca (`ConflitoVersao`, `TransicaoInvalida`) não reserva nada. O ledger sozinho não basta:
   a execução superada (rodada N) e a substituta (rodada N+1) têm chaves diferentes, e só a cerca barra a velha.
2. **Reivindicação:** CAS `reservada|transitorio → enviada` (com `enviada_em` e o `modo` relido). Só quem ganha este CAS chama o destino:
   uma linha `reservada` prova que a chamada nunca começou.
3. **Chamada:** `chamar(destino)` com `destino ∈ {real, teste}`, ou `simular(modo)` em `sombra|duble` (nada sai). Timeout, exceção
   ou `CancelledError` ⇒ `indeterminado` para efeito irreversível (nunca reenvia) e `transitorio` para o resto (repete com a mesma chave).
4. **Fechamento:** CAS `enviada → ok|corrigivel|recusa|indeterminado|transitorio|nao_criada`, com `concluida_em`, `http_bucket`,
   `ref_externa`, `latencia_ms` e `custo_brl`. Sob `asyncio.shield`: a vigia e o `shutdown_graceful_timeout` cancelam qualquer `await`.

Chave já existente: terminal ⇒ devolve o gravado sem chamar; `transitorio`/`reservada` ⇒ reexecuta com a MESMA chave (passo 2);
`enviada|em_andamento` recente ⇒ em andamento em outra execução (devolve sem mexer); `enviada|em_andamento` mais velha que o timeout da
chamada + folga ⇒ a execução que a reivindicou morreu depois de talvez ter chamado: vira `indeterminado` (nunca reenvia).

**`modo_efetivo`** = o mais restritivo entre `atendimento.modo` e `config.modo` (real > teste > duble > sombra; menor vence), relido a cada
efeito (o `LeitorConfig` guarda ≤ 5 s); o ledger grava o `modo` com que o efeito correu. **Posse real** = o `assumir` do atendimento fechou
`ok` com modo `real|teste` (predicado do ledger, sem coluna). **Devolução** (T12, `ia-repasse`, nota do repasse, `Canal.restaurar`): com
posse real corre REAL no modo do atendimento mesmo sob parada dura (exceção 1 do §6); sem posse real é simulada por inteiro.
T7 (e T4, fora do MVP) sem confirmação `aceita` do mesmo atendimento ⇒ `ConfirmacaoAusente` antes de qualquer gravação ou chamada.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
import uuid
from collections.abc import Awaitable, Callable, Collection
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final, Literal

import psycopg
from psycopg import errors as pg_errors

from ia_atendimento.chave import LeitorConfig
from ia_atendimento.estado_erros import AtendimentoInexistente, ConflitoVersao, EstadoErro, TransicaoInvalida
from ia_atendimento.relogio import Relogio

__all__ = [
    "Cerca",
    "ConfirmacaoAusente",
    "Desfecho",
    "EfeitoOcupado",
    "Pedido",
    "ResultadoEfeito",
    "chave_t11",
    "executar_efeito",
    "modo_efetivo",
    "posse_real",
]

Modo = Literal["real", "teste", "duble", "sombra"]
ClasseEfeito = Literal["leitura", "leitura_paga", "efeito_irreversivel", "acao_interna"]
EstadoFinal = Literal["ok", "corrigivel", "recusa", "indeterminado", "transitorio", "nao_criada"]
HttpBucket = Literal["2xx", "3xx", "4xx", "5xx", "timeout", "rede"]

RESTRITIVIDADE: Final[dict[str, int]] = {"sombra": 0, "duble": 1, "teste": 2, "real": 3}
DESTINOS_REAIS: Final = frozenset({"real", "teste"})
TERMINAIS: Final = frozenset({"ok", "corrigivel", "recusa", "indeterminado", "nao_criada"})
REEXECUTAVEIS: Final = frozenset({"reservada", "transitorio"})
EM_VOO: Final = frozenset({"enviada", "em_andamento"})
FERRAMENTA_ASSUMIR: Final = "assumir"
COM_CONFIRMACAO: Final = frozenset({"t4", "t7"})
ESTADOS_DA_CONVERSA: Final = frozenset({"aberto", "aguardando_cliente"})
TIMEOUT_PADRAO_S: Final = 10.0
FOLGA_EM_VOO: Final = timedelta(seconds=30)  # além do timeout da chamada: quem reivindicou e não fechou nesse prazo morreu
_FERRAMENTA: Final = re.compile(r"^[a-z][a-z0-9_]{1,19}$")
_CHAVE: Final = re.compile(r"^[a-z][a-z0-9_]{1,19}:[A-Za-z0-9_.:-]{1,180}$")


class ConfirmacaoAusente(EstadoErro):
    """T7/T4 sem confirmação `aceita` deste atendimento: barrado ANTES do banco (nada gravado, nada chamado)."""


class EfeitoOcupado(EstadoErro):
    """O banco recusou a reserva por unicidade que não é a da chave (T7 viva da mesma pessoa e banco, tentativa repetida): nada chamado."""

    def __init__(self, restricao: str | None) -> None:
        super().__init__(f"reserva recusada pela restrição {restricao or '?'}")
        self.restricao = restricao


def modo_efetivo(do_atendimento: str, global_: str) -> Modo:
    """O mais restritivo entre o modo do atendimento e o global (real > teste > duble > sombra: o menor vence)."""
    if do_atendimento not in RESTRITIVIDADE or global_ not in RESTRITIVIDADE:
        raise ValueError("modo fora de real|teste|duble|sombra")
    return min(do_atendimento, global_, key=RESTRITIVIDADE.__getitem__)  # type: ignore[return-value]


def chave_t11(atendimento_id: uuid.UUID | str, rodada: int, seq: int) -> str:
    """`t11:{atd}:{rodada}:{seq}`: `rodada` é a do CAS do `consumir` (ou a lida no claim da volta), `seq` o ordinal da mensagem.
    Determinística: nunca hora nem `job_id` (o retry do mesmo turno acha a mesma chave)."""
    if rodada < 0 or seq < 1:
        raise ValueError("rodada >= 0 e seq >= 1")
    return f"t11:{atendimento_id}:{rodada}:{seq}"


def posse_real(conn: psycopg.Connection, atendimento_id: uuid.UUID) -> bool:
    """O `assumir` deste atendimento fechou `ok` em `real|teste` (o orquestrador tomou o chat de verdade). Não volta atrás."""
    linha = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM ia.ferramenta_chamada WHERE atendimento_id = %s AND ferramenta = %s AND estado = 'ok'"
        " AND modo IN ('real', 'teste'))",
        (atendimento_id, FERRAMENTA_ASSUMIR),
    ).fetchone()
    return bool(linha[0])


@dataclass(frozen=True)
class Pedido:
    """O efeito a executar. `devolucao=True` marca T12/`ia-repasse`/nota do repasse/`restaurar` (exceção 1 do contrato 08 §6)."""

    ferramenta: str
    ferramenta_versao: str
    classe_efeito: ClasseEfeito
    chave_logica: str
    banco: str | None = None
    confirmacao_id: uuid.UUID | None = None
    args_hash: str | None = None
    resolve_id: int | None = None
    tentativa_n: int = 1
    devolucao: bool = False

    def __post_init__(self) -> None:
        if not _FERRAMENTA.fullmatch(self.ferramenta) or not _CHAVE.fullmatch(self.chave_logica):
            raise ValueError("ferramenta ou chave_logica fora da forma do ledger")
        if self.chave_logica.split(":", 1)[0] != self.ferramenta:
            raise ValueError("a chave_logica começa pelo nome da ferramenta")

    @property
    def idem_key(self) -> str:
        return hashlib.sha256(self.chave_logica.encode()).hexdigest()


@dataclass(frozen=True)
class Cerca:
    """CAS da `versao` do atendimento na transação da reserva. `estados`: onde o efeito ainda vale (a conversa, por padrão)."""

    versao: int
    estados: Collection[str] = field(default=ESTADOS_DA_CONVERSA)


@dataclass(frozen=True)
class Desfecho:
    """O que o destino respondeu, já classificado por quem conhece o protocolo (Canal, gateway)."""

    estado: EstadoFinal = "ok"
    http_bucket: HttpBucket | None = None
    ref_externa: str | None = None
    custo_brl: Decimal | None = None


@dataclass(frozen=True)
class ResultadoEfeito:
    chamada_id: int
    estado: str
    modo: str
    executou: bool  # ESTA execução chamou o destino real (`real|teste`)
    repetido: bool  # a chave já existia no ledger
    versao: int | None = None  # a versão do atendimento depois da cerca (None sem cerca ou na repetição)
    http_bucket: str | None = None
    ref_externa: str | None = None
    latencia_ms: int | None = None
    custo_brl: Decimal | None = None

    @property
    def simulado(self) -> bool:
        return self.modo != "real"


Chamada = Callable[[str], Awaitable[Desfecho]]


@dataclass(frozen=True)
class _Linha:
    chamada_id: int
    estado: str
    modo: str
    enviada_em: datetime | None
    http_bucket: str | None
    ref_externa: str | None
    latencia_ms: int | None
    custo_brl: Decimal | None


_SQL_INSERIR: Final = """
INSERT INTO ia.ferramenta_chamada (atendimento_id, pessoa_id, ferramenta, ferramenta_versao, classe_efeito, chave_logica, idem_key,
  tentativa_n, banco, confirmacao_id, args_hash, resolve_id, modo, reservada_em)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (idem_key) DO NOTHING
RETURNING chamada_id, estado, modo, enviada_em, http_bucket, ref_externa, latencia_ms, custo_brl
"""
_SQL_LER: Final = """
SELECT chamada_id, estado, modo, enviada_em, http_bucket, ref_externa, latencia_ms, custo_brl FROM ia.ferramenta_chamada WHERE idem_key = %s
"""
_SQL_REIVINDICAR: Final = """
UPDATE ia.ferramenta_chamada SET estado = 'enviada', enviada_em = %s, concluida_em = NULL, http_bucket = NULL, ref_externa = NULL,
  latencia_ms = NULL, custo_brl = NULL, modo = %s
WHERE chamada_id = %s AND estado = ANY(%s)
RETURNING chamada_id, estado, modo, enviada_em, http_bucket, ref_externa, latencia_ms, custo_brl
"""
_SQL_FECHAR: Final = """
UPDATE ia.ferramenta_chamada SET estado = %s, concluida_em = %s, http_bucket = %s, ref_externa = %s, latencia_ms = %s, custo_brl = %s
WHERE chamada_id = %s AND estado = ANY(%s)
RETURNING chamada_id, estado, modo, enviada_em, http_bucket, ref_externa, latencia_ms, custo_brl
"""


class _JaExiste(Exception):
    """Interno: a chave já estava no ledger; desfaz a cerca da transação da reserva."""


# --- reserva (passo 1) ----------------------------------------------------------------------------------------------------------------


def _cercar(conn: psycopg.Connection, atd: uuid.UUID, cerca: Cerca | None, agora: datetime) -> tuple[str, uuid.UUID, int | None]:
    """Devolve (modo do atendimento, pessoa_id, versão nova ou None). Sem cerca, só recusa atendimento encerrado."""
    if cerca is None:
        linha = conn.execute("SELECT modo, pessoa_id, estado FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()
        if linha is None:
            raise AtendimentoInexistente("atendimento inexistente")
        if linha[2] == "encerrado":
            raise TransicaoInvalida("efeito em atendimento encerrado")
        return linha[0], linha[1], None
    linha = conn.execute(
        "UPDATE ia.atendimento SET versao = versao + 1, atualizado_em = %s WHERE atendimento_id = %s AND versao = %s AND estado = ANY(%s)"
        " RETURNING modo, pessoa_id, versao",
        (agora, atd, cerca.versao, list(cerca.estados)),
    ).fetchone()
    if linha is not None:
        return linha[0], linha[1], linha[2]
    atual = conn.execute("SELECT versao, estado FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()
    if atual is None:
        raise AtendimentoInexistente("atendimento inexistente")
    if atual[0] != cerca.versao:
        raise ConflitoVersao("a versão do atendimento mudou: a execução foi superada e não envia")
    raise TransicaoInvalida(f"efeito fora dos estados da cerca (estado {atual[1]})")


def _exigir_confirmacao(conn: psycopg.Connection, atd: uuid.UUID, pedido: Pedido) -> None:
    if pedido.ferramenta not in COM_CONFIRMACAO:
        return
    if pedido.confirmacao_id is None:
        raise ConfirmacaoAusente(f"{pedido.ferramenta} sem confirmação")
    linha = conn.execute(
        "SELECT estado FROM ia.confirmacao WHERE atendimento_id = %s AND confirmacao_id = %s", (atd, pedido.confirmacao_id)
    ).fetchone()
    if linha is None or linha[0] != "aceita":
        raise ConfirmacaoAusente(f"{pedido.ferramenta} sem confirmação aceita deste atendimento")


def _modo_do_efeito(conn: psycopg.Connection, atd: uuid.UUID, do_atendimento: str, pedido: Pedido, leitor: LeitorConfig) -> str:
    if pedido.devolucao and do_atendimento in DESTINOS_REAIS and posse_real(conn, atd):
        return do_atendimento  # exceção 1: devolve de verdade quem tomou o chat de verdade
    return modo_efetivo(do_atendimento, str(leitor.valor(conn, "modo")))


def _inserir(conn: psycopg.Connection, atd: uuid.UUID, pessoa: uuid.UUID, pedido: Pedido, modo: str, agora: datetime) -> _Linha | None:
    try:
        linha = conn.execute(
            _SQL_INSERIR,
            (
                atd, pessoa, pedido.ferramenta, pedido.ferramenta_versao, pedido.classe_efeito, pedido.chave_logica, pedido.idem_key,
                pedido.tentativa_n, pedido.banco, pedido.confirmacao_id, pedido.args_hash, pedido.resolve_id, modo, agora,
            ),
        ).fetchone()  # fmt: skip
    except pg_errors.UniqueViolation as erro:
        raise EfeitoOcupado(erro.diag.constraint_name) from None
    return _Linha(*linha) if linha is not None else None


def _reservar(
    conn: psycopg.Connection, atd: uuid.UUID, pedido: Pedido, cerca: Cerca | None, leitor: LeitorConfig, agora: datetime
) -> tuple[_Linha | None, int | None]:
    """Passo 1. Devolve (linha nova, versão nova) ou (None, None) se a chave já existia (a cerca é desfeita junto)."""
    try:
        with conn.transaction():
            do_atendimento, pessoa, versao = _cercar(conn, atd, cerca, agora)
            _exigir_confirmacao(conn, atd, pedido)
            linha = _inserir(conn, atd, pessoa, pedido, _modo_do_efeito(conn, atd, do_atendimento, pedido, leitor), agora)
            if linha is None:
                raise _JaExiste
            return linha, versao
    except _JaExiste:
        return None, None


# --- reivindicação, fechamento e leitura (passos 2 e 4) --------------------------------------------------------------------------------


def _ler(conn: psycopg.Connection, pedido: Pedido) -> _Linha:
    linha = conn.execute(_SQL_LER, (pedido.idem_key,)).fetchone()
    if linha is None:
        raise EstadoErro("linha do ledger sumiu")
    return _Linha(*linha)


def _reivindicar(
    conn: psycopg.Connection, atd: uuid.UUID, pedido: Pedido, chamada_id: int, leitor: LeitorConfig, agora: datetime
) -> _Linha | None:
    """Passo 2: CAS `reservada|transitorio → enviada`, com o `modo` relido. None = outra execução reivindicou antes."""
    with conn.transaction():
        do_atendimento = conn.execute("SELECT modo FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()[0]
        modo = _modo_do_efeito(conn, atd, do_atendimento, pedido, leitor)
        linha = conn.execute(_SQL_REIVINDICAR, (agora, modo, chamada_id, list(REEXECUTAVEIS))).fetchone()
    return _Linha(*linha) if linha is not None else None


def _fechar(conn: psycopg.Connection, chamada_id: int, desfecho: Desfecho, latencia_ms: int, agora: datetime) -> _Linha | None:
    """Passo 4: CAS `enviada|em_andamento → final`. None = alguém já fechou (o retry a deu como indeterminada): vale o gravado."""
    linha = conn.execute(
        _SQL_FECHAR,
        (desfecho.estado, agora, desfecho.http_bucket, desfecho.ref_externa, latencia_ms, desfecho.custo_brl, chamada_id, list(EM_VOO)),
    ).fetchone()
    return _Linha(*linha) if linha is not None else None


def _dar_como_indeterminada(conn: psycopg.Connection, chamada_id: int, agora: datetime) -> _Linha | None:
    return _fechar(conn, chamada_id, Desfecho("indeterminado"), 0, agora)


def _resultado(linha: _Linha, *, executou: bool, repetido: bool, versao: int | None = None) -> ResultadoEfeito:
    return ResultadoEfeito(
        chamada_id=linha.chamada_id, estado=linha.estado, modo=linha.modo, executou=executou, repetido=repetido, versao=versao,
        http_bucket=linha.http_bucket, ref_externa=linha.ref_externa, latencia_ms=linha.latencia_ms, custo_brl=linha.custo_brl,
    )  # fmt: skip


# --- chamada (passo 3) ----------------------------------------------------------------------------------------------------------------


def _desfecho_da_falha(pedido: Pedido, bucket: HttpBucket) -> Desfecho:
    """Sem resposta (timeout, rede, exceção, corte): efeito irreversível pode ter acontecido ⇒ `indeterminado`; o resto repete."""
    return Desfecho("indeterminado" if pedido.classe_efeito == "efeito_irreversivel" else "transitorio", http_bucket=bucket)


async def _chamar(pedido: Pedido, modo: str, chamar: Chamada, simular: Chamada | None, timeout_s: float) -> Desfecho:
    if modo not in DESTINOS_REAIS:
        return await simular(modo) if simular is not None else Desfecho("ok")
    try:
        return await asyncio.wait_for(chamar(modo), timeout_s)
    except TimeoutError:
        return _desfecho_da_falha(pedido, "timeout")
    except Exception:  # erro do cliente/protocolo: não se sabe se saiu
        return _desfecho_da_falha(pedido, "rede")


async def _chamar_e_fechar(
    conn: psycopg.Connection, pedido: Pedido, linha: _Linha, *, chamar: Chamada, simular: Chamada | None, relogio: Relogio, timeout_s: float
) -> _Linha:
    inicio = time.monotonic()
    tarefa = asyncio.ensure_future(_chamar(pedido, linha.modo, chamar, simular, timeout_s))
    try:
        desfecho = await asyncio.shield(tarefa)
    except asyncio.CancelledError:
        tarefa.cancel()  # a chamada fica sem dono; o que vale é o ledger: corte no meio do envio = indeterminado
        corte = _desfecho_da_falha(pedido, "rede")
        await asyncio.shield(asyncio.to_thread(_fechar, conn, linha.chamada_id, corte, _ms(inicio), relogio.agora()))
        raise
    fechada = await asyncio.shield(asyncio.to_thread(_fechar, conn, linha.chamada_id, desfecho, _ms(inicio), relogio.agora()))
    return fechada or await asyncio.to_thread(_ler, conn, pedido)


def _ms(inicio: float) -> int:
    return max(0, int((time.monotonic() - inicio) * 1000))


# --- executar_efeito -------------------------------------------------------------------------------------------------------------------


async def _repetida(
    conn: psycopg.Connection, atd: uuid.UUID, pedido: Pedido, leitor: LeitorConfig, relogio: Relogio, timeout_s: float
) -> tuple[_Linha | None, ResultadoEfeito | None]:
    """A chave já existia. Devolve (linha reivindicada para chamar, None) ou (None, resultado final sem chamar)."""
    existente = await asyncio.to_thread(_ler, conn, pedido)
    if existente.estado in REEXECUTAVEIS:
        reivindicada = await asyncio.to_thread(_reivindicar, conn, atd, pedido, existente.chamada_id, leitor, relogio.agora())
        if reivindicada is not None:
            return reivindicada, None
        existente = await asyncio.to_thread(_ler, conn, pedido)
    if existente.estado in EM_VOO and _morta(existente, relogio.agora(), timeout_s):
        existente = await asyncio.to_thread(
            _dar_como_indeterminada, conn, existente.chamada_id, relogio.agora()
        ) or await asyncio.to_thread(_ler, conn, pedido)
    return None, _resultado(existente, executou=False, repetido=True)


def _morta(linha: _Linha, agora: datetime, timeout_s: float) -> bool:
    return linha.enviada_em is None or agora - linha.enviada_em > timedelta(seconds=timeout_s) + FOLGA_EM_VOO


async def executar_efeito(
    conn: psycopg.Connection,
    atendimento_id: uuid.UUID,
    pedido: Pedido,
    *,
    chamar: Chamada,
    leitor: LeitorConfig,
    relogio: Relogio,
    cerca: Cerca | None = None,
    simular: Chamada | None = None,
    timeout_s: float = TIMEOUT_PADRAO_S,
) -> ResultadoEfeito:
    """Executa `pedido` no máximo uma vez por `chave_logica` (ver o docstring do módulo). Levanta `ConflitoVersao`/`TransicaoInvalida`
    (cerca), `ConfirmacaoAusente` e `EfeitoOcupado` antes de chamar qualquer coisa. Um `estado` não terminal no resultado
    (`enviada`) quer dizer «em andamento em outra execução»: quem chama NÃO reenvia."""
    if not conn.autocommit or conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
        raise RuntimeError(
            "executar_efeito exige conexão em autocommit e fora de transação: a reserva precisa estar commitada antes da chamada"
        )
    nova, versao = await asyncio.to_thread(_reservar, conn, atendimento_id, pedido, cerca, leitor, relogio.agora())
    if nova is not None:
        reivindicada = await asyncio.to_thread(_reivindicar, conn, atendimento_id, pedido, nova.chamada_id, leitor, relogio.agora())
        repetido = False
        if reivindicada is None:  # outra execução reivindicou a linha recém-criada (corrida da mesma chave)
            return _resultado(await asyncio.to_thread(_ler, conn, pedido), executou=False, repetido=True, versao=versao)
    else:
        reivindicada, pronto = await _repetida(conn, atendimento_id, pedido, leitor, relogio, timeout_s)
        repetido = True
        if pronto is not None:
            return pronto
    if reivindicada is None:
        raise EstadoErro("ledger sem linha reivindicada")
    fechada = await _chamar_e_fechar(conn, pedido, reivindicada, chamar=chamar, simular=simular, relogio=relogio, timeout_s=timeout_s)
    return _resultado(fechada, executou=reivindicada.modo in DESTINOS_REAIS, repetido=repetido, versao=versao)
