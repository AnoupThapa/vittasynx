# Integrations

## Release 1
| Integration | Status | Notes |
|---|---|---|
| CSV/XLSX file import (invoices, credit notes, payments, bank) | Built | Configurable column mapping with synonym-based suggestions; works with Xero/MYOB/QuickBooks-style exports without per-vendor code. |
| Email delivery | Adapter only | `dev_outbox` stores emails in the database for development. A real provider (SMTP or API) must be chosen and implemented before staging (startup refuses `dev_outbox` in staging/production). |
| Object storage | Adapter only | Local private directory. An S3-compatible adapter is needed before multi-instance hosting. |
| AI providers | None | Decision D-19: no customer financial data is sent to AI in Release 1. |

## Not in Release 1
- Direct accounting-system APIs (Xero, MYOB, QuickBooks, Tally): excluded as "complex ERP integrations" until pilot evidence shows that file exports are insufficient (assumption A-02).
- Bank feeds / open banking: excluded; bank CSV exports only.
- Payment initiation of any kind: permanently out of scope.

## Adapter rule
External services are isolated behind adapters (`app/services/email.py`, `app/services/storage.py`) so providers can be selected in Phase 3 approval without changing business logic.
