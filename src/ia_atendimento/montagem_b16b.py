"""Montagem dos serviços da B1.6b sobre os `Servicos` do worker (processador, repasse, desligamento, reaper do ledger, publicador).

Recebe as PORTAS prontas (Canal, `ia-repasse`, espelho, batimento, motor e alertas). **Em produção ainda não há adaptador real de
nenhuma delas** (a delegação real depende de DEC-PIA-002; a hospedagem da IA vai para a S5, a configurar): o `worker.montar_servicos`
NÃO chama esta montagem, e os jobs que dependem dela seguem falhando alto (`ServicoNaoConfigurado`). Os testes a usam com portas falsas.
"""

from __future__ import annotations

import asyncio
import dataclasses
import uuid
from datetime import datetime
from typing import Any

import procrastinate

from ia_atendimento import expiracao, fila, processador, publicar_espelho, reaper_ledger, repasse
from ia_atendimento.alertas import Alertas
from ia_atendimento.batimento import LeitorBatimento
from ia_atendimento.canal import Canal, PortaCanal
from ia_atendimento.gasto import MedidorGasto
from ia_atendimento.jobs import Servicos


@dataclasses.dataclass(frozen=True)
class Portas:
    canal: PortaCanal
    rota: repasse.PortaRepasse
    espelho: publicar_espelho.PortaEspelho
    batimento: LeitorBatimento
    motor: processador.Motor
    alertas: Alertas


def _chat(servicos: Servicos, atd: uuid.UUID) -> str:
    with servicos.abrir_conexao() as conn:
        return conn.execute("SELECT chat_id FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()[0]


def montar(base: Servicos, portas: Portas, app: procrastinate.App | None = None) -> Servicos:
    """`app` = a fila (enfileira o repasse e o turno que pede nova tentativa); sem ela, só nos testes, o repasse não é enfileirado."""
    relogio, leitor = base.relogio, base.leitor()
    canal = Canal(portas.canal, portas.batimento, leitor=leitor, relogio=relogio)
    medidor = MedidorGasto(relogio)

    async def enfileirar_repasse(atd: uuid.UUID) -> None:
        if app is not None:
            await fila.enfileirar_repasse(app, atd, await asyncio.to_thread(_chat, base, atd))

    deps_proc = processador.DepsProcessador(
        canal, portas.motor, portas.batimento, portas.alertas, leitor, relogio, enfileirar_repasse, medidor=medidor
    )
    deps_rep = repasse.DepsRepasse(canal, portas.rota, portas.batimento, portas.alertas, leitor, relogio)
    deps_esp = publicar_espelho.DepsEspelho(portas.espelho, portas.alertas, relogio)

    async def com_conexao(funcao: Any, *args: Any) -> Any:
        with base.abrir_conexao() as conn:
            return await funcao(conn, *args)

    async def reagendar_turno(atd: uuid.UUID, r: processador.Resultado) -> None:
        if app is not None and r.reagendar_s:
            await fila.enfileirar_turno(app, atd, await asyncio.to_thread(_chat, base, atd), rajada_s=r.reagendar_s)

    async def processar_turno(atd: uuid.UUID) -> None:
        await reagendar_turno(atd, await com_conexao(processador.processar, atd, deps_proc))

    async def iniciar_atendimento(atd: uuid.UUID) -> None:
        await com_conexao(processador.iniciar, atd, deps_proc)

    async def encerrar_por_chave(atd: uuid.UUID) -> None:
        await com_conexao(processador.encerrar_por_chave, atd, deps_proc)

    async def repassar(atd: uuid.UUID, desde: datetime | None) -> repasse.Reagendar | None:
        return await com_conexao(repasse.executar_repasse, atd, deps_rep, desde)

    async def varrer() -> reaper_ledger.Varredura:
        def _varrer() -> reaper_ledger.Varredura:
            with base.abrir_conexao() as conn:
                return reaper_ledger.varrer_ledger(conn, relogio.agora(), portas.alertas)

        return await asyncio.to_thread(_varrer)

    async def publicar() -> int:
        return await com_conexao(publicar_espelho.publicar_espelho, deps_esp)

    montado = dataclasses.replace(
        base,
        processar_turno=processar_turno,
        iniciar_atendimento=iniciar_atendimento,
        encerrar_por_chave=encerrar_por_chave,
        repassar=repassar,
        enfileirar_repasse=enfileirar_repasse,
        reaper_ledger=varrer,
        publicar_espelho=publicar,
    )
    return dataclasses.replace(montado, expirar_parados=lambda: expiracao.executar_expirar_parados(montado))
