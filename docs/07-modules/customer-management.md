# Customer management

**Status:** Built (Release 1). Tests: `backend/tests/test_reports.py`, `test_imports.py`, `test_permissions.py`.

## What it does
- Create, edit, deactivate and search customers (name or code).
- Customer detail: balances by ageing bucket, unapplied payments and credits, invoice history, observed payment behaviour.
- Every customer belongs to exactly one organisation (RLS-enforced).

## Rules
- Customer code is unique within an organisation. Without a code, the normalised name must be unique.
- Import matching: code first, then exact normalised name; never fuzzy (D-15). Unknown customers are created only after the user confirms.
- Who can edit: Owner, Admin, Finance Manager, AR Officer.

## Payment behaviour (observed, not predicted)
Definitions: `docs/03-business-rules/financial-calculations.md` §Customer payment behaviour. Shown only with ≥ 6 fully paid invoices spanning ≥ 90 days; otherwise "Insufficient data (n = X)". No scores or credit judgements.
