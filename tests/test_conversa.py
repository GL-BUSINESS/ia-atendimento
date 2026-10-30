"""Conversa cifrada (B1.2, sp01 T4): máscara antes de cifrar, AES-GCM com AAD completa, resumo sem dígito e janela de 24 h."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ia_atendimento.cifra import ChaveDesconhecida, FalhaAoDecifrar
from ia_atendimento.conversa import (
    LIMITE_TROCA,
    ChaveForaDoMes,
    NomesIndisponiveis,
    ResumoInvalido,
    TextoVazio,
    chave_id_do_mes,
    gravar_resumo,
    gravar_troca,
    ler_trocas,
    texto_livre_permitido,
)
from tests.apoio_b12 import AGORA, CPF_SINTETICO, MARCADOR, OUTRO_CHAT, chave_aleatoria, chaveiro_com, novo_atendimento

pytest_plugins = ["tests.apoio_b12"]

TELEFONE = "(11) 91234-5678"
EMAIL = "fulano@exemplo.invalid"
CEP = "01310-100"
UUID_ = "01a18a0a-6522-722b-8bf2-cced4767f1aa"


@pytest.fixture
def atd(conn_app):
    return novo_atendimento(conn_app)


def _troca(conn, atd, chaveiro, texto, remetente="cliente", **kw):
    return gravar_troca(conn, atd, remetente=remetente, texto=texto, chaveiro=chaveiro, **{"nomes": (), "agora": AGORA, **kw})


def test_cifra_ida_e_volta_e_o_texto_sai_mascarado(conn_app, atd, chaveiro):
    seq = _troca(conn_app, atd, chaveiro, f"meu cpf é {CPF_SINTETICO}")
    assert seq == 1
    conversa = ler_trocas(conn_app, atd, chaveiro=chaveiro)
    assert [t.texto for t in conversa.mensagens] == ["meu cpf é [CPF]"]
    assert conversa.mensagens[0].remetente == "cliente"


@pytest.mark.parametrize(
    ("bruto", "marcador"),
    [
        (f"cpf {CPF_SINTETICO}", "[CPF]"),
        (f"liga {TELEFONE}", "[TELEFONE]"),
        (f"escreve {EMAIL}", "[EMAIL]"),
        (f"cep {CEP}", "[CEP]"),
        (f"id {UUID_}", "[UUID]"),
        ("conta 123456789012", "[NUMERO]"),
    ],
)
def test_mascarar_cobre_cpf_telefone_email_cep_uuid_e_8_digitos(conn_app, atd, chaveiro, bruto, marcador):
    _troca(conn_app, atd, chaveiro, bruto)
    texto = ler_trocas(conn_app, atd, chaveiro=chaveiro).mensagens[0].texto
    assert marcador in texto
    for pedaco in (CPF_SINTETICO, TELEFONE, EMAIL, CEP, UUID_, "123456789012"):
        assert pedaco not in texto


def test_nome_do_cliente_e_mascarado_quando_informado(conn_app, atd, chaveiro):
    _troca(conn_app, atd, chaveiro, "sou a Maria Souza", nomes=("Maria Souza",))
    assert ler_trocas(conn_app, atd, chaveiro=chaveiro).mensagens[0].texto == "sou a [NOME]"


def test_banco_nao_contem_o_texto(banco, conn_app, atd, chaveiro):
    """Grep no dump de TODAS as tabelas do schema `ia`: o marcador nunca aparece em claro (nem em hex do bytea)."""
    _troca(conn_app, atd, chaveiro, f"quero reduzir a {MARCADOR} do emprestimo")
    _troca(conn_app, atd, chaveiro, f"entendi, vou olhar a {MARCADOR}", remetente="ia")
    alvos = [MARCADOR, MARCADOR.encode().hex()]
    with banco.sessao() as admin:  # superusuário: lê tudo
        tabelas = [r[0] for r in admin.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'ia'").fetchall()]
        assert "conversa_cifrada" in tabelas and "passo" in tabelas
        for tabela in tabelas:
            dump = " ".join(r[0] for r in admin.execute(f"SELECT t::text FROM ia.{tabela} t").fetchall())
            for alvo in alvos:
                assert alvo not in dump, f"texto em claro em ia.{tabela}"
    assert ler_trocas(conn_app, atd, chaveiro=chaveiro).mensagens[0].texto.count(MARCADOR) == 1  # mas o runtime lê de volta


def test_aad_trocada_nao_decifra(banco, conn_app, atd, chaveiro):
    """Copiar a linha para outro atendimento, outro seq ou outro remetente quebra a tag GCM (a AAD é parte do que foi cifrado)."""
    outro = novo_atendimento(conn_app, chat=OUTRO_CHAT)
    _troca(conn_app, atd, chaveiro, "primeira")
    _troca(conn_app, atd, chaveiro, "segunda")
    with banco.sessao() as admin:
        admin.execute("UPDATE ia.conversa_cifrada SET atendimento_id = %s WHERE atendimento_id = %s AND seq = 2", (outro, atd))
    with pytest.raises(FalhaAoDecifrar):  # outro atendimento
        ler_trocas(conn_app, outro, chaveiro=chaveiro)
    with banco.sessao() as admin:
        admin.execute("UPDATE ia.conversa_cifrada SET atendimento_id = %s, seq = 9 WHERE atendimento_id = %s", (atd, outro))
    with pytest.raises(FalhaAoDecifrar):  # outro seq
        ler_trocas(conn_app, atd, chaveiro=chaveiro)
    with banco.sessao() as admin:
        admin.execute("UPDATE ia.conversa_cifrada SET seq = 2, remetente = 'ia' WHERE seq = 9")
    with pytest.raises(FalhaAoDecifrar):  # outro remetente
        ler_trocas(conn_app, atd, chaveiro=chaveiro)


def test_nonce_nunca_repete(conn_app, atd, chaveiro):
    for i in range(150):
        _troca(conn_app, atd, chaveiro, f"mensagem {i}")
    nonces = [bytes(r[0]) for r in conn_app.execute("SELECT nonce FROM ia.conversa_cifrada").fetchall()]
    assert len(nonces) == 150 and len(set(nonces)) == 150
    assert {len(n) for n in nonces} == {12}


def test_chave_id_gravado_e_o_mensal_e_a_linha_guarda_criada_e_apagar_em(conn_app, atd, chaveiro):
    assert chave_id_do_mes(AGORA) == chaveiro.vigente == 2  # 1 = out/2026, 2 = nov/2026
    _troca(conn_app, atd, chaveiro, "oi")
    linha = conn_app.execute("SELECT chave_id, apagar_em - criada_em, mascarado, tipo FROM ia.conversa_cifrada").fetchone()
    assert linha == (2, timedelta(days=30), True, "mensagem")


def test_chave_id_do_mes_sequencial_a_partir_de_out_2026():

    assert chave_id_do_mes(datetime(2026, 10, 1, tzinfo=UTC)) == 1
    assert chave_id_do_mes(datetime(2026, 12, 31, 23, tzinfo=UTC)) == 3
    assert chave_id_do_mes(datetime(2027, 10, 5, tzinfo=UTC)) == 13
    with pytest.raises(ValueError, match="anterior"):
        chave_id_do_mes(datetime(2026, 9, 30, tzinfo=UTC))


def test_chave_id_descartado_omite_a_linha_e_nao_derruba_o_turno(conn_app, atd, tmp_path):
    k1, k2 = chave_aleatoria(), chave_aleatoria()
    velho = chaveiro_com(tmp_path, {1: k1, 2: k2}, vigente=1, nome="velho.json")
    novo = chaveiro_com(tmp_path, {1: k1, 2: k2}, vigente=2, nome="novo.json")
    so_novo = chaveiro_com(tmp_path, {2: k2}, vigente=2, nome="so_novo.json")  # a chave de out/2026 foi descartada
    _troca(conn_app, atd, velho, "mensagem de outubro", agora=datetime(2026, 10, 15, tzinfo=UTC))
    _troca(conn_app, atd, novo, "mensagem de novembro")
    completa = ler_trocas(conn_app, atd, chaveiro=novo)
    assert [t.texto for t in completa.mensagens] == ["mensagem de outubro", "mensagem de novembro"] and completa.omitidas == 0
    descartada = ler_trocas(conn_app, atd, chaveiro=so_novo)
    assert [t.texto for t in descartada.mensagens] == ["mensagem de novembro"] and descartada.omitidas == 1
    with pytest.raises(ChaveDesconhecida):
        so_novo.decifrar(1, b"\x00" * 12, b"\x00" * 20, atd, seq=1, remetente="cliente", tipo="mensagem")


def test_ler_conversa_devolve_resumo_mais_ultimas_3_trocas(conn_app, atd, chaveiro):
    for i in range(1, 9):
        _troca(conn_app, atd, chaveiro, f"fala {i} " + "x" * 400, remetente="cliente" if i % 2 else "ia")
    gravar_resumo(
        conn_app,
        atd,
        texto="cliente quer reduzir a parcela e prefere falar de manha",
        cobre_ate_seq=4,
        agora=AGORA,
        chaveiro=chaveiro,
        nomes=(),
    )
    conversa = ler_trocas(conn_app, atd, chaveiro=chaveiro)
    assert conversa.resumo == "cliente quer reduzir a parcela e prefere falar de manha"
    assert [t.seq for t in conversa.mensagens] == [3, 4, 5, 6, 7, 8]  # 3 trocas = 6 mensagens; o resumo (seq 9) não é mensagem
    assert all(len(t.texto) <= 280 for t in conversa.mensagens)
    assert ler_trocas(conn_app, atd, chaveiro=chaveiro, trocas=1).mensagens[0].seq == 7


def test_resumo_com_digito_e_rejeitado_e_mantem_o_anterior(conn_app, atd, chaveiro):
    _troca(conn_app, atd, chaveiro, "oi")
    gravar_resumo(conn_app, atd, texto="prefere contato de manha", cobre_ate_seq=1, agora=AGORA, chaveiro=chaveiro, nomes=())
    for ruim in ("quer parcela de 300 reais", "ligar às ① hora", "ligar depois do dia ٣", "x" + "palavra " * 61):
        with pytest.raises(ResumoInvalido) as erro:
            gravar_resumo(conn_app, atd, texto=ruim, cobre_ate_seq=1, agora=AGORA, chaveiro=chaveiro, nomes=())
        assert "300" not in str(erro.value)
    assert ler_trocas(conn_app, atd, chaveiro=chaveiro).resumo == "prefere contato de manha"
    assert conn_app.execute("SELECT count(*) FROM ia.conversa_cifrada WHERE tipo = 'resumo'").fetchone() == (1,)


def test_resumo_nao_leva_nome_nem_pii_e_o_vigente_e_o_de_maior_seq(conn_app, atd, chaveiro):
    _troca(conn_app, atd, chaveiro, "oi")
    with pytest.raises(ResumoInvalido):
        gravar_resumo(
            conn_app, atd, texto="Maria Souza prefere manha", cobre_ate_seq=1, agora=AGORA, chaveiro=chaveiro, nomes=("Maria Souza",)
        )
    with pytest.raises(ResumoInvalido):
        gravar_resumo(conn_app, atd, texto=f"escreve para {EMAIL}", cobre_ate_seq=1, agora=AGORA, chaveiro=chaveiro, nomes=())
    with pytest.raises(ResumoInvalido):  # cobre_ate_seq além do que existe
        gravar_resumo(conn_app, atd, texto="prefere manha", cobre_ate_seq=5, agora=AGORA, chaveiro=chaveiro, nomes=())
    gravar_resumo(conn_app, atd, texto="prefere manha", cobre_ate_seq=1, agora=AGORA, chaveiro=chaveiro, nomes=())
    _troca(conn_app, atd, chaveiro, "ola", remetente="ia")
    gravar_resumo(conn_app, atd, texto="prefere tarde", cobre_ate_seq=3, agora=AGORA, chaveiro=chaveiro, nomes=())
    assert ler_trocas(conn_app, atd, chaveiro=chaveiro).resumo == "prefere tarde"
    linha = conn_app.execute("SELECT remetente, passo_ordem, cobre_ate_seq FROM ia.conversa_cifrada WHERE seq = 4").fetchone()
    assert linha == ("ia", None, 3)


def test_substituto_dado_pix_nao_grava_o_valor(conn_app, atd, chaveiro):
    _troca(conn_app, atd, chaveiro, "minha chave pix e 00000001234", substituto="[dado:pix]")
    assert ler_trocas(conn_app, atd, chaveiro=chaveiro).mensagens[0].texto == "[dado:pix]"
    with pytest.raises(ValueError, match="substituto"):
        _troca(conn_app, atd, chaveiro, "x", substituto="qualquer coisa")


def test_texto_vazio_ou_invalido_e_recusado_sem_eco(conn_app, atd, chaveiro):
    with pytest.raises(TextoVazio):
        _troca(conn_app, atd, chaveiro, "   ")
    with pytest.raises(ValueError, match="remetente") as erro:
        _troca(conn_app, atd, chaveiro, f"segredo {MARCADOR}", remetente="vendedor")
    assert MARCADOR not in str(erro.value)
    assert conn_app.execute("SELECT count(*) FROM ia.conversa_cifrada").fetchone() == (0,)


def test_texto_longo_e_truncado_depois_da_mascara(conn_app, atd, chaveiro):
    _troca(conn_app, atd, chaveiro, "a" * (LIMITE_TROCA + 500))
    assert len(ler_trocas(conn_app, atd, chaveiro=chaveiro, trocas=1).mensagens[0].texto) == 280  # leitura corta em 280
    chave_id, nonce, cifra = conn_app.execute("SELECT chave_id, nonce, cifra FROM ia.conversa_cifrada WHERE seq = 1").fetchone()
    guardado = chaveiro.decifrar(chave_id, bytes(nonce), bytes(cifra), atd, seq=1, remetente="cliente", tipo="mensagem")
    assert len(guardado) == LIMITE_TROCA  # o que vai cifrado é cortado em 4000
    seq = _troca(conn_app, atd, chaveiro, "b" * 10)
    assert seq == 2


def test_texto_livre_bloqueado_com_24h_ou_mais():
    ultimo = AGORA
    assert texto_livre_permitido(AGORA + timedelta(hours=23, minutes=59, seconds=59), ultimo) is True
    assert texto_livre_permitido(AGORA + timedelta(hours=24), ultimo) is False  # exatamente 24 h já é «≥ 24 h»
    assert texto_livre_permitido(AGORA + timedelta(days=3), ultimo) is False
    assert texto_livre_permitido(AGORA, None) is False  # sem data do último cliente: fail-closed (só template)
    with pytest.raises(ValueError, match="fuso"):
        texto_livre_permitido(AGORA.replace(tzinfo=None), ultimo)


def test_ultimo_cliente_em_no_futuro_nao_abre_a_janela_a4():
    """Relógio do cliente adiantado (ou dado corrompido) não pode manter a janela aberta para sempre: tolera 5 min, não 30 dias."""
    assert texto_livre_permitido(AGORA, AGORA + timedelta(minutes=4)) is True
    assert texto_livre_permitido(AGORA, AGORA + timedelta(minutes=6)) is False
    assert texto_livre_permitido(AGORA, AGORA + timedelta(days=30)) is False


@pytest.mark.xfail(
    reason="ultimo_cliente_em chega na migração 0003 da B1.1 (feat/b1-1-estado); dono: quem integrar a B1.1 (feat/b1-1-estado) remove esta marca; strict=True o lembra",
    strict=True,
)
def test_coluna_ultimo_cliente_em_existe_no_atendimento(conn_app):
    colunas = {
        r[0]
        for r in conn_app.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = 'ia' AND table_name = 'atendimento'"
        ).fetchall()
    }
    assert "ultimo_cliente_em" in colunas


# --- correções da revisão 1 (A2, M1, M2, M3) -------------------------------------------------------------------------------------


def test_repr_de_troca_e_conversa_nao_vaza_o_texto_decifrado_a2(conn_app, atd, chaveiro):
    _troca(conn_app, atd, chaveiro, f"quero a {MARCADOR}")
    gravar_resumo(conn_app, atd, texto="prefere manha", cobre_ate_seq=1, agora=AGORA, chaveiro=chaveiro, nomes=())
    conversa = ler_trocas(conn_app, atd, chaveiro=chaveiro)
    assert conversa.mensagens[0].texto.count(MARCADOR) == 1
    assert MARCADOR not in repr(conversa) + str(conversa) + repr(conversa.mensagens[0])
    assert "prefere manha" not in repr(conversa)


def test_sem_nomes_nao_grava_texto_de_cliente_nem_resumo_m3(conn_app, atd, chaveiro):
    with pytest.raises(TypeError):  # `nomes` não tem default: esquecer é erro, não «ninguém tem nome»
        gravar_resumo(conn_app, atd, texto="o João quer parcela menor", cobre_ate_seq=1, agora=AGORA, chaveiro=chaveiro)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        gravar_troca(conn_app, atd, remetente="cliente", texto="oi", agora=AGORA, chaveiro=chaveiro)  # type: ignore[call-arg]
    with pytest.raises(NomesIndisponiveis) as erro:
        gravar_troca(conn_app, atd, remetente="cliente", texto="o João Carlos mora na Rua X", agora=AGORA, chaveiro=chaveiro, nomes=None)
    assert "João" not in str(erro.value)
    _troca(conn_app, atd, chaveiro, "oi")
    with pytest.raises(NomesIndisponiveis):
        gravar_resumo(conn_app, atd, texto="prefere manha", cobre_ate_seq=1, agora=AGORA, chaveiro=chaveiro, nomes=None)
    assert conn_app.execute("SELECT count(*) FROM ia.conversa_cifrada").fetchone() == (1,)


def test_chave_do_mes_diferente_da_vigente_recusa_gravar_m2(conn_app, atd, chaveiro):

    dezembro = datetime(2026, 12, 15, tzinfo=UTC)  # chave_id 3; o chaveiro está na 2 (esqueceram de virar CHAVE_AES_ID)
    with pytest.raises(ChaveForaDoMes) as erro:
        gravar_troca(conn_app, atd, remetente="cliente", texto="oi", agora=dezembro, chaveiro=chaveiro, nomes=())
    assert "3" in str(erro.value) and "2" in str(erro.value)
    with pytest.raises(ChaveForaDoMes):
        gravar_resumo(conn_app, atd, texto="x", cobre_ate_seq=1, agora=dezembro, chaveiro=chaveiro, nomes=())
    assert conn_app.execute("SELECT count(*) FROM ia.conversa_cifrada").fetchone() == (0,)


def test_retencao_da_linha_e_contada_pelo_relogio_do_banco_m1(conn_app, atd, chaveiro_do_mes_atual):
    """Sem `agora` do chamador: `criada_em`/`apagar_em` saem de `now()` do SQL, então nenhum relógio errado alonga a vida real do texto."""
    gravar_troca(conn_app, atd, remetente="cliente", texto="oi", chaveiro=chaveiro_do_mes_atual, nomes=())
    dentro = conn_app.execute(
        "SELECT abs(extract(epoch FROM now() - criada_em)) < 10 AND apagar_em - criada_em = interval '30 days' FROM ia.conversa_cifrada"
    ).fetchone()
    assert dentro == (True,)
    with pytest.raises(TypeError):  # o relógio do chamador não escolhe mais a data da linha
        gravar_troca(conn_app, atd, remetente="cliente", texto="oi", chaveiro=chaveiro_do_mes_atual, nomes=(), criada_em=AGORA)  # type: ignore[call-arg]
