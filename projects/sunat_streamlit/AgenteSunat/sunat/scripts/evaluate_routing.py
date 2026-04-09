#!/usr/bin/env python
# scripts/evaluate_routing.py
"""
Evaluación end-to-end del sistema de routing conversacional.

¿QUÉ MIDE ESTE SCRIPT?
Simula mensajes completos de usuario y verifica que el sistema tome
la ACCIÓN CORRECTA en cada caso. Evalúa el pipeline completo:

    mensaje → IntentService → ConversationRouter → ¿acción correcta?

Las acciones posibles son:
    - use_tool   → activar un flujo guiado (formalización, regímenes)
    - use_rag    → buscar en documentos SUNAT
    - clarify    → pedir aclaración al usuario (mensaje ambiguo)

¿POR QUÉ ESTO ES IMPORTANTE?
El intent puede estar bien clasificado pero el router puede decidir mal.
Por ejemplo: el intent es "multas_y_sanciones" → el router debería ir a RAG,
pero si hay un bug podría ir a clarify o a una tool inexistente.

MÉTRICAS:
    - Routing Accuracy: % de mensajes donde se tomó la acción correcta
    - Accuracy por acción: ¿en cuáles tipos de acción falla más?

USO:
    cd sunat/
    python scripts/evaluate_routing.py
    python scripts/evaluate_routing.py --verbose
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Optional

# Agregar el directorio raíz al path para importar app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.intent_service import IntentService
from app.services.router import ConversationRouter
from app.services.state_store import InMemoryStateStore
from app.core.constants import ACTION_USE_TOOL, ACTION_USE_RAG, ACTION_CLARIFY


# ---------------------------------------------------------------------------
# Casos de prueba de routing
# ---------------------------------------------------------------------------

ROUTING_TEST_CASES = [
    # -----------------------------------------------------------------------
    # Mensajes que deben activar la TOOL de formalización
    # -----------------------------------------------------------------------
    {
        "message": "Quiero formalizar mi negocio",
        "expected_action": ACTION_USE_TOOL,
        "expected_tool":   "build_formalization_checklist",
        "description":     "Inicio de flujo de formalización",
    },
    {
        "message": "Cómo saco mi RUC",
        "expected_action": ACTION_USE_TOOL,
        "expected_tool":   "build_formalization_checklist",
        "description":     "Consulta RUC → debe activar tool de formalización",
    },
    {
        "message": "Necesito registrar mi empresa ante SUNAT",
        "expected_action": ACTION_USE_TOOL,
        "expected_tool":   "build_formalization_checklist",
        "description":     "Registro empresa → tool de formalización",
    },

    # -----------------------------------------------------------------------
    # Mensajes que deben activar la TOOL de regímenes tributarios
    # -----------------------------------------------------------------------
    {
        "message": "Qué régimen tributario me conviene",
        "expected_action": ACTION_USE_TOOL,
        "expected_tool":   "compare_tax_regimes",
        "description":     "Comparar regímenes → tool de regímenes",
    },
    {
        "message": "Diferencia entre Nuevo RUS y RER",
        "expected_action": ACTION_USE_TOOL,
        "expected_tool":   "compare_tax_regimes",
        "description":     "Consulta RUS vs RER → tool de regímenes",
    },

    # -----------------------------------------------------------------------
    # Mensajes que deben ir a RAG (consultas documentales)
    # -----------------------------------------------------------------------
    {
        "message": "Cuánto es la multa por no declarar a tiempo",
        "expected_action": ACTION_USE_RAG,
        "expected_tool":   None,
        "description":     "Multas → RAG (no hay tool para multas)",
    },
    {
        "message": "Cuándo vence mi declaración mensual",
        "expected_action": ACTION_USE_RAG,
        "expected_tool":   None,
        "description":     "Cronograma → RAG",
    },
    {
        "message": "Cómo emito una factura electrónica",
        "expected_action": ACTION_USE_RAG,
        "expected_tool":   None,
        "description":     "Comprobantes → RAG",
    },
    {
        "message": "Me llegó una notificación de SUNAT por deuda",
        "expected_action": ACTION_USE_RAG,
        "expected_tool":   None,
        "description":     "Sanciones → RAG",
    },

    # -----------------------------------------------------------------------
    # Mensajes ambiguos que deben pedir CLARIFICACIÓN
    # -----------------------------------------------------------------------
    {
        "message": "hola",
        "expected_action": ACTION_CLARIFY,
        "expected_tool":   None,
        "description":     "Saludo sin contexto → clarificación",
    },
    {
        "message": "tengo un problema",
        "expected_action": ACTION_CLARIFY,
        "expected_tool":   None,
        "description":     "Mensaje vago → clarificación",
    },
    {
        "message": "xyz",
        "expected_action": ACTION_CLARIFY,
        "expected_tool":   None,
        "description":     "Texto sin sentido → clarificación",
    },
]


# ---------------------------------------------------------------------------
# Script principal
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Evalúa el sistema de routing end-to-end del chatbot SUNAT."
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Muestra el detalle de cada caso evaluado.",
    )
    args = parser.parse_args()

    print("\n" + "=" * 65)
    print("  EVALUACIÓN DE ROUTING END-TO-END")
    print("=" * 65)
    print("\n  Cargando servicios...")

    # Inicializar los servicios necesarios
    intent_classifier = IntentService()
    router            = ConversationRouter()
    state_store       = InMemoryStateStore()

    print(f"  Servicios listos. Evaluando {len(ROUTING_TEST_CASES)} casos...\n")

    # Contadores
    correctos = 0
    errores   = []

    # Contadores por tipo de acción esperada
    por_accion_total   = defaultdict(int)
    por_accion_acierto = defaultdict(int)

    for i, caso in enumerate(ROUTING_TEST_CASES):
        message       = caso["message"]
        exp_action    = caso["expected_action"]
        exp_tool      = caso["expected_tool"]
        description   = caso["description"]

        # Usamos un session_id único por caso para no contaminar estado entre tests
        session_id = f"eval-routing-{i}"
        state      = state_store.get(session_id)

        # Clasificar intención
        intent_result = intent_classifier.classify_topic(message)

        # Decidir ruta
        decision = router.decide(
            message=message,
            intent_result=intent_result,
            state=state,
        )

        # Verificar si la acción es correcta
        accion_correcta = (decision.action == exp_action)

        # Si esperamos una tool específica, verificarla también
        tool_correcta = True
        if exp_tool is not None:
            tool_correcta = (decision.tool_name == exp_tool)

        es_correcto = accion_correcta and tool_correcta

        # Acumular contadores
        por_accion_total[exp_action] += 1
        if es_correcto:
            correctos += 1
            por_accion_acierto[exp_action] += 1
        else:
            errores.append({
                "message":     message,
                "description": description,
                "exp_action":  exp_action,
                "got_action":  decision.action,
                "exp_tool":    exp_tool,
                "got_tool":    decision.tool_name,
                "intent":      intent_result.intent,
                "confidence":  intent_result.confidence,
                "reason":      decision.reason,
            })

        # Verbose: imprimir cada caso
        if args.verbose:
            marca = "✓" if es_correcto else "✗"
            print(f"  {marca} [{intent_result.confidence:.2f}] '{message}'")
            print(f"      Descripción : {description}")
            print(f"      Intent      : {intent_result.intent}")
            print(f"      Esperado    : {exp_action}" + (f" / tool={exp_tool}" if exp_tool else ""))
            print(f"      Obtuvo      : {decision.action}" + (f" / tool={decision.tool_name}" if decision.tool_name else ""))
            if not es_correcto:
                print(f"      Razón router: {decision.reason}")
            print()

    # ---- Resultados globales ----
    n = len(ROUTING_TEST_CASES)
    accuracy = correctos / n

    print("=" * 65)
    print("  RESULTADOS GLOBALES")
    print("=" * 65)
    print(f"  Casos evaluados  : {n}")
    print(f"  Correctos        : {correctos}")
    print(f"  Errores          : {len(errores)}")
    print(f"  Routing Accuracy : {accuracy * 100:.1f}%")

    # ---- Resultados por acción ----
    print("\n" + "=" * 65)
    print("  ACCURACY POR TIPO DE ACCIÓN")
    print("=" * 65)

    iconos_accion = {
        ACTION_USE_TOOL: "🔧",
        ACTION_USE_RAG:  "📄",
        ACTION_CLARIFY:  "❓",
    }

    for accion in [ACTION_USE_TOOL, ACTION_USE_RAG, ACTION_CLARIFY]:
        total   = por_accion_total.get(accion, 0)
        acierto = por_accion_acierto.get(accion, 0)
        if total > 0:
            pct   = acierto / total * 100
            icono = iconos_accion.get(accion, "•")
            marca = "✓" if pct >= 80 else ("⚠" if pct >= 60 else "✗")
            print(f"  {marca} {icono} {accion:<20} {acierto}/{total} = {pct:.0f}%")

    # ---- Errores detallados ----
    if errores:
        print("\n" + "=" * 65)
        print(f"  ERRORES DETALLADOS ({len(errores)} casos)")
        print("=" * 65)
        for e in errores:
            print(f"\n  Mensaje     : \"{e['message']}\"")
            print(f"  Descripción : {e['description']}")
            print(f"  Intent det. : {e['intent']} (conf={e['confidence']:.2f})")
            print(f"  Esperaba    : acción={e['exp_action']}" +
                  (f", tool={e['exp_tool']}" if e['exp_tool'] else ""))
            print(f"  Obtuvo      : acción={e['got_action']}" +
                  (f", tool={e['got_tool']}" if e['got_tool'] else ""))
            print(f"  Razón       : {e['reason']}")

    # ---- Interpretación ----
    print("\n" + "=" * 65)
    print("  INTERPRETACIÓN")
    print("=" * 65)

    if accuracy >= 0.85:
        nivel = "BUENO ✓"
        consejo = "El router toma decisiones correctas consistentemente."
    elif accuracy >= 0.70:
        nivel = "ACEPTABLE ⚠"
        consejo = (
            "Se recomienda revisar los casos que fallan. Posibles causas:\n"
            "  - Umbral de confianza muy alto/bajo (ajustar LOW_CONFIDENCE_THRESHOLD)\n"
            "  - Falta mapeo en TOOL_INTENT_TO_NAME o DOCUMENTAL_INTENTS"
        )
    else:
        nivel = "NECESITA MEJORA ✗"
        consejo = (
            "El routing tiene problemas estructurales. Se debe revisar:\n"
            "  - Las constantes en app/core/constants.py\n"
            "  - La lógica de decisión en app/services/router.py\n"
            "  - Los thresholds de confianza"
        )

    print(f"\n  Nivel general : {nivel}")
    print(f"  Consejo       : {consejo}")
    print(f"\n  Benchmark de referencia:")
    print(f"  - Routing Accuracy >= 85% → Sistema confiable para demo")
    print(f"  - Routing Accuracy >= 70% → Funciona con casos principales")
    print()


if __name__ == "__main__":
    main()
