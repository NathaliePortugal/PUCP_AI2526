"""Juez Gemini para GEval, en vez del juez por omision de DeepEval (GPT-4 de
OpenAI), para no depender de una cuenta de OpenAI que este proyecto no usa
en ningun otro lugar.

Subclase de DeepEvalBaseLLM con load_model/generate/a_generate/get_model_name.
Usa generate_content, igual que vendebot/llm/gemini_client.py.
"""

from deepeval.models.base_model import DeepEvalBaseLLM
from google import genai

from vendebot.config import Settings


class GeminiJudge(DeepEvalBaseLLM):
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = genai.Client(api_key=settings.gemini_api_key)

    def load_model(self):
        return self._client

    def generate(self, prompt: str) -> str:
        response = self._client.models.generate_content(model=self._settings.llm_model, contents=prompt)
        return response.text

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self) -> str:
        return f"gemini:{self._settings.llm_model}"
