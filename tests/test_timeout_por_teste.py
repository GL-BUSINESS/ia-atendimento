"""R2-07: a suíte tem timeout por teste. Dois mutantes da vigia (sem a task, sem `graceful = 0`) só morriam por TRAVAMENTO até o `timeout 600` do `check.sh`."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def test_pyproject_pina_pytest_timeout_e_configura_um_limite_por_teste():
    projeto = tomllib.loads((RAIZ / "pyproject.toml").read_text())
    assert "pytest-timeout==2.4.0" in projeto["dependency-groups"]["dev"]
    assert 0 < float(projeto["tool"]["pytest"]["ini_options"]["timeout"]) <= 300


def test_o_plugin_esta_ativo_na_execucao(pytestconfig):
    assert pytestconfig.pluginmanager.hasplugin("timeout") and float(pytestconfig.getini("timeout")) == 120


def test_um_teste_travado_falha_por_timeout_em_vez_de_travar_a_suite(tmp_path):
    """Roda um pytest de verdade com um teste que dorme 60 s e `--timeout=1`: tem de terminar REPROVADO em poucos segundos, com «Timeout»."""
    teste = tmp_path / "test_trava.py"
    teste.write_text("import time\n\ndef test_trava():\n    time.sleep(60)\n")
    r = subprocess.run(
        [sys.executable, "-I", "-m", "pytest", "-p", "no:cacheprovider", "-o", "addopts=", "--timeout=1", "--rootdir", str(tmp_path), str(teste)],
        capture_output=True, text=True, timeout=30, cwd=tmp_path, check=False,
    )  # fmt: skip
    assert r.returncode == 1 and "Timeout" in r.stdout and "1 failed" in r.stdout, r.stdout[-800:]
