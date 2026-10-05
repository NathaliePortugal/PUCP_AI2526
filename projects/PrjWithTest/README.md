# VendeBot

Asistente de pedidos para una tienda online. Un cliente conversa para
consultar productos, precios y stock, y arma un pedido; el LLM solo propone
pedidos (`propose_order`) y el pedido se crea cuando el cliente confirma
explicitamente (`POST /orders/confirm`, con idempotencia). Un lote reanudable
clasifica el sentimiento de las resenas post-venta para priorizar el
seguimiento humano.

## Requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) para dependencias y entorno virtual
- Docker (solo para construir/correr el contenedor)
- Una API key de Gemini para usar el chat real y el lote real (ver
  "Configuracion" abajo). Sin ella, la API y los tests corren igual, pero
  `/chat` y el lote fallan con `LLM_UNAVAILABLE` al intentar llamar al
  proveedor.

## Instalacion

```bash
uv sync
cp .env.example .env
```

## Configuracion


| Variable | Para que sirve |
|---|---|
| `GEMINI_API_KEY` | Habilita `/chat` real y el lote real. Sin ella, ambos devuelven `LLM_UNAVAILABLE`. |
| `STORAGE_BACKEND` | `sqlite` (default, local) o `firestore` (GCP). |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | Si estan vacias, la app funciona igual pero sin trazas (modo sin operacion). |
| `GCP_PROJECT_ID` / `GCP_REGION` | Solo se usan si `STORAGE_BACKEND=firestore` o al desplegar. |

## Ejecutar la API

```bash
uv run uvicorn vendebot.api.main:app --reload
curl http://127.0.0.1:8000/health
```

## Cargar datos de prueba (seed)

```bash
uv run python scripts/seed.py
```

Carga `data/fixtures/products.csv` y dos clientes de prueba
(`C001`/`dev-key-c001`, `C002`/`dev-key-c002`) en SQLite (`SQLITE_PATH`).

## Probar el recorrido completo (con `GEMINI_API_KEY` configurada)

```bash
# 1. buscar productos
curl "http://127.0.0.1:8000/products?query=audifonos"

# 2. conversar y obtener una propuesta
curl -X POST http://127.0.0.1:8000/chat \
  -H "X-API-Key: dev-key-c001" -H "Content-Type: application/json" \
  -d '{"session_id": "s1", "message": "Quiero 2 audifonos X"}'

# 3. confirmar (usar el proposal_id de la respuesta anterior)
curl -X POST http://127.0.0.1:8000/orders/confirm \
  -H "X-API-Key: dev-key-c001" -H "Content-Type: application/json" \
  -H "Idempotency-Key: idem-demo-1" \
  -d '{"proposal_id": "PR-xxxx", "confirm": true}'

# 4. ver el pedido (solo el dueno puede verlo)
curl http://127.0.0.1:8000/orders/O-xxxx -H "X-API-Key: dev-key-c001"
```

## Lote reanudable (resenas)

```bash
uv run python -m vendebot.batch        # CLI
curl -X POST http://127.0.0.1:8000/batch/reviews/run   # o via la API
```

Relanzarlo no duplica trabajo: los items `done` se saltan y los `failed` se
reintentan hasta `BATCH_MAX_ATTEMPTS`.

## Tests

```bash
uv run pytest                 # unitarios + los 6 casos, todos con LLM simulado
uv run pytest tests/eval -v   # evaluacion con DeepEval contra Gemini real
                               # (se salta sola si no hay GEMINI_API_KEY)
```

Los tests en `tests/unit/` usan `FakeLLMClient` (simulado) y no llaman a
ningun proveedor real: corren siempre, sin costo ni llaves. Los de
`tests/eval/` llaman a Gemini de verdad y escriben un reporte en
`docs/evidencia/eval/`.

## Contenedor

```bash
docker build -t vendebot:local .
docker run -p 8080:8080 \
  -e GEMINI_API_KEY=tu_api_key \
  -e SQLITE_PATH=/tmp/vendebot.db \
  vendebot:local
curl http://127.0.0.1:8080/health
```

Build y run verificados con Docker Desktop. Nota para Git Bash/MSYS en
Windows: si una ruta como `/tmp/...` en un
`-e` se reescribe sola a una ruta de Windows, usar `MSYS_NO_PATHCONV=1`
antes del comando `docker run` (no es un problema del Dockerfile, es un
comportamiento de Git Bash).

## Despliegue en GCP (script listo, no ejecutado)

```bash
export PROJECT_ID=tu-proyecto
export GEMINI_API_KEY=tu_api_key
export LANGFUSE_PUBLIC_KEY=...   # opcional
export LANGFUSE_SECRET_KEY=...   # opcional
./scripts/deploy.sh
./scripts/run_batch.sh
```

`deploy.sh` habilita las APIs necesarias, crea el repositorio en Artifact
Registry, la base Firestore, los secretos en Secret Manager, y publica el
servicio (`min-instances=0`) y el Job de Cloud Run para el lote. Esta
escrito contra la documentacion oficial, **pero no se ejecuto contra un
proyecto real**: GCP pide una tarjeta de credito para habilitar la
facturacion (necesaria para Cloud Run/Firestore/Artifact Registry, incluso
dentro de la capa gratuita), y no se quiso usar una tarjeta para esto. Si en
algun momento se consigue un proyecto GCP con facturacion, `deploy.sh` queda
listo para correr tal cual.

## Despliegue real usado en esta entrega: Render.com

Como alternativa sin tarjeta de credito, el servicio (no el lote, ver
abajo) se desplego en [Render.com](https://render.com), que para su plan
free de "Web Service" con Dockerfile no pide tarjeta. Esto **no es GCP**:
se documenta como una sustitucion explicita, no como si fuera la pieza de
GCP de la rubrica.

```bash
git push                      # a un repo de GitHub/GitLab
# en Render: New + -> Blueprint -> conectar el repo (usa render.yaml)
# completar como secretos: GEMINI_API_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
curl https://<tu-servicio>.onrender.com/health
curl -X POST https://<tu-servicio>.onrender.com/batch/reviews/run   # el lote, a mano (no hay Cloud Run Job aqui)
```

Limitaciones de esta alternativa (para la seccion de limites y costos):
- **Sin persistencia real entre despliegues**: el plan free no da disco
  persistente, así que `SQLITE_PATH=/tmp/vendebot.db` se reinicia vacio en
  cada redeploy o reinicio del contenedor. Sirve para demostrar el
  recorrido completo en una sesion en vivo, no para datos que deban
  sobrevivir semanas. Correr `scripts/seed.py` (o `POST /batch/reviews/run`)
  despues de cada arranque.
- **El plan free "duerme" el servicio tras inactividad**: el primer
  request despues de dormir tarda mas (cold start).
- **No hay un Cloud Run Job equivalente**: el lote se dispara a mano via
  `POST /batch/reviews/run` o `python -m vendebot.batch` desde una
  maquina con acceso a la misma base; sigue siendo reanudable (ver Fase 4),
  solo que no automatizado por un scheduler.
- **Gemini y Langfuse no dependen de GCP**: la API key de IA Studio y las
  credenciales de Langfuse funcionan igual sin importar donde corra el
  contenedor, asi que `/chat` real y las trazas si quedan verificables en
  esta alternativa.

## Cuentas y llaves

| Que | Donde se obtiene | Estado |
|---|---|---|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/) -> "Get API key" | Configurada. **Capa gratuita: 20 requests/dia por modelo** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`), resetea cada 24h. Para una demo en vivo sin sustos, habilitar facturacion en AI Studio sube ese limite. |
| Langfuse | [cloud.langfuse.com](https://cloud.langfuse.com) | Configurada (`LANGFUSE_PUBLIC_KEY`/`SECRET_KEY` en `.env`). |
| GCP con facturacion | [console.cloud.google.com](https://console.cloud.google.com) | No disponible (requiere tarjeta de credito). Alternativa: Render.com (ver arriba) o un proyecto guiado por el docente. |
| `gcloud` CLI | https://cloud.google.com/sdk/docs/install | No instalado. |
| Docker Desktop | -- | Build y run verificados: `docker build` + `docker run` + `/health` respondiendo. |

Nada de esto bloquea la logica del proyecto: toda la app esta probada con
`FakeLLMClient` sin depender de ninguna cuenta externa. Lo que depende de
estas cuentas es exclusivamente la evidencia "en vivo" (chat real,
`tests/eval`, trazas, servicio desplegado).

## Estructura del proyecto

```
vendebot/
├── src/vendebot/
│   ├── api/            # FastAPI: rutas, esquemas, lifespan
│   ├── llm/             # interfaz LLMClient + Gemini real + doble de prueba
│   ├── chat/             # herramientas y el bucle de conversacion
│   ├── orders/           # confirmacion de pedido (accion sensible)
│   ├── batch/            # lote reanudable (CLI y logica)
│   ├── classify/         # clasificacion de una resena
│   ├── repo/             # patron repositorio: SQLite y Firestore
│   └── observability/    # trazas de Langfuse
├── tests/unit/            # LLM simulado, incluye los 6 casos de validacion
├── tests/eval/            # DeepEval contra Gemini real
├── data/fixtures/         # catalogo y resenas de prueba
├── docs/                  # arquitectura, plantilla del curso, evidencia
└── scripts/               # seed, deploy, run_batch
```

## Limites conocidos

- La estimacion de tokens para el presupuesto diario es aproximada
  (caracteres / 4), no el conteo exacto del proveedor.
- El timeout del LLM se implementa con un hilo auxiliar (no cancela la
  llamada en curso si se agota el tiempo, solo deja de esperarla).
- La capa gratuita de `GEMINI_API_KEY` tiene un limite de 20 requests/dia
  por modelo.
- `FirestoreRepo` esta escrito contra la documentacion oficial de Firestore
  pero no se probo contra un proyecto real ni contra el emulador.
- El endpoint `POST /batch/reviews/run` no tiene autenticacion propia: se
  asume un uso interno/de demostracion, no expuesto al cliente final.
