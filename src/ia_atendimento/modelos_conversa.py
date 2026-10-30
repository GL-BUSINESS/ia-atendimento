"""Modelos do estado da conversa (E0–E10). Ficam num módulo sem dependência de `estado.py` para `Mudancas` poder tipar `estado_conversa`
com eles (sem o tipo, um dict cru burlava `extra='forbid'` e o «só códigos»). Ver `estado_conversa.py` para leitura/gravação.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator

from ia_atendimento.tipos import LIMITE_JSON_OCTETOS, Codigo40, Referencia, octetos_como_jsonb

Fase = Literal["E0", "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10"]
Codigo = Codigo40  # nome de campo, intenção, objeção, flag


class _Base(BaseModel):
    # `revalidate_instances`: um `EstadoConversa` forjado por `model_construct` não entra em `Mudancas` sem passar pelos validadores
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, revalidate_instances="always")


class Contadores(_Base):
    """Só o que NÃO é coluna. Nomes como `turnos` ou `sem_avanco` são recusados (campo desconhecido)."""

    rodada: Annotated[int, Field(ge=0, strict=True)] = 0
    falhas: Annotated[int, Field(ge=0, strict=True)] = 0
    t4_pagas: Annotated[int, Field(ge=0, strict=True)] = 0
    midia_sem_suporte: Annotated[int, Field(ge=0, strict=True)] = 0
    fora_de_escopo: Annotated[int, Field(ge=0, strict=True)] = 0
    t5_no_turno: Annotated[int, Field(ge=0, strict=True)] = 0


class OfertaCorrente(_Base):
    """Referência à oferta em jogo; os valores ficam no 360/ferramenta, nunca aqui."""

    banco: Annotated[str, StringConstraints(pattern=r"^[A-Z0-9_]{1,32}$")]
    oferta_id: Referencia
    oferta_versao: Annotated[int, Field(ge=1, strict=True)]


class Confirmacao(_Base):
    estado: Literal["pendente", "aceita", "recusada", "expirada", "invalidada"]
    expira_em: AwareDatetime | None = None


class TentativaT7(_Base):
    estado: Codigo
    classe: Codigo | None = None
    n: Annotated[int, Field(ge=0, le=99, strict=True)] = 0


class Pausa(_Base):
    agendamento_ref: Referencia | None = None
    retoma_fase: Literal["E2", "E3", "E4", "E5", "E6", "E8"]  # nunca E7 (CHECK do DDL)


class EstadoConversa(_Base):
    fase: Fase
    contadores: Contadores = Contadores()
    oferta_corrente: OfertaCorrente | None = None
    opcoes_t5: Annotated[tuple[Referencia, ...], Field(max_length=5)] = ()
    confirmacao: Confirmacao | None = None
    campos_coletados: Annotated[tuple[Codigo, ...], Field(max_length=20)] = ()  # nomes, nunca valores
    campos_faltantes: Annotated[tuple[Codigo, ...], Field(max_length=20)] = ()
    tentativa_t7: TentativaT7 | None = None
    objecoes: Annotated[tuple[Codigo, ...], Field(max_length=10)] = ()
    intencoes_recentes: Annotated[tuple[Codigo, ...], Field(max_length=3)] = ()
    flags: Annotated[dict[Codigo, StrictBool], Field(max_length=16)] = Field(default_factory=dict)
    contexto_previo: Annotated[tuple[Codigo, ...], Field(max_length=10)] = ()
    pausa: Pausa | None = None

    @model_validator(mode="after")
    def _cabe_em_2kb(self) -> EstadoConversa:
        if octetos_como_jsonb(self.para_json()) > LIMITE_JSON_OCTETOS:
            raise ValueError("estado_conversa acima de 2 KB")
        return self

    def para_json(self) -> dict[str, Any]:
        """O que vai para a coluna: sem o que é padrão (campos vazios, contadores zerados), sempre com a `fase`."""
        return self.model_dump(mode="json", exclude_defaults=True)
