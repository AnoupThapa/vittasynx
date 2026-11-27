# Pre-launch hardening report

- **Date:** 2026-11-27
- **Status:** AWAITING REVIEW (PR)
- **Approved scope:** owner approval of Phases 3–5 and the hardening work, 2026-11-27

## Delivered
1. Rate limiting on authentication endpoints (PostgreSQL-backed, multi-instance safe).
2. MFA recovery codes (10, single use, hashed; regeneration needs a current TOTP code).
3. SMTP email adapter (standard library; no new dependency).
4. Database file-storage backend with forced RLS (`file_blobs`), for free/serverless hosting.
5. Separate database roles script (`deploy/sql/roles.sql`).

Migration `0003_hardening` adds `rate_limit_hits`, `mfa_recovery_codes` and `file_blobs` (RLS forced).

## Results — exact
- `python -m pytest -q` → **161 passed, 0 failed** (151 previous + 10 in `test_hardening.py`).
- `alembic downgrade base && alembic upgrade head && alembic check` → no drift.
- `tsc --noEmit` → no errors; `next build` → succeeded.
- Roles script: applied to a fresh database; migrations run as `vittasynx_migrator`; runtime role confirmed `rolsuper=f`, `rolbypassrls=f`, no DELETE on `allocations`/`invoices`, no UPDATE on `audit_events`. **E2E smoke test passed 11/11 with the API running as `vittasynx_app` and `VX_STORAGE_BACKEND=database`**; 0 server errors logged.

## Still open before paid production
- External security review / penetration test.
- S3-compatible object storage adapter (database storage is fine for Release 1 limits but grows the database).
- Email provider account (owner action) and SPF/DKIM for the sending domain.
- Legal privacy review (Australia, Nepal).
