"""Especificação declarativa de uma ferramenta (estudo F §Gateway 1 e 2) e as regras que a recusam na subida.

Uma `Especificacao` é dado, não código: nome do catálogo, semver, esquemas Pydantic de entrada e saída (`extra=forbid` em TODOS os níveis),
classe de efeito, pré-condições nomeadas, timeout, síncrona/assíncrona, idempotência, bancos e a flag que os liga. O `descrever()` é o
que entra no JSON canônico do `catalogo_hash`.

Regras fixas (o registro não sobe sem elas):
- **o modelo nunca fornece CPF, banco, valor, parcela, prazo, tabela, vendedor ou destino**: a ferramenta do modelo só recebe
  referências opacas (`REFERENCIAS_DO_MODELO`); um campo de `CAMPOS_PROIBIDOS_NA_ENTRADA` em qualquer nível é recusado em qualquer
  ferramenta, do modelo ou do código, salvo a T6 (o valor do cliente vai ao validador sem passar pelo modelo);
- a saída que vai ao modelo é a allowlist de `PROJECAO_DAS_FERRAMENTAS` (D-29): toda chave dela existe no esquema de saída;
- síncrona ≤ 3 s; ação interna não fala com serviço de fora.
"""

from __future__ import annotations

import re
import types
import typing
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal, get_args

from pydantic import BaseModel

from ia_atendimento.chave_registro import BANCOS
from ia_atendimento.contexto import PROJECAO_DAS_FERRAMENTAS
from ia_atendimento.ferramentas.erros import PRECONDICOES

ClasseEfeito = Literal["leitura", "leitura_paga", "efeito_irreversivel", "acao_interna"]
CLASSES_DE_EFEITO: Final = frozenset(get_args(ClasseEfeito))
Execucao = Literal["sincrona", "assincrona"]
Idempotencia = Literal["nenhuma", "chave_por_atendimento", "chave_por_tentativa", "chave_por_pessoa_dia"]
# Serviço de fora que a ferramenta alcança. `banco` = o do par/oferta referenciado (T5 calcula na FACTA, no 3RN ou no C6).
Servico = Literal["c360", "facta", "trn", "c6", "banco", "interno"]
SERVICOS: Final = frozenset(get_args(Servico))

REFERENCIAS_DO_MODELO: Final = frozenset(
    {"oferta_ref", "opcao_ref", "confirmacao_id", "tentativa_ref", "alvo"}
)  # `alvo` = valor|parcela|prazo
CAMPOS_PROIBIDOS_NA_ENTRADA: Final = frozenset(
    {
        "cpf",
        "cpf_hash",
        "documento",
        "banco",
        "valor",
        "valor_liberado",
        "valor_parcela",
        "valor_operacao",
        "parcela",
        "prazo",
        "tabela",
        "codigo_tabela",
        "coeficiente",
        "vendedor",
        "destino",
        "url",
        "telefone",
        "celular",
        "email",
        "nome",
    }
)
FERRAMENTAS_QUE_RECEBEM_VALOR_DO_CLIENTE: Final = frozenset({"T6"})  # o valor vai ao validador e ao cofre, nunca ao modelo (B5.3)
TIMEOUT_MAX_SINCRONA_S: Final = 3.0
TIMEOUT_MAX_S: Final = 3600.0  # 3RN até 3600 s (F §Gateway 6)
_NOME: Final = re.compile(r"^T([1-9]|1[0-5])$")
_FUNCAO: Final = re.compile(r"^[a-z][a-z0-9_]{2,39}$")
_SEMVER: Final = re.compile(r"^(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})$")
_FLAG: Final = re.compile(r"^[a-z][a-z0-9_]{1,59}$")  # nome de chave de `config_versao`


class EsquemaInvalido(ValueError):
    """A especificação (ou o catálogo) não cumpre as regras do registro: o gateway não sobe."""


def modelos_dentro(anotacao: Any) -> Iterator[type[BaseModel]]:
    """Os `BaseModel` dentro de uma anotação (`X | None`, `tuple[X, ...]`, `list[X]`, `Annotated[X, ...]`)."""
    if isinstance(anotacao, type) and issubclass(anotacao, BaseModel):
        yield anotacao
        return
    origem = typing.get_origin(anotacao)
    if origem is typing.Annotated:
        yield from modelos_dentro(get_args(anotacao)[0])
        return
    if origem is not None or isinstance(anotacao, types.UnionType):
        for argumento in get_args(anotacao):
            yield from modelos_dentro(argumento)


def _conferir_fechado(modelo: type[BaseModel], onde: str, vistos: set[type[BaseModel]] | None = None) -> None:
    vistos = set() if vistos is None else vistos
    if modelo in vistos:
        return
    vistos.add(modelo)
    if modelo.model_config.get("extra") != "forbid":
        raise EsquemaInvalido(f"{onde}: {modelo.__name__} precisa de extra=forbid")
    for campo in modelo.model_fields.values():
        for filho in modelos_dentro(campo.annotation):
            _conferir_fechado(filho, onde, vistos)


def _nomes_de_campo(modelo: type[BaseModel]) -> Iterator[str]:
    for nome, campo in modelo.model_fields.items():
        yield nome
        if campo.alias:
            yield campo.alias
        for filho in modelos_dentro(campo.annotation):
            yield from _nomes_de_campo(filho)


def _conferir_projecao(saida: type[BaseModel], projecao: Mapping[str, Any], onde: str) -> None:
    """Toda chave da allowlist existe no esquema de saída (senão a allowlist promete o que a ferramenta não devolve)."""
    for chave, regra in projecao.items():
        if chave not in saida.model_fields:
            raise EsquemaInvalido(f"{onde}: a allowlist cita {chave}, que o esquema de saída não tem")
        if isinstance(regra, Mapping):
            filhos = list(modelos_dentro(saida.model_fields[chave].annotation))
            if len(filhos) != 1:
                raise EsquemaInvalido(f"{onde}: {chave} da allowlist é objeto, o esquema de saída não")
            _conferir_projecao(filhos[0], regra, onde)


def _canonico(valor: Any) -> Any:
    """frozenset/tuple/Mapping → JSON estável (conjuntos ordenados)."""
    if isinstance(valor, (frozenset, set)):
        return sorted(_canonico(v) for v in valor)
    if isinstance(valor, Mapping):
        return {str(k): _canonico(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_canonico(v) for v in valor]
    return valor


@dataclass(frozen=True)
class Especificacao:
    """Uma ferramenta do catálogo. `nome` é o do catálogo (`T3`); no ledger vai `nome_no_ledger` (`t3`, o CHECK da 0001)."""

    nome: str
    funcao: str  # nome do estudo F (`ofertas_disponiveis`)
    versao: str  # semver; patch pode entrar no meio de um atendimento, minor/major só em atendimento novo (F §Gateway 1)
    descricao: str  # o que o MODELO lê no esquema (só nas do modelo); sem dado nem número
    classe: ClasseEfeito
    servico: Servico
    entrada: type[BaseModel]
    saida: type[BaseModel]
    do_modelo: bool = False
    precondicoes: tuple[str, ...] = ()
    timeout_s: float = TIMEOUT_MAX_SINCRONA_S
    execucao: Execucao = "sincrona"
    idempotencia: Idempotencia = "nenhuma"
    bancos: tuple[str, ...] = ()
    flag_dos_bancos: str | None = None
    usa_cpf: bool = False  # o gateway lê o CPF (memória, por chamada) e o entrega só ao executor (D18)

    def __post_init__(self) -> None:
        onde = f"ferramenta {self.nome}"
        if not _NOME.fullmatch(self.nome):
            raise EsquemaInvalido("nome fora do catálogo T1–T15")
        if not _FUNCAO.fullmatch(self.funcao):
            raise EsquemaInvalido(f"{onde}: funcao em snake_case minúsculo")
        if not _SEMVER.fullmatch(self.versao):
            raise EsquemaInvalido(f"{onde}: versao deve ser semver (1.0.0)")
        if self.classe not in CLASSES_DE_EFEITO or self.servico not in SERVICOS:
            raise EsquemaInvalido(f"{onde}: classe de efeito ou serviço fora do vocabulário")
        if (self.classe == "acao_interna") != (self.servico == "interno"):
            raise EsquemaInvalido(f"{onde}: ação interna e só ela usa o serviço interno")
        teto = TIMEOUT_MAX_SINCRONA_S if self.execucao == "sincrona" else TIMEOUT_MAX_S
        if not 0 < self.timeout_s <= teto:
            raise EsquemaInvalido(f"{onde}: timeout fora de (0, {teto}] s")
        if set(self.precondicoes) - PRECONDICOES or len(set(self.precondicoes)) != len(self.precondicoes):
            raise EsquemaInvalido(f"{onde}: pré-condição fora do catálogo ou repetida")
        if set(self.bancos) - set(BANCOS) or len(set(self.bancos)) != len(self.bancos):
            raise EsquemaInvalido(f"{onde}: banco fora de {', '.join(BANCOS)} ou repetido")
        if self.flag_dos_bancos is not None and (not self.bancos or not _FLAG.fullmatch(self.flag_dos_bancos)):
            raise EsquemaInvalido(f"{onde}: flag dos bancos só com bancos e com nome de chave de config")
        if self.do_modelo and self.execucao != "sincrona":
            raise EsquemaInvalido(f"{onde}: o modelo só pede ferramenta síncrona")
        for nome, modelo in (("entrada", self.entrada), ("saida", self.saida)):
            if not (isinstance(modelo, type) and issubclass(modelo, BaseModel)):
                raise EsquemaInvalido(f"{onde}: {nome} deve ser um BaseModel")
            _conferir_fechado(modelo, f"{onde} ({nome})")
        self._conferir_entrada(onde)
        if self.projecao is not None:
            _conferir_projecao(self.saida, self.projecao, onde)

    def _conferir_entrada(self, onde: str) -> None:
        campos = set(_nomes_de_campo(self.entrada))
        if self.nome not in FERRAMENTAS_QUE_RECEBEM_VALOR_DO_CLIENTE and (proibidos := campos & CAMPOS_PROIBIDOS_NA_ENTRADA):
            raise EsquemaInvalido(f"{onde}: a entrada não pode ter {', '.join(sorted(proibidos))} (só referências)")
        if self.do_modelo and (fora := campos - REFERENCIAS_DO_MODELO):
            raise EsquemaInvalido(f"{onde}: o modelo só passa referências; fora da lista: {', '.join(sorted(fora))}")

    @property
    def nome_no_ledger(self) -> str:
        return self.nome.lower()

    @property
    def projecao(self) -> Mapping[str, Any] | None:
        """A allowlist do que volta ao modelo (só nas do modelo). Lida a cada uso: é a MESMA de `contexto` e entra no hash."""
        return PROJECAO_DAS_FERRAMENTAS[self.nome] if self.do_modelo else None

    def descrever(self) -> dict[str, Any]:
        """O que entra no JSON canônico do `catalogo_hash` (nada de função, só dado)."""
        return {
            "nome": self.nome,
            "funcao": self.funcao,
            "versao": self.versao,
            "descricao": self.descricao,
            "classe": self.classe,
            "servico": self.servico,
            "do_modelo": self.do_modelo,
            "precondicoes": list(self.precondicoes),
            "timeout_s": self.timeout_s,
            "execucao": self.execucao,
            "idempotencia": self.idempotencia,
            "bancos": list(self.bancos),
            "flag_dos_bancos": self.flag_dos_bancos,
            "usa_cpf": self.usa_cpf,
            "entrada": self.entrada.model_json_schema(),
            "saida": self.saida.model_json_schema(),
            "projecao": _canonico(self.projecao),
        }
