# Database design principles

## General
Use PostgreSQL with explicit foreign keys, constraints and migrations. Use stable primary keys. Store timestamps in UTC and retain the relevant business date where required.

## Tenant ownership
Every organisation-owned record must contain `organisation_id` or be reachable through a rigorously enforced tenant-owned parent. Tenant scope is enforced in backend queries and may be reinforced with PostgreSQL Row Level Security.

## Initial entities
- users
- organisations
- organisation_memberships
- customers
- suppliers
- import_batches
- import_rows or source references
- invoices
- credit_notes
- payments
- payment_allocations
- cash_accounts or opening_cash_entries
- forecast_scenarios
- forecast_items
- audit_events

Final schema must be designed from detailed feature specifications. This list is conceptual, not a migration script.

## Financial data
- Store money using an exact decimal representation, such as PostgreSQL `NUMERIC`.
- Store currency code explicitly for every monetary value.
- Define precision and rounding rules centrally.
- Preserve original imported values and source references.
- Do not overwrite financial history to correct an error; use auditable correction or reversal workflows.

## Constraints and indexes
Use database constraints for essential integrity, including foreign keys, non-null requirements and unique keys within an organisation where appropriate. Add indexes based on query patterns and measured performance.

## Migrations
All schema changes use versioned migrations. Migrations must be reviewed, tested against representative data and have a rollback or recovery strategy. Destructive changes require explicit approval.

---

## As built — Release 1 (migrations `0001`, `0002`)

### Tables
| Table | Tenant-owned | Notes |
|---|---|---|
| users, user_sessions, user_tokens | No | Identity. Session and email/reset tokens stored only as SHA-256 hashes. |
| organisations, memberships, invitations | No (access via membership checks) | Role check constraint; one membership per user per organisation. |
| customers | Yes | Unique code per organisation; normalised name for exact matching. |
| stored_files | Yes | Metadata, SHA-256 and storage key of every uploaded source file. |
| import_batches, import_rows | Yes | `raw` source values are immutable (trigger); corrections stored separately. |
| invoices, invoice_versions | Yes | Current values plus an immutable version history (every version, including the first). Unique (organisation, customer, normalised number). `status` ∈ open/disputed/cancelled/void; "paid" is derived. |
| credit_notes | Yes | Positive amount; unique per customer. |
| payments | Yes | `customer_id` NULL = unassigned bank receipt; dedupe key. |
| allocations | Yes | Payment **or** credit note → invoice; positive amount; effective date = source date. Cannot be deleted or altered, only reversed (trigger). |
| audit_events | Org or NULL | Insert-only (RLS has no UPDATE/DELETE policy and a trigger blocks changes even for superusers). |
| email_outbox | No | Development only. |

### Money and dates
`NUMERIC(19,4)` for every amount plus a 3-letter currency; business dates as `DATE`; event times as `TIMESTAMPTZ` (UTC).

### Row Level Security
All tenant-owned tables have `ENABLE` and `FORCE ROW LEVEL SECURITY` with policy
`organisation_id = NULLIF(current_setting('app.current_org', true), '')::uuid`. The API sets `app.current_org` transaction-locally after verifying membership; with no setting, no rows are visible (fail closed). The application database role is not a superuser and has no `BYPASSRLS`; tests assert this.

### Recommended production roles
- `vittasynx_app`: runtime; owns no tables; `SELECT/INSERT/UPDATE` on business tables, no `DELETE` on financial tables.
- `vittasynx_migrator`: runs Alembic only.
Release 1 local setup uses a single non-superuser role; splitting roles is a pre-staging task.
