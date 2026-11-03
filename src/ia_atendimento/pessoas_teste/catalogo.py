"""Catálogo sintético das pessoas de teste (B2.4): uma por `persona_id` da F3 (60 H + 24 P-M), com o que T1/T3 precisam ler.

O arquivo `pessoas.json` é GERADO de `tests/corpus/` por `scripts/gerar_pessoas_teste.py` (e conferido por `--verificar` no `check.sh`):
persona_id, CPF `000.000.0nn-dd`, nome e telefone são os do corpus; `pessoa_id` é fixo e legível (`00000000-0000-7000-8000-<n>`, o prefixo
`00000000-` é o que a varredura do corpus reconhece como sintético); as ofertas saem do perfil da persona e da grade de coeficientes do
dublê da FACTA (tabela 115716). Nada aqui é de cliente: um CPF desta faixa nunca pertence a uma pessoa.

Várias personas dividem o mesmo CPF quando dividem a persona do dublê (P01, P34, P57 e P-M01 usam o `aprovado-24`): o CPF é a chave do
dublê da FACTA (stubs por CPF), o `pessoa_id` é a chave do 360. Quem lê T1/T3 em `duble|teste` pergunta por `pessoa_id`, então não há
ambiguidade; a oferta (valor, prazo) é por persona.

`hash_canonico` é o hash que o `bancos-duble` guarda no seu instantâneo (`personas/pessoas_teste.sha256`): o teste de consistência entre
os repositórios compara os dois.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from functools import cache
from pathlib import Path
from typing import Annotated, Any, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from ia_atendimento.pessoas_teste.arquivo import PessoasTesteFixas, PessoasTesteInvalidas

ARQUIVO: Final = Path(__file__).with_name("pessoas.json")
ARQUIVO_HASH: Final = Path(__file__).with_name("pessoas.sha256")
FAIXA_DO_PESSOA_ID: Final = "00000000-0000-7000-8000-"
_PERSONA_ID: Final = re.compile(r"^(P(0[1-9]|[1-5][0-9]|60)|P-M(0[1-9]|1[0-9]|2[0-4]))$")
_CPF_FORMATADO: Final = re.compile(r"^000\.000\.0[0-9]{2}-[0-9]{2}$")
_CHAT_HEX24: Final = re.compile(r"^[0-9a-f]{24}$")


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EconomiaDeTeste(_Modelo):
    """`PayloadEconomicoCltV1` da oferta: valores como TEXTO decimal, do jeito que o 360 os entrega."""

    valor_liberado: str
    valor_parcela: str
    prazo_meses: Annotated[int, Field(ge=12, le=96)]
    tabela_identificador: str
    convenio: str
    coeficiente_financeiro: str
    coef_valor: str  # grandeza de ordenação do fallback (T3); nunca chega ao modelo


class ParDeTeste(_Modelo):
    banco: Annotated[str, StringConstraints(pattern=r"^[A-Z0-9_]{2,32}$")]
    produto: Annotated[str, StringConstraints(pattern=r"^[A-Z0-9_]{2,32}$")]
    oferta_id: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,19}$")] | None  # None = par sem oferta ativa
    economia: EconomiaDeTeste | None

    @model_validator(mode="after")
    def _oferta_e_economia_juntas(self) -> ParDeTeste:
        if (self.oferta_id is None) != (self.economia is None):
            raise ValueError("oferta_id e economia vêm juntos (par sem oferta: os dois nulos)")
        return self


class PessoaDeTeste(_Modelo):
    persona_id: str
    pessoa_id: UUID
    cpf: str
    nome: str
    telefone: Annotated[str, StringConstraints(pattern=r"^[0-9]{12,13}$")]
    duble: str | None  # persona do dublê da FACTA a que o CPF pertence (None = sem stub: persona «sem FACTA»)
    pares: tuple[ParDeTeste, ...]

    @model_validator(mode="after")
    def _coerente(self) -> PessoaDeTeste:
        if not _PERSONA_ID.match(self.persona_id):
            raise ValueError(f"persona_id fora do padrão da F3: {self.persona_id!r}")
        if not str(self.pessoa_id).startswith(FAIXA_DO_PESSOA_ID) or self.pessoa_id.version != 7:
            raise ValueError("pessoa_id fora da faixa sintética 00000000-0000-7000-8000-…")
        if not _CPF_FORMATADO.match(self.cpf) or not _dv_confere(self.cpf):
            raise ValueError("CPF fora da faixa 000.000.0nn-dd ou com dígito verificador errado")
        if len({(p.banco, p.produto) for p in self.pares}) != len(self.pares):
            raise ValueError("par (banco, produto) repetido")
        return self

    @property
    def cpf_digitos(self) -> str:
        return re.sub(r"\D", "", self.cpf)

    @property
    def primeiro_nome(self) -> str:
        return self.nome.split()[0]


class CatalogoPessoasTeste(_Modelo):
    versao: int
    fonte: str
    pessoas: tuple[PessoaDeTeste, ...]

    @model_validator(mode="after")
    def _unicidade(self) -> CatalogoPessoasTeste:
        for rotulo, valores in (
            ("persona_id", [p.persona_id for p in self.pessoas]),
            ("pessoa_id", [p.pessoa_id for p in self.pessoas]),
            ("oferta_id", [o.oferta_id for p in self.pessoas for o in p.pares if o.oferta_id]),
        ):
            if len(set(valores)) != len(valores):
                raise ValueError(f"{rotulo} repetido no catálogo")
        return self

    def por_persona(self, persona_id: str) -> PessoaDeTeste | None:
        return next((p for p in self.pessoas if p.persona_id == persona_id), None)

    def por_pessoa(self, pessoa_id: UUID | str) -> PessoaDeTeste | None:
        alvo = pessoa_id if isinstance(pessoa_id, UUID) else _como_uuid(pessoa_id)
        return None if alvo is None else next((p for p in self.pessoas if p.pessoa_id == alvo), None)

    def pessoa_ids(self) -> frozenset[UUID]:
        return frozenset(p.pessoa_id for p in self.pessoas)

    def como_pessoas_teste(self, chats: dict[str, str]) -> PessoasTesteFixas:
        """`PessoasTeste` da API: todas as pessoas do catálogo e os chats de teste ligados (`chat_id` 24 hex → `persona_id`)."""
        ligados: dict[str, UUID] = {}
        for chat, persona in chats.items():
            pessoa = self.por_persona(persona)
            if pessoa is None or not _CHAT_HEX24.fullmatch(chat):
                raise PessoasTesteInvalidas("pessoas_teste: chat de 24 hex minúsculo ligado a uma persona do catálogo")
            ligados[chat] = pessoa.pessoa_id
        return PessoasTesteFixas(self.pessoa_ids(), ligados)

    def conteudo(self) -> list[dict[str, Any]]:
        return [p.model_dump(mode="json") for p in self.pessoas]


def _como_uuid(texto: str) -> UUID | None:
    try:
        return UUID(texto)
    except ValueError:
        return None


def _dv_confere(cpf_formatado: str) -> bool:
    d = [int(c) for c in cpf_formatado if c.isdigit()]
    for n in (9, 10):
        soma = sum(v * p for v, p in zip(d[:n], range(n + 1, 1, -1), strict=True))
        if (soma * 10) % 11 % 10 != d[n]:
            return False
    return True


def hash_canonico(pessoas: Iterable[dict[str, Any]]) -> str:
    """sha256 do JSON canônico (chaves ordenadas, sem espaço, UTF-8) da lista de pessoas.

    O `bancos-duble` calcula o MESMO hash sobre o seu YAML (`personas/pessoas_teste.yaml`).
    """
    texto = json.dumps(list(pessoas), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def ler_hash_gravado(caminho: Path = ARQUIVO_HASH) -> str:
    return caminho.read_text(encoding="utf-8").split()[0]


def carregar_catalogo(caminho: Path | str | None = None) -> CatalogoPessoasTeste:
    """Lê e valida `pessoas.json`. Arquivo ausente, JSON ruim ou forma errada = `PessoasTesteInvalidas` (a mensagem não cita conteúdo)."""
    try:
        dados = json.loads(Path(caminho or ARQUIVO).read_text(encoding="utf-8"))
        return CatalogoPessoasTeste.model_validate(dados)
    except (OSError, ValueError):  # `ValidationError` do Pydantic é um `ValueError`
        raise PessoasTesteInvalidas("pessoas_teste: catálogo ausente ou fora da forma esperada") from None


@cache
def catalogo_padrao() -> CatalogoPessoasTeste:
    """O catálogo embalado com o pacote (lido uma vez)."""
    return carregar_catalogo()
