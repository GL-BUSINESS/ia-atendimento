"""Gateway de ferramentas (B5.1; estudo F §Gateway 1–12): o único caminho entre o modelo (ou o código) e o mundo de fora.

- `especificacao`, `esquemas`, `catalogo`: o registro versionado (`catalogo_hash` amarrado ao `numero` de `catalogo_versoes.json`);
- `gateway`: `Gateway.chamar` (validação, referências, orçamento, pré-condições, destino, CPF em memória, saída) e as `Tool` do agente;
- `modo`: `modo_efetivo` relido a cada efeito e o destino por serviço (a FACTA de produção só em `real`);
- `saida`, `segredo`, `orcamento`, `erros`: a reconstrução por allowlist, o CPF em memória, os tetos e o vocabulário fechado de erros;
- `projecao`: a cerca do retorno no `Agent` (B1.4, A-1): nada volta ao modelo sem a allowlist de `PROJECAO_DAS_FERRAMENTAS`.

Não confundir com o `gl-gateway` (S2) nem com o ledger (`ferramenta_chamada`, B1.6).
"""

from __future__ import annotations

from ia_atendimento.ferramentas.projecao import (
    MENSAGEM_DE_NOVA_TENTATIVA,
    Deps,
    FerramentaFalhou,
    FerramentaSemProjecao,
    ProjecaoDeFerramentas,
    RetornoDeFerramentaInvalido,
    proteger_retorno,
    registrar,
)

__all__ = [
    "MENSAGEM_DE_NOVA_TENTATIVA",
    "Deps",
    "FerramentaFalhou",
    "FerramentaSemProjecao",
    "ProjecaoDeFerramentas",
    "RetornoDeFerramentaInvalido",
    "proteger_retorno",
    "registrar",
]
