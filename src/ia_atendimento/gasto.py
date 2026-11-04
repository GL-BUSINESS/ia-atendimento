"""Gasto e teto financeiro (contrato 08 §9, R1-14): a fonte canônica é **Σ `passo.custo_brl`**.

- **Competência:** dia `[00:00, 24:00)` e mês civil de America/Sao_Paulo, convertidos a UTC no código (`calendario.limites_*`); a soma é
  por `passo.ocorrido_em` (`idx_passo_ocorrido`). Uma conversa que atravessa a meia-noite conta cada passo no seu dia.
- **Todos os modos contam** (real, teste, duble e sombra: a F3 em `duble` também gasta dinheiro).
- **Sem dupla contagem:** `ferramenta_chamada.custo_brl` não é somada (o passo `chamada_ferramenta` carrega a cópia) e
  `atendimento.custo_modelo_brl`/`custo_midia_brl` são derivados, só do disjuntor por atendimento.
- **Custo ausente:** passo com tokens e `custo_brl` nulo, ou decisão do modelo sem `usage` (tudo nulo), conta em `custo_ausente`: nunca se
  soma zero em silêncio; quem lê alerta crítico.
- **Gasto não calculável** ⇒ `GastoIndisponivel`: a entrada responde `503 nao_pronto` e o `turno` não chama o modelo (B1.6b).
- **Níveis** (`nivel_do_gasto`): < 80 % normal; 80 % amarelo; 100 % crítico (entrada nova recusada, os abertos concluem); acima de 125 %
  (folga fixa) o turno repassa sem chamar o modelo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Final, Literal

import psycopg

from ia_atendimento.calendario import limites_do_dia, limites_do_mes
from ia_atendimento.relogio import Relogio

if TYPE_CHECKING:
    from ia_atendimento.chave import LeitorConfig

__all__ = [
    "AvaliacaoGasto",
    "GastoIndisponivel",
    "MedidorGasto",
    "Nivel",
    "avaliar_gasto",
    "custo_ausente_dia",
    "gasto_dia",
    "gasto_mes",
    "nivel_do_gasto",
]

TTL_GASTO_S: Final = 30.0
AMARELO: Final = Decimal("0.80")
CRITICO: Final = Decimal("1.00")
REPASSAR: Final = Decimal("1.25")
Nivel = Literal["normal", "amarelo", "critico", "repassar"]
_ORDEM: Final[dict[str, int]] = {"normal": 0, "amarelo": 1, "critico": 2, "repassar": 3}

_SQL_SOMA: Final = "SELECT coalesce(sum(custo_brl), 0) FROM ia.passo WHERE ocorrido_em >= %s AND ocorrido_em < %s"
_SQL_AUSENTE: Final = """
SELECT count(*) FROM ia.passo WHERE ocorrido_em >= %s AND ocorrido_em < %s AND custo_brl IS NULL
  AND (tokens_entrada IS NOT NULL OR tokens_saida IS NOT NULL OR (tipo = 'decisao' AND motor = 'modelo'))
"""


class GastoIndisponivel(RuntimeError):
    """A soma do gasto falhou: ninguém decide teto com zero. A entrada responde `503 nao_pronto`; o turno não chama o modelo."""

    codigo = "nao_pronto"


def _somar_custos(conn: psycopg.Connection, inicio: datetime, fim: datetime) -> Decimal:
    linha = conn.execute(_SQL_SOMA, (inicio, fim)).fetchone()
    return Decimal(linha[0])


def _gasto(conn: psycopg.Connection, inicio: datetime, fim: datetime) -> Decimal:
    try:
        return _somar_custos(conn, inicio, fim)
    except psycopg.Error as erro:
        raise GastoIndisponivel(f"soma do gasto falhou ({type(erro).__name__})") from None


def gasto_dia(conn: psycopg.Connection, agora: datetime) -> Decimal:
    return _gasto(conn, *limites_do_dia(agora))


def gasto_mes(conn: psycopg.Connection, agora: datetime) -> Decimal:
    return _gasto(conn, *limites_do_mes(agora))


def custo_ausente_dia(conn: psycopg.Connection, agora: datetime) -> int:
    """Passos do dia local com chamada ao modelo (ou tokens) e `custo_brl` nulo."""
    try:
        return int(conn.execute(_SQL_AUSENTE, limites_do_dia(agora)).fetchone()[0])
    except psycopg.Error as erro:
        raise GastoIndisponivel(f"contagem de custo ausente falhou ({type(erro).__name__})") from None


def nivel_do_gasto(gasto: Decimal, limite: Decimal) -> Nivel:
    """80 % amarelo, 100 % crítico, acima de 125 % repassa. Limite zero: o teto já foi alcançado (e passado) com qualquer gasto."""
    if limite <= 0:
        return "repassar"
    fracao = gasto / limite
    if fracao > REPASSAR:
        return "repassar"
    if fracao >= CRITICO:
        return "critico"
    return "amarelo" if fracao >= AMARELO else "normal"


class MedidorGasto:
    """Soma do dia e do mês com cache de até `ttl_s` (30 s, contrato 08 §9) pelo relógio injetado. Um por processo."""

    def __init__(self, relogio: Relogio, ttl_s: float = TTL_GASTO_S) -> None:
        self._relogio = relogio
        self._ttl_s = ttl_s
        self._cache: dict[str, tuple[datetime, tuple[datetime, datetime], Decimal]] = {}

    def _medir(self, conn: psycopg.Connection, nome: str, limites: tuple[datetime, datetime]) -> Decimal:
        agora = self._relogio.agora()
        guardado = self._cache.get(nome)
        if guardado is not None and guardado[1] == limites and 0 <= (agora - guardado[0]).total_seconds() < self._ttl_s:
            return guardado[2]
        valor = _gasto(conn, *limites)
        self._cache = {**self._cache, nome: (agora, limites, valor)}
        return valor

    def dia(self, conn: psycopg.Connection) -> Decimal:
        return self._medir(conn, "dia", limites_do_dia(self._relogio.agora()))

    def mes(self, conn: psycopg.Connection) -> Decimal:
        return self._medir(conn, "mes", limites_do_mes(self._relogio.agora()))


@dataclass(frozen=True)
class AvaliacaoGasto:
    gasto_dia: Decimal
    gasto_mes: Decimal
    nivel_dia: Nivel
    nivel_mes: Nivel
    custo_ausente: int

    @property
    def nivel(self) -> Nivel:
        return max(self.nivel_dia, self.nivel_mes, key=_ORDEM.__getitem__)


def _limite(leitor: LeitorConfig, conn: psycopg.Connection, nome: str) -> Decimal:
    valor: Any = leitor.valor(conn, nome)
    return Decimal(str(valor))


def avaliar_gasto(
    conn: psycopg.Connection, relogio: Relogio, *, leitor: LeitorConfig | None = None, medidor: MedidorGasto | None = None
) -> AvaliacaoGasto:
    """O que o `turno` consulta antes de chamar o modelo: gasto e nível do dia (`subteto_dia`) e do mês (`teto_mensal_brl`)."""
    from ia_atendimento.chave import LeitorConfig

    leitor = leitor or LeitorConfig(relogio, ttl_s=0)
    medidor = medidor or MedidorGasto(relogio, ttl_s=0)
    dia, mes = medidor.dia(conn), medidor.mes(conn)
    return AvaliacaoGasto(
        gasto_dia=dia,
        gasto_mes=mes,
        nivel_dia=nivel_do_gasto(dia, _limite(leitor, conn, "subteto_dia")),
        nivel_mes=nivel_do_gasto(mes, _limite(leitor, conn, "teto_mensal_brl")),
        custo_ausente=custo_ausente_dia(conn, relogio.agora()),
    )
