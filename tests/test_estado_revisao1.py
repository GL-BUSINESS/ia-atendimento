"""Casos da revisão 1 de contexto limpo (docs/REVISAO-B1.1-3010.md): A1–A4, M1–M5, B1–B4, B6, T1, T2. Escritos antes da correção.

Valores "sigilosos" são sintéticos: CPF `123.456.789-09` (o de exemplo conhecido da varredura) e marcadores.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from ia_atendimento.estado import (
    LEASE_TURNO_S,
    DadoRecusado,
    EntradaAtendimento,
    EntradaInvalida,
    EstadoErro,
    Mudancas,
    TransicaoInvalida,
    abrir,
    aplicar,
    encerrar,
    entrada_de_corpo,
    entrada_fingerprint,
    iniciar,
    ler,
    renovar_lease,
    repassar,
)
from ia_atendimento.estado_conversa import (
    EstadoConversa,
    Pausa,
    estado_conversa_de_json,
    gravar_estado_conversa,
    janela_24h_aberta,
    registrar_mensagem_do_cliente,
)
from tests.estado_apoio import CHAT, corpo_da_entrada, entrada

CPF = "123.456.789-09"
CPF_DIGITOS = "12345678909"
FONE = "5511912345678"


def _abrir(conn, relogio, versoes, ent=None, **kw):
    kw.setdefault("modo_global", "duble")
    kw.setdefault("chats_teste", frozenset())
    return abrir(
        conn,
        origem="n8n_braco",
        entrada=ent or entrada(),
        versoes=versoes,
        faixa_esforco="media",
        comissao_esperada_brl=None,
        relogio=relogio,
        **kw,
    )


def _aberto(conn, relogio, versoes):
    res = _abrir(conn, relogio, versoes)
    v = iniciar(conn, res.atendimento_id, res.versao, chatbot_antes="desligado", chatbot_estado="desligado_pela_ia", relogio=relogio)
    return res.atendimento_id, v


# --- A1: encerrado é absorvente -------------------------------------------------------------------------------------------------


@pytest.mark.banco
def test_a1_encerrado_e_absorvente_tambem_via_aplicar(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    v = encerrar(db_conn, atd, v, desfecho="sem_venda", motivo="fim", relogio=relogio)
    ressuscitar = Mudancas(estado="aberto", desfecho=None, encerrado_em=None, lease_ate=relogio() + timedelta(minutes=5))
    with pytest.raises(TransicaoInvalida):
        aplicar(db_conn, atd, v, ressuscitar, agora=relogio())
    assert ler(db_conn, atd).estado == "encerrado"


# --- A2: estado_conversa tipado -------------------------------------------------------------------------------------------------


def test_a2_mudancas_nao_aceita_estado_conversa_fora_do_schema():
    with pytest.raises(ValidationError):
        Mudancas(estado_conversa={"fase": "E1", "cpf": CPF_DIGITOS})
    assert Mudancas(estado_conversa=EstadoConversa(fase="E1")).estado_conversa == EstadoConversa(fase="E1")


# --- A3: ultimo_cliente_em contra o relógio -------------------------------------------------------------------------------------


@pytest.mark.banco
def test_a3_ultimo_cliente_em_no_futuro_e_recusado(db_conn, relogio, versoes):
    with pytest.raises(EntradaInvalida):
        _abrir(db_conn, relogio, versoes, entrada(ultimo_cliente_em=relogio() + timedelta(days=30)))
    assert db_conn.execute("SELECT count(*) FROM ia.atendimento").fetchone() == (0,)
    ok = _abrir(
        db_conn, relogio, versoes, entrada(ultimo_cliente_em=relogio() + timedelta(minutes=4))
    )  # relógio de origem adiantado: tolera 5 min
    assert ok.estado == "reservado"


@pytest.mark.banco
def test_a3_registrar_mensagem_no_futuro_e_recusado_e_nao_grava(db_conn, relogio, versoes):
    r = _abrir(db_conn, relogio, versoes)
    with pytest.raises(ValueError, match="futuro"):
        registrar_mensagem_do_cliente(db_conn, r.atendimento_id, relogio() + timedelta(days=3650), relogio=relogio)
    assert ler(db_conn, r.atendimento_id).ultimo_cliente_em is None


def test_a3_janela_nao_abre_com_ultimo_cliente_em_no_futuro(relogio):
    assert not janela_24h_aberta(relogio() + timedelta(days=30), relogio())
    assert janela_24h_aberta(relogio() + timedelta(minutes=4), relogio())


# --- A4: tradutor único de erro do banco ------------------------------------------------------------------------------------------


@pytest.mark.banco
def test_a4_abrir_nao_deixa_psycopg_cru_nem_a_linha_na_mensagem(db_conn, relogio, versoes):
    """Quem contorna o Pydantic (`model_construct`) cai no banco: o erro sai traduzido, sem 'Failing row' nem as chaves do perfil."""
    gigante = EntradaAtendimento.model_construct(**{**corpo_da_entrada(), "perfil": {"a": [1e22] * 280}})
    nan = EntradaAtendimento.model_construct(**{**corpo_da_entrada(), "perfil": {"renda_cliente_12345": float("nan")}})
    for ent in (gigante, nan):
        with pytest.raises(EstadoErro) as e:
            _abrir(db_conn, relogio, versoes, ent)
        assert isinstance(e.value, DadoRecusado) and "Failing row" not in str(e.value) and "renda_cliente_12345" not in str(e.value)
        assert e.value.__context__ is None and e.value.__cause__ is None
    assert db_conn.execute("SELECT count(*) FROM ia.atendimento").fetchone() == (0,)


def test_a4_perfil_com_float_e_recusado_na_entrada():
    for perfil in ({"a": float("nan")}, {"a": float("inf")}, {"a": 1.5}, {"a": [1e22] * 280}):
        with pytest.raises(ValidationError):
            entrada(perfil=perfil)


@pytest.mark.banco
def test_a4_origem_fora_do_padrao_e_recusada_antes_do_banco(db_conn, relogio, versoes):
    with pytest.raises(EntradaInvalida):
        abrir(
            db_conn, origem="N8N", entrada=entrada(), versoes=versoes, modo_global="duble", chats_teste=frozenset(), faixa_esforco="media",
            comissao_esperada_brl=None, relogio=relogio,
        )  # fmt: skip


@pytest.mark.banco
def test_a4_aplicar_traduz_not_null_e_estado_conversa_vazio(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    with pytest.raises(ValueError) as e:  # `{}` não é EstadoConversa (fase obrigatória): barrado antes do banco
        aplicar(db_conn, atd, v, Mudancas(estado_conversa={}), agora=relogio())
    assert "Failing row" not in str(e.value)
    nulo = Mudancas.model_construct(_fields_set={"turnos"}, turnos=None)  # contorna o validador: NOT NULL estoura no banco
    with pytest.raises(DadoRecusado) as e2:
        aplicar(db_conn, atd, v, nulo, agora=relogio())
    assert "Failing row" not in str(e2.value) and e2.value.__context__ is None
    assert ler(db_conn, atd).versao == v


# --- M1/M2: códigos, referências e perfil sem documento ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "corpo",
    [
        pytest.param({"fase": "E1", "campos_coletados": [CPF_DIGITOS]}, id="campo-11-digitos"),
        pytest.param({"fase": "E1", "objecoes": [FONE]}, id="objecao-telefone"),
        pytest.param({"fase": "E1", "flags": {FONE: True}}, id="flag-telefone"),
        pytest.param(
            {"fase": "E1", "oferta_corrente": {"banco": "FACTA", "oferta_id": CPF, "oferta_versao": 1}}, id="referencia-cpf-mascarado"
        ),
        pytest.param({"fase": "E1", "opcoes_t5": [CPF_DIGITOS]}, id="opcao-cpf"),
    ],
)
def test_m1_codigo_e_referencia_nao_podem_ser_documento(corpo):
    with pytest.raises(EntradaInvalida):
        estado_conversa_de_json(corpo)


@pytest.mark.parametrize(
    "campo,valor", [("motivo_desfecho", CPF_DIGITOS), ("contexto_codigos", ("ok", FONE)), ("sinais_cliente", (CPF_DIGITOS,))]
)
def test_m1_codigos_da_mudanca_tambem_recusam_documento(campo, valor):
    with pytest.raises(ValidationError):
        Mudancas(**{campo: valor})


def test_m1_codigo_legitimo_com_poucos_digitos_continua_valido():
    ok = estado_conversa_de_json(
        {"fase": "E1", "campos_coletados": ["renda_2"], "oferta_corrente": {"banco": "FACTA", "oferta_id": "of-001", "oferta_versao": 3}}
    )
    assert ok.oferta_corrente.oferta_id == "of-001"


@pytest.mark.parametrize(
    "perfil",
    [
        pytest.param({"cpf": CPF}, id="cpf-no-valor"),
        pytest.param({"nome": "Fulano da Silva"}, id="texto-livre"),
        pytest.param({"telefone": FONE}, id="telefone"),
        pytest.param({"cpf": int(CPF_DIGITOS)}, id="cpf-como-inteiro"),
        pytest.param({"Nome Completo": "x"}, id="chave-fora-do-padrao"),
        pytest.param({FONE: "x"}, id="chave-telefone"),
        pytest.param({"a": {"b": "c"}}, id="aninhado"),
        pytest.param({"a": ["x"]}, id="lista"),
    ],
)
def test_m2_perfil_so_aceita_rotulos_curtos_sem_documento(perfil):
    with pytest.raises(ValidationError):
        entrada(perfil=perfil)


def test_m2_perfil_do_contrato_continua_valido():
    assert (
        entrada(perfil={"banco": "FACTA", "faixa_parcela": "200_300", "idade_min": 42, "tem_margem": True, "x": None}).perfil["idade_min"]
        == 42
    )


# --- M3: repassado só a partir de repassando ---------------------------------------------------------------------------------------


@pytest.mark.banco
def test_m3_repassado_so_a_partir_de_repassando(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    with pytest.raises(TransicaoInvalida):
        encerrar(db_conn, atd, v, desfecho="repassado", motivo="x", relogio=relogio)
    v = repassar(db_conn, atd, v, modo="fila", motivo="pediu_humano", relogio=relogio)
    encerrar(db_conn, atd, v, desfecho="repassado", motivo="pediu_humano", relogio=relogio)


@pytest.mark.banco
def test_m3_devolucao_da_s2_e_a_unica_excecao(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    encerrar(db_conn, atd, v, desfecho="repassado", motivo="devolvido_pela_s2", relogio=relogio)
    assert ler(db_conn, atd).desfecho == "repassado"


# --- M4: lease ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.banco
def test_m4_renovar_lease_e_transicao_com_cas(db_conn, relogio, versoes):
    from ia_atendimento.estado import ConflitoVersao

    atd, v = _aberto(db_conn, relogio, versoes)
    relogio.avancar(minutes=4)
    v2 = renovar_lease(db_conn, atd, v, relogio=relogio)
    a = ler(db_conn, atd)
    assert (v2, a.estado, a.lease_ate) == (v + 1, "aberto", relogio() + timedelta(seconds=LEASE_TURNO_S))
    with pytest.raises(ConflitoVersao):
        renovar_lease(db_conn, atd, v, relogio=relogio)
    v3 = encerrar(db_conn, atd, v2, desfecho="sem_venda", motivo="fim", relogio=relogio)
    with pytest.raises(TransicaoInvalida):
        renovar_lease(db_conn, atd, v3, relogio=relogio)


# --- M5: chats_teste --------------------------------------------------------------------------------------------------------------


@pytest.mark.banco
def test_m5_chats_teste_string_e_recusada(db_conn, relogio, versoes):
    with pytest.raises(TypeError):
        _abrir(db_conn, relogio, versoes, entrada(), chats_teste="xx" + CHAT + "yy")
    with pytest.raises(EntradaInvalida):
        _abrir(db_conn, relogio, versoes, entrada(), chats_teste=["nao-e-24-hex"])


# --- T1: gravar em encerrado; T2: UUID maiúsculo no fingerprint ----------------------------------------------------------------------


@pytest.mark.banco
def test_t1_gravar_estado_conversa_em_encerrado_e_recusado(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    v = encerrar(db_conn, atd, v, desfecho="sem_venda", motivo="fim", relogio=relogio)
    with pytest.raises(TransicaoInvalida):
        gravar_estado_conversa(db_conn, atd, v, EstadoConversa(fase="E2"), relogio=relogio)


def test_t2_fingerprint_normaliza_uuid_com_letras_e_bate_com_o_literal():
    esperado = "d6883c70251373c6da3324efdc7e2c72e709e5350c028ffcc1739bcf6d6a6bfd"  # calculado fora do código, com pessoa_id em minúsculas
    assert entrada_fingerprint(entrada(pessoa_id="aaaaaaaa-bbbb-7ccc-8ddd-eeeeeeeeeeee")) == esperado
    assert entrada_fingerprint(entrada(pessoa_id="AAAAAAAA-BBBB-7CCC-8DDD-EEEEEEEEEEEE")) == esperado


# --- B1–B4, B6 -------------------------------------------------------------------------------------------------------------------


@pytest.mark.banco
def test_b1_aplicar_exige_agora_com_fuso(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    with pytest.raises(ValueError, match="fuso"):
        aplicar(db_conn, atd, v, Mudancas(sem_avanco=1), agora=datetime(2026, 11, 24, 13, 0))


def test_b2_erro_de_corpo_nao_ecoa_nome_de_chave_do_cliente():
    with pytest.raises(EntradaInvalida) as e:
        entrada_de_corpo({**corpo_da_entrada(), CPF: "x"})
    assert CPF not in str(e.value) and CPF not in repr(e.value.campos) and e.value.campos == (("(campo desconhecido)", "extra_forbidden"),)
    with pytest.raises(EntradaInvalida) as e2:
        estado_conversa_de_json({"fase": "E1", "flags": {CPF_DIGITOS: "Fulano"}})
    assert CPF_DIGITOS not in str(e2.value) and CPF_DIGITOS not in repr(e2.value.campos)


@pytest.mark.banco
def test_b3_transicao_com_motivo_invalido_levanta_entrada_invalida_sem_valor(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    with pytest.raises(EntradaInvalida) as e:
        repassar(db_conn, atd, v, modo="fila", motivo=f"CPF {CPF}", relogio=relogio)
    assert CPF not in str(e.value) and CPF not in repr(e.value.campos)
    with pytest.raises(EntradaInvalida):
        repassar(db_conn, atd, v, modo="qualquer", motivo="m", relogio=relogio)


@pytest.mark.banco
def test_b4_gravar_nao_pula_para_e10_nem_traz_pausa_fora_de_pausado(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    for invalido in (EstadoConversa(fase="E10"), EstadoConversa(fase="E3", pausa=Pausa(retoma_fase="E3")), EstadoConversa(fase="E0")):
        with pytest.raises(TransicaoInvalida) as e:
            gravar_estado_conversa(db_conn, atd, v, invalido, relogio=relogio)
        assert e.value.restricao == "atendimento_fase_estado_check" or e.value.restricao == "atendimento_conversa_check"
    assert gravar_estado_conversa(db_conn, atd, v, EstadoConversa(fase="E9"), relogio=relogio) == v + 1


@pytest.mark.parametrize("campo", ["turnos", "mensagens_enviadas", "lembretes_enviados", "ordem_consumida"])
def test_b6_inteiro_acima_de_int4_e_recusado(campo):
    with pytest.raises(ValidationError):
        Mudancas(**{campo: 2**40})
