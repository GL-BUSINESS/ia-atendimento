"""Para onde vai cada chamada: `modo_efetivo` relido a cada efeito e a URL base por serviço (B5.1; P-R7, R2-02; contrato 08 §6).

- `modo_efetivo` = o mais restritivo entre `atendimento.modo` e o `config.modo` vigente (real > teste > duble > sombra; o menor vence).
  O que não for modo conhecido vale `sombra` (fail-closed, D-15). `LeitorDeModo` relê o `config.modo` com cache de no máximo 5 s.
- `Destinos` guarda as URLs (`FACTA_BASE`, `FACTA_BASE_TESTE`, `C360_BASE`, `TRN_BASE`, `C6_BASE`) e decide o destino. O executor da
  ferramenta só conhece a URL que o `Destino` lhe entrega: em `teste` e `sombra` a URL de produção da FACTA nem sai daqui.

Regra de destino (servico × classe × modo_efetivo; `posse_real` só pesa sob parada dura, `modo_efetivo ∈ {sombra, duble}`):

| | real | teste | duble | sombra |
|---|---|---|---|---|
| FACTA (T5/T7/T8/T9), qualquer classe | produção | dublê da VPS (`FACTA_BASE_TESTE`) | interceptado | interceptado |
| FACTA, leitura, com posse real | produção | dublê da VPS | `MODO_SOMENTE_LEITURA` | `MODO_SOMENTE_LEITURA` |
| 360/3RN/C6, leitura | produção | fixture | fixture; com posse real, produção só leitura | produção só leitura |
| 360/3RN/C6, leitura paga ou efeito | produção | interceptado | interceptado | interceptado |
| ação interna | interno | interno | interno | interno |

A linha da FACTA segue o roteiro B5.1 («só em `real` resolvem `FACTA_BASE`»), mais restritiva que a linha «Ler» de 08 §6 para a FACTA.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Final, Literal, get_args
from urllib.parse import urlsplit

from ia_atendimento.ferramentas.erros import ErroDeFerramenta
from ia_atendimento.relogio import Relogio

Modo = Literal["real", "teste", "duble", "sombra"]
MODOS: Final = get_args(Modo)
_RESTRICAO: Final = {modo: posicao for posicao, modo in enumerate(MODOS)}  # maior = mais restritivo
_MODOS_GLOBAIS: Final = frozenset({"real", "sombra", "duble"})  # `teste` global não existe (08 §6)
TTL_MAXIMO_S: Final = 5.0
TipoDeDestino = Literal["producao", "duble", "fixture", "interceptado", "interno"]
ServicoDeFora = Literal["facta", "c360", "trn", "c6", "interno"]
SERVICO_DO_BANCO: Final[Mapping[str, ServicoDeFora]] = {"FACTA": "facta", "3RN": "trn", "C6": "c6"}
VARIAVEIS_DE_AMBIENTE: Final[Mapping[str, tuple[str, str | None]]] = {
    "facta": ("FACTA_BASE", "FACTA_BASE_TESTE"),
    "c360": ("C360_BASE", None),
    "trn": ("TRN_BASE", None),
    "c6": ("C6_BASE", None),
}


def modo_efetivo(atendimento_modo: object, config_modo: object) -> Modo:
    if atendimento_modo not in _RESTRICAO or config_modo not in _MODOS_GLOBAIS:
        return "sombra"
    return max((atendimento_modo, config_modo), key=_RESTRICAO.__getitem__)  # type: ignore[return-value]


class LeitorDeModo:
    """Relê o `config.modo` vigente com cache ≤ 5 s (pelo relógio injetado). Leitura que falha vale `sombra` e não entra no cache."""

    def __init__(self, ler_config: Callable[[], object], relogio: Relogio, *, ttl_s: float = TTL_MAXIMO_S) -> None:
        if not 0 <= ttl_s <= TTL_MAXIMO_S:
            raise ValueError("o cache do modo vai de 0 a 5 s")
        self._ler, self._relogio, self._ttl = ler_config, relogio, timedelta(seconds=ttl_s)
        self._cache: tuple[datetime, object] | None = None

    def config(self) -> object:
        agora = self._relogio.agora()
        if self._cache is not None and agora - self._cache[0] < self._ttl:
            return self._cache[1]
        try:
            valor = self._ler()
        except Exception:
            self._cache = None
            return "sombra"
        self._cache = (agora, valor)
        return valor

    def efetivo(self, atendimento_modo: object) -> Modo:
        return modo_efetivo(atendimento_modo, self.config())


class DestinosInvalidos(ValueError):
    """URL base malformada ou o dublê apontando para o host da produção: o gateway não sobe. A mensagem cita só o serviço."""


def _conferir_url(url: str, servico: str, papel: str) -> str:
    erro = DestinosInvalidos(f"{servico}: URL {papel} inválida (https, ou http só em loopback; sem credencial, query nem fragmento)")
    if any(c.isspace() or ord(c) < 32 for c in url):
        raise erro
    try:
        partes = urlsplit(url)
        host = partes.hostname
        _ = partes.port
    except ValueError:
        raise erro from None
    if not host or partes.username or partes.password or partes.query or partes.fragment:
        raise erro
    loopback = host == "localhost" or _e_loopback(host)
    if partes.scheme != "https" and not (partes.scheme == "http" and loopback):
        raise erro
    return host.lower()


def _e_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class BasesDoServico:
    producao: str | None = field(default=None, repr=False)
    teste: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class Destino:
    tipo: TipoDeDestino
    modo_efetivo: Modo
    url: str | None = field(default=None, repr=False)
    somente_leitura: bool = False

    @property
    def simulado(self) -> bool:
        """O que o ledger grava (`simulado = modo <> 'real'`)."""
        return self.modo_efetivo != "real"


class Destinos:
    def __init__(self, bases: Mapping[str, BasesDoServico]) -> None:
        for servico, base in bases.items():
            hosts = {
                papel: _conferir_url(url, servico, papel) for papel, url in (("producao", base.producao), ("teste", base.teste)) if url
            }
            if len(hosts) == 2 and hosts["producao"] == hosts["teste"]:
                raise DestinosInvalidos(f"{servico}: a URL de teste aponta para o host da produção")
        self._bases = dict(bases)

    def __repr__(self) -> str:
        return f"Destinos({', '.join(sorted(self._bases))})"

    @classmethod
    def de_ambiente(cls, ambiente: Mapping[str, str]) -> Destinos:
        bases = {
            servico: BasesDoServico(producao=ambiente.get(prod) or None, teste=(ambiente.get(teste) or None) if teste else None)
            for servico, (prod, teste) in VARIAVEIS_DE_AMBIENTE.items()
        }
        return cls(bases)

    def resolver(self, servico: str, classe: str, modo: Modo, *, posse_real: bool = False) -> Destino:
        if servico == "interno" or classe == "acao_interna":
            return Destino("interno", modo)
        base = self._bases.get(servico, BasesDoServico())
        if modo == "real":
            if not base.producao:
                raise ErroDeFerramenta("BANCO_INDISPONIVEL")
            return Destino("producao", modo, base.producao)
        if servico == "facta":
            if modo != "teste":
                if classe == "leitura" and posse_real:
                    # Leitura da FACTA de um atendimento com posse real sob parada dura (T5, T8, T9): nem a produção (roteiro B5.1) nem o
                    # simulador, que responderia `nao_criada` a uma digitação que pode existir e abriria caminho à redigitação (revisão
                    # B5.1, M-7). Fail-closed até o dono decidir entre o roteiro e a linha «Ler real» de 08 §6.
                    raise ErroDeFerramenta("MODO_SOMENTE_LEITURA")
                return Destino("interceptado", modo)
            if not base.teste:
                raise ErroDeFerramenta("MODO_SOMENTE_LEITURA")  # sem dublê configurado: nunca cai na produção
            return Destino("duble", modo, base.teste)
        if classe != "leitura":
            return Destino("interceptado", modo)
        if modo == "sombra" or (modo == "duble" and posse_real):
            if not base.producao:
                raise ErroDeFerramenta("BANCO_INDISPONIVEL")
            return Destino("producao", modo, base.producao, somente_leitura=True)
        return Destino("fixture", modo)  # teste (pessoa sintética) e duble sem posse real
