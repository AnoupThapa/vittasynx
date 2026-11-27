# Shared coding-agent instructions

Vittasynx is a multi-tenant financial operations SaaS for B2B wholesalers and distributors.

## Non-negotiable principles (read first)
Full text and tool responsibilities: `docs/00-project/engineering-principles.md`.
1. Documentation before implementation.
2. Financial rules before financial features.
3. Database and tenant security before customer data.
4. Automated tests before declaring completion.
5. Human approval before production deployment.

## Your role (Codex)
Codex is the independent reviewer, tester and problem solver. For each pull request you did not write:
- Check it against the cited documentation and `docs/03-business-rules/` (principles 1 and 2).
- Re-run `cd backend && python -m pytest`, `cd frontend && npm run typecheck && npm test`, and the E2E test when workflows change; report exact results (principle 4).
- Check tenant isolation, permissions, decimal arithmetic and immutability of financial history (principle 3).
- Report findings by severity. Do not approve your own changes and never deploy (principle 5).

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
