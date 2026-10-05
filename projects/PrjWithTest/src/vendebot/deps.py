"""Dependencias de FastAPI: repos, LLM client, configuracion y autenticacion.

Se inyectan via Request.app.state (poblado en el lifespan de la app) para
que los tests puedan sustituirlas con `app.dependency_overrides` sin tocar
la app real ni el proveedor real del LLM.
"""

from fastapi import Depends, Header, Request

from vendebot.config import Settings
from vendebot.errors import UnauthorizedError
from vendebot.llm.base import LLMClient
from vendebot.repo.factory import Repos
from vendebot.repo.models import Customer


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_repos(request: Request) -> Repos:
    return request.app.state.repos


def get_llm_client(request: Request) -> LLMClient:
    return request.app.state.llm_client


def get_current_customer(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    repos: Repos = Depends(get_repos),
) -> Customer:
    """El cliente se identifica solo por X-API-Key. Un id mencionado en el
    chat (p. ej. "soy el cliente C002") nunca se usa como prueba de identidad."""
    if not x_api_key:
        raise UnauthorizedError("Falta el header X-API-Key")
    customer = repos.customers.get_by_api_key(x_api_key)
    if customer is None:
        raise UnauthorizedError("API key invalida")
    return customer
