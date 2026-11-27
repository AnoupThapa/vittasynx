"""Loads tenant-scoped records into calculation facts. All arithmetic lives in app.domain."""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.money import ZERO
from app.domain.receivables import AllocationFact, InvoiceFact
from app.models import Allocation, CreditNote, Invoice, Organisation, Payment


def org_today(org: Organisation) -> date:
    return datetime.now(ZoneInfo(org.timezone)).date()


def invoice_facts(
    db: Session,
    org_id: uuid.UUID,
    *,
    customer_id: uuid.UUID | None = None,
    invoice_ids: list[uuid.UUID] | None = None,
) -> tuple[dict[uuid.UUID, InvoiceFact], dict[uuid.UUID, Invoice]]:
    q = select(Invoice).where(Invoice.organisation_id == org_id)
    if customer_id:
        q = q.where(Invoice.customer_id == customer_id)
    if invoice_ids is not None:
        q = q.where(Invoice.id.in_(invoice_ids))
    invoices = {inv.id: inv for inv in db.scalars(q)}
    allocs: dict[uuid.UUID, list[AllocationFact]] = defaultdict(list)
    if invoices:
        aq = select(Allocation).where(
            Allocation.organisation_id == org_id,
            Allocation.status == "confirmed",
            Allocation.invoice_id.in_(list(invoices)),
        )
        for a in db.scalars(aq):
            allocs[a.invoice_id].append(
                AllocationFact(a.amount, a.effective_date, "payment" if a.payment_id else "credit")
            )
    facts = {
        inv.id: InvoiceFact(
            id=inv.id,
            customer_id=inv.customer_id,
            issue_date=inv.issue_date,
            due_date=inv.due_date,
            amount=inv.total_amount,
            status=inv.status,
            allocations=tuple(allocs.get(inv.id, ())),
        )
        for inv in invoices.values()
    }
    return facts, invoices


def allocated_by_source(db: Session, org_id: uuid.UUID, *, payment_ids=None, credit_note_ids=None) -> dict[uuid.UUID, Decimal]:
    out: dict[uuid.UUID, Decimal] = {}
    if payment_ids:
        rows = db.execute(
            select(Allocation.payment_id, func.sum(Allocation.amount))
            .where(Allocation.organisation_id == org_id, Allocation.status == "confirmed",
                   Allocation.payment_id.in_(list(payment_ids)))
            .group_by(Allocation.payment_id)
        )
        out.update({pid: total for pid, total in rows})
    if credit_note_ids:
        rows = db.execute(
            select(Allocation.credit_note_id, func.sum(Allocation.amount))
            .where(Allocation.organisation_id == org_id, Allocation.status == "confirmed",
                   Allocation.credit_note_id.in_(list(credit_note_ids)))
            .group_by(Allocation.credit_note_id)
        )
        out.update({cid: total for cid, total in rows})
    return out


def unapplied_payments(db: Session, org_id: uuid.UUID, as_at: date, customer_id: uuid.UUID | None = None) -> list[tuple[Payment, Decimal]]:
    q = select(Payment).where(Payment.organisation_id == org_id, Payment.payment_date <= as_at)
    if customer_id:
        q = q.where(Payment.customer_id == customer_id)
    payments = list(db.scalars(q))
    allocated = allocated_by_source(db, org_id, payment_ids=[p.id for p in payments])
    result = []
    for p in payments:
        rem = p.amount - allocated.get(p.id, ZERO)
        if rem > ZERO:
            result.append((p, rem))
    return result


def unapplied_credits(db: Session, org_id: uuid.UUID, as_at: date, customer_id: uuid.UUID | None = None) -> list[tuple[CreditNote, Decimal]]:
    q = select(CreditNote).where(CreditNote.organisation_id == org_id, CreditNote.credit_date <= as_at)
    if customer_id:
        q = q.where(CreditNote.customer_id == customer_id)
    credits = list(db.scalars(q))
    allocated = allocated_by_source(db, org_id, credit_note_ids=[c.id for c in credits])
    result = []
    for c in credits:
        rem = c.amount - allocated.get(c.id, ZERO)
        if rem > ZERO:
            result.append((c, rem))
    return result
