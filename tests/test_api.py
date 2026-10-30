"""API de entrada (B1.5, sp01 T7): POST /atendimentos e GET /atendimentos/por-chave, contra o Postgres 18 descartável.

A fila é um espião (`EspiaDeFila`); a transação conjunta com o job é provada em `test_enfileirador.py`. Dado sintético: telefone do contrato 08 §15,
CPF `000.000.0nn` só como valor RECUSADO, e-mails `@glcapital.invalid`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from ia_atendimento.api.contexto import PreVooFalhou
from tests import apoio_api
from tests.apoio_api import (
    CHAT,
    CHAT_TESTE,
    OUTRO_CHAT,
    PESSOA,
    PESSOA_TESTE,
    TELEFONE,
    abrir_ativo,
    corpo_de_entrada,
    entrada_para,
)

ambiente = apoio_api.ambiente  # a fixture mora em `apoio_api`; este nome a registra neste módulo
pytestmark = pytest.mark.banco
CPF_SINTETICO = "000.000.012-34"


def _codigo(resposta) -> str:
    return resposta.json()["erro"]["codigo"]


# --- POST /atendimentos ----------------------------------------------------------------------------------------------------------------


def test_entrada_cria_reservado_grava_cofre_e_enfileira_iniciar(ambiente):
    ambiente.ligar()
    r = ambiente.post("/atendimentos", corpo_de_entrada())
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert (corpo["estado"], corpo["modo"], corpo["faixa_esforco"], corpo["repetido"], corpo["chatbot_antes"]) == (
        "reservado",
        "duble",
        "media",
        False,
        None,
    )
    atd = uuid.UUID(corpo["atendimento_id"])
    estado, fase, lease, origem = ambiente.consultar(
        "SELECT estado, fase, lease_ate, origem FROM ia.atendimento WHERE atendimento_id = %s", (atd,)
    )[0]
    assert (estado, fase, origem) == ("reservado", "E0", "n8n_braco")
    assert lease == ambiente.relogio.agora() + timedelta(seconds=120)
    assert ambiente.fila.inicios == [(atd, CHAT)]
    assert ambiente.escalar("SELECT count(*) FROM ia.cofre WHERE atendimento_id = %s AND finalidade = 'canal'", (atd,)) == 1


def test_o_numero_do_chat_so_existe_cifrado_no_cofre(ambiente):
    ambiente.ligar()
    assert ambiente.post("/atendimentos", corpo_de_entrada()).status_code == 201
    cifra = bytes(ambiente.escalar("SELECT cifra FROM ia.cofre"))
    assert TELEFONE.encode() not in cifra
    # nenhuma coluna de CPF ou telefone em lugar nenhum do esquema, e o valor não está em texto algum do atendimento
    assert (
        ambiente.consultar(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'ia' AND column_name ~* '(cpf|telefone|celular|phone_number|chat_number)'"
        )
        == []
    )
    assert ambiente.escalar("SELECT count(*) FROM ia.atendimento a WHERE a::text LIKE %s", (f"%{TELEFONE}%",)) == 0


def test_entrada_idempotente_mesmo_com_chat_ocupado_e_chave_desligada(ambiente):
    ambiente.ligar()
    primeiro = ambiente.post("/atendimentos", corpo_de_entrada()).json()
    ambiente.configurar("ia_ativa", False)
    r = ambiente.post("/atendimentos", corpo_de_entrada())
    assert r.status_code == 200 and r.json()["atendimento_id"] == primeiro["atendimento_id"] and r.json()["repetido"] is True
    assert ambiente.escalar("SELECT count(*) FROM ia.atendimento") == 1
    assert len(ambiente.fila.inicios) == 1, "o replay não enfileira de novo"


def test_replay_de_outro_operador_devolve_200_e_outra_pessoa_409(ambiente):
    ambiente.ligar()
    assert ambiente.post("/atendimentos", corpo_de_entrada()).status_code == 201
    outro_operador = corpo_de_entrada(disparado_por="outro.operador@glcapital.invalid", sessao_id=str(uuid.uuid4()), perfil={"banco": "C6"})
    assert ambiente.post("/atendimentos", outro_operador).status_code == 200
    r = ambiente.post("/atendimentos", corpo_de_entrada(pessoa_id="44444444-4444-7444-8444-444444444444"))
    assert r.status_code == 409 and _codigo(r) == "chave_reutilizada"


def test_replay_com_outra_comissao_e_outra_faixa_continua_200(ambiente):
    ambiente.ligar()
    primeiro = ambiente.post("/atendimentos", corpo_de_entrada()).json()
    r = ambiente.post("/atendimentos", corpo_de_entrada(comissao_esperada_brl=500, faixa_esforco="alta"))
    assert r.status_code == 200 and r.json()["faixa_esforco"] == "media" == primeiro["faixa_esforco"], (
        "devolve o GRAVADO, nada é atualizado"
    )


def test_segundo_atendimento_no_chat_409_chat_ocupado(ambiente):
    ambiente.ligar()
    assert ambiente.post("/atendimentos", corpo_de_entrada()).status_code == 201
    r = ambiente.post("/atendimentos", entrada_para(CHAT))
    assert r.status_code == 409 and _codigo(r) == "chat_ocupado"


def test_ia_desligada_409_e_a_ia_nasce_desligada(ambiente):
    r = ambiente.post("/atendimentos", corpo_de_entrada())
    assert r.status_code == 409 and _codigo(r) == "ia_desligada"
    assert ambiente.escalar("SELECT count(*) FROM ia.atendimento") == 0 and ambiente.fila.inicios == []


def _preparar_recusa(amb, motivo: str) -> dict:
    """Deixa a config de modo que `motivo` seja a PRIMEIRA recusa; devolve o corpo a postar."""
    corpo = corpo_de_entrada()
    if motivo == "bloqueio_entrada":
        amb.configurar("bloqueio_entrada", True)
    elif motivo == "fora_de_janela":
        amb.relogio.definir(datetime(2026, 11, 22, 15, 0, tzinfo=UTC))  # domingo
        corpo = corpo_de_entrada(ultimo_cliente_em="2026-11-22T11:00:00-03:00")
    elif motivo == "opt_out":
        with amb.super() as conn:
            conn.execute(
                "INSERT INTO ia.opt_out (pessoa_id, tipo, origem, chave_logica, idem_key, registrado_por) VALUES (%s, 'opt_out', 'operador', 't14:x',"
                " encode(sha256(convert_to('t14:x','UTF8')),'hex'), 'teste')",
                (PESSOA,),
            )
    elif motivo == "janela_24h":
        corpo = corpo_de_entrada(ultimo_cliente_em="2026-11-14T10:00:00-03:00")
    elif motivo == "teto_atingido":
        amb.configurar("teto_mensal_brl", 0)
    elif motivo == "teto_diario":
        amb.configurar("subteto_dia", 0)
    elif motivo == "disparos_dia":
        abrir_ativo(amb, OUTRO_CHAT, estado="aberto")
        amb.configurar("agenda_max_dia", 1)  # o contrato exige agenda_max_dia <= max_disparos_dia
        amb.configurar("max_disparos_dia", 1)
    elif motivo == "abertos_max":
        abrir_ativo(amb, OUTRO_CHAT, estado="aberto")
        amb.configurar("max_abertos", 1)
    return corpo


@pytest.mark.parametrize(
    "motivo",
    ["bloqueio_entrada", "fora_de_janela", "opt_out", "janela_24h", "teto_atingido", "teto_diario", "disparos_dia", "abertos_max"],
)
def test_recusas_pela_config(ambiente, motivo):
    ambiente.ligar()
    corpo = _preparar_recusa(ambiente, motivo)
    r = ambiente.post("/atendimentos", corpo)
    assert r.status_code == 409 and _codigo(r) == motivo, r.text
    assert ambiente.escalar("SELECT count(*) FROM ia.atendimento WHERE chat_id = %s", (CHAT,)) == 0, "recusa não grava nada"
    assert ambiente.fila.inicios == []


def test_janela_24h_com_template_aprovado_aceita_e_sem_ultimo_cliente_em_aceita(ambiente):
    ambiente.ligar()
    antigo = corpo_de_entrada(ultimo_cliente_em="2026-11-14T10:00:00-03:00")
    ambiente.trocar(template_de_abertura_aprovado=lambda: True)
    assert ambiente.post("/atendimentos", antigo).status_code == 201
    ambiente.trocar(template_de_abertura_aprovado=lambda: False)
    sem_hora = entrada_para(OUTRO_CHAT)
    del sem_hora["ultimo_cliente_em"]
    assert ambiente.post("/atendimentos", sem_hora).status_code == 201, "desconhecido: aceita e decide no iniciar (08 §8)"


def test_ultimo_cliente_em_no_futuro_422(ambiente):
    ambiente.ligar()
    r = ambiente.post("/atendimentos", corpo_de_entrada(ultimo_cliente_em="2026-11-17T20:00:00-03:00"))
    assert r.status_code == 422 and r.json()["erro"]["campo"] == "ultimo_cliente_em"


def test_pre_voo_falho_409_e_nada_muda(ambiente):
    ambiente.ligar()

    class Falha:
        def verificar(self) -> None:
            raise PreVooFalhou("provedor_fora")

    ambiente.trocar(pre_voo=Falha())
    r = ambiente.post("/atendimentos", corpo_de_entrada())
    assert r.status_code == 409 and _codigo(r) == "provedor_fora"
    assert ambiente.escalar("SELECT count(*) FROM ia.atendimento") == 0 and ambiente.escalar("SELECT count(*) FROM ia.cofre") == 0


@pytest.mark.parametrize("gatilho,codigo", [("esteira_parada", "gatilho_desabilitado"), ("agendamento", "validacao")])
def test_gatilho_so_venda(ambiente, gatilho, codigo):
    ambiente.ligar()
    r = ambiente.post("/atendimentos", corpo_de_entrada(gatilho=gatilho))
    assert r.status_code == 422 and _codigo(r) == codigo


def test_chat_em_chats_teste_nasce_teste_e_teste_fora_da_lista_422(ambiente):
    ambiente.ligar()
    ambiente.configurar("chats_teste", [CHAT_TESTE])
    r = ambiente.post("/atendimentos", entrada_para(CHAT_TESTE, pessoa_id=PESSOA_TESTE, modo="teste"))
    assert r.status_code == 201 and r.json()["modo"] == "teste", r.text
    r = ambiente.post("/atendimentos", entrada_para(CHAT, modo="teste"))
    assert r.status_code == 422 and _codigo(r) == "teste_fora_da_lista"


def test_chat_de_teste_exige_pessoa_de_pessoas_teste(ambiente):
    ambiente.ligar()
    ambiente.configurar("chats_teste", [CHAT_TESTE])
    r = ambiente.post("/atendimentos", entrada_para(CHAT_TESTE))  # PESSOA não é de teste
    assert r.status_code == 422 and _codigo(r) == "pessoa_fora_de_pessoas_teste"


def test_persona_id_so_com_chat_de_teste(ambiente):
    ambiente.ligar()
    r = ambiente.post("/atendimentos", entrada_para(CHAT, persona_id="P01"))
    assert r.status_code == 422 and _codigo(r) == "persona_fora_de_teste"
    ambiente.configurar("chats_teste", [CHAT_TESTE])
    r = ambiente.post("/atendimentos", entrada_para(CHAT_TESTE, pessoa_id=PESSOA_TESTE, persona_id="P01"))
    assert r.status_code == 201
    assert ambiente.escalar("SELECT persona_id FROM ia.atendimento WHERE atendimento_id = %s", (r.json()["atendimento_id"],)) == "P01"


def test_chat_de_cliente_nao_entra_em_chats_teste(ambiente):
    """Chat com atendimento anterior `real`/`sombra` é de cliente; chat sem pessoa em `pessoas_teste` também não entra (08 §5.6, §6)."""
    abrir_ativo(ambiente, CHAT, estado="encerrado", modo="real")
    r = ambiente.put("/config/chats_teste", {"valor": [CHAT], "por": "operador.teste@glcapital.invalid"})
    assert r.status_code == 422 and _codigo(r) == "chat_de_cliente"
    r = ambiente.put("/config/chats_teste", {"valor": [OUTRO_CHAT], "por": "operador.teste@glcapital.invalid"})
    assert r.status_code == 422 and _codigo(r) == "pessoa_fora_de_pessoas_teste"
    r = ambiente.put("/config/chats_teste", {"valor": [CHAT_TESTE], "por": "operador.teste@glcapital.invalid"})
    assert r.status_code == 200 and r.json()["valor"] == [CHAT_TESTE]


def test_faixa_calculada_pela_comissao_e_divergente_422(ambiente):
    ambiente.ligar()
    r = ambiente.post("/atendimentos", entrada_para(CHAT, comissao_esperada_brl=500, faixa_esforco="alta"))
    assert r.status_code == 201 and r.json()["faixa_esforco"] == "alta"
    assert ambiente.escalar("SELECT comissao_esperada_brl FROM ia.atendimento") == 500
    r = ambiente.post("/atendimentos", entrada_para(OUTRO_CHAT, faixa_esforco="alta"))  # sem comissão a faixa é media
    assert r.status_code == 422 and _codigo(r) == "faixa_incoerente"
    r = ambiente.post("/atendimentos", entrada_para("bbbbbbbbbbbbbbbbbbbbbbbb", comissao_esperada_brl=100, faixa_esforco="muito_alta"))
    assert r.status_code == 422 and _codigo(r) == "faixa_incoerente"


def test_chave_logica_incoerente_422(ambiente):
    ambiente.ligar()
    r = ambiente.post("/atendimentos", corpo_de_entrada(chave_logica="venda:" + "0" * 32))
    assert r.status_code == 422 and _codigo(r) == "chave_incoerente"


def test_sem_artefato_versao_503(ambiente):
    ambiente.ligar()
    ambiente.consultar("SELECT 1")
    with ambiente.super() as conn:
        conn.execute("DELETE FROM ia.artefato_versao WHERE tipo = 'motor'")
    r = ambiente.post("/atendimentos", corpo_de_entrada())
    assert r.status_code == 503 and _codigo(r) == "artefatos_ausentes"


def test_sem_token_401_e_origem_errada_403(ambiente):
    ambiente.ligar()
    assert ambiente.post("/atendimentos", corpo_de_entrada(), token=None).status_code == 401
    assert (
        ambiente.cliente.post(
            "/atendimentos", json=corpo_de_entrada(), headers={"x-ia-token": "token-que-nao-existe-0123456789abcdef"}
        ).status_code
        == 401
    )
    r = ambiente.post("/atendimentos", corpo_de_entrada(), token="vigia")
    assert r.status_code == 403 and _codigo(r) == "origem_nao_autorizada"
    assert ambiente.escalar("SELECT count(*) FROM ia.atendimento") == 0


def test_nenhum_campo_de_cpf_no_corpo_nem_no_banco(ambiente):
    ambiente.ligar()
    for campo in ("cpf", "cpf_hash", "documento", "celular", "nome", "email"):
        r = ambiente.post("/atendimentos", corpo_de_entrada(**{campo: CPF_SINTETICO}))
        assert r.status_code == 422 and _codigo(r) == "campo_desconhecido", campo
        assert CPF_SINTETICO not in r.text
    assert ambiente.escalar("SELECT count(*) FROM ia.atendimento") == 0


def test_corpo_com_cpf_no_perfil_ou_na_nota_422_sem_ecoar_valor(ambiente):
    ambiente.ligar()
    for corpo in (
        corpo_de_entrada(perfil={"documento": "00000001234"}),
        corpo_de_entrada(motivo_escolha="outro", motivo_escolha_nota=f"cliente {CPF_SINTETICO}"),
        corpo_de_entrada(perfil={"contato": "fulano@glcapital.invalid"}),
    ):
        r = ambiente.post("/atendimentos", corpo)
        assert r.status_code == 422, r.text
        assert CPF_SINTETICO not in r.text and "00000001234" not in r.text and "fulano@" not in r.text


def test_erro_de_validacao_nunca_ecoa_o_valor_recebido(ambiente):
    ambiente.ligar()
    r = ambiente.post("/atendimentos", corpo_de_entrada(chat_id="valor-secreto-que-nao-pode-voltar", pessoa_id="tambem-nao-pode-voltar"))
    assert r.status_code == 422
    assert "valor-secreto" not in r.text and "tambem-nao" not in r.text
    campos = {c["campo"] for c in r.json()["erro"]["detalhe"]["campos"]}
    assert {"chat_id", "pessoa_id"} <= campos
    assert len(r.json()["trace_id"]) == 32


def test_corpo_que_nao_e_json_ou_nao_e_objeto_422(ambiente):
    for bruto in (b"isto nao e json {{", b"[1, 2]", b'"texto"', b""):
        r = ambiente.post("/atendimentos", bruto)
        assert r.status_code == 422 and r.json()["erro"]["campo"] == "(corpo)"
        assert "isto nao" not in r.text


# --- GET /atendimentos/por-chave -----------------------------------------------------------------------------------------------------


def test_por_chave_devolve_estado_sem_pii_e_404_se_nao_existe(ambiente):
    ambiente.ligar()
    atd = ambiente.post("/atendimentos", corpo_de_entrada()).json()["atendimento_id"]
    for token in ("n8n_braco", "vigia", "ti"):
        r = ambiente.get("/atendimentos/por-chave/" + corpo_de_entrada()["chave_logica"], token)
        assert r.status_code == 200 and r.json() == {"atendimento_id": atd, "estado": "reservado", "modo": "duble", "encerrado": False}
    assert ambiente.get("/atendimentos/por-chave/venda:" + "f" * 32).status_code == 404
    assert ambiente.get("/atendimentos/por-chave/Nao%20e%20chave").status_code == 422
    assert ambiente.get("/atendimentos/por-chave/" + CHAVE_QUALQUER, "c360_api").status_code == 403


CHAVE_QUALQUER = "venda:" + "a" * 32
