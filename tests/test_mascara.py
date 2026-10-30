"""Máscara de PII: só dados SINTÉTICOS (CPF de exemplo com DV válido, telefones/e-mails de teste). Nunca dados reais."""

from __future__ import annotations

import random
import re

import pytest

from ia_atendimento.mascara import mascarar

CPF_VALIDO = "52998224725"  # exemplo clássico de CPF sintético com dígitos verificadores válidos
CPF_FORMATADO = "529.982.247-25"
CPF_INVALIDO_FORMATADO = "000.000.000-00"  # o do script do estudo I: formatado é sempre mascarado, mesmo sem DV válido


def _cpf_com_dv(base9: str) -> str:
    def dv(digitos: str) -> str:
        soma = sum(int(d) * p for d, p in zip(digitos, range(len(digitos) + 1, 1, -1), strict=True))
        resto = (soma * 10) % 11
        return str(0 if resto == 10 else resto)

    d1 = dv(base9)
    return base9 + d1 + dv(base9 + d1)


def test_gerador_de_cpf_sintetico_bate_com_o_exemplo():
    assert _cpf_com_dv("529982247") == CPF_VALIDO


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        (f"meu CPF é {CPF_FORMATADO} ok", "meu CPF é [CPF] ok"),
        (f"meu CPF é {CPF_VALIDO} ok", "meu CPF é [CPF] ok"),
        (f"cpf {CPF_INVALIDO_FORMATADO}", "cpf [CPF]"),
        ("CPF 529.982.247 25", "CPF [CPF]"),  # separadores estranhos: a corrente de dígitos é classificada pelos 11 dígitos (DV válido)
    ],
)
def test_cpf(entrada, esperado):
    assert mascarar(entrada) == esperado


@pytest.mark.parametrize(
    "telefone",
    [
        "(11) 91234-5678",
        "+55 11 91234-5678",
        "+5511912345678",
        "11 91234-5678",
        "11912345678",
        "(21) 3456-7890",
        "91234-5678",
        "3456-7890",
        "55 (11) 3456 7890",
    ],
)
def test_telefone_brasileiro(telefone):
    saida = mascarar(f"me liga no {telefone} depois das 18h")
    assert saida == "me liga no [TELEFONE] depois das 18h"


def test_email():
    assert (
        mascarar("escreve para fulano.de-tal+x@exemplo.test ou para ciclano@sub.exemplo.com.br") == "escreve para [EMAIL] ou para [EMAIL]"
    )


def test_cep_formatado_e_puro():
    assert mascarar("moro no CEP 99999-999 aqui") == "moro no CEP [CEP] aqui"
    assert mascarar("CEP: 99999999") == "CEP: [CEP]"


def test_uuid():
    assert mascarar("id 11111111-1111-7111-8111-111111111111 fim") == "id [UUID] fim"


def test_numero_longo_generico_8_ou_mais_digitos():
    assert mascarar("conta 12345678 e cartão 1234 5678 9012 3456") == "conta [NUMERO] e cartão [NUMERO]"
    assert mascarar("matrícula 1234567") == "matrícula 1234567"  # 7 dígitos fica


@pytest.mark.parametrize(
    "texto",
    [
        "quero 3 mil em 24x",
        "parcela de R$ 450,00 por 84 meses",
        "dia 29/10/2026 às 14:30",
        "prazo 24 meses, taxa 1,85% ao mês",
        "sim",
        "",
        "tenho 35 anos e 2 filhos",
    ],
)
def test_texto_sem_pii_passa_intacto(texto):
    assert mascarar(texto) == texto


def test_nome_so_quando_marcado():
    texto = "oi, sou a Maria Aparecida de Souza e moro em Sao Paulo"
    assert mascarar(texto) == texto  # sem nomes marcados, nada de nome é tocado
    assert mascarar(texto, nomes=["Maria Aparecida de Souza"]) == "oi, sou a [NOME] e moro em Sao Paulo"


def test_nome_ignora_caixa_e_acento_e_mascara_partes():
    saida = mascarar("JOAO falou com a Sra Conceição; depois o joão ligou", nomes=["João da Silva", "Conceição Teste"])
    assert "JOAO" not in saida and "joão" not in saida and "Conceição" not in saida
    assert saida.count("[NOME]") == 3


def test_nome_curto_de_parte_nao_mascara_palavras_comuns():
    # "da", "de" (partículas) e partes com menos de 3 letras não viram máscara: senão "da" sumiria de qualquer frase
    saida = mascarar("o contrato da casa de praia", nomes=["Ana da Silva"])
    assert saida == "o contrato da casa de praia"


def test_nome_nao_mascara_dentro_de_outra_palavra():
    assert mascarar("a analise esta pronta", nomes=["Ana"]) == "a analise esta pronta"


def test_mistura_de_tudo_e_deterministica_e_idempotente():
    texto = f"Sou Fulana Teste, CPF {CPF_FORMATADO}, tel (11) 91234-5678, fulana@exemplo.test, CEP 99999-999, id 11111111-1111-7111-8111-111111111111"
    esperado = "Sou [NOME], CPF [CPF], tel [TELEFONE], [EMAIL], CEP [CEP], id [UUID]"
    primeira = mascarar(texto, nomes=["Fulana Teste"])
    assert primeira == esperado
    assert mascarar(texto, nomes=["Fulana Teste"]) == primeira
    assert mascarar(primeira, nomes=["Fulana Teste"]) == primeira  # idempotente


def test_depois_de_mascarar_nao_sobra_pii_reconhecivel():
    rng = random.Random(20261029)
    for _ in range(300):
        cpf = _cpf_com_dv("".join(rng.choice("0123456789") for _ in range(9)))
        ddd = rng.choice(["11", "21", "31", "41", "51", "61", "71", "81"])
        celular = f"{ddd}9{rng.randrange(10**8):08d}"
        fixo = f"{ddd}{rng.randrange(2, 6)}{rng.randrange(10**7):07d}"
        forma = rng.choice(["{c}", "{f}", "({d}) {c4}-{c5}"])
        cpf_txt = rng.choice([cpf, f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"])
        tel = forma.format(c=celular, f=fixo, d=ddd, c4=celular[2:7], c5=celular[7:])
        saida = mascarar(f"cpf {cpf_txt} cel {tel} fim")
        assert not re.search(r"\d{8,}", saida), saida
        assert "[CPF]" in saida
        assert cpf not in saida and tel not in saida


def test_mascara_nao_deixa_digitos_de_cpf_com_separadores_estranhos():
    # espaços entre os grupos: pega pela regra geral
    saida = mascarar("cpf 529 982 247 25")
    assert "529" not in saida and "247" not in saida


def test_tipo_nao_string_recusado():
    with pytest.raises(TypeError):
        mascarar(None)  # type: ignore[arg-type]


# --- resistência a separadores (achado da revisão de segurança: pii_masking_bypass) ------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("cpf 123 . 456 / 789 -- 00 fim", "cpf [NUMERO] fim"),  # DV inválido: cai em [NUMERO], mas some inteiro
        ("cpf 1 2 3 4 5 6 7 8 9 0 9 fim", "cpf [CPF] fim"),  # 123.456.789-09 tem DV válido
        ("tel (11) 9 1234_5678 fim", "tel [TELEFONE] fim"),
        ("tel 1 1 9 1 2 3 4 5 6 7 8 fim", "tel [TELEFONE] fim"),
        ("tel +55 (11) 9.1234.5678 fim", "tel [TELEFONE] fim"),
        ("cpf 529,982,247,25 fim", "cpf [CPF] fim"),
        ("cpf 529\n982\n247\n25 fim", "cpf [CPF] fim"),  # quebra de linha entre os grupos
        ("cpf 529 / 982 / 247 / 25 fim", "cpf [CPF] fim"),
        ("cpf ５２９９８２２４７２５ fim", "cpf [CPF] fim"),  # dígitos de largura total
        ("tel ١١٩١٢٣٤٥٦٧٨ fim", "tel [TELEFONE] fim"),  # dígitos árabe-índicos (\d do Python casa com eles)
        ("cartão 1234  5678   9012    3456", "cartão [NUMERO]"),
        ("conta 1-2-3-4-5-6-7-8", "conta [NUMERO]"),
    ],
)
def test_separadores_estranhos_nao_furam_a_mascara(entrada, esperado):
    saida = mascarar(entrada)
    assert saida == esperado
    assert not re.search(r"[0-9\u0660-\u0669\uff10-\uff19]{2,}", saida)


@pytest.mark.parametrize(
    "texto",
    [
        "paguei R$ 1.234,56 ontem",
        "o total é R$ 1.234.567,89 no contrato",  # 9 dígitos, mas é dinheiro bem formado (centavos, 2 grupos de milhar)
        "entrada de R$ 150.000,00 e o resto depois",  # 8 dígitos
        "venceu em 29/10/2026 mesmo",
        "venceu em 29-10-2026 mesmo",
        "venceu em 29.10.2026 mesmo",
        "proposta 48213 aprovada",
        "proposta 4821 e contrato 77",
        "prazo de 84 meses a 1,85% ao mês, parcela 450,00",
        "das 08:00 às 20:00, de 2 a 6",
    ],
)
def test_valor_data_e_numero_curto_nao_sao_mascarados(texto):
    assert mascarar(texto) == texto


def test_data_com_texto_no_meio_nao_protege_a_pii():
    assert mascarar("vence 29/10/2026 e meu cpf 529.982.247-25") == "vence 29/10/2026 e meu cpf [CPF]"


def test_corrente_que_entra_ou_sai_do_trecho_isento_perde_a_isencao():
    """Sem letra no meio, data/dinheiro + outro número formam UMA corrente: a isenção cai e tudo é mascarado."""
    assert mascarar("29/10/2026 11912345678") == "[NUMERO]"
    assert mascarar("11912345678 29/10/2026") == "[NUMERO]"
    assert mascarar("R$ 1.234,56 12345678") == "R$ [NUMERO]"
    assert mascarar("R$ 1.234,56 e 12345678") == "R$ 1.234,56 e [NUMERO]"  # com letra no meio são duas correntes


def test_numero_de_onze_digitos_colado_a_R_cifrao_nao_vira_dinheiro():
    assert mascarar("R$ 52998224725") == "R$ [CPF]"


def test_idempotente_com_separadores_estranhos():
    primeira = mascarar("cpf 1 2 3 4 5 6 7 8 9 0 9 tel (11) 9 1234_5678")
    assert mascarar(primeira) == primeira


# --- a isenção de dinheiro/data não protege CPF, telefone nem número longo (segundo achado da revisão de segurança) ---------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("R$ 123.456.789-09", "R$ [CPF]"),  # CPF válido depois de «R$»
        ("R$ 52998224725", "R$ [CPF]"),
        ("R$ 11 91234-5678", "R$ [TELEFONE]"),
        ("R$ 11912345678", "R$ [TELEFONE]"),
        ("R$ 1.234.567.890,00", "R$ [NUMERO]"),  # 12 dígitos, 3 grupos de milhar: acima do limite de 11 dígitos
        ("R$ 123.456.789", "R$ [NUMERO]"),  # sem centavos não é dinheiro com 8+ dígitos
        ("R$ 12.345.678,90", "R$ [TELEFONE]"),  # 10 dígitos com cara de telefone: a classe forte vem antes da isenção
        ("R$ 99999-999", "R$ [CEP]"),
        ("valor R$ 450,00 e CPF 529.982.247-25", "valor R$ 450,00 e CPF [CPF]"),
    ],
)
def test_isencao_monetaria_nao_protege_cpf_telefone_nem_numero_longo(entrada, esperado):
    assert mascarar(entrada) == esperado


def test_classe_forte_vem_antes_da_isencao_de_data():
    # 11 dígitos de CPF válido escritos com cara de data não ganham isenção
    assert mascarar("52/99/822472 5") != "52/99/822472 5"
    assert mascarar("529-982-247-25") == "[CPF]"


# --- revisão 29/10: e-mail com letras Unicode, dígitos «de enfeite» e tempo linear --------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("joão@exemplo.test", "[EMAIL]"),  # «joã[EMAIL]» deixava o começo do nome para trás
        ("jõao@exemplo.test", "[EMAIL]"),  # «õ» decomposto (o + til combinante)
        ("contato: maria@exémplo.test.", "contato: [EMAIL]."),  # domínio com letra acentuada passava inteiro
        ("fulano＠exemplo.test", "[EMAIL]"),  # arroba de largura total
        ("fulano@exemplo．test", "[EMAIL]"),  # ponto de largura total
        ("fulano@exemplo。test", "[EMAIL]"),  # ponto ideográfico (o navegador/cliente de e-mail o trata como ponto)
        ("Fulano.De.Tal@EXEMPLO.TEST", "[EMAIL]"),
    ],
)
def test_email_com_letra_unicode_e_pontuacao_de_largura_total(entrada, esperado):
    assert mascarar(entrada) == esperado


@pytest.mark.parametrize(
    "entrada",
    [
        "⁵²⁹⁹⁸²²⁴⁷²⁵",  # sobrescritos: str.isdigit() sim, str.isdecimal() não, e a vista só trocava isdecimal
        "⑤②⑨⑨⑧②②④⑦②⑤",
        "₅₂₉₉₈₂₂₄₇₂₅",
        "⁵²⁹.⁹⁸².²⁴⁷-²⁵",
    ],
)
def test_cpf_com_digitos_sobrescritos_ou_circulados_e_mascarado(entrada):
    assert mascarar(entrada) == "[CPF]"


@pytest.mark.parametrize("texto", ["a" * 100_000, "a." * 50_000, "x@" * 50_000, "1-" * 50_000, "joão " * 20_000])
def test_mascara_roda_em_tempo_linear_no_tamanho_do_texto(texto):
    """O padrão de e-mail varria o resto da corrida de letras a cada posição: 100 mil letras levavam ~9 s (quadrático)."""
    import time

    inicio = time.perf_counter()
    mascarar(texto)
    assert time.perf_counter() - inicio < 2.0, "máscara não é linear: 100 mil caracteres não podem levar segundos"
