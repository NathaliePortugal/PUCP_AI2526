"""Clasificacion de sentimiento de una resena individual.

Separado en su propio modulo porque lo usan dos llamadores distintos: el
lote reanudable (Fase 4) y los tests unitarios con LLM simulado.
"""

from vendebot.llm.base import LLMClient, ReviewClassification


def classify_review(llm_client: LLMClient, content: str) -> ReviewClassification:
    return llm_client.classify_review(content)
