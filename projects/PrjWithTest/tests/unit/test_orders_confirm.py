"""Flujo propuesta -> confirmacion: casos de error e idempotencia de la tabla
de validacion (propuesta expirada, sin stock, misma Idempotency-Key dos veces)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from vendebot.errors import NotFoundError, OutOfStockError, ProposalExpiredError, ValidationError
from vendebot.orders.service import confirm_order, get_order_for_customer
from vendebot.repo.factory import Repos
from vendebot.repo.models import Customer, OrderItem
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
    db_path = tmp_path / "orders.db"
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


@pytest.fixture
def other_customer() -> Customer:
    return Customer(id="C002", name="Luis Paredes", api_key="dev-key-c002")


def test_confirm_requires_explicit_confirm_true(repos, customer):
    proposal = repos.proposals.create(customer.id, [OrderItem(product_id="P001", name="Audifonos X", quantity=1, unit_price=129.90)], 129.90, 10)

    with pytest.raises(ValidationError):
        confirm_order(repos, customer, proposal.id, confirm=False, idempotency_key="idem-1")


def test_confirm_requires_idempotency_key(repos, customer):
    proposal = repos.proposals.create(customer.id, [OrderItem(product_id="P001", name="Audifonos X", quantity=1, unit_price=129.90)], 129.90, 10)

    with pytest.raises(ValidationError):
        confirm_order(repos, customer, proposal.id, confirm=True, idempotency_key=None)


def test_confirm_success_discounts_stock_exactly_once(repos, customer):
    proposal = repos.proposals.create(
        customer.id, [OrderItem(product_id="P001", name="Audifonos X", quantity=2, unit_price=129.90)], 259.80, 10
    )

    order = confirm_order(repos, customer, proposal.id, confirm=True, idempotency_key="idem-ok")

    assert order.status == "confirmed"
    assert order.total == pytest.approx(259.80)
    product = repos.products.get("P001")
    assert product.stock == 13  # 15 - 2


def test_confirm_twice_with_same_idempotency_key_returns_single_order(repos, customer):
    proposal = repos.proposals.create(
        customer.id, [OrderItem(product_id="P001", name="Audifonos X", quantity=1, unit_price=129.90)], 129.90, 10
    )

    first = confirm_order(repos, customer, proposal.id, confirm=True, idempotency_key="idem-repeat")
    second = confirm_order(repos, customer, proposal.id, confirm=True, idempotency_key="idem-repeat")

    assert first.id == second.id
    product = repos.products.get("P001")
    assert product.stock == 14  # el descuento solo ocurrio una vez


def test_confirm_expired_proposal_raises_proposal_expired(repos, customer):
    proposal = repos.proposals.create(
        customer.id, [OrderItem(product_id="P001", name="Audifonos X", quantity=1, unit_price=129.90)], 129.90, 10
    )
    expired_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    repos.proposals._conn.execute(
        "UPDATE proposals SET expires_at = ? WHERE id = ?", (expired_at, proposal.id)
    )
    repos.proposals._conn.commit()

    with pytest.raises(ProposalExpiredError):
        confirm_order(repos, customer, proposal.id, confirm=True, idempotency_key="idem-expired")


def test_confirm_without_enough_stock_raises_out_of_stock(repos, customer):
    proposal = repos.proposals.create(
        customer.id, [OrderItem(product_id="P005", name="Monitor 24 pulgadas", quantity=3, unit_price=699.00)], 2097.00, 10
    )
    # alguien mas se adelanta y agota el stock despues de que se creo la propuesta
    repos.products._conn.execute("UPDATE products SET stock = 0 WHERE id = 'P005'")
    repos.products._conn.commit()

    with pytest.raises(OutOfStockError):
        confirm_order(repos, customer, proposal.id, confirm=True, idempotency_key="idem-nostock")


def test_customer_cannot_confirm_another_customers_proposal(repos, customer, other_customer):
    proposal = repos.proposals.create(
        customer.id, [OrderItem(product_id="P001", name="Audifonos X", quantity=1, unit_price=129.90)], 129.90, 10
    )

    with pytest.raises(NotFoundError):
        confirm_order(repos, other_customer, proposal.id, confirm=True, idempotency_key="idem-other")


def test_get_order_only_returns_it_to_its_owner(repos, customer, other_customer):
    proposal = repos.proposals.create(
        customer.id, [OrderItem(product_id="P001", name="Audifonos X", quantity=1, unit_price=129.90)], 129.90, 10
    )
    order = confirm_order(repos, customer, proposal.id, confirm=True, idempotency_key="idem-owner")

    assert get_order_for_customer(repos, customer, order.id).id == order.id
    with pytest.raises(NotFoundError):
        get_order_for_customer(repos, other_customer, order.id)
