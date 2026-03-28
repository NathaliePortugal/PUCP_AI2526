# app/services/rag_service.py
"""
Pipeline RAG (Retrieval-Augmented Generation) para el chatbot SUNAT.

FUNCIONES
1. Carga documentos desde disco (archivos .txt y .pdf).
2. Divide cada documento en fragmentos (chunks) manejables.
3. Genera embeddings (vectores numéricos) para cada fragmento.
4. Almacena los embeddings en ChromaDB (base de datos vectorial persistente en disco).
5. Ante una consulta del usuario, busca los fragmentos más relevantes semánticamente.

GUARDAR EMBEDDINGS EN CHROMADB
- Es gratuita y open source.
- Persiste los datos en disco automáticamente (no necesitas re-indexar al reiniciar).
- Tiene su propia integración con sentence-transformers.

"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Sequence

import chromadb
from chromadb.utils import embedding_functions

from app.core import config as cfg

logger = logging.getLogger(__name__)


class RagService:
    """
    Servicio principal de RAG. Encapsula todo el pipeline:
    carga de documentos → chunking → embedding → almacenamiento → recuperación.

    Uso típico:
        rag = RagService()
        rag.index_documents()        # indexa todos los docs de DOCS_DIR
        results = rag.search("¿qué es el Nuevo RUS?")
    """

    def __init__(self) -> None:
        """
        Inicializa ChromaDB y la función de embedding.

        PersistentClient guarda la base de datos en el directorio cfg.CHROMA_DIR,
        así los datos sobreviven reinicios del servidor.
        """
        # Asegura que el directorio de ChromaDB exista
        cfg.CHROMA_DIR.mkdir(parents=True, exist_ok=True)

        # Cliente persistente de ChromaDB — guarda todo en disco automáticamente
        self._client = chromadb.PersistentClient(path=str(cfg.CHROMA_DIR))

        # Función de embedding: usa sentence-transformers con el mismo modelo
        # que usa intent_service.py, así no se descarga dos veces.
        # HF_HUB_OFFLINE se setea en main.py antes de que este código corra.
        self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=cfg.EMBEDDING_MODEL
        )

        # Colección = tabla en ChromaDB donde se guardan los vectores y textos
        # get_or_create_collection: si ya existe la abre, si no la crea.
        # metadata hnsw:space=cosine → usamos similitud coseno (mejor para texto)
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
        """
        Indica si ya hay documentos indexados en ChromaDB.
        Usado en main.py para decidir si necesitamos indexar al arrancar.
        """
        return self._collection.count() > 0

    def index_documents(self, docs_dir: Optional[Path] = None) -> int:
        """
        Carga, divide e indexa todos los documentos de docs_dir en ChromaDB.

        Si ya existen documentos de la misma fuente los actualiza (upsert).
        Soporta archivos .txt y .pdf.

        Args:
            docs_dir: carpeta con los documentos. Por defecto usa cfg.DOCS_DIR.

        Returns:
            Número total de fragmentos (chunks) indexados.
        """
        target_dir = docs_dir or cfg.DOCS_DIR

        if not target_dir.exists():
            logger.warning("Directorio de documentos no encontrado: %s", target_dir)
            return 0

        # Busca RECURSIVAMENTE todos los archivos soportados en el directorio y subcarpetas.
        txt_files = list(target_dir.rglob("*.txt"))
        pdf_files = list(target_dir.rglob("*.pdf"))
        all_files = txt_files + pdf_files

        if not all_files:
            logger.warning("No se encontraron documentos en %s", target_dir)
            return 0

        total_chunks = 0

        for file_path in all_files:
            try:
                chunks_added = self._index_single_file(file_path)
                total_chunks += chunks_added
                logger.info("Indexado: %s → %d fragmentos", file_path.name, chunks_added)
            except Exception as e:
                # Si un archivo falla, continuamos con los demás
                logger.error("Error indexando %s: %s", file_path.name, e)

        logger.info(
            "Indexación completa. Total: %d fragmentos en %d archivos.",
            total_chunks,
            len(all_files),
        )
        return total_chunks

    def search(
        self,
        query: str,
        n_results: int = cfg.TOP_K_RESULTS,
        source_filter: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Busca los fragmentos más relevantes para la consulta dada.

        Funcionamiento:
        1. Recupera n_results * CANDIDATE_MULTIPLIER candidatos de ChromaDB.
        2. Filtra los que superan MAX_DISTANCE (poco relevantes).
        3. Deduplica por fuente: si el mismo documento aparece varias veces,
           se conserva solo el chunk con menor distancia (el más relevante).
           Esto evita que un documento grande monopolice los n_results slots.
        4. Devuelve los n_results mejores documentos únicos.

        Args:
            query: pregunta o mensaje del usuario.
            n_results: cuántos documentos distintos devolver.
            source_filter: lista opcional de nombres de archivo (ej. ["Guia_infraciones.pdf"]).
                           Si se proporciona, la búsqueda se restringe a esos documentos.
                           Útil para evitar falsos positivos semánticos cuando la intención
                           del usuario apunta a un dominio documental específico.

        Returns:
            Lista de dicts con keys: 'text', 'source', 'distance', 'chunk_index'.
            Ordenados de más a menos relevante (menor distance = más similar).
            Máximo un resultado por documento fuente.
        """
        if not self.is_indexed():
            logger.warning("No hay documentos indexados. Ejecuta index_documents() primero.")
            return []

        # Recuperamos más candidatos de los que necesitamos para que la
        # deduplicación por fuente tenga suficiente material donde elegir.
        CANDIDATE_MULTIPLIER = 5
        fetch_n = min(n_results * CANDIDATE_MULTIPLIER, self._collection.count())

        # Filtro de fuentes: restringe la búsqueda a documentos relacionados con la intención.
        # ChromaDB acepta {"source": {"$in": [...]}} como filtro de metadatos.
        # Si source_filter está vacío o es None, se busca en toda la colección.
        where_clause = (
            {"source": {"$in": list(source_filter)}}
            if source_filter
            else None
        )

        try:
            query_kwargs: Dict[str, Any] = dict(
                query_texts=[query],
                n_results=fetch_n,
                include=["documents", "metadatas", "distances"],
            )
            if where_clause:
                query_kwargs["where"] = where_clause
                logger.debug(
                    "Búsqueda RAG con filtro de fuentes: %s",
                    list(source_filter),
                )

            results = self._collection.query(**query_kwargs)
        except Exception as e:
            logger.error("Error en búsqueda RAG: %s", e)
            return []

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        # Deduplicar por fuente: conservar el chunk con menor distancia por doc.
        # best_by_source[source] = el dict resultado con menor distancia visto.
        best_by_source: Dict[str, Dict[str, Any]] = {}

        for text, meta, distance in zip(documents, metadatas, distances):
            if distance > cfg.MAX_DISTANCE:
                continue  # descartar resultados poco relevantes

            source = meta.get("source", "desconocido")
            entry = {
                "text": text,
                "source": source,
                "distance": round(distance, 4),
                "chunk_index": meta.get("chunk_index", 0),
                "similarity_pct": round((1 - distance / 2) * 100, 1),
            }

            # Solo guardamos el chunk más cercano (menor distancia) por fuente
            if source not in best_by_source or distance < best_by_source[source]["distance"]:
                best_by_source[source] = entry

        # Ordenar los mejores chunks únicos por distancia y tomar los n_results
        unique_results = sorted(best_by_source.values(), key=lambda x: x["distance"])
        final_results = unique_results[:n_results]

        logger.debug(
            "Búsqueda RAG: '%s' → %d fuentes únicas relevantes (de %d candidatos, %d fuentes distintas).",
            query[:60],
            len(final_results),
            len(documents),
            len(best_by_source),
        )

        return final_results

    def get_stats(self) -> Dict[str, Any]:
        """
        Devuelve estadísticas de la colección.
        Útil para debugging y para el endpoint de health check.
        """
        return {
            "collection_name": cfg.COLLECTION_NAME,
            "total_chunks": self._collection.count(),
            "chroma_dir": str(cfg.CHROMA_DIR),
            "embedding_model": cfg.EMBEDDING_MODEL,
        }


    def _index_single_file(self, file_path: Path) -> int:
        """
        Procesa un solo archivo: lo carga, lo divide en chunks y los indexa.

        Returns:
            Número de chunks indexados del archivo.
        """
        # 1. Cargar el texto del archivo
        text = self._load_file(file_path)
        if not text.strip():
            logger.warning("Archivo vacío o sin texto: %s", file_path.name)
            return 0

        # 2. Dividir en fragmentos manejables
        chunks = self._chunk_text(text, cfg.CHUNK_SIZE, cfg.CHUNK_OVERLAP)

        if not chunks:
            return 0

        # 3. Preparar los datos para ChromaDB
        # Cada chunk necesita: un ID único, el texto, y metadata (info extra)
        ids = []
        documents = []
        metadatas = []

        for i, chunk in enumerate(chunks):
            # ID único por archivo + índice: "sunat_regimenes_tributarios_0", "_1", etc.
            chunk_id = f"{file_path.stem}_{i}"

            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append({
                "source": file_path.name,    # nombre del archivo origen
                "chunk_index": i,             # posición del chunk en el documento
                "total_chunks": len(chunks),  # total de chunks del documento
            })

        # 4. Indexar en ChromaDB usando upsert (insert + update si ya existe)
        # Esto permite re-indexar sin crear duplicados
        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        return len(chunks)

    def _load_file(self, file_path: Path) -> str:
        """
        Carga el contenido de texto de un archivo .txt o .pdf.

        Para PDFs usa PyMuPDF (fitz), que ya está en requirements.txt.
        """
        suffix = file_path.suffix.lower()

        if suffix == ".txt":
            # Lectura directa de archivos de texto
            return file_path.read_text(encoding="utf-8", errors="ignore")

        elif suffix == ".pdf":
            # Extracción de texto de PDF usando PyMuPDF
            return self._extract_text_from_pdf(file_path)

        else:
            logger.warning("Tipo de archivo no soportado: %s", file_path.suffix)
            return ""

    def _extract_text_from_pdf(self, file_path: Path) -> str:
        """
        Extrae todo el texto de un PDF.

        Estrategia en dos pasos:
        1. Intenta pymupdf4llm, que convierte el PDF a Markdown y maneja
           tablas y columnas mucho mejor que el extractor básico de PyMuPDF.
        2. Si pymupdf4llm no está instalado, usa PyMuPDF (fitz) directamente.
           En este modo también detecta páginas que son imágenes puras (poco
           texto + imágenes embebidas) y emite una advertencia para que se
           sepa qué contenido puede estar perdiéndose.

        Para instalar la librería mejorada:
            pip install pymupdf4llm
        """
        # --- Paso 1: pymupdf4llm (preferido) --------------------------------
        # Usa table_strategy="lines" para evitar el modelo ONNX interno que
        # puede fallar en Windows con ciertos PDFs por incompatibilidad int32/int64.
        try:
            import pymupdf4llm  # type: ignore

            text = pymupdf4llm.to_markdown(str(file_path), table_strategy="lines")
            if text.strip():
                logger.debug(
                    "PDF cargado con pymupdf4llm: %s (%d caracteres)",
                    file_path.name,
                    len(text),
                )
                return text
        except ImportError:
            pass  # no instalado, continuar con fitz
        except Exception as e:
            # Fallo silencioso: el fallback a fitz a continuación es suficiente.
            logger.debug(
                "pymupdf4llm no pudo procesar '%s' (%s). Usando fitz.",
                file_path.name,
                type(e).__name__,
            )

        # --- Paso 2: PyMuPDF (fitz) con detección de páginas imagen ---------
        try:
            import fitz  # PyMuPDF

            text_parts = []
            image_only_pages = []
            doc = fitz.open(str(file_path))

            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                chars = len(page_text.strip())

                if chars < 100:
                    # Página con muy poco texto: verificar si tiene imágenes
                    images = page.get_images(full=False)
                    if images:
                        image_only_pages.append(page_num + 1)

                if page_text.strip():
                    text_parts.append(page_text)

            total_pages = page_num + 1
            doc.close()

            if image_only_pages:
                try:
                    import pymupdf4llm  # noqa: F401
                    _has_pymupdf4llm = True
                except ImportError:
                    _has_pymupdf4llm = False

                if _has_pymupdf4llm:
                    # pymupdf4llm está instalado pero falló en este PDF (ej. error ONNX).
                    # El contenido de esas páginas no se indexará.
                    logger.warning(
                        "'%s': páginas %s son imágenes y pymupdf4llm no pudo procesarlas. "
                        "Ese contenido visual no quedará indexado en ChromaDB.",
                        file_path.name,
                        image_only_pages,
                    )
                else:
                    logger.warning(
                        "'%s': páginas %s parecen imágenes (poco texto). "
                        "Instala pymupdf4llm para mejorar la extracción: pip install pymupdf4llm",
                        file_path.name,
                        image_only_pages,
                    )

            full_text = "\n".join(text_parts)
            logger.debug(
                "PDF cargado con fitz: %s (%d páginas, %d caracteres)",
                file_path.name,
                total_pages,
                len(full_text),
            )
            return full_text

        except ImportError:
            logger.error("PyMuPDF no instalado. Instala con: pip install pymupdf")
            return ""
        except Exception as e:
            logger.error("Error leyendo PDF %s: %s", file_path.name, e)
            return ""

    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """
        Divide un texto largo en fragmentos (chunks) con superposición (overlap).

        Si dividimos sin overlap, podemos cortar una idea a la mitad.
        Con overlap, cada chunk comparte algunos caracteres con el anterior,
        así la información que estaba "en el borde" aparece en ambos chunks.

        Ejemplo con chunk_size=10, overlap=3:
        Texto: "ABCDEFGHIJKLMNOP"
        Chunk 1: "ABCDEFGHIJ"  (posición 0-10)
        Chunk 2: "HIJKLMNOP"   (posición 7-17, overlap de "HIJ")

        Args:
            text: texto completo del documento.
            chunk_size: tamaño máximo de cada fragmento en caracteres.
            overlap: cuántos caracteres comparten fragmentos consecutivos.

        Returns:
            Lista de strings, cada uno es un fragmento del texto.
        """
        if len(text) <= chunk_size:
            # Si el texto es pequeño, no necesita dividirse
            return [text.strip()] if text.strip() else []

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Si no es el último chunk, intentamos cortar en un espacio/salto de línea
            # para no cortar palabras a la mitad
            if end < len(text):
                # Busca hacia atrás un salto de línea o espacio para cortar limpio
                cut_pos = text.rfind("\n", start, end)
                if cut_pos == -1:
                    cut_pos = text.rfind(" ", start, end)
                if cut_pos > start:
                    end = cut_pos

            chunk = text[start:end].strip()
            if chunk:  # Solo agrega chunks no vacíos
                chunks.append(chunk)

            # El siguiente chunk empieza con overlap para no perder contexto
            start = end - overlap

            # Seguridad: si el overlap nos retrocede demasiado, avanzamos de todas formas
            if start <= (end - chunk_size):
                start = end

        return chunks
