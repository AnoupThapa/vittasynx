"""Configurable import workflow: upload → preview → map → validate → correct/exclude → confirm → commit.

Raw source values are stored unchanged in import_rows.raw; user corrections are stored separately in
import_rows.corrections, so the original evidence is always preserved (rules.md §1, TA-05).
Commit is idempotent (a committed batch returns its summary) and re-validates every row inside the
commit transaction so it cannot act on stale results.
"""
from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleViolation, NotFound, ValidationFailed
from app.domain.money import ZERO, MoneyError, fmt, parse_amount
from app.domain.normalise import DATE_FORMATS, DateParseError, normalise_name, normalise_number, parse_date
from app.models import CreditNote, Customer, ImportBatch, ImportRow, Invoice, Organisation, Payment, StoredFile
from app.services import audit, customers as customer_svc, ledger
from app.services.imports.fields import FIELDS, map_status, suggest_mapping
from app.services.imports.parsing import parse
from app.services.storage import get_storage

PREVIEW_ROWS = 20


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------- upload ----------

def upload(db: Session, org: Organisation, actor_id: uuid.UUID, kind: str, filename: str, data: bytes) -> ImportBatch:
    if kind not in FIELDS:
        raise ValidationFailed(f"Unknown import type '{kind}'", code="invalid_kind")
    parsed = parse(filename, data)  # validates type/size/structure before anything is stored
    key, sha = get_storage().put(org.id, data)
    f = StoredFile(organisation_id=org.id, original_filename=filename[:300], content_type=parsed.content_type,
                   size_bytes=len(data), sha256=sha, storage_key=key, created_by=actor_id)
    db.add(f)
    db.flush()
    warnings = []
    previous = db.scalar(
        select(ImportBatch).join(StoredFile, StoredFile.id == ImportBatch.file_id)
        .where(ImportBatch.organisation_id == org.id, StoredFile.sha256 == sha, ImportBatch.kind == kind,
               ImportBatch.status == "committed", ImportBatch.id.is_not(None))
        .order_by(ImportBatch.committed_at.desc())
    )
    if previous:
        warnings.append({"code": "file_previously_imported",
                         "message": f"This exact file was already imported on {previous.committed_at:%Y-%m-%d}. "
                                    "Rows already imported will be skipped as duplicates."})
    batch = ImportBatch(organisation_id=org.id, kind=kind, file_id=f.id, headers=parsed.headers,
                        mapping=suggest_mapping(kind, parsed.headers),
                        options={"date_format": "DD/MM/YYYY", "status_map": {}}, warnings=warnings,
                        created_by=actor_id)
    db.add(batch)
    db.flush()
    for line, raw in parsed.rows:
        db.add(ImportRow(organisation_id=org.id, batch_id=batch.id, row_number=line, raw=raw, status="pending"))
    audit.record(db, action="import.uploaded", actor_user_id=actor_id, organisation_id=org.id,
                 entity_type="import_batch", entity_id=batch.id,
                 after={"kind": kind, "filename": filename[:300], "rows": len(parsed.rows), "sha256": sha})
    return batch


def get_batch(db: Session, org_id: uuid.UUID, batch_id: uuid.UUID, *, lock: bool = False) -> ImportBatch:
    q = select(ImportBatch).where(ImportBatch.id == batch_id, ImportBatch.organisation_id == org_id)
    if lock:
        q = q.with_for_update()
    b = db.scalar(q)
    if b is None:
        raise NotFound("Import not found")
    return b


def rows(db: Session, batch: ImportBatch, status: str | None = None, limit: int = 500, offset: int = 0) -> list[ImportRow]:
    q = select(ImportRow).where(ImportRow.batch_id == batch.id, ImportRow.organisation_id == batch.organisation_id)
    if status:
        q = q.where(ImportRow.status == status)
    return list(db.scalars(q.order_by(ImportRow.row_number).limit(limit).offset(offset)))


# ---------- validation ----------

@dataclass
class _Context:
    org: Organisation
    kind: str
    mapping: dict[str, str]
    date_format: str
    status_map: dict[str, str]
    seen_identities: Counter = field(default_factory=Counter)
    new_customers: dict[str, dict] = field(default_factory=dict)


def _value(row: ImportRow, ctx: _Context, key: str) -> str:
    if key in row.corrections:
        return str(row.corrections[key] or "").strip()
    header = ctx.mapping.get(key)
    if not header:
        return ""
    return str(row.raw.get(header, "") or "").strip()


def _amount(row, ctx, key, errors, *, required=False, allow_negative=False) -> Decimal | None:
    raw = _value(row, ctx, key)
    if not raw:
        if required:
            errors.append({"field": key, "message": f"{_label(ctx.kind, key)} is required"})
        return None
    try:
        return parse_amount(raw, ctx.org.currency, allow_negative=allow_negative)
    except MoneyError as exc:
        errors.append({"field": key, "message": f"{_label(ctx.kind, key)}: {exc}"})
        return None


def _date(row, ctx, key, errors, *, required=True) -> date | None:
    raw = _value(row, ctx, key)
    if not raw:
        if required:
            errors.append({"field": key, "message": f"{_label(ctx.kind, key)} is required"})
        return None
    try:
        return parse_date(raw, ctx.date_format)
    except DateParseError as exc:
        errors.append({"field": key, "message": f"{_label(ctx.kind, key)}: {exc}"})
        return None


def _label(kind: str, key: str) -> str:
    for f in FIELDS[kind]:
        if f.key == key:
            return f.label
    return key


def _currency(row, ctx, errors) -> str:
    raw = _value(row, ctx, "currency").upper()
    if raw and raw != ctx.org.currency:
        errors.append({"field": "currency",
                       "message": f"Currency {raw} is not supported; this organisation reports in {ctx.org.currency}"})
    return ctx.org.currency


def _resolve_customer(db: Session, row, ctx: _Context, errors, *, required: bool) -> tuple[str | None, str | None]:
    """Returns (existing_customer_id, new_customer_key). Exact code or normalised name only (D-15)."""
    code = _value(row, ctx, "customer_code")
    name = _value(row, ctx, "customer_name")
    if not code and not name:
        if required:
            errors.append({"field": "customer_name", "message": "Customer code or name is required"})
        return None, None
    if code:
        c = customer_svc.find_by_code(db, ctx.org.id, code)
        if c:
            return str(c.id), None
        if not name:
            errors.append({"field": "customer_code",
                           "message": f"Customer code {code} is not known; add a customer name to create it"})
            return None, None
        key = f"code:{code}"
        ctx.new_customers.setdefault(key, {"code": code, "name": name})
        return None, key
    matches = customer_svc.find_by_name(db, ctx.org.id, name)
    if len(matches) == 1:
        return str(matches[0].id), None
    if len(matches) > 1:
        errors.append({"field": "customer_name",
                       "message": f"More than one customer is named '{name}'; map a customer code column"})
        return None, None
    key = f"name:{normalise_name(name)}"
    ctx.new_customers.setdefault(key, {"code": None, "name": name})
    return None, key


def _classify_invoice(db: Session, row: ImportRow, ctx: _Context) -> tuple[str, list, dict | None]:
    errors: list[dict] = []
    warnings: list[dict] = []
    number = _value(row, ctx, "invoice_number")
    if not number:
        errors.append({"field": "invoice_number", "message": "Invoice number is required"})
    customer_id, new_key = _resolve_customer(db, row, ctx, errors, required=True)
    issue = _date(row, ctx, "issue_date", errors)
    due = _date(row, ctx, "due_date", errors)
    if issue and due and due < issue:
        errors.append({"field": "due_date", "message": "Due date is before the issue date"})
    currency = _currency(row, ctx, errors)
    total = _amount(row, ctx, "total_amount", errors, allow_negative=True)
    net = _amount(row, ctx, "net_amount", errors, allow_negative=True)
    tax = _amount(row, ctx, "tax_amount", errors, allow_negative=True)
    amount_due = _amount(row, ctx, "amount_due", errors, allow_negative=True)
    derived = False
    if total is None and not any(e["field"] == "total_amount" for e in errors):
        if net is not None and tax is not None:
            total, derived = net + tax, True
        else:
            errors.append({"field": "total_amount", "message": "Total amount is required (or both net and tax amounts)"})
    if total is not None and net is not None and tax is not None and not derived and net + tax != total:
        errors.append({"field": "total_amount", "message": "Total does not equal net + tax"})
    if total is not None and total < ZERO:
        errors.append({"field": "total_amount", "message": "Negative invoice amounts must be imported as credit notes"})
    raw_status = _value(row, ctx, "status")
    status = map_status(raw_status, ctx.status_map)
    if status == "__draft__":
        errors.append({"field": "status", "message": "Draft invoices are not imported"})
    elif status is None:
        errors.append({"field": "status", "message": f"Status '{raw_status}' is not recognised; map it in the import options"})
    elif raw_status.strip().lower() == "paid":
        warnings.append({"field": "status", "message": "Marked paid in the source. Vittasynx calculates the balance "
                                                       "from payments you import or record."})
    if total is not None and total == ZERO:
        warnings.append({"field": "total_amount", "message": "Zero-value invoice"})
    if errors:
        return "error", errors, None

    norm = normalise_number(number)
    normalised = {
        "invoice_number": number, "normalised_number": norm, "customer_id": customer_id, "new_customer_key": new_key,
        "issue_date": issue.isoformat(), "due_date": due.isoformat(), "currency": currency,
        "total_amount": fmt(total, currency), "total_is_derived": derived,
        "net_amount": fmt(net, currency), "tax_amount": fmt(tax, currency),
        "amount_due": fmt(amount_due, currency), "status": status, "reference": _value(row, ctx, "reference") or None,
    }
    identity = (customer_id or new_key, norm)
    ctx.seen_identities[identity] += 1
    if ctx.seen_identities[identity] > 1:
        return "error", [{"field": "invoice_number", "message": "Duplicate of an earlier row in this file"}], normalised

    if customer_id:
        existing = db.scalar(select(Invoice).where(Invoice.organisation_id == ctx.org.id,
                                                   Invoice.customer_id == uuid.UUID(customer_id),
                                                   Invoice.normalised_number == norm))
        if existing:
            normalised["existing_invoice_id"] = str(existing.id)
            changes = _invoice_changes(existing, normalised)
            if not changes:
                return "duplicate", warnings + [{"field": None, "message": "Already imported with identical values"}], normalised
            normalised["changes"] = changes
            return "amendment", warnings + [{"field": None, "message": "Existing invoice with changed values: "
                                             + ", ".join(sorted(changes))}], normalised
    elsewhere = db.scalar(select(Invoice).where(Invoice.organisation_id == ctx.org.id, Invoice.normalised_number == norm))
    if elsewhere:
        return "needs_review", warnings + [{"field": "invoice_number", "message": "An invoice with this number exists "
                                            "for a different customer; include or exclude this row"}], normalised
    return "valid", warnings, normalised


_AMEND_FIELDS = ("issue_date", "due_date", "total_amount", "net_amount", "tax_amount", "reference", "status")


def _invoice_changes(inv: Invoice, n: dict) -> dict:
    current = ledger.invoice_values(inv)
    changes = {}
    for k in _AMEND_FIELDS:
        new = n.get(k)
        if k == "status" and inv.status in ("cancelled", "void", "disputed") and new == "open":
            continue  # a source 'open' does not reopen an invoice changed in Vittasynx
        if current.get(k) != new:
            changes[k] = {"from": current.get(k), "to": new}
    return changes


def _classify_credit_note(db: Session, row: ImportRow, ctx: _Context) -> tuple[str, list, dict | None]:
    errors: list[dict] = []
    number = _value(row, ctx, "credit_note_number")
    if not number:
        errors.append({"field": "credit_note_number", "message": "Credit note number is required"})
    customer_id, new_key = _resolve_customer(db, row, ctx, errors, required=True)
    credit_date = _date(row, ctx, "credit_date", errors)
    currency = _currency(row, ctx, errors)
    amount = _amount(row, ctx, "amount", errors, required=True, allow_negative=True)
    if amount is not None:
        amount = abs(amount)  # exports often show credits as negative; the record type carries the sign
        if amount == ZERO:
            errors.append({"field": "amount", "message": "Credit note amount must be greater than zero"})
    if errors:
        return "error", errors, None
    norm = normalise_number(number)
    normalised = {"credit_note_number": number, "normalised_number": norm, "customer_id": customer_id,
                  "new_customer_key": new_key, "credit_date": credit_date.isoformat(), "currency": currency,
                  "amount": fmt(amount, currency), "applies_to_invoice": _value(row, ctx, "applies_to_invoice") or None,
                  "reason": _value(row, ctx, "reason") or None}
    identity = (customer_id or new_key, norm)
    ctx.seen_identities[identity] += 1
    if ctx.seen_identities[identity] > 1:
        return "error", [{"field": "credit_note_number", "message": "Duplicate of an earlier row in this file"}], normalised
    if customer_id:
        existing = db.scalar(select(CreditNote).where(CreditNote.organisation_id == ctx.org.id,
                                                      CreditNote.customer_id == uuid.UUID(customer_id),
                                                      CreditNote.normalised_number == norm))
        if existing:
            same = (existing.credit_date.isoformat() == normalised["credit_date"]
                    and fmt(existing.amount, currency) == normalised["amount"])
            if same:
                return "duplicate", [{"field": None, "message": "Already imported with identical values"}], normalised
            return "error", [{"field": "credit_note_number", "message": "A credit note with this number already exists "
                              "with different values; amendments to credit notes are not supported"}], normalised
    return "valid", [], normalised


def _classify_payment(db: Session, row: ImportRow, ctx: _Context) -> tuple[str, list, dict | None]:
    errors: list[dict] = []
    if ctx.kind == "bank":
        pay_date = _date(row, ctx, "date", errors)
        credit = _amount(row, ctx, "credit", errors, allow_negative=True)
        debit = _amount(row, ctx, "debit", errors, allow_negative=True)
        signed = _amount(row, ctx, "amount", errors, allow_negative=True)
        _currency(row, ctx, errors)
        if errors:
            return "error", errors, None
        if credit is not None and credit != ZERO:
            amount = abs(credit)
        elif signed is not None and signed > ZERO:
            amount = signed
        elif (debit is not None and debit != ZERO) or (signed is not None and signed < ZERO):
            return "skipped", [{"field": None, "message": "Money out — not a customer receipt"}], None
        else:
            return "error", [{"field": "credit", "message": "No credit or amount value"}], None
        customer_id, new_key = None, None
        reference = _value(row, ctx, "reference") or None
        description = _value(row, ctx, "description") or None
        method = "bank"
    else:
        pay_date = _date(row, ctx, "payment_date", errors)
        amount = _amount(row, ctx, "amount", errors, required=True)
        _currency(row, ctx, errors)
        customer_id, new_key = _resolve_customer(db, row, ctx, errors, required=False)
        if amount is not None and amount == ZERO:
            errors.append({"field": "amount", "message": "Payment amount must be greater than zero"})
        if errors:
            return "error", errors, None
        reference = _value(row, ctx, "reference") or None
        description = None
        method = _value(row, ctx, "method") or None
    key = ledger.payment_dedupe_key(pay_date, amount, reference, description)
    normalised = {"payment_date": pay_date.isoformat(), "amount": fmt(amount, ctx.org.currency),
                  "currency": ctx.org.currency, "customer_id": customer_id, "new_customer_key": new_key,
                  "reference": reference, "description": description, "method": method, "dedupe_key": key}
    if db.scalar(select(Payment).where(Payment.organisation_id == ctx.org.id, Payment.dedupe_key == key)):
        return "duplicate", [{"field": None, "message": "A payment with the same date, amount and reference already "
                              "exists"}], normalised
    ctx.seen_identities[key] += 1
    if ctx.seen_identities[key] > 1:
        return "needs_review", [{"field": None, "message": "Same date, amount and reference as an earlier row in this "
                                 "file; include it only if it is a separate payment"}], normalised
    return "valid", [], normalised


_CLASSIFIERS = {"invoices": _classify_invoice, "credit_notes": _classify_credit_note,
                "payments": _classify_payment, "bank": _classify_payment}

_REQUIRED_ONE_OF = {"bank": ("credit", "amount")}


def _check_mapping(kind: str, headers: list[str], mapping: dict[str, str]) -> None:
    valid_keys = {f.key for f in FIELDS[kind]}
    unknown = set(mapping) - valid_keys
    if unknown:
        raise ValidationFailed(f"Unknown fields in mapping: {', '.join(sorted(unknown))}", code="invalid_mapping")
    for k, h in mapping.items():
        if h not in headers:
            raise ValidationFailed(f"Column '{h}' (mapped to {k}) is not in the file", code="invalid_mapping")
    dupes = [h for h, n in Counter(mapping.values()).items() if n > 1]
    if dupes:
        raise ValidationFailed(f"Column '{dupes[0]}' is mapped more than once", code="invalid_mapping")
    missing = [f.label for f in FIELDS[kind] if f.required and f.key not in mapping]
    if kind in ("invoices", "credit_notes") and not ({"customer_code", "customer_name"} & set(mapping)):
        missing.append("Customer code or Customer name")
    if kind == "invoices" and "total_amount" not in mapping and not {"net_amount", "tax_amount"} <= set(mapping):
        missing.append("Total amount (or Net and Tax amounts)")
    if kind == "bank" and not ({"credit", "amount"} & set(mapping)):
        missing.append("Credit or Signed amount")
    if missing:
        raise ValidationFailed("Required columns are not mapped: " + ", ".join(missing), code="invalid_mapping",
                               details={"missing": missing})


def _run_classification(db: Session, org: Organisation, batch: ImportBatch) -> _Context:
    ctx = _Context(org=org, kind=batch.kind, mapping=batch.mapping or {},
                   date_format=(batch.options or {}).get("date_format", "DD/MM/YYYY"),
                   status_map=(batch.options or {}).get("status_map", {}) or {})
    classify = _CLASSIFIERS[batch.kind]
    for row in rows(db, batch, limit=10**9):
        status, messages, normalised = classify(db, row, ctx)
        if row.include_override is False:
            status = "excluded"
        elif status == "needs_review" and row.include_override is True:
            status = "valid"
            messages = messages + [{"field": None, "message": "Included after review"}]
        row.status, row.messages, row.normalised = status, messages, normalised
    db.flush()
    return ctx


def _summarise(db: Session, batch: ImportBatch, ctx: _Context | None = None) -> dict:
    counts = Counter(r.status for r in rows(db, batch, limit=10**9))
    out = {"total_rows": sum(counts.values()), "by_status": dict(counts)}
    if ctx is not None:
        out["new_customers"] = list(ctx.new_customers.values())
    return out


def configure_and_validate(db: Session, org: Organisation, actor_id: uuid.UUID, batch_id: uuid.UUID,
                           mapping: dict[str, str], date_format: str, status_map: dict[str, str] | None) -> ImportBatch:
    batch = get_batch(db, org.id, batch_id, lock=True)
    if batch.status not in ("uploaded", "validated"):
        raise BusinessRuleViolation(f"This import is {batch.status}", code="import_closed")
    if date_format not in DATE_FORMATS:
        raise ValidationFailed(f"Date format must be one of {', '.join(DATE_FORMATS)}", code="invalid_date_format")
    allowed_status = {"open", "disputed", "cancelled", "void", "__draft__"}
    for k, v in (status_map or {}).items():
        if v not in allowed_status:
            raise ValidationFailed(f"Status '{k}' must map to one of open, disputed, cancelled, void", code="invalid_status_map")
    mapping = {k: v for k, v in mapping.items() if v}
    _check_mapping(batch.kind, batch.headers, mapping)
    batch.mapping = mapping
    batch.options = {"date_format": date_format, "status_map": status_map or {}}
    ctx = _run_classification(db, org, batch)
    batch.status = "validated"
    batch.summary = _summarise(db, batch, ctx)
    audit.record(db, action="import.validated", actor_user_id=actor_id, organisation_id=org.id,
                 entity_type="import_batch", entity_id=batch.id, after={"mapping": mapping, "options": batch.options,
                                                                        "summary": batch.summary})
    return batch


def update_row(db: Session, org: Organisation, actor_id: uuid.UUID, batch_id: uuid.UUID, row_id: uuid.UUID,
               action: str, corrections: dict[str, str] | None) -> ImportBatch:
    batch = get_batch(db, org.id, batch_id, lock=True)
    if batch.status != "validated":
        raise BusinessRuleViolation("Validate the import before reviewing rows", code="import_not_validated")
    row = db.scalar(select(ImportRow).where(ImportRow.id == row_id, ImportRow.batch_id == batch.id))
    if row is None:
        raise NotFound("Row not found")
    valid_keys = {f.key for f in FIELDS[batch.kind]}
    if action == "exclude":
        row.include_override = False
    elif action == "include":
        row.include_override = True
    elif action == "reset":
        row.include_override = None
        row.corrections = {}
    elif action == "correct":
        if not corrections or set(corrections) - valid_keys:
            raise ValidationFailed("Corrections must use import field names", code="invalid_correction")
        row.corrections = {**row.corrections, **{k: str(v) for k, v in corrections.items()}}
        row.include_override = None
    else:
        raise ValidationFailed("Action must be exclude, include, correct or reset")
    audit.record(db, action=f"import.row_{action}", actor_user_id=actor_id, organisation_id=org.id,
                 entity_type="import_row", entity_id=row.id,
                 after={"row_number": row.row_number, "corrections": row.corrections if action == "correct" else None})
    ctx = _run_classification(db, org, batch)
    batch.summary = _summarise(db, batch, ctx)
    return batch


def cancel(db: Session, org: Organisation, actor_id: uuid.UUID, batch_id: uuid.UUID) -> ImportBatch:
    batch = get_batch(db, org.id, batch_id, lock=True)
    if batch.status == "committed":
        raise BusinessRuleViolation("A committed import cannot be cancelled", code="import_closed")
    batch.status = "cancelled"
    audit.record(db, action="import.cancelled", actor_user_id=actor_id, organisation_id=org.id,
                 entity_type="import_batch", entity_id=batch.id)
    return batch


# ---------- commit ----------

def commit(db: Session, org: Organisation, actor_id: uuid.UUID, batch_id: uuid.UUID, *,
           confirm_new_customers: bool, exclude_errors: bool) -> ImportBatch:
    batch = get_batch(db, org.id, batch_id, lock=True)
    if batch.status == "committed":
        return batch  # idempotent: retrying a commit never duplicates records
    if batch.status != "validated":
        raise BusinessRuleViolation("Validate the import before committing", code="import_not_validated")
    ctx = _run_classification(db, org, batch)  # re-check against the current database
    all_rows = rows(db, batch, limit=10**9)
    errors = [r for r in all_rows if r.status == "error"]
    if errors and not exclude_errors:
        raise BusinessRuleViolation(f"{len(errors)} row(s) have errors; correct or exclude them first",
                                    code="rows_have_errors", details={"error_rows": [r.row_number for r in errors[:50]]})
    review = [r for r in all_rows if r.status == "needs_review"]
    if review:
        raise BusinessRuleViolation(f"{len(review)} row(s) need review; include or exclude them",
                                    code="rows_need_review", details={"rows": [r.row_number for r in review[:50]]})
    used_new = {r.normalised.get("new_customer_key") for r in all_rows
                if r.status in ("valid", "amendment") and r.normalised and r.normalised.get("new_customer_key")}
    if used_new and not confirm_new_customers:
        raise BusinessRuleViolation(f"{len(used_new)} new customer(s) will be created; confirm to continue",
                                    code="confirm_new_customers",
                                    details={"new_customers": [ctx.new_customers[k] for k in sorted(used_new)]})

    created_customers: dict[str, uuid.UUID] = {}
    for key in sorted(used_new):
        info = ctx.new_customers[key]
        c = customer_svc.create(db, org.id, actor_id, info["name"], info["code"], source=f"import:{batch.id}")
        created_customers[key] = c.id

    def cust(n: dict) -> uuid.UUID | None:
        if n.get("customer_id"):
            return uuid.UUID(n["customer_id"])
        if n.get("new_customer_key"):
            return created_customers[n["new_customer_key"]]
        return None

    counts: Counter = Counter()
    for row in all_rows:
        n = row.normalised or {}
        if row.status == "error":
            row.status = "excluded"
            row.messages = row.messages + [{"field": None, "message": "Excluded at commit because of errors"}]
            counts["excluded"] += 1
        elif row.status == "duplicate":
            row.status = "duplicate_skipped"
            counts["duplicate_skipped"] += 1
        elif row.status in ("excluded", "skipped"):
            counts[row.status] += 1
        elif row.status == "amendment":
            row.status = "amendment_pending"
            row.target_type, row.target_id = "invoice", uuid.UUID(n["existing_invoice_id"])
            counts["amendment_pending"] += 1
        elif row.status == "valid":
            target_type, target_id = _create_record(db, org, actor_id, batch, row, n, cust(n))
            row.status, row.target_type, row.target_id = "committed", target_type, target_id
            counts["committed"] += 1
    batch.status = "committed"
    batch.committed_at = _now()
    batch.committed_by = actor_id
    batch.summary = {**_summarise(db, batch), "result": dict(counts), "customers_created": len(created_customers)}
    audit.record(db, action="import.committed", actor_user_id=actor_id, organisation_id=org.id,
                 entity_type="import_batch", entity_id=batch.id, after=batch.summary)
    return batch


def _create_record(db: Session, org: Organisation, actor_id: uuid.UUID, batch: ImportBatch, row: ImportRow,
                   n: dict, customer_id: uuid.UUID | None) -> tuple[str, uuid.UUID]:
    src = f"import:{batch.id}"
    c = org.currency
    if batch.kind == "invoices":
        inv = Invoice(organisation_id=org.id, customer_id=customer_id, invoice_number=n["invoice_number"],
                      normalised_number=n["normalised_number"], issue_date=date.fromisoformat(n["issue_date"]),
                      due_date=date.fromisoformat(n["due_date"]), currency=c,
                      total_amount=parse_amount(n["total_amount"], c, allow_negative=True),
                      tax_amount=parse_amount(n["tax_amount"], c, allow_negative=True) if n.get("tax_amount") else None,
                      net_amount=parse_amount(n["net_amount"], c, allow_negative=True) if n.get("net_amount") else None,
                      total_is_derived=n["total_is_derived"],
                      source_amount_due=parse_amount(n["amount_due"], c, allow_negative=True) if n.get("amount_due") else None,
                      reference=n.get("reference"), status=n["status"], version=1, source_row_id=row.id,
                      created_by=actor_id)
        db.add(inv)
        db.flush()
        ledger.record_version(db, inv, "imported", actor_id, row.id)
        audit.record(db, action="invoice.imported", actor_user_id=actor_id, organisation_id=org.id,
                     entity_type="invoice", entity_id=inv.id, after=ledger.invoice_values(inv), source=src)
        return "invoice", inv.id
    if batch.kind == "credit_notes":
        cn = ledger.create_credit_note(db, org, actor_id, customer_id=customer_id, number=n["credit_note_number"],
                                       credit_date=date.fromisoformat(n["credit_date"]), amount=n["amount"],
                                       reason=n.get("reason"), applies_to=n.get("applies_to_invoice"),
                                       source_row_id=row.id, source=src)
        return "credit_note", cn.id
    p = ledger.create_payment(db, org, actor_id, customer_id=customer_id,
                              payment_date=date.fromisoformat(n["payment_date"]), amount=n["amount"],
                              reference=n.get("reference"), description=n.get("description"), method=n.get("method"),
                              source="bank" if batch.kind == "bank" else "import", source_row_id=row.id,
                              check_duplicate=False)
    return "payment", p.id


# ---------- amendments (D-09) ----------

def pending_amendments(db: Session, org_id: uuid.UUID) -> list[ImportRow]:
    return list(db.scalars(select(ImportRow).where(ImportRow.organisation_id == org_id,
                                                   ImportRow.status == "amendment_pending")
                           .order_by(ImportRow.created_at)))


def review_amendment(db: Session, org: Organisation, actor_id: uuid.UUID, row_id: uuid.UUID, approve: bool,
                     reason: str | None) -> ImportRow:
    row = db.scalar(select(ImportRow).where(ImportRow.id == row_id, ImportRow.organisation_id == org.id)
                    .with_for_update())
    if row is None or row.status != "amendment_pending":
        raise NotFound("Pending amendment not found")
    inv = ledger.get_invoice(db, org.id, row.target_id, lock=True)
    n = row.normalised or {}
    if approve:
        c = org.currency
        new_total = parse_amount(n["total_amount"], c, allow_negative=True)
        allocated = ledger.confirmed_total(db, org.id, invoice_id=inv.id)
        if new_total < allocated:
            raise BusinessRuleViolation(
                f"The new amount {fmt(new_total, c)} is less than the confirmed allocations of {fmt(allocated, c)}; "
                "reverse allocations first", code="amendment_below_allocations")
        new_status = n["status"]
        if new_status in ("cancelled", "void") and allocated > ZERO:
            raise BusinessRuleViolation("Reverse allocations before cancelling or voiding this invoice",
                                        code="has_allocations")
        before = ledger.invoice_values(inv)
        inv.issue_date = date.fromisoformat(n["issue_date"])
        inv.due_date = date.fromisoformat(n["due_date"])
        inv.total_amount = new_total
        inv.net_amount = parse_amount(n["net_amount"], c, allow_negative=True) if n.get("net_amount") else None
        inv.tax_amount = parse_amount(n["tax_amount"], c, allow_negative=True) if n.get("tax_amount") else None
        inv.total_is_derived = n["total_is_derived"]
        inv.source_amount_due = parse_amount(n["amount_due"], c, allow_negative=True) if n.get("amount_due") else None
        inv.reference = n.get("reference")
        if not (inv.status in ("cancelled", "void", "disputed") and new_status == "open"):
            inv.status = new_status
        inv.version += 1
        ledger.record_version(db, inv, f"amendment approved: {reason or 'source change'}", actor_id, row.id)
        row.status = "amendment_approved"
        audit.record(db, action="invoice.amended", actor_user_id=actor_id, organisation_id=org.id,
                     entity_type="invoice", entity_id=inv.id, before=before, after=ledger.invoice_values(inv),
                     source=f"import_row:{row.id}", note=reason)
    else:
        row.status = "amendment_rejected"
        audit.record(db, action="invoice.amendment_rejected", actor_user_id=actor_id, organisation_id=org.id,
                     entity_type="invoice", entity_id=inv.id, source=f"import_row:{row.id}", note=reason)
    row.reviewed_by, row.reviewed_at = actor_id, _now()
    return row


def file_for(db: Session, org_id: uuid.UUID, batch: ImportBatch) -> tuple[StoredFile, bytes]:
    f = db.scalar(select(StoredFile).where(StoredFile.id == batch.file_id, StoredFile.organisation_id == org_id))
    if f is None:
        raise NotFound("File not found")
    return f, get_storage().get(f.storage_key)


__all__ = ["upload", "configure_and_validate", "update_row", "commit", "cancel", "review_amendment",
           "pending_amendments", "get_batch", "rows", "file_for"]
