# Receivables dashboard

**Status:** Built (Release 1). Tests: `backend/tests/test_reports.py` (8 tests including the reconciliation chain).

Every figure states the reporting date, currency, calculation time and rule version, and has a written definition on the page.

| Figure | Definition |
|---|---|
| Total outstanding | Sum of positive invoice balances as at the reporting date (cancelled/void excluded) |
| Overdue | Balance of invoices whose due date is before the reporting date (count shown) |
| Current | Balance not yet due |
| Ageing | Current, 1–30, 31–60, 61–90, 91+ days past due; bucket totals must reconcile to total outstanding (checked on every request) |
| Unapplied payments / credits | Shown separately; never netted into outstanding |
| Net position | Outstanding − unapplied payments − unapplied credits, labelled as net |
| Largest overdue customers, oldest invoices, recent payments, unapplied payments | Top 10 lists |
| Exceptions | Invoices with negative balances, excluded from ageing and flagged |

Exports (CSV): invoice register, ageing by customer, customer balances. Each carries organisation, reporting date, currency and rule version, neutralises spreadsheet formula injection, and is recorded in the audit log.
