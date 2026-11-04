"""Roteamento do gateway pelo `modo_efetivo` (B5.1; P-R7, R2-02; contrato 08 §6): o mais restritivo entre `atendimento.modo` e
`config.modo`, relido a cada efeito (cache ≤ 5 s), e a URL de produção da FACTA só em `real`.

Os hosts são de exemplo (`.test`, RFC 2606): nada aqui resolve DNS nem abre conexão.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime

import pytest

from ia_atendimento.ferramentas.erros import ErroDeFerramenta
from ia_atendimento.ferramentas.especificacao import CLASSES_DE_EFEITO
from ia_atendimento.ferramentas.modo import (
    MODOS,
    BasesDoServico,
    Destinos,
    DestinosInvalidos,
    LeitorDeModo,
    modo_efetivo,
)
from ia_atendimento.relogio import RelogioFalso

FACTA_PROD = "https://facta-on.producao.test"
FACTA_DUBLE = "https://duble-facta.vps.test"
C360_PROD = "https://api-360.producao.test"
TRN_PROD = "https://trn.producao.test"
C6_PROD = "https://c6.producao.test"
PRODUCAO = {FACTA_PROD, C360_PROD, TRN_PROD, C6_PROD}
SERVICOS_DE_FORA = ("facta", "c360", "trn", "c6")


def _destinos() -> Destinos:
    return Destinos(
        {
            "facta": BasesDoServico(producao=FACTA_PROD, teste=FACTA_DUBLE),
            "c360": BasesDoServico(producao=C360_PROD),
            "trn": BasesDoServico(producao=TRN_PROD),
            "c6": BasesDoServico(producao=C6_PROD),
        }
    )


# --- modo_efetivo -------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("atendimento", "config", "esperado"),
    [
        ("real", "real", "real"),
        ("real", "sombra", "sombra"),
        ("real", "duble", "duble"),
        ("teste", "real", "teste"),
        ("teste", "duble", "duble"),
        ("teste", "sombra", "sombra"),
        ("duble", "real", "duble"),
        ("duble", "sombra", "sombra"),
        ("sombra", "real", "sombra"),
        ("sombra", "duble", "sombra"),
    ],
)
def test_modo_efetivo_e_o_mais_restritivo(atendimento, config, esperado):
    assert modo_efetivo(atendimento, config) == esperado


@pytest.mark.parametrize(("atendimento", "config"), [("real", "teste"), ("real", "REAL"), ("produção", "real"), ("real", None), ("", "")])
def test_modo_desconhecido_vale_sombra(atendimento, config):
    """Fail-closed (D-15): o que não é um modo conhecido vira o mais restritivo; `teste` global não existe (08 §6)."""
    assert modo_efetivo(atendimento, config) == "sombra"


def test_leitor_de_modo_cacheia_ate_5s_e_rele_depois():
    relogio = RelogioFalso(datetime(2026, 11, 10, 12, tzinfo=UTC))
    vigente = ["real"]
    lidas: list[str] = []

    def ler() -> str:
        lidas.append(vigente[0])
        return vigente[0]

    leitor = LeitorDeModo(ler, relogio)
    assert leitor.efetivo("real") == "real"
    vigente[0] = "sombra"  # parada dura
    relogio.avancar(seconds=4.9)
    assert leitor.efetivo("real") == "real"  # dentro do cache
    relogio.avancar(seconds=0.2)
    assert leitor.efetivo("real") == "sombra"
    assert lidas == ["real", "sombra"]


def test_leitor_de_modo_falha_fechado_e_nao_cacheia_a_falha():
    relogio = RelogioFalso(datetime(2026, 11, 10, 12, tzinfo=UTC))
    respostas = iter([RuntimeError("banco fora"), "real"])

    def ler() -> str:
        r = next(respostas)
        if isinstance(r, Exception):
            raise r
        return r

    leitor = LeitorDeModo(ler, relogio)
    assert leitor.efetivo("real") == "sombra"
    assert leitor.efetivo("real") == "real"  # a falha não ficou no cache


def test_cache_do_modo_nao_passa_de_5s():
    relogio = RelogioFalso(datetime(2026, 11, 10, 12, tzinfo=UTC))
    with pytest.raises(ValueError):
        LeitorDeModo(lambda: "real", relogio, ttl_s=5.1)


# --- destinos -------------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("posse_real", [False, True])
def test_teste_e_sombra_nunca_resolvem_host_de_producao(posse_real):
    """`teste`: nenhum serviço resolve produção (FACTA no dublê da VPS; 360/3RN/C6 nas fixtures). `sombra`: a FACTA e todo efeito
    (`leitura_paga`, `efeito_irreversivel`) ficam interceptados; só a LEITURA do 360/3RN/C6 é real e só leitura (08 §6, Tabela final)."""
    destinos = _destinos()
    for servico, classe in itertools.product(SERVICOS_DE_FORA, sorted(CLASSES_DE_EFEITO - {"acao_interna"})):
        teste = destinos.resolver(servico, classe, "teste", posse_real=posse_real)
        assert teste.url not in PRODUCAO, (servico, classe)
        sombra = destinos.resolver(servico, classe, "sombra", posse_real=posse_real)
        if servico == "facta" or classe != "leitura":
            assert sombra.url not in PRODUCAO and sombra.tipo == "interceptado", (servico, classe)
        else:
            assert sombra.tipo == "producao" and sombra.somente_leitura, (servico, classe)
    facta = destinos.resolver("facta", "efeito_irreversivel", "teste")
    assert (facta.tipo, facta.url) == ("duble", FACTA_DUBLE)


def test_producao_so_em_real_salvo_leitura_fora_da_facta():
    """Varre TODAS as combinações: a URL de produção sai em `real`; fora dele só a leitura de 360/3RN/C6 em `sombra` ou com posse real
    sob parada dura (`duble`), sempre só leitura. A FACTA de produção NUNCA fora de `real`."""
    destinos = _destinos()
    for servico, classe, modo, posse in itertools.product(
        SERVICOS_DE_FORA, sorted(CLASSES_DE_EFEITO - {"acao_interna"}), MODOS, (False, True)
    ):
        destino = destinos.resolver(servico, classe, modo, posse_real=posse)
        if destino.url in PRODUCAO:
            permitido = modo == "real" or (classe == "leitura" and servico != "facta" and (modo == "sombra" or (modo == "duble" and posse)))
            assert permitido, (servico, classe, modo, posse)
            assert destino.somente_leitura == (modo != "real")
        if servico == "facta" and modo != "real":
            assert destino.url != FACTA_PROD


def test_duble_sem_posse_le_fixture_e_teste_le_fixture_mesmo_com_posse():
    destinos = _destinos()
    assert destinos.resolver("c360", "leitura", "duble").tipo == "fixture"
    assert destinos.resolver("c360", "leitura", "teste", posse_real=True).tipo == "fixture"  # pessoa sintética: o 360 real não a tem
    assert destinos.resolver("c360", "leitura", "duble", posse_real=True).tipo == "producao"  # parada dura com posse real lê o real


def test_acao_interna_nao_tem_host():
    destino = _destinos().resolver("interno", "acao_interna", "real")
    assert destino.tipo == "interno" and destino.url is None


def test_teste_sem_url_do_duble_falha_fechado_nunca_cai_na_producao():
    destinos = Destinos({"facta": BasesDoServico(producao=FACTA_PROD)})
    with pytest.raises(ErroDeFerramenta) as erro:
        destinos.resolver("facta", "efeito_irreversivel", "teste")
    assert erro.value.codigo == "MODO_SOMENTE_LEITURA"


def test_real_sem_url_de_producao_e_banco_indisponivel():
    with pytest.raises(ErroDeFerramenta) as erro:
        Destinos({}).resolver("facta", "leitura", "real")
    assert erro.value.codigo == "BANCO_INDISPONIVEL"


@pytest.mark.parametrize(
    "bases",
    [
        BasesDoServico(producao=FACTA_PROD, teste=FACTA_PROD),  # o dublê apontando para a produção
        BasesDoServico(producao=FACTA_PROD, teste="https://FACTA-ON.producao.test/outro"),  # mesmo host, outro caminho
        BasesDoServico(producao="http://facta-on.producao.test"),  # http fora do loopback
        BasesDoServico(producao="https://usuario:senha@facta-on.producao.test"),
        BasesDoServico(producao="https://facta-on.producao.test/?token=1"),
        BasesDoServico(producao="facta-on.producao.test"),
        BasesDoServico(teste="https://duble facta.test"),
    ],
)
def test_destinos_recusam_subir_mal_configurados(bases):
    """F §Gateway 11: o gateway recusa subir com o host de produção no lugar do dublê."""
    with pytest.raises(DestinosInvalidos):
        Destinos({"facta": bases})


def test_destinos_aceitam_loopback_http_para_o_duble_local():
    Destinos({"facta": BasesDoServico(producao=FACTA_PROD, teste="http://127.0.0.1:8089")})


def test_destinos_do_ambiente():
    destinos = Destinos.de_ambiente(
        {"FACTA_BASE": FACTA_PROD, "FACTA_BASE_TESTE": FACTA_DUBLE, "C360_BASE": C360_PROD, "TRN_BASE": TRN_PROD, "C6_BASE": C6_PROD}
    )
    assert destinos.resolver("facta", "leitura", "teste").url == FACTA_DUBLE
    assert destinos.resolver("c6", "leitura", "real").url == C6_PROD
    assert Destinos.de_ambiente({}).resolver("c360", "leitura", "duble").tipo == "fixture"


def test_repr_dos_destinos_nao_mostra_url():
    """A URL pode levar caminho de credencial no futuro; o repr fica só com os nomes dos serviços."""
    assert FACTA_PROD not in repr(_destinos())
