"""`POST /agendamentos` (contrato 08 §5.5): o n8n «IA · agendar» manda a mensagem do cliente; a hora vem do extrator determinístico (B5.7a).

Ordem: forma (422) → chave recalculada (`chave_incoerente`) → **replay** (200 `repetido`, ou 409 com outro texto) → `agenda_desligada` →
`ia_desligada` →
`bloqueio_entrada` → `fora_de_janela` → `opt_out` → `agenda_max_dia` → `chat_ocupado` → extrator (sem hora única: `200 agendado:false`,
nada gravado) → modo (422) →
artefatos (503) → reserva (atendimento `reservado` + linha `pendente` + cofre do número do chat, numa transação). O replay vem ANTES das
recusas de config de
propósito: o retry do n8n de uma chamada que já deu certo não pode virar erro porque a agenda foi desligada no meio.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

import psycopg

from ia_atendimento import agendamento as ag
from ia_atendimento import cofre, estado
from ia_atendimento.api.atendimentos import CHAVE_DO_CHAT_NUMBER, TRAVA_ABRIR, modo_do_atendimento
from ia_atendimento.api.contexto import ContextoApi
from ia_atendimento.api.erros import ErroApi
from ia_atendimento.api.validacao import validar
from ia_atendimento.calendario import carregar_calendario
from ia_atendimento.chave import optou_por_sair

CHAVES_DA_AGENDA: Final = ("agenda_janela", "agenda_periodos", "agenda_teto_horas", "calendario_bloqueio")


def _recusa(ctx: ContextoApi, conn: psycopg.Connection, entrada: ag.EntradaAgendamento, agora: datetime) -> str | None:
    """Primeira recusa de config na ordem do contrato (§5.5), ou `None`."""
    cfg = lambda nome: ctx.leitor.valor(conn, nome)  # noqa: E731
    if cfg("agenda_ativa") is not True:
        return "agenda_desligada"
    if cfg("ia_ativa") is not True:
        return "ia_desligada"
    if cfg("bloqueio_entrada") is True:
        return "bloqueio_entrada"
    if not carregar_calendario(cfg("janela_mensagem"), cfg("calendario_bloqueio")).dentro_da_janela(agora):
        return "fora_de_janela"
    if optou_por_sair(conn, entrada.pessoa_id):
        return "opt_out"
    if ag.agendamentos_hoje(conn, agora) >= cfg("agenda_max_dia"):
        return "agenda_max_dia"
    if ag.chat_ocupado(conn, entrada.chat_id):
        return "chat_ocupado"
    return None


def _horario(
    ctx: ContextoApi, conn: psycopg.Connection, entrada: ag.EntradaAgendamento, agora: datetime
) -> tuple[datetime, str] | ag.SemHora:
    config = ag.config_da_agenda({nome: ctx.leitor.valor(conn, nome) for nome in CHAVES_DA_AGENDA})
    ultima = entrada.ultimo_cliente_em or entrada.datetime_post
    return ag.horario_unico(entrada.texto_mensagem, agora, ultima, config)


def criar_agendamento(ctx: ContextoApi, origem: str, corpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    entrada = validar(ag.EntradaAgendamento, corpo)
    agora = ctx.relogio.agora()
    ag.validar_instantes(entrada, agora)
    try:
        chave = ag.validar_chave(entrada)
    except ag.ChaveIncoerente:
        raise ErroApi("chave_incoerente", campo="chave") from None
    hash_do_texto = ag.texto_hash(entrada.texto_mensagem, ctx.chaves_msg.h16)
    with ctx.conexao() as conn:
        try:
            anterior = ag.procurar_replay(conn, chave, hash_do_texto)
        except estado.ConflitoIdempotencia:
            raise ErroApi("chave_reutilizada", campo="chave") from None
        if anterior is not None:
            return 200, anterior.corpo()
        if (recusa := _recusa(ctx, conn, entrada, agora)) is not None:
            raise ErroApi(recusa)
        horario = _horario(ctx, conn, entrada, agora)
        if isinstance(horario, ag.SemHora):
            return 200, {"agendado": False, "motivo": horario.motivo}
        modo_do_atendimento(ctx, conn, chat_id=entrada.chat_id, pessoa_id=entrada.pessoa_id)  # 422 de modo/pessoa de teste, antes de gravar
        return _reservar(ctx, conn, origem, entrada, chave, hash_do_texto, horario, agora)


def _reservar(
    ctx: ContextoApi,
    conn: psycopg.Connection,
    origem: str,
    entrada: ag.EntradaAgendamento,
    chave: str,
    hash_do_texto: str,
    horario: tuple[datetime, str],
    agora: datetime,
) -> tuple[int, dict[str, Any]]:
    try:
        versoes = estado.versoes_vigentes(conn)
    except estado.ArtefatoAusente:
        raise ErroApi("artefatos_ausentes") from None
    quando, confianca = horario
    try:
        with conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (TRAVA_ABRIR,))
            reservado = ag.reservar(
                conn, origem=origem, entrada=entrada, chave_logica=chave, hash_do_texto=hash_do_texto, quando=quando, confianca=confianca,
                versoes=versoes, modo_global=ctx.leitor.valor(conn, "modo"), chats_teste=ctx.leitor.valor(conn, "chats_teste"),
                folga_min=ctx.leitor.valor(conn, "agenda_folga_min"), agora=agora,
            )  # fmt: skip
            if entrada.chat_number is not None:
                cofre.guardar(
                    conn, reservado.atendimento_id, "canal", {CHAVE_DO_CHAT_NUMBER: entrada.chat_number}, chaveiro=ctx.chaveiro, agora=agora
                )
    except estado.ChatOcupado:
        raise ErroApi("chat_ocupado", campo="chat_id") from None
    return 201, reservado.corpo()
