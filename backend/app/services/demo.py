"""Demo organisation with synthetic sample data (rules.md §8.13).

Every record is created through the normal services, so it passes the same validation, gets
versions and audit events, and obeys the allocation rules. Names are fictional and marked "(Demo)".
The data set is deterministic (fixed seed) and dated relative to the creation day.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Organisation, User
from app.services import audit, customers as customer_svc, ledger
from app.services.organisations import create_organisation
from app.services.receivables import org_today

DEMO_NAME = "Demo — Sample Wholesale (synthetic data)"

# name, code, behaviour profile, number of invoices
CUSTOMERS = [
    ("Harbourside Aged Care (Demo)", "DEMO-01", "on_time", 9),
    ("Westgate Medical Centre (Demo)", "DEMO-02", "on_time", 8),
    ("Northside Dental Group (Demo)", "DEMO-03", "slightly_late", 7),
    ("Parkview Hotel (Demo)", "DEMO-04", "late", 6),
    ("Riverbend School (Demo)", "DEMO-05", "slightly_late", 5),
    ("Summit Cleaning Services (Demo)", "DEMO-06", "very_late", 4),
    ("Lakeside Cafe Group (Demo)", "DEMO-07", "partial", 4),
    ("Greenfield Veterinary (Demo)", "DEMO-08", "new", 2),
]

LATENESS = {  # days after the due date the customer pays (negative = early)
    "on_time": (-6, 0),
    "slightly_late": (3, 14),
    "late": (15, 40),
    "very_late": (45, 95),
    "partial": (5, 25),
    "new": (0, 0),
}


def existing_demo(db: Session, user: User) -> Organisation | None:
    return db.scalar(select(Organisation).where(Organisation.demo_owner_id == user.id))


def create_demo_organisation(db: Session, user: User, currency: str = "AUD", tz: str = "Australia/Sydney") -> Organisation:
    org = existing_demo(db, user)
    if org:
        return org
    org = create_organisation(db, user, DEMO_NAME, currency, tz)
    org.is_demo = True
    org.demo_owner_id = user.id
    db.flush()
    _populate(db, org, user)
    audit.record(db, action="organisation.demo_populated", actor_user_id=user.id, organisation_id=org.id,
                 entity_type="organisation", entity_id=org.id, note="Synthetic sample data (rules.md §8.13)")
    return org


def _amount(rng: random.Random) -> Decimal:
    return Decimal(rng.randint(15_000, 450_000)) / 100  # 150.00 – 4,500.00, exact cents


def _populate(db: Session, org: Organisation, user: User) -> None:
    rng = random.Random(20261127)
    today = org_today(org)
    start = today - timedelta(days=270)
    actor = user.id
    open_invoices = []

    for name, code, profile, count in CUSTOMERS:
        cust = customer_svc.create(db, org.id, actor, name, code, source="demo")
        spacing = 270 // count
        for k in range(count):
            issue = start + timedelta(days=k * spacing + rng.randint(0, max(spacing - 1, 0)))
            if profile == "new":
                issue = today - timedelta(days=20 + 15 * k)
            due = issue + timedelta(days=30)
            amount = _amount(rng)
            number = f"DEMO-{code[-2:]}{k + 1:03d}"
            inv = ledger.create_invoice_manual(
                db, org, actor, customer_id=cust.id, invoice_number=number, issue_date=issue, due_date=due,
                total_amount=str(amount), net_amount=None, tax_amount=None, reference=f"PO {rng.randint(1000, 9999)}",
                entry_method="demo")
            lo, hi = LATENESS[profile]
            pay_date = due + timedelta(days=rng.randint(lo, hi))
            if profile == "very_late" and k == count - 1:
                pay_date = today + timedelta(days=1)  # still unpaid
            if pay_date > today:
                open_invoices.append(inv)
                continue
            if profile == "partial" and k % 2 == 0:
                part = (amount / 2).quantize(Decimal("0.01"))
                _pay(db, org, actor, cust.id, inv, pay_date, part, f"DEMO part payment {number}")
                open_invoices.append(inv)
            else:
                _pay(db, org, actor, cust.id, inv, pay_date, amount, f"DEMO payment {number}")

    _extras(db, org, actor, today, open_invoices)


def _pay(db, org, actor, customer_id, inv, pay_date: date, amount: Decimal, reference: str) -> None:
    p = ledger.create_payment(db, org, actor, customer_id=customer_id, payment_date=pay_date, amount=amount,
                              reference=reference, description=None, method="EFT (demo)", source="manual")
    ledger.allocate(db, org, actor, invoice_id=inv.id, amount=str(amount), payment_id=p.id)


def _extras(db, org, actor, today: date, open_invoices: list) -> None:
    by_customer: dict = {}
    for inv in open_invoices:
        by_customer.setdefault(inv.customer_id, []).append(inv)
    unpaid_full = [i for i in open_invoices if ledger.confirmed_total(db, org.id, invoice_id=i.id) == 0]

    # A credit note applied to an open invoice.
    target = unpaid_full[0]
    cn = ledger.create_credit_note(db, org, actor, customer_id=target.customer_id, number="DEMO-CN001",
                                   credit_date=today - timedelta(days=10), amount="120.00",
                                   reason="Damaged carton (demo)", applies_to=target.invoice_number, source="demo")
    ledger.allocate(db, org, actor, invoice_id=target.id, amount="120.00", credit_note_id=cn.id)

    # A disputed invoice and a cancelled invoice.
    ledger.change_invoice_status(db, org, actor, unpaid_full[1].id, "disputed", "Customer queried pricing (demo)")
    cancelled_cust = unpaid_full[2].customer_id
    cancelled = ledger.create_invoice_manual(
        db, org, actor, customer_id=cancelled_cust, invoice_number="DEMO-CANCEL01", issue_date=today - timedelta(days=40),
        due_date=today - timedelta(days=10), total_amount="310.00", net_amount=None, tax_amount=None,
        reference="Raised in error (demo)", entry_method="demo")
    ledger.change_invoice_status(db, org, actor, cancelled.id, "cancelled", "Raised in error (demo)")

    # An unapplied payment (customer paid but nobody allocated it yet).
    ledger.create_payment(db, org, actor, customer_id=unpaid_full[3].customer_id, payment_date=today - timedelta(days=3),
                          amount=Decimal("250.00"), reference="DEMO on-account payment", description=None,
                          method="EFT (demo)", source="manual")

    # An unassigned bank receipt whose description names an open invoice, so a suggestion appears.
    hint = unpaid_full[-1]
    balance = hint.total_amount - ledger.confirmed_total(db, org.id, invoice_id=hint.id)
    ledger.create_payment(db, org, actor, customer_id=None, payment_date=today - timedelta(days=1), amount=balance,
                          reference=None, description=f"DIRECT CREDIT DEMO {hint.invoice_number}", method="bank",
                          source="bank")
