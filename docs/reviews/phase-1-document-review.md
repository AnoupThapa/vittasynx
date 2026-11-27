# Phase 1 — Document review and product confirmation

- **Status:** AWAITING APPROVAL
- **Date:** 2026-11-27
- **Reviewer:** Claude (lead architect role, per master build instruction)
- **Companion document:** `docs/reviews/phase-1-open-decisions.md`

## 0. Phase framing

**Objective.** Review all existing documentation, confirm the product and MVP boundaries, and surface every gap, conflict and assumption that needs a product-owner decision before business validation (Phase 2) begins.

**Documents reviewed (19).**

| Area | Files |
|---|---|
| Root | `README.md`, `CLAUDE.md`, `AGENTS.md` |
| Project | `docs/00-project/vision.md`, `scope.md`, `product-requirements.md` |
| Architecture | `docs/02-architecture/architecture.md`, `database.md`, `infrastructure.md`, `multi-tenancy.md` |
| Business rules | `docs/03-business-rules/rules.md`, `financial-calculations.md` |
| Security | `docs/04-security/security.md`, `data-privacy.md` |
| Testing / QA | `docs/06-development/testing-strategy.md`, `docs/08-quality-assurance/acceptance-criteria.md` |
| Decisions | `docs/09-decisions/architecture-decisions.md`, `assumptions.md`, `known-limitations.md` |

Also reviewed: the master build instruction supplied by the product owner on 2026-11-27, which is not yet stored in the repository (see R-01).

**Repository inspection.** The repository `AnoupThapa/vittasynx` contains one commit holding only the 19 Markdown files above. There is no application code, no database schema or migrations, no dependency manifests, no `.env.example`, no CI configuration and no test suite. Nothing was overwritten.

**Out of scope for this phase (per instruction):** application code, migrations, dependency installation and provider selection. None were done.

---

## 1. Product summary

TradeFlow Intelligence is a multi-tenant SaaS for small and medium inventory-led B2B wholesalers and distributors (roughly 5–50 employees) that sell on credit. It is financial operations intelligence, not accounting software. It reads exported invoice and payment data, then calculates deterministically in the backend and shows:

- what customers owe and how overdue it is (receivables and ageing),
- how each customer actually pays (observed payment behaviour),
- which receipts belong to which invoices (controlled payment allocation), and
- later, what cash is likely to arrive or leave over 13 weeks (forecasting).

Product principles that shape every later decision: accuracy before automation, evidence before assumptions, explainable calculations, tenant isolation by design, human review of uncertain matches, and starting narrow.

> **Naming note.** The repository and Project are called *Vittasynx*; every document calls the product *TradeFlow Intelligence*. See decision D-01.

---

## 2. Confirmed MVP scope

The master instruction narrows the existing `scope.md`. Until D-02 is decided, this review treats the **master instruction as the intended direction** and the existing docs as needing an update.

### 2a. Receivables MVP (proposed first release)

| # | Capability | Source |
|---|---|---|
| 1 | Authentication, organisation workspaces, membership | scope §1, master Ph4 A/B |
| 2 | Role-based access, enforced by the backend | scope §2, master Ph4 C |
| 3 | Tenant isolation (application layer, with RLS evaluated) | multi-tenancy.md, master Ph4 D |
| 4 | Customer master records | scope §3, master Ph5 M1 |
| 5 | CSV/XLSX invoice import with preview, mapping, validation, duplicate detection and error reporting | scope §4–5, master Ph5 M2 |
| 6 | Invoice register, credit notes, balances, ageing | scope §6, master Ph5 M3 |
| 7 | Payments (manual and bank CSV), controlled allocation, unapplied funds, reversal | scope §7–8, master Ph5 M4 |
| 8 | Receivables dashboard with an explicit reporting date | scope §11 (receivables part), master Ph5 M5 |
| 9 | Observed customer payment behaviour, suppressed when data is insufficient | scope §9, master Ph5 M6 |
| 10 | Audit history for imports, edits, allocations and settings | scope §13, rules §7 |

### 2b. Deferred to a later module (after the Phase 6 gate)

- Rolling 13-week cash forecast, scenarios, opening cash entries and forecast items (scope §10)
- The cash part of the dashboard (scope §11)
- Supplier obligations, if suppliers exist only to feed the forecast (scope §3; see D-04)

### 2c. Unclear (needs a decision)

- Exportable reports and operational alerts (scope §12). The acceptance criteria require "exports return consistent results", but the master instruction's Phase 5 doesn't mention exports or alerts (D-05).
- DSO. It is defined in `financial-calculations.md` but absent from the master instruction's dashboard list (D-14).

---

## 3. Explicitly excluded from the MVP

These come from `scope.md` and the master instruction, and the two agree:

- General ledger, bookkeeping, full accounting
- Payroll and tax filing
- Payment initiation or any money movement
- Inventory, purchase orders and warehouse management
- Lending, underwriting and credit bureau services
- Autonomous financial decisions
- Cross-company customer credit scoring or benchmarking
- Complex ERP integrations; MVP is CSV/XLSX only
- Multi-entity consolidation
- AI-generated financial calculations
- ERP expansion in any form (master §1)

**Gaps in the exclusion list.** Write-offs and bad-debt provisioning, multi-currency revaluation, and statement or dunning email sending aren't mentioned either way. See D-12 and D-05.

---

## 4. Target users and workflows

### 4a. Roles: a conflict between the documents

| Master instruction (Ph4 C) | `product-requirements.md` |
|---|---|
| Organisation Owner | Owner / business administrator *(one role)* |
| Administrator | *(merged into the above)* |
| Finance Manager | Finance manager |
| Accounts Receivable Officer | Accounts receivable officer |
| Read-only User | Read-only manager or advisor |

The master instruction has five roles; the requirements have four. Neither document has a **permission matrix** saying which role may import, confirm imports, edit customers, record payments, confirm or reverse allocations, manage users or change settings. Support-staff (platform operator) access is mentioned in `multi-tenancy.md` but isn't defined as a role. See D-03 and the proposed matrix in the decisions document.

### 4b. Core workflows (as implied by the docs)

1. **Onboard:** the owner creates an organisation, invites the finance team and assigns roles.
2. **Load receivables:** an AR officer uploads an invoice export (from Xero, MYOB, QuickBooks, Tally or a spreadsheet), maps columns, reviews errors and duplicates, and confirms.
3. **Load receipts:** the AR officer uploads a bank CSV or enters payments manually.
4. **Allocate:** the system suggests matches; a permitted user confirms, splits or leaves funds unapplied; reversals are audited.
5. **Review position:** the owner or finance manager opens the dashboard for a chosen reporting date, reviews ageing, the largest overdue customers and the oldest invoices.
6. **Investigate a customer:** open their invoice history, outstanding balance and observed payment behaviour.
7. **Repeat weekly:** re-import updated data. How updates to already-imported invoices are handled is undefined (D-09).

Workflow 7 is the riskiest gap. Real businesses re-export every week, and the docs don't say what happens when the same invoice comes back with a changed amount, status or due date.

---

## 5. Core financial operations

| Operation | Defined rule | Status |
|---|---|---|
| Outstanding balance | `I − P − C` (original − allocated payments − applicable credits) | Defined. Tax basis, credit application and negative results are open (D-06, D-08, D-10) |
| Overdue | Positive balance and due date < reporting date | Defined |
| Days past due | `max(0, reporting date − due date)` | Defined. Missing due date behaviour is open (D-11) |
| Ageing buckets | Current, 1–30, 31–60, 61–90, >90 | Labels defined; inclusive boundaries need confirming (D-11) |
| Payment allocation | Many-to-many; capped at payment available and invoice balance; unapplied remains visible; reversals audited | Defined. Overpayment and credit-balance handling is open (D-10) |
| Duplicate detection | "Flag candidates"; same file twice must not duplicate | Duplicate key is undefined (D-09) |
| Payment behaviour | Observed timing, sample size, observation period, suppressed if insufficient | Metric formulas and minimum sample are undefined (D-13) |
| DSO | Approximate formula with open questions | Undefined; recommended deferral (D-14) |
| Rounding | "Defined centrally" | Precision, mode and boundaries are undefined (D-07) |
| Currency | Single reporting currency in first release; currency code stored on every value | Foreign-currency rows are undefined (D-07) |

---

## 6. Financial calculation risks

| ID | Risk | Why it matters | Mitigation proposed |
|---|---|---|---|
| FR-01 | **Tax-inclusive vs tax-exclusive amounts are undefined.** | Balances, ageing totals and any later DSO differ by 10% (AU GST) or 13% (NP VAT) depending on basis. A mixed basis across imports silently corrupts totals. | D-06: receivables are tax-inclusive (the amount the customer owes); tax is stored separately for information only. |
| FR-02 | **Re-imports of changed invoices.** | "Never overwrite" combined with weekly re-exports means either duplicate invoices or silent overwrites, unless a versioning or amendment workflow exists. | D-09: an invoice identity key and an explicit "source amendment" review step that keeps history. |
| FR-03 | **Two sources of truth for payments.** Accounting exports often include *amount paid* / *amount due* columns, while the product also calculates balances from its own allocations. | The two can disagree; users won't know which to trust. | D-08: the product calculates from its own allocations; any imported "amount due" is stored only as a reconciliation reference and differences are flagged. |
| FR-04 | **Point-in-time vs current-state reporting.** The reporting date is explicit, but nothing says whether payments dated after it, or allocations created after it, are counted. | Back-dated reports would be irreproducible, and the "reproducible calculation" rule couldn't be met. | D-11: balances as at reporting date R include only invoices issued ≤ R and payments/credits effective ≤ R; allocation effective date = payment date. |
| FR-05 | **Overpayments and credit balances.** The formula says "classify, don't clamp"; payment rules say allocations can't exceed the invoice balance. | A negative balance is unreachable by allocation but reachable through credit notes or source amendments. Undefined classification means totals can be overstated. | D-10: allocations capped; excess stays as unapplied payment / customer credit, shown separately and never netted silently into "total outstanding". |
| FR-06 | **Credit notes not linked to an invoice.** | The `C` in `I − P − C` is ambiguous for customer-level credits; ageing can't place them. | D-08: a credit note is applied to invoices like a payment (allocated, audited); unapplied credits are shown at customer level, outside the ageing buckets. |
| FR-07 | **Rounding and precision.** | An imported `123.455` in a 2-decimal currency must be either rejected or rounded by a rule; silent rounding breaks the reconciliation required in Phase 6. | D-07: reject or flag values exceeding currency precision; store `NUMERIC(19,4)`, calculate at full precision, round only for display/export using banker's or half-up rounding (owner choice). |
| FR-08 | **Missing due dates.** | Ageing can't be calculated; defaulting silently would fabricate data. | D-11: a row without a due date is a validation error unless the owner approves deriving it from customer payment terms (which aren't currently in the data model). |
| FR-09 | **Customer identity on import.** | Name-based matching (e.g. "ABC Pty Ltd" vs "A.B.C. Pty Ltd") can merge two customers or split one, corrupting customer totals and behaviour metrics. | D-15: match on an external customer code where present; otherwise exact normalised name, with new customers created only after user confirmation. |
| FR-10 | **Behaviour metrics from thin data.** | "Average days late" from 3 invoices is misleading and could be read as a credit judgement. | D-13: a minimum sample (proposed ≥ 6 fully paid invoices over ≥ 90 days) and explicit formulas for partial payments. |
| FR-11 | **Business date vs timezone.** Timestamps are UTC, but "overdue" depends on the organisation's local date. | A Nepal (UTC+5:45) or Sydney (UTC+10/11) organisation could see an invoice flip to overdue a day early or late. | D-16: each organisation has a timezone; business dates are stored as dates (not timestamps); the default reporting date is "today" in the organisation's timezone. |
| FR-12 | **Cancelled/void/disputed status set is undefined.** | Exclusion rules can't be applied consistently across screens and exports. | D-17: a closed list of statuses with a defined effect on receivables. |
| FR-13 | **No write-off path.** | Uncollectable invoices stay overdue forever and distort ageing. | D-12: out of MVP; the workaround is a credit note with reason "write-off", which stays auditable. |

---

## 7. Security and privacy risks

| ID | Risk | Mitigation (already documented unless noted) |
|---|---|---|
| SR-01 | Cross-tenant data exposure through APIs, files, exports, caches, background jobs or logs | Documented thoroughly in `multi-tenancy.md`; release blocker. **Add:** tenant-scoped IDs must not be guessable (use UUIDs) and error messages must not reveal whether another tenant's record exists (return 404, not 403). |
| SR-02 | Uploaded files are untrusted (macro-enabled XLSX, CSV formula injection, zip bombs) | Partly documented in `security.md`. **Add:** neutralise leading `= + - @` in values written to any exported CSV/XLSX (CSV injection); cap decompressed size and row count. |
| SR-03 | Bank transaction CSVs contain account numbers, counterparty names and narrations | `security.md` forbids logging these. **Add:** a defined list of which bank fields are stored, and masking of account numbers in the UI. |
| SR-04 | Privileged roles (Owner/Admin) without MFA | `security.md` says "require MFA where supported"; the master says "where practical". **Decide** the MVP position (D-18). |
| SR-05 | Platform support staff access to tenant data | Mentioned but undefined. **Decide** whether support access exists in the MVP at all (D-03). |
| SR-06 | AI providers receiving customer financial data | `data-privacy.md` requires a provider review first. The master instruction allows AI "suggesting payment matches", which `CLAUDE.md` does not list. **Decide** whether the MVP uses AI at all (D-19). |
| SR-07 | Retention and deletion policy is referenced (source files, audit) but doesn't exist | **Decide** the default retention (D-20). Needed before any real (even anonymised) data arrives in Phase 2. |
| SR-08 | Legal basis for processing across Nepal and Australia | `data-privacy.md` requires legal review before commercial launch. Not a Phase 1 blocker, but it must happen before the pilot. Noted in the progress tracker. |
| SR-09 | Anonymisation of sample data in Phase 2 | No anonymisation procedure is defined. **Add** one in Phase 2 (`data-requirements.md`) before any sample data is received. |
| SR-10 | Audit log tampering | `rules.md` §7 says "not editable through normal workflows". **Add:** application DB role has INSERT-only rights on `audit_events`. |

---

## 8. Missing requirements

1. **Permission matrix** per role and action (D-03).
2. **Invoice status list** and the effect of each status (D-17).
3. **Canonical import templates** and the minimum required columns for invoices, credit notes, payments and bank transactions. Listed as an open decision in `architecture-decisions.md` #6.
4. **Duplicate detection keys** for invoices, payments and files (D-09).
5. **Source amendment workflow** for re-imported, changed records (D-09).
6. **Customer matching rules** during import (D-15).
7. **Customer payment terms.** Not in the data model, but needed if due dates are ever derived (D-11).
8. **Payment behaviour metric formulas and thresholds** (D-13).
9. **Point-in-time reporting rules** (D-11).
10. **Organisation timezone and business-date handling** (D-16).
11. **Rounding mode, precision and the boundaries where rounding happens** (D-07).
12. **Treatment of foreign-currency invoices** under a single-currency MVP (D-07).
13. **Retention and deletion policy** (D-20).
14. **Data anonymisation procedure** for validation datasets (Phase 2).
15. **Bank CSV scope.** Are outflows imported and ignored, or rejected? Is a bank transaction the same entity as a payment? (D-21)
16. **Performance and volume targets.** Deliberately deferred to after pilot measurement; acceptable.
17. **RPO/RTO targets.** Deliberately deferred to before production launch; acceptable.
18. **Accessibility standard** for the UI (e.g. WCAG 2.2 AA). Not mentioned anywhere.
19. **Changelog.** `CLAUDE.md` requires updating "documentation and changelog", but no `CHANGELOG.md` exists.
20. **Organisation deletion / offboarding** behaviour.

---

## 9. Conflicting documentation

| ID | Conflict | Documents | Recommendation |
|---|---|---|---|
| C-01 | **Cash forecast in or out of MVP.** The existing docs make the 13-week forecast an MVP feature; the master instruction defers it until after the receivables module passes Phase 6. | `README.md`, `CLAUDE.md` (product context), `scope.md` §10–11, `product-requirements.md`, `acceptance-criteria.md` vs master §1, Ph5, Ph6 | Adopt the master instruction: split the MVP into **Release 1 – Receivables** and **Release 2 – Cash forecast**. Update the five docs after approval (D-02). |
| C-02 | **Number of roles** (5 vs 4) | `product-requirements.md` vs master Ph4 C | Adopt five roles; Owner and Administrator differ only in billing/ownership transfer and deleting the organisation (D-03). |
| C-03 | **AI uses.** The master allows AI to suggest payment matches; `CLAUDE.md` doesn't list it; `data-privacy.md` requires provider approval. | master §3 vs `CLAUDE.md` AI section, `data-privacy.md` | MVP match suggestions are deterministic rules (amount + reference + customer); no AI processing of customer data in Release 1 (D-19). |
| C-04 | **Multi-organisation membership.** Requirements say a user "can belong to one or more organisations"; the master says "where approved". | `product-requirements.md` vs master Ph4 B | Allow it from the start; the cost is low if designed in, and high to retrofit (D-22). |
| C-05 | **Suppliers.** Supplier master records are in MVP scope, but the master's receivables modules don't use them. | `scope.md` §3 vs master Ph5 | Move suppliers to Release 2 with the forecast (D-04). |
| C-06 | **MFA strength:** "require where supported" vs "where practical" | `security.md` vs master Ph4 A | Require MFA for Owner and Administrator in Release 1 (D-18). |
| C-07 | **Test data.** The testing strategy says synthetic fixtures; the master also allows anonymised real data. | `testing-strategy.md` vs master Ph6 | Not truly contradictory. Use both, labelled; add the anonymisation procedure (SR-09). |
| C-08 | **Product name:** Vittasynx (repo/Project) vs TradeFlow Intelligence (all docs) | repo vs docs | Owner decision (D-01). |

---

## 10. Technical assumptions requiring approval

These aren't Phase 1 decisions, but they affect how rules are written, so they're listed for awareness. Provider selection waits for Phase 3.

| ID | Assumption | Impact if wrong |
|---|---|---|
| TA-01 | Money stored as PostgreSQL `NUMERIC(19,4)` with a separate ISO 4217 currency code | Precision or overflow problems; schema migration later |
| TA-02 | Business dates stored as `DATE`; event timestamps as `TIMESTAMPTZ` in UTC | Off-by-one overdue errors across timezones |
| TA-03 | Tenant-owned tables carry `organisation_id` directly (not only via a parent), so RLS and composite keys are simple | Harder tenant enforcement and RLS |
| TA-04 | Record IDs are UUIDs, not sequential integers | Enumeration risk across tenants |
| TA-05 | Imported rows are stored immutably (`import_rows`) and business records reference them | Loses traceability required by Phase 6 reconciliation |
| TA-06 | Corrections use reversal/amendment records, never `UPDATE` of financial amounts | Audit trail incomplete |
| TA-07 | Calculations are recomputed from records (not stored running balances) in Release 1; caching only with tenant-scoped keys | Performance at scale; revisit after pilot volumes |
| TA-08 | Python `decimal.Decimal` with an explicit context throughout domain services; JSON APIs send money as strings | Float leakage at API or frontend boundaries |
| TA-09 | One reporting currency per organisation, fixed at creation | Changing it later needs a migration path |

---

## 11. Recommended changes to existing documentation

To be applied **only after** the related decisions are approved:

1. **`scope.md`.** Split "Included" into Release 1 (Receivables) and Release 2 (Cash forecast & suppliers); move forecast, opening cash, scenarios and suppliers to Release 2; state the position on exports and alerts. *(D-02, D-04, D-05)*
2. **`README.md` and `CLAUDE.md` product context.** Replace "and a transparent 13-week cash forecast" with "followed by a 13-week cash forecast in a later release". *(D-02)*
3. **`product-requirements.md`.** Five roles plus a permission matrix; mark the cash forecast section as Release 2; add payment-behaviour metric definitions. *(D-03, D-13)*
4. **`rules.md`.** Add the invoice status list, duplicate keys, the source amendment workflow, credit note application, overpayment handling, the reporting-date rule, the organisation timezone and customer matching. *(D-08–D-11, D-15–D-17)*
5. **`financial-calculations.md`.** Fill in the calculation contract (all nine headings) for Outstanding balance, Ageing and each behaviour metric, with worked examples; add the rounding and precision section; mark DSO deferred. *(D-06, D-07, D-11, D-13, D-14)*
6. **`acceptance-criteria.md`.** Move the cash forecast criteria to a Release 2 section; add criteria for re-import amendments, the reporting date, credit balances and insufficient-data suppression.
7. **`database.md`.** Add `organisation_id` on every tenant table (TA-03), invoice versions/amendments, the `credit_note_allocations` entity and a customer external code.
8. **`data-privacy.md`.** Add the retention defaults and the anonymisation procedure. *(D-20)*
9. **`CLAUDE.md` AI section.** Align with the master instruction once D-19 is decided.
10. **`assumptions.md`.** Add A-07 (accounting exports include stable customer codes), A-08 (invoices are mostly single-currency) and A-09 (users re-import weekly rather than incrementally).
11. **New files.** Store the master build instruction as `docs/00-project/master-build-instruction.md` (R-01), and add `CHANGELOG.md`.

**R-01.** The master build instruction is currently only in chat. It governs the whole build, so it should be committed to the repository as a source-of-truth document. Recommendation: approve storing it as above.

---

## 12. End-of-phase report

- **Completed:** full review of 19 documents and the master instruction; repository inspection.
- **Files created:** `docs/reviews/phase-1-document-review.md`, `docs/reviews/phase-1-open-decisions.md`, `docs/reviews/project-progress.md`.
- **Files modified:** none. Recommended edits wait for approval.
- **Tests performed:** none applicable; no code exists.
- **Outstanding defects:** none (no implementation).
- **Unresolved decisions:** 23 decisions plus one repository recommendation (R-01); 14 of them are core gate items (see the decisions document).
- **Gate status:** **NOT PASSED — AWAITING APPROVAL.** Phase 2 will not start until the product owner explicitly approves the gate items in `phase-1-open-decisions.md` §1.
