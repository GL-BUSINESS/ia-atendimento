"""Apoio dos testes da B1.6b: portas falsas (Canal, ia-repasse, espelho, batimento) e alertas que se lembram. Nada sai para fora."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ia_atendimento.ledger import Desfecho


@dataclass
class AlertasFalsos:
    vistos: list[tuple[str, str]] = field(default_factory=list)

    def alertar(self, nivel: str, codigo: str, *, atendimento_id: object = None, detalhe: str = "") -> None:
        self.vistos.append((nivel, codigo))

    def codigos(self, nivel: str | None = None) -> list[str]:
        return [c for n, c in self.vistos if nivel is None or n == nivel]


@dataclass
class FonteFalsa:
    corpo: object | None = None

    async def buscar(self) -> object | None:
        return self.corpo


def batimento_v2(gerado_em: datetime, *, seq: int = 1, impedidos: dict | None = None, vivos: dict | None = None) -> dict[str, Any]:
    return {"v": 2, "gerado_em": gerado_em.isoformat(), "seq": seq, "impedidos": impedidos or {}, "vivos": vivos or {}}


Resposta = Desfecho | Callable[[], Any] | BaseException


@dataclass
class CanalFalso:
    """`PortaCanal` falsa: registra (operação, destino, texto) e devolve o que `respostas[operação]` mandar (uma lista consome em ordem)."""

    respostas: dict[str, list[Resposta]] = field(default_factory=dict)
    chamadas: list[tuple[str, str, str | None]] = field(default_factory=list)

    async def _responder(self, op: str, destino: str, texto: str | None) -> Desfecho:
        self.chamadas.append((op, destino, texto))
        fila = self.respostas.get(op)
        resposta: Resposta = fila.pop(0) if fila else (Desfecho("ok", ref_externa="ligado") if op == "assumir" else Desfecho("ok"))
        if isinstance(resposta, BaseException):
            raise resposta
        if callable(resposta):
            return await resposta()
        return resposta

    async def assumir(self, atendimento_id: object, destino: str) -> Desfecho:
        return await self._responder("assumir", destino, None)

    async def enviar(self, atendimento_id: object, destino: str, texto: str) -> Desfecho:
        return await self._responder("enviar", destino, texto)

    async def nota(self, atendimento_id: object, destino: str, texto: str) -> Desfecho:
        return await self._responder("nota", destino, texto)

    async def restaurar(self, atendimento_id: object, destino: str) -> Desfecho:
        return await self._responder("restaurar", destino, None)

    def ops(self) -> list[str]:
        return [c[0] for c in self.chamadas]


@dataclass
class RotaFalsa:
    """`PortaRepasse` falsa (o `ia-repasse`): devolve `resultados` em ordem; registra o corpo (sem PII por construção)."""

    resultados: list[str | BaseException] = field(default_factory=lambda: ["delegou"])
    corpos: list[dict[str, Any]] = field(default_factory=list)

    async def rotear(self, atendimento_id: object, destino: str, corpo: dict[str, Any]) -> str:
        self.corpos.append(dict(corpo))
        r = self.resultados.pop(0) if len(self.resultados) > 1 else self.resultados[0]
        if isinstance(r, BaseException):
            raise r
        return r


@dataclass
class EspelhoFalso:
    resultados: list[str | BaseException] = field(default_factory=lambda: ["aplicado"])
    enviados: list[tuple[str, int, str]] = field(default_factory=list)

    async def publicar(self, chave: str, seq: int, evento: str, detalhe: dict[str, Any]) -> str:
        self.enviados.append((chave, seq, evento))
        r = self.resultados.pop(0) if len(self.resultados) > 1 else self.resultados[0]
        if isinstance(r, BaseException):
            raise r
        return r
