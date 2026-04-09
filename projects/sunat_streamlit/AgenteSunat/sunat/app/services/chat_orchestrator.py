from __future__ import annotations

from app.schemas.nlu import IntentResult, RouteDecision
from app.services.clarification_service import build_clarification_message
from app.services.intent_service import IntentService
from app.services.rag_executor import RagExecutor
from app.services.router import ConversationRouter
from app.services.state_store import ConversationState, InMemoryStateStore
from app.services.tool_executor import ToolExecutor


class ChatOrchestrator:
    """
    Coordina cada turno de conversación.

    Por cada mensaje del usuario:
    1. Carga el estado de la sesión
    2. Clasifica la intención
    3. El router decide qué hacer (wizard / RAG / aclaración)
    4. Actualiza el estado
    5. Ejecuta la acción y devuelve la respuesta
    """

    def __init__(
        self,
        state_store: InMemoryStateStore,
        intent_classifier: IntentService,
        router: ConversationRouter,
        tool_executor: ToolExecutor,
        rag_executor: RagExecutor,
    ) -> None:
        self.state_store = state_store
        self.intent_classifier = intent_classifier
        self.router = router
        self.tool_executor = tool_executor
        self.rag_executor = rag_executor

    def handle_message(self, session_id: str, message: str) -> dict:
        state = self.state_store.get(session_id)
        intent_result = self.intent_classifier.classify_topic(message)
        decision = self.router.decide(
            message=message,
            intent_result=intent_result,
            state=state,
        )
        self._update_state_before_execution(state, intent_result, decision)
        response_text = self._execute_decision(message, state, intent_result, decision)
        self.state_store.save(state)

        return {
            "response": response_text,
            "intent_result": intent_result.model_dump(),
            "route_decision": decision.model_dump(),
            "state": self._serialize_state(state),
        }

    def _update_state_before_execution(
        self,
        state: ConversationState,
        intent_result: IntentResult,
        decision: RouteDecision,
    ) -> None:
        state.last_intent = intent_result.intent
        state.last_confidence = intent_result.confidence
        state.last_action = decision.action
        state.current_topic = intent_result.intent
        state.awaiting_clarification = decision.needs_clarification

        if decision.use_tool:
            state.active_tool = decision.tool_name
        elif decision.use_rag:
            state.active_tool = None

    def _execute_decision(
        self,
        message: str,
        state: ConversationState,
        intent_result: IntentResult,
        decision: RouteDecision,
    ) -> str:
        if decision.needs_clarification:
            return build_clarification_message(intent_result)

        if decision.use_tool and decision.tool_name:
            return self.tool_executor.execute(
                tool_name=decision.tool_name,
                message=message,
                state=state,
            )

        if decision.use_rag:
            return self.rag_executor.answer(message=message, state=state)

        return (
            "No se pudo determinar una acción válida para tu mensaje. "
            "Por favor intenta reformular tu consulta."
        )

    # Solo para testing: convierte ConversationState a dict plano para que los tests
    # puedan acceder a result["state"]["active_tool"], result["state"]["entities"], etc.
    # Uso: scratch_test_tool_flow_assertions.py, pages/2_🧪_Evaluacion.py (tab Integración)
    def _serialize_state(self, state: ConversationState) -> dict:
        return {
            "session_id": state.session_id,
            "current_topic": state.current_topic,
            "last_intent": state.last_intent,
            "last_confidence": state.last_confidence,
            "last_action": state.last_action,
            "menu_context": state.menu_context,
            "awaiting_clarification": state.awaiting_clarification,
            "active_tool": state.active_tool,
            "entities": state.entities,
        }
