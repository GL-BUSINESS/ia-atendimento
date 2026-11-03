"""`mensagens.py` (chave de comparação do casamento) e o job `encerrar_por_chave` da parada leve."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ia_atendimento import jobs
from ia_atendimento.mensagens import RespostaMensagem, texto_chave
from ia_atendimento.relogio import RelogioFalso


@pytest.mark.parametrize(
    "a,b",
    [
        ("Quero  a   PROPOSTA", "quero a proposta"),
        ("  oi\n tudo   bem ", "OI TUDO BEM"),
        ("meu cpf é 000.000.012-34", "meu cpf é [CPF]"),  # as duas fontes passam pela mesma máscara
        ("Pedro", "pedro"),
    ],
)
def test_texto_chave_ignora_caixa_espaco_e_pii(a, b):
    assert texto_chave(a) == texto_chave(b)


def test_texto_chave_distingue_textos_diferentes():
    assert texto_chave("sim") != texto_chave("não")
    assert texto_chave("quero a proposta") != texto_chave("quero a proposta agora")


def test_resposta_so_leva_codigos_e_ids_opacos_e_omite_o_que_e_nulo():
    atd = uuid.uuid4()
    assert RespostaMensagem("descartado", motivo="sem_atendimento").corpo() == {
        "recebido": True,
        "resultado": "descartado",
        "motivo": "sem_atendimento",
    }
    corpo = RespostaMensagem(
        "gravado", atendimento_id=atd, ordem=3, fora_de_ordem=False, turno_enfileirado=True, delegacao_externa=False
    ).corpo()
    assert corpo == {
        "recebido": True, "resultado": "gravado", "atendimento_id": str(atd), "ordem": 3, "fora_de_ordem": False, "turno_enfileirado": True,
        "delegacao_externa": False,
    }  # fmt: skip


async def test_job_encerrar_por_chave_chama_o_servico_e_sem_servico_falha_alto():
    chamadas: list[uuid.UUID] = []

    async def encerrar(atendimento_id: uuid.UUID) -> None:
        chamadas.append(atendimento_id)

    relogio = RelogioFalso(datetime(2026, 11, 17, 15, 0, tzinfo=UTC))
    atd = uuid.uuid4()
    await jobs.executar_encerrar_por_chave(jobs.Servicos(relogio=relogio, abrir_conexao=lambda: None, encerrar_por_chave=encerrar), atd)
    assert chamadas == [atd]
    with pytest.raises(jobs.ServicoNaoConfigurado):
        await jobs.executar_encerrar_por_chave(jobs.Servicos(relogio=relogio, abrir_conexao=lambda: None), atd)
