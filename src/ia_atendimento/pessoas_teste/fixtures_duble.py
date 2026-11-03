"""Os arquivos `fixtures/duble/*.json` (B2.4): forma medida de `Oferta` (360), `/3rn/calcular` e `/c6/oferta/simular`.

SEM WireMock e SEM chamada real. São o que o gateway de ferramentas devolve em `duble|teste` quando a F3 (P13, P14) ou o ensaio pedem T5 de
outro banco: sem elas a F3 chamaria o C6 de verdade (1 req/s, custo) e o 3RN (fila da AJIN). Cada arquivo é validado pelas formas de
`formas.py` ao carregar; `scripts/gerar_pessoas_teste.py` os gera do catálogo, então a oferta de T3 e a simulação de T5 da mesma persona
nunca divergem.

`cpf` nas respostas de banco é ECO do pedido: o arquivo traz `00000000000` e `servir_*` o troca pelo CPF consultado (11 dígitos).
O arquivo mora em `fixtures/duble/` do checkout e, no pacote instalado, em `ia_atendimento/fixtures/duble/` (o wheel o leva, como as
migrações).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ia_atendimento.pessoas_teste.arquivo import PessoasTesteInvalidas
from ia_atendimento.pessoas_teste.fonte import MODOS_COM_FIXTURES, ForaDoModoDeTeste
from ia_atendimento.pessoas_teste.formas import (
    C6Simular,
    Calcular3rnCalculado,
    Calcular3rnSemCalculo,
    Instante,
    ResultadoPropostasPessoa,
    ResumosPessoas,
)

NOMES: Final = ("cliente360_oferta.json", "3rn_calcular.json", "c6_simular.json")
CPF_ECO: Final = "00000000000"
_RAIZ: Final = Path(__file__).resolve().parents[3]


def diretorio_padrao() -> Path:
    for candidato in (_RAIZ / "fixtures" / "duble", Path(__file__).resolve().parents[1] / "fixtures" / "duble"):
        if candidato.is_dir():
            return candidato
    raise PessoasTesteInvalidas("fixtures/duble não encontrada (checkout ou pacote instalado com fixtures/)")


class _Fechado(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Relativo(_Fechado):
    valid_until_s: Annotated[int, Field(gt=0)]
    regra: str


class CasoCliente360(_Fechado):
    resumo: ResumosPessoas
    propostas: ResultadoPropostasPessoa


class ArquivoCliente360(_Fechado):
    versao: int
    fonte: str
    relativo: Relativo
    agora_referencia: Instante
    casos: dict[str, CasoCliente360]


class Caso3rn(_Fechado):
    http: int
    corpo: Calcular3rnCalculado | Calcular3rnSemCalculo


class CasoC6(_Fechado):
    http: int
    corpo: C6Simular


class _ArquivoDeBanco(_Fechado):
    versao: int
    fonte: str
    por_persona: dict[str, str]
    eco_cpf: str

    @model_validator(mode="after")
    def _ecoa_o_cpf_zerado(self) -> _ArquivoDeBanco:
        if not self.eco_cpf:
            raise ValueError("`eco_cpf` explica que `cpf` ecoa o pedido")
        return self


class Arquivo3rn(_ArquivoDeBanco):
    casos: dict[str, Caso3rn]
    padrao: str

    @model_validator(mode="after")
    def _referencias(self) -> Arquivo3rn:
        if not {self.padrao, *self.por_persona.values()} <= set(self.casos):
            raise ValueError("`padrao` e `por_persona` apontam para casos que existem")
        return self


class ArquivoC6(_ArquivoDeBanco):
    casos: dict[str, CasoC6]
    padrao: str

    @model_validator(mode="after")
    def _referencias(self) -> ArquivoC6:
        if not {self.padrao, *self.por_persona.values()} <= set(self.casos):
            raise ValueError("`padrao` e `por_persona` apontam para casos que existem")
        return self


class FixturesDuble(_Fechado):
    cliente360: ArquivoCliente360
    tres_rn: Arquivo3rn
    c6: ArquivoC6

    def calcular_3rn(self, persona_id: str, cpf: str, modo: str) -> tuple[int, dict[str, Any]]:
        """`POST /3rn/calcular` da persona: o caso dela (P14: sem simulação) ou o padrão (calculado). (HTTP, corpo), `cpf` = o do pedido."""
        return _servir(self.tres_rn, persona_id, cpf, modo)

    def simular_c6(self, persona_id: str, cpf: str, modo: str) -> tuple[int, dict[str, Any]]:
        """`POST /c6/oferta/simular` da persona (P13: simulado com a oferta do T3) ou o padrão (sem oferta)."""
        return _servir(self.c6, persona_id, cpf, modo)


def _servir(arquivo: Arquivo3rn | ArquivoC6, persona_id: str, cpf: str, modo: str) -> tuple[int, dict[str, Any]]:
    if modo not in MODOS_COM_FIXTURES:
        raise ForaDoModoDeTeste(f"fixtures de bancos só valem em duble|teste (modo pedido: {modo!r})")
    if len(cpf) != 11 or not cpf.isdigit():
        raise ValueError("cpf com 11 dígitos")
    caso = arquivo.casos[arquivo.por_persona.get(persona_id, arquivo.padrao)]
    corpo = caso.corpo.model_dump(mode="json", exclude_unset=True)
    return caso.http, {**corpo, "cpf": cpf}


def carregar_fixtures_duble(diretorio: Path | str | None = None) -> FixturesDuble:
    base = Path(diretorio) if diretorio else diretorio_padrao()
    try:
        c360, tres, c6 = (json.loads((base / nome).read_text(encoding="utf-8")) for nome in NOMES)
        return FixturesDuble(
            cliente360=ArquivoCliente360.model_validate(c360), tres_rn=Arquivo3rn.model_validate(tres), c6=ArquivoC6.model_validate(c6)
        )
    except (OSError, ValueError):  # `ValidationError` do Pydantic é um `ValueError`
        raise PessoasTesteInvalidas("fixtures/duble ausente ou fora da forma esperada") from None
