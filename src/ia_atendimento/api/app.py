"""A aplicação FastAPI: 13 rotas do contrato 08, autenticação por rota, envelope de erro e log sem corpo.

Cada rota lê o corpo CRU (com limite), autentica, valida (`validacao.py`) e roda a lógica síncrona do módulo da rota numa thread
(`run_in_threadpool`): o psycopg
é síncrono e a lógica fala com o banco. Nenhum erro devolve o valor recebido, e o log só tem `trace_id`, rota (o MOLDE do caminho),
status e duração.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as HTTPExceptionStarlette

from ia_atendimento import estado, scrubber
from ia_atendimento.api import agendamentos, anotacoes, atendimentos, config_rotas, eventos, saude
from ia_atendimento.api.auth import Identidade, autenticar_token, autorizar, tem_cabecalho_do_gateway, verificar_assinatura
from ia_atendimento.api.contexto import ContextoApi
from ia_atendimento.api.erros import ErroApi, resposta_de_erro
from ia_atendimento.api.validacao import erro_de_validacao, objeto_do_corpo
from ia_atendimento.conversa import ChaveForaDoMes

log = logging.getLogger("ia_atendimento.api")
LIMITE_EVENTO = 64 * 1024  # 413 acima disto (08 §1)
LIMITE_CANDIDATOS = 1024 * 1024  # até 200 candidatos de perfil <= 2 KB
LIMITE_PADRAO = 128 * 1024
ORIGENS_ENTRADA = frozenset({"n8n_braco", "robo_esteira"})
ORIGENS_POR_CHAVE = frozenset({"n8n_braco", "vigia", "ti"})
ORIGENS_LEITURA_DE_CONFIG = frozenset({"n8n_braco", "ti", "c360_api", "vigia"})
Logica = Callable[[], tuple[int, dict[str, Any]]]


def _trace_id(request: Request) -> str:
    return str(request.scope.setdefault("trace_id", uuid.uuid4().hex))


async def ler_corpo(request: Request, limite: int) -> bytes:
    """Lê o corpo até `limite` bytes; acima disso `413 payload_grande` (sem ler o resto)."""
    declarado = request.headers.get("content-length", "")
    if declarado.isascii() and declarado.isdigit() and int(declarado) > limite:
        raise ErroApi("payload_grande", detalhe={"limite_bytes": limite})
    pedacos: list[bytes] = []
    total = 0
    async for pedaco in request.stream():
        total += len(pedaco)
        if total > limite:
            raise ErroApi("payload_grande", detalhe={"limite_bytes": limite})
        pedacos.append(pedaco)
    return b"".join(pedacos)


def _ctx(request: Request) -> ContextoApi:
    return request.app.state.ctx  # type: ignore[no-any-return]


def _token(request: Request, permitidas: frozenset[str] | None = None) -> Identidade:
    identidade = autenticar_token(request.headers, _ctx(request).tokens)
    return identidade if permitidas is None else autorizar(identidade, permitidas)


def _evento(request: Request, bruto: bytes, *, aceita_gateway: bool) -> Identidade:
    """Assinatura do gateway (só em `/eventos/chatguru`) ou token `ti`. Se algum `x-gl-*` veio, a assinatura tem de valer: nada de queda
    para o token."""
    ctx = _ctx(request)
    if aceita_gateway and tem_cabecalho_do_gateway(request.headers):
        return verificar_assinatura(request.headers, bruto, ctx.gateway_hmac, ctx.relogio.agora())
    return _token(request, frozenset({"ti"}))


async def _responder(logica: Logica) -> JSONResponse:
    status, corpo = await run_in_threadpool(logica)
    return JSONResponse(corpo, status_code=status)


def _rotas_de_entrada(app: FastAPI) -> None:
    @app.post("/atendimentos")
    async def post_atendimentos(request: Request) -> JSONResponse:
        identidade = _token(request, ORIGENS_ENTRADA)
        corpo = objeto_do_corpo(await ler_corpo(request, LIMITE_PADRAO))
        return await _responder(lambda: atendimentos.criar_atendimento(_ctx(request), identidade.origem, corpo))

    @app.get("/atendimentos/por-chave/{chave}")
    async def get_por_chave(request: Request, chave: str) -> JSONResponse:
        _token(request, ORIGENS_POR_CHAVE)
        return await _responder(lambda: atendimentos.atendimento_por_chave(_ctx(request), chave))

    @app.post("/eventos/chatguru")
    async def post_evento_chatguru(request: Request) -> JSONResponse:
        bruto = await ler_corpo(request, LIMITE_EVENTO)
        identidade = _evento(request, bruto, aceita_gateway=True)
        corpo = objeto_do_corpo(bruto)
        return await _responder(lambda: eventos.evento_chatguru(_ctx(request), identidade, corpo))

    @app.post("/eventos/mensagem")
    async def post_evento_mensagem(request: Request) -> JSONResponse:
        bruto = await ler_corpo(request, LIMITE_EVENTO)
        identidade = _evento(request, bruto, aceita_gateway=False)
        corpo = objeto_do_corpo(bruto)
        return await _responder(lambda: eventos.evento_mensagem(_ctx(request), identidade, corpo))

    @app.post("/agendamentos")
    async def post_agendamentos(request: Request) -> JSONResponse:
        identidade = _token(request, frozenset({"n8n_braco"}))
        corpo = objeto_do_corpo(await ler_corpo(request, LIMITE_PADRAO))
        return await _responder(lambda: agendamentos.criar_agendamento(_ctx(request), identidade.origem, corpo))

    @app.post("/sessoes/{sessao_id}/candidatos")
    async def post_candidatos(request: Request, sessao_id: str) -> JSONResponse:
        _token(request, frozenset({"n8n_braco"}))
        corpo = objeto_do_corpo(await ler_corpo(request, LIMITE_CANDIDATOS))
        return await _responder(lambda: anotacoes.gravar_candidatos(_ctx(request), sessao_id, corpo))

    @app.post("/atendimentos/{atendimento_id}/anotacoes")
    async def post_anotacoes(request: Request, atendimento_id: str) -> JSONResponse:
        _token(request, frozenset({"ti"}))
        corpo = objeto_do_corpo(await ler_corpo(request, LIMITE_PADRAO))
        return await _responder(lambda: anotacoes.criar_anotacao(_ctx(request), atendimento_id, corpo))


def _rotas_de_config_e_saude(app: FastAPI) -> None:
    @app.get("/config")
    async def get_config(request: Request) -> JSONResponse:
        _token(request, ORIGENS_LEITURA_DE_CONFIG)
        return await _responder(lambda: config_rotas.listar_config(_ctx(request)))

    @app.get("/config/{nome}")
    async def get_config_nome(request: Request, nome: str) -> JSONResponse:
        _token(request, ORIGENS_LEITURA_DE_CONFIG)
        historico = request.query_params.get("historico")
        return await _responder(lambda: config_rotas.ler_config(_ctx(request), nome, historico))

    @app.put("/config/{nome}")
    async def put_config(request: Request, nome: str) -> JSONResponse:
        identidade = _token(request, frozenset({"ti", "c360_api"}))
        corpo = objeto_do_corpo(await ler_corpo(request, LIMITE_PADRAO))
        return await _responder(lambda: config_rotas.gravar_config(_ctx(request), identidade.origem, nome, corpo))

    @app.get("/healthz")
    async def get_healthz(request: Request) -> JSONResponse:
        return JSONResponse(saude.healthz(_ctx(request)))

    @app.get("/readyz")
    async def get_readyz(request: Request) -> JSONResponse:
        _token(request)
        return await _responder(lambda: saude.readyz(_ctx(request)))

    @app.get("/saude")
    async def get_saude(request: Request) -> JSONResponse:
        _token(request)
        return await _responder(lambda: saude.saude(_ctx(request)))


def _registrar_tratadores(app: FastAPI) -> None:
    @app.exception_handler(ErroApi)
    async def _erro_api(request: Request, erro: ErroApi) -> JSONResponse:
        request.scope["codigo_de_erro"] = erro.codigo
        return resposta_de_erro(erro, _trace_id(request))

    @app.exception_handler(estado.EntradaInvalida)
    async def _entrada_invalida(request: Request, erro: estado.EntradaInvalida) -> JSONResponse:
        return await _erro_api(request, erro_de_validacao(erro.campos))

    @app.exception_handler(scrubber.EntradaInvalida)
    async def _entrada_sem_eco(request: Request, erro: scrubber.EntradaInvalida) -> JSONResponse:
        campos = tuple((d.split(":", 1)[0].strip() or "(corpo)", "invalido") for d in erro.detalhes)
        return await _erro_api(request, erro_de_validacao(campos))

    @app.exception_handler(RequestValidationError)
    async def _validacao_do_framework(request: Request, erro: RequestValidationError) -> JSONResponse:
        # o handler padrão devolve o `input`: aqui só o caminho do campo e o tipo
        campos = tuple(
            (".".join(str(p) for p in e["loc"]), str(e["type"])) for e in erro.errors(include_input=False, include_context=False)[:20]
        )
        return await _erro_api(request, erro_de_validacao(campos))

    @app.exception_handler(HTTPExceptionStarlette)
    async def _http(request: Request, erro: HTTPExceptionStarlette) -> JSONResponse:
        codigo = "metodo_nao_permitido" if erro.status_code == 405 else "rota_inexistente"
        return await _erro_api(request, ErroApi(codigo))

    @app.exception_handler(psycopg.OperationalError)
    @app.exception_handler(psycopg.InterfaceError)  # conexão fechada pelo pool no meio da requisição
    async def _banco_fora(request: Request, erro: psycopg.Error) -> JSONResponse:
        log.warning("banco indisponível trace=%s tipo=%s", _trace_id(request), type(erro).__name__)
        return await _erro_api(request, ErroApi("nao_pronto"))

    @app.exception_handler(ChaveForaDoMes)
    async def _chave_fora_do_mes(request: Request, erro: ChaveForaDoMes) -> JSONResponse:
        log.critical("alerta ti: chave AES fora do mês; vire CHAVE_AES_ID e reinicie (trace=%s)", _trace_id(request))
        return await _erro_api(request, ErroApi("nao_pronto"))


def _middleware_de_log(app: FastAPI) -> None:
    @app.middleware("http")
    async def com_trace_e_log(request: Request, proxima: Callable[[Request], Awaitable[Response]]) -> Response:
        trace_id = _trace_id(request)
        inicio = time.perf_counter()
        try:
            resposta = await proxima(request)
        except Exception as erro:
            log.error("erro interno trace=%s tipo=%s", trace_id, type(erro).__name__)
            request.scope["codigo_de_erro"] = "erro_interno"
            resposta = resposta_de_erro(ErroApi("erro_interno"), trace_id)
        resposta.headers["x-trace-id"] = trace_id
        rota = getattr(request.scope.get("route"), "path", "(sem rota)")
        log.info(
            "req trace=%s metodo=%s rota=%s status=%s codigo=%s ms=%d", trace_id, request.method, rota, resposta.status_code,
            request.scope.get("codigo_de_erro", "-"), (time.perf_counter() - inicio) * 1000,
        )  # fmt: skip
        return resposta


def criar_app(
    ctx: ContextoApi,
    *,
    ao_iniciar: Callable[[], None] | None = None,
    ao_encerrar: Callable[[], None] | None = None,
) -> FastAPI:
    """App com o contexto injetado. `ao_iniciar`/`ao_encerrar` abrem e fecham o que o contexto usa (pool de conexões, fila)."""

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
        if ao_iniciar is not None:
            await run_in_threadpool(ao_iniciar)
        try:
            yield
        finally:
            if ao_encerrar is not None:
                await run_in_threadpool(ao_encerrar)

    # sem /docs, /redoc nem /openapi.json: o esquema não é público (só /healthz é aberto)
    app = FastAPI(title="ia-atendimento", version=ctx.versao, docs_url=None, redoc_url=None, openapi_url=None, lifespan=ciclo_de_vida)
    app.state.ctx = ctx
    _rotas_de_entrada(app)
    _rotas_de_config_e_saude(app)
    _registrar_tratadores(app)
    _middleware_de_log(app)
    return app
