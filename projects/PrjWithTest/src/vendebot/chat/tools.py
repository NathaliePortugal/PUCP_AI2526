"""Herramientas que el LLM puede invocar durante /chat.

`propose_order` es la unica que escribe algo: crea una propuesta (nunca un
pedido). El LLM no puede dar descuentos, cambiar precios ni ver pedidos de
otro cliente -- no existe ninguna herramienta para eso, asi que no hay nada
que "prohibir" en tiempo de ejecucion, la restriccion esta en el catalogo de
herramientas disponible.
"""

from typing import Any

from vendebot.repo.factory import Repos
from vendebot.repo.models import Customer, OrderItem, Proposal

TOOL_SPECS: list[dict] = [
    {
        "type": "function",
        "name": "search_products",
        "description": "Busca productos del catalogo por nombre o palabra clave",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "texto a buscar"}},
            "required": ["query"],
        },
    },
    {
        "type": "function",
        "name": "get_stock",
        "description": "Consulta el stock disponible de un producto por su id",
        "parameters": {
            "type": "object",
            "properties": {"product_id": {"type": "string"}},
            "required": ["product_id"],
        },
    },
    {
        "type": "function",
        "name": "get_my_orders",
        "description": "Lista los pedidos del cliente autenticado en esta conversacion",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "propose_order",
        "description": (
            "Propone un pedido con una lista de items. No lo confirma ni descuenta stock: "
            "el cliente debe confirmarlo explicitamente despues."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string"},
                            "quantity": {"type": "integer", "minimum": 1},
                        },
                        "required": ["product_id", "quantity"],
                    },
                }
            },
            "required": ["items"],
        },
    },
]


def _build_order_items(
    repos: Repos, raw_items: list[dict]
) -> tuple[list[OrderItem] | None, float | None, str | None]:
    items: list[OrderItem] = []
    total = 0.0
    for raw in raw_items:
        product = repos.products.get(raw.get("product_id", ""))
        quantity = int(raw.get("quantity", 0))
        if product is None:
            return None, None, f"El producto {raw.get('product_id')} no existe"
        if quantity <= 0:
            return None, None, "La cantidad debe ser mayor a cero"
        if product.stock < quantity:
            return None, None, f"No hay stock suficiente de {product.name} (disponible: {product.stock})"
        items.append(
            OrderItem(product_id=product.id, name=product.name, quantity=quantity, unit_price=product.price)
        )
        total += product.price * quantity
    return items, round(total, 2), None


def execute_tool(
    name: str,
    arguments: dict[str, Any],
    repos: Repos,
    customer: Customer,
    proposal_ttl_minutes: int,
) -> tuple[Any, Proposal | None]:
    if name == "search_products":
        products = repos.products.search(arguments.get("query", ""))
        return [p.model_dump() for p in products], None

    if name == "get_stock":
        product = repos.products.get(arguments.get("product_id", ""))
        if product is None:
            return {"error": "producto no encontrado"}, None
        return {"product_id": product.id, "stock": product.stock}, None

    if name == "get_my_orders":
        orders = repos.orders.list_by_customer(customer.id)
        return [o.model_dump() for o in orders], None

    if name == "propose_order":
        items, total, error = _build_order_items(repos, arguments.get("items", []))
        if error:
            return {"error": error}, None
        proposal = repos.proposals.create(customer.id, items, total, proposal_ttl_minutes)
        return (
            {
                "proposal_id": proposal.id,
                "items": [i.model_dump() for i in items],
                "total": total,
                "expires_at": proposal.expires_at,
            },
            proposal,
        )

    raise ValueError(f"Herramienta desconocida: {name}")
