import uuid
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.common import reporting_date
from app.api.deps import OrgContext, require
from app.core.permissions import Perm
from app.domain.money import fmt
from app.models import Allocation, AuditEvent, CreditNote, Customer, InvoiceVersion, Payment
from app.services import customers as customer_svc, ledger, matching, reporting
from app.services.receivables import allocated_by_source

router = APIRouter(prefix="/orgs/{org_id}", tags=["invoices"])


class StatusIn(BaseModel):
    status: str
    reason: str = Field(min_length=1, max_length=300)


class CreditNoteIn(BaseModel):
    customer_id: uuid.UUID
    credit_note_number: str = Field(min_length=1, max_length=100)
    credit_date: date
    amount: str = Field(min_length=1, max_length=30)
    reason: str | None = Field(default=None, max_length=300)
    applies_to_invoice: str | None = Field(default=None, max_length=100)


def allocation_out(a: Allocation, currency: str) -> dict:
    return {"id": str(a.id), "invoice_id": str(a.invoice_id), "payment_id": str(a.payment_id) if a.payment_id else None,
            "credit_note_id": str(a.credit_note_id) if a.credit_note_id else None, "amount": fmt(a.amount, currency),
            "effective_date": a.effective_date.isoformat(), "status": a.status, "created_at": a.created_at.isoformat(),
            "reversed_at": a.reversed_at.isoformat() if a.reversed_at else None, "reversal_reason": a.reversal_reason}


@router.get("/invoices")
def list_invoices(as_at: date | None = None, customer_id: uuid.UUID | None = None, status: str | None = None,
                  q: str | None = None, issue_from: date | None = None, issue_to: date | None = None,
                  due_from: date | None = None, due_to: date | None = None,
                  ctx: OrgContext = Depends(require(Perm.VIEW))) -> dict:
    r = reporting_date(ctx, as_at)
    items = reporting.invoice_rows(ctx.db, ctx.org, r, customer_id=customer_id, status=status, search=q,
                                   issue_from=issue_from, issue_to=issue_to, due_from=due_from, due_to=due_to)
    return {"reporting_date": r.isoformat(), "currency": ctx.org.currency, "items": items}


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: uuid.UUID, as_at: date | None = None, ctx: OrgContext = Depends(require(Perm.VIEW))) -> dict:
    r = reporting_date(ctx, as_at)
    inv = ledger.get_invoice(ctx.db, ctx.org_id, invoice_id)
    row = next((x for x in reporting.invoice_rows(ctx.db, ctx.org, max(r, inv.issue_date), customer_id=inv.customer_id)
                if x["id"] == str(inv.id)), None)
    allocs = list(ctx.db.scalars(select(Allocation).where(Allocation.invoice_id == inv.id,
                                                          Allocation.organisation_id == ctx.org_id)
                                 .order_by(Allocation.effective_date, Allocation.created_at)))
    versions = list(ctx.db.scalars(select(InvoiceVersion).where(InvoiceVersion.invoice_id == inv.id)
                                   .order_by(InvoiceVersion.version)))
    history = list(ctx.db.scalars(select(AuditEvent).where(AuditEvent.organisation_id == ctx.org_id,
                                                           AuditEvent.entity_id.in_([inv.id, *[a.id for a in allocs]]))
                                  .order_by(AuditEvent.created_at)))
    return {
        **(row or {}), "reporting_date": r.isoformat(), "reference": inv.reference, "tax_amount": fmt(inv.tax_amount, inv.currency),
        "net_amount": fmt(inv.net_amount, inv.currency), "total_is_derived": inv.total_is_derived,
        "stored_status": inv.status, "status_reason": inv.status_reason, "version": inv.version,
        "source_row_id": str(inv.source_row_id) if inv.source_row_id else None,
        "allocations": [allocation_out(a, inv.currency) for a in allocs],
        "versions": [{"version": v.version, "values": v.values, "reason": v.change_reason,
                      "created_at": v.created_at.isoformat()} for v in versions],
        "history": [{"action": h.action, "at": h.created_at.isoformat(), "actor_user_id": str(h.actor_user_id) if h.actor_user_id else None,
                     "before": h.before, "after": h.after, "note": h.note} for h in history],
    }


@router.post("/invoices/{invoice_id}/status")
def change_status(invoice_id: uuid.UUID, body: StatusIn, ctx: OrgContext = Depends(require(Perm.MANAGE_CREDITS_AND_STATUS))) -> dict:
    inv = ledger.change_invoice_status(ctx.db, ctx.org, ctx.user.id, invoice_id, body.status, body.reason)
    ctx.db.commit()
    return {"id": str(inv.id), "status": inv.status, "version": inv.version}


def credit_note_out(ctx: OrgContext, c: CreditNote, allocated) -> dict:
    cust = ctx.db.get(Customer, c.customer_id)
    return {"id": str(c.id), "credit_note_number": c.credit_note_number, "customer_id": str(c.customer_id),
            "customer_name": cust.name if cust else None, "credit_date": c.credit_date.isoformat(),
            "amount": fmt(c.amount, c.currency), "allocated": fmt(allocated, c.currency),
            "unapplied": fmt(c.amount - allocated, c.currency), "reason": c.reason,
            "applies_to_invoice": c.applies_to_invoice_number}


@router.get("/credit-notes")
def list_credit_notes(customer_id: uuid.UUID | None = None, ctx: OrgContext = Depends(require(Perm.VIEW))) -> dict:
    q = select(CreditNote).where(CreditNote.organisation_id == ctx.org_id)
    if customer_id:
        q = q.where(CreditNote.customer_id == customer_id)
    credits = list(ctx.db.scalars(q.order_by(CreditNote.credit_date.desc())))
    allocated = allocated_by_source(ctx.db, ctx.org_id, credit_note_ids=[c.id for c in credits])
    from app.domain.money import ZERO

    return {"currency": ctx.org.currency, "items": [credit_note_out(ctx, c, allocated.get(c.id, ZERO)) for c in credits]}


@router.post("/credit-notes", status_code=201)
def create_credit_note(body: CreditNoteIn, ctx: OrgContext = Depends(require(Perm.MANAGE_CREDITS_AND_STATUS))) -> dict:
    customer_svc.get(ctx.db, ctx.org_id, body.customer_id)
    c = ledger.create_credit_note(ctx.db, ctx.org, ctx.user.id, customer_id=body.customer_id,
                                  number=body.credit_note_number, credit_date=body.credit_date, amount=body.amount,
                                  reason=body.reason, applies_to=body.applies_to_invoice)
    ctx.db.commit()
    from app.domain.money import ZERO

    return credit_note_out(ctx, c, ZERO)


@router.get("/credit-notes/{credit_note_id}")
def get_credit_note(credit_note_id: uuid.UUID, ctx: OrgContext = Depends(require(Perm.VIEW))) -> dict:
    c = ledger.get_credit_note(ctx.db, ctx.org_id, credit_note_id)
    allocs = list(ctx.db.scalars(select(Allocation).where(Allocation.credit_note_id == c.id).order_by(Allocation.created_at)))
    allocated = ledger.confirmed_total(ctx.db, ctx.org_id, credit_note_id=c.id)
    remaining = c.amount - allocated
    return {**credit_note_out(ctx, c, allocated), "allocations": [allocation_out(a, c.currency) for a in allocs],
            "suggestions": matching.suggest(ctx.db, ctx.org, customer_id=c.customer_id, remaining=remaining,
                                            texts=(c.applies_to_invoice_number, c.reason))}


__all__ = ["router", "allocation_out", "Payment"]
