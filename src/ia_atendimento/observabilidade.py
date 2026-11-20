"""Observabilidade (B1.4, sp01 T6): OpenTelemetry → Phoenix, com a máscara de PII na saída de TUDO que sai do processo.

- **Desligada por padrão.** Sem `PHOENIX_ENDPOINT` (e sem exportador injetado) `configurar` não cria provedor, não instrumenta e não
  faz rede:
  é assim nos testes. Com endpoint, os spans vão por OTLP/HTTP (`<endpoint>/v1/traces`) em lote.
- **O pydantic-ai emite os spans** (`InstrumentationSettings`, por agente: nada de estado global do Pydantic AI); o
  `OpenInferenceSpanProcessor` os enriquece com os atributos que o Phoenix lê. O pacote `openinference-instrumentation-pydantic-ai` 0.1.x
  não traz mais o `PydanticAIInstrumentor` do plano: traz esse processador.
- **O scrubber é o ÚLTIMO elo**, um exportador que embrulha o de verdade: roda depois de todo processador (inclusive do OpenInference,
  que copia
  o conteúdo das mensagens para atributos próprios) e passa `mascarar()` em nome, atributos (texto e listas), eventos (a exceção e seu
  traceback
  entram aqui), status e na descrição. Um CPF, telefone ou e-mail que chegasse ao prompt por engano NÃO sai do processo.
- **Logs:** `instalar_filtro_de_logs` troca a fábrica de `LogRecord` para mascarar a mensagem, os argumentos e o traceback de todo registro
  (do `openai`, do `httpx` e do nosso), qualquer que seja o handler.
- **Segredos:** `registrar_segredo` (a chave do provedor, a do Phoenix) faz o scrubber e o filtro trocarem o valor literal por `[SEGREDO]`.
- **Raciocínio:** se a resposta do modelo trouxer tokens de raciocínio (o V4.1 Flash deve rodar sem; G §7) o turno ainda vale, mas
  `alertar_raciocinio` registra o alerta `alerta_raciocinio` em log e no span, para o custo e a latência não subirem calados.
"""

from __future__ import annotations

import json
import logging
import threading
import traceback
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Final
from urllib.parse import urlsplit

from openinference.instrumentation.pydantic_ai import OpenInferenceSpanProcessor
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Link, Span, Status, StatusCode, Tracer
from pydantic import SecretStr
from pydantic_ai.models.instrumented import InstrumentationSettings

from ia_atendimento.config import Settings
from ia_atendimento.mascara import mascarar

ALERTA_RACIOCINIO: Final = "alerta_raciocinio"
ALERTA_USO_AUSENTE: Final = "alerta_uso_ausente"
NOME_DO_TRACER: Final = "ia_atendimento"
SPAN_DO_TURNO: Final = "ia.turno"
SPAN_DA_FERRAMENTA: Final = "ia.ferramenta"
TRACE_ID_NULO: Final = "0" * 32
SEGREDO: Final = "[SEGREDO]"
TAMANHO_MIN_SEGREDO: Final = 8  # abaixo disso o valor casaria com texto comum
CAMINHO_OTLP: Final = "/v1/traces"
TIMEOUT_EXPORTACAO_S: Final = 10

registro = logging.getLogger("ia_atendimento.observabilidade")
_segredos: frozenset[str] = frozenset()
_trava = threading.Lock()


# --- máscara ----------------------------------------------------------------------------------------------------------------------------


def registrar_segredo(valor: str | SecretStr | None) -> None:
    """A partir daqui o valor literal nunca sai em span nem em log (vira `[SEGREDO]`). Valor curto demais é ignorado."""
    texto = valor.get_secret_value() if isinstance(valor, SecretStr) else valor
    if texto and len(texto) >= TAMANHO_MIN_SEGREDO:
        global _segredos
        with _trava:
            _segredos = _segredos | {texto}


def registrar_segredos_do_settings(settings: Settings) -> None:
    """Revisão dos altos (M3 de G-0085): todo segredo que o `Settings` carrega sai como `[SEGREDO]`, não só a chave do modelo e a do
    Phoenix. São aleatórios: a máscara de PII não os pegaria. A senha do `DATABASE_URL` entra sozinha (aparece em traceback de driver)."""
    for valor in (
        settings.modelo_api_key_1,
        settings.phoenix_api_key,
        settings.chave_h16,
        settings.chave_fingerprint,
        settings.chat_ref_chave,
    ):
        registrar_segredo(valor)
    for token in settings.api_tokens.values():
        registrar_segredo(token)
    registrar_segredo(urlsplit(settings.database_url.get_secret_value()).password)


def mascarar_texto(texto: str) -> str:
    """`mascarar()` (CPF, telefone, e-mail, CEP, UUID, 8+ dígitos) e depois os segredos registrados."""
    saida = mascarar(texto)
    for segredo in _segredos:
        saida = saida.replace(segredo, SEGREDO)
    return saida


def _limpar_json(texto: str) -> str | None:
    """Atributo que é JSON (o OpenInference e o pydantic-ai gravam mensagens assim): máscara no valor DECODIFICADO, porque no texto escapado
    (`"000\\n000\\n012\\n34"`) o CPF partido por quebra de linha não casa (B-4). `None` = não é JSON."""
    if not texto.lstrip().startswith(("{", "[")):
        return None
    try:
        return json.dumps(_limpar_valor(json.loads(texto)), ensure_ascii=False)
    except ValueError:
        return None


def _limpar_valor(valor: Any) -> Any:
    if isinstance(valor, str):
        em_json = _limpar_json(valor)
        return mascarar_texto(em_json if em_json is not None else valor)
    if isinstance(valor, bytes):
        return mascarar_texto(valor.decode("utf-8", errors="replace"))
    if isinstance(valor, Mapping):
        return {mascarar_texto(str(chave)): _limpar_valor(v) for chave, v in valor.items()}
    if isinstance(valor, Sequence):
        return tuple(_limpar_valor(v) for v in valor)
    return valor


def _limpar_atributos(atributos: Mapping[str, Any] | None) -> dict[str, Any]:
    return {mascarar_texto(str(chave)): _limpar_valor(valor) for chave, valor in (atributos or {}).items()}  # a CHAVE também (B-4)


def copia_mascarada(span: ReadableSpan) -> ReadableSpan:
    """Cópia do span com nome, atributos, eventos e status mascarados. O original (já exportado ou não) não é tocado."""
    status = span.status
    descricao = mascarar_texto(status.description) if status.description else None
    return ReadableSpan(
        name=mascarar_texto(span.name),
        context=span.context,
        parent=span.parent,
        resource=span.resource,
        attributes=_limpar_atributos(span.attributes),
        events=tuple(Event(mascarar_texto(e.name), _limpar_atributos(e.attributes), e.timestamp) for e in span.events),
        links=tuple(Link(lig.context, _limpar_atributos(lig.attributes)) for lig in span.links),
        kind=span.kind,
        status=Status(status.status_code, descricao if status.status_code == StatusCode.ERROR else None),
        start_time=span.start_time,
        end_time=span.end_time,
        instrumentation_scope=span.instrumentation_scope,
    )


class ExportadorMascarado(SpanExporter):
    """Embrulha um exportador: tudo que sai passa por `copia_mascarada`. É o último elo da cadeia de spans."""

    def __init__(self, interno: SpanExporter) -> None:
        self._interno = interno

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return self._interno.export([copia_mascarada(s) for s in spans])

    def shutdown(self) -> None:
        self._interno.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._interno.force_flush(timeout_millis)


# --- logs -------------------------------------------------------------------------------------------------------------------------------


MARCA_DE_LOG_MAL_FORMATADO: Final = "[log mal formatado] "
_avisando: ContextVar[bool] = ContextVar("avisando_log_mal_formatado", default=False)


def _mensagem_do_registro(registro_de_log: logging.LogRecord) -> str:
    """`getMessage()` NUNCA levanta aqui: uma chamada de log mal formatada (`%d` com texto, argumentos a menos) de QUALQUER biblioteca
    derrubaria o chamador, porque a fábrica roda na criação do registro e não no `emit` (onde a stdlib engole o erro). Falhou: vai o
    formato cru e os argumentos, mascarados, com a marca."""
    try:
        return registro_de_log.getMessage()
    except Exception:
        _avisar_log_mal_formatado(registro_de_log.name)
        return f"{MARCA_DE_LOG_MAL_FORMATADO}{registro_de_log.msg!r} {registro_de_log.args!r}"


def _avisar_log_mal_formatado(origem: str) -> None:
    """Um aviso (sem o conteúdo) de que `origem` chamou o log com formato inválido; não recursivo."""
    if _avisando.get():
        return
    marca = _avisando.set(True)
    try:
        registro.warning("chamada de log com formato inválido em %s; mensagem preservada e mascarada", origem)
    finally:
        _avisando.reset(marca)


def _mascarar_registro(registro_de_log: logging.LogRecord) -> logging.LogRecord:
    """Mensagem já formatada, argumentos, traceback e pilha mascarados, no próprio registro (vale para todo handler). Nunca levanta."""
    registro_de_log.msg = mascarar_texto(_mensagem_do_registro(registro_de_log))
    registro_de_log.args = ()
    try:
        if registro_de_log.exc_info and registro_de_log.exc_info[1] is not None:
            registro_de_log.exc_text = mascarar_texto("".join(traceback.format_exception(*registro_de_log.exc_info)))
        elif registro_de_log.exc_text:
            registro_de_log.exc_text = mascarar_texto(registro_de_log.exc_text)
        if registro_de_log.stack_info:
            registro_de_log.stack_info = mascarar_texto(registro_de_log.stack_info)
    except Exception:
        registro_de_log.exc_info, registro_de_log.exc_text, registro_de_log.stack_info = None, "[traceback indisponível]", None
    return registro_de_log


class FiltroSemPii(logging.Filter):
    """Para quem prefere pendurar a máscara num handler específico em vez de trocar a fábrica global."""

    def filter(self, record: logging.LogRecord) -> bool:
        _mascarar_registro(record)
        return True


_fabrica_original: Callable[..., logging.LogRecord] | None = None


def instalar_filtro_de_logs() -> None:
    """Idempotente. Toda mensagem de log do processo passa a sair mascarada."""
    global _fabrica_original
    with _trava:
        if _fabrica_original is not None:
            return
        _fabrica_original = logging.getLogRecordFactory()
        original = _fabrica_original

        def fabrica(*args: Any, **kwargs: Any) -> logging.LogRecord:
            return _mascarar_registro(original(*args, **kwargs))

        logging.setLogRecordFactory(fabrica)


def desinstalar_filtro_de_logs() -> None:
    global _fabrica_original
    with _trava:
        if _fabrica_original is not None:
            logging.setLogRecordFactory(_fabrica_original)
            _fabrica_original = None


# --- OpenTelemetry ----------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Observabilidade:
    """O que `configurar` montou. `instrumentacao` é o que o agente usa (`agente.instrument = ...`); `None` = desligada."""

    ativa: bool
    provedor: TracerProvider | None = None
    instrumentacao: InstrumentationSettings | None = None

    def encerrar(self) -> None:
        """Esvazia a fila e desliga o provedor (no fim do processo; nos testes, no fim do teste)."""
        if self.provedor is not None:
            self.provedor.shutdown()


_DESLIGADA: Final = Observabilidade(ativa=False)
_atual: Observabilidade = _DESLIGADA
_tracer: Tracer | None = None


def _exportador_otlp(settings: Settings) -> SpanExporter:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    endpoint = str(settings.phoenix_endpoint).rstrip("/")
    if not endpoint.endswith(CAMINHO_OTLP):
        endpoint += CAMINHO_OTLP
    chave = settings.phoenix_api_key.get_secret_value() if settings.phoenix_api_key else None
    return OTLPSpanExporter(
        endpoint=endpoint, headers={"authorization": f"Bearer {chave}"} if chave else None, timeout=TIMEOUT_EXPORTACAO_S
    )


def configurar(settings: Settings, *, exportador: SpanExporter | None = None, incluir_conteudo: bool = True) -> Observabilidade:
    """Monta o `TracerProvider` com a cadeia `OpenInference → scrubber → exportador`. Sem endpoint e sem `exportador`, fica desligada.

    `exportador` (em memória, nos testes) usa processamento síncrono; o OTLP usa lote. O conteúdo das mensagens vai nos spans já mascarado
    (`incluir_conteudo=False` o tira de vez). Segredos do `Settings` são registrados para sair como `[SEGREDO]`."""
    global _atual, _tracer
    _atual.encerrar()  # `configurar` duas vezes não deixa a thread do `BatchSpanProcessor` do provedor anterior vazar (B-8)
    registrar_segredos_do_settings(settings)
    instalar_filtro_de_logs()
    if exportador is None and not settings.phoenix_endpoint:
        _atual, _tracer = _DESLIGADA, None
        return _DESLIGADA
    mascarado = ExportadorMascarado(exportador if exportador is not None else _exportador_otlp(settings))
    provedor = TracerProvider(
        resource=Resource.create({"service.name": NOME_DO_TRACER, "openinference.project.name": settings.phoenix_projeto})
    )
    provedor.add_span_processor(OpenInferenceSpanProcessor())
    provedor.add_span_processor(SimpleSpanProcessor(mascarado) if exportador is not None else BatchSpanProcessor(mascarado))
    _atual = Observabilidade(True, provedor, InstrumentationSettings(tracer_provider=provedor, include_content=incluir_conteudo))
    _tracer = provedor.get_tracer(NOME_DO_TRACER)
    return _atual


def desligar() -> None:
    """Encerra o que `configurar` montou e volta ao estado desligado (a fábrica de logs fica: mascarar é sempre seguro)."""
    global _atual, _tracer
    atual, _atual, _tracer = _atual, _DESLIGADA, None
    atual.encerrar()


def instrumentacao_atual() -> InstrumentationSettings | None:
    return _atual.instrumentacao


# --- spans do turno ---------------------------------------------------------------------------------------------------------------------


def trace_id_atual() -> str:
    """`trace_id` do span corrente em 32 hex minúsculos; sem span ativo (ou desligada), 32 zeros."""
    contexto = trace.get_current_span().get_span_context()
    return format(contexto.trace_id, "032x") if contexto.is_valid else TRACE_ID_NULO


@contextmanager
def span_do_turno(**atributos: str | int | bool) -> Iterator[Span]:
    """Span `ia.turno` (raiz do turno; os do pydantic-ai ficam dentro). Só códigos e números: nunca texto de cliente."""
    tracer = _tracer if _tracer is not None else trace.get_tracer(NOME_DO_TRACER)
    with tracer.start_as_current_span(SPAN_DO_TURNO, attributes=_limpar_atributos(atributos)) as span:
        yield span


@contextmanager
def span_da_ferramenta(**atributos: str | int | bool) -> Iterator[Span]:
    """Span `ia.ferramenta` (uma chamada do gateway de ferramentas, B5.1). Só códigos e números: nunca argumento, CPF nem retorno."""
    tracer = _tracer if _tracer is not None else trace.get_tracer(NOME_DO_TRACER)
    with tracer.start_as_current_span(SPAN_DA_FERRAMENTA, attributes=_limpar_atributos(atributos)) as span:
        yield span


def alertar_raciocinio(tokens_raciocinio: int, *, modelo: str, provedor: str) -> None:
    """A resposta trouxe tokens de raciocínio (G §7, risco «raciocínio ligado por engano»): alerta em log e no span corrente."""
    registro.warning("%s: %d tokens de raciocínio (modelo=%s, provedor=%s)", ALERTA_RACIOCINIO, tokens_raciocinio, modelo, provedor)
    trace.get_current_span().add_event(ALERTA_RACIOCINIO, {"tokens_raciocinio": tokens_raciocinio, "modelo": modelo, "provedor": provedor})


def alertar_uso_ausente(*, modelo: str, provedor: str) -> None:
    """A resposta do provedor veio sem `usage` (B-2): o custo do turno sai zero sem ser medido. Alerta em log e no span corrente."""
    registro.warning("%s: resposta sem usage (modelo=%s, provedor=%s); o custo do turno não é medida", ALERTA_USO_AUSENTE, modelo, provedor)
    trace.get_current_span().add_event(ALERTA_USO_AUSENTE, {"modelo": modelo, "provedor": provedor})
