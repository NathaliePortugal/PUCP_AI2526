from __future__ import annotations

import json

from app.services.chat_orchestrator import ChatOrchestrator
from app.services.clarification_service import ClarificationService
from app.services.rag_executor import RagExecutor
from app.services.router import ConversationRouter
from app.services.state_store import InMemoryStateStore
from app.services.tool_executor import ToolExecutor
from app.services.intent_service import IntentService


def print_block(title: str, payload: dict) -> None:
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_orchestrator() -> ChatOrchestrator:
    return ChatOrchestrator(
        state_store=InMemoryStateStore(),
        intent_classifier=IntentService(),
        router=ConversationRouter(),
        tool_executor=ToolExecutor(),
        rag_executor=RagExecutor(),
        clarification_service=ClarificationService(),
    )


def run_predefined_flow() -> None:
    orchestrator = build_orchestrator()
    session_id = "demo-formalizacion"

    test_messages = [
        "Quiero formalizar mi negocio",
        "no",
        "natural",
        "servicios",
        "boletas",
        "sí",
    ]

    for index, message in enumerate(test_messages, start=1):
        result = orchestrator.handle_message(session_id=session_id, message=message)

        print_block(
            title=f"TURNO {index} - MENSAJE: {message}",
            payload=result,
        )


def run_interactive_console() -> None:
    orchestrator = build_orchestrator()
    session_id = "interactive-session"

    print("\nModo interactivo iniciado. Escribe 'salir' para terminar.\n")

    while True:
        message = input("TÚ: ").strip()
        if message.lower() in {"salir", "exit", "quit"}:
            print("Sesión finalizada.")
            break

        result = orchestrator.handle_message(session_id=session_id, message=message)

        print("\nBOT:")
        print(result["response"])

        print("\nINTENT:")
        print(json.dumps(result["intent_result"], ensure_ascii=False, indent=2))

        print("\nROUTE DECISION:")
        print(json.dumps(result["route_decision"], ensure_ascii=False, indent=2))

        print("\nSTATE:")
        print(json.dumps(result["state"], ensure_ascii=False, indent=2))
        print("\n" + "-" * 100)


if __name__ == "__main__":
    print("1. Ejecutar flujo predefinido")
    print("2. Ejecutar modo interactivo")
    option = input("Elige una opción (1/2): ").strip()

    if option == "1":
        run_predefined_flow()
    else:
        run_interactive_console()