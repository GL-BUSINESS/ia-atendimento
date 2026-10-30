"""Estado da conversa (B1.1): a máquina E0–E10 e o que o turno seguinte precisa lembrar, em JSON ≤ 2 KB dentro de `ia.atendimento`.

- **Só códigos, referências e contadores.** Nenhum campo guarda texto livre, valor monetário, CPF, nome ou telefone: nomes de campo
  (`renda`, `conta`), códigos de intenção/objeção e ids de oferta. Campo desconhecido é recusado (`extra='forbid'`) e o erro não ecoa o
  valor (`hide_input_in_errors=True`; `estado_conversa_de_json` devolve só nome de campo e regra).
- **Fonte única:** o que já é coluna de `ia.atendimento` (`sem_avanco`, `turnos`, `lembretes_enviados`...) NÃO mora no JSON.
- **Gravar é uma transição** (`versao + 1`, CAS): o processador do turno grava o estado junto com o resto. O lease não é tocado aqui
  (num `pausado` ele tem de ficar >= `retoma_em`); quem renova é a transição do turno. A `fase` gerada acompanha o JSON, e o CHECK
  cruzado fase×estado do banco barra combinação impossível (`TransicaoInvalida`).
- **`ultimo_cliente_em`** (0003) é coluna à parte, com GRANT próprio: o evento da mensagem a escreve sem disputar o CAS de `versao`.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Any, Final, Literal
from uuid import UUID

import psycopg
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator

from ia_atendimento.estado import (
    ESTADOS_NAO_TERMINAIS,
    LIMITE_JSON_OCTETOS,
    AtendimentoInexistente,
    Mudancas,
    Relogio,
    agora_de,
    aplicar,
    octetos_como_jsonb,
    validar_corpo,
)

JANELA_SERVICO: Final = timedelta(hours=24)  # janela de serviço do WhatsApp: texto livre só dentro dela
Fase = Literal["E0", "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10"]
Codigo = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,40}$")]  # nome de campo, intenção, objeção, flag
Referencia = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.:-]{1,64}$")]  # id opaco (oferta, agendamento, opção)


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


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


def estado_conversa_de_json(corpo: object) -> EstadoConversa:
    """Valida o JSON; recusa campo desconhecido e documento acima de 2 KB com `EntradaInvalida` (só nomes, nunca valores)."""
    return validar_corpo(EstadoConversa, corpo)


def ler_estado_conversa(conn: psycopg.Connection, atendimento_id: UUID | str) -> EstadoConversa:
    linha = conn.execute("SELECT estado_conversa FROM ia.atendimento WHERE atendimento_id = %s", (atendimento_id,)).fetchone()
    if linha is None:
        raise AtendimentoInexistente("atendimento não existe")
    return estado_conversa_de_json(linha[0])


def gravar_estado_conversa(
    conn: psycopg.Connection, atendimento_id: UUID | str, versao: int, estado: EstadoConversa, *, relogio: Relogio
) -> int:
    """Grava o estado como transição com CAS (`versao + 1`); atendimento encerrado não muda. Devolve a nova `versao`."""
    agora = agora_de(relogio)
    mudancas = Mudancas(estado_conversa=estado.para_json())
    return aplicar(conn, atendimento_id, versao, mudancas, agora=agora, de=ESTADOS_NAO_TERMINAIS)


def registrar_mensagem_do_cliente(conn: psycopg.Connection, atendimento_id: UUID | str, quando: datetime) -> datetime:
    """`ultimo_cliente_em = greatest(atual, quando)`: só avança (mensagem fora de ordem não recua a janela de 24 h) e NÃO toca `versao`.

    UPDATE próprio, de uma coluna com GRANT próprio (0003): não disputa o CAS com o processador do turno.
    """
    if quando.tzinfo is None:
        raise ValueError("ultimo_cliente_em exige datetime com fuso")
    linha = conn.execute(
        "UPDATE ia.atendimento SET ultimo_cliente_em = greatest(coalesce(ultimo_cliente_em, '-infinity'::timestamptz), %s) "
        "WHERE atendimento_id = %s RETURNING ultimo_cliente_em",
        (quando, atendimento_id),
    ).fetchone()
    if linha is None:
        raise AtendimentoInexistente("atendimento não existe")
    return linha[0]


def janela_24h_aberta(ultimo_cliente_em: datetime | None, agora: datetime) -> bool:
    """Texto livre só com `agora − ultimo_cliente_em < 24 h`; desconhecido (None) = fechada (só template)."""
    return ultimo_cliente_em is not None and agora - ultimo_cliente_em < JANELA_SERVICO
