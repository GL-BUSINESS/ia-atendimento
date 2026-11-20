"""G-0097 (revisão 0911): a regra de permissão dos arquivos de segredo é UMA e a mensagem de erro a diz inteira.

O contêiner roda como uid 10001 com `cap_drop: ALL`: só sobe arquivo 0600 cujo DONO é o usuário do processo. 0640 (o que o DEPLOY.md da
esteira mandava) é recusado; 0600 de outro dono (root:root) nem abre. A mensagem tem de levar o operador à regra (modo e dono), sem o
conteúdo. A documentação está em `docs/OPERACAO.md` §2 e §8.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ia_atendimento.cifra import ChaveInsegura, Chaveiro
from ia_atendimento.segredos import SegredoInvalido, ler_arquivo_privado

OPERACAO = Path(__file__).resolve().parent.parent / "docs" / "OPERACAO.md"


def _arquivo(tmp_path: Path, modo: int) -> Path:
    caminho = tmp_path / "segredo"
    caminho.write_text('{"1": "AAAA"}')
    caminho.chmod(modo)
    return caminho


@pytest.mark.parametrize("modo", [0o640, 0o604, 0o644])
def test_modo_com_bit_de_grupo_ou_outros_e_recusado_e_a_mensagem_diz_modo_e_dono(tmp_path, modo):
    caminho = _arquivo(tmp_path, modo)
    for ler, erro in ((ler_arquivo_privado, SegredoInvalido), (lambda c: Chaveiro.de_arquivo(c, 1), ChaveInsegura)):
        with pytest.raises(erro) as achado:
            ler(caminho)
        assert "0600" in str(achado.value) and f"uid {os.geteuid()}" in str(achado.value) and "AAAA" not in str(achado.value)


@pytest.mark.skipif(os.geteuid() == 0, reason="root lê o arquivo 000")
def test_arquivo_que_o_processo_nao_le_diz_a_regra_do_dono(tmp_path):
    caminho = _arquivo(tmp_path, 0o000)
    for ler, erro in ((ler_arquivo_privado, SegredoInvalido), (lambda c: Chaveiro.de_arquivo(c, 1), ChaveInsegura)):
        with pytest.raises(erro) as achado:
            ler(caminho)
        assert f"uid {os.geteuid()}" in str(achado.value) and "0600" in str(achado.value)


def test_operacao_documenta_dono_modo_e_montagem():
    texto = OPERACAO.read_text(encoding="utf-8")
    assert "chown 10001:10001" in texto and "chmod 600" in texto and "/etc/ia-s4:/etc/ia-s4:ro" in texto
    assert "640" not in texto.replace("0640 é recusado", "")
