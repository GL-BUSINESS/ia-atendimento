"""O portão não mente verde sobre a consistência entre os repositórios (B2.4, R1-02)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests import apoio_irmao

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "scripts" / "exigir_irmao.sh"
ARQUIVO = "personas/pessoas_teste.sha256"


def _rodar(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", **env}, check=False
    )


def test_exigir_irmao_falha_sem_a_variavel_e_diz_como_definir():
    r = _rodar({})
    assert r.returncode == 1 and "BANCOS_DUBLE_PATH não está definida" in r.stderr and "check.sh" in r.stderr


def test_exigir_irmao_falha_com_checkout_sem_a_b2_4(tmp_path):
    r = _rodar({"BANCOS_DUBLE_PATH": str(tmp_path)})
    assert r.returncode == 1 and "sem a B2.4" in r.stderr


def test_exigir_irmao_passa_com_o_checkout_certo(tmp_path):
    (tmp_path / "personas").mkdir()
    (tmp_path / ARQUIVO).write_text("abc  x\n")
    r = _rodar({"BANCOS_DUBLE_PATH": str(tmp_path)})
    assert r.returncode == 0 and "irmão achado" in r.stdout


def test_check_sh_chama_o_exigir_irmao_antes_de_tudo_e_liga_a_exigencia():
    texto = (RAIZ / "scripts" / "check.sh").read_text(encoding="utf-8")
    linhas = [linha for linha in texto.splitlines() if linha and not linha.startswith("#")]
    assert linhas.index("run bash scripts/exigir_irmao.sh") < linhas.index("run uv lock --check")
    assert "export PESSOAS_TESTE_EXIGE_IRMAO=1" in texto


def test_localizar_pula_sem_a_variavel_e_falha_quando_o_portao_exige(tmp_path, monkeypatch):
    monkeypatch.delenv("BANCOS_DUBLE_PATH", raising=False)
    monkeypatch.delenv(apoio_irmao.EXIGE, raising=False)
    with pytest.raises(pytest.skip.Exception, match="defina BANCOS_DUBLE_PATH"):
        apoio_irmao.localizar("BANCOS_DUBLE_PATH", ARQUIVO, "bancos-duble")
    monkeypatch.setenv(apoio_irmao.EXIGE, "1")
    with pytest.raises(pytest.fail.Exception, match="irmão não foi encontrado"):
        apoio_irmao.localizar("BANCOS_DUBLE_PATH", ARQUIVO, "bancos-duble")
    monkeypatch.setenv("BANCOS_DUBLE_PATH", str(tmp_path))  # variável definida mas apontando para o lugar errado: também falha
    with pytest.raises(pytest.fail.Exception, match="não tem o arquivo"):
        apoio_irmao.localizar("BANCOS_DUBLE_PATH", ARQUIVO, "bancos-duble")


def test_localizar_devolve_o_checkout_quando_acha(tmp_path, monkeypatch):
    (tmp_path / "personas").mkdir()
    (tmp_path / ARQUIVO).write_text("abc  x\n")
    monkeypatch.setenv("BANCOS_DUBLE_PATH", str(tmp_path))
    monkeypatch.setenv(apoio_irmao.EXIGE, "1")
    assert apoio_irmao.localizar("BANCOS_DUBLE_PATH", ARQUIVO, "bancos-duble") == tmp_path


def test_ci_traz_o_irmao_e_exige_a_consistencia_em_vez_de_pular():
    """R2-11: o CI rodava `pytest` puro e os testes cruzados pulavam. Agora ele faz checkout do bancos-duble, define a variável, liga a exigência e roda o `exigir_irmao.sh`."""
    ci = (RAIZ / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert 'PESSOAS_TESTE_EXIGE_IRMAO: "1"' in ci
    assert "BANCOS_DUBLE_PATH: ${{ github.workspace }}/irmao/bancos-duble" in ci
    assert "repository: GL-BUSINESS/bancos-duble" in ci and "path: irmao/bancos-duble" in ci
    assert "bash scripts/exigir_irmao.sh" in ci and "gerar_pessoas_teste.py --verificar" in ci
    assert ci.index("path: irmao/bancos-duble") < ci.index("uv run pytest"), "o irmão vem antes do pytest"
