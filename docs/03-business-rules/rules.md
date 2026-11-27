# Core business rules

## 1. General principles
- Financial values are calculated deterministically by backend services.
- Every calculation has defined inputs, date basis, rounding and version.
- Imported source data is preserved.
- No silent financial changes.
- Actual, confirmed, estimated and scenario values remain distinguishable.
- Missing data is shown as missing, never fabricated.

## 2. Invoice rules
- An invoice belongs to one organisation and one customer.
- Invoice number uniqueness is checked within the relevant organisation and source/customer context; do not assume invoice numbers are globally unique.
- Preserve source invoice number and import reference.
- Validate issue date, due date, currency and amount.
- Duplicate candidates are flagged for review.
- Cancelled or void invoices are excluded from outstanding receivables according to their status.
- Credit notes are represented separately and linked to the relevant invoice/customer where possible.

## 3. Payment rules
- A payment belongs to one organisation.
- One payment may be allocated across multiple invoices.
- One invoice may receive multiple partial payments.
- Allocations cannot exceed the available payment amount or invoice balance unless an explicitly approved exception workflow is defined.
- Unallocated payment amounts remain unapplied.
- Reversals and allocation changes are auditable.
- Suggested matches are not confirmed until authorised user action.

## 4. Receivables
Outstanding invoice balance equals original invoice amount less valid allocated payments and applicable credits.
An invoice is overdue when it has a positive outstanding balance and its due date is earlier than the selected reporting date.
Ageing uses a documented basis, normally days past due, and must be consistent across screens and exports.

## 5. Cash forecasting
- Opening cash is an explicit input with an effective date and source.
- Actual bank transactions are not forecasts.
- Expected receipts and expected outflows retain source, expected date, status and confidence basis.
- Forecast assumptions are visible and editable by authorised users.
- Scenarios never modify actual transactions or the baseline forecast.
- A forecast is not a guarantee of future cash.

## 6. Customer payment behaviour
- Metrics use recorded invoice and payment history only.
- Show sample size and observation period.
- Define treatment of partial payments, disputed invoices, credit notes and missing due dates.
- Suppress or label metrics when sample size is insufficient.
- Do not describe a statistical estimate as a verified customer commitment.

## 7. Audit
Record actor, timestamp, organisation, action, affected entity, relevant before/after values where appropriate, and source. Audit records must not be editable through normal application workflows.

## 8. Approved Release 1 rules (Phase 1, 2026-11-27)

### 8.1 Currency (D-07)
- Each organisation has one reporting currency (ISO 4217), fixed at creation.
- Imported rows in another currency are rejected with a clear reason.
- Amounts with more decimal places than the currency allows are validation errors; they are never silently rounded.

### 8.2 Tax basis (D-06)
- Receivables are tax-inclusive: the invoice amount is the gross amount the customer owes.
- Tax amount is optional and informational.
- If an import supplies net and tax but not gross, gross = net + tax, calculated in the backend and marked as derived; both source values are kept.

### 8.3 Source of truth (D-08)
- Balances are calculated by Vittasynx from confirmed allocations only.
- An imported "amount due" or "amount paid" is stored as a source-reported reference. Differences are flagged and never used as the balance.

### 8.4 Credit notes (D-08)
- Credit notes are separate records allocated to invoices with the same controls as payments (capped, confirmed, reversible, audited).
- A credit note referencing an invoice produces a suggested allocation that still needs confirmation.
- Unallocated credit is shown at customer level, outside the ageing buckets.

### 8.5 Duplicates and re-imports (D-09)
- File-level: SHA-256 of the uploaded file. A repeat file triggers a warning; row-level checks still apply.
- Invoice identity: organisation + customer + normalised invoice number (trimmed, upper-cased, internal whitespace removed).
- Identical re-imported row → skipped as already imported.
- Same identity with changed fields → amendment candidate, reviewed by a Finance Manager or above. Accepting creates a new invoice version and keeps the previous version and source rows. An amendment that would reduce the amount below confirmed allocations is blocked until allocations are reversed.
- Same invoice number under a different customer → flagged as a possible duplicate, never merged automatically.
- Payment duplicate candidate: same organisation + date + amount + reference.

### 8.6 Overpayments and credit balances (D-10)
- An allocation can never exceed the remaining invoice balance or the remaining payment/credit amount.
- Excess remains unapplied on the customer.
- Total outstanding receivables = sum of positive invoice balances. Unapplied payments and credits are reported separately. Any "net position" is labelled as net.
- A negative invoice balance is an exception: flagged, excluded from ageing and never clamped.

### 8.7 Invoice statuses (D-17)
| Status | In receivables? | Notes |
|---|---|---|
| open | Yes | Default after import |
| paid | Yes (balance 0) | Derived by the system; never imported as truth |
| disputed | Yes, flagged | Excluded from behaviour metrics |
| cancelled / void | No | Kept for history; confirmed allocations must be reversed first |

Draft invoices are rejected at import. Imported status text is mapped to these values.

### 8.8 Customer matching (D-15)
1. Match on organisation + customer code when supplied.
2. Otherwise exact normalised name (trimmed, case-folded, whitespace collapsed).
3. Unknown customers are listed in the preview; the user confirms creating them.
4. No fuzzy automatic matching.

### 8.9 Dates and timezone (D-16)
- Each organisation has an IANA timezone.
- Business dates (issue, due, payment, credit note) are stored as dates without time.
- The default reporting date is today in the organisation's timezone.
- A missing due date, or a due date before the issue date, is a validation error.

### 8.10 Bank receipts (D-21)
- Bank CSV credit (incoming) lines are imported as receipts; debit lines are skipped and counted in the summary.
- A receipt is a customer payment once assigned to a customer; until then it is an unassigned receipt.

### 8.11 Write-offs (D-12)
No write-off workflow in Release 1. Use a credit note with reason "write-off".
