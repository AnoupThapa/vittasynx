"""Backend enforcement of the approved permission matrix (D-03). Hidden buttons are not protection."""
import pytest

from tests.conftest import import_file

ROLES = ["owner", "admin", "finance_manager", "ar_officer", "read_only"]


@pytest.fixture
def org_with_roles(make_user, make_org, add_member):
    owner = make_user()
    org = make_org(owner)
    users = {"owner": owner}
    for role in ROLES[1:]:
        users[role] = add_member(owner, org, role)
    cust = owner.post(f"/api/v1/orgs/{org}/customers", json={"name": "Customer One", "code": "C1"}).json()
    import_file(owner, org, "invoices", "inv.csv",
                "invoice_number,customer_code,customer_name,issue_date,due_date,total_amount\n"
                "INV-1,C1,Customer One,2026-01-01,2026-01-31,500.00\n")
    inv = owner.get(f"/api/v1/orgs/{org}/invoices?as_at=2026-03-01").json()["items"][0]
    pay = owner.post(f"/api/v1/orgs/{org}/payments", json={"customer_id": cust["id"], "payment_date": "2026-02-01",
                                                           "amount": "100.00", "reference": "base"}).json()
    return org, users, cust, inv, pay


# action -> roles allowed
MATRIX = {
    "view_dashboard": {"owner", "admin", "finance_manager", "ar_officer", "read_only"},
    "export": {"owner", "admin", "finance_manager", "ar_officer"},
    "create_customer": {"owner", "admin", "finance_manager", "ar_officer"},
    "upload_import": {"owner", "admin", "finance_manager", "ar_officer"},
    "record_payment": {"owner", "admin", "finance_manager", "ar_officer"},
    "manual_invoice": {"owner", "admin", "finance_manager", "ar_officer"},
    "confirm_allocation": {"owner", "admin", "finance_manager", "ar_officer"},
    "credit_note": {"owner", "admin", "finance_manager"},
    "invoice_status": {"owner", "admin", "finance_manager"},
    "view_audit": {"owner", "admin", "finance_manager"},
    "invite": {"owner", "admin"},
    "org_settings": {"owner", "admin"},
}


def _do(action, api, org, cust, inv, pay, n):
    base = f"/api/v1/orgs/{org}"
    if action == "view_dashboard":
        return api.get(f"{base}/dashboard")
    if action == "export":
        return api.get(f"{base}/exports/invoices.csv")
    if action == "create_customer":
        return api.post(f"{base}/customers", json={"name": f"New {n}", "code": f"N{n}"})
    if action == "upload_import":
        return api.upload(org, "invoices", "x.csv", b"invoice_number,customer_name\nA,B\n")
    if action == "record_payment":
        return api.post(f"{base}/payments", json={"customer_id": cust["id"], "payment_date": "2026-02-02",
                                                   "amount": "1.00", "reference": f"perm-{n}"})
    if action == "manual_invoice":
        return api.post(f"{base}/invoices", json={"customer_id": cust["id"], "invoice_number": f"MAN-{n}",
                                                   "issue_date": "2026-01-01", "due_date": "2026-01-31",
                                                   "total_amount": "5.00"})
    if action == "confirm_allocation":
        return api.post(f"{base}/allocations", json={"invoice_id": inv["id"], "payment_id": pay["id"], "amount": "1.00"})
    if action == "credit_note":
        return api.post(f"{base}/credit-notes", json={"customer_id": cust["id"], "credit_note_number": f"CN{n}",
                                                       "credit_date": "2026-02-01", "amount": "1.00"})
    if action == "invoice_status":
        return api.post(f"{base}/invoices/{inv['id']}/status", json={"status": "disputed", "reason": "test"})
    if action == "view_audit":
        return api.get(f"{base}/audit")
    if action == "invite":
        return api.post(f"{base}/invitations", json={"email": f"inv{n}@example.com", "role": "read_only"})
    if action == "org_settings":
        return api.patch(f"{base}", json={"name": "Renamed"})
    raise AssertionError(action)


def test_permission_matrix(org_with_roles):
    org, users, cust, inv, pay = org_with_roles
    n = 0
    for action, allowed in MATRIX.items():
        for role in ROLES:
            n += 1
            r = _do(action, users[role], org, cust, inv, pay, n)
            if role in allowed:
                assert r.status_code < 400, f"{role} should be allowed to {action}: {r.status_code} {r.text}"
            else:
                assert r.status_code == 403, f"{role} must not {action}: {r.status_code}"
                assert r.json()["error"]["code"] == "permission_denied"
            if action == "invoice_status" and r.status_code < 400:  # reset for the next role's attempt
                users["owner"].post(f"/api/v1/orgs/{org}/invoices/{inv['id']}/status",
                                    json={"status": "open", "reason": "reset"})


def test_reverse_allocation_requires_finance_manager(org_with_roles):
    org, users, cust, inv, pay = org_with_roles
    a = users["ar_officer"].post(f"/api/v1/orgs/{org}/allocations",
                                 json={"invoice_id": inv["id"], "payment_id": pay["id"], "amount": "10.00"}).json()
    r = users["ar_officer"].post(f"/api/v1/orgs/{org}/allocations/{a['id']}/reverse", json={"reason": "mistake"})
    assert r.status_code == 403
    assert users["finance_manager"].post(f"/api/v1/orgs/{org}/allocations/{a['id']}/reverse",
                                         json={"reason": "mistake"}).status_code == 200


def test_only_owner_transfers_ownership(org_with_roles):
    org, users, *_ = org_with_roles
    r = users["admin"].post(f"/api/v1/orgs/{org}/transfer-ownership", json={"user_id": users["read_only"].user_id})
    assert r.status_code == 403
