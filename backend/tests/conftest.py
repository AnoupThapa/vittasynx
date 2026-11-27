"""Test harness: a real PostgreSQL database (with RLS active, non-superuser role), migrated with Alembic.

Set VX_TEST_DATABASE_URL to override the default local test database.
"""
import os
import tempfile

os.environ.setdefault("VX_ENVIRONMENT", "test")
os.environ["VX_DATABASE_URL"] = os.environ.get(
    "VX_TEST_DATABASE_URL", "postgresql+psycopg://vittasynx:devpassword@localhost:5432/vittasynx_test"
)
os.environ["VX_REQUIRE_MFA_FOR_PRIVILEGED"] = "false"
os.environ["VX_RATE_LIMIT_ENABLED"] = "false"  # enabled explicitly in test_hardening.py
os.environ["VX_FILE_STORAGE_DIR"] = tempfile.mkdtemp(prefix="vx-files-")

import io  # noqa: E402
import uuid  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text, update  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import new_session, reset_engine  # noqa: E402

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "correct horse battery staple"


def _truncate_all() -> None:
    with new_session() as db:
        tables = db.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'"
        )).scalars().all()
        if tables:
            db.execute(text("TRUNCATE " + ", ".join(tables) + " RESTART IDENTITY CASCADE"))
        db.commit()


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    _truncate_all()  # test data from a previous run must not block downgrades
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "migrations"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_db(migrated_db):
    _truncate_all()
    yield


@pytest.fixture
def settings_override():
    """Temporarily change settings, e.g. settings_override(require_mfa_for_privileged=True)."""
    changed = {}

    def apply(**kwargs):
        s = get_settings()
        for k, v in kwargs.items():
            changed.setdefault(k, getattr(s, k))
            setattr(s, k, v)

    yield apply
    s = get_settings()
    for k, v in changed.items():
        setattr(s, k, v)


class Api:
    """A signed-in browser-like client: holds cookies and sends the CSRF header automatically."""

    def __init__(self, client: TestClient):
        self.c = client
        self.user_id: str | None = None
        self.email: str | None = None

    def _headers(self, extra=None):
        h = {}
        csrf = self.c.cookies.get(get_settings().csrf_cookie_name)
        if csrf:
            h["x-csrf-token"] = csrf
        if extra:
            h.update(extra)
        return h

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def post(self, url, json=None, headers=None, **kw):
        return self.c.post(url, json=json, headers=self._headers(headers), **kw)

    def patch(self, url, json=None, headers=None, **kw):
        return self.c.patch(url, json=json, headers=self._headers(headers), **kw)

    def delete(self, url, headers=None, **kw):
        return self.c.delete(url, headers=self._headers(headers), **kw)

    def upload(self, org_id, kind, filename, content: bytes):
        return self.c.post(f"/api/v1/orgs/{org_id}/imports", data={"kind": kind},
                           files={"file": (filename, io.BytesIO(content))}, headers=self._headers())


@pytest.fixture
def app():
    from app.main import create_app

    return create_app()


@pytest.fixture
def make_client(app):
    clients = []

    def factory() -> Api:
        c = TestClient(app)
        clients.append(c)
        return Api(c)

    yield factory
    for c in clients:
        c.close()


def verify_email_directly(email: str) -> None:
    from app.models import User

    with new_session() as db:
        db.execute(update(User).where(User.email == email).values(email_verified_at=datetime.now(timezone.utc)))
        db.commit()


@pytest.fixture
def make_user(make_client):
    def factory(email: str | None = None, name: str = "Test User", verified: bool = True) -> Api:
        email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
        api = make_client()
        r = api.post("/api/v1/auth/register", json={"email": email, "full_name": name, "password": PASSWORD})
        assert r.status_code == 201, r.text
        if verified:
            verify_email_directly(email)
        r = api.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        api.user_id = r.json()["user"]["id"]
        api.email = email
        return api

    return factory


@pytest.fixture
def make_org():
    def factory(api: Api, name: str = "Acme Distribution", currency: str = "AUD", tz: str = "Australia/Sydney") -> str:
        r = api.post("/api/v1/orgs", json={"name": name, "currency": currency, "timezone": tz})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    return factory


def latest_email(to: str) -> str:
    from sqlalchemy import select

    from app.models import EmailOutbox

    with new_session() as db:
        msg = db.scalars(select(EmailOutbox).where(EmailOutbox.to_address == to).order_by(EmailOutbox.created_at.desc())).first()
        assert msg is not None, f"no email to {to}"
        return msg.body


def token_from_email(to: str) -> str:
    body = latest_email(to)
    return body.split("token=")[1].split()[0]


@pytest.fixture
def add_member(make_user):
    """Create a user and add them to org with role via a real invitation flow."""
    def factory(owner: Api, org_id: str, role: str, email: str | None = None) -> Api:
        member = make_user(email=email)
        r = owner.post(f"/api/v1/orgs/{org_id}/invitations", json={"email": member.email, "role": role})
        assert r.status_code == 201, r.text
        r = member.post("/api/v1/invitations/accept", json={"token": token_from_email(member.email)})
        assert r.status_code == 200, r.text
        return member

    return factory


INVOICE_CSV_HEADER = "invoice_number,customer_code,customer_name,issue_date,due_date,currency,total_amount,tax_amount,status\n"


def import_file(api: Api, org_id: str, kind: str, filename: str, content: str | bytes, mapping=None,
                date_format="YYYY-MM-DD", confirm=True, status_map=None, exclude_errors=False):
    data = content.encode() if isinstance(content, str) else content
    r = api.upload(org_id, kind, filename, data)
    assert r.status_code == 201, r.text
    batch = r.json()
    r = api.post(f"/api/v1/orgs/{org_id}/imports/{batch['id']}/validate",
                 json={"mapping": mapping or batch["mapping"], "date_format": date_format, "status_map": status_map})
    assert r.status_code == 200, r.text
    validated = r.json()
    r = api.post(f"/api/v1/orgs/{org_id}/imports/{batch['id']}/commit",
                 json={"confirm_new_customers": confirm, "exclude_errors": exclude_errors})
    return validated, r
