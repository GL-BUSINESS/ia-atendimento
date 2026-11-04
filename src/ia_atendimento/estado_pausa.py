"""Pausa combinada e agendamento (B5.7b, estudo M): `pausar`/`sair_da_pausa` (caso a) e `abrir_agendado`/`iniciar_agendado` (caso b).

Moram fora de `estado.py` para o ciclo de vida ficar abaixo de 800 linhas. Tudo passa por `estado.aplicar` (CAS por `versao`, um só UPDATE).

- **Caso (a):** o cliente combinou a volta; a IA segue dona do chat e dorme em `pausado` até `retoma_em`. Só de E2–E6 e E8, nunca de E7.
- **Caso (b):** `reservado` de vida longa (`gatilho='agendamento'`) que NÃO toca o chat; na hora, `iniciar_agendado` assume o canal.
- A chave `pausa` do `estado_conversa` existe se e só se o estado é `pausado`: entra em `pausar` e sai em `sair_da_pausa`
  (e em `repassar`/`encerrar`, que estão em `estado.py`).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Final, Literal
from uuid import UUID

import psycopg

from ia_atendimento.estado import (
    LEASE_AGUARDANDO_S,
    LEASE_TURNO_S,
    EntradaInvalida,
    EstadoErro,
    Relogio,
    Resultado,
    Versoes,
    _lease,
    _mudancas,
    agora_de,
    aplicar,
    executar_traduzindo,
    fingerprint_de_identidade,
    idempotency_key,
    validar_corpo,
)
from ia_atendimento.modelos_conversa import Pausa

FASES_PAUSAVEIS: Final = ("E2", "E3", "E4", "E5", "E6", "E8")  # nunca E7 (T7/T8 em voo), nem E0/E1/E9/E10
# padrões das chaves `agenda_*` (um teste confere com o registro): quem chama passa o valor VIGENTE da config
AGENDA_FOLGA_MIN: Final = 30  # `agenda_folga_min`: o lease de quem dorme vai até `retoma_em` + 30 min (a vigia só devolve depois)
AGENDA_MAX_PAUSADOS: Final = 10  # `agenda_max_pausados`: pausados ao mesmo tempo, fora de `max_abertos`
AGENDA_TETO_HORAS: Final = 23  # `agenda_teto_horas`: a volta cabe na janela de 24 h do WhatsApp, contada da última mensagem do cliente
TRAVA_PAUSAR: Final = "ia_atendimento.pausar"
FAIXA_AGENDAMENTO: Final = "media"  # faixa do atendimento nascido de um agendamento (sem comissão calculável)


class LimiteDePausados(EstadoErro):
    """Já há `agenda_max_pausados` atendimentos `pausado`: este não pausa (o cliente segue com a IA ou vai ao humano, decisão da B5.7c)."""


def pausar(
    conn: psycopg.Connection,
    atendimento_id: UUID | str,
    versao: int,
    *,
    retoma_em: datetime,
    retoma_fase: str,
    agendamento_ref: str | None = None,
    folga_min: int = AGENDA_FOLGA_MIN,
    max_pausados: int = AGENDA_MAX_PAUSADOS,
    teto_horas: int = AGENDA_TETO_HORAS,
    relogio: Relogio,
) -> int:
    """Caso (a): `aberto|aguardando_cliente → pausado`. O cliente combinou a volta; a IA segue dona do chat e dorme até `retoma_em`.

    **Só de E2–E6 e E8, nunca de E7** (T7/T8 em voo): `retoma_fase` é a fase em que a conversa está e para a qual volta; o UPDATE só casa se
    a fase ATUAL é ela (`onde_igual`), e a `pausa{agendamento_ref, retoma_fase}` entra no `estado_conversa` no mesmo UPDATE.
    `lease_ate = retoma_em + folga_min` (o CHECK exige `lease_ate >= retoma_em`): é o que faz o `reaper_lease` pular quem dorme, pois só o
    vê depois da folga, como `retomada_perdida`. Nada aqui encerra ou repassa o `pausado`: `bloqueio_entrada` e o timer das 20:15 o poupam.

    **Quem cria `pausado` impõe os tetos (R1-05):** `retoma_em` no máximo `teto_horas` (23) depois da última mensagem do cliente
    (`EntradaInvalida`; sem `ultimo_cliente_em`, depois de agora), e no máximo `max_pausados` (10) pausados ao mesmo tempo
    (`LimiteDePausados`), contados sob uma trava consultiva da transação (duas pausas concorrentes não passam juntas do teto)."""
    agora = agora_de(relogio)
    if retoma_fase not in FASES_PAUSAVEIS:
        raise EntradaInvalida("retoma_fase fora de E2–E6/E8 (pausa nunca em E7)")
    if folga_min < 0:
        raise EntradaInvalida("folga_min negativa")
    if retoma_em <= agora:
        raise EntradaInvalida("retoma_em no passado")
    pausa = validar_corpo(Pausa, {"agendamento_ref": agendamento_ref, "retoma_fase": retoma_fase})
    m = _mudancas(estado="pausado", retoma_em=retoma_em, lease_ate=retoma_em + timedelta(minutes=folga_min))
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (TRAVA_PAUSAR,))
        _conferir_tetos(conn, atendimento_id, agora, retoma_em, max_pausados, teto_horas)
        return aplicar(
            conn, atendimento_id, versao, m, agora=agora, de={"aberto", "aguardando_cliente"}, pausa=pausa, onde_igual={"fase": retoma_fase}
        )


def _conferir_tetos(
    conn: psycopg.Connection, atendimento_id: UUID | str, agora: datetime, retoma_em: datetime, max_pausados: int, teto_horas: int
) -> None:
    linha = conn.execute(
        "SELECT ultimo_cliente_em, (SELECT count(*) FROM ia.atendimento WHERE estado = 'pausado')"
        " FROM ia.atendimento WHERE atendimento_id = %s",
        (atendimento_id,),
    ).fetchone()
    if linha is None:
        return  # o `aplicar` diz «não existe» com o erro certo
    ultimo, pausados = linha
    if retoma_em > (ultimo or agora) + timedelta(hours=teto_horas):
        raise EntradaInvalida("retoma_em além do teto (agenda_teto_horas depois da última mensagem do cliente)")
    if pausados >= max_pausados:
        raise LimiteDePausados(f"já há {pausados} atendimento(s) pausado(s) (agenda_max_pausados = {max_pausados})")


def sair_da_pausa(
    conn: psycopg.Connection,
    atendimento_id: UUID | str,
    versao: int,
    *,
    relogio: Relogio,
    para: Literal["aberto", "aguardando_cliente"] = "aberto",
    lease_ate: datetime | None = None,
) -> int:
    """`pausado → aberto` (padrão: a volta é um turno, lease +5 min; falhou, o reaper devolve) ou `→ aguardando_cliente` (lease de espera).

    Remove a `pausa` do `estado_conversa` e zera `retoma_em` no mesmo UPDATE; a fase fica a de antes (a de volta, `pausa.retoma_fase`)."""
    agora = agora_de(relogio)
    if lease_ate is not None and (para != "aguardando_cliente" or lease_ate <= agora):
        raise EntradaInvalida("lease_ate só vale para aguardando_cliente e no futuro")
    lease = lease_ate or _lease(agora, LEASE_AGUARDANDO_S if para == "aguardando_cliente" else LEASE_TURNO_S)
    m = _mudancas(estado=para, retoma_em=None, lease_ate=lease)
    return aplicar(conn, atendimento_id, versao, m, agora=agora, de={"pausado"}, pausa="remover")


_INSERIR_AGENDADO: Final = """
INSERT INTO ia.atendimento (origem, chave_logica, idempotency_key, entrada_fingerprint, gatilho, disparado_por, faixa_esforco, pessoa_id,
  chat_id, phone_id, clt_job_id, roteiro_versao, regras_versao, catalogo_versao, motor_versao, modo, ultimo_cliente_em, retoma_em,
  lease_ate, iniciado_em, atualizado_em)
VALUES (%(origem)s, %(chave_logica)s, %(idem)s, %(fp)s, 'agendamento', %(disparado_por)s, %(faixa)s, %(pessoa_id)s, %(chat_id)s,
  %(phone_id)s, %(clt_job_id)s, %(roteiro)s, %(regras)s, %(catalogo)s, %(motor)s, %(modo)s, %(ultimo_cliente_em)s, %(retoma_em)s,
  %(lease_ate)s, %(agora)s, %(agora)s)
RETURNING atendimento_id, estado, versao, modo
"""


def abrir_agendado(
    conn: psycopg.Connection,
    *,
    origem: str,
    chave_logica: str,
    disparado_por: str,
    pessoa_id: UUID,
    chat_id: str,
    phone_id: str,
    clt_job_id: UUID,
    versoes: Versoes,
    modo: str,
    retoma_em: datetime,
    ultimo_cliente_em: datetime,
    agora: datetime,
    folga_min: int = AGENDA_FOLGA_MIN,
    faixa_esforco: str = FAIXA_AGENDAMENTO,
) -> Resultado:
    """Caso (b): `reservado` de vida longa (`gatilho='agendamento'`, fase E0) que NÃO toca o chat até `retoma_em`, quando o
    `iniciar_agendado` assume o canal. `lease_ate = retoma_em + folga_min` (CHECK). O índice por chat já o conta como não encerrado.

    A idempotência é de quem chama (`ia.agendamento.idem_key` e a trava da API): aqui a mesma chave duas vezes é `DadoRecusado` e outro
    atendimento no chat é `ChatOcupado`. A linha do `agendamento` e o job `retomar` entram na MESMA transação do chamador."""
    if agora.tzinfo is None:
        raise ValueError("`agora` exige datetime com fuso")
    if folga_min < 0 or retoma_em <= agora:
        raise EntradaInvalida("retoma_em precisa estar no futuro e a folga não pode ser negativa")
    identidade = {
        "chat_id": chat_id, "chave_logica": chave_logica, "clt_job_id": str(clt_job_id), "gatilho": "agendamento",
        "pessoa_id": str(pessoa_id), "phone_id": phone_id,
    }  # fmt: skip
    params = {
        "origem": origem, "chave_logica": chave_logica, "idem": idempotency_key(chave_logica), "fp": fingerprint_de_identidade(identidade),
        "disparado_por": disparado_por, "faixa": faixa_esforco, "pessoa_id": pessoa_id, "chat_id": chat_id, "phone_id": phone_id,
        "clt_job_id": clt_job_id, "roteiro": versoes.roteiro, "regras": versoes.regras, "catalogo": versoes.catalogo,
        "motor": versoes.motor, "modo": modo, "ultimo_cliente_em": ultimo_cliente_em, "retoma_em": retoma_em,
        "lease_ate": retoma_em + timedelta(minutes=folga_min), "agora": agora,
    }  # fmt: skip
    nova = executar_traduzindo(conn, _INSERIR_AGENDADO, params)
    return Resultado(nova[0], nova[1], nova[2], nova[3], repetido=False)


def iniciar_agendado(
    conn: psycopg.Connection,
    atendimento_id: UUID | str,
    versao: int,
    *,
    retoma_fase: str,
    chatbot_antes: str | None,
    chatbot_estado: str,
    responsavel_antes: str | None = None,
    relogio: Relogio,
) -> int:
    """Caso (b) na hora combinada: `reservado(gatilho=agendamento) → aberto` já em `retoma_fase` (E8 enquanto `agenda_b_digita=false`),
    não em E1: o cliente já passou da abertura. Como `iniciar` (assumir canal, lease +5 min), e zera `retoma_em`."""
    agora = agora_de(relogio)
    if retoma_fase not in FASES_PAUSAVEIS:
        raise EntradaInvalida("retoma_fase fora de E2–E6/E8")
    if chatbot_estado != "intocado" and chatbot_antes is None:
        raise EntradaInvalida("chatbot mexido sem o estado anterior")
    campos: dict[str, Any] = {
        "estado": "aberto", "assumido_em": agora, "lease_ate": _lease(agora), "retoma_em": None,
        "chatbot_antes": chatbot_antes, "chatbot_estado": chatbot_estado,
    }  # fmt: skip
    if responsavel_antes is not None:
        campos["responsavel_antes"] = responsavel_antes
    return aplicar(
        conn,
        atendimento_id,
        versao,
        _mudancas(**campos),
        agora=agora,
        de={"reservado"},
        fase=retoma_fase,
        onde_igual={"gatilho": "agendamento"},
    )
