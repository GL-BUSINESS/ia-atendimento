#!/usr/bin/env python3
"""Varredura dos arquivos versionados E dos novos ainda não adicionados (respeitando .gitignore): segredo, credencial em URL de
host que não seja local, CPF com DV válido, celular brasileiro e e-mail que não seja de teste. Sai 1 se achar algo.

Dado sintético permitido fica nas listas abaixo (CPFs de exemplo conhecidos e a faixa `000.000.0nn` do corpus; celulares de exemplo; e-mails `@exemplo.test`; hosts
`.test`, loopback e a faixa de documentação 203.0.113.0/24).

NÃO pega: texto de cliente em prosa, nome de pessoa, CEP, dado em arquivo binário, segredo sem forma conhecida (use gitleaks quando o
CI voltar) e CPF/celular escrito por extenso ou com separadores fora do usual. É uma rede de segurança, não prova de ausência.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SEGREDOS = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16}|\bfw_[A-Za-z0-9]{24,}|\bgh[pousr]_[A-Za-z0-9]{30,}|\bsk-[A-Za-z0-9]{24,}"
    r"|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}|(?i:password|senha|secret|token)\s*[:=]\s*['\"][^'\"\s]{12,}['\"]"
)
# credencial em URL (`esquema://usuario:senha@host`): só passa host de teste/loopback/documentação ou marcador (HOST)
URL_COM_SENHA = re.compile(r"[a-z][a-z0-9+.\-]*://[^\s:/@'\"`]+:([^\s@/'\"`]{3,})@(\[[^\s/'\"`\]]*\]?|[^\s/:'\"`?]+)", re.IGNORECASE)
HOSTS_DE_URL_OK = {"127.0.0.1", "localhost", "[::1]", "host"}
PREFIXOS_DE_HOST_OK = ("203.0.113.", "[::1", "{", "$")  # documentação, IPv6 loopback, marcador de template/variável de shell
# celular com hífen entre as metades (`(11) 91234-5678`, `+55 11 91234-5678`); sem hífen se confunde com CPF de 11 dígitos
CELULAR_BR = re.compile(r"(?<![0-9])(?:\+?55[ -]?)?\(?[1-9][0-9]\)?[ -]?(9[0-9]{4})-([0-9]{4})(?![0-9])")
CELULARES_SINTETICOS = {"912345678", "987654321", "999999999", "900000000"}
CPF = re.compile(r"(?<![0-9])([0-9]{3})\.?([0-9]{3})\.?([0-9]{3})-?([0-9]{2})(?![0-9])")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})")
DOMINIOS_DE_TESTE = {"exemplo.test", "x.com", "sub.exemplo.com.br", "exemplo.com", "exemplo.com.br", "users.noreply.github.com"}
# reservados (RFC 2606) e o domínio do provedor aprovado, que aparece em URLs de exemplo (`https://u:p@us.api.fireworks.ai`)
SUFIXOS_DE_DOMINIO_OK = (".test", ".example", ".invalid", ".localhost", ".fireworks.ai")
CPFS_SINTETICOS = {"52998224725", "00000000000", "12345678909", "11144477735"}
PREFIXO_CPF_DO_CORPUS = "0000000"  # `000.000.0nn-dd`: a faixa sintética das personas do corpus da F3 (e do dublê); nenhuma pessoa real tem
IGNORAR = {"uv.lock"}


def _cpf_valido(onze: str) -> bool:
    if len(set(onze)) == 1:
        return False
    for n in (9, 10):
        soma = sum(int(d) * p for d, p in zip(onze[:n], range(n + 1, 1, -1), strict=True))
        if (soma * 10) % 11 % 10 != int(onze[n]):
            return False
    return True


def _segredo_real(linha: str) -> bool:
    """Casou com a forma de segredo e o TRECHO casado não é marcado como exemplo (a palavra «exemplo» solta na linha não isenta)."""
    return any(not any(marca in m.group() for marca in ("exemplo", "descartavel")) for m in SEGREDOS.finditer(linha))


def _url_com_credencial_real(linha: str) -> bool:
    for m in URL_COM_SENHA.finditer(linha):
        host = m.group(2).lower()
        if host not in HOSTS_DE_URL_OK and not host.endswith(SUFIXOS_DE_DOMINIO_OK) and not host.startswith(PREFIXOS_DE_HOST_OK):
            return True
    return False


def varrer(arquivo: Path) -> list[str]:
    try:
        texto = arquivo.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    achados = []
    for numero, linha in enumerate(texto.splitlines(), start=1):
        if _segredo_real(linha):
            achados.append(f"{arquivo.relative_to(RAIZ)}:{numero}: parece segredo")
        if _url_com_credencial_real(linha):
            achados.append(f"{arquivo.relative_to(RAIZ)}:{numero}: credencial em URL de host que não é de teste")
        for m in CELULAR_BR.finditer(linha):
            if m.group(1) + m.group(2) not in CELULARES_SINTETICOS:
                achados.append(f"{arquivo.relative_to(RAIZ)}:{numero}: celular brasileiro fora da lista sintética")
        for m in CPF.finditer(linha):
            onze = "".join(m.groups())
            if onze not in CPFS_SINTETICOS and not onze.startswith(PREFIXO_CPF_DO_CORPUS) and _cpf_valido(onze):
                achados.append(f"{arquivo.relative_to(RAIZ)}:{numero}: CPF com DV válido fora da lista sintética")
        for m in EMAIL.finditer(linha):
            if m.group(1).lower() not in DOMINIOS_DE_TESTE and not m.group(1).lower().endswith(SUFIXOS_DE_DOMINIO_OK):
                achados.append(f"{arquivo.relative_to(RAIZ)}:{numero}: e-mail de domínio real ({m.group(1)})")
    return achados


def main() -> int:
    # versionados + novos ainda sem `git add` (que não estejam no .gitignore): o portão roda ANTES do commit
    comando = ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"]
    arquivos = subprocess.run(comando, cwd=RAIZ, check=True, capture_output=True, text=True).stdout.split("\0")
    achados = [a for nome in arquivos if nome and nome not in IGNORAR and (RAIZ / nome).is_file() for a in varrer(RAIZ / nome)]
    for a in achados:
        print(a, file=sys.stderr)
    if achados:
        print(f"varredura: {len(achados)} achado(s)", file=sys.stderr)
        return 1
    print("varredura: limpa")
    return 0


if __name__ == "__main__":
    sys.exit(main())
