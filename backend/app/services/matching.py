"""Deterministic payment/credit match suggestions (decision D-19: no AI in Release 1).

Suggestions are never applied automatically; a permitted user must confirm each allocation.
Rules, in priority order:
  1. reference/description contains the invoice number      → confidence "high"
  2. remaining amount equals the invoice balance exactly     → confidence "medium"
  3. other open invoices for the customer, oldest due first  → confidence "low"
For an unassigned bank receipt, invoice numbers found in the description suggest a customer.
"""
from __future__ import annotations

import re
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.money import ZERO, fmt
from app.models import Customer, Invoice, Organisation
from app.services.ledger import confirmed_total

_TOKEN = re.compile(r"[A-Z0-9][A-Z0-9\-/]*")


def _tokens(*texts: str | None) -> set[str]:
    out: set[str] = set()
    for t in texts:
        if t:
            for tok in _TOKEN.findall(t.upper()):
                out.add(tok.replace(" ", ""))
    return out


def _open_invoices(db: Session, org_id: uuid.UUID, customer_id: uuid.UUID | None) -> list[tuple[Invoice, Decimal]]:
    q = select(Invoice).where(Invoice.organisation_id == org_id, Invoice.status.in_(("open", "disputed")))
    if customer_id:
        q = q.where(Invoice.customer_id == customer_id)
    result = []
    for inv in db.scalars(q.order_by(Invoice.due_date, Invoice.invoice_number)):
        bal = inv.total_amount - confirmed_total(db, org_id, invoice_id=inv.id)
        if bal > ZERO:
            result.append((inv, bal))
    return result


def suggest(db: Session, org: Organisation, *, customer_id: uuid.UUID | None, remaining: Decimal,
            texts: tuple[str | None, ...], limit: int = 10) -> list[dict]:
    if remaining <= ZERO:
        return []
    tokens = _tokens(*texts)
    suggestions = []
    for inv, bal in _open_invoices(db, org.id, customer_id):
        if inv.normalised_number in tokens:
            confidence, reason = "high", "Invoice number appears in the payment reference"
        elif bal == remaining:
            confidence, reason = "medium", "Amount equals the invoice balance"
        elif customer_id is not None:
            confidence, reason = "low", "Open invoice for this customer (oldest due first)"
        else:
            continue  # without a customer, only reference matches are meaningful
        customer = db.get(Customer, inv.customer_id)
        suggestions.append({
            "invoice_id": str(inv.id),
            "invoice_number": inv.invoice_number,
            "customer_id": str(inv.customer_id),
            "customer_name": customer.name if customer else None,
            "due_date": inv.due_date.isoformat(),
            "invoice_balance": fmt(bal, org.currency),
            "suggested_amount": fmt(min(bal, remaining), org.currency),
            "confidence": confidence,
            "reason": reason,
            "requires_confirmation": True,
        })
    order = {"high": 0, "medium": 1, "low": 2}
    suggestions.sort(key=lambda s: (order[s["confidence"]], s["due_date"]))
    return suggestions[:limit]
