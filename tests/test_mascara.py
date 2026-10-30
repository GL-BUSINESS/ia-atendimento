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
        ("CPF 529.982.247 25", "CPF [NUMERO]"),  # forma estranha: cai na regra geral de 8+ dígitos
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
