# TradeFlow Intelligence

TradeFlow Intelligence is a financial operations intelligence platform for inventory-led B2B wholesalers and distributors. Its first release focuses on receivables visibility, payment behaviour and short-term cash-flow forecasting.

## Current product stage
Pre-development specification and validation. This repository is not production-ready.

## Product promise
Help a business understand what it is owed, when cash may arrive, what obligations are approaching and which items need attention.

## MVP boundaries
- Organisation workspaces and role-based access
- Customer and supplier records
- CSV/XLSX import of invoices and bank transactions
- Invoice balances and receivables ageing
- Payment allocation with user review
- Customer payment history
- A rolling 13-week cash forecast with explicit assumptions
- Basic reports and alerts

Not in the MVP: general ledger, tax filing, payroll, payment execution, inventory management, lending, credit bureau services, autonomous financial decisions or cross-company credit scoring.

## Documentation
Read `CLAUDE.md` or `AGENTS.md` first, then:
1. `docs/00-project/vision.md`
2. `docs/00-project/scope.md`
3. `docs/00-project/product-requirements.md`
4. `docs/02-architecture/architecture.md`
5. `docs/03-business-rules/rules.md`
6. `docs/03-business-rules/financial-calculations.md`

The documents are the working source of truth. Where they conflict, stop and raise the conflict rather than guessing.

## Proposed technology direction
- Frontend: Next.js / React with TypeScript
- Backend: Python / FastAPI
- Database: PostgreSQL
- Financial calculations: Python domain services using decimal arithmetic
- Background processing: worker queue for imports and reports
- File storage: private S3-compatible object storage
- Testing: pytest, frontend unit tests and Playwright end-to-end tests

This is a proposed stack, not a final infrastructure purchase decision. Record material decisions in `docs/09-decisions/architecture-decisions.md`.

## Development setup
Detailed local setup instructions must be added once the repository and deployment providers are selected. Never commit secrets. Use `.env.example` with placeholder values only.

## Definition of done
A feature is complete only when its acceptance criteria, automated tests, security checks and relevant documentation are complete. Financial features must include calculation examples and edge-case tests.
