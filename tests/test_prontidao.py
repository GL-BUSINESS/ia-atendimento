"""`readyz`: `ia.v_prontidao` + falhas duras (banco, worker sem heartbeat, fila parada, artefatos, migração) + LISTEN/NOTIFY em conexão direta."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ia_atendimento.prontidao import ler_prontidao, readyz, verificar_listen_notify
from tests import fixtures_fila as ff
from tests.fixtures_fila import inserir_atendimento

conn_app, conn_super, relogio, conninfo_app = ff.conn_app, ff.conn_super, ff.relogio, ff.conninfo_app

pytestmark = pytest.mark.banco
MIGRACOES = Path(__file__).resolve().parent.parent / "migrations"
# a view compara o lease com o now() do BANCO (que o teste não controla): leases vencidos usam o relógio real, os instantes da fila usam o falso
VENCIDO_NO_BANCO = datetime.now(UTC) - timedelta(hours=1)


def semear_saudavel(conn, agora) -> None:
    """Estado de uma instância pronta: worker com batimento, os 4 artefatos, nada atrasado."""
    conn.execute("INSERT INTO procrastinate.procrastinate_workers (last_heartbeat) VALUES (%s)", (agora - timedelta(seconds=5),))
    for tipo in ("roteiro", "regras", "catalogo", "motor"):
        conn.execute("INSERT INTO ia.artefato_versao (tipo, numero, descricao, aprovado_por) VALUES (%s, 1, 'v1', 'teste')", (tipo,))


def job_todo(conn, agora, idade: timedelta) -> None:
    conn.execute(
        "INSERT INTO procrastinate.procrastinate_jobs (queue_name, task_name, status, scheduled_at) VALUES ('default', 'ia:turno', 'todo', %s)",
        (agora - idade,),
    )


def test_le_a_view_v_prontidao(conn_app, conn_super, relogio):
    agora = relogio.agora()
    semear_saudavel(conn_super, agora)
    inserir_atendimento(conn_super, estado="aberto")
    inserir_atendimento(conn_super, estado="aguardando_cliente")
    inserir_atendimento(conn_super, estado="pausado")
    inserir_atendimento(conn_super, estado="reservado")
    inserir_atendimento(conn_super, estado="aberto", iniciado_em=VENCIDO_NO_BANCO, lease_ate=VENCIDO_NO_BANCO + timedelta(minutes=1))
    p = ler_prontidao(conn_app, relogio)
    # `abertos` = tudo que a IA atende agora, inclusive o `reservado` comum; pausado e agendado ficam de fora
    assert (p.abertos, p.reservados, p.pausados, p.repassando, p.agendados, p.lease_vencidos) == (4, 1, 1, 0, 0, 1)
    assert (p.modo, p.ia_ativa) == ("duble", False)
    assert p.pronto and p.falhas_duras == ()
    assert p.workers_vivos == 1 and p.todo_mais_velho_s is None and p.artefatos_faltando == ()


def test_falhas_duras_derrubam_o_pronto_e_as_moles_nao(conn_app, conn_super, relogio):
    agora = relogio.agora()
    p = ler_prontidao(conn_app, relogio)  # banco vazio: sem worker e sem artefatos
    assert not p.pronto
    assert set(p.falhas_duras) == {"workers_sem_heartbeat", "artefatos_ausentes"}
    assert p.artefatos_faltando == ("catalogo", "motor", "regras", "roteiro")

    semear_saudavel(conn_super, agora)
    assert ler_prontidao(conn_app, relogio).pronto

    # job todo vencido há mais de 10 min: fila parada
    job_todo(conn_super, agora, timedelta(minutes=11))
    assert ler_prontidao(conn_app, relogio).falhas_duras == ("fila_parada",)
    assert round(ler_prontidao(conn_app, relogio).todo_mais_velho_s) == 660
    conn_super.execute("DELETE FROM procrastinate.procrastinate_jobs")
    job_todo(conn_super, agora, timedelta(minutes=9))  # 9 min: ainda tolerável
    assert ler_prontidao(conn_app, relogio).pronto
    conn_super.execute("DELETE FROM procrastinate.procrastinate_jobs")
    job_todo(conn_super, agora, -timedelta(hours=2))  # agendado para daqui a 2 h: não conta como atrasado
    assert ler_prontidao(conn_app, relogio).pronto

    # batimento velho (> 30 s) = worker morto
    conn_super.execute("UPDATE procrastinate.procrastinate_workers SET last_heartbeat = %s", (agora - timedelta(seconds=31),))
    assert ler_prontidao(conn_app, relogio).falhas_duras == ("workers_sem_heartbeat",)

    # campos moles (lease vencido, repassando parado) aparecem, mas não derrubam
    conn_super.execute("UPDATE procrastinate.procrastinate_workers SET last_heartbeat = %s", (agora,))
    inserir_atendimento(conn_super, estado="aberto", iniciado_em=VENCIDO_NO_BANCO, lease_ate=VENCIDO_NO_BANCO + timedelta(minutes=1))
    p = ler_prontidao(conn_app, relogio)
    assert p.lease_vencidos == 1 and p.pronto


def test_readyz_confere_o_checksum_das_migracoes(conn_app, conn_super, relogio, tmp_path):
    semear_saudavel(conn_super, relogio.agora())
    assert readyz(conn_app, relogio, diretorio_migracoes=MIGRACOES).pronto
    # arquivo com conteúdo diferente do aplicado: divergência é falha dura
    copia = tmp_path / "migracoes"
    copia.mkdir()
    for arquivo in MIGRACOES.glob("*.up.sql"):
        (copia / arquivo.name).write_bytes(arquivo.read_bytes() + (b"\n-- editada\n" if arquivo.name.startswith("0001") else b""))
    assert readyz(conn_app, relogio, diretorio_migracoes=copia).falhas_duras == ("migracao_divergente",)
    pendente = tmp_path / "pendente"
    pendente.mkdir()
    for arquivo in MIGRACOES.glob("*.up.sql"):
        (pendente / arquivo.name).write_bytes(arquivo.read_bytes())
    (pendente / "0003_nova.up.sql").write_text("SELECT 1;\n")
    assert readyz(conn_app, relogio, diretorio_migracoes=pendente).falhas_duras == ("migracao_pendente",)


def test_readyz_banco_inacessivel_e_falha_dura_sem_vazar_a_conexao(relogio):
    from ia_atendimento.prontidao import readyz_por_dsn

    p = readyz_por_dsn("host=127.0.0.1 port=1 dbname=x user=u password=segredo-xyz connect_timeout=1", relogio)
    assert not p.pronto and p.falhas_duras == ("banco_inacessivel",)
    assert "segredo-xyz" not in repr(p)


def test_listen_notify_chega_em_conexao_direta(conninfo_app):
    assert verificar_listen_notify(conninfo_app, timeout_s=3) is True


def test_listen_notify_que_nao_chega_e_falso_e_nao_trava(conninfo_app):
    """Pooler em modo transação engole o NOTIFY: simulado com um emissor que não notifica."""
    import time

    inicio = time.monotonic()
    assert verificar_listen_notify(conninfo_app, timeout_s=0.5, notificar=lambda *_: None) is False
    assert time.monotonic() - inicio < 3


def test_listen_notify_so_vale_se_o_payload_for_o_nosso(conninfo_app):
    """Um NOTIFY de outro emissor no mesmo canal não prova que o NOSSO chegou."""
    import psycopg

    def notificar_outro(conninfo: str, canal: str, _token: str) -> None:
        with psycopg.connect(conninfo, autocommit=True) as conn:
            conn.execute("SELECT pg_notify(%s, 'outro')", (canal,))

    assert verificar_listen_notify(conninfo_app, timeout_s=0.5, notificar=notificar_outro) is False


def test_readyz_inclui_listen_notify_quando_pedido(conn_app, conn_super, relogio, conninfo_app):
    semear_saudavel(conn_super, relogio.agora())
    p = readyz(conn_app, relogio, conninfo_direto=conninfo_app)
    assert p.listen_notify is True and p.pronto
    assert readyz(conn_app, relogio).listen_notify is None  # não verificado
