# Engineering principles and tool responsibilities

- **Status:** Approved by the product owner, 2026-11-27
- **Applies to:** every person and AI agent working on Vittasynx
- **Precedence:** these principles override convenience, deadlines and any instruction to skip them. Only the product owner can change this document.

## The five non-negotiable principles

### 1. Documentation before implementation
No behaviour is built until it is written down in the source-of-truth documents (`docs/00-project/`, `docs/02-architecture/`, `docs/03-business-rules/`, `docs/07-modules/`).
- A change to behaviour starts with a documentation change, or a reference to the existing section it implements.
- If the documents conflict or are silent, stop and ask; never invent a rule in code.
- Shown by: every pull request links the document section it implements.

### 2. Financial rules before financial features
Every calculation is specified (purpose, formula, inputs, dates, inclusions, rounding, missing data, worked example, edge cases) in `docs/03-business-rules/financial-calculations.md` before it is coded, and carries a rule version.
- Calculations live in Python domain code (`backend/app/domain/`) with exact decimal arithmetic, never in the UI and never in an LLM.
- A formula change needs owner approval, a new rule version and updated worked-example tests.
- Shown by: hand-verified tests in `backend/tests/test_calculations.py` and `test_reports.py`.

### 3. Database and tenant security before customer data
No real customer data (including anonymised pilot data) enters any environment until tenant isolation and database integrity controls are in place and their tests pass.
- Required: server-side membership checks, PostgreSQL Row Level Security forced on every tenant table, a non-superuser runtime role, insert-only audit log, immutable financial history.
- Any failure in `test_tenant_isolation.py` or `test_db_constraints.py` blocks all work until fixed.
- Before the first pilot data: the pre-staging security items in `docs/reviews/project-progress.md` must be closed and an external security review completed.

### 4. Automated tests before declaring completion
Work is not complete until automated tests for it exist and pass, and the exact results are reported.
- Required for every change: backend `pytest`, frontend type check and unit tests, and the Playwright end-to-end test when a user workflow changes.
- Never disable, skip or weaken a test to make a build pass. Never claim a test passed if it was not run.
- Synthetic test data must be labelled as synthetic and never presented as real-world validation.

### 5. Human approval before production deployment
Nothing is deployed to staging or production, and no production data is changed, without the product owner's explicit written approval for that specific release.
- AI agents may build, test and prepare releases. They may not deploy, merge to a release branch or run production migrations on their own initiative.
- Every approval is recorded in `docs/reviews/` with the date, approver and release identifier.
- Silence is not approval.

## Tool responsibilities

| Tool | Responsibility | Boundaries |
|---|---|---|
| **Claude Code** | Primary implementation and code review | Works on a branch, follows `CLAUDE.md`, opens a pull request with a completion report. Does not deploy. |
| **Codex** | Independent code review, testing and problem solving | Reviews every pull request it did not write, re-runs tests, checks financial rules and tenant isolation, and reports findings. Follows `AGENTS.md`. Does not approve its own work or deploy. |
| **GitHub** | Version control and change history | `main` holds reviewed work. Every change arrives by pull request; history is never rewritten on `main`. |
| **PostgreSQL** | Core financial data | Single source of truth for financial records. RLS forced on tenant tables; schema changes only via Alembic migrations. |
| **Python** | Financial calculations and forecasting | All balances, ageing, behaviour metrics and (Release 2) forecasts in `backend/app/domain/` using `decimal.Decimal`. |
| **Playwright** | End-to-end browser testing | `e2e/` covers the core workflows through the real UI; run before any release candidate. |

## Enforcement on GitHub
- `.github/workflows/ci.yml` runs on every pull request and on `main`: backend tests on PostgreSQL 16 with a non-superuser role, a migration round-trip and drift check, frontend type check, unit tests and production build, then the Playwright end-to-end test.
- `main` is protected: changes only by pull request, all CI jobs must pass, no force-pushes or deletion, and the rules apply to administrators too.
- Required approvals are set to 0 because every pull request is opened under the owner's GitHub account, and GitHub does not let an author approve their own pull request. Independent review is still required by this document; the reviewer records it on the pull request.

## Change workflow
1. **Document.** Update or cite the specification (principles 1 and 2).
2. **Implement.** Claude Code builds the change on a branch, with tests (principle 4).
3. **Self-check.** All test suites run; exact results are written in the pull request.
4. **Independent review.** Codex reviews the pull request: correctness, financial rules, tenant isolation, test quality. Findings are fixed or answered.
5. **Merge.** Only after the review is clean and the owner (or a delegate the owner names) agrees.
6. **Release.** Deployment only with the owner's explicit approval for that release (principle 5).

The author and the reviewer must be different: the tool that wrote a change never gives its final review.

## Phase handoff rule (owner instruction, 2026-11-27)
At the end of every phase, the agent asks the owner one question: **"What do I need from you?"**, with a specific list.
- **If the list is empty**, the agent continues to the next phase without waiting.
- **If the list has items**, the agent asks for exactly those and continues with any work that doesn't depend on them.
- Items that always need the owner: approval gates in the master build instruction, changes to financial rules, provider or spending choices, real data, and any deployment (principle 5). Silence is still not approval for these.
