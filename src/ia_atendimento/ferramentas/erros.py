"""Erros tipados do gateway (estudo F §Gateway 5): vocabulário FECHADO, mensagem fixa, nunca o valor que falhou.

O modelo vê só `{"erro": <código>}` (e, em `PRECONDICAO_FALHOU`, o nome da pré-condição), nunca texto do banco nem o argumento recusado.
Módulo-folha: não importa nada do pacote (o `contexto` e a `projecao` podem importá-lo sem ciclo).
"""

from __future__ import annotations

from typing import Any, Final, Literal, get_args

CodigoDeErro = Literal[
    "PARAMETRO_INVALIDO",
    "PRECONDICAO_FALHOU",
    "CONFIRMACAO_AUSENTE",
    "OPT_OUT",
    "LEASE_PERDIDO",
    "JANELA_DATAPREV",
    "BANCO_INDISPONIVEL",
    "ORCAMENTO_ESGOTADO",
    "CORRIGIVEL",
    "RECUSA",
    "INDETERMINADO",
    "EM_ANDAMENTO",
    "MODO_SOMENTE_LEITURA",
    "DESCONHECIDO",
]
CODIGOS_DE_ERRO: Final = frozenset(get_args(CodigoDeErro))

# Pré-condições nomeadas (F T7 e roteiro B5.4, 12 itens; opt-out e não perturbe separados). O nome diz o que TEM de valer; a falha devolve
# `PRECONDICAO_FALHOU{precondicao}`. Domínio fechado: é o que pode chegar ao modelo, então nada fora daqui.
PRECONDICOES: Final = frozenset(
    {
        "lease_ativo",
        "sem_opt_out",
        "sem_nao_perturbe",
        "fora_da_dataprev",
        "oferta_ativa",
        "confirmacao_aceita",
        "dados_completos",
        "sem_proposta_viva",
        "sem_tentativa_aberta",
        "corrigiveis_no_limite",
        "banco_habilitado",
        "humano_nao_assumiu",
        "com_matricula",
    }
)
CHAVE_DO_ERRO: Final = "erro"
CHAVE_DA_PRECONDICAO: Final = "precondicao"


class ErroDeFerramenta(Exception):
    """Falha tipada de uma chamada. `retry_apos_s` só em `BANCO_INDISPONIVEL`. A mensagem cita só o código (e a pré-condição)."""

    def __init__(self, codigo: CodigoDeErro, *, precondicao: str | None = None, retry_apos_s: int | None = None) -> None:
        if codigo not in CODIGOS_DE_ERRO:
            raise ValueError("código de erro fora do vocabulário fechado")
        if (precondicao is not None) != (codigo == "PRECONDICAO_FALHOU"):
            raise ValueError("pré-condição existe se e somente se o código é PRECONDICAO_FALHOU")
        if precondicao is not None and precondicao not in PRECONDICOES:
            raise ValueError("pré-condição fora do catálogo")
        if retry_apos_s is not None and (codigo != "BANCO_INDISPONIVEL" or retry_apos_s < 0):
            raise ValueError("retry_apos_s só em BANCO_INDISPONIVEL, não negativo")
        self.codigo: CodigoDeErro = codigo
        self.precondicao = precondicao
        self.retry_apos_s = retry_apos_s
        super().__init__(codigo if precondicao is None else f"{codigo}:{precondicao}")

    def copia_limpa(self) -> ErroDeFerramenta:
        """O mesmo erro, novo e nunca levantado: sem `__cause__`, `__context__` nem `__traceback__`. O executor que faz `except HTTPError:
        raise ErroDeFerramenta("RECUSA")` deixa no original a exceção do banco (com PII na mensagem) e os frames que tiveram o CPF revelado;
        o `Resultado` guarda só a cópia (revisão B5.1, M-4)."""
        return ErroDeFerramenta(self.codigo, precondicao=self.precondicao, retry_apos_s=self.retry_apos_s)

    def para_o_modelo(self) -> dict[str, Any]:
        corpo: dict[str, Any] = {CHAVE_DO_ERRO: self.codigo}
        if self.precondicao is not None:
            corpo[CHAVE_DA_PRECONDICAO] = self.precondicao
        return corpo


def envelope_de_erro(retorno: Any) -> dict[str, Any] | None:
    """O retorno é o envelope de erro do gateway? Devolve-o reconstruído (só código e pré-condição do vocabulário); senão `None`.

    Envelope = mapa com a chave `erro` e, no máximo, `precondicao`. Qualquer outra chave, ou valor fora do vocabulário, NÃO é envelope:
    o retorno segue pela projeção comum (que descarta o que não está na allowlist)."""
    if not isinstance(retorno, dict) or CHAVE_DO_ERRO not in retorno or set(retorno) - {CHAVE_DO_ERRO, CHAVE_DA_PRECONDICAO}:
        return None
    codigo, precondicao = retorno.get(CHAVE_DO_ERRO), retorno.get(CHAVE_DA_PRECONDICAO)
    if codigo not in CODIGOS_DE_ERRO:
        return None
    if codigo == "PRECONDICAO_FALHOU":
        if precondicao not in PRECONDICOES:
            return None
        return {CHAVE_DO_ERRO: codigo, CHAVE_DA_PRECONDICAO: precondicao}
    return None if precondicao is not None else {CHAVE_DO_ERRO: codigo}
