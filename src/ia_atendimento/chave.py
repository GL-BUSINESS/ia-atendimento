"""Chave: configuração versionada (`ia.config_versao`, append-only) e as recusas de entrada.

- Vigente = `max(versao)` por nome. Mudar = `INSERT versao+1`; perder a corrida (PK, ou `versao_esperada` velha) = `ConfigCorrida` (409).
- Todo valor passa pelo registro (`chave_registro`) antes de ir ao banco; chave fora do registro = `ConfigInexistente`.
- `LeitorConfig` guarda cada chave por até 5 s (relógio injetado); a escrita do próprio processo invalida o cache na hora.
- `bloqueio_entrada()` devolve o código da primeira recusa de entrada nova (ou None). A chave `bloqueio_entrada=true` recusa entrada nova e
  **não encerra ninguém**: abertos e pausados seguem as réguas deles (quem encerra por chave é só a parada leve manual `ia_ativa=false`).
- Gasto (`teto_atingido`/`teto_diario`) é Σ `passo.custo_brl` em São Paulo (`gasto.py`, contrato 08 §9); soma que falha levanta
  `GastoIndisponivel` (a API responde `503 nao_pronto`), nunca recusa nem aceita com zero.
- Hora e mês/dia de negócio vêm do `Relogio` e do calendário (America/Sao_Paulo), nunca do `now()` nem do fuso do banco.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import psycopg
from psycopg import errors as pg_errors
from psycopg.types.json import Jsonb

from ia_atendimento.calendario import carregar_calendario, limites_do_dia
from ia_atendimento.chave_registro import (
    PADROES,
    REGISTRO,
    ConfigCorrida,
    ConfigInexistente,
    ErroConfig,
    ModoTesteGlobal,
    ValorInvalido,
)
from ia_atendimento.gasto import GastoIndisponivel, gasto_dia, gasto_mes
from ia_atendimento.relogio import Relogio

__all__ = [
    "RECUSAS_DE_ENTRADA",
    "ConfigCorrida",
    "ConfigInexistente",
    "ErroConfig",
    "GastoIndisponivel",
    "LeitorConfig",
    "ModoTesteGlobal",
    "ValorInvalido",
    "VersaoConfig",
    "abertos_agora",
    "bloqueio_entrada",
    "config_em",
    "config_vigente",
    "garantir_defaults",
    "gasto_dia",
    "gasto_mes",
    "ia_ativa_agora",
    "optou_por_sair",
    "registrar_config",
]

TTL_CACHE_S = 5.0
RECUSAS_DE_ENTRADA = (
    "ia_desligada",
    "bloqueio_entrada",
    "fora_de_janela",
    "opt_out",
    "teto_atingido",
    "teto_diario",
    "disparos_dia",
    "abertos_max",
)
# pares (A, B) com A <= B: agenda_max_dia nunca passa de max_disparos_dia (R2-17)
LIMITES_CRUZADOS = (("agenda_max_dia", "max_disparos_dia"),)
CHAVE_TRAVA_LIMITES = "ia_atendimento.config.limites_cruzados"


@dataclass(frozen=True)
class VersaoConfig:
    nome: str
    versao: int
    valor: Any
    publicado_em: datetime
    publicado_por: str
    motivo: str | None


def config_vigente(conn: psycopg.Connection, nome: str) -> VersaoConfig | None:
    """A versão de maior número da chave, ou None se ela nunca foi gravada."""
    linha = conn.execute(
        "SELECT nome, versao, valor, publicado_em, publicado_por, motivo FROM ia.config_versao WHERE nome = %s "
        "ORDER BY versao DESC LIMIT 1",
        (nome,),
    ).fetchone()
    return VersaoConfig(*linha) if linha else None


def config_em(conn: psycopg.Connection, nome: str, instante: datetime) -> Any:
    """Valor da chave vigente em `instante` (a maior versão publicada até ele). Sem versão até lá (a chave foi gravada depois, ex.: seed no
    boot posterior ao atendimento), a mais antiga; nunca gravada, o padrão do registro. É o que «a config vigente em `iniciado_em`» quer
    dizer: trocar a config não muda atendimento em curso."""
    linha = conn.execute(
        "SELECT valor FROM ia.config_versao WHERE nome = %s AND publicado_em <= %s ORDER BY versao DESC LIMIT 1", (nome, instante)
    ).fetchone()
    if linha is None:
        linha = conn.execute("SELECT valor FROM ia.config_versao WHERE nome = %s ORDER BY versao LIMIT 1", (nome,)).fetchone()
    return linha[0] if linha is not None else PADROES.get(nome)


def registrar_config(
    conn: psycopg.Connection,
    nome: str,
    valor: Any,
    por: str,
    *,
    relogio: Relogio,
    motivo: str | None = None,
    versao_esperada: int | None = None,
) -> VersaoConfig:
    """Valida e grava `versao+1`. `versao_esperada` (opcional) é a versão que o chamador leu: se mudou, `ConfigCorrida`."""
    especificacao = REGISTRO.get(nome)
    if especificacao is None:
        raise ConfigInexistente(f"chave fora do registro: {nome}")
    normalizado = especificacao.validar(valor)
    with conn.transaction():
        if any(nome in par for par in LIMITES_CRUZADOS):  # duas escritas do par não se enxergam em READ COMMITTED: serializa (revisão A6)
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (CHAVE_TRAVA_LIMITES,))
        _conferir_limites_cruzados(conn, nome, normalizado)
        atual = config_vigente(conn, nome)
        versao_atual = atual.versao if atual else 0
        if versao_esperada is not None and versao_esperada != versao_atual:
            raise ConfigCorrida(f"{nome}: a versão vigente é {versao_atual}, não {versao_esperada}")
        return _inserir_versao(conn, nome, versao_atual + 1, normalizado, por, motivo, relogio.agora())


def _inserir_versao(
    conn: psycopg.Connection, nome: str, versao: int, valor: Any, por: str, motivo: str | None, publicado_em: datetime
) -> VersaoConfig:
    try:
        with conn.transaction():  # savepoint: a PK perdida não derruba a transação de quem chamou
            conn.execute(
                "INSERT INTO ia.config_versao (nome, versao, valor, publicado_em, publicado_por, motivo) VALUES (%s, %s, %s, %s, %s, %s)",
                (nome, versao, Jsonb(valor), publicado_em, por, motivo),
            )
    except pg_errors.UniqueViolation:
        raise ConfigCorrida(f"{nome}: outra versão {versao} foi gravada antes") from None
    except pg_errors.CheckViolation:
        raise ValorInvalido(nome, "o banco recusou o valor (CHECK de config_versao)") from None
    return VersaoConfig(nome, versao, valor, publicado_em, por, motivo)


def _conferir_limites_cruzados(conn: psycopg.Connection, nome: str, valor: Any) -> None:
    for menor, maior in LIMITES_CRUZADOS:
        if nome not in (menor, maior):
            continue
        outro = maior if nome == menor else menor
        vigente = config_vigente(conn, outro)
        valor_menor, valor_maior = (valor, vigente.valor) if nome == menor else (vigente.valor if vigente else None, valor)
        if vigente is not None and valor_menor > valor_maior:
            raise ValorInvalido(nome, f"{menor} não pode passar de {maior}")


def garantir_defaults(conn: psycopg.Connection, relogio: Relogio, *, por: str = "boot:b1.3") -> tuple[str, ...]:
    """No boot: grava `versao=1` (o padrão do registro) de cada chave que ainda não existe. Não toca no que já existe."""
    criadas: list[str] = []
    for nome, padrao in PADROES.items():
        if config_vigente(conn, nome) is None:
            registrar_config(conn, nome, padrao, por, relogio=relogio, motivo="padrão do registro, gravado no boot")
            criadas.append(nome)
    return tuple(criadas)


class LeitorConfig:
    """Leitura de config com cache de até `ttl_s` segundos pelo relógio injetado. Um por processo; a escrita daqui invalida a chave."""

    def __init__(self, relogio: Relogio, ttl_s: float = TTL_CACHE_S) -> None:
        self._relogio = relogio
        self._ttl_s = ttl_s
        self._cache: dict[str, tuple[datetime, VersaoConfig | None]] = {}

    def vigente(self, conn: psycopg.Connection, nome: str) -> VersaoConfig | None:
        agora = self._relogio.agora()
        guardado = self._cache.get(nome)
        if guardado is not None and 0 <= (agora - guardado[0]).total_seconds() < self._ttl_s:
            return guardado[1]
        lida = config_vigente(conn, nome)
        if lida is not None:  # chave ausente não é cacheada: a recém-criada aparece na hora
            self._cache = {**self._cache, nome: (agora, lida)}
        return lida

    def invalidar(self, nome: str) -> None:
        """Descarta a chave do cache. Quem grava DENTRO de uma transação chama de novo DEPOIS do commit: uma leitura concorrente, entre o
        `registrar` e o commit, repõe o valor velho por até `ttl_s` segundos (R1-20)."""
        self._cache = {k: v for k, v in self._cache.items() if k != nome}

    def valor(self, conn: psycopg.Connection, nome: str) -> Any:
        """Valor vigente; se a chave nunca foi gravada, o padrão do registro (None se nem isso)."""
        lida = self.vigente(conn, nome)
        return lida.valor if lida is not None else PADROES.get(nome)

    def registrar(self, conn: psycopg.Connection, nome: str, valor: Any, por: str, **opcoes: Any) -> VersaoConfig:
        nova = registrar_config(conn, nome, valor, por, relogio=self._relogio, **opcoes)
        if conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE:  # gravado de verdade
            self._cache = {**self._cache, nome: (self._relogio.agora(), nova)}
        else:  # o chamador ainda pode dar rollback: nada de cachear versão que talvez não exista
            self._cache = {k: v for k, v in self._cache.items() if k != nome}
        return nova


# --- gasto e recusas de entrada ----------------------------------------------------------------------------------------------------------


def disparos_dia(conn: psycopg.Connection, agora: datetime) -> int:
    """Atendimentos de disparo iniciados no dia local (o `agendamento` nasce de uma conversa do cliente, não de um disparo)."""
    inicio, fim = limites_do_dia(agora)
    linha = conn.execute(
        "SELECT count(*) FROM ia.atendimento WHERE gatilho <> 'agendamento' AND iniciado_em >= %s AND iniciado_em < %s", (inicio, fim)
    ).fetchone()
    return int(linha[0])


def ia_ativa_agora(conn: psycopg.Connection) -> bool:
    """`ia_ativa` lida do banco AGORA, sem o cache do processo: quem executa um job agendado minutos antes (parada leve, `iniciar`,
    volta) decide pelo valor de agora, não pelo de quando o job nasceu (liga → desliga → liga em menos de 19 min)."""
    vigente = config_vigente(conn, "ia_ativa")
    return vigente is not None and vigente.valor is True


def optou_por_sair(conn: psycopg.Connection, pessoa_id: uuid.UUID) -> bool:
    linha = conn.execute(
        "SELECT tipo FROM ia.opt_out WHERE pessoa_id = %s ORDER BY registrado_em DESC, opt_out_id DESC LIMIT 1", (pessoa_id,)
    ).fetchone()
    return linha is not None and linha[0] == "opt_out"


def bloqueio_entrada(
    conn: psycopg.Connection,
    relogio: Relogio,
    pessoa_id: uuid.UUID | None = None,
    *,
    leitor: LeitorConfig | None = None,
    abertura_possivel: bool = True,
) -> str | None:
    """Código da primeira recusa de entrada nova, na ordem de `RECUSAS_DE_ENTRADA`, ou None se pode entrar.

    Só recusa; nunca encerra, repassa nem toca em atendimento aberto ou pausado. Sem `pessoa_id` a regra de opt-out é pulada.
    `abertura_possivel=False` (janela de 24 h do WhatsApp fechada e sem template de abertura aprovado, contrato 08 §8) acrescenta a
    recusa `janela_24h` ENTRE `opt_out` e `teto_atingido`, que é a ordem do catálogo de erros; a API calcula o predicado.
    """
    leitor = leitor or LeitorConfig(relogio, ttl_s=0)
    agora = relogio.agora()

    def cfg(nome: str) -> Any:
        return leitor.valor(conn, nome)

    if cfg("ia_ativa") is not True:
        return "ia_desligada"
    if cfg("bloqueio_entrada") is True:
        return "bloqueio_entrada"
    if not carregar_calendario(cfg("janela_mensagem"), cfg("calendario_bloqueio")).dentro_da_janela(agora):
        return "fora_de_janela"
    if pessoa_id is not None and optou_por_sair(conn, pessoa_id):
        return "opt_out"
    if not abertura_possivel:
        return "janela_24h"
    if gasto_mes(conn, agora) >= Decimal(str(cfg("teto_mensal_brl"))):
        return "teto_atingido"
    if gasto_dia(conn, agora) >= Decimal(str(cfg("subteto_dia"))):
        return "teto_diario"
    if disparos_dia(conn, agora) >= cfg("max_disparos_dia"):
        return "disparos_dia"
    if abertos_agora(conn) >= cfg("max_abertos"):
        return "abertos_max"
    return None


def abertos_agora(conn: psycopg.Connection) -> int:
    """`v_prontidao.abertos`: o que a IA atende AGORA (pausados e agendados ficam fora)."""
    return int(conn.execute("SELECT abertos FROM ia.v_prontidao").fetchone()[0])
