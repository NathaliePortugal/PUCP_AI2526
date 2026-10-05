from pathlib import Path

import pytest

from vendebot.chat.tools import execute_tool
from vendebot.repo.factory import Repos
from vendebot.repo.models import Customer
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
from scripts.seed import TEST_CUSTOMERS, seed

PRODUCTS_CSV = Path("data/fixtures/products.csv")


@pytest.fixture
def repos(tmp_path) -> Repos:
    db_path = tmp_path / "tools.db"
    seed(db_path, products_csv=PRODUCTS_CSV, customers=TEST_CUSTOMERS)
    conn = get_connection(db_path)
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


@pytest.fixture
def customer() -> Customer:
    return Customer(id="C001", name="Ana Torres", api_key="dev-key-c001")


def test_search_products_matches_by_name(repos, customer):
    result, proposal = execute_tool("search_products", {"query": "Audifonos"}, repos, customer, 10)

    assert proposal is None
    assert {p["id"] for p in result} == {"P001", "P002"}


def test_get_stock_returns_current_stock(repos, customer):
    result, proposal = execute_tool("get_stock", {"product_id": "P001"}, repos, customer, 10)

    assert proposal is None
    assert result == {"product_id": "P001", "stock": 15}


def test_propose_order_creates_pending_proposal_with_correct_total(repos, customer):
    result, proposal = execute_tool(
        "propose_order", {"items": [{"product_id": "P001", "quantity": 2}]}, repos, customer, 10
    )

    assert proposal is not None
    assert proposal.status == "pending"
    assert result["total"] == pytest.approx(259.80)
    assert result["items"][0]["product_id"] == "P001"
    assert result["items"][0]["quantity"] == 2


def test_propose_order_rejects_insufficient_stock(repos, customer):
    result, proposal = execute_tool(
        "propose_order", {"items": [{"product_id": "P005", "quantity": 99}]}, repos, customer, 10
    )

    assert proposal is None
    assert "error" in result


def test_get_my_orders_is_scoped_to_the_given_customer(repos, customer):
    result, _ = execute_tool("get_my_orders", {}, repos, customer, 10)

    assert result == []
