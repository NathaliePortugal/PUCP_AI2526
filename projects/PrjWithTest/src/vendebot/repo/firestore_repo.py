"""Implementacion Firestore (modo nativo) del patron repositorio, usada
cuando STORAGE_BACKEND=firestore (despliegue en GCP).

Mismo contrato de metodos que repo/sqlite_repo.py: el resto de la app no
sabe cual backend esta detras del bundle `Repos`.

Firestore no tiene una restriccion UNIQUE nativa como SQL, asi que la
idempotencia de `confirm_proposal` se protege con un documento-candado en la
coleccion `idempotency_keys`: `transaction.create()` falla con
AlreadyExists si otro request ya reclamo esa clave, que es el equivalente
transaccional al UNIQUE de SQLite.

Nota: no probada contra un proyecto de GCP real ni contra el emulador de
Firestore.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore

from vendebot.errors import NotFoundError, OutOfStockError, ProposalExpiredError
from vendebot.repo.models import Customer, Order, OrderItem, Product, Proposal, Review


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_expired(expires_at_iso: str) -> bool:
    return datetime.now(timezone.utc) > datetime.fromisoformat(expires_at_iso)


class FirestoreProductsRepo:
    def __init__(self, db: firestore.Client):
        self._db = db

    def search(self, query: str) -> list[Product]:
        query_lower = query.lower()
        docs = self._db.collection("products").stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            if query_lower in data["name"].lower():
                results.append(Product(id=doc.id, name=data["name"], price=data["price"], stock=data["stock"]))
        return sorted(results, key=lambda p: p.name)

    def get(self, product_id: str) -> Product | None:
        doc = self._db.collection("products").document(product_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        return Product(id=doc.id, name=data["name"], price=data["price"], stock=data["stock"])


class FirestoreCustomersRepo:
    def __init__(self, db: firestore.Client):
        self._db = db

    def get_by_api_key(self, api_key: str) -> Customer | None:
        docs = list(self._db.collection("customers").where("api_key", "==", api_key).limit(1).stream())
        if not docs:
            return None
        data = docs[0].to_dict()
        return Customer(id=docs[0].id, name=data["name"], api_key=data["api_key"])


class FirestoreProposalsRepo:
    def __init__(self, db: firestore.Client):
        self._db = db

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
        self._db.collection("proposals").document(proposal.id).set(
            {
                "customer_id": proposal.customer_id,
                "items": [i.model_dump() for i in proposal.items],
                "total": proposal.total,
                "status": proposal.status,
                "created_at": proposal.created_at,
                "expires_at": proposal.expires_at,
            }
        )
        return proposal

    def get(self, proposal_id: str) -> Proposal | None:
        doc = self._db.collection("proposals").document(proposal_id).get()
        if not doc.exists:
            return None
        return _doc_to_proposal(proposal_id, doc.to_dict())


def _doc_to_proposal(doc_id: str, data: dict) -> Proposal:
    return Proposal(
        id=doc_id,
        customer_id=data["customer_id"],
        items=[OrderItem(**i) for i in data["items"]],
        total=data["total"],
        status=data["status"],
        created_at=data["created_at"],
        expires_at=data["expires_at"],
    )


def _doc_to_order(doc_id: str, data: dict) -> Order:
    return Order(
        id=doc_id,
        customer_id=data["customer_id"],
        proposal_id=data["proposal_id"],
        items=[OrderItem(**i) for i in data["items"]],
        total=data["total"],
        status=data["status"],
        idempotency_key=data["idempotency_key"],
        created_at=data["created_at"],
    )


class FirestoreOrdersRepo:
    def __init__(self, db: firestore.Client):
        self._db = db

    def get(self, order_id: str) -> Order | None:
        doc = self._db.collection("orders").document(order_id).get()
        if not doc.exists:
            return None
        return _doc_to_order(order_id, doc.to_dict())

    def get_by_idempotency_key(self, idempotency_key: str) -> Order | None:
        lock_doc = self._db.collection("idempotency_keys").document(idempotency_key).get()
        if not lock_doc.exists:
            return None
        return self.get(lock_doc.to_dict()["order_id"])

    def list_by_customer(self, customer_id: str) -> list[Order]:
        docs = self._db.collection("orders").where("customer_id", "==", customer_id).stream()
        orders = [_doc_to_order(d.id, d.to_dict()) for d in docs]
        return sorted(orders, key=lambda o: o.created_at, reverse=True)

    def confirm_proposal(self, proposal_id: str, customer_id: str, idempotency_key: str) -> Order:
        existing = self.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing

        db = self._db
        order_id = f"O-{uuid.uuid4().hex[:10]}"
        transaction = db.transaction()
        proposal_ref = db.collection("proposals").document(proposal_id)
        lock_ref = db.collection("idempotency_keys").document(idempotency_key)
        order_ref = db.collection("orders").document(order_id)

        @firestore.transactional
        def _run(transaction):
            proposal_snapshot = proposal_ref.get(transaction=transaction)
            if not proposal_snapshot.exists:
                raise NotFoundError("La propuesta no existe")
            data = proposal_snapshot.to_dict()
            if data["customer_id"] != customer_id:
                raise NotFoundError("La propuesta no existe")

            proposal = _doc_to_proposal(proposal_id, data)
            if proposal.status != "pending" or _is_expired(proposal.expires_at):
                raise ProposalExpiredError("La propuesta expiro o ya fue usada")

            product_refs = {item.product_id: db.collection("products").document(item.product_id) for item in proposal.items}
            product_snapshots = {pid: ref.get(transaction=transaction) for pid, ref in product_refs.items()}

            for item in proposal.items:
                snapshot = product_snapshots[item.product_id]
                if not snapshot.exists or snapshot.to_dict()["stock"] < item.quantity:
                    raise OutOfStockError(f"Sin stock suficiente de {item.name}")

            try:
                transaction.create(lock_ref, {"order_id": order_id})
            except AlreadyExists as exc:
                raise ProposalExpiredError("Esta solicitud ya fue procesada") from exc

            for item in proposal.items:
                snapshot = product_snapshots[item.product_id]
                transaction.update(
                    product_refs[item.product_id], {"stock": snapshot.to_dict()["stock"] - item.quantity}
                )

            created_at = _now_iso()
            transaction.set(
                order_ref,
                {
                    "customer_id": customer_id,
                    "proposal_id": proposal_id,
                    "items": [i.model_dump() for i in proposal.items],
                    "total": proposal.total,
                    "status": "confirmed",
                    "idempotency_key": idempotency_key,
                    "created_at": created_at,
                },
            )
            transaction.update(proposal_ref, {"status": "confirmed"})

        _run(transaction)
        return self.get(order_id)


class FirestoreSessionsRepo:
    def __init__(self, db: firestore.Client):
        self._db = db

    def _doc_ref(self, session_id: str, customer_id: str):
        return self._db.collection("chat_sessions").document(f"{session_id}::{customer_id}")

    def get_history(self, session_id: str, customer_id: str) -> list[dict]:
        doc = self._doc_ref(session_id, customer_id).get()
        if not doc.exists:
            return []
        return doc.to_dict().get("history", [])

    def append_turn(self, session_id: str, customer_id: str, role: str, text: str) -> None:
        history = self.get_history(session_id, customer_id)
        history.append({"role": role, "text": text})
        self._doc_ref(session_id, customer_id).set({"customer_id": customer_id, "history": history})


class FirestoreBudgetRepo:
    def __init__(self, db: firestore.Client):
        self._db = db

    def _doc_ref(self, customer_id: str):
        today = datetime.now(timezone.utc).date().isoformat()
        return self._db.collection("token_usage").document(f"{customer_id}::{today}")

    def get_usage_today(self, customer_id: str) -> int:
        doc = self._doc_ref(customer_id).get()
        return doc.to_dict().get("tokens_used", 0) if doc.exists else 0

    def add_usage(self, customer_id: str, tokens: int) -> None:
        ref = self._doc_ref(customer_id)
        ref.set({"tokens_used": firestore.Increment(tokens)}, merge=True)


class FirestoreReviewsRepo:
    def __init__(self, db: firestore.Client):
        self._db = db

    def ensure_queued(
        self, review_id: str, customer_id: str, product_id: str, content: str, content_hash: str
    ) -> None:
        ref = self._db.collection("reviews").document(review_id)
        if ref.get().exists:
            return
        ref.set(
            {
                "customer_id": customer_id,
                "product_id": product_id,
                "content": content,
                "content_hash": content_hash,
                "status": "pending",
                "attempts": 0,
                "label": None,
                "motivo": None,
                "evidencia": None,
                "confianza": None,
            }
        )

    def get(self, review_id: str) -> Review | None:
        doc = self._db.collection("reviews").document(review_id).get()
        if not doc.exists:
            return None
        return _doc_to_review(review_id, doc.to_dict())

    def list_to_process(self, max_attempts: int, limit: int) -> list[Review]:
        pending = list(self._db.collection("reviews").where("status", "==", "pending").limit(limit).stream())
        remaining = limit - len(pending)
        failed: list[Any] = []
        if remaining > 0:
            failed = [
                d
                for d in self._db.collection("reviews").where("status", "==", "failed").stream()
                if d.to_dict().get("attempts", 0) < max_attempts
            ][:remaining]
        return [_doc_to_review(d.id, d.to_dict()) for d in [*pending, *failed]]

    def mark_done(self, review_id: str, label: str, motivo: str, evidencia: str, confianza: float) -> None:
        self._db.collection("reviews").document(review_id).update(
            {
                "status": "done",
                "label": label,
                "motivo": motivo,
                "evidencia": evidencia,
                "confianza": confianza,
                "updated_at": _now_iso(),
            }
        )

    def mark_failed(self, review_id: str) -> None:
        self._db.collection("reviews").document(review_id).update(
            {"status": "failed", "attempts": firestore.Increment(1), "updated_at": _now_iso()}
        )


def _doc_to_review(doc_id: str, data: dict) -> Review:
    return Review(
        id=doc_id,
        customer_id=data["customer_id"],
        product_id=data["product_id"],
        content=data["content"],
        content_hash=data["content_hash"],
        status=data["status"],
        attempts=data.get("attempts", 0),
        label=data.get("label"),
        motivo=data.get("motivo"),
        evidencia=data.get("evidencia"),
        confianza=data.get("confianza"),
    )


def build_firestore_repos(settings):
    from vendebot.repo.factory import Repos

    db = firestore.Client(project=settings.gcp_project_id)
    return Repos(
        products=FirestoreProductsRepo(db),
        customers=FirestoreCustomersRepo(db),
        proposals=FirestoreProposalsRepo(db),
        orders=FirestoreOrdersRepo(db),
        sessions=FirestoreSessionsRepo(db),
        budget=FirestoreBudgetRepo(db),
        reviews=FirestoreReviewsRepo(db),
    )
