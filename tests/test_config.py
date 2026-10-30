from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from ia_atendimento.config import Settings, get_settings

SEGREDOS = {
    "DATABASE_URL": "postgresql://ia_app_a:senha-do-banco-XYZ@127.0.0.1:5434/ia_atendimento",
    "MODELO_API_KEY_1": "fw_chave-do-modelo-ABC123",
    "API_TOKEN": "token-da-api-QWERTY",
}
BASE = {
    **SEGREDOS,
    "CHAVE_AES_ID": "3",
    "CHAVE_AES_ARQUIVO": "/etc/ia-s4/chaves.json",
}


@pytest.fixture(autouse=True)
def _ambiente_limpo(monkeypatch, tmp_path):
    """Nenhum .env do disco nem variável do shell interfere: cada teste declara o que usa."""
    for nome in [*BASE, "MODELO_NOME", "MODELO_BASE_URL_1", "PHOENIX_ENDPOINT"]:
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _definir(monkeypatch, valores: dict[str, str]) -> None:
    for nome, valor in valores.items():
        monkeypatch.setenv(nome, valor)


def test_le_env_com_padroes_do_estudo_g(monkeypatch):
    _definir(monkeypatch, BASE)
    s = Settings()
    assert s.modelo_nome == "deepseek-v4p1-flash-1017"
    assert s.modelo_base_url_1 == "https://us.api.fireworks.ai/inference/v1"
    assert s.chave_aes_id == 3
    assert str(s.chave_aes_arquivo) == "/etc/ia-s4/chaves.json"
    assert s.phoenix_endpoint is None
    assert s.modelo_api_key_1.get_secret_value() == "fw_chave-do-modelo-ABC123"
    assert s.database_url.get_secret_value().startswith("postgresql://ia_app_a:")


def test_chaves_sao_secretstr(monkeypatch):
    _definir(monkeypatch, BASE)
    s = Settings()
    for campo in (s.database_url, s.modelo_api_key_1, s.api_token):
        assert isinstance(campo, SecretStr)


def test_repr_str_e_dump_nao_vazam_segredo(monkeypatch):
    _definir(monkeypatch, BASE)
    s = Settings()
    for saida in (repr(s), str(s), s.model_dump_json(), str(s.model_dump())):
        for segredo in ("senha-do-banco-XYZ", "fw_chave-do-modelo-ABC123", "token-da-api-QWERTY"):
            assert segredo not in saida


@pytest.mark.parametrize("faltando", ["DATABASE_URL", "MODELO_API_KEY_1", "API_TOKEN", "CHAVE_AES_ID", "CHAVE_AES_ARQUIVO"])
def test_campo_obrigatorio_ausente_recusa_o_boot(monkeypatch, faltando):
    _definir(monkeypatch, {k: v for k, v in BASE.items() if k != faltando})
    with pytest.raises(ValidationError) as erro:
        Settings()
    assert faltando.lower() in str(erro.value).lower()
    assert "senha-do-banco-XYZ" not in str(erro.value)  # o erro de validação também não ecoa o valor


@pytest.mark.parametrize(
    "url", ["https://api.deepseek.com/v1", "https://api.deepseek.com", "https://eu.api.deepseek.com/v1", "https://api.anthropic.com/v1"]
)
def test_recusa_api_oficial_da_deepseek_e_da_anthropic(monkeypatch, url):
    _definir(monkeypatch, {**BASE, "MODELO_BASE_URL_1": url})
    with pytest.raises(ValidationError):
        Settings()


def test_recusa_url_do_modelo_sem_tls_fora_de_localhost(monkeypatch):
    _definir(monkeypatch, {**BASE, "MODELO_BASE_URL_1": "http://us.api.fireworks.ai/inference/v1"})
    with pytest.raises(ValidationError):
        Settings()


def test_aceita_http_em_localhost_para_o_duble_do_modelo(monkeypatch):
    _definir(monkeypatch, {**BASE, "MODELO_BASE_URL_1": "http://127.0.0.1:8089/v1"})
    assert Settings().modelo_base_url_1 == "http://127.0.0.1:8089/v1"


@pytest.mark.parametrize("nome", ["claude-sonnet-5-5", "gpt-oss-120b", "Deepseek V4", "", "outro-modelo-x"])
def test_recusa_modelo_fora_de_deepseek_ou_gemini(monkeypatch, nome):
    _definir(monkeypatch, {**BASE, "MODELO_NOME": nome})
    with pytest.raises(ValidationError):
        Settings()


def test_aceita_roteador_do_fireworks_so_eua(monkeypatch):
    _definir(monkeypatch, {**BASE, "MODELO_NOME": "accounts/fireworks/routers/deepseek-v4p1-flash-1017-us"})
    assert Settings().modelo_nome.endswith("-us")


@pytest.mark.parametrize("valor", ["0", "-1", "32768", "x"])
def test_chave_aes_id_fora_de_smallint_positivo_recusada(monkeypatch, valor):
    _definir(monkeypatch, {**BASE, "CHAVE_AES_ID": valor})
    with pytest.raises(ValidationError):
        Settings()


def test_phoenix_endpoint_opcional(monkeypatch):
    _definir(monkeypatch, {**BASE, "PHOENIX_ENDPOINT": "http://127.0.0.1:6006/v1/traces"})
    assert Settings().phoenix_endpoint == "http://127.0.0.1:6006/v1/traces"


def test_get_settings_e_cacheada(monkeypatch):
    _definir(monkeypatch, BASE)
    assert get_settings() is get_settings()


def test_env_example_so_tem_nomes_dos_campos():
    """O .env.example lista exatamente os campos de Settings (em MAIÚSCULAS) e nenhum valor secreto."""
    from pathlib import Path

    exemplo = (Path(__file__).resolve().parent.parent / ".env.example").read_text(encoding="utf-8")
    nomes = {linha.split("=", 1)[0] for linha in exemplo.splitlines() if linha and not linha.startswith("#")}
    assert nomes == {campo.upper() for campo in Settings.model_fields}
    for linha in exemplo.splitlines():
        if linha.startswith(("DATABASE_URL", "MODELO_API_KEY_1", "API_TOKEN")):
            assert linha.split("=", 1)[1] == "", f"valor secreto no exemplo: {linha.split('=', 1)[0]}"
