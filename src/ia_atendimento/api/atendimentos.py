"""`POST /atendimentos` e `GET /atendimentos/por-chave/{chave}` (contrato 08 §3, §4 e §7.5).

Ordem do POST (sp01 T7): forma (422, inclui `pii_no_texto_livre`) → gatilho → coerência da chave → **replay** (200 com o GRAVADO, mesmo
com o chat ocupado e a
chave desligada; outra identidade ⇒ 409) → pré-voo → recusas de config (`bloqueio_entrada` + `janela_24h`) → modo (422) → faixa (422) →
artefatos (503) →
`abrir` sob `pg_advisory_xact_lock` (`abertos_max`, `chat_ocupado`) com o cofre do número do chat e o job `iniciar` NA MESMA transação.
Sem CPF em lugar nenhum: o corpo não tem o campo (`extra=forbid`), o banco não tem a coluna, e `chat_number` só existe cifrado no cofre
`canal`.
"""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal
from typing import Annotated, Any, Final, Literal
from uuid import UUID

import psycopg
from pydantic import Field, StringConstraints

from ia_atendimento import cofre, estado
from ia_atendimento.api.contexto import ContextoApi, PreVooFalhou
from ia_atendimento.api.erros import ErroApi
from ia_atendimento.api.validacao import erro_de_validacao, rejeitar_pii, validar
from ia_atendimento.chave import abertos_agora, bloqueio_entrada, disparos_dia
from ia_atendimento.esforco import faixa_por_comissao
from ia_atendimento.estado import TOLERANCIA_RELOGIO, EntradaAtendimento, ModoInvalido, Resultado
from ia_atendimento.estado_conversa import janela_24h_aberta

CHAVE_DO_CHAT_NUMBER: Final = "chat_number"
TRAVA_ABRIR: Final = "ia_atendimento.abrir"
_CHAVE_POR_CHAVE: Final = re.compile(r"^[a-z][a-z0-9_]{1,19}:[A-Za-z0-9_.:-]{1,180}$")
Faixa = Literal["baixa", "media", "alta", "muito_alta"]


class EntradaApi(EntradaAtendimento):
    """`EntradaAtendimento` (identidade e extras do contrato) mais o que só a API recebe: o número do chat (vai ao cofre) e a
    comissão/faixa a conferir."""

    chave_logica: Annotated[str, StringConstraints(pattern=r"^venda:[0-9a-f]{32}$")]
    chat_number: Annotated[str, StringConstraints(pattern=r"^[0-9]{10,15}$")]
    comissao_esperada_brl: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)] | None = None
    faixa_esforco: Faixa | None = None


def chave_esperada(clt_job_id: Any, chat_id: str) -> str:
    """`venda:` + sha256(`clt_job_id|chat_id`)[:32] (contrato 08 §3)."""
    return "venda:" + hashlib.sha256(f"{clt_job_id}|{chat_id}".encode()).hexdigest()[:32]


def _conferir_forma(entrada: EntradaApi, agora: Any) -> None:
    if entrada.ultimo_cliente_em is not None and entrada.ultimo_cliente_em > agora + TOLERANCIA_RELOGIO:
        raise erro_de_validacao((("ultimo_cliente_em", "no_futuro"),))
    if entrada.motivo_escolha_nota is not None:
        rejeitar_pii("motivo_escolha_nota", entrada.motivo_escolha_nota)
    for nome, valor in entrada.perfil.items():
        if isinstance(valor, str):
            rejeitar_pii(f"perfil.{nome}", valor)
    if entrada.gatilho == "esteira_parada":
        raise ErroApi("gatilho_desabilitado", campo="gatilho")
    if entrada.clt_job_id is not None and entrada.chave_logica != chave_esperada(entrada.clt_job_id, entrada.chat_id):
        raise ErroApi("chave_incoerente", campo="chave_logica")


def _corpo_da_resposta(atendimento: estado.Atendimento, *, repetido: bool) -> dict[str, Any]:
    return {
        "atendimento_id": str(atendimento.atendimento_id), "estado": atendimento.estado, "modo": atendimento.modo,
        "faixa_esforco": atendimento.faixa_esforco, "repetido": repetido, "chatbot_antes": atendimento.chatbot_antes,
    }  # fmt: skip


def _replay(conn: psycopg.Connection, resultado: Resultado) -> tuple[int, dict[str, Any]]:
    return 200, _corpo_da_resposta(estado.ler(conn, resultado.atendimento_id), repetido=True)


def _abertura_possivel(ctx: ContextoApi, entrada: EntradaApi) -> bool:
    """08 §8: `ultimo_cliente_em` DESCONHECIDO aceita (a decisão é do `iniciar`, com a hora de então); conhecido: janela aberta OU
    template aprovado."""
    if entrada.ultimo_cliente_em is None:
        return True
    return janela_24h_aberta(entrada.ultimo_cliente_em, ctx.relogio.agora()) or ctx.template_de_abertura_aprovado()


def modo_do_atendimento(
    ctx: ContextoApi,
    conn: psycopg.Connection,
    *,
    chat_id: str,
    pessoa_id: UUID,
    persona_id: str | None = None,
    modo_pedido: str | None = None,
) -> str:
    """Modo por atendimento (08 §6): `teste` só para chat de `chats_teste` (com pessoa de `pessoas_teste`), senão o global."""
    try:
        modo = estado.resolver_modo(
            chat_id=chat_id, modo_global=ctx.leitor.valor(conn, "modo"), chats_teste=ctx.leitor.valor(conn, "chats_teste"),
            persona_id=persona_id, modo_pedido=modo_pedido,
        )  # fmt: skip
    except ModoInvalido as erro:
        raise ErroApi(erro.codigo, campo="persona_id" if erro.codigo == "persona_fora_de_teste" else "modo") from None
    if modo == "teste" and not ctx.pessoas_teste.contem(pessoa_id):
        raise ErroApi("pessoa_fora_de_pessoas_teste", campo="pessoa_id")
    return modo


def _faixa(ctx: ContextoApi, conn: psycopg.Connection, entrada: EntradaApi) -> tuple[str, Decimal | None]:
    limites = ctx.leitor.valor(conn, "faixas_esforco")["limites_brl"]
    calculada = faixa_por_comissao(entrada.comissao_esperada_brl, limites)
    if entrada.faixa_esforco is not None and entrada.faixa_esforco != calculada:
        raise ErroApi("faixa_incoerente", campo="faixa_esforco")
    return calculada, entrada.comissao_esperada_brl


def _recusas_de_config(ctx: ContextoApi, conn: psycopg.Connection, entrada: EntradaApi) -> None:
    try:
        ctx.pre_voo.verificar()
    except PreVooFalhou as erro:
        raise ErroApi(erro.codigo) from None
    recusa = bloqueio_entrada(conn, ctx.relogio, entrada.pessoa_id, leitor=ctx.leitor, abertura_possivel=_abertura_possivel(ctx, entrada))
    if recusa is not None:
        raise ErroApi(recusa)


def _procurar_replay(conn: psycopg.Connection, origem: str, entrada: EntradaApi) -> estado.Resultado | None:
    try:
        return estado.procurar_replay(conn, origem, entrada)
    except estado.ConflitoIdempotencia:
        raise ErroApi("chave_reutilizada", campo="chave_logica") from None


def criar_atendimento(ctx: ContextoApi, origem: str, corpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    entrada = validar(EntradaApi, corpo)
    _conferir_forma(entrada, ctx.relogio.agora())
    with ctx.conexao() as conn:
        if (anterior := _procurar_replay(conn, origem, entrada)) is not None:
            return _replay(conn, anterior)
        try:
            return _tentar_abrir(ctx, conn, origem, entrada)
        except ErroApi:
            # o gêmeo (retry do n8n) pode ter commitado entre a busca de replay e a recusa: o POST não leva 409 pela própria reserva
            if (anterior := _procurar_replay(conn, origem, entrada)) is not None:
                return _replay(conn, anterior)
            raise


def _tentar_abrir(ctx: ContextoApi, conn: psycopg.Connection, origem: str, entrada: EntradaApi) -> tuple[int, dict[str, Any]]:
    _recusas_de_config(ctx, conn, entrada)
    modo = modo_do_atendimento(
        ctx, conn, chat_id=entrada.chat_id, pessoa_id=entrada.pessoa_id, persona_id=entrada.persona_id, modo_pedido=entrada.modo
    )
    faixa, comissao = _faixa(ctx, conn, entrada)
    try:
        versoes = estado.versoes_vigentes(conn)
    except estado.ArtefatoAusente:
        raise ErroApi("artefatos_ausentes") from None
    return _abrir(ctx, conn, origem, entrada, versoes, modo, faixa, comissao)


def _abrir(
    ctx: ContextoApi,
    conn: psycopg.Connection,
    origem: str,
    entrada: EntradaApi,
    versoes: estado.Versoes,
    modo: str,
    faixa: str,
    comissao: Decimal | None,
) -> tuple[int, dict[str, Any]]:
    agora = ctx.relogio.agora()
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (TRAVA_ABRIR,))  # serializa `abertos_max` entre processos
        if (
            anterior := _procurar_replay(conn, origem, entrada)
        ) is not None:  # o gêmeo que estava na frente da trava já abriu: 200, antes dos tetos
            return _replay(conn, anterior)
        if abertos_agora(conn) >= ctx.leitor.valor(conn, "max_abertos"):
            raise ErroApi("abertos_max")
        if disparos_dia(conn, agora) >= ctx.leitor.valor(conn, "max_disparos_dia"):  # a rampa do dono: conferida AQUI, já serializada
            raise ErroApi("disparos_dia")
        try:
            aberto = estado.abrir(
                conn, origem=origem, entrada=entrada, versoes=versoes, modo_global=ctx.leitor.valor(conn, "modo"),
                chats_teste=ctx.leitor.valor(conn, "chats_teste"), faixa_esforco=faixa, comissao_esperada_brl=comissao,
                relogio=ctx.relogio.agora,
            )  # fmt: skip
        except estado.ChatOcupado:
            raise ErroApi("chat_ocupado", campo="chat_id") from None
        except estado.ConflitoIdempotencia:
            raise ErroApi("chave_reutilizada", campo="chave_logica") from None
        if aberto.repetido:  # perdeu a corrida para a MESMA chave: é replay, e quem venceu já gravou o cofre e enfileirou
            return _replay(conn, aberto)
        cofre.guardar(conn, aberto.atendimento_id, "canal", {CHAVE_DO_CHAT_NUMBER: entrada.chat_number}, chaveiro=ctx.chaveiro, agora=agora)
        ctx.enfileirador.iniciar(conn, aberto.atendimento_id, entrada.chat_id)
    return 201, _corpo_da_resposta(estado.ler(conn, aberto.atendimento_id), repetido=False)


def atendimento_por_chave(ctx: ContextoApi, chave: str) -> tuple[int, dict[str, Any]]:
    """`{"atendimento_id","estado","modo","encerrado"}` do atendimento mais recente com a chave lógica (`venda:…` ou `agendar:…`). Sem PII.
    `{"atendimento_id","estado","modo","encerrado"}` do atendimento mais recente com a chave lógica (`venda:…` ou `agendar:…`). Sem PII."""
    if not _CHAVE_POR_CHAVE.fullmatch(chave):
        raise erro_de_validacao((("chave", "formato_invalido"),))
    with ctx.conexao() as conn:
        linha = conn.execute(
            "SELECT atendimento_id, estado, modo FROM ia.atendimento WHERE chave_logica = %s ORDER BY iniciado_em DESC LIMIT 1", (chave,)
        ).fetchone()
    if linha is None:
        raise ErroApi("atendimento_inexistente", campo="chave")
    return 200, {"atendimento_id": str(linha[0]), "estado": linha[1], "modo": linha[2], "encerrado": linha[1] == "encerrado"}
