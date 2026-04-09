# app/services/rag_executor.py

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.services.llm_service import LLMService
from app.services.rag_service import RagService
from app.services.state_store import ConversationState
from app.services.web_search_service import WebSearchService

logger = logging.getLogger(__name__)

# Restringe la búsqueda vectorial a documentos relevantes por intención,
# evitando falsos positivos cuando la misma palabra aparece en varios PDFs.
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

FALLBACK_LINKS = (
    "Portal principal: sunat.gob.pe\n"
    "Orientación MYPES: emprender.sunat.gob.pe\n"
    "Central gratuita: 0-808-88-666"
)


class RagExecutor:
    """
    Busca en ChromaDB y genera la respuesta usando el LLM.
    Si no hay LLM disponible, devuelve los chunks directamente formateados.
    """

    def __init__(self, rag_service: RagService, llm_service: LLMService) -> None:
        self.rag_service = rag_service
        self.llm_service = llm_service
        self.web_search = WebSearchService()

    def answer(self, message: str, state: ConversationState) -> str:
        state.menu_context = "consulta_documental"

        if not self.rag_service.is_indexed():
            return (
                "Por el momento no tengo documentos cargados para responder esa consulta.\n\n"
                f"{FALLBACK_LINKS}"
            )

        intent = state.current_topic or ""
        source_filter: Optional[List[str]] = INTENT_TO_SOURCES.get(intent)

        MIN_SIMILARITY = 55  # chunks con menos del 55% de similitud se descartan

        results = self.rag_service.search(query=message, n_results=3, source_filter=source_filter)

        # Si con el filtro no encontramos nada, intentamos sin filtro
        if not results and source_filter:
            logger.info("Búsqueda filtrada vacía para '%s'. Reintentando sin filtro.", intent)
            results = self.rag_service.search(query=message, n_results=3)

        # Si el mejor resultado no es suficientemente similar, descartar
        if results and results[0]["similarity_pct"] < MIN_SIMILARITY:
            logger.info(
                "Mejor resultado tiene similitud %.1f%% < %d%%. Descartando para '%s'.",
                results[0]["similarity_pct"], MIN_SIMILARITY, intent,
            )
            results = []

        if not results:
            # Fallback: buscar en sunat.gob.pe antes de rendirse
            web_snippet = self.web_search.search(message)
            if web_snippet:
                logger.info("RAG sin resultados. Usando snippet de sunat.gob.pe como contexto.")
                return self._build_response(message, [], extra_context=web_snippet)
            return self._no_results_response()

        return self._build_response(message, results)

    # Solo para testing: variante de answer() que acepta contexto adicional
    # para evaluar búsquedas enriquecidas sin pasar por el flujo principal.
    # Uso: scripts/evaluate_rag.py u otros tests que necesiten inyectar contexto extra.
    def answer_with_context(
        self,
        message: str,
        state: ConversationState,
        extra_context: str = "",
    ) -> str:
        """Versión que acepta contexto adicional para enriquecer el query."""
        enriched_query = f"{message} {extra_context}".strip() if extra_context else message
        state.menu_context = "consulta_documental"

        if not self.rag_service.is_indexed():
            return f"Por el momento no tengo documentos cargados.\n\n{FALLBACK_LINKS}"

        results = self.rag_service.search(query=enriched_query)

        if not results:
            return self._no_results_response()

        return self._build_response(message, results, extra_context=extra_context)

    def _build_response(
        self,
        query: str,
        results: List[Dict[str, Any]],
        extra_context: str = "",
    ) -> str:
        chunks_text = [r["text"] for r in results]
        if extra_context:
            chunks_text.append(extra_context)

        fuentes_bloque = self._build_sources_block(results)
        if extra_context:
            fuentes_bloque += "\n- sunat.gob.pe (búsqueda web)"

        if self.llm_service.is_available():
            generated = self.llm_service.generate(query=query, context_chunks=chunks_text)
            if generated:
                return f"{generated}\n\n{fuentes_bloque}"

        # Sin LLM: mostramos los chunks directamente
        best = results[0]
        if len(results) == 1 or best["distance"] < 0.3:
            respuesta = self._format_single_result(query, best)
        else:
            respuesta = self._format_multiple_results(results)

        return f"{respuesta}\n\n{fuentes_bloque}"

    def _format_single_result(self, query: str, result: Dict[str, Any]) -> str:
        source = self._format_source_name(result["source"])
        return (
            f"Encontré información relevante:\n\n"
            f"{result['text']}\n\n"
            f"Fuente: {source} (relevancia: {result['similarity_pct']}%)"
        )

    def _format_multiple_results(self, results: List[Dict[str, Any]]) -> str:
        lines = ["Encontré información relevante en los documentos SUNAT:\n"]
        for i, result in enumerate(results, start=1):
            source = self._format_source_name(result["source"])
            lines.append(f"--- Sección {i} ({source}, relevancia: {result['similarity_pct']}%) ---")
            lines.append(result["text"])
            lines.append("")
        lines.append("Si necesitas más detalle, puedes preguntarme con más detalle.")
        return "\n".join(lines)

    def _no_results_response(self) -> str:
        return (
            "No encontré información suficiente en mis documentos para esa consulta.\n\n"
            "Puedes intentar reformular tu pregunta o consultar directamente:\n\n"
            f"{FALLBACK_LINKS}\n\n"
            "Puedo ayudarte con:\n"
            "• Regímenes tributarios (Nuevo RUS, RER, MYPE Tributario)\n"
            "• Multas, sanciones y cómo reducirlas\n"
            "• Comprobantes de pago y facturación electrónica\n"
            "• Formalización de negocios y RUC\n"
            "• Cronograma de vencimientos tributarios"
        )

    def _build_sources_block(self, results: List[Dict[str, Any]]) -> str:
        seen = set()
        lines = ["---", "**Fuentes consultadas:**"]
        for r in results:
            if r["source"] not in seen:
                seen.add(r["source"])
                lines.append(f"- {self._format_source_name(r['source'])}")
        return "\n".join(lines)

    def _format_source_name(self, filename: str) -> str:
        name_map = {
            "sunat_regimenes_tributarios": "Regímenes Tributarios",
            "sunat_formalizacion": "Formalización de Negocios",
            "sunat_multas_sanciones": "Multas y Sanciones",
            "sunat_comprobantes_pago": "Comprobantes de Pago",
            "sunat_cronograma_obligaciones": "Cronograma de Obligaciones",
        }
        stem = filename.rsplit(".", 1)[0]
        return name_map.get(stem, stem.replace("_", " ").title())
