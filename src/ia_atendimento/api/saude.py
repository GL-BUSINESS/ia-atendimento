"""`/healthz`, `/readyz` e `/saude` (contrato 08 §5.6). Sem PII: contagens, instantes e códigos.

- `/healthz` (sem token): só `{ok, version, git_sha, built_at}`; não toca no banco.
- `/readyz` (qualquer token válido): `ia.v_prontidao` + falhas duras da B1.3 (`prontidao.readyz`). 503 `nao_pronto` só nas falhas duras.
  `repassando_ha_10min` é
  CONTAGEM (a view devolve os chats; a lista de ids não sai).
- `/saude`: `{ok, ia_ativa, modo, fila:{todo, doing, mais_velho_s}}`.
"""

from __future__ import annotations

from typing import Any

import psycopg

from ia_atendimento import prontidao
from ia_atendimento.api.contexto import ContextoApi
from ia_atendimento.api.erros import ErroApi


def healthz(ctx: ContextoApi) -> dict[str, Any]:
    return {"ok": True, "version": ctx.versao, "git_sha": ctx.git_sha, "built_at": ctx.built_at}


def _espelho_pendente_mais_velho_s(conn: psycopg.Connection) -> float | None:
    linha = conn.execute("SELECT extract(epoch FROM now() - min(criado_em)) FROM ia.espelho_evento WHERE enviado_em IS NULL").fetchone()
    return None if linha is None or linha[0] is None else round(float(linha[0]), 1)


def _prontidao(ctx: ContextoApi) -> prontidao.Prontidao:
    if ctx.diretorio_migracoes is None:  # sem a pasta não há como conferir checksum nem pendência: falha FECHADO (R1-09), nunca em silêncio
        raise ErroApi("nao_pronto", detalhe={"falhas": ["migracoes_nao_conferidas"]})
    opcoes: dict[str, Any] = {"conninfo_direto": ctx.dsn} if ctx.dsn else {}
    if ctx.diretorio_migracoes is not None:
        opcoes["diretorio_migracoes"] = ctx.diretorio_migracoes
    if ctx.dsn:
        return prontidao.readyz_por_dsn(ctx.dsn, **opcoes)
    with ctx.conexao() as conn:
        return prontidao.readyz(conn, **opcoes)


def readyz(ctx: ContextoApi) -> tuple[int, dict[str, Any]]:
    p = _prontidao(ctx)
    if not p.pronto:
        raise ErroApi("nao_pronto", detalhe={"falhas": list(p.falhas_duras)})
    with ctx.conexao() as conn:
        espelho = _espelho_pendente_mais_velho_s(conn)
    return 200, {
        "abertos": p.abertos, "reservados": p.reservados, "repassando": p.repassando, "pausados": p.pausados, "agendados": p.agendados,
        "mais_velho_em": p.mais_velho_em.isoformat() if p.mais_velho_em else None,
        "proxima_retomada_em": p.proxima_retomada_em.isoformat() if p.proxima_retomada_em else None,
        "lease_vencidos": p.lease_vencidos, "repassando_ha_10min": len(p.repassando_ha_10min),
        "espelho_pendente_mais_velho_s": espelho, "batimento_idade_s": None,  # o batimento da vigia é consumido na B1.6
        "modo": p.modo, "ia_ativa": p.ia_ativa,
    }  # fmt: skip


_SQL_FILA = """
SELECT count(*) FILTER (WHERE status = 'todo'), count(*) FILTER (WHERE status = 'doing'),
       extract(epoch FROM now() - min(scheduled_at) FILTER (WHERE status = 'todo' AND scheduled_at <= now()))
FROM procrastinate.procrastinate_jobs WHERE status IN ('todo', 'doing')
"""


def saude(ctx: ContextoApi) -> tuple[int, dict[str, Any]]:
    with ctx.conexao() as conn:
        todo, doing, mais_velho = conn.execute(_SQL_FILA).fetchone()
        ia_ativa = ctx.leitor.valor(conn, "ia_ativa")
        modo = ctx.leitor.valor(conn, "modo")
    return 200, {
        "ok": True, "ia_ativa": ia_ativa, "modo": modo,
        "fila": {"todo": int(todo), "doing": int(doing), "mais_velho_s": None if mais_velho is None else round(float(mais_velho), 1)},
    }  # fmt: skip
