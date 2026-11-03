"""Agente do turno (B1.4, sp01 T6): `Turno`, ações por fase, UM provedor, raciocínio desligado, custo e `ErroDoModelo`. Sem rede, sem chave real.

O 'Fireworks' é um `httpx.MockTransport` (`RedeSimulada`): o corpo que o SDK monta é o que se confere. O modelo falso é o `ProvedorFalso`.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, get_args
from uuid import UUID

import httpx
import pytest
from pydantic import ValidationError
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.openai import OpenAIChatModel

from ia_atendimento import corpus as f3
from ia_atendimento import observabilidade
from ia_atendimento.agente import (
    PROVEDOR_FIREWORKS_US,
    AcaoForaDaFase,
    Deps,
    ErroDoModelo,
    ModeloDaFaixa,
    ProvedorFalso,
    ProvedorIndisponivel,
    ProvedorNaoConfigurado,
    RaciocinioNaoLiberado,
    ResolvedorModelo,
    SaidaInvalida,
    criar_agente,
    executar_turno,
    extra_body_raciocinio,
    ferramenta_falsa,
)
from ia_atendimento.chave import LeitorConfig
from ia_atendimento.config import Precos
from ia_atendimento.contexto import proteger_texto
from ia_atendimento.linha_tempo import CtxPasso, gravar_passo
from ia_atendimento.passos import MOTIVOS_DE_DECISAO
from ia_atendimento.relogio import RelogioFalso
from ia_atendimento.roteiro_f3 import ForaDoRoteiro, RoteiroF3, exemplos_da_f3, fase_do_modelo
from ia_atendimento.turno import (
    ACOES_POR_FASE,
    FERRAMENTAS_DO_MODELO_POR_FASE,
    PLACEHOLDERS_DO_TEXTO,
    TX_DO_MODELO_POR_FASE,
    TX_FAQ,
    Acao,
    AlvoPedido,
    CampoAlvo,
    CampoForaDaFase,
    FerramentaForaDaFase,
    FerramentaPedida,
    Intencao,
    Objecao,
    Turno,
    TxForaDaFase,
    custo_brl,
    formato_do_turno,
    validar_turno_na_fase,
)
from tests.apoio_b12 import novo_atendimento
from tests.apoio_b14 import (
    CHAVE_DA_API,
    MODELO,
    TURNO_E2,
    ContextoFalso,
    RedeSimulada,
    agente_falso,
    agente_na_rede,
    resposta_openai,
    settings_de_teste,
)

pytest_plugins = ["tests.apoio_b12"]

RAIZ_DO_CORPUS = Path(__file__).parent / "corpus"
DEPS = Deps(atendimento_id=UUID(int=1), pessoa_id=UUID(int=2))
TURNO_BASE = {"intencao": "aceita", "acao": "responder", "confianca": "alta"}


def _turno(**mudar: Any) -> Turno:
    return Turno(**{**TURNO_BASE, **mudar})


@pytest.fixture(scope="module")
def corpus() -> f3.Corpus:
    return f3.carregar(RAIZ_DO_CORPUS)


# --- o Turno (H §2.2 + sinal) ----------------------------------------------------------------------------------------------------------


def test_turno_recusa_campo_desconhecido_texto_com_digito_e_intencao_fora_das_20():
    assert len(get_args(Intencao)) == 20
    with pytest.raises(ValidationError):
        _turno(inventado="x")
    with pytest.raises(ValidationError):
        _turno(intencao="pedir_cpf")
    with pytest.raises(ValidationError, match="dígito"):
        _turno(texto="Pode ser em 3 vezes?")
    with pytest.raises(ValidationError, match="dígito"):
        _turno(texto="Fica ³ vezes")  # dígito Unicode também é dígito


def test_turno_aceita_adiar_com_hora_adiar_sem_hora_e_sinal():
    for intencao in ("adiar_com_hora", "adiar_sem_hora"):
        for sinal in get_args(_turno().__class__.model_fields["sinal"].annotation):
            assert _turno(intencao=intencao, sinal=sinal).sinal == sinal
    assert _turno().sinal == "neutro"  # sem sinal o padrão é neutro: faltar o campo não vira repasse
    with pytest.raises(ValidationError):
        _turno(sinal="furioso")


@pytest.mark.parametrize(
    "texto",
    [
        "Seu valor é R$ mil",  # símbolo de moeda
        "veja em fulano@exemplo.test",  # e-mail
        "acesse https://exemplo.test/x",  # link
        "acesse www exemplo.test e www.exemplo.test",
        "Oi {{cpf}}, tudo bem?",  # placeholder fora do conjunto fechado
        "Oi {{nome}, tudo bem?",  # chave solta
        "Oi {nome}, tudo bem?",
    ],
)
def test_texto_livre_recusa_valor_link_email_e_placeholder_invalido(texto):
    with pytest.raises(ValidationError):
        _turno(texto=texto)


def test_texto_livre_aceita_placeholder_do_conjunto_fechado_e_limita_320():
    assert _turno(texto="Oi, {{nome}}! Sobre {{banco}}, quer ver {{valor_parcela}} em {{prazo}}?").texto
    with pytest.raises(ValidationError):
        _turno(texto="a" * 321)
    assert _turno(texto="a" * 320).texto
    assert _turno(texto="   ").texto is None  # vazio é ausente


def test_motivo_ausente_nulo_ou_vazio_vira_o_padrao_e_o_longo_e_recusado():
    assert _turno().motivo == "(não informado)"
    assert _turno(motivo=None).motivo == "(não informado)"
    assert _turno(motivo="  ").motivo == "(não informado)"
    with pytest.raises(ValidationError):
        _turno(motivo="m" * 121)


def test_ferramenta_existe_se_e_so_se_usar_ferramenta_e_args_so_referencias():
    assert _turno(acao="usar_ferramenta", ferramenta={"nome": "T3", "args": {"oferta_ref": "oferta-1"}}).ferramenta.nome == "T3"
    with pytest.raises(ValidationError):
        _turno(acao="usar_ferramenta")
    with pytest.raises(ValidationError):
        _turno(acao="responder", ferramenta={"nome": "T3"})
    with pytest.raises(ValidationError):
        _turno(acao="usar_ferramenta", ferramenta={"nome": "T3", "args": {"oferta_ref": "R$ 5.000,00"}})  # valor não é referência
    with pytest.raises(ValidationError):
        _turno(acao="usar_ferramenta", ferramenta={"nome": "T3", "args": {"cpf": "12345678909"}})  # 11 dígitos
    with pytest.raises(ValidationError):
        _turno(acao="usar_ferramenta", ferramenta={"nome": "T99"})


def test_contexto_codigos_ate_10_e_sem_dado_pessoal():
    assert _turno(contexto_codigos=["motivacao_valor", "objecao_parcela_alta"]).contexto_codigos == (
        "motivacao_valor",
        "objecao_parcela_alta",
    )
    with pytest.raises(ValidationError):
        _turno(contexto_codigos=[f"c{i}" for i in range(11)])
    with pytest.raises(ValidationError):
        _turno(contexto_codigos=["12345678909"])


def test_esquema_do_turno_e_enxuto_e_conta_nos_tokens():
    esquema = json.dumps(Turno.model_json_schema())
    assert '"title"' not in esquema and '"description"' not in esquema
    assert len(formato_do_turno()) < 2300  # vai a cada chamada como ferramenta de saída: é custo de entrada


# --- o vocabulário bate com o da F3 (uma só verdade) -----------------------------------------------------------------------------------


def test_vocabulario_do_turno_e_igual_ao_do_corpus_da_f3():
    assert set(get_args(Intencao)) == set(f3.INTENCOES)
    assert set(get_args(Objecao)) == set(f3.OBJECOES)
    assert set(get_args(CampoAlvo)) == set(get_args(f3.CampoAlvo))
    assert set(get_args(Acao)) <= f3.ACOES
    assert set(get_args(AlvoPedido)) == {"valor", "parcela", "prazo"}
    assert set(ACOES_POR_FASE) == set(f3.FASES)
    assert PLACEHOLDERS_DO_TEXTO <= f3.PLACEHOLDERS


def test_ferramentas_e_tx_do_modelo_sao_subconjunto_do_que_a_f3_permite():
    for fase, ferramentas in FERRAMENTAS_DO_MODELO_POR_FASE.items():
        assert ferramentas <= f3.FERRAMENTAS_POR_FASE[fase] or not ferramentas, fase
    for fase, tx in TX_DO_MODELO_POR_FASE.items():
        assert all(fase in f3.TX_FASES[t] for t in tx), fase
    assert all(t in f3.TX_IDS for t in TX_FAQ)


def test_acoes_por_fase_batem_com_o_gabarito_das_falas_do_cliente(corpus):
    """O gabarito (B8.1a, duas revisões) é o oráculo: a união das ações permitidas nas falas do cliente de cada fase É o conjunto do modelo."""
    modelo = set(get_args(Acao))
    do_cliente: dict[str, set[str]] = {fase: set() for fase in f3.FASES}
    da_ia: dict[str, set[str]] = {fase: set() for fase in f3.FASES}
    for dialogo in corpus.dialogos.values():
        for turno in dialogo.turnos:
            destino = do_cliente if turno.quem == "cliente" else da_ia
            destino[turno.fase_esperada] |= set(turno.acoes_permitidas) & modelo
    for fase in ("E2", "E3", "E4", "E5", "E6", "E7", "E8"):
        assert do_cliente[fase] == ACOES_POR_FASE[fase], fase
    assert (
        do_cliente["E10"] <= ACOES_POR_FASE["E10"] <= da_ia["E10"]
    )  # E10: `encerrar` do cliente + `repassar` de quem preenche contexto_codigos
    for fase in ("E0", "E1", "E9"):
        assert ACOES_POR_FASE[fase] == frozenset()  # sem turno do modelo


# --- ação fora da fase -----------------------------------------------------------------------------------------------------------------


def test_acao_fora_do_conjunto_da_fase_e_erro_do_modelo():
    with pytest.raises(AcaoForaDaFase) as erro:
        validar_turno_na_fase("E2", _turno(acao="pedir_confirmacao"))
    assert isinstance(erro.value, ErroDoModelo) and erro.value.acao_invalida and erro.value.codigo == "acao_fora_da_fase"
    for fase in ("E0", "E1", "E9"):  # fase sem turno do modelo recusa toda ação
        with pytest.raises(AcaoForaDaFase):
            validar_turno_na_fase(fase, _turno())
    validar_turno_na_fase("E2", _turno(acao="repassar"))
    validar_turno_na_fase("E4", _turno(acao="usar_ferramenta", ferramenta=FerramentaPedida(nome="T5")))


def test_ferramenta_tx_e_campo_fora_da_fase_tambem_sao_erro_do_modelo():
    with pytest.raises(FerramentaForaDaFase):
        validar_turno_na_fase("E3", _turno(acao="usar_ferramenta", ferramenta=FerramentaPedida(nome="T5")))  # T5 é da E4
    with pytest.raises(FerramentaForaDaFase):
        validar_turno_na_fase("E4", _turno(acao="usar_ferramenta", ferramenta=FerramentaPedida(nome="T7")))  # T7 nunca é do modelo
    with pytest.raises(TxForaDaFase):
        validar_turno_na_fase("E2", _turno(tx_id="TX-03"))  # a oferta é texto do código
    with pytest.raises(TxForaDaFase):
        validar_turno_na_fase("E7", _turno(acao="aguardar", tx_id="TX-39"))
    validar_turno_na_fase("E2", _turno(tx_id="TX-39"))
    with pytest.raises(CampoForaDaFase):
        validar_turno_na_fase("E4", _turno(acao="repassar", campo_alvo="pix"))
    validar_turno_na_fase("E5", _turno(acao="pedir_dado", campo_alvo="pix"))
    with pytest.raises(ValueError, match="fase desconhecida"):
        validar_turno_na_fase("E11", _turno())


# --- custo -----------------------------------------------------------------------------------------------------------------------------


def test_custo_por_tokens():
    assert custo_brl(tokens_in=1_000_000, tokens_cache=0, tokens_out=0) == Decimal("2.400570")
    assert custo_brl(tokens_in=0, tokens_cache=0, tokens_out=1_000_000) == Decimal("9.602280")
    assert custo_brl(tokens_in=0, tokens_cache=1_000_000, tokens_out=0) == Decimal("0.048011")  # 0,0480114 em 6 casas (numeric(14,6))
    assert custo_brl(tokens_in=0, tokens_cache=0, tokens_out=0) == 0


def test_custo_usa_os_precos_do_settings_e_recusa_token_negativo():
    s = settings_de_teste(preco_in_usd="1.00", preco_cache_usd="0.10", preco_out_usd="2.00", cambio="5.00")
    assert custo_brl(tokens_in=1_000_000, tokens_cache=0, tokens_out=0, precos=s.precos()) == Decimal("5.000000")
    assert s.precos() == Precos(Decimal("1.00"), Decimal("0.10"), Decimal("2.00"), Decimal("5.00"))
    with pytest.raises(ValueError, match="negativos"):
        custo_brl(tokens_in=-1, tokens_cache=0, tokens_out=0)


# --- UM provedor (Fireworks só-EUA), raciocínio desligado, chave só do Settings ---------------------------------------------------------


@pytest.mark.parametrize(
    ("forma", "presente", "ausente"),
    [
        ("reasoning_effort_none", ("reasoning_effort", "none"), "thinking"),
        ("thinking_disabled", ("thinking", {"type": "disabled"}), "reasoning_effort"),
    ],
)
async def test_raciocinio_desligado_vai_no_extra_body(forma, presente, ausente):
    rede = RedeSimulada([resposta_openai(TURNO_E2)])
    agente = agente_na_rede(rede, settings=settings_de_teste(modelo_raciocinio_off=forma, modelo_tentativas_http=0))
    await executar_turno(agente, DEPS, ContextoFalso("E2"))
    corpo = rede.corpos[0]
    assert corpo[presente[0]] == presente[1]
    assert ausente not in corpo
    assert corpo["model"] == "accounts/fireworks/routers/deepseek-v4p1-flash-1017-us"  # o roteador só-EUA, versão 1017
    assert corpo["temperature"] == 0.3 and corpo["max_tokens"] == 400 and "max_completion_tokens" not in corpo
    assert [t["function"]["name"] for t in corpo["tools"]] == ["final_result"]  # a saída é o Turno, por ferramenta
    na_rede = len(json.dumps(corpo["tools"], ensure_ascii=False, separators=(",", ":")))
    assert 0.9 * len(formato_do_turno()) <= na_rede <= 1.15 * len(formato_do_turno())  # o que o contexto conta cobre o que de fato vai
    assert str(rede.requisicoes[0].url) == "https://us.api.fireworks.ai/inference/v1/chat/completions"


def test_forma_padrao_de_desligar_o_raciocinio_e_reasoning_effort_none_e_a_outra_tambem_existe():
    assert settings_de_teste().modelo_raciocinio_off == "reasoning_effort_none"
    assert extra_body_raciocinio("reasoning_effort_none") == {"reasoning_effort": "none"}
    assert extra_body_raciocinio("thinking_disabled") == {"thinking": {"type": "disabled"}}
    with pytest.raises(ValueError):
        extra_body_raciocinio("pensar_bastante")
    with pytest.raises(ValidationError):
        settings_de_teste(modelo_raciocinio_off="pensar_bastante")


async def test_um_so_provedor_falha_e_propaga():
    rede = RedeSimulada([httpx.Response(503, json={"error": {"message": "sobrecarga corpo-secreto-do-provedor"}})])
    agente = agente_na_rede(rede, settings=settings_de_teste(modelo_tentativas_http=0))
    assert isinstance(agente.agente.model, OpenAIChatModel) and not isinstance(agente.agente.model, FallbackModel)
    with pytest.raises(ProvedorIndisponivel) as erro:
        await executar_turno(agente, DEPS, ContextoFalso("E2"))
    assert isinstance(erro.value, ErroDoModelo) and erro.value.status == 503 and erro.value.codigo == "provedor"
    assert "corpo-secreto-do-provedor" not in str(erro.value)  # a mensagem é fixa: o SDK cita o corpo da resposta
    assert erro.value.__cause__ is None and erro.value.__context__ is None
    assert len(rede.requisicoes) == 1  # sem segundo provedor, sem fallback: uma tentativa e o erro sobe
    assert {r.url.host for r in rede.requisicoes} == {"us.api.fireworks.ai"}


async def test_rede_fora_do_ar_e_tempo_esgotado_tambem_viram_erro_do_modelo():
    def cai(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("sem resposta")

    agente = agente_na_rede(RedeSimulada([cai]), settings=settings_de_teste(modelo_tentativas_http=0))
    with pytest.raises(ProvedorIndisponivel) as erro:
        await executar_turno(agente, DEPS, ContextoFalso("E2"))
    assert erro.value.codigo in {"provedor", "tempo_esgotado"} and erro.value.__context__ is None


def test_par_modelo_provedor_nao_configurado_levanta():
    resolvedor = ResolvedorModelo(settings_de_teste())
    for modelo, provedor in [
        ("gemini-3-flash", PROVEDOR_FIREWORKS_US),
        ("deepseek-v4p1-flash-1017", "together-us"),
        ("deepseek-v4-pro", "fireworks-us"),
    ]:
        with pytest.raises(ProvedorNaoConfigurado):
            resolvedor.resolver(modelo, provedor, False)
    with pytest.raises(RaciocinioNaoLiberado):
        resolvedor.resolver("deepseek-v4p1-flash-1017", PROVEDOR_FIREWORKS_US, True)  # raciocínio só depois da F3
    assert isinstance(resolvedor.resolver("deepseek-v4p1-flash-1017", PROVEDOR_FIREWORKS_US, False), OpenAIChatModel)


async def test_chave_da_api_so_do_settings_e_nunca_em_repr_log_nem_erro(caplog):
    caplog.set_level(logging.DEBUG)
    rede = RedeSimulada([httpx.Response(401, json={"error": {"message": f"chave invalida {CHAVE_DA_API}"}})])
    settings = settings_de_teste(modelo_tentativas_http=0)
    resolvedor = ResolvedorModelo(settings, cliente_http=rede.cliente())
    agente = criar_agente(resolvedor, MODELO, settings=settings)
    with pytest.raises(ProvedorIndisponivel) as erro:
        await executar_turno(agente, DEPS, ContextoFalso("E2"))
    assert rede.requisicoes[0].headers["authorization"] == f"Bearer {CHAVE_DA_API}"  # a chave vai ao provedor, e só a ele
    for saida in (repr(resolvedor), repr(settings), str(settings), str(erro.value), repr(erro.value), repr(agente), caplog.text):
        assert CHAVE_DA_API not in saida
    assert "ModelHTTPError" not in str(erro.value)


# --- executar_turno: resultado, custo, falhas ------------------------------------------------------------------------------------------


async def test_turno_devolve_resposta_estruturada():
    rede = RedeSimulada([resposta_openai({**TURNO_E2, "objecao": None, "tx_id": "TX-39"}, entrada=1200, em_cache=800, saida=90)])
    agente = agente_na_rede(rede, settings=settings_de_teste(modelo_tentativas_http=0))
    r = await executar_turno(agente, DEPS, ContextoFalso("E2"), cronometro=iter([10.0, 10.25]).__next__)
    assert r.turno.intencao == "saudacao" and r.turno.tx_id == "TX-39" and r.turno.sinal == "positivo"
    assert (r.tokens_in, r.tokens_cache, r.tokens_out) == (400, 800, 90)  # a entrada total (1200) inclui o cache (800)
    assert r.latencia_ms == 250 and r.acao_invalida is False and r.raciocinio_detectado is False
    assert r.custo_brl == custo_brl(tokens_in=400, tokens_cache=800, tokens_out=90) == Decimal("0.001863")
    assert (r.modelo, r.provedor) == ("deepseek-v4p1-flash-1017", "fireworks-us")


async def test_decisao_sem_motivo():
    sem_motivo = {k: v for k, v in TURNO_E2.items() if k != "motivo"}
    agente = agente_na_rede(RedeSimulada([resposta_openai(sem_motivo)]), settings=settings_de_teste(modelo_tentativas_http=0))
    r = await executar_turno(agente, DEPS, ContextoFalso("E2"))
    assert r.turno.motivo == "(não informado)"
    assert r.como_decisao().colunas()["motivo"] == "nao_informado"  # passo.motivo é de lista fechada; o texto do modelo nunca vai para lá


async def test_motivo_livre_do_modelo_nao_vai_para_o_passo_so_o_codigo_da_lista():
    agente = agente_na_rede(
        RedeSimulada([resposta_openai({**TURNO_E2, "motivo": "cliente_concordou"})]), settings=settings_de_teste(modelo_tentativas_http=0)
    )
    r = await executar_turno(agente, DEPS, ContextoFalso("E2"))
    assert "cliente_concordou" in MOTIVOS_DE_DECISAO and r.como_decisao().colunas()["motivo"] == "cliente_concordou"
    livre = await executar_turno(
        agente_na_rede(RedeSimulada([resposta_openai(TURNO_E2)]), settings=settings_de_teste(modelo_tentativas_http=0)),
        DEPS,
        ContextoFalso("E2"),
    )
    assert livre.turno.motivo == "cliente cumprimentou" and livre.como_decisao().colunas()["motivo"] == "nao_informado"


async def test_acao_fora_da_fase_chega_com_o_gasto_e_acao_invalida():
    rede = RedeSimulada([resposta_openai({**TURNO_BASE, "acao": "pedir_confirmacao"}, entrada=1000, saida=50)])
    agente = agente_na_rede(rede, settings=settings_de_teste(modelo_tentativas_http=0))
    with pytest.raises(AcaoForaDaFase) as erro:
        await executar_turno(agente, DEPS, ContextoFalso("E2"))
    resultado = erro.value.resultado
    assert resultado is not None and resultado.acao_invalida is True
    assert erro.value.uso.custo_brl == resultado.custo_brl > 0  # o turno gastou: o gasto do dia (Σ passo.custo_brl) tem de enxergar
    decisao = resultado.como_decisao()
    assert decisao.acao_invalida is True and decisao.custo_brl == resultado.custo_brl


async def test_saida_invalida_depois_do_output_retries_conta_uma_falha_e_leva_o_gasto():
    invalida = resposta_openai({**TURNO_BASE, "intencao": "inventada-xyz"}, entrada=1000, saida=60)
    rede = RedeSimulada([invalida])
    agente = agente_na_rede(rede, settings=settings_de_teste(modelo_tentativas_http=0))
    with pytest.raises(SaidaInvalida) as erro:
        await executar_turno(agente, DEPS, ContextoFalso("E2"))
    assert len(rede.requisicoes) == 2  # output_retries=1: a saída inválida ganha UMA nova tentativa
    assert "inventada-xyz" not in str(erro.value) and erro.value.__context__ is None
    assert (erro.value.uso.tokens_in, erro.value.uso.tokens_out) == (2000, 120)  # as duas respostas foram cobradas
    assert erro.value.uso.custo_brl == custo_brl(tokens_in=2000, tokens_cache=0, tokens_out=120)


async def test_saida_invalida_que_se_corrige_na_segunda_vale():
    rede = RedeSimulada([resposta_openai({**TURNO_BASE, "intencao": "inventada-xyz"}), resposta_openai(TURNO_E2)])
    agente = agente_na_rede(rede, settings=settings_de_teste(modelo_tentativas_http=0))
    r = await executar_turno(agente, DEPS, ContextoFalso("E2"))
    assert len(rede.requisicoes) == 2 and r.turno.intencao == "saudacao"
    assert r.tokens_in == 2400 and r.tokens_out == 180  # as duas chamadas somam no custo


async def test_resposta_com_raciocinio_alerta_e_marca_o_resultado(caplog):
    caplog.set_level(logging.WARNING, logger="ia_atendimento.observabilidade")
    rede = RedeSimulada([resposta_openai(TURNO_E2, saida=200, tokens_raciocinio=120, conteudo_de_raciocinio="pensando")])
    agente = agente_na_rede(rede, settings=settings_de_teste(modelo_tentativas_http=0))
    r = await executar_turno(agente, DEPS, ContextoFalso("E2"))
    assert r.raciocinio_detectado is True and r.uso.tokens_raciocinio == 120
    assert observabilidade.ALERTA_RACIOCINIO in caplog.text


async def test_sem_raciocinio_nao_alerta(caplog):
    caplog.set_level(logging.WARNING, logger="ia_atendimento.observabilidade")
    agente = agente_na_rede(RedeSimulada([resposta_openai(TURNO_E2)]), settings=settings_de_teste(modelo_tentativas_http=0))
    r = await executar_turno(agente, DEPS, ContextoFalso("E2"))
    assert r.raciocinio_detectado is False and observabilidade.ALERTA_RACIOCINIO not in caplog.text


async def test_ferramenta_do_agente_e_registrada_em_ferramentas_chamadas_e_nao_vaza_ids():
    chamada = httpx.Response(
        200,
        json={
            "id": "x", "object": "chat.completion", "created": 1, "model": "m",
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "ferramenta_falsa", "arguments": "{}"}}]}}],
            "usage": {"prompt_tokens": 500, "completion_tokens": 10, "total_tokens": 510},
        },
    )  # fmt: skip
    rede = RedeSimulada([chamada, resposta_openai(TURNO_E2)])
    agente = agente_na_rede(rede, ferramentas=[ferramenta_falsa], settings=settings_de_teste(modelo_tentativas_http=0))
    r = await executar_turno(agente, DEPS, ContextoFalso("E2"))
    assert r.ferramentas_chamadas == ("ferramenta_falsa",) and len(rede.requisicoes) == 2
    segunda = str(rede.corpos[1])
    assert "oferta-1" in segunda and "valor_liberado" in segunda  # só placeholders
    assert str(DEPS.pessoa_id) not in str(rede.corpos) and str(DEPS.atendimento_id) not in str(rede.corpos)  # Deps nunca vai ao modelo


# --- ProvedorFalso e o roteiro da F3 ---------------------------------------------------------------------------------------------------


def _usuario(fase: str, *mensagens: str) -> str:
    pendentes = "\n".join(f"{i}. «{m}»" for i, m in enumerate(mensagens, start=1))
    return f'## Estado\n{{"fase":"{fase}"}}\n\n## Mensagens pendentes do cliente\n{pendentes}'


async def test_provedor_falso_e_deterministico_e_responde_pelo_roteiro(corpus):
    falso_a, falso_b = ProvedorFalso(RoteiroF3(corpus)), ProvedorFalso(RoteiroF3(corpus))
    a, b = criar_agente(falso_a, MODELO), criar_agente(falso_b, MODELO)
    contexto = ContextoFalso("E2", usuario=_usuario("E2", "nao lembro de ter pedido isso"))
    ra, rb = await executar_turno(a, DEPS, contexto), await executar_turno(b, DEPS, contexto)
    assert ra.turno == rb.turno and ra.uso.tokens_in == rb.uso.tokens_in  # mesma entrada, mesma saída, mesmo custo
    assert ra.turno.intencao == "objecao" and ra.turno.objecao == "nao_lembra" and ra.turno.tx_id == "TX-33"
    assert falso_a.chamadas == 1 and "nao lembro" in falso_a.vistos[0]


async def test_provedor_falso_falha_sob_comando_e_a_falha_propaga_como_erro_do_modelo():
    from pydantic_ai.exceptions import ModelHTTPError

    agente, falso = agente_falso(_NaoDeveSerChamado())
    falso.falha = ModelHTTPError(503, "falso", {"error": "x"})
    with pytest.raises(ProvedorIndisponivel) as erro:
        await executar_turno(agente, DEPS, ContextoFalso("E2"))
    assert erro.value.status == 503 and falso.chamadas == 1


class _NaoDeveSerChamado:
    def responder(self, fase, mensagens):  # pragma: no cover - o ProvedorFalso levanta antes
        raise AssertionError


def test_roteiro_f3_responde_a_toda_fala_do_corpus_com_um_turno_valido_na_fase(corpus):
    roteiro = RoteiroF3(corpus)
    nomes = {p.id: p.nome for p in corpus.todas()}
    total = 0
    for persona_id, dialogo in corpus.dialogos.items():
        for turno in dialogo.turnos:
            fase = fase_do_modelo(turno.fase_esperada)
            if turno.quem != "cliente" or turno.texto_cliente is None or not ACOES_POR_FASE.get(fase):
                continue
            for texto in (turno.texto_cliente, *turno.variacoes):
                resposta = roteiro.responder(fase, (proteger_texto(texto, [nomes[persona_id]]),))
                assert isinstance(resposta, Turno)
                assert resposta.sinal in get_args(Turno.model_fields["sinal"].annotation)
                total += 1
                validar_turno_na_fase(fase, resposta)
    assert total > 400


def test_roteiro_f3_recusa_fala_que_nao_e_do_corpus_e_prompt_sem_mensagem(corpus):
    roteiro = RoteiroF3(corpus)
    with pytest.raises(ForaDoRoteiro):
        roteiro.responder("E2", ("frase que nenhuma persona disse",))
    with pytest.raises(ForaDoRoteiro):
        roteiro.responder("E2", ())


def test_exemplos_da_f3_nunca_vem_do_holdout_nem_levam_pii_nem_digito(corpus):
    fora = set(corpus.semente.holdout)
    for fase in ("E2", "E3", "E4", "E5", "E6", "E8"):
        exemplos = exemplos_da_f3(corpus, fase)
        assert 1 <= len(exemplos) <= 2, fase
        intencoes = [e.saida.intencao for e in exemplos]
        assert len(set(intencoes)) == len(intencoes), "intenções diferentes"
        for e in exemplos:
            assert not any(c.isdigit() for c in e.cliente)
            validar_turno_na_fase(fase, e.saida)
            assert e.saida.motivo == "(não informado)"
    por_persona = {t.texto_cliente: pid for pid, d in corpus.dialogos.items() for t in d.turnos if t.texto_cliente}
    for fase in ("E2", "E3", "E4", "E5", "E6", "E8"):
        assert all(por_persona[e.cliente] not in fora for e in exemplos_da_f3(corpus, fase)), "exemplo veio do hold-out"
    assert exemplos_da_f3(corpus, "E0") == () and exemplos_da_f3(corpus, "E9") == ()


def test_exemplos_da_f3_sao_deterministicos(corpus):
    assert exemplos_da_f3(corpus, "E3") == exemplos_da_f3(corpus, "E3")


# --- o custo vai ao passo ---------------------------------------------------------------------------------------------------------------


async def test_modelo_e_provedor_do_resultado_vem_de_modelo_por_faixa(conn_app):
    """O que a `decisao` grava: o par de `modelo_por_faixa` (config vigente), não o id do roteador."""
    valor = LeitorConfig(RelogioFalso(datetime(2026, 11, 24, 13, 0, tzinfo=UTC))).valor(conn_app, "modelo_por_faixa")
    media = ModeloDaFaixa.de_config(valor, "media")
    assert (media.modelo, media.provedor, media.raciocinio) == ("deepseek-v4p1-flash-1017", "fireworks-us", False)
    assert media.custo_max_brl == Decimal("2.0")
    agente = criar_agente(ProvedorFalso(_Fixo(_turno(intencao="saudacao"))), media)
    r = await executar_turno(agente, DEPS, ContextoFalso("E2", usuario=_usuario("E2", "oi")))
    assert (r.modelo, r.provedor) == ("deepseek-v4p1-flash-1017", "fireworks-us")
    with pytest.raises(ProvedorNaoConfigurado):
        ModeloDaFaixa.de_config(valor, "faixa_que_nao_existe")


class _Fixo:
    def __init__(self, turno: Turno) -> None:
        self._turno = turno

    def responder(self, fase, mensagens):
        return self._turno


async def test_decisao_do_turno_grava_tokens_custo_e_latencia_no_passo(conn_app):
    atd = novo_atendimento(conn_app)
    agente = criar_agente(ProvedorFalso(_Fixo(_turno(intencao="duvida_oferta", objecao="taxa_juros", confianca="media"))), MODELO)
    r = await executar_turno(agente, DEPS, ContextoFalso("E2", usuario=_usuario("E2", "e a taxa?")), cronometro=iter([1.0, 1.5]).__next__)
    ordem = gravar_passo(conn_app, atd, ctx=CtxPasso(turno=1, fase="E2"), dados=r.como_decisao(faixa_esforco="media")).ordem
    tipo, intencao, custo, tokens_in, tokens_out, latencia, modelo, provedor, acao_invalida = conn_app.execute(
        "SELECT tipo, intencao, custo_brl, tokens_entrada, tokens_saida, latencia_ms, modelo, provedor, acao_invalida FROM ia.passo"
        " WHERE atendimento_id = %s AND ordem = %s",
        (atd, ordem),
    ).fetchone()
    assert (tipo, intencao, modelo, provedor, acao_invalida) == (
        "decisao",
        "duvida_oferta",
        "deepseek-v4p1-flash-1017",
        "fireworks-us",
        False,
    )
    assert custo == r.custo_brl > 0 and tokens_in == r.uso.tokens_entrada and tokens_out == r.tokens_out and latencia == 500


# --- Settings do modelo (roteador só-EUA, forma de desligar o raciocínio, preços) --------------------------------------------------------


def test_padroes_documentados_do_settings_do_modelo():
    s = settings_de_teste()
    assert s.modelo_roteador == "accounts/fireworks/routers/deepseek-v4p1-flash-1017-us" and s.modelo_base_url_1.endswith("/inference/v1")
    assert (s.modelo_temperatura, s.modelo_max_tokens, s.modelo_timeout_s, s.modelo_tentativas_http) == (0.3, 400, 20.0, 1)
    assert s.precos() == Precos(Decimal("0.45"), Decimal("0.009"), Decimal("1.80"), Decimal("5.3346"))  # estudo G §4 e premissas.json


@pytest.mark.parametrize(
    "roteador",
    [
        "accounts/fireworks/routers/deepseek-v4p1-flash-1017",  # sem -us: endpoint «global», que NÃO garante os EUA
        "accounts/fireworks/models/deepseek-v4p1-flash-1017-us",  # modelo, não roteador
        "accounts/fireworks/routers/deepseek-v4p1-flash-1010-us",  # outra versão: o roteador tem de ser o do modelo_nome
        "accounts/fireworks/routers/claude-opus-5-us",
        "deepseek-v4p1-flash-1017-us",
        "accounts/fireworks/routers/deepseek-v4p1-flash-1017-us/../x",
    ],
)
def test_roteador_que_nao_e_o_so_eua_do_modelo_derruba_o_boot(roteador):
    with pytest.raises(ValidationError):
        settings_de_teste(modelo_roteador=roteador)


@pytest.mark.parametrize("campo", ["preco_in_usd", "preco_cache_usd", "preco_out_usd", "cambio"])
@pytest.mark.parametrize("valor", ["0", "-1", "1001"])
def test_boot_recusa_preco_ou_cambio_zerado_negativo_ou_absurdo(campo, valor):
    """Contrato 08 §9: preço ausente ou ≤ 0 derruba o boot; custo zero calado esconderia o gasto do dia."""
    with pytest.raises(ValidationError) as erro:
        settings_de_teste(**{campo: valor})
    assert valor not in str(erro.value) or campo in str(erro.value)


def test_limites_do_modelo_no_settings():
    for ruim in ({"modelo_temperatura": 1.5}, {"modelo_max_tokens": 10}, {"modelo_timeout_s": 0}, {"modelo_tentativas_http": 9}):
        with pytest.raises(ValidationError):
            settings_de_teste(**ruim)
