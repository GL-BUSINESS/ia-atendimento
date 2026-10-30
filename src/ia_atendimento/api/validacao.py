"""Validação de entrada da API: corpo cru → JSON → modelo, sempre com `ErroApi` que leva só NOME de campo e regra (contrato 08 §1).

`validar_corpo` (estado) já tira o valor do `ValidationError`; aqui o resultado vira `422 validacao` (ou o código específico).
Chave de topo que o modelo não conhece vira `campo_desconhecido`/`campo_fora_da_allowlist` ANTES do Pydantic, para o código sair
certo e o nome ser filtrado (`nome_seguro`: uma chave estranha pode ser o próprio dado).
"""

from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, StringConstraints

from ia_atendimento.api.erros import MAX_CAMPOS_NO_DETALHE, ErroApi, nome_seguro
from ia_atendimento.estado import EntradaInvalida, validar_corpo
from ia_atendimento.mascara import mascarar
from ia_atendimento.tipos import contem_documento


def objeto_do_corpo(bruto: bytes) -> dict[str, Any]:
    """O corpo tem de ser um objeto JSON; senão `422 validacao` em `(corpo)`."""
    try:
        corpo = json.loads(bruto)
    except (ValueError, RecursionError):  # JSON profundo demais estoura a pilha do parser: também é corpo inválido, não erro interno
        corpo = None
    if not isinstance(corpo, dict):
        raise ErroApi("validacao", campo="(corpo)", detalhe={"campos": [{"campo": "(corpo)", "regra": "objeto_json_esperado"}]})
    return corpo


def exigir_chaves_conhecidas(corpo: dict[str, Any], modelo: type[BaseModel], *, codigo: str = "campo_desconhecido") -> None:
    """Chave de topo fora do modelo ⇒ `codigo` com SÓ os nomes seguros (CPF, celular, token, message_id... nunca o valor)."""
    desconhecidas = [nome for nome in corpo if nome not in modelo.model_fields]
    if desconhecidas:
        nomes = [nome_seguro(n) for n in desconhecidas][:MAX_CAMPOS_NO_DETALHE]
        raise ErroApi(codigo, campo=nomes[0], detalhe={"campos": [{"campo": n, "regra": "extra_forbidden"} for n in nomes]})


def erro_de_validacao(campos: tuple[tuple[str, str], ...]) -> ErroApi:
    lista = [{"campo": c, "regra": r} for c, r in campos[:MAX_CAMPOS_NO_DETALHE]]
    return ErroApi("validacao", campo=lista[0]["campo"] if lista else None, detalhe={"campos": lista} if lista else {})


def validar[M: BaseModel](modelo: type[M], corpo: dict[str, Any], *, codigo_de_chave_extra: str = "campo_desconhecido") -> M:
    exigir_chaves_conhecidas(corpo, modelo, codigo=codigo_de_chave_extra)
    try:
        return validar_corpo(modelo, corpo)
    except EntradaInvalida as erro:
        saida = erro_de_validacao(erro.campos)
    raise saida  # fora do `except`: sem `__context__` com o erro do Pydantic (que guarda o valor)


def rejeitar_pii(campo: str, valor: str) -> None:
    """`422 pii_no_texto_livre` (só o nome do campo) se a máscara mudaria o texto: CPF, telefone, e-mail, CEP, UUID, 8+ dígitos (§5.4)."""
    if mascarar(valor) != valor:
        raise ErroApi("pii_no_texto_livre", campo=campo)


def rejeitar_documento(campo: str, valor: str) -> None:
    """`422 pii_no_texto_livre` se a IDENTIDADE (login/e-mail do operador) leva sequência de documento ou telefone (10+ dígitos)."""
    if contem_documento(valor):
        raise ErroApi("pii_no_texto_livre", campo=campo)


def uuid_do_caminho(valor: str, campo: str) -> UUID:
    """UUID minúsculo e hifenizado; qualquer outra forma ⇒ `422 validacao` no campo (nunca o valor)."""
    try:
        achado = UUID(valor)
    except ValueError:
        achado = None
    if achado is None or str(achado) != valor:
        raise erro_de_validacao(((campo, "uuid_esperado"),))
    return achado


# login ou e-mail do operador (`por`, `operador`, `disparado_por`): sem espaço nem texto livre (documento nele: `rejeitar_documento`)
LoginOuEmail = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._@+-]{1,128}$")]
