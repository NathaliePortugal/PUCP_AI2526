# app/services/intent_serviceZeroShot.py

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from transformers import pipeline

from app.core.constants import (
    TOPIC_LABELS,
    TOPIC_LABEL_TO_INTENT,
    TOP_LABELS_TO_KEEP,
)
from app.schemas.nlu import IntentResult, RankedIntentLabel


class IntentService:
    def __init__(
        self,
        model_name: str = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
        candidate_labels: Optional[List[str]] = None,
        multi_label: bool = False,
        local_files_only: bool = True,
    ) -> None:
        self.model_name = model_name
        self.candidate_labels = candidate_labels or TOPIC_LABELS
        self.multi_label = multi_label
        self.local_files_only = local_files_only

        os.environ["HF_HUB_OFFLINE"] = "1"

        self._classifier = pipeline(
            task="zero-shot-classification",
            model=self.model_name,
            tokenizer=self.model_name,
            local_files_only=self.local_files_only,
        )

    def classify_topic(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> IntentResult:
        normalized_text = self._normalize_text(text)
        context_used = self._extract_relevant_context(context or {})
        classifier_input = self._build_classifier_input(
            normalized_text=normalized_text,
            context_used=context_used,
        )

        result = self._classifier(
            sequences=classifier_input,
            candidate_labels=self.candidate_labels,
            multi_label=self.multi_label,
            hypothesis_template="Esta consulta trata sobre {}."
        )

        ranked_labels = self._build_ranked_labels(
            labels=result["labels"],
            scores=result["scores"]
        )

        top_label = ranked_labels[0]
        internal_intent = TOPIC_LABEL_TO_INTENT.get(
            top_label.label,
            "consulta_documental_general"
        )

        return IntentResult(
            intent=internal_intent,
            confidence=top_label.score,
            ranked_labels=ranked_labels,
            normalized_text=normalized_text,
            context_used=context_used,
        )

    def _normalize_text(self, text: str) -> str:
        return " ".join(text.strip().split())

    def _extract_relevant_context(self, context: Dict[str, Any]) -> Dict[str, str]:
        cleaned_context: Dict[str, str] = {}

        current_topic = context.get("current_topic")
        if current_topic:
            cleaned_context["current_topic"] = str(current_topic)

        return cleaned_context

    def _build_classifier_input(
        self,
        normalized_text: str,
        context_used: Dict[str, str]
    ) -> str:
        if not context_used:
            return normalized_text

        context_parts = [f"{key}: {value}" for key, value in context_used.items()]
        context_block = " | ".join(context_parts)

        return (
            f"mensaje_usuario: {normalized_text}\n"
            f"contexto_conversacional: {context_block}"
        )

    def _build_ranked_labels(
        self,
        labels: List[str],
        scores: List[float]
    ) -> List[RankedIntentLabel]:
        return [
            RankedIntentLabel(label=label, score=float(score))
            for label, score in zip(labels[:TOP_LABELS_TO_KEEP], scores[:TOP_LABELS_TO_KEEP])
        ]
