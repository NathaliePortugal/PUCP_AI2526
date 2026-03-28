#!/usr/bin/env python
# scripts/evaluate_intent.py
"""
Evaluación del clasificador de intenciones (IntentService).

¿QUÉ MIDE ESTE SCRIPT?
Compara lo que predice el modelo contra lo que era correcto, y calcula:

- ACCURACY: de todos los mensajes evaluados, ¿qué % clasificó bien?
  → Es el indicador más intuitivo.

- PRECISION por intención: de todos los mensajes que el modelo dijo "son intent X",
  ¿qué porcentaje realmente era X?
  → Mide cuántos falsos positivos tiene.

- RECALL por intención: de todos los mensajes que REALMENTE son intent X,
  ¿qué porcentaje el modelo los clasificó como X?
  → Mide cuántos falsos negativos tiene.

- F1 por intención: media armónica entre Precision y Recall.
  → El mejor indicador individual por clase (útil cuando los datos no están balanceados).

- MATRIZ DE CONFUSIÓN: tabla que muestra qué intents se confunden entre sí.
  → Muy útil para entender los errores del modelo.

USO:
    cd sunat/
    python scripts/evaluate_intent.py
    python scripts/evaluate_intent.py --verbose   # muestra cada predicción
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Dict

# Agregar el directorio raíz al path para importar app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.intent_service import IntentService
from app.data.test_cases.intent_test_cases import INTENT_TEST_CASES


# ---------------------------------------------------------------------------
# Funciones de cálculo de métricas
# (sin sklearn: todo hecho a mano para entender qué está pasando)
# ---------------------------------------------------------------------------

def calcular_metricas(
    y_true: List[str],
    y_pred: List[str],
) -> Dict:
    """
    Calcula accuracy, precision, recall y F1 para clasificación multiclase.

    Args:
        y_true: lista de etiquetas reales (ground truth)
        y_pred: lista de etiquetas predichas por el modelo

    Returns:
        Dict con accuracy global y métricas por clase.
    """
    intents = sorted(set(y_true))   # lista de todas las clases posibles

    # Contadores por clase
    verdaderos_positivos = defaultdict(int)   # predijo X y era X
    falsos_positivos     = defaultdict(int)   # predijo X pero no era X
    falsos_negativos     = defaultdict(int)   # era X pero predijo otra cosa

    correctos = 0
    for real, pred in zip(y_true, y_pred):
        if real == pred:
            verdaderos_positivos[real] += 1
            correctos += 1
        else:
            falsos_positivos[pred] += 1
            falsos_negativos[real] += 1

    # Accuracy global
    accuracy = correctos / len(y_true) if y_true else 0

    # Métricas por clase
    por_clase = {}
    for intent in intents:
        vp = verdaderos_positivos[intent]
        fp = falsos_positivos[intent]
        fn = falsos_negativos[intent]

        # Precision: TP / (TP + FP)
        # "De lo que predije como X, ¿cuánto era realmente X?"
        precision = vp / (vp + fp) if (vp + fp) > 0 else 0.0

        # Recall: TP / (TP + FN)
        # "De todos los X reales, ¿cuántos encontré?"
        recall = vp / (vp + fn) if (vp + fn) > 0 else 0.0

        # F1: 2 * P * R / (P + R)
        # Media armónica — penaliza cuando P y R son muy disparejos
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        por_clase[intent] = {
            "precision": round(precision, 3),
            "recall":    round(recall, 3),
            "f1":        round(f1, 3),
            "soporte":   vp + fn,   # cuántos ejemplos reales hay de esta clase
        }

    # Macro F1: promedio simple del F1 de todas las clases (trata igual a todas)
    macro_f1 = sum(m["f1"] for m in por_clase.values()) / len(por_clase) if por_clase else 0

    return {
        "accuracy":  round(accuracy, 4),
        "macro_f1":  round(macro_f1, 4),
        "por_clase": por_clase,
    }


def construir_matriz_confusion(
    y_true: List[str],
    y_pred: List[str],
    intents: List[str],
) -> Dict[str, Dict[str, int]]:
    """
    Construye la matriz de confusión como un dict anidado.

    matriz[real][predicho] = cantidad de veces que pasó

    Ejemplo de lectura:
    - Si matriz["multas_y_sanciones"]["formalizacion_negocio"] = 2,
      significa que 2 mensajes de multas fueron clasificados como formalización.
    """
    # Inicializar todos en 0
    matriz = {i: {j: 0 for j in intents} for i in intents}

    for real, pred in zip(y_true, y_pred):
        if real in matriz and pred in matriz:
            matriz[real][pred] += 1

    return matriz


def imprimir_matriz_confusion(
    matriz: Dict[str, Dict[str, int]],
    intents: List[str],
) -> None:
    """
    Imprime la matriz de confusión en formato tabla de texto.

    Las filas son los intents REALES, las columnas los PREDICHOS.
    Los valores en la diagonal = predicciones correctas.
    Fuera de la diagonal = errores (confusiones).
    """
    # Nombres cortos para que la tabla quepa en pantalla
    etiquetas_cortas = {
        "formalizacion_negocio":  "FORM",
        "multas_y_sanciones":     "MULT",
        "regimenes_tributarios":  "REGI",
        "comprobantes_pago":      "COMP",
        "cronograma_obligaciones":"CRON",
    }

    header_cols = [etiquetas_cortas.get(i, i[:4].upper()) for i in intents]

    # Encabezado
    col_width = 6
    print("\n  Matriz de Confusión (filas=real, columnas=predicho)")
    print("  " + " " * 6 + "  ".join(f"{c:>{col_width}}" for c in header_cols))
    print("  " + "-" * (6 + (col_width + 2) * len(intents)))

    for intent_real in intents:
        fila = etiquetas_cortas.get(intent_real, intent_real[:4].upper())
        valores = "  ".join(
            f"{matriz[intent_real][intent_pred]:>{col_width}}"
            for intent_pred in intents
        )
        print(f"  {fila:<6}  {valores}")

    print()
    print("  Referencia:", "  ".join(
        f"{v}={k}" for k, v in etiquetas_cortas.items() if k in intents
    ))


# ---------------------------------------------------------------------------
# Script principal
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Evalúa el clasificador de intenciones del chatbot SUNAT."
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Muestra cada predicción individual (buenas y malas).",
    )
    args = parser.parse_args()

    print("\n" + "=" * 65)
    print("  EVALUACIÓN DEL CLASIFICADOR DE INTENCIONES")
    print("=" * 65)
    print(f"\n  Cargando modelo de embeddings (puede tardar un momento)...")

    # Cargar el clasificador
    classifier = IntentService()

    print(f"  Modelo cargado. Evaluando {len(INTENT_TEST_CASES)} casos de prueba...\n")

    y_true  = []  # etiquetas reales
    y_pred  = []  # etiquetas predichas
    scores  = []  # confianzas del modelo
    errores = []  # casos donde el modelo se equivocó

    # Evaluar cada caso
    for caso in INTENT_TEST_CASES:
        texto    = caso["text"]
        esperado = caso["expected_intent"]

        resultado = classifier.classify_topic(texto)
        predicho  = resultado.intent
        confianza = resultado.confidence

        y_true.append(esperado)
        y_pred.append(predicho)
        scores.append(confianza)

        correcto = (predicho == esperado)

        if not correcto:
            errores.append({
                "texto":    texto,
                "esperado": esperado,
                "predicho": predicho,
                "conf":     confianza,
            })

        # Modo verbose: imprimir cada predicción
        if args.verbose:
            marca = "✓" if correcto else "✗"
            print(f"  {marca} [{confianza:.2f}] '{texto[:55]}'")
            if not correcto:
                print(f"      Esperado: {esperado}")
                print(f"      Predicho: {predicho}")

    # Calcular métricas
    metricas = calcular_metricas(y_true, y_pred)
    intents  = sorted(set(y_true))
    matriz   = construir_matriz_confusion(y_true, y_pred, intents)

    # ---- Imprimir resultados ----
    print("\n" + "=" * 65)
    print("  RESULTADOS GLOBALES")
    print("=" * 65)
    print(f"  Casos evaluados  : {len(INTENT_TEST_CASES)}")
    print(f"  Aciertos         : {len(INTENT_TEST_CASES) - len(errores)}")
    print(f"  Errores          : {len(errores)}")
    print(f"  Accuracy         : {metricas['accuracy'] * 100:.1f}%")
    print(f"  Macro F1         : {metricas['macro_f1'] * 100:.1f}%")
    print(f"  Confianza media  : {sum(scores) / len(scores):.3f}")

    print("\n" + "=" * 65)
    print("  MÉTRICAS POR INTENCIÓN")
    print("=" * 65)
    print(f"  {'Intención':<30} {'Prec':>6} {'Rec':>6} {'F1':>6} {'N':>5}")
    print("  " + "-" * 55)

    for intent, m in sorted(metricas["por_clase"].items()):
        icono = "✓" if m["f1"] >= 0.8 else ("⚠" if m["f1"] >= 0.5 else "✗")
        print(
            f"  {icono} {intent:<28} "
            f"{m['precision']*100:>5.1f}% "
            f"{m['recall']*100:>5.1f}% "
            f"{m['f1']*100:>5.1f}% "
            f"{m['soporte']:>5}"
        )

    # Matriz de confusión
    imprimir_matriz_confusion(matriz, intents)

    # ---- Errores detallados ----
    if errores:
        print("=" * 65)
        print(f"  ERRORES DETALLADOS ({len(errores)} casos)")
        print("=" * 65)
        for e in errores:
            print(f"\n  Texto    : \"{e['texto']}\"")
            print(f"  Esperado : {e['esperado']}")
            print(f"  Predicho : {e['predicho']}  (confianza: {e['conf']:.3f})")

    # ---- Interpretación para el diplomado ----
    print("\n" + "=" * 65)
    print("  INTERPRETACIÓN DE RESULTADOS")
    print("=" * 65)
    acc = metricas["accuracy"] * 100
    if acc >= 85:
        nivel = "BUENO ✓"
        consejo = "El clasificador funciona bien para producción académica."
    elif acc >= 70:
        nivel = "ACEPTABLE ⚠"
        consejo = "Considera agregar más ejemplos a los intents con F1 bajo."
    else:
        nivel = "NECESITA MEJORA ✗"
        consejo = "Revisa los intents confundidos y agrega ejemplos más variados."

    print(f"\n  Nivel general: {nivel}")
    print(f"  Consejo      : {consejo}")
    print(f"\n  Benchmark de referencia:")
    print(f"  - Accuracy >= 85%  → Bueno para demo académica")
    print(f"  - Accuracy >= 70%  → Aceptable con ajustes")
    print(f"  - Accuracy <  70%  → Necesita más ejemplos de entrenamiento")
    print()


if __name__ == "__main__":
    main()
