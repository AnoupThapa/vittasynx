# Document import

**Status:** Built (Release 1). Tests: `backend/tests/test_imports.py` (27 tests), E2E `e2e/smoke_test.py`.

## Workflow
1. **Upload** a `.csv` or `.xlsx` (≤ 5 MB, ≤ 20,000 rows). The file is validated (type, encoding, macros, decompressed size) before anything is stored, then kept privately as source evidence with its SHA-256.
2. **Preview** the first 20 rows; Vittasynx suggests a column mapping from header synonyms.
3. **Map** columns and choose the file's date format (DD/MM/YYYY, YYYY-MM-DD, MM/DD/YYYY, DD-MM-YYYY, DD.MM.YYYY). ISO dates are always accepted.
4. **Validate** every row. Statuses: Ready, Error, Already imported, Changed (amendment), Needs review, Skipped.
5. **Correct or exclude** rows. Corrections are stored beside the untouched raw value.
6. **Confirm**: new customers must be confirmed; rows with errors must be corrected or explicitly excluded.
7. **Commit**: records are created with source-row references; the summary is recorded in the audit log. Re-committing is harmless (idempotent).

## Import types and required columns
| Type | Required |
|---|---|
| Invoices | number, customer code or name, issue date, due date, total (or net + tax) |
| Credit notes | number, customer, date, amount |
| Payments | date, amount (customer optional) |
| Bank | date, credit or signed amount; debit lines are skipped |

## Validation rules (examples)
Missing or invalid dates; due before issue; more decimal places than the currency allows (never rounded); ambiguous number formats such as `1.100,00`; other currencies; negative invoice totals (use credit notes); draft status; unrecognised status (mappable); duplicate within the file; total ≠ net + tax.

## Re-imports (D-09)
Identical rows are skipped. Changed invoices become **amendments** that a Finance Manager or above must approve; approval creates a new invoice version and keeps the old one. Same number under a different customer requires an explicit include/exclude decision.
