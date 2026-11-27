from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import current_session, current_user, pending_session
from app.config import get_settings
from app.core.errors import Forbidden
from app.core.permissions import ROLE_LABELS
from app.db import get_db
from app.models import User, UserSession
from app.services import identity, organisations
from app.services.ratelimit import client_ip, hashed, hit

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=256)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=256)


class TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class ResetRequestIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(max_length=256)


class CodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=12)  # 6-digit TOTP or a recovery code like abcde-fghjk


def user_out(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "email_verified": user.email_verified_at is not None,
        "mfa_enabled": user.mfa_enabled,
    }


def _set_cookies(response: Response, token: str, csrf: str) -> None:
    s = get_settings()
    max_age = s.session_absolute_hours * 3600
    response.set_cookie(s.session_cookie_name, token, httponly=True, secure=s.cookie_secure, samesite="lax",
                        max_age=max_age, path="/")
    # Readable by the frontend so it can echo it in X-CSRF-Token (double-submit).
    response.set_cookie(s.csrf_cookie_name, csrf, httponly=False, secure=s.cookie_secure, samesite="lax",
                        max_age=max_age, path="/")


def _clear_cookies(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(s.session_cookie_name, path="/")
    response.delete_cookie(s.csrf_cookie_name, path="/")


@router.post("/register", status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)) -> dict:
    s = get_settings()
    hit(db, f"register:ip:{client_ip(request)}", s.register_limit_per_ip, 3600)
    user = identity.register(db, body.email, body.full_name, body.password)
    db.commit()
    return {"user": user_out(user), "message": "Account created. Check your email to verify your address."}


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    s = get_settings()
    hit(db, f"login:ip:{client_ip(request)}", s.login_limit_per_ip, 900)
    hit(db, f"login:acct:{hashed(body.email)}", s.login_limit_per_account, 900)
    result = identity.login(db, body.email, body.password)
    db.commit()
    _set_cookies(response, result.token, result.session.csrf_token)
    return {"user": user_out(result.user), "mfa_required": result.mfa_required}


@router.post("/mfa/verify")
def mfa_verify(body: CodeIn, session: UserSession = Depends(pending_session), db: Session = Depends(get_db)) -> dict:
    hit(db, f"mfa:session:{session.id}", get_settings().mfa_limit_per_session, 900)
    identity.mfa_verify(db, session, body.code)
    db.commit()
    return {"user": user_out(session.user), "mfa_required": False}


@router.post("/logout")
def logout(response: Response, session: UserSession = Depends(pending_session), db: Session = Depends(get_db)) -> dict:
    identity.logout(db, session)
    db.commit()
    _clear_cookies(response)
    return {"ok": True}


@router.get("/me")
def me(session: UserSession = Depends(current_session), db: Session = Depends(get_db)) -> dict:
    memberships = organisations.memberships_for(db, session.user)
    return {
        "user": user_out(session.user),
        "organisations": [
            {
                "id": str(m.organisation_id),
                "name": m.organisation.name,
                "currency": m.organisation.currency,
                "timezone": m.organisation.timezone,
                "is_demo": m.organisation.is_demo,
                "role": m.role,
                "role_label": ROLE_LABELS[m.role],
            }
            for m in memberships
        ],
        "mfa_required_for_privileged": get_settings().require_mfa_for_privileged,
    }


@router.post("/verify-email")
def verify_email(body: TokenIn, db: Session = Depends(get_db)) -> dict:
    user = identity.verify_email(db, body.token)
    db.commit()
    return {"user": user_out(user)}


@router.post("/resend-verification")
def resend_verification(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    identity.resend_verification(db, user)
    db.commit()
    return {"ok": True}


@router.post("/password-reset/request")
def password_reset_request(body: ResetRequestIn, request: Request, db: Session = Depends(get_db)) -> dict:
    s = get_settings()
    hit(db, f"reset:ip:{client_ip(request)}", s.reset_limit_per_ip, 3600)
    hit(db, f"reset:acct:{hashed(body.email)}", s.reset_limit_per_account, 3600)
    identity.request_password_reset(db, body.email)
    db.commit()
    return {"message": "If an account exists for that email, a reset link has been sent."}


@router.post("/password-reset/confirm")
def password_reset_confirm(body: ResetIn, db: Session = Depends(get_db)) -> dict:
    identity.reset_password(db, body.token, body.new_password)
    db.commit()
    return {"message": "Password updated. Sign in with your new password."}


@router.post("/mfa/setup")
def mfa_setup(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    uri = identity.mfa_setup(db, user)
    db.commit()
    return {"otpauth_uri": uri, "secret": user.mfa_secret}


@router.post("/mfa/enable")
def mfa_enable(body: CodeIn, session: UserSession = Depends(current_session), db: Session = Depends(get_db)) -> dict:
    codes = identity.mfa_enable(db, session.user, session, body.code)
    db.commit()
    return {"user": user_out(session.user), "recovery_codes": codes,
            "message": "Save these recovery codes somewhere safe. Each works once; they will not be shown again."}


@router.get("/mfa/recovery-codes")
def recovery_status(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return {"remaining": identity.remaining_recovery_codes(db, user)}


@router.post("/mfa/recovery-codes")
def regenerate_recovery_codes(body: CodeIn, session: UserSession = Depends(current_session), db: Session = Depends(get_db)) -> dict:
    """Requires a current authenticator code, so a stolen session alone cannot mint new codes."""
    user = session.user
    if not user.mfa_enabled or not identity._check_code(user, body.code):
        from app.core.errors import ValidationFailed

        raise ValidationFailed("Enter a current code from your authenticator app", code="invalid_mfa_code")
    codes = identity.issue_recovery_codes(db, user)
    db.commit()
    return {"recovery_codes": codes}


@router.get("/dev/outbox")
def dev_outbox(request: Request, db: Session = Depends(get_db)) -> dict:
    """Development-only: shows emails that would have been sent. Disabled outside development."""
    if get_settings().environment != "development":
        raise Forbidden("Not available", code="not_available")
    from sqlalchemy import select

    from app.models import EmailOutbox

    rows = db.scalars(select(EmailOutbox).order_by(EmailOutbox.created_at.desc()).limit(20))
    return {"messages": [{"to": r.to_address, "subject": r.subject, "body": r.body, "at": r.created_at.isoformat()} for r in rows]}
