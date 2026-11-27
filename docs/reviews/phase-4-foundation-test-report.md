# Phase 4 — Application foundation test report

- **Date:** 2026-11-27
- **Status:** AWAITING APPROVAL (all automated gate checks pass; owner review outstanding)
- **Environment:** PostgreSQL 16.15 (non-superuser role, RLS forced), Python 3.13, FastAPI 0.165, SQLAlchemy 2.1, Next.js 15.5, TypeScript 5.9. Local test environment only; nothing is deployed.

## Scope built
Authentication (registration, login/logout, server-side sessions, idle and absolute expiry, account lockout, email verification, password reset, TOTP MFA with enforcement for Owner/Admin), organisations (create, settings, multiple organisations per user), memberships (invitations by verified email, role changes, removal, ownership transfer), backend-enforced role permissions, tenant isolation (application checks plus PostgreSQL Row Level Security), audit logging, migrations, centralised configuration, structured logging, error handling, health checks, dashboard shell.

## Results — exact
Command: `cd backend && python -m pytest -q` → **151 passed in 59.63 s, 0 failed, 0 skipped.**

| Test file | Tests | Covers |
|---|---|---|
| `test_auth.py` | 16 | Registration, login, generic login errors, lockout, CSRF, idle and absolute session expiry, hashed tokens, email verification, password reset (revokes sessions; single-use token), MFA enrolment and login, MFA enforcement for privileged roles, audit of identity events, health checks, production-by-default config, dev outbox disabled outside development |
| `test_organisations.py` | 13 | Org creation and validation, settings, invitation flow, wrong/unverified email rejected, revoked invitation, owner protection, removed member loses access, ownership transfer, multi-organisation switching, membership audit |
| `test_permissions.py` | 3 | Full permission matrix: 11 actions × 5 roles, each allowed or refused (403) as approved in D-03; allocation reversal; ownership transfer |
| `test_tenant_isolation.py` | 9 | Cross-tenant reads (19 URLs), A's IDs through B's URLs, 10 cross-tenant write attempts, list isolation, RLS with no context, RLS with wrong context, RLS blocks cross-tenant INSERT and UPDATE, app role cannot bypass RLS, no tenant context leakage between pooled requests |
| `test_db_constraints.py` | 6 | Audit log insert-only (also verified manually: even the PostgreSQL superuser gets "audit_events is insert-only"), allocations immutable and undeletable, invoice versions immutable, raw import values immutable, check constraints, invoice identity uniqueness |

Migrations: `alembic downgrade base && alembic upgrade head && alembic check` → "No new upgrade operations detected" (models and migrations match; downgrade works).

Frontend: `npx tsc --noEmit` → no errors. `npm test` → 3 passed, 0 failed. `next build` → 27 routes compiled.

## Gate checklist
| Gate item | Result |
|---|---|
| Authentication works | ✅ |
| Organisation management works | ✅ |
| Permissions enforced by the backend | ✅ (matrix test) |
| Tenant isolation tests pass | ✅ 9/9, no unresolved failure |
| Database migrations work | ✅ up, down, up, check |
| Critical security checks pass | ✅ automated checks above; **no external penetration test has been done** |
| Automated tests pass | ✅ 151/151 |

## Defects found and fixed during this phase
1. Audit `source` column too short for import references (40 → 80 chars; caught by tests before release).
2. Identity audit events (logins) were insertable but unreadable; read policy corrected so they are readable only outside any tenant context.
3. Header auto-mapping missed run-together names such as `InvoiceNumber`; matching now ignores spaces and punctuation.
4. Configuration defaulted to `development`; now defaults to `production` (fail-safe), so an unconfigured deployment refuses unsafe settings.

## Known limitations
- MFA recovery codes are not implemented; a locked-out privileged user needs manual support.
- No rate limiting beyond per-account lockout (registration and reset requests are not rate-limited). Add at the hosting layer or the application before staging.
- Email delivery is a development outbox only; a provider is required before staging.
- File storage is a local private directory; an S3-compatible adapter is required for multi-instance hosting.
- Single database role locally; separate runtime and migration roles before staging.
- No external security review or penetration test yet.
