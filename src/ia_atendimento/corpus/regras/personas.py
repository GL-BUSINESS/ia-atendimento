"""Regras sobre as personas: ids, nomes, CPF, alinhamento com o dublê, conjunto da F3 curta, tempo."""

from __future__ import annotations

import re
from collections import Counter

from ia_atendimento.corpus.calendario import cenarios_do_instante, dentro_do_horario
from ia_atendimento.corpus.modelos import Corpus, Persona
from ia_atendimento.corpus.pii import cpf_sintetico, digitos
from ia_atendimento.corpus.regras._comum import precisa_de_dialogo
from ia_atendimento.corpus.vocabulario import F3_CURTA_IDS, FAIXA_SEM_STUB, N_F3_CURTA, N_PERSONAS_H, N_PERSONAS_M, SOBRENOMES_FICTICIOS


def ids_unicos(corpus: Corpus) -> list[str]:
    erros: list[str] = []
    for rotulo, valores in (("id", [p.id for p in corpus.todas()]), ("nome", [p.nome for p in corpus.todas()])):
        erros += [f"ids_unicos: {rotulo} repetido: {v}" for v, n in Counter(valores).items() if n > 1]
    return erros


def nome_ficticio(corpus: Corpus) -> list[str]:
    erros = []
    for p in corpus.todas():
        partes = p.nome.split()
        if len(partes) < 2 or not all(x.isalpha() and x[0].isupper() for x in partes) or partes[-1] not in SOBRENOMES_FICTICIOS:
            erros.append(f"nome_ficticio: {p.id}: sobrenome fora da lista de inventados ({p.nome!r})")
    return erros


def cpf_sintetico_regra(corpus: Corpus) -> list[str]:
    erros = []
    for p in corpus.todas():
        if not re.fullmatch(r"000\.000\.0[0-9]{2}-[0-9]{2}", p.cpf):
            erros.append(f"cpf_sintetico: {p.id}: CPF fora do formato 000.000.0nn-dd")
        elif not cpf_sintetico(digitos(p.cpf)):
            erros.append(f"cpf_sintetico: {p.id}: dígito verificador errado")
    return erros


def _persona_do_duble(p: Persona, por_id: dict, quem_aponta: dict) -> list[str]:
    cf, erros = p.cenario_facta, []
    d = por_id.get(cf.persona_duble)
    if d is None:
        return [f"cpf_alinhado_duble: {p.id}: persona do dublê inexistente ({cf.persona_duble})"]
    if p.cpf != d.cpf:
        erros.append(f"cpf_alinhado_duble: {p.id}: CPF diferente do da persona {d.id} do dublê")
    if cf.cenario != d.cenario:
        erros.append(f"cpf_alinhado_duble: {p.id}: cenário {cf.cenario!r} difere do do dublê ({d.cenario!r})")
    if cf.sem_chamada_facta or cf.global_duble:
        erros.append(f"cpf_alinhado_duble: {p.id}: persona do dublê não pode ser «sem FACTA» nem global")
    if p.familia == "H" and p.id in quem_aponta and quem_aponta[p.id] != d.id:
        erros.append(f"cpf_alinhado_duble: {p.id}: o dublê lista {p.id} em `f3` de {quem_aponta[p.id]} e não de {d.id}")
    elif p.familia == "H" and p.id not in quem_aponta and d.cenario != "aprovado":
        erros.append(
            f"cpf_alinhado_duble: {p.id}: o dublê não lista {p.id} e {d.id} não é o caminho feliz (aprovado) que serve a qualquer persona"
        )
    return erros


def _persona_sem_stub(p: Persona, duble, quem_aponta: dict) -> list[str]:
    cf, erros = p.cenario_facta, []
    if p.cpf in {d.cpf for d in duble.personas}:
        erros.append(f"cpf_alinhado_duble: {p.id}: sem persona no dublê mas usa CPF de uma delas")
    n = int(digitos(p.cpf)[7:9])
    if not FAIXA_SEM_STUB[0] <= n <= FAIXA_SEM_STUB[1]:
        faixa = f"{FAIXA_SEM_STUB[0]:03d}-{FAIXA_SEM_STUB[1]:03d}"
        erros.append(f"cpf_alinhado_duble: {p.id}: sem stub no dublê o CPF fica na faixa reservada {faixa} (n={n})")
    if p.familia == "M":
        if not cf.sem_chamada_facta:
            erros.append(f"cpf_alinhado_duble: {p.id}: P-M sem persona do dublê tem de declarar sem_chamada_facta")
        return erros
    if p.id in quem_aponta:
        erros.append(f"cpf_alinhado_duble: {p.id}: o dublê tem persona para ela ({quem_aponta[p.id]})")
    global_esperado = duble.f3_globais.get(p.id)
    if global_esperado != cf.global_duble:
        erros.append(f"cpf_alinhado_duble: {p.id}: global_duble deveria ser {global_esperado!r}")
    elif global_esperado is None and (p.id in duble.f3_sem_facta) != cf.sem_chamada_facta:
        erros.append(f"cpf_alinhado_duble: {p.id}: sem_chamada_facta não bate com `f3_sem_facta` do dublê")
    return erros


def cpf_alinhado_duble(corpus: Corpus) -> list[str]:
    """O CPF e o vínculo com o dublê batem com o instantâneo de `bancos-duble/personas/personas.yaml` (ids e CPFs alinhados)."""
    duble = corpus.duble
    por_id = {d.id: d for d in duble.personas}
    quem_aponta = {pid: d.id for d in duble.personas for pid in d.f3}
    erros: list[str] = []
    livres: list[Persona] = []
    for p in corpus.todas():
        if p.cenario_facta.persona_duble is not None:
            erros += _persona_do_duble(p, por_id, quem_aponta)
        else:
            livres.append(p)
            erros += _persona_sem_stub(p, duble, quem_aponta)
    erros += [
        f"cpf_alinhado_duble: CPF {c} repetido entre personas sem stub na FACTA" for c, n in Counter(p.cpf for p in livres).items() if n > 1
    ]
    return erros


def conjunto_f3_curta(corpus: Corpus) -> list[str]:
    erros = []
    if len(corpus.personas) != N_PERSONAS_H or [p.id for p in corpus.personas] != [f"P{n:02d}" for n in range(1, N_PERSONAS_H + 1)]:
        erros.append(f"conjunto_f3_curta: esperadas as {N_PERSONAS_H} personas P01..P60, em ordem")
    if [p.id for p in corpus.personas_m] != [f"P-M{n:02d}" for n in range(1, N_PERSONAS_M + 1)]:
        erros.append(f"conjunto_f3_curta: esperadas as {N_PERSONAS_M} personas P-M01..P-M24, em ordem")
    marcadas = frozenset(p.id for p in corpus.personas if p.f3_curta)
    if marcadas != F3_CURTA_IDS:
        faltam, sobram = sorted(F3_CURTA_IDS - marcadas), sorted(marcadas - F3_CURTA_IDS)
        erros.append(f"conjunto_f3_curta: as {N_F3_CURTA} da F3 curta divergem do roteiro (faltam {faltam}, sobram {sobram})")
    return erros


def f3_com_dialogo(corpus: Corpus) -> list[str]:
    """Diálogo para toda persona que o harness roda (F3 curta, P-M críticas) e só para elas; abre com a IA (caso (b) de M: com o Post)."""
    erros = []
    exigidos = {p.id for p in corpus.todas() if precisa_de_dialogo(p)}
    erros += [f"f3_com_dialogo: {pid} é da F3 curta ou P-M crítica e não tem diálogo" for pid in sorted(exigidos - set(corpus.dialogos))]
    erros += [f"f3_com_dialogo: {pid} tem diálogo mas não é da F3 curta nem P-M crítica" for pid in sorted(set(corpus.dialogos) - exigidos)]
    por_id = {p.id: p for p in corpus.todas()}
    for pid, d in corpus.dialogos.items():
        caso_b = pid in por_id and por_id[pid].classe.startswith(("caso_b", "post_"))
        if not d.turnos or (d.turnos[0].quem != "ia" and not caso_b):
            erros.append(
                f"f3_com_dialogo: {pid}: o diálogo começa com a IA (abertura TX-01 ou aborto em E0); só o caso (b) de M começa pelo Post"
            )
    return erros


def cenario_tempo_coerente(corpus: Corpus) -> list[str]:
    erros = []
    for p in corpus.todas():
        ctx = p.contexto
        if ctx.instante_chave_utc < ctx.inicio_utc:
            erros.append(f"cenario_tempo_coerente: {p.id}: o instante-chave é anterior ao início")
        if ctx.cenario_tempo not in cenarios_do_instante(ctx.instante_chave_utc):
            erros.append(
                f"cenario_tempo_coerente: {p.id}: cenario_tempo={ctx.cenario_tempo} não descreve {ctx.instante_chave_utc:%Y-%m-%dT%H:%MZ}"
            )
        if ctx.cenario_tempo == "horario_normal" and not dentro_do_horario(ctx.inicio_utc):
            erros.append(f"cenario_tempo_coerente: {p.id}: horario_normal mas o início está fora do horário")
    return erros
