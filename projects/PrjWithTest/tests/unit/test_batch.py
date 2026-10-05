"""Lote reanudable: carga desde CSV, corte simulado a la mitad, reintentos
acotados. Usa FakeLLMClient (LLM simulado), no al proveedor real."""

from pathlib import Path

import pytest

from vendebot.batch.runner import load_reviews_from_csv, run_batch
from vendebot.llm.base import ReviewClassification
from vendebot.llm.fake_client import FakeLLMClient
from vendebot.repo.sqlite import get_connection, init_db
from vendebot.repo.sqlite_repo import SqliteReviewsRepo

REVIEWS_CSV = Path("data/fixtures/reviews.csv")


@pytest.fixture
def reviews_repo(tmp_path):
    conn = get_connection(tmp_path / "batch.db")
    init_db(conn)
    return SqliteReviewsRepo(conn)


def _classification(label="positivo") -> ReviewClassification:
    return ReviewClassification(label=label, motivo="motivo", evidencia="fragmento citado", confianza=0.8)


def test_load_reviews_from_csv_queues_all_rows_as_pending(reviews_repo):
    queued = load_reviews_from_csv(reviews_repo, REVIEWS_CSV)

    assert queued == 8
    pending = reviews_repo.list_to_process(max_attempts=3, limit=100)
    assert len(pending) == 8
    assert all(r.status == "pending" for r in pending)


def test_reloading_the_same_csv_does_not_reset_already_done_items(reviews_repo):
    load_reviews_from_csv(reviews_repo, REVIEWS_CSV)
    reviews_repo.mark_done("R001", "positivo", "motivo", "evidencia", 0.9)

    load_reviews_from_csv(reviews_repo, REVIEWS_CSV)  # simula relanzar el lote

    assert reviews_repo.get("R001").status == "done"


def test_interruption_mid_batch_is_resumed_without_duplicating_work(reviews_repo):
    load_reviews_from_csv(reviews_repo, REVIEWS_CSV)
    fake = FakeLLMClient(scripted_classifications=[_classification() for _ in range(8)])

    first_run = run_batch(reviews_repo, fake, block_size=2, max_attempts=3, max_blocks=1)

    assert first_run.processed == 2
    assert reviews_repo.get("R001").status == "done"
    assert reviews_repo.get("R003").status == "pending"  # el "corte" ocurrio aqui

    second_run = run_batch(reviews_repo, fake, block_size=2, max_attempts=3)

    assert second_run.processed == 6  # los 6 restantes, ninguno repetido
    remaining = reviews_repo.list_to_process(max_attempts=3, limit=100)
    assert remaining == []
    classify_calls = [c for c in fake.calls if c["kind"] == "classify"]
    assert len(classify_calls) == 8  # nunca se reprocesa un item ya 'done'


def test_failed_item_is_retried_and_can_succeed_on_a_later_attempt(reviews_repo):
    reviews_repo.ensure_queued("R-A", "C001", "P001", "contenido A", "hash-a")
    reviews_repo.ensure_queued("R-B", "C001", "P002", "contenido B", "hash-b")
    fake = FakeLLMClient(
        scripted_classifications=[RuntimeError("fallo temporal del proveedor"), _classification(), _classification()]
    )

    first_run = run_batch(reviews_repo, fake, block_size=2, max_attempts=3, max_blocks=1)
    assert first_run.succeeded == 1
    assert first_run.failed == 1
    assert reviews_repo.get("R-A").status == "failed"
    assert reviews_repo.get("R-A").attempts == 1
    assert reviews_repo.get("R-B").status == "done"

    second_run = run_batch(reviews_repo, fake, block_size=2, max_attempts=3)
    assert second_run.processed == 1  # solo R-A, R-B ya estaba done
    assert reviews_repo.get("R-A").status == "done"


def test_item_stops_retrying_after_max_attempts(reviews_repo):
    reviews_repo.ensure_queued("R-X", "C001", "P001", "contenido", "hash-x")
    fake = FakeLLMClient(
        scripted_classifications=[RuntimeError("falla 1"), RuntimeError("falla 2")]
    )

    summary = run_batch(reviews_repo, fake, block_size=1, max_attempts=2)

    assert summary.failed == 2
    final = reviews_repo.get("R-X")
    assert final.status == "failed"
    assert final.attempts == 2
    # una tercera vuelta ya no deberia encontrar nada pendiente de reintentar
    assert reviews_repo.list_to_process(max_attempts=2, limit=10) == []
