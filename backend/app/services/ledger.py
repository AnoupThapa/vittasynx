"""Invoices, credit notes, payments and allocations: the controlled write operations.

Rules: docs/03-business-rules/rules.md §2, §3, §8. Allocations lock both the source and the invoice
row (SELECT ... FOR UPDATE) so concurrent requests cannot over-allocate.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleViolation, Conflict, NotFound, ValidationFailed
from app.domain.money import ZERO, MoneyError, fmt, parse_amount
from app.domain.normalise import normalise_number
from app.models import Allocation, CreditNote, Invoice, InvoiceVersion, Organisation, Payment
from app.services import audit

INVOICE_STATUS_TRANSITIONS = {
    "open": {"disputed", "cancelled", "void"},
    "disputed": {"open", "cancelled", "void"},
    "cancelled": set(),
    "void": set(),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def payment_dedupe_key(payment_date: date, amount: Decimal, reference: str | None, description: str | None) -> str:
    basis = f"{payment_date.isoformat()}|{amount}|{(reference or '').strip().upper()}|{(description or '').strip().upper()}"
    return hashlib.sha256(basis.encode()).hexdigest()


def invoice_values(inv: Invoice) -> dict:
    c = inv.currency
    return {
        "invoice_number": inv.invoice_number,
        "customer_id": str(inv.customer_id),
        "issue_date": inv.issue_date.isoformat(),
        "due_date": inv.due_date.isoformat(),
        "currency": c,
        "total_amount": fmt(inv.total_amount, c),
        "tax_amount": fmt(inv.tax_amount, c),
        "net_amount": fmt(inv.net_amount, c),
        "total_is_derived": inv.total_is_derived,
        "source_amount_due": fmt(inv.source_amount_due, c),
        "reference": inv.reference,
        "status": inv.status,
    }


def get_invoice(db: Session, org_id: uuid.UUID, invoice_id: uuid.UUID, *, lock: bool = False) -> Invoice:
    q = select(Invoice).where(Invoice.id == invoice_id, Invoice.organisation_id == org_id)
    if lock:
        q = q.with_for_update()
    inv = db.scalar(q)
    if inv is None:
        raise NotFound("Invoice not found")
    return inv


def confirmed_total(db: Session, org_id: uuid.UUID, *, invoice_id=None, payment_id=None, credit_note_id=None) -> Decimal:
    q = select(func.coalesce(func.sum(Allocation.amount), 0)).where(
        Allocation.organisation_id == org_id, Allocation.status == "confirmed")
    if invoice_id:
        q = q.where(Allocation.invoice_id == invoice_id)
    if payment_id:
        q = q.where(Allocation.payment_id == payment_id)
    if credit_note_id:
        q = q.where(Allocation.credit_note_id == credit_note_id)
    return Decimal(db.scalar(q))


def record_version(db: Session, inv: Invoice, reason: str, actor_id: uuid.UUID | None, source_row_id=None) -> None:
    db.add(InvoiceVersion(organisation_id=inv.organisation_id, invoice_id=inv.id, version=inv.version,
                          values=invoice_values(inv), change_reason=reason, source_row_id=source_row_id,
                          created_by=actor_id))


def change_invoice_status(db: Session, org: Organisation, actor_id: uuid.UUID, invoice_id: uuid.UUID,
                          status: str, reason: str) -> Invoice:
    if not reason or not reason.strip():
        raise ValidationFailed("A reason is required")
    inv = get_invoice(db, org.id, invoice_id, lock=True)
    if status not in INVOICE_STATUS_TRANSITIONS.get(inv.status, set()):
        raise BusinessRuleViolation(f"Cannot change status from {inv.status} to {status}", code="invalid_transition")
    if status in ("cancelled", "void") and confirmed_total(db, org.id, invoice_id=inv.id) > ZERO:
        raise BusinessRuleViolation("Reverse confirmed allocations before cancelling or voiding this invoice",
                                    code="has_allocations")
    before = inv.status
    inv.status = status
    inv.status_reason = reason.strip()
    inv.version += 1
    record_version(db, inv, f"status {before} → {status}: {reason.strip()}", actor_id)
    audit.record(db, action="invoice.status_changed", actor_user_id=actor_id, organisation_id=org.id,
                 entity_type="invoice", entity_id=inv.id, before={"status": before},
                 after={"status": status, "reason": reason.strip()})
    return inv


def create_credit_note(db: Session, org: Organisation, actor_id: uuid.UUID, *, customer_id: uuid.UUID, number: str,
                       credit_date: date, amount: str, reason: str | None, applies_to: str | None,
                       source_row_id=None, source: str = "api") -> CreditNote:
    try:
        value = parse_amount(amount, org.currency)
    except MoneyError as exc:
        raise ValidationFailed(str(exc), code="invalid_amount") from exc
    if value <= ZERO:
        raise ValidationFailed("Credit note amount must be greater than zero", code="invalid_amount")
    if not number or not number.strip():
        raise ValidationFailed("Credit note number is required")
    norm = normalise_number(number)
    if db.scalar(select(CreditNote).where(CreditNote.organisation_id == org.id, CreditNote.customer_id == customer_id,
                                          CreditNote.normalised_number == norm)):
        raise Conflict("A credit note with this number already exists for this customer", code="duplicate_credit_note")
    cn = CreditNote(organisation_id=org.id, customer_id=customer_id, credit_note_number=number.strip(),
                    normalised_number=norm, credit_date=credit_date, currency=org.currency, amount=value,
                    reason=(reason or None), applies_to_invoice_number=(applies_to or None),
                    source_row_id=source_row_id, created_by=actor_id)
    db.add(cn)
    db.flush()
    audit.record(db, action="credit_note.created", actor_user_id=actor_id, organisation_id=org.id,
                 entity_type="credit_note", entity_id=cn.id,
                 after={"number": cn.credit_note_number, "amount": fmt(value, org.currency), "reason": reason},
                 source=source)
    return cn


def create_payment(db: Session, org: Organisation, actor_id: uuid.UUID, *, customer_id: uuid.UUID | None,
                   payment_date: date, amount: str | Decimal, reference: str | None, description: str | None,
                   method: str | None, source: str, source_row_id=None, check_duplicate: bool = True) -> Payment:
    try:
        value = amount if isinstance(amount, Decimal) else parse_amount(amount, org.currency)
    except MoneyError as exc:
        raise ValidationFailed(str(exc), code="invalid_amount") from exc
    if value <= ZERO:
        raise ValidationFailed("Payment amount must be greater than zero", code="invalid_amount")
    key = payment_dedupe_key(payment_date, value, reference, description)
    if check_duplicate and db.scalar(select(Payment).where(Payment.organisation_id == org.id, Payment.dedupe_key == key)):
        raise Conflict("A payment with the same date, amount and reference already exists", code="duplicate_payment")
    p = Payment(organisation_id=org.id, customer_id=customer_id, payment_date=payment_date, currency=org.currency,
                amount=value, reference=(reference or None), description=(description or None), method=(method or None),
                source=source, dedupe_key=key, source_row_id=source_row_id, created_by=actor_id)
    db.add(p)
    db.flush()
    audit.record(db, action="payment.recorded", actor_user_id=actor_id, organisation_id=org.id, entity_type="payment",
                 entity_id=p.id, after={"amount": fmt(value, org.currency), "date": payment_date.isoformat(),
                                        "source": source}, source=source)
    return p


def get_payment(db: Session, org_id: uuid.UUID, payment_id: uuid.UUID, *, lock: bool = False) -> Payment:
    q = select(Payment).where(Payment.id == payment_id, Payment.organisation_id == org_id)
    if lock:
        q = q.with_for_update()
    p = db.scalar(q)
    if p is None:
        raise NotFound("Payment not found")
    return p


def get_credit_note(db: Session, org_id: uuid.UUID, credit_note_id: uuid.UUID, *, lock: bool = False) -> CreditNote:
    q = select(CreditNote).where(CreditNote.id == credit_note_id, CreditNote.organisation_id == org_id)
    if lock:
        q = q.with_for_update()
    c = db.scalar(q)
    if c is None:
        raise NotFound("Credit note not found")
    return c


def assign_payment_customer(db: Session, org: Organisation, actor_id: uuid.UUID, payment_id: uuid.UUID,
                            customer_id: uuid.UUID) -> Payment:
    p = get_payment(db, org.id, payment_id, lock=True)
    if p.customer_id == customer_id:
        return p
    if confirmed_total(db, org.id, payment_id=p.id) > ZERO:
        raise BusinessRuleViolation("Reverse this payment's allocations before changing its customer",
                                    code="has_allocations")
    before = str(p.customer_id) if p.customer_id else None
    p.customer_id = customer_id
    audit.record(db, action="payment.customer_assigned", actor_user_id=actor_id, organisation_id=org.id,
                 entity_type="payment", entity_id=p.id, before={"customer_id": before},
                 after={"customer_id": str(customer_id)})
    return p


def allocate(db: Session, org: Organisation, actor_id: uuid.UUID, *, invoice_id: uuid.UUID, amount: str,
             payment_id: uuid.UUID | None = None, credit_note_id: uuid.UUID | None = None) -> Allocation:
    if bool(payment_id) == bool(credit_note_id):
        raise ValidationFailed("Provide exactly one of payment_id or credit_note_id")
    try:
        value = parse_amount(amount, org.currency)
    except MoneyError as exc:
        raise ValidationFailed(str(exc), code="invalid_amount") from exc
    if value <= ZERO:
        raise ValidationFailed("Allocation amount must be greater than zero", code="invalid_amount")

    # Lock order: source first, then invoice (consistent order avoids deadlocks).
    if payment_id:
        source = get_payment(db, org.id, payment_id, lock=True)
        source_total, effective = source.amount, source.payment_date
        source_allocated = confirmed_total(db, org.id, payment_id=source.id)
    else:
        source = get_credit_note(db, org.id, credit_note_id, lock=True)  # type: ignore[arg-type]
        source_total, effective = source.amount, source.credit_date
        source_allocated = confirmed_total(db, org.id, credit_note_id=source.id)
    inv = get_invoice(db, org.id, invoice_id, lock=True)

    if source.customer_id is None:
        raise BusinessRuleViolation("Assign this receipt to a customer before allocating it", code="unassigned_receipt")
    if source.customer_id != inv.customer_id:
        raise BusinessRuleViolation("The payment/credit and the invoice belong to different customers",
                                    code="customer_mismatch")
    if source.currency != inv.currency:
        raise BusinessRuleViolation("Currency mismatch", code="currency_mismatch")
    if inv.status in ("cancelled", "void"):
        raise BusinessRuleViolation(f"Cannot allocate to a {inv.status} invoice", code="invoice_closed")

    source_remaining = source_total - source_allocated
    invoice_remaining = inv.total_amount - confirmed_total(db, org.id, invoice_id=inv.id)
    if value > source_remaining:
        raise BusinessRuleViolation(
            f"Amount exceeds the unallocated {'payment' if payment_id else 'credit'} amount of "
            f"{fmt(source_remaining, org.currency)}", code="exceeds_source",
            details={"available": fmt(source_remaining, org.currency)})
    if value > invoice_remaining:
        raise BusinessRuleViolation(
            f"Amount exceeds the invoice balance of {fmt(invoice_remaining, org.currency)}", code="exceeds_invoice",
            details={"invoice_balance": fmt(invoice_remaining, org.currency)})

    a = Allocation(organisation_id=org.id, invoice_id=inv.id, payment_id=payment_id, credit_note_id=credit_note_id,
                   amount=value, effective_date=effective, created_by=actor_id)
    db.add(a)
    db.flush()
    audit.record(db, action="allocation.confirmed", actor_user_id=actor_id, organisation_id=org.id,
                 entity_type="allocation", entity_id=a.id,
                 after={"invoice_id": str(inv.id), "payment_id": str(payment_id) if payment_id else None,
                        "credit_note_id": str(credit_note_id) if credit_note_id else None,
                        "amount": fmt(value, org.currency), "effective_date": effective.isoformat()})
    return a


def reverse_allocation(db: Session, org: Organisation, actor_id: uuid.UUID, allocation_id: uuid.UUID, reason: str) -> Allocation:
    if not reason or not reason.strip():
        raise ValidationFailed("A reason is required to reverse an allocation")
    a = db.scalar(select(Allocation).where(Allocation.id == allocation_id, Allocation.organisation_id == org.id)
                  .with_for_update())
    if a is None:
        raise NotFound("Allocation not found")
    if a.status == "reversed":
        raise Conflict("This allocation has already been reversed", code="already_reversed")
    a.status = "reversed"
    a.reversed_by = actor_id
    a.reversed_at = _now()
    a.reversal_reason = reason.strip()
    audit.record(db, action="allocation.reversed", actor_user_id=actor_id, organisation_id=org.id,
                 entity_type="allocation", entity_id=a.id, before={"status": "confirmed"},
                 after={"status": "reversed", "reason": reason.strip(), "amount": fmt(a.amount, org.currency)})
    return a
