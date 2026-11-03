"""Tempo-limite do turno no modelo (B1.4, achado M-9 da revisão 1; sonda p6): um provedor que PENDURA falha no tempo, sem retentativa escondida do SDK.

O 'provedor' é um servidor em 127.0.0.1 que aceita a conexão e nunca responde: nenhuma rede externa. Escala de décimos de segundo.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import replace

import pytest

from ia_atendimento.agente import Deps, ProvedorFalso, ProvedorIndisponivel, ResolvedorModelo, criar_agente, executar_turno
from ia_atendimento.turno import Turno
from tests.apoio_b14 import MODELO, contexto_falso, settings_de_teste

DEPS = Deps(atendimento_id=uuid.UUID(int=1), pessoa_id=uuid.UUID(int=2))
LIMITE_DO_TESTE_S = 6.0  # se a correção sumir o turno nunca volta: o teste falha por tempo em vez de pendurar a suíte


class _Pendurado:
    """Servidor que aceita e nunca responde; conta as conexões (uma retentativa do SDK abriria a segunda)."""

    def __init__(self) -> None:
        self.conexoes = 0
        self.servidor: asyncio.Server | None = None

    async def _atender(self, leitor: asyncio.StreamReader, escritor: asyncio.StreamWriter) -> None:
        self.conexoes += 1
        try:
            await leitor.read(65536)
            await asyncio.sleep(60)
        except (asyncio.CancelledError, ConnectionError):
            pass
        finally:
            escritor.close()

    async def __aenter__(self) -> _Pendurado:
        self.servidor = await asyncio.start_server(self._atender, "127.0.0.1", 0)
        return self

    async def __aexit__(self, *_: object) -> None:
        assert self.servidor is not None
        self.servidor.close()

    @property
    def url(self) -> str:
        assert self.servidor is not None
        return f"http://127.0.0.1:{self.servidor.sockets[0].getsockname()[1]}/inference/v1"


async def test_cliente_http_tem_tempo_limite_proprio_e_nao_repete_a_chamada():
    """Nível 1 (cliente OpenAI): com o tempo do turno DESLIGADO, só o `timeout` do cliente impede de pendurar; e é UMA conexão (`max_retries=0`)."""
    async with _Pendurado() as servidor:
        s = settings_de_teste(modelo_base_url_1=servidor.url, modelo_timeout_s=0.5)
        agente = replace(criar_agente(ResolvedorModelo(s), MODELO, settings=s), timeout_s=None)
        inicio = time.perf_counter()
        async with asyncio.timeout(LIMITE_DO_TESTE_S):
            with pytest.raises(ProvedorIndisponivel) as erro:
                await executar_turno(agente, DEPS, contexto_falso("E2"))
        gasto = time.perf_counter() - inicio
    assert erro.value.codigo in {"tempo_esgotado", "provedor"} and erro.value.__context__ is None
    assert gasto < 1.5, f"o cliente levou {gasto:.1f}s para desistir de 0,5s"
    assert servidor.conexoes == 1, "retentativa escondida do SDK: uma 2ª conexão ao provedor"


async def test_turno_inteiro_tem_tempo_limite_mesmo_se_o_provedor_for_outro():
    """Nível 2 (`Agent.run`): um `Provedor` que não é o resolvedor (aqui o falso, lento) também é cortado, sem `settings`."""
    falso = ProvedorFalso(_Fixo(), atraso_s=30)
    agente = criar_agente(falso, MODELO, settings=settings_de_teste(modelo_timeout_s=0.3))
    assert agente.timeout_s == pytest.approx(0.6)  # 0,3 s × (1 + output_retries)
    inicio = time.perf_counter()
    async with asyncio.timeout(LIMITE_DO_TESTE_S):
        with pytest.raises(ProvedorIndisponivel) as erro:
            await executar_turno(agente, DEPS, contexto_falso("E2"))
    assert erro.value.codigo == "tempo_esgotado" and time.perf_counter() - inicio < 1.5


def test_sem_settings_o_turno_tem_tempo_limite_padrao_e_o_resolvedor_empresta_o_dele():
    sem = criar_agente(ProvedorFalso(_Fixo()), MODELO)
    assert sem.timeout_s == pytest.approx(16.0)  # nada de `timeout_s=None`: 8 s × 2
    s = settings_de_teste(modelo_timeout_s=3)
    do_resolvedor = criar_agente(ResolvedorModelo(s), MODELO)  # sem `settings=`: o resolvedor tem os dele
    assert do_resolvedor.timeout_s == pytest.approx(6.0) and do_resolvedor.precos == s.precos()


def test_o_tempo_do_settings_tem_teto_de_10_segundos_e_nao_ha_retentativa_do_sdk():
    with pytest.raises(ValueError):
        settings_de_teste(modelo_timeout_s=10.5)
    assert settings_de_teste(modelo_timeout_s=10).modelo_timeout_s == 10
    s = settings_de_teste()
    modelo = ResolvedorModelo(s).resolver("deepseek-v4p1-flash-1017", "fireworks-us", False)
    assert modelo.client.max_retries == 0 and modelo.client.timeout == s.modelo_timeout_s


class _Fixo:
    def responder(self, fase, mensagens):
        return Turno(intencao="saudacao", acao="responder", confianca="alta")
