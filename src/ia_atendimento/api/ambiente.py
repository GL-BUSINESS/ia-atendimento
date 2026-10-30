"""Montagem de produção: `Settings` + arquivos de segredo + pool de conexões + fila, num `ContextoApi`.

Uso (OPERACAO.md §8): `uvicorn --factory ia_atendimento.api.ambiente:criar_app_de_ambiente --host 10.90.0.5 --port 8000 --no-access-log`.
Faltou segredo obrigatório, arquivo aberto demais, chave inválida ou fixture malformada ⇒ falha NA SUBIDA, com a regra e nunca o valor.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from psycopg_pool import ConnectionPool

from ia_atendimento import fila
from ia_atendimento.api.app import criar_app
from ia_atendimento.api.contexto import ContextoApi, PreVooComCache, PreVooLivre
from ia_atendimento.chave import LeitorConfig
from ia_atendimento.cifra import Chaveiro
from ia_atendimento.config import Settings, get_settings
from ia_atendimento.enfileirador import EnfileiradorProcrastinate
from ia_atendimento.evento_mensagem import ChavesDeMensagem
from ia_atendimento.pessoas_teste import carregar as carregar_pessoas_teste
from ia_atendimento.relogio import RelogioReal
from ia_atendimento.segredos import carregar_gateway_hmac, carregar_segredos_de_saida

RAIZ = Path(__file__).resolve().parents[3]
POOL_MIN = 1
POOL_MAX = 8
POOL_ESPERA_S = 5.0  # sem conexão livre em 5 s ⇒ PoolTimeout ⇒ 503 `nao_pronto` (o gateway/ChatGuru repete)


def criar_app_de_ambiente() -> FastAPI:
    settings = get_settings()
    return _montar(settings)


def _montar(settings: Settings) -> FastAPI:
    relogio = RelogioReal()
    dsn = fila.conninfo_da_fila(
        settings.database_url.get_secret_value()
    )  # search_path da fila: o defer na transação da API usa as funções do Procrastinate
    pool = ConnectionPool(dsn, min_size=POOL_MIN, max_size=POOL_MAX, timeout=POOL_ESPERA_S, kwargs={"autocommit": True}, open=False)
    app_fila = fila.criar_app(settings.database_url.get_secret_value(), com_periodicas=False)
    contexto = ContextoApi(
        settings=settings, relogio=relogio, conexao=pool.connection, leitor=LeitorConfig(relogio),
        chaveiro=Chaveiro.de_arquivo(settings.chave_aes_arquivo, settings.chave_aes_id),
        chaves_msg=ChavesDeMensagem.de_settings(settings), enfileirador=EnfileiradorProcrastinate(app_fila),
        tokens={origem: token.get_secret_value().encode() for origem, token in settings.api_tokens.items()},
        gateway_hmac=carregar_gateway_hmac(settings.gateway_hmac_arquivo),
        pessoas_teste=carregar_pessoas_teste(settings.pessoas_teste_arquivo),
        segredos_de_saida=carregar_segredos_de_saida(settings.segredos_saida_arquivo),
        pre_voo=PreVooComCache(PreVooLivre(), relogio), dsn=settings.database_url.get_secret_value(),
        diretorio_migracoes=_diretorio_de_migracoes(),
        git_sha=os.environ.get("GIT_SHA", "desconhecido"), built_at=os.environ.get("BUILT_AT", "desconhecido"),
    )  # fmt: skip
    return criar_app(contexto, ao_iniciar=pool.open, ao_encerrar=pool.close)


def _diretorio_de_migracoes() -> Path | None:
    """`migrations/` ao lado do pacote (imagem com o repo inteiro) ou `IA_MIGRACOES_DIR`; sem ela o `/readyz` não confere checksum."""
    escolhido = Path(os.environ["IA_MIGRACOES_DIR"]) if os.environ.get("IA_MIGRACOES_DIR") else RAIZ / "migrations"
    return escolhido if escolhido.is_dir() else None
