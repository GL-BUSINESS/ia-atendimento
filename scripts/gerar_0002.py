#!/usr/bin/env python3
"""Gera migrations/0002_procrastinate.up.sql a partir do schema do pacote `procrastinate` pinado.

O corpo é `SchemaManager.get_schema()`, o mesmo texto de `procrastinate schema --read` (o CLI exige conexão ao abrir o app).
Rode de novo SÓ ao trocar a versão pinada, e só antes de a 0002 ser aplicada em algum lugar; depois disso o diff do pacote vira 0003+.
Uso: uv run python scripts/gerar_0002.py [--verificar]
"""

from __future__ import annotations

import sys
from importlib.metadata import version
from pathlib import Path

from procrastinate.schema import SchemaManager

DESTINO = Path(__file__).resolve().parent.parent / "migrations" / "0002_procrastinate.up.sql"


def gerar() -> str:
    v = version("procrastinate")
    return (
        f"-- 0002_procrastinate.up.sql · fila de jobs (Procrastinate {v}, versão pinada em pyproject.toml/uv.lock) no schema `procrastinate`.\n"
        "-- Gerado por scripts/gerar_0002.py; o corpo entre os marcadores é o schema.sql do pacote (= `procrastinate schema --read`), sem edição.\n"
        "-- NÃO reaplicar (o Procrastinate não é idempotente): o ledger ia.migracao impede. Trocar a versão do pacote depois de aplicada = 0003+.\n"
        "-- Aplicar como s4_super (psql -1 -v ON_ERROR_STOP=1); o arquivo faz SET ROLE ia_owner e cria tudo em `procrastinate`. Os default\n"
        "-- privileges da 0001 dão DML e EXECUTE ao ia_app. A conexão da aplicação usa search_path = procrastinate, public (migrations/README.md).\n"
        "SET ROLE ia_owner; SET search_path = procrastinate, public;\n"
        f"-- >>> procrastinate {v} schema.sql\n"
        f"{SchemaManager.get_schema()}"
        f"-- <<< procrastinate {v} schema.sql\n"
        "RESET search_path; RESET ROLE;\n"
    )


def main() -> int:
    novo = gerar()
    if "--verificar" in sys.argv:
        atual = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else ""
        if atual != novo:
            print("0002 desatualizada em relação ao procrastinate pinado", file=sys.stderr)
            return 1
        print("0002 em dia")
        return 0
    DESTINO.write_text(novo, encoding="utf-8")
    print(f"escrito {DESTINO} ({len(novo)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
