"""Registro versionado do gateway de ferramentas (B5.1, estudo F §Gateway 1): especificação declarativa, esquemas `extra=forbid`, classes de
efeito e `catalogo_hash` amarrado a um `numero` (o CI falha se o hash mudar sem versão nova).

Nenhum dado de cliente: as especificações de teste são construídas aqui, com nomes de campo, nunca valores.
"""

from __future__ import annotations

import dataclasses
import json
import re

import pytest
from pydantic import BaseModel, ConfigDict, create_model

from ia_atendimento.chave_registro import BANCOS
from ia_atendimento.contexto import PROJECAO_DAS_FERRAMENTAS
from ia_atendimento.ferramentas import esquemas
from ia_atendimento.ferramentas.catalogo import (
    CATALOGO_MVP,
    Catalogo,
    CatalogoSemVersao,
    VersaoDoCatalogo,
    carregar_versoes,
    conferir_versao,
    versao_vigente,
)
from ia_atendimento.ferramentas.especificacao import (
    CAMPOS_PROIBIDOS_NA_ENTRADA,
    CLASSES_DE_EFEITO,
    REFERENCIAS_DO_MODELO,
    Especificacao,
    EsquemaInvalido,
)
from ia_atendimento.turno import FERRAMENTAS_DO_MODELO_POR_FASE

_LEDGER = re.compile(r"^[a-z][a-z0-9_]{1,19}$")  # `ferramenta_chamada_chave_check` da 0001
_SEMVER = re.compile(r"^[0-9]{1,3}[.][0-9]{1,3}[.][0-9]{1,3}$")


def _spec(**mudancas) -> Especificacao:
    base = CATALOGO_MVP["T3"]
    return dataclasses.replace(base, **mudancas)


# --- catalogo_hash e versão -------------------------------------------------------------------------------------------------------------


def test_catalogo_vigente_tem_versao_registrada():
    """O portão de verdade: o catálogo do código tem o hash do último `numero` de `catalogo_versoes.json`."""
    vigente = versao_vigente()
    assert vigente == carregar_versoes()[-1]
    assert vigente.hash == CATALOGO_MVP.hash()


def test_catalogo_hash_muda_sem_versao_falha_ci():
    versoes = carregar_versoes()
    conferir_versao(CATALOGO_MVP, versoes)  # em dia

    mudado = Catalogo([*(s for s in CATALOGO_MVP if s.nome != "T3"), _spec(timeout_s=2.5)])
    assert mudado.hash() != CATALOGO_MVP.hash()
    with pytest.raises(CatalogoSemVersao) as erro:
        conferir_versao(mudado, versoes)
    assert "numero" in str(erro.value)

    nova = (*versoes, VersaoDoCatalogo(numero=versoes[-1].numero + 1, hash=mudado.hash(), descricao="teste"))
    assert conferir_versao(mudado, nova).numero == versoes[-1].numero + 1


@pytest.mark.parametrize(
    "mudanca",
    [
        {"versao": "1.0.1"},
        {"descricao": "outra descrição"},
        {"precondicoes": ("oferta_ativa",)},
        {"classe": "leitura_paga"},
        {"bancos": ("FACTA",)},
        {"idempotencia": "chave_por_atendimento"},
        {"usa_cpf": True},
    ],
)
def test_qualquer_campo_da_especificacao_muda_o_hash(mudanca):
    mudado = Catalogo([*(s for s in CATALOGO_MVP if s.nome != "T3"), _spec(**mudanca)])
    assert mudado.hash() != CATALOGO_MVP.hash()


def test_mudar_a_allowlist_de_saida_muda_o_hash(monkeypatch):
    """A allowlist do modelo (`PROJECAO_DAS_FERRAMENTAS`) faz parte do JSON canônico: abrir uma chave pede versão nova."""
    antes = CATALOGO_MVP.hash()
    aberta = {**PROJECAO_DAS_FERRAMENTAS, "T3": {k: v for k, v in PROJECAO_DAS_FERRAMENTAS["T3"].items() if k != "mudou"}}
    monkeypatch.setattr("ia_atendimento.ferramentas.especificacao.PROJECAO_DAS_FERRAMENTAS", aberta)
    assert CATALOGO_MVP.hash() != antes


def test_hash_e_canonico_independe_da_ordem():
    specs = list(CATALOGO_MVP)
    assert Catalogo(reversed(specs)).hash() == CATALOGO_MVP.hash()
    assert re.fullmatch(r"[0-9a-f]{64}", CATALOGO_MVP.hash())
    json.loads(CATALOGO_MVP.json_canonico())  # é JSON


@pytest.mark.parametrize(
    "versoes",
    [
        (VersaoDoCatalogo(2, "a" * 64, "x"),),  # não começa em 1
        (VersaoDoCatalogo(1, "a" * 64, "x"), VersaoDoCatalogo(3, "b" * 64, "x")),  # pula número
        (VersaoDoCatalogo(1, "a" * 64, "x"), VersaoDoCatalogo(2, "a" * 64, "x")),  # número novo com o mesmo hash
        (),
    ],
)
def test_historico_de_versoes_malformado_e_recusado(versoes):
    with pytest.raises(CatalogoSemVersao):
        conferir_versao(CATALOGO_MVP, versoes)


def test_versao_do_catalogo_tem_forma_do_artefato_versao():
    with pytest.raises(ValueError):
        VersaoDoCatalogo(0, "a" * 64, "x")
    with pytest.raises(ValueError):
        VersaoDoCatalogo(1, "A" * 64, "x")
    with pytest.raises(ValueError):
        VersaoDoCatalogo(1, "a" * 64, "")


# --- forma da especificação -----------------------------------------------------------------------------------------------------------


def test_catalogo_mvp_cobre_o_que_o_modelo_pode_pedir_e_nada_de_t4():
    do_modelo = {s.nome for s in CATALOGO_MVP if s.do_modelo}
    assert do_modelo == set().union(*FERRAMENTAS_DO_MODELO_POR_FASE.values()) == {"T2", "T3", "T5", "T10"}
    assert "T4" not in CATALOGO_MVP  # P-R23: T4 fora do MVP
    assert {s.nome for s in CATALOGO_MVP} >= {"T1", "T2", "T3", "T5", "T6", "T7", "T8", "T9", "T10", "T13", "T14"}


def test_cada_especificacao_tem_a_forma_do_ledger():
    for spec in CATALOGO_MVP:
        assert _LEDGER.fullmatch(spec.nome_no_ledger), spec.nome
        assert _SEMVER.fullmatch(spec.versao), spec.nome
        assert spec.classe in CLASSES_DE_EFEITO
        assert set(spec.bancos) <= set(BANCOS)


def test_classes_de_efeito_do_mvp():
    classe = {s.nome: s.classe for s in CATALOGO_MVP}
    assert classe["T7"] == "efeito_irreversivel"
    assert {classe[n] for n in ("T1", "T2", "T3", "T5", "T8", "T9", "T10")} == {"leitura"}
    assert {classe[n] for n in ("T6", "T13", "T14")} == {"acao_interna"}
    t7 = CATALOGO_MVP["T7"]
    assert t7.bancos == ("FACTA",) and t7.flag_dos_bancos == "bancos_digitacao"  # mem(w): só a FACTA digita
    assert t7.execucao == "assincrona" and "confirmacao_aceita" in t7.precondicoes
    assert {s.nome for s in CATALOGO_MVP if s.usa_cpf} <= {"T1", "T5", "T7", "T8"}  # D18: CPF só onde o 360/FACTA o pedem


def test_allowlist_de_saida_do_modelo_e_a_projecao_do_contexto():
    for spec in CATALOGO_MVP:
        if spec.do_modelo:
            assert spec.projecao is PROJECAO_DAS_FERRAMENTAS[spec.nome]
        else:
            assert spec.projecao is None


def test_projecao_com_chave_fora_do_esquema_de_saida_e_recusada():
    class SaidaSemStatus(esquemas.Fechado):
        oferta_ref: str

    with pytest.raises(EsquemaInvalido, match="status"):
        _spec(saida=SaidaSemStatus)


class _Aberto(BaseModel):
    model_config = ConfigDict(extra="ignore")
    oferta_ref: str | None = None


class _Interno(BaseModel):
    model_config = ConfigDict(extra="allow")
    x: int = 0


class _ComFilhoAberto(esquemas.Fechado):
    filho: _Interno = _Interno()


@pytest.mark.parametrize("campo", ["entrada", "saida"])
@pytest.mark.parametrize("modelo", [_Aberto, _ComFilhoAberto])
def test_esquema_sem_extra_forbid_e_recusado(campo, modelo):
    with pytest.raises(EsquemaInvalido, match="extra=forbid"):
        _spec(**{campo: modelo}, do_modelo=False)


@pytest.mark.parametrize("proibido", sorted(CAMPOS_PROIBIDOS_NA_ENTRADA))
def test_ferramenta_do_modelo_nao_aceita_campo_de_valor_nem_de_pessoa(proibido):
    entrada = create_model("Entrada", __base__=esquemas.Fechado, **{proibido: (str | None, None)})
    with pytest.raises(EsquemaInvalido):
        _spec(entrada=entrada)


def test_ferramenta_do_modelo_so_recebe_referencias():
    class ComOutroCampo(esquemas.Fechado):
        oferta_ref: str | None = None
        observacao: str | None = None

    with pytest.raises(EsquemaInvalido, match="observacao"):
        _spec(entrada=ComOutroCampo)
    for spec in CATALOGO_MVP:
        if spec.do_modelo:
            assert set(spec.entrada.model_fields) <= REFERENCIAS_DO_MODELO, spec.nome


@pytest.mark.parametrize(
    "mudanca",
    [
        {"nome": "T16"},
        {"nome": "t3"},
        {"versao": "1.0"},
        {"versao": "v1.0.0"},
        {"timeout_s": 0},
        {"timeout_s": 3.5},  # síncrona ≤ 3 s (F §Gateway 6)
        {"bancos": ("ITAU",)},
        {"flag_dos_bancos": "bancos_digitacao"},  # flag sem banco
        {"classe": "acao_interna"},  # ação interna não fala com serviço de fora
        {"funcao": "Ofertas"},
    ],
)
def test_especificacao_malformada_e_recusada(mudanca):
    with pytest.raises(EsquemaInvalido):
        _spec(**mudanca)


def test_catalogo_recusa_nome_repetido():
    with pytest.raises(EsquemaInvalido, match="T3"):
        Catalogo([*CATALOGO_MVP, _spec()])
