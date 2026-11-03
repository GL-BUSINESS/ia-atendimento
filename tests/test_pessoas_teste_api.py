"""`chats_teste` ↔ `pessoas_teste` na API (B2.4, risco 4 «fantasma de venda em `teste`»), com o catálogo REAL das 84 pessoas e o Postgres descartável.

O que se fecha: chat de cliente na lista `chats_teste` por engano faria a IA conversar de verdade e «digitar» no dublê. Por isso `chats_teste` só aceita
chat cuja pessoa está em `pessoas_teste`; a entrada de teste só abre com pessoa de `pessoas_teste`; só a TI mexe na lista e fica registro (quem, quando, por quê).
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ia_atendimento.api.ambiente import _montar
from ia_atendimento.conversa import chave_id_do_mes
from ia_atendimento.pessoas_teste import SEM_PESSOAS_DE_TESTE, PessoasTesteFixas, catalogo_padrao
from tests import apoio_api
from tests import fixtures_fila as ff
from tests.apoio_api import (
    CHAT,
    CHAT_TESTE,
    CHAVE_GATEWAY,
    OUTRO_CHAT,
    PESSOA,
    TOKENS,
    abrir_ativo,
    corpo_de_agendamento,
    entrada_para,
    settings_de_teste,
)
from tests.estado_apoio import semear_versoes
from tests.test_ambiente_api import SAIDA

ambiente = apoio_api.ambiente  # a fixture mora em `apoio_api`; este nome a registra neste módulo
pytestmark = pytest.mark.banco
POR = "operador.teste@glcapital.invalid"
CATALOGO = catalogo_padrao()
P01 = str(CATALOGO.por_persona("P01").pessoa_id)
P_M01 = str(CATALOGO.por_persona("P-M01").pessoa_id)


def _codigo(resposta) -> str:
    return resposta.json()["erro"]["codigo"]


def _vigente(ambiente) -> tuple[int, list[str]]:
    r = ambiente.get("/config/chats_teste")
    assert r.status_code == 200, r.text
    return r.json()["versao"], r.json()["valor"]


def _com_catalogo(ambiente, chats: dict[str, str]) -> None:
    """A API como o boot a deixa com `PESSOAS_TESTE_ARQUIVO` = as 84 pessoas do catálogo e estes chats (chat → persona)."""
    ambiente.trocar(pessoas_teste=CATALOGO.como_pessoas_teste(chats))


def test_chats_teste_so_com_pessoa_de_teste(ambiente):
    """`PUT /config/chats_teste` só aceita chat cuja pessoa está em `pessoas_teste`; qualquer outro derruba o PUT inteiro e a lista fica como estava."""
    _com_catalogo(ambiente, {CHAT_TESTE: "P01"})
    v0, vazio = _vigente(ambiente)
    assert vazio == []

    r = ambiente.put("/config/chats_teste", {"valor": [CHAT_TESTE], "por": POR, "motivo": "ensaio_b"})
    assert r.status_code == 200 and r.json()["valor"] == [CHAT_TESTE] and r.json()["versao"] == v0 + 1

    for recusado in ([OUTRO_CHAT], [CHAT_TESTE, OUTRO_CHAT], [CHAT]):  # chat sem pessoa no arquivo, mistura, chat de cliente
        r = ambiente.put("/config/chats_teste", {"valor": recusado, "por": POR})
        assert r.status_code == 422 and _codigo(r) == "pessoa_fora_de_pessoas_teste", recusado
        assert r.json()["erro"]["detalhe"] == {"quantos": 1}
    assert _vigente(ambiente) == (v0 + 1, [CHAT_TESTE]), "o PUT recusado não grava nada"


def test_chats_teste_chat_ligado_a_pessoa_que_nao_e_de_teste_nao_entra(ambiente):
    """O arquivo liga o chat a uma pessoa de CLIENTE (fora do catálogo): `pessoa_do_chat` devolve nulo e a lista recusa. Sem arquivo, ninguém é de teste."""
    cliente = uuid.UUID(PESSOA)
    ambiente.trocar(pessoas_teste=PessoasTesteFixas(CATALOGO.pessoa_ids(), {CHAT_TESTE: cliente}))
    r = ambiente.put("/config/chats_teste", {"valor": [CHAT_TESTE], "por": POR})
    assert r.status_code == 422 and _codigo(r) == "pessoa_fora_de_pessoas_teste"
    ambiente.trocar(pessoas_teste=SEM_PESSOAS_DE_TESTE)
    r = ambiente.put("/config/chats_teste", {"valor": [CHAT_TESTE], "por": POR})
    assert r.status_code == 422 and _codigo(r) == "pessoa_fora_de_pessoas_teste"
    assert _vigente(ambiente)[1] == []


def test_chats_teste_chat_de_cliente_nao_entra_mesmo_ligado_a_uma_pessoa_de_teste(ambiente):
    """Fantasma de venda: o chat TEM atendimento `real` anterior (é de cliente). Ligá-lo a uma pessoa de teste no arquivo não o salva."""
    abrir_ativo(ambiente, CHAT_TESTE, estado="encerrado", modo="real")
    _com_catalogo(ambiente, {CHAT_TESTE: "P01"})
    r = ambiente.put("/config/chats_teste", {"valor": [CHAT_TESTE], "por": POR})
    assert r.status_code == 422 and _codigo(r) == "chat_de_cliente"
    assert _vigente(ambiente)[1] == []


def test_chats_teste_chat_com_historico_duble_de_cliente_nao_entra_mas_o_de_pessoa_de_teste_entra(ambiente):
    """R1-06: o seed de `modo` é `duble`. Chat de cliente real que passou pelo orquestrador em `duble` (pessoa fora de `pessoas_teste`) NÃO entra em
    `chats_teste`; o chat que só teve atendimento `duble`/`teste` de pessoa do catálogo (o harness, o ensaio) entra."""
    _com_catalogo(ambiente, {CHAT_TESTE: "P01"})
    with ambiente.super() as conn:
        ff.inserir_atendimento(conn, estado="encerrado", chat_id=CHAT_TESTE, modo="duble", pessoa_id=uuid.UUID(PESSOA))  # pessoa de CLIENTE
    r = ambiente.put("/config/chats_teste", {"valor": [CHAT_TESTE], "por": POR})
    assert r.status_code == 422 and _codigo(r) == "chat_de_cliente", r.text
    assert r.json()["erro"]["detalhe"] == {"quantos": 1}
    assert _vigente(ambiente)[1] == []
    with ambiente.super() as conn:
        conn.execute("DELETE FROM ia.atendimento WHERE chat_id = %s", (CHAT_TESTE,))
        for modo in ("duble", "teste"):  # histórico só de pessoa de teste: não barra
            ff.inserir_atendimento(conn, estado="encerrado", chat_id=CHAT_TESTE, modo=modo, pessoa_id=CATALOGO.por_persona("P01").pessoa_id)
    r = ambiente.put("/config/chats_teste", {"valor": [CHAT_TESTE], "por": POR})
    assert r.status_code == 200 and r.json()["valor"] == [CHAT_TESTE], r.text


def test_chats_teste_so_a_ti_mexe_na_lista_e_fica_registro(ambiente):
    """Só a origem `ti` grava `chats_teste` (n8n, vigia e c360_api tomam 403) e a versão leva quem, o motivo e o instante."""
    _com_catalogo(ambiente, {CHAT_TESTE: "P01"})
    v0, _ = _vigente(ambiente)
    for origem in ("n8n_braco", "c360_api", "vigia"):
        r = ambiente.put("/config/chats_teste", {"valor": [CHAT_TESTE], "por": POR}, token=origem)
        assert r.status_code == 403 and _codigo(r) == "origem_nao_autorizada", origem
    assert _vigente(ambiente) == (v0, [])

    r = ambiente.put("/config/chats_teste", {"valor": [CHAT_TESTE], "por": POR, "motivo": "ensaio_b_18_11", "versao_esperada": v0})
    assert r.status_code == 200 and r.json()["versao"] == v0 + 1
    historico = ambiente.get("/config/chats_teste?historico=5").json()["itens"]
    assert (historico[0]["versao"], historico[0]["publicado_por"], historico[0]["motivo"]) == (v0 + 1, POR, "ensaio_b_18_11")
    assert historico[0]["valor"] == [CHAT_TESTE] and historico[0]["publicado_em"]
    # a versão está na tabela de registro, não só na resposta: quem publicou, por quê, e a lista que ficou
    linha = ambiente.consultar(
        "SELECT versao, valor, publicado_por, motivo FROM ia.config_versao WHERE nome = 'chats_teste' ORDER BY versao DESC LIMIT 1"
    )[0]
    assert (linha[0], linha[1], linha[2], linha[3]) == (v0 + 1, [CHAT_TESTE], POR, "ensaio_b_18_11")
    # versão esperada velha = 409; operador com CPF no nome = recusado antes de gravar
    r = ambiente.put("/config/chats_teste", {"valor": [], "por": POR, "versao_esperada": v0})
    assert r.status_code == 409 and _codigo(r) == "config_corrida"
    r = ambiente.put("/config/chats_teste", {"valor": [], "por": "000.000.012-34"})
    assert r.status_code == 422
    assert _vigente(ambiente) == (v0 + 1, [CHAT_TESTE])


def test_chats_teste_entrada_de_teste_abre_com_pessoa_do_catalogo_e_nao_com_a_de_cliente(ambiente):
    """No chat de teste a entrada só abre com pessoa de `pessoas_teste`: o catálogo abre (`persona_id` junto), a pessoa de cliente é recusada."""
    ambiente.ligar()
    _com_catalogo(ambiente, {CHAT_TESTE: "P01"})
    ambiente.configurar("chats_teste", [CHAT_TESTE])
    r = ambiente.post("/atendimentos", entrada_para(CHAT_TESTE, pessoa_id=PESSOA, modo="teste"))
    assert r.status_code == 422 and _codigo(r) == "pessoa_fora_de_pessoas_teste"
    r = ambiente.post("/atendimentos", entrada_para(CHAT_TESTE, pessoa_id=P01, persona_id="P01", modo="teste"))
    assert r.status_code == 201 and r.json()["modo"] == "teste", r.text
    assert ambiente.escalar("SELECT pessoa_id::text FROM ia.atendimento WHERE atendimento_id = %s", (r.json()["atendimento_id"],)) == P01
    # persona de teste em chat de cliente: nunca (`persona_id` só com `chat_id ∈ chats_teste`)
    r = ambiente.post("/atendimentos", entrada_para(CHAT, pessoa_id=P_M01, persona_id="P-M01"))
    assert r.status_code == 422 and _codigo(r) == "persona_fora_de_teste"


def test_chats_teste_agendamento_de_teste_tambem_exige_pessoa_do_catalogo(ambiente):
    ambiente.ligar()
    _com_catalogo(ambiente, {CHAT_TESTE: "P-M01"})
    ambiente.configurar("chats_teste", [CHAT_TESTE])
    assert _codigo(ambiente.post("/agendamentos", corpo_de_agendamento(CHAT_TESTE))) == "pessoa_fora_de_pessoas_teste"
    r = ambiente.post("/agendamentos", corpo_de_agendamento(CHAT_TESTE, pessoa_id=P_M01))
    assert r.status_code == 201
    assert ambiente.escalar("SELECT modo FROM ia.atendimento WHERE atendimento_id = %s", (r.json()["atendimento_id"],)) == "teste"


def test_pessoas_teste_arquivo_gerado_pelo_kit_vale_no_boot_real(banco, tmp_path):
    """Ponta a ponta do kit `config/chats-teste.sh`: o JSON que o CLI monta é o `PESSOAS_TESTE_ARQUIVO` do boot, e o `PUT` da TI passa a valer."""
    import base64
    import os

    arquivo = tmp_path / "pessoas_teste.json"
    feito = subprocess.run(
        [sys.executable, "-m", "ia_atendimento.pessoas_teste", "arquivo", "--par", f"{CHAT_TESTE}=P13", "--saida", str(arquivo)],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert feito.returncode == 0, feito.stderr
    (tmp_path / "chaves-api.json").write_text(
        json.dumps({"1": base64.b64encode(os.urandom(32)).decode(), "2": base64.b64encode(os.urandom(32)).decode()})
    )
    (tmp_path / "gw.keys").write_text(CHAVE_GATEWAY + "\n")
    (tmp_path / "saida.json").write_text(json.dumps(SAIDA))
    for nome in ("chaves-api.json", "gw.keys", "saida.json"):
        (tmp_path / nome).chmod(0o600)
    with ff.abrir(banco, "postgres") as conn:
        semear_versoes(conn)
    app = _montar(settings_de_teste(banco, tmp_path, chave_aes_id=chave_id_do_mes(datetime.now(UTC)), pessoas_teste_arquivo=arquivo))
    cab = {"x-ia-token": TOKENS["ti"], "content-type": "application/json"}
    with TestClient(app, raise_server_exceptions=False) as cliente:
        ok = cliente.put("/config/chats_teste", content=json.dumps({"valor": [CHAT_TESTE], "por": POR}), headers=cab)
        assert ok.status_code == 200, ok.text
        fora = cliente.put("/config/chats_teste", content=json.dumps({"valor": [OUTRO_CHAT], "por": POR}), headers=cab)
        assert fora.status_code == 422 and fora.json()["erro"]["codigo"] == "pessoa_fora_de_pessoas_teste"
    assert Path(arquivo).stat().st_mode & 0o777 == 0o600
