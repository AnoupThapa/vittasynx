# Security requirements

## Security baseline
- Enforce least privilege.
- Use secure authentication and session management.
- Require MFA for privileged roles where supported.
- Enforce tenant isolation server-side.
- Validate and sanitise external input.
- Protect against common web vulnerabilities.
- Encrypt traffic in transit and use provider encryption at rest.
- Keep dependencies patched and scan for known vulnerabilities.
- Maintain auditable administrative actions.

## Sensitive information
Collect only data needed for the product. Avoid storing bank credentials or payment-card data. Restrict access to uploaded statements and financial exports. Do not include sensitive transaction details in routine logs or AI prompts.

## File handling
Validate extension, MIME type, size and file structure. Treat uploaded files as untrusted. Store privately, scan where practical and parse in an isolated worker context. Do not execute macros or embedded content.

## Incident readiness
Define incident classification, escalation, containment, evidence preservation, customer communication and recovery procedures before production launch.

## Implemented controls (Release 1 + pre-launch hardening, 2026-11-27)
| Control | Implementation |
|---|---|
| Rate limiting | PostgreSQL-backed fixed windows (shared across instances): login 30/15 min per IP and 10/15 min per account; registration 10/h per IP; password reset 10/h per IP and 3/h per account; MFA verification 10/15 min per session; invitation acceptance 20/h per IP. `X-Forwarded-For` is trusted only when `VX_TRUST_FORWARDED_FOR=true` (set it only behind your own proxy). Emails in limiter keys are hashed. |
| Account lockout | 10 failed logins → 15-minute lock |
| MFA | TOTP; required for Owner/Admin. Ten single-use recovery codes issued on enrolment (stored as hashes); regenerating them requires a current authenticator code. |
| Email | `smtp` adapter (any provider) or development outbox. The outbox is refused in staging/production; message bodies (which contain tokens) are never logged. |
| File storage | `local` private directory or `database` (RLS-protected `file_blobs`) for hosts without persistent disk. |
| Database roles | `deploy/sql/roles.sql`: separate migration owner and restricted runtime role (no superuser, no BYPASSRLS, no DELETE on financial history). Verified: full end-to-end test passes running as the restricted role. |
