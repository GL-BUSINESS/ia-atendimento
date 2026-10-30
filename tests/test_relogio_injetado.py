"""Nenhum módulo de negócio chama `datetime.now()`/`date.today()`/`time.time()`: o tempo vem de um `Relogio` injetado (só `relogio.py` lê o relógio)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ia_atendimento.relogio import RelogioFalso

SRC = Path(__file__).resolve().parent.parent / "src" / "ia_atendimento"
PROIBIDO = re.compile(r"datetime\.now\(|\.utcnow\(|date\.today\(|\btime\.time\(|\btime\.monotonic\(")
# `now()` do banco em regra de negócio é proibido; a prontidão compara instantes que o PRÓPRIO banco gravou (batimento, fila) com o `now()` dele
NOW_DO_BANCO = re.compile(r"now\(\)\s*(?:::|-|\+)")
SO_RELOGIO_DO_SISTEMA = ("prontidao",)
MODULOS_DA_B13 = ("calendario", "chave", "chave_registro", "fila", "jobs", "prontidao")


@pytest.mark.parametrize("modulo", MODULOS_DA_B13)
def test_modulo_nao_le_o_relogio_do_sistema_nem_o_now_do_banco(modulo: str):
    codigo = (SRC / f"{modulo}.py").read_text(encoding="utf-8")
    sem_comentarios = "\n".join(linha.split("#", 1)[0] for linha in codigo.splitlines())
    achados = PROIBIDO.findall(sem_comentarios)
    if modulo not in SO_RELOGIO_DO_SISTEMA:
        achados += NOW_DO_BANCO.findall(sem_comentarios)
    assert achados == [], f"{modulo}.py lê o relógio do sistema: {achados}"


def test_relogio_falso_so_anda_quando_mandam():
    from datetime import UTC, datetime

    relogio = RelogioFalso(datetime(2026, 11, 17, 15, 0, tzinfo=UTC))
    assert relogio.agora() == datetime(2026, 11, 17, 15, 0, tzinfo=UTC)
    relogio.avancar(seconds=3, minutes=1)
    assert relogio.agora() == datetime(2026, 11, 17, 15, 1, 3, tzinfo=UTC)
    with pytest.raises(ValueError, match="fuso"):
        RelogioFalso(datetime(2026, 11, 17, 15, 0))
