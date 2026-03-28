# app/services/tool_executor.py
"""
Ejecutor de tools conversacionales (flujos guiados multi-turno).

Una "tool" en este sistema es un flujo de preguntas secuenciales donde el chatbot
guía al usuario paso a paso para obtener información específica y luego generar
una respuesta personalizada (checklist, recomendación de régimen, etc.).

¿Por qué flujos multi-turno?
Porque algunas preguntas tributarias no se responden con un solo mensaje.
Para recomendar el régimen correcto, necesitas saber cuánto vende el negocio,
si emite facturas, cuántos trabajadores tiene, etc. Es mejor preguntar de a poco.

Tools disponibles:
1. build_formalization_checklist → checklist de formalización personalizado
2. compare_tax_regimes          → recomendación de régimen según perfil del negocio
3. handle_fines_guidance        → orientación básica sobre multas (redirige a RAG)
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.services.state_store import ConversationState


class ToolExecutor:
    """
    Ejecuta tools especializadas según el nombre resuelto por el ConversationRouter.

    Cada tool tiene:
    - Una lista de pasos (preguntas secuenciales).
    - Lógica para guardar respuestas en state.entities.
    - Un método de "resumen final" que genera la respuesta cuando se completan todos los pasos.
    """

    # ------------------------------------------------------------------
    # Pasos del flujo de FORMALIZACIÓN
    # ------------------------------------------------------------------
    FORMALIZATION_STEPS = [
        {
            "key": "has_ruc",
            "question": "¿Tu negocio ya tiene RUC? Responde: sí o no.",
        },
        {
            "key": "person_type",
            "question": "¿Eres persona natural o jurídica?",
        },
        {
            "key": "economic_activity",
            "question": (
                "¿Qué tipo de actividad económica realizas?\n"
                "Ejemplo: ventas, servicios, restaurante, tienda, consultoría."
            ),
        },
        {
            "key": "voucher_type",
            "question": "¿Emitirás boletas, facturas o ambos?",
        },
        {
            "key": "has_employees",
            "question": "¿Tendrás trabajadores? Responde: sí o no.",
        },
    ]

    # ------------------------------------------------------------------
    # Pasos del flujo de REGÍMENES TRIBUTARIOS
    # ------------------------------------------------------------------
    TAX_REGIME_STEPS = [
        {
            "key": "monthly_sales",
            "question": (
                "Para ayudarte a elegir el régimen correcto, necesito algunos datos.\n\n"
                "¿Cuánto factura o planeas facturar tu negocio al mes?\n"
                "Opciones:\n"
                "  a) Menos de S/ 5,000\n"
                "  b) Entre S/ 5,000 y S/ 8,000\n"
                "  c) Entre S/ 8,000 y S/ 43,750 (hasta S/ 525,000 al año)\n"
                "  d) Más de S/ 43,750 al mes\n"
                "Responde con la letra o escribe el monto aproximado."
            ),
        },
        {
            "key": "needs_invoices",
            "question": (
                "¿Necesitas emitir facturas a empresas o instituciones?\n"
                "(Por ejemplo: si vendes a otras empresas que necesitan factura para su contabilidad)\n"
                "Responde: sí o no."
            ),
        },
        {
            "key": "worker_count",
            "question": (
                "¿Cuántos trabajadores tienes o planeas contratar?\n"
                "Opciones:\n"
                "  a) Ninguno (trabajo solo)\n"
                "  b) Entre 1 y 10 trabajadores\n"
                "  c) Más de 10 trabajadores\n"
                "Responde con la letra o número."
            ),
        },
    ]

    def __init__(self, rag_service=None) -> None:
        """
        Args:
            rag_service: instancia de RagService para buscar información documental
                         al finalizar algunos flujos. Opcional: si no se pasa,
                         el flujo funciona igual pero sin recuperación documental.
        """
        # Guardamos referencia al RagService para usarlo al final de los flujos
        # Esto es "inyección de dependencias": tool_executor no crea el rag_service,
        # lo recibe desde afuera (desde main.py), lo que hace el código más testeable.
        self.rag_service = rag_service

    # ------------------------------------------------------------------
    # Punto de entrada principal
    # ------------------------------------------------------------------

    def execute(self, tool_name: str, message: str, state: ConversationState) -> str:
        """
        Despacha la ejecución a la tool correspondiente.

        Args:
            tool_name: nombre de la tool a ejecutar (viene del ConversationRouter).
            message: mensaje actual del usuario.
            state: estado conversacional de la sesión.

        Returns:
            Texto de respuesta para el usuario.
        """
        if tool_name == "build_formalization_checklist":
            return self._build_formalization_checklist(message, state)

        if tool_name == "compare_tax_regimes":
            return self._compare_tax_regimes(message, state)

        if tool_name == "handle_fines_guidance":
            return self._handle_fines_guidance(message, state)

        # Fallback si llega un nombre de tool desconocido
        return (
            f"La tool '{tool_name}' aún no tiene implementación. "
            "Pero el routing funcionó correctamente."
        )

    # ------------------------------------------------------------------
    # TOOL 1: Formalización del negocio
    # ------------------------------------------------------------------

    def _build_formalization_checklist(
        self,
        message: str,
        state: ConversationState,
    ) -> str:
        """
        Flujo guiado multi-turno para formalización del negocio.

        Hace 5 preguntas secuenciales y genera un checklist personalizado al final.
        Guarda el progreso en state.entities["formalization_flow"].

        Estructura de state.entities["formalization_flow"]:
        {
            "started": True,
            "step": 3,                  # siguiente pregunta a hacer (1-indexed)
            "has_ruc": "no",
            "person_type": "natural",
            "economic_activity": "bodega",
            "voucher_type": "boletas",
            "has_employees": "sí",
        }
        """
        state.menu_context = "formalizacion_negocio"

        # Obtiene o inicializa el dict de progreso del flujo
        flow_data = state.entities.setdefault("formalization_flow", {})
        current_step = flow_data.get("step", 0)

        # --- Caso 1: primer ingreso al flujo ---
        if current_step == 0 and "started" not in flow_data:
            flow_data["started"] = True
            flow_data["step"] = 1

            return (
                "Perfecto. Iniciemos el flujo de formalización del negocio.\n\n"
                "Te haré unas preguntas cortas para construir un checklist educativo "
                "personalizado para tu situación.\n\n"
                f"Pregunta 1 de {len(self.FORMALIZATION_STEPS)}: "
                f"{self.FORMALIZATION_STEPS[0]['question']}"
            )

        # --- Caso 2: guardar respuesta del paso anterior ---
        previous_index = current_step - 1
        if 0 <= previous_index < len(self.FORMALIZATION_STEPS):
            previous_key = self.FORMALIZATION_STEPS[previous_index]["key"]
            normalized_value = self._normalize_answer(previous_key, message)
            flow_data[previous_key] = normalized_value

        # --- Caso 3: si aún faltan preguntas, avanzar al siguiente paso ---
        if current_step < len(self.FORMALIZATION_STEPS):
            next_question = self.FORMALIZATION_STEPS[current_step]["question"]
            flow_data["step"] = current_step + 1
            return (
                f"Pregunta {current_step + 1} de {len(self.FORMALIZATION_STEPS)}: "
                f"{next_question}"
            )

        # --- Caso 4: flujo completado, generar resumen ---
        summary = self._build_formalization_summary(flow_data)

        # Limpiar tool activa para que el router no quede "atrapado" en este flujo
        state.active_tool = None

        # Guardar resultado final en entities por si otra parte del sistema lo necesita
        state.entities["formalization_result"] = {
            "has_ruc": flow_data.get("has_ruc"),
            "person_type": flow_data.get("person_type"),
            "economic_activity": flow_data.get("economic_activity"),
            "voucher_type": flow_data.get("voucher_type"),
            "has_employees": flow_data.get("has_employees"),
        }

        return summary

    def _build_formalization_summary(self, flow_data: Dict[str, Any]) -> str:
        """
        Genera el checklist educativo personalizado basado en las respuestas del flujo.

        Personaliza el checklist según:
        - Si ya tiene RUC o no.
        - Si tendrá empleados o no.
        """
        has_ruc = flow_data.get("has_ruc", "no especificado")
        person_type = flow_data.get("person_type", "no especificado")
        economic_activity = flow_data.get("economic_activity", "no especificado")
        voucher_type = flow_data.get("voucher_type", "no especificado")
        has_employees = flow_data.get("has_employees", "no especificado")

        # Checklist base que aplica a todos
        checklist = [
            "1. Definir claramente el tipo de contribuyente (persona natural o jurídica).",
            "2. Confirmar la actividad económica principal y su código CIIU.",
            "3. Revisar inscripción o actualización en RUC (sunat.gob.pe).",
            "4. Gestionar o validar acceso a Clave SOL.",
            "5. Verificar qué tipo de comprobantes emitirás.",
            "6. Evaluar el régimen tributario que mejor se adapta a tu perfil.",
        ]

        # Personalización: si no tiene RUC, agregar el paso de inscripción
        if str(has_ruc).lower() == "no":
            checklist.insert(2, "PRIORITARIO: Inscribirte al RUC en SUNAT.")

        # Personalización: si tendrá empleados, agregar obligaciones laborales
        if str(has_employees).lower() == "sí":
            checklist.append(
                "7. Revisar obligaciones laborales: ESSALUD (9%), "
                "sistema de pensiones (AFP/ONP) y planilla electrónica (PDT 601)."
            )

        checklist_text = "\n".join(checklist)

        return (
            "Flujo de formalización completado.\n\n"
            "Resumen del perfil registrado:\n"
            f"  • Tiene RUC: {has_ruc}\n"
            f"  • Tipo de persona: {person_type}\n"
            f"  • Actividad económica: {economic_activity}\n"
            f"  • Comprobantes a emitir: {voucher_type}\n"
            f"  • Tendrá trabajadores: {has_employees}\n\n"
            "Checklist educativo personalizado:\n"
            f"{checklist_text}\n\n"
            "¿Qué quieres hacer ahora?\n"
            "  • Escribir 'regímenes' para comparar los regímenes tributarios.\n"
            "  • Hacer cualquier otra consulta sobre SUNAT."
        )

    # ------------------------------------------------------------------
    # TOOL 2: Comparación de regímenes tributarios
    # ------------------------------------------------------------------

    def _compare_tax_regimes(
        self,
        message: str,
        state: ConversationState,
    ) -> str:
        """
        Flujo guiado multi-turno para recomendar el régimen tributario ideal.

        Hace 3 preguntas sobre el negocio y luego recomienda el régimen más adecuado.
        Opcionalmente busca detalles en RAG si está disponible.

        Estructura de state.entities["tax_regime_flow"]:
        {
            "started": True,
            "step": 2,
            "monthly_sales": "b",          # categoría de ventas mensuales
            "needs_invoices": "sí",
            "worker_count": "a",
        }
        """
        state.menu_context = "regimenes_tributarios"

        flow_data = state.entities.setdefault("tax_regime_flow", {})
        current_step = flow_data.get("step", 0)

        # --- Caso 1: primer ingreso al flujo ---
        if current_step == 0 and "started" not in flow_data:
            flow_data["started"] = True
            flow_data["step"] = 1

            return (
                "Vamos a encontrar el régimen tributario ideal para tu negocio.\n\n"
                "Te haré 3 preguntas cortas. Con esas respuestas puedo darte una "
                "recomendación personalizada.\n\n"
                f"Pregunta 1 de {len(self.TAX_REGIME_STEPS)}: "
                f"{self.TAX_REGIME_STEPS[0]['question']}"
            )

        # --- Caso 2: guardar respuesta del paso anterior ---
        previous_index = current_step - 1
        if 0 <= previous_index < len(self.TAX_REGIME_STEPS):
            previous_key = self.TAX_REGIME_STEPS[previous_index]["key"]
            normalized_value = self._normalize_answer(previous_key, message)
            flow_data[previous_key] = normalized_value

        # --- Caso 3: si aún faltan preguntas, avanzar ---
        if current_step < len(self.TAX_REGIME_STEPS):
            next_question = self.TAX_REGIME_STEPS[current_step]["question"]
            flow_data["step"] = current_step + 1
            return (
                f"Pregunta {current_step + 1} de {len(self.TAX_REGIME_STEPS)}: "
                f"{next_question}"
            )

        # --- Caso 4: flujo completado, generar recomendación ---
        recommendation = self._build_regime_recommendation(flow_data, state)

        # Limpiar tool activa
        state.active_tool = None

        # Guardar perfil para uso posterior
        state.entities["tax_regime_result"] = {
            "monthly_sales": flow_data.get("monthly_sales"),
            "needs_invoices": flow_data.get("needs_invoices"),
            "worker_count": flow_data.get("worker_count"),
        }

        return recommendation

    def _build_regime_recommendation(
        self,
        flow_data: Dict[str, Any],
        state: ConversationState,
    ) -> str:
        """
        Determina el régimen recomendado basándose en las respuestas del usuario
        y agrega información documental del RAG si está disponible.

        Lógica de recomendación:
        - No necesita facturas + ventas ≤ S/8,000/mes → Nuevo RUS
        - Necesita facturas + ventas ≤ S/43,750/mes → RER
        - Necesita facturas + ventas mayores o planea crecer → RMT
        """
        monthly_sales = str(flow_data.get("monthly_sales", "")).lower()
        needs_invoices = str(flow_data.get("needs_invoices", "")).lower()
        worker_count = str(flow_data.get("worker_count", "")).lower()

        # --- Lógica de recomendación ---
        # Determinar rango de ventas
        ventas_bajo = any(x in monthly_sales for x in ["a)", "a ", "menos", "5000", "5,000"])
        ventas_medio_bajo = any(x in monthly_sales for x in ["b)", "b ", "8000", "8,000"])
        ventas_medio = any(x in monthly_sales for x in ["c)", "c ", "43750", "43,750", "525000"])
        ventas_alto = any(x in monthly_sales for x in ["d)", "d ", "mayor", "más de"])

        necesita_facturas = needs_invoices in {"sí", "si", "s", "yes"}

        # Árboles de decisión
        if not necesita_facturas and (ventas_bajo or ventas_medio_bajo):
            regime = "Nuevo RUS"
            reason = (
                "No necesitas emitir facturas y tus ventas están dentro del límite "
                "del Nuevo RUS (hasta S/ 8,000/mes). Es el régimen más simple y económico."
            )
            detail_query = "Nuevo RUS cuota mensual límite ingresos"

        elif necesita_facturas and (ventas_bajo or ventas_medio_bajo or ventas_medio):
            regime = "Régimen Especial de Renta (RER)"
            reason = (
                "Necesitas emitir facturas y tus ventas no superan S/ 43,750 al mes "
                "(S/ 525,000 al año). El RER te permite facturar con una contabilidad simple "
                "y pagar solo 1.5% de tus ingresos como Renta."
            )
            detail_query = "Régimen Especial RER límite ingresos impuesto 1.5%"

        elif ventas_alto or necesita_facturas:
            regime = "Régimen MYPE Tributario (RMT)"
            reason = (
                "El Régimen MYPE Tributario es ideal para tu perfil. "
                "Te permite emitir todos los comprobantes, sin límite de ingresos, "
                "con una tasa de Impuesto a la Renta preferencial del 10% sobre "
                "las primeras 15 UIT de utilidad."
            )
            detail_query = "Régimen MYPE Tributario tasa 10% beneficios"

        else:
            # Caso ambiguo: recomendar RMT como opción segura
            regime = "Régimen MYPE Tributario (RMT)"
            reason = (
                "Basándome en tu perfil, el Régimen MYPE Tributario es la opción "
                "más flexible para una MYPE. Permite crecer sin cambiar de régimen "
                "y tiene la tasa de IR más conveniente."
            )
            detail_query = "Régimen MYPE Tributario requisitos beneficios"

        # --- Construir respuesta base ---
        response_lines = [
            f"Análisis completado. Mi recomendación para tu negocio es:\n",
            f"RÉGIMEN RECOMENDADO: {regime}\n",
            f"¿Por qué? {reason}\n",
        ]

        # --- Enriquecer con RAG si está disponible ---
        if self.rag_service and self.rag_service.is_indexed():
            rag_results = self.rag_service.search(detail_query, n_results=1)
            if rag_results:
                best_result = rag_results[0]
                response_lines.append("Información adicional de los documentos SUNAT:\n")
                response_lines.append(best_result["text"])
                response_lines.append("")

        # --- Pie con siguiente paso ---
        response_lines.append(
            "¿Quieres saber más sobre este régimen o comparar con otras opciones? "
            "Puedes preguntarme con más detalle."
        )

        return "\n".join(response_lines)

    # ------------------------------------------------------------------
    # TOOL 3: Orientación sobre multas y sanciones
    # ------------------------------------------------------------------

    def _handle_fines_guidance(
        self,
        message: str,
        state: ConversationState,
    ) -> str:
        """
        Orientación sobre multas y sanciones. Redirige al RAG para los detalles.

        Esta tool es un "pre-RAG": da un menú inicial orientativo y luego
        deja que el RAG responda las preguntas específicas del usuario.
        """
        state.menu_context = "multas_y_sanciones"
        # Esta tool no tiene flujo multi-turno: solo orienta y libera el control
        state.active_tool = None

        return (
            "Entiendo que tienes dudas sobre multas y sanciones tributarias.\n\n"
            "Puedo ayudarte con los siguientes temas:\n"
            "  • Infracciones por no presentar declaraciones a tiempo.\n"
            "  • Cómo calcular y reducir tu multa con el Régimen de Gradualidad.\n"
            "  • Fraccionamiento de deudas tributarias.\n"
            "  • Consejos para evitar sanciones en el futuro.\n\n"
            "¿Sobre qué tema específico quieres consultar? "
            "Escribe tu pregunta y buscaré en los documentos SUNAT."
        )

    # ------------------------------------------------------------------
    # Normalización de respuestas
    # ------------------------------------------------------------------

    def _normalize_answer(self, key: str, value: str) -> str:
        """
        Normaliza las respuestas del usuario para estandarizar el procesamiento.

        Ejemplos:
        - "sí", "si", "yes", "s" → "sí"
        - "persona juridica" → "jurídica"
        - "ambos tipos" → "ambos"

        Args:
            key: nombre del campo (has_ruc, person_type, etc.)
            value: respuesta libre del usuario.

        Returns:
            Valor normalizado.
        """
        normalized = value.strip().lower()

        # Normalización de respuestas sí/no
        if key in {"has_ruc", "has_employees", "needs_invoices"}:
            if normalized in {"si", "sí", "s", "yes", "claro", "correcto", "afirmativo"}:
                return "sí"
            if normalized in {"no", "n", "nope", "negativo"}:
                return "no"

        # Normalización del tipo de persona
        if key == "person_type":
            if "jurid" in normalized or "empresa" in normalized or "sociedad" in normalized:
                return "jurídica"
            if "natural" in normalized or "persona" in normalized:
                return "natural"

        # Normalización del tipo de comprobante
        if key == "voucher_type":
            tiene_factura = "factura" in normalized
            tiene_boleta = "boleta" in normalized
            if "ambos" in normalized or (tiene_factura and tiene_boleta):
                return "ambos"
            if tiene_factura:
                return "facturas"
            if tiene_boleta:
                return "boletas"

        # Para campos de texto libre (actividad económica, ventas mensuales, trabajadores)
        # devolvemos el valor tal cual pero limpio
        return value.strip()
