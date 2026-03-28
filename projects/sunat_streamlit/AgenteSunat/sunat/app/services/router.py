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
    Decide qué acción tomar con cada mensaje: tool, RAG o pedir aclaración.

    Orden de prioridad:
    0. Si hay un flujo activo en el estado, continuarlo
    1. Confianza baja → pedir aclaración
    2. Intención con tool asignada + mensaje no informacional → activar tool
    3. Intención documental → RAG
    4. Contexto de aclaración previa → reutilizar tool del contexto
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

        # 0. Flujo activo: continuar la tool en curso
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

        # 1. Confianza baja
        if intent_result.confidence < LOW_CONFIDENCE_THRESHOLD:
            return RouteDecision(
                action=ACTION_CLARIFY,
                use_rag=False,
                use_tool=False,
                tool_name=None,
                needs_clarification=True,
                reason=f"Confianza baja ({intent_result.confidence:.2f}).",
            )

        # 2. Tool asignada → activar si es one-shot (siempre) o si no es informacional
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

        # 3. Intención documental → RAG
        if intent_result.intent in DOCUMENTAL_INTENTS:
            return RouteDecision(
                action=ACTION_USE_RAG,
                use_rag=True,
                use_tool=False,
                tool_name=None,
                needs_clarification=False,
                reason=f"Intención '{intent_result.intent}' → RAG.",
            )

        # 4. Reutilizar contexto de aclaración previa
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

        # 5. Fallback
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
        Determina si el mensaje busca información (→ RAG) o quiere iniciar
        un flujo guiado (→ tool/wizard).

        Usa el LLM si está disponible. Si no, cae en patrones hardcodeados.
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

        # Fallback: patrones hardcodeados
        text = message.lower().strip()

        # Verificar primero señales claras de PROCESO para cortocircuitar el check
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
