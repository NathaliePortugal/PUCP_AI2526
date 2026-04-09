# app/schemas/nlu.py

from typing import List, Optional
from pydantic import BaseModel, Field


class RankedIntentLabel(BaseModel):
    label: str = Field(..., min_length=1)
    score: float = Field(..., ge=0.0, le=1.0)


class IntentResult(BaseModel):
    intent: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    ranked_labels: List[RankedIntentLabel] = Field(default_factory=list)
    normalized_text: str = Field(..., min_length=1)


class RouteDecision(BaseModel):
    action: str = Field(..., min_length=1)
    use_rag: bool = False
    use_tool: bool = False
    tool_name: Optional[str] = None
    needs_clarification: bool = False
    reason: str = Field(..., min_length=1)