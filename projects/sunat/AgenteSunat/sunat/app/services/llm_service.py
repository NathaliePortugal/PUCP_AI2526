# app/services/llm_service.py
"""
Servicio de generación de texto con Groq (LLM gratuito en la nube).

Modelo por defecto: llama-3.1-8b-instant
- Alternativas: "gemma2-9b-it" o "llama-3.3-70b-versatile" (más preciso pero más lento).
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)


class LLMService:
    """
    Genera respuestas en lenguaje natural usando Groq como proveedor LLM.

    Si la API key no está configurada o hay un error de red, cae en modo
    "sin generación": devuelve None para que el RagExecutor use los chunks directos.

    Esto hace al sistema resiliente: funciona con o sin LLM.
    """

    # Prompt del sistema que define el rol y comportamiento del asistente.
    SYSTEM_PROMPT = """Eres "Sunatito", el asistente virtual de SUNAT Perú. Tu misión es ayudar a personas que quieren formalizar o manejar mejor su negocio.

TONO Y LENGUAJE:
- Habla siempre en español, de forma amable y respetuosa.
- Usa un lenguaje MUY sencillo: que te pueda entender tanto un joven de 18 años que recién empieza, como una persona mayor de 80 años que nunca ha tramitado nada.
- Evita términos técnicos. Si debes usarlos, explícalos en seguida con palabras simples.
- Sé paciente, cálido y alentador. Muchos usuarios tienen miedo de los trámites.
- Saluda con amabilidad cuando sea el primer mensaje.

CÓMO RESPONDER:
- Responde ÚNICAMENTE con la información del contexto que se te proporciona.
- Si el contexto no tiene la respuesta, dilo con honestidad: "No tengo esa información en mis documentos, pero puedes consultarlo en sunat.gob.pe".
- NUNCA inventes cifras, fechas, montos ni nombres de leyes que no estén en el contexto.
- Cuando la respuesta tenga varios pasos o puntos, usa una lista numerada o viñetas para que sea fácil de seguir.
- Sé conciso: responde lo que se pregunta, sin dar rodeos innecesarios.
- Termina siempre ofreciendo ayuda adicional si la necesitan."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "llama-3.1-8b-instant",
    ) -> None:
        """
        Args:
            api_key: API key de Groq. Si no se pasa, la lee de la variable
                     de entorno GROQ_API_KEY.
            model:   nombre del modelo a usar. Opciones gratuitas:
                     - "llama-3.1-8b-instant"  (rápido, buena calidad)
                     - "gemma2-9b-it"           (alternativa Google)
                     - "llama-3.3-70b-versatile" (mejor calidad, más lento)
        """
        self.model = model
        self._client = None  # se inicializa solo si hay API key

        # Intentar obtener la API key
        resolved_key = api_key or os.getenv("GROQ_API_KEY", "")

        if not resolved_key:
            logger.warning(
                "GROQ_API_KEY no configurada. El sistema funcionará sin generación LLM "
                "(devuelve los chunks directamente). "
                "Para activar Groq, agrega GROQ_API_KEY=gsk_... en un archivo .env "
                "o como variable de entorno."
            )
            return

        try:
            from groq import Groq
            self._client = Groq(api_key=resolved_key)
            logger.info("LLMService inicializado con Groq (modelo: %s).", self.model)
        except ImportError:
            logger.error(
                "Librería 'groq' no instalada. Ejecuta: pip install groq"
            )

    def is_available(self) -> bool:
        """Indica si el LLM está disponible para generar respuestas."""
        return self._client is not None

    def generate(self, query: str, context_chunks: List[str]) -> Optional[str]:
        """
        Genera una respuesta en lenguaje natural usando el contexto recuperado por RAG.

        Args:
            query:          pregunta original del usuario.
            context_chunks: lista de fragmentos de documentos recuperados por ChromaDB.

        Returns:
            Texto generado por el LLM, o None si el LLM no está disponible o falla.
            Cuando devuelve None, el RagExecutor usará los chunks directamente.
        """
        if not self.is_available():
            return None

        # Unir los chunks en un bloque de contexto
        context = "\n\n---\n\n".join(context_chunks)

        # Prompt del usuario con la consulta y el contexto
        user_prompt = f"""Contexto de documentos SUNAT:

{context}

---

Consulta del usuario: {query}

Responde basándote únicamente en el contexto anterior."""

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
                max_tokens=600,    # respuestas concisas para un chatbot
                temperature=0.1,   # baja temperatura = respuestas más precisas y consistentes sin alucinar
            )
            generated_text = response.choices[0].message.content
            logger.debug("Groq generó respuesta (%d chars).", len(generated_text))
            return generated_text

        except Exception as e:
            logger.error("Error al llamar a Groq: %s. Usando chunks directos.", e)
            return None  # fallback silencioso a modo sin LLM
