"""Registration, login, sessions, email verification, password reset and TOTP MFA."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pyotp
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import Conflict, Unauthorised, ValidationFailed
from app.core.security import (
    DUMMY_HASH,
    hash_password,
    hash_token,
    new_token,
    validate_password,
    verify_password,
)
from app.models import User, UserSession, UserToken
from app.services import audit
from app.services.email import send_email

VERIFY_TTL = timedelta(hours=48)
RESET_TTL = timedelta(minutes=30)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalise_email(email: str) -> str:
    return email.strip().lower()


def register(db: Session, email: str, full_name: str, password: str) -> User:
    email = normalise_email(email)
    problem = validate_password(password)
    if problem:
        raise ValidationFailed(problem, code="weak_password")
    if not full_name.strip():
        raise ValidationFailed("Full name is required")
    if db.scalar(select(User).where(User.email == email)):
        raise Conflict("An account with this email already exists", code="email_taken")
    user = User(email=email, full_name=full_name.strip(), password_hash=hash_password(password))
    db.add(user)
    db.flush()
    _issue_token(db, user, "verify_email", VERIFY_TTL, "Verify your Vittasynx email", "/verify-email?token=")
    audit.record(db, action="user.registered", actor_user_id=user.id, entity_type="user", entity_id=user.id)
    return user


def _issue_token(db: Session, user: User, purpose: str, ttl: timedelta, subject: str, path: str) -> str:
    token = new_token()
    db.add(UserToken(user_id=user.id, purpose=purpose, token_hash=hash_token(token), expires_at=_now() + ttl))
    link = f"{get_settings().app_base_url}{path}{token}"
    send_email(db, user.email, subject, f"Hello {user.full_name},\n\nUse this link: {link}\n\nIt expires in {ttl}.")
    return token


def _consume_token(db: Session, token: str, purpose: str) -> User:
    row = db.scalar(
        select(UserToken).where(UserToken.token_hash == hash_token(token), UserToken.purpose == purpose).with_for_update()
    )
    if row is None or row.used_at is not None or row.expires_at < _now():
        raise ValidationFailed("This link is invalid or has expired", code="invalid_token")
    row.used_at = _now()
    user = db.get(User, row.user_id)
    assert user is not None
    return user


def verify_email(db: Session, token: str) -> User:
    user = _consume_token(db, token, "verify_email")
    if user.email_verified_at is None:
        user.email_verified_at = _now()
        audit.record(db, action="user.email_verified", actor_user_id=user.id, entity_type="user", entity_id=user.id)
    return user


def resend_verification(db: Session, user: User) -> None:
    if user.email_verified_at is None:
        _issue_token(db, user, "verify_email", VERIFY_TTL, "Verify your Vittasynx email", "/verify-email?token=")


def request_password_reset(db: Session, email: str) -> None:
    """Always succeeds from the caller's perspective, so account existence is not revealed."""
    user = db.scalar(select(User).where(User.email == normalise_email(email), User.is_active.is_(True)))
    if user:
        _issue_token(db, user, "reset_password", RESET_TTL, "Reset your Vittasynx password", "/reset-password?token=")
        audit.record(db, action="user.password_reset_requested", actor_user_id=user.id, entity_type="user", entity_id=user.id)


def reset_password(db: Session, token: str, new_password: str) -> None:
    problem = validate_password(new_password)
    if problem:
        raise ValidationFailed(problem, code="weak_password")
    user = _consume_token(db, token, "reset_password")
    user.password_hash = hash_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    # Revoke every existing session after a password reset.
    db.execute(update(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None)).values(revoked_at=_now()))
    audit.record(db, action="user.password_reset", actor_user_id=user.id, entity_type="user", entity_id=user.id)


@dataclass
class LoginResult:
    user: User
    session: UserSession
    token: str
    mfa_required: bool


def login(db: Session, email: str, password: str) -> LoginResult:
    s = get_settings()
    user = db.scalar(select(User).where(User.email == normalise_email(email)).with_for_update())
    generic = Unauthorised("Email or password is incorrect", code="invalid_credentials")
    if user is None or not user.is_active:
        verify_password(DUMMY_HASH, password)  # similar timing
        raise generic
    if user.locked_until and user.locked_until > _now():
        raise Unauthorised("Too many failed attempts. Try again later.", code="account_locked")
    if not verify_password(user.password_hash, password):
        user.failed_login_count += 1
        if user.failed_login_count >= s.max_failed_logins:
            user.locked_until = _now() + timedelta(minutes=s.lockout_minutes)
            user.failed_login_count = 0
            audit.record(db, action="user.locked", actor_user_id=user.id, entity_type="user", entity_id=user.id)
        db.commit()  # persist the failure count even though the request fails
        raise generic
    user.failed_login_count = 0
    user.locked_until = None
    token = new_token()
    now = _now()
    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(token),
        csrf_token=new_token(),
        expires_at=now + timedelta(hours=s.session_absolute_hours),
        last_seen_at=now,
        mfa_verified=not user.mfa_enabled,
    )
    db.add(session)
    audit.record(db, action="user.login", actor_user_id=user.id, entity_type="user", entity_id=user.id)
    return LoginResult(user, session, token, user.mfa_enabled)


def resolve_session(db: Session, token: str | None) -> UserSession | None:
    if not token:
        return None
    s = get_settings()
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    now = _now()
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        return None
    if session.last_seen_at + timedelta(minutes=s.session_idle_minutes) <= now:
        session.revoked_at = now
        db.commit()
        return None
    if not session.user.is_active:
        return None
    # Throttle last_seen writes to once a minute.
    if now - session.last_seen_at > timedelta(minutes=1):
        session.last_seen_at = now
    return session


def logout(db: Session, session: UserSession) -> None:
    session.revoked_at = _now()
    audit.record(db, action="user.logout", actor_user_id=session.user_id, entity_type="user", entity_id=session.user_id)


# ---- MFA (TOTP) ----

def mfa_setup(db: Session, user: User) -> str:
    if user.mfa_enabled:
        raise Conflict("MFA is already enabled", code="mfa_already_enabled")
    user.mfa_secret = pyotp.random_base32()
    return pyotp.TOTP(user.mfa_secret).provisioning_uri(name=user.email, issuer_name="Vittasynx")


def _check_code(user: User, code: str) -> bool:
    return bool(user.mfa_secret) and pyotp.TOTP(user.mfa_secret).verify(code.strip(), valid_window=1)


def mfa_enable(db: Session, user: User, session: UserSession, code: str) -> None:
    if user.mfa_enabled:
        raise Conflict("MFA is already enabled", code="mfa_already_enabled")
    if not _check_code(user, code):
        raise ValidationFailed("The code is incorrect", code="invalid_mfa_code")
    user.mfa_enabled = True
    session.mfa_verified = True
    audit.record(db, action="user.mfa_enabled", actor_user_id=user.id, entity_type="user", entity_id=user.id)


def mfa_verify(db: Session, session: UserSession, code: str) -> None:
    user = session.user
    if not _check_code(user, code):
        audit.record(db, action="user.mfa_failed", actor_user_id=user.id, entity_type="user", entity_id=user.id)
        db.commit()
        raise Unauthorised("The code is incorrect", code="invalid_mfa_code")
    session.mfa_verified = True
    audit.record(db, action="user.mfa_verified", actor_user_id=user.id, entity_type="user", entity_id=user.id)
