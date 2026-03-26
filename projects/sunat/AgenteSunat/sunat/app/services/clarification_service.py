from __future__ import annotations

from app.schemas.nlu import IntentResult


def build_clarification_message(intent_result: IntentResult) -> str:
    """
    Genera un mensaje de aclaración cuando la intención detectada
    no tiene suficiente confianza o no puede rutearse con seguridad.
    """
    top_labels = intent_result.ranked_labels[:3]

    if top_labels:
        suggestions = "\n".join(
            f"- {item.label} ({item.score:.2f})"
            for item in top_labels
        )
        return (
            "No estoy completamente seguro de tu intención.\n\n"
            "¿Podrías reformular tu consulta o elegir uno de estos temas?\n"
            f"{suggestions}\n\n"
            "Ejemplos:\n"
            "- Quiero saber cómo sacar mi RUC\n"
            "- Qué pasa si no declaro a tiempo\n"
            "- Ayúdame a elegir un régimen tributario"
        )

    return (
        "No pude identificar con suficiente claridad tu consulta.\n\n"
        "¿Podrías reformularla?\n"
        "Ejemplos:\n"
        "- Cómo sacar mi RUC\n"
        "- Qué multas hay por no declarar\n"
        "- Qué régimen tributario me conviene"
    )
