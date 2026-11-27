"""Workflow 1 (invoice import) plus credit note, payment and bank imports. Synthetic data only."""
import io

import pytest
from openpyxl import Workbook

from tests.conftest import import_file

H = "invoice_number,customer_code,customer_name,issue_date,due_date,total_amount,tax_amount,status\n"


@pytest.fixture
def owner_org(make_user, make_org):
    owner = make_user()
    return owner, make_org(owner)


def _invoices(api, org, as_at="2026-06-30"):
    return api.get(f"/api/v1/orgs/{org}/invoices?as_at={as_at}").json()["items"]


def _upload_validate(api, org, kind, name, content, mapping=None, date_format="YYYY-MM-DD", status_map=None):
    r = api.upload(org, kind, name, content.encode() if isinstance(content, str) else content)
    assert r.status_code == 201, r.text
    b = r.json()
    r = api.post(f"/api/v1/orgs/{org}/imports/{b['id']}/validate",
                 json={"mapping": mapping or b["mapping"], "date_format": date_format, "status_map": status_map})
    return b, r


def _rows(api, org, batch_id):
    return {r["row_number"]: r for r in api.get(f"/api/v1/orgs/{org}/imports/{batch_id}/rows").json()["items"]}


def test_clean_invoice_import(owner_org):
    api, org = owner_org
    csv = H + ("INV-1,C1,Hospital One,2026-01-05,2026-02-04,1100.00,100.00,AUTHORISED\n"
               "INV-2,C1,Hospital One,2026-01-10,2026-02-09,550.00,50.00,\n"
               "INV-3,C2,Clinic Two,2026-02-01,2026-03-03,220.00,20.00,open\n")
    validated, r = import_file(api, org, "invoices", "clean.csv", csv)
    assert validated["summary"]["by_status"] == {"valid": 3}
    assert {c["name"] for c in validated["summary"]["new_customers"]} == {"Hospital One", "Clinic Two"}
    assert r.status_code == 200 and r.json()["status"] == "committed"
    assert r.json()["summary"]["result"] == {"committed": 3}
    assert r.json()["summary"]["customers_created"] == 2
    invs = _invoices(api, org)
    assert [i["invoice_number"] for i in invs] == ["INV-1", "INV-2", "INV-3"]
    assert sum(float(i["balance"]) for i in invs) == 1870.0  # sanity only; exact checks use strings below
    assert [i["balance"] for i in invs] == ["1100.00", "550.00", "220.00"]


def test_new_customers_need_confirmation(owner_org):
    api, org = owner_org
    _, r = import_file(api, org, "invoices", "x.csv", H + "INV-1,C1,New Co,2026-01-05,2026-02-04,10.00,,\n", confirm=False)
    assert r.status_code == 422 and r.json()["error"]["code"] == "confirm_new_customers"
    assert r.json()["error"]["details"]["new_customers"] == [{"code": "C1", "name": "New Co"}]
    assert _invoices(api, org) == []


def test_missing_fields_and_invalid_values_are_reported_per_row(owner_org):
    api, org = owner_org
    csv = H + ("INV-1,C1,Good Co,2026-01-05,2026-02-04,100.00,,\n"
               ",C1,Good Co,2026-01-05,2026-02-04,100.00,,\n"            # 3: missing number
               "INV-3,C1,Good Co,2026-01-05,,100.00,,\n"                # 4: missing due date
               "INV-4,C1,Good Co,2026-02-31,2026-03-04,100.00,,\n"      # 5: invalid date
               "INV-5,C1,Good Co,2026-02-05,2026-01-04,100.00,,\n"      # 6: due before issue
               "INV-6,C1,Good Co,2026-01-05,2026-02-04,100.005,,\n"     # 7: precision
               )
    csv = csv + "INV-7,C1,Good Co,2026-01-05,2026-02-04,abc,,\n" \
        "INV-8,C1,Good Co,2026-01-05,2026-02-04,-50.00,,\n" "INV-9,,,2026-01-05,2026-02-04,5.00,,\n" \
        "INV-10,C1,Good Co,2026-01-05,2026-02-04,5.00,,DRAFT\n" "INV-11,C1,Good Co,2026-01-05,2026-02-04,5.00,,weird\n"
    b, r = _upload_validate(api, org, "invoices", "bad.csv", csv)
    rows = _rows(api, org, b["id"])
    msg = {n: " ".join(m["message"] for m in rows[n]["messages"]) for n in rows}
    assert rows[2]["status"] == "valid"
    assert "Invoice number is required" in msg[3]
    assert "Due date is required" in msg[4]
    assert "not a valid date" in msg[5]
    assert "before the issue date" in msg[6]
    assert "more than 2 decimal places" in msg[7]
    assert "not a valid amount" in msg[8]
    assert "credit notes" in msg[9]
    assert "Customer code or name is required" in msg[10]
    assert "Draft invoices" in msg[11]
    assert "not recognised" in msg[12]
    # Commit is blocked until errors are corrected or excluded.
    r = api.post(f"/api/v1/orgs/{org}/imports/{b['id']}/commit", json={"confirm_new_customers": True})
    assert r.json()["error"]["code"] == "rows_have_errors"
    # Correct row 4 without touching the raw value; exclude the rest explicitly.
    r = api.patch(f"/api/v1/orgs/{org}/imports/{b['id']}/rows/{rows[4]['id']}",
                  json={"action": "correct", "corrections": {"due_date": "2026-02-04"}})
    assert r.status_code == 200
    rows = _rows(api, org, b["id"])
    assert rows[4]["status"] == "valid" and rows[4]["raw"]["due_date"] == "" and rows[4]["corrections"] == {"due_date": "2026-02-04"}
    r = api.post(f"/api/v1/orgs/{org}/imports/{b['id']}/commit", json={"confirm_new_customers": True, "exclude_errors": True})
    assert r.status_code == 200
    assert r.json()["summary"]["result"] == {"committed": 2, "excluded": 9}
    assert {i["invoice_number"] for i in _invoices(api, org)} == {"INV-1", "INV-3"}


def test_row_with_extra_values_is_malformed(owner_org):
    api, org = owner_org
    r = api.upload(org, "invoices", "bad.csv", (H + "INV-1,C1,X,2026-01-05,2026-02-04,1.00,,,EXTRA\n").encode())
    assert r.status_code == 422 and r.json()["error"]["code"] == "malformed_file"


def test_foreign_currency_rejected(owner_org):
    api, org = owner_org
    csv = "invoice_number,customer_name,issue_date,due_date,total_amount,currency\nINV-1,X,2026-01-05,2026-02-04,10.00,USD\n"
    b, r = _upload_validate(api, org, "invoices", "fx.csv", csv)
    row = list(_rows(api, org, b["id"]).values())[0]
    assert row["status"] == "error" and "USD is not supported" in row["messages"][0]["message"]


def test_different_column_names_day_first_dates_thousands_and_status_map(owner_org):
    api, org = owner_org
    csv = ("InvoiceNumber,ContactName,InvoiceDate,DueDate,Total,TaxTotal,AmountDue,Currency,Status\n"
           'INV-1001,Example Hospital Supplies,05/01/2026,04/02/2026,"1,100.00",100.00,1100.00,AUD,AUTHORISED\n'
           "INV-1002,Example Hospital Supplies,06/01/2026,05/02/2026,50.00,,0.00,AUD,PAID\n"
           "INV-1003,Example Hospital Supplies,07/01/2026,06/02/2026,60.00,,60.00,AUD,On Hold\n")
    r = api.upload(org, "invoices", "xero-style.csv", csv.encode())
    b = r.json()
    assert b["mapping"] == {"invoice_number": "InvoiceNumber", "customer_name": "ContactName", "issue_date": "InvoiceDate",
                            "due_date": "DueDate", "total_amount": "Total", "tax_amount": "TaxTotal",
                            "currency": "Currency", "amount_due": "AmountDue", "status": "Status"}
    validated, r = import_file(api, org, "invoices", "xero-style.csv", csv, date_format="DD/MM/YYYY")
    assert r.status_code == 200, r.text
    invs = {i["invoice_number"]: i for i in _invoices(api, org)}
    assert invs["INV-1001"]["issue_date"] == "2026-01-05" and invs["INV-1001"]["original_amount"] == "1100.00"
    # Source says PAID with amount due 0, but no payments are recorded: the balance is NOT trusted from source.
    assert invs["INV-1002"]["balance"] == "50.00" and invs["INV-1002"]["source_differs"] is True
    assert invs["INV-1003"]["status"] == "disputed"


def test_net_plus_tax_derives_gross_and_mismatch_is_error(owner_org):
    api, org = owner_org
    csv = ("invoice_number,customer_name,issue_date,due_date,net,gst,total\n"
           "N-1,Net Co,2026-01-05,2026-02-04,1000.00,100.00,\n"
           "N-2,Net Co,2026-01-05,2026-02-04,1000.00,100.00,1200.00\n")
    b, r = _upload_validate(api, org, "invoices", "net.csv", csv)
    rows = _rows(api, org, b["id"])
    assert rows[2]["status"] == "valid" and rows[2]["normalised"]["total_amount"] == "1100.00"
    assert rows[2]["normalised"]["total_is_derived"] is True
    assert "does not equal net + tax" in rows[3]["messages"][0]["message"]


def test_reimport_same_file_skips_duplicates(owner_org):
    api, org = owner_org
    csv = H + "INV-1,C1,Hospital One,2026-01-05,2026-02-04,1100.00,100.00,\n"
    import_file(api, org, "invoices", "a.csv", csv)
    r = api.upload(org, "invoices", "a.csv", csv.encode())
    assert r.json()["warnings"][0]["code"] == "file_previously_imported"
    validated, r = import_file(api, org, "invoices", "a.csv", csv)
    assert validated["summary"]["by_status"] == {"duplicate": 1}
    assert r.json()["summary"]["result"] == {"duplicate_skipped": 1}
    assert len(_invoices(api, org)) == 1


def test_duplicate_within_file_is_error(owner_org):
    api, org = owner_org
    csv = H + "INV-1,C1,H,2026-01-05,2026-02-04,10.00,,\ninv-1 ,C1,H,2026-01-05,2026-02-04,10.00,,\n"
    b, _ = _upload_validate(api, org, "invoices", "d.csv", csv)
    rows = _rows(api, org, b["id"])
    assert rows[2]["status"] == "valid" and rows[3]["status"] == "error"


def test_same_number_other_customer_needs_review(owner_org):
    api, org = owner_org
    import_file(api, org, "invoices", "a.csv", H + "INV-1,C1,Alpha,2026-01-05,2026-02-04,10.00,,\n")
    b, _ = _upload_validate(api, org, "invoices", "b.csv", H + "INV-1,C2,Beta,2026-01-05,2026-02-04,20.00,,\n")
    row = list(_rows(api, org, b["id"]).values())[0]
    assert row["status"] == "needs_review"
    r = api.post(f"/api/v1/orgs/{org}/imports/{b['id']}/commit", json={"confirm_new_customers": True})
    assert r.json()["error"]["code"] == "rows_need_review"
    api.patch(f"/api/v1/orgs/{org}/imports/{b['id']}/rows/{row['id']}", json={"action": "include"})
    r = api.post(f"/api/v1/orgs/{org}/imports/{b['id']}/commit", json={"confirm_new_customers": True})
    assert r.status_code == 200
    assert len(_invoices(api, org)) == 2  # never merged


def test_changed_reimport_becomes_amendment_and_needs_approval(owner_org, add_member):
    api, org = owner_org
    import_file(api, org, "invoices", "a.csv", H + "INV-1,C1,Alpha,2026-01-05,2026-02-04,1100.00,100.00,\n")
    validated, r = import_file(api, org, "invoices", "a2.csv", H + "INV-1,C1,Alpha,2026-01-05,2026-02-20,1000.00,90.91,\n")
    assert validated["summary"]["by_status"] == {"amendment": 1}
    assert r.json()["summary"]["result"] == {"amendment_pending": 1}
    inv = _invoices(api, org)[0]
    assert inv["original_amount"] == "1100.00" and inv["due_date"] == "2026-02-04"  # not overwritten
    pending = api.get(f"/api/v1/orgs/{org}/amendments").json()["items"]
    assert len(pending) == 1
    assert pending[0]["changes"]["total_amount"] == {"from": "1100.00", "to": "1000.00"}
    ar = add_member(api, org, "ar_officer")
    assert ar.post(f"/api/v1/orgs/{org}/amendments/{pending[0]['id']}/approve", json={}).status_code == 403
    r = api.post(f"/api/v1/orgs/{org}/amendments/{pending[0]['id']}/approve", json={"reason": "credit agreed"})
    assert r.status_code == 200
    detail = api.get(f"/api/v1/orgs/{org}/invoices/{inv['id']}").json()
    assert detail["original_amount"] == "1000.00" and detail["due_date"] == "2026-02-20" and detail["version"] == 2
    assert [v["values"]["total_amount"] for v in detail["versions"]] == ["1100.00", "1000.00"]


def test_amendment_below_allocations_blocked(owner_org):
    api, org = owner_org
    import_file(api, org, "invoices", "a.csv", H + "INV-1,C1,Alpha,2026-01-05,2026-02-04,100.00,,\n")
    inv = _invoices(api, org)[0]
    pay = api.post(f"/api/v1/orgs/{org}/payments", json={"customer_id": inv["customer_id"], "payment_date": "2026-02-01",
                                                         "amount": "80.00"}).json()
    api.post(f"/api/v1/orgs/{org}/allocations", json={"invoice_id": inv["id"], "payment_id": pay["id"], "amount": "80.00"})
    import_file(api, org, "invoices", "a2.csv", H + "INV-1,C1,Alpha,2026-01-05,2026-02-04,50.00,,\n")
    pending = api.get(f"/api/v1/orgs/{org}/amendments").json()["items"][0]
    r = api.post(f"/api/v1/orgs/{org}/amendments/{pending['id']}/approve", json={})
    assert r.json()["error"]["code"] == "amendment_below_allocations"
    assert api.post(f"/api/v1/orgs/{org}/amendments/{pending['id']}/reject", json={"reason": "source error"}).status_code == 200
    assert _invoices(api, org)[0]["original_amount"] == "100.00"


def test_commit_is_idempotent(owner_org):
    api, org = owner_org
    b, _ = _upload_validate(api, org, "invoices", "a.csv", H + "INV-1,C1,Alpha,2026-01-05,2026-02-04,10.00,,\n")
    url = f"/api/v1/orgs/{org}/imports/{b['id']}/commit"
    r1 = api.post(url, json={"confirm_new_customers": True})
    r2 = api.post(url, json={"confirm_new_customers": True})
    assert r1.status_code == r2.status_code == 200
    assert len(_invoices(api, org)) == 1


def test_xlsx_import_with_numeric_and_date_cells(owner_org):
    api, org = owner_org
    from datetime import datetime

    wb = Workbook()
    ws = wb.active
    ws.append(["Invoice No", "Customer", "Invoice Date", "Due Date", "Amount"])
    ws.append(["X-1", "Excel Co", datetime(2026, 1, 5), datetime(2026, 2, 4), 1100.1])
    ws.append(["X-2", "Excel Co", datetime(2026, 1, 6), datetime(2026, 2, 5), 1100.005])  # over-precise
    buf = io.BytesIO()
    wb.save(buf)
    b, r = _upload_validate(api, org, "invoices", "book.xlsx", buf.getvalue())
    rows = _rows(api, org, b["id"])
    assert rows[2]["status"] == "valid" and rows[2]["normalised"]["total_amount"] == "1100.10"
    assert rows[3]["status"] == "error"  # over-precise value is caught, not silently rounded
    assert "decimal places" in rows[3]["messages"][0]["message"]


@pytest.mark.parametrize("name,content,code", [
    ("x.xls", b"anything", "unsupported_file_type"),
    ("x.xlsm", b"PK\x03\x04", "unsupported_file_type"),
    ("x.csv", b"", "empty_file"),
    ("x.csv", b"\xff\xfe\x00b", "invalid_encoding"),
    ("x.xlsx", b"not a zip", "file_type_mismatch"),
    ("x.csv", b"PK\x03\x04rest", "file_type_mismatch"),
])
def test_unsafe_or_invalid_files_rejected(owner_org, name, content, code):
    api, org = owner_org
    r = api.upload(org, "invoices", name, content)
    assert r.status_code == 422 and r.json()["error"]["code"] == code


def test_macro_workbook_rejected_even_with_xlsx_name(owner_org):
    import zipfile

    api, org = owner_org
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", "<workbook/>")
        z.writestr("xl/vbaProject.bin", b"\x00")
    r = api.upload(org, "invoices", "evil.xlsx", buf.getvalue())
    assert r.json()["error"]["code"] == "macros_not_allowed"


def test_file_size_and_row_limits(owner_org, settings_override):
    api, org = owner_org
    settings_override(max_upload_bytes=100)
    assert api.upload(org, "invoices", "big.csv", b"a," * 100).json()["error"]["code"] == "file_too_large"
    settings_override(max_upload_bytes=5 * 1024 * 1024, max_import_rows=2)
    csv = H + "".join(f"I{i},C,N,2026-01-01,2026-01-31,1.00,,\n" for i in range(3))
    assert api.upload(org, "invoices", "rows.csv", csv.encode()).json()["error"]["code"] == "too_many_rows"


def test_mapping_must_cover_required_fields(owner_org):
    api, org = owner_org
    b = api.upload(org, "invoices", "m.csv", b"a,b\n1,2\n").json()
    r = api.post(f"/api/v1/orgs/{org}/imports/{b['id']}/validate", json={"mapping": {"invoice_number": "a"}})
    assert r.json()["error"]["code"] == "invalid_mapping"
    r = api.post(f"/api/v1/orgs/{org}/imports/{b['id']}/validate", json={"mapping": {"invoice_number": "zzz"}})
    assert "not in the file" in r.json()["error"]["message"]


def test_credit_note_import_and_suggestion(owner_org):
    api, org = owner_org
    import_file(api, org, "invoices", "a.csv", H + "INV-1,C1,Alpha,2026-01-05,2026-02-04,1100.00,100.00,\n")
    csv = ("credit_note_number,customer_code,customer_name,credit_date,amount,applies_to_invoice,reason\n"
           "CN-1,C1,Alpha,2026-01-20,-100.00,INV-1,damaged\n")
    _, r = import_file(api, org, "credit_notes", "cn.csv", csv)
    assert r.status_code == 200
    cn = api.get(f"/api/v1/orgs/{org}/credit-notes").json()["items"][0]
    assert cn["amount"] == "100.00" and cn["unapplied"] == "100.00"
    detail = api.get(f"/api/v1/orgs/{org}/credit-notes/{cn['id']}").json()
    assert detail["suggestions"][0]["confidence"] == "high" and detail["suggestions"][0]["requires_confirmation"]
    # Suggestion is not applied until confirmed.
    assert _invoices(api, org)[0]["balance"] == "1100.00"


def test_payment_import_duplicates(owner_org):
    api, org = owner_org
    csv = ("payment_date,customer_name,amount,reference\n"
           "2026-02-01,Alpha,500.00,INV-1\n" "2026-02-01,Alpha,500.00,INV-1\n" "2026-02-02,Alpha,0.00,x\n")
    b, _ = _upload_validate(api, org, "payments", "p.csv", csv)
    rows = _rows(api, org, b["id"])
    assert [rows[n]["status"] for n in (2, 3, 4)] == ["valid", "needs_review", "error"]
    api.patch(f"/api/v1/orgs/{org}/imports/{b['id']}/rows/{rows[3]['id']}", json={"action": "exclude"})
    r = api.post(f"/api/v1/orgs/{org}/imports/{b['id']}/commit", json={"confirm_new_customers": True, "exclude_errors": True})
    assert r.json()["summary"]["result"] == {"committed": 1, "excluded": 2}
    validated, r = import_file(api, org, "payments", "p2.csv", "payment_date,customer_name,amount,reference\n"
                               "2026-02-01,Alpha,500.00,INV-1\n")
    assert validated["summary"]["by_status"] == {"duplicate": 1}


def test_bank_import_receipts_only_and_assignment(owner_org):
    api, org = owner_org
    import_file(api, org, "invoices", "a.csv", H + "INV-1001,C1,Alpha,2026-01-05,2026-02-04,500.00,,\n")
    csv = ("Date,Description,Debit,Credit,Balance\n"
           "01/02/2026,DIRECT CREDIT ALPHA INV-1001,,500.00,12500.00\n"
           "02/02/2026,SUPPLIER PAYMENT,300.00,,12200.00\n")
    validated, r = import_file(api, org, "bank", "bank.csv", csv, date_format="DD/MM/YYYY")
    assert validated["summary"]["by_status"] == {"valid": 1, "skipped": 1}
    assert r.json()["summary"]["result"] == {"committed": 1, "skipped": 1}
    pay = api.get(f"/api/v1/orgs/{org}/payments?unassigned_only=true").json()["items"][0]
    assert pay["assigned"] is False and pay["amount"] == "500.00"
    detail = api.get(f"/api/v1/orgs/{org}/payments/{pay['id']}").json()
    assert detail["suggestions"][0]["invoice_number"] == "INV-1001" and detail["suggestions"][0]["confidence"] == "high"
    inv = _invoices(api, org)[0]
    r = api.post(f"/api/v1/orgs/{org}/allocations", json={"invoice_id": inv["id"], "payment_id": pay["id"], "amount": "500.00"})
    assert r.json()["error"]["code"] == "unassigned_receipt"
    api.post(f"/api/v1/orgs/{org}/payments/{pay['id']}/assign-customer", json={"customer_id": inv["customer_id"]})
    r = api.post(f"/api/v1/orgs/{org}/allocations", json={"invoice_id": inv["id"], "payment_id": pay["id"], "amount": "500.00"})
    assert r.status_code == 201
    assert _invoices(api, org)[0]["status"] == "paid"


def test_source_file_is_preserved_and_downloadable(owner_org):
    api, org = owner_org
    csv = H + "INV-1,C1,Alpha,2026-01-05,2026-02-04,10.00,,\n"
    _, r = import_file(api, org, "invoices", "orig.csv", csv)
    f = api.get(f"/api/v1/orgs/{org}/imports/{r.json()['id']}/file")
    assert f.status_code == 200 and f.content == csv.encode()
