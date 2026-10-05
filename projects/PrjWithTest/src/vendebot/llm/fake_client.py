"""Doble de prueba de LLMClient. Los tests que lo usan se marcan como simulados
y se separan de la evaluacion contra el proveedor real (ver tests/eval)."""

from dataclasses import dataclass, field
from typing import Any

from vendebot.llm.base import ChatTurn, LLMClient, LLMReply, ReviewClassification, ToolResult


@dataclass
class FakeLLMClient(LLMClient):
    """Reproduce listas de respuestas predefinidas, en el orden en que se piden."""

    scripted_replies: list[LLMReply] = field(default_factory=list)
    scripted_classifications: list[ReviewClassification] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def generate_reply(self, history: list[ChatTurn], tools: list[dict]) -> LLMReply:
        self.calls.append({"kind": "generate_reply", "history": history, "tools": tools})
        return self.scripted_replies.pop(0)

    def continue_with_tool_results(
        self, continuation_token: Any, results: list[ToolResult], tools: list[dict]
    ) -> LLMReply:
        self.calls.append({"kind": "continue", "token": continuation_token, "results": results})
        return self.scripted_replies.pop(0)

    def classify_review(self, content: str) -> ReviewClassification:
        """Si el siguiente item guionado es una excepcion, se lanza en vez de
        devolverse: asi se simulan fallos del proveedor para probar reintentos."""
        self.calls.append({"kind": "classify", "content": content})
        item = self.scripted_classifications.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
