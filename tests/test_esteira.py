"""Esteira de build e deploy (A6.6): compose, workflow de imagem, Dockerfile e scripts de release/deploy.

Nada aqui toca rede, Coolify, VPS ou registry: o compose e o workflow são validados como texto/YAML, e os scripts rodam com `ssh`/`curl`
falsos no PATH (o falso grava o que recebeu; o deploy de verdade só acontece com `--executar` e credencial, que o teste nunca tem).
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

from ia_atendimento.config import Settings

RAIZ = Path(__file__).resolve().parent.parent
COMPOSE = RAIZ / "docker-compose.yml"
WORKFLOW = RAIZ / ".github" / "workflows" / "imagem.yml"
DOCKERFILE = RAIZ / "Dockerfile"
RELEASE = RAIZ / "scripts" / "release.sh"
DEPLOY = RAIZ / "scripts" / "deploy-s5.sh"
ENTRADA = RAIZ / "docker" / "ia-entrada.sh"

SERVICOS = ("orquestrador", "worker")
# Nomes que o compose injeta além dos campos do Settings (nunca valores): o diretório dos arquivos de segredo, lido pelo ia-entrada.
ENV_EXTRA_PERMITIDAS = {"IA_SEGREDOS_DIR"}
PADRAO_ENV_COMPOSE = re.compile(r"^(?P<nome>[A-Z][A-Z0-9_]*)=\$\{(?P<ref>[A-Z][A-Z0-9_]*)(?:(?P<op>:-|:\?)(?P<padrao>[^}]*))?\}$")
NOMES_SECRETOS = re.compile(r"KEY|(?<!MAX_)TOKEN|SECRET|PASSWORD|SENHA|CHAVE_H16|FINGERPRINT|CHAT_REF|DATABASE_URL")
SHA_FALSO = "0123456789abcdef0123456789abcdef01234567"


def _segredos_do_entrada() -> set[str]:
    casou = re.search(r'^SEGREDOS="([A-Z0-9_ ]+)"$', ENTRADA.read_text(encoding="utf-8"), re.MULTILINE)
    assert casou, "docker/ia-entrada.sh precisa da lista SEGREDOS"
    return set(casou.group(1).split())


def _carregar(caminho: Path) -> dict:
    return yaml.safe_load(caminho.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def compose() -> dict:
    return _carregar(COMPOSE)


@pytest.fixture(scope="module")
def workflow() -> dict:
    return _carregar(WORKFLOW)


def _env_de(servico: dict) -> list[str]:
    ambiente = servico.get("environment", [])
    assert isinstance(ambiente, list), "environment em lista NOME=${NOME:-} (o padrão do gateway), não em dicionário com valores"
    return ambiente


# ------------------------------------------------------------------ docker-compose.yml


def test_compose_tem_orquestrador_e_worker_com_a_mesma_imagem(compose):
    assert set(compose["services"]) == set(SERVICOS)
    imagens = {compose["services"][s]["image"] for s in SERVICOS}
    assert len(imagens) == 1, "orquestrador e worker usam a MESMA imagem"
    imagem = imagens.pop()
    assert imagem.startswith("${IA_REGISTRO_IMAGEM:?"), "o registro vem de variável; nenhum host fixo"
    assert "/gl-business/ia-atendimento:${IMAGE_TAG:?" in imagem, "a tag vem do env; nunca fixa, nunca latest, obrigatória"


def test_compose_e_workflow_sem_host_ou_ip_fixo():
    """S5 ainda não existe: IP do WireGuard, registro e hostnames entram por variável (pedido de 20/11)."""
    for arquivo in (COMPOSE, WORKFLOW, DEPLOY):
        texto = "\n".join(linha for linha in arquivo.read_text(encoding="utf-8").splitlines() if not linha.lstrip().startswith("#"))
        assert not re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", texto), f"{arquivo.name}: IP fixo"
        assert not re.search(r"ts\.net|glcapital(?:-ti)?\.(?:net|ltd|com)", texto), f"{arquivo.name}: host fixo"


@pytest.mark.parametrize("nome", SERVICOS)
def test_compose_servico_endurecido_e_com_limite(compose, nome):
    s = compose["services"][nome]
    assert s["restart"] == "unless-stopped"
    assert s["mem_limit"], "mem_limit obrigatório (PD-4)"
    assert s["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in s["security_opt"]
    assert s["read_only"] is True, "raiz do contêiner só leitura; /tmp em tmpfs"
    assert s["labels"]["coolify.managed"] in ("true", True), "senão o CleanupDocker apaga a imagem (memória coolify-cleanup-imagens)"
    assert "ports" not in s, "porta publicada passa pelo NAT e escapa do INPUT do nftables: rede host + bind no IP do wg0"
    assert s["network_mode"] == "host"
    assert s["healthcheck"]["test"], "healthcheck por serviço"
    assert s["stop_grace_period"] == "40s", "maior que o shutdown_graceful_timeout (30 s) do worker (OPERACAO §9)"


@pytest.mark.parametrize("nome", SERVICOS)
def test_compose_monta_o_diretorio_de_segredos_somente_leitura_no_mesmo_caminho(compose, nome):
    volumes = compose["services"][nome]["volumes"]
    assert volumes == ["${IA_SEGREDOS_DIR:?defina IA_SEGREDOS_DIR}:${IA_SEGREDOS_DIR}:ro"], "diretório (não arquivo), :ro, mesmo caminho"


def test_orquestrador_sobe_a_fabrica_da_main_no_ip_do_wireguard(compose):
    """F4-016: `ia_atendimento.api:app` não existe na main; o ponto de entrada é a fábrica `ambiente:criar_app_de_ambiente`."""
    comando = compose["services"]["orquestrador"]["command"]
    assert comando[:3] == ["uvicorn", "--factory", "ia_atendimento.api.ambiente:criar_app_de_ambiente"]
    assert comando[comando.index("--host") + 1].startswith("${IA_BIND_IP:?"), "bind no IP do wg0 por variável, obrigatório"
    assert comando[comando.index("--port") + 1] == "${IA_PORTA:-8000}"
    assert "0.0.0.0" not in comando  # noqa: S104 (o teste prova que NÃO se escuta em todas as interfaces)
    for flag in ("--no-access-log", "--no-server-header", "--no-proxy-headers"):
        assert flag in comando, flag
    assert comando[comando.index("--limit-concurrency") + 1] == "64" and comando[comando.index("--timeout-keep-alive") + 1] == "5"
    teste = " ".join(compose["services"]["orquestrador"]["healthcheck"]["test"])
    assert "/healthz" in teste and "${IA_BIND_IP}" in teste


def test_os_pontos_de_entrada_do_compose_existem_na_main():
    """O teste que reprova antes (F4-016, G-0016): o módulo e o atributo que o compose chama existem no código desta árvore."""
    import importlib

    ambiente = importlib.import_module("ia_atendimento.api.ambiente")
    assert callable(ambiente.criar_app_de_ambiente)
    worker = importlib.import_module("ia_atendimento.worker")
    assert callable(worker.main) and callable(worker.saude)


def test_worker_usa_o_ponto_de_entrada_da_main_e_healthcheck_de_batimento(compose):
    """G-0016: `procrastinate --app=ia_atendimento.fila.app worker` aponta um atributo que não existe e pula a vigia (OPERACAO §9)."""
    worker = compose["services"]["worker"]
    assert worker["command"] == ["python", "-m", "ia_atendimento.worker"]
    assert worker["healthcheck"]["test"] == ["CMD", "/usr/local/bin/ia-entrada", "python", "-m", "ia_atendimento.worker", "--saude"]
    assert "--port" not in worker["command"]


@pytest.mark.parametrize("nome", SERVICOS)
def test_compose_env_so_com_nomes_e_nenhum_segredo(compose, nome):
    campos = {campo.upper() for campo in Settings.model_fields}
    for linha in _env_de(compose["services"][nome]):
        casou = PADRAO_ENV_COMPOSE.fullmatch(linha)
        assert casou, f"{linha!r}: use NOME=${{NOME:-padrao}} ou NOME=${{NOME:?msg}}; valor literal não entra no repositório"
        assert casou["nome"] == casou["ref"]
        assert casou["nome"] in campos | ENV_EXTRA_PERMITIDAS, f"{casou['nome']} não é campo de Settings (config.py)"
        assert not NOMES_SECRETOS.search(casou["nome"]), f"{casou['nome']}: segredo só por arquivo 0600 (docker/ia-entrada.sh)"
        assert casou["nome"] not in _segredos_do_entrada()


def test_compose_mais_arquivos_cobrem_todos_os_campos_obrigatorios_do_settings(compose):
    obrigatorios = {c.upper() for c, f in Settings.model_fields.items() if f.is_required()}
    for nome in SERVICOS:
        declarados = {PADRAO_ENV_COMPOSE.fullmatch(linha)["nome"] for linha in _env_de(compose["services"][nome])}
        faltam = obrigatorios - declarados - _segredos_do_entrada()
        assert not faltam, f"{nome}: faltam {sorted(faltam)}"
        obrigatorios_no_compose = obrigatorios & declarados
        for linha in _env_de(compose["services"][nome]):
            casou = PADRAO_ENV_COMPOSE.fullmatch(linha)
            if casou["nome"] in obrigatorios_no_compose:
                assert casou["op"] == ":?", f"{casou['nome']}: obrigatório no Settings ⇒ `:?` no compose (falha no deploy, não no boot)"


def test_padroes_do_compose_iguais_aos_do_settings(compose):
    """Um padrão do compose diferente do código mudaria o comportamento sem PR no config.py."""
    for linha in _env_de(compose["services"]["orquestrador"]):
        casou = PADRAO_ENV_COMPOSE.fullmatch(linha)
        campo = casou["nome"].lower()
        if casou["op"] != ":-" or not casou["padrao"] or campo not in Settings.model_fields:
            continue
        padrao = Settings.model_fields[campo].default
        assert str(padrao) == casou["padrao"], f"{casou['nome']}: compose {casou['padrao']!r} × Settings {padrao!r}"


def test_compose_iguais_nos_dois_servicos(compose):
    o, w = compose["services"]["orquestrador"], compose["services"]["worker"]
    assert o["environment"] == w["environment"] and o["volumes"] == w["volumes"] and o["image"] == w["image"]


def test_compose_nao_traz_nada_que_pareca_segredo():
    texto = COMPOSE.read_text(encoding="utf-8")
    assert not re.search(r"postgres(?:ql)?://[^\s$]*:[^\s$@]+@", texto), "credencial em URL"
    assert not re.search(r"\bfw_[A-Za-z0-9]{10,}", texto)


# ------------------------------------------------------------------ docker/ia-entrada.sh


def _entrada(tmp_path: Path, arquivos: dict[str, tuple[str, int]], *comando: str, **env: str) -> subprocess.CompletedProcess[str]:
    env_dir = tmp_path / "segredos" / "env"
    env_dir.mkdir(parents=True, exist_ok=True)
    for nome, (conteudo, modo) in arquivos.items():
        (env_dir / nome).write_text(conteudo)
        (env_dir / nome).chmod(modo)
    base = {k: v for k, v in os.environ.items() if k not in _segredos_do_entrada()}
    ambiente = {**base, "IA_SEGREDOS_DIR": str(tmp_path / "segredos"), **env}
    return subprocess.run(["sh", str(ENTRADA), *comando], env=ambiente, capture_output=True, text=True, check=False)


def test_entrada_carrega_segredo_0600_e_executa_o_comando(tmp_path):
    r = _entrada(tmp_path, {"MODELO_API_KEY_1": ("kkkkkkkkkkkkkkkk\n", 0o600)}, "sh", "-c", 'test "$MODELO_API_KEY_1" = kkkkkkkkkkkkkkkk')
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("modo", [0o640, 0o644, 0o660, 0o604])
def test_entrada_recusa_arquivo_aberto_sem_citar_o_valor(tmp_path, modo):
    r = _entrada(tmp_path, {"API_TOKENS": ("segredo-que-nao-pode-vazar", modo)}, "true")
    assert r.returncode == 78 and "API_TOKENS" in r.stderr
    assert "segredo-que-nao-pode-vazar" not in r.stdout + r.stderr


def test_entrada_recusa_link_simbolico(tmp_path):
    alvo = tmp_path / "fora"
    alvo.write_text("x")
    alvo.chmod(0o600)
    (tmp_path / "segredos" / "env").mkdir(parents=True)
    (tmp_path / "segredos" / "env" / "DATABASE_URL").symlink_to(alvo)
    r = _entrada(tmp_path, {}, "true")
    assert r.returncode == 78 and "link" in r.stderr


def test_entrada_recusa_origem_dupla(tmp_path):
    r = _entrada(tmp_path, {"CHAVE_H16": ("a" * 40, 0o600)}, "true", CHAVE_H16="b" * 40)
    assert r.returncode == 78 and "ambiente E em arquivo" in r.stderr and "a" * 40 not in r.stderr


def test_entrada_recusa_vazio_e_diretorio_ausente(tmp_path):
    assert _entrada(tmp_path, {"CHAT_REF_CHAVE": ("", 0o600)}, "true").returncode == 78
    r = subprocess.run(["sh", str(ENTRADA), "true"], env={**os.environ, "IA_SEGREDOS_DIR": str(tmp_path / "nao-existe")},
                       capture_output=True, text=True, check=False)  # fmt: skip
    assert r.returncode == 78


def test_entrada_ignora_nome_fora_da_lista(tmp_path):
    r = _entrada(tmp_path, {"OUTRA_COISA": ("x", 0o644)}, "sh", "-c", 'test -z "${OUTRA_COISA:-}"')
    assert r.returncode == 0, r.stderr


def test_entrada_cobre_os_segredos_do_settings():
    secretos = {c.upper() for c, f in Settings.model_fields.items() if "SecretStr" in str(f.annotation)}
    assert secretos <= _segredos_do_entrada() | {"DATABASE_URL"}, sorted(secretos - _segredos_do_entrada())
    assert "DATABASE_URL" in _segredos_do_entrada() and "MODELO_API_KEY_1" in _segredos_do_entrada()


# ------------------------------------------------------------------ .github/workflows/imagem.yml


def _gatilhos(workflow: dict) -> dict:
    # PyYAML (YAML 1.1) lê a chave `on` como True
    return workflow.get("on", workflow.get(True))


def test_imagem_dispara_so_em_tag_v(workflow):
    gatilhos = _gatilhos(workflow)
    assert set(gatilhos) == {"push"}, "sem pull_request, sem workflow_dispatch, sem schedule: só push de tag (PD-3)"
    assert gatilhos["push"] == {"tags": ["v*"]}, "push em branch (main) NUNCA dispara a imagem"
    assert "branches" not in gatilhos["push"]


def test_imagem_roda_no_builder_da_s3(workflow):
    construir = workflow["jobs"]["construir"]
    assert construir["runs-on"]["group"] == "s3-builders"
    assert {"self-hosted", "s3-new", "builder"} <= set(construir["runs-on"]["labels"])
    assert construir["permissions"] == {"contents": "read"}


def test_imagem_so_publica_tag_que_esta_na_main(workflow):
    passos = workflow["jobs"]["construir"]["steps"]
    texto = yaml.safe_dump(passos)
    assert "merge-base --is-ancestor" in texto and "origin/main" in texto, "tag em commit fora da main não chega ao runner da S3"
    checkout = next(p for p in passos if str(p.get("uses", "")).startswith("actions/checkout"))
    assert checkout["with"]["fetch-depth"] == 0


def test_imagem_nao_publica_alias_movel(workflow):
    texto = WORKFLOW.read_text(encoding="utf-8")
    assert not re.search(r"value=(latest|production)", texto), "deploy por tag fixa: nada de latest/production"
    assert "github.ref_name" in texto


def test_deploy_automatico_exige_variavel_do_repo(workflow):
    deploy = workflow["jobs"]["implantar"]
    condicao = deploy["if"]
    assert "vars.DEPLOY_AUTOMATICO == 'true'" in condicao, "default ausente = só publica"
    assert deploy["needs"] == "construir"
    assert deploy["environment"] == "producao-s5", "environment com aprovação do dono é a trava extra"


def test_workflow_usa_so_secrets_e_variaveis_documentados(workflow):
    texto = WORKFLOW.read_text(encoding="utf-8")
    assert set(re.findall(r"secrets\.([A-Z0-9_]+)", texto)) <= {
        "S3_REGISTRY_USER",
        "S3_REGISTRY_PASSWORD",
        "COOLIFY_S2_URL",
        "COOLIFY_S2_TOKEN",
        "ALERT_WEBHOOK_URL",
    }
    assert set(re.findall(r"vars\.([A-Z0-9_]+)", texto)) <= {
        "DEPLOY_AUTOMATICO",
        "COOLIFY_UUID_IA_ORQUESTRADOR",
        "APP_GID",
        "REGISTRO_IMAGEM",
    }
    assert workflow["env"]["REGISTRY"] == "${{ vars.REGISTRO_IMAGEM }}", "registro por variável do repositório"
    assert not re.search(r"\b(?:ghp|gho|ghs|ghr)_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY", texto)


def test_acoes_do_workflow_fixadas_por_sha(workflow):
    for job in workflow["jobs"].values():
        for passo in job["steps"]:
            usa = passo.get("uses")
            if usa:
                assert re.search(r"@[0-9a-f]{40}$", usa), f"{usa}: fixe por SHA de 40 caracteres (como o pipeline central)"


def test_ci_existente_continua_por_sha():
    ci = _carregar(RAIZ / ".github" / "workflows" / "ci.yml")
    assert ci[True]["push"]["branches"] == ["main"] and "pull_request" in ci[True]


# ------------------------------------------------------------------ Dockerfile e .dockerignore


def test_dockerfile_python_igual_ao_python_version():
    versao = (RAIZ / ".python-version").read_text().strip()
    texto = DOCKERFILE.read_text(encoding="utf-8")
    assert f"ARG PYTHON_VERSION={versao}" in texto
    assert re.search(r"^FROM python:\${PYTHON_VERSION}-slim AS ", texto, re.MULTILINE)


def test_dockerfile_usuario_nao_root_com_gid_configuravel():
    texto = DOCKERFILE.read_text(encoding="utf-8")
    assert "ARG APP_GID=10001" in texto and "ARG APP_UID=10001" in texto
    assert re.search(r"^USER \$\{APP_UID\}:\$\{APP_GID\}|^USER appuser", texto, re.MULTILINE)
    assert len(re.findall(r"^FROM ", texto, re.MULTILINE)) >= 2, "multi-stage"
    assert 'LABEL coolify.managed="true"' in texto
    assert re.search(r"^HEALTHCHECK .*import ia_atendimento", texto, re.MULTILINE | re.DOTALL)
    assert not re.search(r"^HEALTHCHECK[^\n]*curl", texto, re.MULTILINE), "a imagem slim não tem curl"
    assert 'ENTRYPOINT ["/usr/local/bin/ia-entrada"]' in texto, "segredos de arquivo 0600 antes do comando"
    assert re.search(r"^ENV .*\n(?:.*\n)*?\s+GIT_SHA=\$\{GIT_SHA\}", texto, re.MULTILINE), "o /healthz lê GIT_SHA (api/ambiente.py)"


def test_dockerfile_leva_migrations_e_fixtures_para_o_pacote():
    """G-0094: o pyproject faz `force-include` de migrations/ e fixtures/; sem copiá-las o `uv sync` do build da main falha."""
    texto = DOCKERFILE.read_text(encoding="utf-8")
    ordem = [texto.index(x) for x in ("COPY migrations/ ./migrations/", "COPY fixtures/ ./fixtures/", "--no-editable")]
    assert ordem == sorted(ordem), "copiar antes do segundo uv sync"
    ignorados = {x.strip() for x in (RAIZ / ".dockerignore").read_text().splitlines() if x.strip() and not x.startswith("#")}
    assert not {"migrations", "fixtures", "docker"} & ignorados
    assert not re.search(r"^(?:ENV|ARG)\s+\w*(?:KEY|TOKEN|SECRET|PASSWORD|DATABASE_URL)\w*", texto, re.MULTILINE), "sem segredo na imagem"
    assert "uv sync --locked" in texto, "instala do uv.lock"


def test_dockerignore_deixa_segredo_e_lixo_fora_do_contexto():
    linhas = {x.strip() for x in (RAIZ / ".dockerignore").read_text().splitlines() if x.strip() and not x.startswith("#")}
    assert {".git", ".env", ".env.*", "tests", ".venv"} <= linhas
    assert "!.env.example" not in linhas


# ------------------------------------------------------------------ scripts


def test_scripts_tem_sintaxe_valida_e_modo_estrito():
    for script in (RELEASE, DEPLOY):
        assert os.access(script, os.X_OK), f"{script.name} precisa ser executável"
        assert subprocess.run(["bash", "-n", str(script)], check=False).returncode == 0
        assert "set -euo pipefail" in script.read_text(encoding="utf-8")
    assert os.access(ENTRADA, os.X_OK) and subprocess.run(["sh", "-n", str(ENTRADA)], check=False).returncode == 0


def _repo_temporario(tmp_path: Path, changelog: str) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(RELEASE, repo / "scripts" / "release.sh")
    (repo / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    (repo / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.2.0"\n', encoding="utf-8")
    ambiente = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@exemplo.test",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@exemplo.test",
    }
    for comando in (["init", "-q", "-b", "main"], ["add", "."], ["commit", "-q", "-m", "chore: base"]):
        subprocess.run(["git", *comando], cwd=repo, check=True, env=ambiente, capture_output=True)
    return repo


def _release(repo: Path, *args: str, check_cmd: str = "true") -> subprocess.CompletedProcess[str]:
    ambiente = {**os.environ, "CHECK_CMD": check_cmd, "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@exemplo.test"}
    return subprocess.run(["bash", "scripts/release.sh", *args], cwd=repo, env=ambiente, capture_output=True, text=True, check=False)


def test_release_sem_versao_ou_versao_invalida_falha(tmp_path):
    repo = _repo_temporario(tmp_path, "## [0.2.0] - 2026-10-30\n")
    assert _release(repo).returncode != 0
    assert _release(repo, "0.2").returncode != 0
    assert _release(repo, "v0.2.0").returncode != 0, "a versão é X.Y.Z; o script põe o `v` na tag"


def test_release_recusa_versao_fora_do_changelog_e_nao_cria_tag(tmp_path):
    repo = _repo_temporario(tmp_path, "## [Unreleased]\n## [0.1.0] - 2026-10-29\n")
    resultado = _release(repo, "0.2.0")
    assert resultado.returncode != 0 and "CHANGELOG" in resultado.stderr
    assert subprocess.run(["git", "tag"], cwd=repo, capture_output=True, text=True, check=True).stdout == ""


def test_release_recusa_versao_diferente_do_pyproject(tmp_path):
    repo = _repo_temporario(tmp_path, "## [0.3.0] - 2026-10-30\n## [0.2.0] - 2026-10-29\n")
    resultado = _release(repo, "0.3.0")
    assert resultado.returncode != 0 and "pyproject" in resultado.stderr


def test_release_com_check_vermelho_nao_cria_tag(tmp_path):
    repo = _repo_temporario(tmp_path, "## [0.2.0] - 2026-10-30\n")
    assert _release(repo, "0.2.0", check_cmd="false").returncode != 0
    assert subprocess.run(["git", "tag"], cwd=repo, capture_output=True, text=True, check=True).stdout == ""


def test_release_cria_tag_anotada_e_so_imprime_o_push(tmp_path):
    repo = _repo_temporario(tmp_path, "## [0.2.0] - 2026-10-30\n")
    resultado = _release(repo, "0.2.0")
    assert resultado.returncode == 0, resultado.stderr
    assert subprocess.run(["git", "cat-file", "-t", "v0.2.0"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip() == "tag"
    assert "git push origin v0.2.0" in resultado.stdout
    assert "gh release create v0.2.0" in resultado.stdout
    assert _release(repo, "0.2.0").returncode != 0, "tag repetida é recusada"


def _atalhos(tmp_path: Path) -> tuple[Path, Path]:
    """`ssh` e `curl` falsos com ESTADO: a IMAGE_TAG gravada no «Coolify», a tag que de fato roda e o /healthz que a reflete.

    Variáveis do falso: PATCH_FALHA (código HTTP que o PATCH devolve), PATCH_IGNORADO=1 (aceita e não grava), DEPLOY_PRESO=1 (o deploy
    termina «finished» mas a tag velha continua rodando), HEALTHZ_SEQ (códigos por chamada), SHA_HEALTHZ (git_sha que o /healthz diz).
    """
    bin_dir, log = tmp_path / "bin", tmp_path / "chamadas.log"
    bin_dir.mkdir(exist_ok=True)
    (tmp_path / "estado.tag").write_text("v0.0.9")
    (tmp_path / "estado.rodando").write_text("v0.0.9")
    ssh = (
        "#!/usr/bin/env bash\n"
        'echo "ssh $*" >> "$LOG_FALSO"\n'
        'case "$*" in\n'
        '  *df*) echo " ${DISCO_USADO:-40}%" ;;\n'
        '  *loadavg*) echo "${CARGA:-0.50}" ;;\n'
        '  *healthz*) n=$(( $(cat "$LOG_FALSO.n" 2>/dev/null || echo 0) + 1 )); echo $n > "$LOG_FALSO.n"\n'
        '     set -- ${HEALTHZ_SEQ:-200}; [ "$n" -gt "$#" ] && n=$#; shift $((n - 1)); cod="$1"\n'
        '     v=$(cat "$ESTADO_DIR/estado.rodando"); v=${v#v}\n'
        '     [ "$cod" = 200 ] && printf \'{"ok":true,"version":"%s","git_sha":"%s","built_at":"x"}\' "$v" "${SHA_HEALTHZ:-$SHA_ESPERADO}"\n'
        "     printf '\\n%s' \"$cod\" ;;\n"
        "esac\n"
    )
    curl = (
        "#!/usr/bin/env bash\n"
        'echo "curl $*" >> "$LOG_FALSO"\n'
        "cat > /dev/null 2>&1 || true\n"
        'case "$*" in\n'
        '  *"-X PATCH"*)\n'
        '     if [ -n "${PATCH_FALHA:-}" ]; then echo \'{"message":"This field is not allowed."}\'; exit 22; fi\n'
        '     [ "${PATCH_IGNORADO:-0}" = 1 ] || sed -n \'s/.*"value":"\\([^"]*\\)".*/\\1/p\' <<<"$*" > "$ESTADO_DIR/estado.tag"\n'
        '     echo "{}" ;;\n'
        '  *"-X POST"*) [ "${DEPLOY_PRESO:-0}" = 1 ] || cp "$ESTADO_DIR/estado.tag" "$ESTADO_DIR/estado.rodando"\n'
        '     echo \'{"deployments":[{"deployment_uuid":"d1"}]}\' ;;\n'
        '  *deployments/d1*) echo \'{"status":"finished"}\' ;;\n'
        '  *envs*) printf \'[{"key":"IMAGE_TAG","value":"%s"}]\' "$(cat "$ESTADO_DIR/estado.tag")" ;;\n'
        "esac\n"
    )
    for nome, conteudo in (("ssh", ssh), ("curl", curl)):
        (bin_dir / nome).write_text(conteudo)
        (bin_dir / nome).chmod((bin_dir / nome).stat().st_mode | stat.S_IXUSR)
    return bin_dir, log


def _deploy(tmp_path: Path, *args: str, agora: str = "2026-11-02 13:00", **env: str) -> tuple[subprocess.CompletedProcess[str], str]:
    bin_dir, log = _atalhos(tmp_path)
    (tmp_path / "config").mkdir(exist_ok=True)
    piloto = tmp_path / "config" / "dias-piloto.txt"
    if not piloto.exists():
        piloto.write_text("2026-12-25\n")
    ambiente = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "LOG_FALSO": str(log),
        "ESTADO_DIR": str(tmp_path),
        "DEPLOY_TESTE": "1",
        "DEPLOY_AGORA": agora,
        "SHA_ESPERADO": SHA_FALSO,
        "DIAS_PILOTO_ARQUIVO": str(piloto),
        "ESPERA_S": "0",
        "S5_SSH": "danilo@s5.exemplo.test",
        "COOLIFY_URL": "https://coolify.exemplo.test",
        "COOLIFY_TOKEN": "token-falso-so-do-teste",
        "COOLIFY_APP_UUID": "uuid-falso-0001",
        "HEALTHZ_URL": "http://s5.exemplo.test:8000/healthz",
        **env,
    }
    resultado = subprocess.run(["bash", str(DEPLOY), *args], env=ambiente, capture_output=True, text=True, check=False, cwd=tmp_path)
    return resultado, log.read_text() if log.exists() else ""


def _rodando(tmp_path: Path) -> str:
    return (tmp_path / "estado.rodando").read_text().strip()


def test_deploy_sem_executar_so_imprime_e_nao_chama_nada(tmp_path):
    resultado, chamadas = _deploy(tmp_path, "v0.2.0")
    assert resultado.returncode == 0, resultado.stderr
    assert chamadas == "", "dry-run não chama ssh nem curl"
    assert "v0.2.0" in resultado.stdout and "IMAGE_TAG" in resultado.stdout and "/healthz" in resultado.stdout
    assert "token-falso-so-do-teste" not in resultado.stdout + resultado.stderr


def test_deploy_exige_tag_semver(tmp_path):
    for ruim in ("0.2.0", "main", "latest", "v0.2", "v0.2.0;rm"):
        resultado, chamadas = _deploy(tmp_path, ruim, "--executar")
        assert resultado.returncode != 0 and chamadas == "", ruim


def test_deploy_exige_healthz_url_e_recusa_formato_estranho(tmp_path):
    for ruim in ("", "http://x/healthz;rm -rf /", "https://x/healthz", "http://x/outra"):
        resultado, chamadas = _deploy(tmp_path, "v0.2.0", "--executar", HEALTHZ_URL=ruim)
        assert resultado.returncode == 2 and chamadas == "", ruim


def test_deploy_relogio_falso_so_com_deploy_teste(tmp_path):
    resultado, chamadas = _deploy(tmp_path, "v0.2.0", "--executar", DEPLOY_TESTE="0")
    assert resultado.returncode == 2 and "DEPLOY_TESTE" in resultado.stderr and chamadas == ""


@pytest.mark.parametrize(
    "agora",
    [
        "2026-11-02 09:30",
        "2026-11-02 11:59",
        "2026-11-02 14:01",
        "2026-11-02 18:00",
        "2026-11-02 20:29",
        "2026-11-02 02:00",
        "2026-11-02 08:00",
    ],
)
def test_deploy_recusa_hora_fora_da_janela(tmp_path, agora):
    resultado, chamadas = _deploy(tmp_path, "v0.2.0", "--executar", agora=agora)
    assert resultado.returncode == 3 and "janela" in resultado.stderr
    assert chamadas == "", "bloqueio de hora vem antes de qualquer chamada remota"


@pytest.mark.parametrize("agora", ["2026-11-02 12:30", "2026-11-02 14:00", "2026-11-02 20:31", "2026-11-02 23:50"])
def test_deploy_aceita_hora_da_janela(tmp_path, agora):
    resultado, _ = _deploy(tmp_path, "v0.2.0", "--executar", agora=agora)
    assert resultado.returncode == 0, resultado.stderr


def test_deploy_recusa_dia_de_piloto(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "dias-piloto.txt").write_text("# dias de piloto\n2026-11-29\n")
    resultado, chamadas = _deploy(tmp_path, "v0.2.0", "--executar", agora="2026-11-29 13:00")
    assert resultado.returncode == 3 and "piloto" in resultado.stderr and chamadas == ""


@pytest.mark.parametrize("conteudo", [None, "", "# só comentário\n", "29/11/2026\n"])
def test_deploy_sem_lista_de_dias_de_piloto_falha_fechado(tmp_path, conteudo):
    """G-0096: arquivo ausente, vazio ou sem data válida NÃO libera o deploy."""
    (tmp_path / "config").mkdir()
    arquivo = tmp_path / "config" / "dias-piloto.txt"
    if conteudo is None:
        env = {"DIAS_PILOTO_ARQUIVO": str(tmp_path / "nao-existe.txt")}
    else:
        arquivo.write_text(conteudo)
        env = {}
    resultado, chamadas = _deploy(tmp_path, "v0.2.0", "--executar", **env)
    assert resultado.returncode == 3 and "falha fechado" in resultado.stderr and chamadas == ""


def test_dias_piloto_do_repo_tem_datas_validas():
    linhas = [x.strip() for x in (RAIZ / "config" / "dias-piloto.txt").read_text().splitlines() if x.strip() and not x.startswith("#")]
    assert linhas and all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", x) for x in linhas)


@pytest.mark.parametrize(("env", "motivo"), [({"DISCO_USADO": "90"}, "disco"), ({"CARGA": "6.20"}, "carga")])
def test_deploy_recusa_s5_sem_folga(tmp_path, env, motivo):
    resultado, chamadas = _deploy(tmp_path, "v0.2.0", "--executar", **env)
    assert resultado.returncode == 4 and motivo in resultado.stderr
    assert "-X PATCH" not in chamadas, "nada é gravado no Coolify se o portão reprova"


def test_deploy_caminho_feliz_grava_relê_dispara_e_confere_versao_e_sha(tmp_path):
    resultado, chamadas = _deploy(tmp_path, "v0.2.0", "--executar")
    assert resultado.returncode == 0, resultado.stderr
    linhas = chamadas.splitlines()
    indice_healthz = [i for i, linha in enumerate(linhas) if "healthz" in linha]
    indice_patch = next(i for i, linha in enumerate(linhas) if "-X PATCH" in linha)
    assert len(indice_healthz) >= 2 and indice_healthz[0] < indice_patch < indice_healthz[-1]
    assert "-X POST" in chamadas and all("--fail-with-body" in linha for linha in linhas if linha.startswith("curl"))
    assert "token-falso-so-do-teste" not in chamadas, "o token vai por stdin (curl -K -), nunca nos argumentos"
    assert "v0.0.9" in resultado.stdout, "mostra a tag anterior: é o rollback"
    assert _rodando(tmp_path) == "v0.2.0" and "OK: v0.2.0" in resultado.stdout


def test_deploy_com_patch_recusado_nao_anuncia_nem_dispara(tmp_path):
    """G-0095: Coolify devolve 422 no PATCH; antes o script disparava o deploy da tag velha e dizia «OK»."""
    resultado, chamadas = _deploy(tmp_path, "v0.2.0", "--executar", PATCH_FALHA="422")
    assert resultado.returncode == 8 and "OK:" not in resultado.stdout
    assert "-X POST" not in chamadas and _rodando(tmp_path) == "v0.0.9"


def test_deploy_com_patch_ignorado_em_silencio_e_pego_pela_releitura(tmp_path):
    resultado, chamadas = _deploy(tmp_path, "v0.2.0", "--executar", PATCH_IGNORADO="1")
    assert resultado.returncode == 8 and "relida" in resultado.stderr and "-X POST" not in chamadas


def test_deploy_que_termina_com_a_tag_velha_rodando_nao_e_ok(tmp_path):
    """G-0095: deployment «finished» e /healthz 200, mas com a versão anterior: falha e volta (não anuncia a tag nova)."""
    resultado, _ = _deploy(tmp_path, "v0.2.0", "--executar", DEPLOY_PRESO="1", HEALTH_TENTATIVAS="2")
    assert resultado.returncode == 6 and "OK:" not in resultado.stdout
    assert "version=0.0.9" in resultado.stderr


def test_deploy_com_git_sha_diferente_nao_e_ok(tmp_path):
    resultado, _ = _deploy(tmp_path, "v0.2.0", "--executar", SHA_HEALTHZ="f" * 40, HEALTH_TENTATIVAS="2")
    assert resultado.returncode == 7 and "OK:" not in resultado.stdout, "nem a nova nem a anterior batem o sha: intervenção manual"


def test_deploy_com_healthz_ruim_depois_volta_para_a_tag_anterior(tmp_path):
    resultado, chamadas = _deploy(tmp_path, "v0.2.0", "--executar", HEALTHZ_SEQ="200 500 500 500 200", HEALTH_TENTATIVAS="3")
    assert resultado.returncode == 6, resultado.stderr
    patches = [linha for linha in chamadas.splitlines() if "-X PATCH" in linha]
    assert len(patches) == 2 and "v0.2.0" in patches[0] and "v0.0.9" in patches[1]
    assert "rollback" in resultado.stderr and _rodando(tmp_path) == "v0.0.9"


def test_deploy_com_rollback_que_tambem_falha_sai_com_7(tmp_path):
    resultado, _ = _deploy(tmp_path, "v0.2.0", "--executar", HEALTHZ_SEQ="200 500", HEALTH_TENTATIVAS="2")
    assert resultado.returncode == 7


def test_deploy_com_healthz_fora_do_ar_antes_para_sem_gravar(tmp_path):
    resultado, chamadas = _deploy(tmp_path, "v0.2.0", "--executar", HEALTHZ_SEQ="500")
    assert resultado.returncode == 5 and "-X PATCH" not in chamadas


def test_entrada_tira_o_cr_de_arquivo_com_crlf(tmp_path):
    r = _entrada(tmp_path, {"CHAVE_H16": ("a" * 40 + "\r\n", 0o600)}, "sh", "-c", 'test "$CHAVE_H16" = ' + "a" * 40)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize(
    ("env", "motivo"),
    [
        ({"COOLIFY_URL": "http://coolify.exemplo.test"}, "https"),
        ({"COOLIFY_APP_UUID": "x;rm"}, "UUID"),
        ({"S5_SSH": "-oProxyCommand=x"}, "S5_SSH"),
    ],
)
def test_deploy_recusa_destino_inseguro_antes_de_chamar(tmp_path, env, motivo):
    resultado, chamadas = _deploy(tmp_path, "v0.2.0", "--executar", **env)
    assert resultado.returncode == 2 and motivo in resultado.stderr and chamadas == ""
