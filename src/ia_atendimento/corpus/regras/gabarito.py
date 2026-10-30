"""Forma do gabarito dos diálogos: vocabulário, fases, TX, transições, silêncio, segurança, coleta da E5, SIM literal, janela de 24 h."""

from __future__ import annotations

import re
import unicodedata
from datetime import timedelta

from ia_atendimento.corpus.calendario import dentro_do_horario
from ia_atendimento.corpus.modelos import Corpus, Turno
from ia_atendimento.corpus.regras._comum import dialogos_com_persona, instantes, mensagem_da_ia
from ia_atendimento.corpus.vocabulario import (
    ACOES,
    ACOES_DE_SEGURANCA,
    CAMPOS_DA_E5,
    COMPOSTOS,
    FERRAMENTAS,
    FERRAMENTAS_POR_FASE,
    JANELA_WHATSAPP_HORAS,
    MAX_VARIACOES,
    SIMS,
    TRANSICOES,
    TX_FASES,
)

PEDIDO_DE_CONFIRMACAO = frozenset({"TX-11", "TX-12", "TX-13"})


def normalizar(texto: str) -> str:
    """minúsculas, sem acento, sem pontuação, espaços colapsados: «Sim!» → «sim»."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", sem_acento)).strip()


def redacoes(t: Turno) -> list[str]:
    return [t.texto_cliente or "", *t.variacoes]


def e_sim_literal(t: Turno) -> bool:
    """O TEXTO (e toda variação) do cliente está na lista fechada do SIM (H §2.3). «bora», «pode ser», «sim mas...» não estão."""
    return t.texto_cliente is not None and all(normalizar(x) in SIMS for x in redacoes(t))


def _campo_pedido_sem_alvo(t: Turno) -> bool:
    entrega = t.quem == "cliente" and t.fase_esperada == "E5" and t.intencao_esperada == "fornece_dado"
    return ("TX-07" in t.tx_esperado or entrega) and not t.campo_alvo


def dialogo_gabarito(corpus: Corpus) -> list[str]:
    """Vocabulário de ações, permitidas ∩ proibidas = ∅, intenção em todo turno do cliente, coerência com a persona, campo_alvo, pós-E10."""
    erros: list[str] = []
    for pid, persona, d in dialogos_com_persona(corpus):
        fases_do_dialogo = {t.fase_esperada for t in d.turnos}
        if not fases_do_dialogo <= set(persona.fases):
            erros.append(f"dialogo_gabarito: {pid}: fases {sorted(fases_do_dialogo - set(persona.fases))} fora de `fases` da persona")
        sem_passar = sorted(set(persona.fases) - fases_do_dialogo - {"E0"})
        if sem_passar:
            erros.append(f"dialogo_gabarito: {pid}: fases da persona que o diálogo não percorre ({sem_passar})")
        objecoes_vistas: list[str] = []
        encerrou = False
        for i, t in enumerate(d.turnos):
            onde = f"dialogo_gabarito: {pid} turno {i}"
            fora = (set(t.acoes_permitidas) | set(t.acoes_proibidas)) - ACOES
            if fora:
                erros.append(f"{onde}: ação fora do vocabulário {sorted(fora)}")
            repetidas = set(t.acoes_permitidas) & set(t.acoes_proibidas)
            if repetidas:
                erros.append(f"{onde}: ação ao mesmo tempo permitida e proibida {sorted(repetidas)}")
            if not t.acoes_permitidas:
                erros.append(f"{onde}: sem ações permitidas")
            if t.quem == "cliente":
                if t.midia is None and t.intencao_esperada is None:
                    erros.append(f"{onde}: turno do cliente sem intenção esperada")
                if t.intencao_esperada and t.intencao_esperada not in persona.comportamento.intencoes:
                    erros.append(f"{onde}: intenção {t.intencao_esperada} que a persona não exibe")
                if t.objecao_esperada:
                    objecoes_vistas.append(t.objecao_esperada)
                if len(t.variacoes) > MAX_VARIACOES or t.texto_cliente in t.variacoes or len(set(t.variacoes)) != len(t.variacoes):
                    erros.append(f"{onde}: variações repetidas, iguais ao texto ou mais de {MAX_VARIACOES}")
            elif not t.invariantes and not t.acoes_proibidas:
                erros.append(f"{onde}: turno da IA sem invariante nem ação proibida")
            if _campo_pedido_sem_alvo(t):
                erros.append(f"{onde}: pedido ou entrega de campo da E5 sem campo_alvo")
            if t.campo_alvo and not ("TX-07" in t.tx_esperado or t.quem == "cliente"):
                erros.append(f"{onde}: campo_alvo fora de TX-07 e de resposta do cliente")
            if encerrou and mensagem_da_ia(t):
                erros.append(f"{onde}: mensagem da IA depois do encerramento (E10)")
            encerrou = encerrou or (t.quem == "ia" and t.fase_esperada == "E10")
        it = iter(persona.comportamento.objecoes)
        if objecoes_vistas and not all(o in it for o in objecoes_vistas):  # subsequência, em ordem
            erros.append(f"dialogo_gabarito: {pid}: objeções {objecoes_vistas} fora da ordem/lista da persona")
    return erros


def gabarito_acoes_por_fase(corpus: Corpus) -> list[str]:
    """Ferramenta só na fase em que H §2.3b a deixa (T6 só na E5, T5 só na E4...)."""
    erros = []
    for pid, d in corpus.dialogos.items():
        for i, t in enumerate(d.turnos):
            fora = sorted((set(t.acoes_permitidas) & FERRAMENTAS) - FERRAMENTAS_POR_FASE[t.fase_esperada])
            if fora:
                erros.append(f"gabarito_acoes_por_fase: {pid} turno {i}: {fora} não cabem na fase {t.fase_esperada}")
    return erros


def gabarito_fase_tx(corpus: Corpus) -> list[str]:
    """Cada TX só sai na fase dele (TX-16 na abertura E1 não)."""
    return [
        f"gabarito_fase_tx: {pid} turno {i}: {tx} não sai na fase {t.fase_esperada}"
        for pid, d in corpus.dialogos.items()
        for i, t in enumerate(d.turnos)
        for tx in t.tx_esperado
        if tx in TX_FASES and t.fase_esperada not in TX_FASES[tx]
    ]


def gabarito_tx_composto(corpus: Corpus) -> list[str]:
    """Um só envio: no máximo os compostos da lista (prefixo + texto da fase), e texto livre do modelo com no máximo 1 TX."""
    erros = []
    for pid, d in corpus.dialogos.items():
        for i, t in enumerate(d.turnos):
            if len(t.tx_esperado) > 1 and tuple(t.tx_esperado) not in COMPOSTOS:
                erros.append(f"gabarito_tx_composto: {pid} turno {i}: composição {list(t.tx_esperado)} fora da lista de compostos")
            if t.texto_livre_ia and len(t.tx_esperado) > 1:
                erros.append(f"gabarito_tx_composto: {pid} turno {i}: texto livre mais de um TX")
    return erros


def gabarito_transicoes(corpus: Corpus) -> list[str]:
    """A fase da IA só anda pelo grafo de H §2.1, e o cliente chega na fase em que a IA parou."""
    erros: list[str] = []
    for pid, d in corpus.dialogos.items():
        estado: str | None = None
        for i, t in enumerate(d.turnos):
            if t.quem == "ia":
                origem = estado or "E0"
                if t.fase_esperada not in TRANSICOES[origem]:
                    erros.append(f"gabarito_transicoes: {pid} turno {i}: pulo de fase {origem} → {t.fase_esperada}")
                estado = t.fase_esperada
            elif estado is not None and t.fase_esperada != estado:
                erros.append(f"gabarito_transicoes: {pid} turno {i}: o cliente chega em {t.fase_esperada} e a IA parou em {estado}")
    return erros


def gabarito_silencio(corpus: Corpus) -> list[str]:
    """Silêncio da IA tem motivo: evento, aborto em E0, depois do E10 ou fora do horário. Mensagem não traz `enviar` proibido."""
    erros: list[str] = []
    for pid, persona, d in dialogos_com_persona(corpus):
        encerrou = False
        for i, (t, quando) in enumerate(zip(d.turnos, instantes(persona.contexto.inicio_utc, d.turnos), strict=True)):
            if t.quem != "ia":
                continue
            onde = f"gabarito_silencio: {pid} turno {i}"
            if mensagem_da_ia(t):
                if "enviar" in t.acoes_proibidas:
                    erros.append(f"{onde}: mensagem com `enviar` proibido")
            else:
                if "enviar" not in t.acoes_proibidas:
                    erros.append(f"{onde}: silêncio sem `enviar` nas ações proibidas")
                fora_do_horario = quando is not None and not dentro_do_horario(quando)
                if not (t.evento or t.fase_esperada == "E0" or encerrou or fora_do_horario):
                    erros.append(f"{onde}: silêncio sem motivo (nem evento, nem E0, nem pós-E10, nem fora do horário)")
            encerrou = encerrou or t.fase_esperada == "E10"
    return erros


def gabarito_seguranca(corpus: Corpus) -> list[str]:
    """I2, I5 e I9 viram ação proibida verificável: toda mensagem da IA proíbe valor fora de placeholder, eco de dado pessoal e promessa."""
    return [
        f"gabarito_seguranca: {pid} turno {i}: mensagem sem {faltam} nas ações proibidas"
        for pid, d in corpus.dialogos.items()
        for i, t in enumerate(d.turnos)
        if mensagem_da_ia(t) and (faltam := [a for a in ACOES_DE_SEGURANCA if a not in t.acoes_proibidas])
    ]


def e5_completa(corpus: Corpus) -> list[str]:
    """H §2.3: a E5 colhe recebimento (PIX OU conta), CEP, número e celular; só então o TX-11 (`faltam=[]`), salvo o que o 360 já tem."""
    erros = []
    for pid, persona, d in dialogos_com_persona(corpus):
        coletados = set(persona.perfil.campos_no_360)
        for i, t in enumerate(d.turnos):
            if t.quem == "cliente" and t.fase_esperada == "E5" and t.intencao_esperada == "fornece_dado" and t.campo_alvo:
                coletados.add("recebimento" if t.campo_alvo in ("pix", "conta") else t.campo_alvo)
            if t.quem == "ia" and "TX-11" in t.tx_esperado:
                faltam = [c for c in CAMPOS_DA_E5 if c not in coletados]
                if faltam:
                    erros.append(f"e5_completa: {pid} turno {i}: TX-11 sem coletar {faltam}")
                break
    return erros


def gabarito_sim_literal(corpus: Corpus) -> list[str]:
    """O SIM vale pelo TEXTO: no E6, `aceita` só com texto (e variações) da lista fechada; texto da lista com outro rótulo reprova."""
    erros = []
    for pid, d in corpus.dialogos.items():
        for i, t in enumerate(d.turnos):
            if t.quem != "cliente" or t.fase_esperada != "E6" or t.texto_cliente is None:
                continue
            if t.intencao_esperada == "aceita" and not e_sim_literal(t):
                erros.append(
                    f"gabarito_sim_literal: {pid} turno {i}: rotulado `aceita` mas o texto não é um SIM da lista fechada ({redacoes(t)})"
                )
            if t.intencao_esperada != "aceita" and e_sim_literal(t):
                erros.append(f"gabarito_sim_literal: {pid} turno {i}: o texto é um SIM da lista fechada e o rótulo é {t.intencao_esperada}")
    return erros


def gabarito_janela24h(corpus: Corpus) -> list[str]:
    """P-R21: mensagem da IA (texto livre ou TX) só até 24 h do último cliente; depois só template aprovado (e só o TX-24 é template)."""
    erros = []
    limite = timedelta(hours=JANELA_WHATSAPP_HORAS)
    for pid, persona, d in dialogos_com_persona(corpus):
        ultimo_cliente = None
        for i, (t, quando) in enumerate(zip(d.turnos, instantes(persona.contexto.inicio_utc, d.turnos), strict=True)):
            if t.quem == "cliente":
                ultimo_cliente = quando
            elif not mensagem_da_ia(t) or ultimo_cliente is None or quando is None or quando - ultimo_cliente <= limite:
                continue
            elif t.texto_livre_ia or not set(t.tx_esperado) <= {"TX-24"}:
                horas = (quando - ultimo_cliente).total_seconds() / 3600
                erros.append(f"gabarito_janela24h: {pid} turno {i}: texto livre {horas:.0f} h depois do cliente")
    return erros


def gabarito_t7_so_com_oferta_facta(corpus: Corpus) -> list[str]:
    """T7 só para CPF com stub na FACTA (persona do dublê ou estado global) e oferta ativa; «sem FACTA» não digita nem chega ao E7/E8."""
    erros = []
    for p in corpus.todas():
        cf = p.cenario_facta
        sem_stub = cf.persona_duble is None and cf.global_duble is None
        digita = any(f in p.fases for f in ("E7", "E8")) or (
            p.id in corpus.dialogos and any({"T7", "T7_mesma_chave"} & set(t.acoes_permitidas) for t in corpus.dialogos[p.id].turnos)
        )
        if digita and (sem_stub or not p.perfil.oferta_facta_ativa):
            erros.append(f"t7_so_com_oferta_facta: {p.id}: chega ao T7/E7-E8 sem persona do dublê e oferta FACTA ativa")
    return erros
