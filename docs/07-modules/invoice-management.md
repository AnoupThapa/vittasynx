# Invoice management

**Status:** Built (Release 1).

- Register with filters (status, customer search, due-date range) and an explicit reporting date.
- Columns: original amount, payments allocated, credits allocated, balance, derived status, ageing bucket, and a "source differs" flag when the accounting export's amount due disagrees with the calculated balance.
- Detail: allocations (with reversal), immutable version history, audit history, tax/net/reference.
- Status changes (Finance Manager+): open ↔ disputed; open/disputed → cancelled or void (only with no confirmed allocations). A reason is required and audited.
- "Paid" and "Overdue" are derived from balances and dates, never stored or imported.
- Credit notes are separate records (see payment-management.md).
