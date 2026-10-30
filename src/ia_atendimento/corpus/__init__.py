"""Corpus da F3 (roteiro B8.1a): carregador tipado e validador de `tests/corpus/`.

O corpus é INVENTADO: nenhuma conversa real do ChatGuru (proibido até o parecer jurídico J5), CPF só `000.000.0nn`, nomes fictícios,
valores redondos. Ele guarda o que a avaliação (B8.1b/B8.2) precisa e NADA do texto da IA: o gabarito de cada turno da IA fixa só a
fase, as ações permitidas/proibidas e os TX que ela pode emitir; o texto do cliente é fixo (com até 2 variações escolhidas pela semente).

Pacote (dependência só desce): `vocabulario` e `calendario` → `modelos` → `carga`, `semente`, `pii` → `regras/*` → este `__init__`.
Uso: `carregar()` devolve o `Corpus` tipado; `validar(carregar_bruto())` devolve as violações `codigo: mensagem` (vazia = corpus bom);
`uv run python -m ia_atendimento.corpus [--semente]` valida o corpus do disco ou imprime a semente derivada.
"""

from __future__ import annotations

from ia_atendimento.corpus.calendario import cenarios_do_instante, dentro_da_agenda, dentro_do_horario
from ia_atendimento.corpus.carga import carregar, carregar_bruto, montar
from ia_atendimento.corpus.modelos import Corpus, Dialogo, Persona, Turno
from ia_atendimento.corpus.pii import achados_pii, cpf_sintetico
from ia_atendimento.corpus.regras import REGRAS, validar
from ia_atendimento.corpus.semente import derivar_semente, escolher_variacao, texto_do_turno
from ia_atendimento.corpus.vocabulario import *  # noqa: F403 - API pública: vocabulário e limites

__all__ = [
    "REGRAS",
    "Corpus",
    "Dialogo",
    "Persona",
    "Turno",
    "achados_pii",
    "carregar",
    "carregar_bruto",
    "cenarios_do_instante",
    "cpf_sintetico",
    "dentro_da_agenda",
    "dentro_do_horario",
    "derivar_semente",
    "escolher_variacao",
    "montar",
    "texto_do_turno",
    "validar",
]
