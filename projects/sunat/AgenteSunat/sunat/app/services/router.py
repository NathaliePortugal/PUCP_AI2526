from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from app.core.constants import (
    ACTION_CLARIFY,
    ACTION_USE_RAG,
    ACTION_USE_TOOL,
    DOCUMENTAL_INTENTS,
    LOW_CONFIDENCE_THRESHOLD,
    TOOL_INTENT_TO_NAME,
)
from app.schemas.nlu import IntentResult, RouteDecision
from app.services.state_store import ConversationState

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ConversationRouter:
    """
    Router conversacional para intents temáticos.

    Responsabilidades:
    - decidir la acción técnica a partir de:
      * intención detectada
      * score de confianza
      * estado conversacional

    No debe:
    - ejecutar RAG
    - llamar tools directamente
    - generar la respuesta final
    """

    def __init__(self, llm_service: Optional["LLMService"] = None) -> None:
        self._llm = llm_service

    def decide(
        self,
        message: str,
        intent_result: IntentResult,
        state: ConversationState
    ) -> RouteDecision:
        """
        Decide la ruta técnica del mensaje.
        """

        # 0. Si existe un flujo activo, priorizar continuidad conversacional.
        active_tool = self._resolve_active_tool_from_state(state)
        if active_tool:
            return RouteDecision(
                action=ACTION_USE_TOOL,
                use_rag=False,
                use_tool=True,
                tool_name=active_tool,
                needs_clarification=False,
                reason=(
                    f"Existe un flujo activo en el estado conversacional. "
                    f"Se continúa con la tool '{active_tool}'."
                ),
            )

        # 1. Si la confianza es baja, pedir aclaración.
        if intent_result.confidence < LOW_CONFIDENCE_THRESHOLD:
            return RouteDecision(
                action=ACTION_CLARIFY,
                use_rag=False,
                use_tool=False,
                tool_name=None,
                needs_clarification=True,
                reason=(
                    f"Confianza baja en la clasificación ({intent_result.confidence:.2f}). "
                    "Se requiere aclaración antes de continuar."
                ),
            )

        # 2. Si existe una tool específica para esta intención, usarla.
        #    EXCEPCIÓN: si el mensaje es una pregunta informacional/definitoria
        #    ("qué es", "qué significa", "explícame", etc.) se manda al RAG aunque
        #    la intención tenga tool asignada. El usuario quiere información, no un flujo.
        tool_name = self._resolve_tool_name(intent_result.intent)
        if tool_name and not self._is_informational_query(message):
            return RouteDecision(
                action=ACTION_USE_TOOL,
                use_rag=False,
                use_tool=True,
                tool_name=tool_name,
                needs_clarification=False,
                reason=(
                    f"La intención '{intent_result.intent}' está asociada a la tool "
                    f"'{tool_name}'."
                ),
            )

        # 3. Si es una intención documental, usar RAG.
        if intent_result.intent in DOCUMENTAL_INTENTS:
            return RouteDecision(
                action=ACTION_USE_RAG,
                use_rag=True,
                use_tool=False,
                tool_name=None,
                needs_clarification=False,
                reason=(
                    f"La intención '{intent_result.intent}' requiere recuperación "
                    "documental con RAG."
                ),
            )

        # 4. Si el sistema estaba esperando aclaración, intentar reutilizar contexto previo.
        fallback_tool = self._resolve_tool_from_clarification_context(state)
        if fallback_tool:
            return RouteDecision(
                action=ACTION_USE_TOOL,
                use_rag=False,
                use_tool=True,
                tool_name=fallback_tool,
                needs_clarification=False,
                reason=(
                    f"Se reutiliza el contexto previo de aclaración con la tool "
                    f"'{fallback_tool}'."
                ),
            )

        # 5. Fallback sano: si no encaja, pedir aclaración.
        return RouteDecision(
            action=ACTION_CLARIFY,
            use_rag=False,
            use_tool=False,
            tool_name=None,
            needs_clarification=True,
            reason=(
                f"No se encontró una ruta válida para la intención "
                f"'{intent_result.intent}'. Se solicita aclaración."
            ),
        )

    def _resolve_active_tool_from_state(
        self,
        state: ConversationState
    ) -> Optional[str]:
        """
        Si existe un flujo activo en la conversación, devuelve la tool a continuar.
        """
        if state.active_tool:
            return state.active_tool

        return None

    def _resolve_tool_name(
        self,
        intent: str
    ) -> Optional[str]:
        """
        Resuelve si una intención debe activar una tool especializada.
        """
        return TOOL_INTENT_TO_NAME.get(intent)

    def _is_informational_query(self, message: str) -> bool:
        """
        Detecta si el mensaje busca información (explicación, listado, beneficios)
        en lugar de iniciar un flujo guiado (wizard/tool).

        Si devuelve True, el router manda el mensaje a RAG aunque la intención
        tenga una tool asignada, porque el usuario quiere información, no un wizard.

        Estrategia:
        - Primero intenta clasificar con el LLM (más robusto, no requiere mantenimiento).
        - Si el LLM no está disponible, cae en la detección por patrones (hardcode).
        """
        # --- Detección con LLM (preferida) -----------------------------------
        if self._llm and self._llm.is_available():
            try:
                result = self._llm._client.chat.completions.create(
                    model=self._llm.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Eres un clasificador de intenciones. "
                                "Tu única tarea es decidir si un mensaje de usuario "
                                "busca INFORMACIÓN (quiere una explicación, lista, "
                                "beneficios, requisitos o descripción de algo) "
                                "o quiere INICIAR UN PROCESO (hacer un trámite, "
                                "obtener una guía paso a paso personalizada, registrarse). "
                                "Responde únicamente con una sola palabra: "
                                "INFORMACIONAL o PROCESO"
                            ),
                        },
                        {"role": "user", "content": message},
                    ],
                    max_tokens=5,
                    temperature=0.0,
                )
                answer = result.choices[0].message.content.strip().upper()
                is_info = answer.startswith("INFORMACIONAL")
                logger.debug(
                    "LLM clasificó '%s' como %s",
                    message[:60],
                    "INFORMACIONAL" if is_info else "PROCESO",
                )
                return is_info
            except Exception as e:
                logger.debug("LLM no disponible para clasificar query (%s). Usando patrones.", e)

        # --- Fallback: detección por patrones hardcodeados -------------------
        # NOTA: Este enfoque fue el punto de partida. Se dejó como fallback
        # porque requiere mantenimiento manual cada vez que aparece un nuevo
        # patrón no contemplado. El LLM de arriba lo reemplaza de forma más
        # robusta y generalizable.
        text = message.lower().strip()
        informational_patterns = [
            "qué es", "que es",
            "qué son", "que son",
            "qué significa", "que significa",
            "cómo funciona", "como funciona",
            "explícame", "explicame",
            "cuéntame", "cuentame",
            "información sobre", "informacion sobre",
            "qué diferencia", "que diferencia",
            "en qué consiste", "en que consiste",
            "qué implica", "que implica",
            "qué incluye", "que incluye",
            "cómo se define", "como se define",
            "cuáles son", "cuales son",
            "cuál es", "cual es",
            "qué beneficios", "que beneficios",
            "qué ventajas", "que ventajas",
            "qué requisitos", "que requisitos",
            "qué documentos", "que documentos",
            "cuántos son", "cuantos son",
        ]
        return any(text.startswith(p) or f" {p} " in text for p in informational_patterns)

    def _resolve_tool_from_clarification_context(
        self,
        state: ConversationState
    ) -> Optional[str]:
        """
        Si el sistema estaba esperando aclaración y existe un tema previo
        asociado a una tool, reusa ese contexto.
        """
        if (
            state.awaiting_clarification
            and state.current_topic in TOOL_INTENT_TO_NAME
        ):
            return TOOL_INTENT_TO_NAME[state.current_topic]

        return None