# Payment reconciliation (allocation)

**Status:** Built (Release 1).

## Rules (rules.md §3, §8.6)
- One payment → many invoices; one invoice ← many payments and credits.
- An allocation can never exceed the remaining payment/credit or the remaining invoice balance. Row locks (`SELECT … FOR UPDATE`) stop concurrent requests over-allocating; a test runs two simultaneous allocations to prove it.
- Payment and invoice must belong to the same customer and currency; cancelled/void invoices cannot receive allocations.
- Effective date of an allocation = payment/credit date (drives point-in-time balances).
- Allocations are never deleted or edited; they are **reversed** with a reason (Finance Manager+). The database refuses deletes and value changes.

## Suggestions (deterministic, D-19)
| Confidence | Rule |
|---|---|
| High | Invoice number appears in the payment reference / bank description |
| Medium | Remaining amount equals the invoice balance exactly |
| Low | Other open invoices for the customer, oldest due first |
Suggestions are displayed only; each one needs a user's confirmation. For unassigned bank receipts only reference matches are suggested.
