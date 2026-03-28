from collections import defaultdict

from app.services.intent_service import IntentService
from app.services.router import ConversationRouter
from app.services.state_store import InMemoryStateStore


TEST_CASES = [
    # =========================================================
    # FORMALIZACION_NEGOCIO (4)
    # =========================================================
    {
        "text": "Quiero saber qué necesito para formalizar mi negocio",
        "expected_intent": "formalizacion_negocio",
    },
    {
        "text": "Cómo saco mi RUC para empezar mi negocio",
        "expected_intent": "formalizacion_negocio",
    },
    {
        "text": "Qué pasos debo seguir para formalizar una empresa pequeña",
        "expected_intent": "formalizacion_negocio",
    },
    {
        "text": "Qué debo hacer para registrar mi negocio ante SUNAT",
        "expected_intent": "formalizacion_negocio",
    },

    # =========================================================
    # MULTAS_Y_SANCIONES (4)
    # =========================================================
    {
        "text": "Me llegó una multa por declarar fuera de fecha",
        "expected_intent": "multas_y_sanciones",
    },
    {
        "text": "Qué pasa si no presenté mi declaración a tiempo",
        "expected_intent": "multas_y_sanciones",
    },
    {
        "text": "Quiero saber cuánto me pueden cobrar de multa por no declarar",
        "expected_intent": "multas_y_sanciones",
    },
    {
        "text": "Hay sanción si no cumplo con mis obligaciones tributarias",
        "expected_intent": "multas_y_sanciones",
    },

    # =========================================================
    # REGIMENES_TRIBUTARIOS (4)
    # =========================================================
    {
        "text": "Qué régimen tributario me conviene para una bodega pequeña",
        "expected_intent": "regimenes_tributarios",
    },
    {
        "text": "Cuál es la diferencia entre NRUS y RER",
        "expected_intent": "regimenes_tributarios",
    },
    {
        "text": "Cómo saber en qué régimen tributario debería estar mi negocio",
        "expected_intent": "regimenes_tributarios",
    },
    {
        "text": "Qué régimen me conviene si recién empiezo a vender",
        "expected_intent": "regimenes_tributarios",
    },

    # =========================================================
    # COMPROBANTES_PAGO (4)
    # =========================================================
    {
        "text": "Cómo emito una boleta o factura",
        "expected_intent": "comprobantes_pago",
    },
    {
        "text": "Qué comprobante de pago debo entregar a mi cliente",
        "expected_intent": "comprobantes_pago",
    },
    {
        "text": "Cuándo corresponde emitir factura y cuándo boleta",
        "expected_intent": "comprobantes_pago",
    },
    {
        "text": "Quiero saber cómo generar comprobantes de pago",
        "expected_intent": "comprobantes_pago",
    },

    # =========================================================
    # CRONOGRAMA_OBLIGACIONES (4)
    # =========================================================
    {
        "text": "Cuándo vence mi declaración mensual",
        "expected_intent": "cronograma_obligaciones",
    },
    {
        "text": "Cuál es la fecha límite para declarar impuestos este mes",
        "expected_intent": "cronograma_obligaciones",
    },
    {
        "text": "Dónde consulto el cronograma de vencimientos de SUNAT",
        "expected_intent": "cronograma_obligaciones",
    },
    {
        "text": "Qué día me toca presentar mis obligaciones tributarias",
        "expected_intent": "cronograma_obligaciones",
    },
]


def run_tests() -> None:
    state_store = InMemoryStateStore()
    intent_service = IntentService()
    router = ConversationRouter()

    total_correct = 0
    per_intent_stats = defaultdict(lambda: {"correct": 0, "total": 0})

    print("\n" + "=" * 100)
    print("BATCH TEST - NLU + ROUTER (20 CASOS)")
    print("=" * 100)

    for i, case in enumerate(TEST_CASES, start=1):
        state = state_store.get(f"session-{i}")

        intent_result = intent_service.classify_topic(
            text=case["text"],
            context={}
        )

        decision = router.decide(
            message=case["text"],
            intent_result=intent_result,
            state=state
        )

        expected_intent = case["expected_intent"]
        predicted_intent = intent_result.intent

        is_correct = predicted_intent == expected_intent
        if is_correct:
            total_correct += 1

        per_intent_stats[expected_intent]["total"] += 1
        if is_correct:
            per_intent_stats[expected_intent]["correct"] += 1

        print("\n" + "-" * 100)
        print(f"TEST #{i}")
        print(f"INPUT: {case['text']}")
        print(f"EXPECTED INTENT: {expected_intent}")
        print(f"PREDICTED INTENT: {predicted_intent}")
        print(f"CONFIDENCE: {intent_result.confidence:.2f}")
        print(f"ACTION: {decision.action}")
        print(f"TOOL: {decision.tool_name}")
        print("TOP 3 LABELS:")
        for ranked in intent_result.ranked_labels[:3]:
            print(f"  - {ranked.label}: {ranked.score:.2f}")
        print(f"RESULT: {'OK' if is_correct else 'FAIL'}")

    total_cases = len(TEST_CASES)
    overall_accuracy = total_correct / total_cases

    print("\n" + "=" * 100)
    print("RESUMEN GENERAL")
    print("=" * 100)
    print(f"TOTAL CORRECTOS: {total_correct}/{total_cases}")
    print(f"ACCURACY GLOBAL: {overall_accuracy:.2f}")

    print("\n" + "=" * 100)
    print("ACCURACY POR INTENCION")
    print("=" * 100)

    for intent_name, stats in per_intent_stats.items():
        accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0.0
        print(
            f"- {intent_name}: "
            f"{stats['correct']}/{stats['total']} = {accuracy:.2f}"
        )


if __name__ == "__main__":
    run_tests()