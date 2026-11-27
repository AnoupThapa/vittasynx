"""Deterministic receivables calculations (rule version R1-2026-11-27).

Specification: docs/03-business-rules/financial-calculations.md. These functions are pure:
they take plain values and return plain values, so they are exhaustively unit-testable and
reproducible from stored inputs.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from app.domain.money import RULE_VERSION, ZERO, round_metric

INCLUDED_STATUSES = frozenset({"open", "disputed"})  # 'paid' is derived, never stored
EXCLUDED_STATUSES = frozenset({"cancelled", "void"})

BUCKETS = ("current", "1_30", "31_60", "61_90", "91_plus")
BUCKET_LABELS = {
    "current": "Current (not yet due)",
    "1_30": "1–30 days overdue",
    "31_60": "31–60 days overdue",
    "61_90": "61–90 days overdue",
    "91_plus": "More than 90 days overdue",
}

MIN_BEHAVIOUR_INVOICES = 6
MIN_BEHAVIOUR_SPAN_DAYS = 90
DEFAULT_OBSERVATION_DAYS = 365


@dataclass(frozen=True)
class AllocationFact:
    amount: Decimal
    effective_date: date
    kind: str = "payment"  # payment | credit


@dataclass(frozen=True)
class InvoiceFact:
    id: object
    customer_id: object
    issue_date: date
    due_date: date
    amount: Decimal
    status: str
    allocations: tuple[AllocationFact, ...] = field(default_factory=tuple)


def balance_as_at(invoice: InvoiceFact, as_at: date) -> Decimal:
    """B(R) = I − Σ confirmed allocations with effective date ≤ R. Exact; never clamped."""
    applied = sum((a.amount for a in invoice.allocations if a.effective_date <= as_at), ZERO)
    return invoice.amount - applied


def payments_as_at(invoice: InvoiceFact, as_at: date) -> Decimal:
    return sum((a.amount for a in invoice.allocations if a.kind == "payment" and a.effective_date <= as_at), ZERO)


def credits_as_at(invoice: InvoiceFact, as_at: date) -> Decimal:
    return sum((a.amount for a in invoice.allocations if a.kind == "credit" and a.effective_date <= as_at), ZERO)


def in_receivables(invoice: InvoiceFact, as_at: date) -> bool:
    return invoice.status in INCLUDED_STATUSES and invoice.issue_date <= as_at


def days_past_due(due_date: date, as_at: date) -> int:
    return (as_at - due_date).days


def bucket_for(days: int) -> str:
    if days <= 0:
        return "current"
    if days <= 30:
        return "1_30"
    if days <= 60:
        return "31_60"
    if days <= 90:
        return "61_90"
    return "91_plus"


def display_status(invoice: InvoiceFact, as_at: date) -> str:
    """'paid' and 'overdue' are derived, never stored or imported as truth (D-17)."""
    if invoice.status in EXCLUDED_STATUSES:
        return invoice.status
    b = balance_as_at(invoice, as_at)
    if b == ZERO and invoice.amount > ZERO:
        return "paid"
    if b < ZERO:
        return "exception"
    if invoice.status == "disputed":
        return "disputed"
    if b > ZERO and invoice.due_date < as_at:
        return "overdue"
    return "open"


@dataclass
class AgeingResult:
    as_at: date
    totals: dict[str, Decimal]
    counts: dict[str, int]
    total_outstanding: Decimal
    overdue_total: Decimal
    overdue_count: int
    exceptions: list[object]  # invoice ids with negative balance
    reconciles: bool
    rule_version: str = RULE_VERSION


def ageing(invoices: Iterable[InvoiceFact], as_at: date) -> AgeingResult:
    totals = {b: ZERO for b in BUCKETS}
    counts = {b: 0 for b in BUCKETS}
    exceptions: list[object] = []
    total = ZERO
    overdue_total = ZERO
    overdue_count = 0
    for inv in invoices:
        if not in_receivables(inv, as_at):
            continue
        b = balance_as_at(inv, as_at)
        if b < ZERO:
            exceptions.append(inv.id)
            continue
        if b == ZERO:
            continue
        bucket = bucket_for(days_past_due(inv.due_date, as_at))
        totals[bucket] += b
        counts[bucket] += 1
        total += b
        if bucket != "current":
            overdue_total += b
            overdue_count += 1
    reconciles = sum(totals.values(), ZERO) == total
    return AgeingResult(as_at, totals, counts, total, overdue_total, overdue_count, exceptions, reconciles)


def settlement_date(invoice: InvoiceFact, as_at: date) -> date | None:
    """Effective date of the allocation that brought the balance to zero, if settled by R."""
    if invoice.amount <= ZERO or balance_as_at(invoice, as_at) != ZERO:
        return None
    running = ZERO
    for a in sorted((a for a in invoice.allocations if a.effective_date <= as_at), key=lambda a: a.effective_date):
        running += a.amount
        if running >= invoice.amount:
            return a.effective_date
    return None  # unreachable when the balance is zero


@dataclass
class BehaviourResult:
    as_at: date
    observation_start: date
    observation_end: date
    invoices_analysed: int
    sufficient: bool
    reason: str | None
    average_days_to_payment: Decimal | None
    average_days_late: Decimal | None
    on_time_percentage: Decimal | None
    payment_frequency_per_month: Decimal | None
    minimum_invoices: int = MIN_BEHAVIOUR_INVOICES
    minimum_span_days: int = MIN_BEHAVIOUR_SPAN_DAYS
    rule_version: str = RULE_VERSION
    limitation: str = (
        "Based only on invoices fully settled within the observation period. Open invoices are excluded, "
        "so customers who have not yet paid are under-represented. Observed history, not a prediction."
    )


def customer_behaviour(
    invoices: Sequence[InvoiceFact],
    payment_dates: Sequence[date],
    as_at: date,
    observation_days: int = DEFAULT_OBSERVATION_DAYS,
) -> BehaviourResult:
    start = as_at - timedelta(days=observation_days - 1)
    qualifying: list[tuple[InvoiceFact, date]] = []
    for inv in invoices:
        if inv.status != "open":  # disputed, cancelled and void are excluded
            continue
        sd = settlement_date(inv, as_at)
        if sd is None or sd < start:
            continue
        qualifying.append((inv, sd))

    n = len(qualifying)
    span = (max(sd for _, sd in qualifying) - min(sd for _, sd in qualifying)).days if qualifying else 0
    if n < MIN_BEHAVIOUR_INVOICES or span < MIN_BEHAVIOUR_SPAN_DAYS:
        reason = (
            f"Insufficient data: {n} fully paid invoice(s) spanning {span} day(s); at least "
            f"{MIN_BEHAVIOUR_INVOICES} invoices spanning {MIN_BEHAVIOUR_SPAN_DAYS} days are required."
        )
        return BehaviourResult(as_at, start, as_at, n, False, reason, None, None, None, None)

    days_to_pay = [Decimal((sd - inv.issue_date).days) for inv, sd in qualifying]
    days_late = [Decimal(max(0, (sd - inv.due_date).days)) for inv, sd in qualifying]
    on_time = sum(1 for inv, sd in qualifying if sd <= inv.due_date)
    distinct_payment_days = {d for d in payment_dates if start <= d <= as_at}
    months = Decimal(observation_days) / (Decimal(365) / Decimal(12))
    return BehaviourResult(
        as_at=as_at,
        observation_start=start,
        observation_end=as_at,
        invoices_analysed=n,
        sufficient=True,
        reason=None,
        average_days_to_payment=round_metric(sum(days_to_pay, ZERO) / n),
        average_days_late=round_metric(sum(days_late, ZERO) / n),
        on_time_percentage=round_metric(Decimal(on_time) * 100 / n),
        payment_frequency_per_month=round_metric(Decimal(len(distinct_payment_days)) / months),
    )


def remaining(amount: Decimal, allocated: Iterable[Decimal]) -> Decimal:
    return amount - sum(allocated, ZERO)
