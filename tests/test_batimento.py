"""Consumo do batimento v2 (contrato 08 §7.4, D-15 fail-closed, R2-04): relógio falso, fonte falsa, nada sai para fora."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ia_atendimento.batimento import BatimentoInvalido, LeitorBatimento, ler_batimento
from ia_atendimento.relogio import RelogioFalso
from tests.apoio_b16b import AlertasFalsos, FonteFalsa, batimento_v2

T0 = datetime(2026, 11, 20, 14, 0, tzinfo=UTC)


def _leitor(corpo=None, agora=T0):
    alertas, relogio = AlertasFalsos(), RelogioFalso(agora)
    return LeitorBatimento(FonteFalsa(corpo), relogio, alertas), relogio, alertas


@pytest.mark.parametrize(("idade_s", "bloqueia"), [(59, False), (75, False), (89, False), (91, True)])
async def test_batimento_idade_59_75_89s_nao_alerta_91s_alerta(idade_s, bloqueia):
    leitor, _, alertas = _leitor(batimento_v2(T0 - timedelta(seconds=idade_s)))
    await leitor.atualizar()
    situacao = leitor.situacao("venda:x")
    assert (situacao == "indisponivel") is bloqueia
    assert ("batimento_indisponivel" in alertas.codigos("critico")) is bloqueia


async def test_batimento_ausente_ou_velho_bloqueia_efeito_e_alerta():
    leitor, relogio, alertas = _leitor(None)
    await leitor.atualizar()
    assert leitor.situacao("venda:x") == "indisponivel"
    leitor._fonte.corpo = batimento_v2(T0)
    await leitor.atualizar()
    assert leitor.situacao("venda:x") == "livre"
    relogio.avancar(seconds=91)  # a vigia morre: o último aceito envelhece
    await leitor.atualizar()
    assert leitor.situacao("venda:x") == "indisponivel"
    assert alertas.codigos("critico").count("batimento_indisponivel") == 2


@pytest.mark.parametrize(
    "corpo",
    [
        {"v": 1, "gerado_em": T0.isoformat(), "seq": 1},
        {"v": 2, "gerado_em": "ontem", "seq": 1},
        {"v": 2, "gerado_em": "2026-11-20T14:00:00", "seq": 1},
        {"v": 2, "gerado_em": T0.isoformat(), "seq": -1},
        {"v": 2, "gerado_em": T0.isoformat(), "seq": 1, "impedidos": {"venda:x": "talvez"}},
        {"v": 2, "gerado_em": T0.isoformat(), "seq": 1, "vivos": ["venda:x"]},
        "nao e json",
    ],
)
async def test_forma_invalida_derruba_o_aceito_e_alerta(corpo):
    leitor, _, alertas = _leitor(batimento_v2(T0))
    await leitor.atualizar()
    leitor._fonte.corpo = corpo
    await leitor.atualizar()
    assert leitor.situacao("venda:x") == "indisponivel"
    assert "batimento_invalido" in alertas.codigos("critico")
    with pytest.raises(BatimentoInvalido):
        ler_batimento(corpo)


async def test_seq_que_regride_e_recusado():
    leitor, relogio, alertas = _leitor(batimento_v2(T0, seq=10, impedidos={"venda:a": "devolvido"}))
    await leitor.atualizar()
    relogio.avancar(seconds=60)
    leitor._fonte.corpo = batimento_v2(relogio.agora(), seq=9)
    await leitor.atualizar()
    assert "batimento_seq_regrediu" in alertas.codigos("critico")
    assert leitor.situacao("venda:a") == "impedido"  # vale o seq 10


async def test_fonte_que_levanta_conta_como_ausente():
    class Quebrada:
        async def buscar(self):
            raise OSError("rede")

    alertas = AlertasFalsos()
    leitor = LeitorBatimento(Quebrada(), RelogioFalso(T0), alertas)
    await leitor.atualizar()
    assert leitor.situacao("venda:x") == "indisponivel"


async def test_impedidos_barra_sempre():
    leitor, _, _ = _leitor(batimento_v2(T0, impedidos={"venda:a": "devolvendo"}, vivos={"venda:a": "aberto"}))
    await leitor.atualizar()
    assert leitor.situacao("venda:a") == "impedido"
    assert leitor.situacao("venda:a", esperado_em_vivos="aberto") == "impedido"


async def test_batimento_vivos_exigido_no_boot_e_na_retomada():
    leitor, _, alertas = _leitor(batimento_v2(T0, vivos={"venda:a": "pausado"}))
    await leitor.atualizar()
    assert leitor.recem_voltou  # processo recém-iniciado
    assert leitor.situacao("venda:a", esperado_em_vivos="aberto") == "fora_de_vivos"
    assert leitor.situacao("venda:a", esperado_em_vivos="pausado") == "livre"
    assert not leitor.recem_voltou
    assert "fora_de_vivos" in alertas.codigos("amarelo")


async def test_ausencia_em_vivos_nao_autoriza():
    leitor, _, _ = _leitor(batimento_v2(T0, vivos={}))
    await leitor.atualizar()
    assert leitor.situacao("venda:a", esperado_em_vivos="aberto") == "fora_de_vivos"
    assert leitor.situacao("venda:a") == "livre"  # o iniciar (regra iii) e o repasse usam só a regra (i)
