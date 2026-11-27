"""Database-level integrity: history cannot be silently altered, even by application code."""
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db import new_session, set_tenant
from app.models import AuditEvent
from tests.conftest import import_file

CSV = ("invoice_number,customer_code,customer_name,issue_date,due_date,total_amount\n"
       "D-1,C1,Delta,2026-01-01,2026-01-31,100.00\n")


@pytest.fixture
def setup(make_user, make_org):
    owner = make_user()
    org = make_org(owner)
    import_file(owner, org, "invoices", "d.csv", CSV)
    inv = owner.get(f"/api/v1/orgs/{org}/invoices?as_at=2026-03-01").json()["items"][0]
    pay = owner.post(f"/api/v1/orgs/{org}/payments", json={"customer_id": inv["customer_id"],
                                                           "payment_date": "2026-02-01", "amount": "40.00"}).json()
    alloc = owner.post(f"/api/v1/orgs/{org}/allocations", json={"invoice_id": inv["id"], "payment_id": pay["id"],
                                                                "amount": "40.00"}).json()
    return org, inv, alloc


def _db(org):
    db = new_session()
    set_tenant(db, uuid.UUID(org))
    return db


def test_audit_events_are_insert_only(setup):
    """Layer 1: RLS grants no UPDATE/DELETE policy, so tenant connections change nothing.
    Layer 2: a trigger raises for any role that could bypass RLS (e.g. a misconfigured superuser)."""
    org, *_ = setup
    with _db(org) as db:
        before = db.scalar(text("SELECT count(*) FROM audit_events"))
        assert before > 0
        assert db.execute(text("UPDATE audit_events SET action = 'tampered'")).rowcount == 0
        assert db.execute(text("DELETE FROM audit_events")).rowcount == 0
        db.commit()
        assert db.scalar(text("SELECT count(*) FROM audit_events")) == before
        assert db.scalar(select(AuditEvent).where(AuditEvent.action == "tampered")) is None
        trigger = db.scalar(text("SELECT tgenabled FROM pg_trigger WHERE tgname = 'audit_events_immutable'"))
        assert trigger == "O"  # enabled


def test_allocations_cannot_be_deleted_or_altered(setup):
    org, inv, alloc = setup
    with _db(org) as db:
        with pytest.raises(DBAPIError, match="cannot be deleted"):
            db.execute(text("DELETE FROM allocations"))
        db.rollback()
        with pytest.raises(DBAPIError, match="immutable"):
            db.execute(text("UPDATE allocations SET amount = 1"))
        db.rollback()
        db.execute(text("UPDATE allocations SET status='reversed', reversal_reason='t'"))
        with pytest.raises(DBAPIError, match="reversed allocation"):
            db.execute(text("UPDATE allocations SET status='confirmed'"))
        db.rollback()


def test_invoice_versions_are_immutable(setup):
    org, *_ = setup
    with _db(org) as db:
        with pytest.raises(DBAPIError, match="immutable"):
            db.execute(text("UPDATE invoice_versions SET change_reason='x'"))
        db.rollback()


def test_raw_import_values_are_immutable(setup):
    org, *_ = setup
    with _db(org) as db:
        with pytest.raises(DBAPIError, match="raw imported values"):
            db.execute(text("""UPDATE import_rows SET raw = '{"x":"y"}'::jsonb"""))
        db.rollback()
        with pytest.raises(DBAPIError, match="cannot be deleted"):
            db.execute(text("DELETE FROM import_rows"))
        db.rollback()


def test_check_constraints(setup):
    org, inv, _ = setup
    with _db(org) as db:
        for stmt in (
            "UPDATE invoices SET total_amount = -1",
            "UPDATE invoices SET status = 'paid'",  # paid is derived, never stored
            "UPDATE invoices SET due_date = issue_date - 1",
        ):
            with pytest.raises(IntegrityError):
                db.execute(text(stmt))
            db.rollback()


def test_invoice_identity_unique_within_customer(setup):
    org, inv, _ = setup
    with _db(org) as db:
        with pytest.raises(IntegrityError):
            db.execute(text(
                "INSERT INTO invoices (id, organisation_id, customer_id, invoice_number, normalised_number, issue_date,"
                " due_date, currency, total_amount, total_is_derived, status, version, created_at) "
                "SELECT gen_random_uuid(), organisation_id, customer_id, 'd-1', 'D-1', issue_date, due_date, currency,"
                " 1, false, 'open', 1, now() FROM invoices LIMIT 1"))
        db.rollback()
