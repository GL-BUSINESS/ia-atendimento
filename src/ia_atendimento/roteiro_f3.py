"""O roteiro da F3 como resposta do modelo (B1.4): alimenta o `ProvedorFalso` e os exemplos do bloco 2 do prompt.

O corpus (`tests/corpus/`, B8.1a) tem 60 personas e 60 diálogos-gabarito: para cada fala do cliente, a intenção e a objeção esperadas e,
no turno seguinte da IA, as ações permitidas e os TX esperados. Daqui sai o `Turno` que um modelo certo daria àquela fala:
`turno_esperado`. É um modelo de brinquedo (acerta porque lê o gabarito), bom para provar o encanamento sem rede: contexto → prompt →
agente → `Turno` → validação na fase → custo → `decisao`. A qualidade do modelo de verdade é da B8.2.

- **Hold-out fora dos exemplos.** Os exemplos que vão ao prompt vêm só de personas que NÃO são do hold-out (20%, risco 7 de H): exemplo
  tirado
  de lá contaminaria a nota do desenvolvimento. O `ProvedorFalso`, ao contrário, responde a qualquer persona (é o gabarito, não um prompt).
- A fala do cliente é comparada **como o modelo a vê**: depois de `proteger_texto` (máscara, `[VALOR]`, `[PRAZO]`), com os nomes da persona.
- A resposta da E1 ao TX-01 cai na fase E2 (H §2.1: «cliente responde → E2»): o gabarito rotula a fala com a fase em que ela CHEGOU.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from ia_atendimento.contexto import ExemploDaFase, proteger_texto
from ia_atendimento.corpus import Corpus, Dialogo
from ia_atendimento.corpus import Turno as TurnoDoCorpus
from ia_atendimento.turno import (
    ACOES_POR_FASE,
    FASE_DO_CAMPO_ALVO,
    FERRAMENTAS_DO_MODELO_POR_FASE,
    MOTIVO_AUSENTE,
    TX_DO_MODELO_POR_FASE,
    FerramentaPedida,
    Sinal,
    Turno,
)

TEXTO_DA_PONTE: Final = "Entendi, vou te ajudar com isso."  # sem dígito, sem valor: o gabarito NÃO fixa o texto livre da IA
MOTIVO_DO_ROTEIRO: Final = "roteiro da F3"
ORDEM_DAS_ACOES: Final = ("responder", "pedir_dado", "usar_ferramenta", "repassar", "aguardar", "encerrar", "pedir_confirmacao")
FASE_DO_MODELO: Final = {"E1": "E2"}  # a resposta ao TX-01 é processada na E2
SINAL_POR_INTENCAO: Final[Mapping[str, Sinal]] = {
    "aceita": "positivo", "saudacao": "positivo", "reclamacao": "frustrado", "pede_humano": "negativo", "parar": "negativo",
    "recusa_firme": "negativo", "nao_sou_eu": "negativo", "sinal_fraude_ou_vulnerabilidade": "negativo",
}  # fmt: skip
ALVO_POR_INTENCAO: Final[Mapping[str, str]] = {"quer_outro_valor": "valor", "quer_outro_prazo": "prazo"}


class ForaDoRoteiro(LookupError):
    """O ProvedorFalso recebeu uma fala que o corpus não tem. Erro de teste: não é falha do modelo."""


def fase_do_modelo(fase_do_corpus: str) -> str:
    return FASE_DO_MODELO.get(fase_do_corpus, fase_do_corpus)


def _acao(fase: str, permitidas: Sequence[str]) -> str:
    da_fase = ACOES_POR_FASE[fase]  # type: ignore[index]
    for acao in ORDEM_DAS_ACOES:
        if acao in permitidas and acao in da_fase and (acao != "usar_ferramenta" or FERRAMENTAS_DO_MODELO_POR_FASE[fase]):  # type: ignore[index]
            return acao
    return "aguardar" if "aguardar" in da_fase else sorted(da_fase)[0]


def turno_esperado(cliente: TurnoDoCorpus, ia: TurnoDoCorpus | None, fase: str) -> Turno:
    """O `Turno` que um modelo certo daria à fala `cliente`, na fase `fase` do modelo, olhando o turno seguinte da IA (`ia`)."""
    if cliente.intencao_esperada is None:
        raise ValueError("fala sem intenção esperada (mídia): não há turno do modelo")
    permitidas = ia.acoes_permitidas if ia is not None else ()
    acao = _acao(fase, permitidas)
    ferramenta = None
    if acao == "usar_ferramenta":
        ferramenta = FerramentaPedida(nome=sorted(FERRAMENTAS_DO_MODELO_POR_FASE[fase])[0])  # type: ignore[index]
    tx = next((t for t in (ia.tx_esperado if ia else ()) if t in TX_DO_MODELO_POR_FASE[fase]), None)  # type: ignore[index]
    alvo = ALVO_POR_INTENCAO.get(cliente.intencao_esperada, "parcela" if cliente.objecao_esperada == "parcela_alta" else None)
    campo = (ia.campo_alvo if ia else None) or cliente.campo_alvo
    return Turno(
        intencao=cliente.intencao_esperada,
        acao=acao,  # type: ignore[arg-type]
        confianca="alta",
        objecao=cliente.objecao_esperada,
        alvo_pedido=alvo,  # type: ignore[arg-type]
        campo_alvo=campo if fase == FASE_DO_CAMPO_ALVO else None,
        ferramenta=ferramenta,
        tx_id=tx,
        texto=TEXTO_DA_PONTE if (ia is not None and ia.texto_livre_ia and acao == "responder" and tx is None) else None,
        motivo=MOTIVO_DO_ROTEIRO,
        sinal=SINAL_POR_INTENCAO.get(cliente.intencao_esperada, "neutro"),
    )


@dataclass(frozen=True)
class _Fala:
    persona_id: str
    fase: str  # do modelo
    cliente: TurnoDoCorpus
    ia: TurnoDoCorpus | None


def _falas(dialogo: Dialogo) -> list[_Fala]:
    achadas = []
    turnos = dialogo.turnos
    for i, turno in enumerate(turnos):
        if turno.quem == "cliente" and turno.texto_cliente is not None and turno.intencao_esperada is not None:
            seguinte = turnos[i + 1] if i + 1 < len(turnos) and turnos[i + 1].quem == "ia" else None
            fase = fase_do_modelo(turno.fase_esperada)
            if ACOES_POR_FASE.get(fase):  # type: ignore[index]
                achadas.append(_Fala(dialogo.persona_id, fase, turno, seguinte))
    return achadas


class RoteiroF3:
    """`Roteiro` do `ProvedorFalso` sobre o corpus. Casa a fala (já protegida, como o modelo a vê) com todas as redações do gabarito."""

    def __init__(self, corpus: Corpus) -> None:
        nomes = {p.id: p.nome for p in corpus.todas()}
        self._indice: dict[str, list[_Fala]] = {}
        for persona_id in sorted(corpus.dialogos):
            for fala in _falas(corpus.dialogos[persona_id]):
                for texto in (fala.cliente.texto_cliente or "", *fala.cliente.variacoes):
                    chave = proteger_texto(texto, [nomes.get(persona_id, "")])
                    self._indice.setdefault(chave, []).append(fala)

    def responder(self, fase: str, mensagens: tuple[str, ...]) -> Turno:
        if not mensagens:
            raise ForaDoRoteiro("o prompt não traz mensagem pendente")
        candidatas = self._indice.get(mensagens[-1])
        if not candidatas:
            raise ForaDoRoteiro("a fala não está no corpus da F3")
        fala = next((f for f in candidatas if f.fase == fase), candidatas[0])
        return turno_esperado(fala.cliente, fala.ia, fase if ACOES_POR_FASE.get(fase) else fala.fase)  # type: ignore[index]


# Intenções que mais ensinam, na ordem em que entram no bloco 2 (a classificação difícil primeiro; saudação e adiamento só se faltar).
INTENCOES_DIDATICAS: Final = (
    "objecao", "duvida_oferta", "duvida_processo", "quer_outro_valor", "quer_outro_prazo", "recusa_firme", "aceita", "quer_pensar",
    "pede_humano", "fornece_dado", "reclamacao", "fora_de_escopo", "saudacao",
)  # fmt: skip


def exemplos_da_f3(corpus: Corpus, fase: str, *, quantos: int = 2) -> tuple[ExemploDaFase, ...]:
    """Até `quantos` exemplos curtos da fase, de intenções diferentes, só de personas fora do hold-out. Determinístico."""
    if fase not in ACOES_POR_FASE or not ACOES_POR_FASE[fase]:  # type: ignore[index]
        return ()
    fora = set(corpus.semente.holdout)
    por_intencao: dict[str, _Fala] = {}
    for persona_id in sorted(corpus.dialogos):
        if persona_id in fora:
            continue
        for fala in _falas(corpus.dialogos[persona_id]):
            texto = fala.cliente.texto_cliente or ""
            if fala.fase == fase and not fala.cliente.pii_digitada and len(texto) <= 60 and not any(c.isdigit() for c in texto):
                por_intencao.setdefault(fala.cliente.intencao_esperada or "", fala)
    ordem = [i for i in INTENCOES_DIDATICAS if i in por_intencao] + sorted(set(por_intencao) - set(INTENCOES_DIDATICAS))
    exemplos = []
    for intencao in ordem[:quantos]:
        fala = por_intencao[intencao]
        esperado = turno_esperado(fala.cliente, fala.ia, fase).model_copy(update={"motivo": MOTIVO_AUSENTE})  # o prompt não cita «F3»
        exemplos.append(ExemploDaFase(fase, fala.cliente.texto_cliente or "", esperado))
    return tuple(exemplos)
