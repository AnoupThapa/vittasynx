# Sample data requirements and anonymisation procedure

**Status:** Ready for use. No sample data has been received.

## What we ask for
Templates are in `templates/`. Participants can also send their own system's export as-is; we'll map it.

| Dataset | Template | Needed for | Required? |
|---|---|---|---|
| Customer list | `customers.csv` | Customer matching (D-15) | Yes |
| Sales invoices (12 months, open and paid) | `invoices.csv` | Balances, ageing, behaviour | Yes |
| Credit notes | `credit-notes.csv` | Credit allocation | If used |
| Customer payments / receipts | `payments.csv` | Allocation, behaviour | Yes |
| Bank transaction export (receipts account) | `bank-transactions.csv` | Bank import | Optional |
| Their own ageing report at a stated date | `receivables-ageing.csv` | Reconciliation test (Phase 6) | Strongly preferred |
| Supplier list | `suppliers.csv` | Release 2 only | No |

## What we never ask for
Bank or accounting login credentials, passwords, full bank account numbers, card numbers, staff personal details, tax file numbers, or anything not listed above.

## Anonymisation procedure (done by the participant or by us before any development use)
1. **Customer names** → replace with stable pseudonyms (`Customer 001`, `Customer 002`…), keeping the same pseudonym for the same customer across all files.
2. **Customer codes** → keep if they're internal codes; otherwise replace consistently.
3. **ABN/PAN, addresses, contact names, emails, phones** → delete the columns.
4. **Bank descriptions/narrations** → replace names with the customer pseudonym; delete account numbers and BSBs.
5. **Amounts and dates** → keep unchanged (they're what we're testing). If the participant prefers, multiply all amounts by one constant factor and record that fact, not the factor.
6. **Invoice numbers** → keep, or replace consistently across invoices, credits and payments.
7. Record in the dataset log: source (segment only), date received, anonymisation steps applied, who checked it, consent reference.
8. Store only in the restricted validation folder, never in the code repository, and delete per the retention rule (D-20) once the validation report is final, unless written consent allows keeping it as test fixtures.

## Dataset log
| Dataset ID | Segment | Received | Anonymised by | Checked by | Consent ref | Delete by |
|---|---|---|---|---|---|---|
| *(none yet)* | | | | | | |
