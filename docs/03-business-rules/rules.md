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
