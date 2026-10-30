"""Tipos sem documento (S5, S6 da revisão automática de segurança no a421330): normalização antes de olhar os dígitos, e UUID sem allowlist cega.

Sintético: CPF `123.456.789-09` (exemplo conhecido da varredura) e sequências de dígitos de marcador.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import TypeAdapter, ValidationError

from ia_atendimento.estado import EntradaAtendimento
from ia_atendimento.modelos_conversa import OfertaCorrente, Pausa
from ia_atendimento.tipos import Codigo40, Referencia, Rotulo
from tests.estado_apoio import corpo_da_entrada

TIPOS = {"Codigo40": TypeAdapter(Codigo40), "Rotulo": TypeAdapter(Rotulo), "Referencia": TypeAdapter(Referencia)}


# --- S5: separadores no meio não escondem o documento -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tipo,valor",
    [
        ("Referencia", "123456789012"),  # 12 dígitos puros (antes só 11 e 14 eram vistos)
        ("Referencia", "012345678901"),  # 12 dígitos com zero à esquerda
        ("Referencia", "1234.5678.90.12"),
        ("Referencia", "12:345:678:901"),
        ("Referencia", "1234567890"),  # 10 dígitos: acima do teto do id numérico de sistema (9)
        ("Codigo40", "1234567890"),
        ("Codigo40", "123_456_789_01"),  # sublinhado também separa
        ("Codigo40", "12345_678901"),
        ("Codigo40", "123456789_012"),
        ("Rotulo", "12345.678901"),
        ("Rotulo", "123456-789012"),
        ("Rotulo", "1234567890"),
    ],
)
def test_s5_sequencia_de_10_ou_mais_digitos_e_recusada_mesmo_com_separador(tipo, valor):
    with pytest.raises(ValidationError):
        TIPOS[tipo].validate_python(valor)


@pytest.mark.parametrize("valor", ["12345 678901", "123456789 01", "12.345.678/0001-95"])
def test_s5_separadores_de_espaco_e_barra_tambem_sao_removidos_na_normalizacao(valor):
    from ia_atendimento.tipos import _sem_documento

    with pytest.raises(ValueError, match="documento"):
        _sem_documento(valor)  # o alfabeto dos tipos já barra espaço/barra; a normalização não depende dele


def test_s5_codigos_legitimos_com_poucos_digitos_seguem_validos():
    for tipo, valor in (
        ("Codigo40", "renda_2"),
        ("Codigo40", "t7_ok"),
        ("Rotulo", "200_300"),
        ("Referencia", "of-001"),
        ("Referencia", "482130000"),
    ):
        assert TIPOS[tipo].validate_python(valor) == valor


def test_s5_id_numerico_de_sistema_ate_9_digitos_passa_so_em_referencia():
    for oferta in ("115716", "48213", "999999999"):
        assert OfertaCorrente(banco="FACTA", oferta_id=oferta, oferta_versao=1).oferta_id == oferta
    with pytest.raises(ValidationError):
        OfertaCorrente(banco="FACTA", oferta_id="1000000000", oferta_versao=1)  # 10 dígitos
    with pytest.raises(ValidationError):
        TIPOS["Codigo40"].validate_python("999999999999")


# --- S6: UUID só parseado (versão e variante válidas) e só em campo de id --------------------------------------------------------------


@pytest.mark.parametrize(
    "forjado",
    [
        "12345678-9012-3456-7890-123456789012",  # variante '7': não é RFC 4122
        "12345678-9012-0456-8890-123456789012",  # versão '0'
        "12345678-9012-9456-8890-123456789012",  # versão '9' (inexistente)
        "00000000-0000-0000-0000-000000000000",  # nil
    ],
)
def test_s6_uuid_forjado_com_digitos_nao_passa_pela_allowlist(forjado):
    with pytest.raises(ValidationError):
        Pausa(agendamento_ref=forjado, retoma_fase="E3")
    with pytest.raises(ValidationError):
        OfertaCorrente(banco="FACTA", oferta_id=forjado, oferta_versao=1)


def test_s6_uuid_valido_continua_passando_em_campo_de_id():
    for _ in range(500):
        u = str(uuid.uuid4())
        assert Pausa(agendamento_ref=u, retoma_fase="E3").agendamento_ref == u


def test_s6_uuid_nao_e_allowlist_em_rotulo_de_perfil_nem_em_codigo():
    u = "0192f3a1-7c4e-7abc-8def-0123456789ab"  # uuid7 válido, com 10 dígitos seguidos no último grupo
    with pytest.raises(ValidationError):
        TIPOS["Rotulo"].validate_python(u)
    with pytest.raises(ValidationError):
        EntradaAtendimento(**corpo_da_entrada(perfil={"ref": u}))
