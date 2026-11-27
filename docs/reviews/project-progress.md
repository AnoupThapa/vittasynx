# Project progress

Status labels: NOT STARTED · IN PROGRESS · BLOCKED · AWAITING APPROVAL · APPROVED · COMPLETED

A phase is never marked COMPLETED merely because its documents exist.

## Phase status

| Phase | Name | Status | Gate / what's outstanding | Last updated |
|---|---|---|---|---|
| 1 | Document review and product confirmation | **APPROVED** | Approved by owner 2026-11-27 (`phase-1-approval.md`) | 2026-11-27 |
| 2 | Business validation | **BLOCKED (awaiting external validation)** | Materials ready. No interviews done, no sample data received. Owner chose to build in parallel. | 2026-11-27 |
| 3 | Finalise technical architecture | **AWAITING APPROVAL** | Architecture documented as built. Provider selection, region, budget and RPO/RTO need an owner decision (ADR-008); ADR-004 (synchronous imports) needs confirmation. | 2026-11-27 |
| 4 | Application foundation | **AWAITING APPROVAL** | All automated gate checks pass (`phase-4-foundation-test-report.md`). Owner review outstanding. | 2026-11-27 |
| 5 | Invoice imports and receivables intelligence | **AWAITING APPROVAL** | Built; 151 backend tests and an 11-check browser test pass on synthetic data (`phase-5-receivables-test-report.md`). | 2026-11-27 |
| 6 | Real business workflow testing | NOT STARTED | Needs anonymised real data from Phase 2 | — |
| — | 13-week cash-flow forecasting (Release 2) | NOT STARTED | Only after Phase 6 approval | — |

## Log

### 2026-11-27
- Repository initialised with 19 specification documents (commit `d918d93`).
- Phase 1 review produced; 23 decisions raised (commit `1cc8859`).
- Owner approved all Phase 1 recommendations; product named **Vittasynx**; rounding HALF_UP and behaviour threshold (6 invoices / 90 days) applied as recommended defaults. Owner instructed: build the application.
- Phase 1 decisions applied to the source-of-truth documents; master build instruction stored in `docs/00-project/`.
- Phase 2 materials written (interview guide, data requirements and anonymisation procedure, import examples, 7 CSV templates, validation report marked awaiting validation).
- Phase 3 architecture, API design, integrations, database and ADR-001…008 documented; provider options compared with **unverified** cost estimates.
- Phase 4 foundation and Phase 5 receivables modules built (FastAPI + PostgreSQL RLS backend, Next.js frontend).
- Tests: 151 backend tests passed; frontend type check and 3 unit tests passed; production build succeeded; end-to-end browser test passed 11/11 checks.

### 2026-11-27 (later)
- Owner established five non-negotiable principles and tool responsibilities; recorded in `docs/00-project/engineering-principles.md` and wired into `CLAUDE.md`, `AGENTS.md`, `README.md` and a pull request template.

## Open items carried forward
- Owner decisions: hosting providers and region, email provider, budget, RPO/RTO (ADR-008); confirm synchronous imports (ADR-004).
- Before staging: rate limiting, MFA recovery codes, S3-compatible storage adapter, email provider adapter, split DB roles, external security review.
- Legal review of privacy obligations for Australia and Nepal (before pilot).
- Phase 2 interviews and anonymised sample data (feeds Phase 6).
