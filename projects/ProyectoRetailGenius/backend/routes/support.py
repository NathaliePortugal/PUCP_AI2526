from fastapi import APIRouter, HTTPException
from ..models import SupportTicketRequest, SupportTicketResponse

router = APIRouter(prefix="/support", tags=["Soporte"])


@router.post("/ticket", response_model=SupportTicketResponse, summary="Crear ticket de soporte post-venta")
async def create_ticket(request: SupportTicketRequest):
    """
    Crea un ticket de soporte con clasificacion automatica por el LLM.

    - Clasifica la prioridad segun palabras clave en la descripcion del problema
    - Genera una respuesta empatica con tiempo estimado de resolucion
    - Escala automaticamente a agente humano si la prioridad es ALTA o URGENTE

    Tiempos de resolucion por prioridad:
    - urgente: 2-4 horas
    - alta: 24 horas
    - media: 2-3 dias habiles
    - baja: 5-7 dias habiles
    """
    from ..main import get_assistant
    assistant = get_assistant()

    try:
        return assistant.create_ticket(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
