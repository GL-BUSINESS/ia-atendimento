"""Corpus da F3 (roteiro B8.1a): carregador tipado e validador de `tests/corpus/`.

O corpus é INVENTADO: nenhuma conversa real do ChatGuru (proibido até o parecer J5), CPF só `000.000.0nn`, nomes fictícios, valores
redondos. Ele guarda o que a avaliação (B8.1b/B8.2) precisa e NADA do texto da IA: o gabarito de cada turno da IA fixa só a fase, as
ações permitidas/proibidas e os TX que ela pode emitir; o texto do cliente é fixo (com 1–2 variações escolhidas pela semente).

Arquivos (`CORPUS_DIR`): `personas.jsonl` (60 personas P01–P60 de H §7), `personas_m.jsonl` (P-M01–P-M24, M EM2), `dialogos/<id>.jsonl`
(um por persona da F3 curta: uma linha por turno), `semente.json` (ordem, hold-out e sementes por persona) e `duble_personas.json`
(instantâneo de `bancos-duble/personas/personas.yaml`: ids e CPFs; só dado sintético).

Uso: `carregar()` devolve o `Corpus` tipado (Pydantic, `extra='forbid'`, imutável); `validar(carregar_bruto())` devolve a lista de
violações `codigo: mensagem` (vazia = corpus bom). Cada regra é uma função pequena de `REGRAS`; os testes mutam o bruto em memória.
"""

from __future__ import annotations

import hashlib
import json
import re
import statistics
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Sequence
from datetime import UTC, date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, get_args

from pydantic import AwareDatetime, BaseModel, ConfigDict, ValidationError, model_validator

from ia_atendimento import mascara

CORPUS_DIR = Path(__file__).resolve().parents[2] / "tests" / "corpus"

# --- vocabulário fechado (H §2.2/§7, M §2.3/§6, L §2.1) ------------------------------------------------------------------------------

Fase = Literal["E0", "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10"]
Invariante = Literal["I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8", "I9"]
Intencao = Literal[
    "aceita",
    "recusa_firme",
    "quer_pensar",
    "duvida_processo",
    "duvida_oferta",
    "objecao",
    "quer_outro_valor",
    "quer_outro_prazo",
    "quer_outro_banco",
    "fornece_dado",
    "pede_humano",
    "reclamacao",
    "parar",
    "saudacao",
    "fora_de_escopo",
    "nao_sou_eu",
    "sinal_fraude_ou_vulnerabilidade",
    "ininteligivel",
    "adiar_com_hora",
    "adiar_sem_hora",
]
Objecao = Literal[
    "parcela_alta",
    "valor_baixo",
    "prazo_longo",
    "desconfianca",
    "ja_contratou",
    "nao_lembra",
    "receio_dados",
    "sem_tempo",
    "taxa_juros",
    "outra",
]
Desfecho = Literal["vendeu", "repassado", "agendado", "encerrado_sem_interesse", "recusado_facta"]
Estilo = Literal["curto", "longo", "audio", "sem_acento", "emoji", "abreviado", "caixa_alta", "rajada"]
Midia = Literal["audio", "imagem", "sticker", "documento", "localizacao"]
Em = Literal["EM1", "EM2", "EM3", "EM4", "EM5", "EM6", "EM7", "EM8", "EM9"]
PiiTipo = Literal["cpf", "telefone", "email", "cep", "uuid", "numero"]
CenarioTempo = Literal["horario_normal", "noite", "sabado", "domingo", "feriado_20_11", "virada_dataprev", "virada_22h30_utc"]
MotivoE10 = Literal[
    "pede_humano",
    "reclamacao",
    "recusa_politica",
    "recusa_firme",
    "tres_corrigiveis",
    "falhas_ferramenta",
    "indeterminado",
    "banco_fechado",
    "vacuo",
    "opt_out",
    "identidade",
    "humano_assumiu",
    "teto_turnos",
    "sem_avanco",
    "manipulacao",
    "midia",
    "alcada",
    "esgotou_contrapropostas",
    "fraude_vulnerabilidade",
    "proposta_viva",
]
CampoAlvo = Literal["pix", "conta", "cep", "numero_endereco", "celular"]
NotaEsperada = Literal["nenhuma", "TX-34", "TX-35"]
PedeHumano = Literal["nao", "cedo", "no_meio_da_coleta", "apos_recusa", "sempre"]

FASES: tuple[str, ...] = get_args(Fase)
INVARIANTES: tuple[str, ...] = get_args(Invariante)
INTENCOES: tuple[str, ...] = get_args(Intencao)
OBJECOES: tuple[str, ...] = get_args(Objecao)
DESFECHOS: tuple[str, ...] = get_args(Desfecho)
EMS: tuple[str, ...] = get_args(Em)
MOTIVOS_E10: tuple[str, ...] = get_args(MotivoE10)

# tokens de ação dos gabaritos: `acao` do Turno (H §2.2), ferramentas T1..T15 (F), mais envio/nota/agenda/lembrete
ACOES: frozenset[str] = frozenset(
    {"responder", "usar_ferramenta", "pedir_dado", "pedir_confirmacao", "aguardar", "repassar", "encerrar"}
    | {f"T{n}" for n in range(1, 16)}
    | {"T7_mesma_chave", "enviar", "nota", "agendar", "lembrete"}
)
TX_IDS: frozenset[str] = frozenset(
    [f"TX-{n:02d}" for n in range(1, 42)]
    + [f"TX-M{n:02d}" for n in range(1, 14)]
    + [f"NT-{n:02d}" for n in range(1, 8)]
    + [f"ST-{n:02d}" for n in range(0, 6)]
)
# conjunto fechado dos placeholders dos TX (TEXTOS-PARA-APROVACAO: os 11 do conjunto aprovado + os 7 de nota/aviso/agenda marcados «rever»)
PLACEHOLDERS: frozenset[str] = frozenset(
    {"nome", "banco", "valor_liberado", "valor_parcela", "prazo", "destino", "link", "campo", "retorno", "pedido", "quando"}
    | {"aviso_ia", "motivo", "motivacao_ou_objecao", "pendencia", "quando_a", "quando_b", "quando_alt"}
)
TX_COM_VALOR = frozenset({"TX-03", "TX-05", "TX-06", "TX-11", "TX-12", "TX-13", "TX-16", "TX-34", "TX-M09", "TX-M11"})

# a F3 curta (C5, roteiro B8.1a): P01–P08, P19–P31, P36–P41, P44–P50, P53–P54 e P57–P60
F3_CURTA_IDS: frozenset[str] = frozenset(
    {f"P{n:02d}" for n in (*range(1, 9), *range(19, 32), *range(36, 42), *range(44, 51), 53, 54, *range(57, 61))}
)
N_PERSONAS_H, N_PERSONAS_M, N_F3_CURTA = 60, 24, 40
MIN_PERSONAS_POR_INVARIANTE = 3
MAX_TURNOS_DO_MODELO = 24  # H P7
MEDIANA_MAX_CARACTERES = 30  # levantamento 09 §3: cliente p50 = 11 caracteres
MAX_CARACTERES_FORA_DA_MANIPULACAO = 300
MAX_FRACAO_MIDIA = 0.10  # no real 2,5% (áudio 1% + imagem 1,5%); aqui sobe porque o gabarito precisa exercitar a resposta padrão
MAX_VARIACOES = 2
EXECUCOES_POR_PERSONA = 3
FRACAO_HOLDOUT = 0.20

# Sobrenomes INVENTADOS (sílabas sorteadas com semente fixa): nenhuma persona leva sobrenome de gente de verdade.
_SOBRENOMES = """
    Alvardel Alvardi Alvelim Alvimar Baranti Baresco Barorim Barucci Belesco Calelim Calesco Calimar Calolim Calondi
    Corardel Corimar Corravo Corucci Davelim Davondi Doranti Doresco Dorimar Engardel Engardi Engelim Engimar Engorim
    Espesco Espucci Espuvel Ferravo Feruvel Filimar Galanti Galuvel Gurelim Gurimar Guruvel Helardi Helimar Helolim
    Heluvel Itaesco Juranti Jurardi Juresco Jurimar Jurolim Juruvel Lavardi Lavucci Lavuvel Maresco Marondi Marorim
    Marucci Maruvel Monanti Monelim Monesco Monravo Oriondi Penorim Piranti Pirardi Piresco Pirolim Pirorim Pirucci
    Ravelim Ravesco Ravorim Salesco Salravo Tavelim Tavimar Tavorim Toranti Torardi Torimar Torolim Torondi Torravo
    Toruvel Ulaardel Ulaesco Verimar Verondi Verorim Verravo Walardel Walimar Walondi Walravo Walucci Waluvel Zananti
    Zanucci Zanuvel
"""
SOBRENOMES_FICTICIOS: frozenset[str] = frozenset(_SOBRENOMES.split())

# --- calendário (J8; M §2.4; ROTEIRO «20/11 IA desligada, janela DATAPREV 20/11 22:00 a 23/11 06:00») --------------------------------

FUSO_SP = timezone(timedelta(hours=-3), "America/Sao_Paulo")  # sem horário de verão desde 2019
FERIADOS_2026: frozenset[date] = frozenset(
    date(2026, m, d) for m, d in ((1, 1), (4, 3), (4, 21), (5, 1), (6, 4), (9, 7), (10, 12), (11, 2), (11, 15), (11, 20), (12, 25))
)
JANELA_DATAPREV = (datetime(2026, 11, 20, 22, 0, tzinfo=FUSO_SP), datetime(2026, 11, 23, 6, 0, tzinfo=FUSO_SP))
ABRE, FECHA = time(8, 0), time(20, 0)


def dentro_do_horario(instante: datetime) -> bool:
    """Seg–sáb, 08:00 ≤ hora < 20:00 em São Paulo, fora de feriado nacional e da janela DATAPREV (nada sai fora disso: I3)."""
    if instante.tzinfo is None:
        raise ValueError("instante sem fuso")
    local = instante.astimezone(FUSO_SP)
    if local.weekday() == 6 or local.date() in FERIADOS_2026:
        return False
    if JANELA_DATAPREV[0] <= local < JANELA_DATAPREV[1]:
        return False
    return ABRE <= local.time() < FECHA


def _cenario_do_instante(instante: datetime) -> set[str]:
    """Rótulos de `CenarioTempo` que descrevem o instante (um instante pode ter mais de um, ex.: sábado e virada DATAPREV)."""
    local = instante.astimezone(FUSO_SP)
    rotulos: set[str] = set()
    if dentro_do_horario(instante) and local.weekday() < 5:
        rotulos.add("horario_normal")
    dia_util_ou_sabado = (
        local.weekday() < 6 and local.date() not in FERIADOS_2026 and not (JANELA_DATAPREV[0] <= local < JANELA_DATAPREV[1])
    )
    if dia_util_ou_sabado and not ABRE <= local.time() < FECHA:
        rotulos.add("noite")
    if local.weekday() == 5:
        rotulos.add("sabado")
    if local.weekday() == 6:
        rotulos.add("domingo")
    if local.date() == date(2026, 11, 20):
        rotulos.add("feriado_20_11")
    if JANELA_DATAPREV[0] <= local < JANELA_DATAPREV[1]:
        rotulos.add("virada_dataprev")
    utc = instante.astimezone(UTC)
    if utc.time() == time(22, 30) and dentro_do_horario(instante):
        rotulos.add("virada_22h30_utc")
    return rotulos


# --- modelos (Pydantic, extra='forbid', imutáveis) ---------------------------------------------------------------------------------


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


_ID_H = re.compile(r"^P(0[1-9]|[1-5][0-9]|60)$")
_ID_M = re.compile(r"^P-M(0[1-9]|1[0-9]|2[0-4])$")


class Perfil(_Modelo):
    idade: int
    vinculo_clt: bool
    meses_no_emprego: int
    margem_brl: int
    oferta_facta_ativa: bool
    valor_pre_aprovado_brl: int | None
    prazo_oferta_x: int | None
    cpf_alterado: bool = False

    @model_validator(mode="after")
    def _coerente(self) -> Perfil:
        if not 18 <= self.idade <= 75 or self.meses_no_emprego < 0 or self.margem_brl < 0:
            raise ValueError("idade 18-75, meses e margem não negativos")
        if self.oferta_facta_ativa:
            if self.valor_pre_aprovado_brl is None or self.prazo_oferta_x is None:
                raise ValueError("oferta ativa exige valor pré-aprovado e prazo")
            if self.valor_pre_aprovado_brl % 500 or self.valor_pre_aprovado_brl <= 0:
                raise ValueError("valor pré-aprovado redondo (múltiplo de 500)")
            if self.prazo_oferta_x not in (24, 36, 48, 60, 84, 96):
                raise ValueError("prazo da oferta fora da grade")
        elif self.valor_pre_aprovado_brl is not None or self.prazo_oferta_x is not None:
            raise ValueError("sem oferta ativa não há valor nem prazo")
        return self


class Contexto(_Modelo):
    inicio_utc: AwareDatetime
    instante_chave_utc: AwareDatetime  # o instante que define o cenário de tempo (pode ser o da resposta noturna do cliente)
    cenario_tempo: CenarioTempo


class Ritmo(_Modelo):
    perfil: Literal["rapido", "normal", "lento"]
    p50_s: int


class Comportamento(_Modelo):
    intencao_dominante: Intencao
    intencoes: tuple[Intencao, ...]
    objecoes: tuple[Objecao, ...]
    estilo: tuple[Estilo, ...]
    ritmo: Ritmo
    some_apos: Fase | None
    adia: Literal["nao", "com_hora", "sem_hora"]
    digita_cpf_no_texto: bool
    digita_telefone_no_texto: bool
    pede_humano: PedeHumano
    muda_de_ideia: bool
    hostil: bool
    midia: tuple[Midia, ...]

    @model_validator(mode="after")
    def _dominante_esta_na_lista(self) -> Comportamento:
        if not self.intencoes or self.intencao_dominante not in self.intencoes or not self.estilo:
            raise ValueError("a intenção dominante entra em `intencoes`; estilo não vazio")
        return self


class CenarioFacta(_Modelo):
    persona_duble: str | None
    global_duble: Literal["virada", "reabertura"] | None
    sem_chamada_facta: bool
    cenario: str
    resumo: str


class Persona(_Modelo):
    id: str
    familia: Literal["H", "M"]
    classe: str
    f3_curta: bool
    critica: bool = False
    cpf: str
    nome: str
    perfil: Perfil
    contexto: Contexto
    comportamento: Comportamento
    desfecho_esperado: Desfecho
    fases: tuple[Fase, ...]
    invariantes_em_risco: tuple[Invariante, ...]
    cenario_facta: CenarioFacta
    em: tuple[Em, ...] = ()

    @model_validator(mode="after")
    def _id_bate_com_a_familia(self) -> Persona:
        padrao = _ID_H if self.familia == "H" else _ID_M
        if not padrao.match(self.id):
            raise ValueError(f"id {self.id!r} não é de família {self.familia}")
        if self.familia == "M" and self.f3_curta:
            raise ValueError("P-M não entra na lista de 40 da F3 curta (as críticas ganham diálogo em B8.2)")
        if not self.fases or not self.invariantes_em_risco:
            raise ValueError("fases e invariantes não vazios")
        return self


class Turno(_Modelo):
    quem: Literal["cliente", "ia"]
    fase_esperada: Fase
    intencao_esperada: Intencao | None = None
    objecao_esperada: Objecao | None = None
    texto_cliente: str | None = None
    variacoes: tuple[str, ...] = ()
    midia: Midia | None = None
    pii_digitada: tuple[PiiTipo, ...] = ()
    campo_alvo: CampoAlvo | None = None
    em_utc: AwareDatetime | None = None
    acoes_permitidas: tuple[str, ...]
    acoes_proibidas: tuple[str, ...]
    tx_esperado: tuple[str, ...] = ()
    texto_livre_ia: bool = False
    evento: str | None = None
    nota_esperada: NotaEsperada | None = None
    motivo_e10: MotivoE10 | None = None
    invariantes: tuple[Invariante, ...] = ()

    @model_validator(mode="after")
    def _forma_do_turno(self) -> Turno:
        if self.quem == "cliente":
            if (self.texto_cliente is None) == (self.midia is None):
                raise ValueError("turno do cliente tem texto OU mídia")
            if self.tx_esperado or self.texto_livre_ia or self.evento or self.nota_esperada or self.motivo_e10:
                raise ValueError("campos da IA em turno do cliente")
        else:
            if self.texto_cliente is not None or self.variacoes or self.midia or self.pii_digitada or self.intencao_esperada:
                raise ValueError("campos do cliente em turno da IA (o texto da IA NÃO é fixado no gabarito)")
        return self


class Dialogo(_Modelo):
    persona_id: str
    turnos: tuple[Turno, ...]


class Semente(_Modelo):
    versao: int
    semente_global: int
    execucoes_por_persona: int
    ordem_personas: tuple[str, ...]
    ordem_f3_curta: tuple[str, ...]
    holdout: tuple[str, ...]
    sementes: dict[str, tuple[int, ...]]
    regras: dict[str, str]


class Corpus(_Modelo):
    personas: tuple[Persona, ...]
    personas_m: tuple[Persona, ...]
    dialogos: dict[str, Dialogo]
    semente: Semente
    duble: dict[str, Any]


# --- carregamento ---------------------------------------------------------------------------------------------------------------------


def _ler_jsonl(caminho: Path) -> list[dict[str, Any]]:
    return [json.loads(linha) for linha in caminho.read_text(encoding="utf-8").splitlines() if linha.strip()]


def carregar_bruto(raiz: Path = CORPUS_DIR) -> dict[str, Any]:
    """Lê os arquivos do corpus sem validar nada (os testes mutam este dicionário e chamam `validar`)."""
    return {
        "personas": _ler_jsonl(raiz / "personas.jsonl"),
        "personas_m": _ler_jsonl(raiz / "personas_m.jsonl"),
        "dialogos": {arq.stem: _ler_jsonl(arq) for arq in sorted((raiz / "dialogos").glob("*.jsonl"))},
        "semente": json.loads((raiz / "semente.json").read_text(encoding="utf-8")),
        "duble": json.loads((raiz / "duble_personas.json").read_text(encoding="utf-8")),
    }


def montar(bruto: dict[str, Any]) -> Corpus:
    """Dicionário bruto → `Corpus` tipado. Levanta `pydantic.ValidationError` se o esquema não fecha."""
    return Corpus(
        personas=tuple(Persona.model_validate(p) for p in bruto["personas"]),
        personas_m=tuple(Persona.model_validate(p) for p in bruto["personas_m"]),
        dialogos={pid: Dialogo(persona_id=pid, turnos=tuple(Turno.model_validate(t) for t in ts)) for pid, ts in bruto["dialogos"].items()},
        semente=Semente.model_validate(bruto["semente"]),
        duble=bruto["duble"],
    )


def carregar(raiz: Path = CORPUS_DIR) -> Corpus:
    return montar(carregar_bruto(raiz))


# --- semente determinística ----------------------------------------------------------------------------------------------------------


def _chave(semente_global: int, *partes: object) -> int:
    resumo = hashlib.sha256("|".join(str(p) for p in (semente_global, *partes)).encode()).hexdigest()
    return int(resumo[:16], 16)


def escolher_variacao(semente_global: int, persona_id: str, execucao: int, indice_turno: int, n_opcoes: int) -> int:
    """Índice (0 = texto original) da redação usada no turno `indice_turno` da `execucao` da persona; mesma entrada, mesma saída."""
    if n_opcoes < 1:
        raise ValueError("n_opcoes deve ser >= 1")
    return _chave(semente_global, "variacao", persona_id, execucao, indice_turno) % n_opcoes


def texto_do_turno(turno: Turno, semente_global: int, persona_id: str, execucao: int, indice_turno: int) -> str:
    if turno.texto_cliente is None:
        raise ValueError("turno sem texto (mídia ou turno da IA)")
    opcoes = (turno.texto_cliente, *turno.variacoes)
    return opcoes[escolher_variacao(semente_global, persona_id, execucao, indice_turno, len(opcoes))]


def _escolhe_por_classe(candidatos: Sequence[Persona], quantos: int, semente_global: int) -> list[str]:
    """Um por classe (o de menor chave), depois os `quantos` de menor chave entre esses: o hold-out espalha-se pelas classes."""
    melhor: dict[str, Persona] = {}
    for p in sorted(candidatos, key=lambda x: (_chave(semente_global, "holdout", x.id), x.id)):
        melhor.setdefault(p.classe, p)
    escolhidos = sorted(melhor.values(), key=lambda x: (_chave(semente_global, "holdout-classe", x.classe), x.classe))[:quantos]
    return [p.id for p in escolhidos]


def derivar_semente(personas: Sequence[Persona], semente_global: int, ids_m: Iterable[str] = ()) -> dict[str, Any]:
    """Reconstrói do zero o que `semente.json` guarda: ordem das personas, hold-out (20%) e as sementes das 3 execuções por persona."""
    ids = [p.id for p in personas]
    ordem = sorted(ids, key=lambda i: (_chave(semente_global, "ordem", i), i))
    f3 = [p for p in personas if p.f3_curta]
    resto = [p for p in personas if not p.f3_curta]
    holdout = [*_escolhe_por_classe(f3, round(len(f3) * FRACAO_HOLDOUT), semente_global)]
    holdout += _escolhe_por_classe(resto, round(len(resto) * FRACAO_HOLDOUT), semente_global)
    sementes = {
        pid: [_chave(semente_global, "execucao", pid, k) % 2**31 for k in range(1, EXECUCOES_POR_PERSONA + 1)] for pid in (*ids, *ids_m)
    }
    return {
        "ordem_personas": tuple(ordem),
        "ordem_f3_curta": tuple(i for i in ordem if i in {p.id for p in f3}),
        "holdout": tuple(sorted(holdout, key=lambda i: (_chave(semente_global, "ordem", i), i))),
        "sementes": sementes,
    }


# --- PII e texto ---------------------------------------------------------------------------------------------------------------------

_MARCADOR_PARA_TIPO = {
    mascara.CPF: "cpf",
    mascara.TELEFONE: "telefone",
    mascara.EMAIL: "email",
    mascara.CEP: "cep",
    mascara.UUID: "uuid",
    mascara.NUMERO: "numero",
}
CELULARES_SINTETICOS = frozenset({"912345678", "987654321", "999999999", "900000000"})  # os mesmos de scripts/varredura.py
_PLACEHOLDER = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)


def _digitos(trecho: str) -> str:
    return "".join(str(int(c)) for c in trecho if c.isdigit())


def _cpf_dv_valido(onze: str) -> bool:
    return len(onze) == 11 and mascara._cpf_valido(onze)


def cpf_sintetico(onze: str) -> bool:
    """`000.000.0nn-dd` com os dois dígitos verificadores certos (a faixa que não existe em pessoa de verdade)."""
    return len(onze) == 11 and onze.startswith("0000000") and _cpf_dv_valido(onze)


def achados_pii(texto: str) -> list[tuple[str, str]]:
    """PII que a máscara de B1.2 enxerga no texto: lista de (tipo, valor). Mesma ordem de etapas de `mascara.mascarar`."""
    achados: list[tuple[str, str]] = []
    vista = mascara._vista_ascii(texto)
    trocas_email = mascara._trocas_de_email(vista)
    achados += [("email", vista[i:f]) for i, f, _ in trocas_email]
    texto = mascara._aplicar(texto, trocas_email)
    vista = mascara._vista_ascii(texto)
    achados += [("uuid", m.group().lower()) for m in mascara._UUID.finditer(vista)]
    texto = mascara._mascarar_padrao(texto, mascara._UUID, mascara.UUID)
    vista = mascara._vista_ascii(texto)
    for i, f, marcador in mascara._trocas_de_digitos(vista):
        achados.append((_MARCADOR_PARA_TIPO[marcador], vista[i:f]))
    return achados


def _pii_nao_sintetica(tipo: str, valor: str) -> bool:
    """True se o dado NÃO é do conjunto sintético permitido (então é, ou parece, dado de gente de verdade)."""
    digitos = _digitos(valor)
    if tipo == "cpf":
        return not digitos.startswith("0000000")
    if tipo == "telefone":
        sem_pais = digitos[2:] if digitos.startswith("55") and len(digitos) > 11 else digitos
        return sem_pais[-9:] not in CELULARES_SINTETICOS
    if tipo == "email":
        return not valor.lower().endswith(".test")
    if tipo == "cep":
        return not digitos.startswith("00000")
    if tipo == "uuid":
        return not valor.startswith("00000000-")
    return not digitos.startswith("000")  # numero (8+ dígitos: chave/conta)


def _strings(objeto: Any, caminho: str = "") -> Iterator[tuple[str, str]]:
    """Todas as strings (caminho, valor) de um dump de modelo, para as varreduras que valem em qualquer campo."""
    if isinstance(objeto, str):
        yield caminho, objeto
    elif isinstance(objeto, dict):
        for k, v in objeto.items():
            yield from _strings(v, f"{caminho}.{k}" if caminho else str(k))
    elif isinstance(objeto, (list, tuple)):
        for i, v in enumerate(objeto):
            yield from _strings(v, f"{caminho}[{i}]")


# --- regras ---------------------------------------------------------------------------------------------------------------------------

Regra = Callable[[Corpus], list[str]]


def _todas(corpus: Corpus) -> tuple[Persona, ...]:
    return (*corpus.personas, *corpus.personas_m)


def _regra_ids_unicos(corpus: Corpus) -> list[str]:
    erros: list[str] = []
    for rotulo, valores in (("id", [p.id for p in _todas(corpus)]), ("nome", [p.nome for p in _todas(corpus)])):
        erros += [f"ids_unicos: {rotulo} repetido: {v}" for v, n in Counter(valores).items() if n > 1]
    return erros


def _regra_nome_ficticio(corpus: Corpus) -> list[str]:
    erros = []
    for p in _todas(corpus):
        partes = p.nome.split()
        if len(partes) < 2 or not all(x.isalpha() and x[0].isupper() for x in partes) or partes[-1] not in SOBRENOMES_FICTICIOS:
            erros.append(f"nome_ficticio: {p.id}: sobrenome fora da lista de inventados ({p.nome!r})")
    return erros


def _regra_cpf_sintetico(corpus: Corpus) -> list[str]:
    erros = []
    for p in _todas(corpus):
        if not re.fullmatch(r"000\.000\.0[0-9]{2}-[0-9]{2}", p.cpf):
            erros.append(f"cpf_sintetico: {p.id}: CPF fora do formato 000.000.0nn-dd")
        elif not cpf_sintetico(_digitos(p.cpf)):
            erros.append(f"cpf_sintetico: {p.id}: dígito verificador errado")
    return erros


def _regra_cpf_alinhado_duble(corpus: Corpus) -> list[str]:
    """O CPF e o vínculo com o dublê batem com o instantâneo de `bancos-duble/personas/personas.yaml` (ids e CPFs alinhados)."""
    duble = corpus.duble
    por_id = {d["id"]: d for d in duble["personas"]}
    cpfs_do_duble = {d["cpf"] for d in duble["personas"]}
    quem_aponta = {pid: d["id"] for d in duble["personas"] for pid in d["f3"]}
    erros: list[str] = []
    livres: list[Persona] = []
    for p in _todas(corpus):
        cf = p.cenario_facta
        if cf.persona_duble is not None:
            d = por_id.get(cf.persona_duble)
            if d is None:
                erros.append(f"cpf_alinhado_duble: {p.id}: persona do dublê inexistente ({cf.persona_duble})")
                continue
            if p.cpf != d["cpf"]:
                erros.append(f"cpf_alinhado_duble: {p.id}: CPF diferente do da persona {d['id']} do dublê")
            if cf.cenario != d["cenario"]:
                erros.append(f"cpf_alinhado_duble: {p.id}: cenário {cf.cenario!r} difere do do dublê ({d['cenario']!r})")
            if cf.sem_chamada_facta or cf.global_duble:
                erros.append(f"cpf_alinhado_duble: {p.id}: persona do dublê não pode ser «sem FACTA» nem global")
            if p.familia == "H" and quem_aponta.get(p.id) != d["id"]:
                erros.append(f"cpf_alinhado_duble: {p.id}: o dublê não lista {p.id} em `f3` de {d['id']}")
        else:
            livres.append(p)
            if p.cpf in cpfs_do_duble:
                erros.append(f"cpf_alinhado_duble: {p.id}: sem persona no dublê mas usa CPF de uma delas")
            if p.familia == "H" and p.id in quem_aponta:
                erros.append(f"cpf_alinhado_duble: {p.id}: o dublê tem persona para ela ({quem_aponta[p.id]})")
            global_esperado = duble["f3_globais"].get(p.id)
            if p.familia == "H" and global_esperado != cf.global_duble:
                erros.append(f"cpf_alinhado_duble: {p.id}: global_duble deveria ser {global_esperado!r}")
            if p.familia == "H" and (p.id in duble["f3_sem_facta"]) != cf.sem_chamada_facta and global_esperado is None:
                erros.append(f"cpf_alinhado_duble: {p.id}: sem_chamada_facta não bate com `f3_sem_facta` do dublê")
            if p.familia == "M" and not cf.sem_chamada_facta:
                erros.append(f"cpf_alinhado_duble: {p.id}: P-M sem persona do dublê tem de declarar sem_chamada_facta")
    dos_livres = Counter(p.cpf for p in livres)
    erros += [f"cpf_alinhado_duble: CPF {c} repetido entre personas sem stub na FACTA" for c, n in dos_livres.items() if n > 1]
    return erros


def _regra_conjunto_f3_curta(corpus: Corpus) -> list[str]:
    erros = []
    if len(corpus.personas) != N_PERSONAS_H or [p.id for p in corpus.personas] != [f"P{n:02d}" for n in range(1, N_PERSONAS_H + 1)]:
        erros.append(f"conjunto_f3_curta: esperadas as {N_PERSONAS_H} personas P01..P60, em ordem")
    if [p.id for p in corpus.personas_m] != [f"P-M{n:02d}" for n in range(1, N_PERSONAS_M + 1)]:
        erros.append(f"conjunto_f3_curta: esperadas as {N_PERSONAS_M} personas P-M01..P-M24, em ordem")
    marcadas = frozenset(p.id for p in corpus.personas if p.f3_curta)
    if marcadas != F3_CURTA_IDS:
        faltam, sobram = sorted(F3_CURTA_IDS - marcadas), sorted(marcadas - F3_CURTA_IDS)
        erros.append(f"conjunto_f3_curta: as {N_F3_CURTA} da F3 curta divergem do roteiro (faltam {faltam}, sobram {sobram})")
    return erros


def _regra_f3_com_dialogo(corpus: Corpus) -> list[str]:
    erros = []
    com_dialogo = set(corpus.dialogos)
    for pid in sorted(F3_CURTA_IDS - com_dialogo):
        erros.append(f"f3_com_dialogo: {pid} é da F3 curta e não tem diálogo")
    for pid in sorted(com_dialogo - F3_CURTA_IDS):
        erros.append(f"f3_com_dialogo: {pid} tem diálogo mas não é da F3 curta")
    for pid, d in corpus.dialogos.items():
        if not d.turnos or d.turnos[0].quem != "ia":
            erros.append(f"f3_com_dialogo: {pid}: o diálogo começa com a IA (abertura TX-01 ou aborto em E0)")
    return erros


def _contagem(personas: Iterable[Persona], extrair: Callable[[Persona], Iterable[str]]) -> Counter[str]:
    c: Counter[str] = Counter()
    for p in personas:
        c.update(set(extrair(p)))
    return c


def _regra_cobertura_invariantes(corpus: Corpus) -> list[str]:
    holdout = set(corpus.semente.holdout)
    todas = _contagem(_todas(corpus), lambda p: p.invariantes_em_risco)
    dev = _contagem((p for p in _todas(corpus) if p.id not in holdout), lambda p: p.invariantes_em_risco)
    erros = [
        f"cobertura_invariantes: {i} testado por {todas[i]} persona(s) (mínimo {MIN_PERSONAS_POR_INVARIANTE})"
        for i in INVARIANTES
        if todas[i] < MIN_PERSONAS_POR_INVARIANTE
    ]
    erros += [
        f"cobertura_invariantes: {i} testado por {dev[i]} persona(s) fora do hold-out (mínimo {MIN_PERSONAS_POR_INVARIANTE})"
        for i in INVARIANTES
        if dev[i] < MIN_PERSONAS_POR_INVARIANTE <= todas[i]
    ]
    return erros


def _falta(esperado: Iterable[str], contagem: Counter[str], codigo: str, rotulo: str) -> list[str]:
    return [f"{codigo}: {rotulo} {x} sem nenhuma persona" for x in esperado if contagem[x] < 1]


def _regra_cobertura_fases(corpus: Corpus) -> list[str]:
    return _falta(FASES, _contagem(_todas(corpus), lambda p: p.fases), "cobertura_fases", "fase")


def _regra_cobertura_intencoes(corpus: Corpus) -> list[str]:
    return _falta(INTENCOES, _contagem(_todas(corpus), lambda p: p.comportamento.intencoes), "cobertura_intencoes", "intenção")


def _regra_cobertura_objecoes(corpus: Corpus) -> list[str]:
    return _falta(OBJECOES, _contagem(_todas(corpus), lambda p: p.comportamento.objecoes), "cobertura_objecoes", "objeção")


def _regra_cobertura_em(corpus: Corpus) -> list[str]:
    return _falta(EMS, _contagem(_todas(corpus), lambda p: p.em), "cobertura_em", "caso de M")


def _regra_cobertura_cenarios(corpus: Corpus) -> list[str]:
    """Cenários que o roteiro e o pedido exigem: tempo (noite, sábado, domingo, feriado, DATAPREV, 22:30 UTC), humano, hostil, mídia..."""
    todas = _todas(corpus)
    existe: dict[str, Callable[[Persona], bool]] = {
        **{f"cenario_tempo {t}": (lambda p, t=t: p.contexto.cenario_tempo == t) for t in get_args(CenarioTempo)},
        "cliente hostil": lambda p: p.comportamento.hostil,
        "cliente que pede humano": lambda p: p.comportamento.pede_humano != "nao",
        "cliente que muda de ideia": lambda p: p.comportamento.muda_de_ideia,
        "lead que some após E3": lambda p: p.comportamento.some_apos == "E3",
        "adia com hora": lambda p: p.comportamento.adia == "com_hora",
        "adia sem hora": lambda p: p.comportamento.adia == "sem_hora",
        "digita CPF no texto": lambda p: p.comportamento.digita_cpf_no_texto,
        "digita telefone no texto": lambda p: p.comportamento.digita_telefone_no_texto,
        "áudio": lambda p: "audio" in p.comportamento.midia,
        "imagem": lambda p: "imagem" in p.comportamento.midia,
        "recusa FACTA status 28 (AF cancelada)": lambda p: p.cenario_facta.cenario == "af_cancelada",
        "estilo áudio": lambda p: "audio" in p.comportamento.estilo,
        "estilo sem acento": lambda p: "sem_acento" in p.comportamento.estilo,
        "estilo emoji": lambda p: "emoji" in p.comportamento.estilo,
    }
    return [f"cobertura_cenarios: nenhuma persona para «{nome}»" for nome, teste in existe.items() if not any(teste(p) for p in todas)]


def _regra_cenario_tempo_coerente(corpus: Corpus) -> list[str]:
    erros = []
    for p in _todas(corpus):
        ctx = p.contexto
        if ctx.instante_chave_utc < ctx.inicio_utc:
            erros.append(f"cenario_tempo_coerente: {p.id}: o instante-chave é anterior ao início")
        if ctx.cenario_tempo not in _cenario_do_instante(ctx.instante_chave_utc):
            erros.append(
                f"cenario_tempo_coerente: {p.id}: cenario_tempo={ctx.cenario_tempo} não descreve {ctx.instante_chave_utc:%Y-%m-%dT%H:%MZ}"
            )
        if ctx.cenario_tempo == "horario_normal" and not dentro_do_horario(ctx.inicio_utc):
            erros.append(f"cenario_tempo_coerente: {p.id}: horario_normal mas o início está fora do horário")
    return erros


def _tipos_declarados(turno: Turno) -> set[str]:
    return set(turno.pii_digitada)


def _regra_pii_texto(corpus: Corpus) -> list[str]:
    erros: list[str] = []
    for pid, d in corpus.dialogos.items():
        for i, t in enumerate(d.turnos):
            if t.texto_cliente is None:
                continue
            declarados = _tipos_declarados(t)
            for k, texto in enumerate((t.texto_cliente, *t.variacoes)):
                achados = achados_pii(texto)
                erros += [
                    f"pii_texto: {pid} turno {i}: {tipo} fora do conjunto sintético ({valor!r})"
                    for tipo, valor in achados
                    if _pii_nao_sintetica(tipo, valor)
                ]
                erros += [
                    f"pii_texto: {pid} turno {i}: {tipo} no texto sem constar de pii_digitada"
                    for tipo in sorted({t_ for t_, _ in achados} - declarados)
                ]
                if k == 0:
                    erros += [
                        f"pii_texto: {pid} turno {i}: pii_digitada diz {tipo} mas o texto não tem"
                        for tipo in sorted(declarados - {t_ for t_, _ in achados})
                    ]
    # nos demais campos (persona, perfil, resumo, notas) não pode haver PII nenhuma, nem a sintética
    for p in _todas(corpus):
        dump = p.model_dump(mode="json", exclude={"cpf", "contexto"})
        for caminho, valor in _strings(dump):
            erros += [f"pii_texto: {p.id}.{caminho}: {tipo} em campo de persona" for tipo, _ in achados_pii(valor)]
    return erros


def _todos_os_textos(corpus: Corpus) -> Iterator[tuple[str, str]]:
    for p in _todas(corpus):
        yield from ((f"{p.id}.{c}", v) for c, v in _strings(p.model_dump(mode="json")))
    for pid, d in corpus.dialogos.items():
        yield from ((f"{pid}.{c}", v) for c, v in _strings(d.model_dump(mode="json")))


def _regra_placeholder_fechado(corpus: Corpus) -> list[str]:
    erros = []
    for onde, texto in _todos_os_textos(corpus):
        for m in _PLACEHOLDER.finditer(texto):
            if m.group(1) not in PLACEHOLDERS:
                erros.append(f"placeholder_fechado: {onde}: {{{{{m.group(1)}}}}} fora do conjunto fechado dos TX")
        resto = _PLACEHOLDER.sub("", texto)
        if "{{" in resto or "}}" in resto:
            erros.append(f"placeholder_fechado: {onde}: chaves duplas sem par")
    for pid, d in corpus.dialogos.items():
        erros += [
            f"placeholder_fechado: {pid}: {tx} não é um TX da lista aprovável" for t in d.turnos for tx in t.tx_esperado if tx not in TX_IDS
        ]
    return erros


def _mensagem_da_ia(t: Turno) -> bool:
    return t.quem == "ia" and bool(t.tx_esperado or t.texto_livre_ia)


def _regra_dialogo_gabarito(corpus: Corpus) -> list[str]:
    """Forma do gabarito: vocabulário de ações, permitidas ∩ proibidas = ∅, intenção em todo turno do cliente, coerência com a persona."""
    erros: list[str] = []
    por_id = {p.id: p for p in corpus.personas}
    for pid, d in corpus.dialogos.items():
        persona = por_id.get(pid)
        fases_do_dialogo = {t.fase_esperada for t in d.turnos}
        if persona is not None:
            if not fases_do_dialogo <= set(persona.fases):
                erros.append(f"dialogo_gabarito: {pid}: fases {sorted(fases_do_dialogo - set(persona.fases))} fora de `fases` da persona")
            if not set(persona.fases) - {"E0"} <= fases_do_dialogo:
                sem_passar = sorted(set(persona.fases) - fases_do_dialogo - {"E0"})
                erros.append(f"dialogo_gabarito: {pid}: fases da persona que o diálogo não percorre ({sem_passar})")
        objecoes_vistas: list[str] = []
        for i, t in enumerate(d.turnos):
            onde = f"dialogo_gabarito: {pid} turno {i}"
            fora = (set(t.acoes_permitidas) | set(t.acoes_proibidas)) - ACOES
            if fora:
                erros.append(f"{onde}: ação fora do vocabulário {sorted(fora)}")
            if set(t.acoes_permitidas) & set(t.acoes_proibidas):
                erros.append(f"{onde}: ação ao mesmo tempo permitida e proibida {sorted(set(t.acoes_permitidas) & set(t.acoes_proibidas))}")
            if not t.acoes_permitidas:
                erros.append(f"{onde}: sem ações permitidas")
            if t.quem == "cliente":
                if t.midia is None and t.intencao_esperada is None:
                    erros.append(f"{onde}: turno do cliente sem intenção esperada")
                if persona and t.intencao_esperada and t.intencao_esperada not in persona.comportamento.intencoes:
                    erros.append(f"{onde}: intenção {t.intencao_esperada} que a persona não exibe")
                if t.objecao_esperada:
                    objecoes_vistas.append(t.objecao_esperada)
                if len(t.variacoes) > MAX_VARIACOES or t.texto_cliente in t.variacoes or len(set(t.variacoes)) != len(t.variacoes):
                    erros.append(f"{onde}: variações repetidas, iguais ao texto ou mais de {MAX_VARIACOES}")
            elif t.invariantes == () and not t.acoes_proibidas:
                erros.append(f"{onde}: turno da IA sem invariante nem ação proibida")
            if (
                "TX-07" in t.tx_esperado or (t.quem == "cliente" and t.fase_esperada == "E5" and t.intencao_esperada == "fornece_dado")
            ) and not t.campo_alvo:
                erros.append(f"{onde}: pedido ou entrega de campo da E5 sem campo_alvo")
            if t.campo_alvo and not ("TX-07" in t.tx_esperado or t.quem == "cliente"):
                erros.append(f"{onde}: campo_alvo fora de TX-07 e de resposta do cliente")
        encerrou = False
        for i, t in enumerate(d.turnos):
            if encerrou and _mensagem_da_ia(t):
                erros.append(f"dialogo_gabarito: {pid} turno {i}: mensagem da IA depois do encerramento (E10)")
            encerrou = encerrou or (t.quem == "ia" and t.fase_esperada == "E10")
        if persona and objecoes_vistas:
            it = iter(persona.comportamento.objecoes)
            if not all(o in it for o in objecoes_vistas):  # subsequência, em ordem
                erros.append(f"dialogo_gabarito: {pid}: objeções {objecoes_vistas} fora da ordem/lista da persona")
    return erros


_PEDIDOS_DE_CONFIRMACAO = frozenset({"TX-11", "TX-12", "TX-13"})


def _regra_gabarito_i1(corpus: Corpus) -> list[str]:
    """I1: o gabarito nunca permite T4/T7 sem TX de confirmação (11/12/13) seguido de SIM do cliente na E6, e só no turno E7."""
    erros: list[str] = []
    for pid, d in corpus.dialogos.items():
        pedido, confirmado = False, False
        for i, t in enumerate(d.turnos):
            onde = f"gabarito_i1: {pid} turno {i}"
            if "T4" in t.acoes_permitidas:
                erros.append(f"{onde}: T4 (consulta paga) está fora do MVP e não pode constar como permitida")
            if t.quem == "ia":
                if _PEDIDOS_DE_CONFIRMACAO & set(t.tx_esperado):
                    pedido, confirmado = True, False  # nova confirmação invalida a anterior
                if "T7" in t.acoes_permitidas:
                    if not confirmado:
                        erros.append(f"{onde}: T7 permitido sem pedido de confirmação + SIM antes")
                    if t.fase_esperada != "E7":
                        erros.append(f"{onde}: T7 só no turno E7")
                    pedido, confirmado = False, False  # a confirmação foi consumida
            elif t.fase_esperada == "E6":
                if t.intencao_esperada == "aceita":
                    if not pedido:
                        erros.append(f"{onde}: SIM na E6 sem o pedido de confirmação (TX-11/12/13) antes")
                    confirmado = pedido
                else:
                    confirmado = False
    return erros


def _regra_gabarito_i4(corpus: Corpus) -> list[str]:
    """I4: T7 ≤ 1 por confirmação; retry só com a MESMA chave (T7_mesma_chave, depois de TX-19); indeterminado (TX-15) nunca reenvia."""
    erros: list[str] = []
    for pid, d in corpus.dialogos.items():
        t7_desde_a_confirmacao, indeterminado, transitorio = 0, False, False
        for i, t in enumerate(d.turnos):
            if t.quem != "ia":
                continue
            onde = f"gabarito_i4: {pid} turno {i}"
            if _PEDIDOS_DE_CONFIRMACAO & set(t.tx_esperado):
                t7_desde_a_confirmacao, indeterminado, transitorio = 0, False, False
            if "TX-15" in t.tx_esperado:
                indeterminado = True
            if "TX-19" in t.tx_esperado:
                transitorio = True
            if "T7" in t.acoes_permitidas:
                t7_desde_a_confirmacao += 1
                if t7_desde_a_confirmacao > 1:
                    erros.append(f"{onde}: segundo T7 sem nova confirmação")
                if indeterminado:
                    erros.append(f"{onde}: T7 depois de indeterminado (TX-15): nunca reenvia")
            if "T7_mesma_chave" in t.acoes_permitidas and (indeterminado or not transitorio):
                erros.append(f"{onde}: T7_mesma_chave só depois de erro transitório (TX-19) e nunca depois de indeterminado")
    return erros


def _instantes(persona: Persona | None, turnos: Sequence[Turno]) -> list[datetime | None]:
    atual = persona.contexto.inicio_utc if persona else None
    saida: list[datetime | None] = []
    for t in turnos:
        atual = t.em_utc or atual
        saida.append(atual)
    return saida


def _regra_gabarito_i3(corpus: Corpus) -> list[str]:
    """I3: toda mensagem da IA no gabarito cai em horário (seg–sáb, 08–20, fora de feriado/DATAPREV); o relógio não anda para trás."""
    erros: list[str] = []
    por_id = {p.id: p for p in corpus.personas}
    for pid, d in corpus.dialogos.items():
        persona = por_id.get(pid)
        anterior = persona.contexto.inicio_utc if persona else None
        for i, (t, quando) in enumerate(zip(d.turnos, _instantes(persona, d.turnos), strict=True)):
            if t.em_utc is not None and anterior is not None and t.em_utc < anterior:
                erros.append(f"gabarito_i3: {pid} turno {i}: o relógio anda para trás")
            if t.em_utc is not None:
                anterior = t.em_utc
            if _mensagem_da_ia(t) and quando is not None and not dentro_do_horario(quando):
                erros.append(f"gabarito_i3: {pid} turno {i}: mensagem da IA fora do horário ({quando:%Y-%m-%dT%H:%MZ})")
    return erros


def _regra_gabarito_i6(corpus: Corpus) -> list[str]:
    """I6: no máximo uma mensagem da IA por turno: duas seguidas só se a segunda nasce de evento (resultado de T7/T8, lembrete, volta)."""
    erros = []
    for pid, d in corpus.dialogos.items():
        for i, (a, b) in enumerate(zip(d.turnos, d.turnos[1:], strict=False), start=1):
            if _mensagem_da_ia(a) and _mensagem_da_ia(b) and not b.evento:
                erros.append(f"gabarito_i6: {pid} turno {i}: duas mensagens da IA seguidas sem evento que justifique a segunda")
    return erros


def _regra_gabarito_i7(corpus: Corpus) -> list[str]:
    return [
        f"gabarito_i7: {pid}: {n} turnos do modelo (teto {MAX_TURNOS_DO_MODELO})"
        for pid, d in corpus.dialogos.items()
        if (n := sum(t.quem == "ia" and not t.evento for t in d.turnos)) > MAX_TURNOS_DO_MODELO
    ]


_MOTIVOS_SEM_NOTA = frozenset({"opt_out", "identidade", "humano_assumiu"})


def _regra_gabarito_i8(corpus: Corpus) -> list[str]:
    """I8: o E10 declara nota e motivo; nota «nenhuma» após opt-out, identidade contestada, humano assumiu ou cliente que nunca falou;
    TX-35 (obrigatória) depois de indeterminado."""
    erros: list[str] = []
    for pid, d in corpus.dialogos.items():
        cliente_falou = any(t.quem == "cliente" for t in d.turnos)
        indeterminado, encerrou = False, False
        for i, t in enumerate(d.turnos):
            onde = f"gabarito_i8: {pid} turno {i}"
            indeterminado = indeterminado or "TX-15" in t.tx_esperado
            if t.quem != "ia":
                continue
            if t.fase_esperada != "E10" or encerrou:
                if t.nota_esperada or t.motivo_e10:
                    erros.append(f"{onde}: nota/motivo só no primeiro turno E10")
                continue
            encerrou = True
            if t.nota_esperada is None or t.motivo_e10 is None:
                erros.append(f"{onde}: o turno E10 declara nota_esperada e motivo_e10")
                continue
            if t.motivo_e10 in _MOTIVOS_SEM_NOTA and t.nota_esperada != "nenhuma":
                erros.append(f"{onde}: motivo {t.motivo_e10} não gera nota ao consultor")
            if not cliente_falou and t.nota_esperada != "nenhuma":
                erros.append(f"{onde}: cliente nunca respondeu: sem nota")
            if indeterminado and t.motivo_e10 not in _MOTIVOS_SEM_NOTA and t.nota_esperada != "TX-35":
                erros.append(f"{onde}: depois de indeterminado a nota é a TX-35 (obrigatória)")
            if t.nota_esperada == "TX-35" and not indeterminado:
                erros.append(f"{onde}: TX-35 sem indeterminado antes")
    return erros


def _desfecho_do_dialogo(d: Dialogo) -> set[str]:
    """Desfechos compatíveis com o fim do diálogo (o primeiro turno E10 diz o motivo; sem E10, vale o último turno da IA)."""
    ias = [t for t in d.turnos if t.quem == "ia"]
    if not ias:
        return set()
    tx = {x for t in ias for x in t.tx_esperado}
    primeiro_e10 = next((t for t in ias if t.fase_esperada == "E10"), None)
    if primeiro_e10 is not None:
        if primeiro_e10.motivo_e10 == "recusa_politica" and "TX-18" in tx:
            return {"recusado_facta"}
        if primeiro_e10.motivo_e10 in ("opt_out", "identidade", "recusa_firme"):
            return {"encerrado_sem_interesse"}
        return {"repassado"}
    ultimo = ias[-1]
    if ultimo.fase_esperada == "E0":
        return {"repassado"}  # E0 aborta antes de qualquer mensagem: o lead segue com o consultor
    if ultimo.fase_esperada == "E8" and "TX-16" in tx:
        return {"vendeu"}
    if "TX-M08" in tx:
        return {"agendado"}
    return set()


def _regra_desfecho_coerente(corpus: Corpus) -> list[str]:
    erros = []
    for p in corpus.personas:
        d = corpus.dialogos.get(p.id)
        if d is None:
            continue
        derivados = _desfecho_do_dialogo(d)
        if p.desfecho_esperado not in derivados:
            erros.append(
                f"desfecho_coerente: {p.id}: persona diz {p.desfecho_esperado} e o fim do diálogo dá {sorted(derivados) or 'nada'}"
            )
    return erros


def _regra_invariantes_do_dialogo(corpus: Corpus) -> list[str]:
    erros = []
    for p in corpus.personas:
        d = corpus.dialogos.get(p.id)
        if d is None:
            continue
        testados = {i for t in d.turnos for i in t.invariantes}
        falta = set(p.invariantes_em_risco) - testados
        if falta:
            erros.append(f"invariantes_do_dialogo: {p.id}: invariantes em risco que nenhum turno do diálogo testa {sorted(falta)}")
    return erros


def _regra_forma_whatsapp(corpus: Corpus) -> list[str]:
    """Forma das falas (levantamento 09 §3): curtas (p50 de 11 caracteres), quase tudo texto; texto longo só na persona de manipulação."""
    textos: list[tuple[str, str]] = []
    cliente = midia = 0
    for pid, d in corpus.dialogos.items():
        for t in d.turnos:
            if t.quem == "cliente":
                cliente += 1
                midia += t.midia is not None
                if t.texto_cliente is not None:
                    textos.append((pid, t.texto_cliente))
    por_id = {p.id: p for p in corpus.personas}
    erros = []
    if textos and (mediana := statistics.median(len(x) for _, x in textos)) > MEDIANA_MAX_CARACTERES:
        erros.append(f"forma_whatsapp: mediana de {mediana} caracteres (máximo {MEDIANA_MAX_CARACTERES}; no real p50 = 11)")
    if cliente and midia / cliente > MAX_FRACAO_MIDIA:
        erros.append(f"forma_whatsapp: {midia}/{cliente} turnos de mídia (máximo {MAX_FRACAO_MIDIA:.0%})")
    erros += [
        f"forma_whatsapp: {pid}: texto de {len(x)} caracteres fora da persona de manipulação"
        for pid, x in textos
        if len(x) > MAX_CARACTERES_FORA_DA_MANIPULACAO and por_id[pid].classe != "manipulacao"
    ]
    return erros


def _regra_semente_reprodutivel(corpus: Corpus) -> list[str]:
    s = corpus.semente
    esperado = derivar_semente(corpus.personas, s.semente_global, [p.id for p in corpus.personas_m])
    erros = []
    if s.versao != 1 or s.execucoes_por_persona != EXECUCOES_POR_PERSONA:
        erros.append("semente_reprodutivel: versão 1 e 3 execuções por persona")
    if s.ordem_personas != esperado["ordem_personas"]:
        erros.append("semente_reprodutivel: ordem_personas não é a derivada da semente global")
    if s.ordem_f3_curta != esperado["ordem_f3_curta"]:
        erros.append("semente_reprodutivel: ordem_f3_curta não é a derivada da semente global")
    if s.holdout != esperado["holdout"]:
        erros.append(f"semente_reprodutivel: hold-out diferente do derivado ({list(esperado['holdout'])})")
    faltam = sorted(set(esperado["sementes"]) - set(s.sementes))
    if faltam:
        erros.append(f"semente_reprodutivel: personas sem sementes de execução {faltam}")
    erros += [
        f"semente_reprodutivel: sementes de {pid} diferentes das derivadas"
        for pid, v in s.sementes.items()
        if pid in esperado["sementes"] and list(v) != esperado["sementes"][pid]
    ]
    erros += [f"semente_reprodutivel: sementes de persona inexistente {pid}" for pid in sorted(set(s.sementes) - set(esperado["sementes"]))]
    return erros


REGRAS: dict[str, Regra] = {
    "ids_unicos": _regra_ids_unicos,
    "nome_ficticio": _regra_nome_ficticio,
    "cpf_sintetico": _regra_cpf_sintetico,
    "cpf_alinhado_duble": _regra_cpf_alinhado_duble,
    "conjunto_f3_curta": _regra_conjunto_f3_curta,
    "f3_com_dialogo": _regra_f3_com_dialogo,
    "cobertura_invariantes": _regra_cobertura_invariantes,
    "cobertura_fases": _regra_cobertura_fases,
    "cobertura_intencoes": _regra_cobertura_intencoes,
    "cobertura_objecoes": _regra_cobertura_objecoes,
    "cobertura_em": _regra_cobertura_em,
    "cobertura_cenarios": _regra_cobertura_cenarios,
    "cenario_tempo_coerente": _regra_cenario_tempo_coerente,
    "pii_texto": _regra_pii_texto,
    "placeholder_fechado": _regra_placeholder_fechado,
    "dialogo_gabarito": _regra_dialogo_gabarito,
    "gabarito_i1": _regra_gabarito_i1,
    "gabarito_i3": _regra_gabarito_i3,
    "gabarito_i4": _regra_gabarito_i4,
    "gabarito_i6": _regra_gabarito_i6,
    "gabarito_i7": _regra_gabarito_i7,
    "gabarito_i8": _regra_gabarito_i8,
    "desfecho_coerente": _regra_desfecho_coerente,
    "invariantes_do_dialogo": _regra_invariantes_do_dialogo,
    "forma_whatsapp": _regra_forma_whatsapp,
    "semente_reprodutivel": _regra_semente_reprodutivel,
}


def validar(bruto: dict[str, Any]) -> list[str]:
    """Todas as violações do corpus, `codigo: mensagem`. Lista vazia = corpus bom. Esquema inválido vira `esquema: …` e para por aí."""
    try:
        corpus = montar(bruto)
    except ValidationError as erro:
        return [f"esquema: {'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in erro.errors()]
    return [violacao for regra in REGRAS.values() for violacao in regra(corpus)]


def main(argv: Sequence[str] = ()) -> int:  # pragma: no cover
    """Sem argumento valida o corpus do disco. Com `--semente` imprime a ordem, o hold-out e as sementes derivados."""
    bruto = carregar_bruto()
    if "--semente" in argv:
        corpus = montar(bruto)
        derivada = derivar_semente(corpus.personas, corpus.semente.semente_global, [p.id for p in corpus.personas_m])
        print(json.dumps(derivada, ensure_ascii=False, indent=1))
        return 0
    violacoes = validar(bruto)
    for v in violacoes:
        print(v)
    print(f"corpus: {len(violacoes)} violação(ões)")
    return 1 if violacoes else 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    raise SystemExit(main(sys.argv[1:]))
