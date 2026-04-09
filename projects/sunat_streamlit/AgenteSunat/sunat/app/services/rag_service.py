# app/services/rag_service.py

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import re

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from app.core import config as cfg

logger = logging.getLogger(__name__)

_INDEX_FILE = "faiss.index"
_META_FILE = "faiss_meta.pkl"


class RagService:
    """Gestiona la carga, chunking, indexación en FAISS y búsqueda de documentos."""

    def __init__(self) -> None:
        cfg.INDEX_DIR.mkdir(parents=True, exist_ok=True)

        self._index_path = cfg.INDEX_DIR / _INDEX_FILE
        self._meta_path = cfg.INDEX_DIR / _META_FILE

        self._model = SentenceTransformer(cfg.EMBEDDING_MODEL)
        self._dim = self._model.get_sentence_embedding_dimension()

        self._documents: List[str] = []
        self._metadatas: List[Dict[str, Any]] = []
        self._index: faiss.IndexFlatIP = faiss.IndexFlatIP(self._dim)

        self._load_index()

        logger.info(
            "RagService inicializado. Índice FAISS tiene %d fragmentos.",
            self._index.ntotal,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_indexed(self) -> bool:
        return self._index.ntotal > 0

    def index_documents(self, docs_dir: Optional[Path] = None) -> int:
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

        self._save_index()
        logger.info("Indexación completa. Total: %d fragmentos en %d archivos.", total_chunks, len(all_files))
        return total_chunks

    def search(
        self,
        query: str,
        n_results: int = cfg.TOP_K_RESULTS,
        source_filter: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        if not self.is_indexed():
            return []

        query_vec = self._embed([query])  # (1, dim) normalized
        fetch_n = min(n_results * 5, self._index.ntotal)

        scores, indices = self._index.search(query_vec, fetch_n)
        scores = scores[0]
        indices = indices[0]

        source_set = set(source_filter) if source_filter else None
        best_by_source: Dict[str, Dict[str, Any]] = {}

        for score, idx in zip(scores, indices):
            if idx == -1:
                continue

            # Convertir similitud coseno → distancia coseno (igual que chromadb)
            distance = float(1.0 - score)

            if distance > cfg.MAX_DISTANCE:
                continue

            meta = self._metadatas[idx]
            source = meta.get("source", "desconocido")

            if source_set and source not in source_set:
                continue

            entry = {
                "text": self._documents[idx],
                "source": source,
                "distance": round(distance, 4),
                "chunk_index": meta.get("chunk_index", 0),
                "similarity_pct": round((1 - distance / 2) * 100, 1),
            }

            if source not in best_by_source or distance < best_by_source[source]["distance"]:
                best_by_source[source] = entry

        unique_results = sorted(best_by_source.values(), key=lambda x: x["distance"])
        return unique_results[:n_results]

    def clear(self) -> None:
        """Elimina todos los fragmentos del índice y borra los archivos persistidos."""
        self._index = faiss.IndexFlatIP(self._dim)
        self._documents = []
        self._metadatas = []
        if self._index_path.exists():
            self._index_path.unlink()
        if self._meta_path.exists():
            self._meta_path.unlink()
        logger.info("Índice FAISS limpiado.")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "collection_name": cfg.COLLECTION_NAME,
            "total_chunks": self._index.ntotal,
            "index_dir": str(cfg.INDEX_DIR),
            "embedding_model": cfg.EMBEDDING_MODEL,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _embed(self, texts: List[str]) -> np.ndarray:
        vecs = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return vecs.astype(np.float32)

    def _index_single_file(self, file_path: Path) -> int:
        text = self._load_file(file_path)
        if not text.strip():
            logger.warning("Archivo vacío o sin texto: %s", file_path.name)
            return 0

        chunks = self._chunk_text(text, cfg.CHUNK_SIZE, cfg.CHUNK_OVERLAP)
        if not chunks:
            return 0

        # Remove existing chunks for this file (upsert behaviour)
        self._remove_by_source(file_path.name)

        vecs = self._embed(chunks)
        self._index.add(vecs)

        for i, chunk in enumerate(chunks):
            self._documents.append(chunk)
            self._metadatas.append({
                "source": file_path.name,
                "chunk_index": i,
                "total_chunks": len(chunks),
            })

        return len(chunks)

    def _remove_by_source(self, source_name: str) -> None:
        """Elimina todos los fragmentos de un archivo para permitir re-indexación."""
        keep_indices = [
            i for i, m in enumerate(self._metadatas) if m.get("source") != source_name
        ]
        if len(keep_indices) == len(self._metadatas):
            return  # Nothing to remove

        kept_docs = [self._documents[i] for i in keep_indices]
        kept_meta = [self._metadatas[i] for i in keep_indices]

        if kept_docs:
            kept_vecs = self._embed(kept_docs)
        else:
            kept_vecs = np.empty((0, self._dim), dtype=np.float32)

        self._index = faiss.IndexFlatIP(self._dim)
        if len(kept_vecs) > 0:
            self._index.add(kept_vecs)

        self._documents = kept_docs
        self._metadatas = kept_meta

    def _save_index(self) -> None:
        faiss.write_index(self._index, str(self._index_path))
        with open(self._meta_path, "wb") as f:
            pickle.dump({"documents": self._documents, "metadatas": self._metadatas}, f)

    def _load_index(self) -> None:
        if self._index_path.exists() and self._meta_path.exists():
            try:
                self._index = faiss.read_index(str(self._index_path))
                with open(self._meta_path, "rb") as f:
                    data = pickle.load(f)
                self._documents = data["documents"]
                self._metadatas = data["metadatas"]
                logger.info("Índice FAISS cargado desde disco (%d fragmentos).", self._index.ntotal)
            except Exception as e:
                logger.warning("No se pudo cargar índice FAISS: %s. Se iniciará vacío.", e)

    def _load_file(self, file_path: Path) -> str:
        suffix = file_path.suffix.lower()
        if suffix == ".txt":
            return file_path.read_text(encoding="utf-8", errors="ignore")
        elif suffix == ".pdf":
            raw = self._extract_text_from_pdf(file_path)
            return self._strip_markdown(raw)
        else:
            logger.warning("Tipo de archivo no soportado: %s", file_path.suffix)
            return ""

    def _strip_markdown(self, text: str) -> str:
        """Elimina sintaxis markdown para que los chunks no tengan headers gigantes al renderizarse."""
        # Cabeceras: ## Título → Título
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        # Negrita/cursiva: **texto** o *texto* → texto
        text = re.sub(r"\*{1,2}([^*\n]+)\*{1,2}", r"\1", text)
        # Líneas horizontales de markdown (--- o ___)
        text = re.sub(r"^[-_]{3,}\s*$", "", text, flags=re.MULTILINE)
        return text

    def _extract_text_from_pdf(self, file_path: Path) -> str:
        try:
            import pymupdf4llm
            text = pymupdf4llm.to_markdown(str(file_path), table_strategy="lines")
            if text.strip():
                return text
        except ImportError:
            pass
        except Exception as e:
            logger.debug("pymupdf4llm falló en '%s' (%s). Usando fitz.", file_path.name, type(e).__name__)

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
                    "'%s': páginas %s parecen ser imágenes.",
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
