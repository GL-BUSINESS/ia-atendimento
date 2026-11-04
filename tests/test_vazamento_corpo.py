"""O corpo HTTP COMPLETO que o provedor recebe, fase a fase, com o estado mais rico possível (sonda p2 da revisão 1 da B1.4).

Monta o contexto de verdade (Postgres 18 descartável: `abrir` → `iniciar` → estado), com linhas ANTIGAS gravadas sem máscara, resumo cru, `perfil` rico, oferta, opções,
confirmação, resultado de T2/T3/T5/T10 com valor/CPF/link/protocolo e os exemplos da F3; roda `executar_turno` contra o `httpx.MockTransport` e procura os itens
proibidos no JSON inteiro da requisição (`messages`, `tools`, parâmetros). Tudo sintético (`000.000.0nn`, `exemplo.test`, valores redondos).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from ia_atendimento import contexto as ctx
from ia_atendimento.agente import Deps, executar_turno
from ia_atendimento.conversa import _gravar
from ia_atendimento.corpus import carregar
from ia_atendimento.linha_tempo import mensagens_pendentes
from ia_atendimento.modelos_conversa import OfertaCorrente
from ia_atendimento.roteiro_f3 import exemplos_da_f3
from ia_atendimento.turno import ACOES_POR_FASE
from tests.apoio_b12 import AGORA
from tests.apoio_b14 import RedeSimulada, abrir_em, agente_na_rede, receber, resposta_da_ia, resposta_openai, settings_de_teste

pytest_plugins = ["tests.apoio_b12"]

RAIZ_DO_CORPUS = Path(__file__).parent / "corpus"
OFERTA_ID = str(uuid.UUID("0194a8b0-2f7e-4c3a-9d41-6b1f0c2e7a55"))
OPCAO_ID = str(uuid.UUID("0194a8b0-2f7e-4c3a-9d41-6b1f0c2e7a66"))
NOME = "Maria Alvardel"
NOMES = (NOME,)
CPF = "000.000.012-34"
CPF_PURO = "00000001234"
FONE = "(11) 91234-5678"
FONE_CHAT = "5511912345678"  # chat_number
EMAIL = "fulano@exemplo.test"
DEPS = Deps(atendimento_id=uuid.UUID(int=7), pessoa_id=uuid.UUID(int=8), nomes=NOMES)
PERFIL = {
    "banco": "FACTA", "origem": "inapp", "ultimo_sentido": "out", "tipo_ultima_fala": "texto", "etapa_inapp": "tela_dados",
    "idade_do_lead_min": 45, "etapas_do_robo_concluidas": 3,
    "faixa_parcela": "200_300", "chat_number": "tem-chave-proibida", "nome": "ZZNOMEZZ", "cpf": "ZZCPFZZ",
}  # fmt: skip
RESULTADOS = {
    "T2": {"fase": "em_esteira", "etapa": "em_esteira", "contrato_vivo": False, "proposta_viva": True, "cpf": CPF, "nome": NOME, "telefone": FONE},
    "T3": {
        "oferta_ref": OFERTA_ID, "status": "ativa", "versao": 2, "valor_liberado": "R$ 5.000,00", "valor_parcela": "R$ 312,45", "prazo": 36,
        "coef_valor": "0.0613", "comissao": "R$ 410,00", "motivo_do_banco": "reprovado por margem de 1.234,56",
        "placeholders": ["valor_liberado", "valor_parcela", "prazo", "5000_00", CPF],
    },
    "T5": {
        "opcoes": [{"opcao_ref": OPCAO_ID, "dentro_da_alcada": True, "valor_liberado": "R$ 4.000,00", "placeholders": ["valor_liberado"]}],
        "sem_opcao": False, "acima_do_maximo": False,
    },
    "T10": {"macro": "pendente", "proxima_acao": "abrir_link", "frase_ref": "ST-01", "status": "em_analise", "link": "https://exemplo.test/assina/abc", "protocolo": "123456789012"},
}  # fmt: skip
PROIBIDOS = [
    CPF, CPF_PURO, "12-34", FONE, "91234-5678", "912345678", FONE_CHAT, EMAIL, "exemplo.test", "fulano", NOME, "Maria", "Alvardel", "alvardel",
    "R$", "5.000,00", "3.000,00", "312,45", "410,00", "1.234,56", "5000", "3000", "4.000,00", "0.0613", "coef_valor", "comissao", "motivo_do_banco",
    OFERTA_ID, "0194a8b0", OPCAO_ID, "faixa_parcela", "200_300", "chat_number", "ZZNOMEZZ", "ZZCPFZZ", "assina/abc", "123456789012",
    str(DEPS.pessoa_id), str(DEPS.atendimento_id), "12/03/1985", "01310-100", "1234-5", "56789-0", "5000_00",
]  # fmt: skip


def _resposta(fase: str):
    acao = sorted(ACOES_POR_FASE[fase])[0]
    return resposta_openai({"intencao": "saudacao", "acao": acao, "confianca": "alta", "sinal": "positivo", "motivo": "x"})


async def _corpo_da_fase(db_conn, relogio, versoes, chaveiro, fase: str, **opcoes) -> tuple[str, ctx.Contexto]:
    atd, _ = abrir_em(
        db_conn, relogio, versoes, fase=fase, perfil=PERFIL,
        oferta_corrente=OfertaCorrente(banco="FACTA", oferta_id=OFERTA_ID, oferta_versao=2),
        opcoes_t5=(OPCAO_ID,), campos_coletados=("pix",), campos_faltantes=("cep",), objecoes=("parcela_alta",), intencoes_recentes=("objecao",),
        flags={"banco_ok": True}, confirmacao={"estado": "pendente", "expira_em": "2026-11-24T13:30:00+00:00"},
        contexto_previo=("origem_inapp",), tentativa_t7={"estado": "indeterminado", "classe": "dado_cliente", "n": 1},
    )  # fmt: skip
    resposta_da_ia(db_conn, atd, chaveiro, f"Oi {NOME}! Aqui é o Amado Batista. Seu CPF {CPF} está certo?", nomes=())
    # linhas ANTIGAS gravadas sem máscara (defesa em profundidade) e um resumo cru
    texto_antigo = f"sou {NOME}, cpf {CPF}, fone {FONE}, mail {EMAIL}, nasci 12/03/1985, cep 01310-100"
    _gravar(db_conn, atd, remetente="cliente", tipo="mensagem", texto=texto_antigo, agora=AGORA, chaveiro=chaveiro, passo_ordem=None)
    texto_ia = "Anotei: agência 1234-5 conta 56789-0, pix 5511912345678"
    _gravar(db_conn, atd, remetente="ia", tipo="mensagem", texto=texto_ia, agora=AGORA, chaveiro=chaveiro, passo_ordem=None)
    resumo = f"{NOME} quer R$ 3.000,00 em 36x, cpf {CPF}"
    _gravar(db_conn, atd, remetente="ia", tipo="resumo", texto=resumo, agora=AGORA, chaveiro=chaveiro, passo_ordem=None, cobre_ate_seq=2)
    pendente = f"{CPF} {FONE} {FONE_CHAT} {EMAIL} sou {NOME} quero R$ 3.000,00 em 36x ou uns 3 mil, 5k; mande em https://exemplo.test/x"
    receber(db_conn, atd, chaveiro, pendente, nomes=NOMES)
    contexto = ctx.montar_contexto(
        db_conn, atd, pendentes=mensagens_pendentes(db_conn, atd), chaveiro=chaveiro, nomes=NOMES, agora=AGORA, resultados=RESULTADOS,
        exemplos=exemplos_da_f3(carregar(RAIZ_DO_CORPUS), fase), **opcoes,
    )  # fmt: skip
    rede = RedeSimulada([_resposta(fase)])
    await executar_turno(agente_na_rede(rede, settings=settings_de_teste()), DEPS, contexto)
    return json.dumps(rede.corpos[0], ensure_ascii=False), contexto


@pytest.mark.parametrize("fase", ["E2", "E3", "E4", "E5", "E6", "E7", "E8"])
async def test_o_corpo_http_inteiro_nao_leva_nenhum_item_proibido(db_conn, relogio, versoes, chaveiro, fase):
    """A espinha da B1.4: nada de CPF, telefone, e-mail, nome, ids reais, valores, coeficiente, comissão, motivo cru, link nem protocolo no que o provedor recebe."""
    corpo, contexto = await _corpo_da_fase(db_conn, relogio, versoes, chaveiro, fase)
    assert [p for p in PROIBIDOS if p in corpo] == []
    assert contexto.tokens_total <= ctx.TETO_TOKENS
    assert '"fase\\":\\"' + fase in corpo  # o corpo é o do estado da fase


async def test_o_corpo_da_e5_com_desvio_liberado_tambem_esta_limpo(db_conn, relogio, versoes, chaveiro):
    corpo, contexto = await _corpo_da_fase(db_conn, relogio, versoes, chaveiro, "E5", desvio_liberado=True)
    assert [p for p in PROIBIDOS if p in corpo] == []
    assert "[dado:" not in "".join(contexto.insumos.pendentes)  # liberado: a mensagem (protegida) vai, não o marcador


async def test_o_corpo_da_e5_sem_desvio_so_leva_o_marcador_do_campo(db_conn, relogio, versoes, chaveiro):
    corpo, contexto = await _corpo_da_fase(db_conn, relogio, versoes, chaveiro, "E5")
    assert contexto.insumos.pendentes == ("[dado:cep]",)
    assert "quero" not in corpo.split("Mensagens pendentes")[-1][:200]
