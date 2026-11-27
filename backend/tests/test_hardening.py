"""Pre-launch hardening: rate limiting, MFA recovery codes, SMTP email, database file storage."""
import uuid

import pyotp
import pytest
from sqlalchemy import func, select

from app.db import new_session, set_tenant
from app.models import FileBlob
from tests.conftest import PASSWORD, import_file


# ---------- rate limiting ----------

def test_login_limited_per_account(make_client, settings_override):
    settings_override(rate_limit_enabled=True, login_limit_per_account=3)
    api = make_client()
    api.post("/api/v1/auth/register", json={"email": "rl@example.com", "full_name": "R", "password": PASSWORD})
    for _ in range(3):
        assert api.post("/api/v1/auth/login", json={"email": "rl@example.com", "password": "wrong password here"}).status_code == 401
    r = api.post("/api/v1/auth/login", json={"email": "RL@example.com", "password": PASSWORD})
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"
    assert r.json()["error"]["details"]["retry_after_seconds"] > 0
    # Another account from the same client is unaffected by the per-account limit.
    api.post("/api/v1/auth/register", json={"email": "other@example.com", "full_name": "O", "password": PASSWORD})
    assert api.post("/api/v1/auth/login", json={"email": "other@example.com", "password": PASSWORD}).status_code == 200


def test_login_limited_per_ip(make_client, settings_override):
    settings_override(rate_limit_enabled=True, login_limit_per_ip=2, login_limit_per_account=100)
    api = make_client()
    for i in range(2):
        api.post("/api/v1/auth/login", json={"email": f"x{i}@example.com", "password": "whatever password"})
    assert api.post("/api/v1/auth/login", json={"email": "y@example.com", "password": "whatever password"}).status_code == 429


def test_forwarded_for_only_trusted_when_configured(make_client, settings_override):
    settings_override(rate_limit_enabled=True, login_limit_per_ip=1, login_limit_per_account=100)
    api = make_client()
    body = {"email": "z@example.com", "password": "whatever password"}
    api.post("/api/v1/auth/login", json=body, headers={"x-forwarded-for": "1.1.1.1"})
    # Spoofed header ignored by default: same client IP, so limited.
    assert api.post("/api/v1/auth/login", json=body, headers={"x-forwarded-for": "2.2.2.2"}).status_code == 429
    settings_override(trust_forwarded_for=True)
    assert api.post("/api/v1/auth/login", json=body, headers={"x-forwarded-for": "3.3.3.3"}).status_code == 401


def test_register_and_reset_limits(make_client, settings_override):
    settings_override(rate_limit_enabled=True, register_limit_per_ip=2, reset_limit_per_account=1)
    api = make_client()
    for i in range(2):
        assert api.post("/api/v1/auth/register", json={"email": f"r{i}@example.com", "full_name": "R", "password": PASSWORD}).status_code == 201
    assert api.post("/api/v1/auth/register", json={"email": "r9@example.com", "full_name": "R", "password": PASSWORD}).status_code == 429
    assert api.post("/api/v1/auth/password-reset/request", json={"email": "r0@example.com"}).status_code == 200
    assert api.post("/api/v1/auth/password-reset/request", json={"email": "r0@example.com"}).status_code == 429


# ---------- MFA recovery codes ----------

def _enable_mfa(api):
    secret = api.post("/api/v1/auth/mfa/setup").json()["secret"]
    r = api.post("/api/v1/auth/mfa/enable", json={"code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200
    return secret, r.json()["recovery_codes"]


def test_recovery_codes_issued_once_and_single_use(make_user, make_client):
    api = make_user(email="mfa-rc@example.com")
    secret, codes = _enable_mfa(api)
    assert len(codes) == 10 and len(set(codes)) == 10 and all(len(c) == 11 and c[5] == "-" for c in codes)
    assert api.get("/api/v1/auth/mfa/recovery-codes").json() == {"remaining": 10}

    other = make_client()
    other.post("/api/v1/auth/login", json={"email": "mfa-rc@example.com", "password": PASSWORD})
    assert other.post("/api/v1/auth/mfa/verify", json={"code": codes[0].upper()}).status_code == 200  # case/dash tolerant
    assert other.get("/api/v1/auth/me").status_code == 200

    third = make_client()
    third.post("/api/v1/auth/login", json={"email": "mfa-rc@example.com", "password": PASSWORD})
    assert third.post("/api/v1/auth/mfa/verify", json={"code": codes[0]}).status_code == 401  # already used
    assert api.get("/api/v1/auth/mfa/recovery-codes").json() == {"remaining": 9}


def test_recovery_codes_stored_hashed_and_regeneration_needs_totp(make_user):
    from app.models import MfaRecoveryCode

    api = make_user()
    secret, codes = _enable_mfa(api)
    with new_session() as db:
        hashes = db.scalars(select(MfaRecoveryCode.code_hash)).all()
    assert not any(c.replace("-", "") in h or c in h for c in codes for h in hashes)
    assert api.post("/api/v1/auth/mfa/recovery-codes", json={"code": codes[1]}).status_code == 422  # recovery code is not enough
    r = api.post("/api/v1/auth/mfa/recovery-codes", json={"code": pyotp.TOTP(secret).now()})
    new_codes = r.json()["recovery_codes"]
    assert len(new_codes) == 10 and not set(new_codes) & set(codes)


def test_mfa_verify_is_rate_limited(make_user, make_client, settings_override):
    api = make_user(email="mfa-rl@example.com")
    _enable_mfa(api)
    settings_override(rate_limit_enabled=True, mfa_limit_per_session=3)
    other = make_client()
    other.post("/api/v1/auth/login", json={"email": "mfa-rl@example.com", "password": PASSWORD})
    for _ in range(3):
        assert other.post("/api/v1/auth/mfa/verify", json={"code": "000000"}).status_code == 401
    assert other.post("/api/v1/auth/mfa/verify", json={"code": "000000"}).status_code == 429


# ---------- SMTP email ----------

class FakeSMTP:
    sent: list = []

    def __init__(self, host, port, timeout):
        self.host, self.port = host, port
        self.started_tls = False
        self.logged_in = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, user, pw):
        self.logged_in = user

    def send_message(self, msg):
        FakeSMTP.sent.append((self, msg))


def test_smtp_backend_sends_and_nothing_stored(make_client, settings_override, monkeypatch):
    import smtplib

    from app.models import EmailOutbox

    FakeSMTP.sent = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    settings_override(email_backend="smtp", smtp_host="smtp.example.com", smtp_username="apikey",
                      smtp_password="secret", email_from="Vittasynx <no-reply@example.com>")
    api = make_client()
    assert api.post("/api/v1/auth/register", json={"email": "mail@example.com", "full_name": "M", "password": PASSWORD}).status_code == 201
    conn, msg = FakeSMTP.sent[0]
    assert conn.host == "smtp.example.com" and conn.started_tls and conn.logged_in == "apikey"
    assert msg["To"] == "mail@example.com" and "verify-email?token=" in msg.get_content()
    with new_session() as db:
        assert db.scalar(select(func.count()).select_from(EmailOutbox)) == 0


def test_smtp_requires_host_outside_development():
    from app.config import Settings

    s = Settings(_env_file=None, environment="staging", cookie_secure=True, email_backend="smtp", smtp_host="",
                 database_url="postgresql+psycopg://app:strong@db/vx")
    with pytest.raises(RuntimeError, match="SMTP_HOST"):
        s.validate_for_runtime()


# ---------- database file storage ----------

def test_database_storage_roundtrip_and_tenant_isolation(make_user, make_org, settings_override):
    settings_override(storage_backend="database")
    a, b = make_user(), make_user()
    org_a, org_b = make_org(a, "A"), make_org(b, "B")
    csv = "invoice_number,customer_name,issue_date,due_date,total_amount\nI-1,Alpha,2026-01-01,2026-01-31,10.00\n"
    _, r = import_file(a, org_a, "invoices", "a.csv", csv)
    batch = r.json()["id"]
    assert a.get(f"/api/v1/orgs/{org_a}/imports/{batch}/file").content == csv.encode()
    assert b.get(f"/api/v1/orgs/{org_a}/imports/{batch}/file").status_code == 404
    with new_session() as db:  # RLS: no tenant context, no blobs visible
        assert db.scalar(select(func.count()).select_from(FileBlob)) == 0
    with new_session() as db:
        set_tenant(db, uuid.UUID(org_b))
        assert db.scalar(select(func.count()).select_from(FileBlob)) == 0
    with new_session() as db:
        set_tenant(db, uuid.UUID(org_a))
        assert db.scalar(select(func.count()).select_from(FileBlob)) == 1
