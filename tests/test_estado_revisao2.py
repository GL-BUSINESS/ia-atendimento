"""Casos da revisão 2 de contexto limpo (docs/REVISAO-B1.1-3010-r2.md): R1–R8, escritos antes da correção.

Sintético: CPF `123.456.789-09` (exemplo conhecido da varredura) e telefone de marcador; UUIDs gerados na hora.
"""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from ia_atendimento.estado import (
    ESTADOS_NAO_TERMINAIS,
    LEASE_AGUARDANDO_S,
    LEASE_TURNO_S,
    Mudancas,
    TransicaoInvalida,
    abrir,
    aguardar_cliente,
    aplicar,
    encerrar,
    iniciar,
    lease_de_espera,
    ler,
    renovar_lease,
)
from ia_atendimento.estado_conversa import EstadoConversa, OfertaCorrente, Pausa, janela_24h_aberta
from tests.estado_apoio import entrada

FUSO = ZoneInfo("America/Sao_Paulo")
FONE = "5511912345678"
CPF = "123.456.789-09"

# Reaper de lease da B1.3, literal de `origin/feat/b1-3-fila` (dd806ab, jobs.py `_SQL_LEASES`): o alarme do lembrete NÃO leva lock do chat,
# então só o lease protege quem espera o cliente.
SQL_LEASES_B13 = """
SELECT a.atendimento_id, a.chat_id, a.estado, a.gatilho, a.lease_ate FROM ia.atendimento a
WHERE a.estado IN ('reservado', 'aberto', 'aguardando_cliente', 'pausado') AND a.lease_ate < %s
  AND NOT EXISTS (SELECT 1 FROM procrastinate.procrastinate_jobs j WHERE j.lock = 'chat:' || a.chat_id AND j.status IN ('doing', 'todo'))
ORDER BY a.lease_ate LIMIT %s
"""


def _abrir(conn, relogio, versoes):
    return abrir(
        conn, origem="n8n_braco", entrada=entrada(), versoes=versoes, modo_global="duble", chats_teste=frozenset(), faixa_esforco="media",
        comissao_esperada_brl=None, relogio=relogio,
    )  # fmt: skip


def _aberto(conn, relogio, versoes):
    res = _abrir(conn, relogio, versoes)
    v = iniciar(conn, res.atendimento_id, res.versao, chatbot_antes="desligado", chatbot_estado="desligado_pela_ia", relogio=relogio)
    return res.atendimento_id, v


def _uuid7() -> uuid.UUID:
    ms = int(datetime.now(UTC).timestamp() * 1000)
    valor = (ms << 80) | (0x7 << 76) | (uuid.uuid4().int & ((1 << 76) - 1))
    valor = (valor & ~(0x3 << 62)) | (0x2 << 62)
    return uuid.UUID(int=valor)


def proxima_janela(instante: datetime) -> datetime:
    """Calendário de teste: seg–sáb 08:00–20:00 em São Paulo (o `Calendario.proxima_janela` da B1.3 tem a mesma forma)."""
    atual = instante.astimezone(FUSO)
    for avanco in range(0, 8):
        dia = (atual + timedelta(days=avanco)).date()
        if dia.isoweekday() == 7:
            continue
        abre, fecha = datetime.combine(dia, time(8), FUSO), datetime.combine(dia, time(20), FUSO)
        if atual < abre:
            return abre.astimezone(UTC)
        if atual < fecha:
            return atual.astimezone(UTC)
    raise AssertionError("sem janela")


# --- R1: UUID e id numérico passam; documento e telefone não ----------------------------------------------------------------------


def test_r1_referencia_aceita_uuid4_e_uuid7_sempre():
    """Antes: `\\d{6,}` recusava 20–28 % dos UUID. Aqui, 2000 de cada."""
    for _ in range(2000):
        for u in (uuid.uuid4(), _uuid7()):
            assert Pausa(agendamento_ref=str(u), retoma_fase="E3").agendamento_ref == str(u)
            assert OfertaCorrente(banco="FACTA", oferta_id=str(u), oferta_versao=1).oferta_id == str(u)


def test_r1_uuid_do_caso_do_revisor_e_oferta_numerica_de_6_a_10_digitos():
    assert Pausa(agendamento_ref="01912345-6789-7abc-8def-0123456789ab", retoma_fase="E3")
    for oferta in ("115716", "48213", "4821300000", "12345678"):
        assert OfertaCorrente(banco="FACTA", oferta_id=oferta, oferta_versao=1).oferta_id == oferta


@pytest.mark.parametrize("valor", ["12345678909", CPF, FONE, "11-91234-5678", "cpf12345678909", "551133334444", "12345678000195"])
def test_r1_continua_recusando_cpf_telefone_e_cnpj(valor):
    with pytest.raises(ValidationError):
        OfertaCorrente(banco="FACTA", oferta_id=valor, oferta_versao=1)
    with pytest.raises(ValidationError):
        EstadoConversa(fase="E1", campos_coletados=(valor.lower().replace(".", "").replace("-", ""),))


# --- R2: lease de quem espera o cliente cobre o lembrete adiado --------------------------------------------------------------------


def test_r2_lease_de_espera_segue_lembretes_janela_e_encerramento():
    t0 = datetime(2026, 11, 24, 19, 0, tzinfo=UTC)  # terça 16:00 local
    # lembrete 1: +4 h = 20:00 (fora da janela) → quarta 08:00; lembrete 2: +4 h = 12:00; encerra 2 h depois (14:00) + 30 min de folga
    esperado = datetime(2026, 11, 25, 14, 30, tzinfo=FUSO).astimezone(UTC)
    assert lease_de_espera(t0, intervalos_min=[240, 240], proxima_janela=proxima_janela) == esperado
    sabado = datetime(2026, 11, 28, 22, 0, tzinfo=UTC)  # sábado 19:00 local: fim de semana inteiro pela frente
    assert lease_de_espera(sabado, intervalos_min=[240, 240], proxima_janela=proxima_janela) == datetime(
        2026, 11, 30, 14, 30, tzinfo=FUSO
    ).astimezone(UTC)


@pytest.mark.banco
def test_r2_reaper_da_b1_3_nao_pega_quem_espera_o_lembrete_adiado_para_o_dia_seguinte(db_conn, relogio, versoes):
    relogio.agora = datetime(2026, 11, 24, 19, 0, tzinfo=UTC)  # terça 16:00 local
    atd, v = _aberto(db_conn, relogio, versoes)
    lease = lease_de_espera(relogio(), intervalos_min=[240, 240], proxima_janela=proxima_janela)
    aguardar_cliente(db_conn, atd, v, relogio=relogio, lease_ate=lease)
    assert ler(db_conn, atd).lease_ate == lease
    pega = lambda quando: db_conn.execute(SQL_LEASES_B13, (quando, 10)).fetchall()  # noqa: E731
    for horas in (1, 4, 13, 14, 20):  # com o lease antigo de 12 h o reaper devolvia o lead em 12,5 h, 13 h e 14 h
        assert pega(relogio() + timedelta(hours=horas)) == [], f"vencido cedo demais com {horas} h"
    assert pega(lease - timedelta(seconds=1)) == []
    assert [r[2] for r in pega(lease + timedelta(seconds=1))] == ["aguardando_cliente"]  # perdido mesmo: sem lembrete nem encerramento


@pytest.mark.banco
def test_r2_sem_lease_informado_vale_o_teto_de_96_h_que_cobre_fim_de_semana_com_feriado(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    aguardar_cliente(db_conn, atd, v, relogio=relogio)
    assert LEASE_AGUARDANDO_S == 96 * 3600 and ler(db_conn, atd).lease_ate == relogio() + timedelta(seconds=LEASE_AGUARDANDO_S)


@pytest.mark.banco
def test_r2_lease_informado_no_passado_e_recusado(db_conn, relogio, versoes):
    from ia_atendimento.estado import EntradaInvalida

    atd, v = _aberto(db_conn, relogio, versoes)
    with pytest.raises(EntradaInvalida):
        aguardar_cliente(db_conn, atd, v, relogio=relogio, lease_ate=relogio() - timedelta(seconds=1))


# --- R3: renovar_lease nunca encurta -------------------------------------------------------------------------------------------------


@pytest.mark.banco
def test_r3_renovar_lease_de_quem_espera_o_cliente_nao_encurta(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    v = aguardar_cliente(db_conn, atd, v, relogio=relogio)
    antes = ler(db_conn, atd).lease_ate
    relogio.avancar(minutes=1)
    renovar_lease(db_conn, atd, v, relogio=relogio)
    assert ler(db_conn, atd).lease_ate == antes  # +5 min seria bem menos que as 96 h; fica o maior
    assert LEASE_TURNO_S < LEASE_AGUARDANDO_S


@pytest.mark.banco
def test_r3_renovar_lease_estende_quando_o_novo_e_maior(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    relogio.avancar(minutes=4)
    renovar_lease(db_conn, atd, v, relogio=relogio)
    assert ler(db_conn, atd).lease_ate == relogio() + timedelta(seconds=LEASE_TURNO_S)


# --- R4: o trigger congela também estado_conversa e motivos --------------------------------------------------------------------------


@pytest.mark.banco
@pytest.mark.parametrize(
    "atualizacao",
    [
        'estado_conversa = \'{"fase": "E2"}\'::jsonb',
        "motivo_desfecho = 'reescrito'",
        "contexto_codigos = ARRAY['reescrito']",
        "repasse_modo = 'fila'",
        "repasse_consultor_ref = 'perfil-01'",
    ],
)
def test_r4_encerrado_nao_reescreve_estado_conversa_nem_motivos(db_conn, relogio, versoes, atualizacao):
    import psycopg

    atd, v = _aberto(db_conn, relogio, versoes)
    encerrar(db_conn, atd, v, desfecho="sem_venda", motivo="fim", relogio=relogio)
    with pytest.raises(psycopg.errors.CheckViolation) as erro:
        db_conn.execute(f"UPDATE ia.atendimento SET {atualizacao} WHERE atendimento_id = %s", (atd,))
    assert erro.value.diag.constraint_name == "atendimento_terminal_absorvente"


@pytest.mark.banco
def test_r4_o_que_o_job_noturno_grava_depois_do_fim_continua_livre(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    encerrar(db_conn, atd, v, desfecho="sem_venda", motivo="fim", relogio=relogio)
    db_conn.execute(
        "UPDATE ia.atendimento SET contrato_id = 7, pii_auditoria = false, sinais_cliente = ARRAY['x'], ultimo_cliente_em = %s WHERE atendimento_id = %s",
        (relogio(), atd),
    )


# --- R5: EstadoConversa forjado ------------------------------------------------------------------------------------------------------


def test_r5_estado_conversa_forjado_por_model_construct_e_revalidado():
    forjado = EstadoConversa.model_construct(fase="E1", flags={FONE: True})
    with pytest.raises(ValidationError):
        Mudancas(estado_conversa=forjado)


# --- R6: cada camada do A1 sozinha ---------------------------------------------------------------------------------------------------


def test_r6_aplicar_tem_por_padrao_so_os_estados_nao_terminais():
    assert inspect.signature(aplicar).parameters["de"].default == ESTADOS_NAO_TERMINAIS
    assert "encerrado" not in ESTADOS_NAO_TERMINAIS


@pytest.mark.banco
def test_r6_a1_camada_python_sozinha_com_o_trigger_desligado(banco, db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    v = encerrar(db_conn, atd, v, desfecho="sem_venda", motivo="fim", relogio=relogio)
    with banco.sessao() as dono:
        dono.execute("ALTER TABLE ia.atendimento DISABLE TRIGGER atendimento_terminal_absorvente")
    ressuscitar = Mudancas(estado="aberto", desfecho=None, encerrado_em=None, lease_ate=relogio() + timedelta(minutes=5))
    with pytest.raises(TransicaoInvalida) as erro:
        aplicar(db_conn, atd, v, ressuscitar, agora=relogio(), fase="E1")
    assert erro.value.restricao is None  # barrou o WHERE (`de`), não o banco
    assert ler(db_conn, atd).estado == "encerrado"


@pytest.mark.banco
def test_r6_a1_camada_do_trigger_sozinha_com_de_aberto_a_todos(db_conn, relogio, versoes):
    atd, v = _aberto(db_conn, relogio, versoes)
    v = encerrar(db_conn, atd, v, desfecho="sem_venda", motivo="fim", relogio=relogio)
    ressuscitar = Mudancas(estado="aberto", desfecho=None, encerrado_em=None, lease_ate=relogio() + timedelta(minutes=5))
    todos = ESTADOS_NAO_TERMINAIS | {"encerrado"}
    with pytest.raises(TransicaoInvalida) as erro:
        aplicar(db_conn, atd, v, ressuscitar, agora=relogio(), de=todos, fase="E1")
    assert erro.value.restricao == "atendimento_terminal_absorvente"
    assert ler(db_conn, atd).estado == "encerrado"


# --- R8 ------------------------------------------------------------------------------------------------------------------------------


def test_r8_janela_24h_com_datetime_sem_fuso_levanta_value_error():
    agora = datetime(2026, 11, 24, 13, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="fuso"):
        janela_24h_aberta(datetime(2026, 11, 24, 12, 0), agora)
    with pytest.raises(ValueError, match="fuso"):
        janela_24h_aberta(agora, datetime(2026, 11, 24, 13, 0))
