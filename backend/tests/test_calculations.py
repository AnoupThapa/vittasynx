"""Pure calculation tests with manually verified expected results (rule version R1-2026-11-27)."""
from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from app.domain import receivables as calc
from app.domain.money import MoneyError, fmt, parse_amount, round_money
from app.domain.normalise import DateParseError, normalise_name, normalise_number, parse_date

A = calc.AllocationFact


def inv(amount="1100.00", issue=date(2026, 1, 5), due=date(2026, 2, 4), status="open", allocs=(), id_="i1", cust="c1"):
    return calc.InvoiceFact(id_, cust, issue, due, D(amount), status, tuple(allocs))


# ---------- money ----------

@pytest.mark.parametrize("raw,expected", [
    ("1100", "1100.00"), ("1,100.00", "1100.00"), ("$1,234,567.89", "1234567.89"), ("  12.5 ", "12.50"),
    ("(50.00)", "-50.00"), ("-0.01", "-0.01"), ("1100.000", "1100.00"), ("AUD 99.99", "99.99"), (D("3.10"), "3.10"),
])
def test_parse_amount_accepts(raw, expected):
    assert fmt(parse_amount(raw, "AUD", allow_negative=True), "AUD") == expected


@pytest.mark.parametrize("raw", ["1100.005", "abc", "", "1.100,00", "1,10", "NaN", "Infinity", "1e20"])
def test_parse_amount_rejects(raw):
    with pytest.raises(MoneyError):
        parse_amount(raw, "AUD")


def test_parse_amount_rejects_float_and_negative():
    with pytest.raises(MoneyError):
        parse_amount(0.1, "AUD")
    with pytest.raises(MoneyError):
        parse_amount("-5.00", "AUD")


@pytest.mark.parametrize("value,expected", [("0.005", "0.01"), ("0.004", "0.00"), ("2.675", "2.68"), ("-0.005", "-0.01")])
def test_round_half_up_boundaries(value, expected):
    assert str(round_money(D(value), "AUD")) == expected


def test_decimal_sum_has_no_float_drift():
    # 0.1 + 0.2 is exactly 0.3 with Decimal, unlike binary floating point.
    assert parse_amount("0.10", "AUD") + parse_amount("0.20", "AUD") == D("0.30")


# ---------- normalisation and dates ----------

def test_normalisation():
    assert normalise_number(" inv- 1001 ") == "INV-1001"
    assert normalise_name("  ABC   Pty Ltd ") == normalise_name("abc pty ltd")
    assert normalise_name("ABC Pty. Ltd.") != normalise_name("ABC Pty Ltd")  # no fuzzy matching


@pytest.mark.parametrize("raw,fmt_,expected", [
    ("05/01/2026", "DD/MM/YYYY", date(2026, 1, 5)), ("01/05/2026", "MM/DD/YYYY", date(2026, 1, 5)),
    ("2026-01-05", "DD/MM/YYYY", date(2026, 1, 5)), ("29/02/2024", "DD/MM/YYYY", date(2024, 2, 29)),
    ("2026-01-05 00:00:00", "YYYY-MM-DD", date(2026, 1, 5)),
])
def test_parse_date(raw, fmt_, expected):
    assert parse_date(raw, fmt_) == expected


@pytest.mark.parametrize("raw", ["31/02/2026", "29/02/2025", "2026-13-01", "", "yesterday"])
def test_parse_date_rejects(raw):
    with pytest.raises(DateParseError):
        parse_date(raw, "DD/MM/YYYY")


# ---------- balance ----------

def test_worked_example_from_specification():
    i = inv(allocs=[A(D("300.00"), date(2026, 2, 10)), A(D("250.00"), date(2026, 3, 5)),
                    A(D("100.00"), date(2026, 3, 1), "credit")])
    assert calc.balance_as_at(i, date(2026, 2, 28)) == D("800.00")
    assert calc.balance_as_at(i, date(2026, 3, 31)) == D("450.00")
    assert calc.payments_as_at(i, date(2026, 3, 31)) == D("550.00")
    assert calc.credits_as_at(i, date(2026, 3, 31)) == D("100.00")


def test_zero_balance_and_paid_status():
    i = inv(allocs=[A(D("1100.00"), date(2026, 2, 1))])
    assert calc.balance_as_at(i, date(2026, 2, 1)) == D("0")
    assert calc.display_status(i, date(2026, 2, 1)) == "paid"
    assert calc.display_status(i, date(2026, 1, 31)) == "open"


def test_negative_balance_is_never_clamped():
    i = inv(amount="100.00", allocs=[A(D("150.00"), date(2026, 2, 1))])
    assert calc.balance_as_at(i, date(2026, 3, 1)) == D("-50.00")
    assert calc.display_status(i, date(2026, 3, 1)) == "exception"
    res = calc.ageing([i], date(2026, 3, 1))
    assert res.exceptions == ["i1"] and res.total_outstanding == D("0")


# ---------- ageing ----------

@pytest.mark.parametrize("days,bucket", [(-5, "current"), (0, "current"), (1, "1_30"), (30, "1_30"), (31, "31_60"),
                                         (60, "31_60"), (61, "61_90"), (90, "61_90"), (91, "91_plus"), (400, "91_plus")])
def test_bucket_boundaries(days, bucket):
    assert calc.bucket_for(days) == bucket


def test_due_today_is_current_and_not_overdue():
    i = inv(due=date(2026, 3, 31))
    r = calc.ageing([i], date(2026, 3, 31))
    assert r.counts["current"] == 1 and r.overdue_count == 0
    assert calc.display_status(i, date(2026, 3, 31)) == "open"
    assert calc.display_status(i, date(2026, 4, 1)) == "overdue"


def test_month_end_year_end_and_leap_year():
    # Due 31 Jan 2024; reporting 29 Feb 2024 (leap year) = 29 days → 1–30.
    assert calc.days_past_due(date(2024, 1, 31), date(2024, 2, 29)) == 29
    # Due 31 Dec 2025, reporting 30 Jan 2026 = 30 days (year boundary) → 1–30; 31 Jan → 31 → 31–60.
    assert calc.bucket_for(calc.days_past_due(date(2025, 12, 31), date(2026, 1, 30))) == "1_30"
    assert calc.bucket_for(calc.days_past_due(date(2025, 12, 31), date(2026, 1, 31))) == "31_60"
    # Feb 2025 (non-leap): due 28 Feb, reporting 1 Mar = 1 day.
    assert calc.days_past_due(date(2025, 2, 28), date(2025, 3, 1)) == 1


def test_ageing_totals_reconcile_and_exclusions():
    as_at = date(2026, 3, 31)
    invoices = [
        inv("100.00", due=date(2026, 4, 10), id_="a"),                       # current
        inv("200.00", due=date(2026, 3, 1), id_="b"),                        # 30 → 1–30
        inv("300.00", due=date(2026, 1, 30), id_="c"),                       # 60 → 31–60
        inv("400.00", due=date(2025, 12, 31), id_="d"),                      # 90 → 61–90
        inv("500.00", due=date(2025, 12, 30), id_="e"),                      # 91 → 91+
        inv("999.00", due=date(2026, 1, 1), status="cancelled", id_="f"),    # excluded
        inv("50.00", due=date(2026, 1, 1), status="disputed", id_="g"),      # 89 → 61–90, included, flagged
        inv("70.00", issue=date(2026, 4, 1), due=date(2026, 4, 30), id_="h"),  # issued after R → excluded
        inv("80.00", due=date(2026, 1, 1), allocs=[A(D("80.00"), date(2026, 2, 1))], id_="i"),  # paid
    ]
    r = calc.ageing(invoices, as_at)
    assert r.totals == {"current": D("100.00"), "1_30": D("200.00"), "31_60": D("300.00"), "61_90": D("450.00"),
                        "91_plus": D("500.00")}
    assert r.total_outstanding == D("1550.00")
    assert r.overdue_total == D("1450.00") and r.overdue_count == 5
    assert r.reconciles


def test_point_in_time_excludes_later_allocations():
    i = inv(allocs=[A(D("1100.00"), date(2026, 3, 15))])
    assert calc.ageing([i], date(2026, 3, 14)).total_outstanding == D("1100.00")
    assert calc.ageing([i], date(2026, 3, 15)).total_outstanding == D("0")


# ---------- behaviour ----------

def _paid_series(n, start=date(2025, 6, 1), step=20, late_by=0, terms=30):
    out = []
    for k in range(n):
        issue = start + timedelta(days=step * k)
        due = issue + timedelta(days=terms)
        paid = due + timedelta(days=late_by)
        out.append(calc.InvoiceFact(f"p{k}", "c", issue, due, D("100.00"), "open", (A(D("100.00"), paid),)))
    return out


def test_behaviour_insufficient_by_count():
    r = calc.customer_behaviour(_paid_series(5), [], date(2026, 3, 31))
    assert not r.sufficient and r.invoices_analysed == 5 and r.average_days_late is None
    assert "Insufficient data" in r.reason


def test_behaviour_insufficient_by_span():
    r = calc.customer_behaviour(_paid_series(8, step=5), [], date(2026, 3, 31))  # 35-day span
    assert not r.sufficient and r.invoices_analysed == 8


def test_behaviour_metrics_hand_checked():
    invoices = _paid_series(6, late_by=10)  # every invoice paid 10 days late; span 100 days
    # Add one on-time invoice: paid on the due date.
    invoices.append(calc.InvoiceFact("ot", "c", date(2025, 9, 1), date(2025, 10, 1), D("50.00"), "open",
                                     (A(D("20.00"), date(2025, 9, 20)), A(D("30.00"), date(2025, 10, 1)))))
    # A disputed and an open invoice are excluded.
    invoices.append(calc.InvoiceFact("d", "c", date(2025, 9, 1), date(2025, 10, 1), D("10.00"), "disputed",
                                     (A(D("10.00"), date(2025, 10, 5)),)))
    invoices.append(calc.InvoiceFact("o", "c", date(2025, 9, 1), date(2025, 10, 1), D("10.00"), "open", ()))
    r = calc.customer_behaviour(invoices, [date(2025, 7, 11), date(2025, 7, 11), date(2025, 8, 1)], date(2026, 3, 31))
    assert r.sufficient and r.invoices_analysed == 7
    # Days to payment: six × 40, one × 30 → 270 / 7 = 38.571… → 38.6
    assert r.average_days_to_payment == D("38.6")
    # Days late: six × 10, one × 0 → 60 / 7 = 8.571… → 8.6
    assert r.average_days_late == D("8.6")
    # On time: 1 / 7 = 14.285… → 14.3
    assert r.on_time_percentage == D("14.3")
    # 2 distinct payment dates / 12 months = 0.1666… → 0.2
    assert r.payment_frequency_per_month == D("0.2")


def test_behaviour_observation_window():
    old = _paid_series(10, start=date(2023, 1, 1))  # settled before the 365-day window
    r = calc.customer_behaviour(old, [], date(2026, 3, 31))
    assert r.invoices_analysed == 0 and not r.sufficient
