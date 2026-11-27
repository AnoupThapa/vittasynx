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
