"""Audit trail (rules.md §7). Records actor, organisation, action, entity, before/after and source.
Never include passwords, tokens, full bank details or file contents."""
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent


def record(
    db: Session,
    *,
    action: str,
    actor_user_id: uuid.UUID | None,
    organisation_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    source: str | None = "api",
    note: str | None = None,
) -> None:
    db.add(
        AuditEvent(
            organisation_id=organisation_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            source=source,
            note=note,
        )
    )
