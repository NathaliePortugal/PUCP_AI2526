"""Rutas HTTP de VendeBot."""

from fastapi import APIRouter, Depends, Header

from vendebot.api.schemas import (
    BatchRunResponse,
    ChatRequest,
    ChatResponse,
    OrderConfirmRequest,
    OrderConfirmResponse,
    OrderItemOut,
    OrderOut,
    ProductOut,
    ProposalOut,
)
from vendebot.batch.runner import DEFAULT_REVIEWS_CSV, load_reviews_from_csv, run_batch
from vendebot.chat.service import run_chat_turn
from vendebot.config import Settings
from vendebot.deps import get_current_customer, get_llm_client, get_repos, get_settings_dep
from vendebot.llm.base import LLMClient
from vendebot.observability.langfuse_client import traced_operation
from vendebot.orders.service import confirm_order, get_order_for_customer
from vendebot.repo.factory import Repos
from vendebot.repo.models import Customer

router = APIRouter()


@router.get("/products", response_model=list[ProductOut])
def list_products(query: str = "", repos: Repos = Depends(get_repos)):
    products = repos.products.search(query)
    return [ProductOut(**p.model_dump()) for p in products]


@router.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    customer: Customer = Depends(get_current_customer),
    repos: Repos = Depends(get_repos),
    llm_client: LLMClient = Depends(get_llm_client),
    settings: Settings = Depends(get_settings_dep),
):
    with traced_operation(settings, "chat", session_id=body.session_id, customer_id=customer.id) as trace_id:
        result = run_chat_turn(
            llm_client=llm_client,
            repos=repos,
            settings=settings,
            customer=customer,
            session_id=body.session_id,
            message=body.message,
        )
    proposal_out = None
    if result.proposal is not None:
        proposal_out = ProposalOut(
            proposal_id=result.proposal.id,
            items=[OrderItemOut(**i.model_dump()) for i in result.proposal.items],
            total=result.proposal.total,
            expires_at=result.proposal.expires_at,
        )
    return ChatResponse(reply=result.reply, proposal=proposal_out, tools_used=result.tools_used, trace_id=trace_id)


@router.post("/orders/confirm", response_model=OrderConfirmResponse)
def confirm(
    body: OrderConfirmRequest,
    customer: Customer = Depends(get_current_customer),
    repos: Repos = Depends(get_repos),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    order = confirm_order(repos, customer, body.proposal_id, body.confirm, idempotency_key)
    return OrderConfirmResponse(order_id=order.id, status=order.status, total=order.total)


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(
    order_id: str,
    customer: Customer = Depends(get_current_customer),
    repos: Repos = Depends(get_repos),
):
    order = get_order_for_customer(repos, customer, order_id)
    return OrderOut(
        order_id=order.id,
        status=order.status,
        total=order.total,
        items=[OrderItemOut(**i.model_dump()) for i in order.items],
    )


@router.post("/batch/reviews/run", response_model=BatchRunResponse)
def run_reviews_batch(
    repos: Repos = Depends(get_repos),
    llm_client: LLMClient = Depends(get_llm_client),
    settings: Settings = Depends(get_settings_dep),
):
    load_reviews_from_csv(repos.reviews, DEFAULT_REVIEWS_CSV)
    summary = run_batch(
        repos.reviews, llm_client, settings.batch_block_size, settings.batch_max_attempts, settings=settings
    )
    return BatchRunResponse(
        processed=summary.processed,
        succeeded=summary.succeeded,
        failed=summary.failed,
        blocks=summary.blocks,
    )
