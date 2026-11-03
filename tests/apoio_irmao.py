"""O repositório irmão (B2.4, R1-02): a consistência entre `ia-atendimento` e `bancos-duble` não pode ser um skip que o portão deixa passar calado.

`localizar` devolve o checkout do irmão apontado por uma variável de ambiente. Faltando: pula (desenvolvimento rápido) ou, com
`PESSOAS_TESTE_EXIGE_IRMAO=1` (que o `scripts/check.sh` liga), FALHA com a mensagem de como definir a variável.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

EXIGE = "PESSOAS_TESTE_EXIGE_IRMAO"


def localizar(variavel: str, arquivo_que_prova: str, quem: str) -> Path:
    """Checkout do irmão, ou `skip`/`fail` (conforme `PESSOAS_TESTE_EXIGE_IRMAO`)."""
    bruto = os.environ.get(variavel)
    raiz = Path(bruto).expanduser() if bruto else None
    if raiz is not None and (raiz / arquivo_que_prova).is_file():
        return raiz
    motivo = f"defina {variavel} (checkout do {quem} com a B2.4; precisa conter {arquivo_que_prova}) para comparar os dois repositórios" + (
        "" if raiz is None else f"; {raiz} não tem o arquivo"
    )
    if os.environ.get(EXIGE) == "1":
        pytest.fail(f"{EXIGE}=1 e o irmão não foi encontrado: {motivo}", pytrace=False)
    pytest.skip(motivo)
