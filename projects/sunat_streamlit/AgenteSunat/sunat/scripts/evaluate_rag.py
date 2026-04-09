#!/usr/bin/env python
# scripts/evaluate_rag.py
"""
Evaluación del pipeline RAG (Retrieval-Augmented Generation).

¿QUÉ MIDE ESTE SCRIPT?

HIT RATE @ K (también llamado Recall@K):
    "De todos los queries evaluados, ¿en qué porcentaje el documento correcto
    apareció entre los primeros K resultados?"
    → Mide si el sistema ENCUENTRA la información relevante.
    → Hit Rate@1 = solo cuenta si el correcto fue el PRIMER resultado (más exigente).
    → Hit Rate@3 = cuenta si el correcto apareció en el TOP 3 (más flexible).

MRR — Mean Reciprocal Rank:
    "En promedio, ¿en qué posición aparece el primer resultado correcto?"
    → Si siempre aparece en posición 1: MRR = 1.0 (perfecto).
    → Si siempre aparece en posición 2: MRR = 0.5.
    → Si siempre aparece en posición 3: MRR = 0.33.
    → Más informativo que Hit Rate porque penaliza aparecer tarde.

AVERAGE DISTANCE:
    Promedio de la distancia coseno entre el query y los resultados recuperados.
    → Valores cercanos a 0 = muy relevante. Valores cercanos a 1 = poco relevante.
    → Nos dice qué tan "confiado" está el sistema en sus respuestas.

USO:
    cd sunat/
    python scripts/evaluate_rag.py
    python scripts/evaluate_rag.py --k 5      # evalúa Hit Rate@5 también
    python scripts/evaluate_rag.py --verbose  # muestra resultados por query
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any

# Agregar el directorio raíz al path para importar app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.rag_service import RagService
from app.data.test_cases.rag_test_cases import RAG_TEST_CASES


# ---------------------------------------------------------------------------
# Funciones de cálculo de métricas RAG
# ---------------------------------------------------------------------------

def hit_rate_at_k(
    resultados: List[Dict[str, Any]],
    expected_sources: List[str],
    k: int,
) -> bool:
    """
    ¿Aparece alguno de los documentos esperados entre los primeros k resultados?

    Args:
        resultados: lista de dicts devuelta por rag_service.search()
        expected_sources: lista de nombres de archivo esperados
        k: número de resultados a considerar

    Returns:
        True si encontró al menos un documento esperado en top-k, False si no.
    """
    top_k_sources = [r["source"] for r in resultados[:k]]
    return any(src in top_k_sources for src in expected_sources)


def reciprocal_rank(
    resultados: List[Dict[str, Any]],
    expected_sources: List[str],
) -> float:
    """
    Calcula el Reciprocal Rank para un query.

    = 1 / (posición del primer resultado correcto)

    Ejemplos:
    - Si el primer resultado es correcto: RR = 1/1 = 1.0
    - Si el segundo resultado es correcto: RR = 1/2 = 0.5
    - Si el tercero es correcto: RR = 1/3 = 0.33
    - Si ninguno es correcto: RR = 0.0
    """
    for i, resultado in enumerate(resultados, start=1):
        if resultado["source"] in expected_sources:
            return 1.0 / i
    return 0.0


# ---------------------------------------------------------------------------
# Script principal
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Evalúa el pipeline RAG del chatbot SUNAT."
    )
    parser.add_argument(
        "--k",
        type=int,
        default=3,
        help="Número de resultados a recuperar por query (default: 3).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Muestra los resultados de cada query.",
    )
    args = parser.parse_args()

    print("\n" + "=" * 65)
    print("  EVALUACIÓN DEL PIPELINE RAG")
    print("=" * 65)
    print("\n  Inicializando FAISS y modelo de embeddings...")

    rag = RagService()

    if not rag.is_indexed():
        print("\n  ERROR: No hay documentos indexados en FAISS.")
        print("  Ejecuta primero: python scripts/ingest_documents.py")
        sys.exit(1)

    stats = rag.get_stats()
    print(f"  FAISS listo: {stats['total_chunks']} fragmentos indexados.")
    print(f"  Evaluando {len(RAG_TEST_CASES)} queries de prueba con top-{args.k}...\n")

    # Resultados acumulados
    hits_at_1  = []   # 1 si encontró el doc correcto en posición 1
    hits_at_k  = []   # 1 si encontró el doc correcto en top-k
    rr_scores  = []   # reciprocal rank de cada query
    distances  = []   # distancias promedio de los resultados relevantes

    resultados_por_query = []

    for caso in RAG_TEST_CASES:
        query    = caso["query"]
        expected = caso["expected_sources"]

        # Buscar en FAISS
        resultados = rag.search(query=query, n_results=args.k)

        # Calcular métricas para este query
        h1  = hit_rate_at_k(resultados, expected, k=1)
        hk  = hit_rate_at_k(resultados, expected, k=args.k)
        rr  = reciprocal_rank(resultados, expected)

        hits_at_1.append(1 if h1 else 0)
        hits_at_k.append(1 if hk else 0)
        rr_scores.append(rr)

        # Distancia promedio de los resultados que SÍ son del documento esperado
        dists_relevantes = [
            r["distance"] for r in resultados
            if r["source"] in expected
        ]
        if dists_relevantes:
            distances.append(sum(dists_relevantes) / len(dists_relevantes))

        resultados_por_query.append({
            "query":    query,
            "expected": expected,
            "hit@1":    h1,
            "hit@k":    hk,
            "rr":       rr,
            "resultados": resultados,
        })

        # Verbose: imprimir detalle de cada query
        if args.verbose:
            marca = "✓" if h1 else ("~" if hk else "✗")
            print(f"  {marca} RR={rr:.2f} | '{query[:55]}'")
            for i, r in enumerate(resultados, 1):
                es_correcto = r["source"] in expected
                indicador = "←✓" if es_correcto else ""
                print(f"      {i}. {r['source']} (dist={r['distance']:.3f}) {indicador}")
            print()

    # Calcular métricas globales
    n = len(RAG_TEST_CASES)
    hit_rate_1   = sum(hits_at_1) / n
    hit_rate_top = sum(hits_at_k) / n
    mrr          = sum(rr_scores) / n
    avg_distance = sum(distances) / len(distances) if distances else 0

    # ---- Imprimir resultados globales ----
    print("=" * 65)
    print("  RESULTADOS GLOBALES")
    print("=" * 65)
    print(f"  Queries evaluados      : {n}")
    print(f"  Hit Rate @ 1           : {hit_rate_1 * 100:.1f}%  "
          f"(el doc correcto fue el 1er resultado)")
    print(f"  Hit Rate @ {args.k}           : {hit_rate_top * 100:.1f}%  "
          f"(el doc correcto apareció en top-{args.k})")
    print(f"  MRR (Mean Recip. Rank) : {mrr:.3f}  (1.0 = siempre en 1er lugar)")
    print(f"  Distancia media (hits) : {avg_distance:.3f}  (0 = idéntico, 1 = diferente)")

    # ---- Análisis por tema ----
    print("\n" + "=" * 65)
    print("  ANÁLISIS POR DOCUMENTO FUENTE")
    print("=" * 65)

    # Agrupar resultados por documento esperado
    por_doc: Dict[str, List] = {}
    for r in resultados_por_query:
        for src in r["expected"]:
            if src not in por_doc:
                por_doc[src] = []
            por_doc[src].append(r)

    for doc, casos_doc in sorted(por_doc.items()):
        h1_doc  = sum(1 for c in casos_doc if c["hit@1"]) / len(casos_doc)
        hk_doc  = sum(1 for c in casos_doc if c["hit@k"]) / len(casos_doc)
        mrr_doc = sum(c["rr"] for c in casos_doc) / len(casos_doc)
        icono   = "✓" if h1_doc >= 0.8 else ("⚠" if h1_doc >= 0.5 else "✗")
        nombre  = doc.replace("sunat_", "").replace(".txt", "").replace("_", " ").title()

        print(
            f"  {icono} {nombre:<32} "
            f"Hit@1={h1_doc*100:.0f}%  "
            f"Hit@{args.k}={hk_doc*100:.0f}%  "
            f"MRR={mrr_doc:.2f}"
        )

    # ---- Queries donde falló ----
    fallos = [r for r in resultados_por_query if not r["hit@k"]]
    if fallos:
        print("\n" + "=" * 65)
        print(f"  QUERIES SIN RESULTADO CORRECTO EN TOP-{args.k} ({len(fallos)} casos)")
        print("=" * 65)
        for f in fallos:
            print(f"\n  Query   : \"{f['query']}\"")
            print(f"  Esperado: {f['expected']}")
            if f["resultados"]:
                print(f"  Obtuvo  : {[r['source'] for r in f['resultados']]}")
            else:
                print("  Obtuvo  : (ningún resultado - revisar MAX_DISTANCE en config.py)")

    # ---- Interpretación ----
    print("\n" + "=" * 65)
    print("  INTERPRETACIÓN DE RESULTADOS")
    print("=" * 65)

    if hit_rate_top >= 0.85:
        nivel = "BUENO"
        consejo = "El RAG recupera bien los documentos relevantes."
    elif hit_rate_top >= 0.70:
        nivel = "ACEPTABLE"
        consejo = (
            "Se recomienda mejorar el chunking o agregar más contenido "
            "a los documentos con bajo Hit Rate."
        )
    else:
        nivel = "NECESITA MEJORA ✗"
        consejo = (
            "El RAG no recupera correctamente los documentos. Opciones:\n"
            "  1. Verificar que los docs estén indexados (python scripts/ingest_documents.py)\n"
            "  2. Ajustar CHUNK_SIZE y CHUNK_OVERLAP en config.py\n"
            "  3. Incrementar MAX_DISTANCE en config.py (actualmente filtra resultados distantes)"
        )

    print(f"\n  Nivel general : {nivel}")
    print(f"  Consejo       : {consejo}")
    print(f"\n  Benchmark de referencia:")
    print(f"  - Hit Rate@3 >= 85% → Bueno")
    print(f"  - Hit Rate@3 >= 70% → Aceptable")
    print(f"  - MRR >= 0.7        → El doc correcto aparece cerca del top")
    print()


if __name__ == "__main__":
    main()
