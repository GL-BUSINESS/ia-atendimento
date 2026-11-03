"""Fixtures de `duble|teste` (B2.4): `fixtures/duble/{cliente360_oferta,3rn_calcular,c6_simular}.json`, na forma medida, sem WireMock e sem chamada real.

`pytest -k fixtures_duble`. Cada arquivo é validado pelos modelos Pydantic estritos de `pessoas_teste/formas.py`; cada regra de forma tem um teste
que a quebra de propósito (campo a mais, campo a menos, tipo errado, caso incoerente) e espera a recusa. P13 (oferta ativa no C6) e P14 (sem oferta no
3RN) rodam de ponta a ponta nas fixtures.
"""

from __future__ import annotations

import copy
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from ia_atendimento.pessoas_teste import (
    FixturesDuble,
    FontePessoasTeste,
    ForaDoModoDeTeste,
    PessoasTesteInvalidas,
    carregar_fixtures_duble,
    catalogo_padrao,
    formas,
)
from ia_atendimento.pessoas_teste import fixtures_duble as modulo
from ia_atendimento.pessoas_teste.formas import C6Simular, Calcular3rnCalculado, Calcular3rnSemCalculo, Oferta, ResultadoPropostasPessoa
from ia_atendimento.relogio import RelogioFalso

RAIZ = Path(__file__).resolve().parent.parent
DIRETORIO = RAIZ / "fixtures" / "duble"
CPF_P14 = "00000000353"
CPF_P13 = "00000007528"
CONTRATO_360 = Path(os.environ.get("CLIENTE360_CONTRATO_PATH", "~/repos/cliente360-web/contrato/cliente360.json")).expanduser()


@pytest.fixture(scope="module")
def fixtures() -> FixturesDuble:
    return carregar_fixtures_duble()


@pytest.fixture
def bruto() -> dict[str, dict[str, Any]]:
    return {nome: json.loads((DIRETORIO / nome).read_text(encoding="utf-8")) for nome in modulo.NOMES}


def _grava(tmp_path: Path, bruto: dict[str, dict[str, Any]]) -> Path:
    for nome, dados in bruto.items():
        (tmp_path / nome).write_text(json.dumps(dados), encoding="utf-8")
    return tmp_path


# --- validam contra o esquema Pydantic da forma ---------------------------------------------------------------------------------------


def test_fixtures_duble_validam_contra_o_schema_pydantic_da_forma(fixtures):
    """Os três arquivos carregam, e carregam pelo diretório do checkout (o wheel leva o mesmo, `force-include`)."""
    assert modulo.diretorio_padrao() == DIRETORIO
    assert set(fixtures.cliente360.casos) == {"P01", "P13", "P14", "P-M18", "desconhecida"}
    assert {"calculado", "sem_simulacao", "reprovado"} <= set(fixtures.tres_rn.casos) and {"sem_oferta"} <= set(fixtures.c6.casos)
    for caso in fixtures.tres_rn.casos.values():
        assert isinstance(caso.corpo, Calcular3rnCalculado | Calcular3rnSemCalculo)
    for caso in fixtures.c6.casos.values():
        assert isinstance(caso.corpo, C6Simular)


def test_fixtures_duble_cada_oferta_tem_a_forma_do_schema_oferta(fixtures):
    """Toda `oferta_ativa` das fixtures do 360 é uma `Oferta` válida (obrigatórios do esquema presentes, nenhum campo inventado)."""
    ofertas = [
        par.oferta_ativa for caso in fixtures.cliente360.casos.values() for par in caso.propostas.pares if par.oferta_ativa is not None
    ]
    assert len(ofertas) >= 4
    for oferta in ofertas:
        assert isinstance(oferta, Oferta) and oferta.estado == "ativa" and oferta.economia.forma == "payload_clt_v1"


def _sem(dados: dict[str, Any], caminho: list[str | int]) -> None:
    alvo: Any = dados
    for passo in caminho[:-1]:
        alvo = alvo[passo]
    del alvo[caminho[-1]]


def _com(dados: dict[str, Any], caminho: list[str | int], valor: Any) -> None:
    alvo: Any = dados
    for passo in caminho[:-1]:
        alvo = alvo[passo]
    alvo[caminho[-1]] = valor


OFERTA = ["casos", "P01", "propostas", "pares", 0, "oferta_ativa"]
C6_SIMULADO = ["casos", "simulado_P13", "corpo"]
MUTACOES: list[tuple[str, str, Any]] = [
    # (arquivo, rótulo, função que estraga o dicionário)
    ("cliente360_oferta.json", "oferta sem valid_until", lambda d: _sem(d, [*OFERTA, "valid_until"])),
    ("cliente360_oferta.json", "oferta sem economia", lambda d: _sem(d, [*OFERTA, "economia"])),
    ("cliente360_oferta.json", "campo inventado na oferta", lambda d: _com(d, [*OFERTA, "pct_empresa"], "0.5")),
    ("cliente360_oferta.json", "campo inventado na economia", lambda d: _com(d, [*OFERTA, "economia", "comissao"], "1.00")),
    ("cliente360_oferta.json", "valor com vírgula", lambda d: _com(d, [*OFERTA, "economia", "valor_liberado"], "3000,00")),
    ("cliente360_oferta.json", "valid_until sem fuso", lambda d: _com(d, [*OFERTA, "valid_until"], "2026-11-17T17:00:00")),
    ("cliente360_oferta.json", "valid_until só data", lambda d: _com(d, [*OFERTA, "valid_until"], "2026-11-17")),
    ("cliente360_oferta.json", "oferta_id não numérico", lambda d: _com(d, [*OFERTA, "oferta_id"], "oferta-1")),
    ("cliente360_oferta.json", "pessoa_id não uuid", lambda d: _com(d, [*OFERTA, "pessoa_id"], "nao-e-uuid")),
    ("cliente360_oferta.json", "versão zero", lambda d: _com(d, [*OFERTA, "versao"], 0)),
    ("cliente360_oferta.json", "estado fora do enum", lambda d: _com(d, [*OFERTA, "estado"], "vigente")),
    ("cliente360_oferta.json", "banco minúsculo", lambda d: _com(d, [*OFERTA, "banco"], "facta")),
    ("cliente360_oferta.json", "caso so_oferta sem oferta", lambda d: _com(d, ["casos", "P01", "propostas", "pares", 0, "oferta_ativa"], None)),
    ("cliente360_oferta.json", "contrato vivo nas fixtures", lambda d: _com(d, ["casos", "P01", "propostas", "pares", 0, "contratos"], [{"x": 1}])),
    ("cliente360_oferta.json", "varias_ofertas incoerente", lambda d: _com(d, ["casos", "P13", "propostas", "varias_ofertas"], False)),
    ("cliente360_oferta.json", "encontrado:false com pares", lambda d: _com(d, ["casos", "desconhecida", "propostas", "pares"], [{"x": 1}])),
    ("cliente360_oferta.json", "resumo com cpf mascarado errado", lambda d: _com(d, ["casos", "P01", "resumo", "itens", 0, "cpf_mascarado"], "***.***.***-9")),
    ("cliente360_oferta.json", "resumo sem cpf", lambda d: _sem(d, ["casos", "P01", "resumo", "itens", 0, "cpf"])),
    ("3rn_calcular.json", "3rn: status fora do vocabulário", lambda d: _com(d, ["casos", "sem_simulacao", "corpo", "status"], "TALVEZ")),
    ("3rn_calcular.json", "3rn: calculado sem parcela", lambda d: _sem(d, ["casos", "calculado", "corpo", "parcela"])),
    ("3rn_calcular.json", "3rn: campo inventado", lambda d: _com(d, ["casos", "calculado", "corpo", "comissao"], 1.0)),
    ("3rn_calcular.json", "3rn: persona aponta caso inexistente", lambda d: _com(d, ["por_persona", "P14"], "nao_existe")),
    ("3rn_calcular.json", "3rn: cpf de 10 dígitos", lambda d: _com(d, ["casos", "calculado", "corpo", "cpf"], "0000000019")),
    ("c6_simular.json", "c6: simulado sem simulacao", lambda d: _com(d, [*C6_SIMULADO, "simulacao"], None)),
    ("c6_simular.json", "c6: result desconhecido", lambda d: _com(d, [*C6_SIMULADO, "result"], "quase")),
    ("c6_simular.json", "c6: condição sem parcelas", lambda d: _sem(d, [*C6_SIMULADO, "simulacao", "condicoes_credito", 0, "condicao", "quantidade_parcelas"])),
    ("c6_simular.json", "c6: valor como texto", lambda d: _com(d, [*C6_SIMULADO, "simulacao", "condicoes_credito", 0, "condicao", "valor_cliente"], "R$ 4.800,00")),
    ("c6_simular.json", "c6: campo inventado no envelope", lambda d: _com(d, [*C6_SIMULADO, "token"], "x")),
    ("c6_simular.json", "c6: sem custo", lambda d: _sem(d, [*C6_SIMULADO, "custo"])),
    ("c6_simular.json", "c6: padrão inexistente", lambda d: _com(d, ["padrao"], "nenhum")),
]  # fmt: skip


@pytest.mark.parametrize(("arquivo", "rotulo", "estragar"), MUTACOES, ids=[m[1] for m in MUTACOES])
def test_fixtures_duble_forma_quebrada_e_recusada(tmp_path, bruto, arquivo, rotulo, estragar):
    """Mutação: cada defeito de forma reprova ao carregar (a fixture não pode «funcionar» e divergir da resposta real, PD-6)."""
    carregar_fixtures_duble(_grava(tmp_path, copy.deepcopy(bruto)))  # a base passa
    estragada = copy.deepcopy(bruto)
    estragar(estragada[arquivo])
    with pytest.raises(PessoasTesteInvalidas):
        carregar_fixtures_duble(_grava(tmp_path, estragada))
    assert rotulo


def test_fixtures_duble_modelos_isolados_recusam_extra_e_tipo(fixtures):
    base = json.loads((DIRETORIO / "3rn_calcular.json").read_text(encoding="utf-8"))["casos"]["calculado"]["corpo"]
    assert Calcular3rnCalculado.model_validate(base).tabela == "FGL 102"
    with pytest.raises(ValidationError):
        Calcular3rnCalculado.model_validate({**base, "extra": 1})
    with pytest.raises(ValidationError):
        Calcular3rnCalculado.model_validate({**base, "success": False})  # `success:false` é outro formato (Calcular3rnSemCalculo)
    with pytest.raises(ValidationError):
        formas.ResumosPessoas.model_validate({"itens": [{"pessoa_id": "x"}]})


def test_fixtures_duble_arquivo_ausente_ou_ilegivel(tmp_path, bruto):
    with pytest.raises(PessoasTesteInvalidas):
        carregar_fixtures_duble(tmp_path)  # vazio
    pasta = _grava(tmp_path, bruto)
    (pasta / "c6_simular.json").write_text("{não é json", encoding="utf-8")
    with pytest.raises(PessoasTesteInvalidas, match="fora da forma"):
        carregar_fixtures_duble(pasta)


# --- P13 e P14 ------------------------------------------------------------------------------------------------------------------------


def test_fixtures_duble_p13_oferta_ativa_no_c6_roda_ate_o_t5(fixtures):
    """P13 cita o C6: T3 mostra a oferta ativa dele e o T5 simulado é COERENTE com ela (mesmo valor e parcela no prazo da oferta)."""
    catalogo = catalogo_padrao()
    p13 = catalogo.por_persona("P13")
    fonte = FontePessoasTeste(catalogo, RelogioFalso(datetime(2026, 11, 18, 15, 20, tzinfo=UTC)))
    t3 = ResultadoPropostasPessoa.model_validate(fonte.propostas(p13.pessoa_id, "duble"))
    c6 = next(par for par in t3.pares if par.banco == "C6")
    assert c6.caso == "so_oferta" and c6.oferta_ativa.economia.prazo_meses == 60 and t3.varias_ofertas

    http, corpo = fixtures.simular_c6("P13", CPF_P13, "duble")
    sim = C6Simular.model_validate(corpo)
    assert (http, sim.result, sim.success, sim.cpf) == (200, "simulado", True, CPF_P13)
    no_prazo = [c.condicao for c in sim.simulacao.condicoes_credito if c.condicao.quantidade_parcelas == 60]
    assert len(no_prazo) == 1
    assert (no_prazo[0].valor_cliente, no_prazo[0].valor_parcela) == (
        float(c6.oferta_ativa.economia.valor_liberado),
        float(c6.oferta_ativa.economia.valor_parcela),
    )
    assert sim.opcao_selecionada.prazo == 60 and sim.opcao_selecionada.id_simulacao == no_prazo[0].id_simulacao
    assert sorted(c.condicao.quantidade_parcelas for c in sim.simulacao.condicoes_credito) == [24, 36, 48, 60]


def test_fixtures_duble_p14_sem_oferta_no_3rn_roda_ate_o_t5(fixtures):
    """P14 cita o 3RN: T3 mostra o par SEM oferta e o T5 do 3RN não calcula (`SIM_AUSENTE`, sem refazer a consulta paga)."""
    catalogo = catalogo_padrao()
    fonte = FontePessoasTeste(catalogo, RelogioFalso(datetime(2026, 11, 19, 12, 10, tzinfo=UTC)))
    t3 = ResultadoPropostasPessoa.model_validate(fonte.propostas(catalogo.por_persona("P14").pessoa_id, "teste"))
    tres = next(par for par in t3.pares if par.banco == "3RN")
    assert tres.caso == "sem_oferta" and tres.oferta_ativa is None and not t3.varias_ofertas

    http, corpo = fixtures.calcular_3rn("P14", CPF_P14, "teste")
    sem = Calcular3rnSemCalculo.model_validate(corpo)
    assert (http, sem.success, sem.status, sem.etapa, sem.cpf) == (200, False, "SIM_AUSENTE", "vinculos", CPF_P14)


def test_fixtures_duble_outra_persona_cai_no_padrao(fixtures):
    """Quem não tem caso próprio: o 3RN devolve o recálculo (calculado) e o C6 devolve «sem oferta» (404), como o `c6-api`."""
    http, corpo = fixtures.calcular_3rn("P01", "00000000191", "duble")
    calculado = Calcular3rnCalculado.model_validate(corpo)
    assert (http, calculado.parcela, calculado.prazo) == (200, 155.05, 48)
    http, corpo = fixtures.simular_c6("P01", "00000000191", "duble")
    sem_oferta = C6Simular.model_validate(corpo)
    assert (http, sem_oferta.result, sem_oferta.success, sem_oferta.simulacao) == (404, "sem_oferta", True, None)


def test_fixtures_duble_cpf_eco_e_modo(fixtures):
    """O `cpf` da resposta é o do pedido (o arquivo traz 00000000000); em `real`/`sombra` a fixture se recusa; CPF malformado não passa."""
    assert fixtures.calcular_3rn("P01", "00000000191", "duble")[1]["cpf"] == "00000000191"
    assert modulo.CPF_ECO == "00000000000" and fixtures.c6.casos["sem_oferta"].corpo.cpf == modulo.CPF_ECO
    for modo in ("real", "sombra"):
        with pytest.raises(ForaDoModoDeTeste):
            fixtures.calcular_3rn("P14", CPF_P14, modo)
        with pytest.raises(ForaDoModoDeTeste):
            fixtures.simular_c6("P13", CPF_P13, modo)
    for ruim in ("1234", "0000000019a", "000.000.003-53"):
        with pytest.raises(ValueError, match="11 dígitos"):
            fixtures.calcular_3rn("P14", ruim, "duble")


def test_fixtures_duble_so_persona_do_corpus_tem_caso_proprio(fixtures):
    personas = {p.persona_id for p in catalogo_padrao().pessoas}
    assert set(fixtures.tres_rn.por_persona) <= personas and set(fixtures.c6.por_persona) <= personas
    assert set(fixtures.tres_rn.por_persona) == {"P14"} and set(fixtures.c6.por_persona) == {"P13", "P-M18"}


# --- cliente360_oferta.json: o exemplo e o relativo -----------------------------------------------------------------------------------


def test_fixtures_duble_exemplo_do_360_carrega_o_valid_until_relativo(fixtures):
    """O arquivo é a saída da fonte em `agora_referencia`: o `valid_until` dele é agora_referencia + 2 h, e a regra relativa está escrita nele."""
    c360 = fixtures.cliente360
    agora = datetime.strptime(c360.agora_referencia, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    assert c360.relativo.valid_until_s == 7200
    for caso in c360.casos.values():
        for par in caso.propostas.pares:
            if par.oferta_ativa is not None:
                valido_ate = datetime.strptime(par.oferta_ativa.valid_until, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
                assert valido_ate - agora == timedelta(seconds=c360.relativo.valid_until_s)
    # servir em outro instante muda o valid_until: o arquivo é referência, não o valor servido
    outro = FontePessoasTeste(catalogo_padrao(), RelogioFalso(agora + timedelta(days=3))).propostas(
        catalogo_padrao().por_persona("P01").pessoa_id, "duble"
    )
    assert outro["pares"][0]["oferta_ativa"]["valid_until"] != c360.casos["P01"].propostas.pares[0].oferta_ativa.valid_until


# --- deriva em relação ao contrato real -----------------------------------------------------------------------------------------------


@pytest.mark.skipif(not CONTRATO_360.is_file(), reason="cliente360.json do web não está neste checkout (defina CLIENTE360_CONTRATO_PATH)")
def test_fixtures_duble_formas_nao_inventam_campo_nem_perdem_obrigatorio_do_contrato_360():
    """Contra `cliente360.json`: todo campo dos modelos existe no esquema e todo `required` do esquema existe no modelo (senão a fixture deriva)."""
    esquemas = json.loads(CONTRATO_360.read_text(encoding="utf-8"))["components"]["schemas"]
    pares = {
        "Oferta": formas.Oferta, "PayloadEconomicoCltV1": formas.PayloadEconomicoCltV1, "ParPropostasPessoa": formas.ParPropostasPessoa,
        "ResultadoPropostasPessoa": formas.ResultadoPropostasPessoa, "PessoaResumo": formas.PessoaResumo, "ResumosPessoas": formas.ResumosPessoas,
        "AtributosCadastraisOferta": formas.AtributosCadastraisOferta, "NaoPerturbe": formas.NaoPerturbe, "LimiteContratos": formas.LimiteContratos,
    }  # fmt: skip
    for nome, modelo in pares.items():
        esquema = esquemas[nome]
        campos = set(modelo.model_fields)
        assert campos <= set(esquema["properties"]), f"{nome}: campo fora do contrato: {sorted(campos - set(esquema['properties']))}"
        obrigatorios = {c for c, f in modelo.model_fields.items() if f.is_required()}
        assert set(esquema.get("required", [])) <= obrigatorios, f"{nome}: obrigatório do contrato ausente no modelo"
