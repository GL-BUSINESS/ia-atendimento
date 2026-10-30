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
CTX = {"seq": 1, "remetente": "cliente", "tipo": "mensagem"}  # a AAD do esquema é sempre completa (estudo I §1.6, B1.2)


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
    chave_id, nonce, ct = chaveiro.cifrar(TEXTO, ATD, **CTX)
    assert chave_id == 2 and len(nonce) == 12
    assert chaveiro.decifrar(chave_id, nonce, ct, ATD, **CTX) == TEXTO


def test_resultado_e_tupla_chave_id_nonce_ct(chaveiro):
    chave_id, nonce, ct = resultado = chaveiro.cifrar(TEXTO, ATD, **CTX)
    assert isinstance(resultado, tuple) and (chave_id, nonce, ct) == tuple(resultado)


def test_ct_nao_contem_o_texto_e_leva_tag_gcm_de_16_bytes(chaveiro):
    _, _, ct = chaveiro.cifrar(TEXTO, ATD, **CTX)
    assert TEXTO.encode() not in ct and b"CPF" not in ct
    assert len(ct) == len(TEXTO.encode()) + 16


def test_nonce_nunca_repete_e_ct_difere_para_o_mesmo_texto(chaveiro):
    saidas = [chaveiro.cifrar(TEXTO, ATD, **CTX) for _ in range(200)]
    assert len({s.nonce for s in saidas}) == 200
    assert len({s.ct for s in saidas}) == 200


def test_aad_errado_nao_decifra(chaveiro):
    chave_id, nonce, ct = chaveiro.cifrar(TEXTO, ATD, **CTX)
    with pytest.raises(FalhaAoDecifrar):
        chaveiro.decifrar(chave_id, nonce, ct, OUTRO_ATD, **CTX)


def test_uuid_e_str_dao_o_mesmo_aad(chaveiro):
    chave_id, nonce, ct = chaveiro.cifrar(TEXTO, uuid.UUID(ATD), **CTX)
    assert chaveiro.decifrar(chave_id, nonce, ct, ATD.upper(), **CTX) == TEXTO


def test_aad_completo_do_estudo_i_amarra_seq_remetente_tipo_e_chave(chaveiro):
    ctx = {"seq": 3, "remetente": "cliente", "tipo": "mensagem"}
    chave_id, nonce, ct = chaveiro.cifrar(TEXTO, ATD, **ctx)
    assert chaveiro.decifrar(chave_id, nonce, ct, ATD, **ctx) == TEXTO
    for troca in ({"seq": 4}, {"remetente": "ia"}, {"tipo": "resumo"}):
        with pytest.raises(FalhaAoDecifrar):
            chaveiro.decifrar(chave_id, nonce, ct, ATD, **{**ctx, **troca})


def test_montar_aad_e_a_do_estudo_i():
    """`atendimento_id|seq|remetente|tipo|chave_id` (I §1.6; o `i-teste-0001.sh` cifra com `{atd}|1|cliente|mensagem|1`)."""
    assert montar_aad(ATD, chave_id=7, seq=1, remetente="cliente", tipo="mensagem") == f"{ATD}|1|cliente|mensagem|7".encode()
    assert montar_aad(ATD, chave_id=7, seq=0, remetente="cofre", tipo="digitacao") == f"{ATD}|0|cofre|digitacao|7".encode()


# --- revisão 29/10: a forma «simples» da AAD (só atendimento_id) não existe mais ------------------------------------------------


def test_cifrar_sem_contexto_e_erro_nao_cai_em_aad_fraca(chaveiro):
    """Antes, `cifrar(texto, atd)` valia e amarrava só ao atendimento: a linha podia ser movida de seq/remetente/tipo."""
    with pytest.raises(TypeError):
        chaveiro.cifrar(TEXTO, ATD)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        chaveiro.cifrar(TEXTO, ATD, seq=1)  # type: ignore[call-arg]
    chave_id, nonce, ct = chaveiro.cifrar(TEXTO, ATD, **CTX)
    with pytest.raises(TypeError):
        chaveiro.decifrar(chave_id, nonce, ct, ATD)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "ruim",
    [
        {"seq": 0},  # seq >= 1 no esquema (CHECK conversa_cifrada_forma_check); 0 é do cofre
        {"seq": -1},
        {"seq": True},
        {"seq": "1"},
        {"remetente": "consultor"},
        {"remetente": "cliente|ia"},
        {"remetente": "cofre"},
        {"tipo": "resumo|x"},
        {"tipo": "digitacao"},
        {"tipo": ""},
    ],
)
def test_contexto_fora_do_dominio_do_esquema_e_recusado(chaveiro, ruim):
    with pytest.raises(ValueError):
        chaveiro.cifrar(TEXTO, ATD, **{**CTX, **ruim})


def test_separador_na_aad_nao_cria_colisao_entre_contextos():
    """`a|b`+`c` e `a`+`b|c` davam a mesma AAD; o domínio fechado impede o separador de entrar."""
    with pytest.raises(ValueError):
        montar_aad(ATD, chave_id=1, seq=1, remetente="a|b", tipo="c")
    with pytest.raises(ValueError):
        montar_aad(ATD, chave_id=1, seq=1, remetente="a", tipo="b|c")


def test_cofre_tem_aad_propria_com_seq_zero_e_remetente_cofre(chaveiro):
    chave_id, nonce, ct = chaveiro.cifrar_cofre(TEXTO, ATD, "digitacao")
    assert chaveiro.decifrar_cofre(chave_id, nonce, ct, ATD, "digitacao") == TEXTO
    with pytest.raises(FalhaAoDecifrar):  # outra finalidade
        chaveiro.decifrar_cofre(chave_id, nonce, ct, ATD, "canal")
    with pytest.raises(FalhaAoDecifrar):  # linha do cofre não passa por mensagem da conversa
        chaveiro.decifrar(chave_id, nonce, ct, ATD, **CTX)
    with pytest.raises(ValueError):
        chaveiro.cifrar_cofre(TEXTO, ATD, "outra")


def test_cofre_e_aes_gcm_padrao_com_a_aad_do_plano_01(tmp_path):
    """sp01: cofre = `atendimento_id|0|cofre|finalidade|chave_id`."""
    chave = os.urandom(32)
    c = Chaveiro({9: chave}, vigente=9)
    chave_id, nonce, ct = c.cifrar_cofre(TEXTO, ATD, "canal")
    assert AESGCM(chave).decrypt(nonce, ct, f"{ATD}|0|cofre|canal|9".encode()).decode() == TEXTO
    assert chave_id == 9


def test_chave_id_desconhecido_falha(chaveiro):
    _, nonce, ct = chaveiro.cifrar(TEXTO, ATD, **CTX)
    with pytest.raises(ChaveDesconhecida) as erro:
        chaveiro.decifrar(99, nonce, ct, ATD, **CTX)
    assert "99" in str(erro.value)


def test_chave_descartada_deixa_o_texto_ilegivel(tmp_path):
    arquivo = _arquivo(tmp_path, {1: _b64(), 2: _b64()})
    antigo = Chaveiro.de_arquivo(arquivo, vigente=1)
    chave_id, nonce, ct = antigo.cifrar(TEXTO, ATD, **CTX)
    arquivo.write_text(json.dumps({"2": json.loads(arquivo.read_text())["2"]}), encoding="utf-8")  # dia 31: descarta a chave 1
    novo = Chaveiro.de_arquivo(arquivo, vigente=2)
    with pytest.raises(ChaveDesconhecida):
        novo.decifrar(chave_id, nonce, ct, ATD, **CTX)


def test_ct_adulterado_ou_truncado_nao_decifra(chaveiro):
    chave_id, nonce, ct = chaveiro.cifrar(TEXTO, ATD, **CTX)
    adulterado = bytes([ct[0] ^ 1]) + ct[1:]
    for ruim_nonce, ruim_ct in ((nonce, adulterado), (nonce, ct[:-1]), (nonce, ct[:5]), (os.urandom(12), ct)):
        with pytest.raises(FalhaAoDecifrar):
            chaveiro.decifrar(chave_id, ruim_nonce, ruim_ct, ATD, **CTX)


def test_nonce_de_tamanho_errado_falha_sem_vazar(chaveiro):
    chave_id, _, ct = chaveiro.cifrar(TEXTO, ATD, **CTX)
    with pytest.raises(FalhaAoDecifrar):
        chaveiro.decifrar(chave_id, b"curto", ct, ATD, **CTX)


def test_texto_vazio_ou_grande_demais_recusado(chaveiro):
    with pytest.raises(ValueError):
        chaveiro.cifrar("", ATD, **CTX)
    with pytest.raises(ValueError):
        chaveiro.cifrar("x" * 20_000, ATD, **CTX)  # a coluna `cifra` aceita 17..20000 bytes (texto + tag de 16)
    chave_id, nonce, ct = chaveiro.cifrar("x" * 19_984, ATD, **CTX)
    assert len(ct) == 20_000 and chaveiro.decifrar(chave_id, nonce, ct, ATD, **CTX) == "x" * 19_984


def test_atendimento_id_invalido_recusado(chaveiro):
    with pytest.raises(ValueError):
        chaveiro.cifrar(TEXTO, "nao-e-uuid", **CTX)


def test_interoperavel_com_aesgcm_puro(tmp_path):
    """O formato é AES-256-GCM padrão: nonce de 12 bytes, ct = texto + tag; quem tem a chave decifra sem a nossa classe."""
    chave = os.urandom(32)
    arquivo = _arquivo(tmp_path, {5: base64.b64encode(chave).decode()})
    c = Chaveiro.de_arquivo(arquivo, vigente=5)
    chave_id, nonce, ct = c.cifrar(TEXTO, ATD, **CTX)
    assert AESGCM(chave).decrypt(nonce, ct, f"{ATD}|1|cliente|mensagem|5".encode()).decode() == TEXTO
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
    chave_id, nonce, ct = chaveiro.cifrar(TEXTO, ATD, **CTX)
    with pytest.raises(FalhaAoDecifrar) as e2:
        chaveiro.decifrar(chave_id, nonce, ct, OUTRO_ATD, **CTX)
    for saida in (str(e2.value), repr(e2.value), repr(e2.value.args)):
        assert "CPF" not in saida and TEXTO not in saida and ct.hex() not in saida


def test_nenhum_texto_vai_para_o_log_nem_para_a_tela(chaveiro, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    chave_id, nonce, ct = chaveiro.cifrar(TEXTO, ATD, seq=1, remetente="cliente", tipo="mensagem")
    chaveiro.decifrar(chave_id, nonce, ct, ATD, seq=1, remetente="cliente", tipo="mensagem")
    with pytest.raises(FalhaAoDecifrar):
        chaveiro.decifrar(chave_id, nonce, ct, ATD, **{**CTX, "seq": 2})
    with pytest.raises(ChaveDesconhecida):
        chaveiro.decifrar(99, nonce, ct, ATD, **CTX)
    visto = capsys.readouterr()
    tudo = caplog.text + visto.out + visto.err
    assert "CPF" not in tudo and "24x" not in tudo and nonce.hex() not in tudo and ct.hex() not in tudo


def test_funcoes_de_modulo_usam_o_chaveiro_padrao(tmp_path, monkeypatch):
    from ia_atendimento import cifra
    from ia_atendimento.config import get_settings

    arquivo = _arquivo(tmp_path, {4: _b64()})
    monkeypatch.setenv("DATABASE_URL", "postgresql://ia_app_a:y@127.0.0.1/db")
    monkeypatch.setenv("MODELO_API_KEY_1", "k" * 24)
    monkeypatch.setenv("API_TOKEN", "t" * 24)
    monkeypatch.setenv("CHAVE_H16", "h" * 32)
    monkeypatch.setenv("CHAVE_FINGERPRINT", "f" * 32)
    monkeypatch.setenv("CHAVE_AES_ID", "4")
    monkeypatch.setenv("CHAVE_AES_ARQUIVO", str(arquivo))
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    cifra.chaveiro_padrao.cache_clear()
    try:
        chave_id, nonce, ct = cifra.cifrar(TEXTO, ATD, **CTX)
        assert chave_id == 4 and cifra.decifrar(chave_id, nonce, ct, ATD, **CTX) == TEXTO
    finally:
        get_settings.cache_clear()
        cifra.chaveiro_padrao.cache_clear()


# --- revisão 29/10: rótulos de chave, repr e exceções ------------------------------------------------------------------------------


def _bruto(tmp_path: Path, conteudo: str) -> Path:
    caminho = tmp_path / "chaves.json"
    caminho.write_text(conteudo, encoding="utf-8")
    caminho.chmod(0o600)
    return caminho


@pytest.mark.parametrize("rotulo", ["١", "²", "01", "+1", "1_0", " 1", "1 ", "１"])
def test_rotulo_de_chave_so_aceita_inteiro_ascii_canonico(tmp_path, rotulo):
    """`"١".isdigit()` é verdadeiro e `int("١")` vale 1; `"²"` estourava ValueError cru; `"01"` e `"1"` colidiam em silêncio."""
    with pytest.raises(ChaveInsegura):
        Chaveiro.de_arquivo(_bruto(tmp_path, json.dumps({rotulo: _b64()})), vigente=1)


def test_chave_repetida_no_arquivo_e_recusada(tmp_path):
    outra = _b64()
    with pytest.raises(ChaveInsegura):  # JSON com a mesma chave_id duas vezes: o parser comum fica com a última, em silêncio
        Chaveiro.de_arquivo(_bruto(tmp_path, f'{{"1": "{_b64()}", "1": "{outra}"}}'), vigente=1)
    mesma = _b64()
    with pytest.raises(ChaveInsegura):  # mesma chave em dois meses: o descarte mensal não descartaria nada
        Chaveiro.de_arquivo(_bruto(tmp_path, json.dumps({"1": mesma, "2": mesma})), vigente=2)


def test_chave_toda_zero_e_recusada(tmp_path):
    with pytest.raises(ChaveInsegura):
        Chaveiro.de_arquivo(_bruto(tmp_path, json.dumps({"1": base64.b64encode(bytes(32)).decode()})), vigente=1)


def test_repr_do_resultado_nao_mostra_nonce_nem_texto_cifrado(chaveiro):
    resultado = chaveiro.cifrar(TEXTO, ATD, **CTX)
    for saida in (repr(resultado), str(resultado)):
        assert resultado.nonce.hex() not in saida and repr(resultado.nonce) not in saida and repr(resultado.ct) not in saida
        assert "chave_id" in saida
    assert tuple(resultado) == (resultado.chave_id, resultado.nonce, resultado.ct)  # continua desempacotável


def test_texto_com_surrogate_solto_nao_vaza_o_caractere_na_excecao(chaveiro):
    with pytest.raises(ValueError) as erro:
        chaveiro.cifrar("a\ud800b", ATD, **CTX)
    assert "ud800" not in str(erro.value) and "surrogate" not in str(erro.value)
