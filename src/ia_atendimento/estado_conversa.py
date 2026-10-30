"""Estado da conversa (B1.1): a máquina E0–E10 e o que o turno seguinte precisa lembrar, em JSON ≤ 2 KB dentro de `ia.atendimento`.

- **Só códigos, referências e contadores.** Nenhum campo guarda texto livre, valor monetário, CPF, nome ou telefone: nomes de campo
  (`renda`, `conta`), códigos de intenção/objeção e ids de oferta. Campo desconhecido é recusado (`extra='forbid'`) e o erro não ecoa o
  valor (`hide_input_in_errors=True`; `estado_conversa_de_json` devolve só nome de campo e regra).
- **Fonte única:** o que já é coluna de `ia.atendimento` (`sem_avanco`, `turnos`, `lembretes_enviados`...) NÃO mora no JSON.
- **Gravar é uma transição** (`versao + 1`, CAS): o processador do turno grava o estado junto com o resto. O lease não é tocado aqui
  (num `pausado` ele tem de ficar >= `retoma_em`); quem renova é a transição do turno. A `fase` gerada acompanha o JSON, e o CHECK
  cruzado fase×estado do banco (`atendimento_conversa_check` e `atendimento_fase_estado_check`, 0003) barra combinação impossível
  (`TransicaoInvalida`): E0 só no reservado, E10 só no repassando, `pausa` só no pausado.
- **`ultimo_cliente_em`** (0003) é coluna à parte, com GRANT próprio: o evento da mensagem a escreve sem disputar o CAS de `versao`.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

import psycopg

from ia_atendimento.estado import (
    ESTADOS_NAO_TERMINAIS,
    TOLERANCIA_RELOGIO,
    AtendimentoInexistente,
    EntradaInvalida,
    Mudancas,
    Relogio,
    agora_de,
    aplicar,
    validar_corpo,
)
from ia_atendimento.modelos_conversa import (  # noqa: F401  (reexportados: é daqui que o resto do código importa)
    Confirmacao,
    Contadores,
    EstadoConversa,
    OfertaCorrente,
    Pausa,
    TentativaT7,
)

JANELA_SERVICO: Final = timedelta(hours=24)  # janela de serviço do WhatsApp: texto livre só dentro dela


def estado_conversa_de_json(corpo: object) -> EstadoConversa:
    """Valida o JSON; recusa campo desconhecido e documento acima de 2 KB com `EntradaInvalida` (só nomes, nunca valores)."""
    return validar_corpo(EstadoConversa, corpo)


def ler_estado_conversa(conn: psycopg.Connection, atendimento_id: UUID | str) -> EstadoConversa:
    linha = conn.execute("SELECT estado_conversa FROM ia.atendimento WHERE atendimento_id = %s", (atendimento_id,)).fetchone()
    if linha is None:
        raise AtendimentoInexistente("atendimento não existe")
    return estado_conversa_de_json(linha[0])


def gravar_estado_conversa(
    conn: psycopg.Connection, atendimento_id: UUID | str, versao: int, estado: EstadoConversa, *, relogio: Relogio
) -> int:
    """Grava o estado como transição com CAS (`versao + 1`); atendimento encerrado não muda. Devolve a nova `versao`."""
    agora = agora_de(relogio)
    mudancas = Mudancas(estado_conversa=estado.para_json())
    return aplicar(conn, atendimento_id, versao, mudancas, agora=agora, de=ESTADOS_NAO_TERMINAIS)


def registrar_mensagem_do_cliente(conn: psycopg.Connection, atendimento_id: UUID | str, quando: datetime, *, relogio: Relogio) -> datetime:
    """`ultimo_cliente_em = greatest(atual, quando)`: só avança (mensagem fora de ordem não recua a janela de 24 h) e NÃO toca `versao`.

    UPDATE próprio, de uma coluna com GRANT próprio (0003): não disputa o CAS com o processador do turno. Como o valor só avança, um
    futuro gravado nunca mais se corrige: `quando` mais de 5 min à frente do relógio é recusado (`EntradaInvalida`, é um `ValueError`).
    """
    if quando.tzinfo is None:
        raise ValueError("ultimo_cliente_em exige datetime com fuso")
    if quando > agora_de(relogio) + TOLERANCIA_RELOGIO:
        raise EntradaInvalida("ultimo_cliente_em no futuro (mais de 5 min à frente do relógio)")
    linha = conn.execute(
        "UPDATE ia.atendimento SET ultimo_cliente_em = greatest(coalesce(ultimo_cliente_em, '-infinity'::timestamptz), %s) "
        "WHERE atendimento_id = %s RETURNING ultimo_cliente_em",
        (quando, atendimento_id),
    ).fetchone()
    if linha is None:
        raise AtendimentoInexistente("atendimento não existe")
    return linha[0]


def janela_24h_aberta(ultimo_cliente_em: datetime | None, agora: datetime) -> bool:
    """Texto livre só com `agora − ultimo_cliente_em < 24 h`. Desconhecido (None) ou mais de 5 min no futuro = fechada (só template)."""
    if ultimo_cliente_em is None or ultimo_cliente_em > agora + TOLERANCIA_RELOGIO:
        return False
    return agora - ultimo_cliente_em < JANELA_SERVICO
