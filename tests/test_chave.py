"""Chave (config versionada) e as recusas de entrada: `max(versao)`, cache de 5 s, registro validado, `bloqueio_entrada` sem encerrar ninguém."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from ia_atendimento.chave import (
    RECUSAS_DE_ENTRADA,
    ConfigCorrida,
    ConfigInexistente,
    LeitorConfig,
    ModoTesteGlobal,
    ValorInvalido,
    bloqueio_entrada,
    config_vigente,
    garantir_defaults,
    gasto_dia,
    gasto_mes,
    registrar_config,
)
from ia_atendimento.chave_registro import PADROES, REGISTRO
from ia_atendimento.relogio import RelogioFalso
from tests import fixtures_fila as ff
from tests.fixtures_fila import estados_dos_atendimentos, hex24, inserir_atendimento, inserir_custo, inserir_opt_out

# fixtures da B1.3 (atribuição, não import: o módulo ganha o nome do fixture sem brigar com o parâmetro do teste nem com o conftest)
conn_app, conn_super, relogio = ff.conn_app, ff.conn_super, ff.relogio

pytestmark = pytest.mark.banco

SEEDS = [
    "ia_ativa",
    "teto_mensal_brl",
    "modo",
    "subteto_dia",
    "max_disparos_dia",
    "max_abertos",
    "verificador_ativo",
    "bancos_digitacao",
    "ia_repasse_dias",
    "faixas_esforco",
    "esforco_por_periodo",
    "janela_vendedores",
    "janela_mensagem",
    "modelo_por_faixa",
    "bloqueio_entrada",
    "chats_teste",
    "agenda_max_dia",
    "agenda_periodos",
    "agenda_ativa",
    "agenda_janela",
    "agenda_teto_horas",
    "agenda_max_por_atendimento",
    "agenda_max_pausados",
    "agenda_folga_min",
    "agenda_b_digita",
    "alcada_valor_max_brl",
    "calendario_bloqueio",
]


def reg(conn, relogio, nome, valor, **kw):
    return registrar_config(conn, nome, valor, "teste", relogio=relogio, **kw)


def ligar(conn, relogio):
    return reg(conn, relogio, "ia_ativa", True)


# --- registro ---------------------------------------------------------------------------------------------------------------------------


def test_config_registro_cobre_as_27_chaves_com_seed_e_as_sem_seed(conn_super):
    assert len(SEEDS) == 27
    do_banco = {r[0]: r[1] for r in conn_super.execute("SELECT nome, valor FROM ia.config_versao WHERE versao = 1")}
    assert set(do_banco) == set(SEEDS)
    assert set(SEEDS) <= set(REGISTRO)
    assert {"verificador_modelo", "lembretes_intervalos_min"} <= set(REGISTRO)
    for nome in SEEDS:
        # o padrão do código é a seed da 0001 (se divergir, um dos dois está errado) e passa na própria validação
        assert PADROES[nome] == do_banco[nome], nome
        assert REGISTRO[nome].validar(PADROES[nome]) == PADROES[nome], nome
    assert PADROES["lembretes_intervalos_min"] == [240, 240]
    assert "verificador_modelo" not in PADROES  # sem seed e sem padrão: ausente = nenhum modelo no verificador


def test_config_recusa_modo_teste_global(conn_app, relogio):
    with pytest.raises(ModoTesteGlobal) as erro:
        reg(conn_app, relogio, "modo", "teste")
    assert erro.value.codigo == "modo_teste_global"
    assert config_vigente(conn_app, "modo").versao == 1  # nada gravado
    assert reg(conn_app, relogio, "modo", "sombra").versao == 2
    for ruim in ("fora", "", 1, None, ["real"]):
        with pytest.raises(ValorInvalido):
            reg(conn_app, relogio, "modo", ruim)


def test_chats_teste_recusa_formato_e_quantidade(conn_app, relogio):
    boa = [hex24(), hex24()]
    assert reg(conn_app, relogio, "chats_teste", boa).valor == boa
    ruins = {
        "vinte_e_um": [hex24() for _ in range(21)],
        "maiuscula": ["A" * 24],
        "curto": ["a" * 23],
        "longo": ["a" * 25],
        "nao_hex": ["g" * 24],
        "repetido": ["a" * 24, "a" * 24],
        "nao_lista": "a" * 24,
        "numero": [1],
    }
    for caso, valor in ruins.items():
        with pytest.raises(ValorInvalido):
            reg(conn_app, relogio, "chats_teste", valor)
        assert caso
    assert len(reg(conn_app, relogio, "chats_teste", [hex24() for _ in range(20)]).valor) == 20
    assert config_vigente(conn_app, "chats_teste").versao == 3


def test_agenda_max_dia_nunca_passa_de_max_disparos_dia(conn_app, relogio):
    with pytest.raises(ValorInvalido, match="agenda_max_dia"):
        reg(conn_app, relogio, "agenda_max_dia", 11)  # max_disparos_dia vigente = 10
    assert reg(conn_app, relogio, "agenda_max_dia", 10).versao == 2
    with pytest.raises(ValorInvalido, match="max_disparos_dia"):
        reg(conn_app, relogio, "max_disparos_dia", 9)  # não pode ficar abaixo de agenda_max_dia (10)
    assert reg(conn_app, relogio, "max_disparos_dia", 15).versao == 2


def test_valores_de_tipo_e_limite_errados_sao_recusados(conn_app, relogio):
    ruins = [
        ("bloqueio_entrada", "true"),
        ("bloqueio_entrada", 1),
        ("ia_ativa", None),
        ("max_abertos", 0),
        ("max_abertos", 201),
        ("max_abertos", 2.5),
        ("max_abertos", True),
        ("teto_mensal_brl", -1),
        ("teto_mensal_brl", "100"),
        ("agenda_teto_horas", 24),
        ("agenda_max_por_atendimento", 3),
        ("bancos_digitacao", ["ITAU"]),
        ("lembretes_intervalos_min", [240, 240, 240]),
        ("lembretes_intervalos_min", [0, 240]),
        ("lembretes_intervalos_min", []),
        ("agenda_periodos", {"cedo": "07:00"}),
        ("agenda_periodos", {"Cedo": "08:30"}),
        ("agenda_janela", {"inicio": "07:00", "fim": "19:00"}),
        ("agenda_janela", {"inicio": "08:30", "fim": "19:00", "sabado_fim": "20:30"}),
        ("janela_mensagem", {"dias": {"7": {"inicio": "07:00", "fim": "12:00"}}}),  # D-18: o dia 7 vale, mas só dentro de 08–20
        ("janela_mensagem", {"dias": {"7": {"inicio": "08:00", "fim": "20:30"}}}),
        ("calendario_bloqueio", {**PADROES["calendario_bloqueio"], "domingos": "false"}),
        ("calendario_bloqueio", {"domingos": True, "feriados": [], "janelas": []}),
        ("modelo_por_faixa", {"baixa": {"modelo": "claude-x", "provedor": "p", "raciocinio": False, "custo_max_brl": 1}}),
        ("faixas_esforco", {"limites_brl": [400, 150, 800], "faixas": {}}),
    ]
    for nome, valor in ruins:
        with pytest.raises(ValorInvalido):
            reg(conn_app, relogio, nome, valor)
    for nome in {n for n, _ in ruins}:
        vigente = config_vigente(conn_app, nome)
        assert vigente is None or vigente.versao == 1, nome  # lembretes_intervalos_min não tem seed


def test_nome_fora_do_registro_e_config_inexistente(conn_app, relogio):
    with pytest.raises(ConfigInexistente):
        reg(conn_app, relogio, "chave_inventada", 1)
    assert config_vigente(conn_app, "chave_inventada") is None
    assert config_vigente(conn_app, "verificador_modelo") is None  # registrada, mas sem seed
    assert reg(conn_app, relogio, "verificador_modelo", "deepseek-v4p1-flash-1017").versao == 1  # o primeiro PUT grava versao=1


# --- versionamento ----------------------------------------------------------------------------------------------------------------------


def test_vigente_e_o_max_versao_e_publicar_incrementa(conn_app, relogio):
    antes = config_vigente(conn_app, "max_abertos")
    assert (antes.versao, antes.valor) == (1, 10)
    novo = reg(conn_app, relogio, "max_abertos", 12, motivo="rampa")
    assert (novo.versao, novo.valor, novo.publicado_por, novo.motivo, novo.publicado_em) == (2, 12, "teste", "rampa", relogio.agora())
    assert config_vigente(conn_app, "max_abertos") == novo
    assert conn_app.execute("SELECT count(*) FROM ia.config_versao WHERE nome = 'max_abertos'").fetchone()[0] == 2  # append-only


def test_publicar_perde_corrida_vira_config_corrida(conn_app, relogio):
    reg(conn_app, relogio, "max_abertos", 11)  # versão 2 já existe
    with pytest.raises(ConfigCorrida) as erro:
        reg(conn_app, relogio, "max_abertos", 12, versao_esperada=1)  # quem leu a 1 perdeu
    assert erro.value.codigo == "config_corrida"
    assert reg(conn_app, relogio, "max_abertos", 13, versao_esperada=2).versao == 3
    assert config_vigente(conn_app, "max_abertos").valor == 13


def test_pk_perdida_sem_versao_esperada_tambem_e_config_corrida(conn_app, conn_super, relogio, monkeypatch):
    """Dois escritores leem a mesma versão e inserem a seguinte: o segundo bate na PK e recebe 409 (não sobrescreve)."""
    import ia_atendimento.chave as chave

    original = chave.config_vigente

    def leitura_atrasada(conn, nome):
        lida = original(conn, nome)
        conn_super.execute(
            "INSERT INTO ia.config_versao (nome, versao, valor, publicado_por) VALUES (%s, %s, '99', 'concorrente')",
            (nome, lida.versao + 1),
        )
        return lida

    monkeypatch.setattr(chave, "config_vigente", leitura_atrasada)
    with pytest.raises(ConfigCorrida):
        reg(conn_app, relogio, "max_abertos", 12)
    monkeypatch.undo()
    assert config_vigente(conn_app, "max_abertos").valor == 99


def test_garantir_defaults_no_boot_so_cria_o_que_falta(conn_app, conn_super, relogio):
    conn_super.execute("DELETE FROM ia.config_versao WHERE nome IN ('chats_teste', 'bloqueio_entrada')")
    reg(conn_app, relogio, "max_abertos", 12)
    criadas = garantir_defaults(conn_app, relogio)
    assert set(criadas) == {"chats_teste", "bloqueio_entrada", "lembretes_intervalos_min"}
    assert config_vigente(conn_app, "chats_teste").valor == []
    assert config_vigente(conn_app, "bloqueio_entrada").valor is False
    assert config_vigente(conn_app, "lembretes_intervalos_min").valor == [240, 240]
    assert config_vigente(conn_app, "max_abertos").versao == 2  # o que existe não é tocado
    assert garantir_defaults(conn_app, relogio) == ()  # idempotente
    assert {r[0] for r in conn_super.execute("SELECT nome FROM ia.config_versao")} >= set(SEEDS)


# --- cache ------------------------------------------------------------------------------------------------------------------------------


def test_cache_de_5_segundos_e_invalidado_pela_propria_escrita(conn_app, conn_super, relogio):
    leitor = LeitorConfig(relogio)
    assert leitor.vigente(conn_app, "max_abertos").valor == 10
    conn_super.execute("INSERT INTO ia.config_versao (nome, versao, valor, publicado_por) VALUES ('max_abertos', 2, '20', 'outro')")
    relogio.avancar(seconds=4.9)
    assert leitor.vigente(conn_app, "max_abertos").valor == 10  # ainda no cache
    relogio.avancar(seconds=0.2)
    assert leitor.vigente(conn_app, "max_abertos").valor == 20  # passou de 5 s
    leitor.registrar(conn_app, "max_abertos", 30, "teste")
    assert leitor.vigente(conn_app, "max_abertos").valor == 30  # a escrita do próprio processo vale na hora


# --- recusas de entrada -----------------------------------------------------------------------------------------------------------------


def recusa(conn, relogio, pessoa=None, leitor=None):
    return bloqueio_entrada(conn, relogio, pessoa, leitor=leitor)


def test_recusas_estao_na_ordem_do_contrato():
    assert RECUSAS_DE_ENTRADA == (
        "ia_desligada",
        "bloqueio_entrada",
        "fora_de_janela",
        "opt_out",
        "teto_atingido",
        "teto_diario",
        "disparos_dia",
        "abertos_max",
    )


def test_cinco_recusas_de_entrada(conn_app, conn_super, relogio):
    # 1. a IA nasce desligada
    assert recusa(conn_app, relogio) == "ia_desligada"
    ligar(conn_app, relogio)
    assert recusa(conn_app, relogio) is None

    # 2. fora_de_janela: 20:30 local, domingo, feriado e janela DATAPREV (todos pelo calendário do código)
    for instante in (
        datetime(2026, 11, 17, 23, 30, tzinfo=UTC),
        datetime(2026, 11, 15, 15, 0, tzinfo=UTC),
        datetime(2026, 11, 2, 15, 0, tzinfo=UTC),
        datetime(2026, 11, 21, 15, 0, tzinfo=UTC),
    ):
        assert recusa(conn_app, RelogioFalso(instante)) == "fora_de_janela", instante
    assert recusa(conn_app, RelogioFalso(datetime(2026, 11, 17, 22, 30, tzinfo=UTC))) is None  # 19:30 local: dentro

    # 3. teto_atingido: Σ passo.custo_brl do mês de TODOS os modos (contrato 08 §9); o mês anterior não conta
    reg(conn_app, relogio, "teto_mensal_brl", 10)
    velho = inserir_atendimento(conn_super, estado="encerrado", iniciado_em=relogio.agora() - timedelta(days=20))  # 28/10
    inserir_custo(conn_super, velho, 50, relogio.agora() - timedelta(days=20))
    sombra = inserir_atendimento(conn_super, estado="encerrado", modo="sombra", iniciado_em=relogio.agora() - timedelta(days=5))
    inserir_custo(conn_super, sombra, 6, relogio.agora() - timedelta(days=5))
    assert recusa(conn_app, relogio) is None
    teste = inserir_atendimento(conn_super, estado="encerrado", modo="teste", iniciado_em=relogio.agora() - timedelta(days=2))
    inserir_custo(conn_super, teste, 4, relogio.agora() - timedelta(days=2))
    assert gasto_mes(conn_app, relogio.agora()) == 10
    assert recusa(conn_app, relogio) == "teto_atingido"
    reg(conn_app, relogio, "teto_mensal_brl", 1000)

    # 4. teto_diario: sub-teto em R$ do dia local (02:30 UTC de hoje ainda é ontem em SP)
    reg(conn_app, relogio, "subteto_dia", 5)
    ontem = inserir_atendimento(conn_super, estado="encerrado", iniciado_em=datetime(2026, 11, 17, 2, 30, tzinfo=UTC))
    inserir_custo(conn_super, ontem, 9, datetime(2026, 11, 17, 2, 30, tzinfo=UTC))
    assert gasto_dia(conn_app, relogio.agora()) == 0
    assert recusa(conn_app, relogio) is None
    hoje = inserir_atendimento(conn_super, estado="encerrado", iniciado_em=relogio.agora() - timedelta(hours=1))
    inserir_custo(conn_super, hoje, 5, relogio.agora() - timedelta(hours=1))
    assert recusa(conn_app, relogio) == "teto_diario"
    reg(conn_app, relogio, "subteto_dia", 1000)

    # 5. abertos_max: lê v_prontidao.abertos (pausado não conta)
    reg(conn_app, relogio, "max_abertos", 2)
    inserir_atendimento(conn_super, estado="pausado")
    inserir_atendimento(conn_super, estado="aberto")
    assert recusa(conn_app, relogio) is None
    inserir_atendimento(conn_super, estado="aguardando_cliente")
    assert recusa(conn_app, relogio) == "abertos_max"


def test_domingo_so_abre_a_entrada_com_as_duas_chaves_publicadas(conn_app, relogio):
    """D-18 (B1.8): com a 0005 no banco, o registro aceita as duas chaves; o domingo abre só com as duas e fecha de novo com uma versão nova."""
    ligar(conn_app, relogio)
    domingo = RelogioFalso(datetime(2026, 11, 29, 15, 0, tzinfo=UTC))  # domingo 29/11, 12:00 SP
    assert recusa(conn_app, domingo) == "fora_de_janela"  # seed: fechado
    com_domingo = {"dias": {**PADROES["janela_mensagem"]["dias"], "7": {"inicio": "09:00", "fim": "18:00"}}}
    reg(conn_app, relogio, "janela_mensagem", com_domingo)
    assert recusa(conn_app, domingo) == "fora_de_janela", "só a janela aberta: domingos=true ainda fecha"
    reg(conn_app, relogio, "calendario_bloqueio", {**PADROES["calendario_bloqueio"], "domingos": False})
    assert recusa(conn_app, domingo) is None, "as duas chaves abertas"
    assert recusa(conn_app, RelogioFalso(datetime(2026, 11, 29, 21, 30, tzinfo=UTC))) == "fora_de_janela"  # 18:30 SP: depois do dia 7
    reg(conn_app, relogio, "janela_mensagem", PADROES["janela_mensagem"])
    assert recusa(conn_app, domingo) == "fora_de_janela", "só o bloqueio aberto: o dia 7 sumiu da janela"
    reg(conn_app, relogio, "calendario_bloqueio", PADROES["calendario_bloqueio"])
    assert recusa(conn_app, domingo) == "fora_de_janela"


def test_opt_out_e_disparos_dia(conn_app, conn_super, relogio):
    ligar(conn_app, relogio)
    pessoa = uuid.uuid4()
    assert recusa(conn_app, relogio, pessoa) is None
    inserir_opt_out(conn_super, pessoa, "opt_out")
    assert recusa(conn_app, relogio, pessoa) == "opt_out"
    assert recusa(conn_app, relogio, uuid.uuid4()) is None  # outra pessoa
    inserir_opt_out(conn_super, pessoa, "consentimento")  # vale a ÚLTIMA linha da pessoa
    assert recusa(conn_app, relogio, pessoa) is None

    reg(conn_app, relogio, "agenda_max_dia", 2)  # nunca acima de max_disparos_dia
    reg(conn_app, relogio, "max_disparos_dia", 2)
    reg(conn_app, relogio, "max_abertos", 50)
    for _ in range(2):
        inserir_atendimento(conn_super, estado="encerrado", iniciado_em=relogio.agora() - timedelta(minutes=30))
    inserir_atendimento(conn_super, estado="encerrado", iniciado_em=relogio.agora() - timedelta(days=1))  # ontem não conta
    assert recusa(conn_app, relogio) == "disparos_dia"


def test_ordem_das_recusas_quando_varias_valem(conn_app, relogio):
    # IA desligada E fora da janela: a primeira da ordem vence
    assert recusa(conn_app, RelogioFalso(datetime(2026, 11, 15, 15, 0, tzinfo=UTC))) == "ia_desligada"
    ligar(conn_app, relogio)
    reg(conn_app, relogio, "bloqueio_entrada", True)
    assert recusa(conn_app, RelogioFalso(datetime(2026, 11, 15, 15, 0, tzinfo=UTC))) == "bloqueio_entrada"


def test_bloqueio_entrada_nao_encerra_abertos_nem_pausados(conn_app, conn_super, relogio):
    ligar(conn_app, relogio)
    ids = [inserir_atendimento(conn_super, estado=e) for e in ("aberto", "aguardando_cliente", "pausado", "reservado", "repassando")]
    antes = estados_dos_atendimentos(conn_super)
    jobs_antes = conn_super.execute("SELECT count(*) FROM procrastinate.procrastinate_jobs").fetchone()[0]
    assert recusa(conn_app, relogio) is None

    reg(conn_app, relogio, "bloqueio_entrada", True)
    assert recusa(conn_app, relogio) == "bloqueio_entrada"  # entrada nova recusada ...
    assert estados_dos_atendimentos(conn_super) == antes  # ... e ninguém foi encerrado, repassado nem teve a versão mexida
    assert all(antes[i][0] != "encerrado" for i in ids)
    assert (
        conn_super.execute("SELECT count(*) FROM procrastinate.procrastinate_jobs").fetchone()[0] == jobs_antes
    )  # nenhum encerrar_por_chave enfileirado

    reg(conn_app, relogio, "bloqueio_entrada", False)
    assert recusa(conn_app, relogio) is None


def test_bloqueio_entrada_vale_mesmo_com_a_ia_ligada_e_o_leitor_com_cache(conn_app, relogio):
    ligar(conn_app, relogio)
    leitor = LeitorConfig(relogio)
    assert recusa(conn_app, relogio, leitor=leitor) is None
    leitor.registrar(conn_app, "bloqueio_entrada", True, "teste")
    assert recusa(conn_app, relogio, leitor=leitor) == "bloqueio_entrada"


def test_config_guardada_como_json(conn_super):
    valor = conn_super.execute("SELECT valor FROM ia.config_versao WHERE nome = 'chats_teste'").fetchone()[0]
    assert json.dumps(valor) == "[]"
    with pytest.raises(psycopg.errors.CheckViolation):  # o CHECK do banco segue valendo por baixo do registro
        conn_super.execute("INSERT INTO ia.config_versao (nome, versao, valor, publicado_por) VALUES ('ia_ativa', 2, '1', 'x')")
