"""Pruebas de extremo a extremo sobre la app real (rutas, esquemas,
dependencias y lifespan), con LLM simulado via dependency_overrides."""

import pytest

from vendebot.api.main import app
from vendebot.deps import get_llm_client
from vendebot.llm.base import LLMReply, ReviewClassification, ToolCall
from vendebot.llm.fake_client import FakeLLMClient
from tests.unit.conftest import C001_HEADERS, C002_HEADERS


def test_products_endpoint_filters_by_query(client):
    response = client.get("/products", params={"query": "Audifonos"})

    assert response.status_code == 200
    ids = {p["id"] for p in response.json()}
    assert ids == {"P001", "P002"}


def test_chat_without_api_key_is_unauthorized(client):
    response = client.post("/chat", json={"session_id": "s1", "message": "hola"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_full_propose_then_confirm_flow(client):
    fake = FakeLLMClient(
        scripted_replies=[
            LLMReply(
                text=None,
                tool_calls=[
                    ToolCall(
                        name="propose_order",
                        arguments={"items": [{"product_id": "P001", "quantity": 2}]},
                        call_id="call-1",
                    )
                ],
                continuation_token="interaction-1",
            ),
            LLMReply(text="Te propongo 2 audifonos X por 259.80 en total.", tool_calls=[]),
        ]
    )
    app.dependency_overrides[get_llm_client] = lambda: fake

    chat_response = client.post(
        "/chat", json={"session_id": "s1", "message": "quiero 2 audifonos X"}, headers=C001_HEADERS
    )
    assert chat_response.status_code == 200
    body = chat_response.json()
    assert body["tools_used"] == ["propose_order"]
    proposal_id = body["proposal"]["proposal_id"]

    confirm_response = client.post(
        "/orders/confirm",
        json={"proposal_id": proposal_id, "confirm": True},
        headers={**C001_HEADERS, "Idempotency-Key": "idem-flow-1"},
    )
    assert confirm_response.status_code == 200
    order = confirm_response.json()
    assert order["status"] == "confirmed"
    assert order["total"] == pytest.approx(259.80)

    repeat_response = client.post(
        "/orders/confirm",
        json={"proposal_id": proposal_id, "confirm": True},
        headers={**C001_HEADERS, "Idempotency-Key": "idem-flow-1"},
    )
    assert repeat_response.json()["order_id"] == order["order_id"]

    order_id = order["order_id"]
    owner_view = client.get(f"/orders/{order_id}", headers=C001_HEADERS)
    assert owner_view.status_code == 200

    stranger_view = client.get(f"/orders/{order_id}", headers=C002_HEADERS)
    assert stranger_view.status_code == 404
    assert stranger_view.json()["error"]["code"] == "NOT_FOUND"


def test_discount_request_is_not_proposed_and_has_no_tool_calls(client):
    """Caso de seguridad: pedir un descuento se deriva a una persona; no
    existe una herramienta de descuentos que el LLM pueda invocar."""
    fake = FakeLLMClient(
        scripted_replies=[
            LLMReply(
                text="No puedo aplicar descuentos. Un asesor humano revisara tu pedido.",
                tool_calls=[],
            )
        ]
    )
    app.dependency_overrides[get_llm_client] = lambda: fake

    response = client.post(
        "/chat", json={"session_id": "s2", "message": "dame 50% de descuento"}, headers=C001_HEADERS
    )

    assert response.status_code == 200
    body = response.json()
    assert body["proposal"] is None
    assert body["tools_used"] == []


def test_batch_endpoint_runs_the_resumable_batch(client):
    fake = FakeLLMClient(
        scripted_classifications=[
            ReviewClassification(label="positivo", motivo="m", evidencia="e", confianza=0.7) for _ in range(8)
        ]
    )
    app.dependency_overrides[get_llm_client] = lambda: fake

    response = client.post("/batch/reviews/run")

    assert response.status_code == 200
    body = response.json()
    assert body["processed"] == 8
    assert body["succeeded"] == 8
    assert body["failed"] == 0
