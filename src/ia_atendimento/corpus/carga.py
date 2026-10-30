"""Leitura dos arquivos do corpus e montagem do `Corpus` tipado."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ia_atendimento.corpus.modelos import Corpus, Dialogo, Duble, Persona, Semente, Turno


def _ler_jsonl(caminho: Path) -> list[dict[str, Any]]:
    return [json.loads(linha) for linha in caminho.read_text(encoding="utf-8").splitlines() if linha.strip()]


def carregar_bruto(raiz: Path) -> dict[str, Any]:
    """Lê os arquivos do corpus sem validar nada (os testes mutam este dicionário e chamam `validar`)."""
    return {
        "personas": _ler_jsonl(raiz / "personas.jsonl"),
        "personas_m": _ler_jsonl(raiz / "personas_m.jsonl"),
        "dialogos": {arq.stem: _ler_jsonl(arq) for arq in sorted((raiz / "dialogos").glob("*.jsonl"))},
        "semente": json.loads((raiz / "semente.json").read_text(encoding="utf-8")),
        "duble": json.loads((raiz / "duble_personas.json").read_text(encoding="utf-8")),
    }


def montar(bruto: dict[str, Any]) -> Corpus:
    """Dicionário bruto → `Corpus` tipado. Levanta `pydantic.ValidationError` se o esquema não fecha."""
    return Corpus(
        personas=tuple(Persona.model_validate(p) for p in bruto["personas"]),
        personas_m=tuple(Persona.model_validate(p) for p in bruto["personas_m"]),
        dialogos={pid: Dialogo(persona_id=pid, turnos=tuple(Turno.model_validate(t) for t in ts)) for pid, ts in bruto["dialogos"].items()},
        semente=Semente.model_validate(bruto["semente"]),
        duble=Duble.model_validate(bruto["duble"]),
    )


def carregar(raiz: Path) -> Corpus:
    return montar(carregar_bruto(raiz))
