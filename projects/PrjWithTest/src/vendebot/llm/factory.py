"""Construye el LLMClient real a partir de la configuracion."""

from vendebot.config import Settings
from vendebot.llm.base import LLMClient
from vendebot.llm.gemini_client import GeminiClient


def build_llm_client(settings: Settings) -> LLMClient:
    return GeminiClient(
        api_key=settings.gemini_api_key,
        model=settings.llm_model,
        max_output_tokens=settings.llm_max_output_tokens,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
