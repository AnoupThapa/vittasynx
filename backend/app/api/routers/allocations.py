import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import OrgContext, require
from app.api.routers.invoices import allocation_out
from app.core.permissions import Perm
from app.services import ledger

router = APIRouter(prefix="/orgs/{org_id}/allocations", tags=["allocations"])


class AllocationIn(BaseModel):
    invoice_id: uuid.UUID
    amount: str = Field(min_length=1, max_length=30)
    payment_id: uuid.UUID | None = None
    credit_note_id: uuid.UUID | None = None


class ReverseIn(BaseModel):
    reason: str = Field(min_length=1, max_length=300)


@router.post("", status_code=201)
def confirm_allocation(body: AllocationIn, ctx: OrgContext = Depends(require(Perm.CONFIRM_ALLOCATION))) -> dict:
    a = ledger.allocate(ctx.db, ctx.org, ctx.user.id, invoice_id=body.invoice_id, amount=body.amount,
                        payment_id=body.payment_id, credit_note_id=body.credit_note_id)
    ctx.db.commit()
    return allocation_out(a, ctx.org.currency)


@router.post("/{allocation_id}/reverse")
def reverse(allocation_id: uuid.UUID, body: ReverseIn, ctx: OrgContext = Depends(require(Perm.REVERSE_ALLOCATION))) -> dict:
    a = ledger.reverse_allocation(ctx.db, ctx.org, ctx.user.id, allocation_id, body.reason)
    ctx.db.commit()
    return allocation_out(a, ctx.org.currency)
