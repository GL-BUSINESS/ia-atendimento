"""`POST /atendimentos/{id}/anotacoes` e `POST /sessoes/{id}/candidatos` (contrato 08 §5.6).

Anotação: texto do OPERADOR (não do cliente), passo `anotacao_operador`, vale em qualquer estado, inclusive `encerrado`;
`pii_no_texto_livre` se a máscara o mudaria.
O texto da anotação vai a no máximo 240 caracteres: o CHECK do passo limita `Anotação (categoria): nota` a 300 (categoria de até 40 + o
prefixo).
Candidatos: `chat_ref = HMAC-SHA256(chat_ref_chave, chat_id)`; várias chamadas por sessão (uma por candidato); igual ⇒ repetido,
diferente na mesma `(sessao, chat_ref)` ⇒ 409.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from typing import Annotated, Any, Final

import psycopg
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from ia_atendimento import passos
from ia_atendimento.api.contexto import ContextoApi
from ia_atendimento.api.erros import ErroApi
from ia_atendimento.api.validacao import LoginOuEmail, erro_de_validacao, rejeitar_documento, rejeitar_pii, uuid_do_caminho, validar
from ia_atendimento.estado import Hex24
from ia_atendimento.linha_tempo import gravar_passo
from ia_atendimento.passos import LIMITE_NOTA
from ia_atendimento.tipos import LIMITE_JSON_OCTETOS, Codigo40, Perfil, octetos_como_jsonb

MAX_CANDIDATOS: Final = 200
Codigo = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,40}$")]


class Anotacao(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    operador: LoginOuEmail
    categoria: Codigo
    texto: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=LIMITE_NOTA)]


class Candidato(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    chat_id: Hex24
    posicao: Annotated[int, Field(ge=1, le=1_000_000)] | None = None
    perfil_versao: Annotated[int, Field(ge=1, le=32767)] = 1
    perfil: Perfil = Field(default_factory=dict)
    escolhido: bool
    atendimento_id: uuid.UUID | None = None
    recusa: Codigo40 | None = None  # contrato 08 §5.6: ^[a-z0-9_]{1,40}$, sem sequência de documento

    @model_validator(mode="after")
    def _regras_do_check(self) -> Candidato:
        """`candidato_forma_check` da 0001: escolhido ⇒ `atendimento_id` xor `recusa`; não escolhido ⇒ sem atendimento e (`recusa` xor
        `posicao`)."""
        if self.escolhido and (self.atendimento_id is None) == (self.recusa is None):
            raise ValueError("escolhido exige atendimento_id ou recusa, nunca os dois")
        if not self.escolhido and (self.atendimento_id is not None or (self.recusa is None) == (self.posicao is None)):
            raise ValueError("não escolhido: sem atendimento_id e com recusa ou posicao (uma só)")
        if octetos_como_jsonb(self.perfil) > LIMITE_JSON_OCTETOS:
            raise ValueError("perfil acima de 2 KB")
        return self


class Candidatos(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    criterio_versao: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.-]{1,64}$")]
    candidatos: Annotated[list[Candidato], Field(min_length=1, max_length=MAX_CANDIDATOS)]


def criar_anotacao(ctx: ContextoApi, atendimento_id: str, corpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    atd = uuid_do_caminho(atendimento_id, "id")
    dados = validar(Anotacao, corpo)
    rejeitar_documento("operador", dados.operador)
    rejeitar_pii("texto", dados.texto)
    with ctx.conexao() as conn:
        if conn.execute("SELECT 1 FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone() is None:
            raise ErroApi("atendimento_inexistente", campo="id")
        # `nomes=()`: o orquestrador não guarda o nome do cliente; a rejeição é por FORMA (08 §5.4), não por nome
        passo = passos.criar("anotacao_operador", nomes=(), operador=dados.operador, resultado=dados.categoria, nota=dados.texto)
        gravado = gravar_passo(conn, atd, ctx=None, dados=passo, nomes=())
    return 201, {"ordem": gravado.ordem}


def chat_ref(chave: bytes, chat_id: str) -> str:
    return hmac.new(chave, chat_id.encode("ascii"), hashlib.sha256).hexdigest()


def _registro(sessao: uuid.UUID, criterio: str, ref: str, c: Candidato) -> dict[str, Any]:
    return {
        "sessao": sessao, "criterio": criterio, "ref": ref, "posicao": c.posicao, "perfil_versao": c.perfil_versao,
        "perfil": Jsonb(c.perfil),
        "escolhido": c.escolhido, "atendimento": c.atendimento_id, "recusa": c.recusa,
    }  # fmt: skip


def _igual(existente: tuple[Any, ...], c: Candidato, criterio: str) -> bool:
    criterio_gravado, posicao, perfil_versao, perfil, escolhido, atendimento, recusa = existente
    return (criterio_gravado, posicao, perfil_versao, perfil, escolhido, atendimento, recusa) == (
        criterio, c.posicao, c.perfil_versao, json.loads(json.dumps(c.perfil)), c.escolhido, c.atendimento_id, c.recusa,
    )  # fmt: skip


_INSERIR_CANDIDATO = (
    "INSERT INTO ia.candidato (sessao_id, chat_ref, criterio_versao, posicao, perfil_versao, perfil, escolhido, atendimento_id, recusa)"
    " VALUES (%(sessao)s, %(ref)s, %(criterio)s, %(posicao)s, %(perfil_versao)s, %(perfil)s, %(escolhido)s, %(atendimento)s, %(recusa)s)"
    " ON CONFLICT (sessao_id, chat_ref) DO NOTHING RETURNING candidato_id"
)


def _gravar_um(conn: psycopg.Connection, sessao: uuid.UUID, criterio: str, ref: str, c: Candidato) -> bool:
    """`True` = gravou; `False` = já existia IGUAL (também se a gêmea concorrente acabou de gravar: o `ON CONFLICT` espera o commit dela).
    Existente diferente ⇒ `chave_reutilizada`. FK sem atendimento ⇒ 422 no campo."""
    try:
        with conn.transaction():
            gravada = conn.execute(_INSERIR_CANDIDATO, _registro(sessao, criterio, ref, c)).fetchone()
    except psycopg.errors.ForeignKeyViolation:
        raise erro_de_validacao((("candidatos.atendimento_id", "atendimento_inexistente"),)) from None
    if gravada is not None:
        return True
    existente = conn.execute(
        "SELECT criterio_versao, posicao, perfil_versao, perfil, escolhido, atendimento_id, recusa FROM ia.candidato"
        " WHERE sessao_id = %s AND chat_ref = %s",
        (sessao, ref),
    ).fetchone()
    if existente is None or not _igual(tuple(existente), c, criterio):
        raise ErroApi("chave_reutilizada", campo="candidatos")
    return False


def gravar_candidatos(ctx: ContextoApi, sessao_id: str, corpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    sessao = uuid_do_caminho(sessao_id, "id")
    dados = validar(Candidatos, corpo)
    rejeitar_documento("criterio_versao", dados.criterio_versao)
    for i, candidato in enumerate(dados.candidatos):
        for nome, valor in candidato.perfil.items():
            if isinstance(valor, str):
                rejeitar_pii(f"candidatos.{i}.perfil.{nome}", valor)
    chave = ctx.settings.chat_ref_chave.get_secret_value().encode()
    gravados = repetidos = 0
    with ctx.conexao() as conn, conn.transaction():
        for candidato in dados.candidatos:
            if _gravar_um(conn, sessao, dados.criterio_versao, chat_ref(chave, candidato.chat_id), candidato):
                gravados += 1
            else:
                repetidos += 1
    return (201 if gravados else 200), {"gravados": gravados, "repetidos": repetidos}
