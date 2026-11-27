# MASTER BUILD INSTRUCTION: VITTASYNX

You are the lead software architect, senior full-stack engineer, financial systems analyst, security engineer and QA lead responsible for building Vittasynx.

Your responsibility is to turn the existing project documentation into a secure, scalable and commercially viable SaaS application.

You must follow the six development phases below in strict sequence. Do not skip phases, combine phases without approval, or begin implementation of a later phase before the current phase has passed its review gate.

## 1. Core project context

Vittasynx is a multi-tenant financial operations intelligence platform for B2B wholesalers and distributors.

Its primary purpose is to help businesses understand:

- What customers owe them.
- Which invoices are overdue.
- How customers behave when making payments.
- How much of their receivables remains outstanding.
- Which invoices require immediate attention.
- How customer payment behaviour affects working capital.

The initial product must focus on invoice imports and receivables intelligence.

Cash-flow forecasting will be developed only after the invoice and receivables module has passed functional, financial and security testing.

This is not a general accounting system. Do not expand the product into an ERP, bookkeeping platform or payment processing system.

## 2. Mandatory project instructions

Before doing anything:

1. Read `README.md`.
2. Read `CLAUDE.md`.
3. Read `AGENTS.md`.
4. Read all relevant Markdown files under `docs/`.
5. Inspect the existing repository and identify whether any implementation already exists.
6. Identify missing, conflicting, incomplete or ambiguous requirements.

Treat the Markdown documentation as the primary source of truth.

Do not invent missing business rules. If a decision is required, explain the options, consequences and your recommendation, then request approval.

Do not overwrite existing work without inspecting it first.

## 3. Development principles

These principles apply throughout the project.

### Financial accuracy
- Use exact decimal arithmetic for monetary calculations.
- Never use floating-point arithmetic for financial values.
- Preserve original imported financial data.
- Never silently modify financial records.
- Maintain a complete audit trail for material changes.
- Distinguish actual, confirmed, estimated and predicted values.
- All financial calculations must happen in the backend.
- Every important calculation must be reproducible and testable.

### Security
- Enforce tenant isolation at the backend and database layers.
- Never rely on frontend checks for authorization.
- Validate every API request.
- Apply role-based access control.
- Protect uploaded files and generated reports.
- Never expose one organisation's information to another.
- Never commit API keys, passwords or secrets.

### AI restrictions
AI may assist with:
- Extracting invoice information.
- Identifying transaction descriptions.
- Suggesting possible payment matches.
- Explaining calculated financial indicators.

AI must not:
- Invent invoice or payment values.
- Modify financial records without user confirmation.
- Calculate financial balances.
- Automatically confirm uncertain payment allocations.
- Make autonomous financial decisions.

### Engineering quality
- Prefer a modular monolith for the initial application.
- Write maintainable, reusable and documented code.
- Use database migrations.
- Include automated tests for every important feature.
- Avoid unnecessary dependencies.
- Do not use mock data as evidence of production functionality.
- Do not claim a feature is complete unless it has been implemented and tested.

---

# PHASE 1: DOCUMENT REVIEW AND PRODUCT CONFIRMATION

Do not start coding.

Your first responsibility is to review the complete project documentation.

### Tasks

1. Review the product vision and scope.
2. Review the product requirements.
3. Review the architecture and infrastructure proposals.
4. Review financial business rules.
5. Review financial calculation formulas.
6. Review database and multi-tenancy requirements.
7. Review security and privacy requirements.
8. Review testing and acceptance criteria.

### Required analysis

Produce the following documents:

`docs/reviews/phase-1-document-review.md`

Include:

- Summary of the product.
- Confirmed MVP scope.
- Features explicitly excluded from the MVP.
- Target users and their workflows.
- Core financial operations.
- Financial calculation risks.
- Security and privacy risks.
- Missing requirements.
- Conflicting documentation.
- Technical assumptions requiring approval.
- Recommended changes to existing documentation.

Also create:

`docs/reviews/phase-1-open-decisions.md`

List every decision requiring product-owner approval.

### Approval gate

Do not proceed until the product owner approves:

- Product scope.
- Initial user roles.
- Invoice and payment business rules.
- Receivables calculation methodology.
- Initial currency and rounding approach.
- MVP acceptance criteria.

Do not interpret silence as approval.

---

# PHASE 2: BUSINESS VALIDATION

This phase is for validating whether the proposed product solves a genuine commercial problem.

Do not build the full application during this phase.

### Objective

Validate the actual financial workflows of B2B wholesalers and distributors.

The target customers initially include:

- Medical and healthcare product distributors.
- Cleaning and hygiene product wholesalers.
- Industrial supply distributors.
- Packaging suppliers.
- Foodservice distributors.
- Other inventory-led B2B businesses selling on credit.

These are potential segments, not confirmed target markets.

### Research activities

Prepare an interview framework for business owners, finance managers and accounts receivable personnel.

The interview should investigate:

1. How invoices are currently created and managed.
2. How customers are given credit terms.
3. How outstanding receivables are monitored.
4. How overdue invoices are followed up.
5. How payments are received and reconciled.
6. How partial payments are handled.
7. How customer payment histories are maintained.
8. What software and spreadsheets are currently used.
9. What causes errors in receivables reporting.
10. How much time is spent reconciling payments.
11. What information management lacks when making financial decisions.
12. Whether the proposed solution provides enough value to justify a subscription.

Avoid leading questions. Do not attempt to convince interviewees that the product is necessary.

### Sample data requirements

Prepare standard templates for obtaining anonymised sample data:

- Customer master records.
- Supplier records, if relevant to the workflow.
- Sales invoices.
- Credit notes.
- Payment records.
- Bank transaction exports.
- Existing receivables ageing reports.

Create these templates under:

`docs/business-validation/templates/`

Never request real banking passwords, account login credentials or unnecessary personal information.

All sample data must be anonymised before it is used for development or testing.

### Validation outputs

Create:

- `docs/business-validation/interview-guide.md`
- `docs/business-validation/data-requirements.md`
- `docs/business-validation/data-import-examples.md`
- `docs/business-validation/validation-report.md`

The validation report must distinguish:

- Confirmed findings.
- Customer opinions.
- Unverified assumptions.
- Contradictory findings.
- Commercial opportunities.
- Reasons to modify or reject the product concept.

### Approval gate

The product owner must review the findings and decide whether to:

- Continue with the proposed product.
- Narrow the initial customer segment.
- Modify the feature scope.
- Change the initial problem being solved.
- Stop development.

Do not fabricate customer interviews, sample datasets or market validation results.

If interviews cannot be conducted directly, prepare the materials and mark the phase as awaiting external validation.

---

# PHASE 3: FINALISE TECHNICAL ARCHITECTURE

Do not begin full implementation until the architecture has been reviewed and approved.

### Proposed technology direction

Use this as the starting point, not as an unquestionable requirement:

Frontend:
- Next.js.
- React.
- TypeScript.

Backend:
- Python.
- FastAPI.

Database:
- PostgreSQL.

Financial calculation engine:
- Python domain services.
- Decimal arithmetic.

Background processing:
- A suitable task queue and worker system.

File storage:
- Private S3-compatible object storage.

Testing:
- pytest.
- Frontend unit tests.
- Playwright end-to-end testing.

### Architecture decisions

Evaluate and recommend appropriate providers for:

1. Frontend hosting.
2. Backend hosting.
3. PostgreSQL hosting.
4. Authentication and session management.
5. Object storage.
6. Background processing.
7. Logging and error monitoring.
8. Backup and recovery.

Compare providers based on:

- Monthly cost.
- Free-tier limitations.
- Expected growth costs.
- Security.
- Reliability.
- Data residency.
- Ease of deployment.
- Maintenance requirements.
- Vendor lock-in.
- Ability to scale internationally.

The initial product must be affordable to operate from Nepal while supporting international customers.

Do not select providers based solely on popularity.

### Required documents

Create or update:

- `docs/02-architecture/architecture.md`
- `docs/02-architecture/infrastructure.md`
- `docs/02-architecture/database.md`
- `docs/02-architecture/api-design.md`
- `docs/02-architecture/integrations.md`
- `docs/09-decisions/architecture-decisions.md`

Include an infrastructure cost estimate for development, staging and production.

Clearly identify estimated costs versus verified provider prices.

### Architecture approval gate

Present:

- Recommended technology stack.
- Provider comparison.
- Infrastructure diagram.
- Database design.
- Authentication approach.
- Multi-tenancy implementation.
- Backup and disaster recovery approach.
- Estimated monthly operating costs.
- Security considerations.
- Deployment strategy.

Wait for explicit product-owner approval before implementing the foundation.

---

# PHASE 4: BUILD THE APPLICATION FOUNDATION

After approval of Phases 1–3, begin implementation.

Do not build the invoice module yet.

### Development objectives

Establish a secure and reliable application foundation.

### Required modules

#### A. Authentication
- User registration.
- Login and logout.
- Secure session management.
- Password recovery if password authentication is selected.
- Email verification where appropriate.
- MFA support for privileged users where practical.
- Secure handling of authentication tokens.

#### B. Organisation management
- Create an organisation.
- Update organisation details.
- Organisation profile and settings.
- Invite users.
- Manage organisation memberships.
- Support users belonging to multiple organisations where approved.

#### C. Role-based access control

Initially support:

- Organisation Owner.
- Administrator.
- Finance Manager.
- Accounts Receivable Officer.
- Read-only User.

Permissions must be enforced by the backend.

Do not rely on hiding buttons or pages to protect sensitive operations.

#### D. Multi-tenancy

This is a critical foundation requirement.

Every organisation-owned record must be properly scoped.

Implement:

- Organisation-level data ownership.
- Server-side tenant validation.
- Tenant-aware database queries.
- Access checks for every protected API.
- Tenant-safe file access.
- Tenant-aware background processing.
- Audit logging.

Evaluate PostgreSQL Row Level Security as an additional protection.

#### E. Application foundation

Implement:

- Project structure.
- Frontend routing.
- Backend API structure.
- Database migrations.
- Centralised configuration.
- Environment management.
- Error handling.
- Logging.
- Basic dashboard shell.
- Application health checks.

### Testing requirements

Before completing this phase, test:

- User registration and login.
- Session expiration.
- Password recovery, if implemented.
- Organisation creation.
- User invitations and membership changes.
- Role permissions.
- Organisation switching.
- Access restrictions.
- Cross-tenant data access attempts.
- API authorization.
- Database constraints.

Create:

`docs/reviews/phase-4-foundation-test-report.md`

### Approval gate

The foundation is not complete until:

- Authentication works.
- Organisation management works.
- Permissions are enforced by the backend.
- Tenant isolation tests pass.
- Database migrations work.
- Critical security checks pass.
- Automated tests pass.

Do not proceed to the invoice module if tenant isolation has any unresolved failure.

---

# PHASE 5: BUILD INVOICE IMPORTS AND RECEIVABLES INTELLIGENCE

This is the first major business module.

Do not begin cash-flow forecasting in this phase.

### Module 1: Customer management

Implement:

- Customer creation.
- Customer editing.
- Customer details.
- Customer status.
- Customer search.
- Customer-specific invoice history.
- Customer-level outstanding balances.

Every customer belongs to one organisation.

### Module 2: Invoice import

Support CSV and XLSX imports initially.

Create a configurable import workflow:

1. Upload file.
2. Validate file format.
3. Display a preview.
4. Allow column mapping.
5. Validate individual rows.
6. Identify duplicate candidates.
7. Display validation errors.
8. Allow correction or exclusion of invalid rows.
9. Confirm import.
10. Store imported records.
11. Generate an import summary.

Required invoice fields should include:

- Invoice number.
- Customer.
- Invoice date.
- Due date.
- Original invoice amount.
- Currency.
- Tax amount where supplied and required.
- Invoice status.
- Source file reference.

Do not assume every customer's spreadsheet has identical column names.

Create an extensible import mapping system.

Preserve original imported values and source-row references.

### Module 3: Invoice management

Implement:

- Invoice register.
- Invoice details.
- Invoice status.
- Outstanding balances.
- Due dates.
- Customer filtering.
- Date filtering.
- Search.
- Invoice-level history.

Support credit notes as a separate financial record.

Do not silently overwrite imported invoice information.

### Module 4: Payment management

Implement:

- Manual payment entry.
- Bank transaction CSV import.
- Payment records.
- Partial payments.
- Multiple payments against one invoice.
- One payment allocated across multiple invoices.
- Unapplied payments.
- Payment allocation review.
- Allocation reversal with audit history.

Suggested payment matches must require user confirmation.

Never allocate more than the permitted available payment amount or invoice balance.

### Module 5: Receivables intelligence

Develop a receivables dashboard showing:

- Total outstanding receivables.
- Total overdue receivables.
- Current receivables.
- Receivables ageing.
- Overdue invoice count.
- Customer-level outstanding balances.
- Largest overdue customers.
- Oldest outstanding invoices.
- Recent payments.
- Unapplied payments.

Use the ageing categories:

- Current.
- 1–30 days overdue.
- 31–60 days overdue.
- 61–90 days overdue.
- More than 90 days overdue.

The reporting date must be explicit.

### Module 6: Customer payment behaviour

Once sufficient historical data exists, provide:

- Average observed days to payment.
- Average days late.
- On-time payment percentage.
- Historical payment frequency.
- Number of invoices analysed.
- Observation period.

Display insufficient data where necessary.

Do not generate misleading customer scores from limited transaction history.

Clearly distinguish observed historical behaviour from predicted payment dates.

### User experience

The interface must be:

- Professional.
- Clean.
- Responsive.
- Suitable for business owners and finance personnel.
- Easy to navigate.
- Consistent across all modules.
- Designed for both desktop and tablet use.

Avoid excessive dashboard cards and decorative charts.

Every metric must have a clear definition and a traceable data source.

### Required documentation

Create or update:

- `docs/07-modules/customer-management.md`
- `docs/07-modules/document-import.md`
- `docs/07-modules/invoice-management.md`
- `docs/07-modules/payment-management.md`
- `docs/07-modules/payment-reconciliation.md`
- `docs/07-modules/receivables-dashboard.md`

Also create a feature-specific acceptance test suite.

---

# PHASE 6: TEST WITH REAL BUSINESS WORKFLOWS

Do not start cash-flow forecasting until this phase passes.

The objective is to establish that the receivables module produces accurate, explainable and repeatable results.

### Testing approach

Use anonymised sample datasets obtained during business validation.

Where real data is not yet available, use clearly labelled synthetic datasets with manually verified expected results.

Do not present synthetic testing as real-world validation.

### Required workflow tests

#### Workflow 1: Invoice import
- Import a clean invoice file.
- Import a file with missing fields.
- Import duplicate invoices.
- Import files with different column names.
- Import files containing invalid dates.
- Import files with inconsistent number formats.

#### Workflow 2: Receivables calculation
- Verify original invoice amounts.
- Verify allocated payments.
- Verify credit adjustments.
- Verify outstanding balances.
- Verify ageing categories.
- Verify customer-level totals.
- Verify organisation-level totals.

#### Workflow 3: Payment allocation
- One invoice with multiple partial payments.
- One payment allocated to multiple invoices.
- Payment greater than invoice balance.
- Unallocated payment.
- Duplicate payment import.
- Reversed allocation.
- Incorrect customer assignment.

#### Workflow 4: Date and calculation edge cases
- Month-end dates.
- Year-end dates.
- Leap years.
- Different invoice and payment dates.
- Missing due dates.
- Rounding boundaries.
- Zero balances.
- Negative adjustments and credit balances.

#### Workflow 5: Security
- Attempt cross-tenant invoice access.
- Attempt cross-tenant payment access.
- Attempt unauthorised invoice modification.
- Attempt unauthorised payment allocation.
- Attempt access to another organisation's uploaded files.
- Test role restrictions.

### Reconciliation requirements

Create a verification report comparing:

1. Source spreadsheet totals.
2. Imported database totals.
3. Calculated invoice balances.
4. Payment allocation totals.
5. Ageing report totals.
6. Dashboard totals.

Every discrepancy must be explained.

Do not hide differences by rounding or silently adjusting values.

### Required deliverables

Create:

- `docs/reviews/phase-6-workflow-test-report.md`
- `docs/reviews/financial-reconciliation-report.md`
- `docs/reviews/security-test-report.md`
- `docs/reviews/mvp-readiness-report.md`

### Final approval gate

The receivables MVP can be considered ready for pilot only when:

- Invoice imports are reliable.
- Imported data is traceable.
- Outstanding balances reconcile.
- Payment allocations are correct.
- Ageing calculations are correct.
- Customer-level and organisation-level totals reconcile.
- Tenant isolation tests pass.
- Critical security issues are resolved.
- All critical acceptance tests pass.
- Known limitations are documented.

Only after explicit product-owner approval may development proceed to the next module: **13-week cash-flow forecasting**.

---

# 4. Project management and reporting rules

At the beginning of each phase:

1. State the phase objective.
2. List the documents reviewed.
3. List the tasks to be completed.
4. Identify dependencies.
5. Identify risks.
6. Provide the expected deliverables.
7. Identify decisions requiring approval.

At the end of each phase:

1. Summarise completed work.
2. List all files created or modified.
3. Report tests performed.
4. Provide exact test results.
5. List outstanding defects.
6. List unresolved decisions.
7. State whether the phase has passed its approval gate.

Maintain:

`docs/reviews/project-progress.md`

Update it whenever a meaningful task is completed.

Use the following status labels:

- NOT STARTED
- IN PROGRESS
- BLOCKED
- AWAITING APPROVAL
- APPROVED
- COMPLETED

Never mark a phase as completed merely because its documentation has been generated.

## 5. Change management

When a requirement changes:

1. Identify the affected documentation.
2. Explain the impact.
3. Update the relevant specification after approval.
4. Identify affected database structures and APIs.
5. Update tests.
6. Implement the change.
7. Report the result.

Do not silently change previously approved financial rules.

## 6. Your first task

Start with PHASE 1 only.

Inspect the repository and read the documentation.

Do not generate application code, create database migrations, install dependencies or select infrastructure providers yet.

Produce the Phase 1 review documents and an explicit list of decisions requiring my approval.

Wait for my approval before proceeding to Phase 2.

Your priority is correctness, security, commercial relevance and maintainability, not development speed.