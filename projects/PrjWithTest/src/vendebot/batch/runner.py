"""Lote reanudable de clasificacion de resenas.

`load_reviews_from_csv` solo inserta filas que todavia no existen (ON
CONFLICT DO NOTHING): el estado de procesamiento vive unicamente en la tabla
`reviews`, asi que volver a cargar el mismo CSV tras un corte nunca pisa el
progreso ya hecho. `run_batch` procesa por bloques y cada item hace su propio
commit al terminar (mark_done/mark_failed), que es un checkpoint mas fino que
"por bloque": un corte a la mitad de un bloque como maximo repite el ultimo
item en curso, nunca duplica uno ya confirmado.
"""

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

from vendebot.classify.review import classify_review
from vendebot.config import Settings
from vendebot.llm.base import LLMClient
from vendebot.observability.langfuse_client import traced_operation

DEFAULT_REVIEWS_CSV = Path(__file__).resolve().parents[3] / "data" / "fixtures" / "reviews.csv"


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_reviews_from_csv(reviews_repo, csv_path: Path = DEFAULT_REVIEWS_CSV) -> int:
    queued = 0
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            content = row["contenido"]
            reviews_repo.ensure_queued(
                review_id=row["id"],
                customer_id=row["customer_id"],
                product_id=row["product_id"],
                content=content,
                content_hash=_content_hash(content),
            )
            queued += 1
    return queued


@dataclass
class BatchSummary:
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    blocks: int = 0


def run_batch(
    reviews_repo,
    llm_client: LLMClient,
    block_size: int,
    max_attempts: int,
    max_blocks: int | None = None,
    settings: Settings | None = None,
) -> BatchSummary:
    summary = BatchSummary()
    while max_blocks is None or summary.blocks < max_blocks:
        block = reviews_repo.list_to_process(max_attempts, block_size)
        if not block:
            break
        for review in block:
            summary.processed += 1
            try:
                with traced_operation(settings, "batch.review_classification", review_id=review.id):
                    classification = classify_review(llm_client, review.content)
                reviews_repo.mark_done(
                    review.id,
                    classification.label,
                    classification.motivo,
                    classification.evidencia,
                    classification.confianza,
                )
                summary.succeeded += 1
            except Exception:
                reviews_repo.mark_failed(review.id)
                summary.failed += 1
        summary.blocks += 1
    return summary
