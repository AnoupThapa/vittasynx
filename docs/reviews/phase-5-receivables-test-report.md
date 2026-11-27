# Phase 5 — Invoice imports and receivables intelligence: build and test report

- **Date:** 2026-11-27
- **Status:** AWAITING APPROVAL. Built and tested with **synthetic data only**. This is not real-world validation; Phase 6 (anonymised real data) has not started.

## Modules built
Customer management, invoice import (CSV/XLSX with mapping, validation, correction, exclusion, duplicates, amendments), invoice management with credit notes, payment management (manual, payment import, bank import), payment allocation with deterministic suggestions and reversal, receivables dashboard, customer payment behaviour, CSV exports. Specifications: `docs/07-modules/`.

## Results — exact
| Suite | Result |
|---|---|
| `test_calculations.py`: money parsing and rounding boundaries, dates, balances, ageing boundaries, month/year end, leap years, point-in-time, behaviour metrics hand-checked | 55 passed |
| `test_imports.py`: workflow 1 (clean file, missing fields, duplicates, different column names, invalid dates, inconsistent number formats), XLSX, unsafe files, limits, credit notes, payments, bank, amendments, idempotent commit, source file preserved | 27 passed |
| `test_allocations.py`: workflow 3 (multiple partials, split payment, over-allocation, unapplied, duplicate payment, reversal, wrong customer, cancelled invoice, concurrent allocation race) | 14 passed |
| `test_reports.py`: workflow 2 & 4 and the reconciliation chain, filters, export = screen, CSV formula injection, behaviour (sufficient and insufficient) | 8 passed |
| End-to-end browser test `e2e/smoke_test.py` (Chrome, real API + web app) | 11/11 checks passed |

Full backend suite: **151 passed, 0 failed.**

## Synthetic reconciliation (pre-check for Phase 6)
Dataset in `test_reports.py` (7 invoices, 4 customers, payments, a credit and a cancellation), reporting date 31 Mar 2026:

| Stage | Total | Matches |
|---|---|---|
| Source spreadsheet invoice totals | 3,679.00 | — |
| Imported invoice totals | 3,679.00 | = source |
| Less cancelled invoice | −999.00 | |
| Less confirmed allocations (300 + 100 credit + 80) | −480.00 | = allocation records |
| Calculated invoice balances | 2,200.00 | = 3,679 − 999 − 480 |
| Ageing bucket totals (550 + 300 + 700 + 400 + 250) | 2,200.00 | = balances |
| Customer-level totals | 2,200.00 | = balances |
| Dashboard total outstanding | 2,200.00 | = balances |
| Ageing CSV export | 2,200.00 | = dashboard |

No discrepancies. Every figure was computed by hand in the test's docstring before the code ran.

## Defects found during testing
Two test expectations were wrong and the code was right (a disputed invoice 89 days overdue belongs in 61–90; an invoice issued before the as-at date counts). The test expectations were corrected; no calculation code changed.

## Known limitations
- Imports are synchronous (≤ 5 MB / 20,000 rows); a background worker is needed for larger files (ADR-004).
- Suggestions for unassigned bank receipts use only invoice numbers in the description.
- Single currency per organisation; no write-off workflow (use credit notes); no DSO; no alerts.
- Calculations recompute from records on each request; performance with pilot volumes is unmeasured.
- Customer behaviour excludes open invoices (bias towards customers who eventually pay); shown on screen.
- Browser testing covered Chrome at desktop width only; tablet layout is responsive by CSS but was not tested on devices.
