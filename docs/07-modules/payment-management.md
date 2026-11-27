# Payment management

**Status:** Built (Release 1). Tests: `backend/tests/test_allocations.py` (14 tests).

- Manual payment entry (AR Officer+), payment CSV import, bank CSV import (receipts only).
- Unassigned bank receipts must be assigned to a customer before allocation; the customer can change only while nothing is allocated.
- Duplicate protection: same date + amount + reference (+ bank description) is rejected (manual) or flagged (import).
- Credit notes: recorded manually (Finance Manager+) or imported; allocated to invoices exactly like payments.
- Every payment and credit shows amount, allocated and unapplied.
