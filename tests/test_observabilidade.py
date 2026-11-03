"""Observabilidade (B1.4, sp01 T6): OTel → Phoenix desligado por padrão, scrubber de spans e logs, segredos, `trace_id` e alerta de raciocínio.

Exportador EM MEMÓRIA: nada sai do processo. CPF/telefone/e-mail são sintéticos (`000.000.0nn`, `exemplo.test`).
"""

from __future__ import annotations

import json
import logging
import sys
from uuid import UUID

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic_ai.exceptions import ModelHTTPError

from ia_atendimento import observabilidade as obs
from ia_atendimento.agente import Deps, ProvedorFalso, criar_agente, executar_turno
from ia_atendimento.turno import ErroDoModelo, Turno
from tests.apoio_b14 import CHAVE_DA_API, EMAIL, MODELO, TELEFONE, ContextoFalso, settings_de_teste

CPF_FORMATADO = "000.000.012-34"
CPF_SO_DIGITOS = "00000001234"
DEPS = Deps(atendimento_id=UUID(int=1), pessoa_id=UUID(int=2))
SUJEIRA = f"cpf {CPF_FORMATADO} ou {CPF_SO_DIGITOS}, fone {TELEFONE}, e-mail {EMAIL}, chave {CHAVE_DA_API}"


class _Fixo:
    def __init__(self, turno: Turno) -> None:
        self._turno = turno

    def responder(self, fase, mensagens):
        return self._turno


@pytest.fixture(autouse=True)
def _limpo():
    obs.desligar()
    yield
    obs.desligar()
    obs.desinstalar_filtro_de_logs()


@pytest.fixture
def memoria() -> InMemorySpanExporter:
    return InMemorySpanExporter()


def _serializar(spans) -> str:
    """Tudo que um exportador de verdade veria: nome, atributos, eventos (a exceção e o traceback entram aqui) e status."""
    return json.dumps(
        [
            {
                "nome": s.name,
                "atributos": dict(s.attributes or {}),
                "eventos": [{"nome": e.name, "atributos": dict(e.attributes or {})} for e in s.events],
                "status": [s.status.status_code.name, s.status.description],
            }
            for s in spans
        ],
        ensure_ascii=False,
        default=str,
    )


def _sem_pii(texto: str) -> None:
    for proibido in (CPF_FORMATADO, CPF_SO_DIGITOS, "12-34", TELEFONE, "91234-5678", EMAIL, "fulano", CHAVE_DA_API):
        assert proibido not in texto, proibido


# --- desligada por padrão ----------------------------------------------------------------------------------------------------------------


def test_sem_endpoint_e_sem_exportador_fica_desligada_e_nao_cria_provedor():
    o = obs.configurar(settings_de_teste())
    assert o.ativa is False and o.provedor is None and o.instrumentacao is None and obs.instrumentacao_atual() is None


class _OtlpFalso(InMemorySpanExporter):
    """Troca o `OTLPSpanExporter`: guarda como foi criado e NÃO abre conexão."""

    criados: list[dict] = []

    def __init__(self, **kwargs) -> None:
        super().__init__()
        self.criados.append(kwargs)


@pytest.fixture
def otlp_falso(monkeypatch):
    import opentelemetry.exporter.otlp.proto.http.trace_exporter as modulo

    _OtlpFalso.criados = []
    monkeypatch.setattr(modulo, "OTLPSpanExporter", _OtlpFalso)
    return _OtlpFalso.criados


def test_com_endpoint_monta_o_exportador_otlp_do_phoenix_sem_enviar_nada(otlp_falso):
    s = settings_de_teste(phoenix_endpoint="http://127.0.0.1:6006", phoenix_api_key="chave-do-phoenix-descartavel-01")
    o = obs.configurar(s)
    try:
        assert o.ativa and o.provedor is not None and o.instrumentacao is not None
        assert otlp_falso == [
            {
                "endpoint": "http://127.0.0.1:6006/v1/traces",
                "headers": {"authorization": "Bearer chave-do-phoenix-descartavel-01"},
                "timeout": 10,
            }
        ]
    finally:
        o.encerrar()
    otlp_falso.clear()
    com_caminho = obs.configurar(settings_de_teste(phoenix_endpoint="http://127.0.0.1:6006/v1/traces/"))
    try:
        assert otlp_falso == [{"endpoint": "http://127.0.0.1:6006/v1/traces", "headers": None, "timeout": 10}]
    finally:
        com_caminho.encerrar()


def test_phoenix_so_aceita_url_sem_credencial_e_a_chave_e_secretstr():
    s = settings_de_teste(phoenix_endpoint="http://127.0.0.1:6006", phoenix_api_key="chave-do-phoenix-descartavel-01")
    assert "chave-do-phoenix" not in repr(s) and "chave-do-phoenix" not in s.model_dump_json()
    with pytest.raises(ValueError, match="sem credencial"):
        settings_de_teste(phoenix_endpoint="http://usuario:senha@127.0.0.1:6006")


# --- scrubber ---------------------------------------------------------------------------------------------------------------------------


async def test_span_nao_contem_cpf(memoria):
    """O agente instrumentado recebe CPF, telefone, e-mail e a chave da API no prompt (o contexto não deixaria; aqui se prova a segunda cerca)."""
    obs.configurar(settings_de_teste(), exportador=memoria)
    falso = ProvedorFalso(_Fixo(Turno(intencao="saudacao", acao="responder", confianca="alta", motivo=f"cliente falou {CPF_FORMATADO}")))
    agente = criar_agente(falso, MODELO)
    contexto = ContextoFalso("E2", usuario=f'## Estado\n{{"fase":"E2"}}\n\n## Mensagens pendentes do cliente\n1. «{SUJEIRA}»')
    await executar_turno(agente, DEPS, contexto)
    spans = memoria.get_finished_spans()
    assert spans, "o pydantic-ai tem de emitir spans com a instrumentação ligada"
    assert {"ia.turno"} <= {s.name for s in spans} and any("chat" in s.name or "agent" in s.name for s in spans)
    exportado = _serializar(spans)
    _sem_pii(exportado)
    assert "[CPF]" in exportado and "[TELEFONE]" in exportado and "[EMAIL]" in exportado  # o span existe e o conteúdo chegou, mascarado
    assert obs.SEGREDO in exportado  # a chave da API (registrada no configurar) virou [SEGREDO]


async def test_span_de_erro_nao_leva_pii_na_excecao_nem_no_traceback(memoria):
    obs.configurar(settings_de_teste(), exportador=memoria)
    corpo = {"error": f"estourou com {SUJEIRA}"}  # o SDK cita o corpo da resposta na exceção: é por aqui que a PII entraria no span
    falso = ProvedorFalso(_Fixo(Turno(intencao="saudacao", acao="responder", confianca="alta")), falha=ModelHTTPError(500, "falso", corpo))
    agente = criar_agente(falso, MODELO)
    with pytest.raises(ErroDoModelo):
        await executar_turno(agente, DEPS, ContextoFalso("E2"))
    exportado = _serializar(memoria.get_finished_spans())
    _sem_pii(exportado)
    assert "exception" in exportado or "ERROR" in exportado  # o erro foi registrado, só que mascarado


def _span_cru() -> tuple[InMemorySpanExporter, object]:
    """Um span COM a sujeira, de um provedor SEM scrubber (o que um exportador veria se o scrubber não existisse)."""
    cru = InMemorySpanExporter()
    provedor = TracerProvider()
    provedor.add_span_processor(SimpleSpanProcessor(cru))
    with provedor.get_tracer("t").start_as_current_span(
        f"span de {CPF_FORMATADO}", attributes={"a": SUJEIRA, "lista": [EMAIL, "ok"], "n": 3}
    ) as span:
        span.add_event("evento", {"detalhe": TELEFONE})
        span.set_status(trace.Status(trace.StatusCode.ERROR, f"falhou {EMAIL}"))
    (original,) = cru.get_finished_spans()
    return cru, original


def test_copia_mascarada_nao_toca_o_span_original_e_cobre_nome_atributo_lista_evento_e_status():
    _, original = _span_cru()
    assert CPF_FORMATADO in original.name and EMAIL in str(dict(original.attributes))  # o cru tem a sujeira de verdade
    copia = obs.copia_mascarada(original)
    _sem_pii(_serializar([copia]))
    assert copia.attributes["n"] == 3 and copia.attributes["lista"] == ("[EMAIL]", "ok") and "[CPF]" in copia.name
    assert copia.events[0].attributes["detalhe"] == "[TELEFONE]" and copia.status.description == "falhou [EMAIL]"
    assert copia.context == original.context and copia.start_time == original.start_time and copia.end_time == original.end_time
    assert EMAIL in str(dict(original.attributes))  # o original ficou como estava (a cópia é que sai)


def test_exportador_mascarado_so_entrega_copias():
    destino = InMemorySpanExporter()
    mascarado = obs.ExportadorMascarado(destino)
    _, original = _span_cru()
    mascarado.export([original])
    (entregue,) = destino.get_finished_spans()
    _sem_pii(_serializar([entregue]))
    assert mascarado.force_flush() is True
    mascarado.shutdown()
    assert EMAIL in str(dict(original.attributes))


def test_incluir_conteudo_falso_tira_o_texto_das_mensagens_dos_spans(memoria):
    o = obs.configurar(settings_de_teste(), exportador=memoria, incluir_conteudo=False)
    assert o.instrumentacao is not None and o.instrumentacao.include_content is False


# --- logs -------------------------------------------------------------------------------------------------------------------------------


def test_log_sai_mascarado_na_mensagem_nos_argumentos_e_no_traceback(caplog):
    obs.configurar(settings_de_teste())
    caplog.set_level(logging.DEBUG)
    log = logging.getLogger("ia_atendimento.teste_de_log")
    log.warning("cliente %s escreveu de %s", CPF_FORMATADO, TELEFONE)
    try:
        raise ValueError(f"erro com {EMAIL} e {CHAVE_DA_API}")
    except ValueError:
        log.exception("falhou")
    log.info("dict %s", {"cpf": CPF_SO_DIGITOS})
    saida = "\n".join(caplog.messages) + caplog.text
    _sem_pii(saida)
    assert "[CPF]" in saida and "[TELEFONE]" in saida and "[EMAIL]" in saida and obs.SEGREDO in saida


def test_filtro_de_logs_e_idempotente_e_reversivel():
    antes = logging.getLogRecordFactory()
    obs.instalar_filtro_de_logs()
    instalada = logging.getLogRecordFactory()
    obs.instalar_filtro_de_logs()
    assert logging.getLogRecordFactory() is instalada and instalada is not antes
    obs.desinstalar_filtro_de_logs()
    assert logging.getLogRecordFactory() is antes


def test_filtro_de_handler_tambem_mascara():
    registro = logging.LogRecord("x", logging.INFO, __file__, 1, "fone %s", (TELEFONE,), None)
    assert obs.FiltroSemPii().filter(registro) is True and registro.getMessage() == "fone [TELEFONE]"


def test_excecao_nao_tratada_do_log_com_stack_info_sai_mascarada():
    try:
        raise ValueError(CPF_FORMATADO)
    except ValueError:
        registro = logging.LogRecord("x", logging.ERROR, __file__, 1, "erro", (), sys.exc_info(), stack_info=f"pilha {EMAIL}")
    obs.FiltroSemPii().filter(registro)
    assert CPF_FORMATADO not in (registro.exc_text or "") and EMAIL not in (registro.stack_info or "")


# --- segredos ---------------------------------------------------------------------------------------------------------------------------


def test_segredo_registrado_nunca_sai_e_segredo_curto_demais_e_ignorado():
    obs.registrar_segredo("segredo-descartavel-12345")
    obs.registrar_segredo("curto")
    obs.registrar_segredo(None)
    assert obs.mascarar_texto("a chave é segredo-descartavel-12345 ok") == f"a chave é {obs.SEGREDO} ok"
    assert obs.mascarar_texto("palavra curto fica") == "palavra curto fica"


# --- trace_id e alerta de raciocínio -----------------------------------------------------------------------------------------------------


def test_trace_id_atual_tem_32_hex(memoria):
    assert obs.trace_id_atual() == obs.TRACE_ID_NULO == "0" * 32  # sem span ativo
    obs.configurar(settings_de_teste(), exportador=memoria)
    with obs.span_do_turno(fase="E2") as span:
        atual = obs.trace_id_atual()
        assert len(atual) == 32 and set(atual) <= set("0123456789abcdef") and atual != "0" * 32
        assert atual == format(span.get_span_context().trace_id, "032x")
    assert obs.trace_id_atual() == "0" * 32


async def test_executar_turno_devolve_o_trace_id_do_span_do_turno(memoria):
    obs.configurar(settings_de_teste(), exportador=memoria)
    agente = criar_agente(ProvedorFalso(_Fixo(Turno(intencao="saudacao", acao="responder", confianca="alta"))), MODELO)
    r = await executar_turno(agente, DEPS, ContextoFalso("E2"))
    assert r.trace_id is not None and len(r.trace_id) == 32
    assert {format(s.context.trace_id, "032x") for s in memoria.get_finished_spans()} == {r.trace_id}  # um turno, um trace
    assert r.como_decisao().trace_id == r.trace_id


async def test_sem_observabilidade_o_trace_id_do_turno_e_nulo_e_o_passo_aceita():
    agente = criar_agente(ProvedorFalso(_Fixo(Turno(intencao="saudacao", acao="responder", confianca="alta"))), MODELO)
    r = await executar_turno(agente, DEPS, ContextoFalso("E2"))
    assert r.trace_id is None and r.como_decisao().trace_id is None


def test_alerta_de_raciocinio_vai_ao_log_e_ao_span(memoria, caplog):
    obs.configurar(settings_de_teste(), exportador=memoria)
    caplog.set_level(logging.WARNING, logger="ia_atendimento.observabilidade")
    with obs.span_do_turno(fase="E2"):
        obs.alertar_raciocinio(120, modelo="deepseek-v4p1-flash-1017", provedor="fireworks-us")
    assert f"{obs.ALERTA_RACIOCINIO}: 120 tokens" in caplog.text
    (span,) = [s for s in memoria.get_finished_spans() if s.name == obs.SPAN_DO_TURNO]
    (evento,) = [e for e in span.events if e.name == obs.ALERTA_RACIOCINIO]
    assert evento.attributes["tokens_raciocinio"] == 120


def test_atributos_do_span_do_turno_sao_so_codigos_e_passam_pela_mascara(memoria):
    obs.configurar(settings_de_teste(), exportador=memoria)
    with obs.span_do_turno(fase="E2", modelo="deepseek-v4p1-flash-1017", nota=f"x {EMAIL}"):
        pass
    (span,) = memoria.get_finished_spans()
    assert span.attributes["fase"] == "E2" and span.attributes["nota"] == "x [EMAIL]"
