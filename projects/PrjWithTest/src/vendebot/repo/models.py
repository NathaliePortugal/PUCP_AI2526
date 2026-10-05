"""Modelos de las filas que viven en el repositorio (SQLite/Firestore)."""

from pydantic import BaseModel


class Product(BaseModel):
    id: str
    name: str
    price: float
    stock: int


class Customer(BaseModel):
    id: str
    name: str
    api_key: str


class OrderItem(BaseModel):
    product_id: str
    name: str
    quantity: int
    unit_price: float


class Proposal(BaseModel):
    id: str
    customer_id: str
    items: list[OrderItem]
    total: float
    status: str  # pending | confirmed | expired
    created_at: str
    expires_at: str


class Order(BaseModel):
    id: str
    customer_id: str
    proposal_id: str
    items: list[OrderItem]
    total: float
    status: str
    idempotency_key: str
    created_at: str


class Review(BaseModel):
    id: str
    customer_id: str
    product_id: str
    content: str
    content_hash: str
    status: str  # pending | done | failed
    attempts: int
    label: str | None = None
    motivo: str | None = None
    evidencia: str | None = None
    confianza: float | None = None
