"""Any failure here is a release blocker (multi-tenancy.md)."""
import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from app.db import new_session, set_tenant
from app.models import Allocation, AuditEvent, Customer, ImportRow, Invoice, Payment, StoredFile
from tests.conftest import import_file

CSV = ("invoice_number,customer_code,customer_name,issue_date,due_date,total_amount\n"
       "A-1,C1,Alpha Customer,2026-01-01,2026-01-31,1000.00\n")


@pytest.fixture
def two_tenants(make_user, make_org):
    a, b = make_user(), make_user()
    org_a, org_b = make_org(a, "Org A"), make_org(b, "Org B")
    _, r = import_file(a, org_a, "invoices", "a.csv", CSV)
    assert r.status_code == 200, r.text
    batch_a = r.json()["id"]
    inv_a = a.get(f"/api/v1/orgs/{org_a}/invoices?as_at=2026-03-01").json()["items"][0]
    cust_a = inv_a["customer_id"]
    pay_a = a.post(f"/api/v1/orgs/{org_a}/payments", json={"customer_id": cust_a, "payment_date": "2026-02-01",
                                                           "amount": "100.00", "reference": "A"}).json()
    alloc_a = a.post(f"/api/v1/orgs/{org_a}/allocations", json={"invoice_id": inv_a["id"], "payment_id": pay_a["id"],
                                                                "amount": "100.00"}).json()
    cn_a = a.post(f"/api/v1/orgs/{org_a}/credit-notes", json={"customer_id": cust_a, "credit_note_number": "CN1",
                                                              "credit_date": "2026-02-02", "amount": "10.00"}).json()
    return {"a": a, "b": b, "org_a": org_a, "org_b": org_b, "inv": inv_a["id"], "cust": cust_a, "pay": pay_a["id"],
            "alloc": alloc_a["id"], "batch": batch_a, "cn": cn_a["id"]}


def test_member_of_b_cannot_use_org_a_url(two_tenants):
    t = two_tenants
    b, org_a = t["b"], t["org_a"]
    for path in ("", "/dashboard", "/customers", f"/customers/{t['cust']}", "/invoices", f"/invoices/{t['inv']}",
                 "/payments", f"/payments/{t['pay']}", "/credit-notes", f"/credit-notes/{t['cn']}", "/imports",
                 f"/imports/{t['batch']}", f"/imports/{t['batch']}/file", f"/imports/{t['batch']}/rows",
                 "/exports/invoices.csv", "/exports/ageing.csv", "/audit", "/members", "/amendments"):
        r = b.get(f"/api/v1/orgs/{org_a}{path}")
        assert r.status_code == 404, f"{path}: {r.status_code}"


def test_org_a_ids_through_org_b_url_are_not_found(two_tenants):
    """B uses its own org URL but A's record IDs: the records must not be reachable."""
    t = two_tenants
    b, org_b = t["b"], t["org_b"]
    assert b.get(f"/api/v1/orgs/{org_b}/invoices/{t['inv']}").status_code == 404
    assert b.get(f"/api/v1/orgs/{org_b}/customers/{t['cust']}").status_code == 404
    assert b.get(f"/api/v1/orgs/{org_b}/payments/{t['pay']}").status_code == 404
    assert b.get(f"/api/v1/orgs/{org_b}/credit-notes/{t['cn']}").status_code == 404
    assert b.get(f"/api/v1/orgs/{org_b}/imports/{t['batch']}").status_code == 404
    assert b.get(f"/api/v1/orgs/{org_b}/imports/{t['batch']}/file").status_code == 404
    assert b.get(f"/api/v1/orgs/{org_b}/customers/{t['cust']}/behaviour").status_code == 404


def test_cross_tenant_modification_attempts(two_tenants):
    t = two_tenants
    b, org_b = t["b"], t["org_b"]
    b_cust = b.post(f"/api/v1/orgs/{org_b}/customers", json={"name": "Beta"}).json()
    b_pay = b.post(f"/api/v1/orgs/{org_b}/payments", json={"customer_id": b_cust["id"], "payment_date": "2026-02-01",
                                                           "amount": "50.00"}).json()
    attempts = [
        b.patch(f"/api/v1/orgs/{org_b}/customers/{t['cust']}", json={"name": "Hacked"}),
        b.post(f"/api/v1/orgs/{org_b}/invoices/{t['inv']}/status", json={"status": "void", "reason": "x"}),
        b.post(f"/api/v1/orgs/{org_b}/allocations", json={"invoice_id": t["inv"], "payment_id": b_pay["id"], "amount": "1.00"}),
        b.post(f"/api/v1/orgs/{org_b}/allocations", json={"invoice_id": t["inv"], "payment_id": t["pay"], "amount": "1.00"}),
        b.post(f"/api/v1/orgs/{org_b}/allocations/{t['alloc']}/reverse", json={"reason": "x"}),
        b.post(f"/api/v1/orgs/{org_b}/payments", json={"customer_id": t["cust"], "payment_date": "2026-02-01", "amount": "1.00"}),
        b.post(f"/api/v1/orgs/{org_b}/payments/{t['pay']}/assign-customer", json={"customer_id": b_cust["id"]}),
        b.post(f"/api/v1/orgs/{org_b}/credit-notes", json={"customer_id": t["cust"], "credit_note_number": "X",
                                                           "credit_date": "2026-02-01", "amount": "1.00"}),
        b.post(f"/api/v1/orgs/{org_b}/imports/{t['batch']}/commit", json={}),
        b.post(f"/api/v1/orgs/{org_b}/payments/{b_pay['id']}/assign-customer", json={"customer_id": t["cust"]}),
    ]
    for r in attempts:
        assert r.status_code == 404, r.text
    # Nothing in A changed.
    inv = t["a"].get(f"/api/v1/orgs/{t['org_a']}/invoices/{t['inv']}?as_at=2026-03-01").json()
    assert inv["stored_status"] == "open" and inv["balance"] == "900.00"
    assert t["a"].get(f"/api/v1/orgs/{t['org_a']}/customers/{t['cust']}").json()["name"] == "Alpha Customer"


def test_org_b_lists_contain_nothing_from_a(two_tenants):
    t = two_tenants
    b, org_b = t["b"], t["org_b"]
    assert b.get(f"/api/v1/orgs/{org_b}/invoices").json()["items"] == []
    assert b.get(f"/api/v1/orgs/{org_b}/customers").json()["items"] == []
    assert b.get(f"/api/v1/orgs/{org_b}/payments").json()["items"] == []
    assert b.get(f"/api/v1/orgs/{org_b}/dashboard").json()["totals"]["total_outstanding"] == "0.00"
    actions = [e["action"] for e in b.get(f"/api/v1/orgs/{org_b}/audit").json()["items"]]
    assert "invoice.imported" not in actions and "allocation.confirmed" not in actions
    csv_text = b.get(f"/api/v1/orgs/{org_b}/exports/invoices.csv").text
    assert "A-1" not in csv_text and "Alpha" not in csv_text


def test_rls_without_tenant_context_returns_nothing(two_tenants):
    with new_session() as db:  # no app.current_org set
        for model in (Customer, Invoice, Payment, Allocation, ImportRow, StoredFile):
            assert db.scalar(select(func.count()).select_from(model)) == 0, model.__tablename__


def test_rls_with_other_tenant_context_returns_nothing(two_tenants):
    with new_session() as db:
        set_tenant(db, uuid.UUID(two_tenants["org_b"]))
        assert db.scalar(select(func.count()).select_from(Invoice)) == 0
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(
            AuditEvent.organisation_id == uuid.UUID(two_tenants["org_a"]))) == 0
    with new_session() as db:
        set_tenant(db, uuid.UUID(two_tenants["org_a"]))
        assert db.scalar(select(func.count()).select_from(Invoice)) == 1


def test_rls_blocks_writes_into_another_tenant(two_tenants):
    with new_session() as db:
        set_tenant(db, uuid.UUID(two_tenants["org_b"]))
        db.add(Customer(organisation_id=uuid.UUID(two_tenants["org_a"]), name="Injected", normalised_name="injected"))
        with pytest.raises((ProgrammingError, DBAPIError)):
            db.flush()
        db.rollback()
    with new_session() as db:
        set_tenant(db, uuid.UUID(two_tenants["org_b"]))
        # An UPDATE of A's rows from B's context affects nothing.
        res = db.execute(text("UPDATE invoices SET status='void'"))
        assert res.rowcount == 0
        db.commit()


def test_application_role_is_not_superuser_and_cannot_bypass_rls():
    with new_session() as db:
        row = db.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")).one()
        assert row == (False, False)
        forced = db.execute(text("SELECT count(*) FROM pg_class WHERE relname = ANY(:t) AND relforcerowsecurity"),
                            {"t": ["customers", "invoices", "payments", "allocations", "import_rows", "stored_files",
                                   "import_batches", "invoice_versions", "credit_notes"]}).scalar()
        assert forced == 9


def test_tenant_context_does_not_leak_between_requests(two_tenants):
    """After a request for org A, a request for org B on a pooled connection must not see A's data."""
    t = two_tenants
    for _ in range(5):
        assert t["a"].get(f"/api/v1/orgs/{t['org_a']}/invoices?as_at=2026-03-01").json()["items"]
        assert t["b"].get(f"/api/v1/orgs/{t['org_b']}/invoices?as_at=2026-03-01").json()["items"] == []
    with new_session() as db:
        assert db.execute(text("SELECT current_setting('app.current_org', true)")).scalar() in ("", None)
