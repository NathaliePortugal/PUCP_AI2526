"""Implementacion SQLite del patron repositorio.

`confirm_proposal` es la unica operacion que escribe stock: lo hace dentro de
una transaccion explicita (BEGIN IMMEDIATE) para que verificar stock y
descontarlo sea atomico, y usa la restriccion UNIQUE de `idempotency_key`
como red de seguridad si dos requests con la misma clave llegan a la vez.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from vendebot.errors import NotFoundError, OutOfStockError, ProposalExpiredError
from vendebot.repo.models import Customer, Order, OrderItem, Product, Proposal, Review


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_expired(expires_at_iso: str) -> bool:
    return datetime.now(timezone.utc) > datetime.fromisoformat(expires_at_iso)


def _items_from_json(raw: str) -> list[OrderItem]:
    return [OrderItem(**item) for item in json.loads(raw)]


def _items_to_json(items: list[OrderItem]) -> str:
    return json.dumps([item.model_dump() for item in items], ensure_ascii=False)


def _row_to_product(row: sqlite3.Row) -> Product:
    return Product(id=row["id"], name=row["name"], price=row["price"], stock=row["stock"])


def _row_to_customer(row: sqlite3.Row) -> Customer:
    return Customer(id=row["id"], name=row["name"], api_key=row["api_key"])


def _row_to_proposal(row: sqlite3.Row) -> Proposal:
    return Proposal(
        id=row["id"],
        customer_id=row["customer_id"],
        items=_items_from_json(row["items_json"]),
        total=row["total"],
        status=row["status"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
    )


def _row_to_order(row: sqlite3.Row) -> Order:
    return Order(
        id=row["id"],
        customer_id=row["customer_id"],
        proposal_id=row["proposal_id"],
        items=_items_from_json(row["items_json"]),
        total=row["total"],
        status=row["status"],
        idempotency_key=row["idempotency_key"],
        created_at=row["created_at"],
    )


def _row_to_review(row: sqlite3.Row) -> Review:
    return Review(
        id=row["id"],
        customer_id=row["customer_id"],
        product_id=row["product_id"],
        content=row["content"],
        content_hash=row["content_hash"],
        status=row["status"],
        attempts=row["attempts"],
        label=row["label"],
        motivo=row["motivo"],
        evidencia=row["evidencia"],
        confianza=row["confianza"],
    )


class SqliteProductsRepo:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def search(self, query: str) -> list[Product]:
        rows = self._conn.execute(
            "SELECT * FROM products WHERE name LIKE ? ORDER BY name", (f"%{query}%",)
        ).fetchall()
        return [_row_to_product(r) for r in rows]

    def get(self, product_id: str) -> Product | None:
        row = self._conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        return _row_to_product(row) if row else None


class SqliteCustomersRepo:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def get_by_api_key(self, api_key: str) -> Customer | None:
        row = self._conn.execute("SELECT * FROM customers WHERE api_key = ?", (api_key,)).fetchone()
        return _row_to_customer(row) if row else None


class SqliteProposalsRepo:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def create(self, customer_id: str, items: list[OrderItem], total: float, ttl_minutes: int) -> Proposal:
        proposal = Proposal(
            id=f"PR-{uuid.uuid4().hex[:10]}",
            customer_id=customer_id,
            items=items,
            total=total,
            status="pending",
            created_at=_now_iso(),
            expires_at=(datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)).isoformat(),
        )
        self._conn.execute(
            "INSERT INTO proposals (id, customer_id, items_json, total, status, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                proposal.id,
                proposal.customer_id,
                _items_to_json(proposal.items),
                proposal.total,
                proposal.status,
                proposal.created_at,
                proposal.expires_at,
            ),
        )
        self._conn.commit()
        return proposal

    def get(self, proposal_id: str) -> Proposal | None:
        row = self._conn.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
        return _row_to_proposal(row) if row else None


class SqliteOrdersRepo:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def get(self, order_id: str) -> Order | None:
        row = self._conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return _row_to_order(row) if row else None

    def get_by_idempotency_key(self, idempotency_key: str) -> Order | None:
        row = self._conn.execute(
            "SELECT * FROM orders WHERE idempotency_key = ?", (idempotency_key,)
        ).fetchone()
        return _row_to_order(row) if row else None

    def list_by_customer(self, customer_id: str) -> list[Order]:
        rows = self._conn.execute(
            "SELECT * FROM orders WHERE customer_id = ? ORDER BY created_at DESC", (customer_id,)
        ).fetchall()
        return [_row_to_order(r) for r in rows]

    def confirm_proposal(self, proposal_id: str, customer_id: str, idempotency_key: str) -> Order:
        existing = self.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing

        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
            if row is None or row["customer_id"] != customer_id:
                raise NotFoundError("La propuesta no existe")

            proposal = _row_to_proposal(row)
            if proposal.status != "pending" or _is_expired(proposal.expires_at):
                raise ProposalExpiredError("La propuesta expiro o ya fue usada")

            for item in proposal.items:
                stock_row = conn.execute(
                    "SELECT stock FROM products WHERE id = ?", (item.product_id,)
                ).fetchone()
                if stock_row is None or stock_row["stock"] < item.quantity:
                    raise OutOfStockError(f"Sin stock suficiente de {item.name}")

            for item in proposal.items:
                conn.execute(
                    "UPDATE products SET stock = stock - ? WHERE id = ?",
                    (item.quantity, item.product_id),
                )

            order_id = f"O-{uuid.uuid4().hex[:10]}"
            created_at = _now_iso()
            conn.execute(
                "INSERT INTO orders "
                "(id, customer_id, proposal_id, items_json, total, status, idempotency_key, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'confirmed', ?, ?)",
                (
                    order_id,
                    customer_id,
                    proposal_id,
                    _items_to_json(proposal.items),
                    proposal.total,
                    idempotency_key,
                    created_at,
                ),
            )
            conn.execute("UPDATE proposals SET status = 'confirmed' WHERE id = ?", (proposal_id,))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            existing = self.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing
            raise
        except Exception:
            conn.rollback()
            raise

        return self.get(order_id)


class SqliteSessionsRepo:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def get_history(self, session_id: str, customer_id: str) -> list[dict]:
        row = self._conn.execute(
            "SELECT history_json FROM chat_sessions WHERE session_id = ? AND customer_id = ?",
            (session_id, customer_id),
        ).fetchone()
        return json.loads(row["history_json"]) if row else []

    def append_turn(self, session_id: str, customer_id: str, role: str, text: str) -> None:
        history = self.get_history(session_id, customer_id)
        history.append({"role": role, "text": text})
        self._conn.execute(
            "INSERT INTO chat_sessions (session_id, customer_id, history_json) VALUES (?, ?, ?) "
            "ON CONFLICT(session_id, customer_id) DO UPDATE SET history_json = excluded.history_json",
            (session_id, customer_id, json.dumps(history, ensure_ascii=False)),
        )
        self._conn.commit()


class SqliteBudgetRepo:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def get_usage_today(self, customer_id: str) -> int:
        today = datetime.now(timezone.utc).date().isoformat()
        row = self._conn.execute(
            "SELECT tokens_used FROM token_usage WHERE customer_id = ? AND usage_date = ?",
            (customer_id, today),
        ).fetchone()
        return row["tokens_used"] if row else 0

    def add_usage(self, customer_id: str, tokens: int) -> None:
        today = datetime.now(timezone.utc).date().isoformat()
        self._conn.execute(
            "INSERT INTO token_usage (customer_id, usage_date, tokens_used) VALUES (?, ?, ?) "
            "ON CONFLICT(customer_id, usage_date) DO UPDATE SET tokens_used = tokens_used + excluded.tokens_used",
            (customer_id, today, tokens),
        )
        self._conn.commit()


class SqliteReviewsRepo:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def ensure_queued(
        self, review_id: str, customer_id: str, product_id: str, content: str, content_hash: str
    ) -> None:
        """Solo inserta si el id todavia no existe: relanzar el lote con el
        mismo CSV nunca pisa el progreso (pending/done/failed) ya guardado."""
        self._conn.execute(
            "INSERT INTO reviews (id, customer_id, product_id, content, content_hash, status, attempts) "
            "VALUES (?, ?, ?, ?, ?, 'pending', 0) ON CONFLICT(id) DO NOTHING",
            (review_id, customer_id, product_id, content, content_hash),
        )
        self._conn.commit()

    def get(self, review_id: str) -> Review | None:
        row = self._conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
        return _row_to_review(row) if row else None

    def list_to_process(self, max_attempts: int, limit: int) -> list[Review]:
        rows = self._conn.execute(
            "SELECT * FROM reviews WHERE status = 'pending' "
            "OR (status = 'failed' AND attempts < ?) ORDER BY id LIMIT ?",
            (max_attempts, limit),
        ).fetchall()
        return [_row_to_review(r) for r in rows]

    def mark_done(self, review_id: str, label: str, motivo: str, evidencia: str, confianza: float) -> None:
        self._conn.execute(
            "UPDATE reviews SET status = 'done', label = ?, motivo = ?, evidencia = ?, confianza = ?, "
            "updated_at = ? WHERE id = ?",
            (label, motivo, evidencia, confianza, _now_iso(), review_id),
        )
        self._conn.commit()

    def mark_failed(self, review_id: str) -> None:
        self._conn.execute(
            "UPDATE reviews SET status = 'failed', attempts = attempts + 1, updated_at = ? WHERE id = ?",
            (_now_iso(), review_id),
        )
        self._conn.commit()
