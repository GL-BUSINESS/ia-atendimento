"""Ledger `ia.ferramenta_chamada` e `executar_efeito` (B1.6a; contrato 08 §6; receita D14b da r2 da B5.7b).

O que se prova, contra o Postgres 18 descartável e com `chamar` espião (nada sai para fora):
- a linha `reservada` e o `enviada` estão COMMITADOS antes da chamada; a mesma chave nunca executa duas vezes;
- timeout, exceção e `CancelledError` no meio do envio de efeito irreversível ⇒ `indeterminado`, e `indeterminado` nunca reenvia;
- `transitorio` e `reservada` (a chamada nunca começou) podem ser reexecutados com a MESMA chave; `enviada` órfã ⇒ `indeterminado` só para irreversível real (G-0131);
- cerca de `versao`: a reserva e o CAS do atendimento na mesma transação; a execução superada (rodada velha) não envia;
- `modo_efetivo` = o mais restritivo entre `atendimento.modo` e `config.modo`, relido a cada efeito (cache ≤ 5 s), gravado no ledger;
- posse real (assumir `ok` em `real|teste`) e a devolução real sob parada dura; T7 sem confirmação aceita ⇒ `ConfirmacaoAusente` antes do banco.
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import timedelta

import pytest

from ia_atendimento import ledger
from ia_atendimento.chave import LeitorConfig, registrar_config
from ia_atendimento.estado_erros import ConflitoVersao, TransicaoInvalida
from ia_atendimento.ledger import (
    Cerca,
    ChaveDivergente,
    ConfirmacaoAusente,
    Desfecho,
    EfeitoOcupado,
    Pedido,
    chave_t11,
    executar_efeito,
    modo_efetivo,
    posse_real,
)
from tests import fixtures_fila as ff
from tests.fixtures_fila import inserir_atendimento

conn_app, conn_super, relogio = ff.conn_app, ff.conn_super, ff.relogio

pytestmark = pytest.mark.banco


class Espia:
    """`chamar` falso: registra o destino e devolve o desfecho pedido (ou faz o que `acao` mandar)."""

    def __init__(self, desfecho: Desfecho | None = None, acao=None) -> None:
        self.destinos: list[str] = []
        self._desfecho = desfecho or Desfecho("ok", http_bucket="2xx", ref_externa="msg-1")
        self._acao = acao

    async def __call__(self, destino: str) -> Desfecho:
        self.destinos.append(destino)
        if self._acao is not None:
            return await self._acao(destino)
        return self._desfecho


def _config(conn, relogio, nome, valor):
    registrar_config(conn, nome, valor, "teste", relogio=relogio, motivo="preparo do teste")


def _versao(conn, atd) -> int:
    return conn.execute("SELECT versao FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()[0]


def _linha(conn, chave: str):
    return conn.execute(
        "SELECT estado, modo, simulado, enviada_em IS NOT NULL, concluida_em IS NOT NULL FROM ia.ferramenta_chamada WHERE chave_logica = %s",
        (chave,),
    ).fetchone()


HASH_TEXTO = "a" * 64


def _t11(atd, rodada: int = 1, seq: int = 1, args_hash: str = HASH_TEXTO) -> Pedido:
    return Pedido(
        ferramenta="t11",
        ferramenta_versao="1.0.0",
        classe_efeito="efeito_irreversivel",
        chave_logica=chave_t11(atd, rodada, seq),
        args_hash=args_hash,
    )


async def _executar(conn, relogio, atd, pedido, chamar, **opcoes):
    leitor = opcoes.pop("leitor", None) or LeitorConfig(relogio, ttl_s=0)
    return await executar_efeito(conn, atd, pedido, chamar=chamar, leitor=leitor, relogio=relogio, **opcoes)


@pytest.fixture
def real(conn_app, conn_super, relogio):
    """Atendimento `aberto` em `real` com `config.modo = real`."""
    _config(conn_app, relogio, "modo", "real")
    return inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())


# --- modo_efetivo ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("do_atendimento", "global_", "esperado"),
    [
        ("real", "real", "real"),
        ("real", "duble", "duble"),
        ("real", "sombra", "sombra"),
        ("teste", "real", "teste"),
        ("teste", "duble", "duble"),
        ("teste", "sombra", "sombra"),
        ("duble", "real", "duble"),
        ("duble", "sombra", "sombra"),
        ("sombra", "real", "sombra"),
    ],
)
def test_modo_efetivo_e_o_mais_restritivo(do_atendimento, global_, esperado):
    assert modo_efetivo(do_atendimento, global_) == esperado


def test_modo_desconhecido_levanta():
    with pytest.raises(ValueError):
        modo_efetivo("real", "teste_global")


# --- reserva, idempotência, estados ----------------------------------------------------------------------------------------------------


async def test_ledger_grava_reservada_antes_de_chamar(conn_app, conn_super, relogio, real):
    pedido = _t11(real)
    vistas: list[tuple] = []

    async def olhar(_destino: str) -> Desfecho:
        vistas.append(_linha(conn_super, pedido.chave_logica))  # outra conexão: só vê o que já foi commitado
        return Desfecho("ok", http_bucket="2xx")

    resultado = await _executar(conn_app, relogio, real, pedido, Espia(acao=olhar))
    assert vistas == [("enviada", "real", False, True, False)], "a chamada só começa com a reserva e o `enviada` commitados"
    assert resultado.estado == "ok" and resultado.executou and not resultado.repetido
    assert _linha(conn_super, pedido.chave_logica) == ("ok", "real", False, True, True)


async def test_mesma_chave_nao_executa_duas_vezes(conn_app, relogio, real):
    espia = Espia()
    primeiro = await _executar(conn_app, relogio, real, _t11(real), espia, cerca=Cerca(_versao(conn_app, real)))
    segundo = await _executar(conn_app, relogio, real, _t11(real), espia, cerca=Cerca(_versao(conn_app, real)))
    assert espia.destinos == ["real"]
    assert (segundo.estado, segundo.executou, segundo.repetido, segundo.chamada_id) == ("ok", False, True, primeiro.chamada_id)
    assert segundo.versao is None, "repetição não move a cerca (a transação da reserva foi desfeita)"


async def test_timeout_vira_indeterminado_e_nunca_reenvia(conn_app, conn_super, relogio, real):
    async def lento(_destino: str) -> Desfecho:
        await asyncio.sleep(5)
        return Desfecho("ok")

    espia = Espia(acao=lento)
    r = await _executar(conn_app, relogio, real, _t11(real), espia, timeout_s=0.05)
    assert r.estado == "indeterminado" and r.http_bucket == "timeout"
    de_novo = await _executar(conn_app, relogio, real, _t11(real), Espia())
    assert (de_novo.estado, de_novo.executou) == ("indeterminado", False), "indeterminado NUNCA reenvia"
    assert _linha(conn_super, chave_t11(real, 1, 1))[0] == "indeterminado"


async def test_excecao_no_envio_irreversivel_e_indeterminado(conn_app, relogio, real):
    async def explode(_destino: str) -> Desfecho:
        raise RuntimeError("conexão caiu no meio")

    r = await _executar(conn_app, relogio, real, _t11(real), Espia(acao=explode))
    assert r.estado == "indeterminado" and r.http_bucket == "rede"


async def test_acao_interna_que_falha_e_transitorio_e_reexecuta_com_a_mesma_chave(conn_app, conn_super, relogio, real):
    pedido = Pedido(ferramenta="t12", ferramenta_versao="1.0.0", classe_efeito="acao_interna", chave_logica=f"t12:{real}")

    async def explode(_destino: str) -> Desfecho:
        raise TimeoutError("n8n fora")

    primeiro = await _executar(conn_app, relogio, real, pedido, Espia(acao=explode))
    assert primeiro.estado == "transitorio"
    espia = Espia()
    segundo = await _executar(conn_app, relogio, real, pedido, espia)
    assert espia.destinos == ["real"] and (segundo.estado, segundo.chamada_id, segundo.executou) == ("ok", primeiro.chamada_id, True)
    assert conn_super.execute("SELECT count(*) FROM ia.ferramenta_chamada WHERE atendimento_id = %s", (real,)).fetchone()[0] == 1


async def test_cancelled_no_meio_do_envio_deixa_indeterminado_e_nao_reenvia(conn_app, conn_super, relogio, real):
    comecou = asyncio.Event()

    async def trava(_destino: str) -> Desfecho:
        comecou.set()
        await asyncio.sleep(5)
        return Desfecho("ok")

    tarefa = asyncio.create_task(_executar(conn_app, relogio, real, _t11(real), Espia(acao=trava)))
    await asyncio.wait_for(comecou.wait(), 5)
    tarefa.cancel()
    with pytest.raises(asyncio.CancelledError):
        await tarefa
    assert _linha(conn_super, chave_t11(real, 1, 1))[0] == "indeterminado"
    espia = Espia()
    de_novo = await _executar(conn_app, relogio, real, _t11(real), espia)
    assert espia.destinos == [] and de_novo.estado == "indeterminado"


def _inserir_linha(conn, atd, chave: str, estado: str, enviada_em=None, *, classe="efeito_irreversivel", modo="real") -> None:
    pessoa = conn.execute("SELECT pessoa_id FROM ia.atendimento WHERE atendimento_id = %s", (atd,)).fetchone()[0]
    ferramenta = chave.split(":", 1)[0]
    args_hash = HASH_TEXTO if classe == "efeito_irreversivel" else None
    conn.execute(
        "INSERT INTO ia.ferramenta_chamada (atendimento_id, pessoa_id, ferramenta, ferramenta_versao, classe_efeito, chave_logica, idem_key,"
        " estado, modo, enviada_em, args_hash) VALUES (%s, %s, %s, '1.0.0', %s, %s, %s, %s, %s, %s, %s)",
        (atd, pessoa, ferramenta, classe, chave, hashlib.sha256(chave.encode()).hexdigest(), estado, modo, enviada_em, args_hash),
    )


async def test_enviada_achada_no_retry_vira_indeterminado_sem_chamar(conn_app, conn_super, relogio, real):
    """A execução anterior morreu depois do `enviada` (a mensagem pode ter saído): o retry não reenvia."""
    _inserir_linha(conn_super, real, chave_t11(real, 1, 1), "enviada", enviada_em=relogio.agora() - timedelta(minutes=10))
    espia = Espia()
    r = await _executar(conn_app, relogio, real, _t11(real), espia)
    assert espia.destinos == [] and (r.estado, r.executou, r.repetido) == ("indeterminado", False, True)


async def test_enviada_recente_esta_em_andamento_e_nao_muda(conn_app, conn_super, relogio, real):
    """Outra execução pode estar no meio da chamada (ela fecha dentro do timeout): não reenvia nem rouba o resultado dela."""
    _inserir_linha(conn_super, real, chave_t11(real, 1, 1), "enviada", enviada_em=relogio.agora() - timedelta(seconds=1))
    espia = Espia()
    r = await _executar(conn_app, relogio, real, _t11(real), espia)
    assert espia.destinos == [] and (r.estado, r.executou, r.repetido) == ("enviada", False, True)
    assert _linha(conn_super, chave_t11(real, 1, 1))[0] == "enviada"


@pytest.mark.parametrize("ferramenta", ["t12", "assumir"])
async def test_orfa_de_acao_interna_volta_a_transitorio_e_executa_uma_vez(conn_app, conn_super, relogio, real, ferramenta):
    """G-0131: o worker morreu esperando o `ia-repasse` (ou o `assumir`). A linha `enviada` de 10 min atrás não vira `indeterminado`
    terminal (o repasse nunca mais se repetiria e o chat ficaria no Amado): volta a `transitorio` e o retry chama UMA vez."""
    chave = f"{ferramenta}:{real}"
    _inserir_linha(conn_super, real, chave, "enviada", relogio.agora() - timedelta(minutes=10), classe="acao_interna")
    espia = Espia()
    pedido = Pedido(ferramenta=ferramenta, ferramenta_versao="1.0.0", classe_efeito="acao_interna", chave_logica=chave)
    r = await _executar(conn_app, relogio, real, pedido, espia)
    assert espia.destinos == ["real"] and (r.estado, r.executou, r.repetido) == ("ok", True, True)
    de_novo = await _executar(conn_app, relogio, real, pedido, espia)
    assert espia.destinos == ["real"] and de_novo.estado == "ok"


async def test_orfa_simulada_de_irreversivel_volta_a_transitorio(conn_app, conn_super, relogio):
    """Simulado nada saiu: a órfã de um T11 em `sombra` repete (simulada), não vira `indeterminado`."""
    atd = inserir_atendimento(conn_super, estado="aberto", modo="sombra", iniciado_em=relogio.agora())
    _inserir_linha(conn_super, atd, chave_t11(atd, 1, 1), "enviada", relogio.agora() - timedelta(minutes=10), modo="sombra")
    espia = Espia()
    r = await _executar(conn_app, relogio, atd, _t11(atd), espia)
    assert espia.destinos == [] and (r.estado, r.modo) == ("ok", "sombra")


async def test_transitorio_de_irreversivel_sem_prova_vira_indeterminado(conn_app, conn_super, relogio, real):
    """G-0087 (ledger): o destino devolveu `transitorio` depois do disparo sem provar que nada saiu: nunca se repete."""
    espia = Espia(Desfecho("transitorio", http_bucket="5xx"))
    r = await _executar(conn_app, relogio, real, _t11(real), espia)
    assert r.estado == "indeterminado"
    de_novo = await _executar(conn_app, relogio, real, _t11(real), espia)
    assert espia.destinos == ["real"] and de_novo.estado == "indeterminado"


async def test_transitorio_de_irreversivel_com_prova_repete(conn_app, conn_super, relogio, real):
    espia = Espia(Desfecho("transitorio", http_bucket="5xx", nada_saiu=True))
    r = await _executar(conn_app, relogio, real, _t11(real), espia)
    assert r.estado == "transitorio"
    await _executar(conn_app, relogio, real, _t11(real), espia)
    assert espia.destinos == ["real", "real"]


def test_irreversivel_sem_args_hash_e_recusado():
    """G-0454: sem o hash do conteúdo, outra mensagem na mesma (rodada, seq) seria engolida como repetição."""
    with pytest.raises(ValueError, match="args_hash"):
        _t11(uuid.uuid4(), args_hash=None)


async def test_t11_mesma_chave_outro_texto_e_chave_divergente(conn_app, conn_super, relogio, real):
    espia = Espia()
    await _executar(conn_app, relogio, real, _t11(real), espia)
    with pytest.raises(ChaveDivergente):
        await _executar(conn_app, relogio, real, _t11(real, args_hash="b" * 64), espia)
    assert espia.destinos == ["real"]


async def test_reservada_achada_no_retry_e_reivindicada_e_executa_uma_vez(conn_app, conn_super, relogio, real):
    """A execução anterior morreu entre a reserva e o `enviada`: a chamada nunca começou (o CAS `reservada → enviada` vem antes dela)."""
    _inserir_linha(conn_super, real, chave_t11(real, 1, 1), "reservada")
    espia = Espia()
    r = await _executar(conn_app, relogio, real, _t11(real), espia)
    assert espia.destinos == ["real"] and (r.estado, r.executou, r.repetido) == ("ok", True, True)


async def test_duas_execucoes_concorrentes_da_mesma_chave_chamam_uma_vez(banco, relogio, real, conn_app):
    async def devagar(_destino: str) -> Desfecho:
        await asyncio.sleep(0.2)
        return Desfecho("ok")

    espia = Espia(acao=devagar)
    with ff.abrir(banco) as outra:
        resultados = await asyncio.gather(
            _executar(conn_app, relogio, real, _t11(real), espia), _executar(outra, relogio, real, _t11(real), espia)
        )
    assert len(espia.destinos) == 1
    assert sorted(r.executou for r in resultados) == [False, True]


async def test_exige_conexao_autocommit_fora_de_transacao(conn_app, relogio, real):
    with conn_app.transaction(), pytest.raises(RuntimeError, match="autocommit"):
        await _executar(conn_app, relogio, real, _t11(real), Espia())


# --- cerca de versao ------------------------------------------------------------------------------------------------------------------


async def test_execucao_superada_nao_envia_e_o_canal_e_chamado_uma_vez(conn_app, conn_super, relogio, real):
    """D14b (i): o turno da rodada 1 parou depois do modelo com a versão v; o da rodada 2 (substituto) leu a mesma v e enviou. A rodada 1
    acorda: chave diferente (o ledger sozinho não a barraria), mas a cerca de `versao` sim."""
    espia = Espia()
    v = _versao(conn_app, real)
    substituto = await _executar(conn_app, relogio, real, _t11(real, rodada=2), espia, cerca=Cerca(v))
    assert substituto.versao == v + 1
    with pytest.raises(ConflitoVersao):
        await _executar(conn_app, relogio, real, _t11(real, rodada=1), espia, cerca=Cerca(v))
    assert espia.destinos == ["real"]
    assert _linha(conn_super, chave_t11(real, 1, 1)) is None, "o perdedor da cerca não reserva nada"


async def test_cerca_recusa_atendimento_fora_dos_estados(conn_app, conn_super, relogio):
    _config(conn_app, relogio, "modo", "real")
    atd = inserir_atendimento(conn_super, estado="repassando", modo="real", iniciado_em=relogio.agora())
    espia = Espia()
    with pytest.raises(TransicaoInvalida):
        await _executar(conn_app, relogio, atd, _t11(atd), espia, cerca=Cerca(_versao(conn_app, atd)))
    assert espia.destinos == []


# --- modos ----------------------------------------------------------------------------------------------------------------------------


async def test_modo_efetivo_relido_a_cada_efeito_e_gravado_no_ledger(conn_app, conn_super, relogio, real):
    """Parada dura: `config.modo = sombra` intercepta o atendimento `real` já aberto em até 5 s (cache do `LeitorConfig`)."""
    leitor = LeitorConfig(relogio)  # ttl padrão: 5 s
    espia = Espia()
    assert (await _executar(conn_app, relogio, real, _t11(real, 1, 1), espia, leitor=leitor)).modo == "real"
    _config(conn_app, relogio, "modo", "sombra")  # outro processo grava (este leitor não sabe)
    relogio.avancar(seconds=5)
    r = await _executar(conn_app, relogio, real, _t11(real, 1, 2), espia, leitor=leitor)
    assert espia.destinos == ["real"], "nada sai depois de 5 s da parada dura"
    assert (r.modo, r.simulado, r.executou, r.estado) == ("sombra", True, False, "ok")
    assert _linha(conn_super, chave_t11(real, 1, 2))[:3] == ("ok", "sombra", True)


async def test_teste_vai_ao_destino_de_teste(conn_app, conn_super, relogio):
    _config(conn_app, relogio, "modo", "real")
    atd = inserir_atendimento(conn_super, estado="aberto", modo="teste", iniciado_em=relogio.agora())
    espia = Espia()
    r = await _executar(conn_app, relogio, atd, _t11(atd), espia)
    assert espia.destinos == ["teste"] and r.modo == "teste" and r.executou  # `simulado` do banco = modo <> real (o teste também)


@pytest.mark.parametrize(("do_atendimento", "global_"), [("sombra", "real"), ("duble", "real"), ("real", "duble"), ("teste", "sombra")])
async def test_sombra_e_duble_nunca_chamam_o_destino(conn_app, conn_super, relogio, do_atendimento, global_):
    _config(conn_app, relogio, "modo", global_)
    atd = inserir_atendimento(conn_super, estado="aberto", modo=do_atendimento, iniciado_em=relogio.agora())
    espia, simulador = Espia(), Espia(Desfecho("ok", ref_externa="simulada"))
    r = await _executar(conn_app, relogio, atd, _t11(atd), espia, simular=simulador)
    assert espia.destinos == [] and simulador.destinos == [r.modo] and r.simulado and r.ref_externa == "simulada"


# --- posse real e devolução ------------------------------------------------------------------------------------------------------------


def _assumir(atd) -> Pedido:
    return Pedido(ferramenta="assumir", ferramenta_versao="1.0.0", classe_efeito="acao_interna", chave_logica=f"assumir:{atd}")


def _t12(atd) -> Pedido:
    return Pedido(ferramenta="t12", ferramenta_versao="1.0.0", classe_efeito="acao_interna", chave_logica=f"t12:{atd}", devolucao=True)


async def test_posse_real_so_com_assumir_ok_real_ou_teste(conn_app, conn_super, relogio):
    _config(conn_app, relogio, "modo", "real")
    casos = {}
    for modo, desfecho in (("real", "ok"), ("teste", "ok"), ("sombra", "ok"), ("real", "indeterminado")):
        atd = inserir_atendimento(conn_super, estado="aberto", modo=modo, iniciado_em=relogio.agora())
        assert not posse_real(conn_app, atd)
        await _executar(conn_app, relogio, atd, _assumir(atd), Espia(Desfecho(desfecho)))
        casos[(modo, desfecho)] = posse_real(conn_app, atd)
    assert casos == {("real", "ok"): True, ("teste", "ok"): True, ("sombra", "ok"): False, ("real", "indeterminado"): False}


async def test_parada_dura_devolve_real_quem_tem_posse_real(conn_app, conn_super, relogio, real):
    await _executar(conn_app, relogio, real, _assumir(real), Espia())
    _config(conn_app, relogio, "modo", "sombra")
    espia = Espia()
    r = await _executar(conn_app, relogio, real, _t12(real), espia)
    assert espia.destinos == ["real"] and (r.modo, r.simulado) == ("real", False), "a devolução de quem tem posse real é real (exceção 1)"
    enviar = await _executar(conn_app, relogio, real, _t11(real), espia)
    assert espia.destinos == ["real"] and enviar.simulado, "a parada dura continua barrando o envio"


async def test_sombra_nascida_nunca_chama_o_destino_nem_na_devolucao(conn_app, conn_super, relogio):
    _config(conn_app, relogio, "modo", "real")
    atd = inserir_atendimento(conn_super, estado="aberto", modo="sombra", iniciado_em=relogio.agora())
    await _executar(conn_app, relogio, atd, _assumir(atd), Espia())
    espia = Espia()
    r = await _executar(conn_app, relogio, atd, _t12(atd), espia)
    assert espia.destinos == [] and r.simulado and r.modo == "sombra"


# --- T7: confirmação e vaga única ------------------------------------------------------------------------------------------------------


INSTANTE_PERGUNTA = ff.INSTANTE_UTIL - timedelta(minutes=2)  # o relógio dos testes está 2 min depois da pergunta


def _confirmacao(conn, atd, estado: str = "aceita", *, tipo: str = "digitacao", banco: str = "FACTA", respondida_apos_min: int = 1):
    """Confirmação perguntada 2 min antes do relógio do teste (vence em 30 min); a aceita foi respondida `respondida_apos_min` depois."""
    aceita = estado == "aceita"
    return conn.execute(
        "INSERT INTO ia.confirmacao (atendimento_id, tipo, banco, oferta_versao, valores_hash, texto_id, estado, classe_resposta, respondida_em,"
        " resposta_ordem, pergunta_ordem, criada_em, expira_em) VALUES (%s, %s, %s, 1, %s, 'tx-28', %s, %s, %s, %s, 1, %s, %s)"
        " RETURNING confirmacao_id",
        (
            atd, tipo, banco, "a" * 64, estado, "sim" if aceita else None,
            INSTANTE_PERGUNTA + timedelta(minutes=respondida_apos_min) if aceita else None, 2 if aceita else None,
            INSTANTE_PERGUNTA, INSTANTE_PERGUNTA + timedelta(minutes=30),
        ),
    ).fetchone()[0]  # fmt: skip


def _t7(atd, confirmacao_id, tentativa: int = 1, banco: str = "FACTA", args_hash: str = "b" * 64) -> Pedido:
    return Pedido(
        ferramenta="t7", ferramenta_versao="1.0.0", classe_efeito="efeito_irreversivel", chave_logica=f"t7:{atd}:{banco}:{tentativa}",
        banco=banco, confirmacao_id=confirmacao_id, args_hash=args_hash, tentativa_n=tentativa,
    )  # fmt: skip


@pytest.mark.parametrize("confirmacao", ["nenhuma", "pendente", "de_outro_atendimento"])
async def test_t7_sem_confirmacao_aceita_levanta_antes_do_banco(conn_app, conn_super, relogio, real, confirmacao):
    if confirmacao == "nenhuma":
        confirmacao_id = None
    elif confirmacao == "pendente":
        confirmacao_id = _confirmacao(conn_super, real, "pendente")
    else:
        outro = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
        confirmacao_id = _confirmacao(conn_super, outro)
    espia = Espia()
    with pytest.raises(ConfirmacaoAusente):
        await _executar(conn_app, relogio, real, _t7(real, confirmacao_id), espia)
    assert espia.destinos == []
    assert conn_super.execute("SELECT count(*) FROM ia.ferramenta_chamada WHERE atendimento_id = %s", (real,)).fetchone()[0] == 0


async def test_t7_viva_unica_por_pessoa_banco_em_outro_atendimento(conn_app, conn_super, relogio):
    _config(conn_app, relogio, "modo", "real")
    pessoa = uuid.uuid4()
    primeiro = inserir_atendimento(
        conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora() - timedelta(hours=2), pessoa_id=pessoa
    )
    segundo = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora(), pessoa_id=pessoa)
    await _executar(conn_app, relogio, primeiro, _t7(primeiro, _confirmacao(conn_super, primeiro)), Espia(Desfecho("indeterminado")))
    espia = Espia()
    with pytest.raises(EfeitoOcupado):
        await _executar(conn_app, relogio, segundo, _t7(segundo, _confirmacao(conn_super, segundo)), espia)
    assert espia.destinos == [], "a T7 indeterminada da mesma pessoa e banco ocupa a vaga: nada se digita"


async def test_parada_dura_sem_posse_real_simula_a_devolucao(conn_app, conn_super, relogio, real):
    """Nasceu `real` mas o `assumir` nunca fechou `ok`: não tomou nada, não tem o que devolver de verdade (exceção 2 do §6)."""
    await _executar(conn_app, relogio, real, _assumir(real), Espia(Desfecho("indeterminado")))
    _config(conn_app, relogio, "modo", "sombra")
    espia = Espia()
    r = await _executar(conn_app, relogio, real, _t12(real), espia)
    assert espia.destinos == [] and (r.modo, r.simulado) == ("sombra", True)


# --- revisão da B1.6a (04/11): A1 a A6 ---------------------------------------------------------------------------------------------------


async def _sem_resposta(_destino: str) -> Desfecho:
    raise TimeoutError("destino sem resposta")


def _t12_interno(atd) -> Pedido:
    return Pedido(ferramenta="t12", ferramenta_versao="1.0.0", classe_efeito="acao_interna", chave_logica=f"t12:{atd}")


def _chamadas(conn, atd) -> int:
    return conn.execute("SELECT count(*) FROM ia.ferramenta_chamada WHERE atendimento_id = %s", (atd,)).fetchone()[0]


@pytest.mark.parametrize("assumir", ["indeterminado", "transitorio", "nunca_rodou"])
async def test_devolucao_sem_posse_real_e_simulada_mesmo_com_o_global_real(conn_app, conn_super, relogio, real, assumir):
    """A1 · 08 §6, exceção 2: sem posse real (o `assumir` nunca fechou `ok`) a devolução é simulada por inteiro, também com
    `config.modo = real`: o T12 real rodaria o rodízio do `zVuE` e o `restaurar` mexeria num chat que a IA nunca tomou."""
    if assumir == "indeterminado":
        await _executar(conn_app, relogio, real, _assumir(real), Espia(Desfecho("indeterminado")))
    elif assumir == "transitorio":
        await _executar(conn_app, relogio, real, _assumir(real), Espia(acao=_sem_resposta))
    espia = Espia()
    r = await _executar(conn_app, relogio, real, _t12(real), espia)
    assert espia.destinos == [] and (r.modo, r.simulado, r.executou) == ("sombra", True, False)
    assert _linha(conn_super, f"t12:{real}")[:2] == ("ok", "sombra")


async def test_devolucao_em_teste_sem_posse_real_tambem_e_simulada(conn_app, conn_super, relogio):
    _config(conn_app, relogio, "modo", "real")
    atd = inserir_atendimento(conn_super, estado="aberto", modo="teste", iniciado_em=relogio.agora())
    espia = Espia()
    r = await _executar(conn_app, relogio, atd, _t12(atd), espia)
    assert espia.destinos == [] and r.modo == "sombra"


@pytest.mark.parametrize("defeito", ["outro_banco", "outro_tipo", "vencida", "respondida_depois_do_prazo"])
async def test_t7_com_confirmacao_que_nao_e_deste_dado_levanta_antes_do_banco(conn_app, conn_super, relogio, real, defeito):
    """A2 · o «sim» é ligado ao DADO (DDL 0001): do tipo `digitacao`, do MESMO banco, respondido no prazo e ainda não vencido no relógio
    de quem executa."""
    if defeito == "outro_banco":
        pedido = _t7(real, _confirmacao(conn_super, real), banco="C6")  # o «sim» foi dado para a FACTA
    elif defeito == "outro_tipo":
        pedido = _t7(real, _confirmacao(conn_super, real, tipo="consulta"))
    elif defeito == "vencida":
        pedido = _t7(real, _confirmacao(conn_super, real))
        relogio.avancar(hours=3)
    else:
        pedido = _t7(real, _confirmacao(conn_super, real, respondida_apos_min=31))
    espia = Espia()
    with pytest.raises(ConfirmacaoAusente):
        await _executar(conn_app, relogio, real, pedido, espia)
    assert espia.destinos == [] and _chamadas(conn_super, real) == 0


async def test_t7_nao_reusa_a_confirmacao_gasta_por_outra_chave(conn_app, conn_super, relogio, real):
    """A2 · uso único: a 1ª T7 ficou `transitorio` (fora dos índices de vaga única) e ainda pode digitar; a 2ª tentativa com o mesmo
    «sim» é barrada antes do banco."""
    confirmacao = _confirmacao(conn_super, real)
    await _executar(conn_app, relogio, real, _t7(real, confirmacao), Espia(Desfecho("transitorio", http_bucket="5xx", nada_saiu=True)))
    espia = Espia()
    with pytest.raises(ConfirmacaoAusente):
        await _executar(conn_app, relogio, real, _t7(real, confirmacao, tentativa=2), espia)
    assert espia.destinos == [] and _chamadas(conn_super, real) == 1


async def test_t7_corrigivel_nao_gasta_a_confirmacao(conn_app, conn_super, relogio, real):
    """O banco devolveu `corrigivel` (a proposta não nasceu): a 2ª tentativa pode usar o mesmo «sim»."""
    confirmacao = _confirmacao(conn_super, real)
    await _executar(conn_app, relogio, real, _t7(real, confirmacao), Espia(Desfecho("corrigivel", http_bucket="4xx")))
    espia = Espia()
    r = await _executar(conn_app, relogio, real, _t7(real, confirmacao, tentativa=2), espia)
    assert espia.destinos == ["real"] and r.estado == "ok"


async def test_t7_repetida_confere_a_confirmacao_so_quando_vai_chamar(conn_app, conn_super, relogio, real):
    """A repetição de uma T7 `transitorio` vai chamar de novo: com o «sim» vencido, não chama. A de uma T7 terminal só devolve o
    gravado, mesmo vencido (quem pergunta «já digitou?» não pode ouvir `ConfirmacaoAusente`)."""
    transitoria = _t7(real, _confirmacao(conn_super, real))
    await _executar(conn_app, relogio, real, transitoria, Espia(Desfecho("transitorio", http_bucket="5xx", nada_saiu=True)))
    outro = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
    terminal = _t7(outro, _confirmacao(conn_super, outro))
    await _executar(conn_app, relogio, outro, terminal, Espia())
    relogio.avancar(hours=1)
    espia = Espia()
    with pytest.raises(ConfirmacaoAusente):
        await _executar(conn_app, relogio, real, transitoria, espia)
    r = await _executar(conn_app, relogio, outro, terminal, espia)
    assert espia.destinos == [] and (r.estado, r.repetido) == ("ok", True)
    assert _linha(conn_super, transitoria.chave_logica)[0] == "transitorio"


async def test_chave_de_outro_atendimento_e_recusada_sem_chamar(conn_app, conn_super, relogio, real):
    """A3 · a `idem_key` é única no banco todo: o pedido de B com a chave de A não reivindica a linha de A."""
    await _executar(conn_app, relogio, real, _t12_interno(real), Espia(acao=_sem_resposta))
    outro = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
    espia = Espia()
    with pytest.raises(ChaveDivergente):
        await _executar(conn_app, relogio, outro, _t12_interno(real), espia)
    assert espia.destinos == [] and _linha(conn_super, f"t12:{real}")[0] == "transitorio"


async def test_chave_com_outros_argumentos_e_recusada_sem_chamar(conn_app, conn_super, relogio, real):
    confirmacao = _confirmacao(conn_super, real)
    await _executar(conn_app, relogio, real, _t7(real, confirmacao), Espia(Desfecho("transitorio", http_bucket="5xx", nada_saiu=True)))
    espia = Espia()
    with pytest.raises(ChaveDivergente):
        await _executar(conn_app, relogio, real, _t7(real, confirmacao, args_hash="c" * 64), espia)
    assert espia.destinos == []


async def test_transitorio_real_nao_e_rebaixado_pela_parada_dura(conn_app, conn_super, relogio, real):
    """A4 · o `assumir` em `real` sem resposta pode ter tomado o chat. Reexecutado sob parada dura, não vira `ok`/`sombra` (o que
    apagaria a tentativa real e a posse): fica `transitorio` em `real`, sem chamar, até o global voltar."""
    primeiro = await _executar(conn_app, relogio, real, _assumir(real), Espia(acao=_sem_resposta))
    assert (primeiro.estado, primeiro.modo) == ("transitorio", "real")
    _config(conn_app, relogio, "modo", "sombra")
    espia = Espia()
    r = await _executar(conn_app, relogio, real, _assumir(real), espia)
    assert espia.destinos == [] and (r.estado, r.modo, r.executou, r.repetido) == ("transitorio", "real", False, True)
    assert _linha(conn_super, f"assumir:{real}")[:2] == ("transitorio", "real")
    _config(conn_app, relogio, "modo", "real")
    de_volta = await _executar(conn_app, relogio, real, _assumir(real), espia)
    assert espia.destinos == ["real"] and de_volta.estado == "ok" and posse_real(conn_app, real)


async def test_reivindicacao_reconfere_a_cerca_na_mesma_transacao(conn_app, conn_super, relogio, real, monkeypatch):
    """A5 · entre o ROLLBACK da reserva (a chave já existia) e o CAS da reivindicação, outra execução moveu a `versao`: não chama."""
    await _executar(conn_app, relogio, real, _t12_interno(real), Espia(acao=_sem_resposta))
    v = _versao(conn_app, real)
    original = ledger._reservar

    def reservar_e_ser_superado(*args):
        resultado = original(*args)
        conn_super.execute("UPDATE ia.atendimento SET versao = versao + 1 WHERE atendimento_id = %s", (real,))
        return resultado

    monkeypatch.setattr(ledger, "_reservar", reservar_e_ser_superado)
    espia = Espia()
    with pytest.raises(ConflitoVersao):
        await _executar(conn_app, relogio, real, _t12_interno(real), espia, cerca=Cerca(v))
    assert espia.destinos == [] and _linha(conn_super, f"t12:{real}")[0] == "transitorio"


async def test_reivindicacao_sem_cerca_recusa_atendimento_encerrado_no_meio(conn_app, conn_super, relogio, real, monkeypatch):
    await _executar(conn_app, relogio, real, _t12_interno(real), Espia(acao=_sem_resposta))
    original = ledger._reservar

    def reservar_e_encerrar(*args):
        resultado = original(*args)
        conn_super.execute(
            "UPDATE ia.atendimento SET estado = 'encerrado', desfecho = 'sem_venda', encerrado_em = %s, lease_ate = NULL"
            " WHERE atendimento_id = %s",
            (relogio.agora(), real),
        )
        return resultado

    monkeypatch.setattr(ledger, "_reservar", reservar_e_encerrar)
    espia = Espia()
    with pytest.raises(TransicaoInvalida):
        await _executar(conn_app, relogio, real, _t12_interno(real), espia)
    assert espia.destinos == []


async def test_simulacao_que_falha_fica_transitorio_e_repete(conn_app, conn_super, relogio):
    """A6 · em `sombra` nada sai: a exceção do `simular` não deixa a linha `enviada` (que o retry daria como `indeterminado`)."""
    _config(conn_app, relogio, "modo", "sombra")
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())

    async def quebra(_modo: str) -> Desfecho:
        raise RuntimeError("harness caiu")

    espia = Espia()
    r = await _executar(conn_app, relogio, atd, _t11(atd), espia, simular=quebra)
    assert espia.destinos == [] and (r.estado, r.modo) == ("transitorio", "sombra")
    de_novo = await _executar(conn_app, relogio, atd, _t11(atd), espia, simular=Espia(Desfecho("ok", ref_externa="simulada")))
    assert espia.destinos == [] and (de_novo.estado, de_novo.repetido, de_novo.ref_externa) == ("ok", True, "simulada")


async def test_corte_na_simulacao_fica_transitorio(conn_app, conn_super, relogio):
    _config(conn_app, relogio, "modo", "sombra")
    atd = inserir_atendimento(conn_super, estado="aberto", modo="real", iniciado_em=relogio.agora())
    comecou = asyncio.Event()

    async def trava(_modo: str) -> Desfecho:
        comecou.set()
        await asyncio.sleep(5)
        return Desfecho("ok")

    tarefa = asyncio.create_task(_executar(conn_app, relogio, atd, _t11(atd), Espia(), simular=trava))
    await asyncio.wait_for(comecou.wait(), 5)
    tarefa.cancel()
    with pytest.raises(asyncio.CancelledError):
        await tarefa
    assert _linha(conn_super, chave_t11(atd, 1, 1))[:2] == ("transitorio", "sombra")
