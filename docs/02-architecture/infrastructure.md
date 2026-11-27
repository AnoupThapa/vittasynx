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
