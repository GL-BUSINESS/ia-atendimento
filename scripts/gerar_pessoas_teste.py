#!/usr/bin/env python3
"""Gera `src/ia_atendimento/pessoas_teste/pessoas.json` (+ `pessoas.sha256`) e `fixtures/duble/*.json` a partir do corpus da F3 (`tests/corpus/`). B2.4.

Uma pessoa por `persona_id` (60 H + 24 P-M): CPF, nome e persona do dublê vêm do corpus; o `pessoa_id` é fixo e legível; as ofertas saem do perfil
(`valor_pre_aprovado_brl`, `prazo_oferta_x`) e da grade de coeficientes do dublê da FACTA (tabela 115716, camada A do bancos-duble). Nenhum dado de pessoa.
As fixtures (`cliente360_oferta`, `3rn_calcular`, `c6_simular`) saem do MESMO catálogo: a oferta de T3 e a simulação de T5 da mesma persona não divergem.
Determinista: sem relógio, sem aleatório. Rode de novo ao mudar o corpus; `--verificar` não grava e sai 1 se o que está versionado difere do gerado.

Uso: uv run python scripts/gerar_pessoas_teste.py [--verificar]
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from ia_atendimento.corpus import carregar  # noqa: E402
from ia_atendimento.corpus.modelos import Persona  # noqa: E402
from ia_atendimento.pessoas_teste.catalogo import ARQUIVO, ARQUIVO_HASH, CatalogoPessoasTeste, hash_canonico  # noqa: E402
from ia_atendimento.pessoas_teste.fixtures_duble import CPF_ECO  # noqa: E402
from ia_atendimento.pessoas_teste.fonte import VALIDADE_PADRAO, FontePessoasTeste  # noqa: E402
from ia_atendimento.relogio import RelogioFalso  # noqa: E402

DIRETORIO_FIXTURES = RAIZ / "fixtures" / "duble"
AGORA_REFERENCIA = datetime(2026, 11, 17, 15, 0, tzinfo=UTC)  # só para o exemplo do arquivo; em uso, `valid_until` é agora + 2 h

FONTE = (
    "tests/corpus/personas.jsonl + personas_m.jsonl (corpus B8.1a); coeficientes da tabela FACTA 115716 da camada A do bancos-duble "
    "@1305152; C6 e 3RN inventados (so forma). Tudo sintetico."
)
PREFIXO_PESSOA_ID = "00000000-0000-7000-8000-"
PRIMEIRA_OFERTA_ID = 6_000_000
# Grade de coeficientes por prazo. FACTA: a da persona `aprovado-24..60` do dublê (operacoes-ok), tabela 115716 a 3,50% a.m.
COEFICIENTES = {
    "FACTA": {"tabela": "115716", "grade": {24: "0.0623", 36: "0.0493", 48: "0.0433", 60: "0.0400"}, "comissao": "0.012000"},
    "C6": {"tabela": "800077", "grade": {24: "0.0668", 36: "0.0526", 48: "0.0457", 60: "0.0412"}, "comissao": "0.010000"},
    "3RN": {"tabela": "FGL 102", "grade": {24: "0.0655", 36: "0.0511", 48: "0.0443", 60: "0.0401"}, "comissao": "0.008000"},
}
CODIGO_DO_PAR = {"FACTA": 1, "C6": 2, "3RN": 3}
# Quem tem par em OUTRO banco (H §7: P13 «cita C6 e há oferta ativa»; M caso (b): outro banco, sem oferta FACTA): (banco, valor_liberado em reais, prazo).
# «P14 cita o 3RN e não há» e «sem FACTA» (P-M18) são o par AUSENTE: no 360 real o par só nasce de oferta ativa ou de contrato (`pessoas_propostas`).
OUTROS_BANCOS: dict[str, tuple[str, int, int]] = {
    "P13": ("C6", 4800, 60),
    "P-M18": ("C6", 3000, 36),
}
# «Já tem proposta» (P59, persona `proposta-viva` do dublê): contrato vivo no par FACTA. A oferta ativa segue visível (a de uma consulta posterior): o contrato NÃO a
# consumiu (`consome_oferta_ativa: false`). Valores inventados; AF = 9000000 + n da persona do dublê (a que o `por-cpf` lista); status = o da etapa de assinatura.
CONTRATO_VIVO = {"P59": {"macro": "pendente", "status_nativo_codigo": "12", "status_nativo_texto": "12 - AGUARDANDO ASSINATURA DIGITAL"}}


def _centavos(valor: Decimal) -> str:
    return str(valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def economia(banco: str, valor_brl: int, prazo: int) -> dict[str, Any]:
    tab = COEFICIENTES[banco]
    coef = tab["grade"][prazo]
    valor = Decimal(valor_brl)
    return {
        "valor_liberado": _centavos(valor),
        "valor_parcela": _centavos(valor * Decimal(coef)),
        "prazo_meses": prazo,
        "tabela_identificador": tab["tabela"],
        "convenio": "CLT",
        "coeficiente_financeiro": coef,
        "coef_valor": tab["comissao"],
    }


def _numero(persona_id: str) -> int:
    """P01 → 1 … P60 → 60; P-M01 → 101 … P-M24 → 124."""
    return int(persona_id[-2:]) + (100 if persona_id.startswith("P-M") else 0)


def _par(banco: str, k: int, valor: int, prazo: int) -> dict[str, Any]:
    return {
        "banco": banco, "produto": "CLT", "oferta_id": str(PRIMEIRA_OFERTA_ID + 10 * k + CODIGO_DO_PAR[banco]),
        "economia": economia(banco, valor, prazo),
    }  # fmt: skip


def pessoa(p: Persona, duble_do_corpus: Any) -> dict[str, Any]:
    k = _numero(p.id)
    nn = int(p.cpf[8:11])  # 000.000.0nn-dd → nn
    pares = []
    perfil = p.perfil
    if perfil.oferta_facta_ativa and perfil.valor_pre_aprovado_brl is not None and perfil.prazo_oferta_x is not None:
        pares.append(_par("FACTA", k, perfil.valor_pre_aprovado_brl, perfil.prazo_oferta_x))
    if p.id in OUTROS_BANCOS:
        banco, valor, prazo = OUTROS_BANCOS[p.id]
        pares.append(_par(banco, k, valor, prazo))
    if p.id in CONTRATO_VIVO:
        facta = next(par for par in pares if par["banco"] == "FACTA")
        n_duble = next(d.n for d in duble_do_corpus.personas if d.id == p.cenario_facta.persona_duble)
        facta["contratos"] = [{
            "contrato_id": str(PRIMEIRA_OFERTA_ID + 10 * k + 5), "referencia_banco": str(9_000_000 + n_duble), "oferta_id": str(PRIMEIRA_OFERTA_ID + 10 * k + 9),
            **CONTRATO_VIVO[p.id],
        }]  # fmt: skip
    return {
        "persona_id": p.id,
        "pessoa_id": f"{PREFIXO_PESSOA_ID}{k:012d}",
        "cpf": p.cpf,
        "nome": p.nome,
        "telefone": f"55009000{nn:04d}",
        "duble": p.cenario_facta.persona_duble,
        "pares": pares,
    }


def construir(raiz_corpus: Path | None = None) -> dict[str, Any]:
    corpus = carregar(raiz_corpus or RAIZ / "tests" / "corpus")
    return {"versao": 1, "fonte": FONTE, "pessoas": [pessoa(p, corpus.duble) for p in corpus.todas()]}


def _json(dados: Any) -> str:
    return json.dumps(dados, ensure_ascii=False, indent=1) + "\n"


def _condicao(persona: str, banco: str, prazo: int, valor_brl: int, selecionada: int) -> dict[str, Any]:
    """Uma condição crua da C6 (`condicoes_credito[].condicao`): o valor pedido em cada prazo da grade, parcela = valor × coeficiente."""
    tab = COEFICIENTES[banco]
    coef = tab["grade"][prazo]
    return {
        "condicao": {
            "id_simulacao": f"SIM-TESTE-{persona}-{prazo}", "valor_cliente": float(valor_brl), "valor_parcela": float(_centavos(Decimal(valor_brl) * Decimal(coef))),
            "quantidade_parcelas": prazo, "convenio": {"codigo": tab["tabela"], "descricao": "Convenio sintetico de teste"},
            "coeficiente_tabela": float(tab["comissao"]),
        }
    }  # fmt: skip


def _c6_simulado(persona: str, valor_brl: int, prazo_oferta: int) -> dict[str, Any]:
    grade = [_condicao(persona, "C6", prazo, valor_brl, prazo_oferta) for prazo in COEFICIENTES["C6"]["grade"]]
    escolhida = next(c["condicao"] for c in grade if c["condicao"]["quantidade_parcelas"] == prazo_oferta)
    return {
        "http": 200,
        "corpo": {
            "success": True, "result": "simulado", "cpf": CPF_ECO, "fonte": "online", "custo": True, "status": "OK", "motivo": "Simulação concluída.",
            "simulacao": {"condicoes_credito": grade}, "condicoes_persistidas": True, "oferta": None,
            "opcao_selecionada": {
                "id_simulacao": escolhida["id_simulacao"], "convenio": escolhida["convenio"]["codigo"], "convenio_nome": escolhida["convenio"]["descricao"],
                "prazo": prazo_oferta, "valor_parcela": escolhida["valor_parcela"], "valor_liberado": escolhida["valor_cliente"], "proibida": False,
                "motivo": None, "coeficiente_tabela": escolhida["coeficiente_tabela"],
            },
        },
    }  # fmt: skip


def fixture_c6(catalogo: CatalogoPessoasTeste) -> dict[str, Any]:
    casos: dict[str, Any] = {
        "sem_oferta": {
            "http": 404,
            "corpo": {
                "success": True, "result": "sem_oferta", "cpf": CPF_ECO, "fonte": "online", "custo": True, "status": "REPROVADO",
                "motivo": "Sem oferta disponível.", "motivo_banco": "Reprovado Política Interna (texto sintético)", "simulacao": None,
                "condicoes_persistidas": False, "oferta": None,
            },
        }
    }  # fmt: skip
    por_persona: dict[str, str] = {}
    for p in catalogo.pessoas:
        for par in p.pares:
            if par.banco == "C6" and par.economia is not None:
                casos[f"simulado_{p.persona_id}"] = _c6_simulado(
                    p.persona_id, int(Decimal(par.economia.valor_liberado)), par.economia.prazo_meses
                )
                por_persona[p.persona_id] = f"simulado_{p.persona_id}"
    return {
        "versao": 1, "fonte": "forma de /c6/oferta/simular (c6-api app/routers/oferta.py, simular) e da condicao (sim_client.extrair_opcoes); valores sinteticos",
        "eco_cpf": "`cpf` ecoa o pedido: o arquivo traz 00000000000 e o gateway o troca pelo CPF consultado", "padrao": "sem_oferta", "por_persona": por_persona, "casos": casos,
    }  # fmt: skip


def fixture_3rn(catalogo: CatalogoPessoasTeste) -> dict[str, Any]:
    """`/3rn/calcular` no modo da IA (`nao_repagar: true`): TODA resposta ecoa o campo (`_ecoar_nao_repagar`). O padrão é `SIM_AUSENTE` (sem simulação
    guardada a consulta paga NÃO é refeita): só quem tem par 3RN com oferta ativa cai em `calculado`."""
    tab = COEFICIENTES["3RN"]
    valor, prazo = 3500, 48
    parcela = float(_centavos(Decimal(valor) * Decimal(tab["grade"][prazo])))
    prazos = sorted(tab["grade"])
    casos: dict[str, Any] = {
        "calculado": {
            "http": 200,
            "corpo": {
                "success": True, "cpf": CPF_ECO, "fonte_sim": "cache", "tabela": tab["tabela"], "valorFinanciado": float(valor), "valorLiquido": 3290.0,
                "parcela": parcela, "prazo": prazo, "coeficiente_tabela": float(tab["comissao"]), "nao_repagar": True,
            },
        },
        "sem_simulacao": {
            "http": 200,
            "corpo": {
                "success": False, "cpf": CPF_ECO, "etapa": "vinculos", "status": "SIM_AUSENTE",
                "motivo": "Sem simulação válida em trn.sim para este CPF — com nao_repagar, a consulta de vínculos (paga) não é refeita.",
                "nao_repagar": True,
            },
        },
        "prazo_indisponivel": {  # `validar_prazo_tabela`: o prazo pedido não existe na tabela (sem `etapa`, com a grade)
            "http": 200,
            "corpo": {
                "success": False, "cpf": CPF_ECO, "status": "REPROVADO", "tabela": tab["tabela"], "prazoMaximo": max(prazos), "prazosDisponiveis": prazos,
                "motivo": f'Prazo 72x indisponível para a tabela "{tab["tabela"]}". Prazos aceitos: {", ".join(f"{p}x" for p in prazos)}.',
                "nao_repagar": True,
            },
        },
    }  # fmt: skip
    por_persona = {
        p.persona_id: "calculado" for p in catalogo.pessoas for par in p.pares if par.banco == "3RN" and par.economia is not None
    }
    return {
        "versao": 2, "fonte": "forma de /3rn/calcular com nao_repagar (3rn-api app/routers/consulta.py, calcular/_calcular/_ecoar_nao_repagar); valores sinteticos",
        "eco_cpf": "`cpf` ecoa o pedido: o arquivo traz 00000000000 e o gateway o troca pelo CPF consultado", "padrao": "sem_simulacao", "por_persona": por_persona, "casos": casos,
    }  # fmt: skip


def fixture_cliente360(catalogo: CatalogoPessoasTeste) -> dict[str, Any]:
    fonte = FontePessoasTeste(catalogo, RelogioFalso(AGORA_REFERENCIA))
    exemplos = ("P01", "P13", "P14", "P-M18", "P59")  # só FACTA; FACTA + C6; sem par 3RN; sem par FACTA + C6; com contrato vivo
    casos = {
        pid: {
            "resumo": fonte.resumo(catalogo.por_persona(pid).pessoa_id, "duble"),
            "propostas": fonte.propostas(catalogo.por_persona(pid).pessoa_id, "duble"),
        }
        for pid in exemplos
    }  # type: ignore[union-attr]
    inexistente = "00000000-0000-7000-8000-999999999999"
    casos["desconhecida"] = {"resumo": fonte.resumo(inexistente, "duble"), "propostas": fonte.propostas(inexistente, "duble")}
    return {
        "versao": 1,
        "fonte": "forma de Oferta/ParPropostasPessoa/ResultadoPropostasPessoa/PessoaResumo/ResumosPessoas (cliente360.json); saida de FontePessoasTeste em agora_referencia",
        "relativo": {
            "valid_until_s": int(VALIDADE_PADRAO.total_seconds()),
            "regra": "valid_until = agora + 2 h, calculado ao servir; lido_em/criada_em/business_date também seguem o relógio. Os instantes abaixo valem só para agora_referencia",
        },
        "agora_referencia": AGORA_REFERENCIA.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "casos": casos,
    }  # fmt: skip


def textos(raiz_corpus: Path | None = None) -> dict[Path, str]:
    """Caminho → conteúdo de tudo que este script gera. Valida o catálogo pelo mesmo modelo que o runtime usa."""
    dados = construir(raiz_corpus)
    catalogo = CatalogoPessoasTeste.model_validate(dados)
    sha = f"{hash_canonico(catalogo.conteudo())}  pessoas_teste ({len(catalogo.pessoas)} pessoas; sha256 do JSON canonico da lista, catalogo.hash_canonico)\n"
    return {
        ARQUIVO: _json(dados), ARQUIVO_HASH: sha,
        DIRETORIO_FIXTURES / "cliente360_oferta.json": _json(fixture_cliente360(catalogo)),
        DIRETORIO_FIXTURES / "3rn_calcular.json": _json(fixture_3rn(catalogo)),
        DIRETORIO_FIXTURES / "c6_simular.json": _json(fixture_c6(catalogo)),
    }  # fmt: skip


def main(argv: list[str]) -> int:
    gerado = textos()
    if "--verificar" in argv:
        defasados = [c.relative_to(RAIZ) for c, t in gerado.items() if not c.exists() or c.read_text(encoding="utf-8") != t]
        for c in defasados:
            print(f"DESATUALIZADO: {c} (rode scripts/gerar_pessoas_teste.py)", file=sys.stderr)
        print(
            "pessoas_teste e fixtures/duble em dia"
            if not defasados
            else f"{len(defasados)} arquivo(s) desatualizado(s) em relacao ao corpus"
        )
        return 1 if defasados else 0
    DIRETORIO_FIXTURES.mkdir(parents=True, exist_ok=True)
    for caminho, texto in gerado.items():
        caminho.write_text(texto, encoding="utf-8")
    print(f"escritos {len(gerado)} arquivos ({', '.join(c.name for c in gerado)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
