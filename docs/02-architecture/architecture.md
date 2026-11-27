# Application architecture

## Architectural style
Start as a modular monolith with clear domain boundaries. Do not introduce microservices until measured scale, team ownership or deployment constraints justify them.

## Proposed components
- Web client: Next.js, React and TypeScript.
- API: Python FastAPI.
- Relational database: PostgreSQL.
- Financial domain services: Python modules using decimal arithmetic.
- Background worker: imports, reconciliation suggestions and report generation.
- Private object storage: uploaded source files and generated exports.
- Authentication provider: select after evaluating cost, MFA, session security and data location.
- Observability: structured application logs, error tracking and service metrics.

## Domain modules
1. Identity and organisation membership
2. Customers and suppliers
3. Import and data validation
4. Invoices and credit notes
5. Payments and allocations
6. Receivables analytics
7. Cash-flow forecasting
8. Reporting and alerts
9. Audit events

## Layering
- UI handles presentation and user interaction.
- API handles authentication, authorization, validation and orchestration.
- Domain services enforce business rules and calculate financial values.
- Repositories persist and retrieve tenant-scoped records.
- Workers execute retryable background tasks.
- Integrations are isolated behind adapters.

## Financial calculation boundary
All monetary calculations occur in backend domain services. The frontend displays returned values. LLMs must never be the calculation engine.

## Data flow
1. User uploads a file.
2. API validates user and organisation access.
3. File is stored privately and linked to an import job.
4. Worker parses rows and validates them.
5. User reviews errors and duplicate candidates.
6. Confirmed records are committed with source references.
7. Domain services calculate balances and analytics.
8. UI displays results with data freshness and provenance.

## API conventions
- Version APIs from the start, for example `/api/v1`.
- Validate request and response schemas.
- Use consistent pagination and filtering.
- Return stable error codes.
- Make retryable write operations idempotent where appropriate.
- Never rely on client-side checks for authorization.

## Deployment model
Separate development, staging and production. Production data must not be copied into development or staging without an approved anonymisation process.
