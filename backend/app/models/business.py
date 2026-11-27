"""Tenant-owned business records. All tables here are protected by PostgreSQL RLS (see migration)."""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin, IdMixin, TenantMixin


class Customer(IdMixin, CreatedMixin, TenantMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        Index("uq_customers_org_code", "organisation_id", "code", unique=True, postgresql_where=text("code IS NOT NULL")),
        Index("ix_customers_org_normname", "organisation_id", "normalised_name"),
        CheckConstraint("status IN ('active','inactive')", name="ck_customers_status"),
    )
    code: Mapped[str | None] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    normalised_name: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime | None] = mapped_column()


class StoredFile(IdMixin, CreatedMixin, TenantMixin, Base):
    __tablename__ = "stored_files"
    original_filename: Mapped[str] = mapped_column(String(300), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class FileBlob(TenantMixin, Base):
    """File contents for the 'database' storage backend (free-tier hosting without object storage)."""

    __tablename__ = "file_blobs"
    storage_key: Mapped[str] = mapped_column(String(300), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


IMPORT_KINDS = ("invoices", "credit_notes", "payments", "bank")


class ImportBatch(IdMixin, CreatedMixin, TenantMixin, Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        CheckConstraint("kind IN ('invoices','credit_notes','payments','bank')", name="ck_import_kind"),
        CheckConstraint("status IN ('uploaded','validated','committed','cancelled')", name="ck_import_status"),
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="uploaded", nullable=False)
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stored_files.id"), nullable=False)
    headers: Mapped[list] = mapped_column(JSONB, nullable=False)
    mapping: Mapped[dict | None] = mapped_column(JSONB)
    options: Mapped[dict | None] = mapped_column(JSONB)
    summary: Mapped[dict | None] = mapped_column(JSONB)
    warnings: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    committed_at: Mapped[datetime | None] = mapped_column()
    committed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


ROW_STATUSES = (
    "valid",  # will create a new record
    "error",  # cannot be imported until corrected
    "duplicate",  # identical to an existing record; will be skipped
    "amendment",  # same identity, changed values; becomes an amendment candidate
    "needs_review",  # possible duplicate; must be included or excluded explicitly
    "excluded",  # excluded by the user
    "skipped",  # not applicable (e.g. bank debit line)
    "committed",  # record created
    "amendment_pending",
    "amendment_approved",
    "amendment_rejected",
    "duplicate_skipped",
)


class ImportRow(IdMixin, CreatedMixin, TenantMixin, Base):
    """Immutable raw source values plus validation outcome. Raw values are never changed (TA-05)."""

    __tablename__ = "import_rows"
    __table_args__ = (UniqueConstraint("batch_id", "row_number", name="uq_import_rows_batch_row"),)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"), index=True)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-based data row (header = row 0)
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False)
    corrections: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    normalised: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    messages: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    include_override: Mapped[bool | None] = mapped_column()
    target_type: Mapped[str | None] = mapped_column(String(30))
    target_id: Mapped[uuid.UUID | None] = mapped_column()
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column()


class Invoice(IdMixin, CreatedMixin, TenantMixin, Base):
    """Current accepted values. Every version (including the first) is kept in invoice_versions."""

    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("organisation_id", "customer_id", "normalised_number", name="uq_invoices_identity"),
        CheckConstraint("status IN ('open','disputed','cancelled','void')", name="ck_invoices_status"),
        CheckConstraint("total_amount >= 0", name="ck_invoices_total_nonneg"),
        CheckConstraint("due_date >= issue_date", name="ck_invoices_due_after_issue"),
        CheckConstraint("entry_method IN ('import','manual','demo')", name="ck_invoices_entry_method"),
        Index("ix_invoices_org_due", "organisation_id", "due_date"),
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True, nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    normalised_number: Mapped[str] = mapped_column(String(100), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(nullable=False)
    tax_amount: Mapped[Decimal | None] = mapped_column()
    net_amount: Mapped[Decimal | None] = mapped_column()
    total_is_derived: Mapped[bool] = mapped_column(default=False, nullable=False)
    source_amount_due: Mapped[Decimal | None] = mapped_column()  # reference only (D-08)
    reference: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)
    status_reason: Mapped[str | None] = mapped_column(String(300))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    entry_method: Mapped[str] = mapped_column(String(10), default="import", server_default="import", nullable=False)
    source_row_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("import_rows.id"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class InvoiceVersion(IdMixin, CreatedMixin, TenantMixin, Base):
    __tablename__ = "invoice_versions"
    __table_args__ = (UniqueConstraint("invoice_id", "version", name="uq_invoice_versions"),)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    values: Mapped[dict] = mapped_column(JSONB, nullable=False)  # money as strings
    change_reason: Mapped[str] = mapped_column(String(300), nullable=False)
    source_row_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("import_rows.id"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class CreditNote(IdMixin, CreatedMixin, TenantMixin, Base):
    __tablename__ = "credit_notes"
    __table_args__ = (
        UniqueConstraint("organisation_id", "customer_id", "normalised_number", name="uq_credit_notes_identity"),
        CheckConstraint("amount > 0", name="ck_credit_notes_amount_pos"),
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True, nullable=False)
    credit_note_number: Mapped[str] = mapped_column(String(100), nullable=False)
    normalised_number: Mapped[str] = mapped_column(String(100), nullable=False)
    credit_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount: Mapped[Decimal] = mapped_column(nullable=False)
    reason: Mapped[str | None] = mapped_column(String(300))
    applies_to_invoice_number: Mapped[str | None] = mapped_column(String(100))
    source_row_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("import_rows.id"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class Payment(IdMixin, CreatedMixin, TenantMixin, Base):
    """A customer receipt. customer_id is NULL for an unassigned bank receipt (D-21)."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payments_amount_pos"),
        CheckConstraint("source IN ('manual','import','bank')", name="ck_payments_source"),
        Index("ix_payments_org_date", "organisation_id", "payment_date"),
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id"), index=True)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount: Mapped[Decimal] = mapped_column(nullable=False)
    reference: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(500))
    method: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(10), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_row_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("import_rows.id"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class Allocation(IdMixin, CreatedMixin, TenantMixin, Base):
    """Confirmed application of a payment or credit note to an invoice. Never deleted; reversed instead."""

    __tablename__ = "allocations"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_allocations_amount_pos"),
        CheckConstraint("status IN ('confirmed','reversed')", name="ck_allocations_status"),
        CheckConstraint(
            "(payment_id IS NOT NULL AND credit_note_id IS NULL) OR (payment_id IS NULL AND credit_note_id IS NOT NULL)",
            name="ck_allocations_one_source",
        ),
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"), index=True, nullable=False)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payments.id"), index=True)
    credit_note_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_notes.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)  # payment/credit date (D-11)
    status: Mapped[str] = mapped_column(String(12), default="confirmed", nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    reversed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reversed_at: Mapped[datetime | None] = mapped_column()
    reversal_reason: Mapped[str | None] = mapped_column(String(300))


class AuditEvent(IdMixin, CreatedMixin, Base):
    """Insert-only (enforced by a database trigger). organisation_id is NULL for identity events."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_org_created", "organisation_id", "created_at"),)
    organisation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organisations.id"))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID | None] = mapped_column()
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    source: Mapped[str | None] = mapped_column(String(80))
    note: Mapped[str | None] = mapped_column(Text)


TENANT_TABLES = (
    "customers",
    "stored_files",
    "import_batches",
    "import_rows",
    "invoices",
    "invoice_versions",
    "credit_notes",
    "payments",
    "allocations",
    "file_blobs",
)
