"""
RetailGenius — Logica del asistente con Ollama
FastAPI -> RetailAssistant -> Ollama (Llama 3.2 local)
"""

import uuid
import time
import json
import logging
from pathlib import Path
from typing import Optional

import ollama
from tenacity import retry, stop_after_attempt, wait_exponential

from .models import (
    AssistantQueryRequest, AssistantQueryResponse,
    ProductRecommendRequest, ProductRecommendResponse,
    SupportTicketRequest, SupportTicketResponse,
    Product, QueryIntent, TicketPriority, TicketStatus
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "llama3.2:3b"
TEMPERATURE   = 0.2

BRAND_SYSTEM_PROMPT = """Eres RetailBotito, asistente virtual de RetailGenius, tienda online de tecnologia y hogar.

ALCANCE - Solo puedes ayudar con temas de la tienda:
- Consultas sobre productos del catalogo (precios, caracteristicas, disponibilidad)
- Recomendaciones de compra segun necesidad y presupuesto
- Estado de pedidos y envios
- Devoluciones y cambios
- Soporte post-venta

Si el cliente pregunta algo fuera de este alcance (politica, recetas, otros temas), dile amablemente que solo puedes ayudar con temas de la tienda y ofrece las opciones anteriores.

REGLAS:
1. Responde siempre en español
2. Inicia siempre saludando y ofreciendo 2-3 opciones concretas de lo que puedes hacer
3. Se conciso (maximo 3 parrafos)
4. Si hay una queja o problema con un pedido, muestra empatia e informa que se creo un ticket de soporte automaticamente
5. Nunca prometas lo que no puedes cumplir

TONO: Amigable, directo y profesional."""

INTENT_PROMPT = """Clasifica la siguiente consulta de un cliente de tienda retail en UNA de estas categorias:
- consulta_producto: Pregunta sobre caracteristicas, precio o disponibilidad de un producto
- recomendacion: El cliente quiere sugerencias de que comprar
- soporte: Problema con un pedido, envio o cuenta
- queja: El cliente esta insatisfecho con algo
- devolucion: Quiere devolver o cambiar un producto
- envio: Pregunta sobre estado de envio o tiempos
- general: Cualquier otra consulta

Responde SOLO con el nombre de la categoria, sin explicacion ni puntuacion."""

ESCALATION_PROMPT = """Eres un clasificador de mensajes de soporte al cliente.
Tu unica tarea: determinar si el siguiente mensaje requiere atencion URGENTE de un agente humano real.

Casos que SI requieren escalar (responde SI):
- Amenazas o lenguaje agresivo
- Acusaciones de fraude, estafa o robo
- Menciones a problemas legales o denuncias
- El cliente indica una emergencia
- Queja muy grave (producto peligroso, perdida significativa de dinero)
- El cliente esta extremadamente enojado y no quiere hablar con un bot

Casos que NO requieren escalar (responde NO):
- Preguntas normales sobre productos
- Consultas de precio o disponibilidad
- Solicitudes de recomendacion
- Problemas menores de soporte o envio

Responde SOLO con: SI o NO"""

EXTRACT_PROMPT = """Eres un extractor de filtros de busqueda para una tienda retail.

De la consulta del cliente extrae dos datos:
- category: la categoria del producto mencionada. Solo puede ser UNA de estas opciones exactas:
    electronica, computadores, celulares, audio, hogar, gaming, mascotas
  Si no hay ninguna categoria clara en el mensaje, usa null.
- budget: el presupuesto maximo del cliente en USD (solo el numero, sin simbolos ni texto).
  Si dice "menos de 500", "hasta 300 dolares", "no mas de 200", pon ese numero.
  Si no menciona precio ni presupuesto, usa null.

Responde SOLO con JSON valido. Sin texto adicional, sin explicacion.

Ejemplos:
  "Busco un celular bueno a menos de 300 dolares"
  {"category": "celulares", "budget": 300}

  "Quiero una laptop para gaming hasta 800 USD"
  {"category": "computadores", "budget": 800}

  "Comedero automatico para mascotas, cuanto cuesta?"
  {"category": "mascotas", "budget": null}

  "Que televisores tienen disponibles?"
  {"category": "electronica", "budget": null}

  "No me llego mi paquete"
  {"category": null, "budget": null}"""


def load_products() -> list[Product]:
    data_path = Path(__file__).parent / "data" / "products.json"
    with open(data_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [Product(**p) for p in raw]


def keyword_search(products: list[Product], query: str, budget: Optional[float] = None,
                   category: Optional[str] = None, limit: int = 3) -> list[Product]:
    """
    Busqueda por palabras clave con puntaje.

    Filtra por categoria primero (reduce el espacio de busqueda antes del loop).
    El budget no es un filtro duro — actua como bonus de puntuacion para priorizar
    productos dentro del presupuesto sin excluir los demas (necesario para poder
    sugerir la opcion mas cercana cuando no hay nada en el rango del cliente).
    """
    if category:
        products = [p for p in products if p.category == category]

    query_lower = query.lower()
    query_words = set(query_lower.split())

    scored = []
    for p in products:
        score = 0
        text = f"{p.name} {p.description} {p.category} {p.brand}".lower()

        for word in query_words:
            if word in text:
                score += 2
        if p.name.lower() in query_lower or query_lower in p.name.lower():
            score += 5
        if budget and p.price_usd <= budget:
            score += 2
        if not p.in_stock:
            score -= 10

        if score > 0:
            scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:limit]]


def classify_priority(description: str, intent: Optional[QueryIntent] = None) -> TicketPriority:
    desc_lower = description.lower()
    if any(w in desc_lower for w in ["urgente", "fraude", "robo", "dinero", "emergencia", "estafa", "denuncia", "legal"]):
        return TicketPriority.URGENT
    if any(w in desc_lower for w in ["dañado", "no funciona", "defecto", "roto", "rayado", "daño", "averiado", "defectuoso", "golpe", "quemado"]):
        return TicketPriority.HIGH
    if any(w in desc_lower for w in ["demora", "retraso", "cambio", "devolver", "devolucion", "no llego", "no me llego", "no ha llegado", "atraso", "tardando"]):
        return TicketPriority.MEDIUM
    if intent == QueryIntent.COMPLAINT:
        return TicketPriority.HIGH
    if intent in (QueryIntent.SUPPORT, QueryIntent.RETURN):
        return TicketPriority.MEDIUM
    return TicketPriority.LOW


class RetailAssistant:
    """
    Nucleo del sistema: orquesta mini-agentes LLM y busqueda de productos.

    Flujo por consulta:
    1. _detect_intent     — clasifica el tipo de mensaje
    2. _extract_filters   — extrae categoria y presupuesto del lenguaje natural
    3. keyword_search     — encuentra productos relevantes
    4. _should_escalate   — decide si derivar a humano
    5. _call_llm          — genera la respuesta final en tono de marca
    """

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self.products = load_products()
        self.metrics = {
            "total_queries": 0,
            "escalations": 0,
            "tickets_created": 0,
            "out_of_scope": 0,
            "total_response_time_ms": 0.0,
            "queries_by_intent": {},
            "satisfaction_scores": [],
            "total_tokens_in": 0,
            "total_tokens_out": 0,
            "response_times_history": [],
        }

    def is_ollama_available(self) -> bool:
        try:
            ollama.list()
            return True
        except Exception:
            return False

    def get_available_models(self) -> list[str]:
        try:
            return [m.model for m in ollama.list().models]
        except Exception:
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
    def _call_llm(self, prompt: str, system: str = BRAND_SYSTEM_PROMPT) -> str:
        response = ollama.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt}
            ],
            options={"temperature": TEMPERATURE, "num_predict": 500, "top_p": 0.9}
        )
        self.metrics["total_tokens_in"]  += getattr(response, "prompt_eval_count", 0) or 0
        self.metrics["total_tokens_out"] += getattr(response, "eval_count", 0) or 0
        return response.message.content

    def _detect_intent(self, message: str) -> QueryIntent:
        try:
            raw = self._call_llm(
                f"Consulta del cliente: {message}",
                system=INTENT_PROMPT
            ).strip().lower()
            intent_map = {e.value: e for e in QueryIntent}
            return intent_map.get(raw, QueryIntent.GENERAL)
        except Exception:
            return QueryIntent.GENERAL

    def _should_escalate(self, message: str) -> tuple[bool, Optional[str]]:
        """Mini agente: decide si el mensaje requiere atencion urgente de un humano."""
        try:
            result = self._call_llm(
                f"Mensaje del cliente: {message}",
                system=ESCALATION_PROMPT
            ).strip().upper()
            if result.startswith("SI"):
                return True, "El asistente detecto que este caso requiere atencion humana"
            return False, None
        except Exception:
            return False, None

    def _extract_filters(self, message: str) -> tuple[Optional[str], Optional[float]]:
        """
        Mini agente: extrae categoria y presupuesto del lenguaje natural.
        Convierte 'busco un celular menos de 300' en category='celulares', budget=300.
        """
        try:
            raw = self._call_llm(
                f"Consulta del cliente: {message}",
                system=EXTRACT_PROMPT
            ).strip()
            if "```" in raw:
                raw = raw.split("```")[1].lstrip("json").strip()
            data = json.loads(raw)
            category = data.get("category") or None
            budget_raw = data.get("budget")
            budget = float(budget_raw) if budget_raw is not None else None
            return category, budget
        except Exception:
            return None, None

    def query(self, req: AssistantQueryRequest) -> AssistantQueryResponse:
        t_start = time.time()
        self.metrics["total_queries"] += 1

        intent = self._detect_intent(req.message)
        self.metrics["queries_by_intent"][intent.value] = \
            self.metrics["queries_by_intent"].get(intent.value, 0) + 1

        should_escalate, escalation_reason = self._should_escalate(req.message)
        if should_escalate:
            self.metrics["escalations"] += 1

        suggested_products = []
        budget_note = ""
        if intent in (QueryIntent.PRODUCT_INFO, QueryIntent.RECOMMENDATION):
            category_filter, budget_filter = self._extract_filters(req.message)

            suggested_products = keyword_search(
                self.products, req.message,
                budget=budget_filter,
                category=category_filter,
                limit=3
            )

            if budget_filter and suggested_products:
                under_budget = [p for p in suggested_products if p.price_usd <= budget_filter]
                if not under_budget:
                    cheapest = min(suggested_products, key=lambda p: p.price_usd)
                    budget_note = (
                        f"\nAVISO PARA EL ASISTENTE: Ninguno de los productos encontrados "
                        f"esta dentro del presupuesto de ${budget_filter:.0f} USD. "
                        f"El mas economico disponible es '{cheapest.name}' a ${cheapest.price_usd:.2f} USD. "
                        f"Informale al cliente y ofrecele esta opcion como la mas cercana a su presupuesto."
                    )

        product_context = ""
        if suggested_products:
            product_context = "\n\nPRODUCTOS DISPONIBLES RELEVANTES:\n"
            for p in suggested_products:
                product_context += f"- {p.name} ({p.brand}) — ${p.price_usd:.2f} USD | {p.description}\n"
            product_context += budget_note

        user_label = f"Cliente {req.user_name}: " if req.user_name else "Cliente: "
        full_prompt = f"{user_label}{req.message}{product_context}"

        try:
            response_text = self._call_llm(full_prompt)
        except Exception as e:
            logger.error(f"Error LLM: {e}")
            response_text = ("Lo siento, estoy teniendo dificultades tecnicas. "
                             "Un agente humano te atendera pronto.")
            should_escalate = True
            escalation_reason = "Error tecnico del asistente"

        elapsed_ms = (time.time() - t_start) * 1000
        self.metrics["total_response_time_ms"] += elapsed_ms
        history = self.metrics["response_times_history"]
        history.append(round(elapsed_ms, 0))
        if len(history) > 20:
            history.pop(0)

        if intent == QueryIntent.GENERAL:
            self.metrics["out_of_scope"] += 1

        auto_ticket = None
        if intent in (QueryIntent.SUPPORT, QueryIntent.COMPLAINT, QueryIntent.RETURN):
            try:
                ticket_req = SupportTicketRequest(
                    session_id=req.session_id,
                    user_name=req.user_name or "Cliente Chat",
                    user_email="chat@retailgenius.com",
                    issue_description=req.message,
                )
                auto_ticket = self.create_ticket(ticket_req, intent=intent)
            except Exception as e:
                logger.error(f"Error creando ticket automatico: {e}")

        return AssistantQueryResponse(
            session_id=req.session_id,
            response=response_text,
            intent=intent,
            escalate_to_human=should_escalate,
            escalation_reason=escalation_reason,
            suggested_products=suggested_products,
            auto_ticket=auto_ticket,
            processing_time_ms=round(elapsed_ms, 2),
            model_used=self.model
        )

    def recommend(self, req: ProductRecommendRequest) -> ProductRecommendResponse:
        t_start = time.time()
        self.metrics["total_queries"] += 1
        self.metrics["queries_by_intent"]["recomendacion"] = \
            self.metrics["queries_by_intent"].get("recomendacion", 0) + 1

        products = keyword_search(
            self.products, req.query,
            budget=req.budget_usd,
            category=req.category,
            limit=req.limit
        )

        if not products:
            summary = "No encontre productos que coincidan con tu busqueda en el catalogo actual."
        else:
            product_list = "\n".join(
                f"- {p.name}: ${p.price_usd:.2f} USD — {p.description}" for p in products
            )
            prompt = (f"Un cliente busca: '{req.query}'"
                      f"{f' con presupuesto de ${req.budget_usd:.0f} USD' if req.budget_usd else ''}.\n"
                      f"Productos disponibles:\n{product_list}\n\n"
                      f"Explica brevemente por que estos productos son buenas opciones.")
            try:
                summary = self._call_llm(prompt)
            except Exception:
                summary = f"Encontre {len(products)} productos que podrian interesarte."

        elapsed_ms = (time.time() - t_start) * 1000
        self.metrics["total_response_time_ms"] += elapsed_ms

        return ProductRecommendResponse(
            query=req.query,
            products=products,
            ai_summary=summary,
            total_found=len(products),
            processing_time_ms=round(elapsed_ms, 2)
        )

    def create_ticket(self, req: SupportTicketRequest, intent: Optional[QueryIntent] = None) -> SupportTicketResponse:
        t_start = time.time()
        self.metrics["tickets_created"] += 1

        ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
        priority = classify_priority(req.issue_description, intent)
        escalated = priority in (TicketPriority.HIGH, TicketPriority.URGENT)

        if escalated:
            self.metrics["escalations"] += 1

        resolution_times = {
            TicketPriority.URGENT: "2-4 horas",
            TicketPriority.HIGH:   "24 horas",
            TicketPriority.MEDIUM: "2-3 dias habiles",
            TicketPriority.LOW:    "5-7 dias habiles",
        }

        prompt = (f"Un cliente llamado {req.user_name} reporta este problema:\n"
                  f"'{req.issue_description}'\n"
                  f"{'Numero de orden: ' + req.order_id if req.order_id else ''}\n\n"
                  f"Genera una respuesta empatica confirmando que recibimos su caso "
                  f"(ticket {ticket_id}), que lo resolveremos en {resolution_times[priority]} "
                  f"y cuales son los pasos siguientes.")
        try:
            ai_response = self._call_llm(prompt)
        except Exception:
            ai_response = (f"Hola {req.user_name}, recibimos tu reporte (Ticket: {ticket_id}). "
                           f"Nuestro equipo te contactara en {resolution_times[priority]}.")

        elapsed_ms = (time.time() - t_start) * 1000
        self.metrics["total_response_time_ms"] += elapsed_ms
        self.metrics["queries_by_intent"]["soporte"] = \
            self.metrics["queries_by_intent"].get("soporte", 0) + 1

        status = TicketStatus.ESCALATED if escalated else TicketStatus.OPEN

        return SupportTicketResponse(
            ticket_id=ticket_id,
            status=status,
            priority=priority,
            ai_response=ai_response,
            escalated_to_human=escalated,
            estimated_resolution=resolution_times[priority],
            processing_time_ms=round(elapsed_ms, 2)
        )

    def get_metrics(self) -> dict:
        total = self.metrics["total_queries"]
        avg_time = (self.metrics["total_response_time_ms"] / total) if total > 0 else 0
        scores = self.metrics["satisfaction_scores"]
        avg_satisfaction = sum(scores) / len(scores) if scores else 4.2

        return {
            "total_queries": total,
            "escalations": self.metrics["escalations"],
            "tickets_created": self.metrics["tickets_created"],
            "out_of_scope": self.metrics["out_of_scope"],
            "avg_response_time_ms": round(avg_time, 2),
            "satisfaction_score": round(avg_satisfaction, 2),
            "queries_by_intent": self.metrics["queries_by_intent"],
            "total_tokens_in": self.metrics["total_tokens_in"],
            "total_tokens_out": self.metrics["total_tokens_out"],
            "response_times_history": self.metrics["response_times_history"],
        }
