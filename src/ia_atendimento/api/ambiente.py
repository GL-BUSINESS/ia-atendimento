"""Montagem de produção: `Settings` + arquivos de segredo + pool de conexões + fila, num `ContextoApi`.

Uso (OPERACAO.md §8): `uvicorn --factory ia_atendimento.api.ambiente:criar_app_de_ambiente --host 10.90.0.5 --port 8000 --no-access-log`.
Faltou segredo obrigatório, arquivo aberto demais, chave inválida ou fixture malformada ⇒ falha NA SUBIDA, com a regra e nunca o valor.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg_pool import ConnectionPool

from ia_atendimento import fila, migracoes
from ia_atendimento.api.app import criar_app
from ia_atendimento.api.contexto import ContextoApi, PreVooComCache, PreVooLivre
from ia_atendimento.api.logs import configurar_logging
from ia_atendimento.chave import LeitorConfig
from ia_atendimento.cifra import Chaveiro
from ia_atendimento.config import ConfiguracaoInvalida, Settings, get_settings
from ia_atendimento.enfileirador import EnfileiradorProcrastinate
from ia_atendimento.evento_mensagem import ChavesDeMensagem
from ia_atendimento.observabilidade import configurar as configurar_observabilidade
from ia_atendimento.observabilidade import registrar_segredo
from ia_atendimento.pessoas_teste import carregar as carregar_pessoas_teste
from ia_atendimento.relogio import RelogioReal
from ia_atendimento.segredos import carregar_gateway_hmac, carregar_segredos_de_saida

RAIZ = Path(__file__).resolve().parents[3]
POOL_MIN = 1
POOL_MAX = 8
TEMPOS_DE_SESSAO = "-c lock_timeout=2000 -c statement_timeout=5000 -c idle_in_transaction_session_timeout=10000"
POOL_ESPERA_S = 5.0  # sem conexão livre em 5 s ⇒ PoolTimeout ⇒ 503 `nao_pronto` (o gateway/ChatGuru repete)


def criar_app_de_ambiente() -> FastAPI:
    configurar_logging()  # o uvicorn não configura o logger da aplicação: sem isto a linha `req trace=…` e os alertas não saem (R2-03)
    settings = get_settings()
    configurar_observabilidade(settings)  # G-0085: sem isto a máscara de logs e o registro de segredos nunca ligavam em produção
    return _montar(settings)


def conninfo_do_pool(database_url: str) -> str:
    """Conninfo do pool da API: o `search_path` da fila mais os tempos-limite de sessão (R2-08).

    Sem `lock_timeout`, uma espera por `FOR UPDATE` ou pela trava advisory segurava uma das 8 conexões sem limite; vencido, vira
    `LockNotAvailable` (OperationalError ⇒ 503 `nao_pronto`, e o n8n repete)."""
    base = fila.conninfo_da_fila(database_url)
    options = conninfo_to_dict(base).get("options", "")
    return make_conninfo(base, options=f"{options} {TEMPOS_DE_SESSAO}".strip())


def _exigir_url_pura(database_url: str) -> None:
    """`postgresql+psycopg://` (dialeto do SQLAlchemy) passa no `Settings`, mas o `/readyz` entrega a URL crua ao libpq e ficaria em 503
    `erro_de_consulta` para sempre enquanto o resto funciona (R2-04). Falha na subida, sem citar a URL."""
    esquema = database_url.split("://", 1)[0]
    if "+" in esquema:
        raise ConfiguracaoInvalida("database_url: a API exige o esquema puro postgresql:// (sem +dialeto, como +psycopg)")


def _montar(settings: Settings) -> FastAPI:
    relogio = RelogioReal()
    url = settings.database_url.get_secret_value()
    _exigir_url_pura(url)
    pool = ConnectionPool(
        conninfo_do_pool(url), min_size=POOL_MIN, max_size=POOL_MAX, timeout=POOL_ESPERA_S, kwargs={"autocommit": True},
        check=ConnectionPool.check_connection, open=False,
    )  # fmt: skip
    app_fila = fila.criar_app(url, com_periodicas=False)
    gateway_hmac = carregar_gateway_hmac(settings.gateway_hmac_arquivo)
    segredos_de_saida = carregar_segredos_de_saida(settings.segredos_saida_arquivo)
    for segredo in (*(c.decode("ascii") for c in gateway_hmac), *vars(segredos_de_saida).values()):
        registrar_segredo(segredo)  # dos arquivos 0600: também viram [SEGREDO] em log e span (revisão dos altos, M3)
    contexto = ContextoApi(
        settings=settings, relogio=relogio, conexao=pool.connection, leitor=LeitorConfig(relogio),
        chaveiro=Chaveiro.de_arquivo(settings.chave_aes_arquivo, settings.chave_aes_id),
        chaves_msg=ChavesDeMensagem.de_settings(settings), enfileirador=EnfileiradorProcrastinate(app_fila),
        tokens={origem: token.get_secret_value().encode() for origem, token in settings.api_tokens.items()},
        gateway_hmac=gateway_hmac,
        pessoas_teste=carregar_pessoas_teste(settings.pessoas_teste_arquivo),
        segredos_de_saida=segredos_de_saida,
        pre_voo=PreVooComCache(PreVooLivre(), relogio), dsn=settings.database_url.get_secret_value(),
        diretorio_migracoes=_diretorio_de_migracoes(),
        git_sha=os.environ.get("GIT_SHA", "desconhecido"), built_at=os.environ.get("BUILT_AT", "desconhecido"),
    )  # fmt: skip
    return criar_app(contexto, ao_iniciar=pool.open, ao_encerrar=pool.close)


def _diretorio_de_migracoes() -> Path:
    """Pasta das migrações que o `/readyz` confere contra o ledger (checksum e pendência). Ordem: `IA_MIGRACOES_DIR` (explícito),
    `migrations/` do checkout, `ia_atendimento/migrations/` no pacote instalado (o wheel as leva). Não achou, ou veio sem migração válida:
    FALHA a subida, porque um `/readyz` que deixa de conferir checksum em silêncio (R1-09) é pior que não subir."""
    explicito = os.environ.get("IA_MIGRACOES_DIR")
    candidatas = [Path(explicito)] if explicito else [RAIZ / "migrations", Path(__file__).resolve().parents[1] / "migrations"]
    for pasta in candidatas:
        if pasta.is_dir():
            try:
                migracoes.listar(pasta)
            except migracoes.MigracaoErro:
                raise ConfiguracaoInvalida(f"pasta de migrações sem migração válida: {pasta.name}") from None
            return pasta
    raise ConfiguracaoInvalida("pasta de migrações não encontrada (defina IA_MIGRACOES_DIR ou instale o pacote com migrations/)")
