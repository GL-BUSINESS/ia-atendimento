"""Os 13 tipos de passo (classes Pydantic + `texto_passo`) e a PII fora da trilha de erro. Sem banco."""

from __future__ import annotations

import json
import re
import sys
import threading
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ia_atendimento.mascara import mascarar
from ia_atendimento.passos import (
    TIPOS_DE_PASSO,
    AnotacaoOperador,
    DecisaoModelo,
    Erro,
    MensagemRecebida,
    RespostaEnviada,
    criar,
    texto_passo,
)
from ia_atendimento.scrubber import EntradaInvalida, formatar_sem_pii, instalar_excepthook
from tests.apoio_b12 import CPF_SINTETICO, MARCADOR
from tests.conftest import MIGRACOES

DOURADO = json.loads((Path(__file__).parent / "golden" / "texto_passo.json").read_text(encoding="utf-8"))
FP = "a" * 64
NOMES = ("Maria Souza",)  # nome fictício do cliente da conversa
CHAVE = "cg:0123456789abcdef01234567:0f1e2d3c4b5a6978"


def test_texto_mensagem_recebida_nao_vaza_texto():
    dados = MensagemRecebida(msg_chave=CHAVE, msg_fingerprint=FP, msg_tipo="texto", msg_tamanho=42, origem_evento="webhook")
    assert texto_passo(dados) == "Cliente enviou texto (42 caracteres)."


def test_tipos_do_codigo_sao_os_13_do_ddl():
    ddl = (MIGRACOES / "0001_esquema.up.sql").read_text(encoding="utf-8")
    bloco = re.search(r"passo_tipo_check CHECK \(tipo IN \(([^)]*)\)", ddl)
    assert bloco is not None
    do_ddl = tuple(re.findall(r"'([a-z_]+)'", bloco.group(1)))
    assert len(do_ddl) == 13
    assert set(TIPOS_DE_PASSO) == set(do_ddl)
    assert {caso["tipo"] for caso in DOURADO} == set(do_ddl)


@pytest.mark.parametrize("caso", DOURADO, ids=[f"{i:02d}-{c['tipo']}" for i, c in enumerate(DOURADO)])
def test_texto_dos_13_tipos_bate_com_o_arquivo_dourado(caso):
    texto = texto_passo(criar(caso["tipo"], nomes=NOMES, **caso["dados"]))
    assert texto == caso["texto"]
    assert 1 <= len(texto) <= 1000
    assert mascarar(texto) == texto, "o texto do passo não pode conter nada que a máscara trocaria"


def _preencher_livres(caso: dict) -> dict:
    """Põe o marcador e um CPF sintético em todo campo de texto livre que o tipo aceita (só `motivo`: o modelo escreve)."""
    dados = dict(caso["dados"])
    if caso["tipo"] == "decisao":
        dados["motivo"] = f"o cliente disse {MARCADOR} e informou {CPF_SINTETICO}"
    return dados


@pytest.mark.parametrize("caso", DOURADO, ids=[f"{i:02d}-{c['tipo']}" for i, c in enumerate(DOURADO)])
def test_13_tipos_de_passo_sem_citar_o_cliente(caso):
    dados = criar(caso["tipo"], nomes=NOMES, **_preencher_livres(caso))
    texto = texto_passo(dados)
    assert MARCADOR not in texto
    assert CPF_SINTETICO not in texto
    colunas = {k: str(v) for k, v in dados.colunas(NOMES).items()}
    assert CPF_SINTETICO not in " ".join(colunas.values()), "o motivo do modelo é mascarado antes de ir à coluna"


def test_motivo_da_decisao_e_mascarado_e_tem_padrao():
    assert criar("decisao", motor="regra").colunas(NOMES)["motivo"] == "(não informado)"
    com_cpf = criar("decisao", motor="regra", motivo=f"cpf {CPF_SINTETICO}")
    assert com_cpf.colunas(NOMES)["motivo"] == "cpf [CPF]"


def test_motivo_da_decisao_nao_leva_o_nome_do_cliente_s1():
    """Achado S1: `mascarar` sozinho não pega nome. Com os nomes da conversa o nome vira [NOME]; sem eles o texto é redigido."""
    dados = criar("decisao", motor="regra", motivo="Maria Souza aceitou a oferta")
    assert dados.colunas(NOMES)["motivo"] == "[NOME] aceitou a oferta"
    assert dados.colunas(())["motivo"] == "Maria Souza aceitou a oferta"  # conferido: não há nome a esconder
    assert "Maria" not in dados.colunas()["motivo"], "nomes indisponíveis: nada de texto livre"
    assert dados.colunas()["motivo"] == "(texto redigido)"


def test_anotacao_com_nome_do_cliente_e_recusada_s1():
    nota = "cliente Maria Souza pediu para ligar"
    with pytest.raises(EntradaInvalida):
        criar("anotacao_operador", nomes=NOMES, operador="op@exemplo.invalid", resultado="observacao", nota=nota)
    with pytest.raises(EntradaInvalida):  # variante: só o primeiro nome, sem acento e em caixa diferente
        criar("anotacao_operador", nomes=("Maria Souza",), operador="op@exemplo.invalid", resultado="observacao", nota="MARIA ligou")
    with pytest.raises(EntradaInvalida):  # nomes indisponíveis: recusa em vez de aceitar
        criar("anotacao_operador", operador="op@exemplo.invalid", resultado="observacao", nota="retorno amanha")
    ok = criar("anotacao_operador", nomes=NOMES, operador="op@exemplo.invalid", resultado="observacao", nota="retorno amanha")
    assert texto_passo(ok) == "Anotação (observacao): retorno amanha"


@pytest.mark.parametrize(
    ("tipo", "extra"),
    [
        ("erro", {"intencao": "aceita_oferta"}),  # intenção só na decisão do modelo
        ("erro", {"tx_id": "TX-03"}),  # 3c: tx_id só em resposta, lembrete, repasse e agendamento
        ("resposta_enviada", {"janela_24h": True}),  # janela_24h só no lembrete
        ("resposta_enviada", {"confianca": "alta"}),
        ("opt_out", {"tx_id": "TX-03"}),
        ("mensagem_recebida", {"fora_de_ordem": False, "verif_det": []}),
    ],
)
def test_cada_classe_de_passo_recusa_o_campo_que_o_check_proibe(tipo, extra):
    base = {c["tipo"]: c["dados"] for c in reversed(DOURADO)}[tipo]
    with pytest.raises(EntradaInvalida):
        criar(tipo, **{**base, **extra})


def test_envio_sem_verif_det_e_recusado_e_lista_vazia_e_aceita():
    with pytest.raises(EntradaInvalida):
        criar("resposta_enviada", entrega="aceito")
    with pytest.raises(EntradaInvalida):
        criar("lembrete", entrega="aceito", janela_24h=True)
    assert criar("resposta_enviada", entrega="aceito", verif_det=[]).colunas()["verif_det"] == []


def test_lembrete_pago_exige_custo_e_dentro_da_janela_exige_custo_zero():
    base = {"entrega": "aceito", "verif_det": []}
    with pytest.raises(EntradaInvalida):
        criar("lembrete", **base, janela_24h=False)  # fora da janela = template pago: custo > 0
    with pytest.raises(EntradaInvalida):
        criar("lembrete", **base, janela_24h=True, custo_brl="0.45")
    assert criar("lembrete", **base, janela_24h=False, custo_brl="0.45").colunas()["custo_brl"] == Decimal("0.45")
    assert criar("lembrete", **base, janela_24h=True).colunas()["custo_brl"] == Decimal(0)


def test_decisao_do_modelo_sem_modelo_ou_sem_intencao_e_recusada():
    ok = {"motor": "modelo", "intencao": "duvida", "confianca": "media", "modelo": "deepseek-v4p1-flash-1017", "provedor": "fireworks-us"}
    assert criar("decisao", **ok)
    for faltando in ("modelo", "provedor", "intencao", "confianca"):
        with pytest.raises(EntradaInvalida):
            criar("decisao", **{k: v for k, v in ok.items() if k != faltando})
    with pytest.raises(EntradaInvalida):  # decisão de regra não tem intenção nem confiança
        criar("decisao", motor="regra", intencao="duvida", confianca="alta")


def test_t4_t7_sem_confirmacao_ref_recusado():
    for ferramenta in ("t4", "t7"):
        with pytest.raises(EntradaInvalida):
            criar("chamada_ferramenta", ferramenta=ferramenta, ferramenta_versao="1.0.0")
    assert criar("chamada_ferramenta", ferramenta="t1", ferramenta_versao="1.0.0")


def test_confirmacao_invalidada_exige_invalidacao_e_so_ela():
    base = {"confirmacao_id": "01a18a0a-6522-722b-8bf2-cced4767f1aa", "confirmacao_ref": "0123456789abcdef"}
    with pytest.raises(EntradaInvalida):
        criar("confirmacao", **base, resultado="invalidada")
    with pytest.raises(EntradaInvalida):
        criar("confirmacao", **base, resultado="pergunta", invalidacao="valor_mudou")


def test_anotacao_com_pii_e_recusada_como_texto_livre():
    with pytest.raises(EntradaInvalida):
        criar("anotacao_operador", nomes=NOMES, operador="op@exemplo.invalid", resultado="observacao", nota=f"ligar para {CPF_SINTETICO}")
    with pytest.raises(EntradaInvalida):
        criar("anotacao_operador", nomes=NOMES, operador="op@exemplo.invalid", resultado="observacao", nota="x" * 251)


# --- PII fora da trilha de erro --------------------------------------------------------------------------------------------------


def test_validation_error_nao_vaza_input():
    pii = f"cliente {CPF_SINTETICO} {MARCADOR}"
    # camada 1: o erro cru do Pydantic não cita o valor (hide_input_in_errors)
    for modelo, campos in (
        (MensagemRecebida, {"msg_chave": pii, "msg_fingerprint": FP, "msg_tipo": "texto", "msg_tamanho": 1, "origem_evento": "webhook"}),
        (Erro, {"peca": pii}),
        (RespostaEnviada, {"entrega": pii, "verif_det": []}),
        (DecisaoModelo, {"motor": "modelo", "intencao": pii, "confianca": "alta", "modelo": "m", "provedor": "p"}),
        (AnotacaoOperador, {"operador": "op@exemplo.invalid", "resultado": pii, "nota": "x"}),
    ):
        with pytest.raises(ValidationError) as cru:
            modelo(**campos)
        assert MARCADOR not in str(cru.value)
        assert CPF_SINTETICO not in str(cru.value)
        assert MARCADOR not in repr(cru.value)
    # camada 2: `.errors()` e `.json()` guardam o input; `criar` troca o erro por um sem valor e sem causa encadeada
    with pytest.raises(EntradaInvalida) as nosso:
        criar("erro", peca=pii)
    assert nosso.value.__context__ is None
    assert nosso.value.__cause__ is None
    saida = " ".join([str(nosso.value), repr(nosso.value), *nosso.value.detalhes, formatar_sem_pii(nosso.value)])
    assert MARCADOR not in saida
    assert CPF_SINTETICO not in saida


def test_scrubber_mascara_traceback_e_excecoes_encadeadas():
    try:
        try:
            raise RuntimeError(f"falha com {CPF_SINTETICO} e fulano@exemplo.invalid")
        except RuntimeError as causa:
            raise ValueError("segundo erro") from causa
    except ValueError as erro:
        texto = formatar_sem_pii(erro)
    assert CPF_SINTETICO not in texto
    assert "fulano@exemplo.invalid" not in texto
    assert "[CPF]" in texto
    assert "segundo erro" in texto


def test_excepthook_nao_imprime_pii(capsys):
    anterior = (sys.excepthook, threading.excepthook)
    try:
        instalar_excepthook()
        try:
            raise RuntimeError(f"cpf {CPF_SINTETICO}")
        except RuntimeError as erro:
            sys.excepthook(type(erro), erro, erro.__traceback__)
    finally:
        sys.excepthook, threading.excepthook = anterior
    erro_padrao = capsys.readouterr().err
    assert CPF_SINTETICO not in erro_padrao
    assert "[CPF]" in erro_padrao
