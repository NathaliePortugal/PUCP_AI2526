# app/services/rag_executor.py
"""
Ejecutor de consultas RAG (Retrieval-Augmented Generation).

Responsabilidades:
- Recibir el mensaje del usuario y el estado de la sesión.
- Delegar la búsqueda semántica al RagService.
- Formatear los resultados en una respuesta legible y útil para el usuario.

- RagService se encarga de la TÉCNICA (embeddings, ChromaDB, chunks).
- RagExecutor se encarga de la PRESENTACIÓN (formatear la respuesta al usuario).
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional

from app.services.llm_service import LLMService
from app.services.rag_service import RagService
from app.services.state_store import ConversationState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapeo intención → documentos relevantes
#
# Cuando la intención del usuario es conocida con alta confianza, restringimos
# la búsqueda vectorial a los documentos que realmente tratan ese tema.
# Esto evita falsos positivos semánticos: por ejemplo, "subsanación voluntaria"
# (término tributario) dejaba de recuperar la Guía de Infracciones porque el
# embedding de "voluntaria" era más cercano a "voluntariado" en el Libro de
# Cultura Tributaria.
#
# Cómo funciona:
# - rag_executor.answer() lee state.current_topic (seteado por el orquestador
#   con la intención clasificada).
# - Si hay un filtro definido para esa intención, lo pasa a rag_service.search()
#   como source_filter.
# - ChromaDB aplica un WHERE clause que restringe los candidatos a esas fuentes.
# - Si el filtro no da resultados (edge case: doc no indexado), el executor
#   reintenta sin filtro para no dejar al usuario sin respuesta.
# ---------------------------------------------------------------------------
INTENT_TO_SOURCES: Dict[str, List[str]] = {
    "multas_y_sanciones": [
        "Guia_infraciones-sanciones-tributarias_2023.pdf",
        "Libro-Cultura_Tributaria_y_Aduanera_final_0.pdf",
        "363257-remype-tributario.pdf",
    ],
    "formalizacion_negocio": [
        "cartilla_formalizacion_2020_PORTAL.pdf",
        "Libro-Cultura_Tributaria_y_Aduanera_final_0.pdf",
        "363257-remype-tributario.pdf",
    ],
    "regimenes_tributarios": [
        "Regímenes Tributarios _ Emprender.pdf",
        "Regímenes Tributarios _ EmprenderCompare.pdf",
        "Régimen MYPE Tributario _ Emprender.pdf",
        "363257-remype-tributario.pdf",
        "cartilla_formalizacion_2020_PORTAL.pdf",
        "Caso practico RMT1.pdf",
        "Libro-Cultura_Tributaria_y_Aduanera_final_0.pdf",
    ],
    "comprobantes_pago": [
        "PREGUNTAS FRECUENTES _ Comprobantes de Pago Electrónicos.pdf",
        "363257-remype-tributario.pdf",
        "cartilla_formalizacion_2020_PORTAL.pdf",
    ],
    "cronograma_obligaciones": [
        "Ayuda_621_IGV_Renta_Mensual.pdf",
        "ayuda_621_igv_renta_mensual_ccv.pdf",
        "363257-remype-tributario.pdf",
        "7577495-declaracion-jurada-anual.pdf",
        "Libro-Cultura_Tributaria_y_Aduanera_final_0.pdf",
    ],
    "declaraciones_impuestos": [
        "Ayuda_621_IGV_Renta_Mensual.pdf",
        "ayuda_621_igv_renta_mensual_ccv.pdf",
        "MODULOS INDEPENDIENTES.pdf",
        "7577495-declaracion-jurada-anual.pdf",
        "363257-remype-tributario.pdf",
        "Guia_infraciones-sanciones-tributarias_2023.pdf",
    ],
}


class RagExecutor:
    """
    Ejecuta consultas documentales usando el pipeline RAG real.

    Recibe la consulta del usuario → busca en ChromaDB → formatea respuesta.

    Sin LLM: devuelve directamente los fragmentos más relevantes.
    Este enfoque funciona muy bien para Q&A sobre documentos estructurados
    como los de SUNAT, donde la información está clara y ordenada.
    """

    def __init__(self, rag_service: RagService, llm_service: LLMService) -> None:
        """
        Args:
            rag_service: instancia del servicio RAG (búsqueda en ChromaDB).
            llm_service: instancia del LLM (generación con Groq).
                         Si Groq no está configurado, el ejecutor devuelve
                         los chunks directamente (modo sin generación).
        """
        self.rag_service = rag_service
        self.llm_service = llm_service

    def answer(self, message: str, state: ConversationState) -> str:
        """
        Responde una consulta documental usando RAG.

        Flujo:
        1. Verifica que haya documentos indexados.
        2. Busca los fragmentos más relevantes para el mensaje.
        3. Formatea y devuelve la respuesta.

        Args:
            message: pregunta del usuario.
            state: estado de la conversación (para enriquecer contexto si es necesario).

        Returns:
            Texto de respuesta formateado para mostrar al usuario.
        """
        # Actualizar el contexto del estado para que el router sepa en qué tema estamos
        state.menu_context = "consulta_documental"

        # Verificar que haya documentos para buscar
        if not self.rag_service.is_indexed():
            return (
                "Por el momento no tengo documentos cargados para responder esa consulta.\n\n"
                "Mientras tanto, puedes consultar directamente en el portal oficial:\n\n"
                "Portal SUNAT: sunat.gob.pe\n"
                "Orientación para MYPES: emprender.sunat.gob.pe\n"
                "Central gratuita: 0-808-88-666"
            )

        # Búsqueda con filtro de fuentes según la intención detectada.
        # Si la intención está mapeada, restringimos la búsqueda a los documentos
        # relevantes para ese dominio, evitando falsos positivos semánticos.
        # Si el filtro no devuelve resultados (edge case), reintentamos sin filtro.
        intent = state.current_topic or ""
        source_filter: Optional[List[str]] = INTENT_TO_SOURCES.get(intent)

        results = self.rag_service.search(
            query=message,
            n_results=3,
            source_filter=source_filter,
        )

        # Si la búsqueda filtrada no dio resultados, reintentamos sin filtro
        if not results and source_filter:
            logger.info(
                "Búsqueda filtrada por intención '%s' sin resultados. Reintentando sin filtro.",
                intent,
            )
            results = self.rag_service.search(query=message, n_results=3)

        # Si no encontramos nada relevante, dar respuesta de fallback
        if not results:
            return self._build_no_results_response(message)

        # Construir la respuesta con los fragmentos encontrados
        return self._build_response(message, results)

    def answer_with_context(
        self,
        message: str,
        state: ConversationState,
        extra_context: str = "",
    ) -> str:
        """
        Versión extendida de answer() que permite pasar contexto adicional.

        Útil para las tools: después de completar el flujo guiado (ej. regímenes),
        pasan el contexto de las respuestas del usuario para refinar la búsqueda.

        Args:
            message: consulta del usuario (o resumen del flujo completado).
            state: estado de la conversación.
            extra_context: texto adicional para enriquecer el query de búsqueda.

        Returns:
            Respuesta formateada.
        """
        # Enriquece el query con el contexto adicional para mejores resultados
        enriched_query = f"{message} {extra_context}".strip() if extra_context else message

        state.menu_context = "consulta_documental"

        if not self.rag_service.is_indexed():
            return (
                "Por el momento no tengo documentos cargados para responder esa consulta.\n\n"
                "Consulta directamente en: sunat.gob.pe\n"
                "Orientación MYPES: emprender.sunat.gob.pe"
            )

        results = self.rag_service.search(query=enriched_query)

        if not results:
            return self._build_no_results_response(message)

        return self._build_response(message, results, extra_context=extra_context)

    # ------------------------------------------------------------------
    # Métodos privados de formateo
    # ------------------------------------------------------------------

    def _build_response(
        self,
        query: str,
        results: List[Dict[str, Any]],
        extra_context: str = "",
    ) -> str:
        """
        Construye la respuesta final.

        Estrategia con LLM disponible:
        - Pasa los chunks al LLM (Groq) para generar una respuesta natural y coherente.
        - Agrega la fuente al pie de la respuesta.

        Estrategia sin LLM (fallback):
        - Devuelve los chunks directamente formateados.
        """
        chunks_text = [r["text"] for r in results]
        fuentes = list({r["source"] for r in results})
        fuentes_str = ", ".join(self._format_source_name(f) for f in fuentes)

        # Construir el bloque de fuentes que se agrega al pie de TODA respuesta RAG.
        # Muestra el nombre legible Y el nombre del archivo para transparencia.
        fuentes_bloque = self._build_sources_block(results)

        # --- Intentar generar con LLM ---
        if self.llm_service.is_available():
            generated = self.llm_service.generate(query=query, context_chunks=chunks_text)
            if generated:
                return f"{generated}\n\n{fuentes_bloque}"

        # --- Fallback sin LLM: devolver chunks formateados directamente ---
        best_result   = results[0]
        best_distance = best_result["distance"]

        if len(results) == 1 or best_distance < 0.3:
            respuesta = self._format_single_result(query, best_result)
        else:
            respuesta = self._format_multiple_results(query, results)

        return f"{respuesta}\n\n{fuentes_bloque}"

    def _format_single_result(self, query: str, result: Dict[str, Any]) -> str:
        """
        Formatea una respuesta cuando hay un resultado muy relevante.
        """
        source = self._format_source_name(result["source"])
        text = result["text"]
        similarity = result["similarity_pct"]

        return (
            f"Encontré información relevante para tu consulta:\n\n"
            f"{text}\n\n"
            f"Fuente: {source} (relevancia: {similarity}%)"
        )

    def _format_multiple_results(self, query: str, results: List[Dict[str, Any]]) -> str:
        """
        Formatea una respuesta cuando hay múltiples fragmentos complementarios.
        Los muestra como secciones ordenadas por relevancia.
        """
        lines = ["Encontré información relevante en los documentos SUNAT:\n"]

        for i, result in enumerate(results, start=1):
            source = self._format_source_name(result["source"])
            text = result["text"]
            similarity = result["similarity_pct"]

            lines.append(f"--- Sección {i} ({source}, relevancia: {similarity}%) ---")
            lines.append(text)
            lines.append("")  # línea en blanco entre secciones

        lines.append(
            "Si necesitas más detalle sobre algún punto específico, "
            "puedes preguntarme con más detalle."
        )

        return "\n".join(lines)

    def _build_no_results_response(self, query: str) -> str:
        """
        Respuesta cuando no se encontraron resultados relevantes en los documentos.
        Es honesta sobre la limitación y orienta al usuario a fuentes oficiales.
        """
        return (
            f"No encontré información suficiente sobre eso en mis documentos disponibles.\n\n"
            "Te recomiendo consultar directamente en el portal oficial de SUNAT:\n\n"
            "Portal principal: sunat.gob.pe\n"
            "Orientación tributaria: emprender.sunat.gob.pe\n"
            "También puedes intentar reformular tu pregunta. Puedo ayudarte con:\n"
            "• Regímenes tributarios (Nuevo RUS, RER, MYPE Tributario)\n"
            "• Multas, sanciones y cómo reducirlas\n"
            "• Comprobantes de pago y facturación electrónica\n"
            "• Formalización de negocios y RUC\n"
            "• Cronograma de vencimientos tributarios"
        )

    def _build_sources_block(self, results: List[Dict[str, Any]]) -> str:
        """
        Construye el bloque "Fuentes consultadas" que se muestra al pie
        de cada respuesta RAG.

        Muestra nombre legible + nombre del archivo para transparencia total.
        Si varios chunks vienen del mismo archivo, aparece solo una vez.
        """
        # Deduplicar por nombre de archivo manteniendo el orden de relevancia
        seen = set()
        lineas = ["Fuentes consultadas:"]

        for r in results:
            filename = r["source"]
            if filename in seen:
                continue
            seen.add(filename)

            nombre_legible = self._format_source_name(filename)
            lineas.append(f"   • {nombre_legible}  ({filename})")

        return "\n".join(lineas)

    def _format_source_name(self, filename: str) -> str:
        """
        Convierte el nombre del archivo en algo más legible para el usuario.

        Ejemplo: "sunat_regimenes_tributarios.txt" → "Regímenes Tributarios"
        """
        # Mapeo de nombres de archivo a etiquetas amigables
        name_map = {
            "sunat_regimenes_tributarios": "Regímenes Tributarios",
            "sunat_formalizacion": "Formalización de Negocios",
            "sunat_multas_sanciones": "Multas y Sanciones",
            "sunat_comprobantes_pago": "Comprobantes de Pago",
            "sunat_cronograma_obligaciones": "Cronograma de Obligaciones",
        }

        # Quitar extensión y buscar en el mapa
        stem = filename.rsplit(".", 1)[0]  # remueve extensión
        return name_map.get(stem, stem.replace("_", " ").title())
