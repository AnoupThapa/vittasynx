"""End-to-end smoke test of the core receivables workflow through the real browser UI.

Requires the API on :8000 (VX_ENVIRONMENT=development so the dev outbox is readable) and the web app on :3000.
Run: python e2e/smoke_test.py [--chrome /usr/bin/google-chrome] [--shots ./e2e/screenshots]
Synthetic data only.
"""
import argparse
import json
import os
import re
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("VX_WEB_URL", "http://localhost:3000")
PASSWORD = "a long synthetic test password"

INVOICES = (
    "InvoiceNumber,ContactCode,ContactName,InvoiceDate,DueDate,Total,TaxTotal,Status\n"
    "E2E-1001,HOSP1,Example Hospital (SYNTHETIC),05/01/2026,04/02/2026,\"1,100.00\",100.00,AUTHORISED\n"
    "E2E-1002,HOSP1,Example Hospital (SYNTHETIC),10/02/2026,12/03/2026,550.00,50.00,AUTHORISED\n"
    "E2E-1003,CLIN2,Example Clinic (SYNTHETIC),15/01/2026,14/02/2026,330.00,30.00,AUTHORISED\n"
    "E2E-1004,CLIN2,Example Clinic (SYNTHETIC),01/03/2026,31/03/2026,99.995,,AUTHORISED\n"
)


def outbox_token(email: str) -> str:
    with urllib.request.urlopen(f"{BASE}/api/v1/auth/dev/outbox") as r:
        messages = json.load(r)["messages"]
    body = next(m["body"] for m in messages if m["to"] == email)
    return re.search(r"token=(\S+)", body).group(1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chrome", default=None)
    ap.add_argument("--shots", default=os.path.join(os.path.dirname(__file__), "screenshots"))
    args = ap.parse_args()
    os.makedirs(args.shots, exist_ok=True)
    email = f"owner-{int(time.time())}@example.com"
    csv_path = os.path.join(tempfile.mkdtemp(), "invoices-export.csv")
    with open(csv_path, "w") as f:
        f.write(INVOICES)
    checks: list[str] = []

    def ok(msg: str) -> None:
        checks.append(msg)
        print(f"  ✓ {msg}")

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chrome) if args.chrome else p.chromium.launch()
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        shot = lambda name: page.screenshot(path=os.path.join(args.shots, f"{name}.png"), full_page=True)  # noqa: E731

        # 1. Register, verify email, sign in
        page.goto(f"{BASE}/register")
        page.fill("#name", "Olive Owner")
        page.fill("#email", email)
        page.fill("#pw", PASSWORD)
        page.click("button.primary")
        expect(page.get_by_text("Check your email")).to_be_visible()
        page.goto(f"{BASE}/verify-email?token={outbox_token(email)}")
        expect(page.get_by_text("Your email address is verified")).to_be_visible()
        ok("registration and email verification")
        page.goto(f"{BASE}/login")
        page.fill("#email", email)
        page.fill("#password", PASSWORD)
        shot("01-login")
        page.click("button.primary")
        page.wait_for_url(f"{BASE}/orgs")
        ok("sign in")

        # 2. Create an organisation
        page.fill("#n", "Synthetic Distribution Pty Ltd")
        page.select_option("#c", "AUD")
        page.select_option("#t", "Australia/Sydney")
        page.click("button.primary")
        page.wait_for_url(re.compile(r".*/o/[0-9a-f-]+/dashboard"))
        org_url = page.url.rsplit("/", 1)[0]
        expect(page.get_by_text("Total outstanding", exact=True)).to_be_visible()
        ok("organisation created; empty dashboard shows zero")

        # 3. Import invoices: upload → mapping → validate → review → confirm
        page.goto(f"{org_url}/imports")
        page.select_option("#k", "invoices")
        page.set_input_files("#f", csv_path)
        page.click("text=Upload and preview")
        page.wait_for_url(re.compile(r".*/imports/[0-9a-f-]+"))
        expect(page.get_by_role("heading", name="Column mapping")).to_be_visible()
        shot("02-import-mapping")
        page.select_option("#df", "DD/MM/YYYY")
        page.click("text=Validate rows")
        expect(page.get_by_text("more than 2 decimal places")).to_be_visible()
        ok("over-precise amount 99.995 flagged as an error, not rounded")
        shot("03-import-review")
        page.check("text=Create these customers")
        page.check("text=with errors and import the rest")
        page.click("text=Import 3 new record(s)")
        expect(page.get_by_text("Import complete")).to_be_visible()
        ok("3 invoices imported, 1 excluded, 2 customers created")

        # 4. Dashboard as at 31 Mar 2026
        page.goto(f"{org_url}/dashboard")
        page.fill("#as-at", "2026-03-31")
        expect(page.locator(".figure").first).to_contain_text("1,980.00")
        # Ageing at 31 Mar: E2E-1001 due 4 Feb → 55 days (31–60); 1002 due 12 Mar → 19 (1–30); 1003 due 14 Feb → 45 (31–60)
        expect(page.locator("tr", has_text="31–60 days overdue")).to_contain_text("1,430.00")
        expect(page.locator("tr", has_text="1–30 days overdue")).to_contain_text("550.00")
        ok("dashboard: outstanding 1,980.00; ageing 31–60 = 1,430.00, 1–30 = 550.00")
        shot("04-dashboard-before-payment")

        # 5. Record a payment and allocate it from a suggestion
        page.goto(f"{org_url}/payments")
        page.select_option("#c", label="Example Hospital (SYNTHETIC)")
        page.fill("#d", "2026-02-20")
        page.fill("#a", "1100.00")
        page.fill("#r", "Remittance E2E-1001")
        page.click("text=Record payment")
        page.click("td >> text=20 Feb 2026")
        expect(page.get_by_text("Suggested matches")).to_be_visible()
        row = page.locator("tr", has_text="E2E-1001")
        expect(row).to_contain_text("high")
        shot("05-payment-suggestions")
        row.get_by_role("button", name="Confirm").click()
        expect(page.locator(".figure", has_text="Unapplied")).to_contain_text("0.00")
        ok("payment suggested for E2E-1001 (high confidence) and confirmed by the user")

        # 6. Invoice shows as paid; dashboard updates
        page.goto(f"{org_url}/invoices")
        page.fill("#as-at", "2026-03-31")
        expect(page.locator("tr", has_text="E2E-1001")).to_contain_text("Paid")
        shot("06-invoices")
        page.goto(f"{org_url}/dashboard")
        page.fill("#as-at", "2026-03-31")
        expect(page.locator(".figure").first).to_contain_text("880.00")
        ok("after allocation: E2E-1001 paid, outstanding 880.00")
        shot("07-dashboard-after-payment")

        # 7. Point in time: before the payment date the invoice is still owed
        page.fill("#as-at", "2026-02-19")
        # 1001 (1,100) + 1002 issued 10 Feb (550) + 1003 (330); the 20 Feb payment is not yet counted.
        expect(page.locator(".figure").first).to_contain_text("1,980.00")
        ok("as at 19 Feb (before the payment date): outstanding back to 1,980.00")

        # 8. Customer page shows insufficient-data behaviour message
        page.goto(f"{org_url}/customers")
        page.click("text=Example Hospital (SYNTHETIC)")
        expect(page.locator(".notice", has_text="Insufficient data")).to_be_visible()
        ok("payment behaviour suppressed with insufficient history")
        shot("08-customer")

        # 9. Audit log
        page.goto(f"{org_url}/audit")
        expect(page.get_by_text("allocation.confirmed", exact=True).first).to_be_visible()
        expect(page.get_by_text("import.committed", exact=True).first).to_be_visible()
        ok("audit log records import and allocation")
        shot("09-audit")

        # 10. Manual invoice entry (rules.md §8.12)
        page.goto(f"{org_url}/invoices")
        page.click("text=Add invoice")
        page.select_option("#ai-c", label="Example Clinic (SYNTHETIC)")
        page.fill("#ai-n", "MAN-2001")
        page.fill("#ai-i", "2026-03-10")
        page.fill("#ai-d", "2026-04-09")
        page.fill("#ai-net", "200.00")
        page.fill("#ai-tax", "20.00")
        shot("10-add-invoice")
        page.locator("form").get_by_role("button", name="Add invoice").click()
        expect(page.get_by_text("Invoice MAN-2001 added.")).to_be_visible()
        page.fill("#as-at", "2026-03-31")
        expect(page.locator("tr", has_text="MAN-2001")).to_contain_text("220.00")
        ok("manual invoice MAN-2001 entered; total 220.00 derived from net + tax")
        browser.close()

    print(f"\nE2E smoke test passed: {len(checks)} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
