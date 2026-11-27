import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Exact decimal for all money (TA-01). Never Float.
Money = Numeric(19, 4, asdecimal=True)


class Base(DeclarativeBase):
    type_annotation_map = {
        uuid.UUID: PGUUID(as_uuid=True),
        datetime: DateTime(timezone=True),
        Decimal: Money,
    }


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class CreatedMixin:
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)


class TenantMixin:
    """Every business-owned record carries organisation_id directly (TA-03) and is covered by RLS."""

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
