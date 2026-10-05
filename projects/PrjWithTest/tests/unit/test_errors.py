from fastapi import FastAPI
from fastapi.testclient import TestClient

from vendebot.errors import NotFoundError, error_body, register_error_handlers


def test_error_body_shape():
    body = error_body("NOT_FOUND", "no existe", "trace-123")
    assert body == {"error": {"code": "NOT_FOUND", "message": "no existe", "trace_id": "trace-123"}}


def test_not_found_error_has_code_and_status():
    exc = NotFoundError("producto no encontrado")
    assert exc.code == "NOT_FOUND"
    assert exc.status_code == 404


def test_vendebot_error_is_rendered_with_unified_contract():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise NotFoundError("producto no encontrado")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NOT_FOUND", "message": "producto no encontrado", "trace_id": None}
    }


def test_unhandled_exception_uses_internal_error_code():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise RuntimeError("algo no previsto")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
