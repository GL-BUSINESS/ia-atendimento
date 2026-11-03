"""Proteção do texto que vai ao prompt (B1.4, H §3.3/P3): a máscara de PII outra vez, mais valor, prazo, data e número «nu».

`proteger_texto` é a ÚLTIMA cerca do texto de cliente (ou da IA) antes do modelo; a primeira é a máscara da gravação
(`conversa.gravar_troca`). Em ordem:

0. vista NFKC do texto (largura inteira, pontos ideográficos: `ｈｔｔｐ：／／` é `http://`); o resto olha SEMPRE esta vista;
1. `mascarar` (CPF, telefone, e-mail, CEP, UUID, 8+ dígitos e os nomes da conversa), que é idempotente; link digitado (esquema, `www.` ou
   host com TLD conhecido, até o próximo espaço) vira `[LINK]` (H §3.3);
2. data completa (`dd/mm/aaaa`) vira `[DATA]`: nascimento é dado que H §3.3 proíbe; a data de agendamento do cliente não leva o ano
   («dia 5», «05/11») e fica;
3. dinheiro (`R$ 5.000,00`, `3 mil`, `800 reais`, `5k`) e prazo (`36x`, `12 parcelas`, `60 meses`) viram `[VALOR]` e `[PRAZO]`; um `r$`
   ou `us$` solto também é `[VALOR]` (senão a auditoria final derrubaria o turno por causa de um «r$» sem número, M-7);
4. **todo número com 2 ou mais dígitos** que não seja HORA, DIA ou DURAÇÃO vira `[NUMERO]` (M-1, M-2): `quero 5000`, `a parcela de 312,45`,
   `prazo de 84`, `conta 123456-7`, `agência 1234`, `matrícula 1234567`. O que fica: `15h30`, `às 9`, `7 da noite`, `dia 5`, `05/11`,
   `10 de nov`, `daqui a 40 minutos`, `2 horas` (o `adiar_com_hora` precisa deles);
5. linha única e sem os delimitadores «» (a mensagem do cliente não forja cabeçalho nem fecha aspas).

O número do pedido («queria 250 por mês») é extraído por CÓDIGO da mensagem (H P3, `alvo_pedido`); o modelo só precisa da palavra em volta.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Collection
from typing import Final

from ia_atendimento.mascara import mascarar

# Link que o cliente digitou (H §3.3: URL/link nunca entra no prompt). Depois de casar o ESQUEMA (`xxx://`), `www.` ou o host com TLD
# conhecido, o link vai até o próximo espaço: porta, caminho, `?query` e `#fragmento` não ficam no texto (um `.evil.xyz/…` ou
# `:8080?token=…` chegava ao provedor).
LIMITE_DA_ENTRADA: Final = 1000  # caracteres do texto cru que entram na proteção (R2-01)
JANELA_DA_PALAVRA: Final = 100  # ao cortar, volta até aqui procurando o fim da palavra anterior
_TLDS: Final = (
    "com|net|org|br|io|app|me|link|ly|xyz|info|biz|site|online|top|club|shop|store|tech|dev|cc|co|tk|ml|ga|cf|gq|ru|cn|pw|click|live|win|vip|fun|ws|gl"
    "|page|cloud|digital"
)
# Início de token: a lookbehind dupla impede de COMEÇAR no meio de uma cadeia de host («palavra.» + outra) e assim o regex não parte de cada
# segmento e varre até o fim, O(n²) (4.000 caracteres = 1 s, R2-01). Os caracteres são os de HOST (ASCII): com `\w` (que inclui `_` e letras
# acentuadas) `joão.evil.xyz/x`, `a_b.evil.com/x` e `ç.www.evil.com` não casavam e o link passava. `x..y.com/a` ainda começa em `y`.
_ANTES_DO_HOST: Final = r"(?<![a-z0-9\-])(?<![a-z0-9\-]\.)"
_ANTES_DO_ESQUEMA: Final = (
    r"(?<![a-z0-9+\-])(?<![a-z0-9+\-]\.)"  # `+` conta: o esquema (`a+b+c:`) varre até o fim se puder recomeçar em cada `+`
)
# Host com SINAL DE CAMINHO (`/`, `#`, `?x`, `:porta`) é link com QUALQUER TLD (`meusite.company/oferta`, `x.tv/abc`, `exemplo.test/pagar`).
# Sem o sinal, só a lista de TLDs acima: a regra larga «qualquer x.y» faria de `sim.pode` um link (e «sim.pode» é um SIM na E6).
# O `?` só conta com algo colado depois (`sim.pode?` é pergunta). Host nu fora da lista (`meusite.company`) é risco aceito (B8.2 mede).
_SINAL_DE_CAMINHO: Final = r"(?=/|#|\?\S|:\d{2,5}(?!\d))"
_LINK: Final = re.compile(
    rf"(?i){_ANTES_DO_ESQUEMA}(?:[a-z][a-z0-9+.\-]*://|www\.)\S+"
    rf"|{_ANTES_DO_HOST}\.?(?:[a-z0-9-]+\.)+(?:{_TLDS})\b\S*"
    rf"|{_ANTES_DO_HOST}(?:[a-z0-9-]+\.)+[a-z]{{2,24}}{_SINAL_DE_CAMINHO}\S*"
)
_PONTO_IDEOGRAFICO: Final = {"\u3002": ".", "\uff61": "."}  # «。» e «｡»: NFKC não os leva a «.»
_DATA_COMPLETA: Final = re.compile(r"(?<!\d)(?:0?[1-9]|[12]\d|3[01])([/.\-])(?:0?[1-9]|1[0-2])\1(?:19|20)\d{2}(?!\d)")
_DINHEIRO: Final = re.compile(
    r"(?i)(?<![\w])(?:r\$|rs)\s*\d[\d.,]*(?:\s*(?:mil|milh(?:ão|ões|ao|oes)|k|reais))?(?![\w])"
    r"|(?<![\w])\d[\d.,]*\s*(?:mil|milh(?:ão|ões|ao|oes)|k|reais?|contos?|pilas?|mangos?)(?![\w])"
)
_PRAZO: Final = re.compile(r"(?i)(?<![\w])\d{1,3}\s*(?:x|vezes|parcelas?|meses|mês|mes)(?![\w])")
_SIMBOLO_DE_MOEDA_SOLTO: Final = re.compile(r"(?i)(?:r|us)\$")
_MESES: Final = r"(?:jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\w*"
# Número que FICA (hora, dia, duração) ou que VIRA `[NUMERO]` (2+ dígitos, com os separadores que acompanham dinheiro, conta e matrícula).
# As alternativas permitidas vêm primeiro: a regex pega a primeira que casa na posição mais à esquerda e devolve o trecho intacto.
_NUMERO: Final = re.compile(
    r"(?i)"
    r"(?P<fica>"
    r"(?<![\w.,/:\-])\d{1,2}\s*h(?:\s*\d{2})?(?![\w])"  # 9h, 15h30, 2h
    r"|(?<![\w.,/:\-])\d{1,2}:\d{2}(?::\d{2})?(?![\w])"  # 15:30
    r"|(?<![\w.,/:\-])\d{1,3}\s*(?:min(?:utos?)?|horas?|dias?|semanas?|segundos?)(?![\w])"  # 40 minutos, 2 horas
    r"|(?<![\w])dia\s+\d{1,2}(?![\d.,/:\-])"  # dia 5
    r"|(?<![\w.,/:\-])\d{1,2}/\d{1,2}(?![\d/:\-.,]*\d)"  # 05/11 (sem ano)
    r"|(?<![\w])(?:[aà]s|pelas|das|umas?)\s+\d{1,2}(?![\d.,/:\-]|\s*h)"  # às 9, depois das 6, umas 6
    r"|(?<![\w.,/:\-])\d{1,2}\s+da\s+(?:manh[ãa]|tarde|noite|madrugada)(?![\w])"  # 7 da noite
    rf"|(?<![\w.,/:\-])\d{{1,2}}\s+de\s+{_MESES}"  # 10 de nov
    r")"
    r"|(?P<numero>\d[\d.,/\-]*\d)"
)


def _normalizar_caractere(caractere: str) -> str:
    normal = unicodedata.normalize("NFKC", caractere)
    return _PONTO_IDEOGRAFICO.get(normal, normal) if len(normal) == 1 else caractere


def normalizar(texto: str) -> str:
    """Vista NFKC caractere a caractere (largura inteira, círculos e pontos ideográficos viram ASCII) com o MESMO comprimento: a URL
    de largura inteira vira `http://...`. Um caractere cuja forma NFKC tem outro tamanho (`…`, `™`) fica como está. Todo validador
    olha esta vista."""
    return "".join(_normalizar_caractere(c) for c in texto)


def ha_link(texto: str) -> bool:
    """O texto (na vista normalizada) ainda tem link? Usado pela auditoria final: o que a proteção devia ter trocado e não trocou."""
    return _LINK.search(normalizar(texto)) is not None


def _trocar_numero(achado: re.Match[str]) -> str:
    return achado.group("fica") if achado.group("fica") is not None else "[NUMERO]"


def cortar_entrada(texto: str) -> str:
    """Corta o texto CRU antes de qualquer regex: o prompt nunca mostra mais de ~560 caracteres de uma mensagem e o evento aceita até
    4.000. Corta na última palavra inteira (um CPF ou nome partido ao meio não deixa fragmento) e marca com «…». O cortado não vai a
    lugar nenhum."""
    if len(texto) <= LIMITE_DA_ENTRADA:
        return texto
    corte = texto[:LIMITE_DA_ENTRADA]
    if not texto[LIMITE_DA_ENTRADA].isspace():  # cortou no meio de uma palavra: descarta o pedaço dela
        espaco = max(corte.rfind(" "), corte.rfind("\n"), corte.rfind("\t"))
        if espaco >= LIMITE_DA_ENTRADA - JANELA_DA_PALAVRA:
            corte = corte[:espaco]
    return corte.rstrip() + " …"


def proteger_texto(texto: str, nomes: Collection[str]) -> str:
    """Texto de cliente (ou da IA) pronto para o prompt (ver o docstring do módulo). Idempotente."""
    texto = cortar_entrada(texto)
    protegido = _LINK.sub("[LINK]", mascarar(normalizar(texto), nomes))  # tudo olha a vista normalizada (largura inteira não escapa)
    protegido = _DATA_COMPLETA.sub("[DATA]", protegido)
    protegido = _PRAZO.sub("[PRAZO]", _DINHEIRO.sub("[VALOR]", protegido))
    protegido = _SIMBOLO_DE_MOEDA_SOLTO.sub("[VALOR]", protegido)
    protegido = _NUMERO.sub(_trocar_numero, protegido)
    return re.sub(r"\s+", " ", protegido.replace("«", "").replace("»", "")).strip()
