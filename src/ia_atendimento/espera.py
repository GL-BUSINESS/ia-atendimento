"""Espera do cliente: limites da faixa do atendimento e o lease de `aguardando_cliente` (B1.6a; DECISOES-B1.5 pendência 1, R2 da B1.1).

- **Limites da faixa** = a faixa do atendimento na versão de `faixas_esforco` vigente em `iniciado_em` (`chave.config_em`): trocar a config
  não muda atendimento em curso. Nunca acima do teto global (2 lembretes, 7 dias, 3 contrapropostas, R$ 3, 10 agendamentos).
- **Lease de espera** = até o encerramento por vácuo + folga, seguindo os lembretes (`lembretes_intervalos_min`) adiados para a próxima
  janela de mensagem do calendário vigente (`estado.lease_de_espera`). Sem lembrete na faixa (`lembretes_max=0`): o vácuo encerra no
  primeiro intervalo (4 h) e o lease cobre até ali + folga. O alarme do lembrete não leva lock do chat: o reaper de lease só vê `lease_ate`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final

import psycopg

from ia_atendimento import estado
from ia_atendimento.calendario import carregar_calendario
from ia_atendimento.chave import LeitorConfig, config_em
from ia_atendimento.estado import FOLGA_ESPERA_MIN
from ia_atendimento.estado_erros import AtendimentoInexistente
from ia_atendimento.relogio import Relogio

TETO_LEMBRETES: Final = 2
TETO_DIAS: Final = 7
TETO_CONTRAPROPOSTAS: Final = 3
TETO_CUSTO_BRL: Final = Decimal(3)
TETO_AGENDAMENTOS: Final = 10


@dataclass(frozen=True)
class Limites:
    lembretes_max: int
    lembrete_pago_max: int
    dias_max: int
    contrapropostas_max: int
    custo_max_brl: Decimal
    agendamentos_max: int


def _do_atendimento(conn: psycopg.Connection, atendimento_id: uuid.UUID) -> tuple[str, datetime]:
    linha = conn.execute("SELECT faixa_esforco, iniciado_em FROM ia.atendimento WHERE atendimento_id = %s", (atendimento_id,)).fetchone()
    if linha is None:
        raise AtendimentoInexistente("atendimento inexistente")
    return linha[0], linha[1]


def limites_de(faixas_esforco: dict, faixa: str) -> Limites:
    f = faixas_esforco["faixas"][faixa]
    lembretes = min(TETO_LEMBRETES, int(f["lembretes_max"]))
    return Limites(
        lembretes_max=lembretes,
        lembrete_pago_max=min(lembretes, int(f["lembrete_pago_max"])),
        dias_max=min(TETO_DIAS, int(f["dias_max"])),
        contrapropostas_max=min(TETO_CONTRAPROPOSTAS, int(f["contrapropostas_max"])),
        custo_max_brl=min(TETO_CUSTO_BRL, Decimal(str(f["custo_max_brl"]))),
        agendamentos_max=min(TETO_AGENDAMENTOS, int(f["agendamentos_max"])),
    )


def limites_da_faixa(conn: psycopg.Connection, atendimento_id: uuid.UUID) -> Limites:
    faixa, iniciado_em = _do_atendimento(conn, atendimento_id)
    return limites_de(config_em(conn, "faixas_esforco", iniciado_em), faixa)


def lease_de_espera_do_atendimento(conn: psycopg.Connection, atendimento_id: uuid.UUID, agora: datetime, leitor: LeitorConfig) -> datetime:
    lembretes_max = limites_da_faixa(conn, atendimento_id).lembretes_max
    intervalos = list(leitor.valor(conn, "lembretes_intervalos_min"))
    if lembretes_max == 0:
        return agora + timedelta(minutes=intervalos[0] + FOLGA_ESPERA_MIN)
    calendario = carregar_calendario(leitor.valor(conn, "janela_mensagem"), leitor.valor(conn, "calendario_bloqueio"))
    return estado.lease_de_espera(agora, intervalos_min=intervalos, proxima_janela=calendario.proxima_janela, lembretes_max=lembretes_max)


def aguardar_cliente_com_espera(
    conn: psycopg.Connection, atendimento_id: uuid.UUID, versao: int, *, relogio: Relogio, leitor: LeitorConfig
) -> int:
    """`aberto → aguardando_cliente` com o lease de espera calculado (o ponto de chamada que faltava). Devolve a versão nova."""
    agora = relogio.agora()
    lease = lease_de_espera_do_atendimento(conn, atendimento_id, agora, leitor)
    return estado.aguardar_cliente(conn, atendimento_id, versao, relogio=relogio.agora, lease_ate=lease)
