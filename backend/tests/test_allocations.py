"""Workflow 3 (payment allocation). Synthetic data with hand-verified expected results."""
import threading

import pytest

from tests.conftest import import_file

H = "invoice_number,customer_code,customer_name,issue_date,due_date,total_amount\n"


@pytest.fixture
def ledger(make_user, make_org):
    api = make_user()
    org = make_org(api)
    import_file(api, org, "invoices", "inv.csv", H +
                "INV-1,C1,Alpha,2026-01-05,2026-02-04,1100.00\n"
                "INV-2,C1,Alpha,2026-01-10,2026-02-09,550.00\n"
                "INV-3,C2,Beta,2026-01-15,2026-02-14,300.00\n")
    invs = {i["invoice_number"]: i for i in api.get(f"/api/v1/orgs/{org}/invoices?as_at=2026-06-30").json()["items"]}
    return api, org, invs


def pay(api, org, customer_id, amount, date="2026-02-01", ref=None):
    r = api.post(f"/api/v1/orgs/{org}/payments", json={"customer_id": customer_id, "payment_date": date,
                                                       "amount": amount, "reference": ref or f"{amount}-{date}"})
    assert r.status_code == 201, r.text
    return r.json()


def alloc(api, org, invoice_id, amount, payment_id=None, credit_note_id=None):
    return api.post(f"/api/v1/orgs/{org}/allocations", json={"invoice_id": invoice_id, "amount": amount,
                                                             "payment_id": payment_id, "credit_note_id": credit_note_id})


def balance(api, org, invoice_id, as_at="2026-06-30"):
    return api.get(f"/api/v1/orgs/{org}/invoices/{invoice_id}?as_at={as_at}").json()["balance"]


def test_one_invoice_multiple_partial_payments(ledger):
    api, org, invs = ledger
    i1 = invs["INV-1"]
    p1, p2 = pay(api, org, i1["customer_id"], "300.00", "2026-02-10"), pay(api, org, i1["customer_id"], "250.00", "2026-03-05")
    assert alloc(api, org, i1["id"], "300.00", p1["id"]).status_code == 201
    assert alloc(api, org, i1["id"], "250.00", p2["id"]).status_code == 201
    assert balance(api, org, i1["id"]) == "550.00"
    assert balance(api, org, i1["id"], "2026-02-28") == "800.00"  # point-in-time
    d = api.get(f"/api/v1/orgs/{org}/invoices/{i1['id']}").json()
    assert d["payments_allocated"] == "550.00" and len(d["allocations"]) == 2


def test_one_payment_split_across_invoices_with_unapplied_remainder(ledger):
    api, org, invs = ledger
    p = pay(api, org, invs["INV-1"]["customer_id"], "2000.00")
    assert alloc(api, org, invs["INV-1"]["id"], "1100.00", p["id"]).status_code == 201
    assert alloc(api, org, invs["INV-2"]["id"], "550.00", p["id"]).status_code == 201
    detail = api.get(f"/api/v1/orgs/{org}/payments/{p['id']}").json()
    assert detail["allocated"] == "1650.00" and detail["unapplied"] == "350.00"
    dash = api.get(f"/api/v1/orgs/{org}/dashboard?as_at=2026-06-30").json()
    assert dash["totals"]["unapplied_payments"] == "350.00"
    assert dash["totals"]["total_outstanding"] == "300.00"  # unapplied cash is not netted
    assert dash["totals"]["net_position"] == "-50.00"


def test_over_allocation_is_blocked(ledger):
    api, org, invs = ledger
    i3 = invs["INV-3"]
    p = pay(api, org, i3["customer_id"], "500.00")
    r = alloc(api, org, i3["id"], "300.01", p["id"])
    assert r.status_code == 422 and r.json()["error"]["code"] == "exceeds_invoice"
    assert r.json()["error"]["details"]["invoice_balance"] == "300.00"
    small = pay(api, org, i3["customer_id"], "100.00")
    r = alloc(api, org, i3["id"], "100.01", small["id"])
    assert r.json()["error"]["code"] == "exceeds_source"
    assert alloc(api, org, i3["id"], "300.00", p["id"]).status_code == 201
    r = alloc(api, org, i3["id"], "0.01", small["id"])
    assert r.json()["error"]["code"] == "exceeds_invoice"  # fully paid


@pytest.mark.parametrize("amount", ["0", "-5.00", "1.001", "abc"])
def test_invalid_allocation_amounts(ledger, amount):
    api, org, invs = ledger
    p = pay(api, org, invs["INV-3"]["customer_id"], "50.00")
    assert alloc(api, org, invs["INV-3"]["id"], amount, p["id"]).status_code == 422


def test_incorrect_customer_assignment_is_blocked(ledger):
    api, org, invs = ledger
    p = pay(api, org, invs["INV-1"]["customer_id"], "100.00")  # Alpha's payment
    r = alloc(api, org, invs["INV-3"]["id"], "100.00", p["id"])  # Beta's invoice
    assert r.json()["error"]["code"] == "customer_mismatch"


def test_reversal_restores_balance_and_is_audited(ledger):
    api, org, invs = ledger
    i1 = invs["INV-1"]
    p = pay(api, org, i1["customer_id"], "1100.00")
    a = alloc(api, org, i1["id"], "1100.00", p["id"]).json()
    assert balance(api, org, i1["id"]) == "0.00"
    assert api.post(f"/api/v1/orgs/{org}/allocations/{a['id']}/reverse", json={"reason": ""}).status_code == 422
    r = api.post(f"/api/v1/orgs/{org}/allocations/{a['id']}/reverse", json={"reason": "wrong invoice"})
    assert r.status_code == 200 and r.json()["status"] == "reversed"
    assert api.post(f"/api/v1/orgs/{org}/allocations/{a['id']}/reverse", json={"reason": "again"}).status_code == 409
    assert balance(api, org, i1["id"]) == "1100.00"
    d = api.get(f"/api/v1/orgs/{org}/invoices/{i1['id']}").json()
    assert d["allocations"][0]["status"] == "reversed" and d["allocations"][0]["reversal_reason"] == "wrong invoice"
    actions = [h["action"] for h in d["history"]]
    assert "allocation.confirmed" in actions and "allocation.reversed" in actions
    # The payment is available again.
    assert alloc(api, org, i1["id"], "1100.00", p["id"]).status_code == 201


def test_duplicate_manual_payment_rejected(ledger):
    api, org, invs = ledger
    pay(api, org, invs["INV-1"]["customer_id"], "10.00", ref="same")
    r = api.post(f"/api/v1/orgs/{org}/payments", json={"customer_id": invs["INV-1"]["customer_id"],
                                                       "payment_date": "2026-02-01", "amount": "10.00", "reference": "same"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_payment"


def test_credit_note_allocation_and_cancelled_invoice_rules(ledger):
    api, org, invs = ledger
    i2 = invs["INV-2"]
    cn = api.post(f"/api/v1/orgs/{org}/credit-notes", json={"customer_id": i2["customer_id"], "credit_note_number": "CN-1",
                                                            "credit_date": "2026-01-20", "amount": "50.00",
                                                            "reason": "write-off", "applies_to_invoice": "INV-2"}).json()
    assert alloc(api, org, i2["id"], "50.00", credit_note_id=cn["id"]).status_code == 201
    d = api.get(f"/api/v1/orgs/{org}/invoices/{i2['id']}?as_at=2026-06-30").json()
    assert d["credits_allocated"] == "50.00" and d["balance"] == "500.00"
    r = api.post(f"/api/v1/orgs/{org}/invoices/{i2['id']}/status", json={"status": "cancelled", "reason": "x"})
    assert r.json()["error"]["code"] == "has_allocations"
    i3 = invs["INV-3"]
    assert api.post(f"/api/v1/orgs/{org}/invoices/{i3['id']}/status", json={"status": "cancelled", "reason": "duplicate"}).status_code == 200
    p = pay(api, org, i3["customer_id"], "10.00")
    assert alloc(api, org, i3["id"], "10.00", p["id"]).json()["error"]["code"] == "invoice_closed"
    dash = api.get(f"/api/v1/orgs/{org}/dashboard?as_at=2026-06-30").json()
    assert dash["totals"]["total_outstanding"] == "1600.00"  # 1100 + 500; cancelled INV-3 excluded


def test_payment_customer_change_blocked_after_allocation(ledger):
    api, org, invs = ledger
    p = pay(api, org, invs["INV-1"]["customer_id"], "10.00")
    alloc(api, org, invs["INV-1"]["id"], "10.00", p["id"])
    r = api.post(f"/api/v1/orgs/{org}/payments/{p['id']}/assign-customer", json={"customer_id": invs["INV-3"]["customer_id"]})
    assert r.json()["error"]["code"] == "has_allocations"


def test_concurrent_allocations_cannot_over_allocate(ledger, make_client):
    """Two simultaneous requests each try to allocate the full payment; row locks allow only one."""
    api, org, invs = ledger
    p = pay(api, org, invs["INV-1"]["customer_id"], "550.00")
    results = []

    def go(invoice):
        results.append(alloc(api, org, invs[invoice]["id"], "550.00", p["id"]).status_code)

    threads = [threading.Thread(target=go, args=(n,)) for n in ("INV-1", "INV-2")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [201, 422]
    assert api.get(f"/api/v1/orgs/{org}/payments/{p['id']}").json()["unapplied"] == "0.00"


def test_suggestions_are_deterministic_and_unconfirmed(ledger):
    api, org, invs = ledger
    p = pay(api, org, invs["INV-1"]["customer_id"], "550.00", ref="Payment for inv-2")
    s = api.get(f"/api/v1/orgs/{org}/payments/{p['id']}").json()["suggestions"]
    assert s[0]["invoice_number"] == "INV-2" and s[0]["confidence"] == "high"
    assert all(x["requires_confirmation"] for x in s)
    assert balance(api, org, invs["INV-2"]["id"]) == "550.00"  # nothing applied automatically
