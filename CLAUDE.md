# Claude Code project instructions

## Product context
Build Vittasynx, a multi-tenant SaaS for B2B wholesalers and distributors. Release 1 provides receivables intelligence. A transparent 13-week cash forecast follows in Release 2, only after the receivables module passes Phase 6 testing (see `docs/00-project/scope.md` and `docs/00-project/master-build-instruction.md`). This is financial operations software, not accounting software.

## Required reading
Before changing product behaviour or architecture, read:
- `README.md`
- `docs/00-project/vision.md`
- `docs/00-project/scope.md`
- `docs/00-project/product-requirements.md`
- Relevant architecture and business-rule documents

## Source of truth
- Product scope: `docs/00-project/scope.md`
- Requirements: `docs/00-project/product-requirements.md`
- Architecture: `docs/02-architecture/`
- Financial behaviour: `docs/03-business-rules/`
- Security: `docs/04-security/`
- Tests and acceptance: `docs/06-development/testing-strategy.md` and `docs/08-quality-assurance/`
If instructions conflict or are incomplete, explain the conflict and request a decision. Do not silently invent a rule.

## Non-negotiable financial integrity
- Use decimal arithmetic for monetary values. Never use binary floating-point for money.
- Keep source values, calculated values, assumptions and predictions distinguishable.
- Every material calculation must be reproducible and traceable to its inputs and rule version.
- Never silently alter, delete or overwrite imported financial records.
- Preserve original imported files and source-row references according to the retention policy.
- Do not label estimated collections as confirmed cash.
- Do not let an LLM calculate balances, forecast totals or make financial decisions.
- Uncertain payment matches require user review.
- Scenarios must not modify actual transactions.

## Security and privacy
- Enforce organisation/tenant scope on the server for every business-owned record.
- Never trust an organisation ID supplied by the browser as proof of access.
- Check tenant ownership before serving files, exports or reports.
- Do not expose one tenant's data to another tenant, including in logs, analytics or AI prompts.
- Never commit credentials, tokens, private keys or production data.
- Do not log full bank details, credentials or unnecessary personal information.
- Apply least-privilege access and audit sensitive administrative actions.

## Engineering standards
- Prefer small, maintainable modules and explicit interfaces.
- Validate all external input at system boundaries.
- Use database migrations for schema changes.
- Add tests with every behaviour change.
- Handle retries and duplicate jobs safely.
- Keep business rules out of UI components.
- Do not add dependencies without explaining the need and maintenance impact.
- Avoid premature microservices. Start with a modular monolith unless an approved decision says otherwise.

## AI use
Release 1 uses no AI processing of customer financial data (decision D-19). Payment match suggestions are deterministic rules. Any future AI use needs an approved provider review (`docs/04-security/data-privacy.md`).

When approved, AI may assist with document extraction, transaction description classification and plain-language explanations of already-calculated results.
AI must not:
- create or modify financial records without explicit user confirmation
- allocate uncertain payments automatically
- invent missing amounts, dates or counterparties
- change historical records
- approve credit, payments or other financial decisions
Every AI-derived field must carry provenance and a confidence/review state.

## Required workflow
1. Inspect the repository and read relevant documentation.
2. Summarise the task and identify affected modules.
3. State assumptions and propose a short implementation plan.
4. Implement the smallest complete change.
5. Add or update tests.
6. Run relevant tests and report exact results.
7. Review tenant isolation, permissions and financial integrity.
8. Update documentation, `CHANGELOG.md` and `docs/reviews/project-progress.md` where relevant.

Do not begin a broad rewrite when a focused change is sufficient.

## Prohibited shortcuts
- Do not disable, skip or weaken tests to make a build pass.
- Do not bypass authorization for convenience.
- Do not make destructive schema or data changes without an approved migration and backup plan.
- Do not silently change formulas or business rules.
- Do not claim tests passed if they were not run.
- Do not deploy to production or alter production data without explicit approval.

## Completion report
For each task report:
- What changed
- Files/modules affected
- Database or migration changes
- Tests run and exact outcome
- Security and tenant-isolation considerations
- Known limitations and follow-up work
