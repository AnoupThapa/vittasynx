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
