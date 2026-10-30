"""Estado da conversa (B1.1): JSON ≤ 2 KB sem campo desconhecido, só códigos e referências (nunca valores), e `ultimo_cliente_em`.

Sem PII: nomes de campo e códigos sintéticos; os "valores sigilosos" abaixo são marcadores.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from pydantic import ValidationError

from ia_atendimento.estado import (
    AtendimentoInexistente,
    EntradaInvalida,
    TransicaoInvalida,
    abrir,
    aguardar_cliente,
    iniciar,
    ler,
    octetos_como_jsonb,
)
from ia_atendimento.estado_conversa import (
    Contadores,
    EstadoConversa,
    estado_conversa_de_json,
    gravar_estado_conversa,
    janela_24h_aberta,
    ler_estado_conversa,
    registrar_mensagem_do_cliente,
)
from tests.banco import Banco
from tests.estado_apoio import entrada

SIGILOSO = "valor-sigiloso-zz9"


def _aberto(conn, relogio, versoes):
    res = abrir(
        conn,
        origem="n8n_braco",
        entrada=entrada(),
        versoes=versoes,
        modo_global="duble",
        chats_teste=frozenset(),
        faixa_esforco="media",
        comissao_esperada_brl=None,
        relogio=relogio,
    )
    v = iniciar(conn, res.atendimento_id, res.versao, chatbot_antes="desligado", chatbot_estado="desligado_pela_ia", relogio=relogio)
    return res.atendimento_id, v


def _maximo_permitido_pelos_campos() -> dict:
    """Preenche cada lista até o limite do próprio campo: sozinhos os campos passam, juntos estouram 2 KB."""
    nome = "n" * 40
    return {
        "fase": "E3",
        "campos_coletados": [nome] * 20,
        "campos_faltantes": [nome] * 20,
        "contexto_previo": [nome] * 10,
        "objecoes": [nome] * 10,
    }


# --- o modelo (sem banco) ---------------------------------------------------------------------------------------------------------


def test_estado_conversa_recusa_campo_desconhecido_e_acima_de_2kb():
    with pytest.raises(ValidationError):
        EstadoConversa(fase="E1", nome_do_cliente="x")
    with pytest.raises(EntradaInvalida) as erro:
        estado_conversa_de_json({"fase": "E1", "contadores": {"rodada": 1, "campo_novo": 2}})
    assert erro.value.campos == (("contadores.campo_novo", "extra_forbidden"),)
    estoura = _maximo_permitido_pelos_campos()
    with pytest.raises(EntradaInvalida) as erro:
        estado_conversa_de_json(estoura)
    assert "2 KB" in str(erro.value) or "(corpo)" in str(erro.value)
    pequeno = estado_conversa_de_json({"fase": "E3", "campos_coletados": ["renda", "banco"]})
    assert pequeno.campos_coletados == ("renda", "banco")


def _doc_com_tamanho(alvo: int) -> dict:
    """Documento válido campo a campo cujo `jsonb::text` mede exatamente `alvo` octetos (varre quantos itens de 40 + um item de 1..40)."""
    base = {"fase": "E3", "campos_coletados": ["a" * 40] * 20, "campos_faltantes": ["b" * 40] * 20}
    for cheios in range(0, 10):
        for resto in range(1, 41):
            doc = {**base, "contexto_previo": ["c" * 40] * cheios + ["d" * resto]}
            if octetos_como_jsonb(doc) == alvo:
                return doc
    raise AssertionError(f"não achei documento de {alvo} octetos")


def test_estado_conversa_exatamente_em_2048_octetos_passa_e_em_2049_nao():
    assert estado_conversa_de_json(_doc_com_tamanho(2048)).fase == "E3"
    with pytest.raises(EntradaInvalida):
        estado_conversa_de_json(_doc_com_tamanho(2049))


def test_estado_conversa_nao_vaza_o_valor_na_mensagem_de_erro():
    with pytest.raises(ValidationError) as erro:
        EstadoConversa(fase="E1", campos_coletados=(SIGILOSO.upper(),))
    assert SIGILOSO.upper() not in str(erro.value) and SIGILOSO not in str(erro.value).lower()
    with pytest.raises(EntradaInvalida) as erro2:
        estado_conversa_de_json({"fase": "E1", "segredo": SIGILOSO})
    assert SIGILOSO not in str(erro2.value) and SIGILOSO not in repr(erro2.value.campos)
    assert erro2.value.__context__ is None


@pytest.mark.parametrize(
    "corpo",
    [
        pytest.param({"fase": "E11"}, id="fase-fora-de-E0-E10"),
        pytest.param({"fase": "e1"}, id="fase-minuscula"),
        pytest.param({"fase": "E1", "campos_coletados": ["Nome Completo"]}, id="campo-com-espaco-e-maiuscula"),
        pytest.param({"fase": "E1", "campos_faltantes": ["renda_líquida"]}, id="acento"),
        pytest.param({"fase": "E1", "intencoes_recentes": ["a", "b", "c", "d"]}, id="mais-de-3-intencoes"),
        pytest.param({"fase": "E1", "contadores": {"rodada": -1}}, id="contador-negativo"),
        pytest.param({"fase": "E1", "contadores": {"rodada": "2"}}, id="contador-texto"),
        pytest.param({"fase": "E1", "oferta_corrente": {"banco": "FACTA", "oferta_id": "1", "oferta_versao": 0}}, id="oferta-versao-zero"),
        pytest.param(
            {"fase": "E1", "oferta_corrente": {"banco": "FACTA", "oferta_id": "1", "oferta_versao": 1, "valor": 1500}},
            id="oferta-com-valor",
        ),
        pytest.param({"fase": "E1", "confirmacao": {"estado": "talvez"}}, id="confirmacao-estado"),
        pytest.param({"fase": "E1", "pausa": {"retoma_fase": "E7"}}, id="pausa-em-E7"),
        pytest.param({"fase": "E1", "flags": {"Flag Grande": True}}, id="flag-com-nome-ruim"),
        pytest.param({"fase": "E1", "flags": {"f": "sim"}}, id="flag-nao-booleana"),
    ],
)
def test_estado_conversa_recusa_o_que_nao_e_codigo_referencia_ou_contador(corpo):
    with pytest.raises(EntradaInvalida):
        estado_conversa_de_json(corpo)


def test_estado_conversa_aceita_a_forma_completa_e_faz_ida_e_volta_em_json():
    completo = EstadoConversa(
        fase="E4",
        contadores=Contadores(rodada=3, falhas=1, t4_pagas=1),
        oferta_corrente={"banco": "FACTA", "oferta_id": "of-001", "oferta_versao": 2},
        opcoes_t5=("op-1", "op-2"),
        confirmacao={"estado": "pendente", "expira_em": datetime(2026, 11, 24, 13, 30, tzinfo=UTC)},
        campos_coletados=("renda",),
        campos_faltantes=("conta",),
        tentativa_t7={"estado": "reservada", "classe": "t7_nova", "n": 1},
        objecoes=("juros",),
        intencoes_recentes=("quer_proposta",),
        flags={"cliente_ja_enviou_doc": True},
        contexto_previo=("reabertura",),
        pausa={"agendamento_ref": "ag-01", "retoma_fase": "E3"},
    )
    assert estado_conversa_de_json(completo.para_json()) == completo


def test_para_json_omite_o_que_e_padrao_e_sempre_leva_a_fase():
    assert EstadoConversa(fase="E0").para_json() == {"fase": "E0"}
    assert EstadoConversa(fase="E2", contadores=Contadores(rodada=2)).para_json() == {"fase": "E2", "contadores": {"rodada": 2}}


@pytest.mark.banco
def test_contadores_do_json_nunca_repetem_coluna_de_atendimento(banco: Banco):
    """Fonte única: o que já é coluna (sem_avanco, turnos, ...) não pode morar também no JSON, ou os dois divergem."""
    with banco.sessao() as conn:
        colunas = {
            c
            for (c,) in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema='ia' AND table_name='atendimento'"
            )
        }
    assert colunas.isdisjoint(Contadores.model_fields)
    for coluna in ("sem_avanco", "corrigiveis", "contrapropostas", "turnos", "mensagens_enviadas", "lembretes_enviados"):
        with pytest.raises(ValidationError):
            Contadores(**{coluna: 1})


# --- leitura e gravação (banco) -----------------------------------------------------------------------------------------------------


@pytest.mark.banco
def test_atendimento_novo_le_fase_e0(db_conn, relogio, versoes):
    res = abrir(
        db_conn, origem="n8n_braco", entrada=entrada(), versoes=versoes, modo_global="duble", chats_teste=frozenset(),
        faixa_esforco="media", comissao_esperada_brl=None, relogio=relogio,
    )  # fmt: skip
    assert ler_estado_conversa(db_conn, res.atendimento_id) == EstadoConversa(fase="E0")


@pytest.mark.banco
def test_gravar_e_ler_estado_conversa_incrementa_versao_e_mantem_o_resto(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    antes = ler(db_conn, atd)
    novo = EstadoConversa(fase="E3", contadores=Contadores(rodada=2), campos_coletados=("renda",), campos_faltantes=("conta",))
    v2 = gravar_estado_conversa(db_conn, atd, v, novo, relogio=relogio)
    assert v2 == v + 1
    assert ler_estado_conversa(db_conn, atd) == novo
    depois = ler(db_conn, atd)
    assert (depois.fase, depois.estado, depois.lease_ate) == (
        "E3",
        "aberto",
        antes.lease_ate,
    )  # a fase gerada acompanha; o lease não é tocado
    assert depois.estado_conversa == novo.para_json()


@pytest.mark.banco
def test_gravar_com_versao_velha_e_conflito(db_conn, relogio, versoes):
    from ia_atendimento.estado import ConflitoVersao

    atd, v = _aberto(db_conn, relogio, versoes)
    with pytest.raises(ConflitoVersao):
        gravar_estado_conversa(db_conn, atd, v - 1, EstadoConversa(fase="E2"), relogio=relogio)


@pytest.mark.banco
def test_gravar_fase_e0_em_atendimento_aberto_e_recusado_pelo_check_cruzado(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    with pytest.raises(TransicaoInvalida) as erro:
        gravar_estado_conversa(db_conn, atd, v, EstadoConversa(fase="E0"), relogio=relogio)
    assert erro.value.restricao == "atendimento_conversa_check"


@pytest.mark.banco
def test_o_banco_tambem_recusa_estado_conversa_acima_de_2kb(banco: Banco, db_conn, relogio, versoes):
    """Defesa em profundidade: quem contorna o Pydantic (SQL direto) esbarra no CHECK do DDL."""
    atd, _ = _aberto(db_conn, relogio, versoes)
    grande = '{"fase": "E1", "x": "' + "y" * 2100 + '"}'
    with banco.sessao() as super_, pytest.raises(psycopg.errors.CheckViolation) as erro:
        super_.execute("UPDATE ia.atendimento SET estado_conversa = %s::jsonb WHERE atendimento_id = %s", (grande, atd))
    assert erro.value.diag.constraint_name == "atendimento_conversa_check"


@pytest.mark.banco
def test_ler_estado_conversa_de_atendimento_inexistente(db_conn):
    import uuid

    with pytest.raises(AtendimentoInexistente):
        ler_estado_conversa(db_conn, uuid.uuid4())


@pytest.mark.banco
def test_ler_estado_conversa_de_json_invalido_no_banco_nao_vaza_valor(banco: Banco, db_conn, relogio, versoes):
    atd, _ = _aberto(db_conn, relogio, versoes)
    with banco.sessao() as super_:
        super_.execute(
            "UPDATE ia.atendimento SET estado_conversa = jsonb_build_object('fase', 'E1', 'texto_livre', %s::text) WHERE atendimento_id = %s",
            (SIGILOSO, atd),
        )
    with pytest.raises(EntradaInvalida) as erro:
        ler_estado_conversa(db_conn, atd)
    assert SIGILOSO not in str(erro.value) and SIGILOSO not in repr(erro.value.campos)


# --- ultimo_cliente_em ----------------------------------------------------------------------------------------------------------


@pytest.mark.banco
def test_ultimo_cliente_em_so_avanca_e_nao_incrementa_versao(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    antes = ler(db_conn, atd)
    assert antes.ultimo_cliente_em is None
    t1 = relogio() - timedelta(hours=2)
    t2 = relogio() - timedelta(hours=1)
    assert registrar_mensagem_do_cliente(db_conn, atd, t1) == t1
    assert registrar_mensagem_do_cliente(db_conn, atd, t2) == t2
    assert registrar_mensagem_do_cliente(db_conn, atd, t1) == t2  # mensagem atrasada (fora de ordem) não recua a janela
    depois = ler(db_conn, atd)
    assert (depois.versao, depois.atualizado_em, depois.ultimo_cliente_em) == (v, antes.atualizado_em, t2)


@pytest.mark.banco
def test_ultimo_cliente_em_nao_disputa_o_cas_do_processador(db_conn, relogio, versoes):
    """O evento da mensagem escreve entre a leitura e a transição do turno sem derrubar a versão que o processador segura."""
    atd, v = _aberto(db_conn, relogio, versoes)
    registrar_mensagem_do_cliente(db_conn, atd, relogio() - timedelta(minutes=1))
    assert aguardar_cliente(db_conn, atd, v, relogio=relogio) == v + 1  # não levanta ConflitoVersao


@pytest.mark.banco
def test_ultimo_cliente_em_exige_fuso_e_atendimento_existente(db_conn, relogio, versoes):
    import uuid

    atd, _ = _aberto(db_conn, relogio, versoes)
    with pytest.raises(ValueError, match="fuso"):
        registrar_mensagem_do_cliente(db_conn, atd, datetime(2026, 11, 24, 10, 0))
    with pytest.raises(AtendimentoInexistente):
        registrar_mensagem_do_cliente(db_conn, uuid.uuid4(), relogio())


def test_janela_de_24h_so_abre_com_mensagem_do_cliente_ha_menos_de_24h():
    agora = datetime(2026, 11, 24, 13, 0, tzinfo=UTC)
    assert janela_24h_aberta(agora - timedelta(hours=23, minutes=59), agora)
    assert not janela_24h_aberta(agora - timedelta(hours=24), agora)
    assert not janela_24h_aberta(agora - timedelta(days=3), agora)
    assert not janela_24h_aberta(None, agora)  # desconhecido: só template
    assert janela_24h_aberta(agora + timedelta(seconds=5), agora)  # relógio da origem adiantado: não fecha a janela por isso
