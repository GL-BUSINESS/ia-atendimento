"""Kit `kits/chats-teste.sh` (B2.4, R1-08), contra uma API falsa em processo (http.server): o fluxo de controle, o corpo do PUT e o que fica em disco.

A API falsa guarda a lista como o `PUT /config/chats_teste` guardaria (versão + valor) e recusa o que a real recusaria (token, 422, 409). Nada de rede
externa: tudo em 127.0.0.1. O que o ensaio NÃO prova (autorização real, LoginOuEmail) está em `test_pessoas_teste_api.py`.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
KIT = RAIZ / "kits" / "chats-teste.sh"
TOKEN = "token-ti-descartavel-0123456789abcdef-kit"
A, B, C = "a" * 24, "b" * 24, "c" * 24
POR = "operador.teste@glcapital.invalid"


class ApiFalsa:
    def __init__(self) -> None:
        self.versao, self.valor, self.pedidos, self.recusar = 3, [A], [], None
        self.arquivo: set[str] | None = None  # chats do `PESSOAS_TESTE_ARQUIVO` lido no boot; None = não valida (como o ensaio anterior)
        api = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silêncio
                pass

            def _json(self, cod: int, corpo: dict) -> None:
                b = json.dumps(corpo).encode()
                self.send_response(cod)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def _ok(self) -> bool:
                if self.headers.get("x-ia-token") != TOKEN:
                    self._json(401, {"erro": {"codigo": "token_invalido"}})
                    return False
                return True

            def do_GET(self):
                api.pedidos.append(("GET", None))
                if self._ok():
                    self._json(200, {"nome": "chats_teste", "versao": api.versao, "valor": api.valor})

            def do_PUT(self):
                corpo = json.loads(self.rfile.read(int(self.headers["content-length"])))
                api.pedidos.append(("PUT", corpo))
                if not self._ok():
                    return
                if api.recusar:
                    return self._json(*api.recusar)
                if (
                    api.arquivo is not None and not set(corpo["valor"]) <= api.arquivo
                ):  # a API real valida a lista INTEIRA contra o arquivo do boot
                    return self._json(422, {"erro": {"codigo": "pessoa_fora_de_pessoas_teste"}})
                if corpo["versao_esperada"] != api.versao:
                    return self._json(409, {"erro": {"codigo": "config_corrida"}})
                api.versao, api.valor = api.versao + 1, corpo["valor"]
                self._json(200, {"nome": "chats_teste", "versao": api.versao, "valor": api.valor})

        self.servidor = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.servidor.server_port}"
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()

    def reiniciar_com(self, arquivo: Path) -> None:
        """«Entregar o arquivo à VPS e reiniciar o orquestrador»: a API passa a validar contra os chats DESTE arquivo."""
        self.arquivo = set(json.loads(arquivo.read_text())["chats"])

    def puts(self) -> list[dict]:
        return [c for m, c in self.pedidos if m == "PUT"]


@pytest.fixture
def api():
    a = ApiFalsa()
    yield a
    a.servidor.shutdown()


@pytest.fixture
def ambiente(tmp_path: Path, api: ApiFalsa) -> dict[str, str]:
    token = tmp_path / "token_ti"
    token.write_text(TOKEN + "\n")
    token.chmod(0o600)
    return {
        "PATH": os.environ["PATH"], "HOME": str(tmp_path), "IA_API_URL": api.url, "IA_TOKEN_TI_ARQUIVO": str(token),
        "CHATS_TESTE_ESTADO": str(tmp_path / "estado"), "IA_PY": sys.executable, "IA_REPO": str(RAIZ), "PYTHONPATH": str(RAIZ / "src"),
        "SAIDA_ARQUIVO": str(tmp_path / "pessoas_teste.json"),
    }  # fmt: skip


def anterior(tmp_path: Path, api: ApiFalsa, versao: int, sufixo: str = "") -> Path:
    """O arquivo da lista guardada: `anterior-<8 primeiros do sha256 da URL>-<versão>.json` (a lista é DESTA API, R2-12)."""
    return tmp_path / "estado" / f"anterior-{hashlib.sha256(api.url.encode()).hexdigest()[:8]}-{versao}.json{sufixo}"


def kit(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(KIT), *args], capture_output=True, text=True, env=env, check=False)


def _aplicar(env, *pares, extra=()):
    return kit(env, "aplicar", *[x for p in pares for x in ("--par", p)], "--motivo", "ensaio_b", "--por", POR, *extra, "--confirmo")


def test_sem_flag_nao_faz_nada_e_ensaio_nao_abre_conexao(ambiente, api):
    assert kit(ambiente, "aplicar", "--par", f"{B}=P01", "--motivo", "m1", "--por", POR).returncode == 2
    for cmd in (["aplicar", "--par", f"{B}=P01"], ["limpar"], ["limpar", "--vazio"]):
        r = kit(ambiente, *cmd, "--motivo", "m1", "--por", POR, "--ensaio")
        assert r.returncode == 0 and "nenhuma conexão aberta" in r.stdout, cmd
    assert api.pedidos == []
    assert kit(ambiente, "aplicar", "--par", f"{B}=P01", "--motivo", "m1", "--por", POR, "--ensaio", "--confirmo").returncode == 1


def test_aplicar_acrescenta_a_lista_vigente_e_guarda_a_anterior(ambiente, api, tmp_path):
    r = _aplicar(ambiente, f"{B}=P01", f"{C}=P-M01")
    assert r.returncode == 0, r.stderr
    (put,) = api.puts()
    assert put["valor"] == [A, B, C], "MERGE: a lista vigente [A] + os dois chats novos, sem tirar o que a TI já tinha"
    assert put == {"valor": [A, B, C], "por": POR, "motivo": "ensaio_b", "versao_esperada": 3}
    assert (api.versao, api.valor) == (4, [A, B, C])
    guardada = json.loads(anterior(tmp_path, api, 3).read_text())
    assert guardada["valor"] == [A] and guardada["versao_antes"] == 3 and guardada["motivo"] == "ensaio_b"
    assert guardada["url"] == api.url and guardada["valor_depois"] == [A, B, C], "guarda a URL e a lista que o aplicar gravou (R2-12)"
    assert (tmp_path / "estado").stat().st_mode & 0o777 == 0o700 and (anterior(tmp_path, api, 3)).stat().st_mode & 0o777 == 0o600
    assert f"{A}" in r.stdout and "versão vigente = 3" in r.stdout


def test_aplicar_nao_repete_chat_ja_na_lista_e_substituir_troca_tudo_e_limpar_desempilha(ambiente, api, tmp_path):
    assert _aplicar(ambiente, f"{A}=P01", f"{B}=P02").returncode == 0
    assert api.valor == [A, B], "A já estava na lista: não duplica"
    r = _aplicar(ambiente, f"{C}=P03", extra=["--substituir"])
    assert r.returncode == 0 and api.valor == [C], "--substituir: a lista passa a ser SÓ o novo chat"
    assert sorted(p.name for p in (tmp_path / "estado").glob("anterior-*.json")) == sorted(
        [anterior(tmp_path, api, 3).name, anterior(tmp_path, api, 4).name]
    )
    assert kit(ambiente, "limpar", "--motivo", "m1", "--por", POR, "--confirmo").returncode == 0 and api.valor == [A, B], (
        "desfaz o ÚLTIMO aplicar"
    )
    assert kit(ambiente, "limpar", "--motivo", "m1", "--por", POR, "--confirmo").returncode == 0 and api.valor == [A], "e o anterior a ele"


def test_aplicar_recusa_quando_ja_existe_lista_guardada_da_mesma_versao(ambiente, api, tmp_path):
    (tmp_path / "estado").mkdir(mode=0o700)
    anterior(tmp_path, api, 3).write_text(json.dumps({"versao_antes": 3, "valor": [], "por": POR, "motivo": "velho"}))
    r = _aplicar(ambiente, f"{B}=P01")
    assert r.returncode == 1 and "já existe" in r.stderr and api.puts() == [], (
        "não sobrescreve a lista que alguém ainda pode precisar restaurar"
    )


def test_limpar_restaura_a_lista_que_o_aplicar_guardou(ambiente, api, tmp_path):
    assert _aplicar(ambiente, f"{B}=P01").returncode == 0 and api.valor == [A, B]
    r = kit(ambiente, "limpar", "--motivo", "fim_do_ensaio", "--por", POR, "--confirmo")
    assert r.returncode == 0, r.stderr
    assert api.valor == [A], "limpar RESTAURA a lista anterior ([A]), não zera"
    assert api.puts()[-1] == {"valor": [A], "por": POR, "motivo": "fim_do_ensaio", "versao_esperada": 4}
    assert anterior(tmp_path, api, 3, ".restaurado").is_file() and not anterior(tmp_path, api, 3).exists()
    sem = kit(ambiente, "limpar", "--motivo", "fim", "--por", POR, "--confirmo")
    assert sem.returncode == 1 and "não há lista anterior" in sem.stderr and "--vazio" in sem.stderr
    vazio = kit(ambiente, "limpar", "--vazio", "--motivo", "fim", "--por", POR, "--confirmo")
    assert vazio.returncode == 0 and api.valor == []


def test_substituir_vale_so_com_o_ultimo_aplicar_restaurado(ambiente, api):
    assert _aplicar(ambiente, f"{B}=P01").returncode == 0
    assert kit(ambiente, "limpar", "--motivo", "m1", "--por", POR, "--confirmo").returncode == 0
    r = _aplicar(ambiente, f"{C}=P03", extra=["--substituir"])
    assert r.returncode == 0 and api.valor == [C] and api.puts()[-1]["valor"] == [C]


def test_recusa_da_api_nao_deixa_lista_guardada_e_diz_o_codigo(ambiente, api, tmp_path):
    api.recusar = (422, {"erro": {"codigo": "pessoa_fora_de_pessoas_teste"}})
    r = _aplicar(ambiente, f"{B}=P01")
    assert r.returncode == 1 and "pessoa_fora_de_pessoas_teste" in r.stderr and "nada foi gravado" in r.stderr
    assert not list((tmp_path / "estado").glob("anterior-*")), "PUT recusado não deixa a lista anterior (nem .tmp) para trás"
    api.recusar = None
    api.versao = 9  # alguém gravou entre o GET e o PUT não acontece aqui; simula a corrida com versao_esperada velha
    api.pedidos.clear()
    assert _aplicar(ambiente, f"{B}=P01").returncode == 0


def test_motivo_e_obrigatorio_sem_padrao_e_o_motivo_vai_ao_registro(ambiente, api):
    r = kit(ambiente, "aplicar", "--par", f"{B}=P01", "--por", POR, "--confirmo")
    assert r.returncode == 1 and "--motivo" in r.stderr and "obrigatório" in r.stderr and api.pedidos == []
    for ruim in ("Ensaio B", "ensaio-b", "x" * 41, ""):
        assert kit(ambiente, "aplicar", "--par", f"{B}=P01", "--por", POR, "--motivo", ruim, "--confirmo").returncode == 1
    assert api.pedidos == []
    ambiente["IA_MOTIVO"] = "via_env"
    assert kit(ambiente, "aplicar", "--par", f"{B}=P01", "--por", POR, "--confirmo").returncode == 0
    assert api.puts()[0]["motivo"] == "via_env"


def test_token_so_0600_sem_link_e_nunca_impresso(ambiente, api, tmp_path):
    r = _aplicar(ambiente, f"{B}=P01")
    assert TOKEN not in r.stdout + r.stderr
    Path(ambiente["IA_TOKEN_TI_ARQUIVO"]).chmod(0o644)
    assert _aplicar(ambiente, f"{C}=P01").returncode == 1
    Path(ambiente["IA_TOKEN_TI_ARQUIVO"]).chmod(0o600)
    elo = tmp_path / "elo"
    elo.symlink_to(ambiente["IA_TOKEN_TI_ARQUIVO"])
    r2 = _aplicar({**ambiente, "IA_TOKEN_TI_ARQUIVO": str(elo)}, f"{C}=P01")
    assert r2.returncode == 1 and "link simbólico" in r2.stderr
    r3 = _aplicar({**ambiente, "CHATS_TESTE_ESTADO": str(tmp_path / "e2")}, f"{C}=P01")
    assert TOKEN not in r3.stdout + r3.stderr


def test_so_fala_com_a_wireguard_ou_loopback_a_menos_que_o_operador_diga(ambiente, api):
    r = _aplicar({**ambiente, "IA_API_URL": "http://203.0.113.9:8000"}, f"{B}=P01")
    assert r.returncode == 1 and "fora da WireGuard" in r.stderr
    r2 = kit({**ambiente, "IA_API_URL": "http://10.90.0.5:8000"}, "limpar", "--vazio", "--motivo", "m1", "--por", POR, "--ensaio")
    assert r2.returncode == 0, "10.90.0.5 (a WireGuard) passa pela validação"


def test_entradas_ruins_sao_recusadas_antes_de_abrir_conexao(ambiente, api):
    ruins = [
        ["--par", f"{B.upper()}=P01"], ["--par", f"{B}=P61"], ["--par", B], ["--par", f"{B}=P01", "--par", f"{B}=P02"],
        [x for i in range(21) for x in ("--par", f"{i:024x}=P01")],  # 21 chats: a 0003 recusa mais de 20
    ]  # fmt: skip
    for pares in ruins:
        assert kit(ambiente, "aplicar", *pares, "--motivo", "m1", "--por", POR, "--confirmo").returncode == 1, pares
    assert kit(ambiente, "aplicar", "--par", f"{B}=P01", "--motivo", "m1", "--por", "00000001234", "--confirmo").returncode == 1
    assert kit(ambiente, "gerar", "--substituir", "--par", f"{B}=P01", "--confirmo").returncode == 1
    assert api.pedidos == []


def test_gerar_escreve_o_arquivo_da_api_com_as_84_pessoas_em_0600(ambiente, tmp_path):
    r = kit(ambiente, "gerar", "--par", f"{B}=P13", "--confirmo")
    assert r.returncode == 0, r.stderr
    saida = Path(ambiente["SAIDA_ARQUIVO"])
    assert saida.stat().st_mode & 0o777 == 0o600
    dados = json.loads(saida.read_text())
    assert len(dados["pessoas"]) == 84 and list(dados["chats"]) == [B]


def test_gerar_sem_checkout_com_a_b2_4_diz_o_que_fazer(ambiente, tmp_path):
    r = kit({**ambiente, "IA_REPO": str(tmp_path / "vazio"), "HOME": str(tmp_path / "casa")}, "gerar", "--par", f"{B}=P13", "--ensaio")
    assert r.returncode == 0, "o ensaio de `gerar` não precisa do repositório"
    # o kit do próprio repositório SEMPRE acha o checkout dele (é o primeiro candidato), então `gerar` funciona sem IA_REPO
    sem_repo = {k: v for k, v in ambiente.items() if k != "IA_REPO"}
    assert kit(sem_repo, "gerar", "--par", f"{B}=P13", "--confirmo").returncode == 0


def test_gerar_preserva_os_pares_do_arquivo_anterior_e_o_fluxo_gerar_aplicar_limpar_nao_toma_422(ambiente, api, tmp_path):
    """R2-03, ponta a ponta contra a API em processo que valida a lista inteira contra o arquivo do boot: gerar A → aplicar A → gerar B (preserva A) → aplicar B
    em merge → limpar (restaura [A]). Sem 422 em nenhum passo."""
    api.valor = []
    saida = Path(ambiente["SAIDA_ARQUIVO"])
    assert kit(ambiente, "gerar", "--par", f"{A}=P01", "--confirmo").returncode == 0
    api.reiniciar_com(saida)
    assert _aplicar(ambiente, f"{A}=P01").returncode == 0 and api.valor == [A]

    r = kit(ambiente, "gerar", "--par", f"{B}=P02", "--confirmo")
    assert r.returncode == 0 and "2 chat(s)" in r.stdout, r.stdout + r.stderr
    assert set(json.loads(saida.read_text())["chats"]) == {A, B}, "o arquivo preserva o par antigo e acrescenta o novo"
    assert not Path(str(saida) + ".anterior").exists(), "a cópia temporária some"
    api.reiniciar_com(saida)
    r = _aplicar(ambiente, f"{B}=P02")
    assert r.returncode == 0, r.stdout + r.stderr
    assert api.valor == [A, B]
    r = kit(ambiente, "limpar", "--motivo", "fim", "--por", POR, "--confirmo")
    assert r.returncode == 0, r.stdout + r.stderr
    assert api.valor == [A]


def test_gerar_sem_preservar_derruba_o_aplicar_em_merge_e_o_limpar_por_422(ambiente, api, tmp_path):
    """O defeito que o R2-03 achou, agora como contraprova: arquivo só com o chat novo + merge com a lista vigente = 422 pelos chats antigos; `--recomecar` faz isso de propósito."""
    api.valor = [A]
    saida = Path(ambiente["SAIDA_ARQUIVO"])
    saida.write_text(json.dumps({"pessoas": [], "chats": {A: "00000000-0000-7000-8000-000000000001"}}))
    saida.chmod(0o600)
    assert kit(ambiente, "gerar", "--par", f"{B}=P02", "--recomecar", "--confirmo").returncode == 0
    assert set(json.loads(saida.read_text())["chats"]) == {B}, "--recomecar ignora o arquivo anterior"
    api.reiniciar_com(saida)
    r = _aplicar(ambiente, f"{B}=P02")
    assert r.returncode == 1 and "pessoa_fora_de_pessoas_teste" in r.stderr and api.valor == [A]


def test_gerar_com_arquivo_anterior_de_pessoa_fora_do_catalogo_ou_conflitante_recusa(ambiente, tmp_path):
    saida = Path(ambiente["SAIDA_ARQUIVO"])
    saida.write_text(json.dumps({"pessoas": [], "chats": {A: "11111111-1111-7111-8111-111111111111"}}))
    saida.chmod(0o600)
    r = kit(ambiente, "gerar", "--par", f"{B}=P02", "--confirmo")
    assert r.returncode != 0 and "catálogo" in r.stderr, "não adivinha a persona de uma pessoa que o catálogo não conhece"
    assert json.loads(saida.read_text())["chats"] == {A: "11111111-1111-7111-8111-111111111111"}, (
        "arquivo anterior intacto quando o gerar falha"
    )
    saida.write_text(json.dumps({"pessoas": [], "chats": {A: "00000000-0000-7000-8000-000000000001"}}))  # A = P01
    saida.chmod(0o600)
    assert kit(ambiente, "gerar", "--par", f"{A}=P02", "--confirmo").returncode != 0, "mesmo chat, outra persona: recusa"
    assert kit(ambiente, "gerar", "--par", f"{A}=P01", "--confirmo").returncode == 0, "mesmo chat, mesma persona: idempotente"
    assert kit(ambiente, "aplicar", "--recomecar", "--par", f"{A}=P01", "--motivo", "m1", "--por", POR, "--confirmo").returncode == 1


def test_ensaio_do_gerar_diz_se_preserva_ou_recomeca(ambiente):
    saida = Path(ambiente["SAIDA_ARQUIVO"])
    novo = kit(ambiente, "gerar", "--par", f"{B}=P02", "--ensaio")
    assert "arquivo novo ou --recomecar" in novo.stdout
    saida.write_text(json.dumps({"pessoas": [], "chats": {}}))
    assert "PRESERVA os pares" in kit(ambiente, "gerar", "--par", f"{B}=P02", "--ensaio").stdout
    assert "arquivo novo ou --recomecar" in kit(ambiente, "gerar", "--par", f"{B}=P02", "--recomecar", "--ensaio").stdout


def test_limpar_nao_restaura_por_cima_de_mudanca_de_terceiro_sem_forcar(ambiente, api, tmp_path):
    """R2-12a: se alguém acrescentou um chat no meio, a lista vigente deixa de ser a que o `aplicar` gravou e o `limpar` recusa (restaurar apagaria o chat dele)."""
    assert _aplicar(ambiente, f"{B}=P01").returncode == 0 and api.valor == [A, B]
    api.versao, api.valor = api.versao + 1, [A, B, C]  # terceiro acrescentou C
    r = kit(ambiente, "limpar", "--motivo", "fim", "--por", POR, "--confirmo")
    assert r.returncode == 1 and "alguém mexeu" in r.stderr and "--forcar" in r.stderr and api.valor == [A, B, C]
    assert anterior(tmp_path, api, 3).exists(), "a lista guardada continua à espera"
    forcado = kit(ambiente, "limpar", "--forcar", "--motivo", "fim", "--por", POR, "--confirmo")
    assert forcado.returncode == 0 and api.valor == [A]
    assert kit(ambiente, "aplicar", "--forcar", "--par", f"{B}=P01", "--motivo", "m1", "--por", POR, "--confirmo").returncode == 1, (
        "--forcar só vale em limpar"
    )


def test_limpar_so_restaura_lista_guardada_para_a_mesma_api(ambiente, api, tmp_path):
    """R2-12b: a lista guardada leva a URL (no nome e no conteúdo); a de outro ambiente, mesmo de versão MAIOR, nunca é restaurada aqui."""
    assert _aplicar(ambiente, f"{B}=P01").returncode == 0
    (tmp_path / "estado" / "anterior-deadbeef-99.json").write_text(
        json.dumps(
            {"url": "http://127.0.0.1:1", "versao_antes": 99, "valor": [C], "valor_depois": [C], "por": POR, "motivo": "outro_ambiente"}
        )
    )
    r = kit(ambiente, "limpar", "--motivo", "fim", "--por", POR, "--confirmo")
    assert r.returncode == 0 and api.valor == [A], "restaurou a desta API (versão 3), não a de outro ambiente (versão 99)"
    assert (tmp_path / "estado" / "anterior-deadbeef-99.json").exists()
    sem = kit(ambiente, "limpar", "--motivo", "fim", "--por", POR, "--confirmo")
    assert sem.returncode == 1 and "não há lista anterior" in sem.stderr, (
        "sobrou só a de outro ambiente: para esta API não há nada a restaurar"
    )


# --- a cópia de ~/retomada-2809 (R2-12c) -------------------------------------------------------------------------------------------------------


INSTALAR = RAIZ / "scripts" / "instalar_kit_chats_teste.sh"
RETOMADA = Path(os.environ.get("KIT_RETOMADA", "~/retomada-2809/fila-2910/ia/config/chats-teste.sh")).expanduser()


def _instalar(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(INSTALAR), *args], capture_output=True, text=True, check=False)


def test_instalar_gera_a_copia_igual_a_fonte_mais_uma_linha_e_o_verificar_pega_divergencia(tmp_path):
    destino = tmp_path / "copia" / "chats-teste.sh"
    assert _instalar(str(destino)).returncode == 0
    fonte, copia = KIT.read_text().splitlines(), destino.read_text().splitlines()
    assert copia[0] == fonte[0] and copia[2:] == fonte[1:] and "CÓPIA de kits/chats-teste.sh" in copia[1]
    assert destino.stat().st_mode & 0o777 == 0o755
    assert _instalar("--verificar", str(destino)).returncode == 0
    destino.write_text(destino.read_text() + "\n# editei a cópia à mão\n")
    r = _instalar("--verificar", str(destino))
    assert r.returncode == 1 and "difere" in r.stderr
    assert _instalar("--verificar", str(tmp_path / "nao-existe.sh")).returncode == 1


def test_a_copia_do_kit_nesta_maquina_e_igual_a_fonte():
    """Se `~/retomada-2809/fila-2910/ia/config/chats-teste.sh` existe aqui, tem de ser a fonte + o cabeçalho (rode `scripts/instalar_kit_chats_teste.sh`)."""
    if not RETOMADA.is_file():
        pytest.skip(f"{RETOMADA} não existe nesta máquina (defina KIT_RETOMADA para conferir outra cópia)")
    r = _instalar("--verificar", str(RETOMADA))
    assert r.returncode == 0, r.stderr
