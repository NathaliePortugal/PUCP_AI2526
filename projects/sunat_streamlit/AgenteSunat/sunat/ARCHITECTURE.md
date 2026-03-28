# Sunatito — Arquitectura del sistema

Chatbot tributario para MYPES peruanas. Combina clasificación semántica de
intenciones, flujos guiados multi-turno y RAG sobre documentos SUNAT.

---

## Flujo de un mensaje

```
Usuario escribe un mensaje
         │
         ▼
┌─────────────────────┐
│    IntentService    │  Embeddings (sentence-transformers)
│                     │  Compara el mensaje contra INTENT_EXAMPLES
│  → intent           │  Score híbrido: 0.7·max + 0.3·mean
│  → confidence       │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  ConversationRouter │  Decide la acción según este orden:
│                     │
│  1. ¿Flujo activo?  │──► ToolExecutor  (continuar wizard)
│  2. Confianza baja? │──► Clarificación
│  3. Intent + tool   │
│     + es PROCESO?   │──► ToolExecutor  (iniciar wizard)
│  4. Intent documental──► RagExecutor
│  5. Fallback        │──► Clarificación
└────────┬────────────┘
         │
    ┌────┴─────┐
    ▼          ▼
┌────────┐  ┌──────────────────────────────────────────┐
│  Tool  │  │               RagExecutor                │
│Executor│  │                                          │
│        │  │  ChromaDB (búsqueda vectorial)           │
│ Wizard │  │      ↓                                   │
│ multi- │  │  Filtro por intención (INTENT_TO_SOURCES)│
│ turno  │  │      ↓                                   │
│        │  │  Top-K chunks más relevantes             │
│ Guarda │  │      ↓                                   │
│ resp.  │  │  LLMService (Groq) genera respuesta      │
│ en     │  │  usando los chunks como contexto         │
│ state. │  │      ↓  (fallback: chunks directo)       │
│entities│  │  Respuesta con fuentes al pie            │
└───┬────┘  └──────────────┬───────────────────────────┘
    │                      │
    │   Al completarse      │
    │   el wizard:          │
    │   LLMService genera   │
    │   resumen enriquecido │
    └──────────┬────────────┘
               ▼
        Respuesta al usuario
```

---

## Componentes

| Archivo | Responsabilidad |
|---|---|
| `streamlit_app.py` | UI, inicialización de servicios (`@st.cache_resource`), sesión |
| `chat_orchestrator.py` | Coordina el flujo completo por cada mensaje |
| `intent_service.py` | Clasifica la intención del mensaje con embeddings |
| `router.py` | Decide si ir a tool, RAG o pedir aclaración |
| `tool_executor.py` | Flujos guiados multi-turno (formalización, regímenes, multas) |
| `rag_executor.py` | Orquesta búsqueda en ChromaDB + generación con LLM |
| `rag_service.py` | Pipeline RAG: carga PDFs → chunks → embeddings → ChromaDB |
| `llm_service.py` | Llama a la API de Groq (llama-3.3-70b) |
| `state_store.py` | Estado conversacional en memoria por session_id |
| `clarification_service.py` | Genera mensajes de aclaración cuando la confianza es baja |

---

## Intenciones disponibles

Definidas en `core/intent_examples.py`. Cada intención tiene ejemplos de frases
reales que el clasificador usa como referencia.

| Intent | Tool asignada | Ruta por defecto |
|---|---|---|
| `formalizacion_negocio` | `build_formalization_checklist` | Tool → RAG si es consulta informacional |
| `regimenes_tributarios` | `compare_tax_regimes` | Tool → RAG si es consulta informacional |
| `multas_y_sanciones` | `handle_fines_guidance` | Tool (menú orientativo) → RAG |
| `comprobantes_pago` | — | RAG directo |
| `declaraciones_impuestos` | — | RAG directo |
| `cronograma_obligaciones` | — | RAG directo |
| `consulta_documental_general` | — | RAG directo |

---

## RAG — Documentos indexados

Los PDFs viven en `app/data/docs/` organizados por carpeta temática.
ChromaDB persiste los embeddings en `chroma_db/` (no se sube al repo).

**Primera vez o al agregar documentos nuevos:**
```bash
# Re-indexar desde cero
python scripts/ingest_documents.py --force

# Verificar qué quedó indexado
python scripts/inspect_chroma.py --samples
```

El sistema **no detecta documentos nuevos automáticamente** en el arranque.
Si `chroma_db/` ya tiene datos, los usa sin re-indexar.

---

## Estado conversacional

Cada sesión tiene un `ConversationState` con:
- `active_tool` — si hay un wizard en curso, el router lo continúa automáticamente
- `entities` — respuestas acumuladas del wizard (`formalization_flow`, `tax_regime_flow`)
- `current_topic` — última intención detectada (usada por RagExecutor para filtrar fuentes)
- `awaiting_clarification` — si el turno anterior pidió aclaración

---

## Cómo agregar una nueva tool (wizard)

1. Definir los pasos en `tool_executor.py` como lista `[{key, question}]`
2. Implementar `_mi_nueva_tool(message, state)` con la lógica de flujo
3. Agregar el dispatch en `execute()`
4. Registrar en `core/constants.py`: `TOOL_INTENT_TO_NAME["mi_intent"] = "mi_nueva_tool"`
5. Agregar ejemplos en `core/intent_examples.py` para que el clasificador la reconozca

## Cómo agregar una nueva intención sin tool (solo RAG)

1. Agregar ejemplos en `core/intent_examples.py`
2. Agregar el intent a `DOCUMENTAL_INTENTS` en `core/constants.py`
3. Opcionalmente mapear fuentes en `rag_executor.py` → `INTENT_TO_SOURCES`

---

## Stack

- **UI**: Streamlit
- **Clasificación de intenciones**: sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2)
- **Base vectorial**: ChromaDB (persistente en disco)
- **Extracción de PDFs**: pymupdf4llm → fitz (fallback)
- **LLM**: Groq API — llama-3.3-70b-versatile
- **Python**: 3.10+
