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


# --- revisão 29/10: o que a varredura deixava passar ------------------------------------------------------------------------------


def _modulo(monkeypatch, raiz: Path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("varredura_rev", RAIZ / "scripts" / "varredura.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    monkeypatch.setattr(modulo, "RAIZ", raiz)
    return modulo


def test_palavra_exemplo_solta_na_linha_nao_isenta_um_segredo_de_verdade(tmp_path, monkeypatch):
    modulo = _modulo(monkeypatch, tmp_path)
    ruim = tmp_path / "ruim.txt"
    segredo = "sk" + "-" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123"
    ruim.write_text(f"chave = '{segredo}'  # exemplo\n", encoding="utf-8")
    assert len(modulo.varrer(ruim)) == 1
    ok = tmp_path / "ok.txt"
    ok.write_text(f"chave = 'sk-exemplo{segredo[3:]}'\n", encoding="utf-8")  # o TRECHO casado é marcado como exemplo
    assert modulo.varrer(ok) == []


def test_credencial_em_url_de_host_real_e_acusada_e_a_de_teste_nao(tmp_path, monkeypatch):
    modulo = _modulo(monkeypatch, tmp_path)
    ruim = tmp_path / "ruim.txt"
    ruim.write_text("DATABASE_URL=postgresql://ia_app_a:" + "S3nh4Real" + "@db-prod.empresa.net:5434/x\n", encoding="utf-8")
    assert any("credencial em URL" in achado for achado in modulo.varrer(ruim))
    ok = tmp_path / "ok.txt"
    ok.write_text(
        "a postgresql://u:senha@127.0.0.1/x b postgres://u:senha@db.exemplo.test/x c mysql://u:senha@203.0.113.4/x d https://u:p@h/x\n"
    )
    assert modulo.varrer(ok) == []


def test_celular_brasileiro_real_e_acusado_e_o_sintetico_nao(tmp_path, monkeypatch):
    modulo = _modulo(monkeypatch, tmp_path)
    ruim = tmp_path / "ruim.txt"
    ruim.write_text("liga (11) " + "97531-2468" + " ou +55 21 " + "98642-1357" + "\n", encoding="utf-8")
    assert len(modulo.varrer(ruim)) == 2
    ok = tmp_path / "ok.txt"
    ok.write_text("tel (11) 91234-5678, +55 11 91234-5678, 11912345678 e o CPF 52998224725\n", encoding="utf-8")
    assert modulo.varrer(ok) == []


def test_arquivo_novo_ainda_sem_git_add_tambem_e_varrido(tmp_path, monkeypatch, capsys):
    """O portão roda ANTES do commit: `git ls-files` sozinho nunca via o arquivo recém-criado."""
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text("ignorado.txt\n", encoding="utf-8")
    cpf = "390.533" + ".447-05"
    (tmp_path / "novo.txt").write_text(f"cpf {cpf}\n", encoding="utf-8")
    (tmp_path / "ignorado.txt").write_text(f"cpf {cpf}\n", encoding="utf-8")
    modulo = _modulo(monkeypatch, tmp_path)
    assert modulo.main() == 1
    erro = capsys.readouterr().err
    assert "novo.txt" in erro and "ignorado.txt" not in erro
