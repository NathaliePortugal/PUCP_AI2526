"""Punto de entrada de la API FastAPI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from vendebot.api.routes import router
from vendebot.config import get_settings
from vendebot.errors import register_error_handlers
from vendebot.llm.factory import build_llm_client
from vendebot.repo.factory import build_repos


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.repos = build_repos(settings)
    app.state.llm_client = build_llm_client(settings)
    yield


app = FastAPI(title="VendeBot", version="0.1.0", lifespan=lifespan)
register_error_handlers(app)
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
