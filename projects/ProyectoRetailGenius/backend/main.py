import time
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .assistant import RetailAssistant
from .models import HealthResponse, MetricsResponse
from .routes import assistant as assistant_router
from .routes import products as products_router
from .routes import support as support_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("retail_genius")

_assistant: RetailAssistant = None
START_TIME = time.time()


def get_assistant() -> RetailAssistant:
    return _assistant


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Ciclo de vida de la aplicacion.
    El bloque antes del yield corre al arrancar el servidor (inicializa el asistente
    y verifica Ollama antes de aceptar el primer request).
    El bloque despues del yield corre al apagar el servidor (Ctrl+C o señal del OS).
    """
    global _assistant
    logger.info("Iniciando RetailGenius API...")
    _assistant = RetailAssistant()
    if not _assistant.is_ollama_available():
        logger.warning("Ollama no disponible — instalar desde https://ollama.ai")
        logger.warning("Luego ejecutar: ollama pull llama3.2:3b")
    else:
        models = _assistant.get_available_models()
        logger.info(f"Ollama conectado | Modelos: {models}")
        logger.info(f"Catalogo cargado: {len(_assistant.products)} productos")
    yield
    logger.info("Cerrando RetailGenius...")


app = FastAPI(
    title="RetailGenius API",
    version="1.0.0",
    description="Asistente de ventas con LLM local (Ollama). Documentacion en /docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.mount("/img", StaticFiles(directory=str(Path(__file__).parent / "data" / "img")), name="images")

app.include_router(assistant_router.router)
app.include_router(products_router.router)
app.include_router(support_router.router)


@app.get("/", tags=["Info"])
async def root():
    """Mapa de endpoints disponibles en la API."""
    return {
        "api": "RetailGenius",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "assistant": "POST /assistant/query",
            "recommend": "POST /products/recommend",
            "catalog":   "GET  /products/catalog",
            "ticket":    "POST /support/ticket",
            "metrics":   "GET  /metrics",
            "health":    "GET  /health",
        },
    }


@app.get("/health", response_model=HealthResponse, tags=["Monitoreo"])
async def health():
    """Estado del sistema: disponibilidad de Ollama y modelo cargado."""
    is_up = _assistant.is_ollama_available()
    models = _assistant.get_available_models()
    return HealthResponse(
        status="healthy" if is_up else "degraded",
        ollama_connected=is_up,
        model_loaded=any("llama" in m for m in models) or len(models) > 0,
        available_models=models,
        uptime_seconds=round(time.time() - START_TIME, 1)
    )


@app.get("/metrics", response_model=MetricsResponse, tags=["Monitoreo"])
async def metrics():
    """Metricas acumuladas: consultas, escalaciones, tokens consumidos y tiempos de respuesta."""
    data = _assistant.get_metrics()
    return MetricsResponse(
        **data,
        uptime_seconds=round(time.time() - START_TIME, 1)
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Error no manejado: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor", "type": type(exc).__name__}
    )
