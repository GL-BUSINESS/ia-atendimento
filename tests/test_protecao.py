"""`protecao.proteger_texto` / `ha_link` (B1.4): desempenho com texto hostil, corte da entrada e as demais regras da proteção (revisão 2).

Sem banco e sem rede. CPF/e-mail sintéticos (`000.000.0nn`, `exemplo.test`).
"""

from __future__ import annotations

import time

import pytest

from ia_atendimento import contexto as ctx
from ia_atendimento.linha_tempo import mensagens_pendentes
from ia_atendimento.protecao import LIMITE_DA_ENTRADA, cortar_entrada, ha_link, normalizar, proteger_texto
from tests.apoio_b12 import AGORA
from tests.apoio_b14 import abrir_em, receber

pytest_plugins = ["tests.apoio_b12"]

NOMES = ("Maria Alvardel",)
CPF = "000.000.012-34"
EMAIL = "fulano@exemplo.test"
LIMITE_MS = 20  # coordenação: 4.000 caracteres hostis em até 20 ms (medido: 3-4 ms)


def _melhor_de_tres_ms(funcao) -> float:
    melhor = float("inf")
    for _ in range(3):
        inicio = time.perf_counter()
        funcao()
        melhor = min(melhor, (time.perf_counter() - inicio) * 1000)
    return melhor


HOSTIS = {
    "segmentos a.a.a": "a." * 2000,  # a regressão ALTA da revisão 2: 4.000 caracteres = 1 s
    "segmentos a-a-a": "a-" * 2000,
    "segmentos 1.1.1": "1." * 2000,
    "arrobas": "a@" * 2000,
    "horas coladas": "9h" * 2000,
    "dinheiro": "R$ 1 " * 800,
    "datas": "12/" * 1333,
    "dígitos": "0" * 4000,
    "espaços": " " * 4000,
    "emoji": "😀" * 4000,
    "mistura": ("a.b-c d,e/f 1.2 3h http://x.y/z " * 130)[:4000],
}


@pytest.mark.parametrize("nome", list(HOSTIS))
def test_texto_hostil_de_4000_caracteres_e_protegido_em_ate_20_ms(nome):
    """R2-01: o regex do link era quadrático; o trabalho é síncrono e trava o laço de eventos do worker inteiro."""
    texto = HOSTIS[nome]
    assert len(texto) >= 3900
    ms = _melhor_de_tres_ms(lambda: proteger_texto(texto, NOMES))
    assert ms <= LIMITE_MS, f"{nome}: {ms:.1f} ms"


@pytest.mark.parametrize("segmentos", [2000, 10000, 40000])
def test_ha_link_e_linear_mesmo_sem_o_corte(segmentos):
    """`ha_link` roda no prompt inteiro (sem o corte da entrada): o regex em si tem de ser linear."""
    texto = "a." * segmentos
    assert _melhor_de_tres_ms(lambda: ha_link(texto)) <= LIMITE_MS * (segmentos / 2000)


def test_o_corte_da_entrada_nao_leva_pii_nem_deixa_fragmento_de_palavra():
    palavras = "palavra " * 130  # 1.040 caracteres: o CPF e o e-mail ficam depois do limite
    cru = palavras + CPF + " " + EMAIL + " " + "x" * 3000
    assert len(cru) > LIMITE_DA_ENTRADA
    saida = proteger_texto(cru, NOMES)
    assert len(saida) <= LIMITE_DA_ENTRADA + 10 and saida.endswith("…")
    assert "[CPF]" not in saida and "[EMAIL]" not in saida and "000" not in saida  # o que foi cortado não vai a lugar nenhum
    assert "xxxx" not in saida


def test_cpf_partido_pelo_corte_nao_deixa_digitos():
    prefixo = "ab " * 330 + "cd"  # 992 caracteres; o CPF começa antes do limite e termina depois
    cru = prefixo + " " + CPF + " resto"
    assert prefixo.__len__() + 1 < LIMITE_DA_ENTRADA < len(prefixo) + 1 + len(CPF)
    saida = proteger_texto(cru, NOMES)
    assert not any(c.isdigit() for c in saida) and "[CPF]" not in saida and "[NUMERO]" not in saida


def test_texto_curto_nao_e_cortado_nem_marcado():
    assert cortar_entrada("oi, tudo bem?") == "oi, tudo bem?"
    assert cortar_entrada("a" * LIMITE_DA_ENTRADA) == "a" * LIMITE_DA_ENTRADA
    assert cortar_entrada("a" * (LIMITE_DA_ENTRADA + 1)).endswith("…")


def test_link_com_ponto_duplo_e_ponto_inicial_ainda_viram_marcador():
    for texto in ("x..y.com/a", "x .evil.xyz/path", "veja ...evil.xyz/x", "a.b.c.com/x", "(site.com)"):
        assert ha_link(texto) and "[LINK]" in proteger_texto(texto, ()), texto
    assert not ha_link("a.a.a.a.a") and proteger_texto("a.a.a.a.a", ()) == "a.a.a.a.a"


def test_a_vista_normalizada_continua_com_o_mesmo_comprimento():
    texto = "ｈｔｔｐ：／／ｅｘ．ｔｅｓｔ … ™ ①"
    assert len(normalizar(texto)) == len(texto)


def test_montar_contexto_com_10_pendentes_hostis_de_4000_caracteres_leva_menos_de_1_segundo(db_conn, relogio, versoes, chaveiro):
    """R2-01 (sonda p6 da revisão): 10 pendentes `a.a.a…` (o máximo que entra no prompt) levavam 10 s; o mesmo job reentra a cada falha."""
    atd, _ = abrir_em(db_conn, relogio, versoes, fase="E3")
    for i in range(10):
        receber(db_conn, atd, chaveiro, "a." * 1999 + chr(97 + i), nomes=NOMES)
    inicio = time.perf_counter()
    c = ctx.montar_contexto(db_conn, atd, pendentes=mensagens_pendentes(db_conn, atd), chaveiro=chaveiro, nomes=NOMES, agora=AGORA)
    assert time.perf_counter() - inicio < 1.0
    assert len(c.insumos.pendentes) == 10


@pytest.mark.parametrize(
    "texto",
    ["joão.evil.xyz/x", "a_b.evil.com/x", "ç.www.evil.com", "é.evil.com", "x+evil.com/x", "ã.http://evil.test/a", "Ação.evil.com/x"],
)
def test_link_depois_de_underscore_ou_letra_acentuada_nao_escapa(texto):
    """Revisão automática: o lookbehind usava `\\w` (que inclui `_` e letras acentuadas) e o host depois deles não casava."""
    assert ha_link(texto), texto
    protegido = proteger_texto(texto, ())
    assert "[LINK]" in protegido and "evil" not in protegido, protegido


def test_os_tres_exemplos_da_revisao_automatica_viram_marcador_na_frase():
    for texto in ("veja joão.evil.xyz/x", "mande a_b.evil.com/x", "ç.www.evil.com"):
        assert "evil" not in proteger_texto(texto, ()) and ha_link(texto)


@pytest.mark.parametrize("trecho", ["a.", "a+", "ã.a.", "_a.", "a_", "a-", "ç.", "a._", "a+b.", "é.é."])
def test_cadeias_com_underscore_acento_e_mais_continuam_lineares(trecho):
    """O lookbehind em caracteres de host continua impedindo o recomeço no meio da cadeia (`a.a.a…`)."""
    texto = (trecho * 4000)[:4000]
    assert _melhor_de_tres_ms(lambda: ha_link(texto)) <= LIMITE_MS
    assert _melhor_de_tres_ms(lambda: proteger_texto(texto, NOMES)) <= LIMITE_MS


# --- link com sinal de caminho vale com qualquer TLD; frases de chat sem espaço depois do ponto não são link (R2-05) ---------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "veja meusite.company/oferta?id=9",
        "exemplo.test/pagar",
        "ofertas.academy/abc",
        "x.tv/abc",
        "host.qualquer:8080",
        "a.b.cc#frag",
        "x.yz?q=1",
        "meusite.company?id=9",
        "ｅｘｅｍｐｌｏ．ｔｅｓｔ／ｘ",  # host de largura inteira
        "exemplo。test/x",  # ponto ideográfico
        "exemplo｡test/x",  # ponto ideográfico de meia largura
        "ｏｆｅｒｔａｓ．ａｃａｄｅｍｙ／ａｂｃ",
    ],
)
def test_host_com_sinal_de_caminho_e_link_com_qualquer_tld_e_ha_link_tambem(texto):
    """R2-05: `meusite.company/oferta` passava (TLD fora da lista) e o portão final, que usa o mesmo regex, não o via."""
    assert ha_link(texto), texto
    protegido = proteger_texto(texto, ())
    assert "[LINK]" in protegido and not ha_link(protegido)


@pytest.mark.parametrize(
    "frase",
    [
        "sim.pode",
        "Sr.Silva",
        "bom dia.tudo bem?",
        "e/ou",
        "vc.pode",
        "oi.tudo",
        "ate.logo",
        "sim.pode?",
        "ok.tudo?",
        "ok.obrigado!",
        "não.pode?",
        "tchau.vc",
    ],
)
def test_frase_de_chat_sem_espaco_depois_do_ponto_nao_e_link(frase):
    """NÃO se adota a regra larga `x.y`: 10 de 15 frases de chat virariam `[LINK]` e «sim.pode» é um SIM na E6."""
    assert not ha_link(frase) and proteger_texto(frase, ()) == frase


def test_numero_com_barra_nao_e_link():
    assert not ha_link("5.000/mes") and not ha_link("10.5/12") and not ha_link("R$ 5.000/mes")


def test_o_corpus_da_f3_inteiro_nao_tem_falso_positivo_de_link():
    """Prova contra os DADOS: nenhuma das 966 redações do corpus (depois da máscara de PII) tem link."""
    from pathlib import Path

    from ia_atendimento.corpus import carregar
    from ia_atendimento.mascara import mascarar

    corpus = carregar(Path(__file__).parent / "corpus")
    falas = [
        (nome.nome, x)
        for p_id, d in corpus.dialogos.items()
        for nome in corpus.todas()
        if nome.id == p_id
        for t in d.turnos
        for x in ((t.texto_cliente, *t.variacoes) if t.texto_cliente else ())
    ]
    assert len(falas) > 900
    assert [f for n, f in falas if ha_link(mascarar(f, [n]))] == []


def test_cadeias_com_o_sinal_de_caminho_continuam_lineares():
    for texto in ("a." * 2000, ("a.b/" * 1000), ("ab.ab." * 700), ("x.y:80 " * 570)):
        assert _melhor_de_tres_ms(lambda texto=texto: ha_link(texto)) <= LIMITE_MS
        assert _melhor_de_tres_ms(lambda texto=texto: proteger_texto(texto[:4000], NOMES)) <= LIMITE_MS


# --- [NUMERO:n], hora com hrs/hs/min e data com hora (R2-08, R2-07) ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("quero 5000", "quero [NUMERO:4]"),
        ("pode ser 3.500?", "pode ser [NUMERO:4]?"),
        ("250", "[NUMERO:3]"),
        ("uns 300", "uns [NUMERO:3]"),
        ("84", "[NUMERO:2]"),
        ("em 48 fica bom?", "em [NUMERO:2] fica bom?"),
        ("tem como 12000?", "tem como [NUMERO:5]?"),
        ("a parcela de 312,45", "a parcela de [NUMERO:3]"),
        ("nao, quero 3000", "nao, quero [NUMERO:4]"),
        ("conta 123456-7", "conta [NUMERO:6]"),
        ("matricula 1234567", "matricula [NUMERO]"),  # 7 dígitos: acima da classe, sem contagem
    ],
)
def test_numero_nu_vira_marcador_com_a_contagem_de_digitos(bruto, esperado):
    """R2-08: sem palavra ao redor, a grandeza era a única pista de valor × parcela × prazo (8/8 da bateria do revisor perdiam). O NÚMERO não vai."""
    assert proteger_texto(bruto, ()) == esperado


@pytest.mark.parametrize(
    "fica",
    ["15hrs", "as 15 hrs", "15hs", "15h30min", "umas 3hs", "06/11 15:30", "dia 12/11 15:30", "quinta 06/11 15:30", "05/11 10:00 ou 11:00"],
)
def test_hora_com_hrs_hs_min_e_data_com_hora_ficam(fica):
    assert proteger_texto(fica, ()) == fica


def test_o_marcador_com_contagem_e_idempotente_e_passa_no_portao():
    from ia_atendimento.contexto import auditar_textos

    uma = proteger_texto("quero 5000 em 36x, parcela 312,45, nasci 12/03/1985", NOMES)
    assert proteger_texto(uma, NOMES) == uma and "[NUMERO:4]" in uma and "[NUMERO:3]" in uma
    auditar_textos("", uma, NOMES)


def test_o_sistema_explica_o_numero_com_contagem():
    from ia_atendimento.modulos_fase import SISTEMA

    assert "[NUMERO:n]" in SISTEMA and "parcela" in SISTEMA.split("[NUMERO:n] é um número")[1][:120]
