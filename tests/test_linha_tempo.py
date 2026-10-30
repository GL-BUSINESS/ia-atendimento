"""Linha do tempo (B1.2, sp01 T4): `gravar_passo`, mensagens recebidas com dedupe permanente, pendentes/consumir. Postgres 18 descartável."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import replace

import psycopg
import pytest

from ia_atendimento.evento_mensagem import EventoMensagem, identidade
from ia_atendimento.linha_tempo import (
    AtendimentoInexistente,
    Conflito,
    ConflitoDeVersao,
    CtxPasso,
    Duplicada,
    EnvioSemVerificacao,
    Gravada,
    PassoComPii,
    PassoSemTurnoOuFase,
    consumir,
    gravar_mensagem_recebida,
    gravar_passo,
    mensagens_pendentes,
)
from ia_atendimento.passos import criar
from ia_atendimento.scrubber import EntradaInvalida
from tests.apoio_b12 import AGORA, CHAT, CPF_SINTETICO, MARCADOR, OUTRO_CHAT, PHONE, novo_atendimento

pytest_plugins = ["tests.apoio_b12"]

CHAVE_H16 = b"chave-h16-de-teste-descartavel-01"  # a do vetor dourado do contrato 08 §5.1
CTX = CtxPasso(turno=1, fase="E1")


@pytest.fixture
def atd(conn_app: psycopg.Connection) -> uuid.UUID:
    return novo_atendimento(conn_app)


def _evento(texto: str | None = "oi, quero saber da proposta", **mudar) -> EventoMensagem:
    base = {
        "chat_id": CHAT,
        "phone_id": PHONE,
        "tipo": "texto",
        "texto": texto,
        "datetime_post": "2026-11-24T10:15:30-03:00",
        "origem_evento": "webhook",
    }
    return EventoMensagem(**{**base, **mudar})


# --- chave e fingerprint (contrato 08 §5.1) ------------------------------------------------------------------------------------


def test_msg_chave_vetor_dourado_do_contrato():
    ident = identidade(_evento(), CHAVE_H16)
    assert ident.msg_chave == "cg:0123456789abcdef01234567:be0f44572b7488ed"
    assert ident.msg_fingerprint == "924ee977cbf01faa02f5f872067aa86f99fce5ce05838fac80933182090ab57d"
    assert ident.msg_tamanho == len("oi, quero saber da proposta")


def test_chave_e_fingerprint_nao_trazem_o_texto_em_claro():
    ident = identidade(_evento(texto=f"{MARCADOR} {CPF_SINTETICO}"), CHAVE_H16)
    assert MARCADOR not in ident.msg_chave + ident.msg_fingerprint
    assert ident.msg_chave.startswith("cg:") and len(ident.msg_chave.split(":")[-1]) == 16


def test_mesmo_conteudo_por_webhook_e_por_replay_da_a_mesma_chave_e_o_mesmo_fingerprint():
    a = identidade(_evento(origem_evento="webhook"), CHAVE_H16)
    b = identidade(_evento(origem_evento="replay"), CHAVE_H16)
    assert (a.msg_chave, a.msg_fingerprint) == (b.msg_chave, b.msg_fingerprint)


def test_reconciliacao_rpa_tem_chave_rpa_e_o_mesmo_fingerprint_do_webhook():
    webhook = identidade(_evento(), CHAVE_H16)
    rpa = identidade(_evento(origem_evento="reconciliacao", rpa_id="65f1c2a9b8d7e6f5a4b3c2d1"), CHAVE_H16)
    assert rpa.msg_chave == "rpa:65f1c2a9b8d7e6f5a4b3c2d1"
    assert rpa.msg_fingerprint == webhook.msg_fingerprint  # o fingerprint não inclui a origem: serve ao casamento webhook × RPA


def test_chave_muda_com_texto_hora_tipo_e_chave_secreta():
    base = identidade(_evento(), CHAVE_H16).msg_chave
    assert identidade(_evento(texto="oi, quero saber da proposta!"), CHAVE_H16).msg_chave != base
    assert identidade(_evento(datetime_post="2026-11-24T10:15:31-03:00"), CHAVE_H16).msg_chave != base
    assert identidade(_evento(), b"outra-chave-descartavel-de-teste-02").msg_chave != base
    assert identidade(_evento(texto=None, tipo="audio"), CHAVE_H16).msg_chave != base


def test_hora_com_fusos_diferentes_do_mesmo_instante_da_a_mesma_chave():
    a = identidade(_evento(datetime_post="2026-11-24T10:15:30-03:00"), CHAVE_H16)
    b = identidade(_evento(datetime_post="2026-11-24T13:15:30+00:00"), CHAVE_H16)
    assert a == b


def test_evento_recusa_forma_invalida_sem_vazar_o_valor():
    with pytest.raises(Exception) as erro:  # noqa: PT011 (ValidationError do Pydantic, sem input)
        EventoMensagem(chat_id=f"{CPF_SINTETICO}", phone_id=PHONE, tipo="texto", texto="x", origem_evento="webhook")
    assert CPF_SINTETICO not in str(erro.value)
    with pytest.raises(EntradaInvalida):  # reconciliação sem rpa_id
        EventoMensagem.criar(chat_id=CHAT, phone_id=PHONE, tipo="texto", texto="x", origem_evento="reconciliacao")


# --- gravar_passo -----------------------------------------------------------------------------------------------------------------


def test_passo_sem_turno_ou_fase_e_recusado(conn_app, atd):
    dados = criar("erro", peca="fila")
    with pytest.raises(PassoSemTurnoOuFase):
        gravar_passo(conn_app, atd, ctx=None, dados=dados)
    with pytest.raises(EntradaInvalida):
        CtxPasso.criar(turno=1, fase=None)
    with pytest.raises(EntradaInvalida):
        CtxPasso.criar(turno=None, fase="E1")
    with pytest.raises(EntradaInvalida):
        CtxPasso.criar(turno=1, fase="E11")
    with pytest.raises(EntradaInvalida):
        CtxPasso.criar(turno=-1, fase="E1")
    assert conn_app.execute("SELECT count(*) FROM ia.passo").fetchone() == (0,)
    # a anotação do operador é a única sem turno e fase (CHECK passo_turno_check)
    nota = criar("anotacao_operador", nomes=(), operador="op@exemplo.invalid", resultado="observacao", nota="retorno amanha")
    assert gravar_passo(conn_app, atd, ctx=None, dados=nota, nomes=()).ordem == 1


def test_passo_grava_turno_fase_e_ordem_crescente(conn_app, atd):
    p1 = gravar_passo(conn_app, atd, ctx=CtxPasso(turno=2, fase="E3"), dados=criar("erro", peca="fila"), agora=AGORA)
    p2 = gravar_passo(conn_app, atd, ctx=CtxPasso(turno=2, fase="E4"), dados=criar("opt_out"), agora=AGORA)
    assert (p1.ordem, p2.ordem) == (1, 2)
    linhas = conn_app.execute("SELECT ordem, turno, fase, tipo, ocorrido_em FROM ia.passo ORDER BY ordem").fetchall()
    assert linhas == [(1, 2, "E3", "erro", AGORA), (2, 2, "E4", "opt_out", AGORA)]


def test_envio_sem_verif_det_e_recusado(conn_app, atd):
    sem = criar("resposta_enviada", entrega="aceito", verif_det=[]).model_copy(update={"verif_det": None})  # contorna o Pydantic
    with pytest.raises(EnvioSemVerificacao):
        gravar_passo(conn_app, atd, ctx=CTX, dados=sem)
    assert conn_app.execute("SELECT count(*) FROM ia.passo").fetchone() == (0,)
    # a terceira cerca: o CHECK do banco recusa o envio sem verif_det mesmo com SQL cru
    with pytest.raises(psycopg.errors.CheckViolation):
        conn_app.execute(
            "INSERT INTO ia.passo (atendimento_id, ordem, tipo, texto, turno, fase, entrega) VALUES (%s, 1, 'resposta_enviada', 'x', 1, 'E1', 'aceito')",
            (atd,),
        )
    ok = gravar_passo(conn_app, atd, ctx=CTX, dados=criar("resposta_enviada", entrega="aceito", verif_det=[]))
    assert conn_app.execute("SELECT verif_det FROM ia.passo WHERE ordem = %s", (ok.ordem,)).fetchone() == ([],)


def test_passo_com_pii_no_texto_e_recusado(conn_app, atd):
    nota = criar("anotacao_operador", nomes=(), operador="op@exemplo.invalid", resultado="observacao", nota="ok")
    sujo = nota.model_copy(update={"nota": f"ligar para {CPF_SINTETICO}"})  # contorna o validador do modelo
    with pytest.raises(PassoComPii) as erro:
        gravar_passo(conn_app, atd, ctx=None, dados=sujo, nomes=())
    assert CPF_SINTETICO not in str(erro.value)
    com_nome = nota.model_copy(update={"nota": "Maria Souza pediu retorno"})
    with pytest.raises(PassoComPii):  # achado S1: o nome do cliente também é PII no texto do passo
        gravar_passo(conn_app, atd, ctx=None, dados=com_nome, nomes=("Maria Souza",))
    with pytest.raises(PassoComPii):  # nomes indisponíveis: texto livre não é aceito
        gravar_passo(conn_app, atd, ctx=None, dados=nota)
    assert conn_app.execute("SELECT count(*) FROM ia.passo").fetchone() == (0,)


def test_atendimento_inexistente_e_recusado(conn_app):
    with pytest.raises(AtendimentoInexistente):
        gravar_passo(conn_app, uuid.uuid4(), ctx=CTX, dados=criar("erro", peca="fila"))


def test_gravar_passo_ordem_e_for_update_funciona_com_ia_app(banco, atd, conn_app):
    """O `FOR UPDATE` do atendimento serializa a ordem: a 2ª gravação ESPERA a 1ª confirmar e fica com ordem 2 (sem o lock,
    as duas leriam max=0 e a 2ª quebraria em passo_ordem_uq)."""
    resultado: dict[str, object] = {}

    def segunda() -> None:
        with banco.sessao("ia_app_a") as outra:
            try:
                resultado["passo"] = gravar_passo(outra, atd, ctx=CTX, dados=criar("opt_out"))
            except Exception as erro:  # noqa: BLE001
                resultado["erro"] = erro

    with banco.conectar("ia_app_a", autocommit=False) as primeira:
        p1 = gravar_passo(primeira, atd, ctx=CTX, dados=criar("erro", peca="fila"))
        fio = threading.Thread(target=segunda)
        fio.start()
        time.sleep(0.6)
        assert fio.is_alive(), "a segunda gravação deveria estar esperando o lock do atendimento"
        primeira.commit()
    fio.join(timeout=10)
    assert "erro" not in resultado, resultado.get("erro")
    assert (p1.ordem, resultado["passo"].ordem) == (1, 2)  # type: ignore[attr-defined]


def _semear_filhos(conn: psycopg.Connection, atd: uuid.UUID) -> dict[str, str]:
    """Linhas que os passos `confirmacao` e `agendamento` referenciam por FK (ia_app tem INSERT nas duas)."""
    confirmacao = conn.execute(
        "INSERT INTO ia.confirmacao (atendimento_id, tipo, banco, oferta_versao, valores_hash, texto_id, pergunta_ordem)"
        " VALUES (%s, 'digitacao', 'FACTA', 1, %s, 'tx-11', 1) RETURNING confirmacao_id",
        (atd, "c" * 64),
    ).fetchone()
    chave = f"agendar:{uuid.uuid4().hex}"
    agendamento = conn.execute(
        "INSERT INTO ia.agendamento (atendimento_id, pessoa_id, chat_id, entrada, seq, msg_chave, texto_hash, retoma_fase, chave_logica, idem_key)"
        " SELECT atendimento_id, pessoa_id, chat_id, 'pausa_ia', 1, 'cg:0123456789abcdef01234567:4444444444444444', %s, 'E4', %s,"
        " encode(sha256(convert_to(%s,'UTF8')),'hex') FROM ia.atendimento WHERE atendimento_id = %s RETURNING agendamento_id",
        ("a" * 64, chave, chave, atd),
    ).fetchone()
    assert confirmacao is not None and agendamento is not None
    return {"confirmacao_id": str(confirmacao[0]), "agendamento_id": str(agendamento[0])}


def test_os_13_tipos_gravam_no_banco_sem_violar_check(conn_app, atd):
    from tests.test_passos import DOURADO

    ids = _semear_filhos(conn_app, atd)
    vistos = set()
    for caso in DOURADO:
        dados = dict(caso["dados"])
        dados.update({k: v for k, v in ids.items() if k in dados})
        if caso["tipo"] == "mensagem_recebida":
            dados["msg_chave"] = f"cg:{CHAT}:{uuid.uuid4().hex[:16]}"
        ctx = None if caso["tipo"] == "anotacao_operador" else CTX
        gravar_passo(conn_app, atd, ctx=ctx, dados=criar(caso["tipo"], nomes=(), **dados), nomes=())
        vistos.add(caso["tipo"])
    assert len(vistos) == 13
    assert conn_app.execute("SELECT count(DISTINCT tipo) FROM ia.passo").fetchone() == (13,)


# --- mensagens recebidas ---------------------------------------------------------------------------------------------------------


def test_dedupe_permanente_mesma_chave_mesmo_fingerprint_e_noop(conn_app, atd):
    primeira = gravar_mensagem_recebida(conn_app, atd, evento=_evento(), chave_h16=CHAVE_H16, agora=AGORA)
    segunda = gravar_mensagem_recebida(conn_app, atd, evento=_evento(), chave_h16=CHAVE_H16, agora=AGORA)
    assert isinstance(primeira, Gravada) and isinstance(segunda, Duplicada)
    assert segunda.ordem == primeira.ordem
    assert conn_app.execute("SELECT count(*) FROM ia.passo WHERE tipo = 'mensagem_recebida'").fetchone() == (1,)


def test_dedupe_permanente_vale_mesmo_depois_de_o_atendimento_encerrar_e_outro_abrir(conn_app, atd):
    """«Permanente»: o índice é global (não por atendimento); o reenvio do ChatGuru depois de 3 dias continua sendo duplicata."""
    gravar_mensagem_recebida(conn_app, atd, evento=_evento(), chave_h16=CHAVE_H16, agora=AGORA)
    outro = novo_atendimento(conn_app, chat=OUTRO_CHAT)
    de_novo = gravar_mensagem_recebida(conn_app, outro, evento=_evento(), chave_h16=CHAVE_H16, agora=AGORA)
    assert isinstance(de_novo, Duplicada) and de_novo.atendimento_id == atd
    assert conn_app.execute("SELECT count(*) FROM ia.passo WHERE atendimento_id = %s", (outro,)).fetchone() == (0,)


def test_dedupe_permanente_webhook_e_rpa_mesma_chave(conn_app, atd):
    """Webhook e reconciliador RPA: o MESMO evento repetido por qualquer um dos dois caminhos é uma só linha. Webhook × replay
    têm a mesma `msg_chave`; o RPA tem `rpa:{_id}` (contrato 08 §5.1) e o mesmo `msg_fingerprint` do webhook."""
    rpa = _evento(origem_evento="reconciliacao", rpa_id="65f1c2a9b8d7e6f5a4b3c2d1")
    assert isinstance(gravar_mensagem_recebida(conn_app, atd, evento=_evento(), chave_h16=CHAVE_H16), Gravada)
    assert isinstance(gravar_mensagem_recebida(conn_app, atd, evento=_evento(origem_evento="replay"), chave_h16=CHAVE_H16), Duplicada)
    assert isinstance(gravar_mensagem_recebida(conn_app, atd, evento=rpa, chave_h16=CHAVE_H16), Gravada)  # outra fonte: casamento é da B1.5
    assert isinstance(gravar_mensagem_recebida(conn_app, atd, evento=rpa, chave_h16=CHAVE_H16), Duplicada)
    fingerprints = conn_app.execute("SELECT DISTINCT msg_fingerprint FROM ia.passo WHERE tipo = 'mensagem_recebida'").fetchall()
    assert len(fingerprints) == 1


def test_mesma_chave_outro_fingerprint_e_conflito(conn_app, atd, monkeypatch):
    """Colisão de chave com conteúdo diferente (os 16 hex do HMAC colidiram): nada é gravado e o chamador é avisado."""
    gravar_mensagem_recebida(conn_app, atd, evento=_evento(), chave_h16=CHAVE_H16)
    real = identidade(_evento(), CHAVE_H16)
    monkeypatch.setattr("ia_atendimento.linha_tempo.identidade", lambda ev, ch: replace(real, msg_fingerprint="f" * 64))
    resultado = gravar_mensagem_recebida(conn_app, atd, evento=_evento(texto="outro texto"), chave_h16=CHAVE_H16)
    assert isinstance(resultado, Conflito)
    assert conn_app.execute("SELECT count(*) FROM ia.passo WHERE tipo = 'mensagem_recebida'").fetchone() == (1,)


def test_mensagem_recebida_grava_turno_mais_um_fase_atual_e_so_codigos(conn_app, atd):
    gravar_mensagem_recebida(conn_app, atd, evento=_evento(texto=f"{MARCADOR} {CPF_SINTETICO}"), chave_h16=CHAVE_H16, agora=AGORA)
    linha = conn_app.execute(
        "SELECT turno, fase, texto, msg_tipo, msg_tamanho, origem_evento, msg_enviada_em, passo::text FROM ia.passo WHERE tipo = 'mensagem_recebida'"
    ).fetchone()
    assert linha is not None
    assert (linha[0], linha[1]) == (1, "E0")  # rodada 0 + 1; o atendimento nasce em E0
    assert linha[2] == f"Cliente enviou texto ({len(MARCADOR) + 1 + len(CPF_SINTETICO)} caracteres)."
    assert (linha[3], linha[5]) == ("texto", "webhook")
    assert linha[6].isoformat() == "2026-11-24T13:15:30+00:00"
    assert MARCADOR not in linha[7] and CPF_SINTETICO not in linha[7]


def test_campos_msg_so_em_mensagem_recebida(conn_app, atd):
    with pytest.raises(psycopg.errors.CheckViolation):
        conn_app.execute(
            "INSERT INTO ia.passo (atendimento_id, ordem, tipo, texto, turno, fase, peca, msg_tipo) VALUES (%s, 1, 'erro', 'x', 1, 'E1', 'fila', 'texto')",
            (atd,),
        )
    with pytest.raises(EntradaInvalida):
        criar("erro", peca="fila", msg_tipo="texto")


def test_tres_pendentes_sao_consumidas_juntas_e_turnos_sobe_uma_vez(conn_app, atd):
    for i in range(3):
        gravar_mensagem_recebida(conn_app, atd, evento=_evento(texto=f"mensagem numero {i}"), chave_h16=CHAVE_H16)
    pendentes = mensagens_pendentes(conn_app, atd)
    assert [p.ordem for p in pendentes] == [1, 2, 3]
    assert {p.msg_tipo for p in pendentes} == {"texto"}
    versao = conn_app.execute("SELECT versao FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()[0]
    nova = consumir(conn_app, atd, versao=versao, ate_ordem=3, agora=AGORA)
    assert nova == versao + 1
    assert mensagens_pendentes(conn_app, atd) == []
    atendimento = conn_app.execute(
        "SELECT ordem_consumida, turnos, estado_conversa #>> '{contadores,rodada}', versao FROM ia.atendimento WHERE atendimento_id = %s", (atd,)
    ).fetchone()
    assert atendimento == (3, 1, "1", versao + 1)
    # a próxima mensagem já cai no turno seguinte (rodada 1 + 1)
    gravar_mensagem_recebida(conn_app, atd, evento=_evento(texto="outra"), chave_h16=CHAVE_H16)
    assert conn_app.execute("SELECT turno FROM ia.passo WHERE ordem = 4").fetchone() == (2,)
    assert [p.ordem for p in mensagens_pendentes(conn_app, atd)] == [4]


def test_consumir_com_versao_velha_e_conflito_e_nao_consome(conn_app, atd):
    gravar_mensagem_recebida(conn_app, atd, evento=_evento(), chave_h16=CHAVE_H16)
    with pytest.raises(ConflitoDeVersao):
        consumir(conn_app, atd, versao=99, ate_ordem=1)
    assert len(mensagens_pendentes(conn_app, atd)) == 1


def test_consumir_recusa_ordem_que_nao_e_mensagem_ou_que_nao_avanca(conn_app, atd):
    gravar_mensagem_recebida(conn_app, atd, evento=_evento(), chave_h16=CHAVE_H16)
    gravar_passo(conn_app, atd, ctx=CTX, dados=criar("erro", peca="fila"))  # ordem 2 não é mensagem
    versao = conn_app.execute("SELECT versao FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()[0]
    for ate in (0, 2, 7):
        with pytest.raises(ValueError, match="ate_ordem"):
            consumir(conn_app, atd, versao=versao, ate_ordem=ate)
