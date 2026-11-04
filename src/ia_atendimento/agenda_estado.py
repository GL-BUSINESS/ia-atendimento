"""Estados da linha `ia.agendamento` (B5.7b, estudo M §3): `pendente → confirmado → disparado`, ou `cancelado`/`expirado` pelo caminho.

Cada transição é um `UPDATE … WHERE agendamento_id = $1 AND versao = $2 AND estado ∈ de` com `versao + 1` (CAS, como `estado.aplicar`):
quem perde a corrida leva `ConflitoVersao` (outro escritor mexeu) ou `TransicaoInvalida` (o estado já não é o de origem) e **não age**.
É esse CAS que garante «nenhum duplicado»: o job `retomar` só envia a volta quem ganhou `confirmado → disparado`.

- **Um ativo por atendimento** é do banco (`agendamento_ativo_uq`, índice parcial em `pendente|confirmado`); `seq` 1..2 limita o
  reagendamento a 2. Nada disso se repete aqui.
- Os CHECKs de forma do estado (`confirmado` exige `confirmado_em` e `confirmacao_origem`; `disparado`, `disparado_em` e `desfecho_disparo`;
  `cancelado`, `cancelado_por`) são do banco: violação sai como `TransicaoInvalida` com o NOME da restrição.
- Cada mudança relevante grava o passo `agendamento` da linha do tempo (`passo_de_agendamento`), com texto montado por código.
- **`disparado` não é beco sem saída (R1-02):** a reivindicação vem ANTES das pré-checagens da volta, e o estudo M §2.5/§2.6 manda
  `reagendado_sistema` («próximo horário válido, MESMO agendamento») e «tentar a +10 min». `rearmar` faz `disparado → confirmado` com novo
  `dispara_em`, sem consumir `seq` (o teto de 2 é do CLIENTE reagendar) e movendo `retoma_em`/`lease_ate` do atendimento junto; no máximo
  `MAX_REARMES` por agendamento, senão o lead ficaria preso fora do `reaper_lease` para sempre.
- A confirmação do cliente (TX-M02/M08) e o reagendamento pelo cliente são da B5.7c; `confirmar` existe aqui porque o `retomar` só dispara
  `confirmado` e porque ela é a única porta para esse estado.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, fields
from datetime import datetime, timedelta
from typing import Any, Final, Literal

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from ia_atendimento.estado import Mudancas, aplicar, executar_traduzindo
from ia_atendimento.estado_erros import ConflitoVersao, EntradaInvalida, EstadoErro, TransicaoInvalida
from ia_atendimento.estado_pausa import AGENDA_FOLGA_MIN
from ia_atendimento.linha_tempo import CtxPasso, gravar_passo, travar_atendimento
from ia_atendimento.passos import Agendamento as PassoAgendamento

EstadoAgendamento = Literal["pendente", "confirmado", "disparado", "cancelado", "expirado"]
Desfecho = Literal["retomou", "resolvido", "reagendado_sistema", "repassou", "humano_atuou"]
Origem = Literal["cliente", "tacita", "operador"]
CanceladoPor = Literal["cliente", "humano_assumiu", "operador", "opt_out", "reagendado", "sistema"]
ResultadoDoPasso = Literal["proposto", "confirmado", "reagendado", "cancelado", "expirado", "disparado", "resolvido"]
ATIVOS: Final = ("pendente", "confirmado")
MAX_REARMES: Final = 2  # volta + até 2 novas tentativas (calendário ou +10 min) por agendamento; depois é o lease que devolve o lead


class AgendamentoInexistente(EstadoErro):
    pass


class LimiteDeRearmes(EstadoErro):
    """O agendamento já foi rearmado `MAX_REARMES` vezes: o lead segue para o `reaper_lease` (devolução ao humano)."""


@dataclass(frozen=True)
class Dono:
    """O atendimento dono do agendamento, lido com `FOR UPDATE` (a ordem de locks é sempre atendimento, depois agendamento)."""

    atendimento_id: uuid.UUID
    estado: str
    gatilho: str
    chat_id: str
    lease_ate: datetime | None
    versao: int


def travar_dono(conn: psycopg.Connection, agendamento_id: uuid.UUID | str) -> Dono | None:
    linha = conn.execute(
        "SELECT a.atendimento_id, a.estado, a.gatilho, a.chat_id, a.lease_ate, a.versao FROM ia.atendimento a"
        " WHERE a.atendimento_id = (SELECT atendimento_id FROM ia.agendamento WHERE agendamento_id = %s) FOR UPDATE",
        (agendamento_id,),
    ).fetchone()
    return None if linha is None else Dono(*linha)


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


def expirar(conn: psycopg.Connection, agendamento_id: uuid.UUID | str, versao: int, *, agora: datetime) -> int:
    """`confirmado → expirado`: a hora combinada passou do teto de atraso (o lease do atendimento já venceu) e a volta NÃO sai. O lead é do
    `reaper_lease` (`retomada_perdida`), que o devolve ao humano. O CHECK de `expirado` só exige `cancelado_por` e `disparado_em` nulos."""
    return _transicionar(conn, agendamento_id, versao, de=("confirmado",), mudancas={"estado": "expirado"}, agora=agora)


def esperando_a_volta(entrada: str, estado: str, gatilho: str) -> bool:
    """O atendimento ainda espera a volta combinada: (a) `pausado`, ou (b) `reservado` de agendamento que não tocou o chat."""
    return (entrada == "pausa_ia" and estado == "pausado") or (
        entrada == "dialogo_agendar" and estado == "reservado" and gatilho == "agendamento"
    )


def rearmar(
    conn: psycopg.Connection,
    agendamento_id: uuid.UUID | str,
    *,
    dispara_em: datetime,
    agora: datetime,
    folga_min: int = AGENDA_FOLGA_MIN,
) -> int:
    """`disparado → confirmado` com novo `dispara_em`: MESMO agendamento, `seq` intacto (R1-02). Para a volta que decidiu adiar
    (`reagendado_sistema`: calendário/DATAPREV; ou «tentar» a +10 min). Na transação de quem chama, que já é o dono do disparo.

    Move o atendimento junto (`retoma_em = dispara_em`, `lease_ate = dispara_em + folga`, nunca encurtando): sem isso o `reaper_lease`
    devolveria o lead no lease velho. Exige o atendimento ainda à espera. Limite de `MAX_REARMES` (`LimiteDeRearmes`). Grava o passo
    `reagendado`. Devolve a nova `versao` do agendamento."""
    if agora.tzinfo is None or dispara_em.tzinfo is None:
        raise ValueError("`agora` e `dispara_em` exigem datetime com fuso")
    if dispara_em <= agora:
        raise EntradaInvalida("o rearme precisa de um dispara_em no futuro")
    dono = travar_dono(conn, agendamento_id)
    if dono is None:
        raise AgendamentoInexistente("agendamento não existe")
    linha = ler_agendamento(conn, agendamento_id, travar=True)
    if not esperando_a_volta(linha.entrada, dono.estado, dono.gatilho):
        raise TransicaoInvalida(f"atendimento {dono.estado} não espera mais a volta: não se rearma")
    feitos = conn.execute(
        "SELECT count(*) FROM ia.passo WHERE agendamento_id = %s AND tipo = 'agendamento' AND resultado = 'reagendado'", (agendamento_id,)
    ).fetchone()[0]
    if feitos >= MAX_REARMES:
        raise LimiteDeRearmes(f"agendamento já rearmado {feitos} vez(es)")
    nova = _transicionar(
        conn,
        agendamento_id,
        linha.versao,
        de=("disparado",),
        mudancas={"estado": "confirmado", "dispara_em": dispara_em, "disparado_em": None, "desfecho_disparo": None, "job_id": None},
        agora=agora,
    )
    movido = Mudancas(retoma_em=dispara_em, lease_ate=dispara_em + timedelta(minutes=folga_min))
    aplicar(conn, dono.atendimento_id, dono.versao, movido, agora=agora, de={dono.estado}, lease_so_cresce=True)
    passo_de_agendamento(conn, dono.atendimento_id, uuid.UUID(str(agendamento_id)), "reagendado")
    return nova


SituacaoDaVoltaPerdida = Literal["nao_falou", "pode_ter_falado"]


@dataclass(frozen=True)
class VoltaPerdidaFechada:
    """Como ficou o agendamento quando o `reaper_lease` devolveu o lead (R2-03) e qual nota ao consultor é VERDADE nessa situação."""

    situacao: SituacaoDaVoltaPerdida
    estado_antes: str  # `pendente`, `confirmado`, `disparado` ou `expirado`
    nota: str  # id do texto em `textos/TEXTOS-PARA-APROVACAO.md`


def nota_da_volta_perdida(situacao: SituacaoDaVoltaPerdida, retoma_fase: str | None) -> str:
    """NT-06 («a IA não retomou») só quando é verdade: a IA NUNCA falou (`expirado`, `confirmado` órfão, `pendente`). Se a volta foi
    reivindicada (`disparado`) a mensagem PODE ter saído: E8 usa NT-05 («não conseguiu concluir»), as demais fases NT-01 («interrompido por
    instabilidade; o cliente pode ter escrito sem resposta»). Os textos ainda esperam a aprovação do dono (D36)."""
    if situacao == "nao_falou":
        return "NT-06"
    return "NT-05" if retoma_fase == "E8" else "NT-01"


def fechar_volta_perdida(conn: psycopg.Connection, atendimento_id: uuid.UUID | str, *, agora: datetime) -> VoltaPerdidaFechada | None:
    """O handler de `retomada_perdida`/`agendamento_perdido` (B1.6) chama isto NA TRANSAÇÃO do repasse (ou do aborto), para a linha do
    agendamento não ficar mentindo: depois do CAS ela diz `disparado/retomou`, e sem isto diria isso PARA SEMPRE, mesmo com o lead repassado
    (as métricas «repasse por falha da volta» e «resposta após a volta» saem erradas). Fecha o agendamento mais novo do atendimento com
    resultado PRÓPRIO:

    - `disparado` → desfecho `repassou` (a volta foi reivindicada e se perdeu: a mensagem pode ter saído);
    - `confirmado` (alarme perdido e o `reaper_lease` chegou antes do `reaper_agenda`) → `cancelado` por `sistema`, passo `cancelado`;
    - `pendente` (a confirmação nunca veio) → `expirado`, passo `expirado`;
    - `expirado` (teto de atraso do `retomar`) e `cancelado` já estão fechados: nada a fazer.

    Devolve `None` se o atendimento não tem agendamento. Trava o atendimento antes do agendamento (a ordem de locks de sempre)."""
    travar_atendimento(conn, uuid.UUID(str(atendimento_id)))
    achado = conn.execute(
        "SELECT agendamento_id FROM ia.agendamento WHERE atendimento_id = %s ORDER BY seq DESC LIMIT 1", (atendimento_id,)
    ).fetchone()
    if achado is None:
        return None
    linha = ler_agendamento(conn, achado[0], travar=True)
    if linha.estado == "disparado":
        _transicionar(conn, linha.agendamento_id, linha.versao, de=("disparado",), mudancas={"desfecho_disparo": "repassou"}, agora=agora)
    elif linha.estado == "confirmado":
        cancelar(conn, linha.agendamento_id, linha.versao, por="sistema", agora=agora)
        passo_de_agendamento(conn, linha.atendimento_id, linha.agendamento_id, "cancelado")
    elif linha.estado == "pendente":
        _transicionar(conn, linha.agendamento_id, linha.versao, de=("pendente",), mudancas={"estado": "expirado"}, agora=agora)
        passo_de_agendamento(conn, linha.atendimento_id, linha.agendamento_id, "expirado")
    situacao: SituacaoDaVoltaPerdida = "pode_ter_falado" if linha.estado == "disparado" else "nao_falou"
    return VoltaPerdidaFechada(situacao, linha.estado, nota_da_volta_perdida(situacao, linha.retoma_fase))


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
