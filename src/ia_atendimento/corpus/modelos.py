"""Modelos Pydantic do corpus: `extra='forbid'`, imutáveis, tipos estritos (sem coerção de `"41"` em int nem `"yes"` em bool)."""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, model_validator

from ia_atendimento.corpus.vocabulario import (
    CENARIOS_FACTA,
    CLASSES_H,
    CLASSES_M,
    CampoAlvo,
    CenarioTempo,
    Desfecho,
    Em,
    Estilo,
    Evento,
    Fase,
    Intencao,
    Invariante,
    Midia,
    MotivoE10,
    NotaEsperada,
    Objecao,
    PedeHumano,
    PiiTipo,
)


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


_ID_H = re.compile(r"^P(0[1-9]|[1-5][0-9]|60)$")
_ID_M = re.compile(r"^P-M(0[1-9]|1[0-9]|2[0-4])$")
Texto = StrictStr
# o prazo é da grade de prazos da FACTA; a margem e o valor são inteiros em reais
PrazoOferta = Annotated[StrictInt, Field(ge=12, le=96)]


class Perfil(_Modelo):
    idade: StrictInt
    vinculo_clt: StrictBool
    meses_no_emprego: StrictInt
    margem_brl: StrictInt
    oferta_facta_ativa: StrictBool
    valor_pre_aprovado_brl: StrictInt | None
    prazo_oferta_x: PrazoOferta | None
    cpf_alterado: StrictBool = False
    campos_no_360: tuple[CampoAlvo, ...] = ()  # campos da E5 que o 360 já tem (a IA não os pede)

    @model_validator(mode="after")
    def _coerente(self) -> Perfil:
        if not 18 <= self.idade <= 75 or self.meses_no_emprego < 0 or self.margem_brl < 0:
            raise ValueError("idade 18-75, meses e margem não negativos")
        if self.oferta_facta_ativa:
            if self.valor_pre_aprovado_brl is None or self.prazo_oferta_x is None:
                raise ValueError("oferta ativa exige valor pré-aprovado e prazo")
            if self.valor_pre_aprovado_brl % 500 or self.valor_pre_aprovado_brl <= 0:
                raise ValueError("valor pré-aprovado redondo (múltiplo de 500)")
        elif self.valor_pre_aprovado_brl is not None or self.prazo_oferta_x is not None:
            raise ValueError("sem oferta ativa não há valor nem prazo")
        return self


class Contexto(_Modelo):
    inicio_utc: AwareDatetime
    instante_chave_utc: AwareDatetime  # o instante que define o cenário de tempo (pode ser o da resposta noturna do cliente)
    cenario_tempo: CenarioTempo


class Ritmo(_Modelo):
    perfil: Literal["rapido", "normal", "lento"]
    p50_s: StrictInt


class Comportamento(_Modelo):
    intencao_dominante: Intencao
    intencoes: tuple[Intencao, ...]
    objecoes: tuple[Objecao, ...]
    estilo: tuple[Estilo, ...]
    ritmo: Ritmo
    some_apos: Fase | None
    adia: Literal["nao", "com_hora", "sem_hora"]
    digita_cpf_no_texto: StrictBool
    digita_telefone_no_texto: StrictBool
    pede_humano: PedeHumano
    muda_de_ideia: StrictBool
    hostil: StrictBool
    midia: tuple[Midia, ...]

    @model_validator(mode="after")
    def _dominante_esta_na_lista(self) -> Comportamento:
        if not self.intencoes or self.intencao_dominante not in self.intencoes or not self.estilo:
            raise ValueError("a intenção dominante entra em `intencoes`; estilo não vazio")
        return self


class CenarioFacta(_Modelo):
    persona_duble: Texto | None
    global_duble: Literal["virada", "reabertura"] | None
    sem_chamada_facta: StrictBool
    cenario: Texto
    resumo: Texto

    @model_validator(mode="after")
    def _cenario_conhecido(self) -> CenarioFacta:
        if self.cenario not in CENARIOS_FACTA:
            raise ValueError(f"cenário {self.cenario!r} fora do vocabulário")
        return self


class Persona(_Modelo):
    id: Texto
    familia: Literal["H", "M"]
    classe: Texto
    f3_curta: StrictBool
    critica: StrictBool = False
    cpf: Texto
    nome: Texto
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
        padrao, classes = (_ID_H, CLASSES_H) if self.familia == "H" else (_ID_M, CLASSES_M)
        if not padrao.match(self.id):
            raise ValueError(f"id {self.id!r} não é de família {self.familia}")
        if self.classe not in classes:
            raise ValueError(f"classe {self.classe!r} fora do vocabulário da família {self.familia}")
        if self.familia == "M" and self.f3_curta:
            raise ValueError("P-M não entra na lista de 40 da F3 curta (as críticas têm diálogo à parte)")
        if self.familia == "H" and (self.critica or self.em):
            raise ValueError("`critica` e `em` são das P-M")
        if not self.fases or not self.invariantes_em_risco:
            raise ValueError("fases e invariantes não vazios")
        return self


class Turno(_Modelo):
    quem: Literal["cliente", "ia"]
    fase_esperada: Fase
    intencao_esperada: Intencao | None = None
    objecao_esperada: Objecao | None = None
    texto_cliente: Texto | None = None
    variacoes: tuple[Texto, ...] = ()
    midia: Midia | None = None
    pii_digitada: tuple[PiiTipo, ...] = ()
    campo_alvo: CampoAlvo | None = None
    em_utc: AwareDatetime | None = None
    dispara_em_utc: AwareDatetime | None = None  # volta combinada (TX-M08): quando a IA volta a falar
    acoes_permitidas: tuple[Texto, ...]
    acoes_proibidas: tuple[Texto, ...]
    tx_esperado: tuple[Texto, ...] = ()
    texto_livre_ia: StrictBool = False
    evento: Evento | None = None
    nota_esperada: NotaEsperada | None = None
    motivo_e10: MotivoE10 | None = None
    invariantes: tuple[Invariante, ...] = ()

    @model_validator(mode="after")
    def _forma_do_turno(self) -> Turno:
        if self.quem == "cliente":
            if (self.texto_cliente is None) == (self.midia is None):
                raise ValueError("turno do cliente tem texto OU mídia")
            if self.tx_esperado or self.texto_livre_ia or self.evento or self.nota_esperada or self.motivo_e10 or self.dispara_em_utc:
                raise ValueError("campos da IA em turno do cliente")
        elif (
            self.texto_cliente is not None
            or self.variacoes
            or self.midia
            or self.pii_digitada
            or self.intencao_esperada
            or self.objecao_esperada
        ):
            raise ValueError("campos do cliente em turno da IA (o texto da IA NÃO é fixado no gabarito)")
        return self


class Dialogo(_Modelo):
    persona_id: Texto
    turnos: tuple[Turno, ...]


class Semente(_Modelo):
    versao: StrictInt
    semente_global: StrictInt
    execucoes_por_persona: StrictInt
    ordem_personas: tuple[Texto, ...]
    ordem_f3_curta: tuple[Texto, ...]
    holdout: tuple[Texto, ...]
    sementes: dict[Texto, tuple[StrictInt, ...]]
    regras: dict[Texto, Texto]

    @model_validator(mode="after")
    def _chaves_das_regras(self) -> Semente:
        if set(self.regras) != CHAVES_DAS_REGRAS:
            raise ValueError(f"`regras` tem de ter exatamente as chaves {sorted(CHAVES_DAS_REGRAS)}")
        return self


CHAVES_DAS_REGRAS = frozenset({"chave", "ordem_personas", "sementes_de_execucao", "escolha_da_variacao", "holdout", "reproduzir"})


class PersonaDuble(_Modelo):
    id: Texto
    n: StrictInt
    cpf: Texto
    cenario: Texto
    f3: tuple[Texto, ...]
    clone_de: Texto | None = None  # B2.4 (R1-09): persona do dublê de que esta é cópia (mesmo cenário, CPF e scenario próprios)


class Duble(_Modelo):
    """Instantâneo de `bancos-duble/personas/personas.yaml`: só o que liga a persona do corpus à do dublê."""

    fonte: Texto
    f3_globais: dict[Texto, Literal["virada", "reabertura"]]
    f3_sem_facta: tuple[Texto, ...]
    personas: tuple[PersonaDuble, ...]


class Corpus(_Modelo):
    personas: tuple[Persona, ...]
    personas_m: tuple[Persona, ...]
    dialogos: dict[str, Dialogo]
    semente: Semente
    duble: Duble

    def todas(self) -> tuple[Persona, ...]:
        return (*self.personas, *self.personas_m)


def como_dict(modelo: BaseModel, **opcoes: Any) -> dict[str, Any]:
    return modelo.model_dump(mode="json", **opcoes)
