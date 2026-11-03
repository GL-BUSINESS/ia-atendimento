"""Envelope de erro da API (contrato 08 §1 e §2): `{"erro":{"codigo","mensagem","campo","detalhe"},"trace_id":"<32 hex>"}`.

Nada que o cliente mandou volta na resposta: a `mensagem` é uma frase fixa por código, o `campo` é o NOME de um campo do contrato (ou um
marcador
como `(corpo)`), o `detalhe` só leva códigos de regra e contagens. As tabelas abaixo são o enum do catálogo de erros e as partes do
contrato 08 §2.
"""

from __future__ import annotations

import re
from typing import Any, Final

from fastapi.responses import JSONResponse

# código -> HTTP, exatamente a tabela de §2 do contrato 08 (o teste lê o contrato quando ele está na máquina)
CODIGOS_DO_CONTRATO: Final[dict[str, int]] = {
    "token_invalido": 401, "assinatura_invalida": 401,
    "origem_nao_autorizada": 403, "origem_teste_fora_da_lista": 403,
    "atendimento_inexistente": 404, "config_inexistente": 404,
    "ia_desligada": 409, "bloqueio_entrada": 409, "fora_de_janela": 409, "opt_out": 409, "janela_24h": 409,
    "teto_atingido": 409, "teto_diario": 409, "disparos_dia": 409, "abertos_max": 409,
    "chat_ocupado": 409, "chave_reutilizada": 409, "provedor_fora": 409, "pre_voo_falhou": 409,
    "agenda_desligada": 409, "agenda_max_dia": 409, "config_corrida": 409,
    "payload_grande": 413,
    "validacao": 422, "campo_desconhecido": 422, "campo_fora_da_allowlist": 422,
    "gatilho_desabilitado": 422, "chave_incoerente": 422, "faixa_incoerente": 422,
    "teste_fora_da_lista": 422, "persona_fora_de_teste": 422, "pessoa_fora_de_pessoas_teste": 422,
    "valor_invalido": 422, "modo_teste_global": 422, "chat_de_cliente": 422, "pii_no_texto_livre": 422,
    "artefatos_ausentes": 503, "nao_pronto": 503,
}  # fmt: skip
# do framework, fora da tabela do contrato: rota/método inexistente e falha interna (o corpo continua o mesmo envelope)
CODIGOS_AUXILIARES: Final[dict[str, int]] = {"erro_interno": 500, "rota_inexistente": 404, "metodo_nao_permitido": 405}

MENSAGENS: Final[dict[str, str]] = {
    "token_invalido": "Token ausente ou inválido.",
    "assinatura_invalida": "Assinatura ausente, vencida ou inválida.",
    "origem_nao_autorizada": "Esta origem não pode usar esta rota.",
    "origem_teste_fora_da_lista": "A credencial de teste só vale para chat da lista de teste.",
    "atendimento_inexistente": "Atendimento não encontrado.",
    "config_inexistente": "Chave de configuração fora do registro.",
    "payload_grande": "Corpo acima do limite.",
    "validacao": "Corpo ou parâmetro inválido.",
    "campo_desconhecido": "Campo fora do contrato.",
    "campo_fora_da_allowlist": "Campo fora da lista permitida.",
    "pii_no_texto_livre": "O texto livre contém dado pessoal.",
    "artefatos_ausentes": "Faltam versões aprovadas dos artefatos.",
    "nao_pronto": "Serviço indisponível; tente de novo.",
    "erro_interno": "Erro interno.",
    "rota_inexistente": "Rota inexistente.",
    "metodo_nao_permitido": "Método não permitido.",
}
_NOME_SEGURO: Final = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_DIGITOS: Final = re.compile(r"\d")
MAX_CAMPOS_NO_DETALHE: Final = 20


class ErroApi(Exception):
    """Erro de contrato: vira o envelope com o status do catálogo. Não leva nada do que o cliente enviou."""

    def __init__(self, codigo: str, *, campo: str | None = None, detalhe: dict[str, Any] | None = None) -> None:
        super().__init__(codigo)
        self.codigo = codigo
        self.status = {**CODIGOS_DO_CONTRATO, **CODIGOS_AUXILIARES}[codigo]
        self.campo = campo
        self.detalhe = detalhe or {}


def nome_seguro(nome: object) -> str:
    """Nome de chave que pode voltar na resposta: só `^[a-z][a-z0-9_]{0,39}$` com no máximo 3 dígitos. Senão, um marcador.

    Uma chave estranha pode ser o próprio dado (`"12345678909": "x"`); `cpf` e `celular` passam, `cpf12345678909` não."""
    if isinstance(nome, str) and _NOME_SEGURO.fullmatch(nome) and len(_DIGITOS.findall(nome)) <= 3:
        return nome
    return "(campo desconhecido)"


def envelope(erro: ErroApi, trace_id: str) -> dict[str, Any]:
    mensagem = MENSAGENS.get(erro.codigo, "Operação recusada.")
    return {"erro": {"codigo": erro.codigo, "mensagem": mensagem, "campo": erro.campo, "detalhe": erro.detalhe}, "trace_id": trace_id}


def resposta_de_erro(erro: ErroApi, trace_id: str) -> JSONResponse:
    return JSONResponse(envelope(erro, trace_id), status_code=erro.status)
