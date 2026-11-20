"""Processador do atendimento (B1.6b; roteiro B1.6 T8; contrato 08 §6, §7.4, §9): `iniciar`, `processar` e o desligamento.

`iniciar` (job `iniciar`, depois de reler `ia_ativa`): regra (i) do batimento ⇒ `assumir` pelo `Canal` (cerca `reservado`) ⇒
`estado.iniciar` + evento `assumiu` na mesma transação ⇒ o 1º turno (a abertura, TX-01, vem do `Motor`).

`processar` (job `turno`), nesta ordem, tudo ANTES do modelo:
1. `aguardando_cliente` volta a `aberto`; outro estado não processa.
2. Batimento (regra i; regra ii na 1ª ação depois de indisponibilidade): `impedido` ⇒ `encerrado(repassado, devolvido_pela_s2)`;
   `indisponivel` ⇒ não age e pede nova tentativa em 15 s (D-15); `fora_de_vivos` ⇒ não age.
3. Transversais (gancho `transversal`): código ⇒ repasse.
4. Gasto (08 §9): soma que falha ⇒ não chama o modelo, nova tentativa em 60 s; 80 % ⇒ amarelo e 100 % ⇒ crítico (1×/dia por nível);
   > 125 % ⇒ repasse sem chamar o modelo; `custo_ausente` ⇒ crítico.
5. Disjuntor: `turnos ≥ 24` (RG-006) ou custo do atendimento acima do `custo_max_brl` da faixa (≤ R$ 3) ⇒ repasse.
6. `Motor.decidir`: `ErroDoModelo` conta em `contadores.falhas`; a 2ª seguida ⇒ repasse. Ok ⇒ nova `rodada`, envio de cada texto
   pelo `Canal` com a cerca de `versao` (chave `t11:{atd}:{rodada}:{seq}`, `args_hash` do texto) e depois `aguardar_cliente` com o
   lease de espera, ou o repasse.

O `Motor` é uma porta: o agente do turno da B1.4 entra aqui na integração (B1.7), com as obrigações herdadas que dependem dele
(`como_decisao_de_falha`, `[dado:<campo>]`, `nomes` em `Deps`...). O repasse é a fase 1 (`repassando`) + o job `repasse` (enfileirado
pela porta `enfileirar_repasse`).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Final, Literal, Protocol

import psycopg

from ia_atendimento import espelho, estado
from ia_atendimento.alertas import Alertas
from ia_atendimento.batimento import LeitorBatimento
from ia_atendimento.calendario import FUSO
from ia_atendimento.canal import ESTADO_EM_VIVOS_DA_CONVERSA, BatimentoIndisponivel, Canal, CercoFechado, ForaDeVivos
from ia_atendimento.chave import LeitorConfig
from ia_atendimento.espera import aguardar_cliente_com_espera, limites_da_faixa
from ia_atendimento.estado import Mudancas, aplicar
from ia_atendimento.estado_conversa import ler_estado_conversa
from ia_atendimento.estado_erros import ConflitoVersao, TransicaoInvalida
from ia_atendimento.gasto import GastoIndisponivel, MedidorGasto, avaliar_gasto
from ia_atendimento.ledger import Cerca
from ia_atendimento.relogio import Relogio
from ia_atendimento.repasse import Linha, encerrar_devolvido_pela_s2, iniciar_repasse, ler_linha
from ia_atendimento.turno import ErroDoModelo

TURNOS_MAX: Final = 24  # RG-006 (08 v2.4 §9): a F3 reprova acima de 24
FALHAS_MAX: Final = 2  # P7: duas falhas do modelo ⇒ repasse
ESPERA_BATIMENTO_S: Final = 15.0
ESPERA_GASTO_S: Final = 60.0
ESPERA_FALHA_S: Final = 10.0
CHATBOT_ANTES: Final = frozenset({"ligado", "desligado", "desconhecido"})

Acao = Literal["aguardar", "repassar"]


@dataclass(frozen=True)
class Decisao:
    """O que o turno decidiu: os textos a enviar (na ordem) e o que fazer depois."""

    textos: tuple[str, ...] = ()
    acao: Acao = "aguardar"
    motivo: str | None = None  # código curto do repasse pedido pelo modelo/regra


class Motor(Protocol):
    async def decidir(self, atendimento_id: uuid.UUID) -> Decisao: ...


@dataclass(frozen=True)
class Resultado:
    """`acao`: o que aconteceu. `reagendar_s`: o job deve rodar de novo depois disso (None = não)."""

    acao: str
    reagendar_s: float | None = None


class AvisosDeGasto:
    """80 % e 100 % alertam 1× por dia (São Paulo) e por nível; um por processo."""

    def __init__(self) -> None:
        self._dados: frozenset[tuple[str, date]] = frozenset()

    def primeiro_do_dia(self, codigo: str, dia: date) -> bool:
        if (codigo, dia) in self._dados:
            return False
        self._dados = self._dados | {(codigo, dia)}
        return True


@dataclass(frozen=True)
class DepsProcessador:
    canal: Canal
    motor: Motor
    batimento: LeitorBatimento
    alertas: Alertas
    leitor: LeitorConfig
    relogio: Relogio
    enfileirar_repasse: Callable[[uuid.UUID], Awaitable[None]]
    medidor: MedidorGasto | None = None
    transversal: Callable[[psycopg.Connection, uuid.UUID], str | None] | None = None
    avisos: AvisosDeGasto = field(default_factory=AvisosDeGasto)


# --- apoio -----------------------------------------------------------------------------------------------------------------------------


async def repassar(conn: psycopg.Connection, atd: uuid.UUID, deps: DepsProcessador, motivo: str) -> Resultado:
    """Fase 1 (`repassando`) + o job `repasse`. Perdeu o CAS (outra execução mexeu): não repassa por cima."""
    try:
        iniciar_repasse(conn, atd, motivo=motivo, relogio=deps.relogio)
    except (ConflitoVersao, TransicaoInvalida):
        return Resultado("superado")
    await deps.enfileirar_repasse(atd)
    return Resultado("repassar")


def _custos(conn: psycopg.Connection, atd: uuid.UUID) -> Decimal:
    return conn.execute("SELECT custo_modelo_brl + custo_midia_brl FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()[0]


def _cercar(conn: psycopg.Connection, linha: Linha, deps: DepsProcessador, *, recem_criado: bool = False) -> Resultado | None:
    """Regra (i) sempre; regra (ii) na 1ª ação depois de indisponibilidade, MENOS no 1º turno do `iniciar` (regra iii: o recém-criado
    leva até ~75 s para aparecer em `vivos`)."""
    esperado = ESTADO_EM_VIVOS_DA_CONVERSA if deps.batimento.recem_voltou and not recem_criado else None
    try:
        deps.canal.cercar(conn, linha.atendimento_id, devolucao=False, esperado_em_vivos=esperado)
    except CercoFechado:
        encerrar_devolvido_pela_s2(conn, linha, deps.relogio.agora())
        return Resultado("devolvido_pela_s2")
    except BatimentoIndisponivel:
        return Resultado("batimento_indisponivel", ESPERA_BATIMENTO_S)
    except ForaDeVivos:
        return Resultado("fora_de_vivos")
    return None


def _gasto(conn: psycopg.Connection, deps: DepsProcessador) -> Resultado | Literal["repassar"] | None:
    try:
        avaliacao = avaliar_gasto(conn, deps.relogio, leitor=deps.leitor, medidor=deps.medidor)
    except GastoIndisponivel:
        deps.alertas.alertar("critico", "gasto_indisponivel")
        return Resultado("gasto_indisponivel", ESPERA_GASTO_S)
    if avaliacao.custo_ausente > 0:
        deps.alertas.alertar("critico", "custo_ausente")
    dia = deps.relogio.agora().astimezone(FUSO).date()
    nivel = avaliacao.nivel
    if nivel == "repassar":
        return "repassar"
    if nivel in ("amarelo", "critico") and deps.avisos.primeiro_do_dia(f"gasto_{nivel}", dia):
        deps.alertas.alertar(nivel, f"gasto_{nivel}")
    return None


def _disjuntor(conn: psycopg.Connection, linha: Linha) -> str | None:
    if linha.turnos >= TURNOS_MAX:
        return "disjuntor_turnos"
    if _custos(conn, linha.atendimento_id) > limites_da_faixa(conn, linha.atendimento_id).custo_max_brl:
        return "disjuntor_custo"
    return None


def _anotar_rodada(conn: psycopg.Connection, linha: Linha, deps: DepsProcessador, *, falhou: bool) -> tuple[int, int, int]:
    """Uma transição (CAS): a falha conta em `falhas`; o turno bom zera `falhas`, abre `rodada + 1` e soma `turnos`. Devolve
    (versão nova, rodada, falhas)."""
    conversa = ler_estado_conversa(conn, linha.atendimento_id)
    c = conversa.contadores
    contadores = c.model_copy(update={"falhas": c.falhas + 1}) if falhou else c.model_copy(update={"falhas": 0, "rodada": c.rodada + 1})
    nova = conversa.model_copy(update={"contadores": contadores})
    campos: dict = {"estado_conversa": nova}
    if not falhou:
        campos["turnos"] = linha.turnos + 1
    versao = aplicar(conn, linha.atendimento_id, linha.versao, Mudancas(**campos), agora=deps.relogio.agora(), de={"aberto"})
    return versao, contadores.rodada, contadores.falhas


# --- iniciar ---------------------------------------------------------------------------------------------------------------------------


async def iniciar(conn: psycopg.Connection, atd: uuid.UUID, deps: DepsProcessador) -> Resultado:
    linha = ler_linha(conn, atd)
    if linha is None or linha.estado != "reservado":
        return Resultado("fora_de_estado")
    try:
        r = await deps.canal.assumir(conn, atd, cerca=Cerca(linha.versao, {"reservado"}))
    except CercoFechado:
        encerrar_devolvido_pela_s2(conn, linha, deps.relogio.agora())
        return Resultado("devolvido_pela_s2")
    except BatimentoIndisponivel:
        return Resultado("batimento_indisponivel")  # não age; o reaper do lease aborta o reservado se o batimento não voltar
    except (ConflitoVersao, TransicaoInvalida):
        return Resultado("superado")
    if r.estado != "ok" or r.versao is None:
        deps.alertas.alertar("critico", "assumir_falhou", atendimento_id=atd)
        return Resultado("assumir_falhou")
    antes = r.ref_externa if r.ref_externa in CHATBOT_ANTES else "desconhecido"
    mexeu = r.executou and antes == "ligado"  # só o efeito real desliga o chatbot
    with conn.transaction():
        estado.iniciar(
            conn,
            atd,
            r.versao,
            chatbot_antes=antes,
            chatbot_estado="desligado_pela_ia" if mexeu else "intocado",
            relogio=deps.relogio.agora,
        )
        espelho.emitir(conn, atd, "assumiu", {"chatbot_antes": antes})
    return await processar(conn, atd, deps, recem_criado=True)


# --- processar -------------------------------------------------------------------------------------------------------------------------


async def processar(conn: psycopg.Connection, atd: uuid.UUID, deps: DepsProcessador, *, recem_criado: bool = False) -> Resultado:
    linha = ler_linha(conn, atd)
    if linha is not None and linha.estado == "aguardando_cliente":
        estado.retomar(conn, atd, linha.versao, relogio=deps.relogio.agora)
        linha = ler_linha(conn, atd)
    if linha is None or linha.estado != "aberto":
        return Resultado("fora_de_estado")
    parar = _cercar(conn, linha, deps, recem_criado=recem_criado)
    if parar is not None:
        return parar
    codigo = deps.transversal(conn, atd) if deps.transversal is not None else None
    if codigo is not None:
        return await repassar(conn, atd, deps, codigo)
    gasto = _gasto(conn, deps)
    if gasto == "repassar":
        return await repassar(conn, atd, deps, "teto_gasto")
    if gasto is not None:
        return gasto
    disjuntor = _disjuntor(conn, linha)
    if disjuntor is not None:
        return await repassar(conn, atd, deps, disjuntor)
    return await _turno(conn, linha, deps)


async def _turno(conn: psycopg.Connection, linha: Linha, deps: DepsProcessador) -> Resultado:
    atd = linha.atendimento_id
    try:
        decisao = await deps.motor.decidir(atd)
    except ErroDoModelo as erro:
        _, _, falhas = _anotar_rodada(conn, linha, deps, falhou=True)
        deps.alertas.alertar("amarelo", "falha_do_modelo", atendimento_id=atd, detalhe=erro.codigo[:40])
        if falhas >= FALHAS_MAX:
            return await repassar(conn, atd, deps, "duas_falhas")
        return Resultado("falha_do_modelo", ESPERA_FALHA_S)
    try:
        versao, rodada, _ = _anotar_rodada(conn, linha, deps, falhou=False)
    except (ConflitoVersao, TransicaoInvalida):
        return Resultado("superado")
    enviados = 0
    for seq, texto in enumerate(decisao.textos, start=1):
        try:
            r = await deps.canal.enviar(conn, atd, rodada=rodada, seq=seq, texto=texto, cerca=Cerca(versao))
        except CercoFechado:
            encerrar_devolvido_pela_s2(conn, linha, deps.relogio.agora())
            return Resultado("devolvido_pela_s2")
        except BatimentoIndisponivel:
            return Resultado("batimento_indisponivel", ESPERA_BATIMENTO_S)
        except (ConflitoVersao, TransicaoInvalida):
            return Resultado("superado")  # outra execução (rodada nova) mexeu: a velha não envia por cima
        versao = r.versao if r.versao is not None else versao
        enviados += 1
    if enviados:
        versao = aplicar(
            conn, atd, versao, Mudancas(mensagens_enviadas=_enviadas(conn, atd) + enviados), agora=deps.relogio.agora(), de={"aberto"}
        )
    if decisao.acao == "repassar":
        return await repassar(conn, atd, deps, decisao.motivo or "pedido_do_turno")
    aguardar_cliente_com_espera(conn, atd, versao, relogio=deps.relogio, leitor=deps.leitor)
    return Resultado("aguardar")


def _enviadas(conn: psycopg.Connection, atd: uuid.UUID) -> int:
    return conn.execute("SELECT mensagens_enviadas FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()[0]


# --- desligamento (parada leve manual: encerrar_por_chave) -----------------------------------------------------------------------------


async def encerrar_por_chave(conn: psycopg.Connection, atd: uuid.UUID, deps: DepsProcessador) -> Resultado:
    """`PUT ia_ativa=false` agenda um job por atendimento (≤ 20 min). Quem ainda não tocou o chat (`reservado`) aborta com o `encerrou`;
    `aberto|aguardando_cliente|pausado` vão ao repasse (a nota e o chatbot voltam ao vendedor). `repassando`/`encerrado` não mudam.
    Quem chama já releu `ia_ativa` (jobs.executar_encerrar_por_chave)."""
    linha = ler_linha(conn, atd)
    if linha is None:
        return Resultado("fora_de_estado")
    if linha.estado == "reservado":
        with conn.transaction():
            atual = ler_linha(conn, atd, travar=True)
            if atual is None or atual.estado != "reservado":
                return Resultado("superado")
            estado.abortar(conn, atd, atual.versao, motivo="ia_desligada", relogio=deps.relogio.agora)
            espelho.emitir_encerrou(conn, atd, "ia_desligada", deps.relogio.agora())
        return Resultado("abortado")
    if linha.estado in ("aberto", "aguardando_cliente", "pausado"):
        return await repassar(conn, atd, deps, "ia_desligada")
    return Resultado("fora_de_estado")
