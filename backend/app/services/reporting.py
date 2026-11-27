"""Receivables reporting. Every figure states its reporting date, rule version and definition."""
from __future__ import annotations

import csv
import io
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import receivables as calc
from app.domain.money import RULE_VERSION, ZERO, fmt
from app.models import Customer, Organisation, Payment
from app.services.receivables import invoice_facts, unapplied_credits, unapplied_payments

DEFINITIONS = {
    "total_outstanding": "Sum of positive invoice balances as at the reporting date. Balance = invoice total − "
                         "confirmed payment and credit allocations dated on or before the reporting date. "
                         "Cancelled and void invoices are excluded.",
    "overdue_total": "Outstanding balance of invoices whose due date is before the reporting date.",
    "current_total": "Outstanding balance of invoices not yet due at the reporting date.",
    "ageing": "Days past due = reporting date − due date. Buckets: current (≤0), 1–30, 31–60, 61–90, 91+.",
    "unapplied_payments": "Payments dated on or before the reporting date not yet allocated to invoices. "
                          "Shown separately; not deducted from outstanding receivables.",
    "unapplied_credits": "Credit notes dated on or before the reporting date not yet allocated to invoices.",
    "exceptions": "Invoices with a negative balance. Excluded from ageing and require review.",
}


def _generated() -> str:
    return datetime.now(timezone.utc).isoformat()


def _customers(db: Session, org_id: uuid.UUID) -> dict[uuid.UUID, Customer]:
    return {c.id: c for c in db.scalars(select(Customer).where(Customer.organisation_id == org_id))}


def dashboard(db: Session, org: Organisation, as_at: date) -> dict:
    cur = org.currency
    facts, invoices = invoice_facts(db, org.id)
    result = calc.ageing(facts.values(), as_at)
    customers = _customers(db, org.id)

    by_customer: dict[uuid.UUID, dict[str, Decimal]] = defaultdict(lambda: {"outstanding": ZERO, "overdue": ZERO})
    oldest = []
    for f in facts.values():
        if not calc.in_receivables(f, as_at):
            continue
        b = calc.balance_as_at(f, as_at)
        if b <= ZERO:
            continue
        dpd = calc.days_past_due(f.due_date, as_at)
        by_customer[f.customer_id]["outstanding"] += b
        if dpd > 0:
            by_customer[f.customer_id]["overdue"] += b
        oldest.append((f, b, dpd))
    oldest.sort(key=lambda t: (t[0].due_date, invoices[t[0].id].invoice_number))

    largest_overdue = sorted(((cid, v) for cid, v in by_customer.items() if v["overdue"] > ZERO),
                             key=lambda t: (-t[1]["overdue"], customers[t[0]].name))[:10]
    up = unapplied_payments(db, org.id, as_at)
    uc = unapplied_credits(db, org.id, as_at)
    recent = list(db.scalars(select(Payment).where(Payment.organisation_id == org.id, Payment.payment_date <= as_at)
                             .order_by(Payment.payment_date.desc(), Payment.created_at.desc()).limit(10)))
    unapplied_total = sum((r for _, r in up), ZERO)
    credits_total = sum((r for _, r in uc), ZERO)
    return {
        "reporting_date": as_at.isoformat(),
        "generated_at": _generated(),
        "currency": cur,
        "rule_version": RULE_VERSION,
        "totals": {
            "total_outstanding": fmt(result.total_outstanding, cur),
            "overdue_total": fmt(result.overdue_total, cur),
            "current_total": fmt(result.totals["current"], cur),
            "overdue_count": result.overdue_count,
            "open_invoice_count": sum(result.counts.values()),
            "unapplied_payments": fmt(unapplied_total, cur),
            "unapplied_payment_count": len(up),
            "unapplied_credits": fmt(credits_total, cur),
            "net_position": fmt(result.total_outstanding - unapplied_total - credits_total, cur),
            "exception_count": len(result.exceptions),
        },
        "ageing": [{"bucket": b, "label": calc.BUCKET_LABELS[b], "total": fmt(result.totals[b], cur),
                    "count": result.counts[b]} for b in calc.BUCKETS],
        "reconciles": result.reconciles,
        "largest_overdue_customers": [
            {"customer_id": str(cid), "customer_name": customers[cid].name, "overdue": fmt(v["overdue"], cur),
             "outstanding": fmt(v["outstanding"], cur)} for cid, v in largest_overdue],
        "oldest_outstanding_invoices": [
            {"invoice_id": str(f.id), "invoice_number": invoices[f.id].invoice_number,
             "customer_id": str(f.customer_id), "customer_name": customers[f.customer_id].name,
             "due_date": f.due_date.isoformat(), "days_past_due": max(0, dpd), "balance": fmt(b, cur)}
            for f, b, dpd in oldest[:10]],
        "recent_payments": [
            {"payment_id": str(p.id), "payment_date": p.payment_date.isoformat(), "amount": fmt(p.amount, cur),
             "customer_name": customers[p.customer_id].name if p.customer_id else None, "reference": p.reference}
            for p in recent],
        "unapplied_payments": [
            {"payment_id": str(p.id), "payment_date": p.payment_date.isoformat(), "unapplied": fmt(r, cur),
             "customer_name": customers[p.customer_id].name if p.customer_id else None,
             "reference": p.reference or p.description} for p, r in up[:10]],
        "definitions": {**DEFINITIONS, "net_position": "Total outstanding − unapplied payments − unapplied credits. "
                                                       "Labelled net; not the same as outstanding receivables."},
    }


def invoice_rows(db: Session, org: Organisation, as_at: date, *, customer_id=None, status=None, search=None,
                 issue_from=None, issue_to=None, due_from=None, due_to=None) -> list[dict]:
    cur = org.currency
    facts, invoices = invoice_facts(db, org.id, customer_id=customer_id)
    customers = _customers(db, org.id)
    out = []
    for f in facts.values():
        inv = invoices[f.id]
        if inv.issue_date > as_at:
            continue  # not yet issued at the reporting date
        b = calc.balance_as_at(f, as_at)
        dstatus = calc.display_status(f, as_at)
        if status and dstatus != status and not (status == "outstanding" and b > ZERO and dstatus not in ("cancelled", "void")):
            continue
        if search and search.strip().upper() not in inv.normalised_number and \
                search.strip().casefold() not in customers[f.customer_id].normalised_name:
            continue
        if issue_from and inv.issue_date < issue_from or issue_to and inv.issue_date > issue_to:
            continue
        if due_from and inv.due_date < due_from or due_to and inv.due_date > due_to:
            continue
        dpd = calc.days_past_due(f.due_date, as_at)
        included = calc.in_receivables(f, as_at)
        out.append({
            "id": str(inv.id),
            "invoice_number": inv.invoice_number,
            "customer_id": str(inv.customer_id),
            "customer_name": customers[inv.customer_id].name,
            "issue_date": inv.issue_date.isoformat(),
            "due_date": inv.due_date.isoformat(),
            "currency": cur,
            "original_amount": fmt(inv.total_amount, cur),
            "payments_allocated": fmt(calc.payments_as_at(f, as_at), cur),
            "credits_allocated": fmt(calc.credits_as_at(f, as_at), cur),
            "balance": fmt(b, cur),
            "status": dstatus,
            "days_past_due": max(0, dpd) if included and b > ZERO else 0,
            "ageing_bucket": calc.bucket_for(dpd) if included and b > ZERO else None,
            "source_amount_due": fmt(inv.source_amount_due, cur),
            "source_differs": inv.source_amount_due is not None and inv.source_amount_due != b,
        })
    out.sort(key=lambda r: (r["due_date"], r["invoice_number"]))
    return out


def customer_balances(db: Session, org: Organisation, as_at: date) -> list[dict]:
    cur = org.currency
    facts, _ = invoice_facts(db, org.id)
    customers = _customers(db, org.id)
    agg: dict[uuid.UUID, dict] = {cid: {b: ZERO for b in calc.BUCKETS} for cid in customers}
    for f in facts.values():
        if not calc.in_receivables(f, as_at):
            continue
        b = calc.balance_as_at(f, as_at)
        if b > ZERO:
            agg[f.customer_id][calc.bucket_for(calc.days_past_due(f.due_date, as_at))] += b
    unapplied = defaultdict(lambda: ZERO)
    for p, r in unapplied_payments(db, org.id, as_at):
        if p.customer_id:
            unapplied[p.customer_id] += r
    credits = defaultdict(lambda: ZERO)
    for c, r in unapplied_credits(db, org.id, as_at):
        credits[c.customer_id] += r
    out = []
    for cid, buckets in agg.items():
        total = sum(buckets.values(), ZERO)
        c = customers[cid]
        out.append({"customer_id": str(cid), "customer_code": c.code, "customer_name": c.name, "status": c.status,
                    **{b: fmt(v, cur) for b, v in buckets.items()},
                    "total_outstanding": fmt(total, cur),
                    "overdue": fmt(total - buckets["current"], cur),
                    "unapplied_payments": fmt(unapplied[cid], cur), "unapplied_credits": fmt(credits[cid], cur)})
    out.sort(key=lambda r: r["customer_name"].casefold())
    return out


def behaviour(db: Session, org: Organisation, customer_id: uuid.UUID, as_at: date) -> dict:
    facts, _ = invoice_facts(db, org.id, customer_id=customer_id)
    payment_dates = list(db.scalars(select(Payment.payment_date).where(Payment.organisation_id == org.id,
                                                                       Payment.customer_id == customer_id)))
    r = calc.customer_behaviour(list(facts.values()), payment_dates, as_at)

    def s(v: Decimal | None) -> str | None:
        return None if v is None else str(v)

    return {
        "reporting_date": as_at.isoformat(), "observation_start": r.observation_start.isoformat(),
        "observation_end": r.observation_end.isoformat(), "invoices_analysed": r.invoices_analysed,
        "sufficient_data": r.sufficient, "insufficient_reason": r.reason,
        "average_days_to_payment": s(r.average_days_to_payment), "average_days_late": s(r.average_days_late),
        "on_time_percentage": s(r.on_time_percentage),
        "payment_frequency_per_month": s(r.payment_frequency_per_month),
        "minimum_invoices": r.minimum_invoices, "minimum_span_days": r.minimum_span_days,
        "rule_version": r.rule_version, "limitation": r.limitation, "kind": "observed_history",
    }


# ---------- CSV exports ----------

_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def _safe(value: object) -> str:
    """Neutralise spreadsheet formula injection in exported text (SR-02). Numbers are left intact."""
    if value is None:
        return ""
    text = str(value)
    if text and text[0] in _DANGEROUS:
        try:
            Decimal(text)
            return text  # a genuine negative number
        except Exception:  # noqa: BLE001
            return "'" + text
    return text


def to_csv(rows: list[dict], columns: list[tuple[str, str]], preamble: list[tuple[str, str]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    for k, v in preamble:
        w.writerow([_safe(k), _safe(v)])
    w.writerow([])
    w.writerow([label for _, label in columns])
    for r in rows:
        w.writerow([_safe(r.get(key)) for key, _ in columns])
    return buf.getvalue()


def preamble(org: Organisation, report: str, as_at: date) -> list[tuple[str, str]]:
    return [("Report", report), ("Organisation", org.name), ("Reporting date", as_at.isoformat()),
            ("Currency", org.currency), ("Rule version", RULE_VERSION), ("Generated at (UTC)", _generated())]
