# app/services/rag_service.py

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import chromadb
from chromadb.utils import embedding_functions

from app.core import config as cfg

logger = logging.getLogger(__name__)


class RagService:
    """
    Se encarga de todo lo relacionado a los documentos: cargarlos,
    dividirlos en chunks, indexarlos en ChromaDB y buscar luego.

    ChromaDB guarda los datos en disco así que no se re-indexa cada vez
    que se inicia la app.
    """

    def __init__(self) -> None:
        cfg.CHROMA_DIR.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=str(cfg.CHROMA_DIR))

        self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=cfg.EMBEDDING_MODEL
        )

        # hnsw:space=cosine → similitud coseno, mejor para comparar texto
        self._collection = self._client.get_or_create_collection(
            name=cfg.COLLECTION_NAME,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(
            "RagService inicializado. Colección '%s' tiene %d fragmentos.",
            cfg.COLLECTION_NAME,
            self._collection.count(),
        )

    def is_indexed(self) -> bool:
        return self._collection.count() > 0

    def index_documents(self, docs_dir: Optional[Path] = None) -> int:
        """
        Lee todos los .txt y .pdf de la carpeta de documentos y los indexa en ChromaDB.
        Usa upsert, así que no genera duplicados si se ejecuta varias veces.
        """
        target_dir = docs_dir or cfg.DOCS_DIR

        if not target_dir.exists():
            logger.warning("Directorio de documentos no encontrado: %s", target_dir)
            return 0

        all_files = list(target_dir.rglob("*.txt")) + list(target_dir.rglob("*.pdf"))

        if not all_files:
            logger.warning("No se encontraron documentos en %s", target_dir)
            return 0

        total_chunks = 0
        for file_path in all_files:
            try:
                added = self._index_single_file(file_path)
                total_chunks += added
                logger.info("Indexado: %s → %d fragmentos", file_path.name, added)
            except Exception as e:
                logger.error("Error indexando %s: %s", file_path.name, e)

        logger.info("Indexación completa. Total: %d fragmentos en %d archivos.", total_chunks, len(all_files))
        return total_chunks

    def search(
        self,
        query: str,
        n_results: int = cfg.TOP_K_RESULTS,
        source_filter: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Busca los chunks más parecidos al query.

        Trae más candidatos de los necesarios, filtra por distancia máxima
        y deduplica por archivo (máximo 1 resultado por documento).
        """
        if not self.is_indexed():
            return []

        CANDIDATE_MULTIPLIER = 5
        fetch_n = min(n_results * CANDIDATE_MULTIPLIER, self._collection.count())

        where_clause = (
            {"source": {"$in": list(source_filter)}} if source_filter else None
        )

        try:
            kwargs: Dict[str, Any] = dict(
                query_texts=[query],
                n_results=fetch_n,
                include=["documents", "metadatas", "distances"],
            )
            if where_clause:
                kwargs["where"] = where_clause

            results = self._collection.query(**kwargs)
        except Exception as e:
            logger.error("Error en búsqueda RAG: %s", e)
            return []

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        best_by_source: Dict[str, Dict[str, Any]] = {}

        for text, meta, distance in zip(documents, metadatas, distances):
            if distance > cfg.MAX_DISTANCE:
                continue

            source = meta.get("source", "desconocido")
            entry = {
                "text": text,
                "source": source,
                "distance": round(distance, 4),
                "chunk_index": meta.get("chunk_index", 0),
                "similarity_pct": round((1 - distance / 2) * 100, 1),
            }

            # Nos quedamos con el chunk más cercano por documento
            if source not in best_by_source or distance < best_by_source[source]["distance"]:
                best_by_source[source] = entry

        unique_results = sorted(best_by_source.values(), key=lambda x: x["distance"])
        return unique_results[:n_results]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "collection_name": cfg.COLLECTION_NAME,
            "total_chunks": self._collection.count(),
            "chroma_dir": str(cfg.CHROMA_DIR),
            "embedding_model": cfg.EMBEDDING_MODEL,
        }

    def _index_single_file(self, file_path: Path) -> int:
        text = self._load_file(file_path)
        if not text.strip():
            logger.warning("Archivo vacío o sin texto: %s", file_path.name)
            return 0

        chunks = self._chunk_text(text, cfg.CHUNK_SIZE, cfg.CHUNK_OVERLAP)
        if not chunks:
            return 0

        ids = [f"{file_path.stem}_{i}" for i in range(len(chunks))]
        metadatas = [
            {"source": file_path.name, "chunk_index": i, "total_chunks": len(chunks)}
            for i in range(len(chunks))
        ]

        self._collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)
        return len(chunks)

    def _load_file(self, file_path: Path) -> str:
        suffix = file_path.suffix.lower()
        if suffix == ".txt":
            return file_path.read_text(encoding="utf-8", errors="ignore")
        elif suffix == ".pdf":
            return self._extract_text_from_pdf(file_path)
        else:
            logger.warning("Tipo de archivo no soportado: %s", file_path.suffix)
            return ""

    def _extract_text_from_pdf(self, file_path: Path) -> str:
        """
        Extrae texto del PDF. Primero intenta con pymupdf4llm que maneja mejor
        tablas y columnas. Si falla, usa fitz como alternativa.
        """
        # Paso 1: pymupdf4llm — mejor calidad para PDFs con tablas
        # table_strategy="lines" evita el modelo ONNX que puede fallar en Windows
        try:
            import pymupdf4llm
            text = pymupdf4llm.to_markdown(str(file_path), table_strategy="lines")
            if text.strip():
                return text
        except ImportError:
            pass
        except Exception as e:
            logger.debug("pymupdf4llm falló en '%s' (%s). Usando fitz.", file_path.name, type(e).__name__)

        # Paso 2: fitz como fallback
        try:
            import fitz

            text_parts = []
            image_only_pages = []
            doc = fitz.open(str(file_path))

            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                if len(page_text.strip()) < 100 and page.get_images(full=False):
                    image_only_pages.append(page_num + 1)
                if page_text.strip():
                    text_parts.append(page_text)

            doc.close()

            if image_only_pages:
                logger.warning(
                    "'%s': páginas %s parecen ser imágenes y no se indexarán correctamente. "
                    "Instala pymupdf4llm para mejorar la extracción.",
                    file_path.name,
                    image_only_pages,
                )

            return "\n".join(text_parts)

        except ImportError:
            logger.error("PyMuPDF no instalado. Ejecuta: pip install pymupdf")
            return ""
        except Exception as e:
            logger.error("Error leyendo PDF %s: %s", file_path.name, e)
            return ""

    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """
        Divide el texto en chunks con un pequeño overlap entre ellos para
        no perder contexto cuando la respuesta está a caballo entre dos chunks.
        Intenta cortar en saltos de línea o espacios para no partir palabras.
        """
        if len(text) <= chunk_size:
            return [text.strip()] if text.strip() else []

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            if end < len(text):
                cut_pos = text.rfind("\n", start, end)
                if cut_pos == -1:
                    cut_pos = text.rfind(" ", start, end)
                if cut_pos > start:
                    end = cut_pos

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap
            if start <= (end - chunk_size):
                start = end

        return chunks
