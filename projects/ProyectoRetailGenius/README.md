# RetailGenius

Asistente de ventas y soporte al cliente con LLM local.  
Proyecto del curso AI LLM Engineer — BSG Institute.

---

## Requisitos previos

Antes de correr el proyecto necesitas tener instalado:

- **Python 3.11+** — [python.org](https://python.org)
- **Node.js 18+** — [nodejs.org](https://nodejs.org)
- **Ollama** — [ollama.ai](https://ollama.ai)

---

## Setup rapido

### 1. Instalar y correr Ollama

```bash
# Descargar desde https://ollama.ai e instalar
# Luego bajar el modelo:
ollama pull llama3.2:3b
```

Verifica que este corriendo:
```bash
ollama list
# Debe aparecer: llama3.2:3b
```

### 2. Backend (FastAPI)

Abre una terminal en la raiz del proyecto:

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Docs interactivos disponibles en: `http://localhost:8000/docs`

### 3. Frontend (React + Vite)

Abre otra terminal:

```bash
cd frontend
npm install
npm run dev
```

App disponible en: `http://localhost:3000`

---

## Endpoints de la API

| Metodo | Endpoint                | Que hace                                      |
|--------|-------------------------|-----------------------------------------------|
| POST   | `/assistant/query`      | Chat con el asistente. Detecta intencion, busca productos, escala si es necesario |
| POST   | `/products/recommend`   | Recomienda productos segun busqueda y presupuesto |
| GET    | `/products/catalog`     | Devuelve todos los productos del catalogo     |
| POST   | `/support/ticket`       | Crea ticket de soporte con prioridad automatica |
| GET    | `/metrics`              | Dashboard de metricas: consultas, escalaciones, satisfaccion |
| GET    | `/health`               | Estado del sistema y conexion con Ollama      |

---

## Estructura del proyecto

```
ProyectoRetailGenius/
│
├── backend/
│   ├── main.py             # FastAPI app: registra routers, /health, /metrics
│   ├── models.py           # Schemas Pydantic (shapes de requests y responses)
│   ├── assistant.py        # RetailAssistant: logica LLM + busqueda de productos
│   ├── routes/
│   │   ├── assistant.py    # POST /assistant/query
│   │   ├── products.py     # POST /products/recommend  GET /products/catalog
│   │   └── support.py      # POST /support/ticket
│   └── data/
│       └── products.json   # Catalogo de 15 productos
│
├── frontend/
│   └── src/
│       ├── hooks/
│       │   ├── useProducts.js   # Fetch catalogo + filtro/busqueda
│       │   ├── useChat.js       # Estado del chat y envio de mensajes
│       │   ├── useMetrics.js    # Fetch metricas con auto-refresh
│       │   └── useTicket.js     # Formulario de soporte
│       ├── styles/
│       │   ├── _variables.scss  # Colores, fuentes, espaciado
│       │   ├── _mixins.scss     # Helpers reutilizables (card, btn, input...)
│       │   └── main.scss        # Todos los estilos con nesting BEM
│       ├── components/
│       │   ├── ChatWidget.jsx        # Chat flotante
│       │   ├── ProductCard.jsx       # Tarjeta de producto
│       │   └── MetricsDashboard.jsx  # Dashboard de metricas
│       └── App.jsx          # Componente raiz con 3 tabs
│
├── requirements.txt         # Dependencias Python
├── start_backend.bat        # Script para levantar el backend en Windows
├── start_frontend.bat       # Script para levantar el frontend en Windows
└── README.md                # Este archivo
```

---

## Como funciona el asistente

Cada mensaje del usuario activa una cadena de mini-agentes LLM antes de generar la respuesta final:

```
Usuario escribe mensaje
        |
        v
_detect_intent()      -- LLM clasifica la intencion
        |               (consulta_producto, recomendacion, soporte, queja, devolucion, envio, general)
        v
_extract_filters()    -- LLM extrae categoria y presupuesto del lenguaje natural
        |               Ejemplo: "un celular menos de 300" -> category=celulares, budget=300
        |               Si no detecta ninguno, retorna null y no aplica filtros
        v
keyword_search()      -- busca productos en el catalogo si la intencion es producto/recomendacion
        |               Filtra primero por categoria (reduce espacio de busqueda)
        |               El budget actua como bonus de puntaje, no como filtro duro,
        |               para poder sugerir la opcion mas cercana si no hay nada en rango
        v
_should_escalate()    -- LLM decide si el caso requiere atencion urgente de un humano
        |               (fraude, amenazas, emergencias, clientes extremadamente enojados)
        v
_call_llm()           -- genera respuesta en tono de marca con contexto de productos
        |               Si ningun producto entra en el presupuesto del cliente, recibe
        |               un aviso interno para sugerir la opcion mas economica disponible
        v
auto_ticket           -- si la intencion es soporte, queja o devolucion, se crea
        |               un ticket automaticamente sin que el cliente tenga que pedirlo
        v
AssistantQueryResponse
```

### Sistema de puntaje en keyword_search

| Condicion                              | Puntos |
|----------------------------------------|--------|
| Palabra del query en texto del producto | +2 c/u |
| Nombre del producto coincide con query  | +5     |
| Precio dentro del presupuesto del cliente | +2   |
| Producto sin stock                      | -10    |

La categoria no suma puntos porque se filtra antes del loop (todos los productos en el loop ya la cumplen). El budget no es filtro duro para que siempre haya resultados que mostrar, incluso si estan fuera de rango.

---

## Stack tecnico

| Capa      | Tecnologia                     |
|-----------|-------------------------------|
| Backend   | Python, FastAPI, Uvicorn      |
| LLM       | Ollama + llama3.2:3b (local)  |
| Frontend  | React 18, Vite, SASS          |
| Validacion| Pydantic v2                   |
| HTTP      | Axios (frontend)              |
