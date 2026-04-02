from __future__ import annotations

from app.services.chat_orchestrator import ChatOrchestrator
from app.services.rag_executor import RagExecutor
from app.services.router import ConversationRouter
from app.services.state_store import InMemoryStateStore
from app.services.tool_executor import ToolExecutor
from app.services.intent_service import IntentService
from app.services.rag_service import RagService
from app.services.llm_service import LLMService


def build_orchestrator() -> ChatOrchestrator:
    rag = RagService()
    llm = LLMService()
    return ChatOrchestrator(
        state_store=InMemoryStateStore(),
        intent_classifier=IntentService(),
        router=ConversationRouter(),
        tool_executor=ToolExecutor(rag_service=rag, llm_service=llm),
        rag_executor=RagExecutor(rag_service=rag, llm_service=llm),
    )


def run_turns(orchestrator: ChatOrchestrator, session_id: str, messages: list[str]) -> dict:
    """Ejecuta todos los turnos y devuelve el resultado del último."""
    result = {}
    for message in messages:
        result = orchestrator.handle_message(session_id, message)
    return result


def test_formalization_flow():
    """
    Verifica que el flujo de formalización:
    - Guarda correctamente las respuestas del usuario en el estado.
    - Limpia el flujo activo al terminar (no queda en bucle).
    - Libera active_tool para que el siguiente mensaje vaya al RAG.
    """
    orchestrator = build_orchestrator()
    last = run_turns(orchestrator, "assert-formalizacion", [
        "Quiero formalizar mi negocio",
        "no",
        "natural",
        "servicios",
        "boletas",
        "sí",
    ])

    state = last["state"]
    result = state["entities"].get("formalization_result", {})

    assert state["active_tool"] is None, "active_tool debe quedar None al finalizar"
    assert result.get("has_ruc") == "no", f"has_ruc esperado 'no', recibido '{result.get('has_ruc')}'"
    assert result.get("person_type") == "natural", f"person_type esperado 'natural', recibido '{result.get('person_type')}'"
    assert result.get("economic_activity") == "servicios", f"economic_activity esperado 'servicios', recibido '{result.get('economic_activity')}'"
    assert result.get("voucher_type") == "boletas", f"voucher_type esperado 'boletas', recibido '{result.get('voucher_type')}'"
    assert result.get("has_employees") == "sí", f"has_employees esperado 'sí', recibido '{result.get('has_employees')}'"
    assert "formalization_flow" not in state["entities"], "formalization_flow debe eliminarse del estado al terminar"

    print("OK: test_formalization_flow pasó correctamente.")


def test_tax_regime_flow():
    """
    Verifica que el flujo de regímenes tributarios:
    - Guarda las 3 respuestas del usuario.
    - Limpia tax_regime_flow del estado al terminar.
    - Libera active_tool.

    Perfil simulado: ventas bajas, no necesita facturas, trabaja solo.
    """
    orchestrator = build_orchestrator()
    last = run_turns(orchestrator, "assert-regimenes", [
        "Ayúdame a elegir el régimen tributario ideal para mi negocio",
        "a",   # ventas: menos de S/5,000
        "no",  # no necesita facturas
        "a",   # trabaja solo
    ])

    state = last["state"]
    result = state["entities"].get("tax_regime_result", {})

    assert state["active_tool"] is None, "active_tool debe quedar None al finalizar"
    assert result.get("monthly_sales") is not None, "monthly_sales debe haberse guardado"
    assert result.get("needs_invoices") == "no", f"needs_invoices esperado 'no', recibido '{result.get('needs_invoices')}'"
    assert result.get("worker_count") is not None, "worker_count debe haberse guardado"
    assert "tax_regime_flow" not in state["entities"], "tax_regime_flow debe eliminarse del estado al terminar"

    print("OK: test_tax_regime_flow pasó correctamente.")


def test_fines_flow():
    """
    Verifica que el flujo one-shot de multas:
    - Responde en el primer turno sin pedir más datos.
    - Libera active_tool inmediatamente (es un handler de un solo turno).
    """
    orchestrator = build_orchestrator()
    last = run_turns(orchestrator, "assert-multas", [
        "Tengo una multa de SUNAT",
    ])

    state = last["state"]

    assert state["active_tool"] is None, "active_tool debe quedar None tras el turno one-shot de multas"
    assert len(last["response"]) > 50, "La respuesta de multas debe tener contenido real"

    print("OK: test_fines_flow pasó correctamente.")


if __name__ == "__main__":
    test_formalization_flow()
    test_tax_regime_flow()
    test_fines_flow()
    print("\nTodos los tests pasaron.")
