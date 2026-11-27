# Changelog

## Unreleased
### Added
- Engineering principles and tool responsibilities (`docs/00-project/engineering-principles.md`), referenced from `CLAUDE.md`, `AGENTS.md` and `README.md`.
- Pull request template enforcing the five principles and author ≠ reviewer.

## 0.1.0 — 2026-11-27 (Release 1 build, not deployed)

### Added
- Backend (FastAPI, PostgreSQL 16): authentication with server-side sessions, CSRF protection, account lockout, email verification, password reset and TOTP MFA (required for Owner/Admin); organisations, invitations, five roles with backend-enforced permissions; Row Level Security on all tenant tables; insert-only audit log.
- Receivables Release 1: customers; CSV/XLSX import of invoices, credit notes, payments and bank receipts with column mapping, validation, corrections, duplicate detection and amendment approval; invoice register and versions; payments and credit notes with controlled allocation, deterministic suggestions and reversal; dashboard with point-in-time ageing; observed customer payment behaviour; CSV exports.
- Frontend (Next.js): sign-in, registration, MFA, organisation switching and all Release 1 screens.
- Tests: 151 backend tests, 3 frontend unit tests, browser end-to-end smoke test.
- Documentation: Phase 1 approval, Phase 2 validation materials, Phase 3 architecture and ADRs, module specifications, Phase 4 and 5 test reports.

### Changed
- Product renamed from TradeFlow Intelligence to Vittasynx (decision D-01).
- MVP split into Release 1 (receivables) and Release 2 (cash forecast) (decision D-02).
