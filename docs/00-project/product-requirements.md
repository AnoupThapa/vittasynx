# Product requirements

## Users and roles (approved D-03)
- Organisation Owner
- Administrator
- Finance Manager
- Accounts Receivable Officer
- Read-only User

There is exactly one Owner per organisation. Platform support staff have no access to tenant data in Release 1.

### Permission matrix (backend-enforced)
| Action | Owner | Admin | Finance Mgr | AR Officer | Read-only |
|---|---|---|---|---|---|
| View dashboard, invoices, customers, payments | ✔ | ✔ | ✔ | ✔ | ✔ |
| Export reports | ✔ | ✔ | ✔ | ✔ | — |
| Create/edit customers | ✔ | ✔ | ✔ | ✔ | — |
| Upload, map and confirm an import | ✔ | ✔ | ✔ | ✔ | — |
| Enter an invoice manually | ✔ | ✔ | ✔ | ✔ | — |
| Approve a source amendment to an existing invoice | ✔ | ✔ | ✔ | — | — |
| Record manual payment | ✔ | ✔ | ✔ | ✔ | — |
| Confirm allocation | ✔ | ✔ | ✔ | ✔ | — |
| Reverse a confirmed allocation | ✔ | ✔ | ✔ | — | — |
| Record credit note, cancel/dispute invoice | ✔ | ✔ | ✔ | — | — |
| View audit log | ✔ | ✔ | ✔ | — | — |
| Invite/remove users, change roles | ✔ | ✔ | — | — | — |
| Organisation settings | ✔ | ✔ | — | — | — |
| Transfer ownership, delete organisation | ✔ | — | — | — | — |

An Administrator cannot remove, demote or change the Owner.

## Primary jobs
- Import current invoices and transaction data.
- Identify unpaid and overdue invoices.
- Review customer payment patterns.
- Match bank receipts to invoices with traceable confirmation.
- Understand expected cash receipts and upcoming cash outflows.
- Test simple what-if scenarios without changing actual records.

## Functional requirements

### Organisation and access
- A user can belong to one or more organisations only through explicit membership.
- Each organisation has its own users, customers, suppliers and financial records.
- Roles determine permitted actions.
- All access is checked by the backend.

### Import
- Users can upload supported CSV/XLSX templates.
- The system shows a preview before committing records.
- Invalid rows are reported with actionable reasons.
- Duplicate candidates are flagged.
- Original source file and row identifiers are retained according to the retention policy.
- Importing the same file twice must not silently duplicate records.

### Receivables
- Display invoice number, customer, issue date, due date, original amount, allocated payments, credits and remaining balance.
- Provide current, 1–30, 31–60, 61–90 and over-90-day ageing buckets, with the ageing basis documented.
- Allow filters by customer, due status and date.
- Show the source and calculation basis for balances.

### Payment allocation
- A payment may be allocated across multiple invoices.
- An invoice may receive multiple partial payments.
- The user can review and confirm suggested matches.
- Unallocated funds remain visible as unapplied.
- Allocation changes are auditable.

### Customer payment behaviour
- Summarise observed payment timing from valid invoice and payment history.
- Display sample size and observation period.
- Do not present a prediction as a verified fact.
- Do not calculate a meaningful behavioural indicator when data is insufficient.
- Metric definitions and thresholds: `docs/03-business-rules/financial-calculations.md` §Customer payment behaviour.

### Cash forecast (Release 2 — not in the current build)
- Display a rolling 13-week forecast.
- Separate opening cash, expected receipts and expected outflows.
- Distinguish confirmed, scheduled, estimated and scenario-only values.
- Allow users to adjust assumptions in a scenario without modifying actual records.
- Show the source and confidence basis for material forecast items.

## Non-functional requirements
- Tenant isolation and least-privilege access.
- Secure transport and encrypted storage where supported by selected providers.
- Auditability of financial changes.
- Reliable backups and tested restoration.
- Responsive desktop and tablet experience; mobile should support core review tasks.
- Clear error messages and recoverable import workflows.
- Performance targets must be set after pilot data volumes are measured.

## Acceptance
Each feature requires specific acceptance criteria and automated tests. See `docs/08-quality-assurance/acceptance-criteria.md`.
