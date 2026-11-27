# Shared coding-agent instructions

Vittasynx is a multi-tenant financial operations SaaS for B2B wholesalers and distributors.

Before work:
1. Read `README.md`.
2. Read `docs/00-project/vision.md`, `scope.md` and `product-requirements.md`.
3. Read all relevant architecture, business-rule, security and test documents.

Follow `CLAUDE.md` for the complete engineering, security, financial-integrity and AI-use rules. If your coding tool does not automatically read `AGENTS.md`, configure it to do so.

Do not guess when documentation conflicts. Stop and report the conflict.

Critical requirements:
- Tenant isolation is mandatory and enforced server-side.
- Monetary calculations use decimal arithmetic.
- Imported records are immutable source evidence; corrections are auditable.
- Actuals, confirmed items, estimates and scenarios remain distinct.
- LLMs do not calculate money or make financial decisions.
- Every behaviour change includes tests and documentation updates.
- Never claim a test or deployment succeeded unless it actually did.
