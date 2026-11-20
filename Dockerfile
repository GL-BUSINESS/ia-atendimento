# Imagem do ia-atendimento (orquestrador e worker usam a MESMA imagem; o compose escolhe o comando).
# Multi-stage com uv: `construtor` instala as dependências do uv.lock num venv; `runtime` leva só o venv e o código.
# Sem segredo na imagem: configuração por env do compose e segredos por arquivo 0600 (docker/ia-entrada.sh; docs/DEPLOY.md §4).
# A versão do Python é a do .python-version (um teste confere os dois).
ARG PYTHON_VERSION=3.13

# ---------------------------------------------------------------- construtor ---
FROM python:${PYTHON_VERSION}-slim AS construtor

# uv pinado (mesma versão do desenvolvimento); instala do PyPI, sem depender do ghcr.io no builder da S3
ARG UV_VERSION=0.13.5
RUN pip install --no-cache-dir "uv==${UV_VERSION}"

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# 1) só dependências (camada em cache enquanto pyproject/uv.lock não mudam); --locked falha se o lock não bate
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# 2) o projeto (hatchling precisa do README.md declarado no pyproject), sem editable: o venv não aponta para /app/src.
#    migrations/ e fixtures/ entram no wheel (`force-include` do pyproject): o /readyz confere o checksum das migrações e o gateway lê
#    as fixtures do dublê. Sem elas o build da main falha (G-0094).
COPY README.md ./
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY fixtures/ ./fixtures/
RUN uv sync --locked --no-dev --no-editable \
    && /opt/venv/bin/python -c "import importlib.resources as r; m = r.files('ia_atendimento') / 'migrations'; assert any(p.name.endswith('.up.sql') for p in m.iterdir()), 'migrations fora do pacote'"

# ------------------------------------------------------------------- runtime ---
FROM python:${PYTHON_VERSION}-slim AS runtime

# uid/gid do processo. O código recusa arquivo de segredo com qualquer bit de grupo/outros (cifra.py, segredos.py, ia-entrada):
# na S5 os arquivos de ${IA_SEGREDOS_DIR} são 0600 com DONO 10001 (uid daqui), o diretório 0750 root:10001 (G-0097).
# Mudar o uid exige mudar o kit kits/s5 (IA_UID) junto.
ARG APP_UID=10001
ARG APP_GID=10001
# Preenchidos pelo workflow (`--build-arg`); o /healthz os devolve. Não são segredo.
ARG VERSION=0.0.0-dev
ARG GIT_SHA=desconhecido
ARG BUILT_AT=desconhecido

# GIT_SHA e BUILT_AT são lidos por api/ambiente.py e saem no /healthz (o deploy-s5.sh confere o git_sha; G-0095).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    IA_VERSION=${VERSION} \
    GIT_SHA=${GIT_SHA} \
    BUILT_AT=${BUILT_AT}

# A imagem oficial vem SEM os .pyc da stdlib e o processo não-root não os grava: sem isto todo `python -c` do HEALTHCHECK
# recompila a stdlib (medido no gl-gateway: 430 ms contra 89 ms de CPU). Só a stdlib; o uv já compilou o resto.
RUN python -m compileall -q -j0 -x /site-packages/ "$(python -c 'import sysconfig; print(sysconfig.get_path("stdlib"))')" \
    && groupadd --gid "${APP_GID}" app \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin app

COPY --from=construtor /opt/venv /opt/venv
# carrega os segredos de arquivo 0600 e executa o comando do serviço (sem ele o Settings recusa o boot)
COPY --chmod=0755 docker/ia-entrada.sh /usr/local/bin/ia-entrada

# `coolify.managed=true` NA IMAGEM: o CleanupDocker do Coolify apaga imagem sem esse rótulo e sem contêiner (memória
# coolify-cleanup-imagens). O compose também rotula os contêineres.
LABEL coolify.managed="true" \
      org.opencontainers.image.title="ia-atendimento" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILT_AT}"

USER ${APP_UID}:${APP_GID}
WORKDIR /app

# Healthcheck padrão da imagem: só prova que o pacote importa. O compose troca por serviço: o orquestrador consulta /healthz no IP do
# WireGuard (variável) e o worker roda `python -m ia_atendimento.worker --saude` (batimento no banco).
HEALTHCHECK --interval=120s --timeout=5s --start-period=30s --start-interval=2s --retries=3 \
    CMD ["python", "-c", "import ia_atendimento"]

ENTRYPOINT ["/usr/local/bin/ia-entrada"]
# O compose define `command:` por serviço. Padrão inofensivo.
CMD ["python", "-c", "import ia_atendimento; print('ia-atendimento: importa')"]
