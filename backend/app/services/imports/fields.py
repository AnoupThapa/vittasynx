"""Canonical import fields per kind, header synonyms for suggested mapping, and status mapping.

The mapping system is data-driven so new source layouts need only new synonyms, not code changes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    required: bool = False
    synonyms: tuple[str, ...] = ()


CUSTOMER_FIELDS = (
    Field("customer_code", "Customer code", synonyms=("customer code", "customer id", "account code", "account number",
                                                      "contact code", "debtor code", "client code", "cust code")),
    Field("customer_name", "Customer name", synonyms=("customer", "customer name", "contact", "contact name", "client",
                                                      "client name", "debtor", "debtor name", "account name", "name")),
)

FIELDS: dict[str, tuple[Field, ...]] = {
    "invoices": (
        Field("invoice_number", "Invoice number", True, ("invoice number", "invoice no", "invoice #", "invoice",
                                                          "inv no", "inv number", "document number", "number", "invoice id")),
        *CUSTOMER_FIELDS,
        Field("issue_date", "Issue date", True, ("issue date", "invoice date", "date", "date issued", "document date")),
        Field("due_date", "Due date", True, ("due date", "payment due", "due", "date due")),
        Field("total_amount", "Total amount (incl. tax)", False, ("total", "total amount", "amount", "invoice total",
                                                                  "gross", "gross amount", "total incl tax",
                                                                  "total inc gst", "amount inc gst")),
        Field("net_amount", "Net amount (excl. tax)", False, ("net", "net amount", "subtotal", "sub total",
                                                              "amount ex gst", "total ex gst")),
        Field("tax_amount", "Tax amount", False, ("tax", "tax amount", "tax total", "gst", "vat", "total tax")),
        Field("currency", "Currency", False, ("currency", "currency code", "ccy")),
        Field("amount_due", "Amount due (reference only)", False, ("amount due", "balance", "balance due", "outstanding",
                                                                    "amount outstanding", "due amount")),
        Field("status", "Status", False, ("status", "invoice status", "state")),
        Field("reference", "Reference", False, ("reference", "ref", "po", "po number", "order number", "your reference")),
    ),
    "credit_notes": (
        Field("credit_note_number", "Credit note number", True, ("credit note number", "credit note no", "credit note",
                                                                  "cn number", "number", "document number")),
        *CUSTOMER_FIELDS,
        Field("credit_date", "Credit date", True, ("credit date", "date", "issue date", "credit note date")),
        Field("amount", "Amount (incl. tax)", True, ("amount", "total", "credit amount", "total amount", "gross")),
        Field("currency", "Currency", False, ("currency", "currency code", "ccy")),
        Field("applies_to_invoice", "Applies to invoice", False, ("applies to invoice", "invoice number", "invoice",
                                                                  "original invoice", "applied to")),
        Field("reason", "Reason", False, ("reason", "description", "memo", "notes")),
    ),
    "payments": (
        Field("payment_date", "Payment date", True, ("payment date", "date", "date received", "receipt date", "paid date")),
        *CUSTOMER_FIELDS,
        Field("amount", "Amount", True, ("amount", "amount paid", "payment amount", "total", "received")),
        Field("currency", "Currency", False, ("currency", "currency code", "ccy")),
        Field("reference", "Reference", False, ("reference", "ref", "payment reference", "invoice number", "description")),
        Field("method", "Method", False, ("method", "payment method", "type")),
    ),
    "bank": (
        Field("date", "Transaction date", True, ("date", "transaction date", "posted date", "value date")),
        Field("description", "Description", False, ("description", "narration", "details", "particulars", "memo",
                                                    "transaction details")),
        Field("reference", "Reference", False, ("reference", "ref", "cheque number")),
        Field("credit", "Credit (money in)", False, ("credit", "credits", "money in", "deposit", "deposits", "paid in",
                                                     "credit amount")),
        Field("debit", "Debit (money out)", False, ("debit", "debits", "money out", "withdrawal", "withdrawals",
                                                    "paid out", "debit amount")),
        Field("amount", "Signed amount (+in / −out)", False, ("amount", "transaction amount", "value")),
        Field("currency", "Currency", False, ("currency", "ccy")),
    ),
}

_CANON = re.compile(r"[^a-z0-9#]+")  # spaces and punctuation are ignored: "InvoiceNumber" == "invoice number"


def _canon(s: str) -> str:
    return _CANON.sub("", s.lower())


def suggest_mapping(kind: str, headers: list[str]) -> dict[str, str]:
    """Exact (canonicalised) synonym matches only. Users always review the mapping."""
    by_canon = {_canon(h): h for h in headers}
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for f in FIELDS[kind]:
        for syn in (f.key.replace("_", " "), f.label, *f.synonyms):
            h = by_canon.get(_canon(syn))
            if h and h not in used:
                mapping[f.key] = h
                used.add(h)
                break
    return mapping


DEFAULT_STATUS_MAP = {
    "": "open", "open": "open", "authorised": "open", "authorized": "open", "awaiting payment": "open",
    "sent": "open", "issued": "open", "unpaid": "open", "overdue": "open", "partially paid": "open",
    "part paid": "open", "outstanding": "open", "approved": "open", "posted": "open", "due": "open",
    "paid": "open",  # balance is calculated from allocations (D-08); source "paid" is noted, not trusted
    "disputed": "disputed", "in dispute": "disputed", "on hold": "disputed",
    "void": "void", "voided": "void", "deleted": "void",
    "cancelled": "cancelled", "canceled": "cancelled",
    "draft": "__draft__", "submitted": "__draft__",
}


def map_status(raw: str, overrides: dict[str, str] | None) -> str | None:
    key = raw.strip().lower()
    if overrides and key in {k.lower(): v for k, v in overrides.items()}:
        return {k.lower(): v for k, v in overrides.items()}[key]
    return DEFAULT_STATUS_MAP.get(key)
