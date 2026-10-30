"""API de entrada do orquestrador (B1.5, contrato 08): `criar_app(contexto)` e, para o uvicorn, `ambiente:criar_app_de_ambiente`."""

from ia_atendimento.api.app import criar_app
from ia_atendimento.api.contexto import ContextoApi, PreVoo, PreVooComCache, PreVooFalhou, PreVooLivre

__all__ = ["ContextoApi", "PreVoo", "PreVooComCache", "PreVooFalhou", "PreVooLivre", "criar_app"]
