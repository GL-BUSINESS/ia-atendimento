"""Acesso ao Postgres 18 descartável dos testes: papéis, bancos e execução de SQL em texto.

Nada aqui conversa com a S4: o servidor é um contêiner `postgres:18` (docker) ou o serviço do CI, sempre local.
"""

from __future__ import annotations

import re
import subprocess
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass

import psycopg
import psycopg.postgres
from psycopg import sql
from psycopg.adapt import Loader

SENHA_SUPER = "descartavel"
SENHA_LOGIN = "x"
HOSTS_LOCAIS = frozenset({"localhost", "127.0.0.1", "::1"})
GRUPOS = ("ia_owner", "ia_app", "ia_leitura", "ia_qualidade")
# login -> grupo (como a infra do estudo E cria: `_a`; o `intruso` não tem grupo nem grant)
LOGINS = {"ia_app_a": "ia_app", "ia_leitura_a": "ia_leitura", "ia_qualidade_a": "ia_qualidade", "intruso": None}
SUPER = "postgres"


@dataclass(frozen=True)
class Servidor:
    host: str
    port: int

    def conectar(self, banco: str, usuario: str = SUPER, *, autocommit: bool = True, texto: bool = False) -> psycopg.Connection:
        senha = SENHA_SUPER if usuario == SUPER else SENHA_LOGIN
        conn = psycopg.connect(
            host=self.host, port=self.port, dbname=banco, user=usuario, password=senha, autocommit=autocommit, connect_timeout=5
        )
        if texto:
            registrar_texto(conn)
        return conn


class _Texto(Loader):
    """Devolve o texto cru do servidor (o que `psql -At` imprime): 't'/'f', numeric sem conversão, jsonb como veio."""

    def load(self, data: bytes | memoryview) -> str:
        return bytes(data).decode()


def registrar_texto(conn: psycopg.Connection) -> None:
    for tipo in psycopg.postgres.types:
        conn.adapters.register_loader(tipo.oid, _Texto)
        if tipo.array_oid:
            conn.adapters.register_loader(tipo.array_oid, _Texto)


def esperar_servidor(servidor: Servidor, limite_s: float = 90.0) -> None:
    """Espera a CONDIÇÃO (login TCP aceito), não um sinal: o servidor temporário do init só escuta no socket unix."""
    prazo = time.monotonic() + limite_s
    ultimo: Exception | None = None
    while time.monotonic() < prazo:
        try:
            with servidor.conectar("postgres") as conn:
                conn.execute("SELECT 1")
            return
        except psycopg.Error as exc:
            ultimo = exc
            time.sleep(0.25)
    raise RuntimeError(f"Postgres de teste não ficou pronto em {limite_s}s: {ultimo}")


def subir_docker(imagem: str) -> tuple[Servidor, Callable[[], None]]:
    nome = f"ia-pg18-pytest-{uuid.uuid4().hex[:8]}"
    cmd = [
        "docker", "run", "-d", "--rm", "--name", nome, "--label", "ia-atendimento-teste=1",
        "-p", "127.0.0.1::5432", "-e", f"POSTGRES_PASSWORD={SENHA_SUPER}", "--tmpfs", "/var/lib/postgresql:rw",
        imagem, "-c", "fsync=off", "-c", "full_page_writes=off", "-c", "synchronous_commit=off", "-c", "max_connections=60",
    ]  # fmt: skip
    subprocess.run(cmd, check=True, capture_output=True, text=True)

    def derrubar() -> None:
        subprocess.run(["docker", "rm", "-f", nome], check=False, capture_output=True)

    try:
        mapeada = subprocess.run(["docker", "port", nome, "5432/tcp"], check=True, capture_output=True, text=True).stdout
        achado = re.search(r"127\.0\.0\.1:(\d+)", mapeada)
        if achado is None:
            raise RuntimeError(f"porta do contêiner não encontrada: {mapeada!r}")
        servidor = Servidor("127.0.0.1", int(achado.group(1)))
        esperar_servidor(servidor)
    except BaseException:
        derrubar()
        raise
    return servidor, derrubar


def servidor_do_ambiente(host: str, port: int) -> Servidor:
    """Servidor já existente (serviço do CI). Recusa host que não seja local e cluster que já tenha papéis `ia_*`."""
    if host not in HOSTS_LOCAIS:
        raise RuntimeError(f"IA_TESTE_PG_HOST={host!r}: os testes só rodam em Postgres local descartável (nunca na S4)")
    servidor = Servidor(host, port)
    esperar_servidor(servidor)
    with servidor.conectar("postgres") as conn:
        existentes = conn.execute("SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)", (list(GRUPOS) + list(LOGINS),)).fetchall()
    if existentes:
        raise RuntimeError("cluster de teste já tem papéis ia_*: não é descartável, abortando para não tocar em infra real")
    return servidor


def criar_papeis(servidor: Servidor) -> None:
    """O que a infra faz antes da migração (estudo E): grupos NOLOGIN, logins `_a` e um papel sem grants."""
    with servidor.conectar("postgres") as conn:
        for grupo in GRUPOS:
            conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(grupo)))
        for login, grupo in LOGINS.items():
            partes = [sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(login), sql.Literal(SENHA_LOGIN))]
            if grupo:
                partes.append(sql.SQL("IN ROLE {}").format(sql.Identifier(grupo)))
            conn.execute(sql.SQL(" ").join(partes))


def criar_banco(servidor: Servidor, nome: str, *, modelo: str | None = None) -> None:
    ident = sql.Identifier(nome)
    with servidor.conectar("postgres") as conn:
        consulta = sql.SQL("CREATE DATABASE {} OWNER ia_owner").format(ident)
        if modelo:
            consulta += sql.SQL(" TEMPLATE {}").format(sql.Identifier(modelo))
        conn.execute(consulta)
        conn.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(ident))
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO ia_app, ia_leitura, ia_qualidade, intruso").format(ident))


def apagar_banco(servidor: Servidor, nome: str) -> None:
    with suppress(psycopg.Error), servidor.conectar("postgres") as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(nome)))


@dataclass(frozen=True)
class Banco:
    servidor: Servidor
    nome: str

    def conectar(self, usuario: str = SUPER, *, autocommit: bool = True, texto: bool = False) -> psycopg.Connection:
        return self.servidor.conectar(self.nome, usuario, autocommit=autocommit, texto=texto)

    @contextmanager
    def sessao(self, usuario: str = SUPER, *, texto: bool = False) -> Iterator[psycopg.Connection]:
        with self.conectar(usuario, texto=texto) as conn:
            yield conn

    def escalar(self, usuario: str, consulta: str) -> str:
        """Primeira coluna da última linha do último resultado, em texto (como `psql -At | tail -1`)."""
        return resultado_texto(self, usuario, consulta)


def novo_nome(prefixo: str) -> str:
    return f"{prefixo}_{uuid.uuid4().hex[:10]}"


def resultado_texto(banco: Banco, usuario: str, consulta: str) -> str:
    """Executa (protocolo simples, várias instruções) e devolve a última linha do último resultado com linhas."""
    ultimo = ""
    with banco.sessao(usuario, texto=True) as conn, conn.cursor() as cur:
        cur.execute(consulta)
        while True:
            if cur.description is not None:
                linhas = cur.fetchall()
                if linhas:
                    ultimo = "|".join("" if v is None else str(v) for v in linhas[-1])
            if not cur.nextset():
                break
    return ultimo


def texto_do_erro(exc: psycopg.Error) -> str:
    """Tudo que o `psql` imprimiria do erro: mensagem, detalhe, nome de restrição e contexto."""
    diag = exc.diag
    partes = [str(exc), diag.message_primary, diag.message_detail, diag.message_hint, diag.constraint_name, diag.context]
    return "\n".join(p for p in partes if p)
