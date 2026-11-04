"""Gateway de ferramentas (B5.1; estudo F §Gateway 2–12): validação antes da chamada, referências opacas, pré-condições por código,
roteamento pelo `modo_efetivo` relido a cada efeito, orçamento, saída por allowlist e CPF só em memória.

Os seis testes nomeados no roteiro B5.1 estão aqui e em `test_ferramentas_registro.py`/`test_ferramentas_modo.py`.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import pickle
import re
from pathlib import Path
from typing import Any

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from ia_atendimento import observabilidade as obs
from ia_atendimento.ferramentas import Deps
from ia_atendimento.ferramentas.catalogo import CATALOGO_MVP, Catalogo
from ia_atendimento.ferramentas.especificacao import CAMPOS_PROIBIDOS_NA_ENTRADA
from ia_atendimento.ferramentas.gateway import Referencia, RegistroDaChamada
from ia_atendimento.ferramentas.orcamento import ContadorDoAtendimento, OrcamentoDoTurno
from ia_atendimento.ferramentas.projecao import proteger_retorno
from ia_atendimento.ferramentas.saida import formatar_brl
from ia_atendimento.ferramentas.segredo import CpfEmMemoria
from ia_atendimento.relogio import RelogioFalso
from tests.apoio_gateway import (
    ATENDIMENTO,
    CONFIRMACAO,
    CPF,
    CPF_DIGITOS,
    FACTA_DUBLE,
    INICIO,
    OFERTA_DE_OUTRO,
    OFERTA_REAL,
    OUTRO_ATENDIMENTO,
    PESSOA,
    PRODUCAO,
    RETORNO_T3_CRU,
    Espiao,
    contexto,
    gateway,
)

RAIZ = Path(__file__).resolve().parents[1]
T7_OK = {"classe": "criada", "ref_externa": "AF-0001"}


def _propriedades(esquema: Any) -> set[str]:
    """Todos os NOMES de campo de um JSON Schema (em qualquer nível), não os valores dos enums."""
    if isinstance(esquema, dict):
        return set(esquema.get("properties", {})) | {n for v in esquema.values() for n in _propriedades(v)}
    if isinstance(esquema, list):
        return {n for v in esquema for n in _propriedades(v)}
    return set()


def _orcamento() -> OrcamentoDoTurno:
    return OrcamentoDoTurno()


async def _chamar(gw, nome: str, args: dict[str, Any] | None = None, ctx=None, **opcoes):
    return await gw.chamar(nome, args or {}, ctx or contexto(), orcamento=opcoes.pop("orcamento", None) or _orcamento(), **opcoes)


# --- roteiro: o modelo nunca fornece CPF nem valor ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("campo", sorted(CAMPOS_PROIBIDOS_NA_ENTRADA))
async def test_modelo_nao_fornece_cpf_nem_valor(campo):
    """Esquema: nenhuma ferramenta do modelo tem campo de valor ou pessoa. Chamada: o argumento a mais é `PARAMETRO_INVALIDO`, sem eco,
    e o executor nem roda."""
    for spec in CATALOGO_MVP:
        if spec.do_modelo:
            assert campo not in _propriedades(spec.entrada.model_json_schema())
    t3 = Espiao(RETORNO_T3_CRU)
    gw = gateway(executores={"T3": t3})
    sujo = CPF if campo.startswith("cpf") or campo == "documento" else "5000"
    r = await _chamar(gw, "T3", {"oferta_ref": "oferta-1", campo: sujo}, pelo_modelo=True)
    assert r.erro is not None and r.erro.codigo == "PARAMETRO_INVALIDO"
    assert r.retorno_ao_modelo() == {"erro": "PARAMETRO_INVALIDO"}
    assert sujo not in repr(r) and sujo not in str(r.erro)
    assert t3.chamadas == []


@pytest.mark.parametrize(
    "args",
    [
        {"oferta_ref": OFERTA_REAL},  # o id real não é apelido: o modelo não o conhece nem o passa
        {"oferta_ref": "oferta-7"},  # apelido que o contexto não deu
        {"oferta_ref": "R$ 5.000"},
        {"alvo": "valor", "oferta_ref": "oferta-1", "valor": 5000},
    ],
)
async def test_argumento_do_modelo_fora_das_referencias_e_parametro_invalido(args):
    t5 = Espiao({"sem_opcao": True})
    r = await _chamar(gateway(executores={"T5": t5}), "T5", args, pelo_modelo=True)
    assert r.erro.codigo == "PARAMETRO_INVALIDO" and t5.chamadas == []


async def test_referencia_de_outro_atendimento_e_parametro_invalido():
    """«Se der errado» do roteiro: a referência de outro atendimento é `PARAMETRO_INVALIDO` (esperado)."""
    t3 = Espiao(RETORNO_T3_CRU)
    gw = gateway(executores={"T3": t3})
    r = await _chamar(gw, "T3", {"oferta_ref": "oferta-1"}, contexto(apelidos={"oferta-1": OFERTA_DE_OUTRO}), pelo_modelo=True)
    assert r.erro.codigo == "PARAMETRO_INVALIDO" and t3.chamadas == []
    outro = dataclasses.replace(contexto(), atendimento_id=OUTRO_ATENDIMENTO)
    r = await _chamar(gw, "T3", {"oferta_ref": "oferta-1"}, outro, pelo_modelo=True)
    assert r.erro.codigo == "PARAMETRO_INVALIDO"


async def test_modelo_nao_cita_apelido_que_o_contexto_nao_deu_mesmo_com_resolvedor_permissivo():
    """O resolvedor confere ids do estado; o apelido que o contexto não deu nem chega a ele (o modelo inventou `oferta-7`)."""
    consultados: list[str] = []

    def aceita_tudo(atendimento_id, campo, real):
        consultados.append(real)
        return Referencia(real, banco="FACTA")

    t3 = Espiao(RETORNO_T3_CRU)
    r = await _chamar(gateway(executores={"T3": t3}, referencias=aceita_tudo), "T3", {"oferta_ref": "oferta-7"}, pelo_modelo=True)
    assert r.erro.codigo == "PARAMETRO_INVALIDO" and t3.chamadas == [] and consultados == []


async def test_sem_resolvedor_de_referencias_o_codigo_nao_passa_id_cru():
    """Fail-closed: sem quem confira no estado, só o apelido que o próprio contexto deu vale."""
    t7 = Espiao(T7_OK)
    gw = gateway(executores={"T7": t7}, referencias=None)
    r = await _chamar(gw, "T7", {"confirmacao_id": CONFIRMACAO})
    assert r.erro.codigo == "PARAMETRO_INVALIDO" and t7.chamadas == []


async def test_modelo_so_chama_ferramenta_do_modelo():
    t7 = Espiao(T7_OK)
    r = await _chamar(gateway(executores={"T7": t7}), "T7", {"confirmacao_id": CONFIRMACAO}, pelo_modelo=True)
    assert r.erro.codigo == "PARAMETRO_INVALIDO" and t7.chamadas == []
    r = await _chamar(gateway(), "T4", {}, pelo_modelo=True)  # fora do catálogo (P-R23)
    assert r.erro.codigo == "PARAMETRO_INVALIDO"


async def test_executor_recebe_o_id_real_e_o_banco_da_referencia():
    t5 = Espiao({"opcoes": [{"opcao_ref": "op-1", "dentro_da_alcada": True}]})
    r = await _chamar(gateway(executores={"T5": t5}), "T5", {"oferta_ref": "oferta-1", "alvo": "prazo"}, pelo_modelo=True)
    assert r.ok
    (chamada,) = t5.chamadas
    assert chamada.referencias["oferta_ref"].id == OFERTA_REAL and chamada.banco == "FACTA"
    assert chamada.destino.url == PRODUCAO[0]  # T5 de uma oferta FACTA vai à FACTA


# --- roteiro: saída só pela allowlist --------------------------------------------------------------------------------------------------------


async def test_saida_fora_da_allowlist_e_descartada():
    """Duas cercas: o esquema de saída descarta na chegada o que não conhece (CPF, coeficiente, comissão, tabela, link, motivo cru) e a
    allowlist do modelo deixa passar só a projeção (valores ficam do lado do código)."""
    r = await _chamar(gateway(executores={"T3": Espiao(RETORNO_T3_CRU)}), "T3", {"oferta_ref": "oferta-1"}, pelo_modelo=True)
    assert r.ok
    guardado = r.dados.model_dump(mode="json")
    for chave in ("cpf", "coef_valor", "comissao", "tabela_identificador", "link_formalizacao", "motivo_texto"):
        assert chave not in guardado
    assert guardado["valor_liberado"] == "5000.00"  # o código guarda o valor, formatado por código quando for ao cliente
    ao_modelo = proteger_retorno("T3", r.retorno_ao_modelo(), Deps(ATENDIMENTO, PESSOA, apelidos=contexto().apelidos))
    assert ao_modelo == {
        "oferta_ref": "oferta-1",
        "status": "ativa",
        "versao": 2,
        "placeholders": ["valor_liberado", "valor_parcela", "prazo"],
    }
    corpo = json.dumps(ao_modelo)
    assert all(proibido not in corpo for proibido in ("5000", "312", CPF, "0.0613", "410", "TAB-", "https", OFERTA_REAL))


async def test_saida_que_nao_cumpre_o_esquema_e_desconhecido_sem_eco():
    r = await _chamar(gateway(executores={"T3": Espiao({"status": f"cpf {CPF}"})}), "T3", {})
    assert r.erro.codigo == "DESCONHECIDO" and CPF not in repr(r) and CPF not in str(r.erro)
    r = await _chamar(gateway(executores={"T3": Espiao(comportamento=lambda c: asyncio.sleep(0, ["lista"]))}), "T3", {})
    assert r.erro.codigo == "DESCONHECIDO"


async def test_url_e_texto_com_pii_nao_chegam_ao_modelo_nem_por_campo_permitido():
    """Varredura por conteúdo: URL vira `{{link}}` e texto que a máscara troca some, antes da projeção."""
    from ia_atendimento.ferramentas.esquemas import SaidaT9
    from ia_atendimento.ferramentas.saida import para_projetar

    corpo = para_projetar(SaidaT9(disponivel=True, link="https://assina.exemplo.test/abc"))
    assert corpo == {"disponivel": True, "link": "{{link}}"}


def test_dinheiro_pre_formatado_pelo_codigo():
    from decimal import Decimal

    assert formatar_brl(Decimal("2400")) == "R$ 2.400,00"
    assert formatar_brl(Decimal("1234567.891")) == "R$ 1.234.567,89"
    assert formatar_brl(Decimal("0.5")) == "R$ 0,50"
    with pytest.raises(ValueError):
        formatar_brl(Decimal("-1"))


# --- roteiro: teste e sombra nunca alcançam a produção (no gateway) ---------------------------------------------------------------------


@pytest.mark.parametrize("modo_do_atendimento", ["teste", "sombra"])
async def test_teste_e_sombra_nunca_entregam_url_de_producao_da_facta_ao_executor(modo_do_atendimento):
    vistas: list[str | None] = []

    async def registra(chamada):
        vistas.append(chamada.destino.url)
        return T7_OK

    t7, simulador = Espiao(comportamento=registra), Espiao(comportamento=registra)
    gw = gateway(executores={"T7": t7, "T5": t7}, simuladores={"T7": simulador, "T5": simulador})
    await _chamar(gw, "T7", {"confirmacao_id": CONFIRMACAO}, contexto(modo_do_atendimento))
    await _chamar(gw, "T5", {"oferta_ref": "oferta-1", "alvo": "prazo"}, contexto(modo_do_atendimento), pelo_modelo=True)
    assert vistas and all(url not in PRODUCAO for url in vistas)
    if modo_do_atendimento == "teste":
        assert vistas[0] == FACTA_DUBLE and t7.chamadas and not simulador.chamadas
    else:
        assert not t7.chamadas and simulador.chamadas  # interceptado: só o simulador roda


async def test_efeito_interceptado_sem_simulador_e_modo_somente_leitura():
    t7 = Espiao(T7_OK)
    r = await _chamar(gateway(executores={"T7": t7}), "T7", {"confirmacao_id": CONFIRMACAO}, contexto("duble"))
    assert r.erro.codigo == "MODO_SOMENTE_LEITURA" and t7.chamadas == []


# --- roteiro: parada dura muda o roteamento do efeito já em curso -----------------------------------------------------------------------------


async def test_parada_dura_muda_o_roteamento_do_efeito_ja_em_curso():
    """R2-02: o atendimento nasceu e já leu em `real`; durante as pré-condições da T7 o operador liga a parada dura (`config.modo =
    sombra`) e o tempo passa do cache. O destino é resolvido NA HORA do efeito: a T7 sai interceptada, nunca para a FACTA de produção."""
    relogio = RelogioFalso(INICIO)
    config = ["real"]

    def parada_dura_no_meio(pedido) -> bool:
        config[0] = "sombra"
        relogio.avancar(seconds=6)
        return True

    precondicoes = {nome: (lambda p: True) for nome in CATALOGO_MVP["T7"].precondicoes} | {"confirmacao_aceita": parada_dura_no_meio}
    t3, t7, simulador = Espiao(RETORNO_T3_CRU), Espiao(T7_OK), Espiao(T7_OK)
    gw = gateway(
        executores={"T3": t3, "T7": t7},
        simuladores={"T7": simulador},
        config_modo=lambda: config[0],
        relogio=relogio,
        precondicoes=precondicoes,
    )
    primeira = await _chamar(gw, "T3", {"oferta_ref": "oferta-1"}, pelo_modelo=True)
    assert primeira.destino.tipo == "producao" and primeira.destino.modo_efetivo == "real"

    r = await _chamar(gw, "T7", {"confirmacao_id": CONFIRMACAO})
    assert t7.chamadas == [] and len(simulador.chamadas) == 1
    assert r.destino.tipo == "interceptado" and r.destino.modo_efetivo == "sombra" and r.destino.simulado

    depois = await _chamar(gw, "T3", {"oferta_ref": "oferta-1"}, pelo_modelo=True)
    assert depois.destino.modo_efetivo == "sombra" and depois.destino.somente_leitura  # leitura real, só leitura (08 §6)


async def test_falha_ao_ler_o_modo_intercepta_o_efeito():
    def fora():
        raise RuntimeError("banco fora")

    t7, simulador = Espiao(T7_OK), Espiao(T7_OK)
    r = await _chamar(
        gateway(executores={"T7": t7}, simuladores={"T7": simulador}, config_modo=fora), "T7", {"confirmacao_id": CONFIRMACAO}
    )
    assert t7.chamadas == [] and r.destino.modo_efetivo == "sombra"


# --- pré-condições e flags --------------------------------------------------------------------------------------------------------------------


async def test_precondicao_que_falha_devolve_o_codigo_e_nao_chama():
    t7 = Espiao(T7_OK)
    precondicoes = {nome: (lambda p: True) for nome in CATALOGO_MVP["T7"].precondicoes} | {"sem_opt_out": lambda p: False}
    r = await _chamar(gateway(executores={"T7": t7}, precondicoes=precondicoes), "T7", {"confirmacao_id": CONFIRMACAO})
    assert (r.erro.codigo, r.erro.precondicao) == ("PRECONDICAO_FALHOU", "sem_opt_out") and t7.chamadas == []
    assert r.retorno_ao_modelo() == {"erro": "PRECONDICAO_FALHOU", "precondicao": "sem_opt_out"}


async def test_precondicao_sem_verificador_ou_que_levanta_falha_fechado():
    t7 = Espiao(T7_OK)
    faltando = {nome: (lambda p: True) for nome in CATALOGO_MVP["T7"].precondicoes if nome != "lease_ativo"}
    r = await _chamar(gateway(executores={"T7": t7}, precondicoes=faltando), "T7", {"confirmacao_id": CONFIRMACAO})
    assert r.erro.precondicao == "lease_ativo"

    def explode(pedido):
        raise RuntimeError(f"cpf {CPF}")

    r = await _chamar(
        gateway(executores={"T7": t7}, precondicoes=faltando | {"lease_ativo": explode}), "T7", {"confirmacao_id": CONFIRMACAO}
    )
    assert r.erro.precondicao == "lease_ativo" and t7.chamadas == [] and CPF not in repr(r)


async def test_precondicao_assincrona_e_aceita():
    async def lease(pedido) -> bool:
        return False

    precondicoes = {nome: (lambda p: True) for nome in CATALOGO_MVP["T7"].precondicoes} | {"lease_ativo": lease}
    r = await _chamar(gateway(executores={"T7": Espiao(T7_OK)}, precondicoes=precondicoes), "T7", {"confirmacao_id": CONFIRMACAO})
    assert r.erro.precondicao == "lease_ativo"


async def test_banco_fora_da_flag_nao_digita():
    t7 = Espiao(T7_OK)
    r = await _chamar(gateway(executores={"T7": t7}, bancos_ligados=lambda flag: ()), "T7", {"confirmacao_id": CONFIRMACAO})
    assert (r.erro.codigo, r.erro.precondicao) == ("PRECONDICAO_FALHOU", "banco_habilitado") and t7.chamadas == []


# --- orçamento, timeout e limitadores -----------------------------------------------------------------------------------------------------


async def test_orcamento_do_turno_quatro_sincronas():
    t3 = Espiao(RETORNO_T3_CRU)
    gw, orcamento = gateway(executores={"T3": t3}), OrcamentoDoTurno()
    resultados = [await _chamar(gw, "T3", {}, orcamento=orcamento) for _ in range(5)]
    assert [r.ok for r in resultados] == [True, True, True, True, False]
    assert resultados[-1].erro.codigo == "ORCAMENTO_ESGOTADO" and len(t3.chamadas) == 4


async def test_orcamento_do_turno_cinco_segundos():
    instantes = iter([0.0, 4.9, 4.9, 5.2])
    t3 = Espiao(RETORNO_T3_CRU)
    gw, orcamento = gateway(executores={"T3": t3}, cronometro=lambda: next(instantes)), OrcamentoDoTurno()
    assert (await _chamar(gw, "T3", {}, orcamento=orcamento)).ok  # 4,9 s gastos
    assert (await _chamar(gw, "T3", {}, orcamento=orcamento)).ok  # 0,3 s: 5,2 s
    r = await _chamar(gw, "T3", {}, orcamento=orcamento)
    assert r.erro.codigo == "ORCAMENTO_ESGOTADO" and len(t3.chamadas) == 2


async def test_assincrona_nao_gasta_o_orcamento_do_turno():
    orcamento = OrcamentoDoTurno(max_sincronas=0)
    r = await _chamar(gateway(executores={"T7": Espiao(T7_OK)}), "T7", {"confirmacao_id": CONFIRMACAO}, orcamento=orcamento)
    assert r.ok


async def test_tres_corrigiveis_esgotam_a_digitacao_do_atendimento():
    contador = ContadorDoAtendimento()
    t7 = Espiao({"classe": "corrigivel"})
    gw = gateway(executores={"T7": t7}, contador=contador)
    resultados = [await _chamar(gw, "T7", {"confirmacao_id": CONFIRMACAO}) for _ in range(4)]
    assert [r.ok for r in resultados] == [True, True, True, False]
    assert resultados[-1].erro.codigo == "ORCAMENTO_ESGOTADO" and len(t7.chamadas) == 3
    assert contador.corrigiveis(ATENDIMENTO) == 3


def test_orcamento_do_atendimento_tem_os_tetos_do_roteiro():
    assert ContadorDoAtendimento().max_pagas == 2 and ContadorDoAtendimento().max_corrigiveis == 3
    assert OrcamentoDoTurno().max_sincronas == 4 and OrcamentoDoTurno().max_segundos == 5.0


async def test_timeout_de_leitura_e_banco_indisponivel_e_de_efeito_e_indeterminado():
    catalogo = Catalogo([dataclasses.replace(s, timeout_s=0.01) if s.nome in ("T3", "T7") else s for s in CATALOGO_MVP])

    async def lento(chamada):
        await asyncio.sleep(1)
        return {}

    gw = gateway(executores={"T3": Espiao(comportamento=lento), "T7": Espiao(comportamento=lento)}, catalogo=catalogo)
    assert (await _chamar(gw, "T3", {})).erro.codigo == "BANCO_INDISPONIVEL"
    assert (await _chamar(gw, "T7", {"confirmacao_id": CONFIRMACAO})).erro.codigo == "INDETERMINADO"  # nunca reenvia (regra 12)


async def test_excecao_do_executor_vira_desconhecido_sem_eco(caplog):
    async def explode(chamada):
        raise ValueError(f"falhou para {chamada.cpf.revelar()} com R$ 5.000,00")

    caplog.set_level(logging.DEBUG)
    r = await _chamar(gateway(executores={"T1": Espiao(comportamento=explode)}), "T1", {})
    assert r.erro.codigo == "DESCONHECIDO"
    assert CPF_DIGITOS not in caplog.text and "5.000" not in caplog.text and CPF_DIGITOS not in repr(r)
    assert r.erro.__cause__ is None and r.erro.__context__ is None


async def test_limitador_da_facta_deixa_no_maximo_duas_ao_mesmo_tempo():
    em_voo, pico = 0, 0
    liberar = asyncio.Event()

    async def segura(chamada):
        nonlocal em_voo, pico
        em_voo += 1
        pico = max(pico, em_voo)
        await liberar.wait()
        em_voo -= 1
        return {"estado": "aguardando"}

    gw = gateway(executores={"T8": Espiao(comportamento=segura)}, referencias=lambda a, c, r: Referencia(r, banco="FACTA"))
    tarefas = [asyncio.create_task(_chamar(gw, "T8", {"tentativa_ref": f"t7-{n}"})) for n in range(5)]
    await asyncio.sleep(0.05)
    assert pico == 2
    liberar.set()
    assert all(r.ok for r in await asyncio.gather(*tarefas))


# --- roteiro: CPF só em memória do gateway ------------------------------------------------------------------------------------------------


@pytest.fixture
def spans_crus(monkeypatch):
    """Spans SEM o exportador mascarado: o que o gateway pôs no span, como pôs (o scrubber não pode esconder um vazamento do teste)."""
    memoria = InMemorySpanExporter()
    provedor = TracerProvider()
    provedor.add_span_processor(SimpleSpanProcessor(memoria))
    monkeypatch.setattr(obs, "_tracer", provedor.get_tracer("teste"))
    yield memoria
    provedor.shutdown()


@pytest.fixture
def logs_crus():
    """Sem a fábrica de logs mascarada (outro teste pode tê-la instalado): o log que o gateway escreve, como escreve."""
    estava = obs._fabrica_original is not None
    obs.desinstalar_filtro_de_logs()
    yield
    if estava:
        obs.instalar_filtro_de_logs()


async def test_cpf_so_em_memoria_do_gateway(caplog, spans_crus, logs_crus):
    """D18/E-1: o CPF é lido a cada chamada, entregue só ao executor e não fica em coluna, log, span, registro do ledger nem resultado."""
    caplog.set_level(logging.DEBUG)
    recebidos: list[str] = []
    registros: list[RegistroDaChamada] = []

    async def t1(chamada):
        recebidos.append(chamada.cpf.revelar())
        return {"encontrado": True, "primeiro_nome": "Fulano", "cpf": chamada.cpf.revelar(), "nao_perturbe": False}

    async def t7(chamada):
        recebidos.append(chamada.cpf.revelar())
        raise RuntimeError(f"timeout no banco para o CPF {chamada.cpf.revelar()}")

    gw = gateway(executores={"T1": Espiao(comportamento=t1), "T7": Espiao(comportamento=t7)}, registrar=registros.append)
    r1 = await _chamar(gw, "T1", {})
    r7 = await _chamar(gw, "T7", {"confirmacao_id": CONFIRMACAO})
    assert recebidos == [CPF_DIGITOS, CPF_DIGITOS] and r1.ok and r7.erro.codigo == "INDETERMINADO"  # efeito em dúvida: T8, nunca reenvio
    assert len(registros) == 2 and len(spans_crus.get_finished_spans()) == 2

    spans = json.dumps(
        [
            {"nome": s.name, "atributos": dict(s.attributes or {}), "eventos": [dict(e.attributes or {}) for e in s.events]}
            for s in spans_crus.get_finished_spans()
        ]
    )
    vistos = "\n".join(
        [
            caplog.text, spans, repr(registros), json.dumps([dataclasses.asdict(x) for x in registros], default=str), repr(r1), repr(r7),
            r1.dados.model_dump_json(), json.dumps(r1.retorno_ao_modelo()), json.dumps(r7.retorno_ao_modelo()),
        ]
    )  # fmt: skip
    assert CPF not in vistos and CPF_DIGITOS not in vistos
    assert "cpf" not in {f.name for f in dataclasses.fields(RegistroDaChamada)} | {f.name for f in dataclasses.fields(Deps)}


def test_cpf_em_memoria_nao_se_serializa():
    cpf = CpfEmMemoria(CPF)
    assert cpf.revelar() == CPF_DIGITOS
    for forma in (repr(cpf), str(cpf), f"{cpf}", f"{cpf!r}"):
        assert CPF_DIGITOS not in forma and "012" not in forma
    with pytest.raises(TypeError):
        json.dumps(cpf)
    with pytest.raises(TypeError):
        pickle.dumps(cpf)
    with pytest.raises(ValueError):
        CpfEmMemoria("123")
    assert not hasattr(cpf, "__dict__")


def test_nenhuma_migracao_tem_coluna_de_cpf():
    """«Nenhuma coluna» (E-1): o esquema `ia` não guarda CPF nem `cpf_hash` (o atendimento tem `pessoa_id`)."""
    for sql in sorted((RAIZ / "migrations").glob("*.sql")):
        texto = sql.read_text(encoding="utf-8")
        assert not re.search(r"(?im)^\s*\"?cpf\w*\"?\s+(text|varchar|char|bigint|numeric|bytea|integer)", texto), sql.name
        assert not re.search(r"(?i)\bcpf(_hash)?\s+(text|varchar|bytea)\b", texto), sql.name


async def test_sem_leitor_de_cpf_a_ferramenta_que_precisa_falha_fechado():
    t1 = Espiao({"encontrado": True})
    r = await _chamar(gateway(executores={"T1": t1}, leitor_de_cpf=None), "T1", {})
    assert r.erro.codigo == "DESCONHECIDO" and t1.chamadas == []


async def test_fixture_e_interceptado_nao_leem_cpf():
    lidos: list[Any] = []

    async def ler(pessoa_id):
        lidos.append(pessoa_id)
        return CpfEmMemoria(CPF)

    t1 = Espiao({"encontrado": True})
    r = await _chamar(gateway(executores={"T1": t1}, leitor_de_cpf=ler), "T1", {}, contexto("duble"))
    assert r.ok and r.destino.tipo == "fixture" and lidos == [] and t1.chamadas[0].cpf is None


# --- registro da chamada -----------------------------------------------------------------------------------------------------------------


async def test_registro_da_chamada_tem_a_forma_do_ledger():
    registros: list[RegistroDaChamada] = []
    gw = gateway(executores={"T3": Espiao(RETORNO_T3_CRU)}, registrar=registros.append)
    await _chamar(gw, "T3", {"oferta_ref": "oferta-1"}, pelo_modelo=True)
    await _chamar(gw, "T3", {"oferta_ref": "oferta-9"}, pelo_modelo=True)
    ok, erro = registros
    assert (ok.ferramenta, ok.versao, ok.classe, ok.resultado, ok.modo_efetivo, ok.destino) == (
        "t3",
        "1.0.0",
        "leitura",
        "ok",
        "real",
        "producao",
    )
    assert re.fullmatch(r"[0-9a-f]{64}", ok.args_hash) and ok.simulado is False
    assert erro.resultado == "parametro_invalido" and erro.args_hash is None
    assert OFERTA_REAL not in repr(registros)
