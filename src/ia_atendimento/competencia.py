"""Competência da oferta (DEC-PIA-005 e DEC-PIA-014, 20/11): a T3 só apresenta oferta gerada DEPOIS da última virada da competência.

A virada é às 00:00 do dia 20 (São Paulo). Depois dela, a margem da competência anterior não vale mais e a calculadora grátis da FACTA não
lê a margem nova: refazer a conta exige consulta paga, fora do MVP. Então oferta criada antes da última virada não é candidata, nem
recalculada: o lead sai da lista ou vai ao vendedor. Na semana do dia 20 o volume de candidatos cai; o fluxo normal gera ofertas novas.

Puro: recebe o instante de um `Relogio` (com fuso) e a oferta crua do `pessoas:propostas` (`criada_em`, `estado`, `valid_until`, RFC 3339).
Quem decide «apresentar ou não» na T3 (B5.2) chama `oferta_apresentavel`; quem monta a `SaidaT3` usa `status_para_t3`.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, time
from typing import Any, Final, Literal

from ia_atendimento.calendario import FUSO

DIA_DA_VIRADA: Final = 20
HORA_DA_VIRADA: Final = time(0, 0)


def _utc(instante: datetime) -> datetime:
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("a competência só aceita instante com fuso (venha de um Relogio)")
    return instante.astimezone(UTC)


def virada_vigente(agora: datetime) -> datetime:
    """A última virada (dia 20, 00:00 de São Paulo) que já aconteceu até `agora`, em UTC."""
    local = _utc(agora).astimezone(FUSO)
    ano, mes = local.year, local.month
    if local.day < DIA_DA_VIRADA:
        ano, mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    return datetime(ano, mes, DIA_DA_VIRADA, HORA_DA_VIRADA.hour, HORA_DA_VIRADA.minute, tzinfo=FUSO).astimezone(UTC)


def da_competencia_vigente(criada_em: datetime, agora: datetime) -> bool:
    """`True` se a oferta foi gerada na competência vigente (em ou depois da última virada)."""
    return _utc(criada_em) >= virada_vigente(agora)


def _instante(valor: Any) -> datetime | None:
    if not isinstance(valor, str):
        return None
    try:
        instante = datetime.fromisoformat(valor)
    except ValueError:
        return None
    return instante if instante.tzinfo is not None and instante.utcoffset() is not None else None


def oferta_apresentavel(oferta: Mapping[str, Any] | None, agora: datetime) -> bool:
    """Ativa, dentro do `valid_until` e da competência vigente. Qualquer campo ausente ou fora da forma = não apresenta (fail-closed)."""
    if not isinstance(oferta, Mapping) or oferta.get("estado") != "ativa":
        return False
    criada_em, valida_ate = _instante(oferta.get("criada_em")), _instante(oferta.get("valid_until"))
    if criada_em is None or valida_ate is None:
        return False
    return da_competencia_vigente(criada_em, agora) and _utc(agora) < _utc(valida_ate)


def status_para_t3(oferta: Mapping[str, Any] | None, agora: datetime) -> Literal["ativa", "vencida", "sem_oferta"]:
    """`sem_oferta` sem oferta; `vencida` para oferta que existe mas não se apresenta (competência anterior, prazo vencido, forma ruim);
    `ativa` só quando `oferta_apresentavel`. Com `vencida`/`sem_oferta` a T3 não leva valor nenhum ao código nem ao modelo."""
    if oferta is None:
        return "sem_oferta"
    return "ativa" if oferta_apresentavel(oferta, agora) else "vencida"
