"""Modelos Pydantic de entrada/salida de la API (contratos de /chat, /orders, /products)."""

from pydantic import BaseModel, Field


class ProductOut(BaseModel):
    id: str
    name: str
    price: float
    stock: int


class OrderItemOut(BaseModel):
    product_id: str
    name: str
    quantity: int
    unit_price: float


class ProposalOut(BaseModel):
    proposal_id: str
    items: list[OrderItemOut]
    total: float
    expires_at: str


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    reply: str
    proposal: ProposalOut | None = None
    tools_used: list[str]
    trace_id: str | None = None


class OrderConfirmRequest(BaseModel):
    proposal_id: str = Field(min_length=1)
    confirm: bool


class OrderConfirmResponse(BaseModel):
    order_id: str
    status: str
    total: float


class OrderOut(BaseModel):
    order_id: str
    status: str
    total: float
    items: list[OrderItemOut]


class BatchRunResponse(BaseModel):
    processed: int
    succeeded: int
    failed: int
    blocks: int
