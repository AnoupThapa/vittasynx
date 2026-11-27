# Data import examples

All examples are **synthetic** and labelled as such. They show the shapes the Release 1 importer must handle; they are not evidence about real businesses.

## 1. Canonical invoice file
See `templates/invoices.csv`. Required columns: invoice number, customer (code or name), issue date, due date, total amount. Optional: currency (defaults to the organisation currency), tax, net, amount due (reference only), status, reference.

## 2. Same data, different column names (accounting-system style)
```
InvoiceNumber,ContactName,InvoiceDate,DueDate,Total,TaxTotal,AmountDue,Currency,Status
INV-1001,Example Hospital Supplies,05/01/2026,04/02/2026,"1,100.00",100.00,1100.00,AUD,AUTHORISED
```
Handled by column mapping (InvoiceNumber → invoice number, ContactName → customer name…), the day-first date format setting, thousands separators, and status mapping (AUTHORISED → open).

## 3. Rows the importer must reject or flag
| Row problem | Outcome |
|---|---|
| Missing due date | Error: "Due date is required" |
| Due date before issue date | Error |
| Date `31/02/2026` | Error: invalid date |
| Amount `1100.005` | Error: more than 2 decimal places |
| Currency `USD` in an AUD organisation | Error: currency not supported |
| Status `DRAFT` | Error: draft invoices are not imported |
| Same invoice number and customer as an existing invoice, identical values | Skipped: already imported |
| Same invoice number and customer, different amount | Amendment candidate for review |
| Same invoice number, different customer | Warning: possible duplicate |
| Unknown customer | Listed in preview; created on confirmation |

## 4. Bank export
See `templates/bank-transactions.csv`. Credit lines become receipts; debit lines are skipped and counted.
