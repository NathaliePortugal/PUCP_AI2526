"""La identidad del cliente viene solo del header X-API-Key, nunca de un id
mencionado en el chat (caso de seguridad de la tabla de validacion)."""

from dataclasses import dataclass

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from vendebot.deps import get_current_customer, get_repos
from vendebot.errors import register_error_handlers
from vendebot.repo.models import Customer


@dataclass
class _FakeCustomersRepo:
    customers_by_key: dict[str, Customer]

    def get_by_api_key(self, api_key: str) -> Customer | None:
        return self.customers_by_key.get(api_key)


@dataclass
class _FakeRepos:
    customers: _FakeCustomersRepo


def _build_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/whoami")
    def whoami(customer: Customer = Depends(get_current_customer)):
        return {"customer_id": customer.id}

    return app


def test_missing_api_key_is_unauthorized():
    app = _build_app()
    app.dependency_overrides[get_repos] = lambda: _FakeRepos(customers=_FakeCustomersRepo({}))
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/whoami")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_valid_api_key_resolves_the_owning_customer():
    app = _build_app()
    c001 = Customer(id="C001", name="Ana", api_key="dev-key-c001")
    fake_repos = _FakeRepos(customers=_FakeCustomersRepo({"dev-key-c001": c001}))
    app.dependency_overrides[get_repos] = lambda: fake_repos
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/whoami", headers={"X-API-Key": "dev-key-c001"})

    assert response.status_code == 200
    assert response.json() == {"customer_id": "C001"}


def test_a_customer_id_mentioned_in_text_is_never_used_as_identity():
    """Ni siquiera si el header pertenece a otro cliente: la identidad es
    siempre la del X-API-Key, el texto del request nunca se consulta aqui."""
    app = _build_app()
    c002 = Customer(id="C002", name="Luis", api_key="dev-key-c002")
    fake_repos = _FakeRepos(customers=_FakeCustomersRepo({"dev-key-c002": c002}))
    app.dependency_overrides[get_repos] = lambda: fake_repos
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/whoami", headers={"X-API-Key": "dev-key-c002"})

    assert response.json() == {"customer_id": "C002"}
