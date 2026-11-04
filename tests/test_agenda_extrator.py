"""B5.7a: extrator determinístico de horário (EM1). Módulo puro: sem banco, sem rede, relógio injetado."""

from __future__ import annotations

import ast
import dataclasses
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from ia_atendimento import agenda_extrator
from ia_atendimento.agenda_extrator import VERSAO, ConfigAgenda, extrair
from ia_atendimento.mascara import mascarar

BRT = ZoneInfo("America/Sao_Paulo")
CORPUS = Path(__file__).parent / "corpus" / "agenda_frases.jsonl"
CONFIANCA_ORDEM = {"baixa": 0, "media": 1, "alta": 2}
QUI10 = datetime(2026, 11, 5, 10, 0, tzinfo=BRT)  # quinta; o teto padrão é sexta 09:00


def _carregar() -> list[dict]:
    return [json.loads(linha) for linha in CORPUS.read_text(encoding="utf-8").splitlines() if linha.strip()]


FRASES = _carregar()
DEV = [f for f in FRASES if not f["holdout"]]
HOLDOUT = [f for f in FRASES if f["holdout"]]


def _rodar(caso: dict, *, como_a_conversa_guarda: bool = False):
    """`como_a_conversa_guarda`: o extrator recebe o texto de `mascarar` (o que `gravar_troca` guarda e `ler_trocas` devolve), a entrada REAL dele."""
    agora = datetime.fromisoformat(caso["agora"])
    ultima = datetime.fromisoformat(caso["ultima_msg"]) if caso["ultima_msg"] else agora
    texto = mascarar(caso["texto"]) if como_a_conversa_guarda else caso["texto"]
    return extrair(texto, agora, ultima, ConfigAgenda(usa_periodos=caso["usa_periodos"]))


def _confere(caso: dict, *, como_a_conversa_guarda: bool = False) -> bool:
    r = _rodar(caso, como_a_conversa_guarda=como_a_conversa_guarda)
    return (
        [c.quando for c in r.candidatos] == [datetime.fromisoformat(e) for e in caso["esperado"]]
        and [c.confianca for c in r.candidatos] == caso["confianca"]
        and r.motivo_recusa == caso["motivo"]
    )


def _ex(texto: str, agora: datetime = QUI10, ultima: datetime | None = None, **cfg):
    return extrair(texto, agora, ultima or agora, ConfigAgenda(**cfg))


# ------------------------------------------------------------------ o corpus
def test_corpus_tem_o_tamanho_pedido():
    assert len(FRASES) >= 150
    assert len(HOLDOUT) >= 30
    assert len({f["id"] for f in FRASES}) == len(FRASES)
    assert len({(f["texto"], f["agora"], f["ultima_msg"], f["usa_periodos"]) for f in FRASES}) == len(FRASES)


def test_corpus_cobre_os_casos_exigidos():
    tags = {f["tag"] for f in FRASES}
    for exigida in ("utc", "sabado", "domingo", "feriado", "dataprev", "relativo", "ambiguo", "sem_hora", "ruido", "hora_passada", "teto"):
        assert exigida in tags, exigida
    assert any(f["agora"].endswith("+00:00") for f in FRASES)  # 22:30 UTC
    assert any("amanhã" in f["texto"].lower() and f["agora"].startswith("2026-11-06") for f in FRASES)  # "amanhã" numa sexta
    assert any("daqui a 1 hora" in f["texto"] for f in FRASES)
    assert any("umas 3" in f["texto"] for f in FRASES) and any("3 e meia" in f["texto"] for f in FRASES)


@pytest.mark.parametrize("caso", DEV, ids=[f["id"] for f in DEV])
def test_corpus_de_desenvolvimento_acerta_tudo(caso):
    r = _rodar(caso)
    assert [c.quando.isoformat() for c in r.candidatos] == [
        datetime.fromisoformat(e).astimezone(BRT).isoformat() for e in caso["esperado"]
    ], caso["texto"]
    assert [c.confianca for c in r.candidatos] == caso["confianca"], caso["texto"]
    assert r.motivo_recusa == caso["motivo"], caso["texto"]


def test_holdout_acerto_minimo_de_95_por_cento(capsys):
    erros = [f for f in HOLDOUT if not _confere(f)]
    taxa = 1 - len(erros) / len(HOLDOUT)
    with capsys.disabled():
        print(f"\n[hold-out] {len(HOLDOUT) - len(erros)}/{len(HOLDOUT)} = {taxa:.1%}")
    assert taxa >= 0.95, [(f["id"], f["texto"]) for f in erros]


def test_holdout_sobre_a_entrada_real_do_extrator_o_texto_de_mascarar(capsys):
    """R2-07: o extrator lê o texto que a conversa guarda (`mascarar`), nunca o do prompt (`proteger_texto`). Hold-out 130/130 sobre essa entrada."""
    erros = [f for f in HOLDOUT if not _confere(f, como_a_conversa_guarda=True)]
    with capsys.disabled():
        print(f"\n[hold-out sobre mascarar] {len(HOLDOUT) - len(erros)}/{len(HOLDOUT)}")
    assert erros == [] and len(HOLDOUT) >= 130, [(f["id"], f["texto"], mascarar(f["texto"])) for f in erros]


def test_corpus_inteiro_sobre_o_texto_de_mascarar_nao_perde_nenhum_caso():
    """`06/11 15:30` virava `[NUMERO]` (8 dígitos) na máscara da B1.2; a isenção de data+hora do agendamento fecha os 390."""
    erros = [f["id"] for f in FRASES if not _confere(f, como_a_conversa_guarda=True)]
    assert erros == []


@pytest.mark.parametrize(
    "texto", ["06/11 15:30", "dia 12/11 15:30", "quinta 06/11 15:30", "05/11 10:00 ou 11:00", "segunda 23/11 05:30", "dia 12/11, 9h30"]
)
def test_data_com_hora_do_agendamento_nao_vira_numero_na_mascara_de_pii(texto):
    assert mascarar(texto) == texto


@pytest.mark.parametrize(
    "documento", ["000.000.012-34", "00000001234", "(11) 91234-5678", "11912345678", "01310-100", "cep 01310100", "12345678"]
)
def test_documento_e_telefone_continuam_mascarados_depois_da_isencao_de_data_com_hora(documento):
    assert mascarar(documento) != documento and mascarar(f"dia 06/11 15:30 e {documento}") != f"dia 06/11 15:30 e {documento}"


def test_o_extrator_nao_conhece_a_protecao_do_prompt():
    """O extrator (e o número do pedido) leem `mascarar`; `proteger_texto` é só para o prompt (122/130 = 93,8% se fosse a entrada)."""
    fonte = Path(agenda_extrator.__file__).read_text(encoding="utf-8")
    assert "protecao" not in fonte and "proteger_texto" not in fonte


# ------------------------------------------------------------------ EM1: zero data inventada
def _todas_as_entradas() -> list[tuple[str, datetime, datetime, bool]]:
    saida = []
    for f in FRASES:
        agora = datetime.fromisoformat(f["agora"])
        ultima = datetime.fromisoformat(f["ultima_msg"]) if f["ultima_msg"] else agora
        saida.append((f["texto"], agora, ultima, f["usa_periodos"]))
    return saida


def test_em1_todo_quando_tem_origem_que_aparece_no_texto():
    com_candidato = 0
    for texto, agora, ultima, periodos in _todas_as_entradas():
        for c in extrair(texto, agora, ultima, ConfigAgenda(usa_periodos=periodos)).candidatos:
            com_candidato += 1
            assert c.origem and c.origem in texto, (texto, c.origem)
            assert c.quando.tzinfo is not None and c.quando.utcoffset() == timedelta(hours=-3)
    assert com_candidato > 100


def test_em1_sem_hora_nao_ha_candidato_nem_data_inventada():
    for texto in ("depois", "mais tarde", "semana que vem", "amanhã", "segunda", "dia 5", "daqui a pouco", "boa tarde", ""):
        r = _ex(texto)
        assert r.candidatos == () and r.motivo_recusa == "sem_hora_explicita", texto


def test_em1_ambiguo_nunca_vira_alta():
    ambiguos = 0
    for texto, agora, ultima, periodos in _todas_as_entradas():
        r = extrair(texto, agora, ultima, ConfigAgenda(usa_periodos=periodos))
        if len(r.candidatos) >= 2:
            ambiguos += 1
            assert all(c.confianca != "alta" for c in r.candidatos), texto
    assert ambiguos >= 10
    for texto in ("15 ou 16", "às 15h ou 16h", "3 ou 4 da tarde", "hoje ou amanhã às 15"):
        assert {c.confianca for c in _ex(texto).candidatos} <= {"media", "baixa"}, texto


def test_periodos_nunca_viram_alta():
    for texto in ("amanhã de tarde", "depois do almoço", "de manhã", "à noite", "fim da tarde", "amanhã cedo", "hoje à noite"):
        r = _ex(texto, usa_periodos=True)
        assert r.candidatos and all(c.confianca in ("media", "baixa") for c in r.candidatos), texto


def test_periodo_so_vale_com_a_chave_na_config_e_a_v1_nao_o_usa_por_padrao():
    assert _ex("depois do almoço").motivo_recusa == "sem_hora_explicita"
    sem_almoco = {k: v for k, v in ConfigAgenda().periodos.items() if k != "depois_do_almoco"}
    r = _ex("depois do almoço", usa_periodos=True, periodos=sem_almoco)
    assert r.candidatos == () and r.motivo_recusa == "sem_hora_explicita"


# ------------------------------------------------------------------ janela, antecedência, teto
@pytest.mark.parametrize(
    ("texto", "agora", "motivo"),
    [
        ("hoje às 19:01", QUI10, "depois_da_janela"),
        ("hoje às 8", QUI10, "passado"),
        ("amanhã às 8", QUI10, "antes_da_janela"),
        ("hoje às 10:05", QUI10, "antecedencia"),
        ("hoje às 9", QUI10, "passado"),
        ("sábado às 12:30", datetime(2026, 11, 6, 8, 0, tzinfo=BRT), "depois_da_janela"),
        ("domingo às 10", datetime(2026, 11, 6, 8, 0, tzinfo=BRT), "domingo"),
    ],
)
def test_candidato_fora_da_janela_e_marcado_nao_descartado(texto, agora, motivo):
    r = _ex(texto, agora)
    assert len(r.candidatos) == 1
    assert r.candidatos[0].fora_da_janela is True
    assert motivo in r.candidatos[0].razoes
    assert r.motivo_recusa is not None


def test_limites_da_janela_sao_inclusivos_e_antecedencia_de_10_minutos():
    assert _ex("hoje às 10:10").motivo_recusa is None  # exatamente 10 min
    assert _ex("hoje às 10:09").motivo_recusa == "antecedencia"
    assert _ex("hoje às 19h").candidatos[0].fora_da_janela is False
    cedo = datetime(2026, 11, 5, 9, 30, tzinfo=BRT)  # teto = sexta 08:30
    assert _ex("amanhã às 8:30", cedo).candidatos[0].razoes == ()
    assert _ex("amanhã às 8:31", cedo).candidatos[0].razoes == ("acima_do_teto",)


def test_sabado_ate_meio_dia_e_flag_na_config():
    sabado = datetime(2026, 11, 7, 8, 0, tzinfo=BRT)
    assert _ex("hoje às 12", sabado).motivo_recusa is None
    assert _ex("hoje às 14", sabado).motivo_recusa == "depois_da_janela"
    assert _ex("hoje às 14", sabado, sabado_fim=None).motivo_recusa is None  # sem corte de sábado


def test_teto_e_o_menor_entre_23h_da_ultima_msg_e_proximo_dia_util_19h():
    ultima = datetime(2026, 11, 5, 9, 0, tzinfo=BRT)
    agora = datetime(2026, 11, 5, 14, 0, tzinfo=BRT)
    assert _ex("amanhã às 8", agora, ultima).motivo_recusa == "antes_da_janela"
    ok = _ex("amanhã às 8:30", agora, ultima)  # teto = sexta 08:00 (09:00 + 23 h): 08:30 passa
    assert ok.candidatos[0].razoes == ("acima_do_teto",)
    assert _ex("amanhã às 07:59", agora, ultima).candidatos[0].razoes == ("antes_da_janela",)
    # o próximo dia útil 19:00 vence quando 23 h depois da última msg passa dele (quinta 23:30 + 23 h = sexta 22:30)
    noite = datetime(2026, 11, 5, 23, 30, tzinfo=BRT)
    alargada = {"janela_fim": "20:00"}  # janela mais larga que o teto: só o teto segura
    assert _ex("amanhã às 19h", noite, **alargada).motivo_recusa is None
    assert _ex("amanhã às 19:30", noite, **alargada).candidatos[0].razoes == ("acima_do_teto",)


def test_teto_horas_vem_da_config():
    r = _ex("hoje às 14", teto_horas=2)  # teto 12:00
    assert r.candidatos[0].razoes == ("acima_do_teto",)
    assert _ex("hoje às 12", teto_horas=2).motivo_recusa is None
    assert _ex("hoje às 12:01", teto_horas=2).motivo_recusa == "acima_do_teto"


def test_proximo_dia_util_pula_domingo_e_feriado():
    # sexta 30/10 16:00 com teto de 100 h: o único limite é o próximo dia útil (sábado) 19:00
    sexta = datetime(2026, 10, 30, 16, 0, tzinfo=BRT)
    r = _ex("sábado às 11", sexta, teto_horas=100)
    assert r.motivo_recusa is None
    # sábado 31/10: próximo dia útil é terça 03/11 (domingo e feriado de 02/11 pulados)
    sabado = datetime(2026, 10, 31, 8, 0, tzinfo=BRT)
    assert _ex("terça às 19h", sabado, teto_horas=100).motivo_recusa is None
    assert _ex("quarta às 9", sabado, teto_horas=100).motivo_recusa == "acima_do_teto"


def test_domingo_fechado_por_padrao_e_aberto_pela_config():
    """D-18 (B1.8): «domingo» só é razão com o domingo fechado (o padrão); aberto, o domingo segue a janela 08:30–19:00 dos outros dias."""
    sabado = datetime(2026, 11, 7, 10, 0, tzinfo=BRT)  # teto = domingo 09:00 (+23 h)
    assert ConfigAgenda().domingo_aberto is False
    fechado = _ex("domingo às 9", sabado)
    assert fechado.candidatos[0].razoes == ("domingo",) and fechado.motivo_recusa == "domingo"
    aberto = _ex("domingo às 9", sabado, domingo_aberto=True)
    assert aberto.candidatos[0].razoes == () and aberto.motivo_recusa is None
    assert aberto.candidatos[0].quando == datetime(2026, 11, 8, 9, 0, tzinfo=BRT)
    assert _ex("domingo às 8", sabado, domingo_aberto=True, teto_horas=100).motivo_recusa == "antes_da_janela"
    assert _ex("domingo às 19:30", sabado, domingo_aberto=True, teto_horas=100).motivo_recusa == "depois_da_janela"
    # aberto não fura DATAPREV nem feriado: 22/11 é domingo dentro da janela da DATAPREV
    agora = datetime(2026, 11, 20, 10, 0, tzinfo=BRT)
    assert _ex("domingo 22/11 às 10", agora, domingo_aberto=True, teto_horas=100).motivo_recusa == "bloqueio_dataprev"


def test_proximo_dia_util_do_teto_inclui_o_domingo_aberto():
    sabado = datetime(2026, 11, 7, 16, 0, tzinfo=BRT)  # teto de 100 h: só o «próximo dia útil 19:00» limita
    assert _ex("segunda às 9", sabado, teto_horas=100).motivo_recusa is None  # fechado: segunda 19:00
    assert _ex("segunda às 9", sabado, teto_horas=100, domingo_aberto=True).motivo_recusa == "acima_do_teto"  # aberto: domingo 19:00
    assert _ex("domingo às 19h", sabado, teto_horas=100, domingo_aberto=True).motivo_recusa is None


# ------------------------------------------------------------------ feriados e DATAPREV
@pytest.mark.parametrize(
    ("texto", "motivo"),
    [
        ("dia 2 às 10", "feriado"),
        ("02/11 às 14h", "feriado"),
        ("20/11 às 9h", "feriado"),
        ("21/11 às 10", "bloqueio_dataprev"),
        ("domingo 22/11 às 10", "bloqueio_dataprev"),
        ("segunda 23/11 05:30", "bloqueio_dataprev"),
    ],
)
def test_feriado_e_bloqueio_dataprev_recusam_com_motivo(texto, motivo):
    agora = datetime(2026, 10, 30, 15, 0, tzinfo=BRT)
    r = extrair(texto, agora, agora, ConfigAgenda(teto_horas=23))
    assert r.motivo_recusa == motivo and r.candidatos and all(c.fora_da_janela for c in r.candidatos)


def test_bloqueio_dataprev_termina_as_6h_de_23_11():
    agora = datetime(2026, 11, 18, 10, 0, tzinfo=BRT)
    r = extrair("23/11 06:00", agora, agora, ConfigAgenda(teto_horas=23))
    assert "bloqueio_dataprev" not in r.candidatos[0].razoes  # 06:00 já não é bloqueio (só falha por antes da janela/teto)
    r2 = extrair("23/11 05:59", agora, agora, ConfigAgenda(teto_horas=23))
    assert "bloqueio_dataprev" in r2.candidatos[0].razoes


def test_feriados_e_bloqueios_vem_da_config():
    sem_feriado = _ex("dia 20 às 10", feriados=frozenset(), bloqueios=())
    assert "feriado" not in sem_feriado.candidatos[0].razoes


# ------------------------------------------------------------------ fuso, entrada e forma do resultado
def test_virada_de_dia_em_utc_usa_o_dia_de_brasilia():
    agora_utc = datetime(2026, 11, 6, 2, 30, tzinfo=UTC)  # ainda é quinta 23:30 em Brasília
    r = extrair("amanhã às 10", agora_utc, agora_utc, ConfigAgenda())
    assert r.candidatos[0].quando == datetime(2026, 11, 6, 10, 0, tzinfo=BRT)
    assert r.motivo_recusa is None
    r2 = extrair("sexta às 10", agora_utc, agora_utc, ConfigAgenda())
    assert r2.candidatos[0].quando == datetime(2026, 11, 6, 10, 0, tzinfo=BRT)


def test_datetime_ingenuo_e_recusado():
    ingenuo = datetime(2026, 11, 5, 10, 0)
    with pytest.raises(ValueError, match="fuso"):
        extrair("15h", ingenuo, QUI10, ConfigAgenda())
    with pytest.raises(ValueError, match="fuso"):
        extrair("15h", QUI10, ingenuo, ConfigAgenda())


def test_texto_longo_e_recusado_sem_varrer():
    r = _ex("às 15h " + "a" * 2000)
    assert r.candidatos == () and r.motivo_recusa == "texto_longo"


def test_resultado_e_candidato_sao_imutaveis_e_versionados():
    r = _ex("às 15h")
    assert VERSAO == "1" and r.versao == "1"
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.motivo_recusa = "x"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.candidatos[0].confianca = "baixa"  # type: ignore[misc]
    assert isinstance(r.candidatos, tuple)


def test_idempotencia_mesma_entrada_mesma_saida():
    for texto, agora, ultima, periodos in _todas_as_entradas():
        cfg = ConfigAgenda(usa_periodos=periodos)
        assert extrair(texto, agora, ultima, cfg) == extrair(texto, agora, ultima, cfg), texto


def test_config_a_partir_das_chaves_do_banco():
    cfg = ConfigAgenda.das_chaves(
        agenda_janela={"inicio": "09:00", "fim": "18:00", "sabado_fim": "11:00"},
        agenda_periodos={"manha": "10:00", "tarde": "15:00"},
        agenda_teto_horas=20,
    )
    assert (cfg.janela_inicio, cfg.janela_fim, cfg.sabado_fim, cfg.teto_horas) == ("09:00", "18:00", "11:00", 20)
    assert dict(cfg.periodos) == {"manha": "10:00", "tarde": "15:00"}
    with pytest.raises(ValueError, match="agenda_teto_horas"):
        ConfigAgenda.das_chaves(agenda_teto_horas=24)
    with pytest.raises(ValueError, match="agenda_periodos"):
        ConfigAgenda.das_chaves(agenda_periodos={"manha": "25:00"})


def test_modulo_e_puro_so_biblioteca_padrao():
    arvore = ast.parse(Path(agenda_extrator.__file__).read_text(encoding="utf-8"))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados |= {a.name.split(".")[0] for a in no.names}
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])
    permitidos = {
        "__future__",
        "dataclasses",
        "datetime",
        "re",
        "unicodedata",
        "zoneinfo",
        "typing",
        "collections",
        "itertools",
        "math",
        "types",
    }
    assert importados <= permitidos, importados - permitidos


# ------------------------------------------------------------------ propriedades (sem hypothesis nas dependências: aleatório com semente)
PALAVRAS_DE_RUIDO = [
    "oi",
    "ok",
    "blz",
    "beleza",
    "depois",
    "mais tarde",
    "amanhã",
    "hoje",
    "segunda",
    "sexta",
    "de manhã",
    "à tarde",
    "à noite",
    "cedo",
    "tudo bem",
    "valeu",
    "kkk",
    "😀",
    "👍",
    "?",
    "!!",
    "...",
    "pode ser",
    "não",
    "sim",
    "quando",
    "semana que vem",
    "mês que vem",
    "daqui a pouco",
    "agora",
    "boa tarde",
    "boa noite",
    "bom dia",
    "obrigado",
    "tenho parcelas",
    "quero o dinheiro",
    "me chama",
    "fala",
    "dia",
    "hora",
    "horário",
    "tarde",
    "manhã",
    "noite",
    "almoço",
    "fim da tarde",
    "outro dia",
    "qualquer hora",
]  # sem dígito, sem número por extenso, sem «meio-dia»: nenhuma hora explícita


@pytest.mark.parametrize("usa_periodos", [False, True])
def test_ruido_sem_hora_explicita_nunca_produz_candidato_alta(usa_periodos):
    rng = random.Random(20261105)
    for _ in range(200):
        texto = " ".join(rng.choice(PALAVRAS_DE_RUIDO) for _ in range(rng.randint(1, 8)))
        r = _ex(texto, usa_periodos=usa_periodos)
        assert all(c.confianca != "alta" for c in r.candidatos), texto
        if not usa_periodos:
            assert r.candidatos == (), texto
            assert r.motivo_recusa == "sem_hora_explicita", texto


def test_propriedades_em_entradas_aleatorias_com_hora():
    rng = random.Random(7)
    extras = ["às 15h", "16:30", "3 da tarde", "15 ou 16", "meio-dia", "dia 9", "05/11", "daqui a 1 hora", "umas 3", "sábado"]
    pedacos = [*PALAVRAS_DE_RUIDO, *extras]
    agoras = [
        QUI10,
        datetime(2026, 11, 7, 9, 30, tzinfo=BRT),
        datetime(2026, 11, 8, 10, 0, tzinfo=BRT),
        datetime(2026, 11, 20, 8, 0, tzinfo=BRT),
    ]
    for _ in range(300):
        texto = " ".join(rng.choice(pedacos) for _ in range(rng.randint(1, 6)))
        agora = rng.choice(agoras)
        r = _ex(texto, agora)
        assert r == _ex(texto, agora)
        assert len(r.candidatos) <= 3
        assert (r.motivo_recusa is None) == any(not c.fora_da_janela for c in r.candidatos)
        if len(r.candidatos) >= 2:
            assert all(c.confianca != "alta" for c in r.candidatos), texto
        for c in r.candidatos:
            assert c.origem in texto and c.quando.tzinfo is not None


# ------------------------------------------------------------------ revisão adversarial 1 (docs/REVISAO-B5.7a-3010.md)
def _horas(r) -> list[str]:
    return [c.quando.strftime("%d/%m %H:%M") for c in r.candidatos]


def test_r1_data_explicita_invalida_nao_vira_hoje():
    for texto in ("31/11 às 15h", "29/02/2027 às 15h", "30/02 às 15h", "dia 31 de abril às 10"):
        r = _ex(texto)
        assert r.candidatos == () and r.motivo_recusa == "data_invalida", texto


@pytest.mark.parametrize(
    "texto",
    ["hoje às 19:01:00", "às 15:99", "às 15 e trinta e cinco", "às dozentas parcelas", "às 15:30:45", "15.30", "às 15,30"],
)
def test_r2_reconhecimento_parcial_nao_apaga_minutos_nem_atravessa_fronteira(texto):
    assert _ex(texto).candidatos == (), texto


def test_r2_construcoes_compostas_mantem_os_minutos():
    assert _horas(_ex("às 15h e meia")) == ["05/11 15:30"]
    assert _horas(_ex("daqui a uma hora e quinze minutos")) == ["05/11 11:15"]
    assert _horas(_ex("daqui a 2 horas e meia")) == ["05/11 12:30"]


def test_r3_alternativa_preserva_os_minutos_de_cada_lado():
    assert _horas(_ex("às 15h ou 16:30")) == ["05/11 15:00", "05/11 16:30"]
    assert _horas(_ex("15:30 ou 16h45")) == ["05/11 15:30", "05/11 16:45"]
    assert _horas(_ex("entre 14h30 e 15h")) == ["05/11 14:30", "05/11 15:00"]
    assert _ex("às 15h ou 16:99").candidatos == ()  # lado inválido: recusa tudo, não oferece só o outro


def test_r4_aproximacao_nao_vira_alta_com_periodo():
    for texto in ("umas 3 da tarde", "umas 10 da manhã", "depois das 3 da tarde", "umas 7 da noite"):
        assert all(c.confianca != "alta" for c in _ex(texto).candidatos), texto


def test_r5_hora_relativa_respeita_o_dia_explicito():
    r = _ex("hoje ou amanhã daqui a 1 hora")
    assert r.candidatos and all(c.confianca != "alta" for c in r.candidatos)
    for texto in ("amanhã daqui a 1 hora", "sexta daqui a 2 horas"):
        r = _ex(texto)
        assert r.candidatos == () and r.motivo_recusa == "dia_contraditorio", texto
    assert _horas(_ex("hoje daqui a 1 hora")) == ["05/11 11:00"]
    assert _ex("hoje daqui a 1 hora").candidatos[0].confianca == "alta"


def test_r6_segundos_de_agora_contam_na_antecedencia_e_no_arredondamento():
    agora = QUI10.replace(second=59)
    assert "antecedencia" in _ex("hoje às 10:10", agora).candidatos[0].razoes  # 541 s < 600 s
    assert _ex("hoje às 10:11", agora).motivo_recusa is None
    assert _horas(_ex("daqui a 1 hora", agora)) == ["05/11 11:05"]
    assert _horas(_ex("daqui a 1 hora")) == ["05/11 11:00"]  # sem segundos, a grade não muda


@pytest.mark.parametrize(
    "texto",
    ["tenho entre 15 e 16 parcelas", "12 parcelas", "R$ 15", "2 contratos", "entre 12 e 24 meses", "as 2 contratos", "umas 12 parcelas",
     "quero 15 ou 20 mil", "pagar em 12x", "são 3 propostas", "as 5 pessoas", "R$ 15 por mês", "entre 2 e 3 contratos"],
)  # fmt: skip
def test_r7_quantidade_nunca_vira_hora(texto):
    r = _ex(texto)
    assert r.candidatos == () and r.motivo_recusa == "sem_hora_explicita", texto


def test_r8_ano_bissexto_ao_avancar_o_ano_nao_lanca():
    r = _ex("29/02 às 15h", datetime(2028, 12, 5, 10, tzinfo=BRT))
    assert r.candidatos == () and r.motivo_recusa == "data_invalida"
    assert isinstance(_ex("29/02 às 15h", datetime(2027, 12, 5, 10, tzinfo=BRT)), agenda_extrator.Resultado)


def test_r9_meio_dia_e_media():
    for texto in ("meio-dia", "meio dia e meia", "meia-noite"):
        assert _ex(texto).candidatos[0].confianca == "media", texto


def test_r10_meia_noite_e_meia_usa_os_minutos():
    c = _ex("meia-noite e meia").candidatos[0]
    assert c.quando == datetime(2026, 11, 6, 0, 30, tzinfo=BRT)


def test_r11_holdout_nao_reutiliza_caso_que_ensinou_correcao():
    assert not [f for f in HOLDOUT if f["tag"] == "regressao"]
    textos_regressao = {f["texto"] for f in FRASES if f["tag"] == "regressao"}
    assert not [f for f in HOLDOUT if f["texto"] in textos_regressao]
    assert len(HOLDOUT) >= 90  # 52 da rodada 1 + 43 novos congelados antes da revisão


# ------------------------------------------------------------------ revisão adversarial 2 (docs/REVISAO-B5.7a-3010-r2.md)
def _sem_alta(texto: str) -> bool:
    return all(c.confianca != "alta" for c in _ex(texto).candidatos)


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("às 15h e 16h", ["15:00", "16:00"]),
        ("15h e 16h30", ["15:00", "16:30"]),
        ("15:30 e 16h", ["15:30", "16:00"]),
        ("às 15 e 16:30", ["15:00", "16:30"]),
        ("às 15 e 4 da tarde", ["15:00", "16:00"]),
        ("às três ou 16:30", ["15:00", "16:30"]),
        ("às 3 e meia ou 16:30", ["15:30", "16:30"]),
        ("às 3 e meia ou 4 e meia", ["15:30", "16:30"]),
        ("15h ou meio-dia", ["12:00", "15:00"]),
        ("14h ou depois das 16", ["14:00", "16:15"]),
        ("14h ou umas três", ["14:00", "15:00"]),
        ("15h ou quatro da tarde", ["15:00", "16:00"]),
        ("15h ou meio dia e meia", ["12:30", "15:00"]),
        ("10h ou meio-dia e meia", None),  # 10h de hoje já passou: só confere que não sobra alta
        ("às 14h ou 15 e meia", ["14:00", "15:30"]),
        ("15h ou 16h30min", ["15:00", "16:30"]),
    ],
)
def test_n1_n2_n5_lista_ou_alternativa_nunca_deixa_so_uma_metade(texto, esperado):
    r = _ex(texto)
    assert r.candidatos and _sem_alta(texto), texto
    if esperado is not None:
        assert sorted(c.quando.strftime("%H:%M") for c in r.candidatos) == esperado, texto


@pytest.mark.parametrize(
    "texto", ["às 15h ou 16:99", "16:99 ou 15h", "às 15 e trinta e cinco", "às 10 e 15 parcelas", "15h e 16:99", "15h ou 20:75 ou 16h"]
)
def test_n1_n2_metade_recusada_recusa_a_frase_inteira(texto):
    r = _ex(texto)
    assert r.candidatos == () and r.motivo_recusa == "hora_incompleta", texto


@pytest.mark.parametrize(
    "texto",
    [
        "das 14 às 16h",
        "de 14 às 16",
        "15h até 16h",
        "10 às 12",
        "das 10 às 12",
        "15 às 16h30",
        "às 15 a 16",
        "de 14h a 16h",
        "das 9h às 11h30",
    ],
)
def test_n3_faixa_nao_e_hora_unica(texto):
    r = _ex(texto)
    assert r.candidatos == () and r.motivo_recusa == "intervalo", texto


def test_n3_faixa_nao_confunde_quantidade_nem_data():
    assert _ex("de 12 a 24 parcelas").motivo_recusa == "sem_hora_explicita"
    assert _ex("dia 5 a 7").candidatos == ()
    assert _ex("às 15h, até 17h").motivo_recusa != "intervalo"  # «até» sozinho segue sendo limite (R3/R4 antigos)


@pytest.mark.parametrize(
    "texto",
    ["por volta das 15h", "mais ou menos 15h", "15h mais ou menos", "aproximadamente 15h", "perto das 15h", "lá pelas 15h", "pelas 15h", "uns 15h",
     "tipo 15h", "15h por aí", "umas 15:30", "umas às 3 da tarde", "umas as 15", "15h ou mais", "a partir das 15h", "após as 15h", "talvez 15h",
     "acho que 15h", "quem sabe 15h", "15h se der", "cerca de 15h", "quase 15h", "em torno de 15h", "daqui a 1 hora mais ou menos"],
)  # fmt: skip
def test_n4_aproximacao_nunca_e_alta(texto):
    r = _ex(texto)
    assert r.candidatos and _sem_alta(texto), texto


def test_n4_hedge_distante_ou_vizinho_so_rebaixa_nunca_inventa_hora():
    assert _ex("depois de amanhã às 15h").candidatos[0].confianca == "alta"  # «depois de» não é aproximação
    assert _ex("às 15h").candidatos[0].confianca == "alta"
    assert _ex("tipo 15h").candidatos[0].quando.strftime("%H:%M") == "15:00"


@pytest.mark.parametrize(
    "texto", ["trabalho 16 horas por dia", "trabalho 12 horas por dia", "demora 15 horas", "espero há 15 horas", "faz 15h que espero"]
)
def test_n6_duracao_nao_e_horario(texto):
    assert _ex(texto).candidatos == (), texto


@pytest.mark.parametrize("texto", ["daqui a 1 hora ou 2 horas", "daqui a 1 ou 2 horas", "dentro de 1 hora ou 2"])
def test_n6_duracao_alternativa_recusa(texto):
    r = _ex(texto)
    assert r.candidatos == () and r.motivo_recusa == "duracao_ambigua", texto


def test_n7_contradicao_parcial_recusa_ou_rebaixa():
    r = _ex("amanhã às 10 daqui a 1 hora")
    assert r.candidatos == () and r.motivo_recusa == "dia_contraditorio"


def test_n8_nao_recusa_demais():
    assert _horas(_ex("às 15h 06/11")) == ["06/11 15:00"]
    assert _horas(_ex("às 15h 6/11/2026")) == ["06/11 15:00"]
    assert _horas(_ex("às 3 e meia dia 6")) == ["06/11 15:30"]
    assert _horas(_ex("às quatro e meia dia 10 de novembro")) == ["10/11 16:30"]
    assert _horas(_ex("às 15 dia 6")) == ["06/11 15:00"]
    assert _ex("15h 30").candidatos == ()  # continua recusando minutos soltos
