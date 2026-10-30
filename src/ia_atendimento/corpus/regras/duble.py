"""O gabarito é amarrado ao cenário do dublê da persona (R2-4): só os resultados de T7/T8 que o cenário produz, com o TX obrigado."""

from __future__ import annotations

from ia_atendimento.corpus.modelos import Corpus, Persona
from ia_atendimento.corpus.regras._comum import dialogos_com_persona
from ia_atendimento.corpus.vocabulario import (
    EVENTOS_DE_RESULTADO_TX,
    EVENTOS_POR_CENARIO_DO_DUBLE,
    EVENTOS_POR_PERSONA_DO_DUBLE,
)

_SUCESSOS = frozenset(e for e, tx in EVENTOS_DE_RESULTADO_TX.items() if tx == "TX-16")


def eventos_possiveis(p: Persona) -> frozenset[str]:
    """Resultados de T7/T8 que o dublê da persona pode devolver (vazio para «sem FACTA»)."""
    cf = p.cenario_facta
    if cf.persona_duble in EVENTOS_POR_PERSONA_DO_DUBLE:
        return EVENTOS_POR_PERSONA_DO_DUBLE[cf.persona_duble]
    chave = f"global_{cf.global_duble}" if cf.global_duble else cf.cenario
    return EVENTOS_POR_CENARIO_DO_DUBLE.get(chave, frozenset())


def _tx_do_turno_ou_do_proximo(turnos, i: int) -> set[str]:
    """TX do turno; se o turno é silêncio (a ferramenta foi chamada), o da próxima mensagem da IA."""
    if turnos[i].tx_esperado:
        return set(turnos[i].tx_esperado)
    proxima = next((t for t in turnos[i + 1 :] if t.quem == "ia" and t.tx_esperado), None)
    return set(proxima.tx_esperado) if proxima else set()


def gabarito_cenario_duble(corpus: Corpus) -> list[str]:
    """Evento de resultado só se o cenário do dublê o produz; evento ⇒ TX; TX-16 só com sucesso (e só no cenário que o permite);
    TX-16 só depois de um T7 permitido; T7_mesma_chave só depois de um T7."""
    erros: list[str] = []
    for pid, persona, d in dialogos_com_persona(corpus):
        possiveis = eventos_possiveis(persona)
        t7_visto = False
        for i, t in enumerate(d.turnos):
            if t.quem != "ia":
                continue
            onde = f"gabarito_cenario_duble: {pid} turno {i}"
            if t.evento in EVENTOS_DE_RESULTADO_TX:
                if t.evento not in possiveis:
                    erros.append(f"{onde}: o cenário {persona.cenario_facta.cenario} do dublê não produz o resultado {t.evento}")
                obrigado = EVENTOS_DE_RESULTADO_TX[t.evento]
                if obrigado and obrigado not in _tx_do_turno_ou_do_proximo(d.turnos, i):
                    erros.append(f"{onde}: o resultado {t.evento} obriga o {obrigado}")
            if "TX-16" in t.tx_esperado:
                if t.evento not in _SUCESSOS or t.evento not in possiveis:
                    erros.append(f"{onde}: TX-16 (link) só depois de um resultado de sucesso que o cenário do dublê produz")
                if not t7_visto:
                    erros.append(f"{onde}: TX-16 sem nenhum T7 permitido antes")
            if "T7_mesma_chave" in t.acoes_permitidas and not t7_visto:
                erros.append(f"{onde}: T7_mesma_chave sem T7 antes")
            t7_visto = t7_visto or "T7" in t.acoes_permitidas
    return erros
