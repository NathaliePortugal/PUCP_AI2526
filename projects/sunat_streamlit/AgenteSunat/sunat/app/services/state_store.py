from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ConversationState:
    session_id: str
    current_topic: Optional[str] = None
    last_intent: Optional[str] = None
    last_confidence: float = 0.0
    last_action: Optional[str] = None
    menu_context: Optional[str] = None
    awaiting_clarification: bool = False
    active_tool: Optional[str] = None
    entities: Dict[str, Any] = field(default_factory=dict)


class InMemoryStateStore:
    def __init__(self) -> None:
        self._store: dict[str, ConversationState] = {}

    def get(self, session_id: str) -> ConversationState:
        if session_id not in self._store:
            self._store[session_id] = ConversationState(session_id=session_id)
        return self._store[session_id]

    def save(self, state: ConversationState) -> None:
        self._store[state.session_id] = state