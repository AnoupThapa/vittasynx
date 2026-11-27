"""Request dependencies: authentication, CSRF, organisation membership, permissions and tenant context.

The organisation ID in the URL is never trusted on its own: membership is looked up for the
authenticated user, and a non-member receives 404 (not 403) so record existence is not revealed.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import Forbidden, NotFound, Unauthorised
from app.core.permissions import PRIVILEGED_ROLES, Perm, has_permission
from app.core.security import tokens_equal
from app.db import get_db, set_tenant
from app.models import Membership, Organisation, User, UserSession
from app.services.identity import resolve_session

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _session(request: Request, db: Session, *, allow_mfa_pending: bool) -> UserSession:
    s = get_settings()
    session = resolve_session(db, request.cookies.get(s.session_cookie_name))
    if session is None:
        raise Unauthorised("Sign in required")
    if request.method not in SAFE_METHODS:
        header = request.headers.get("x-csrf-token", "")
        if not header or not tokens_equal(header, session.csrf_token):
            raise Forbidden("Missing or invalid CSRF token", code="csrf_failed")
    if not session.mfa_verified and not allow_mfa_pending:
        raise Unauthorised("MFA verification required", code="mfa_required")
    request.state.user_id = session.user_id
    return session


def current_session(request: Request, db: Session = Depends(get_db)) -> UserSession:
    return _session(request, db, allow_mfa_pending=False)


def pending_session(request: Request, db: Session = Depends(get_db)) -> UserSession:
    return _session(request, db, allow_mfa_pending=True)


def current_user(session: UserSession = Depends(current_session)) -> User:
    return session.user


@dataclass
class OrgContext:
    org: Organisation
    membership: Membership
    user: User
    db: Session

    @property
    def org_id(self) -> uuid.UUID:
        return self.org.id

    @property
    def role(self) -> str:
        return self.membership.role


def require(perm: Perm) -> Callable[..., OrgContext]:
    def dependency(org_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> OrgContext:
        membership = db.scalar(
            select(Membership).where(Membership.organisation_id == org_id, Membership.user_id == user.id)
        )
        if membership is None:
            raise NotFound("Organisation not found")
        if get_settings().require_mfa_for_privileged and membership.role in PRIVILEGED_ROLES and not user.mfa_enabled:
            raise Forbidden(
                "Owners and Administrators must enable two-factor authentication first",
                code="mfa_enrolment_required",
            )
        if not has_permission(membership.role, perm):
            raise Forbidden("Your role does not allow this action", code="permission_denied")
        org = db.get(Organisation, org_id)
        assert org is not None
        set_tenant(db, org.id)
        return OrgContext(org=org, membership=membership, user=user, db=db)

    return dependency
