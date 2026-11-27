# MVP scope

## Included
1. User authentication and organisation workspaces.
2. Organisation roles and permissions.
3. Customer and supplier master records.
4. CSV/XLSX import for invoices and bank transactions.
5. Import preview, validation, duplicate detection and error reporting.
6. Invoice register, balances and ageing.
7. Payment records and controlled allocation to invoices.
8. Unapplied payment handling.
9. Customer payment history based on recorded transactions.
10. Rolling 13-week cash forecast with visible assumptions.
11. Basic cash and receivables dashboard.
12. Exportable reports and simple operational alerts.
13. Audit history for imports, edits, allocations and important settings.

## Explicitly excluded from MVP
- Full accounting/general ledger
- Payroll and tax filing
- Payment initiation or money movement
- Inventory, purchase-order or warehouse management
- Lending, underwriting or credit bureau services
- Autonomous financial decisions
- Cross-company customer credit scoring
- Complex ERP integrations
- Multi-entity consolidation
- AI-generated financial calculations

## MVP constraints
- Begin with CSV/XLSX and common accounting exports.
- Support one organisation's reporting currency in the first release unless a documented requirement justifies multi-currency.
- Do not assume imported data is complete or correct.
- Forecast inputs and confidence must be visible.
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
