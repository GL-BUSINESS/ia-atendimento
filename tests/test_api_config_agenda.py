"""API de entrada (B1.5, sp01 T7): config, agendamentos, anotações, candidatos e saúde, contra o Postgres 18 descartável.

Mesma base: fila espiã e dado sintético.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tests import apoio_api
from tests.apoio_api import (
    CHAT,
    CHAT_TESTE,
    CLT_JOB,
    OUTRO_CHAT,
    PESSOA,
    PESSOA_TESTE,
    TOKENS,
    abrir_ativo,
    corpo_de_agendamento,
    mensagem_nativa,
)

ambiente = apoio_api.ambiente  # a fixture mora em `apoio_api`; este nome a registra neste módulo
pytestmark = pytest.mark.banco
CPF_SINTETICO = "000.000.012-34"


def _codigo(resposta) -> str:
    return resposta.json()["erro"]["codigo"]


# --- config -------------------------------------------------------------------------------------------------------------------------------


def test_put_config_insere_versao_mais_um_e_perder_a_corrida_da_409(ambiente):
    r = ambiente.put("/config/max_abertos", {"valor": 12, "por": "operador.teste@glcapital.invalid", "motivo": "ensaio"})
    assert r.status_code == 200 and (r.json()["nome"], r.json()["versao"], r.json()["valor"]) == ("max_abertos", 2, 12)
    assert r.json()["efeitos"] == {"encerrar_por_chave_agendados": 0}
    r = ambiente.put("/config/max_abertos", {"valor": 13, "por": "operador.teste@glcapital.invalid", "versao_esperada": 1})
    assert r.status_code == 409 and _codigo(r) == "config_corrida"
    r = ambiente.put("/config/max_abertos", {"valor": 13, "por": "operador.teste@glcapital.invalid", "versao_esperada": 2})
    assert r.status_code == 200 and r.json()["versao"] == 3
    assert ambiente.escalar("SELECT max(versao) FROM ia.config_versao WHERE nome = 'max_abertos'") == 3


def test_put_config_valida_pelo_registro_e_modo_global_teste_422(ambiente):
    por = "operador.teste@glcapital.invalid"
    r = ambiente.put("/config/modo", {"valor": "teste", "por": por})
    assert r.status_code == 422 and _codigo(r) == "modo_teste_global"
    r = ambiente.put("/config/max_abertos", {"valor": 0, "por": por})
    assert r.status_code == 422 and _codigo(r) == "valor_invalido"
    assert ambiente.put("/config/nome_fora_do_registro", {"valor": 1, "por": por}).status_code == 404
    assert ambiente.put("/config/ia_ativa", {"valor": "sim", "por": por}).status_code == 422
    assert ambiente.put("/config/modo", {"valor": "sombra", "por": por, "extra": 1}).status_code == 422
    assert ambiente.escalar("SELECT max(versao) FROM ia.config_versao WHERE nome = 'modo'") == 1


def test_put_config_origem_c360_so_ia_ativa_e_modo_e_chats_teste_so_ti(ambiente):
    por = "operador.teste@glcapital.invalid"
    assert ambiente.put("/config/modo", {"valor": "sombra", "por": por}, token="c360_api").status_code == 200
    assert ambiente.put("/config/max_abertos", {"valor": 12, "por": por}, token="c360_api").status_code == 403
    assert ambiente.put("/config/chats_teste", {"valor": [], "por": por}, token="c360_api").status_code == 403
    assert ambiente.put("/config/modo", {"valor": "real", "por": por}, token="n8n_braco").status_code == 403
    assert ambiente.put("/config/modo", {"valor": "real", "por": por}, token="vigia").status_code == 403


def test_put_config_motivo_com_pii_422_e_leitura_mascara_o_que_ja_estava_gravado(ambiente):
    por = "operador.teste@glcapital.invalid"
    r = ambiente.put("/config/max_abertos", {"valor": 12, "por": por, "motivo": f"liberar para {CPF_SINTETICO}"})
    assert r.status_code == 422 and _codigo(r) == "pii_no_texto_livre" and CPF_SINTETICO not in r.text
    with ambiente.super() as conn:  # legado gravado antes da regra (ou por fora da API)
        conn.execute(
            "INSERT INTO ia.config_versao (nome, versao, valor, publicado_por, motivo) VALUES ('max_abertos', 2, '12', 'legado', %s)",
            (f"cpf {CPF_SINTETICO}",),
        )
    lido = ambiente.get("/config/max_abertos").json()
    assert lido["motivo"] == "[mascarado]" and CPF_SINTETICO not in json.dumps(lido)
    assert CPF_SINTETICO not in ambiente.get("/config").text
    assert ambiente.ctx.metricas.valor("texto_livre_mascarado_na_leitura") >= 2


def test_get_config_lista_os_vigentes_e_os_nomes_fora_do_registro(ambiente):
    with ambiente.super() as conn:
        conn.execute("INSERT INTO ia.config_versao (nome, versao, valor, publicado_por) VALUES ('chave_sem_registro', 1, 'true', 'teste')")
    ambiente.configurar("max_abertos", 11)
    corpo = ambiente.get("/config", "vigia").json()
    por_nome = {i["nome"]: i for i in corpo["itens"]}
    assert (
        corpo["fora_do_registro"] == ["chave_sem_registro"]
        and por_nome["max_abertos"]["versao"] == 2
        and por_nome["max_abertos"]["valor"] == 11
    )
    assert {"ia_ativa", "modo", "chats_teste", "bloqueio_entrada"} <= set(por_nome) and "chave_sem_registro" not in por_nome
    assert set(por_nome["modo"]) == {"nome", "versao", "valor", "publicado_em", "publicado_por", "motivo"}


def test_get_config_nome_historico_e_404(ambiente):
    ambiente.configurar("max_abertos", 11)
    ambiente.configurar("max_abertos", 12)
    um = ambiente.get("/config/max_abertos", "c360_api").json()
    assert (um["versao"], um["valor"]) == (3, 12)
    historico = ambiente.get("/config/max_abertos?historico=2").json()["itens"]
    assert [i["versao"] for i in historico] == [3, 2]
    assert ambiente.get("/config/max_abertos?historico=51").status_code == 422
    assert ambiente.get("/config/max_abertos?historico=x").status_code == 422
    assert ambiente.get("/config/nao_existe_no_registro").status_code == 404
    assert ambiente.get("/config", "n8n_braco").status_code == 200


def test_desligar_a_chave_agenda_encerrar_por_chave_inclusive_pausado_e_bloqueio_nao_agenda(ambiente):
    ambiente.ligar()
    aberto = abrir_ativo(ambiente, "aaaaaaaaaaaaaaaaaaaaaaa1", estado="aberto")
    aguardando = abrir_ativo(ambiente, "aaaaaaaaaaaaaaaaaaaaaaa2", estado="aguardando_cliente")
    pausado = abrir_ativo(ambiente, "aaaaaaaaaaaaaaaaaaaaaaa3", estado="pausado")
    abrir_ativo(ambiente, "aaaaaaaaaaaaaaaaaaaaaaa4", estado="repassando")
    abrir_ativo(ambiente, "aaaaaaaaaaaaaaaaaaaaaaa5", estado="encerrado")
    por = "operador.teste@glcapital.invalid"
    r = ambiente.put("/config/bloqueio_entrada", {"valor": True, "por": por})
    assert r.json()["efeitos"] == {"encerrar_por_chave_agendados": 0} and ambiente.fila.encerramentos == []
    r = ambiente.put("/config/ia_ativa", {"valor": True, "por": por})
    assert r.json()["efeitos"]["encerrar_por_chave_agendados"] == 0
    r = ambiente.put("/config/ia_ativa", {"valor": False, "por": por, "motivo": "parada leve de ensaio"})
    assert r.status_code == 200 and r.json()["efeitos"] == {"encerrar_por_chave_agendados": 3}
    assert {a for a, _, _ in ambiente.fila.encerramentos} == {aberto, aguardando, pausado}
    atrasos = sorted(s for _, _, s in ambiente.fila.encerramentos)
    assert atrasos == [0, 380, 760], "escalonado: um job por atendimento, o último antes de 20 min (19 min / 3)"


# --- agendamentos -------------------------------------------------------------------------------------------------------------------------


def test_agendamento_cria_reservado_com_a_linha_pendente(ambiente):
    ambiente.ligar()
    r = ambiente.post("/agendamentos", corpo_de_agendamento())
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert (corpo["estado"], corpo["tipo_extracao"], corpo["confianca"]) == ("pendente", "explicita", "alta")
    assert corpo["dispara_em"] == "2026-11-17T17:00:00-03:00"
    atd = corpo["atendimento_id"]
    estado, gatilho, retoma, lease, disparado_por, job = ambiente.consultar(
        "SELECT estado, gatilho, retoma_em, lease_ate, disparado_por, clt_job_id FROM ia.atendimento WHERE atendimento_id = %s", (atd,)
    )[0]
    assert (estado, gatilho, disparado_por, str(job)) == ("reservado", "agendamento", "dialogo_agendar", CLT_JOB)
    assert retoma == datetime(2026, 11, 17, 20, 0, tzinfo=UTC) and lease == retoma + timedelta(minutes=30)
    linha = ambiente.consultar("SELECT msg_chave, retoma_fase, estado, chave_logica, texto_hash FROM ia.agendamento")[0]
    assert (
        linha[0].startswith(f"cg:{CHAT}:")
        and linha[1:3] == ("E8", "pendente")
        and linha[3].startswith(f"agendar:{CHAT}:")
        and len(linha[4]) == 64
    )
    assert ambiente.escalar("SELECT count(*) FROM ia.cofre WHERE finalidade = 'canal'") == 1


def test_agendamento_repetido_200_e_mesma_chave_outro_texto_409(ambiente):
    ambiente.ligar()
    primeiro = ambiente.post("/agendamentos", corpo_de_agendamento()).json()
    r = ambiente.post("/agendamentos", corpo_de_agendamento())
    assert r.status_code == 200 and r.json() == {**primeiro, "repetido": True}
    r = ambiente.post("/agendamentos", corpo_de_agendamento(texto_mensagem="pode ser hoje às 18h"))
    assert r.status_code == 409 and _codigo(r) == "chave_reutilizada"
    ambiente.configurar("agenda_ativa", False)
    assert ambiente.post("/agendamentos", corpo_de_agendamento()).status_code == 200, "o retry de uma chamada que deu certo não vira erro"
    assert ambiente.escalar("SELECT count(*) FROM ia.agendamento") == 1


def test_agendamento_chave_recalculada_e_validada(ambiente):
    ambiente.ligar()
    r = ambiente.post("/agendamentos", corpo_de_agendamento(chave=f"agendar:{CHAT}:0000000000000000"))
    assert r.status_code == 422 and _codigo(r) == "chave_incoerente"
    r = ambiente.post("/agendamentos", corpo_de_agendamento(datetime_post="2026-11-17T11:55:00"))  # sem fuso
    assert r.status_code == 422 and _codigo(r) == "validacao"


@pytest.mark.parametrize(
    "preparo,codigo",
    [("agenda", "agenda_desligada"), ("ia", "ia_desligada"), ("bloqueio", "bloqueio_entrada"), ("janela", "fora_de_janela")],
)
def test_agendamento_recusas_na_ordem_do_contrato(ambiente, preparo, codigo):
    ambiente.ligar()
    if preparo == "agenda":
        ambiente.configurar("agenda_ativa", False)
        ambiente.configurar("ia_ativa", False)  # a agenda vem antes da IA
    elif preparo == "ia":
        ambiente.configurar("ia_ativa", False)
    elif preparo == "bloqueio":
        ambiente.configurar("bloqueio_entrada", True)
    else:
        ambiente.relogio.definir(datetime(2026, 11, 22, 15, 0, tzinfo=UTC))
    r = ambiente.post("/agendamentos", corpo_de_agendamento())
    assert r.status_code == 409 and _codigo(r) == codigo
    assert ambiente.escalar("SELECT count(*) FROM ia.agendamento") == 0


def test_agendamento_max_dia_e_chat_ocupado(ambiente):
    ambiente.ligar()
    ambiente.configurar("agenda_max_dia", 1)
    assert ambiente.post("/agendamentos", corpo_de_agendamento(CHAT)).status_code == 201
    r = ambiente.post("/agendamentos", corpo_de_agendamento(OUTRO_CHAT))
    assert r.status_code == 409 and _codigo(r) == "agenda_max_dia"
    ambiente.configurar("agenda_max_dia", 5)
    r = ambiente.post("/agendamentos", corpo_de_agendamento(CHAT, datetime_post="2026-11-17T11:56:00-03:00"))
    assert r.status_code == 409 and _codigo(r) == "chat_ocupado"


def test_agenda_max_dia_e_conferido_de_novo_dentro_da_trava(ambiente, monkeypatch):
    """Duas requisições concorrentes passam juntas pela checagem de FORA da trava (aqui: desligada à força); a 2ª é barrada DENTRO dela."""
    from ia_atendimento.api import agendamentos as rota

    ambiente.ligar()
    ambiente.configurar("agenda_max_dia", 1)
    monkeypatch.setattr(rota, "_recusa", lambda *_: None)
    primeira = ambiente.post("/agendamentos", corpo_de_agendamento(CHAT))
    assert primeira.status_code == 201, primeira.text
    segunda = ambiente.post("/agendamentos", corpo_de_agendamento(OUTRO_CHAT))
    assert segunda.status_code == 409 and _codigo(segunda) == "agenda_max_dia"
    assert ambiente.escalar("SELECT count(*) FROM ia.agendamento") == 1
    assert ambiente.escalar("SELECT count(*) FROM ia.atendimento WHERE chat_id = %s", (OUTRO_CHAT,)) == 0
    assert ambiente.escalar("SELECT count(*) FROM ia.cofre") == 1, "a reserva barrada não deixa cofre"


def test_gemeo_concorrente_da_mesma_chave_e_repeticao_e_nao_chat_ocupado(ambiente):
    """Duas requisições idênticas passam juntas pelo replay do começo; a que entra depois na trava vê a reserva da outra e devolve 200."""
    from ia_atendimento import agendamento as ag
    from ia_atendimento.api import agendamentos as rota

    ambiente.ligar()
    corpo = corpo_de_agendamento()
    entrada = ag.EntradaAgendamento(**corpo)
    chave, texto = ag.validar_chave(entrada), ag.texto_hash(entrada.texto_mensagem, ambiente.ctx.chaves_msg.h16)
    quando = (datetime(2026, 11, 17, 20, 0, tzinfo=UTC), "alta")
    agora = ambiente.relogio.agora()
    with ambiente.runtime() as conn:
        primeiro = rota._reservar(ambiente.ctx, conn, "n8n_braco", entrada, chave, texto, quando, agora)
        segundo = rota._reservar(ambiente.ctx, conn, "n8n_braco", entrada, chave, texto, quando, agora)
        with pytest.raises(rota.ErroApi) as erro:  # mesma chave, outro texto
            rota._reservar(ambiente.ctx, conn, "n8n_braco", entrada, chave, "f" * 64, quando, agora)
    assert primeiro[0] == 201 and segundo[0] == 200 and segundo[1]["repetido"] is True
    assert segundo[1]["atendimento_id"] == primeiro[1]["atendimento_id"] and erro.value.codigo == "chave_reutilizada"
    assert ambiente.escalar("SELECT count(*) FROM ia.agendamento") == 1


def test_agendamento_opt_out_409(ambiente):
    ambiente.ligar()
    with ambiente.super() as conn:
        conn.execute(
            "INSERT INTO ia.opt_out (pessoa_id, tipo, origem, chave_logica, idem_key, registrado_por) VALUES (%s, 'opt_out', 'operador', 't14:x',"
            " encode(sha256(convert_to('t14:x','UTF8')),'hex'), 'teste')",
            (PESSOA,),
        )
    assert _codigo(ambiente.post("/agendamentos", corpo_de_agendamento())) == "opt_out"


@pytest.mark.parametrize("texto", ["depois eu vejo", "pode ser às 15 ou às 16", "amanhã às 15h", "domingo às 10h", "às 3h da manhã"])
def test_agendamento_sem_hora_unica_valida_200_agendado_false_e_nada_gravado(ambiente, texto):
    ambiente.ligar()
    r = ambiente.post("/agendamentos", corpo_de_agendamento(texto_mensagem=texto))
    assert r.status_code == 200 and r.json() == {"agendado": False, "motivo": "sem_hora"}
    assert ambiente.escalar("SELECT count(*) FROM ia.agendamento") == 0 and ambiente.escalar("SELECT count(*) FROM ia.atendimento") == 0


def test_agendamento_so_com_token_n8n_braco_e_sem_campo_desconhecido(ambiente):
    ambiente.ligar()
    assert ambiente.post("/agendamentos", corpo_de_agendamento(), token="ti").status_code == 403
    assert ambiente.post("/agendamentos", corpo_de_agendamento(cpf=CPF_SINTETICO)).status_code == 422
    assert ambiente.post("/agendamentos", corpo_de_agendamento(clt_job_id=None)).status_code == 422, "clt_job_id é obrigatório (F13)"


def test_agendamento_em_chat_de_teste_exige_pessoa_de_teste(ambiente):
    ambiente.ligar()
    ambiente.configurar("chats_teste", [CHAT_TESTE])
    assert _codigo(ambiente.post("/agendamentos", corpo_de_agendamento(CHAT_TESTE))) == "pessoa_fora_de_pessoas_teste"
    r = ambiente.post("/agendamentos", corpo_de_agendamento(CHAT_TESTE, pessoa_id=PESSOA_TESTE))
    assert r.status_code == 201
    assert ambiente.escalar("SELECT modo FROM ia.atendimento WHERE atendimento_id = %s", (r.json()["atendimento_id"],)) == "teste"


# --- anotações e candidatos -----------------------------------------------------------------------------------------------------------


def test_anotacao_operador_sem_pii_e_com_pii_422(ambiente):
    atd = abrir_ativo(ambiente)
    corpo = {"operador": "operador.teste@glcapital.invalid", "categoria": "observacao", "texto": "cliente pediu retorno amanha"}
    r = ambiente.post(f"/atendimentos/{atd}/anotacoes", corpo, token="ti")
    assert r.status_code == 201 and r.json() == {"ordem": 1}
    assert ambiente.consultar("SELECT tipo, operador, resultado, turno, fase FROM ia.passo") == [
        ("anotacao_operador", "operador.teste@glcapital.invalid", "observacao", None, None)
    ]
    r = ambiente.post(f"/atendimentos/{atd}/anotacoes", {**corpo, "texto": f"ligar para {CPF_SINTETICO}"}, token="ti")
    assert r.status_code == 422 and _codigo(r) == "pii_no_texto_livre" and CPF_SINTETICO not in r.text
    assert ambiente.escalar("SELECT count(*) FROM ia.passo") == 1


def test_anotacao_em_atendimento_encerrado_ok_e_inexistente_404(ambiente):
    atd = abrir_ativo(ambiente, estado="encerrado")
    corpo = {"operador": "operador.teste@glcapital.invalid", "categoria": "ajuste", "texto": "revisado"}
    assert ambiente.post(f"/atendimentos/{atd}/anotacoes", corpo, token="ti").status_code == 201
    assert ambiente.post(f"/atendimentos/{uuid.uuid4()}/anotacoes", corpo, token="ti").status_code == 404
    assert ambiente.post("/atendimentos/nao-e-uuid/anotacoes", corpo, token="ti").status_code == 422
    assert ambiente.post(f"/atendimentos/{atd}/anotacoes", corpo, token="n8n_braco").status_code == 403


def test_candidatos_hmac_xor_e_repeticao(ambiente):
    atd = abrir_ativo(ambiente)
    sessao = str(uuid.uuid4())
    escolhido = {"chat_id": CHAT, "escolhido": True, "atendimento_id": str(atd), "posicao": 1, "perfil": {"banco": "FACTA"}}
    recusado = {"chat_id": OUTRO_CHAT, "escolhido": False, "recusa": "ja_em_atendimento", "perfil": {}}
    corpo = {"criterio_versao": "c1.0", "candidatos": [escolhido, recusado]}
    r = ambiente.post(f"/sessoes/{sessao}/candidatos", corpo)
    assert r.status_code == 201 and r.json() == {"gravados": 2, "repetidos": 0}
    import hashlib
    import hmac

    ref = hmac.new(ambiente.ctx.settings.chat_ref_chave.get_secret_value().encode(), CHAT.encode(), hashlib.sha256).hexdigest()
    assert ambiente.escalar("SELECT chat_ref FROM ia.candidato WHERE escolhido") == ref
    assert CHAT not in json.dumps(ambiente.consultar("SELECT c::text FROM ia.candidato c"))
    r = ambiente.post(f"/sessoes/{sessao}/candidatos", corpo)
    assert r.status_code == 200 and r.json() == {"gravados": 0, "repetidos": 2}
    r = ambiente.post(f"/sessoes/{sessao}/candidatos", {**corpo, "candidatos": [escolhido, {**recusado, "recusa": "outro_codigo"}]})
    assert r.status_code == 409 and _codigo(r) == "chave_reutilizada"


def test_candidatos_varias_chamadas_por_sessao_e_regras_do_check(ambiente):
    atd = abrir_ativo(ambiente)
    sessao = str(uuid.uuid4())
    um = {"criterio_versao": "c1.0", "candidatos": [{"chat_id": CHAT, "escolhido": True, "atendimento_id": str(atd), "perfil": {}}]}
    dois = {"criterio_versao": "c1.0", "candidatos": [{"chat_id": OUTRO_CHAT, "escolhido": False, "posicao": 2, "perfil": {}}]}
    assert ambiente.post(f"/sessoes/{sessao}/candidatos", um).status_code == 201
    assert ambiente.post(f"/sessoes/{sessao}/candidatos", dois).status_code == 201
    assert ambiente.escalar("SELECT count(*) FROM ia.candidato WHERE sessao_id = %s", (sessao,)) == 2
    ruins = [
        {"chat_id": CHAT, "escolhido": True, "perfil": {}},  # escolhido sem atendimento nem recusa
        {"chat_id": CHAT, "escolhido": True, "atendimento_id": str(atd), "recusa": "x", "perfil": {}},  # os dois
        {"chat_id": CHAT, "escolhido": False, "perfil": {}},  # sem posição nem recusa
        {"chat_id": CHAT, "escolhido": False, "atendimento_id": str(atd), "posicao": 1, "perfil": {}},
        {"chat_id": CHAT, "escolhido": False, "posicao": 1, "recusa": "x", "perfil": {}},
    ]
    for ruim in ruins:
        r = ambiente.post(f"/sessoes/{uuid.uuid4()}/candidatos", {"criterio_versao": "c1.0", "candidatos": [ruim]})
        assert r.status_code == 422, ruim
    r = ambiente.post(
        f"/sessoes/{uuid.uuid4()}/candidatos",
        {
            "criterio_versao": "c1.0",
            "candidatos": [{"chat_id": CHAT, "escolhido": True, "atendimento_id": str(uuid.uuid4()), "perfil": {}}],
        },
    )
    assert r.status_code == 422 and "atendimento_inexistente" in r.text
    r = ambiente.post(
        f"/sessoes/{uuid.uuid4()}/candidatos",
        {
            "criterio_versao": "c1.0",
            "candidatos": [
                {"chat_id": CHAT, "escolhido": False, "posicao": 1, "perfil": {"x": CPF_SINTETICO.replace(".", "").replace("-", "")}}
            ],
        },
    )
    assert r.status_code == 422 and "00000001234" not in r.text
    assert ambiente.post(f"/sessoes/{sessao}/candidatos", {"criterio_versao": "c1.0", "candidatos": []}).status_code == 422


# --- saúde ----------------------------------------------------------------------------------------------------------------------------------


def test_healthz_sem_token_e_sem_banco(ambiente):
    r = ambiente.cliente.get("/healthz")
    assert r.status_code == 200 and r.json() == {
        "ok": True,
        "version": ambiente.ctx.versao,
        "git_sha": "abc1234",
        "built_at": "2026-10-30T00:00:00Z",
    }
    assert "x-trace-id" in r.headers


def test_readyz_e_saude_exigem_token(ambiente):
    for caminho in ("/readyz", "/saude"):
        assert ambiente.get(caminho, None).status_code == 401
    r = ambiente.get("/saude", "vigia")
    assert r.status_code == 200 and r.json() == {
        "ok": True,
        "ia_ativa": False,
        "modo": "duble",
        "fila": {"todo": 0, "doing": 0, "mais_velho_s": None},
    }


def test_readyz_503_so_nas_falhas_duras_e_200_com_a_view(ambiente):
    r = ambiente.get("/readyz", "n8n_braco")
    assert r.status_code == 503 and _codigo(r) == "nao_pronto" and "workers_sem_heartbeat" in r.json()["erro"]["detalhe"]["falhas"]
    with ambiente.super() as conn:
        conn.execute("INSERT INTO procrastinate.procrastinate_workers (last_heartbeat) VALUES (now() - interval '5 seconds')")
    abrir_ativo(ambiente, estado="aberto")
    abrir_ativo(ambiente, "aaaaaaaaaaaaaaaaaaaaaaa1", estado="pausado")
    r = ambiente.get("/readyz", "ti")
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert (corpo["abertos"], corpo["pausados"], corpo["repassando"], corpo["modo"], corpo["ia_ativa"]) == (1, 1, 0, "duble", False)
    assert set(corpo) == {
        "abertos", "reservados", "repassando", "pausados", "agendados", "mais_velho_em", "proxima_retomada_em", "lease_vencidos",
        "repassando_ha_10min", "espelho_pendente_mais_velho_s", "batimento_idade_s", "modo", "ia_ativa",
    }  # fmt: skip
    assert isinstance(corpo["repassando_ha_10min"], int), "contagem, não a lista de chats"


def test_readyz_espelho_pendente_mais_velho_e_migracao_divergente(ambiente, tmp_path):
    import shutil
    from pathlib import Path

    with ambiente.super() as conn:
        conn.execute("INSERT INTO procrastinate.procrastinate_workers (last_heartbeat) VALUES (now() - interval '5 seconds')")
    atd = abrir_ativo(ambiente)
    with ambiente.super() as conn:
        conn.execute(
            "INSERT INTO ia.espelho_evento (atendimento_id, seq, evento, chave, criado_em) VALUES (%s, 1, 'assumiu', 'venda:abc', now() - interval '3 minutes')",
            (atd,),
        )
    # o banco do teste nasceu pelo `aplicar` (ledger completo): a pasta real confere
    r = ambiente.get("/readyz")
    assert r.status_code == 200 and 170 <= r.json()["espelho_pendente_mais_velho_s"] <= 200
    copia = tmp_path / "migracoes"
    shutil.copytree(Path(__file__).resolve().parent.parent / "migrations", copia)
    (copia / "0001_esquema.up.sql").write_bytes((copia / "0001_esquema.up.sql").read_bytes() + b"\n-- editada\n")
    ambiente.trocar(diretorio_migracoes=copia)
    r = ambiente.get("/readyz")
    assert r.status_code == 503 and "migracao_divergente" in r.json()["erro"]["detalhe"]["falhas"]


def test_rota_inexistente_e_metodo_errado_tem_o_mesmo_envelope(ambiente):
    r = ambiente.cliente.get("/nao-existe")
    assert r.status_code == 404 and r.json()["erro"]["codigo"] == "rota_inexistente" and len(r.json()["trace_id"]) == 32
    r = ambiente.cliente.delete("/config/modo")
    assert r.status_code == 405 and r.json()["erro"]["codigo"] == "metodo_nao_permitido"
    assert ambiente.cliente.get("/openapi.json").status_code == 404 and ambiente.cliente.get("/docs").status_code == 404


def test_erro_interno_devolve_envelope_sem_detalhe_e_nao_loga_o_corpo(ambiente, caplog):
    abrir_ativo(ambiente)

    class Quebra:
        def turno(self, *_):
            raise RuntimeError("zebra-quantica-no-erro")

        iniciar = encerrar_por_chave = turno

    ambiente.trocar(enfileirador=Quebra())
    with caplog.at_level("DEBUG"):
        r = ambiente.evento_chatguru(mensagem_nativa("zebra-quantica-parcela"))
    assert r.status_code == 500 and r.json()["erro"]["codigo"] == "erro_interno"
    assert "zebra" not in r.text and "zebra" not in caplog.text, "nem o texto do cliente nem a mensagem da exceção vão ao log"
    assert TOKENS["ti"] not in caplog.text
