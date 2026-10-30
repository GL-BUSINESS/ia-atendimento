"""Pequena linguagem para os casos do estudo I: cada caso é (nome, papel, SQL, expectativa), como no `i-teste-0001.sh`.

Os casos formam UMA sequência com estado compartilhado (um banco só, como no script): o 2º atendimento do mesmo chat só é
recusado porque o 1º existe. Por isso rodam em ordem, no mesmo módulo, sem `-k` isolado.

Marcadores `@@NOME@@` no SQL são resolvidos na hora de rodar (ids que o banco gerou: ID1, ID2, CF, T7ID...).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import psycopg
import pytest

from tests.banco import Banco, resultado_texto, texto_do_erro

P1 = "11111111-1111-7111-8111-111111111111"
P2 = "22222222-2222-7222-8222-222222222222"
P3 = "33333333-3333-7333-8333-333333333333"
SES = "44444444-4444-7444-8444-444444444444"
FP = "a" * 64
FP2 = "b" * 64
H32 = "9f" * 16
APP, LEITURA, QUALIDADE, INTRUSO, SUPER = "ia_app_a", "ia_leitura_a", "ia_qualidade_a", "intruso", "postgres"

_MARCADOR = re.compile(r"@@([A-Z][A-Z0-9_]*)@@")
# ids que o banco gera (uuidv7/identity): descobertos na primeira vez que o SQL de algum caso os usa, como as `$(...)` do script
_PREGUICOSOS = {
    "ID1": (APP, "SELECT atendimento_id FROM ia.atendimento WHERE chat_id='chatAAAA0001' AND estado<>'encerrado';"),
    "ID2": (APP, "SELECT atendimento_id FROM ia.atendimento WHERE chat_id='chatBBBB0002';"),
    "T7ID": (APP, "SELECT chamada_id FROM ia.ferramenta_chamada WHERE ferramenta='t7';"),
    "LID": (APP, "SELECT atendimento_id FROM ia.atendimento WHERE chat_id='chatLLLL0012';"),
    "PAT": (APP, "SELECT atendimento_id FROM ia.atendimento WHERE chat_id='chatRRRR0016';"),
    "AID": (APP, "SELECT agendamento_id FROM ia.agendamento WHERE atendimento_id='@@PAT@@' AND seq=2;"),
}


class Ctx:
    """Banco da sequência + valores gerados por ele."""

    def __init__(self, banco: Banco, dir_so_0001: Path, sql_0001: str) -> None:
        self.banco = banco
        self.dir_so_0001 = dir_so_0001
        self.sql_0001 = sql_0001
        self.valores: dict[str, str] = {}
        self.extras: dict[str, object] = {}

    def valor(self, nome: str) -> str:
        if nome == "SQL_0001":
            return self.sql_0001
        if nome not in self.valores:
            if nome not in _PREGUICOSOS:
                raise KeyError(f"@@{nome}@@ ainda não foi definido")
            papel, consulta = _PREGUICOSOS[nome]
            self.valores[nome] = self.escalar(papel, consulta)
        return self.valores[nome]

    def render(self, sql: str) -> str:
        return _MARCADOR.sub(lambda m: self.valor(m.group(1)), sql)

    def executar(self, papel: str, sql: str) -> None:
        with self.banco.sessao(papel) as conn:
            conn.execute(self.render(sql))

    def escalar(self, papel: str, sql: str) -> str:
        return resultado_texto(self.banco, papel, self.render(sql))


Tipo = Literal["ok", "err", "eq", "nao_vazio", "func"]


@dataclass(frozen=True)
class Caso:
    nome: str
    tipo: Tipo
    papel: str = APP
    sql: str = ""
    esperado: str = ""  # err: regex que tem de aparecer no erro; eq: texto exato do último valor
    # ações sem veredito (o `run`/`owner` solto do script): (papel, sql) ou (papel, sql, nome_para_guardar_o_valor)
    antes: tuple[tuple[str, ...], ...] = ()
    depois: tuple[tuple[str, ...], ...] = ()
    guardar: str = ""  # nome em Ctx.valores para o valor devolvido (CF = RETURNING)
    func: Callable[[Ctx], None] | None = field(default=None, compare=False)

    def rodar(self, ctx: Ctx) -> None:
        self._acoes(ctx, self.antes)
        try:
            self._veredito(ctx)
        finally:
            self._acoes(ctx, self.depois)

    @staticmethod
    def _acoes(ctx: Ctx, acoes: tuple[tuple[str, ...], ...]) -> None:
        for papel, sql, *guardar in acoes:
            if guardar:
                ctx.valores[guardar[0]] = ctx.escalar(papel, sql)
            else:
                ctx.executar(papel, sql)

    def _veredito(self, ctx: Ctx) -> None:
        if self.tipo == "func":
            assert self.func is not None
            self.func(ctx)
        elif self.tipo == "ok":
            ctx.executar(self.papel, self.sql)
        elif self.tipo == "err":
            with pytest.raises(psycopg.Error) as erro:
                ctx.executar(self.papel, self.sql)
            texto = texto_do_erro(erro.value)
            assert re.search(self.esperado, texto), f"esperava /{self.esperado}/ no erro:\n{texto[:400]}"
        else:
            obtido = ctx.escalar(self.papel, self.sql)
            if self.tipo == "eq":
                assert obtido == self.esperado, f"esperava {self.esperado!r}, veio {obtido!r}"
            else:
                assert obtido, "esperava um valor não vazio"
            if self.guardar:
                ctx.valores[self.guardar] = obtido

    @property
    def id(self) -> str:
        base = unicodedata.normalize("NFKD", self.nome).encode("ascii", "ignore").decode()
        return re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower()[:70]


def ok(nome: str, papel: str, sql: str, *, antes: tuple[tuple[str, ...], ...] = (), depois: tuple[tuple[str, ...], ...] = ()) -> Caso:
    return Caso(nome, "ok", papel, sql, antes=antes, depois=depois)


def err(nome: str, papel: str, sql: str, padrao: str, *, antes: tuple[tuple[str, ...], ...] = ()) -> Caso:
    return Caso(nome, "err", papel, sql, padrao, antes=antes)


def eq(nome: str, papel: str, sql: str, esperado: str, *, antes: tuple[tuple[str, ...], ...] = ()) -> Caso:
    return Caso(nome, "eq", papel, sql, esperado, antes=antes)


def nao_vazio(nome: str, papel: str, sql: str, guardar: str = "") -> Caso:
    return Caso(nome, "nao_vazio", papel, sql, guardar=guardar)


def fn(nome: str, func: Callable[[Ctx], None]) -> Caso:
    return Caso(nome, "func", func=func)


def owner(sql: str) -> tuple[str, ...]:
    """`owner` do script: superusuário com SET ROLE ia_owner (dono do DDL), numa sessão só."""
    return (SUPER, f"SET ROLE ia_owner; {sql}")


# --- construtores de SQL sintético (os `atd`, `chamada`, `pas`... do script; só dados de teste) ------------------------------


def atd(chat, chave, fp, pessoa, cols="", vals="", *, modo="duble", gatilho="venda", faixa="210.00, 'media'") -> str:
    return (
        "INSERT INTO ia.atendimento (origem, chave_logica, idempotency_key, entrada_fingerprint, gatilho, disparado_por, pessoa_id, chat_id, phone_id,"
        " roteiro_versao, regras_versao, catalogo_versao, motor_versao, modo, criterio_versao, comissao_esperada_brl, faixa_esforco"
        + cols
        + ")"
        f" VALUES ('n8n_braco', '{chave}', encode(sha256(convert_to('{chave}','UTF8')),'hex'), '{fp}', '{gatilho}', 'operador@exemplo.test', '{pessoa}',"
        f" '{chat}', 'a1b2c3d4e5f6a1b2c3d4e5f6', 1,1,1,1, '{modo}', 'crit_v1', {faixa}" + vals + ");"
    )


def mk(chat, hex2, pessoa, cols="", vals="", **kw) -> str:
    """`venda:` + hex2 repetido 16 vezes (32 hex), como o `mk` do script."""
    return atd(chat, "venda:" + hex2 * 16, FP, pessoa, cols, vals, **kw)


def chamada(atendimento, pessoa, ferramenta, chave, cols="", vals="") -> str:
    return (
        "INSERT INTO ia.ferramenta_chamada (atendimento_id, pessoa_id, ferramenta, ferramenta_versao, classe_efeito, chave_logica, idem_key, modo"
        f"{cols}) VALUES ('{atendimento}','{pessoa}','{ferramenta}','1.0.0','efeito_irreversivel','{chave}',"
        f" encode(sha256(convert_to('{chave}','UTF8')),'hex'), 'duble'{vals});"
    )


def t7(atendimento, pessoa, chave, tentativa=1) -> str:
    return chamada(
        atendimento, pessoa, "t7", chave, ", banco, args_hash, confirmacao_id, tentativa_n", f", 'FACTA', '{FP}', '@@CF@@', {tentativa}"
    )


def pas(cols, tipo, vals) -> str:
    """Passo no ID1 com `ordem` = próxima livre."""
    ordem = "(SELECT coalesce(max(ordem),0)+1 FROM ia.passo WHERE atendimento_id='@@ID1@@')"
    return f"INSERT INTO ia.passo (atendimento_id, ordem, tipo, texto{cols}) VALUES ('@@ID1@@',{ordem},'{tipo}','x'{vals});"


def psl(cols, ordem, tipo, vals) -> str:
    return f"INSERT INTO ia.passo (atendimento_id, ordem, tipo, texto{cols}) VALUES ('@@LID@@',{ordem},'{tipo}','x'{vals});"


def hx(caractere: str) -> str:
    return caractere * 64


def cand(hexa, cols, vals) -> str:
    return f"INSERT INTO ia.candidato (sessao_id, chat_ref, criterio_versao, {cols}) VALUES ('{SES}','{hx(hexa)}','crit_v1',{vals});"
