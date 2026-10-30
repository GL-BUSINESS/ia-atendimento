"""Linha do tempo (B1.2, sp01 T4): `gravar_passo`, mensagens recebidas com dedupe permanente, pendentes/consumir. Postgres 18 descartável."""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from ia_atendimento import linha_tempo
from ia_atendimento.evento_mensagem import ChavesDeMensagem, EventoMensagem, identidade
from ia_atendimento.linha_tempo import (
    AtendimentoInexistente,
    Casada,
    Conflito,
    ConflitoDeVersao,
    CtxPasso,
    Duplicada,
    EnvioSemVerificacao,
    Gravada,
    PassoComPii,
    PassoRecusadoPeloBanco,
    PassoSemTurnoOuFase,
    consumir,
    gravar_mensagem_recebida,
    gravar_passo,
    mensagens_pendentes,
)
from ia_atendimento.passos import criar
from ia_atendimento.scrubber import EntradaInvalida
from tests.apoio_b12 import CHAT, CPF_SINTETICO, MARCADOR, OUTRO_CHAT, PHONE, novo_atendimento

pytest_plugins = ["tests.apoio_b12"]

CHAVE_H16 = b"chave-h16-de-teste-descartavel-01"  # a do vetor dourado do contrato 08 §5.1
CHAVE_FP = b"chave-fingerprint-de-teste-descartavel-01"
CHAVES = ChavesDeMensagem(h16=CHAVE_H16, fingerprint=CHAVE_FP)
OUTRAS = ChavesDeMensagem(h16=b"outra-chave-h16-descartavel-de-teste", fingerprint=b"outra-chave-fp-descartavel-de-teste-02")
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
    ident = identidade(_evento(), CHAVES)
    assert ident.msg_chave == "cg:0123456789abcdef01234567:be0f44572b7488ed"  # h16 do contrato 08 §5.1
    assert ident.msg_tamanho == len("oi, quero saber da proposta")


def test_fingerprint_e_hmac_e_nao_sha256_puro_s2():
    """S2: texto curto é enumerável; o sha256 puro do contrato (`924ee977…`) seria reversível por dicionário. O fingerprint agora é
    HMAC-SHA256 do mesmo corpo canônico, com chave dedicada (vetor recalculado independentemente)."""
    canonico = (
        '{"chat_id":"0123456789abcdef01234567","datetime_post":"2026-11-24T13:15:30Z","phone_id":"89abcdef0123456789abcdef",'
        '"texto":"oi, quero saber da proposta","tipo":"texto"}'
    )
    ident = identidade(_evento(), CHAVES)
    assert ident.msg_fingerprint == "d91e6bf4176d42e4a6af732ecda90217a3bbcdea5aadf9de756a8ac087a06dd4"
    assert ident.msg_fingerprint == hmac.new(CHAVE_FP, b"ia-evento/v1\n" + canonico.encode(), hashlib.sha256).hexdigest()
    assert ident.msg_fingerprint != hashlib.sha256(b"ia-evento/v1\n" + canonico.encode()).hexdigest()


def test_mesma_mensagem_com_chaves_diferentes_da_fingerprints_diferentes_s2():
    a = identidade(_evento(), CHAVES)
    b = identidade(_evento(), ChavesDeMensagem(h16=CHAVE_H16, fingerprint=OUTRAS.fingerprint))
    assert a.msg_chave == b.msg_chave
    assert a.msg_fingerprint != b.msg_fingerprint


def test_fingerprint_nao_depende_dos_nomes_da_conversa_m5():
    """M5: o fingerprint é HMAC do texto mascarado SEM nomes (contrato 08 §5.1). Se o nome do cliente for aprendido depois, um replay
    antigo não pode virar `Conflito` (alarme falso). O HMAC já impede a reversão por dicionário (S2)."""
    with pytest.raises(TypeError):
        identidade(_evento(), CHAVES, nomes=("Maria Souza",))  # type: ignore[call-arg]


def test_replay_com_nomes_novos_nao_vira_conflito_m5(conn_app, atd):
    ev = _evento(texto="sou o joão")
    assert isinstance(gravar_mensagem_recebida(conn_app, atd, evento=ev, chaves=CHAVES), Gravada)
    assert isinstance(gravar_mensagem_recebida(conn_app, atd, evento=ev, chaves=CHAVES), Duplicada)


def test_chaves_de_mensagem_recusam_curta_repetida_e_nao_vazam_no_repr():
    with pytest.raises(ValueError, match="h16"):
        ChavesDeMensagem(h16=b"curta", fingerprint=CHAVE_FP)
    with pytest.raises(ValueError, match="fingerprint"):
        ChavesDeMensagem(h16=CHAVE_H16, fingerprint=b"curta")
    with pytest.raises(ValueError, match="diferentes"):
        ChavesDeMensagem(h16=CHAVE_H16, fingerprint=CHAVE_H16)
    assert CHAVE_FP.decode() not in repr(CHAVES) + str(CHAVES)


def test_chave_e_fingerprint_nao_trazem_o_texto_em_claro():
    ident = identidade(_evento(texto=f"{MARCADOR} {CPF_SINTETICO}"), CHAVES)
    assert MARCADOR not in ident.msg_chave + ident.msg_fingerprint
    assert ident.msg_chave.startswith("cg:") and len(ident.msg_chave.split(":")[-1]) == 16


def test_mesmo_conteudo_por_webhook_e_por_replay_da_a_mesma_chave_e_o_mesmo_fingerprint():
    a = identidade(_evento(origem_evento="webhook"), CHAVES)
    b = identidade(_evento(origem_evento="replay"), CHAVES)
    assert (a.msg_chave, a.msg_fingerprint) == (b.msg_chave, b.msg_fingerprint)


def test_reconciliacao_rpa_tem_chave_rpa_e_o_mesmo_fingerprint_do_webhook():
    webhook = identidade(_evento(), CHAVES)
    rpa = identidade(_evento(origem_evento="reconciliacao", rpa_id="65f1c2a9b8d7e6f5a4b3c2d1"), CHAVES)
    assert rpa.msg_chave == "rpa:65f1c2a9b8d7e6f5a4b3c2d1"
    assert rpa.msg_fingerprint == webhook.msg_fingerprint  # o fingerprint não inclui a origem: serve ao casamento webhook × RPA


def test_chave_muda_com_texto_hora_tipo_e_chave_secreta():
    base = identidade(_evento(), CHAVES).msg_chave
    assert identidade(_evento(texto="oi, quero saber da proposta!"), CHAVES).msg_chave != base
    assert identidade(_evento(datetime_post="2026-11-24T10:15:31-03:00"), CHAVES).msg_chave != base
    assert identidade(_evento(), OUTRAS).msg_chave != base
    assert identidade(_evento(texto=None, tipo="audio"), CHAVES).msg_chave != base


def test_hora_com_fusos_diferentes_do_mesmo_instante_da_a_mesma_chave():
    a = identidade(_evento(datetime_post="2026-11-24T10:15:30-03:00"), CHAVES)
    b = identidade(_evento(datetime_post="2026-11-24T13:15:30+00:00"), CHAVES)
    assert a == b


def test_evento_recusa_forma_invalida_sem_vazar_o_valor():
    with pytest.raises(Exception) as erro:
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
    p1 = gravar_passo(conn_app, atd, ctx=CtxPasso(turno=2, fase="E3"), dados=criar("erro", peca="fila"))
    p2 = gravar_passo(conn_app, atd, ctx=CtxPasso(turno=2, fase="E4"), dados=criar("opt_out"))
    assert (p1.ordem, p2.ordem) == (1, 2)
    linhas = conn_app.execute(
        "SELECT ordem, turno, fase, tipo, abs(extract(epoch FROM now() - ocorrido_em)) < 10 FROM ia.passo ORDER BY ordem"
    ).fetchall()
    assert linhas == [(1, 2, "E3", "erro", True), (2, 2, "E4", "opt_out", True)]  # a hora é a do BANCO (M1), não a do chamador


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
            except Exception as erro:
                resultado["erro"] = erro

    with banco.conectar("ia_app_a", autocommit=False) as primeira:
        primeira.execute(
            "SELECT 1"
        )  # abre a transação externa: o `transaction()` do gravar_passo vira savepoint e o lock fica até o commit
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
    primeira = gravar_mensagem_recebida(conn_app, atd, evento=_evento(), chaves=CHAVES)
    segunda = gravar_mensagem_recebida(conn_app, atd, evento=_evento(), chaves=CHAVES)
    assert isinstance(primeira, Gravada) and isinstance(segunda, Duplicada)
    assert segunda.ordem == primeira.ordem
    assert conn_app.execute("SELECT count(*) FROM ia.passo WHERE tipo = 'mensagem_recebida'").fetchone() == (1,)


def test_dedupe_permanente_vale_mesmo_depois_de_o_atendimento_encerrar_e_outro_abrir(conn_app, atd):
    """«Permanente»: o índice é global (não por atendimento); o reenvio do ChatGuru depois de 3 dias continua sendo duplicata."""
    gravar_mensagem_recebida(conn_app, atd, evento=_evento(), chaves=CHAVES)
    outro = novo_atendimento(conn_app, chat=OUTRO_CHAT)
    de_novo = gravar_mensagem_recebida(conn_app, outro, evento=_evento(), chaves=CHAVES)
    assert isinstance(de_novo, Duplicada) and de_novo.mesmo_atendimento is False
    assert de_novo.ordem is None, "B2: não devolve ordem de outro atendimento"
    assert conn_app.execute("SELECT count(*) FROM ia.passo WHERE atendimento_id = %s", (outro,)).fetchone() == (0,)


def test_dedupe_permanente_webhook_e_rpa_mesma_chave(conn_app, atd):
    """Webhook e reconciliador RPA: o MESMO evento repetido por qualquer um dos dois caminhos é uma só linha. Webhook × replay
    têm a mesma `msg_chave`; o RPA tem `rpa:{_id}` (contrato 08 §5.1) e o mesmo `msg_fingerprint` do webhook."""
    rpa = _evento(origem_evento="reconciliacao", rpa_id="65f1c2a9b8d7e6f5a4b3c2d1")
    assert isinstance(gravar_mensagem_recebida(conn_app, atd, evento=_evento(), chaves=CHAVES), Gravada)
    assert isinstance(gravar_mensagem_recebida(conn_app, atd, evento=_evento(origem_evento="replay"), chaves=CHAVES), Duplicada)
    assert isinstance(gravar_mensagem_recebida(conn_app, atd, evento=rpa, chaves=CHAVES), Gravada)  # outra fonte: casamento é da B1.5
    assert isinstance(gravar_mensagem_recebida(conn_app, atd, evento=rpa, chaves=CHAVES), Duplicada)
    fingerprints = conn_app.execute("SELECT DISTINCT msg_fingerprint FROM ia.passo WHERE tipo = 'mensagem_recebida'").fetchall()
    assert len(fingerprints) == 1


def test_mesma_chave_outro_fingerprint_e_conflito(conn_app, atd, monkeypatch):
    """Colisão de chave com conteúdo diferente (os 16 hex do HMAC colidiram): nada é gravado e o chamador é avisado."""
    gravar_mensagem_recebida(conn_app, atd, evento=_evento(), chaves=CHAVES)
    real = identidade(_evento(), CHAVES)
    monkeypatch.setattr("ia_atendimento.linha_tempo.identidade", lambda ev, ch, **kw: replace(real, msg_fingerprint="f" * 64))
    resultado = gravar_mensagem_recebida(conn_app, atd, evento=_evento(texto="outro texto"), chaves=CHAVES)
    assert isinstance(resultado, Conflito)
    assert conn_app.execute("SELECT count(*) FROM ia.passo WHERE tipo = 'mensagem_recebida'").fetchone() == (1,)


def test_mensagem_recebida_grava_turno_mais_um_fase_atual_e_so_codigos(conn_app, atd):
    gravar_mensagem_recebida(conn_app, atd, evento=_evento(texto=f"{MARCADOR} {CPF_SINTETICO}"), chaves=CHAVES)
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
        gravar_mensagem_recebida(conn_app, atd, evento=_evento(texto=f"mensagem numero {i}"), chaves=CHAVES)
    pendentes = mensagens_pendentes(conn_app, atd)
    assert [p.ordem for p in pendentes] == [1, 2, 3]
    assert {p.msg_tipo for p in pendentes} == {"texto"}
    versao = conn_app.execute("SELECT versao FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()[0]
    nova = consumir(conn_app, atd, versao=versao, ate_ordem=3)
    assert nova == versao + 1
    assert mensagens_pendentes(conn_app, atd) == []
    atendimento = conn_app.execute(
        "SELECT ordem_consumida, turnos, estado_conversa #>> '{contadores,rodada}', versao FROM ia.atendimento WHERE atendimento_id = %s",
        (atd,),
    ).fetchone()
    assert atendimento == (3, 1, "1", versao + 1)
    # a próxima mensagem já cai no turno seguinte (rodada 1 + 1)
    gravar_mensagem_recebida(conn_app, atd, evento=_evento(texto="outra"), chaves=CHAVES)
    assert conn_app.execute("SELECT turno FROM ia.passo WHERE ordem = 4").fetchone() == (2,)
    assert [p.ordem for p in mensagens_pendentes(conn_app, atd)] == [4]


def test_consumir_com_versao_velha_e_conflito_e_nao_consome(conn_app, atd):
    gravar_mensagem_recebida(conn_app, atd, evento=_evento(), chaves=CHAVES)
    with pytest.raises(ConflitoDeVersao):
        consumir(conn_app, atd, versao=99, ate_ordem=1)
    assert len(mensagens_pendentes(conn_app, atd)) == 1


def test_consumir_recusa_ordem_que_nao_e_mensagem_ou_que_nao_avanca(conn_app, atd):
    gravar_mensagem_recebida(conn_app, atd, evento=_evento(), chaves=CHAVES)
    gravar_passo(conn_app, atd, ctx=CTX, dados=criar("erro", peca="fila"))  # ordem 2 não é mensagem
    versao = conn_app.execute("SELECT versao FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()[0]
    for ate in (0, 2, 7):
        with pytest.raises(ValueError, match="ate_ordem"):
            consumir(conn_app, atd, versao=versao, ate_ordem=ate)


# --- correções da revisão 1 (A1–A3, M4, M6, B1, B2) -------------------------------------------------------------------------------


def test_motivo_de_texto_livre_nunca_chega_ao_banco_a1(banco, conn_app, atd):
    with pytest.raises(EntradaInvalida):
        criar("decisao", motor="regra", motivo=f"cliente disse {MARCADOR} sobre juros")
    gravar_passo(conn_app, atd, ctx=CTX, dados=criar("decisao", motor="regra", motivo="oferta_aceita"))
    with banco.sessao() as admin:
        dump = " ".join(r[0] for r in admin.execute("SELECT t::text FROM ia.passo t").fetchall())
    assert MARCADOR not in dump


def test_violacao_de_check_nao_imprime_a_linha_a1(conn_app, atd):
    """O `DETAIL` do CheckViolation traz «Failing row contains (…)»: o erro do módulo sai só com o nome da restrição."""
    sujo = criar("erro", peca="fila").model_copy(update={"trace_id": "SEGREDO-ZZZ-fora-do-padrao"})  # contorna o Pydantic
    with pytest.raises(PassoRecusadoPeloBanco) as erro:
        gravar_passo(conn_app, atd, ctx=CTX, dados=sujo)
    assert "SEGREDO" not in str(erro.value) + repr(erro.value)
    assert erro.value.restricao == "passo_valores_check"
    assert erro.value.__cause__ is None and erro.value.__context__ is None


def test_repr_e_errors_do_evento_nao_vazam_o_texto_a2():
    ev = _evento(texto=f"zebra {MARCADOR}", url_arquivo=f"https://exemplo.invalid/a?token={MARCADOR}")
    assert MARCADOR not in repr(ev) + str(ev)
    with pytest.raises(EntradaInvalida) as erro:  # construtor DIRETO, reconciliação sem rpa_id
        EventoMensagem(chat_id=CHAT, phone_id=PHONE, tipo="texto", texto=f"   {MARCADOR} ", origem_evento="reconciliacao")
    saida = json.dumps([str(erro.value), repr(erro.value), list(erro.value.detalhes), list(map(str, erro.value.args))])
    assert MARCADOR not in saida
    assert erro.value.__context__ is None


def test_sem_datetime_post_nunca_colapsa_mensagens_iguais_a3(conn_app, atd):
    """«sim» é a confirmação de T4/T7: dois «sim» legítimos não podem virar um só, nem em outro atendimento do mesmo chat."""
    outro = novo_atendimento(conn_app, chat=OUTRO_CHAT)
    sim = _evento(texto="sim", datetime_post=None)
    t0 = datetime(2026, 11, 24, 13, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="recebido_em"):
        identidade(sim, CHAVES)
    r = [
        gravar_mensagem_recebida(conn_app, a, evento=sim, chaves=CHAVES, recebido_em=t0 + timedelta(seconds=s))
        for a, s in ((atd, 0), (atd, 5), (outro, 90))
    ]
    assert all(isinstance(x, Gravada) for x in r)
    assert len({x.msg_chave for x in r}) == 3


def test_mensagem_id_e_fracao_de_segundo_e_query_da_url_distinguem_mensagens_a3():
    base = identidade(_evento(texto="sim"), CHAVES).msg_chave
    com_id = identidade(_evento(texto="sim", mensagem_id="wamid.HBgN-1="), CHAVES)
    outro_id = identidade(_evento(texto="sim", mensagem_id="wamid.HBgN-2="), CHAVES)
    assert com_id.msg_chave == "cgid:wamid.HBgN-1=" and com_id.msg_chave != outro_id.msg_chave != base
    meio = identidade(_evento(texto="sim", datetime_post="2026-11-24T10:15:30.500000-03:00"), CHAVES).msg_chave
    assert meio != base
    img1 = identidade(_evento(texto=None, tipo="imagem", url_arquivo="https://exemplo.invalid/f?id=1"), CHAVES).msg_chave
    img2 = identidade(_evento(texto=None, tipo="imagem", url_arquivo="https://exemplo.invalid/f?id=2"), CHAVES).msg_chave
    assert img1 != img2
    # o fingerprint segue o contrato (URL sem query): a query só pesa na chave
    f1 = identidade(_evento(texto=None, tipo="imagem", url_arquivo="https://exemplo.invalid/f?id=1"), CHAVES).msg_fingerprint
    f2 = identidade(_evento(texto=None, tipo="imagem", url_arquivo="https://exemplo.invalid/f?id=2"), CHAVES).msg_fingerprint
    assert f1 == f2


def test_espaco_nas_pontas_nao_muda_a_identidade():
    assert identidade(_evento(texto="  sim\n"), CHAVES) == identidade(_evento(texto="sim"), CHAVES)


def test_corrida_entre_atendimentos_cai_no_on_conflict_e_vira_duplicada(conn_app, atd, monkeypatch):
    """O SELECT prévio não viu a linha (outra transação a gravou entre o SELECT e o INSERT): `ON CONFLICT DO NOTHING` + releitura."""
    outro = novo_atendimento(conn_app, chat=OUTRO_CHAT)
    assert isinstance(gravar_mensagem_recebida(conn_app, outro, evento=_evento(), chaves=CHAVES), Gravada)
    real = linha_tempo._existente
    chamadas = []

    def cego_na_primeira(*args, **kw):
        chamadas.append(1)
        return None if len(chamadas) == 1 else real(*args, **kw)

    monkeypatch.setattr(linha_tempo, "_existente", cego_na_primeira)
    resultado = gravar_mensagem_recebida(conn_app, atd, evento=_evento(), chaves=CHAVES)
    assert isinstance(resultado, Duplicada) and len(chamadas) == 2
    assert conn_app.execute("SELECT count(*) FROM ia.passo WHERE atendimento_id = %s", (atd,)).fetchone() == (0,)


def test_gancho_de_casamento_webhook_x_rpa_roda_sob_o_lock_m4(conn_app, atd):
    visto = {}

    def casar(conn, atendimento_id, evento, ident):
        visto["travado"] = conn.execute(  # a linha do atendimento está bloqueada por NÓS: outra conexão não a pega com NOWAIT
            "SELECT count(*) FROM pg_locks l JOIN pg_class c ON c.oid = l.relation WHERE c.relname = 'atendimento' AND l.mode = 'RowShareLock' AND l.pid = pg_backend_pid()"
        ).fetchone()
        return 1 if evento.origem_evento == "reconciliacao" else None

    gravar_mensagem_recebida(conn_app, atd, evento=_evento(), chaves=CHAVES, casar=casar)
    rpa = _evento(origem_evento="reconciliacao", rpa_id="65f1c2a9b8d7e6f5a4b3c2d1", datetime_post="2026-11-24T10:15:33-03:00")
    resultado = gravar_mensagem_recebida(conn_app, atd, evento=rpa, chaves=CHAVES, casar=casar)
    assert isinstance(resultado, Casada) and resultado.ordem == 1
    assert conn_app.execute("SELECT count(*) FROM ia.passo WHERE tipo = 'mensagem_recebida'").fetchone() == (1,)
    assert visto["travado"][0] >= 1


@pytest.mark.xfail(
    reason="casamento webhook × RPA (contrato 08 §5.3 passo 7) é da B1.5: sem `casar` o mesmo evento vira 2 passos", strict=True
)
def test_webhook_e_rpa_colapsam(conn_app, atd):
    gravar_mensagem_recebida(conn_app, atd, evento=_evento(), chaves=CHAVES)
    rpa = _evento(origem_evento="reconciliacao", rpa_id="65f1c2a9b8d7e6f5a4b3c2d1")
    assert not isinstance(gravar_mensagem_recebida(conn_app, atd, evento=rpa, chaves=CHAVES), Gravada)


def test_consumir_perdedor_da_corrida_recebe_conflito_de_versao_m6(conn_app, atd):
    gravar_mensagem_recebida(conn_app, atd, evento=_evento(), chaves=CHAVES)
    versao = conn_app.execute("SELECT versao FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()[0]
    consumir(conn_app, atd, versao=versao, ate_ordem=1)
    with pytest.raises(ConflitoDeVersao):  # mesma versão velha, ordem já consumida: perdeu a corrida, não é erro de argumento
        consumir(conn_app, atd, versao=versao, ate_ordem=1)
