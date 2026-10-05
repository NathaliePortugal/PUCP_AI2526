"""Pruebas del bucle de chat con LLM simulado (FakeLLMClient).
Se distinguen de la evaluacion contra Gemini real en tests/eval."""

from pathlib import Path

import pytest

from vendebot.chat.service import run_chat_turn
from vendebot.config import Settings
from vendebot.errors import BudgetExceededError
from vendebot.llm.base import LLMReply, ToolCall
from vendebot.llm.fake_client import FakeLLMClient
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
    db_path = tmp_path / "chat.db"
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
def settings() -> Settings:
    return Settings(daily_token_budget_per_customer=50000, chat_history_max_turns=10, proposal_expiration_minutes=10)


def test_chat_turn_with_tool_call_attaches_the_resulting_proposal(repos, customer, settings):
    fake = FakeLLMClient(
        scripted_replies=[
            LLMReply(
                text=None,
                tool_calls=[
                    ToolCall(name="propose_order", arguments={"items": [{"product_id": "P001", "quantity": 2}]}, call_id="call-1")
                ],
                continuation_token="interaction-1",
            ),
            LLMReply(text="Te propongo 2 audifonos X por 259.80.", tool_calls=[]),
        ]
    )

    result = run_chat_turn(
        llm_client=fake, repos=repos, settings=settings, customer=customer,
        session_id="s1", message="Quiero 2 audifonos X",
    )

    assert result.proposal is not None
    assert result.proposal.total == pytest.approx(259.80)
    assert result.tools_used == ["propose_order"]
    assert "259.80" in result.reply


def test_chat_turn_without_enough_data_does_not_propose(repos, customer, settings):
    fake = FakeLLMClient(
        scripted_replies=[LLMReply(text="¿Cual producto te interesa? Tenemos varios.", tool_calls=[])]
    )

    result = run_chat_turn(
        llm_client=fake, repos=repos, settings=settings, customer=customer,
        session_id="s2", message="Quiero el producto",
    )

    assert result.proposal is None
    assert result.tools_used == []


def test_chat_turn_persists_bounded_history(repos, customer, settings):
    fake = FakeLLMClient(scripted_replies=[LLMReply(text="Hola, ¿en que te ayudo?", tool_calls=[])])

    run_chat_turn(
        llm_client=fake, repos=repos, settings=settings, customer=customer, session_id="s3", message="hola"
    )

    history = repos.sessions.get_history("s3", customer.id)
    assert [h["role"] for h in history] == ["user", "model"]


def test_chat_turn_raises_budget_exceeded_without_calling_llm(repos, customer, settings):
    repos.budget.add_usage(customer.id, settings.daily_token_budget_per_customer)
    fake = FakeLLMClient(scripted_replies=[])  # si se llamara, pop() fallaria

    with pytest.raises(BudgetExceededError):
        run_chat_turn(
            llm_client=fake, repos=repos, settings=settings, customer=customer,
            session_id="s4", message="hola otra vez",
        )
