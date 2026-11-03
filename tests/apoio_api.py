"""Apoio dos testes da API de entrada (B1.5): contexto injetado, cliente HTTP, assinatura do gateway e corpos sintéticos.

Tudo sintético: telefone `5511912345678` (o literal do contrato 08 §15), CPF só `000.000.0nn` e nunca em corpo aceito, e-mails `@glcapital.invalid`,
chaves de teste com «descartavel» no nome. Os testes olham o banco de verdade (Postgres 18 descartável do conftest); a fila é um espião que só registra.
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from ia_atendimento.api import ContextoApi, criar_app
from ia_atendimento.api.auth import assinatura_esperada
from ia_atendimento.chave import LeitorConfig
from ia_atendimento.cifra import Chaveiro
from ia_atendimento.config import Settings
from ia_atendimento.evento_mensagem import ChavesDeMensagem
from ia_atendimento.pessoas_teste import PessoasTesteFixas
from ia_atendimento.relogio import RelogioFalso
from ia_atendimento.segredos import SegredosDeSaida
from tests import fixtures_fila as ff
from tests.banco import Banco
from tests.estado_apoio import semear_versoes

INSTANTE = ff.INSTANTE_UTIL  # terça 17/11/2026 12:00 em São Paulo: dentro da janela, sem feriado nem DATAPREV; chave AES do mês = 2
CHAT = "0123456789abcdef01234567"
OUTRO_CHAT = "fedcba9876543210fedcba98"
CHAT_TESTE = "aaaaaaaaaaaaaaaaaaaaaaaa"
PHONE = "89abcdef0123456789abcdef"
PESSOA = "11111111-1111-7111-8111-111111111111"
PESSOA_TESTE = "33333333-3333-7333-8333-333333333333"
CLT_JOB = "5a1f0c3e-7b2d-4e9a-8c61-0d2f9b3a4e55"
CHAVE_VENDA = "venda:57460eeceae26a872a0bef6a72cdf8df"  # sha256(CLT_JOB|CHAT)[:32] (vetor do contrato 08 §4)
TELEFONE = "5511912345678"
OPERADOR = "operador.teste@glcapital.invalid"
RESPONSAVEL_IA = "amado.teste@glcapital.invalid"
CHAVE_GATEWAY = "chave-de-teste-descartavel-do-contrato-01"  # vetor dourado de 01 §3.2
CHAVE_GATEWAY_NOVA = "chave-de-teste-descartavel-do-contrato-02"
H16 = "chave-h16-de-teste-descartavel-01"
FINGERPRINT = "chave-fingerprint-de-teste-descartavel-01"
CHAT_REF = "chave-chat-ref-de-teste-descartavel-01"
TOKENS = {
    "n8n_braco": "token-n8n-descartavel-0123456789abcdef-A",
    "ti": "token-ti-descartavel-0123456789abcdef-B",
    "c360_api": "token-c360-descartavel-0123456789abcdef-C",
    "vigia": "token-vigia-descartavel-0123456789abcdef-D",
}


class EspiaDeFila:
    """`Enfileirador` que só registra (a fila real é provada em `test_enfileirador.py`)."""

    def __init__(self) -> None:
        self.turnos: list[tuple[uuid.UUID, str]] = []
        self.inicios: list[tuple[uuid.UUID, str]] = []
        self.encerramentos: list[tuple[uuid.UUID, str, float]] = []
        self.retomadas: list[tuple[uuid.UUID, uuid.UUID, str, datetime]] = []

    def turno(self, conn: psycopg.Connection, atendimento_id: uuid.UUID, chat_id: str) -> None:
        self.turnos.append((atendimento_id, chat_id))

    def iniciar(self, conn: psycopg.Connection, atendimento_id: uuid.UUID, chat_id: str) -> None:
        self.inicios.append((atendimento_id, chat_id))

    def encerrar_por_chave(self, conn: psycopg.Connection, atendimento_id: uuid.UUID, chat_id: str, atraso_s: float) -> bool:
        self.encerramentos.append((atendimento_id, chat_id, atraso_s))
        return True

    def agendar_retomada(
        self, conn: psycopg.Connection, agendamento_id: uuid.UUID, atendimento_id: uuid.UUID, chat_id: str, dispara_em: datetime
    ) -> bool:
        self.retomadas.append((agendamento_id, atendimento_id, chat_id, dispara_em))
        return True


def _chaveiro(tmp_path: Path) -> Chaveiro:
    arquivo = tmp_path / "chaves-api.json"
    arquivo.write_text(json.dumps({"1": base64.b64encode(os.urandom(32)).decode(), "2": base64.b64encode(os.urandom(32)).decode()}))
    arquivo.chmod(0o600)
    return Chaveiro.de_arquivo(arquivo, vigente=2)


def settings_de_teste(banco: Banco, tmp_path: Path, **mudar: Any) -> Settings:
    """`Settings` de verdade (a validação do boot roda): login `ia_app_a` do banco descartável, segredos de teste, arquivos 0600 em `tmp_path`."""
    s = banco.servidor
    campos: dict[str, Any] = {
        "database_url": f"postgresql://ia_app_a:x@{s.host}:{s.port}/{banco.nome}",
        "modelo_api_key_1": SecretStr("fw_chave-do-modelo-descartavel-123"),
        "api_tokens": {k: SecretStr(v) for k, v in TOKENS.items()},
        "chave_aes_id": 2,
        "chave_aes_arquivo": tmp_path / "chaves-api.json",
        "chave_h16": SecretStr(H16),
        "chave_fingerprint": SecretStr(FINGERPRINT),
        "chat_ref_chave": SecretStr(CHAT_REF),
        "gateway_hmac_arquivo": tmp_path / "gw.keys",
        "segredos_saida_arquivo": tmp_path / "saida.json",
        "responsavel_ia": RESPONSAVEL_IA,
    }
    return Settings(**{**campos, **mudar})  # type: ignore[arg-type]


@dataclass
class Ambiente:
    """O que um teste da API enxerga: o cliente HTTP, a fila espiã, o relógio, o contexto e o banco."""

    cliente: TestClient
    fila: EspiaDeFila
    relogio: RelogioFalso
    ctx: ContextoApi
    banco: Banco
    pessoas: dict[str, uuid.UUID] = field(default_factory=dict)

    def trocar(self, **campos: Any) -> None:
        """Troca peças do contexto da app em execução (pré-voo, fila, pessoas de teste...): a rota lê `app.state.ctx` a cada requisição."""
        self.ctx = dataclasses.replace(self.ctx, **campos)
        self.cliente.app.state.ctx = self.ctx  # type: ignore[attr-defined]

    def super(self) -> psycopg.Connection:
        return ff.abrir(self.banco, "postgres")

    def runtime(self) -> psycopg.Connection:
        return ff.abrir(self.banco)

    def consultar(self, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        with self.super() as conn:
            return [tuple(linha) for linha in conn.execute(sql, params).fetchall()]

    def escalar(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        linhas = self.consultar(sql, params)
        return linhas[0][0] if linhas else None

    def configurar(self, nome: str, valor: Any, versao_esperada: int | None = None) -> None:
        """Muda uma chave do jeito do runtime (pelo registro), sem passar pela API."""
        with self.runtime() as conn:
            self.ctx.leitor.registrar(conn, nome, valor, "teste", motivo="preparo do teste", versao_esperada=versao_esperada)

    def ligar(self) -> None:
        """Estado de uma instância no ar: IA e agenda ligadas, fora do bloqueio."""
        self.configurar("ia_ativa", True)
        self.configurar("agenda_ativa", True)

    def assinar(
        self, corpo: bytes, *, origem: str = "chatguru-ia", rota: str = "ia-mensagem", chave: str = CHAVE_GATEWAY, agora: int | None = None
    ) -> dict[str, str]:
        ts = str(int(self.relogio.agora().timestamp()) if agora is None else agora)
        return {
            "x-gl-origem": origem, "x-gl-rota": rota, "x-gl-timestamp": ts,
            "x-gl-assinatura": assinatura_esperada(chave.encode(), origem, rota, ts, corpo), "content-type": "application/json",
        }  # fmt: skip

    def post(self, caminho: str, corpo: Any, token: str | None = "n8n_braco", **cabecalhos: str) -> Any:
        bruto = corpo if isinstance(corpo, bytes) else json.dumps(corpo).encode()
        headers = {"content-type": "application/json", **cabecalhos}
        if token is not None:
            headers["x-ia-token"] = TOKENS[token]
        return self.cliente.post(caminho, content=bruto, headers=headers)

    def evento_chatguru(self, corpo: dict[str, Any], *, origem: str = "chatguru-ia", **opcoes: Any) -> Any:
        bruto = json.dumps(corpo, separators=(",", ":"), ensure_ascii=False).encode()
        return self.cliente.post("/eventos/chatguru", content=bruto, headers=self.assinar(bruto, origem=origem, **opcoes))

    def get(self, caminho: str, token: str | None = "ti") -> Any:
        return self.cliente.get(caminho, headers={"x-ia-token": TOKENS[token]} if token else {})

    def put(self, caminho: str, corpo: Any, token: str | None = "ti") -> Any:
        return self.cliente.put(
            caminho, content=json.dumps(corpo).encode(), headers={"x-ia-token": TOKENS[token], "content-type": "application/json"}
        )


@contextmanager
def _conexoes(banco: Banco) -> Iterator[psycopg.Connection]:
    with ff.abrir(banco) as conn:
        yield conn


@pytest.fixture
def ambiente(banco: Banco, tmp_path: Path) -> Iterator[Ambiente]:
    """API de pé sobre o Postgres descartável: 0001–0004, artefatos semeados, IA DESLIGADA (o seed), relógio na terça 12:00."""
    relogio = RelogioFalso(INSTANTE)
    with ff.abrir(banco) as conn:
        semear_versoes(conn)
    (tmp_path / "gw.keys").write_text(CHAVE_GATEWAY + "\n")
    (tmp_path / "gw.keys").chmod(0o600)
    saida = {
        c: f"valor-descartavel-de-{c}-0123" for c in ("ia_orquestrador_bearer", "chatguru_token_ia", "c360_client_id", "c360_client_secret")
    }
    (tmp_path / "saida.json").write_text(json.dumps(saida))
    (tmp_path / "saida.json").chmod(0o600)
    settings = settings_de_teste(banco, tmp_path)
    fila = EspiaDeFila()
    ctx = ContextoApi(
        settings=settings, relogio=relogio, conexao=lambda: _conexoes(banco), leitor=LeitorConfig(relogio, ttl_s=0),
        chaveiro=_chaveiro(tmp_path), chaves_msg=ChavesDeMensagem(H16.encode(), FINGERPRINT.encode()), enfileirador=fila,
        tokens={k: v.encode() for k, v in TOKENS.items()}, gateway_hmac=(CHAVE_GATEWAY.encode(),),
        pessoas_teste=PessoasTesteFixas(frozenset({uuid.UUID(PESSOA_TESTE)}), {CHAT_TESTE: uuid.UUID(PESSOA_TESTE)}),
        segredos_de_saida=SegredosDeSaida(**saida), dsn=ff.conninfo(banco), git_sha="abc1234", built_at="2026-10-30T00:00:00Z",
        diretorio_migracoes=Path(__file__).resolve().parent.parent / "migrations",
    )  # fmt: skip
    with TestClient(criar_app(ctx), raise_server_exceptions=False) as cliente:
        yield Ambiente(cliente, fila, relogio, ctx, banco)


def corpo_de_entrada(**mudar: Any) -> dict[str, Any]:
    """Corpo de `POST /atendimentos` do exemplo do contrato 08 §3 (vetor dourado de §4)."""
    base: dict[str, Any] = {
        "chave_logica": CHAVE_VENDA, "gatilho": "venda", "pessoa_id": PESSOA, "chat_id": CHAT, "phone_id": PHONE, "chat_number": TELEFONE,
        "disparado_por": OPERADOR, "clt_job_id": CLT_JOB, "sessao_id": "22222222-2222-7222-8222-222222222222",
        "motivo_escolha": "mais_antigo_elegivel", "criterio_versao": "c1.0", "ultimo_cliente_em": "2026-11-17T08:41:07-03:00",
        "perfil": {"banco": "FACTA", "faixa_parcela": "200_300", "idade_min": 42}, "perfil_versao": 1,
    }  # fmt: skip
    return {**base, **mudar}


def chave_para(clt_job: str, chat: str) -> str:
    return "venda:" + hashlib.sha256(f"{clt_job}|{chat}".encode()).hexdigest()[:32]


def entrada_para(chat: str, **mudar: Any) -> dict[str, Any]:
    """Corpo coerente (chave recalculada) para um chat/job novo."""
    job = mudar.pop("clt_job_id", str(uuid.uuid4()))
    return corpo_de_entrada(chat_id=chat, clt_job_id=job, chave_logica=chave_para(job, chat), **mudar)


def mensagem_nativa(texto: str = "oi, quero saber da proposta", **mudar: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "chat_id": CHAT,
        "phone_id": PHONE,
        "tipo_mensagem": "chat",
        "texto_mensagem": texto,
        "datetime_post": "2026-11-17T08:59:30-03:00",
        "responsavel_email": RESPONSAVEL_IA,
    }
    return {**base, **mudar}


def abrir_ativo(amb: Ambiente, chat: str = CHAT, estado: str = "aberto", modo: str = "duble", **mudar: Any) -> uuid.UUID:
    """Atendimento ativo sintético no chat (por SQL, como o `iniciar` deixaria)."""
    with amb.super() as conn:
        return ff.inserir_atendimento(conn, estado=estado, chat_id=chat, modo=modo, iniciado_em=amb.relogio.agora(), **mudar)


def agora_utc() -> datetime:
    return datetime.now(UTC)


def corpo_de_agendamento(chat: str = CHAT, **mudar: Any) -> dict[str, Any]:
    """Corpo de `POST /agendamentos` com a chave RECALCULADA do `datetime_post` (08 §5.5). «hoje às 17h» cabe na janela e no teto de 23 h."""
    from datetime import datetime as _dt

    from ia_atendimento.agendamento import chave_logica_do_agendamento

    postado = mudar.pop("datetime_post", "2026-11-17T11:55:00-03:00")
    chave = mudar.pop("chave", None) or chave_logica_do_agendamento(chat, _dt.fromisoformat(postado))
    base: dict[str, Any] = {
        "pessoa_id": PESSOA, "chat_id": chat, "phone_id": PHONE, "chat_number": TELEFONE, "clt_job_id": CLT_JOB,
        "texto_mensagem": "pode ser hoje às 17h", "datetime_post": postado, "retoma_fase": "E8", "chave": chave,
    }  # fmt: skip
    return {**base, **mudar}


def env_de_processo(ambiente, tmp_path: Path, dialeto: str = "") -> dict[str, str]:
    """Ambiente de um PROCESSO real (uvicorn, worker) contra o Postgres descartável: o mesmo conjunto de variáveis que a OPERACAO manda."""
    s = ambiente.banco.servidor
    return {
        "PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "PYTHONUNBUFFERED": "1",
        "DATABASE_URL": f"postgresql{dialeto}://ia_app_a:x@{s.host}:{s.port}/{ambiente.banco.nome}",
        "MODELO_API_KEY_1": "fw_chave-do-modelo-descartavel-123", "API_TOKENS": json.dumps(TOKENS), "CHAVE_AES_ID": "2",
        "CHAVE_AES_ARQUIVO": str(tmp_path / "chaves-api.json"), "CHAVE_H16": H16, "CHAVE_FINGERPRINT": FINGERPRINT, "CHAT_REF_CHAVE": CHAT_REF,
        "GATEWAY_HMAC_ARQUIVO": str(tmp_path / "gw.keys"), "SEGREDOS_SAIDA_ARQUIVO": str(tmp_path / "saida.json"), "RESPONSAVEL_IA": RESPONSAVEL_IA,
    }  # fmt: skip
