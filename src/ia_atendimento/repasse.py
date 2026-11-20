"""Repasse por etapas persistidas (B1.6b; contrato 08 §7.1 e §7.2; D-14, D-15, R-c2 do lado do orquestrador).

Fase 1 (`iniciar_repasse`): CAS `aberto|aguardando_cliente|pausado → repassando` (o chat fica trancado, mensagens não enfileiram turno).
Fase 2 (`executar_repasse`, o job `repasse`): **nota → chatbot → rota → marca → lease**, cada etapa um passo `repasse` com `resultado`
(`ok|transitorio|incerto|pulado`); o job retoma pelo primeiro marco sem desfecho, então a nota que saiu nunca se repete e o chatbot
restaurado idem (o ledger garante o mesmo por baixo).

- **Sem posse real** (nasceu `sombra|duble`, ou o `assumir` nunca fechou `ok`): as cinco etapas são simuladas, sem porta nenhuma, e o
  atendimento fecha `sem_venda/repasse_simulado` (08 §6, exceção 2).
- **Batimento** (08 §7.4, R2-03): consultado antes da nota e antes do chatbot enquanto a rota não teve tentativa. `impedido` ⇒
  `encerrado(repassado, devolvido_pela_s2)` sem nota, sem restaurar, sem rota. `indisponivel` ⇒ fail-closed (D-15): nada sai e o job
  espera um batimento válido, dentro do mesmo prazo de D-14.
- **Prazo D-14**: espera total ≤ 30 min desde a 1ª execução do job (`desde`, levado pelo reagendamento). Backoff 10 s, 30 s, 90 s,
  4 min e depois 5 min. Esgotado ⇒ código `repasse_travado` em `contexto_codigos`, passo, alerta crítico e alerta `humano` (o lead
  precisa de uma pessoa: G-0020, G-0032), e o job PARA; o atendimento fica `repassando`. `repasses_travados()` é a lista que a vigia lê
  na R-c2 (a regra da vigia e a rota que a expõe são da B6.4, decisão do dono DN-28).
- **Rota**: a porta `PortaRepasse` (o `ia-repasse`). O adaptador real NÃO existe aqui: o caminho `ia-repasse → zVuE` está morto em
  produção desde 30/10 e a delegação real depende de DEC-PIA-002. Resultado do n8n vai em `ref_externa` do ledger (`t12:{atd}`,
  idempotente por `repasse_id`, 08 §7.1).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final, Protocol

import psycopg

from ia_atendimento import espelho, estado
from ia_atendimento.alertas import Alertas
from ia_atendimento.batimento import LeitorBatimento
from ia_atendimento.canal import BatimentoIndisponivel, Canal, CercoFechado, efeito_seria_real
from ia_atendimento.chave import LeitorConfig
from ia_atendimento.estado import MOTIVO_DEVOLVIDO_S2, Mudancas, aplicar
from ia_atendimento.estado_erros import AtendimentoInexistente, TransicaoInvalida
from ia_atendimento.ledger import Desfecho, Pedido, ResultadoEfeito, executar_efeito
from ia_atendimento.linha_tempo import CtxPasso, gravar_passo
from ia_atendimento.passos import Repasse
from ia_atendimento.relogio import Relogio

PRAZO: Final = timedelta(minutes=30)  # D-14
BACKOFF_S: Final = (10, 30, 90, 240)
BACKOFF_DEPOIS_S: Final = 300
ESPERA_BATIMENTO_S: Final = 15  # o batimento é relido a cada 15 s
EM_VOO_S: Final = 10  # outra execução está no meio do efeito: volta logo
MODO_DO_REPASSE: Final = "indicado"  # 08 §7.1 (RG-009): todo repasse sem venda que não seja `nenhum`
MOTIVO_SIMULADO: Final = "repasse_simulado"
CODIGO_TRAVADO: Final = "repasse_travado"
CODIGO_SEM_CONSULTOR: Final = "repasse_sem_consultor"
TERMINAIS: Final = frozenset({"delegou", "fechado_sem_delegar", "ja_devolvido", "sem_consultor", "desconhecido"})
TRANSITORIOS: Final = frozenset({"em_andamento", "falha_transitoria"})
RESPOSTA_INVALIDA: Final = "invalida"
DESFECHOS_DA_ETAPA: Final = frozenset({"ok", "pulado", "incerto"})  # a etapa terminou (o `transitorio` repete)
TAMANHO_MAX_NOTA: Final = 400
MOTIVO_HUMANO_ASSUMIU: Final = "humano_assumiu"  # `encerrar` exige o instante junto (revisão B1.6b, achado 8)
_CODIGO_MOTIVO: Final = re.compile(r"^[a-z0-9_]{1,60}$")
MOTIVO_PADRAO: Final = "repasse"


def motivo_valido(motivo: str | None) -> str:
    """O motivo do repasse vai ao `motivo_desfecho` (Codigo60): fora da forma vira `repasse`, nunca derruba a fase 1."""
    return motivo if motivo is not None and _CODIGO_MOTIVO.fullmatch(motivo) else MOTIVO_PADRAO


class PortaRepasse(Protocol):
    """O `ia-repasse` (01 §4.2). Devolve o `resultado` do n8n; exceção ou timeout = sem resposta (transitório)."""

    async def rotear(self, atendimento_id: uuid.UUID, destino: str, corpo: dict[str, Any]) -> str: ...


@dataclass(frozen=True)
class Reagendar:
    atraso_s: float
    desde: datetime


@dataclass(frozen=True)
class Linha:
    atendimento_id: uuid.UUID
    estado: str
    modo: str
    versao: int
    chave: str
    chat_id: str
    motivo_desfecho: str | None
    chatbot_estado: str
    mensagens_enviadas: int
    turnos: int
    contexto_codigos: tuple[str, ...]


def nota_padrao(linha: Linha) -> str | None:
    """Sem mensagem da IA ao cliente não há o que contar ao vendedor (`nao_aplica`). O texto real (TX-34) vem do catálogo de textos."""
    if linha.mensagens_enviadas == 0:
        return None
    return "A IA conversou com o cliente e devolveu o atendimento a você."


@dataclass(frozen=True)
class DepsRepasse:
    canal: Canal
    rota: PortaRepasse
    batimento: LeitorBatimento
    alertas: Alertas
    leitor: LeitorConfig
    relogio: Relogio
    texto_da_nota: Callable[[Linha], str | None] = nota_padrao
    timeout_rota_s: float = 10.0


# --- leitura ---------------------------------------------------------------------------------------------------------------------------

_SQL_LINHA: Final = """
SELECT atendimento_id, estado, modo, versao, chave_logica, chat_id, motivo_desfecho, chatbot_estado, mensagens_enviadas, turnos,
  contexto_codigos FROM ia.atendimento WHERE atendimento_id = %s
"""


def ler_linha(conn: psycopg.Connection, atd: uuid.UUID, *, travar: bool = False) -> Linha | None:
    linha = conn.execute(_SQL_LINHA + (" FOR UPDATE" if travar else ""), (atd,)).fetchone()
    if linha is None:
        return None
    return Linha(*linha[:10], tuple(linha[10]))


def etapas_feitas(conn: psycopg.Connection, atd: uuid.UUID) -> dict[str, tuple[str, str | None]]:
    """O último marco de cada etapa: {etapa: (resultado, motivo)}."""
    feitas: dict[str, tuple[str, str | None]] = {}
    for etapa, resultado, motivo in conn.execute(
        "SELECT repasse_etapa, resultado, motivo FROM ia.passo WHERE atendimento_id = %s AND tipo = 'repasse' ORDER BY ordem", (atd,)
    ):
        feitas[etapa] = (resultado, motivo)
    return feitas


def _contar(conn: psycopg.Connection, atd: uuid.UUID, etapa: str, resultado: str) -> int:
    return conn.execute(
        "SELECT count(*) FROM ia.passo WHERE atendimento_id = %s AND tipo = 'repasse' AND repasse_etapa = %s AND resultado = %s",
        (atd, etapa, resultado),
    ).fetchone()[0]


def _primeira_rota(conn: psycopg.Connection, atd: uuid.UUID) -> datetime | None:
    linha = conn.execute(
        "SELECT reservada_em FROM ia.ferramenta_chamada WHERE atendimento_id = %s AND ferramenta = 't12'", (atd,)
    ).fetchone()
    return linha[0] if linha else None


def repasses_travados(conn: psycopg.Connection) -> list[str]:
    """R-c2 (lado do orquestrador): as chaves `repassando` que o job deixou de tentar. A vigia devolve por `indicado` (B6.4)."""
    return [
        r[0]
        for r in conn.execute(
            "SELECT chave_logica FROM ia.atendimento WHERE estado = 'repassando' AND %s = ANY(contexto_codigos) ORDER BY atualizado_em",
            (CODIGO_TRAVADO,),
        )
    ]


_SQL_SEM_JOB: Final = """
SELECT a.atendimento_id, a.chat_id FROM ia.atendimento a
WHERE a.estado = 'repassando' AND NOT (%(travado)s = ANY(a.contexto_codigos)) AND a.atualizado_em < %(antes)s
  AND NOT EXISTS (SELECT 1 FROM procrastinate.procrastinate_jobs j WHERE j.queueing_lock = 'repasse:' || a.atendimento_id
                  AND j.status IN ('todo', 'doing'))
ORDER BY a.atualizado_em LIMIT %(limite)s
"""
FOLGA_SEM_JOB: Final = timedelta(minutes=2)


def repasses_sem_job(conn: psycopg.Connection, agora: datetime, limite: int = 100) -> list[tuple[uuid.UUID, str]]:
    """Revisão B1.6b, achado 1: `repassando` sem job `repasse` vivo (o worker morreu entre a fase 1 e o defer, ou o job esgotou o retry)
    e sem `repasse_travado`. O varredor periódico reenfileira; o prazo de D-14 recomeça (o `desde` se perdeu com o job)."""
    parametros = {"travado": CODIGO_TRAVADO, "antes": agora - FOLGA_SEM_JOB, "limite": limite}
    return [(r[0], r[1]) for r in conn.execute(_SQL_SEM_JOB, parametros)]


# --- fase 1 ----------------------------------------------------------------------------------------------------------------------------


def iniciar_repasse(conn: psycopg.Connection, atd: uuid.UUID, *, motivo: str, relogio: Relogio, versao: int | None = None) -> int:
    """`aberto|aguardando_cliente|pausado → repassando` (CAS). Quem chama enfileira o job `repasse` na mesma transação, se puder."""
    if versao is None:
        linha = ler_linha(conn, atd)
        if linha is None:
            raise AtendimentoInexistente("atendimento inexistente")
        versao = linha.versao
    motivo = motivo_valido(motivo)
    humano = relogio.agora() if motivo == MOTIVO_HUMANO_ASSUMIU else None
    return estado.repassar(conn, atd, versao, modo=MODO_DO_REPASSE, motivo=motivo, humano_assumiu_em=humano, relogio=relogio.agora)


# --- escrita dos marcos ----------------------------------------------------------------------------------------------------------------


def _passo(conn: psycopg.Connection, linha: Linha, etapa: str, resultado: str, motivo: str | None = None) -> None:
    gravar_passo(
        conn, linha.atendimento_id, ctx=CtxPasso.criar(turno=linha.turnos, fase="E10"),
        dados=Repasse(repasse_etapa=etapa, resultado=resultado, motivo=motivo),
    )  # fmt: skip


def _aplicar(conn: psycopg.Connection, atd: uuid.UUID, agora: datetime, **campos: Any) -> None:
    linha = ler_linha(conn, atd, travar=True)
    if linha is None or linha.estado != "repassando":
        raise TransicaoInvalida("o atendimento saiu de repassando no meio do repasse")
    aplicar(conn, atd, linha.versao, Mudancas(**campos), agora=agora, de={"repassando"})


def _humano_assumiu_em(conn: psycopg.Connection, atd: uuid.UUID, agora: datetime) -> datetime:
    """O instante gravado na fase 1 (o `encerrar` o regrava junto do motivo); sem ele, agora."""
    linha = conn.execute("SELECT humano_assumiu_em FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()
    return linha[0] if linha and linha[0] is not None else agora


def _encerrar(
    conn: psycopg.Connection, linha: Linha, *, desfecho: str, motivo: str, evento: espelho.DesfechoEspelho, agora: datetime, codigos=()
) -> None:
    with conn.transaction():
        atual = ler_linha(conn, linha.atendimento_id, travar=True)
        if atual is None or atual.estado == "encerrado":
            return
        estado.encerrar(
            conn, linha.atendimento_id, atual.versao, desfecho=desfecho, motivo=motivo,
            contexto_codigos=tuple(dict.fromkeys((*atual.contexto_codigos, *codigos))), relogio=lambda: agora,
            humano_assumiu_em=_humano_assumiu_em(conn, linha.atendimento_id, agora) if motivo == MOTIVO_HUMANO_ASSUMIU else None,
        )  # fmt: skip
        espelho.emitir_encerrou(conn, linha.atendimento_id, evento, agora)


def encerrar_devolvido_pela_s2(conn: psycopg.Connection, linha: Linha, agora: datetime) -> None:
    """A S2 já tomou o lead (impedidos ou `ja_devolvido`): fecha sem nota, sem restaurar, sem rota."""
    desfecho = "sem_venda" if linha.modo == "sombra" else "repassado"  # `atendimento_sombra_check`: sombra nunca fecha `repassado`
    with conn.transaction():
        _passo(conn, linha, "cerco", "ok", MOTIVO_DEVOLVIDO_S2)
        _encerrar(conn, linha, desfecho=desfecho, motivo=MOTIVO_DEVOLVIDO_S2, evento="devolvido_pela_s2", agora=agora)


def _travar(conn: psycopg.Connection, linha: Linha, etapa: str, deps: DepsRepasse, agora: datetime) -> None:
    """D-14 esgotado: o orquestrador para de tentar e o lead vai para a recuperação humana (alerta `humano`) e para a vigia (R-c2)."""
    with conn.transaction():
        atual = ler_linha(conn, linha.atendimento_id, travar=True)
        if atual is None or atual.estado != "repassando":
            return
        if CODIGO_TRAVADO not in atual.contexto_codigos:
            _aplicar(conn, linha.atendimento_id, agora, contexto_codigos=(*atual.contexto_codigos, CODIGO_TRAVADO))
        _passo(conn, linha, etapa, "transitorio", CODIGO_TRAVADO)
    deps.alertas.alertar("critico", CODIGO_TRAVADO, atendimento_id=linha.atendimento_id)
    deps.alertas.alertar("humano", CODIGO_TRAVADO, atendimento_id=linha.atendimento_id)


def backoff_s(tentativas: int) -> float:
    return float(BACKOFF_S[tentativas - 1] if 1 <= tentativas <= len(BACKOFF_S) else BACKOFF_DEPOIS_S)


def _esperar_ou_travar(
    conn: psycopg.Connection, linha: Linha, etapa: str, deps: DepsRepasse, *, inicio: datetime, desde: datetime, atraso_s: float
) -> Reagendar | None:
    """A próxima tentativa só é marcada se cabe no prazo de D-14; a que não cabe vira `repasse_travado` agora (a 1ª + 8 repetições,
    a última aos ≈ 26 min, 08 §7.2)."""
    agora = deps.relogio.agora()
    if agora + timedelta(seconds=atraso_s) - inicio > PRAZO:
        _travar(conn, linha, etapa, deps, agora)
        return None
    return Reagendar(atraso_s, desde)


# --- etapas ----------------------------------------------------------------------------------------------------------------------------


def _simular(conn: psycopg.Connection, linha: Linha, agora: datetime) -> None:
    """Sem posse real: as cinco etapas simuladas (nada chama porta nenhuma) e `sem_venda/repasse_simulado`."""
    with conn.transaction():
        for etapa in ("nota", "chatbot", "rota", "marca", "lease"):
            _passo(conn, linha, etapa, "ok", MOTIVO_SIMULADO)
        _encerrar(conn, linha, desfecho="sem_venda", motivo=MOTIVO_SIMULADO, evento="sem_venda", agora=agora)


async def _nota(conn: psycopg.Connection, linha: Linha, deps: DepsRepasse) -> ResultadoEfeito | None:
    """UMA chamada, sem retry próprio (02 §5 i). 200 ⇒ `sim`; sem resposta ⇒ `incerta` (nunca repete); recusa ⇒ segue sem nota."""
    texto = (deps.texto_da_nota(linha) or "").strip() or None
    agora = deps.relogio.agora()
    if texto is None:
        with conn.transaction():
            _aplicar(conn, linha.atendimento_id, agora, repasse_nota_enviada=False)
            _passo(conn, linha, "nota", "pulado", "nao_aplica")
        return None
    texto = texto[:TAMANHO_MAX_NOTA]
    r = await deps.canal.nota(conn, linha.atendimento_id, texto=texto)
    if r.estado == "enviada":
        return r
    with conn.transaction():
        if r.estado == "ok":
            _aplicar(conn, linha.atendimento_id, agora, repasse_nota_enviada=True, nota_repasse_tamanho=len(texto))
            _passo(conn, linha, "nota", "ok", "sim")
        elif r.estado == "indeterminado":
            _aplicar(conn, linha.atendimento_id, agora, repasse_nota_enviada=True, nota_repasse_tamanho=len(texto))
            _passo(conn, linha, "nota", "incerto", "incerta")
        else:
            _aplicar(conn, linha.atendimento_id, agora, repasse_nota_enviada=False)
            _passo(conn, linha, "nota", "pulado", "nota_nao_entregue")
    if r.estado not in ("ok", "indeterminado"):
        deps.alertas.alertar("amarelo", "nota_nao_entregue", atendimento_id=linha.atendimento_id)
    return r


async def _chatbot(conn: psycopg.Connection, linha: Linha, deps: DepsRepasse) -> str:
    """`Canal.restaurar` com retry próprio (repete com a mesma chave). Devolve `ok|pulado|transitorio|enviada`."""
    if linha.chatbot_estado == "intocado":
        _passo(conn, linha, "chatbot", "pulado", "intocado")
        return "pulado"
    r = await deps.canal.restaurar(conn, linha.atendimento_id)
    if r.estado in ("enviada", "transitorio"):
        if r.estado == "transitorio":
            _passo(conn, linha, "chatbot", "transitorio", "restaurar_transitorio")
        return r.estado
    agora = deps.relogio.agora()
    with conn.transaction():
        if r.estado == "ok":
            _aplicar(conn, linha.atendimento_id, agora, chatbot_estado="restaurado")
            _passo(conn, linha, "chatbot", "ok", "restaurado")
        else:
            _aplicar(conn, linha.atendimento_id, agora, chatbot_estado="nao_confirmou")
            _passo(conn, linha, "chatbot", "pulado", "chatbot_nao_restaurado")
    if r.estado != "ok":
        deps.alertas.alertar("critico", "chatbot_nao_restaurado", atendimento_id=linha.atendimento_id)
    return "ok" if r.estado == "ok" else "pulado"


def _nota_enviada(feitas: dict[str, tuple[str, str | None]]) -> str:
    resultado, motivo = feitas.get("nota", ("pulado", "nao_aplica"))
    return {"ok": "sim", "incerto": "incerta"}.get(resultado, "nao_aplica" if motivo == "nao_aplica" else "nao")


def _corpo(linha: Linha, nota_enviada: str, agora: datetime) -> dict[str, Any]:
    """Sem `chat_number`, sem `pessoa_id`, sem CPF (aceito do 04). `consultor` sempre nulo no MVP (R2-13)."""
    return {
        "idempotency_key": f"repasse:{linha.atendimento_id}", "chave": linha.chave, "chat_id": linha.chat_id, "desfecho": "sem_venda",
        "motivo_curto": linha.motivo_desfecho, "modo": MODO_DO_REPASSE, "consultor": None, "encerrado_em": agora.isoformat(),
        "nota_enviada": nota_enviada,
    }  # fmt: skip


async def _rota(conn: psycopg.Connection, linha: Linha, deps: DepsRepasse, nota_enviada: str) -> ResultadoEfeito:
    corpo = _corpo(linha, nota_enviada, deps.relogio.agora())

    async def chamar(destino: str) -> Desfecho:
        resultado = await deps.rota.rotear(linha.atendimento_id, destino, corpo)
        if resultado in TERMINAIS:
            return Desfecho("ok", ref_externa=resultado)
        if resultado in TRANSITORIOS:
            return Desfecho("transitorio", ref_externa=resultado)
        return Desfecho("recusa", ref_externa=RESPOSTA_INVALIDA)

    pedido = Pedido(ferramenta="t12", ferramenta_versao="1.0.0", classe_efeito="acao_interna", chave_logica=f"t12:{linha.atendimento_id}",
                    devolucao=True)  # fmt: skip
    return await executar_efeito(
        conn, linha.atendimento_id, pedido, chamar=chamar, leitor=deps.leitor, relogio=deps.relogio, timeout_s=deps.timeout_rota_s
    )


def _marcar(conn: psycopg.Connection, linha: Linha, resultado: str, deps: DepsRepasse) -> None:
    agora = deps.relogio.agora()
    if resultado == "ja_devolvido":
        encerrar_devolvido_pela_s2(conn, linha, agora)
        return
    codigos = (CODIGO_SEM_CONSULTOR,) if resultado in ("sem_consultor", "desconhecido") else ()
    with conn.transaction():
        _passo(conn, linha, "marca", "ok", resultado)
        _passo(conn, linha, "lease", "ok")
        _encerrar(conn, linha, desfecho="repassado", motivo=linha.motivo_desfecho or "repasse", evento="repassado", agora=agora,
                  codigos=codigos)  # fmt: skip
    if codigos:
        deps.alertas.alertar("critico", CODIGO_SEM_CONSULTOR, atendimento_id=linha.atendimento_id)


# --- o job -----------------------------------------------------------------------------------------------------------------------------


async def executar_repasse(conn: psycopg.Connection, atd: uuid.UUID, deps: DepsRepasse, desde: datetime | None = None) -> Reagendar | None:
    """Uma rodada do job `repasse`. `None` = terminou (encerrado, travado ou fora de `repassando`); `Reagendar` = chamar de novo com o
    mesmo `desde` depois de `atraso_s`. `conn` em autocommit (o ledger exige)."""
    agora = deps.relogio.agora()
    desde = desde or agora
    linha = ler_linha(conn, atd)
    if linha is None or linha.estado != "repassando":
        return None
    if not efeito_seria_real(conn, atd, deps.leitor, devolucao=True):
        _simular(conn, linha, agora)
        return None
    feitas = etapas_feitas(conn, atd)
    if _primeira_rota(conn, atd) is None:
        parar = await _antes_da_rota(conn, linha, feitas, deps, desde)
        if parar is not False:
            return parar
        feitas = etapas_feitas(conn, atd)
    return await _rodar_rota(conn, linha, feitas, deps, desde)


async def _antes_da_rota(
    conn: psycopg.Connection, linha: Linha, feitas: dict[str, tuple[str, str | None]], deps: DepsRepasse, desde: datetime
) -> Reagendar | bool | None:
    """Nota e chatbot, cada um atrás do batimento. `False` = seguir para a rota."""
    for etapa in ("nota", "chatbot"):
        if feitas.get(etapa, ("",))[0] in DESFECHOS_DA_ETAPA:
            continue
        situacao = deps.batimento.situacao(linha.chave, atendimento_id=linha.atendimento_id)
        if situacao == "impedido":
            encerrar_devolvido_pela_s2(conn, linha, deps.relogio.agora())
            return None
        if situacao == "indisponivel":
            return _esperar_ou_travar(conn, linha, "cerco", deps, inicio=desde, desde=desde, atraso_s=ESPERA_BATIMENTO_S)
        try:
            resultado = await (_nota(conn, linha, deps) if etapa == "nota" else _chatbot(conn, linha, deps))
        except CercoFechado:
            encerrar_devolvido_pela_s2(conn, linha, deps.relogio.agora())
            return None
        except BatimentoIndisponivel:
            return _esperar_ou_travar(conn, linha, "cerco", deps, inicio=desde, desde=desde, atraso_s=ESPERA_BATIMENTO_S)
        if resultado == "enviada" or (isinstance(resultado, ResultadoEfeito) and resultado.estado == "enviada"):
            return Reagendar(EM_VOO_S, desde)
        if resultado == "transitorio":
            n = _contar(conn, linha.atendimento_id, "chatbot", "transitorio")
            return _esperar_ou_travar(conn, linha, "chatbot", deps, inicio=desde, desde=desde, atraso_s=backoff_s(n))
    situacao = deps.batimento.situacao(linha.chave, atendimento_id=linha.atendimento_id)  # e uma vez antes da 1ª rota (D-15)
    if situacao == "impedido":
        encerrar_devolvido_pela_s2(conn, linha, deps.relogio.agora())
        return None
    if situacao == "indisponivel":
        return _esperar_ou_travar(conn, linha, "cerco", deps, inicio=desde, desde=desde, atraso_s=ESPERA_BATIMENTO_S)
    return False


async def _rodar_rota(
    conn: psycopg.Connection, linha: Linha, feitas: dict[str, tuple[str, str | None]], deps: DepsRepasse, desde: datetime
) -> Reagendar | None:
    """Depois da 1ª tentativa o batimento não é mais consultado (08 §7.1): vale a resposta idempotente do n8n."""
    r = await _rota(conn, linha, deps, _nota_enviada(feitas))
    if r.estado == "enviada":
        return Reagendar(EM_VOO_S, desde)
    resultado = r.ref_externa or ""
    if r.estado == "ok" and resultado in TERMINAIS:
        _passo(conn, linha, "rota", "ok", resultado)
        _marcar(conn, linha, resultado, deps)
        return None
    if r.estado == "recusa" or resultado == RESPOSTA_INVALIDA:
        deps.alertas.alertar("critico", "repasse_resposta_invalida", atendimento_id=linha.atendimento_id)
        _travar(conn, linha, "rota", deps, deps.relogio.agora())
        return None
    _passo(conn, linha, "rota", "transitorio", resultado if resultado in TRANSITORIOS else "sem_resposta")
    n = _contar(conn, linha.atendimento_id, "rota", "transitorio")
    if n == 1:
        deps.alertas.alertar("amarelo", "repasse_falhou", atendimento_id=linha.atendimento_id)
    inicio = min(desde, _primeira_rota(conn, linha.atendimento_id) or desde)  # D-14: ≤ 30 min desde o 1º pedido
    return _esperar_ou_travar(conn, linha, "rota", deps, inicio=inicio, desde=desde, atraso_s=backoff_s(n))
