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
