# Infrastructure specification

## Status
Proposed baseline. Choose providers only after comparing total cost, data residency, security controls, support and exit options.

## Environments
- Local: developer machines with synthetic data.
- Development: shared integration environment.
- Staging: production-like configuration with synthetic or anonymised data.
- Production: isolated accounts, secrets, database and storage.

No environment may share production credentials or unrestricted production data.

## Application hosting
Host the web frontend and API on managed services initially. Prefer a simple deployment model with health checks, automated builds and rollback. Avoid Kubernetes and complex orchestration for the MVP unless a documented requirement emerges.

## Database
- PostgreSQL managed service.
- Private network access where available.
- Automated backups and point-in-time recovery if supported.
- Encrypted connections and storage.
- Connection pooling and migration process.
- Separate database credentials for application runtime and migrations.
- Never expose the production database publicly without strict network controls.

## File storage
- Private object bucket.
- Block public access.
- Short-lived signed download URLs only after backend authorization.
- Validate file type, size and content.
- Malware scanning before processing where practical.
- Retention and deletion rules documented.
- Store file metadata and tenant ownership in PostgreSQL.

## Background processing
Use a worker queue for large imports, parsing, reconciliation suggestions and report generation. Jobs must:
- carry organisation context
- be idempotent or safely retryable
- record status and failure reason
- avoid leaking tenant data in logs
- have bounded retries and dead-letter handling

## Secrets and configuration
- Store secrets in the hosting provider's secret manager.
- Keep `.env` files out of version control.
- Commit `.env.example` with names and placeholder values only.
- Rotate credentials and restrict access.
- Never place secrets in prompts, logs or client-side bundles.

## Monitoring
Monitor:
- API availability and latency
- worker queue depth and failures
- database health and storage
- import success and rejection rates
- authentication failures and suspicious access
- backup completion
- application exceptions

Do not log full financial documents or unnecessary personal data.

## Backup and recovery
Define and test:
- Recovery Point Objective (RPO): maximum acceptable data loss.
- Recovery Time Objective (RTO): maximum acceptable restoration time.
- Backup frequency and retention.
- Restore procedure and responsible role.
- Periodic restore drills.
Initial RPO/RTO targets must be approved before production launch; do not invent that recovery is guaranteed without a tested process.

## Deployment controls
- Automated tests and static checks must pass.
- Database migrations reviewed before release.
- Staging smoke test completed.
- Backup status checked before risky migrations.
- Rollback plan documented.
- Production deployment requires explicit approval.

---

## Phase 3 provider evaluation — AWAITING OWNER APPROVAL

**No provider has been selected or purchased.** The application is provider-neutral (PostgreSQL, a Python web process, a Node web process, a private file store, an email sender), so any of the options below can run it.

> **Price status:** every figure below is an **unverified estimate** from general market knowledge as of mid-2026. None was checked against a provider's current price list. Verify each before approval; prices, free tiers and regions change often.

### Options compared
| Need | Option A: managed PaaS (lowest effort) | Option B: single VPS (lowest cost) | Option C: AWS Sydney (most control) |
|---|---|---|---|
| Web + API hosting | Render / Railway / Fly.io web services | One VPS (e.g. Hetzner, DigitalOcean) running both behind Caddy/Nginx | ECS Fargate or App Runner |
| PostgreSQL | Provider-managed Postgres, or Neon / Supabase | Same VPS (self-managed) or a small managed DB | RDS PostgreSQL |
| Object storage | Cloudflare R2 / Backblaze B2 | Same | S3 |
| Email | Postmark / Amazon SES / Resend | Same | SES |
| Errors and logs | Sentry free tier + provider logs | Sentry + journald | CloudWatch + Sentry |
| Backups | Provider PITR (plan-dependent) | You must script and test `pg_dump` + offsite copies | RDS automated backups + PITR |
| Data residency (AU) | Varies by provider; some have Sydney regions | Depends on the VPS location chosen | Sydney region available |
| Maintenance burden | Low | **High** (OS patching, DB backups, security are on you) | Medium–high |
| Lock-in | Low–medium | Low | Medium |
| **Unverified est. monthly, dev + staging + prod** | ~USD 40–120 | ~USD 15–50 | ~USD 150–400 |

### Recommendation (for discussion, not a decision)
**Option A with an Australian or Singapore region**, Neon or the PaaS's managed Postgres with point-in-time recovery, Cloudflare R2 for files, and Postmark or SES for email. Reasons: affordable to run from Nepal, low operational burden for a small team, real backups without building them yourself, and easy to move later because nothing is provider-specific. Option B is cheaper but puts backup and security operations on you, which is risky for financial data.

### Decisions needed from the owner before staging
1. Provider set (A, B, C or other) and region (data residency for Australian customers).
2. Email provider.
3. RPO/RTO targets (suggested starting point: RPO 24 h with daily backups plus PITR where available; RTO 8 h).
4. Monthly budget ceiling.
