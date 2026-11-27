# MVP scope

Approved by the product owner on 2026-11-27 (Phase 1 decisions D-02, D-04, D-05, D-12, D-14, D-19). See `docs/reviews/phase-1-approval.md`.

## Release 1 — Receivables intelligence (current build)
1. User authentication and organisation workspaces (users may belong to several organisations).
2. Organisation roles and permissions (five roles, backend-enforced).
3. Customer master records.
4. CSV/XLSX import for invoices, credit notes and bank receipts.
5. Import preview, column mapping, validation, duplicate detection, amendment candidates and error reporting.
6. Invoice register, credit notes, balances and ageing as at an explicit reporting date.
7. Payment records (manual and bank CSV receipts) and controlled allocation to invoices.
8. Unapplied payment and credit handling.
9. Observed customer payment behaviour, suppressed when data is insufficient.
10. Receivables dashboard.
11. CSV export of invoice register, ageing report and customer balances.
12. Audit history for imports, edits, allocations, memberships and settings.

## Release 2 — Cash forecast (only after the Phase 6 gate is approved)
- Supplier master records and supplier obligations.
- Opening cash entries.
- Rolling 13-week cash forecast with visible assumptions.
- Scenarios that never modify actual records.
- Cash section of the dashboard.

## Deferred until after pilot evidence
- Operational alerts.
- DSO.
- Write-off workflow (use a credit note with reason "write-off" meanwhile).
- AI processing of customer financial data (Release 1 uses deterministic match suggestions).
- Multi-currency.

## Explicitly excluded
- Full accounting/general ledger
- Payroll and tax filing
- Payment initiation or money movement, including sending reminders or statements to debtors
- Inventory, purchase-order or warehouse management
- Lending, underwriting or credit bureau services
- Autonomous financial decisions
- Cross-company customer credit scoring
- Complex ERP integrations
- Multi-entity consolidation
- AI-generated financial calculations

## MVP constraints
- Begin with CSV/XLSX and common accounting exports.
- One reporting currency per organisation, fixed at creation; rows in other currencies are rejected.
- Do not assume imported data is complete or correct.
- Build a modular monolith before considering distributed services.

## Scope change
A proposed feature must state:
- Customer problem and evidence
- User and workflow affected
- Data required
- Security and privacy implications
- Build and support cost
- Why it belongs in the MVP
The product owner must approve scope changes. Update this document and the relevant requirements before implementation.
