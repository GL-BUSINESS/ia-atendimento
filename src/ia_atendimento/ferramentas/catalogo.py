"""Catálogo MVP versionado (estudo F §Gateway 1): as especificações, o `catalogo_hash` e o histórico de `numero` que o amarra.

`catalogo_hash` = sha256 do JSON canônico (`sort_keys`, sem espaço, UTF-8) das especificações ordenadas por nome. O histórico mora em
`catalogo_versoes.json` (no git, ao lado deste módulo): cada `numero` novo traz o hash novo. `conferir_versao` FALHA se o hash do código não
for o do último `numero`, e o teste `test_catalogo_vigente_tem_versao_registrada` roda no portão: mudou o catálogo sem versão, o CI cai.

O `numero` é o de `ia.artefato_versao(tipo='catalogo')`; a 0001 não traz seed (o dono aprova a v1) e o atendimento fixa `catalogo_versao`
na criação. Inserir a linha no banco é ato do dono (kit da S4), fora deste repositório.

Para versionar: mude o catálogo, rode `uv run python -m ia_atendimento.ferramentas.catalogo` (imprime o hash) e acrescente
`{"numero": n+1, "hash": …, "descricao": …}` ao JSON.

Fora do catálogo de propósito: T4 (P-R23, fora do MVP), T11/T12 (ações do orquestrador: `Canal` e repasse, B1.6), T15 (verificador
opcional, B5.9) e T16 (serviço de mídia).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Final

from ia_atendimento.ferramentas import esquemas as e
from ia_atendimento.ferramentas.especificacao import Especificacao, EsquemaInvalido

ARQUIVO_DE_VERSOES: Final = Path(__file__).with_name("catalogo_versoes.json")
_HASH: Final = re.compile(r"^[0-9a-f]{64}$")

# Pré-condições da T7 (F T7; roteiro B5.4, 12 itens com opt-out e não perturbe separados): o gateway as roda por código, antes do efeito.
PRECONDICOES_DA_T7: Final = (
    "lease_ativo",
    "sem_opt_out",
    "sem_nao_perturbe",
    "humano_nao_assumiu",
    "fora_da_dataprev",
    "banco_habilitado",
    "oferta_ativa",
    "confirmacao_aceita",
    "dados_completos",
    "com_matricula",
    "sem_proposta_viva",
    "sem_tentativa_aberta",
    "corrigiveis_no_limite",
)


class CatalogoSemVersao(EsquemaInvalido):
    """O hash do catálogo não é o do último `numero` (ou o histórico está malformado): o CI falha e o gateway não sobe."""


@dataclass(frozen=True)
class VersaoDoCatalogo:
    numero: int
    hash: str
    descricao: str

    def __post_init__(self) -> None:
        if self.numero < 1:
            raise ValueError("numero começa em 1 (CHECK de artefato_versao)")
        if not _HASH.fullmatch(self.hash):
            raise ValueError("hash = sha256 em 64 hex minúsculos")
        if not 1 <= len(self.descricao.strip()) <= 1000:
            raise ValueError("descricao entre 1 e 1000 caracteres (CHECK de artefato_versao)")


class Catalogo:
    """Conjunto imutável de especificações, por nome. Iterar devolve em ordem de número (T1, T2, …, T14)."""

    def __init__(self, especificacoes: Iterable[Especificacao]) -> None:
        por_nome: dict[str, Especificacao] = {}
        for spec in especificacoes:
            if spec.nome in por_nome:
                raise EsquemaInvalido(f"ferramenta {spec.nome} repetida no catálogo")
            por_nome[spec.nome] = spec
        self._por_nome = dict(sorted(por_nome.items(), key=lambda par: int(par[0][1:])))

    def __getitem__(self, nome: str) -> Especificacao:
        return self._por_nome[nome]

    def __contains__(self, nome: object) -> bool:
        return nome in self._por_nome

    def __iter__(self) -> Iterator[Especificacao]:
        return iter(self._por_nome.values())

    def __len__(self) -> int:
        return len(self._por_nome)

    def get(self, nome: str) -> Especificacao | None:
        return self._por_nome.get(nome)

    def json_canonico(self) -> str:
        return json.dumps([s.descrever() for s in self], sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def hash(self) -> str:
        return hashlib.sha256(self.json_canonico().encode("utf-8")).hexdigest()


def ler_versoes(texto: str) -> tuple[VersaoDoCatalogo, ...]:
    dados = json.loads(texto)
    return tuple(VersaoDoCatalogo(int(v["numero"]), str(v["hash"]), str(v["descricao"])) for v in dados["versoes"])


def carregar_versoes(caminho: Path = ARQUIVO_DE_VERSOES) -> tuple[VersaoDoCatalogo, ...]:
    return ler_versoes(caminho.read_text(encoding="utf-8"))


def conferir_historico(base: Sequence[VersaoDoCatalogo], atual: Sequence[VersaoDoCatalogo]) -> None:
    """O histórico só cresce no fim: cada linha da `main` continua idêntica (numero, hash e descrição). Reescrever o hash do `numero` 1
    passaria em `conferir_versao` com o catálogo mudado e quebraria a reprodutibilidade de quem já gravou `catalogo_versao = 1` (revisão
    B5.1, M-5). O portão (`scripts/conferir_catalogo.py`) compara com a `origin/main`."""
    if tuple(atual[: len(base)]) != tuple(base):
        raise CatalogoSemVersao("o histórico do catálogo foi reescrito: as linhas da main não mudam, só se acrescenta numero novo no fim")


def conferir_versao(catalogo: Catalogo, versoes: Sequence[VersaoDoCatalogo]) -> VersaoDoCatalogo:
    """O último `numero` do histórico tem o hash do catálogo. Histórico: 1, 2, 3… sem buraco, hash novo a cada número."""
    if not versoes:
        raise CatalogoSemVersao("catálogo sem nenhum numero registrado")
    if [v.numero for v in versoes] != list(range(1, len(versoes) + 1)):
        raise CatalogoSemVersao("os numero do catálogo devem ser 1, 2, 3… sem buraco")
    if len({v.hash for v in versoes}) != len(versoes):
        raise CatalogoSemVersao("cada numero do catálogo traz um hash novo")
    vigente = versoes[-1]
    if catalogo.hash() != vigente.hash:
        raise CatalogoSemVersao(f"o catálogo mudou sem numero novo (último numero {vigente.numero}); registre a versão nova")
    return vigente


def versao_vigente() -> VersaoDoCatalogo:
    """O `numero` do catálogo do código (o atendimento novo o grava em `catalogo_versao`). Falha se o hash não tiver versão."""
    return _versao_vigente()


@cache
def _versao_vigente() -> VersaoDoCatalogo:
    return conferir_versao(CATALOGO_MVP, carregar_versoes())


CATALOGO_MVP: Final = Catalogo(
    [
        Especificacao(
            nome="T1", funcao="identificar_cliente", versao="1.0.0", descricao="Quem é o cliente (só código).", classe="leitura",
            servico="c360", entrada=e.SemArgumentos, saida=e.SaidaT1, usa_cpf=True,
        ),
        Especificacao(
            nome="T2", funcao="estado_oportunidade", versao="1.0.0",
            descricao="T2 estado_oportunidade: o estado do lead (oferta, digitação, contrato). Argumentos: nenhum.", classe="leitura",
            servico="c360", entrada=e.SemArgumentos, saida=e.SaidaT2, do_modelo=True,
        ),
        Especificacao(
            nome="T3", funcao="ofertas_disponiveis", versao="1.0.0",
            descricao="T3 oferta_ativa: a condição disponível agora. Argumentos: oferta_ref (o apelido que está no estado, como oferta-1).",
            classe="leitura", servico="c360", entrada=e.ArgsOferta, saida=e.SaidaT3, do_modelo=True,
        ),
        Especificacao(
            nome="T5", funcao="simular", versao="1.0.0",
            descricao="T5 simular: outras opções para o pedido do cliente. Argumentos: oferta_ref (o apelido do estado) e alvo (valor, "
            "parcela ou prazo).",
            classe="leitura", servico="banco", entrada=e.ArgsSimulacao, saida=e.SaidaT5, do_modelo=True, usa_cpf=True,
        ),
        Especificacao(
            nome="T6", funcao="coletar_dados_digitacao", versao="1.0.0", descricao="Valida e guarda um campo da digitação (só código).",
            classe="acao_interna", servico="interno", entrada=e.ArgsColeta, saida=e.SaidaT6, timeout_s=1.0,
        ),
        Especificacao(
            nome="T7", funcao="digitar_proposta", versao="1.0.0", descricao="Digita a proposta confirmada (só código).",
            classe="efeito_irreversivel", servico="facta", entrada=e.ArgsDigitacao, saida=e.SaidaT7, precondicoes=PRECONDICOES_DA_T7,
            timeout_s=125.0, execucao="assincrona", idempotencia="chave_por_tentativa", bancos=("FACTA",),
            flag_dos_bancos="bancos_digitacao", usa_cpf=True,
        ),
        Especificacao(
            nome="T8", funcao="conferir_digitacao", versao="1.0.0", descricao="Resolve a digitação indeterminada (só código).",
            classe="leitura", servico="facta", entrada=e.ArgsTentativa, saida=e.SaidaT8, timeout_s=1500.0, execucao="assincrona",
            idempotencia="chave_por_tentativa", bancos=("FACTA",), flag_dos_bancos="bancos_digitacao", usa_cpf=True,
        ),
        Especificacao(
            nome="T9", funcao="link_formalizacao", versao="1.0.0", descricao="Link de assinatura (só código).", classe="leitura",
            servico="facta", entrada=e.ArgsTentativa, saida=e.SaidaT9, bancos=("FACTA",),
        ),
        Especificacao(
            nome="T10", funcao="status_proposta", versao="1.0.0",
            descricao="T10 status_proposta: onde está a proposta enviada (só leitura). Argumentos: nenhum.", classe="leitura",
            servico="c360", entrada=e.SemArgumentos, saida=e.SaidaT10, do_modelo=True,
        ),
        Especificacao(
            nome="T13", funcao="contexto_operacional", versao="1.0.0", descricao="Bancos disponíveis e janela DATAPREV (só código).",
            classe="acao_interna", servico="interno", entrada=e.SemArgumentos, saida=e.SaidaT13, timeout_s=1.0,
        ),
        Especificacao(
            nome="T14", funcao="registrar_opt_out", versao="1.0.0", descricao="Opt-out local (só código).", classe="acao_interna",
            servico="interno", entrada=e.ArgsOptOut, saida=e.SaidaT14, timeout_s=1.0, idempotencia="chave_por_atendimento",
        ),
    ]
)  # fmt: skip


if __name__ == "__main__":  # pragma: no cover - ajuda para versionar
    print(CATALOGO_MVP.hash())
