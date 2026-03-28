# app/data/test_cases/intent_test_cases.py
"""
Casos de prueba para evaluar el clasificador de intenciones.

IMPORTANTE: estos ejemplos deben ser DISTINTOS a los de intent_examples.py.
Si usamos los mismos ejemplos de entrenamiento para evaluar, el resultado
será artificialmente alto (el modelo los "memorizó").

Estos casos simulan cómo un usuario real escribiría sus consultas:
- con errores de ortografía
- con frases cortas o informales
- con variaciones de vocabulario que no están en los ejemplos de entrenamiento

Formato de cada caso:
{
    "text": "lo que escribe el usuario",
    "expected_intent": "nombre_del_intent_esperado"
}
"""

INTENT_TEST_CASES = [
    # -----------------------------------------------------------------------
    # formalizacion_negocio
    # -----------------------------------------------------------------------
    {
        "text": "Quiero abrir mi primera empresa, por dónde empiezo",
        "expected_intent": "formalizacion_negocio",
    },
    {
        "text": "Cómo inscribo mi negocio en SUNAT",
        "expected_intent": "formalizacion_negocio",
    },
    {
        "text": "Necesito el RUC para mi bodega",
        "expected_intent": "formalizacion_negocio",
    },
    {
        "text": "Me quiero formalizar como persona natural con negocio",
        "expected_intent": "formalizacion_negocio",
    },
    {
        "text": "Cómo registro mi empresa ante la SUNAT",
        "expected_intent": "formalizacion_negocio",
    },

    # -----------------------------------------------------------------------
    # multas_y_sanciones
    # -----------------------------------------------------------------------
    {
        "text": "Me olvidé de declarar el mes pasado, qué hago",
        "expected_intent": "multas_y_sanciones",
    },
    {
        "text": "Cuánto es la multa por declarar tarde",
        "expected_intent": "multas_y_sanciones",
    },
    {
        "text": "SUNAT me mandó una notificación por deuda",
        "expected_intent": "multas_y_sanciones",
    },
    {
        "text": "Cómo pago una sanción tributaria",
        "expected_intent": "multas_y_sanciones",
    },
    {
        "text": "Puedo reducir mi multa si declaro ahora",
        "expected_intent": "multas_y_sanciones",
    },

    # -----------------------------------------------------------------------
    # regimenes_tributarios
    # -----------------------------------------------------------------------
    {
        "text": "Qué régimen me conviene para mi tiendita",
        "expected_intent": "regimenes_tributarios",
    },
    {
        "text": "Diferencia entre RUS y régimen especial",
        "expected_intent": "regimenes_tributarios",
    },
    {
        "text": "Estoy en el RUS pero quiero emitir facturas",
        "expected_intent": "regimenes_tributarios",
    },
    {
        "text": "Mi negocio creció y creo que debo cambiar de régimen",
        "expected_intent": "regimenes_tributarios",
    },
    {
        "text": "Cuál es la tasa del MYPE tributario",
        "expected_intent": "regimenes_tributarios",
    },

    # -----------------------------------------------------------------------
    # comprobantes_pago
    # -----------------------------------------------------------------------
    {
        "text": "Cuándo tengo que dar factura y cuándo boleta",
        "expected_intent": "comprobantes_pago",
    },
    {
        "text": "Cómo emito comprobantes electrónicos",
        "expected_intent": "comprobantes_pago",
    },
    {
        "text": "Mi cliente me pide factura, cómo la hago",
        "expected_intent": "comprobantes_pago",
    },
    {
        "text": "Qué diferencia hay entre nota de crédito y nota de débito",
        "expected_intent": "comprobantes_pago",
    },
    {
        "text": "Puedo emitir boletas si estoy en el RUS",
        "expected_intent": "comprobantes_pago",
    },

    # -----------------------------------------------------------------------
    # cronograma_obligaciones
    # -----------------------------------------------------------------------
    {
        "text": "Cuándo tengo que pagar mis impuestos este mes",
        "expected_intent": "cronograma_obligaciones",
    },
    {
        "text": "Mi RUC termina en 4, cuándo vence mi declaración",
        "expected_intent": "cronograma_obligaciones",
    },
    {
        "text": "Qué pasa si declaro después de la fecha",
        "expected_intent": "cronograma_obligaciones",
    },
    {
        "text": "Cómo sé la fecha límite para declarar",
        "expected_intent": "cronograma_obligaciones",
    },
    {
        "text": "El cronograma de SUNAT según el RUC",
        "expected_intent": "cronograma_obligaciones",
    },
]
