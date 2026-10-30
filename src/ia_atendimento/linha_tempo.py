"""Linha do tempo do atendimento (B1.2, sp01 T4): passos, mensagens recebidas com dedupe permanente, pendentes e consumo.

- `gravar_passo`: `ordem = max + 1` na mesma transação, sob `SELECT … FOR UPDATE` do atendimento (o `ia_app` pode: tem UPDATE em
  colunas). **Todo passo leva `turno` e `fase`** (só a `anotacao_operador` dispensa, como o CHECK); o envio exige `verif_det`.
- `gravar_mensagem_recebida`: identidade pelo `evento_mensagem` (contrato 08 §5.1); o índice único PARCIAL `passo_msg_chave_uq`
  é global e permanente: o mesmo `msg_chave` com o mesmo `msg_fingerprint` é `Duplicada` (no-op), com outro é `Conflito`.
- `mensagens_pendentes`/`consumir`: pendente = `ordem > ordem_consumida`; `consumir` avança `ordem_consumida`, soma 1 em `turnos`
  **por lote** e 1 em `rodada` (`estado_conversa.contadores.rodada`) num único `UPDATE … WHERE versao = $v` (CAS).
- Tempo de negócio vem do chamador (`agora`); sem ele valem os defaults do banco. Nenhum texto de cliente entra aqui.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, Final, Self

import psycopg
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from ia_atendimento.evento_mensagem import ChavesDeMensagem, EventoMensagem, Identidade, identidade
from ia_atendimento.mascara import mascarar
from ia_atendimento.passos import DadosPasso, MensagemRecebida, texto_passo
from ia_atendimento.scrubber import validar

TIPOS_DE_ENVIO: Final = frozenset({"resposta_enviada", "lembrete"})
TURNO_MAX: Final = 32767  # smallint
FASE_INICIAL: Final = "E0"


class LinhaDoTempoErro(Exception):
    """Base dos erros da linha do tempo. As mensagens nunca citam texto de cliente."""


class PassoSemTurnoOuFase(LinhaDoTempoErro):
    """Passo sem `CtxPasso` (turno e fase): recusado antes do banco (L G6, A1)."""


class EnvioSemVerificacao(LinhaDoTempoErro):
    """`resposta_enviada`/`lembrete` sem `verif_det` (`[]` = limpo é válido; ausente não)."""


class PassoComPii(LinhaDoTempoErro):
    """O texto do passo mudaria sob a máscara de PII (CPF, telefone, e-mail, CEP, UUID, 8+ dígitos ou nome da conversa)."""


class PassoRecusadoPeloBanco(LinhaDoTempoErro):
    """O banco recusou o INSERT (CHECK, unicidade ou FK). Só o NOME da restrição sai: o `DETAIL` do Postgres imprime a linha inteira."""

    def __init__(self, restricao: str | None) -> None:
        self.restricao = restricao
        super().__init__(f"o banco recusou o passo (restrição: {restricao or 'desconhecida'})")


class AtendimentoInexistente(LinhaDoTempoErro):
    pass


class ConflitoDeVersao(LinhaDoTempoErro):
    """CAS perdido em `consumir` (`versao` mudou). Será unificado com o `ConflitoVersao` de `estado.py` na integração com a B1.1."""


class CtxPasso(BaseModel):
    """Onde o passo cai: `turno` = rodada do atendimento (cresce a cada ciclo) e `fase` E0–E10."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)
    turno: Annotated[int, Field(ge=0, le=TURNO_MAX)]
    fase: Annotated[str, StringConstraints(pattern=r"^E([0-9]|10)$")]

    @classmethod
    def criar(cls, **campos: Any) -> Self:
        return validar(cls.__name__, lambda: cls(**campos))


@dataclass(frozen=True)
class Passo:
    ordem: int
    tipo: str
    texto: str


@dataclass(frozen=True)
class Gravada:
    ordem: int
    msg_chave: str


@dataclass(frozen=True)
class Duplicada:
    """Mesma `msg_chave` e mesmo fingerprint já gravados: nada foi escrito. `ordem` só vem se a duplicata é deste atendimento (B2:
    o índice é global e permanente, e a ordem de outro atendimento não é assunto de quem chama)."""

    msg_chave: str
    mesmo_atendimento: bool
    ordem: int | None


@dataclass(frozen=True)
class Casada:
    """O gancho `casar` (webhook × RPA, contrato 08 §5.3) achou a mesma mensagem já gravada: nada foi escrito."""

    ordem: int
    msg_chave: str


@dataclass(frozen=True)
class Conflito:
    """Mesma `msg_chave`, outro fingerprint: nada foi escrito; o chamador registra o passo `erro` (peça `receptor`) e alerta."""

    msg_chave: str


Casador = Callable[[psycopg.Connection, uuid.UUID, EventoMensagem, Identidade], int | None]


@dataclass(frozen=True)
class Pendente:
    ordem: int
    msg_tipo: str
    msg_tamanho: int
    msg_chave: str
    origem_evento: str
    fora_de_ordem: bool


def _uma_linha(conn: psycopg.Connection, consulta: str, parametros: tuple[Any, ...]) -> tuple[Any, ...]:
    linha = conn.execute(consulta, parametros).fetchone()
    if linha is None:
        raise LinhaDoTempoErro("consulta que sempre devolve uma linha não devolveu nenhuma")
    return tuple(linha)


def travar_atendimento(conn: psycopg.Connection, atendimento_id: uuid.UUID) -> tuple[str, int]:
    """`SELECT … FOR UPDATE` do atendimento: serializa a `ordem`. Devolve (fase atual, rodada)."""
    linha = conn.execute(
        "SELECT fase, coalesce((estado_conversa #>> '{contadores,rodada}')::int, 0)"
        " FROM ia.atendimento WHERE atendimento_id = %s FOR UPDATE",
        (atendimento_id,),
    ).fetchone()
    if linha is None:
        raise AtendimentoInexistente("atendimento inexistente")
    return linha[0], linha[1]


def _proxima_ordem(conn: psycopg.Connection, atendimento_id: uuid.UUID) -> int:
    return _uma_linha(conn, "SELECT coalesce(max(ordem), 0) + 1 FROM ia.passo WHERE atendimento_id = %s", (atendimento_id,))[0]


def _inserir(
    conn: psycopg.Connection,
    atendimento_id: uuid.UUID,
    ordem: int,
    dados: DadosPasso,
    texto: str,
    extras: dict[str, Any],
    *,
    conflito: str = "",
) -> int | None:
    """INSERT em `ia.passo`; os nomes de coluna vêm das nossas classes e de `extras` (nunca de entrada externa)."""
    colunas = {"atendimento_id": atendimento_id, "ordem": ordem, "tipo": dados.tipo, "texto": texto, **extras}
    restricao: str | None = None
    recusado = False
    try:
        linha = conn.execute(
            f"INSERT INTO ia.passo ({', '.join(colunas)}) VALUES ({', '.join(['%s'] * len(colunas))}) {conflito} RETURNING ordem",  # noqa: S608
            list(colunas.values()),
        ).fetchone()
    except psycopg.errors.IntegrityError as erro:
        restricao, recusado = erro.diag.constraint_name, True
    if recusado:  # fora do `except`: a causa (com o DETAIL e a linha inteira) não fica encadeada
        raise PassoRecusadoPeloBanco(restricao)
    return linha[0] if linha else None


def _exigir_ctx(ctx: CtxPasso | None, dados: DadosPasso) -> None:
    if ctx is None and dados.tipo != "anotacao_operador":
        raise PassoSemTurnoOuFase("todo passo leva turno e fase (só a anotação do operador dispensa)")


def _exigir_texto_sem_pii(texto: str, nomes: Collection[str] | None, dados: DadosPasso) -> None:
    sem_nomes = nomes is None and dados.tipo == "anotacao_operador"  # texto livre de pessoa sem os nomes da conversa: recusa (S1)
    if sem_nomes or mascarar(texto, nomes or ()) != texto:
        raise PassoComPii("o texto do passo contém dado que a máscara trocaria (ou os nomes da conversa não foram informados)")


def gravar_passo(
    conn: psycopg.Connection,
    atendimento_id: uuid.UUID,
    *,
    ctx: CtxPasso | None,
    dados: DadosPasso,
    nomes: Collection[str] | None = None,
) -> Passo:
    """Grava um passo; a hora (`ocorrido_em`) é a do BANCO. `nomes` = nome do cliente e variantes (S1): valida o texto livre do operador."""
    _exigir_ctx(ctx, dados)
    colunas = dados.colunas()
    if dados.tipo in TIPOS_DE_ENVIO and colunas.get("verif_det") is None:
        raise EnvioSemVerificacao("envio sem verif_det (use [] para «limpo»)")
    texto = texto_passo(dados)
    _exigir_texto_sem_pii(texto, nomes, dados)
    extras: dict[str, Any] = dict(colunas)
    if ctx is not None:
        extras.update(turno=ctx.turno, fase=ctx.fase)
    with conn.transaction():
        travar_atendimento(conn, atendimento_id)
        ordem = _proxima_ordem(conn, atendimento_id)
        _inserir(conn, atendimento_id, ordem, dados, texto, extras)
    return Passo(ordem, dados.tipo, texto)


# --- mensagens recebidas ---------------------------------------------------------------------------------------------------------


def _existente(conn: psycopg.Connection, ident: Identidade, rpa_id: str | None) -> tuple[uuid.UUID, int, str] | None:
    """Passo `mensagem_recebida` com a mesma `msg_chave` (ou, na reconciliação, com o `_id` do RPA já anexado)."""
    linha = conn.execute(
        "SELECT atendimento_id, ordem, msg_fingerprint FROM ia.passo WHERE tipo = 'mensagem_recebida'"
        " AND (msg_chave = %s OR (%s::text IS NOT NULL AND msg_chave_rpa = %s)) LIMIT 1",
        (ident.msg_chave, rpa_id, rpa_id),
    ).fetchone()
    return (linha[0], linha[1], linha[2]) if linha else None


def _comparar(existente: tuple[uuid.UUID, int, str], ident: Identidade, atendimento_id: uuid.UUID) -> Duplicada | Conflito:
    atendimento, ordem, fingerprint = existente
    if fingerprint != ident.msg_fingerprint:
        return Conflito(ident.msg_chave)
    mesmo = atendimento == atendimento_id
    return Duplicada(ident.msg_chave, mesmo, ordem if mesmo else None)


def gravar_mensagem_recebida(
    conn: psycopg.Connection,
    atendimento_id: uuid.UUID,
    *,
    evento: EventoMensagem,
    chaves: ChavesDeMensagem,
    recebido_em: datetime | None = None,
    casar: Casador | None = None,
) -> Gravada | Duplicada | Casada | Conflito:
    """Grava a mensagem como passo `mensagem_recebida` (só códigos e tamanho: o texto vai, mascarado e cifrado, a `conversa`).

    `turno` = rodada + 1 (a mensagem pertence ao próximo turno) e `fase` = a atual. Dedupe permanente por `msg_chave` (ver
    `evento_mensagem.identidade`; `recebido_em` só pesa quando o evento não traz hora nem id). Sem esta etapa o RPA e o webhook do MESMO
    evento viram dois passos: `casar` é o gancho do casamento (contrato 08 §5.3 passo 7, B1.5); roda DENTRO do `FOR UPDATE` do
    atendimento, depois da busca exata e antes do INSERT, e devolve a `ordem` do passo já gravado (ou `None`)."""
    ident = identidade(evento, chaves, recebido_em=recebido_em or datetime.now(UTC))
    dados = MensagemRecebida(
        msg_chave=ident.msg_chave,
        msg_fingerprint=ident.msg_fingerprint,
        msg_tipo=evento.tipo,
        msg_tamanho=ident.msg_tamanho,
        origem_evento=evento.origem_evento,
        msg_enviada_em=evento.datetime_post,
        msg_chave_rpa=None,
    )
    with conn.transaction():
        fase, rodada = travar_atendimento(conn, atendimento_id)
        anterior = _existente(conn, ident, evento.rpa_id)
        if anterior is not None:
            return _comparar(anterior, ident, atendimento_id)
        casada = casar(conn, atendimento_id, evento, ident) if casar is not None else None
        if casada is not None:
            return Casada(casada, ident.msg_chave)
        extras: dict[str, Any] = {**dados.colunas(), "turno": rodada + 1, "fase": fase}
        ordem = _inserir(
            conn,
            atendimento_id,
            _proxima_ordem(conn, atendimento_id),
            dados,
            texto_passo(dados),
            extras,
            conflito="ON CONFLICT (msg_chave) WHERE tipo = 'mensagem_recebida' DO NOTHING",
        )
        if ordem is None:  # corrida: outro atendimento gravou a mesma chave entre o SELECT e o INSERT
            concorrente = _existente(conn, ident, evento.rpa_id)
            if concorrente is None:
                raise LinhaDoTempoErro("INSERT não gravou e a chave não existe: estado impossível")
            return _comparar(concorrente, ident, atendimento_id)
        return Gravada(ordem, ident.msg_chave)


def mensagens_pendentes(conn: psycopg.Connection, atendimento_id: uuid.UUID) -> list[Pendente]:
    """Mensagens com `ordem > ordem_consumida`, em ordem. Sem texto (o texto mora cifrado na `conversa`)."""
    linhas = conn.execute(
        "SELECT p.ordem, p.msg_tipo, p.msg_tamanho, p.msg_chave, p.origem_evento, p.fora_de_ordem FROM ia.passo p"
        " JOIN ia.atendimento a USING (atendimento_id)"
        " WHERE p.atendimento_id = %s AND p.tipo = 'mensagem_recebida' AND p.ordem > a.ordem_consumida ORDER BY p.ordem",
        (atendimento_id,),
    ).fetchall()
    return [Pendente(*linha) for linha in linhas]


def consumir(conn: psycopg.Connection, atendimento_id: uuid.UUID, *, versao: int, ate_ordem: int) -> int:
    """Consome as pendentes até `ate_ordem` (inclusive): um turno por lote. CAS por `versao`; devolve a versão nova.

    A versão é conferida PRIMEIRO, sob o lock: quem perde a corrida recebe `ConflitoDeVersao` (e repete o turno), não `ValueError`."""
    with conn.transaction():
        travar_atendimento(conn, atendimento_id)
        atual, consumida, ultima = _uma_linha(
            conn,
            "SELECT a.versao, a.ordem_consumida, (SELECT max(p.ordem) FROM ia.passo p WHERE p.atendimento_id = a.atendimento_id"
            " AND p.tipo = 'mensagem_recebida') FROM ia.atendimento a WHERE a.atendimento_id = %s",
            (atendimento_id,),
        )
        if atual != versao:
            raise ConflitoDeVersao("a versão do atendimento mudou (CAS perdido)")
        eh_mensagem = conn.execute(
            "SELECT 1 FROM ia.passo WHERE atendimento_id = %s AND ordem = %s AND tipo = 'mensagem_recebida'", (atendimento_id, ate_ordem)
        ).fetchone()
        if ate_ordem <= consumida or ultima is None or ate_ordem > ultima or eh_mensagem is None:
            raise ValueError("ate_ordem deve ser uma mensagem recebida, posterior ao que já foi consumido")
        atualizada = conn.execute(
            "UPDATE ia.atendimento SET ordem_consumida = %s, turnos = turnos + 1, versao = versao + 1, atualizado_em = now(),"
            " estado_conversa = jsonb_set(estado_conversa, '{contadores}', coalesce(estado_conversa -> 'contadores', '{}'::jsonb)"
            " || jsonb_build_object('rodada', coalesce((estado_conversa #>> '{contadores,rodada}')::int, 0) + 1))"
            " WHERE atendimento_id = %s AND versao = %s RETURNING versao",
            (ate_ordem, atendimento_id, versao),
        ).fetchone()
    if atualizada is None:
        raise ConflitoDeVersao("a versão do atendimento mudou (CAS perdido)")
    return atualizada[0]
