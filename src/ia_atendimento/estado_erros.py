"""Erros do ciclo de vida do atendimento (B1.1). Mensagens trazem nomes de campo/estado/restrição, nunca valores da linha ou do cliente.

Moram aqui (não em `estado.py`) para o módulo de entrada e o de transições os compartilharem sem import circular; `estado` os reexporta."""

from __future__ import annotations


class EstadoErro(Exception):
    """Base dos erros do ciclo de vida. Mensagens trazem nomes de campo/estado/restrição, nunca valores da linha."""


class TransicaoInvalida(EstadoErro):
    def __init__(self, mensagem: str, *, restricao: str | None = None) -> None:
        super().__init__(mensagem)
        self.restricao = restricao  # nome do CHECK do banco que barrou, quando foi ele


class ConflitoVersao(EstadoErro):
    """Outro escritor mudou o atendimento (CAS por `versao` perdeu): releia e decida de novo."""


class AtendimentoInexistente(EstadoErro):
    pass


class ConflitoIdempotencia(EstadoErro):
    """Mesma `(origem, chave_logica)` com identidade diferente (HTTP 409 `chave_reutilizada`)."""


class ChatOcupado(EstadoErro):
    """Já existe atendimento não encerrado neste chat (HTTP 409 `chat_ocupado`)."""


class ArtefatoAusente(EstadoErro):
    def __init__(self, tipos: tuple[str, ...]) -> None:
        super().__init__("sem artefato_versao para: " + ", ".join(tipos))
        self.tipos = tipos


class ModoInvalido(EstadoErro):
    def __init__(self, codigo: str) -> None:
        super().__init__(codigo)
        self.codigo = codigo  # teste_fora_da_lista | persona_fora_de_teste | modo_teste_global | validacao


class DadoRecusado(EstadoErro):
    """O banco recusou o dado (CHECK, NOT NULL, tipo). Só sqlstate e nome da restrição: a mensagem do psycopg traz a LINHA inteira."""

    def __init__(self, *, sqlstate: str | None, restricao: str | None) -> None:
        super().__init__(f"banco recusou o dado (sqlstate {sqlstate or '?'}, restrição {restricao or '?'})")
        self.sqlstate = sqlstate
        self.restricao = restricao


class EntradaInvalida(EstadoErro, ValueError):
    """Argumento incoerente que o banco também recusaria (CHECK), barrado antes de chegar nele.

    `campos` = pares `(campo, regra)` quando vem de validação de corpo (`EntradaAtendimento.de_corpo`): só NOMES, nunca o valor.
    """

    def __init__(self, mensagem: str, *, campos: tuple[tuple[str, str], ...] = ()) -> None:
        super().__init__(mensagem)
        self.campos = campos
