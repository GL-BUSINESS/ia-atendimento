"""Ponto de entrada REAL do worker da fila (R2-02, revisão 2 da B5.7b): `python -m ia_atendimento.worker` (ou `ia-worker`).

Sem isto a proteção da revisão 1 não existia em produção: o `command` do compose chamava `procrastinate worker` direto, sem
`Servicos`, sem a vigia do batimento e com a poda de worker de 30 s. Aqui:

- `Settings` (a mesma validação da API), log de formato fixo (`configurar_logging`), pool de conexões com o `search_path` da fila,
  `Servicos` e `fila.rodar_worker` (reconciliação do bloqueio na subida, concorrência, `stalled_worker_timeout` de 60 s,
  `shutdown_graceful_timeout` de 30 s, vigia do batimento). O job mensal do dia 20 às 21:50 (DATAPREV) é agendado em todo boot (idempotente)
  e as periódicas ficam registradas.
- Os serviços da B1.6 (turno, iniciar, lembrete, repasse, `retomar_atendimento`...) ainda não existem: ficam `_NaoConfigurado` e o
  job que os chama FALHA ALTO (o `retomar` falha antes do CAS). Nada finge que processou.
- Códigos de saída: 0 = parada limpa (SIGTERM/SIGINT); `EXIT_PERDEU_BATIMENTO` (3) = a vigia parou o worker e abortou os jobs em
  voo; 1 = outra falha. O supervisor (`restart: unless-stopped`) reinicia nos dois últimos casos.
- `--saude` (healthcheck do contêiner): sai 0 só se há worker COM BATIMENTO recente no banco (`last_heartbeat` dentro de
  `HEARTBEAT_MAX_S`); importar o pacote não prova nada. Há um worker por implantação: o healthcheck lê a tabela inteira, sem saber
  qual linha é a dele.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from collections.abc import Sequence
from typing import Final

import psycopg
from psycopg_pool import ConnectionPool

from ia_atendimento import fila
from ia_atendimento.api.logs import configurar_logging
from ia_atendimento.chave import LeitorConfig
from ia_atendimento.config import ConfiguracaoInvalida, Settings, get_settings
from ia_atendimento.jobs import Servicos
from ia_atendimento.observabilidade import configurar as configurar_observabilidade
from ia_atendimento.prontidao import HEARTBEAT_MAX_S
from ia_atendimento.relogio import RelogioReal
from ia_atendimento.worker_vivo import WorkerPerdeuOBatimento

log = logging.getLogger(__name__)
EXIT_PERDEU_BATIMENTO: Final = 3
EXIT_SAUDE_RUIM: Final = 1
POOL_MIN: Final = 1
POOL_MAX: Final = 6  # `CONCORRENCIA_PADRAO` (4) jobs + a reconciliação da subida + folga; os handlers abrem a conexão por chamada
_SQL_VIVOS: Final = "SELECT count(*) FROM procrastinate.procrastinate_workers WHERE last_heartbeat >= now() - make_interval(secs => %s)"


def montar_servicos(pool: ConnectionPool) -> Servicos:
    """`Servicos` de produção. Só o que existe (relógio, conexão, config); o resto falha alto até a B1.6 injetá-lo."""
    relogio = RelogioReal()
    return Servicos(relogio=relogio, abrir_conexao=pool.connection, leitor_config=LeitorConfig(relogio))


async def executar(settings: Settings) -> None:
    url = settings.database_url.get_secret_value()
    pool = ConnectionPool(
        fila.conninfo_da_fila(url),
        min_size=POOL_MIN,
        max_size=POOL_MAX,
        kwargs={"autocommit": True},
        check=ConnectionPool.check_connection,
        open=False,
    )
    pool.open(wait=True, timeout=15)
    try:
        app = fila.criar_app(url, com_periodicas=True)
        async with app.open_async():
            await fila.agendar_bloqueio_dataprev(app, RelogioReal())
            await fila.rodar_worker(app, montar_servicos(pool))
    finally:
        pool.close()


def saude(database_url: str | None = None) -> int:
    """Healthcheck: 0 se algum worker bateu o coração nos últimos `HEARTBEAT_MAX_S`, senão 1. Imprime só `ok`/o motivo, nunca a URL."""
    url = database_url or os.environ.get("DATABASE_URL", "")
    if not url:
        print("sem DATABASE_URL")
        return EXIT_SAUDE_RUIM
    try:
        with psycopg.connect(fila.conninfo_da_fila(url), autocommit=True, connect_timeout=5) as conn:
            vivos = conn.execute(_SQL_VIVOS, (HEARTBEAT_MAX_S,)).fetchone()[0]
    except (psycopg.Error, ValueError) as erro:
        print(f"banco inalcancavel ({type(erro).__name__})")
        return EXIT_SAUDE_RUIM
    print("ok" if vivos else "sem batimento recente")
    return 0 if vivos else EXIT_SAUDE_RUIM


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ia-worker", description="Worker da fila do orquestrador da IA de atendimento")
    parser.add_argument("--saude", action="store_true", help="healthcheck: sai 0 só com batimento de worker recente no banco")
    args = parser.parse_args(argv)
    if args.saude:
        return saude()
    configurar_logging()
    try:
        settings = get_settings()
    except ConfiguracaoInvalida as erro:
        log.error("configuração inválida: %s", erro)
        return 1
    configurar_observabilidade(settings)  # G-0085: máscara de PII em TODO log do processo (Procrastinate, psycopg_pool...) e segredos
    try:
        asyncio.run(executar(settings))
    except WorkerPerdeuOBatimento as erro:
        log.error("worker parado pela vigia do batimento (%s): o supervisor deve reiniciá-lo", erro)
        return EXIT_PERDEU_BATIMENTO
    return 0


if __name__ == "__main__":
    sys.exit(main())
