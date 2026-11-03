"""Quem serve T1 e T3 em `duble|teste` no lugar do 360 (B2.4, R2-07): as fixtures do catálogo, com `valid_until` RELATIVO ao servir.

O gateway de ferramentas (B5.2) pergunta por `pessoa_id` (chat de teste não tem CPF) e recebe o MESMO corpo que o 360 devolveria:
`ResumosPessoas` (T1, `pessoas:resumos`) e `ResultadoPropostasPessoa` (T3, `pessoas:propostas`). Em `real` e `sombra` a fonte se recusa
(`ForaDoModoDeTeste`): fixture nunca responde por cliente de verdade. Em `teste` o 360 real não tem a pessoa (CPF `000.000.0nn`), por isso
o roteiro (B2.4/B5.2) manda ler fixture em `duble` **e** em `teste`; a tabela do contrato 08 §6 diz «360 real» na linha «Ler» de `teste`
e precisa ser emendada (DECISOES-B2.4).

Nada é lido de disco aqui: o catálogo chega pronto e o relógio é injetado, então `valid_until` = agora + validade em qualquer teste.
Pessoa que o catálogo não conhece responde como o 360: `encontrado:false` / `itens: []`, 200.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Final
from uuid import UUID
from zoneinfo import ZoneInfo

from ia_atendimento.pessoas_teste.catalogo import CatalogoPessoasTeste, ParDeTeste, PessoaDeTeste
from ia_atendimento.pessoas_teste.formas import (
    AlvoSugerido,
    AtribuicaoPropostas,
    AtributosCadastraisOferta,
    Oferta,
    ParPropostasPessoa,
    PayloadEconomicoCltV1,
    PessoaResumo,
    ResultadoPropostasPessoa,
    ResumosPessoas,
    SnapshotCoeficiente,
)
from ia_atendimento.relogio import Relogio

MODOS_COM_FIXTURES: Final = frozenset({"teste", "duble"})
VALIDADE_PADRAO: Final = timedelta(hours=2)  # roteiro B2.4: `valid_until` = agora + 2 h, calculado ao servir
CRIADA_HA: Final = timedelta(minutes=15)  # a oferta "nasceu" há 15 min (consulta recente, dentro de qualquer janela de frescor)
FUSO_NEGOCIO: Final = ZoneInfo("America/Sao_Paulo")


class ForaDoModoDeTeste(RuntimeError):
    """Pediram fixture em `real` ou `sombra`. A mensagem cita só o modo."""


def instante(momento: datetime) -> str:
    """RFC 3339 em UTC com `Z`, sem fração (o padrão `Instante` do 360)."""
    return momento.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")


class FontePessoasTeste:
    def __init__(self, catalogo: CatalogoPessoasTeste, relogio: Relogio, *, validade: timedelta = VALIDADE_PADRAO) -> None:
        if validade <= timedelta(0):
            raise ValueError("a validade da oferta de teste é positiva")
        self._catalogo, self._relogio, self._validade = catalogo, relogio, validade

    def _pessoa(self, pessoa_id: UUID | str, modo: str) -> PessoaDeTeste | None:
        if modo not in MODOS_COM_FIXTURES:
            raise ForaDoModoDeTeste(f"fixtures de pessoas de teste só valem em duble|teste (modo pedido: {modo!r})")
        return self._catalogo.por_pessoa(pessoa_id)

    def resumo(self, pessoa_id: UUID | str, modo: str) -> dict[str, Any]:
        """T1 cru: `{"itens": [PessoaResumo]}` (vazio se a pessoa não é do catálogo). Sem `nao_perturbe` nem `limite_contratos`."""
        pessoa = self._pessoa(pessoa_id, modo)
        itens = [] if pessoa is None else [self._resumo(pessoa)]
        return ResumosPessoas(itens=itens).model_dump(mode="json", exclude_unset=True)

    def propostas(self, pessoa_id: UUID | str, modo: str, *, validade: timedelta | None = None, versao: int = 1) -> dict[str, Any]:
        """T3 cru: `ResultadoPropostasPessoa`. `validade`/`versao` deixam o harness (B8.1b) fabricar «a oferta vence» e «a versão mudou»."""
        pessoa = self._pessoa(pessoa_id, modo)
        agora = self._relogio.agora()
        if pessoa is None:
            vazio = ResultadoPropostasPessoa(encontrado=False, pares=[], varias_ofertas=False, lido_em=instante(agora))
            return vazio.model_dump(mode="json", exclude_unset=True)
        valido_ate = agora + (self._validade if validade is None else validade)
        pares = [self._par(pessoa, par, agora, valido_ate, versao) for par in pessoa.pares]
        resultado = ResultadoPropostasPessoa(
            encontrado=True,
            pessoa_id=str(pessoa.pessoa_id),
            atribuicao=AtribuicaoPropostas(versao=1, site_profile_id=None),
            varias_ofertas=sum(1 for p in pares if p.oferta_ativa is not None) > 1,
            pares=pares,
            lido_em=instante(agora),
        )
        return resultado.model_dump(mode="json", exclude_unset=True)

    def cpf_de(self, pessoa_id: UUID | str, modo: str) -> str | None:
        """CPF (11 dígitos) da pessoa de teste, para as chamadas ao dublê (T5/T7/T8). Só o gateway o usa; nunca vai ao modelo nem ao log."""
        pessoa = self._pessoa(pessoa_id, modo)
        return None if pessoa is None else pessoa.cpf_digitos

    # ------------------------------------------------------------------------------------------------------------- montagem

    @staticmethod
    def _resumo(pessoa: PessoaDeTeste) -> PessoaResumo:
        d = pessoa.cpf_digitos
        return PessoaResumo(
            pessoa_id=str(pessoa.pessoa_id), nome=pessoa.nome, cpf_mascarado=f"***.***.***-{d[9:]}", cpf=d,
            status_atendimento=None, vendedor=None, nao_perturbe=None, limite_contratos=None,
        )  # fmt: skip

    @staticmethod
    def _par(pessoa: PessoaDeTeste, par: ParDeTeste, agora: datetime, valido_ate: datetime, versao: int) -> ParPropostasPessoa:
        if par.economia is None or par.oferta_id is None:
            return ParPropostasPessoa(
                banco=par.banco, produto=par.produto, caso="sem_oferta", contratos=[], oferta_ativa=None, alvo_sugerido=None
            )
        eco, criada = par.economia, instante(agora - CRIADA_HA)
        oferta = Oferta(
            oferta_id=par.oferta_id, pessoa_id=str(pessoa.pessoa_id), banco=par.banco, produto=par.produto,
            business_date=agora.astimezone(FUSO_NEGOCIO).date().isoformat(), estado="ativa", versao=versao,
            valid_until=instante(valido_ate), criada_em=criada, ciclo=1, ultima_consulta_em=criada,
            economia=PayloadEconomicoCltV1(
                forma="payload_clt_v1", valor_liberado=eco.valor_liberado, valor_parcela=eco.valor_parcela, prazo_meses=eco.prazo_meses,
                tabela_identificador=eco.tabela_identificador, convenio=eco.convenio, coeficiente_financeiro=eco.coeficiente_financeiro,
            ),
            atributos_cadastrais=AtributosCadastraisOferta(nome=pessoa.nome, telefone=pessoa.telefone),
            coeficiente=SnapshotCoeficiente(
                alvo_tipo="oferta", alvo_id=par.oferta_id, coef_origem="catalogo", coef_valor=eco.coef_valor, coef_versao_id=1,
                coef_resolvido_em=criada, coef_financeiro=eco.coeficiente_financeiro,
            ),
        )  # fmt: skip
        return ParPropostasPessoa(
            banco=par.banco, produto=par.produto, caso="so_oferta", contratos=[], oferta_ativa=oferta,
            alvo_sugerido=AlvoSugerido(tipo="oferta", id=par.oferta_id),
        )  # fmt: skip
