"""Trazas de Langfuse: cada request de /chat y cada item del lote generan
una traza, y el trace_id se devuelve en la respuesta (chat) o se guarda en
el reporte del lote.

Si no hay credenciales de Langfuse configuradas, se usa un modo sin
operacion: la observabilidad es una capa adicional, no un requisito para que
VendeBot corra localmente sin cuenta de Langfuse.

Se llama a `flush()` al cerrar cada operacion porque Cloud Run puede
suspender el contenedor entre requests.
"""

from contextlib import contextmanager

from vendebot.config import Settings


def is_langfuse_enabled(settings: Settings | None) -> bool:
    return bool(settings and settings.langfuse_public_key and settings.langfuse_secret_key)


@contextmanager
def traced_operation(settings: Settings | None, name: str, **metadata):
    if not is_langfuse_enabled(settings):
        yield None
        return

    from langfuse import get_client

    langfuse = get_client()
    with langfuse.start_as_current_observation(as_type="span", name=name) as span:
        if metadata:
            span.update(metadata=metadata)
        trace_id = langfuse.get_current_trace_id()
        try:
            yield trace_id
        finally:
            langfuse.flush()
