"""Saída das ferramentas (estudo F §Gateway 7; D-29): reconstruída pelo esquema, varrida por conteúdo e, ao modelo, só pela allowlist.

1. `reconstruir`: só as chaves do esquema de saída (em todos os níveis) entram; o resto (CPF, `coef_valor`, comissão, tabela, link, motivo
   cru do banco…) é descartado NA CHEGADA, antes da validação. O que sobra tem de cumprir o esquema, senão `DESCONHECIDO` sem eco.
2. `para_projetar`: o corpo que a projeção (`proteger_retorno`, a mesma allowlist do contexto) recebe: URL vira `{{link}}` e texto que a
   máscara de PII troca some.
3. Dinheiro ao cliente sai formatado pelo código (`formatar_brl`), nunca pelo modelo.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, Final

from pydantic import BaseModel, ValidationError

from ia_atendimento.ferramentas.erros import ErroDeFerramenta
from ia_atendimento.ferramentas.especificacao import Especificacao, modelos_dentro
from ia_atendimento.mascara import mascarar
from ia_atendimento.protecao import ha_link

PLACEHOLDER_DO_LINK: Final = "{{link}}"
CHAVES_DE_REFERENCIA: Final = frozenset({"oferta_ref", "opcao_ref"})  # as chaves que `contexto._ALIAS_DE_REF` troca por apelido
_CENTAVO: Final = Decimal("0.01")


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


def reconstruir(spec: Especificacao, bruto: Any) -> BaseModel:
    if not isinstance(bruto, Mapping):
        raise ErroDeFerramenta("DESCONHECIDO")
    try:
        return spec.saida.model_validate(_filtrar(spec.saida, bruto))
    except ValidationError:
        pass
    raise ErroDeFerramenta("DESCONHECIDO")  # fora do `except`: sem causa nem contexto (que citariam o valor)


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
