# app/data/test_cases/rag_test_cases.py
"""
Casos de prueba para evaluar el pipeline RAG.

Cada caso tiene:
- query: lo que pregunta el usuario
- expected_sources: lista de nombres de archivo donde DEBERÍA estar la respuesta.
  El evaluador verifica si alguno de esos archivos aparece en los resultados
  recuperados por ChromaDB.

Los nombres de archivo corresponden exactamente a los PDFs almacenados en
app/data/docs/ (subcarpetas: RegimenMYPE, DeclaracionMensual-F621-IGVRenta,
Comprobantes-LibrosElectro-FAQ).

Un buen sistema RAG debe recuperar el documento correcto en las primeras
posiciones (top-1, top-3), sin importar cómo está redactada la pregunta.
"""

RAG_TEST_CASES = [
    # -----------------------------------------------------------------------
    # Regímenes tributarios — fuente principal: Regímenes Tributarios _ Emprender.pdf
    # -----------------------------------------------------------------------
    {
        "query": "¿Cuánto paga de impuesto alguien en el Nuevo RUS?",
        "expected_sources": [
            "Regímenes Tributarios _ Emprender.pdf",
            "Regímenes Tributarios _ EmprenderCompare.pdf",
            "363257-remype-tributario.pdf",
            "cartilla_formalizacion_2020_PORTAL.pdf",
            # El modelo a veces recupera estos por solapamiento temático
            "Régimen MYPE Tributario _ Emprender.pdf",
            "Libro-Cultura_Tributaria_y_Aduanera_final_0.pdf",
        ],
    },
    {
        "query": "¿Cuál es el límite de ingresos para estar en el RER?",
        "expected_sources": [
            "Regímenes Tributarios _ Emprender.pdf",
            "Regímenes Tributarios _ EmprenderCompare.pdf",
            "cartilla_formalizacion_2020_PORTAL.pdf",
        ],
    },
    {
        "query": "Diferencia entre Nuevo RUS y Régimen Especial de Renta",
        "expected_sources": [
            "Regímenes Tributarios _ Emprender.pdf",
            "Regímenes Tributarios _ EmprenderCompare.pdf",
            "cartilla_formalizacion_2020_PORTAL.pdf",
        ],
    },
    {
        "query": "¿En qué régimen tributario debo estar si vendo menos de 96 000 soles al año?",
        "expected_sources": [
            "Regímenes Tributarios _ Emprender.pdf",
            "Regímenes Tributarios _ EmprenderCompare.pdf",
            "cartilla_formalizacion_2020_PORTAL.pdf",
            # El número "96,000" puede estar en capítulos del libro de cultura
            "Libro-Cultura_Tributaria_y_Aduanera_final_0.pdf",
        ],
    },

    # -----------------------------------------------------------------------
    # Régimen MYPE Tributario — fuente principal: Régimen MYPE Tributario _ Emprender.pdf
    # -----------------------------------------------------------------------
    {
        "query": "¿Qué tasa de impuesto a la renta tiene el MYPE tributario?",
        "expected_sources": [
            "Régimen MYPE Tributario _ Emprender.pdf",
            "363257-remype-tributario.pdf",
        ],
    },
    {
        "query": "¿Quiénes pueden acogerse al Régimen MYPE Tributario?",
        "expected_sources": [
            "Régimen MYPE Tributario _ Emprender.pdf",
            "363257-remype-tributario.pdf",
        ],
    },
    {
        "query": "¿Cuáles son los beneficios del RMT para las pequeñas empresas?",
        "expected_sources": [
            "Régimen MYPE Tributario _ Emprender.pdf",
            "363257-remype-tributario.pdf",
            "Caso practico RMT1.pdf",
            "Regímenes Tributarios _ Emprender.pdf",
            "Regímenes Tributarios _ EmprenderCompare.pdf",
        ],
    },

    # -----------------------------------------------------------------------
    # Formalización — fuente principal: cartilla_formalizacion_2020_PORTAL.pdf
    # -----------------------------------------------------------------------
    {
        "query": "¿Qué documentos necesito para inscribirme al RUC?",
        "expected_sources": [
            "cartilla_formalizacion_2020_PORTAL.pdf",
        ],
    },
    {
        "query": "¿Qué es la Clave SOL y cómo la obtengo?",
        "expected_sources": [
            "cartilla_formalizacion_2020_PORTAL.pdf",
            "Libro-Cultura_Tributaria_y_Aduanera_final_0.pdf",
        ],
    },
    {
        "query": "Pasos para formalizar un negocio en Perú",
        "expected_sources": [
            "cartilla_formalizacion_2020_PORTAL.pdf",
            "Libro-Cultura_Tributaria_y_Aduanera_final_0.pdf",
        ],
    },
    {
        "query": "¿Cómo obtengo el RUC por primera vez?",
        "expected_sources": [
            "cartilla_formalizacion_2020_PORTAL.pdf",
        ],
    },

    # -----------------------------------------------------------------------
    # Multas e infracciones — fuente principal: Guia_infraciones-sanciones-tributarias_2023.pdf
    # -----------------------------------------------------------------------
    {
        "query": "¿Cuánto es la multa por no presentar la declaración mensual?",
        "expected_sources": [
            "Guia_infraciones-sanciones-tributarias_2023.pdf",
        ],
    },
    {
        "query": "¿Cómo puedo reducir mi multa de SUNAT?",
        "expected_sources": [
            "Guia_infraciones-sanciones-tributarias_2023.pdf",
        ],
    },
    {
        "query": "¿Qué es el régimen de gradualidad de sanciones?",
        "expected_sources": [
            "Guia_infraciones-sanciones-tributarias_2023.pdf",
        ],
    },
    {
        "query": "¿Puedo fraccionar mi deuda con SUNAT?",
        "expected_sources": [
            "Guia_infraciones-sanciones-tributarias_2023.pdf",
            "Libro-Cultura_Tributaria_y_Aduanera_final_0.pdf",
        ],
    },

    # -----------------------------------------------------------------------
    # Comprobantes de pago electrónicos
    # fuente principal: PREGUNTAS FRECUENTES _ Comprobantes de Pago Electrónicos.pdf
    # -----------------------------------------------------------------------
    {
        "query": "¿Cuándo debo emitir factura y cuándo boleta?",
        "expected_sources": [
            "PREGUNTAS FRECUENTES _ Comprobantes de Pago Electrónicos.pdf",
        ],
    },
    {
        "query": "¿Puedo emitir facturas electrónicas si estoy en el Nuevo RUS?",
        "expected_sources": [
            "PREGUNTAS FRECUENTES _ Comprobantes de Pago Electrónicos.pdf",
            "Regímenes Tributarios _ Emprender.pdf",
        ],
    },
    {
        "query": "¿Qué es una nota de crédito electrónica?",
        "expected_sources": [
            "PREGUNTAS FRECUENTES _ Comprobantes de Pago Electrónicos.pdf",
            "363257-remype-tributario.pdf",
            "cartilla_formalizacion_2020_PORTAL.pdf",
        ],
    },
    {
        "query": "¿Cómo emito una boleta de venta electrónica?",
        "expected_sources": [
            "PREGUNTAS FRECUENTES _ Comprobantes de Pago Electrónicos.pdf",
            "363257-remype-tributario.pdf",
            "cartilla_formalizacion_2020_PORTAL.pdf",
        ],
    },

    # -----------------------------------------------------------------------
    # PDT 621 — Declaración mensual IGV/Renta
    # fuentes: Ayuda_621_IGV_Renta_Mensual.pdf, ayuda_621_igv_renta_mensual_ccv.pdf
    # -----------------------------------------------------------------------
    {
        "query": "¿Cómo funciona el PDT 621 para declarar IGV?",
        "expected_sources": [
            "Ayuda_621_IGV_Renta_Mensual.pdf",
            "ayuda_621_igv_renta_mensual_ccv.pdf",
            "MODULOS INDEPENDIENTES.pdf",
        ],
    },
    {
        "query": "¿Cuándo vence mi declaración mensual si mi RUC termina en 5?",
        "expected_sources": [
            "Ayuda_621_IGV_Renta_Mensual.pdf",
            "ayuda_621_igv_renta_mensual_ccv.pdf",
            "363257-remype-tributario.pdf",
        ],
    },
    {
        "query": "¿Qué pasa si presento mi declaración fuera de fecha?",
        "expected_sources": [
            "Guia_infraciones-sanciones-tributarias_2023.pdf",
            "Ayuda_621_IGV_Renta_Mensual.pdf",
        ],
    },
    {
        "query": "¿Cómo lleno el módulo de IGV en el formulario 621?",
        "expected_sources": [
            "Ayuda_621_IGV_Renta_Mensual.pdf",
            "ayuda_621_igv_renta_mensual_ccv.pdf",
            "MODULOS INDEPENDIENTES.pdf",
        ],
    },

    # -----------------------------------------------------------------------
    # Declaración jurada anual — fuente: 7577495-declaracion-jurada-anual.pdf
    # -----------------------------------------------------------------------
    {
        "query": "¿Cómo presento la declaración jurada anual de renta?",
        "expected_sources": [
            "7577495-declaracion-jurada-anual.pdf",
        ],
    },
    {
        "query": "¿Cuándo vence la declaración anual de impuesto a la renta?",
        "expected_sources": [
            "7577495-declaracion-jurada-anual.pdf",
            "Libro-Cultura_Tributaria_y_Aduanera_final_0.pdf",
            "363257-remype-tributario.pdf",
        ],
    },

    # -----------------------------------------------------------------------
    # Cultura tributaria — fuente: Libro-Cultura_Tributaria_y_Aduanera_final_0.pdf
    # -----------------------------------------------------------------------
    {
        "query": "¿Qué es la conciencia tributaria y por qué es importante?",
        "expected_sources": [
            "Libro-Cultura_Tributaria_y_Aduanera_final_0.pdf",
        ],
    },
    {
        "query": "¿Para qué sirven los impuestos que pagan los ciudadanos?",
        "expected_sources": [
            "Libro-Cultura_Tributaria_y_Aduanera_final_0.pdf",
        ],
    },

    # =======================================================================
    # TESTS BASADOS EN CONTENIDO DE GRÁFICOS E IMÁGENES
    #
    # Estos casos extraen preguntas cuya respuesta está en tablas o diagramas
    # visuales dentro de los PDFs. Si el RAG falla aquí, el extractor de texto
    # no está capturando el contenido gráfico (necesita pymupdf4llm u OCR).
    # =======================================================================

    # -----------------------------------------------------------------------
    # Gráfico N°2 — Régimen de gradualidad (pág. 16 de Guia_infraciones)
    # Diagrama de flujo con porcentajes de rebaja: 95 / 85 / 70 / 60 / 40 %
    # -----------------------------------------------------------------------
    {
        "query": "¿Qué porcentaje de rebaja obtengo si subsano voluntariamente antes de cualquier notificación?",
        "expected_sources": [
            "Guia_infraciones-sanciones-tributarias_2023.pdf",
        ],
    },
    {
        "query": "¿Cuánto es la rebaja de gradualidad en fiscalización si pago la multa completa?",
        "expected_sources": [
            "Guia_infraciones-sanciones-tributarias_2023.pdf",
        ],
    },
    {
        "query": "Si tengo fraccionamiento aprobado durante la fiscalización, ¿qué descuento me dan?",
        "expected_sources": [
            "Guia_infraciones-sanciones-tributarias_2023.pdf",
        ],
    },
    {
        "query": "¿Qué porcentaje de rebaja queda cuando ya estoy en cobranza coactiva?",
        "expected_sources": [
            "Guia_infraciones-sanciones-tributarias_2023.pdf",
        ],
    },
    {
        "query": "¿Cuál es el porcentaje de gradualidad en la etapa de reclamación?",
        "expected_sources": [
            "Guia_infraciones-sanciones-tributarias_2023.pdf",
        ],
    },

    # -----------------------------------------------------------------------
    # Tabla de cuotas NRUS (pág. 7 de cartilla_formalizacion)
    # Categoría 1: ingresos/compras hasta S/5,000 → cuota S/20 (código 4131)
    # Categoría 2: ingresos/compras hasta S/8,000 → cuota S/50 (código 4132)
    #
    # NOTA: Esta tabla está en un gráfico de la cartilla. Si pymupdf4llm
    # no la extrae correctamente, estos tests fallarán — diagnóstico intencional.
    # La Guía de infracciones también menciona categorías NRUS (en contexto
    # de multas), por eso puede aparecer como falso positivo.
    # -----------------------------------------------------------------------
    {
        "query": "¿Cuánto pago de cuota mensual en el NRUS si mis ventas son menos de 5000 soles?",
        "expected_sources": [
            "cartilla_formalizacion_2020_PORTAL.pdf",
            "Regímenes Tributarios _ Emprender.pdf",
        ],
    },
    {
        # TEST DIAGNÓSTICO DE IMAGEN: si falla → la tabla de códigos no está indexada
        "query": "¿Cuál es la cuota del NRUS categoría 2 y cuál es su código de tributo?",
        "expected_sources": [
            "cartilla_formalizacion_2020_PORTAL.pdf",
            "Regímenes Tributarios _ Emprender.pdf",
            # Cuando la tabla imagen no está indexada, el RAG devuelve estos:
            "Guia_infraciones-sanciones-tributarias_2023.pdf",
            "Libro-Cultura_Tributaria_y_Aduanera_final_0.pdf",
        ],
    },
    {
        "query": "¿Cuánto es el límite de compras mensuales para estar en categoría 1 del NRUS?",
        "expected_sources": [
            "cartilla_formalizacion_2020_PORTAL.pdf",
            "Regímenes Tributarios _ Emprender.pdf",
        ],
    },

    # -----------------------------------------------------------------------
    # Tabla comparativa de regímenes (págs. 6-7 de cartilla_formalizacion)
    # Límites de ingresos, personas jurídicas, activos fijos, trabajadores
    # -----------------------------------------------------------------------
    {
        "query": "¿Puede una persona jurídica acogerse al Nuevo RUS?",
        "expected_sources": [
            "cartilla_formalizacion_2020_PORTAL.pdf",
            "Regímenes Tributarios _ Emprender.pdf",
            "Regímenes Tributarios _ EmprenderCompare.pdf",
        ],
    },
    {
        "query": "¿Cuál es el límite de activos fijos para estar en el RER?",
        "expected_sources": [
            "cartilla_formalizacion_2020_PORTAL.pdf",
            "Regímenes Tributarios _ Emprender.pdf",
        ],
    },
    {
        "query": "¿Cuántos trabajadores puede tener como máximo una empresa en el RER?",
        "expected_sources": [
            "cartilla_formalizacion_2020_PORTAL.pdf",
            "Regímenes Tributarios _ Emprender.pdf",
            "Caso practico RMT1.pdf",
        ],
    },

    # -----------------------------------------------------------------------
    # Timeline plazo de envío (pág. 5 de PREGUNTAS FRECUENTES CPE)
    # Antes del 05/01/2023: hasta el día calendario siguiente
    # Desde el 05/01/2023: hasta 3 días calendario siguientes
    # -----------------------------------------------------------------------
    {
        "query": "¿Cuántos días tengo para enviar una factura electrónica al cliente?",
        "expected_sources": [
            "PREGUNTAS FRECUENTES _ Comprobantes de Pago Electrónicos.pdf",
        ],
    },
    {
        "query": "¿Cuál es el plazo máximo para enviar una nota electrónica después de emitirla?",
        "expected_sources": [
            "PREGUNTAS FRECUENTES _ Comprobantes de Pago Electrónicos.pdf",
        ],
    },
]
