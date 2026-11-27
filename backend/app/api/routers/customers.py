import uuid
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.common import reporting_date
from app.api.deps import OrgContext, require
from app.core.permissions import Perm
from app.models import Customer
from app.services import customers as svc, reporting

router = APIRouter(prefix="/orgs/{org_id}/customers", tags=["customers"])


class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    code: str | None = Field(default=None, max_length=100)


class CustomerPatch(BaseModel):
    name: str | None = Field(default=None, max_length=300)
    code: str | None = Field(default=None, max_length=100)
    status: str | None = None


def customer_out(c: Customer) -> dict:
    return {"id": str(c.id), "code": c.code, "name": c.name, "status": c.status, "created_at": c.created_at.isoformat()}


@router.get("")
def list_customers(q: str | None = None, status: str | None = None, as_at: date | None = None,
                   ctx: OrgContext = Depends(require(Perm.VIEW))) -> dict:
    r = reporting_date(ctx, as_at)
    balances = {b["customer_id"]: b for b in reporting.customer_balances(ctx.db, ctx.org, r)}
    items = []
    for c in svc.search(ctx.db, ctx.org_id, q, status):
        b = balances.get(str(c.id), {})
        items.append({**customer_out(c), "total_outstanding": b.get("total_outstanding"), "overdue": b.get("overdue"),
                      "unapplied_payments": b.get("unapplied_payments")})
    return {"reporting_date": r.isoformat(), "currency": ctx.org.currency, "items": items}


@router.post("", status_code=201)
def create_customer(body: CustomerIn, ctx: OrgContext = Depends(require(Perm.MANAGE_CUSTOMERS))) -> dict:
    c = svc.create(ctx.db, ctx.org_id, ctx.user.id, body.name, body.code)
    ctx.db.commit()
    return customer_out(c)


@router.get("/{customer_id}")
def get_customer(customer_id: uuid.UUID, as_at: date | None = None, ctx: OrgContext = Depends(require(Perm.VIEW))) -> dict:
    r = reporting_date(ctx, as_at)
    c = svc.get(ctx.db, ctx.org_id, customer_id)
    balance = next((b for b in reporting.customer_balances(ctx.db, ctx.org, r) if b["customer_id"] == str(c.id)), None)
    return {**customer_out(c), "reporting_date": r.isoformat(), "currency": ctx.org.currency, "balances": balance,
            "invoices": reporting.invoice_rows(ctx.db, ctx.org, r, customer_id=c.id),
            "behaviour": reporting.behaviour(ctx.db, ctx.org, c.id, r)}


@router.patch("/{customer_id}")
def update_customer(customer_id: uuid.UUID, body: CustomerPatch,
                    ctx: OrgContext = Depends(require(Perm.MANAGE_CUSTOMERS))) -> dict:
    c = svc.get(ctx.db, ctx.org_id, customer_id)
    svc.update(ctx.db, ctx.org_id, ctx.user.id, c, name=body.name, code=body.code, status=body.status,
               code_set="code" in body.model_fields_set)
    ctx.db.commit()
    return customer_out(c)


@router.get("/{customer_id}/behaviour")
def customer_behaviour(customer_id: uuid.UUID, as_at: date | None = None,
                       ctx: OrgContext = Depends(require(Perm.VIEW))) -> dict:
    c = svc.get(ctx.db, ctx.org_id, customer_id)
    return reporting.behaviour(ctx.db, ctx.org, c.id, reporting_date(ctx, as_at))
