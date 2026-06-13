from fastapi import APIRouter, HTTPException, status
from ..models import AssistantQueryRequest, AssistantQueryResponse

router = APIRouter(prefix="/assistant", tags=["Asistente"])


@router.post("/query", response_model=AssistantQueryResponse, summary="Consulta al asistente de ventas")
async def query_assistant(request: AssistantQueryRequest):
    """
    - Detecta la intencion del mensaje (consulta, recomendacion, queja, devolucion, etc.)
    - Extrae categoria y presupuesto del lenguaje natural si los hay
    - Busca productos relevantes en el catalogo
    - Evalua si el caso requiere escalar a un agente humano
    - Genera una respuesta empatica en tono de marca
    - Crea un ticket automatico si la intencion es soporte, queja o devolucion
    """
    from ..main import get_assistant
    assistant = get_assistant()

    if not assistant.is_ollama_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ollama no disponible. Instala desde https://ollama.ai y ejecuta: ollama pull llama3.2:3b"
        )

    try:
        return assistant.query(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
