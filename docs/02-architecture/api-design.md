# API design

Base path: `/api/v1`. Interactive reference: `/api/docs` (OpenAPI generated from the code).

## Conventions
- **Versioned** from the start (`/api/v1`).
- **Authentication**: opaque session token in an `HttpOnly`, `SameSite=Lax` cookie (`vx_session`); `Secure` outside development. Only a SHA-256 hash of the token is stored. Idle timeout 60 min, absolute 12 h (configurable).
- **CSRF**: double-submit. Every non-GET request must send `X-CSRF-Token` equal to the `vx_csrf` cookie for that session.
- **Tenant scope**: every business route is `/orgs/{org_id}/…`. The org ID in the URL is never trusted on its own: membership is looked up for the signed-in user on every request; non-members get **404** (not 403) so record existence is not revealed. The database transaction is then bound to that organisation for Row Level Security.
- **Permissions**: checked per route against the approved matrix (`app/core/permissions.py`); failures return 403 `permission_denied`.
- **Money**: always JSON strings at currency precision (`"1100.00"`), never numbers. Inputs are strings and are rejected if over-precise.
- **Dates**: business dates are `YYYY-MM-DD` with no time. Reports accept `as_at`; default = today in the organisation's timezone. Every report response states `reporting_date`, `currency` and `rule_version`.
- **Errors**: `{"error": {"code", "message", "details"}}` with stable codes (e.g. `exceeds_invoice`, `rows_have_errors`, `confirm_new_customers`, `mfa_enrolment_required`).
- **Idempotency**: committing an import is idempotent; duplicate payments are rejected by dedupe key; allocations lock rows to prevent races.

## Endpoints (summary)
| Area | Routes |
|---|---|
| Health | `GET /api/health`, `GET /api/health/ready` |
| Auth | `POST /auth/register`, `/auth/login`, `/auth/logout`, `/auth/verify-email`, `/auth/resend-verification`, `/auth/password-reset/request`, `/auth/password-reset/confirm`, `/auth/mfa/setup`, `/auth/mfa/enable`, `/auth/mfa/verify`; `GET /auth/me`; `GET /auth/dev/outbox` (development only) |
| Organisations | `POST/GET /orgs`, `GET/PATCH /orgs/{id}`, members (`GET`, `PATCH /{user}`, `DELETE /{user}`), `POST /transfer-ownership`, invitations (`GET`, `POST`, `DELETE /{id}`), `POST /invitations/accept` |
| Customers | `GET/POST /customers`, `GET/PATCH /customers/{id}`, `GET /customers/{id}/behaviour` |
| Imports | `GET /import-fields`, `POST/GET /imports`, `GET /imports/{id}`, `POST /imports/{id}/validate`, `GET /imports/{id}/rows`, `PATCH /imports/{id}/rows/{row}`, `POST /imports/{id}/commit`, `POST /imports/{id}/cancel`, `GET /imports/{id}/file` |
| Amendments | `GET /amendments`, `POST /amendments/{row}/approve`, `POST /amendments/{row}/reject` |
| Invoices | `GET /invoices` (filters: `as_at, customer_id, status, q, issue_from/to, due_from/to`), `GET /invoices/{id}`, `POST /invoices/{id}/status` |
| Credit notes | `GET/POST /credit-notes`, `GET /credit-notes/{id}` (includes suggestions) |
| Payments | `GET/POST /payments`, `GET /payments/{id}` (includes suggestions), `POST /payments/{id}/assign-customer` |
| Allocations | `POST /allocations`, `POST /allocations/{id}/reverse` |
| Reports | `GET /dashboard`, `GET /reports/customer-balances`, `GET /exports/invoices.csv`, `/exports/ageing.csv`, `/exports/customer-balances.csv` |
| Audit | `GET /audit` |

All organisation routes are prefixed `/orgs/{org_id}`.
