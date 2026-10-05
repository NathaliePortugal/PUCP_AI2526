# Arquitectura de VendeBot

## Vision general (objetivo final)

```mermaid
flowchart LR
    U[Cliente] -->|X-API-Key, mensaje| API[API FastAPI]
    API -->|historial acotado| LLM[Gemini - google-genai]
    LLM -->|function calling| T1[search_products]
    LLM -->|function calling| T2[get_stock]
    LLM -->|function calling| T3[get_my_orders]
    LLM -->|function calling| T4[propose_order]
    T1 --> DB[(Repositorio\nSQLite / Firestore)]
    T2 --> DB
    T3 --> DB
    T4 -->|crea propuesta,\nno escribe pedido| DB
    API -->|reply, proposal, tools_used, trace_id| U

    U -->|"POST /orders/confirm\n{proposal_id, confirm}\nIdempotency-Key"| CONFIRM[Confirmacion]
    CONFIRM -->|"transaccion: valida stock\ny descuenta"| DB
    CONFIRM -->|order_id, status, total| U

    API -.->|traza por request| LANGFUSE[Langfuse]
    BATCH[Lote reanudable\nreviews] -->|clasifica sentimiento| LLM
    BATCH -.->|traza por item| LANGFUSE
    BATCH --> DB

    classDef confirm fill:#f9f3d0,stroke:#9a8a3f;
    class CONFIRM confirm;
```

El punto marcado en amarillo (`CONFIRM`) es el control explicito antes de la
accion sensible: el LLM solo propone (`propose_order`), nunca escribe un
pedido ni descuenta stock. Eso ocurre unicamente cuando el cliente confirma
de forma explicita en `POST /orders/confirm`, con `Idempotency-Key` para que
una confirmacion repetida no duplique el pedido.

## Estado implementado

Todo el diagrama de arriba esta implementado: `/chat` con las 4
herramientas, el flujo propuesta -> confirmacion con idempotencia, el lote
reanudable, y las trazas de Langfuse en cada request de chat y cada item del
lote. El repositorio soporta SQLite (local/tests, usado en toda la
verificacion) y Firestore (para GCP, implementado contra la documentacion
oficial pero sin probar contra un proyecto real -- ver README, seccion
"Cuentas y llaves").

## Decisiones de arquitectura

- **Patron repositorio para la persistencia**: la logica de negocio no debe
  saber si los datos viven en SQLite o Firestore. `STORAGE_BACKEND` selecciona
  la implementacion sin tocar el resto del codigo.
- **Interfaz `LLMClient`**: aisla el SDK de Gemini para poder sustituirlo por
  un doble de prueba en los tests unitarios, sin llamar al proveedor real.
- **Propuesta como paso intermedio**: separar "proponer" de "confirmar" es lo
  que permite declarar una accion sensible (descontar stock) bajo control
  explicito del cliente, en vez de dejar que el LLM decida cuando escribir.
