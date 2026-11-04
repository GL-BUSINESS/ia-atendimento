"""`pessoas_teste` (B2.4): quem pode ser cliente de um chat de teste e o que T1/T3 leem dessas pessoas em `duble|teste`.

`arquivo`: o `PessoasTeste` da API (arquivo JSON `{pessoas, chats}`; sem arquivo ninguém é de teste), vindo da B1.5.
`catalogo`: as 84 pessoas sintéticas (uma por `persona_id` da F3). `fonte`: serve T1/T3 delas com `valid_until` relativo.
`formas`: as formas medidas (360, 3RN, C6). `fixtures_duble`: os arquivos `fixtures/duble/*.json`. `prefixo`: a marca «[TESTE]».
"""

from __future__ import annotations

from ia_atendimento.pessoas_teste.arquivo import SEM_PESSOAS_DE_TESTE, PessoasTeste, PessoasTesteFixas, PessoasTesteInvalidas, carregar
from ia_atendimento.pessoas_teste.catalogo import CatalogoPessoasTeste, PessoaDeTeste, carregar_catalogo, catalogo_padrao, hash_canonico
from ia_atendimento.pessoas_teste.fixtures_duble import FixturesDuble, carregar_fixtures_duble
from ia_atendimento.pessoas_teste.fonte import MODOS_COM_FIXTURES, VALIDADE_PADRAO, FontePessoasTeste, ForaDoModoDeTeste
from ia_atendimento.pessoas_teste.prefixo import PREFIXO_TESTE, marcar_teste, texto_de_saida

__all__ = [
    "MODOS_COM_FIXTURES",
    "PREFIXO_TESTE",
    "SEM_PESSOAS_DE_TESTE",
    "VALIDADE_PADRAO",
    "CatalogoPessoasTeste",
    "FixturesDuble",
    "FontePessoasTeste",
    "ForaDoModoDeTeste",
    "PessoaDeTeste",
    "PessoasTeste",
    "PessoasTesteFixas",
    "PessoasTesteInvalidas",
    "carregar",
    "carregar_catalogo",
    "carregar_fixtures_duble",
    "catalogo_padrao",
    "hash_canonico",
    "marcar_teste",
    "texto_de_saida",
]
