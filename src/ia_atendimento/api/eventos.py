"""`POST /eventos/chatguru` (corpo nativo, assinado pelo gateway) e `POST /eventos/mensagem` (normalizado, token `ti`): contrato 08
§5.1–§5.3.

Os dois convergem em `mensagens.registrar_mensagem`: mesma `msg_chave`, mesmo `msg_fingerprint`, mesma tabela de respostas. Eventos NÃO
usam 404 nem 409:
sem atendimento ativo é `200 descartado` (nada gravado) e `msg_chave` repetida com outro fingerprint é `200 conflito`, porque o gateway
transforma todo
não-2xx em 424 e o ChatGuru repete (F05). Corpo, texto, URL e `link_chat` não vão a log nem a resposta; a query de `url_arquivo` sai
antes de tudo.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Any, Final, Literal
from urllib.parse import urlsplit

import psycopg
from pydantic import BaseModel, ConfigDict, StringConstraints

from ia_atendimento.api.auth import CREDENCIAL_DE_TESTE, Identidade
from ia_atendimento.api.contexto import ContextoApi
from ia_atendimento.api.erros import ErroApi
from ia_atendimento.api.validacao import erro_de_validacao, validar
from ia_atendimento.estado import TOLERANCIA_RELOGIO, Hex24
from ia_atendimento.evento_mensagem import LIMITE_TEXTO, EventoMensagem, RpaId, TipoMensagem
from ia_atendimento.mensagens import DepsMensagem, RespostaMensagem, atendimento_ativo, registrar_mensagem
from ia_atendimento.tipos import DataHora

log = logging.getLogger(__name__)
TIPOS_NATIVOS: Final[dict[str, str]] = {
    "chat": "texto", "audio": "audio", "ptt": "audio", "image": "imagem", "document": "documento", "sticker": "sticker",
    "location": "localizacao",
}  # fmt: skip
Curto = Annotated[str, StringConstraints(max_length=254)]
Medio = Annotated[str, StringConstraints(max_length=2000)]


class NativoChatguru(BaseModel):
    """O Post nativo já projetado pela allowlist do gateway (01): qualquer outra chave (CPF, celular, token, message_id...) é recusada."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    chat_id: Hex24
    phone_id: Hex24
    tipo_mensagem: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.-]{1,40}$")]
    texto_mensagem: str | None = None  # RG-104: acima de 4000 trunca (o corpo inteiro já é limitado a 64 KB, 413)
    datetime_post: DataHora | None = None
    url_arquivo: Medio | None = None
    responsavel_email: Curto | None = None
    responsavel_nome: Curto | None = None  # descartado sem registro
    executado_por: Curto | None = None  # descartado sem registro
    link_chat: Medio | None = None  # descartado sem registro


class MensagemNormalizada(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    chat_id: Hex24
    phone_id: Hex24
    tipo: TipoMensagem
    texto: str | None = None  # RG-104: acima de 4000 trunca
    url_arquivo: Medio | None = None
    datetime_post: DataHora | None = None
    origem_evento: Literal["webhook", "reconciliacao", "replay"]
    rpa_id: RpaId | None = None


def url_sem_query(url: str | None, campo: str) -> str | None:
    """`esquema://host[:porta]/caminho`: sem query, fragmento nem credencial. Só http/https (senão `422 validacao`, sem ecoar a URL)."""
    if not url:
        return None
    try:
        partes = urlsplit(url)
        host, porta = partes.hostname, partes.port
    except ValueError:  # URL malformada (porta inválida, colchete sem fechar...): 422 direto, sem o texto do ValueError, que cita a URL
        raise erro_de_validacao(((campo, "url_invalida"),)) from None
    if partes.scheme not in ("http", "https") or not host:
        raise erro_de_validacao(((campo, "url_invalida"),))
    return f"{partes.scheme}://{host}{f':{porta}' if porta else ''}{partes.path}"


def truncar(texto: str | None) -> str | None:
    """RG-104 (08 v2.4 §5.1): texto acima de `LIMITE_TEXTO` é truncado, marcado no log (só o tamanho) e segue; nunca 422."""
    if texto is None or len(texto) <= LIMITE_TEXTO:
        return texto
    log.info("texto_mensagem truncado: %d caracteres para %d", len(texto), LIMITE_TEXTO)
    return texto[:LIMITE_TEXTO]


def _evento_de_nativo(dados: NativoChatguru, origem_evento: str, hora: datetime | None) -> EventoMensagem | None:
    """`None` = `chat` sem texto (descartado `texto_vazio`)."""
    tipo = TIPOS_NATIVOS.get(dados.tipo_mensagem, "outro")
    if tipo == "texto" and not (dados.texto_mensagem or "").strip():
        return None
    return EventoMensagem.criar(
        chat_id=dados.chat_id, phone_id=dados.phone_id, tipo=tipo, texto=truncar(dados.texto_mensagem) if tipo == "texto" else None,
        url_arquivo=url_sem_query(dados.url_arquivo, "url_arquivo"), datetime_post=hora, origem_evento=origem_evento,
    )  # fmt: skip


def _evento_de_normalizado(dados: MensagemNormalizada, hora: datetime | None) -> EventoMensagem | None:
    if dados.tipo == "texto" and not (dados.texto or "").strip():
        return None
    return EventoMensagem.criar(
        chat_id=dados.chat_id, phone_id=dados.phone_id, tipo=dados.tipo, texto=truncar(dados.texto) if dados.tipo == "texto" else None,
        url_arquivo=url_sem_query(dados.url_arquivo, "url_arquivo"), datetime_post=hora, origem_evento=dados.origem_evento,
        rpa_id=dados.rpa_id,
    )  # fmt: skip


def _regra_do_canal_de_teste(
    ctx: ContextoApi, conn: psycopg.Connection, identidade: Identidade, chat_id: str, modo_ativo: str | None
) -> None:
    """08 §5.2: a credencial `chatguru-ia-teste` só passa para chat de `chats_teste` e atendimento `teste`; senão 403 ANTES de gravar."""
    if identidade.canal_origem != CREDENCIAL_DE_TESTE:
        return
    if chat_id not in ctx.leitor.valor(conn, "chats_teste") or (modo_ativo is not None and modo_ativo != "teste"):
        ctx.metricas.somar("evento_teste_fora_da_lista")
        raise ErroApi("origem_teste_fora_da_lista", campo="chat_id")


def _delegacao_externa(ctx: ContextoApi, responsavel_email: str | None) -> bool:
    """`responsavel_email` diferente do Amado ⇒ humano na conversa. Ausente, vazio ou só espaço = sem evidência = falso."""
    informado = (responsavel_email or "").strip().lower()  # o ChatGuru manda texto vazio para campo sem valor: vazio = ausente
    return bool(informado) and informado != ctx.settings.responsavel_ia


def _deps(ctx: ContextoApi) -> DepsMensagem:
    return DepsMensagem(
        ctx.chaves_msg, ctx.chaveiro, ctx.enfileirador, ctx.settings.casamento_janela_s, ctx.settings.casamento_janela_sem_hora_s
    )


def _tratar(
    ctx: ContextoApi, identidade: Identidade, chat_id: str, montar: Any, delegacao_externa: bool, agora: datetime, relogio_futuro: bool
) -> tuple[int, dict[str, Any]]:
    evento = montar()  # normaliza ANTES de olhar o atendimento (08 §5.3): a resposta de forma não depende do estado do chat (R2-10)
    with ctx.conexao() as conn:
        ativo = atendimento_ativo(conn, chat_id)
        _regra_do_canal_de_teste(ctx, conn, identidade, chat_id, None if ativo is None else ativo.modo)
        if ativo is None:
            return 200, RespostaMensagem("descartado", motivo="sem_atendimento").corpo()
        if evento is None:
            return 200, RespostaMensagem("descartado", motivo="texto_vazio", atendimento_id=ativo.atendimento_id).corpo()
        resposta = registrar_mensagem(
            conn, evento, chat_id=chat_id, agora=agora, delegacao_externa=delegacao_externa, deps=_deps(ctx), relogio_futuro=relogio_futuro
        )
        if relogio_futuro and resposta.resultado == "gravado":
            ctx.metricas.somar("datetime_post_adiantado")  # alerta do TI: relógio (ou fuso) do ChatGuru/RPA adiantado
        return 200, resposta.corpo()


def _hora_utilizavel(instante: datetime | None, agora: datetime) -> tuple[datetime | None, bool]:
    """`datetime_post` mais de 5 min à frente do relógio da API não é erro de forma: a mensagem é REAL e perdê-la (422 definitivo; o gateway
    vira 424 e o ChatGuru repete 3×) é pior que desconfiar da hora. Vale como AUSENTE (identidade, casamento e dedupe pelo recebimento, como
    `sem_hora`); `msg_enviada_em` guarda o recebimento e o atendimento ganha `relogio_futuro`. Devolve (hora a usar, estava adiantada)."""
    if instante is not None and instante > agora + TOLERANCIA_RELOGIO:
        return None, True
    return instante, False


def evento_chatguru(ctx: ContextoApi, identidade: Identidade, corpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Origem `gateway_chatguru` (assinatura) ⇒ `webhook`; origem `ti` (replay manual, sem `x-gl-*`) ⇒ `replay`."""
    dados = validar(NativoChatguru, corpo, codigo_de_chave_extra="campo_fora_da_allowlist")
    agora = ctx.relogio.agora()
    hora, adiantada = _hora_utilizavel(dados.datetime_post, agora)
    origem_evento = "webhook" if identidade.canal_origem is not None else "replay"
    return _tratar(
        ctx, identidade, dados.chat_id, lambda: _evento_de_nativo(dados, origem_evento, hora),
        _delegacao_externa(ctx, dados.responsavel_email), agora, adiantada,
    )  # fmt: skip


def evento_mensagem(ctx: ContextoApi, identidade: Identidade, corpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Normalizado (o reconciliador do RPA chama a mesma função por dentro): `origem_evento` e `rpa_id` vêm no corpo."""
    dados = validar(MensagemNormalizada, corpo, codigo_de_chave_extra="campo_fora_da_allowlist")
    agora = ctx.relogio.agora()
    hora, adiantada = _hora_utilizavel(dados.datetime_post, agora)
    return _tratar(ctx, identidade, dados.chat_id, lambda: _evento_de_normalizado(dados, hora), False, agora, adiantada)
