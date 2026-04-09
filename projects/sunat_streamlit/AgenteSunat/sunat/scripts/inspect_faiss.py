#!/usr/bin/env python
# scripts/inspect_faiss.py
"""
Herramienta de inspección de la base de datos vectorial (FAISS).

Muestra exactamente qué hay indexado: fuentes, cantidad de chunks,
y permite hacer búsquedas de prueba para verificar que el RAG funciona.

Uso:
    python scripts/inspect_faiss.py                  # resumen general
    python scripts/inspect_faiss.py --samples        # muestra un chunk de muestra por archivo
    python scripts/inspect_faiss.py --search "multas"  # prueba una búsqueda
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.rag_service import RagService
from app.core import config as cfg


def main():
    parser = argparse.ArgumentParser(description="Inspecciona el contenido del índice FAISS.")
    parser.add_argument("--samples", action="store_true", help="Muestra un chunk de ejemplo por archivo.")
    parser.add_argument("--search", type=str, default="", help="Ejecuta una búsqueda de prueba.")
    parser.add_argument("--all", action="store_true", help="Muestra TODOS los chunks (puede ser largo).")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  INSPECTOR DE ÍNDICE FAISS — SUNAT Chatbot")
    print("=" * 60)

    rag = RagService()

    if not rag.is_indexed():
        print("\n  ⚠ El índice FAISS está VACÍO.")
        print("  Ejecuta primero: python scripts/ingest_documents.py")
        return

    metadatas = rag._metadatas
    documents = rag._documents
    total = rag._index.ntotal

    # Contar chunks por archivo fuente
    fuentes = Counter(m["source"] for m in metadatas)

    # --- Resumen general ---
    print(f"\n  📦 Directorio índice : {cfg.INDEX_DIR}")
    print(f"  📚 Colección         : {cfg.COLLECTION_NAME}")
    print(f"  🔢 Total de chunks   : {total}")
    print(f"  📄 Archivos fuente   : {len(fuentes)}")

    print(f"\n  Chunks por archivo:")
    print("  " + "-" * 50)
    for fuente, cantidad in sorted(fuentes.items()):
        barra = "█" * min(cantidad, 30)
        print(f"  {fuente:<45} {cantidad:>3} chunks  {barra}")

    # --- Muestras de chunks ---
    if args.samples:
        print(f"\n" + "=" * 60)
        print("  MUESTRA DE CHUNKS (1 por archivo)")
        print("=" * 60)

        mostrados = set()
        for meta, doc in zip(metadatas, documents):
            src = meta["source"]
            if src in mostrados:
                continue
            mostrados.add(src)

            print(f"\n  📄 Fuente  : {src}")
            print(f"  📍 Chunk   : {meta.get('chunk_index', '?')} de {meta.get('total_chunks', '?')}")
            print(f"  📝 Texto   :")
            preview = doc[:300].replace("\n", " ")
            print(f"     {preview}...")

    # --- Búsqueda de prueba ---
    if args.search:
        print(f"\n" + "=" * 60)
        print(f"  BÚSQUEDA DE PRUEBA: \"{args.search}\"")
        print("=" * 60)

        resultados = rag.search(query=args.search, n_results=3)

        if not resultados:
            print(f"\n  ⚠ No se encontraron resultados relevantes.")
            print(f"  Prueba ajustar MAX_DISTANCE en config.py (actual: {cfg.MAX_DISTANCE})")
        else:
            for i, r in enumerate(resultados, 1):
                print(f"\n  Resultado {i}:")
                print(f"  📄 Fuente     : {r['source']}")
                print(f"  📊 Similitud  : {r['similarity_pct']}%  (distancia: {r['distance']})")
                print(f"  📝 Fragmento  :")
                preview = r['text'][:400].replace("\n", " ")
                print(f"     {preview}...")

    # --- Mostrar todos los chunks ---
    if args.all:
        print(f"\n" + "=" * 60)
        print("  TODOS LOS CHUNKS")
        print("=" * 60)
        for i, (meta, doc) in enumerate(zip(metadatas, documents)):
            print(f"\n  [{i+1}] {meta['source']} — chunk {meta.get('chunk_index','?')}")
            print(f"  {doc[:200].replace(chr(10), ' ')}...")

    print()


if __name__ == "__main__":
    main()
