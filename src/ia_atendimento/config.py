"""Configuração por variáveis de ambiente (nomes e padrões em `.env.example`; estudo G §3).

Regras do roteiro (§0.3) validadas já no boot: o modelo é DeepSeek ou Gemini hospedado fora da API oficial da
DeepSeek e sem nada da Anthropic; chaves são `SecretStr` (nunca no `repr`, no log nem no erro de validação).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

HOSTS_LOCAIS = frozenset({"localhost", "127.0.0.1", "::1"})
# Domínios proibidos como destino do modelo: API oficial da DeepSeek (China, LGPD art. 33) e Anthropic (regra 1).
DOMINIOS_PROIBIDOS = ("deepseek.com", "deepseek.ai", "anthropic.com", "claude.ai")
# Mesma regra do CHECK `modelo_por_faixa` do esquema (famílias abertas) + roteador do provedor (`accounts/.../deepseek-...-us`).
PADRAO_MODELO = re.compile(r"^(?:[a-z0-9._-]+/)*(?:deepseek|gemini)-[a-z0-9][a-z0-9._-]{0,59}$")
CHAVE_ID_MAX = 32767  # coluna smallint (conversa_cifrada.chave_id, cofre.chave_id)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", frozen=True)

    # Banco `ia_atendimento` na S4, login `ia_app_a`/`ia_app_b` (sem DDL, sem DELETE). A URL leva a senha: SecretStr.
    database_url: SecretStr
    # Modelo: um provedor no MVP (a reserva é o repasse ao vendedor). Nome, URL e chave vêm de env (estudo G §3).
    modelo_nome: str = "deepseek-v4p1-flash-1017"
    modelo_base_url_1: str = "https://us.api.fireworks.ai/inference/v1"
    modelo_api_key_1: SecretStr
    api_token: SecretStr
    phoenix_endpoint: str | None = None
    # Chave AES-256-GCM da conversa/cofre: id vigente (mensal) + arquivo 0600 com {"<id>": "<base64 de 32 bytes>"}.
    chave_aes_id: int = Field(ge=1, le=CHAVE_ID_MAX)
    chave_aes_arquivo: Path

    @field_validator("modelo_nome")
    @classmethod
    def _modelo_so_deepseek_ou_gemini(cls, valor: str) -> str:
        if not PADRAO_MODELO.fullmatch(valor):
            raise ValueError("modelo_nome deve ser deepseek-* ou gemini-* (nada da Anthropic, nada fora das famílias aprovadas)")
        return valor

    @field_validator("modelo_base_url_1")
    @classmethod
    def _url_do_modelo(cls, valor: str) -> str:
        partes = urlsplit(valor)
        host = (partes.hostname or "").lower()
        if any(host == d or host.endswith(f".{d}") for d in DOMINIOS_PROIBIDOS):
            raise ValueError("modelo_base_url_1 aponta para domínio proibido (API oficial da DeepSeek ou Anthropic)")
        local = host in HOSTS_LOCAIS
        if partes.scheme != "https" and not (partes.scheme == "http" and local):
            raise ValueError("modelo_base_url_1 exige https (http só em localhost, para o dublê do modelo)")
        if not host:
            raise ValueError("modelo_base_url_1 sem host")
        return valor


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # campos obrigatórios vêm do ambiente
