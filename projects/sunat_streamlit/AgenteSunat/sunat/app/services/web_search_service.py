# app/services/web_search_service.py

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

ALLOWED_SITE = "sunat.gob.pe"
MAX_SNIPPET_CHARS = 300


class WebSearchService:
    """
    Busca en sunat.gob.pe usando DuckDuckGo. Solo se usa como fallback
    cuando el RAG no encuentra resultados en los documentos locales.
    """

    def search(self, query: str) -> Optional[str]:
        """
        Devuelve el snippet del primer resultado en sunat.gob.pe,
        truncado a MAX_SNIPPET_CHARS. Retorna None si falla o no encuentra.
        """
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            logger.warning("duckduckgo-search no instalado. Ejecuta: pip install duckduckgo-search")
            return None

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    f"site:{ALLOWED_SITE} {query}",
                    max_results=1,
                ))
            if not results:
                return None

            snippet = results[0].get("body", "").strip()
            if not snippet:
                return None

            return snippet[:MAX_SNIPPET_CHARS]

        except Exception as e:
            logger.debug("WebSearchService falló: %s", e)
            return None
