"""Jobs da pausa combinada (B5.7b, estudo M §2.5, §2.7 e §3): `retomar` e `reaper_agenda`. Handlers sem Procrastinate (a fila é `fila.py`).

**O relógio é o Procrastinate** (`schedule_at = dispara_em`), nunca o `send_date` do ChatGuru (não cancela, não revalida, não reentra).

- **Alarme + job de verdade** (como o lembrete, R2-01): o agendado para daqui a horas NÃO leva `lock`. Um `todo` com `lock=chat:` segura
  TODO job posterior do chat, e a mensagem do cliente que chega na pausa ficaria sem turno até a hora combinada. Ao disparar, o alarme
  enfileira o `retomar` com o lock do chat. `queueing_lock` do alarme: `retomar:{agendamento_id}`; do job de verdade:
  `retomar_exec:{agendamento_id}`. É por agendamento (não por atendimento) para que o reagendamento (`seq` 2, outro `dispara_em`) não tenha
  o alarme engolido pelo do `seq` 1, ainda `todo`.
- **Quem ganha o CAS `confirmado → disparado` é o único que fala com o cliente.** O `retomar` reivindica a linha (uma transação: lê com
  `FOR UPDATE`, confere, `disparar`, passo `disparado`) e só então chama `Servicos.retomar_atendimento` (a volta da B5.7c: pré-checagens,
  `sair_da_pausa` ou `iniciar_agendado`, mensagem). Duplicata (alarme + reaper, reexecução) acha `disparado` e não faz nada. Sem retry: a
  reivindicação não é reentrante. Se a volta falhar DEPOIS dela, o lease do `pausado`/`reservado` (retoma_em + 30 min) vence e o
  `reaper_lease` devolve o lead (`retomada_perdida`).
- **`reaper_agenda`** (por minuto): `confirmado` com `dispara_em` vencido, atendimento ainda à espera (`pausado`, ou `reservado` de
  agendamento) e **sem job vivo** (`todo`, ou `doing` de worker com batimento) ⇒ enfileira o `retomar` de verdade. É a rede de quem perdeu o
  job na queda do worker. Um `doing` de worker MORTO é dado como `failed` antes (`Vencido.travados`): ele segue segurando o `lock=chat:` e o
  novo job nunca sairia da fila.
- **Teto de atraso (R1-03):** o lease do atendimento é `dispara_em + folga`. Depois dele o `retomar` NÃO entrega a volta (a hora combinada
  já passou; a janela de 08:30–19:00 e as 24 h do WhatsApp podem ter estourado): marca o agendamento `expirado` e deixa o lead para o
  `reaper_lease` (`retomada_perdida`), que o devolve ao humano. Quem chega primeiro (este job ou o `reaper_lease`) decide; o outro desiste.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Literal

import psycopg

from ia_atendimento import agenda_estado as ae
from ia_atendimento.estado_erros import ConflitoVersao, TransicaoInvalida
from ia_atendimento.jobs import LIMITE_LOTE, ServicoNaoConfigurado, Servicos, Volta, configurado
from ia_atendimento.prontidao import HEARTBEAT_MAX_S

PREFIXO_ALARME: Final = "retomar:"
PREFIXO_EXEC: Final = "retomar_exec:"
FOLGA_REARME: Final = timedelta(
    seconds=5
)  # o alarme `cedo` nunca volta antes de agora + 5 s (relógio da app atrasado não vira laço quente)
Codigo = Literal["disparado", "inexistente", "nao_confirmado", "fora_do_estado", "cedo", "expirado", "perdeu"]


@dataclass(frozen=True)
class Reivindicacao:
    """O que a reivindicação concluiu. Só `disparado` leva a `volta`; `cedo` leva o `dispara_em` para o alarme se rearmar."""

    codigo: Codigo
    volta: Volta | None = None
    dispara_em: datetime | None = None


def _esperando_a_volta(entrada: str, estado: str, gatilho: str) -> bool:
    """O atendimento ainda espera a volta combinada: (a) `pausado`, ou (b) `reservado` de agendamento que não tocou o chat."""
    return (entrada == "pausa_ia" and estado == "pausado") or (
        entrada == "dialogo_agendar" and estado == "reservado" and gatilho == "agendamento"
    )


def _reivindicar(servicos: Servicos, agendamento_id: uuid.UUID, agora: datetime, job_id: int | None) -> Reivindicacao:
    with servicos.abrir_conexao() as conn, conn.transaction():
        # ordem de locks: atendimento, depois agendamento (a mesma da API e da B5.7c); o CAS por `versao` continua sendo a prova
        dono = conn.execute(
            "SELECT a.atendimento_id, a.estado, a.gatilho, a.chat_id, a.lease_ate FROM ia.atendimento a"
            " WHERE a.atendimento_id = (SELECT atendimento_id FROM ia.agendamento WHERE agendamento_id = %s) FOR UPDATE",
            (agendamento_id,),
        ).fetchone()
        if dono is None:
            return Reivindicacao("inexistente")
        atendimento_id, estado, gatilho, chat_id, lease_ate = dono
        linha = ae.ler_agendamento(conn, agendamento_id, travar=True)
        if linha.estado != "confirmado" or linha.dispara_em is None:
            return Reivindicacao("nao_confirmado")  # pendente (a confirmação ainda não veio), ou já disparado/cancelado/expirado
        if not _esperando_a_volta(linha.entrada, estado, gatilho):
            ae.cancelar(conn, agendamento_id, linha.versao, por="sistema", agora=agora)
            ae.passo_de_agendamento(conn, atendimento_id, agendamento_id, "cancelado")
            return Reivindicacao("fora_do_estado")  # alguém tirou o atendimento da espera: não se fala com o cliente
        if linha.dispara_em > agora:
            return Reivindicacao("cedo", dispara_em=linha.dispara_em)
        # teto de atraso (R1-03): o lease é `dispara_em + folga`; passou dele, quem decide é a vigia
        if lease_ate is not None and agora > lease_ate:
            ae.expirar(conn, agendamento_id, linha.versao, agora=agora)
            ae.passo_de_agendamento(conn, atendimento_id, agendamento_id, "expirado")
            return Reivindicacao("expirado")
        try:
            ae.disparar(conn, agendamento_id, linha.versao, agora=agora, job_id=job_id)
        except (ConflitoVersao, TransicaoInvalida):
            return Reivindicacao("perdeu")
        ae.passo_de_agendamento(conn, atendimento_id, agendamento_id, "disparado")
        volta = Volta(agendamento_id, atendimento_id, chat_id, linha.entrada, linha.retoma_fase, linha.dispara_em)
        return Reivindicacao("disparado", volta=volta)


def _registrar_desfecho(servicos: Servicos, volta: Volta, desfecho: ae.Desfecho) -> None:
    with servicos.abrir_conexao() as conn, conn.transaction():
        ae.registrar_desfecho(conn, volta.agendamento_id, desfecho, agora=servicos.relogio.agora())
        if desfecho == "resolvido":
            ae.passo_de_agendamento(conn, volta.atendimento_id, volta.agendamento_id, "resolvido")


def atraso_do_rearme(dispara_em: datetime, agora: datetime) -> float:
    """Segundos até o alarme `cedo` voltar: `max(dispara_em, agora + 5 s) - agora`, no relógio da APLICAÇÃO (R1-04).

    O alarme dispara pelo `now()` do banco e a conferência é pelo relógio da aplicação. Se este atrasa, `dispara_em` já é passado para o
    banco, e rearmar PARA `dispara_em` faria o job voltar na hora, em laço (277 jobs em 3 s com 2 s de atraso). O relativo converge."""
    return (max(dispara_em, agora + FOLGA_REARME) - agora).total_seconds()


async def executar_retomar(
    servicos: Servicos, agendamento_id: uuid.UUID, reagendar: Callable[[float], Awaitable[None]], *, job_id: int | None = None
) -> Codigo:
    """O job `retomar`: reivindica o agendamento e, se ganhou, entrega a volta ao serviço. `cedo` (o alarme chegou antes do `dispara_em`
    pelo relógio da aplicação) rearma o alarme com atraso RELATIVO (`atraso_do_rearme`), como o lembrete adiado."""
    if not configurado(
        servicos.retomar_atendimento
    ):  # sem a volta para entregar, reivindicar seria perder o agendamento: falha ANTES do CAS
        raise ServicoNaoConfigurado("serviço 'retomar_atendimento' não foi injetado (Servicos): o agendamento fica confirmado")
    agora = servicos.relogio.agora()
    r = await asyncio.to_thread(_reivindicar, servicos, agendamento_id, agora, job_id)
    if r.codigo == "cedo" and r.dispara_em is not None:
        await reagendar(atraso_do_rearme(r.dispara_em, agora))
    if r.volta is not None:
        desfecho = await servicos.retomar_atendimento(r.volta)
        if desfecho not in (None, "retomou"):
            await asyncio.to_thread(_registrar_desfecho, servicos, r.volta, desfecho)
    return r.codigo


# --- reaper_agenda ----------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Vencido:
    agendamento_id: uuid.UUID
    atendimento_id: uuid.UUID
    chat_id: str
    dispara_em: datetime
    travados: tuple[int, ...] = ()  # jobs `doing` deste agendamento cujo worker morreu (sem batimento): a fila deve dá-los como falhos


# job vivo = `todo` (alarme ou job de verdade esperando) ou `doing` de worker com batimento; `doing` de worker morto (queda) não conta
_SQL_VENCIDOS: Final = """
SELECT g.agendamento_id, g.atendimento_id, g.chat_id, g.dispara_em,
  array(SELECT j.id FROM procrastinate.procrastinate_jobs j LEFT JOIN procrastinate.procrastinate_workers w ON w.id = j.worker_id
        WHERE j.queueing_lock IN (%(alarme)s || g.agendamento_id::text, %(exec)s || g.agendamento_id::text) AND j.status = 'doing'
          AND (w.last_heartbeat IS NULL OR w.last_heartbeat < now() - make_interval(secs => %(batimento)s)) ORDER BY j.id) AS travados
FROM ia.agendamento g
JOIN ia.atendimento a ON a.atendimento_id = g.atendimento_id
WHERE g.estado = 'confirmado' AND g.dispara_em <= %(agora)s
  AND ((g.entrada = 'pausa_ia' AND a.estado = 'pausado')
       OR (g.entrada = 'dialogo_agendar' AND a.estado = 'reservado' AND a.gatilho = 'agendamento'))
  AND NOT EXISTS (
    SELECT 1 FROM procrastinate.procrastinate_jobs j LEFT JOIN procrastinate.procrastinate_workers w ON w.id = j.worker_id
    WHERE j.queueing_lock IN (%(alarme)s || g.agendamento_id::text, %(exec)s || g.agendamento_id::text)
      AND (j.status = 'todo' OR (j.status = 'doing' AND w.last_heartbeat >= now() - make_interval(secs => %(batimento)s))))
ORDER BY g.dispara_em LIMIT %(limite)s
"""  # fmt: skip


def selecionar_vencidos(conn: psycopg.Connection, agora: datetime, limite: int = LIMITE_LOTE) -> list[Vencido]:
    """`confirmado` vencido, ainda à espera e sem job vivo: o que a queda do worker (ou um job que falhou antes de reivindicar) deixou."""
    params = {"agora": agora, "alarme": PREFIXO_ALARME, "exec": PREFIXO_EXEC, "batimento": HEARTBEAT_MAX_S, "limite": limite}
    return [Vencido(*r[:4], tuple(r[4])) for r in conn.execute(_SQL_VENCIDOS, params)]


def _vencidos(servicos: Servicos) -> list[Vencido]:
    with servicos.abrir_conexao() as conn:
        return selecionar_vencidos(conn, servicos.relogio.agora())


async def executar_reaper_agenda(servicos: Servicos, enfileirar: Callable[[Vencido], Awaitable[None]]) -> int:
    """Enfileira o `retomar` de verdade de cada vencido (idempotente por `queueing_lock`). Devolve quantos pediu."""
    vencidos = await asyncio.to_thread(_vencidos, servicos)
    for vencido in vencidos:
        await enfileirar(vencido)
    return len(vencidos)
