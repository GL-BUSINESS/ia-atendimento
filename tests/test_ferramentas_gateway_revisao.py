"""Achados da revisão independente da B5.1 (`docs/REVISAO-B5.1-0411.md`): cada teste reprova no código de `493c068` e passa com a correção.

A-1 parada dura durante a fila e durante a leitura do CPF; M-1 síncronas em paralelo; M-2 a fila dentro do prazo; M-3 `CORRIGIVEL` tipado e
a consulta paga contada na tentativa; M-4 erro tipado sem a causa; M-6 PII nos dados do lado do código; M-7 leitura da FACTA com posse
real sob parada dura; B-1 a B-4 as lacunas de teste e o registro da recusa na entrada. M-5 (histórico do catálogo) está em
`test_ferramentas_registro.py`.

Dados sintéticos: CPF da faixa `000.000.0nn`, hosts `.test`.
"""

from __future__ import annotations

import asyncio
import dataclasses
import traceback
from typing import Any

import pytest

from ia_atendimento.ferramentas.catalogo import CATALOGO_MVP, Catalogo
from ia_atendimento.ferramentas.erros import ErroDeFerramenta
from ia_atendimento.ferramentas.especificacao import EsquemaInvalido
from ia_atendimento.ferramentas.esquemas import Fechado, SaidaT1, SaidaT3
from ia_atendimento.ferramentas.gateway import Referencia, RegistroDaChamada
from ia_atendimento.ferramentas.orcamento import ContadorDoAtendimento, OrcamentoDoTurno
from ia_atendimento.ferramentas.saida import para_projetar, reconstruir
from ia_atendimento.ferramentas.segredo import CpfEmMemoria
from ia_atendimento.relogio import RelogioFalso
from tests.apoio_gateway import (
    ATENDIMENTO,
    CONFIRMACAO,
    CPF,
    CPF_DIGITOS,
    INICIO,
    OFERTA_REAL,
    PRODUCAO,
    RETORNO_T3_CRU,
    Espiao,
    contexto,
    gateway,
)

T7_OK = {"classe": "criada", "ref_externa": "AF-0001"}
GUARDA_S = 2.0  # teto de cada espera do teste: no código antigo a chamada pendura na fila e o teste FALHA em vez de travar


def _tudo_facta(atendimento_id, campo, real):
    return Referencia(real, banco="FACTA")


async def _chamar(gw, nome: str, args: dict[str, Any] | None = None, ctx=None, **opcoes):
    orcamento = opcoes.pop("orcamento", None) or OrcamentoDoTurno()
    return await gw.chamar(nome, args or {}, ctx or contexto(), orcamento=orcamento, **opcoes)


class _Fila:
    """Duas T8 que seguram as duas vagas da FACTA até `soltar()`."""

    def __init__(self) -> None:
        self.liberar = asyncio.Event()
        self.em_voo = 0

    async def segura(self, chamada) -> dict[str, str]:
        self.em_voo += 1
        await self.liberar.wait()
        return {"estado": "aguardando"}

    async def ocupar(self, gw) -> list[asyncio.Task]:
        tarefas = [asyncio.create_task(_chamar(gw, "T8", {"tentativa_ref": f"t7-{n}"})) for n in range(2)]
        for _ in range(100):
            if self.em_voo == 2:
                break
            await asyncio.sleep(0.005)
        assert self.em_voo == 2
        return tarefas


# --- A-1: a parada dura alcança o efeito que espera a vaga e o que lê o CPF -------------------------------------------------------------


async def test_parada_dura_durante_a_espera_do_limitador_intercepta_a_t7():
    """A T7 entra na fila da FACTA atrás de duas T8; enquanto espera, o operador liga a parada dura e o cache do modo vence. Quando a
    vaga sai, a T7 vai ao simulador: o destino é o da hora do efeito, não o de quando ela entrou na fila."""
    relogio, config, fila = RelogioFalso(INICIO), ["real"], _Fila()
    t7, simulador = Espiao(T7_OK), Espiao(T7_OK)
    gw = gateway(
        executores={"T8": Espiao(comportamento=fila.segura), "T7": t7},
        simuladores={"T7": simulador},
        config_modo=lambda: config[0],
        relogio=relogio,
        referencias=_tudo_facta,
    )
    ocupadas = await fila.ocupar(gw)
    t7_tarefa = asyncio.create_task(_chamar(gw, "T7", {"confirmacao_id": CONFIRMACAO}))
    await asyncio.sleep(0.02)
    assert not t7.chamadas and not simulador.chamadas  # está na fila
    config[0] = "sombra"
    relogio.avancar(seconds=6)
    fila.liberar.set()
    r = await asyncio.wait_for(t7_tarefa, GUARDA_S)
    await asyncio.gather(*ocupadas)
    assert t7.chamadas == [] and len(simulador.chamadas) == 1
    assert (r.destino.tipo, r.destino.modo_efetivo) == ("interceptado", "sombra")
    assert simulador.chamadas[0].cpf is None  # interceptado não lê CPF


async def test_parada_dura_durante_a_leitura_do_cpf_intercepta_a_t7():
    relogio, config = RelogioFalso(INICIO), ["real"]

    async def ler_cpf_e_parar(pessoa_id):
        config[0] = "sombra"
        relogio.avancar(seconds=6)
        await asyncio.sleep(0)
        return CpfEmMemoria(CPF)

    t7, simulador = Espiao(T7_OK), Espiao(T7_OK)
    gw = gateway(
        executores={"T7": t7}, simuladores={"T7": simulador}, config_modo=lambda: config[0], relogio=relogio, leitor_de_cpf=ler_cpf_e_parar
    )
    r = await _chamar(gw, "T7", {"confirmacao_id": CONFIRMACAO})
    assert t7.chamadas == [] and len(simulador.chamadas) == 1
    assert r.destino.tipo == "interceptado" and simulador.chamadas[0].cpf is None


# --- M-1: síncronas em paralelo não furam o teto do turno ----------------------------------------------------------------------------------


async def test_sincronas_concorrentes_respeitam_o_teto_do_turno():
    """O Pydantic AI roda as function tools em paralelo: cinco T3 ao mesmo tempo no mesmo orçamento ⇒ quatro rodam, a quinta é
    `ORCAMENTO_ESGOTADO`."""
    liberar = asyncio.Event()

    async def segura(chamada):
        await liberar.wait()
        return RETORNO_T3_CRU

    t3, orcamento = Espiao(comportamento=segura), OrcamentoDoTurno()
    gw = gateway(executores={"T3": t3})
    tarefas = [asyncio.create_task(_chamar(gw, "T3", {}, orcamento=orcamento)) for _ in range(5)]
    await asyncio.sleep(0.02)
    liberar.set()
    resultados = await asyncio.wait_for(asyncio.gather(*tarefas), GUARDA_S)
    assert sorted(r.ok for r in resultados) == [False, True, True, True, True]
    assert [r.erro.codigo for r in resultados if not r.ok] == ["ORCAMENTO_ESGOTADO"]
    assert len(t3.chamadas) == 4 and orcamento.sincronas == 4


# --- M-2: a espera na fila conta no prazo ---------------------------------------------------------------------------------------------------


async def test_sincrona_que_espera_a_vaga_estoura_no_prazo_sem_rodar():
    """T5 (FACTA) com prazo de 0,05 s atrás de duas T8 longas: estoura na fila como `BANCO_INDISPONIVEL`, o executor não roda e a espera
    conta no turno."""
    catalogo = Catalogo([dataclasses.replace(s, timeout_s=0.05) if s.nome == "T5" else s for s in CATALOGO_MVP])
    fila, t5, orcamento = _Fila(), Espiao({"sem_opcao": True}), OrcamentoDoTurno()
    gw = gateway(executores={"T8": Espiao(comportamento=fila.segura), "T5": t5}, catalogo=catalogo, referencias=_tudo_facta)
    ocupadas = await fila.ocupar(gw)
    try:
        r = await asyncio.wait_for(
            _chamar(gw, "T5", {"oferta_ref": "oferta-1", "alvo": "prazo"}, orcamento=orcamento, pelo_modelo=True), GUARDA_S
        )
    finally:
        fila.liberar.set()
        await asyncio.gather(*ocupadas)
    assert r.erro.codigo == "BANCO_INDISPONIVEL" and t5.chamadas == []
    assert orcamento.segundos > 0


async def test_assincrona_que_estoura_na_fila_nao_e_indeterminada():
    """Timeout da T7 ainda na fila: nada saiu, então não é `INDETERMINADO` (que levaria ao T8 de uma digitação que não existe)."""
    catalogo = Catalogo([dataclasses.replace(s, timeout_s=0.05) if s.nome == "T7" else s for s in CATALOGO_MVP])
    fila, t7 = _Fila(), Espiao(T7_OK)
    gw = gateway(executores={"T8": Espiao(comportamento=fila.segura), "T7": t7}, catalogo=catalogo, referencias=_tudo_facta)
    ocupadas = await fila.ocupar(gw)
    try:
        r = await asyncio.wait_for(_chamar(gw, "T7", {"confirmacao_id": CONFIRMACAO}), GUARDA_S)
    finally:
        fila.liberar.set()
        await asyncio.gather(*ocupadas)
    assert r.erro.codigo == "BANCO_INDISPONIVEL" and t7.chamadas == []


async def test_assincrona_tem_o_prazo_do_efeito_inteiro_depois_da_fila():
    """A fila da assíncrona não come o prazo do efeito: 0,4 s na fila + 0,2 s de efeito num prazo de 0,5 s passa."""
    catalogo = Catalogo([dataclasses.replace(s, timeout_s=0.5) if s.nome == "T7" else s for s in CATALOGO_MVP])
    fila = _Fila()

    async def digita(chamada):
        await asyncio.sleep(0.2)
        return T7_OK

    gw = gateway(executores={"T8": Espiao(comportamento=fila.segura), "T7": Espiao(comportamento=digita)}, catalogo=catalogo,
                 referencias=_tudo_facta)  # fmt: skip
    ocupadas = await fila.ocupar(gw)
    tarefa = asyncio.create_task(_chamar(gw, "T7", {"confirmacao_id": CONFIRMACAO}))
    await asyncio.sleep(0.4)
    fila.liberar.set()
    r = await asyncio.wait_for(tarefa, GUARDA_S)
    await asyncio.gather(*ocupadas)
    assert r.ok, r.erro


# --- M-3: corrigível tipado e consulta paga pela tentativa ---------------------------------------------------------------------------------


async def test_corrigivel_tipado_do_executor_conta_no_teto():
    async def corrigivel(chamada):
        raise ErroDeFerramenta("CORRIGIVEL")

    contador, t7 = ContadorDoAtendimento(), Espiao(comportamento=corrigivel)
    gw = gateway(executores={"T7": t7}, contador=contador)
    resultados = [await _chamar(gw, "T7", {"confirmacao_id": CONFIRMACAO}) for _ in range(5)]
    assert [r.erro.codigo for r in resultados] == ["CORRIGIVEL"] * 3 + ["ORCAMENTO_ESGOTADO"] * 2
    assert len(t7.chamadas) == 3 and contador.corrigiveis(ATENDIMENTO) == 3
    assert resultados[0].retorno_ao_modelo() == {"erro": "CORRIGIVEL"}


def _catalogo_com_paga() -> Catalogo:
    """O MVP não tem T4 (P-R23): uma leitura paga de teste com a forma da T10."""
    paga = dataclasses.replace(CATALOGO_MVP["T10"], nome="T4", funcao="consultar_margem", classe="leitura_paga", do_modelo=False)
    return Catalogo([*CATALOGO_MVP, paga])


async def test_consulta_paga_conta_a_tentativa_que_falha():
    async def banco_cobra_e_falha(chamada):
        raise RuntimeError("resposta inválida")

    contador, t4 = ContadorDoAtendimento(), Espiao(comportamento=banco_cobra_e_falha)
    gw = gateway(executores={"T4": t4}, contador=contador, catalogo=_catalogo_com_paga())
    resultados = [await _chamar(gw, "T4", {}) for _ in range(3)]
    assert [r.erro.codigo for r in resultados] == ["DESCONHECIDO", "DESCONHECIDO", "ORCAMENTO_ESGOTADO"]
    assert len(t4.chamadas) == 2 and contador.pagas(ATENDIMENTO) == 2


async def test_consultas_pagas_concorrentes_respeitam_o_teto():
    liberar = asyncio.Event()

    async def segura(chamada):
        await liberar.wait()
        return {"macro": "em_analise"}

    t4 = Espiao(comportamento=segura)
    gw = gateway(executores={"T4": t4}, catalogo=_catalogo_com_paga())
    tarefas = [asyncio.create_task(_chamar(gw, "T4", {})) for _ in range(3)]
    await asyncio.sleep(0.02)
    liberar.set()
    resultados = await asyncio.wait_for(asyncio.gather(*tarefas), GUARDA_S)
    assert len(t4.chamadas) == 2 and [r.erro.codigo for r in resultados if r.erro] == ["ORCAMENTO_ESGOTADO"]


# --- M-4: o erro tipado do executor não guarda a causa -------------------------------------------------------------------------------------


@pytest.mark.parametrize("encadeado", [False, True])
async def test_erro_tipado_do_executor_chega_sem_causa_nem_frames(encadeado):
    """`except HTTPError: raise ErroDeFerramenta("RECUSA")` deixa no original a exceção do banco (CPF na mensagem) e os frames do
    executor com o CPF revelado. O `Resultado` guarda uma cópia nova."""

    async def recusa(chamada):
        revelado = chamada.cpf.revelar()
        try:
            raise RuntimeError(f"recusado para {revelado}")
        except RuntimeError as original:
            if encadeado:
                raise ErroDeFerramenta("RECUSA") from original
            raise ErroDeFerramenta("RECUSA")  # noqa: B904 - é o caso que a revisão provou (contexto implícito)

    r = await _chamar(gateway(executores={"T7": Espiao(comportamento=recusa)}), "T7", {"confirmacao_id": CONFIRMACAO})
    assert r.erro.codigo == "RECUSA"
    assert r.erro.__context__ is None and r.erro.__cause__ is None and r.erro.__traceback__ is None
    impresso = "".join(traceback.format_exception(r.erro))
    assert CPF_DIGITOS not in impresso and CPF not in impresso


def test_copia_limpa_preserva_o_vocabulario():
    erro = ErroDeFerramenta("BANCO_INDISPONIVEL", retry_apos_s=30)
    copia = erro.copia_limpa()
    assert (copia.codigo, copia.precondicao, copia.retry_apos_s) == ("BANCO_INDISPONIVEL", None, 30) and copia is not erro
    pre = ErroDeFerramenta("PRECONDICAO_FALHOU", precondicao="lease_ativo").copia_limpa()
    assert pre.para_o_modelo() == {"erro": "PRECONDICAO_FALHOU", "precondicao": "lease_ativo"}


# --- M-6: PII nos dados do lado do código ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nome", "bruto"),
    [
        ("T1", {"encontrado": True, "primeiro_nome": CPF}),
        ("T1", {"encontrado": True, "primeiro_nome": "fulano@exemplo.test"}),
        ("T3", {**RETORNO_T3_CRU, "oferta_ref": CPF_DIGITOS}),  # cabe no `IdOpaco`: 11 dígitos com forma de CPF
        ("T7", {"classe": "criada", "ref_externa": "11912345678"}),  # telefone
    ],
)
async def test_saida_com_pii_em_campo_permitido_e_desconhecido(nome, bruto):
    async def devolve(chamada):
        return bruto

    ctx = contexto(apelidos={})
    args = {"confirmacao_id": CONFIRMACAO} if nome == "T7" else {}
    r = await _chamar(gateway(executores={nome: Espiao(comportamento=devolve)}), nome, args, ctx)
    assert r.erro.codigo == "DESCONHECIDO" and r.dados is None
    assert CPF_DIGITOS not in repr(r) and CPF_DIGITOS not in repr(ctx.apelidos.mapa)


def test_saida_sem_pii_passa_na_chegada():
    """Uuid, chave do ledger, proposta numérica longa sem forma de documento e data ISO não são PII."""
    t3 = reconstruir(CATALOGO_MVP["T3"], {**RETORNO_T3_CRU, "valid_until": "2026-11-10T12:00:00Z"})
    assert isinstance(t3, SaidaT3) and t3.oferta_ref == OFERTA_REAL
    for ref in ("AF-0001", "12345678", f"t7:{OFERTA_REAL}:FACTA:2"):
        assert reconstruir(CATALOGO_MVP["T7"], {"classe": "criada", "ref_externa": ref}).ref_externa == ref
    assert reconstruir(CATALOGO_MVP["T1"], {"encontrado": True, "primeiro_nome": "Fulano"}).primeiro_nome == "Fulano"


# --- M-7: leitura da FACTA com posse real sob parada dura ----------------------------------------------------------------------------------


async def test_t8_de_tentativa_real_sob_parada_dura_nao_sai_do_simulador():
    t8, simulador = Espiao({"estado": "criada"}), Espiao({"estado": "nao_criada"})
    gw = gateway(executores={"T8": t8}, simuladores={"T8": simulador}, config_modo=lambda: "sombra", referencias=_tudo_facta)
    r = await _chamar(gw, "T8", {"tentativa_ref": "t7-1"}, contexto("real", posse_real=True))
    assert r.erro.codigo == "MODO_SOMENTE_LEITURA" and t8.chamadas == [] and simulador.chamadas == []
    sem_posse = await _chamar(gw, "T8", {"tentativa_ref": "t7-1"}, contexto("real"))
    assert sem_posse.ok and len(simulador.chamadas) == 1


# --- baixos ------------------------------------------------------------------------------------------------------------------------------


class _EntradaComCpf(Fechado):
    cpf: str


@pytest.mark.parametrize("nome", ["T7", "T8", "T13"])
def test_campo_proibido_e_recusado_tambem_em_ferramenta_so_do_codigo(nome):
    """B-1: a regra «campo proibido em QUALQUER ferramenta» (só a T6 recebe valor do cliente), sem a regra do modelo por cima."""
    spec = CATALOGO_MVP[nome]
    assert not spec.do_modelo
    with pytest.raises(EsquemaInvalido, match="cpf"):
        dataclasses.replace(spec, entrada=_EntradaComCpf)


def test_texto_com_pii_em_campo_permitido_nao_vai_a_projecao():
    """B-2: a segunda cerca (`para_projetar`) apaga o texto que a máscara troca, mesmo num campo que a allowlist deixaria passar."""
    corpo = para_projetar(SaidaT1(encontrado=True, primeiro_nome=CPF))
    assert corpo == {"encontrado": True}


async def test_precondicao_assincrona_verdadeira_deixa_a_t7_rodar():
    """B-3: o verificador assíncrono que devolve `True` é aguardado (sem o `await`, a corrotina não é `True` e a T7 nunca roda)."""

    async def vale(pedido) -> bool:
        await asyncio.sleep(0)
        return True

    t7 = Espiao(T7_OK)
    gw = gateway(executores={"T7": t7}, precondicoes=dict.fromkeys(CATALOGO_MVP["T7"].precondicoes, vale))
    r = await _chamar(gw, "T7", {"confirmacao_id": CONFIRMACAO})
    assert r.ok and len(t7.chamadas) == 1


async def test_modelo_pedindo_ferramenta_que_nao_e_dele_vai_ao_registro():
    """B-4: o modelo tentando o que não pode é sinal para o ledger e o alerta: `RegistroDaChamada` com `parametro_invalido`."""
    registros: list[RegistroDaChamada] = []
    t7 = Espiao(T7_OK)
    r = await _chamar(gateway(executores={"T7": t7}, registrar=registros.append), "T7", {"confirmacao_id": CONFIRMACAO}, pelo_modelo=True)
    assert r.erro.codigo == "PARAMETRO_INVALIDO" and t7.chamadas == []
    (linha,) = registros
    assert (linha.ferramenta, linha.resultado, linha.destino, linha.args_hash) == ("t7", "parametro_invalido", None, None)
    assert all(url not in repr(linha) for url in PRODUCAO)
