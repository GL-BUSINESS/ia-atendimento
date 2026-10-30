"""Segredos em arquivo 0600 (P-R10): chaves HMAC do gateway e segredos de saída. Nada de valor em erro nem em `repr`."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ia_atendimento.segredos import (
    CAMPOS_DE_SAIDA,
    SegredoInvalido,
    carregar_gateway_hmac,
    carregar_segredos_de_saida,
    ler_arquivo_privado,
)

CHAVE_A = "chave-gateway-descartavel-aaaaaaaaaaaaaaaaaaaa"
CHAVE_B = "chave-gateway-descartavel-bbbbbbbbbbbbbbbbbbbb"
SAIDA = {campo: f"valor-descartavel-de-{campo}-0123456789" for campo in CAMPOS_DE_SAIDA}


def _arquivo(tmp_path: Path, conteudo: str, modo: int = 0o600, nome: str = "segredo") -> Path:
    caminho = tmp_path / nome
    caminho.write_text(conteudo, encoding="utf-8")
    caminho.chmod(modo)
    return caminho


def test_le_uma_ou_duas_chaves_ignorando_comentario_e_linha_em_branco(tmp_path):
    assert carregar_gateway_hmac(_arquivo(tmp_path, f"# gateway\n\n{CHAVE_A}\n")) == (CHAVE_A.encode(),)
    assert carregar_gateway_hmac(_arquivo(tmp_path, f"{CHAVE_A}\n{CHAVE_B}\n", nome="duas")) == (CHAVE_A.encode(), CHAVE_B.encode())


@pytest.mark.parametrize(
    "conteudo",
    [
        pytest.param("", id="vazio"),
        pytest.param("# so comentario\n", id="so-comentario"),
        pytest.param("curta\n", id="curta"),
        pytest.param(f"{CHAVE_A}\n{CHAVE_A}\n", id="repetidas"),
        pytest.param(f"{CHAVE_A}\n{CHAVE_B}\n{CHAVE_B}x\n", id="tres"),
        pytest.param("chave com espaço no meio 0123456789abcdef\n", id="espaco"),
        pytest.param("chave-não-ascii-é-0123456789abcdefghijklmnop\n", id="nao-ascii"),
    ],
)
def test_gateway_hmac_invalido_recusa_sem_citar_o_conteudo(tmp_path, conteudo):
    with pytest.raises(SegredoInvalido) as erro:
        carregar_gateway_hmac(_arquivo(tmp_path, conteudo))
    assert CHAVE_A not in str(erro.value) and "curta" not in str(erro.value)


@pytest.mark.parametrize("modo", [0o644, 0o640, 0o604, 0o660])
def test_arquivo_com_permissao_aberta_e_recusado(tmp_path, modo):
    with pytest.raises(SegredoInvalido, match="0600"):
        ler_arquivo_privado(_arquivo(tmp_path, CHAVE_A, modo))


def test_arquivo_ausente_link_simbolico_e_diretorio_sao_recusados(tmp_path):
    with pytest.raises(SegredoInvalido):
        ler_arquivo_privado(tmp_path / "nao-existe")
    alvo = _arquivo(tmp_path, CHAVE_A, nome="alvo")
    elo = tmp_path / "elo"
    os.symlink(alvo, elo)
    with pytest.raises(SegredoInvalido):
        ler_arquivo_privado(elo)
    with pytest.raises(SegredoInvalido):
        ler_arquivo_privado(tmp_path)


def test_segredos_de_saida_ok_e_repr_nao_mostra_nada(tmp_path):
    segredos = carregar_segredos_de_saida(_arquivo(tmp_path, json.dumps(SAIDA)))
    assert segredos.c360_client_secret == SAIDA["c360_client_secret"]
    assert not any(valor in repr(segredos) or valor in str(segredos) for valor in SAIDA.values())


@pytest.mark.parametrize(
    "dados",
    [
        pytest.param({k: v for k, v in SAIDA.items() if k != "chatguru_token_ia"}, id="falta-campo"),
        pytest.param({**SAIDA, "extra": "valor-descartavel-extra-0123456789"}, id="campo-a-mais"),
        pytest.param({**SAIDA, "c360_client_id": "curto"}, id="curto"),
        pytest.param({**SAIDA, "c360_client_id": 12345678901234567}, id="nao-texto"),
        pytest.param({**SAIDA, "c360_client_id": " espaco-nas-pontas-0123456789 "}, id="espaco-nas-pontas"),
        pytest.param(["lista"], id="nao-objeto"),
    ],
)
def test_segredos_de_saida_invalidos_recusam_sem_citar_valor(tmp_path, dados):
    with pytest.raises(SegredoInvalido) as erro:
        carregar_segredos_de_saida(_arquivo(tmp_path, json.dumps(dados)))
    assert not any(str(v) in str(erro.value) for v in SAIDA.values())


def test_segredos_de_saida_que_nao_e_json_recusa(tmp_path):
    with pytest.raises(SegredoInvalido, match="JSON"):
        carregar_segredos_de_saida(_arquivo(tmp_path, "isto nao e json"))


def test_fifo_no_caminho_do_segredo_e_recusado_sem_travar_a_subida(tmp_path):
    """R2-09: `open` sem `O_NONBLOCK` num FIFO sem escritor trava para sempre. O teste roda numa thread com prazo para não pendurar a suíte numa regressão."""
    import threading

    fifo = tmp_path / "segredo.fifo"
    os.mkfifo(fifo, 0o600)
    resultado: list[object] = []

    def tentar() -> None:
        try:
            ler_arquivo_privado(fifo)
        except SegredoInvalido as erro:
            resultado.append(erro)

    fio = threading.Thread(target=tentar, daemon=True)
    fio.start()
    fio.join(5)
    assert not fio.is_alive(), "o FIFO travou a leitura do segredo"
    assert len(resultado) == 1 and "comum" in str(resultado[0])


def test_json_profundo_demais_nos_segredos_de_saida_e_segredo_invalido_e_nao_recursion_error(tmp_path):
    with pytest.raises(SegredoInvalido, match="JSON"):
        carregar_segredos_de_saida(_arquivo(tmp_path, "[" * 100_000))
    with pytest.raises(SegredoInvalido):
        carregar_segredos_de_saida(_arquivo(tmp_path, '{"a":' * 100_000, nome="obj"))
