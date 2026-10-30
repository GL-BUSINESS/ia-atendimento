from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def test_repositorio_sem_segredo_cpf_ou_email_reais():
    resultado = subprocess.run(
        [sys.executable, "-I", str(RAIZ / "scripts" / "varredura.py")], cwd=RAIZ, capture_output=True, text=True, check=False
    )
    assert resultado.returncode == 0, resultado.stderr


def test_varredura_acusa_o_que_deve(tmp_path, monkeypatch):
    """Reprova sem a mudança: a varredura de verdade enxerga segredo, CPF válido e e-mail real."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("varredura", RAIZ / "scripts" / "varredura.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    monkeypatch.setattr(modulo, "RAIZ", tmp_path)
    ruim = tmp_path / "ruim.txt"
    # montado em pedaços: o próprio arquivo de teste não pode parecer segredo, CPF ou e-mail real para a varredura
    segredo = "fw" + "_" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123"
    cpf = "390.533" + ".447-05"
    email = "pessoa.real" + "@empresa" + ".com.br"
    token = "tok" + "en = 'abcdefghijklmnop1234'"
    ruim.write_text(f"a = '{segredo}'\ncpf {cpf}\ncontato {email}\n{token}\n", encoding="utf-8")
    achados = modulo.varrer(ruim)
    assert len(achados) == 4, achados
    bom = tmp_path / "bom.txt"
    bom.write_text("cpf 529.982.247-25 danilo@exemplo.test postgresql://u:p@127.0.0.1/db\n", encoding="utf-8")
    assert modulo.varrer(bom) == []
