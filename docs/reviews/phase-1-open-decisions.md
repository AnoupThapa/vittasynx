# Phase 1 — Open decisions for product-owner approval

- **Status:** AWAITING APPROVAL
- **Date:** 2026-11-27
- **Related:** `docs/reviews/phase-1-document-review.md`

Silence is not approval. For each decision, reply with **Approve recommendation**, **Choose option X** or **Change**, plus any notes. Nothing below takes effect until you approve it, and approved decisions are then written into the source-of-truth documents.

---

## 1. Quick-answer sheet

**Gate** = must be decided before Phase 2 starts (per the master instruction's Phase 1 gate).

| ID | Decision | Recommendation | Gate |
|---|---|---|---|
| D-01 | Product name | Keep "TradeFlow Intelligence" for the product; "Vittasynx" as the company/repo, unless you prefer otherwise | — |
| D-02 | Is the cash forecast in the first release? | No. Release 1 = Receivables; Release 2 = Forecast | **Gate: scope** |
| D-03 | User roles and permissions | Five roles + the matrix in §D-03; no support-staff access in Release 1 | **Gate: roles** |
| D-04 | Suppliers in Release 1? | No, move to Release 2 | **Gate: scope** |
| D-05 | Exports and alerts in Release 1? | CSV export of invoice register, ageing and customer balances: yes. Alerts: no | **Gate: scope** |
| D-06 | Tax basis of receivables | Tax-inclusive (gross amount owed); tax stored separately | **Gate: receivables method** |
| D-07 | Currency and rounding | One currency per organisation; reject foreign-currency rows; `NUMERIC(19,4)`; reject over-precision; round half-up at display/export only | **Gate: currency & rounding** |
| D-08 | Balance source of truth and credit notes | The product calculates from its own allocations; credit notes are allocated like payments | **Gate: invoice & payment rules** |
| D-09 | Duplicates and re-imports | Identity = organisation + customer + invoice number; changed re-imports go to a review queue as amendments | **Gate: invoice & payment rules** |
| D-10 | Overpayments and credit balances | Allocation is capped; excess stays unapplied; shown separately, never netted silently | **Gate: invoice & payment rules** |
| D-11 | Ageing and reporting-date rules | Point-in-time as at reporting date; inclusive buckets; missing due date = validation error | **Gate: receivables method** |
| D-12 | Write-offs | Out of Release 1; use a credit note with reason "write-off" | Gate: invoice rules |
| D-13 | Payment behaviour metrics | Formulas in §D-13; minimum 6 fully paid invoices over ≥ 90 days | **Gate: receivables method** |
| D-14 | DSO | Defer to after pilot | Gate: receivables method |
| D-15 | Customer matching on import | Match by customer code, else exact normalised name; new customers need confirmation | **Gate: invoice rules** |
| D-16 | Timezone and business dates | Each organisation sets a timezone; dates stored as dates | Gate: receivables method |
| D-17 | Invoice statuses | Closed list in §D-17 | **Gate: invoice rules** |
| D-18 | MFA | Required for Owner and Administrator | — (Phase 3/4) |
| D-19 | AI in Release 1 | None; match suggestions use deterministic rules | — (Phase 3) |
| D-20 | Data retention defaults | Proposal in §D-20; needs legal review before pilot | Before any sample data (Phase 2) |
| D-21 | Bank CSV scope | Import receipts only; ignore outflows (logged as skipped) | Gate: payment rules |
| D-22 | Users in multiple organisations | Allowed from the start | — (Phase 4) |
| D-23 | MVP acceptance criteria | Approve the revised Release 1 criteria in §D-23 | **Gate: acceptance criteria** |
| R-01 | Store the master build instruction in the repo | Yes, as `docs/00-project/master-build-instruction.md` | — |

---

## 2. Decision details

### D-01 — Product name
The repo and Project are "Vittasynx"; all docs say "TradeFlow Intelligence". A name used in the code (package names, database names, domain) is costly to change later.
- **A.** Product = TradeFlow Intelligence; Vittasynx = company/repo name. *(Recommended for now)*
- **B.** Rename the product to Vittasynx everywhere.
- **C.** Undecided. Use a neutral code name (`tradeflow`) in code until branding is settled.

Note: trademark and domain availability haven't been checked for either name.

### D-02 — First-release scope (cash forecast)
The existing docs include the 13-week forecast in the MVP; the master instruction defers it.
- **A.** Release 1 = Receivables (scope items 1–9, 11 (receivables part), 12 (partial, see D-05), 13). Release 2 = Forecast. *(Recommended)*
- **B.** Keep the forecast in the MVP, as currently written.

*Consequence of A:* a smaller first build that can be validated sooner; forecasting is built on reconciled receivables data. Five docs need updating (review §11).

### D-03 — Roles and permissions
Proposed matrix (✔ = allowed, — = not allowed, all enforced by the backend):

| Action | Owner | Admin | Finance Mgr | AR Officer | Read-only |
|---|---|---|---|---|---|
| View dashboard, invoices, customers, payments | ✔ | ✔ | ✔ | ✔ | ✔ |
| Export reports | ✔ | ✔ | ✔ | ✔ | — |
| Create/edit customers | ✔ | ✔ | ✔ | ✔ | — |
| Upload and map an import | ✔ | ✔ | ✔ | ✔ | — |
| Confirm (commit) an import | ✔ | ✔ | ✔ | ✔ | — |
| Approve a source amendment to an existing invoice (D-09) | ✔ | ✔ | ✔ | — | — |
| Record manual payment | ✔ | ✔ | ✔ | ✔ | — |
| Confirm allocation | ✔ | ✔ | ✔ | ✔ | — |
| Reverse a confirmed allocation | ✔ | ✔ | ✔ | — | — |
| Issue/record credit note | ✔ | ✔ | ✔ | — | — |
| View audit log | ✔ | ✔ | ✔ | — | — |
| Invite/remove users, change roles | ✔ | ✔ | — | — | — |
| Organisation settings (timezone, currency at setup) | ✔ | ✔ | — | — | — |
| Transfer ownership, delete organisation, billing | ✔ | — | — | — | — |

- An Admin cannot remove or demote the Owner. There is always exactly one Owner.
- **Support staff:** no access to tenant data in Release 1. Revisit with a time-limited, audited, customer-approved access design.
- *Question for you:* should the AR Officer be able to confirm imports, or only prepare them for a Finance Manager to confirm? Recommendation: allowed, because small teams often have one finance person. Some customers may want maker-checker controls; that would be an organisation setting later.

### D-04 — Suppliers
Suppliers only matter for outflows in the forecast.
- **A.** Move to Release 2. *(Recommended)*
- **B.** Keep basic supplier records in Release 1 with no use yet.

### D-05 — Exports and alerts
- **Exports:** CSV/XLSX export of the invoice register, ageing report and customer balances, each stamped with the reporting date and organisation. *(Recommended for Release 1: needed for the Phase 6 reconciliation and for user trust.)*
- **Alerts:** defer to after pilot. Without validation evidence it's unclear which alerts are useful. *(Recommended)*
- Sending reminder or statement emails to debtors stays **out of scope**. It is money-adjacent communication on the customer's behalf.

### D-06 — Tax basis
- **A.** Receivables are **tax-inclusive** (the gross amount the debtor must pay). The import accepts the gross total; tax amount is optional and informational. *(Recommended: it matches what customers owe and what payments clear.)*
- **B.** Tax-exclusive, with tax tracked separately.

If an import supplies only net + tax, gross = net + tax, calculated in the backend and recorded as derived, with both source values kept.

### D-07 — Currency and rounding
1. **Currency:** each organisation has one reporting currency (e.g. AUD or NPR), set at creation. Rows in other currencies are **rejected with a clear reason** in Release 1; multi-currency is a future decision. *(Recommended)* Alternative: import but exclude them from totals, which is confusing, so not recommended.
2. **Storage:** `NUMERIC(19,4)` plus an ISO 4217 code on every monetary value.
3. **Input precision:** values with more decimals than the currency allows (AUD and NPR both use 2) are **flagged as validation errors**, never silently rounded.
4. **Calculation:** exact decimal; no intermediate rounding (amounts are already at currency precision, so sums stay exact).
5. **Rounding mode** where rounding is unavoidable (derived gross from net + tax, averages in behaviour metrics): **ROUND_HALF_UP** (common in accounting exports). Alternative: ROUND_HALF_EVEN (banker's). Please choose.
6. **Day-count metrics** (average days late etc.) are shown to one decimal place.

### D-08 — Source of truth for balances; credit notes
- Balances are **calculated by TradeFlow** from original amount − confirmed payment allocations − confirmed credit allocations. *(Recommended)*
- If an import includes an "amount due" or "amount paid" column, it is stored as a **source-reported reference** and differences are shown as reconciliation flags, never used as the balance.
- **Credit notes** are separate records allocated to one or more invoices (same controls as payments: capped, confirmed, reversible, audited). A credit note that names an invoice gets a *suggested* allocation that still needs confirmation. Unallocated credit sits at customer level, outside the ageing buckets.
- *Alternative:* trust the accounting system's amount due. That is simpler, but it makes TradeFlow a viewer of another system's numbers and breaks the allocation features.

### D-09 — Duplicates and re-imports
1. **File-level:** a SHA-256 hash of an uploaded file. The same file uploaded again triggers a warning; the user can cancel or proceed (proceeding still goes through row-level checks).
2. **Invoice identity:** organisation + customer + normalised invoice number.
3. On re-import:
   - Identical row → skipped as "already imported" (reported in the summary).
   - Same identity, changed fields → **amendment candidate**. A Finance Manager or above reviews and accepts or rejects it. Accepting creates a new version and keeps the original and the source rows. Accepted amendments to the amount are blocked if they would push the balance below confirmed allocations; the user must reverse allocations first.
   - Same invoice number, different customer → flagged as a possible duplicate, never merged automatically.
4. **Payment duplicates:** same organisation + date + amount + reference (+ bank account if present) is flagged as a duplicate candidate.

### D-10 — Overpayments and credit balances
- An allocation can never exceed the remaining invoice balance or the remaining payment amount. *(Already in rules.md)*
- The excess stays as an **unapplied payment** on the customer.
- The dashboard shows **Total outstanding receivables** (sum of positive invoice balances) and, separately, **Unapplied payments and credits**. An optional "Net position" = outstanding − unapplied is labelled clearly as net.
- A negative invoice balance should be unreachable. If it ever happens (e.g. a data error), the invoice is flagged as an exception, excluded from ageing and shown for review. It is never clamped to zero.

### D-11 — Ageing and reporting-date rules
1. **Reporting date R** defaults to today in the organisation's timezone (D-16) and is always shown on screen and in exports.
2. **As-at R:** include invoices with issue date ≤ R; include payment and credit allocations whose **effective date** (payment date / credit note date) ≤ R and that were confirmed and not reversed *as at the time the report is run*. A reversed allocation is excluded from all reports, including back-dated ones. The report states the run time so it can be reproduced.
3. **Days past due** = R − due date (in days). ≤ 0 → Current.
4. **Buckets (inclusive):** Current (≤ 0), 1–30, 31–60, 61–90, 91+.
5. **Missing due date:** a validation error at import (row excluded until corrected). *Alternative:* derive it from customer payment terms, but that requires adding terms to the customer record. Not recommended for Release 1.
6. **Due date before issue date:** a validation error.
7. Ageing totals must equal the sum of positive invoice balances as at R (acceptance test).

### D-12 — Write-offs
- **A.** Out of Release 1. Record a credit note with reason "write-off" when needed; it stays auditable. *(Recommended)*
- **B.** A dedicated write-off workflow with approval.

### D-13 — Customer payment behaviour metrics
Only **fully paid** invoices with valid issue and due dates, not cancelled or disputed, in a defined observation window (default the last 12 months, as at R).

| Metric | Formula |
|---|---|
| Days to payment (per invoice) | Final settlement date − issue date |
| Days late (per invoice) | max(0, final settlement date − due date) |
| Average days to payment | Mean over qualifying invoices |
| Average days late | Mean over qualifying invoices |
| On-time % | Invoices settled on or before the due date ÷ qualifying invoices |
| Payment frequency | Count of distinct payment dates per month in the window |
| Sample | Number of qualifying invoices, observation start/end |

- **Final settlement date** = the effective date of the allocation that brings the balance to zero (partial payments count toward it).
- **Unweighted** means (each invoice counts once). An amount-weighted variant could follow later.
- **Minimum sample:** ≥ 6 qualifying invoices spanning ≥ 90 days; otherwise show "Insufficient data (n = X)". Please confirm or set your own threshold.
- **No scores, grades or colours implying creditworthiness** in Release 1.
- Open invoices are excluded (this is a known bias towards customers who eventually paid). The limitation will be shown on screen.

### D-14 — DSO
- **A.** Defer until after pilot; it needs a defined credit-sales period and opening balances that the import may not provide. *(Recommended)*
- **B.** Include, with the definitions in `financial-calculations.md` completed.

### D-15 — Customer matching on import
1. If the file has a customer code/ID column, match on (organisation + code).
2. Else, match on exact name after normalisation (trim, case-fold, collapse spaces). No fuzzy auto-matching.
3. Unknown customers are listed in the import preview; the user confirms "create new" or maps each one to an existing customer.
4. Near matches (e.g. "ABC Pty Ltd" vs "ABC Pty. Ltd.") are **suggested**, never applied automatically.

### D-16 — Timezone and business dates
Each organisation sets an IANA timezone (e.g. `Australia/Sydney`, `Asia/Kathmandu`). Invoice, due and payment dates are stored as calendar dates with no time; the default reporting date and "today" use the organisation's timezone. *(Recommended)*

### D-17 — Invoice statuses
| Status | Counts in receivables? | Notes |
|---|---|---|
| Open | Yes | Default after import |
| Paid | Yes (balance 0) | **Derived** by the system when balance = 0, never imported as truth |
| Disputed | Yes, flagged | Shown in ageing with a marker; excluded from behaviour metrics |
| Cancelled / Void | No | Kept for history; any allocations must be reversed first |

Draft invoices are rejected at import. Imported status text (e.g. Xero's "AUTHORISED") is mapped to these values during column mapping.

### D-18 — MFA
Required for Owner and Administrator; optional for other roles. *(Recommended)* Final implementation depends on the authentication provider chosen in Phase 3.

### D-19 — AI in Release 1
- **A.** No AI processing of customer financial data in Release 1. Payment match suggestions use deterministic rules (customer + amount + reference/invoice number in the narration). *(Recommended: avoids the provider review in `data-privacy.md`, and matching quality can be measured first.)*
- **B.** Allow AI-assisted match suggestions after a provider review, with provenance and confidence recorded and confirmation mandatory.

Either way, update `CLAUDE.md` to reflect the decision.

### D-20 — Data retention defaults (proposal; subject to legal review)
| Data | Proposed default |
|---|---|
| Uploaded source files | Kept while the organisation is active, plus 90 days after account closure |
| Imported rows and financial records | Same as above |
| Audit events | 7 years (aligns with common AU record-keeping periods; to be confirmed by legal review for AU and Nepal) |
| Backups | Rolling 35 days |
| Phase 2 validation sample data | Deleted when the validation report is finalised, unless the provider consents in writing to keep it as test fixtures |

### D-21 — Bank CSV scope
Import credit (incoming) transactions as candidate receipts; debit transactions are skipped and counted in the import summary. A bank receipt becomes a **payment** only when the user confirms it is a customer payment, so transfers between own accounts, refunds and so on don't pollute receivables. *(Recommended)*

### D-22 — Users in multiple organisations
Allowed from the start; access is always derived from explicit membership; the active organisation is chosen in the UI and re-verified by the backend on every request. *(Recommended; important for accountants and advisors.)*

### D-23 — Release 1 acceptance criteria
Approve the existing Import, Receivables, Payment allocation and Security criteria in `acceptance-criteria.md`, **plus**:
- Re-importing a changed invoice creates an amendment candidate, never a silent overwrite or duplicate.
- Every dashboard figure shows the reporting date and reconciles to the invoice-level balances.
- Unapplied payments and credits are shown separately from outstanding receivables.
- Behaviour metrics show the sample size and period, and display "Insufficient data" below the threshold.
- Foreign-currency and over-precision rows are rejected with actionable reasons.
- Exports match on-screen totals for the same reporting date.
- Cash forecast criteria are moved to a Release 2 section.

### R-01 — Store the master instruction
Commit the master build instruction to `docs/00-project/master-build-instruction.md` so that it is versioned with the other source-of-truth documents. *(Recommended)*

---

## 3. How to respond

The quickest reply is something like:

> "Approve all recommendations, except D-07 rounding = HALF_EVEN and D-13 minimum = 10 invoices."

Once you reply, I'll record the decisions, update the affected docs (review §11), set Phase 1 to APPROVED, and only then begin Phase 2 (business validation materials).
