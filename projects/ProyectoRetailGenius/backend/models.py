from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TicketPriority(str, Enum):
    """Niveles de prioridad que determinan el tiempo de resolucion de un ticket."""
    LOW    = "baja"
    MEDIUM = "media"
    HIGH   = "alta"
    URGENT = "urgente"


class TicketStatus(str, Enum):
    """Estados del ciclo de vida de un ticket de soporte."""
    OPEN        = "abierto"
    IN_PROGRESS = "en_proceso"
    ESCALATED   = "escalado"
    CLOSED      = "cerrado"


class QueryIntent(str, Enum):
    """
    Categorias de intencion detectadas por el LLM en cada mensaje del cliente.
    El valor determina el flujo: busqueda de productos, ticket automatico, etc.
    """
    PRODUCT_INFO   = "consulta_producto"
    RECOMMENDATION = "recomendacion"
    SUPPORT        = "soporte"
    COMPLAINT      = "queja"
    RETURN         = "devolucion"
    SHIPPING       = "envio"
    GENERAL        = "general"


class AssistantQueryRequest(BaseModel):
    """Cuerpo del request para POST /assistant/query."""
    session_id: str = Field(..., description="ID de sesion del usuario")
    message: str = Field(..., min_length=1, max_length=2000)
    user_name: Optional[str] = Field(default=None)
    context: Optional[str] = Field(default=None, description="Contexto previo de la conversacion")

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "ses-001",
                "message": "Busco un televisor para sala de estar, presupuesto de 800 dolares",
                "user_name": "Maria",
            }
        }
    }


class ProductRecommendRequest(BaseModel):
    """Parametros para POST /products/recommend."""
    query: str = Field(..., description="Que esta buscando el cliente")
    budget_usd: Optional[float] = Field(default=None, gt=0)
    category: Optional[str] = Field(default=None)
    limit: int = Field(default=3, ge=1, le=10)

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "televisor 4K para sala grande",
                "budget_usd": 800.0,
                "category": "electronica",
                "limit": 3
            }
        }
    }


class SupportTicketRequest(BaseModel):
    """Datos del cliente para abrir un ticket en POST /support/ticket."""
    session_id: str
    user_name: str = Field(..., min_length=1)
    user_email: str = Field(..., description="Email del cliente")
    issue_description: str = Field(..., min_length=10, max_length=2000)
    order_id: Optional[str] = Field(default=None)

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "ses-001",
                "user_name": "Nathalie Portugal",
                "user_email": "nathalie@email.com",
                "issue_description": "Mi pedido llego con el empaque dañado y el producto tiene una rayadura.",
                "order_id": "ORD-2024-00847"
            }
        }
    }


class Product(BaseModel):
    """Producto del catalogo cargado desde data/products.json."""
    id: str
    name: str
    category: str
    price_usd: float
    rating: float
    description: str
    brand: str
    in_stock: bool
    image_url: Optional[str] = None


class AssistantQueryResponse(BaseModel):
    """
    Respuesta del asistente al mensaje del cliente.
    Incluye texto de respuesta, intencion detectada, productos sugeridos
    y ticket creado automaticamente si el caso lo requiere.
    """
    session_id: str
    response: str = Field(description="Respuesta del asistente")
    intent: QueryIntent
    escalate_to_human: bool = Field(description="Si debe escalar a agente humano")
    escalation_reason: Optional[str] = None
    suggested_products: list[Product] = Field(default=[])
    auto_ticket: Optional["SupportTicketResponse"] = Field(default=None, description="Ticket creado automaticamente si aplica")
    processing_time_ms: float
    model_used: str


class ProductRecommendResponse(BaseModel):
    """
    Resultado del motor de recomendacion.
    Incluye productos encontrados y un resumen generado por el LLM
    explicando por que son buenas opciones para la consulta del cliente.
    """
    query: str
    products: list[Product]
    ai_summary: str = Field(description="Resumen del asistente sobre las recomendaciones")
    total_found: int
    processing_time_ms: float


class SupportTicketResponse(BaseModel):
    """
    Ticket de soporte creado por el sistema.
    Incluye ID unico, prioridad clasificada automaticamente, respuesta empatica
    y tiempo estimado de resolucion segun la gravedad del caso.
    """
    ticket_id: str
    status: TicketStatus
    priority: TicketPriority
    ai_response: str = Field(description="Respuesta automatica al cliente")
    escalated_to_human: bool
    estimated_resolution: str
    processing_time_ms: float


class MetricsResponse(BaseModel):
    """
    Metricas acumuladas del sistema desde el ultimo reinicio del servidor.
    Expuestas en GET /metrics para el dashboard de monitoreo del frontend.
    """
    total_queries: int
    escalations: int
    tickets_created: int
    out_of_scope: int
    avg_response_time_ms: float
    satisfaction_score: float
    queries_by_intent: dict[str, int]
    total_tokens_in: int
    total_tokens_out: int
    response_times_history: list[float]
    uptime_seconds: float


class HealthResponse(BaseModel):
    """Estado de salud de la API y disponibilidad del modelo Ollama. Expuesto en GET /health."""
    status: str
    ollama_connected: bool
    model_loaded: bool
    available_models: list[str]
    uptime_seconds: float
