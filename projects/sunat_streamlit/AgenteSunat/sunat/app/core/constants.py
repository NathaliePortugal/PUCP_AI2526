# app/core/constants.py

from typing import Dict, Set

TOPIC_LABELS = [
    "consulta sobre multas tributarias o sanciones",
    "consulta sobre cómo iniciar un negocio, sacar RUC o formalizar una empresa",
    "consulta sobre declaraciones mensuales o impuestos",
    "consulta sobre emisión de boletas, facturas o comprobantes de pago",
    "consulta sobre regímenes tributarios para negocios",
    "consulta sobre cronograma de vencimientos y fechas de obligación",
    "consulta documental general de SUNAT",
]

TOPIC_LABEL_TO_INTENT: Dict[str, str] = {
    "consulta sobre multas tributarias o sanciones": "multas_y_sanciones",
    "consulta sobre cómo iniciar un negocio, sacar RUC o formalizar una empresa": "formalizacion_negocio",
    "consulta sobre declaraciones mensuales o impuestos": "declaraciones_impuestos",
    "consulta sobre emisión de boletas, facturas o comprobantes de pago": "comprobantes_pago",
    "consulta sobre regímenes tributarios para negocios": "regimenes_tributarios",
    "consulta sobre cronograma de vencimientos y fechas de obligación": "cronograma_obligaciones",
    "consulta documental general de SUNAT": "consulta_documental_general",
}

DOCUMENTAL_INTENTS: Set[str] = {
    "multas_y_sanciones",
    "formalizacion_negocio",
    "declaraciones_impuestos",
    "comprobantes_pago",
    "regimenes_tributarios",
    "cronograma_obligaciones",
    "consulta_documental_general",
}

ACTION_GUIDED_RESPONSE = "guided_response"
ACTION_USE_RAG = "use_rag"
ACTION_USE_TOOL = "use_tool"
ACTION_CLARIFY = "clarify"

TOOL_INTENT_TO_NAME: Dict[str, str] = {
    "regimenes_tributarios": "compare_tax_regimes",
    "formalizacion_negocio": "build_formalization_checklist",
    "multas_y_sanciones": "handle_fines_guidance",
    "cronograma_obligaciones": "handle_schedule_guidance",
}

LOW_CONFIDENCE_THRESHOLD = 0.35
MEDIUM_CONFIDENCE_THRESHOLD = 0.50
HIGH_CONFIDENCE_THRESHOLD = 0.65

TOP_LABELS_TO_KEEP = 5