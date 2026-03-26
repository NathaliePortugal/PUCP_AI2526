from __future__ import annotations

from app.services.chat_orchestrator import ChatOrchestrator
from app.services.clarification_service import ClarificationService
from app.services.rag_executor import RagExecutor
from app.services.router import ConversationRouter
from app.services.state_store import InMemoryStateStore
from app.services.tool_executor import ToolExecutor
from app.services.intent_serviceZeroShot import ZeroShotIntentService


def build_orchestrator() -> ChatOrchestrator:
    return ChatOrchestrator(
        state_store=InMemoryStateStore(),
        intent_classifier=ZeroShotIntentService(),
        router=ConversationRouter(),
        tool_executor=ToolExecutor(),
        rag_executor=RagExecutor(),
        clarification_service=ClarificationService(),
    )


def test_formalization_flow():
    orchestrator = build_orchestrator()
    session_id = "assert-formalizacion"

    turns = [
        "Quiero formalizar mi negocio",
        "no",
        "natural",
        "servicios",
        "boletas",
        "sí",
    ]

    results = []
    for message in turns:
        results.append(orchestrator.handle_message(session_id, message))

    final_state = results[-1]["state"]
    final_response = results[-1]["response"]

    assert "Flujo de formalización completado" in final_response
    assert final_state["active_tool"] is None
    assert final_state["entities"]["formalization_result"]["has_ruc"] == "no"
    assert final_state["entities"]["formalization_result"]["person_type"] == "natural"
    assert final_state["entities"]["formalization_result"]["economic_activity"] == "servicios"


if __name__ == "__main__":
    test_formalization_flow()
    print("OK: test_formalization_flow pasó correctamente.")