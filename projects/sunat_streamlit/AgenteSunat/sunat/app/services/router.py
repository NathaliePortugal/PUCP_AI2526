from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from app.core.constants import (
    ACTION_CLARIFY,
    ACTION_USE_RAG,
    ACTION_USE_TOOL,
    DOCUMENTAL_INTENTS,
    LOW_CONFIDENCE_THRESHOLD,
    ONE_SHOT_TOOL_INTENTS,
    TOOL_INTENT_TO_NAME,
)
from app.schemas.nlu import IntentResult, RouteDecision
from app.services.state_store import ConversationState

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ConversationRouter:
    """
    Decide qué hacer con cada mensaje: lanzar un wizard (tool),
    buscar en documentos (RAG) o pedir aclaración al usuario.

    Orden de prioridad:
    0. Si hay un wizard activo, seguir con él
    1. Confianza muy baja → pedir aclaración
    2. Intent tiene wizard asignado y el mensaje pide un proceso → activar wizard
    3. Intent documental → buscar en RAG
    4. Si estaba esperando aclaración, reutilizar contexto anterior
    5. Fallback → pedir aclaración
    """

    def __init__(self, llm_service: Optional["LLMService"] = None) -> None:
        self._llm = llm_service

    def decide(
        self,
        message: str,
        intent_result: IntentResult,
        state: ConversationState,
    ) -> RouteDecision:

        # 0. Si hay un wizard en curso, seguir con él sin importar el intent
        active_tool = state.active_tool
        if active_tool:
            return RouteDecision(
                action=ACTION_USE_TOOL,
                use_rag=False,
                use_tool=True,
                tool_name=active_tool,
                needs_clarification=False,
                reason=f"Flujo activo: continuando tool '{active_tool}'.",
            )

        # 1. Confianza muy baja → no sabemos de qué está hablando el usuario
        if intent_result.confidence < LOW_CONFIDENCE_THRESHOLD:
            return RouteDecision(
                action=ACTION_CLARIFY,
                use_rag=False,
                use_tool=False,
                tool_name=None,
                needs_clarification=True,
                reason=f"Confianza baja ({intent_result.confidence:.2f}).",
            )

        # 2. Si el intent tiene wizard y el usuario quiere iniciar un proceso
        tool_name = TOOL_INTENT_TO_NAME.get(intent_result.intent)
        is_one_shot = intent_result.intent in ONE_SHOT_TOOL_INTENTS
        if tool_name and (is_one_shot or not self._is_informational_query(message)):
            return RouteDecision(
                action=ACTION_USE_TOOL,
                use_rag=False,
                use_tool=True,
                tool_name=tool_name,
                needs_clarification=False,
                reason=f"Intención '{intent_result.intent}' → tool '{tool_name}'.",
            )

        # 3. Intent documental → buscar en los PDFs de SUNAT
        if intent_result.intent in DOCUMENTAL_INTENTS:
            return RouteDecision(
                action=ACTION_USE_RAG,
                use_rag=True,
                use_tool=False,
                tool_name=None,
                needs_clarification=False,
                reason=f"Intención '{intent_result.intent}' → RAG.",
            )

        # 4. Si estábamos esperando aclaración, intentar reutilizar el contexto
        fallback_tool = self._resolve_tool_from_clarification_context(state)
        if fallback_tool:
            return RouteDecision(
                action=ACTION_USE_TOOL,
                use_rag=False,
                use_tool=True,
                tool_name=fallback_tool,
                needs_clarification=False,
                reason=f"Reutilizando contexto previo → tool '{fallback_tool}'.",
            )

        # 5. No se pudo determinar nada con certeza
        return RouteDecision(
            action=ACTION_CLARIFY,
            use_rag=False,
            use_tool=False,
            tool_name=None,
            needs_clarification=True,
            reason=f"Sin ruta válida para '{intent_result.intent}'.",
        )

    def _is_informational_query(self, message: str) -> bool:
        """
        Detecta si el usuario quiere información (→ RAG) o quiere iniciar
        un wizard guiado (→ tool).

        Usa el LLM si está disponible. Si no, cae en una lista de patrones.
        """
        if self._llm and self._llm.is_available():
            try:
                result = self._llm._client.chat.completions.create(
                    model=self._llm.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Eres un clasificador para un chatbot tributario de SUNAT Perú. "
                                "Decide si el mensaje del usuario quiere INFORMACIÓN "
                                "o quiere INICIAR UN ASISTENTE INTERACTIVO.\n\n"
                                "PROCESO — el usuario quiere que el chatbot le haga "
                                "preguntas guiadas para generar un resultado personalizado. "
                                "Señales claras: 'quiero iniciar', 'iniciar la guía', "
                                "'ayúdame a elegir', 'quiero formalizar mi negocio', "
                                "'quiero empezar', 'necesito que me ayudes paso a paso'.\n\n"
                                "INFORMACIONAL — el usuario quiere una explicación, "
                                "definición, lista de pasos, requisitos o descripción. "
                                "Señales claras: 'qué es', 'cómo funciona', 'cómo me inscribo', "
                                "'qué documentos', 'cuáles son', 'dónde', 'cuánto cuesta', "
                                "'cómo se hace', 'qué pasos'.\n\n"
                                "EN CASO DE DUDA, responde INFORMACIONAL.\n\n"
                                "Responde únicamente con una sola palabra: INFORMACIONAL o PROCESO"
                            ),
                        },
                        {"role": "user", "content": message},
                    ],
                    max_tokens=5,
                    temperature=0.0,
                )
                answer = result.choices[0].message.content.strip().upper()
                is_info = answer.startswith("INFORMACIONAL")
                logger.debug("LLM clasificó '%s' como %s", message[:60], "INFORMACIONAL" if is_info else "PROCESO")
                return is_info
            except Exception as e:
                logger.debug("LLM no disponible para clasificar (%s). Usando patrones.", e)

        # Fallback cuando no hay LLM disponible
        text = message.lower().strip()

        process_patterns = [
            "quiero iniciar", "iniciar la guía", "iniciar guía",
            "ayúdame a elegir", "ayudame a elegir",
            "quiero formalizar mi negocio",
            "quiero empezar",
            "iniciar el asistente",
        ]
        if any(text.startswith(p) or p in text for p in process_patterns):
            return False

        informational_patterns = [
            "qué es", "que es",
            "qué son", "que son",
            "qué significa", "que significa",
            "cómo funciona", "como funciona",
            "cómo me", "como me",
            "cómo puedo", "como puedo",
            "cómo se hace", "como se hace",
            "cómo hago", "como hago",
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
            "dónde", "donde",
            "cuánto cuesta", "cuanto cuesta",
            "qué pasos", "que pasos",
        ]
        return any(text.startswith(p) or f" {p} " in text for p in informational_patterns)

    def _resolve_tool_from_clarification_context(
        self,
        state: ConversationState,
    ) -> Optional[str]:
        if state.awaiting_clarification and state.current_topic in TOOL_INTENT_TO_NAME:
            return TOOL_INTENT_TO_NAME[state.current_topic]
        return None
