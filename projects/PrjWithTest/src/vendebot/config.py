"""Configuracion centralizada desde variables de entorno (.env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Persistencia
    storage_backend: str = "sqlite"
    sqlite_path: str = "./vendebot.db"

    # LLM
    gemini_api_key: str = ""
    llm_model: str = "gemini-flash-latest"
    llm_max_output_tokens: int = 1024
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2

    # Limites de conversacion y consumo
    chat_history_max_turns: int = 10
    daily_token_budget_per_customer: int = 50000
    proposal_expiration_minutes: int = 10

    # Lote reanudable
    batch_block_size: int = 20
    batch_max_attempts: int = 3

    # Observabilidad
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # GCP
    gcp_project_id: str = ""
    gcp_region: str = "us-central1"

    # Servicio
    port: int = 8080


@lru_cache
def get_settings() -> Settings:
    return Settings()
