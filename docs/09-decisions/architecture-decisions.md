# Architecture decision record

Record each material decision using this template.

## ADR-000: [Decision title]
- Status: Proposed / Accepted / Superseded
- Date:
- Owner:
- Context:
- Decision:
- Alternatives considered:
- Consequences:
- Security and privacy impact:
- Cost and operational impact:
- Review trigger:

## Initial decisions to resolve
1. Hosting provider and deployment region.
2. Authentication provider and MFA approach.
3. PostgreSQL provider and backup/PITR plan.
4. Object storage provider and retention.
5. Background worker and queue technology.
6. Supported import formats and canonical templates.
7. Initial reporting currency and currency expansion plan.
8. Data retention and deletion policy.
9. AI provider and whether any customer data may be processed by it.

Do not mark a decision accepted until the owner has reviewed cost, security, operational burden and exit options.


---

## Recorded decisions (2026-11-27)

### ADR-001: Modular monolith
- Status: Accepted (approved stack; master instruction §3)
- Decision: one FastAPI service with domain, service and API layers; one Next.js web app.
- Consequences: simple deployment; modules can be split later if measured need arises.

### ADR-002: PostgreSQL Row Level Security as a second tenant barrier
- Status: Accepted (multi-tenancy.md asked for evaluation; implemented)
- Decision: FORCE RLS on all tenant tables keyed on a transaction-local `app.current_org`, set only after membership checks.
- Alternatives: application filtering only. Rejected: a single missed filter would leak data.
- Consequences: queries without tenant context return nothing (fail closed). Requires a non-superuser runtime role.
- Review trigger: connection pooling in transaction mode (PgBouncer) must keep `set_config(..., true)` semantics; it does, as the setting is transaction-local.

### ADR-003: Opaque server-side sessions with CSRF double-submit
- Status: Accepted
- Decision: random session token in an HttpOnly cookie, hashed at rest; CSRF header on writes; TOTP MFA (required for Owner/Admin by configuration).
- Alternatives: JWTs (harder to revoke); external identity provider (deferred to Phase 3 provider review).
- Consequences: immediate revocation (logout, password reset, member removal).
- Review trigger: if an external identity provider is approved, sessions can be issued after its login.

### ADR-004: Imports processed in-request for Release 1 (deviation from the worker-queue proposal)
- Status: Accepted provisionally; **owner to confirm**
- Context: architecture.md proposes a background worker. Release 1 imports are capped at 5 MB / 20,000 rows and validate in a few seconds.
- Decision: parse and validate synchronously; design is idempotent and tenant-scoped so it can move to a worker without changing behaviour.
- Consequences: no queue infrastructure to operate yet. Larger files need the worker.
- Review trigger: pilot files exceed the limits, or p95 validation time > 10 s.

### ADR-005: Deterministic match suggestions, no AI (D-19)
- Status: Accepted
- Decision: suggestions from invoice-number-in-reference, exact amount and oldest-due rules; always require confirmation.

### ADR-006: Calculations recomputed from records, not stored balances (TA-07)
- Status: Accepted for Release 1
- Consequences: every figure is reproducible from inputs; performance must be measured with pilot volumes.
- Review trigger: dashboard p95 > 2 s at pilot volumes.

### ADR-007: Exact money handling end-to-end
- Status: Accepted
- Decision: NUMERIC(19,4) in PostgreSQL, `decimal.Decimal` in Python, strings in JSON, string formatting in the browser. Floats are rejected at every boundary. Rounding ROUND_HALF_UP at explicit boundaries only.

### ADR-008: Hosting, database, storage, email, monitoring providers
- Status: **Proposed — awaiting owner approval** (see infrastructure.md §Phase 3 provider evaluation)
