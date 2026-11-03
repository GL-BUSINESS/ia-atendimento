"""`pessoas_teste` (B2.4): uma pessoa sintética por `persona_id` da F3, servida em `duble|teste` com `valid_until` relativo.

Sem banco. O catálogo (`src/ia_atendimento/pessoas_teste/pessoas.json`) é gerado do corpus por `scripts/gerar_pessoas_teste.py`; aqui se prova que
cobre as 84 personas, que T1/T3 saem na forma medida do 360, que `valid_until` anda com o relógio, que a marca «[TESTE]» é só do modo `teste`,
que fixture não responde em `real`/`sombra` e que nenhum dado de pessoa entrou.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from ia_atendimento import corpus
from ia_atendimento.pessoas_teste import (
    PREFIXO_TESTE,
    CatalogoPessoasTeste,
    FontePessoasTeste,
    ForaDoModoDeTeste,
    PessoasTesteInvalidas,
    carregar,
    carregar_catalogo,
    catalogo_padrao,
    formas,
    hash_canonico,
    marcar_teste,
    texto_de_saida,
)
from ia_atendimento.pessoas_teste import catalogo as modulo_catalogo
from ia_atendimento.pessoas_teste.formas import ResultadoPropostasPessoa, ResumosPessoas
from ia_atendimento.relogio import RelogioFalso
from tests.apoio_irmao import localizar

RAIZ = Path(__file__).resolve().parent.parent
AGORA = datetime(2026, 11, 17, 15, 0, tzinfo=UTC)
CPF_SINTETICO = re.compile(r"^000\.000\.[01]\d{2}-\d{2}$")  # 0nn: as personas do corpus; 1nn: os clones do dublê (R1-09)
TELEFONE_SINTETICO = re.compile(r"^55009000\d{4}$")


@pytest.fixture(scope="module")
def corpo() -> corpus.Corpus:
    return corpus.carregar(RAIZ / "tests" / "corpus")


@pytest.fixture(scope="module")
def catalogo() -> CatalogoPessoasTeste:
    return catalogo_padrao()


@pytest.fixture
def relogio() -> RelogioFalso:
    return RelogioFalso(AGORA)


@pytest.fixture
def fonte(catalogo: CatalogoPessoasTeste, relogio: RelogioFalso) -> FontePessoasTeste:
    return FontePessoasTeste(catalogo, relogio)


def _instante(texto: str) -> datetime:
    return datetime.strptime(texto, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


# --- cobertura: todas as personas da F3 ------------------------------------------------------------------------------------------------


def test_pessoas_teste_cobrem_todas_as_personas(catalogo, corpo):
    """Uma pessoa por `persona_id` (60 H + 24 P-M), com o CPF, o nome e o cenário do dublê do corpus; `pessoa_id` fixo e único."""
    personas = corpo.todas()
    assert len(personas) == 84
    assert [p.persona_id for p in catalogo.pessoas] == [p.id for p in personas]
    assert len(catalogo.pessoa_ids()) == 84, "pessoa_id repetido"
    for persona, pessoa in zip(personas, catalogo.pessoas, strict=True):
        assert (pessoa.cpf, pessoa.nome, pessoa.duble) == (persona.cpf, persona.nome, persona.cenario_facta.persona_duble), persona.id
        assert CPF_SINTETICO.match(pessoa.cpf) and TELEFONE_SINTETICO.match(pessoa.telefone), persona.id
        assert str(pessoa.pessoa_id).startswith("00000000-0000-7000-8000-"), "pessoa_id fora da faixa sintética"


def test_pessoas_teste_um_cpf_e_um_telefone_por_persona(catalogo):
    """R1-09: o estado do dublê (scenario do WireMock) e os stubs são por CPF; duas personas no mesmo CPF veriam a proposta uma da outra."""
    assert len({p.cpf for p in catalogo.pessoas}) == 84
    assert len({p.telefone for p in catalogo.pessoas}) == 84


def test_pessoas_teste_prazo_do_t3_e_o_do_cenario_aprovado_do_dublê(catalogo, corpo):
    """R1-09: a oferta que T3 mostra (36x, por exemplo) é a que o T5/T7 do dublê calcula; antes 23 das 41 personas `aprovado-N` divergiam."""
    base = {d.id: d.clone_de or d.id for d in corpo.duble.personas}
    conferidas = 0
    for pessoa in catalogo.pessoas:
        if pessoa.duble and (m := re.fullmatch(r"aprovado-(\d+)", base[pessoa.duble])):
            facta = next(par for par in pessoa.pares if par.banco == "FACTA")
            assert facta.economia.prazo_meses == int(m.group(1)), pessoa.persona_id
            conferidas += 1
    assert conferidas == 41


def test_pessoas_teste_oferta_facta_ativa_segue_o_perfil_da_persona(catalogo, corpo):
    """Oferta FACTA ativa ⇔ `perfil.oferta_facta_ativa`; valor e prazo são os do perfil; a parcela é valor × coeficiente da tabela 115716."""
    for persona in corpo.todas():
        facta = next((par for par in catalogo.por_persona(persona.id).pares if par.banco == "FACTA"), None)
        perfil = persona.perfil
        if not perfil.oferta_facta_ativa:
            assert facta is None, f"{persona.id}: sem oferta FACTA o par é AUSENTE (no 360 o par só nasce de oferta ativa ou contrato)"
            continue
        assert facta is not None and facta.economia is not None
        assert int(float(facta.economia.valor_liberado)) == perfil.valor_pre_aprovado_brl, persona.id
        assert facta.economia.prazo_meses == perfil.prazo_oferta_x, persona.id
        esperado = round(perfil.valor_pre_aprovado_brl * float(facta.economia.coeficiente_financeiro), 2)
        assert float(facta.economia.valor_parcela) == pytest.approx(esperado, abs=0.005), persona.id


@pytest.mark.parametrize("modo", ["duble", "teste"])
def test_pessoas_teste_todas_as_personas_leem_t1_e_t3(catalogo, fonte, modo):
    """O aceite da B2.4: as 84 personas leem T1 e T3 em `duble|teste`, e o que sai tem a forma do 360 (Pydantic estrito)."""
    for pessoa in catalogo.pessoas:
        resumo = ResumosPessoas.model_validate(fonte.resumo(pessoa.pessoa_id, modo))
        assert [i.pessoa_id for i in resumo.itens] == [str(pessoa.pessoa_id)]
        assert resumo.itens[0].cpf == pessoa.cpf_digitos
        propostas = ResultadoPropostasPessoa.model_validate(fonte.propostas(pessoa.pessoa_id, modo))
        assert propostas.encontrado and propostas.pessoa_id == str(pessoa.pessoa_id)
        assert [p.banco for p in propostas.pares] == sorted(par.banco for par in pessoa.pares), pessoa.persona_id  # a ordem do 360 real
        com_oferta = [par for par in pessoa.pares if par.economia is not None]
        assert [p.banco for p in propostas.pares if p.oferta_ativa] == sorted(par.banco for par in com_oferta), pessoa.persona_id
        assert {p.caso for p in propostas.pares} <= {"so_oferta", "com_contrato"}
        assert propostas.atribuicao.versao == 0 and propostas.atribuicao.site_profile_id is None, "pessoa sem atribuição: versao 0 (R1-03)"


def test_pessoas_teste_pares_saem_ordenados_por_banco_e_produto_como_no_360_real(catalogo, fonte):
    """R2-01: `pessoas_propostas` faz `for (banco, produto), grupo in sorted(pares.items())`. P13, a única com dois pares, sai `[C6, FACTA]` (a ordem do catálogo é a inversa)."""
    pessoa = catalogo.por_persona("P13")
    assert [par.banco for par in pessoa.pares] == ["FACTA", "C6"], (
        "a ordem do catálogo não é a do 360 (o catálogo não muda, o hash também não)"
    )
    pares = fonte.propostas(pessoa.pessoa_id, "duble")["pares"]
    assert [(p["banco"], p["produto"]) for p in pares] == [("C6", "CLT"), ("FACTA", "CLT")]
    for p in catalogo.pessoas:
        servidos = [(x["banco"], x["produto"]) for x in fonte.propostas(p.pessoa_id, "teste")["pares"]]
        assert servidos == sorted(servidos), p.persona_id


def test_pessoas_teste_p13_tem_oferta_no_c6_e_p14_nao_tem_par_no_3rn(catalogo, fonte):
    """«Sem oferta no 3RN» (P14) é o par AUSENTE, como no 360 real: o par só nasce de oferta ativa ou de contrato (R1-04)."""
    p13 = {p["banco"]: p for p in fonte.propostas(catalogo.por_persona("P13").pessoa_id, "duble")["pares"]}
    assert p13["FACTA"]["caso"] == "so_oferta" and p13["C6"]["caso"] == "so_oferta" and p13["C6"]["oferta_ativa"]["estado"] == "ativa"
    p14 = {p["banco"] for p in fonte.propostas(catalogo.por_persona("P14").pessoa_id, "duble")["pares"]}
    assert p14 == {"FACTA"}, "P14 não tem par 3RN"
    pm18 = {p["banco"] for p in fonte.propostas(catalogo.por_persona("P-M18").pessoa_id, "duble")["pares"]}
    assert pm18 == {"C6"}, "P-M18 não tem par FACTA"


def test_pessoas_teste_p59_ja_tem_proposta_e_o_par_vem_com_contrato(catalogo, fonte):
    """«Proposta viva» (P59): contrato vivo no par FACTA, `com_contrato`, alvo = o contrato, e a oferta ativa segue visível sem ser consumida por ele."""
    (par,) = fonte.propostas(catalogo.por_persona("P59").pessoa_id, "teste")["pares"]
    assert par["caso"] == "com_contrato" and par["oferta_ativa"]["estado"] == "ativa"
    (foto,) = par["contratos"]
    assert (foto["terminal"], foto["consome_oferta_ativa"], foto["contrato"]["macro"]) == (False, False, "pendente")
    assert par["alvo_sugerido"] == {"tipo": "contrato", "id": foto["contrato"]["contrato_id"]}
    assert (
        foto["contrato"]["oferta_id"] != par["oferta_ativa"]["oferta_id"]
        and foto["contrato"]["pessoa_id"] == par["oferta_ativa"]["pessoa_id"]
    )


def test_pessoas_teste_pessoa_desconhecida_responde_como_o_360(fonte):
    """«Não encontrado» do T3 (`pessoasPropostas`): 200 com `pessoa_id: null` e `atribuicao: null` SEMPRE presentes; T1 omite o id desconhecido."""
    fora = "00000000-0000-7000-8000-999999999999"
    assert fonte.resumo(fora, "duble") == {"itens": []}
    vazio = fonte.propostas(fora, "teste")
    assert vazio == {
        "encontrado": False,
        "pessoa_id": None,
        "atribuicao": None,
        "varias_ofertas": False,
        "pares": [],
        "lido_em": vazio["lido_em"],
    }
    assert fonte.resumo("nao-e-uuid", "duble") == {"itens": []}
    assert fonte.cpf_de(fora, "duble") is None


def test_pessoas_teste_t1_tem_so_as_chaves_da_projecao_real(catalogo, fonte):
    """`pessoas:resumos` com as flags do T1: `{pessoa_id, nome, cpf_mascarado, cpf, vendedor, nao_perturbe, limite_contratos}`; `status_atendimento` NÃO existe."""
    (item,) = fonte.resumo(catalogo.por_persona("P01").pessoa_id, "duble")["itens"]
    assert set(item) == {"pessoa_id", "nome", "cpf_mascarado", "cpf", "vendedor", "nao_perturbe", "limite_contratos"}
    assert item["vendedor"] is None and item["nao_perturbe"] is None and item["limite_contratos"] is None


def test_pessoas_teste_oferta_nao_inventa_ultima_consulta_em_e_traz_link_chat_nulo(catalogo, fonte):
    """R2-04: `pessoas:propostas` não emite `ultima_consulta_em` (só `propostas:periodo`) e SEMPRE emite as três chaves de `atributos_cadastrais`."""
    for pessoa in catalogo.pessoas:
        for par in fonte.propostas(pessoa.pessoa_id, "duble")["pares"]:
            oferta = par["oferta_ativa"]
            if oferta is not None:
                assert "ultima_consulta_em" not in oferta, pessoa.persona_id
                assert oferta["atributos_cadastrais"] == {"nome": pessoa.nome, "telefone": pessoa.telefone, "link_chat": None}, (
                    pessoa.persona_id
                )


def test_pessoas_teste_contrato_do_p59_traz_as_31_chaves_que_a_projecao_real_sempre_emite(catalogo, fonte):
    """R2-05: `projetar_contrato` emite 31 chaves SEMPRE (as 10 obrigatórias + 21 que valem `null`, `[]` ou `false`); código que lê `contrato["flags"]` não pode dar KeyError no dublê."""
    (par,) = fonte.propostas(catalogo.por_persona("P59").pessoa_id, "teste")["pares"]
    contrato = par["contratos"][0]["contrato"]
    assert set(contrato) == formas.SEMPRE_NO_CONTRATO and len(contrato) == 31
    assert (contrato["flags"], contrato["adicional"], contrato["valor_pago"], contrato["link_formalizacao"], contrato["fundida_em_id"]) == (
        [],
        False,
        None,
        None,
        None,
    )


def test_pessoas_teste_oferta_traz_as_chaves_nulas_que_a_projecao_real_sempre_emite(catalogo, fonte):
    oferta = fonte.propostas(catalogo.por_persona("P01").pessoa_id, "duble")["pares"][0]["oferta_ativa"]
    for chave in (
        "business_date_origem",
        "superseded_causa",
        "motivo_encerramento",
        "motivo_encerramento_texto",
        "competencia_inicio",
        "competencia_fim",
        "origem",
        "lead_id",
    ):
        assert chave in oferta, chave
    assert oferta["business_date_origem"] == "medida" and oferta["lead_id"] is None and oferta["origem"] is None


# --- valid_until relativo -------------------------------------------------------------------------------------------------------------


def test_valid_until_relativo(catalogo, fonte, relogio):
    """`valid_until` = agora + 2 h, calculado a CADA leitura: o relógio anda, a oferta anda junto (nunca fica velha no arquivo)."""
    pessoa = catalogo.por_persona("P01").pessoa_id
    for avanco_h in (0, 1, 5, 30):
        relogio.definir(AGORA + timedelta(hours=avanco_h))
        agora = relogio.agora()
        corpo_t3 = fonte.propostas(pessoa, "duble")
        oferta = corpo_t3["pares"][0]["oferta_ativa"]
        assert _instante(oferta["valid_until"]) == agora + timedelta(hours=2)
        assert _instante(corpo_t3["lido_em"]) == agora and _instante(oferta["criada_em"]) < agora < _instante(oferta["valid_until"])
    # a data de negócio é a de São Paulo, não a de UTC (01:30 UTC de 18/11 ainda é 17/11 no Brasil)
    relogio.definir(datetime(2026, 11, 18, 1, 30, tzinfo=UTC))
    assert fonte.propostas(pessoa, "duble")["pares"][0]["oferta_ativa"]["business_date"] == "2026-11-17"
    # e é o dia em que a oferta NASCEU (criada_em = agora - 15 min): 00:10 em São Paulo (03:10 UTC) a oferta nasceu 23:55 do dia anterior
    relogio.definir(datetime(2026, 11, 18, 3, 10, tzinfo=UTC))
    assert fonte.propostas(pessoa, "duble")["pares"][0]["oferta_ativa"]["business_date"] == "2026-11-17"


def test_valid_until_relativo_padrao_e_substituivel_pelo_harness(catalogo, relogio):
    """A validade é de 2 h por padrão; o harness da F3 (P51/P52, «a oferta vence») pode encurtá-la, e a versão pode mudar entre o SIM e o T7."""
    pessoa = catalogo.por_persona("P51").pessoa_id
    assert (
        FontePessoasTeste(catalogo, relogio).propostas(pessoa, "duble")["pares"][0]["oferta_ativa"]["valid_until"] == "2026-11-17T17:00:00Z"
    )
    curta = FontePessoasTeste(catalogo, relogio, validade=timedelta(minutes=5)).propostas(pessoa, "duble")
    assert curta["pares"][0]["oferta_ativa"]["valid_until"] == "2026-11-17T15:05:00Z"
    v2 = FontePessoasTeste(catalogo, relogio).propostas(pessoa, "teste", validade=timedelta(seconds=1), versao=2)["pares"][0][
        "oferta_ativa"
    ]
    assert (v2["valid_until"], v2["versao"]) == ("2026-11-17T15:00:01Z", 2)
    with pytest.raises(ValueError, match="positiva"):
        FontePessoasTeste(catalogo, relogio, validade=timedelta(0))


def test_pessoas_teste_nao_serve_em_real_nem_em_sombra(catalogo, fonte):
    """Fixture nunca responde por cliente de verdade: `real` e `sombra` leem o 360 (sombra só leitura), não o catálogo."""
    pessoa = catalogo.por_persona("P01").pessoa_id
    for modo in ("real", "sombra", "", "qualquer"):
        for chamada in (fonte.resumo, fonte.propostas, fonte.cpf_de):
            with pytest.raises(ForaDoModoDeTeste):
                chamada(pessoa, modo)


# --- «[TESTE]» -----------------------------------------------------------------------------------------------------------------------


def test_mensagem_de_teste_prefixada_TESTE():
    """Só o `modo_efetivo = teste` envia a um chat da TI, e a mensagem leva «[TESTE]» (08 §6); os outros modos não mexem no texto."""
    assert PREFIXO_TESTE == "[TESTE]"
    assert texto_de_saida("teste", "Oi, tudo bem?") == "[TESTE] Oi, tudo bem?"
    for modo in ("real", "duble", "sombra"):
        assert texto_de_saida(modo, "Oi, tudo bem?") == "Oi, tudo bem?", modo
    assert marcar_teste(marcar_teste("Oi")) == "[TESTE] Oi", "idempotente: nunca dois prefixos"
    assert texto_de_saida("teste", "[TESTE] Oi") == "[TESTE] Oi"
    assert texto_de_saida("teste", "") == "[TESTE] "
    assert texto_de_saida("teste", "meio [TESTE] do texto") == "[TESTE] meio [TESTE] do texto"


# --- sem dado de pessoa ---------------------------------------------------------------------------------------------------------------


def _strings(objeto: Any):
    if isinstance(objeto, str):
        yield objeto
    elif isinstance(objeto, dict):
        for v in objeto.values():
            yield from _strings(v)
    elif isinstance(objeto, list):
        for v in objeto:
            yield from _strings(v)


def test_pessoas_teste_e_fixtures_sem_dado_de_pessoa(catalogo, fonte):
    """Todo CPF é `000.000.0nn`, todo telefone `5500 9000-00nn`, nenhum e-mail, nenhum UUID fora da faixa sintética, nomes só de inventados."""
    textos = list(_strings(json.loads((RAIZ / "src/ia_atendimento/pessoas_teste/pessoas.json").read_text(encoding="utf-8"))))
    for nome in ("cliente360_oferta.json", "3rn_calcular.json", "c6_simular.json"):
        textos += list(_strings(json.loads((RAIZ / "fixtures" / "duble" / nome).read_text(encoding="utf-8"))))
    textos += list(_strings(fonte.propostas(catalogo.por_persona("P13").pessoa_id, "duble")))
    for texto in textos:
        assert not re.search(r"[^\s@]+@[^\s@]+\.[a-z]{2,}", texto), "e-mail"
        for cpf in re.findall(r"\d{3}\.\d{3}\.\d{3}-\d{2}", texto):
            assert CPF_SINTETICO.match(cpf), cpf
        for onze in re.findall(r"(?<!\d)\d{11}(?!\d)", texto):
            assert re.match(r"000000[01]", onze), onze
        for tel in re.findall(r"(?<!\d)55\d{10,11}(?!\d)", texto):
            assert TELEFONE_SINTETICO.match(tel), tel
        for uid in re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", texto):
            assert uid.startswith("00000000-"), uid
    sobrenomes = corpus.SOBRENOMES_FICTICIOS
    assert all(p.nome.split()[-1] in sobrenomes for p in catalogo.pessoas)


# --- catálogo, hash e gerador ---------------------------------------------------------------------------------------------------------


def test_pessoas_teste_hash_gravado_confere(catalogo):
    """`pessoas.sha256` é o hash que o `bancos-duble` guarda no instantâneo dele; mexer no catálogo sem regravar reprova. O hash vale para o
    ARQUIVO (o que o duble lê) e para o modelo: o `pessoas.json` é a forma normalizada, sem chave que o modelo preencheria por padrão."""
    bruto = json.loads((RAIZ / "src/ia_atendimento/pessoas_teste/pessoas.json").read_text(encoding="utf-8"))["pessoas"]
    assert bruto == catalogo.conteudo()
    assert hash_canonico(bruto) == hash_canonico(catalogo.conteudo()) == modulo_catalogo.ler_hash_gravado()
    mudado = [dict(p) for p in catalogo.conteudo()]
    mudado[0]["nome"] = "Outro Nome"
    assert hash_canonico(mudado) != modulo_catalogo.ler_hash_gravado()


def test_pessoas_teste_gerador_esta_em_dia():
    """O que está versionado (catálogo, hash e as 3 fixtures) é exatamente o que `scripts/gerar_pessoas_teste.py` produz do corpus."""
    spec = importlib.util.spec_from_file_location("gerar_pessoas_teste", RAIZ / "scripts" / "gerar_pessoas_teste.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    for caminho, texto in modulo.textos().items():
        assert caminho.read_text(encoding="utf-8") == texto, (
            f"{caminho.relative_to(RAIZ)} desatualizado: rode scripts/gerar_pessoas_teste.py"
        )


def test_pessoas_teste_catalogo_recusa_arquivo_ruim(tmp_path, catalogo):
    base = json.loads((RAIZ / "src/ia_atendimento/pessoas_teste/pessoas.json").read_text(encoding="utf-8"))

    def com(mutar) -> Path:
        copia = json.loads(json.dumps(base))
        mutar(copia)
        arquivo = tmp_path / "pessoas.json"
        arquivo.write_text(json.dumps(copia), encoding="utf-8")
        return arquivo

    assert len(carregar_catalogo(com(lambda d: None)).pessoas) == 84
    ruins = {
        "cpf de cliente": lambda d: d["pessoas"][0].update(cpf="529.982." + "247-25"),
        "dv errado": lambda d: d["pessoas"][0].update(cpf="000.000.001-92"),
        "pessoa_id fora da faixa": lambda d: d["pessoas"][0].update(pessoa_id="11111111-1111-7111-8111-111111111111"),
        "pessoa_id repetido": lambda d: d["pessoas"][1].update(pessoa_id=d["pessoas"][0]["pessoa_id"]),
        "persona_id repetido": lambda d: d["pessoas"][1].update(persona_id="P01"),
        "persona fora da F3": lambda d: d["pessoas"][0].update(persona_id="P61"),
        "campo a mais": lambda d: d["pessoas"][0].update(email="x@y.test"),
        "oferta sem economia": lambda d: d["pessoas"][0]["pares"][0].update(economia=None),
        "par repetido": lambda d: d["pessoas"][0]["pares"].append(dict(d["pessoas"][0]["pares"][0], oferta_id="1")),
        "telefone real": lambda d: d["pessoas"][0].update(telefone="11"),
        "telefone fora da faixa 5500 9000": lambda d: d["pessoas"][0].update(telefone="5511912345678"),
    }
    for rotulo, mutar in ruins.items():
        with pytest.raises(PessoasTesteInvalidas):
            carregar_catalogo(com(mutar))
        assert rotulo
    with pytest.raises(PessoasTesteInvalidas):
        carregar_catalogo(tmp_path / "nao-existe.json")


# --- a ligação com a API: PessoasTeste a partir do catálogo -------------------------------------------------------------------------


def test_pessoas_teste_do_catalogo_viram_o_pessoas_teste_da_api(catalogo):
    chat = "a1b2c3d4e5f60718293a4b5c"
    fixas = catalogo.como_pessoas_teste({chat: "P13"})
    p13 = catalogo.por_persona("P13").pessoa_id
    assert fixas.contem(p13) and len(fixas.pessoas) == 84 and fixas.pessoa_do_chat(chat) == p13
    assert not fixas.contem(UUID("11111111-1111-7111-8111-111111111111"))
    assert fixas.pessoa_do_chat("bbbbbbbbbbbbbbbbbbbbbbbb") is None
    for ruim in ({chat: "P99"}, {"CHAT-MAIUSCULO": "P01"}, {"abc": "P01"}):
        with pytest.raises(PessoasTesteInvalidas):
            catalogo.como_pessoas_teste(ruim)


def _cli(*argumentos: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ia_atendimento.pessoas_teste", *argumentos], capture_output=True, text=True, cwd=cwd, check=False
    )


def test_pessoas_teste_cli_monta_o_arquivo_da_api_e_nao_vaza_cpf(tmp_path):
    chat = "a1b2c3d4e5f60718293a4b5c"
    saida = tmp_path / "pessoas_teste.json"
    ok = _cli("arquivo", "--par", f"{chat}=P01", "--saida", str(saida), cwd=tmp_path)
    assert ok.returncode == 0, ok.stderr
    assert saida.stat().st_mode & 0o777 == 0o600
    pessoas = carregar(saida)  # o mesmo carregador que o orquestrador usa no boot
    assert len(pessoas.pessoas) == 84 and pessoas.pessoa_do_chat(chat) == UUID("00000000-0000-7000-8000-000000000001")
    listar = _cli("listar", cwd=tmp_path)
    assert listar.returncode == 0 and "P01\t00000000-0000-7000-8000-000000000001" in listar.stdout
    assert "000.000" not in listar.stdout and "Zuleide" not in listar.stdout, "listar não mostra CPF nem nome"
    for pares in (["--par", "sem-igual"], ["--par", f"{chat}=P01", "--par", f"{chat}=P02"], ["--par", f"{chat}=P99"]):
        assert _cli("arquivo", *pares, cwd=tmp_path).returncode == 2, pares


# --- consistência com o bancos-duble (BANCOS_DUBLE_PATH; o check.sh a EXIGE, sem ela o pytest solto pula) ------------------------------------


def test_pessoas_teste_o_hash_e_o_mesmo_do_instantaneo_do_bancos_duble(catalogo):
    """O `bancos-duble` guarda `personas/pessoas_teste.yaml` (o instantâneo em YAML) e o MESMO `.sha256`; o teste dele confere o YAML contra o hash."""
    duble = localizar("BANCOS_DUBLE_PATH", "personas/pessoas_teste.sha256", "bancos-duble")
    do_duble = (duble / "personas" / "pessoas_teste.sha256").read_text(encoding="utf-8")
    assert do_duble == modulo_catalogo.ARQUIVO_HASH.read_text(encoding="utf-8"), (
        "regrave lá: scripts/atualizar_pessoas_teste.py <pessoas.json>"
    )
    assert do_duble.split()[0] == hash_canonico(catalogo.conteudo())
    assert (duble / "personas" / "pessoas_teste.yaml").is_file()
