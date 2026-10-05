"""Flujo de confirmacion de pedido: el control explicito antes de la accion
sensible (descontar stock) vive aqui, no en el LLM."""

from vendebot.errors import NotFoundError, ValidationError
from vendebot.repo.factory import Repos
from vendebot.repo.models import Customer, Order


def confirm_order(
    repos: Repos,
    customer: Customer,
    proposal_id: str,
    confirm: bool,
    idempotency_key: str | None,
) -> Order:
    if not confirm:
        raise ValidationError("Debes confirmar explicitamente para crear el pedido (confirm=true)")
    if not idempotency_key:
        raise ValidationError("Falta el header Idempotency-Key")
    return repos.orders.confirm_proposal(proposal_id, customer.id, idempotency_key)


def get_order_for_customer(repos: Repos, customer: Customer, order_id: str) -> Order:
    order = repos.orders.get(order_id)
    if order is None or order.customer_id != customer.id:
        raise NotFoundError("Pedido no encontrado")
    return order
