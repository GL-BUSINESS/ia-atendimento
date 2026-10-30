"""Mensagem recebida do cliente (B1.5, contrato 08 §5.1 e §5.3): UMA função para o webhook (`/eventos/chatguru`) e para o RPA
(`/eventos/mensagem`), com a mesma `msg_chave` e o mesmo `msg_fingerprint` para a mesma mensagem.

Ordem da decisão (F24): atendimento ativo do chat (`descartado` se não há) → identidade (`linha_tempo.gravar_mensagem_recebida`: busca
exata,
replay sem hora) → **casamento webhook × RPA** → inserir. Gravar = passo `mensagem_recebida` + conversa cifrada (texto MASCARADO) +
`ultimo_cliente_em` + job `turno`, tudo numa transação. O texto do cliente só passa por aqui em memória: nada em log, nada na resposta.

Casamento (`criar_casador`): candidatos = passos do MESMO atendimento, de OUTRA fonte e ainda sem contraparte, do mesmo `tipo` e (texto)
com o
mesmo `texto_chave` (mascarado, espaços colapsados, `casefold`). Janela: `|Δ msg_enviada_em| ≤ casamento_janela_s` se os dois lados têm
hora;
senão `|Δ ocorrido_em| ≤ casamento_janela_sem_hora_s` (relógio do banco). Um para um: o de menor `|Δt|` (empate: menor `ordem`). Webhook
primeiro ⇒ o `_id`
do RPA entra por `ia.fn_anexar_rpa` (0004); RPA primeiro ⇒ nada se grava (o passo não tem coluna para a chave `cg:`: limite aceito).
"""

from __future__ import annotations

import logging
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final, Literal

import psycopg

from ia_atendimento.cifra import ChaveDesconhecida, Chaveiro
from ia_atendimento.conversa import gravar_troca
from ia_atendimento.enfileirador import Enfileirador
from ia_atendimento.estado_conversa import registrar_mensagem_do_cliente
from ia_atendimento.evento_mensagem import ChavesDeMensagem, EventoMensagem, Identidade
from ia_atendimento.linha_tempo import (
    Casada,
    Casador,
    Conflito,
    CtxPasso,
    Duplicada,
    Gravada,
    gravar_mensagem_recebida,
    gravar_passo,
    travar_atendimento,
)
from ia_atendimento.mascara import mascarar
from ia_atendimento.passos import Erro

log = logging.getLogger(__name__)

TOLERANCIA_FUTURO: Final = timedelta(minutes=5)  # mesma tolerância de `registrar_mensagem_do_cliente`
PECA_DO_CONFLITO: Final = "receptor"
Resultado = Literal["gravado", "repetido", "anexado", "descartado", "conflito"]


@dataclass(frozen=True)
class Ativo:
    """O atendimento ativo (qualquer estado ≠ `encerrado`) do chat."""

    atendimento_id: uuid.UUID
    estado: str
    modo: str
    ultimo_cliente_em: datetime | None


@dataclass(frozen=True)
class RespostaMensagem:
    """Corpo do 200 de `/eventos/*` (tabela única do contrato 08 §5.3): só códigos e identificadores opacos, nunca texto."""

    resultado: Resultado
    recebido: bool = True
    motivo: str | None = None
    atendimento_id: uuid.UUID | None = None
    ordem: int | None = None
    fora_de_ordem: bool | None = None
    turno_enfileirado: bool | None = None
    delegacao_externa: bool | None = None

    def corpo(self) -> dict[str, Any]:
        bruto = {
            "recebido": self.recebido, "resultado": self.resultado, "motivo": self.motivo,
            "atendimento_id": None if self.atendimento_id is None else str(self.atendimento_id), "ordem": self.ordem,
            "fora_de_ordem": self.fora_de_ordem, "turno_enfileirado": self.turno_enfileirado, "delegacao_externa": self.delegacao_externa,
        }  # fmt: skip
        return {k: v for k, v in bruto.items() if v is not None}


@dataclass(frozen=True)
class DepsMensagem:
    chaves: ChavesDeMensagem
    chaveiro: Chaveiro
    enfileirador: Enfileirador
    casamento_janela_s: int
    casamento_janela_sem_hora_s: int


def atendimento_ativo(conn: psycopg.Connection, chat_id: str, *, travar: bool = False) -> Ativo | None:
    """O índice único parcial `atendimento_ativo_chat_uq` garante no máximo um.

    `travar=True` lê com `FOR UPDATE` (dentro de uma transação): o estado vale até o commit, e um atendimento encerrado enquanto se
    esperava o lock sai do filtro (READ COMMITTED reavalia o WHERE)."""
    consulta = "SELECT atendimento_id, estado, modo, ultimo_cliente_em FROM ia.atendimento WHERE chat_id = %s AND estado <> 'encerrado'"
    linha = conn.execute(consulta + (" FOR UPDATE" if travar else ""), (chat_id,)).fetchone()
    return None if linha is None else Ativo(*linha)


# --- casamento webhook × RPA -----------------------------------------------------------------------------------------------------------


def texto_chave(texto: str) -> str:
    """Chave de comparação do texto: mascarado (como foi gravado), espaços internos colapsados, `casefold`, NFC."""
    return " ".join(unicodedata.normalize("NFC", mascarar(texto)).split()).casefold()


@dataclass(frozen=True)
class _Candidato:
    passo_id: int
    ordem: int
    msg_chave: str
    delta_s: float


_SQL_CANDIDATOS_COM_HORA: Final = """
SELECT passo_id, ordem, msg_chave, abs(extract(epoch FROM msg_enviada_em - %(hora)s)) AS delta
FROM ia.passo
WHERE atendimento_id = %(atd)s AND tipo = 'mensagem_recebida' AND msg_tipo = %(tipo)s AND {lado}
  AND msg_enviada_em IS NOT NULL AND abs(extract(epoch FROM msg_enviada_em - %(hora)s)) <= %(janela)s
UNION ALL
SELECT passo_id, ordem, msg_chave, abs(extract(epoch FROM now() - ocorrido_em)) AS delta
FROM ia.passo
WHERE atendimento_id = %(atd)s AND tipo = 'mensagem_recebida' AND msg_tipo = %(tipo)s AND {lado}
  AND msg_enviada_em IS NULL AND abs(extract(epoch FROM now() - ocorrido_em)) <= %(janela_sem_hora)s
"""
_SQL_CANDIDATOS_SEM_HORA: Final = """
SELECT passo_id, ordem, msg_chave, abs(extract(epoch FROM now() - ocorrido_em)) AS delta
FROM ia.passo
WHERE atendimento_id = %(atd)s AND tipo = 'mensagem_recebida' AND msg_tipo = %(tipo)s AND {lado}
  AND abs(extract(epoch FROM now() - ocorrido_em)) <= %(janela_sem_hora)s
"""
# O evento do RPA procura linhas do webhook SEM contraparte; o do webhook procura linhas do RPA (que não guardam a chave `cg:`).
_LADO_DO_WEBHOOK: Final = "msg_chave_rpa IS NULL AND (msg_chave LIKE 'cg:%%' OR msg_chave LIKE 'cgid:%%')"
_LADO_DO_RPA: Final = "msg_chave LIKE 'rpa:%%'"


def _candidatos(conn: psycopg.Connection, atendimento_id: uuid.UUID, evento: EventoMensagem, deps: DepsMensagem) -> list[_Candidato]:
    lado = _LADO_DO_WEBHOOK if evento.origem_evento == "reconciliacao" else _LADO_DO_RPA
    consulta = (_SQL_CANDIDATOS_COM_HORA if evento.datetime_post is not None else _SQL_CANDIDATOS_SEM_HORA).format(lado=lado)
    linhas = conn.execute(
        consulta,
        {
            "atd": atendimento_id, "tipo": evento.tipo, "hora": evento.datetime_post, "janela": deps.casamento_janela_s,
            "janela_sem_hora": deps.casamento_janela_sem_hora_s,
        },
    ).fetchall()  # fmt: skip
    return sorted((_Candidato(*linha) for linha in linhas), key=lambda c: (c.delta_s, c.ordem))


def _texto_do_passo(conn: psycopg.Connection, atendimento_id: uuid.UUID, ordem: int, chaveiro: Chaveiro) -> str | None:
    """Texto (já mascarado) que a conversa guardou para o passo; `None` se a linha não existe ou a chave do mês foi descartada."""
    linha = conn.execute(
        "SELECT seq, remetente, tipo, chave_id, nonce, cifra FROM ia.conversa_cifrada"
        " WHERE atendimento_id = %s AND passo_ordem = %s AND tipo = 'mensagem'",
        (atendimento_id, ordem),
    ).fetchone()
    if linha is None:
        return None
    seq, remetente, tipo, chave_id, nonce, cifra = linha
    try:
        return chaveiro.decifrar(chave_id, bytes(nonce), bytes(cifra), atendimento_id, seq=seq, remetente=remetente, tipo=tipo)
    except ChaveDesconhecida:
        return None


def criar_casador(deps: DepsMensagem) -> Casador:
    """O gancho `casar` de `gravar_mensagem_recebida`: roda dentro do `FOR UPDATE` do atendimento, depois da busca exata."""

    def casar(conn: psycopg.Connection, atendimento_id: uuid.UUID, evento: EventoMensagem, ident: Identidade) -> int | None:
        quer = texto_chave(evento.texto or "") if evento.tipo == "texto" else None
        for candidato in _candidatos(conn, atendimento_id, evento, deps):
            if quer is not None:
                guardado = _texto_do_passo(conn, atendimento_id, candidato.ordem, deps.chaveiro)
                if guardado is None or texto_chave(guardado) != quer:
                    continue
            if evento.origem_evento != "reconciliacao":
                return candidato.ordem  # RPA primeiro: o passo não tem onde guardar a chave `cg:`
            anexou = conn.execute("SELECT ia.fn_anexar_rpa(%s, %s)", (candidato.passo_id, evento.rpa_id)).fetchone()
            return candidato.ordem if anexou and anexou[0] else None  # só o melhor candidato casa (um para um)
        return None

    return casar


# --- registrar -------------------------------------------------------------------------------------------------------------------------


def _quando_do_cliente(evento: EventoMensagem, agora: datetime) -> datetime:
    """Hora da mensagem para o `ultimo_cliente_em`: a do evento; sem ela, a do recebimento. Relógio do cliente mais de 5 min adiantado
    vale o recebimento (o valor só avança: um futuro gravado nunca se corrige)."""
    quando = evento.datetime_post or agora
    return agora if quando > agora + TOLERANCIA_FUTURO else quando


def _texto_da_conversa(evento: EventoMensagem) -> str:
    return (evento.texto or "") if evento.tipo == "texto" else f"[{evento.tipo}]"  # mídia grava só o marcador e não chama o modelo (TX-30)


def _registrar_conflito(conn: psycopg.Connection, atendimento_id: uuid.UUID, ativo: Ativo) -> None:
    """Mesma `msg_chave` com outro fingerprint: passo `erro` (peça `receptor`, sem texto) e alerta ao TI. Nada de conteúdo no log."""
    with conn.transaction():
        fase, rodada = travar_atendimento(conn, atendimento_id)
        gravar_passo(conn, atendimento_id, ctx=CtxPasso(turno=rodada, fase=fase), dados=Erro(peca=PECA_DO_CONFLITO))
    log.warning("alerta ti: evento_conflito atendimento=%s estado=%s", str(atendimento_id)[:6], ativo.estado)


def registrar_mensagem(
    conn: psycopg.Connection,
    evento: EventoMensagem,
    *,
    chat_id: str,
    agora: datetime,
    delegacao_externa: bool,
    deps: DepsMensagem,
) -> RespostaMensagem:
    """Grava a mensagem do cliente no atendimento ativo do chat (decide `gravado|repetido|anexado|conflito|descartado`).

    O atendimento é RELIDO sob o lock da própria transação (R1-04): a leitura sem trava de quem chama pode estar velha. Entre ela e o
    lock ele pode ter encerrado (nada se grava: `descartado`) ou ido a `repassando` (grava, sem enfileirar turno). Quem chama já tratou
    `texto_vazio` e a regra do canal de teste."""
    with conn.transaction():
        ativo = atendimento_ativo(conn, chat_id, travar=True)
        if ativo is None:
            return RespostaMensagem("descartado", motivo="sem_atendimento")
        fora_de_ordem = (
            evento.datetime_post is not None and ativo.ultimo_cliente_em is not None and evento.datetime_post < ativo.ultimo_cliente_em
        )
        decisao = gravar_mensagem_recebida(
            conn, ativo.atendimento_id, evento=evento, chaves=deps.chaves, recebido_em=agora, casar=criar_casador(deps),
            fora_de_ordem=fora_de_ordem,
        )  # fmt: skip
        if isinstance(decisao, Gravada):
            return _gravada(
                conn, ativo, evento, decisao, chat_id=chat_id, agora=agora, delegacao_externa=delegacao_externa, deps=deps,
                fora_de_ordem=fora_de_ordem,
            )  # fmt: skip
    base = {"atendimento_id": ativo.atendimento_id}
    if isinstance(decisao, Duplicada):
        return RespostaMensagem("repetido", **base)
    if isinstance(decisao, Casada):
        return RespostaMensagem("anexado", ordem=decisao.ordem, turno_enfileirado=False, **base)
    if isinstance(decisao, Conflito):
        _registrar_conflito(conn, ativo.atendimento_id, ativo)
        return RespostaMensagem("conflito", recebido=False, **base)
    raise TypeError("decisão de mensagem desconhecida")


def _gravada(
    conn: psycopg.Connection,
    ativo: Ativo,
    evento: EventoMensagem,
    gravada: Gravada,
    *,
    chat_id: str,
    agora: datetime,
    delegacao_externa: bool,
    deps: DepsMensagem,
    fora_de_ordem: bool,
) -> RespostaMensagem:
    gravar_troca(
        conn, ativo.atendimento_id, remetente="cliente", texto=_texto_da_conversa(evento), chaveiro=deps.chaveiro, nomes=(),
        agora=agora, passo_ordem=gravada.ordem, mensagem_em=evento.datetime_post,
    )  # fmt: skip
    registrar_mensagem_do_cliente(conn, ativo.atendimento_id, _quando_do_cliente(evento, agora), relogio=_como_relogio(agora))
    enfileirar = ativo.estado != "repassando"  # repassando grava e NÃO enfileira turno: o chat está trancado para o repasse
    if enfileirar:
        deps.enfileirador.turno(conn, ativo.atendimento_id, chat_id)
    return RespostaMensagem(
        "gravado", atendimento_id=ativo.atendimento_id, ordem=gravada.ordem,
        fora_de_ordem=fora_de_ordem,
        turno_enfileirado=enfileirar, delegacao_externa=delegacao_externa,
    )  # fmt: skip


def _como_relogio(agora: datetime) -> Callable[[], datetime]:
    return lambda: agora
