"""Interfaz LLMClient: aisla el proveedor (Gemini) para poder simularlo en tests.

El flujo de chat con herramientas es de dos pasos porque el proveedor devuelve
o bien texto final, o bien llamados a herramientas pendientes de resolver:
1. generate_reply(): primer turno, puede devolver texto o tool_calls.
2. continue_with_tool_results(): si hubo tool_calls, se ejecutan localmente y
   el resultado se reenvia para obtener el texto final (o mas tool_calls).

`continuation_token` es opaco a proposito: para Gemini es el id de la
interaccion a continuar: no se guarda como estado mutable del cliente para
que una misma instancia de LLMClient sea segura entre requests concurrentes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


class ReviewClassification(BaseModel):
    label: str = Field(description="positivo, neutro o negativo")
    motivo: str
    evidencia: str = Field(description="fragmento citado de la resena")
    confianza: float = Field(ge=0.0, le=1.0)


@dataclass
class ChatTurn:
    role: str  # "user" | "model"
    text: str


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    call_id: str


@dataclass
class ToolResult:
    name: str
    call_id: str
    result: Any


@dataclass
class LLMReply:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    continuation_token: Any = None


class LLMClient(ABC):
    @abstractmethod
    def generate_reply(self, history: list[ChatTurn], tools: list[dict]) -> LLMReply: ...

    @abstractmethod
    def continue_with_tool_results(
        self, continuation_token: Any, results: list[ToolResult], tools: list[dict]
    ) -> LLMReply: ...

    @abstractmethod
    def classify_review(self, content: str) -> ReviewClassification: ...
