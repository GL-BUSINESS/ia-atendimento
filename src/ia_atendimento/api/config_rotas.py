"""`GET /config`, `GET /config/{nome}` e `PUT /config/{nome}` (contrato 08 §5.6, §6).

`PUT` é `INSERT versao+1` pelo registro (`chave.registrar_config`): perder a corrida (PK, ou `versao_esperada` velha) é 409. O `efeitos`
da resposta tem
UMA chave (`encerrar_por_chave_agendados`, igual ao zod estrito do web). `ia_ativa=false` agenda `encerrar_por_chave` de abertos,
aguardando e PAUSADOS,
escalonado em até 19 min, NA MESMA transação da nova versão; `bloqueio_entrada` não encerra ninguém. `modo=teste` global é recusado;
`chats_teste` só aceita
chat de pessoa de `pessoas_teste` e que nunca teve atendimento `real`/`sombra`. `motivo` passa por `pii_no_texto_livre` e, na LEITURA,
por `mascarar`.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Any, Final
from uuid import UUID

import psycopg
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from ia_atendimento.api.contexto import ContextoApi
from ia_atendimento.api.erros import ErroApi
from ia_atendimento.api.validacao import LoginOuEmail, rejeitar_documento, rejeitar_pii, validar
from ia_atendimento.chave import ConfigCorrida, ConfigInexistente, ModoTesteGlobal, ValorInvalido, VersaoConfig
from ia_atendimento.chave_registro import PADROES, REGISTRO
from ia_atendimento.mascara import mascarar
from ia_atendimento.tipos import contem_documento

JANELA_ENCERRAMENTO_S: Final = 19 * 60  # a parada leve fecha tudo em <= 20 min (folga de 1 min)
MAX_HISTORICO: Final = 50
MASCARADO: Final = "[mascarado]"
_CODIGO: Final = re.compile(r"^[a-z0-9_]{1,40}$")
_DATA: Final = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ORIGENS_QUE_MEXEM_EM_TUDO: Final = frozenset({"ti"})
ORIGENS_LIMITADAS: Final = {"c360_api": frozenset({"ia_ativa", "modo"})}  # `por` = o login do operador no web
ESTADOS_DA_PARADA_LEVE: Final = ("aberto", "aguardando_cliente", "pausado")


class PutConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    valor: Any
    por: LoginOuEmail
    motivo: Annotated[str, StringConstraints(min_length=1, max_length=300)] | None = None
    versao_esperada: Annotated[int, Field(ge=0)] | None = None


def _codigo_publico(ctx: ContextoApi, texto: object) -> object:
    """Motivo de janela na leitura: código `^[a-z0-9_]{1,40}$` sem documento passa; legado de texto livre vira `[mascarado]`."""
    if isinstance(texto, str) and _CODIGO.fullmatch(texto) and not contem_documento(texto):
        return texto
    ctx.metricas.somar("texto_livre_mascarado_na_leitura")
    return MASCARADO


def _valor_publico(ctx: ContextoApi, nome: str, valor: Any) -> Any:
    """Só `calendario_bloqueio` tem texto de operador no `valor`: voltam só as chaves do contrato, e o `motivo` mascarado se preciso."""
    if nome != "calendario_bloqueio" or not isinstance(valor, dict):
        return valor
    janelas = [
        {chave: (_codigo_publico(ctx, j[chave]) if chave == "motivo" else j[chave]) for chave in ("de", "ate", "motivo") if chave in j}
        for j in valor.get("janelas", [])
        if isinstance(j, dict)
    ]
    feriados = [f for f in valor.get("feriados", []) if isinstance(f, str) and _DATA.fullmatch(f)]
    return {"domingos": valor.get("domingos"), "feriados": feriados, "janelas": janelas}


def _item(ctx: ContextoApi, v: VersaoConfig) -> dict[str, Any]:
    motivo = v.motivo
    if motivo is not None and mascarar(motivo) != motivo:  # defesa na leitura (08 §5.4): nunca devolve texto que a máscara mudaria
        ctx.metricas.somar("texto_livre_mascarado_na_leitura")
        motivo = MASCARADO
    return {
        "nome": v.nome, "versao": v.versao, "valor": _valor_publico(ctx, v.nome, v.valor), "publicado_em": _iso(v.publicado_em),
        "publicado_por": MASCARADO if contem_documento(v.publicado_por) else v.publicado_por, "motivo": motivo,
    }  # fmt: skip


def _iso(instante: datetime) -> str:
    return instante.isoformat()


def _vigentes(conn: psycopg.Connection) -> list[VersaoConfig]:
    linhas = conn.execute(
        "SELECT DISTINCT ON (nome) nome, versao, valor, publicado_em, publicado_por, motivo"
        " FROM ia.config_versao ORDER BY nome, versao DESC"
    ).fetchall()
    return [VersaoConfig(*linha) for linha in linhas]


def listar_config(ctx: ContextoApi) -> tuple[int, dict[str, Any]]:
    with ctx.conexao() as conn:
        vigentes = _vigentes(conn)
    return 200, {
        "itens": [_item(ctx, v) for v in vigentes if v.nome in REGISTRO],
        "fora_do_registro": sorted(v.nome for v in vigentes if v.nome not in REGISTRO),
    }


def ler_config(ctx: ContextoApi, nome: str, historico: str | None) -> tuple[int, dict[str, Any]]:
    if nome not in REGISTRO:
        raise ErroApi("config_inexistente", campo="nome")
    quantas = 1
    if historico is not None:
        if not historico.isascii() or not historico.isdigit() or not 1 <= int(historico) <= MAX_HISTORICO:
            raise ErroApi(
                "validacao", campo="historico", detalhe={"campos": [{"campo": "historico", "regra": f"inteiro_de_1_a_{MAX_HISTORICO}"}]}
            )
        quantas = int(historico)
    with ctx.conexao() as conn:
        linhas = conn.execute(
            "SELECT nome, versao, valor, publicado_em, publicado_por, motivo FROM ia.config_versao"
            " WHERE nome = %s ORDER BY versao DESC LIMIT %s",
            (nome, quantas),
        ).fetchall()
    versoes = [VersaoConfig(*linha) for linha in linhas]
    if historico is not None:
        return 200, {"itens": [_item(ctx, v) for v in versoes]}
    if not versoes:  # no registro mas nunca gravada (o boot grava os padrões): vale o padrão, versão 0
        return 200, {"nome": nome, "versao": 0, "valor": PADROES.get(nome), "publicado_em": None, "publicado_por": None, "motivo": None}
    return 200, _item(ctx, versoes[0])


def _conferir_origem(origem: str, nome: str) -> None:
    if origem in ORIGENS_QUE_MEXEM_EM_TUDO or nome in ORIGENS_LIMITADAS.get(origem, frozenset()):
        return
    raise ErroApi("origem_nao_autorizada")


def _conferir_chats_teste(ctx: ContextoApi, conn: psycopg.Connection, chats: list[str]) -> None:
    """08 §5.6: nenhum chat com atendimento anterior `real`/`sombra` (é de cliente) e cada chat de uma pessoa de `pessoas_teste`."""
    cliente = conn.execute(
        "SELECT DISTINCT chat_id FROM ia.atendimento WHERE chat_id = ANY(%s) AND modo IN ('real', 'sombra')", (chats,)
    ).fetchall()
    if cliente:
        raise ErroApi("chat_de_cliente", campo="valor", detalhe={"quantos": len(cliente)})
    sem_pessoa = [c for c in chats if ctx.pessoas_teste.pessoa_do_chat(c) is None]
    if sem_pessoa:
        raise ErroApi("pessoa_fora_de_pessoas_teste", campo="valor", detalhe={"quantos": len(sem_pessoa)})


def _valor_validado(nome: str, valor: Any) -> Any:
    try:
        return REGISTRO[nome].validar(valor)
    except ModoTesteGlobal:
        raise ErroApi("modo_teste_global", campo="valor") from None
    except ValorInvalido as erro:
        regra = (
            erro.regra if mascarar(erro.regra) == erro.regra else "(regra omitida)"
        )  # a regra pode citar o caminho de uma chave do cliente
        raise ErroApi("valor_invalido", campo="valor", detalhe={"regra": regra}) from None
    except (TypeError, ValueError, KeyError, AttributeError):
        raise ErroApi("valor_invalido", campo="valor", detalhe={"regra": "valor_fora_do_tipo"}) from None


def _agendar_encerramentos(ctx: ContextoApi, conn: psycopg.Connection) -> int:
    """Um job `encerrar_por_chave` por atendimento aberto, aguardando ou pausado, escalonado (o 1º já, o último ≤ 19 min). Idempotente por
    atendimento."""
    linhas: list[tuple[UUID, str]] = conn.execute(
        "SELECT atendimento_id, chat_id FROM ia.atendimento WHERE estado = ANY(%s) ORDER BY iniciado_em", (list(ESTADOS_DA_PARADA_LEVE),)
    ).fetchall()
    passo = JANELA_ENCERRAMENTO_S / max(len(linhas), 1)
    agendados = [ctx.enfileirador.encerrar_por_chave(conn, atd, chat, i * passo) for i, (atd, chat) in enumerate(linhas)]
    return sum(agendados)


def gravar_config(ctx: ContextoApi, origem: str, nome: str, corpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if nome not in REGISTRO:
        raise ErroApi("config_inexistente", campo="nome")
    _conferir_origem(origem, nome)
    dados = validar(PutConfig, corpo)
    rejeitar_documento("por", dados.por)
    if dados.motivo is not None:
        rejeitar_pii("motivo", dados.motivo)
    valor = _valor_validado(nome, dados.valor)
    with ctx.conexao() as conn:
        if nome == "chats_teste":
            _conferir_chats_teste(ctx, conn, valor)
        try:
            with conn.transaction():
                nova = ctx.leitor.registrar(conn, nome, valor, dados.por, motivo=dados.motivo, versao_esperada=dados.versao_esperada)
                agendados = _agendar_encerramentos(ctx, conn) if nome == "ia_ativa" and nova.valor is False else 0
        except ConfigCorrida:
            raise ErroApi("config_corrida", campo="versao_esperada" if dados.versao_esperada is not None else None) from None
        except ConfigInexistente:
            raise ErroApi("config_inexistente", campo="nome") from None
        except ValorInvalido:  # o banco (CHECK) ou a regra cruzada recusou
            raise ErroApi("valor_invalido", campo="valor") from None
    return 200, {
        "nome": nova.nome, "versao": nova.versao, "valor": nova.valor, "publicado_em": _iso(nova.publicado_em),
        "efeitos": {"encerrar_por_chave_agendados": agendados},
    }  # fmt: skip
