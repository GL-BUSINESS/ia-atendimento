"""Entrada do atendimento (B1.1/B1.5): `EntradaAtendimento`, validação sem eco do valor, fingerprint (08 §4) e modo por atendimento.

Separado de `estado.py` (passava de 800 linhas); `estado` reexporta tudo daqui: `estado.EntradaAtendimento` e as demais seguem valendo."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Collection
from decimal import Decimal
from functools import cache
from inspect import isclass
from typing import Annotated, Final, Literal, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, model_validator

from ia_atendimento.estado_erros import EntradaInvalida, ModoInvalido
from ia_atendimento.tipos import LIMITE_JSON_OCTETOS, DataHora, Perfil, octetos_como_jsonb

_HEX24: Final = re.compile(r"^[0-9a-f]{24}$")
PREFIXO_FINGERPRINT: Final = b"ia-entrada/v1\n"
Modo = Literal["real", "sombra", "duble", "teste"]
Hex24 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{24}$")]
_FAIXAS_COM_COMISSAO: Final = frozenset({"alta", "muito_alta"})
_MODOS_GLOBAIS: Final = frozenset({"real", "sombra", "duble"})


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
    ultimo_cliente_em: DataHora | None = None

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
