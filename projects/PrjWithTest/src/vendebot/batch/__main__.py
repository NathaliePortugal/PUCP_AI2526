"""CLI del lote reanudable: uv run python -m vendebot.batch"""

from vendebot.batch.runner import DEFAULT_REVIEWS_CSV, load_reviews_from_csv, run_batch
from vendebot.config import get_settings
from vendebot.llm.factory import build_llm_client
from vendebot.repo.factory import build_repos


def main() -> None:
    settings = get_settings()
    repos = build_repos(settings)
    llm_client = build_llm_client(settings)

    queued = load_reviews_from_csv(repos.reviews, DEFAULT_REVIEWS_CSV)
    summary = run_batch(
        repos.reviews, llm_client, settings.batch_block_size, settings.batch_max_attempts, settings=settings
    )

    print(f"Resenas en cola (nuevas o existentes): {queued}")
    print(f"Procesadas en esta corrida: {summary.processed}")
    print(f"Clasificadas correctamente: {summary.succeeded}")
    print(f"Fallidas (quedan pending/failed para el proximo intento): {summary.failed}")
    print(f"Bloques ejecutados: {summary.blocks}")


if __name__ == "__main__":
    main()
