"""Prueba con LLM simulado (FakeLLMClient): no llama al proveedor real.
Se distingue de la evaluacion contra Gemini real en tests/eval."""

from vendebot.classify.review import classify_review
from vendebot.llm.base import ReviewClassification
from vendebot.llm.fake_client import FakeLLMClient


def test_classify_review_returns_validated_schema():
    fake = FakeLLMClient(
        scripted_classifications=[
            ReviewClassification(
                label="negativo",
                motivo="el cliente reporta un producto danado",
                evidencia="llego con una tecla danada",
                confianza=0.9,
            )
        ]
    )

    result = classify_review(fake, "El teclado llego con una tecla danada, pesima experiencia")

    assert isinstance(result, ReviewClassification)
    assert result.label == "negativo"
    assert 0.0 <= result.confianza <= 1.0
    assert fake.calls[0] == {
        "kind": "classify",
        "content": "El teclado llego con una tecla danada, pesima experiencia",
    }
