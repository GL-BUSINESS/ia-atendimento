"""O portão não mente verde sobre segredos (RG-119) e o passo do sha256 do CI não tem o caminho dobrado (RG-128)."""

from __future__ import annotations

import os
import re
import subprocess
import tomllib
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "scripts" / "gitleaks.sh"


def _cfg() -> dict:
    return tomllib.loads((RAIZ / ".gitleaks.toml").read_text(encoding="utf-8"))


def _rodar(env_extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PATH": "/usr/bin:/bin", **env_extra}
    return subprocess.run(["bash", str(SCRIPT)], cwd=RAIZ, env=env, capture_output=True, text=True, check=False)


def _gitleaks_falso(pasta: Path, codigo: int) -> Path:
    falso = pasta / "gitleaks"
    falso.write_text(f"#!/usr/bin/env bash\necho \"$@\" >> '{pasta}/args'\nexit {codigo}\n", encoding="utf-8")
    falso.chmod(0o755)
    return falso


def test_sem_o_binario_o_script_falha_e_diz_o_que_instalar():
    r = _rodar({"GITLEAKS_BIN": "gitleaks-que-nao-existe"})
    assert r.returncode == 1
    assert "falha em vez de pular" in r.stderr and "8.30.1" in r.stderr


@pytest.mark.parametrize("codigo", [0, 1])
def test_com_o_binario_o_script_repassa_o_resultado_e_varre_arvore_e_historico_de_head(tmp_path, codigo):
    r = _rodar({"GITLEAKS_BIN": str(_gitleaks_falso(tmp_path, codigo))})
    assert r.returncode == codigo
    chamadas = (tmp_path / "args").read_text(encoding="utf-8").splitlines()
    assert (
        chamadas[0].startswith("dir ")
        and "--config .gitleaks.toml" in chamadas[0]
        and "--redact" in chamadas[0]
        and "-v" in chamadas[0].split()
        and "--exit-code 1" in chamadas[0]
    )
    if (RAIZ / ".git").exists():
        assert chamadas[1].startswith("git ") and "--log-opts=HEAD" in chamadas[1]


@pytest.mark.parametrize("modo", ["dir", "git"])
def test_achado_em_um_so_modo_reprova_e_o_outro_modo_ainda_roda(tmp_path, modo):
    """Vazamento só na árvore ou só no histórico: cada modo responde pelo seu `|| status=1`, sem o outro segurar o resultado."""
    if not (RAIZ / ".git").exists():
        pytest.skip("sem .git o modo git não roda")
    falso = tmp_path / "gitleaks"
    falso.write_text(f'#!/usr/bin/env bash\necho "$1" >> \'{tmp_path}/modos\'\n[ "$1" = {modo} ] && exit 1\nexit 0\n', encoding="utf-8")
    falso.chmod(0o755)
    r = _rodar({"GITLEAKS_BIN": str(falso)})
    assert r.returncode == 1
    assert (tmp_path / "modos").read_text(encoding="utf-8").splitlines() == ["dir", "git"]


def test_check_sh_chama_o_gitleaks_sem_poder_pular():
    linhas = (RAIZ / "scripts" / "check.sh").read_text(encoding="utf-8").splitlines()
    assert any(linha.startswith("run bash scripts/gitleaks.sh") for linha in linhas)
    assert not any("gitleaks" in linha and ("|| true" in linha or "skip" in linha.lower()) for linha in linhas)


def test_config_estende_o_padrao_e_a_regra_de_cpf_pega_cpf_formatado():
    c = _cfg()
    assert c["extend"]["useDefault"] is True
    regra = next(r for r in c["rules"] if r["id"] == "cpf-formatado")
    assert re.search(regra["regex"], "cpf 000.000." + "201-00 aqui")


def test_a_allowlist_de_cpf_e_ancorada_e_so_vale_para_a_regra_de_cpf():
    listas = [a for a in _cfg()["allowlists"] if "regexes" in a]
    assert listas and all(len(a["targetRules"]) == 1 for a in listas), (
        "sem targetRules a exceção valeria para qualquer regra, inclusive segredo"
    )
    assert all(x.startswith("^") and x.endswith("$") for a in listas for x in a["regexes"])
    cpf = next(a for a in listas if a["targetRules"] == ["cpf-formatado"])

    def liberado(texto: str) -> bool:
        return any(re.search(x, texto) for x in cpf["regexes"])

    assert liberado("000.000.012-00") and liberado("000.000.123-00")
    assert not liberado("000.000." + "223-00")  # 2nn em diante não é pessoa de teste
    assert not liberado("x000.000.012-00") and not liberado("000.000.012-009")


def test_nenhum_caminho_de_codigo_inteiro_fora_da_varredura():
    caminhos = [p for a in _cfg()["allowlists"] for p in a.get("paths", [])]
    assert caminhos == [r"^uv\.lock$", r"(^|/)__pycache__/"]


def test_nenhum_pycache_versionado():
    """A exceção de `__pycache__` só vale para o bytecode local: um `git add -f` abriria um caminho sem varredura."""
    if not (RAIZ / ".git").exists():
        pytest.skip("sem .git não há o que conferir")
    versionados = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=True).stdout.splitlines()
    assert not [x for x in versionados if "__pycache__/" in x]


def test_gitleaksignore_so_tem_impressao_digital_de_commit_inteira():
    linhas = [x for x in (RAIZ / ".gitleaksignore").read_text(encoding="utf-8").splitlines() if x and not x.startswith("#")]
    assert linhas and all(re.fullmatch(r"[0-9a-f]{40}:[^:]+:[a-z-]+:\d+", x) for x in linhas), (
        "sem commit, a exceção valeria para a árvore de hoje"
    )


def test_ci_roda_o_sha256_dentro_de_migrations_sem_o_caminho_dobrado():
    ci = (RAIZ / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "- run: sha256sum -c 0001.sha256\n        working-directory: migrations" in ci
    assert "sha256sum -c migrations/0001.sha256" not in ci
