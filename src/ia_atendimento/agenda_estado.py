"""Estados da linha `ia.agendamento` (B5.7b, estudo M §3): `pendente → confirmado → disparado`, ou `cancelado`/`expirado` pelo caminho.

Cada transição é um `UPDATE … WHERE agendamento_id = $1 AND versao = $2 AND estado ∈ de` com `versao + 1` (CAS, como `estado.aplicar`):
quem perde a corrida leva `ConflitoVersao` (outro escritor mexeu) ou `TransicaoInvalida` (o estado já não é o de origem) e **não age**.
É esse CAS que garante «nenhum duplicado»: o job `retomar` só envia a volta quem ganhou `confirmado → disparado`.

- **Um ativo por atendimento** é do banco (`agendamento_ativo_uq`, índice parcial em `pendente|confirmado`); `seq` 1..2 limita o
  reagendamento a 2. Nada disso se repete aqui.
- Os CHECKs de forma do estado (`confirmado` exige `confirmado_em` e `confirmacao_origem`; `disparado`, `disparado_em` e `desfecho_disparo`;
  `cancelado`, `cancelado_por`) são do banco: violação sai como `TransicaoInvalida` com o NOME da restrição.
- Cada mudança relevante grava o passo `agendamento` da linha do tempo (`passo_de_agendamento`), com texto montado por código.
- A confirmação do cliente (TX-M02/M08), a expiração e o reagendamento são da B5.7c; `confirmar` existe aqui porque o `retomar` só dispara
  `confirmado` e porque ela é a única porta para esse estado.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, fields
from datetime import datetime
from typing import Any, Final, Literal

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from ia_atendimento.estado import executar_traduzindo
from ia_atendimento.estado_erros import ConflitoVersao, EstadoErro, TransicaoInvalida
from ia_atendimento.linha_tempo import CtxPasso, gravar_passo, travar_atendimento
from ia_atendimento.passos import Agendamento as PassoAgendamento

EstadoAgendamento = Literal["pendente", "confirmado", "disparado", "cancelado", "expirado"]
Desfecho = Literal["retomou", "resolvido", "reagendado_sistema", "repassou", "humano_atuou"]
Origem = Literal["cliente", "tacita", "operador"]
CanceladoPor = Literal["cliente", "humano_assumiu", "operador", "opt_out", "reagendado", "sistema"]
ResultadoDoPasso = Literal["proposto", "confirmado", "reagendado", "cancelado", "expirado", "disparado", "resolvido"]
ATIVOS: Final = ("pendente", "confirmado")


class AgendamentoInexistente(EstadoErro):
    pass


@dataclass(frozen=True)
class LinhaAgendamento:
    agendamento_id: uuid.UUID
    atendimento_id: uuid.UUID
    chat_id: str
    entrada: str
    seq: int
    retoma_fase: str | None
    estado: str
    versao: int
    dispara_em: datetime | None
    confirmado_em: datetime | None
    confirmacao_origem: str | None
    disparado_em: datetime | None
    desfecho_disparo: str | None
    cancelado_por: str | None
    cancelado_em: datetime | None
    job_id: int | None


_COLUNAS: Final = tuple(f.name for f in fields(LinhaAgendamento))


def ler_agendamento(conn: psycopg.Connection, agendamento_id: uuid.UUID | str, *, travar: bool = False) -> LinhaAgendamento:
    """A linha do agendamento. `travar=True` faz `FOR UPDATE`: quem decide sobre ela dentro de uma transação a segura até o fim."""
    colunas = sql.SQL(", ").join(sql.Identifier(c) for c in _COLUNAS)
    trava = sql.SQL(" FOR UPDATE") if travar else sql.SQL("")
    consulta = sql.SQL("SELECT {} FROM ia.agendamento WHERE agendamento_id = %s{}").format(colunas, trava)
    with conn.cursor(row_factory=dict_row) as cur:
        linha = cur.execute(consulta, (agendamento_id,)).fetchone()
    if linha is None:
        raise AgendamentoInexistente("agendamento não existe")
    return LinhaAgendamento(**linha)


def _transicionar(
    conn: psycopg.Connection,
    agendamento_id: uuid.UUID | str,
    versao: int,
    *,
    de: tuple[str, ...],
    mudancas: dict[str, Any],
    agora: datetime,
) -> int:
    """CAS: `SET <mudancas>, versao + 1 WHERE … versao = $v AND estado ∈ de`. Os nomes de coluna são do nosso código."""
    if agora.tzinfo is None:
        raise ValueError("`agora` exige datetime com fuso")
    sets = [sql.SQL("{} = {}").format(sql.Identifier(c), sql.Placeholder(f"p_{c}")) for c in mudancas]
    consulta = sql.SQL(
        "UPDATE ia.agendamento SET {}, versao = versao + 1, atualizado_em = %(agora)s "
        "WHERE agendamento_id = %(id)s AND versao = %(versao)s AND estado = ANY(%(de)s) RETURNING versao"
    ).format(sql.SQL(", ").join(sets))
    params = {f"p_{c}": v for c, v in mudancas.items()} | {"agora": agora, "id": agendamento_id, "versao": versao, "de": list(de)}
    linha = executar_traduzindo(conn, consulta, params, check_e_transicao=True)
    if linha is not None:
        return int(linha[0])
    atual = ler_agendamento(conn, agendamento_id)
    if atual.versao != versao:
        raise ConflitoVersao(f"versão esperada {versao}, atual {atual.versao}")
    raise TransicaoInvalida(f"agendamento {atual.estado} não sai de {'/'.join(de)} por esta transição")


def confirmar(conn: psycopg.Connection, agendamento_id: uuid.UUID | str, versao: int, *, origem: Origem, agora: datetime) -> int:
    """`pendente → confirmado` (o cliente disse sim, ou a confirmação tácita da B5.7c). Exige `horario_extraido` e `dispara_em` (CHECK)."""
    mudancas = {"estado": "confirmado", "confirmado_em": agora, "confirmacao_origem": origem}
    return _transicionar(conn, agendamento_id, versao, de=("pendente",), mudancas=mudancas, agora=agora)


def disparar(
    conn: psycopg.Connection,
    agendamento_id: uuid.UUID | str,
    versao: int,
    *,
    agora: datetime,
    desfecho: Desfecho = "retomou",
    job_id: int | None = None,
) -> int:
    """`confirmado → disparado`: **quem ganha este CAS é o único que fala com o cliente**. O desfecho entra já (o CHECK exige), como
    `retomou`; se as pré-checagens da volta (B5.7c) decidirem outra coisa, `registrar_desfecho` o troca."""
    mudancas = {"estado": "disparado", "disparado_em": agora, "desfecho_disparo": desfecho, "job_id": job_id}
    return _transicionar(conn, agendamento_id, versao, de=("confirmado",), mudancas=mudancas, agora=agora)


def registrar_desfecho(conn: psycopg.Connection, agendamento_id: uuid.UUID | str, desfecho: Desfecho, *, agora: datetime) -> int:
    """Troca o `desfecho_disparo` de um `disparado` (a volta acabou em `resolvido`, `repassou`...). Só o dono do disparo a chama."""
    atual = ler_agendamento(conn, agendamento_id)
    return _transicionar(conn, agendamento_id, atual.versao, de=("disparado",), mudancas={"desfecho_disparo": desfecho}, agora=agora)


def cancelar(conn: psycopg.Connection, agendamento_id: uuid.UUID | str, versao: int, *, por: CanceladoPor, agora: datetime) -> int:
    """`pendente|confirmado → cancelado`. O `retomar` cancela por `sistema` se o atendimento já não espera a volta."""
    mudancas = {"estado": "cancelado", "cancelado_por": por, "cancelado_em": agora}
    return _transicionar(conn, agendamento_id, versao, de=ATIVOS, mudancas=mudancas, agora=agora)


def passo_de_agendamento(
    conn: psycopg.Connection, atendimento_id: uuid.UUID, agendamento_id: uuid.UUID, resultado: ResultadoDoPasso
) -> int:
    """Grava o passo `agendamento` (turno = rodada, fase = a atual) e devolve a `ordem`. Roda na transação de quem chama."""
    dados = PassoAgendamento(agendamento_id=agendamento_id, resultado=resultado)
    with conn.transaction():
        fase, rodada = travar_atendimento(conn, atendimento_id)
        return gravar_passo(conn, atendimento_id, ctx=CtxPasso(turno=rodada, fase=fase), dados=dados).ordem
