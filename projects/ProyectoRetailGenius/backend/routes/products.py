from fastapi import APIRouter, HTTPException
from ..models import ProductRecommendRequest, ProductRecommendResponse

router = APIRouter(prefix="/products", tags=["Productos"])


@router.post("/recommend", response_model=ProductRecommendResponse, summary="Recomendaciones personalizadas de productos")
async def recommend_products(request: ProductRecommendRequest):
    """
    Motor de recomendacion con busqueda por palabras clave y LLM.
    - Filtra el catalogo por categoria si se especifica
    - Prioriza productos dentro del presupuesto indicado
    - El LLM genera un resumen explicando por que recomienda cada producto

    Diferencia con /assistant/query: este endpoint recibe parametros estructurados
    (category, budget_usd) en vez de lenguaje natural. Util para integraciones directas.
    """
    from ..main import get_assistant
    assistant = get_assistant()

    try:
        return assistant.recommend(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog", summary="Catalogo completo de productos")
async def get_catalog():
    """Devuelve todos los productos del catalogo cargado en memoria."""
    from ..main import get_assistant
    assistant = get_assistant()
    return {"products": [p.model_dump() for p in assistant.products], "total": len(assistant.products)}
