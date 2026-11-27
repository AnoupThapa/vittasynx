# Vittasynx

Vittasynx is a financial operations intelligence platform for inventory-led B2B wholesalers and distributors. Release 1 focuses on receivables visibility and customer payment behaviour. Short-term cash-flow forecasting follows in Release 2.

## Current product stage
Release 1 (receivables) is built and tested locally with synthetic data. It is **not deployed and not production-ready**: hosting providers, email delivery, real-data validation (Phase 6) and an external security review are outstanding. See `docs/reviews/project-progress.md`.

## Product promise
Help a business understand what it is owed, when cash may arrive, what obligations are approaching and which items need attention.

## MVP boundaries
- Organisation workspaces and role-based access
Release 1 (built):
- Customer records
- CSV/XLSX import of invoices, credit notes and bank receipts
- Invoice balances and receivables ageing as at a reporting date
- Payment and credit allocation with user review
- Observed customer payment behaviour
- Receivables dashboard and CSV exports

Release 2 (not started): suppliers, opening cash, rolling 13-week cash forecast and scenarios.

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

## Repository layout
```
backend/    FastAPI API, domain calculations, services, Alembic migrations, pytest suite
frontend/   Next.js web app (TypeScript)
e2e/        Browser end-to-end smoke test (Playwright)
docs/       Specifications, decisions, module docs and phase reports
```

## Local development setup
Requires Python 3.12+, Node 20+ and PostgreSQL 16.

1. **Database** (as a PostgreSQL superuser, once). The app role must not be a superuser, or Row Level Security is bypassed:
   ```sql
   CREATE ROLE vittasynx LOGIN PASSWORD 'choose-a-local-password' NOSUPERUSER NOBYPASSRLS;
   CREATE DATABASE vittasynx OWNER vittasynx;
   CREATE DATABASE vittasynx_test OWNER vittasynx;
   ```
2. **Backend**
   ```bash
   cd backend
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements-dev.txt
   cp .env.example .env        # then edit the password
   alembic upgrade head
   uvicorn app.main:app --reload --port 8000
   ```
   `VX_ENVIRONMENT=development` must be set (it is in `.env.example`). With no environment set, the app assumes production and refuses development settings.
3. **Frontend**
   ```bash
   cd frontend
   npm install
   npm run dev                 # http://localhost:3000 (proxies /api to :8000)
   ```
4. In development, verification and invitation emails are not sent; read them at `http://localhost:3000/api/v1/auth/dev/outbox`.

## Tests
```bash
cd backend && python -m pytest          # uses the vittasynx_test database (VX_TEST_DATABASE_URL to override)
cd frontend && npm run typecheck && npm test
python e2e/smoke_test.py                # needs both servers running; backend with VX_ENVIRONMENT=development
```

Never commit secrets. `.env` is git-ignored; `.env.example` holds placeholders only.

## Definition of done
A feature is complete only when its acceptance criteria, automated tests, security checks and relevant documentation are complete. Financial features must include calculation examples and edge-case tests.
