"""G-0121 e G-0122 (revisão 0911): o corpo do braço do n8n (04 §2.5 passo 7) entra sem 422.

- G-0121: o corpo leva `matricula` (D-29). A API respondia 422 `campo_desconhecido` e o braço cancelava o disparo. Agora é campo opcional
  (`^[0-9A-Za-z./-]{1,40}$`), gravado só no cofre `digitacao` na mesma transação da abertura, fora do fingerprint, da resposta e do log.
- G-0122: `criterio_versao` é o sha256 hex do critério (04). A guarda de documento recusava qualquer valor com 10+ dígitos seguidos, o que
  pega ~18 % dos hashes. Hex de 64 minúsculo é isento; qualquer outro valor segue a guarda.
"""

from __future__ import annotations

import hashlib
import logging
import uuid

import pytest

from ia_atendimento import cofre
from tests import apoio_api
from tests.apoio_api import CHAT, OUTRO_CHAT, abrir_ativo, corpo_de_entrada

ambiente = apoio_api.ambiente
pytestmark = pytest.mark.banco
MATRICULA = "MAT-0007/2026.B"  # sintética, na forma do 08 §3
HASH_COM_DIGITOS = "0123456789" + "abcdef" * 9  # 64 hex com 10 dígitos seguidos: o caso que caía em `pii_no_texto_livre`


def _matricula_no_cofre(ambiente, atendimento_id: str) -> dict | None:
    with ambiente.super() as conn:
        return cofre.ler(conn, uuid.UUID(atendimento_id), "digitacao", chaveiro=ambiente.ctx.chaveiro)


def test_hash_de_teste_tem_10_digitos_seguidos():
    assert len(HASH_COM_DIGITOS) == 64 and "0123456789" in HASH_COM_DIGITOS
    assert all(c in "0123456789abcdef" for c in HASH_COM_DIGITOS)


def test_matricula_aceita_e_so_no_cofre_digitacao(ambiente, caplog):
    ambiente.ligar()
    caplog.set_level(logging.DEBUG)
    r = ambiente.post("/atendimentos", corpo_de_entrada(matricula=MATRICULA))
    assert r.status_code == 201, r.text
    assert MATRICULA not in r.text and MATRICULA not in caplog.text
    atd = r.json()["atendimento_id"]
    assert _matricula_no_cofre(ambiente, atd) == {"matricula": MATRICULA}
    linha = ambiente.consultar("SELECT a::text FROM ia.atendimento a WHERE atendimento_id = %s", (atd,))[0][0]
    assert MATRICULA not in linha


def test_sem_matricula_nao_cria_cofre_digitacao(ambiente):
    ambiente.ligar()
    r = ambiente.post("/atendimentos", corpo_de_entrada())
    assert r.status_code == 201, r.text
    assert _matricula_no_cofre(ambiente, r.json()["atendimento_id"]) is None


def test_matricula_fica_fora_do_fingerprint_do_replay(ambiente):
    """O retry do braço com outra matrícula é o MESMO atendimento (200 repetido), e o cofre não é regravado pelo replay."""
    ambiente.ligar()
    primeiro = ambiente.post("/atendimentos", corpo_de_entrada(matricula=MATRICULA))
    assert primeiro.status_code == 201
    replay = ambiente.post("/atendimentos", corpo_de_entrada(matricula="OUTRA-01"))
    assert replay.status_code == 200 and replay.json()["repetido"] is True
    assert replay.json()["atendimento_id"] == primeiro.json()["atendimento_id"]
    assert _matricula_no_cofre(ambiente, primeiro.json()["atendimento_id"]) == {"matricula": MATRICULA}


@pytest.mark.parametrize("ruim", ["", "tem espaço", "a" * 41, "mat;drop", 12345])
def test_matricula_fora_da_forma_422_sem_eco(ambiente, ruim):
    ambiente.ligar()
    r = ambiente.post("/atendimentos", corpo_de_entrada(matricula=ruim))
    assert r.status_code == 422 and r.json()["erro"]["campo"] == "matricula"
    if isinstance(ruim, str) and ruim:
        assert ruim not in r.text
    assert ambiente.escalar("SELECT count(*) FROM ia.atendimento") == 0


def test_criterio_versao_sha256_com_10_digitos_seguidos_abre(ambiente):
    ambiente.ligar()
    r = ambiente.post("/atendimentos", corpo_de_entrada(criterio_versao=HASH_COM_DIGITOS))
    assert r.status_code == 201, r.text


@pytest.mark.parametrize("ruim", ["c1.0-000000" + "20100", "0123456789", "0123456789" + "ABCDEF" * 9])
def test_criterio_versao_que_nao_e_hash_segue_a_guarda_de_documento(ambiente, ruim):
    """A isenção é só para hex de 64 minúsculo: rótulo com documento, 10 dígitos soltos ou hex maiúsculo seguem 422."""
    ambiente.ligar()
    r = ambiente.post("/atendimentos", corpo_de_entrada(criterio_versao=ruim))
    assert r.status_code == 422 and r.json()["erro"]["codigo"] == "pii_no_texto_livre" and ruim not in r.text


def test_candidatos_com_criterio_sha256_gravam(ambiente):
    atd = abrir_ativo(ambiente)
    escolhido = {"chat_id": CHAT, "escolhido": True, "atendimento_id": str(atd), "posicao": 1, "perfil": {"banco": "FACTA"}}
    recusado = {"chat_id": OUTRO_CHAT, "escolhido": False, "recusa": "ja_em_atendimento", "perfil": {}}
    r = ambiente.post(f"/sessoes/{uuid.uuid4()}/candidatos", {"criterio_versao": HASH_COM_DIGITOS, "candidatos": [escolhido, recusado]})
    assert r.status_code == 201, r.text


def test_hash_real_de_um_criterio_passa():
    """Sanidade: o que o 04 manda é `sha256(...).hexdigest()`, minúsculo."""
    from ia_atendimento.api.validacao import rejeitar_documento_salvo_sha256

    rejeitar_documento_salvo_sha256("criterio_versao", hashlib.sha256(b"criterio-sintetico").hexdigest())
