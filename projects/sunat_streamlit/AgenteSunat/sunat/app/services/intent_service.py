# app/services/intent_service.py

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.intent_examples import INTENT_EXAMPLES
from app.schemas.nlu import IntentResult, RankedIntentLabel


class IntentService:
    """
    Clasificador de intención por similitud semántica usando ejemplos.

    Estrategia:
    - se embebe el mensaje del usuario
    - se compara contra ejemplos representativos por intención
    - se obtiene un score por intención
    - se selecciona la intención con mayor similitud

    Ventajas:
    - no depende de labels abstractos
    - usa ejemplos reales del dominio
    - reutiliza sentence-transformers, ya coherente con stack RAG
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        intent_examples: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        self.model_name = model_name
        self.intent_examples = intent_examples or INTENT_EXAMPLES
        # El modelo se carga desde caché local.
        # HF_HUB_OFFLINE y TRANSFORMERS_OFFLINE se setean en main.py antes
        # de que este código corra, así evitamos llamadas innecesarias a internet.
        self._model = SentenceTransformer(self.model_name)

        self._intent_embeddings = self._build_intent_embeddings()

    def classify_topic(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> IntentResult:
        normalized_text = self._normalize_text(text)
        context_used = self._extract_relevant_context(context or {})

        query_embedding = self._model.encode(
            normalized_text,
            normalize_embeddings=True
        )

        ranked = []
        for intent_name, example_embeddings in self._intent_embeddings.items():
            score = self._score_intent(query_embedding, example_embeddings)
            ranked.append(
                RankedIntentLabel(label=intent_name, score=float(score))
            )

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
        intent_embeddings: Dict[str, np.ndarray] = {}

        for intent_name, examples in self.intent_examples.items():
            embeddings = self._model.encode(
                examples,
                normalize_embeddings=True
            )
            intent_embeddings[intent_name] = np.array(embeddings)

        return intent_embeddings

    def _score_intent(
        self,
        query_embedding: np.ndarray,
        example_embeddings: np.ndarray
    ) -> float:
        """
        Score híbrido:
        - max similarity: captura el ejemplo más parecido
        - mean similarity: captura consistencia general

        Esto suele ser más robusto que usar solo promedio.
        """
        similarities = np.dot(example_embeddings, query_embedding)
        max_sim = float(np.max(similarities))
        mean_sim = float(np.mean(similarities))

        return (0.7 * max_sim) + (0.3 * mean_sim)

    def _normalize_text(self, text: str) -> str:
        return " ".join(text.strip().split())

    def _extract_relevant_context(self, context: Dict[str, Any]) -> Dict[str, str]:
        cleaned_context: Dict[str, str] = {}

        current_topic = context.get("current_topic")
        if current_topic:
            cleaned_context["current_topic"] = str(current_topic)

        return cleaned_context