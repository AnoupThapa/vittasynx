import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedMixin, IdMixin

ROLES = ("owner", "admin", "finance_manager", "ar_officer", "read_only")
_ROLE_CHECK = "role IN ('owner','admin','finance_manager','ar_officer','read_only')"


class User(IdMixin, CreatedMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)  # stored lower-case
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class UserSession(IdMixin, CreatedMixin, Base):
    __tablename__ = "user_sessions"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(nullable=False)
    mfa_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    user: Mapped[User] = relationship()


class UserToken(IdMixin, CreatedMixin, Base):
    """Single-use tokens for email verification and password reset. Only the hash is stored."""

    __tablename__ = "user_tokens"
    __table_args__ = (CheckConstraint("purpose IN ('verify_email','reset_password')", name="ck_user_tokens_purpose"),)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Organisation(IdMixin, CreatedMixin, Base):
    __tablename__ = "organisations"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)  # fixed at creation (D-07)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)  # IANA (D-16)


class Membership(IdMixin, CreatedMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("organisation_id", "user_id", name="uq_membership_org_user"),
        CheckConstraint(_ROLE_CHECK, name="ck_memberships_role"),
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    user: Mapped[User] = relationship()
    organisation: Mapped[Organisation] = relationship()


class Invitation(IdMixin, CreatedMixin, Base):
    __tablename__ = "invitations"
    __table_args__ = (CheckConstraint(_ROLE_CHECK.replace("'owner',", ""), name="ck_invitations_role"),)
    organisation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    invited_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)


class EmailOutbox(IdMixin, CreatedMixin, Base):
    """Development-only email sink. Refused in staging/production by Settings.validate_for_runtime."""

    __tablename__ = "email_outbox"
    to_address: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)


class MfaRecoveryCode(IdMixin, CreatedMixin, Base):
    """Single-use backup codes for two-factor login. Only hashes are stored."""

    __tablename__ = "mfa_recovery_codes"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(nullable=True)


class RateLimitHit(Base):
    """Fixed-window request counters shared by all app instances (stored in PostgreSQL)."""

    __tablename__ = "rate_limit_hits"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
