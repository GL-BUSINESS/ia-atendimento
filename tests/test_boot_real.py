"""Boot REAL da API, como a OPERACAO §8 manda (`uvicorn --factory ia_atendimento.api.ambiente:criar_app_de_ambiente`), contra o Postgres descartável.

Prova o que `caplog` esconde (R2-03): em produção o logger da aplicação não tinha handler nem nível, então a linha `req trace=…` e os alertas não saíam. Aqui
um subprocesso sobe, recebe requisições de verdade e o teste lê o STDERR dele. Também prende R2-04 (dialeto `+psycopg`) e R1-19/R2-06 (access log desligado).
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from tests import apoio_api
from tests.apoio_api import TOKENS, env_de_processo

ambiente = apoio_api.ambiente
pytestmark = pytest.mark.banco
CHAVE_SECRETA_NA_URL = "venda:57460eeceae26a872a0bef6a72cdf8df"


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def servidor_real(ambiente, tmp_path):
    """Sobe o uvicorn de verdade; entrega `(url, ler_stderr)`; derruba ao fim. Espera a CONDIÇÃO (`/healthz` 200), não um tempo."""
    processos: list[subprocess.Popen] = []

    def subir(dialeto: str = ""):
        porta, log = _porta_livre(), tmp_path / f"uvicorn{dialeto or '-puro'}.log"
        with open(log, "w") as saida:
            processo = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "--factory", "ia_atendimento.api.ambiente:criar_app_de_ambiente", "--host", "127.0.0.1",
                 "--port", str(porta), "--log-level", "info"],
                env=env_de_processo(ambiente, tmp_path, dialeto), stdout=saida, stderr=subprocess.STDOUT, cwd="/",
            )  # fmt: skip
        processos.append(processo)
        url = f"http://127.0.0.1:{porta}"
        fim = time.monotonic() + 30
        while time.monotonic() < fim:
            if processo.poll() is not None:
                raise AssertionError("o uvicorn morreu na subida:\n" + log.read_text()[-2000:])
            try:
                if httpx.get(f"{url}/healthz", timeout=1).status_code == 200:
                    return url, log
            except httpx.HTTPError:
                time.sleep(0.1)
        raise AssertionError("o uvicorn não ficou de pé:\n" + log.read_text()[-2000:])

    yield subir
    for processo in processos:
        processo.terminate()
        try:
            processo.wait(5)
        except subprocess.TimeoutExpired:
            processo.kill()


def _esperar_no_log(log: Path, trecho: str, limite_s: float = 10.0) -> str:
    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        texto = log.read_text()
        if trecho in texto:
            return texto
        time.sleep(0.05)
    raise AssertionError(f"{trecho!r} não apareceu no log:\n{log.read_text()[-2500:]}")


def test_a_linha_de_requisicao_e_os_alarmes_de_credencial_saem_em_producao(servidor_real):
    url, log = servidor_real()
    cab = {"x-ia-token": TOKENS["vigia"]}
    assert httpx.get(f"{url}/saude", headers=cab).status_code == 200
    r_assinatura = httpx.post(
        f"{url}/eventos/chatguru",
        content=b"{}",
        headers={"x-gl-origem": "chatguru-ia", "x-gl-rota": "ia-mensagem", "x-gl-timestamp": "1", "x-gl-assinatura": "v1=00"},
    )
    r_token = httpx.post(f"{url}/atendimentos", content=b"{}", headers={"x-ia-token": "token-errado-descartavel-0123456789abcdef"})
    r_origem = httpx.post(f"{url}/atendimentos", content=b"{}", headers=cab)
    assert (r_assinatura.status_code, r_token.status_code, r_origem.status_code) == (401, 401, 403)
    assert httpx.get(f"{url}/atendimentos/por-chave/{CHAVE_SECRETA_NA_URL}", headers=cab).status_code == 404
    texto = _esperar_no_log(log, "codigo=origem_nao_autorizada")
    # a linha de requisição, com o molde da rota e o código
    assert "INFO ia_atendimento.api req trace=" in texto and "rota=/saude status=200" in texto
    assert "rota=/eventos/chatguru status=401 codigo=assinatura_invalida" in texto
    assert "rota=/atendimentos status=401 codigo=token_invalido" in texto
    assert "rota=/atendimentos status=403 codigo=origem_nao_autorizada" in texto
    # os alarmes do TI em WARNING
    assert "WARNING ia_atendimento.api alerta ti: contador=assinatura_invalida total=1" in texto
    assert "alerta ti: contador=token_invalido total=1" in texto
    # o trace_id da resposta casa com uma linha do log
    assert f"req trace={r_assinatura.json()['trace_id']}" in texto
    # nada de acesso do uvicorn (caminho e query) nem de valor de cliente
    assert (
        "POST /eventos/chatguru" not in texto
        and CHAVE_SECRETA_NA_URL not in texto
        and "por-chave" not in texto.replace("rota=/atendimentos/por-chave/{chave}", "")
    )
    assert TOKENS["vigia"] not in texto and "token-errado" not in texto


def test_subida_real_com_dialeto_psycopg_na_url_morre_com_mensagem_sem_a_senha(ambiente, tmp_path):
    """R2-04 no processo de verdade: `postgresql+psycopg://` deixava o `/readyz` em 503 `erro_de_consulta` para sempre; agora o uvicorn não sobe."""
    log = tmp_path / "dialeto.log"
    with open(log, "w") as saida:
        processo = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "--factory",
                "ia_atendimento.api.ambiente:criar_app_de_ambiente",
                "--port",
                str(_porta_livre()),
            ],
            env=env_de_processo(ambiente, tmp_path, "+psycopg"),
            stdout=saida,
            stderr=subprocess.STDOUT,
            cwd="/",
        )
    assert processo.wait(30) != 0
    texto = log.read_text()
    assert "database_url" in texto and "+psycopg" in texto and "ia_app_a:x@" not in texto, texto[-1500:]


def test_configurar_logging_e_idempotente_e_nao_propaga(monkeypatch):
    import logging
    import sys
    import threading

    from ia_atendimento.api.logs import NOME_DO_LOGGER, configurar_logging

    logger = logging.getLogger(NOME_DO_LOGGER)
    acesso = logging.getLogger("uvicorn.access")
    estado = (list(logger.handlers), logger.level, logger.propagate, acesso.disabled)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)  # `instalar_excepthook` é global: o monkeypatch o devolve ao fim
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    try:
        assert configurar_logging() is logger
        depois_da_primeira = len(logger.handlers)
        assert configurar_logging() is logger and len(logger.handlers) == depois_da_primeira, "duas chamadas não duplicam o handler"
        assert logger.level == logging.INFO and logger.propagate is False and acesso.disabled is True
    finally:  # nada vaza para os testes que usam `caplog` (que precisa da propagação até o root)
        logger.handlers[:], logger.level, logger.propagate, acesso.disabled = estado
