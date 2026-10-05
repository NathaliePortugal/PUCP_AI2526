# Etapa de build: instala dependencias con uv (necesita pip/uv, no hace
# falta en la imagen final).
FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

# Etapa final: imagen minima, sin uv ni cache de build, usuario no root.
FROM python:3.12-slim

RUN useradd --create-home --uid 1000 vendebot
WORKDIR /app

COPY --from=builder /app/.venv ./.venv
COPY --from=builder /app/src ./src
COPY data ./data

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER vendebot

EXPOSE 8080

# Cloud Run inyecta $PORT; en local sin definirlo cae a 8080.
CMD ["sh", "-c", "uvicorn vendebot.api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
