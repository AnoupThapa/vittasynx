"""Organisations, memberships and invitations."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import set_tenant
from app.core.errors import BusinessRuleViolation, Conflict, Forbidden, NotFound, ValidationFailed
from app.core.security import hash_token, new_token
from app.domain.money import CURRENCY_MINOR_UNITS
from app.models import Invitation, Membership, Organisation, User
from app.services import audit
from app.services.email import send_email

INVITE_TTL = timedelta(days=7)
ASSIGNABLE_ROLES = ("admin", "finance_manager", "ar_officer", "read_only")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def validate_timezone(tz: str) -> str:
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValidationFailed(f"Unknown timezone '{tz}'", code="invalid_timezone") from exc
    return tz


def create_organisation(db: Session, user: User, name: str, currency: str, tz: str) -> Organisation:
    currency = currency.upper()
    if currency not in CURRENCY_MINOR_UNITS:
        raise ValidationFailed(
            f"Currency {currency} is not supported. Supported: {', '.join(sorted(CURRENCY_MINOR_UNITS))}",
            code="unsupported_currency",
        )
    if not name.strip():
        raise ValidationFailed("Organisation name is required")
    org = Organisation(name=name.strip(), currency=currency, timezone=validate_timezone(tz))
    db.add(org)
    db.flush()
    db.add(Membership(organisation_id=org.id, user_id=user.id, role="owner"))
    set_tenant(db, org.id)  # the creator is now the Owner of this organisation
    audit.record(db, action="organisation.created", actor_user_id=user.id, organisation_id=org.id,
                 entity_type="organisation", entity_id=org.id,
                 after={"name": org.name, "currency": currency, "timezone": tz})
    return org


def memberships_for(db: Session, user: User) -> list[Membership]:
    return list(db.scalars(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at)))


def update_organisation(db: Session, actor: User, org: Organisation, name: str | None, tz: str | None) -> Organisation:
    before = {"name": org.name, "timezone": org.timezone}
    if name is not None:
        if not name.strip():
            raise ValidationFailed("Organisation name is required")
        org.name = name.strip()
    if tz is not None:
        org.timezone = validate_timezone(tz)
    audit.record(db, action="organisation.updated", actor_user_id=actor.id, organisation_id=org.id,
                 entity_type="organisation", entity_id=org.id, before=before,
                 after={"name": org.name, "timezone": org.timezone})
    return org


def list_members(db: Session, org: Organisation) -> list[Membership]:
    return list(db.scalars(select(Membership).where(Membership.organisation_id == org.id).order_by(Membership.created_at)))


def _get_member(db: Session, org: Organisation, user_id: uuid.UUID) -> Membership:
    m = db.scalar(select(Membership).where(Membership.organisation_id == org.id, Membership.user_id == user_id).with_for_update())
    if m is None:
        raise NotFound("Member not found")
    return m


def change_role(db: Session, actor: Membership, org: Organisation, user_id: uuid.UUID, role: str) -> Membership:
    if role not in ASSIGNABLE_ROLES:
        raise ValidationFailed("Role cannot be assigned here; use ownership transfer for Owner", code="invalid_role")
    target = _get_member(db, org, user_id)
    if target.role == "owner":
        raise Forbidden("The Owner's role cannot be changed; transfer ownership instead", code="owner_protected")
    if target.user_id == actor.user_id:
        raise Forbidden("You cannot change your own role", code="self_change")
    before = target.role
    target.role = role
    audit.record(db, action="membership.role_changed", actor_user_id=actor.user_id, organisation_id=org.id,
                 entity_type="membership", entity_id=target.id, before={"role": before}, after={"role": role})
    return target


def remove_member(db: Session, actor: Membership, org: Organisation, user_id: uuid.UUID) -> None:
    target = _get_member(db, org, user_id)
    if target.role == "owner":
        raise Forbidden("The Owner cannot be removed", code="owner_protected")
    audit.record(db, action="membership.removed", actor_user_id=actor.user_id, organisation_id=org.id,
                 entity_type="membership", entity_id=target.id,
                 before={"user_id": str(target.user_id), "role": target.role})
    db.delete(target)


def transfer_ownership(db: Session, actor: Membership, org: Organisation, user_id: uuid.UUID) -> None:
    if actor.role != "owner":
        raise Forbidden("Only the Owner can transfer ownership")
    if user_id == actor.user_id:
        raise BusinessRuleViolation("You are already the Owner")
    target = _get_member(db, org, user_id)
    actor_row = _get_member(db, org, actor.user_id)
    previous = target.role
    target.role = "owner"
    actor_row.role = "admin"
    audit.record(db, action="organisation.ownership_transferred", actor_user_id=actor.user_id, organisation_id=org.id,
                 entity_type="organisation", entity_id=org.id,
                 before={"owner": str(actor.user_id), "new_owner_previous_role": previous},
                 after={"owner": str(user_id)})


def invite(db: Session, actor: User, org: Organisation, email: str, role: str) -> Invitation:
    email = email.strip().lower()
    if role not in ASSIGNABLE_ROLES:
        raise ValidationFailed("Invalid role", code="invalid_role")
    existing_user = db.scalar(select(User).where(User.email == email))
    if existing_user and db.scalar(select(Membership).where(Membership.organisation_id == org.id, Membership.user_id == existing_user.id)):
        raise Conflict("This person is already a member", code="already_member")
    token = new_token()
    inv = Invitation(organisation_id=org.id, email=email, role=role, token_hash=hash_token(token),
                     invited_by=actor.id, expires_at=_now() + INVITE_TTL)
    db.add(inv)
    db.flush()
    link = f"{get_settings().app_base_url}/accept-invitation?token={token}"
    send_email(db, email, f"You're invited to {org.name} on Vittasynx",
               f"{actor.full_name} invited you to join {org.name} as {role}.\n\nAccept: {link}\n\nExpires in 7 days.")
    audit.record(db, action="invitation.created", actor_user_id=actor.id, organisation_id=org.id,
                 entity_type="invitation", entity_id=inv.id, after={"email": email, "role": role})
    return inv


def list_invitations(db: Session, org: Organisation) -> list[Invitation]:
    return list(db.scalars(select(Invitation).where(
        Invitation.organisation_id == org.id, Invitation.accepted_at.is_(None), Invitation.revoked_at.is_(None),
    ).order_by(Invitation.created_at.desc())))


def revoke_invitation(db: Session, actor: User, org: Organisation, invitation_id: uuid.UUID) -> None:
    inv = db.scalar(select(Invitation).where(Invitation.id == invitation_id, Invitation.organisation_id == org.id))
    if inv is None or inv.accepted_at or inv.revoked_at:
        raise NotFound("Invitation not found")
    inv.revoked_at = _now()
    audit.record(db, action="invitation.revoked", actor_user_id=actor.id, organisation_id=org.id,
                 entity_type="invitation", entity_id=inv.id)


def accept_invitation(db: Session, user: User, token: str) -> Membership:
    inv = db.scalar(select(Invitation).where(Invitation.token_hash == hash_token(token)).with_for_update())
    if inv is None or inv.accepted_at or inv.revoked_at or inv.expires_at < _now():
        raise ValidationFailed("This invitation is invalid or has expired", code="invalid_invitation")
    if user.email != inv.email:
        raise Forbidden("This invitation was sent to a different email address", code="invitation_email_mismatch")
    if user.email_verified_at is None:
        raise Forbidden("Verify your email address before accepting invitations", code="email_not_verified")
    if db.scalar(select(Membership).where(Membership.organisation_id == inv.organisation_id, Membership.user_id == user.id)):
        raise Conflict("You are already a member", code="already_member")
    inv.accepted_at = _now()
    set_tenant(db, inv.organisation_id)  # membership is being granted by a valid invitation
    m = Membership(organisation_id=inv.organisation_id, user_id=user.id, role=inv.role)
    db.add(m)
    db.flush()
    audit.record(db, action="invitation.accepted", actor_user_id=user.id, organisation_id=inv.organisation_id,
                 entity_type="membership", entity_id=m.id, after={"role": inv.role})
    return m
