"""Apoio dos testes da B1.4 (contexto, agente, observabilidade): settings sintéticas, provedor simulado na rede, atendimento aberto.

Tudo sintético e SEM rede: o "Fireworks" é um `httpx.MockTransport`; chaves e CPF/telefone/e-mail de mentira (`000.000.0nn`, `exemplo.test`).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import psycopg

from ia_atendimento.agente import ModeloDaFaixa, ProvedorFalso, criar_agente
from ia_atendimento.cifra import Chaveiro
from ia_atendimento.config import Settings
from ia_atendimento.contexto import Contexto, Insumos, construir
from ia_atendimento.conversa import gravar_troca
from ia_atendimento.estado import Versoes, abrir, iniciar, ler
from ia_atendimento.estado_conversa import EstadoConversa, gravar_estado_conversa, registrar_mensagem_do_cliente
from ia_atendimento.evento_mensagem import ChavesDeMensagem, EventoMensagem
from ia_atendimento.linha_tempo import Gravada, Pendente, gravar_mensagem_recebida, mensagens_pendentes
from ia_atendimento.modulos_fase import esquemas_das_ferramentas, modulo_da_fase
from ia_atendimento.tokens import ESTIMADOR_PADRAO
from tests.apoio_b12 import AGORA
from tests.estado_apoio import RelogioFalso, entrada

CHAVE_DA_API = "fw_chave-da-api-descartavel-0001"  # tem «descartavel»: a varredura a isenta
CPF = "000.000.012-34"  # faixa sintética do corpus
TELEFONE = "(11) 91234-5678"
EMAIL = "fulano@exemplo.test"
NOME_DO_CLIENTE = "Maria Alvardel"
CHAVES = ChavesDeMensagem(h16=b"chave-h16-de-teste-descartavel-01", fingerprint=b"chave-fingerprint-de-teste-descartavel-01")
MODELO = ModeloDaFaixa("deepseek-v4p1-flash-1017", "fireworks-us", False, Decimal("2.0"))
URL_DO_PROVEDOR = "https://us.api.fireworks.ai/inference/v1/chat/completions"


def settings_de_teste(**mudar: Any) -> Settings:
    base: dict[str, Any] = {
        "database_url": "postgresql://ia_app_a:senha-descartavel-0001@127.0.0.1:5434/ia_atendimento",
        "modelo_api_key_1": CHAVE_DA_API,
        "api_token": "token-da-api-descartavel-0001",
        "chave_aes_id": 2,
        "chave_aes_arquivo": "/tmp/nao-existe.json",
        "chave_h16": "h16-chave-hmac-de-teste-descartavel-0123456789",
        "chave_fingerprint": "fp-chave-hmac-de-teste-descartavel-0123456789",
    }
    return Settings(_env_file=None, **{**base, **mudar})  # type: ignore[call-arg]


# --- provedor simulado na rede ----------------------------------------------------------------------------------------------------------


def resposta_openai(
    turno: Mapping[str, Any] | None,
    *,
    entrada: int = 1200,
    em_cache: int = 0,
    saida: int = 90,
    tokens_raciocinio: int = 0,
    conteudo_de_raciocinio: str | None = None,
    sem_uso: bool = False,
) -> httpx.Response:
    """Resposta de `chat/completions` com a ferramenta de saída `final_result` (o `Turno`) e o `usage` pedido."""
    mensagem: dict[str, Any] = {"role": "assistant", "content": None}
    if turno is not None:
        mensagem["tool_calls"] = [
            {"id": "call_1", "type": "function", "function": {"name": "final_result", "arguments": json.dumps(turno)}}
        ]
    if conteudo_de_raciocinio is not None:
        mensagem["reasoning_content"] = conteudo_de_raciocinio
    uso: dict[str, Any] = {"prompt_tokens": entrada, "completion_tokens": saida, "total_tokens": entrada + saida}
    uso["prompt_tokens_details"] = {"cached_tokens": em_cache}
    uso["completion_tokens_details"] = {"reasoning_tokens": tokens_raciocinio}
    corpo = {
        "id": "chatcmpl-descartavel",
        "object": "chat.completion",
        "created": 1_700_000_000,
        "model": "accounts/fireworks/routers/deepseek-v4p1-flash-1017-us",
        "choices": [{"index": 0, "message": mensagem, "finish_reason": "tool_calls" if turno is not None else "stop"}],
        "usage": None if sem_uso else uso,
    }
    return httpx.Response(200, json=corpo)


@dataclass
class RedeSimulada:
    """O 'Fireworks' dos testes: guarda cada requisição (corpo JSON e cabeçalhos) e responde com o que o teste mandar."""

    respostas: list[Callable[[httpx.Request], httpx.Response] | httpx.Response] = field(default_factory=list)
    requisicoes: list[httpx.Request] = field(default_factory=list)
    corpos: list[dict[str, Any]] = field(default_factory=list)

    def handler(self, requisicao: httpx.Request) -> httpx.Response:
        self.requisicoes.append(requisicao)
        self.corpos.append(json.loads(requisicao.content) if requisicao.content else {})
        item = self.respostas[min(len(self.requisicoes), len(self.respostas)) - 1]
        return item(requisicao) if callable(item) else item

    def cliente(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


TURNO_E2 = {"intencao": "saudacao", "acao": "responder", "confianca": "alta", "sinal": "positivo", "motivo": "cliente cumprimentou"}


def agente_na_rede(rede: RedeSimulada, **opcoes: Any):
    from ia_atendimento.agente import ResolvedorModelo

    settings = opcoes.pop("settings", None) or settings_de_teste()
    return criar_agente(ResolvedorModelo(settings, cliente_http=rede.cliente()), MODELO, settings=settings, **opcoes)


def contexto_falso(
    fase: str, *, pendentes: tuple[str, ...] = (), referencias: Mapping[str, str] | None = None, estado: str | None = None
) -> Contexto:
    """`Contexto` de verdade (os mesmos 8 blocos) sem banco: `executar_turno` só aceita o que `contexto.construir` monta.

    As `pendentes` entram COMO ESTÃO (sem a proteção de `montar_contexto`): é assim que um teste simula um vazamento que escapou das cercas."""
    insumos = Insumos(
        fase,
        estado or json.dumps({"fase": fase}, separators=(",", ":")),
        modulo_da_fase(fase),
        esquemas_das_ferramentas(fase),
        (),
        None,
        (),
        "",
        tuple(pendentes),  # type: ignore[arg-type]
    )
    return construir(insumos, dict(referencias or {}), ESTIMADOR_PADRAO)


def agente_falso(roteiro, **opcoes: Any):
    falso = ProvedorFalso(roteiro, **opcoes)
    return criar_agente(falso, MODELO), falso


# --- atendimento aberto com conversa -----------------------------------------------------------------------------------------------------


def abrir_em(
    conn: psycopg.Connection,
    relogio: RelogioFalso,
    versoes: Versoes,
    *,
    fase: str = "E2",
    perfil: dict[str, Any] | None = None,
    **estado: Any,
) -> tuple[uuid.UUID, int]:
    """Atendimento `aberto` na `fase` (pelas transições de verdade: `abrir` → `iniciar` → `gravar_estado_conversa`)."""
    # chave lógica e chat PRÓPRIOS: `abrir` é idempotente por chave e o chat só admite um atendimento não encerrado
    corpo = {
        "chave_logica": f"venda:{uuid.uuid4().hex}",
        "chat_id": uuid.uuid4().hex[:24],
        **({"perfil": perfil} if perfil is not None else {}),
    }
    resultado = abrir(
        conn, origem="n8n_braco", entrada=entrada(**corpo), versoes=versoes, modo_global="duble", chats_teste=frozenset(),
        faixa_esforco="media", comissao_esperada_brl=None, relogio=relogio,
    )  # fmt: skip
    versao = iniciar(
        conn, resultado.atendimento_id, resultado.versao, chatbot_antes="desligado", chatbot_estado="desligado_pela_ia", relogio=relogio
    )
    versao = gravar_estado_conversa(conn, resultado.atendimento_id, versao, EstadoConversa(fase=fase, **estado), relogio=relogio)  # type: ignore[arg-type]
    registrar_mensagem_do_cliente(conn, resultado.atendimento_id, relogio(), relogio=relogio)
    return resultado.atendimento_id, versao


def _evento(conn: psycopg.Connection, atendimento_id: uuid.UUID, em: datetime, **campos: Any) -> EventoMensagem:
    """Evento do chat DO atendimento (cada atendimento dos testes tem o seu)."""
    atendimento = ler(conn, atendimento_id)
    return EventoMensagem(
        chat_id=atendimento.chat_id,
        phone_id=atendimento.phone_id,
        datetime_post=em.astimezone(UTC).isoformat(),
        origem_evento="webhook",
        **campos,
    )  # type: ignore[arg-type]


def receber(
    conn: psycopg.Connection,
    atendimento_id: uuid.UUID,
    chaveiro: Chaveiro,
    texto: str,
    *,
    nomes: tuple[str, ...] = (),
    em: datetime = AGORA,
    id_externo: str | None = None,
) -> Pendente:
    """A mensagem do cliente como a B1.5 a gravaria: passo `mensagem_recebida` + o texto mascarado e cifrado na conversa."""
    evento = _evento(conn, atendimento_id, em, tipo="texto", texto=texto, **({"mensagem_id": id_externo} if id_externo else {}))
    gravada = gravar_mensagem_recebida(conn, atendimento_id, evento=evento, chaves=CHAVES)
    assert isinstance(gravada, Gravada)
    gravar_troca(
        conn, atendimento_id, remetente="cliente", texto=texto, chaveiro=chaveiro, nomes=nomes, agora=em, passo_ordem=gravada.ordem
    )
    return next(p for p in mensagens_pendentes(conn, atendimento_id) if p.ordem == gravada.ordem)


def resposta_da_ia(
    conn: psycopg.Connection, atendimento_id: uuid.UUID, chaveiro: Chaveiro, texto: str, *, nomes: tuple[str, ...] = ()
) -> None:
    gravar_troca(conn, atendimento_id, remetente="ia", texto=texto, chaveiro=chaveiro, nomes=nomes, agora=AGORA)


def receber_midia(conn: psycopg.Connection, atendimento_id: uuid.UUID, tipo: str = "audio", *, em: datetime = AGORA) -> Pendente:
    """Áudio, imagem...: vira passo `mensagem_recebida` sem linha na conversa (o texto não existe)."""
    evento = _evento(conn, atendimento_id, em, tipo=tipo, url_arquivo="https://exemplo.test/arquivo")
    gravada = gravar_mensagem_recebida(conn, atendimento_id, evento=evento, chaves=CHAVES)
    assert isinstance(gravada, Gravada)
    return next(p for p in mensagens_pendentes(conn, atendimento_id) if p.ordem == gravada.ordem)


def receber_sem_linha_na_conversa(
    conn: psycopg.Connection, atendimento_id: uuid.UUID, texto: str = "texto que sumiu", *, em: datetime = AGORA
) -> Pendente:
    """Passo `mensagem_recebida` de texto SEM a linha cifrada na conversa (poda ou falha): o contexto tem de dizer «indisponível»."""
    evento = _evento(conn, atendimento_id, em, tipo="texto", texto=texto)
    gravada = gravar_mensagem_recebida(conn, atendimento_id, evento=evento, chaves=CHAVES)
    assert isinstance(gravada, Gravada)
    return next(p for p in mensagens_pendentes(conn, atendimento_id) if p.ordem == gravada.ordem)


def receber_cru(conn: psycopg.Connection, atendimento_id: uuid.UUID, chaveiro: Chaveiro, texto: str, *, em: datetime = AGORA) -> Pendente:
    """Como `receber`, mas grava o texto SEM a máscara (linha legada ou bug): simula o que só a proteção do contexto e o portão final seguram."""
    from ia_atendimento.conversa import _gravar

    evento = _evento(conn, atendimento_id, em, tipo="texto", texto="mensagem")  # o passo leva só tamanho e chaves, nunca o texto
    gravada = gravar_mensagem_recebida(conn, atendimento_id, evento=evento, chaves=CHAVES)
    assert isinstance(gravada, Gravada)
    _gravar(conn, atendimento_id, remetente="cliente", tipo="mensagem", texto=texto, agora=em, chaveiro=chaveiro, passo_ordem=gravada.ordem)
    return next(p for p in mensagens_pendentes(conn, atendimento_id) if p.ordem == gravada.ordem)
