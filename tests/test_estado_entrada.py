"""Entrada do atendimento (B1.1): fingerprint do contrato 08 §4, validadores que reproduzem os CHECKs e `Mudancas` = GRANT do `ia_app`.

Sem PII: ids e operador sintéticos (`tests/estado_apoio.py`); os valores "sigilosos" abaixo são marcadores, não dados.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ia_atendimento.estado import (
    EntradaAtendimento,
    EntradaInvalida,
    Mudancas,
    entrada_de_corpo,
    entrada_fingerprint,
    idempotency_key,
)
from tests.banco import Banco
from tests.estado_apoio import CHAVE, OUTRA_PESSOA, OUTRO_CHAT, PESSOA, corpo_da_entrada, entrada

# --- fingerprint e identidade da entrada (contrato 08 §4) -----------------------------------------------------------------------


def test_fingerprint_vetor_dourado():
    """O vetor do contrato 08 §4: se a regra do canônico mudar, o hash muda e este teste reprova."""
    assert entrada_fingerprint(entrada()) == "b8da81fb3df655ca7f76f648613991e4a8291667ea7941b3a1c8d699d4636650"
    assert idempotency_key(CHAVE) == "87efe21cc58f3483825867fe9cfe0a4a2ebd36ecbc8be6dd454a5e47ed20726d"


def test_fingerprint_ignora_perfil_sessao_disparado_por_e_o_resto_instavel():
    base = entrada_fingerprint(entrada())
    outro = entrada(
        perfil={"banco": "C6"},
        perfil_versao=2,
        sessao_id="33333333-3333-7333-8333-333333333333",
        disparado_por="outra.pessoa@exemplo.invalid",
        motivo_escolha="outro",
        motivo_escolha_nota="sorteio manual",
        criterio_versao="c9.9",
        responsavel_antes="consultor.x",
        banco="3RN",
        produto="CLT",
        ultimo_cliente_em="2026-11-24T09:00:00-03:00",
    )
    assert entrada_fingerprint(outro) == base


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("pessoa_id", OUTRA_PESSOA),
        ("chat_id", OUTRO_CHAT),
        ("phone_id", "0123456789abcdef01234567"),
        ("clt_job_id", "5a1f0c3e-7b2d-4e9a-8c61-0d2f9b3a4e56"),
        ("gatilho", "esteira_parada"),
        ("chave_logica", "venda:00000000000000000000000000000001"),
        ("persona_id", "persona_teste"),
    ],
)
def test_fingerprint_inclui_a_identidade_do_episodio(campo, valor):
    mudou = entrada_fingerprint(entrada(**{campo: valor}))
    assert mudou != entrada_fingerprint(entrada())


def test_fingerprint_null_igual_a_ausente_e_ordem_das_chaves_nao_importa():
    sem_clt = corpo_da_entrada()
    sem_clt.pop("clt_job_id")
    com_none = {**sem_clt, "clt_job_id": None}
    invertido = dict(reversed(list(sem_clt.items())))
    fp = entrada_fingerprint(EntradaAtendimento(**sem_clt))
    assert entrada_fingerprint(EntradaAtendimento(**com_none)) == fp
    assert entrada_fingerprint(EntradaAtendimento(**invertido)) == fp


def test_fingerprint_normaliza_uuid_maiusculo():
    assert entrada_fingerprint(entrada(pessoa_id=PESSOA.upper())) == entrada_fingerprint(entrada())


# --- Mudancas = a lista do GRANT -------------------------------------------------------------------------------------------------


def test_mudancas_nao_tem_coluna_imutavel_nem_identidade():
    campos = set(Mudancas.model_fields)
    proibidas = {
        "faixa_esforco", "comissao_esperada_brl", "chat_id", "phone_id", "pessoa_id", "modo", "origem", "chave_logica",
        "idempotency_key", "entrada_fingerprint", "gatilho", "roteiro_versao", "regras_versao", "catalogo_versao", "motor_versao",
        "iniciado_em", "atendimento_id", "persona_id", "ultimo_cliente_em", "versao", "atualizado_em",
    }  # fmt: skip
    assert campos.isdisjoint(proibidas)
    with pytest.raises(ValidationError):
        Mudancas(faixa_esforco="alta")


@pytest.mark.banco
def test_mudancas_e_exatamente_a_lista_do_grant_de_ia_app(banco: Banco):
    with banco.sessao() as conn:
        grant = {
            c
            for (c,) in conn.execute(
                "SELECT column_name FROM information_schema.column_privileges WHERE table_schema='ia' AND table_name='atendimento' "
                "AND grantee='ia_app' AND privilege_type='UPDATE'"
            )
        }
    geridas_pelo_aplicar = {"versao", "atualizado_em"}  # o CAS e o relógio: `aplicar` os escreve, nunca o chamador
    escrita_a_parte = {"ultimo_cliente_em"}  # 0003: coluna com GRANT próprio, fora do CAS (estado_conversa.registrar_mensagem_do_cliente)
    assert grant == set(Mudancas.model_fields) | geridas_pelo_aplicar | escrita_a_parte


def test_mudancas_so_atualiza_o_que_foi_informado_inclusive_null():
    m = Mudancas(lease_ate=None)
    assert m.model_fields_set == {"lease_ate"}


@pytest.mark.parametrize(
    "campo,valor",
    [("motivo_desfecho", "Motivo Com Espaço"), ("contexto_codigos", ["ok", "COM MAIUSCULA"]), ("contexto_codigos", ["a"] * 11)],
)
def test_mudancas_valida_codigos_como_os_checks_do_ddl(campo, valor):
    with pytest.raises(ValidationError):
        Mudancas(**{campo: valor})


# --- entrada: validadores que reproduzem os CHECKs --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mudar",
    [
        pytest.param({"chat_id": "chat_com_sublinhado"}, id="chat-id-fora-de-24-hex"),
        pytest.param({"chat_id": "0123456789ABCDEF01234567"}, id="chat-id-maiusculo"),
        pytest.param({"phone_id": "curto"}, id="phone-id"),
        pytest.param({"pessoa_id": "nao-e-uuid"}, id="pessoa-id"),
        pytest.param({"chave_logica": "VENDA:xx"}, id="chave-logica"),
        pytest.param({"gatilho": "agendamento"}, id="agendamento-so-por-abrir_agendado"),
        pytest.param({"criterio_versao": None}, id="venda-exige-criterio"),
        pytest.param({"motivo_escolha": "outro", "motivo_escolha_nota": None}, id="outro-sem-nota"),
        pytest.param({"motivo_escolha": "mais_antigo_elegivel", "motivo_escolha_nota": "nota solta"}, id="nota-sem-outro"),
        pytest.param({"motivo_escolha": "outro", "motivo_escolha_nota": "x" * 81}, id="nota-grande"),
        pytest.param({"perfil": {"k": "x" * 2100}}, id="perfil-acima-de-2kb"),
        pytest.param({"banco": "facta"}, id="banco-minusculo"),
        pytest.param({"disparado_por": ""}, id="disparado-por-vazio"),
        pytest.param({"persona_id": "com espaço"}, id="persona"),
        pytest.param({"modo": "real"}, id="modo-so-aceita-teste"),
        pytest.param({"perfil_versao": 0}, id="perfil-versao"),
    ],
)
def test_entrada_recusa_o_que_os_checks_do_ddl_recusariam(mudar):
    with pytest.raises(ValidationError):
        entrada(**mudar)


def test_entrada_recusa_cpf_telefone_nome_e_qualquer_campo_desconhecido_sem_ecoar_o_valor():
    for campo, valor in (
        ("cpf", "000.000.0nn-00"),
        ("chat_number", "5511900000000"),
        ("nome", "Fulano de Tal"),
        ("grupo", "valor-sigiloso-zz9"),
    ):
        with pytest.raises(ValidationError) as erro:
            entrada(**{campo: valor})
        assert valor not in str(erro.value)  # hide_input_in_errors
        assert valor not in repr(erro.value.errors(include_input=False))


def test_entrada_de_corpo_devolve_so_nomes_de_campo_e_regra_e_nao_encadeia_a_causa():
    """`ValidationError.errors()/.json()` carregam o valor recusado; `entrada_de_corpo` é o que a API (422) usa."""
    sigilosos = {"cpf": "000.000.0nn-00", "chat_number": "5511900000000", "nome": "Fulano de Tal"}
    for campo, valor in sigilosos.items():
        with pytest.raises(EntradaInvalida) as erro:
            entrada_de_corpo({**corpo_da_entrada(), campo: valor})
        assert erro.value.campos == (("(campo desconhecido)", "extra_forbidden"),)
        for texto in (str(erro.value), repr(erro.value), repr(erro.value.args), repr(erro.value.campos)):
            assert valor not in texto
        assert erro.value.__cause__ is None and erro.value.__context__ is None  # a ValidationError (com o valor) não vai junto
    with pytest.raises(EntradaInvalida) as erro:
        entrada_de_corpo({**corpo_da_entrada(), "chat_id": "chat_com_sublinhado"})
    assert erro.value.campos == (("chat_id", "string_pattern_mismatch"),) and "sublinhado" not in str(erro.value)
    assert entrada_de_corpo(corpo_da_entrada()) == entrada()


def test_entrada_e_imutavel():
    e = entrada()
    with pytest.raises(ValidationError):
        e.chat_id = OUTRO_CHAT  # type: ignore[misc]
