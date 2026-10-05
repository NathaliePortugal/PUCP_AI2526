"""Selecciona el backend de persistencia segun STORAGE_BACKEND, sin que el
resto de la app conozca si hay SQLite o Firestore detras."""

from dataclasses import dataclass
from typing import Any

from vendebot.config import Settings
from vendebot.repo.sqlite import get_connection, init_db
from vendebot.repo.sqlite_repo import (
    SqliteBudgetRepo,
    SqliteCustomersRepo,
    SqliteOrdersRepo,
    SqliteProductsRepo,
    SqliteProposalsRepo,
    SqliteReviewsRepo,
    SqliteSessionsRepo,
)


@dataclass
class Repos:
    products: Any
    customers: Any
    proposals: Any
    orders: Any
    sessions: Any
    budget: Any
    reviews: Any


def build_repos(settings: Settings) -> Repos:
    if settings.storage_backend == "sqlite":
        conn = get_connection(settings.sqlite_path)
        init_db(conn)
        return Repos(
            products=SqliteProductsRepo(conn),
            customers=SqliteCustomersRepo(conn),
            proposals=SqliteProposalsRepo(conn),
            orders=SqliteOrdersRepo(conn),
            sessions=SqliteSessionsRepo(conn),
            budget=SqliteBudgetRepo(conn),
            reviews=SqliteReviewsRepo(conn),
        )
    if settings.storage_backend == "firestore":
        from vendebot.repo.firestore_repo import build_firestore_repos

        return build_firestore_repos(settings)
    raise ValueError(f"STORAGE_BACKEND desconocido: {settings.storage_backend}")
