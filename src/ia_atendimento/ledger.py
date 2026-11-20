"""Ledger dos efeitos (`ia.ferramenta_chamada`) e `executar_efeito` (B1.6a; contrato 08 §6; receita D14b da revisão 2 da B5.7b).

Ciclo de uma chamada, cada passo commitado antes do seguinte (a conexão TEM de estar em autocommit, fora de transação):
1. **Reserva:** na mesma transação, a cerca de `versao` do atendimento (CAS `versao → versao + 1`, opcional) e o `INSERT … 'reservada'
   ON CONFLICT (idem_key) DO NOTHING`. Perder a cerca (`ConflitoVersao`, `TransicaoInvalida`) não reserva nada. O ledger sozinho não basta:
   a execução superada (rodada N) e a substituta (rodada N+1) têm chaves diferentes, e só a cerca barra a velha.
2. **Reivindicação:** numa transação, a conferência do atendimento (estado e, com cerca, a mesma `versao`, sob `FOR SHARE`), a da
   confirmação (T7) e o CAS `reservada|transitorio → enviada` (com `enviada_em` e o `modo` relido), preso ao `atendimento_id`. Só quem
   ganha este CAS chama o destino: uma linha `reservada` prova que a chamada nunca começou. Um `transitorio` que já correu em `real|teste`
   NÃO é reivindicado em modo simulado (parada dura): fica `transitorio`, sem chamar, e o modo da tentativa real não se apaga.
3. **Chamada:** `chamar(destino)` com `destino ∈ {real, teste}`, ou `simular(modo)` em `sombra|duble` (nada sai). Timeout, exceção
   ou `CancelledError` ⇒ `indeterminado` para efeito irreversível (nunca reenvia) e `transitorio` para o resto (repete com a mesma chave).
   Na simulação nada saiu: exceção ou corte ⇒ `transitorio` sempre.
4. **Fechamento:** CAS `enviada → ok|corrigivel|recusa|indeterminado|transitorio|nao_criada`, com `concluida_em`, `http_bucket`,
   `ref_externa`, `latencia_ms` e `custo_brl`. Sob `asyncio.shield`: a vigia e o `shutdown_graceful_timeout` cancelam qualquer `await`.

Chave já existente: a linha tem de ser do MESMO pedido (`atendimento_id`, `ferramenta`, `banco`, `args_hash`, `confirmacao_id`), senão
`ChaveDivergente` sem chamar; terminal ⇒ devolve o gravado sem chamar; `transitorio`/`reservada` ⇒ reexecuta com a MESMA chave (passo 2);
`enviada|em_andamento` recente ⇒ em andamento em outra execução (devolve sem mexer); `enviada|em_andamento` mais velha que o timeout da
chamada + folga ⇒ a execução que a reivindicou morreu (G-0131): efeito irreversível em `real|teste` vira `indeterminado` (nunca reenvia);
ação interna, leitura e efeito simulado voltam a `transitorio` e são reivindicados na mesma chamada (o T12 é idempotente por `repasse_id`).
Efeito irreversível exige `args_hash` (G-0454); `transitorio` dele em `real|teste` só repete com `Desfecho.nada_saiu` (G-0087).

**`modo_efetivo`** = o mais restritivo entre `atendimento.modo` e `config.modo` (real > teste > duble > sombra; menor vence), relido a cada
efeito (o `LeitorConfig` guarda ≤ 5 s); o ledger grava o `modo` com que o efeito correu. **Posse real** = o `assumir` do atendimento fechou
`ok` com modo `real|teste` (predicado do ledger, sem coluna). **Devolução** (T12, `ia-repasse`, nota do repasse, `Canal.restaurar`): com
posse real corre REAL no modo do atendimento mesmo sob parada dura (exceção 1 do §6); sem posse real é simulada por inteiro, em qualquer
`config.modo` (exceção 2: grava `sombra`, nunca chama o destino).
T7 (e T4, fora do MVP) só com confirmação `aceita` do mesmo atendimento, do tipo certo (`digitacao` para a T7), do MESMO banco, respondida
dentro do prazo, ainda não vencida no relógio da execução e nunca usada por outra chave; senão `ConfirmacaoAusente` antes de qualquer
gravação ou chamada.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
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

log = logging.getLogger(__name__)

__all__ = [
    "Cerca",
    "ChaveDivergente",
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
TIPO_DA_CONFIRMACAO: Final[dict[str, str]] = {"t7": "digitacao", "t4": "consulta"}  # T4 fora do MVP; o tipo do DDL (0001, ia.confirmacao)
DEVOLUCAO_SEM_POSSE: Final = "sombra"  # exceção 2 do 08 §6: simulada por inteiro (rascunho), nunca `real` nem `teste`
ESTADOS_DA_CONVERSA: Final = frozenset({"aberto", "aguardando_cliente"})
TIMEOUT_PADRAO_S: Final = 10.0
FOLGA_EM_VOO: Final = timedelta(seconds=30)  # além do timeout da chamada: quem reivindicou e não fechou nesse prazo morreu
_FERRAMENTA: Final = re.compile(r"^[a-z][a-z0-9_]{1,19}$")
_ARGS_HASH: Final = re.compile(r"^[0-9a-f]{64}$")
_CHAVE: Final = re.compile(r"^[a-z][a-z0-9_]{1,19}:[A-Za-z0-9_.:-]{1,180}$")


class ConfirmacaoAusente(EstadoErro):
    """T7/T4 sem confirmação `aceita` deste atendimento: barrado ANTES do banco (nada gravado, nada chamado)."""


class ChaveDivergente(EstadoErro):
    """A `chave_logica` já está no ledger para OUTRO pedido (outro atendimento, banco, argumentos ou confirmação): nada chamado."""


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
        if self.args_hash is not None and not _ARGS_HASH.fullmatch(self.args_hash):
            raise ValueError("args_hash é sha256 hex (64)")
        if self.classe_efeito == "efeito_irreversivel" and self.args_hash is None:
            # G-0454: sem o hash do conteúdo, duas mensagens diferentes com a mesma (rodada, seq) seriam «o mesmo pedido» e a 2ª sumiria
            raise ValueError("efeito irreversível exige args_hash: chave repetida com outro conteúdo vira ChaveDivergente")

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
    # o protocolo PROVA que nada chegou ao destino (recusa de conexão, 503 antes do envio): só assim o irreversível repete
    nada_saiu: bool = False


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
    atendimento_id: uuid.UUID
    ferramenta: str
    banco: str | None
    args_hash: str | None
    confirmacao_id: uuid.UUID | None

    def do_mesmo_pedido(self, atendimento_id: uuid.UUID, pedido: Pedido) -> bool:
        return (self.atendimento_id, self.ferramenta, self.banco, self.args_hash, self.confirmacao_id) == (
            atendimento_id, pedido.ferramenta, pedido.banco, pedido.args_hash, pedido.confirmacao_id,
        )  # fmt: skip


_SQL_INSERIR: Final = """
INSERT INTO ia.ferramenta_chamada (atendimento_id, pessoa_id, ferramenta, ferramenta_versao, classe_efeito, chave_logica, idem_key,
  tentativa_n, banco, confirmacao_id, args_hash, resolve_id, modo, reservada_em)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (idem_key) DO NOTHING
RETURNING chamada_id, estado, modo, enviada_em, http_bucket, ref_externa, latencia_ms, custo_brl, atendimento_id, ferramenta, banco,
  args_hash, confirmacao_id
"""
_SQL_LER: Final = """
SELECT chamada_id, estado, modo, enviada_em, http_bucket, ref_externa, latencia_ms, custo_brl, atendimento_id, ferramenta, banco, args_hash,
  confirmacao_id
FROM ia.ferramenta_chamada WHERE idem_key = %s
"""
_SQL_TRAVAR: Final = """
SELECT chamada_id, estado, modo, enviada_em, http_bucket, ref_externa, latencia_ms, custo_brl, atendimento_id, ferramenta, banco, args_hash,
  confirmacao_id
FROM ia.ferramenta_chamada WHERE chamada_id = %s AND atendimento_id = %s FOR UPDATE
"""
_SQL_REIVINDICAR: Final = """
UPDATE ia.ferramenta_chamada SET estado = 'enviada', enviada_em = %s, concluida_em = NULL, http_bucket = NULL, ref_externa = NULL,
  latencia_ms = NULL, custo_brl = NULL, modo = %s
WHERE chamada_id = %s AND atendimento_id = %s AND estado = ANY(%s)
RETURNING chamada_id, estado, modo, enviada_em, http_bucket, ref_externa, latencia_ms, custo_brl, atendimento_id, ferramenta, banco,
  args_hash, confirmacao_id
"""
_SQL_FECHAR: Final = """
UPDATE ia.ferramenta_chamada SET estado = %s, concluida_em = %s, http_bucket = %s, ref_externa = %s, latencia_ms = %s, custo_brl = %s
WHERE chamada_id = %s AND estado = ANY(%s)
RETURNING chamada_id, estado, modo, enviada_em, http_bucket, ref_externa, latencia_ms, custo_brl, atendimento_id, ferramenta, banco,
  args_hash, confirmacao_id
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


def _conferir_atendimento(conn: psycopg.Connection, atd: uuid.UUID, cerca: Cerca | None) -> str:
    """Na reivindicação: reconfere, sob `FOR SHARE` (a cerca de outra execução espera este CAS), o que a reserva conferiu. Com cerca, a
    `versao` é a esperada e o estado está entre os da cerca; sem cerca, só recusa encerrado. Devolve o modo do atendimento."""
    linha = conn.execute("SELECT modo, estado, versao FROM ia.atendimento WHERE atendimento_id = %s FOR SHARE", (atd,)).fetchone()
    if linha is None:
        raise AtendimentoInexistente("atendimento inexistente")
    modo, estado_atual, versao = linha
    if cerca is None:
        if estado_atual == "encerrado":
            raise TransicaoInvalida("efeito em atendimento encerrado")
        return modo
    if versao != cerca.versao:
        raise ConflitoVersao("a versão do atendimento mudou antes da reivindicação: a execução foi superada e não envia")
    if estado_atual not in cerca.estados:
        raise TransicaoInvalida(f"efeito fora dos estados da cerca (estado {estado_atual})")
    return modo


_SQL_CONFIRMACAO: Final = """
SELECT c.estado, c.tipo, c.banco, c.respondida_em, c.expira_em,
  EXISTS (SELECT 1 FROM ia.ferramenta_chamada f WHERE f.confirmacao_id = c.confirmacao_id AND f.idem_key <> %s AND f.estado <> ALL(%s))
FROM ia.confirmacao c WHERE c.atendimento_id = %s AND c.confirmacao_id = %s FOR SHARE OF c
"""
NAO_CONSOMEM: Final = ("corrigivel", "recusa", "nao_criada")  # desfechos em que a digitação não aconteceu: o «sim» não foi gasto


def _exigir_confirmacao(conn: psycopg.Connection, atd: uuid.UUID, pedido: Pedido, agora: datetime) -> None:
    """T7/T4: o «sim» do cliente ligado ao DADO (DDL 0001, `ia.confirmacao`): aceita, deste atendimento, do tipo da ferramenta, do mesmo
    banco, respondida no prazo, não vencida em `agora` e não gasta por outra chave. `valores_hash` × `args_hash` é da B1.6b."""
    tipo = TIPO_DA_CONFIRMACAO.get(pedido.ferramenta)
    if tipo is None:
        return
    if pedido.confirmacao_id is None:
        raise ConfirmacaoAusente(f"{pedido.ferramenta} sem confirmação")
    linha = conn.execute(_SQL_CONFIRMACAO, (pedido.idem_key, list(NAO_CONSOMEM), atd, pedido.confirmacao_id)).fetchone()
    if linha is None or linha[0] != "aceita":
        raise ConfirmacaoAusente(f"{pedido.ferramenta} sem confirmação aceita deste atendimento")
    _estado, tipo_lido, banco, respondida_em, expira_em, gasta = linha
    if tipo_lido != tipo:
        raise ConfirmacaoAusente(f"{pedido.ferramenta} com confirmação do tipo {tipo_lido}")
    if banco != pedido.banco:
        raise ConfirmacaoAusente(f"{pedido.ferramenta} com confirmação de outro banco")
    if respondida_em > expira_em:
        raise ConfirmacaoAusente(f"{pedido.ferramenta} com confirmação respondida depois do prazo")
    if agora > expira_em:
        raise ConfirmacaoAusente(f"{pedido.ferramenta} com confirmação vencida")
    if gasta:
        raise ConfirmacaoAusente(f"{pedido.ferramenta} com confirmação já usada por outra chave")


def _modo_do_efeito(conn: psycopg.Connection, atd: uuid.UUID, do_atendimento: str, pedido: Pedido, leitor: LeitorConfig) -> str:
    efetivo = modo_efetivo(do_atendimento, str(leitor.valor(conn, "modo")))
    if not pedido.devolucao:
        return efetivo
    if do_atendimento in DESTINOS_REAIS and posse_real(conn, atd):
        return do_atendimento  # exceção 1: devolve de verdade quem tomou o chat de verdade
    return efetivo if efetivo not in DESTINOS_REAIS else DEVOLUCAO_SEM_POSSE  # exceção 2: sem posse real, simulada em qualquer modo


def _existe(conn: psycopg.Connection, pedido: Pedido) -> bool:
    return conn.execute("SELECT EXISTS (SELECT 1 FROM ia.ferramenta_chamada WHERE idem_key = %s)", (pedido.idem_key,)).fetchone()[0]


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
    """Passo 1. Devolve (linha nova, versão nova) ou (None, None) se a chave já existia (a cerca é desfeita junto). A confirmação é
    conferida aqui só para a chave nova: a repetição de uma T7 já gravada devolve o gravado mesmo com o «sim» vencido, e a que vai
    chamar de novo passa pela conferência da reivindicação."""
    try:
        with conn.transaction():
            do_atendimento, pessoa, versao = _cercar(conn, atd, cerca, agora)
            if not _existe(conn, pedido):
                _exigir_confirmacao(conn, atd, pedido, agora)
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


def _rebaixaria(atual: _Linha, modo: str) -> bool:
    """Um `transitorio` que já correu em `real|teste` (pode ter tido efeito: o `assumir` sem resposta) não se reexecuta simulado: o CAS
    sobrescreveria o modo, e a posse real (e a devolução real) se perderiam junto."""
    return atual.estado == "transitorio" and atual.modo in DESTINOS_REAIS and modo not in DESTINOS_REAIS


def _reivindicar(
    conn: psycopg.Connection,
    atd: uuid.UUID,
    pedido: Pedido,
    chamada_id: int,
    cerca: Cerca | None,
    leitor: LeitorConfig,
    agora: datetime,
) -> tuple[_Linha | None, _Linha]:
    """Passo 2, numa transação com a conferência do atendimento (cerca) e da confirmação. Devolve (reivindicada, ela) para chamar ou
    (None, linha atual) sem chamar: outra execução reivindicou antes, ou o `transitorio` real que a parada dura rebaixaria."""
    with conn.transaction():
        do_atendimento = _conferir_atendimento(conn, atd, cerca)
        travada = conn.execute(_SQL_TRAVAR, (chamada_id, atd)).fetchone()
        if travada is None:
            raise ChaveDivergente("a linha do ledger não é deste atendimento")
        atual = _Linha(*travada)
        if atual.estado not in REEXECUTAVEIS:
            return None, atual
        _exigir_confirmacao(conn, atd, pedido, agora)
        modo = _modo_do_efeito(conn, atd, do_atendimento, pedido, leitor)
        if _rebaixaria(atual, modo):
            return None, atual
        linha = _Linha(*conn.execute(_SQL_REIVINDICAR, (agora, modo, chamada_id, atd, list(REEXECUTAVEIS))).fetchone())
    return linha, linha


def _fechar(conn: psycopg.Connection, chamada_id: int, desfecho: Desfecho, latencia_ms: int, agora: datetime) -> _Linha | None:
    """Passo 4: CAS `enviada|em_andamento → final`. None = alguém já fechou (o retry a deu como indeterminada): vale o gravado."""
    linha = conn.execute(
        _SQL_FECHAR,
        (desfecho.estado, agora, desfecho.http_bucket, desfecho.ref_externa, latencia_ms, desfecho.custo_brl, chamada_id, list(EM_VOO)),
    ).fetchone()
    return _Linha(*linha) if linha is not None else None


def _resultado(linha: _Linha, *, executou: bool, repetido: bool, versao: int | None = None) -> ResultadoEfeito:
    return ResultadoEfeito(
        chamada_id=linha.chamada_id, estado=linha.estado, modo=linha.modo, executou=executou, repetido=repetido, versao=versao,
        http_bucket=linha.http_bucket, ref_externa=linha.ref_externa, latencia_ms=linha.latencia_ms, custo_brl=linha.custo_brl,
    )  # fmt: skip


# --- chamada (passo 3) ----------------------------------------------------------------------------------------------------------------


def _desfecho_da_falha(pedido: Pedido, modo: str, bucket: HttpBucket) -> Desfecho:
    """Sem resposta (timeout, rede, exceção, corte): efeito irreversível pode ter acontecido ⇒ `indeterminado`; o resto repete. Na
    simulação nada saiu: repete sempre."""
    if modo not in DESTINOS_REAIS:
        return Desfecho("transitorio")
    return Desfecho("indeterminado" if pedido.classe_efeito == "efeito_irreversivel" else "transitorio", http_bucket=bucket)


async def _chamar(pedido: Pedido, modo: str, chamar: Chamada, simular: Chamada | None, timeout_s: float) -> Desfecho:
    return _sem_repeticao_em_duvida(pedido, modo, await _chamar_cru(pedido, modo, chamar, simular, timeout_s))


def _sem_repeticao_em_duvida(pedido: Pedido, modo: str, desfecho: Desfecho) -> Desfecho:
    """G-0087 (parte do ledger): efeito irreversível em `real|teste` que volta `transitorio` sem a prova `nada_saiu` pode ter acontecido
    (erro tipado depois do disparo, resposta que não se reconstrói): vira `indeterminado` e nunca se repete."""
    irreversivel_real = pedido.classe_efeito == "efeito_irreversivel" and modo in DESTINOS_REAIS
    if desfecho.estado == "transitorio" and not desfecho.nada_saiu and irreversivel_real:
        return Desfecho("indeterminado", http_bucket=desfecho.http_bucket, ref_externa=desfecho.ref_externa, custo_brl=desfecho.custo_brl)
    return desfecho


async def _chamar_cru(pedido: Pedido, modo: str, chamar: Chamada, simular: Chamada | None, timeout_s: float) -> Desfecho:
    if modo not in DESTINOS_REAIS:
        if simular is None:
            return Desfecho("ok")
        try:
            return await simular(modo)
        except Exception as erro:  # a simulação não manda nada para fora: falhar aqui não pode deixar a linha `enviada`
            log.warning("simulação de %s falhou (%s): transitorio", pedido.ferramenta, type(erro).__name__)
            return _desfecho_da_falha(pedido, modo, "rede")
    try:
        return await asyncio.wait_for(chamar(modo), timeout_s)
    except TimeoutError:
        return _desfecho_da_falha(pedido, modo, "timeout")
    except Exception:  # erro do cliente/protocolo: não se sabe se saiu
        return _desfecho_da_falha(pedido, modo, "rede")


async def _chamar_e_fechar(
    conn: psycopg.Connection, pedido: Pedido, linha: _Linha, *, chamar: Chamada, simular: Chamada | None, relogio: Relogio, timeout_s: float
) -> _Linha:
    inicio = time.monotonic()
    tarefa = asyncio.ensure_future(_chamar(pedido, linha.modo, chamar, simular, timeout_s))
    try:
        desfecho = await asyncio.shield(tarefa)
    except asyncio.CancelledError:
        tarefa.cancel()  # a chamada fica sem dono; o que vale é o ledger: corte no meio do envio = indeterminado
        corte = _desfecho_da_falha(pedido, linha.modo, "rede")
        await asyncio.shield(asyncio.to_thread(_fechar, conn, linha.chamada_id, corte, _ms(inicio), relogio.agora()))
        raise
    fechada = await asyncio.shield(asyncio.to_thread(_fechar, conn, linha.chamada_id, desfecho, _ms(inicio), relogio.agora()))
    return fechada or await asyncio.to_thread(_ler, conn, pedido)


def _ms(inicio: float) -> int:
    return max(0, int((time.monotonic() - inicio) * 1000))


# --- executar_efeito -------------------------------------------------------------------------------------------------------------------


async def _repetida(
    conn: psycopg.Connection,
    atd: uuid.UUID,
    pedido: Pedido,
    cerca: Cerca | None,
    leitor: LeitorConfig,
    relogio: Relogio,
    timeout_s: float,
) -> tuple[_Linha | None, ResultadoEfeito | None]:
    """A chave já existia. Devolve (linha reivindicada para chamar, None) ou (None, resultado final sem chamar)."""
    existente = await asyncio.to_thread(_ler, conn, pedido)
    if not existente.do_mesmo_pedido(atd, pedido):
        raise ChaveDivergente("a chave_logica já está no ledger para outro pedido")
    if existente.estado in EM_VOO and _morta(existente, relogio.agora(), timeout_s):
        existente = await asyncio.to_thread(_fechar_orfa, conn, pedido, existente, relogio.agora()) or await asyncio.to_thread(
            _ler, conn, pedido
        )
    if existente.estado in REEXECUTAVEIS:
        reivindicada, existente = await asyncio.to_thread(
            _reivindicar, conn, atd, pedido, existente.chamada_id, cerca, leitor, relogio.agora()
        )
        if reivindicada is not None:
            return reivindicada, None
    return None, _resultado(existente, executou=False, repetido=True)


def desfecho_da_orfa(classe_efeito: str, modo: str) -> EstadoFinal:
    """G-0131: a execução que reivindicou morreu (OOM, deploy) sem fechar. Só o efeito irreversível que correu em `real|teste` pode ter
    saído e não se repete (`indeterminado`); ação interna (T12 idempotente por `repasse_id`, `assumir`, `restaurar`), leitura e qualquer
    efeito simulado voltam a `transitorio` e se repetem com a MESMA chave (08 §7.1: «indeterminado nunca reenvia» não vale para o T12)."""
    return "indeterminado" if classe_efeito == "efeito_irreversivel" and modo in DESTINOS_REAIS else "transitorio"


def _fechar_orfa(conn: psycopg.Connection, pedido: Pedido, linha: _Linha, agora: datetime) -> _Linha | None:
    return _fechar(conn, linha.chamada_id, Desfecho(desfecho_da_orfa(pedido.classe_efeito, linha.modo)), 0, agora)


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
    (cerca), `ConfirmacaoAusente`, `EfeitoOcupado` e `ChaveDivergente` antes de chamar qualquer coisa. Um `estado` não terminal no
    resultado (`enviada`, ou `transitorio` que a parada dura não deixa reexecutar) quer dizer «não chamou agora»: quem chama NÃO reenvia."""
    if not conn.autocommit or conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
        raise RuntimeError(
            "executar_efeito exige conexão em autocommit e fora de transação: a reserva precisa estar commitada antes da chamada"
        )
    nova, versao = await asyncio.to_thread(_reservar, conn, atendimento_id, pedido, cerca, leitor, relogio.agora())
    if nova is not None:
        cerca_nova = Cerca(versao, cerca.estados) if cerca is not None and versao is not None else None
        reivindicada, atual = await asyncio.to_thread(
            _reivindicar, conn, atendimento_id, pedido, nova.chamada_id, cerca_nova, leitor, relogio.agora()
        )
        repetido = False
        if reivindicada is None:  # outra execução reivindicou a linha recém-criada (corrida da mesma chave)
            return _resultado(atual, executou=False, repetido=True, versao=versao)
    else:
        reivindicada, pronto = await _repetida(conn, atendimento_id, pedido, cerca, leitor, relogio, timeout_s)
        repetido = True
        if pronto is not None:
            return pronto
    if reivindicada is None:
        raise EstadoErro("ledger sem linha reivindicada")
    fechada = await _chamar_e_fechar(conn, pedido, reivindicada, chamar=chamar, simular=simular, relogio=relogio, timeout_s=timeout_s)
    return _resultado(fechada, executou=reivindicada.modo in DESTINOS_REAIS, repetido=repetido, versao=versao)
