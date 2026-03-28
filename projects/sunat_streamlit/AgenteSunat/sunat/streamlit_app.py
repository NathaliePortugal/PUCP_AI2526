"""
Interfaz Streamlit para el chatbot SUNAT.

Ejecutar desde la carpeta sunat/:
    streamlit run streamlit_app.py
"""

import os
import sys
import uuid

# Asegura que 'app' sea importable desde este archivo
sys.path.insert(0, os.path.dirname(__file__))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import logging
import streamlit as st

from app.services.chat_orchestrator import ChatOrchestrator
from app.services.intent_service import IntentService
from app.services.llm_service import LLMService
from app.services.rag_executor import RagExecutor
from app.services.rag_service import RagService
from app.services.router import ConversationRouter
from app.services.state_store import InMemoryStateStore
from app.services.tool_executor import ToolExecutor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Acciones rápidas (equivalente a los botones del React)
# ---------------------------------------------------------------------------

QUICK_ACTIONS = [
    {
        "label": "🏢 Formalizar mi negocio",
        "message": "Quiero iniciar la guía para formalizar mi negocio",
    },
    {
        "label": "📊 Comparar regímenes tributarios",
        "message": "Ayúdame a elegir el régimen tributario ideal para mi negocio",
    },
    {
        "label": "📄 Comprobantes electrónicos",
        "message": "Qué son los comprobantes de pago electrónicos y cómo funcionan",
    },
    {
        "label": "📅 Declaración mensual IGV/Renta",
        "message": "Qué es la declaración mensual de IGV y Renta y cómo se hace",
    },
    {
        "label": "⚠️ Multas y sanciones",
        "message": "Qué multas y sanciones existen y cómo puedo reducirlas",
    },
    {
        "label": "📆 Cronograma de obligaciones",
        "message": "Cuál es el cronograma de vencimientos de obligaciones tributarias",
    },
]


@st.cache_resource(show_spinner="Inicializando servicios del chatbot...")
def init_services() -> ChatOrchestrator:
    """
    Inicializa todos los servicios una sola vez.
    Streamlit reutiliza el resultado en cada rerun gracias a cache_resource.
    """
    logger.info("Inicializando servicios del chatbot SUNAT...")

    state_store = InMemoryStateStore()
    intent_classifier = IntentService()
    router = ConversationRouter()
    rag_service = RagService()

    if not rag_service.is_indexed():
        logger.info("ChromaDB vacío. Indexando documentos SUNAT...")
        total = rag_service.index_documents()
        logger.info("Indexación completada: %d fragmentos.", total)
    else:
        stats = rag_service.get_stats()
        logger.info(
            "ChromaDB cargado. Colección '%s' tiene %d fragmentos.",
            stats["collection_name"],
            stats["total_chunks"],
        )

    llm_service = LLMService()
    router._llm = llm_service

    rag_executor = RagExecutor(rag_service=rag_service, llm_service=llm_service)
    tool_executor = ToolExecutor(rag_service=rag_service, llm_service=llm_service)

    orchestrator = ChatOrchestrator(
        state_store=state_store,
        intent_classifier=intent_classifier,
        router=router,
        tool_executor=tool_executor,
        rag_executor=rag_executor,
    )

    logger.info("Servicios inicializados correctamente.")
    return orchestrator


def send_message(orchestrator: ChatOrchestrator, prompt: str) -> None:
    """Procesa un mensaje, actualiza el historial y muestra la respuesta."""
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Procesando..."):
            result = orchestrator.handle_message(
                session_id=st.session_state.session_id,
                message=prompt,
            )
        response = result["response"]
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})


# ---------------------------------------------------------------------------
# Configuración de página
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Sunatito",
    page_icon="🤖",
    layout="centered",
)

# Header con colores institucionales SUNAT
st.markdown(
    """
    <style>
        .sunat-header {
            background-color: #003876;
            padding: 1.2rem 1.5rem;
            border-radius: 8px;
            margin-bottom: 0.5rem;
            display: flex;
            align-items: center;
            gap: 0.8rem;
        }
        .sunat-header h1 {
            color: #FFFFFF;
            font-size: 1.6rem;
            margin: 0;
            padding: 0;
        }
        .sunat-header span.badge {
            background-color: #E8192C;
            color: white;
            font-size: 0.75rem;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 4px;
        }
        .sunat-caption {
            color: #4A5568;
            font-size: 0.9rem;
            margin-bottom: 1rem;
        }
        .quick-actions-title {
            color: #003876;
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }
    </style>
    <div class="sunat-header">
        <h1>🤖 Sunatito</h1>
        <span class="badge">Tu agente amigable</span>
    </div>
    <p class="sunat-caption">Tu asistente virtual de SUNAT para orientación tributaria de MYPES peruanas</p>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Estado de sesión
# ---------------------------------------------------------------------------

WELCOME_MESSAGE = (
    "¡Hola! Soy **Sunatito**, tu agente amigable de SUNAT 🤖\n\n"
    "Estoy aquí para ayudarte con orientación tributaria: regímenes, "
    "comprobantes electrónicos, declaraciones mensuales, multas y más. "
    "¿En qué puedo ayudarte hoy?"
)

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": WELCOME_MESSAGE}]

if "pending_message" not in st.session_state:
    st.session_state.pending_message = None

# ---------------------------------------------------------------------------
# Inicializar servicios (cached)
# ---------------------------------------------------------------------------

orchestrator = init_services()

# ---------------------------------------------------------------------------
# Mostrar historial de mensajes
# ---------------------------------------------------------------------------

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---------------------------------------------------------------------------
# Botones de acceso rápido (solo se muestran al inicio de la conversación)
# ---------------------------------------------------------------------------

is_fresh_conversation = len(st.session_state.messages) == 1

if is_fresh_conversation:
    st.markdown(
        '<p class="quick-actions-title">Selecciona un tema o escribe tu consulta:</p>',
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns(2)
    for i, action in enumerate(QUICK_ACTIONS):
        col = col1 if i % 2 == 0 else col2
        if col.button(action["label"], key=f"quick_{i}", use_container_width=True):
            st.session_state.pending_message = action["message"]
            st.rerun()

# ---------------------------------------------------------------------------
# Procesar mensaje pendiente (viene de un botón de acceso rápido)
# ---------------------------------------------------------------------------

if st.session_state.pending_message:
    prompt = st.session_state.pending_message
    st.session_state.pending_message = None
    send_message(orchestrator, prompt)

# ---------------------------------------------------------------------------
# Input de texto del usuario
# ---------------------------------------------------------------------------

if prompt := st.chat_input("Escribe tu consulta tributaria..."):
    send_message(orchestrator, prompt)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        """
        <div style="background-color:#003876;padding:0.8rem 1rem;border-radius:6px;margin-bottom:1rem;">
            <span style="color:white;font-weight:700;font-size:1rem;">🤖 Sunatito</span>
            <span style="color:#E8192C;font-weight:700;font-size:0.85rem;display:block;margin-top:2px;">Tu agente amigable de SUNAT</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("**Temas disponibles:**")
    st.markdown(
        "- 🏢 Formalización de empresas\n"
        "- 📊 Regímenes tributarios\n"
        "- 📄 Comprobantes electrónicos\n"
        "- 📅 Declaraciones mensuales\n"
        "- ⚠️ Multas y sanciones\n"
        "- 📆 Cronograma de obligaciones"
    )

    st.divider()

    st.caption(f"Sesión: `{st.session_state.session_id[:8]}...`")

    if st.button("🔄 Nueva conversación", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = [{"role": "assistant", "content": WELCOME_MESSAGE}]
        st.session_state.pending_message = None
        st.rerun()
