# app/core/config.py

from pathlib import Path

# Raíz del proyecto (sunat/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

DOCS_DIR = BASE_DIR / "app" / "data" / "docs"
CHROMA_DIR = BASE_DIR / "chroma_db"

COLLECTION_NAME = "sunat_docs"

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Tamaño de cada chunk en caracteres y superposición entre chunks consecutivos
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

# Resultados a recuperar por búsqueda y umbral máximo de distancia coseno
TOP_K_RESULTS = 3
MAX_DISTANCE = 0.6
