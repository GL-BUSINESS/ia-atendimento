"""Orçamento das chamadas (estudo F §Gateway 6; roteiro B5.1): por turno ≤ 4 síncronas e ≤ 5 s; por atendimento ≤ 2 consultas pagas e
≤ 3 corrigíveis.

O orçamento do turno nasce a cada `executar_turno` (`Deps.orcamento`); sem ele a ferramenta do modelo não roda (fail-closed). O contador
do atendimento aqui é em memória; a B1.6 o troca pela contagem do ledger (`ferramenta_chamada`), que sobrevive a reinício.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Final
from uuid import UUID

MAX_SINCRONAS_POR_TURNO: Final = 4
MAX_SEGUNDOS_POR_TURNO: Final = 5.0
MAX_PAGAS_POR_ATENDIMENTO: Final = 2
MAX_CORRIGIVEIS_POR_ATENDIMENTO: Final = 3


@dataclass
class OrcamentoDoTurno:
    max_sincronas: int = MAX_SINCRONAS_POR_TURNO
    max_segundos: float = MAX_SEGUNDOS_POR_TURNO
    sincronas: int = 0
    segundos: float = 0.0

    def cabe(self) -> bool:
        return self.sincronas < self.max_sincronas and self.segundos < self.max_segundos

    def restante_s(self) -> float:
        return max(self.max_segundos - self.segundos, 0.0)

    def gastar(self, segundos: float) -> None:
        self.sincronas += 1
        self.segundos += max(segundos, 0.0)

    @classmethod
    def esgotado(cls) -> OrcamentoDoTurno:
        return cls(max_sincronas=0, max_segundos=0.0)


@dataclass
class ContadorDoAtendimento:
    max_pagas: int = MAX_PAGAS_POR_ATENDIMENTO
    max_corrigiveis: int = MAX_CORRIGIVEIS_POR_ATENDIMENTO
    _pagas: Counter[UUID] = field(default_factory=Counter, repr=False)
    _corrigiveis: Counter[UUID] = field(default_factory=Counter, repr=False)

    def pagas(self, atendimento_id: UUID) -> int:
        return self._pagas[atendimento_id]

    def corrigiveis(self, atendimento_id: UUID) -> int:
        return self._corrigiveis[atendimento_id]

    def registrar_paga(self, atendimento_id: UUID) -> None:
        self._pagas[atendimento_id] += 1

    def registrar_corrigivel(self, atendimento_id: UUID) -> None:
        self._corrigiveis[atendimento_id] += 1
