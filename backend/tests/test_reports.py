"""Workflow 2 & 4 and the Phase 6 reconciliation chain on a synthetic dataset with hand-computed totals.

Dataset (AUD, reporting date 2026-03-31):
  Alpha  INV-A1 1,100.00 due 2026-02-04 → paid 300.00 (2026-02-10) + credit 100.00 (2026-03-01) → 700.00, 55 days → 31–60
  Alpha  INV-A2   550.00 due 2026-04-15 → unpaid → 550.00 current
  Beta   INV-B1   300.00 due 2026-03-01 → unpaid → 300.00, 30 days → 1–30
  Beta   INV-B2   400.00 due 2025-12-31 → unpaid → 400.00, 90 days → 61–90
  Gamma  INV-G1   250.00 due 2025-12-30 → unpaid → 250.00, 91 days → 91+
  Gamma  INV-G2    80.00 due 2026-01-31 → fully paid 2026-02-15 → 0.00 (excluded)
  Delta  INV-D1   999.00 due 2026-01-31 → cancelled (excluded)
  Alpha  unapplied payment 120.00 (2026-03-20); Beta payment dated 2026-04-02 (after R, excluded)
  Totals: current 550.00; 1–30 300.00; 31–60 700.00; 61–90 400.00; 91+ 250.00; outstanding 2,200.00;
          overdue 1,650.00 (4 invoices); unapplied payments 120.00; net 2,080.00.
"""
import csv
import io

import pytest

from tests.conftest import import_file

R = "2026-03-31"


@pytest.fixture
def dataset(make_user, make_org):
    api = make_user()
    org = make_org(api)
    src = ("invoice_number,customer_code,customer_name,issue_date,due_date,total_amount,status\n"
           "INV-A1,A,Alpha,2026-01-05,2026-02-04,\"1,100.00\",open\n"
           "INV-A2,A,Alpha,2026-03-16,2026-04-15,550.00,open\n"
           "INV-B1,B,Beta,2026-01-30,2026-03-01,300.00,open\n"
           "INV-B2,B,Beta,2025-12-01,2025-12-31,400.00,open\n"
           "INV-G1,G,Gamma,2025-11-30,2025-12-30,250.00,open\n"
           "INV-G2,G,Gamma,2026-01-01,2026-01-31,80.00,open\n"
           "INV-D1,D,Delta,2026-01-01,2026-01-31,999.00,cancelled\n")
    _, r = import_file(api, org, "invoices", "dataset.csv", src)
    assert r.status_code == 200, r.text
    invs = {i["invoice_number"]: i for i in api.get(f"/api/v1/orgs/{org}/invoices?as_at=2026-12-31").json()["items"]}
    base = f"/api/v1/orgs/{org}"

    def payment(cust, amount, d, ref):
        return api.post(f"{base}/payments", json={"customer_id": cust, "payment_date": d, "amount": amount,
                                                  "reference": ref}).json()

    a1, g2 = invs["INV-A1"], invs["INV-G2"]
    p1 = payment(a1["customer_id"], "300.00", "2026-02-10", "A1 part")
    api.post(f"{base}/allocations", json={"invoice_id": a1["id"], "payment_id": p1["id"], "amount": "300.00"})
    cn = api.post(f"{base}/credit-notes", json={"customer_id": a1["customer_id"], "credit_note_number": "CN-A1",
                                                "credit_date": "2026-03-01", "amount": "100.00"}).json()
    api.post(f"{base}/allocations", json={"invoice_id": a1["id"], "credit_note_id": cn["id"], "amount": "100.00"})
    p2 = payment(g2["customer_id"], "80.00", "2026-02-15", "G2")
    api.post(f"{base}/allocations", json={"invoice_id": g2["id"], "payment_id": p2["id"], "amount": "80.00"})
    payment(a1["customer_id"], "120.00", "2026-03-20", "unapplied")
    payment(invs["INV-B1"]["customer_id"], "300.00", "2026-04-02", "after R")
    return api, org, src


def test_dashboard_matches_hand_computed_totals(dataset):
    api, org, _ = dataset
    d = api.get(f"/api/v1/orgs/{org}/dashboard?as_at={R}").json()
    assert d["reporting_date"] == R and d["currency"] == "AUD" and d["rule_version"] == "R1-2026-11-27"
    assert {a["bucket"]: a["total"] for a in d["ageing"]} == {
        "current": "550.00", "1_30": "300.00", "31_60": "700.00", "61_90": "400.00", "91_plus": "250.00"}
    t = d["totals"]
    assert t["total_outstanding"] == "2200.00" and t["overdue_total"] == "1650.00" and t["overdue_count"] == 4
    assert t["current_total"] == "550.00" and t["unapplied_payments"] == "120.00" and t["net_position"] == "2080.00"
    assert t["unapplied_credits"] == "0.00" and t["exception_count"] == 0
    assert d["reconciles"] is True
    assert [c["customer_name"] for c in d["largest_overdue_customers"]] == ["Alpha", "Beta", "Gamma"]
    assert d["largest_overdue_customers"][1]["overdue"] == "700.00"  # Beta 300 + 400
    assert d["oldest_outstanding_invoices"][0]["invoice_number"] == "INV-G1"
    assert d["oldest_outstanding_invoices"][0]["days_past_due"] == 91
    assert all(k in d["definitions"] for k in ("total_outstanding", "ageing", "unapplied_payments"))
    assert "after R" not in [p["reference"] for p in d["recent_payments"]]


def test_point_in_time_report_is_reproducible(dataset):
    api, org, _ = dataset
    early = api.get(f"/api/v1/orgs/{org}/dashboard?as_at=2026-02-28").json()["totals"]
    # At 28 Feb: A1 1100−300 = 800 (credit dated 1 Mar excluded); A2 not yet issued; B1 300; B2 400; G1 250; G2 paid.
    assert early["total_outstanding"] == "1750.00"
    again = api.get(f"/api/v1/orgs/{org}/dashboard?as_at=2026-02-28").json()["totals"]
    assert again == early


def test_reconciliation_chain_source_to_dashboard(dataset):
    """Phase 6 reconciliation: source totals → imported → balances → allocations → ageing → dashboard → export."""
    api, org, src = dataset
    from decimal import Decimal as D

    source_rows = list(csv.DictReader(io.StringIO(src)))
    source_total = sum(D(r["total_amount"].replace(",", "")) for r in source_rows)
    invoices = api.get(f"/api/v1/orgs/{org}/invoices?as_at={R}").json()["items"]
    imported_total = sum(D(i["original_amount"]) for i in invoices)
    assert source_total == imported_total == D("3679.00")

    open_invoices = [i for i in invoices if i["status"] not in ("cancelled", "void")]
    for i in open_invoices:  # balance = original − payments − credits, for every invoice
        assert D(i["balance"]) == D(i["original_amount"]) - D(i["payments_allocated"]) - D(i["credits_allocated"])
    allocated = sum(D(i["payments_allocated"]) + D(i["credits_allocated"]) for i in open_invoices)
    assert allocated == D("480.00")  # 300 + 100 + 80
    balances_total = sum(D(i["balance"]) for i in open_invoices)
    assert balances_total == D("2200.00")  # = source 3679 − cancelled 999 − allocated 480

    d = api.get(f"/api/v1/orgs/{org}/dashboard?as_at={R}").json()
    assert sum(D(a["total"]) for a in d["ageing"]) == D(d["totals"]["total_outstanding"]) == balances_total

    customer_rows = api.get(f"/api/v1/orgs/{org}/reports/customer-balances?as_at={R}").json()["items"]
    assert sum(D(c["total_outstanding"]) for c in customer_rows) == balances_total

    export = api.get(f"/api/v1/orgs/{org}/exports/ageing.csv?as_at={R}").text
    lines = list(csv.reader(io.StringIO(export)))
    assert ["Reporting date", R] in lines
    header = lines.index(["Customer code", "Customer", "Current", "1-30 days", "31-60 days", "61-90 days", "91+ days",
                          "Total outstanding"])
    assert sum(D(row[-1]) for row in lines[header + 1:]) == balances_total


def test_invoice_filters(dataset):
    api, org, _ = dataset
    base = f"/api/v1/orgs/{org}/invoices?as_at={R}"
    assert {i["invoice_number"] for i in api.get(base + "&status=overdue").json()["items"]} == {"INV-A1", "INV-B1", "INV-B2", "INV-G1"}
    assert {i["invoice_number"] for i in api.get(base + "&status=paid").json()["items"]} == {"INV-G2"}
    assert {i["invoice_number"] for i in api.get(base + "&q=beta").json()["items"]} == {"INV-B1", "INV-B2"}
    assert {i["invoice_number"] for i in api.get(base + "&due_from=2026-03-01&due_to=2026-04-30").json()["items"]} == {"INV-A2", "INV-B1"}
    outstanding = api.get(base + "&status=outstanding").json()["items"]
    assert len(outstanding) == 5


def test_invoice_export_matches_screen(dataset):
    api, org, _ = dataset
    screen = {i["invoice_number"]: i["balance"] for i in api.get(f"/api/v1/orgs/{org}/invoices?as_at={R}").json()["items"]}
    text_ = api.get(f"/api/v1/orgs/{org}/exports/invoices.csv?as_at={R}").text
    lines = list(csv.reader(io.StringIO(text_)))
    header_idx = next(i for i, l in enumerate(lines) if l and l[0] == "Invoice number")
    exported = {l[0]: l[7] for l in lines[header_idx + 1:]}
    assert exported == screen
    actions = [e["action"] for e in api.get(f"/api/v1/orgs/{org}/audit").json()["items"]]
    assert "report.exported" in actions


def test_csv_export_neutralises_formula_injection(make_user, make_org):
    api = make_user()
    org = make_org(api)
    import_file(api, org, "invoices", "x.csv", "invoice_number,customer_name,issue_date,due_date,total_amount\n"
                "INV-1,=HYPERLINK(\"http://evil\"),2026-01-01,2026-01-31,10.00\n")
    text_ = api.get(f"/api/v1/orgs/{org}/exports/customer-balances.csv?as_at={R}").text
    assert "'=HYPERLINK" in text_ and ",=HYPERLINK" not in text_


def test_customer_detail_and_behaviour_insufficient(dataset):
    api, org, _ = dataset
    custs = {c["name"]: c for c in api.get(f"/api/v1/orgs/{org}/customers?as_at={R}").json()["items"]}
    assert custs["Alpha"]["total_outstanding"] == "1250.00" and custs["Alpha"]["unapplied_payments"] == "120.00"
    d = api.get(f"/api/v1/orgs/{org}/customers/{custs['Gamma']['id']}?as_at={R}").json()
    assert d["balances"]["91_plus"] == "250.00"
    b = d["behaviour"]
    assert b["sufficient_data"] is False and b["invoices_analysed"] == 1 and b["average_days_late"] is None
    assert b["kind"] == "observed_history" and "Insufficient data" in b["insufficient_reason"]


def test_behaviour_sufficient_data_via_api(make_user, make_org):
    api = make_user()
    org = make_org(api)
    rows = "".join(f"B-{k},C,Steady Co,2025-{k + 1:02d}-01,2025-{k + 1:02d}-28,100.00\n" for k in range(1, 8))
    import_file(api, org, "invoices", "b.csv", "invoice_number,customer_code,customer_name,issue_date,due_date,total_amount\n" + rows)
    invs = api.get(f"/api/v1/orgs/{org}/invoices?as_at=2025-12-31").json()["items"]
    for i in invs:  # each paid 5 days after due
        due = i["due_date"]
        paid = f"{due[:8]}{int(due[8:]) - 23:02d}"  # 28th → 5th of same month; makes it early, adjust below
        p = api.post(f"/api/v1/orgs/{org}/payments", json={"customer_id": i["customer_id"], "payment_date": paid,
                                                           "amount": "100.00", "reference": i["invoice_number"]}).json()
        api.post(f"/api/v1/orgs/{org}/allocations", json={"invoice_id": i["id"], "payment_id": p["id"], "amount": "100.00"})
    b = api.get(f"/api/v1/orgs/{org}/customers/{invs[0]['customer_id']}/behaviour?as_at=2025-12-31").json()
    # Issued on the 1st, paid on the 5th → 4 days to pay, all before the due date (28th).
    assert b["sufficient_data"] is True and b["invoices_analysed"] == 7
    assert b["average_days_to_payment"] == "4.0" and b["average_days_late"] == "0.0" and b["on_time_percentage"] == "100.0"
