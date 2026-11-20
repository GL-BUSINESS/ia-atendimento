"""`Canal`: os efeitos no chat do cliente, sempre pelo ledger e atrás do batimento (B1.6b; contrato 08 §6 e §7.4).

Duas camadas:
- **`PortaCanal`** (protocolo): o adaptador que fala com o mundo (`assumir`, `enviar`, `nota`, `restaurar`), recebendo o destino já
  decidido (`real|teste`). **Não há adaptador real neste repositório**: a delegação de verdade hoje passa pela edge function
  `delegar-pre-aprovado` (gl-painel + robô de tela), não pelo `ia-repasse → zVuE`, e o desenho volta ao dono (DEC-PIA-002, estudo do
  CLT de 17/11). Até lá só a porta falsa dos testes; o real é da B6.8.
- **`Canal`**: antes de cada efeito que seria REAL (`modo_efetivo ∈ {real, teste}`, ou a devolução de quem tem posse real), consulta o
  batimento: `impedido` ⇒ `CercoFechado`; `indisponivel` ⇒ `BatimentoIndisponivel` (D-15: a IA não age, fail-closed);
  `fora_de_vivos` ⇒ `ForaDeVivos`. Nada é reservado no ledger quando o cerco recusa. Depois, `executar_efeito` com a chave do efeito:
  `t11:{atd}:{rodada}:{seq}` (com `args_hash` do texto), `nota:{atd}`, `restaurar:{atd}`, `assumir:{atd}`. Em `teste` o texto leva o
  prefixo «[TESTE]». Quem nasceu `sombra|duble` (ou a parada dura sem posse real) nunca chega à porta: o ledger simula.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Final, Protocol

import psycopg

from ia_atendimento.batimento import LeitorBatimento
from ia_atendimento.chave import LeitorConfig
from ia_atendimento.estado_erros import AtendimentoInexistente, EstadoErro
from ia_atendimento.ledger import (
    DESTINOS_REAIS,
    Cerca,
    Desfecho,
    Pedido,
    ResultadoEfeito,
    chave_t11,
    executar_efeito,
    modo_efetivo,
    posse_real,
)
from ia_atendimento.relogio import Relogio

PREFIXO_TESTE: Final = "[TESTE] "
VERSAO: Final = "1.0.0"
TIMEOUT_CANAL_S: Final = 10.0
ESTADO_EM_VIVOS_DA_CONVERSA: Final = "aberto"


class CercoFechado(EstadoErro):
    """A chave está em `impedidos` do batimento: a S2 já tomou o lead. Quem chama encerra `repassado/devolvido_pela_s2` sem efeito."""


class BatimentoIndisponivel(EstadoErro):
    """Batimento ausente, velho (> 90 s) ou inválido e o efeito seria real: a IA não age (D-15). Nada reservado."""


class ForaDeVivos(EstadoErro):
    """Regra (ii): a chave não está em `vivos` com o estado esperado. Não age; quem encerra é o prazo (vigia R-b) ou `expirar_parados`."""


class PortaCanal(Protocol):
    """O adaptador do chat. `assumir` devolve o estado anterior do chatbot em `ref_externa` (`ligado|desligado|desconhecido`)."""

    async def assumir(self, atendimento_id: uuid.UUID, destino: str) -> Desfecho: ...

    async def enviar(self, atendimento_id: uuid.UUID, destino: str, texto: str) -> Desfecho: ...

    async def nota(self, atendimento_id: uuid.UUID, destino: str, texto: str) -> Desfecho: ...

    async def restaurar(self, atendimento_id: uuid.UUID, destino: str) -> Desfecho: ...


def hash_texto(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def com_prefixo(destino: str, texto: str) -> str:
    return PREFIXO_TESTE + texto if destino == "teste" and not texto.startswith(PREFIXO_TESTE) else texto


def _dados(conn: psycopg.Connection, atd: uuid.UUID) -> tuple[str, str]:
    linha = conn.execute("SELECT modo, chave_logica FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()
    if linha is None:
        raise AtendimentoInexistente("atendimento inexistente")
    return linha[0], linha[1]


def efeito_seria_real(conn: psycopg.Connection, atd: uuid.UUID, leitor: LeitorConfig, *, devolucao: bool) -> bool:
    """O efeito chegaria ao mundo? (Só esses consultam o batimento, 08 §7.4 R2-03.)"""
    modo_atd, _ = _dados(conn, atd)
    if devolucao:
        return modo_atd in DESTINOS_REAIS and posse_real(conn, atd)
    return modo_efetivo(modo_atd, str(leitor.valor(conn, "modo"))) in DESTINOS_REAIS


class Canal:
    def __init__(
        self,
        porta: PortaCanal,
        batimento: LeitorBatimento,
        *,
        leitor: LeitorConfig,
        relogio: Relogio,
        timeout_s: float = TIMEOUT_CANAL_S,
    ) -> None:
        self._porta = porta
        self._batimento = batimento
        self._leitor = leitor
        self._relogio = relogio
        self._timeout_s = timeout_s

    def cercar(self, conn: psycopg.Connection, atd: uuid.UUID, *, devolucao: bool, esperado_em_vivos: str | None = None) -> None:
        """Levanta se o batimento não deixa agir; não faz nada quando o efeito não seria real."""
        if not efeito_seria_real(conn, atd, self._leitor, devolucao=devolucao):
            return
        _, chave = _dados(conn, atd)
        situacao = self._batimento.situacao(chave, esperado_em_vivos=esperado_em_vivos, atendimento_id=atd)
        if situacao == "impedido":
            raise CercoFechado("a chave está em impedidos: a S2 já tomou o lead")
        if situacao == "indisponivel":
            raise BatimentoIndisponivel("batimento ausente ou velho: a IA não age (D-15)")
        if situacao == "fora_de_vivos":
            raise ForaDeVivos("a chave não está em vivos com o estado esperado")

    async def _executar(self, conn: psycopg.Connection, atd: uuid.UUID, pedido: Pedido, chamar, cerca: Cerca | None) -> ResultadoEfeito:
        return await executar_efeito(
            conn, atd, pedido, chamar=chamar, leitor=self._leitor, relogio=self._relogio, cerca=cerca, timeout_s=self._timeout_s
        )

    async def assumir(self, conn: psycopg.Connection, atd: uuid.UUID, *, cerca: Cerca) -> ResultadoEfeito:
        """Toma o chat (regra iii: só `impedidos`). `ref_externa` do resultado = estado anterior do chatbot."""
        self.cercar(conn, atd, devolucao=False)
        pedido = Pedido(ferramenta="assumir", ferramenta_versao=VERSAO, classe_efeito="acao_interna", chave_logica=f"assumir:{atd}")

        async def chamar(destino: str) -> Desfecho:
            return await self._porta.assumir(atd, destino)

        return await self._executar(conn, atd, pedido, chamar, cerca)

    async def enviar(
        self,
        conn: psycopg.Connection,
        atd: uuid.UUID,
        *,
        rodada: int,
        seq: int,
        texto: str,
        cerca: Cerca,
        esperado_em_vivos: str | None = None,
    ) -> ResultadoEfeito:
        """Mensagem ao cliente (T11). A cerca é obrigatória: só a conversa viva (versão e estado esperados) envia."""
        self.cercar(conn, atd, devolucao=False, esperado_em_vivos=esperado_em_vivos)
        pedido = Pedido(
            ferramenta="t11", ferramenta_versao=VERSAO, classe_efeito="efeito_irreversivel",
            chave_logica=chave_t11(atd, rodada, seq), args_hash=hash_texto(texto),
        )  # fmt: skip

        async def chamar(destino: str) -> Desfecho:
            return await self._porta.enviar(atd, destino, com_prefixo(destino, texto))

        return await self._executar(conn, atd, pedido, chamar, cerca)

    async def nota(self, conn: psycopg.Connection, atd: uuid.UUID, *, texto: str) -> ResultadoEfeito:
        """Nota do repasse (TX-34): devolução, irreversível, UMA chamada (o ledger nunca a repete depois de `indeterminado`)."""
        self.cercar(conn, atd, devolucao=True)
        pedido = Pedido(
            ferramenta="nota", ferramenta_versao=VERSAO, classe_efeito="efeito_irreversivel", chave_logica=f"nota:{atd}",
            args_hash=hash_texto(texto), devolucao=True,
        )  # fmt: skip

        async def chamar(destino: str) -> Desfecho:
            return await self._porta.nota(atd, destino, com_prefixo(destino, texto))

        return await self._executar(conn, atd, pedido, chamar, None)

    async def restaurar(self, conn: psycopg.Connection, atd: uuid.UUID) -> ResultadoEfeito:
        """Devolve o chatbot ao estado anterior (ação interna, idempotente: repete com a mesma chave)."""
        self.cercar(conn, atd, devolucao=True)
        pedido = Pedido(
            ferramenta="restaurar", ferramenta_versao=VERSAO, classe_efeito="acao_interna", chave_logica=f"restaurar:{atd}", devolucao=True
        )

        async def chamar(destino: str) -> Desfecho:
            return await self._porta.restaurar(atd, destino)

        return await self._executar(conn, atd, pedido, chamar, None)
