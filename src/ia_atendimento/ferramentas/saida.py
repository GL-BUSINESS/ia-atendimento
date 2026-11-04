"""Saída das ferramentas (estudo F §Gateway 7; D-29): reconstruída pelo esquema, varrida por conteúdo e, ao modelo, só pela allowlist.

1. `reconstruir`: só as chaves do esquema de saída (em todos os níveis) entram; o resto (CPF, `coef_valor`, comissão, tabela, link, motivo
   cru do banco…) é descartado NA CHEGADA, antes da validação. O que sobra tem de cumprir o esquema, senão `DESCONHECIDO` sem eco. E todo
   texto que sobra é varrido por conteúdo (`_tem_pii`): CPF, telefone, e-mail, CEP ou 11 dígitos com forma de CPF num campo permitido
   (`primeiro_nome`, `oferta_ref`, `ref_externa`…) também é `DESCONHECIDO`, porque `dados` fica no lado do código e a B1.6 o grava (D18;
   revisão B5.1, M-6). Número longo sem forma de documento (`[NUMERO]`, a proposta do banco) e uuid passam.
2. `para_projetar`: o corpo que a projeção (`proteger_retorno`, a mesma allowlist do contexto) recebe: URL vira `{{link}}` e texto que a
   máscara de PII troca some.
3. Dinheiro ao cliente sai formatado pelo código (`formatar_brl`), nunca pelo modelo.
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Iterator, Mapping
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, Final

from pydantic import BaseModel, ValidationError

from ia_atendimento.ferramentas.erros import ErroDeFerramenta
from ia_atendimento.ferramentas.especificacao import Especificacao, modelos_dentro
from ia_atendimento.mascara import CEP, CPF, EMAIL, NOME, TELEFONE, mascarar
from ia_atendimento.protecao import ha_link

PLACEHOLDER_DO_LINK: Final = "{{link}}"
CHAVES_DE_REFERENCIA: Final = frozenset({"oferta_ref", "opcao_ref"})  # as chaves que `contexto._ALIAS_DE_REF` troca por apelido
_CENTAVO: Final = Decimal("0.01")
_UUID: Final = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
# 11 dígitos com a forma do CPF, com ou sem pontuação, mesmo com DV inválido (`00000001234` a máscara chama de `[NUMERO]`)
_FORMA_DE_CPF: Final = re.compile(r"(?<![0-9])[0-9]{3}[.\s]?[0-9]{3}[.\s]?[0-9]{3}[-.\s/]?[0-9]{2}(?![0-9])")
_MARCAS_DE_PII: Final = (CPF, TELEFONE, EMAIL, CEP, NOME)


def _filtrar(modelo: type[BaseModel], bruto: Mapping[str, Any]) -> dict[str, Any]:
    saida: dict[str, Any] = {}
    for nome, campo in modelo.model_fields.items():
        if nome not in bruto:
            continue
        valor, filhos = bruto[nome], list(modelos_dentro(campo.annotation))
        if len(filhos) == 1 and isinstance(valor, Mapping):
            valor = _filtrar(filhos[0], valor)
        elif len(filhos) == 1 and isinstance(valor, (list, tuple)):
            valor = [_filtrar(filhos[0], item) if isinstance(item, Mapping) else item for item in valor]
        saida[nome] = valor
    return saida


def _textos(valor: Any) -> Iterator[str]:
    """Todo `str` do modelo validado (em qualquer nível). Decimal e datetime não são texto: o ISO da data não é documento."""
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, BaseModel):
        for nome in type(valor).model_fields:
            yield from _textos(getattr(valor, nome))
    elif isinstance(valor, (list, tuple)):
        for item in valor:
            yield from _textos(item)


def _tem_pii(texto: str) -> bool:
    neutro = _UUID.sub("u", texto)  # o uuid do id real não é PII (a máscara o trocaria por `[UUID]`)
    mascarado = mascarar(neutro)
    return any(marca in mascarado for marca in _MARCAS_DE_PII) or _FORMA_DE_CPF.search(neutro) is not None


def reconstruir(spec: Especificacao, bruto: Any) -> BaseModel:
    if not isinstance(bruto, Mapping):
        raise ErroDeFerramenta("DESCONHECIDO")
    dados: BaseModel | None = None
    with contextlib.suppress(ValidationError):
        dados = spec.saida.model_validate(_filtrar(spec.saida, bruto))
    if dados is None or any(_tem_pii(texto) for texto in _textos(dados)):
        raise ErroDeFerramenta("DESCONHECIDO")  # fora do `except`: sem causa nem contexto (que citariam o valor)
    return dados


def _varrer(valor: Any, chave: str = "") -> tuple[bool, Any]:
    if isinstance(valor, str):
        if ha_link(valor) or "://" in valor:
            return True, PLACEHOLDER_DO_LINK
        if chave in CHAVES_DE_REFERENCIA:  # id real (uuid): a projeção o troca pelo apelido; a máscara o apagaria
            return True, valor
        return (mascarar(valor) == valor), valor
    if isinstance(valor, Mapping):
        return True, {k: v for k, (ok, v) in ((k, _varrer(v, k)) for k, v in valor.items()) if ok}
    if isinstance(valor, (list, tuple)):
        return True, [v for ok, v in (_varrer(item, chave) for item in valor) if ok]
    return True, valor


def para_projetar(dados: BaseModel) -> dict[str, Any]:
    """Sem os padrões (`false`, listas vazias): ao modelo só o que diz algo."""
    _, corpo = _varrer(dados.model_dump(mode="json", exclude_defaults=True))
    return corpo


def formatar_brl(valor: Decimal) -> str:
    """`Decimal("2400")` → `R$ 2.400,00` (arredonda ao centavo, meio-par). Negativo não é valor de oferta."""
    if valor < 0:
        raise ValueError("valor negativo")
    inteiro, centavos = f"{valor.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN):.2f}".split(".")
    return f"R$ {int(inteiro):,}".replace(",", ".") + f",{centavos}"
