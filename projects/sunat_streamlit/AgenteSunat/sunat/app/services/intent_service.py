# app/services/intent_service.py

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.intent_examples import INTENT_EXAMPLES
from app.schemas.nlu import IntentResult, RankedIntentLabel


class IntentService:
    """
    Clasificador de intención por similitud semántica.

    Embebe el mensaje del usuario y lo compara contra ejemplos por intención
    usando similitud coseno. El score final es un híbrido de max y mean
    similarity para mayor robustez que usar solo el promedio.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        intent_examples: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        self.model_name = model_name
        self.intent_examples = intent_examples or INTENT_EXAMPLES
        self._model = SentenceTransformer(self.model_name)
        self._intent_embeddings = self._build_intent_embeddings()

    def classify_topic(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> IntentResult:
        normalized_text = self._normalize_text(text)
        context_used = self._extract_relevant_context(context or {})

        query_embedding = self._model.encode(normalized_text, normalize_embeddings=True)

        ranked = []
        for intent_name, example_embeddings in self._intent_embeddings.items():
            score = self._score_intent(query_embedding, example_embeddings)
            ranked.append(RankedIntentLabel(label=intent_name, score=float(score)))

        ranked.sort(key=lambda item: item.score, reverse=True)
        top_label = ranked[0]

        return IntentResult(
            intent=top_label.label,
            confidence=top_label.score,
            ranked_labels=ranked[:5],
            normalized_text=normalized_text,
            context_used=context_used,
        )

    def _build_intent_embeddings(self) -> Dict[str, np.ndarray]:
        return {
            intent_name: np.array(
                self._model.encode(examples, normalize_embeddings=True)
            )
            for intent_name, examples in self.intent_examples.items()
        }

    def _score_intent(
        self,
        query_embedding: np.ndarray,
        example_embeddings: np.ndarray
    ) -> float:
        """Score híbrido: 70% similitud máxima + 30% promedio."""
        similarities = np.dot(example_embeddings, query_embedding)
        return (0.7 * float(np.max(similarities))) + (0.3 * float(np.mean(similarities)))

    def _normalize_text(self, text: str) -> str:
        return " ".join(text.strip().split())

    def _extract_relevant_context(self, context: Dict[str, Any]) -> Dict[str, str]:
        cleaned: Dict[str, str] = {}
        if current_topic := context.get("current_topic"):
            cleaned["current_topic"] = str(current_topic)
        return cleaned
