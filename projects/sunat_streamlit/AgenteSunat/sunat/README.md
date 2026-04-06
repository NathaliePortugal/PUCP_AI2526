# Sunatito — Chatbot SUNAT para MYPEs

Chatbot para orientación tributaria de MYPEs peruanas. Responde consultas sobre regímenes, declaraciones, multas y comprobantes usando documentos oficiales de SUNAT + un LLM.

---

## Cómo ejecutarlo en local

### 1. Requisitos

- Python 3.10 o superior
- Una API key de [Groq](https://console.groq.com/) (tiene plan gratuito)

### 2. Instalar dependencias

```bash
cd AgenteSunat/sunat

python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configurar la API key

Crear un archivo `.env` en la carpeta `AgenteSunat/sunat/` con:

```
GROQ_API_KEY=gsk_tu_clave_aqui
```

Sin esta clave el sistema igual funciona, pero responde con los chunks del RAG directamente en lugar de generar texto con el LLM.

### 4. Indexar los documentos (solo la primera vez)

```bash
python scripts/ingest_documents.py
```

Esto lee los PDFs de `app/data/docs/` y los guarda en ChromaDB. Tarda 1-2 minutos. Las siguientes ejecuciones reutilizan el índice ya creado.

Si quieres re-indexar desde cero:

```bash
python scripts/ingest_documents.py --force
```

### 5. Iniciar la app

```bash
streamlit run streamlit_app.py
```

Se abre automáticamente en `http://localhost:8501`.

---

## Scripts útiles

```bash
# Ver qué hay en ChromaDB
python scripts/inspect_chroma.py

# Evaluar el clasificador de intenciones
python scripts/evaluate_intent.py

# Evaluar el pipeline RAG
python scripts/evaluate_rag.py

# Evaluar el sistema de routing completo
python scripts/evaluate_routing.py
```

---

## Estructura rápida

```
sunat/
├── streamlit_app.py        # Punto de entrada
├── app/
│   ├── core/               # Config y constantes
│   ├── services/           # Lógica del chatbot (RAG, LLM, router, wizards)
│   ├── schemas/            # Modelos de datos (Pydantic)
│   └── data/
│       ├── docs/           # PDFs de SUNAT que se indexan
│       └── test_cases/     # Casos de prueba para evaluación
├── chroma_db/              # Base de datos vectorial (se genera al indexar)
└── scripts/                # Indexación y evaluación
```
