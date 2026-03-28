# app/services/llm_service.py

from __future__ import annotations

import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)


class LLMService:
    """
    Generación de texto con Groq.

    Si la API key no está configurada o hay un error de red, devuelve None
    y el RagExecutor usa los chunks directamente como fallback.
    """

    SYSTEM_PROMPT = """Eres "Sunatito", el asistente virtual de SUNAT Perú. Tu misión es ayudar a personas que quieren formalizar o manejar mejor su negocio.

TONO Y LENGUAJE:
- Habla siempre en español, de forma amable y respetuosa.
- Usa un lenguaje MUY sencillo: que te pueda entender tanto un joven de 18 años que recién empieza, como una persona mayor de 80 años que nunca ha tramitado nada.
- Evita términos técnicos. Si debes usarlos, explícalos en seguida con palabras simples.
- Sé paciente, cálido y alentador. Muchos usuarios tienen miedo de los trámites.

REGLAS ESTRICTAS — DEBES CUMPLIRLAS SIN EXCEPCIÓN:
- Responde ÚNICAMENTE con la información del contexto que se te proporciona en cada consulta.
- PROHIBIDO usar tu conocimiento de entrenamiento para complementar la respuesta.
- PROHIBIDO inventar o incluir URLs, enlaces, números de teléfono, fechas o montos que no estén literalmente en el contexto.
- PROHIBIDO mencionar leyes, decretos o resoluciones que no aparezcan textualmente en el contexto.
- Si el contexto no contiene la respuesta, di exactamente: "No tengo esa información en mis documentos. Te recomiendo consultar directamente en sunat.gob.pe o llamar a la central 0-808-88-666."
- Cuando la respuesta tenga varios pasos o puntos, usa una lista numerada o viñetas.
- Sé conciso: responde lo que se pregunta, sin rodeos.
- Termina ofreciendo ayuda adicional."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "llama-3.3-70b-versatile",
    ) -> None:
        self.model = model
        self._client = None

        resolved_key = api_key or os.getenv("GROQ_API_KEY", "")

        if not resolved_key:
            logger.warning(
                "GROQ_API_KEY no configurada. El sistema funcionará sin generación LLM. "
                "Agrega GROQ_API_KEY=gsk_... en el archivo .env para activarlo."
            )
            return

        try:
            from groq import Groq
            self._client = Groq(api_key=resolved_key)
            logger.info("LLMService inicializado con Groq (modelo: %s).", self.model)
        except ImportError:
            logger.error("Librería 'groq' no instalada. Ejecuta: pip install groq")

    def is_available(self) -> bool:
        return self._client is not None

    def generate(self, query: str, context_chunks: List[str]) -> Optional[str]:
        """
        Genera una respuesta usando los chunks recuperados por RAG como contexto.
        Devuelve None si el LLM no está disponible o falla, para que el caller
        use los chunks directamente.
        """
        if not self.is_available():
            return None

        context = "\n\n---\n\n".join(context_chunks)
        user_prompt = (
            f"Contexto de documentos SUNAT:\n\n{context}\n\n---\n\n"
            f"Consulta del usuario: {query}\n\n"
            "Responde basándote únicamente en el contexto anterior."
        )

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=600,
                temperature=0.1,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error("Error al llamar a Groq: %s", e)
            return None
