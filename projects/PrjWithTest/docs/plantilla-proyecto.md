# Plantilla del proyecto - VendeBot

## 1. Caso y recorrido

**Caso elegido:** un asistente de pedidos para una tienda online. El
cliente conversa para preguntar por productos, precios y stock, y armar un
pedido. El LLM nunca crea el pedido directamente, solo lo propone
(`propose_order`); el pedido se crea cuando el cliente lo confirma de forma
explicita. Aparte, hay un lote que clasifica el sentimiento de las resenas
que dejan los clientes despues de comprar, para que una persona sepa a
cuales atender primero.

**Recorrido de principio a fin:**
1. El cliente consulta el catalogo (`GET /products`, o preguntando en el chat).
2. El cliente conversa con el asistente (`POST /chat`) para armar un pedido.
3. El asistente busca productos y consulta stock real (`search_products`,
   `get_stock`) y propone un pedido con el total (`propose_order`).
4. El cliente confirma explicitamente (`POST /orders/confirm`, con un header
   `Idempotency-Key`). Solo ahi se descuenta el stock y se crea el pedido.
5. Mas adelante, el cliente deja una resena. El lote
   (`python -m vendebot.batch` o `POST /batch/reviews/run`) la clasifica por
   sentimiento. Esa clasificacion no autoriza reembolsos, solo ayuda a
   priorizar el seguimiento.

**Lo que el LLM nunca puede hacer:** dar descuentos, cambiar precios o
procesar reembolsos. No hay ninguna herramienta para eso, asi que el modelo
no tiene como hacerlo aunque el cliente lo pida (es el caso 6 de la tabla de
validacion).

## 2. Contratos de API y limites

| Endpoint | Estado |
|---|---|
| `GET /health` | Implementado |
| `GET /products?query=` | Implementado |
| `POST /chat` | Implementado (herramientas, historial acotado, presupuesto diario, traza de Langfuse) |
| `POST /orders/confirm` | Implementado (idempotencia + transaccion atomica) |
| `GET /orders/{order_id}` | Implementado (solo el dueno) |
| `POST /batch/reviews/run` | Implementado |
| CLI `python -m vendebot.batch` | Implementado |

Todos los errores usan el mismo formato:
`{"error": {"code", "message", "trace_id"}}` (en `vendebot/errors.py`).
Ademas de los 8 codigos pedidos, agregue `INTERNAL_ERROR` para los errores
que no entran en ninguno de los otros (en vez de etiquetarlos como
`VALIDATION_ERROR`, que no les queda bien).

## 3. API y uso del LLM

El cliente de Gemini (libreria `google-genai`) esta detras de una interfaz
`LLMClient`, para poder reemplazarlo por un doble de prueba en los tests.
Usa `client.models.generate_content`, con:
- `max_output_tokens` configurable.
- Un timeout propio (con un hilo auxiliar en Python), porque el SDK no
  ofrece un parametro de timeout en el que confiar del todo (ver seccion 7).
- Maximo 2 reintentos con backoff si el error es 429 o 5xx.
- Historial de la conversacion acotado a los ultimos N turnos (`CHAT_HISTORY_MAX_TURNS`).
- Un presupuesto diario de tokens por cliente (`DAILY_TOKEN_BUDGET_PER_CUSTOMER`).
  El conteo es una aproximacion (caracteres / 4) porque el proveedor no da
  todavia un numero exacto de tokens usados en esta API; si se supera el
  presupuesto, se devuelve `BUDGET_EXCEEDED`.

La clasificacion de una resena individual (salida estructurada validada con
Pydantic) esta en `vendebot/classify/review.py`.

## 4. Conversacion, datos y operacion conectada

`POST /chat` tiene 4 herramientas: `search_products`, `get_stock`,
`get_my_orders` y `propose_order`. El cliente se identifica solo por el
header `X-API-Key` (nunca por un id que el mismo escriba en el chat, por
seguridad). El flujo de pedido es: `propose_order` solo crea una propuesta
que expira a los 10 minutos; `POST /orders/confirm` con `Idempotency-Key`
es lo unico que descuenta stock y crea el pedido, dentro de una transaccion
(en SQLite con `BEGIN IMMEDIATE` + una restriccion `UNIQUE`; en Firestore
seria con `@firestore.transactional`).

## 5. Automatizacion y clasificacion justificada

El lote lee `data/fixtures/reviews.csv` y guarda cada resena en la tabla
`reviews` con un estado (`pending`, `done` o `failed`). Si se vuelve a
correr el lote, no reprocesa lo que ya esta `done`, y reintenta lo que esta
`failed` hasta un maximo de intentos. Cada resena hace su propio commit al
terminar, asi que un corte a la mitad del lote como mucho repite el ultimo
item que estaba en curso, nunca duplica uno que ya se guardo.

**Por que elegi sentimiento (positivo/neutro/negativo) como magnitud:** el
lote no tiene que resolver el reclamo del cliente, solo ayudar a decidir a
quien atiende primero una persona. Para eso alcanza con el sentimiento, y
pedirle al modelo que cite un fragmento como evidencia hace mas facil
revisar si la clasificacion tiene sentido. A proposito, esta clasificacion
no autoriza reembolsos ni devoluciones, eso lo decide siempre una persona.

## 6. Validacion y evaluacion

Los 6 casos de la tabla de validacion estan probados de dos formas:
- `tests/unit/test_six_cases.py`: con un LLM simulado (`FakeLLMClient`).
  Corre siempre, rapido y sin costo. Prueba que la app haga lo correcto
  dado lo que el modelo "dijo" (sin depender de si el modelo real responde
  asi siempre).
- `tests/eval/test_real_llm_cases.py`: contra Gemini real, usando DeepEval
  (`ToolCorrectnessMetric` para ver si uso las herramientas esperadas, y
  `GEval` con un juez tambien basado en Gemini para la relevancia de la
  respuesta). Se salta solo si no hay `GEMINI_API_KEY` configurada, o si el
  proveedor no responde (por ejemplo, por cuota agotada). El reporte queda
  en `docs/evidencia/eval/`.

## 7. Observabilidad y GCP

**Langfuse:** integrado en `/chat` y en cada resena del lote; el
`trace_id` se devuelve en la respuesta del chat. Si no hay credenciales de
Langfuse configuradas, la app sigue funcionando igual, solo que sin trazas.
Las credenciales ya estan configuradas.

**Contenedor:** `Dockerfile` multi-stage, con un usuario que no es root, y
escucha en el puerto de la variable `$PORT`. Probe `docker build` y
`docker run` en mi maquina y funcionaron (`/health` respondio bien).

**GCP: no se desplego.** `scripts/deploy.sh` y `scripts/run_batch.sh` estan
escritos y listos (Cloud Run, Artifact Registry, Secret Manager,
Firestore), igual que `repo/firestore_repo.py`, pero no los corri contra un
proyecto real. La razon es simple: para habilitar facturacion en GCP hay
que poner una tarjeta de credito, y no quise usar la mia para esto.

Como alternativa, el servicio (la API, no el lote) lo desplegue en
Render.com (`render.yaml`), que no pide tarjeta para su plan gratis. Esto
no es GCP, lo dejo bien claro en el README para no hacerlo pasar por algo
que no es. Tiene sus limitaciones (sin disco persistente, sin un
equivalente a un Job de Cloud Run, el servicio "duerme" si no se usa) y
estan anotadas en el README.

**Gemini en vivo:** lo probe contra el proveedor real con mi API key.
Terminé usando `client.models.generate_content` en vez de
`client.interactions.create` porque, probandolo de verdad, `generate_content`
falla rapido y de forma clara ante un error del servidor, mientras que
`interactions.create` se quedaba colgado sin responder. La capa gratuita de
la API key tiene un limite de 20 requests por dia por modelo.

## Estado por fase

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Esqueleto, `/health`, fixtures, seed, tests basicos | Completado y probado |
| 2 | Contratos, manejador de errores, cliente Gemini, clasificacion individual | Completado y probado (con LLM simulado) |
| 3 | `/chat`, autenticacion, propuesta -> confirmacion con idempotencia | Completado y probado |
| 4 | Lote reanudable con checkpoint y reintentos | Completado y probado (incluye un test de corte a la mitad) |
| 5 | 6 casos, DeepEval, Dockerfile probado | Completado |
| 6 | Despliegue, Langfuse, README final | Langfuse probado; GCP no desplegado (ver seccion 7); Render.com usado como alternativa |
