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
import re
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, fields
from datetime import datetime, timedelta
from decimal import Decimal
from functools import cache
from inspect import isclass
from typing import Annotated, Any, Final, Literal, get_args
from uuid import UUID

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, ValidationError, model_validator

from ia_atendimento.modelos_conversa import EstadoConversa
from ia_atendimento.tipos import LIMITE_JSON_OCTETOS, Codigo40, Codigo60, Perfil, octetos_como_jsonb

LEASE_RESERVADO_S: Final = 120  # `reservado` nasce com 2 min (K §8.1)
LEASE_TURNO_S: Final = 300  # `iniciar` e cada transição renovam para +5 min
LEASE_AGUARDANDO_S: Final = 96 * 3600  # teto de quem espera o cliente sem lease calculado: fim de semana + feriado + janela DATAPREV
ENCERRA_APOS_ULTIMO_LEMBRETE_MIN: Final = 120  # H E9: encerra 2 h depois do último lembrete permitido
FOLGA_ESPERA_MIN: Final = 30
TOLERANCIA_RELOGIO: Final = timedelta(minutes=5)  # relógio de origem adiantado; além disso `ultimo_cliente_em` é recusado
_ORIGEM: Final = re.compile(r"^[a-z0-9_]{1,40}$")
_HEX24: Final = re.compile(r"^[0-9a-f]{24}$")
PREFIXO_FINGERPRINT: Final = b"ia-entrada/v1\n"
MOTIVO_DEVOLVIDO_S2: Final = "devolvido_pela_s2"  # a S2 devolve o lead: fecha `repassado` sem ter passado por `repassando`
ARTEFATOS: Final = ("roteiro", "regras", "catalogo", "motor")

Relogio = Callable[[], datetime]
Estado = Literal["reservado", "aberto", "aguardando_cliente", "pausado", "repassando", "encerrado"]
Modo = Literal["real", "sombra", "duble", "teste"]
Faixa = Literal["baixa", "media", "alta", "muito_alta"]
Desfecho = Literal[
    "sem_venda", "repassado", "sem_resposta", "expirado", "opt_out", "abortado", "vendeu", "destravou", "motivo_identificado"
]
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


class DadoRecusado(EstadoErro):
    """O banco recusou o dado (CHECK, NOT NULL, tipo). Só sqlstate e nome da restrição: a mensagem do psycopg traz a LINHA inteira."""

    def __init__(self, *, sqlstate: str | None, restricao: str | None) -> None:
        super().__init__(f"banco recusou o dado (sqlstate {sqlstate or '?'}, restrição {restricao or '?'})")
        self.sqlstate = sqlstate
        self.restricao = restricao


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
    perfil: Perfil = Field(default_factory=dict)  # rótulos curtos; sem aninhamento, float, texto livre nem dígitos de documento
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


@cache
def _nomes_do_modelo(modelo: type[BaseModel]) -> frozenset[str]:
    """Nomes de campo do modelo e dos aninhados: o que NÃO está aqui é chave de dicionário ou campo extra (dado do cliente)."""
    nomes: set[str] = set()
    pilha, vistos = [modelo], set()
    while pilha:
        atual = pilha.pop()
        if atual in vistos:
            continue
        vistos.add(atual)
        for nome, campo in atual.model_fields.items():
            nomes.add(nome)
            pilha.extend(t for t in _tipos_da_anotacao(campo.annotation) if isclass(t) and issubclass(t, BaseModel))
    return frozenset(nomes)


def _tipos_da_anotacao(anotacao: object) -> list[object]:
    achados = [anotacao]
    for arg in get_args(anotacao):
        achados.extend(_tipos_da_anotacao(arg))
    return achados


def campos_invalidos(erro: ValidationError, modelo: type[BaseModel]) -> tuple[tuple[str, str], ...]:
    """`(campo, regra)` de cada recusa. `.errors()` e `.json()` carregam o valor recusado mesmo com `hide_input_in_errors`: aqui não.

    O nome de uma chave que o cliente mandou também pode ser dado (`"123.456.789-09": "x"`): só nomes de campo do modelo saem;
    chave extra vira `(campo desconhecido)` e chave de dicionário vira `(chave)`.
    """
    conhecidos = _nomes_do_modelo(modelo)
    saida = []
    for e in erro.errors(include_input=False, include_context=False, include_url=False):
        caminho = [str(p) if isinstance(p, int) or p in conhecidos else "(chave)" for p in e["loc"]]
        if e["type"] == "extra_forbidden":
            caminho[-1] = "(campo desconhecido)"
        regra = e["msg"].removeprefix("Value error, ") if e["type"] == "value_error" else e["type"]
        saida.append((".".join(caminho) or "(corpo)", regra))
    return tuple(saida)


def validar_corpo[M: BaseModel](modelo: type[M], corpo: object) -> M:
    """Valida o corpo; se recusar, levanta `EntradaInvalida` só com nomes de campo e regra (422), sem valor e sem a causa encadeada."""
    try:
        return modelo.model_validate(corpo)
    except ValidationError as erro:
        campos = campos_invalidos(erro, modelo)
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
    return fingerprint_de_identidade(
        {
            "chat_id": entrada.chat_id,
            "chave_logica": entrada.chave_logica,
            "clt_job_id": None if entrada.clt_job_id is None else str(entrada.clt_job_id),
            "gatilho": entrada.gatilho,
            "persona_id": entrada.persona_id,
            "pessoa_id": str(entrada.pessoa_id),
            "phone_id": entrada.phone_id,
        }
    )


def fingerprint_de_identidade(identidade: dict[str, str | None]) -> str:
    """O hash do contrato 08 §4 sobre os campos da identidade (`None` e ausente são o mesmo; chaves ordenadas, sem espaço, UTF-8).

    Separado para o atendimento nascido de `POST /agendamentos` (mesma identidade `chat/chave/job/gatilho/pessoa/phone`)."""
    presentes = {k: v for k, v in identidade.items() if v is not None}
    canonico = json.dumps(presentes, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(PREFIXO_FINGERPRINT + canonico).hexdigest()


def _normalizar_chats_teste(chats: Collection[str]) -> frozenset[str]:
    """`chat_id in "texto"` é teste de SUBSTRING: uma string no lugar da lista faria um chat virar `teste`. Recusa; confere o formato."""
    if isinstance(chats, str | bytes):
        raise TypeError("chats_teste deve ser uma coleção de chat_id, não texto")
    itens = frozenset(chats)
    if not all(isinstance(c, str) and _HEX24.fullmatch(c) for c in itens):
        raise EntradaInvalida("chats_teste com id fora de 24 hex minúsculo")
    return itens


def resolver_modo(
    *, chat_id: str, modo_global: str, chats_teste: Collection[str], persona_id: str | None = None, modo_pedido: str | None = None
) -> Modo:
    """Contrato 08 §6: global `real|sombra|duble`; `teste` só com `chat_id ∈ chats_teste`; `persona_id` só em chat de teste."""
    chats_teste = _normalizar_chats_teste(chats_teste)
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


def procurar_replay(conn: psycopg.Connection, origem: str, entrada: EntradaAtendimento) -> Resultado | None:
    """Só a busca de replay do `abrir`, sem criar nada: `Resultado(repetido=True)` com o GRAVADO, `None` se é entrada nova, ou
    `ConflitoIdempotencia` (mesma chave lógica com outra identidade). A API a usa ANTES das recusas de config (contrato 08 §2: o replay
    vale mesmo com o chat ocupado e a chave desligada)."""
    return _replay(conn, origem, idempotency_key(entrada.chave_logica), entrada_fingerprint(entrada))


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
    if not _ORIGEM.fullmatch(origem):
        raise EntradaInvalida("origem fora do padrão ^[a-z0-9_]{1,40}$")
    fp, idem = entrada_fingerprint(entrada), idempotency_key(entrada.chave_logica)
    with conn.transaction():
        achado = _replay(conn, origem, idem, fp)
        if achado is not None:
            return achado
        comissao = _validar_esforco(faixa_esforco, comissao_esperada_brl)
        if entrada.ultimo_cliente_em is not None and entrada.ultimo_cliente_em > agora + TOLERANCIA_RELOGIO:
            raise EntradaInvalida("ultimo_cliente_em no futuro (mais de 5 min à frente do relógio)")
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
        nova = executar_traduzindo(conn, _INSERIR, params)
    except ChatOcupado:
        # perdeu a corrida para a MESMA chave (o índice do chat é o 1º a reclamar)? então é replay, não chat ocupado
        achado = _replay(conn, origem, idem, fp)
        if achado is None:
            raise
        return achado
    if nova is not None:
        return Resultado(nova[0], nova[1], nova[2], nova[3], repetido=False)
    achado = _replay(conn, origem, idem, fp)  # DO NOTHING: o vencedor da mesma chave já está visível
    if achado is None:
        raise EstadoErro("conflito de chave sem linha visível")
    return achado


def traduzir_erro_banco(erro: psycopg.Error, *, check_e_transicao: bool = False) -> EstadoErro:
    """Único ponto que converte erro de integridade/dado do psycopg: a mensagem original traz a LINHA inteira (inclusive o `perfil`)."""
    nome = erro.diag.constraint_name
    if isinstance(erro, psycopg.errors.UniqueViolation) and nome == "atendimento_ativo_chat_uq":
        return ChatOcupado("chat com atendimento não encerrado")
    if check_e_transicao and isinstance(erro, psycopg.errors.CheckViolation):
        return TransicaoInvalida(f"viola a restrição {nome or 'desconhecida'}", restricao=nome)
    return DadoRecusado(sqlstate=erro.sqlstate, restricao=nome)


def executar_traduzindo(conn: psycopg.Connection, consulta: Any, params: dict[str, Any], *, check_e_transicao: bool = False) -> Any:
    """Executa num savepoint (a violação não envenena a transação de fora) e devolve a 1ª linha. Erro do banco sai traduzido."""
    traduzido: EstadoErro | None = None
    try:
        with conn.transaction():
            return conn.execute(consulta, params).fetchone()
    except (psycopg.errors.IntegrityError, psycopg.errors.DataError) as erro:
        traduzido = traduzir_erro_banco(erro, check_e_transicao=check_e_transicao)
    raise traduzido  # fora do `except`: sem `__context__` com a exceção crua (e a linha dela)


# --- aplicar: o único UPDATE com CAS ---------------------------------------------------------------------------------------------


_INT4: Final = 2**31 - 1


class Mudancas(BaseModel):
    """Colunas que `ia_app` atualiza em `ia.atendimento` (GRANT UPDATE da 0001), menos `versao`/`atualizado_em`, que `aplicar` escreve.

    Só vai ao UPDATE o que foi informado (`model_fields_set`); `lease_ate=None` grava NULL. `ultimo_cliente_em` (0003) tem escrita própria.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    estado: Estado | None = None
    estado_conversa: EstadoConversa | None = None  # tipado: um dict cru burlava `extra='forbid'` e o «só códigos»
    lease_ate: AwareDatetime | None = None
    retoma_em: AwareDatetime | None = None
    assumido_em: AwareDatetime | None = None
    encerrado_em: AwareDatetime | None = None
    responsavel_antes: Annotated[str, StringConstraints(min_length=1, max_length=128)] | None = None
    chatbot_antes: Literal["ligado", "desligado", "desconhecido"] | None = None
    chatbot_estado: Literal["intocado", "desligado_pela_ia", "restaurado", "nao_confirmou"] | None = None
    ordem_consumida: Annotated[int, Field(ge=0, le=_INT4)] | None = None
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
    turnos: Annotated[int, Field(ge=0, le=_INT4)] | None = None
    mensagens_enviadas: Annotated[int, Field(ge=0, le=_INT4)] | None = None
    lembretes_enviados: Annotated[int, Field(ge=0, le=_INT4)] | None = None
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
        return self


_NOT_NULL: Final = frozenset(
    {"estado", "estado_conversa", "chatbot_estado", "ordem_consumida", "contexto_codigos", "sinais_cliente", "sem_avanco", "corrigiveis",
     "contrapropostas", "confirmacoes_emitidas", "confirmacoes_invalidas", "turnos", "mensagens_enviadas", "lembretes_enviados",
     "custo_modelo_brl", "custo_midia_brl"}
)  # fmt: skip


def _valor_sql(nome: str, valor: Any) -> Any:
    if nome == "estado_conversa":
        return Jsonb(valor.para_json())
    if isinstance(valor, tuple):
        return list(valor)  # text[]
    return valor


def _expressoes(mudancas: Mudancas, fase: str | None, lease_so_cresce: bool = False) -> dict[str, sql.Composable]:
    """`coluna → expressão` do SET. Com `fase`, o `estado_conversa` sai de `jsonb_set(...)`: a fase vai no mesmo UPDATE, atômica."""
    exprs: dict[str, sql.Composable] = {}
    for nome in sorted(mudancas.model_fields_set):
        exprs[nome] = sql.SQL("%(p_estado_conversa)s::jsonb" if nome == "estado_conversa" else f"%(p_{nome})s")
    if lease_so_cresce and "lease_ate" in exprs:
        exprs["lease_ate"] = sql.SQL("greatest(lease_ate, %(p_lease_ate)s)")  # nunca encurta (quem espera o cliente tem lease de dias)
    if fase is not None:
        base = exprs.get("estado_conversa", sql.SQL("estado_conversa"))
        exprs["estado_conversa"] = sql.SQL("jsonb_set({}, '{{fase}}', to_jsonb(%(p_fase)s::text))").format(base)
    return exprs


def _montar_update(
    mudancas: Mudancas, fase: str | None, de: Collection[str] | None, sem_assumido_em: bool, lease_so_cresce: bool
) -> tuple[sql.Composed, dict[str, Any]]:
    params: dict[str, Any] = {f"p_{n}": _valor_sql(n, getattr(mudancas, n)) for n in mudancas.model_fields_set}
    sets = [sql.SQL("{} = {}").format(sql.Identifier(nome), expr) for nome, expr in _expressoes(mudancas, fase, lease_so_cresce).items()]
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
    de: Collection[str] = ESTADOS_NAO_TERMINAIS,
    fase: str | None = None,
    sem_assumido_em: bool = False,
    lease_so_cresce: bool = False,
) -> int:
    """`UPDATE … WHERE atendimento_id = $1 AND versao = $2 AND estado ∈ de` com `versao + 1`; devolve a nova `versao`.

    `de` tem por padrão os estados NÃO terminais: `encerrado` é absorvente (o trigger da 0003 também o garante no banco).

    `fase` (E0..E10) é escrita no mesmo UPDATE dentro do `estado_conversa`. Zero linhas ⇒ `ConflitoVersao` / `AtendimentoInexistente` /
    `TransicaoInvalida`. CHECK violado ⇒ `TransicaoInvalida` (com `restricao`); NOT NULL/tipo ⇒ `DadoRecusado`; sem valores da linha.
    """
    if agora.tzinfo is None:
        raise ValueError("`agora` exige datetime com fuso")
    consulta, params = _montar_update(mudancas, fase, de, sem_assumido_em, lease_so_cresce)
    params.update({"agora": agora, "atd": atendimento_id, "versao": versao})
    linha = executar_traduzindo(conn, consulta, params, check_e_transicao=True)
    if linha is None:
        raise _porque_falhou(conn, atendimento_id, versao, str(mudancas.estado))
    return int(linha[0])


# --- transições (invólucros finos de `aplicar`) ----------------------------------------------------------------------------------


def _lease(agora: datetime, segundos: int = LEASE_TURNO_S) -> datetime:
    return agora + timedelta(seconds=segundos)


def _mudancas(**campos: Any) -> Mudancas:
    """`Mudancas` por `validar_corpo`: recusa sai como `EntradaInvalida` (só nomes), sem o `ValidationError` cru que guarda o valor."""
    return validar_corpo(Mudancas, campos)


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
    return aplicar(conn, atendimento_id, versao, _mudancas(**campos), agora=agora, de={"reservado"}, fase="E1")


def lease_de_espera(
    agora: datetime,
    *,
    intervalos_min: Sequence[int],
    proxima_janela: Callable[[datetime], datetime],
    lembretes_max: int = 2,
    encerra_apos_min: int = ENCERRA_APOS_ULTIMO_LEMBRETE_MIN,
    folga_min: int = FOLGA_ESPERA_MIN,
) -> datetime:
    """Lease de quem espera o cliente: até o ENCERRAMENTO por vácuo (+ folga), seguindo a linha do tempo dos lembretes.

    Cada lembrete sai `intervalos_min[n]` depois do anterior e, se cair fora da janela de mensagem (08–20 seg–sáb, feriado, DATAPREV), é
    ADIADO para a próxima abertura (`proxima_janela`, a do `Calendario` da B1.3; `intervalos_min` = `lembretes_intervalos_min`). O alarme do
    lembrete não leva lock do chat, então o reaper de lease só enxerga o `lease_ate`: se ele vencer antes disso, o lead que espera como
    planejado é repassado e o lembrete agendado fica órfão.
    """
    if not intervalos_min or lembretes_max < 1:
        raise EntradaInvalida("intervalos_min vazio ou lembretes_max < 1")
    momento = agora
    for n in range(lembretes_max):
        momento = proxima_janela(momento + timedelta(minutes=intervalos_min[min(n, len(intervalos_min) - 1)]))
    return momento + timedelta(minutes=encerra_apos_min + folga_min)


def aguardar_cliente(
    conn: psycopg.Connection, atendimento_id: UUID | str, versao: int, *, relogio: Relogio, lease_ate: datetime | None = None
) -> int:
    """`aberto → aguardando_cliente`. O lease cobre a espera (`lease_de_espera`, que o chamador calcula com o calendário); sem ele,
    vale o teto de `LEASE_AGUARDANDO_S` (96 h). Nunca os 5 min do turno: o cliente leva horas."""
    agora = agora_de(relogio)
    if lease_ate is not None and lease_ate <= agora:
        raise EntradaInvalida("lease_ate de espera no passado")
    m = _mudancas(estado="aguardando_cliente", lease_ate=lease_ate or _lease(agora, LEASE_AGUARDANDO_S))
    return aplicar(conn, atendimento_id, versao, m, agora=agora, de={"aberto"})


def renovar_lease(
    conn: psycopg.Connection, atendimento_id: UUID | str, versao: int, *, relogio: Relogio, segundos: int = LEASE_TURNO_S
) -> int:
    """Renova a posse sem mudar de estado (turno longo, acima de 5 min). Transição com CAS: `versao + 1`. NUNCA encurta (`greatest`).
    `pausado` e `reservado` têm
    lease ligado a `retoma_em` e não passam por aqui; quem espera o cliente renova com `segundos=LEASE_AGUARDANDO_S`."""
    agora = agora_de(relogio)
    de = {"aberto", "aguardando_cliente", "repassando"}
    m = _mudancas(lease_ate=_lease(agora, segundos))
    return aplicar(conn, atendimento_id, versao, m, agora=agora, de=de, lease_so_cresce=True)


def retomar(conn: psycopg.Connection, atendimento_id: UUID | str, versao: int, *, relogio: Relogio) -> int:
    agora = agora_de(relogio)
    m = _mudancas(estado="aberto", lease_ate=_lease(agora))
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
    return aplicar(conn, atendimento_id, versao, _mudancas(**campos), agora=agora, de=_REPASSAVEIS, fase="E10")


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
    # `repassado` só sai de `repassando` (repasse em duas fases); a devolução da S2 é a única exceção (nunca passou pela fase 1)
    de = {"repassando"} if desfecho == "repassado" and motivo != MOTIVO_DEVOLVIDO_S2 else ESTADOS_NAO_TERMINAIS
    return aplicar(conn, atendimento_id, versao, _mudancas(**campos), agora=agora, de=de, sem_assumido_em=desfecho == "abortado")


def abortar(conn: psycopg.Connection, atendimento_id: UUID | str, versao: int, *, motivo: str, relogio: Relogio) -> int:
    """`reservado → encerrado(abortado)`: só enquanto `assumido_em IS NULL` (o canal nunca foi tocado)."""
    agora = agora_de(relogio)
    m = _mudancas(estado="encerrado", desfecho="abortado", motivo_desfecho=motivo, lease_ate=None, retoma_em=None, encerrado_em=agora)
    return aplicar(conn, atendimento_id, versao, m, agora=agora, de={"reservado"}, sem_assumido_em=True)
