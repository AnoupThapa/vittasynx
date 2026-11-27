"use client";

import Link from "next/link";
import { useState } from "react";
import { apiGet, apiSend, ApiError } from "@/lib/api";
import { useOrg } from "@/components/OrgContext";
import { ErrorNotice, Notice, useAction, useLoad } from "@/components/ui";

const blank = { customer_id: "", invoice_number: "", issue_date: "", due_date: "", total_amount: "", net_amount: "", tax_amount: "", reference: "" };

/** Manual entry follows the same rules as import (rules.md §8.12); the server does all validation. */
export function AddInvoice({ onCreated }: { onCreated: () => void }) {
  const { base, org } = useOrg();
  const customers = useLoad(() => apiGet(`${base}/customers`), [base]);
  const [form, setForm] = useState(blank);
  const [confirmDup, setConfirmDup] = useState(false);
  const [created, setCreated] = useState<string | null>(null);
  const act = useAction();
  const set = (k: keyof typeof blank) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });
  const err = act.error as ApiError | null;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setCreated(null);
    const payload: any = { ...form, confirm_duplicate_number: confirmDup };
    for (const k of ["total_amount", "net_amount", "tax_amount", "reference"]) if (!payload[k]) payload[k] = null;
    const r = await act.run(() => apiSend("POST", `${base}/invoices`, payload));
    if (r) { setCreated(r.invoice_number); setForm({ ...blank, customer_id: form.customer_id }); setConfirmDup(false); onCreated(); }
  }

  return (
    <div className="panel">
      <h2>Add an invoice</h2>
      {created && <Notice kind="ok">Invoice {created} added.</Notice>}
      <ErrorNotice error={act.error} />
      <form onSubmit={submit}>
        <div className="field"><label htmlFor="ai-c">Customer</label>
          <select id="ai-c" required value={form.customer_id} onChange={set("customer_id")}>
            <option value="">Select…</option>{customers.data?.items.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
          <div className="def">Not listed? <Link href={`/o/${org.id}/customers`}>Add the customer first</Link>.</div></div>
        <div className="field"><label htmlFor="ai-n">Invoice number</label><input id="ai-n" required value={form.invoice_number} onChange={set("invoice_number")} /></div>
        <div className="inline">
          <div className="field"><label htmlFor="ai-i">Issue date</label><input id="ai-i" type="date" required value={form.issue_date} onChange={set("issue_date")} /></div>
          <div className="field"><label htmlFor="ai-d">Due date</label><input id="ai-d" type="date" required value={form.due_date} onChange={set("due_date")} /></div>
        </div>
        <div className="field" style={{ marginTop: 12 }}><label htmlFor="ai-t">Total incl. tax ({org.currency})</label>
          <input id="ai-t" inputMode="decimal" placeholder="1,100.00" value={form.total_amount} onChange={set("total_amount")} /></div>
        <div className="inline">
          <div className="field"><label htmlFor="ai-net">Net (optional)</label><input id="ai-net" inputMode="decimal" style={{ width: 120 }} value={form.net_amount} onChange={set("net_amount")} /></div>
          <div className="field"><label htmlFor="ai-tax">Tax (optional)</label><input id="ai-tax" inputMode="decimal" style={{ width: 120 }} value={form.tax_amount} onChange={set("tax_amount")} /></div>
        </div>
        <div className="def">Leave the total blank to calculate it from net + tax.</div>
        <div className="field" style={{ marginTop: 12 }}><label htmlFor="ai-r">Reference / PO (optional)</label><input id="ai-r" value={form.reference} onChange={set("reference")} /></div>
        {err?.code === "invoice_number_used_elsewhere" && (
          <div className="field"><label><input type="checkbox" style={{ width: "auto", marginRight: 6 }} checked={confirmDup} onChange={(e) => setConfirmDup(e.target.checked)} />
            Yes, this is a separate invoice for this customer</label></div>
        )}
        <button className="primary" disabled={act.busy}>Add invoice</button>
      </form>
      <p className="def">Entered invoices can't be edited afterwards. To fix one, cancel it with a reason and enter it again, or issue a credit note, so the history stays intact.</p>
    </div>
  );
}
