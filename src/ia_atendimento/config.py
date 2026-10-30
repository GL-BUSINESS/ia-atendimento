"""Configuração por variáveis de ambiente (nomes e padrões em `.env.example`; estudo G §3).

Regras do roteiro (§0.3) validadas já no boot: o modelo é DeepSeek ou Gemini servido SÓ pelo provedor aprovado (lista
positiva de hosts, não lista de proibidos: ponto final, ponto ideográfico e domínio parecido furam lista negativa) e sem nada
da Anthropic; chaves são `SecretStr` (nunca no `repr`, no log nem no erro de validação); o runtime conecta como `ia_app_*`,
conferido pelo mesmo parser do libpq que fará a conexão (`%5F`, `?user=` e afins não enganam).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlsplit

from psycopg import ProgrammingError
from psycopg.conninfo import conninfo_to_dict
from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

HOSTS_LOCAIS = frozenset({"localhost", "127.0.0.1", "::1"})
# Único host de produção do modelo: Fireworks SÓ-EUA (estudo G §2). `api.fireworks.ai` (global) NÃO vale. Outro provedor (reserva
# Together só-EUA, Gemini) entra por mudança de código revisada, nunca por variável de ambiente.
HOSTS_DO_MODELO = frozenset({"us.api.fireworks.ai"})
PORTAS_HTTPS = (None, 443)
# Domínios proibidos (API oficial da DeepSeek: China, LGPD art. 33; Anthropic: regra 1): só escolhem a mensagem de erro;
# a trava de verdade é a lista positiva acima.
DOMINIOS_PROIBIDOS = ("deepseek.com", "deepseek.ai", "anthropic.com", "claude.ai")
# Nome lógico (`deepseek-*`/`gemini-*`, igual ao CHECK `modelo_por_faixa`) ou id do provedor: `accounts/<conta>/(models|routers)/<nome>`.
PADRAO_MODELO = re.compile(r"^(?:accounts/[a-z0-9][a-z0-9-]{0,62}/(?:models|routers)/)?(?:deepseek|gemini)-[a-z0-9][a-z0-9._-]{0,59}$")
TERMOS_PROIBIDOS_NO_MODELO = ("anthropic", "claude", "opus", "sonnet", "haiku")
# Login do runtime: ia_app_a/ia_app_b (e só eles na prática). Nem o grupo `ia_app` (NOLOGIN), nem outro grupo, nem dono ou superusuário.
PADRAO_LOGIN_RUNTIME = re.compile(r"^ia_app_[a-z0-9]{1,16}$")
TAMANHO_MIN_SEGREDO = 16  # `.env.example` traz os segredos vazios: esquecer de preencher não pode subir com API aberta
CHAVE_ID_MAX = 32767  # coluna smallint (conversa_cifrada.chave_id, cofre.chave_id)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", frozen=True, hide_input_in_errors=True)

    # Banco `ia_atendimento` na S4, login `ia_app_a`/`ia_app_b` (sem DDL, sem DELETE). A URL leva a senha: SecretStr.
    database_url: SecretStr
    # Modelo: um provedor no MVP (a reserva é o repasse ao vendedor). Nome, URL e chave vêm de env (estudo G §3).
    modelo_nome: str = "deepseek-v4p1-flash-1017"
    modelo_base_url_1: str = "https://us.api.fireworks.ai/inference/v1"
    modelo_api_key_1: SecretStr = Field(min_length=TAMANHO_MIN_SEGREDO)
    api_token: SecretStr = Field(min_length=TAMANHO_MIN_SEGREDO)
    phoenix_endpoint: str | None = None
    # Chave AES-256-GCM da conversa/cofre: id vigente (mensal) + arquivo 0600 com {"<id>": "<base64 de 32 bytes>"}.
    chave_aes_id: int = Field(ge=1, le=CHAVE_ID_MAX)
    chave_aes_arquivo: Path

    @field_validator("database_url")
    @classmethod
    def _banco_como_ia_app(cls, valor: SecretStr) -> SecretStr:
        """O runtime conecta como ia_app_* (sem DDL, sem DELETE): nunca como dono nem superusuário. Não ecoa a URL no erro."""
        url = valor.get_secret_value()
        try:
            partes = urlsplit(url)
            # `postgresql+psycopg://` é dialeto do SQLAlchemy; o libpq só entende o esquema puro
            efetiva = conninfo_to_dict(re.sub(r"^(postgres(?:ql)?)\+[a-z0-9_]+://", r"\1://", url, flags=re.IGNORECASE))
        except (ValueError, ProgrammingError):  # a mensagem do libpq cita a URL inteira, com a senha
            raise ValueError("database_url deve ser postgresql://usuario:senha@host:porta/banco") from None
        if partes.scheme.split("+")[0].lower() not in ("postgresql", "postgres") or not efetiva.get("host"):
            raise ValueError("database_url deve ser postgresql://usuario:senha@host:porta/banco")
        # os dois olhares: o da userinfo (decodificada, como o libpq faz) e o login que o libpq de fato usará (`?user=` vence a userinfo)
        for login in (unquote(partes.username or ""), efetiva.get("user", "")):
            if not PADRAO_LOGIN_RUNTIME.fullmatch(login):
                raise ValueError("database_url deve usar o login ia_app_a ou ia_app_b (nunca ia_owner, s4_super, postgres ou outro grupo)")
        return valor

    @field_validator("modelo_nome")
    @classmethod
    def _modelo_so_deepseek_ou_gemini(cls, valor: str) -> str:
        if not PADRAO_MODELO.fullmatch(valor) or any(termo in valor.lower() for termo in TERMOS_PROIBIDOS_NO_MODELO):
            raise ValueError("modelo_nome deve ser deepseek-* ou gemini-* (nada da Anthropic, nada fora das famílias aprovadas)")
        return valor

    @field_validator("modelo_base_url_1")
    @classmethod
    def _url_do_modelo(cls, valor: str) -> str:
        """Lista positiva: o provedor aprovado (https) ou loopback (dublê do modelo, http ou https). Sem credencial, query nem porta."""
        try:
            partes = urlsplit(valor)
            host, porta = (partes.hostname or ""), partes.port
        except ValueError:
            raise ValueError("modelo_base_url_1 malformada") from None
        if not host:
            raise ValueError("modelo_base_url_1 sem host")
        canonico = host.rstrip(".")
        if any(canonico == d or canonico.endswith(f".{d}") for d in DOMINIOS_PROIBIDOS):
            raise ValueError("modelo_base_url_1 aponta para domínio proibido (API oficial da DeepSeek ou Anthropic)")
        if partes.username is not None or partes.password is not None or partes.query or partes.fragment or "@" in partes.netloc:
            raise ValueError("modelo_base_url_1 não pode levar credencial, query nem fragmento (segredo vai em MODELO_API_KEY_1)")
        if host in HOSTS_LOCAIS:
            if partes.scheme not in ("http", "https"):
                raise ValueError("modelo_base_url_1 local exige http ou https")
            return valor
        if partes.scheme != "https" or host not in HOSTS_DO_MODELO or porta not in PORTAS_HTTPS:
            raise ValueError("modelo_base_url_1 deve ser https://us.api.fireworks.ai (provedor só-EUA aprovado) ou loopback do dublê")
        return valor

    @field_validator("phoenix_endpoint", mode="before")
    @classmethod
    def _phoenix_sem_credencial(cls, valor: object) -> object:
        """Vazio = não exporta traces. O campo não é SecretStr, então credencial na URL sairia no `repr`: recusada."""
        if valor is None or valor == "":
            return None
        try:
            partes = urlsplit(str(valor))
            com_credencial = partes.username is not None or partes.password is not None
            invalida = partes.scheme not in ("http", "https") or not partes.hostname or com_credencial
        except ValueError:
            invalida = True
        if invalida:
            raise ValueError("phoenix_endpoint deve ser http(s)://host[:porta]/caminho, sem credencial na URL")
        return valor


class ConfiguracaoInvalida(RuntimeError):
    """Falha de boot por configuração. A mensagem lista só campo e motivo: nunca o valor (a `ValidationError` do pydantic guarda o
    valor de entrada em `.errors()`/`.json()` mesmo com `hide_input_in_errors`, e a entrada pode ser a URL do banco com a senha)."""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]  # campos obrigatórios vêm do ambiente
    except ValidationError as erro:
        motivos = erro.errors(include_input=False, include_context=False, include_url=False)
        raise ConfiguracaoInvalida("; ".join(f"{'.'.join(str(parte) for parte in m['loc'])}: {m['msg']}" for m in motivos)) from None
