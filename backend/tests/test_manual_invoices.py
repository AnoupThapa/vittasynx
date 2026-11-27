"""Manual invoice entry (rules.md §8.12): same rules as import, no shortcuts."""
import pytest


@pytest.fixture
def setup(make_user, make_org):
    api = make_user()
    org = make_org(api)
    alpha = api.post(f"/api/v1/orgs/{org}/customers", json={"name": "Alpha", "code": "A"}).json()
    beta = api.post(f"/api/v1/orgs/{org}/customers", json={"name": "Beta", "code": "B"}).json()
    return api, org, alpha["id"], beta["id"]


def body(customer_id, **kw):
    b = {"customer_id": customer_id, "invoice_number": "M-1", "issue_date": "2026-01-05", "due_date": "2026-02-04",
         "total_amount": "1100.00", "tax_amount": "100.00"}
    b.update(kw)
    return b


def test_create_and_appears_in_receivables(setup):
    api, org, alpha, _ = setup
    r = api.post(f"/api/v1/orgs/{org}/invoices", json=body(alpha))
    assert r.status_code == 201 and r.json()["entry_method"] == "manual"
    inv = api.get(f"/api/v1/orgs/{org}/invoices/{r.json()['id']}?as_at=2026-03-31").json()
    assert inv["balance"] == "1100.00" and inv["status"] == "overdue" and inv["entry_method"] == "manual"
    assert inv["versions"][0]["reason"] == "entered manually"
    assert "invoice.created_manual" in [h["action"] for h in inv["history"]]
    dash = api.get(f"/api/v1/orgs/{org}/dashboard?as_at=2026-03-31").json()
    assert dash["totals"]["total_outstanding"] == "1100.00"


def test_total_derived_from_net_plus_tax(setup):
    api, org, alpha, _ = setup
    r = api.post(f"/api/v1/orgs/{org}/invoices", json=body(alpha, total_amount=None, net_amount="1,000.00", tax_amount="100.00"))
    assert r.json()["total_amount"] == "1100.00" and r.json()["total_is_derived"] is True


@pytest.mark.parametrize("override,code", [
    ({"total_amount": "1100.005", "tax_amount": None}, "invalid_amount"),
    ({"total_amount": "-5.00", "tax_amount": None}, "invalid_amount"),
    ({"total_amount": "1200.00", "net_amount": "1000.00", "tax_amount": "100.00"}, "invalid_amount"),
    ({"total_amount": None, "tax_amount": None}, "invalid_amount"),
    ({"due_date": "2026-01-01"}, "validation_failed"),
    ({"invoice_number": "   "}, "validation_failed"),
])
def test_validation_matches_import_rules(setup, override, code):
    api, org, alpha, _ = setup
    r = api.post(f"/api/v1/orgs/{org}/invoices", json=body(alpha, **override))
    assert r.status_code == 422 and r.json()["error"]["code"] == code
    assert api.get(f"/api/v1/orgs/{org}/invoices").json()["items"] == []


def test_duplicate_rules(setup):
    api, org, alpha, beta = setup
    assert api.post(f"/api/v1/orgs/{org}/invoices", json=body(alpha)).status_code == 201
    r = api.post(f"/api/v1/orgs/{org}/invoices", json=body(alpha, invoice_number=" m-1 "))
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_invoice"
    r = api.post(f"/api/v1/orgs/{org}/invoices", json=body(beta))
    assert r.status_code == 409 and r.json()["error"]["code"] == "invoice_number_used_elsewhere"
    assert api.post(f"/api/v1/orgs/{org}/invoices", json=body(beta, confirm_duplicate_number=True)).status_code == 201


def test_manual_invoice_then_import_of_same_invoice_is_duplicate(setup):
    from tests.conftest import import_file

    api, org, alpha, _ = setup
    api.post(f"/api/v1/orgs/{org}/invoices", json=body(alpha, tax_amount=None))
    validated, r = import_file(api, org, "invoices", "x.csv",
                               "invoice_number,customer_code,customer_name,issue_date,due_date,total_amount\n"
                               "M-1,A,Alpha,2026-01-05,2026-02-04,1100.00\n")
    assert validated["summary"]["by_status"] == {"duplicate": 1}


def test_permissions_and_tenant_scope(setup, add_member, make_user, make_org):
    api, org, alpha, _ = setup
    ro = add_member(api, org, "read_only")
    assert ro.post(f"/api/v1/orgs/{org}/invoices", json=body(alpha)).status_code == 403
    ar = add_member(api, org, "ar_officer")
    assert ar.post(f"/api/v1/orgs/{org}/invoices", json=body(alpha)).status_code == 201
    other = make_user()
    other_org = make_org(other, "Other")
    # Another tenant cannot create an invoice for this organisation's customer, via either URL.
    assert other.post(f"/api/v1/orgs/{org}/invoices", json=body(alpha, invoice_number="X")).status_code == 404
    assert other.post(f"/api/v1/orgs/{other_org}/invoices", json=body(alpha, invoice_number="X")).status_code == 404
