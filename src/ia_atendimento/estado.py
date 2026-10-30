"""Ciclo de vida do atendimento (B1.1, sp01 T3): `reservado → aberto ⇄ aguardando_cliente → pausado/repassando → encerrado`.

- **Uma só escrita:** `aplicar` é o único `UPDATE … WHERE atendimento_id = $1 AND versao = $2` (CAS), com `versao + 1` e `atualizado_em`;
  toda transição é um invólucro fino dele. Sem SELECT-e-depois-UPDATE: o estado de origem entra no próprio `WHERE`; só no caminho de
  falha há uma leitura, para dizer POR QUE (`ConflitoVersao`, `AtendimentoInexistente` ou `TransicaoInvalida`).
- **Tempo de negócio vem do `Relogio` injetado**, nunca do `now()` do banco (lease, `assumido_em`, `encerrado_em`, `atualizado_em`).
- **Fase e estado andam juntos:** o CHECK `atendimento_conversa_check` cruza as duas máquinas; quem muda `estado` passa `fase` no mesmo
  UPDATE (`jsonb_set`, atômico). Violação de CHECK vira `TransicaoInvalida` (com o NOME da restrição, nunca os valores da linha).
- **Imutáveis por privilégio:** `faixa_esforco`, `comissao_esperada_brl`, identidade e versões de artefato são gravadas em `abrir` e ficam
  fora do GRANT UPDATE de `ia_app`; `Mudancas` tem exatamente as colunas do GRANT (um teste confere com o catálogo).
- **Sem PII:** a entrada não tem CPF, telefone (`chat_number` vai ao cofre na B1.5), nome nem texto de cliente; `hide_input_in_errors`.
- Fora daqui (outras etapas): `pausar`/`sair_da_pausa`/`abrir_agendado` (B5.7b), tetos/`max_abertos`/pré-voo (B1.5), jobs e reapers (B1.3).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Collection
from dataclasses import dataclass, fields
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any, Final, Literal
from uuid import UUID

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, ValidationError, model_validator

LEASE_RESERVADO_S: Final = 120  # `reservado` nasce com 2 min (K §8.1)
LEASE_TURNO_S: Final = 300  # `iniciar` e cada transição renovam para +5 min
LIMITE_JSON_OCTETOS: Final = 2048  # CHECK do DDL: `octet_length(perfil::text)` e `octet_length(estado_conversa::text)`
PREFIXO_FINGERPRINT: Final = b"ia-entrada/v1\n"
ARTEFATOS: Final = ("roteiro", "regras", "catalogo", "motor")

Relogio = Callable[[], datetime]
Estado = Literal["reservado", "aberto", "aguardando_cliente", "pausado", "repassando", "encerrado"]
Modo = Literal["real", "sombra", "duble", "teste"]
Faixa = Literal["baixa", "media", "alta", "muito_alta"]
Desfecho = Literal[
    "sem_venda", "repassado", "sem_resposta", "expirado", "opt_out", "abortado", "vendeu", "destravou", "motivo_identificado"
]
Codigo40 = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,40}$")]
Codigo60 = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,60}$")]
Hex24 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{24}$")]

ESTADOS_NAO_TERMINAIS: Final = frozenset({"reservado", "aberto", "aguardando_cliente", "pausado", "repassando"})
_REPASSAVEIS: Final = frozenset({"aberto", "aguardando_cliente", "pausado"})
_FAIXAS_COM_COMISSAO: Final = frozenset({"alta", "muito_alta"})
_MODOS_GLOBAIS: Final = frozenset({"real", "sombra", "duble"})


# --- erros (sem valor de cliente na mensagem) ------------------------------------------------------------------------------------


class EstadoErro(Exception):
    """Base dos erros do ciclo de vida. Mensagens trazem nomes de campo/estado/restrição, nunca valores da linha."""


class TransicaoInvalida(EstadoErro):
    def __init__(self, mensagem: str, *, restricao: str | None = None) -> None:
        super().__init__(mensagem)
        self.restricao = restricao  # nome do CHECK do banco que barrou, quando foi ele


class ConflitoVersao(EstadoErro):
    """Outro escritor mudou o atendimento (CAS por `versao` perdeu): releia e decida de novo."""


class AtendimentoInexistente(EstadoErro):
    pass


class ConflitoIdempotencia(EstadoErro):
    """Mesma `(origem, chave_logica)` com identidade diferente (HTTP 409 `chave_reutilizada`)."""


class ChatOcupado(EstadoErro):
    """Já existe atendimento não encerrado neste chat (HTTP 409 `chat_ocupado`)."""


class ArtefatoAusente(EstadoErro):
    def __init__(self, tipos: tuple[str, ...]) -> None:
        super().__init__("sem artefato_versao para: " + ", ".join(tipos))
        self.tipos = tipos


class ModoInvalido(EstadoErro):
    def __init__(self, codigo: str) -> None:
        super().__init__(codigo)
        self.codigo = codigo  # teste_fora_da_lista | persona_fora_de_teste | modo_teste_global | validacao


class EntradaInvalida(EstadoErro, ValueError):
    """Argumento incoerente que o banco também recusaria (CHECK), barrado antes de chegar nele.

    `campos` = pares `(campo, regra)` quando vem de validação de corpo (`EntradaAtendimento.de_corpo`): só NOMES, nunca o valor.
    """

    def __init__(self, mensagem: str, *, campos: tuple[tuple[str, str], ...] = ()) -> None:
        super().__init__(mensagem)
        self.campos = campos


# --- utilidades ------------------------------------------------------------------------------------------------------------------


def agora_de(relogio: Relogio) -> datetime:
    agora = relogio()
    if agora.tzinfo is None:
        raise ValueError("o relógio deve devolver datetime com fuso")
    return agora


def octetos_como_jsonb(valor: object) -> int:
    """Tamanho em bytes do `valor::text` do jsonb (`", "` e `": "` como separadores): o que o CHECK `octet_length(...) <= 2048` mede."""
    return len(json.dumps(valor, ensure_ascii=False, separators=(", ", ": ")).encode("utf-8"))


def idempotency_key(chave_logica: str) -> str:
    """sha256 hex da chave lógica: o CHECK do DDL exige `idempotency_key = encode(sha256(chave_logica), 'hex')`."""
    return hashlib.sha256(chave_logica.encode("utf-8")).hexdigest()


# --- versões dos artefatos -------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Versoes:
    roteiro: int
    regras: int
    catalogo: int
    motor: int


def versoes_vigentes(conn: psycopg.Connection) -> Versoes:
    """`max(numero)` por tipo em `artefato_versao`; tipo ausente ⇒ `ArtefatoAusente` (a IA não abre atendimento sem roteiro aprovado)."""
    achadas = dict(conn.execute("SELECT tipo, max(numero) FROM ia.artefato_versao GROUP BY tipo").fetchall())
    faltam = tuple(sorted(t for t in ARTEFATOS if t not in achadas))
    if faltam:
        raise ArtefatoAusente(faltam)
    return Versoes(**{t: int(achadas[t]) for t in ARTEFATOS})


# --- entrada e identidade --------------------------------------------------------------------------------------------------------


class EntradaAtendimento(BaseModel):
    """Corpo de `POST /atendimentos` sem o que é derivado (faixa, comissão) ou PII (`chat_number`). Chave desconhecida ⇒ erro."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    chave_logica: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,19}:[A-Za-z0-9_.:-]{1,180}$")]
    gatilho: Literal["venda", "esteira_parada"]  # `agendamento` nasce por `abrir_agendado` (B5.7b)
    pessoa_id: UUID
    chat_id: Hex24
    phone_id: Hex24
    disparado_por: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    clt_job_id: UUID | None = None
    sessao_id: UUID | None = None
    motivo_escolha: Literal["mais_antigo_elegivel", "oferta_forte", "consultor_sobrecarregado", "teste", "outro"] | None = None
    motivo_escolha_nota: Annotated[str, StringConstraints(min_length=1, max_length=80)] | None = None
    criterio_versao: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.-]{1,64}$")] | None = None
    perfil: dict[str, Any] = Field(default_factory=dict)
    perfil_versao: Annotated[int, Field(ge=1, le=32767)] = 1
    responsavel_antes: Annotated[str, StringConstraints(min_length=1, max_length=128)] | None = None
    banco: Annotated[str, StringConstraints(pattern=r"^[A-Z0-9_]{1,32}$")] | None = None
    produto: Annotated[str, StringConstraints(pattern=r"^[A-Z0-9_]{1,32}$")] | None = None
    persona_id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,40}$")] | None = None
    modo: Literal["teste"] | None = None  # asserção do chamador; o modo de verdade sai de `resolver_modo`
    ultimo_cliente_em: AwareDatetime | None = None

    @model_validator(mode="after")
    def _regras_dos_checks(self) -> EntradaAtendimento:
        if self.gatilho == "venda" and self.criterio_versao is None:
            raise ValueError("gatilho venda exige criterio_versao")
        if (self.motivo_escolha == "outro") != (self.motivo_escolha_nota is not None):
            raise ValueError("motivo_escolha_nota existe se, e somente se, motivo_escolha for 'outro'")
        if octetos_como_jsonb(self.perfil) > LIMITE_JSON_OCTETOS:
            raise ValueError("perfil acima de 2 KB")
        return self


def campos_invalidos(erro: ValidationError) -> tuple[tuple[str, str], ...]:
    """`(campo, regra)` de cada recusa. `.errors()` e `.json()` carregam o valor recusado mesmo com `hide_input_in_errors`: aqui não."""
    achados = erro.errors(include_input=False, include_context=False, include_url=False)
    return tuple(
        (
            ".".join(str(p) for p in e["loc"]) or "(corpo)",
            e["msg"].removeprefix("Value error, ") if e["type"] == "value_error" else e["type"],
        )
        for e in achados
    )


def validar_corpo[M: BaseModel](modelo: type[M], corpo: object) -> M:
    """Valida o corpo; se recusar, levanta `EntradaInvalida` só com nomes de campo e regra (422), sem valor e sem a causa encadeada."""
    try:
        return modelo.model_validate(corpo)
    except ValidationError as erro:
        campos = campos_invalidos(erro)
    # fora do `except`: o erro novo não leva `__context__` com a ValidationError (que guarda o valor recusado)
    raise EntradaInvalida("corpo inválido: " + ", ".join(f"{c} ({r})" for c, r in campos), campos=campos)


def entrada_de_corpo(corpo: object) -> EntradaAtendimento:
    return validar_corpo(EntradaAtendimento, corpo)


def entrada_fingerprint(entrada: EntradaAtendimento) -> str:
    """Contrato 08 §4: `sha256(b"ia-entrada/v1\\n" + JSON canônico)` só da identidade do episódio (chaves ordenadas, sem espaço).

    Ficam FORA (instáveis num replay do n8n, ou PII): `chat_number`, comissão, faixa, modo, `ultimo_cliente_em`, `disparado_por`,
    `sessao_id`,
    `motivo_escolha*`, `criterio_versao`, `perfil*`, `responsavel_antes`, `banco`, `produto`.
    """
    identidade = {
        "chat_id": entrada.chat_id,
        "chave_logica": entrada.chave_logica,
        "clt_job_id": None if entrada.clt_job_id is None else str(entrada.clt_job_id),
        "gatilho": entrada.gatilho,
        "persona_id": entrada.persona_id,
        "pessoa_id": str(entrada.pessoa_id),
        "phone_id": entrada.phone_id,
    }
    presentes = {k: v for k, v in identidade.items() if v is not None}
    canonico = json.dumps(presentes, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(PREFIXO_FINGERPRINT + canonico).hexdigest()


def resolver_modo(
    *, chat_id: str, modo_global: str, chats_teste: Collection[str], persona_id: str | None = None, modo_pedido: str | None = None
) -> Modo:
    """Contrato 08 §6: global `real|sombra|duble`; `teste` só com `chat_id ∈ chats_teste`; `persona_id` só em chat de teste."""
    if modo_global == "teste":
        raise ModoInvalido("modo_teste_global")
    if modo_global not in _MODOS_GLOBAIS:
        raise ModoInvalido("validacao")
    em_teste = chat_id in chats_teste
    if modo_pedido == "teste" and not em_teste:
        raise ModoInvalido("teste_fora_da_lista")
    if persona_id is not None and not em_teste:
        raise ModoInvalido("persona_fora_de_teste")
    return "teste" if em_teste else modo_global  # type: ignore[return-value]


def _validar_esforco(faixa: str, comissao: Decimal | str | int | None) -> Decimal | None:
    if faixa not in ("baixa", "media", "alta", "muito_alta"):
        raise EntradaInvalida("faixa_esforco desconhecida")
    valor = None if comissao is None else Decimal(str(comissao))
    if valor is not None and valor < 0:
        raise EntradaInvalida("comissao_esperada_brl negativa")
    if valor is None and faixa in _FAIXAS_COM_COMISSAO:
        raise EntradaInvalida("faixa alta/muito_alta exige comissão calculada")
    return valor


# --- leitura ---------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Atendimento:
    atendimento_id: UUID
    origem: str
    chave_logica: str
    entrada_fingerprint: str
    gatilho: str
    pessoa_id: UUID
    chat_id: str
    phone_id: str
    clt_job_id: UUID | None
    modo: str
    persona_id: str | None
    estado: str
    versao: int
    fase: str
    lease_ate: datetime | None
    assumido_em: datetime | None
    retoma_em: datetime | None
    faixa_esforco: str
    comissao_esperada_brl: Decimal | None
    roteiro_versao: int
    regras_versao: int
    catalogo_versao: int
    motor_versao: int
    responsavel_antes: str | None
    chatbot_antes: str | None
    chatbot_estado: str
    desfecho: str | None
    motivo_desfecho: str | None
    contexto_codigos: tuple[str, ...]
    opt_out_em: datetime | None
    humano_assumiu_em: datetime | None
    repasse_modo: str | None
    repasse_consultor_ref: str | None
    estado_conversa: dict[str, Any]
    ultimo_cliente_em: datetime | None
    iniciado_em: datetime
    encerrado_em: datetime | None
    atualizado_em: datetime


_COLUNAS_LEITURA: Final = tuple(f.name for f in fields(Atendimento))


def ler(conn: psycopg.Connection, atendimento_id: UUID | str) -> Atendimento:
    consulta = sql.SQL("SELECT {} FROM ia.atendimento WHERE atendimento_id = %s").format(
        sql.SQL(", ").join(sql.Identifier(c) for c in _COLUNAS_LEITURA)
    )
    with conn.cursor(row_factory=dict_row) as cur:
        linha = cur.execute(consulta, (atendimento_id,)).fetchone()
    if linha is None:
        raise AtendimentoInexistente("atendimento não existe")
    return Atendimento(**{**linha, "contexto_codigos": tuple(linha["contexto_codigos"])})


# --- abrir (idempotente) ---------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Resultado:
    atendimento_id: UUID
    estado: str
    versao: int
    modo: str
    repetido: bool  # True = replay: devolve o que está GRAVADO, nada é atualizado


_INSERIR: Final = """
INSERT INTO ia.atendimento (origem, chave_logica, idempotency_key, entrada_fingerprint, gatilho, disparado_por, sessao_id, motivo_escolha,
  motivo_escolha_nota, criterio_versao, comissao_esperada_brl, faixa_esforco, pessoa_id, chat_id, phone_id, clt_job_id, banco, produto,
  perfil_versao, perfil, roteiro_versao, regras_versao, catalogo_versao, motor_versao, modo, persona_id, responsavel_antes,
  ultimo_cliente_em, lease_ate, iniciado_em, atualizado_em)
VALUES (%(origem)s, %(chave_logica)s, %(idem)s, %(fp)s, %(gatilho)s, %(disparado_por)s, %(sessao_id)s, %(motivo_escolha)s,
  %(motivo_escolha_nota)s, %(criterio_versao)s, %(comissao)s, %(faixa)s, %(pessoa_id)s, %(chat_id)s, %(phone_id)s, %(clt_job_id)s,
  %(banco)s,
  %(produto)s, %(perfil_versao)s, %(perfil)s, %(roteiro)s, %(regras)s, %(catalogo)s, %(motor)s, %(modo)s, %(persona_id)s,
  %(responsavel_antes)s, %(ultimo_cliente_em)s, %(lease_ate)s, %(agora)s, %(agora)s)
ON CONFLICT (origem, idempotency_key) DO NOTHING
RETURNING atendimento_id, estado, versao, modo
"""


def _replay(conn: psycopg.Connection, origem: str, idem: str, fp: str) -> Resultado | None:
    linha = conn.execute(
        "SELECT atendimento_id, estado, versao, modo, entrada_fingerprint FROM ia.atendimento WHERE origem = %s AND idempotency_key = %s",
        (origem, idem),
    ).fetchone()
    if linha is None:
        return None
    if linha[4] != fp:
        raise ConflitoIdempotencia("mesma chave lógica com outra identidade de entrada")
    return Resultado(linha[0], linha[1], linha[2], linha[3], repetido=True)


def _parametros_de_insercao(
    origem: str, entrada: EntradaAtendimento, versoes: Versoes, modo: str, faixa: str, comissao: Decimal | None, agora: datetime
) -> dict[str, Any]:
    return {
        "origem": origem, "chave_logica": entrada.chave_logica, "idem": idempotency_key(entrada.chave_logica),
        "fp": entrada_fingerprint(entrada), "gatilho": entrada.gatilho, "disparado_por": entrada.disparado_por,
        "sessao_id": entrada.sessao_id, "motivo_escolha": entrada.motivo_escolha, "motivo_escolha_nota": entrada.motivo_escolha_nota,
        "criterio_versao": entrada.criterio_versao, "comissao": comissao, "faixa": faixa, "pessoa_id": entrada.pessoa_id,
        "chat_id": entrada.chat_id, "phone_id": entrada.phone_id, "clt_job_id": entrada.clt_job_id, "banco": entrada.banco,
        "produto": entrada.produto, "perfil_versao": entrada.perfil_versao, "perfil": Jsonb(entrada.perfil),
        "roteiro": versoes.roteiro, "regras": versoes.regras, "catalogo": versoes.catalogo, "motor": versoes.motor, "modo": modo,
        "persona_id": entrada.persona_id, "responsavel_antes": entrada.responsavel_antes,
        "ultimo_cliente_em": entrada.ultimo_cliente_em, "lease_ate": agora + timedelta(seconds=LEASE_RESERVADO_S), "agora": agora,
    }  # fmt: skip


def abrir(
    conn: psycopg.Connection,
    *,
    origem: str,
    entrada: EntradaAtendimento,
    versoes: Versoes,
    modo_global: str,
    chats_teste: Collection[str],
    faixa_esforco: str,
    comissao_esperada_brl: Decimal | str | int | None,
    relogio: Relogio,
) -> Resultado:
    """Cria o atendimento `reservado` (fase E0, lease 2 min). A identidade é `(origem, chave_logica)` + `entrada_fingerprint`:

    mesmo corpo ⇒ `Resultado(repetido=True)` com o gravado (200); corpo diferente ⇒ `ConflitoIdempotencia` (409), **antes** de olhar o chat,
    então vale mesmo com o chat ocupado (pelo próprio atendimento). Chat com outro atendimento não encerrado ⇒ `ChatOcupado` (409).
    O replay vem antes da validação de modo/esforço: ele devolve o que foi gravado, sem reavaliar a configuração de hoje.
    """
    agora = agora_de(relogio)
    fp, idem = entrada_fingerprint(entrada), idempotency_key(entrada.chave_logica)
    with conn.transaction():
        achado = _replay(conn, origem, idem, fp)
        if achado is not None:
            return achado
        comissao = _validar_esforco(faixa_esforco, comissao_esperada_brl)
        modo = resolver_modo(
            chat_id=entrada.chat_id,
            modo_global=modo_global,
            chats_teste=chats_teste,
            persona_id=entrada.persona_id,
            modo_pedido=entrada.modo,
        )
        params = _parametros_de_insercao(origem, entrada, versoes, modo, faixa_esforco, comissao, agora)
        return _inserir(conn, params, origem, idem, fp)


def _inserir(conn: psycopg.Connection, params: dict[str, Any], origem: str, idem: str, fp: str) -> Resultado:
    try:
        with conn.transaction():  # savepoint: a violação não envenena a transação de fora, e dá para reler
            nova = conn.execute(_INSERIR, params).fetchone()
    except psycopg.errors.UniqueViolation as erro:
        if erro.diag.constraint_name != "atendimento_ativo_chat_uq":
            raise
        # perdeu a corrida para a MESMA chave (o índice do chat é o 1º a reclamar)? então é replay, não chat ocupado
        achado = _replay(conn, origem, idem, fp)
        if achado is None:
            raise ChatOcupado("chat com atendimento não encerrado") from None
        return achado
    if nova is not None:
        return Resultado(nova[0], nova[1], nova[2], nova[3], repetido=False)
    achado = _replay(conn, origem, idem, fp)  # DO NOTHING: o vencedor da mesma chave já está visível
    if achado is None:
        raise EstadoErro("conflito de chave sem linha visível")
    return achado


# --- aplicar: o único UPDATE com CAS ---------------------------------------------------------------------------------------------


class Mudancas(BaseModel):
    """Colunas que `ia_app` atualiza em `ia.atendimento` (GRANT UPDATE da 0001), menos `versao`/`atualizado_em`, que `aplicar` escreve.

    Só vai ao UPDATE o que foi informado (`model_fields_set`); `lease_ate=None` grava NULL. `ultimo_cliente_em` (0003) tem escrita própria.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    estado: Estado | None = None
    estado_conversa: dict[str, Any] | None = None
    lease_ate: AwareDatetime | None = None
    retoma_em: AwareDatetime | None = None
    assumido_em: AwareDatetime | None = None
    encerrado_em: AwareDatetime | None = None
    responsavel_antes: Annotated[str, StringConstraints(min_length=1, max_length=128)] | None = None
    chatbot_antes: Literal["ligado", "desligado", "desconhecido"] | None = None
    chatbot_estado: Literal["intocado", "desligado_pela_ia", "restaurado", "nao_confirmou"] | None = None
    ordem_consumida: Annotated[int, Field(ge=0)] | None = None
    desfecho: Desfecho | None = None
    motivo_desfecho: Codigo60 | None = None
    contexto_codigos: Annotated[tuple[Codigo40, ...], Field(max_length=10)] | None = None
    sinais_cliente: Annotated[tuple[Codigo40, ...], Field(max_length=12)] | None = None
    opt_out_em: AwareDatetime | None = None
    humano_assumiu_em: AwareDatetime | None = None
    pii_auditoria: bool | None = None
    sem_avanco: Annotated[int, Field(ge=0, le=32767)] | None = None
    corrigiveis: Annotated[int, Field(ge=0, le=32767)] | None = None
    contrapropostas: Annotated[int, Field(ge=0, le=32767)] | None = None
    confirmacoes_emitidas: Annotated[int, Field(ge=0, le=32767)] | None = None
    confirmacoes_invalidas: Annotated[int, Field(ge=0, le=32767)] | None = None
    nota_repasse_tamanho: Annotated[int, Field(ge=1, le=400)] | None = None
    turnos: Annotated[int, Field(ge=0)] | None = None
    mensagens_enviadas: Annotated[int, Field(ge=0)] | None = None
    lembretes_enviados: Annotated[int, Field(ge=0)] | None = None
    custo_modelo_brl: Annotated[Decimal, Field(ge=0)] | None = None
    custo_midia_brl: Annotated[Decimal, Field(ge=0)] | None = None
    repasse_modo: Literal["fila", "indicado"] | None = None
    repasse_consultor_ref: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,64}$")] | None = None
    repasse_nota_enviada: bool | None = None
    contrato_id: int | None = None

    @model_validator(mode="after")
    def _colunas_not_null(self) -> Mudancas:
        nulas = [c for c in _NOT_NULL if c in self.model_fields_set and getattr(self, c) is None]
        if nulas:
            raise ValueError("coluna NOT NULL sem valor: " + ", ".join(nulas))
        if self.estado_conversa is not None and octetos_como_jsonb(self.estado_conversa) > LIMITE_JSON_OCTETOS:
            raise ValueError("estado_conversa acima de 2 KB")
        return self


_NOT_NULL: Final = frozenset(
    {"estado", "estado_conversa", "chatbot_estado", "ordem_consumida", "contexto_codigos", "sinais_cliente", "sem_avanco", "corrigiveis",
     "contrapropostas", "confirmacoes_emitidas", "confirmacoes_invalidas", "turnos", "mensagens_enviadas", "lembretes_enviados",
     "custo_modelo_brl", "custo_midia_brl"}
)  # fmt: skip


def _valor_sql(nome: str, valor: Any) -> Any:
    if nome == "estado_conversa":
        return Jsonb(valor)
    if isinstance(valor, tuple):
        return list(valor)  # text[]
    return valor


def _expressoes(mudancas: Mudancas, fase: str | None) -> dict[str, sql.Composable]:
    """`coluna → expressão` do SET. Com `fase`, o `estado_conversa` sai de `jsonb_set(...)`: a fase vai no mesmo UPDATE, atômica."""
    exprs: dict[str, sql.Composable] = {}
    for nome in sorted(mudancas.model_fields_set):
        exprs[nome] = sql.SQL("%(p_estado_conversa)s::jsonb" if nome == "estado_conversa" else f"%(p_{nome})s")
    if fase is not None:
        base = exprs.get("estado_conversa", sql.SQL("estado_conversa"))
        exprs["estado_conversa"] = sql.SQL("jsonb_set({}, '{{fase}}', to_jsonb(%(p_fase)s::text))").format(base)
    return exprs


def _montar_update(
    mudancas: Mudancas, fase: str | None, de: Collection[str] | None, sem_assumido_em: bool
) -> tuple[sql.Composed, dict[str, Any]]:
    params: dict[str, Any] = {f"p_{n}": _valor_sql(n, getattr(mudancas, n)) for n in mudancas.model_fields_set}
    sets = [sql.SQL("{} = {}").format(sql.Identifier(nome), expr) for nome, expr in _expressoes(mudancas, fase).items()]
    sets.append(sql.SQL("versao = versao + 1, atualizado_em = %(agora)s"))
    onde = [sql.SQL("atendimento_id = %(atd)s AND versao = %(versao)s")]
    if fase is not None:
        params["p_fase"] = fase
    if de is not None:
        params["de"] = sorted(de)
        onde.append(sql.SQL("estado = ANY(%(de)s)"))
    if sem_assumido_em:
        onde.append(sql.SQL("assumido_em IS NULL"))
    consulta = sql.SQL("UPDATE ia.atendimento SET {} WHERE {} RETURNING versao").format(
        sql.SQL(", ").join(sets), sql.SQL(" AND ").join(onde)
    )
    return consulta, params


def _porque_falhou(conn: psycopg.Connection, atendimento_id: UUID | str, versao: int, destino: str) -> EstadoErro:
    """Só no caminho de falha: o UPDATE não casou nenhuma linha. Diz qual das três razões."""
    linha = conn.execute("SELECT estado, versao FROM ia.atendimento WHERE atendimento_id = %s", (atendimento_id,)).fetchone()
    if linha is None:
        return AtendimentoInexistente("atendimento não existe")
    if linha[1] != versao:
        return ConflitoVersao(f"versão esperada {versao}, atual {linha[1]}")
    return TransicaoInvalida(f"transição {linha[0]} -> {destino} não permitida")


def aplicar(
    conn: psycopg.Connection,
    atendimento_id: UUID | str,
    versao: int,
    mudancas: Mudancas,
    *,
    agora: datetime,
    de: Collection[str] | None = None,
    fase: str | None = None,
    sem_assumido_em: bool = False,
) -> int:
    """`UPDATE … WHERE atendimento_id = $1 AND versao = $2 [AND estado ∈ de]` com `versao + 1`; devolve a nova `versao`.

    `fase` (E0..E10) é escrita no mesmo UPDATE dentro do `estado_conversa`. Zero linhas ⇒ `ConflitoVersao` / `AtendimentoInexistente` /
    `TransicaoInvalida`. CHECK violado ⇒ `TransicaoInvalida` (com `restricao`), sem valores da linha na mensagem.
    """
    consulta, params = _montar_update(mudancas, fase, de, sem_assumido_em)
    params.update({"agora": agora, "atd": atendimento_id, "versao": versao})
    try:
        with conn.transaction():
            linha = conn.execute(consulta, params).fetchone()
    except psycopg.errors.CheckViolation as erro:
        nome = erro.diag.constraint_name or "desconhecida"
        raise TransicaoInvalida(f"viola a restrição {nome}", restricao=nome) from None
    if linha is None:
        raise _porque_falhou(conn, atendimento_id, versao, str(mudancas.estado))
    return int(linha[0])


# --- transições (invólucros finos de `aplicar`) ----------------------------------------------------------------------------------


def _lease(agora: datetime) -> datetime:
    return agora + timedelta(seconds=LEASE_TURNO_S)


def iniciar(
    conn: psycopg.Connection,
    atendimento_id: UUID | str,
    versao: int,
    *,
    chatbot_antes: str | None,
    chatbot_estado: str,
    responsavel_antes: str | None = None,
    relogio: Relogio,
) -> int:
    """`assumir_canal` concluído: `reservado → aberto`, fase E1, grava `assumido_em`, lease +5 min."""
    agora = agora_de(relogio)
    if chatbot_estado != "intocado" and chatbot_antes is None:
        raise EntradaInvalida("chatbot mexido sem o estado anterior")
    campos: dict[str, Any] = {
        "estado": "aberto",
        "assumido_em": agora,
        "lease_ate": _lease(agora),
        "chatbot_antes": chatbot_antes,
        "chatbot_estado": chatbot_estado,
    }  # fmt: skip
    if responsavel_antes is not None:
        campos["responsavel_antes"] = responsavel_antes
    return aplicar(conn, atendimento_id, versao, Mudancas(**campos), agora=agora, de={"reservado"}, fase="E1")


def aguardar_cliente(conn: psycopg.Connection, atendimento_id: UUID | str, versao: int, *, relogio: Relogio) -> int:
    agora = agora_de(relogio)
    m = Mudancas(estado="aguardando_cliente", lease_ate=_lease(agora))
    return aplicar(conn, atendimento_id, versao, m, agora=agora, de={"aberto"})


def retomar(conn: psycopg.Connection, atendimento_id: UUID | str, versao: int, *, relogio: Relogio) -> int:
    agora = agora_de(relogio)
    m = Mudancas(estado="aberto", lease_ate=_lease(agora))
    return aplicar(conn, atendimento_id, versao, m, agora=agora, de={"aguardando_cliente"})


def repassar(
    conn: psycopg.Connection,
    atendimento_id: UUID | str,
    versao: int,
    *,
    modo: str,
    motivo: str,
    consultor_ref: str | None = None,
    relogio: Relogio,
) -> int:
    """Fase 1 do repasse: `aberto|aguardando_cliente|pausado → repassando` (E10), grava `repasse_modo`. O chat continua trancado.

    A fase 2 é `encerrar(desfecho="repassado")`, quando o n8n confirma (e devolve o `consultor_ref` do modo `indicado`).
    """
    agora = agora_de(relogio)
    campos: dict[str, Any] = {
        "estado": "repassando", "repasse_modo": modo, "motivo_desfecho": motivo, "lease_ate": _lease(agora), "retoma_em": None,
    }  # fmt: skip
    if consultor_ref is not None:
        campos["repasse_consultor_ref"] = consultor_ref
    return aplicar(conn, atendimento_id, versao, Mudancas(**campos), agora=agora, de=_REPASSAVEIS, fase="E10")


def _exigir_timestamps(desfecho: str, motivo: str, opt_out_em: datetime | None, humano_assumiu_em: datetime | None) -> None:
    if desfecho == "opt_out" and opt_out_em is None:
        raise EntradaInvalida("desfecho opt_out exige opt_out_em")
    if motivo == "humano_assumiu" and humano_assumiu_em is None:
        raise EntradaInvalida("motivo humano_assumiu exige humano_assumiu_em")


def encerrar(
    conn: psycopg.Connection,
    atendimento_id: UUID | str,
    versao: int,
    *,
    desfecho: str,
    motivo: str,
    contexto_codigos: Collection[str] = (),
    opt_out_em: datetime | None = None,
    humano_assumiu_em: datetime | None = None,
    consultor_ref: str | None = None,
    relogio: Relogio,
) -> int:
    """Qualquer não-terminal → `encerrado` (lease NULL, `encerrado_em`). `opt_out` e `humano_assumiu` gravam o timestamp no MESMO UPDATE.

    Só `repassado` mantém `repasse_*`; qualquer outro desfecho os zera (o CHECK os proíbe fora de `repassando`/`repassado`), o que inclui
    o repasse simulado da sombra (`sem_venda` + `repasse_simulado`). Em sombra o CHECK recusa `vendeu` e `repassado`.
    """
    agora = agora_de(relogio)
    _exigir_timestamps(desfecho, motivo, opt_out_em, humano_assumiu_em)
    campos: dict[str, Any] = {
        "estado": "encerrado", "desfecho": desfecho, "motivo_desfecho": motivo, "contexto_codigos": tuple(contexto_codigos),
        "lease_ate": None, "retoma_em": None, "encerrado_em": agora,
    }  # fmt: skip
    if opt_out_em is not None:
        campos["opt_out_em"] = opt_out_em
    if humano_assumiu_em is not None:
        campos["humano_assumiu_em"] = humano_assumiu_em
    if desfecho != "repassado":
        campos |= {"repasse_modo": None, "repasse_consultor_ref": None, "repasse_nota_enviada": None, "nota_repasse_tamanho": None}
    elif consultor_ref is not None:
        campos["repasse_consultor_ref"] = consultor_ref
    m = Mudancas(**campos)
    return aplicar(conn, atendimento_id, versao, m, agora=agora, de=ESTADOS_NAO_TERMINAIS, sem_assumido_em=desfecho == "abortado")


def abortar(conn: psycopg.Connection, atendimento_id: UUID | str, versao: int, *, motivo: str, relogio: Relogio) -> int:
    """`reservado → encerrado(abortado)`: só enquanto `assumido_em IS NULL` (o canal nunca foi tocado)."""
    agora = agora_de(relogio)
    m = Mudancas(estado="encerrado", desfecho="abortado", motivo_desfecho=motivo, lease_ate=None, retoma_em=None, encerrado_em=agora)
    return aplicar(conn, atendimento_id, versao, m, agora=agora, de={"reservado"}, sem_assumido_em=True)
