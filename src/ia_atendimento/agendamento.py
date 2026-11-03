"""`POST /agendamentos` (B1.5, contrato 08 §5.5; diálogo «Vou fazer depois» do n8n): reserva um atendimento `agendamento` e a linha
`pendente`.

- **Chave** `agendar:{chat_id}:{sufixo16}` com `sufixo16 = sha256(datetime_utc)[:16]`, `datetime_utc` = `AAAA-MM-DDTHH:MM:SSZ` (segundos
  inteiros). O n8n
  a calcula antes do POST (precisa dela para o espelho `agendado`); o servidor RECALCULA e recusa a divergente (`ChaveIncoerente`). A
  `msg_chave` do
  agendamento é `cg:{chat_id}:{sufixo16}`, a forma que o `agendamento_forma_check` da 0001 aceita; o `texto_hash` é HMAC do texto mascarado.
- **A hora vem do extrator determinístico** (B5.7a), nunca do modelo. Em v1 só vale UMA hora explícita dentro da janela: zero ou mais de um
  candidato válido ⇒ `agendado:false, motivo:"sem_hora"` e nada é gravado (ambíguo é da proposta/confirmação, B5.7c).
- O atendimento nasce `reservado` por `estado_pausa.abrir_agendado` (`gatilho='agendamento'`, `retoma_em = dispara_em`,
  `lease_ate = retoma_em + agenda_folga_min`, o CHECK exige `lease_ate >= retoma_em`) e **não toca o chat**. A reserva grava o passo
  `agendamento` (`proposto`); o job `retomar` é enfileirado pela API NA MESMA transação (`api/agendamentos.py`). Quem confirma e quem
  dispara é a B5.7b/c (`agenda_estado`, `agenda_jobs`).
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, Final

import psycopg
from pydantic import BaseModel, ConfigDict, StringConstraints

from ia_atendimento.agenda_estado import passo_de_agendamento
from ia_atendimento.agenda_extrator import VERSAO as EXTRATOR_VERSAO
from ia_atendimento.agenda_extrator import ConfigAgenda, extrair
from ia_atendimento.calendario import FUSO, limites_do_dia, validar_calendario_bloqueio
from ia_atendimento.estado import (
    TOLERANCIA_RELOGIO,
    ConflitoIdempotencia,
    EntradaInvalida,
    EstadoErro,
    Hex24,
    Versoes,
    executar_traduzindo,
    idempotency_key,
    resolver_modo,
)
from ia_atendimento.estado_pausa import abrir_agendado
from ia_atendimento.mascara import mascarar
from ia_atendimento.tipos import DataHora

PREFIXO_TEXTO: Final = b"texto/v1\n"
DISPARADO_POR: Final = "dialogo_agendar"


class ChaveIncoerente(EstadoErro):
    """`chave` do corpo diferente de `agendar:{chat_id}:{sufixo16}` recalculada de `chat_id` e `datetime_post` (HTTP 422)."""


class EntradaAgendamento(BaseModel):
    """Corpo de `POST /agendamentos`. Sem CPF, nome nem e-mail; `chat_number` vai ao cofre (fora do hash e do banco do atendimento)."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    pessoa_id: uuid.UUID
    chat_id: Hex24
    phone_id: Hex24
    chat_number: Annotated[str, StringConstraints(pattern=r"^[0-9]{10,15}$")] | None = None
    clt_job_id: uuid.UUID  # obrigatório: preserva a associação ao job (F13)
    texto_mensagem: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    datetime_post: DataHora
    chave: Annotated[str, StringConstraints(pattern=r"^agendar:[0-9a-f]{24}:[0-9a-f]{16}$")]
    retoma_fase: Annotated[str, StringConstraints(pattern=r"^E([2-6]|8)$")]
    ultimo_cliente_em: DataHora | None = None


def datetime_utc_texto(instante: datetime) -> str:
    """`AAAA-MM-DDTHH:MM:SSZ` em UTC, segundos inteiros (a fração é descartada)."""
    return instante.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sufixo16(instante: datetime) -> str:
    return hashlib.sha256(datetime_utc_texto(instante).encode("utf-8")).hexdigest()[:16]


def chave_logica_do_agendamento(chat_id: str, datetime_post: datetime) -> str:
    return f"agendar:{chat_id}:{sufixo16(datetime_post)}"


def msg_chave_do_agendamento(chat_id: str, datetime_post: datetime) -> str:
    return f"cg:{chat_id}:{sufixo16(datetime_post)}"


def texto_hash(texto: str, chave_h16: bytes) -> str:
    """HMAC (chave `h16`) do texto MASCARADO: o mesmo texto repetido dá o mesmo hash; outro texto na mesma chave é `chave_reutilizada`."""
    return hmac.new(chave_h16, PREFIXO_TEXTO + mascarar(texto).encode("utf-8"), hashlib.sha256).hexdigest()


def validar_chave(entrada: EntradaAgendamento) -> str:
    """A `chave_logica` recalculada; diferente da enviada ⇒ `ChaveIncoerente`."""
    esperada = chave_logica_do_agendamento(entrada.chat_id, entrada.datetime_post)
    if not hmac.compare_digest(esperada, entrada.chave):
        raise ChaveIncoerente("chave diferente de agendar:{chat_id}:{sufixo16} recalculada de chat_id e datetime_post")
    return esperada


def validar_instantes(entrada: EntradaAgendamento, agora: datetime) -> None:
    """`datetime_post` e `ultimo_cliente_em` mais de 5 min à frente do relógio são recusados (nomes de campo, nunca o valor)."""
    futuros = tuple(
        (campo, "no_futuro")
        for campo, valor in (("datetime_post", entrada.datetime_post), ("ultimo_cliente_em", entrada.ultimo_cliente_em))
        if valor is not None and valor > agora + TOLERANCIA_RELOGIO
    )
    if futuros:
        raise EntradaInvalida("instante no futuro", campos=futuros)


def config_da_agenda(config: dict[str, Any]) -> ConfigAgenda:
    """`ConfigAgenda` das chaves `agenda_*` e do `calendario_bloqueio` vigentes (o DDL e o registro já os validaram)."""
    feriados, janelas = validar_calendario_bloqueio(config["calendario_bloqueio"])
    return ConfigAgenda.das_chaves(
        agenda_janela=config["agenda_janela"],
        agenda_periodos=config["agenda_periodos"],
        agenda_teto_horas=config["agenda_teto_horas"],
        feriados=feriados,
        bloqueios=tuple((j.de, j.ate) for j in janelas),
    )


@dataclass(frozen=True)
class Agendado:
    atendimento_id: uuid.UUID
    agendamento_id: uuid.UUID
    estado: str
    dispara_em: datetime
    tipo_extracao: str
    confianca: str
    repetido: bool = False

    def corpo(self) -> dict[str, Any]:
        corpo: dict[str, Any] = {
            "atendimento_id": str(self.atendimento_id), "agendamento_id": str(self.agendamento_id), "estado": self.estado,
            "dispara_em": self.dispara_em.astimezone(FUSO).isoformat(), "tipo_extracao": self.tipo_extracao, "confianca": self.confianca,
        }  # fmt: skip
        return {**corpo, "repetido": True} if self.repetido else corpo


@dataclass(frozen=True)
class SemHora:
    """Nenhum horário utilizável (ausente, ambíguo ou fora da janela): 200 `{agendado:false, motivo:"sem_hora"}`, nada gravado."""

    motivo: str = "sem_hora"


def horario_unico(texto: str, agora: datetime, ultima_msg_cliente_em: datetime, config: ConfigAgenda) -> tuple[datetime, str] | SemHora:
    """O único candidato válido do extrator e sua confiança; qualquer outro caso é `SemHora`."""
    resultado = extrair(texto, agora, ultima_msg_cliente_em, config)
    validos = resultado.validos
    if len(validos) != 1:
        return SemHora()
    return validos[0].quando, validos[0].confianca


def procurar_replay(conn: psycopg.Connection, chave_logica: str, hash_do_texto: str) -> Agendado | None:
    """Agendamento já gravado para a chave: o MESMO texto ⇒ `Agendado(repetido=True)` com o gravado; outro ⇒ `ConflitoIdempotencia`."""
    linha = conn.execute(
        "SELECT atendimento_id, agendamento_id, estado, dispara_em, tipo_extracao, confianca, texto_hash"
        " FROM ia.agendamento WHERE idem_key = %s",
        (idempotency_key(chave_logica),),
    ).fetchone()
    if linha is None:
        return None
    if not hmac.compare_digest(linha[6], hash_do_texto):
        raise ConflitoIdempotencia("mesma chave de agendamento com outro texto")
    return Agendado(*linha[:6], repetido=True)


def agendamentos_hoje(conn: psycopg.Connection, agora: datetime) -> int:
    inicio, fim = limites_do_dia(agora)
    linha = conn.execute("SELECT count(*) FROM ia.agendamento WHERE pedido_em >= %s AND pedido_em < %s", (inicio, fim)).fetchone()
    return int(linha[0]) if linha else 0


def chat_ocupado(conn: psycopg.Connection, chat_id: str) -> bool:
    return conn.execute("SELECT 1 FROM ia.atendimento WHERE chat_id = %s AND estado <> 'encerrado'", (chat_id,)).fetchone() is not None


_INSERIR_AGENDAMENTO: Final = """
INSERT INTO ia.agendamento (atendimento_id, pessoa_id, chat_id, entrada, seq, pedido_em, msg_chave, texto_hash, retoma_fase,
horario_extraido,
  tipo_extracao, extrator_versao, confianca, dispara_em, chave_logica, idem_key)
VALUES (%(atd)s, %(pessoa)s, %(chat)s, 'dialogo_agendar', 1, %(agora)s, %(msg_chave)s, %(texto_hash)s, %(retoma_fase)s, %(quando)s,
  'explicita', %(extrator)s, %(confianca)s, %(quando)s, %(chave)s, %(idem)s)
RETURNING agendamento_id, estado
"""


def reservar(
    conn: psycopg.Connection,
    *,
    origem: str,
    entrada: EntradaAgendamento,
    chave_logica: str,
    hash_do_texto: str,
    quando: datetime,
    confianca: str,
    versoes: Versoes,
    modo_global: str,
    chats_teste: list[str],
    folga_min: int,
    agora: datetime,
) -> Agendado:
    """Cria o atendimento `reservado` de agendamento (`estado_pausa.abrir_agendado`), a linha `pendente` e o passo `agendamento` NA
    TRANSAÇÃO do chamador (savepoint próprio). Chat ocupado ⇒ `ChatOcupado`."""
    modo = resolver_modo(chat_id=entrada.chat_id, modo_global=modo_global, chats_teste=chats_teste)
    with conn.transaction():
        atendimento = abrir_agendado(
            conn, origem=origem, chave_logica=chave_logica, disparado_por=DISPARADO_POR, pessoa_id=entrada.pessoa_id,
            chat_id=entrada.chat_id, phone_id=entrada.phone_id, clt_job_id=entrada.clt_job_id, versoes=versoes, modo=modo,
            retoma_em=quando, ultimo_cliente_em=entrada.ultimo_cliente_em or entrada.datetime_post, agora=agora, folga_min=folga_min,
        )  # fmt: skip
        agendamento = executar_traduzindo(
            conn,
            _INSERIR_AGENDAMENTO,
            {
                "atd": atendimento.atendimento_id, "pessoa": entrada.pessoa_id, "chat": entrada.chat_id, "agora": agora,
                "msg_chave": msg_chave_do_agendamento(entrada.chat_id, entrada.datetime_post), "texto_hash": hash_do_texto,
                "retoma_fase": entrada.retoma_fase, "quando": quando, "extrator": EXTRATOR_VERSAO, "confianca": confianca,
                "chave": chave_logica, "idem": idempotency_key(chave_logica),
            },
        )  # fmt: skip
        passo_de_agendamento(conn, atendimento.atendimento_id, agendamento[0], "proposto")
    return Agendado(atendimento.atendimento_id, agendamento[0], agendamento[1], quando, "explicita", confianca)
