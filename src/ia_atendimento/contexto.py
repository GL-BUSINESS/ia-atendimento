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

**O modelo nunca recebe** CPF, telefone, e-mail, nome, valor, prazo da oferta nem texto sem máscara (H §3.3, P3): o texto de cliente
passa pela
máscara outra vez aqui (defesa em profundidade; a máscara é idempotente), valores em reais e prazos que o próprio cliente digitou viram
`[VALOR]`/`[PRAZO]`, o resultado de ferramenta só deixa passar o que a allowlist nomeia e antes da fase E3 (Q1: abertura sem valores) nem a
oferta aparece. Ids reais (oferta, opções, agendamento) viram apelidos (`oferta-1`, `opcao-2`); `Contexto.referencias` diz o que cada um é.
Por fim `auditar_prompt` confere o prompt inteiro contra a máscara: se algo ainda mudaria, o turno não sai (`ContextoComDadoPessoal`).

**Teto de 4.000 tokens de entrada.** A contagem é uma ESTIMATIVA (HIPÓTESE, `tokens.py`; medir com o tokenizer do DeepSeek em B8.2) e
inclui o formato
`Turno`. Acima do teto cortam-se, NESTA ordem: resumo → trocas antigas (de duas em duas, fica a última) → exemplos da fase (um a um).
Se ainda
não couber, `ContextoNaoCabe`: o turno conta como falha do modelo. Nada além dessas três coisas é opcional.
"""

from __future__ import annotations

import json
import re
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Final
from uuid import UUID

import psycopg

from ia_atendimento.cifra import ChaveDesconhecida, Chaveiro
from ia_atendimento.conversa import NomesIndisponiveis, ler_trocas
from ia_atendimento.estado import ler as ler_atendimento
from ia_atendimento.estado_conversa import estado_conversa_de_json, janela_24h_aberta
from ia_atendimento.linha_tempo import Pendente
from ia_atendimento.mascara import mascarar
from ia_atendimento.modelos_conversa import EstadoConversa
from ia_atendimento.modulos_fase import FASES_SEM_TURNO_DO_MODELO, SISTEMA, esquemas_das_ferramentas, modulo_da_fase
from ia_atendimento.tokens import ESTIMADOR_PADRAO, EstimadorDeTokens
from ia_atendimento.turno import Turno, formato_do_turno

TETO_TOKENS: Final = 4000  # H §3.1: teto duro de entrada
TROCAS_NO_PROMPT: Final = 3
EXEMPLOS_POR_FASE: Final = 2
MENSAGENS_MINIMAS_APOS_CORTE: Final = 2  # a última troca nunca sai: é o que a IA acabou de perguntar e a resposta do cliente
CARACTERES_DAS_PENDENTES: Final = 560  # ~200 tokens (teto do bloco 8); dividido pela rajada
CARACTERES_MINIMOS_POR_PENDENTE: Final = 120
TETOS_DO_BLOCO: Final = {1: 800, 2: 650, 3: 600, 4: 600, 5: 300, 6: 700, 7: 400, 8: 200}  # H §3.1 (referência; só o total é imposto)
NOMES_DOS_BLOCOS: Final = {
    1: "sistema", 2: "modulo_da_fase", 3: "ferramentas", 4: "estado", 5: "resumo", 6: "trocas", 7: "resultados", 8: "pendentes",
}  # fmt: skip

CABECALHO_PENDENTES: Final = "## Mensagens pendentes do cliente"
CABECALHO_TROCAS: Final = "## Últimas trocas (mascaradas)"
CABECALHO_RESUMO: Final = "## Resumo da conversa"
CABECALHO_ESTADO: Final = "## Estado"
CABECALHO_RESULTADOS: Final = "## Resultado das ferramentas neste turno"
# Chaves do `perfil` que o modelo pode ver (n §2.2/§3: quem falou por último, tipo da última fala, etapa do in-app). Faixas de parcela ou
# valor ficam de fora: são valores. Chave fora daqui não chega ao prompt, exista ou não no `perfil`.
PERFIL_PARA_O_MODELO: Final = (
    "banco", "etapa_inapp", "etapas_do_robo_concluidas", "idade_do_lead_min", "origem", "tipo_ultima_fala", "ultimo_sentido",
)  # fmt: skip
FASES_COM_VALORES: Final = frozenset({"E3", "E4", "E5", "E6", "E7", "E8"})  # Q1: antes da E3 nem a oferta aparece no estado
PLACEHOLDERS_DA_FASE: Final[Mapping[str, tuple[str, ...]]] = {
    "E2": ("nome",),
    "E3": ("nome", "banco", "valor_liberado", "valor_parcela", "prazo"),
    "E4": ("nome", "banco", "valor_liberado", "valor_parcela", "prazo", "pedido"),
    "E5": ("nome", "campo"),
    "E6": ("nome", "banco", "valor_liberado", "valor_parcela", "prazo", "destino"),
    "E7": ("nome",),
    "E8": ("nome", "banco", "link"),
    "E10": (),
}
# Resultado de ferramenta ao modelo: SÓ o que está aqui (`True` = folha permitida; dict = objeto/lista de objetos). Valor em reais, prazo,
# coeficiente, comissão e motivo cru do banco não estão em nenhuma lista: não passam, mesmo que a ferramenta os devolva.
PROJECAO_DAS_FERRAMENTAS: Final[Mapping[str, Mapping[str, Any]]] = {
    "T2": {"status": True, "etapa": True, "contrato_vivo": True, "proposta_viva": True},
    "T3": {"oferta_ref": True, "status": True, "versao": True, "vencida": True, "mudou": True, "placeholders": True},
    "T5": {"opcoes": {"opcao_ref": True, "dentro_da_alcada": True, "placeholders": True}, "sem_opcao": True, "acima_do_maximo": True},
    "T10": {"macro": True, "status": True},
}
MAX_ITENS_DE_LISTA: Final = 5
MAX_INTEIRO_DE_RESULTADO: Final = 99  # contador; acima disso pode ser valor, prazo ou id (ver o teste de projeção)
MAX_INTEIRO_DO_LEAD: Final = 9999  # `idade_do_lead_min`: minutos desde a simulação
_FOLHA_TEXTO: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,39}$")
_PARECE_NUMERO: Final = re.compile(
    r"^[0-9][0-9.,:-]*$|[0-9][.,][0-9]{2}(?![0-9])"
)  # «5000.00», «1,5»: dinheiro ou taxa disfarçados de código
_ALIAS_DE_REF: Final = {"oferta_ref": "oferta", "opcao_ref": "opcao"}

_DINHEIRO: Final = re.compile(
    r"(?i)(?<![\w])(?:r\$|rs)\s*\d[\d.,]*(?:\s*(?:mil|milh(?:ão|ões|ao|oes)|k|reais))?(?![\w])"
    r"|(?<![\w])\d[\d.,]*\s*(?:mil|milh(?:ão|ões|ao|oes)|k|reais?|contos?|pilas?|mangos?)(?![\w])"
)
_PRAZO: Final = re.compile(r"(?i)(?<![\w])\d{1,3}\s*(?:x|vezes|parcelas?|meses|mês|mes)(?![\w])")
_PROIBIDO_NO_PROMPT: Final = re.compile(r"(?i)r\$|us\$")
_LINHA_DE_PENDENTE: Final = re.compile(r"^\d+\. «(.*)»$")
_FASE_NO_ESTADO: Final = re.compile(r'"fase":"(E(?:10|[0-9]))"')


# --- erros -------------------------------------------------------------------------------------------------------------------------------


class ContextoErro(Exception):
    """Base. As mensagens trazem números e nomes de campo, nunca texto."""


class FaseSemTurnoDoModelo(ContextoErro, ValueError):
    """E0, E1 e E9 não têm turno do modelo (H §2.3): montar o contexto delas é erro do chamador."""


class ContextoNaoCabe(ContextoErro):
    """Mesmo sem resumo, trocas antigas e exemplos o prompt passa do teto: o turno conta como falha do modelo (B1.6 repassa na 2ª)."""

    def __init__(self, tokens: int, teto: int) -> None:
        super().__init__(f"contexto de {tokens} tokens acima do teto de {teto} depois de cortar tudo que era opcional")
        self.tokens = tokens
        self.teto = teto


class ContextoComDadoPessoal(ContextoErro):
    """A máscara ainda mudaria o prompt montado (ou há símbolo de moeda): nada vai ao modelo. Não diz o que casou."""


# --- proteção do texto -------------------------------------------------------------------------------------------------------------------


def proteger_texto(texto: str, nomes: Collection[str]) -> str:
    """Texto de cliente (ou da IA) pronto para o prompt: máscara de PII outra vez, valor em reais e prazo digitados viram
    `[VALOR]`/`[PRAZO]`,
    linha única e sem os delimitadores «» (a mensagem do cliente não forja cabeçalho nem fecha aspas)."""
    protegido = _PRAZO.sub("[PRAZO]", _DINHEIRO.sub("[VALOR]", mascarar(texto, nomes)))
    return re.sub(r"\s+", " ", protegido.replace("«", "").replace("»", "")).strip()


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

    @property
    def tokens_total(self) -> int:
        return sum(b.tokens for b in self.blocos) + self.tokens_formato

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


def construir(insumos: Insumos, referencias: Mapping[str, str], estimador: EstimadorDeTokens, cortes: tuple[str, ...] = ()) -> Contexto:
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
    return Contexto(insumos.fase, blocos, estimador.contar(formato_do_turno()), cortes, dict(referencias), insumos, estimador)


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
        atual = construir(insumos, atual.referencias, atual.estimador, (*atual.cortes, nome))
    return atual


def auditar_prompt(contexto: Contexto) -> None:
    """Último portão: o prompt inteiro tem de passar na máscara sem mudar e não pode ter símbolo de moeda. Não diz o que casou."""
    prompt = f"{contexto.sistema}\n{contexto.usuario}"
    if mascarar(prompt) != prompt or _PROIBIDO_NO_PROMPT.search(prompt):
        raise ContextoComDadoPessoal("o prompt montado ainda tem dado pessoal ou valor; o turno não sai")


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


def _linhas_pendentes(
    pendentes: Sequence[Pendente], achados: Mapping[int, tuple[int, str | None]], nomes: Collection[str]
) -> tuple[str, ...]:
    limite = max(CARACTERES_MINIMOS_POR_PENDENTE, CARACTERES_DAS_PENDENTES // max(len(pendentes), 1))
    linhas = []
    for pendente in pendentes:
        if pendente.msg_tipo != "texto":
            linhas.append(f"[mídia sem texto: {pendente.msg_tipo}]")
            continue
        texto = achados.get(pendente.ordem, (0, None))[1]
        linhas.append(_cortar(proteger_texto(texto, nomes), limite) if texto else "[mensagem indisponível]")
    return tuple(linhas)


# --- estado e resultados para o modelo ---------------------------------------------------------------------------------------------------


class _Apelidos:
    """`oferta-1`, `opcao-2`...: o modelo cita a referência pelo apelido e o processador (B1.6) volta ao id real por `referencias`."""

    def __init__(self) -> None:
        self.mapa: dict[str, str] = {}
        self._por_valor: dict[tuple[str, str], str] = {}

    def de(self, prefixo: str, real: str) -> str:
        existente = self._por_valor.get((prefixo, real))
        if existente is not None:
            return existente
        apelido = f"{prefixo}-{sum(1 for p, _ in self._por_valor if p == prefixo) + 1}"
        self._por_valor[(prefixo, real)] = apelido
        self.mapa[apelido] = real
        return apelido


def _estado_para_o_modelo(estado: EstadoConversa, perfil: Mapping[str, Any], janela_aberta: bool, apelidos: _Apelidos) -> str:
    corpo: dict[str, Any] = {"fase": estado.fase}
    if contadores := estado.contadores.model_dump(exclude_defaults=True):
        corpo["contadores"] = contadores
    if (oferta := estado.oferta_corrente) is not None and estado.fase in FASES_COM_VALORES:
        corpo["oferta"] = {"ref": apelidos.de("oferta", oferta.oferta_id), "banco": oferta.banco, "versao": oferta.oferta_versao}
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
    seguros = {chave: _folha_segura(perfil.get(chave), MAX_INTEIRO_DO_LEAD) for chave in PERFIL_PARA_O_MODELO}
    if lead := {chave: valor for chave, (ok, valor) in seguros.items() if ok and valor is not None}:
        corpo["lead"] = lead
    return json.dumps(corpo, ensure_ascii=False, separators=(",", ":"))


def _folha_segura(valor: Any, maximo_inteiro: int = MAX_INTEIRO_DE_RESULTADO) -> tuple[bool, Any]:
    """Folha que pode ir ao modelo: booleano, contador pequeno ou código curto que a máscara não troca e que não parece dinheiro."""
    if valor is None or isinstance(valor, bool):
        return True, valor
    if isinstance(valor, int) and 0 <= valor <= maximo_inteiro:
        return True, valor
    if isinstance(valor, str) and _FOLHA_TEXTO.fullmatch(valor) and not _PARECE_NUMERO.search(valor) and mascarar(valor) == valor:
        return True, valor
    return False, None


def _projetar(valor: Any, regra: Any, chave: str, apelidos: _Apelidos) -> tuple[bool, Any]:
    if regra is True:
        if isinstance(valor, (list, tuple)):
            itens = [item for ok, item in map(_folha_segura, valor[:MAX_ITENS_DE_LISTA]) if ok]
            return bool(itens), itens
        if chave in _ALIAS_DE_REF and isinstance(valor, (str, int)) and not isinstance(valor, bool):
            return True, apelidos.de(_ALIAS_DE_REF[chave], str(valor))  # id real (até UUID) nunca vai ao modelo: vai o apelido
        return _folha_segura(valor)
    if isinstance(regra, Mapping):
        if isinstance(valor, Mapping):
            return True, _projetar_objeto(valor, regra, apelidos)
        if isinstance(valor, (list, tuple)):
            return True, [_projetar_objeto(item, regra, apelidos) for item in valor[:MAX_ITENS_DE_LISTA] if isinstance(item, Mapping)]
    return False, None


def _projetar_objeto(bruto: Mapping[str, Any], regra: Mapping[str, Any], apelidos: _Apelidos) -> dict[str, Any]:
    saida: dict[str, Any] = {}
    for chave, sub in regra.items():
        if chave in bruto:
            ok, valor = _projetar(bruto[chave], sub, chave, apelidos)
            if ok:
                saida[chave] = valor
    return saida


def projetar_resultado(resultados: Mapping[str, Mapping[str, Any]], apelidos: _Apelidos) -> str:
    """Bloco 7: só as chaves da allowlist de cada ferramenta, com ids trocados por apelidos. Ferramenta fora da lista é descartada."""
    projetado = {
        nome: _projetar_objeto(bruto, PROJECAO_DAS_FERRAMENTAS[nome], apelidos)
        for nome, bruto in resultados.items()
        if nome in PROJECAO_DAS_FERRAMENTAS and isinstance(bruto, Mapping)
    }
    return json.dumps(projetado, ensure_ascii=False, separators=(",", ":")) if any(projetado.values()) else ""


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
    apelidos = _Apelidos()
    janela = janela_24h_aberta(atendimento.ultimo_cliente_em, agora)
    insumos = Insumos(
        fase=estado.fase,
        estado=_estado_para_o_modelo(estado, _ler_perfil(conn, atendimento_id), janela, apelidos),
        modulo=modulo_da_fase(estado.fase),  # type: ignore[arg-type]
        ferramentas=esquemas_das_ferramentas(estado.fase),  # type: ignore[arg-type]
        exemplos=_exemplos_da_fase(exemplos, estado.fase, nomes),
        resumo=proteger_texto(conversa.resumo, nomes) if conversa.resumo else None,
        trocas=_linhas_das_trocas(historico, nomes),
        resultados=projetar_resultado(resultados or {}, apelidos),
        pendentes=_linhas_pendentes(pendentes, achados, nomes),
    )
    contexto = cortar_ate_caber(construir(insumos, apelidos.mapa, estimador), teto)
    auditar_prompt(contexto)
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
    "PERFIL_PARA_O_MODELO",
    "PLACEHOLDERS_DA_FASE",
    "PROJECAO_DAS_FERRAMENTAS",
    "TETO_TOKENS",
    "Bloco",
    "Contexto",
    "ContextoComDadoPessoal",
    "ContextoNaoCabe",
    "ExemploDaFase",
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
