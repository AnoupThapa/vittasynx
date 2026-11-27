import uuid
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import OrgContext, require
from app.api.routers.invoices import allocation_out
from app.core.permissions import Perm
from app.domain.money import ZERO, fmt
from app.models import Allocation, Customer, Payment
from app.services import customers as customer_svc, ledger, matching
from app.services.receivables import allocated_by_source

router = APIRouter(prefix="/orgs/{org_id}/payments", tags=["payments"])


class PaymentIn(BaseModel):
    customer_id: uuid.UUID
    payment_date: date
    amount: str = Field(min_length=1, max_length=30)
    reference: str | None = Field(default=None, max_length=200)
    method: str | None = Field(default=None, max_length=50)


class AssignIn(BaseModel):
    customer_id: uuid.UUID


def payment_out(ctx: OrgContext, p: Payment, allocated) -> dict:
    cust = ctx.db.get(Customer, p.customer_id) if p.customer_id else None
    return {"id": str(p.id), "customer_id": str(p.customer_id) if p.customer_id else None,
            "customer_name": cust.name if cust else None, "payment_date": p.payment_date.isoformat(),
            "amount": fmt(p.amount, p.currency), "allocated": fmt(allocated, p.currency),
            "unapplied": fmt(p.amount - allocated, p.currency), "reference": p.reference,
            "description": p.description, "method": p.method, "source": p.source,
            "assigned": p.customer_id is not None}


@router.get("")
def list_payments(customer_id: uuid.UUID | None = None, unapplied_only: bool = False, unassigned_only: bool = False,
                  ctx: OrgContext = Depends(require(Perm.VIEW))) -> dict:
    q = select(Payment).where(Payment.organisation_id == ctx.org_id)
    if customer_id:
        q = q.where(Payment.customer_id == customer_id)
    if unassigned_only:
        q = q.where(Payment.customer_id.is_(None))
    payments = list(ctx.db.scalars(q.order_by(Payment.payment_date.desc(), Payment.created_at.desc()).limit(1000)))
    allocated = allocated_by_source(ctx.db, ctx.org_id, payment_ids=[p.id for p in payments])
    items = [payment_out(ctx, p, allocated.get(p.id, ZERO)) for p in payments]
    if unapplied_only:
        items = [i for i in items if i["unapplied"] != fmt(ZERO, ctx.org.currency)]
    return {"currency": ctx.org.currency, "items": items}


@router.post("", status_code=201)
def create_payment(body: PaymentIn, ctx: OrgContext = Depends(require(Perm.RECORD_PAYMENT))) -> dict:
    customer_svc.get(ctx.db, ctx.org_id, body.customer_id)
    p = ledger.create_payment(ctx.db, ctx.org, ctx.user.id, customer_id=body.customer_id,
                              payment_date=body.payment_date, amount=body.amount, reference=body.reference,
                              description=None, method=body.method, source="manual")
    ctx.db.commit()
    return payment_out(ctx, p, ZERO)


@router.get("/{payment_id}")
def get_payment(payment_id: uuid.UUID, ctx: OrgContext = Depends(require(Perm.VIEW))) -> dict:
    p = ledger.get_payment(ctx.db, ctx.org_id, payment_id)
    allocs = list(ctx.db.scalars(select(Allocation).where(Allocation.payment_id == p.id).order_by(Allocation.created_at)))
    allocated = ledger.confirmed_total(ctx.db, ctx.org_id, payment_id=p.id)
    return {**payment_out(ctx, p, allocated), "allocations": [allocation_out(a, p.currency) for a in allocs],
            "suggestions": matching.suggest(ctx.db, ctx.org, customer_id=p.customer_id, remaining=p.amount - allocated,
                                            texts=(p.reference, p.description))}


@router.post("/{payment_id}/assign-customer")
def assign_customer(payment_id: uuid.UUID, body: AssignIn, ctx: OrgContext = Depends(require(Perm.RECORD_PAYMENT))) -> dict:
    customer_svc.get(ctx.db, ctx.org_id, body.customer_id)
    p = ledger.assign_payment_customer(ctx.db, ctx.org, ctx.user.id, payment_id, body.customer_id)
    ctx.db.commit()
    return payment_out(ctx, p, ledger.confirmed_total(ctx.db, ctx.org_id, payment_id=p.id))
