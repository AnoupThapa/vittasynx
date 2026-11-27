# Testing strategy

## Test layers
- Unit tests: formulas, validation, ageing, allocation and forecast logic.
- Integration tests: database constraints, API authorization, imports and worker jobs.
- Security tests: authentication, permissions, tenant isolation and file access.
- End-to-end tests: core user workflows in a browser.
- Regression tests: every fixed defect receives a test where practical.

## Financial test data
Use synthetic fixtures with known expected results. Include decimal precision, partial payment, split payment, credit note, unapplied receipt, duplicate import and overdue scenarios.

## Required edge cases
- Zero amount and zero balance
- Partial and multiple payments
- Payment split across invoices
- Overpayment and unapplied amount
- Credit note and reversal
- Duplicate invoice and duplicate import
- Missing or invalid dates
- Due date before issue date
- Month end, year end and leap year
- Currency mismatch
- Rounding boundaries
- Insufficient history for behaviour metrics
- Forecast item moved, cancelled or received late
- Tenant-crossing attempts

## Release gate
No release if:
- A financial calculation test fails.
- A tenant-isolation test fails.
- A migration risks data loss without an approved recovery plan.
- Critical security checks fail.
- Acceptance criteria are not met.
