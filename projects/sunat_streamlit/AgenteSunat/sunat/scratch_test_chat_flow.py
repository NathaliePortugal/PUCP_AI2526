from __future__ import annotations

import json

from app.services.chat_orchestrator import ChatOrchestrator
from app.services.rag_executor import RagExecutor
from app.services.router import ConversationRouter
from app.services.state_store import InMemoryStateStore
from app.services.tool_executor import ToolExecutor
from app.services.intent_service import IntentService
from app.services.rag_service import RagService
from app.services.llm_service import LLMService


def print_block(title: str, payload: dict) -> None:
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


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


def run_flow(orchestrator: ChatOrchestrator, session_id: str, messages: list[str]) -> None:
    for index, message in enumerate(messages, start=1):
        result = orchestrator.handle_message(session_id=session_id, message=message)
        print_block(
            title=f"TURNO {index} - MENSAJE: {message}",
            payload=result,
        )


def run_formalization_flow() -> None:
    """
    Flujo completo de formalización: 5 preguntas guiadas.
    Cubre build_formalization_checklist de principio a fin.
    """
    print("\n>>> FLUJO: FORMALIZACION DE NEGOCIO <<<")
    orchestrator = build_orchestrator()
    run_flow(orchestrator, "demo-formalizacion", [
        "Quiero formalizar mi negocio",
        "no",
        "natural",
        "servicios",
        "boletas",
        "sí",
    ])


def run_tax_regime_flow() -> None:
    """
    Flujo completo de regímenes tributarios: 3 preguntas guiadas.
    Cubre compare_tax_regimes de principio a fin.

    Perfil simulado: ventas bajas (a), no necesita facturas, trabaja solo (a).
    Resultado esperado: recomendación Nuevo RUS.
    """
    print("\n>>> FLUJO: REGIMENES TRIBUTARIOS <<<")
    orchestrator = build_orchestrator()
    run_flow(orchestrator, "demo-regimenes", [
        "Ayúdame a elegir el régimen tributario ideal para mi negocio",
        "a",   # ventas: menos de S/5,000
        "no",  # no necesita facturas
        "a",   # trabaja solo
    ])


def run_fines_flow() -> None:
    """
    Flujo one-shot de multas y sanciones.
    handle_fines_guidance responde en 1 turno y libera el control al RAG.
    Verifica que active_tool quede None tras la primera respuesta.
    """
    print("\n>>> FLUJO: MULTAS Y SANCIONES <<<")
    orchestrator = build_orchestrator()
    run_flow(orchestrator, "demo-multas", [
        "Tengo una multa de SUNAT",
    ])


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
    print("1. Flujo de formalización")
    print("2. Flujo de regímenes tributarios")
    print("3. Flujo de multas y sanciones")
    print("4. Modo interactivo")
    option = input("Elige una opción (1/2/3/4): ").strip()

    if option == "1":
        run_formalization_flow()
    elif option == "2":
        run_tax_regime_flow()
    elif option == "3":
        run_fines_flow()
    else:
        run_interactive_console()
