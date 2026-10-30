from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ia_atendimento.cifra import (
    ChaveDesconhecida,
    ChaveInsegura,
    Chaveiro,
    FalhaAoDecifrar,
    montar_aad,
)

ATD = "01a18a0a-6522-722b-8bf2-cced4767f1aa"
OUTRO_ATD = "01a18a0a-6522-722b-8bf2-cced4767f1ab"
TEXTO = "meu CPF é [CPF] e quero [NUMERO] em 24x"  # sintético, já mascarado


def _b64(n: int = 32) -> str:
    return base64.b64encode(os.urandom(n)).decode()


def _arquivo(tmp_path: Path, chaves: dict[int, str], modo: int = 0o600) -> Path:
    caminho = tmp_path / "chaves.json"
    caminho.write_text(json.dumps({str(k): v for k, v in chaves.items()}), encoding="utf-8")
    caminho.chmod(modo)
    return caminho


@pytest.fixture
def chaveiro(tmp_path) -> Chaveiro:
    return Chaveiro.de_arquivo(_arquivo(tmp_path, {1: _b64(), 2: _b64()}), vigente=2)


def test_roundtrip_devolve_o_texto_original(chaveiro):
    chave_id, nonce, ct = chaveiro.cifrar(TEXTO, ATD)
    assert chave_id == 2 and len(nonce) == 12
    assert chaveiro.decifrar(chave_id, nonce, ct, ATD) == TEXTO


def test_resultado_e_tupla_chave_id_nonce_ct(chaveiro):
    chave_id, nonce, ct = resultado = chaveiro.cifrar(TEXTO, ATD)
    assert isinstance(resultado, tuple) and (chave_id, nonce, ct) == tuple(resultado)


def test_ct_nao_contem_o_texto_e_leva_tag_gcm_de_16_bytes(chaveiro):
    _, _, ct = chaveiro.cifrar(TEXTO, ATD)
    assert TEXTO.encode() not in ct and b"CPF" not in ct
    assert len(ct) == len(TEXTO.encode()) + 16


def test_nonce_nunca_repete_e_ct_difere_para_o_mesmo_texto(chaveiro):
    saidas = [chaveiro.cifrar(TEXTO, ATD) for _ in range(200)]
    assert len({s.nonce for s in saidas}) == 200
    assert len({s.ct for s in saidas}) == 200


def test_aad_errado_nao_decifra(chaveiro):
    chave_id, nonce, ct = chaveiro.cifrar(TEXTO, ATD)
    with pytest.raises(FalhaAoDecifrar):
        chaveiro.decifrar(chave_id, nonce, ct, OUTRO_ATD)


def test_uuid_e_str_dao_o_mesmo_aad(chaveiro):
    chave_id, nonce, ct = chaveiro.cifrar(TEXTO, uuid.UUID(ATD))
    assert chaveiro.decifrar(chave_id, nonce, ct, ATD.upper()) == TEXTO


def test_aad_completo_do_estudo_i_amarra_seq_remetente_tipo_e_chave(chaveiro):
    ctx = {"seq": 3, "remetente": "cliente", "tipo": "mensagem"}
    chave_id, nonce, ct = chaveiro.cifrar(TEXTO, ATD, **ctx)
    assert chaveiro.decifrar(chave_id, nonce, ct, ATD, **ctx) == TEXTO
    for troca in ({"seq": 4}, {"remetente": "ia"}, {"tipo": "resumo"}):
        with pytest.raises(FalhaAoDecifrar):
            chaveiro.decifrar(chave_id, nonce, ct, ATD, **{**ctx, **troca})
    with pytest.raises(FalhaAoDecifrar):  # forma simples (só atendimento_id) não decifra a forma completa
        chaveiro.decifrar(chave_id, nonce, ct, ATD)


def test_aad_completo_exige_os_tres_campos(chaveiro):
    with pytest.raises(ValueError):
        chaveiro.cifrar(TEXTO, ATD, seq=1)


def test_montar_aad_forma_simples_e_o_atendimento_id():
    assert montar_aad(ATD, chave_id=7) == ATD.encode()
    assert montar_aad(ATD, chave_id=7, seq=1, remetente="cliente", tipo="mensagem") == f"{ATD}|1|cliente|mensagem|7".encode()


def test_chave_id_desconhecido_falha(chaveiro):
    _, nonce, ct = chaveiro.cifrar(TEXTO, ATD)
    with pytest.raises(ChaveDesconhecida) as erro:
        chaveiro.decifrar(99, nonce, ct, ATD)
    assert "99" in str(erro.value)


def test_chave_descartada_deixa_o_texto_ilegivel(tmp_path):
    arquivo = _arquivo(tmp_path, {1: _b64(), 2: _b64()})
    antigo = Chaveiro.de_arquivo(arquivo, vigente=1)
    chave_id, nonce, ct = antigo.cifrar(TEXTO, ATD)
    arquivo.write_text(json.dumps({"2": json.loads(arquivo.read_text())["2"]}), encoding="utf-8")  # dia 31: descarta a chave 1
    novo = Chaveiro.de_arquivo(arquivo, vigente=2)
    with pytest.raises(ChaveDesconhecida):
        novo.decifrar(chave_id, nonce, ct, ATD)


def test_ct_adulterado_ou_truncado_nao_decifra(chaveiro):
    chave_id, nonce, ct = chaveiro.cifrar(TEXTO, ATD)
    adulterado = bytes([ct[0] ^ 1]) + ct[1:]
    for ruim_nonce, ruim_ct in ((nonce, adulterado), (nonce, ct[:-1]), (nonce, ct[:5]), (os.urandom(12), ct)):
        with pytest.raises(FalhaAoDecifrar):
            chaveiro.decifrar(chave_id, ruim_nonce, ruim_ct, ATD)


def test_nonce_de_tamanho_errado_falha_sem_vazar(chaveiro):
    chave_id, _, ct = chaveiro.cifrar(TEXTO, ATD)
    with pytest.raises(FalhaAoDecifrar):
        chaveiro.decifrar(chave_id, b"curto", ct, ATD)


def test_texto_vazio_ou_grande_demais_recusado(chaveiro):
    with pytest.raises(ValueError):
        chaveiro.cifrar("", ATD)
    with pytest.raises(ValueError):
        chaveiro.cifrar("x" * 20_000, ATD)  # a coluna `cifra` aceita 17..20000 bytes (texto + tag de 16)
    chave_id, nonce, ct = chaveiro.cifrar("x" * 19_984, ATD)
    assert len(ct) == 20_000 and chaveiro.decifrar(chave_id, nonce, ct, ATD) == "x" * 19_984


def test_atendimento_id_invalido_recusado(chaveiro):
    with pytest.raises(ValueError):
        chaveiro.cifrar(TEXTO, "nao-e-uuid")


def test_interoperavel_com_aesgcm_puro(tmp_path):
    """O formato é AES-256-GCM padrão: nonce de 12 bytes, ct = texto + tag; quem tem a chave decifra sem a nossa classe."""
    chave = os.urandom(32)
    arquivo = _arquivo(tmp_path, {5: base64.b64encode(chave).decode()})
    c = Chaveiro.de_arquivo(arquivo, vigente=5)
    chave_id, nonce, ct = c.cifrar(TEXTO, ATD)
    assert AESGCM(chave).decrypt(nonce, ct, ATD.encode()).decode() == TEXTO
    assert chave_id == 5


# --- arquivo de chaves -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("modo", [0o644, 0o640, 0o604, 0o660, 0o666, 0o700 | 0o077])
def test_arquivo_com_permissao_aberta_e_recusado(tmp_path, modo):
    with pytest.raises(ChaveInsegura) as erro:
        Chaveiro.de_arquivo(_arquivo(tmp_path, {1: _b64()}, modo=modo), vigente=1)
    assert "0600" in str(erro.value)


@pytest.mark.parametrize("modo", [0o600, 0o400])
def test_arquivo_0600_ou_0400_aceito(tmp_path, modo):
    assert Chaveiro.de_arquivo(_arquivo(tmp_path, {1: _b64()}, modo=modo), vigente=1).ids == (1,)


def test_symlink_para_arquivo_de_chaves_e_recusado(tmp_path):
    real = _arquivo(tmp_path, {1: _b64()})
    link = tmp_path / "link.json"
    link.symlink_to(real)
    with pytest.raises(ChaveInsegura):
        Chaveiro.de_arquivo(link, vigente=1)


def test_arquivo_ausente_e_recusado(tmp_path):
    with pytest.raises(ChaveInsegura):
        Chaveiro.de_arquivo(tmp_path / "nao-existe.json", vigente=1)


@pytest.mark.parametrize("tamanho", [16, 24, 31, 33, 64])
def test_chave_que_nao_tem_32_bytes_e_recusada(tmp_path, tamanho):
    with pytest.raises(ChaveInsegura) as erro:
        Chaveiro.de_arquivo(_arquivo(tmp_path, {1: _b64(tamanho)}), vigente=1)
    assert "32 bytes" in str(erro.value)


def test_vigente_ausente_do_arquivo_e_recusada(tmp_path):
    with pytest.raises(ChaveInsegura):
        Chaveiro.de_arquivo(_arquivo(tmp_path, {1: _b64()}), vigente=2)


@pytest.mark.parametrize(
    "conteudo", ["", "isto não é json", "[]", '{"1": 123}', '{"um": "AAAA"}', '{"0": "AAAA"}', '{"40000": "AAAA"}', "{}"]
)
def test_conteudo_invalido_do_arquivo_e_recusado(tmp_path, conteudo):
    caminho = tmp_path / "chaves.json"
    caminho.write_text(conteudo, encoding="utf-8")
    caminho.chmod(0o600)
    with pytest.raises(ChaveInsegura):
        Chaveiro.de_arquivo(caminho, vigente=1)


def test_base64_invalido_e_recusado(tmp_path):
    with pytest.raises(ChaveInsegura):
        Chaveiro.de_arquivo(_arquivo(tmp_path, {1: "isto não é base64!!"}), vigente=1)


# --- nada de segredo em log, repr ou erro ---------------------------------------------------------------------------------


def test_repr_do_chaveiro_nao_mostra_chave(tmp_path):
    chave = _b64()
    c = Chaveiro.de_arquivo(_arquivo(tmp_path, {1: chave}), vigente=1)
    assert chave not in repr(c) and chave not in str(c)
    assert "vigente=1" in repr(c)


def test_erros_nao_carregam_texto_nem_chave(tmp_path, chaveiro):
    chave = _b64(16)
    with pytest.raises(ChaveInsegura) as e1:
        Chaveiro.de_arquivo(_arquivo(tmp_path, {1: chave}), vigente=1)
    assert chave not in str(e1.value) and chave not in repr(e1.value)
    chave_id, nonce, ct = chaveiro.cifrar(TEXTO, ATD)
    with pytest.raises(FalhaAoDecifrar) as e2:
        chaveiro.decifrar(chave_id, nonce, ct, OUTRO_ATD)
    for saida in (str(e2.value), repr(e2.value), repr(e2.value.args)):
        assert "CPF" not in saida and TEXTO not in saida and ct.hex() not in saida


def test_nenhum_texto_vai_para_o_log_nem_para_a_tela(chaveiro, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    chave_id, nonce, ct = chaveiro.cifrar(TEXTO, ATD, seq=1, remetente="cliente", tipo="mensagem")
    chaveiro.decifrar(chave_id, nonce, ct, ATD, seq=1, remetente="cliente", tipo="mensagem")
    with pytest.raises(FalhaAoDecifrar):
        chaveiro.decifrar(chave_id, nonce, ct, ATD)
    with pytest.raises(ChaveDesconhecida):
        chaveiro.decifrar(99, nonce, ct, ATD)
    visto = capsys.readouterr()
    tudo = caplog.text + visto.out + visto.err
    assert "CPF" not in tudo and "24x" not in tudo and nonce.hex() not in tudo and ct.hex() not in tudo


def test_funcoes_de_modulo_usam_o_chaveiro_padrao(tmp_path, monkeypatch):
    from ia_atendimento import cifra
    from ia_atendimento.config import get_settings

    arquivo = _arquivo(tmp_path, {4: _b64()})
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@127.0.0.1/db")
    monkeypatch.setenv("MODELO_API_KEY_1", "k")
    monkeypatch.setenv("API_TOKEN", "t")
    monkeypatch.setenv("CHAVE_AES_ID", "4")
    monkeypatch.setenv("CHAVE_AES_ARQUIVO", str(arquivo))
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    cifra.chaveiro_padrao.cache_clear()
    try:
        chave_id, nonce, ct = cifra.cifrar(TEXTO, ATD)
        assert chave_id == 4 and cifra.decifrar(chave_id, nonce, ct, ATD) == TEXTO
    finally:
        get_settings.cache_clear()
        cifra.chaveiro_padrao.cache_clear()
