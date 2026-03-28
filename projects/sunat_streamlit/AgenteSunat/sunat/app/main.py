# app/main.py
"""
Punto de entrada de la aplicación FastAPI del chatbot SUNAT.

Responsabilidades de este archivo:
1. Crear la app FastAPI.
2. Instanciar todos los servicios (con sus dependencias).
3. Inicializar el RAG (indexar documentos si no están indexados aún).
4. Exponer los endpoints HTTP.

Patrón de diseño usado: Inyección de Dependencias manual.
Cada servicio recibe sus dependencias por el constructor, no las crea internamente.
Esto hace el código más fácil de testear y mantener.
"""

import os

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Carga variables de entorno desde el archivo .env (si existe).
# Así puedes poner GROQ_API_KEY=gsk_... en sunat/.env sin hardcodear la key.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.services.chat_orchestrator import ChatOrchestrator
from app.services.intent_service import IntentService
from app.services.llm_service import LLMService
from app.services.rag_executor import RagExecutor
from app.services.rag_service import RagService
from app.services.router import ConversationRouter
from app.services.state_store import InMemoryStateStore
from app.services.tool_executor import ToolExecutor

# Configurar logging básico para ver mensajes de info/debug en consola
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Crear la app FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SUNAT Chatbot Backend",
    version="0.2.0",
    description=(
        "Chatbot conversacional para orientación tributaria a MYPES peruanas. "
        "Usa NLU semántico + flujos guiados + RAG sobre documentos SUNAT."
    ),
)

# ---------------------------------------------------------------------------
# CORS — permite que el frontend (React en localhost:5173) hable con este backend
# Sin esto el navegador bloquea las peticiones por política de seguridad
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Modelo de datos para el endpoint /chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """
    Esquema del body que espera el endpoint POST /chat.

    session_id: identificador único de la conversación.
                El frontend debe generar uno (ej. UUID) y mantenerlo durante la sesión.
    message: texto del mensaje del usuario.
    """
    session_id: str
    message: str


# ---------------------------------------------------------------------------
# Inicialización de servicios (al arrancar el servidor)
# ---------------------------------------------------------------------------

logger.info("Inicializando servicios del chatbot SUNAT...")

# 1. Estado conversacional en memoria (simple dict por session_id)
state_store = InMemoryStateStore()

# 2. Clasificador de intenciones (carga el modelo de embeddings al arrancar)
intent_classifier = IntentService()

# 3. Router conversacional (no tiene estado, solo lógica de decisión)
# Se inicializa sin LLM aquí; recibe llm_service después de que este se cree
router = ConversationRouter()

# 4. Servicio RAG — conecta con ChromaDB en disco
#    Si la carpeta chroma_db ya existe con datos, los carga automáticamente.
#    Si no existe o está vacía, la crea.
rag_service = RagService()

# 5. Indexación automática al arrancar
#    Si ya hay documentos indexados, no vuelve a indexar (evita re-procesar).
#    Si la colección está vacía (primera vez o base borrada), indexa los docs de data/docs/.
if not rag_service.is_indexed():
    logger.info("ChromaDB vacío. Iniciando indexación de documentos SUNAT...")
    total = rag_service.index_documents()
    logger.info("Indexación completada: %d fragmentos.", total)
else:
    stats = rag_service.get_stats()
    logger.info(
        "ChromaDB cargado. Colección '%s' tiene %d fragmentos.",
        stats["collection_name"],
        stats["total_chunks"],
    )

# 6. LLM con Groq — lee GROQ_API_KEY del entorno (o de un archivo .env)
#    Si la key no está, el sistema sigue funcionando sin generación LLM.
#    Para activarlo: crea un archivo .env en sunat/ con: GROQ_API_KEY=gsk_...
llm_service = LLMService()

# Ahora que el LLM está listo, lo inyectamos al router para que pueda
# usar clasificación LLM en _is_informational_query en lugar de patrones hardcodeados.
router._llm = llm_service

# 7. Ejecutor RAG — recibe rag_service + llm_service
rag_executor = RagExecutor(rag_service=rag_service, llm_service=llm_service)

# 8. Ejecutor de tools — también recibe el rag_service para enriquecer respuestas finales
tool_executor = ToolExecutor(rag_service=rag_service)

# 9. Orquestador principal — conecta todos los servicios
chat_orchestrator = ChatOrchestrator(
    state_store=state_store,
    intent_classifier=intent_classifier,
    router=router,
    tool_executor=tool_executor,
    rag_executor=rag_executor,
)

logger.info("Todos los servicios inicializados correctamente.")


# ---------------------------------------------------------------------------
# Endpoints HTTP
# ---------------------------------------------------------------------------

@app.get("/")
def health_check():
    """
    Endpoint de health check.
    Útil para verificar que el servidor está corriendo y ver el estado del RAG.
    """
    rag_stats = rag_service.get_stats()
    return {
        "status": "ok",
        "message": "SUNAT Chatbot Backend funcionando correctamente.",
        "rag": {
            "indexed": rag_service.is_indexed(),
            "total_chunks": rag_stats["total_chunks"],
            "collection": rag_stats["collection_name"],
        },
    }


@app.post("/chat")
def chat(request: ChatRequest):
    """
    Endpoint principal de conversación.

    Recibe el mensaje del usuario y devuelve la respuesta del chatbot.

    Response body:
    {
        "response": "texto de respuesta para el usuario",
        "intent_result": { intent, confidence, ranked_labels, ... },
        "route_decision": { action, use_tool, use_rag, tool_name, ... },
        "state": { session_id, current_topic, last_intent, ... }
    }
    """
    return chat_orchestrator.handle_message(
        session_id=request.session_id,
        message=request.message,
    )


@app.post("/rag/reindex")
def reindex_documents():
    """
    Endpoint para re-indexar los documentos manualmente.

    Útil cuando agregas nuevos documentos a data/docs/ y quieres
    actualizarlos en ChromaDB sin reiniciar el servidor.

    Nota: usa upsert, así que no genera duplicados.
    """
    logger.info("Re-indexación manual solicitada via endpoint.")
    total = rag_service.index_documents()
    return {
        "status": "ok",
        "message": f"Re-indexación completada.",
        "total_chunks": total,
    }


@app.get("/rag/stats")
def rag_stats():
    """
    Endpoint para ver estadísticas del RAG.
    Útil para debugging: cuántos chunks hay, en qué directorio, etc.
    """
    return rag_service.get_stats()
