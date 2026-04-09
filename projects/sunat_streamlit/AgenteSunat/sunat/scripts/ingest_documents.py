#!/usr/bin/env python
# scripts/ingest_documents.py
"""
Script de ingesta manual de documentos para el RAG.

¿Cuándo se utiliza este script?
- La primera vez que se configura el proyecto.
- Cuando se agregan nuevos documentos PDF o TXT a la carpeta data/docs/.
- Cuando se desea forzar la re-indexación (por ejemplo, después de modificar un documento).

¿Qué hace?
1. Borra el índice FAISS existente (para comenzar desde cero).
2. Carga todos los archivos .txt y .pdf de data/docs/.
3. Los divide en chunks.
4. Los indexa en FAISS.

Uso:
    # Desde la carpeta sunat/
    python scripts/ingest_documents.py

    # Con verbose output
    python scripts/ingest_documents.py --verbose

    # Para indexar desde una carpeta diferente
    python scripts/ingest_documents.py --docs-dir /ruta/a/los/docs
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Agregar el directorio padre al path para poder importar app.*
# Necesario porque ejecutamos este script desde sunat/, no desde app/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import config as cfg
from app.services.rag_service import RagService


def setup_logging(verbose: bool) -> None:
    """Configura el nivel de logging según el flag --verbose."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    """Define y parsea los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="Indexa documentos SUNAT en FAISS para el sistema RAG.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python scripts/ingest_documents.py
  python scripts/ingest_documents.py --verbose
  python scripts/ingest_documents.py --docs-dir ./mis_docs --verbose
        """,
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=cfg.DOCS_DIR,
        help=f"Carpeta con los documentos a indexar. Default: {cfg.DOCS_DIR}",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Mostrar información detallada del proceso.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Forzar re-indexación aunque ya existan documentos.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    print("\n" + "=" * 60)
    print("  SUNAT Chatbot — Indexación de Documentos RAG")
    print("=" * 60)

    # Verificar que la carpeta de documentos existe
    docs_dir = args.docs_dir
    if not docs_dir.exists():
        print(f"\n❌ Error: La carpeta de documentos no existe: {docs_dir}")
        print(f"   Se debe crear la carpeta y agregar los archivos .txt o .pdf.")
        sys.exit(1)

    # Listar archivos encontrados
    # rglob busca recursivamente en todas las subcarpetas
    txt_files = list(docs_dir.rglob("*.txt"))
    pdf_files = list(docs_dir.rglob("*.pdf"))
    # Excluir archivos .py que puedan estar en test_cases/
    all_files = [f for f in txt_files + pdf_files if not str(f).endswith(".py")]

    if not all_files:
        print(f"\n⚠ No se encontraron archivos .txt o .pdf en: {docs_dir}")
        print("  Se deben agregar documentos SUNAT y volver a ejecutar este script.")
        sys.exit(0)

    print(f"\n📁 Directorio: {docs_dir}")
    print(f"   Archivos encontrados: {len(all_files)}")
    for f in sorted(all_files):
        size_kb = f.stat().st_size / 1024
        print(f"   • {f.name} ({size_kb:.1f} KB)")

    print(f"\n🔧 Configuración:")
    print(f"   Índice FAISS: {cfg.INDEX_DIR}")
    print(f"   Colección: {cfg.COLLECTION_NAME}")
    print(f"   Modelo: {cfg.EMBEDDING_MODEL}")
    print(f"   Chunk size: {cfg.CHUNK_SIZE} chars | Overlap: {cfg.CHUNK_OVERLAP} chars")

    # Inicializar el servicio RAG
    print("\n⏳ Inicializando índice FAISS y modelo de embeddings...")
    print("   (La primera vez puede tardar ~30 segundos mientras descarga el modelo)")
    start_time = time.time()

    rag_service = RagService()

    # Verificar si ya hay documentos indexados
    if rag_service.is_indexed() and not args.force:
        stats = rag_service.get_stats()
        print(f"\n✅ Ya hay {stats['total_chunks']} fragmentos indexados en FAISS.")
        print("   Para re-indexar, se debe utilizar el flag --force:")
        print("   python scripts/ingest_documents.py --force")
        return

    # Si --force, limpiar el índice antes de re-indexar
    if args.force and rag_service.is_indexed():
        print("\n🗑  Limpiando índice existente (--force activado)...")
        rag_service.clear()
        print("   Índice limpiado.")

    # Ejecutar la indexación
    print(f"\n📚 Indexando {len(all_files)} documento(s)...")
    total_chunks = rag_service.index_documents(docs_dir=docs_dir)

    elapsed = time.time() - start_time

    # Mostrar resultado
    print("\n" + "=" * 60)
    if total_chunks > 0:
        print(f"✅ Indexación completada exitosamente.")
        print(f"   Total de fragmentos indexados: {total_chunks}")
        print(f"   Tiempo total: {elapsed:.1f} segundos")
        print(f"   Índice FAISS guardado en: {cfg.INDEX_DIR}")
    else:
        print(f"⚠ No se indexaron fragmentos. Se deben revisar los archivos en {docs_dir}")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
