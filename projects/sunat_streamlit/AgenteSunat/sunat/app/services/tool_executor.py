# app/services/tool_executor.py
"""
Wizards multi-turno para el chatbot SUNAT.

Cada wizard hace preguntas secuenciales al usuario, guarda las respuestas en
state.entities y genera un resultado personalizado al completarse.

Wizards disponibles:
- build_formalization_checklist : checklist de formalización según perfil del negocio
- compare_tax_regimes           : recomendación de régimen tributario
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.services.state_store import ConversationState


class ToolExecutor:
    """
    Ejecuta wizards guiados según el nombre resuelto por el ConversationRouter.

    Cada wizard define sus pasos en una lista de dicts {key, question}.
    Las respuestas se acumulan en state.entities hasta completar el flujo.
    """

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

    TAX_REGIME_STEPS = [
        {
            "key": "monthly_sales",
            "question": (
                "Para ayudarte a elegir el régimen correcto, necesito algunos datos.\n\n"
                "¿Cuánto factura o planeas facturar tu negocio al mes?\n\n"
                "- **a)** Menos de S/ 5,000\n"
                "- **b)** Entre S/ 5,000 y S/ 8,000\n"
                "- **c)** Entre S/ 8,000 y S/ 43,750 (hasta S/ 525,000 al año)\n"
                "- **d)** Más de S/ 43,750 al mes\n\n"
                "Responde con la letra o escribe el monto aproximado."
            ),
        },
        {
            "key": "needs_invoices",
            "question": (
                "¿Necesitas emitir facturas a empresas o instituciones?\n\n"
                "*(Por ejemplo: si vendes a otras empresas que necesitan factura para su contabilidad)*\n\n"
                "Responde: **sí** o **no**."
            ),
        },
        {
            "key": "worker_count",
            "question": (
                "¿Cuántos trabajadores tienes o planeas contratar?\n\n"
                "- **a)** Ninguno (trabajo solo)\n"
                "- **b)** Entre 1 y 10 trabajadores\n"
                "- **c)** Más de 10 trabajadores\n\n"
                "Responde con la letra o número."
            ),
        },
    ]

    def __init__(self, rag_service=None, llm_service=None) -> None:
        self.rag_service = rag_service
        self.llm_service = llm_service

    def execute(self, tool_name: str, message: str, state: ConversationState) -> str:
        """Despacha a la tool correspondiente según el nombre recibido del router."""
        if tool_name == "build_formalization_checklist":
            return self._build_formalization_checklist(message, state)

        if tool_name == "compare_tax_regimes":
            return self._compare_tax_regimes(message, state)

        return f"Tool '{tool_name}' no reconocida."

    def _build_formalization_checklist(
        self,
        message: str,
        state: ConversationState,
    ) -> str:
        """
        Flujo de 5 preguntas para formalización. Progreso guardado en
        state.entities["formalization_flow"] con las respuestas y el step actual.
        """
        state.menu_context = "formalizacion_negocio"

        flow_data = state.entities.setdefault("formalization_flow", {})
        current_step = flow_data.get("step", 0)

        if current_step == 0 and "started" not in flow_data:
            flow_data["started"] = True
            flow_data["step"] = 1
            return (
                "Perfecto. Iniciemos el flujo de formalización del negocio.\n\n"
                "Te haré unas preguntas cortas para construir un checklist "
                "personalizado para tu situación.\n\n"
                f"**Pregunta 1 de {len(self.FORMALIZATION_STEPS)}:**\n\n"
                f"{self.FORMALIZATION_STEPS[0]['question']}"
            )

        previous_index = current_step - 1
        if 0 <= previous_index < len(self.FORMALIZATION_STEPS):
            previous_key = self.FORMALIZATION_STEPS[previous_index]["key"]
            flow_data[previous_key] = self._normalize_answer(previous_key, message)

        if current_step < len(self.FORMALIZATION_STEPS):
            next_question = self.FORMALIZATION_STEPS[current_step]["question"]
            flow_data["step"] = current_step + 1
            return (
                f"**Pregunta {current_step + 1} de {len(self.FORMALIZATION_STEPS)}:**\n\n"
                f"{next_question}"
            )

        summary = self._build_formalization_summary(flow_data)

        state.entities["formalization_result"] = {
            "has_ruc": flow_data.get("has_ruc"),
            "person_type": flow_data.get("person_type"),
            "economic_activity": flow_data.get("economic_activity"),
            "voucher_type": flow_data.get("voucher_type"),
            "has_employees": flow_data.get("has_employees"),
        }

        state.entities.pop("formalization_flow", None)
        state.active_tool = None

        return summary

    def _build_formalization_summary(self, flow_data: Dict[str, Any]) -> str:
        """
        Genera el checklist personalizado. Si el LLM está disponible lo usa
        para dar una respuesta más conversacional; si no, usa el template fijo.
        """
        has_ruc = flow_data.get("has_ruc", "no especificado")
        person_type = flow_data.get("person_type", "no especificado")
        economic_activity = flow_data.get("economic_activity", "no especificado")
        voucher_type = flow_data.get("voucher_type", "no especificado")
        has_employees = flow_data.get("has_employees", "no especificado")

        perfil = (
            f"- ¿Tiene RUC?: {has_ruc}\n"
            f"- Tipo de persona: {person_type}\n"
            f"- Actividad económica: {economic_activity}\n"
            f"- Comprobantes a emitir: {voucher_type}\n"
            f"- Tendrá trabajadores: {has_employees}"
        )

        if self.llm_service and self.llm_service.is_available():
            prompt = (
                "Un usuario acaba de completar el flujo de formalización de negocio "
                "en el asistente virtual de SUNAT Perú. Este es su perfil:\n\n"
                f"{perfil}\n\n"
                "Genera un checklist personalizado de pasos para formalizar su negocio "
                "según ese perfil. Usa lenguaje simple y amable. "
                "Si no tiene RUC, pon ese paso como prioritario al inicio. "
                "Si tendrá trabajadores, incluye las obligaciones laborales (ESSALUD, AFP/ONP, planilla). "
                "Al final, ofrece continuar ayudando con otras consultas como regímenes tributarios."
            )
            try:
                generated = self.llm_service.generate(
                    query=prompt,
                    context_chunks=[perfil],
                )
                if generated:
                    return generated
            except Exception:
                pass  # si falla el LLM, usamos el template de abajo

        # Fallback sin LLM
        checklist = [
            "1. Definir claramente el tipo de contribuyente (persona natural o jurídica).",
            "2. Confirmar la actividad económica principal y su código CIIU.",
            "3. Revisar inscripción o actualización en RUC (sunat.gob.pe).",
            "4. Gestionar o validar acceso a Clave SOL.",
            "5. Verificar qué tipo de comprobantes emitirás.",
            "6. Evaluar el régimen tributario que mejor se adapta a tu perfil.",
        ]

        if str(has_ruc).lower() == "no":
            checklist.insert(2, "PRIORITARIO: Inscribirte al RUC en SUNAT.")

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
            "  • Escribe 'regímenes' para comparar los regímenes tributarios.\n"
            "  • Haz cualquier otra consulta sobre SUNAT."
        )

    def _compare_tax_regimes(
        self,
        message: str,
        state: ConversationState,
    ) -> str:
        """
        Flujo de 3 preguntas para recomendar el régimen tributario ideal.
        Progreso en state.entities["tax_regime_flow"].
        """
        state.menu_context = "regimenes_tributarios"

        flow_data = state.entities.setdefault("tax_regime_flow", {})
        current_step = flow_data.get("step", 0)

        if current_step == 0 and "started" not in flow_data:
            flow_data["started"] = True
            flow_data["step"] = 1

            return (
                "Vamos a encontrar el régimen tributario ideal para tu negocio.\n\n"
                "Te haré 3 preguntas cortas. Con esas respuestas puedo darte una "
                "recomendación personalizada.\n\n"
                f"**Pregunta 1 de {len(self.TAX_REGIME_STEPS)}:**\n\n"
                f"{self.TAX_REGIME_STEPS[0]['question']}"
            )

        previous_index = current_step - 1
        if 0 <= previous_index < len(self.TAX_REGIME_STEPS):
            previous_key = self.TAX_REGIME_STEPS[previous_index]["key"]
            normalized_value = self._normalize_answer(previous_key, message)
            flow_data[previous_key] = normalized_value

        if current_step < len(self.TAX_REGIME_STEPS):
            next_question = self.TAX_REGIME_STEPS[current_step]["question"]
            flow_data["step"] = current_step + 1
            return (
                f"**Pregunta {current_step + 1} de {len(self.TAX_REGIME_STEPS)}:**\n\n"
                f"{next_question}"
            )

        recommendation = self._build_regime_recommendation(flow_data, state)

        state.entities["tax_regime_result"] = {
            "monthly_sales": flow_data.get("monthly_sales"),
            "needs_invoices": flow_data.get("needs_invoices"),
            "worker_count": flow_data.get("worker_count"),
        }

        # Limpiar el flujo para que próximas preguntas sobre regímenes
        # vayan al RAG en lugar de reiniciar el wizard accidentalmente.
        state.entities.pop("tax_regime_flow", None)
        state.active_tool = None

        return recommendation

    def _build_regime_recommendation(
        self,
        flow_data: Dict[str, Any],
        state: ConversationState,
    ) -> str:
        """
        Determina el régimen recomendado y enriquece la respuesta con RAG + LLM.

        Lógica:
        - No necesita facturas + ventas ≤ S/8,000/mes → Nuevo RUS
        - Necesita facturas + ventas ≤ S/43,750/mes  → RER
        - Ventas altas o necesita facturas             → RMT
        """
        monthly_sales = str(flow_data.get("monthly_sales", "")).lower()
        needs_invoices = str(flow_data.get("needs_invoices", "")).lower()
        worker_count = str(flow_data.get("worker_count", "")).lower()

        ventas_bajo = any(x in monthly_sales for x in ["a)", "a ", "menos", "5000", "5,000"]) or monthly_sales.strip() == "a"
        ventas_medio_bajo = any(x in monthly_sales for x in ["b)", "b ", "8000", "8,000"]) or monthly_sales.strip() == "b"
        ventas_medio = any(x in monthly_sales for x in ["c)", "c ", "43750", "43,750", "525000"]) or monthly_sales.strip() == "c"
        ventas_alto = any(x in monthly_sales for x in ["d)", "d ", "mayor", "más de"]) or monthly_sales.strip() == "d"

        necesita_facturas = needs_invoices in {"sí", "si", "s", "yes"}

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
            # Caso ambiguo: RMT es la opción más segura y flexible
            regime = "Régimen MYPE Tributario (RMT)"
            reason = (
                "Basándome en tu perfil, el Régimen MYPE Tributario es la opción "
                "más flexible para una MYPE. Permite crecer sin cambiar de régimen "
                "y tiene la tasa de IR más conveniente."
            )
            detail_query = "Régimen MYPE Tributario requisitos beneficios"

        perfil = (
            f"- Ventas mensuales: {monthly_sales}\n"
            f"- Necesita emitir facturas: {needs_invoices}\n"
            f"- Cantidad de trabajadores: {worker_count}"
        )

        # Intentar enriquecer con RAG + LLM
        rag_chunk = ""
        rag_source = ""
        if self.rag_service and self.rag_service.is_indexed():
            rag_results = self.rag_service.search(detail_query, n_results=1)
            if rag_results:
                rag_chunk = rag_results[0]["text"]
                rag_source = rag_results[0]["source"]

        sources_block = self._build_sources_block(rag_source) if rag_source else ""

        if self.llm_service and self.llm_service.is_available():
            prompt = (
                f"Un usuario completó el asistente de regímenes tributarios de SUNAT Perú. "
                f"Su perfil es:\n{perfil}\n\n"
                f"El régimen recomendado es: {regime}\n"
                f"Razón: {reason}\n\n"
                f"Explícale de forma amable y sencilla por qué ese régimen es el mejor para él, "
                f"qué impuestos pagará y cuál es el siguiente paso para inscribirse. "
                f"Ofrece continuar ayudando si tiene más preguntas."
            )
            context_chunks = [perfil]
            if rag_chunk:
                context_chunks.append(rag_chunk)
            try:
                generated = self.llm_service.generate(
                    query=prompt,
                    context_chunks=context_chunks,
                )
                if generated:
                    return f"{generated}\n\n{sources_block}" if sources_block else generated
            except Exception:
                pass  # si falla el LLM, usamos el template

        # Fallback sin LLM
        response_lines = [
            f"Análisis completado. Mi recomendación para tu negocio es:\n",
            f"RÉGIMEN RECOMENDADO: {regime}\n",
            f"¿Por qué? {reason}\n",
        ]

        if rag_chunk:
            response_lines.append("Información adicional de los documentos SUNAT:\n")
            response_lines.append(rag_chunk)
            response_lines.append("")

        response_lines.append(
            "¿Quieres saber más sobre este régimen o comparar con otras opciones? "
            "Puedes preguntarme con más detalle."
        )

        if sources_block:
            response_lines.append(f"\n{sources_block}")

        return "\n".join(response_lines)

    def _build_sources_block(self, source: str) -> str:
        stem = source.rsplit(".", 1)[0]
        name_map = {
            "Régimen MYPE Tributario _ Emprender": "Régimen MYPE Tributario",
            "Regímenes Tributarios _ Emprender": "Regímenes Tributarios",
            "Regímenes Tributarios _ EmprenderCompare": "Comparativa de Regímenes Tributarios",
            "363257-remype-tributario": "Régimen MYPE Tributario (D.L. 1269)",
            "cartilla_formalizacion_2020_PORTAL": "Cartilla de Formalización",
            "Caso practico RMT1": "Caso Práctico RMT",
            "Libro-Cultura_Tributaria_y_Aduanera_final_0": "Cultura Tributaria y Aduanera",
        }
        label = name_map.get(stem, stem.replace("_", " ").title())
        return f"---\n**Fuentes consultadas:**\n- {label}"

    def _normalize_answer(self, key: str, value: str) -> str:
        """Normaliza respuestas comunes para que el wizard las entienda bien."""
        normalized = value.strip().lower()

        if key in {"has_ruc", "has_employees", "needs_invoices"}:
            if normalized in {"si", "sí", "s", "yes", "claro", "correcto", "afirmativo"}:
                return "sí"
            if normalized in {"no", "n", "nope", "negativo"}:
                return "no"

        if key == "person_type":
            if "jurid" in normalized or "empresa" in normalized or "sociedad" in normalized:
                return "jurídica"
            if "natural" in normalized or "persona" in normalized:
                return "natural"

        if key == "voucher_type":
            tiene_factura = "factura" in normalized
            tiene_boleta = "boleta" in normalized
            if "ambos" in normalized or (tiene_factura and tiene_boleta):
                return "ambos"
            if tiene_factura:
                return "facturas"
            if tiene_boleta:
                return "boletas"

        return value.strip()
