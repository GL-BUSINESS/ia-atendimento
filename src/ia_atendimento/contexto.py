"""Contexto do turno (B1.4, sp01 T6): os 8 blocos do prompt de H §3.1, a estimativa de tokens e o corte até caber em 4 mil.

| # | Bloco | Onde vai | De onde vem |
|---|---|---|---|
| 1 | sistema fixo (+ o formato `Turno`, que o provedor recebe como ferramenta de saída) | instruções | `modulos_fase.SISTEMA` |
| 2 | módulo da fase: objetivo, ações, TX do modelo e até 2 exemplos da F3 | instruções | `modulos_fase`, exemplos de `roteiro_f3` |
| 3 | esquemas das ferramentas que o MODELO pode pedir na fase | instruções | `turno.FERRAMENTAS_DO_MODELO_POR_FASE` |
| 4 | estado estruturado (só códigos e referências opacas) | mensagem | `EstadoConversa` + allowlist do `perfil` |
| 5 | resumo (só depois de 10 mensagens) | mensagem | `conversa.gravar_resumo` |
| 6 | últimas 3 trocas, mascaradas | mensagem | `conversa.ler_trocas` |
| 7 | resultado das ferramentas do turno, por allowlist | mensagem | `projetar_resultado` |
| 8 | mensagens pendentes do cliente (a rajada junta) | mensagem | `conversa_cifrada` (por `passo_ordem`) |

**O modelo nunca recebe** CPF, telefone, e-mail, nome, valor, prazo da oferta nem texto sem máscara (H §3.3, P3). O texto de cliente passa
pela máscara outra vez aqui (`protecao.proteger_texto`: dinheiro, prazo, data de nascimento e todo número «nu» de 2+ dígitos fora de hora,
dia e duração viram `[VALOR]`, `[PRAZO]`, `[DATA]`, `[NUMERO]`); o `perfil` e o resultado de ferramenta só passam por allowlist de
chave e de valor (enum, catálogo ou forma segura); antes da fase E3 (Q1: abertura sem valores) nem a oferta aparece. Ids reais (oferta,
opções) viram apelidos (`oferta-1`, `opcao-2`); `Contexto.referencias` diz o que cada um é.

**Na E5 a mensagem do cliente É o valor do campo** (modo guiado, B5.3): por padrão vira `[dado:<campo>]` e só chega ao modelo com
`desvio_liberado=True`, que o chamador passa quando a regra de desvio manda. Por fim `auditar_prompt` confere o prompt inteiro contra a
máscara: se algo ainda mudaria, o turno não sai (`ContextoComDadoPessoal`, um `ErroDoModelo`).

**Teto de 4.000 tokens de entrada.** A contagem é uma ESTIMATIVA (HIPÓTESE, `tokens.py`; medir com o tokenizer do DeepSeek em B8.2) e
inclui o formato `Turno`. Acima do teto cortam-se, NESTA ordem: resumo → trocas antigas (de duas em duas, fica a última) → exemplos da
fase (um a um). Se ainda não couber, `ContextoNaoCabe`: o turno conta como falha do modelo. Nada além dessas três coisas é opcional.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Final
from uuid import UUID

import psycopg

from ia_atendimento.chave_registro import BANCOS
from ia_atendimento.cifra import ChaveDesconhecida, Chaveiro
from ia_atendimento.conversa import NomesIndisponiveis, ler_trocas
from ia_atendimento.estado import ler as ler_atendimento
from ia_atendimento.estado_conversa import estado_conversa_de_json, janela_24h_aberta
from ia_atendimento.linha_tempo import Pendente
from ia_atendimento.mascara import mascarar
from ia_atendimento.modelos_conversa import EstadoConversa
from ia_atendimento.modulos_fase import FASES_SEM_TURNO_DO_MODELO, SISTEMA, esquemas_das_ferramentas, modulo_da_fase
from ia_atendimento.protecao import ha_link, normalizar, proteger_texto
from ia_atendimento.tokens import ESTIMADOR_PADRAO, EstimadorDeTokens
from ia_atendimento.turno import PLACEHOLDERS_DA_FASE, PLACEHOLDERS_DO_TEXTO, ErroDoModelo, Turno, formato_do_turno

TETO_TOKENS: Final = 4000  # H §3.1: teto duro de entrada
TROCAS_NO_PROMPT: Final = 3
EXEMPLOS_POR_FASE: Final = 2
MENSAGENS_MINIMAS_APOS_CORTE: Final = 2  # a última troca nunca sai: é o que a IA acabou de perguntar e a resposta do cliente
CARACTERES_DAS_PENDENTES: Final = 560  # ~200 tokens (teto do bloco 8); dividido pela rajada
CARACTERES_MINIMOS_POR_PENDENTE: Final = 120
MAX_PENDENTES_NO_PROMPT: Final = 10  # rajada maior: entram as 10 últimas e uma linha diz quantas ficaram de fora (B-3)
TETOS_DO_BLOCO: Final = {1: 800, 2: 650, 3: 600, 4: 600, 5: 300, 6: 700, 7: 400, 8: 200}  # H §3.1 (referência; só o total é imposto)
NOMES_DOS_BLOCOS: Final = {
    1: "sistema", 2: "modulo_da_fase", 3: "ferramentas", 4: "estado", 5: "resumo", 6: "trocas", 7: "resultados", 8: "pendentes",
}  # fmt: skip

CABECALHO_PENDENTES: Final = "## Mensagens pendentes do cliente"
CABECALHO_TROCAS: Final = "## Últimas trocas (mascaradas)"
CABECALHO_RESUMO: Final = "## Resumo da conversa"
CABECALHO_ESTADO: Final = "## Estado"
CABECALHO_RESULTADOS: Final = "## Resultado das ferramentas neste turno"
# `perfil` ao modelo (n §2.2/§3: quem falou por último, tipo da última fala, etapa do in-app). Allowlist POR CHAVE e com regra própria de
# valor: um limite único para todas as chaves deixaria um valor da oferta ou um número sensível entrar por uma chave errada. Faixas de
# parcela ou valor ficam de fora (são valores). Chave fora daqui não chega ao prompt, e valor fora da regra da SUA chave é descartado,
# sem aviso e sem eco.
LEAD_ENUMS: Final[Mapping[str, frozenset[str]]] = {
    # catálogo fechado de `chave_registro` (FACTA, 3RN, C6): o padrão `[A-Z0-9_]+` deixava passar `R_1500` e `200_300` (M-4)
    "banco": frozenset(BANCOS),
    "origem": frozenset({"inapp", "leilao"}),  # H §3.6
    "ultimo_sentido": frozenset({"in", "out"}),  # n §1: quem falou por último
    "tipo_ultima_fala": frozenset({"texto", "audio", "imagem", "documento", "sticker", "localizacao", "outro"}),  # igual a `msg_tipo`
    "etapa_inapp": frozenset(
        {"proposta_vista", "simulou", "tela_dados", "saiu_da_tela", "desconhecida"}
    ),  # n §3.1 (e); B6.2 fixa os códigos (L3)
}
LIMITES_INTEIROS_DO_LEAD: Final[Mapping[str, int]] = {
    "idade_do_lead_min": 9999,  # minutos desde a simulação
    "etapas_do_robo_concluidas": 20,  # quantas etapas do in-app o lead já fez
}
PERFIL_PARA_O_MODELO: Final = tuple(sorted({*LEAD_ENUMS, *LIMITES_INTEIROS_DO_LEAD}))
FASES_COM_VALORES: Final = frozenset({"E3", "E4", "E5", "E6", "E7", "E8"})  # Q1: antes da E3 nem a oferta aparece no estado
# Resultado de ferramenta ao modelo: SÓ o que está aqui (`True` = folha permitida; dict = objeto/lista de objetos). Valor em reais, prazo,
# coeficiente, comissão e motivo cru do banco não estão em nenhuma lista: não passam, mesmo que a ferramenta os devolva.
# TODA folha de texto é de domínio FECHADO (um `frozenset`: valor fora dele some); `True` é só escalar (booleano ou inteiro pequeno) ou, nas
# chaves `*_ref`, o id que vira apelido. Nenhuma folha de texto passa por «forma» (regex): `valor-5000` e `parcela312` passavam (R2-04).
# Macros da proposta: estudo F (T10) e dicionário ST-00…05 de TEXTOS-PARA-APROVACAO.
MACROS_DA_PROPOSTA: Final = frozenset({"pendente", "em_analise", "aguardando_pagamento", "pago", "cancelado", "estornado"})
# `fase` do T2 (estudo F, contrato do T2): onde está a oportunidade; `etapa` é o mesmo domínio sob o nome que o gateway ainda pode usar.
FASES_DO_T2: Final = frozenset(
    {"sem_oferta", "oferta_ativa", "confirmando", "digitando", "indeterminado", "em_esteira", "paga", "cancelada", "encerrada"}
)
STATUS_DA_OFERTA: Final = frozenset({"ativa", "vencida", "indisponivel", "sem_oferta"})  # HIPÓTESE: o gateway (B5) fixa; muda junto com ele
PROXIMAS_ACOES_DO_T10: Final = frozenset({"aguardar", "abrir_link", "pedir_documento", "repasse"})  # estudo F, contrato do T10
FRASES_DO_T10: Final = frozenset(f"ST-{n:02d}" for n in range(6))  # ST-00…05 de TEXTOS-PARA-APROVACAO
PROJECAO_DAS_FERRAMENTAS: Final[Mapping[str, Mapping[str, Any]]] = {
    "T2": {"fase": FASES_DO_T2, "etapa": FASES_DO_T2, "contrato_vivo": True, "proposta_viva": True, "degradado": True},
    "T3": {
        "oferta_ref": True,
        "status": STATUS_DA_OFERTA,
        "versao": True,
        "vencida": True,
        "mudou": True,
        "placeholders": PLACEHOLDERS_DO_TEXTO,
    },
    "T5": {
        "opcoes": {"opcao_ref": True, "dentro_da_alcada": True, "placeholders": PLACEHOLDERS_DO_TEXTO},
        "sem_opcao": True,
        "acima_do_maximo": True,
    },
    "T10": {"macro": MACROS_DA_PROPOSTA, "proxima_acao": PROXIMAS_ACOES_DO_T10, "frase_ref": FRASES_DO_T10},
}
MAX_ITENS_DE_LISTA: Final = 5
MAX_INTEIRO_DE_RESULTADO: Final = 99  # contador; acima disso pode ser valor, prazo ou id (ver o teste de projeção)
_ALIAS_DE_REF: Final = {"oferta_ref": "oferta", "opcao_ref": "opcao"}

_PROIBIDO_NO_PROMPT: Final = re.compile(r"(?i)r\$|us\$")
_LINHA_DE_PENDENTE: Final = re.compile(r"^\d+\. «(.*)»$")
_FASE_NO_ESTADO: Final = re.compile(r'"fase":"(E(?:10|[0-9]))"')


# --- erros -------------------------------------------------------------------------------------------------------------------------------


class ContextoErro(Exception):
    """Base. As mensagens trazem números e nomes de campo, nunca texto."""


class FaseSemTurnoDoModelo(ContextoErro, ValueError):
    """E0, E1 e E9 não têm turno do modelo (H §2.3): montar o contexto delas é erro do chamador."""


class FalhaDoContexto(ContextoErro, ErroDoModelo):
    """Falha do contexto que conta como falha do turno do modelo. Quem faz `except ErroDoModelo` (o processador da B1.6, que repassa na
    2ª) a pega junto das do provedor e da saída; sem isso o job reentrava sem contar e o cliente ficava sem repasse (M-11)."""

    def __init__(self, codigo: str, mensagem: str) -> None:
        ErroDoModelo.__init__(self, codigo, mensagem)


class ContextoNaoCabe(FalhaDoContexto):
    """Mesmo sem resumo, trocas antigas e exemplos o prompt passa do teto: o turno conta como falha do modelo (B1.6 repassa na 2ª)."""

    def __init__(self, tokens: int, teto: int) -> None:
        super().__init__("contexto_nao_cabe", f"contexto de {tokens} tokens acima do teto de {teto} depois de cortar tudo que era opcional")
        self.tokens = tokens
        self.teto = teto


class ContextoComDadoPessoal(FalhaDoContexto):
    """A máscara ainda mudaria o prompt montado (ou há símbolo de moeda): nada vai ao modelo. Não diz o que casou."""

    def __init__(self, mensagem: str = "o prompt montado ainda tem dado pessoal, valor ou link; o turno não sai") -> None:
        super().__init__("contexto_com_dado_pessoal", mensagem)


# --- proteção do texto -------------------------------------------------------------------------------------------------------------------


def _cortar(texto: str, limite: int) -> str:
    return texto if len(texto) <= limite else texto[: max(limite - 1, 1)].rstrip() + "…"


# --- insumos e contexto ------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ExemploDaFase:
    """Um exemplo curto do bloco 2: o que o cliente disse e o `Turno` esperado. Vem da F3 (`roteiro_f3.exemplos_da_f3`)."""

    fase: str
    cliente: str = field(repr=False)
    saida: Turno


@dataclass(frozen=True)
class Bloco:
    numero: int
    nome: str
    texto: str = field(repr=False)
    tokens: int

    @property
    def teto(self) -> int:
        return TETOS_DO_BLOCO[self.numero]


@dataclass(frozen=True)
class Insumos:
    """O que foi lido e protegido, ainda sem tokens: `cortar_ate_caber` tira daqui e remonta."""

    fase: str
    estado: str = field(repr=False)
    modulo: str = field(repr=False)
    ferramentas: str = field(repr=False)
    exemplos: tuple[str, ...] = field(repr=False)
    resumo: str | None = field(repr=False)
    trocas: tuple[str, ...] = field(repr=False)
    resultados: str = field(repr=False)
    pendentes: tuple[str, ...] = field(repr=False)


@dataclass(frozen=True)
class Contexto:
    fase: str
    blocos: tuple[Bloco, ...] = field(repr=False)
    tokens_formato: int
    cortes: tuple[str, ...]
    referencias: Mapping[str, str] = field(repr=False)  # apelido que o modelo viu -> id real (oferta, opção, agendamento)
    insumos: Insumos = field(repr=False)
    estimador: EstimadorDeTokens = field(repr=False)
    tokens_ferramentas: int = 0  # esquemas das ferramentas REGISTRADAS que o provedor recebe nesta fase (`tools` do corpo HTTP)

    @property
    def tokens_total(self) -> int:
        return sum(b.tokens for b in self.blocos) + self.tokens_formato + self.tokens_ferramentas

    @property
    def sistema(self) -> str:
        """Blocos 1 a 3 (estáveis na fase): vão como instruções, no começo do prompt."""
        return _juntar(b.texto for b in self.blocos[:3])

    @property
    def usuario(self) -> str:
        """Blocos 4 a 8 (mudam a cada turno): a mensagem do usuário."""
        return _juntar(b.texto for b in self.blocos[3:])

    def tokens_do_bloco(self, numero: int) -> int:
        bloco = self.blocos[numero - 1]
        return bloco.tokens + (self.tokens_formato if numero == 1 else 0)  # o formato `Turno` conta junto do bloco 1 (H §3.1)


def _juntar(textos: Iterable[str]) -> str:
    return "\n\n".join(t for t in textos if t)


def _bloco(numero: int, texto: str, estimador: EstimadorDeTokens) -> Bloco:
    return Bloco(numero, NOMES_DOS_BLOCOS[numero], texto, estimador.contar(texto))


def construir(
    insumos: Insumos,
    referencias: Mapping[str, str],
    estimador: EstimadorDeTokens,
    cortes: tuple[str, ...] = (),
    tokens_ferramentas: int = 0,
) -> Contexto:
    """Renderiza os 8 blocos na ordem de H §3.1 e conta os tokens (o bloco vazio custa zero)."""
    modulo = insumos.modulo + ("\nExemplos:\n" + "\n".join(insumos.exemplos) if insumos.exemplos else "")
    textos = (
        SISTEMA,
        modulo,
        insumos.ferramentas,
        f"{CABECALHO_ESTADO}\n{insumos.estado}",
        f"{CABECALHO_RESUMO}\n{insumos.resumo}" if insumos.resumo else "",
        f"{CABECALHO_TROCAS}\n" + "\n".join(insumos.trocas) if insumos.trocas else "",
        f"{CABECALHO_RESULTADOS}\n{insumos.resultados}" if insumos.resultados else "",
        f"{CABECALHO_PENDENTES}\n" + "\n".join(f"{i}. «{t}»" for i, t in enumerate(insumos.pendentes, start=1)),
    )
    blocos = tuple(_bloco(numero, texto, estimador) for numero, texto in enumerate(textos, start=1))
    return Contexto(
        insumos.fase,
        blocos,
        estimador.contar(formato_do_turno()),
        cortes,
        dict(referencias),
        insumos,
        estimador,
        tokens_ferramentas,
    )


def _proximo_corte(insumos: Insumos) -> tuple[str, Insumos] | None:
    """A ordem do corte (H §3.1): resumo → trocas antigas → exemplos da fase. `None` = não há mais nada opcional."""
    if insumos.resumo:
        return "resumo", replace(insumos, resumo=None)
    if len(insumos.trocas) > MENSAGENS_MINIMAS_APOS_CORTE:
        sobra = max(len(insumos.trocas) - 2, MENSAGENS_MINIMAS_APOS_CORTE)  # uma troca (2 mensagens) por vez
        return "troca_antiga", replace(insumos, trocas=insumos.trocas[-sobra:])
    if insumos.exemplos:
        return "exemplo", replace(insumos, exemplos=insumos.exemplos[:-1])
    return None


def cortar_ate_caber(contexto: Contexto, teto: int = TETO_TOKENS) -> Contexto:
    """Tira resumo, depois trocas antigas, depois exemplos, até `tokens_total <= teto`. Sem o que cortar: `ContextoNaoCabe`."""
    atual = contexto
    while atual.tokens_total > teto:
        corte = _proximo_corte(atual.insumos)
        if corte is None:
            raise ContextoNaoCabe(atual.tokens_total, teto)
        nome, insumos = corte
        atual = construir(insumos, atual.referencias, atual.estimador, (*atual.cortes, nome), atual.tokens_ferramentas)
    return atual


def auditar_prompt(contexto: Contexto, nomes: Collection[str] = ()) -> None:
    """Último portão: o prompt inteiro tem de passar na máscara sem mudar e não pode ter símbolo de moeda. Não diz o que casou.

    `nomes` (o nome do cliente e variantes) vale só para a parte que muda a cada turno (blocos 4 a 8): o texto fixo (sistema, módulo,
    ferramentas) cita «Amado Batista» e palavras comuns, e um cliente de mesmo nome faria o turno falhar sem motivo."""
    auditar_textos(contexto.sistema, contexto.usuario, nomes)


def auditar_textos(fixo: str, variavel: str, nomes: Collection[str] = ()) -> None:
    """A mesma auditoria sobre textos soltos (o retorno de ferramenta usa só a parte variável). Não diz o que casou."""
    visto = normalizar(f"{fixo}\n{variavel}")  # também na vista NFKC: `Ｒ＄` e `ｈｔｔｐ：／／` de largura inteira não escapam do portão
    if mascarar(fixo) != fixo or mascarar(variavel, nomes) != variavel or _PROIBIDO_NO_PROMPT.search(visto) or ha_link(visto):
        raise ContextoComDadoPessoal("o prompt montado ainda tem dado pessoal, valor ou link; o turno não sai")


# --- leitura do banco --------------------------------------------------------------------------------------------------------------------


def _ler_perfil(conn: psycopg.Connection, atendimento_id: UUID | str) -> Mapping[str, Any]:
    linha = conn.execute("SELECT perfil FROM ia.atendimento WHERE atendimento_id = %s", (atendimento_id,)).fetchone()
    return linha[0] if linha and isinstance(linha[0], dict) else {}


def _textos_pendentes(
    conn: psycopg.Connection, atendimento_id: UUID | str, chaveiro: Chaveiro, ordens: Sequence[int]
) -> dict[int, tuple[int, str | None]]:
    """`passo.ordem` da mensagem recebida -> (`seq` da conversa, texto decifrado). Texto `None` = chave mensal descartada."""
    if not ordens:
        return {}
    linhas = conn.execute(
        "SELECT passo_ordem, seq, remetente, chave_id, nonce, cifra FROM ia.conversa_cifrada WHERE atendimento_id = %s"
        " AND tipo = 'mensagem' AND remetente = 'cliente' AND passo_ordem = ANY(%s)",
        (atendimento_id, list(ordens)),
    ).fetchall()
    achados: dict[int, tuple[int, str | None]] = {}
    for ordem, seq, remetente, chave_id, nonce, cifra in linhas:
        try:
            texto = chaveiro.decifrar(chave_id, bytes(nonce), bytes(cifra), atendimento_id, seq=seq, remetente=remetente, tipo="mensagem")
        except ChaveDesconhecida:
            texto = None
        achados[ordem] = (seq, texto)
    return achados


def _campo_a_ocultar(estado: EstadoConversa, desvio_liberado: bool) -> str | None:
    """Na E5 (modo guiado) a mensagem é o valor do campo: oculta, salvo `desvio_liberado` (a regra de desvio do B5.3 é de quem chama)."""
    if estado.fase != "E5" or desvio_liberado:
        return None
    return estado.campos_faltantes[0] if estado.campos_faltantes else "campo"


def _linhas_pendentes(
    pendentes: Sequence[Pendente],
    achados: Mapping[int, tuple[int, str | None]],
    nomes: Collection[str],
    ocultar_como: str | None = None,
) -> tuple[str, ...]:
    """Uma linha por pendente. `ocultar_como` (campo da E5) troca o TEXTO por `[dado:<campo>]`: o modelo nem vê o que o cliente digitou."""
    omitidas = max(len(pendentes) - MAX_PENDENTES_NO_PROMPT, 0)
    pendentes = pendentes[omitidas:]
    limite = max(CARACTERES_MINIMOS_POR_PENDENTE, CARACTERES_DAS_PENDENTES // max(len(pendentes), 1))
    linhas = [f"[{omitidas} mensagens anteriores omitidas]"] if omitidas else []
    for pendente in pendentes:
        if pendente.msg_tipo != "texto":
            linhas.append(f"[mídia sem texto: {pendente.msg_tipo}]")
            continue
        if ocultar_como is not None:
            linhas.append(f"[dado:{ocultar_como}]")
            continue
        texto = achados.get(pendente.ordem, (0, None))[1]
        linhas.append(_cortar(proteger_texto(texto, nomes), limite) if texto else "[mensagem indisponível]")
    return tuple(linhas)


# --- estado e resultados para o modelo ---------------------------------------------------------------------------------------------------


class Apelidos:
    """`oferta-1`, `opcao-2`...: o modelo cita a referência pelo apelido e o processador (B1.6) volta ao id real por `referencias`."""

    def __init__(self, mapa: Mapping[str, str] | None = None) -> None:
        """`mapa` (apelido → id real) semeia os apelidos já dados no contexto: o mesmo id real recebe o MESMO apelido no resultado de
        ferramenta."""
        self.mapa: dict[str, str] = {}
        self._por_valor: dict[tuple[str, str], str] = {}
        for apelido, real in (mapa or {}).items():
            self.mapa[apelido] = real
            self._por_valor[(apelido.rsplit("-", 1)[0], real)] = apelido

    def de(self, prefixo: str, real: str) -> str:
        existente = self._por_valor.get((prefixo, real))
        if existente is not None:
            return existente
        apelido = f"{prefixo}-{sum(1 for p, _ in self._por_valor if p == prefixo) + 1}"
        self._por_valor[(prefixo, real)] = apelido
        self.mapa[apelido] = real
        return apelido


def _estado_para_o_modelo(
    estado: EstadoConversa, perfil: Mapping[str, Any], janela_aberta: bool, apelidos: Apelidos, nomes: Collection[str]
) -> str:
    corpo: dict[str, Any] = {"fase": estado.fase}
    if contadores := estado.contadores.model_dump(exclude_defaults=True):
        corpo["contadores"] = contadores
    if (oferta := estado.oferta_corrente) is not None and estado.fase in FASES_COM_VALORES:
        banco = oferta.banco if oferta.banco in BANCOS else "OUTRO"  # o `OfertaCorrente` aceita `[A-Z0-9_]+`: no prompt só o catálogo
        corpo["oferta"] = {"ref": apelidos.de("oferta", oferta.oferta_id), "banco": banco, "versao": oferta.oferta_versao}
    if placeholders := PLACEHOLDERS_DA_FASE.get(estado.fase):
        corpo["placeholders"] = list(placeholders)
    if estado.opcoes_t5:
        corpo["opcoes"] = [apelidos.de("opcao", ref) for ref in estado.opcoes_t5]
    if estado.confirmacao is not None:
        corpo["confirmacao"] = estado.confirmacao.estado
    for nome in ("campos_coletados", "campos_faltantes", "objecoes", "intencoes_recentes", "contexto_previo"):
        if valor := getattr(estado, nome):
            corpo[nome] = list(valor)
    if estado.tentativa_t7 is not None:
        corpo["tentativa_t7"] = estado.tentativa_t7.model_dump(exclude_none=True)
    if estado.pausa is not None:
        corpo["pausa"] = {"retoma_fase": estado.pausa.retoma_fase}
    corpo["flags"] = {**estado.flags, "janela_aberta": janela_aberta}
    lead = {chave: valor for chave in PERFIL_PARA_O_MODELO if (valor := _valor_do_lead(chave, perfil.get(chave), nomes)) is not None}
    if lead:
        corpo["lead"] = lead
    return json.dumps(corpo, ensure_ascii=False, separators=(",", ":"))


def _sem_nome(texto: str, nomes: Collection[str]) -> bool:
    """O texto passa na máscara (com os nomes da conversa) sem mudar: nenhum nome, CPF, telefone ou e-mail dentro."""
    return mascarar(texto, nomes) == texto


def _valor_do_lead(chave: str, valor: Any, nomes: Collection[str]) -> Any:
    """O valor da chave do `perfil` se obedece à regra DA PRÓPRIA CHAVE (enum fechado ou limite inteiro); senão `None` (descartado).
    Inteiro só em chave com limite inteiro (um `{"banco": 5000}` não passa) e `bool` nunca (é `int` em Python)."""
    if valor is None or isinstance(valor, bool):
        return None
    if chave in LIMITES_INTEIROS_DO_LEAD:
        return valor if isinstance(valor, int) and 0 <= valor <= LIMITES_INTEIROS_DO_LEAD[chave] else None
    if not isinstance(valor, str) or not _sem_nome(valor, nomes):
        return None
    return valor if valor in LEAD_ENUMS.get(chave, frozenset()) else None


def _escalar_seguro(valor: Any) -> tuple[bool, Any]:
    """Escalar de RESULTADO de ferramenta que pode ir ao modelo: `None`, booleano ou contador pequeno. Texto nunca (só por domínio
    fechado)."""
    if valor is None or isinstance(valor, bool):
        return True, valor
    if isinstance(valor, int) and 0 <= valor <= MAX_INTEIRO_DE_RESULTADO:
        return True, valor
    return False, None


def _no_dominio(valor: Any, dominio: frozenset[str], nomes: Collection[str] = ()) -> bool:
    """Texto do catálogo fechado e que a máscara (com os nomes da conversa) não trocaria: um cliente chamado «Pago» não leva o macro
    «pago»."""
    return isinstance(valor, str) and valor in dominio and _sem_nome(valor, nomes)


def _projetar(valor: Any, regra: Any, chave: str, apelidos: Apelidos, nomes: Collection[str]) -> tuple[bool, Any]:
    if isinstance(regra, frozenset):  # domínio fechado: texto ou lista de textos, e só o que está no catálogo
        if isinstance(valor, (list, tuple)):
            itens = [v for v in valor if _no_dominio(v, regra, nomes)][:MAX_ITENS_DE_LISTA]
            return bool(itens), itens
        return _no_dominio(valor, regra, nomes), valor
    if regra is True:
        if chave in _ALIAS_DE_REF and isinstance(valor, (str, int)) and not isinstance(valor, bool):
            return True, apelidos.de(_ALIAS_DE_REF[chave], str(valor))  # id real (até UUID) nunca vai ao modelo: vai o apelido
        return _escalar_seguro(valor)
    if isinstance(regra, Mapping):
        if isinstance(valor, Mapping):
            return True, _projetar_objeto(valor, regra, apelidos, nomes)
        if isinstance(valor, (list, tuple)):
            return True, [
                _projetar_objeto(item, regra, apelidos, nomes) for item in valor[:MAX_ITENS_DE_LISTA] if isinstance(item, Mapping)
            ]
    return False, None


def _projetar_objeto(bruto: Mapping[str, Any], regra: Mapping[str, Any], apelidos: Apelidos, nomes: Collection[str]) -> dict[str, Any]:
    saida: dict[str, Any] = {}
    for chave, sub in regra.items():
        if chave in bruto:
            ok, valor = _projetar(bruto[chave], sub, chave, apelidos, nomes)
            if ok:
                saida[chave] = valor
    return saida


def projetar_resultado(resultados: Mapping[str, Mapping[str, Any]], apelidos: Apelidos, nomes: Collection[str] = ()) -> str:
    """Bloco 7: só as chaves da allowlist de cada ferramenta, com ids trocados por apelidos. Ferramenta fora da lista é descartada."""
    projetado = {
        nome: _projetar_objeto(bruto, PROJECAO_DAS_FERRAMENTAS[nome], apelidos, nomes)
        for nome, bruto in resultados.items()
        if nome in PROJECAO_DAS_FERRAMENTAS and isinstance(bruto, Mapping)
    }
    projetado = {nome: valores for nome, valores in projetado.items() if valores}  # ferramenta que não deixou nada passar não aparece
    return json.dumps(projetado, ensure_ascii=False, separators=(",", ":")) if projetado else ""


def _linhas_das_trocas(mensagens: Sequence[Any], nomes: Collection[str]) -> tuple[str, ...]:
    return tuple(f"[{m.remetente}] {proteger_texto(m.texto, nomes)}" for m in mensagens)


def _exemplos_da_fase(exemplos: Sequence[ExemploDaFase], fase: str, nomes: Collection[str]) -> tuple[str, ...]:
    do_prompt = [e for e in exemplos if e.fase == fase][:EXEMPLOS_POR_FASE]
    return tuple(
        f"Cliente: «{proteger_texto(e.cliente, nomes)}» -> "
        + json.dumps(e.saida.model_dump(mode="json", exclude_defaults=True), ensure_ascii=False, separators=(",", ":"))
        for e in do_prompt
    )


# --- montagem ----------------------------------------------------------------------------------------------------------------------------


def montar_contexto(
    conn: psycopg.Connection,
    atendimento_id: UUID | str,
    *,
    pendentes: Sequence[Pendente],
    chaveiro: Chaveiro,
    nomes: Collection[str] | None,
    agora: datetime,
    resultados: Mapping[str, Mapping[str, Any]] | None = None,
    exemplos: Sequence[ExemploDaFase] = (),
    estimador: EstimadorDeTokens = ESTIMADOR_PADRAO,
    teto: int = TETO_TOKENS,
    desvio_liberado: bool = False,
    tokens_das_ferramentas: Callable[[str], int] | None = None,
) -> Contexto:
    """Lê o atendimento, a conversa cifrada e o `perfil`; monta os 8 blocos, corta até caber em `teto` e audita o prompt.

    `nomes` é obrigatório (`None` recusa, como a conversa): sem os nomes da conversa não há como mascarar o texto. `agora` vem do relógio
    injetado. Fase sem turno do modelo (E0, E1, E9): `FaseSemTurnoDoModelo`. Os `resultados` das ferramentas já vêm como o gateway os
    devolveu: aqui só passa a allowlist."""
    if nomes is None:
        raise NomesIndisponiveis("nomes da conversa não informados; passe () só se já conferiu que não há nome a esconder")
    atendimento = ler_atendimento(conn, atendimento_id)
    estado = estado_conversa_de_json(atendimento.estado_conversa)
    if estado.fase in FASES_SEM_TURNO_DO_MODELO:
        raise FaseSemTurnoDoModelo(f"a fase {estado.fase} não tem turno do modelo")
    achados = _textos_pendentes(conn, atendimento_id, chaveiro, [p.ordem for p in pendentes])
    seqs_pendentes = {seq for seq, _ in achados.values()}
    conversa = ler_trocas(conn, atendimento_id, chaveiro=chaveiro, trocas=TROCAS_NO_PROMPT + len(pendentes))
    historico = [m for m in conversa.mensagens if m.seq not in seqs_pendentes][-2 * TROCAS_NO_PROMPT :]
    apelidos = Apelidos()
    janela = janela_24h_aberta(atendimento.ultimo_cliente_em, agora)
    insumos = Insumos(
        fase=estado.fase,
        estado=_estado_para_o_modelo(estado, _ler_perfil(conn, atendimento_id), janela, apelidos, nomes),
        modulo=modulo_da_fase(estado.fase),  # type: ignore[arg-type]
        ferramentas=esquemas_das_ferramentas(estado.fase),  # type: ignore[arg-type]
        exemplos=_exemplos_da_fase(exemplos, estado.fase, nomes),
        resumo=proteger_texto(conversa.resumo, nomes) if conversa.resumo else None,
        trocas=_linhas_das_trocas(historico, nomes),
        resultados=projetar_resultado(resultados or {}, apelidos, nomes),
        pendentes=_linhas_pendentes(pendentes, achados, nomes, _campo_a_ocultar(estado, desvio_liberado)),
    )
    extra = tokens_das_ferramentas(estado.fase) if tokens_das_ferramentas is not None else 0
    contexto = cortar_ate_caber(construir(insumos, apelidos.mapa, estimador, (), extra), teto)
    auditar_prompt(contexto, nomes)
    return contexto


def ler_do_prompt(usuario: str) -> tuple[str | None, tuple[str, ...]]:
    """Faz o caminho inverso do bloco 4 e do 8: (fase, mensagens pendentes) do texto da mensagem do usuário. Para o `ProvedorFalso`."""
    achou = _FASE_NO_ESTADO.search(usuario)
    secao = usuario.split(CABECALHO_PENDENTES, 1)[1] if CABECALHO_PENDENTES in usuario else ""
    textos = tuple(m.group(1) for linha in secao.splitlines() if (m := _LINHA_DE_PENDENTE.match(linha)))
    return (achou.group(1) if achou else None), textos


__all__ = [
    "CABECALHO_PENDENTES",
    "FASES_COM_VALORES",
    "FASES_DO_T2",
    "FRASES_DO_T10",
    "LEAD_ENUMS",
    "MACROS_DA_PROPOSTA",
    "PERFIL_PARA_O_MODELO",
    "PLACEHOLDERS_DA_FASE",
    "PROJECAO_DAS_FERRAMENTAS",
    "PROXIMAS_ACOES_DO_T10",
    "STATUS_DA_OFERTA",
    "TETO_TOKENS",
    "Bloco",
    "Contexto",
    "ContextoComDadoPessoal",
    "ContextoNaoCabe",
    "ExemploDaFase",
    "FalhaDoContexto",
    "FaseSemTurnoDoModelo",
    "Insumos",
    "auditar_prompt",
    "construir",
    "cortar_ate_caber",
    "ler_do_prompt",
    "montar_contexto",
    "projetar_resultado",
    "proteger_texto",
]
