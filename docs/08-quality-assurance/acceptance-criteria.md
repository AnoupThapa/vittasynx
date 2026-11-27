# MVP acceptance criteria

## Import
- User can select a supported file and see a preview before commit.
- Invalid rows show row number and actionable reason.
- Duplicate candidates are identified.
- Re-importing the same file does not silently create duplicate records.
- The import outcome is recorded and auditable.

## Receivables
- Invoice list shows original amount, allocated payments, credits and outstanding balance.
- Ageing buckets reconcile to the invoice-level outstanding balances.
- Reporting date can be identified.
- Filters and exports return consistent results.
- Cancelled invoices are handled according to the documented rule.

## Payment allocation
- Partial and split allocations are supported.
- Suggested matches require confirmation.
- Allocated totals cannot exceed permitted amounts.
- Unapplied amounts remain visible.
- Allocation changes are auditable.

## Cash forecast
- Forecast shows opening cash, inflows, outflows and closing cash by period.
- Each material item has source, expected date and status.
- Confirmed, estimated and scenario-only values are visually distinct.
- Changing a scenario does not alter actual records or baseline values.
- Forecast assumptions are visible.

## Security
- Users cannot access another organisation's data.
- File access and exports enforce tenant ownership.
- Role restrictions are enforced by the backend.
- Sensitive values are not exposed in routine logs.

## Pilot readiness
- Core workflows pass automated tests.
- Backup and restoration process has been tested.
- Known limitations are visible to pilot users.
- No unsupported claim of prediction accuracy or financial certainty is made.
