"""Tudo que as rotas precisam, injetado de uma vez (testes trocam conexões, relógio, fila e pré-voo; produção monta de `Settings`).

Imutável. `conexao()` entrega uma conexão em autocommit (cada grupo atômico abre o seu `conn.transaction()`); `enfileirador` põe job na
transação da conexão que recebe. Os segredos de saída (Bearer do `ia-repasse`, token do chatguru-api, client do c360-auth) são só VALIDADOS
no boot: a B1.5 não os usa, e nenhum deles aparece em log nem em resposta.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from importlib import metadata
from pathlib import Path
from typing import Final, Literal, Protocol

import psycopg

from ia_atendimento.chave import LeitorConfig
from ia_atendimento.cifra import Chaveiro
from ia_atendimento.config import Settings
from ia_atendimento.enfileirador import Enfileirador
from ia_atendimento.evento_mensagem import ChavesDeMensagem
from ia_atendimento.pessoas_teste import PessoasTeste
from ia_atendimento.relogio import Relogio
from ia_atendimento.segredos import SegredosDeSaida

log = logging.getLogger("ia_atendimento.api")
CACHE_PRE_VOO_S: Final = 30.0  # contrato 08 §3: o pré-voo vale por 30 s


class PreVooFalhou(Exception):
    """Pré-voo (modelo, S4, canal ou cookie) recusou: `409 provedor_fora` ou `409 pre_voo_falhou`, nada muda."""

    def __init__(self, codigo: Literal["provedor_fora", "pre_voo_falhou"]) -> None:
        super().__init__(codigo)
        self.codigo = codigo


class PreVoo(Protocol):
    def verificar(self) -> None:
        """Levanta `PreVooFalhou` se a entrada não deve começar. A implementação real (modelo, canal, cookie) é da B1.6/B6.8."""
        ...


class PreVooLivre:
    """Padrão da B1.5: nada a checar além do banco (que a própria rota já exige)."""

    def verificar(self) -> None:
        return None


class PreVooComCache:
    """Guarda o resultado por 30 s (relógio injetado): sucesso e falha. Uma falha repetida não martela o provedor."""

    def __init__(self, interno: PreVoo, relogio: Relogio, ttl_s: float = CACHE_PRE_VOO_S) -> None:
        self._interno, self._relogio, self._ttl = interno, relogio, timedelta(seconds=ttl_s)
        self._guardado: tuple[datetime, str | None] | None = None

    def verificar(self) -> None:
        agora = self._relogio.agora()
        if self._guardado is None or not (timedelta(0) <= agora - self._guardado[0] < self._ttl):
            try:
                self._interno.verificar()
                self._guardado = (agora, None)
            except PreVooFalhou as erro:
                self._guardado = (agora, erro.codigo)
        if self._guardado[1] is not None:
            raise PreVooFalhou(self._guardado[1])  # type: ignore[arg-type]


@dataclass
class Contadores:
    """Contadores de métrica da API (alertas do TI: `evento_teste_fora_da_lista`, `texto_livre_mascarado_na_leitura`...). Só nomes e
    inteiros."""

    _valores: Counter[str] = field(default_factory=Counter)

    def somar(self, nome: str, n: int = 1) -> None:
        self._valores[nome] += n

    def valor(self, nome: str) -> int:
        return self._valores[nome]


@dataclass(frozen=True)
class ContextoApi:
    settings: Settings
    relogio: Relogio
    conexao: Callable[[], AbstractContextManager[psycopg.Connection]]
    leitor: LeitorConfig
    chaveiro: Chaveiro
    chaves_msg: ChavesDeMensagem
    enfileirador: Enfileirador
    tokens: dict[str, bytes] = field(repr=False)
    gateway_hmac: tuple[bytes, ...] = field(repr=False)
    pessoas_teste: PessoasTeste
    segredos_de_saida: SegredosDeSaida = field(repr=False)
    pre_voo: PreVoo = field(default_factory=PreVooLivre)
    # há template de abertura aprovado? (08 §8, E-5/V5). Padrão: não há ⇒ a recusa segura `janela_24h` vale (a mais restritiva)
    template_de_abertura_aprovado: Callable[[], bool] = field(default=lambda: False)
    dsn: str = field(default="", repr=False)  # conexão do `/readyz` (nova por chamada, com timeout); vazio = usa a conexão do pool
    diretorio_migracoes: Path | None = None
    metricas: Contadores = field(default_factory=Contadores)
    versao: str = field(default_factory=lambda: _versao_do_pacote())
    git_sha: str = "desconhecido"
    built_at: str = "desconhecido"


def _versao_do_pacote() -> str:
    try:
        return metadata.version("ia-atendimento")
    except metadata.PackageNotFoundError:
        return "desconhecida"
