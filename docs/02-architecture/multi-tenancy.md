# Multi-tenancy and organisation isolation

## Model
A platform contains organisations. Users access an organisation through an explicit membership with a role. Business records belong to exactly one organisation.

## Mandatory controls
- Every business-owned record is tenant-scoped.
- Backend derives authorised organisation access from the authenticated session and membership.
- Never trust a browser-supplied organisation ID without checking membership and permission.
- Every read, update, delete, export and file download checks tenant ownership.
- Background jobs carry and validate organisation context.
- Cache keys include tenant scope.
- Search indexes and analytics preserve tenant boundaries.
- Support staff access is restricted, justified and audited.

## Database protections
Use foreign keys and tenant-aware uniqueness constraints. Evaluate PostgreSQL Row Level Security as an additional safeguard, not a replacement for correct application authorization.

## Testing
Create automated tests proving:
- Organisation A cannot read Organisation B's records.
- Organisation A cannot modify or delete Organisation B's records.
- File and export URLs cannot bypass tenant checks.
- A user removed from an organisation loses access.
- Worker jobs cannot process records outside their authorised tenant context.
- Cached results cannot cross tenant boundaries.

Any tenant-isolation failure is a release blocker.
