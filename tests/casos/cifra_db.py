"""Os 13 casos de cifra do estudo I (§5 «Cifra»), agora com o `Chaveiro` de verdade da aplicação em vez de `cryptography` solto."""

from __future__ import annotations

import psycopg
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ia_atendimento.cifra import Chaveiro, FalhaAoDecifrar
from tests.casos.dsl import APP, LEITURA, Caso, Ctx, fn

TEXTO = "meu CPF é 000.000.000-00 e quero 3 mil em 24x"  # sintético
INSERE = (
    "INSERT INTO ia.conversa_cifrada (atendimento_id, seq, remetente, tipo, cobre_ate_seq, mascarado, chave_id, nonce, cifra)"
    " VALUES (%s,%s,%s,%s,%s,%s,1,%s,%s)"
)


def _estado(ctx: Ctx):
    if "cifra" not in ctx.extras:
        chaveiro = Chaveiro({1: AESGCM.generate_key(bit_length=256)}, vigente=1)
        atd = ctx.valor("ID1")
        ctx.extras["cifra"] = (chaveiro, atd, chaveiro.cifrar(TEXTO, atd, seq=1, remetente="cliente", tipo="mensagem"))
    return ctx.extras["cifra"]


def _inserir(ctx: Ctx, seq: int, remetente: str, tipo: str, cobre, mascarado: bool, nonce=None, cifra=None) -> None:
    _, atd, cif = _estado(ctx)
    with ctx.banco.sessao(APP) as conn:
        conn.execute(
            INSERE, (atd, seq, remetente, tipo, cobre, mascarado, cif.nonce if nonce is None else nonce, cif.ct if cifra is None else cifra)
        )


def _recusa_por_forma(ctx: Ctx, *args, **kw) -> None:
    with pytest.raises(psycopg.errors.CheckViolation) as erro:
        _inserir(ctx, *args, **kw)
    assert erro.value.diag.constraint_name == "conversa_cifrada_forma_check"


def _insere(ctx: Ctx) -> None:
    _inserir(ctx, 1, "cliente", "mensagem", None, True)


def _decifra(ctx: Ctx) -> None:
    chaveiro, atd, _ = _estado(ctx)
    with ctx.banco.sessao(APP) as conn:
        nonce, ct = conn.execute("SELECT nonce, cifra FROM ia.conversa_cifrada WHERE seq=1 AND atendimento_id=%s", (atd,)).fetchone()
    assert chaveiro.decifrar(1, bytes(nonce), bytes(ct), atd, seq=1, remetente="cliente", tipo="mensagem") == TEXTO


def _banco_nao_tem_o_texto(ctx: Ctx) -> None:
    _, atd, _ = _estado(ctx)
    with ctx.banco.sessao(APP) as conn:
        achou = conn.execute(
            "SELECT position(convert_to('CPF','UTF8') in cifra) + position(convert_to('3 mil','UTF8') in cifra) FROM ia.conversa_cifrada WHERE seq=1 AND atendimento_id=%s",
            (atd,),
        ).fetchone()
    assert achou == (0,)


def _aad_trocada(ctx: Ctx) -> None:
    chaveiro, atd, cif = _estado(ctx)
    for troca in ({"seq": 2}, {"remetente": "ia"}, {"tipo": "resumo"}):
        contexto = {"seq": 1, "remetente": "cliente", "tipo": "mensagem", **troca}
        with pytest.raises(FalhaAoDecifrar):
            chaveiro.decifrar(1, cif.nonce, cif.ct, atd, **contexto)


def _leitura_nao_le(ctx: Ctx) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege), ctx.banco.sessao(LEITURA) as conn:
        conn.execute("SELECT count(*) FROM ia.conversa_cifrada")


def _nonce_curto(ctx: Ctx) -> None:
    _recusa_por_forma(ctx, 2, "cliente", "mensagem", None, True, nonce=b"\x00\x11")


def _cifra_curta(ctx: Ctx) -> None:
    _recusa_por_forma(ctx, 3, "cliente", "mensagem", None, True, cifra=TEXTO.encode()[:10])


def _resumo_aceito(ctx: Ctx) -> None:
    _inserir(ctx, 11, "ia", "resumo", 10, True)


def _cofre(ctx: Ctx) -> None:
    _, atd, cif = _estado(ctx)
    with ctx.banco.sessao(APP) as conn:
        conn.execute(
            "INSERT INTO ia.cofre (atendimento_id, finalidade, chave_id, nonce, cifra) VALUES (%s,'digitacao',1,%s,%s)",
            (atd, cif.nonce, cif.ct),
        )


def casos_cifra() -> list[Caso]:
    return [
        fn("insere linha cifrada", _insere),
        fn("decifra no runtime = texto original", _decifra),
        fn("o banco não contém o texto em claro", _banco_nao_tem_o_texto),
        fn("linha copiada para outro seq/atendimento não decifra (AAD)", _aad_trocada),
        fn("ia_leitura NÃO lê o texto cifrado", _leitura_nao_le),
        fn("nonce com tamanho errado recusado", _nonce_curto),
        fn("'cifra' curta demais (texto em claro sem tag) recusada", _cifra_curta),
        fn("resumo (tipo=resumo, remetente=ia, cobre_ate_seq) aceito", _resumo_aceito),
        fn("resumo sem cobre_ate_seq recusado", lambda c: _recusa_por_forma(c, 12, "ia", "resumo", None, True)),
        fn("resumo 'do cliente' recusado", lambda c: _recusa_por_forma(c, 13, "cliente", "resumo", 10, True)),
        fn("texto NÃO mascarado recusado (mascarado=false)", lambda c: _recusa_por_forma(c, 14, "cliente", "mensagem", None, False)),
        fn("remetente fora de cliente|ia recusado", lambda c: _recusa_por_forma(c, 15, "consultor", "mensagem", None, True)),
        fn("cofre da digitação aceita linha cifrada", _cofre),
    ]
