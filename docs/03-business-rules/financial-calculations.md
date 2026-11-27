# Financial calculations

## Calculation contract
Every calculation specification must state:
1. Purpose
2. Formula
3. Input definitions and units
4. Date basis and reporting period
5. Inclusion and exclusion rules
6. Currency and rounding
7. Missing-data behaviour
8. Worked example
9. Edge cases and automated tests

Use decimal arithmetic. Never use binary floating-point for monetary calculations.

## Outstanding invoice balance
Let:
- `I` = original invoice amount
- `P` = valid payments allocated to the invoice
- `C` = applicable credits

`Outstanding balance = I - P - C`

The system must prevent invalid negative balances through allocation controls or explicitly classify credit balances/overpayments. Do not silently clamp a negative result to zero.

## Receivables ageing
For an invoice with positive outstanding balance:
`Days past due = max(0, reporting date - due date)`
Ageing buckets:
- Current: not yet due
- 1–30 days overdue
- 31–60 days overdue
- 61–90 days overdue
- More than 90 days overdue

The exact bucket boundaries must be consistent in UI, exports and tests.

## Days Sales Outstanding (DSO)
A common approximation is:
`DSO = average accounts receivable / credit sales for period × number of days in period`

Before implementing, define whether receivables include tax, how average receivables are calculated, and how credit sales and opening balances are sourced. DSO must not be shown if the required inputs are unavailable or unreliable.

## Cash forecast
For each forecast period:
`Closing cash = Opening cash + expected inflows - expected outflows`
The next period's opening cash equals the prior period's closing cash in the same scenario.

Each inflow/outflow must have a status and source. Do not add a forecast item to actual cash merely because its expected date has passed.

## Rounding
Store and calculate at the defined currency precision. Apply rounding at explicitly specified boundaries, not arbitrarily at every intermediate step. Document currency-specific precision and rounding mode before supporting multiple currencies.

## Test cases
At minimum test zero values, partial payments, multiple allocations, credits, overpayments, negative adjustments, duplicate imports, missing dates, month/year boundaries, leap years, rounding boundaries and currency mismatch.

---
## Approved Release 1 calculation specifications (rule version `R1-2026-11-27`)

### Money, precision and rounding (D-07)
- Storage: PostgreSQL `NUMERIC(19,4)` plus currency code.
- Calculation: Python `decimal.Decimal`; no float anywhere. APIs send money as strings.
- Input amounts must be at currency precision (2 decimals for AUD and NPR); otherwise rejected.
- Sums of amounts at currency precision are exact and are not rounded.
- Where rounding is unavoidable (derived gross, averages): `ROUND_HALF_UP` to currency precision for money and to 1 decimal place for day-based metrics; percentages to 1 decimal place.

### Outstanding balance as at reporting date R
1. Purpose: amount the customer still owes on one invoice at R.
2. Formula: `B(R) = I − Σ confirmed payment allocations (payment date ≤ R) − Σ confirmed credit allocations (credit note date ≤ R)`, using the invoice version effective at report time.
3. Inputs: I = current accepted invoice amount (gross); allocations not reversed.
4. Date basis: invoices with issue date ≤ R. Allocation effective date = payment/credit note date.
5. Inclusion: status open, paid or disputed. Exclusion: cancelled, void.
6. Currency: organisation currency only; no rounding (exact).
7. Missing data: invoices without a valid due date cannot be imported.
8. Worked example: I = 1,100.00; payment allocations 300.00 (10 Feb) and 250.00 (5 Mar); credit 100.00 (1 Mar). B(28 Feb) = 800.00. B(31 Mar) = 450.00.
9. Edge cases and tests: `backend/tests/test_calculations.py`.

### Ageing as at R
- `days_past_due = R − due_date` (calendar days).
- Buckets (inclusive): current (≤ 0), 1–30, 31–60, 61–90, 91+.
- Only invoices with B(R) > 0. Negative balances are exceptions, listed separately.
- Bucket totals must equal total outstanding at R.
- Example: R = 2026-03-31, due 2026-03-01 → 30 days → 1–30. Due 2026-03-31 → 0 → current.

### Customer payment behaviour (D-13)
- Qualifying invoices: fully settled (B = 0) on or before R, status not disputed/cancelled/void, settlement date within the observation window (default the 365 days ending at R).
- Settlement date = effective date of the allocation that brought the balance to zero.
- Days to payment = settlement date − issue date. Days late = max(0, settlement date − due date).
- Average days to payment, average days late = unweighted means, 1 decimal place.
- On-time % = invoices with settlement date ≤ due date ÷ qualifying invoices × 100, 1 decimal place.
- Payment frequency = distinct payment dates in the window ÷ months in the window, 1 decimal place.
- Minimum sample: ≥ 6 qualifying invoices AND first-to-last settlement span ≥ 90 days. Otherwise all metrics show "insufficient data" with n.
- Limitation shown to users: open invoices are excluded, which biases towards customers who eventually paid.
- No scores or credit judgements.

### DSO (D-14)
Deferred. Not shown in Release 1.
