# app/core/config.py
"""
Configuración central del proyecto SUNAT Chatbot.

Aquí centralizamos todas las constantes de configuración:
- rutas de archivos y directorios
- nombre de colecciones en ChromaDB
- modelos de embeddings
- parámetros del pipeline RAG

"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas base del proyecto
# ---------------------------------------------------------------------------

# Directorio raíz del backend (sunat/)
# __file__ es este archivo: sunat/app/core/config.py
# .parent      → sunat/app/core/
# .parent.parent → sunat/app/
# .parent.parent.parent → sunat/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Carpeta donde viven los documentos fuente (PDFs, TXTs de SUNAT)
DOCS_DIR = BASE_DIR / "app" / "data" / "docs"

# Carpeta donde ChromaDB persistirá la base de datos vectorial en disco
# Esto evita tener que re-indexar cada vez que se reinicia el servidor
CHROMA_DIR = BASE_DIR / "chroma_db"

# ---------------------------------------------------------------------------
# Configuración de ChromaDB
# ---------------------------------------------------------------------------

# Nombre de la colección dentro de ChromaDB (como una "tabla" en SQL)
COLLECTION_NAME = "sunat_docs"

# ---------------------------------------------------------------------------
# Modelo de embeddings
# ---------------------------------------------------------------------------

# Usamos el mismo modelo que usa intent_service.py para consistencia.
# Este modelo es multilingüe y funciona bien en español.
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# ---------------------------------------------------------------------------
# Parámetros del chunking (división de documentos)
# ---------------------------------------------------------------------------

# Tamaño de cada fragmento en caracteres.
# Fragmentos muy grandes pierden precisión; muy pequeños pierden contexto.
# 500 caracteres ≈ 2-3 párrafos cortos → buen balance para Q&A.
CHUNK_SIZE = 500

# Superposición entre fragmentos consecutivos en caracteres.
# Evita que una respuesta quede "cortada" entre dos chunks.
CHUNK_OVERLAP = 100

# ---------------------------------------------------------------------------
# Parámetros de recuperación RAG
# ---------------------------------------------------------------------------

# Cuántos fragmentos relevantes recuperar por consulta.
TOP_K_RESULTS = 3

# Umbral máximo de distancia coseno (0 = idéntico, 2 = opuesto).
# Fragmentos con distancia mayor a este valor se descartan como poco relevantes.
MAX_DISTANCE = 0.6
