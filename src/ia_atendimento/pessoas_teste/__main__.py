"""CLI do kit `config/chats-teste.sh` (B2.4). Sem rede, sem banco: só monta o arquivo `PESSOAS_TESTE_ARQUIVO` e lista as pessoas.

python -m ia_atendimento.pessoas_teste arquivo --par <chat_id 24 hex>=<persona_id> [--par …] [--saida CAMINHO] [--juntar ARQUIVO]
    JSON `{"pessoas": [<as 84>], "chats": {chat_id: pessoa_id}}` (stdout ou arquivo 0600). O chat de teste é da TI;
    a persona só diz de qual pessoa ele vale. `--juntar` PRESERVA os chats de um arquivo anterior (o orquestrador valida a lista
    inteira de `chats_teste` contra o arquivo lido no boot: arquivo só com o chat novo derruba o `aplicar` em merge e o `limpar`).
python -m ia_atendimento.pessoas_teste listar        persona_id e pessoa_id (sem CPF, sem nome)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from ia_atendimento.pessoas_teste.arquivo import PessoasTesteInvalidas
from ia_atendimento.pessoas_teste.catalogo import catalogo_padrao


def _pares_do_arquivo(caminho: str) -> dict[str, str] | None:
    """`{chat: persona_id}` de um `PESSOAS_TESTE_ARQUIVO` anterior (a pessoa de cada chat volta a ser a persona do catálogo)."""
    catalogo = catalogo_padrao()
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
        return {chat: catalogo.por_pessoa(pessoa).persona_id for chat, pessoa in dados["chats"].items()}  # type: ignore[union-attr]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def _arquivo(pares: list[str], saida: str | None, juntar: str | None = None) -> int:
    chats: dict[str, str] = {}
    if juntar is not None:
        anteriores = _pares_do_arquivo(juntar)
        if anteriores is None:
            print("--juntar: arquivo ausente, ilegível ou com pessoa fora do catálogo", file=sys.stderr)
            return 2
        chats.update(anteriores)
    for par in pares:
        chat, separador, persona = par.partition("=")
        if not separador or (chat in chats and chats[chat] != persona):
            print("--par: use CHAT=PERSONA, sem repetir o chat com outra persona", file=sys.stderr)
            return 2
        chats[chat] = persona
    catalogo = catalogo_padrao()
    try:
        fixas = catalogo.como_pessoas_teste(chats)
    except PessoasTesteInvalidas as erro:
        print(erro, file=sys.stderr)
        return 2
    texto = (
        json.dumps({"pessoas": sorted(str(p) for p in fixas.pessoas), "chats": {c: str(p) for c, p in fixas.chats.items()}}, indent=1)
        + "\n"
    )
    if saida is None:
        print(texto, end="")
        return 0
    destino = Path(saida)
    descritor = os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descritor, "w", encoding="utf-8") as f:
        f.write(texto)
    print(f"escrito {destino} ({len(fixas.pessoas)} pessoas, {len(fixas.chats)} chat(s))")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m ia_atendimento.pessoas_teste", description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = ap.add_subparsers(dest="comando", required=True)
    a = sub.add_parser("arquivo")
    a.add_argument("--par", action="append", default=[], metavar="CHAT=PERSONA", help="chat de teste (24 hex) e a persona dele; repetível")
    a.add_argument("--saida", help="caminho do arquivo (0600); sem ele imprime em stdout")
    a.add_argument("--juntar", metavar="ARQUIVO", help="preserva os chats de um arquivo anterior e acrescenta os --par")
    sub.add_parser("listar")
    args = ap.parse_args(argv)
    if args.comando == "listar":
        for p in catalogo_padrao().pessoas:
            print(f"{p.persona_id}\t{p.pessoa_id}")
        return 0
    return _arquivo(args.par, args.saida, args.juntar)


if __name__ == "__main__":
    sys.exit(main())
