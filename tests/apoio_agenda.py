"""Apoio dos testes da pausa combinada e dos jobs da agenda (B5.7b): atendimentos pausados/agendados pelas transições de verdade e linhas de
`ia.agendamento` por SQL (a criação do caso (a) é da B5.7c). Tudo sintético, sem PII.
"""

from __future__ import annotations

import itertools
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import psycopg

from ia_atendimento import agenda_estado as ae
from ia_atendimento import estado
from ia_atendimento.estado import Versoes
from ia_atendimento.estado_conversa import EstadoConversa, gravar_estado_conversa
from ia_atendimento.jobs import Volta
from tests.estado_apoio import entrada

_SEQ = itertools.count(1)
FOLGA_MIN = 30


@dataclass
class Caso:
    """Um atendimento à espera da volta e o agendamento `confirmado` dele."""

    atendimento_id: uuid.UUID
    agendamento_id: uuid.UUID
    chat_id: str
    dispara_em: datetime


@dataclass
class Voltas:
    """Espião do serviço `retomar_atendimento` (a volta é da B5.7c): guarda cada `Volta` recebida e devolve o desfecho pedido."""

    recebidas: list[Volta] = field(default_factory=list)
    desfecho: str | None = None
    erro: Exception | None = None

    async def __call__(self, volta: Volta) -> str | None:
        self.recebidas.append(volta)
        if self.erro is not None:
            raise self.erro
        return self.desfecho

    @property
    def ids(self) -> list[uuid.UUID]:
        return [v.agendamento_id for v in self.recebidas]


def novo_aberto(conn: psycopg.Connection, relogio: Any, versoes: Versoes, *, fase: str = "E3") -> tuple[uuid.UUID, int, str]:
    """Atendimento `aberto` (de verdade: `abrir` + `iniciar` + fase) num chat novo. `relogio` é o callable que as transições esperam."""
    n = next(_SEQ)
    chat = f"{n:024x}"
    pessoa = str(uuid.uuid4())
    resultado = estado.abrir(
        conn,
        origem="n8n_braco",
        entrada=entrada(chave_logica=f"venda:{n:032x}", chat_id=chat, pessoa_id=pessoa),
        versoes=versoes,
        modo_global="duble",
        chats_teste=frozenset(),
        faixa_esforco="media",
        comissao_esperada_brl=None,
        relogio=relogio,
    )
    v = estado.iniciar(
        conn, resultado.atendimento_id, resultado.versao, chatbot_antes="desligado", chatbot_estado="desligado_pela_ia", relogio=relogio
    )
    v = gravar_estado_conversa(conn, resultado.atendimento_id, v, EstadoConversa(fase=fase), relogio=relogio)
    return resultado.atendimento_id, v, chat


def novo_agendado(
    conn: psycopg.Connection, agora: datetime, versoes: Versoes, *, retoma_em: datetime, folga_min: int = FOLGA_MIN
) -> tuple[uuid.UUID, int, str]:
    """Caso (b): `reservado` de vida longa por `abrir_agendado`. Devolve (atendimento, versao, chat)."""
    n = next(_SEQ)
    chat = f"{n:024x}"
    resultado = estado.abrir_agendado(
        conn,
        origem="n8n_braco",
        chave_logica=f"agendar:{chat}:{n:016x}",
        disparado_por="dialogo_agendar",
        pessoa_id=uuid.uuid4(),
        chat_id=chat,
        phone_id="89abcdef0123456789abcdef",
        clt_job_id=uuid.uuid4(),
        versoes=versoes,
        modo="duble",
        retoma_em=retoma_em,
        ultimo_cliente_em=agora,
        agora=agora,
        folga_min=folga_min,
    )
    return resultado.atendimento_id, resultado.versao, chat


def inserir_agendamento(
    conn: psycopg.Connection,
    atendimento_id: uuid.UUID,
    *,
    entrada_do_pedido: str,
    dispara_em: datetime,
    pedido_em: datetime,
    retoma_fase: str | None = "E8",
    seq: int = 1,
) -> uuid.UUID:
    """Linha `pendente` do agendamento por SQL, coerente com o CHECK (`msg_chave` e `chave_logica` na forma do contrato 08 §5.5)."""
    pessoa, chat = conn.execute("SELECT pessoa_id, chat_id FROM ia.atendimento WHERE atendimento_id = %s", (atendimento_id,)).fetchone()
    sufixo = uuid.uuid4().hex[:16]
    chave = f"agendar:{chat}:{sufixo}"
    linha = conn.execute(
        "INSERT INTO ia.agendamento (atendimento_id, pessoa_id, chat_id, entrada, seq, pedido_em, msg_chave, texto_hash, retoma_fase,"
        " horario_extraido, tipo_extracao, extrator_versao, confianca, dispara_em, chave_logica, idem_key)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'explicita', '1', 'alta', %s, %s, encode(sha256(convert_to(%s, 'UTF8')), 'hex'))"
        " RETURNING agendamento_id",
        (atendimento_id, pessoa, chat, entrada_do_pedido, seq, pedido_em, f"cg:{chat}:{sufixo}", "a" * 64, retoma_fase, dispara_em,
         dispara_em, chave, chave),
    ).fetchone()  # fmt: skip
    return linha[0]


def pausado_confirmado(conn: psycopg.Connection, relogio: Any, versoes: Versoes, *, dispara_em: datetime, fase: str = "E3") -> Caso:
    """Caso (a) completo: `aberto` → `pausar` → agendamento `pausa_ia` → `confirmar` (cliente)."""
    atendimento_id, versao, chat = novo_aberto(conn, relogio, versoes, fase=fase)
    estado.pausar(conn, atendimento_id, versao, retoma_em=dispara_em, retoma_fase=fase, relogio=relogio)
    agendamento_id = inserir_agendamento(
        conn, atendimento_id, entrada_do_pedido="pausa_ia", dispara_em=dispara_em, pedido_em=relogio(), retoma_fase=fase
    )
    ae.confirmar(conn, agendamento_id, 1, origem="cliente", agora=relogio())
    return Caso(atendimento_id, agendamento_id, chat, dispara_em)


def agendado_confirmado(conn: psycopg.Connection, relogio: Any, versoes: Versoes, *, dispara_em: datetime) -> Caso:
    """Caso (b) completo: `abrir_agendado` → agendamento `dialogo_agendar` → `confirmar`."""
    agora = relogio()
    atendimento_id, _versao, chat = novo_agendado(conn, agora, versoes, retoma_em=dispara_em)
    agendamento_id = inserir_agendamento(conn, atendimento_id, entrada_do_pedido="dialogo_agendar", dispara_em=dispara_em, pedido_em=agora)
    ae.confirmar(conn, agendamento_id, 1, origem="cliente", agora=agora)
    return Caso(atendimento_id, agendamento_id, chat, dispara_em)


def estado_do_atendimento(conn: psycopg.Connection, atendimento_id: uuid.UUID) -> tuple[str, int, timedelta | None]:
    estado_, versao, lease = conn.execute(
        "SELECT estado, versao, lease_ate - retoma_em FROM ia.atendimento WHERE atendimento_id = %s", (atendimento_id,)
    ).fetchone()
    return estado_, versao, lease
