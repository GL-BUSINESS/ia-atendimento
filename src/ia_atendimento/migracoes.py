"""Aplicador de migrações: roda `migrations/NNNN_nome.up.sql` em ordem e grava o ledger `ia.migracao`.

- Cada arquivo roda em UMA transação, junto com a linha do ledger (checksum = sha256 dos bytes do arquivo): ou entra tudo
  ou nada. Os arquivos fazem `SET ROLE ia_owner` sozinhos (estudo I §4); quem conecta é o superusuário da infra.
- Idempotente pelo ledger: migração já registrada é pulada; registrada com checksum diferente PARA tudo
  (`ChecksumDivergente`): migração aplicada nunca se edita, o desenho novo vira 0003+.
- Uso real na S4 é do dono (psql, `migrations/README.md`). O CLI abaixo só aceita banco local e nunca imprime a senha.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

PADRAO_ARQUIVO = re.compile(r"^(?P<numero>\d{4})_(?P<nome>[a-z0-9_]{1,60})\.up\.sql$")
PAPEL_DONO = "ia_owner"
CHAVE_TRAVA = "ia_atendimento.migracoes"  # advisory lock: dois aplicadores ao mesmo tempo não se atropelam
HOSTS_LOCAIS = frozenset({"localhost", "127.0.0.1", "::1", ""})


class MigracaoErro(Exception):
    pass


class ChecksumDivergente(MigracaoErro):
    pass


class MigracoesPendentes(MigracaoErro):
    pass


@dataclass(frozen=True)
class Migracao:
    id: str  # ex.: 0001_esquema (casa com o CHECK de ia.migracao.migracao_id)
    numero: int
    caminho: Path
    conteudo: bytes  # lido UMA vez: o checksum e o SQL executado saem destes mesmos bytes

    @property
    def checksum(self) -> str:
        """sha256 hex dos bytes do arquivo."""
        return hashlib.sha256(self.conteudo).hexdigest()

    def ler(self) -> str:
        try:
            return self.conteudo.decode("utf-8")
        except UnicodeDecodeError:
            raise MigracaoErro(f"{self.id}: o arquivo não é UTF-8") from None


def listar(diretorio: Path | str) -> list[Migracao]:
    """Migrações do diretório em ordem. Exige numeração contínua a partir de 0001, sem repetição."""
    base = Path(diretorio)
    if not base.is_dir():
        raise MigracaoErro(f"diretório de migrações não existe: {base}")
    achadas: list[Migracao] = []
    for caminho in sorted(base.glob("*.up.sql")):
        casou = PADRAO_ARQUIVO.fullmatch(caminho.name)
        if casou is None:
            raise MigracaoErro(f"nome de migração fora do padrão NNNN_nome.up.sql: {caminho.name}")
        numero = int(casou["numero"])
        achadas.append(Migracao(f"{casou['numero']}_{casou['nome']}", numero, caminho, caminho.read_bytes()))
    if not achadas:
        raise MigracaoErro(f"nenhuma migração em {base}")
    numeros = [m.numero for m in achadas]
    if len(set(numeros)) != len(numeros):
        raise MigracaoErro(f"número de migração repetido em {base}")
    for esperado, m in enumerate(achadas, start=1):
        if m.numero != esperado:
            raise MigracaoErro(f"falta a migração {esperado:04d} (achei {m.id})")
    return achadas


def _ledger(conn: psycopg.Connection) -> dict[str, str]:
    """`{id: checksum}`; vazio se o ledger ainda não existe (a 0001 é quem o cria)."""
    existe = conn.execute("SELECT to_regclass('ia.migracao') IS NOT NULL").fetchone()
    if not existe or not existe[0]:
        return {}
    return dict(conn.execute("SELECT migracao_id, checksum FROM ia.migracao").fetchall())


def _conferir_checksum(m: Migracao, registrado: str) -> None:
    if registrado != m.checksum:
        raise ChecksumDivergente(
            f"{m.id}: arquivo mudou depois de aplicada (banco {registrado[:12]}, arquivo {m.checksum[:12]}). "
            "Não edite migração aplicada; o desenho novo vira a próxima migração."
        )


def aplicar(conn: psycopg.Connection, diretorio: Path | str, *, papel: str = PAPEL_DONO) -> list[str]:
    """Aplica o que falta; devolve os ids aplicados nesta chamada. `conn` = superusuário da infra, sem transação aberta."""
    if conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
        raise MigracaoErro("a conexão já está dentro de uma transação; passe uma conexão sem transação aberta")
    migracoes = listar(diretorio)
    feitas: list[str] = []
    for m in migracoes:
        with conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (CHAVE_TRAVA,))
            registrado = _ledger(conn).get(m.id)
            if registrado is not None:
                _conferir_checksum(m, registrado)
                continue
            conn.execute(m.ler())  # sem parâmetros: protocolo simples, várias instruções, '%' do SQL fica intacto
            conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(papel)))
            conn.execute("INSERT INTO ia.migracao (migracao_id, checksum) VALUES (%s, %s)", (m.id, m.checksum))
            feitas.append(m.id)
    return feitas


def conferir(conn: psycopg.Connection, diretorio: Path | str) -> None:
    """Só leitura: o ledger tem todas as migrações do diretório e com o mesmo checksum. É o que o boot do orquestrador exige."""
    with conn.transaction():
        registradas = _ledger(conn)
    pendentes = []
    for m in listar(diretorio):
        if m.id not in registradas:
            pendentes.append(m.id)
        else:
            _conferir_checksum(m, registradas[m.id])
    if pendentes:
        raise MigracoesPendentes("migrações não aplicadas: " + ", ".join(pendentes))


def _so_local(entradas: str, aceitos: frozenset[str]) -> bool:
    return all(e in aceitos or e.startswith("/") for e in entradas.split(","))


def _host_local(dsn: str) -> bool:
    """O DSN só pode chegar a loopback ou socket unix. Olha `host`, `hostaddr` (que vence o host na conexão) e as variáveis
    PGHOST/PGHOSTADDR quando o DSN não diz; recusa `service` e a variável PGSERVICE (o pg_service.conf pode apontar para qualquer host)."""
    try:
        partes = conninfo_to_dict(dsn)
    except psycopg.ProgrammingError:
        return False
    if "service" in partes or os.environ.get("PGSERVICE"):  # o serviço pode trazer `hostaddr`, que vence o `host` do DSN
        return False
    host = partes.get("host") or os.environ.get("PGHOST") or ""
    hostaddr = partes.get("hostaddr") or os.environ.get("PGHOSTADDR") or ""
    return _so_local(host, HOSTS_LOCAIS) and (not hostaddr or _so_local(hostaddr, HOSTS_LOCAIS))


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m ia_atendimento.migracoes", description="Aplica as migrações em um Postgres LOCAL (docker)."
    )
    ap.add_argument(
        "--dsn", required=True, help="conexão do superusuário local, ex.: postgresql://postgres:...@127.0.0.1:5432/ia_atendimento"
    )
    ap.add_argument("--dir", default="migrations", help="diretório das migrações (padrão: migrations)")
    ap.add_argument("--conferir", action="store_true", help="só confere o ledger, não aplica nada")
    args = ap.parse_args(argv)
    if not _host_local(args.dsn):
        ap.error("o CLI só aceita banco local (localhost/127.0.0.1/socket). A S4 é aplicada pelo dono com psql, ver migrations/README.md")
    with psycopg.connect(args.dsn, autocommit=False, connect_timeout=10) as conn:
        if args.conferir:
            conferir(conn, args.dir)
            print("ledger confere com os arquivos")
            return 0
        feitas = aplicar(conn, args.dir)
    print("aplicadas: " + ", ".join(feitas) if feitas else "nada a aplicar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
