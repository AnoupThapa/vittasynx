"""Demo organisation (rules.md §8.13): synthetic, separate, labelled, internally consistent."""
from decimal import Decimal as D



def test_demo_org_created_once_and_labelled(make_user):
    api = make_user()
    r = api.post("/api/v1/orgs/demo", json={})
    assert r.status_code == 201 and r.json()["is_demo"] is True and "synthetic" in r.json()["name"].lower()
    again = api.post("/api/v1/orgs/demo", json={})
    assert again.json()["id"] == r.json()["id"]  # one per user
    orgs = api.get("/api/v1/auth/me").json()["organisations"]
    assert [o["is_demo"] for o in orgs] == [True]


def test_demo_data_is_consistent_and_reconciles(make_user):
    api = make_user()
    org = api.post("/api/v1/orgs/demo", json={}).json()["id"]
    d = api.get(f"/api/v1/orgs/{org}/dashboard").json()
    assert d["is_demo"] is True and d["reconciles"] is True
    t = d["totals"]
    assert D(t["total_outstanding"]) > 0 and D(t["overdue_total"]) > 0
    assert D(t["unapplied_payments"]) > 0 and t["exception_count"] == 0
    assert sum(D(a["total"]) for a in d["ageing"]) == D(t["total_outstanding"])
    invoices = api.get(f"/api/v1/orgs/{org}/invoices").json()["items"]
    assert len(invoices) >= 40
    statuses = {i["status"] for i in invoices}
    assert {"paid", "overdue", "disputed", "cancelled"} <= statuses
    customers = api.get(f"/api/v1/orgs/{org}/customers").json()["items"]
    assert len(customers) == 8 and all("(Demo)" in c["name"] for c in customers)
    sufficient = [c for c in customers
                  if api.get(f"/api/v1/orgs/{org}/customers/{c['id']}/behaviour").json()["sufficient_data"]]
    assert len(sufficient) >= 2
    unassigned = api.get(f"/api/v1/orgs/{org}/payments?unassigned_only=true").json()["items"]
    assert len(unassigned) == 1
    detail = api.get(f"/api/v1/orgs/{org}/payments/{unassigned[0]['id']}").json()
    assert detail["suggestions"] and detail["suggestions"][0]["confidence"] == "high"
    actions = {e["action"] for e in api.get(f"/api/v1/orgs/{org}/audit?limit=500").json()["items"]}
    assert {"invoice.created_demo", "allocation.confirmed", "organisation.demo_populated"} <= actions


def test_demo_exports_are_labelled(make_user):
    api = make_user()
    org = api.post("/api/v1/orgs/demo", json={}).json()["id"]
    text = api.get(f"/api/v1/orgs/{org}/exports/invoices.csv").text
    assert text.startswith("Data,\"DEMO ORGANISATION — SYNTHETIC DATA, NOT REAL\"")


def test_demo_is_separate_from_real_org(make_user, make_org):
    api = make_user()
    real = make_org(api, "Real Co")
    demo = api.post("/api/v1/orgs/demo", json={}).json()["id"]
    assert api.get(f"/api/v1/orgs/{real}/invoices").json()["items"] == []
    assert api.get(f"/api/v1/orgs/{real}/customers").json()["items"] == []
    assert api.get(f"/api/v1/orgs/{real}").json()["is_demo"] is False
    other = make_user()
    assert other.get(f"/api/v1/orgs/{demo}/dashboard").status_code == 404


def test_mfa_not_enforced_in_demo_but_still_enforced_in_real(make_user, make_org, settings_override):
    api = make_user()
    real = make_org(api, "Real Co")
    demo = api.post("/api/v1/orgs/demo", json={}).json()["id"]
    settings_override(require_mfa_for_privileged=True)
    assert api.get(f"/api/v1/orgs/{demo}/dashboard").status_code == 200
    assert api.get(f"/api/v1/orgs/{real}/dashboard").json()["error"]["code"] == "mfa_enrolment_required"
