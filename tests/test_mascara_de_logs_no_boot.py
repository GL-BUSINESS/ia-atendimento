"""G-0085 (revisão 0911): a máscara de logs (`observabilidade.configurar`) tem de estar LIGADA nos dois pontos de entrada reais.

Antes, API e worker chamavam só `configurar_logging`: a fábrica de `LogRecord` com a máscara nunca era instalada, e um logger de terceiro
(Procrastinate, httpx, psycopg_pool) caía no `lastResort` com o texto em claro. Aqui um PROCESSO novo sobe cada ponto de entrada (sem banco:
a montagem pesada é trocada por um dublê) e o teste lê o stderr dele. O CPF é sintético (DV inválido de propósito).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.apoio_api import FINGERPRINT, H16, RESPONSAVEL_IA, TOKENS

CPF_SINTETICO = "000.000." + "201-00"
SEGREDO_DO_MODELO = "fw_chave-do-modelo-descartavel-123"
_EMITIR = (
    "import logging;"
    f"logging.getLogger('procrastinate.worker').warning('job falhou: cliente %s', {CPF_SINTETICO!r});"
    f"logging.getLogger('httpx').warning('cabecalho %s', {SEGREDO_DO_MODELO!r});"
    "print('fabrica=' + logging.getLogRecordFactory().__module__, flush=True)"
)
API = (
    "import ia_atendimento.api.ambiente as a; a._montar = lambda settings: None; a.criar_app_de_ambiente();" + _EMITIR
)  # fmt: skip
WORKER = (
    "import asyncio, ia_atendimento.worker as w\n"
    "async def _parado(settings):\n"
    f"    {_EMITIR}\n"
    "w.executar = _parado\n"
    "raise SystemExit(w.main([]))\n"
)


def _env(tmp_path: Path) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "PYTHONUNBUFFERED": "1",
        "DATABASE_URL": "postgresql://ia_app_a:x@127.0.0.1:1/inexistente", "MODELO_API_KEY_1": SEGREDO_DO_MODELO,
        "API_TOKENS": json.dumps(TOKENS), "CHAVE_AES_ID": "2", "CHAVE_AES_ARQUIVO": str(tmp_path / "chaves.json"), "CHAVE_H16": H16,
        "CHAVE_FINGERPRINT": FINGERPRINT, "CHAT_REF_CHAVE": "chave-chat-ref-de-teste-descartavel-01",
        "GATEWAY_HMAC_ARQUIVO": str(tmp_path / "gw.keys"), "SEGREDOS_SAIDA_ARQUIVO": str(tmp_path / "saida.json"),
        "RESPONSAVEL_IA": RESPONSAVEL_IA,
    }  # fmt: skip


def _rodar(codigo: str, tmp_path: Path) -> str:
    feito = subprocess.run(
        [sys.executable, "-c", codigo], env=_env(tmp_path), capture_output=True, text=True, timeout=60, cwd="/", check=False
    )
    saida = feito.stdout + feito.stderr
    assert feito.returncode == 0, saida[-2000:]
    return saida


def _conferir(saida: str) -> None:
    assert "fabrica=ia_atendimento.observabilidade" in saida, "a fábrica de LogRecord com a máscara não foi instalada"
    assert "job falhou: cliente [CPF]" in saida and CPF_SINTETICO not in saida
    assert "cabecalho [SEGREDO]" in saida and SEGREDO_DO_MODELO not in saida


def test_api_de_producao_liga_a_mascara_de_logs(tmp_path):
    _conferir(_rodar(API, tmp_path))


def test_worker_de_producao_liga_a_mascara_de_logs(tmp_path):
    _conferir(_rodar(WORKER, tmp_path))
