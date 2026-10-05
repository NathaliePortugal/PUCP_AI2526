"""Cliente real de Gemini via el SDK oficial google-genai, detras de LLMClient.

Usa `generate_content`, no `interactions.create`: ante un error del
servidor, `interactions.create` puede quedarse colgado sin responder ni
lanzar excepcion, mientras que `generate_content` falla rapido con
`google.genai.errors.APIError`/`ServerError` (atributo `.code`), que es lo
que permite aplicar reintentos y timeout de forma confiable.

Limites no negociables del proyecto, todos aplicados aqui:
- max_output_tokens configurable (GenerateContentConfig.max_output_tokens).
- timeout propio con un hilo auxiliar, no un parametro del SDK.
- maximo N reintentos con backoff ante codigos 429/5xx.
"""

import concurrent.futures
import time
from typing import Any

from google import genai
from google.genai import types

from vendebot.errors import LLMInvalidOutputError, LLMUnavailableError
from vendebot.llm.base import ChatTurn, LLMClient, LLMReply, ReviewClassification, ToolCall, ToolResult

RETRIABLE_CODES = {429, 500, 502, 503, 504}


def _status_code_of(exc: Exception) -> int | None:
    return getattr(exc, "code", None) or getattr(exc, "status_code", None)


CLASSIFY_PROMPT = (
    "Clasifica el sentimiento de esta resena de un producto de una tienda "
    "online. Responde solo con el JSON pedido. Cita textualmente un "
    "fragmento de la resena como evidencia.\n\nResena: {content}"
)


class GeminiClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        model: str,
        max_output_tokens: int,
        timeout_seconds: int,
        max_retries: int,
    ):
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    @staticmethod
    def _turns_to_contents(history: list[ChatTurn]) -> list[types.Content]:
        return [
            types.Content(role="user" if turn.role == "user" else "model", parts=[types.Part(text=turn.text)])
            for turn in history
        ]

    @staticmethod
    def _tools_to_genai(tools: list[dict]) -> list[types.Tool] | None:
        if not tools:
            return None
        declarations = [
            types.FunctionDeclaration(
                name=t["name"], description=t.get("description", ""), parameters=t.get("parameters")
            )
            for t in tools
        ]
        return [types.Tool(function_declarations=declarations)]

    def _call_with_retries(self, **kwargs: Any) -> Any:
        attempt = 0
        while True:
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(self._client.models.generate_content, **kwargs)
                    return future.result(timeout=self._timeout_seconds)
            except concurrent.futures.TimeoutError as exc:
                attempt += 1
                if attempt > self._max_retries:
                    raise LLMUnavailableError(
                        f"Gemini no respondio en {self._timeout_seconds}s"
                    ) from exc
            except Exception as exc:
                status_code = _status_code_of(exc)
                attempt += 1
                if status_code not in RETRIABLE_CODES or attempt > self._max_retries:
                    raise LLMUnavailableError(f"Gemini no disponible (codigo {status_code})") from exc
                time.sleep((2**attempt) * 0.5)

    def _step(self, contents: list[types.Content], tools: list[dict]) -> LLMReply:
        response = self._call_with_retries(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                tools=self._tools_to_genai(tools),
                max_output_tokens=self._max_output_tokens,
            ),
        )
        candidate_content = response.candidates[0].content
        function_call_parts = [p for p in candidate_content.parts if p.function_call]

        if function_call_parts:
            contents.append(candidate_content)
            tool_calls = [
                ToolCall(name=p.function_call.name, arguments=dict(p.function_call.args), call_id=p.function_call.name)
                for p in function_call_parts
            ]
            return LLMReply(text=None, tool_calls=tool_calls, continuation_token=contents)

        return LLMReply(text=response.text, tool_calls=[], continuation_token=contents)

    def generate_reply(self, history: list[ChatTurn], tools: list[dict]) -> LLMReply:
        return self._step(self._turns_to_contents(history), tools)

    def continue_with_tool_results(
        self, continuation_token: Any, results: list[ToolResult], tools: list[dict]
    ) -> LLMReply:
        contents: list[types.Content] = continuation_token
        response_parts = [types.Part.from_function_response(name=r.name, response={"result": r.result}) for r in results]
        contents.append(types.Content(role="user", parts=response_parts))
        return self._step(contents, tools)

    def classify_review(self, content: str) -> ReviewClassification:
        response = self._call_with_retries(
            model=self._model,
            contents=CLASSIFY_PROMPT.format(content=content),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ReviewClassification,
                max_output_tokens=self._max_output_tokens,
            ),
        )
        if response.parsed is None:
            raise LLMInvalidOutputError("Gemini devolvio una clasificacion invalida")
        return response.parsed
