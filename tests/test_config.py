from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from ia_atendimento.config import ConfiguracaoInvalida, Settings, get_settings

SEGREDOS = {
    "DATABASE_URL": "postgresql://ia_app_a:senha-do-banco-XYZ@127.0.0.1:5434/ia_atendimento",
    "MODELO_API_KEY_1": "fw_chave-do-modelo-ABC123",
    "API_TOKEN": "token-da-api-QWERTY",
    "CHAVE_H16": "h16-chave-hmac-de-teste-descartavel-0123456789",
    "CHAVE_FINGERPRINT": "fp-chave-hmac-de-teste-descartavel-0123456789",
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
    for campo in (s.database_url, s.modelo_api_key_1, s.api_token, s.chave_h16, s.chave_fingerprint):
        assert isinstance(campo, SecretStr)


def test_repr_str_e_dump_nao_vazam_segredo(monkeypatch):
    _definir(monkeypatch, BASE)
    s = Settings()
    for saida in (repr(s), str(s), s.model_dump_json(), str(s.model_dump())):
        for segredo in ("senha-do-banco-XYZ", "fw_chave-do-modelo-ABC123", "token-da-api-QWERTY"):
            assert segredo not in saida


@pytest.mark.parametrize(
    "faltando", ["DATABASE_URL", "MODELO_API_KEY_1", "API_TOKEN", "CHAVE_AES_ID", "CHAVE_AES_ARQUIVO", "CHAVE_H16", "CHAVE_FINGERPRINT"]
)
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


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://postgres:segredo-do-super@127.0.0.1:5434/ia_atendimento",
        "postgresql://s4_super:segredo-do-super@127.0.0.1:5434/ia_atendimento",
        "postgresql://ia_owner:segredo-do-super@127.0.0.1:5434/ia_atendimento",
        "mysql://ia_app_a:segredo-do-super@127.0.0.1/ia",
        "postgresql://127.0.0.1/ia_atendimento",
        "isto nao e url",
    ],
)
def test_database_url_recusa_dono_superusuario_e_esquema_errado_sem_ecoar_a_senha(monkeypatch, url):
    """O runtime conecta como ia_app_* (sem DDL, sem DELETE): nunca como dono ou superusuário."""
    _definir(monkeypatch, {**BASE, "DATABASE_URL": url})
    with pytest.raises(ValidationError) as erro:
        Settings()
    assert "segredo-do-super" not in str(erro.value)


@pytest.mark.parametrize("scheme", ["postgresql", "postgres", "postgresql+psycopg"])
def test_database_url_do_ia_app_e_aceita(monkeypatch, scheme):
    _definir(monkeypatch, {**BASE, "DATABASE_URL": f"{scheme}://ia_app_a:senha@127.0.0.1:5434/ia_atendimento"})
    assert Settings().database_url.get_secret_value().startswith(scheme)


# --- revisão 29/10: o que a lista de proibidos deixava passar ------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://api.deepseek.com./v1",  # ponto final de FQDN: o DNS resolve para o mesmo host
        "https://api.deepseek\u3002com/v1",  # ponto ideográfico: o httpx normaliza para «.»
        "https://API.DEEPSEEK.COM/v1",
        "https://api.anthropic.com./v1",
        "https://api.fireworks.ai/inference/v1",  # fireworks GLOBAL: «global» não é EUA (regra 1)
        "https://openrouter.ai/api/v1",
        "https://us.api.fireworks.ai.evil.example/inference/v1",
        "https://evil.example/us.api.fireworks.ai",
        "https://us.api.fireworks.ai@evil.example/inference/v1",
        "https://u:p@us.api.fireworks.ai/inference/v1",  # credencial na URL sairia no repr (o campo não é SecretStr)
        "https://us.api.fireworks.ai/inference/v1?api_key=x",
        "https://us.api.fireworks.ai:8443/inference/v1",
        "https://us.api.fireworks.ai%2Eevil.example/v1",
        "ftp://us.api.fireworks.ai/inference/v1",
        "http://localhost.evil.example/v1",
        "http://127.0.0.1.evil.example/v1",
    ],
)
def test_url_do_modelo_so_aceita_o_provedor_aprovado_ou_loopback(monkeypatch, url):
    _definir(monkeypatch, {**BASE, "MODELO_BASE_URL_1": url})
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize(
    "url",
    [
        "https://us.api.fireworks.ai/inference/v1",
        "https://us.api.fireworks.ai/inference",
        "http://127.0.0.1:8089/v1",
        "http://localhost:8089/v1",
        "http://[::1]:8089/v1",
    ],
)
def test_url_do_modelo_aprovada_ou_loopback_do_duble_e_aceita(monkeypatch, url):
    _definir(monkeypatch, {**BASE, "MODELO_BASE_URL_1": url})
    assert Settings().modelo_base_url_1 == url


@pytest.mark.parametrize(
    "nome",
    [
        "anthropic/deepseek-v4",
        "claude/deepseek-v4",
        "accounts/anthropic/routers/deepseek-v4p1-flash-1017-us",
        "deepseek-claude-3",
        "gemini-anthropic",
        "deepseek-x/anthropic",
        "../deepseek-v4",
        "accounts/fireworks/outra/deepseek-v4",
        "accounts//routers/deepseek-v4",
    ],
)
def test_modelo_nome_recusa_anthropic_em_qualquer_segmento_e_prefixo_fora_do_padrao(monkeypatch, nome):
    _definir(monkeypatch, {**BASE, "MODELO_NOME": nome})
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize(
    "nome",
    [
        "deepseek-v4p1-flash-1017",
        "gemini-2.5-flash",
        "accounts/fireworks/models/deepseek-v4p1-flash-1017",
        "accounts/fireworks/routers/deepseek-v4p1-flash-1017-us",
    ],
)
def test_modelo_nome_aprovado_e_aceito(monkeypatch, nome):
    _definir(monkeypatch, {**BASE, "MODELO_NOME": nome})
    assert Settings().modelo_nome == nome


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://ia%5Fowner:segredo-do-super@127.0.0.1:5434/ia_atendimento",  # o libpq decodifica %5F: é o ia_owner
        "postgresql://s4%5Fsuper:segredo-do-super@127.0.0.1:5434/ia_atendimento",
        "postgresql://%69a_owner:segredo-do-super@127.0.0.1:5434/ia_atendimento",
        "postgresql://ia_app_a:segredo-do-super@127.0.0.1:5434/ia_atendimento?user=ia_owner",  # ?user= vence a userinfo
        "postgresql://ia_app_a:segredo-do-super@127.0.0.1:5434/ia_atendimento?user=postgres",
        "postgresql://ia_leitura_a:segredo-do-super@127.0.0.1:5434/ia_atendimento",  # login de outro grupo
        "postgresql://ia_qualidade_a:segredo-do-super@127.0.0.1:5434/ia_atendimento",
        "postgresql://admin:segredo-do-super@127.0.0.1:5434/ia_atendimento",
        "postgresql://ia_app:segredo-do-super@127.0.0.1:5434/ia_atendimento",  # o grupo NOLOGIN não é login
        "postgresql://ia_app_a:segredo-do-super@[::1/ia_atendimento",  # URL malformada: a mensagem do libpq ecoaria a senha
    ],
)
def test_database_url_exige_login_ia_app_efetivo_pelo_libpq(monkeypatch, url):
    _definir(monkeypatch, {**BASE, "DATABASE_URL": url})
    with pytest.raises(ValidationError) as erro:
        Settings()
    assert "segredo-do-super" not in str(erro.value)
    with pytest.raises(ConfiguracaoInvalida) as boot:  # o caminho do boot: nem `.errors()` nem `.json()` carregam o valor
        get_settings()
    saidas = (str(boot.value), repr(boot.value), repr(boot.value.args), str(boot.value.__cause__), str(boot.value.__context__))
    assert all("segredo-do-super" not in s for s in saidas)
    assert "database_url" in str(boot.value)


@pytest.mark.parametrize(
    "opcoes", ["-c%20role%3Dia_owner", "-c%20ROLE%3Dia_owner", "--role%3Dia_owner", "-c%20session_authorization%3Dpostgres"]
)
def test_database_url_recusa_options_que_trocam_de_papel(monkeypatch, opcoes):
    url = f"postgresql://ia_app_a:segredo-do-super@127.0.0.1:5434/ia_atendimento?options={opcoes}"
    _definir(monkeypatch, {**BASE, "DATABASE_URL": url})
    with pytest.raises(ValidationError):
        Settings()


def test_database_url_aceita_options_de_search_path_da_fila(monkeypatch):
    url = "postgresql://ia_app_a:senha@127.0.0.1:5434/ia_atendimento?options=-c%20search_path%3Dprocrastinate,public"
    _definir(monkeypatch, {**BASE, "DATABASE_URL": url})
    assert "search_path" in Settings().database_url.get_secret_value()


@pytest.mark.parametrize(
    "url",
    [
        " https://us.api.fireworks.ai/inference/v1",
        "https://us.api.fireworks.ai/inference/v1\n",
        "https://us.api.fireworks.ai/\n@evil",
        "http://localhost\t.evil",
    ],
)
def test_url_do_modelo_recusa_espaco_e_controle(monkeypatch, url):
    _definir(monkeypatch, {**BASE, "MODELO_BASE_URL_1": url})
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("login", ["ia_app_a", "ia_app_b"])
def test_database_url_aceita_os_dois_logins_do_runtime(monkeypatch, login):
    _definir(monkeypatch, {**BASE, "DATABASE_URL": f"postgresql://{login}:senha@127.0.0.1:5434/ia_atendimento"})
    assert Settings().database_url.get_secret_value().startswith(f"postgresql://{login}:")


@pytest.mark.parametrize("campo", ["MODELO_API_KEY_1", "API_TOKEN"])
@pytest.mark.parametrize("valor", ["", "k", "curto-demais"])
def test_segredo_vazio_ou_curto_recusa_o_boot(monkeypatch, campo, valor):
    """O `.env.example` traz os campos vazios: copiar e esquecer de preencher não pode subir com a API aberta."""
    _definir(monkeypatch, {**BASE, campo: valor})
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("endpoint", ["http://user:segredo@127.0.0.1:6006/v1/traces", "ftp://127.0.0.1/x", "127.0.0.1:6006"])
def test_phoenix_endpoint_recusa_credencial_na_url_e_esquema_estranho(monkeypatch, endpoint):
    _definir(monkeypatch, {**BASE, "PHOENIX_ENDPOINT": endpoint})
    with pytest.raises(ValidationError) as erro:
        Settings()
    assert "segredo" not in str(erro.value)


def test_phoenix_endpoint_vazio_do_env_example_vale_como_sem_exportar(monkeypatch):
    _definir(monkeypatch, {**BASE, "PHOENIX_ENDPOINT": ""})
    assert Settings().phoenix_endpoint is None


def test_boot_com_erro_lista_campo_e_motivo_sem_valor(monkeypatch):
    _definir(monkeypatch, {**BASE, "API_TOKEN": "curto", "CHAVE_AES_ID": "0"})
    with pytest.raises(ConfiguracaoInvalida) as erro:
        get_settings()
    texto = str(erro.value)
    assert "api_token" in texto and "chave_aes_id" in texto and "curto" not in texto


def test_chaves_hmac_de_mensagem_recusam_curta_vazia_e_repetida_s2(monkeypatch):
    """S2: `msg_fingerprint` e `h16` são HMAC com chaves próprias; sem chave (ou curta, ou a mesma nas duas) o boot recusa."""
    for ruim in ({"CHAVE_FINGERPRINT": ""}, {"CHAVE_H16": "curta"}, {"CHAVE_FINGERPRINT": BASE["CHAVE_H16"]}):
        _definir(monkeypatch, {**BASE, **ruim})
        with pytest.raises(ValidationError) as erro:
            Settings()
        assert BASE["CHAVE_H16"] not in str(erro.value)
        assert BASE["CHAVE_FINGERPRINT"] not in str(erro.value)


def test_chaves_de_mensagem_vem_do_settings_s2(monkeypatch):
    from ia_atendimento.evento_mensagem import ChavesDeMensagem

    _definir(monkeypatch, BASE)
    chaves = ChavesDeMensagem.de_settings(Settings())
    assert chaves.h16 == BASE["CHAVE_H16"].encode()
    assert chaves.fingerprint == BASE["CHAVE_FINGERPRINT"].encode()
