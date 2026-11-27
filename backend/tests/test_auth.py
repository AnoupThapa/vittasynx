from datetime import datetime, timedelta, timezone

import pyotp
import pytest
from sqlalchemy import select, update

from app.db import new_session
from app.models import AuditEvent, User, UserSession
from tests.conftest import PASSWORD, token_from_email


def test_register_login_me_logout(make_client):
    api = make_client()
    r = api.post("/api/v1/auth/register", json={"email": "Owner@Example.com", "full_name": "Olive Owner", "password": PASSWORD})
    assert r.status_code == 201
    assert r.json()["user"]["email"] == "owner@example.com"
    assert api.get("/api/v1/auth/me").status_code == 401  # registration does not sign in

    r = api.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD})
    assert r.status_code == 200 and r.json()["mfa_required"] is False
    cookie = r.headers.get_list("set-cookie")
    assert any("vx_session=" in c and "HttpOnly" in c and "SameSite=lax" in c for c in cookie)
    assert api.get("/api/v1/auth/me").json()["user"]["full_name"] == "Olive Owner"

    assert api.post("/api/v1/auth/logout").status_code == 200
    assert api.get("/api/v1/auth/me").status_code == 401


def test_duplicate_email_and_weak_password(make_client):
    api = make_client()
    assert api.post("/api/v1/auth/register", json={"email": "a@example.com", "full_name": "A", "password": "short"}).json()["error"]["code"] == "weak_password"
    assert api.post("/api/v1/auth/register", json={"email": "a@example.com", "full_name": "A", "password": PASSWORD}).status_code == 201
    r = api.post("/api/v1/auth/register", json={"email": "A@example.com", "full_name": "A", "password": PASSWORD})
    assert r.status_code == 409


def test_wrong_password_and_unknown_email_look_the_same(make_client):
    api = make_client()
    api.post("/api/v1/auth/register", json={"email": "b@example.com", "full_name": "B", "password": PASSWORD})
    r1 = api.post("/api/v1/auth/login", json={"email": "b@example.com", "password": "wrong password here"})
    r2 = api.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong password here"})
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["error"] == r2.json()["error"]


def test_account_lockout(make_client, settings_override):
    settings_override(max_failed_logins=3)
    api = make_client()
    api.post("/api/v1/auth/register", json={"email": "c@example.com", "full_name": "C", "password": PASSWORD})
    for _ in range(3):
        api.post("/api/v1/auth/login", json={"email": "c@example.com", "password": "wrong password here"})
    r = api.post("/api/v1/auth/login", json={"email": "c@example.com", "password": PASSWORD})
    assert r.status_code == 401 and r.json()["error"]["code"] == "account_locked"


def test_csrf_required_for_writes(make_user):
    api = make_user()
    r = api.c.post("/api/v1/orgs", json={"name": "X", "currency": "AUD", "timezone": "Australia/Sydney"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_failed"
    r = api.c.post("/api/v1/orgs", json={"name": "X", "currency": "AUD", "timezone": "Australia/Sydney"},
                   headers={"x-csrf-token": "forged"})
    assert r.status_code == 403
    assert api.post("/api/v1/orgs", json={"name": "X", "currency": "AUD", "timezone": "Australia/Sydney"}).status_code == 201


def test_session_idle_expiry(make_user):
    api = make_user()
    with new_session() as db:
        db.execute(update(UserSession).values(last_seen_at=datetime.now(timezone.utc) - timedelta(hours=2)))
        db.commit()
    assert api.get("/api/v1/auth/me").status_code == 401


def test_session_absolute_expiry(make_user):
    api = make_user()
    with new_session() as db:
        db.execute(update(UserSession).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        db.commit()
    assert api.get("/api/v1/auth/me").status_code == 401


def test_session_token_stored_only_as_hash(make_user):
    api = make_user()
    raw = api.c.cookies.get("vx_session")
    with new_session() as db:
        hashes = db.scalars(select(UserSession.token_hash)).all()
    assert raw not in hashes and len(hashes[0]) == 64


def test_email_verification(make_client):
    api = make_client()
    api.post("/api/v1/auth/register", json={"email": "v@example.com", "full_name": "V", "password": PASSWORD})
    token = token_from_email("v@example.com")
    assert api.post("/api/v1/auth/verify-email", json={"token": token}).json()["user"]["email_verified"] is True
    assert api.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 422  # single use


def test_password_reset_flow_revokes_sessions(make_user, make_client):
    api = make_user(email="r@example.com")
    anon = make_client()
    r = anon.post("/api/v1/auth/password-reset/request", json={"email": "r@example.com"})
    assert r.status_code == 200
    # Unknown emails get the same response (no account enumeration).
    assert anon.post("/api/v1/auth/password-reset/request", json={"email": "nobody@example.com"}).json() == r.json()
    token = token_from_email("r@example.com")
    assert anon.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": "short"}).status_code == 422
    token2 = token_from_email("r@example.com")
    assert token2 == token  # failed attempt did not consume the token
    r = anon.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": "a brand new long password"})
    assert r.status_code == 200
    assert api.get("/api/v1/auth/me").status_code == 401  # old session revoked
    assert anon.post("/api/v1/auth/login", json={"email": "r@example.com", "password": PASSWORD}).status_code == 401
    assert anon.post("/api/v1/auth/login", json={"email": "r@example.com", "password": "a brand new long password"}).status_code == 200
    assert anon.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": "another long password"}).status_code == 422


def test_mfa_enrolment_and_login(make_user, make_client):
    api = make_user(email="m@example.com")
    secret = api.post("/api/v1/auth/mfa/setup").json()["secret"]
    assert api.post("/api/v1/auth/mfa/enable", json={"code": "000000"}).status_code == 422
    assert api.post("/api/v1/auth/mfa/enable", json={"code": pyotp.TOTP(secret).now()}).status_code == 200

    other = make_client()
    r = other.post("/api/v1/auth/login", json={"email": "m@example.com", "password": PASSWORD})
    assert r.json()["mfa_required"] is True
    r = other.get("/api/v1/auth/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "mfa_required"
    assert other.post("/api/v1/auth/mfa/verify", json={"code": "123456"}).status_code == 401
    assert other.post("/api/v1/auth/mfa/verify", json={"code": pyotp.TOTP(secret).now()}).status_code == 200
    assert other.get("/api/v1/auth/me").status_code == 200


def test_mfa_enforced_for_privileged_roles(make_user, make_org, add_member, settings_override):
    owner = make_user()
    org = make_org(owner)
    ar = add_member(owner, org, "ar_officer")
    settings_override(require_mfa_for_privileged=True)
    r = owner.get(f"/api/v1/orgs/{org}/dashboard")
    assert r.status_code == 403 and r.json()["error"]["code"] == "mfa_enrolment_required"
    assert ar.get(f"/api/v1/orgs/{org}/dashboard").status_code == 200  # non-privileged roles unaffected
    secret = owner.post("/api/v1/auth/mfa/setup").json()["secret"]
    owner.post("/api/v1/auth/mfa/enable", json={"code": pyotp.TOTP(secret).now()})
    assert owner.get(f"/api/v1/orgs/{org}/dashboard").status_code == 200


def test_login_is_audited_without_password(make_user):
    make_user(email="audit@example.com")
    with new_session() as db:
        user = db.scalar(select(User).where(User.email == "audit@example.com"))
        actions = db.scalars(select(AuditEvent.action).where(AuditEvent.actor_user_id == user.id)).all()
    assert "user.login" in actions and "user.registered" in actions


def test_health(make_client):
    api = make_client()
    assert api.get("/api/health").json() == {"status": "ok"}
    assert api.get("/api/health/ready").json()["database"] == "ok"


def test_unconfigured_environment_is_treated_as_production(monkeypatch):
    from app.config import Settings

    monkeypatch.delenv("VX_ENVIRONMENT", raising=False)
    s = Settings(_env_file=None)
    assert s.environment == "production"
    with pytest.raises(RuntimeError):
        s.validate_for_runtime()  # dev email outbox, insecure cookies and dev credentials are refused


def test_dev_outbox_endpoint_disabled_outside_development(make_client):
    r = make_client().get("/api/v1/auth/dev/outbox")
    assert r.status_code == 403
