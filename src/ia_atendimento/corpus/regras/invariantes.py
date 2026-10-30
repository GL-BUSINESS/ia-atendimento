"""Invariantes I1-I9 no gabarito: o que o gabarito nunca pode permitir, e o desfecho que o fim do diálogo dá."""

from __future__ import annotations

from ia_atendimento.corpus.calendario import dentro_do_horario
from ia_atendimento.corpus.modelos import Corpus, Dialogo
from ia_atendimento.corpus.regras._comum import dialogos_com_persona, instantes, mensagem_da_ia
from ia_atendimento.corpus.regras.gabarito import PEDIDO_DE_CONFIRMACAO, e_sim_literal
from ia_atendimento.corpus.vocabulario import INTENCOES_QUE_INVALIDAM_O_PEDIDO, MAX_TURNOS_DO_MODELO

_MOTIVOS_SEM_NOTA = frozenset({"opt_out", "identidade", "humano_assumiu"})


def gabarito_i1(corpus: Corpus) -> list[str]:
    """I1: nunca T4/T7 sem TX de confirmação (11/12/13) seguido de SIM do cliente na E6 (pelo TEXTO), e só no turno E7."""
    erros: list[str] = []
    for pid, d in corpus.dialogos.items():
        pedido, confirmado = False, False
        for i, t in enumerate(d.turnos):
            onde = f"gabarito_i1: {pid} turno {i}"
            if "T4" in t.acoes_permitidas:
                erros.append(f"{onde}: T4 (consulta paga) está fora do MVP e não pode constar como permitida")
            if t.quem == "ia":
                if PEDIDO_DE_CONFIRMACAO & set(t.tx_esperado):
                    pedido, confirmado = True, False  # nova confirmação invalida a anterior
                if "T7" in t.acoes_permitidas:
                    if not confirmado:
                        erros.append(f"{onde}: T7 permitido sem pedido de confirmação + SIM (do texto) antes")
                    if t.fase_esperada != "E7":
                        erros.append(f"{onde}: T7 só no turno E7")
                    pedido, confirmado = False, False  # a confirmação foi consumida
            elif t.fase_esperada == "E6":
                if t.intencao_esperada == "aceita" and e_sim_literal(t):
                    if not pedido:
                        erros.append(f"{onde}: SIM na E6 sem o pedido de confirmação (TX-11/12/13) antes")
                    confirmado = pedido
                else:
                    confirmado = False
                    if t.intencao_esperada in INTENCOES_QUE_INVALIDAM_O_PEDIDO:
                        pedido = False
    return erros


def gabarito_i4(corpus: Corpus) -> list[str]:
    """I4: T7 ≤ 1 por confirmação; retry só com a MESMA chave (T7_mesma_chave, depois de TX-19); indeterminado (TX-15) nunca reenvia."""
    erros: list[str] = []
    for pid, d in corpus.dialogos.items():
        t7_desde_a_confirmacao, indeterminado, transitorio = 0, False, False
        for i, t in enumerate(d.turnos):
            if t.quem != "ia":
                continue
            onde = f"gabarito_i4: {pid} turno {i}"
            if PEDIDO_DE_CONFIRMACAO & set(t.tx_esperado):
                t7_desde_a_confirmacao, indeterminado, transitorio = 0, False, False
            indeterminado = indeterminado or "TX-15" in t.tx_esperado
            transitorio = transitorio or "TX-19" in t.tx_esperado
            if "T7" in t.acoes_permitidas:
                t7_desde_a_confirmacao += 1
                if t7_desde_a_confirmacao > 1:
                    erros.append(f"{onde}: segundo T7 sem nova confirmação")
                if indeterminado:
                    erros.append(f"{onde}: T7 depois de indeterminado (TX-15): nunca reenvia")
            if "T7_mesma_chave" in t.acoes_permitidas and (indeterminado or not transitorio):
                erros.append(f"{onde}: T7_mesma_chave só depois de erro transitório (TX-19) e nunca depois de indeterminado")
    return erros


def gabarito_i3(corpus: Corpus) -> list[str]:
    """I3: toda mensagem da IA no gabarito cai em horário (seg–sáb, 08–20, fora de feriado/DATAPREV); o relógio não anda para trás."""
    erros: list[str] = []
    for pid, persona, d in dialogos_com_persona(corpus):
        anterior = persona.contexto.inicio_utc
        for i, (t, quando) in enumerate(zip(d.turnos, instantes(persona.contexto.inicio_utc, d.turnos), strict=True)):
            if t.em_utc is not None:
                if t.em_utc < anterior:
                    erros.append(f"gabarito_i3: {pid} turno {i}: o relógio anda para trás")
                anterior = t.em_utc
            if mensagem_da_ia(t) and quando is not None and not dentro_do_horario(quando):
                erros.append(f"gabarito_i3: {pid} turno {i}: mensagem da IA fora do horário ({quando:%Y-%m-%dT%H:%MZ})")
    return erros


def gabarito_i6(corpus: Corpus) -> list[str]:
    """I6: no máximo uma mensagem da IA por turno: duas seguidas só se a segunda nasce de evento (resultado de T7/T8, lembrete, volta)."""
    return [
        f"gabarito_i6: {pid} turno {i}: duas mensagens da IA seguidas sem evento que justifique a segunda"
        for pid, d in corpus.dialogos.items()
        for i, (a, b) in enumerate(zip(d.turnos, d.turnos[1:], strict=False), start=1)
        if mensagem_da_ia(a) and mensagem_da_ia(b) and not b.evento
    ]


def gabarito_i7(corpus: Corpus) -> list[str]:
    return [
        f"gabarito_i7: {pid}: {n} turnos do modelo (teto {MAX_TURNOS_DO_MODELO})"
        for pid, d in corpus.dialogos.items()
        if (n := sum(t.quem == "ia" and not t.evento for t in d.turnos)) > MAX_TURNOS_DO_MODELO
    ]


def gabarito_i8(corpus: Corpus) -> list[str]:
    """I8: o E10 declara nota e motivo; nota «nenhuma» após opt-out, identidade contestada, humano assumiu ou cliente que nunca falou;
    TX-35 (obrigatória) depois de indeterminado; NT-07 só quando o cliente já concluiu."""
    erros: list[str] = []
    for pid, d in corpus.dialogos.items():
        cliente_falou = any(t.quem == "cliente" for t in d.turnos)
        indeterminado, encerrou = False, False
        for i, t in enumerate(d.turnos):
            onde = f"gabarito_i8: {pid} turno {i}"
            indeterminado = indeterminado or "TX-15" in t.tx_esperado
            if t.quem != "ia":
                continue
            if t.fase_esperada != "E10" or encerrou:
                if t.nota_esperada or t.motivo_e10:
                    erros.append(f"{onde}: nota/motivo só no primeiro turno E10")
                continue
            encerrou = True
            if t.nota_esperada is None or t.motivo_e10 is None:
                erros.append(f"{onde}: o turno E10 declara nota_esperada e motivo_e10")
                continue
            if t.motivo_e10 in _MOTIVOS_SEM_NOTA and t.nota_esperada != "nenhuma":
                erros.append(f"{onde}: motivo {t.motivo_e10} não gera nota ao consultor")
            if not cliente_falou and t.nota_esperada != "nenhuma":
                erros.append(f"{onde}: cliente nunca respondeu: sem nota")
            if indeterminado and t.motivo_e10 not in _MOTIVOS_SEM_NOTA and t.nota_esperada != "TX-35":
                erros.append(f"{onde}: depois de indeterminado a nota é a TX-35 (obrigatória)")
            if t.nota_esperada == "TX-35" and not indeterminado:
                erros.append(f"{onde}: TX-35 sem indeterminado antes")
            if (t.nota_esperada == "NT-07") != (t.motivo_e10 == "ja_concluiu"):
                erros.append(f"{onde}: a nota NT-07 é a do motivo ja_concluiu (e só dele)")
    return erros


def desfecho_do_dialogo(d: Dialogo) -> set[str]:
    """Desfechos compatíveis com o fim do diálogo (o primeiro turno E10 diz o motivo; sem E10, vale o último turno da IA)."""
    ias = [t for t in d.turnos if t.quem == "ia"]
    if not ias:
        return set()
    tx = {x for t in ias for x in t.tx_esperado}
    primeiro_e10 = next((t for t in ias if t.fase_esperada == "E10"), None)
    if primeiro_e10 is not None:
        if primeiro_e10.motivo_e10 == "recusa_politica" and "TX-18" in tx:
            return {"recusado_facta"}
        if primeiro_e10.motivo_e10 in ("opt_out", "identidade"):
            return {"encerrado_sem_interesse"}
        if primeiro_e10.motivo_e10 == "ja_concluiu":
            return {"vendeu"}
        return {"repassado"}
    if ias[-1].fase_esperada == "E0":
        return {"repassado"}  # E0 aborta antes de qualquer mensagem: o lead segue com o consultor

    def ultimo(alvo: str) -> int:
        return max((i for i, t in enumerate(ias) if alvo in t.tx_esperado), default=-1)

    if ultimo("TX-M08") > ultimo("TX-16"):
        return {"agendado"}  # a última coisa combinada foi uma volta (mesmo depois de o link ter sido enviado)
    if ultimo("TX-16") >= 0 and ias[-1].fase_esperada == "E8":
        return {"vendeu"}
    return set()


def desfecho_coerente(corpus: Corpus) -> list[str]:
    erros = []
    for pid, persona, d in dialogos_com_persona(corpus):
        derivados = desfecho_do_dialogo(d)
        if persona.desfecho_esperado not in derivados:
            erros.append(
                f"desfecho_coerente: {pid}: persona diz {persona.desfecho_esperado} e o fim do diálogo dá {sorted(derivados) or 'nada'}"
            )
    return erros
