"""Boot REAL do worker (R2-02, revisão 2 da B5.7b): `python -m ia_atendimento.worker` num processo à parte, contra o Postgres descartável.

Prova o que nenhum teste de módulo prova: que o ponto de entrada que o compose vai chamar sobe o worker de verdade (batimento na tabela
`procrastinate_workers`), que o healthcheck `--saude` enxerga esse batimento (e reprova sem ele), que a vigia o PARA com código 3 se a linha some
e que o SIGTERM encerra limpo (código 0).
"""

from __future__ import annotations

import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests import apoio_api
from tests.apoio_api import env_de_processo

ambiente = apoio_api.ambiente
pytestmark = pytest.mark.banco
COMANDO = [sys.executable, "-m", "ia_atendimento.worker"]


def _vivos(ambiente) -> int:
    return ambiente.escalar("SELECT count(*) FROM procrastinate.procrastinate_workers")


@pytest.fixture
def subir_worker(ambiente, tmp_path: Path):
    """Sobe o worker pelo comando; espera a CONDIÇÃO (linha do worker no banco), não um tempo. Derruba ao fim."""
    processos: list[subprocess.Popen] = []

    def subir():
        log = tmp_path / f"worker{len(processos)}.log"
        with open(log, "w") as saida:
            processo = subprocess.Popen(COMANDO, env=env_de_processo(ambiente, tmp_path), stdout=saida, stderr=subprocess.STDOUT, cwd="/")
        processos.append(processo)
        fim = time.monotonic() + 40
        while _vivos(ambiente) == 0:
            if processo.poll() is not None:
                raise AssertionError("o worker morreu na subida:\n" + log.read_text()[-2500:])
            if time.monotonic() > fim:
                raise AssertionError("o worker não registrou batimento no banco:\n" + log.read_text()[-2500:])
            time.sleep(0.1)
        return processo, log

    yield subir
    for processo in processos:
        if processo.poll() is None:
            processo.kill()
            processo.wait(10)


def _saude(ambiente, tmp_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*COMANDO, "--saude"], env=env_de_processo(ambiente, tmp_path), capture_output=True, text=True, cwd="/", timeout=30, check=False
    )


def test_o_comando_sobe_o_worker_de_verdade_e_o_healthcheck_ve_o_batimento(ambiente, tmp_path, subir_worker):
    processo, _log = subir_worker()
    assert processo.poll() is None and _vivos(ambiente) == 1
    antes = ambiente.escalar("SELECT extract(epoch FROM now() - last_heartbeat) FROM procrastinate.procrastinate_workers")
    assert antes < 30, "batimento recente no banco"
    ok = _saude(ambiente, tmp_path)
    assert (ok.returncode, ok.stdout.strip()) == (0, "ok")


def test_o_healthcheck_reprova_sem_batimento_recente_e_sem_banco(ambiente, tmp_path, subir_worker):
    processo, _log = subir_worker()
    processo.kill()  # SIGKILL: a linha do worker fica no banco, com o batimento envelhecendo
    processo.wait(10)
    with ambiente.super() as conn:
        conn.execute("UPDATE procrastinate.procrastinate_workers SET last_heartbeat = now() - interval '5 minutes'")
    ruim = _saude(ambiente, tmp_path)
    assert (ruim.returncode, ruim.stdout.strip()) == (1, "sem batimento recente")
    # banco inalcançável (porta sem servidor): veredito ruim, sem vazar a URL
    env = env_de_processo(ambiente, tmp_path)
    env["DATABASE_URL"] = "postgresql://ia_app_a:segredo-da-url@127.0.0.1:1/ia"
    fora = subprocess.run([*COMANDO, "--saude"], env=env, capture_output=True, text=True, cwd="/", timeout=30, check=False)
    assert fora.returncode == 1 and "banco inalcancavel" in fora.stdout and "segredo-da-url" not in fora.stdout + fora.stderr
    sem_url = {k: v for k, v in env.items() if k != "DATABASE_URL"}
    assert (
        subprocess.run([*COMANDO, "--saude"], env=sem_url, capture_output=True, text=True, cwd="/", timeout=30, check=False).returncode == 1
    )


def test_a_vigia_do_processo_real_para_o_worker_com_codigo_3_se_a_linha_dele_some(ambiente, tmp_path, subir_worker):
    processo, log = subir_worker()
    with ambiente.super() as conn:
        conn.execute("DELETE FROM procrastinate.procrastinate_workers")  # outro worker o podou
    assert processo.wait(45) == 3, log.read_text()[-2500:]
    texto = log.read_text()
    # a vigia (10 s) ou o `fetch_job` derrubado pela FK (corrida com um job periódico): o veredito e a saída são os mesmos
    assert "linha_sumiu" in texto and "worker parado pela vigia do batimento (linha_sumiu)" in texto
    assert "ia_app_a:x@" not in texto, "a URL do banco não aparece no log"


def test_sigterm_encerra_o_worker_limpo_com_codigo_0_e_desregistra_o_batimento(ambiente, tmp_path, subir_worker):
    processo, log = subir_worker()
    processo.send_signal(signal.SIGTERM)
    assert processo.wait(45) == 0, log.read_text()[-2500:]
    assert _vivos(ambiente) == 0, "o worker desregistrou a própria linha ao parar"


def test_configuracao_invalida_derruba_o_worker_na_subida_sem_citar_o_valor(ambiente, tmp_path):
    env = env_de_processo(ambiente, tmp_path)
    env["CHAVE_H16"] = "curta-demais-segredo-xyz"
    r = subprocess.run(COMANDO, env=env, capture_output=True, text=True, cwd="/", timeout=30, check=False)
    assert r.returncode == 1 and "chave_h16" in r.stderr
    assert "curta-demais-segredo-xyz" not in r.stdout + r.stderr and "ia_app_a:x@" not in r.stdout + r.stderr


def test_o_pyproject_expoe_o_comando_ia_worker_e_ele_e_o_main_do_modulo():
    import tomllib

    raiz = Path(__file__).resolve().parent.parent
    scripts = tomllib.loads((raiz / "pyproject.toml").read_text())["project"]["scripts"]
    assert scripts == {"ia-worker": "ia_atendimento.worker:main"}
    from ia_atendimento import worker

    assert worker.main.__name__ == "main" and worker.EXIT_PERDEU_BATIMENTO == 3
